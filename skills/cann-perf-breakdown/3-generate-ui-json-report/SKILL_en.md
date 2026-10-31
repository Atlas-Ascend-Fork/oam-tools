---
name: cann-perf-ui-json-report
description: Generate, refresh, validate, and preview PTO interactive profiling reports from Skill 2 architecture/overlay/binding outputs plus backend analysis, performance, Timeline, raw Chrome Trace, and optional HBM, findings, frequency, operator-detail, and expert-inventory data. Use when creating or repairing report/index.html, synchronizing reusable Skill 3 UI behavior, validating Layer navigation and scoped metrics, diagnosing missing nodes/edges/heat/tooltips/Trace bindings, or producing a standalone file:// report.
---

# Generate UI JSON Report

Render backend and source facts without inventing architecture, performance, ownership, diagnoses, or advice. Keep backend inputs read-only and treat `report/` as a generated runtime.

## Read the relevant contracts

- Read [references/data-contract.md](references/data-contract.md) before changing input paths, schemas, mapping identity, capabilities, or provenance.
- Read [references/input-files.md](references/input-files.md) when identifying which model-side JSON, CSV, Trace, source, or Markdown files Skill 3 reads.
- Read [references/ui-contract.md](references/ui-contract.md) before changing architecture, Layer navigation, Inspector, Operator List, TraceView, HBM, selection, styling, or tooltips.
- Read [references/validation-matrix.md](references/validation-matrix.md) before changing validators, generation transactions, template synchronization, or final acceptance.
- When changing architecture projection or graph rendering, also read the installed `pto-json-architecture-graph` Skill and its architecture contract. Keep the vendored graph validator synchronized.

## Preserve fact boundaries

- Join analysis, performance, normalized Timeline, raw Trace and Skill 2 outputs only through their explicit stable identities.
- Render architecture solely from `model_architecture_graph.v1` roots and edges. Never infer an edge from hierarchy, source order, kernel order, Timeline order, or Trace Flow.
- Make performance and Trace interactions available only to explicitly mapped backend nodes. Keep source-only nodes metric-free and Trace-free.
- Keep runtime auxiliary outside source model dataflow.
- Preserve original item/edge IDs, metadata, tensor fields, constraints, provenance and source references.
- Keep source-authored model labels unchanged when switching UI language.
- Default a new report to Chinese while honoring a saved Chinese/English preference.

## Generate

Prefer a Skill 2 `ui_report_handoff.v1` manifest. New reports require it; legacy reports may retain an existing `report-config.js`.

```bash
rtk node <skill-dir>/scripts/generate-report.mjs \
  --repo <report-repo> \
  --handoff <ui-report-handoff.json> \
  --refresh-template
```

Optional inputs:

```bash
rtk node <skill-dir>/scripts/generate-report.mjs \
  --repo <report-repo> \
  --trace <trace_view.json> \
  --hbm-dir <aligned-hbm-dir> \
  --refresh-template
```

Rules:

- `--refresh-template` replaces reusable runtime UI files but preserves or regenerates the model-specific config and preserves Skill 2 outputs.
- Generate the complete next report transactionally. On any failure, restore the previous report and trace byte-for-byte.
- Require `skill3_adapter: generic` and consume the graph, overlay and bindings emitted by `cann-perf-breakdown-to-ui-json` for every model family.
- Rebuild `report-embedded-data.js`; never edit it manually.
- Missing optional inputs degrade to empty typed data. Missing required inputs fail with a field-specific error.

## Check without writes

```bash
rtk node <skill-dir>/scripts/generate-report.mjs --repo <report-repo> --check
```

`--check` is strictly read-only and cannot be combined with `--refresh-template`, `--trace`, or `--hbm-dir`. It must not create placeholders, rename `index.html`, rewrite manifests, or touch timestamps. For changes to the generator, run:

```bash
rtk node <skill-dir>/scripts/test-generation-safety.mjs --repo <known-good-report-repo>
```

For changes to the Trace view template's large-trace handling, run:

```bash
rtk node <skill-dir>/scripts/test-large-trace-boundaries.mjs
```

## Required deterministic checks

Generation must run:

```bash
rtk node <skill-dir>/scripts/validate-architecture-graph.mjs \
  <repo>/report/outputs/model_architecture_graph.json \
  --source-root section/source_architecture \
  --require-semantic-port-policy
rtk node <skill-dir>/scripts/validate-report.mjs --repo <repo>
rtk node <skill-dir>/scripts/test-layer-report-metrics.mjs --repo <repo>
rtk node <skill-dir>/scripts/test-projected-fanout.mjs --repo <repo>
```

Run Layer, expert, HBM, and expected-graph-feature assertions only when their handoff capabilities apply. A declared capability with missing evidence is a failure; a genuinely inapplicable capability is `not_applicable`, not a fake pass.

Reject undeclared template drift. Permit reviewed per-report deviations only through `ReportRuntimeConfig.templateOverrides`/handoff `template_overrides`.

Write `model_skill_validation_manifest.v2` with separate deterministic and manual states. Deterministic success leaves `overall_status: pending_manual_validation` until browser and visual checks finish.

## Final browser validation

After deterministic checks pass, perform one smoke test at 1440 × 1000 using the canonical report URL and one `file://` smoke when standalone delivery matters. At minimum verify:

- no console/resource errors;
- architecture, Inspector and Trace load current data;
- mapped/source-only/aggregate/runtime selections respect their fact boundaries;
- three non-adjacent Layers update scoped graph badges, Inspector metrics, Sequence events and Flow without changing operator identity;
- declared branches, residuals and Layer-selection bridges remain connected;
- heat legend, localized labels, tooltips, HBM missing state and optional expert projection match the UI contract;
- empty-canvas selection reset and Trace focus/zoom/pan remain functional.

Record browser, file-protocol and visual results in the validation manifest; only then set overall status to passed.

## Failure routing

- Identity, node coverage, Timeline owner or trace-binding mismatch: return a Skill 1/2 data requirement; do not patch backend JSON.
- Missing edge/tensor/provenance, invalid repeat membership, fan-out/fan-in/residual shortfall: return a Skill 2 graph requirement.
- Source lock mismatch: stop and re-extract/review architecture; never update hashes blindly.
- Layout, styling, localization, interaction, selection or runtime transport: fix Skill 3 template and regenerate.
- Preserve unresolved facts as unavailable; never map by leaf-label similarity merely to raise coverage.

Report counts and observed capabilities from current files, never historical examples.
