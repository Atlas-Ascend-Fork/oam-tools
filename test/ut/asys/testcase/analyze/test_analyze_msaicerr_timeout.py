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
import shutil


from analyze import AsysAnalyze
from common.const import MSAICERR_ANALYZE_TIMEOUT
from params import ParamDict
from ..conftest import AssertTest, test_trace_tmp


def setup_module():
    print("TestAnalyzeMsaicerrTimeout ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestAnalyzeMsaicerrTimeout ut test finish.")  # noqa: T201  # test diagnostic output


class TestAnalyzeMsaicerrTimeout(AssertTest):
    def setup_method(self):
        if os.path.exists(test_trace_tmp):
            shutil.rmtree(test_trace_tmp)
        os.mkdir(test_trace_tmp)
        ParamDict.clear()

    def teardown_method(self):
        ParamDict.clear()
        if os.path.exists(test_trace_tmp):
            shutil.rmtree(test_trace_tmp)

    def test_analyze_timeout_budget_is_three_minutes(self):
        # #399 已拍板的超时规格：msaicerr -p 命令超时 3 分钟
        self.assertTrue(MSAICERR_ANALYZE_TIMEOUT == 180)

    def test_aicore_error_analyze_passes_the_budget(self, mocker):
        # 超时预算必须真的传给 real_time_output：不传的话 msaicerr -p 挂死时
        # analyze 主流程永久阻塞（#399 清单，analyze 转调路径）。
        from analyze import asys_analyze

        seen = {}
        mocker.patch.object(
            asys_analyze,
            "real_time_output",
            side_effect=lambda cmd, timeout=None, **_kw: (
                seen.update({"timeout": timeout}) or True
            ),
        )
        mocker.patch("os.path.exists", return_value=True)
        analyze = AsysAnalyze.__new__(AsysAnalyze)
        analyze.output = test_trace_tmp
        analyze.path = test_trace_tmp
        analyze.device_id = 0
        mocker.patch.object(AsysAnalyze, "clean_output", return_value=True)
        self.assertTrue(analyze._AsysAnalyze__aicore_error_analyze() is True)
        self.assertTrue(seen.get("timeout") == MSAICERR_ANALYZE_TIMEOUT)

    def test_aicore_error_analyze_timeout_returns_false(self, mocker):
        # real_time_output 超时契约返回 False；analyze 须把该结果原样返回，
        # clean_output 仍执行（产物目录不残留）。
        from analyze import asys_analyze

        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(asys_analyze, "real_time_output", return_value=False)
        analyze = AsysAnalyze.__new__(AsysAnalyze)
        analyze.output = test_trace_tmp
        analyze.path = test_trace_tmp
        analyze.device_id = 0
        cleaned = mocker.patch.object(analyze, "clean_output")
        self.assertTrue(analyze._AsysAnalyze__aicore_error_analyze() is False)
        cleaned.assert_called_once()
