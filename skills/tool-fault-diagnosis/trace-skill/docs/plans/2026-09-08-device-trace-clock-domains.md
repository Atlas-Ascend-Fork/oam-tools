# Device And CANN Trace Clock Domains Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse supported Device slog and CANN stackcore Trace evidence without inventing Device identity mappings or Host/Device clock alignment.

**Architecture:** Extend the versioned adapter registry with a Device common-log adapter and a file-level stackcore adapter. Normalized records carry location, explicit clock domain, optional logical/physical Device identities, and mapping evidence. The renderer creates one labelled axis per observed clock domain while the selected view continues to hide out-of-scope events.

**Tech Stack:** Python 3 standard library, JSON Schema, `unittest`, offline HTML.

## Global Constraints

- All changes remain under `skills/tool-fault-diagnosis/trace-skill/`.
- Device paths never fall through to a Host adapter.
- A logical/physical mapping is `proven` only when one source record explicitly states both identities.
- Host wall, Device wall, and Device boot-relative domains remain unaligned (`aligned_to: null`).
- Ordinary `ERROR` records do not become fault anchors by level alone.

---

### Task 1: Device common-log adapter

**Files:**
- Modify: `scripts/fault_trace_core/parser.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `schemas/fault-trace-v1.schema.json`
- Create: `tests/fixtures/device-trace-redacted/`
- Create: `tests/test_device_trace_domains.py`

- [x] Add a failing real-format test for Device wall-clock records, physical ID from `dev-os-5`, and explicit `local device id = 0, physical device id = 5` mapping evidence.
- [x] Add a failing test for a `1970` event record with `[9.621873]` boot-relative evidence and a distinct Device boot clock domain.
- [x] Implement `device-common-slog-v1` normalization with `location: device`, separate identity namespaces, and no inferred mapping on records that do not state both IDs.
- [x] Add runtime and Schema mutations for invalid Device identities, mapping evidence, and clock-domain references.

### Task 2: CANN stackcore Trace adapter

**Files:**
- Modify: `scripts/fault_trace_core/parser.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Test: `tests/test_device_trace_domains.py`

- [x] Add a failing fixture test for `crash task`, PID, TID, `crash reason: signal 6`, and the microsecond timestamp encoded in `stackcore_tracer_*_YYYYMMDDhhmmssffffff.txt`.
- [x] Implement `cann-stackcore-trace-v1` as a file-level adapter that owns its structured header and emits one Host Trace anchor with line evidence.
- [x] Run the complete controlled CANNLab SIGABRT archive and require exit `0`, a Trace-selected anchor, and auditable Device records.

### Task 3: Separate clock-domain axes

**Files:**
- Modify: `assets/fault-trace-template.html`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Test: `tests/test_device_trace_domains.py`

- [x] Add a failing HTML test requiring separate labelled Host wall, Device wall, and Device boot-relative axes with no alignment claim.
- [x] Render one true-scale track per clock domain and place only selected-view events on their own domain track.
- [x] Run all tests, Schema syntax checks, real-package checks, `git diff --check`, and independent review.
- [x] Commit and push Issue #5 only after all Critical/Important findings are resolved.
