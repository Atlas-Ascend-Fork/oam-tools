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
run_validation.py — unified validation entrypoint.

Runs structure, architecture, dataflow, coverage (and optional regression) checks and
emits ONE valid JSON document (schemas/validation_report.schema.json). Never
concatenates multiple JSON objects.

A formal pass is EXACTLY `passed`. `--allow-warnings` still exists for exploratory
triage -- it produces `passed_with_warnings`, which report generation and scoring
reject; it is not a way to ship a config with open warnings.

Shape validation is not part of the formal contract (see --with-shapes): a missing
`shape_semantic` annotation says nothing about whether the decomposition is correct.
The dataflow check took its place as the thing that can actually be wrong.

Exit codes:
  0  -> passed, or a non-formal completion (passed_with_warnings / exploratory)
  1  -> failed (errors, or warnings without --allow-warnings)
  2  -> a sub-check raised an unexpected exception / bad inputs
"""
import argparse
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import breakdown_common as bc  # noqa: E402
import check_structure  # noqa: E402
import check_op_coverage  # noqa: E402
import check_sublayers  # noqa: E402
import validate_architecture  # noqa: E402
import validate_shapes  # noqa: E402
import check_graph_consistency  # noqa: E402
import check_manifest_trace  # noqa: E402
import check_dataflow  # noqa: E402
import check_moe_parallelism  # noqa: E402
import extract_dataflow  # noqa: E402


def _run(check_name, fn):
    """Run a sub-check callable returning (issues, extra). Catch exceptions -> error check."""
    try:
        issues, extra = fn()
        errors = [i for i in issues if i.get('severity') == 'error']
        warnings = [i for i in issues if i.get('severity') == 'warning']
        status = 'passed'
        if errors:
            status = 'failed'
        elif warnings:
            status = 'warning'
        for it in issues:
            it.setdefault('check', check_name)
        return {
            'name': check_name,
            'status': status,
            'error_count': len(errors),
            'warning_count': len(warnings),
            'detail': extra,
        }, issues
    except Exception as e:  # noqa: BLE001 — sub-check must never crash the runner silently
        return {
            'name': check_name,
            'status': 'error',
            'error_count': 1,
            'warning_count': 0,
            'detail': f'{type(e).__name__}: {e}\n{traceback.format_exc()}',
        }, [{'id': 'RUNNER', 'severity': 'error', 'check': check_name,
             'node_path': '<runner>', 'message': f'{check_name} 异常: {e}'}]


#: manifest_trace findings that keep their severity through `_demote_to_info`.
#: The demotion rationale is about *scalars* a single capture cannot arbitrate (a layer
#: count). MT2 is not a scalar: it reports that expert-routing kernels were recorded while
#: the manifest calls every layer dense. A capture cannot be wrong about a kernel it ran,
#: so partial coverage is no excuse for that contradiction.
_TRACE_MISMATCH_NON_DEMOTABLE = {'MT2'}


def _demote_to_info(check, issues):
    """Rewrite one check's issues to `info` and recompute its status.

    Used for `manifest_trace`. Its arithmetic compares a layer count against kernel
    witness counts from one capture, and a capture may legitimately span a single step,
    so a mismatch is evidence to read, never a verdict on the source-derived
    decomposition. Emitting it as a warning made a partial capture fail the formal run.
    The finding stays in the report verbatim; only its severity changes, so nothing is
    hidden — see `--fail-on-trace-mismatch` to restore blocking behaviour.

    Qualitative findings listed in `_TRACE_MISMATCH_NON_DEMOTABLE` are left untouched.
    """
    kept = []
    for issue in issues:
        if issue.get('id') in _TRACE_MISMATCH_NON_DEMOTABLE:
            kept.append(issue)
            continue
        issue['severity'] = 'info'
        issue['demoted_from'] = 'warning'
    errors = [i for i in kept if i.get('severity') == 'error']
    warnings = [i for i in kept if i.get('severity') == 'warning']
    if errors:
        check['status'] = 'failed'
    elif warnings:
        check['status'] = 'warning'
    else:
        check['status'] = 'passed' if issues else check.get('status', 'passed')
    check['error_count'] = len(errors)
    check['warning_count'] = len(warnings)
    check['info_count'] = len(issues) - len(kept)
    detail = check.get('detail')
    if isinstance(detail, dict):
        detail['severity_policy'] = ('trace 为辅助证据：标量类发现仅作 info，不阻断正式流程'
                                     '（--fail-on-trace-mismatch 可恢复阻断）；'
                                     f'定性矛盾 {sorted(_TRACE_MISMATCH_NON_DEMOTABLE)} 不降级')
    return check, issues


def run_all(config_path, raw_ops_path, manifest_path, source_dirs, mode='A',
            include_shapes=False, allow_unmapped=False, baseline_path=None,
            graph_path=None, dataflow_path=None,
            model_sources=(), profile=None, fail_on_trace_mismatch=False):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    version = bc.detect_schema_version(config)
    base_dirs = source_dirs or [os.getcwd()]

    checks = []
    all_issues = []

    # structure
    def _structure():
        if version == 2:
            return check_structure.check_structure_v2(config, base_dirs), {'schema_version': 2}
        return check_structure.check_structure(config), {'schema_version': version}
    c, i = _run('structure', _structure)
    checks.append(c); all_issues.extend(i)

    # architecture (v2 only, meaningful)
    def _arch():
        manifest = None
        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        if version != 2:
            return ([{'id': 'A0', 'severity': 'warning', 'node_path': '<global>',
                      'message': 'legacy v1: architecture 校验跳过（legacy_unverified）'}],
                    {'schema_version': version})
        return validate_architecture.validate(config, manifest, base_dirs), {'manifest': manifest_path}
    c, i = _run('architecture', _arch)
    checks.append(c); all_issues.extend(i)

    # manifest vs trace layer count (needs both; pure arithmetic, no source reading)
    if raw_ops_path and manifest_path and os.path.exists(manifest_path):
        def _manifest_trace():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            with open(raw_ops_path, 'r', encoding='utf-8') as f:
                raw_ops = json.load(f)
            return check_manifest_trace.check_manifest_trace(manifest, raw_ops)
        c, i = _run('manifest_trace', _manifest_trace)
        # The source is the architecture truth; a capture corroborates it and cannot
        # arbitrate it. Keep the finding, drop its blocking power unless asked otherwise.
        if not fail_on_trace_mismatch and c['status'] != 'error':
            c, i = _demote_to_info(c, i)
        checks.append(c); all_issues.extend(i)

    # MoE parallelism from operator shapes. ep_size is arithmetic here, not inference:
    # num_experts (router projection output) / experts_per_rank (MoeComputeExpertTokens
    # output, cross-checked against the GroupedMatmul weight leading dim). Also rejects
    # "absence of kernel X -> conclusion" evidence, which is how EP=1 got asserted on an
    # EP=8 capture: the local-expert path all-reduces instead of using AllToAll, so the
    # missing AllToAll was read as the opposite of what it meant.
    if raw_ops_path:
        def _moe_parallelism():
            with open(raw_ops_path, 'r', encoding='utf-8') as f:
                raw_ops = json.load(f)
            return check_moe_parallelism.check_moe_parallelism(config, raw_ops)
        c, i = _run('moe_parallelism', _moe_parallelism)
        checks.append(c); all_issues.extend(i)

    # coverage (needs raw_ops)
    if raw_ops_path:
        def _coverage():
            with open(raw_ops_path, 'r', encoding='utf-8') as f:
                raw_ops = json.load(f)
            if version == 2:
                issues, summary = check_op_coverage.check_coverage_v2(
                    config, raw_ops, allow_unmapped=allow_unmapped)
            else:
                issues, summary = check_op_coverage.check_coverage_legacy(config, raw_ops)
            return issues, summary
        c, i = _run('coverage', _coverage)
        checks.append(c); all_issues.extend(i)

    # sub-layer template consistency (v2 only)
    if version == 2:
        def _sublayers():
            # raw_ops lets SL6 count compute ops only. Without it, communication jitter in
            # one invocation reads as an architecture difference and demands a template split.
            sub_raw_ops = None
            if raw_ops_path and os.path.exists(raw_ops_path):
                with open(raw_ops_path, 'r', encoding='utf-8') as f:
                    sub_raw_ops = json.load(f)
            return (check_sublayers.check_sublayers(config, sub_raw_ops),
                    {'comm_aware': sub_raw_ops is not None})
        c, i = _run('sublayers', _sublayers)
        checks.append(c); all_issues.extend(i)

    # dataflow: re-derive the graph from source and compare it with what the config claims.
    # `forward()` IS the dataflow graph, so the residual/fork topology is machine-checkable
    # rather than a prose assertion. Runs whenever source is available -- either a prepared
    # dataflow_source.json or model sources to parse inline. With neither, the check is
    # absent rather than passing: nothing here may be inferred from the config alone.
    if version == 2 and (dataflow_path or model_sources):
        def _dataflow():
            manifest = None
            if manifest_path and os.path.exists(manifest_path):
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
            if dataflow_path:
                with open(dataflow_path, 'r', encoding='utf-8') as f:
                    dataflow = json.load(f)
            else:
                modules = []
                for path in model_sources:
                    modules.extend(extract_dataflow.extract_file(path))
                dataflow = {'schema_version': 2, 'modules': modules}
            return check_dataflow.check_dataflow(
                config, dataflow, manifest, profile,
                strict_source_match=mode in ('A', 'B'))
        c, i = _run('dataflow', _dataflow)
        checks.append(c); all_issues.extend(i)

    # Shape validation is a debugging aid, not part of the formal contract: `shape_semantic`
    # is an annotation layered on the profiler's dims, so its absence says nothing about
    # whether the decomposition is right. It runs only under --with-shapes.
    if include_shapes:
        def _shapes():
            symbol_table = validate_shapes.build_symbol_table(config)
            pairs = validate_shapes.collect_kernels_with_op_data(config)
            issues = []
            for kernel, op_data in pairs:
                for level, msg in validate_shapes.validate_kernel(kernel, op_data, symbol_table, strict=True):
                    sev = {'ERROR': 'error', 'WARNING': 'warning', 'INFO': 'info'}.get(level, 'warning')
                    issues.append({'id': 'V1', 'severity': sev, 'node_path': '<kernel>', 'message': msg})
            return issues, {'kernels_checked': len(pairs)}
        c, i = _run('shapes', _shapes)
        checks.append(c); all_issues.extend(i)

    # regression vs manifest/baseline (auto-run when either is available, v2 only)
    if version == 2 and (manifest_path or baseline_path):
        def _regression():
            import regression_check as rc
            findings = []
            if baseline_path and os.path.exists(baseline_path):
                with open(baseline_path, 'r', encoding='utf-8') as f:
                    baseline = json.load(f)
                findings.extend(rc.check_regression(baseline, config))
            if manifest_path and os.path.exists(manifest_path):
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                findings.extend(rc.check_architecture_regression(config, manifest))
            hard = {'L1', 'L2', 'L3', 'L4', 'L7', 'MA1', 'MA2', 'MA3'}
            issues = []
            for f in findings:
                if not f.get('pass'):
                    # A finding may downgrade itself (e.g. MA1/MA3 against a
                    # low-confidence manifest); otherwise fall back to the id class.
                    # L8 only records optional shape annotations. Explicit
                    # --with-shapes remains the separate shape validation path.
                    sev = f.get('severity') or ('error' if f['id'] in hard else
                                               'info' if f['id'] == 'L8' else 'warning')
                    issues.append({'id': f['id'], 'severity': sev, 'node_path': 'regression',
                                   'message': json.dumps(f.get('detail', {}), ensure_ascii=False)[:300]})
            return issues, {'findings': len(findings)}
        c, i = _run('regression', _regression)
        checks.append(c); all_issues.extend(i)

    # A config can score 100 and still be rendered into a wrong picture, because the
    # downstream architecture graph is produced outside this skill. When the graph is
    # supplied, reconcile it against the config (repeat counts, layer coverage, nodes).
    if graph_path:
        def _graph_consistency():
            with open(graph_path, 'r', encoding='utf-8') as f:
                graph = json.load(f)
            return check_graph_consistency.validate_graph(graph, config)
        c, i = _run('graph_consistency', _graph_consistency)
        checks.append(c); all_issues.extend(i)

    error_count = sum(1 for it in all_issues if it.get('severity') == 'error')
    warning_count = sum(1 for it in all_issues if it.get('severity') == 'warning')
    # exploratory iff --allow-unmapped is on AND there are unmapped ops recorded
    has_unmapped = bool(config.get('unmapped_ops'))
    return checks, all_issues, error_count, warning_count, version, has_unmapped


def main():
    parser = argparse.ArgumentParser(description='Unified validation runner (single JSON report)')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-r', '--raw-ops', dest='raw_ops')
    parser.add_argument('-m', '--manifest')
    parser.add_argument('--source-dir', action='append', default=[])
    parser.add_argument('--mode', default='A', choices=['A', 'B'])
    parser.add_argument('--allow-warnings', action='store_true',
                        help='把 warning 降级为非阻断（会在报告中记录 override）')
    parser.add_argument('--allow-unmapped', action='store_true',
                        help='探索模式：允许 unmapped 存在（unmapped 降级为 warning）；'
                             '结果状态为 exploratory，绝不为 passed')
    parser.add_argument('--baseline', help='baseline analysis_config.json，做结构回归')
    parser.add_argument('--graph',
                        help='下游 model_architecture_graph.json；提供时与 config 交叉核对'
                             '（repeatCount / 层号覆盖 / 节点对应）')
    parser.add_argument('--with-shapes', action='store_true',
                        help='额外运行 shape 校验（调试用，不属于正式契约；'
                             'shape_semantic 缺失不代表拆解错误）')
    parser.add_argument('--dataflow',
                        help='extract_dataflow.py 产出的 dataflow_source.json；'
                             '与 config 声明的残差/分支拓扑逐条比对')
    parser.add_argument('--model-source', action='append', default=[],
                        help='模型源码文件；未提供 --dataflow 时就地推导数据流（可重复）')
    parser.add_argument('--profile', help='本次校验对应的 execution profile id')
    parser.add_argument('--fail-on-trace-mismatch', action='store_true',
                        help='让 manifest/trace 层数差异恢复为阻断 warning；'
                             '默认只作 info，因为一次采集可能只覆盖单个 step')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()

    if not os.path.exists(args.config):
        sys.stderr.write(f'错误: 文件不存在: {args.config}\n')
        sys.exit(2)

    checks, issues, error_count, warning_count, version, has_unmapped = run_all(
        args.config, args.raw_ops, args.manifest, args.source_dir,
        mode=args.mode, include_shapes=args.with_shapes,
        allow_unmapped=args.allow_unmapped, baseline_path=args.baseline,
        graph_path=args.graph,
        dataflow_path=args.dataflow, model_sources=args.model_source,
        profile=args.profile, fail_on_trace_mismatch=args.fail_on_trace_mismatch)

    exploratory = args.allow_unmapped and has_unmapped
    if error_count > 0:
        status = 'failed'
    elif exploratory:
        # unmapped ops present under exploratory override: NEVER passed
        status = 'exploratory'
    elif warning_count > 0:
        status = 'passed_with_warnings' if args.allow_warnings else 'failed'
    else:
        status = 'passed'

    report = {
        'status': status,
        'allow_warnings': args.allow_warnings,
        'allow_unmapped': args.allow_unmapped,
        'exploratory': exploratory,
        'error_count': error_count,
        'warning_count': warning_count,
        'config': args.config,
        'checks': checks,
        'issues': issues,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        print(f'validation report 已写入: {args.output}  status={status} '
              f'errors={error_count} warnings={warning_count}')
    else:
        print(text)

    # exploratory exits 0 (the run completed) but is NOT a passing result and must
    # never be accepted by report generation as a formal result.
    sys.exit(0 if status in ('passed', 'passed_with_warnings', 'exploratory') else 1)


if __name__ == '__main__':
    main()
