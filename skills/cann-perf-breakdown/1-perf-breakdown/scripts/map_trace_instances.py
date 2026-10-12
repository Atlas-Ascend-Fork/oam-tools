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
"""
map_trace_instances.py — produce explicit per-invocation trace records.

Given raw_ops and a boundary list (op ranges per observed module invocation), emit
trace_instances[] records that keep EXACT op ranges separate from the learned model
layer identity. Representative templates may still be used downstream to reduce report
size, but every observed invocation is recorded here for validation/accounting.

Two modes:
  --boundaries FILE   JSON list of {model_layer_index, invocation_index?, op_range|op_indices,
                      layer_group_type?, representative_instance_id?}
                      -> normalized into trace_instances with derived instance_id + execution_count.

  --from-segments FILE  Consume segment_layers.py output (op_segments.json) as boundary
                        candidates. Because segments cannot prove learned-layer identity,
                        model_layer_index is set to "unknown" and must be filled by the AI /
                        architecture mapping step. This is explicit, never guessed.

Emits {trace_instances, execution_counts} JSON. execution_count is DERIVED (grouped by
model_layer_index), never taken as a layer count.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402


def normalize_boundaries(boundaries):
    instances = []
    inv_counter = {}
    # Reserve declared indexes even when their records follow automatic calls.
    reserved_invocations = {}
    for i, b in enumerate(boundaries):
        if isinstance(b.get('invocation_index'), int):
            mli = b.get('model_layer_index', 'unknown')
            key = mli if isinstance(mli, int) else f'unknown_{i}'
            reserved_invocations.setdefault(key, set()).add(b['invocation_index'])
    for i, b in enumerate(boundaries):
        mli = b.get('model_layer_index', 'unknown')
        key = mli if isinstance(mli, int) else f'unknown_{i}'
        # derive invocation_index per model layer if not given
        if 'invocation_index' in b:
            inv = b['invocation_index']
        else:
            inv = inv_counter.get(key, 0)
            while inv in reserved_invocations.get(key, ()):
                inv += 1
        # Later automatic records must not reuse an already declared invocation.
        if isinstance(inv, int):
            inv_counter[key] = max(inv_counter.get(key, 0), inv + 1)
        inst = {
            'instance_id': b.get('instance_id') or _make_id(mli, inv, b.get('layer_group_type')),
            'model_layer_index': mli,
            'invocation_index': inv,
        }
        if b.get('layer_group_type'):
            inst['layer_group_type'] = b['layer_group_type']
        if b.get('representative_instance_id'):
            inst['representative_instance_id'] = b['representative_instance_id']
        if b.get('op_indices'):
            inst['op_indices'] = list(b['op_indices'])
        elif b.get('op_range'):
            inst['op_range'] = list(b['op_range'])
        instances.append(inst)
    return instances


def _make_id(mli, inv, gtype):
    base = gtype or 'layer'
    if isinstance(mli, int):
        return f'{base}_{mli}_iter_{inv}'
    return f'{base}_unknown_iter_{inv}'


def derive_execution_counts(instances):
    counts = {}
    for inst in instances:
        mli = inst.get('model_layer_index')
        key = str(mli)
        counts[key] = counts.get(key, 0) + 1
    return counts


def from_segments(segments):
    """Convert op_segments.json candidates into unknown-layer boundaries."""
    boundaries = []
    # segment_layers emits coordinate-bearing ranges; candidates are marker statistics.
    if isinstance(segments.get('ranges'), list):
        seglist = segments['ranges']
    else:
        seglist = segments.get('segments') or segments.get('candidates') or []
    for i, seg in enumerate(seglist):
        rng = seg.get('op_range') or ([seg['start'], seg['end']] if 'start' in seg else None)
        if not rng:
            continue
        boundaries.append({
            'model_layer_index': 'unknown',
            'invocation_index': i,
            'op_range': rng,
        })
    return boundaries


def main():
    parser = argparse.ArgumentParser(description='Map observed invocations to explicit trace_instances')
    parser.add_argument('--boundaries', help='JSON list of boundary records')
    parser.add_argument('--from-segments', dest='from_segments', help='op_segments.json 候选')
    parser.add_argument('-o', '--output')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    if args.boundaries:
        with open(args.boundaries, 'r', encoding='utf-8') as f:
            data = json.load(f)
        boundaries = data if isinstance(data, list) else data.get('boundaries', [])
    elif args.from_segments:
        with open(args.from_segments, 'r', encoding='utf-8') as f:
            segments = json.load(f)
        boundaries = from_segments(segments)
    else:
        sys.stderr.write('错误: 需要 --boundaries 或 --from-segments\n')
        sys.exit(2)

    instances = normalize_boundaries(boundaries)
    result = {
        'trace_instances': instances,
        'execution_counts': derive_execution_counts(instances),
    }
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        print(f'trace_instances 已写入: {args.output}（{len(instances)} 条）')
    else:
        print(text)


if __name__ == '__main__':
    main()
