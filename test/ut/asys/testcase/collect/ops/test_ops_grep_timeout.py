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

# ruff: noqa: E501, S607  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock patterns

import subprocess


from common.const import CMD_TIMEOUT
from collect.ops.ops_collect import _grep_lines
from testcase.conftest import AssertTest


def setup_module():
    print("TestOpsGrepTimeout ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestOpsGrepTimeout ut test finish.")  # noqa: T201  # test diagnostic output


class TestOpsGrepTimeout(AssertTest):
    def test_grep_timeout_budget_is_one_minute(self):
        # #399 已拍板的超时规格：grep 命令超时 1 分钟
        self.assertTrue(CMD_TIMEOUT == 60)

    def test_grep_lines_passes_the_budget_as_subprocess_timeout(self, mocker):
        # 超时预算必须真的传给 subprocess.run：不传的话挂死的 grep 让 collect
        # 流程永久阻塞（#399 清单 #1）。
        seen = {}
        real_run = subprocess.run

        def spy_run(cmd, **kwargs):
            seen.update(kwargs)
            ret = real_run(
                [cmd[0], "--version"], check=False, timeout=10, capture_output=True
            )
            # 与 _grep_lines 的调用契约对齐：带 stdout 的 CompletedProcess
            ret.stdout = ""
            return ret

        mocker.patch("subprocess.run", side_effect=spy_run)
        _grep_lines("pattern", "./")
        self.assertTrue(seen.get("timeout") == CMD_TIMEOUT)

    def test_grep_lines_timeout_returns_empty_list(self, mocker):
        # 挂死的 grep：TimeoutExpired 兜住并按"无匹配"降级返回空列表，
        # 与 OSError 失败路径同一契约。
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="grep", timeout=60),
        )
        self.assertTrue(_grep_lines("pattern", "./") == [])
