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

The classification covers every construct that hides an execution path, not just `if`:
`match` (whose subject always runs but whose arms do not), `except*`, and any statement
type this dispatch does not name. A `match self.quant_mode:` is config-gated exactly like
the `if` above and yields the same named variants; a `match` on a runtime value is
`data_dependent`. Falling through silently is the failure mode this reducer exists to
prevent, so an unrecognised statement that still calls a submodule is reported rather
than dropped.

The `async` spellings classify exactly like their sync ones, because `await` says when a
call may suspend, not whether it happens: `async for layer in self.layers:` is the same
repeated block as `for`, `async with` opens its body like `with`, and `x = await self.f(x)`
is the same call as `x = self.f(x)`. An `async def forward` is scanned like a `def forward`
for the same reason -- skipping it reported zero modules and zero unsupported, which reads
as "nothing to see here" rather than "this method was never looked at".

A loop's `else:` clause is reduced when the body cannot `break`, since then it always runs.
When the body can `break` the clause is still reduced, but as a two-arm merge -- the clause
against "the loop broke, so the clause never ran" -- because whether it ran is a runtime
fact and both producers are possible, so a phi names both instead of the graph picking one.
Two things are reported rather than merged: a clause holding a submodule call, which cannot
be placed on a path that may never execute, and a merge the arms cannot represent at all
(they disagree on whether the residual is None).

A `match` selector is its subject *and* every `case.guard`, so `case 0 if x.sum():` makes
the whole match data-dependent however statically readable the subject is. A match also has
no implicit "ran nothing" arm the way an `if` without `else` does: matching no case raises
MatchError, so the next statement is only reached through some case body.

A branch whose arms call no submodule is still reduced, not skipped. Its arms rebind names,
and skipping the construct left the pre-branch writer in place -- a graph claiming the old
producer, which is the same lie as dropping the calls. Merging the arms records every
possible producer as a phi, and only a merge that cannot be represented at all (arms that
disagree on whether the residual is None) is escalated to `unsupported`.

The same rule holds for the constructs with no selector to classify, and "holds no submodule
call" is not a reason to skip one either. A call-free loop is reduced through the same path
as a loop whose body calls submodules, so its body's rebindings land and its `else:` clause
reaches the two-arm merge above instead of being dropped along with the whole statement. A
call-free `with` reduces in place, because its body always runs -- either `__enter__` succeeds
and every statement in it runs, or control leaves the construct. A call-free `try` merges the
body (and its `else:`) against each handler, because reaching the next statement means one of
those happened and which one is a runtime fact, then reduces `finally:` in place, since that
runs on every outcome. Only a `CONTROL_FLOW_NODES` member this dispatch does not name is
reported outright, and it is reported whether or not it holds a call.
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

#: Statement types whose execution path cannot be read straight off source order, so they
#: are classified by `_control_flow` instead of being reduced in place.
#:
#: `Match` (3.10+) and `TryStar` (3.11+) are looked up with `getattr` and *filtered out*
#: when the running interpreter has no such node. Giving them a fallback type instead
#: (`getattr(ast, "Match", ast.If)`) would both duplicate an entry in the tuple and assert
#: an equivalence that is simply not true. On an interpreter without them the tuple is
#: exactly the original node set, no more and no less.
#:
#: The `async` spellings are here for the same reason their sync ones are: `await` says when
#: a call may suspend, not whether it happens, so `async for layer in self.layers:` runs
#: every iteration exactly like `for` and `async with` opens its body exactly like `with`.
#: Leaving them out sent both to `_unrecognized`, whose callee test sees no `self.` there
#: (the callee is the loop variable), so the async repeated block vanished while the report
#: still claimed nothing was unsupported.
CONTROL_FLOW_NODES = tuple(
    node for node in (
        ast.If, ast.For, ast.While, ast.With, ast.Try,
        ast.AsyncFor, ast.AsyncWith,
        getattr(ast, 'TryStar', None), getattr(ast, 'Match', None),
    ) if isinstance(node, type))

#: Loop spellings that bind a target and iterate an expression: `for` and `async for`.
#: Every "which names does this loop bind" / "what does it iterate" test branches on this
#: one tuple, so the async form cannot drift away from the sync one.
LOOP_NODES = (ast.For, ast.AsyncFor)

#: Loops plus `while`: the constructs reduced as a repeated block by `_loop`.
ITERATIVE_NODES = LOOP_NODES + (ast.While,)

#: `ast.Match` where the interpreter has it, else None. Kept separate from the tuple above
#: because the match handler needs the type for its own isinstance dispatch.
MATCH_NODE = getattr(ast, 'Match', None)

#: `with` / `async with`: the body always runs, so a call-free one reduces in place and the
#: `as` target is a rebinding whose producer this reducer cannot see.
WITH_NODES = (ast.With, ast.AsyncWith)

#: `try` / `try*`: the body and each handler are alternative outcomes, so a call-free one
#: merges its arms exactly like an `if` whose arms call nothing. `TryStar` is 3.11+ and is
#: filtered out on an older interpreter for the same reason it is in `CONTROL_FLOW_NODES`.
TRY_NODES = tuple(node for node in (ast.Try, getattr(ast, 'TryStar', None))
                  if isinstance(node, type))


def _nested_loop_targets(statement):
    """Loop variables bound by any loop nested inside `statement` (its own excluded).

    The gate deciding whether a construct contains submodule calls has to see these.
    `for block in self.blocks:` whose body is another `for layer in block.layers:` only
    ever calls `layer(...)`, so without the inner binding the outer loop looks call-free
    and its entire body is dropped before traversal even starts -- the same silent hole
    this reducer is supposed to close, one level up.

    `async for` binds its target exactly like `for`, so it counts here too: an
    `async for` nested in a `for` (or the other way round) must not make the enclosing
    loop look call-free.
    """
    targets = set()
    for node in ast.walk(statement):
        if isinstance(node, LOOP_NODES) and node is not statement:
            targets |= set(_targets_written(node.target))
    return targets


def _outermost_calls(calls):
    """Keep only the outermost call of each nesting chain in `calls`.

    `_submodule_calls()` walks, so for `self.route(self.pre(x))` it yields the outer *and*
    the inner call, while `_add_call_tree()` descends into arguments on its own. Handing it
    both records `self.pre` a second time -- a phantom step plus a phantom fork on its input,
    which is precisely the "graph that is not ground truth" this script exists to prevent.
    The inner call is already the nested source of the outer one, so only the outermost call
    of a chain is a separate step of the graph.
    """
    nested = set()
    for _, call in calls:
        for child in ast.walk(call):
            if child is not call and isinstance(child, ast.Call):
                nested.add(id(child))
    return [(path, node) for path, node in calls if id(node) not in nested]


def _selector_kind(selectors):
    """Classify the expression(s) that decide which arm of a branch runs.

    A `match` arm is picked by its subject *and* by its `case.guard`, so every one of them
    has to be construction-time config for the choice to be static. Classifying the subject
    alone labelled `match self.quant_mode: case 0 if x.sum():` as
    `selected_by: execution_profile` -- a static claim about a choice a tensor makes at
    runtime -- and left the guard's own calls out of the graph, because arm extraction only
    walks `case.body`.
    """
    kinds = [_test_kind(selector) for selector in selectors if selector is not None]
    for kind in kinds:
        if kind != 'config_gated':
            return kind
    return 'config_gated'


def _match_condition(statement):
    """The `match` selector as source text: the subject, plus every guard that narrows an arm.

    The subject alone is not the whole selector once guards exist, and `condition` is what a
    reader of `dataflow_source.json` uses to work out which deviation to declare.
    """
    condition = ast.unparse(statement.subject)
    guards = [f'case {index} if {ast.unparse(case.guard)}'
              for index, case in enumerate(statement.cases) if case.guard is not None]
    return f'{condition} | ' + '; '.join(guards) if guards else condition


def _sorted_call_sites(calls):
    """Stable `[{symbol, lineno}]` view of a list of (callee path, Call node) pairs."""
    return sorted(({'symbol': path, 'lineno': node.lineno} for path, node in calls),
                  key=lambda item: (item['lineno'], item['symbol']))


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
    """The outermost submodule call in an expression, if any.

    `await` is transparent. `x = await layer(x)` invokes `layer` with the same arguments
    and binds the same result; the coroutine wrapper says when the caller may suspend, not
    whether the submodule ran or what it wrote. Treating `Await` as "not a call" made every
    awaited invocation look like a plain rebinding, so the reducer dropped it without a
    word -- the same silent hole, spelled asynchronously.
    """
    while isinstance(value, ast.Await):
        value = value.value
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
        self.loop_targets = []     # stack of loop-variable names enclosing this statement

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
        if isinstance(statement, CONTROL_FLOW_NODES):
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
        self._unrecognized(statement)

    def _submodule_calls(self, statement, loop_targets=()):
        """(callee path, Call node) for every submodule-shaped call inside `statement`.

        `self.<name>` is the usual callee, but inside `for layer in self.layers:` the callee
        is the loop variable, so the enclosing loop targets count as submodule shapes too.
        "Does this construct contain a call" and "which calls does it report" must share one
        predicate: when they disagree, a construct is judged to contain a call and then
        reports an empty call list.
        """
        targets = set(loop_targets)
        found = []
        for node in ast.walk(statement):
            if not isinstance(node, ast.Call):
                continue
            path = _attr_path(node.func)
            if path.startswith('self.') or path.split('[')[0].split('.')[0] in targets:
                found.append((path, node))
        return found

    def _unrecognized(self, statement):
        """Never let a statement that calls a submodule fall off the end silently.

        The dispatch above is a hardcoded list, so anything it does not name -- today a
        `raise` or `assert` carrying a submodule call, tomorrow whatever a new Python adds
        -- used to reach the implicit `return None` and vanish. The graph then looked
        complete while a whole call was missing, and the downstream gate never fired
        because `unsupported` stayed empty. Reporting one extra explicit "unsupported" is
        always cheaper than that hole.

        Both examples named here are measured, not illustrative. An `async for` used to be
        listed as a third one and was not: async constructs are now classified by
        `_control_flow` like their sync spellings, so this fallback never sees them.
        """
        calls = self._submodule_calls(statement, self._enclosing_loop_targets())
        if not calls:
            return
        self.unsupported.append({
            'lineno': statement.lineno,
            'end_lineno': getattr(statement, 'end_lineno', statement.lineno),
            'construct': type(statement).__name__,
            'severity': 'unparsable',
            'call_symbols': sorted({path for path, _ in calls}),
            'call_sites': _sorted_call_sites(calls),
            'reason': f'{type(statement).__name__} 包含 submodule 调用，但不属于此 reducer '
                      f'已识别的语句类型，无法确定其执行语义；'
                      f'需要在 config.deviations 中显式声明',
        })

    def _enclosing_loop_targets(self):
        """Union of the loop variables of every `for` currently being traversed."""
        if not self.loop_targets:
            return set()
        return set().union(*self.loop_targets)

    def _control_flow(self, statement):
        # A loop over a ModuleList calls the *loop variable* (`for layer in self.layers:
        # x = layer(x)`), not `self.<name>`, so requiring a `self.` callee misses the single
        # most important repeated-block shape in the family. A construct *nested* in such a
        # loop body must see the same targets, otherwise a `match` under
        # `for layer in self.layers:` looks call-free and vanishes without a trace.
        loop_targets = self._enclosing_loop_targets()
        if isinstance(statement, LOOP_NODES):
            loop_targets |= set(_targets_written(statement.target))
        loop_targets |= _nested_loop_targets(statement)

        calls = self._submodule_calls(statement, loop_targets)

        # A loop over submodules is the repeated-block construct, not a variant: every
        # iteration runs. Extract the body once and record the iteration count separately.
        if isinstance(statement, ITERATIVE_NODES):
            # Call-free loops take the same path: the body still rebinds names, and only
            # `_loop` reaches `_loop_else`. Sending them elsewhere dropped a call-free
            # loop's whole `else:` clause, which is the same lie as dropping its calls.
            self._loop(statement, loop_targets)
            return

        if MATCH_NODE is not None and isinstance(statement, MATCH_NODE):
            self._match(statement, calls, loop_targets)
            return

        if isinstance(statement, ast.If):
            condition = ast.unparse(statement.test)
            self._selector_branch(
                statement,
                arms=(('then', statement.body), ('else', statement.orelse)),
                selectors=(statement.test,),
                condition=condition,
                calls=calls,
                construct='If',
                reason=f'分支条件 `{condition}` 依赖运行期数据，展开后的数据流图不可靠；'
                       f'需要在 config 中以 deviations 显式声明所走分支',
                implicit_passthrough=not statement.orelse,
            )
            return

        if not calls:
            if isinstance(statement, WITH_NODES):
                self._with(statement)
            elif isinstance(statement, TRY_NODES):
                self._try(statement)
            else:
                self._unhandled_control_flow(statement)
            return
        self.unsupported.append({
            'lineno': statement.lineno,
            'end_lineno': getattr(statement, 'end_lineno', statement.lineno),
            'construct': type(statement).__name__,
            'severity': 'unparsable',
            'call_symbols': sorted({path for path, _ in calls}),
            'call_sites': _sorted_call_sites(calls),
            'reason': f'{type(statement).__name__} 包含 submodule 调用，此 reducer 无法'
                      f'确定其执行语义；需要显式 deviation 声明',
        })

    def _with(self, statement):
        """A call-free `with`: the body always runs, so reduce it in place.

        `with` opens no alternative execution path -- either `__enter__` succeeds and every
        statement in the body runs, or it raises and control leaves the construct. So there
        is nothing to merge and nothing to report. Skipping the body left the pre-`with`
        writer in place: `x = self.prep(x)` / `y = self.other(x)` / `with self.ctx: x = y`
        made the next read of `x` name only `self.prep`, a producer the body had already
        overwritten -- the same lie as dropping a call.

        An `as` target is bound to whatever `__enter__` returned, which this reducer cannot
        see, so it is recorded as a rebinding with no known producer. Leaving the previous
        writer there would be the stale-producer lie again, and inventing one would be worse.

        The pop runs before the body is reduced, and that order carries semantics: a body
        statement reading the target (`with open('f') as x:` / `y = x`) propagates whatever
        `last_writer['x']` holds when it is reduced, so popping afterwards would hand `y`
        the pre-`with` producer -- the stale-producer lie this construct exists to prevent.
        """
        for item in statement.items:
            if item.optional_vars is None:
                continue
            for name in _targets_written(item.optional_vars):
                self.last_writer.pop(name, None)
                self.phi_writers.pop(name, None)
                self.known_none.discard(name)
        for inner in statement.body:
            self._statement(inner)

    def _try(self, statement):
        """A call-free `try`: body and handlers are alternative outcomes, so merge them.

        Reaching the statement after the `try` means either the body (and its `else:`) ran to
        the end, or an exception diverted into exactly one handler. Which one is a runtime
        fact, so the arms merge into a phi naming every possible producer, exactly like an
        `if` whose arms call nothing. No variant is emitted: `selected_by: execution_profile`
        would claim the profile decides whether an exception was raised, which it does not.
        `finally:` runs on every outcome, so it is reduced in place *after* the merge rather
        than being treated as one more arm.

        Arms that disagree on whether the residual is None cannot be merged at all, and
        `_extract_variants` escalates that once, under this construct's own label and range.
        """
        arms = [('try', list(statement.body) + list(statement.orelse))]
        arms.extend((f'except{index}', list(handler.body))
                    for index, handler in enumerate(statement.handlers))
        self._extract_variants(statement, arms=arms, condition=None, call_symbols=[],
                               call_sites=[], implicit_passthrough=False,
                               static_selector=False)
        for inner in statement.finalbody:
            self._statement(inner)

    def _unhandled_control_flow(self, statement):
        """A `CONTROL_FLOW_NODES` member no branch above names: report it, never drop it.

        Unreachable today -- the tuple is `if`, `match`, the loops, `with` and `try`, and each
        has a handler -- but a node added to that tuple without one used to land in a
        call-free path that reduced nothing and reported only a `= None` write, so the
        construct vanished while the report still claimed nothing was unsupported. Booking it
        as `unparsable` whether or not it holds a submodule call is the same argument
        `_unrecognized` makes one statement over.
        """
        calls = self._submodule_calls(statement, self._enclosing_loop_targets())
        self.unsupported.append({
            'lineno': statement.lineno,
            'end_lineno': getattr(statement, 'end_lineno', statement.lineno),
            'construct': type(statement).__name__,
            'severity': 'unparsable',
            'call_symbols': sorted({path for path, _ in calls}),
            'call_sites': _sorted_call_sites(calls),
            'reason': f'{type(statement).__name__} 属于控制流节点，但此 reducer 没有对应的'
                      f'归约分支，无法确定其执行语义；需要在 config.deviations 中显式声明',
        })

    def _selector_branch(self, statement, arms, selectors, condition, calls, construct,
                         reason, implicit_passthrough):
        """`if`/`match`: classify the selector, then extract the arms or report the branch.

        Shared so the two cannot drift: the same selector spelled `if self.quant_mode:` and
        `match self.quant_mode:` is exactly as statically resolvable, so it must get the same
        severity and the same named-variant extraction.

        A selector that is not fixed before the run *and* whose arms call submodules cannot be
        resolved at all, so it is reported and needs a deviation declaration. When the arms
        call nothing there is still state to keep: an arm that rebinds a name changes every
        later read of it, and dropping the branch here used to leave the pre-branch writer in
        place -- a graph that silently claims the old producer, which is the same failure mode
        as dropping the calls. Merging the arms records both possibilities as a phi instead,
        and escalates to `unsupported` only where the merge is not representable (arms that
        disagree on whether the residual is None, which `_extract_variants` detects).
        """
        call_symbols = sorted({path for path, _ in calls})
        call_sites = _sorted_call_sites(calls)
        kind = _selector_kind(selectors)
        if calls and kind != 'config_gated':
            self.unsupported.append({
                'lineno': statement.lineno,
                'end_lineno': getattr(statement, 'end_lineno', statement.lineno),
                'construct': construct,
                'severity': 'data_dependent' if kind == 'data_dependent' else 'unparsable',
                'condition': condition,
                'call_symbols': call_symbols,
                'call_sites': call_sites,
                'reason': reason,
            })
            return
        self._extract_variants(
            statement,
            arms=arms,
            condition=condition,
            call_symbols=call_symbols,
            call_sites=call_sites,
            implicit_passthrough=implicit_passthrough,
            static_selector=kind == 'config_gated',
        )

    def _match(self, statement, calls, loop_targets):
        """`match subject:` -- the subject always runs, the case bodies do not.

        Three consequences, and getting any one of them wrong costs real graph content:

        * A call in `statement.subject` executes whichever arm wins, so it belongs on the
          main path as an ordinary call. Lumping it in with the arm calls dropped a step
          that provably happens and -- when the arms themselves call nothing -- turned a
          perfectly extractable statement into a blocking error purely because of the
          syntax it happened to be written in. Only the *outermost* call of a nested subject
          is added: `_add_call_tree()` descends into arguments itself, so feeding it both
          halves of `self.route(self.pre(x))` records `self.pre` twice and invents a fork on
          `x` that the source does not have.
        * The subject is classified exactly like an `if` test. `match self.quant_mode:` is
          no less statically resolved than `if self.quant_mode:`, and the module docstring
          is explicit that a config-gated selector is extracted as named variants instead of
          rejected; rejecting it is what once made every real model report its main compute
          as unextractable. So are the guards: `case 0 if x.sum():` picks its arm on a tensor
          value, so the whole match is data-dependent whatever the subject says.
        * A match runs exactly one case body or raises MatchError -- "ran nothing and carried
          on" is not a reachable outcome -- so unlike an `if` without `else` it has no
          implicit passthrough arm. Granting it one added a path that cannot execute, whose
          `returns` then claimed the pre-match value (`from_call: -1`), and made
          `case object():` (which matches every object, exactly like a bare `case _:`) look
          non-exhaustive on top of that.
        """
        subject_calls = self._submodule_calls(statement.subject, loop_targets)
        subject_ids = {id(node) for _, node in subject_calls}
        for _, node in _outermost_calls(subject_calls):
            # Evaluated before any arm is considered, and its result is not bound to a name
            # here, so it is recorded the same way as a bare expression call.
            self._add_call_tree(node, [], node)

        # A guard's own calls stay in `arm_calls`: they are arm-conditional, so they never
        # join the main path, but a match that gets reported must list them instead of
        # losing a `self.check(x)` that provably appears in the source.
        arm_calls = [(path, node) for path, node in calls if id(node) not in subject_ids]
        condition = _match_condition(statement)
        self._selector_branch(
            statement,
            arms=tuple((f'case[{index}]', list(case.body))
                       for index, case in enumerate(statement.cases)),
            selectors=(statement.subject, *(case.guard for case in statement.cases)),
            condition=condition,
            calls=arm_calls,
            construct='Match',
            reason=f'match 目标 `{condition}` 无法在运行前确定命中哪个 case，'
                   f'展开后的数据流图不可靠；'
                   f'需要在 config 中以 deviations 显式声明所走分支',
            implicit_passthrough=False,
        )

    def _extract_variants(self, statement, arms, condition, call_symbols, call_sites,
                          implicit_passthrough=False, static_selector=True,
                          construct=None, lineno=None, end_lineno=None):
        """Reduce each arm, then merge the arms' writer/phi state.

        Shared by `if` and `match` so the two cannot drift. When the selector is
        construction-time config (`static_selector`) exactly one arm runs per deployment, so
        each arm is emitted as a named variant and the caller binds its `execution_profile`
        to it instead of losing everything inside the branch. When the selector is *not*
        static the arms are still reduced -- an arm that rebinds a name changes every later
        read of it, and skipping the branch used to leave the pre-branch writer in place, a
        graph claiming the old producer -- but no variant is emitted, because
        `selected_by: execution_profile` would claim a choice the profile cannot make. The
        arms' writers merge into a phi instead: every possible producer, none invented.
        An arm that produces neither a call nor an `unsupported` entry contributes its state
        but no variant in either mode, so `branch_id` is allocated lazily to leave no gap in
        the numbering callers bind to.

        `implicit_passthrough` marks a construct where "run nothing at all" is itself one of
        the outcomes. That is an `if` with no `else` and a breakable loop's `else:` clause
        (the loop may have broken, in which case the clause never ran); a `match` that
        matches nothing raises MatchError instead of continuing, so granting it a passthrough
        arm invents an execution that cannot happen.

        `construct`/`lineno`/`end_lineno` name the construct an escalation is reported
        against. They default to `statement`, which is right for `if` and `match`, but a
        loop's `else:` clause is not the loop: reporting the clause's rebind against `For`
        and the loop's whole range would make one source fact answer for a different line
        range than the clause-holds-a-call path reports, and a declared deviation is matched
        on exactly those two fields (`check_dataflow.py` D5 -> `_source_ref_covers`).
        """
        branch_id = None
        saved_writers = dict(self.last_writer)
        saved_phi = {name: list(writers) for name, writers in self.phi_writers.items()}
        saved_known_none = set(self.known_none)
        arm_states = []
        for label, body in arms:
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
            if not static_selector or (not produced and not unsupported_produced):
                arm_states.append((dict(self.last_writer), {
                    name: list(writers) for name, writers in self.phi_writers.items()},
                                   set(self.known_none)))
                continue
            if branch_id is None:
                branch_id = self.next_variant_id
                self.next_variant_id += 1
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

        if implicit_passthrough:
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
            entry = {
                'lineno': statement.lineno if lineno is None else lineno,
                'end_lineno': (getattr(statement, 'end_lineno', statement.lineno)
                               if end_lineno is None else end_lineno),
                'construct': (type(statement).__name__ if construct is None
                              else construct),
                'severity': 'unparsable',
            }
            if condition is not None:
                # A loop's `else:` clause has no selector expression to name -- it is gated
                # on "the loop was not broken" -- so it is left out and D5 falls back to
                # `construct`, rather than recording a null the user cannot match on.
                entry['condition'] = condition
            entry['call_symbols'] = call_symbols
            entry['call_sites'] = call_sites
            entry['reason'] = '不同分支对残差是否为 None 的结论不一致；' \
                              '后续 fused 调用无法绑定到唯一的残差拓扑，' \
                              '需要在 config.deviations 中显式声明'
            self.unsupported.append(entry)
        self.known_none = set.intersection(*(state[2] for state in arm_states)) \
            if arm_states else saved_known_none

    def _loop(self, statement, loop_targets=()):
        """A loop whose body calls submodules: the repeated-block construct.

        Every iteration executes, so the body belongs on the main path. What the graph must
        not claim is a specific iteration count when the bound is dynamic — that is recorded
        as metadata, not as flattened repetition.

        `async for` reduces identically: `await` decides where the coroutine may suspend,
        not whether an iteration runs. The loop's own `else:` clause is a different matter
        and is handled by `_loop_else` *after* this loop is booked, so a call there lands on
        the main path instead of being tagged as one of the repeated iterations.
        """
        iterable = ast.unparse(statement.iter) if isinstance(statement, LOOP_NODES) else \
            ast.unparse(statement.test)
        calls_before = len(self.calls)
        # Publish this loop's variables for the duration of the body so a nested construct
        # recognises `layer.first(x)` as a submodule call instead of an unrelated function.
        own_targets = set(_targets_written(statement.target)) \
            if isinstance(statement, LOOP_NODES) else set()
        visible = set(loop_targets) | own_targets
        self.loop_targets.append(visible)
        try:
            for inner in statement.body:
                self._statement(inner)
        finally:
            self.loop_targets.pop()
        # An inner loop already attributed its own calls; the outer one takes the rest
        # rather than overwriting the inner loop_id and listing the call twice.
        produced = [call_id for call_id in range(calls_before, len(self.calls))
                    if 'loop' not in self.calls[call_id]]
        if produced:
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
        self._loop_else(statement, visible)

    def _loop_else(self, statement, loop_targets):
        """A loop's `else:` clause -- reduced when it must run, reported when it may not.

        `for ... else:` / `while ... else:` runs the clause only when the loop finished
        without `break`, so the clause is not part of the repeated block. It used to be
        skipped outright: `for i in range(3): pass` + `else: x = self.fallback(x)` produced
        `calls=[]`, `unsupported=[]`, `blocking_unsupported=0`, i.e. a whole submodule call
        gone while the report claimed nothing was unsupported -- the exact hole
        `_unrecognized` exists to close, one construct over.

        Two readings, and the graph must not pick silently between them:

        * no `break` lexically in the body: the clause always runs, so it is main-path code
          that merely happens to be written inside the loop statement. Reduce it in place
          (the loop variable is still bound after the loop, so it stays visible).
        * the body can `break`: whether the clause runs is a runtime fact. Placing its calls
          on the main path would claim an edge that may never execute, so report them.

        A nested loop's own `break` counts as "can break" too. Telling the two apart needs
        control-flow analysis this reducer does not do, and over-reporting one blocking
        construct is the cheap direction -- it is what the `_unrecognized` docstring argues.

        Both branches below answer for the *clause*, under the same `*Else` label and the
        same line range, whether or not the clause holds a submodule call. Per-statement
        labels would make one source fact (this clause may not run, and it rebinds the
        residual) something a user has to declare twice -- and differently depending on
        whether the loop body happened to call a submodule, since that alone decides which
        branch runs.

        A call-free clause is *merged*, not reported and not dropped. It has no call to
        place, but it still rebinds names, and returning early here left the pre-clause
        writer in place: `x = self.prep(x)` / `y = self.other(x)` / a breakable
        `for layer in self.layers:` / `else: x = y` made the next read of `x` name only
        `layer`, a producer the clause may have overwritten -- the same lie as dropping the
        calls, and inconsistent with the break-free branch above, which reduces the very
        same clause in place. So the clause is reduced against the arm where the loop broke
        and it never ran, exactly as an `if` with no `else` is, and the phi names both
        producers. No variant is emitted: `selected_by: execution_profile` would claim the
        profile decides whether the loop broke, which it does not.
        """
        clause = getattr(statement, 'orelse', None) or []
        if not clause:
            return
        can_break = any(isinstance(node, ast.Break)
                        for inner in statement.body
                        for node in ast.walk(inner))
        if not can_break:
            self.loop_targets.append(set(loop_targets))
            try:
                for inner in clause:
                    self._statement(inner)
            finally:
                self.loop_targets.pop()
            return
        last = clause[-1]
        clause_end = getattr(last, 'end_lineno', last.lineno)
        calls = [call for inner in clause
                 for call in self._submodule_calls(inner, loop_targets)]
        if not calls:
            # Nothing to place, but the clause still rebinds names. Reduce it against the
            # "the loop broke, so this never ran" arm and let the merge keep every possible
            # producer; `_extract_variants` escalates -- once, under the clause's own label
            # and range -- only where the two arms cannot be merged at all, i.e. where they
            # disagree on whether the residual is None, which is what the `= None` clause
            # used to be reported for by hand here.
            self.loop_targets.append(set(loop_targets))
            try:
                self._extract_variants(
                    statement,
                    arms=(('else', clause),),
                    condition=None,
                    call_symbols=[],
                    call_sites=[],
                    implicit_passthrough=True,
                    static_selector=False,
                    construct=f'{type(statement).__name__}Else',
                    lineno=clause[0].lineno,
                    end_lineno=clause_end,
                )
            finally:
                self.loop_targets.pop()
            return
        self.unsupported.append({
            'lineno': clause[0].lineno,
            'end_lineno': clause_end,
            'construct': f'{type(statement).__name__}Else',
            'severity': 'unparsable',
            'call_symbols': sorted({path for path, _ in calls}),
            'call_sites': _sorted_call_sites(calls),
            'reason': f'{type(statement).__name__} 的 else 子句只在循环未被 break 时执行，'
                      f'循环体内存在 break，此 reducer 不跟踪其是否触发，'
                      f'无法确定其中的 submodule 调用是否在主路径上；'
                      f'需要在 config.deviations 中显式声明',
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

    `async def forward` counts as a forward. Skipping it did not raise or warn: the class
    simply matched no method, so the file reported `module_count: 0` and an async forward
    was indistinguishable from a file with no model in it -- every call in it invisible to
    the gate downstream.
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
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
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
