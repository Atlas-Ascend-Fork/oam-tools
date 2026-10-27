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

"""Generate fault-trace JSON and offline HTML artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fault_trace_core import build_trace, render_html
from fault_trace_core.package_reader import PackageReadError, ReaderLimits
from fault_trace_core.pipeline import (
    NoUsableTraceError,
    TraceValidationError,
    parse_source_timezone,
)
from fault_trace_core.redaction import compile_additional_patterns


class ConfigurationError(ValueError):
    """Raised when a caller-supplied JSON configuration is invalid."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="one CANN log directory or archive")
    parser.add_argument("--output-dir", type=Path, required=True, help="artifact directory")
    parser.add_argument("--max-entry-bytes", type=_positive_int, default=64 * 1024 * 1024)
    parser.add_argument("--max-total-bytes", type=_positive_int, default=512 * 1024 * 1024)
    parser.add_argument("--max-archive-depth", type=_non_negative_int, default=2)
    parser.add_argument("--context-before-us", type=_non_negative_int, default=1_000_000)
    parser.add_argument("--context-after-us", type=_non_negative_int, default=100_000)
    parser.add_argument("--context-event-limit", type=_non_negative_int, default=20_000)
    parser.add_argument("--anchor-id", help="explicit normalized event ID to select")
    parser.add_argument("--eval-anchor-json", type=Path, help="eval-skill anchor JSON")
    parser.add_argument("--cann-version", help="caller-declared CANN version")
    parser.add_argument(
        "--source-timezone",
        help="timezone for wall-clock records (UTC, +08:00, or IANA name)",
    )
    parser.add_argument(
        "--redaction-config",
        type=Path,
        help="JSON containing additional_patterns; builtin redaction remains enabled",
    )
    return parser.parse_args(argv)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def _load_json_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"invalid {label}: {error}") from error
    if not isinstance(value, dict):
        raise ConfigurationError(f"invalid {label}: top level must be an object")
    return value


def _load_eval_anchor(path: Path | None) -> dict | None:
    if path is None:
        return None
    value = _load_json_object(path, "eval anchor configuration")
    if "fault_anchor" not in value or not isinstance(value["fault_anchor"], dict):
        raise ConfigurationError("invalid eval anchor configuration: expected fault_anchor object")
    anchor = value["fault_anchor"]
    if set(anchor) == {"event_id"} and isinstance(anchor["event_id"], str) and anchor["event_id"]:
        selector = {"kind": "event_id", "value": anchor["event_id"]}
    elif (
        set(anchor) == {"source_path", "line"}
        and isinstance(anchor["source_path"], str)
        and anchor["source_path"]
        and type(anchor["line"]) is int
        and anchor["line"] >= 1
    ):
        selector = {
            "kind": "source_location",
            "source_path": anchor["source_path"],
            "line": anchor["line"],
        }
    else:
        raise ConfigurationError(
            "invalid eval anchor configuration: use event_id or source_path with a positive line"
        )
    return {"source": "eval-skill", "selector": selector}


def _load_redaction_config(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    value = _load_json_object(path, "redaction configuration")
    if set(value) != {"additional_patterns"}:
        raise ConfigurationError(
            "invalid redaction configuration: only additional_patterns is supported"
        )
    patterns = value["additional_patterns"]
    try:
        compile_additional_patterns(patterns)
    except ValueError as error:
        raise ConfigurationError(f"invalid redaction configuration: {error}") from error
    return patterns


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.input.is_symlink():
        print(f"error: top-level input cannot be a symbolic link: {args.input}", file=sys.stderr)
        return 2
    if not args.input.exists() or not (args.input.is_dir() or args.input.is_file()):
        print(f"error: input path is not readable: {args.input}", file=sys.stderr)
        return 2
    try:
        eval_anchor = _load_eval_anchor(args.eval_anchor_json)
        redaction_patterns = _load_redaction_config(args.redaction_config)
        parse_source_timezone(args.source_timezone)
        if args.cann_version is not None and not args.cann_version.strip():
            raise ConfigurationError("invalid CANN version: value must not be empty")
        if args.anchor_id is not None and not args.anchor_id.strip():
            raise ConfigurationError("invalid anchor ID: value must not be empty")
    except (ConfigurationError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    anchor_request = (
        {
            "source": "caller",
            "selector": {"kind": "event_id", "value": args.anchor_id.strip()},
        }
        if args.anchor_id is not None
        else eval_anchor
    )
    input_path = args.input.resolve()
    output_path = args.output_dir.resolve()
    if (
        (output_path.exists() and not output_path.is_dir())
        or output_path == input_path
        or (input_path.is_dir() and input_path in output_path.parents)
    ):
        print(
            "error: invalid output directory: use a directory outside the input boundary",
            file=sys.stderr,
        )
        return 2

    try:
        trace = build_trace(
            input_path,
            ReaderLimits(
                max_entry_bytes=args.max_entry_bytes,
                max_total_bytes=args.max_total_bytes,
                max_archive_depth=args.max_archive_depth,
            ),
            context_before_us=args.context_before_us,
            context_after_us=args.context_after_us,
            context_event_limit=args.context_event_limit,
            anchor_request=anchor_request,
            cann_version=args.cann_version,
            source_timezone=args.source_timezone,
            additional_redaction_patterns=redaction_patterns,
        )
        rendered_html = render_html(trace)
        output_path.mkdir(parents=True, exist_ok=True)
        output_path.joinpath("fault-trace.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output_path.joinpath("tracing-report.html").write_text(
            rendered_html, encoding="utf-8"
        )
        output_path.joinpath("fault-trace.html").write_text(
            rendered_html, encoding="utf-8"
        )
    except PackageReadError as error:
        print(f"error: invalid input package: {error}", file=sys.stderr)
        return 2
    except NoUsableTraceError as error:
        if error.audit is not None:
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                output_path.joinpath("fault-trace-inventory.json").write_text(
                    json.dumps(error.audit, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError as write_error:
                print(f"error: generation failed: {write_error}", file=sys.stderr)
                return 4
        print(f"error: {error}", file=sys.stderr)
        return 3
    except (OSError, TraceValidationError, ValueError) as error:
        print(f"error: generation failed: {error}", file=sys.stderr)
        return 4

    print(f"generated {output_path / 'fault-trace.json'}")
    print(f"generated {output_path / 'tracing-report.html'}")
    print(f"generated {output_path / 'fault-trace.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
