# Readable Fault Dashboard Implementation Plan

**Goal:** Rebuild the offline viewer so the first screen exposes the fault anchor and its proven reachable chain, preserves clock-domain truth, and remains usable for large log packages.

## Acceptance gates

- The first screen prioritizes the embeddable fault-centered timeline; summary and evidence areas do not displace the chart and evidence details are collapsed by default.
- A single compact toolbar remains visible above the chart for fault-candidate selection, zoom, context, and locale controls.
- The lane-label column stays fixed while the timeline viewport scrolls horizontally; the timeline supports both drag-to-pan and a native bottom scrollbar.
- Clock panels with no event in the selected proven chain are hidden or collapsed by default and remain available through an explicit "show empty clock domains" control.
- Localized UI labels use Chinese by default, while component names, process names, PIDs, stream identifiers, and raw log fields remain in their source form for traceability.
- A compact fixed legend stays at the upper-right of the timeline and distinguishes the fault anchor, proven chain, inferred relationships, and ordinary context.
- The main axis stays anchor-relative with explicit microsecond or millisecond units; hover and selection details include the relative offset, raw timestamp, and clock-domain identifier.
- Labels are shown by default only for the fault anchor and proven-chain events; ordinary context remains a point or short bar until selected or hovered.
- Connectors are drawn only between visible lanes: proven relationships use thin solid arrows, while explicitly enabled inferred relationships use subdued gray dashed arrows.
- Selecting an event opens evidence details in a collapsible right-side drawer so the primary timeline layout is not pushed downward.
- The evidence drawer overlays the right side of the viewer instead of resizing the timeline canvas; it can be dismissed without changing the current zoom or pan.
- The timeline fills the available viewport height with a stable minimum height; longer evidence and secondary content use page scrolling rather than an independently nested timeline scroll region.
- On narrow embeds, the fixed lane-label column shrinks within a bounded minimum width; long labels are truncated with a hover or selection affordance for the full source name.
- Viewer controls are keyboard accessible: Tab reaches controls and events, Enter or Space selects, and arrow keys pan the timeline when it has focus.
- Chain status must not rely on color alone: combine contrast, line style, and a shape or icon cue so anchor, proven, inferred, and context states remain distinguishable for color-vision differences.
- Large-package loading exposes the selected fault candidate and parse progress before the chart is ready; the timeline area shows an explicit loading state and swaps to the chart when rendering completes.
- Incomplete evidence still renders the verifiable portion of the trace; the viewer labels the artifact as partial and exposes missing sources, unaligned clocks, and excluded evidence without replacing the chart with an empty error state.
- Partial status uses a top-level badge plus local warnings on affected Host/Device panels; each warning can expand to show the missing evidence details.
- Partial status uses an amber warning treatment rather than the red fault-anchor treatment, so evidence incompleteness is not presented as a new failure.
- The viewer is designed as an embeddable trace component for the existing `tool-fault-diagnosis` unified interface. The unified interface will invoke the `trace-skill` parser/adapter first and pass the Schema-validated `fault-trace.json` payload into the component; the browser component will not read raw logs or archives. This phase changes only files under `trace-skill` and does not modify external templates, `eval-skill`, or `metric-skill`.
- The default locale is Simplified Chinese (`zh-CN`), with an in-view switch to English; timeline data, evidence semantics, and exported artifacts are identical across locales.
- Default visibility contains only the selected anchor's `highlighted_event_ids`; context is opt-in.
- Inferred relationships are hidden by default and controlled independently from context.
- Events are grouped by Host/Device, clock domain, component, and process lane; stream identity remains expandable event detail instead of creating a default lane.
- Clock roots that are not aligned are rendered in separate panels with independent axes.
- Every panel has numeric anchor-relative ticks with explicit `us` or `ms` units.
- The complete proven fault chain uses a high-contrast treatment, while the selected fault anchor receives a stronger red marker spanning the relevant lanes.
- Overview markup is bounded by aggregation rather than one node per event.
- Evidence and relationship rows are page-bounded; selecting an event shows focused details.
- The existing `fault-trace.json` contract and self-contained offline output remain compatible.

## TDD sequence

1. Extend viewer tests and the Node behavior harness for the acceptance gates; confirm focused tests fail.
2. Refactor Python rendering helpers to build panel, lane, aggregate, and initial-page markup.
3. Replace the viewer state/render logic with chain-first visibility, independent inferred/context toggles, panel-local geometry, ticks, pagination, and details.
4. Run focused tests after each behavior turns green, then run the complete test and quick-validation suites.
5. Regenerate the supplied SIGABRT report, record HTML/DOM counts, inspect the rendered artifact, and fix any visual or interaction regressions.
6. Self-review the directory-only diff, commit, and push the feature branch.
