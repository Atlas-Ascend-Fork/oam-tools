# Safe Package Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accept a directory or archive as one bounded collection, inspect safe nested archives through depth two, and expose every parsed, unsupported, orphaned, or rejected evidence item.

**Architecture:** A standard-library package reader yields bounded in-memory entries plus audit records without extracting archives to disk. Parser adapters consume only yielded entries; the pipeline combines reader and parser inventories, preserves orphan text as non-timeline evidence, and records a package-local pseudonym scope in the v1 artifact.

**Tech Stack:** Python 3 `zipfile`, `tarfile`, `io`, `pathlib`, `unittest`.

## Global Constraints

- All files remain under `skills/tool-fault-diagnosis/trace-skill/`.
- Reject absolute paths, parent traversal, symlinks/hardlinks, depth greater than two, per-entry overflow, and cumulative expanded-size overflow.
- Never extract archive entries to the filesystem.
- Rejected and unsupported entries remain visible with package-relative paths and reasons.
- Untimestamped text is never assigned an invented timestamp.

---

### Task 1: Bounded package reader

**Files:**
- Create: `scripts/fault_trace_core/package_reader.py`
- Create: `tests/test_package_ingestion.py`
- Modify: `scripts/build_fault_trace.py`
- Modify: `scripts/fault_trace_core/parser.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `schemas/fault-trace-v1.schema.json`

**Interfaces:**
- Consumes: directory, `.zip`, `.tar`, `.tar.gz`, or `.tgz`; CLI limits `--max-entry-bytes`, `--max-total-bytes`, and `--max-archive-depth`.
- Produces: safe `PackageEntry` values and inventory records with rejection reasons.

- [x] Write and witness failing tests for directory, archive, and depth-two nested archive inputs.
- [x] Implement safe path, link, depth, entry-size, and cumulative-size checks without extraction.
- [x] Write and witness failing tests for every rejection reason and CLI limit.
- [x] Integrate safe entries into parser selection and preserve rejected/unsupported inventory.

### Task 2: Orphan and package-local evidence

**Files:**
- Modify: `scripts/fault_trace_core/parser.py`
- Modify: `scripts/fault_trace_core/pipeline.py`
- Modify: `schemas/fault-trace-v1.schema.json`
- Test: `tests/test_package_ingestion.py`

**Interfaces:**
- Produces: `orphan_evidence`, parse coverage diagnostics, uninspected-evidence gaps, and `metadata.redaction_scope`.

- [x] Write and witness a failing test proving untimestamped fragments remain non-timeline orphan evidence.
- [x] Add evidence hashes, redacted excerpts, line locations, coverage totals, and package-local scope metadata.
- [x] Run all tests, schema syntax validation, diff checks, and an independent review.
- [x] Commit and push Issue #3 only after Critical/Important findings are resolved.
