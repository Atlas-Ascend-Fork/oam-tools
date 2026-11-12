#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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

# ruff: noqa: E501  # long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock patterns

import subprocess


from common.const import ADDR2LINE_TIMEOUT
from testcase.conftest import AssertTest

import sys
from pathlib import Path

ASYS_SRC = Path(__file__).resolve().parents[5] / "src" / "asys"
sys.path.insert(0, str(ASYS_SRC))

from collect.stackcore import stackcore_collect  # noqa: E402


def setup_module():
    print("TestStackcoreAddr2lineTimeout ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestStackcoreAddr2lineTimeout ut test finish.")  # noqa: T201  # test diagnostic output


class TestStackcoreAddr2lineTimeout(AssertTest):
    def test_addr2line_timeout_budget_is_one_minute(self):
        # #399 已拍板的超时规格：addr2line 命令超时 1 分钟
        self.assertTrue(ADDR2LINE_TIMEOUT == 60)

    def test_get_source_location_passes_the_budget(self, monkeypatch):
        # 超时预算必须真的传给 subprocess.check_output：不传的话挂死的
        # addr2line 把解析线程永久阻塞（#399 清单 #4）。
        seen = {}

        def fake_check_output(*args, **kwargs):
            seen.update(kwargs)
            return b"main\n??:?\n"

        monkeypatch.setattr(
            stackcore_collect.subprocess, "check_output", fake_check_output
        )
        parser = stackcore_collect.ParseStackCore([])
        parser.get_source_location("/lib/libc.so", 4096)
        self.assertTrue(seen.get("timeout") == ADDR2LINE_TIMEOUT)

    def test_get_source_location_timeout_degrades_to_empty(self, monkeypatch, caplog):
        # 挂死的 addr2line：TimeoutExpired 走既有"该 so 解析失败"降级路径
        # 返回 []，告警文本与其他异常同构（按异常类型去重）。
        caplog.set_level("DEBUG")

        def fake_check_output(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd="addr2line", timeout=60)

        monkeypatch.setattr(
            stackcore_collect.subprocess, "check_output", fake_check_output
        )
        parser = stackcore_collect.ParseStackCore([])
        parser.file = "stackcore.txt"

        assert parser.get_source_location("/lib/libc.so", 4096) == []
        assert "cannot be parsed by addr2line" in caplog.text
        assert "error: TimeoutExpired." in caplog.text

    def test_readelf_probe_passes_the_budget(self, monkeypatch):
        # parse_line 里的 readelf 探测同样吃 1 分钟预算（run_linux_cmd 转发）。
        seen = {}

        def fake_run_linux_cmd(cmd, cmp_str="", timeout=None, **_kwargs):
            seen["timeout"] = timeout
            return False

        monkeypatch.setattr(stackcore_collect, "run_linux_cmd", fake_run_linux_cmd)
        monkeypatch.setattr(stackcore_collect.os.path, "exists", lambda _p: True)
        monkeypatch.setattr(stackcore_collect.os.path, "isfile", lambda _p: True)
        monkeypatch.setattr(
            stackcore_collect.os,
            "stat",
            lambda _p, **_kw: type("S", (), {"st_mode": 0})(),
        )
        monkeypatch.setattr(
            stackcore_collect.subprocess,
            "check_output",
            lambda *_a, **_k: b"main\n??:?\n",
        )
        parser = stackcore_collect.ParseStackCore([])
        parser.file = "stackcore.txt"
        line = "0 00007f 00007f /lib/libc.so\n"
        parser.parse_line(0, line, [line])
        self.assertTrue(seen.get("timeout") == ADDR2LINE_TIMEOUT)
