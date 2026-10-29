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


import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def analyzer(monkeypatch):
    # Isolate device/environment setup; keep the actual mapping parser and constants.
    relative = Path("src/asys/analyze/coredump_analyze.py")
    repository = next(
        (
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / relative).is_file() and (parent / ".git").exists()
        ),
        None,
    )
    assert repository is not None, (
        "Cannot locate the OAM repository containing coredump_analyze.py"
    )
    root = repository / "src/asys"
    common = ModuleType("common")
    common.log_error = Mock()
    common.log_warning = Mock()
    monkeypatch.setitem(sys.modules, "common", common)
    spec = importlib.util.spec_from_file_location(
        "common.const", root / "common/const.py"
    )
    constants = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(constants)
    monkeypatch.setitem(sys.modules, "common.const", constants)
    params = ModuleType("params")
    params.ParamDict = Mock()
    monkeypatch.setitem(sys.modules, "params", params)
    log = ModuleType("common.log")
    log.log_error = Mock()
    log.log_info = Mock()
    monkeypatch.setitem(sys.modules, "common.log", log)
    files = ModuleType("common.file_operate")
    files.FileOperate = Mock()
    monkeypatch.setitem(sys.modules, "common.file_operate", files)
    driver = ModuleType("drv")
    driver.EnvVarName = Mock()
    monkeypatch.setitem(sys.modules, "drv", driver)
    spec = importlib.util.spec_from_file_location(
        "common.task_common", root / "common/task_common.py"
    )
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    monkeypatch.setitem(sys.modules, "common.task_common", helpers)
    spec = importlib.util.spec_from_file_location(
        "_map_order_test", root / "analyze/coredump_analyze.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    instance = module.CoreDump.__new__(module.CoreDump)
    instance.map_str = ""
    instance.map_info = []
    return instance


@pytest.mark.parametrize(
    "first,second,expected",
    [
        (("0x9000", "0x10000"), ("0x10000", "0x11000"), ("0x9000", "0x11000")),
        (("0x9fff", "0xa000"), ("0xa000", "0x10000"), ("0x9fff", "0x10000")),
        (("0x9000", "0x10000"), ("0x8000", "0xa000"), ("0x8000", "0x10000")),
        (("0x8000", "0x11000"), ("0x9000", "0x10000"), ("0x8000", "0x11000")),
        (("9000", "10000"), ("8000", "a000"), ("0x8000", "0x10000")),
        (("0X9000", "0X10000"), ("0X8000", "0XA000"), ("0x8000", "0x10000")),
        (("0x2000", "0x3000"), ("0x3000", "0x4000"), ("0x2000", "0x4000")),
    ],
)
def test_same_library_mapping_union_uses_numeric_order(
    analyzer, first, second, expected
):
    previous = ""
    for start, end in (first, second):
        row = [start, end, "0x1000", "0x0", "library.so"]
        previous = analyzer.collect_info(None, row, "      " + " ".join(row), previous)
    assert analyzer.map_info == [[*expected, "library.so"]]


def test_distinct_libraries_are_not_coalesced(analyzer):
    previous = ""
    for library in ("first.so", "second.so"):
        row = ["0x1000", "0x2000", "0x1000", "0x0", library]
        previous = analyzer.collect_info(None, row, "      " + " ".join(row), previous)
    assert len(analyzer.map_info) == 2


@pytest.mark.parametrize("address", ["", "not-hex", "0xZZ"])
def test_invalid_mapping_line_is_ignored_before_numeric_conversion(analyzer, address):
    good = ["0x9000", "0x10000", "0x1000", "0x0", "library.so"]
    previous = analyzer.collect_info(None, good, "      " + " ".join(good), "")
    original = [row.copy() for row in analyzer.map_info]
    invalid = [address, "0x11000", "0x1000", "0x0", "library.so"]
    assert (
        analyzer.collect_info(None, invalid, "      " + " ".join(invalid), previous)
        == previous
    )
    assert analyzer.map_info == original
