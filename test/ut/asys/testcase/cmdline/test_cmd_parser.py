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
from argparse import Namespace

from testcase.conftest import get_root, ut_root_path


from cmdline import CommandLineParser
from params import ParamDict
from common.const import RetCode
from common import DeviceInfo
from ..conftest import AssertTest


def setup_module():
    print("TestCmdParser ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestCmdParser ut test finish.")  # noqa: T201  # test diagnostic output


class TestCmdParser(AssertTest):
    def setup_method(self):
        self.parser = CommandLineParser()

    def teardown_method(self):
        ParamDict.clear()

    def test_parse_collect_default(self, mocker):
        fake_namespace = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r=None,
            remote=None,
            all=None,
            quiet=None,
            timeout=None,
        )
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=fake_namespace)
        self.parser.parse()
        self.assertTrue(ParamDict().get_command() == "collect")

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [
            ("--task_dir", "' '"),
            ("--task_dir", ""),
            ("--task_dir", "\\out"),
            ("--task_dir", "{}/no_exist_dir".format(get_root())),
        ],
    )
    def test_parse_collect_invalid_task_dir(self, mocker, arg_name, arg_val):
        fake_namespace = Namespace(
            subparser_name="collect",
            task_dir=arg_val,
            output=None,
            tar=None,
            r=None,
            remote=None,
            all=None,
            quiet=None,
        )
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=fake_namespace)
        self.assertTrue(self.parser.parse() == RetCode.FAILED)

    def test_parse_launch_default(self, mocker):
        task_script = "bash {}/st/data/asys_test_dir/test.bash".format(get_root())
        fake_namespace = Namespace(
            subparser_name="launch", task=task_script, output=None, tar=None
        )
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=fake_namespace)
        self.parser.parse()
        self.assertTrue(ParamDict().get_command() == "launch")
        self.assertTrue(ParamDict().get_arg("task") == task_script)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"], [("--task", ""), ("--task", "    ")]
    )
    def test_parse_launch_invalid_task(self, mocker, arg_name, arg_val):
        fake_namespace = Namespace(
            subparser_name="launch", task=arg_val, output=None, tar=None
        )
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=fake_namespace)
        self.assertTrue(self.parser.parse() == RetCode.FAILED)

    def test_parse_detect_default(self, mocker):
        fake_namespace = Namespace(subparser_name="detect", output=None, tar=None)
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=fake_namespace)
        ParamDict().set_env_type("RC")
        self.assertTrue(self.parser.parse() == RetCode.FAILED)

    def test_parse_analyze_file(self, mocker):
        file_path = os.path.join(ut_root_path, "data", "atrace", "test", "test.txt")
        fake_namespace = Namespace(
            subparser_name="analyze",
            r="trace",
            file=file_path,
            path=None,
            exe_file=None,
            reg=2,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=None,
            d=0,
        )
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=fake_namespace)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(ParamDict, "get_env_type", return_value="EP")
        self.assertTrue(self.parser.parse() == RetCode.SUCCESS)

    def test_parse_analyze_path(self, mocker):
        dir_path = os.path.join(ut_root_path, "data", "atrace", "test")
        fake_namespace = Namespace(
            subparser_name="analyze",
            r="trace",
            file=None,
            path=dir_path,
            exe_file=None,
            reg=2,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=None,
            d=0,
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(ParamDict, "get_env_type", return_value="EP")
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=fake_namespace)
        self.assertTrue(self.parser.parse() == RetCode.SUCCESS)
