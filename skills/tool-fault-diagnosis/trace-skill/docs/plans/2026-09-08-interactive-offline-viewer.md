# Interactive Offline Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a self-contained fault-trace viewer with overview/detail navigation, microsecond zoom and pan, linked evidence selection, and analyst controls.

**Architecture:** The Python renderer emits all normalized entities once with stable data attributes. A dependency-free browser controller derives visibility from the selected anchor, context mode, and filter; one integer-microsecond coordinate remains authoritative while JavaScript changes only pixels per microsecond and scroll position.

**Tech Stack:** Python 3 standard library, semantic HTML, CSS, dependency-free JavaScript, `unittest`, Node VM behavior harness, Playwright visual QA.

## Global Constraints

- All changes remain under `skills/tool-fault-diagnosis/trace-skill/`.
- The artifact makes no network requests and loads no external assets.
- Zoom and pan never modify event or span microsecond coordinates.
- Proven chain visibility is preserved in overview and detail views.
- Controls remain usable from 320px mobile through desktop widths.

---

### Task 1: Overview and detail geometry

- [x] Add RED behavior tests for overview lanes, active viewport, microsecond scale, zoom, pan, points, span bars, and directed connectors.
- [x] Render all entities with shared integer coordinates and update only pixel geometry at runtime.
- [x] Synchronize overview viewport indicators with detail scroll and zoom.

### Task 2: Analyst interaction

- [x] Add RED behavior tests for candidate switching, bounded/full context, text filtering, evidence sorting, and bidirectional selection.
- [x] Implement one viewer state controller shared by timeline marks and tables.
- [x] Preserve keyboard-accessible native controls and selection status.

### Task 3: Acceptance

- [x] Prove generated HTML contains no external resource or network API usage.
- [x] Run all behavior and Python tests plus real-package generation.
- [x] Inspect desktop and mobile screenshots for blank output, clipping, and overlap.
- [x] Commit and push Issue #8 only after all gates pass.
