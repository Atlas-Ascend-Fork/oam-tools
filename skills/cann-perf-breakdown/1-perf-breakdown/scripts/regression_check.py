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
Step 3 / P8: 与 baseline 做结构等价性回归 (L1–L8)。

L1: top-level keys 集合相等
L2: layer_types 集合 + layer_indices 列表相等
L3: stages keys 与 stage_indices 集合相等
L4: runtime_auxiliary 名字集合相等
L5: 每个 layer_type 的叶节点路径集合 Jaccard ≥ 0.95
L6: 每个叶节点的 op_indices 集合 Jaccard ≥ 0.90
L7: op 总覆盖相等；v2 使用 collect_ownership()['per_owner']，包括每次实际调用的
    trace_instances、stages、runtime_auxiliary、excluded_profiler_ops、unmapped_ops，
    不计 structures 代表模板
L8: 11 类算子的 shape_semantic 字段存在性 100%
"""
import argparse
import json
import os
import sys

SHAPE_SEMANTIC_ALWAYS_REQUIRED = {
    'MatMul', 'MatMulV2', 'QuantBatchMatmulV3', 'GroupedMatmul', 'GemmEx', 'BatchMatMul',
    'FlashAttentionScore', 'FusedInferAttentionScore', 'KvQuantSparseFlashAttention',
    'HcomAllGather', 'HcomReduceScatter', 'HcomAllToAll', 'hcom_allReduce', 'HcomAllReduce',
    'RmsNorm', 'LayerNormV3', 'InplaceAddRmsNorm', 'AddRmsNormDynamicQuant',
    'MlaPrologV3', 'DequantSwigluQuant', 'LightningIndexerQuant', 'MoeGatingTopKHash',
    'RotaryMul',
    'GatherV2', 'GatherV3',
    'MoeDistributeDispatchV2', 'MoeDistributeCombineV2',
}


def is_shape_required(name: str) -> bool:
    return name in SHAPE_SEMANTIC_ALWAYS_REQUIRED or name.startswith('AddRmsNorm')


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(len(a | b), 1)


def collect_leaves(layer_struct):
    """返回 {leaf_path: set(op_indices)}"""
    out = {}

    def walk(node, path):
        if not isinstance(node, dict):
            return
        if 'op_indices' in node and node.get('op_indices') is not None:
            out[path] = set(node['op_indices'])
        for child in node.get('children', []) or []:
            cname = child.get('name', '?')
            walk(child, f'{path}/{cname}')

    walk(layer_struct, layer_struct.get('name', 'root'))
    return out


def collect_all_op_indices(config):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import breakdown_common as bc

    if bc.detect_schema_version(config) == 2:
        # Templates only describe representative calls; ownership includes every
        # observed invocation and the existing runtime/excluded/unmapped categories.
        return set(bc.collect_ownership(config)['per_owner'])
    out = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        for idx in node.get('op_indices', []) or []:
            out.add(idx)
        for child in node.get('children', []) or []:
            walk(child)

    for s in (config.get('stages') or {}).values():
        walk(s)
    for ls in (config.get('layer_structure') or {}).values():
        walk(ls)
    for aux in (config.get('runtime_auxiliary') or []):
        walk(aux)
    return out


def collect_kernels_with_shape(config):
    """返回 {(path, op_index): (kernel_name, has_shape_semantic)}"""
    out = {}

    def walk(node, path):
        if not isinstance(node, dict):
            return
        for ks in node.get('kernels', []) or []:
            kn = ks.get('name', '') or ''
            kn = kn.split('/')[-1] if '/' in kn else kn
            idx = ks.get('index')
            if idx is not None:
                out[(path, idx)] = (kn, bool(ks.get('shape_semantic')))
        for child in node.get('children', []) or []:
            walk(child, f'{path}/{child.get("name", "?")}')

    for sname, s in (config.get('stages') or {}).items():
        walk(s, f'stages/{sname}')
    for ltype, ls in (config.get('layer_structure') or {}).items():
        walk(ls, f'layer_structure/{ltype}')
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk(aux, f'runtime_auxiliary[{i}]')
    return out


def check_regression(baseline, new, l5_threshold=0.95, l6_threshold=0.90):
    findings = []

    # L1
    bl_keys = set(baseline.keys())
    new_keys = set(new.keys())
    if bl_keys == new_keys:
        findings.append({'id': 'L1', 'pass': True, 'detail': f'top-level keys match: {sorted(bl_keys)}'})
    else:
        findings.append({'id': 'L1', 'pass': False,
                         'detail': f'baseline only: {sorted(bl_keys - new_keys)}, '
                                   f'new only: {sorted(new_keys - bl_keys)}'})

    # L2
    bl_lt = baseline.get('layer_types') or {}
    new_lt = new.get('layer_types') or {}
    bl_set = set(bl_lt.keys())
    new_set = set(new_lt.keys())
    l2_pass = (bl_set == new_set) and all(
        sorted(bl_lt[k].get('layer_indices', [])) == sorted(new_lt[k].get('layer_indices', []))
        for k in bl_set
    )
    findings.append({
        'id': 'L2',
        'pass': l2_pass,
        'detail': f'baseline layer_types={sorted(bl_set)}, new={sorted(new_set)}',
    })

    # L3
    bl_stages = baseline.get('stages') or {}
    new_stages = new.get('stages') or {}
    bl_st = set(bl_stages)
    new_st = set(new_stages)
    stage_mismatches = []
    for name in sorted(bl_st & new_st):
        # Match the single-instance default used by compute_metrics/report.
        bl_indices = set(bl_stages[name].get('stage_indices') or [0])
        new_indices = set(new_stages[name].get('stage_indices') or [0])
        if bl_indices != new_indices:
            stage_mismatches.append({'stage': name,
                                     'baseline': sorted(bl_indices),
                                     'new': sorted(new_indices)})
    findings.append({
        'id': 'L3',
        'pass': bl_st == new_st and not stage_mismatches,
        'detail': {'baseline_stages': sorted(bl_st), 'new_stages': sorted(new_st),
                   'stage_indices_mismatches': stage_mismatches},
    })

    # L4
    def names(aux_list):
        return {a.get('name') for a in (aux_list or []) if isinstance(a, dict) and a.get('name')}

    bl_aux = names(baseline.get('runtime_auxiliary'))
    new_aux = names(new.get('runtime_auxiliary'))
    findings.append({
        'id': 'L4',
        'pass': bl_aux == new_aux,
        'detail': f'baseline aux={sorted(bl_aux)}, new={sorted(new_aux)}',
    })

    # L5: per-layer_type leaf path Jaccard
    l5_results = []
    for k in bl_set & new_set:
        bl_paths = set(collect_leaves(bl_lt and (baseline['layer_structure'].get(k, {}))).keys())
        new_paths = set(collect_leaves(new and (new['layer_structure'].get(k, {}))).keys())
        j = jaccard(bl_paths, new_paths)
        l5_results.append({
            'layer_type': k,
            'jaccard': round(j, 3),
            'baseline_only': sorted(list(bl_paths - new_paths))[:10],
            'new_only': sorted(list(new_paths - bl_paths))[:10],
        })
    l5_pass = all(r['jaccard'] >= l5_threshold for r in l5_results) if l5_results else True
    findings.append({'id': 'L5', 'pass': l5_pass, 'threshold': l5_threshold, 'detail': l5_results})

    # L6: per-leaf op_indices Jaccard
    l6_results = []
    for k in bl_set & new_set:
        bl_leaves = collect_leaves(baseline['layer_structure'].get(k, {}))
        new_leaves = collect_leaves(new['layer_structure'].get(k, {}))
        common = set(bl_leaves) & set(new_leaves)
        for path in common:
            j = jaccard(bl_leaves[path], new_leaves[path])
            if j < l6_threshold:
                l6_results.append({
                    'layer_type': k,
                    'leaf': path,
                    'jaccard': round(j, 3),
                    'baseline_only': sorted(list(bl_leaves[path] - new_leaves[path]))[:5],
                    'new_only': sorted(list(new_leaves[path] - bl_leaves[path]))[:5],
                })
    findings.append({
        'id': 'L6',
        'pass': not l6_results,
        'threshold': l6_threshold,
        'mismatches': l6_results[:30],
        'mismatch_count': len(l6_results),
    })

    # L7: total op coverage
    bl_ops = collect_all_op_indices(baseline)
    new_ops = collect_all_op_indices(new)
    findings.append({
        'id': 'L7',
        'pass': bl_ops == new_ops,
        'detail': {
            'baseline_count': len(bl_ops),
            'new_count': len(new_ops),
            'missing_in_new': sorted(list(bl_ops - new_ops))[:20],
            'extra_in_new': sorted(list(new_ops - bl_ops))[:20],
        },
    })

    # L8: shape_semantic 字段存在性
    new_kernels = collect_kernels_with_shape(new)
    missing = [(p, idx, kn) for (p, idx), (kn, ok) in new_kernels.items()
               if is_shape_required(kn) and not ok]
    findings.append({
        'id': 'L8',
        'pass': not missing,
        'missing_count': len(missing),
        'missing_examples': missing[:10],
    })

    return findings


def check_architecture_regression(config, manifest):
    """Semantic architecture comparison of a v2 config against an extracted manifest.

    Blocking (hard) findings when the config's declared architecture contradicts the
    statically-extracted ground truth.
    """
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import breakdown_common as _bc
    findings = []
    arch = config.get('architecture') or {}

    # A layer-count disagreement only blocks when the manifest is actually credible.
    # With an unreachable checkpoint config the manifest number is a Python default-arg
    # fallback describing the model family, so blocking here would reject a config that
    # correctly matched the trace. `severity` is carried on the finding so every consumer
    # honours the same decision instead of hardcoding MA1 as always-hard.
    layer_confidence = _bc.manifest_fact_confidence(manifest)
    findings.append({
        'id': 'MA1',
        'pass': arch.get('num_main_layers') == manifest.get('num_main_layers'),
        # `info` when the manifest number is a low-confidence fallback, matching A1: a formal
        # pass is exactly `passed`, and "the inputs cannot confirm this" must not be the thing
        # that blocks. The unconfirmed count is charged in the score instead (§5.7.1).
        'severity': 'info' if layer_confidence == 'low' else 'error',
        'detail': {'config': arch.get('num_main_layers'),
                   'manifest': manifest.get('num_main_layers'),
                   'manifest_confidence': layer_confidence},
    })

    m_class = {}
    for g in manifest.get('layer_groups', []):
        for idx in _bc.expand_layer_group_indices(g):
            m_class[idx] = g.get('classification')
    c_class = {}
    for g in arch.get('layer_groups', []):
        for idx in _bc.expand_layer_group_indices(g):
            c_class[idx] = g.get('classification')
    mismatched = sorted([i for i in set(m_class) & set(c_class)
                         if m_class[i] != c_class[i]])
    findings.append({'id': 'MA2', 'pass': not mismatched,
                     'detail': {'mismatched_layers': mismatched[:20]}})

    m_pred = sum(p.get('learned_module_count', 0) for p in manifest.get('prediction_modules', [])
                 if isinstance(p.get('learned_module_count'), int))
    c_pred = sum(p.get('learned_module_count', 0) for p in arch.get('prediction_modules', [])
                 if isinstance(p.get('learned_module_count'), int))
    # Same reasoning as MA1, plus: a prediction module with an unresolved source_ref was
    # inferred from a config key rather than found in the modeling source, so it cannot
    # outrank a config that reports none.
    unproven_mtp = any(p.get('source_ref', 'unknown') == 'unknown'
                       for p in manifest.get('prediction_modules') or [])
    mtp_blocking = layer_confidence != 'low' and not unproven_mtp
    findings.append({'id': 'MA3', 'pass': m_pred == c_pred,
                     'severity': 'error' if mtp_blocking else 'warning',
                     'detail': {'config_learned_mtp': c_pred, 'manifest_learned_mtp': m_pred,
                                'manifest_mtp_source_unresolved': unproven_mtp}})
    return findings


def main():
    parser = argparse.ArgumentParser(description='Regression check L1–L8 vs baseline (+ MA1–MA3 vs manifest)')
    parser.add_argument('--baseline', help='baseline analysis_config.json')
    parser.add_argument('--new', required=True, help='new analysis_config.json')
    parser.add_argument('--manifest', help='model_manifest.json，做语义架构回归(MA1-MA3)')
    parser.add_argument('--strict-soft', action='store_true',
                        help='把 soft fail（L5/L6/L8）也视为阻断（CI 用）')
    parser.add_argument('--mode', default='A', choices=['A', 'B'],
                        help='Mode B 跳过 L6/L7/L8（无 op_indices/kernels）')
    parser.add_argument('--report', help='输出 Markdown 报告路径')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出 stdout')
    parser.add_argument('--l5', type=float, default=0.95, help='L5 Jaccard 阈值')
    parser.add_argument('--l6', type=float, default=0.90, help='L6 Jaccard 阈值')
    args = parser.parse_args()

    if not args.baseline and not args.manifest:
        sys.stderr.write('错误: 需要 --baseline 或 --manifest 之一\n')
        sys.exit(2)
    for p in (args.baseline, args.new, args.manifest):
        if p and not os.path.exists(p):
            sys.stderr.write(f'错误: 文件不存在: {p}\n')
            sys.exit(1)

    with open(args.new, 'r', encoding='utf-8') as f:
        new = json.load(f)

    findings = []
    if args.baseline:
        with open(args.baseline, 'r', encoding='utf-8') as f:
            baseline = json.load(f)
        findings = check_regression(baseline, new, args.l5, args.l6)
        if args.mode == 'B':
            findings = [f for f in findings if f['id'] not in ('L6', 'L7', 'L8')]

    if args.manifest:
        with open(args.manifest, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        findings.extend(check_architecture_regression(new, manifest))

    hard_ids = {'L1', 'L2', 'L3', 'L4', 'L7', 'MA1', 'MA2', 'MA3'}
    soft_ids = {'L5', 'L6', 'L8'}
    if args.strict_soft:
        hard_ids |= soft_ids
        soft_ids = set()
    def _is_hard(f):
        """Honour a finding's own severity when it carries one (see MA1/MA3)."""
        sev = f.get('severity')
        if sev:
            return sev == 'error' or (args.strict_soft and f['id'] in soft_ids)
        return f['id'] in hard_ids

    hard_fails = [f for f in findings if not f['pass'] and _is_hard(f)]
    soft_fails = [f for f in findings if not f['pass'] and not _is_hard(f)
                  and f['id'] in soft_ids | hard_ids]

    if args.json:
        print(json.dumps({
            'script': 'regression_check.py',
            'baseline': args.baseline,
            'new': args.new,
            'mode': args.mode,
            'hard_fails': len(hard_fails),
            'soft_fails': len(soft_fails),
            'findings': findings,
        }, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            mark = '✓' if f['pass'] else '✗'
            print(f'[{mark}] {f["id"]}')
            if not f['pass']:
                print(f'    detail: {json.dumps(f.get("detail", f), ensure_ascii=False)[:500]}')
        print(f'\n汇总: hard_fails={len(hard_fails)}, soft_fails={len(soft_fails)}')

    if args.report:
        lines = [f'# Regression Check: {os.path.basename(args.new)} vs baseline\n']
        lines.append(f'- Baseline: `{args.baseline}`')
        lines.append(f'- New:      `{args.new}`')
        lines.append(f'- Mode:     {args.mode}\n')
        lines.append('| 项 | 通过 | 详情 |')
        lines.append('|---|---|---|')
        for f in findings:
            mark = '✓' if f['pass'] else '✗'
            detail = json.dumps(f.get('detail', f), ensure_ascii=False)[:200]
            lines.append(f'| {f["id"]} | {mark} | `{detail}` |')
        with open(args.report, 'w', encoding='utf-8') as fp:
            fp.write('\n'.join(lines) + '\n')
        print(f'\nReport 已保存到: {args.report}')

    sys.exit(1 if hard_fails else 0)


if __name__ == '__main__':
    main()
