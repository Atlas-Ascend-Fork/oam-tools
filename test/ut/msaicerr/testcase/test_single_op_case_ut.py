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


from conftest import MSAICERR_PATH, cur_abspath, ori_data_path
import os
import sys
import pytest
from unittest.mock import Mock

from ms_interface.single_op_test_frame.runtime import AscendRTSApi
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase
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

    def test_run_dirty_ub_tik(self, monkeypatch, mocker):
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
        self.common_mock(mocker)
        mocker.patch("tbe.tik.Tik.vec_dup")
        res = run_dirty_ub(config_file, "Ascend910B", 0)
        assert not res

    def test_run(self, mocker):
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        mocker.patch("ms_interface.run_dirty_ub.run_dirty_ub_tik", return_value=None)
        mocker.patch.object(SingleOpCase, "run_kernel", return_value=None)
        res = single_op_case.run(config_file, "op_test")
        assert "None" in res

    def test_search_aicerr_log(self):
        res = SingleOpCase.search_aicerr_log(
            "kernel_name", ori_data_path.joinpath("collect_milan")
        )
        assert res is True
        res = SingleOpCase.search_aicerr_log(
            "xxxxxxx", ori_data_path.joinpath("collect_milan")
        )
        assert res is False

    @pytest.mark.parametrize(
        "soc_version, res_version",
        [
            ("AscendBeta_V1", "AscendBeta_V1"),
            ("Ascend910B", "Ascend910B1"),
            ("Ascend310B", "Ascend310B1"),
        ],
    )
    def test_get_soc_version_from_cce(self, mocker, soc_version, res_version):
        mock_data = f'// test {soc_version}"'
        mock_open = mocker.mock_open(read_data=mock_data)
        mocker.patch("builtins.open", mock_open)
        res = SingleOpCase.get_soc_version_from_cce("cce_file")
        assert res == res_version

    @staticmethod
    def test_get_soc_version_from_cce_none():
        # config 缺 cce_file 字段时传入 None，open(None) 抛 TypeError，
        # 须与读文件失败一样回退默认芯片版本，不能让用例进程直接退出。
        res = SingleOpCase.get_soc_version_from_cce(None)
        assert res == "Ascend310"

    def test_get_soc_version_from_cce_310(self, mocker):
        res = SingleOpCase.get_soc_version_from_cce("cce_file")
        assert res == "Ascend310"

        mock_data = '// test xxx"'
        mock_open = mocker.mock_open(read_data=mock_data)
        mocker.patch("builtins.open", mock_open)
        res = SingleOpCase.get_soc_version_from_cce("cce_file")
        assert res == "Ascend310"

    @pytest.mark.skip
    def test_update_kernel_by_cce(self, mocker):
        res = SingleOpCase.update_kernel_by_cce("cce_file", "kernel_name")
        assert res is None

        mocker.patch("os.path.exists", return_value=True)
        mock_data = '// test xxx"'
        mock_open = mocker.mock_open(read_data=mock_data)
        mocker.patch("builtins.open", mock_open)
        res = SingleOpCase.update_kernel_by_cce("cce_file", "kernel_name")
        assert res is None

        mocker.patch("re.findall", return_value=[])
        res = SingleOpCase.update_kernel_by_cce("cce_file", "kernel_name")
        assert res is None

    def test_get_io_data_list(self, mocker):
        data = {"input_file_list": ["file1"], "output_file_list": ["file1"]}
        mocker.patch("numpy.load", return_value=Mock())
        res = SingleOpCase.get_io_data_list(data)
        assert len(res) == 2
