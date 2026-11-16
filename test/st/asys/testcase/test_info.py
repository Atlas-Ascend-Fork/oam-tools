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
import subprocess
import copy
from .conftest import CONF_SRC_PATH, test_case_tmp, set_env, unset_env
from .conftest import AssertTest, DrvAml, DrvDsmi, DrvHal
from .conftest import enter_test_tmp, restore_cwd


import asys
from params import ParamDict
from common.device import DeviceInfo
from common.chip_handler import g_device_map
from info.asys_info import AsysInfo

config = {
    "acpu_cnt": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "acpu_usage": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "ccpu_cnt": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "ccpu_usage": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "ccpu_frequency": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "ccpu_voltage": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "aic_cnt": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "aic_usage": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "aic_frequency": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "aic_voltage": {
        "get": ["ALL"],
        "set": ["NULL"],
        "restore": ["910B\\d", "910_93", "950"],
    },
    "bus_voltage": {
        "get": ["ALL"],
        "set": ["NULL"],
        "restore": ["910B\\d", "910_93", "950"],
    },
    "ring_frequency": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "cpu_frequency": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "mata_frequency": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "l2buffer_frequency": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "ddr_total": {
        "get": ["^(?!.*910B\\d)(?!.*910_93)(?!.*950).*"],
        "set": ["NULL"],
        "restore": ["NULL"],
    },
    "ddr_used": {
        "get": ["^(?!.*910B\\d)(?!.*910_93)(?!.*950).*"],
        "set": ["NULL"],
        "restore": ["NULL"],
    },
    "ddr_bandwidth": {
        "get": ["^(?!.*910B\\d)(?!.*910_93)(?!.*950).*"],
        "set": ["NULL"],
        "restore": ["NULL"],
    },
    "ddr_frequency": {
        "get": ["^(?!.*910B\\d)(?!.*910_93)(?!.*950).*"],
        "set": ["NULL"],
        "restore": ["NULL"],
    },
    "hbm_total": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "hbm_used": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "hbm_bandwidth_usage": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "hbm_frequency": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
    "hbm_voltage": {"get": ["ALL"], "set": ["NULL"], "restore": ["NULL"]},
}


def setup_module():
    print("TestCollect st test start.")  # noqa: T201  # test diagnostic output
    set_env()


def teardown_module():
    print("TestCollect st test finish.")  # noqa: T201  # test diagnostic output
    unset_env()


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

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "hardware")])
    def test_info_hardware(self, arg_name, arg_val):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "hardware")])
    def test_info_hardware_not_data(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        fake_ret = subprocess.run(
            "cat /proc/cpuinfo | grep notest",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "software")])
    def test_info_software(self, arg_name, arg_val):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入:  asys info -r=software
        @步骤: 校验main函数返回值是否为True
        @预期结果: 获取打屏关键词
        """
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_error(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val]), "-d=1"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_d(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r, -d参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val]), "-d=1"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_no_ddr_hbm(self, capsys, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 执行info功能
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

        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_ddr_hbm(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910 V1")
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(
            DeviceInfo, "get_device_memory_info", return_value=[1024, 0]
        )
        mocker.patch.object(
            DeviceInfo, "get_device_hbm_info", return_value=[1024, 0, 0, 0]
        )
        mocker.patch.object(
            DeviceInfo, "get_device_hbm_volt_freq", return_value=[1800, 1199]
        )

        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_bus(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(
            DeviceInfo,
            "get_device_bus_info",
            return_value=[930, 2800, 2000, 2000, 2400],
        )
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")

        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_power(self, arg_name, arg_val, mocker):
        self.assertTrue(True)

        class DrvDsmi:
            @staticmethod
            def dsmi_get_device_power_info(device_id, p_memory_info):
                return 1

        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_aicore_count(self, arg_name, arg_val, mocker):
        self.assertTrue(True)

        class DrvHal:
            @staticmethod
            def halGetDeviceInfo(*_args):
                return 0

        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=DrvHal()
        )
        mocker.patch("common.device.LoadSoType.get_env_type", return_value="EP")
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "software")])
    def test_info_software_cann_version(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入:  asys info -r=software
        @步骤: 校验main函数返回值是否为True
        @预期结果: 获取打屏关键词
        """
        mocker.patch("info.asys_info.run_command", return_value="7.6.T7.0.B052")
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_all_info(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        self.assertTrue(True)

        class DeviceInfoMock:
            UNSUPPORTED_KEY_WORDS = ["_"]  # 查询信息返回不支持的关键字数组

            def get_chip_info(self, *_args):
                return "Ascend 910B4 V1"

            def get_device_power(self, *_args):
                return 875

            def get_device_temperature(self, *_args):
                return 56

            def get_device_health(self, *_args):
                return "Healthy"

            def get_device_cpu_info(self, *_args):
                return 6, 1, 930, 2000

            def get_device_aic_info(self, *_args):
                return 20, 900, 800

            def get_device_bus_info(self, *_args):
                return 930, 2700, 2000, 2000, 2300

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

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_without_hbm_total(self, arg_name, arg_val, mocker):
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

        config_table = copy.deepcopy(config)
        config_table["hbm_total"]["get"] = ["NULL"]
        mocker.patch(
            "common.file_operate.FileOperate.read_config", return_value=config_table
        )
        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["d"], [(False,), (0,), (1,), (2,), (3,)])
    def test_info_status_all_info_loop(self, d, capsys, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
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

            def get_device_count(self):
                return 8

        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        mocker.patch("info.asys_info.get_device", return_value=DeviceInfoMock())
        mocker.patch("info.asys_info.run_command", return_value="xxxxx")
        if d is False:
            sys.argv = [CONF_SRC_PATH, "info", "-r=hardware"]
        else:
            sys.argv = [CONF_SRC_PATH, "info", f"-d={d}", "-r=hardware"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_get_device_voltage(self, capsys, arg_name, arg_val, mocker):
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
            def dsmi_get_device_voltage(device_id, p_memory_info):
                return 0

        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch.object(DeviceInfo, "get_device_power", return_value=875)
        mocker.patch.object(DeviceInfo, "get_device_temperature", return_value=56)
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
        mocker.patch.object(DeviceInfo, "get_npu_arch", return_value=2201)
        mocker.patch("ctypes.c_uint", return_value=ctypes.c_uint(35))
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_info_status_status_not_support(self, mocker, caplog):
        """

        :return:
        """
        DrvDsmi.set_res(
            device_count=1,
            device_health=1,
            device_errorcode=1,
            device_frequency=1,
            device_utilization_rate=1,
            get_device_info=1,
        )
        DrvHal.set_res(ChipInfo=1)
        DrvAml.set_res(
            DeviceGetCpuInfo=1,
            DeviceGetAicoreInfo=1,
            DeviceGetBusInfo=1,
            DeviceGetHbmInfo=1,
        )
        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi
        )
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=DrvHal
        )
        mocker.patch("common.device.LoadSoType.get_ascend_ml", return_value=DrvAml)
        ParamDict().set_env_type("EP")
        sys.argv = [CONF_SRC_PATH, "info", "-r=status"]
        self.assertTrue(asys.main())

    def test_info_status_hardware_not_support(self, mocker, caplog):
        """

        :return:
        """
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        DrvHal.set_res(GetDeviceInfo=1)
        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi
        )
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=DrvHal
        )
        mocker.patch("common.device.LoadSoType.get_ascend_ml", return_value=DrvAml)
        ParamDict().set_env_type("EP")
        sys.argv = [CONF_SRC_PATH, "info", "-r=hardware"]
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_timeout(self, arg_name, arg_val, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(AsysInfo, "run_info", side_effect=TimeoutError("timeout"))
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("-r", "status")])
    def test_info_status_without_hbm_total_time_out(self, arg_name, arg_val, mocker):
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
                import time

                time.sleep(11)
                return 0

            @staticmethod
            def dsmi_get_memory_info(device_id, p_memory_info):
                return 0

        config_table = copy.deepcopy(config)
        config_table["hbm_total"]["get"] = ["NULL"]
        mocker.patch(
            "common.file_operate.FileOperate.read_config", return_value=config_table
        )
        mocker.patch(
            "common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        sys.argv = [CONF_SRC_PATH, "info", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    def test_info_write_info(self, mocker):
        ParamDict().asys_output_timestamp_dir = test_case_tmp
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        AsysInfo().write_info()
        self.assertTrue(
            os.path.isfile(os.path.join(test_case_tmp, "software_info.txt"))
        )
        self.assertTrue(
            os.path.isfile(os.path.join(test_case_tmp, "hardware_info.txt"))
        )
