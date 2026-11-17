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
import shutil
from pathlib import Path

import pytest

from conftest import MSAICERR_PATH, TEST_CASE_TMP, cur_abspath

sys.path.append(MSAICERR_PATH)
sys.path.append(f"{cur_abspath}/../res/package")

from ms_interface.ascend950.compile_op import CompileOP
from ms_interface.single_op_test_frame.runtime import AscendRTSApi
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase
from ms_interface.run_dirty_ub import run_dirty_ub
from ms_interface.dsmi_interface import DSMIInterface


def _detect_soc_version():
    try:
        info = DSMIInterface().get_chip_info(0)
        if info is None:
            return None
        return info.get_complete_platform()
    # DSMIInterface() 走 ctypes.CDLL -> OSError；get_complete_platform 走 .decode()
    except (OSError, AttributeError, UnicodeDecodeError):
        return None


_soc = _detect_soc_version()
if _soc is None or "950" not in str(_soc):
    pytest.skip(
        f"test_single_op_case_st_ascend950 requires an Ascend950 host "
        f"(detected SOC: {_soc!r}); skipping module.",
        allow_module_level=True,
    )


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

    def test_run(self, mocker):
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        run_dirty_ub(config_file, "Ascend950", 0)
        mocker.patch(
            "ms_interface.single_op_test_frame.single_op_case.run_dirty_ub",
            return_value=True,
        )
        mocker.patch(
            "ms_interface.single_op_test_frame.single_op_case.DSMIInterface",
            side_effect=Exception("mock dsmi unavailable"),
        )
        mocker.patch.object(
            SingleOpCase, "get_soc_version_from_cce", return_value="Ascend950"
        )
        mocker.patch.object(SingleOpCase, "run_kernel", return_value=None)
        res = single_op_case.run(config_file, "op_test")
        assert "None" in res

    @pytest.mark.parametrize(
        "compile_file, log_content",
        [
            (
                [
                    [
                        "test.o",
                        os.path.join(
                            cur_abspath,
                            "../res/ori_data/collect_milan/collection/DirtyCustom_ab1b6750d7f510985325b603cb06dc8b.json",
                        ),
                    ]
                ],
                "Find bin_file test.o and json_file",
            ),
            (Exception("test"), "Compile dirty_ub op failed, skip dirty ub"),
            ([[]], "Compile dirty_ub op failed, skip dirty ub"),
        ],
    )
    @staticmethod
    def test_run_ascendc(mocker, compile_file, log_content):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(AscendOpKernelRunner, "run", return_value=None)
        mocker.patch.object(AscendOpKernelRunner, "run")
        mocker.patch.object(AscendRTSApi, "_load_runtime_so")
        mocker.patch.object(AscendRTSApi, "register_kernel_launch_fill_func")
        mocker.patch.object(AscendRTSApi, "set_device")
        mocker.patch.object(AscendRTSApi, "create_stream")
        mocker.patch.object(AscendRTSApi, "reset")
        mocker.patch.object(AscendRTSApi, "destroy_stream")
        mocker.patch.object(CompileOP, "get_ub_size", return_value=1)
        mocker.patch.object(CompileOP, "get_compile_file", side_effect=compile_file)
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        run_dirty_ub(config_file, "Ascend950", 0)
        debug_info = Path(f"{os.getcwd()}/debug_info.txt")
        assert log_content in debug_info.read_text(encoding="utf-8")
