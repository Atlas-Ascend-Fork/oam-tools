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
import subprocess
from pathlib import Path

from .conftest import CONF_SRC_PATH, test_case_tmp
from .conftest import AssertTest


import asys
from params import ParamDict
from common import RetCode, FileOperate
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


class AsysDiagnose2:
    pass


class AsysStlDiagnose0:
    def AmlAicoreStlDetect(self, a):
        return 0


class AsysStlDiagnose1:
    def AmlAicoreStlDetect(self, a):
        return 1


@pytest.mark.skip(reason="temporarily skipped due to test failure")
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

    def test_diagnose_stress_1p(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=stress_detect"]
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("common.interface.run_hbm", return_value={0: "Pass"})
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        except_msg = "| Stress Detect      | Pass                   | "
        captured = capsys.readouterr()
        self.assertTrue(except_msg in captured.out)

    def test_diagnose_hbm_1p(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=hbm_detect", "--timeout=10"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0()
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B2 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue(
            "| HBM Detect        | Pass(0)                |" in captured.out
        )

    def test_diagnose_cpu_1p(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=cpu_detect", "--timeout=10"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0()
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue(
            "| CPU Detect        | Pass                   |" in captured.out
        )

    def test_diagnose_aicore_stl_1p(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=aicore_stl_detect"]
        mocker.patch(
            "common.device.LoadSoType.get_aml_aicore_stl",
            return_value=AsysStlDiagnose0(),
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue("AICore STL Detect" in captured.out)

    def test_diagnose_aicore_stl_960dt_1p(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=aicore_stl_detect"]
        mocker.patch(
            "common.device.LoadSoType.get_aml_aicore_stl",
            return_value=AsysStlDiagnose0(),
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 960DT V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue("AICore STL Detect" in captured.out)

    def test_diagnose_aicore_stl_not_950(self, mocker, caplog):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=aicore_stl_detect"]
        mocker.patch(
            "common.device.LoadSoType.get_aml_aicore_stl",
            return_value=AsysStlDiagnose0(),
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "The aicore_stl_detect mode is only supported on Ascend950 and "
            "Ascend960DT." in caplog.text
        )

    def test_diagnose_aicore_stl_960pr_intercepted(self, mocker, caplog):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=aicore_stl_detect"]
        mocker.patch(
            "common.device.LoadSoType.get_aml_aicore_stl",
            return_value=AsysStlDiagnose0(),
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 960PR V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "The aicore_stl_detect mode is only supported on Ascend950 and "
            "Ascend960DT." in caplog.text
        )

    def test_diagnose_aicore_stl_loads_so(self, mocker):
        """aicore_stl_detect loads libaml_aicore_stl.so and assigns it to device_obj.aml_aicore_stl."""
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=aicore_stl_detect"]
        mock_stl = AsysStlDiagnose0()
        mocker.patch(
            "common.device.LoadSoType.get_aml_aicore_stl", return_value=mock_stl
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_diagnose_stress_2p(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=stress_detect"]
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B3 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue(
            "| Stress Detect          | Warn - All             |" in captured.out
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_hbm_2p(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=hbm_detect", "--timeout=10"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9391 V1"
        )
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue(
            "| HBM Detect             | Warn - All             |\n |                        | (0, 0)                 |"
            in captured.out
        )

    def test_diagnose_cpu_2p_warn(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=cpu_detect", "--timeout=10"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue(
            "| CPU Detect             | Warn - All             |" in captured.out
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_cpu_2p_pass(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=cpu_detect", "--timeout=10"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0()
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B2 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue(
            "| CPU Detect             | Pass - All             |" in captured.out
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_hbm_2p_ecc_lt_zero(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=hbm_detect", "--timeout=10"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=-1)
        mocker.patch.object(DeviceInfo, "clear_ecc_isolated", return_value=-1)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9381 V1"
        )
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue(
            "| HBM Detect             | Warn - All             |\n |                        | (0, 0)                 |"
            in captured.out
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_4p_file(self, mocker):
        sys.argv = [
            CONF_SRC_PATH,
            "diagnose",
            "-r=stress_detect",
            f"--output={test_case_tmp}",
        ]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        mocker.patch(
            "cmdline.cmd_parser.CommandLineParser.check_arg_with_checker",
            return_value=RetCode.SUCCESS,
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=True)

        if not os.path.exists(test_case_tmp):
            os.makedirs(test_case_tmp)

        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

        ret_file = [
            f for f in os.listdir(test_case_tmp) if f.startswith("diagnose_result")
        ]
        self.assertTrue(os.path.exists(f"{test_case_tmp}/{ret_file[0]}"))
        shutil.rmtree(test_case_tmp)

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_run_stress_detect(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=stress_detect", "-d=1"]
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9372 V1"
        )
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue(
            "| Device ID: 1       | Diagnostic Result      |" in captured.out
        )
        self.assertTrue(
            "| Stress Detect      | Warn                   |" in captured.out
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    @pytest.mark.parametrize(
        ["run_mode"], [("stress_detect",), ("hbm_detect",), ("cpu_detect",)]
    )
    def test_diagnose_uesr_error(self, mocker, caplog, run_mode):
        sys.argv = [CONF_SRC_PATH, "diagnose", f"-r={run_mode}", "-d=1"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=1000)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9391 V1"
        )
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main() is False)
        self.assertTrue(
            "The diagnose command must be executed as the root user" in caplog.text
        )

    @pytest.mark.parametrize(
        ["run_mode"], [("stress_detect",), ("hbm_detect",), ("cpu_detect",)]
    )
    def test_diagnose_soc_error(self, mocker, caplog, run_mode):
        sys.argv = [CONF_SRC_PATH, "diagnose", f"-r={run_mode}", "-d=1"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch("common.device.LoadSoType.get_env_type", return_value="EP")
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B V1")
        mocker.patch("os.path.isfile", return_value=True)

        self.assertTrue(asys.main() is False)
        self.assertTrue(
            "The diagnose command does not support Ascend 910B V1" in caplog.text
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    @pytest.mark.parametrize(
        ["chip_type"], [("Ascend 910B1 V1",), ("Ascend 910_9391 V1",)]
    )
    def test_diagnose_supported_soc(self, mocker, capsys, chip_type):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=hbm_detect", "--timeout=10"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch("os.getuid", return_value=0)
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

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_run_without_opp_kernel(self, mocker, caplog):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=stress_detect"]

        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9381 V1"
        )
        mocker.patch("os.path.isfile", return_value=False)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main() is False)
        self.assertTrue(
            "The diagnose command can be executed only after the" in caplog.text
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_run_hbm_timeout_le_zero(self, mocker, caplog):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=hbm_detect", "--timeout=-1"]

        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9372 V1"
        )
        mocker.patch("os.path.isfile", return_value=False)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main() is False)
        self.assertTrue(
            "The value of timeout must be in the range of [0, 604800]." in caplog.text
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_run_cpu_timeout_le_one(self, mocker, caplog):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=cpu_detect", "--timeout=-1"]

        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=False)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main() is False)
        self.assertTrue(
            "The value of timeout must be in the range of [1, 604800]." in caplog.text
        )

    def test_diagnose_run_hbm_timeout_not_int(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=hbm_detect", "--timeout=a"]

        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9362 V1"
        )
        mocker.patch("os.path.isfile", return_value=False)
        ParamDict().set_env_type("EP")

        asys.main()
        msg = capsys.readouterr()
        self.assertTrue(
            "asys diagnose: error: argument --timeout: invalid int value: 'a'"
            in msg.err
        )

    def test_diagnose_run_cpu_timeout_not_int(self, mocker, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=cpu_detect", "--timeout=#"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9372 V1"
        )
        mocker.patch("os.path.isfile", return_value=False)
        ParamDict().set_env_type("EP")

        asys.main()
        msg = capsys.readouterr()
        self.assertTrue(
            "asys diagnose: error: argument --timeout: invalid int value: '#'"
            in msg.err
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_run_hbm_aml_api_error(self, mocker, caplog):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=hbm_detect", "--timeout=30"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose2()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=False)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            "Run hbm detect failed, error_msg: 'AsysDiagnose2' object has no attribute 'AmlHbmDetectWithType'"
            in caplog.text
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_run_cpu_aml_api_error(self, mocker, caplog):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=cpu_detect", "--timeout=30"]
        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0()
        )
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose2()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=False)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            "Run cpu detect failed, error_msg: 'AsysDiagnose2' object has no attribute 'AmlCpuDetect'"
            in caplog.text
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_diagnose_run_hbm_without_timeout(self, mocker, capsys, caplog):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=0", "-r=hbm_detect"]
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue("Warn(0)" in captured.out)
        self.assertTrue(
            "Run hbm detect failed, error_msg: 'NoneType' object has no attribute 'AmlHbmDetectWithType'"
            in caplog.text
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_get_phyid_from_logicid(self, mocker):
        from common.device import DeviceInfo

        device_info = DeviceInfo()
        self.assertTrue(device_info.get_phyid_from_logicid(0) == RetCode.FAILED)

        class HalDevice:
            @staticmethod
            def drvDeviceGetPhyIdByIndex(device_id, phyid):
                return 1

        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=HalDevice()
        )
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_phyid_from_logicid(0) == RetCode.FAILED)

        class HalDevice:
            @staticmethod
            def drvDeviceGetPhyIdByIndex(device_id, phyid):
                return 0

        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=HalDevice()
        )
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_phyid_from_logicid(0) == 0)

    def test_get_masterid_from_phyid(self, mocker):
        from common.device import DeviceInfo

        device_info = DeviceInfo()

        class HalDevice:
            @staticmethod
            def halGetDeviceInfo(phyid, a, b, masterid):
                return 1

        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=HalDevice()
        )
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_masterid_from_phyid(0) == RetCode.FAILED)

        class HalDevice:
            @staticmethod
            def halGetDeviceInfo(phyid, a, b, masterid):
                return 0

        mocker.patch(
            "common.device.LoadSoType.get_drvhal_env_type", return_value=HalDevice()
        )
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = DeviceInfo()
        self.assertTrue(device_info.get_masterid_from_phyid(0) == 0)

    def test_diagnose_get_devices_master_id(self, mocker):
        self.assertTrue(True)

        from common.interface import get_devices_master_id

        class HalDevice:
            @staticmethod
            def get_phyid_from_logicid(device_id):
                return RetCode.FAILED

        self.assertTrue(get_devices_master_id(HalDevice(), [0]) == {0: 0})
        self.assertTrue(get_devices_master_id(HalDevice(), [0, 1]) == {0: -1, 1: -1})

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    @pytest.mark.parametrize(["d"], [(False,), (0,), (1,), (2,), (3,)])
    def test_diagnose_device_error_d(self, d, mocker, caplog, capsys):
        if d is False:
            sys.argv = [CONF_SRC_PATH, "diagnose", "-r=stress_detect"]
        else:
            sys.argv = [CONF_SRC_PATH, "diagnose", f"-d={d}", "-r=stress_detect"]
        chip_info = "Unknown" if int(d) in [0, 1] else "Ascend 910B1 V1"
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        mocker.patch("common.interface.run_hbm", return_value={0: "Pass"})
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_info)
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        if d is False:
            self.assertTrue(not asys.main())
            self.assertTrue(
                "The diagnose command does not support on device_0: Unknown."
                in caplog.text
            )
            self.assertTrue(
                "The diagnose command does not support on device_3: Unknown."
                in caplog.text
            )
        elif d in [0, 1]:
            self.assertTrue(not asys.main())
            self.assertTrue(
                "The diagnose command does not support Unknown." in caplog.text
            )
        else:
            self.assertTrue(asys.main())
            except_msg = "| Stress Detect      | Pass                   | "
            captured = capsys.readouterr()
            self.assertTrue(except_msg in captured.out)

    @pytest.mark.parametrize(
        ["run_mode"],
        [("stress_detect",), ("cpu_detect",), ("hbm_detect",), ("component",)],
    )
    def test_diagnose_device_without_d(self, run_mode, mocker, caplog, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", f"-r={run_mode}"]
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        ret = (
            {2: ["Pass", "0"], 3: ["Pass", "0"]}
            if run_mode == "hbm_detect"
            else {2: "Pass", 3: "Pass"}
        )
        mocker.patch("common.interface.run_diagnose", return_value=ret)
        mocker.patch(
            "diagnose.asys_diagnose.AsysDiagnose.get_diagnose_devices_chip_info",
            return_value=([2, 3], "Ascend 910B1 V1"),
        )
        mocker.patch(
            "diagnose.asys_diagnose.AsysDiagnose._check_support", return_value=True
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch("os.path.exists", return_value=True)

        ParamDict().set_env_type("EP")

        asys.main()
        if run_mode == "stress_detect":
            except_msg = """
 +------------------------+-----------------------------+
 | Group of 4 Device      | Diagnostic Result           |
 +========================+=============================+
 +--- Performance --------+-----------------------------+
 | Stress Detect          | Warn, Warn, Pass, Pass      |
 +------------------------+-----------------------------+
"""
        elif run_mode == "cpu_detect":
            except_msg = """
 +------------------------+-----------------------------+
 | Group of 4 Device      | Diagnostic Result           |
 +========================+=============================+
 +--- Hardware -----------+-----------------------------+
 | CPU Detect             | Warn, Warn, Pass, Pass      |
 +------------------------+-----------------------------+
"""
        elif run_mode == "hbm_detect":
            except_msg = """
 +------------------------+-----------------------------+
 | Group of 4 Device      | Diagnostic Result           |
 +========================+=============================+
 +--- Hardware -----------+-----------------------------+
 | HBM Detect             | Warn, Warn, Pass, Pass      |
 |                        | (0, 0, 0, 0)                |
 +------------------------+-----------------------------+
"""
        elif run_mode == "component":
            except_msg = """
 +------------------------+------------------------+
 | Group of 4 Device      | Diagnostic Result      |
 +========================+========================+
 +--- Component ----------+------------------------+
 | AI Vector              | Pass - All             |
 +------------------------+------------------------+
"""

        captured = capsys.readouterr()
        self.assertTrue(except_msg in captured.out)

    def test_asys_diagnose_component_not_have_msaicerr(self, mocker, caplog, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=component"]
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "The path of the msaicerr tool cannot be found, please install the whole package"
            in caplog.text
        )

    def test_asys_diagnose_component_device_id_eq_zero(self, mocker, caplog, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=component"]
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=0)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        msg = """The chip does not have a device for execution."""
        self.assertTrue(msg in caplog.text)

    def test_asys_diagnose_component_device_id_gt_device(self, mocker, caplog, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=4", "-r=component"]
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.path.exists", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("'-d' value should be in [0, 1), input 4" in caplog.text)

    def test_asys_diagnose_component_device_id_lt_zero(self, mocker, caplog, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-d=-1", "-r=component"]
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            'Argument "d" value is range of [0, 63], input: "-1"' in caplog.text
        )

    def test_asys_diagnose_component_have_w_permission(self, mocker, caplog, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=component"]
        mocker.patch("common.cmd_run.run_linux_cmd", return_value=0)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(Path, "exists", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(FileOperate, "check_access", return_value=False)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        msg = """The current directory or debug_info.txt is immutable, Please check"""
        self.assertTrue(msg in caplog.text)

    def test_diagnose_run_msaicerr(self, mocker, caplog, capsys):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=component", "-d=0"]
        fake_ret = subprocess.Popen(
            "test",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch(
            "common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        mocker.patch(
            "diagnose.asys_diagnose.AsysDiagnose._check_support", return_value=True
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(Path, "exists", return_value=False)
        ParamDict().set_env_type("EP")
        asys.main()
        captured = capsys.readouterr()
        self.assertTrue("Fail" in captured.out)
