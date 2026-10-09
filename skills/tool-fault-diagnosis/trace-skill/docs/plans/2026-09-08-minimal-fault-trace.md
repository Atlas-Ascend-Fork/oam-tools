# Minimal Fault Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a schema-valid `fault-trace.json` and self-contained `fault-trace.html` from one CANN-format Host plog containing a fatal event.

**Architecture:** A small Python CLI scans an input directory, delegates records to a parser, selects the first comparable high-severity fault candidate, builds a versioned trace document, validates its runtime invariants, and renders that same document into an offline HTML template. The first increment deliberately supports point events only; later tickets extend the same contract with safe archives, Device sources, correlations, spans, and interactive controls.

**Tech Stack:** Python 3 standard library, `unittest`, JSON Schema draft 2020-12, embedded HTML/CSS/JavaScript.

## Global Constraints

- Every committed file remains under `skills/tool-fault-diagnosis/trace-skill/`.
- Preserve raw timestamp text and integer microsecond coordinates; never use floating-point milliseconds.
- Do not align different clock domains without explicit evidence.
- A default highlighted chain contains only the selected anchor and events reachable through `proven` relationships.
- Every event retains a package-relative evidence locator, SHA-256 record hash, and redacted excerpt.
- HTML must be self-contained and make no external requests.
- Exit `0` means valid complete or partial artifacts, `2` invalid input, `3` no usable event or anchor, and `4` internal validation or rendering failure.

---

### Task 1: Minimal end-to-end contract

**Files:**
- Create: `tests/fixtures/minimal-plog/fault.log`
- Create: `tests/test_minimal_fault_trace.py`
- Create: `scripts/build_fault_trace.py`
- Create: `scripts/fault_trace_core/__init__.py`
- Create: `scripts/fault_trace_core/parser.py`
- Create: `scripts/fault_trace_core/pipeline.py`
- Create: `schemas/fault-trace-v1.schema.json`
- Create: `assets/fault-trace-template.html`

**Interfaces:**
- Consumes: `python scripts/build_fault_trace.py INPUT --output-dir OUTPUT`
- Produces: `build_trace(input_path: Path) -> dict`, `validate_trace(trace: dict) -> None`, `render_html(trace: dict) -> str`
- Produces: `fault-trace.json` and `fault-trace.html`

- [x] **Step 1: Write the failing CLI integration test**

  Run the CLI against the controlled plog fixture and assert exit `0`, both artifacts, schema version `1.0.0`, `partial` status, one selected fatal anchor, the original microsecond timestamp, a Host wall-clock domain, integer `offset_us`, and evidence path/line/hash fields. Assert that the HTML embeds the trace, has no `http://` or `https://` resources, and displays the anchor on a microsecond timeline.

- [x] **Step 2: Run the focused test and verify RED**

  Run: `py -3 -m unittest tests.test_minimal_fault_trace -v`

  Expected: FAIL because `scripts/build_fault_trace.py` does not exist.

- [x] **Step 3: Implement the minimal plog parser and pipeline**

  Parse records matching the documented CANN form:

  ```text
  [FATAL] RUNTIME(4242,app):2026-09-08-10:11:12.123456 [runtime.cc:77]Process abort, error code=507035
  ```

  Normalize the timestamp as raw text plus `host-wall-unknown-zone` and an integer coordinate relative to the domain origin. Classify only `FATAL`, crash, panic, abort, OOM, reset, uncorrectable exception, and process termination as automatic candidates in this increment. Build one selected view whose highlighted event IDs contain only the anchor.

- [x] **Step 4: Publish and enforce the v1 schema**

  Describe the produced document in `schemas/fault-trace-v1.schema.json`. Implement a dependency-free runtime validator for required fields, types, cross-references, allowed evidence strengths, selected-anchor membership, and integer microsecond coordinates so generation fails before invalid artifacts are written.

- [x] **Step 5: Render a self-contained reference viewer**

  Embed the JSON safely in the HTML, render Host/Device and clock-domain lane labels, draw event points at true integer microsecond coordinates, label the selected fault anchor, and include a compact evidence table. Use only inline CSS and JavaScript.

- [x] **Step 6: Run the focused test and verify GREEN**

  Run: `py -3 -m unittest tests.test_minimal_fault_trace -v`

  Expected: PASS with no warnings.

- [x] **Step 7: Exercise failure exit codes test-first**

  Add separate tests for an unreadable/missing input (`2`) and a readable input with no eligible anchor (`3`), observe both fail, implement the smallest CLI handling, and rerun the module.

- [x] **Step 8: Verify and commit**

  Run:

  ```powershell
  py -3 -m unittest discover -s skills/tool-fault-diagnosis/trace-skill/tests -v
  git diff --check
  ```

  Review the diff against Issue #2 and commit only `trace-skill` paths.

## Self-Review

- Spec coverage: this increment covers the first deterministic Host-plog point-event path, evidence provenance, versioned output, partial status, microsecond coordinate, anchor-only highlight, offline HTML, and exit-code boundaries. Archive safety, Device formats, correlation, spans, advanced interaction, scale limits, and final Skill packaging are assigned to Issues #3-#10.
- Placeholder scan: no implementation placeholder is delegated without a concrete observable test or boundary.
- Type consistency: the CLI, pipeline, validator, JSON Schema, and HTML all consume the same trace dictionary and stable v1 field names.
