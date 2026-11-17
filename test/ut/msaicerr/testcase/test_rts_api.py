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

from ms_interface.single_op_test_frame.runtime.rts_api import AscendRTSApi
from conftest import MSAICERR_PATH
import os
import pytest
import sys
import ctypes
from unittest.mock import Mock

te = Mock(name="te")
te.__name__ = "te"
sys.modules["te"] = te
sys.path.append(MSAICERR_PATH)


@pytest.fixture(name="rts_api")
def _rts_api(mocker):
    mocker.patch.object(AscendRTSApi, "_load_runtime_so", return_value=None)
    rtsapi = AscendRTSApi()
    rtsapi.rtsdll = Mock()
    return rtsapi


@pytest.fixture(name="mdata")
def _mdata():
    return {"1": 1}


class TestClassAscendOpKernelRunner:
    @staticmethod
    def test_parse_error_includes_api_name_in_error_log(mocker, rts_api):
        mock_print_error = mocker.patch("ms_interface.utils.print_error_log")
        rts_api.parse_error(0x07010000, "rtStreamDestroy")
        mock_print_error.assert_called_once()
        assert "rtStreamDestroy" in mock_print_error.call_args[0][0]

    @staticmethod
    def test_get_c2c_ctrl_addr_without_api_call(mocker):
        mocker.patch.object(AscendRTSApi, "__init__", return_value=None)
        rtsapi = AscendRTSApi()
        mocker.patch.object(AscendRTSApi, "api_call", return_value=None)
        res = rtsapi.get_c2c_ctrl_addr()
        assert res.value is None

    def test_register_kernel_launch_fill_func(self, mocker):
        mocker.patch.object(AscendRTSApi, "__init__", return_value=None)
        rtsapi = AscendRTSApi()
        mock_rtsdll = Mock()
        rtsapi.rtsdll = mock_rtsdll

        mock_rtsdll.rtRegKernelLaunchFillFunc.return_value = 0
        rtsapi.register_kernel_launch_fill_func()

        mock_rtsdll.rtRegKernelLaunchFillFunc.return_value = 207000
        rtsapi.register_kernel_launch_fill_func()

        mock_rtsdll.rtRegKernelLaunchFillFunc.return_value = -1
        rtsapi.register_kernel_launch_fill_func()

        rtsapi.update_op_system_run_cfg_callback(None, 10)

        mock_rtsdll.rtGetDevice.return_value = 1
        assert rtsapi.update_op_system_run_cfg_callback(1, 10) == 1

        mock_rtsdll.rtGetDevice.return_value = 0
        mock_rtsdll.rtGetL2CacheOffset.return_value = 207000
        assert rtsapi.update_op_system_run_cfg_callback(1, 10) == 207000

        mock_rtsdll.rtGetDevice.return_value = 0
        mock_rtsdll.rtGetL2CacheOffset.return_value = 1
        assert rtsapi.update_op_system_run_cfg_callback(1, 10) == 1

        mock_rtsdll.rtGetDevice.return_value = 0
        mock_rtsdll.rtGetL2CacheOffset.return_value = 0
        mocker.patch.object(ctypes, "cast", return_value=[0])
        assert rtsapi.update_op_system_run_cfg_callback(1, 10) == 0

    @pytest.mark.parametrize(
        "rt_error", [ctypes.c_uint64(0), ctypes.c_uint64(1), 0x07000000]
    )
    @staticmethod
    def test_parse_error(rts_api, rt_error):
        res = rts_api.parse_error(rt_error, "rtStreamDestroy")
        assert res is None

    def test_parse_error_invalid(self, rts_api):
        with pytest.raises(TypeError):
            rts_api.parse_error("xxx", "rtStreamDestroy")

    def test_load_runtime_so(self, mocker):
        mock_environ = {"LD_LIBRARY_PATH": "/mock/lib/path"}
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.dict(os.environ, mock_environ, clear=False)
        mocker.patch("ctypes.CDLL", return_value=Mock())
        rtsapi = AscendRTSApi()
        assert getattr(rtsapi, "_load_runtime_so")() is None

    def test_memcpy(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtMemcpy", return_value=0)
        assert rts_api.memcpy(ctypes.c_void_p(0), 1, b"0x00", 1) is None

        assert rts_api.memcpy(ctypes.c_void_p(0), 10, ctypes.c_void_p(0), 10) is None

    def test_memcpy_failed(self, mocker, rts_api):
        mocker.patch.object(rts_api, "parse_error", side_effect=RuntimeError("test"))
        mocker.patch.object(rts_api.rtsdll, "rtMemcpy", return_value=0)
        try:
            rts_api.memcpy(ctypes.c_void_p(0), 1, b"0x00", 1)
        except RuntimeError:
            assert True
        else:
            assert False

    def test_init_simulator_so_path(self, mocker, rts_api):
        with pytest.raises(RuntimeError):
            getattr(rts_api, "_init_simulator_so_path")(
                "pv", "soc_version", "/lib/path"
            )

        mocker.patch("os.path.exists", return_value=True)
        so_full_path_list, addition_ld_lib_path = getattr(
            rts_api, "_init_simulator_so_path"
        )("pv", "soc_version", "/lib/path")
        assert len(so_full_path_list) == 4
        assert (
            addition_ld_lib_path
            == "/usr/lib/path/soc_version/lib:/usr/lib/path/common/data"
        )

        with pytest.raises(RuntimeError):
            mocker.patch("os.path.exists", side_effect=[True, False, False])
            getattr(rts_api, "_init_simulator_so_path")(
                "pv", "soc_version", "/lib/path"
            )

    def test_dll_simulator_so(self, mocker, rts_api):
        mock_environ = {"LD_LIBRARY_PATH": "/mock/lib/path"}
        mocker.patch.dict(os.environ, mock_environ, clear=False)
        setattr(rts_api, "_simulator_dlls", [])

        with pytest.raises(RuntimeError):
            mocker.patch("ctypes.CDLL", side_effect=[OSError(), Mock()])
            getattr(rts_api, "_dll_simulator_so")(
                ["so_path1", "so_path1"], "ld_lib_paths", "simulator_dump_path"
            )

        with pytest.raises(RuntimeError):
            mocker.patch("ctypes.CDLL", side_effect=[Mock(), OSError()])
            getattr(rts_api, "_dll_simulator_so")(
                ["so_path1", "so_path1"], "ld_lib_paths", "simulator_dump_path"
            )

        mocker.patch("ctypes.CDLL", return_value=Mock())
        assert (
            getattr(rts_api, "_dll_simulator_so")(
                ["so_path1", "so_path1"], "ld_lib_paths", "simulator_dump_path"
            )
            is None
        )

    def test_load_simulator_so(self, mocker, rts_api):
        with pytest.raises(TypeError):
            getattr(rts_api, "_load_simulator_so")()

        with pytest.raises(ValueError):
            getattr(rts_api, "_load_simulator_so")("simulator_mode")

        with pytest.raises(RuntimeError):
            getattr(rts_api, "_load_simulator_so")("pv")

        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(
            rts_api, "_init_simulator_so_path", return_value=(Mock(), Mock())
        )
        mocker.patch.object(rts_api, "_dll_simulator_so", return_value=None)
        getattr(rts_api, "_load_simulator_so")("pv", simulator_lib_path="/lib/path")

    def test_get_device_info(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtGetDeviceInfo", return_value=0)
        res = rts_api.get_device_info(0, "MODULE_TYPE_SYSTEM", "INFO_TYPE_ENV")
        assert res == "FPGA"

    def test_create_context(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtCtxCreate", return_value=0)
        rts_api.device_id = 0
        res = rts_api.create_context("RT_CTX_NORMAL_MODE")
        assert isinstance(res, ctypes.c_void_p)

    def test_destroy_context(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtCtxDestroy", return_value=0)
        ptr = ctypes.c_void_p(0)

        with pytest.raises(ValueError):
            rts_api.destroy_context()

        with pytest.raises(ValueError):
            rts_api.destroy_context(ptr)

        rts_api.context_storage = [ptr]
        assert rts_api.destroy_context(ptr) is None

    def test_set_context(self, mocker, rts_api):
        ptr = ctypes.c_void_p(0)
        with pytest.raises(ValueError):
            rts_api.set_context(ptr)

        mocker.patch.object(rts_api.rtsdll, "rtCtxSetCurrent", return_value=0)
        rts_api.context_storage = [ptr]
        assert rts_api.set_context(ptr) is None

    def test_create_stream(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtStreamCreate", return_value=0)
        res = rts_api.create_stream()
        assert isinstance(res, ctypes.c_void_p)

    def test_destroy_stream(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtStreamDestroy", return_value=0)
        assert rts_api.destroy_stream(ctypes.c_void_p(0)) is None

    def test_register_device_binary_kernel(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtDevBinaryRegister", return_value=0)
        mocker.patch(
            "ms_interface.single_op_test_frame.utils.file_util.read_file",
            return_value=b"0x00",
        )
        res = rts_api.register_device_binary_kernel("kernel_path", "")
        assert isinstance(res, ctypes.c_void_p)

    def test_unregister_device_binary_kernel(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtDevBinaryUnRegister", return_value=0)
        ptr = ctypes.c_void_p(0)
        rts_api.kernel_binary_storage = {ptr.value: 0}
        rts_api.kernel_name_storage = {ptr.value: Mock()}
        res = rts_api.unregister_device_binary_kernel(ptr)
        assert res is None

    def test_register_function(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtFunctionRegister", return_value=0)

        ptr = ctypes.c_void_p(0)
        rts_api.register_function(ptr, "kernel_name", 0)

        rts_api.kernel_name_storage = {ptr.value: Mock()}
        rts_api.register_function(ptr, "kernel_name", 0)

    def test_copy_bin_file_to_hbm(self, mocker, rts_api):
        with pytest.raises(TypeError):
            mocker.patch(
                "ms_interface.single_op_test_frame.utils.file_util.read_file",
                return_value="0x00",
            )
            rts_api.copy_bin_file_to_hbm("/bin/path")

        ptr = ctypes.c_void_p(0)
        mocker.patch(
            "ms_interface.single_op_test_frame.utils.file_util.read_file",
            return_value=b"0x00",
        )
        mocker.patch.object(rts_api, "malloc", return_value=ptr)
        mocker.patch.object(rts_api, "memcpy", return_value=None)
        mocker.patch.object(rts_api, "get_memory_info_ex", return_value=0)
        res = rts_api.copy_bin_file_to_hbm("/bin/path")
        assert res == ptr

        with pytest.raises(Exception):
            mocker.patch.object(rts_api, "malloc", side_effect=[OSError])
            res = rts_api.copy_bin_file_to_hbm("/bin/path")

    def test_get_data_from_hbm(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtMallocHost", return_value=0)
        ptr = ctypes.c_void_p(0)
        mocker.patch.object(rts_api, "memcpy", return_value=1)

        res = rts_api.get_data_from_hbm(0, 10)
        assert len(res) == 2

        ptr = ctypes.c_void_p(0)
        res = rts_api.get_data_from_hbm(ptr, 10)
        assert len(res) == 2

    def test_memset(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtMemset", return_value=0)
        assert rts_api.memset(ctypes.c_void_p(0), 1, 1, 1) is None

    def test_api_call(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtMemset", return_value=0)
        assert rts_api.api_call("rtMemset", ctypes.c_void_p(0), 1, 1, 1) is None

    def test_get_c2c_ctrl_addr(self, mocker, rts_api):
        mocker.patch.object(rts_api, "api_call", return_value=None)
        res = rts_api.get_c2c_ctrl_addr()
        assert isinstance(res, ctypes.c_void_p)

    def test_malloc(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtMalloc", return_value=0)
        mocker.patch.object(rts_api, "memcpy", return_value=None)
        assert isinstance(rts_api.malloc(1), ctypes.c_void_p)

    def test_free(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtFree", return_value=0)
        assert rts_api.free(ctypes.c_void_p) is None

    def test_host_free(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtFreeHost", return_value=0)
        assert rts_api.host_free(ctypes.c_void_p) is None

    def test_launch_kernel(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtKernelLaunch", return_value=0)
        assert (
            rts_api.launch_kernel(ctypes.c_void_p(0), 1, (), 1, 0, ctypes.c_uint64(0))
            == 0
        )

        mocker.patch.object(
            rts_api.rtsdll, "rtKernelLaunch", return_value=ctypes.c_uint64(0)
        )
        assert (
            rts_api.launch_kernel(ctypes.c_void_p(0), 1, (), 1, 0, ctypes.c_uint64(0))
            == 0
        )

    def test_synchronize_with_stream(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtStreamSynchronize", return_value=0)
        assert rts_api.synchronize_with_stream(ctypes.c_uint64(0)) == 0

        mocker.patch.object(
            rts_api.rtsdll, "rtStreamSynchronize", return_value=ctypes.c_uint64(0)
        )
        assert rts_api.synchronize_with_stream(ctypes.c_uint64(0)) == 0

    def test_reset(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtDeviceReset", return_value=0)
        mocker.patch.object(rts_api, "_clear_env", return_value=None)
        rts_api.device_id = 0
        assert rts_api.reset() is None
        assert rts_api.reset(0) is None

    def test_start_online_profing(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtStartOnlineProf", return_value=0)
        assert rts_api.start_online_profiling(ctypes.c_uint64(0), 0) is None

    def test_stop_online_profiling(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtStopOnlineProf", return_value=0)
        assert rts_api.stop_online_profiling(ctypes.c_uint64(0)) is None

    def test_get_online_profiling_data(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtGetOnlineProfData", return_value=0)
        res = rts_api.get_online_profiling_data(ctypes.c_uint64(0), 0)
        assert res is not None

    def test_get_memory_info_ex(self, mocker, rts_api):
        mocker.patch.object(rts_api.rtsdll, "rtMemGetInfoEx", return_value=0)
        with pytest.raises(RuntimeError):
            rts_api.get_memory_info_ex("memory_info")
        res = rts_api.get_memory_info_ex("RT_MEMORYINFO_DDR")
        assert len(res) == 2

    def test_clear_env(self, mocker, rts_api):
        mock_environ = {"LD_LIBRARY_PATH": "/mock/lib/path"}
        mocker.patch.dict(os.environ, mock_environ, clear=False)
        setattr(rts_api, "_simulator_mode", "mode1")
        assert getattr(rts_api, "_clear_env")() is None
