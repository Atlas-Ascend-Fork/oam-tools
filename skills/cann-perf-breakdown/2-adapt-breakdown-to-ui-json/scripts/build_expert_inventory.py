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
"""Emit the MoE expert inventory: every declared expert, and what the capture measured.

The source declares 256 routed experts plus 1 shared expert per MoE layer. A capture almost
never contains 257 separable measurements, for three independent reasons that must not be
conflated:

1. **Expert parallelism.** With `moe_ep_size = N` only `n_routed_experts / N` experts have
   weights resident on the profiled rank. The rest execute on other ranks and appear in this
   capture only as the all-to-all that dispatches tokens to them. They are declared, not
   observed, and their time is unknown rather than zero.

2. **Kernel fusion.** The resident experts run as a single `GroupedMatmul` over a stacked
   weight tensor, with a `group_list` giving each expert's token count. One kernel, one
   duration. Per-expert time is not recoverable from it by any arithmetic the profiler
   supports — splitting the fused duration by token count would fabricate per-expert numbers
   that read as measurements.

3. **Source-only declarations.** An expert declared in the model source may have no kernel
   attributed to it in this capture. It stays listed with unknown time; it is not a zero-time
   measurement, and it must not be folded into the fusion or remote-rank cases.

So this emits an inventory, not a per-expert breakdown: each expert gets an identity and a
`data_state` saying whether its own duration is recoverable. A single shared expert can
be `measured`; multiple shared experts covered by aggregate nodes are `fused_measured`
with null per-expert time. Routed experts remain non-separable within their fused group. A UI can then show all 257 and be honest about which
one figure covers which experts, instead of silently showing 1 of 257 or inventing 257.

Residency is derived from the weight tensor's leading dimension in the GroupedMatmul shapes,
which is the profiled rank's own local expert count — an observation, not a config assumption.
That observation yields the resident *count* only. Which global indices are resident also needs
`--ep-rank`, which the capture never records. With either input missing, every routed expert is
reported as `residency_unresolved`: the complement is not knowable either, so labelling the rest
`remote_ep_shard` would assert a residency the capture never established.
"""
import argparse
import json
import os
import sys

#: Kernels whose stacked weight leading dim reveals the rank's local expert count.
GROUPED_OP_TYPES = ("GroupedMatmul", "GroupedMatmulV2", "GroupedMatMul")


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


def observed_local_experts(rows):
    """Local expert count from the GroupedMatmul weight tensor's leading dimension.

    A stacked expert weight enters as `[local_experts, ...]`. The activation is `[tokens, hidden]`
    and the group_list is 1-D, so the weight is identified as the first input with rank >= 3 —
    which holds for both the plain `[E, K, N]` layout and the fractal-Z quantised
    `[E, K1, N1, k0, n0]` one seen on Ascend W8A8 captures.

    Returns (count, evidence) or (None, reason). Disagreement across kernels is reported rather
    than resolved: it means the layers do not share one EP topology and no single count is right.
    """
    counts = {}
    for row in rows:
        if str(row.get("op_type") or "") not in GROUPED_OP_TYPES:
            continue
        for shape in row.get("input_shapes") or []:
            if isinstance(shape, list) and len(shape) >= 3 and isinstance(shape[0], int):
                counts.setdefault(shape[0], []).append(row.get("op_index"))
                break

    if not counts:
        return None, "no GroupedMatmul kernel carried a stacked expert weight shape"
    if len(counts) > 1:
        return None, (f"GroupedMatmul kernels disagree on local expert count "
                      f"{sorted(counts)}; the layers do not share one EP topology")
    local = next(iter(counts))
    ops = counts[local]
    return local, (f"leading dim of the stacked expert weight in {len(ops)} GroupedMatmul "
                   f"kernel(s), e.g. op {ops[0]}")


def find_expert_nodes(modules, semantic_key):
    """Performance records for a given expert semantic key, one per MoE-bearing scope."""
    return [m for m in modules if str(m.get("node_id", "")).endswith("/" + semantic_key)]


def manifest_facts(manifest):
    """Flatten the manifest's `facts` list to {key: (value, source_ref)}.

    Stage 1 records each fact with the source line it was read from. Carrying the ref through
    means the inventory can cite where 256 came from rather than asserting it.
    """
    out = {}
    for fact in (manifest or {}).get("facts") or []:
        key = fact.get("key")
        if key is not None and isinstance(fact.get("value"), int):
            out[key] = (fact["value"], fact.get("source_ref"))
    return out


def validate_ep_rank(ep_rank, ep_size):
    """Reject a rank that cannot be a rank of the observed expert-parallel topology.

    A negative rank is never valid. When the capture establishes `moe_ep_size`, a rank at or
    beyond it names a shard that does not exist: honouring it would place the resident window
    outside the declared experts and label every one of them remote, which reads as a finding
    about an empty rank rather than as the input error it is. `ep_size` is None when the
    topology is unobserved, and then no upper bound can be checked — the rank stays unusable
    for identity purposes instead of being silently accepted.
    """
    if ep_rank is None:
        return
    if ep_rank < 0:
        raise ValueError(f"--ep-rank {ep_rank} is negative; expert-parallel ranks start at 0")
    if ep_size is not None and ep_rank >= ep_size:
        raise ValueError(f"--ep-rank {ep_rank} is outside the observed expert-parallel topology "
                         f"(moe_ep_size={ep_size}, valid ranks 0-{ep_size - 1})")


def residency_case(ep_rank, local, ep_size, declared_routed):
    """Which of the seven residency situations this capture is in.

    Both human-readable residency fields — the per-expert `reason` and the per-capture
    `identity_note` — switch on this one value instead of re-testing the inputs themselves.
    They used to branch independently, and the two branch sets did not match: with 3 declared
    and 2 observed locally plus `--ep-rank 1`, `reason` said the counts are not a multiple
    while `identity_note` fell through to "this capture establishes no expert-parallel
    topology", the opposite claim, in the very field the CLI prints as its NOTE line and the
    UI reads. Naming the case once makes that disagreement unreachable rather than unlikely.

    `no_routed_declared` is tested first because it is the only case in which there is nothing
    to divide: with no declared routed-expert count the divisibility question is not merely
    unanswered but unaskable, and folding it into `not_divisible` made both fields assert a
    multiple relation they had no operands for (printing `None declared routed experts are
    not a multiple of ...`). A falsy `declared_routed` also forces `ep_size` to `None`, so
    `resolved` can never be the case here.

    `zero_local` is tested second for the same reason: a stacked weight whose leading
    dimension is 0 observes no expert on this rank, so there is nothing to place a rank in
    and no count to divide by. It used to fall through to `rank_missing` (without a rank,
    "0 resident routed experts ... which global indices those are is unknown" — a window of
    no experts needs no resolving) or `not_divisible` (with one, "not a multiple of the 0
    observed locally" — a divisibility claim with 0 as its divisor).
    """
    if not declared_routed:
        return "no_routed_declared"
    if local == 0:
        return "zero_local"
    if ep_rank is not None and ep_size is not None and local:
        return "resolved"
    if ep_rank is None and local is None:
        return "both_missing"
    if ep_rank is None:
        return "rank_missing"
    if local is None:
        return "topology_missing"
    return "not_divisible"


def no_routed_claim(declared_routed):
    """How to say "there is no routed-expert count to work from" without inventing one.

    Missing and zero are different facts and only the second is a claim about the model, so
    neither field may round one into the other.
    """
    if declared_routed is None:
        return ("the declared routed-expert count (n_routed_experts) is absent from this "
                "capture's manifest facts and architecture")
    return f"this model declares {declared_routed} routed experts"


def unresolved_reason(case, ep_rank, local, declared_routed):
    """Why no routed expert's global residency could be established — never which one ran.

    One branch per `residency_case` other than `resolved`, in the same order as
    `identity_note` below, so the two fields describe one inventory one way.
    """
    if case == "both_missing":
        return ("This capture establishes neither a local expert count (no GroupedMatmul "
                "carried a stacked expert weight shape) nor an expert-parallel rank, so no "
                "global expert identity can be asserted local or remote. Residency is "
                "unknown, not absent.")
    if case == "no_routed_declared":
        claim = no_routed_claim(declared_routed)
        if ep_rank is None:
            return (f"No routed expert's residency is asserted because {claim}, so "
                    "moe_ep_size cannot be derived and no global expert identity can be "
                    "called local or remote. Residency is unknown, not absent.")
        return (f"--ep-rank {ep_rank} was supplied and is recorded, but {claim}, so "
                "moe_ep_size cannot be derived and no routed expert has a global identity to "
                "resolve here. Residency is unknown, not absent.")
    if case == "zero_local":
        rank_clause = (f"--ep-rank {ep_rank} was supplied, but the stacked expert weight's "
                       "leading dimension is 0, so this rank observes no routed expert and "
                       "no resident window exists to place that rank in"
                       if ep_rank is not None else
                       "the stacked expert weight's leading dimension is 0, so this rank "
                       "observes no routed expert")
        return (f"{rank_clause}. No global expert identity is asserted local or remote.")
    if case == "rank_missing":
        return (f"This capture has {local} resident routed experts, but it does not record "
                "which expert-parallel rank produced it, so which global indices those are is "
                "unknown. Pass --ep-rank to resolve. The residents are some contiguous window "
                "of the declared experts, so no expert here is claimed local or remote.")
    if case == "topology_missing":
        return (f"--ep-rank {ep_rank} was supplied, but this capture observed no stacked "
                "expert weight shape, so the local expert count and the rank's resident "
                "window are unknown. No global expert identity is asserted local or remote.")
    return (f"--ep-rank {ep_rank} was supplied, but {declared_routed} declared routed experts "
            f"are not a multiple of the {local} observed locally, so moe_ep_size cannot be "
            "derived and the rank's resident window cannot be located. No global expert "
            "identity is asserted local or remote.")


def identity_note(case, ep_rank, local, declared_routed):
    """One sentence on what the rank pins down. Names experts only when the mapping is real.

    Branch-for-branch with `unresolved_reason`, keyed off the same `residency_case`: this is
    the field the CLI prints as its NOTE line and the UI reads, so a case the per-expert
    `reason` distinguishes must not collapse into a different claim here.
    """
    if case == "resolved":
        base = ep_rank * local
        return f"Rank {ep_rank} owns global routed experts {base}-{base + local - 1}."
    if case == "both_missing":
        return ("The capture establishes neither the local expert count nor ep_rank, so global "
                "expert residency is unknown.")
    if case == "no_routed_declared":
        claim = no_routed_claim(declared_routed)
        if ep_rank is None:
            return (f"There is no routed-expert set to resolve because {claim}, so "
                    "moe_ep_size cannot be derived and global expert residency is unknown.")
        return (f"--ep-rank {ep_rank} was supplied and is recorded, but {claim}, so "
                "moe_ep_size cannot be derived, there is no routed-expert set to place that "
                "rank in, and global expert residency remains unknown.")
    if case == "zero_local":
        if ep_rank is None:
            return ("The stacked expert weight's leading dimension is 0, so this rank "
                    "observes no routed expert and global expert residency is unknown.")
        return (f"--ep-rank {ep_rank} was supplied and is recorded, but the stacked expert "
                "weight's leading dimension is 0, so this rank observes no routed expert, "
                "no resident window exists to place that rank in, and global expert "
                "residency remains unknown.")
    if case == "rank_missing":
        return ("The capture does not record ep_rank, so the resident expert COUNT is known "
                f"({local}) but the global indices are not. Rank r owns [r*local, "
                "(r+1)*local); pass --ep-rank to resolve identities.")
    if case == "topology_missing":
        return ("--ep-rank was supplied, but this capture establishes no expert-parallel "
                "topology to place it in, so the resident window cannot be located and global "
                "expert residency remains unknown.")
    # `not_divisible`: declared_routed is a positive count that is not a multiple of local,
    # so the divisibility claim below has real operands on both sides.
    return (f"--ep-rank {ep_rank} was supplied, but {declared_routed} declared routed experts "
            f"are not a multiple of the {local} observed locally, so moe_ep_size cannot be "
            "derived, the resident window cannot be located and global expert residency "
            "remains unknown.")


def build(config, performance, attribution, manifest=None, ep_rank=None):
    architecture = config.get("architecture") or {}
    facts = manifest_facts(manifest)
    modules = performance.get("modules") or []
    rows = attribution.get("rows") or []

    def fact(key):
        value, ref = facts.get(key, (None, None))
        if value is None:
            value = architecture.get(key)
        return value, ref

    # Declared counts come from the model source via stage 1's AST extraction, never from the
    # kernel shapes: the shapes only ever show this rank's slice, so trusting them for the
    # total would under-report the model by the EP factor.
    declared_routed, routed_ref = fact("n_routed_experts")
    declared_shared, shared_ref = fact("n_shared_experts")
    top_k, top_k_ref = fact("num_experts_per_tok")

    local, residency_evidence = observed_local_experts(rows)
    ep_size = None
    if declared_routed and local and declared_routed % local == 0:
        ep_size = declared_routed // local

    routed_nodes = find_expert_nodes(modules, "routed_experts")
    shared_nodes = find_expert_nodes(modules, "shared_expert")

    experts = []

    # Which global expert indices are resident depends on the profiled rank: rank r owns
    # [r*local, (r+1)*local). The capture does not record `ep_rank` — msprof has no reason to —
    # so without `--ep-rank` the resident *count* is known but the resident *identities* are
    # not. Defaulting to rank 0 silently would assert that experts 0-15 were profiled when the
    # capture may have come from rank 5 (experts 80-95). Emit the slot offset as unknown
    # instead, and label the residents by local slot rather than by a fabricated global index.
    #
    # Asserting the complement is the same error in mirror image. With 4 declared and 2 observed
    # locally, calling indices 2-3 `remote_ep_shard` is false for a rank-1 capture, where those
    # two are exactly the residents; with no observed topology at all, every expert would be
    # labelled remote. So an identity is asserted only when BOTH inputs are present and the rank
    # is a possible one — otherwise all routed experts stay `residency_unresolved`.
    validate_ep_rank(ep_rank, ep_size)
    rank_supplied = ep_rank is not None
    # One classification of the capture drives every residency verdict below AND the two
    # human-readable fields, so `reason` / `identity_note` / `ep_rank_validation` /
    # `resident_expert_indices` cannot describe different situations for one inventory.
    case = residency_case(ep_rank, local, ep_size, declared_routed)
    known_rank = case == "resolved"
    base = ep_rank * local if known_rank else 0

    # --- routed experts -----------------------------------------------------------------
    # Every declared expert is listed. Only the resident ones are attributable to a kernel in
    # this capture, and even they share one fused measurement.
    for index in range(int(declared_routed or 0)):
        resident = known_rank and base <= index < base + local
        slot = index - base if resident else None
        if resident:
            state = "fused_measured"
            reason = ("Runs inside the fused GroupedMatmul covering all "
                      f"{local} experts resident on this rank (local slot {slot}). The kernel "
                      "reports one duration for the group; per-expert time is not separable "
                      "from it.")
        elif known_rank:
            state = "remote_ep_shard"
            reason = ("Weights live on a different expert-parallel rank"
                      + (f" (moe_ep_size={ep_size})" if ep_size else "")
                      + ". This capture profiles one rank, so this expert's time is unknown; "
                        "the all-to-all dispatch is the only trace of it here.")
        else:
            state = "residency_unresolved"
            reason = unresolved_reason(case, ep_rank, local, declared_routed)

        experts.append({
            "expert_id": f"routed/{index}",
            "expert_index": index,
            "kind": "routed",
            # `fused_measured`: this expert's work IS inside a measured kernel, but that kernel
            # covers every resident expert at once, so no figure is this expert's alone.
            # `residency_unresolved`: rank or topology is missing, so identity cannot be
            # asserted in either direction — neither resident nor remote.
            # `remote_ep_shard`: executed on another rank; unknown here, not zero.
            "data_state": state,
            "local_slot": slot,
            "resident_on_profiled_rank": bool(resident),
            "measured_by_node_id": ([n["node_id"] for n in routed_nodes]
                                    if state == "fused_measured" else []),
            "time_us": None,
            "reason": reason,
        })

    # --- shared expert(s) ---------------------------------------------------------------
    # Shared experts are replicated on every rank, independent of EP rank identity.
    # An aggregate duration identifies a per-expert time only for one declared shared expert.
    # With multiple shared experts, preserve the measured nodes but leave individual time null.
    for index in range(int(declared_shared or 0)):
        measured = bool(shared_nodes)
        individual = measured and int(declared_shared or 0) == 1
        experts.append({
            "expert_id": f"shared/{index}",
            "expert_index": index,
            "kind": "shared",
            "data_state": ("measured" if individual else "fused_measured") if measured else "source_only",
            "resident_on_profiled_rank": True,
            "measured_by_node_id": [n["node_id"] for n in shared_nodes],
            # Summed across MoE-bearing scopes, matching how each node already aggregates its
            # own invocations. Null when no kernel was attributed, never 0.0.
            "time_us": (round(sum(n["time_us"] for n in shared_nodes
                                  if n.get("time_us") is not None), 4)
                        if individual and any(n.get("time_us") is not None for n in shared_nodes)
                        else None),
            "reason": (
                "Replicated on every rank and executed by its own kernels, so its time is "
                "directly measured rather than fused with the routed group."
                if individual else
                ("The shared-expert nodes aggregate multiple declared experts. "
                 "Their duration cannot identify an individual expert's time.")
                if measured else
                "Declared in the source but no kernel was attributed to it in this capture."
            ),
        })

    resident_count = sum(1 for e in experts if e["resident_on_profiled_rank"])
    unresolved_count = sum(1 for e in experts if e["data_state"] == "residency_unresolved")
    source_only_count = sum(1 for e in experts if e["data_state"] == "source_only")
    return {
        "schema_version": 1,
        "model_id": performance.get("model_id"),
        "report_id": performance.get("report_id"),
        "representative_step": performance.get("representative_step"),
        "declared": {
            "routed_experts": declared_routed,
            "shared_experts": declared_shared,
            "total": (int(declared_routed or 0) + int(declared_shared or 0)) or None,
            "experts_per_token": top_k,
            "source_refs": {
                "n_routed_experts": routed_ref,
                "n_shared_experts": shared_ref,
                "num_experts_per_tok": top_k_ref,
            },
            "source": "model source via stage 1 AST extraction; never inferred from kernel "
                      "shapes, which only ever show this rank's slice",
        },
        "expert_parallelism": {
            "moe_ep_size": ep_size,
            "local_routed_experts": local,
            "residency_evidence": residency_evidence,
            "ep_rank": ep_rank,
            "ep_rank_source": "--ep-rank" if rank_supplied else None,
            # Distinguishes a rank the topology can vouch for from one merely supplied: a UI
            # must not read `ep_rank: 3` as proof that experts 48-63 were profiled.
            "ep_rank_validation": ("observed_topology" if known_rank
                                   else "unverified_without_topology" if rank_supplied
                                   else "not_provided"),
            "resident_expert_indices": (
                [base, base + local - 1] if known_rank else None),
            "identity_note": identity_note(case, ep_rank, local, declared_routed),
            "note": (
                f"{local} of {declared_routed} routed experts have weights on the profiled "
                f"rank. The other {declared_routed - local} execute elsewhere and are declared, "
                "not observed."
                if local and declared_routed else
                "Expert residency could not be established from this capture."
            ),
        },
        "measurability": {
            "separable_per_expert": False,
            "reason": "The resident routed experts execute as one GroupedMatmul over a stacked "
                      "weight, with group_list giving per-expert token counts. The profiler "
                      "reports a single duration for that kernel. Dividing it by token share "
                      "would produce per-expert numbers the hardware never measured.",
            "what_would_be_needed": "Per-expert kernels (unfused MoE), or a profiler that emits "
                                    "per-group timing inside GroupedMatmul.",
        },
        "counts": {
            "declared_total": (int(declared_routed or 0) + int(declared_shared or 0)) or None,
            "resident_on_profiled_rank": resident_count,
            "individually_measured": sum(1 for e in experts if e["data_state"] == "measured"),
            "fused_measured": sum(1 for e in experts if e["data_state"] == "fused_measured"),
            "residency_unresolved": unresolved_count,
            "remote_ep_shard": sum(1 for e in experts if e["data_state"] == "remote_ep_shard"),
            # `source_only` is a legal state — a declared shared expert whose kernels fell
            # outside this capture — so it must be counted like the other four. Omitting it
            # made the four counted buckets sum to less than the listed experts, and the
            # validator read that partition gap as a conversion error.
            "source_only": source_only_count,
        },
        "fused_group_nodes": [
            {
                "node_id": n["node_id"],
                "time_us": n.get("time_us"),
                "nops": n.get("nops"),
                "covers_experts": local,
                "note": f"One measurement covering all {local} resident routed experts.",
            }
            for n in routed_nodes
        ],
        "experts": experts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--breakdown", required=True)
    parser.add_argument("--config", help="explicit breakdown config path")
    parser.add_argument("--performance", required=True, help="*_perf_data.json")
    parser.add_argument("--attribution", required=True, help="kernel_attribution.json")
    parser.add_argument("--manifest", help="model_manifest.json; defaults to "
                                           "<breakdown>/model_manifest.json")
    parser.add_argument("--ep-rank", type=int,
                        help="expert-parallel rank this capture came from. Resolves WHICH "
                             "global expert indices are resident, but only when the capture "
                             "also reveals the local expert count; a negative rank or one "
                             "beyond the observed moe_ep_size is rejected. Without it only "
                             "the count is reported, since the capture does not record it.")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import breakdown_paths

    breakdown_paths.require_breakdown_ready(
        args.breakdown, args.config, "build_expert_inventory.py")
    config = jload(breakdown_paths.config_or_die(args.breakdown, args.config))
    performance = jload(args.performance)
    attribution = jload(args.attribution)

    manifest_path = args.manifest or os.path.join(args.breakdown, "model_manifest.json")
    manifest = jload(manifest_path) if os.path.exists(manifest_path) else None

    try:
        inventory = build(config, performance, attribution, manifest, args.ep_rank)
    except ValueError as error:
        # An impossible rank is a caller error, not a capture with no experts: exit non-zero
        # rather than writing an inventory that asserts every expert lives on another rank.
        print(f"ERROR {error}", file=sys.stderr)
        return 2
    if not inventory["declared"]["total"]:
        print("no MoE experts declared in this model; nothing to inventory")
        return 0

    jdump(inventory, args.out)
    counts = inventory["counts"]
    ep = inventory["expert_parallelism"]
    print(f"WROTE {args.out}")
    print(f"declared {counts['declared_total']} experts "
          f"({inventory['declared']['routed_experts']} routed + "
          f"{inventory['declared']['shared_experts']} shared)")
    print(f"moe_ep_size {ep['moe_ep_size']}, {ep['local_routed_experts']} routed experts "
          f"resident on the profiled rank")
    # All five buckets on ONE line, with no informational line printed after it.
    # `run_pipeline.py` records only stdout's last line as this stage's status
    # (`r.stdout.strip().splitlines()[-1]` -> `stages["expert_inventory"]`), so a separate
    # `source_only` note after the summary displaced the whole bucket split from the
    # recorded status whenever `--ep-rank` was passed: `residency_unresolved` is then 0,
    # the actionable NOTE below does not print, and the status ended up being source-only
    # prose instead of `individually measured 0, fused 16, ...`. The unknown-time caveat
    # rides along inline for the same reason; its full wording stays in each expert's
    # `reason` and in the `data_state` table of SKILL.md.
    print(f"individually measured {counts['individually_measured']}, "
          f"fused {counts['fused_measured']}, "
          f"residency unresolved {counts['residency_unresolved']}, "
          f"remote {counts['remote_ep_shard']}, "
          f"source-only {counts['source_only']}"
          + (" (time_us is null, not 0.0)" if counts["source_only"] else ""))
    if counts["residency_unresolved"]:
        # Reuse the inventory's own note instead of restating it: the reason residency is
        # unknown differs by case (no rank, no topology, both, or an indivisible count), and a
        # second hardcoded sentence here would drift from the field a UI actually reads.
        print("NOTE " + ep["identity_note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
