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

from ms_interface.single_op_test_frame.runtime import AscendRTSApi as RTSApi
from ms_interface.single_op_test_frame.common import ascend_tbe_op
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelParam
from ms_interface.single_op_test_frame.common.ascend_tbe_op import (
    AscendOpKernelRunnerParam,
)
from conftest import MSAICERR_PATH, CommonAssert
import sys
import ctypes
from typing import Union
from unittest.mock import Mock, mock_open
import numpy as np
import pytest

s = np.array([1, 2, 3, 4, 5])
sys.path.append(MSAICERR_PATH)


class AscendRTSApi:
    """
    Class AscendRTSApi
    """

    def __init__(
        self,
        _simulator_mode: str = None,
        _soc_version: str = None,
        _simulator_lib_path: str = None,
        simulator_dump_path: str = "./model",
    ):
        self.rtsdll = None
        # 记录入参供用例断言（也避免桩参数未使用）
        self.simulator_dump_path = simulator_dump_path
        self.last_memcpy = {}

    def malloc(self, memory_size: int) -> ctypes.c_void_p:
        c_memory_p = ctypes.c_void_p(memory_size)
        return c_memory_p

    @staticmethod
    def free(_c_memory_p: ctypes.c_void_p):
        return ctypes.c_void_p(None)

    def memcpy(
        self,
        _c_memory_p: ctypes.c_void_p,
        _memory_size: int,
        _data: Union[bytes, ctypes.c_void_p],
        _data_size: int,
        memcpy_kind: str = "RT_MEMCPY_HOST_TO_HOST",
        retry_count: int = 0,
    ):
        self.last_memcpy = {"kind": memcpy_kind, "retry": retry_count}
        return

    def get_c2c_ctrl_addr(self):
        return ctypes.c_void_p(None)


class AscendOpKernel:
    """
    Class AscendOpKernel
    """

    PageMemorySize = 0x200000  # 内存页大小
    MagicMemorySize = 0x80  # 前后各128个魔术字：0x55
    MagicData = 0x55
    ForwardDestroy = 1
    BackwardDestroy = 2

    def __init__(self, _bin_path: str, _json_path: str):
        self.block_dim = 8


class ChipInfoStub:
    def get_complete_platform(self):
        return "Ascend310"


@pytest.fixture(name="mock_runner")
def _mock_runner(mocker):
    api_mock = Mock()
    api_mock.return_value = 1
    out_hbm_pointer_mock = Mock()
    out_hbm_pointer_mock.value = 1
    api_mock.malloc.return_value = out_hbm_pointer_mock
    api_mock.memcpy.return_value = None
    api_mock.get_data_from_hbm.return_value = (b"xxx", 0)
    mocker.patch.object(AscendOpKernelRunner, "get_rts_api", return_value=api_mock)
    runner = AscendOpKernelRunner()
    return runner


class TestClassAscendOpKernelRunner(CommonAssert):
    def test_exec_single_case(self, mocker):
        kernel = AscendOpKernel("", "")
        mocker.patch.object(AscendOpKernelRunner, "__init__", return_value=None)
        mocker.patch.object(AscendOpKernelRunner, "_fill_binary", return_value=None)
        mocker.patch.object(AscendOpKernelRunner, "_fill_tiling", return_value=None)
        mocker.patch.object(
            AscendOpKernelRunner, "_execute_kernel", return_value=[0, 0]
        )
        mocker.patch.object(AscendOpKernelRunner, "_check_magic_memory", return_value=0)
        runner = AscendOpKernelRunner()
        ascend_op_param = AscendOpKernelRunnerParam(
            kernel=kernel,
            inputs=None,
            output_input_ref=None,
            tiling_data=None,
            block_dim=8,
            actual_out_info=None,
            bin_list=True,
            sub_ptr_addrs=None,
            ffts_addrs_num=0,
            workspace=0,
            op_test="",
        )
        ret_value = runner.exec_single_case(ascend_op_param)
        self.assertEqual(ret_value, [[], [0, 0, 0]])

    def test_execute_kernel(self, mocker, mock_runner):
        api_mock = Mock()
        api_mock.register_kernel_launch_fill_func.side_effect = None
        mocker.patch.object(RTSApi, "_load_runtime_so", return_value=None)
        runner = mock_runner
        runner.profiling = True
        kernel_mock = Mock()
        kernel_mock.is_registered_to_device.return_value = False
        res = getattr(runner, "_execute_kernel")(kernel_mock, [1, 1], 1, "xxx")
        assert isinstance(res, list)

    def test_fill_workspace(self, mocker, mock_runner):
        kernel_mock = Mock()
        wksp_hbm_pointers = []
        kernel_args = []
        mode = "tail"
        runner = mock_runner

        kernel_mock.workspace = [1]
        kernel_mock.parameters = [
            {"dtype": "int8", "init_value": 1},
            None,
            None,
            None,
            None,
        ]
        sync_to_device_spy = mocker.spy(AscendOpKernelParam, "sync_to_device")
        getattr(runner, "_fill_workspace")(
            kernel_mock, 0, wksp_hbm_pointers, kernel_args, mode
        )
        assert sync_to_device_spy.call_count == 1
        assert len(wksp_hbm_pointers) == 1
        assert len(kernel_args) == 1
        assert wksp_hbm_pointers[0] is runner.ascend_device.malloc.return_value
        assert kernel_args[0].value == 1

    @staticmethod
    def test_fill_workspace_no_parameter(mocker, mock_runner):
        sync_to_device_spy = mocker.spy(AscendOpKernelParam, "sync_to_device")
        kernel_mock = Mock()
        kernel_mock.workspace = [-1]
        kernel_mock.parameters = [None, None, None, None, None]
        wksp_hbm_pointers = []
        kernel_args = []
        mode = "tail"
        runner = mock_runner
        getattr(runner, "_fill_workspace")(
            kernel_mock, 0, wksp_hbm_pointers, kernel_args, mode
        )
        assert sync_to_device_spy.call_count == 1
        assert len(wksp_hbm_pointers) == 1
        assert len(kernel_args) == 1
        assert wksp_hbm_pointers[0] is kernel_args[0]
        assert wksp_hbm_pointers[0] is runner.ascend_device.malloc.return_value
        runner.ascend_device.malloc.assert_called_once_with(0x400)

    def test_fill_binary_subptr_no_args_list(self, mocker, mock_runner):
        mocker.patch.object(AscendOpKernelParam, "sync_to_device", return_value=None)
        runner = mock_runner
        getattr(runner, "_fill_binary_subptr")(["xxx"], 1, [], {}, "magic")

    @staticmethod
    def test_fill_binary_subptr(mocker, mock_runner):
        # 必须用 mock_runner：该 fixture patch 了 get_rts_api，否则 __init__ 会去
        # dlopen 真实 libruntime.so，用例退化为依赖环境的测试（本地有 so 就过、
        # 云端没有就抛 RuntimeError）。
        mock_data = b"\xde\xad\xbe\xef"
        open_mock = mocker.mock_open(read_data=mock_data)
        mocker.patch("builtins.open", open_mock)
        assert (
            getattr(mock_runner, "_fill_binary_subptr")(
                ["xxx"], 1, [], {"args_list": ["1"]}, "magic"
            )
            is None
        )

    @staticmethod
    def test_create_output_param_with_pages_no_param(mock_runner):
        kernel_mock = Mock()
        kernel_mock.workspace = []
        kernel_mock.parameters = [None]
        mode = "tail"
        data_list = [{"size": 4, "dtype": "float32", "shape": (1,)}, [], (1,)]
        runner = mock_runner
        res = getattr(runner, "_create_output_param_with_pages")(
            kernel_mock, data_list, mode
        )
        assert isinstance(res, AscendOpKernelParam)

    @staticmethod
    def test_create_output_param_with_pages(mock_runner):
        kernel_mock = Mock()
        kernel_mock.workspace = [-1]
        kernel_mock.parameters = [{"dtype": "int8", "init_value": 1}]
        data_list = [{"size": 4, "dtype": "float32", "shape": (1,)}, [], (1,)]
        mode = "tail"
        runner = mock_runner
        res = getattr(runner, "_create_output_param_with_pages")(
            kernel_mock, data_list, mode
        )
        assert isinstance(res, AscendOpKernelParam)

    def test_fill_inputs(self, mocker, mock_runner):
        runner = mock_runner

        inputs = [AscendOpKernelParam(np_data=np.zeros(1))]
        getattr(runner, "_fill_inputs")(inputs, [], [], "tail")

        inputs = ["xxx.npy"]
        mocker.patch("numpy.load", return_value=np.zeros(1))
        getattr(runner, "_fill_inputs")(inputs, [], [], "tail")

        inputs = ["file_path"]
        mocker.patch.object(
            AscendOpKernelParam, "build_op_param_by_data_file", return_value=Mock()
        )
        getattr(runner, "_fill_inputs")(inputs, [], [], "tail")

    @staticmethod
    def test_fill_outputs(mock_runner):
        kernel_mock = Mock()
        kernel_mock.workspace = [-1]
        kernel_mock.parameters = [{"dtype": "int8", "init_value": 1}]
        runner = mock_runner
        output_input_ref = ()
        actual_output_info = ({"size": 4, "dtype": "float32", "shape": (1,)},)
        output_params = []
        kernel_args = []
        input_params = []
        res = getattr(runner, "_fill_outputs")(
            kernel_mock,
            output_input_ref,
            actual_output_info,
            input_params,
            output_params,
            kernel_args,
            "tail",
        )
        assert res is None

    @staticmethod
    def test_fill_tiling(mock_runner):
        runner = mock_runner
        kernel_mock = Mock()
        getattr(runner, "_fill_tiling")(kernel_mock, b"xx", [], [])

        kernel_mock.need_do_tiling = False
        getattr(runner, "_fill_tiling")(kernel_mock, b"xx", [], [])

        getattr(runner, "_fill_tiling")(Mock(), None, [], [])

    def test_check_magic_memory(self, mocker, mock_runner):
        runner = mock_runner
        setattr(runner, "_kernel_params", [Mock()])
        assert getattr(runner, "_check_magic_memory")() == 1
        mocker.patch.object(runner, "_check_magic", side_effect=[False, True])
        assert getattr(runner, "_check_magic_memory")() == 2
        mocker.patch.object(runner, "_check_magic", return_value=False)
        assert getattr(runner, "_check_magic_memory")() == 0

    def test_build_op_param_by_data_file(self, mocker):
        with pytest.raises(IOError):
            AscendOpKernelParam.build_op_param_by_data_file("xxx", "int8", [1, 1])

        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("numpy.fromfile", return_value=np.zeros(1))
        res = AscendOpKernelParam.build_op_param_by_data_file("xxx", "int8", [1, 1])
        assert isinstance(res, AscendOpKernelParam)

        mocker.patch(
            "ms_interface.single_op_test_frame.utils.shape_utils.calc_shape_size",
            return_value=-1,
        )
        with pytest.raises(RuntimeError):
            AscendOpKernelParam.build_op_param_by_data_file("xxx", "int8", [1, 1])

        mocker.patch(
            "ms_interface.single_op_test_frame.utils.shape_utils.calc_shape_size",
            return_value=2,
        )
        with pytest.raises(RuntimeError):
            AscendOpKernelParam.build_op_param_by_data_file("xxx", "int8", [1, 1])

    def test_ascend_op_kernel_param_v2_dtype(self):
        np_data = np.zeros((2, 3), dtype="V2")
        param = AscendOpKernelParam(np_data=np_data)
        self.assertEqual(param.dtype, "float16")
        self.assertEqual(param.shape, (2, 3))

    def test_hbm_pointer_case(self, mocker):
        c_memory_p = ctypes.c_void_p(None)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(None, (0,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, "__init__", return_value=None)
        res = runner.hbm_pointer.value
        self.assertEqual(res, 1024)

    def test_sync_to_device_case1(self, mocker):
        c_memory_p = ctypes.c_void_p(None)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(s, (1,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, "__init__", return_value=None)
        runner.sync_to_device(kernel, "tail")

    def test_sync_to_device_case(self, mocker):
        c_memory_p = ctypes.c_void_p(None)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(None, (0,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, "__init__", return_value=None)
        runner.sync_to_device(kernel, "tail")

    def test_is_in_device_case(self, mocker):
        c_memory_p = ctypes.c_void_p(10)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(None, (0,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, "__init__", return_value=None)
        res = runner.is_in_device()
        self.assertEqual(res, True)

    def test_release_device_case(self, mocker):
        c_memory_p = ctypes.c_void_p(10)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(None, (1,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, "__init__", return_value=None)
        runner.sync_to_device(kernel, "tail")
        runner.release_device()

    def test_run(self, mocker):
        mocker.patch.object(AscendOpKernelRunner, "__init__", return_value=None)
        runner = AscendOpKernelRunner()
        kernel = AscendOpKernel("", "")
        mocker.patch.object(
            AscendOpKernelRunner, "exec_single_case", return_value=[0, [0, 0, 0]]
        )
        ret_value = runner.run(kernel)
        self.assertEqual(True, "exec single op case success" in ret_value)
        mocker.patch.object(
            AscendOpKernelRunner, "exec_single_case", return_value=[0, [1, 0, 0]]
        )
        ret_value = runner.run(kernel)
        self.assertEqual(True, "exec single op case failed" in ret_value)
        mocker.patch.object(
            AscendOpKernelRunner, "exec_single_case", return_value=[0, [0, 0, 1]]
        )
        ret_value = runner.run(kernel)
        self.assertEqual(True, "memory status check" in ret_value)
        mocker.patch.object(
            AscendOpKernelRunner, "exec_single_case", return_value=[0, [0, 0, 2]]
        )
        ret_value = runner.run(kernel)
        self.assertEqual(True, "memory status check" in ret_value)

    def test_run_exec_failed_with_memory_status(self, mocker):
        mocker.patch.object(AscendOpKernelRunner, "__init__", return_value=None)
        runner = AscendOpKernelRunner()
        mocker.patch.object(
            runner,
            "exec_single_case",
            side_effect=[
                [None, [1, 0, 0]],
                [None, [0, 0, 2]],
            ],
        )
        ret_value = runner.run(Mock())
        self.assertEqual(True, "exec single op case failed." in ret_value)
        self.assertEqual(True, "launch kernel result : 1." in ret_value)
        self.assertEqual(True, "execute result : 0." in ret_value)
        self.assertEqual(True, "memory status check result : 2." in ret_value)

    def test_fill_binary(self, mocker):
        mocker.patch.object(ascend_tbe_op.DSMIInterface, "__init__", return_value=None)
        mocker.patch.object(
            ascend_tbe_op.DSMIInterface, "get_chip_info", return_value=ChipInfoStub()
        )
        mocker.patch.object(AscendOpKernelRunner, "__init__", return_value=None)
        runner = AscendOpKernelRunner()
        runner.ascend_device = None
        setattr(runner, "_kernel_params", [])
        mocker.patch("builtins.open", new_callable=mock_open, read_data=b"\x00")
        c_memory_p = ctypes.c_void_p(None)
        kernel = AscendRTSApi()
        runner1 = AscendOpKernelParam(s, (1,), "float32", kernel, c_memory_p)
        mocker.patch.object(
            AscendOpKernelParam, "build_op_param_by_np_data", return_value=runner1
        )
        mocker.patch.object(runner1, "sync_to_device", return_value=None)
        getattr(runner, "_fill_binary")("./", [], [], {}, "")

    def test_read_tensor_bytes(self, tmp_path):
        """dump解析出的npy需经numpy加载，bin按原始字节读取"""
        bin_file = tmp_path.joinpath("k.input.0.int4.bin")
        bin_file.write_bytes(b"\x01\x02\x03\x04")
        self.assertEqual(
            getattr(AscendOpKernelRunner, "_read_tensor_bytes")(str(bin_file)),
            b"\x01\x02\x03\x04",
        )

        array = np.arange(4, dtype=np.float32)
        npy_file = tmp_path.joinpath("k.input.1.float32.npy")
        np.save(str(npy_file), array)
        data = getattr(AscendOpKernelRunner, "_read_tensor_bytes")(str(npy_file))
        self.assertEqual(data, array.tobytes())
        # npy头不能被当作tensor数据
        assert len(npy_file.read_bytes()) > len(data)

    def test_read_tensor_bytes_npy_unregistered_dtype(self, tmp_path):
        """回放环境缺失dtype扩展时跳过npy头取原始数据，不直接失败"""
        array = np.arange(4, dtype=np.int16)
        npy_file = tmp_path.joinpath("k.input.0.bfloat16.npy")
        np.save(str(npy_file), array)
        raw = bytearray(npy_file.read_bytes())
        header_len = int.from_bytes(raw[8:10], "little")
        header = bytes(raw[10 : 10 + header_len])
        body = bytes(raw[10 + header_len :])
        real_descr = header.split(b"'descr': ")[1].split(b",")[0]
        new_header = header.replace(real_descr, b"'bfloat16'").rstrip(b" \n")
        new_header = new_header + b" " * (header_len - len(new_header) - 1) + b"\n"
        npy_file.write_bytes(bytes(raw[:10]) + new_header + body)
        self.assertEqual(
            getattr(AscendOpKernelRunner, "_read_tensor_bytes")(str(npy_file)),
            array.tobytes(),
        )

    def test_get_tensor_index(self):
        """从dump文件名解析tensor下标"""
        self.assertEqual(
            getattr(AscendOpKernelRunner, "_get_tensor_index")("k.input.0.float32.npy"),
            0,
        )
        self.assertEqual(
            getattr(AscendOpKernelRunner, "_get_tensor_index")("k.input.11.int4.bin"),
            11,
        )
        self.assertEqual(
            getattr(AscendOpKernelRunner, "_get_tensor_index")("k.input.2.bin"), 2
        )
        self.assertEqual(
            getattr(AscendOpKernelRunner, "_get_tensor_index")("no_index.npy"), -1
        )
        # dtype枚举未知时dtype段为纯数字，不能被当成下标
        self.assertEqual(
            getattr(AscendOpKernelRunner, "_get_tensor_index")("k.input.0.99.bin"), 0
        )
        # kernel名自身含数字段
        self.assertEqual(
            getattr(AscendOpKernelRunner, "_get_tensor_index")(
                "exception_info.2.1.20250609144925349.input.0.99.bin"
            ),
            0,
        )
