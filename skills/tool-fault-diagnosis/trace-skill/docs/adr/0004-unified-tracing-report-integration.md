# Unified component-chain and Tracing Report integration

**Status: accepted.** The selected-anchor component summary is produced once by `trace-skill`, rendered below the unified report's evidence chain, and linked to a self-contained detailed `tracing-report.html`. During migration the same rendered HTML is also written to `fault-trace.html` for compatibility.

## Context

The initial trace delivery intentionally kept the standalone viewer independent from the existing metric report. Product use now requires a compact component-level entry point in that report, while the detailed timeline still needs substantially more space and interaction than the report's two-column diagnostic layout can provide. Maintaining separate aggregation logic or two independently styled trace viewers would allow evidence strength, component order, and interaction behavior to drift.

## Decision

- `trace-skill` owns the optional, versioned `component_chain` field in `fault-trace.json`. Current generators always emit it; version-1 consumers may continue to accept older artifacts where it is absent.
- Only components observed in the current package become summary nodes. Proven calls stay proven; architecture and current-log support may create an explicitly inferred edge but never a proven one or an architecture-only node.
- Component-chain arrows express normal call or task-dispatch direction. Fault source, direct trigger, propagation, affected, and business-error roles decorate nodes without adding a reverse propagation edge set.
- The unified report receives `component_chain` through a report-data adapter and renders detailed horizontal cards between evidence chain and remedies. It does not read raw logs or import parser/correlation code.
- A component card links to `tracing-report.html` with `view`, `anchor`, `component`, and `event` parameters. Detailed selection falls back event, component, anchor, then report default and exposes invalid targets visibly.
- The detailed report follows the shared report's typography, color, surface, light/dark, responsive, and print contracts while retaining a trace-specific full-width layout.
- One render result is written to canonical `tracing-report.html` and compatibility `fault-trace.html`. The old interface is retained by Git history and the pre-redesign backup, not by a second production code path.

## Consequences

- Report and detailed-view component semantics cannot drift because both consume the same summary and representative event identities.
- Existing callers of `fault-trace.html` continue to work while new integrations can use the canonical filename.
- The trace JSON addition remains backward compatible within schema version 1 because the new field is optional for consumers and strictly validated when present.
- Dashboard-template and metric-builder changes are allowed only at the adapter/rendering seam; evaluation ownership and diagnostic confidence remain unchanged.
- Visual acceptance requires real-package browser checks in addition to unit and schema tests, and the redesign must remain recoverable from the recorded baseline branch and bundle.
