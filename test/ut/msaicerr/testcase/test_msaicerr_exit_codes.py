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

import os
import sys
from io import StringIO

import pytest

import msaicerr
from conftest import MSAICERR_PATH
from ms_interface.constant import Constant

sys.path.append(MSAICERR_PATH)


class TestMsaicerrExitCodeContract:
    """退出码契约矩阵（#395）：成功 0；无 version 支持/未知参数按失败约定 1。

    与 asys 的契约矩阵（test/ut/asys/testcase/test_asys.py）对齐：
    help 打印用法退出 0；不存在的参数视为失败退出 1。
    """

    @pytest.fixture(autouse=True)
    def setup_opp_path(self):
        os.environ["ASCEND_OPP_PATH"] = "/"

    def test_help_exit_code_is_zero(self, mocker):
        mocker.patch("sys.argv", ["msaicerr.py", "--help"])
        mock_stdout = mocker.patch("sys.stdout", new_callable=StringIO)
        with pytest.raises(SystemExit) as exc_info:
            msaicerr.main()
        assert exc_info.value.code == 0
        assert "usage:" in mock_stdout.getvalue()

    def test_short_help_exit_code_is_zero(self, mocker):
        mocker.patch("sys.argv", ["msaicerr.py", "-h"])
        mocker.patch("sys.stdout", new_callable=StringIO)
        with pytest.raises(SystemExit) as exc_info:
            msaicerr.main()
        assert exc_info.value.code == 0

    def test_version_without_support_exit_code_is_one(self, mocker):
        mocker.patch("sys.argv", ["msaicerr.py", "--version"])
        mocker.patch("sys.stdout", new_callable=StringIO)
        assert msaicerr.main() == Constant.MS_AICERR_INVALID_PARAM_ERROR

    def test_unknown_flag_exit_code_is_one(self, mocker):
        mocker.patch("sys.argv", ["msaicerr.py", "--badflag"])
        mocker.patch("sys.stdout", new_callable=StringIO)
        assert msaicerr.main() == Constant.MS_AICERR_INVALID_PARAM_ERROR
