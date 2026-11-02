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

import sys
import pytest
import os
import subprocess

from testcase.conftest import CONF_SRC_PATH, ut_root_path

import asys
from params import ParamDict
from ..conftest import AssertTest
from common.device import DeviceInfo
from common.chip_handler import g_device_map
from info.asys_info import LSPCI_GREP_VERSION, AsysInfo


class TestInfo(AssertTest):
    def setup_method(self):
        ParamDict().asys_output_timestamp_dir = os.path.join(
            ut_root_path, "asys_output_20230227093645758"
        )
        g_device_map.clear()

    def teardown_method(self):
        ParamDict.clear()
        g_device_map.clear()

    def test_info_pcie(self, capsys):
        self.assertTrue("d100|d500|d801|d802|d803|d806" in LSPCI_GREP_VERSION)

    def test_info_hardware(self, capsys):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        AsysInfo().get_hardware_info()
        captured = capsys.readouterr()
        self.assertTrue(captured.out.count("Host Info") == 1)

    def test_info_hardware_sums_per_device_core_counts(self, mocker):
        device_info = mocker.Mock()
        device_info.get_ccpu_count.side_effect = [8, 12]
        device_info.get_aicpu_count.side_effect = [4, 8]
        device_info.get_aicore_count.side_effect = [32, 40]
        device_info.get_veccore_count.side_effect = [64, 80]
        device_info.get_device_info_loop.side_effect = ["Ascend X", "Arch X"]

        info = object.__new__(AsysInfo)
        info.device_info = device_info
        info.device_num = 2
        table_data = {" Device Info ": []}

        info._AsysInfo__get_device_info(table_data)
        rows = dict(table_data[" Device Info "])

        self.assertTrue(rows["Control CPU Count"] == "20 (8 + 12)")
        self.assertTrue(rows["AI CPU Count"] == "12 (4 + 8)")
        self.assertTrue(rows["AI Core Count"] == "72 (32 + 40)")
        self.assertTrue(rows["AI Vector Count"] == "144 (64 + 80)")

    @pytest.mark.parametrize(
        (
            "device_num",
            "expected_ccpu",
            "expected_aicpu",
            "expected_aicore",
            "expected_vector",
        ),
        [
            (1, "8 (8 * 1)", "4 (4 * 1)", "32 (32 * 1)", "64 (64 * 1)"),
            (2, "16 (8 * 2)", "8 (4 * 2)", "64 (32 * 2)", "128 (64 * 2)"),
        ],
    )
    def test_info_hardware_same_core_counts_keep_multiplication_summary(
        self,
        mocker,
        device_num,
        expected_ccpu,
        expected_aicpu,
        expected_aicore,
        expected_vector,
    ):
        device_info = mocker.Mock()
        device_info.get_ccpu_count.side_effect = [8] * device_num
        device_info.get_aicpu_count.side_effect = [4] * device_num
        device_info.get_aicore_count.side_effect = [32] * device_num
        device_info.get_veccore_count.side_effect = [64] * device_num
        device_info.get_device_info_loop.side_effect = ["Ascend X", "Arch X"]

        info = object.__new__(AsysInfo)
        info.device_info = device_info
        info.device_num = device_num
        table_data = {" Device Info ": []}

        info._AsysInfo__get_device_info(table_data)
        rows = dict(table_data[" Device Info "])

        self.assertTrue(rows["Control CPU Count"] == expected_ccpu)
        self.assertTrue(rows["AI CPU Count"] == expected_aicpu)
        self.assertTrue(rows["AI Core Count"] == expected_aicore)
        self.assertTrue(rows["AI Vector Count"] == expected_vector)

    @pytest.mark.parametrize("unavailable_count", ["-", None, -1])
    def test_info_hardware_does_not_report_partial_core_count(
        self, mocker, unavailable_count
    ):
        device_info = mocker.Mock()
        device_info.get_ccpu_count.side_effect = [8, 12]
        device_info.get_aicpu_count.side_effect = [4, 8]
        device_info.get_aicore_count.side_effect = [32, unavailable_count]
        device_info.get_veccore_count.side_effect = [64, 80]
        device_info.get_device_info_loop.side_effect = ["Ascend X", "Arch X"]

        info = object.__new__(AsysInfo)
        info.device_info = device_info
        info.device_num = 2
        table_data = {" Device Info ": []}

        info._AsysInfo__get_device_info(table_data)
        rows = dict(table_data[" Device Info "])

        self.assertTrue(rows["AI Core Count"] == "-")

    def test_info_hardware_zero_devices_reports_zero_cores(self, mocker):
        device_info = mocker.Mock()
        device_info.get_device_info_loop.return_value = "Unknown"

        info = object.__new__(AsysInfo)
        info.device_info = device_info
        info.device_num = 0
        table_data = {" Device Info ": []}

        info._AsysInfo__get_device_info(table_data)
        rows = dict(table_data[" Device Info "])

        for name in (
            "Control CPU Count",
            "AI CPU Count",
            "AI Core Count",
            "AI Vector Count",
        ):
            self.assertTrue(rows[name] == "0 (no devices)")

    def test_info_hardware_not_data(self, capsys, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        mocker.patch.object(ParamDict, "get_arg", return_value="hardware")
        fake_ret = subprocess.run(
            "cat /proc/cpuinfo | grep notest",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.run", return_value=fake_ret)
        ParamDict().set_env_type("EP")
        AsysInfo().get_hardware_info()
        captured = capsys.readouterr()
        self.assertTrue(captured.out.count("Cpu Info") == 0)

    def test_info_software(self, capsys):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入:  asys info -r=software
        @步骤: 校验main函数返回值是否为True
        @预期结果: 获取打屏关键词
        """
        ParamDict().set_env_type("EP")
        AsysInfo().get_software_info()
        captured = capsys.readouterr()
        self.assertTrue(captured.out.count("Host Version") == 1)

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

    def test_info_status(self, capsys, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        ParamDict().set_env_type("EP")
        AsysInfo().get_status_info(0)
        captured = capsys.readouterr()
        self.assertTrue(captured.out.count("Device ID: 0") == 1)

    def test_info_status_d(self, capsys, mocker):
        """
        @描述: 使用-r, -d参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        ParamDict().set_env_type("EP")
        AsysInfo().get_status_info(1)
        captured = capsys.readouterr()
        self.assertTrue(captured.out.count("Device ID: 1") == 1)

    def test_info_status_no_ddr_hbm(self, capsys, mocker):
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

        mocker.patch("drv.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        ParamDict().set_env_type("EP")
        AsysInfo().get_status_info(0)
        captured = capsys.readouterr()
        self.assertTrue(captured.out.count("Device ID: 0") == 1)

    def test_info_status_ddr_hbm(self, capsys, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
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

        ParamDict().set_env_type("EP")
        AsysInfo().get_status_info(0)
        captured = capsys.readouterr()
        self.assertTrue(captured.out.count("Memory Information") == 1)
        self.assertTrue(captured.out.count("HBM Voltage") == 1)

    def test_info_status_bus(self, capsys, mocker):
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

        ParamDict().set_env_type("EP")
        AsysInfo().get_status_info(0)
        captured = capsys.readouterr()
        self.assertTrue(captured.out.count("Bus Information") == 1)

    def test_info_software_cann_version(self, capsys, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入:  asys info -r=software
        @步骤: 校验main函数返回值是否为True
        @预期结果: 获取打屏关键词
        """
        mocker.patch("info.asys_info.run_command", return_value="7.6.T7.0.B052")
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=0)
        ParamDict().set_env_type("EP")
        AsysInfo().get_software_info()
        captured = capsys.readouterr()
        except_msg = """
 +------------------------+--------------------+
 | Group of 0 Device      | INFORMATION        |
 +========================+====================+
 +--- Host Version -------+--------------------+
 | Kernel                 | 7.6.T7.0.B052      |
 | OS                     | 7.6.T7.0.B052      |
 +--- Device Version -----+--------------------+
 | firmware               | 7.6.T7.0.B052      |
 | driver                 | 7.6.T7.0.B052      |
 | runtime                | 7.6.T7.0.B052      |
 | ge-compiler            | 7.6.T7.0.B052      |
 | bisheng-compiler       | 7.6.T7.0.B052      |
 | oam_tools              | 7.6.T7.0.B052      |
 | dvpp                   | 7.6.T7.0.B052      |
 | aoe                    | 7.6.T7.0.B052      |
 | hccl                   | 7.6.T7.0.B052      |
 | ncs                    | 7.6.T7.0.B052      |
 | opbase                 | 7.6.T7.0.B052      |
 | ops_cv                 | 7.6.T7.0.B052      |
 | ops_legacy             | 7.6.T7.0.B052      |
 | ops_math               | 7.6.T7.0.B052      |
 | ops_nn                 | 7.6.T7.0.B052      |
 | ops_transformer        | 7.6.T7.0.B052      |
 +------------------------+--------------------+
"""
        self.assertTrue(except_msg == captured.out)

    def test_info_status_all_info(self, capsys, mocker):
        """
        @描述: 使用-r参数, 执行info功能
        @类型: FUNCTION
        @输入: asys info -r=status
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: 获取打屏关键词
        """
        self.assertTrue(True)

        class DeviceInfoMock:
            UNSUPPORTED_KEY_WORDS = ["-"]

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

        ParamDict().set_env_type("EP")
        AsysInfo().get_status_info(0)
        captured = capsys.readouterr()
        except_msg = """
 +----------------------------------+----------------------+
 | Device ID: 0                     | INFORMATION          |
 +==================================+======================+
 | Chip Name                        | Ascend 910B4 V1      |
 | Power (W)                        | 875                  |
 | Temperature (C)                  | 56                   |
 | health                           | Healthy              |
 +--- CPU Information --------------+----------------------+
 | AI CPU Count                     | 6                    |
 | AI CPU Usage (%)                 | 0                    |
 | Control CPU Count                | 1                    |
 | Control CPU Usage (%)            | 0                    |
 | Control CPU Frequency (MHZ)      | 2000                 |
 | Control CPU Voltage (MV)         | 930                  |
 +--- AI Core Information ----------+----------------------+
 | AI Core Count                    | 20                   |
 | AI Core Usage (%)                | 0                    |
 | AI Core Frequency (MHZ)          | 800                  |
 | AI Core Voltage (MV)             | 900                  |
 +--- Bus Information --------------+----------------------+
 | Bus Voltage (MV)                 | 930                  |
 | Ring Frequency (MHZ)             | 2700                 |
 | CPU Frequency (MHZ)              | 2000                 |
 | Mata Frequency (MHZ)             | 2000                 |
 | L2buffer Frequency (MHZ)         | 2300                 |
 +--- Memory Information -----------+----------------------+
 | HBM Total (MB)                   | 32768                |
 | HBM Used (MB)                    | 2658                 |
 | HBM Bandwidth Usage (%)          | 0                    |
 | HBM Frequency (MHZ)              | 1600                 |
 | HBM Voltage (MV)                 | 1200                 |
 +----------------------------------+----------------------+
"""
        self.assertTrue(except_msg == captured.out)
