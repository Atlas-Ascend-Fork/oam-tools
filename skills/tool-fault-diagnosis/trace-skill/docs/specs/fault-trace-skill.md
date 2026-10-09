# Fault Trace Skill Specification

## Problem Statement

CANN 故障分析目前能够清洗日志、识别错误、评估诊断可信度并生成静态故障报告，但缺少一个面向故障时刻的组件调用时序视图。现有首错时序主要是少量错误里程碑，不能表达调用开始与结束、组件间关联、Host/Device 并发、不同时间源、微秒级时间间隔或证据来源之间的冲突。

分析人员需要从一次日志采集包中回答以下问题：故障锚点是什么、故障前后哪些组件实际参与了该执行、Host 下发与 Device 活动是否属于同一调用、哪些关系有直接证据、哪些只是推断、以及每个结论能否回到原始日志记录核验。当前设计必须避免把时间接近、组件惯例或第一条 `ERROR` 自动解释为因果链或根因。

## Solution

新增独立的 `trace-skill`，与现有 `eval-skill` 和 `metric-skill` 并列。它接收代表单次采集或复现边界的日志目录或归档，使用版本化解析器适配器将 Host `plog`、CANN Trace、Device 维护日志、Host kernel 日志以及可选 Host `syslog` 转换为规范化事件，建立可审计的时钟域、执行范围、组件身份、调用跨度和关系模型。

技能生成稳定的 `fault-trace.json`，其中包含由选定锚点证据派生的 `component_chain` 摘要；同一渲染器生成完全离线的 `tracing-report.html` 和内容相同的 `fault-trace.html` 兼容副本。默认视图只突出选定故障锚点通过 `proven` 关系可达的故障链；普通上下文按锚点前 1 秒、锚点后 100 毫秒和 20,000 个非链路事件限制。查看器提供从左到右的组件调用入口、真实比例的水平时间轴、Host/Device 与时钟域泳道、微秒级缩放和平移、可切换故障候选、全量上下文、证据表和来源定位。

所有结论都区分 `observed`、`proven`、`inferred`、`conflict` 和缺失证据。确定性核心负责解析、规范化、去重、时钟处理、关联、切片、Schema 校验和渲染；Agent 只负责编排、解释和可选的候选选择，不能把推断关系升级为默认高亮的已证明链路。

## User Stories

1. As a CANN 故障分析人员, I want to provide a raw log directory or archive, so that I can obtain a fault-centered trace without manually assembling multiple log sources。
2. As a CANN 故障分析人员, I want the input boundary to represent one collection or reproduction, so that events from unrelated packages are never silently correlated。
3. As a CANN 故障分析人员, I want safely readable nested archives to be included, so that an outer collection containing an `asys` archive remains analyzable。
4. As a platform operator, I want archive traversal to reject absolute paths, parent traversal, symbolic links, excessive nesting, and resource overuse, so that untrusted packages cannot escape the analysis boundary or exhaust resources。
5. As a CANN 故障分析人员, I want unsupported or rejected files listed with reasons, so that missing evidence is distinguishable from an empty log。
6. As a CANN 故障分析人员, I want versioned parser adapters selected from path and content signatures, so that parsing is deterministic across CANN releases。
7. As a CANN 故障分析人员, I want a generic parser fallback with parse coverage and unparsed counts, so that unfamiliar files do not block useful analysis or create a false completeness claim。
8. As a CANN 故障分析人员, I want multiline stack and error continuations attached only when parser grammar proves their ownership, so that stack text is preserved without inventing timestamps。
9. As a CANN 故障分析人员, I want unassigned untimestamped fragments retained as orphan evidence, so that potentially useful text remains auditable without becoming a fabricated timeline event。
10. As a CANN 故障分析人员, I want duplicate records within one package merged only when strict semantic fingerprints match, so that copied records do not duplicate the timeline while distinct repeated calls remain visible。
11. As an auditor, I want every merged event to retain all source references, so that deduplication never loses provenance。
12. As an auditor, I want conflicting fields to prevent merging and remain visible as evidence conflicts, so that source priority cannot silently choose a winner。
13. As a privacy-conscious operator, I want usernames, host names, IP addresses, directory prefixes, and business paths pseudonymized with stable package-local aliases, so that equality within a report is preserved without creating cross-package identity links。
14. As a CANN 故障分析人员, I want logical and physical Device IDs retained in separate namespaces, so that container numbering is not confused with host hardware numbering。
15. As a CANN 故障分析人员, I want logical-to-physical Device mapping marked proven only by explicit metadata or driver evidence, so that uncertain Device mapping does not create false concurrency。
16. As a CANN 故障分析人员, I want timestamps to retain raw text, clock-domain identity, and microsecond precision, so that the display is traceable to the source record。
17. As a CANN 故障分析人员, I want Host, Device wall-clock, boot-relative, and unknown-zone times kept separate until alignment is proven, so that equal-looking timestamps are not treated as comparable by default。
18. As a CANN 故障分析人员, I want explicit synchronization or validated correlated events to document clock offset, method, and uncertainty, so that cross-domain ordering is explainable。
19. As a CANN 故障分析人员, I want events with equal timestamps and no ordering evidence to overlap or remain order-unknown, so that file order cannot be mistaken for causality。
20. As a CANN 故障分析人员, I want high-severity fault-anchor candidates selected by versioned rules, so that crashes, aborts, OOM, resets, and documented severe errors are eligible while ordinary `ERROR` records are not automatically promoted。
21. As a CANN 故障分析人员, I want an explicit user or `eval-skill` anchor to take precedence, so that an analyst can focus the trace on a known event。
22. As a CANN 故障分析人员, I want candidates in unaligned clock domains shown as domain-local earliest candidates, so that the tool does not fabricate a global earliest fault。
23. As a CANN 故障分析人员, I want an ambiguous anchor selection to produce a usable `partial` artifact with a selector, so that uncertainty is actionable rather than hidden。
24. As a CANN 故障分析人员, I want an execution scope derived from explicit process, session, job, rank, stream, task, and correlation identities, so that unrelated concurrent jobs are excluded from the selected view。
25. As a CANN 故障分析人员, I want processes or Devices admitted across scope boundaries only through proven relationships, so that time proximity alone cannot pull unrelated activity into the chain。
26. As a CANN 故障分析人员, I want ambiguous scope candidates preserved separately from the minimal proven scope, so that I can explicitly switch context without relabelling it as proven。
27. As a CANN 故障分析人员, I want a call span created only from matched start and end evidence with the same correlation identity and execution subject, so that a duration bar never represents an estimated interval。
28. As a CANN 故障分析人员, I want unmatched endpoints shown as point events with a completeness gap, so that incomplete logs remain useful without overstating duration evidence。
29. As a CANN 故障分析人员, I want explicit dispatch, notification, return, and compatible correlation identities to create proven relationships, so that the highlighted chain reflects source-supported interactions。
30. As a CANN 故障分析人员, I want timing and component heuristics represented as visually weakened inferred relationships, so that useful hypotheses are visible without entering the default proven chain。
31. As a CANN 故障分析人员, I want evidence conflicts to block affected proven relationships and spans, so that contradictory records remain unresolved rather than silently reconciled。
32. As a CANN 故障分析人员, I want the default view to highlight only the proven graph reachable from the selected anchor, so that the key fault chain is readable instead of being buried in full-log noise。
33. As a CANN 故障分析人员, I want an optional full-trace context view, so that I can inspect nearby non-chain activity without changing the highlighted chain semantics。
34. As a CANN 故障分析人员, I want the anchor and complete proven chain preserved even when context limits are reached, so that window trimming cannot remove critical evidence。
35. As a CANN 故障分析人员, I want context truncation, effective bounds, and excluded event counts reported, so that the displayed scope is explicit。
36. As a CANN 故障分析人员, I want lanes grouped by Host/Device location and clock domain, then component and process, so that the main view expresses execution ownership without creating one lane per log file。
37. As a CANN 故障分析人员, I want TID, stream, task, rank, and event IDs expandable within lanes, so that detailed correlation is available without making the default chart unreadable。
38. As a CANN 故障分析人员, I want a true-scale horizontal overview timeline, so that microsecond spacing and parallel execution are visually meaningful。
39. As a CANN 故障分析人员, I want a zoomable and pannable microsecond detail timeline synchronized with the overview, so that I can inspect short fault intervals without changing the underlying coordinates。
40. As a CANN 故障分析人员, I want events rendered as points, matched calls as duration bars, and supported interactions as directed connectors, so that point evidence and duration evidence remain distinct。
41. As a CANN 故障分析人员, I want a sortable and filterable evidence table linked to timeline selections, so that visual claims can be traced to package-relative paths, line or byte locations, record hashes, and redacted excerpts。
42. As a CANN 故障分析人员, I want all detected fault-anchor candidates switchable in the viewer, so that the timeline and evidence table refocus consistently on another candidate。
43. As a dashboard integrator, I want a stable versioned JSON Schema, so that the existing dashboard can consume trace data through an adapter without importing parser internals。
44. As a dashboard integrator, I want a self-contained offline HTML artifact, so that the report works in restricted environments without network requests or external assets。
45. As a CANN 故障分析人员, I want incomplete inputs to yield schema-valid `partial` output, so that missing Trace, syslog, alignment, or span evidence is visible rather than causing unnecessary total failure。
46. As a CI operator, I want exit codes to describe artifact generation independently of fault presence, so that automation can distinguish a valid partial report from invalid input or an internal failure。
47. As a maintainer, I want the generator, parser adapters, component mapping, severity rules, and schema versions recorded independently, so that compatibility and diagnosis changes can be audited。
48. As a maintainer, I want unknown component labels and unknown identity mappings preserved as explicit unknown values, so that the Agent cannot invent architecture entities。
49. As a CANN 故障分析人员, I want the viewer to provide Chinese and English interfaces with Simplified Chinese selected by default, so that the primary audience can use the timeline directly while dashboard integrations can select either supported locale。
50. As a dashboard user, I want one horizontal card per observed component in normal call direction, so that I can understand the participating call path before opening the detailed timeline。
51. As an auditor, I want proven call edges shown separately from explicitly labelled inferred edges, so that the component summary remains useful without upgrading architectural convention into fact。
52. As a dashboard user, I want each component card to show its fault role and one concise evidence fact, so that the summary explains where the fault surfaced without drawing a second reverse propagation graph。
53. As a dashboard user, I want a component click to open the same anchor's complete fault-chain view and select a representative event, so that drill-down preserves upstream and downstream context。
54. As a compatibility-sensitive integrator, I want `tracing-report.html` and `fault-trace.html` generated from the same rendered string, so that existing callers continue to work without maintaining two interfaces。
55. As a dashboard integrator, I want the unified report to render `component_chain` through a stable adapter block below its evidence chain, so that report rendering never imports trace parser internals。

## Implementation Decisions

- The deterministic trace capability remains owned by the sibling `trace-skill`. The evaluation skill keeps its diagnosis role; the metric report builder gains only a `component_chain` rendering adapter and does not import trace parser internals.
- The highest seam is the stable `fault-trace.json` contract. The deterministic trace core owns parsing, normalization, clock handling, deduplication, correlation, proven relationships, span matching, scope slicing, Schema validation, and reference HTML rendering. The Agent orchestrates invocation, optional diagnosis input, anchor explanation, and separately labelled inference.
- The unified dashboard invokes the deterministic `trace-skill` generator through an integration adapter before mounting the trace component. The adapter passes only a Schema-validated, versioned `fault-trace.json` payload (or an equivalent in-memory object) to the component; the browser component never reads raw logs, opens archives, or imports parser/correlation internals.
- Inputs are one directory or archive representing one collection/reproduction boundary. Nested archives may be inspected to depth two. Unsafe archive entries and resource-limit violations are recorded and skipped.
- Versioned parser adapters use declared path and content signatures. A generic fallback reports coverage and unparsed records. Parser grammar controls multiline continuation ownership.
- Every normalized timestamp retains raw text and clock-domain identity. Established wall-clock times use decimal-string absolute epoch microseconds; all timeline plotting uses integer clock-domain-relative microsecond offsets. Unknown-zone timestamps do not receive fabricated absolute epochs.
- Host/Device clock alignment requires explicit conversion/synchronization or validated correlated events. The output records offset, method, uncertainty, and alignment status.
- Logical and physical Device IDs are separate fields. Mapping is proven only from explicit environment, `asys`, `npu-smi`, or driver evidence.
- Compatible duplicate observations within one package are merged by an exact semantic fingerprint built from clock domain, exact timestamp, event type, component, execution subject, available correlation IDs, and normalized message fields. Source path and location are not fingerprint inputs. Cross-package deduplication and correlation are prohibited.
- Sensitive environment identities receive deterministic, typed aliases stable only within one package and its generated artifacts. Diagnostic correlation IDs such as Device, process, thread, task, stream, event, error code, PC, and necessary addresses remain available.
- Automatic anchor severity rules are versioned. Explicit fatal signals and documented severe error rules qualify; ordinary error level alone does not. Explicit caller or evaluation anchors take precedence. Unaligned domains may produce anchor-selection ambiguity rather than a fabricated global earliest.
- Execution scope is established from explicit process-group, session, job, rank, stream/task, and correlation identities. Unassigned or unrelated concurrent records remain auditable but are excluded from the selected view.
- A proven relationship requires explicit interaction evidence or compatible explicit correlation identity plus execution subject. Timing or component conventions can only create inferred relationships.
- `component_chain` is derived once by the deterministic trace core from the selected anchor's observed components and relationships. Report and viewer layers consume it without re-deriving evidence strength or component topology.
- Component-chain arrows retain normal call or task-dispatch direction. Fault source, direct trigger, propagation, affected, and business-error roles decorate component nodes and never create a second reverse edge set.
- Only observed canonical components become nodes. Architecture plus current-log evidence may support an inferred edge between observed nodes; architecture alone never materializes a node or proven edge. Missing relationships remain an explicit evidence gap.
- A call span requires matched start/end evidence for the same correlation identity and execution subject. Otherwise the artifact retains discrete events and unmatched-span diagnostics.
- The default fault-chain view contains the proven graph reachable from the anchor in both directions. The full-trace view adds bounded non-chain context without changing evidence strength.
- Default non-chain context is one second before and one hundred milliseconds after the anchor, capped at twenty thousand events. CLI callers can override each bound independently. The proven chain and anchor are never removed by these limits.
- The viewer is a horizontal true-scale timeline with Host/Device and clock-domain lanes, expandable execution details, synchronized overview/detail views, candidate switching, and linked evidence table. It is not a UML sequence diagram.
- The chart keeps one compact, visible toolbar above the timeline for fault-candidate selection, zoom, context visibility, inferred-relationship visibility, and locale switching; secondary evidence remains collapsible.
- The timeline keeps a fixed lane-label column while the time canvas scrolls horizontally, with drag-to-pan and a bottom scrollbar available together.
- Clock-domain panels without selected-chain events are collapsed by default; the viewer preserves an explicit affordance to reveal them without implying that they participate in the fault chain.
- Localization applies to viewer labels and help text only. Component names, process names, PIDs, stream identifiers, and raw evidence fields remain unchanged from the trace contract.
- The timeline includes a compact fixed legend for fault-anchor, proven-chain, inferred-relationship, and ordinary-context styles; it is localized with the rest of the viewer labels.
- Timeline axes remain anchor-relative with explicit `us` or `ms` units. Event hover and selection details expose the relative offset, raw timestamp, and clock-domain identifier without replacing the source value.
- The default canvas labels only the fault anchor and proven-chain events. Context events render as compact marks and reveal component/message text on hover or selection.
- Relationship connectors are limited to visible lanes. Proven relationships render as thin solid directed arrows; inferred relationships, when enabled, render as subdued gray dashed arrows and never enter the default highlighted chain.
- Event selection opens a collapsible right-side evidence drawer. The drawer may reduce available chart width but does not insert a full-width detail block below the timeline.
- The evidence drawer is an overlay: opening or closing it does not change the timeline canvas dimensions, zoom, pan position, or event coordinates.
- The main timeline uses the available viewport height with a stable minimum height. Page scrolling handles content below the chart; the viewer does not create a second full-page nested scroll region for the timeline.
- Narrow layouts retain a bounded, reduced-width fixed lane-label column. Long labels are visually truncated but remain available in the event detail or hover affordance.
- All viewer controls and event marks expose keyboard interaction: Tab navigation, Enter or Space selection, and arrow-key timeline panning when the canvas is focused.
- Evidence strength is never encoded by color alone; anchor, proven, inferred, and context states combine color contrast with line style and shape or icon cues.
- For large inputs, the viewer can show the selected candidate and bounded parse progress before rendering completes. The timeline has an explicit loading state and is replaced automatically by the rendered chart.
- Incomplete evidence produces a usable partial artifact: the viewer renders the verifiable chain, labels the result as partial, and exposes missing sources, unaligned clocks, and excluded evidence instead of suppressing the chart.
- Partial status is shown by a localized top-level badge and panel-local warnings. Each affected panel exposes an expandable explanation of the missing or unaligned evidence.
- Partial status uses an amber warning style distinct from the red fault anchor, communicating usable-but-incomplete evidence rather than a second fault.
- `tracing-report.html` is the self-contained reference implementation of the detailed trace component. The unified report embeds only the horizontal component-chain summary below its evidence chain and deep-links into the detailed report; it does not embed raw logs or parser code.
- The viewer provides Simplified Chinese and English display strings, defaults to `zh-CN`, and exposes a local language switch. Locale changes affect presentation only and must not change trace coordinates, evidence strength, identifiers, filtering, or exported data.
- The HTML is fully offline and self-contained. It embeds the contract data, JavaScript, CSS, icons, and required viewer assets; it performs no external network requests. A single render result is written to `tracing-report.html` and the compatibility filename `fault-trace.html`.
- Detailed-report deep links accept `view`, `anchor`, `component`, and `event`; selection falls back in the order event, component, anchor, then the report default while showing a non-blocking invalid-target notice.
- The contract declares `schema_version`; breaking semantic changes require a major version. Generator, parser, component-map, and severity-rule versions are separate metadata.
- Result status distinguishes `complete` and `partial`. A partial result exposes missing source types, unsupported or unsafe entries, unaligned clocks, unmatched spans, scope ambiguity, parse coverage, conflicts, orphan evidence, and truncation.
- CLI exit codes are: `0` for a schema-valid complete or partial artifact; `2` for invalid arguments, configuration, or unreadable input; `3` for no usable timestamped event or anchor; `4` for internal, Schema-validation, or rendering failure. Wrapped application and collector exit statuses remain evidence metadata.

## Testing Decisions

- Tests verify externally observable output and diagnostics: JSON Schema validity, event content, relationship evidence strength, time coordinates, scope membership, rendered offline behavior, and exit codes. They do not assert private parser implementation details.
- Parser tests use real redacted Host `plog`, CANN Trace, Device maintenance-log, and Host kernel fixtures from the available diagnostic and controlled CANNLab packages. They verify format detection, multiline handling, provenance, logical/physical Device fields, and partial-result reporting.
- Synthetic controlled fixtures cover exact duplicate fingerprints, conflicting fields, unmatched span endpoints, equal timestamps, explicit clock alignment, unknown-zone timestamps, ambiguous scopes, inferred versus proven relationships, archive safety limits, context truncation, and multiple anchor candidates.
- End-to-end tests generate JSON, `tracing-report.html`, and the byte-identical `fault-trace.html` compatibility artifact. Controlled fixtures validate mechanics; DTS HCCL, GE, normal CannLab, and no-chain inputs provide the product acceptance matrix.
- Contract-conformance tests validate required fields, version metadata, redaction behavior, evidence locators, status diagnostics, and backward-compatible optional-field additions.
- Viewer tests open the generated HTML offline, verify no external requests, confirm the initial `zh-CN` locale, switch to English, switch candidates, filter evidence, synchronize event selection between timeline and table, and check microsecond labels and separate clock-domain axes.
- The MVP merge gate requires Schema validation, parser unit tests, the synthetic correlation suite, successful parsing of the existing real packages, and JSON/HTML end-to-end generation. Product-level acceptance additionally requires a representative real product fault with matched Host/Device evidence.
- Existing project prior art is the current cleaning pipeline, structured report-data contract, static HTML builder, and template verification rules. The new trace tests preserve their evidence-first semantics while adding duration and concurrency behavior.

## Out of Scope

- Replacing or redesigning `eval-skill` diagnosis, confidence scoring, case promotion, or unified-report semantics outside the component-chain adapter.
- Claiming a root cause solely from the selected anchor, first `ERROR`, time proximity, component ordering, PID/TID equality, or Device identity.
- Treating inferred relationships as highlighted proven relationships.
- Fabricating Host/Device clock alignment, logical/physical Device mapping, timestamps, call durations, missing stack frames, or unknown component names.
- Cross-package or cross-reproduction deduplication, identity linking, or correlation.
- A cloud service, online viewer, external asset CDN, or server-side persistence layer.
- Complex indexing or random-access infrastructure in the MVP; the initial reader scans files sequentially and retains only the data needed for deterministic normalization and correlation.
- A UML-only sequence diagram, static architecture graph replacement, or a full-process-history view with no scope/window controls.
- Treating the controlled SIGABRT CANNLab fixture as proof of a representative production fault.
- Product-level acceptance before a representative real product-fault package is available.

## Further Notes

- The trace generator owns the component-chain contract and detailed offline report. The unified dashboard integration remains a thin JSON/report-data adapter that renders the summary below the evidence chain and links to the detailed report.
- The original diagnostic package and controlled CANNLab package have different evidence strengths and collection timing. Their limitations must remain visible in generated diagnostics.
- The MVP should preserve the distinction between a valid partial artifact and a failed generation. This allows missing Trace, syslog, Device export timing, or clock alignment to be reported without discarding usable Host evidence.
- Development planning uses GitCode Issues in the contributor fork `Lujialiang/skills`, with `ready-for-agent` as the implementation-ready label. This tracker choice is kept outside the upstream repository configuration so the contribution remains scoped to `trace-skill`.
