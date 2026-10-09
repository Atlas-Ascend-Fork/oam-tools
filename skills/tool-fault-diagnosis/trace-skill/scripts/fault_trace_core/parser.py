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

"""Versioned parsers for supported CANN Host log records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re
from typing import Callable

from .package_reader import ReaderLimits, read_package


HOST_CLOCK_DOMAIN_ID = "clock-host-wall-unknown-zone"
PARSER_VERSIONS = {
    "cann-stackcore-trace": "1.0.0",
    "device-common-slog": "1.1.0",
    "host-common-plog": "2.1.0",
    "host-kernel": "1.1.0",
}

_PLOG_RECORD = re.compile(
    r"^\[(?P<level>[A-Za-z]+)\]\s+"
    r"(?P<module>[^()]+)\((?P<pid>\d+),(?P<process>[^)]*)\):"
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}\.\d{3}(?:\.?\d{3}))\s+"
    r"\[(?P<source_file>[^:\]]+):(?P<source_line>\d+)\]"
    r"(?P<context>(?:\[[^\]]+\]|\([^)]*\))*)"
    r"(?P<message>.*)$"
)

_KERNEL_RECORD = re.compile(
    r"^\[(?P<timestamp>\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}\.\d{6})\]\s+"
    r"\[(?P<monotonic>\d+\.\d{6})\]\s+"
    r"\[(?P<subsystem>[^\]]+)\]\s+\[(?P<module>[^\]]+)\]\s+"
    r"\[(?P<level>[A-Za-z]+)\]\s+"
    r"\[(?P<source_file>\S+)\s+(?P<source_line>\d+)\]\s+"
    r"<(?P<subject>[^>]+)>\s*(?P<message>.*)$"
)

_COMPONENTS = {
    "RUNTIME": "Runtime",
    "ACL": "AscendCL",
    "ASCENDCL": "AscendCL",
    "GE": "GE",
    "HCCL": "HCCL",
    "DRV": "Driver",
    "IDEDD": "Data Dump",
    "OP": "Operator",
    "ATRACE": "Trace",
    "TDT": "TDT",
    # Graph-compile pipeline components: TUNE (autotuning knowledge base),
    # TEFUSION (graph fusion), and FE (graph engine front end) participate in
    # operator compilation faults and must not be lumped into "Unclassified".
    "TUNE": "TUNE",
    "TEFUSION": "TEFusion",
    "FE": "GE",
}

_KERNEL_DRIVER_MODULES = {
    "devdrv",
    "drv",
    "hdcdrv",
}

_FAULT_RULES = tuple(
    (rule_id, re.compile(pattern, re.IGNORECASE))
    for rule_id, pattern in (
        (
            "signal-fatal",
            r"(?:\b(?:caught|received|raised|handled?)\s+SIG(?:ABRT|SEGV|BUS|ILL|FPE)\b|"
            r"\bsignal\s*:\s*SIG(?:ABRT|SEGV|BUS|ILL|FPE)\b|"
            r"^\s*SIG(?:ABRT|SEGV|BUS|ILL|FPE)\s*[.!]?\s*$)",
        ),
        ("process-abort", r"\babort(?:ed|ing)?\b"),
        ("process-crash", r"\bcrash(?:ed|ing)?\b"),
        ("panic", r"\bpanic\b"),
        (
            "out-of-memory",
            r"(?:\bout of memory\b|\boom\s+(?:while|when|killer|killed|failure|error|occurred)\b|"
            r"^\s*OOM\s*[.!]?\s*$)",
        ),
        ("device-reset", r"\b(?:(?:device|chip|npu|system|board)\s+reset|reset(?:ting|ted))\b"),
        ("process-termination", r"\bprocess termination\b"),
        ("uncorrectable-exception", r"\buncorrectable(?:\s+\w+){0,2}\s+exception\b"),
    )
)
_NEGATED_FAULT = re.compile(
    r"\b(?:no|not|without)\s+(?:\w+\s+){0,3}"
    r"(?:crash|panic|abort|oom|reset|exception|termination|SIG(?:ABRT|SEGV|BUS|ILL|FPE))\b",
    re.IGNORECASE,
)
_BENIGN_FAULT_CONTEXT = re.compile(
    r"(?:\bcheck\s+oom\s+reserved\s+mem\b|"
    r"\boom\s+(?:killer\s+)?(?:disabled|initialized|enabled|configured)\b|"
    r"\boom\s+(?:monitor|threshold|handler|handling|check)\b|"
    r"\bout of memory\s+(?:monitor|threshold|handler|handling|check)\b)",
    re.IGNORECASE,
)
_TID = re.compile(r"(?:\[|\()tid:(?P<tid>\d+)(?:\]|\))", re.IGNORECASE)
_DEVICE_MAPPING = re.compile(
    r"local\s+device\s+id\s*=\s*(?P<logical>\d+).*?"
    r"physical\s+device\s+id\s*=\s*(?P<physical>\d+)",
    re.IGNORECASE,
)
_DEVICE_BOOT_TIME = re.compile(r"\[\s*(?P<seconds>\d+\.\d{6})\s*\]")
_PHYSICAL_DEVICE_PATH = re.compile(r"(?:^|/)(?:dev-os|device)-(?P<physical>\d+)(?:/|$)")
_STACKCORE_TIMESTAMP = re.compile(r"_(?P<timestamp>\d{20})\.txt$")
_CORRELATION_FIELD = re.compile(
    r"\b(?P<key>stream_id|task_id|event_id|node_id|assertion|alarm_raised_time|"
    r"device_id|dev_id)\s*=\s*(?P<value>0x[0-9a-f]+|\d+)",
    re.IGNORECASE,
)
_INTERACTION_RULES = (
    # HCCL error-propagation records: the originating timeout and every
    # explicit call-trace frame that received the propagated error.
    (
        "error-source",
        re.compile(r"\[BatchConnectChannels\]\s+channel connect timeout", re.IGNORECASE),
    ),
    (
        "error-propagation",
        re.compile(r"call trace:\s*hcclRet\s*->", re.IGNORECASE),
    ),
    ("notify-host", re.compile(r"\bsent\s+to\s+(?:the\s+)?host\b", re.IGNORECASE)),
    ("receive-device-event", re.compile(r"\breceive\s+an\s+event\b", re.IGNORECASE)),
    (
        "dispatch",
        re.compile(
            r"\b(?:dispatch|launch)\b|\bstreamlaunchkernelv2\b|"
            r"\balloctaskandsendstars\b|"
            r"\bconstructsqefor\w*task\b.*\bsend\b|\bsend\b.*\btask\b",
            re.IGNORECASE,
        ),
    ),
    (
        "return",
        re.compile(r"\b(?:return(?:ed)?|complete(?:d)?|recycl(?:e|ed))\b", re.IGNORECASE),
    ),
)
_FAILED_INTERACTION = re.compile(
    r"\b(?:fail(?:ed)?|failure|unsuccessful|unable)\b|"
    r"\b(?:did|does|was|is|has|have)\s+not\b|"
    r"\bnot\s+(?:sent|received|dispatched|launched|returned|completed|recycled)\b",
    re.IGNORECASE,
)
_CLOCK_ALIGNMENT = re.compile(
    r"\bclock_alignment\s+target=(?P<target>clock-[A-Za-z0-9._-]+)\s+"
    r"offset_us=(?P<offset>[+-]?\d+)\s+uncertainty_us=(?P<uncertainty>\d+)\s+"
    r"method=(?P<method>[A-Za-z][A-Za-z0-9._-]*)\b"
)


@dataclass(frozen=True)
class ParsedRecord:
    level: str
    raw_module: str
    component: str
    component_mapping_rule: str
    pid: str | None
    tid: str | None
    process: str
    raw_timestamp: str
    timestamp_us: int
    clock_domain_id: str
    clock_kind: str
    monotonic_raw: str | None
    message: str
    source_path: str
    line: int
    record_sha256: str
    excerpt: str
    parser_name: str
    parser_version: str
    fault_rule_id: str | None
    is_fault_candidate: bool
    location: str
    device_logical_id: str | None
    device_physical_id: str | None
    device_mapping_explicit: bool
    device_path_physical_id: str | None = None
    device_reported_physical_id: str | None = None
    device_identity_conflict: bool = False
    correlation: tuple[tuple[str, str], ...] = ()
    interaction: str | None = None
    clock_alignment: tuple[str, int, int, str] | None = None
    additional_evidence: tuple[tuple[int, str, str], ...] = ()


@dataclass(frozen=True)
class OrphanRecord:
    source_path: str
    line: int
    record_sha256: str
    excerpt: str


@dataclass(frozen=True)
class _Adapter:
    name: str
    inventory_id: str
    version: str
    pattern: re.Pattern[str]
    parse: Callable[[str, str, int], ParsedRecord | None]


def parse_cann_record(line: str, source_path: str, line_number: int) -> ParsedRecord | None:
    """Backward-compatible entry point for the common Host plog adapter."""
    match = _PLOG_RECORD.match(line)
    if match is None:
        return None
    fields = match.groupdict()
    timestamp_us = _parse_wall_timestamp(fields["timestamp"])
    if timestamp_us is None:
        return None
    raw_module = fields["module"].strip()
    level = fields["level"].upper()
    message = fields["message"].strip()
    tid_match = _TID.search(fields["context"])
    fault_rule_id = _fault_rule(level, message)
    return ParsedRecord(
        level=level,
        raw_module=raw_module,
        component=_COMPONENTS.get(raw_module.upper(), "Unclassified"),
        component_mapping_rule=(
            f"builtin-host-v1:{raw_module.upper()}"
            if raw_module.upper() in _COMPONENTS
            else "unclassified-host-v1"
        ),
        pid=fields["pid"],
        tid=tid_match.group("tid") if tid_match else None,
        process=fields["process"].strip(),
        raw_timestamp=fields["timestamp"],
        timestamp_us=timestamp_us,
        clock_domain_id=HOST_CLOCK_DOMAIN_ID,
        clock_kind="host-wall-unknown-zone",
        monotonic_raw=None,
        message=message,
        source_path=source_path,
        line=line_number,
        record_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
        excerpt=line,
        parser_name="host-common-plog",
        parser_version=PARSER_VERSIONS["host-common-plog"],
        fault_rule_id=fault_rule_id,
        is_fault_candidate=fault_rule_id is not None,
        location="host",
        device_logical_id=None,
        device_physical_id=None,
        device_mapping_explicit=False,
        correlation=_extract_correlation(message),
        interaction=_interaction(message),
        clock_alignment=_clock_alignment(message),
    )


def parse_device_cann_record(
    line: str, source_path: str, line_number: int
) -> ParsedRecord | None:
    match = _PLOG_RECORD.match(line)
    if match is None:
        return None
    fields = match.groupdict()
    wall_timestamp_us = _parse_wall_timestamp(fields["timestamp"])
    if wall_timestamp_us is None:
        return None

    normalized_path = source_path.replace("\\", "/").lower()
    path_match = _PHYSICAL_DEVICE_PATH.search(normalized_path)
    path_physical_id = path_match.group("physical") if path_match else None
    message = fields["message"].strip()
    mapping_match = _DEVICE_MAPPING.search(message)
    logical_id = mapping_match.group("logical") if mapping_match else None
    explicit_physical_id = mapping_match.group("physical") if mapping_match else None
    identity_conflict = (
        path_physical_id is not None
        and explicit_physical_id is not None
        and path_physical_id != explicit_physical_id
    )
    physical_id = None if identity_conflict else explicit_physical_id or path_physical_id
    boot_match = _DEVICE_BOOT_TIME.search(fields["context"])
    is_boot_relative = fields["timestamp"].startswith("1970-") and boot_match is not None
    if is_boot_relative:
        monotonic_raw = boot_match.group("seconds")
        timestamp_us = _decimal_seconds_to_microseconds(monotonic_raw)
        clock_kind = "device-boot-relative"
    else:
        monotonic_raw = None
        timestamp_us = wall_timestamp_us
        clock_kind = "device-wall-unknown-zone"
    if identity_conflict:
        domain_suffix = f"conflict-{path_physical_id}-{explicit_physical_id}"
    elif physical_id is None:
        source_scope = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()[:12]
        domain_suffix = f"unknown-source-{source_scope}"
    else:
        domain_suffix = physical_id
    raw_module = fields["module"].strip()
    level = fields["level"].upper()
    tid_match = _TID.search(fields["context"])
    fault_rule_id = _fault_rule(level, message)
    return ParsedRecord(
        level=level,
        raw_module=raw_module,
        component=_COMPONENTS.get(raw_module.upper(), "Unclassified"),
        component_mapping_rule=(
            f"builtin-device-v1:{raw_module.upper()}"
            if raw_module.upper() in _COMPONENTS
            else "unclassified-device-v1"
        ),
        pid=fields["pid"],
        tid=tid_match.group("tid") if tid_match else None,
        process=fields["process"].strip(),
        raw_timestamp=fields["timestamp"],
        timestamp_us=timestamp_us,
        clock_domain_id=f"clock-{clock_kind}-physical-{domain_suffix}",
        clock_kind=clock_kind,
        monotonic_raw=monotonic_raw,
        message=message,
        source_path=source_path,
        line=line_number,
        record_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
        excerpt=line,
        parser_name="device-common-slog",
        parser_version=PARSER_VERSIONS["device-common-slog"],
        fault_rule_id=fault_rule_id,
        is_fault_candidate=fault_rule_id is not None,
        location="device",
        device_logical_id=logical_id,
        device_physical_id=physical_id,
        device_mapping_explicit=mapping_match is not None and not identity_conflict,
        device_path_physical_id=path_physical_id,
        device_reported_physical_id=explicit_physical_id,
        device_identity_conflict=identity_conflict,
        correlation=_extract_correlation(message),
        interaction=_interaction(message),
        clock_alignment=_clock_alignment(message),
    )


def parse_host_kernel_record(
    line: str, source_path: str, line_number: int
) -> ParsedRecord | None:
    match = _KERNEL_RECORD.match(line)
    if match is None:
        return None
    fields = match.groupdict()
    timestamp_us = _parse_wall_timestamp(fields["timestamp"])
    if timestamp_us is None:
        return None
    subject = fields["subject"].split(":")
    process = subject[0].strip()
    numeric_ids = [part for part in subject[1:] if part.isdigit()]
    pid = numeric_ids[0] if numeric_ids else None
    tid = numeric_ids[1] if len(numeric_ids) > 1 else None
    level = fields["level"].upper()
    message = fields["message"].strip()
    fault_rule_id = _fault_rule(level, message)
    raw_module = fields["module"].strip()
    is_driver_module = raw_module.lower() in _KERNEL_DRIVER_MODULES
    return ParsedRecord(
        level=level,
        raw_module=raw_module,
        component="Driver" if is_driver_module else "Unclassified",
        component_mapping_rule=(
            f"host-kernel-v1:{raw_module}"
            if is_driver_module
            else "unclassified-host-kernel-v1"
        ),
        pid=pid,
        tid=tid,
        process=process,
        raw_timestamp=fields["timestamp"],
        timestamp_us=timestamp_us,
        clock_domain_id=HOST_CLOCK_DOMAIN_ID,
        clock_kind="host-wall-unknown-zone",
        monotonic_raw=fields["monotonic"],
        message=message,
        source_path=source_path,
        line=line_number,
        record_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
        excerpt=line,
        parser_name="host-kernel",
        parser_version=PARSER_VERSIONS["host-kernel"],
        fault_rule_id=fault_rule_id,
        is_fault_candidate=fault_rule_id is not None,
        location="host",
        device_logical_id=None,
        device_physical_id=None,
        device_mapping_explicit=False,
        correlation=_extract_correlation(message),
        interaction=_interaction(message),
        clock_alignment=_clock_alignment(message),
    )


def parse_stackcore_trace(
    source_path: str, lines: list[tuple[int, str]]
) -> ParsedRecord | None:
    timestamp_match = _STACKCORE_TIMESTAMP.search(source_path.replace("\\", "/"))
    if timestamp_match is None:
        return None
    header: dict[str, tuple[int, str]] = {}
    for line_number, line in lines:
        key, separator, value = line.partition(":")
        if separator and key in {"crash task", "crash pid", "crash tid", "crash reason"}:
            header[key] = (line_number, value.strip())
        if line.strip() == "[stack]":
            break
    if not {"crash task", "crash pid", "crash tid", "crash reason"}.issubset(header):
        return None
    reason_line, reason = header["crash reason"]
    if re.fullmatch(r"signal\s+6", reason, re.IGNORECASE) is None:
        return None
    raw_timestamp = timestamp_match.group("timestamp")
    timestamp_us = _parse_compact_wall_timestamp(raw_timestamp)
    if timestamp_us is None:
        return None
    reason_source_line = next(line for number, line in lines if number == reason_line)
    evidence_lines = tuple(
        (line_number, source_line, hashlib.sha256(source_line.encode("utf-8")).hexdigest())
        for key in ("crash task", "crash pid", "crash tid")
        for line_number, _ in (header[key],)
        for source_line in (next(line for number, line in lines if number == line_number),)
    )
    message = f"crash reason: {reason}"
    return ParsedRecord(
        level="FATAL",
        raw_module="stackcore",
        component="Trace",
        component_mapping_rule="builtin-trace-v1:stackcore",
        pid=header["crash pid"][1],
        tid=header["crash tid"][1],
        process=header["crash task"][1],
        raw_timestamp=raw_timestamp,
        timestamp_us=timestamp_us,
        clock_domain_id=HOST_CLOCK_DOMAIN_ID,
        clock_kind="host-wall-unknown-zone",
        monotonic_raw=None,
        message=message,
        source_path=source_path,
        line=reason_line,
        record_sha256=hashlib.sha256(reason_source_line.encode("utf-8")).hexdigest(),
        excerpt=reason_source_line,
        parser_name="cann-stackcore-trace",
        parser_version=PARSER_VERSIONS["cann-stackcore-trace"],
        fault_rule_id="trace-signal-6",
        is_fault_candidate=True,
        location="host",
        device_logical_id=None,
        device_physical_id=None,
        device_mapping_explicit=False,
        additional_evidence=evidence_lines,
    )


_ADAPTERS = (
    _Adapter(
        "host-common-plog",
        "host-common-plog-v2",
        PARSER_VERSIONS["host-common-plog"],
        _PLOG_RECORD,
        parse_cann_record,
    ),
    _Adapter(
        "host-kernel",
        "host-kernel-v1",
        PARSER_VERSIONS["host-kernel"],
        _KERNEL_RECORD,
        parse_host_kernel_record,
    ),
    _Adapter(
        "device-common-slog",
        "device-common-slog-v1",
        PARSER_VERSIONS["device-common-slog"],
        _PLOG_RECORD,
        parse_device_cann_record,
    ),
)


def scan_input(
    input_path: Path, limits: ReaderLimits | None = None
) -> tuple[list[ParsedRecord], list[dict[str, object]], list[OrphanRecord], str]:
    package_entries, inventory, scope_id = read_package(input_path, limits)
    records: list[ParsedRecord] = []
    orphans: list[OrphanRecord] = []
    for entry in package_entries:
        text = entry.data.decode("utf-8", errors="replace")
        lines = [(number, line) for number, line in enumerate(text.splitlines(), start=1) if line]
        normalized_path = entry.source_path.replace("\\", "/").lower()
        path_parts = [part for part in normalized_path.replace("!", "/").split("/") if part]
        source_role = _source_role(path_parts)
        if any(part == "execute_log" for part in path_parts):
            execution_lines = []
            parsed_execution_count = 0
            # The terminal ERROR record may appear after the traceback lines
            # it explains. Pre-scan for it so earlier traceback records can
            # reuse its timestamp.
            anchor_timestamp: tuple[str, int] | None = None
            for line_number, line in lines:
                error_record = parse_execution_error_record(
                    entry.source_path, line_number, line
                )
                if error_record is not None:
                    anchor_timestamp = (
                        error_record.raw_timestamp,
                        error_record.timestamp_us,
                    )
                    break
            if anchor_timestamp is not None:
                for line_number, line in lines:
                    execution_record = parse_execution_error_record(
                        entry.source_path, line_number, line
                    ) or parse_execution_traceback_record(
                        entry.source_path, line_number, line, anchor_timestamp[1], anchor_timestamp[0]
                    )
                    if execution_record is not None:
                        records.append(execution_record)
                        execution_lines.append(line_number)
                        parsed_execution_count += 1
            inventory.append(
                {
                    "source_path": entry.source_path,
                    "status": "parsed" if parsed_execution_count else "unsupported",
                    "parser": "application-execute-log-v1" if parsed_execution_count else None,
                    "content_sha256": entry.content_sha256,
                    "parsed_records": parsed_execution_count,
                    "unparsed_records": len(lines) - parsed_execution_count,
                    **({} if parsed_execution_count else {"reason": "no_parser_match"}),
                }
            )
            orphans.extend(
                OrphanRecord(
                    source_path=entry.source_path,
                    line=line_number,
                    record_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    excerpt=line,
                )
                for line_number, line in lines
                if line_number not in execution_lines
            )
            continue
        stackcore_record = (
            parse_stackcore_trace(entry.source_path, lines)
            if source_role != "device" and "stackcore_tracer_" in normalized_path
            else None
        )
        if stackcore_record is not None:
            records.append(stackcore_record)
            modeled_lines = {
                stackcore_record.line,
                *(line_number for line_number, _, _ in stackcore_record.additional_evidence),
            }
            structural_lines = {
                line_number
                for line_number, line in lines
                if line.strip() in {"[process]", "[stack]"}
            }
            unparsed_lines = [
                (line_number, line)
                for line_number, line in lines
                if line_number not in modeled_lines and line_number not in structural_lines
            ]
            inventory.append(
                {
                    "source_path": entry.source_path,
                    "status": "parsed",
                    "parser": "cann-stackcore-trace-v1",
                    "content_sha256": entry.content_sha256,
                    "parsed_records": 1 + len(stackcore_record.additional_evidence),
                    "unparsed_records": len(unparsed_lines),
                }
            )
            orphans.extend(
                OrphanRecord(
                    source_path=entry.source_path,
                    line=line_number,
                    record_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    excerpt=line,
                )
                for line_number, line in unparsed_lines
            )
            continue
        adapter = _select_adapter(entry.source_path, lines)
        parsed_count = 0
        unparsed_lines: list[tuple[int, str]] = []
        for line_number, line in lines:
            record = adapter.parse(line, entry.source_path, line_number) if adapter else None
            if record is None:
                unparsed_lines.append((line_number, line))
            else:
                records.append(record)
                parsed_count += 1
        status = "parsed" if parsed_count else "unsupported"
        item: dict[str, object] = {
            "source_path": entry.source_path,
            "status": status,
            "parser": adapter.inventory_id if adapter else None,
            "content_sha256": entry.content_sha256,
            "parsed_records": parsed_count,
            "unparsed_records": len(unparsed_lines),
        }
        if status == "unsupported":
            item["reason"] = "no_parser_match"
        inventory.append(item)
        if parsed_count:
            orphans.extend(
                OrphanRecord(
                    source_path=entry.source_path,
                    line=line_number,
                    record_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    excerpt=line,
                )
                for line_number, line in unparsed_lines
            )
    return records, inventory, orphans, scope_id


def _select_adapter(source_path: str, lines: list[tuple[int, str]]) -> _Adapter | None:
    normalized_path = source_path.replace("\\", "/").lower()
    path_parts = [part for part in normalized_path.replace("!", "/").split("/") if part]
    source_role = _source_role(path_parts)
    if source_role == "device":
        candidate_adapters = tuple(
            adapter for adapter in _ADAPTERS if adapter.name == "device-common-slog"
        )
    elif source_role == "host":
        candidate_adapters = tuple(
            adapter for adapter in _ADAPTERS if adapter.name != "device-common-slog"
        )
    else:
        return None

    for _, line in lines:
        for adapter in candidate_adapters:
            if adapter.name == "host-kernel" and not normalized_path.endswith("host_kernel.log"):
                continue
            if adapter.pattern.match(line):
                return adapter
    return None


def _source_role(path_parts: list[str]) -> str:
    basename = path_parts[-1] if path_parts else ""
    if (
        basename == "device.log"
        or "device" in path_parts
        or "device-os" in path_parts
        or any(part.startswith("dev-os-") for part in path_parts)
        or ("host" not in path_parts and any(part.startswith("device-") for part in path_parts))
    ):
        return "device"

    if (
        "host" in path_parts
        or "plog" in path_parts
        or any(part.startswith("host-") and part.endswith("plog") for part in path_parts)
        or len(path_parts) == 1
        or basename in {"fault.log", "host.log", "host_kernel.log"}
    ):
        return "host"
    return "unknown"


def _parse_wall_timestamp(raw_timestamp: str) -> int | None:
    parts = raw_timestamp.rsplit(".", 2)
    normalized = (
        f"{parts[0]}.{parts[1]}{parts[2]}"
        if len(parts) == 3 and len(parts[1]) == 3 and len(parts[2]) == 3
        else raw_timestamp
    )
    try:
        parsed_timestamp = datetime.strptime(normalized, "%Y-%m-%d-%H:%M:%S.%f")
    except ValueError:
        return None
    epoch = datetime(1970, 1, 1)
    delta = parsed_timestamp - epoch
    return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds


def _parse_compact_wall_timestamp(raw_timestamp: str) -> int | None:
    try:
        parsed_timestamp = datetime.strptime(raw_timestamp, "%Y%m%d%H%M%S%f")
    except ValueError:
        return None
    epoch = datetime(1970, 1, 1)
    delta = parsed_timestamp - epoch
    return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds


def _decimal_seconds_to_microseconds(raw_seconds: str) -> int:
    whole, fractional = raw_seconds.split(".", 1)
    return int(whole) * 1_000_000 + int(fractional)


def _fault_rule(level: str, message: str) -> str | None:
    if level == "FATAL":
        return "level-fatal"
    # Routine INFO callbacks such as SetTaskAbortCallBack mention "abort"
    # but are not faults.  Message-pattern fault rules require ERROR/FATAL;
    # explicit signals (SIGABRT etc.) remain candidates at WARNING too.
    if level not in {"ERROR", "FATAL", "WARNING"}:
        return None
    if level == "WARNING" and not re.search(r"SIG(?:ABRT|SEGV|BUS|ILL|FPE)", message):
        return None
    if _NEGATED_FAULT.search(message) or _BENIGN_FAULT_CONTEXT.search(message):
        return None
    for rule_id, pattern in _FAULT_RULES:
        if pattern.search(message):
            return rule_id
    return None


def _extract_correlation(message: str) -> tuple[tuple[str, str], ...]:
    values: dict[str, set[str]] = {}
    for match in _CORRELATION_FIELD.finditer(message):
        key = match.group("key").lower()
        normalized_key = "device_id" if key == "dev_id" else key
        values.setdefault(normalized_key, set()).add(match.group("value"))
    if any(len(items) != 1 for items in values.values()):
        return ()
    return tuple(sorted((key, next(iter(items))) for key, items in values.items()))


def _interaction(message: str) -> str | None:
    if _FAILED_INTERACTION.search(message):
        return None
    for interaction, pattern in _INTERACTION_RULES:
        if pattern.search(message):
            return interaction
    return None


_EXECUTE_TRACEBACK_OPERATOR = re.compile(
    r"current working operator name is (?P<operator>[A-Za-z0-9_]+)",
    re.IGNORECASE,
)
_EXECUTE_CUSTOM_HAND_FAIL = re.compile(
    r"custom op execution failed,.*ret=(?P<ret>-?\d+)",
    re.IGNORECASE,
)
_EXECUTE_ERROR_RECORD = re.compile(
    r"^\[ERROR\]\s+"
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
    r"\(PID:(?P<pid>[^,]+),[^)]*\)\s+"
    r"(?P<code>ERR\d{5})\s+(?P<message>.*)$"
)


def parse_execution_traceback_record(
    source_path: str,
    line_number: int,
    line: str,
    timestamp_us: int,
    raw_timestamp: str,
) -> ParsedRecord | None:
    operator_match = _EXECUTE_TRACEBACK_OPERATOR.search(line)
    custom_match = _EXECUTE_CUSTOM_HAND_FAIL.search(line)
    match = operator_match or custom_match
    if match is None:
        return None
    operator = match.groupdict().get("operator")
    ret = match.groupdict().get("ret") if custom_match else "9"
    if operator is None or ret is None:
        return None
    message = f"{operator} call failed, {'' if custom_match else 'inner error, '}ret={ret}"
    return ParsedRecord(
        level="ERROR",
        raw_module="APP",
        component="Application",
        component_mapping_rule="builtin-application-v1:execute-log",
        pid=None,
        tid=None,
        process="application",
        raw_timestamp=raw_timestamp,
        timestamp_us=timestamp_us,
        clock_domain_id=HOST_CLOCK_DOMAIN_ID,
        clock_kind="host-wall-unknown-zone",
        monotonic_raw=None,
        message=message,
        source_path=source_path,
        line=line_number,
        record_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
        excerpt=line,
        parser_name="application-execute-log",
        parser_version="1.0.0",
        fault_rule_id="level-error",
        is_fault_candidate=True,
        location="host",
        device_logical_id=None,
        device_physical_id=None,
        device_mapping_explicit=False,
        device_path_physical_id=None,
        device_reported_physical_id=None,
        device_identity_conflict=False,
        interaction="error-propagation" if operator_match else "error-source",
        correlation=(("error_code", str(ret)),),
        clock_alignment=None,
        additional_evidence=[],
    )


def parse_execution_error_record(
    source_path: str,
    line_number: int,
    line: str,
) -> ParsedRecord | None:
    match = _EXECUTE_ERROR_RECORD.match(line)
    if match is None:
        return None
    raw_timestamp = match.group("timestamp")
    parsed_us = _parse_wall_timestamp(raw_timestamp)
    if parsed_us is None:
        # execute_log terminal records use second precision without a
        # fractional part; accept that form directly.
        try:
            parsed_dt = datetime.strptime(raw_timestamp, "%Y-%m-%d-%H:%M:%S")
            epoch = datetime(1970, 1, 1)
            delta = parsed_dt - epoch
            parsed_us = delta.days * 86_400_000_000 + delta.seconds * 1_000_000
        except ValueError:
            parsed_us = None
    if parsed_us is None:
        parsed_us = _parse_compact_wall_timestamp(raw_timestamp)
    if parsed_us is None:
        return None
    code = match.group("code")
    message = f"{code} {match.group('message').strip()}"
    return ParsedRecord(
        level="ERROR",
        raw_module="APP",
        component="Application",
        component_mapping_rule="builtin-application-v1:execute-log",
        pid=match.group("pid"),
        tid=None,
        process="application",
        raw_timestamp=raw_timestamp,
        timestamp_us=parsed_us,
        clock_domain_id=HOST_CLOCK_DOMAIN_ID,
        clock_kind="host-wall-unknown-zone",
        monotonic_raw=None,
        message=message,
        source_path=source_path,
        line=line_number,
        record_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
        excerpt=line,
        parser_name="application-execute-log",
        parser_version="1.0.0",
        fault_rule_id="level-error",
        is_fault_candidate=True,
        location="host",
        device_logical_id=None,
        device_physical_id=None,
        device_mapping_explicit=False,
        device_path_physical_id=None,
        device_reported_physical_id=None,
        device_identity_conflict=False,
        interaction=None,
        correlation=(("error_code", code),),
        clock_alignment=None,
        additional_evidence=[],
    )


def _clock_alignment(message: str) -> tuple[str, int, int, str] | None:
    match = _CLOCK_ALIGNMENT.search(message)
    if match is None:
        return None
    return (
        match.group("target"),
        int(match.group("offset")),
        int(match.group("uncertainty")),
        match.group("method"),
    )
