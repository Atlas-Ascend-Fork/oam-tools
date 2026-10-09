# Evidence-Backed Call Spans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge exact duplicate observations, preserve explicit evidence conflicts, and render call spans only for proven matched endpoints.

**Architecture:** A normalization module merges events by a strict semantic fingerprint before correlation. The correlation module derives conflict relationships and dispatch-to-return spans; runtime validation recomputes both artifacts from event evidence, and the offline renderer presents points, span bars, and relationship strengths separately.

**Tech Stack:** Python 3 standard library, JSON Schema, `unittest`, offline HTML/CSS/JavaScript.

## Global Constraints

- All changes remain under `skills/tool-fault-diagnosis/trace-skill/`.
- Deduplication applies only inside one input collection boundary.
- File location and event location do not determine semantic duplicate identity.
- Conflicting observations remain visible and block affected proven relationships and spans.
- Equal timestamps do not establish ordering.

---

### Task 1: Exact duplicate normalization and conflicts

**Files:**
- Create: `scripts/fault_trace_core/normalization.py`
- Modify: `scripts/fault_trace_core/correlation.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `schemas/fault-trace-v1.schema.json`
- Create: `tests/test_spans_and_deduplication.py`

- [x] Prove exact semantic duplicates merge all evidence references.
- [x] Prove same timestamp/correlation observations with incompatible fields remain separate conflict events.
- [x] Block conflict endpoints from proven relationships and validate all derived conflict records.

### Task 2: Matched call spans and completeness

**Files:**
- Modify: `scripts/fault_trace_core/correlation.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `schemas/fault-trace-v1.schema.json`
- Modify: `assets/fault-trace-template.html`
- Test: `tests/test_spans_and_deduplication.py`

- [x] Prove a dispatch/return pair with one execution subject and full stream/task identity creates one duration span.
- [x] Keep unmatched and equal-time endpoints as point events and report `unmatched_span_endpoints`.
- [x] Render matched spans as duration bars distinct from point events and relationship rows.
- [x] Recompute spans during runtime validation so fabricated duration records fail.

### Task 3: Acceptance

- [x] Run all tests, real-package checks, Schema syntax, compile checks, and scope checks.
- [x] Commit and push Issue #7 only after all findings are resolved.
