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

"""Normalize duplicate observations without losing provenance."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_EVENT_SEMANTIC_FIELDS = (
    "kind",
    "level",
    "component",
    "raw_component",
    "component_mapping_rule",
    "fault_rule_id",
    "message",
    "execution",
    "correlation",
    "interaction",
    "clock_alignment",
)


def merge_exact_duplicate_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    event_by_fingerprint: dict[tuple[Any, ...], dict[str, Any]] = {}
    for event in events:
        fingerprint = semantic_event_fingerprint(event)
        existing = event_by_fingerprint.get(fingerprint)
        if existing is None:
            retained = deepcopy(event)
            event_by_fingerprint[fingerprint] = retained
            merged.append(retained)
            continue
        _extend_unique(existing["evidence_ids"], event["evidence_ids"])
        existing_device = existing.get("execution", {}).get("device", {})
        event_device = event.get("execution", {}).get("device", {})
        for field in ("mapping_evidence_ids", "conflict_evidence_ids"):
            if field in event_device:
                _extend_unique(existing_device[field], event_device[field])
    return merged


def semantic_event_fingerprint(event: dict[str, Any]) -> tuple[Any, ...]:
    timestamp = event["timestamp"]
    exact_timestamp = (
        timestamp["clock_domain_id"],
        timestamp["offset_us"],
        timestamp.get("monotonic_raw"),
    )
    semantic_fields = tuple(
        (field, _freeze(_without_evidence_references(event.get(field))))
        for field in _EVENT_SEMANTIC_FIELDS
        if field in event
    )
    return _freeze(exact_timestamp), semantic_fields


def _without_evidence_references(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_evidence_references(item)
            for key, item in value.items()
            if not key.endswith("_evidence_ids")
        }
    if isinstance(value, list):
        return [_without_evidence_references(item) for item in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _extend_unique(target: list[str], additions: list[str]) -> None:
    for item in additions:
        if item not in target:
            target.append(item)
