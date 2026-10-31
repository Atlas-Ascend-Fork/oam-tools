# Model Breakdown to UI Report: Workflow Guide

This guide routes an NPU profiling capture through the three performance skills. It only answers which skill to use next; detailed rules, fields, parameters, and validations remain in each skill's `SKILL.md` and `references/`.

## One-line invocation

```text
Use the three-stage skills/cann-perf-breakdown workflow to break down <capture-dir> for <model-id> and generate two HTML reports.
```

The two HTML reports come from different stages: Stage 1 writes the self-contained breakdown report (`{prefix}_report.html`) and Stage 3 writes the interactive UI report. **Stage 1 is AI work driven by its protocol; no single command runs it from a capture directory.**

One command covers only the deterministic part of Stages 2 and 3, and its input is a completed, gate-approved Stage 1 breakdown directory:

```bash
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/run_pipeline.py \
  --breakdown <stage1-breakdown-dir> --model-id <model-id> --out <output-dir>
```

`--capture-dir <capture-dir>` is optional: pass it only when the trace/HBM data lives elsewhere; it defaults to `--breakdown`.

The entry point starts at the readiness gate, runs every deterministic Stage 2/3 step, and writes `<output-dir>/ui-report/report/index.html`. On success it prints `status: pending_manual_validation` (browser and visual acceptance remain Stage 3 responsibilities); when a stage does not pass it prints `status: failed` with a concrete stage and reason and exits non-zero. It never reproduces Stage 1's mapping, critique, validation, or scoring, and Stage 2 refuses to start when the gate fails.

## Three stages

| Stage | Directory | Input | Output |
|---|---|---|---|
| 1 | `1-perf-breakdown/` (`perf-breakdown-skill`) | profiling data, model source, runtime YAML | schema-v2 breakdown, mapping, validation, critique, and score |
| 2 | `2-adapt-breakdown-to-ui-json/` (`adapt-breakdown-to-ui-json`) | an approved Stage 1 bundle | UI facts, architecture graph, overlay, trace bindings, and handoff |
| 3 | `3-generate-ui-json-report/` (`generate-ui-json-report`) | Stage 2 handoff and trace data | validated interactive report runtime |

The numeric directory names describe execution order. Runtime lookup must use the unique `name` in each skill's frontmatter.

## Choose a starting stage

| Available input | Start at |
|---|---|
| profiling capture and model source | Stage 1 |
| approved `analysis_config.json` and score | Stage 2 |
| analysis, performance, and timeline JSON files | Stage 3 |
| an existing report that needs trace refresh or UI changes | Stage 3 (local refresh) |

## Stage gates

Stage 1 must provide a passed validation report, a convertible score, and an empty `unmapped_ops` list before Stage 2 can start. Stage 2 must pass conversion validation and keep `model_id`, `report_id`, and `representative_step` consistent before Stage 3 can start.

`awaiting_ai_mapping` and `needs_iteration` are Stage 1 statuses (`run_breakdown.py`, `score_breakdown.py`), not outputs of the pipeline entry point. The entry point prints `pending_manual_validation` on success and `failed` with a concrete stage and reason otherwise. Do not infer completion from an exit code alone — read the printed status object and the handoff.

## Data rules

Keep `trace_view.json` with the profiling CSV from collection time because Stage 3 requires it. `perf_data.json` and `timeline.json` are Stage 2 inputs to Stage 3, not Stage 3 outputs. Source code is the architecture authority; trace data can only provide runtime evidence and must not invent missing layers or pipeline ranks.

## Selecting a capture when several ranks are present

A capture directory that holds one subdirectory per rank contains several `trace_view.json` files. The conversion entry point discovers capture files recursively under `--capture-dir` and **accepts only a unique automatic candidate**:

| Discovery result | Behaviour |
|---|---|
| exactly one file | used as is |
| several files | prints a `status: failed` JSON with `stage: conversion_inputs` and a `candidates` list of every path, then exits non-zero |
| `--trace <path>` given | the explicit path wins; no discovery happens and the unique-candidate rule does not apply |

A multi-rank directory therefore requires `--trace` to name the rank being analysed. The script never picks the lexicographically first hit for you, because the report then could not prove it used the intended capture.

`kernel_details.csv` is not discovered by this entry point: Stage 1 names it explicitly with `1-perf-breakdown/scripts/run_breakdown.py --csv <file>`. `--csv` is not an option of the conversion entry point, so do not pass it there.
