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

"""Build, validate, and render the versioned fault-trace contract."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import replace
from datetime import datetime, timedelta, timezone, tzinfo
import html
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .package_reader import ReaderLimits
from .parser import scan_input
from .component_chain import build_component_chain_summary
from .correlation import (
    build_clock_alignments,
    build_relationships,
    build_spans,
    clock_alignment_conflict_sources,
    evidence_conflict_groups,
    unmatched_span_endpoint_ids,
)
from .normalization import merge_exact_duplicate_events, semantic_event_fingerprint
from .redaction import Pseudonymizer


SCHEMA_VERSION = "1.0.0"
INVENTORY_SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = "0.6.0"
SEVERITY_RULES_VERSION = "1.1.0"
DEFAULT_CONTEXT_BEFORE_US = 1_000_000
DEFAULT_CONTEXT_AFTER_US = 100_000
DEFAULT_CONTEXT_EVENT_LIMIT = 20_000


def _optional_nonempty_string(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def parse_source_timezone(value: str | None) -> tuple[str | None, tzinfo | None]:
    value = _optional_nonempty_string("source_timezone", value)
    if value is None:
        return None, None
    if value in {"Z", "UTC"}:
        return value, timezone.utc
    offset_match = re.fullmatch(r"([+-])(\d{2}):(\d{2})", value)
    if offset_match is not None:
        hours = int(offset_match.group(2))
        minutes = int(offset_match.group(3))
        if hours > 23 or minutes > 59:
            raise ValueError("source_timezone has an invalid UTC offset")
        delta = timedelta(hours=hours, minutes=minutes)
        if offset_match.group(1) == "-":
            delta = -delta
        return value, timezone(delta)
    try:
        return value, ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(
            "source_timezone must be UTC, Z, an offset such as +08:00, or an available IANA zone"
        ) from error


def _apply_source_timezone(record: Any) -> Any:
    clock_alignment = record.clock_alignment
    if clock_alignment is not None and "wall-unknown-zone" in clock_alignment[0]:
        clock_alignment = (
            clock_alignment[0].replace("wall-unknown-zone", "wall-source-zone"),
            *clock_alignment[1:],
        )
    if "wall-unknown-zone" not in record.clock_kind:
        return replace(record, clock_alignment=clock_alignment)
    return replace(
        record,
        clock_kind=record.clock_kind.replace("wall-unknown-zone", "wall-source-zone"),
        clock_domain_id=record.clock_domain_id.replace("wall-unknown-zone", "wall-source-zone"),
        clock_alignment=clock_alignment,
    )


def _epoch_us(local_naive_us: int, zone: tzinfo) -> int:
    local_naive = datetime(1970, 1, 1) + timedelta(microseconds=local_naive_us)
    utc_naive = local_naive.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
    delta = utc_naive - datetime(1970, 1, 1)
    return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds


def _validate_anchor_request(request: dict[str, Any] | None) -> dict[str, Any] | None:
    if request is None:
        return None
    if not isinstance(request, dict) or set(request) != {"source", "selector"}:
        raise ValueError("anchor_request must contain source and selector")
    if request["source"] not in {"caller", "eval-skill"}:
        raise ValueError("anchor_request source must be caller or eval-skill")
    selector = request["selector"]
    if not isinstance(selector, dict) or selector.get("kind") not in {
        "event_id",
        "source_location",
    }:
        raise ValueError("anchor_request has an invalid selector")
    if selector["kind"] == "event_id":
        if (
            set(selector) != {"kind", "value"}
            or not isinstance(selector["value"], str)
            or not selector["value"]
        ):
            raise ValueError("event_id anchor must have a non-empty value")
    elif (
        set(selector) != {"kind", "source_path", "line"}
        or not isinstance(selector["source_path"], str)
        or not selector["source_path"]
        or type(selector["line"]) is not int
        or selector["line"] < 1
    ):
        raise ValueError("source_location anchor must have source_path and positive line")
    return request


def _redact_anchor_request(
    request: dict[str, Any], pseudonymizer: Pseudonymizer
) -> dict[str, Any]:
    selector = dict(request["selector"])
    if selector["kind"] == "source_location":
        selector["source_path"] = pseudonymizer.redact(selector["source_path"])
    return {"source": request["source"], "selector": selector}


def _resolve_anchor_request(
    events: list[dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    request: dict[str, Any] | None,
) -> str | None:
    if request is None:
        return None
    selector = request["selector"]
    if selector["kind"] == "event_id":
        requested_id = selector["value"]
        if any(event["id"] == requested_id for event in events):
            return requested_id
    else:
        requested_path = selector["source_path"].replace("\\", "/")
        requested_line = selector["line"]
        matches = [
            event["id"]
            for event in events
            if any(
                evidence[evidence_id]["source_path"].replace("\\", "/") == requested_path
                and evidence[evidence_id]["line"] == requested_line
                for evidence_id in event["evidence_ids"]
            )
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise NoUsableTraceError("requested fault anchor is ambiguous")
    raise NoUsableTraceError("requested fault anchor was not found")


def _redact_inventory(
    inventory: list[dict[str, object]], pseudonymizer: Pseudonymizer
) -> list[dict[str, object]]:
    redacted: list[dict[str, object]] = []
    for item in inventory:
        output = dict(item)
        for field in ("source_path", "reason", "detail"):
            if isinstance(output.get(field), str):
                output[field] = pseudonymizer.redact(output[field])
        redacted.append(output)
    return redacted


def build_trace(
    input_path: Path,
    limits: ReaderLimits | None = None,
    *,
    context_before_us: int = DEFAULT_CONTEXT_BEFORE_US,
    context_after_us: int = DEFAULT_CONTEXT_AFTER_US,
    context_event_limit: int = DEFAULT_CONTEXT_EVENT_LIMIT,
    anchor_request: dict[str, Any] | None = None,
    cann_version: str | None = None,
    source_timezone: str | None = None,
    additional_redaction_patterns: dict[str, str] | None = None,
) -> dict[str, Any]:
    for name, value in (
        ("context_before_us", context_before_us),
        ("context_after_us", context_after_us),
        ("context_event_limit", context_event_limit),
    ):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    cann_version = _optional_nonempty_string("cann_version", cann_version)
    timezone_value, timezone_info = parse_source_timezone(source_timezone)
    anchor_request = _validate_anchor_request(anchor_request)
    pseudonymizer = Pseudonymizer(additional_redaction_patterns)
    records, inventory, orphan_records, redaction_scope_id = scan_input(input_path, limits)
    if timezone_info is not None:
        records = [_apply_source_timezone(record) for record in records]
    audit = _inventory_audit(
        input_path,
        inventory,
        redaction_scope_id,
        pseudonymizer,
        additional_redaction_patterns,
    )
    if not records:
        raise NoUsableTraceError(
            "input contains no usable timestamped CANN records",
            audit,
        )

    records.sort(
        key=lambda item: (
            item.location != "host",
            item.clock_domain_id,
            item.timestamp_us,
            item.source_path,
            item.line,
        )
    )
    origin_by_domain: dict[str, int] = {}
    first_record_by_domain: dict[str, Any] = {}
    for record in records:
        if record.clock_domain_id not in origin_by_domain:
            origin_by_domain[record.clock_domain_id] = record.timestamp_us
            first_record_by_domain[record.clock_domain_id] = record
    evidence: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    next_evidence_index = 1

    for index, record in enumerate(records, start=1):
        evidence_id = f"evidence-{next_evidence_index:06d}"
        next_evidence_index += 1
        event_id = f"event-{index:06d}"
        evidence[evidence_id] = {
            "id": evidence_id,
            "source_path": pseudonymizer.redact(record.source_path),
            "line": record.line,
            "record_sha256": record.record_sha256,
            "excerpt": pseudonymizer.redact(record.excerpt),
        }
        event_evidence_ids = [evidence_id]
        for line_number, excerpt, record_sha256 in record.additional_evidence:
            supporting_evidence_id = f"evidence-{next_evidence_index:06d}"
            next_evidence_index += 1
            evidence[supporting_evidence_id] = {
                "id": supporting_evidence_id,
                "source_path": pseudonymizer.redact(record.source_path),
                "line": line_number,
                "record_sha256": record_sha256,
                "excerpt": pseudonymizer.redact(excerpt),
            }
            event_evidence_ids.append(supporting_evidence_id)
        execution = {"process": pseudonymizer.redact(record.process)}
        if record.pid is not None:
            execution["pid"] = record.pid
        if record.tid is not None:
            execution["tid"] = record.tid
        if (
            record.device_logical_id is not None
            or record.device_physical_id is not None
            or record.device_identity_conflict
        ):
            device_identity: dict[str, Any] = {}
            if record.device_logical_id is not None:
                device_identity["logical_id"] = record.device_logical_id
            if record.device_identity_conflict:
                device_identity.update(
                    {
                        "path_physical_id": record.device_path_physical_id,
                        "reported_physical_id": record.device_reported_physical_id,
                        "identity_status": "conflict",
                        "conflict_evidence_ids": [evidence_id],
                    }
                )
            elif record.device_physical_id is not None:
                device_identity["physical_id"] = record.device_physical_id
            if record.device_mapping_explicit:
                device_identity["mapping_strength"] = "proven"
                device_identity["mapping_evidence_ids"] = [evidence_id]
            execution["device"] = device_identity
        timestamp = {
            "raw": record.raw_timestamp,
            "clock_domain_id": record.clock_domain_id,
            "offset_us": record.timestamp_us - origin_by_domain[record.clock_domain_id],
            "precision": "microsecond",
        }
        if record.monotonic_raw is not None:
            timestamp["monotonic_raw"] = record.monotonic_raw
        if timezone_info is not None and "wall-source-zone" in record.clock_kind:
            timestamp["epoch_us"] = str(_epoch_us(record.timestamp_us, timezone_info))
        event = {
            "id": event_id,
            "kind": "observed",
            "level": record.level,
            "component": record.component,
            "raw_component": record.raw_module,
            "component_mapping_rule": record.component_mapping_rule,
            "message": pseudonymizer.redact(record.message),
            "location": record.location,
            "execution": execution,
            "timestamp": timestamp,
            "evidence_ids": event_evidence_ids,
        }
        if record.fault_rule_id is not None:
            event["fault_rule_id"] = record.fault_rule_id
        if record.correlation:
            event["correlation"] = dict(record.correlation)
        if record.interaction is not None:
            event["interaction"] = record.interaction
        if record.clock_alignment is not None:
            target_domain_id, offset_us, uncertainty_us, method = record.clock_alignment
            event["clock_alignment"] = {
                "target_clock_domain_id": target_domain_id,
                "offset_us": offset_us,
                "uncertainty_us": uncertainty_us,
                "method": method,
            }
        events.append(event)
    events = merge_exact_duplicate_events(events)
    candidate_ids = [
        event["id"] for event in events if "fault_rule_id" in event
    ]
    automatic_candidate_ids = list(candidate_ids)

    redacted_anchor_request = (
        _redact_anchor_request(anchor_request, pseudonymizer)
        if anchor_request is not None
        else None
    )
    requested_anchor_id = _resolve_anchor_request(events, evidence, redacted_anchor_request)
    if requested_anchor_id is not None and requested_anchor_id not in candidate_ids:
        candidate_ids.append(requested_anchor_id)
    if not candidate_ids:
        raise NoUsableTraceError("input contains no eligible fault anchor", audit)

    candidates = candidate_ids
    event_by_id = {event["id"]: event for event in events}
    relationships = build_relationships(events)
    spans = build_spans(events)
    clock_alignments = build_clock_alignments(events)
    clock_coordinates = _resolve_clock_coordinates(
        list(origin_by_domain), clock_alignments
    )
    _apply_aligned_timestamps(events, clock_coordinates)
    if requested_anchor_id is None:
        domain_candidate_ids, selected_anchor_id, selection_reason = _select_anchor(
            events, event_by_id, candidates, clock_coordinates
        )
        selection_status = "ambiguous" if len(domain_candidate_ids) > 1 else "selected"
    else:
        if automatic_candidate_ids:
            domain_candidate_ids, _, _ = _select_anchor(
                events, event_by_id, automatic_candidate_ids, clock_coordinates
            )
        else:
            domain_candidate_ids = [requested_anchor_id]
        selected_anchor_id = requested_anchor_id
        selection_reason = (
            "explicit_event_id"
            if anchor_request["selector"]["kind"] == "event_id"
            else "explicit_source_location"
        )
        selection_status = "selected"
    aligned_to_by_source = {
        alignment["source_clock_domain_id"]: alignment["target_clock_domain_id"]
        for alignment in clock_alignments
    }
    all_event_ids = [event["id"] for event in events]
    proven_neighbors = _proven_neighbors(all_event_ids, relationships)
    context_partitions, partition_by_scope = _build_context_partitions(
        events, event_by_id, candidates
    )
    context_indexes = {
        partition_id: _context_index(event_by_id, partition["event_ids"])
        for partition_id, partition in context_partitions.items()
    }
    views = [
        _build_anchor_view(
            event_by_id,
            all_event_ids,
            context_partitions,
            partition_by_scope,
            context_indexes,
            candidate_id,
            _reachable_event_ids(candidate_id, proven_neighbors, all_event_ids),
            context_before_us=context_before_us,
            context_after_us=context_after_us,
            context_event_limit=context_event_limit,
            materialize_context=candidate_id == selected_anchor_id,
        )
        for candidate_id in candidates
    ]
    selected_view = next(view for view in views if view["anchor_id"] == selected_anchor_id)
    component_chain = build_component_chain_summary(
        events,
        relationships,
        selected_anchor_id,
        selected_view["highlighted_event_ids"],
        selected_view.get("context_event_ids"),
    )
    excluded_event_ids = selected_view["excluded_event_ids"]
    has_host_records = any(event["location"] == "host" for event in events)
    has_device_records = any(event["location"] == "device" for event in events)
    gaps = []
    if not spans:
        gaps.append("no_call_spans")
    if unmatched_span_endpoint_ids(events, spans):
        gaps.append("unmatched_span_endpoints")
    if evidence_conflict_groups(events):
        gaps.append("evidence_conflicts")
    if not has_device_records:
        gaps.append("missing_device_logs")
    clock_roots = {
        clock_coordinates[event["timestamp"]["clock_domain_id"]][0]
        for event in events
    }
    if has_host_records and has_device_records and len(clock_roots) > 1:
        gaps.append("unaligned_host_device_clocks")
    if clock_alignment_conflict_sources(events):
        gaps.append("clock_alignment_conflict")
    if selected_view["scope"]["kind"] == "anchor-only":
        gaps.append("scope_ambiguity")
    ambiguous_domains = selection_status == "ambiguous"
    if ambiguous_domains:
        gaps.append("ambiguous_fault_anchor")
    if any(
        item["status"] in {"unsupported", "unreadable", "rejected"}
        or item["unparsed_records"]
        for item in inventory
    ):
        gaps.append("incomplete_parse_coverage")
    if selected_view["context_window"]["truncated"]:
        gaps.append("context_truncated")

    trace: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "partial",
        "metadata": {
            "generator_version": GENERATOR_VERSION,
            "parser_versions": {
                record.parser_name: record.parser_version
                for record in sorted(records, key=lambda item: item.parser_name)
            },
            "component_map_version": "1.1.0",
            "severity_rules_version": SEVERITY_RULES_VERSION,
            "redaction_scope": {
                "kind": "package-local",
                "scope_id": redaction_scope_id,
            },
        },
        "input": {
            "boundary": pseudonymizer.redact(input_path.name),
            "inventory": _redact_inventory(inventory, pseudonymizer),
        },
        "clock_domains": [
            {
                "id": domain_id,
                "kind": first_record_by_domain[domain_id].clock_kind,
                "origin_raw": first_record_by_domain[domain_id].raw_timestamp,
                "aligned_to": aligned_to_by_source.get(domain_id),
            }
            for domain_id in sorted(origin_by_domain)
        ],
        "events": events,
        "evidence": evidence,
        "orphan_evidence": [
            {
                "id": f"orphan-{index:06d}",
                "source_path": pseudonymizer.redact(orphan.source_path),
                "line": orphan.line,
                "record_sha256": orphan.record_sha256,
                "excerpt": pseudonymizer.redact(orphan.excerpt),
            }
            for index, orphan in enumerate(orphan_records, start=1)
        ],
        "relationships": relationships,
        "component_chain": component_chain,
        "clock_alignments": clock_alignments,
        "spans": spans,
        "fault_candidates": candidates,
        "selected_anchor_id": selected_anchor_id,
        "context_partitions": context_partitions,
        "views": views,
        "diagnostics": {
            "gaps": gaps,
            "event_count": len(events),
            "fault_candidate_count": len(candidates),
            "excluded_event_count": len(excluded_event_ids),
            "anchor_selection": {
                "status": selection_status,
                "reason": selection_reason,
                "domain_candidate_ids": domain_candidate_ids,
            },
            "parse_coverage": {
                "parsed_records": sum(int(item["parsed_records"]) for item in inventory),
                "unparsed_records": sum(int(item["unparsed_records"]) for item in inventory),
            },
            "context_window": {
                **selected_view["context_window"],
                "requested": dict(selected_view["context_window"]["requested"]),
            },
        },
    }
    if anchor_request is not None:
        trace["metadata"]["anchor_request"] = redacted_anchor_request
    if cann_version is not None:
        trace["metadata"]["cann_version"] = {"value": cann_version, "source": "caller"}
    if timezone_value is not None:
        trace["metadata"]["source_timezone"] = {
            "value": timezone_value,
            "source": "caller",
        }
    if additional_redaction_patterns:
        trace["metadata"]["redaction_rules"] = {
            "builtin_profile": "cann-trace-default-v1",
            "additional_pattern_names": sorted(additional_redaction_patterns),
            "source": "caller",
        }
    if any(item["status"] == "rejected" for item in inventory):
        trace["diagnostics"]["gaps"].append("uninspected_evidence")
    if any(item["status"] == "unsupported" for item in inventory):
        trace["diagnostics"]["gaps"].append("unsupported_input")
    if orphan_records:
        trace["diagnostics"]["gaps"].append("orphan_evidence")
    validate_trace(trace)
    return trace


def _build_context_partitions(
    events: list[dict[str, Any]],
    event_by_id: dict[str, dict[str, Any]],
    candidate_ids: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, str], str]]:
    events_by_scope: dict[tuple[str, str, str], list[str]] = {}
    for event in events:
        pid = event["execution"].get("pid")
        if pid is None:
            continue
        key = (event["location"], event["timestamp"]["clock_domain_id"], pid)
        events_by_scope.setdefault(key, []).append(event["id"])

    candidate_scopes = {
        (
            event_by_id[event_id]["location"],
            event_by_id[event_id]["timestamp"]["clock_domain_id"],
            event_by_id[event_id]["execution"]["pid"],
        )
        for event_id in candidate_ids
        if "pid" in event_by_id[event_id]["execution"]
    }
    partitions: dict[str, dict[str, Any]] = {}
    partition_by_scope: dict[tuple[str, str, str], str] = {}
    for index, key in enumerate(sorted(candidate_scopes), start=1):
        location, clock_domain_id, pid = key
        partition_id = f"context-{index:06d}"
        partitions[partition_id] = {
            "id": partition_id,
            "kind": "process",
            "pid": pid,
            "location": location,
            "clock_domain_id": clock_domain_id,
            "event_ids": events_by_scope[key],
        }
        partition_by_scope[key] = partition_id
    return partitions, partition_by_scope


def _build_anchor_view(
    event_by_id: dict[str, dict[str, Any]],
    all_event_ids: list[str],
    context_partitions: dict[str, dict[str, Any]],
    partition_by_scope: dict[tuple[str, str, str], str],
    context_indexes: dict[str, tuple[tuple[str, ...], tuple[int, ...], frozenset[str]]],
    anchor_id: str,
    highlighted_event_ids: list[str],
    *,
    context_before_us: int,
    context_after_us: int,
    context_event_limit: int,
    materialize_context: bool,
) -> dict[str, Any]:
    anchor = event_by_id[anchor_id]
    pid = anchor["execution"].get("pid")
    location = anchor["location"]
    clock_domain_id = anchor["timestamp"]["clock_domain_id"]
    if pid is None:
        context_event_ids = [anchor_id]
        context_index = _context_index(event_by_id, context_event_ids)
        scope = {
            "kind": "anchor-only",
            "anchor_event_id": anchor_id,
            "evidence_ids": anchor["evidence_ids"],
        }
    else:
        partition_id = partition_by_scope[(location, clock_domain_id, pid)]
        context_event_ids = context_partitions[partition_id]["event_ids"]
        context_index = context_indexes[partition_id]
        scope = {
            "kind": "process",
            "pid": pid,
            "location": location,
            "clock_domain_id": clock_domain_id,
            "evidence_ids": anchor["evidence_ids"],
        }
    full_scope_context = set(context_event_ids).union(highlighted_event_ids)
    resolved_context_event_ids, context_window = _bounded_context(
        event_by_id,
        all_event_ids,
        context_index,
        anchor_id,
        highlighted_event_ids,
        context_before_us,
        context_after_us,
        context_event_limit,
    )
    view = {
        "anchor_id": anchor_id,
        "highlighted_event_ids": highlighted_event_ids,
        "excluded_event_count": len(all_event_ids) - len(resolved_context_event_ids),
        "scope": scope,
        "context_window": context_window,
    }
    if (
        pid is None
        or materialize_context
        or set(resolved_context_event_ids) != full_scope_context
    ):
        view["context_event_ids"] = resolved_context_event_ids
    if pid is not None:
        view["context_partition_id"] = partition_id
    if materialize_context:
        context = set(resolved_context_event_ids)
        view["excluded_event_ids"] = [
            event_id for event_id in all_event_ids if event_id not in context
        ]
    return view


def _bounded_context(
    event_by_id: dict[str, dict[str, Any]],
    all_event_ids: list[str],
    context_index: tuple[tuple[str, ...], tuple[int, ...], frozenset[str]],
    anchor_id: str,
    highlighted_event_ids: list[str],
    before_us: int,
    after_us: int,
    event_limit: int,
) -> tuple[list[str], dict[str, Any]]:
    anchor = event_by_id[anchor_id]
    anchor_offset_us = anchor["timestamp"]["offset_us"]
    requested_start = anchor_offset_us - before_us
    requested_end = anchor_offset_us + after_us
    highlighted = set(highlighted_event_ids)
    scoped_event_ids, scoped_offsets, scoped_event_id_set = context_index
    start_index = bisect_left(scoped_offsets, requested_start)
    end_index = bisect_right(scoped_offsets, requested_end)
    within_window = [
        event_id
        for event_id in scoped_event_ids[start_index:end_index]
        if event_id not in highlighted
    ]
    order_by_id = {event_id: index for index, event_id in enumerate(all_event_ids)}
    nearest_ids = sorted(
        within_window,
        key=lambda event_id: (
            abs(event_by_id[event_id]["timestamp"]["offset_us"] - anchor_offset_us),
            event_by_id[event_id]["timestamp"]["offset_us"],
            order_by_id[event_id],
        ),
    )[:event_limit]
    included_non_chain = set(nearest_ids)
    effective_context = included_non_chain.union(highlighted)
    resolved_context = [
        event_id for event_id in all_event_ids if event_id in effective_context
    ]
    included_offsets = [
        event_by_id[event_id]["timestamp"]["offset_us"] for event_id in nearest_ids
    ]
    effective_start = min(included_offsets, default=anchor_offset_us)
    effective_end = max(included_offsets, default=anchor_offset_us)
    non_chain_count = len(scoped_event_ids) - len(
        highlighted.intersection(scoped_event_id_set)
    )
    outside_count = non_chain_count - len(within_window)
    limit_count = len(within_window) - len(nearest_ids)
    return resolved_context, {
        "clock_domain_id": anchor["timestamp"]["clock_domain_id"],
        "requested": {
            "before_us": before_us,
            "after_us": after_us,
            "non_chain_event_limit": event_limit,
        },
        "requested_start_offset_us": requested_start,
        "requested_end_offset_us": requested_end,
        "effective_start_offset_us": effective_start,
        "effective_end_offset_us": effective_end,
        "scope_event_count": len(scoped_event_ids),
        "included_non_chain_event_count": len(nearest_ids),
        "excluded_outside_window_count": outside_count,
        "excluded_by_limit_count": limit_count,
        "preserved_chain_event_count": len(highlighted_event_ids),
        "truncated": bool(outside_count or limit_count),
    }


def _context_index(
    event_by_id: dict[str, dict[str, Any]], event_ids: list[str]
) -> tuple[tuple[str, ...], tuple[int, ...], frozenset[str]]:
    ordered_ids = tuple(
        sorted(
            event_ids,
            key=lambda event_id: (
                event_by_id[event_id]["timestamp"]["offset_us"],
                event_id,
            ),
        )
    )
    return (
        ordered_ids,
        tuple(event_by_id[event_id]["timestamp"]["offset_us"] for event_id in ordered_ids),
        frozenset(ordered_ids),
    )


def _proven_neighbors(
    event_ids: list[str], relationships: list[dict[str, Any]]
) -> dict[str, set[str]]:
    neighbors = {event_id: set() for event_id in event_ids}
    for relationship in relationships:
        if relationship["strength"] != "proven":
            continue
        source_id = relationship["source_event_id"]
        target_id = relationship["target_event_id"]
        neighbors[source_id].add(target_id)
        neighbors[target_id].add(source_id)
    return neighbors


def _reachable_event_ids(
    anchor_id: str, neighbors: dict[str, set[str]], event_order: list[str]
) -> list[str]:
    reachable = {anchor_id}
    pending = [anchor_id]
    while pending:
        current = pending.pop()
        for neighbor in neighbors[current] - reachable:
            reachable.add(neighbor)
            pending.append(neighbor)
    return [event_id for event_id in event_order if event_id in reachable]


def _resolve_clock_coordinates(
    clock_domain_ids: list[str], clock_alignments: list[dict[str, Any]]
) -> dict[str, tuple[str, int, int]]:
    domain_id_set = set(clock_domain_ids)
    alignment_by_source = {
        alignment["source_clock_domain_id"]: alignment
        for alignment in clock_alignments
    }
    coordinates: dict[str, tuple[str, int, int]] = {}
    for domain_id in clock_domain_ids:
        current = domain_id
        offset_us = 0
        uncertainty_us = 0
        visited: set[str] = set()
        while current in alignment_by_source:
            if current in visited:
                raise TraceValidationError("clock alignment graph must be acyclic")
            visited.add(current)
            alignment = alignment_by_source[current]
            current = alignment["target_clock_domain_id"]
            if current not in domain_id_set:
                raise TraceValidationError("clock alignment references unknown domain")
            offset_us += alignment["offset_us"]
            uncertainty_us += alignment["uncertainty_us"]
        coordinates[domain_id] = (current, offset_us, uncertainty_us)
    return coordinates


def _apply_aligned_timestamps(
    events: list[dict[str, Any]],
    clock_coordinates: dict[str, tuple[str, int, int]],
) -> None:
    group_sizes: dict[str, int] = {}
    for root_id, _, _ in clock_coordinates.values():
        group_sizes[root_id] = group_sizes.get(root_id, 0) + 1
    for event in events:
        timestamp = event["timestamp"]
        root_id, offset_us, uncertainty_us = clock_coordinates[
            timestamp["clock_domain_id"]
        ]
        if group_sizes[root_id] <= 1:
            continue
        timestamp["aligned_clock_domain_id"] = root_id
        timestamp["aligned_offset_us"] = timestamp["offset_us"] + offset_us
        timestamp["alignment_uncertainty_us"] = uncertainty_us


def _select_anchor(
    events: list[dict[str, Any]],
    event_by_id: dict[str, dict[str, Any]],
    candidate_ids: list[str],
    clock_coordinates: dict[str, tuple[str, int, int]],
) -> tuple[list[str], str, str]:
    candidate_by_clock_group: dict[str, dict[str, Any]] = {}
    for event_id in candidate_ids:
        event = event_by_id[event_id]
        timestamp = event["timestamp"]
        root_id, offset_us, _ = clock_coordinates[timestamp["clock_domain_id"]]
        aligned_offset_us = timestamp["offset_us"] + offset_us
        current = candidate_by_clock_group.get(root_id)
        if current is None or (aligned_offset_us, event_id) < (
            current["aligned_offset_us"],
            current["event"]["id"],
        ):
            candidate_by_clock_group[root_id] = {
                "event": event,
                "aligned_offset_us": aligned_offset_us,
            }
    selected_by_group = sorted(
        candidate_by_clock_group.items(),
        key=lambda item: (
            item[1]["event"]["location"] != "host",
            item[0],
        ),
    )
    domain_candidate_ids = [item[1]["event"]["id"] for item in selected_by_group]
    candidate_domain_ids = {
        event_by_id[event_id]["timestamp"]["clock_domain_id"]
        for event_id in candidate_ids
    }
    reason = (
        "unaligned_clock_domains"
        if len(domain_candidate_ids) > 1
        else "aligned_clock_domains"
        if len(candidate_domain_ids) > 1
        else "single_clock_domain"
    )
    return domain_candidate_ids, domain_candidate_ids[0], reason


def _relationship_signature(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item.get("source_event_id"),
        item.get("target_event_id"),
        item.get("kind"),
        item.get("strength"),
        item.get("rule_id"),
        tuple(item.get("evidence_ids", [])),
    )


def _clock_alignment_signature(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item.get("source_clock_domain_id"),
        item.get("target_clock_domain_id"),
        item.get("method"),
        item.get("offset_us"),
        item.get("uncertainty_us"),
        tuple(item.get("evidence_ids", [])),
    )


def _span_signature(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item.get("start_event_id"),
        item.get("end_event_id"),
        item.get("duration_us"),
        tuple(item.get("evidence_ids", [])),
    )


def validate_trace(trace: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "status",
        "metadata",
        "input",
        "clock_domains",
        "events",
        "evidence",
        "relationships",
        "spans",
        "fault_candidates",
        "selected_anchor_id",
        "views",
        "diagnostics",
    }
    missing = required.difference(trace)
    if missing:
        raise TraceValidationError(f"missing required fields: {sorted(missing)}")
    if trace["schema_version"] != SCHEMA_VERSION:
        raise TraceValidationError("unsupported schema_version")
    if trace["status"] not in {"complete", "partial"}:
        raise TraceValidationError("invalid status")
    if not isinstance(trace["metadata"], dict):
        raise TraceValidationError("metadata must be an object")
    metadata_fields = (
        "generator_version",
        "parser_versions",
        "component_map_version",
        "severity_rules_version",
    )
    if any(field not in trace["metadata"] for field in metadata_fields):
        raise TraceValidationError("metadata is missing version fields")
    if any(
        not isinstance(trace["metadata"][field], str)
        for field in ("generator_version", "component_map_version", "severity_rules_version")
    ):
        raise TraceValidationError("metadata versions must be strings")
    parser_versions = trace["metadata"]["parser_versions"]
    if not isinstance(parser_versions, dict) or not all(
        isinstance(name, str) and isinstance(version, str)
        for name, version in parser_versions.items()
    ):
        raise TraceValidationError("parser_versions must map names to version strings")
    if "redaction_scope" in trace["metadata"]:
        redaction_scope = trace["metadata"]["redaction_scope"]
        if (
            not isinstance(redaction_scope, dict)
            or redaction_scope.get("kind") != "package-local"
            or not isinstance(redaction_scope.get("scope_id"), str)
            or re.fullmatch(r"[0-9a-f]{16}", redaction_scope["scope_id"]) is None
        ):
            raise TraceValidationError("invalid package-local redaction scope")
    for field in ("cann_version", "source_timezone"):
        if field in trace["metadata"]:
            value = trace["metadata"][field]
            if (
                not isinstance(value, dict)
                or set(value) != {"value", "source"}
                or not isinstance(value["value"], str)
                or not value["value"]
                or value["source"] != "caller"
            ):
                raise TraceValidationError(f"invalid {field} metadata")
            if field == "source_timezone":
                try:
                    parse_source_timezone(value["value"])
                except ValueError as error:
                    raise TraceValidationError("invalid source_timezone metadata") from error
    anchor_request = trace["metadata"].get("anchor_request")
    if anchor_request is not None:
        try:
            _validate_anchor_request(anchor_request)
        except ValueError as error:
            raise TraceValidationError("invalid anchor request metadata") from error
    redaction_rules = trace["metadata"].get("redaction_rules")
    if redaction_rules is not None and (
        not isinstance(redaction_rules, dict)
        or set(redaction_rules)
        != {"builtin_profile", "additional_pattern_names", "source"}
        or redaction_rules["builtin_profile"] != "cann-trace-default-v1"
        or redaction_rules["source"] != "caller"
        or not isinstance(redaction_rules["additional_pattern_names"], list)
        or not redaction_rules["additional_pattern_names"]
        or not all(
            isinstance(name, str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", name) is not None
            for name in redaction_rules["additional_pattern_names"]
        )
        or len(redaction_rules["additional_pattern_names"])
        != len(set(redaction_rules["additional_pattern_names"]))
    ):
        raise TraceValidationError("invalid redaction rules metadata")
    if not isinstance(trace["events"], list) or not trace["events"]:
        raise TraceValidationError("events must be a non-empty array")
    if not isinstance(trace["clock_domains"], list) or not trace["clock_domains"]:
        raise TraceValidationError("clock_domains must be a non-empty array")
    if not isinstance(trace["evidence"], dict):
        raise TraceValidationError("evidence must be an object")
    if "orphan_evidence" in trace and not isinstance(trace["orphan_evidence"], list):
        raise TraceValidationError("orphan_evidence must be an array")
    if not isinstance(trace["relationships"], list) or not isinstance(trace["spans"], list):
        raise TraceValidationError("relationships and spans must be arrays")
    if not isinstance(trace["fault_candidates"], list) or not trace["fault_candidates"]:
        raise TraceValidationError("fault_candidates must be a non-empty array")
    if not isinstance(trace["views"], list) or not trace["views"]:
        raise TraceValidationError("views must be a non-empty array")

    events = list(trace["events"])
    if not all(isinstance(event, dict) for event in events):
        raise TraceValidationError("events must contain objects")
    if not all(isinstance(domain, dict) for domain in trace["clock_domains"]):
        raise TraceValidationError("clock_domains must contain objects")
    event_id_list = [event.get("id") for event in events]
    if not all(isinstance(event_id, str) for event_id in event_id_list):
        raise TraceValidationError("event IDs must be strings")
    event_ids = set(event_id_list)
    event_by_id = {event["id"]: event for event in events}
    evidence_ids = set(trace["evidence"])
    clock_domain_id_list = [domain.get("id") for domain in trace["clock_domains"]]
    if not all(isinstance(domain_id, str) for domain_id in clock_domain_id_list):
        raise TraceValidationError("clock domain IDs must be strings")
    clock_domain_ids = set(clock_domain_id_list)
    if None in event_ids or len(event_ids) != len(event_id_list):
        raise TraceValidationError("event IDs must be present and unique")
    if None in clock_domain_ids or len(clock_domain_ids) != len(clock_domain_id_list):
        raise TraceValidationError("clock domain IDs must be present and unique")
    for domain in trace["clock_domains"]:
        if not {"id", "kind", "origin_raw", "aligned_to"}.issubset(domain):
            raise TraceValidationError("clock domain is missing required fields")
        if (
            not isinstance(domain["id"], str)
            or not isinstance(domain["kind"], str)
            or not isinstance(domain["origin_raw"], str)
            or (domain["aligned_to"] is not None and not isinstance(domain["aligned_to"], str))
        ):
            raise TraceValidationError("invalid clock domain field type")
        if domain["aligned_to"] is not None and (
            domain["aligned_to"] not in clock_domain_ids
            or domain["aligned_to"] == domain["id"]
        ):
            raise TraceValidationError("clock domain aligned_to must reference another domain")

    input_record = trace["input"]
    if not isinstance(input_record, dict) or not {"boundary", "inventory"}.issubset(input_record):
        raise TraceValidationError("input is missing required fields")
    if not isinstance(input_record["boundary"], str) or not isinstance(input_record["inventory"], list):
        raise TraceValidationError("invalid input field type")
    for inventory_entry in input_record["inventory"]:
        if not isinstance(inventory_entry, dict) or not {
            "source_path",
            "status",
            "parsed_records",
            "unparsed_records",
        }.issubset(inventory_entry):
            raise TraceValidationError("inventory entry is missing required fields")
        if (
            not isinstance(inventory_entry["source_path"], str)
            or inventory_entry["status"] not in {"parsed", "unsupported", "unreadable", "rejected", "archive"}
            or type(inventory_entry["parsed_records"]) is not int
            or type(inventory_entry["unparsed_records"]) is not int
            or inventory_entry["parsed_records"] < 0
            or inventory_entry["unparsed_records"] < 0
        ):
            raise TraceValidationError("invalid inventory entry")
        if "parser" in inventory_entry and inventory_entry["parser"] is not None and not isinstance(inventory_entry["parser"], str):
            raise TraceValidationError("inventory parser must be a string or null")
        if "reason" in inventory_entry and not isinstance(inventory_entry["reason"], str):
            raise TraceValidationError("inventory reason must be a string")
        if "detail" in inventory_entry and not isinstance(inventory_entry["detail"], str):
            raise TraceValidationError("inventory detail must be a string")
        if "size_bytes" in inventory_entry and (
            type(inventory_entry["size_bytes"]) is not int or inventory_entry["size_bytes"] < 0
        ):
            raise TraceValidationError("inventory size_bytes must be a non-negative integer")
        if "content_sha256" in inventory_entry and (
            not isinstance(inventory_entry["content_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", inventory_entry["content_sha256"]) is None
        ):
            raise TraceValidationError("inventory content_sha256 must be a SHA-256 string")
    for evidence_id, evidence_record in trace["evidence"].items():
        if not isinstance(evidence_id, str):
            raise TraceValidationError("evidence IDs must be strings")
        if not isinstance(evidence_record, dict):
            raise TraceValidationError("evidence records must be objects")
        evidence_required = {"id", "source_path", "line", "record_sha256", "excerpt"}
        if not evidence_required.issubset(evidence_record):
            raise TraceValidationError("evidence record is missing required fields")
        if evidence_record.get("id") != evidence_id:
            raise TraceValidationError("evidence key and ID must match")
        if (
            not isinstance(evidence_record["source_path"], str)
            or type(evidence_record["line"]) is not int
            or evidence_record["line"] < 1
            or not isinstance(evidence_record["record_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", evidence_record["record_sha256"]) is None
            or not isinstance(evidence_record["excerpt"], str)
        ):
            raise TraceValidationError("invalid evidence field type or value")
    orphan_ids: list[str] = []
    for orphan in trace.get("orphan_evidence", []):
        if not isinstance(orphan, dict) or not {
            "id",
            "source_path",
            "line",
            "record_sha256",
            "excerpt",
        }.issubset(orphan):
            raise TraceValidationError("orphan evidence is missing required fields")
        if (
            not isinstance(orphan["id"], str)
            or not isinstance(orphan["source_path"], str)
            or type(orphan["line"]) is not int
            or orphan["line"] < 1
            or not isinstance(orphan["record_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", orphan["record_sha256"]) is None
            or not isinstance(orphan["excerpt"], str)
        ):
            raise TraceValidationError("invalid orphan evidence")
        orphan_ids.append(orphan["id"])
    if len(orphan_ids) != len(set(orphan_ids)):
        raise TraceValidationError("orphan evidence IDs must be unique")
    if (
        not all(isinstance(candidate_id, str) for candidate_id in trace["fault_candidates"])
        or len(trace["fault_candidates"]) != len(set(trace["fault_candidates"]))
        or not isinstance(trace["selected_anchor_id"], str)
    ):
        raise TraceValidationError("fault candidate and selected anchor IDs must be unique strings")
    if not set(trace["fault_candidates"]).issubset(event_ids):
        raise TraceValidationError("fault candidate references an unknown event")
    if trace["selected_anchor_id"] not in event_ids:
        raise TraceValidationError("selected anchor does not reference an event")
    if trace["selected_anchor_id"] not in trace["fault_candidates"]:
        raise TraceValidationError("selected anchor is not a fault candidate")

    for event in events:
        event_required = {
            "id",
            "kind",
            "level",
            "component",
            "raw_component",
            "message",
            "location",
            "execution",
            "timestamp",
            "evidence_ids",
        }
        if not event_required.issubset(event):
            raise TraceValidationError("event is missing required fields")
        if event["kind"] != "observed" or event["location"] not in {"host", "device"}:
            raise TraceValidationError("invalid event kind or location")
        if not all(
            isinstance(event[field], str)
            for field in ("id", "level", "component", "raw_component", "message")
        ):
            raise TraceValidationError("event text fields must be strings")
        if "component_mapping_rule" in event and not isinstance(event["component_mapping_rule"], str):
            raise TraceValidationError("event component_mapping_rule must be a string")
        if "fault_rule_id" in event and not isinstance(event["fault_rule_id"], str):
            raise TraceValidationError("event fault_rule_id must be a string")
        if "correlation" in event:
            correlation = event["correlation"]
            allowed_correlation_fields = {
                "stream_id",
                "task_id",
                "event_id",
                "node_id",
                "assertion",
                "alarm_raised_time",
                "device_id",
                "error_code",
                "hccl_ret",
                "rank_id",
            }
            if (
                not isinstance(correlation, dict)
                or not correlation
                or not set(correlation).issubset(allowed_correlation_fields)
                or not all(
                    isinstance(key, str) and isinstance(value, str)
                    for key, value in correlation.items()
                )
            ):
                raise TraceValidationError("invalid event correlation")
        if "interaction" in event and event["interaction"] not in {
            "dispatch",
            "notify-host",
            "receive-device-event",
            "return",
            "error-source",
            "error-propagation",
        }:
            raise TraceValidationError("invalid event interaction")
        if "clock_alignment" in event:
            alignment = event["clock_alignment"]
            if (
                not isinstance(alignment, dict)
                or not {
                    "target_clock_domain_id",
                    "offset_us",
                    "uncertainty_us",
                    "method",
                }.issubset(alignment)
                or not isinstance(alignment["target_clock_domain_id"], str)
                or alignment["target_clock_domain_id"] not in clock_domain_ids
                or alignment["target_clock_domain_id"] == event["timestamp"]["clock_domain_id"]
                or type(alignment["offset_us"]) is not int
                or type(alignment["uncertainty_us"]) is not int
                or alignment["uncertainty_us"] < 0
                or not isinstance(alignment["method"], str)
                or not alignment["method"]
            ):
                raise TraceValidationError("invalid event clock alignment declaration")
        if not isinstance(event["execution"], dict):
            raise TraceValidationError("event execution must be an object")
        execution = event["execution"]
        if "pid" in execution and not isinstance(execution["pid"], str):
            raise TraceValidationError("event execution pid must be a string")
        if "process" in execution and not isinstance(execution["process"], str):
            raise TraceValidationError("event execution process must be a string")
        if "tid" in execution and not isinstance(execution["tid"], str):
            raise TraceValidationError("event execution tid must be a string")
        if "device" in execution:
            device = execution["device"]
            if not isinstance(device, dict) or not any(
                key in device for key in ("logical_id", "physical_id", "identity_status")
            ):
                raise TraceValidationError("invalid event device identity")
            if any(
                key in device and not isinstance(device[key], str)
                for key in (
                    "logical_id",
                    "physical_id",
                    "path_physical_id",
                    "reported_physical_id",
                    "identity_status",
                )
            ):
                raise TraceValidationError("device IDs must be strings")
            has_conflict = any(
                key in device
                for key in (
                    "path_physical_id",
                    "reported_physical_id",
                    "identity_status",
                    "conflict_evidence_ids",
                )
            )
            if has_conflict:
                conflict_evidence = device.get("conflict_evidence_ids")
                if (
                    device.get("identity_status") != "conflict"
                    or not all(
                        key in device
                        for key in (
                            "logical_id",
                            "path_physical_id",
                            "reported_physical_id",
                        )
                    )
                    or device["path_physical_id"] == device["reported_physical_id"]
                    or any(
                        key in device
                        for key in ("physical_id", "mapping_strength", "mapping_evidence_ids")
                    )
                    or not isinstance(conflict_evidence, list)
                    or not conflict_evidence
                    or not all(isinstance(item, str) for item in conflict_evidence)
                    or len(conflict_evidence) != len(set(conflict_evidence))
                    or not set(conflict_evidence).issubset(event["evidence_ids"])
                ):
                    raise TraceValidationError("invalid conflicting Device identity")
            has_mapping = "mapping_strength" in device or "mapping_evidence_ids" in device
            mapping_evidence = device.get("mapping_evidence_ids")
            if "logical_id" in device and "physical_id" in device and not has_mapping:
                raise TraceValidationError("logical/physical Device mapping requires proof")
            if has_mapping and (
                device.get("mapping_strength") != "proven"
                or "logical_id" not in device
                or "physical_id" not in device
                or not isinstance(mapping_evidence, list)
                or not mapping_evidence
                or not all(isinstance(item, str) for item in mapping_evidence)
                or len(mapping_evidence) != len(set(mapping_evidence))
                or not set(mapping_evidence).issubset(event["evidence_ids"])
            ):
                raise TraceValidationError("invalid proven Device mapping")
        timestamp = event.get("timestamp", {})
        if not isinstance(timestamp, dict) or not {
            "raw",
            "clock_domain_id",
            "offset_us",
            "precision",
        }.issubset(timestamp):
            raise TraceValidationError("event timestamp is missing required fields")
        if not isinstance(timestamp["raw"], str) or timestamp["precision"] != "microsecond":
            raise TraceValidationError("invalid event timestamp text or precision")
        if type(timestamp.get("offset_us")) is not int:
            raise TraceValidationError("event offset_us must be an integer")
        if not isinstance(timestamp["clock_domain_id"], str):
            raise TraceValidationError("event clock_domain_id must be a string")
        if "monotonic_raw" in timestamp and not isinstance(timestamp["monotonic_raw"], str):
            raise TraceValidationError("event monotonic_raw must be a string")
        if "epoch_us" in timestamp and (
            not isinstance(timestamp["epoch_us"], str)
            or re.fullmatch(r"-?[0-9]+", timestamp["epoch_us"]) is None
        ):
            raise TraceValidationError("event epoch_us must be a decimal string")
        aligned_timestamp_fields = {
            "aligned_clock_domain_id",
            "aligned_offset_us",
            "alignment_uncertainty_us",
        }
        present_aligned_fields = aligned_timestamp_fields.intersection(timestamp)
        if present_aligned_fields and present_aligned_fields != aligned_timestamp_fields:
            raise TraceValidationError("event aligned timestamp fields must be complete")
        if present_aligned_fields and (
            not isinstance(timestamp["aligned_clock_domain_id"], str)
            or type(timestamp["aligned_offset_us"]) is not int
            or type(timestamp["alignment_uncertainty_us"]) is not int
            or timestamp["alignment_uncertainty_us"] < 0
        ):
            raise TraceValidationError("invalid event aligned timestamp")
        if timestamp.get("clock_domain_id") not in clock_domain_ids:
            raise TraceValidationError("event references an unknown clock domain")
        if not isinstance(event["evidence_ids"], list) or not event["evidence_ids"]:
            raise TraceValidationError("event evidence_ids must be a non-empty array")
        if (
            not all(isinstance(evidence_id, str) for evidence_id in event["evidence_ids"])
            or len(event["evidence_ids"]) != len(set(event["evidence_ids"]))
        ):
            raise TraceValidationError("event evidence_ids must be unique strings")
        if not set(event["evidence_ids"]).issubset(evidence_ids):
            raise TraceValidationError("event references unknown evidence")

    fingerprints = [semantic_event_fingerprint(event) for event in events]
    if len(fingerprints) != len(set(fingerprints)):
        raise TraceValidationError("exact duplicate events must be merged")
    has_source_timezone = "source_timezone" in trace["metadata"]
    wall_events = [
        event
        for event in events
        if "wall-source-zone" in next(
            domain["kind"]
            for domain in trace["clock_domains"]
            if domain["id"] == event["timestamp"]["clock_domain_id"]
        )
    ]
    if (not has_source_timezone and wall_events) or any(
        "epoch_us" not in event["timestamp"] for event in wall_events
    ):
        raise TraceValidationError("source timezone and wall-clock epoch metadata disagree")

    clock_alignments = trace.get("clock_alignments")
    if clock_alignments is not None:
        if not isinstance(clock_alignments, list):
            raise TraceValidationError("clock_alignments must be an array")
        alignment_ids: list[str] = []
        aligned_sources: set[str] = set()
        for alignment in clock_alignments:
            if not isinstance(alignment, dict) or not {
                "id",
                "source_clock_domain_id",
                "target_clock_domain_id",
                "method",
                "offset_us",
                "uncertainty_us",
                "evidence_ids",
            }.issubset(alignment):
                raise TraceValidationError("clock alignment is missing required fields")
            alignment_ids.append(alignment["id"])
            source_id = alignment["source_clock_domain_id"]
            target_id = alignment["target_clock_domain_id"]
            alignment_evidence_ids = alignment["evidence_ids"]
            if (
                not isinstance(alignment["id"], str)
                or not isinstance(source_id, str)
                or not isinstance(target_id, str)
                or source_id not in clock_domain_ids
                or target_id not in clock_domain_ids
                or source_id == target_id
                or not isinstance(alignment["method"], str)
                or not alignment["method"]
                or type(alignment["offset_us"]) is not int
                or type(alignment["uncertainty_us"]) is not int
                or alignment["uncertainty_us"] < 0
                or not isinstance(alignment_evidence_ids, list)
                or not alignment_evidence_ids
                or not all(isinstance(item, str) for item in alignment_evidence_ids)
                or len(alignment_evidence_ids) != len(set(alignment_evidence_ids))
                or not set(alignment_evidence_ids).issubset(evidence_ids)
                or source_id in aligned_sources
            ):
                raise TraceValidationError("invalid clock alignment")
            source_domain = next(
                domain for domain in trace["clock_domains"] if domain["id"] == source_id
            )
            if source_domain["aligned_to"] != target_id:
                raise TraceValidationError("clock domain and alignment record disagree")
            aligned_sources.add(source_id)
        if len(alignment_ids) != len(set(alignment_ids)):
            raise TraceValidationError("clock alignment IDs must be unique")
        declared_aligned_sources = {
            domain["id"] for domain in trace["clock_domains"] if domain["aligned_to"] is not None
        }
        if aligned_sources != declared_aligned_sources:
            raise TraceValidationError("clock domains require matching alignment records")
        expected_alignments = build_clock_alignments(events)
        if sorted(
            (_clock_alignment_signature(item) for item in clock_alignments),
            key=repr,
        ) != sorted(
            (_clock_alignment_signature(item) for item in expected_alignments),
            key=repr,
        ):
            raise TraceValidationError(
                "clock alignments do not match event declarations"
            )

    domain_target = {
        domain["id"]: domain["aligned_to"]
        for domain in trace["clock_domains"]
        if domain["aligned_to"] is not None
    }
    for source_id in domain_target:
        visited: set[str] = set()
        current: str | None = source_id
        while current is not None:
            if current in visited:
                raise TraceValidationError("clock alignment graph must be acyclic")
            visited.add(current)
            current = domain_target.get(current)

    effective_alignments = clock_alignments if clock_alignments is not None else []
    clock_coordinates = _resolve_clock_coordinates(
        clock_domain_id_list, effective_alignments
    )
    alignment_group_sizes: dict[str, int] = {}
    for root_id, _, _ in clock_coordinates.values():
        alignment_group_sizes[root_id] = alignment_group_sizes.get(root_id, 0) + 1
    aligned_timestamp_fields = {
        "aligned_clock_domain_id",
        "aligned_offset_us",
        "alignment_uncertainty_us",
    }
    for event in events:
        timestamp = event["timestamp"]
        root_id, alignment_offset_us, uncertainty_us = clock_coordinates[
            timestamp["clock_domain_id"]
        ]
        expected_alignment = alignment_group_sizes[root_id] > 1
        actual_fields = aligned_timestamp_fields.intersection(timestamp)
        if expected_alignment:
            if actual_fields != aligned_timestamp_fields or (
                timestamp["aligned_clock_domain_id"] != root_id
                or timestamp["aligned_offset_us"]
                != timestamp["offset_us"] + alignment_offset_us
                or timestamp["alignment_uncertainty_us"] != uncertainty_us
            ):
                raise TraceValidationError(
                    "event aligned timestamp does not match clock alignment"
                )
        elif actual_fields:
            raise TraceValidationError(
                "event aligned timestamp requires a shared clock group"
            )

    event_ids_by_scope: dict[tuple[str, str, str], set[str]] = {}
    for event in events:
        pid = event["execution"].get("pid")
        if pid is not None:
            scope_key = (
                event["location"],
                event["timestamp"]["clock_domain_id"],
                pid,
            )
            event_ids_by_scope.setdefault(scope_key, set()).add(event["id"])

    context_partitions = trace.get("context_partitions", {})
    if not isinstance(context_partitions, dict):
        raise TraceValidationError("context_partitions must be an object")
    partition_scopes: set[tuple[str, str, str]] = set()
    partition_event_id_sets: dict[str, set[str]] = {}
    partition_context_indexes: dict[
        str, tuple[tuple[str, ...], tuple[int, ...], frozenset[str]]
    ] = {}
    for partition_id, partition in context_partitions.items():
        if not isinstance(partition_id, str) or not isinstance(partition, dict):
            raise TraceValidationError("context partitions must map string IDs to objects")
        if not {
            "id",
            "kind",
            "pid",
            "location",
            "clock_domain_id",
            "event_ids",
        }.issubset(partition):
            raise TraceValidationError("context partition is missing required fields")
        partition_event_ids = partition["event_ids"]
        if (
            partition["id"] != partition_id
            or partition["kind"] != "process"
            or not isinstance(partition["pid"], str)
            or partition["location"] not in {"host", "device"}
            or not isinstance(partition["clock_domain_id"], str)
            or partition["clock_domain_id"] not in clock_domain_ids
            or not isinstance(partition_event_ids, list)
            or not partition_event_ids
            or not all(isinstance(event_id, str) for event_id in partition_event_ids)
        ):
            raise TraceValidationError("invalid context partition")
        partition_event_id_set = set(partition_event_ids)
        if (
            len(partition_event_ids) != len(partition_event_id_set)
            or not partition_event_id_set.issubset(event_ids)
        ):
            raise TraceValidationError("invalid context partition")
        partition_event_id_sets[partition_id] = partition_event_id_set
        partition_context_indexes[partition_id] = _context_index(
            event_by_id, partition_event_ids
        )
        partition_scope = (
            partition["location"],
            partition["clock_domain_id"],
            partition["pid"],
        )
        if partition_scope in partition_scopes:
            raise TraceValidationError("context partition scopes must be unique")
        partition_scopes.add(partition_scope)
        if partition_event_id_set != event_ids_by_scope.get(partition_scope, set()):
            raise TraceValidationError("context partition does not match its process scope")

    relationship_ids: list[str] = []
    for relationship in trace["relationships"]:
        if not isinstance(relationship, dict) or not {
            "id",
            "source_event_id",
            "target_event_id",
            "strength",
            "evidence_ids",
        }.issubset(relationship):
            raise TraceValidationError("relationship is missing required fields")
        if not isinstance(relationship["id"], str):
            raise TraceValidationError("relationship ID must be a string")
        relationship_ids.append(relationship["id"])
        if not isinstance(relationship["source_event_id"], str) or not isinstance(relationship["target_event_id"], str):
            raise TraceValidationError("relationship event references must be strings")
        if relationship.get("strength") not in {"proven", "inferred", "conflict"}:
            raise TraceValidationError("invalid relationship strength")
        if "kind" in relationship and relationship["kind"] not in {
            "notification",
            "same-execution",
            "hypothesis",
            "evidence-conflict",
            "error-propagation",
        }:
            raise TraceValidationError("invalid relationship kind")
        if "rule_id" in relationship and not isinstance(relationship["rule_id"], str):
            raise TraceValidationError("relationship rule_id must be a string")
        if relationship.get("source_event_id") not in event_ids or relationship.get("target_event_id") not in event_ids:
            raise TraceValidationError("relationship references unknown event")
        if not isinstance(relationship["evidence_ids"], list) or not relationship["evidence_ids"]:
            raise TraceValidationError("relationship evidence_ids must be a non-empty array")
        if not all(isinstance(evidence_id, str) for evidence_id in relationship["evidence_ids"]):
            raise TraceValidationError("relationship evidence_ids must be strings")
        if not set(relationship["evidence_ids"]).issubset(evidence_ids):
            raise TraceValidationError("relationship references unknown evidence")
    if len(relationship_ids) != len(set(relationship_ids)):
        raise TraceValidationError("relationship IDs must be unique")
    for relationship in trace.get("component_relationships", []):
        if (
            not all(
                isinstance(relationship[field], str)
                for field in (
                    "id",
                    "source_component",
                    "target_component",
                    "kind",
                    "strength",
                    "rule_id",
                )
            )
            or relationship["source_component"] == relationship["target_component"]
            or relationship["kind"] not in {
                "notification",
                "same-execution",
                "hypothesis",
                "evidence-conflict",
                "error-propagation",
            }
            or relationship["strength"] not in {"proven", "inferred", "conflict"}
        ):
            raise TraceValidationError("invalid component relationship")
        for field in ("source_event_ids", "target_event_ids", "event_relationship_ids", "evidence_ids"):
            if (
                not isinstance(relationship[field], list)
                or not all(isinstance(item, str) for item in relationship[field])
            ):
                raise TraceValidationError("invalid component relationship")
    expected_relationships = build_relationships(events)
    if {
        _relationship_signature(item) for item in trace["relationships"]
    } != {
        _relationship_signature(item) for item in expected_relationships
    }:
        raise TraceValidationError("relationships do not match derivable event evidence")

    span_ids: list[str] = []
    for span in trace["spans"]:
        if not isinstance(span, dict) or not {
            "id",
            "start_event_id",
            "end_event_id",
            "duration_us",
            "evidence_ids",
        }.issubset(span):
            raise TraceValidationError("span is missing required fields")
        span_ids.append(span["id"])
        if not isinstance(span["id"], str):
            raise TraceValidationError("span ID must be a string")
        if not isinstance(span["start_event_id"], str) or not isinstance(span["end_event_id"], str):
            raise TraceValidationError("span event references must be strings")
        if span["start_event_id"] not in event_ids or span["end_event_id"] not in event_ids:
            raise TraceValidationError("span references unknown event")
        if type(span["duration_us"]) is not int or span["duration_us"] < 0:
            raise TraceValidationError("span duration_us must be a non-negative integer")
        if not isinstance(span["evidence_ids"], list) or len(span["evidence_ids"]) < 2:
            raise TraceValidationError("span requires start and end evidence")
        if not all(isinstance(evidence_id, str) for evidence_id in span["evidence_ids"]):
            raise TraceValidationError("span evidence_ids must be strings")
        if not set(span["evidence_ids"]).issubset(evidence_ids):
            raise TraceValidationError("span references unknown evidence")
    if len(span_ids) != len(set(span_ids)):
        raise TraceValidationError("span IDs must be unique")
    expected_spans = build_spans(events)
    if {
        _span_signature(item) for item in trace["spans"]
    } != {
        _span_signature(item) for item in expected_spans
    }:
        raise TraceValidationError("spans do not match derivable endpoint evidence")

    proven_neighbors = _proven_neighbors(event_id_list, trace["relationships"])

    view_anchor_ids: list[str] = []
    for view in trace["views"]:
        if not isinstance(view, dict) or not {
            "anchor_id",
            "highlighted_event_ids",
        }.issubset(view):
            raise TraceValidationError("view is missing required fields")
        if not isinstance(view["highlighted_event_ids"], list):
            raise TraceValidationError("view event references must be arrays")
        direct_context_ids = view.get("context_event_ids")
        partition_id = view.get("context_partition_id")
        if direct_context_ids is None and partition_id is None:
            raise TraceValidationError("view has no context")
        if direct_context_ids is not None and not isinstance(direct_context_ids, list):
            raise TraceValidationError("view event references must be arrays")
        if partition_id is not None and not isinstance(partition_id, str):
            raise TraceValidationError("view context_partition_id must be a string")
        partition = context_partitions.get(partition_id) if partition_id is not None else None
        if partition_id is not None and partition is None:
            raise TraceValidationError("view references an unknown context partition")
        partition_event_ids = partition["event_ids"] if partition is not None else None
        if not isinstance(view["anchor_id"], str) or not all(
            isinstance(event_id, str) for event_id in view["highlighted_event_ids"]
        ):
            raise TraceValidationError("view event references must be strings")
        if direct_context_ids is not None and not all(
            isinstance(event_id, str) for event_id in direct_context_ids
        ):
            raise TraceValidationError("view event references must be strings")
        view_anchor_ids.append(view["anchor_id"])
        if (
            len(view["highlighted_event_ids"]) != len(set(view["highlighted_event_ids"]))
            or (
                direct_context_ids is not None
                and len(direct_context_ids) != len(set(direct_context_ids))
            )
        ):
            raise TraceValidationError("view event references must be unique")
        anchor_id = view.get("anchor_id")
        if anchor_id not in trace["fault_candidates"]:
            raise TraceValidationError("view anchor must reference a fault candidate")
        highlighted_ids = set(view["highlighted_event_ids"])
        if partition is not None:
            partition_context_ids = partition_event_id_sets[partition_id]
            full_context_ids = partition_context_ids.union(highlighted_ids)
            if (
                view.get("context_window") is None
                and direct_context_ids is not None
                and set(direct_context_ids) != full_context_ids
            ):
                raise TraceValidationError("view context representations disagree")
            context_ids = (
                set(direct_context_ids)
                if direct_context_ids is not None
                else full_context_ids
            )
            context_event_ids = direct_context_ids or partition_event_ids
        else:
            context_event_ids = direct_context_ids
            context_ids = set(context_event_ids)
        if partition is None and not context_ids.issubset(event_ids):
            raise TraceValidationError("view context references an unknown event")
        if anchor_id not in context_ids:
            raise TraceValidationError("view context must contain its anchor")
        excluded_ids: list[str] | None = None
        if "excluded_event_ids" in view:
            excluded_ids = view["excluded_event_ids"]
            if (
                not isinstance(excluded_ids, list)
                or not all(isinstance(event_id, str) for event_id in excluded_ids)
                or len(excluded_ids) != len(set(excluded_ids))
                or not set(excluded_ids).issubset(event_ids)
                or context_ids.intersection(excluded_ids)
                or context_ids.union(excluded_ids) != event_ids
            ):
                raise TraceValidationError("invalid view excluded_event_ids")
        if "excluded_event_count" in view and (
            type(view["excluded_event_count"]) is not int
            or view["excluded_event_count"] < 0
            or view["excluded_event_count"] != len(event_ids) - len(context_ids)
        ):
            raise TraceValidationError("invalid view excluded_event_count")
        context_window = view.get("context_window")
        if context_window is not None:
            requested = (
                context_window.get("requested")
                if isinstance(context_window, dict)
                else None
            )
            if not isinstance(requested, dict) or any(
                type(requested.get(field)) is not int or requested[field] < 0
                for field in ("before_us", "after_us", "non_chain_event_limit")
            ):
                raise TraceValidationError("invalid context window")
            context_index = (
                partition_context_indexes[partition_id]
                if partition_id is not None
                else _context_index(event_by_id, [anchor_id])
            )
            expected_ids, expected_window = _bounded_context(
                event_by_id,
                event_id_list,
                context_index,
                anchor_id,
                view["highlighted_event_ids"],
                requested["before_us"],
                requested["after_us"],
                requested["non_chain_event_limit"],
            )
            if (
                context_window != expected_window
                or context_ids != set(expected_ids)
                or (
                    direct_context_ids is not None
                    and direct_context_ids != expected_ids
                )
            ):
                raise TraceValidationError("invalid context window")
        if "scope" in view:
            scope = view["scope"]
            if not isinstance(scope, dict):
                raise TraceValidationError("invalid view execution scope")
            scope_evidence = scope.get("evidence_ids")
            if (
                not isinstance(scope_evidence, list)
                or not scope_evidence
                or not all(isinstance(item, str) for item in scope_evidence)
                or len(scope_evidence) != len(set(scope_evidence))
                or not set(scope_evidence).issubset(evidence_ids)
            ):
                raise TraceValidationError("invalid view execution scope")
            anchor_event = event_by_id[anchor_id]
            if not set(scope_evidence).issubset(anchor_event["evidence_ids"]):
                raise TraceValidationError("scope evidence must come from the anchor")
            if scope.get("kind") == "process":
                scope_pid = scope.get("pid")
                scope_location = scope.get("location", anchor_event["location"])
                scope_domain = scope.get(
                    "clock_domain_id", anchor_event["timestamp"]["clock_domain_id"]
                )
                partition_scope_mismatch = partition is not None and (
                    partition["pid"] != scope_pid
                    or partition["location"] != scope_location
                    or partition["clock_domain_id"] != scope_domain
                )
                direct_scope_mismatch = partition is None and any(
                    (
                        event_by_id[event_id]["execution"].get("pid") != scope_pid
                        or event_by_id[event_id]["location"] != scope_location
                        or event_by_id[event_id]["timestamp"]["clock_domain_id"]
                        != scope_domain
                    )
                    and event_id not in view["highlighted_event_ids"]
                    for event_id in context_event_ids
                )
                if (
                    not isinstance(scope_pid, str)
                    or anchor_event["execution"].get("pid") != scope_pid
                    or scope_location != anchor_event["location"]
                    or scope_domain != anchor_event["timestamp"]["clock_domain_id"]
                    or partition_scope_mismatch
                    or direct_scope_mismatch
                ):
                    raise TraceValidationError("invalid process execution scope")
            elif scope.get("kind") == "anchor-only":
                if (
                    scope.get("anchor_event_id") != anchor_id
                    or any(
                        event_id != anchor_id and event_id not in view["highlighted_event_ids"]
                        for event_id in context_ids
                    )
                ):
                    raise TraceValidationError("invalid anchor-only execution scope")
            else:
                raise TraceValidationError("invalid view execution scope")
        reachable = {anchor_id}
        pending = [anchor_id]
        while pending:
            current = pending.pop()
            for neighbor in proven_neighbors[current] - reachable:
                reachable.add(neighbor)
                pending.append(neighbor)
        if set(view.get("highlighted_event_ids", [])) != reachable:
            raise TraceValidationError("highlighted chain must equal the anchor's proven graph")
        if not reachable.issubset(context_ids):
            raise TraceValidationError("highlighted chain must be visible in context")
    if len(view_anchor_ids) != len(set(view_anchor_ids)):
        raise TraceValidationError("view anchors must be unique")
    has_anchor_selection = (
        isinstance(trace.get("diagnostics"), dict)
        and "anchor_selection" in trace["diagnostics"]
    )
    if has_anchor_selection and set(view_anchor_ids) != set(trace["fault_candidates"]):
        raise TraceValidationError("every fault candidate must have exactly one view")
    if view_anchor_ids.count(trace["selected_anchor_id"]) != 1:
        raise TraceValidationError("exactly one view must match the selected anchor")

    selected_view = next(
        view for view in trace["views"] if view["anchor_id"] == trace["selected_anchor_id"]
    )
    if "component_chain" in trace:
        expected_component_chain = build_component_chain_summary(
            events,
            trace["relationships"],
            trace["selected_anchor_id"],
            selected_view["highlighted_event_ids"],
            selected_view.get("context_event_ids"),
        )
        if trace["component_chain"] != expected_component_chain:
            raise TraceValidationError(
                "component_chain does not match derivable selected-anchor evidence"
            )

    diagnostics = trace["diagnostics"]
    if not isinstance(diagnostics, dict) or not {
        "gaps",
        "event_count",
        "fault_candidate_count",
    }.issubset(diagnostics):
        raise TraceValidationError("diagnostics is missing required fields")
    invalid_diagnostics = (
        not isinstance(diagnostics["gaps"], list)
        or not all(isinstance(gap, str) for gap in diagnostics["gaps"])
        or len(diagnostics["gaps"]) != len(set(diagnostics["gaps"]))
        or type(diagnostics["event_count"]) is not int
        or type(diagnostics["fault_candidate_count"]) is not int
        or diagnostics["event_count"] != len(events)
        or diagnostics["fault_candidate_count"] != len(trace["fault_candidates"])
    )
    if invalid_diagnostics:
        raise TraceValidationError("invalid diagnostics")
    anchor_selection = diagnostics.get("anchor_selection")
    if anchor_selection is not None:
        if not isinstance(anchor_selection, dict):
            raise TraceValidationError("invalid anchor selection diagnostics")
        if anchor_request is None:
            (
                expected_domain_candidate_ids,
                expected_selected_anchor_id,
                expected_selection_reason,
            ) = _select_anchor(
                events,
                event_by_id,
                trace["fault_candidates"],
                clock_coordinates,
            )
            expected_status = (
                "ambiguous" if len(expected_domain_candidate_ids) > 1 else "selected"
            )
        else:
            expected_selected_anchor_id = _resolve_anchor_request(
                events, trace["evidence"], anchor_request
            )
            automatic_candidate_ids = [
                event_id
                for event_id in trace["fault_candidates"]
                if "fault_rule_id" in event_by_id[event_id]
            ]
            if automatic_candidate_ids:
                expected_domain_candidate_ids, _, _ = _select_anchor(
                    events,
                    event_by_id,
                    automatic_candidate_ids,
                    clock_coordinates,
                )
            else:
                expected_domain_candidate_ids = [expected_selected_anchor_id]
            expected_selection_reason = (
                "explicit_event_id"
                if anchor_request["selector"]["kind"] == "event_id"
                else "explicit_source_location"
            )
            expected_status = "selected"
        domain_candidate_ids = anchor_selection.get("domain_candidate_ids")
        if (
            anchor_selection.get("status") not in {"selected", "ambiguous"}
            or anchor_selection.get("reason")
            not in {
                "single_clock_domain",
                "aligned_clock_domains",
                "unaligned_clock_domains",
                "explicit_event_id",
                "explicit_source_location",
            }
            or not isinstance(domain_candidate_ids, list)
            or not all(isinstance(candidate_id, str) for candidate_id in domain_candidate_ids)
            or len(domain_candidate_ids) != len(set(domain_candidate_ids))
            or domain_candidate_ids != expected_domain_candidate_ids
            or trace["selected_anchor_id"] != expected_selected_anchor_id
            or anchor_selection["reason"] != expected_selection_reason
            or anchor_selection["status"] != expected_status
        ):
            raise TraceValidationError("invalid anchor selection diagnostics")
    conflict_gap_present = "clock_alignment_conflict" in diagnostics["gaps"]
    if conflict_gap_present != bool(clock_alignment_conflict_sources(events)):
        raise TraceValidationError("invalid clock alignment conflict diagnostic")
    host_device_present = {
        event["location"] for event in events
    }.issuperset({"host", "device"})
    clock_roots = {
        clock_coordinates[event["timestamp"]["clock_domain_id"]][0]
        for event in events
    }
    unaligned_gap_expected = host_device_present and len(clock_roots) > 1
    if (
        "unaligned_host_device_clocks" in diagnostics["gaps"]
    ) != unaligned_gap_expected:
        raise TraceValidationError("invalid Host/Device clock diagnostic")
    expected_gap_states = {
        "no_call_spans": not trace["spans"],
        "unmatched_span_endpoints": bool(
            unmatched_span_endpoint_ids(events, trace["spans"])
        ),
        "evidence_conflicts": bool(evidence_conflict_groups(events)),
    }
    if any(
        (gap in diagnostics["gaps"]) != expected
        for gap, expected in expected_gap_states.items()
    ):
        raise TraceValidationError("invalid span or evidence conflict diagnostic")
    if "excluded_event_count" in diagnostics:
        selected_view = next(
            view for view in trace["views"] if view["anchor_id"] == trace["selected_anchor_id"]
        )
        if (
            type(diagnostics["excluded_event_count"]) is not int
            or diagnostics["excluded_event_count"] < 0
            or diagnostics["excluded_event_count"]
            != len(selected_view.get("excluded_event_ids", []))
        ):
            raise TraceValidationError("invalid excluded_event_count")
    if "parse_coverage" in diagnostics:
        coverage = diagnostics["parse_coverage"]
        if (
            not isinstance(coverage, dict)
            or type(coverage.get("parsed_records")) is not int
            or type(coverage.get("unparsed_records")) is not int
            or coverage["parsed_records"] < 0
            or coverage["unparsed_records"] < 0
            or coverage["parsed_records"]
            != sum(int(item["parsed_records"]) for item in input_record["inventory"])
            or coverage["unparsed_records"]
            != sum(int(item["unparsed_records"]) for item in input_record["inventory"])
        ):
            raise TraceValidationError("invalid parse coverage")
    if "context_window" in diagnostics:
        selected_view = next(
            view for view in trace["views"] if view["anchor_id"] == trace["selected_anchor_id"]
        )
        selected_window = selected_view.get("context_window")
        if (
            diagnostics["context_window"] != selected_window
            or (
                "context_truncated" in diagnostics["gaps"]
            ) != bool(selected_window and selected_window["truncated"])
        ):
            raise TraceValidationError("invalid context window diagnostics")


VIEWER_PAGE_SIZE = 25
OVERVIEW_MAX_BINS = 120


def _viewer_clock_root(event: dict[str, Any]) -> str:
    timestamp = event["timestamp"]
    return timestamp.get("aligned_clock_domain_id", timestamp["clock_domain_id"])


def _viewer_coordinate_us(event: dict[str, Any]) -> int:
    timestamp = event["timestamp"]
    return timestamp.get("aligned_offset_us", timestamp["offset_us"])


def _format_relative_us(value: int) -> str:
    if abs(value) >= 1000:
        rendered = f"{value / 1000:+.3f}".rstrip("0").rstrip(".")
        return f"{rendered} ms"
    return f"{value:+d} us"


def _viewer_location_title(
    locations: list[str], domain_ids: list[str], domain_by_id: dict[str, dict[str, Any]]
) -> str:
    location_title = " + ".join(location.title() for location in locations)
    identities = [
        str(domain_by_id.get(domain_id, {}).get("kind", domain_id))
        for domain_id in domain_ids
    ]
    return f"{location_title} · {' / '.join(identities)}" if identities else location_title


def _viewer_device_evidence(trace: dict[str, Any], selected_anchor_id: str) -> tuple[str, str]:
    device_events = [event for event in trace["events"] if event["location"] == "device"]
    if not device_events:
        return "no-device-records", "No Device records were parsed; the Device timeline is unavailable."
    selected_view = next(view for view in trace["views"] if view["anchor_id"] == selected_anchor_id)
    event_by_id = {event["id"]: event for event in trace["events"]}
    device_chain = {
        event_id
        for event_id in selected_view["highlighted_event_ids"]
        if event_by_id.get(event_id, {}).get("location") == "device"
    }
    if not device_chain:
        aligned_sources = {
            item["source_clock_domain_id"] for item in trace.get("clock_alignments", [])
        }
        device_aligned = any(
            event["timestamp"]["clock_domain_id"] in aligned_sources for event in device_events
        )
        clock_note = "" if device_aligned else " independent clocks prevent cross-panel comparison."
        return (
            "device-records-unrelated" if device_aligned else "device-records-unaligned",
            f"Device records detected ({len(device_events)}), but no proven relation to the selected fault anchor.{clock_note}",
        )
    return "device-records-related", f"{len(device_chain)} Device record(s) are included in the proven chain."


def _tick_values(relative_values: list[int]) -> list[int]:
    if not relative_values:
        return [-10, -5, 0, 5, 10]
    low = min(relative_values)
    high = max(relative_values)
    if low == high:
        padding = max(10, abs(low) // 10)
        low -= padding
        high += padding
    raw_step = max(1, (high - low) / 5)
    magnitude = 10 ** max(0, len(str(int(raw_step))) - 1)
    step = magnitude
    for multiplier in (1, 2, 5, 10):
        candidate = multiplier * magnitude
        if candidate >= raw_step:
            step = candidate
            break
    start = (low // step) * step
    end = ((high + step - 1) // step) * step
    values = list(range(start, end + 1, step))
    if 0 not in values and low <= 0 <= high:
        values.append(0)
        values.sort()
    return values[:9]


def _event_details_markup(event: dict[str, Any], trace: dict[str, Any]) -> str:
    execution = event.get("execution", {})
    process = execution.get("process", "unknown")
    subject = f'{process} / PID {execution.get("pid", "unknown")}'
    evidence = "".join(
        f'<li><code>{html.escape(trace["evidence"][evidence_id]["source_path"])}:'
        f'{trace["evidence"][evidence_id]["line"]}</code> '
        f'{html.escape(trace["evidence"][evidence_id]["excerpt"])}</li>'
        for evidence_id in event["evidence_ids"]
    )
    return (
        f'<div class="details-heading"><span class="level {html.escape(event["level"].lower())}">'
        f'{html.escape(event["level"])}</span><strong>{html.escape(event["component"])}</strong>'
        f'<code>{html.escape(event["id"])}</code></div>'
        f'<dl><div><dt>Execution</dt><dd>{html.escape(subject)}</dd></div>'
        f'<div><dt>Clock</dt><dd>{html.escape(event["timestamp"]["clock_domain_id"])}</dd></div>'
        f'<div><dt>Raw time</dt><dd><code>{html.escape(event["timestamp"]["raw"])}</code></dd></div>'
        f'<div><dt>Message</dt><dd>{html.escape(event["message"])}</dd></div></dl>'
        f'<ul class="details-evidence">{evidence}</ul>'
    )


def _viewer_trace_projection(
    trace: dict[str, Any],
    *,
    max_embedded_events: int = 6000,
) -> dict[str, Any]:
    """Bound the events embedded into the offline viewer.

    The full package can hold hundreds of thousands of records; the viewer
    only needs the anchor, proven endpoints, fault-window errors, lifecycle
    representatives, and merged-card members.  Source counts are preserved
    in ``viewer_projection`` so the UI can report package density while
    embedding a bounded subset.
    """
    events = trace["events"]
    if len(events) <= max_embedded_events:
        host_count = sum(1 for event in events if event["location"] == "host")
        device_count = len(events) - host_count
        trace["viewer_projection"] = {
            "source_event_count": len(events),
            "source_host_event_count": host_count,
            "source_device_event_count": device_count,
            "embedded_event_count": len(events),
            "bounded": False,
            "default_key_process_event_ids": [],
        }
        return trace

    event_by_id = {event["id"]: event for event in events}
    anchor_id = trace["selected_anchor_id"]
    anchor = event_by_id[anchor_id]
    keep: dict[str, None] = {}

    def keep_event(event_id: str) -> None:
        if event_id in event_by_id:
            keep.setdefault(event_id, None)

    keep_event(anchor_id)
    for candidate_id in trace["fault_candidates"]:
        keep_event(candidate_id)
    for relationship in trace["relationships"]:
        if relationship.get("strength") == "proven":
            keep_event(relationship["source_event_id"])
            keep_event(relationship["target_event_id"])
    for card in trace.get("event_cards", []):
        for member_id in card.get("member_event_ids", []):
            keep_event(member_id)

    anchor_domain = anchor["timestamp"]["clock_domain_id"]
    anchor_offset = anchor["timestamp"]["offset_us"]
    error_window_us = 60_000_000
    for event in events:
        if (
            event["timestamp"]["clock_domain_id"] == anchor_domain
            and event["level"].upper() in {"ERROR", "FATAL"}
            and abs(event["timestamp"]["offset_us"] - anchor_offset) <= error_window_us
        ):
            keep_event(event["id"])

    lanes: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in events:
        lanes.setdefault(
            (event["timestamp"]["clock_domain_id"], event["component"]), []
        ).append(event)
    for lane_events in lanes.values():
        lane_events.sort(key=lambda event: event["timestamp"]["offset_us"])
        keep_event(lane_events[0]["id"])
        keep_event(lane_events[-1]["id"])
        info_events = [
            event for event in lane_events if event["level"].upper() == "INFO"
        ]
        for index in range(0, len(info_events), max(1, len(info_events) // 3)):
            keep_event(info_events[index]["id"])

    if len(keep) > max_embedded_events:
        ordered = list(keep.keys())[:max_embedded_events]
        keep = {key: None for key in ordered}
    keep_event(anchor_id)

    embedded_ids = set(keep)
    embedded_events = [event for event in events if event["id"] in embedded_ids]

    def filter_ids(ids: list[str]) -> list[str]:
        return [item for item in ids if item in embedded_ids]

    embedded_relationships = [
        relationship
        for relationship in trace["relationships"]
        if relationship["source_event_id"] in embedded_ids
        and relationship["target_event_id"] in embedded_ids
    ]
    embedded_cards = [
        card
        for card in trace.get("event_cards", [])
        if any(member_id in embedded_ids for member_id in card.get("member_event_ids", []))
    ]
    referenced_evidence: set[str] = set()
    for event in embedded_events:
        referenced_evidence.update(event.get("evidence_ids", []))
    for relationship in embedded_relationships:
        referenced_evidence.update(relationship.get("evidence_ids", []))
    embedded_evidence = {
        evidence_id: trace["evidence"][evidence_id]
        for evidence_id in referenced_evidence
        if evidence_id in trace["evidence"]
    }
    embedded_views = []
    for view in trace["views"]:
        embedded_view = dict(view)
        embedded_view["highlighted_event_ids"] = filter_ids(view["highlighted_event_ids"])
        embedded_view["context_event_ids"] = filter_ids(view["context_event_ids"])
        embedded_views.append(embedded_view)
    embedded_context_partitions = {
        partition_id: {
            **partition,
            "event_ids": filter_ids(partition.get("event_ids", [])),
        }
        for partition_id, partition in trace.get("context_partitions", {}).items()
    }
    if "component_chain" in trace:
        chain = trace["component_chain"]
        for node in chain.get("nodes", []):
            node["member_event_ids"] = filter_ids(node.get("member_event_ids", []))
            node["evidence_ids"] = [
                evidence_id
                for evidence_id in node.get("evidence_ids", [])
                if evidence_id in embedded_evidence
            ]
        chain["execution_event_ids"] = filter_ids(chain.get("execution_event_ids", []))
        chain["edges"] = [
            {
                **edge,
                "event_relationship_ids": [
                    relationship_id
                    for relationship_id in edge.get("event_relationship_ids", [])
                    if relationship_id
                    in {relationship["id"] for relationship in embedded_relationships}
                ],
                "evidence_ids": [
                    evidence_id
                    for evidence_id in edge.get("evidence_ids", [])
                    if evidence_id in embedded_evidence
                ],
            }
            for edge in chain.get("edges", [])
        ]
        # After projection, representative events may no longer be embedded.
        # Keep nodes with embedded members; re-point representatives to the first member.
        chain["nodes"] = [
            {
                **node,
                "representative_event_id": node["member_event_ids"][0]
                if node.get("member_event_ids")
                and node.get("representative_event_id") not in node["member_event_ids"]
                else node.get("representative_event_id"),
                "deep_link": {
                    **node.get("deep_link", {}),
                    "event": node["member_event_ids"][0]
                    if node.get("member_event_ids")
                    and node.get("deep_link", {}).get("event")
                    not in node["member_event_ids"]
                    else node.get("deep_link", {}).get("event"),
                },
            }
            for node in chain.get("nodes", [])
            if node.get("member_event_ids")
        ]

    host_count = sum(1 for event in events if event["location"] == "host")
    device_count = len(events) - host_count
    trace["events"] = embedded_events
    trace["relationships"] = embedded_relationships
    trace["event_cards"] = embedded_cards
    trace["evidence"] = embedded_evidence
    trace["views"] = embedded_views
    trace["context_partitions"] = embedded_context_partitions
    trace["spans"] = [
        span
        for span in trace["spans"]
        if span["start_event_id"] in embedded_ids and span["end_event_id"] in embedded_ids
    ]
    trace["viewer_projection"] = {
        "source_event_count": len(events),
        "source_host_event_count": host_count,
        "source_device_event_count": device_count,
        "embedded_event_count": len(embedded_events),
        "bounded": True,
        "default_key_process_event_ids": [],
    }
    return trace


def render_html(trace: dict[str, Any]) -> str:
    validate_trace(trace)
    trace = _viewer_trace_projection(trace)
    template_path = Path(__file__).resolve().parents[2] / "assets" / "fault-trace-template.html"
    template = template_path.read_text(encoding="utf-8")
    selected_anchor_id = trace["selected_anchor_id"]
    selected_view = next(view for view in trace["views"] if view["anchor_id"] == selected_anchor_id)
    highlighted_ids = set(selected_view["highlighted_event_ids"])
    event_by_id = {event["id"]: event for event in trace["events"]}

    panel_events: dict[str, list[dict[str, Any]]] = {}
    for event in trace["events"]:
        panel_events.setdefault(_viewer_clock_root(event), []).append(event)
    panel_roots = sorted(
        panel_events,
        key=lambda root: (
            not any(event["location"] == "host" for event in panel_events[root]),
            root,
        ),
    )
    panel_reference: dict[str, int] = {}
    candidate_set = set(trace["fault_candidates"])
    for root in panel_roots:
        events = panel_events[root]
        reference_event = next(
            (event for event in events if event["id"] == selected_anchor_id),
            next((event for event in events if event["id"] in candidate_set), events[0]),
        )
        panel_reference[root] = _viewer_coordinate_us(reference_event)

    display_origin = {
        root: min(_viewer_coordinate_us(event) for event in events)
        for root, events in panel_events.items()
    }
    display_offset_by_event = {
        event["id"]: _viewer_coordinate_us(event) - display_origin[_viewer_clock_root(event)]
        for event in trace["events"]
    }

    alignment_by_source = {
        item["source_clock_domain_id"]: item for item in trace.get("clock_alignments", [])
    }
    domain_by_id = {domain["id"]: domain for domain in trace["clock_domains"]}
    panels_markup: list[str] = []
    overview_markup: list[str] = []
    for root in panel_roots:
        all_panel_events = panel_events[root]
        visible_events = [event for event in all_panel_events if event["id"] in highlighted_ids]
        locations = sorted({event["location"] for event in all_panel_events})
        location_attr = " ".join(locations)
        domain_ids = sorted({event["timestamp"]["clock_domain_id"] for event in all_panel_events})
        location_title = _viewer_location_title(locations, domain_ids, domain_by_id)
        alignment_notes = []
        for domain_id in domain_ids:
            record = alignment_by_source.get(domain_id)
            if record:
                alignment_notes.append(
                    f'{record["method"]}: offset {record["offset_us"]:+d} us, '
                    f'uncertainty {record["uncertainty_us"]} us'
                )
        aligned = len(domain_ids) > 1
        clock_status = "; ".join(alignment_notes) if alignment_notes else "unaligned; independent axis"
        reference_label = (
            "selected fault anchor"
            if any(event["id"] == selected_anchor_id for event in all_panel_events)
            else "local fault reference; not comparable across panels"
        )
        relative_values = [
            _viewer_coordinate_us(event) - panel_reference[root] for event in visible_events
        ]
        tick_values = _tick_values(relative_values)
        panel_min = min(tick_values)
        panel_max = max(tick_values)
        pixel_scale = min(8.0, max(0.00005, 720 / max(1, panel_max - panel_min)))
        tick_markup = "".join(
            f'<span class="time-tick" data-relative-us="{value}" '
            f'style="--tick-position:{100 * (value - panel_min) / max(1, panel_max - panel_min):.4f}%">'
            f'<span class="tick-label">{html.escape(_format_relative_us(value))}</span></span>'
            for value in tick_values
        )

        lanes: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for event in visible_events:
            execution = event.get("execution", {})
            process = str(execution.get("process", "unknown"))
            pid = str(execution.get("pid", "unknown"))
            key = (
                event["timestamp"]["clock_domain_id"],
                event["component"],
                process,
                pid,
            )
            lanes.setdefault(key, []).append(event)
        lane_markup: list[str] = []
        lane_id_by_event: dict[str, str] = {}
        for lane_index, (lane_key, lane_events) in enumerate(sorted(lanes.items()), start=1):
            domain_id, component, process, pid = lane_key
            lane_id = f"lane-{html.escape(root)}-{lane_index}"
            for event in lane_events:
                lane_id_by_event[event["id"]] = lane_id
            event_markup = []
            for event in lane_events:
                relative_us = _viewer_coordinate_us(event) - panel_reference[root]
                x_px = 90 + (relative_us - panel_min) * pixel_scale
                classes = "event event-point highlighted"
                anchor_markup = ""
                if event["id"] == selected_anchor_id:
                    classes += " anchor selected"
                    anchor_markup = '<span class="anchor-label">Fault anchor</span>'
                event_markup.append(
                    f'<button class="{classes}" data-lane-id="{lane_id}" '
                    f'data-event-id="{html.escape(event["id"])}" '
                    f'data-offset-us="{display_offset_by_event[event["id"]]}" '
                    f'data-relative-us="{relative_us}" style="--event-x-px:{x_px:.3f}px" '
                    f'aria-label="{html.escape(event["component"])} {_format_relative_us(relative_us)}" '
                    f'title="{html.escape(event["message"])}">'
                    f'<span class="event-glyph"></span><span class="event-label">'
                    f'<span class="event-time">{html.escape(_format_relative_us(relative_us))}</span>'
                    f'{anchor_markup}'
                    f'<span>{html.escape(event["component"])}</span></span></button>'
                )
            domain_kind = domain_by_id[domain_id]["kind"]
            lane_markup.append(
                f'<div class="trace-lane" data-component="{html.escape(component)}" '
                f'data-process="{html.escape(process)}" data-clock-domain-id="{html.escape(domain_id)}">'
                f'<div class="lane-label"><strong>{html.escape(component)}</strong>'
                f'<span>{html.escape(process)} / PID {html.escape(pid)}</span>'
                f'<small>{html.escape(domain_kind)}</small></div>'
                f'<div class="lane-track">{"".join(event_markup)}</div></div>'
            )
        empty_markup = ""
        if not lane_markup:
            panel_state = "no-proven-events"
            if "device" in locations:
                panel_state = "device-records-unaligned" if not alignment_notes else "device-records-unrelated"
            panel_text = (
                f"Device records present ({len(all_panel_events)}), but no proven relation to the selected fault anchor."
                if panel_state == "device-records-unrelated"
                else "No events in the proven chain for this clock domain."
            )
            empty_markup = (
                f'<p class="panel-empty" data-evidence-state="{panel_state}">'
                f'{html.escape(panel_text)}</p>'
            )
        panels_markup.append(
            f'<section class="clock-panel" data-clock-root-id="{html.escape(root)}" '
            f'data-location="{html.escape(location_attr)}" data-aligned="{str(aligned).lower()}">'
            f'<header class="panel-header"><div><h3>{html.escape(location_title)} timeline</h3>'
            f'<p>{html.escape(root)}</p></div><div class="clock-badges">'
            f'<span>{html.escape(clock_status)}</span><span>{html.escape(reference_label)}</span></div></header>'
            f'<div class="panel-viewport"><div class="panel-canvas" '
            f'style="--panel-width:{max(900, int((panel_max - panel_min) * pixel_scale + 180))}px">'
            f'<div class="time-axis"><div class="axis-label">Relative time</div>'
            f'<div class="axis-track">{tick_markup}</div></div>{empty_markup}{"".join(lane_markup)}'
            f'<svg class="connector-layer" aria-label="Directed component relationships"></svg>'
            f'</div></div></section>'
        )

        coordinates = [_viewer_coordinate_us(event) for event in all_panel_events]
        minimum = min(coordinates)
        span = max(1, max(coordinates) - minimum)
        occupied: dict[int, int] = {}
        for coordinate in coordinates:
            bin_index = min(
                OVERVIEW_MAX_BINS - 1,
                int((coordinate - minimum) * OVERVIEW_MAX_BINS / (span + 1)),
            )
            occupied[bin_index] = occupied.get(bin_index, 0) + 1
        bins = "".join(
            f'<span class="overview-bin" data-count="{count}" '
            f'style="--bin-position:{100 * index / OVERVIEW_MAX_BINS:.4f}%;'
            f'--bin-height:{min(100, 18 + count * 4)}%" title="{count} events"></span>'
            for index, count in occupied.items()
        )
        anchor_in_panel = next(
            (event for event in all_panel_events if event["id"] == selected_anchor_id), None
        )
        marker = ""
        if anchor_in_panel is not None:
            anchor_position = 100 * (
                _viewer_coordinate_us(anchor_in_panel) - minimum
            ) / span
            marker = (
                f'<span class="overview-anchor" style="--anchor-position:{anchor_position:.4f}%" '
                f'title="Selected fault anchor"></span>'
            )
        overview_markup.append(
            f'<div class="overview-panel" data-clock-root-id="{html.escape(root)}">'
            f'<span class="overview-label">{html.escape(location_title)}</span>'
            f'<div class="overview-track">{bins}{marker}</div></div>'
        )

    relationship_markup = []
    for relationship in trace["relationships"][:VIEWER_PAGE_SIZE]:
        strength = relationship["strength"]
        source_id = relationship["source_event_id"]
        target_id = relationship["target_event_id"]
        hidden = "" if (
            strength != "inferred"
            and source_id in highlighted_ids
            and target_id in highlighted_ids
        ) else " hidden"
        relationship_markup.append(
            f'<tr class="relationship {html.escape(strength)}" data-strength="{html.escape(strength)}" '
            f'data-source-event-id="{html.escape(source_id)}" '
            f'data-target-event-id="{html.escape(target_id)}"{hidden}>'
            f'<td>{html.escape(strength)}</td><td>{html.escape(relationship.get("kind", "unspecified"))}</td>'
            f'<td>{html.escape(source_id)}</td><td>{html.escape(target_id)}</td>'
            f'<td>{html.escape(relationship.get("rule_id", ""))}</td></tr>'
        )

    connector_markup = []
    for relationship in trace["relationships"][:VIEWER_PAGE_SIZE]:
        strength = relationship["strength"]
        source_id = relationship["source_event_id"]
        target_id = relationship["target_event_id"]
        hidden = "" if (
            strength != "inferred"
            and source_id in highlighted_ids
            and target_id in highlighted_ids
            and _viewer_clock_root(event_by_id[source_id]) == _viewer_clock_root(event_by_id[target_id])
        ) else " hidden"
        connector_markup.append(
            f'<path class="connector {html.escape(strength)}" data-strength="{html.escape(strength)}" '
            f'data-relationship-id="{html.escape(relationship["id"])}" '
            f'data-source-event-id="{html.escape(source_id)}" '
            f'data-target-event-id="{html.escape(target_id)}" d="M 0 0"{hidden}></path>'
        )

    span_seed_markup = "".join(
        f'<button class="span" data-span-id="{html.escape(span["id"])}" '
        f'data-start-event-id="{html.escape(span["start_event_id"])}" '
        f'data-end-event-id="{html.escape(span["end_event_id"])}" '
        f'data-duration-us="{span["duration_us"]}" hidden></button>'
        for span in trace["spans"][:VIEWER_PAGE_SIZE]
    )

    evidence_markup = []
    for event in (event_by_id[event_id] for event_id in selected_view["highlighted_event_ids"]):
        for evidence_id in event["evidence_ids"]:
            if len(evidence_markup) >= VIEWER_PAGE_SIZE:
                break
            evidence = trace["evidence"][evidence_id]
            evidence_markup.append(
                f'<tr class="evidence-row" data-event-id="{html.escape(event["id"])}" '
                f'data-evidence-id="{html.escape(evidence_id)}" data-line="{evidence["line"]}">'
                f'<td>{html.escape(event["id"])}</td><td>{html.escape(evidence["source_path"])}</td>'
                f'<td>{evidence["line"]}</td><td><code>{html.escape(evidence["record_sha256"])}</code></td>'
                f'<td>{html.escape(evidence["excerpt"])}</td></tr>'
            )

    inventory_markup = "".join(
        f'<tr><td>{html.escape(item["source_path"])}</td><td>{html.escape(item["status"])}</td>'
        f'<td>{html.escape(str(item.get("reason", "")))}</td>'
        f'<td>{item["parsed_records"]}</td><td>{item["unparsed_records"]}</td></tr>'
        for item in trace["input"]["inventory"]
    )
    json_text = json.dumps(trace, ensure_ascii=True, separators=(",", ":"))
    json_text = json_text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    device_evidence_state, device_evidence_summary = _viewer_device_evidence(
        trace, selected_anchor_id
    )
    return (
        template.replace("{{TRACE_JSON}}", json_text)
        .replace(
            "{{CANDIDATE_OPTIONS}}",
            "".join(
                f'<option value="{html.escape(candidate_id)}"'
                f'{" selected" if candidate_id == selected_anchor_id else ""}>'
                f'{html.escape(candidate_id)}</option>'
                for candidate_id in trace["fault_candidates"]
            ),
        )
        .replace("{{CLOCK_PANELS}}", "\n".join(panels_markup))
        .replace("{{OVERVIEW_PANELS}}", "\n".join(overview_markup))
        .replace("{{CONNECTOR_SEED}}", "\n".join(connector_markup))
        .replace("{{SPAN_SEED}}", span_seed_markup)
        .replace("{{RELATIONSHIP_ROWS}}", "\n".join(relationship_markup))
        .replace("{{EVIDENCE_ROWS}}", "\n".join(evidence_markup))
        .replace("{{INVENTORY_ROWS}}", inventory_markup)
        .replace("{{INITIAL_DETAILS}}", _event_details_markup(event_by_id[selected_anchor_id], trace))
        .replace("{{SELECTED_ANCHOR}}", html.escape(selected_anchor_id))
        .replace(
            "{{TRACE_STATUS_LABEL}}",
            "部分结果" if trace["status"] == "partial" else "完整结果",
        )
        .replace("{{TRACE_STATUS}}", html.escape(trace["status"]))
        .replace("{{EVENT_COUNT}}", str(len(trace["events"])))
        .replace("{{CHAIN_COUNT}}", str(len(highlighted_ids)))
        .replace("{{PROVEN_COUNT}}", str(sum(item["strength"] == "proven" for item in trace["relationships"])))
        .replace("{{CLOCK_COUNT}}", str(len(panel_roots)))
        .replace(
            "{{SCOPE_SUMMARY}}",
            f'{_scope_summary(selected_view)}; '
            f'{len(selected_view.get("excluded_event_ids", []))} events excluded',
        )
        .replace("{{DEVICE_EVIDENCE_STATE}}", device_evidence_state)
        .replace("{{DEVICE_EVIDENCE_SUMMARY}}", html.escape(device_evidence_summary))
    )


def _scope_summary(view: dict[str, Any]) -> str:
    scope = view.get("scope", {})
    if scope.get("kind") == "process":
        summary = f'PID {html.escape(str(scope.get("pid", "unknown")))}'
    else:
        summary = "Anchor-only scope"
    window = view.get("context_window")
    if window is None:
        return summary
    requested = window["requested"]
    return (
        f'{summary}; window -{requested["before_us"]}/+{requested["after_us"]} us; '
        f'{window["excluded_outside_window_count"]} outside window; '
        f'{window["excluded_by_limit_count"]} over event limit'
    )


def _view_context_event_ids(
    trace: dict[str, Any], view: dict[str, Any]
) -> list[str]:
    if "context_event_ids" in view:
        return view["context_event_ids"]
    partition_ids = trace["context_partitions"][view["context_partition_id"]]["event_ids"]
    context = set(partition_ids).union(view["highlighted_event_ids"])
    return [event["id"] for event in trace["events"] if event["id"] in context]


class NoUsableTraceError(ValueError):
    """Raised when the input cannot support a fault-centered view."""

    def __init__(self, message: str, audit: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.audit = audit


class TraceValidationError(ValueError):
    """Raised when a generated trace violates the runtime contract."""


def _inventory_audit(
    input_path: Path,
    inventory: list[dict[str, object]],
    redaction_scope_id: str,
    pseudonymizer: Pseudonymizer,
    additional_redaction_patterns: dict[str, str] | None,
) -> dict[str, Any]:
    audit = {
        "artifact_kind": "fault-trace-inventory",
        "inventory_schema_version": INVENTORY_SCHEMA_VERSION,
        "status": "no_trace",
        "metadata": {
            "generator_version": GENERATOR_VERSION,
            "redaction_scope": {
                "kind": "package-local",
                "scope_id": redaction_scope_id,
            },
        },
        "input": {
            "boundary": pseudonymizer.redact(input_path.name),
            "inventory": _redact_inventory(inventory, pseudonymizer),
        },
    }
    if additional_redaction_patterns:
        audit["metadata"]["redaction_rules"] = {
            "builtin_profile": "cann-trace-default-v1",
            "additional_pattern_names": sorted(additional_redaction_patterns),
            "source": "caller",
        }
    validate_inventory_audit(audit)
    return audit


def validate_inventory_audit(audit: dict[str, Any]) -> None:
    required = {
        "artifact_kind",
        "inventory_schema_version",
        "status",
        "metadata",
        "input",
    }
    if not isinstance(audit, dict) or not required.issubset(audit):
        raise TraceValidationError("inventory audit is missing required fields")
    if (
        audit["artifact_kind"] != "fault-trace-inventory"
        or audit["inventory_schema_version"] != INVENTORY_SCHEMA_VERSION
        or audit["status"] != "no_trace"
    ):
        raise TraceValidationError("invalid inventory audit identity")
    metadata = audit["metadata"]
    if not isinstance(metadata, dict) or not {"generator_version", "redaction_scope"}.issubset(metadata):
        raise TraceValidationError("inventory audit metadata is missing required fields")
    if not isinstance(metadata["generator_version"], str):
        raise TraceValidationError("inventory audit generator_version must be a string")
    scope = metadata["redaction_scope"]
    if (
        not isinstance(scope, dict)
        or scope.get("kind") != "package-local"
        or not isinstance(scope.get("scope_id"), str)
        or re.fullmatch(r"[0-9a-f]{16}", scope["scope_id"]) is None
    ):
        raise TraceValidationError("invalid inventory audit redaction scope")
    input_record = audit["input"]
    if not isinstance(input_record, dict) or not {"boundary", "inventory"}.issubset(input_record):
        raise TraceValidationError("inventory audit input is missing required fields")
    if not isinstance(input_record["boundary"], str) or not isinstance(input_record["inventory"], list):
        raise TraceValidationError("invalid inventory audit input")
    for entry in input_record["inventory"]:
        if not isinstance(entry, dict) or not {
            "source_path",
            "status",
            "parsed_records",
            "unparsed_records",
        }.issubset(entry):
            raise TraceValidationError("inventory audit entry is missing required fields")
        if (
            not isinstance(entry["source_path"], str)
            or entry["status"] not in {"parsed", "unsupported", "unreadable", "rejected", "archive"}
            or type(entry["parsed_records"]) is not int
            or type(entry["unparsed_records"]) is not int
            or entry["parsed_records"] < 0
            or entry["unparsed_records"] < 0
        ):
            raise TraceValidationError("invalid inventory audit entry")
        if "content_sha256" in entry and (
            not isinstance(entry["content_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", entry["content_sha256"]) is None
        ):
            raise TraceValidationError("invalid inventory audit content hash")
        if "parser" in entry and entry["parser"] is not None and not isinstance(entry["parser"], str):
            raise TraceValidationError("inventory audit parser must be a string or null")
        if "reason" in entry and not isinstance(entry["reason"], str):
            raise TraceValidationError("inventory audit reason must be a string")
        if "size_bytes" in entry and (
            type(entry["size_bytes"]) is not int or entry["size_bytes"] < 0
        ):
            raise TraceValidationError("inventory audit size_bytes must be non-negative")
