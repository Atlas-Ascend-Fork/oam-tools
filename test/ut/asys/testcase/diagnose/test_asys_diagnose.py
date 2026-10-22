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

import os.path
import subprocess

import pytest
from pathlib import Path


from common.const import RetCode
import diagnose.asys_diagnose as asys_diagnose
from diagnose import AsysDiagnose
from params import ParamDict
from ..conftest import AssertTest
from common.device import DeviceInfo
from common.chip_handler import g_device_map
from common import FileOperate


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


class Dsmi_handle:
    def dsmi_get_total_ecc_isolated_pages_info(self, dev_id, type, a):
        return 0

    def dsmi_clear_ecc_isolated_statistics_info(self, dev_id):
        return 0


class TestAsysDiagnose(AssertTest):
    def setup_method(self):
        if not os.getenv("ASCEND_OPP_PATH"):
            os.environ["ASCEND_OPP_PATH"] = "/home"
        ParamDict.clear()
        g_device_map.clear()

    def teardown_method(self):
        if os.getenv("ASCEND_OPP_PATH"):
            os.environ.pop("ASCEND_OPP_PATH")
        ParamDict.clear()
        g_device_map.clear()

    def test_diagnose_no_so(self, mocker):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "stress_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=RetCode.FAILED)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is False)

    def test_diagnose_device_num_failed(self, mocker):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "stress_detect"
            d = None
            output = False
            timeout = None

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=0)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B2 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is False)

    def test_diagnose_1p(self, mocker, tmp_path):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "stress_detect"
            d = None
            output = str(tmp_path)
            timeout = None

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B3 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        info_log = mocker.spy(asys_diagnose, "log_info")
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)
        ret_file = next(tmp_path.glob("diagnose_result_*.txt"))
        self.assertTrue(ret_file.is_file())
        info_log.assert_any_call(f"output file: {ret_file.resolve()}", force=True)

    def test_diagnose_hbm_1p(self, mocker):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "hbm_detect"
            d = None
            output = "./"
            timeout = 3

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)
        ret_file = [f for f in os.listdir("./") if f.startswith("diagnose_result")][0]
        self.assertTrue(os.path.isfile(ret_file))
        os.remove(ret_file)

    def test_diagnose_cpu_1p(self, mocker):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "cpu_detect"
            d = None
            output = "./"
            timeout = 3

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)
        ret_file = [f for f in os.listdir("./") if f.startswith("diagnose_result")][0]
        self.assertTrue(os.path.isfile(ret_file))
        os.remove(ret_file)

    def test_diagnose_2p(self, mocker):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "stress_detect"
            d = None
            output = None
            timeout = 3

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910B4-1 V1"
        )
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)

    def test_diagnose_hbm_2p(self, mocker):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "hbm_detect"
            d = None
            output = None
            timeout = 3

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)

    def test_diagnose_cpu_2p(self, mocker):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "cpu_detect"
            d = None
            output = None
            timeout = 3

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=1)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9393 V1"
        )
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)

    def test_diagnose_hbm_2p_dsmi(self, mocker):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "hbm_detect"
            d = None
            output = None
            timeout = 3

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_drvdsmi_env_type", return_value=Dsmi_handle())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9382 V1"
        )
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)

    def test_diagnose_hbm_2p_dsmi_lt_zero(self, mocker):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "hbm_detect"
            d = None
            output = None
            timeout = 3

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_drvdsmi_env_type", return_value=Dsmi_handle())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=-1)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9372 V1"
        )
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)

    def test_diagnose_hbm_2p_ecc_lt_zero(self, mocker):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = "hbm_detect"
            d = None
            output = None
            timeout = 3

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=-64)
        mocker.patch.object(DeviceInfo, "clear_ecc_isolated", return_value=-1)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910_9362 V1"
        )
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)

    def test_diagnose_d_zero(self, mocker):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "stress_detect"
            subparser_name = "diagnose"
            output = "./"
            timeout = None

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)
        ret_file = [f for f in os.listdir("./") if f.startswith("diagnose_result")][0]
        self.assertTrue(os.path.isfile(ret_file))
        os.remove(ret_file)

    @pytest.mark.parametrize(
        "ascend_ml, res", [(AsysDiagnose1, True), (AsysDiagnose2, False)]
    )
    def test_diagnose_run_stress_detect(self, ascend_ml, res, mocker, caplog):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "stress_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=ascend_ml())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B2 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        if res:
            self.assertTrue(AsysDiagnose().run() is res)
        else:
            AsysDiagnose().run()
            self.assertTrue("Run stress_detect failed" in caplog.text)

    @pytest.mark.parametrize(
        ["run_mode"], [("stress_detect",), ("hbm_detect",), ("cpu_detect",)]
    )
    def test_diagnose_uesr_error(self, mocker, run_mode):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = run_mode
            d = None
            output = None
            timeout = None

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=1000)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B3 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(not AsysDiagnose().run())

    @pytest.mark.parametrize(
        ["run_mode"], [("stress_detect",), ("hbm_detect",), ("cpu_detect",)]
    )
    def test_diagnose_soc_error(self, mocker, run_mode):
        self.assertTrue(True)

        class Args:
            subparser_name = "diagnose"
            r = run_mode
            d = None
            output = None
            timeout = None

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 9104 V1")
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(not AsysDiagnose().run())

    def test_diagnose_run_without_opp_kernel(self, mocker):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "stress_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(
            DeviceInfo, "get_chip_info", return_value="Ascend 910B4-1 V1"
        )
        mocker.patch("os.path.isfile", return_value=False)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is False)

    def test_diagnose_run_hbm_timeout_le_zero(self, mocker, caplog):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "hbm_detect"
            subparser_name = "diagnose"
            output = None
            timeout = -1

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is False)
        self.assertTrue(
            "The value of timeout must be in the range of [0, 604800]." in caplog.text
        )

    def test_diagnose_run_cpu_timeout_le_one(self, mocker, caplog):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "cpu_detect"
            subparser_name = "diagnose"
            output = None
            timeout = 0

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is False)
        self.assertTrue(
            "The value of timeout must be in the range of [1, 604800]." in caplog.text
        )

    def test_diagnose_run_hbm_timeout_not_int(self, mocker):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "hbm_detect"
            subparser_name = "diagnose"
            output = None
            timeout = [-3]

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B2 V1")
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        try:
            AsysDiagnose().run()
        except TypeError as e:
            self.assertTrue(
                "'<' not supported between instances of 'list' and 'int'" in str(e)
            )
        else:
            self.assertTrue(False)

    def test_diagnose_run_cpu_timeout_not_int(self, mocker):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "cpu_detect"
            subparser_name = "diagnose"
            output = None
            timeout = {-3}

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        try:
            AsysDiagnose().run()
        except TypeError as e:
            self.assertTrue(
                "'<' not supported between instances of 'set' and 'int'" in str(e)
            )
        else:
            self.assertTrue(False)

    def test_diagnose_run_hbm_aml_api_error(self, mocker, caplog):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "hbm_detect"
            subparser_name = "diagnose"
            output = None
            timeout = 5

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose2())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run())
        self.assertTrue(
            "Run hbm detect failed, error_msg: 'AsysDiagnose2' object has no attribute 'AmlHbmDetectWithType'"
            in caplog.text
        )

    def test_diagnose_run_cpu_aml_api_error(self, mocker, caplog):
        self.assertTrue(True)

        class Args:
            d = 0
            r = "cpu_detect"
            subparser_name = "diagnose"
            output = None
            timeout = 5

        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose2())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B4 V1")
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run())
        self.assertTrue(
            "Run cpu detect failed, error_msg: 'AsysDiagnose2' object has no attribute 'AmlCpuDetect'"
            in caplog.text
        )

    def test_diagnose_run_hbm_without_timeout(self, caplog):
        self.assertTrue(True)

        class HbmMocker:
            def get_ecc_isolated_page(self, a):
                return 0

        from common.interface import run_hbm

        ret = [1, 2]
        device_id = 1
        device_obj = HbmMocker()
        run_hbm(device_id, device_obj, ret)
        self.assertTrue(ret == [1, ["Warn", "0"]])
        self.assertTrue(
            "Run hbm detect failed, error_msg: 'HbmMocker' object has no attribute 'ascend_ml'"
            in caplog.text
        )

    def test_diagnose_run_cpu_master_id_error(self):
        from common.interface import run_cpu

        self.assertTrue(run_cpu(-1, 0, {}) == {-1: "Warn"})

    def test_diagnose_run_hbm_master_id_error(self):
        from common.interface import run_hbm

        self.assertTrue(run_hbm(-1, 0, {}) == {-1: ["Warn", "0"]})

    def test_diagnose_get_devices_master_id(self, mocker):
        from common.interface import get_devices_master_id

        self.assertTrue(True)

        class HalDevice:
            @staticmethod
            def get_phyid_from_logicid(device_id):
                return RetCode.FAILED

        self.assertTrue(get_devices_master_id(HalDevice(), [0]) == {0: 0})
        self.assertTrue(get_devices_master_id(HalDevice(), [0, 1]) == {0: -1, 1: -1})

    @pytest.mark.parametrize(["device_id"], [(False,), (0,), (1,), (2,), (3,)])
    def test_diagnose_device_error_d(self, device_id, mocker, caplog, capsys):
        self.assertTrue(True)

        class Args:
            d = device_id
            r = "stress_detect"
            subparser_name = "diagnose"
            output = None
            timeout = 5

        chip_info = "Unknown" if int(device_id) in [0, 1] else "Ascend 910B1 V1"
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        mocker.patch("common.interface.run_hbm", return_value={0: "Pass"})
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_info)
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())

        if device_id is False:
            self.assertTrue(not AsysDiagnose().run())
            self.assertTrue(
                "The diagnose command does not support on device_0: Unknown."
                in caplog.text
            )
            self.assertTrue(
                "The diagnose command does not support on device_3: Unknown."
                in caplog.text
            )
        elif device_id in [0, 1]:
            self.assertTrue(not AsysDiagnose().run())
            self.assertTrue(
                "The diagnose command does not support Unknown." in caplog.text
            )
        else:
            self.assertTrue(AsysDiagnose().run())
            except_msg = "| Stress Detect      | Pass                   |"
            captured = capsys.readouterr()
            self.assertTrue(except_msg in captured.out)

    @pytest.mark.parametrize(
        ["run_mode"],
        [("stress_detect",), ("cpu_detect",), ("hbm_detect",), ("component",)],
    )
    def test_diagnose_device_without_d(self, run_mode, mocker, caplog, capsys):
        self.assertTrue(True)

        class Args:
            d = False
            r = run_mode
            subparser_name = "diagnose"
            output = None
            timeout = 5

        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
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
        ParamDict().set_args(Args())

        AsysDiagnose().run()
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

    def test_diagnose_aicore_stl_950_pass(self, mocker, capsys):
        """aicore_stl_detect on Ascend950 with a passing device."""
        self.assertTrue(True)

        class Args:
            d = 0
            r = "aicore_stl_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mocker.patch(
            "drv.LoadSoType.get_aml_aicore_stl", return_value=AsysStlDiagnose0()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)
        except_msg = "AICore STL Detect"
        captured = capsys.readouterr()
        self.assertTrue(except_msg in captured.out)

    def test_diagnose_aicore_stl_950_fail(self, mocker):
        """aicore_stl_detect on Ascend950 with a failing device returns Warn but run() True."""
        self.assertTrue(True)

        class Args:
            d = 0
            r = "aicore_stl_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mocker.patch(
            "drv.LoadSoType.get_aml_aicore_stl", return_value=AsysStlDiagnose1()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)

    def test_diagnose_aicore_stl_not_950(self, mocker, caplog):
        """aicore_stl_detect is intercepted on unsupported chips (e.g. 910B)."""
        self.assertTrue(True)

        class Args:
            d = 0
            r = "aicore_stl_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mocker.patch(
            "drv.LoadSoType.get_aml_aicore_stl", return_value=AsysStlDiagnose0()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 910B1 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is False)
        self.assertTrue(
            "The aicore_stl_detect mode is only supported on Ascend950 and "
            "Ascend960DT." in caplog.text
        )

    def test_diagnose_aicore_stl_960dt_pass(self, mocker, capsys):
        """aicore_stl_detect on Ascend960DT with a passing device."""
        self.assertTrue(True)

        class Args:
            d = 0
            r = "aicore_stl_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mocker.patch(
            "drv.LoadSoType.get_aml_aicore_stl", return_value=AsysStlDiagnose0()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 960DT V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)
        except_msg = "AICore STL Detect"
        captured = capsys.readouterr()
        self.assertTrue(except_msg in captured.out)

    def test_diagnose_aicore_stl_960pr_intercepted(self, mocker, caplog):
        """aicore_stl_detect is intercepted on Ascend960PR (960 family, DT only)."""
        self.assertTrue(True)

        class Args:
            d = 0
            r = "aicore_stl_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mocker.patch(
            "drv.LoadSoType.get_aml_aicore_stl", return_value=AsysStlDiagnose0()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 960PR V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is False)
        self.assertTrue(
            "The aicore_stl_detect mode is only supported on Ascend950 and "
            "Ascend960DT." in caplog.text
        )

    def test_diagnose_aicore_stl_no_so(self, mocker):
        """aicore_stl_detect fails fast when libaml_aicore_stl.so is not loaded."""
        self.assertTrue(True)

        class Args:
            d = 0
            r = "aicore_stl_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mocker.patch("drv.LoadSoType.get_aml_aicore_stl", return_value=RetCode.FAILED)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is False)

    def test_diagnose_aicore_stl_timeout_ignored(self, mocker, caplog):
        """--timeout is accepted but warned-and-ignored for aicore_stl_detect."""
        self.assertTrue(True)
        import logging

        caplog.set_level(logging.WARNING)

        class Args:
            d = 0
            r = "aicore_stl_detect"
            subparser_name = "diagnose"
            output = None
            timeout = 90

        mocker.patch(
            "drv.LoadSoType.get_aml_aicore_stl", return_value=AsysStlDiagnose0()
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        warning_log = mocker.spy(asys_diagnose, "log_warning")
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysDiagnose().run() is True)
        warning_msg = "The --timeout argument is not supported in aicore_stl_detect mode and will be ignored."
        self.assertTrue(warning_msg in caplog.text)
        warning_log.assert_any_call(warning_msg, force=True)

    def test_diagnose_aicore_stl_loads_so(self, mocker):
        """aicore_stl_detect loads libaml_aicore_stl.so and assigns it to device_obj.aml_aicore_stl."""
        self.assertTrue(True)

        class Args:
            d = 0
            r = "aicore_stl_detect"
            subparser_name = "diagnose"
            output = None
            timeout = None

        mock_stl = AsysStlDiagnose0()
        mocker.patch("drv.LoadSoType.get_aml_aicore_stl", return_value=mock_stl)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("diagnose.asys_diagnose.run_linux_cmd", return_value=True)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        diag = AsysDiagnose()
        result = diag.run()
        self.assertTrue(result is True)
        self.assertTrue(diag.device_obj.aml_aicore_stl is mock_stl)

    def test_diagnose_run_aicore_stl_master_id_error(self):
        from common.interface import run_aicore_stl

        self.assertTrue(run_aicore_stl(-1, 0, {}) == {-1: "Warn"})

    def test_diagnose_run_aicore_stl_no_handle(self, caplog):
        from common.interface import run_aicore_stl

        class StlMocker:
            aml_aicore_stl = None

        ret = {}
        run_aicore_stl(1, StlMocker(), ret)
        self.assertTrue(ret == {1: "Warn"})
        self.assertTrue("libaml_aicore_stl.so is not loaded" in caplog.text)

    def test_diagnose_run_aicore_stl_api_error(self, caplog):
        from common.interface import run_aicore_stl

        class StlMocker:
            aml_aicore_stl = AsysDiagnose2()  # no AmlAicoreStlDetect attribute

        ret = {}
        run_aicore_stl(0, StlMocker(), ret)
        self.assertTrue(ret == {0: "Warn"})
        self.assertTrue("Run aicore_stl_detect failed" in caplog.text)

    def test_diagnose_env_detect_device_zero(self, mocker, caplog, capsys):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        mocker.patch.object(ParamDict, "get_arg", return_value=0)
        diagnose = AsysDiagnose()
        self.assertTrue(diagnose.env_detect("component"))

    def test_diagnose_env_detect_not_have_msaicerr(self, mocker, caplog, capsys):
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        mocker.patch.object(ParamDict, "get_arg", return_value=0)
        mocker.patch("os.path.exists", return_value=False)
        diagnose = AsysDiagnose()
        self.assertTrue(not diagnose.env_detect("component"))

    def test_diagnose_env_detect_not_have_w_permission(self, mocker, caplog, capsys):
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        mocker.patch.object(ParamDict, "get_arg", return_value=False)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(FileOperate, "check_access", return_value=False)
        mocker.patch.object(Path, "exists", return_value=True)
        open_log = mocker.patch.object(asys_diagnose, "open_log", create=True)
        close_log = mocker.patch.object(asys_diagnose, "close_log", create=True)
        diagnose = AsysDiagnose()
        self.assertTrue(not diagnose.env_detect("component"))
        self.assertTrue(
            "The current directory or debug_info.txt is immutable, Please check"
            in caplog.text
        )
        open_log.assert_not_called()
        close_log.assert_not_called()

    def test_diagnose_env_detect_device_eq_zero(self, mocker, caplog, capsys):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=0)
        mocker.patch.object(ParamDict, "get_arg", return_value=False)
        diagnose = AsysDiagnose()
        self.assertTrue(not diagnose.env_detect("component"))

    def test_diagnose_env_detect(self, mocker):
        fake_ret = subprocess.Popen(
            "lsas",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(ParamDict, "get_arg", return_value=False)
        mocker.patch.object(Path, "exists", return_value=False)
        diagnose = AsysDiagnose()
        self.assertTrue(not diagnose.env_detect("component"))

    @pytest.mark.parametrize(
        ["run_mode"],
        [("stress_detect",), ("cpu_detect",), ("hbm_detect",), ("component",)],
    )
    def test_diagnose_device_without_a3(self, run_mode, mocker, caplog, capsys):
        self.assertTrue(True)

        class Args:
            d = False
            r = run_mode
            subparser_name = "diagnose"
            output = None
            timeout = 5

        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=AsysDiagnose0())
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=4)
        ret = (
            {2: ["Pass", "0"], 3: ["Pass", "0"]}
            if run_mode == "hbm_detect"
            else {2: "Pass", 3: "Pass"}
        )
        mocker.patch("common.interface.run_diagnose", return_value=ret)
        mocker.patch(
            "diagnose.asys_diagnose.AsysDiagnose.get_diagnose_devices_chip_info",
            return_value=([2, 3], "Ascend 910_93"),
        )
        mocker.patch(
            "diagnose.asys_diagnose.AsysDiagnose._check_support", return_value=True
        )
        mocker.patch("os.getuid", return_value=0)
        mocker.patch("os.path.exists", return_value=True)

        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())

        AsysDiagnose().run()
        if run_mode == "stress_detect":
            except_msg = """\r-\r\r\\\r\r|\r\r/\r
 +------------------------+-----------------------------+
 | Group of 4 Device      | Diagnostic Result           |
 +========================+=============================+
 +--- Performance --------+-----------------------------+
 | Stress Detect          | Warn, Warn, Pass, Pass      |
 +------------------------+-----------------------------+
"""
        elif run_mode == "cpu_detect":
            except_msg = """\r-\r\r\\\r\r|\r\r/\r
 +------------------------+-----------------------------+
 | Group of 4 Device      | Diagnostic Result           |
 +========================+=============================+
 +--- Hardware -----------+-----------------------------+
 | CPU Detect             | Warn, Warn, Pass, Pass      |
 +------------------------+-----------------------------+
"""
        elif run_mode == "hbm_detect":
            except_msg = """\r-\r\r\\\r\r|\r\r/\r
 +------------------------+-----------------------------+
 | Group of 4 Device      | Diagnostic Result           |
 +========================+=============================+
 +--- Hardware -----------+-----------------------------+
 | HBM Detect             | Warn, Warn, Pass, Pass      |
 |                        | (0, 0, -, -)                |
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
