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

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PARSER_ROOT = ROOT / "skills/tool-fault-diagnosis/trace-skill/scripts/fault_trace_core"
# Load the complete production parser and its actual relative dependencies.
# The package initializer also imports an unrelated renderer requiring Python 3.12.
PACKAGE_NAME = "_fault_clause_scope"
PACKAGE_SPEC = importlib.util.spec_from_file_location(
    PACKAGE_NAME,
    PARSER_ROOT / "__init__.py",
    submodule_search_locations=[str(PARSER_ROOT)],
)
assert PACKAGE_SPEC is not None
sys.modules[PACKAGE_NAME] = importlib.util.module_from_spec(PACKAGE_SPEC)
parse_cann_record = importlib.import_module(PACKAGE_NAME + ".parser").parse_cann_record


@pytest.mark.parametrize(
    "message,rule",
    [
        ("no device reset needed; process aborted", "process-abort"),
        ("no crash detected; received SIGABRT", "signal-fatal"),
        ("oom monitor enabled; process crashed", "process-crash"),
        ("received SIGSEGV; no device reset needed", "signal-fatal"),
    ],
)
def test_benign_clause_does_not_hide_independent_fault(message, rule):
    line = "[ERROR] RUNTIME(7,app):2026-10-14-10:11:12.123456 [runtime.cc:3]" + message
    record = parse_cann_record(line, "fault.log", 1)
    assert record is not None
    assert record.is_fault_candidate
    assert record.fault_rule_id == rule
    assert record.message == message


@pytest.mark.parametrize(
    "level,message",
    [
        ("ERROR", "no crash detected"),
        ("ERROR", "oom monitor enabled"),
        ("INFO", "process aborted"),
        ("WARNING", "process aborted"),
    ],
)
def test_benign_and_level_filters_remain(level, message):
    line = (
        f"[{level}] RUNTIME(7,app):2026-10-14-10:11:12.123456 [runtime.cc:3]" + message
    )
    record = parse_cann_record(line, "fault.log", 1)
    assert record is not None
    assert not record.is_fault_candidate


@pytest.mark.parametrize(
    "message",
    [
        "no crash, abort or panic detected",
        "no exception, crash or abort",
        "not a crash or an abort",
        "without crash, panic or abort",
        "no crash or panic",
        "no panic nor abort",
        "no process crash, device reset or exception detected",
        "oom threshold configured, resetting counter",
        "no device reset, crash or panic is required",
    ],
)
def test_coordinated_negation_and_administrative_counters_are_not_faults(message):
    line = "[ERROR] RUNTIME(7,app):2026-10-14-10:11:12.123456 [runtime.cc:3]" + message
    record = parse_cann_record(line, "fault.log", 1)
    assert record is not None
    assert not record.is_fault_candidate


@pytest.mark.parametrize(
    "message,rule",
    [
        ("no crash detected, process aborted", "process-abort"),
        ("no crash but process aborted", "process-abort"),
        ("no crash, abort or panic detected; device resetting", "device-reset"),
        ("oom threshold configured; resetting device", "device-reset"),
        ("without device reset or panic, process aborted", "process-abort"),
    ],
)
def test_negated_lists_keep_independent_positive_faults(message, rule):
    line = "[ERROR] RUNTIME(7,app):2026-10-14-10:11:12.123456 [runtime.cc:3]" + message
    record = parse_cann_record(line, "fault.log", 1)
    assert record is not None
    assert record.is_fault_candidate
    assert record.fault_rule_id == rule
