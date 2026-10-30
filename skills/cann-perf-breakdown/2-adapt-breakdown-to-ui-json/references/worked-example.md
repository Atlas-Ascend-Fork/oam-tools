# Worked example: Qwen-7B

A full run against a real breakdown, with the numbers each step produced. Use it
to check your own run is behaving, and as the shape of the report to write at the
end.

Breakdown: `perf-skills/breakmodle/output/qwen7b_latest` (schema 2, score 99/100,
representative step 2, 1552 kernels).

## Step 1 — readiness

```bash
python scripts/check_breakdown_ready.py \
  --breakdown <breakdown-dir> --out work/readiness.json
```

```
PASS  config is schema v2  — found 2
PASS  config is not an unverified legacy migration  — migration.status='native_v2'
PASS  unmapped_ops is empty
PASS  trace_scope.kind is declared  — found 'full_model'
PASS  validation status passed  — status='passed'
PASS  critique status passed  — status='passed'
PASS  critique validation status passed  — status='passed'
PASS  critique validation clears candidate  — detail.clears_candidate=True
PASS  score formal gates passed
READY  conversion may proceed
```

The gate returns exit 1 with a named blocker list on a `passed_with_warnings`
validation, a `legacy_unverified` migration, a nonempty `unmapped_ops`, a stale
final critique, a targeted-only critique, or any false score gate. A legacy
`semantic_review.json` cannot authorize conversion. Do not convert past a blocker.

## Step 2 — node index

```bash
python scripts/build_node_index.py \
  --breakdown <breakdown-dir> --namespace model/qwen-7b \
  --rename-group QWenBlock=decoder_layers --out work/node_index.json
```

```
nodes 27 (22 leaves)
declared op_indices 64
observed instances 32
  module: 5   op: 21   runtime_auxiliary: 1
```

The `--rename-group` flag matters: the breakdown calls the repeated group
`QWenBlock` after its source class, the report addresses it as
`decoder_layers`. Without the rename, all 18 ids under the group differ from the
report's and nothing downstream lines up. Declare the rename; do not let the
conversion infer a role name from a class name.

## Step 3 — attribution

```bash
python scripts/attribute_kernels.py \
  --breakdown <breakdown-dir> --nodes work/node_index.json \
  --out work/kernel_attribution.json
```

```
kernels 1552/1552 attributed (100.00%)
evidence mix: {'declared_op_indices': 64, 'instance_range_translation': 1488}
instance translation: 1488 claims across 31 non-representative invocations
PASS every kernel attributed exactly once
```

The accounting: 64 kernels claimed directly by the representative invocation's
leaves, 1488 more by translating those offsets onto 31 further invocations
(31 × 48), totalling 1552 with no remainder.

Confirm the translation was legitimate:

```
layers with data: 31 | distinct profiles: 1
每层 kernel 数: 48
```

One distinct profile across all 31 translated layers is the evidence that the
invocations are interchangeable. Two or more profiles means they are not, and the
constant-offset assumption is invalid — investigate rather than proceeding.

Resulting distribution, which should look structurally sensible before you trust
any metric derived from it:

```
256  decoder_layers/ln_1              (32 × 8 norm kernels)
256  decoder_layers/attn/rotary_q
256  decoder_layers/attn/rotary_k
256  decoder_layers/ln_2
 96  decoder_layers/attn/kv_cache_update
 64  decoder_layers/attn/c_attn
 32  decoder_layers/mlp/w1            (one MatMul per layer)
 32  decoder_layers/mlp/w2
 32  decoder_layers/mlp/c_proj
  8  stages/ln_f
  1  stages/lm_head
```

## Step 4 — emit

```bash
python scripts/emit_ui_facts.py \
  --breakdown <breakdown-dir> --nodes work/node_index.json \
  --attribution work/kernel_attribution.json \
  --model-id qwen-7b --report-id qwen-7b/from-breakdown \
  --peak-bf16-tflops 376 --dtype-bytes 2 --out out/
```

```
backend nodes      27
source-only nodes  0
timeline events    1552
total_time_us      19406.92
kernels            1552 across 22 owners
```

`total_time_us` should reconcile with the breakdown's own step total — here
`raw_ops.json` reports `total_duration_us: 19406.9`. A gap means kernels were
dropped or double-counted.

## Step 5 — validate

First complete the UI Skill architecture graph and save it as
`out/outputs/model_architecture_graph.json`. The graph must satisfy the
`model_architecture_graph.v1` contract; validation does not invent a graph or
accept a missing one. If the UI Skill writes another path, pass that path with
`--graph`.

```bash
python scripts/validate_conversion.py --out out/ --attribution work/kernel_attribution.json \
  --graph out/outputs/model_architecture_graph.json
```

```
Conversion is self-consistent.
```

The example output shows the conclusion only. Read the validator's full output
for actual passed and failed counts on the supplied artifacts; additional metadata
can enable further checks. Success
requires zero failures, including the graph-presence check. Injecting six defects —
a mismatched `report_id`, a source-only entry keyed by `node_id`, an empty
`reason`, a dropped `hbm_mb`, a sampler window reporting `time_us`, and an
unresolvable owner — produces six named failures, each pointing at the specific
node.

## Cross-check against a known-good report

Where an existing report covers the same model, compare capture-independent
values. HBM estimate is a pure function of declared shapes and dtype bytes, so it
must match exactly even across different captures:

| Node | This conversion | Reference report |
|---|---|---|
| `decoder_layers/mlp` | `hbm_mb 8262.125` | `hbm_mb 8262.125` |
| `decoder_layers/mlp/w1` | `hbm_mb 2752.9219` | `hbm_mb 2752.9219` |
| `decoder_layers/mlp/w2` | `hbm_mb 2752.9219` | `hbm_mb 2752.9219` |

Time share legitimately differs — 95.16% versus 70.27% for `decoder_layers` —
because the two runs measured different steps (19.41 ms versus 27.97 ms total).
MFU shifts with them. **A matching HBM estimate alongside a differing time share
is the expected signature of a correct conversion of a different capture.** Equal
time shares across different captures would be the suspicious result.

## What to report

State the counts from the produced files, show the zero-remainder accounting
(`1552 = 64 + 31×48`), name the distinct-profile check result, and list any
validator failure with its assertion text and your A/B/C classification. Never
close a failure by generating data the capture does not contain.
