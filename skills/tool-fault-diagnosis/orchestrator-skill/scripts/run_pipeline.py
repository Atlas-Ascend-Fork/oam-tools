#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
# ----------------------------------------------------------------------------
"""Seven-stage CANN pipeline. Markdown is the shared skill/retry/resume artifact."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from artifact_contract import (STAGE_FILES, OWNERS, new_artifact, read_artifact,
                               write_artifact, atomic_write, now_iso)

SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_ROOT = SCRIPT_DIR.parent.parent
STAGE_IDS = tuple(STAGE_FILES)
STATE_VERSION = 2
TERMINAL_OK = ('success', 'skipped')
MANUAL = ()
CHECK_KEYS = ('has_first_error_line', 'has_env_version', 'has_full_timeline', 'has_crash_artifacts',
              'has_repro_input', 'multi_source_agree', 'timeline_consistent', 'no_contradiction',
              'root_cause_localized', 'chain_no_gap', 'alternatives_excluded', 'reproducible',
              'fix_verified', 'regression_checked', 'errcode_documented', 'case_matched',
              'source_code_confirmed')
BUSINESS_FIELDS = {
    'case_lookup': ('status', 'library_path', 'library_sha256', 'query_features', 'matches', 'errors', 'limitations'),
    'detect': ('primary', 'secondary', 'recognition_confidence', 'scenarios', 'materials', 'errors', 'route'),
    'diagnose': ('first_error', 'timeline', 'causal_chain', 'root_cause', 'alternatives',
                 'recommendations', 'checks', 'references'),
    'report': ('conclusion', 'confidence', 'findings', 'recommendations', 'limitations'),
    'confidence': ('final_score', 'level', 'dimensions', 'unmet_critical', 'missing_items',
                   'case_gate', 'case_gate_reason'),
    'promote': ('enabled', 'decision', 'case_gate', 'target', 'case_id', 'mutation_id', 'reason'),
}
SCRIPTS = {'case_lookup': 'orchestrator-skill/scripts/detect_scenario.py',
           'detect': 'orchestrator-skill/scripts/detect_scenario.py',
           'confidence': 'eval-skill/scripts/assess_confidence.py',
           'promote': 'eval-skill/scripts/promote_case.py'}
TRACE_SCRIPT = SKILLS_ROOT / 'trace-skill/scripts/build_fault_trace.py'
TRACE_CORE_DIR = SKILLS_ROOT / 'trace-skill/scripts/fault_trace_core'
HTML_SCRIPT = SKILLS_ROOT / 'metric-skill/scripts/build_html_report.py'
HTML_TEMPLATE = SKILLS_ROOT / 'metric-skill/template/index.html'
HTML_RULES = SKILLS_ROOT / 'metric-skill/template/report-template-rules.md'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def file_hash(path):
    if not path.is_file():
        return None
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def within(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def classify_error(exc=None, returncode=None, stderr=''):
    text = (str(exc or '') + '\n' + stderr).lower()
    if isinstance(exc, MemoryError) or any(x in text for x in
        ('no space left', 'disk full', 'cannot allocate memory', 'out of memory', 'quota exceeded')):
        return 'resource'
    if isinstance(exc, (ValueError, TypeError, KeyError, PermissionError, FileNotFoundError)):
        return 'permanent'
    if any(x in text for x in ('usage:', 'unrecognized arguments', 'not found', 'permission denied')):
        return 'permanent'
    if isinstance(exc, subprocess.TimeoutExpired) or any(x in text for x in
        ('timed out', 'temporarily unavailable', 'connection reset', 'resource busy', 'eagain', 'eintr')):
        return 'transient'
    if isinstance(exc, OSError) and exc.errno in (4, 11, 16):
        return 'transient'
    return 'permanent' if returncode == 2 else 'unknown'


class StepError(Exception):
    def __init__(self, message, category='permanent', code=None):
        super().__init__(message)
        self.category, self.code = category, code


class Blocked(Exception):
    pass


class Plan:
    def __init__(self, path, state_dir):
        self.path, self.state_dir = path.resolve(), state_dir.resolve()
        self.raw = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(self.raw, dict):
            raise ValueError('plan must be an object')
        self.input = self.raw.get('input', {})
        if not isinstance(self.input, dict) or not self.input.get('path'):
            raise ValueError('plan.input.path is required')
        self.source = Path(self.input['path'])
        if not self.source.is_absolute():
            self.source = self.path.parent / self.source
        self.source = self.source.resolve()
        if not self.source.exists():
            raise FileNotFoundError(str(self.source))
        if within(self.source, state_dir):
            raise ValueError('Input must not be inside the pipeline state directory')
        if self.source.is_dir() and (within(self.state_dir, self.source) or within(self.path, self.source)):
            raise ValueError('Plan and pipeline state must be outside the original input directory')
        requested = self.raw.get('pipeline') or self.raw.get('route', {}).get('pipeline_stages')
        if requested and tuple(requested) != STAGE_IDS:
            raise ValueError('plan must use the fixed seven-stage order')
        self.stages = self.raw.get('stages', self.raw.get('stage_params', self.raw.get('parameters', {})))
        lookup = self.raw.get('case_lookup', {})
        self.library = Path(lookup.get('library_path') or SKILLS_ROOT / 'eval-skill/references/cases.md')
        if not self.library.is_absolute():
            self.library = self.path.parent / self.library
        self.library = self.library.resolve()

    def params(self, sid):
        data = self.stages.get(sid, {})
        if not isinstance(data, dict):
            raise ValueError('stage parameters must be objects')
        return dict(data)

    def artifact(self, sid):
        return self.state_dir / 'artifacts' / STAGE_FILES[sid]

    def materials(self):
        paths = [self.source] if self.source.is_file() else sorted(self.source.rglob('*'))
        return [{'path': str(p.resolve()), 'sha256': file_hash(p)} for p in paths
                if p.is_file() and not within(p, self.state_dir) and p.resolve() != self.path]


def blank_stage():
    return {'status': 'pending', 'attempts': 0, 'failures': 0, 'revision': uuid.uuid4().hex,
            'inputs_fingerprint': None, 'artifact_sha256': None, 'last_error': None}


def load_state(path):
    if not path.exists():
        return {'version': STATE_VERSION, 'run_id': uuid.uuid4().hex, 'created_at': now_iso(),
                'stages': {sid: blank_stage() for sid in STAGE_IDS}}
    state = json.loads(path.read_text(encoding='utf-8-sig'))
    if state.get('version') != STATE_VERSION or tuple(state.get('stages', {})) != STAGE_IDS:
        raise ValueError('State schema changed; select a new --state-dir and retain old state for audit')
    return state


def save_state(plan, state):
    state['updated_at'] = now_iso()
    atomic_write(plan.state_dir / 'state.json', json.dumps(state, ensure_ascii=False, indent=2))


def acquire_lock(directory, force=False):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'pipeline.lock'
    payload = {'pid': os.getpid(), 'token': uuid.uuid4().hex,
               'host': os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', '')), 'at': now_iso()}
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        old = json.loads(path.read_text(encoding='utf-8'))
        if not force or old.get('host') != payload['host']:
            raise StepError('State lock exists; use --force-unlock only after the process exits', 'conflict')
        pid = int(old.get('pid', 0))
        if pid <= 0:
            raise StepError('Invalid lock owner; review lock before removal', 'conflict')
        if os.name == 'nt':
            result = subprocess.run(['tasklist', '/FI', 'PID eq %s' % pid, '/NH'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            if str(pid) in result.stdout.decode('utf-8', 'replace') or result.returncode:
                raise StepError('Lock owner is still running or could not be checked', 'conflict')
        else:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            else:
                raise StepError('Lock owner is still running', 'conflict')
        path.unlink()
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(payload, stream)
        stream.flush()
        os.fsync(stream.fileno())
    return path, payload['token']


def release_lock(lock):
    if lock:
        path, token = lock
        try:
            if json.loads(path.read_text(encoding='utf-8')).get('token') == token:
                path.unlink()
        except (OSError, ValueError):
            pass


def inputs_for(sid, plan, state):
    index = STAGE_IDS.index(sid)
    upstream = [{'stage': other, 'path': str(plan.artifact(other)),
                 'sha256': file_hash(plan.artifact(other))} for other in STAGE_IDS[:index]]
    scripts = [SCRIPT_DIR / 'run_pipeline.py', SCRIPT_DIR / 'artifact_contract.py']
    if sid in SCRIPTS:
        scripts.append(SKILLS_ROOT / SCRIPTS[sid])
    if sid == 'diagnose':
        scripts.append(TRACE_SCRIPT)
        scripts.extend(sorted(TRACE_CORE_DIR.glob('*.py')))
    if sid == 'report':
        scripts.extend((HTML_SCRIPT, HTML_TEMPLATE, HTML_RULES))
    materials = plan.materials()
    parameters = plan.params(sid)
    dependencies = {'input': plan.input, 'revision': state['stages'][sid]['revision'],
                    'scripts': {str(p): file_hash(p) for p in scripts}}
    if sid in ('case_lookup', 'detect'):
        dependencies['case_library'] = {'path': str(plan.library), 'sha256': lookup_library_hash(plan, state)}
    value = {'materials': materials, 'upstream': upstream, 'parameters': parameters,
             'dependencies': dependencies}
    value['fingerprint'] = digest(value)
    return value


def lookup_library_hash(plan, state):
    """A verified publication by this run does not invalidate its own earlier lookup."""
    actual = file_hash(plan.library)
    try:
        lookup, _ = read_artifact(plan.artifact('case_lookup'), 'case_lookup', state['run_id'])
        if lookup['inputs']['dependencies']['revision'] != state['stages']['case_lookup']['revision']:
            return actual
        baseline = lookup['inputs']['dependencies']['case_library']['sha256']
    except (OSError, ValueError, KeyError, TypeError):
        return actual
    receipts = []
    for path in (plan.state_dir / 'mutations').glob('*.json'):
        try:
            receipt = json.loads(path.read_text(encoding='utf-8'))
            if receipt.get('run_id') == state['run_id'] and receipt.get('target') == str(plan.library):
                receipts.append(receipt)
        except (OSError, ValueError):
            continue
    current, seen = actual, set()
    while current != baseline and current not in seen:
        seen.add(current)
        match = next((item for item in receipts if item.get('after_sha256') == current), None)
        if match is None:
            return actual
        current = match['before_sha256']
    return baseline if current == baseline else actual


def read_current(sid, plan, state, inputs):
    return read_artifact(plan.artifact(sid), sid, state['run_id'], inputs['fingerprint'])


def validate_business(sid, data):
    if data['status'] not in TERMINAL_OK:
        raise ValueError('Artifact is not complete')
    if sid not in ('clean', 'promote') and data['status'] == 'skipped':
        raise ValueError('This stage cannot be skipped')
    result = data['result']
    required = BUSINESS_FIELDS.get(sid, ())
    if any(key not in result for key in required):
        raise ValueError('Missing business fields: ' + ', '.join(required))
    if not any(o['kind'] == 'primary_markdown' for o in data['outputs']):
        raise ValueError('A primary Markdown output must be declared')
    if sid == 'case_lookup' and (result['status'] not in ('hit', 'miss', 'unavailable') or
                                 not isinstance(result['matches'], list) or
                                 not isinstance(result['errors'], list)):
        raise ValueError('Invalid case lookup status or candidates')
    if sid == 'detect' and (not isinstance(result['secondary'], list) or
                            not isinstance(result['errors'], list) or
                            tuple(result['route'].get('pipeline_stages', [])) != STAGE_IDS):
        raise ValueError('Classification must retain candidate list and the complete pipeline')
    if sid == 'diagnose':
        if not isinstance(result['checks'], dict) or set(result['checks']) != set(CHECK_KEYS):
            raise ValueError('Diagnosis needs an explicitly reviewed confidence checklist')
        if any(not isinstance(v, dict) or not isinstance(v.get('value'), bool) or
               'evidence' not in v or (v['value'] and not v['evidence']) for v in result['checks'].values()):
            raise ValueError('Every confidence check needs a Boolean and evidence; true checks cannot be unsupported')
        cause = result['root_cause']
        if not isinstance(cause, dict) or not cause.get('description') or cause.get('status') not in ('confirmed', 'hypothesis', 'undetermined'):
            raise ValueError('Root cause needs a description and confirmed/hypothesis/undetermined status')
        if any(not isinstance(result[key], list) for key in ('timeline', 'causal_chain', 'alternatives', 'recommendations', 'references')):
            raise ValueError('Diagnosis evidence, timeline and alternatives must be arrays')
        if not result['references'] or (not result['timeline'] and not data['evidence_gaps']):
            raise ValueError('Reference supplied materials and explain any unavailable timeline')
    if sid == 'report' and (not result['conclusion'] or not result['findings']):
        raise ValueError('Report conclusion and findings must be filled')
    if sid == 'report':
        upstream = next((entry for entry in data['inputs']['upstream'] if entry['stage'] == 'confidence'), None)
        if not upstream or read_artifact(upstream['path'], 'confidence', data['run_id'])[0]['result'] != result['confidence']:
            raise ValueError('Report confidence must exactly preserve the actual confidence.md result')
    if sid == 'confidence' and (not isinstance(result['final_score'], (int, float)) or
                                not 0 <= result['final_score'] <= 100):
        raise ValueError('Invalid confidence score')
    if sid == 'clean' and result.get('applicability') != 'not_applicable':
        if any(key not in result for key in ('mode', 'input_lines', 'kept_lines', 'collapsed_lines', 'files', 'audit_path')):
            raise ValueError('Cleaning result is missing line counts, file mapping or audit path')
        counts = [result[k] for k in ('input_lines', 'kept_lines', 'collapsed_lines')]
        if any(type(n) is not int or n < 0 for n in counts) or counts[0] != counts[1] + counts[2]:
            raise ValueError('Cleaning line counts must reconcile')
        if not result['files'] or not result['audit_path'] or not any(o['kind'] == 'cleaned_log' for o in data['outputs']):
            raise ValueError('Equivalent cleaning needs real logs, source mapping and audit')
    for output in data['outputs']:
        if output['kind'] != 'primary_markdown':
            path = Path(output['path'])
            if not output.get('sha256') or file_hash(path) != output['sha256']:
                raise ValueError('Supporting output is absent or changed: ' + str(path))


def reusable(sid, plan, state):
    stage = state['stages'][sid]
    if stage['status'] not in TERMINAL_OK:
        return False
    try:
        artifact, _ = read_current(sid, plan, state, inputs_for(sid, plan, state))
        validate_business(sid, artifact)
        return file_hash(plan.artifact(sid)) == stage['artifact_sha256']
    except (OSError, ValueError, KeyError, TypeError):
        return False


def invalidate(state, sid):
    for other in STAGE_IDS[STAGE_IDS.index(sid):]:
        previous = state['stages'][other]
        fresh = blank_stage()
        fresh['attempts'] = previous['attempts']
        state['stages'][other] = fresh


def run_command(argv, timeout=600):
    environment = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, encoding='utf-8', errors='replace',
                            env=environment, timeout=timeout)
    if result.returncode:
        raise StepError(result.stderr.strip() or result.stdout.strip() or str(result.returncode),
                        classify_error(returncode=result.returncode, stderr=result.stderr), result.returncode)
    return result.stdout


def child(sid):
    script = SKILLS_ROOT / SCRIPTS[sid]
    if not script.is_file():
        raise Blocked('Automatic executor unavailable. Complete the same Markdown contract using an equivalent executor.')
    return [sys.executable, str(script)]


def detector(sid, plan):
    argv = child(sid) + ['--input', str(plan.source), '--phase', sid,
                         '--json', '--cases-library', str(plan.library)]
    for key, flag in (('request', '--request'), ('max_bytes', '--max-bytes'), ('max_files', '--max-files')):
        if key in plan.input:
            argv += [flag, str(plan.input[key])]
    argv += ['--level', str(plan.input.get('level', 'DEBUG'))]
    if sid == 'detect':
        argv += ['--case-match', str(plan.artifact('case_lookup'))]
    return json.loads(run_command(argv, plan.params(sid).get('timeout', 600)))


def attach(artifact, path, kind):
    artifact['outputs'].append({'path': str(path.resolve()), 'kind': kind, 'sha256': file_hash(path)})


def prepare_clean_input(plan, artifact, work):
    """Extract supplied ZIP text members with unambiguous archive-to-file mapping."""
    suffixes = {'.log', '.txt', '.out', '.err', '.trace', '.info', '.stack'}
    source = plan.source
    if source.is_file() and source.suffix.lower() == '.zip':
        extracted = work / 'extracted'
        aliases = []
        with zipfile.ZipFile(str(source)) as archive:
            entries = sorted((i for i in archive.infolist() if not i.is_dir()), key=lambda i: i.filename)
            for index, entry in enumerate(entries):
                name = entry.filename.replace('\\', '/')
                parts = PurePosixPath(name)
                if parts.is_absolute() or '..' in parts.parts or ':' in name or ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                    raise StepError('Unsafe ZIP entry; original archive retained: ' + name)
                if parts.suffix.lower() not in suffixes:
                    continue
                target = extracted / ('%04d' % index) / Path(*parts.parts)
                if not within(target, extracted):
                    raise StepError('ZIP entry escapes extraction directory')
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as reader, target.open('wb') as writer:
                    shutil.copyfileobj(reader, writer)
                attach(artifact, target, 'original_archive_member')
                aliases.append({'source': str(target.resolve()), 'archive': str(source),
                                'member': entry.filename, 'member_index': index,
                                'original_ref': source.name + '!' + name + '#' + str(index),
                                'sha256': file_hash(target)})
        return extracted, [Path(a['source']) for a in aliases], aliases
    logs = ([source] if source.is_file() and source.suffix.lower() in suffixes else
            sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in suffixes) if source.is_dir() else [])
    return source, logs, []


def _trace_input(plan, work):
    """Give trace-skill a directory for a single log while preserving archives."""
    if plan.source.is_dir() or plan.source.suffix.lower() == '.zip':
        return plan.source
    directory = work / 'trace-input'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / plan.source.name
    shutil.copy2(plan.source, target)
    return directory


def _run_trace(plan, artifact, work):
    trace_dir = work / 'trace'
    trace_dir.mkdir(parents=True, exist_ok=True)
    if not TRACE_SCRIPT.is_file():
        artifact['evidence_gaps'].append('trace-skill 脚本不可用；已保留原始日志继续诊断。')
        return None, trace_dir
    try:
        run_command([sys.executable, str(TRACE_SCRIPT), str(_trace_input(plan, work)),
                     '--output-dir', str(trace_dir)], plan.params('diagnose').get('timeout', 1800))
    except (StepError, OSError, shutil.Error) as exc:
        artifact['evidence_gaps'].append('trace-skill 未生成有效 trace：' + str(exc))
        for path in sorted(trace_dir.glob('fault-trace-inventory.json')):
            attach(artifact, path, 'trace_inventory')
        return None, trace_dir

    kinds = {
        'fault-trace.json': 'fault_trace_json',
        'tracing-report.html': 'trace_report_html',
        'fault-trace.html': 'fault_trace_html',
    }
    for name, kind in kinds.items():
        path = trace_dir / name
        if path.is_file():
            attach(artifact, path, kind)
    trace_path = trace_dir / 'fault-trace.json'
    if not trace_path.is_file():
        artifact['evidence_gaps'].append('trace-skill 未产生 fault-trace.json。')
        return None, trace_dir
    try:
        return json.loads(trace_path.read_text(encoding='utf-8')), trace_dir
    except (OSError, ValueError) as exc:
        artifact['evidence_gaps'].append('fault-trace.json 无法读取：' + str(exc))
        return None, trace_dir


def _timestamp(text):
    match = re.search(r'(?:\d{4}[-/]\d{2}[-/]\d{2}[ T-])?\d{2}:\d{2}:\d{2}(?:\.\d{1,6}){1,2}',
                     str(text or ''))
    return match.group(0) if match else '时间戳未提供'


def _entity(text, pattern):
    match = re.search(pattern, str(text or ''), re.IGNORECASE)
    return match.group(1) if match else None


def _event_source(event, trace):
    evidence = trace.get('evidence', {}) if isinstance(trace, dict) else {}
    for evidence_id in event.get('evidence_ids', []):
        item = evidence.get(evidence_id)
        if isinstance(item, dict):
            return {'file': item.get('source_path'), 'line': item.get('line'),
                    'text': item.get('excerpt') or event.get('message', '')}
    return {'file': event.get('source_path'), 'line': event.get('line'),
            'text': event.get('message', '')}


def _trace_timeline(trace):
    if not isinstance(trace, dict):
        return []
    anchor = trace.get('selected_anchor_id')
    rows = []
    for event in trace.get('events', []):
        if not isinstance(event, dict):
            continue
        source = _event_source(event, trace)
        raw_time = ((event.get('timestamp') or {}).get('raw'))
        status = 'direct_trigger' if event.get('id') == anchor else 'observed'
        rows.append({
            'id': event.get('id'),
            'time': raw_time or '时间戳未提供',
            'host': event.get('location'),
            'pid': ((event.get('execution') or {}).get('pid')),
            'rank': ((event.get('execution') or {}).get('rank')),
            'device': ((event.get('execution') or {}).get('device')),
            'phase': event.get('interaction') or event.get('kind') or 'observed',
            'role': status,
            'source': source,
        })
    return rows


def _diagnosis_body(result):
    first = result.get('first_error') or {}
    reference = '{}:{}'.format(first.get('file', '未提供'), first.get('line', '未提供'))
    root = result.get('root_cause') or {}
    recommendation = (result.get('recommendations') or [{}])[0].get('action', '补齐缺失证据后重新诊断。')
    return ('# Diagnosis\n\n## 问题摘要\n\n'
            '自动诊断识别到 {}；当前证据不足以确认根因。\n\n'
            '## 关键证据链\n\n'
            '- `{}`：{}。\n'
            '- trace-skill 已作为诊断附属步骤执行；调用链只表示观测关系，不等于根因证明。\n\n'
            '## 根因分析\n\n'
            '根因状态为 `{}`。{}\n\n'
            '## 修复建议\n\n{}\n'.format(
                first.get('text', '未发现可定位的错误行'), reference,
                first.get('text', '未发现可定位的错误行'), root.get('status', 'undetermined'),
                root.get('description', '证据不足，无法定位根因。'), recommendation))


def _auto_diagnose(plan, state, artifact, work):
    detect, _ = read_artifact(plan.artifact('detect'))
    lookup, _ = read_artifact(plan.artifact('case_lookup'))
    detected = detect.get('result', {})
    lookup_result = lookup.get('result', {})
    errors = detected.get('errors') or lookup_result.get('errors') or []
    trace, trace_dir = _run_trace(plan, artifact, work)

    first = errors[0] if errors else None
    if first is not None:
        text = first.get('text', '')
        first_error = {
            'file': first.get('file'), 'line': first.get('line'), 'text': text,
            'timestamp': first.get('timestamp') or _timestamp(text),
            'entities': {
                'pid': _entity(text, r'\((\d+)[,)]'),
                'device': _entity(text, r'(?:device[_ ]?id|device)\s*[=:]\s*(\d+)'),
                'rank': _entity(text, r'\brank\s*[=:]?\s*(\d+)'),
            },
            'association': '最早可见错误候选；仍需跨来源核对首错与因果关系。',
        }
    else:
        first_error = None

    timeline = _trace_timeline(trace)
    if not timeline:
        for index, item in enumerate(errors):
            text = item.get('text', '')
            timeline.append({
                'id': 'error-{}'.format(index + 1),
                'time': item.get('timestamp') or _timestamp(text),
                'host': None, 'pid': _entity(text, r'\((\d+)[,)]'),
                'rank': _entity(text, r'\brank\s*[=:]?\s*(\d+)'),
                'device': _entity(text, r'(?:device[_ ]?id|device)\s*[=:]\s*(\d+)'),
                'phase': 'error', 'role': 'direct_trigger' if index == 0 else 'observed',
                'source': {'file': item.get('file'), 'line': item.get('line'), 'text': text},
            })

    trace_chain = (trace or {}).get('component_chain') if isinstance(trace, dict) else None
    causal_chain = []
    if isinstance(trace_chain, dict):
        for edge in trace_chain.get('edges', []):
            if not isinstance(edge, dict):
                continue
            causal_chain.append({
                'from': edge.get('source_component'), 'to': edge.get('target_component'),
                'support': edge.get('evidence_ids', []), 'counterevidence': [],
                'status': 'supported' if edge.get('strength') == 'proven' else 'unresolved',
            })

    source_files = {item.get('file') for item in errors if item.get('file')}
    materials = detected.get('materials') or {}
    trace_status = (trace or {}).get('status') if isinstance(trace, dict) else None
    gaps = list(detected.get('missing_materials') or [])
    if trace_status and trace_status != 'complete':
        gaps.append('trace status=' + str(trace_status))
    diagnostics = (trace or {}).get('diagnostics', {}) if isinstance(trace, dict) else {}
    gaps.extend(str(item) for item in diagnostics.get('gaps', []) if item)
    if not first_error:
        gaps.append('未发现可定位的错误行')
    artifact['evidence_gaps'].extend(item for item in gaps if item not in artifact['evidence_gaps'])

    def check(value, evidence):
        return {'value': bool(value), 'evidence': evidence or '未提供该项证据'}

    checks = {
        'has_first_error_line': check(bool(first_error), first_error and '{}:{}'.format(first_error['file'], first_error['line'])),
        'has_env_version': check(False, '未发现 CANN/Driver/Firmware/OS 版本证据。'),
        'has_full_timeline': check(bool(trace and trace_status == 'complete' and len(timeline) > 1), 'trace 事件数={}'.format(len(timeline))),
        'has_crash_artifacts': check(any(materials.get(key, {}).get('present') for key in ('coredump', 'stackcore')), '材料清单中的 coredump/stackcore'),
        'has_repro_input': check(False, '未提供复现输入。'),
        'multi_source_agree': check(len(source_files) > 1, '错误证据来源数={}'.format(len(source_files))),
        'timeline_consistent': check(bool(trace and trace_status == 'complete' and len(source_files) > 1), 'trace 状态与来源数'),
        'no_contradiction': check(True, '当前输入未发现互相矛盾的明确证据。'),
        'root_cause_localized': check(False, '自动诊断未把观测链升级为根因。'),
        'chain_no_gap': check(bool(causal_chain and all(item['status'] == 'supported' for item in causal_chain)), 'trace component_chain proven edges'),
        'alternatives_excluded': check(False, '竞争假设未被排除。'),
        'reproducible': check(False, '未提供稳定复现条件。'),
        'fix_verified': check(False, '未提供修复后验证。'),
        'regression_checked': check(False, '未提供回归验证。'),
        'errcode_documented': check(False, '错误码定义未由当前输入确认。'),
        'case_matched': check(lookup_result.get('status') == 'hit', 'case_lookup status={}'.format(lookup_result.get('status'))),
        'source_code_confirmed': check(False, '未提供源码定位证据。'),
    }
    root_description = ('已观察到首个错误并生成 trace，但 trace 只描述证据关系，'
                        '不能单独确认根因。' if first_error else
                        '当前材料没有可定位的错误行，无法确认根因。')
    references = (([{'kind': 'raw_log', 'path': first_error.get('file'), 'line': first_error.get('line'),
                     'why': '最早可见错误候选'}] if first_error else []) +
                  [{'kind': 'case_lookup', 'path': str(plan.artifact('case_lookup')), 'why': '案例检索结果'}])
    trace_path = trace_dir / 'fault-trace.json'
    if trace_path.is_file():
        references.append({'kind': 'trace', 'path': str(trace_path), 'why': 'trace-skill 附属证据'})
    result = {
        'first_error': first_error,
        'timeline': timeline,
        'causal_chain': causal_chain,
        'root_cause': {'description': root_description, 'status': 'undetermined',
                       'location': None,
                       'evidence': ([first_error.get('file') + ':' + str(first_error.get('line'))]
                                    if first_error else []),
                       'limitations': artifact['evidence_gaps']},
        'alternatives': [
            {'hypothesis': '运行时或设备侧故障', 'status': 'unresolved',
             'support': ['存在错误/异常日志'] if first_error else [],
             'counterevidence': ['缺少充分设备侧证据']},
            {'hypothesis': '应用或上游输入触发', 'status': 'unresolved',
             'support': ['错误出现在当前输入中'] if first_error else [],
             'counterevidence': ['缺少应用栈和复现输入']},
        ],
        'recommendations': [{'action': '补齐同一故障时间点的 device/runtime 日志、版本、stack/core 和复现条件，随后重新验证因果链。',
                             'evidence': ([first_error.get('file') + ':' + str(first_error.get('line'))]
                                          if first_error else []),
                             'status': 'recommended', 'expected_impact': '缩小根因候选并支持回归验证。'}],
        'checks': checks,
        'references': references,
    }
    if trace is not None:
        result['trace'] = {'status': trace.get('status'), 'event_count': len(trace.get('events', [])),
                           'component_chain': trace_chain or {}}
    artifact['result'] = result
    artifact['summary'] = '自动生成诊断和 trace 附属产物；根因状态为 undetermined。'
    artifact['next_action'] = '继续 confidence、promote 和 report 阶段。'
    return _diagnosis_body(result)


def _report_component_name(node):
    component = str(node.get('component') or 'unknown')
    catalog = component if component in {
        'Slog', 'IDEDD', 'SCC', 'HCCL', 'FMK', 'CCU', 'DVPP', 'Runtime', 'CCE', 'HDC',
        'DRV', 'NET', 'HIXI', 'DQSFW', 'Kernel', 'HCCP ROCE', 'TEFUSION', 'PROFILING',
        'User Application', 'Task Schedule', 'TSDUMP', 'AICPU', 'ASCENDCL', 'TBE',
        'OP', 'UDF', 'TPRT', 'ASYS', 'ATRACE', 'unknown'} else 'unknown'
    return catalog


def _build_report_data(plan, state, diagnosis, confidence, detect, trace, work):
    report_work = work / 'report-work'
    run_command([sys.executable, str(HTML_SCRIPT), '--init', str(report_work)],
                plan.params('report').get('timeout', 1800))
    data_path = report_work / 'report-data.json'
    data = json.loads(data_path.read_text(encoding='utf-8'))
    dresult = diagnosis.get('result', {})
    cresult = confidence.get('result', {})
    sresult = detect.get('result', {})
    first = dresult.get('first_error') or {}
    scenario = sresult.get('primary') or 'unknown'
    data['report'] = {'title': 'CANN 故障诊断报告 - ' + scenario, 'version': '自动生成'}
    data['overview'] = {
        'problem': first.get('text') or '未发现可定位的错误行',
        'scene': {'label': '运行场景', 'value': scenario,
                  'detail': sresult.get('recognition_confidence', 'UNKNOWN')},
        'incident': {'label': '发生问题', 'value': first.get('text') or '证据不足'},
        'impact': {'label': '业务影响', 'value': '当前材料未提供可量化业务影响。'},
        'first_error_note': (str(first.get('file')) + ':' + str(first.get('line'))
                             if first else '首错未确认'),
    }
    timeline = []
    for item in dresult.get('timeline', []):
        source = item.get('source') or {}
        timeline.append({
            'time': item.get('time') or '时间戳未提供',
            'source': '{}:{}'.format(source.get('file', '未提供'), source.get('line', '未提供')),
            'message': source.get('text') or item.get('phase') or '未提供',
            'status': item.get('role') if item.get('role') in {
                'root_cause', 'fault_source', 'direct_trigger', 'candidate',
                'propagation', 'affected', 'first_observed', 'observed', 'unknown'
            } else 'observed',
            'evidence_strength': 'proven',
        })
    data['timeline'] = timeline or [{'time': '时间戳未提供', 'source': '未提供',
                                     'message': '当前材料没有可定位事件。', 'status': 'unknown',
                                     'evidence_strength': 'unknown'}]
    data['critical_log'] = first.get('text') or '未提供'
    score = cresult.get('final_score')
    data['diagnosis'] = {
        'headline': dresult.get('root_cause', {}).get('description', '证据不足'),
        'detail': '；'.join(dresult.get('root_cause', {}).get('limitations', [])[:3]) or '未提供',
        'confidence': cresult.get('level', 'INSUFFICIENT'),
        'confidence_score': score if isinstance(score, int) else None,
        'confidence_display': '可信度 {}%'.format(score) if isinstance(score, int) else '可信度 未提供',
        'facts': [
            {'label': '首报', 'value': data['overview']['first_error_note']},
            {'label': '根因主体', 'value': dresult.get('root_cause', {}).get('description', '未提供')},
            {'label': '源卡证据', 'value': '；'.join(dresult.get('evidence_gaps', [])[:2]) or '未提供'},
            {'label': '客户可做', 'value': (dresult.get('recommendations') or [{}])[0].get('action', '未提供')},
        ],
    }
    data['evidence_chain'] = [
        {'title': '输入边界', 'detail': '；'.join(sresult.get('missing_materials', [])[:3]) or '已读取当前输入'},
        {'title': '首报', 'detail': data['overview']['first_error_note']},
        {'title': '直接触发', 'detail': dresult.get('root_cause', {}).get('description', '未提供')},
        {'title': '传播', 'detail': '{} 条 causal/trace 关系'.format(len(dresult.get('causal_chain', [])))},
        {'title': '结论边界', 'detail': '根因状态为 ' + str(dresult.get('root_cause', {}).get('status', 'undetermined'))},
    ]

    chain = trace.get('component_chain') if isinstance(trace, dict) else None
    chain_nodes = chain.get('nodes', []) if isinstance(chain, dict) else []
    chain_edges = chain.get('edges', []) if isinstance(chain, dict) else []
    component_nodes = []
    component_id = {}
    for index, node in enumerate(chain_nodes[:5]):
        if not isinstance(node, dict):
            continue
        component = str(node.get('component') or 'unknown')
        node_id = 'component-{}'.format(index + 1)
        component_id[component] = node_id
        status = {'direct-trigger': 'direct_trigger', 'propagation': 'propagation',
                  'affected': 'affected', 'observed': 'observed',
                  'business-error': 'affected', 'fault-source': 'affected'}.get(
                      node.get('fault_role'), 'observed')
        catalog = _report_component_name(node)
        title = str(node.get('summary') or component + ' event')
        if title == catalog:
            title += ' event'
        component_nodes.append({
            'id': node_id, 'status': status, 'evidence_strength': 'proven',
            'catalog_name': catalog, 'title': title, 'detail': str(node.get('summary_short') or title),
            'tag': component,
        })
    if not component_nodes:
        component_nodes = [{'id': 'component-entry', 'status': 'unknown', 'evidence_strength': 'unknown',
                            'catalog_name': 'unknown', 'title': '当前错误组件未提供',
                            'detail': '未提供', 'tag': '执行组件'}]
        component_id['unknown'] = 'component-entry'

    hardware_nodes = []
    hardware_seen = set()
    for item in dresult.get('timeline', []):
        device = item.get('device') or item.get('rank')
        if device is None:
            continue
        title = 'Device/rank ' + str(device)
        if title in hardware_seen:
            continue
        hardware_seen.add(title)
        hardware_nodes.append({'id': 'hardware-{}'.format(len(hardware_nodes) + 1),
                               'status': 'first_observed' if not hardware_nodes else 'observed',
                               'evidence_strength': 'proven', 'title': title,
                               'detail': item.get('source', {}).get('text', '未提供'), 'tag': 'Device/rank'})
    arch_edges = []
    for edge in chain_edges:
        if not isinstance(edge, dict):
            continue
        source = component_id.get(edge.get('source_component'))
        target = component_id.get(edge.get('target_component'))
        if not source or not target or source == target:
            continue
        if edge.get('strength') == 'proven':
            arch_edges.append({'from': source, 'to': target, 'kind': 'call',
                               'evidence_strength': 'proven', 'label': '调用/任务下发'})
        else:
            arch_edges.append({'from': source, 'to': target, 'kind': 'candidate',
                               'evidence_strength': 'candidate', 'label': '候选关系'})
    model_node = {'id': 'model-entry', 'status': 'unknown', 'evidence_strength': 'unknown',
                  'title': scenario + ' 执行流', 'detail': '当前输入未提供模型实体。', 'tag': '执行流'}
    data['architecture'] = {
        'wire_call_label': '调用/任务下发', 'wire_return_label': '错误上报/影响',
        'wire_dispatch_label': '调用/任务下发', 'wire_propagation_label': '错误上报/影响',
        'hardware_note': '硬件卡只表示日志中观察到的 Device/rank，不表示硬件根因。',
        'devices': [{'name': node['title'], 'role': node['tag'], 'detail': node['detail']} for node in hardware_nodes],
        'layers': [
            {'kind': 'model', 'label': '模型层', 'caption': '当前日志识别的执行入口', 'nodes': [model_node]},
            {'kind': 'component', 'label': '组件层', 'caption': 'trace-skill 观测到的组件', 'nodes': component_nodes},
            {'kind': 'hardware', 'label': '硬件层', 'caption': '日志明确出现的 Device/rank', 'nodes': hardware_nodes},
        ],
        'edges': arch_edges,
    }
    model_component = '执行流'
    component_name = component_nodes[0].get('catalog_name', 'unknown')
    remedy_component = hardware_nodes[0]['title'] if hardware_nodes else component_name
    data['remedies'] = [
        {'name': '补齐首报证据', 'layer': '组件层', 'component': component_name,
         'owner': '客户方', 'owner_detail': '华为方可指导执行', 'action': '补齐同一时间点日志与版本。',
         'timing': '立即 / 取证', 'timing_detail': '先补齐证据，再判断责任边界'},
        {'name': '核对故障实体', 'layer': '模型层', 'component': model_component,
         'owner': '华为方为主', 'owner_detail': '客户方配合补充现场', 'action': '核对调用关系与输入条件。',
         'timing': '补证后 / 诊断', 'timing_detail': '结论随新增证据更新'},
        {'name': '核验执行设备', 'layer': '硬件层' if hardware_nodes else '组件层', 'component': remedy_component,
         'owner': '华为方', 'owner_detail': '客户方配合升级验证', 'action': '核验设备日志和健康状态。',
         'timing': '定位后 / 候选修复', 'timing_detail': '验证前不得标记为根修复'},
        {'name': '执行回归验证', 'layer': '模型层', 'component': model_component,
         'owner': '客户方', 'owner_detail': '华为方确认故障是否消失', 'action': '覆盖原场景及必要压力回归。',
         'timing': '修复后 / 验证', 'timing_detail': '记录原场景与回归结果'},
    ]
    data['notices'] = {
        'caution': {'title': '风险提示', 'detail': '当前根因状态为 undetermined，不应直接据此修改硬件或算子。'},
        'verification': {'title': '验证状态', 'meta': '未验证', 'detail': '尚未提供修复后回归证据。'},
        'next_steps': {'title': '下一步', 'detail': '补齐 evidence gaps 后重新运行诊断。'},
    }
    atomic_write(data_path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return report_work, data_path, data


def _auto_report(plan, state, artifact, work):
    diagnosis, _ = read_artifact(plan.artifact('diagnose'))
    confidence, _ = read_artifact(plan.artifact('confidence'))
    detect, _ = read_artifact(plan.artifact('detect'))
    trace = diagnosis.get('result', {}).get('trace')
    trace_json = None
    for output in diagnosis.get('outputs', []):
        if output.get('kind') == 'fault_trace_json' and Path(output['path']).is_file():
            trace_json = Path(output['path'])
            break
    trace_data = None
    if trace_json:
        trace_data = json.loads(trace_json.read_text(encoding='utf-8'))
    report_work, data_path, data = _build_report_data(plan, state, diagnosis, confidence,
                                                      detect, trace_data, work)
    trace_for_report = None
    if trace_json:
        trace_for_report = report_work / 'fault-trace.json'
        shutil.copy2(trace_json, trace_for_report)
        attach(artifact, trace_for_report, 'fault_trace_json')
        for name, kind in (('tracing-report.html', 'trace_report_html'), ('fault-trace.html', 'fault_trace_html')):
            source = trace_json.parent / name
            if source.is_file():
                target = report_work / name
                shutil.copy2(source, target)
                attach(artifact, target, kind)
    output = report_work / 'diagnostic-report.html'
    argv = [sys.executable, str(HTML_SCRIPT), '--input', str(report_work / 'index.html'),
            '--data', str(data_path), '--output', str(output), '--force']
    if trace_for_report:
        argv.extend(['--trace', str(trace_for_report)])
    run_command(argv, plan.params('report').get('timeout', 1800))
    attach(artifact, data_path, 'report_data')
    attach(artifact, output, 'diagnostic_html')
    cresult = confidence.get('result', {})
    findings = [{'fact': item.get('source', {}).get('text', item.get('message', '未提供')),
                 'evidence': [str(item.get('source', {}).get('file', '未提供')) + ':' + str(item.get('source', {}).get('line', '未提供'))],
                 'strength': item.get('role', 'observed')} for item in diagnosis.get('result', {}).get('timeline', [])[:8]]
    if not findings:
        findings = [{'fact': '当前材料没有可定位的时间线事件，报告仅记录证据不足边界。',
                     'evidence': [str(plan.artifact('diagnose'))], 'strength': 'unknown'}]
    artifact['result'] = {
        'conclusion': data['diagnosis']['headline'],
        'confidence': cresult,
        'findings': findings,
        'recommendations': data['remedies'],
        'limitations': diagnosis.get('evidence_gaps', []),
    }
    artifact['summary'] = '自动生成 report.md、report-data.json 和 diagnostic-report.html。'
    artifact['next_action'] = '流水线已完成；HTML 与 trace 附属产物已写入 report 阶段工作目录。'
    return ('# Final report\n\n## 结论\n\n' + artifact['result']['conclusion'] +
            '\n\n## 可信度\n\n综合可信度为 {}/100（{}）。\n\n## 限制\n\n'.format(
                cresult.get('final_score', '未提供'), cresult.get('level', 'INSUFFICIENT')) +
            ('\n'.join('- ' + str(item) for item in artifact['result']['limitations']) or '- 未提供') + '\n')


_DEBUG_HEARTBEAT_RE = re.compile(r"^\s*(?:\[?DEBUG\]?\s*[:|]?[ \t]+)?(?:DEBUG\s+)?(?:heartbeat|polling|poll|tick)\b", re.I)


def conservative_clean(logs, output, audit, focus_level='DEBUG', encoding='utf-8'):
    """Preserve raw order and evidence while collapsing only duplicate heartbeats."""
    output = Path(output)
    audit = Path(audit)
    output.parent.mkdir(parents=True, exist_ok=True)
    audit.parent.mkdir(parents=True, exist_ok=True)
    policy = 'preserve_original_except_duplicate_debug_heartbeat'
    files = []
    input_lines = kept_lines = collapsed_lines = 0
    output_line = 0
    last_output_had_newline = True
    first_record = True
    with output.open('wb') as output_stream, audit.open('w', encoding='utf-8') as audit_stream:
        audit_stream.write('# Clean audit\n\n```json\n{"policy": ')
        json.dump(policy, audit_stream, ensure_ascii=False)
        audit_stream.write(', "records": [\n')
        for source in logs:
            source = Path(source)
            previous = None
            file_input = file_kept = file_collapsed = 0
            with source.open('rb') as source_stream:
                for number, line in enumerate(source_stream, 1):
                    text = line.rstrip(b'\r\n').decode(encoding, errors='replace')
                    input_lines += 1
                    file_input += 1
                    collapse = bool(previous == text and _DEBUG_HEARTBEAT_RE.search(text))
                    if collapse:
                        action, reason, line_output = 'collapsed', 'duplicate_debug_heartbeat', None
                        collapsed_lines += 1
                        file_collapsed += 1
                    else:
                        action, reason = 'kept', 'original_evidence'
                        if not last_output_had_newline:
                            output_stream.write(b'\n')
                        output_stream.write(line)
                        last_output_had_newline = line.endswith(b'\n')
                        output_line += 1
                        line_output = output_line
                        kept_lines += 1
                        file_kept += 1
                    record = {'source': str(source.resolve()), 'line': number,
                              'output': line_output, 'output_line': line_output,
                              'action': action, 'reason': reason,
                              'focus': focus_level, 'text': text}
                    audit_stream.write(('' if first_record else ',\n') +
                                       json.dumps(record, ensure_ascii=False))
                    first_record = False
                    previous = text
            files.append({'source': str(source.resolve()), 'sha256': file_hash(source),
                          'output': str(output.resolve()), 'input_lines': file_input,
                          'kept_lines': file_kept, 'collapsed_lines': file_collapsed})
        audit_stream.write('\n]}\n```\n')
    return {'mode': 'conservative', 'focus_level': focus_level, 'encoding': encoding,
            'ordering': 'original_line', 'processed_files': len(logs),
            'input_lines': input_lines, 'kept_lines': kept_lines,
            'collapsed_lines': collapsed_lines, 'files': files,
            'audit_path': str(audit.resolve()), 'source_map': str(audit.resolve()),
            'policy': policy}


def execute(sid, plan, state, artifact, work, inputs):
    if plan.params(sid).get('execution') == 'manual_equivalent':
        raise Blocked('Equivalent manual execution selected. Complete all original business fields and evidence requirements in this Markdown artifact, then --resume.')
    if sid in ('case_lookup', 'detect'):
        artifact['result'] = detector(sid, plan)
        artifact['summary'] = ('Case lookup: ' + str(artifact['result'].get('status')) if sid == 'case_lookup'
                               else 'Scenario: ' + str(artifact['result'].get('primary', 'unknown')))
        artifact['evidence_gaps'] = artifact['result'].get('limitations', artifact['result'].get('missing_materials', []))
        return ''
    if sid == 'clean':
        clean_source, logs, source_aliases = prepare_clean_input(plan, artifact, work)
        if not logs:
            artifact['result'] = {'applicability': 'not_applicable', 'input_files': artifact['inputs']['materials'],
                                  'cleaned_files': [], 'input_lines': 0, 'kept_lines': 0,
                                  'collapsed_lines': 0, 'audit_path': None, 'policy': 'preserve_original',
                                  'reason': 'No supported text logs; supplied binary artifacts remain available.'}
            artifact['summary'] = 'No text log applicable to cleaning; original materials retained for diagnosis.'
            return ''
        output = work / 'cleaned.log'
        audit = work / 'clean-audit.md'
        result = conservative_clean(logs, output, audit,
                                    focus_level=str(plan.params(sid).get('level', 'DEBUG')))
        result['applicability'] = 'applicable'
        result['input_files'] = [str(p) for p in logs]
        result['cleaned_files'] = [str(output.resolve())]
        if source_aliases:
            result['source_aliases'] = source_aliases
        artifact['result'] = result
        attach(artifact, output, 'cleaned_log')
        attach(artifact, audit, 'cleaning_audit')
        artifact['summary'] = ('Conservative clean completed for %d file(s): %d input lines, '
                               '%d kept, %d collapsed.' %
                               (result['processed_files'], result['input_lines'],
                                result['kept_lines'], result['collapsed_lines']))
        return '# Log cleaning\n\n' + artifact['summary'] + '\n'
    if sid == 'diagnose':
        return _auto_diagnose(plan, state, artifact, work)
    if sid == 'report':
        return _auto_report(plan, state, artifact, work)
    if sid == 'confidence':
        diagnosis, _ = read_artifact(plan.artifact('diagnose'))
        checks = diagnosis['result']['checks']
        if any(not isinstance(v if not isinstance(v, dict) else v.get('value'), bool) for v in checks.values()):
            raise StepError('Confidence check values must be Boolean, never strings or implicit truthy values')
        payload = {'meta': diagnosis['result'].get('meta', {}), 'checks': checks}
        checks_path = work / 'checks.json'
        atomic_write(checks_path, json.dumps(payload, ensure_ascii=False, indent=2))
        result = json.loads(run_command(child(sid) + ['--input', str(checks_path), '--json']))
        artifact['result'] = result
        artifact['summary'] = 'Confidence %s/100 (%s); case gate %s.' % (result['final_score'], result['level'], result['case_gate'])
        artifact['evidence_gaps'] = result.get('missing_items', [])
        return '# Confidence assessment\n\n' + artifact['summary']
    if sid == 'promote':
        return promote(plan, state, artifact, work)
    raise ValueError('Unknown stage ' + sid)


def mutation_write(path, data):
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))


def commit_candidate(source, target):
    temporary = target.with_name(target.name + '.tmp-' + uuid.uuid4().hex)
    try:
        with source.open('rb') as input_stream, temporary.open('xb') as output_stream:
            shutil.copyfileobj(input_stream, output_stream)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.replace(str(temporary), str(target))
    finally:
        if temporary.exists():
            temporary.unlink()


def promote(plan, state, artifact, work):
    params = plan.params('promote')
    confidence, _ = read_artifact(plan.artifact('confidence'))
    score = confidence['result']
    artifact['result'] = {'enabled': bool(params.get('enabled', False)), 'decision': 'skipped',
                          'case_gate': score['case_gate'], 'target': None, 'case_id': None,
                          'mutation_id': None, 'reason': ''}
    if not params.get('enabled', False) or score['case_gate'] == 'reject':
        artifact['status'] = 'skipped'
        artifact['summary'] = 'Promotion disabled in plan.' if not params.get('enabled', False) else 'Case gate rejects publication.'
        artifact['result']['reason'] = artifact['summary']
        return ''
    if not params.get('cases_dir'):
        raise Blocked('Enabled promotion requires an explicit cases_dir target in the plan.')
    cases_dir = Path(params['cases_dir'])
    if not cases_dir.is_absolute():
        cases_dir = plan.path.parent / cases_dir
    cases_dir = cases_dir.resolve()
    diagnosis, body = read_artifact(plan.artifact('diagnose'))
    operation = digest({'diagnosis': diagnosis['result'], 'confidence': score, 'target': str(cases_dir)})
    receipt_path = plan.state_dir / 'mutations' / (operation + '.json')
    artifact['result']['mutation_id'] = operation
    target = cases_dir / ('cases.md' if score['case_gate'] == 'accept' else 'cases-pending.md')
    artifact['result']['target'] = str(target)
    lock = acquire_lock(cases_dir)
    try:
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            if file_hash(target) == receipt['after_sha256']:
                receipt['status'] = 'committed'
                mutation_write(receipt_path, receipt)
                artifact['result'].update(decision='already_committed', reason='Existing mutation receipt verified.')
                artifact['result']['case_id'] = receipt.get('case_id')
                artifact['summary'] = 'Verified the prior case publication; no second write.'
                return ''
            raise Blocked('Publication receipt requires reconciliation; refusing a duplicate or uncertain write.')
        # The real promotion script operates on an isolated copy. Only one verified file is committed.
        staging = work / 'cases'
        staging.mkdir(parents=True, exist_ok=True)
        for name in ('cases.md', 'cases-pending.md'):
            source = cases_dir / name
            if source.is_file():
                shutil.copy2(source, staging / name)
        score_path, report_path = work / 'confidence.json', work / 'diagnosis.md'
        atomic_write(score_path, json.dumps(score, ensure_ascii=False))
        # Strip only the machine contract: the legacy script expects the diagnostic Markdown body.
        atomic_write(report_path, body)
        before = file_hash(target)
        try:
            stdout = run_command(child('promote') + ['--report', str(report_path), '--confidence', str(score_path),
                                                     '--cases-dir', str(staging)])
        except StepError as exc:
            if exc.code in (3, 4):
                artifact['result']['reason'] = str(exc)
                raise Blocked('Promotion needs report redaction or duplicate-case review: ' + str(exc)) from exc
            raise
        candidate = staging / target.name
        if not candidate.is_file():
            raise StepError('Promotion script did not produce a candidate case file')
        match = re.search(r'\[DONE\]\s+(P?CASE-\d+)', stdout)
        case_id = match.group(1) if match else None
        receipt = {'mutation_id': operation, 'run_id': state['run_id'], 'target': str(target),
                   'before_sha256': before, 'case_id': case_id,
                   'after_sha256': file_hash(candidate), 'status': 'prepared', 'at': now_iso()}
        mutation_write(receipt_path, receipt)
        if file_hash(target) != before:
            raise Blocked('Case library changed before commit; reconcile the prepared mutation.')
        commit_candidate(candidate, target)
        receipt['status'] = 'committed'
        mutation_write(receipt_path, receipt)
        artifact['result'].update(decision='committed', reason=stdout.strip(), case_id=case_id)
        artifact['summary'] = 'Case publication committed with a durable deduplication receipt.'
        return '# Case publication\n\n' + stdout
    finally:
        release_lock(lock)


def template_body(sid, artifact):
    if sid == 'diagnose':
        return ('# Diagnosis\n\n## 问题摘要\n\nDescribe only facts from supplied materials.\n\n'
                '## 关键证据链\n\nCite source path and line for each causal link.\n\n'
                '## 根因分析\n\nState confirmed root cause, or explicit unresolved hypotheses and evidence gaps.\n\n'
                '## 修复建议\n\nRecord recommendations and existing validation; do not invent verification.\n')
    if sid == 'report':
        return '# Final report\n\nFill the conclusion, confidence, evidence, recommendations and limitations.\n'
    return '# Equivalent execution work item\n\n' + artifact['next_action']


def generate_index(plan, state, stopped_at):
    """Write artifacts-index.md summarizing every stage's artifact, status, causal chain and hits."""
    lines = ['# 产物索引', '',
             '- run_id: ' + state['run_id'], '- state-dir: ' + str(plan.state_dir), '']
    lines.append('## 产物列表')
    lines.append('')
    lines.append('| step | 产物文件 | 状态 | owner_skill | 上游 | 摘要 |')
    lines.append('| --- | --- | --- | --- | --- | --- |')
    causal = []
    for sid in STAGE_IDS:
        stage = state['stages'][sid]
        art_path = plan.artifact(sid)
        fname = STAGE_FILES[sid]
        owner = OWNERS[sid]
        status = stage['status']
        summary = stage.get('summary', '')
        index = STAGE_IDS.index(sid)
        upstream = ', '.join(STAGE_IDS[:index]) if index > 0 else '—'
        exists = 'yes' if art_path.is_file() else 'no'
        lines.append('| {} | `artifacts/{}` ({}) | {} | {} | {} | {} |'.format(
            sid, fname, exists, status, owner, upstream, summary.replace('|', '/')[:80]))
        causal.append((sid, fname, status, [STAGE_IDS[:index]] if index > 0 else []))
    lines.append('')
    lines.append('## 因果链')
    lines.append('')
    lines.append('```text')
    for i, sid in enumerate(STAGE_IDS):
        if i == 0:
            lines.append('{} → {}'.format(STAGE_FILES[sid], STAGE_FILES[STAGE_IDS[i + 1]]))
        elif i < len(STAGE_IDS) - 1:
            lines.append('{} → {}'.format(STAGE_FILES[sid], STAGE_FILES[STAGE_IDS[i + 1]]))
    lines.append('```')
    lines.append('')
    lines.append('## 命中规则与场景识别')
    lines.append('')
    case_match_path = plan.artifact('case_lookup')
    scenario_path = plan.artifact('detect')
    if case_match_path.is_file():
        try:
            cm, _ = read_artifact(case_match_path, 'case_lookup', state['run_id'])
            result = cm.get('result', {})
            lines.append('- 案例库检索: {}'.format(result.get('status', 'unknown')))
            matches = result.get('matches', [])
            if matches:
                for m in matches:
                    lines.append('  - {} ({})'.format(m.get('case_id', '?'), m.get('title', '?')))
            else:
                lines.append('  - 无命中案例')
            lines.append('- 检索特征: {}'.format(json.dumps(result.get('query_features', {}), ensure_ascii=False)[:200]))
        except (OSError, ValueError, KeyError):
            lines.append('- 案例库检索: 读取失败')
    else:
        lines.append('- 案例库检索: 产物未生成')
    if scenario_path.is_file():
        try:
            sc, _ = read_artifact(scenario_path, 'detect', state['run_id'])
            result = sc.get('result', {})
            lines.append('- 主场景: {}'.format(result.get('primary', 'unknown')))
            lines.append('- 竞争场景: {}'.format(', '.join(result.get('secondary', [])) or '无'))
            lines.append('- 识别可信度: {}'.format(result.get('recognition_confidence', 'unknown')))
        except (OSError, ValueError, KeyError):
            lines.append('- 场景识别: 读取失败')
    else:
        lines.append('- 场景识别: 产物未生成')
    lines.append('')
    lines.append('## 诊断结论')
    lines.append('')
    diag_path = plan.artifact('diagnose')
    if diag_path.is_file():
        try:
            dg, _ = read_artifact(diag_path, 'diagnose', state['run_id'])
            result = dg.get('result', {})
            root = result.get('root_cause') or {}
            lines.append('- 根因状态: {}'.format(root.get('status', 'unknown')))
            lines.append('- 根因描述: {}'.format(root.get('description', '—')[:200]))
            conf_path = plan.artifact('confidence')
            if conf_path.is_file():
                cf, _ = read_artifact(conf_path, 'confidence', state['run_id'])
                cr = cf.get('result', {})
                lines.append('- 可信度: {}/100 ({})'.format(cr.get('final_score', '?'), cr.get('level', '?')))
                lines.append('- 入库判定: {}'.format(cr.get('case_gate', '?')))
        except (OSError, ValueError, KeyError):
            lines.append('- 诊断结论: 读取失败')
    else:
        lines.append('- 诊断结论: 产物未生成')
    lines.append('')
    if stopped_at:
        lines.append('> 流水线在 **{}** 步停止。使用 `--resume` 恢复。'.format(stopped_at))
    else:
        lines.append('> 流水线已全部完成。')
    index_path = plan.state_dir / 'artifacts-index.md'
    atomic_write(index_path, '\n'.join(lines) + '\n')
    return index_path


def finalize(plan, state, sid, artifact, body):
    artifact['finished_at'] = now_iso()
    write_artifact(plan.artifact(sid), artifact, body)
    stage = state['stages'][sid]
    stage.update(status=artifact['status'], inputs_fingerprint=artifact['inputs']['fingerprint'],
                 artifact_sha256=file_hash(plan.artifact(sid)), last_error=artifact['error'],
                 summary=artifact['summary'])
    save_state(plan, state)


def run_stage(sid, plan, state, args):
    previous = state['stages'][sid]
    inputs = inputs_for(sid, plan, state)
    candidate, body = None, ''
    try:
        candidate, body = read_current(sid, plan, state, inputs)
    except (OSError, ValueError, TypeError, KeyError):
        pass
    if candidate and previous['status'] in ('blocked', 'failed', 'running') and candidate['status'] in TERMINAL_OK:
        try:
            validate_business(sid, candidate)
        except (ValueError, TypeError, KeyError) as exc:
            body += '\n\nValidation: ' + str(exc)
        else:
            previous['attempts'] += 1
            candidate['attempt'] = previous['attempts']
            candidate['next_action'] = 'Validated equivalent executor output; continue the same pipeline.'
            finalize(plan, state, sid, candidate, body)
            return candidate['status']
    if candidate and previous['status'] == 'running' and candidate['status'] == 'running':
        candidate['status'] = 'failed'
        candidate['summary'] = 'Previous execution was interrupted before completion.'
        candidate['error'] = {'class': 'interrupted', 'code': None, 'message': candidate['summary']}
        candidate['next_action'] = 'Resume the same stage with preserved partial evidence.'
        finalize(plan, state, sid, candidate, body)
    if previous['status'] == 'blocked' and candidate and candidate['status'] == 'blocked':
        # Merely checking an unfinished work item does not create another attempt.
        return 'blocked'
    if previous['status'] == 'failed' and previous['last_error'] and \
            previous['last_error']['class'] not in ('transient', 'resource', 'interrupted'):
        return 'failed'
    while True:
        previous['attempts'] += 1
        artifact = new_artifact(sid, state['run_id'], previous['attempts'], inputs, plan.artifact(sid))
        if candidate:
            artifact['result'] = candidate['result']
            artifact['evidence_gaps'] = candidate['evidence_gaps']
        previous['status'] = 'running'
        previous['inputs_fingerprint'] = inputs['fingerprint']
        save_state(plan, state)
        write_artifact(plan.artifact(sid), artifact, body)
        work = plan.state_dir / 'internal' / sid / ('%04d' % previous['attempts'])
        work.mkdir(parents=True, exist_ok=True)
        try:
            body = execute(sid, plan, state, artifact, work, inputs) or body
            if artifact['status'] == 'running':
                artifact['status'] = 'success'
            validate_business(sid, artifact)
        except Blocked as exc:
            artifact['status'], artifact['summary'] = 'blocked', str(exc)
            artifact['next_action'] = str(exc)
            artifact['result'] = artifact['result'] or {key: ({} if key in ('checks', 'confidence') else
                [] if key in ('timeline', 'causal_chain', 'alternatives', 'recommendations', 'references',
                              'findings', 'limitations', 'errors') else None) for key in BUSINESS_FIELDS.get(sid, ())}
            if sid == 'diagnose' and not artifact['result'].get('checks'):
                artifact['result']['checks'] = {key: {'value': False, 'evidence': ''} for key in CHECK_KEYS}
            body = body or template_body(sid, artifact)
        except (Exception, KeyboardInterrupt) as exc:
            category = exc.category if isinstance(exc, StepError) else classify_error(exc)
            if isinstance(exc, KeyboardInterrupt):
                category = 'interrupted'
            artifact['status'], artifact['summary'] = 'failed', str(exc) or category
            artifact['error'] = {'class': category, 'code': getattr(exc, 'code', None), 'message': str(exc)}
            artifact['next_action'] = ('Resume the interrupted stage.' if category == 'interrupted' else
                'Retry while the execution resource is recoverable.' if category in ('transient', 'resource')
                else 'Resolve the execution failure and use --restart-from %s; retain the evidence standard.' % sid)
            if category != 'interrupted':
                previous['failures'] += 1
            # Preserve real partial outputs, including cleaning audits, in the failed Markdown record.
            for path in work.rglob('*'):
                if path.is_file() and path.suffix != '.json' and not any(o['path'] == str(path.resolve()) for o in artifact['outputs']):
                    attach(artifact, path, 'partial_output')
        finalize(plan, state, sid, artifact, body)
        if not args.json:
            print('[%s] %s: %s' % (artifact['status'], sid, artifact['summary']), flush=True)
        if artifact['status'] != 'failed':
            return artifact['status']
        error_class = artifact['error']['class']
        retryable = error_class in ('transient', 'resource')
        if not retryable:
            return 'failed'
        time.sleep(min(args.retry_delay * (2 ** (previous['failures'] - 1)), 30))
        candidate = artifact


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--plan', type=Path)
    result.add_argument('--state-dir', type=Path, default=Path('.cann-orchestrator'))
    modes = result.add_mutually_exclusive_group()
    modes.add_argument('--resume', action='store_true')
    modes.add_argument('--restart-from', choices=STAGE_IDS)
    modes.add_argument('--only', choices=STAGE_IDS)
    result.add_argument('--retry-delay', type=float, default=2.0)
    result.add_argument('--dry-run', action='store_true')
    result.add_argument('--status', action='store_true')
    result.add_argument('--json', action='store_true')
    result.add_argument('--force-unlock', action='store_true')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    if args.retry_delay < 0:
        raise ValueError('Retry values must be nonnegative')
    state_dir = args.state_dir.resolve()
    if args.status:
        if not (state_dir / 'state.json').exists():
            print('No pipeline state exists.', file=sys.stderr)
            return 2
        state = load_state(state_dir / 'state.json')
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if not args.plan:
        raise ValueError('--plan is required')
    plan = Plan(args.plan, state_dir)
    if args.dry_run:
        print(json.dumps({'pipeline': list(STAGE_IDS), 'state_dir': str(state_dir),
                          'artifacts': {sid: str(plan.artifact(sid)) for sid in STAGE_IDS},
                          'promotion_enabled': bool(plan.params('promote').get('enabled', False)),
                          'manual_stages': list(MANUAL)}, ensure_ascii=False, indent=2))
        return 0
    lock = None
    try:
        lock = acquire_lock(state_dir, args.force_unlock)
        existed = (state_dir / 'state.json').exists()
        state = load_state(state_dir / 'state.json')
        if existed and not (args.resume or args.restart_from or args.only):
            raise StepError('State already exists; use --resume, --restart-from or --only', 'conflict')
        selected = args.only or args.restart_from
        start = STAGE_IDS.index(selected) if selected else 0
        for earlier in STAGE_IDS[:start]:
            if not reusable(earlier, plan, state):
                raise StepError('Predecessor %s is not current; --resume from the earliest invalid stage.' % earlier,
                                'conflict')
        if selected:
            invalidate(state, selected)
        elif args.resume:
            for sid in STAGE_IDS:
                stage = state['stages'][sid]
                inputs = inputs_for(sid, plan, state)
                if stage['status'] in TERMINAL_OK and not reusable(sid, plan, state):
                    invalidate(state, sid)
                    break
                if stage['inputs_fingerprint'] and stage['inputs_fingerprint'] != inputs['fingerprint']:
                    invalidate(state, sid)
                    break
        save_state(plan, state)
        targets = [args.only] if args.only else STAGE_IDS[start:]
        status, stopped = 'success', None
        for sid in targets:
            if reusable(sid, plan, state):
                continue
            status = run_stage(sid, plan, state, args)
            if status not in TERMINAL_OK:
                stopped = sid
                break
        summary = {'ok': status in TERMINAL_OK, 'run_id': state['run_id'], 'stopped_at': stopped,
                   'status': status, 'state_file': str(state_dir / 'state.json'),
                   'stages': {sid: state['stages'][sid]['status'] for sid in STAGE_IDS},
                   'artifact_index': str(plan.state_dir / 'artifacts-index.md'),
                   'next_action': ('Complete the pending Markdown artifact, then --resume.' if status == 'blocked'
                                   else 'Review the failed stage artifact.' if status == 'failed' else '')}
        generate_index(plan, state, stopped)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if status in TERMINAL_OK else 2 if status == 'blocked' else 1
    except StepError as exc:
        print(str(exc), file=sys.stderr)
        return 3 if exc.category == 'conflict' else 1
    finally:
        release_lock(lock)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print('%s: %s' % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(2)
