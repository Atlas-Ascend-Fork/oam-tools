# Host Fault View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse real Host plog and Host kernel formats into a fault-centered, process-scoped Host timeline with auditable exclusions.

**Architecture:** Versioned Host adapters normalize records while preserving raw labels, PID/TID, source evidence, and clock provenance. The pipeline selects a severe anchor, keeps all observed events auditable, limits the rendered view to the anchor process scope, and reports exclusions explicitly.

**Tech Stack:** Python 3 standard library, JSON Schema, `unittest`, offline HTML.

## Global Constraints

- All changes remain under `skills/tool-fault-diagnosis/trace-skill/`.
- Ordinary `ERROR` level alone never creates an anchor.
- Source order and time proximity never create a proven relationship.
- Real source snippets committed as fixtures are minimal and redacted.

---

### Task 1: Versioned Host adapters

**Files:**
- Modify: `scripts/fault_trace_core/parser.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `schemas/fault-trace-v1.schema.json`
- Create: `tests/fixtures/host-real-redacted/`
- Create: `tests/test_host_fault_view.py`

- [x] Add failing tests for segmented-microsecond plog timestamps, PID/TID, raw and normalized components, parser identity, and Host kernel wall/monotonic evidence.
- [x] Implement deterministic adapter detection and normalized Host records.
- [x] Add a failing test proving ordinary real `ERROR` records yield exit 3 while an explicit fatal record is eligible.
- [x] Preserve adapter and severity-rule versions in generated artifacts.

### Task 2: Process-scoped Host view

**Files:**
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `assets/fault-trace-template.html`
- Modify: `schemas/fault-trace-v1.schema.json`
- Test: `tests/test_host_fault_view.py`

- [x] Add a failing test with unrelated concurrent PIDs.
- [x] Emit scope evidence, excluded event IDs/count, and render only selected-scope events.
- [x] Run the committed redacted fixture and available local real package end to end.
- [x] Run all tests, Schema syntax checks, diff checks, and independent review.
- [x] Commit and push Issue #4 after Critical/Important findings are resolved.
