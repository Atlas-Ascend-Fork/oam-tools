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
Exact op coverage check (schema v2).

Replaces the old "representative op count x layer count" extrapolation with an
EXACT union computed from every trace_instance's op_indices/op_range plus any
leaf op_indices in structures/stages/runtime_auxiliary and explicitly classified
unmapped_ops.

Reports (never lets missing and duplicate cancel out):
  C1 missing:    raw_ops indices not covered by any owner            -> error
  C2 duplicate:  op index owned by more than one instance/node       -> error
  C3 out-of-range: covered index not present in raw_ops              -> error
  C4 unmapped-without-reason: unmapped_ops entry missing reason      -> error
  C5 optional shape_semantic missing on a registered kernel          -> info

Legacy v1 configs: emits a single info issue and computes best-effort union of
leaf op_indices (no extrapolation, no pass/fail promotion). Use migrate_config.py
to convert to v2 for real coverage accounting.

--json prints one JSON object. Exit code nonzero if any error.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402

# The historical name is retained for compatibility. In coverage, this set only
# selects operators for the informational C5 hint; it does not require annotations.
SHAPE_SEMANTIC_ALWAYS_REQUIRED = {
    'MatMul', 'MatMulV2', 'QuantBatchMatmulV3', 'GroupedMatmul', 'GemmEx', 'BatchMatMul',
    'FlashAttentionScore', 'FusedInferAttentionScore', 'KvQuantSparseFlashAttention',
    'HcomAllGather', 'HcomReduceScatter', 'HcomAllToAll', 'hcom_allReduce', 'HcomAllReduce',
    'RmsNorm', 'LayerNormV3', 'InplaceAddRmsNorm', 'AddRmsNormDynamicQuant',
    'MlaPrologV3', 'DequantSwigluQuant', 'LightningIndexerQuant', 'MoeGatingTopKHash',
    'RotaryMul', 'GatherV2', 'GatherV3',
    'MoeDistributeDispatchV2', 'MoeDistributeCombineV2',
}


def is_shape_always_required(name: str) -> bool:
    """Select operators for the C5 hint, not mandatory coverage annotations."""
    return name in SHAPE_SEMANTIC_ALWAYS_REQUIRED or name.startswith('AddRmsNorm')


class Issue(dict):
    def __init__(self, code, severity, path, message):
        super().__init__(id=code, severity=severity, node_path=path, message=message)


def collect_registered_kernels(config: dict):
    """Return {op_index: {name, has_shape_semantic, path}} across structures/stages/aux."""
    out = {}

    def walk(node, path):
        if not isinstance(node, dict):
            return
        for ks in node.get('kernels', []) or []:
            kn = (ks.get('name', '') or '').split('/')[-1]
            idx = ks.get('index')
            if idx is not None:
                out[idx] = {'name': kn, 'has_shape_semantic': bool(ks.get('shape_semantic')), 'path': path}
        for child in node.get('children', []) or []:
            walk(child, f"{path}/{child.get('name', '?')}")

    for name, sect in (config.get('structures') or {}).items():
        walk(sect, f"structures/{name}")
    for name, sect in (config.get('stages') or {}).items():
        walk(sect, f"stages/{name}")
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk(aux, f"runtime_auxiliary[{i}]")
    return out


def check_coverage_v2(config: dict, raw_ops: dict, allow_unmapped: bool = False):
    issues = []
    raw_indices = bc.expand_raw_op_indices(raw_ops)
    n_ops = len(raw_indices)
    kind_by_idx = bc.raw_op_kind_by_index(raw_ops)

    own = bc.collect_ownership(config)
    model, runtime, excluded, unmapped = own['model'], own['runtime'], own['excluded'], own['unmapped']
    per_owner = own['per_owner']
    covered = set(per_owner.keys())

    # C1 missing (any raw op with no ownership at all -> always an error).
    #
    # This is THE direction the trace is allowed to falsify — see
    # bc.TRACE_CAN_ONLY_FALSIFY_COVERAGE. The op demonstrably executed and the breakdown
    # accounts for it nowhere, so the breakdown is wrong and no appeal to the source
    # excuses it. Errors here are unconditional: not softened by manifest confidence, not
    # by capture tier, not by an explanatory note.
    #
    # The mirror direction is deliberately absent from this file: a structure the source
    # declares but the trace never witnessed (an unexecuted branch, an off-rank expert
    # shard, a fused-away residual) raises nothing here. Once `missing` is empty, coverage
    # is complete and the decomposition is correct by default — the trace has no standing
    # to withhold a pass for scalars it cannot arbitrate.
    missing = sorted(raw_indices - covered)
    for idx in missing:
        issues.append(Issue('C1', 'error', f'op_index={idx}',
                            f'op_index={idx} ({kind_by_idx.get(idx, "?")}) 无任何归属 '
                            f'(model/runtime/excluded/unmapped 均未包含)'))

    # C2 duplicate (op owned more than once, across any categories)
    duplicates = sorted([idx for idx, owners in per_owner.items() if len(owners) > 1])
    for idx in duplicates:
        issues.append(Issue('C2', 'error', f'op_index={idx}',
                            f'op_index={idx} 被多个 owner 覆盖: {per_owner[idx]}'))

    # C3 out-of-range. Not the forbidden "source has it, trace does not" direction: the
    # config is claiming a concrete op_index that does not exist in this capture's raw_ops,
    # which is a dangling index, not an unexecuted path. Unexecuted paths are expressed by
    # owning zero kernels, never by pointing at an index outside the array.
    out_of_range = sorted(covered - raw_indices)
    for idx in out_of_range:
        issues.append(Issue('C3', 'error', f'op_index={idx}',
                            f'op_index={idx} 出现在配置中但不存在于 raw_ops (owners={per_owner[idx]})'))

    # C4 UNMAPPED is a blocker in strict mode (free-text reason does NOT cover an op).
    #    --allow-unmapped downgrades to warning but the run becomes EXPLORATORY, never passed.
    if unmapped:
        sev = 'warning' if allow_unmapped else 'error'
        issues.append(Issue('C4', sev, 'unmapped_ops',
                            f'{len(unmapped)} 个 op 归属未知（unmapped）：{sorted(unmapped)[:30]}'
                            f'{"..." if len(unmapped) > 30 else ""}。'
                            f'严格模式要求 unmapped=0（填 reason 不算完成映射）。'))

    # C6 main-compute kernel illegally excluded
    for idx, rc in excluded.items():
        kind = kind_by_idx.get(idx, '')
        if bc.is_main_compute_kind(kind):
            issues.append(Issue('C6', 'error', f'op_index={idx}',
                                f'主计算算子 {kind} (op {idx}) 不允许放入 excluded_profiler_ops '
                                f'(reason_code={rc})'))

    # C7 excluded entry must carry evidence (schema already requires; double-guard)
    for e in config.get('excluded_profiler_ops', []) or []:
        if not e.get('evidence'):
            issues.append(Issue('C7', 'error', 'excluded_profiler_ops',
                                f'excluded 条目 {e.get("op_indices")} 缺少 evidence'))

    # C5 is diagnostic only: optional annotations do not decide exact coverage.
    # Explicit shape validation remains available through --with-shapes/validate_shapes.
    for idx, info in collect_registered_kernels(config).items():
        if is_shape_always_required(info['name']) and not info['has_shape_semantic']:
            issues.append(Issue('C5', 'info', f'{info["path"]}/kernels[index={idx}]',
                                f'{info["name"]} 未提供可选 shape_semantic 注解（不影响覆盖校验）'))

    model_c = len(model)
    runtime_c = len(runtime)
    excluded_c = len(excluded)
    unmapped_c = len(unmapped)
    accounted = len((set(model) | set(runtime) | set(excluded)) & raw_indices)
    summary = {
        'total_ops': n_ops,
        'model_mapped': model_c,
        'runtime_mapped': runtime_c,
        'excluded': excluded_c,
        'unmapped': unmapped_c,
        'duplicate': len(duplicates),
        'out_of_range': len(out_of_range),
        'missing': len(missing),
        'exact_coverage_pct': round(100 * accounted / max(n_ops, 1), 2),
        'missing_sample': missing[:20],
        'duplicate_sample': duplicates[:20],
        'out_of_range_sample': out_of_range[:20],
        'unmapped_sample': sorted(unmapped)[:20],
    }
    return issues, summary


def check_coverage_legacy(config: dict, raw_ops: dict):
    """Best-effort union for v1 — no extrapolation, flagged as unverified."""
    raw_indices = bc.expand_raw_op_indices(raw_ops)
    n_ops = len(raw_indices)
    covered = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        for idx in node.get('op_indices', []) or []:
            covered.add(idx)
        for child in node.get('children', []) or []:
            walk(child)

    for s in (config.get('stages') or {}).values():
        walk(s)
    for ls in (config.get('layer_structure') or {}).values():
        walk(ls)
    for aux in (config.get('runtime_auxiliary') or []):
        walk(aux)

    issues = [Issue('C0', 'info', '<global>',
                    'legacy v1 config: exact per-instance coverage 不可用（layer_structure 只含代表层）。'
                    '请用 migrate_config.py 转为 v2 后再做精确覆盖核算。')]
    summary = {
        'total_ops': n_ops,
        'covered_ops': len(covered & raw_indices),
        'schema': 'legacy_v1',
    }
    return issues, summary


def run(config_path, raw_ops_path, allow_unmapped=False):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open(raw_ops_path, 'r', encoding='utf-8') as f:
        raw_ops = json.load(f)

    version = bc.detect_schema_version(config)
    if version == 2:
        issues, summary = check_coverage_v2(config, raw_ops, allow_unmapped=allow_unmapped)
    else:
        issues, summary = check_coverage_legacy(config, raw_ops)
    return issues, summary, version


def main():
    parser = argparse.ArgumentParser(description='Exact op coverage check (schema v2)')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-r', '--raw-ops', dest='raw_ops', required=True)
    parser.add_argument('--allow-unmapped', action='store_true',
                        help='探索模式：unmapped 降级为 warning（结果非 passed，仅 exploratory）')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    for p in (args.config, args.raw_ops):
        if not os.path.exists(p):
            sys.stderr.write(f'错误: 文件不存在: {p}\n')
            sys.exit(2)

    issues, summary, version = run(args.config, args.raw_ops, allow_unmapped=args.allow_unmapped)
    errors = [i for i in issues if i['severity'] == 'error']

    if args.json:
        print(json.dumps({
            'script': 'check_op_coverage.py',
            'config': args.config,
            'raw_ops': args.raw_ops,
            'schema_version': version,
            'error_count': len(errors),
            'summary': summary,
            'issues': issues,
        }, indent=2, ensure_ascii=False))
    else:
        for it in issues:
            print(f'[{it["severity"].upper()}] {it["id"]} @ {it["node_path"]}: {it["message"]}')
        print(f'\n汇总: {json.dumps(summary, ensure_ascii=False)}')
        print(f'errors={len(errors)}')

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
