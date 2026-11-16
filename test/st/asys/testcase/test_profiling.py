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

from .conftest import CONF_SRC_PATH, test_case_tmp
from .conftest import AssertTest
from .conftest import enter_test_tmp, restore_cwd


import asys
from params import ParamDict
from common.device import DeviceInfo
from common.chip_handler import g_device_map


class RunResult:
    """mock the return value of subprocess.run"""

    def __init__(self, returncode=0, stdout="msprof done"):
        self.returncode = returncode
        self.stdout = stdout


class TestProfiling(AssertTest):
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

    @pytest.fixture(autouse=True)
    def mock_device_count(self, mocker):
        # 适配无昇腾 NPU 卡环境：mock 设备数量，避免 '-d' 参数校验失败
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)

    def test_asys_profiling_all_run_modes(self, mocker):
        """
        正常用例：910B 芯片下运行全部 run_mode，覆盖各 concat_* 拼接分支
        """
        captured = {}

        def fake_run(cmd, *_args, **_kwargs):
            captured["cmd"] = (
                cmd[2]
                if isinstance(cmd, list) and len(cmd) == 3 and cmd[1] == "-c"
                else cmd
            )
            return RunResult(returncode=0)

        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="910B1")
        mocker.patch("profiling.asys_profiling.subprocess.run", side_effect=fake_run)
        sys.argv = [
            CONF_SRC_PATH,
            "profiling",
            "-d=0",
            "-p=1",
            "-r=aicore,dvpp,os,link,memory,power",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        cmd = captured["cmd"]
        self.assertTrue("--aic-metrics=PipeUtilization" in cmd)
        self.assertTrue("--dvpp-profiling=on" in cmd)
        self.assertTrue("--sys-profiling=on" in cmd)
        self.assertTrue("--sys-interconnection-profiling=on" in cmd)
        self.assertTrue("--sys-hardware-mem=on" in cmd)

    def test_asys_profiling_power_lp_mode(self, mocker):
        """
        正常用例：950 芯片 need_lp_param 为真，power 走 --sys-lp=on 分支
        """
        captured = {}

        def fake_run(cmd, *_args, **_kwargs):
            captured["cmd"] = (
                cmd[2]
                if isinstance(cmd, list) and len(cmd) == 3 and cmd[1] == "-c"
                else cmd
            )
            return RunResult(returncode=0)

        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("profiling.asys_profiling.subprocess.run", side_effect=fake_run)
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=1", "-r=power"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue("--sys-lp=on" in captured["cmd"])

    def test_asys_profiling_power_aic_mode(self, mocker):
        """
        正常用例：910B need_lp_param 为假且 run_mode 不含 aicore，power 走 --ai-core=on 分支
        """
        captured = {}

        def fake_run(cmd, *_args, **_kwargs):
            captured["cmd"] = (
                cmd[2]
                if isinstance(cmd, list) and len(cmd) == 3 and cmd[1] == "-c"
                else cmd
            )
            return RunResult(returncode=0)

        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="910B1")
        mocker.patch("profiling.asys_profiling.subprocess.run", side_effect=fake_run)
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=1", "-r=power"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue("--ai-core=on" in captured["cmd"])

    def test_asys_profiling_output_path(self, mocker):
        """
        正常用例：指定 output 时结果目录拼接在 output 下
        """
        captured = {}

        def fake_run(cmd, *_args, **_kwargs):
            captured["cmd"] = (
                cmd[2]
                if isinstance(cmd, list) and len(cmd) == 3 and cmd[1] == "-c"
                else cmd
            )
            return RunResult(returncode=0)

        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="910B1")
        mocker.patch("profiling.asys_profiling.subprocess.run", side_effect=fake_run)
        sys.argv = [
            CONF_SRC_PATH,
            "profiling",
            "-d=0",
            "-p=1",
            "-r=aicore",
            "--output=%s" % test_case_tmp,
            "--aic_metrics=Memory",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue("--aic-metrics=Memory" in captured["cmd"])
        self.assertTrue(
            "--output=%s" % os.path.join(test_case_tmp, "asys_profiling_result_")
            in captured["cmd"]
        )

    def test_asys_profiling_period_invalid(self, mocker, caplog):
        """
        异常用例：period 超出 [1, 2592000] 范围
        """
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="910B1")
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=2592001", "-r=aicore"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("Period is invalid" in caplog.text)

    def test_asys_profiling_chip_unsupported(self, mocker, caplog):
        """
        异常用例：芯片类型不支持 profiling
        """
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend310P")
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=1", "-r=aicore"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("does not support" in caplog.text)

    def test_asys_profiling_device_id_invalid(self, mocker, caplog):
        """
        异常用例：device id 无效，get_chip_info 返回 Unknown
        """
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Unknown")
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=1", "-r=aicore"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("is invalid" in caplog.text)

    def test_asys_profiling_run_mode_unsupported(self, mocker, caplog):
        """
        异常用例：run_mode 含不支持的类型
        """
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="910B1")
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=1", "-r=aicore,badmode"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("Run mode type is unsupported" in caplog.text)

    def test_asys_profiling_msprof_failed(self, mocker, caplog):
        """
        异常用例：msprof 命令执行返回非 0
        """
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="910B1")
        mocker.patch(
            "profiling.asys_profiling.subprocess.run",
            return_value=RunResult(returncode=1, stdout="msprof error"),
        )
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=1", "-r=aicore"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("Failed to run profiling" in caplog.text)

    def test_asys_profiling_dvpp_unsupported_91096(self, mocker, caplog):
        """
        异常用例：Ascend960 无 dvpp 硬件，-r=dvpp 应被拦截并明确报错
        """
        fake_run = mocker.patch("profiling.asys_profiling.subprocess.run")
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="960")
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=1", "-r=dvpp"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("does not support dvpp" in caplog.text)
        fake_run.assert_not_called()

    def test_asys_profiling_dvpp_unsupported_91096_mixed(self, mocker, caplog):
        """
        异常用例：Ascend960 混合 run_mode 含 dvpp 同样被拦截
        """
        fake_run = mocker.patch("profiling.asys_profiling.subprocess.run")
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="960")
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=1", "-r=aicore,dvpp"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("does not support dvpp" in caplog.text)
        fake_run.assert_not_called()

    def test_asys_profiling_dvpp_supported_950(self, mocker):
        """
        正常用例：950 芯片支持 dvpp，仍拼接 --dvpp-profiling=on
        """
        captured = {}

        def fake_run(cmd, *_args, **_kwargs):
            captured["cmd"] = (
                cmd[2]
                if isinstance(cmd, list) and len(cmd) == 3 and cmd[1] == "-c"
                else cmd
            )
            return RunResult(returncode=0)

        mocker.patch.object(DeviceInfo, "get_chip_info", return_value="Ascend 950 V1")
        mocker.patch("profiling.asys_profiling.subprocess.run", side_effect=fake_run)
        sys.argv = [CONF_SRC_PATH, "profiling", "-d=0", "-p=1", "-r=dvpp"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue("--dvpp-profiling=on" in captured["cmd"])
