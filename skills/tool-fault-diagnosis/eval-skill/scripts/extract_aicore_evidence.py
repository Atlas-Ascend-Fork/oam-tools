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
"""Print literal AI Core fields, source lines and explicit address arithmetic."""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys


DEFAULT_MAX_FILE_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_OBSERVATIONS = 10000
DEFAULT_MAX_FILES = 1000
DEFAULT_MAX_SUMMARY_GROUPS = 200
_NUMBER = r"(?:0[xX][0-9a-fA-F]+|[0-9]+)"
_NUMBER_LIST = (_NUMBER + r"(?:\s*,\s*" + _NUMBER +
                r")*(?!\s*,\s*[+-]?\s*(?:0[xX]|[0-9]))")
_VALUE_END = r"(?=$|[\s,;)\]]|\.(?![0-9A-Za-z_]))"
_FIELD_PATTERNS = {
    "kernel_name": r"\bfault kernel_name[ \t]*=[ \t]*([^,\s][^,\r\n]*)",
    "kernel_hash": r"\bhash\s*=\s*([0-9]+)",
    "device_id": r"\bdevice_id\s*=\s*([0-9]+)",
    "stream_id": r"\bstream_id\s*=\s*([0-9]+)",
    "task_id": r"\btask_id\s*=\s*([0-9]+)",
    "chip_id": r"\bchipId\s*:\s*([0-9]+)",
    "core_id": r"\bcore[_ ]id\s*(?:=|is)\s*([0-9]+)",
    "pc_start": r"\bpc start\s*:\s*(0x[0-9a-fA-F]+)",
    "pc_current": r"(?:^|[,;])\s*current\s*:\s*(0x[0-9a-fA-F]+)",
    "parameter_block_address": r"\bpara base\s*:\s*(0x[0-9a-fA-F]+)",
    "args_size_bytes": r"\bargsSize\s*=\s*([0-9]+)",
    "tiling_key": r"\btilingKey\s*=\s*(" + _NUMBER + r")",
    "block_dim": r"\bblockDim\s*=\s*([0-9]+)",
    "error_code": r"\berror code\s*=\s*(" + _NUMBER_LIST + r")",
    "mte_error_code": r"\bMTE errorCode\s*[:=]\s*(" + _NUMBER + r")",
    "error_str": r"\berrorStr:\s*(.*?)(?=\s+fixp_error0 info:|$)",
    "errcode": r"\berrcode:\s*(\([^)]*\))",
}
_FIELD_PATTERNS.update({
    unit + "_error_info": r"\b" + unit + r" error info\s*:\s*(" + _NUMBER + r")"
    for unit in ("vec", "mte", "ifu", "ccu", "cube", "biu")})
_FIELD_PATTERNS.update({
    name + "_info": r"\b" + name + r" info\s*:\s*(" + _NUMBER + r")"
    for name in ("fixp_error0", "fixp_error1")})
_FIELD_PATTERNS = {
    key: re.compile(value + (_VALUE_END if key not in {"kernel_name", "error_str", "errcode"} else ""))
    for key, value in _FIELD_PATTERNS.items()}
_ARGUMENTS = re.compile(
    r"\bargs\(([0-9]+) to ([0-9]+)\)\s+(before|after) execute:\s*("
    + _NUMBER + r"(?:\s*,\s*" + _NUMBER + r")*)" + _VALUE_END)


def extract_fields(text):
    """Extract observations only; values carry no legality or causal assessment."""
    fields = {}
    for key, pattern in _FIELD_PATTERNS.items():
        values = [match.group(1).strip() for match in pattern.finditer(text)]
        if values:
            fields[key] = values[0] if len(values) == 1 else values
    if "kernel_name" not in fields:
        fields.pop("kernel_hash", None)
    if "pc_start" not in fields:
        fields.pop("pc_current", None)
    arguments = []
    for match in _ARGUMENTS.finditer(text):
        if text[match.end():].lstrip().startswith(","):
            continue
        arguments.append({
            "phase": match.group(3), "first_index": match.group(1),
            "last_index": match.group(2),
            "values": [value.strip() for value in match.group(4).split(",")],
        })
    if arguments:
        fields["arguments"] = arguments[0] if len(arguments) == 1 else arguments
    return fields


def calculate_pc_offset(fields, text):
    if (len(re.findall(r"\bpc start\s*:", text)) != 1 or
            len(re.findall(r"(?:^|[,;])\s*current\s*:", text)) != 1):
        return {}
    current, start = fields.get("pc_current"), fields.get("pc_start")
    if not isinstance(current, str) or not isinstance(start, str):
        return {}
    if len(current) > 18 or len(start) > 18:
        return {}
    difference = int(current, 16) - int(start, 16)
    return {"pc_offset_bytes": {
        "operation": "subtract", "operands": {"pc_current": current, "pc_start": start},
        "value_decimal": str(difference), "value_hex": hex(difference), "unit": "bytes",
    }}


def add_signature(summary, index, observation, max_groups):
    fields = {key: observation["fields"][key] for key in
              ("error_code", "mte_error_code", "errcode", "error_str")
              if key in observation["fields"]}
    if not fields:
        return
    summary["matching_lines"] += 1
    key = (observation["source"], json.dumps(fields, sort_keys=True))
    group = index.get(key)
    if group is None:
        if len(index) >= max_groups:
            summary["omitted_observations"] += 1
            return
        group = {"source": observation["source"], "fields": fields,
                 "count": 0, "first": observation}
        index[key] = group
        summary["groups"].append(group)
    group["count"] += 1
    group["last"] = observation


class _WalkLimit(Exception):
    pass


def _source(candidate, root):
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return str(candidate)


def _paths(path, max_errors):
    if path.is_symlink() or not path.is_dir():
        yield path, path.name, None
        return
    errors = []

    def onerror(error):
        errors.append(error)
        if len(errors) > max_errors:
            raise _WalkLimit

    try:
        for parent, directories, files in os.walk(path, followlinks=False, onerror=onerror):
            for error in errors:
                candidate = Path(error.filename) if error.filename else path
                yield candidate, _source(candidate, path), error
            errors.clear()
            directories.sort()
            for name in list(directories):
                candidate = Path(parent) / name
                if candidate.is_symlink():
                    directories.remove(name)
                    yield candidate, _source(candidate, path), None
            for name in sorted(files):
                candidate = Path(parent) / name
                yield candidate, _source(candidate, path), None
    except _WalkLimit:
        pass
    for error in errors:
        candidate = Path(error.filename) if error.filename else path
        yield candidate, _source(candidate, path), error


def scan_logs(path, max_file_bytes=DEFAULT_MAX_FILE_BYTES,
              max_total_bytes=DEFAULT_MAX_TOTAL_BYTES,
              max_observations=DEFAULT_MAX_OBSERVATIONS, max_files=DEFAULT_MAX_FILES,
              summary=False, max_summary_groups=DEFAULT_MAX_SUMMARY_GROUPS):
    path = Path(path)
    if min(max_file_bytes, max_total_bytes, max_observations, max_files,
           max_summary_groups) <= 0:
        raise ValueError("read and observation limits must be positive")
    if not path.exists() and not path.is_symlink():
        raise ValueError("input does not exist")
    result = {"schema_version": "1.1", "status": "complete", "files": [], "observations": []}
    signature_index = {}
    if summary:
        result.pop("observations")
        result.update(schema_version="1.2", summary={
            "groups": [], "matching_lines": 0, "omitted_observations": 0,
            "max_groups": max_summary_groups})
    total_bytes = 0
    for candidate, source, read_error in _paths(path, max_files):
        if len(result["files"]) >= max_files:
            result["files"].append({"source": source, "status": "file_limit", "bytes_read": 0})
            result["status"] = "partial"
            break
        record = {"source": source, "status": "complete", "bytes_read": 0}
        result["files"].append(record)
        if read_error:
            record.update(status="read_error", error=type(read_error).__name__)
        elif candidate.is_symlink():
            record["status"] = "symlink_skipped"
        elif not candidate.is_file():
            record["status"] = "unsupported"
        elif total_bytes >= max_total_bytes:
            record["status"] = "budget_skipped"
        elif not summary and len(result["observations"]) >= max_observations:
            record["status"] = "observation_limit"
        elif not hasattr(os, "O_NOFOLLOW"):
            record["status"] = "unsupported_no_follow"
        else:
            try:
                descriptor = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(descriptor, "rb") as stream:
                    before = os.fstat(stream.fileno())
                    record["size_bytes"] = before.st_size
                    if not stat.S_ISREG(before.st_mode):
                        record["status"] = "unsupported"
                    line_number = 0
                    while record["status"] == "complete" and record["bytes_read"] < before.st_size:
                        if not summary and len(result["observations"]) >= max_observations:
                            record["status"] = "observation_limit"
                            break
                        remaining = min(max_file_bytes - record["bytes_read"],
                                        max_total_bytes - total_bytes)
                        if remaining <= 0:
                            record["status"] = "truncated"
                            break
                        raw = stream.readline(remaining)
                        if not raw:
                            record["status"] = "changed_during_read"
                            break
                        record["bytes_read"] += len(raw)
                        total_bytes += len(raw)
                        if not raw.endswith(b"\n") and record["bytes_read"] < record["size_bytes"]:
                            record["status"] = "truncated"
                            break
                        line_number += 1
                        if b"\0" in raw:
                            record["status"] = "binary_skipped"
                            break
                        try:
                            text = raw.decode("utf-8").rstrip("\r\n")
                        except UnicodeDecodeError:
                            record["status"] = "decode_error"
                            break
                        if summary and "error" not in text and "errcode" not in text:
                            continue
                        fields = extract_fields(text)
                        if fields:
                            observation = {
                                "source": source, "line": line_number, "raw": text, "fields": fields}
                            calculations = calculate_pc_offset(fields, text)
                            if calculations:
                                observation["calculations"] = calculations
                            if summary:
                                add_signature(result["summary"], signature_index,
                                              observation, max_summary_groups)
                            else:
                                result["observations"].append(observation)
                    after = os.fstat(stream.fileno())
                    current = candidate.lstat()
                    if ((before.st_size, before.st_mtime_ns, before.st_ino, before.st_dev) !=
                            (after.st_size, after.st_mtime_ns, current.st_ino, current.st_dev)):
                        record["status"] = "changed_during_read"
            except OSError as error:
                record.update(status="read_error", error=type(error).__name__)
        if record["status"] != "complete":
            result["status"] = "partial"
    if not result["files"]:
        result["status"] = "partial"
    if summary and result["summary"]["omitted_observations"]:
        result["status"] = "partial"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?",
                        help="existing text log file or extracted log directory")
    parser.add_argument("--input", type=Path, dest="input_paths", action="append",
                        help="alternative input path")
    parser.add_argument("--pretty", action="store_true", help="print indented JSON")
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--max-observations", type=int, default=DEFAULT_MAX_OBSERVATIONS)
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--summary", action="store_true",
                        help="scan error signatures, retaining counts and first/last source lines")
    parser.add_argument("--max-summary-groups", type=int, default=DEFAULT_MAX_SUMMARY_GROUPS)
    args = parser.parse_args(argv)
    paths = (args.input_paths or []) + ([args.input] if args.input is not None else [])
    if len(paths) != 1:
        parser.error("provide one input path, either positional or --input")
    try:
        result = scan_logs(paths[0], args.max_file_bytes, args.max_total_bytes,
                           args.max_observations, args.max_files,
                           args.summary, args.max_summary_groups)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
