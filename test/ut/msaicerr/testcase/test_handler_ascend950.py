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
import os
import subprocess
import sys
import shutil
import pytest
from pathlib import Path

from conftest import MSAICERR_PATH

sys.path.append(MSAICERR_PATH)
from ms_interface.single_op_test_frame.runtime import AscendRTSApi
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner
from ms_interface.constant import ModeCustom
from ms_interface.ascend950.ascend950_handler import Ascend950Handler
from ms_interface.ascend950.compile_op import CompileOP
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase

cur_abspath = os.path.dirname(__file__)


class TestAscend950Handler:
    @staticmethod
    def test_get_compile_file(mocker):
        mocker.patch.object(AscendOpKernelRunner, "run")
        mocker.patch.object(AscendRTSApi, "_load_runtime_so")
        mocker.patch.object(AscendRTSApi, "register_kernel_launch_fill_func")
        mocker.patch.object(AscendRTSApi, "set_device")
        mocker.patch.object(AscendRTSApi, "create_stream")
        mocker.patch.object(AscendRTSApi, "reset")
        mocker.patch.object(AscendRTSApi, "destroy_stream")
        mocker.patch.object(CompileOP, "get_ub_size", return_value=0)
        mocker.patch("ctypes.CDLL")
        temp_dir = Path(cur_abspath).joinpath("../test_run_golden")
        mocker.patch.object(Path, "exists", return_value=False)
        mocker.patch("shutil.which", return_value=True)
        res = subprocess.run([sys.executable, "-c", ""], check=False)
        mocker.patch("subprocess.run", return_value=res)
        op_kernel_path = temp_dir.joinpath(ModeCustom.ADD_CUSTOM.value, "op_kernel")
        op_kernel_path.mkdir(parents=True, exist_ok=True)
        op_kernel_path.joinpath("add_custom.cpp").write_text("test", encoding="utf-8")
        compile_file_path = temp_dir.joinpath(
            ModeCustom.ADD_CUSTOM.value, "build_out", "op_kernel"
        )
        compile_file_path.mkdir(parents=True, exist_ok=True)
        compile_file_path.joinpath(
            f"{ModeCustom.ADD_CUSTOM.value}_add_custom.o"
        ).write_text("test", encoding="utf-8")
        shutil.copy(
            Path(cur_abspath).joinpath(
                "../res/ori_data/collect_milan/collection",
                "AddCustom_ab1b6750d7f510985325b603cb06dc8b.json",
            ),
            compile_file_path,
        )
        handler = Ascend950Handler()
        build_result = handler.get_compile_file("Ascend950", temp_dir)
        shutil.rmtree(temp_dir)
        assert f"{ModeCustom.ADD_CUSTOM.value}_add_custom.o" in str(build_result[0])
        assert "AddCustom_ab1b6750d7f510985325b603cb06dc8b.json" in str(build_result[1])

        assert res

    @pytest.mark.parametrize(
        "compile_file, log_content",
        [
            (RuntimeError("test"), "Compile dirty_ub op failed, skip dirty ub"),
            ([[]], "Compile dirty_ub op failed, skip dirty ub"),
        ],
    )
    @staticmethod
    def test_run_ascendc_with_diff_soc(
        mocker, monkeypatch, tmp_path, compile_file, log_content
    ):
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
        handler = Ascend950Handler()
        handler.run_dirty_ub(config_file, "Ascend910B1", 0)
        debug_info = tmp_path.joinpath("debug_info.txt")
        assert log_content in debug_info.read_text(encoding="utf-8")
