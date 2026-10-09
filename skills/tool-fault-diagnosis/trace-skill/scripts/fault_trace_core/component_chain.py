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

"""Derive the compact component call-chain summary from a fault trace."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


COMPONENT_CHAIN_SCHEMA_VERSION = "1.0.0"

# Ordering is presentation-neutral domain knowledge: it is used only to orient
# observed components in normal call/dispatch direction.  It never creates a
# component that is absent from the current trace.
_CALL_ORDER = (
    "Application",
    "AscendCL",
    "GE",
    "TEFusion",
    "TUNE",
    "Operator",
    "Data Dump",
    "Runtime",
    "HCCL",
    "AICPU",
    "TDT",
    "Driver",
)
_CALL_ORDER_INDEX = {component: index for index, component in enumerate(_CALL_ORDER)}
_NORMAL_RELATIONSHIP_KINDS = {"notification", "same-execution", "hypothesis"}
_STRENGTH_RANK = {"inferred": 0, "proven": 1}


def _event_key(event: dict[str, Any]) -> tuple[int, str]:
    return (event["timestamp"]["offset_us"], event["id"])


def _component_key(
    component: str,
    events: list[dict[str, Any]],
) -> tuple[int, int, str]:
    first_offset = min(event["timestamp"]["offset_us"] for event in events)
    return (_CALL_ORDER_INDEX.get(component, len(_CALL_ORDER)), first_offset, component)


def _fault_role(
    component: str,
    events: list[dict[str, Any]],
    anchor_id: str,
    error_related_ids: set[str],
) -> str:
    if any(event.get("interaction") == "error-source" for event in events):
        return "fault-source"
    if component == "Application" and any(
        event["id"] == anchor_id or event.get("level", "").upper() in {"ERROR", "FATAL"}
        for event in events
    ):
        return "business-error"
    if any(event["id"] == anchor_id for event in events):
        return "direct-trigger"
    if any(event.get("interaction") == "error-propagation" for event in events):
        return "propagation"
    if any(event["id"] in error_related_ids for event in events) or any(
        event.get("level", "").upper() in {"ERROR", "FATAL"} for event in events
    ):
        return "affected"
    return "observed"


import re as _re

_CODE_RE = _re.compile(r"\b(?:ERR\d{5}|hcclRet\s*=\s*\d+|ret\s*=\s*-?\d+|ErrorNo:\s*\d+|error_code\s*=\s*-?\d+)\b", _re.IGNORECASE)
_PREFIX_RE = _re.compile(r"^(?:\[[^\]]*\]|\(\d+[^)]*\)|\d{4,})\s*")
_LEAD_TAG_RE = _re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*:)?(?:\[[^\]]*\])+\s*")


def shorten_summary(message: str) -> str:
    """Derive a one-line human-readable summary from a raw log message.

    Strips bracketed source tags and leading pid/file tokens, keeps the first
    complete clause, and appends the first error code when the clause lacks
    one.  Falls back to an empty string when nothing readable remains.
    """
    text = (message or "").strip().strip('"').strip()
    if not text:
        return ""
    # Drop leading [tag] / (pid,...) / bare pid prefixes.
    for _ in range(4):
        stripped = _PREFIX_RE.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    # Drop a leading FuncName:[Tag][Tag] run so the readable tail survives.
    stripped = _LEAD_TAG_RE.sub("", text).strip()
    if stripped:
        text = stripped
    # Keep the first complete clause so we never cut mid-word.
    clause = text
    for sep in (",", ";", "."):
        idx = clause.find(sep)
        if 0 < idx <= 48:
            clause = clause[: idx + 1].strip()
            break
    else:
        if len(clause) > 48:
            cut = clause[:48]
            last_space = cut.rfind(" ")
            clause = cut[: last_space if last_space > 12 else 48].rstrip('.,;: ') + "..."
    if not clause.endswith("..."):
        clause = clause.strip('.,;: ')
    codes = _CODE_RE.findall(text)
    if codes and not any(code.lower() in clause.lower() for code in codes):
        clause = f"{clause} {codes[0]}"
    return clause[:64].strip()


def _representative_event(
    events: list[dict[str, Any]], anchor_id: str
) -> dict[str, Any]:
    ordered = sorted(events, key=_event_key)
    informative = lambda event: (
        event.get("level", "").upper() in {"ERROR", "FATAL"}
        and _re.search(r"(?:error|failed|failure|timeout|abort)", event.get("message", ""), _re.IGNORECASE)
        and not event.get("message", "").lstrip('"').startswith("Traceback")
    )
    selectors = (
        lambda event: event.get("interaction") == "error-source",
        lambda event: event["id"] == anchor_id,
        lambda event: event.get("interaction") == "error-propagation",
        informative,
        lambda event: event.get("level", "").upper() in {"ERROR", "FATAL"},
    )
    for selector in selectors:
        selected = next((event for event in ordered if selector(event)), None)
        if selected is not None:
            return selected
    return ordered[0]


def _append_edge_support(
    aggregate: dict[tuple[str, str, str], dict[str, Any]],
    source_component: str,
    target_component: str,
    *,
    kind: str,
    strength: str,
    relationship: dict[str, Any],
    rule_id: str | None = None,
) -> None:
    key = (source_component, target_component, kind)
    current = aggregate.get(key)
    candidate_rank = _STRENGTH_RANK[strength]
    if current is None:
        current = {
            "source_component": source_component,
            "target_component": target_component,
            "kind": kind,
            "strength": strength,
            "rule_ids": [],
            "event_relationship_ids": [],
            "evidence_ids": [],
        }
        aggregate[key] = current
    elif candidate_rank > _STRENGTH_RANK[current["strength"]]:
        current["strength"] = strength
    relationship_rule = rule_id or relationship.get("rule_id")
    if relationship_rule and relationship_rule not in current["rule_ids"]:
        current["rule_ids"].append(relationship_rule)
    if relationship["id"] not in current["event_relationship_ids"]:
        current["event_relationship_ids"].append(relationship["id"])
    for evidence_id in relationship.get("evidence_ids", []):
        if evidence_id not in current["evidence_ids"]:
            current["evidence_ids"].append(evidence_id)


def _has_component_path(
    aggregate: dict[tuple[str, str, str], dict[str, Any]],
    source_component: str,
    target_component: str,
) -> bool:
    neighbors: dict[str, set[str]] = defaultdict(set)
    for edge in aggregate.values():
        neighbors[edge["source_component"]].add(edge["target_component"])
    pending = deque([source_component])
    visited = {source_component}
    while pending:
        current = pending.popleft()
        for neighbor in neighbors[current]:
            if neighbor == target_component:
                return True
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return False


def _normal_direction_for_error_path(
    source_component: str, target_component: str
) -> tuple[str, str]:
    source_order = _CALL_ORDER_INDEX.get(source_component)
    target_order = _CALL_ORDER_INDEX.get(target_component)
    if source_order is not None and target_order is not None and source_order != target_order:
        if source_order < target_order:
            return source_component, target_component
        return target_component, source_component
    # Error propagation normally travels from the callee back to its caller,
    # so its observed direction is reversed for a normal-call summary.
    return target_component, source_component


def build_component_chain_summary(
    events: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    anchor_id: str,
    highlighted_event_ids: list[str],
    context_event_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build one deterministic component summary for the selected anchor.

    When the proven anchor chain has no cross-component edge, context events
    from the anchor scope may be supplied by the caller.  They remain visible
    as observed components, and their hypothesis relationships are downgraded
    to inferred call edges.  This supports normal-run process summaries while
    keeping fault-chain provenance unchanged.
    """

    event_by_id = {event["id"]: event for event in events}
    selected_ids = {
        event_id for event_id in highlighted_event_ids if event_id in event_by_id
    }
    if anchor_id in event_by_id:
        selected_ids.add(anchor_id)
    selected_relationships = [
        relationship
        for relationship in relationships
        if relationship.get("source_event_id") in selected_ids
        and relationship.get("target_event_id") in selected_ids
    ]
    has_cross_component_chain = any(
        event_by_id[relationship["source_event_id"]]["component"]
        != event_by_id[relationship["target_event_id"]]["component"]
        for relationship in selected_relationships
        if relationship.get("source_event_id") in event_by_id
        and relationship.get("target_event_id") in event_by_id
    )
    if not has_cross_component_chain and context_event_ids is not None:
        selected_ids.update(
            event_id
            for event_id in context_event_ids
            if event_id in event_by_id
            and event_by_id[event_id]["component"] in _CALL_ORDER_INDEX
        )
    selected_events = sorted(
        (event_by_id[event_id] for event_id in selected_ids), key=_event_key
    )
    by_component: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in selected_events:
        by_component[event["component"]].append(event)

    selected_relationships = [
        relationship
        for relationship in relationships
        if relationship.get("source_event_id") in selected_ids
        and relationship.get("target_event_id") in selected_ids
    ]
    error_related_ids = {
        event_id
        for relationship in selected_relationships
        if relationship.get("kind") == "error-propagation"
        for event_id in (
            relationship["source_event_id"],
            relationship["target_event_id"],
        )
    }

    ordered_components = sorted(
        by_component,
        key=lambda component: _component_key(component, by_component[component]),
    )
    nodes = []
    for index, component in enumerate(ordered_components, start=1):
        component_events = sorted(by_component[component], key=_event_key)
        representative = _representative_event(component_events, anchor_id)
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for event in component_events
                for evidence_id in event.get("evidence_ids", [])
            )
        )
        nodes.append(
            {
                "id": f"component-node-{index:03d}",
                "component": component,
                "member_event_ids": [event["id"] for event in component_events],
                "representative_event_id": representative["id"],
                "fault_role": _fault_role(
                    component, component_events, anchor_id, error_related_ids
                ),
                "summary": representative.get("message", ""),
                "summary_short": shorten_summary(representative.get("message", "")),
                "evidence_ids": evidence_ids,
                "deep_link": {
                    "view": "fault",
                    "anchor": anchor_id,
                    "component": component,
                    "event": representative["id"],
                },
            }
        )

    component_by_event_id = {
        event["id"]: event["component"] for event in selected_events
    }
    aggregate: dict[tuple[str, str, str], dict[str, Any]] = {}
    for relationship in selected_relationships:
        if relationship.get("kind") not in _NORMAL_RELATIONSHIP_KINDS:
            continue
        if relationship.get("strength") not in _STRENGTH_RANK:
            continue
        source_component = component_by_event_id[relationship["source_event_id"]]
        target_component = component_by_event_id[relationship["target_event_id"]]
        if source_component == target_component:
            continue
        if relationship["kind"] == "hypothesis":
            source_order = _CALL_ORDER_INDEX.get(source_component)
            target_order = _CALL_ORDER_INDEX.get(target_component)
            if source_order is None or target_order is None:
                continue
            if target_order < source_order:
                source_component, target_component = target_component, source_component
        kind = "notification" if relationship["kind"] == "notification" else "call"
        _append_edge_support(
            aggregate,
            source_component,
            target_component,
            kind=kind,
            strength=relationship["strength"],
            relationship=relationship,
        )

    # An explicit error path plus two observed components supports an inferred
    # normal-call dependency, but never a proven one.  Skip transitive
    # shortcuts when an existing normal path already connects the pair.
    for relationship in selected_relationships:
        if relationship.get("kind") != "error-propagation":
            continue
        error_source = component_by_event_id[relationship["source_event_id"]]
        error_target = component_by_event_id[relationship["target_event_id"]]
        if error_source == error_target:
            continue
        source_component, target_component = _normal_direction_for_error_path(
            error_source, error_target
        )
        pair_exists = any(
            edge["source_component"] == source_component
            and edge["target_component"] == target_component
            for edge in aggregate.values()
        )
        if pair_exists or _has_component_path(aggregate, source_component, target_component):
            continue
        _append_edge_support(
            aggregate,
            source_component,
            target_component,
            kind="call",
            strength="inferred",
            relationship=relationship,
            rule_id="observed-error-path-architecture-v1",
        )

    component_position = {
        component: index for index, component in enumerate(ordered_components)
    }
    edge_values = sorted(
        aggregate.values(),
        key=lambda edge: (
            component_position[edge["source_component"]],
            component_position[edge["target_component"]],
            edge["kind"],
        ),
    )
    edges = [
        {"id": f"component-edge-{index:03d}", **edge}
        for index, edge in enumerate(edge_values, start=1)
    ]

    gaps = []
    if len(nodes) > 1 and not edges:
        gaps.append("call_relationship_evidence_insufficient")
    elif len(nodes) > 1:
        connected_components = {
            component
            for edge in edges
            for component in (
                edge["source_component"],
                edge["target_component"],
            )
        }
        if any(node["component"] not in connected_components for node in nodes):
            gaps.append("unconnected_observed_components")

    return {
        "schema_version": COMPONENT_CHAIN_SCHEMA_VERSION,
        "anchor_id": anchor_id,
        "execution_event_ids": [event["id"] for event in selected_events],
        "nodes": nodes,
        "edges": edges,
        "gaps": gaps,
    }
