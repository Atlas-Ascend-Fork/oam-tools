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
import subprocess
import sys
import shutil
from pathlib import Path

# conftest 已把 MSAICERR_PATH 加入 sys.path，且其导入早于下面的 ms_interface
from conftest import MSAICERR_PATH, RES_PATH
from ms_interface.constant import ModeCustom
from ms_interface.golden_op import GoldenOp
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner
from ms_interface.single_op_test_frame.runtime import AscendRTSApi

cur_abspath = os.path.dirname(__file__)


class TestGoldenOp:
    @staticmethod
    def test_run_golden(monkeypatch, mocker):
        custom_paths = [MSAICERR_PATH, f"{RES_PATH}/package"]
        monkeypatch.setattr(sys, "path", custom_paths)
        mocker.patch.object(
            AscendOpKernelRunner, "run", return_value="exec single op case success.\r\n"
        )
        mocker.patch.object(AscendRTSApi, "_load_runtime_so")
        mocker.patch.object(AscendRTSApi, "register_kernel_launch_fill_func")
        mocker.patch.object(AscendRTSApi, "set_device")
        mocker.patch.object(AscendRTSApi, "create_stream")
        mocker.patch.object(AscendRTSApi, "reset")
        mocker.patch.object(AscendRTSApi, "destroy_stream")
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
        res = GoldenOp().run_golden_op("Ascend910B4", 0, temp_dir)
        shutil.rmtree(temp_dir)
        assert res
