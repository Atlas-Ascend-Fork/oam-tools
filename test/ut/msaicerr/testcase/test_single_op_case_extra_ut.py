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

import sys
from unittest.mock import Mock

import numpy as np

from conftest import MSAICERR_PATH
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase

sys.path.append(MSAICERR_PATH)

SOC_MODULE = "ms_interface.single_op_test_frame.single_op_case"


def _kernel_data(**kwargs):
    data = {
        "kernel_name": "k",
        "cce_file": "",
        "bin_path": "b.o",
        "json_path": "j.json",
        "tiling_data": "0102",
        "tiling_key": 0,
        "block_dim": 8,
        "device_id": 0,
        "input_file_list": [],
        "output_file_list": [],
        "bin_file_list": [],
        "sub_ptr_addrs": {},
        "ffts_addrs_num": 0,
        "workspace": 0,
    }
    data.update(kwargs)
    return data


def _ctx_runner(mocker, ret="ok"):
    runner = Mock()
    runner.__enter__ = Mock(return_value=runner)
    runner.__exit__ = Mock(return_value=False)
    runner.run.return_value = ret
    mocker.patch(SOC_MODULE + ".AscendOpKernelRunner", return_value=runner)
    return runner


def test_cce_not_exist(mocker):
    mocker.patch("os.path.exists", return_value=False)
    assert SingleOpCase.update_kernel_by_cce("cce", "k") is None


def test_no_ccec_match(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mocker.mock_open(read_data="no comment here"))
    assert SingleOpCase.update_kernel_by_cce("cce", "k") is None


def test_ccec_not_found(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mocker.mock_open(read_data="// ccec a b c -o out.o"))
    mocker.patch("shutil.which", return_value=None)
    mocker.patch("platform.machine", return_value="x86_64")
    assert SingleOpCase.update_kernel_by_cce("cce", "k") is None


def test_update_kernel_run_success(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mocker.mock_open(read_data="// ccec a b c -o out.o"))
    mocker.patch("shutil.which", return_value="/usr/bin/ccec")
    mocker.patch("subprocess.run")
    mocker.patch("os.getcwd", return_value="/work")
    result = SingleOpCase.update_kernel_by_cce("cce", "k")
    assert result.endswith("k_new.o")


def test_read_bin_file(mocker):
    mocker.patch("builtins.open", mocker.mock_open(read_data=b"\x01\x02"))
    assert SingleOpCase.read_bin_file("a.bin") == b"\x01\x02"


def test_get_io_data_list(mocker):
    in_arr = np.ones(4, dtype=np.float16)
    out_arr = np.ones(4, dtype=np.float32)
    mocker.patch("numpy.load", side_effect=[in_arr, out_arr])
    data = {"input_file_list": ["i.npy"], "output_file_list": ["o.npy"]}
    inputs, outputs = SingleOpCase.get_io_data_list(data)
    assert len(inputs) == 1
    assert outputs[0]["dtype"] == "float32"
    assert outputs[0]["shape"] == (4,)


def test_run_kernel_basic(mocker):
    mocker.patch.object(SingleOpCase, "get_io_data_list", return_value=([], []))
    mocker.patch(SOC_MODULE + ".AscendOpKernel", return_value=Mock())
    _ctx_runner(mocker)
    assert SingleOpCase.run_kernel(_kernel_data(), "op_test") == "ok"


def test_run_kernel_bad_device_id(mocker):
    mocker.patch.object(SingleOpCase, "get_io_data_list", return_value=([], []))
    mocker.patch(SOC_MODULE + ".AscendOpKernel", return_value=Mock())
    _ctx_runner(mocker)
    assert SingleOpCase.run_kernel(_kernel_data(device_id="bad"), "op_test") == "ok"


def test_run_kernel_tiling_bin(mocker):
    mocker.patch.object(SingleOpCase, "get_io_data_list", return_value=([], []))
    mocker.patch.object(SingleOpCase, "read_bin_file", return_value=b"\x01")
    mocker.patch(SOC_MODULE + ".AscendOpKernel", return_value=Mock())
    _ctx_runner(mocker)
    assert SingleOpCase.run_kernel(_kernel_data(tiling_data="t.bin"), "op_test") == "ok"


def test_run_no_soc_version(mocker):
    mocker.patch(SOC_MODULE + ".DSMIInterface", side_effect=RuntimeError)
    mocker.patch.object(SingleOpCase, "get_soc_version_from_cce", return_value=None)
    ret = SingleOpCase.run({"cce_file": ""}, "op_test")
    assert "Cannot determine soc_version" in ret


def test_run_full(mocker):
    dsmi = Mock()
    dsmi.get_chip_info.return_value.get_complete_platform.return_value = "Ascend910B"
    mocker.patch(SOC_MODULE + ".DSMIInterface", return_value=dsmi)
    mocker.patch(SOC_MODULE + ".run_dirty_ub")
    mocker.patch.object(SingleOpCase, "run_kernel", return_value="kernel_ok")
    ret = SingleOpCase.run({"cce_file": "", "device_id": 0}, "op_test")
    assert "kernel_ok" in ret


def test_run_bad_device_id(mocker):
    dsmi = Mock()
    dsmi.get_chip_info.return_value.get_complete_platform.return_value = "Ascend910B"
    mocker.patch(SOC_MODULE + ".DSMIInterface", return_value=dsmi)
    mocker.patch(SOC_MODULE + ".run_dirty_ub")
    mocker.patch.object(SingleOpCase, "run_kernel", return_value="kernel_ok")
    ret = SingleOpCase.run({"cce_file": "", "device_id": "bad"}, "op_test")
    assert "kernel_ok" in ret
