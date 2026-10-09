# Bounded Context Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound non-chain context around every fault candidate while preserving the complete proven chain and reporting all exclusions.

**Architecture:** Context slicing remains deterministic in the trace core. Process partitions retain reusable scope membership; each view records requested and effective bounds and materializes event IDs only when its bounded slice differs from the shared partition.

**Tech Stack:** Python 3 standard library, JSON Schema, `unittest`.

## Global Constraints

- All changes remain under `skills/tool-fault-diagnosis/trace-skill/`.
- Defaults are 1,000,000 us before, 100,000 us after, and 20,000 non-chain events.
- Window and count limits never remove the anchor or a reachable `proven` event.
- CLI overrides are non-negative integers and apply independently.

---

### Task 1: Deterministic bounded views

- [x] Add RED tests for inclusive default bounds, nearest-event limiting, and out-of-window proven-chain preservation.
- [x] Add a versioned `context_window` record to every view and the selected diagnostics.
- [x] Preserve shared partitions when no view-specific materialization is needed.

### Task 2: Contract and CLI

- [x] Add RED tests for three independent CLI overrides and invalid negative values.
- [x] Validate window cross-references and counts in both runtime validation and JSON Schema.
- [x] Show selected-window truncation and bounds in the offline viewer summary.

### Task 3: Acceptance

- [x] Run the full unit suite and both real package paths.
- [x] Confirm the SIGABRT default non-chain context does not exceed 20,000 events.
- [x] Commit and push Issue #9 after all gates pass.
