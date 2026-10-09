#!/usr/bin/env python3
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
"""Search the accepted case library, then classify existing raw evidence for routing.

No log level filtering, root-cause conclusion or collection command is performed.
JSON is the control representation; stage Markdown is written by run_pipeline.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "2.0"
MAX_BYTES_DEFAULT = 8 * 1024 * 1024
MAX_FILES_DEFAULT = 500
ALL_STAGES = ["case_lookup", "detect", "clean", "diagnose", "confidence", "promote", "report"]
DEFAULT_LIBRARY = Path(__file__).resolve().parents[2] / "eval-skill/references/cases.md"
SCENARIOS = {
    "crash": ("进程崩溃", ["coredump", "app_log"], ["fault-flows/crash-flow.md", "coredump-command-playbook.md", "coredump-report-template.md"]),
    "aicore_error": ("AI Core 异常", ["plog", "device_log"], ["fault-flows/aicore-error-flow.md", "ai-core-reference.md"]),
    "oom": ("内存不足", ["app_log"], ["fault-flows/oom-flow.md"]),
    "hang": ("进程卡住", ["app_log"], ["fault-flows/hang-flow.md"]),
    "comm_timeout": ("通信超时", ["plog", "device_log"], ["fault-flows/hang-flow.md", "fault-handling.md"]),
    "card_drop": ("掉卡", ["device_log", "app_log"], ["fault-flows/card-drop-flow.md", "card-drop-reference.md"]),
    "compile_error": ("编译失败", ["app_log"], ["background.md"]),
    "precision": ("精度异常", ["app_log"], ["fault-flows/precision-flow.md"]),
    "perf_degradation": ("性能问题", ["profiling"], ["fault-flows/performance-flow.md"]),
    "offline_inference": ("离线推理/ATC", ["app_log"], ["fault-flows/offline-inference-flow.md"]),
    "network": ("网络故障", ["plog", "device_log"], ["fault-flows/network-flow.md"]),
    "generic_error": ("待分类错误", ["app_log"], []),
    "unknown": ("场景未明确", [], []),
}
MATERIAL_PATTERNS = {
    "plog": r"(^|/)plog(?:[-_/]|$)",
    "device_log": r"(^|/)(?:device[-_]|slog/)|dev-os-|device-os_",
    "coredump": r"(^|/)(?:core(?:\.\d+)?|coredump(?:\..+)?)$|\.core$",
    "stackcore": r"stackcore",
    "asys_output": r"(^|/)asys|msnpureport|msaicerr|hisi_logs",
    "npu_smi": r"npu[-_]smi",
    "app_log": r"\.(?:log|txt|out|err)$",
    "profiling": r"profiling|(^|/)prof_|op_summary|op_statistic",
}
BINARY_SUFFIXES = {".so", ".o", ".a", ".bin", ".pb", ".npy", ".npz", ".om", ".ko", ".pyc", ".gz", ".tar", ".tgz", ".xz", ".zip", ".png", ".jpg", ".pdf", ".pkl", ".pt"}
CODE_RE = re.compile(r"\bE[A-Z0-9]\d{4}\b", re.I)
MODULE_RE = re.compile(r"\[(GE|FE|TE|TBE|HCCL|ACL|RT|RUNTIME|PROF|MEM|HOST|KERNEL|DEVICE)\]", re.I)
ERROR_LEVEL_RE = re.compile(r"\[(ERROR|ERR|FATAL|CRITICAL)\]", re.I)
ERROR_TEXT_RE = re.compile(
    r"\b(?:error|failed|failure|exception|fatal|panic|abort(?:ed)?|"
    r"segmentation fault|sig(?:segv|abrt)|out of memory|memory allocation failed|"
    r"timeout|timed out|deadlock|hang|crash(?:ed)?)\b", re.I)
TIMESTAMP_RE = re.compile(
    # CANN plog commonly uses YYYY-MM-DD-HH:MM:SS.fff.fff, while
    # generic logs use a space/T separator and usually one fractional part.
    r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T-]\d{1,2}:\d{2}:\d{2}"
    r"(?:\.\d+)*(?:Z|[+-]\d{2}:?\d{2})?\b")
OPERATIONS = {
    "allreduce": r"\bAllReduce\b", "allgather": r"\bAllGather\b",
    "broadcast": r"\bBroadcast\b", "reducescatter": r"\bReduceScatter\b",
    "load_graph": r"\bLoad\s+graph\b", "compile_op": r"\bCompile\s+op\b",
    "hbm_allocation": r"\bHBM\s+memory\s+allocation\b", "rtmalloc": r"\brtMalloc\w*\b",
}
SYMPTOMS = {
    "timeout": r"\b(?:timeout|timed out|time out)\b",
    "allocation_failure": r"\b(?:out of memory|memory not enough|memory allocation failed|cannot allocate memory)\b",
    "ub_overflow": r"\bUB\s+memory\s+overflow\b",
    "nonfinite": r"\bcontains\s+(?:inf/nan|nan|inf)\b|\bloss\s*[=:]\s*(?:nan|[-+]?inf)\b",
    "precision_threshold": r"\bmax_diff\s*=",
    "aicore_exception": r"\b(?:aicore|aivec)\s+error(?:\s+exception)?\b|\bAicore kernel execute failed\b",
    "segfault": r"\bSIGSEGV\b|\bSegmentation fault\b",
    "aborted": r"\bSIGABRT\b|\bcore dumped\b",
}


def select_entry_route(request):
    """Select the public entry skill without replacing the scenario pipeline.

    The platform chooses a skill from its description before this script runs.
    Keeping the same boundary in the generated plan makes that decision
    inspectable and prevents a generic log/report request from looking like a
    direct eval invocation. Direct specialist entry is reserved for an
    explicit skill request (or an already-produced eval result for metric).
    """
    text = (request or "").strip()
    lower = text.lower()
    asks_report = bool(re.search(r"诊断报告|完整报告|正式报告|根因报告|html|度量报告|report", lower, re.I))
    explicit_orchestrator = bool(re.search(r"orchestrator(?:-skill)?|统一调度|统一编排", lower, re.I))
    explicit_collect = bool(re.search(r"collect(?:-skill)?|采集日志|收集日志", lower, re.I))
    explicit_eval = bool(re.search(r"eval(?:-skill)?|日志评估技能|评估技能", lower, re.I))
    specialist_terms = (
        r"ai\s*core(?:\s*error)?|aicore|oom|out\s+of\s+memory|coredump|core\s+dump|"
        r"stackcore|sigsegv|sigabrt|通信超时|进程崩溃|任务卡住|hang|precision|精度异常|"
        r"掉卡|卡不在位|\bATC\b|soc_version|离线推理|网络故障"
    )
    explicit_specialist_scenario = bool(re.search(
        r"(?:分析|诊断|排查|定位|处理|专项).{0,8}(?:" + specialist_terms + r")|"
        r"(?:" + specialist_terms + r").{0,8}(?:专项|故障|问题)",
        lower, re.I))
    has_eval_artifact = bool(re.search(
        r"(?:已有|提供了|根据|基于|existing|provided|with|using|based\s+on).*(?:diagnosis(?:\.md)?|confidence(?:\.md)?|评估结论|诊断结论)",
        lower, re.I))

    if explicit_orchestrator:
        return "orchestrator-skill", ["eval-skill", "trace-skill", "metric-skill"], "user_explicitly_requested_orchestrator"
    if explicit_collect and not asks_report:
        return "collect-skill", [], "user_explicitly_requested_collection"
    if has_eval_artifact and asks_report:
        return "metric-skill", [], "existing_eval_artifacts_ready_for_reporting"
    if explicit_eval or explicit_specialist_scenario:
        downstream = ["metric-skill"] if asks_report else []
        reason = "user_explicitly_requested_eval" if explicit_eval else "user_named_single_specialist_scenario"
        return "eval-skill", downstream, reason
    # A raw log plus a generic analysis/diagnosis/report request is the
    # orchestrator boundary. It is a semantic default, not a global force:
    # explicit specialist requests above still take their direct path.
    return "orchestrator-skill", ["eval-skill", "trace-skill", "metric-skill"], "generic_or_multi_stage_log_request"


def _hash(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def extract_features(text):
    """Only evidence vocabulary, never case solutions or generic ERROR/HBM tokens."""
    text = observation_text(text)
    features = {"codes": sorted(set(x.upper() for x in CODE_RE.findall(text))),
                "modules": sorted(set(x.upper() for x in MODULE_RE.findall(text))),
                "operations": [], "symptoms": []}
    for kind, patterns in (("operations", OPERATIONS), ("symptoms", SYMPTOMS)):
        features[kind] = [key for key, pattern in patterns.items() if re.search(pattern, text, re.I)]
    for match in re.finditer(r"\b(?:Op\s+|op\s*=\s*)([A-Za-z][A-Za-z0-9_]*)", text, re.I):
        if match.group(1).lower() not in {"failed", "output", "type"}:
            features["operations"].append("op:" + match.group(1).lower())
    for key in features:
        features[key] = sorted(set(features[key]))
    return features


def observation_text(text):
    """Mask explicit absence/configuration statements for matching, never alter evidence."""
    patterns = [
        r'\b(?:no|without)\s+(?:any\s+)?(?:out of memory|aicore error|segmentation fault|SIGSEGV|SIGABRT|(?:HCCL\s+)?(?:AllReduce\s+)?timeout)\b',
        r'\b(?:SIGSEGV|SIGABRT)\s+handler\s+(?:installed|registered|enabled)\b',
        r'\b(?:install(?:ed|ing)|register(?:ed|ing))\s+(?:an?\s+)?(?:SIGSEGV|SIGABRT)\s+handler\b',
        r'\b(?:HCCL|AllReduce|AllGather|Broadcast|ReduceScatter)\s+timeout\s+(?:configured|configuration|setting|threshold)\b',
        r'\b(?:HCCL|AllReduce|AllGather|Broadcast|ReduceScatter)\s+timeout\s*=\s*\d+(?:ms|s)?\s*(?:configured|enabled|$)',
    ]
    for pattern in patterns:
        text = re.sub(pattern, lambda m: ' ' * len(m.group()), text, flags=re.I)
    return text


def extract_errors(scan):
    """Extract position-preserving error evidence for the routing entry point.

    This is intentionally broader than the scenario signal list: downstream
    diagnosis needs every explicit error line, including codes that do not yet
    map to a dedicated scenario. Negative statements and timeout configuration
    lines are excluded while the original evidence text remains untouched.
    """
    errors = []
    absent = re.compile(r"\b(?:no|without)\s+(?:any\s+)?errors?\b", re.I)
    setup = re.compile(
        r"\b(?:sig(?:segv|abrt)\s+handler|(?:HCCL|AllReduce|AllGather|Broadcast|ReduceScatter)\s+"
        r"timeout)\s*(?:installed|registered|configured|configuration|setting|threshold|=)", re.I)
    for event in scan.get("events", []):
        text = event.get("text", "")
        observed = observation_text(text)
        if absent.search(observed) or setup.search(observed):
            continue
        level = ERROR_LEVEL_RE.search(text)
        keyword = ERROR_TEXT_RE.search(observed)
        codes = sorted(set(code.upper() for code in CODE_RE.findall(text)))
        if not (level or keyword or codes):
            continue
        errors.append({
            "file": event.get("file"),
            "line": event.get("line"),
            "byte_start": event.get("byte_start"),
            "text": text,
            "level": level.group(1).upper() if level else None,
            "codes": codes,
            "keyword": keyword.group(0) if keyword else None,
            "timestamp": (TIMESTAMP_RE.search(text).group(0)
                          if TIMESTAMP_RE.search(text) else None),
            "at": event.get("at"),
        })
    return errors


def _union_features(events):
    result = {key: set() for key in ("codes", "modules", "operations", "symptoms")}
    for event in events:
        for key, values in extract_features(event["text"]).items():
            result[key].update(values)
    return {key: sorted(values) for key, values in result.items()}


def _evidence(file, line, text, byte_start=None):
    return {"file": file, "line": line, "byte_start": byte_start, "text": text,
            "at": "{}:{}".format(file, line) if line is not None else file}


def _read_prefix(stream, size, limit, name):
    raw = stream.read(min(size, limit))
    coverage = {"file": name, "size_bytes": size, "read_bytes": len(raw),
                "sample_sha256": _hash(raw), "scanned_byte_ranges": [],
                "unscanned_byte_ranges": [], "line_range": None, "status": "complete"}
    if b"\x00" in raw[:4096]:
        coverage.update(status="binary", unscanned_byte_ranges=[[0, size]])
        return [], coverage
    usable = raw
    if size > len(raw):
        # Never label a chopped final line as complete or concatenate a tail sample.
        end = raw.rfind(b"\n") + 1
        usable = raw[:end]
        coverage.update(status="truncated", unscanned_byte_ranges=[[end, size]])
    events, offset = [], 0
    for number, line in enumerate(usable.splitlines(keepends=True), 1):
        text = line.decode("utf-8", errors="replace").rstrip("\r\n")
        if number == 1:
            text = text.lstrip("\ufeff")
        events.append(_evidence(name, number, text, offset))
        offset += len(line)
    coverage["scanned_byte_ranges"] = [[0, len(usable)]] if usable else []
    coverage["line_range"] = [1, len(events)] if events else None
    if b"\xef\xbf\xbd" in usable or any("\ufffd" in e["text"] for e in events):
        coverage["encoding_warning"] = "UTF-8 decoding contains replacement characters"
    return events, coverage


def scan_input(input_path, max_bytes=MAX_BYTES_DEFAULT, max_files=MAX_FILES_DEFAULT, min_level=0):
    """Read raw prefixes without filtering levels; byte ranges are zero-based, end-exclusive."""
    path = Path(input_path).resolve()
    if not path.exists():
        raise FileNotFoundError(str(path))
    if max_bytes <= 0 or max_files <= 0:
        raise ValueError("max_bytes and max_files must be positive")
    kind = "directory" if path.is_dir() else ("zip" if path.suffix.lower() == ".zip" else "file")
    result = {"path": str(path), "kind": kind, "events": [], "coverage": [], "rel_paths": [],
              "files_seen": 0, "files_scanned": 0, "omitted_files": [], "limitations": [], "inventory": [],
              "max_bytes": max_bytes, "max_files": max_files}

    def consume(name, size, opener, stamp):
        result["rel_paths"].append(name)
        result["inventory"].append({"file": name, "size": size, "stamp": stamp})
        member_name = name.rsplit("#", 1)[0] if kind == "zip" else name
        if Path(member_name).suffix.lower() in BINARY_SUFFIXES:
            result["coverage"].append({"file": name, "status": "binary", "size_bytes": size,
                                       "scanned_byte_ranges": [], "unscanned_byte_ranges": [[0, size]]})
            return
        try:
            with opener() as stream:
                events, coverage = _read_prefix(stream, size, max_bytes, name)
            result["events"].extend(events)
            result["coverage"].append(coverage)
            result["files_scanned"] += int(coverage["status"] != "binary")
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            result["coverage"].append({"file": name, "status": "unreadable", "error": str(exc),
                                       "scanned_byte_ranges": [], "unscanned_byte_ranges": [[0, size]]})

    if kind == "zip":
        with zipfile.ZipFile(str(path)) as archive:
            entries = sorted((x for x in archive.infolist() if not x.is_dir()), key=lambda x: x.filename)
            result["files_seen"] = len(entries)
            result["omitted_files"] = [x.filename for x in entries[max_files:]]
            for index, entry in enumerate(entries[:max_files]):
                # Duplicate zip member names remain distinguishable by their central-directory index.
                name = "{}!{}#{}".format(path.name, entry.filename.replace("\\", "/"), index)
                consume(name, entry.file_size, lambda e=entry: archive.open(e), [entry.CRC, entry.header_offset])
            result["limitations"].append("ZIP entries are read without extraction; #n identifies duplicate members.")
    else:
        entries = sorted((x for x in path.rglob("*") if x.is_file()), key=lambda x: str(x)) if path.is_dir() else [path]
        result["files_seen"] = len(entries)
        result["omitted_files"] = [str(x.relative_to(path)) for x in entries[max_files:]] if path.is_dir() else []
        for entry in entries[:max_files]:
            name = entry.relative_to(path).as_posix() if path.is_dir() else entry.name
            stat = entry.stat()
            consume(name, stat.st_size, lambda p=entry: p.open("rb"), stat.st_mtime_ns)
    for coverage in result["coverage"]:
        if coverage["status"] != "complete":
            result["limitations"].append("{}: {}; unscanned bytes {}".format(
                coverage["file"], coverage["status"], coverage.get("unscanned_byte_ranges", [])))
        if coverage.get("encoding_warning"):
            result["limitations"].append(coverage["file"] + ": " + coverage["encoding_warning"])
    if result["omitted_files"]:
        result["limitations"].append("max_files reached: {} files not scanned".format(len(result["omitted_files"])))
    result["errors"] = extract_errors(result)
    return result


def _input_fingerprint(scan, request):
    payload = {key: scan.get(key, []) if key == "errors" else scan[key]
               for key in ("path", "kind", "max_bytes", "max_files", "inventory", "coverage", "omitted_files", "errors")}
    payload["request"] = request
    return _hash(payload)


def _library(path):
    path = Path(path).resolve()
    if path.name.lower() != "cases.md":
        raise ValueError("Only the accepted cases.md library may be searched")
    try:
        raw = path.read_bytes()
        return str(path), _hash(raw), raw.decode("utf-8-sig"), None
    except (OSError, UnicodeError) as exc:
        return str(path), None, "", "{}: {}".format(type(exc).__name__, exc)


def _case_signatures(text):
    """Parse only the explicit log-signature section, stopping before root cause/solution."""
    versions = re.findall(r"\bCANN\s+([0-9]+(?:\.[0-9]+)+)", text[:1500], re.I)
    header = re.compile(r"^##\s+(CASE-\d+)[：:]\s*(.+)$", re.M)
    blocks = list(header.finditer(text))
    for index, match in enumerate(blocks):
        end = blocks[index + 1].start() if index + 1 < len(blocks) else len(text)
        block = text[match.end():end]
        signature = re.search(r"\*\*(?:关键日志特征|日志特征签名|Signature)\*\*\s*(.*?)(?=\n\*\*|\n##|\Z)", block, re.S | re.I)
        if not signature:
            continue
        excerpt = signature.group(1).strip()
        lines = [line for line in excerpt.splitlines() if line.strip() and not line.strip().startswith("```")]
        yield {"case_id": match.group(1), "title": match.group(2).strip(),
               "library_line": text[:match.start()].count("\n") + 1,
               "signature": excerpt, "lines": lines, "applicable_versions": sorted(set(versions))}


def lookup_cases(input_or_scan, request="", max_bytes=MAX_BYTES_DEFAULT,
                 max_files=MAX_FILES_DEFAULT, level="DEBUG", case_library=None):
    """Return candidate matches, not a diagnosis; only current raw log lines can match."""
    scan = input_or_scan if isinstance(input_or_scan, dict) else scan_input(input_or_scan, max_bytes, max_files)
    path, digest, library_text, error = _library(case_library or DEFAULT_LIBRARY)
    result = {"status": "miss", "library_path": path, "library_sha256": digest,
              "input_fingerprint": _input_fingerprint(scan, request), "query_features": _union_features(scan["events"]),
              "matches": [], "errors": scan.get("errors", []),
              "limitations": list(scan["limitations"]), "cases_examined": 0}
    if error:
        result["status"] = "unavailable"
        result["limitations"].append("Accepted case library unavailable: " + error)
        return result
    indexed = [(event, extract_features(event["text"])) for event in scan["events"]]
    for case in _case_signatures(library_text):
        result["cases_examined"] += 1
        sig_events = [{"text": line} for line in case["lines"]]
        expected = _union_features(sig_events)
        evidence, matched_features, methods = [], {key: set() for key in expected}, set()
        for signature_line in case["lines"]:
            signature = extract_features(signature_line)
            for event, observed in indexed:
                common = {key: set(signature[key]) & set(observed[key]) for key in signature}
                # EZ9999 wraps multiple underlying failures; it cannot identify a case by itself.
                strong_code = bool(common["codes"] - {"EZ9999"})
                combination = all(common[key] for key in ("modules", "operations", "symptoms"))
                if not (strong_code or combination):
                    continue
                methods.add("strong_error_code" if strong_code else "module_operation_symptom")
                if event not in evidence and len(evidence) < 8:
                    evidence.append(event)
                for key in common:
                    matched_features[key].update(common[key])
        if not evidence:
            continue
        unmatched = {key: sorted(set(expected[key]) - matched_features[key]) for key in expected}
        result["matches"].append({key: case[key] for key in ("case_id", "title", "library_line", "signature", "applicable_versions")})
        result["matches"][-1].update({"match_methods": sorted(methods), "evidence": evidence,
            "matched_features": {key: sorted(value) for key, value in matched_features.items()},
            "differences": {"unmatched_signature_features": unmatched,
                            "version_applicability": "unverified", "environment_applicability": "unverified"},
            "root_cause_status": "candidate_only"})

    if result["matches"]:
        result["status"] = "hit"
        result["limitations"].append("Signature similarity does not verify case root cause, environment or version applicability.")
    if not result["cases_examined"]:
        result["status"] = "unavailable"
        result["limitations"].append("No parseable CASE log-signature sections in accepted library.")
    return result


def validate_case_result(scan, request, result, case_library):
    path, digest, _, error = _library(case_library or DEFAULT_LIBRARY)
    if result.get("status") not in {"hit", "miss", "unavailable"}:
        raise ValueError("Invalid case_lookup result status")
    if result.get("input_fingerprint") != _input_fingerprint(scan, request):
        raise ValueError("case-match input fingerprint differs from current raw input or request")
    if result.get("library_path") != path or result.get("library_sha256") != digest:
        raise ValueError("case-match library path/hash differs from current cases.md")
    if error and result.get("status") != "unavailable":
        raise ValueError("case-match no longer has a readable accepted library")


# Each signal contributes once; repeating one line cannot change any score.
# EZ9999 alone is an outer error wrapper, and exit 137 alone only indicates SIGKILL.
CONTENT_SIGNALS = [
    ("crash_signal", "crash", 60, r"\bSIGSEGV\b|\bSegmentation fault\b|\bSIGABRT\b|\bcore dumped\b|\bsignal\s+(?:11|6)\b"),
    ("uncaught_exception", "crash", 50, r"\bterminate called after throwing\b|\bFatal Python error\b"),
    ("aicore_exception", "aicore_error", 60, r"\b(?:aicore|aivec)\s+error(?:\s+exception)?\b|\bAicore kernel execute failed\b"),
    ("aicore_fault", "aicore_error", 50, r"\bfault kernel_name\s*[:=]|\b(?:aic|vec|mte|ifu) error (?:info|mask)\b"),
    ("oom_allocation", "oom", 60, r"\bEL0004\b|\bout of memory\b|\bMemory_Allocation_Failure\b|\bmemory not enough\b|\bHBM memory allocation failed\b"),
    ("host_oom", "oom", 60, r"\boom-killer\b|\boom-kill\b|\bstd::bad_alloc\b|\bCannot allocate memory\b"),
    ("hang_no_progress", "hang", 50, r"\bno progress(?:\s+for|\s+detected)\b|\bdeadlock detected\b|\btask not finish\b"),
    ("hang_wait", "hang", 20, r"\bfutex_wait\b|\bstill waiting\b|\bStream_?Synchronize_?Timeout\b|\bEE1002\b"),
    ("comm_timeout", "comm_timeout", 60, r"\bEI0002\b|\bCommunication_Error_Timeout\b|\bHCCL(?:_EXEC|_CONNECT)_TIMEOUT\s*(?:occurred|failed)|\b(?:HCCL|AllReduce|AllGather|Broadcast|ReduceScatter)\b.{0,70}\b(?:timeout|timed out|time out)\b"),
    ("compile_failed", "compile_error", 60, r"\b(?:compile\s+op|graph\s+(?:compile|build)|build\s+graph|compilation)\b.{0,60}\b(?:failed|error)\b|\bUB memory overflow\b|\bEB\d{4}\b"),
    ("precision_nonfinite", "precision", 60, r"\bcontains\s+(?:inf/nan|nan|inf)\b|\bloss\s*[=:]\s*(?:nan|[-+]?inf)\b|\b(?:precision|numeric) overflow detected\b"),
    ("perf_regression", "perf_degradation", 50, r"\bperformance regression\b|性能(?:劣化|下降)|吞吐(?:下降|降低)"),
    ("card_drop_device", "card_drop", 60, r"\bEL0001\b|\bDevice_Absent\b|\bDevice_Abnormal\b|卡不在位"),
    ("card_drop_pcie", "card_drop", 50, r"\bPCIe\s+link\s+down\b"),
    ("atc_conversion_failed", "offline_inference", 55, r"\bmodel\s+conversion\s+failed\b|\bATC\b.{0,50}\b(?:failed|error)\b"),
    ("atc_soc_version", "offline_inference", 55, r"\bsoc_version\b"),
    ("offline_inference_error", "offline_inference", 50, r"\bduring\s+ATC\b|\bduring\s+inference\b|\bparameter\s+validation\s+failed\b"),
    ("network_ei0013", "network", 60, r"\bEI0013\b|\bROCE\s+CQE\b"),
    ("network_link_flap", "network", 50, r"端口闪断|网络诊断异常|\blink\s+flap\b|丢包|\bpacket\s+loss\b"),
    ("generic_code", "generic_error", 35, r"\bE[A-Z0-9]\d{4}\b"),
    ("generic_failure", "generic_error", 25, r"\bfailed to\s+\w+|\bFATAL\b|\bRuntimeError:"),
]
REQUEST_SIGNALS = {
    "crash": r"崩溃|段错误|\bcrash(?:ed)?\b|\bcore dumped\b",
    "aicore_error": r"\baicore\b|\baivec\b|AI\s*Core.*异常",
    "oom": r"内存不足|显存不足|爆内存|\boom\b|\bout of memory\b",
    "hang": r"卡住|挂死|卡死|无响应|\bhang\b|\bstuck\b",
    "comm_timeout": r"通信超时|\bhccl\b.*(?:超时|timeout)|\ballreduce\b.*timeout",
    "compile_error": r"编译失败|编译错误|\bcompile\s+(?:error|failed)\b",
    "precision": r"精度异常|精度不达标|不收敛|\bloss\b.*\bnan\b",
    "perf_degradation": r"性能下降|性能劣化|变慢|吞吐下降|\bslow(?:er)?\b",
    "card_drop": r"掉卡|卡消失|查不到卡|卡不在位",
    "offline_inference": r"离线推理|模型转换|\bATC\b|soc_version",
    "network": r"网络故障|丢包|端口闪断|网络排查",
}


def classify(scan, request):
    buckets = {sid: {"id": sid, "name_cn": spec[0], "score": 0, "content_score": 0,
                     "matched_signals": [], "kinds": []} for sid, spec in SCENARIOS.items() if sid != "unknown"}
    signals = [(key, sid, weight, re.compile(pattern, re.I)) for key, sid, weight, pattern in CONTENT_SIGNALS]
    hits = {}
    for event in scan["events"]:
        observed_text = observation_text(event["text"])
        for key, sid, weight, pattern in signals:
            if pattern.search(observed_text):
                hits.setdefault(key, {"id": key, "scenario": sid, "weight": weight,
                                      "kind": "content", "hit_count": 0, "evidence": []})
                hits[key]["hit_count"] += 1
                if len(hits[key]["evidence"]) < 3 and event not in hits[key]["evidence"]:
                    hits[key]["evidence"].append(event)
        diff = re.search(r"\bmax_diff\s*=\s*([0-9.eE+-]+).*?\bthreshold\s*=\s*([0-9.eE+-]+)", event["text"])
        if diff:
            try:
                exceeded = float(diff.group(1)) > float(diff.group(2)) >= 0
            except ValueError:
                exceeded = False
            if exceeded:
                hits.setdefault("precision_threshold", {"id": "precision_threshold", "scenario": "precision", "weight": 60,
                                                       "kind": "content", "hit_count": 1, "evidence": [event]})
    for hit in hits.values():
        bucket = buckets[hit["scenario"]]
        bucket["content_score"] = min(80, bucket["content_score"] + hit["weight"])
        bucket["matched_signals"].append(hit)
    positive_request = " ".join(clause for clause in re.split(r"[,，。;；\n]", request)
                                if not re.search(r"不是|并非|没有|\bnot\b|\bno\b", clause, re.I))
    for sid, bucket in buckets.items():
        bucket["score"] = bucket["content_score"]
        if re.search(REQUEST_SIGNALS.get(sid, r"(?!x)x"), positive_request, re.I):
            bucket["score"] += 12
            bucket["matched_signals"].append({"id": "request_" + sid, "kind": "request", "weight": 12,
                                              "hit_count": 1, "evidence": [_evidence("request", 1, request)]})
        bucket["kinds"] = sorted(set(x["kind"] for x in bucket["matched_signals"]))
        bucket["strong_observation"] = bucket["content_score"] >= 50
    scored = sorted(buckets.values(), key=lambda x: (-int(x["strong_observation"]), -x["content_score"], -x["score"], x["id"]))
    specific = [x for x in scored if x["id"] != "generic_error" and x["strong_observation"]]
    if specific:
        scored = [x for x in scored if x["id"] != "generic_error"] + [buckets["generic_error"]]
    candidates = [x for x in scored if x["score"] > 0 and (x["id"] != "generic_error" or not specific)]
    if not candidates:
        return scored, "unknown", [], "UNKNOWN", True, []
    first = candidates[0]
    notes = []
    strong = [x for x in candidates if x["strong_observation"]]
    if len(strong) > 1:
        earliest = []
        for candidate in strong:
            evidence = [ev for sig in candidate["matched_signals"] if sig["kind"] == "content" and sig["weight"] >= 50 for ev in sig["evidence"]]
            earliest.append((candidate, min(evidence, key=lambda ev: (ev["file"], ev["line"]))))
        if len(set(ev["file"] for _, ev in earliest)) == 1:
            first = min(earliest, key=lambda item: item[1]["line"])[0]
            notes.append("Multiple explicit signals in one raw file: route first by original line order; causality remains unverified.")
    secondary = [x["id"] for x in candidates if x["id"] != first["id"]]
    uncertain = bool(secondary or not first["strong_observation"] or scan["limitations"])
    confidence = "MEDIUM" if first["strong_observation"] else "LOW"
    if not uncertain and len([x for x in first["matched_signals"] if x["kind"] == "content"]) >= 2:
        confidence = "HIGH"
    return scored, first["id"], secondary, confidence, uncertain, notes


def build_plan(input_path, request="", max_bytes=MAX_BYTES_DEFAULT, max_files=MAX_FILES_DEFAULT,
               level="DEBUG", case_library=None, case_lookup_result=None):
    if level != "DEBUG":
        raise ValueError("Scenario recognition requires DEBUG/all levels; use conservative cleaning afterwards")
    scan = input_path if isinstance(input_path, dict) else scan_input(input_path, max_bytes, max_files)
    # This ordering is intentional: classification never runs before a library lookup.
    if case_lookup_result is None:
        case_result = lookup_cases(scan, request, case_library=case_library)
    else:
        validate_case_result(scan, request, case_lookup_result, case_library)
        case_result = case_lookup_result
    scored, primary, secondary, confidence, uncertain, notes = classify(scan, request)
    materials = {}
    for key, pattern in MATERIAL_PATTERNS.items():
        matches = []
        for name in scan["rel_paths"]:
            member = name.split("!", 1)[-1].rsplit("#", 1)[0] if scan["kind"] == "zip" else name
            if re.search(pattern, member, re.I):
                matches.append(name)
        materials[key] = {"present": bool(matches), "count": len(matches), "samples": matches[:20],
                          "verification": "filename_inventory_only; incident relevance unverified"}
    references = ["eval-skill/references/cases.md", "eval-skill/references/err-messages.md",
                  "eval-skill/references/log-spec.md", "eval-skill/references/confidence-assessment.md"]
    for scenario in [primary] + secondary:
        for reference in SCENARIOS[scenario][2]:
            full = "eval-skill/references/" + reference
            if full not in references:
                references.append(full)
    if "perf_degradation" in [primary] + secondary:
        references.extend(["metric-skill/references/baseline-data.md", "metric-skill/references/metric-analysis.md"])
    missing = [key for key in MATERIAL_PATTERNS if not materials[key]["present"]]
    entry_skill, downstream_skills, route_reason = select_entry_route(request)
    skills = []
    for skill in [entry_skill] + downstream_skills:
        if skill not in skills:
            skills.append(skill)
    return {"schema_version": SCHEMA_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(),
            "input": {"path": scan["path"], "kind": scan["kind"], "request": request,
                      "max_bytes": scan["max_bytes"], "max_files": scan["max_files"], "level": "DEBUG",
                      "files_seen": scan["files_seen"], "files_scanned": scan["files_scanned"],
                      "coverage": scan["coverage"], "omitted_files": scan["omitted_files"],
                      "fingerprint": _input_fingerprint(scan, request)},
            "case_lookup": case_result, "primary": primary, "secondary": secondary,
            "errors": scan.get("errors", []),
            "recognition_confidence": confidence, "uncertain": uncertain,
            "scenarios": scored, "materials": materials, "missing_materials": missing,
            "route": {"entry_skill": entry_skill, "downstream_skills": downstream_skills,
                      "selection_reason": route_reason, "skills": skills, "references": references,
                      "pipeline_stages": list(ALL_STAGES)},
            "stages": {"clean": {"level": "DEBUG", "mode": "conservative"}, "promote": {"enabled": False}},
            "notes": notes + list(scan["limitations"]) + [
                "Classification selects a diagnostic route only; candidate cases and source order do not establish root cause.",
                "Missing materials are evidence limits; only existing inputs are analyzed.",
                "Filename inventory does not establish that a core/profiling artifact belongs to this incident."]}


def read_case_markdown(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.S | re.I)
    if len(blocks) != 1:
        raise ValueError("case-match.md must contain exactly one JSON envelope")
    payload = json.loads(blocks[0])
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("case-match.md JSON envelope must contain result object")
    if payload.get("stage") != "case_lookup" or payload.get("status") != "success":
        raise ValueError("case-match.md must be a successful case_lookup artifact")
    return result


def render(plan):
    return "\n".join(["# 场景识别与执行计划", "",
        "- 案例库检索：" + plan["case_lookup"]["status"],
        "- 主场景：" + plan["primary"], "- 竞争场景：" + (", ".join(plan["secondary"]) or "无"),
        "- 识别可信度：" + plan["recognition_confidence"],
        "- 待核实：" + str(plan["uncertain"]),
        "- 入口：" + plan["route"].get("entry_skill", "orchestrator-skill"),
        "- 下游：" + (" → ".join(plan["route"].get("downstream_skills", plan["route"].get("skills", []))) or "无"),
        "- 顺序：" + " → ".join(plan["route"]["pipeline_stages"]),
        "", "分类仅用于选择诊断路线，命中案例仍须核实现有证据和版本适用性。", "",
        "```json", json.dumps(plan, ensure_ascii=False, indent=2), "```"])


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Accepted-case lookup before raw-evidence scenario routing")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--request", default="")
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES_DEFAULT)
    parser.add_argument("--max-files", type=int, default=MAX_FILES_DEFAULT)
    parser.add_argument("--level", choices=["DEBUG"], default="DEBUG", help="All raw log levels remain visible")
    parser.add_argument("--cases-library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--phase", choices=["case_lookup", "detect"], default="detect")
    parser.add_argument("--case-match", type=Path, help="Validated predecessor Markdown artifact")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--plan-out", type=Path)
    args = parser.parse_args(argv)
    try:
        scan = scan_input(args.input, args.max_bytes, args.max_files)
        if args.phase == "case_lookup":
            result = lookup_cases(scan, args.request, case_library=args.cases_library)
        else:
            previous = read_case_markdown(args.case_match) if args.case_match else None
            result = build_plan(scan, args.request, case_library=args.cases_library, case_lookup_result=previous)
        if args.plan_out:
            args.plan_out.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.plan_out.with_name(args.plan_out.name + ".tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(str(temporary), str(args.plan_out))
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print("[ERROR] " + str(exc), file=sys.stderr)
        return 2
    except (OSError, zipfile.BadZipFile) as exc:
        print("[ERROR] " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json or args.phase == "case_lookup" else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
