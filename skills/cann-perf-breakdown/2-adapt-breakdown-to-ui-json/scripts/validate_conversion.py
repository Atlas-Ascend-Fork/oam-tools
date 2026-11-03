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
"""Check a conversion against the UI skill's contract before handing it off.

These are the invariants the report runtime and its validators assume. Catching a
break here names the offending node; catching it downstream only says a count is
wrong. The UI Skill's own validators remain authoritative for the report itself.
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter

#: A key must be written even when its value is null, because an absent key and a null value
#: are different claims: null means the capture did not measure it, absent means the pipeline
#: forgot to ask. `aicore_time_us` / `mac_ratio` / `mte2_ratio` are here because every emitter
#: has always written them (as null when the counters were never joined).
REQUIRED_METRIC_KEYS = ("time_us", "time_pct", "nops", "hbm_mb",
                        "mfu_int8_pct", "mfu_bf16_pct", "metric_scope", "op_ratio",
                        "aicore_time_us", "mac_ratio", "mte2_ratio")

#: Keys only a counter-aware emitter writes. NOT unconditionally required: this validator also
#: runs against facts an earlier emitter produced, which legitimately predate them. Demanding
#: them of every file failed all 77 records of each pre-existing perf_data.json — a validator
#: regression, not a defect in those files.
COUNTER_METRIC_KEYS = ("aiv_time_us", "aicore_time_pct", "cube_utilization_pct",
                       "aic_total_cycles", "aicore_cycle_time_us", "counter_coverage")

#: Presence marker for the counter-aware shape. `counter_coverage` is the right sentinel: the
#: new emitter writes it on every record and no earlier one ever did. Detecting by "any counter
#: key present" would misfire, since the old emitter already wrote aicore_time_us as null.
#: schema_version cannot serve here — old and new both emit "2.1-ui" and no consumer reads it.
COUNTER_SHAPE_MARKER = "counter_coverage"

#: `counts` key -> the `data_state` value that bucket tallies. The names differ for the
#: individually measured bucket (`counts` says what was measured, `data_state` says what the
#: expert is), so the pairing is written out instead of assumed positional. Single source of
#: truth for both the partition sum and the per-bucket comparison below.
STATE_BUCKET_TO_DATA_STATE = {
    "individually_measured": "measured",
    "fused_measured": "fused_measured",
    "residency_unresolved": "residency_unresolved",
    "remote_ep_shard": "remote_ep_shard",
    # `source_only` is a legal data_state: a declared shared expert whose kernels fell outside
    # this capture. It stays in the partition (with `time_us` null) or a legitimate inventory
    # is rejected as unbalanced.
    "source_only": "source_only",
}


#: `data_state` values that claim the expert's weights were on the profiled rank. `measured`
#: is reachable for shared experts only; a routed expert is fused inside one GroupedMatmul,
#: so the generator can only label it `fused_measured` / `remote_ep_shard` /
#: `residency_unresolved` — `routed_state_problems` rejects the rest.
LOCAL_RESIDENCY_STATES = ("measured", "fused_measured")

#: The only `ep_rank_validation` value under which an identity may be asserted. A missing key
#: (an inventory written before the field existed) is not a fourth value: it leaves residency
#: unverified, exactly like `unverified_without_topology` and `not_provided`.
RESOLVED_RANK_VALIDATION = "observed_topology"


def jload(path):
    with open(path) as handle:
        return json.load(handle)


def find_one(out_dir, suffix):
    # ``--out`` is a caller-supplied path, so it is escaped before joining the pattern: a
    # directory legitimately named ``out[0]`` would otherwise parse as a character class and
    # match nothing, and ``out*2026`` would also match unrelated sibling directories.
    matches = sorted(glob.glob(os.path.join(glob.escape(out_dir), f"*{suffix}")))
    if not matches:
        raise SystemExit(f"no *{suffix} in {out_dir}")
    if len(matches) > 1:
        raise SystemExit(f"ambiguous *{suffix} in {out_dir}: {matches}")
    return matches[0]


def collect(node, out, key="node_id"):
    """Depth-first walk collecting every dict that carries `key`."""
    if isinstance(node, dict):
        if key in node:
            out.append(node)
        for value in node.values():
            collect(value, out, key)
    elif isinstance(node, list):
        for item in node:
            collect(item, out, key)
    return out


def _positive_int(value):
    """True for a real positive count — `True` is an `int` in Python but is not a count."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def resident_window_problems(parallelism, declared_routed):
    """Why a claimed resident window is not the one this capture could have observed.

    Returns one string per inconsistency, empty when the window follows from the arithmetic.
    Rank r owns `[r * local, (r + 1) * local)`, so `resident_expert_indices` is fully
    redundant with `ep_rank` / `local_routed_experts` / `moe_ep_size` / the declared count:
    a window that disagrees with them was not derived from the capture, and every identity
    downstream of it is fabricated.

    Every number read off the inventory is type-checked before it is compared, because the
    input this function guards against is a hand-edited or foreign inventory: `moe_ep_size`
    left as the string `"2"` used to raise `TypeError` on `ep_rank >= ep_size` before the
    result-printing loop ran, so the validator died with empty stdout and the operator saw
    an empty failure message instead of the inconsistency. A malformed count is now reported
    as a problem like any other.
    """
    indices = parallelism.get("resident_expert_indices")
    ep_rank = parallelism.get("ep_rank")
    local = parallelism.get("local_routed_experts")
    ep_size = parallelism.get("moe_ep_size")
    if not (isinstance(indices, list) and len(indices) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in indices)):
        return [f"resident_expert_indices must be a [first, last] pair, got {indices!r}"]
    low, high = indices
    problems = []
    if not (isinstance(ep_rank, int) and not isinstance(ep_rank, bool) and ep_rank >= 0):
        problems.append(f"ep_rank {ep_rank!r} is not a possible rank")
    if not _positive_int(local):
        problems.append(f"local_routed_experts {local!r} is not a positive count")
    if ep_size is not None and not _positive_int(ep_size):
        problems.append(f"moe_ep_size {ep_size!r} is not a positive count")
    if high < low:
        problems.append(f"resident_expert_indices {indices} is not an ascending range")
    if problems:
        # The arithmetic below needs all three numbers to be real counts, so stop here
        # rather than raise on a malformed one or report noise on top of it.
        return problems
    if ep_size is not None and ep_rank >= ep_size:
        problems.append(f"ep_rank {ep_rank} is outside moe_ep_size {ep_size}")
    if _positive_int(declared_routed):
        if declared_routed % local:
            problems.append(f"{declared_routed} declared routed experts are not a multiple of "
                            f"the {local} observed locally, so moe_ep_size is not derivable")
        elif ep_size != declared_routed // local:
            problems.append(f"moe_ep_size {ep_size!r} contradicts {declared_routed} declared / "
                            f"{local} local = {declared_routed // local}")
        if high >= declared_routed:
            problems.append(f"resident window {indices} exceeds the {declared_routed} declared "
                            "routed experts")
    elif ep_size is None:
        problems.append("neither moe_ep_size nor a declared routed count places the window in "
                        "a topology")
    expected = [ep_rank * local, ep_rank * local + local - 1]
    if indices != expected:
        problems.append(f"rank {ep_rank} holding {local} local experts owns {expected}, "
                        f"not {indices}")
    # Bounded by construction (at most 4 problems, joined under ~270 characters), so this
    # one is NOT truncated like `routed_state_problems` below: every line here names a
    # distinct contradiction, and the last one — the window the rank would actually own —
    # is the only message that tells the operator what the correct value is. Truncating
    # here printed 3 contradictions plus "(1 more)" and dropped exactly that line.
    return problems


def routed_state_problems(routed_experts):
    """Routed experts labelled `measured` / `source_only` — states only a shared expert
    can carry. Checked unconditionally: a resolved window is not what makes these states
    wrong, so the unresolved branch must not let them through either.

    Truncated like `window_state_problems`: a wholesale relabelling (the failure mode this
    guards) lists every routed expert, and the untruncated `"; ".join` of 256 of them made
    the FAIL line ~24k characters — longer than the whole stdout, so the pipeline's
    `stdout[-1200:]` window kept only a mid-list fragment with no check name in it.
    """
    problems = [
        f"{expert.get('expert_id')} is a routed expert yet labelled "
        f"{expert.get('data_state')}, a state only a shared expert can carry"
        for expert in routed_experts
        if expert.get("data_state") in ("measured", "source_only")
    ]
    return problems[:3] + ([f"({len(problems) - 3} more)"] if len(problems) > 3 else [])


def window_state_problems(routed_experts, indices):
    """Routed experts whose `data_state` disagrees with an already-consistent window."""
    low, high = indices
    problems = []
    for expert in routed_experts:
        identity = expert.get("expert_id")
        state = expert.get("data_state")
        index = expert.get("expert_index")
        inside = isinstance(index, int) and low <= index <= high
        if state == "residency_unresolved":
            problems.append(f"{identity} stays residency_unresolved although the resident "
                            f"window {indices} is resolved")
        elif inside and state == "remote_ep_shard":
            problems.append(f"{identity} is inside the resident window {indices} yet labelled "
                            "remote_ep_shard")
        elif not inside and state in LOCAL_RESIDENCY_STATES:
            problems.append(f"{identity} is outside the resident window {indices} yet labelled "
                            f"{state}")
    return problems[:3] + ([f"({len(problems) - 3} more)"] if len(problems) > 3 else [])


def routed_identity_problems(routed_experts, declared_routed):
    """Routed experts whose id / index pairing is not the one the generator establishes.

    The generator writes `routed/{i}` with `expert_index i` for `i` in `0..declared-1`, a
    bijection. Every residency check downstream consumes `expert_index` to place an expert
    inside or outside the window, so a hand-edited list that duplicates an index, skips one,
    or pairs an id with another expert's index relabels the wrong expert while keeping the
    per-state totals — the counts partition stays balanced and the swap passes unnoticed.
    """
    problems = []
    seen = set()
    for expert in routed_experts:
        identity = expert.get("expert_id")
        index = expert.get("expert_index")
        if not isinstance(index, int) or isinstance(index, bool):
            problems.append(f"{identity} carries expert_index {index!r}, not an index")
            continue
        if index in seen:
            problems.append(f"{identity} reuses expert_index {index}")
        seen.add(index)
        if identity != f"routed/{index}":
            problems.append(f"{identity} is paired with expert_index {index}")
    if _positive_int(declared_routed):
        expected = set(range(declared_routed))
        if seen != expected:
            missing = sorted(expected - seen)[:3]
            extra = sorted(seen - expected)[:3]
            problems.append(
                f"the routed expert indices are not 0..{declared_routed - 1} "
                f"(missing e.g. {missing}, unexpected e.g. {extra})")
    # The per-expert entries are unbounded (one per duplicated / re-paired expert), so they
    # are truncated — but the summary of the bijection as a whole is what an operator fixing
    # the file needs first, so it is lifted out of the truncated tail and emitted first,
    # where `(N more)` cannot swallow it. Lifted, not prepended on top of the full list:
    # a list short enough not to truncate would otherwise print the summary twice.
    summary = ([problems.pop()]
               if problems and problems[-1].startswith("the routed expert indices") else [])
    return summary + problems[:3] + ([f"({len(problems) - 3} more)"] if len(problems) > 3 else [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="conversion output directory")
    parser.add_argument("--graph", help="architecture graph path; defaults to <out>/outputs/model_architecture_graph.json")
    parser.add_argument("--breakdown", help="cross-check kernel conservation")
    parser.add_argument("--attribution", help="kernel_attribution.json")
    args = parser.parse_args()

    analysis = jload(find_one(args.out, "_analysis_config.json"))
    performance = jload(find_one(args.out, "_perf_data.json"))
    timeline = jload(find_one(args.out, "_timeline.json"))
    graph_path = args.graph or os.path.join(args.out, "outputs/model_architecture_graph.json")
    graph = jload(graph_path) if os.path.exists(graph_path) else None

    checks = []

    def check(ok, label, detail=""):
        checks.append({"ok": bool(ok), "check": label, "detail": detail})

    check(graph is not None, "architecture graph exists", graph_path)

    # --- identity ---
    for field in ("model_id", "report_id", "representative_step"):
        values = {
            "analysis": analysis.get(field),
            "performance": performance.get(field),
            "timeline": timeline.get(field),
        }
        check(len(set(map(repr, values.values()))) == 1,
              f"{field} identical across the three facts",
              "" if len(set(map(repr, values.values()))) == 1 else repr(values))

    # --- node sets ---
    analysis_nodes = [n["node_id"] for n in collect(analysis, [])]
    perf_nodes = [n["node_id"] for n in collect(performance, [])]

    dup_analysis = {n for n in analysis_nodes if analysis_nodes.count(n) > 1}
    check(not dup_analysis, "one analysis definition per node_id",
          f"duplicated: {sorted(dup_analysis)}" if dup_analysis else "")
    dup_perf = {n for n in perf_nodes if perf_nodes.count(n) > 1}
    check(not dup_perf, "one performance record per node_id",
          f"duplicated: {sorted(dup_perf)}" if dup_perf else "")

    analysis_set, perf_set = set(analysis_nodes), set(perf_nodes)
    orphan_perf = sorted(perf_set - analysis_set)
    check(not orphan_perf, "every performance node exists in analysis",
          f"missing from analysis: {orphan_perf}" if orphan_perf else "")

    required = {node.get("node_id") for node in collect(analysis, [])
                if node.get("mapped_kernels", 0) > 0}
    missing = sorted(required - perf_set)
    check(not missing, "every mapped analysis node has a performance record",
          f"missing from performance: {missing}" if missing else "")

    # --- source-only nodes must stay metric-free and out of the backend index ---
    source_only = [entry.get("structure_node_id")
                   for entry in (analysis.get("source_only_structure") or [])]
    leaked = sorted(set(source_only) & perf_set)
    check(not leaked, "no source-only node carries metrics",
          f"present in performance: {leaked}" if leaked else "")
    miskeyed = [entry for entry in (analysis.get("source_only_structure") or [])
                if "node_id" in entry]
    check(not miskeyed,
          "source-only entries use structure_node_id, not node_id",
          f"{len(miskeyed)} entr(ies) use node_id and would enter the backend index"
          if miskeyed else "")
    unreasoned = [entry.get("structure_node_id")
                  for entry in (analysis.get("source_only_structure") or [])
                  if not str(entry.get("reason") or "").strip()]
    check(not unreasoned, "every source-only node records a reason",
          f"missing reason: {unreasoned}" if unreasoned else "")

    # --- metric keys present even when null ---
    perf_records = collect(performance, [])

    # Counter keys are demanded only of counter-aware facts. The marker appears on every record
    # a counter-aware emitter writes, so seeing it anywhere means the rest must carry the full
    # set too — that still catches a partial emit. Seeing it nowhere means these facts predate
    # the counter work, which is not a defect in them.
    counter_aware = any(COUNTER_SHAPE_MARKER in record for record in perf_records)
    required = REQUIRED_METRIC_KEYS + (COUNTER_METRIC_KEYS if counter_aware else ())

    missing_keys = {}
    for record in perf_records:
        absent = [key for key in required if key not in record]
        if absent:
            missing_keys[record["node_id"]] = absent
    check(not missing_keys,
          "every performance record declares all metric keys"
          + (" (incl. AI Core counters)" if counter_aware else " (pre-counter facts)"),
          f"{len(missing_keys)} record(s) incomplete, e.g. "
          f"{list(missing_keys.items())[:2]}" if missing_keys else "")

    # A sampled-window node's wall clock is not compute time; leaving time_us set
    # lets it outrank real compute and win default selection.
    bad_scope = [r["node_id"] for r in collect(performance, [])
                 if r.get("metric_scope") == "sampled_window_context"
                 and r.get("time_us") is not None]
    check(not bad_scope, "sampled-window nodes report time_us as null",
          f"{bad_scope}" if bad_scope else "")

    # --- timeline ownership ---
    events = timeline.get("events") if isinstance(timeline, dict) else timeline
    events = events or []
    owners = [e.get("owner_node_id") for e in events if e.get("owner_node_id")]
    unresolved = sorted({o for o in owners if o not in analysis_set})
    check(not unresolved, "every timeline owner resolves in analysis",
          f"unresolved: {unresolved[:5]}" if unresolved else "")
    check(len(owners) == len(events),
          "every timeline event has an owner",
          f"{len(events) - len(owners)} event(s) unowned"
          if len(owners) != len(events) else "")

    # --- kernel conservation ---
    if args.attribution and os.path.exists(args.attribution):
        attribution = jload(args.attribution)
        summary = attribution["summary"]
        attributed = summary["kernels_attributed"]
        excluded = summary.get("kernels_excluded", 0)
        unattributed = len(summary.get("unattributed") or [])
        total = summary["kernels_total"]
        accounted = attributed + excluded
        compute_events = [e for e in events
                          if e.get("mapping_status") != "sample_window_phase_owner"]
        check(len(compute_events) == attributed,
              "timeline compute events match attributed kernels",
              f"timeline {len(compute_events)} vs attributed {attributed}"
              if len(compute_events) != attributed else "")
        check(total == accounted + unattributed,
              "attributed + excluded + unattributed equals total kernels",
              f"{attributed} + {excluded} + {unattributed} != {total}"
              if total != accounted + unattributed else "")
        if "kernels_accounted" in summary:
            check(summary["kernels_accounted"] == accounted,
                  "reported accounted kernel count is internally consistent",
                  "" if summary["kernels_accounted"] == accounted
                  else f"reported {summary['kernels_accounted']} vs computed {accounted}")
        coverage = summary.get("accounting_coverage_pct")
        if coverage is None:
            coverage = summary["coverage_pct"]
        check(coverage == 100.0,
              "kernel accounting coverage is 100%",
              "" if coverage == 100.0 else f"{coverage}%")

    # --- graph ---
    if graph is not None:
        check(graph.get("schema_version") == "model_architecture_graph.v1",
              "graph declares the v1 contract",
              f"found {graph.get('schema_version')!r}")
        roots = graph.get("roots") or []
        root_ids = {r.get("id") if isinstance(r, dict) else r for r in roots}
        check(bool(roots), "graph roots are nonempty")
        for required in ("section/source_architecture", "section/runtime_auxiliary"):
            check(required in root_ids, f"graph declares {required}")
        edges = graph.get("edges") or []
        check(bool(edges), "graph declares explicit edges")
        thin = [e.get("id") for e in edges
                if not e.get("tensor") or not (e.get("provenance") or [])]
        check(not thin, "every edge carries tensor metadata and provenance",
              f"{len(thin)} thin edge(s), e.g. {thin[:3]}" if thin else "")

        items = collect(graph, [], key="backendNodeId")
        dangling = sorted({i["backendNodeId"] for i in items
                           if i["backendNodeId"] not in analysis_set})
        check(not dangling, "every graph backendNodeId resolves in analysis",
              f"dangling: {dangling[:5]}" if dangling else "")
        heated = [i.get("id") for i in collect(graph, [], key="id")
                  if i.get("dataState") == "source_only" and i.get("backendNodeId")]
        check(not heated, "source-only graph items carry no backendNodeId",
              f"{heated[:5]}" if heated else "")

    # --- device clock and counter-derived metrics ---
    # A null clock is a valid result (the capture carried no counters), so absence is not a
    # failure. What must hold is internal consistency: when a clock IS reported, the time it
    # implies from the cycle counters has to match the separately-reported counter time. That
    # equality is the only check here that can catch a wrong core-count divisor, which silently
    # rescales every cycle-derived figure instead of producing an obviously bad one.
    profile = performance.get("device_profile")
    freq = performance.get("aicore_freq_mhz")
    if profile is None:
        check(freq is None, "no device_profile means no clock is claimed", f"freq={freq!r}")
    else:
        check(profile.get("aicore_freq_mhz") == freq,
              "top-level aicore_freq_mhz matches device_profile",
              f"{freq!r} vs {profile.get('aicore_freq_mhz')!r}")
        check(profile.get("aicore_freq_basis") in ("derived", "declared", "unavailable"),
              "clock basis is a known provenance",
              repr(profile.get("aicore_freq_basis")))
        agreement = (profile.get("cross_check") or {}).get("agreement")
        check(agreement != "mismatch",
              "declared and derived clocks agree within tolerance",
              f"agreement={agreement}, "
              f"delta_pct={(profile.get('cross_check') or {}).get('delta_pct')}")

    modules = performance.get("modules") or []
    if freq:
        # Same quantity by two routes: cycles/(freq*cores) vs the reported counter time.
        # 1% is loose enough for counter rounding and tight enough that a wrong divisor
        # (off by the core count, so >100%) cannot pass.
        drift = []
        for module in modules:
            for time_key, cycle_key in (("aicore_time_us", "aicore_cycle_time_us"),
                                        ("aiv_time_us", "aiv_cycle_time_us")):
                reported, implied = module.get(time_key), module.get(cycle_key)
                if not reported or implied is None:
                    continue
                delta = 100.0 * abs(implied - reported) / reported
                if delta > 1.0:
                    drift.append(f"{module['node_id']}:{time_key} {delta:.2f}%")
        check(not drift,
              "cycle-implied time reconciles with reported counter time",
              f"{len(drift)} module-metric(s) off by >1%, e.g. {drift[:3]}" if drift else "")

    # Ratios are fractions of a counter time, so anything outside [0,1] means the weighting
    # divided by the wrong denominator.
    bad_ratio = []
    for module in modules:
        for key in ("mac_ratio", "mte2_ratio", "mte1_ratio", "scalar_ratio",
                    "fixpipe_ratio", "vec_ratio", "aiv_mte2_ratio"):
            value = module.get(key)
            if value is not None and not 0.0 <= value <= 1.0:
                bad_ratio.append(f"{module['node_id']}:{key}={value}")
    check(not bad_ratio, "every pipeline ratio lies in [0,1]",
          f"{len(bad_ratio)} out of range, e.g. {bad_ratio[:3]}" if bad_ratio else "")

    # A counter metric must never be fabricated for a node whose kernels carried none.
    fabricated = [m["node_id"] for m in modules
                  if (m.get("counter_coverage") or {}).get("kernels_with_counters") == 0
                  and m.get("aicore_time_us") is not None]
    check(not fabricated, "no counter metric without a counter-bearing kernel",
          f"{fabricated[:5]}" if fabricated else "")

    # Counter sums intentionally include `duplicate_of` rows, unlike duration sums: for a
    # doubly-reported collective the COMMUNICATION primary carries no counters and the AIV row
    # carries them all, so skipping duplicates would discard measured work instead of
    # de-duplicating it. That is only safe while at most one row per pair carries counters.
    # Assert it rather than trust it — a future profiler that populates both would silently
    # double-count the collective's cube and vector time.
    if args.attribution and os.path.exists(args.attribution):
        rows = {r["op_index"]: r for r in jload(args.attribution)["rows"]}
        counter_keys = ("aicore_time_us", "aiv_time_us",
                        "aic_total_cycles", "aiv_total_cycles")

        def carries(row):
            return any(row.get(key) is not None for key in counter_keys)

        both = [index for index, row in rows.items()
                if row.get("duplicate_of") is not None
                and carries(row) and carries(rows.get(row["duplicate_of"], {}))]
        check(not both,
              "a duplicated collective reports counters on one row only",
              f"{len(both)} pair(s) carry counters on both rows, so counter sums would "
              f"double-count: op {both[:5]}" if both else "")

    # --- MoE expert inventory (only when the model declares experts) ---
    inventory_matches = glob.glob(os.path.join(args.out, "*_expert_inventory.json"))
    if inventory_matches:
        inventory = jload(sorted(inventory_matches)[0])
        declared = inventory.get("declared") or {}
        counts = inventory.get("counts") or {}
        experts = inventory.get("experts") or []

        total = declared.get("total")
        check(total == len(experts),
              f"the inventory lists all {total} declared experts",
              "" if total == len(experts) else f"declared {total} but listed {len(experts)}")

        bucketed = sum(counts.get(key) or 0 for key in STATE_BUCKET_TO_DATA_STATE)
        check(bucketed == len(experts),
              "every expert falls in exactly one data_state bucket",
              "" if bucketed == len(experts)
              else f"buckets sum to {bucketed}, listed {len(experts)}")

        # A balancing total says nothing about the split: moving one expert from `source_only`
        # to `fused_measured` in `counts` keeps the sum at the listed number while telling the
        # UI a group measurement exists that the capture never made. So compare each tally
        # against the states the listed experts actually carry. A `data_state` outside the five
        # buckets needs no separate check: it drops out of `listed` here and out of `bucketed`
        # above, so one of the two already fails.
        listed = Counter(expert.get("data_state") for expert in experts)
        miscounted = [
            f"{key}: counts={counts.get(key) or 0}, listed {listed.get(state, 0)}"
            for key, state in sorted(STATE_BUCKET_TO_DATA_STATE.items())
            if (counts.get(key) or 0) != listed.get(state, 0)
        ]
        check(not miscounted,
              "each data_state bucket count matches the listed experts",
              "; ".join(miscounted))

        # The whole point of the inventory: a fused or absent expert must not carry a time.
        # A per-expert number here would be a fabrication, since the profiler measured the
        # group, not the member.
        fabricated = [e["expert_id"] for e in experts
                      if e.get("data_state") != "measured" and e.get("time_us") is not None]
        check(not fabricated,
              "no per-expert time unless that expert was individually measured",
              f"{len(fabricated)} fabricated, e.g. {fabricated[:3]}" if fabricated else "")

        # An expert claiming a measuring node must name one that exists in the perf facts.
        perf_ids = set(perf_nodes)
        dangling = sorted({node for e in experts
                           for node in (e.get("measured_by_node_id") or [])
                           if node not in perf_ids})
        check(not dangling, "every measured_by_node_id resolves in the perf facts",
              f"dangling: {dangling[:3]}" if dangling else "")

        # Residency identity requires the rank. Claiming specific indices without it is the
        # error this guards: the count is observable from the weight shape, the identity is not.
        parallelism = inventory.get("expert_parallelism") or {}
        if parallelism.get("ep_rank") is None:
            routed_fused = [e["expert_id"] for e in experts
                            if e.get("kind") == "routed"
                            and e.get("data_state") == "fused_measured"]
            check(parallelism.get("resident_expert_indices") is None
                  and not routed_fused,
                  "without ep_rank, no expert identity is asserted as resident",
                  f"indices={parallelism.get('resident_expert_indices')}, "
                  f"routed_fused={routed_fused}")

        # The mirror of the check above, and the reason `resident_expert_indices` cannot
        # vouch for itself: it is the very claim under test, so a stale or hand-edited
        # inventory can carry a window the capture never observed and then derive both the
        # residents and the "remote" complement from it. Only `ep_rank_validation` records
        # whether the observed topology backed the rank, so resolution is decided by that
        # field and the window is then re-derived from rank / local count / ep_size. With no
        # observed topology the complement is not knowable either — declaring 4 and observing
        # 2 locally does not make indices 2-3 remote, a rank-1 capture holds exactly those
        # two — so no routed expert may be called resident or remote.
        rank_validation = parallelism.get("ep_rank_validation")
        resolved = rank_validation == RESOLVED_RANK_VALIDATION
        routed = [e for e in experts if e.get("kind") == "routed"]
        claimed_resident = [e["expert_id"] for e in routed
                            if e.get("data_state") in LOCAL_RESIDENCY_STATES]
        claimed_remote = [e["expert_id"] for e in routed
                          if e.get("data_state") == "remote_ep_shard"]
        # Before any window arithmetic: the window checks place an expert by its
        # `expert_index`, so an index that is duplicated, missing, or paired with another
        # expert's id would relabel the wrong expert while keeping every bucket balanced.
        identity_problems = routed_identity_problems(routed, declared.get("routed_experts"))
        check(not identity_problems,
              "routed experts pair routed/<i> with expert_index i, one per declared index",
              "; ".join(identity_problems))
        # Wrong under every window, so checked before either branch below.
        impossible_states = routed_state_problems(routed)
        check(not impossible_states,
              "no routed expert carries a shared-expert-only data_state",
              "; ".join(impossible_states))
        if resolved:
            window_problems = resident_window_problems(parallelism, declared.get("routed_experts"))
            check(not window_problems,
                  "the resident window follows from ep_rank, local_routed_experts and moe_ep_size",
                  "; ".join(window_problems))
            if not window_problems:
                state_problems = window_state_problems(
                    routed, parallelism["resident_expert_indices"])
                check(not state_problems,
                      "every routed expert's data_state agrees with the resident window",
                      "; ".join(state_problems))
        else:
            detail = (f"ep_rank_validation="
                      f"{rank_validation!r}"
                      if "ep_rank_validation" in parallelism else
                      "the inventory carries no ep_rank_validation, so it predates the "
                      "residency contract; regenerate it with the current "
                      "build_expert_inventory.py")
            check(parallelism.get("resident_expert_indices") is None
                  and not claimed_resident and not claimed_remote,
                  "without an observed topology, no expert is asserted remote or resident",
                  f"indices={parallelism.get('resident_expert_indices')}, "
                  f"routed_resident={claimed_resident[:3]}, "
                  f"routed_remote={claimed_remote[:3]}, {detail}")

    failures = [c for c in checks if not c["ok"]]
    for item in checks:
        print(f"{'PASS' if item['ok'] else 'FAIL'}  {item['check']}"
              + (f"  — {item['detail']}" if item["detail"] else ""))
    print()
    print(f"{len(checks) - len(failures)} passed / {len(failures)} failed")
    if failures:
        print("\nFix the conversion. Do not satisfy a check by generating data the "
              "capture does not contain.")
        return 1
    print("\nConversion is self-consistent. Hand off to the UI skill's validators, "
          "which are authoritative for the report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
