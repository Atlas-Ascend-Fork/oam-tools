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

import os
import shutil
import sys

import pytest
from pathlib import Path

from .conftest import CONF_SRC_PATH, test_case_tmp
from .conftest import AssertTest


import asys
from params import ParamDict
from common.device import DeviceInfo
from common.chip_handler import g_device_map


class AsysDiagnose0:
    def AmlStressDetect(self, a, b):
        return 0

    def AmlHbmDetectWithType(self, a, b, c):
        return 0

    def AmlCpuDetect(self, a, b):
        return 0

    def AmlStressRestore(self, a):
        return 0

    def halGetDeviceInfo(self, phyid, a, b, masterid):
        return 0

    def drvDeviceGetPhyIdByIndex(self, device_id, phyid):
        return 0

    def drvGetPlatformInfo(self, num):
        num[0] = 1
        return 0


class AsysDiagnose1:
    def AmlStressDetect(self, a, b):
        return 1

    def AmlHbmDetectWithType(self, a, b, c):
        return 1

    def AmlCpuDetect(self, a, b):
        return 1

    def AmlStressRestore(self, a):
        return 1

    def halGetDeviceInfo(self, phyid, a, b, masterid):
        return 1

    def drvDeviceGetPhyIdByIndex(self, device_id, phyid):
        return 1

    def drvGetPlatformInfo(self, num):
        num[0] = 1
        return 0


class AsysStlDiagnose0:
    def AmlAicoreStlDetect(self, a):
        return 0


class TestDiagnose(AssertTest):
    def setup_method(self):
        print("init test environment")  # noqa: T201  # test diagnostic output
        if not os.getenv("ASCEND_OPP_PATH"):
            os.environ["ASCEND_OPP_PATH"] = "/home"
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        os.chdir(test_case_tmp)
        ParamDict.clear()
        g_device_map.clear()

    def teardown_method(self):
        print("clean test environment.")  # noqa: T201  # test diagnostic output
        if os.getenv("ASCEND_OPP_PATH"):
            os.environ.pop("ASCEND_OPP_PATH")
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)

    @pytest.mark.parametrize(["chip_type"], [("Ascend 950 V1",)])
    def test_diagnose_supported_soc(self, mocker, capsys, chip_type):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=hbm_detect", "--timeout=10"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch("common.device.LoadSoType.get_env_type", return_value="EP")
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        mocker.patch("diagnose.asys_diagnose.check_command", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=-1)
        mocker.patch.object(DeviceInfo, "clear_ecc_isolated", return_value=-1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_type)
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue(
            "| HBM Detect             | Warn - All             |\n |                        | (0, 0)                 |"
            in captured.out
        )

    def test_diagnose_aicore_stl_loads_so(self, mocker):
        """aicore_stl_detect loads libaml_aicore_stl.so and assigns it to device_obj.aml_aicore_stl.

        Also passes --timeout to exercise the warn-and-ignore branch for aicore_stl_detect.
        """
        sys.argv = [
            CONF_SRC_PATH,
            "diagnose",
            "-d=0",
            "-r=aicore_stl_detect",
            "--timeout=90",
        ]
        mock_stl = AsysStlDiagnose0()
        mocker.patch(
            "common.device.LoadSoType.get_aml_aicore_stl", return_value=mock_stl
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        mocker.patch("diagnose.asys_diagnose.check_command", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_diagnose_aicore_stl_so_loaded_by_absolute_path(self, mocker, monkeypatch):
        """libaml_aicore_stl.so 装在 tools/aml/lib64/aicore_stl/,不在 LD_LIBRARY_PATH 中。

        端到端看护:asys 必须按 ASCEND_HOME_PATH 拼出的绝对路径加载,而非裸 so 名。
        裸名会让入口 so 内部的 dladdr 定位到错误目录,进而加载不到形态 so。
        """
        from drv import LoadSoType
        from drv.env_type import AICORE_STL_SO_NAME, AICORE_STL_SO_SUBPATH

        LoadSoType.clear()
        # 造出安装布局:<home>/tools/aml/lib64/aicore_stl/libaml_aicore_stl.so
        fake_home = os.path.join(test_case_tmp, "fake_ascend_home")
        so_dir = os.path.join(fake_home, AICORE_STL_SO_SUBPATH)
        os.makedirs(so_dir, exist_ok=True)
        so_file = os.path.join(so_dir, AICORE_STL_SO_NAME)
        Path(so_file).write_bytes(b"")
        monkeypatch.setenv("ASCEND_HOME_PATH", fake_home)

        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=aicore_stl_detect"]
        load_dll = mocker.patch.object(
            LoadSoType, "load_dll", return_value=AsysStlDiagnose0()
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch.object(LoadSoType, "get_env_type", return_value="EP")
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        mocker.patch("diagnose.asys_diagnose.check_command", return_value=True)
        ParamDict().set_env_type("EP")

        self.assertTrue(asys.main())
        # load_dll 是六个 so 共用的 staticmethod(drvdsmi/drvhal/ascend_ml/ascendcl/
        # ascend_trace/aml_aicore_stl),故只筛 STL 那一条调用,不断言总次数。
        stl_calls = [
            c
            for c in load_dll.call_args_list
            if c[0] and str(c[0][0]).endswith(AICORE_STL_SO_NAME)
        ]
        self.assertTrue(len(stl_calls) == 1)
        passed = stl_calls[0][0][0]
        self.assertTrue(passed == os.path.realpath(so_file))
        self.assertTrue(os.path.isabs(passed))
        LoadSoType.clear()

    def test_diagnose_aicore_stl_fails_when_so_absent(
        self, mocker, monkeypatch, capsys
    ):
        """so 未安装时 diagnose 优雅失败(而非抛异常),并给出可定位的错误。"""
        from drv import LoadSoType
        from drv.env_type import AICORE_STL_SO_NAME

        LoadSoType.clear()
        fake_home = os.path.join(test_case_tmp, "empty_ascend_home")
        os.makedirs(fake_home, exist_ok=True)
        monkeypatch.setenv("ASCEND_HOME_PATH", fake_home)

        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=aicore_stl_detect"]
        load_dll = mocker.patch.object(LoadSoType, "load_dll")
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch.object(LoadSoType, "get_env_type", return_value="EP")
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        mocker.patch("diagnose.asys_diagnose.check_command", return_value=True)
        ParamDict().set_env_type("EP")

        self.assertTrue(not asys.main())
        # 同上:只关心 STL 那条调用未发生,其余 so 的加载与本用例无关。
        stl_calls = [
            c
            for c in load_dll.call_args_list
            if c[0] and str(c[0][0]).endswith(AICORE_STL_SO_NAME)
        ]
        self.assertTrue(len(stl_calls) == 0)
        LoadSoType.clear()
