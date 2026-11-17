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
from pathlib import Path
import subprocess
import shutil
import inspect
from argparse import Namespace

import pytest

from conftest import MSAICERR_PATH, TEST_CASE_TMP, cur_abspath

sys.path.append(MSAICERR_PATH)
sys.path.append(f"{cur_abspath}/../res/package")
from ms_interface.single_op_test_frame.runtime import AscendRTSApi
from ms_interface.single_op_test_frame.common.ascend_tbe_op import (
    AscendOpKernel,
    AscendOpKernelRunner,
    AscendOpKernelParam,
)
from ms_interface.constant import ModeCustom
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase
from ms_interface.run_dirty_ub import run_dirty_ub


class TestUtilsMethods:
    @staticmethod
    def setup_method(method):
        # 创建临时执行目录
        temp = TEST_CASE_TMP.joinpath(method.__name__)
        if not temp.exists():
            temp.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def teardown_method(method):
        temp = TEST_CASE_TMP.joinpath(method.__name__)
        if temp.exists():
            shutil.rmtree(temp)

    def test_check_file_content_false(self):
        single_op_case = SingleOpCase("collection", "op_test")
        flag = getattr(single_op_case, "_check_file_content")("kernel_name", "content")
        assert not flag

    def test_check_file_content(self):
        single_op_case = SingleOpCase("collection", "op_test")
        flag = getattr(single_op_case, "_check_file_content")(
            "aicore exception", "aicore exception"
        )
        assert flag

    def test_wait_for_log_stabilization(self, mocker):
        mocker.patch("os.path.getsize", return_value=4)
        single_op_case = SingleOpCase("collection", "op_test")
        getattr(single_op_case, "_wait_for_log_stabilization")(
            os.path.join(cur_abspath, "../res/ori_data/complie_path")
        )

    def test_get_cce_file_cce_not_exist(self):
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = "/home/kernel"
        aic_err_info.kernel_name = "kernel_name"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        cce_file = single_op_case.get_cce_file()
        assert not cce_file

    def test_get_cce_file(self, mocker):
        mocker.patch("os.path.exists", return_value=True)
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = "/home/kernel/"
        aic_err_info.kernel_name = "kernel_name"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        cce_file = single_op_case.get_cce_file()
        assert not cce_file

    def test_generate_config(self, mocker):
        mocker.patch.object(
            SingleOpCase, "get_cce_file", return_value="/home/kernel.cce"
        )
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = "/home/kernel/"
        aic_err_info.kernel_name = "kernel_name"
        aic_err_info.block_dim = 0
        data = {
            "cce_file": "/home/kernel.cce",
            "device_id": 0,
            "bin_path": "",
            "json_path": "",
            "tiling_data": "",
            "tiling_key": 0,
            "block_dim": 0,
            "input_file_list": [],
            "output_file_list": [],
            "workspace_file_list": [],
            "bin_file_list": [],
            "kernel_name": "kernel_name",
            "sub_ptr_addrs": {},
            "workspace": 0,
            "ffts_addrs_num": 0,
        }

        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        assert config_file == data

    def test_run_dirty_ub(self, mocker):
        temp_dir = Path(cur_abspath).joinpath("../test_run_dirty_ub")
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        config_file.update({"compile_temp_dir": temp_dir})
        res = subprocess.run([sys.executable, "-c", ""], check=False)
        mocker.patch.object(Path, "exists", return_value=False)
        mocker.patch("shutil.which", return_value=True)
        mocker.patch("subprocess.run", return_value=res)
        mocker.patch.object(AscendOpKernelRunner, "run")
        mocker.patch.object(AscendRTSApi, "_load_runtime_so")
        mocker.patch.object(AscendRTSApi, "register_kernel_launch_fill_func")
        mocker.patch.object(AscendRTSApi, "set_device")
        mocker.patch.object(AscendRTSApi, "create_stream")
        mocker.patch.object(AscendRTSApi, "reset")
        mocker.patch.object(AscendRTSApi, "destroy_stream")
        op_kernel_path = temp_dir.joinpath(ModeCustom.DIRTY_CUSTOM.value, "op_kernel")
        op_kernel_path.mkdir(parents=True, exist_ok=True)
        op_kernel_path.joinpath("add_custom.cpp").write_text("test", encoding="utf-8")
        compile_file_path = temp_dir.joinpath(
            ModeCustom.DIRTY_CUSTOM.value, "build_out", "op_kernel"
        )
        compile_file_path.mkdir(parents=True, exist_ok=True)
        compile_file_path.joinpath(
            f"{ModeCustom.DIRTY_CUSTOM.value}_add_custom.o"
        ).write_text("test", encoding="utf-8")
        shutil.copy(
            Path(cur_abspath).joinpath(
                "../res/ori_data/collect_milan/collection",
                "DirtyCustom_ab1b6750d7f510985325b603cb06dc8b.json",
            ),
            compile_file_path,
        )

        res = run_dirty_ub(config_file, "Ascend910B1", 0)
        assert res

    @pytest.mark.skip
    def test_run(self, mocker):
        temp_dir = os.path.join(cur_abspath, "test_run")
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        config_file.update({"compile_temp_dir": temp_dir})
        run_dirty_ub(config_file, "Ascend910B1", 0)
        mocker.patch.object(SingleOpCase, "run_kernel", return_value=None)
        res = single_op_case.run(config_file, "op_test")
        assert "None" in res

    def test_run_tik(self, monkeypatch, mocker):
        temp_dir = os.path.join(cur_abspath, "test_run_dirty_ub_tik")
        custom_paths = [MSAICERR_PATH, f"{cur_abspath}/../res/package"]
        monkeypatch.setattr(sys, "path", custom_paths)
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        config_file.update({"compile_temp_dir": temp_dir})
        mocker.patch.object(AscendOpKernelRunner, "run", return_value=None)
        mocker.patch.object(AscendOpKernelRunner, "run")
        mocker.patch.object(AscendRTSApi, "_load_runtime_so")
        mocker.patch.object(AscendRTSApi, "register_kernel_launch_fill_func")
        mocker.patch.object(AscendRTSApi, "set_device")
        mocker.patch.object(AscendRTSApi, "create_stream")
        mocker.patch.object(AscendRTSApi, "reset")
        mocker.patch.object(AscendRTSApi, "destroy_stream")
        mocker.patch("tbe.tik.Tik.vec_dup")
        res = run_dirty_ub(config_file, "Ascend910B", 0)
        assert not res

    @pytest.mark.skip
    def test_run_ascend_tbe_op(self, mocker, capsys):
        func_name = inspect.currentframe().f_code.co_name
        compile_temp_dir = TEST_CASE_TMP.joinpath(func_name)
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        config_file.update({"compile_temp_dir": compile_temp_dir})
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("numpy.frombuffer", return_value=0)
        mocker.patch.object(AscendOpKernel, "_parse_json_file")
        mocker.patch.object(AscendRTSApi, "_load_runtime_so")
        mocker.patch.object(AscendRTSApi, "register_kernel_launch_fill_func")
        mocker.patch.object(AscendRTSApi, "set_device")
        mocker.patch.object(AscendRTSApi, "create_stream")
        mocker.patch.object(AscendRTSApi, "reset")
        mocker.patch.object(AscendRTSApi, "destroy_stream")
        mocker.patch.object(
            AscendRTSApi, "get_data_from_hbm", return_value=["0x111", ""]
        )
        mocker.patch.object(AscendOpKernelParam, "concat_into_kernel_args")
        mocker.patch.object(AscendOpKernelParam, "release_device")
        mocker.patch.object(AscendOpKernelRunner, "_fill_inputs")
        mocker.patch.object(AscendOpKernelRunner, "_fill_workspace")
        mocker.patch.object(AscendOpKernelRunner, "_fill_tiling")
        mocker.patch.object(
            AscendOpKernelRunner, "_execute_kernel", return_value=[0, 0]
        )
        mocker.patch.object(
            AscendOpKernelRunner,
            "_create_output_param_with_pages",
            return_value=Namespace(
                origin_pointer=1,
                magic_pointer=1,
                concat_into_kernel_args=AscendOpKernelParam.concat_into_kernel_args,
                release_device=AscendOpKernelParam.release_device,
            ),
        )
        output_info = {"size": 4, "dtype": "float32", "shape": (1,)}
        mocker.patch.object(
            SingleOpCase, "get_io_data_list", return_value=[[], [output_info]]
        )
        single_op_case.run(config_file, "op_test")
        assert "single op case success" in capsys.readouterr().out

    @pytest.mark.skip
    def test_run_ascend_tbe_op_eq_magic(self, mocker, capsys):
        func_name = inspect.currentframe().f_code.co_name
        compile_temp_dir = TEST_CASE_TMP.joinpath(func_name)
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        config_file.update({"compile_temp_dir": compile_temp_dir})
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(AscendOpKernel, "_parse_json_file")
        mocker.patch.object(AscendRTSApi, "_load_runtime_so")
        mocker.patch.object(AscendRTSApi, "register_kernel_launch_fill_func")
        mocker.patch.object(AscendRTSApi, "set_device")
        mocker.patch.object(AscendRTSApi, "create_stream")
        mocker.patch.object(AscendRTSApi, "reset")
        mocker.patch.object(AscendRTSApi, "destroy_stream")
        mocker.patch.object(
            AscendRTSApi, "get_data_from_hbm", return_value=[b"\x55", ""]
        )
        mocker.patch.object(AscendOpKernelParam, "concat_into_kernel_args")
        mocker.patch.object(AscendOpKernelParam, "release_device")
        mocker.patch.object(AscendOpKernelRunner, "_fill_inputs")
        mocker.patch.object(AscendOpKernelRunner, "_fill_workspace")
        mocker.patch.object(AscendOpKernelRunner, "_fill_tiling")
        mocker.patch.object(
            AscendOpKernelRunner, "_execute_kernel", return_value=[0, 0]
        )
        mocker.patch.object(
            AscendOpKernelRunner,
            "_create_output_param_with_pages",
            return_value=Namespace(
                origin_pointer=1,
                magic_pointer=1,
                concat_into_kernel_args=AscendOpKernelParam.concat_into_kernel_args,
                release_device=AscendOpKernelParam.release_device,
            ),
        )
        output_info = {"size": 4, "dtype": "float32", "shape": (1,)}
        mocker.patch.object(
            SingleOpCase, "get_io_data_list", return_value=[[], [output_info]]
        )
        single_op_case.run(config_file, "op_test")
        assert "single op case success" in capsys.readouterr().out
