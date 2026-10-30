#!/usr/bin/env python3
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Derive the ground-truth dataflow graph of a module's forward() from its AST.

The point of this script is that forward() *is* the dataflow graph. Asking an AI to
read the source and then attest "the residual paths are correct" throws away a free,
machine-checkable ground truth. Here we recover it deterministically:

  * every statement is reduced to (writes, reads, called submodule)
  * every read is resolved to the *last writer* of that variable
  * a merge (`a + b + c`) records its operand count and each operand's last writer
  * a variable read by 2+ later calls before being overwritten is a fork (parallel branch)
  * a variable written early and read much later is a shortcut, and the number of
    intervening calls is its overlap window

Output is `dataflow_source.json`, consumed by check_dataflow.py.

Scope and honesty: this handles the straight-line `forward()` shape that transformer
decoder layers overwhelmingly use (assignments, tuple assignments, submodule calls,
binary merges). Control flow is classified rather than uniformly rejected, because
"unsupported" is not one thing:

  * `config_gated`   the test reads only construction-time config/flags, so exactly one
                     branch runs for a given deployment. Each branch is extracted as a
                     named variant; a caller states which one its profile selected.
  * `data_dependent` the test reads a tensor//runtime value, so the graph genuinely varies
                     per token. Needs an explicit deviation declaration.
  * `unparsable`     reflection, dynamic dispatch, or a construct this reducer cannot read.

Only the latter two land in `unsupported`. Treating a quantisation-mode `if` as
unsupported made every real model report its main compute as unextractable, which is
what forced callers to hand-declare the very edges this script exists to derive.
"""
import argparse
import ast
import json
import os
import sys


class _Unsupported(Exception):
    """Raised when a construct would make the derived graph unsound."""


#: Names that mark a branch test as selecting an execution *mode* rather than reading data.
#: These are passed down the call stack as plain booleans by every runner in this family
#: (prefill vs decode, graph-capture vs eager), so a given profile fixes them before the
#: first token. They are recorded as the variant's condition, never silently resolved.
MODE_FLAG_HINTS = ('is_prefill', 'is_decode', 'prefill', 'decode', 'use_aclgraph',
                   'aclgraph', 'is_graph', 'capture', 'warmup', 'training', 'is_train')

#: Attribute reads whose value is fixed when the module is constructed. `self.<name>` set
#: from a config field cannot change between invocations, so a branch on it is one static
#: choice per deployment rather than a fork in the dataflow.
CONFIG_ATTR_HINTS = ('size', 'mode', 'enable', 'enabled', 'use_', 'is_moe', 'n_', 'num_',
                     'quant', 'dtype', 'tp', 'ep', 'pp', 'cp', 'dp', 'experts', 'offload',
                     'streams', 'eplb', 'absorb', 'fused', 'impl', 'backend', 'version')

#: A literal this large is a placeholder or a mistake, not a layer count. Reporting it
#: would hand the consumer an integer that dominates any graph built from it, and JSON
#: readers that parse numbers as doubles lose exactness past 2**53 — so it is reported
#: as unknown size instead.
MAX_STATIC_MODULE_COUNT = 10 ** 6


def _test_kind(test):
    """Classify a branch test as 'config_gated', 'data_dependent' or 'unparsable'.

    The distinction that matters: does this test's value get fixed before the run, or does
    it depend on the tensors flowing through? A quantisation mode or a TP size is the
    former; a value read out of a tensor is the latter.
    """
    names, attributes, calls = [], [], []
    for node in ast.walk(test):
        if isinstance(node, ast.Call):
            calls.append(_attr_path(node.func))
        elif isinstance(node, ast.Attribute):
            path = _attr_path(node)
            if path.startswith('self.'):
                attributes.append(path[len('self.'):])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id != 'self':
                names.append(node.id)

    # A call inside the test can do anything (`.item()`, `.any()`, a predicate on a tensor),
    # so it is only safe when it is a plain size/shape query on a config-shaped attribute.
    for call in calls:
        tail = call.rsplit('.', 1)[-1]
        if tail not in ('len', 'int', 'bool', 'getattr'):
            return 'data_dependent'

    def _is_config_attr(name):
        low = name.lower()
        return any(hint in low for hint in CONFIG_ATTR_HINTS)

    def _is_mode_flag(name):
        low = name.lower()
        return any(hint in low for hint in MODE_FLAG_HINTS)

    if not names and not attributes:
        return 'config_gated'  # a literal test, e.g. `if True:`
    if all(_is_config_attr(a) or _is_mode_flag(a) for a in attributes) and \
       all(_is_mode_flag(n) for n in names):
        return 'config_gated'
    return 'data_dependent'


def _attr_path(node):
    """Render `self.self_attn[0]` / `self.mlp` as a stable dotted string."""
    if isinstance(node, ast.Attribute):
        base = _attr_path(node.value)
        return f'{base}.{node.attr}' if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        base = _attr_path(node.value)
        index = node.slice
        if isinstance(index, ast.Constant):
            return f'{base}[{index.value}]'
        if (isinstance(index, ast.UnaryOp)
                and isinstance(index.op, (ast.UAdd, ast.USub))
                and isinstance(index.operand, ast.Constant)
                and isinstance(index.operand.value, int)
                and not isinstance(index.operand.value, bool)):
            sign = -1 if isinstance(index.op, ast.USub) else 1
            return f'{base}[{sign * index.operand.value}]'
        if isinstance(index, ast.Name):
            return f'{base}[{index.id}]'
        return f'{base}[?]'
    if isinstance(node, ast.Call):
        return _attr_path(node.func)
    return ''


def _names_read(node):
    """Local variable names read anywhere inside an expression.

    `self` is dropped: it appears in every submodule call (`self.mlps[0](x)`) as the
    base of the callee path, never as a dataflow value, so keeping it would make
    every call look like it reads a shared tensor.
    """
    names = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            if child.id == 'self':
                continue
            names.append(child.id)
    return names


#: Producer id for a value that enters forward() as an argument. Call ids are
#: non-negative indices into `calls`, so -1 can never collide with one, and it stays
#: sortable alongside them. Consumers read it as "produced by the caller, upstream of
#: every node in this method".
INPUT = -1


def _parameter_names(func):
    """Names bound by forward()'s signature (excluding `self`).

    Only these get the INPUT producer. A read of some other unwritten name is a global
    or a constant, not a tensor crossing this method's input boundary.
    """
    spec = func.args
    names = []
    for group in (getattr(spec, 'posonlyargs', []), spec.args, spec.kwonlyargs):
        names.extend(argument.arg for argument in group)
    for extra in (spec.vararg, spec.kwarg):
        if extra is not None:
            names.append(extra.arg)
    return {name for name in names if name != 'self'}


def _targets_written(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        written = []
        for element in target.elts:
            written.extend(_targets_written(element))
        return written
    return []


def _unpacked_bindings(target, value):
    """Pair literal tuple/list targets with name or constant values."""
    if isinstance(target, ast.Name) and isinstance(value, (ast.Name, ast.Constant)):
        return [(target.id, value)]
    if (isinstance(target, (ast.Tuple, ast.List))
            and isinstance(value, (ast.Tuple, ast.List))
            and len(target.elts) == len(value.elts)):
        bindings = []
        for child_target, child_value in zip(target.elts, value.elts):
            children = _unpacked_bindings(child_target, child_value)
            if children is None:
                return None
            bindings.extend(children)
        return bindings
    return None


def _call_of(value):
    """The outermost submodule call in an expression, if any."""
    if isinstance(value, ast.Call):
        return value
    return None


def _merge_operands(value):
    """Flatten `a + b + c` into [a, b, c]; return None when not an add-merge."""
    if not isinstance(value, ast.BinOp) or not isinstance(value.op, ast.Add):
        return None
    operands = []

    def flatten(node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            flatten(node.left)
            flatten(node.right)
        else:
            operands.append(node)

    flatten(value)
    return operands


def _submodules(class_node):
    """Map attribute name -> declared size from __init__ (ModuleList length or 1)."""
    declared = {}
    init = next((n for n in class_node.body
                 if isinstance(n, ast.FunctionDef) and n.name == '__init__'), None)
    if init is None:
        return declared
    for node in ast.walk(init):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        for target in targets:
            if not (isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == 'self'):
                continue
            size = 1
            if isinstance(value, ast.Call) and _attr_path(value.func).endswith('ModuleList'):
                size = None
                if value.args:
                    arg = value.args[0]
                    if isinstance(arg, (ast.ListComp, ast.GeneratorExp)):
                        comp = arg.generators[0]
                        iterable = comp.iter
                        if isinstance(iterable, (ast.List, ast.Tuple)):
                            size = len(iterable.elts)
                        elif (isinstance(iterable, ast.Call)
                              and _attr_path(iterable.func) == 'range'
                              and 1 <= len(iterable.args) <= 3
                              and not iterable.keywords
                              and len(arg.generators) == 1
                              and not comp.ifs):
                            try:
                                bounds = [ast.literal_eval(bound) for bound in iterable.args]
                                if all(isinstance(bound, int) for bound in bounds):
                                    size = len(range(*bounds))
                                    if size > MAX_STATIC_MODULE_COUNT:
                                        size = None
                            except (ValueError, TypeError, OverflowError):
                                pass
                    elif isinstance(arg, (ast.List, ast.Tuple)):
                        size = len(arg.elts)
            declared[target.attr] = size
    return declared


class ForwardGraph:
    """Reduce one forward() body to a call sequence plus resolved dataflow edges."""

    def __init__(self, class_name, func):
        self.class_name = class_name
        self.func = func
        self.calls = []           # ordered submodule invocations
        self.merges = []          # add-merges with resolved operands
        self.residual_initializations = []  # fused calls that seed a None carry stream
        self.unsupported = []     # constructs that would make the graph unsound
        self.variants = []        # config-gated branch arms, selected per execution profile
        self.next_variant_id = 0  # allocated before recursion, so nested branches stay unique
        self.loops = []           # submodule loops (repeated blocks) on the main path
        self.last_writer = {}     # variable -> call id that last wrote it
        self.phi_writers = {}     # variable -> mutually-exclusive branch writers
        self.reads_of = {}        # (variable, writer) -> [call ids that read it]
        self.parameters = _parameter_names(func)
        self.known_none = set()    # local bindings proven to be None at this point

    def _record_reads(self, value, call_id, skip=()):
        """Resolve every name read in `value` to its last writer.

        `call_id is None` means "read by something that is not a call node" (today:
        the return statement). Such a read still needs provenance in the output, but
        it must never enter `reads_of` — those lists are call ids and get sorted.

        A name with no writer that IS a forward() parameter still has a producer: the
        caller. It is filed under the INPUT sentinel so that two submodules reading the
        same input tensor register as a fork. Without this, the most common parallel
        shape in MoE code -- `shared_expert(hidden_states)` beside `gate(hidden_states)`,
        both reading the layer input -- looks like a chain, which is exactly the defect
        the fork check exists to catch. Names that are neither written nor parameters
        (globals, module constants) are left unresolved: they are not tensors on this
        graph's input boundary and inventing a producer for them would fabricate edges.
        """
        resolved = []
        for name in _names_read(value):
            if name in skip:
                continue
            phi_sources = self.phi_writers.get(name) or []
            if phi_sources:
                for writer in phi_sources:
                    resolved.append({'variable': name, 'from_call': writer})
                    if call_id is not None:
                        self.reads_of.setdefault((name, writer), []).append(call_id)
                continue
            writer = self.last_writer.get(name)
            resolved.append({'variable': name, 'from_call': writer})
            if call_id is None:
                continue
            if writer is not None:
                self.reads_of.setdefault((name, writer), []).append(call_id)
            elif name in self.parameters:
                self.reads_of.setdefault((name, INPUT), []).append(call_id)
        return resolved

    def _record_fused_merge(self, entry, writes, reads_expr, statement,
                            initialized=()):
        """Record a residual join performed *inside* a called submodule.

        The `a + b` form is the minority in production transformer code. The dominant shape
        is a fused norm that both consumes and returns the residual:

            hidden, residual = self.input_layernorm(hidden, past_residual)

        The add happens inside the kernel, so there is no BinOp to find — which is why a
        BinOp-only reducer reports zero merges on a model whose every layer has two
        residuals. The join is still observable: a call that reads a residual-carrying
        variable and writes one is a merge point, and the tensor it carried in is the
        bypassed path. Recording it here is what lets a checker verify residual topology
        without asking anyone to hand-declare it.
        """
        if reads_expr is None:
            return
        read_vars = [r['variable'] for r in entry['reads'] if r.get('variable')]
        carried = [v for v in read_vars if 'residual' in v.lower()]
        produced = [w for w in writes if 'residual' in w.lower()]
        if not carried or not produced:
            return
        carried = [v for v in carried if v not in initialized]
        if not carried:
            self.residual_initializations.append({
                'call_id': entry['call_id'],
                'lineno': statement.lineno,
                'kind': 'fused_residual_init',
                'symbol': entry['symbol'],
                'writes': list(writes),
                'note': '残差绑定在调用前明确为 None；该调用初始化残差流，不是汇合点',
            })
            return
        operands = [r for r in entry['reads']
                    if r.get('variable') in carried or r.get('variable') in read_vars]
        self.merges.append({
            'call_id': entry['call_id'],
            'lineno': statement.lineno,
            'kind': 'fused_in_call',
            'symbol': entry['symbol'],
            'operand_count': len(operands),
            'operands': operands,
            'carries_in': carried,
            'writes': list(writes),
            'note': '残差在被调用模块内部相加（fused add-norm），源码中没有独立的 `a + b`；'
                    '合并点即该调用本身',
        })

    def _add_call(self, symbol, writes, reads_expr, node, kind='call'):
        call_id = len(self.calls)
        entry = {
            'call_id': call_id,
            'kind': kind,
            'symbol': symbol,
            'lineno': node.lineno,
            'writes': writes,
            'reads': self._record_reads(reads_expr, call_id) if reads_expr is not None else [],
        }
        self.calls.append(entry)
        for name in writes:
            self.last_writer[name] = call_id
            self.phi_writers.pop(name, None)
        return entry

    def _nested_call_sources(self, value, node):
        if isinstance(value, ast.Call) and _attr_path(value.func).startswith('self.'):
            return [self._add_call_tree(value, None, node)['call_id']]
        sources = []
        for child in ast.iter_child_nodes(value):
            sources.extend(self._nested_call_sources(child, node))
        return sources

    def _add_call_tree(self, call, writes, node):
        nested_sources = []
        plain_reads = []
        for value in [*call.args, *(keyword.value for keyword in call.keywords)]:
            sources = self._nested_call_sources(value, node)
            if sources:
                nested_sources.extend(sources)
            else:
                plain_reads.append(value)

        call_id = len(self.calls)
        actual_writes = writes if writes is not None else [f'__call_{call_id}_result']
        entry = self._add_call(_attr_path(call.func), [], None, node)
        resolved = []
        for value in plain_reads:
            resolved.extend(self._record_reads(value, entry['call_id']))
        for source_id in nested_sources:
            source_call = self.calls[source_id]
            variable = (source_call.get('writes') or [f'__call_{source_id}_result'])[0]
            resolved.append({'variable': variable, 'from_call': source_id})
            self.reads_of.setdefault((variable, source_id), []).append(entry['call_id'])
        entry['reads'] = resolved
        entry['writes'] = actual_writes
        for name in actual_writes:
            self.last_writer[name] = entry['call_id']
            self.phi_writers.pop(name, None)
        return entry

    def _resolve_merge_operands(self, operands, node):
        resolved = []
        for operand in operands:
            nested_sources = self._nested_call_sources(operand, node)
            for source_id in nested_sources:
                source_call = self.calls[source_id]
                variable = (source_call.get('writes')
                            or [f'__call_{source_id}_result'])[0]
                resolved.append({
                    'variable': variable,
                    'from_call': source_id,
                    'expression': ast.unparse(operand),
                })

            names = []

            def collect_plain_names(value):
                if (isinstance(value, ast.Call)
                        and _attr_path(value.func).startswith('self.')):
                    return
                if isinstance(value, ast.Name) and isinstance(value.ctx, ast.Load):
                    names.append(value.id)
                    return
                for child in ast.iter_child_nodes(value):
                    collect_plain_names(child)

            collect_plain_names(operand)
            for name in dict.fromkeys(names):
                if (name not in self.last_writer and name not in self.phi_writers
                        and name not in self.parameters):
                    continue
                sources = list(self.phi_writers.get(name) or [])
                if not sources:
                    sources = [self.last_writer.get(name)]
                for writer in sources:
                    resolved.append({
                        'variable': name,
                        'from_call': writer,
                        'expression': ast.unparse(operand),
                    })
        return resolved

    def build(self):
        for statement in self.func.body:
            self._statement(statement)
        self._mark_forks()
        return self

    def _statement(self, statement):
        if isinstance(statement, (ast.Expr, ast.Pass)) and not _call_of(
                getattr(statement, 'value', None)):
            return
        if isinstance(statement, ast.Return):
            self._returns(statement)
            return
        if isinstance(statement, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            self._control_flow(statement)
            return
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            self._assign(statement)
            return
        if isinstance(statement, ast.AugAssign):
            self._aug_assign(statement)
            return
        if isinstance(statement, ast.Expr):
            call = _call_of(statement.value)
            if call is not None:
                self._add_call_tree(call, [], statement)
            return

    def _control_flow(self, statement):
        # A loop over a ModuleList calls the *loop variable* (`for layer in self.layers:
        # x = layer(x)`), not `self.<name>`, so requiring a `self.` callee misses the single
        # most important repeated-block shape in the family.
        loop_targets = set()
        if isinstance(statement, ast.For):
            loop_targets = set(_targets_written(statement.target))
        contains_call = any(
            isinstance(node, ast.Call)
            and (_attr_path(node.func).startswith('self.')
                 or _attr_path(node.func).split('[')[0].split('.')[0] in loop_targets)
            for node in ast.walk(statement))
        if not contains_call:
            # A call-free branch can still change provenance (notably ``residual = None``).
            # We cannot attach a selected execution arm to the later fused call, so reject
            # the construct explicitly instead of silently carrying stale writer state.
            writes_none = any(
                isinstance(node, (ast.Assign, ast.AnnAssign))
                and isinstance(getattr(node, 'value', None), ast.Constant)
                and node.value.value is None
                for node in ast.walk(statement))
            if writes_none:
                self.unsupported.append({
                    'lineno': statement.lineno,
                    'end_lineno': getattr(statement, 'end_lineno', statement.lineno),
                    'construct': type(statement).__name__,
                    'severity': 'unparsable',
                    'call_symbols': [],
                    'call_sites': [],
                    'reason': '分支虽然没有 submodule 调用，但修改了残差绑定；'
                              '无法在后续 fused 调用前确定该路径是否初始化残差，'
                              '需要在 config.deviations 中显式声明',
                })
            return
        call_symbols = sorted({
            _attr_path(node.func)
            for node in ast.walk(statement)
            if isinstance(node, ast.Call) and _attr_path(node.func).startswith('self.')
        })
        call_sites = sorted((
            {'symbol': _attr_path(node.func), 'lineno': node.lineno}
            for node in ast.walk(statement)
            if isinstance(node, ast.Call) and _attr_path(node.func).startswith('self.')
        ), key=lambda item: (item['lineno'], item['symbol']))

        # A loop over submodules is the repeated-block construct, not a variant: every
        # iteration runs. Extract the body once and record the iteration count separately.
        if isinstance(statement, (ast.For, ast.While)):
            self._loop(statement)
            return
        if not isinstance(statement, ast.If):
            self.unsupported.append({
                'lineno': statement.lineno,
                'end_lineno': getattr(statement, 'end_lineno', statement.lineno),
                'construct': type(statement).__name__,
                'severity': 'unparsable',
                'call_symbols': call_symbols,
                'call_sites': call_sites,
                'reason': f'{type(statement).__name__} 包含 submodule 调用，此 reducer 无法'
                          f'确定其执行语义；需要显式 deviation 声明',
            })
            return

        kind = _test_kind(statement.test)
        condition = ast.unparse(statement.test)
        if kind != 'config_gated':
            self.unsupported.append({
                'lineno': statement.lineno,
                'end_lineno': getattr(statement, 'end_lineno', statement.lineno),
                'construct': 'If',
                'severity': 'data_dependent',
                'condition': condition,
                'call_symbols': call_symbols,
                'call_sites': call_sites,
                'reason': f'分支条件 `{condition}` 依赖运行期数据，展开后的数据流图不可靠；'
                          f'需要在 config 中以 deviations 显式声明所走分支',
            })
            return

        # Config-gated: each arm is a self-contained variant selected before the run. Extract
        # them as siblings so a caller can bind its execution_profile to one, instead of
        # losing every call inside the branch.
        branch_id = self.next_variant_id
        self.next_variant_id += 1
        saved_writers = dict(self.last_writer)
        saved_phi = {name: list(writers) for name, writers in self.phi_writers.items()}
        saved_known_none = set(self.known_none)
        arm_states = []
        for label, body in (('then', statement.body), ('else', statement.orelse)):
            if not body:
                continue
            self.last_writer = dict(saved_writers)
            self.phi_writers = {name: list(writers)
                                for name, writers in saved_phi.items()}
            self.known_none = set(saved_known_none)
            calls_before = len(self.calls)
            unsupported_before = len(self.unsupported)
            for inner in body:
                self._statement(inner)
            produced = list(range(calls_before, len(self.calls)))
            unsupported_produced = list(range(unsupported_before, len(self.unsupported)))
            if not produced and not unsupported_produced:
                arm_states.append((dict(self.last_writer), {
                    name: list(writers) for name, writers in self.phi_writers.items()},
                                   set(self.known_none)))
                continue
            membership = {'branch_id': branch_id, 'arm': label}
            for call_id in produced:
                self.calls[call_id].setdefault('variant_memberships', []).append(
                    dict(membership))
                self.calls[call_id].setdefault('variant', membership)
            for unsupported_id in unsupported_produced:
                self.unsupported[unsupported_id].setdefault(
                    'variant_memberships', []).append(dict(membership))
            self.variants.append({
                'branch_id': branch_id,
                'arm': label,
                'lineno': statement.lineno,
                'condition': condition,
                'selected_by': 'execution_profile',
                'call_ids': produced,
                'unsupported_ids': unsupported_produced,
            })
            arm_states.append((dict(self.last_writer), {
                name: list(writers) for name, writers in self.phi_writers.items()},
                               set(self.known_none)))

        if not statement.orelse:
            arm_states.append((saved_writers, saved_phi, saved_known_none))
        merged_writers = dict(saved_writers)
        merged_phi = {name: list(writers) for name, writers in saved_phi.items()}
        variables = set(saved_writers) | set(saved_phi)
        for writers, phis, known_none in arm_states:
            variables.update(writers)
            variables.update(phis)
        for name in variables:
            sources = []
            for writers, phis, _ in arm_states:
                if phis.get(name):
                    sources.extend(phis[name])
                elif name in writers:
                    sources.append(writers[name])
                elif name in self.parameters:
                    sources.append(INPUT)
            unique_sources = list(dict.fromkeys(sources))
            if len(unique_sources) > 1:
                merged_phi[name] = unique_sources
                merged_writers[name] = unique_sources[-1]
            elif unique_sources:
                merged_phi.pop(name, None)
                if unique_sources[0] == INPUT:
                    merged_writers.pop(name, None)
                else:
                    merged_writers[name] = unique_sources[0]
        self.last_writer = merged_writers
        self.phi_writers = merged_phi
        known_none_states = [state[2] for state in arm_states]
        if known_none_states and any(state != known_none_states[0]
                                     for state in known_none_states[1:]):
            self.unsupported.append({
                'lineno': statement.lineno,
                'end_lineno': getattr(statement, 'end_lineno', statement.lineno),
                'construct': type(statement).__name__,
                'severity': 'unparsable',
                'condition': condition,
                'call_symbols': call_symbols,
                'call_sites': call_sites,
                'reason': '不同分支对残差是否为 None 的结论不一致；'
                          '后续 fused 调用无法绑定到唯一的残差拓扑，'
                          '需要在 config.deviations 中显式声明',
            })
        self.known_none = set.intersection(*(state[2] for state in arm_states)) \
            if arm_states else saved_known_none

    def _loop(self, statement):
        """A `for`/`while` whose body calls submodules: the repeated-block construct.

        Every iteration executes, so the body belongs on the main path. What the graph must
        not claim is a specific iteration count when the bound is dynamic — that is recorded
        as metadata, not as flattened repetition.
        """
        iterable = ast.unparse(statement.iter) if isinstance(statement, ast.For) else \
            ast.unparse(statement.test)
        calls_before = len(self.calls)
        for inner in statement.body:
            self._statement(inner)
        produced = list(range(calls_before, len(self.calls)))
        if not produced:
            return
        for call_id in produced:
            self.calls[call_id]['loop'] = {'loop_id': len(self.loops)}
        self.loops.append({
            'loop_id': len(self.loops),
            'lineno': statement.lineno,
            'construct': type(statement).__name__,
            'iterates_over': iterable,
            'call_ids': produced,
            'note': '循环体每次迭代都执行，属于主路径；迭代次数由运行期决定，'
                    '不在此处展开为固定次数',
        })

    def _rebind_unpacked(self, targets, value):
        if not any(isinstance(target, (ast.Tuple, ast.List)) for target in targets):
            return False
        bindings = []
        for target in targets:
            items = _unpacked_bindings(target, value)
            if items is None:
                return False
            bindings.extend(items)
        # Evaluate every source against the old state before assigning any target,
        # so ``left, right = right, left`` preserves both original producers.
        states = []
        for name, source in bindings:
            source_name = source.id if isinstance(source, ast.Name) else None
            writer = self.last_writer.get(source_name)
            phis = list(self.phi_writers.get(source_name) or [])
            if (writer is None and not phis and source_name in self.parameters
                    and source_name not in self.known_none):
                writer = INPUT
            states.append((name, writer, phis,
                           source_name in self.known_none
                           or (isinstance(source, ast.Constant) and source.value is None)))
        for name, writer, phis, known_none in states:
            self.last_writer.pop(name, None)
            self.phi_writers.pop(name, None)
            self.known_none.discard(name)
            if writer is not None:
                self.last_writer[name] = writer
            if phis:
                self.phi_writers[name] = phis
            if known_none:
                self.known_none.add(name)
        return True

    def _assign(self, statement):
        # A local type annotation without a value does not change its binding.
        if isinstance(statement, ast.AnnAssign) and statement.value is None:
            return
        targets = (statement.targets if isinstance(statement, ast.Assign)
                   else [statement.target])
        writes = []
        for target in targets:
            writes.extend(_targets_written(target))
        value = statement.value

        operands = _merge_operands(value)
        if operands is not None and len(operands) >= 2:
            # Resolve operands against the last_writer state BEFORE this merge is added:
            # `h = residual + h + shortcut` reads the h written upstream, not itself.
            resolved = self._resolve_merge_operands(operands, statement)
            entry = self._add_call('<merge>', writes, None, statement, kind='merge')
            entry['reads'] = resolved
            for read in resolved:
                if read.get('variable') is not None and read.get('from_call') is not None:
                    self.reads_of.setdefault(
                        (read['variable'], read['from_call']), []).append(entry['call_id'])
            self.merges.append({
                'call_id': entry['call_id'],
                'lineno': statement.lineno,
                'operand_count': len(operands),
                'operands': resolved,
                'writes': writes,
            })
            return

        # A simple ``residual = None`` is an initialization boundary, not a tensor merge.
        # Keep the fact until the first call consumes the binding so fused add-norm does not
        # mistake the optional carry for a real second operand.
        if isinstance(value, ast.Constant) and value.value is None and writes:
            self.known_none.update(writes)
            for name in writes:
                self.last_writer.pop(name, None)
                self.phi_writers.pop(name, None)
            return

        call = _call_of(value)
        if call is not None:
            # `h = self.mlps[0](h)` reads the PREVIOUS writer of h and then rebinds it.
            # _add_call resolves reads before updating last_writer, so in-place rebinding
            # needs no special case — and the read must be kept, it is the activation edge.
            initialized = set(_names_read(value)) & self.known_none
            entry = self._add_call_tree(call, writes, statement)
            self._record_fused_merge(entry, writes, value, statement, initialized)
            self.known_none.difference_update(writes)
            return

        if self._rebind_unpacked(targets, value):
            return

        # Plain rebinding (`x = y`) — propagate provenance without inventing a node.
        names = _names_read(value)
        if len(names) == 1 and writes:
            if names[0] in self.known_none:
                self.known_none.update(writes)
            else:
                self.known_none.difference_update(writes)
            source = self.last_writer.get(names[0])
            for name in writes:
                if source is None:
                    self.last_writer.pop(name, None)
                else:
                    self.last_writer[name] = source

    def _aug_assign(self, statement):
        """`hidden += residual` is a two-operand merge written in place.

        Reducing it to a plain read would lose the join: the target is both an operand and
        the result, so the residual edge into it disappears and the layer reads as a chain.
        """
        writes = _targets_written(statement.target)
        if not writes or not isinstance(statement.op, ast.Add):
            return
        target = ast.Name(id=writes[0], ctx=ast.Load())
        # A hand-built node has no position; copy the statement's so anything
        # that later reports an expression location has one to read.
        ast.copy_location(target, statement)
        operands = _merge_operands(statement.value)
        if operands is None:
            operands = [statement.value]
        resolved = self._resolve_merge_operands([target, *operands], statement)
        call_id = len(self.calls)
        for read in resolved:
            if read.get('variable') is not None and read.get('from_call') is not None:
                self.reads_of.setdefault(
                    (read['variable'], read['from_call']), []).append(call_id)
        entry = self._add_call('<merge>', writes, None, statement, kind='merge')
        entry['reads'] = resolved
        self.merges.append({
            'call_id': entry['call_id'],
            'lineno': statement.lineno,
            'kind': 'in_place_add',
            'operand_count': 1 + len(operands),
            'operands': resolved,
            'writes': writes,
        })

    def _returns(self, statement):
        """Record what the function hands back.

        `return self.head(x)` is a real submodule invocation and must become a call
        node — dropping it would silently lose the last op of any forward() that
        returns a call directly.
        """
        if statement.value is None:
            self.returns = []
            return
        operands = _merge_operands(statement.value)
        if operands is not None and len(operands) >= 2:
            resolved = self._resolve_merge_operands(operands, statement)
            entry = self._add_call('<merge>', [], None, statement, kind='merge')
            entry['reads'] = resolved
            for read in resolved:
                if read.get('variable') is not None and read.get('from_call') is not None:
                    self.reads_of.setdefault(
                        (read['variable'], read['from_call']), []).append(entry['call_id'])
            self.merges.append({
                'call_id': entry['call_id'],
                'lineno': statement.lineno,
                'operand_count': len(operands),
                'operands': resolved,
                'writes': [],
            })
            self.returns = [{'variable': None, 'from_call': entry['call_id']}]
            return
        call = _call_of(statement.value)
        if call is not None:
            entry = self._add_call_tree(call, [], statement)
            self.returns = [{'variable': None, 'from_call': entry['call_id']}]
            return
        self.returns = self._record_reads(statement.value, None)

    def _mark_forks(self):
        """A value read by 2+ later calls before being overwritten is a fork.

        `from_call` is INPUT when the forked value is a forward() argument: the two
        readers are still parallel consumers of one tensor, which is what a fork means.
        """
        self.forks = []
        for (variable, writer), readers in sorted(self.reads_of.items()):
            unique = sorted(set(readers))
            if len(unique) < 2:
                continue
            self.forks.append({
                'variable': variable,
                'from_call': writer,
                'read_by_calls': unique,
                'branch_count': len(unique),
                'from_input': writer == INPUT,
            })
        # A shortcut is ANY edge whose consumer is far downstream of its producer —
        # not only a forked one. LongCat's `shortcut_mlp_output` (written by self.mlp,
        # read 6 calls later by the three-way merge) has exactly one reader, and it is
        # the ScMoE overlap window: the compute the all-to-all can hide behind.
        self.shortcuts = []
        for (variable, writer), readers in sorted(self.reads_of.items()):
            if writer == INPUT:
                # An overlap window is a span between two calls: work that can hide behind
                # the producer's latency. A method argument is produced before any call in
                # this method, so there is no window here to report.
                continue
            for reader in sorted(set(readers)):
                span = reader - writer
                if span >= 3:
                    self.shortcuts.append({
                        'variable': variable,
                        'from_call': writer,
                        'to_call': reader,
                        'overlap_window_calls': span,
                        'overlapped_calls': list(range(writer + 1, reader)),
                    })

    def edges(self):
        """Derived edges: (from_call, to_call, via variable, type)."""
        fork_keys = {(f['variable'], f['from_call']) for f in self.forks}
        shortcut_keys = {(s['variable'], s['from_call'], s['to_call'])
                         for s in self.shortcuts}
        merge_ids = {m['call_id'] for m in self.merges}
        derived = []
        for call in self.calls:
            for read in call['reads']:
                source = read.get('from_call')
                variable = read.get('variable')
                if source is None or variable is None:
                    continue
                if (variable, source, call['call_id']) in shortcut_keys:
                    edge_type = 'shortcut'
                elif call['call_id'] in merge_ids:
                    edge_type = 'residual'
                elif (variable, source) in fork_keys:
                    edge_type = 'parallel_branch'
                else:
                    edge_type = 'activation'
                derived.append({
                    'from_call': source,
                    'to_call': call['call_id'],
                    'via': variable,
                    'type': edge_type,
                })
        return derived

    def to_dict(self):
        return {
            'class_name': self.class_name,
            'method': self.func.name,
            'forward_lineno': self.func.lineno,
            'calls': self.calls,
            'edges': self.edges(),
            'merges': self.merges,
            'residual_initializations': self.residual_initializations,
            'forks': getattr(self, 'forks', []),
            'shortcuts': getattr(self, 'shortcuts', []),
            'returns': getattr(self, 'returns', []),
            'variants': self.variants,
            'loops': self.loops,
            'unsupported': self.unsupported,
        }


def extract_file(path, class_names=None, forward_name='forward', include_variants=True):
    """Extract one graph per (class, forward-ish method).

    `include_variants` also picks up `forward_absorb` / `forward_w8a8int8` style siblings.
    These are not alternative spellings of `forward` — they are the methods a deployment
    actually runs, selected by config at construction time. Analysing only `forward` reports
    the dispatcher and misses every op in the method that executed.
    """
    with open(path, encoding='utf-8') as stream:
        tree = ast.parse(stream.read(), filename=path)
    modules = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if class_names and node.name not in class_names:
            continue
        methods = [n for n in node.body
                   if isinstance(n, ast.FunctionDef)
                   and (n.name == forward_name
                        or (include_variants and n.name.startswith(forward_name + '_')))]
        if not methods:
            continue
        submodules = _submodules(node)
        for func in methods:
            graph = ForwardGraph(node.name, func).build().to_dict()
            graph['submodules'] = submodules
            graph['source_path'] = path
            graph['is_primary'] = func.name == forward_name
            modules.append(graph)
    return modules


def main():
    parser = argparse.ArgumentParser(
        description='Derive the ground-truth dataflow graph of forward() from the AST')
    parser.add_argument('-s', '--source', required=True, action='append',
                        help='model source file (repeatable)')
    parser.add_argument('--class', dest='classes', action='append',
                        help='limit extraction to these class names (repeatable)')
    parser.add_argument('--forward-name', default='forward',
                        help='method to analyse (default: forward)')
    parser.add_argument('--no-variants', action='store_true',
                        help='only analyse the exact --forward-name, skipping forward_* siblings')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()

    modules = []
    for path in args.source:
        if not os.path.exists(path):
            sys.stderr.write(f'错误: 文件不存在: {path}\n')
            sys.exit(2)
        modules.extend(extract_file(path, args.classes, args.forward_name,
                                    include_variants=not args.no_variants))

    # Report the two severities separately: a config-gated branch is extracted, so counting it
    # as unsupported is what previously made a fully-readable model look unreadable.
    blocking = sum(1 for m in modules for u in m['unsupported']
                   if u.get('severity') in ('data_dependent', 'unparsable'))
    report = {
        'schema_version': 2,
        'script': 'extract_dataflow.py',
        'forward_name': args.forward_name,
        'module_count': len(modules),
        'blocking_unsupported': blocking,
        'config_gated_variants': sum(len(m['variants']) for m in modules),
        'merge_count': sum(len(m['merges']) for m in modules),
        'modules': modules,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as stream:
            stream.write(text + '\n')
        print(f'dataflow 已写入: {args.output}  modules={len(modules)} '
              f'variants={report["config_gated_variants"]} '
              f'merges={report["merge_count"]} blocking={blocking}')
    else:
        print(text)


if __name__ == '__main__':
    main()
