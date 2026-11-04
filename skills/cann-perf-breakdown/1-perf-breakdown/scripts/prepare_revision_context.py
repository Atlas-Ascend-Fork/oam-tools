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
"""Create a bounded revision package from deterministic issue locators."""
import argparse
import hashlib
import json
import os
import sys

import breakdown_common as bc


SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS_CONFIG_SCHEMA = os.path.join(
    SKILL_ROOT, 'schemas', 'analysis_config_v2.schema.json')


FORBIDDEN_INPUT_MARKERS = (
    'iterations/', 'critique_report.json', 'critique_validation.json',
    'validation_report.json', 'revision_request.json', '.md', '.html',
    'ui.json', 'screenshot',
)


def _sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path):
    return {'path': os.path.realpath(path), 'sha256': _sha(path)}


def _load(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _write(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write('\n')


def _unique(values):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _config_path(value):
    if not isinstance(value, str) or not value or value.startswith('<'):
        return None
    if value == '$' or value.startswith('$.') or value.startswith('$['):
        return value
    return '$.' + value


def _normalized_issues(paths, trusted_policy_paths=None):
    allowed = ('id', 'severity', 'message', 'node_path', 'claim', 'expected', 'observed',
               'repair', 'check_id', 'check')
    trusted = {os.path.realpath(path) for path in (trusted_policy_paths or [])}
    result = []
    for path in paths:
        payload = _load(path)
        file_policy_is_trusted = os.path.realpath(path) in trusted
        strict_warnings = (payload.get('status') == 'failed'
                           and payload.get('allow_warnings') is False)
        candidates = list(payload.get('issues') or [])
        candidates.extend(((payload.get('hard_gates') or {}).get('blocking_issues') or []))
        for issue in candidates:
            policy_is_trusted = (file_policy_is_trusted
                                 and issue.get('_scope_origin') != 'independent_review')
            severity = issue.get('severity', 'error')
            if severity != 'error' and not (strict_warnings and severity == 'warning'):
                continue
            normalized = {key: issue[key] for key in allowed if key in issue}
            normalized.setdefault('id', 'UNNAMED_BLOCKER')
            normalized.setdefault('severity', 'error')
            normalized['_repair_policy_source'] = (
                'deterministic_checker' if policy_is_trusted else 'untrusted')
            paths_found = list(issue.get('config_paths') or [])
            if issue.get('config_path'):
                paths_found.append(issue['config_path'])
            policy = ((issue.get('repair_policy') or {}) if policy_is_trusted else {})
            if policy:
                normalized['repair_policy'] = policy
            paths_found.extend(
                (policy.get('allowed_targets') or {}).get('analysis_config') or [])
            node_path = _config_path(issue.get('node_path'))
            if node_path:
                paths_found.append(node_path)
            normalized['config_paths'] = _unique([
                path for path in (_config_path(item) for item in paths_found) if path])
            source_refs = list(issue.get('source_evidence') or [])
            for evidence in issue.get('evidence') or []:
                if isinstance(evidence, str) and '.py:' in evidence:
                    source_refs.append(evidence)
                elif isinstance(evidence, dict) and evidence.get('source_ref'):
                    source_refs.append(evidence['source_ref'])
            normalized['source_evidence'] = _unique(source_refs)
            op_indices = list(issue.get('trace_evidence') or [])
            op_indices.extend(issue.get('op_indices') or [])
            for evidence in issue.get('evidence') or []:
                if isinstance(evidence, dict):
                    op_indices.extend(evidence.get('op_indices') or [])
            normalized['trace_evidence'] = sorted({
                value for value in op_indices if isinstance(value, int)})
            result.append(normalized)
    return result


def _diagnostic_routes(issues):
    """Return checker-authorized repair routes without granting implicit write access."""
    routes = []
    for issue in issues:
        policy = issue.get('repair_policy') or {}
        allowed_targets = policy.get('allowed_targets') or {}
        normalized_targets = {}
        for target in ('analysis_config', 'manifest_hypothesis'):
            prefixes = allowed_targets.get(target) or []
            valid = [path for path in prefixes
                     if bc.json_path_parts(path) is not None]
            if valid:
                normalized_targets[target] = _unique(valid)
        node_path = issue.get('node_path') or ''
        owner = policy.get('owner_artifact')
        if not owner and isinstance(node_path, str) and node_path:
            owner = node_path.split('.', 1)[0].split('/', 1)[0]
        routes.append({
            'issue_id': issue.get('id', 'UNNAMED_BLOCKER'),
            'owner_artifact': owner or 'unknown',
            'repair_class': policy.get('repair_class', 'unclassified'),
            'mode': 'bounded_patch' if normalized_targets else 'diagnosis_only',
            'allowed_targets': normalized_targets,
            'trace_selectors': list(policy.get('trace_selectors') or []),
            'policy_status': (
                'declared' if policy else
                ('missing_from_deterministic_checker'
                 if issue.get('_repair_policy_source') == 'deterministic_checker'
                 else 'untrusted')),
        })
    return routes


def _path_parts(path):
    return bc.json_path_parts(path)


def _resolve(config, path):
    parts = bc._typed_json_path_parts(path)
    if parts is None:
        return False, None
    current = config
    for part in parts:
        if isinstance(current, dict) and isinstance(part, str) and part in current:
            current = current[part]
        elif isinstance(current, list) and isinstance(part, int) and part < len(current):
            current = current[part]
        else:
            return False, None
    return True, current


def _add_legacy_candidate_policies(config, issues):
    """Recover a bounded route for old deterministic reports.

    Current checkers attach repair_policy themselves. Reports produced before that
    contract may still name an exact candidate path, and sending those issues to a
    diagnosis worker cannot repair them. Only authorize the exact existing path under
    structures; everything else keeps the normal controlled-diagnosis route.
    """
    for issue in issues:
        if (issue.get('repair_policy')
                or issue.get('_repair_policy_source') != 'deterministic_checker'):
            continue
        path = _config_path(issue.get('node_path'))
        parts = _path_parts(path)
        structures = config.get('structures') or {}
        if (not parts or len(parts) < 2 or parts[0] != 'structures'
                or parts[1] not in structures or not _resolve(config, path)[0]):
            continue
        issue['repair_policy'] = {
            'owner_artifact': 'analysis_config',
            'repair_class': 'legacy_candidate_path_repair',
            'allowed_targets': {'analysis_config': [path]},
            'required_evidence': ['candidate_nodes'],
        }
        issue['config_paths'] = _unique(list(issue.get('config_paths') or []) + [path])


def _walk_nodes(node, path='$'):
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            child = bc.json_path_child(path, key)
            yield from _walk_nodes(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk_nodes(value, bc.json_path_child(path, index))


def _node_op_indices(node):
    found = set()
    if isinstance(node, dict):
        found.update(value for value in node.get('op_indices') or []
                     if isinstance(value, int))
        for key, value in node.items():
            if key != 'op_data':
                found.update(_node_op_indices(value))
    elif isinstance(node, list):
        for value in node:
            found.update(_node_op_indices(value))
    return found


def _structure_path(path):
    parts = _path_parts(path) or []
    if len(parts) >= 2 and parts[0] == 'structures':
        return bc.json_path('structures', parts[1])
    return None


def _candidate_evidence(config, issues):
    nodes = []
    seen = set()
    for issue in issues:
        resolved_paths = []
        for path in issue['config_paths']:
            exists, value = _resolve(config, path)
            if exists:
                resolved_paths.append(path)
                if path not in seen:
                    nodes.append({'path': path, 'value': value})
                    seen.add(path)
        if not resolved_paths and issue['trace_evidence']:
            wanted = set(issue['trace_evidence'])
            for path, value in _walk_nodes(config):
                direct = set(value.get('op_indices') or []) if isinstance(value, dict) else set()
                if direct & wanted:
                    resolved_paths.append(path)
                    if path not in seen:
                        nodes.append({'path': path, 'value': value})
                        seen.add(path)
        if resolved_paths:
            issue['config_paths'] = _unique(resolved_paths)
        if not issue['trace_evidence']:
            derived = set()
            for path in resolved_paths:
                structure_path = _structure_path(path)
                exists, value = _resolve(config, structure_path or path)
                if exists:
                    derived.update(_node_op_indices(value))
            issue['trace_evidence'] = sorted(derived)
    return {'schema_version': 1, 'nodes': nodes}


def _source_record(index, name):
    normalized = str(name or '').replace('\\', '/')
    records = list(index.get('files') or [])

    if os.path.isabs(normalized):
        wanted = os.path.realpath(normalized)
        exact = [record for record in records
                 if os.path.realpath(os.path.join(
                     record.get('root', ''),
                     *record.get('path', '').replace('\\', '/').split('/'))) == wanted]
        if len(exact) == 1:
            return exact[0]
        return None

    relative = normalized[2:] if normalized.startswith('./') else normalized
    exact = [record for record in records
             if record.get('path', '').replace('\\', '/') == relative]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None

    fuzzy = []
    basename = os.path.basename(normalized)
    for record in records:
        path = record.get('path', '').replace('\\', '/')
        if (path.endswith('/' + normalized)
                or normalized.endswith('/' + path)
                or (basename and os.path.basename(path) == basename)):
            fuzzy.append(record)
    return fuzzy[0] if len(fuzzy) == 1 else None


def _dataflow_source_refs(index, issues, dataflow):
    modules = (dataflow or {}).get('modules') or []
    for issue in issues:
        if issue['source_evidence']:
            continue
        structure_names = []
        for path in issue['config_paths']:
            parts = _path_parts(path) or []
            if len(parts) >= 2 and parts[0] == 'structures':
                structure_names.append(parts[1])
        matches = []
        for module in modules:
            class_name = module.get('class_name') or ''
            if any(name == class_name or name.startswith(class_name + '_')
                   for name in structure_names):
                matches.append(module)
        if not matches:
            matches = [item for item in modules if item.get('is_primary')]
        if not matches:
            continue
        module = sorted(matches, key=lambda item: not item.get('is_primary'))[0]
        record = _source_record(index, module.get('source_path') or '')
        if not record:
            continue
        class_name = module.get('class_name')
        forward = next((item.get('forward') for item in record.get('classes') or []
                        if item.get('name') == class_name and item.get('forward')), None)
        if forward:
            issue['source_evidence'] = [
                f'{record["path"]}:{forward["line_start"]}-{forward["line_end"]}']


def _source_snippets(index, issues):
    requested = [ref for issue in issues for ref in issue['source_evidence']]
    snippets = []
    for ref in sorted(set(requested)):
        name, _, span = ref.rpartition(':')
        record = _source_record(index, name)
        if not record or not span:
            continue
        try:
            parts = [int(value) for value in span.split('-', 1)]
        except ValueError:
            continue
        start, end = parts[0], parts[-1]
        enclosing = []
        for item in record.get('functions') or []:
            if item['line_start'] <= start and item['line_end'] >= end:
                enclosing.append((item['line_end'] - item['line_start'],
                                  item['line_start'], item['line_end']))
        for item in record.get('classes') or []:
            for method in ('init', 'forward'):
                function_range = item.get(method)
                if (function_range and function_range['line_start'] <= start
                        and function_range['line_end'] >= end):
                    enclosing.append((function_range['line_end']
                                      - function_range['line_start'],
                                      function_range['line_start'],
                                      function_range['line_end']))
        if enclosing:
            _, start, end = min(enclosing)
        source_path = os.path.join(record['root'], *record['path'].replace('\\', '/').split('/'))
        with open(source_path, encoding='utf-8') as stream:
            lines = stream.readlines()
        start = max(1, start)
        end = min(len(lines), end)
        snippets.append({'source_ref': f'{record["path"]}:{start}-{end}',
                         'sha256': record['sha256'],
                         'text': ''.join(lines[start - 1:end])})
    return {'schema_version': 1, 'source_bundle_hash': index['source_bundle_hash'],
            'snippets': snippets}


def _raw_slice(raw, issues):
    operators = raw.get('operators') or raw.get('ops') or []
    wanted = {value for issue in issues for value in issue['trace_evidence']}
    for issue in issues:
        selectors = (issue.get('repair_policy') or {}).get('trace_selectors') or []
        matched = []
        for operator in operators:
            normalized = str(operator.get('normalized_name') or operator.get('name') or '')
            original = str(operator.get('name') or '')
            for selector in selectors:
                field = selector.get('field')
                mode = selector.get('match')
                values = [value for value in selector.get('values') or []
                          if isinstance(value, str) and value]
                candidate = original if field == 'name' else normalized
                if field not in ('name', 'normalized_name'):
                    continue
                hit = ((mode == 'exact' and candidate in values)
                       or (mode == 'prefix'
                           and any(candidate.startswith(value) for value in values))
                       or (mode == 'contains'
                           and any(value in candidate for value in values)))
                if hit and isinstance(operator.get('index'), int):
                    matched.append(operator['index'])
                    break
        issue['trace_evidence'] = sorted(set(issue['trace_evidence']) | set(matched))
        wanted.update(matched)
    selected = [item for item in operators if item.get('index') in wanted]
    selected_indices = sorted(item.get('index') for item in selected
                              if isinstance(item.get('index'), int))
    for issue in issues:
        issue['trace_evidence'] = sorted(
            set(issue['trace_evidence']) & set(selected_indices))
    return {'schema_version': 1, 'op_indices': selected_indices, 'operators': selected}


def _source_identity(index, source_ref):
    name = str(source_ref or '').rpartition(':')[0]
    record = _source_record(index, name) if index else None
    if record:
        path = os.path.realpath(os.path.join(
            record.get('root', ''),
            *record.get('path', '').replace('\\', '/').split('/')))
        return path, record.get('sha256')
    return name.replace('\\', '/') or None


def _missing_evidence_for_issue(config, issue, snippets, source_index=None):
    required = set((issue.get('repair_policy') or {}).get('required_evidence') or (
        'candidate_nodes', 'source_snippets', 'raw_ops_slice'))
    snippet_files = {
        _source_identity(source_index, item.get('source_ref'))
        for item in snippets.get('snippets') or []
    }
    issue_files = {
        _source_identity(source_index, ref)
        for ref in issue.get('source_evidence') or []
    }
    available = {
        'candidate_nodes': any(
            _resolve(config, path)[0] for path in issue.get('config_paths') or []),
        'source_snippets': bool(issue_files & snippet_files),
        'raw_ops_slice': bool(issue.get('trace_evidence')),
    }
    return sorted(name for name in required if not available.get(name, False))


def prepare_revision_context(config_path, source_index_path, raw_ops_path, issue_paths,
                             output_path, context_manifest_path, dataflow_path=None,
                             trusted_policy_paths=None):
    index = _load(source_index_path)
    config = _load(config_path)
    issues = _normalized_issues(issue_paths, trusted_policy_paths)
    _add_legacy_candidate_policies(config, issues)
    candidate_nodes = _candidate_evidence(config, issues)
    dataflow = _load(dataflow_path) if dataflow_path and os.path.exists(dataflow_path) else None
    _dataflow_source_refs(index, issues, dataflow)
    snippets = _source_snippets(index, issues)
    raw_slice = _raw_slice(_load(raw_ops_path), issues)
    diagnostic_routes = _diagnostic_routes(issues)
    missing_by_issue = [
        _missing_evidence_for_issue(config, issue, snippets, index) for issue in issues]
    non_candidate = [
        index for index, route in enumerate(diagnostic_routes)
        if 'manifest_hypothesis' in route['allowed_targets']]
    diagnostic_indices = non_candidate or [
        index for index, missing in enumerate(missing_by_issue) if missing]
    if not issues or diagnostic_indices:
        selected_issues = [issues[index] for index in diagnostic_indices]
        selected_routes = [diagnostic_routes[index] for index in diagnostic_indices]
        missing = sorted({
            name for index in diagnostic_indices for name in missing_by_issue[index]})
        deferred = [issue.get('id', 'UNNAMED_BLOCKER')
                    for index, issue in enumerate(issues)
                    if index not in set(diagnostic_indices)]
        blocked = {
            'schema_version': 1,
            'status': 'needs_controlled_diagnosis',
            'diagnostic_reason': (
                'non_candidate_artifact' if non_candidate
                else ('insufficient_targeted_evidence' if missing
                      else 'missing_blocking_issues')),
            'missing_evidence': missing,
            'blocking_issues': selected_issues,
            'diagnostic_routes': selected_routes,
            'deferred_issue_ids': deferred,
            'candidate_sha256': _sha(config_path),
            'source_bundle_hash': index.get('source_bundle_hash'),
        }
        _write(output_path, blocked)
        return blocked

    context_dir = os.path.dirname(os.path.abspath(context_manifest_path))
    candidate_nodes_path = os.path.join(context_dir, 'candidate_nodes.json')
    snippets_path = os.path.join(context_dir, 'source_snippets.json')
    raw_slice_path = os.path.join(context_dir, 'raw_ops.slice.json')
    _write(candidate_nodes_path, candidate_nodes)
    _write(snippets_path, snippets)
    _write(raw_slice_path, raw_slice)
    inputs = {
        'current_candidate': _artifact(config_path),
        'candidate_nodes': _artifact(candidate_nodes_path),
        'source_index': _artifact(source_index_path),
        'source_snippets': _artifact(snippets_path),
        'raw_ops_slice': _artifact(raw_slice_path),
        'analysis_config_schema': _artifact(ANALYSIS_CONFIG_SCHEMA),
    }
    bindings = {'raw_ops': _artifact(raw_ops_path)}
    if dataflow_path and os.path.exists(dataflow_path):
        bindings['dataflow_source'] = _artifact(dataflow_path)
    manifest = {
        'schema_version': 1,
        'stage': 'revision',
        'source_bundle_hash': index['source_bundle_hash'],
        'candidate_sha256': _sha(config_path),
        'inputs': inputs,
        'bindings_not_llm_inputs': bindings,
        'forbidden_inputs': list(FORBIDDEN_INPUT_MARKERS),
    }
    _write(context_manifest_path, manifest)
    request = {
        'schema_version': 1,
        'task': 'revise only the evidence-backed blocking items',
        'session': {
            'clean_context_required': True,
            'fork_turns': 'none',
            'inherit_history': False,
        },
        'inputs': inputs,
        'candidate_sha256': _sha(config_path),
        'source_bundle_hash': index['source_bundle_hash'],
        'blocking_issues': issues,
        'context_manifest': os.path.realpath(context_manifest_path),
        'bindings_not_llm_inputs': bindings,
        'output_expected': os.path.realpath(config_path),
        'rules': [
            'Use only paths listed in context_manifest.inputs.',
            'Do not read iterations or any prior config, validation, critique, revision, UI, report, or screenshot artifact.',
            'Do not rescan the source tree; use source_index and source_snippets only.',
            'Modify only evidence-backed blocking paths and preserve all unmentioned candidate content.',
            'Write the complete schema-v2 analysis_config.json to output_expected; do not return a patch or free-form explanation.',
        ],
    }
    _write(output_path, request)
    return request


def main():
    parser = argparse.ArgumentParser(description='Prepare isolated revision context')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('--source-index', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('--dataflow')
    parser.add_argument('--issues', action='append', required=True)
    parser.add_argument(
        '--trusted-policy-issues', action='append', default=[],
        help='deterministic checker output authorized to declare repair_policy')
    parser.add_argument('--context-manifest', required=True)
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()
    request = prepare_revision_context(
        args.config, args.source_index, args.raw_ops, args.issues,
        args.output, args.context_manifest, dataflow_path=args.dataflow,
        trusted_policy_paths=args.trusted_policy_issues)
    if request.get('status') == 'needs_controlled_diagnosis':
        print(json.dumps(request, indent=2, ensure_ascii=False))
        return 2
    print(f'revision context written: {args.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
