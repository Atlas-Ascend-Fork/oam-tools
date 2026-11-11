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

from testcase.conftest import ut_root_path

from cmdline.arg_checker import check_arg_exist_dir, check_arg_create_dir, check_arg_tar
from cmdline.arg_checker import check_arg_executable, check_arg_device_id
from cmdline.arg_checker import check_arg_exist_or_read_permissibale
from cmdline.arg_checker import check_core_file, check_symbol_path
from common.const import RetCode
from common import DeviceInfo
from ..conftest import AssertTest


def setup_module():
    print("TestArgChecker ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestArgChecker ut test finish.")  # noqa: T201  # test diagnostic output


class TestArgChecker(AssertTest):
    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    @pytest.mark.parametrize("arg_val", [""])
    def test_empty_str(self, arg_val):
        arg_name = "test_arg"
        self.assertTrue(check_arg_exist_dir(arg_name, arg_val) != RetCode.SUCCESS)
        self.assertTrue(check_arg_create_dir(arg_name, arg_val) != RetCode.SUCCESS)
        self.assertTrue(check_arg_executable(arg_name, arg_val) != RetCode.SUCCESS)

    @pytest.mark.parametrize("arg_val", [" ", "    "])
    def test_space(self, arg_val):
        arg_name = "test_arg"
        self.assertTrue(check_arg_exist_dir(arg_name, arg_val) != RetCode.SUCCESS)
        self.assertTrue(check_arg_create_dir(arg_name, arg_val) != RetCode.SUCCESS)

    @pytest.mark.parametrize(
        "arg_val",
        [
            "\\",
            "^",
            "$",
            "%",
            "&",
            "*",
            "+",
            "|",
            "#",
            "~",
            "`",
            "=",
            "<",
            ">",
            ",",
            "?",
            "!",
            ":",
            ";",
            "'",
            '"',
            "[",
            "]",
            "(",
            ")",
            "{",
            "}",
        ],
    )
    def test_illegal_char(self, arg_val):
        arg_name = "test_arg"
        self.assertTrue(check_arg_exist_dir(arg_name, arg_val) != RetCode.SUCCESS)
        self.assertTrue(check_arg_create_dir(arg_name, arg_val) != RetCode.SUCCESS)

    @pytest.mark.parametrize("arg_val", ["/test_not_exist_dir"])
    def test_root_dir_not_exist(self, mocker, arg_val):
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch("os.access", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("cmdline.arg_checker.f.create_dir")
        arg_name = "test_arg"
        self.assertTrue(check_arg_create_dir(arg_name, arg_val) == RetCode.SUCCESS)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val", "test_res"],
        [
            ("task", "", RetCode.ARG_EMPTY_STRING),
            ("task", " ", RetCode.ARG_EMPTY_STRING),
            ("task", "./test.bash", RetCode.SUCCESS),
            ("task", "bash", RetCode.ARG_NO_EXECUTABLE),
            ("task", " bash", RetCode.ARG_NO_EXECUTABLE),
            ("task", "bash ", RetCode.ARG_NO_EXECUTABLE),
            ("task", " bash ", RetCode.ARG_NO_EXECUTABLE),
            ("task", "bash ./data/asys_test_dir/test", RetCode.ARG_NO_EXECUTABLE),
            ("task", "bash test1sh", RetCode.ARG_NO_EXECUTABLE),
            ("task", "bash sh", RetCode.ARG_NO_EXECUTABLE),
            ("task", "bash bash", RetCode.ARG_NO_EXECUTABLE),
            ("task", "bash test test.sh", RetCode.SUCCESS),
            ("task", "~/bash ", RetCode.ARG_NO_EXECUTABLE),
            ("task", "~/bash test.py", RetCode.ARG_NO_EXECUTABLE),
            ("task", "~/bash test test2bash", RetCode.ARG_NO_EXECUTABLE),
            ("task", "./sh ", RetCode.ARG_NO_EXECUTABLE),
            ("task", "./sh test1.py test2sh", RetCode.ARG_NO_EXECUTABLE),
            ("task", "./sh test1sh test2.py", RetCode.ARG_NO_EXECUTABLE),
            ("task", "./sh test1sh test2.sh", RetCode.SUCCESS),
            ("task", "/bin/sh test1sh test2.py", RetCode.ARG_NO_EXECUTABLE),
            ("task", "/bin/bash test1sh test2.py", RetCode.ARG_NO_EXECUTABLE),
            ("task", "python", RetCode.ARG_NO_EXECUTABLE),
            ("task", " python ", RetCode.ARG_NO_EXECUTABLE),
            ("task", "python3", RetCode.ARG_NO_EXECUTABLE),
            ("task", " python3 ", RetCode.ARG_NO_EXECUTABLE),
            ("task", "python3 test1py test.py", RetCode.SUCCESS),
            ("task", "python3 test.sh", RetCode.ARG_NO_EXECUTABLE),
            ("task", "python3 test.bash", RetCode.ARG_NO_EXECUTABLE),
            ("task", "/usr/bin/python3.7 ", RetCode.ARG_NO_EXECUTABLE),
            ("task", "/usr/bin/python3.7 test", RetCode.ARG_NO_EXECUTABLE),
            ("task", "/usr/bin/python3.7 test.sh", RetCode.ARG_NO_EXECUTABLE),
            ("task", "/usr/bin/python3.7 test test.py", RetCode.SUCCESS),
            ("task", " test_sh ", RetCode.SUCCESS),
            ("task", "test_bash", RetCode.SUCCESS),
            ("task", "test_python", RetCode.SUCCESS),
            ("task", "./sh test.sh", RetCode.SUCCESS),
            ("task", "/bin/sh test.sh test1", RetCode.SUCCESS),
            ("task", "~/sh test.bash", RetCode.SUCCESS),
            ("task", "../sh test.bash test1", RetCode.SUCCESS),
            ("task", "./bash test.sh", RetCode.SUCCESS),
            ("task", "/bin/bash test.sh test1", RetCode.SUCCESS),
            ("task", "~/bash test.bash", RetCode.SUCCESS),
            ("task", "../bash test.bash test1", RetCode.SUCCESS),
            ("task", "python test.py", RetCode.SUCCESS),
            ("task", "./python3.7.5 test.py", RetCode.SUCCESS),
            ("task", "~/python3.11.0 test.py", RetCode.SUCCESS),
            (
                "task",
                "/usr/local/python3.7.5/bin/python3 test.py test2",
                RetCode.SUCCESS,
            ),
        ],
    )
    def test_check_arg_executable(self, mocker, arg_name, arg_val, test_res):
        mocker.patch("os.path.exists", return_value=True)
        self.assertTrue(check_arg_executable(arg_name, arg_val) == test_res)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val", "test_res"],
        [
            ("task_dir", "", RetCode.ARG_EMPTY_STRING),
            ("task_dir", "  ", RetCode.ARG_SAPCE_STRING),
            (
                "task_dir",
                "\\" + os.path.join(ut_root_path, "not_exist_dir"),
                RetCode.ARG_ILLEGAL_STRING,
            ),
            (
                "task_dir",
                os.path.join(ut_root_path, "not_exist_dir"),
                RetCode.ARG_NO_EXIST_DIR,
            ),
            ("task_dir", ut_root_path, RetCode.SUCCESS),
        ],
    )
    def test_check_arg_exist_dir(self, mocker, arg_name, arg_val, test_res):
        self.assertTrue(check_arg_exist_dir(arg_name, arg_val) == test_res)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val", "test_res"],
        [
            ("output", "", RetCode.ARG_EMPTY_STRING),
            ("output", "  ", RetCode.ARG_SAPCE_STRING),
            (
                "output",
                "\\" + os.path.join(ut_root_path, "not_exist_dir"),
                RetCode.ARG_ILLEGAL_STRING,
            ),
            ("output", ut_root_path, RetCode.ARG_NO_WRITABLE_PERMISSION),
            (
                "output",
                os.path.join(ut_root_path, "no_exist_dir_1", "no_exist_dir_2"),
                RetCode.SUCCESS,
            ),
            ("output", ut_root_path, RetCode.SUCCESS),
        ],
    )
    def test_check_arg_create_dir(self, mocker, arg_name, arg_val, test_res):
        if test_res == RetCode.ARG_NO_WRITABLE_PERMISSION:
            mocker.patch("os.path.exists", return_value=True)
            mocker.patch("os.path.isdir", return_value=True)
            mocker.patch("os.access", return_value=False)
        if arg_val == os.path.join(ut_root_path, "no_exist_dir_1", "no_exist_dir_2"):
            mocker.patch("common.file_operate.FileOperate.create_dir")
        self.assertTrue(check_arg_create_dir(arg_name, arg_val) == test_res)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val", "test_res"],
        [
            ("tar", "zzz", RetCode.FAILED),
            ("tar", "T", RetCode.SUCCESS),
            ("tar", "t", RetCode.SUCCESS),
            ("tar", "False", RetCode.SUCCESS),
        ],
    )
    def test_check_arg_tar(self, arg_name, arg_val, test_res):
        self.assertTrue(check_arg_tar(arg_name, arg_val) == test_res)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val", "test_res"],
        [
            ("d", -1, RetCode.FAILED),
            ("d", 0, RetCode.SUCCESS),
            ("d", 63, RetCode.SUCCESS),
        ],
    )
    def test_check_arg_device(self, mocker, arg_name, arg_val, test_res):
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=64)
        self.assertTrue(check_arg_device_id(arg_name, arg_val) == test_res)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val", "test_res"],
        [
            (
                "file",
                os.path.join(ut_root_path, "data", "atrace", "test", "test.txt"),
                RetCode.SUCCESS,
            ),
            ("path", ut_root_path, RetCode.SUCCESS),
            ("file", ut_root_path, RetCode.FAILED),
            (
                "path",
                os.path.join(ut_root_path, "data", "atrace", "test", "test.txt"),
                RetCode.FAILED,
            ),
        ],
    )
    def test_check_arg_file_path(self, arg_name, arg_val, test_res):
        self.assertTrue(
            check_arg_exist_or_read_permissibale(arg_name, arg_val) == test_res
        )

    def test_check_core_file(self):
        self.assertTrue(
            check_core_file(
                "core_file",
                os.path.join(ut_root_path, "data", "atrace", "test", "test.txt"),
            )
            == RetCode.SUCCESS
        )

    def test_check_core_file_error(self):
        self.assertTrue(
            check_core_file(
                "core_file", os.path.join(ut_root_path, "data", "atrace", "test")
            )
            == RetCode.FAILED
        )

    def test_check_symbol_path(self):
        self.assertTrue(
            check_symbol_path("symbol", f"{ut_root_path},{ut_root_path}")
            == RetCode.SUCCESS
        )

    def test_check_symbol_path_trims_tokens(self):
        self.assertTrue(
            check_symbol_path("symbol", f" {ut_root_path} , {ut_root_path}, ")
            == RetCode.SUCCESS
        )

    def test_check_symbol_path_error(self):
        self.assertTrue(
            check_symbol_path("symbol", "ut_root_path,ut_root_path") == RetCode.FAILED
        )
