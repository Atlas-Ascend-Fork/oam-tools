# Model Breakdown to UI Report: Workflow Guide

From one NPU profiling capture to one interactive performance report, three skills are used in order.

**This file only answers "which skill comes next".** How each stage works, which parameters to pass, how fields are defined, and how to write assertions all live in that skill's own `SKILL.md` and `references/`.

**To change the workflow, change the corresponding skill file, not this one.** Every detail written here can go stale; the skill files are the single source of truth.

---

## One-line invocation

```text
Use the three-stage skills/cann-perf-breakdown workflow to break down <capture-dir> for <model-id> and generate two HTML reports.
```

The two HTML reports come from different stages: Stage 1 writes the self-contained breakdown report (`{prefix}_report.html`), Stage 3 writes the interactive UI report. **Stage 1 is AI work executed against its protocol; no single command can run it from a capture directory.**

One command covers only the deterministic part of Stages 2 and 3, and its input is a Stage 1 breakdown directory that is complete and has passed the gate:

```bash
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/run_pipeline.py \
  --breakdown <stage1-breakdown-dir> --model-id <model-id> --out <output-dir>
```

`--capture-dir <capture-dir>` is optional: pass it only when the trace/HBM data lives elsewhere; it defaults to `--breakdown`.

It starts at the readiness gate, runs every deterministic Stage 2/3 step, and writes `<output-dir>/ui-report/report/index.html`. On success it prints `status: pending_manual_validation` (browser and visual acceptance still belong to Stage 3); when any stage does not pass it prints `status: failed` with the concrete stage and reason, and exits non-zero. It never reproduces Stage 1's mapping, critique, validation, or scoring — if the gate fails, Stage 2 refuses to start.

Role names of repeated layer groups must be declared explicitly; deriving them heuristically from class names is not allowed:

```bash
  --rename-group <source-class-name>=<report-role-name>     # repeatable
```

Statuses such as `awaiting_ai_mapping` / `needs_iteration` belong to Stage 1 (`run_breakdown.py`, `score_breakdown.py`), not to this entry point's output.

---

## Selecting a capture when several ranks are present

When one capture holds a directory per rank, there are several `trace_view.json` files. The conversion entry point discovers capture files recursively under `--capture-dir` and **accepts only a unique automatic candidate**:

| Discovery result | Behaviour |
|---|---|
| exactly one file | used as is |
| several files | prints a `status: failed` JSON whose `stage` is `conversion_inputs` and whose `candidates` lists every path, then exits non-zero |
| `--trace <path>` given | the explicit path wins; no discovery happens and the unique-candidate rule does not apply |

A multi-rank directory therefore requires `--trace` to name the rank being analysed. The script never picks the lexicographically first hit for you — the report then could not prove it used the intended capture.

`kernel_details.csv` is not discovered by this entry point: Stage 1 names it explicitly with `1-perf-breakdown/scripts/run_breakdown.py --csv <file>`. `--csv` is not an option of the conversion entry point, so do not pass it there.

---

## Where the three skills live

All of them sit under `skills/cann-perf-breakdown/`, numbered by execution order:

```
skills/cann-perf-breakdown/
  1-perf-breakdown/                 SKILL.md scripts/ references/ schemas/ adapters/
  2-adapt-breakdown-to-ui-json/     SKILL.md scripts/ references/
  3-generate-ui-json-report/        SKILL.md scripts/ assets/ references/ agents/
```

The numeric directory names only record the order; each skill's real name is the `name:` field in its own `SKILL.md`, and that is the name to invoke. Below, `<skills>` stands for the `skills/cann-perf-breakdown` directory.

## The whole chain

```
capture artifacts           Stage 1                 Stage 2                     Stage 3
CSV + source + trace  →  perf-breakdown-skill  →  adapt-breakdown-to-ui-json  →  generate-ui-json-report
                         breakdown + attribution    4 UI facts                   report/ runtime + interaction
```

| Stage | Directory / skill name | Input | Output |
|---|---|---|---|
| 1 | `<skills>/1-perf-breakdown`<br>`perf-breakdown-skill` | profiling CSV, model source, runtime YAML | `analysis_config.json`, `raw_ops*.json`, breakdown HTML |
| 2 | `<skills>/2-adapt-breakdown-to-ui-json`<br>`adapt-breakdown-to-ui-json` | Stage 1 artifacts | `*_analysis_config.json`, `*_perf_data.json`, `*_timeline.json`, `model_architecture_graph.json`, `architecture_overlay_map.json`, `trace_bindings.json`, `hbm_series.json` (a real series when HBM samples are found, a schema-valid empty placeholder when they are not) |
| 3 | `<skills>/3-generate-ui-json-report`<br>`generate-ui-json-report` | Stage 2 artifacts + `trace_view.json` | `report/` runtime (`report-config.js`, `report-embedded-data.js`), `operator_details.json`, `validation_manifest.json`, `metrics_findings.json` and `expert_inventory.json` under `outputs/` (the last two written as empty placeholders when no source is found), plus `hbm_series.json` rewritten when `--hbm-dir` is passed |

Entry point of each stage (details live in the respective `SKILL.md`; this is only for orientation):

```bash
# Stage 1: validation and scoring (the breakdown itself is AI work against the protocol, not one script)
python3 <skills>/1-perf-breakdown/scripts/run_validation.py  ...
python3 <skills>/1-perf-breakdown/scripts/score_breakdown.py ...

# Stage 2: five steps, fixed order
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/check_breakdown_ready.py ...
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/build_node_index.py      ...
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/attribute_kernels.py     ...
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/emit_ui_facts.py         ...
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/validate_conversion.py   ...

# Stage 3: needs node, --repo is mandatory
node <skills>/3-generate-ui-json-report/scripts/generate-report.mjs --repo <report-repo> ...
```

---

## Which stage to start from

Pick the entry point from what you already have.

| You have | Start at |
|---|---|
| only a profiling capture and the model source | Stage 1 |
| `analysis_config.json`, and validation and scoring already passed | Stage 2 |
| the analysis / perf / timeline JSON files | Stage 3 |
| a report, and you only want to add raw trace or refresh the frontend | Stage 3 (local refresh) |
| a report, and you want to change presentation or interaction | edit `report/` directly; do not use this chain |

## Stage gates

If the previous stage is not in place, the next one must not start. Judge by files, not by impression.

**Stage 1 → Stage 2**

```
validation_report.json    status: passed (exactly passed; passed_with_warnings does not pass the gate)
critique_report.json      status: passed, and its recorded config SHA256 matches the current config
critique_validation.json  status: passed and detail.clears_candidate: true
breakdown_score.json      convertible: true (status expresses the evidence level; do not hardcode passed)
analysis_config.json      unmapped_ops: [], schema_version: 2, trace_scope.kind declared
```

A non-empty `unmapped_ops`, a failed score, a critique review that did not pass, or a critique whose hash binding no longer matches the current config: Stage 2's readiness gate refuses outright. Do not work around it.

**Stage 2 → Stage 3**

Stage 2's conversion validation passes, and `model_id` / `report_id` / `representative_step` are identical across the three JSON files.

**One thing to get right at capture time**

Stage 1 does not use `trace_view.json`, but it must be kept in the same batch as the CSV — Stage 3 requires it and it cannot be recovered afterwards. This is where the whole chain breaks most easily.

---

## Three easy wrong turns

**`perf_data.json` and `timeline.json` are not generated by Stage 3.**

They are Stage 3's **inputs**, produced by Stage 2. `model_architecture_graph.json` / `architecture_overlay_map.json` / `trace_bindings.json` are written by Stage 2 as well; Stage 3 only reads and validates them (a missing `trace_bindings.json` is a hard error). What Stage 3 writes into `outputs/` itself is `operator_details.json`, `validation_manifest.json`, the optional `metrics_findings.json` / `expert_inventory.json` (written as empty placeholders when no source is found), and `hbm_series.json` **only when `--hbm-dir` is passed**; `report-config.js` / `report-embedded-data.js` land in the `report/` root, not in `outputs/`. Asking Stage 3 to generate those three Stage 2 files is wasted effort.

`hbm_series.json` and `report-config.js` are written by both stages, in the order "Stage 2 first, Stage 3 overwrites":

- `hbm_series.json`: Stage 2 calls Stage 3's `build-hbm-data.mjs` to write a real series when it finds the four HBM samples (`hbm_bandwidth_timeline.csv`, `hbm_occupancy_timeline.csv`, `sample_op_mix.csv`, `hbm_summary.json`), and falls back to a schema-valid empty placeholder when it does not; Stage 3 rewrites it with the same script only when `--hbm-dir` is passed, and never writes it in `--check` mode. So "the panel is an empty series" can mean either that Stage 2 found no samples or that a standalone Stage 3 rebuild was not given the directory.
- `report-config.js`: Stage 2 writes one version through `build_overlay_and_config.py`, and Stage 3 regenerates it from `ui-report-handoff.json` (normalizing the legacy version in place for older reports that have no handoff). Change the source the handoff is built from rather than editing the finished file after Stage 2.

`report-embedded-data.js` is written by Stage 3 only.

**The HTML at the end of Stage 1 is not the Stage 3 report.**

Stage 1 produces a self-contained breakdown report, Stage 3 produces the interactive UI report. Different skills generate them and their fingerprints differ. Getting the interactive report requires running both Stage 2 and Stage 3.

**Code is the architecture authority; trace is used one way only.**

`modeling_*.py` / `config*.py` decide what structure the model has. Trace can only falsify, never adjudicate: a kernel the trace ran that has no attribution → the breakdown is wrong; scalars such as layer count, hidden size, and expert count can never be adjudicated by trace, because it may cover a single step and kernel widths are post-parallel-split quantities.

When the checkpoint `config.json` is unreachable, code wins: record an evidence gap and lower the manifest confidence, but do not block the flow. A disagreement of the form "code says N layers, trace observed M layers" is not an open problem — it is an existing conclusion. Structural nodes the capture did not observe go through the source-only mechanism (details in Stage 2's SKILL.md): they stay visible and selectable in the architecture graph, just without metrics.

---

## Which file to look at when something is wrong

| Symptom | Responsible stage | Where to look |
|---|---|---|
| operator coverage below 100% | 1 | `validation_report.json` |
| layer count / architecture scalar validation failed | 1 | the confidence and gap records in `model_manifest.json` |
| critique review did not pass, or its config hash no longer matches | 1 | `critique_validation.json`, `critique_report.json` |
| Stage 2 refuses to start | 1 | the Stage 1→2 gate items above |
| kernel attribution counts do not add up | 2 | `kernel_attribution.json` |
| node IDs do not match the report | 2 | the role rename declarations for repeated groups |
| timeline owner cannot be resolved | 2 | the conversion validation output |
| HBM panel is an empty series | 2 | the `hbm` stage status printed by `run_pipeline` (which samples were missing and which directories were searched); once they are supplied, re-run Stage 2 with `--hbm-dir`, or pass `--hbm-dir` to Stage 3 to rebuild that file alone |
| identity / invariant validation failed | 3 | Stage 3's validator output |
| source hash mismatch | 3 | treat it as a request to re-extract the architecture, not as a hash to replace |

General principle: **let the assertion fail.** A broken assertion means the structure changed or the capture differs — report it. Do not relax assertions, drop kernels, redistribute the remainder, or fall back to phase-level owners to make the flow run. Never close a failure by generating data that the capture does not contain.

---

## Presentation traps (after Stage 3)

When the data is right but the interface reads wrong, it is usually one of these. All of them are rendering layer: change `report/`, do not go back and touch the backend JSON.

- **Operator share list truncated** — rendering only the top N makes the list sum to less than 100%. Render all of them, or fold the remainder into "other N kinds, X%".
- **Parent and child percentages mixed into one flat list** — a flat array sorted by descending duration puts containers and their children on the same visual level, so adding them up necessarily exceeds 100%. Build a tree by path depth and show children as a percentage of their parent.
- **Inconsistent denominators** — the sum of kernel times differs from end-to-end wall time by the launch gap. Once a denominator is chosen, state it in the label, or make the gap an explicit node.
- **Aggregate counts read as a single instance** — kernel counts on a collapsed repeated group are totals over the whole step. Write them as `<per layer> × <instances> = <total>`.
- **Empty groups silently disappear** — when the data shape does not match the tree-building assumption, a group that is empty after filtering is dropped entirely and the interface shows no difference.

When the backend schema is inconsistent, report a backend requirement; do not patch it in the frontend.

---

## What to say at delivery

Report the actual numbers from the artifact files: node count, mapped versus source-only, kernel count and attribution coverage, timeline event count, `total_time_us`. Show the zero-remainder account explicitly (`<total> = <declared> + <instances> × <per-instance>`) so the split is auditable.

When another known-good report exists for the same model, compare the capture-independent values: `hbm_mb` is a pure function of the declared shapes and dtypes and must be exactly equal across captures, while time shares legitimately differ. **Equal `hbm_mb` with different time shares is the expected signature of having correctly converted a different capture.**
