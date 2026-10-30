# Schema mapping: breakdown v2 → UI JSON

Field-level reference for the conversion. Verified against the Qwen-7B pair:
`perf-skills/breakmodle/output/qwen7b_latest/analysis_config.json` (schema 2)
and the report's `qwen7b_analysis_config.json` (schema `2.1-ui`).

## Top-level keys

| breakdown v2 | UI analysis config | Note |
|---|---|---|
| `schema_version: 2` | `schema_version: "2.1-ui"` | different scales; do not copy the number |
| `model_name` | `model_name` | verbatim |
| — | `model_id` | you choose; must match perf + timeline |
| — | `report_id` | you choose; must match perf + timeline |
| — | `id_namespace` | `model/<model-id>`; every `node_id` derives from it |
| `representative_step` | `representative_step` | verbatim |
| `architecture` | `architecture` | pass through unchanged, including `source_of_truth` and `facts` |
| `trace_scope` | `trace_scope` | pass through; never strengthen an `unknown` |
| `stages` (dict) | `stages` (dict) | reshaped per node, see below |
| `structures.<group>` | `layer_structure.<key>` | folded repeated group |
| `runtime_auxiliary` (list) | `runtime_auxiliary` (list) | reshaped per node |
| — | `source_only_structure` (list) | nodes the capture never observed |
| `excluded_profiler_ops` | — | not a UI owner/fact; stays in the breakdown but counts toward conversion accounting coverage |
| `unmapped_ops` | — | must be empty to convert at all |
| `migration` | — | if present and `legacy_unverified`, refuse |
| `model_flow` | `model_flow` | optional legacy linear flow |
| `dataflow` | `dataflow` | explicit cross-structure graph; supersedes `model_flow` |
| — | `structure_provenance` / `capture_provenance` | required when structure and run data differ in origin |

`architecture` and `trace_scope` pass through because they are already validated
architecture truth. Re-deriving them would discard the breakdown's AST evidence.

## Node shape

Breakdown structural node:

```json
{
  "name": "w1",
  "semantic": "SwiGLU gate projection",
  "code_ref": "modeling_qwen.py:561-571",
  "op_indices": [31],
  "kernels": [{"index": 31, "name": "MatMulV2", "duration_us": 99.5,
               "input_shapes": "1,1,4096;11008,4096",
               "output_shapes": "1,1,11008", "shape_raw": "..."}]
}
```

UI analysis node:

```json
{
  "node_id": "model/qwen-7b/decoder_layers/mlp/w1",
  "semantic_key": "w1",
  "node_kind": "op",
  "metric_scope": "all_observed_instances",
  "name": "w1",
  "semantic": "SwiGLU gate projection",
  "code_ref": "modeling_qwen.py:561-571",
  "instance_indices": [0, 1, "...", 31],
  "mapped_kernels": 32,
  "children": []
}
```

Transformations:

- `name` → `semantic_key` and `name` both.
- `op_indices` / `kernels` → **dropped**; they become `mapped_kernels` (a count)
  and feed perf data and the timeline. Per-kernel rows do not belong in the
  analysis config.
- `node_kind`: `module` when it has children, `op` when it is a leaf,
  `runtime_auxiliary` for runtime items.
- `instance_indices`: `[]` for once-per-step nodes; the full observed list for
  nodes under a repeated group.
- `children`: recurse in declaration order — order is a semantic claim.

## Metric scope

| Scope | Meaning | Typical source |
|---|---|---|
| `aggregate` | sums descendants | container with `children` |
| `all_observed_instances` | leaf repeated across every invocation | leaf under a repeated group |
| `single_instance` | leaf running once per step | leaf under `stages` |
| `sampled_window_context` | sampled device context, not compute | runtime sampler windows |

Overlapping aggregate scopes must not be summed mechanically for time share; the
UI derives share from `total_time_us`.

## Performance record

One per analysis node that carries metrics, keyed by the same `node_id`. Every
key present even when `null`:

```
node_id  module  metric_scope
time_us  time_pct  nops  hbm_mb  gflops
mfu_bf16_pct  mfu_int8_pct
aicore_time_us  aiv_time_us  aicore_time_pct
mac_ratio  mte2_ratio  mte1_ratio  scalar_ratio  fixpipe_ratio
vec_ratio  aiv_mte2_ratio  cube_utilization_pct
aic_total_cycles  aiv_total_cycles
aicore_cycle_time_us  aiv_cycle_time_us
counter_coverage
op_ratio  instance_indices  code_ref  kernel_scope_note
```

`hbm_mb` is logical shape × dtype bytes — a comparison estimate, never measured
traffic, capacity, or the sampled HBM timeline. Say so in `kernel_scope_note`
when the node aggregates across invocations.

### AI Core counters

These come from the `aic_*` / `aiv_*` columns of `kernel_details.csv`, carried
onto every attributed row by `attribute_kernels.py` (which reads
`raw_ops_details.json` for them — `raw_ops.json` holds only identity and
timing). Keep the CSV's own `aic_`/`aiv_` prefixes: an unprefixed `mac_ratio`
reads as if it covered the vector core too, and the AIV pipeline has separate
ratios.

`mac_ratio` versus `mte2_ratio` is the compute-bound versus memory-bound read —
high MAC means the cube is doing math, high MTE2 means it is waiting on loads.
Both are **time-weighted** by the counter time they describe, not flat means: a
2 µs Cast must not weigh as much as an 84 µs MlaPrologV3.

`counter_coverage` reports how many of the node's kernels carried counters at
all. Without it, a ratio computed from 1 of 50 kernels reads as node-wide.

### MoE expert inventory

`<model-id>_expert_inventory.json`, one entry per declared expert (DS3.2: 257).
Not a per-expert breakdown — a statement of what the capture can and cannot say:

```
declared            routed / shared / total / experts_per_token / source_refs
expert_parallelism  moe_ep_size  local_routed_experts  residency_evidence
                    ep_rank  resident_expert_indices  identity_note
measurability       separable_per_expert  reason  what_would_be_needed
counts              declared_total  resident_on_profiled_rank
                    individually_measured  fused_measured
                    residency_unresolved  remote_ep_shard
fused_group_nodes   node_id  time_us  nops  covers_experts
experts[]           expert_id  expert_index  kind  data_state  local_slot
                    resident_on_profiled_rank  measured_by_node_id
                    time_us  reason
```

`data_state` is `measured` (one declared shared expert with attributed kernels),
`fused_measured` (routed group kernels or aggregate nodes covering multiple shared
experts; individual `time_us` is null), `remote_ep_shard` (another EP rank, time
unknown), or `residency_unresolved` (count known, identity not).

`moe_ep_size` comes from the stacked expert weight's leading dimension in the
`GroupedMatmul` inputs. Declared totals come from the manifest facts with their
source refs; never from kernel shapes, which show one rank's slice only.

`time_us` is null on everything except `measured`. The profiler timed the group,
not the member, so a per-expert figure derived from token share would be a
fabrication — enforced by a validator check.

### Device clock

`aicore_freq_mhz` at the top level, with the full `device_profile` block from
stage 1's `device_freq.py`. Two independent sources:

- `declared` — the `AI Core Freq` counter events in `trace_view.json`. Typically
  **two samples for the whole capture**, so it is a nameplate value, not a
  frequency curve.
- `derived` — `cycles / time / cores` per kernel, dense, and the value every
  cycle-derived metric actually depends on. Wins when the two disagree;
  `cross_check.agreement` surfaces a mismatch rather than averaging it away.

The core divisor is the whole trick. `aic_total_cycles` sums every core the
kernel occupied, so `cycles / time` alone yields cores × clock — on a 24-core
kernel that reads as ~44 GHz. `Mix Block Dim` wins over `Block Dim` for the AIV
counters on `MIX_AIC` kernels, where the vector phase ran on a different core
count; using `Block Dim` there reports exactly 2× the true clock.

`aicore_cycle_time_us` is the same quantity as `aicore_time_us` reached by a
different route, so their agreement is the cheapest available check that the
clock and the divisor are both right. `validate_conversion.py` enforces it at 1%,
which is loose enough for counter rounding and tight enough that a wrong divisor
(off by the core count) cannot pass.

A capture without counters is not an error: the clock goes null, every derived
field goes null, and the UI reports unavailable. Never substitute an assumed
frequency — it silently rescales the whole set.

Counter sums intentionally **include** `duplicate_of` rows, unlike duration sums.
For a doubly-reported collective the COMMUNICATION primary carries no counters
and the AIV row carries all of them, so skipping duplicates would discard
measured vector work (6.9% of the step's AIV time on the DS3.2 capture) instead
of de-duplicating it. A validator check asserts at most one row per pair carries
counters, so a future profiler populating both cannot silently double-count.

Sampler-window nodes take `time_us: null` plus a separate
`sampled_window_span_us`. Ordering by duration otherwise lets a non-compute node
win default selection: four 10 ms windows total 39.88 ms of wall clock and
outrank a 19.65 ms decoder aggregate, so the Inspector opens at 0% time share.

## Timeline event

One per attributed kernel, plus one per runtime/sampled window:

```
event_id  op_index  name  op_type  device_id  stream_id  accelerator_core
start_time_us_raw  ts_us  duration_us  end_us  wait_time_us
owner_node_id  instance_index  structure_instance_node_id
submodule  mapping_status  trace_join_status
```

`owner_node_id` must resolve to an analysis node. `instance_index` carries the
layer index for repeated groups. `structure_instance_node_id` identifies the
concrete instance when the representative node is folded — the UI needs it to
compute single-instance core metrics without summing all 32 layers.

`submodule` holds the structural leaf name; keep the capture's original
segmentation label as `capture_submodule` when they differ.

## Graph

`model_architecture_graph.v1` requires nonempty `roots`, explicit `edges`, a
`section/source_architecture` root, and a separate `section/runtime_auxiliary`
root.

Edge derivation — both from declarations, never inferred:

- **Activation edges** from sequential `children` order within a container.
- **Residual/skip edges** from `structures.<group>.branches`:
- **Cross-structure edges** from top-level `dataflow.edges`, resolving each endpoint's
  `structure` and optional `source_port` / `target_port` into graph node ids.

```json
{"name": "attention_residual",
 "inputs": ["block_input", "attn.c_proj"],
 "output": "residual_attn",
 "source_ref": "modeling_qwen.py:623-624"}
```

Each declared `inputs`/`output` pair becomes its own edge with a stable id,
`semanticEdgeType: "residual"`, tensor metadata, and provenance. Retain every
edge identity even when collapse projects several onto the same visible
endpoints; never deduplicate by projected `source->target` alone.

A `branches` entry naming an input the structure does not define is a breakdown
defect — report it rather than dropping the edge.

Per item: `dataState` is `mapped`, `source_only`, or `runtime`; `origin` is
`source`, `hybrid`, or `synthetic`; mapped items carry `backendNodeId` and
`mappingKind`. Source-only items stay `selectable: true` with `sourceRefs`, and
must never carry `backendNodeId` or inherit performance heat.

## Source-only nodes

Keyed by `structure_node_id`, **not** `node_id` — the UI runtime scans for
`node_id` to build its backend index, so using it there would inject a
metric-free node into that index and fail the backend-count check.

```json
{"structure_node_id": "model/qwen-7b/stages/embedding/position_range",
 "name": "position_range",
 "code_ref": "modeling_qwen.py:802-808",
 "data_state": "source_only",
 "reason": "Position arange runs once outside the representative decode step, so no Range kernel falls inside this capture window."}
```

`reason` must be a concrete capture fact. "Not found" is not a reason.

## Cross-file invariants

Verified by `validate_conversion.py` before handing off:

- `model_id`, `report_id`, `representative_step` identical in all three files.
- Analysis and performance `node_id` sets match for every metric-carrying node.
- Every nonempty timeline `owner_node_id` resolves in analysis.
- `sum(mapped_kernels)` over leaves equals the attributed kernel count, which
  equals the timeline's compute-event count; attributed + excluded +
  unattributed equals the raw kernel count.
- No `source_only_structure` entry appears in performance data.
- Every graph `backendNodeId` resolves to an analysis node.
