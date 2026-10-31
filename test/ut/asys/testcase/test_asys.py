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
import runpy
import sys
import pytest

from .conftest import ASYS_MAIN_PATH, ASYS_SRC_PATH, CONF_SRC_PATH, ut_root_path
from .conftest import AssertTest


import asys
from params import ParamDict
from common.const import RetCode
from collect import AsysCollect
from launch import AsysLaunch
from info import AsysInfo
from diagnose import AsysDiagnose
from health import AsysHealth
from analyze import AsysAnalyze
from config_cmd import AsysConfig


def setup_module():
    print("TestAsysMain ut test start.")  # noqa: T201  # test diagnostic output
    os.chdir(ut_root_path)
    ParamDict().set_env_type("EP")


def teardown_module():
    print("TestAsysMain ut test finish.")  # noqa: T201  # test diagnostic output
    ParamDict.clear()


class TestAsysMain(AssertTest):
    sub_cmd_class = {
        "collect": "collect.asys_collect.AsysCollect.run",
        "launch": "launch.asys_launch.AsysLaunch.run",
        "diagnose": "diagnose.asys_diagnose.AsysDiagnose.run",
        "health": "health.asys_health.AsysHealth.run",
        "info": "info.asys_info.AsysInfo.run",
        "analyze": "analyze.asys_analyze.AsysAnalyze.run",
        "config": "config_cmd.asys_config.AsysConfig.run",
    }

    def test_main_no_args(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=None)
        mocker.patch("cmdline.CommandLineParser.parse", return_value=RetCode.SUCCESS)
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(
        "sub_cmd",
        ["collect", "launch", "diagnose", "health", "info", "analyze", "config"],
    )
    def test_main_success(self, mocker, sub_cmd):
        mocker.patch("common.FileOperate.create_dir", return_value=RetCode.SUCCESS)
        mocker.patch("cmdline.cmd_parser.CommandLineParser.parse", return_value=True)
        mocker.patch("config.config_parser.AsysConfigParser.parse", return_value=True)
        mocker.patch("params.param_dict.ParamDict.get_command", return_value=sub_cmd)
        mocker.patch(self.sub_cmd_class[sub_cmd], return_value=True)
        self.assertTrue(asys.main())

    def test_main_collect_stacktrace_success(self, mocker):
        mocker.patch("common.FileOperate.create_dir", return_value=RetCode.SUCCESS)
        mocker.patch("cmdline.cmd_parser.CommandLineParser.parse", return_value=True)
        mocker.patch("config.config_parser.AsysConfigParser.parse", return_value=True)
        mocker.patch("params.param_dict.ParamDict.get_command", return_value="collect")
        mocker.patch("params.param_dict.ParamDict.get_arg", return_value="stacktrace")
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace.run",
            return_value=True,
        )
        mocker.patch("os.access", return_value=True)
        self.assertTrue(asys.main())

    def test_main_confparse_failed(self, mocker):
        mocker.patch("common.FileOperate.create_dir", return_value=RetCode.SUCCESS)
        mocker.patch("cmdline.cmd_parser.CommandLineParser.parse", return_value=True)
        mocker.patch("config.config_parser.AsysConfigParser.parse", return_value=False)
        self.assertTrue(not asys.main())

    @pytest.mark.parametrize(
        "sub_cmd",
        ["collect", "launch", "diagnose", "health", "info", "analyze", "config"],
    )
    def test_main_each_command_execute_failed(self, mocker, sub_cmd):
        mocker.patch("common.FileOperate.create_dir", return_value=RetCode.SUCCESS)
        mocker.patch("cmdline.cmd_parser.CommandLineParser.parse", return_value=True)
        mocker.patch("config.config_parser.AsysConfigParser.parse", return_value=True)
        mocker.patch("params.param_dict.ParamDict.get_command", return_value=sub_cmd)
        mocker.patch(self.sub_cmd_class[sub_cmd], return_value=False)
        self.assertTrue(not asys.main())

    def test_main_env_type_error(self, mocker, caplog):
        mocker.patch("common.FileOperate.create_dir", return_value=RetCode.SUCCESS)
        mocker.patch("cmdline.cmd_parser.CommandLineParser.parse", return_value=True)
        mocker.patch("config.config_parser.AsysConfigParser.parse", return_value=True)
        mocker.patch("params.param_dict.ParamDict.get_command", return_value="collect")
        mocker.patch(self.sub_cmd_class["collect"], return_value=False)
        mocker.patch("params.param_dict.ParamDict.get_env_type", return_value="")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "Failed to obtain the execution environment type." in caplog.text
        )

    def test_main_conf_parser_error(self, mocker, caplog):
        mocker.patch("common.FileOperate.create_dir", return_value=RetCode.SUCCESS)
        mocker.patch("cmdline.cmd_parser.CommandLineParser.parse", return_value=True)
        mocker.patch("config.config_parser.AsysConfigParser.parse", return_value=False)
        mocker.patch("params.param_dict.ParamDict.get_command", return_value="launch")
        mocker.patch(self.sub_cmd_class["launch"], return_value=False)
        self.assertTrue(not asys.main())
        self.assertTrue("Configs parse failed, asys exit." in caplog.text)

    def test_main_create_out_timestamp_dir_error(self, mocker, caplog):
        mocker.patch("common.FileOperate.create_dir", return_value=RetCode.SUCCESS)
        mocker.patch("cmdline.cmd_parser.CommandLineParser.parse", return_value=True)
        mocker.patch("config.config_parser.AsysConfigParser.parse", return_value=True)
        mocker.patch("params.param_dict.ParamDict.get_command", return_value="analyze")
        mocker.patch(self.sub_cmd_class["analyze"], return_value=False)
        mocker.patch("os.access", return_value=False)
        self.assertTrue(not asys.main())
        self.assertTrue("Create asys output directory failed." in caplog.text)

    def test_main_check_args_duplicate_error(self, caplog):
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "--output=/home",
            "--output=/home/test",
            "--tar=True",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("--tar" in caplog.text)
        self.assertTrue("--output" in caplog.text)
        self.assertTrue("args can be specified" in caplog.text)

    @pytest.mark.parametrize(
        ["sub_cmd", "obj", "result"],
        [
            ("collect", AsysCollect, True),
            ("collect -r=stacktrace", AsysCollect, False),
            ("launch", AsysLaunch, True),
            ("diagnose", AsysDiagnose, False),
            ("health", AsysHealth, False),
            ("info", AsysInfo, False),
            ("analyze", AsysAnalyze, False),
            ("config", AsysConfig, False),
        ],
    )
    def test_main_check_rc_env_command(self, sub_cmd, obj, result, mocker, caplog):
        mocker.patch("common.FileOperate.create_dir", return_value=RetCode.SUCCESS)
        mocker.patch("cmdline.cmd_parser.CommandLineParser.parse", return_value=True)
        mocker.patch("config.config_parser.AsysConfigParser.parse", return_value=True)
        mocker.patch("params.param_dict.ParamDict.get_command", return_value=sub_cmd)
        mocker.patch.object(obj, "run", return_value=True)

        sys.argv = [CONF_SRC_PATH, sub_cmd]
        ParamDict().set_env_type("RC")

        self.assertTrue(asys.main() is result)
        if result:
            self.assertTrue(
                "The RC supports the launch command and the collect command without the -r parameter."
                not in caplog.text
            )
        else:
            self.assertTrue(
                "The RC supports the launch command and the collect command without the -r parameter."
                in caplog.text
            )

    def test_clean_env(self, mocker):
        mocker.patch("common.FileOperate.create_dir", return_value=RetCode.SUCCESS)
        mocker.patch(
            "cmdline.cmd_parser.CommandLineParser.parse", side_effect=SystemExit(2)
        )
        mocker.patch("config.config_parser.AsysConfigParser.parse", return_value=True)
        mocker.patch("params.param_dict.ParamDict.get_command", return_value="collect")
        mocker.patch(self.sub_cmd_class["collect"], return_value=True)
        self.assertTrue(not asys.main())
        check = False
        asys.clean_pycache()
        for root, dirs, files in os.walk(ASYS_SRC_PATH):
            if "__pycache__" in dirs:
                check = True
        self.assertTrue(not check)

    @pytest.mark.parametrize(("result", "expected"), [(True, 0), (False, 1)])
    def test_cli_exit_code_reflects_main_result(self, mocker, result, expected):
        mocker.patch("asys.main", return_value=result)
        mocker.patch("asys.clean_pycache")
        self.assertTrue(asys._run_cli() == expected)

    @pytest.mark.parametrize(
        ("parse_exit_code", "expected"), [(None, 0), (0, 0), (2, 1)]
    )
    def test_main_guard_propagates_exit_code(
        self, monkeypatch, mocker, parse_exit_code, expected
    ):
        mocker.patch(
            "cmdline.cmd_parser.CommandLineParser.parse",
            side_effect=SystemExit(parse_exit_code),
        )
        monkeypatch.setattr(sys, "argv", [ASYS_MAIN_PATH, "collect"])
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_path(ASYS_MAIN_PATH, run_name="__main__")
        self.assertTrue(exc_info.value.code == expected)
