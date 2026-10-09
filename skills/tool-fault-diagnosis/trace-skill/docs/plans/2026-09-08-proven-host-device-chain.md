# Proven Host And Device Fault Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct only evidence-supported Host/Device relationships and highlight the proven graph reachable from each fault anchor.

**Architecture:** Parser adapters expose normalized explicit correlation identities, interaction semantics, and optional explicit clock-alignment declarations. A pure internal correlation module builds deterministic relationships and alignments; `build_trace()` remains the external interface and derives each view from the resulting proven graph.

**Tech Stack:** Python 3 standard library, JSON Schema, `unittest`, offline HTML.

## Global Constraints

- All changes remain under `skills/tool-fault-diagnosis/trace-skill/`.
- Time proximity, PID/TID equality, component convention, and Device identity alone never create a `proven` relationship.
- `inferred` relationships never enter `highlighted_event_ids`.
- Unaligned clock domains remain separate unless explicit evidence records method, offset, uncertainty, and evidence IDs.
- Existing v1 artifacts without new optional fields remain valid.

---

### Task 1: Explicit correlation normalization

**Files:**
- Modify: `scripts/fault_trace_core/parser.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `schemas/fault-trace-v1.schema.json`
- Create: `tests/test_fault_correlation.py`

- [x] Add failing end-to-end tests for normalized `event_id`, `node_id`, `assertion`, `alarm_raised_time`, `device_id`, `stream_id`, and `task_id` values.
- [x] Implement versioned extraction into optional event `correlation` and `interaction` fields without interpreting absent values.
- [x] Add runtime and Schema validation for correlation values and interaction vocabulary.

### Task 2: Proven and inferred relationships

**Files:**
- Create: `scripts/fault_trace_core/correlation.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `schemas/fault-trace-v1.schema.json`
- Test: `tests/test_fault_correlation.py`

- [x] Add failing tests that pair an explicit Device notification with its Host receipt only when the full event identity matches.
- [x] Add failing tests for same-domain stream/task execution identity and for a timing/component hypothesis that must remain `inferred`.
- [x] Build deterministic relationships with evidence IDs and rule IDs; ambiguous or incomplete matches create no proven edge.
- [x] Segment reused stream/task identities into dispatch-to-return occurrences; records before dispatch and edges across repeated dispatches remain unproven.
- [x] Recompute every candidate view from the bidirectional proven graph, adding cross-scope chain events to visible context while keeping inferred events unhighlighted.

### Task 3: Explicit clock alignment and acceptance

**Files:**
- Modify: `scripts/fault_trace_core/parser.py`
- Modify: `scripts/fault_trace_core/correlation.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `schemas/fault-trace-v1.schema.json`
- Modify: `assets/fault-trace-template.html`
- Test: `tests/test_fault_correlation.py`

- [x] Add a failing test for an explicit alignment declaration carrying source/target domains, signed integer offset, non-negative uncertainty, method, and evidence.
- [x] Add failing mutation tests for dangling domains, missing evidence, invalid uncertainty, and alignment cycles; leave unsupported domains unaligned.
- [x] Render proven and inferred links with distinct offline styles and preserve separate axes for every unaligned domain.
- [x] Run all tests, real-package checks, Schema syntax, `git diff --check`, and independent review.
- [ ] Commit and push Issue #6 only after all Critical/Important findings are resolved.
