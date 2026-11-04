#!/usr/bin/env python3
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
"""
breakdown_common.py — shared helpers for schema v2 analysis_config + manifest.

Pure standard library. No model imports, no NPU dependency.

Key responsibilities:
- schema_version detection (v1 legacy vs v2)
- expand layer_groups (indices / range) into a full model-layer index set
- expand trace_instances into exact op index multisets (union + duplicate detection)
- source_ref parsing / existence validation
- minimal JSON-Schema (draft-07 subset) validation so we don't require jsonschema pkg
"""
import hashlib
import json
import os
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# schema version
# ---------------------------------------------------------------------------

#: Marker recorded by extract_model_manifest.py when the deployed checkpoint's config.json
#: could not be read. Everything it could not confirm falls back to Python default args,
#: which describe a model *family* rather than this deployment.
UNREACHABLE_CHECKPOINT_MARKER = 'checkpoint config.json 不可达'

#: Manifest facts whose confidence backs `num_main_layers`.
LAYER_COUNT_FACT_KEYS = ('num_layers', 'num_hidden_layers', 'n_layer')


def sha256_file(path):
    """Return the SHA256 digest of a file without loading it all into memory."""
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


_SIMPLE_JSON_PATH_KEY = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]*$')


def json_path(*parts):
    """Build an unambiguous JSONPath while preserving simple dotted paths."""
    result = '$'
    quote_keys = any(
        isinstance(part, str) and not _SIMPLE_JSON_PATH_KEY.fullmatch(part)
        for part in parts)
    for part in parts:
        if isinstance(part, int):
            if part < 0:
                raise ValueError('JSONPath array indices must be non-negative')
            result += f'[{part}]'
        elif (isinstance(part, str) and not quote_keys
              and _SIMPLE_JSON_PATH_KEY.fullmatch(part)):
            result += '.' + part
        elif isinstance(part, str):
            result += '[' + json.dumps(part, ensure_ascii=False) + ']'
        else:
            raise TypeError('JSONPath parts must be strings or integers')
    return result


def json_path_child(path, part):
    """Append one key or array index to an existing canonical JSONPath."""
    parts = _typed_json_path_parts(path)
    if parts is None:
        raise ValueError(f'invalid JSONPath: {path!r}')
    return json_path(*(parts + [part]))


def _typed_json_path_parts(path):
    if not isinstance(path, str) or not path.startswith('$'):
        return None
    parts = []
    index = 1
    decoder = json.JSONDecoder()
    while index < len(path):
        marker = path[index]
        if marker == '.':
            index += 1
            end = index
            while end < len(path) and path[end] not in '.[':
                end += 1
            if end == index:
                return None
            parts.append(path[index:end])
            index = end
            continue
        if marker != '[':
            return None
        index += 1
        if index >= len(path):
            return None
        if path[index] == '"':
            try:
                value, consumed = decoder.raw_decode(path[index:])
            except (json.JSONDecodeError, ValueError):
                return None
            if not isinstance(value, str):
                return None
            index += consumed
            if index >= len(path) or path[index] != ']':
                return None
            parts.append(value)
            index += 1
            continue
        end = path.find(']', index)
        if end < 0:
            return None
        value = path[index:end]
        if not value.isdigit():
            return None
        parts.append(int(value))
        index = end + 1
    return parts


def json_path_parts(path):
    """Parse dotted, indexed, and JSON-quoted bracket JSONPath locators."""
    parts = _typed_json_path_parts(path)
    if parts is None:
        return None
    return [str(part) for part in parts]


def resolve_config_path(config, path):
    """Return whether a JSONPath-like locator resolves in ``config``."""
    parts = _typed_json_path_parts(path)
    if parts is None:
        return False
    current = config
    for part in parts:
        if isinstance(current, dict) and isinstance(part, str) and part in current:
            current = current[part]
            continue
        if isinstance(current, list) and isinstance(part, int) and part < len(current):
            current = current[part]
            continue
        return False
    return True


def effective_duration_us(op) -> float:
    """A kernel's duration for summation, counting a doubly-reported collective once.

    `analyze_kernels.py` marks the second record of a collective msprof reports twice (an
    identical-timestamp COMMUNICATION pair: the communication entry plus the AIV kernel running
    it) with `duplicate_of`. Both rows stay in `operators` so op indices remain stable, so every
    place that sums durations must skip the marked one or it double-counts real device work.
    """
    if op.get('duplicate_of') is not None:
        return 0.0
    return op.get('duration_us', 0) or 0.0


def is_duplicate_record(op) -> bool:
    """Whether this row restates device work another row already accounts for."""
    return op.get('duplicate_of') is not None


#: The asymmetry between source evidence and trace evidence, in one place.
#:
#: Source is the architecture truth: it declares every path the model can take. A trace
#: witnesses one capture — one step, one rank, post-sharding, post-fusion — so it sees a
#: SUBSET of those paths. That asymmetry makes the two directions of disagreement mean
#: entirely different things:
#:
#:   trace has it, breakdown does not  ->  the breakdown is WRONG (error).
#:       Something demonstrably executed and the decomposition fails to account for it.
#:       No appeal to the source can excuse it. This is C1/C6's job.
#:
#:   source has it, trace does not     ->  NOT an error (info at most).
#:       An unexecuted path, a shard on another rank, a kernel fused away, a layer this
#:       step skipped. The source remains the truth; the trace simply did not witness it.
#:
#:   every trace kernel is accounted for -> the decomposition is correct by default.
#:       Once coverage is complete, a scalar the trace cannot arbitrate (layer count,
#:       expert count) is settled by the source alone. The trace may not overturn it, and
#:       may not withhold a pass for failing to corroborate it.
#:
#: A check that reverses either direction turns absent data into a defect, which is what
#: made three captures with identical inputs land on three different verdicts.
TRACE_CAN_ONLY_FALSIFY_COVERAGE = True


def trace_disagreement_severity(in_trace: bool, in_breakdown: bool) -> str:
    """Severity for one source/trace disagreement, per the asymmetry above.

    The single place that encodes the direction rule, so a new check cannot quietly invert
    it. `in_trace` means the trace witnesses the thing; `in_breakdown` means the
    decomposition (and hence the source it was derived from) accounts for it.
    """
    if in_trace and not in_breakdown:
        return 'error'      # demonstrably ran, unaccounted for -> the breakdown is wrong
    if in_breakdown and not in_trace:
        return 'info'       # source declares a path this capture did not exercise
    return 'none'


def manifest_fact_confidence(manifest: dict, fact_keys=LAYER_COUNT_FACT_KEYS) -> str:
    """Lowest confidence among the manifest facts backing a field.

    Returns 'low' when the manifest itself admits the number is a fallback. This reports
    how well-evidenced the scalar is; it does NOT license the trace to overrule it. Under
    `TRACE_CAN_ONLY_FALSIFY_COVERAGE` a low-confidence layer count still outranks a trace
    kernel tally, because the tally is post-sharding and covers only the paths this step
    executed — it cannot arbitrate a scalar in either direction. Low confidence is
    therefore surfaced as an evidence gap (and caps the exit conclusion at
    `verified_unbound_scalars`), never as grounds to fail the decomposition.

    This single definition is shared by A1, MT1 and MA1 — when each check decided severity
    for itself, A1 was taught to defer to the trace while MT1 and MA1 kept failing the
    correct config against the fallback manifest.
    """
    if not isinstance(manifest, dict):
        return 'unknown'
    if any(UNREACHABLE_CHECKPOINT_MARKER in str(gap)
           for gap in manifest.get('evidence_gaps') or []):
        return 'low'
    order = {'low': 0, 'unknown': 0, 'medium': 1, 'high': 2}
    found = [f.get('confidence', 'unknown') for f in manifest.get('facts') or []
             if f.get('key') in fact_keys]
    if not found:
        return 'unknown'
    return min(found, key=lambda c: order.get(c, 0))


def detect_schema_version(config: dict) -> int:
    v = config.get('schema_version')
    if v == 2:
        return 2
    if v == 1:
        return 1
    # legacy configs had no schema_version but used layer_types/layer_structure
    if 'layer_types' in config or 'layer_structure' in config:
        return 1
    if 'architecture' in config and 'trace_instances' in config:
        return 2
    return 1


# ---------------------------------------------------------------------------
# layer group expansion
# ---------------------------------------------------------------------------

def expand_layer_group_indices(group: dict) -> list:
    """Return the explicit list of model layer indices covered by one layer_group."""
    if 'model_layer_indices' in group and group['model_layer_indices']:
        return list(group['model_layer_indices'])
    rng = group.get('model_layer_range')
    if rng and len(rng) == 2:
        start, end = rng
        return list(range(start, end + 1))
    return []


def collect_main_layer_indices(architecture: dict):
    """Return (index_list, duplicates, groups_by_index) for main (non-prediction) layers."""
    seen = {}
    duplicates = []
    for group in architecture.get('layer_groups', []) or []:
        for idx in expand_layer_group_indices(group):
            if idx in seen:
                duplicates.append(idx)
            seen[idx] = group.get('type', '?')
    return sorted(seen.keys()), duplicates, seen


def collect_prediction_layer_indices(architecture: dict) -> dict:
    """Return {model_layer_index: prediction_module_type}."""
    out = {}
    for pm in architecture.get('prediction_modules', []) or []:
        for idx in pm.get('model_layer_indices', []) or []:
            out[idx] = pm.get('type', '?')
    return out


# ---------------------------------------------------------------------------
# trace instance expansion (exact coverage)
# ---------------------------------------------------------------------------

def instance_op_indices(inst: dict) -> list:
    """Exact op indices for one trace instance. op_indices wins; else op_range inclusive."""
    if inst.get('op_indices'):
        return list(inst['op_indices'])
    rng = inst.get('op_range')
    if rng and len(rng) == 2:
        start, end = rng
        return list(range(start, end + 1))
    return []


def build_v2_report_view(config: dict):
    """Translate a schema-v2 config into uniform report/metrics sections.

    Returns a list of dicts (in first-seen order):
      {name, structure(node dict), multiplier, group_type}

    multiplier = observed invocation count for that layer_group_type, DERIVED from
    trace_instances — never the learned model-layer count, so a rank-local/partial
    trace is not extrapolated to the full model. When config['structures'] has a
    representative tree for the group it is used verbatim; otherwise a minimal leaf
    node is synthesized from the representative trace instance's op range so the
    group still appears in the observed-execution tree with real timing.

    Returns None for non-v2 configs.
    """
    if config.get('schema_version') != 2:
        return None
    structures = config.get('structures') or {}
    instances = config.get('trace_instances') or []

    groups = {}
    order = []
    for inst in instances:
        gt = inst.get('layer_group_type') or f"model_layer_{inst.get('model_layer_index')}"
        if gt not in groups:
            groups[gt] = []
            order.append(gt)
        groups[gt].append(inst)

    sections = []
    for gt in order:
        insts = groups[gt]
        multiplier = len(insts)
        rep = None
        for inst in insts:
            rid = inst.get('representative_instance_id')
            if rid:
                rep = next((x for x in insts if x.get('instance_id') == rid), None)
                if rep:
                    break
        rep = rep or insts[0]
        rep_ops = instance_op_indices(rep)
        template = structures.get(gt)
        if template:
            # Use the representative TEMPLATE for the child breakdown, but overlay the real
            # representative-instance op range so timing reflects one actual invocation.
            # If the template's leaves already carry op_indices we keep them; otherwise we
            # attach the instance ops to the root so the section is never a zero-timing node.
            import copy as _copy
            node = _copy.deepcopy(template)
            if not _node_has_any_op_indices(node):
                node['op_indices'] = rep_ops
            _attach_report_aggregate_indices(
                node, rep_ops, [instance_op_indices(i) for i in insts]
            )
        else:
            node = {
                'name': gt,
                'semantic': f'observed {gt}',
                'op_indices': rep_ops,
            }
        sections.append({
            'name': node.get('name', gt),
            'structure': node,
            'multiplier': multiplier,
            'group_type': gt,
            'representative_instance_id': rep.get('instance_id'),
            'representative_op_indices': rep_ops,
            'all_instance_op_indices': [instance_op_indices(i) for i in insts],
        })
    return sections


def _attach_report_aggregate_indices(node: dict, representative_ops: list,
                                     all_instance_ops: list) -> None:
    """Attach exact per-invocation op mappings to a representative report tree.

    Schema-v2 structures describe one representative invocation. Reports still show
    that compact tree, but timing must use every observed invocation rather than
    multiplying one layer's duration by the invocation count. Mapping by position is
    valid because sublayer validation requires each invocation to have the same op
    count/order as the representative template.
    """
    positions = {op_index: pos for pos, op_index in enumerate(representative_ops)}

    def visit(current: dict) -> None:
        aggregate = []
        groups = []
        for op_index in current.get('op_indices', []) or []:
            pos = positions.get(op_index)
            if pos is None:
                continue
            mapped = [ops[pos] for ops in all_instance_ops if pos < len(ops)]
            aggregate.extend(mapped)
            groups.append(mapped)
        current['_report_op_indices'] = aggregate
        current['_report_op_groups'] = groups
        current['_report_invocation_count'] = len(all_instance_ops)
        for child in current.get('children', []) or []:
            visit(child)

    visit(node)


def _node_has_any_op_indices(node) -> bool:
    if not isinstance(node, dict):
        return False
    if node.get('op_indices'):
        return True
    return any(_node_has_any_op_indices(c) for c in node.get('children', []) or [])


# Main-compute kernel kinds that may NEVER be excluded as "profiler/bookkeeping".
MAIN_COMPUTE_KINDS = {
    'MatMul', 'MatMulV2', 'QuantBatchMatmulV3', 'GroupedMatmul', 'GemmEx', 'BatchMatMul',
    'FlashAttentionScore', 'FusedInferAttentionScore', 'KvQuantSparseFlashAttention',
    'HcomAllGather', 'HcomReduceScatter', 'HcomAllToAll', 'hcom_allReduce', 'HcomAllReduce',
    'RmsNorm', 'LayerNormV3', 'InplaceAddRmsNorm', 'AddRmsNormDynamicQuant',
    'MlaPrologV3', 'DequantSwigluQuant', 'LightningIndexerQuant', 'MoeGatingTopKHash',
    'RotaryMul', 'GatherV2', 'GatherV3', 'ScatterNdUpdate',
    'MoeDistributeDispatchV2', 'MoeDistributeCombineV2',
    'ArgMaxV2', 'ArgMaxWithValue',
}


def is_main_compute_kind(kind: str) -> bool:
    if not kind:
        return False
    base = kind.split('/')[0]
    if base in MAIN_COMPUTE_KINDS or kind in MAIN_COMPUTE_KINDS:
        return True
    if base.startswith('AddRmsNorm') or base.startswith('BatchMatMul'):
        return True
    return False


def collect_ownership(config: dict):
    """Categorize every referenced op index into model / runtime / excluded / unmapped.

    Returns dict:
      {
        'model':    {idx: [owner,...]},
        'runtime':  {idx: [owner,...]},
        'excluded': {idx: reason_code},
        'unmapped': {idx: reason_or_None},
        'per_owner': {idx: [all owner labels across categories]},   # for duplicate detection
      }
    Model ops = trace_instances + structures leaves + stages leaves.
    Runtime ops = runtime_auxiliary leaves.
    Excluded ops = excluded_profiler_ops.
    Unmapped ops = unmapped_ops.
    """
    model, runtime, excluded, unmapped = {}, {}, {}, {}
    per_owner = {}

    def add(bucket, idx, owner):
        bucket.setdefault(idx, [])
        if owner not in bucket[idx]:
            bucket[idx].append(owner)
        per_owner.setdefault(idx, []).append(owner)

    for inst in config.get('trace_instances', []) or []:
        label = f"trace_instance:{inst.get('instance_id', '?')}"
        for idx in instance_op_indices(inst):
            add(model, idx, label)

    def walk(node, path, bucket):
        if not isinstance(node, dict):
            return
        for idx in node.get('op_indices', []) or []:
            add(bucket, idx, path)
        for child in node.get('children', []) or []:
            walk(child, f"{path}/{child.get('name', '?')}", bucket)

    for sname, s in (config.get('stages') or {}).items():
        walk(s, f"stages/{sname}", model)
    # NOTE: `structures` are representative report templates that re-describe the ops of
    # ONE representative trace instance. They are intentionally NOT counted here, else they
    # would double-count against their trace_instances. Their internal consistency (subset
    # of the representative instance, disjoint children) is checked by the sub-layer
    # consistency validator (check_sublayers.py), not by coverage.
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk(aux, f"runtime_auxiliary[{i}]", runtime)

    for e in config.get('excluded_profiler_ops', []) or []:
        rc = e.get('reason_code', '?')
        for idx in e.get('op_indices', []) or []:
            excluded[idx] = rc
            per_owner.setdefault(idx, []).append(f"excluded:{rc}")

    for u in config.get('unmapped_ops', []) or []:
        for idx in u.get('op_indices', []) or []:
            unmapped[idx] = u.get('reason')
            per_owner.setdefault(idx, []).append("unmapped")

    return {
        'model': model, 'runtime': runtime, 'excluded': excluded,
        'unmapped': unmapped, 'per_owner': per_owner,
    }


def collect_trace_op_multiset(config: dict):
    """Back-compat: exact union across model+runtime+excluded+unmapped.

    Returns (all_indices_list_with_repeats, per_owner). Prefer collect_ownership() for
    the four-way category breakdown.
    """
    own = collect_ownership(config)
    per_owner = own['per_owner']
    all_with_repeats = []
    for idx, owners in per_owner.items():
        for _ in owners:
            all_with_repeats.append(idx)
    return all_with_repeats, per_owner


# ---------------------------------------------------------------------------
# raw_ops helpers
# ---------------------------------------------------------------------------

def expand_raw_op_indices(raw_ops: dict) -> set:
    """Full set of op indices present in a raw_ops.json (handles compact repeat folding)."""
    indices = set()
    for op in raw_ops.get('operators', []) or []:
        if op.get('repeat'):
            first = op.get('first_index')
            count = op.get('count', 0)
            if first is not None:
                for k in range(count):
                    indices.add(first + k)
        else:
            idx = op.get('index')
            if idx is not None:
                indices.add(idx)
    return indices


def raw_op_kind_by_index(raw_ops: dict) -> dict:
    out = {}
    for op in raw_ops.get('operators', []) or []:
        if op.get('repeat'):
            first = op.get('first_index')
            count = op.get('count', 0)
            kind = op.get('normalized_name', '')
            if first is not None:
                for k in range(count):
                    out[first + k] = kind
        else:
            idx = op.get('index')
            if idx is not None:
                out[idx] = op.get('normalized_name', op.get('type', ''))
    return out


# ---------------------------------------------------------------------------
# source_ref
# ---------------------------------------------------------------------------

SOURCE_REF_RE = re.compile(r'^(?P<file>.+):(?P<start>\d+)(?:-(?P<end>\d+))?$')


def parse_source_ref(ref: str):
    """Return (file, start, end) or None if malformed."""
    if not isinstance(ref, str):
        return None
    m = SOURCE_REF_RE.match(ref.strip())
    if not m:
        return None
    start = int(m.group('start'))
    end = int(m.group('end')) if m.group('end') else start
    return m.group('file'), start, end


def validate_source_ref(ref: str, base_dirs):
    """
    Return (ok, reason). Checks format, file existence (searching base_dirs),
    and that line numbers are within the file.
    base_dirs: list of directories to resolve the file path against.
    """
    parsed = parse_source_ref(ref)
    if not parsed:
        return False, f"malformed source_ref: {ref!r} (expected file.py:line or file.py:start-end)"
    fname, start, end = parsed
    if end < start:
        return False, f"source_ref {ref!r}: end line {end} < start line {start}"
    candidates = []
    p = Path(fname)
    if p.is_absolute():
        candidates.append(p)
    else:
        for base in base_dirs:
            candidates.append(Path(base) / fname)
            # also allow matching just the basename anywhere under base
    found = None
    for c in candidates:
        if c.exists():
            found = c
            break
    if found is None:
        # try basename search under base_dirs (one level of flexibility)
        for base in base_dirs:
            for cand in Path(base).rglob(p.name):
                found = cand
                break
            if found:
                break
    if found is None:
        return False, f"source_ref {ref!r}: file not found under {list(map(str, base_dirs))}"
    try:
        with open(found, 'r', encoding='utf-8', errors='replace') as fh:
            line_count = sum(1 for _ in fh)
    except OSError as e:
        return False, f"source_ref {ref!r}: cannot read {found}: {e}"
    if start < 1 or end > line_count:
        return False, f"source_ref {ref!r}: line range {start}-{end} out of file bounds (1-{line_count})"
    return True, None


# ---------------------------------------------------------------------------
# tiny draft-07 subset validator (avoids external dependency)
# ---------------------------------------------------------------------------

class SchemaError(Exception):
    pass


def load_schema(schema_path):
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _resolve_ref(root_schema, ref):
    if not ref.startswith('#/'):
        raise SchemaError(f"only local refs supported: {ref}")
    node = root_schema
    for part in ref[2:].split('/'):
        node = node[part]
    return node


def validate_json_schema(instance, schema, root_schema=None, path='$'):
    """
    Minimal JSON Schema (draft-07 subset) validator. Supports:
    type, required, properties, additionalProperties(bool), items, enum, const,
    oneOf, anyOf, allOf, if/then/else, minimum, minItems, maxItems, pattern,
    $ref, definitions.
    Returns list of error strings (empty => valid).
    """
    if root_schema is None:
        root_schema = schema
    errors = []

    if '$ref' in schema:
        schema = _resolve_ref(root_schema, schema['$ref'])

    if 'const' in schema:
        if instance != schema['const']:
            errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
        return errors

    if 'enum' in schema:
        if instance not in schema['enum']:
            errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")
        return errors

    # `oneOf`/`anyOf` are combined WITH the rest of the schema, not instead of it. Returning
    # here used to skip every sibling keyword, so an object carrying `anyOf` silently lost its
    # `required`, `additionalProperties` and `minItems` checks -- `branch` uses exactly that
    # combination to mean "strict, and needs one of source_ref/code_ref", and was therefore
    # accepting misspelled fields and missing required ones.
    if 'oneOf' in schema:
        matches = sum(1 for sub in schema['oneOf']
                      if not validate_json_schema(instance, sub, root_schema, path))
        if matches != 1:
            errors.append(f"{path}: matched {matches} of oneOf (expected exactly 1)")

    if 'anyOf' in schema:
        if not any(not validate_json_schema(instance, sub, root_schema, path)
                   for sub in schema['anyOf']):
            errors.append(f"{path}: did not match anyOf")

    for sub in schema.get('allOf', []):
        errors.extend(validate_json_schema(instance, sub, root_schema, path))

    if 'if' in schema:
        condition_matches = not validate_json_schema(
            instance, schema['if'], root_schema, path)
        branch = schema.get('then') if condition_matches else schema.get('else')
        if branch is not None:
            errors.extend(validate_json_schema(instance, branch, root_schema, path))

    t = schema.get('type')
    if t:
        types = t if isinstance(t, list) else [t]
        if not _type_ok(instance, types):
            errors.append(f"{path}: expected type {t}, got {type(instance).__name__}")
            return errors

    if isinstance(instance, dict):
        for req in schema.get('required', []):
            if req not in instance:
                errors.append(f"{path}: missing required property {req!r}")
        props = schema.get('properties', {})
        for key, val in instance.items():
            if key in props:
                errors.extend(validate_json_schema(val, props[key], root_schema, f"{path}.{key}"))
            else:
                addl = schema.get('additionalProperties', True)
                if addl is False:
                    errors.append(f"{path}: additional property {key!r} not allowed")
                elif isinstance(addl, dict):
                    errors.extend(validate_json_schema(val, addl, root_schema, f"{path}.{key}"))

    if isinstance(instance, list):
        items = schema.get('items')
        if isinstance(items, dict):
            for i, el in enumerate(instance):
                errors.extend(validate_json_schema(el, items, root_schema, f"{path}[{i}]"))
        if 'minItems' in schema and len(instance) < schema['minItems']:
            errors.append(f"{path}: expected >= {schema['minItems']} items, got {len(instance)}")
        if 'maxItems' in schema and len(instance) > schema['maxItems']:
            errors.append(f"{path}: expected <= {schema['maxItems']} items, got {len(instance)}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if 'minimum' in schema and instance < schema['minimum']:
            errors.append(f"{path}: {instance} < minimum {schema['minimum']}")

    if isinstance(instance, str) and 'pattern' in schema:
        if not re.search(schema['pattern'], instance):
            errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']}")

    return errors


def _type_ok(instance, types):
    for t in types:
        if t == 'object' and isinstance(instance, dict):
            return True
        if t == 'array' and isinstance(instance, list):
            return True
        if t == 'string' and isinstance(instance, str):
            return True
        if t == 'integer' and isinstance(instance, int) and not isinstance(instance, bool):
            return True
        if t == 'number' and isinstance(instance, (int, float)) and not isinstance(instance, bool):
            return True
        if t == 'boolean' and isinstance(instance, bool):
            return True
        if t == 'null' and instance is None:
            return True
    return False


SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS_DIR.parent
SCHEMAS_DIR = SKILL_ROOT / 'schemas'
