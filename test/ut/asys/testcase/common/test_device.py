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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

import pytest
import os
import ctypes
from pathlib import Path

from testcase.conftest import ut_root_path

from common.device import DeviceInfo
from common.const import RetCode
from drv import LoadSoType
from ..conftest import AssertTest


class DsmiHandle:
    def __init__(self, value=0):
        self.value = value

    def dsmi_get_device_count(self, p_device_count):
        return self.value

    def dsmi_list_device(self, carray, device_count):
        return self.value

    def dsmi_get_chip_info(self, carray, p_chip_info):
        return carray

    def dsmi_get_aicpu_info(self, carray, p_aicpu_info):
        return carray

    def dsmi_get_device_health(self, count, p_health_count):
        return count

    def dsmi_get_device_errorcode(self, count, p_error_count, perrorcode):
        return count

    def dsmi_query_errorstring(self, count, error_code, errorinfo, max_size):
        return count

    def dsmi_get_network_health(self, count, health_count):
        return count


class HalHandle:
    def __init__(self, value=0):
        self.value = value

    def halGetDeviceInfo(
        self, card_num, module_type_aicpu, type_core_num, p_aicpu_count
    ):
        return self.value


class TestDevice(AssertTest):
    test_file_path = os.path.join(ut_root_path, "test_file")

    def setup_method(self):
        testfile = Path(self.test_file_path)
        testfile.touch(exist_ok=True)
        self.fp = open(testfile, encoding="utf-8")

    def teardown_method(self):
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def test_get_device_count(self, mocker):
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        deviceinfo = DeviceInfo()
        deviceinfo.get_device_count()
        deviceinfo.dsmi_handle = DsmiHandle()
        deviceinfo.get_device_count()
        deviceinfo.dsmi_handle = DsmiHandle(1)
        deviceinfo.get_device_count()
        self.assertTrue(True)

    def test_get_chip_info(self, mocker):
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        deviceinfo = DeviceInfo()
        deviceinfo.get_chip_info(0)
        deviceinfo.dsmi_handle = DsmiHandle()
        deviceinfo.get_chip_info(0)
        deviceinfo.get_chip_info(1)
        self.assertTrue(True)

    def test_get_aicpu_count(self, mocker):
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        deviceinfo = DeviceInfo()
        deviceinfo.get_aicpu_count(0)
        deviceinfo.dsmi_handle = DsmiHandle(0)
        deviceinfo.get_aicpu_count(0)
        deviceinfo.hal_handle = HalHandle(0)
        deviceinfo.get_aicpu_count(1)
        deviceinfo.hal_handle = HalHandle(1)
        deviceinfo.get_aicpu_count(1)
        self.assertTrue(True)

    def test_get_aicore_count(self, mocker):
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        deviceinfo = DeviceInfo()
        deviceinfo.hal_handle = HalHandle(0)
        deviceinfo.get_aicore_count(0)
        deviceinfo.hal_handle = HalHandle(1)
        deviceinfo.get_aicore_count(0)
        self.assertTrue(True)

    def test_get_veccore_count(self, mocker):
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        deviceinfo = DeviceInfo()
        deviceinfo.hal_handle = HalHandle(0)
        deviceinfo.get_veccore_count(0)
        deviceinfo.hal_handle = HalHandle(1)
        deviceinfo.get_veccore_count(0)
        self.assertTrue(True)

    def test_get_device_health(self, mocker):
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch("ctypes.c_int", return_value=ctypes.c_int(0))
        deviceinfo = DeviceInfo()
        deviceinfo.get_device_health(0)
        deviceinfo.dsmi_handle = DsmiHandle()
        deviceinfo.get_device_health(0)
        deviceinfo.get_device_health(1)
        mocker.patch("ctypes.c_int", return_value=ctypes.c_int(10))
        deviceinfo.get_device_health(0)
        self.assertTrue(True)

    def test_get_device_errorcode(self, mocker):
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        deviceinfo = DeviceInfo()
        deviceinfo.get_device_errorcode(1)
        deviceinfo.dsmi_handle = DsmiHandle()
        deviceinfo.get_device_errorcode(1)
        mocker.patch("ctypes.c_int", return_value=ctypes.c_int(1))
        mocker.patch("ctypes.c_uint", return_value=ctypes.c_int(11000))
        mocker.patch("ctypes.c_char", return_value=ctypes.c_char())
        deviceinfo.get_device_errorcode(0)
        mocker.patch("ctypes.c_char", return_value=ctypes.c_char(b"t"))
        deviceinfo.get_device_errorcode(0)
        self.assertTrue(True)

    def test_get_device_errorcode_buffer_size(self, mocker):
        class RecordDsmiHandle:
            def __init__(self, error_count):
                self.error_count = error_count
                self.errorinfo_lens = []
                self.max_sizes = []

            def dsmi_get_device_errorcode(self, device_id, p_error_count, perrorcode):
                p_error_count.contents.value = self.error_count
                return 0

            def dsmi_query_errorstring(
                self, device_id, error_code, errorinfo, max_size
            ):
                self.errorinfo_lens.append(len(errorinfo))
                self.max_sizes.append(max_size)
                return 0

        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        deviceinfo = DeviceInfo()
        deviceinfo.dsmi_handle = RecordDsmiHandle(1)
        deviceinfo.get_device_errorcode(0)
        self.assertTrue(deviceinfo.dsmi_handle.errorinfo_lens == [256])
        self.assertTrue(deviceinfo.dsmi_handle.max_sizes == [256])

    def test_get_device_errorcode_count_clamped(self, mocker, caplog):
        class CountDsmiHandle:
            def __init__(self, error_count):
                self.error_count = error_count
                self.query_count = 0

            def dsmi_get_device_errorcode(self, device_id, p_error_count, perrorcode):
                p_error_count.contents.value = self.error_count
                return 0

            def dsmi_query_errorstring(
                self, device_id, error_code, errorinfo, max_size
            ):
                self.query_count += 1
                return 0

        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        deviceinfo = DeviceInfo()
        deviceinfo.dsmi_handle = CountDsmiHandle(129)
        error_list = deviceinfo.get_device_errorcode(0)
        self.assertTrue(deviceinfo.dsmi_handle.query_count == 128)
        self.assertTrue(len(error_list) == 128)
        self.assertTrue("reported 129 error codes" in caplog.text)
        self.assertTrue("only the first 128 are queried" in caplog.text)

    def test_get_ccpu_count(self, mocker):
        self.assertTrue(True)

        class DreHal:
            @staticmethod
            def halGetDeviceInfo(*_args):
                return 0

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=DreHal())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch("ctypes.c_int", return_value=ctypes.c_int(0))
        deviceinfo = DeviceInfo()
        self.assertTrue(deviceinfo.get_ccpu_count(0) == 0)

        class DreHal:
            @staticmethod
            def halGetDeviceInfo(*_args):
                return 1

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=DreHal())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch("ctypes.c_int", return_value=ctypes.c_int(0))
        deviceinfo = DeviceInfo()
        self.assertTrue(deviceinfo.get_ccpu_count(0) == "-")

    def test_get_device_hbm_info(self, mocker):
        self.assertTrue(True)

        class DrvDsmi:
            @staticmethod
            def dsmi_get_hbm_info(device_id, p_memory_info):
                return 0

            @staticmethod
            def dsmi_get_memory_info(device_id, p_memory_info):
                return 0

        mocker.patch("drv.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch("ctypes.c_int", return_value=ctypes.c_int(0))
        deviceinfo = DeviceInfo()
        deviceinfo.get_device_hbm_info(0)

    def test_get_device_cpu_info(self, mocker):
        device_info = DeviceInfo()

        class AmlDevice:
            @staticmethod
            def AmlDeviceGetCpuInfo(device_id, info):
                return 1

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_device_cpu_info(0) == ["-"] * 4)

        class AmlDevice:
            @staticmethod
            def AmlDeviceGetCpuInfo(device_id, info):
                return 0

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_device_cpu_info(0) == [0] * 4)

    def test_get_device_cpu_info_ctypes_argument_error(self, mocker):
        # ctypes.ArgumentError 直接继承 Exception，不是 TypeError 子类，
        # 必须显式出现在 except 元组里，否则会穿透兜底导致 asys 崩溃
        class AmlDevice:
            @staticmethod
            def AmlDeviceGetCpuInfo(device_id, info):
                raise ctypes.ArgumentError("argument 1: wrong type")

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_device_cpu_info(0) == ["-"] * 4)

    def test_get_device_aic_info(self, mocker):
        device_info = DeviceInfo()

        class AmlDevice:
            @staticmethod
            def AmlDeviceGetAicoreInfo(device_id, info):
                return 1

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_device_aic_info(0) == ["-"] * 3)

        class AmlDevice:
            @staticmethod
            def AmlDeviceGetAicoreInfo(device_id, info):
                return 0

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_device_aic_info(0) == [0] * 3)

    def test_get_device_bus_info(self, mocker):
        device_info = DeviceInfo()

        class AmlDevice:
            @staticmethod
            def AmlDeviceGetBusInfo(device_id, info):
                return 1

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_device_bus_info(0) == ["-"] * 5)

        class AmlDevice:
            @staticmethod
            def AmlDeviceGetBusInfo(device_id, info):
                return 0

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_device_bus_info(0) == [0] * 5)

    def test_get_device_hbm_volt_freq(self, mocker):
        device_info = DeviceInfo()

        class AmlDevice:
            @staticmethod
            def AmlDeviceGetHbmInfo(device_id, info):
                return 1

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_device_hbm_volt_freq(0) == ["-"] * 2)

        class AmlDevice:
            @staticmethod
            def AmlDeviceGetHbmInfo(device_id, info):
                return 0

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_device_hbm_volt_freq(0) == [0] * 2)

    def test_get_phyid_from_logicid(self, mocker):
        device_info = DeviceInfo()

        class HalDevice:
            @staticmethod
            def drvDeviceGetPhyIdByIndex(device_id, phyid):
                return 1

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=HalDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_phyid_from_logicid(0) == RetCode.FAILED)

        class HalDevice:
            @staticmethod
            def drvDeviceGetPhyIdByIndex(device_id, phyid):
                return 0

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=HalDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_phyid_from_logicid(0) == 0)

    def test_get_masterid_from_phyid(self, mocker):
        device_info = DeviceInfo()

        class HalDevice:
            @staticmethod
            def halGetDeviceInfo(phyid, a, b, masterid):
                return 1

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=HalDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_masterid_from_phyid(0) == RetCode.FAILED)

        class HalDevice:
            @staticmethod
            def halGetDeviceInfo(phyid, a, b, masterid):
                return 0

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=HalDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_masterid_from_phyid(0) == 0)

    def test_common_device_get_device_info_loop(self, mocker):
        self.assertTrue(True)

        class DeviceInfoMock:
            @staticmethod
            def get_device_info_loop(device_num, func, err):
                return DeviceInfo().get_device_info_loop(device_num, func, err)

            def get_chip_info(self, device_id):
                ret = "Ascend 910B4 V1" if device_id > 2 else "Unknown"
                return ret

            def get_ccpu_count(self, device_id):
                ret = 1 if device_id > 2 else "-"
                return ret

            def get_aicpu_count(self, device_id):
                ret = 7 if device_id > 2 else "-"
                return ret

            def get_aicore_count(self, device_id):
                ret = 8 if device_id > 2 else "-"
                return ret

            def get_veccore_count(self, device_id):
                ret = 7 if device_id > 2 else "-"
                return ret

        device_info = DeviceInfoMock()
        chip_info = device_info.get_device_info_loop(
            8, device_info.get_chip_info, "Unknown"
        )
        self.assertTrue(chip_info == "Ascend 910B4 V1")
        ccpu_count = device_info.get_device_info_loop(
            8, device_info.get_ccpu_count, "-"
        )
        self.assertTrue(ccpu_count == 1)
        aicpu_count = device_info.get_device_info_loop(
            8, device_info.get_aicpu_count, "-"
        )
        self.assertTrue(aicpu_count == 7)
        aicore_count = device_info.get_device_info_loop(
            8, device_info.get_aicore_count, "-"
        )
        self.assertTrue(aicore_count == 8)
        veccore_count = device_info.get_device_info_loop(
            8, device_info.get_veccore_count, "-"
        )
        self.assertTrue(veccore_count == 7)

    def test_get_device_voltage(self, mocker):
        self.assertTrue(True)

        class DrvDsmi:
            @staticmethod
            def dsmi_get_device_voltage(device_id, p_memory_info):
                return 0

        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch.object(LoadSoType, "get_drvdsmi_env_type", return_value=DrvDsmi())
        deviceinfo = DeviceInfo()
        mocker.patch("ctypes.c_uint", return_value=ctypes.c_uint(35))
        res = deviceinfo.get_device_voltage(0)
        self.assertTrue(res == 350)

    def test_get_device_temperature(self, mocker):
        self.assertTrue(True)

        class DrvDsmi:
            @staticmethod
            def dsmi_get_device_temperature(device_id, p_memory_info):
                return 0

        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch.object(LoadSoType, "get_drvdsmi_env_type", return_value=DrvDsmi())
        deviceinfo = DeviceInfo()
        mocker.patch("ctypes.c_int", return_value=ctypes.c_int(35))
        res = deviceinfo.get_device_temperature(0)
        self.assertTrue(res == 35)

    @pytest.mark.parametrize(
        "func, log_data",
        [
            ("get_device_cpu_info", "Get device cpu info failed"),
            ("get_device_aic_info", "Get device aic info failed"),
            ("get_device_bus_info", "Get device bus info failed"),
            ("get_device_hbm_volt_freq", "Get device hbm volt & freq failed"),
        ],
    )
    def test_get_device_info_failed(self, func, log_data, mocker, caplog):
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch("drv.LoadSoType.get_drvdsmi_env_type", return_value=None)
        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=None)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=None)
        deviceinfo = DeviceInfo()
        func_dict = {
            "get_device_cpu_info": deviceinfo.get_device_cpu_info(0),
            "get_device_aic_info": deviceinfo.get_device_aic_info(0),
            "get_device_bus_info": deviceinfo.get_device_bus_info(0),
            "get_device_hbm_volt_freq": deviceinfo.get_device_hbm_volt_freq(0),
        }
        func_dict.get(func)
        self.assertTrue(log_data in caplog.text)

    def test_dsmi_get_device_power_info(self, mocker):
        self.assertTrue(True)

        class DrvDsmi:
            @staticmethod
            def dsmi_get_device_power_info(device_id, p):
                return 0

        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch("drv.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=None)
        deviceinfo = DeviceInfo()
        self.assertTrue(deviceinfo.get_device_power(0) == 0)

    def test_get_npu_arch(self, mocker):
        self.assertTrue(True)

        class Ascendcl:
            @staticmethod
            def aclrtGetDeviceInfo(device_id, type, p):
                return 0

        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch("drv.LoadSoType.get_ascend_cl", return_value=Ascendcl)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=None)
        deviceinfo = DeviceInfo()
        self.assertTrue(deviceinfo.get_npu_arch(0) == 0)
