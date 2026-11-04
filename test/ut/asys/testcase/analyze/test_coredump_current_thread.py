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
def coredump_module(monkeypatch):
    # Isolate device/environment setup; keep the actual gdb output parser.
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
    log.log_warning = Mock()
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
        "_coredump_current_thread_test", root / "analyze/coredump_analyze.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _GdbProcess:
    def __init__(self, output):
        self.stdin = Mock()
        self.stdout = None
        self._output = output

    def communicate(self):
        return self._output, None


@pytest.mark.parametrize(
    "line",
    [
        "[Current thread is <main thread>]",
        "[Current thread is the main thread]",
    ],
)
def test_current_thread_without_numeric_tid_does_not_crash(
    coredump_module, monkeypatch, line
):
    instance = coredump_module.CoreDump("exe", "core", None, "")
    gdb_output = (
        "Program terminated with signal SIGSEGV, Segmentation fault.\n"
        "  1    process       8032  8032  /path/app\n"
        "* 1    process       8032  8032  /path/app\n" + line + "\n"
        "Thread 1 (Thread 0x7ffff50c3700 (LWP 40907)):\n"
        "#0  0x00007f05887750a3 0x00007f058876a000 /path/libtest.so\n"
        "      0x00007f058876a000     0x00007f058877a000     0x6000        0x0 /path/libtest.so\n"
    )
    monkeypatch.setattr(
        coredump_module.subprocess,
        "Popen",
        Mock(return_value=_GdbProcess(gdb_output)),
    )
    stack_txt, pid = instance.start_gdb("[process]\n")
    assert "crash tid: \n" in stack_txt  # empty tid kept, no TypeError raised


def test_current_thread_with_numeric_tid_is_recorded(coredump_module, monkeypatch):
    instance = coredump_module.CoreDump("exe", "core", None, "")
    gdb_output = (
        "Program terminated with signal SIGSEGV, Segmentation fault.\n"
        "  1    process       8032  8032  /path/app\n"
        "* 1    process       8032  8032  /path/app\n"
        "[Current thread is 1 (Thread 0x7ffff50c3700 (LWP 40907))]\n"
        "Thread 1 (Thread 0x7ffff50c3700 (LWP 40907)):\n"
        "#0  0x00007f05887750a3 0x00007f058876a000 /path/libtest.so\n"
        "      0x00007f058876a000     0x00007f058877a000     0x6000        0x0 /path/libtest.so\n"
    )
    monkeypatch.setattr(
        coredump_module.subprocess,
        "Popen",
        Mock(return_value=_GdbProcess(gdb_output)),
    )
    stack_txt, _ = instance.start_gdb("[process]\n")
    assert "crash tid: 40907" in stack_txt
