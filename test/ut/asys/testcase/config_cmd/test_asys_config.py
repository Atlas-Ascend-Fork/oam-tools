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

from argparse import Namespace


from config_cmd import AsysConfig
from params import ParamDict
from ..conftest import AssertTest
from common.device import DeviceInfo
from common.chip_handler import g_device_map


class AsysConfig0:
    def AmlStressRestore(self, *_args):
        return 0


class AsysConfig1:
    def AmlStressRestore(self, *_args):
        return 1


class AsysConfigOSError:
    def AmlStressRestore(self, *_args):
        raise OSError("mock aml stress restore failure")


class TestAsysConfig(AssertTest):
    def setup_method(self):
        ParamDict.clear()
        g_device_map.clear()

    def teardown_method(self):
        ParamDict.clear()

    def test_asys_config_get_mode(self, mocker, capsys):
        args = Namespace(
            d=1, get=True, restore=False, stress_detect=True, subparser_name="config"
        )

        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch.object(DeviceInfo, "get_device_aic_info", return_value=[0, 850, 0])
        mocker.patch.object(
            DeviceInfo, "get_device_bus_info", return_value=[900, 0, 0, 0, 0]
        )
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run())
        captured = capsys.readouterr()
        expect_ret = """
 +---------------------------+----------------------------+
 | Device ID: 1              | CURRENT CONFIGURATION      |
 +===========================+============================+
 | AI Core Voltage (MV)      | 850                        |
 | Bus Voltage (MV)          | 900                        |
 +---------------------------+----------------------------+
"""
        self.assertTrue(captured.out == expect_ret)

    def test_asys_config_get_mode_without_d(self, mocker, capsys):
        args = Namespace(
            d=None, get=True, restore=False, stress_detect=True, subparser_name="config"
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B2 V1")
        mocker.patch.object(DeviceInfo, "get_device_aic_info", return_value=[0, 850, 0])
        mocker.patch.object(
            DeviceInfo, "get_device_bus_info", return_value=[900, 0, 0, 0, 0]
        )
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run())
        captured = capsys.readouterr()
        expect_ret = """
 +---------------------------+----------------------------+
 | Device ID: 0              | CURRENT CONFIGURATION      |
 +===========================+============================+
 | AI Core Voltage (MV)      | 850                        |
 | Bus Voltage (MV)          | 900                        |
 +---------------------------+----------------------------+
"""
        self.assertTrue(captured.out == expect_ret)

    def test_asys_config_get_mode_without_option_error(self, mocker, caplog):
        args = Namespace(
            d=None,
            get=True,
            restore=False,
            stress_detect=False,
            subparser_name="config",
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B3 V1")
        mocker.patch.object(DeviceInfo, "get_device_aic_info", return_value=[0, 850, 0])
        mocker.patch.object(
            DeviceInfo, "get_device_bus_info", return_value=[900, 0, 0, 0, 0]
        )
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run() is False)
        self.assertTrue(
            """At least one configuration option is required.""" in caplog.text
        )

    def test_asys_config_get_mode_without_mode_error(self, mocker, caplog):
        args = Namespace(
            d=None,
            get=False,
            restore=False,
            stress_detect=True,
            subparser_name="config",
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch.object(DeviceInfo, "get_device_aic_info", return_value=[0, 850, 0])
        mocker.patch.object(
            DeviceInfo, "get_device_bus_info", return_value=[900, 0, 0, 0, 0]
        )
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run() is False)
        self.assertTrue(
            "The config command requires either the --get or --restore argument"
            in caplog.text
        )

    def test_asys_config_get_mode_volt_error(self, mocker, caplog):
        args = Namespace(
            d=1, get=True, restore=False, stress_detect=True, subparser_name="config"
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9391 V1"
        )
        mocker.patch.object(
            DeviceInfo, "get_device_aic_info", return_value=["-", "-", "-"]
        )
        mocker.patch.object(
            DeviceInfo, "get_device_bus_info", return_value=["-", "-", "-", "-", "-"]
        )
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run() is False)
        self.assertTrue("Configuration unsuccessfully get, on device 1." in caplog.text)

    def test_asys_config_get_mode_aic_volt_error(self, mocker, capsys):
        args = Namespace(
            d=1, get=True, restore=False, stress_detect=True, subparser_name="config"
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9381 V1"
        )
        mocker.patch.object(
            DeviceInfo, "get_device_aic_info", return_value=["-", 850, "-"]
        )
        mocker.patch.object(
            DeviceInfo, "get_device_bus_info", return_value=["-", "-", "-", "-", "-"]
        )
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run())
        captured = capsys.readouterr()
        expect_ret = """
 +---------------------------+----------------------------+
 | Device ID: 1              | CURRENT CONFIGURATION      |
 +===========================+============================+
 | AI Core Voltage (MV)      | 850                        |
 +---------------------------+----------------------------+
"""
        self.assertTrue(captured.out == expect_ret)

    def test_asys_config_get_mode_bus_volt_error(self, mocker, capsys):
        args = Namespace(
            d=1, get=True, restore=False, stress_detect=True, subparser_name="config"
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9392 V1"
        )
        mocker.patch.object(
            DeviceInfo, "get_device_aic_info", return_value=["-", "-", "-"]
        )
        mocker.patch.object(
            DeviceInfo, "get_device_bus_info", return_value=[900, "-", "-", "-", "-"]
        )
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run())
        captured = capsys.readouterr()
        expect_ret = """
 +-----------------------+----------------------------+
 | Device ID: 1          | CURRENT CONFIGURATION      |
 +=======================+============================+
 | Bus Voltage (MV)      | 900                        |
 +-----------------------+----------------------------+
"""
        self.assertTrue(captured.out == expect_ret)

    def test_asys_config_restore_mode(self, mocker):
        args = Namespace(
            d=1, get=False, restore=True, stress_detect=True, subparser_name="config"
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysConfig0())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9382 V1"
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run())

    def test_asys_config_restore_mode_error(self, mocker, caplog):
        args = Namespace(
            d=1, get=False, restore=True, stress_detect=True, subparser_name="config"
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysConfig1())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9372 V1"
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run() is False)
        self.assertTrue(
            "Configuration unsuccessfully restore, on device 1." in caplog.text
        )

    def test_asys_config_restore_mode_exception_logged(self, mocker, caplog):
        args = Namespace(
            d=1, get=False, restore=True, stress_detect=True, subparser_name="config"
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysConfigOSError())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9372 V1"
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run() is False)
        self.assertTrue("OSError" in caplog.text)
        self.assertTrue("mock aml stress restore failure" in caplog.text)
        self.assertTrue(
            "Configuration unsuccessfully restore, on device 1." in caplog.text
        )

    def test_asys_config_user_error(self, mocker, caplog):
        args = Namespace(
            d=1, get=False, restore=True, stress_detect=True, subparser_name="config"
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysConfig1())
        mocker.patch("os.getuid", return_value=1000)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9362 V1"
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run() is False)
        self.assertTrue(
            "The config --restore command must be executed as the root user."
            in caplog.text
        )

    def test_asys_config_chip_error(self, mocker, caplog):
        args = Namespace(
            d=1, get=False, restore=True, stress_detect=True, subparser_name="config"
        )
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=True)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysConfig1())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910 V1")
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run() is False)
        self.assertTrue(
            "The config command does not support Ascend 910 V1" in caplog.text
        )

    def test_asys_config_vm_docker_error(self, mocker, caplog):
        args = Namespace(
            d=1, get=False, restore=True, stress_detect=True, subparser_name="config"
        )
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysConfig1())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9361 V1"
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("config_cmd.asys_config.run_linux_cmd", return_value=False)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)
        self.assertTrue(AsysConfig().run() is False)
        self.assertTrue(
            "The config command cannot be executed on VMs and docker." in caplog.text
        )
