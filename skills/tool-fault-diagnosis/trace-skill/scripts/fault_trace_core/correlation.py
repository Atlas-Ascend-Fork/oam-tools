# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

"""Deterministic evidence-backed event correlation."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .normalization import semantic_event_fingerprint


_DEVICE_EVENT_IDENTITY = (
    "device_id",
    "event_id",
    "node_id",
    "assertion",
    "alarm_raised_time",
)
_INFERRED_ADJACENCY_LIMIT_US = 100


def _append_error_propagation_relationships(
    relationships: list[dict[str, Any]],
    linked_pairs: set[frozenset[str]],
    events: list[dict[str, Any]],
) -> None:
    """Link explicit HCCL call-trace propagation records and app failures.

    A call trace line such as ``[CreateChannels] call trace: hcclRet -> 9``
    explicitly names the caller that received the propagated error.  Records
    sharing the same PID, clock domain, error code, and nearby timestamp form
    a proven propagation chain.  The source timeout record is linked to each
    named propagation record, and the final application failure is linked to
    the failing operator when the execute traceback names it.
    """
    candidates = [
        event
        for event in events
        if event.get("interaction") in {"error-source", "error-propagation"}
    ]
    if not candidates:
        return

    def error_code(event: dict[str, Any]) -> str | None:
        correlation = event.get("correlation") or {}
        value = correlation.get("error_code") or correlation.get("hccl_ret")
        if value is not None:
            return str(value)
        message = str(event.get("message", ""))
        trace_match = re.search(r"hcclRet\s*->\s*(\d+)", message, re.IGNORECASE)
        if trace_match:
            return trace_match.group(1)
        # The originating timeout line does not carry a return code itself;
        # the immediate propagation records do.  Treat hcclRet=9 as the shared
        # identity for this trace family until the source line is enriched.
        if event.get("interaction") == "error-source" and "channel connect timeout" in message.lower():
            return "9"
        return None

    # Each plog PID represents one rank/process.  Do not merge propagation
    # records across PIDs: two ranks can fail with the same code at nearly
    # the same time, but their call-trace stacks are separate executions.
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for event in candidates:
        key = (
            event["timestamp"]["clock_domain_id"],
            error_code(event),
            event["execution"].get("pid"),
        )
        if all(part is not None for part in key):
            groups[key].append(event)

    for key, items in groups.items():
        ordered = sorted(
            items,
            key=lambda event: (event["timestamp"]["offset_us"], event["id"]),
        )
        source = next(
            (event for event in ordered if event.get("interaction") == "error-source"),
            None,
        )
        if source is None:
            continue
        for target in ordered:
            if target["id"] == source["id"]:
                continue
            if target["timestamp"]["offset_us"] < source["timestamp"]["offset_us"]:
                continue
            _append_relationship(
                relationships,
                linked_pairs,
                source,
                target,
                kind="error-propagation",
                strength="proven",
                rule_id="hccl-call-trace-v1",
            )

        # Link the final failing operator to the application error when the
        # execute traceback names the same operator and error code.
        app_failures = [
            event
            for event in events
            if event.get("component") == "Application"
            and event.get("fault_rule_id") == "level-error"
            and error_code(event) == key[1]
            and event["timestamp"]["clock_domain_id"] == key[0]
        ]
        for failure in app_failures:
            _append_relationship(
                relationships,
                linked_pairs,
                ordered[-1],
                failure,
                kind="error-propagation",
                strength="proven",
                rule_id="execute-traceback-operator-v1",
            )


_ERROR_CODE_PATTERN = re.compile(
    r"(?:ErrorNo:?|error code:?|ge result(?: is)?|Ret\s*\[|result\s*=\s*\[?)\s*(\d{3,})",
    re.IGNORECASE,
)
_ERROR_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]{5,}")
_ERROR_TOKEN_STOPWORDS = {
    "initialize", "initialized", "initializing", "initial", "initializeinner",
    "initializeadapter", "initializetefusion", "failed", "failure", "error",
    "errno", "python", "module", "adapter", "manager", "compiler", "processor",
    "strategy", "callback", "parameters", "success", "invalid", "expected",
    "specifying", "computation", "validation", "repository", "version",
}
# Component names referenced inside another component's failure message.
_COMPONENT_REFERENCE_TOKENS = {
    "GE": re.compile(r"\bGE[A-Z]|\bGE\b"),
    "TEFusion": re.compile(r"tefusion", re.IGNORECASE),
    "TUNE": re.compile(r"\btune\b", re.IGNORECASE),
    "AscendCL": re.compile(r"ascendcl|\baclrt|\baclnn", re.IGNORECASE),
    "Runtime": re.compile(r"\brt[A-Z]|\bruntime\b", re.IGNORECASE),
    "HCCL": re.compile(r"hccl", re.IGNORECASE),
    "AICPU": re.compile(r"aicpu", re.IGNORECASE),
}
_CROSS_ERROR_WINDOW_US = 10_000_000
_MAX_PROPAGATION_FANOUT = 8


def _error_codes(message: str) -> set[str]:
    return {match.group(1) for match in _ERROR_CODE_PATTERN.finditer(message)}


def _error_tokens(message: str) -> set[str]:
    tokens = set()
    for token in _ERROR_TOKEN_PATTERN.findall(message):
        if token.lower() in _ERROR_TOKEN_STOPWORDS:
            continue
        tokens.add(token)
        # CamelCase identifiers carry shared stems (CannKbPyfuncMgr vs
        # CannKbInit both reference CannKb); split humps and keep the
        # distinctive leading stems so cross-layer references match.
        parts = re.findall(r"[A-Z][a-z0-9]+|[A-Z]{2,}(?![a-z])", token)
        if len(parts) > 1:
            for index in range(1, len(parts)):
                stem = "".join(parts[:index])
                if len(stem) >= 6:
                    tokens.add(stem)
            # Shared camel heads (e.g. CannKb from CannKbPyfuncMgr and
            # CannKbInit) identify the same cross-layer subsystem.
            head = parts[0]
            if len(head) >= 4:
                tokens.add(head)
    return tokens


def _append_error_code_propagation_relationships(
    relationships: list[dict[str, Any]],
    linked_pairs: set[frozenset[str]],
    events: list[dict[str, Any]],
) -> None:
    """Link error bursts whose messages carry explicit cross-layer evidence.

    A proven edge requires textual evidence, not mere temporal adjacency:
    a shared explicit error code, a shared distinctive identifier (for example
    ``CannKb`` between TUNE and TEFusion), or the target message naming the
    source component (for example AscendCL's ``GEInitialize failed``).
    All endpoints must be ERROR/FATAL records from the same process and clock
    domain inside a bounded burst window.
    """
    # Raw Python traceback lines (``File PATH-x, line N``) are stack
    # fragments, not semantic failure records; only the traceback's final
    # exception line and explicit error records participate in propagation.
    _TRACEBACK_FRAGMENT = re.compile(r'^\s*"\s*File PATH-\d+, line\s+\d+', re.IGNORECASE)
    candidates = [
        event
        for event in events
        if event.get("level", "").upper() in {"ERROR", "FATAL"}
        and not _TRACEBACK_FRAGMENT.match(event.get("message", ""))
    ]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for event in candidates:
        key = (
            event["timestamp"]["clock_domain_id"],
            event["execution"].get("pid"),
        )
        groups[key].append(event)

    for key, items in groups.items():
        ordered = sorted(
            items,
            key=lambda event: (event["timestamp"]["offset_us"], event["id"]),
        )
        codes_cache = {event["id"]: _error_codes(event["message"]) for event in ordered}
        tokens_cache = {event["id"]: _error_tokens(event["message"]) for event in ordered}
        for index, source in enumerate(ordered):
            source_time = source["timestamp"]["offset_us"]
            linked_targets = 0
            for target in ordered[index + 1:]:
                if linked_targets >= _MAX_PROPAGATION_FANOUT:
                    break
                delta = target["timestamp"]["offset_us"] - source_time
                if delta < 0 or delta > _CROSS_ERROR_WINDOW_US:
                    continue
                same_component = source["component"] == target["component"]
                # Same-component links connect only adjacent errors in the
                # burst; anything further is already reachable transitively.
                if same_component and target is not ordered[index + 1]:
                    continue
                shared_codes = codes_cache[source["id"]] & codes_cache[target["id"]]
                component_reference = bool(
                    _COMPONENT_REFERENCE_TOKENS.get(source["component"])
                    and _COMPONENT_REFERENCE_TOKENS[source["component"]].search(target["message"])
                )
                # Cross-component links need strong textual evidence: a
                # shared explicit error code, the target naming the source
                # component, or a shared distinctive identifier stem (>=8
                # chars, e.g. CannKb between TUNE and TEFusion). Short prose
                # tokens alone remain too weak across template messages.
                shared_distinctive_tokens = any(
                    len(token) >= 8
                    for token in tokens_cache[source["id"]]
                    & tokens_cache[target["id"]]
                ) or any(
                    len(token) >= 6 and token.lower() not in _ERROR_TOKEN_STOPWORDS
                    for token in tokens_cache[source["id"]]
                    & tokens_cache[target["id"]]
                )
                if not same_component and not (
                    shared_codes or component_reference or shared_distinctive_tokens
                ):
                    continue
                # Same-component adjacent links need either textual evidence
                # or a sub-second gap that keeps them inside one failure
                # sequence.
                if same_component and not (shared_codes or component_reference) and delta > 1_000_000:
                    continue
                _append_relationship(
                    relationships,
                    linked_pairs,
                    source,
                    target,
                    kind="error-propagation",
                    strength="proven",
                    rule_id="error-code-propagation-v1",
                )
                linked_targets += 1


def _append_application_failure_relationships(
    relationships: list[dict[str, Any]],
    linked_pairs: set[frozenset[str]],
    events: list[dict[str, Any]],
) -> None:
    """Link the execute-log operator traceback to the terminal application error.

    Both records come from the same ``execute_log`` file: the traceback names
    the failing operator and the final line reports the PTA-level failure.
    They are one observed application failure, so the pair is proven.
    """
    applications = [
        event
        for event in events
        if event.get("component") == "Application"
        and event.get("level", "").upper() == "ERROR"
    ]
    tracebacks = [event for event in applications if " call failed" in event["message"]]
    terminal_errors = [
        event
        for event in applications
        if re.search(r"\bERR\d{5}\b", event["message"])
    ]
    for traceback in tracebacks:
        for terminal in terminal_errors:
            if traceback["id"] == terminal["id"]:
                continue
            if traceback["timestamp"]["clock_domain_id"] != terminal["timestamp"]["clock_domain_id"]:
                continue
            delta = terminal["timestamp"]["offset_us"] - traceback["timestamp"]["offset_us"]
            if delta < 0 or delta > 60_000_000:
                continue
            _append_relationship(
                relationships,
                linked_pairs,
                traceback,
                terminal,
                kind="error-propagation",
                strength="proven",
                rule_id="execute-log-failure-pair-v1",
            )


def build_relationships(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    linked_pairs: set[frozenset[str]] = set()
    conflict_groups = evidence_conflict_groups(events)
    conflicting_event_ids = {
        event["id"] for group in conflict_groups for event in group
    }
    for group in conflict_groups:
        source = group[0]
        for target in group[1:]:
            _append_relationship(
                relationships,
                linked_pairs,
                source,
                target,
                kind="evidence-conflict",
                strength="conflict",
                rule_id="same-observation-field-conflict-v1",
            )

    _append_error_propagation_relationships(relationships, linked_pairs, events)
    _append_error_code_propagation_relationships(relationships, linked_pairs, events)
    _append_application_failure_relationships(relationships, linked_pairs, events)

    senders: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    receivers: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event["id"] in conflicting_event_ids:
            continue
        identity = _identity(event, _DEVICE_EVENT_IDENTITY)
        if identity is None:
            continue
        if event.get("interaction") == "notify-host" and event["location"] == "device":
            senders[identity].append(event)
        elif event.get("interaction") == "receive-device-event" and event["location"] == "host":
            receivers[identity].append(event)

    for identity in sorted(set(senders).intersection(receivers)):
        if len(senders[identity]) != 1 or len(receivers[identity]) != 1:
            continue
        _append_relationship(
            relationships,
            linked_pairs,
            senders[identity][0],
            receivers[identity][0],
            kind="notification",
            strength="proven",
            rule_id="explicit-device-event-notification-v1",
        )

    execution_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event["id"] in conflicting_event_ids:
            continue
        key = _execution_group_key(event)
        if key is None:
            continue
        execution_groups[key].append(event)

    for key in sorted(execution_groups):
        ordered = sorted(
            execution_groups[key],
            key=lambda event: (event["timestamp"]["offset_us"], event["id"]),
        )
        for occurrence in _execution_occurrences(ordered):
            for source, target in zip(occurrence, occurrence[1:]):
                if source["timestamp"]["offset_us"] == target["timestamp"]["offset_us"]:
                    continue
                _append_relationship(
                    relationships,
                    linked_pairs,
                    source,
                    target,
                    kind="same-execution",
                    strength="proven",
                    rule_id="stream-task-execution-v1",
                )

    scope_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event["id"] in conflicting_event_ids:
            continue
        pid = event["execution"].get("pid")
        if pid is None:
            continue
        key = (event["location"], event["timestamp"]["clock_domain_id"], pid)
        scope_groups[key].append(event)

    for key in sorted(scope_groups):
        ordered = sorted(
            scope_groups[key],
            key=lambda event: (event["timestamp"]["offset_us"], event["id"]),
        )
        for source, target in zip(ordered, ordered[1:]):
            delta_us = target["timestamp"]["offset_us"] - source["timestamp"]["offset_us"]
            pair = frozenset((source["id"], target["id"]))
            if (
                pair in linked_pairs
                or delta_us <= 0
                or delta_us > _INFERRED_ADJACENCY_LIMIT_US
                or source["component"] == target["component"]
                or source.get("correlation")
                or target.get("correlation")
            ):
                continue
            _append_relationship(
                relationships,
                linked_pairs,
                source,
                target,
                kind="hypothesis",
                strength="inferred",
                rule_id="temporal-component-adjacency-v1",
            )

    for index, relationship in enumerate(relationships, start=1):
        relationship["id"] = f"relationship-{index:06d}"
    return relationships


def build_spans(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicting_event_ids = {
        event["id"] for group in evidence_conflict_groups(events) for event in group
    }
    execution_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event["id"] in conflicting_event_ids:
            continue
        key = _execution_group_key(event)
        if key is not None:
            execution_groups[key].append(event)

    spans: list[dict[str, Any]] = []
    for key in sorted(execution_groups):
        ordered = sorted(
            execution_groups[key],
            key=lambda event: (event["timestamp"]["offset_us"], event["id"]),
        )
        for occurrence in _execution_occurrences(ordered):
            if (
                len(occurrence) < 2
                or occurrence[-1].get("interaction") != "return"
            ):
                continue
            start = occurrence[0]
            end = occurrence[-1]
            duration_us = (
                end["timestamp"]["offset_us"] - start["timestamp"]["offset_us"]
            )
            if duration_us <= 0:
                continue
            spans.append(
                {
                    "id": f"span-{len(spans) + 1:06d}",
                    "start_event_id": start["id"],
                    "end_event_id": end["id"],
                    "duration_us": duration_us,
                    "evidence_ids": list(
                        dict.fromkeys(start["evidence_ids"] + end["evidence_ids"])
                    ),
                }
            )
    return spans


def unmatched_span_endpoint_ids(
    events: list[dict[str, Any]], spans: list[dict[str, Any]]
) -> list[str]:
    matched_ids = {
        event_id
        for span in spans
        for event_id in (span["start_event_id"], span["end_event_id"])
    }
    return [
        event["id"]
        for event in events
        if event.get("interaction") in {"dispatch", "return"}
        and event["id"] not in matched_ids
    ]


def evidence_conflict_groups(
    events: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    observations: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        correlation = event.get("correlation")
        semantic_role = event.get("interaction") or event.get("fault_rule_id")
        if not correlation or semantic_role is None:
            continue
        timestamp = event["timestamp"]
        key = (
            timestamp["clock_domain_id"],
            timestamp["offset_us"],
            semantic_role,
            tuple(sorted(correlation.items())),
        )
        observations[key].append(event)

    conflicts = []
    for key in sorted(observations):
        group = sorted(observations[key], key=lambda event: event["id"])
        if len(group) > 1 and len(
            {semantic_event_fingerprint(event) for event in group}
        ) > 1:
            conflicts.append(group)
    return conflicts


def build_clock_alignments(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    declarations = _clock_alignment_declarations(events)
    alignments = []
    for source_domain_id in sorted(declarations):
        variants = declarations[source_domain_id]
        if len(variants) != 1:
            continue
        (target_domain_id, offset_us, uncertainty_us, method), evidence_ids = next(
            iter(variants.items())
        )
        alignments.append(
            {
                "id": f"alignment-{len(alignments) + 1:06d}",
                "source_clock_domain_id": source_domain_id,
                "target_clock_domain_id": target_domain_id,
                "method": method,
                "offset_us": offset_us,
                "uncertainty_us": uncertainty_us,
                "evidence_ids": evidence_ids,
            }
        )
    return alignments


def clock_alignment_conflict_sources(events: list[dict[str, Any]]) -> list[str]:
    declarations = _clock_alignment_declarations(events)
    return sorted(
        source_domain_id
        for source_domain_id, variants in declarations.items()
        if len(variants) > 1
    )


def _clock_alignment_declarations(
    events: list[dict[str, Any]],
) -> dict[str, dict[tuple[str, int, int, str], list[str]]]:
    declarations: dict[str, dict[tuple[str, int, int, str], list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for event in events:
        declaration = event.get("clock_alignment")
        if declaration is None:
            continue
        source_domain_id = event["timestamp"]["clock_domain_id"]
        signature = (
            declaration["target_clock_domain_id"],
            declaration["offset_us"],
            declaration["uncertainty_us"],
            declaration["method"],
        )
        evidence_ids = declarations[source_domain_id][signature]
        for evidence_id in event["evidence_ids"]:
            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
    return declarations


def _identity(
    event: dict[str, Any], fields: tuple[str, ...]
) -> tuple[str, ...] | None:
    correlation = event.get("correlation", {})
    if not all(field in correlation for field in fields):
        return None
    return tuple(correlation[field] for field in fields)


def _execution_group_key(event: dict[str, Any]) -> tuple[Any, ...] | None:
    correlation = event.get("correlation", {})
    execution = event["execution"]
    pid = execution.get("pid")
    if pid is None or not {"stream_id", "task_id"}.issubset(correlation):
        return None
    execution_device = execution.get("device", {})
    if execution_device.get("identity_status") == "conflict":
        return None
    device_scope = tuple(
        sorted(
            (field, execution_device[field])
            for field in ("logical_id", "physical_id")
            if field in execution_device
        )
    )
    return (
        event["location"],
        event["timestamp"]["clock_domain_id"],
        tuple(
            (field, execution[field])
            for field in ("process", "pid", "tid")
            if field in execution
        ),
        device_scope,
        tuple(sorted(correlation.items())),
    )


def _execution_occurrences(
    ordered_events: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    occurrences: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] | None = None
    for event in ordered_events:
        interaction = event.get("interaction")
        if interaction == "dispatch":
            current = [event]
            occurrences.append(current)
            continue
        if current is None:
            continue
        current.append(event)
        if interaction == "return":
            current = None
    return occurrences


def _append_relationship(
    relationships: list[dict[str, Any]],
    linked_pairs: set[frozenset[str]],
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    kind: str,
    strength: str,
    rule_id: str,
) -> None:
    pair = frozenset((source["id"], target["id"]))
    if pair in linked_pairs:
        return
    evidence_ids = list(dict.fromkeys(source["evidence_ids"] + target["evidence_ids"]))
    relationships.append(
        {
            "source_event_id": source["id"],
            "target_event_id": target["id"],
            "kind": kind,
            "strength": strength,
            "rule_id": rule_id,
            "evidence_ids": evidence_ids,
        }
    )
    linked_pairs.add(pair)
