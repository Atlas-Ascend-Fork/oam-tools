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
"""Bind every normalized Timeline event to one structure node and one raw TraceView event.

The UI skill's own `build-trace-bindings.mjs` re-derives ownership from one model's kernel
shapes (RmsNorm layer boundaries, an `mtp_scaffold` stage, hardcoded lm_head node ids), so it
only runs for that model. The attribution this pipeline already produced is stronger evidence:
it comes from the breakdown's declared `op_indices` and instance ranges, verified at 100%
coverage. This joins that attribution to the raw trace instead of guessing it again.

The raw join is by exact (op name, start time, duration) against `X` events; a kernel that
matches no raw event, or matches ambiguously, is an error rather than a silent drop.
"""
import argparse
import json
import math
import os
from collections import defaultdict


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def required_time(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Missing or invalid {label}: {value!r}") from error
    if not math.isfinite(result) or (label == "duration" and result < 0):
        raise ValueError(f"Invalid {label}: {value!r}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--attribution", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--enrich-trace", metavar="PATH",
                        help="write a copy of the trace with structure facts added to each "
                             "joined X event's args. The repeated-layer pager derives its "
                             "per-layer heat from args.layer_index, so without this the dots "
                             "stay uncolored even though the layers ran.")
    args = parser.parse_args()

    timeline = load(args.timeline)
    attribution = load(args.attribution)
    raw = load(args.trace)
    raw_events = raw if isinstance(raw, list) else raw.get("traceEvents") or []

    rows_by_op = {int(row["op_index"]): row for row in attribution["rows"]}

    # Index raw duration events by name; match within the pair to the nearest duration so a
    # repeated kernel name still resolves to its own event.
    by_name = defaultdict(list)
    for index, event in enumerate(raw_events):
        if event.get("ph") == "X":
            by_name[event.get("name")].append(index)

    used = set()
    enrich_by_raw_index = {}
    bindings = []
    unresolved = []
    for event in timeline.get("events") or []:
        op_index = int(event["op_index"])
        row = rows_by_op.get(op_index)
        if row is None:
            unresolved.append((op_index, "no attribution row"))
            continue
        # This adapter matches nearest duration; do not require unused timestamps.
        try:
            duration = required_time(row.get("duration_us"), "duration")
        except ValueError as error:
            unresolved.append((op_index, str(error)))
            continue
        candidates = []
        rejected = []
        for raw_index in by_name.get(row.get("op_name"), []):
            if raw_index in used:
                continue
            try:
                raw_duration = required_time(raw_events[raw_index].get("dur"), "duration")
            except ValueError as error:
                rejected.append(str(error))
                continue
            candidates.append((raw_index, raw_duration))
        if not candidates:
            reason = ("invalid raw matching fields: " + "; ".join(rejected)) if rejected else (
                f"no free raw X event named {row.get('op_name')!r}")
            unresolved.append((op_index, reason))
            continue
        pick = min(candidates, key=lambda candidate: abs(candidate[1] - duration))[0]
        used.add(pick)
        enrich_by_raw_index[pick] = {
            "layer_index": event.get("layer_index"),
            "owner_node_id": event["owner_node_id"],
            "submodule": event.get("submodule"),
            "op_index": op_index,
            "op_type": row.get("op_type"),
        }
        bindings.append({
            "trace_event_id": event["event_id"],
            "raw_source_event_index": pick,
            "timeline_event_id": event["event_id"],
            "op_index": op_index,
            "node_id": event["owner_node_id"],
            "instance_id": event.get("instance_index"),
            "structure_instance_node_id": event.get("structure_instance_node_id"),
            "submodule": event.get("submodule"),
            "relation": "direct_kernel_owner",
            "mapping_method": row.get("attribution_evidence") or "declared_op_indices",
            "confidence": "high",
        })

    if unresolved:
        for op_index, reason in unresolved[:10]:
            print(f"UNRESOLVED op_index={op_index}: {reason}")
        raise SystemExit(f"{len(unresolved)} Timeline event(s) could not be bound; "
                         "a binding must not be invented")

    output = {
        "schema_version": 1,
        "contract": "structure_tree_to_raw_traceview_v1",
        "model_id": timeline["model_id"],
        "report_id": timeline["report_id"],
        "representative_step": timeline.get("representative_step"),
        "sources": {"timeline": os.path.basename(args.timeline),
                    "raw_trace": os.path.basename(args.trace),
                    "attribution": os.path.basename(args.attribution)},
        "bindings": bindings,
        "summary": {
            "timeline_events": len(timeline.get("events") or []),
            "bound_events": len(bindings),
            "direct_events": len(bindings),
            "propagated_events": 0,
            "coverage_pct": round(100.0 * len(bindings)
                                  / max(1, len(timeline.get("events") or [])), 4),
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print(f"WROTE {args.out}")
    print(f"  bound {len(bindings)}/{len(timeline.get('events') or [])} "
          f"({output['summary']['coverage_pct']}%)")

    if args.enrich_trace:
        # Copy the structure facts into each joined event's `args`, leaving every standard lane
        # field untouched so Chrome-trace viewers still read it. Only `args` gains keys.
        enriched = 0
        with_layer = 0
        for raw_index, facts in enrich_by_raw_index.items():
            event = raw_events[raw_index]
            merged = dict(event.get("args") or {})
            for key, value in facts.items():
                if value is not None:
                    merged[key] = value
            event["args"] = merged
            enriched += 1
            if facts.get("layer_index") is not None:
                with_layer += 1
        payload = raw_events if isinstance(raw, list) else {**raw, "traceEvents": raw_events}
        os.makedirs(os.path.dirname(os.path.abspath(args.enrich_trace)), exist_ok=True)
        with open(args.enrich_trace, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        print(f"WROTE {args.enrich_trace}")
        print(f"  enriched {enriched} X events, {with_layer} carry layer_index")
        if not with_layer:
            print("  NOTE no event carries layer_index: the per-layer pager heat will be "
                  "uniform. Check that trace_instances declare model_layer_index.")


if __name__ == "__main__":
    main()
