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

# ruff: noqa: E501, S607  # test mock methods, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock patterns

import os

import pytest

from common.const import CMD_TIMEOUT
from testcase.conftest import AssertTest

from collect.stacktrace import stacktrace_collect


def setup_module():
    print("TestStacktraceCmdTimeout ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestStacktraceCmdTimeout ut test finish.")  # noqa: T201  # test diagnostic output


class TestStacktraceCmdTimeout(AssertTest):
    def test_generic_cmd_timeout_budget_is_one_minute(self):
        # #399 已拍板的超时规格：grep 等通用单条命令超时 1 分钟
        self.assertTrue(CMD_TIMEOUT == 60)

    @pytest.mark.parametrize(
        "checker_name",
        [
            "_check_remote_id_validity",
            "_get_all_tid_of_process",
            "_get_other_stacktrace_remote_id",
        ],
    )
    def test_ps_probes_pass_the_generic_budget(self, mocker, checker_name):
        # ps 探测属于"通用命令"档：必须把 1 分钟预算转发给 popen_run_cmd，
        # 否则挂死的 ps 把 stacktrace 流程永久阻塞（#399 清单 #5 的 bin 文件
        # 探测部分已配 LSOF_TIMEOUT，此处补齐其余探测命令）。
        seen = {}

        def fake_popen_run_cmd(cmd, timeout=None, **_kwargs):
            seen["timeout"] = timeout
            return ""

        mocker.patch.object(stacktrace_collect, "popen_run_cmd", fake_popen_run_cmd)
        trace = stacktrace_collect.AsysStackTrace.__new__(
            stacktrace_collect.AsysStackTrace
        )
        trace.remote_id = os.getpid()  # 真实存在的 pid，过 os.kill(pid, 0) 探活
        if checker_name == "_check_remote_id_validity":
            mocker.patch.object(trace, "_check_remote_id_alive", return_value="0")
            trace._check_remote_id_validity()
        elif checker_name == "_get_all_tid_of_process":
            trace._get_all_tid_of_process(99998)
        else:
            stacktrace_collect.AsysStackTrace._get_other_stacktrace_remote_id(99998)
        self.assertTrue(seen.get("timeout") == CMD_TIMEOUT)
