---
name: adapt-breakdown-to-ui-json
description: Convert a formally passed perf-breakdown-skill schema-v2 bundle (analysis_config.json, final critique, validation, score, and representative-step kernel rows) into the four backend JSON facts that generate-ui-json-report consumes — analysis config, performance data, normalized timeline, and model_architecture_graph.v1. Use when a breakdown has cleared every current Skill 1 hard gate but the UI skill has no inputs yet, when kernels must be attributed to structure nodes without name-similarity matching, when a model has no adapter for this conversion yet, or when diagnosing identity, coverage, or schema mismatches between a breakdown and a report.
---

# Adapt Breakdown to UI JSON

Turn one validated schema-v2 breakdown into the four backend facts the report
runtime reads. This Skill owns exactly the gap between
`perf-breakdown-skill` and `generate-ui-json-report`, and nothing else. The
one-shot path also writes the versioned `ui_report_handoff.v1` that formally
transfers those facts to Skill 3.

Inputs are read-only. Every derived file goes to `--out`.

## Scope

```
perf-breakdown-skill        →  THIS SKILL  →  generate-ui-json-report
analysis_config.json           4 UI facts      report/ runtime + HTML
kernel rows (representative)
model source
```

Do not collect profiling data, re-run a model, re-segment layers the breakdown
already segmented, render HTML, or emit optimization advice. Start only from the
five formal Skill 1 files: `analysis_config.json`, `critique_report.json`,
`critique_validation.json`, `validation_report.json`, and `breakdown_score.json`.
Reject `semantic_review.json`, targeted critique files, `passed_with_warnings`,
and legacy score conclusions as formal conversion authority.

## Non-negotiable rules

- **Never map a kernel by leaf-label similarity.** Attribution evidence is the
  breakdown's own `op_indices`, plus exact operator name, operator type, tensor
  shapes, and position within a consecutive run. Both neighbouring Skills forbid
  name-similarity matching; so does this one.
- **Account for every kernel exactly once.** Every raw kernel must be either
  attributed to exactly one evidence-backed node or explicitly present in Skill
  1's validated `excluded_profiler_ops`. Excluded profiler/bookkeeping rows stay
  ownerless and out of UI metrics; they count toward accounting coverage, not
  attribution count. Any other remainder is a defect, not a rounding difference.
- **Let assertions fail.** Segment boundaries are claims about the capture. When
  an assertion breaks, the structure changed or the capture differs — report it.
  Never widen an assertion, drop a kernel, or fall back to a phase-level owner
  to make a run succeed.
- **Do not invent semantic edges.** Emit an edge only where the breakdown
  declares one: `structures.<group>.branches` gives intra-structure residual/skip
  inputs and output; sequential `children` order gives intra-container activation
  flow; top-level `dataflow.edges` gives cross-structure edges and supersedes the
  legacy linear `model_flow`. Fan-out exists only where it is explicitly declared.
- **Do not fabricate owners.** A timeline event either has evidence-backed
  attribution or stays unmapped. Phase-level fallback owners hide missing work.
- **Source-only nodes carry no metrics.** A structure node the capture never
  observed belongs in `source_only_structure` keyed by `structure_node_id`, not
  `node_id`, so it stays out of the backend node index. It stays visible,
  selectable, and metric-free, and must record a concrete `reason`.
- **Keep runtime auxiliary outside model dataflow.** Sampler windows, token
  sampling, and similar runtime facts live in their own root.
- **No diagnoses or advice.** Time, counts, ratios, and shapes only. Diagnostic
  labels belong to the breakdown's `metrics_report.md`; optimization advice
  belongs to `cann-npu-perfanalysis`. Emitting either here is a contract violation.

Read [references/schema-mapping.md](references/schema-mapping.md) before changing
field names or identity rules, and
[references/worked-example.md](references/worked-example.md) for a full run with
the numbers each step produced.

## Identity contract

The UI validator enforces three rules across the four outputs. Satisfy them by
construction, not by patching afterwards.

- One analysis definition and one performance record per backend `node_id`.
- Every performance `node_id` exists in analysis, and every analysis node that
  carries metrics exists in performance.
- Every nonempty timeline `owner_node_id` resolves to an analysis node.

Choose one `id_namespace` (`model/<model-id>`) and derive every `node_id` from
the breakdown's structural path under it. Set `model_id`, `report_id`, and
`representative_step` identically in all three JSON files. When structure and
run data come from different sources, record both provenances explicitly rather
than blending them into one ambiguous id.

## Step 1 — Verify the breakdown is convertible

```bash
python <skill-dir>/scripts/check_breakdown_ready.py \
  --breakdown <breakdown-dir> \
  --out <work-dir>/readiness.json
```

Require all of the following:

- `validation_report.status == "passed"`;
- `critique_report.status == "passed"` and its SHA256 binding matches the selected config;
- `critique_validation.status == "passed"`;
- `critique_validation.detail.clears_candidate == true`;
- `breakdown_score.passed_at_cap == true`;
- `breakdown_score.convertible == true`;
- `breakdown_score.hard_gates.passed == true`;
- `breakdown_score.critique_gates.passed == true`.

Also require schema v2, empty `unmapped_ops`, a declared `trace_scope.kind`, and no
`legacy_unverified` migration. Resolve `analysis_config.json` by default. Accept
`analysis_config_v2.json` only through an explicit `--config` path for old bundles;
never let it override the formal filename automatically.

For a one-shot conversion, pass the completed Skill 1 directory to
`scripts/run_pipeline.py --breakdown <breakdown-dir>`. The pipeline starts at this
readiness gate and does not perform mapping, critique, validation, or scoring itself.
It emits `<out>/ui-report/ui-report-handoff.json`, runs Skill 3's deterministic
generator, and returns `pending_manual_validation`; browser and visual acceptance
remain Skill 3 responsibilities.

## Step 2 — Build the node index

```bash
python <skill-dir>/scripts/build_node_index.py \
  --breakdown <breakdown-dir> \
  --namespace model/<model-id> \
  --rename-group <StructureKey>=<node-name> \
  --out <work-dir>/node_index.json
```

Walk `stages`, `structures.<group>.children`, and `runtime_auxiliary` in
declaration order. For each node emit one entry with a stable `node_id`,
`semantic_key`, `node_kind` (`module` / `op` / `runtime_auxiliary`),
`metric_scope`, `name`, `semantic`, `code_ref`, `instance_indices`,
`mapped_kernels`, and `children`.

A breakdown names a repeated group after its source class (`QWenBlock`) while a
report usually addresses it by role (`decoder_layers`). Declare that rename with
`--rename-group`; never derive a role name from a class name heuristically.

The script refuses a node that declares both `children` and `op_indices` — such a
node would count its own kernels twice, once directly and once through
descendants — and refuses two structural nodes colliding on one `node_id`.

Pick `metric_scope` from what the node actually aggregates:

| Scope | Use when |
|---|---|
| `aggregate` | a container summing descendants |
| `all_observed_instances` | a leaf repeated across every layer invocation |
| `single_instance` | a leaf that runs once per step |
| `sampled_window_context` | sampled device context, never compute time |

A repeated layer group becomes one folded node whose `instance_indices` lists
every observed invocation and whose children aggregate the matching kernels from
all of them. Keep the group's source JSON static; per-layer timing is a runtime
overlay, not a structural fact.

## Step 3 — Attribute kernels

```bash
python <skill-dir>/scripts/attribute_kernels.py \
  --breakdown <breakdown-dir> \
  --nodes <work-dir>/node_index.json \
  --split-rules <rules.json> \
  --out <work-dir>/kernel_attribution.json
```

Three evidence sources, in order of authority:

1. **A leaf's own `op_indices`** — the breakdown already proved these.
2. **`trace_instances[].op_range`** — a repeated group declares one
   representative invocation plus a range per invocation. Equal-length ranges
   make the offset exact, so a leaf owning offset *k* in the representative owns
   offset *k* in every other invocation. This is range arithmetic over declared
   facts, not pattern matching, and it carries the bulk of the work: on Qwen-7B,
   64 directly declared claims translate into 1488 more across 31 invocations for
   1552/1552 coverage.
3. **An asserted split rule** — only for runs the breakdown folded into one leaf
   that the report needs separated.

Unequal invocation spans are a hard error: a constant offset would misattribute,
so the script reports which instance differs instead of translating anyway.

After attribution, confirm every non-representative invocation resolved to one
identical profile. On Qwen-7B all 31 translated layers yield exactly 48 kernels
in the same per-node distribution; more than one distinct profile means the
invocations are not interchangeable and the translation assumption is wrong.

For a folded run that must be split, state the expected profile — operator types
in order, run length — in the rules file so a structural change fails loudly:

```json
{"splits": [{
  "name": "mlp_gate_up",
  "source_node_id": "model/<id>/decoder_layers/mlp/gate_up_proj",
  "expect_length": 4,
  "expect_op_types": ["MatMulV2", "Swish", "MatMulV2", "Mul"],
  "assign": [
    {"target_node_id": "model/<id>/decoder_layers/mlp/w2",         "range": [0, 1]},
    {"target_node_id": "model/<id>/decoder_layers/mlp/activation", "range": [1, 2]},
    {"target_node_id": "model/<id>/decoder_layers/mlp/w1",         "range": [2, 3]},
    {"target_node_id": "model/<id>/decoder_layers/mlp/activation", "range": [3, 4]}
  ]
}]}
```

Read the assignment order off the model source, not off the label. In a SwiGLU
where the first MatMul feeds the activation, that MatMul is the up projection
even when a fused label lists gate first — check which tensor reaches `Swish`.

Handle runs that straddle a layer boundary explicitly rather than truncating
them. Record both labels when the capture's own segmentation name differs from
the structural leaf name: keep the structural name in `submodule` and preserve
the original as `capture_submodule`.

The script fails when any non-excluded kernel is unattributed, any kernel is
attributed twice, an excluded kernel also has an owner, an excluded index is
absent from the raw rows, or an owner is absent from the node index.

## Step 4 — Emit the backend facts

```bash
python <skill-dir>/scripts/emit_ui_facts.py \
  --breakdown <breakdown-dir> \
  --nodes <work-dir>/node_index.json \
  --attribution <work-dir>/kernel_attribution.json \
  --model-id <model-id> --report-id <report-id> \
  --peak-bf16-tflops <value> --dtype-bytes <value> \
  --out <out-dir>
```

Writes `<prefix>_analysis_config.json`, `<prefix>_perf_data.json`, and
`<prefix>_timeline.json`. It refuses to run below 100% accounting coverage
(`attributed + excluded`). Only attributed rows feed metrics and timeline events.

A node with zero attributed kernels is emitted into `source_only_structure` with
a generated `reason`; replace that text with the concrete capture fact once you
know it, because "no kernel attributed" describes the symptom, not the cause.

The fourth fact — `outputs/model_architecture_graph.json` — needs the declared
`branches` and top-level `dataflow`. Build it with the UI Skill's
`build-source-overlay.mjs`, or emit it directly per
[references/schema-mapping.md](references/schema-mapping.md) § Graph. Derive
activation edges from sequential `children` order and residual edges from
`structures.<group>.branches`, then resolve cross-structure endpoints and optional
ports from `dataflow.edges`, one edge identity per declaration. Never infer an
edge the breakdown does not declare.

Metrics come from the attributed kernels only:

| Field | Definition |
|---|---|
| `time_us` | sum of attributed kernel durations |
| `time_pct` | `time_us / total_time_us × 100` |
| `nops` | count of attributed kernels |
| `hbm_mb` | logical shape × dtype bytes; a comparison estimate, never measured traffic |
| `gflops` | from declared shapes |
| `mfu_bf16_pct` / `mfu_int8_pct` | mapped effective compute over declared peak; `null` when unavailable |
| `aicore_time_us`, `aiv_time_us`, `aicore_time_pct` | AI Core / AI Vector counter time, and cube time as a share of wall |
| `mac_ratio`, `mte2_ratio`, `mte1_ratio`, `scalar_ratio`, `fixpipe_ratio` | cube pipeline breakdown, time-weighted |
| `vec_ratio`, `aiv_mte2_ratio` | vector pipeline breakdown, time-weighted |
| `cube_utilization_pct` | cube occupancy, time-weighted |
| `aic_total_cycles`, `aiv_total_cycles` | raw core-cycle totals; no clock needed |
| `aicore_cycle_time_us`, `aiv_cycle_time_us` | cycles re-expressed as time; `null` without a known clock |
| `counter_coverage` | how many of the node's kernels carried counters at all |
| `op_ratio` | operator-type time share within the node |

Counter fields come from the `aic_*` / `aiv_*` CSV columns via
`raw_ops_details.json` — `raw_ops.json` has only identity and timing, so
attribution must read the details file or every counter metric emits `null`.
Ratios are **time-weighted** by the counter time they describe; a flat mean lets
a 2 µs Cast outweigh an 84 µs MlaPrologV3. `mac_ratio` vs `mte2_ratio` is the
compute-bound vs memory-bound read.

The perf JSON also carries `aicore_freq_mhz` plus a `device_profile` block from
stage 1's `device_freq.py`: the clock declared by the trace's `AI Core Freq`
counter (usually just two samples — a nameplate, not a curve) cross-checked
against a per-kernel derivation from `cycles / time / cores`. Derived wins;
a mismatch is reported, never averaged away. Always divide cycle counters by the
core count (`Mix Block Dim` for AIV on mixed kernels, else `Block Dim`) —
`aic_total_cycles` is core-summed, so skipping it overstates the clock by the
core count, ~22× on the DS3.2 capture.

Emit every key even when the value is `null`. A missing key and a null value are
different claims; `–` in the UI must mean unavailable, never zero. This applies
hardest to the clock: a capture profiled without counters reports `null`, never
an assumed frequency, because every cycle-derived metric divides by it.

## MoE expert inventory

`build_expert_inventory.py` writes `<model-id>_expert_inventory.json` for any
model declaring experts. It lists **every** declared expert (DS3.2: 256 routed +
1 shared = 257) and gives each a `data_state` saying precisely what the capture
measured. Two independent reasons keep 257 declared experts from becoming 257
measurements, and they must not be conflated:

| `data_state` | Meaning |
|---|---|
| `measured` | one declared shared expert with attributed kernels and a separable duration |
| `fused_measured` | routed experts in a measured group, or multiple shared experts covered by aggregate nodes; individual `time_us` is null |
| `remote_ep_shard` | executes on another expert-parallel rank; time **unknown**, not zero |
| `residency_unresolved` | resident count known, global identity not — see below |

**Expert parallelism.** With `moe_ep_size = N` only `n_routed_experts / N`
experts have weights on the profiled rank. On the DS3.2 capture that is **16 of
256**; the other 240 appear only as the all-to-all that dispatches tokens to
them. `moe_ep_size` is derived from the leading dimension of the stacked expert
weight in the `GroupedMatmul` shapes — an observation from the capture, not a
config assumption. Never read the declared *total* from those shapes: they only
ever show one rank's slice, so doing so under-reports the model by the EP factor.

**Kernel fusion.** The resident experts run as one `GroupedMatmul` over a stacked
weight, with `group_list` giving per-expert token counts and the profiler
reporting a single duration. Per-expert time is not recoverable from it. Dividing
the fused duration by token share would produce numbers the hardware never
measured — a validator check rejects any per-expert `time_us` on a non-`measured`
expert for exactly this reason.

**Residency identity needs the rank.** Rank *r* owns
`[r*local, (r+1)*local)`, and msprof has no reason to record `ep_rank`. Without
`--ep-rank` the resident *count* is known but the *identities* are not: defaulting
to rank 0 would assert experts 0–15 ran when the capture may be rank 5's
(80–95). So those entries report `residency_unresolved` and no expert is claimed
resident. Pass `--ep-rank` to resolve.

Never let a non-compute node win default selection. A sampler-window node's wall
clock is not compute time: set `time_us: null` and keep the span in a separate
field such as `sampled_window_span_us`. Ordering nodes by duration otherwise
puts a 0%-time-share node first and the Inspector opens empty.

For the graph, require `schema_version: model_architecture_graph.v1`, a
`section/source_architecture` root, a separate `section/runtime_auxiliary` root,
nonempty `roots`, and explicit `edges`. Derive activation edges from sequential
`children` order and residual edges from `branches`, preserving each declared
`inputs`/`output` pair as its own edge identity with tensor metadata and
provenance. Preserve `dataflow.edges` as explicit cross-structure edges; resolve
their `structure` plus optional `source_port` / `target_port` without reducing a
fork or join to `model_flow`. Mark every item's `dataState` (`mapped` /
`source_only` / `runtime`) and `origin`.

## Step 5 — Validate the conversion

```bash
python <skill-dir>/scripts/validate_conversion.py \
  --out <out-dir> \
  --attribution <work-dir>/kernel_attribution.json
```

Checks identity consistency across the three JSON files, one definition and one
record per `node_id`, 100% timeline owner resolution for attributed rows,
kernel-count conservation (`attributed + excluded + unattributed = total`), that
no `source_only` node carries metrics, that every required metric key is present,
and that graph edges resolve with tensor metadata and provenance.

Then hand off to the UI Skill's own validators, which are authoritative for the
report:

```bash
node <ui-skill>/scripts/validate-architecture-graph.mjs \
  <out-dir>/outputs/model_architecture_graph.json \
  --source-root section/source_architecture --require-semantic-port-policy
```

## Reporting the result

State the numbers from the produced files: node count, mapped versus
source-only, attributed and excluded kernel counts, accounting coverage,
timeline events, and `total_time_us`. Show the zero-remainder accounting
explicitly, for example `1218 total = 1217 attributed + 1 excluded + 0
unattributed`, so the segmentation is auditable.

Report failures honestly. A validator that hard-codes another model's node IDs
or module names fails on a correct conversion; say which assertion and why
rather than renaming nodes to satisfy it. Never suppress a failure by generating
data the capture does not contain.

## Handle failures

### Kernel count mismatch

Do not redistribute the remainder. Find the run whose assertion is wrong, print
its operator types and shapes, and compare against the model source. A changed
fusion or a different capture is the usual cause.

### Node not in index

The breakdown declares a structural path the walk missed, or two nodes collide
on one `node_id`. Fix the namespace derivation; never merge two distinct
structural nodes into one id.

### Timeline owner unresolved

Every event needs an owner that exists in analysis. Sampled or runtime events
get an explicit runtime-auxiliary node — not a phase-level fallback, and not a
compute node they do not belong to.

### Metrics present on a source-only node

The node was observed after all, or it was misclassified. Decide from capture
evidence: move it into the mapped set with real metrics, or remove the metrics
and keep the documented `reason`.

### Adapter missing for a model family

Write the segmentation assertions from the model source and the breakdown's
`branches`, and keep them as executable assertions rather than comments. Do not
copy another family's expected profile; a Dense SwiGLU run and an MoE expert run
have different shapes and lengths.
