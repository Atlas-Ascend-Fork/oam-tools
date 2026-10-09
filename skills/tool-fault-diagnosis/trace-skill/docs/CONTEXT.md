# CANN Fault Trace Visualization

This context defines the domain language for reconstructing and visualizing CANN component calls around a failure. It separates the evidence-backed fault path from the broader execution context shown in the HTML dashboard.

## Input Boundary

**Input package**:
One top-level directory or archive representing a single collection or reproduction boundary. Safely readable nested archives belong to the same input package; separately supplied packages remain separate boundaries.
_Avoid_: Log file, fixture

**Execution scope**:
The processes, Device activity, and events belonging to the selected fault's execution, established from explicit process-group, session, job, rank, or correlation identity and proven relationships. It is an identity boundary, not merely a time window.
_Avoid_: Fault window, all concurrent activity

**Execution-scope candidate**:
A possible execution scope consistent with the available identities when the selected fault cannot be assigned uniquely. It remains selectable context and is not treated as proven membership.
_Avoid_: Execution scope, inferred fault chain

## Views

**Fault-chain view**:
The default view containing only calls and relationships relevant to the selected fault anchor, with the causal path emphasized.
_Avoid_: Error timeline, full trace

**Component call-chain summary**:
A compact left-to-right projection of component-level call or dispatch relationships for the selected fault's execution. It uses one node per observed canonical component and may annotate each node with its fault role, but its arrows retain normal call direction rather than error-propagation direction. Proven and explicitly qualified inferred relationships may both appear without changing their evidence strength.
_Avoid_: Fault-propagation chain, event timeline, architecture inventory

**Fault role**:
The part a component plays relative to the selected fault anchor, such as fault source, direct trigger, propagation point, or affected business boundary. A fault role decorates a component in the call-chain summary and does not create a second relationship or reverse the call direction.
_Avoid_: Relationship direction, component severity, proven root cause

**Call-chain evidence gap**:
The state in which observed components belong to the selected execution but the available evidence cannot establish a proven or qualified inferred normal call relationship between them. The components remain inspectable while the missing relationship is stated explicitly.
_Avoid_: Hidden component, architecture-completed edge, parser failure

**Full-trace view**:
An optional expanded view containing the broader call trace around the same fault window, while preserving the emphasis on the fault chain.
_Avoid_: Unfiltered logs, all logs

**Tracing report**:
A self-contained interactive presentation of one versioned fault trace. It provides component-level entry points and event-level fault and process views while preserving the trace's evidence strength, clock-domain, and selection semantics; it is a consumer of the trace contract rather than the contract itself.
_Avoid_: Unified diagnosis report, raw trace contract, log parser

**Fault window**:
The bounded non-chain context around a fault anchor. It limits surrounding events by time and count but never removes the anchor or any event in its proven fault chain.
_Avoid_: Fault chain, complete process lifetime

**Trace completeness**:
Whether a schema-valid trace has all material evidence needed for its claims, expressed as `complete` or `partial`. It is independent of whether a fault was detected and whether the generator process succeeded.
_Avoid_: CLI exit status, fault presence

## Fault Selection

**Fault anchor**:
The selected observed anomaly around which the trace is correlated and sliced. It identifies the focus of a view but does not by itself assert a root cause.
_Avoid_: Root cause, first error

**Fault-anchor candidate**:
An observed high-severity anomaly eligible to become the fault anchor, retained with the evidence explaining why it was detected.
_Avoid_: Confirmed fault, root-cause candidate

**Anchor severity**:
A deterministic classification of whether an observed anomaly is eligible for automatic fault-anchor selection. It expresses selection relevance, not root-cause confidence.
_Avoid_: Log level, diagnosis confidence

**Anchor-selection ambiguity**:
The state in which eligible fault anchors cannot be placed in one proven temporal order, such as candidates in unaligned clock domains. It preserves domain-local candidates without asserting a global earliest event.
_Avoid_: Default anchor, parser failure

## Evidence

**Observed event**:
A timestamped fact present directly in a source log, retaining its original record and provenance.
_Avoid_: Call, span

**Duplicate observation**:
Two or more compatible source records within one input package that represent the same normalized event. They form one observed event with every source retained as evidence; records from different packages or reproduction runs are never duplicate observations.
_Avoid_: Repeated event, evidence conflict

**Proven relationship**:
A relationship supported either by an explicit call, dispatch, notification, or return statement in the source record, or by matching correlation identities with compatible semantics and execution subjects. Time proximity, component convention, PID, TID, or Device identity alone cannot prove a cross-component relationship.
_Avoid_: Certain root cause

**Inferred relationship**:
A possible relationship derived from timing and component rules when explicit correlation evidence is absent. It is visually de-emphasized and excluded from the default highlighted fault chain.
_Avoid_: Proven relationship, call fact

**Evidence reference**:
A traceable pointer from an event or relationship to its source record, containing a package-relative source location, record hash, and minimally necessary redacted excerpt. It supports verification without copying the complete source log into the trace artifact.
_Avoid_: Full embedded log, unverifiable summary

**Orphan evidence**:
An untimestamped source fragment that no parser can attach to a timestamped record from explicit format structure. It remains inspectable provenance but is not a timeline event.
_Avoid_: Observed event, discarded text

**Pseudonymous identity**:
A type-specific alias that preserves equality for a sensitive identity within one input package and its artifacts. It carries no default identity relationship to aliases in another input package.
_Avoid_: Global identity, reversible redaction

**Evidence conflict**:
Two or more observed records that cannot simultaneously support the same relationship or span, such as one correlation identity resolving to incompatible execution subjects or an end preceding its start. Conflicting records remain visible but cannot establish a proven relationship until resolved.
_Avoid_: Parser preference, inferred winner

**Clock domain**:
The time basis used by a log source or record, such as Host wall clock, unknown-zone wall clock, Device wall clock, or Device boot-relative time. Equal-looking timestamps from different clock domains are not comparable until alignment is proven.
_Avoid_: Timestamp format, Host time

**Temporal order**:
A partial ordering established by comparable timestamps or explicit relationship evidence. Events with equal timestamps and no ordering evidence remain simultaneous or order-unknown even when serialized deterministically in an artifact.
_Avoid_: File order, display order

**Device identity**:
A Device reference that preserves its identity namespace, including whether an ID is logical or physical. Logical and physical IDs identify the same Device only when explicit environment or log evidence establishes the mapping.
_Avoid_: Device number, assumed Device mapping

**Call span**:
A duration-bearing call or execution interval formed from explicitly matched start and end evidence for the same correlation identity and execution subject.
_Avoid_: Adjacent events, estimated duration

## Timeline Structure

**Timeline lane**:
A visual row for events and call spans from one component and process within a Host/Device location and clock domain. Thread, stream, and task identities are expandable execution detail rather than separate default lanes; a source log file is provenance, not a lane.
_Avoid_: Log-file lane, one-thread-per-lane

**Canonical component**:
A stable component identity used to group records whose source logs use different module or process labels. Every mapping retains the original label and the versioned rule that produced the canonical identity; an unrecognized label remains unclassified rather than being guessed.
_Avoid_: Raw module label, Agent-assigned component
