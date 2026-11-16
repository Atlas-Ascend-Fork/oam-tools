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

import ctypes
import os
import sys
import pytest
import shutil
from .conftest import CONF_SRC_PATH, test_case_tmp
from .conftest import AssertTest
from .conftest import enter_test_tmp, restore_cwd


import asys
from params import ParamDict
from common.device import DeviceInfo
from common.chip_handler import g_device_map
from common.ascend950.ascend950_handler import Ascend950Handler


class TestInfo(AssertTest):
    def setup_method(self):
        print("init test environment")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        enter_test_tmp()
        ParamDict.clear()
        g_device_map.clear()

    def teardown_method(self):
        print("clean test environment.")  # noqa: T201  # test diagnostic output
        restore_cwd()
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_all_info_with_910D(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 在Ascend910D环境上执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        self.assertTrue(True)

        class DrvDsmi:
            @staticmethod
            def dsmi_get_hbm_info(device_id, p_memory_info):
                return 0

            @staticmethod
            def dsmi_get_memory_info(device_id, p_memory_info):
                return 0

        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9591 V1"
        )

        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_all_info_with_910D_use_ascend950handler(
        self, arg_name, arg_val, mocker
    ):
        """
        @描述: 使用-r参数, 在Ascend910D环境上执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        self.assertTrue(True)

        class DrvDsmi:
            @staticmethod
            def dsmi_get_hbm_info(device_id, p_memory_info):
                return 0

            @staticmethod
            def dsmi_get_memory_info(device_id, p_memory_info):
                return 0

        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi()
        )
        mocker.patch("common.chip_handler.get_device", return_value=Ascend950Handler())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9591 V1"
        )

        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_all_info_with_910D_for_coverusage(
        self, arg_name, arg_val, mocker
    ):
        """
        @描述: 使用-r参数, 在Ascend910D环境上执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        self.assertTrue(True)

        class DrvDsmi:
            @staticmethod
            def dsmi_get_hbm_info(device_id, p_memory_info):
                return 0

            @staticmethod
            def dsmi_get_memory_info(device_id, p_memory_info):
                return 0

        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi()
        )
        mocker.patch("common.chip_handler.get_device", return_value=Ascend950Handler())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9591 V1"
        )

        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        device_id = (
            ParamDict().get_arg("device_id") if ParamDict().get_arg("device_id") else 0
        )
        ascend950handler = Ascend950Handler()
        self.assertTrue(
            ascend950handler.get_device_aic_info(device_id) == ["-", "-, -", "-, -"]
        )
        self.assertTrue(
            ascend950handler.get_device_bus_info(device_id)
            == ["-, -", "-, -", "-", "-, -", "-, -"]
        )
        self.assertTrue(
            ascend950handler.get_device_hbm_info(device_id) == ["-", "-", "-", "-"]
        )
        self.assertTrue(ascend950handler.get_device_voltage(device_id) == "-")
        self.assertTrue(ascend950handler.get_device_aicore_frequency(device_id) == "-")
        self.assertTrue(ascend950handler.get_device_temperature(device_id) == "-")

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_with_910D_aic_info_fail(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 在Ascend910D环境上执行info功能, 模拟AML接口获取Aic信息失败
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        self.assertTrue(True)

        class DeviceInfoMock:
            UNSUPPORTED_KEY_WORDS = ["-", "-, -"]

            def get_chip_info(self, *_args):
                return "Ascend 910_9591 V1"

            def get_aicore_count(self, *_args):
                return 20

            def get_device_voltage(self, *_args):
                return "930(Max)"

            def get_device_aicore_frequency(self, *_args):
                return "800(Avg)"

            def get_device_power(self, *_args):
                return 875

            def get_device_temperature(self, *_args):
                return 56

            def get_device_health(self, *_args):
                return "Healthy"

            def get_device_cpu_info(self, *_args):
                return 6, 1, 930, 2000

            def get_device_aic_info(self, *_args):
                return 20, "-, -", "-, -"

            def get_device_bus_info(self, *_args):
                return "930, 920", "2700, 2800", 2000, "2700, 2800", "2700, 2800"

            def get_device_memory_info(self, *_args):
                return "-", "-"

            def get_device_hbm_info(self, *_args):
                return 32768, 2658, 0, 0

            def get_device_utilization_rate(self, *_args):
                return 0

            def get_device_hbm_volt_freq(self, *_args):
                return 1200, 1600

            def get_device_count(self):
                return 1

        mocker.patch("info.asys_info.get_device", return_value=DeviceInfoMock())

        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(
        ["arg_name", "arg_val", "chip_info", "value"],
        [("-r", "status", "Ascend 910_9599", 0)],
    )
    def test_info_status_get_temperature(
        self, capsys, arg_name, arg_val, chip_info, value, mocker
    ):
        """
        @描述: 使用-r参数, 在Ascend910B环境上执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        self.assertTrue(True)

        class DrvDsmi:
            @staticmethod
            def dsmi_get_soc_sensor_info(device_id, soc_temp, p_memory_info):
                return 0

            @staticmethod
            def dsmi_get_device_temperature(device_id, p_memory_info):
                return 0

        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_info)
        mocker.patch.object(DeviceInfo, "get_device_power", return_value=875)
        mocker.patch.object(DeviceInfo, "get_device_voltage", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_health", return_value="Healthy")
        mocker.patch.object(
            DeviceInfo, "get_device_cpu_info", return_value=[6, 1, 930, 2000]
        )
        mocker.patch.object(
            DeviceInfo, "get_device_aic_info", return_value=["-", "-", "-"]
        )
        mocker.patch.object(
            DeviceInfo, "get_device_bus_info", return_value=["-", "-", "-", "-", "-"]
        )
        mocker.patch.object(
            DeviceInfo, "get_device_hbm_info", return_value=[32768, 2658, 0, 0]
        )
        mocker.patch.object(DeviceInfo, "get_device_utilization_rate", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_device_hbm_volt_freq", return_value=[1200, 1600]
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_aicore_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_device_aicore_frequency", return_value=2)
        mocker.patch.object(DeviceInfo, "get_npu_arch", return_value=3510)
        mocker.patch("ctypes.c_int", return_value=ctypes.c_uint(35))
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
