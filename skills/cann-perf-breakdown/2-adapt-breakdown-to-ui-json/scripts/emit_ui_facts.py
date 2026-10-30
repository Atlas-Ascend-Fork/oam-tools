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
"""Emit the three UI backend facts from an attributed breakdown.

Metrics derive from attributed kernels only. Every metric key is written even
when its value is null, because a missing key and a null value are different
claims: the UI renders null as unavailable, never as zero.

The architecture graph is emitted separately by build_graph.py, which needs the
declared `branches` this stage does not consume.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import breakdown_paths  # noqa: E402


def jload(path):
    with open(path) as handle:
        return json.load(handle)


def jdump(obj, path):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def numel(shape):
    if not isinstance(shape, list) or not shape:
        return 0
    total = 1
    for dim in shape:
        if not isinstance(dim, int) or dim <= 0:
            return 0
        total *= dim
    return total


def descendants(node_id, children_of):
    """node_id plus every descendant, so aggregate scopes include subtree kernels."""
    out, stack = [node_id], [node_id]
    while stack:
        for child in children_of.get(stack.pop(), []):
            out.append(child)
            stack.append(child)
    return out


def effective_duration_us(row):
    """A kernel's duration for summation, counting a doubly-reported collective once.

    msprof emits one collective as two rows with identical start and duration: the
    COMMUNICATION record and the AIV kernel executing it. The breakdown marks the second with
    `duplicate_of` rather than dropping it, so op indices stay stable. Every sum here must skip
    the marked row or the collective's time is counted twice — on a tp8 capture that inflated
    the step total by 48% and let one all-reduce claim 95% of it.
    """
    if row.get("duplicate_of") is not None:
        return 0.0
    return float(row.get("duration_us") or 0.0)


def counter_sum(rows, field):
    """Sum a counter across rows, or None when no row reported it.

    Null and zero are different claims. A node whose kernels never carried the counter must
    report null (unavailable), not 0.0 (measured idle) — the UI renders those differently and
    a zero would read as a real cube-idle finding.

    Unlike `effective_duration_us`, this deliberately does NOT skip `duplicate_of` rows. The
    duration rule exists because msprof reports a collective's *time* twice; the counters are
    not duplicated the same way. On the DS3.2 capture's 16 duplicate pairs the COMMUNICATION
    primary carries no counters at all and the AIV row carries all of them, so skipping
    duplicates here would discard the collective's measured vector work — 6.9% of the step's
    AIV time — rather than de-duplicate it. Exactly one row per pair carries counters, so a
    plain sum is right. `validate_conversion.py` asserts that precondition.
    """
    values = [r.get(field) for r in rows if r.get(field) is not None]
    return round(sum(values), 4) if values else None


def counter_time_weighted(rows, ratio_field, weight_field):
    """Time-weighted mean of a pipeline ratio.

    A plain mean over kernels lets a 2 us Cast weigh as much as an 84 us MlaPrologV3, which
    misreports where the node's cube time actually went. Weight by the counter time the ratio
    describes: `aic_mac_ratio` is a fraction of `aicore_time_us`, the AIV ratios of `aiv_time_us`.
    Rows missing either field are skipped rather than treated as zero-weight zeros.
    """
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        ratio = row.get(ratio_field)
        weight = row.get(weight_field)
        if ratio is None or weight is None:
            continue
        numerator += float(ratio) * float(weight)
        denominator += float(weight)
    return round(numerator / denominator, 6) if denominator > 0 else None


def _cores(row, prefer_mix):
    """Core count a kernel's cycle counter was accumulated over.

    Mix Block Dim wins for the vector counters on a mixed kernel, where the AIV phase ran on a
    different core count than the cube phase; using Block Dim there is wrong by exactly 2x.
    """
    keys = ("mix_block_dim", "block_dim") if prefer_mix else ("block_dim", "mix_block_dim")
    for key in keys:
        cores = row.get(key)
        if cores:
            try:
                value = float(cores)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
    return None


def _cycle_time_us(rows, cycles_key, time_key, freq_mhz, prefer_mix):
    """Elapsed us implied by the cycle counters, summed per kernel.

    The division is per kernel and includes the core count. `aic_total_cycles` is summed over
    every core the kernel occupied, so `cycles / freq` alone yields core-microseconds: on this
    capture's mean Block Dim of ~22 that overstated a node's cube time by ~22x. Only
    `cycles / (freq * cores)` is comparable to the reported `aicore_time(us)`, which is why
    this cannot be computed from an already-aggregated cycle total.
    """
    total = 0.0
    seen = False
    for row in rows:
        cycles = row.get(cycles_key)
        cores = _cores(row, prefer_mix)
        if cycles is None or not cores:
            continue
        reported_time = row.get(time_key)
        if float(cycles) > 0 and reported_time is not None and float(reported_time) > 0:
            observed_freq = float(cycles) / (float(reported_time) * cores)
            if abs(observed_freq - freq_mhz) / freq_mhz > 0.02:
                return None
        total += float(cycles) / (freq_mhz * cores)
        seen = True
    return round(total, 4) if seen else None


def cycle_metrics(rows, freq_mhz):
    """Cycle-derived metrics for a node, all null unless the clock is known.

    Every derived figure divides by the device clock, so computing them against an assumed
    frequency would silently rescale the set. A capture without a verified clock reports the raw
    cycle counts (which need no clock) and nulls the rest.
    """
    metrics = {
        # Raw core-cycle totals: summed across cores and kernels, no clock involved. A
        # scale-free work measure, not a duration.
        "aic_total_cycles": counter_sum(rows, "aic_total_cycles"),
        "aiv_total_cycles": counter_sum(rows, "aiv_total_cycles"),
        "aicore_cycle_time_us": None,
        "aiv_cycle_time_us": None,
    }
    if not freq_mhz:
        return metrics
    metrics["aicore_cycle_time_us"] = _cycle_time_us(
        rows, "aic_total_cycles", "aicore_time_us", freq_mhz, prefer_mix=False)
    metrics["aiv_cycle_time_us"] = _cycle_time_us(
        rows, "aiv_total_cycles", "aiv_time_us", freq_mhz, prefer_mix=True)
    return metrics


def node_metrics(rows, peak_tflops, dtype_bytes, total_time_us, freq_mhz=None):
    """Metrics for one node from the kernels attributed to it (and its subtree)."""
    if not rows:
        return None

    durations = [effective_duration_us(r) for r in rows]
    time_us = sum(durations)

    # HBM estimate is logical shape x dtype bytes — a comparison figure, never
    # measured traffic. Inputs plus outputs, per kernel.
    hbm_bytes = 0
    for row in rows:
        for shape in (row.get("input_shapes") or []) + (row.get("output_shapes") or []):
            hbm_bytes += numel(shape) * dtype_bytes

    # FLOPs only where a shape pair makes the contraction unambiguous.
    flops = 0
    for row in rows:
        if str(row.get("op_type") or "") not in ("MatMulV2", "MatMul", "BatchMatMulV2"):
            continue
        inputs = row.get("input_shapes") or []
        outputs = row.get("output_shapes") or []
        if len(inputs) < 2 or not outputs:
            continue
        weight_shape = inputs[1]
        output_shape = outputs[0]
        if (not isinstance(weight_shape, list) or len(weight_shape) < 2
                or not isinstance(output_shape, list) or not output_shape):
            continue
        n = output_shape[-1]
        if weight_shape[-1] == n:
            contraction = weight_shape[-2]
        elif weight_shape[-2] == n:
            contraction = weight_shape[-1]
        else:
            continue
        if not isinstance(contraction, int) or contraction <= 0:
            continue
        flops += 2 * numel(output_shape) * contraction

    # AI Core counters. The keys are the CSV's own `aic_`/`aiv_` spellings, which is what
    # attribute_kernels carries through; the earlier unprefixed `mac_ratio`/`mte2_ratio`
    # lookups matched nothing and reported every node's cube behaviour as unavailable while
    # the data sat in raw_ops_details.json.
    aicore_time_us = counter_sum(rows, "aicore_time_us")
    aiv_time_us = counter_sum(rows, "aiv_time_us")
    counters_present = sum(1 for r in rows if r.get("aicore_time_us") is not None
                           or r.get("aiv_time_us") is not None)

    op_time = defaultdict(float)
    for row in rows:
        op_time[str(row.get("op_type") or "unknown")] += effective_duration_us(row)
    op_ratio = ({op: round(100.0 * value / time_us, 2)
                 for op, value in sorted(op_time.items(), key=lambda kv: -kv[1])}
                if time_us > 0 else {})

    mfu = None
    if flops > 0 and time_us > 0 and peak_tflops:
        mfu = round(100.0 * (flops / (time_us * 1e-6)) / (peak_tflops * 1e12), 4)

    return {
        "time_us": round(time_us, 4),
        "time_pct": round(100.0 * time_us / total_time_us, 4) if total_time_us else None,
        "nops": len(rows),
        "hbm_mb": round(hbm_bytes / (1024 * 1024), 4) if hbm_bytes else None,
        "gflops": round(flops / 1e9, 6) if flops else 0.0,
        "mfu_bf16_pct": mfu,
        "mfu_int8_pct": None,
        "aicore_time_us": aicore_time_us,
        "aiv_time_us": aiv_time_us,
        # Cube-time share of wall time. Distinguishes a node genuinely busy on the cube from
        # one whose duration is mostly launch gap or waiting.
        "aicore_time_pct": (round(100.0 * aicore_time_us / time_us, 4)
                            if aicore_time_us is not None and time_us > 0 else None),
        # Pipeline ratios, time-weighted (see counter_time_weighted). mac vs mte2 is the
        # compute-bound vs memory-bound read: high mac means the cube is doing math, high
        # mte2 means it is waiting on loads from HBM/L2.
        "mac_ratio": counter_time_weighted(rows, "aic_mac_ratio", "aicore_time_us"),
        "mte2_ratio": counter_time_weighted(rows, "aic_mte2_ratio", "aicore_time_us"),
        "mte1_ratio": counter_time_weighted(rows, "aic_mte1_ratio", "aicore_time_us"),
        "scalar_ratio": counter_time_weighted(rows, "aic_scalar_ratio", "aicore_time_us"),
        "fixpipe_ratio": counter_time_weighted(rows, "aic_fixpipe_ratio", "aicore_time_us"),
        "vec_ratio": counter_time_weighted(rows, "aiv_vec_ratio", "aiv_time_us"),
        "aiv_mte2_ratio": counter_time_weighted(rows, "aiv_mte2_ratio", "aiv_time_us"),
        "cube_utilization_pct": counter_time_weighted(
            rows, "cube_utilization_pct", "aicore_time_us"),
        **cycle_metrics(rows, freq_mhz),
        "counter_coverage": {
            "kernels_with_counters": counters_present,
            "kernels_total": len(rows),
            "pct": round(100.0 * counters_present / len(rows), 2) if rows else None,
        },
        "op_ratio": op_ratio,
    }


def strip(node):
    """Analysis-config view of a node: identity and semantics, no kernel rows.

    A node the capture never observed is keyed by `structure_node_id` instead of `node_id`,
    for the same reason `source_only_structure` is: the UI runtime builds its backend index
    by scanning for `node_id`, so leaving one here injects a metric-free node into that
    index and the backend-count checks fail. The node still appears in the tree, keeps its
    semantics, and stays selectable -- it just carries no backend identity.
    """
    id_key = "node_id" if node.get("mapped_kernels", 0) else "structure_node_id"
    return {
        id_key: node["node_id"],
        "semantic_key": node["semantic_key"],
        "node_kind": node["node_kind"],
        "metric_scope": node["metric_scope"],
        "name": node["name"],
        "semantic": node["semantic"],
        "code_ref": node["code_ref"],
        "instance_indices": node["instance_indices"],
        # Declared vs observed layers for a repeated group. The graph pager spans the
        # declared set, so it has to survive this hop; dropping it silently shrinks a
        # 58-layer group to the 3 layers this capture happened to run.
        **{k: node[k] for k in ("declared_instance_indices",
                                "unobserved_instance_indices",
                                "invocation_count",
                                "structure_key",
                                "architecture_group_type",
                                "runtime_pattern") if node.get(k)},
        "mapped_kernels": node.get("mapped_kernels", 0),
        "children": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="explicit breakdown config path")
    parser.add_argument("--breakdown", required=True)
    parser.add_argument("--nodes", required=True)
    parser.add_argument("--attribution", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--model-name")
    parser.add_argument("--file-prefix", help="output filename prefix; defaults to model-id")
    parser.add_argument("--device-freq",
                        help="device_freq.json from stage 1 device_freq.py. Supplies the "
                             "measured AI Core clock; without it every cycle-derived metric "
                             "is emitted as null rather than against an assumed frequency.")
    parser.add_argument("--peak-bf16-tflops", type=float, default=0.0)
    parser.add_argument("--dtype-bytes", type=int, default=2)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    breakdown_paths.require_breakdown_ready(
        args.breakdown, args.config, "emit_ui_facts.py")

    config = jload(breakdown_paths.config_or_die(args.breakdown, args.config))
    index = jload(args.nodes)
    attribution = jload(args.attribution)

    summary = attribution["summary"]
    accounting_coverage = summary.get("accounting_coverage_pct")
    if accounting_coverage is None:
        accounting_coverage = summary["coverage_pct"]
    if accounting_coverage != 100.0:
        raise SystemExit(
            f"kernel accounting coverage is "
            f"{accounting_coverage}%; "
            "emit only from a fully accounted breakdown"
        )

    # The device clock travels with the metrics that depend on it. A missing file is not an
    # error: the run proceeds and every cycle-derived field is null, which the UI reports as
    # unavailable rather than as a measurement.
    device_profile = jload(args.device_freq) if args.device_freq else None
    freq_mhz = (device_profile or {}).get("aicore_freq_mhz")

    nodes = {n["node_id"]: dict(n) for n in index["nodes"]}
    children_of = {nid: list(n.get("child_ids") or []) for nid, n in nodes.items()}
    rows_by_node = defaultdict(list)
    for row in attribution["rows"]:
        rows_by_node[row["owner_node_id"]].append(row)

    for node_id, node in nodes.items():
        node["mapped_kernels"] = sum(
            len(rows_by_node.get(child, [])) for child in descendants(node_id, children_of)
        )

    total_time_us = round(sum(effective_duration_us(r)
                              for r in attribution["rows"]), 4)
    step = index.get("representative_step")
    prefix = args.file_prefix or args.model_id
    namespace = index["id_namespace"]

    # --- analysis config: hierarchy, no metrics ---
    roots = index["roots"]

    def nest(node_id):
        entry = strip(nodes[node_id])
        entry["children"] = [nest(child) for child in children_of.get(node_id, [])]
        return entry

    analysis = {
        "schema_version": "2.1-ui",
        "model_id": args.model_id,
        "model_name": args.model_name or config.get("model_name") or args.model_id,
        "report_id": args.report_id,
        "id_namespace": namespace,
        "representative_step": step,
        "architecture": config.get("architecture"),
        # Declared top-level order (embedding -> decoder stack -> tail). The graph builder
        # needs it to connect the separate roots; dropping it here leaves them unlinked.
        "model_flow": list(config.get("model_flow") or []),
        "trace_scope": config.get("trace_scope"),
        "stages": {nodes[nid]["semantic_key"]: nest(nid) for nid in roots["stages"]},
        "layer_structure": {key: nest(nid)
                            for key, nid in (roots["layer_structure"] or {}).items()},
        "runtime_auxiliary": [nest(nid) for nid in roots["runtime_auxiliary"]],
        "source_only_structure": [],
        # A single note is a str, and list("abc") would explode it into characters.
        "notes": ([notes] if isinstance(notes := config.get("notes") or [], str)
                  else list(notes)),
    }
    # `dataflow` supersedes the legacy linear `model_flow` for forks, joins and explicit
    # cross-structure ports. Preserve the reviewed declaration verbatim; the graph builder
    # resolves its structure keys into the UI namespace after node indexing.
    if config.get("dataflow") is not None:
        analysis["dataflow"] = config["dataflow"]

    # A node the capture never observed keeps its structure and loses its metrics.
    # Keyed by structure_node_id so it stays out of the backend node index.
    for node_id, node in nodes.items():
        if node["mapped_kernels"] == 0:
            analysis["source_only_structure"].append({
                "structure_node_id": node_id,
                "name": node["name"],
                "code_ref": node["code_ref"],
                "data_state": "source_only",
                # Which declared layer this stands for -- coverage checks read it.
                "instance_indices": list(node.get("instance_indices") or []),
                "declared_not_observed": bool(node.get("declared_not_observed")),
                # "no kernel attributed" is the symptom. When the index already knows the
                # node is a declared layer the capture never ran, say that instead -- the
                # reader needs the cause to judge whether the breakdown is wrong or the
                # capture was simply narrower than the model.
                "reason": (
                    f"Declared by the source at model layer index "
                    f"{node['instance_indices'][0]} but not executed in representative "
                    f"step {step} of this capture; structure retained, metrics omitted."
                    if node.get("declared_not_observed") and node.get("instance_indices")
                    else "No kernel attributed to this node inside the "
                         f"representative step ({step}) window of this capture."),
            })

    source_only_ids = {e["structure_node_id"] for e in analysis["source_only_structure"]}

    # --- performance: one record per metric-carrying node ---
    modules = []
    for node_id, node in nodes.items():
        if node_id in source_only_ids:
            continue
        subtree = [r for child in descendants(node_id, children_of)
                   for r in rows_by_node.get(child, [])]
        metrics = node_metrics(subtree, args.peak_bf16_tflops,
                               args.dtype_bytes, total_time_us, freq_mhz)
        if metrics is None:
            continue
        modules.append({
            "node_id": node_id,
            "module": node["name"],
            "metric_scope": node["metric_scope"],
            **metrics,
            "instance_indices": node["instance_indices"],
            "invocation_count": node.get("invocation_count"),
            "code_ref": node["code_ref"],
            # Invocations, never len(layer indices): one learned module called N times has
            # one index and N calls, and calling that "1 invocation" understates the
            # aggregate N-fold. State both so the divisor is auditable.
            "kernel_scope_note": (
                "Metrics aggregate every observed instance of this node across all "
                f"{node.get('invocation_count') or len(node['instance_indices'])} "
                f"invocations (model layer indices {node['instance_indices']}) in "
                f"representative step {step}." if node["instance_indices"] else None),
        })
    modules.sort(key=lambda m: -(m["time_us"] or 0))

    performance = {
        "schema_version": "2.1-ui",
        "model_id": args.model_id,
        "report_id": args.report_id,
        "id_namespace": namespace,
        "representative_step": step,
        "peak_bf16_tflops_assumed": args.peak_bf16_tflops or None,
        # The measured clock, kept beside the assumed peak so a reader can tell which figures
        # rest on a measurement and which on an assumption. `peak_bf16_tflops_assumed` is a
        # nameplate the caller passed in; `device_profile.aicore_freq_mhz` is observed.
        "aicore_freq_mhz": freq_mhz,
        "device_profile": device_profile,
        "total_time_us": total_time_us,
        "modules": modules,
        "scope_note": "Metrics are representative-step aggregates over attributed "
                      "kernels. HBM figures are logical shape x dtype estimates, "
                      "not measured traffic.",
    }

    # --- timeline: one event per attributed kernel ---
    rows = sorted(attribution["rows"], key=lambda r: r["op_index"])
    events = []
    for row in rows:
        start = float(row.get("start_time_us") or 0.0)
        duration = float(row.get("duration_us") or 0.0)
        events.append({
            "event_id": f"{namespace}/step/{step}/kernel/{row['op_index']}",
            "op_index": row["op_index"],
            "name": row.get("op_name"),
            "op_type": row.get("op_type"),
            "device_id": 0,
            "stream_id": row.get("stream_id"),
            "accelerator_core": "ASCEND_HARDWARE",
            "start_time_us_raw": f"{start:.3f}",
            "ts_us": start,
            "duration_us": duration,
            "end_us": start + duration,
            "wait_time_us": 0,
            "owner_node_id": row["owner_node_id"],
            "structure_instance_node_id": row["owner_node_id"],
            "layer_index": row.get("layer_index"),
            "submodule": nodes[row["owner_node_id"]]["semantic_key"],
            "mapping_status": row["attribution_evidence"],
            "trace_join_status": "breakdown_attributed_kernel",
        })

    timeline = {
        "schema_version": "1.4",
        "model_id": args.model_id,
        "report_id": args.report_id,
        "representative_step": step,
        "time_origin_us": min((e["ts_us"] for e in events), default=0),
        "time_unit": "us",
        "event_count": len(events),
        "events": events,
        "mapping_summary": {
            "mapped_events": len(events),
            "unmapped_events": 0,
            "mapping_coverage_pct": 100,
            "mapping_semantics": "structure node ownership derived from the "
                                 "breakdown's declared op_indices and instance "
                                 "ranges; no name-similarity matching",
        },
        "scope_note": f"Representative step {step} of the source capture.",
    }

    jdump(analysis, os.path.join(args.out, f"{prefix}_analysis_config.json"))
    jdump(performance, os.path.join(args.out, f"{prefix}_perf_data.json"))
    jdump(timeline, os.path.join(args.out, f"{prefix}_timeline.json"))

    print(f"WROTE {args.out}/{prefix}_analysis_config.json")
    print(f"WROTE {args.out}/{prefix}_perf_data.json")
    print(f"WROTE {args.out}/{prefix}_timeline.json")
    print()
    print(f"backend nodes      {len(modules)}")
    print(f"source-only nodes  {len(analysis['source_only_structure'])}")
    print(f"timeline events    {len(events)}")
    print(f"total_time_us      {total_time_us}")
    counts = Counter(r["owner_node_id"] for r in rows)
    print(f"kernels            {sum(counts.values())} across {len(counts)} owners")
    return 0


if __name__ == "__main__":
    sys.exit(main())
