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
# -------
from conftest import MSAICERR_PATH, cur_abspath
import os
import sys
import pytest

from ms_interface.single_op_test_frame.runtime import AscendRTSApi
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase
from ms_interface.ascend950.compile_op import CompileOP
from ms_interface.ascend950.ascend950_handler import Ascend950Handler
from ms_interface.run_dirty_ub import run_dirty_ub

sys.path.append(MSAICERR_PATH)


class TestUtilsMethods:
    def common_mock(self, mocker):
        mocker.patch.object(AscendRTSApi, "_load_runtime_so")
        mocker.patch.object(AscendRTSApi, "register_kernel_launch_fill_func")
        mocker.patch.object(AscendRTSApi, "set_device")
        mocker.patch.object(AscendRTSApi, "create_stream")
        mocker.patch.object(AscendRTSApi, "reset")
        mocker.patch.object(AscendRTSApi, "destroy_stream")

    def test_run_dirty_ub(self, mocker):
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        self.common_mock(mocker)
        mocker.patch.object(CompileOP, "get_ub_size", return_value=1)
        mocker.patch.object(
            CompileOP,
            "get_compile_file",
            return_value=[
                "test.o",
                os.path.join(
                    cur_abspath,
                    "../res/ori_data/collect_milan/collection/DirtyCustom_ab1b6750d7f510985325b603cb06dc8b.json",
                ),
            ],
        )
        mocker.patch.object(AscendOpKernelRunner, "run", return_value=None)
        mocker.patch.object(AscendOpKernelRunner, "run")
        mocker.patch("os.path.exists", return_value=True)
        res = run_dirty_ub(config_file, "Ascend950", 0)
        assert res

    def test_run(self, mocker):
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        res = run_dirty_ub(config_file, "Ascend950", 0)
        mocker.patch("ms_interface.run_dirty_ub.run_dirty_ub_tik", return_value=None)
        mocker.patch.object(SingleOpCase, "run_kernel", return_value=None)
        res = single_op_case.run(config_file, "op_test")
        assert res

    @pytest.mark.parametrize(
        "compile_file, log_content",
        [
            (RuntimeError("test"), "Compile dirty_ub op failed, skip dirty ub"),
            ([[]], "Compile dirty_ub op failed, skip dirty ub"),
        ],
    )
    @staticmethod
    def test_run_ascendc(mocker, monkeypatch, tmp_path, compile_file, log_content):
        mocker.patch.object(CompileOP, "get_ub_size", return_value=1)
        mocker.patch.object(CompileOP, "get_compile_file", side_effect=compile_file)
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        monkeypatch.chdir(tmp_path)
        run_dirty_ub(config_file, "Ascend950", 0)
        debug_info = tmp_path.joinpath("debug_info.txt")
        assert log_content in debug_info.read_text(encoding="utf-8")

    def test_run_dirty_ub_with_diff_soc(self, mocker):
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        self.common_mock(mocker)
        mocker.patch.object(CompileOP, "get_ub_size", return_value=1)
        mocker.patch.object(
            CompileOP,
            "get_compile_file",
            return_value=[
                "test.o",
                os.path.join(
                    cur_abspath,
                    "../res/ori_data/collect_milan/collection/DirtyCustom_ab1b6750d7f510985325b603cb06dc8b.json",
                ),
            ],
        )
        mocker.patch.object(AscendOpKernelRunner, "run", return_value=None)
        mocker.patch.object(AscendOpKernelRunner, "run")
        mocker.patch("os.path.exists", return_value=True)
        handler = Ascend950Handler()
        res = handler.run_dirty_ub(config_file, "Ascend910B1", 0)
        assert res
