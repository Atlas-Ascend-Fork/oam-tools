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
分析 kernel_details.csv，输出结构化 JSON 统计信息

用法:
  python analyze_kernels.py [-f FILE] [-s STEP] [-o OUTPUT] [-d DETAILS] [-m MD]

选项:
  -f, --file FILE    指定 CSV 文件路径 (默认: kernel_details.csv)
  -s, --step STEP    指定要输出详情的 step ID (默认: 自动选择非 warmup 代表 step)
  -o, --output FILE  输出 operators JSON 文件路径 (默认: kernels.json)
  -d, --details FILE 输出详细 operators JSON 文件路径 (包含 CSV 全部字段)
  -m, --markdown FILE 输出统计摘要 Markdown 文件路径 (不指定则不生成)
  -h, --help         显示帮助信息
"""
import csv
import json
import sys
import argparse
import os
import math
from collections import defaultdict

REQUIRED_COLUMNS = ['Step Id', 'Name', 'Duration(us)', 'Start Time(us)', 'Stream ID']

IGNORED_COLUMNS = {'Step Id'}

METRIC_COLUMN_PATTERNS = [
    'duration', 'time', 'cycles', 'ratio', 'utilization',
    'fops', 'rate', 'miss', 'count', 'num', 'dim', 'id'
]

VALUE_COLUMN_PATTERNS = [
    'name', 'type', 'state', 'core', 'shapes', 'formats',
    'eligible', 'formats', 'context'
]

FLOAT_SUFFIXES = ['(us)', '(%)']


def is_metric_column(col_name):
    col_lower = col_name.lower()
    for pattern in METRIC_COLUMN_PATTERNS:
        if pattern in col_lower:
            return True
    return False


def is_value_column(col_name):
    col_lower = col_name.lower()
    for pattern in VALUE_COLUMN_PATTERNS:
        if pattern in col_lower:
            return True
    return False


def parse_column_value(value, col_name, json_key=None):
    value = value.strip().rstrip('\t')
    if not value or value == 'N/A':
        return None

    col_lower = col_name.lower()

    for suffix in FLOAT_SUFFIXES:
        if col_lower.endswith(suffix.lower()) or suffix.lower() in col_lower:
            try:
                return float(value)
            except (ValueError, AttributeError):
                return value

    if is_metric_column(col_name):
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except (ValueError, AttributeError):
            return value

    try:
        if '.' in value:
            fval = float(value)
            return fval if fval != int(fval) else int(fval)
        return int(value)
    except (ValueError, AttributeError):
        pass

    return value


def csv_col_name_to_json_key(col_name):
    key = col_name.lower()
    key = key.replace('(us)', '_us')
    key = key.replace('(%)', '_pct')
    key = key.replace(' ', '_')
    key = key.replace('(', '')
    key = key.replace(')', '')
    return key


class ValidationError(Exception):
    pass


class ConsistencyError(Exception):
    pass


def _step_sort_key(step_id):
    return int(step_id) if str(step_id).isdigit() else str(step_id)


def _kernel_signature(summary):
    return (
        summary['kernel_count'],
        tuple(sorted(summary['kernel_types'].items())),
    )


def choose_representative_step(steps_summary):
    """
    Choose a stable non-warmup step when the caller does not specify -s.

    Policy:
    1. Group steps by kernel_count + exact kernel type distribution.
    2. Use the largest group, preferring groups with more kernels on ties.
    3. Treat the earliest step in that group as warmup only if its kernel_sum is
       a clear outlier versus the later steps.
    4. If warmup is skipped, choose the remaining step whose kernel_sum is
       closest to the later-step median; otherwise choose the earliest stable
       step to keep behavior deterministic and close to user-visible traces.

    This avoids picking first-step warmup/outlier traces such as decode step 10
    when later steps have the same structure but stable duration.
    """
    if not steps_summary:
        return None, 'no steps available'
    if len(steps_summary) == 1:
        return steps_summary[0]['step_id'], 'single step available'

    groups = defaultdict(list)
    for item in steps_summary:
        groups[_kernel_signature(item)].append(item)

    def group_rank(items):
        first_key = _step_sort_key(items[0]['step_id'])
        first_rank = -first_key if isinstance(first_key, int) else 0
        return (len(items), items[0]['kernel_count'], first_rank)

    selected_group = max(groups.values(), key=group_rank)
    ordered = sorted(selected_group, key=lambda x: _step_sort_key(x['step_id']))
    later = ordered[1:]
    skip_earliest = False
    later_median = None
    if later:
        later_durations = sorted(x['total_duration_us'] for x in later)
        later_mid = len(later_durations) // 2
        later_median = (
            later_durations[later_mid]
            if len(later_durations) % 2
            else (later_durations[later_mid - 1] + later_durations[later_mid]) / 2
        )
        first_duration = ordered[0]['total_duration_us']
        if later_median > 0:
            ratio = first_duration / later_median
            skip_earliest = ratio > 1.5 or ratio < 0.67

    candidates = later if skip_earliest else [ordered[0]]

    durations = sorted(x['total_duration_us'] for x in candidates)
    mid = len(durations) // 2
    median = durations[mid] if len(durations) % 2 else (durations[mid - 1] + durations[mid]) / 2
    selected = min(
        candidates,
        key=lambda x: (abs(x['total_duration_us'] - median), _step_sort_key(x['step_id']))
    )

    skipped = ordered[0]['step_id'] if skip_earliest else None
    if skip_earliest:
        reason = (
            f'auto-selected non-warmup step {selected["step_id"]}: '
            f'largest stable kernel signature group size={len(ordered)}, '
            f'skipped earliest warmup/outlier candidate={skipped}, '
            f'duration_us={selected["total_duration_us"]}, '
            f'later_median_us={round(later_median, 1)}'
        )
    else:
        reason = (
            f'auto-selected stable step {selected["step_id"]}: '
            f'largest stable kernel signature group size={len(ordered)}, '
            f'earliest candidate is not a duration outlier, '
            f'duration_us={selected["total_duration_us"]}'
        )
    return selected['step_id'], reason


def mark_duplicate_collective_records(kernels: list) -> int:
    """Flag the second record of each collective that msprof reports twice.

    A collective op appears as two rows with an identical (Start Time, Duration) and
    `Accelerator Core = COMMUNICATION`: one communication record with no Stream/Task ID, and
    one row for the AIV kernel that executes it on a real stream. They are the same device
    work, so summing both counts it twice. On a tp8 LongCat capture this inflated
    `kernel_sum` by 48% and let a single 73 ms all-reduce claim 95% of the step.

    The two rows are kept — both are real profiler output, and dropping one would break
    op-index continuity that every downstream `op_indices` depends on. Instead the second is
    marked `duplicate_of` and excluded from duration totals. The communication record is kept
    as the primary because it carries the collective's name; the AIV row is the duplicate.

    Pairing requires an exact timestamp and duration match plus exactly one record without
    a Stream ID and one record on a real stream. Two genuinely concurrent collectives on
    different streams keep both durations. Larger or otherwise ambiguous groups are kept
    because a timestamp/duration match alone does not prove they describe the same work.
    """
    by_key = {}
    for op in kernels:
        valid_times = op.pop('_dedup_times_valid', True)
        if str(op.get('accelerator_core', '')).upper() != 'COMMUNICATION':
            continue
        if not valid_times:
            continue
        key = (op.get('start_time_us'), op.get('duration_us'))
        by_key.setdefault(key, []).append(op)

    duplicates = 0
    for group in by_key.values():
        if len(group) != 2:
            continue
        summaries = [op for op in group if str(op.get('stream_id') or '').strip().upper() in ('', 'N/A')]
        if len(summaries) != 1:
            continue
        # Only an unambiguous summary/kernel pair proves duplicate device work.
        primary = summaries[0]
        for op in group:
            if op is primary:
                continue
            op['duplicate_of'] = primary['index']
            op['duplicate_reason'] = (
                'msprof records one collective twice: a COMMUNICATION entry and the AIV kernel '
                'executing it, with identical start and duration. Counted once in totals.'
            )
            duplicates += 1
    return duplicates


def validate_file(file_path):
    if not os.path.exists(file_path):
        raise ValidationError(f'错误: 文件不存在: {file_path}')
    if not os.path.isfile(file_path):
        raise ValidationError(f'错误: 路径不是文件: {file_path}')
    if not os.access(file_path, os.R_OK):
        raise ValidationError(f'错误: 文件不可读: {file_path}')


def validate_csv_structure(fieldnames):
    missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
    if missing:
        raise ValidationError(
            f'错误: CSV 文件缺少必需列\n'
            f'缺少的列: {", ".join(missing)}\n'
            f'当前的列: {", ".join(fieldnames)}'
        )


def get_safe_value(row, key, default=''):
    return row.get(key, default).strip().rstrip('\t')


def parse_float(value, required=False):
    """Require valid duration values while preserving optional start timestamps."""
    try:
        number = float(value.strip().rstrip('\t'))
    except (ValueError, AttributeError) as error:
        if required:
            raise ValidationError(f'Invalid required time value: {value!r}') from error
        return 0.0
    if required and (not math.isfinite(number) or number < 0):
        raise ValidationError(f'Invalid required time value: {value!r}')
    return number


def is_finite_csv_number(value):
    """A missing/invalid CSV time is not evidence of duplicate device work."""
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError):
        return False


def extract_kernel_type(name):
    if not name:
        return 'Unknown'

    if '/' in name:
        return name

    if '_' not in name:
        return name

    parts = name.split('_')

    while parts and parts[-1].isdigit():
        parts.pop()

    if not parts:
        return name

    last_part = parts[-1]
    if last_part and last_part[0].isupper() and not last_part.isdigit():
        return last_part

    return '_'.join([p for p in parts if p])


def parse_args():
    parser = argparse.ArgumentParser(
        description='分析 kernel_details.csv，输出结构化 JSON 统计信息',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '-f', '--file',
        default='kernel_details.csv',
        help='指定 CSV 文件路径 (默认: kernel_details.csv)'
    )
    parser.add_argument(
        '-s', '--step',
        type=int,
        default=None,
        help='指定要输出详情的 step ID (默认: 自动选择非 warmup 代表 step)'
    )
    parser.add_argument(
        '-o', '--output',
        default='kernels.json',
        help='输出 operators JSON 文件路径 (默认: kernels.json)'
    )
    parser.add_argument(
        '-d', '--details',
        default=None,
        help='输出详细 operators JSON 文件路径 (包含 CSV 全部字段)'
    )
    parser.add_argument(
        '-m', '--markdown',
        default=None,
        help='输出统计摘要 Markdown 文件路径 (不指定则不生成)'
    )
    parser.add_argument(
        '--compact-out',
        default=None,
        dest='compact_out',
        help='输出 Step 2 投喂用的精简 JSON 路径 (删除 start_time_us/duration_us，连续相同算子折叠)'
    )
    parser.add_argument(
        '--allow-step-variation',
        action='store_true',
        help='允许 Step 间 Kernel 签名不同，并从最大稳定签名组自动选择代表 Step'
    )
    parser.add_argument(
        '--enrich',
        action='store_true',
        default=False,
        help='enrich 模式：将 raw_ops.json 数据内嵌到 analysis_config.json'
    )
    parser.add_argument(
        '-c', '--config',
        default=None,
        help='[enrich 模式] analysis_config.json 路径'
    )
    parser.add_argument(
        '-r', '--raw-ops',
        default=None,
        dest='raw_ops',
        help='[enrich 模式] raw_ops.json 路径'
    )
    return parser.parse_args()


def check_consistency(steps_summary):
    if len(steps_summary) <= 1:
        return

    first_types = None
    first_step = None

    for s in steps_summary:
        if first_types is None:
            first_types = s['kernel_types']
            first_step = s['step_id']
        elif s['kernel_types'] != first_types:
            diff_kernels = []
            all_keys = set(first_types.keys()) | set(s['kernel_types'].keys())
            for k in sorted(all_keys):
                v1 = first_types.get(k, 0)
                v2 = s['kernel_types'].get(k, 0)
                if v1 != v2:
                    diff_kernels.append(f'  {k}: Step {first_step}={v1}, Step {s["step_id"]}={v2}')

            raise ConsistencyError(
                f'错误: 各 Step 的 Kernel 分布不一致\n'
                f'差异:\n' + '\n'.join(diff_kernels[:10]) +
                (f'\n  ... 还有 {len(diff_kernels) - 10} 个差异' if len(diff_kernels) > 10 else '')
            )


def analyze_kernels(csv_file, detail_step_id=None, allow_step_variation=False):
    validate_file(csv_file)

    steps_data = defaultdict(lambda: {
        'kernels': [],
        'kernels_details': [],
        'total_duration': 0.0,
        'kernel_types': defaultdict(int),
        'all_columns': []
    })

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                raise ValidationError('错误: CSV 文件为空或格式不正确')
            validate_csv_structure(reader.fieldnames)

            all_columns = [col for col in reader.fieldnames if col not in IGNORED_COLUMNS]

            row_count = 0
            for row_num, row in enumerate(reader, start=2):
                try:
                    step_id = get_safe_value(row, 'Step Id')
                    if not step_id:
                        continue

                    name = get_safe_value(row, 'Name')
                    kernel_type = extract_kernel_type(name)
                    try:
                        duration = parse_float(get_safe_value(row, 'Duration(us)'), required=True)
                    except ValidationError as error:
                        raise ValidationError(
                            f'错误: {csv_file} 第 {row_num} 行 Duration(us): {error}'
                        ) from error
                    accelerator_core = (get_safe_value(row, 'Accelerator Core')
                                        if 'Accelerator Core' in row else '')

                    op_info = {
                        'index': len(steps_data[step_id]['kernels']),
                        'org_index': row_num - 2,
                        'original_name': name,
                        'normalized_name': kernel_type,
                        'duration_us': duration,
                        'start_time_us': parse_float(get_safe_value(row, 'Start Time(us)')),
                        'stream_id': get_safe_value(row, 'Stream ID'),
                        'accelerator_core': accelerator_core,
                        'task_type': get_safe_value(row, 'Type') if 'Type' in row else '',
                        'input_shapes': get_safe_value(row, 'Input Shapes').strip('"') if 'Input Shapes' in row else '',
                        'output_shapes': get_safe_value(row, 'Output Shapes').strip('"') if 'Output Shapes' in row else ''
                    }
                    op_info['_dedup_times_valid'] = all(
                        is_finite_csv_number(get_safe_value(row, column))
                        for column in ('Start Time(us)', 'Duration(us)')
                    )

                    detail_info = {'index': op_info['index'], 'org_index': op_info['org_index']}
                    for col in all_columns:
                        if col in IGNORED_COLUMNS:
                            continue
                        json_key = csv_col_name_to_json_key(col)
                        raw_value = get_safe_value(row, col)
                        if raw_value:
                            detail_info[json_key] = parse_column_value(raw_value, col, json_key)
                            if json_key in ('start_time_us', 'duration_us'):
                                detail_info[f'{json_key}_raw'] = raw_value
                    for key in ('input_shapes', 'output_shapes'):
                        if key in detail_info and isinstance(detail_info[key], str):
                            detail_info[key] = detail_info[key].strip('"')

                    steps_data[step_id]['kernels'].append(op_info)
                    steps_data[step_id]['kernels_details'].append(detail_info)
                    steps_data[step_id]['total_duration'] += duration
                    steps_data[step_id]['kernel_types'][kernel_type] += 1
                    steps_data[step_id]['all_columns'] = all_columns
                    row_count += 1

                except ValidationError:
                    raise
                except Exception as e:
                    sys.stderr.write(f'警告: 第 {row_num} 行数据解析失败: {e}\n')

            if row_count == 0:
                raise ValidationError('错误: CSV 文件没有有效数据行')

    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f'错误: 解析 CSV 文件失败: {e}')

    # A collective reported twice must not be counted twice. Do this per step, after every row
    # is parsed, so pairing sees the whole step and `total_duration` reflects real device work.
    for data in steps_data.values():
        data['duplicate_collective_count'] = mark_duplicate_collective_records(data['kernels'])
        duplicate_indices = {op['index'] for op in data['kernels'] if 'duplicate_of' in op}
        if duplicate_indices:
            data['total_duration'] = sum(op['duration_us'] for op in data['kernels']
                                         if op['index'] not in duplicate_indices)
            for detail in data['kernels_details']:
                if detail['index'] in duplicate_indices:
                    detail['duplicate_of'] = next(
                        op['duplicate_of'] for op in data['kernels']
                        if op['index'] == detail['index'])

    sorted_steps = sorted(steps_data.keys(), key=lambda x: int(x) if x.isdigit() else x)

    result = {
        'step_count': len(steps_data),
        'steps_summary': [],
        'csv_columns': all_columns
    }

    for step_id in sorted_steps:
        data = steps_data[step_id]
        result['steps_summary'].append({
            'step_id': step_id,
            'total_duration_us': round(data['total_duration'], 1),
            'duplicate_collective_count': data.get('duplicate_collective_count', 0),
            'kernel_count': len(data['kernels']),
            'kernel_types_count': len(data['kernel_types']),
            'kernel_types': dict(sorted(data['kernel_types'].items(),
                                        key=lambda x: -x[1]))
        })

    if not allow_step_variation:
        check_consistency(result['steps_summary'])

    if detail_step_id is None:
        detail_step_id, selection_reason = choose_representative_step(result['steps_summary'])
        result['selected_step_reason'] = selection_reason
    else:
        result['selected_step_reason'] = f'user-specified step {detail_step_id}'

    if detail_step_id is not None:
        str_step_id = str(detail_step_id)
        if str_step_id in steps_data:
            data = steps_data[str_step_id]
            result['selected_step_operators'] = {
                'step_id': str_step_id,
                'selection_reason': result.get('selected_step_reason', ''),
                'total_duration_us': round(data['total_duration'], 1),
                'duplicate_collective_count': data.get('duplicate_collective_count', 0),
                'kernel_count': len(data['kernels']),
                'kernel_types_count': len(data['kernel_types']),
                'kernel_types': dict(sorted(data['kernel_types'].items(),
                                            key=lambda x: -x[1])),
                'operators': data['kernels']
            }
            result['selected_step_operators_details'] = {
                'step_id': str_step_id,
                'selection_reason': result.get('selected_step_reason', ''),
                'total_duration_us': round(data['total_duration'], 1),
                'duplicate_collective_count': data.get('duplicate_collective_count', 0),
                'kernel_count': len(data['kernels']),
                'kernel_types_count': len(data['kernel_types']),
                'kernel_types': dict(sorted(data['kernel_types'].items(),
                                            key=lambda x: -x[1])),
                'csv_columns': data['all_columns'],
                'operators': data['kernels_details']
            }
        else:
            available = list(sorted_steps)
            raise ValidationError(
                f'错误: Step {detail_step_id} 不存在\n'
                f'可用的 Step: {", ".join(available)}'
            )

    return result, sorted_steps


def build_compact_view(operators_block: dict) -> dict:
    """
    将 selected_step_operators 视图压缩为 Step 2 投喂的精简版本：
    - 删除 start_time_us（Step 2 不需要时间）
    - 删除 original_name、duration_us（Step 2 用 normalized_name 即可）
    - 仅保留：index、org_index、normalized_name、stream_id、task_type、input_shapes、output_shapes
    - 连续相同 (normalized_name, stream_id, task_type, input_shapes, output_shapes) 块折叠为：
        {repeat: true, normalized_name, stream_id, task_type, input_shapes, output_shapes,
         first_index, last_index, first_org_index, count}
      非连续或单个不折叠。
    """
    keep_fields = ('index', 'org_index', 'normalized_name', 'stream_id',
                   'task_type', 'input_shapes', 'output_shapes')

    src_ops = operators_block.get('operators', [])
    compact_ops = []

    def signature(op):
        return (
            op.get('normalized_name', ''),
            op.get('stream_id', ''),
            op.get('task_type', ''),
            op.get('input_shapes', ''),
            op.get('output_shapes', ''),
        )

    i = 0
    n = len(src_ops)
    while i < n:
        sig = signature(src_ops[i])
        j = i + 1
        while j < n and signature(src_ops[j]) == sig:
            j += 1
        run_len = j - i
        if run_len >= 3:
            head = src_ops[i]
            tail = src_ops[j - 1]
            compact_ops.append({
                'repeat': True,
                'normalized_name': head.get('normalized_name', ''),
                'stream_id': head.get('stream_id', ''),
                'task_type': head.get('task_type', ''),
                'input_shapes': head.get('input_shapes', ''),
                'output_shapes': head.get('output_shapes', ''),
                'first_index': head.get('index'),
                'last_index': tail.get('index'),
                'first_org_index': head.get('org_index'),
                'count': run_len,
            })
        else:
            for k in range(i, j):
                op = src_ops[k]
                compact_ops.append({f: op.get(f) for f in keep_fields if f in op})
        i = j

    return {
        'step_id': operators_block.get('step_id'),
        'kernel_count': operators_block.get('kernel_count'),
        'kernel_types_count': operators_block.get('kernel_types_count'),
        'kernel_types': operators_block.get('kernel_types', {}),
        'compact_operator_count': len(compact_ops),
        'note': 'compact view for Step 2: timing fields removed; consecutive identical ops folded as {repeat:true,...,count}',
        'operators': compact_ops,
    }


def generate_markdown(result, csv_file):
    lines = []
    lines.append(f'# Kernel Analysis Summary')
    lines.append(f'')
    lines.append(f'**Source File:** `{os.path.basename(csv_file)}`')
    lines.append(f'')
    lines.append(f'---')
    lines.append(f'')

    lines.append(f'## Overview')
    lines.append(f'')
    lines.append(f'| Step ID | Kernel Count | Kernel Types | Total Duration (us) |')
    lines.append(f'|---------|--------------|--------------|---------------------|')
    for s in result['steps_summary']:
        lines.append(f'| {s["step_id"]} | {s["kernel_count"]} | {s["kernel_types_count"]} | {s["total_duration_us"]} |')
    lines.append(f'')
    if result.get('selected_step_reason'):
        lines.append(f'**Selected step:** {result.get("selected_step_reason")}')
        lines.append(f'')

    lines.append(f'---')
    lines.append(f'')
    lines.append(f'## Kernel Types Distribution')
    lines.append(f'')
    lines.append(f'### Steps {", ".join([s["step_id"] for s in result["steps_summary"]])}')
    lines.append(f'')
    lines.append(f'| Kernel Name | Count |')
    lines.append(f'|-------------|-------|')

    first_types = result['steps_summary'][0]['kernel_types']
    for ktype, count in first_types.items():
        lines.append(f'| {ktype} | {count} |')
    lines.append(f'')

    return '\n'.join(lines)


def _is_empty_value(v) -> bool:
    return v is None or v == '' or str(v).strip().upper() == 'N/A'


def _format_shape_pair(input_shapes: str, output_shapes: str) -> str:
    ins = str(input_shapes).strip('"') if not _is_empty_value(input_shapes) else ''
    outs = str(output_shapes).strip('"') if not _is_empty_value(output_shapes) else ''
    parts = []
    if ins:
        parts.append(f'[{ins}]')
    if outs:
        parts.append(f'[{outs}]')
    return '→'.join(parts) if parts else ''


def enrich_analysis_config(config: dict, operators: list) -> dict:
    import copy
    config = copy.deepcopy(config)
    op_dict = {op['index']: op for op in operators}

    def collect_kernels_semantics(node: dict) -> dict:
        result = {}
        for ks in node.get('kernels', []):
            idx = ks.get('index')
            if idx is not None:
                entry = {}
                for field in ('semantic', 'shape_semantic', 'code_ref'):
                    val = ks.get(field, '')
                    if val:
                        entry[field] = val
                if entry:
                    result[idx] = entry
        return result

    def enrich_node(node: dict) -> dict:
        kernel_sem = collect_kernels_semantics(node)

        if 'op_indices' in node:
            op_data = []
            for idx in node['op_indices']:
                op = op_dict.get(idx)
                if op is None:
                    continue
                entry = {
                    'index': op.get('index', idx),
                    'org_index': op.get('org_index', -1),
                    'name': op.get('normalized_name') or op.get('name', 'Unknown'),
                    'duration_us': op.get('duration_us', 0),
                    'stream_id': op.get('stream_id', ''),
                    'task_type': op.get('task_type', ''),
                    'input_shapes': op.get('input_shapes', ''),
                    'output_shapes': op.get('output_shapes', ''),
                }
                shape_sem = _format_shape_pair(entry['input_shapes'], entry['output_shapes'])
                if shape_sem:
                    entry['shape_raw'] = shape_sem
                sem_info = kernel_sem.get(idx, {})
                for field in ('semantic', 'shape_semantic', 'code_ref'):
                    if field in sem_info:
                        entry[field] = sem_info[field]
                entry = {k: v for k, v in entry.items()
                         if not _is_empty_value(v) and v != -1}
                if 'index' not in entry:
                    entry['index'] = idx
                op_data.append(entry)
            node['op_data'] = op_data

        if 'kernels' in node:
            for ks in node['kernels']:
                idx = ks.get('index')
                op = op_dict.get(idx) if idx is not None else None
                if op:
                    if 'name' not in ks:
                        ks['name'] = op.get('normalized_name') or op.get('name', 'Unknown')
                    if 'org_index' not in ks:
                        ks['org_index'] = op.get('org_index', -1)
                    if 'duration_us' not in ks:
                        ks['duration_us'] = op.get('duration_us', 0)
                    if 'input_shapes' not in ks:
                        ks['input_shapes'] = op.get('input_shapes', '')
                    if 'output_shapes' not in ks:
                        ks['output_shapes'] = op.get('output_shapes', '')
                    if 'shape_raw' not in ks:
                        shape_sem = _format_shape_pair(
                            op.get('input_shapes', ''), op.get('output_shapes', ''))
                        if shape_sem:
                            ks['shape_raw'] = shape_sem

        for child in node.get('children', []):
            enrich_node(child)

        return node

    for stage_name, stage_info in config.get('stages', {}).items():
        config['stages'][stage_name] = enrich_node(stage_info)

    for layer_type, structure in config.get('layer_structure', {}).items():
        config['layer_structure'][layer_type] = enrich_node(structure)

    # schema v2 renamed representative layer templates to `structures`.
    for layer_type, structure in config.get('structures', {}).items():
        config['structures'][layer_type] = enrich_node(structure)

    for i, aux in enumerate(config.get('runtime_auxiliary', [])):
        config['runtime_auxiliary'][i] = enrich_node(aux)

    return config


def enrich_main(args):
    config_path = args.config
    raw_ops_path = args.raw_ops
    output_path = args.output if args.output != 'kernels.json' else config_path

    if not os.path.exists(config_path):
        sys.stderr.write(f'错误: 配置文件不存在: {config_path}\n')
        sys.exit(1)
    if not os.path.exists(raw_ops_path):
        sys.stderr.write(f'错误: raw_ops 文件不存在: {raw_ops_path}\n')
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open(raw_ops_path, 'r', encoding='utf-8') as f:
        raw_ops = json.load(f)

    operators = raw_ops.get('operators', [])
    enriched = enrich_analysis_config(config, operators)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)
    print(f'Enriched config 已保存到: {output_path}')


def main():
    args = parse_args()
    if getattr(args, 'enrich', False):
        enrich_main(args)
        return

    try:
        result, sorted_steps = analyze_kernels(
            args.file, args.step, allow_step_variation=args.allow_step_variation
        )

        if 'selected_step_operators' in result:
            operators_json = result['selected_step_operators']
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(operators_json, f, indent=2, ensure_ascii=False)
            print(f'Operators JSON 已保存到: {args.output}')

        if args.details and 'selected_step_operators_details' in result:
            details_json = result['selected_step_operators_details']
            with open(args.details, 'w', encoding='utf-8') as f:
                json.dump(details_json, f, indent=2, ensure_ascii=False)
            print(f'Details JSON 已保存到: {args.details}')

        if args.compact_out and 'selected_step_operators' in result:
            compact_json = build_compact_view(result['selected_step_operators'])
            with open(args.compact_out, 'w', encoding='utf-8') as f:
                json.dump(compact_json, f, indent=2, ensure_ascii=False)
            src_n = compact_json['kernel_count']
            cmp_n = compact_json['compact_operator_count']
            saved = (1 - cmp_n / src_n) * 100 if src_n else 0
            print(f'Compact JSON 已保存到: {args.compact_out} '
                  f'(原 {src_n} 算子 → {cmp_n} 条目，折叠率 {saved:.1f}%)')

        if args.markdown:
            markdown_content = generate_markdown(result, args.file)
            with open(args.markdown, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print(f'Summary Markdown 已保存到: {args.markdown}')

    except ValidationError as e:
        sys.stderr.write(str(e) + '\n')
        sys.exit(1)
    except ConsistencyError as e:
        sys.stderr.write(str(e) + '\n')
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f'错误: 未知错误: {e}\n')
        sys.exit(1)


if __name__ == '__main__':
    main()
