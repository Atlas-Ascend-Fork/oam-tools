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

import pytest
import shutil
from .conftest import test_case_tmp
from .conftest import AssertTest


from params import ParamDict
from common.const import RetCode
from common import FileOperate
from common.task_common import create_out_timestamp_dir


class TestCommon(AssertTest):
    @staticmethod
    def setup_method():
        print("init test environment")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        os.chdir(test_case_tmp)
        ParamDict.clear()

    @staticmethod
    def teardown_method():
        print("clean test environment.")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            os.chmod(test_case_tmp, 0o777)  # nosec B103  # test asserts permission-mask behavior
            shutil.rmtree(test_case_tmp)

    @pytest.mark.parametrize(
        "test_fun, check_res",
        [
            ("write_file", "failed in write file"),
            ("append_write_file", "failed in write file"),
            ("delete_dirs", "Delete intermediate"),
            ("copy_dir", "The output directory cannot be in the data directory"),
            ("collect_file_to_dir", "Unknown mode in collect file"),
            ("collect_dir", "Unknown mode in collect directory"),
        ],
    )
    def test_file_operator_error(self, mocker, test_fun, check_res, caplog):
        if test_fun == "write_file":
            mocker.patch("os.path.exists", return_value=False)
            mocker.patch.object(FileOperate, "create_dir", return_value=False)
            FileOperate.write_file(os.path.join("some_dir", "file_path"), "info")
            self.assertTrue(check_res in caplog.text)
        if test_fun == "append_write_file":
            mocker.patch("os.path.exists", return_value=False)
            mocker.patch.object(FileOperate, "create_dir", return_value=False)
            FileOperate.append_write_file(os.path.join("some_dir", "file_path"), "info")
            self.assertTrue(check_res in caplog.text)
        if test_fun == "delete_dirs":
            mocker.patch("os.path.exists", return_value=True)
            mocker.patch.object(FileOperate, "remove_dir", return_value=False)
            FileOperate.delete_dirs(["test1", "test2"])
            self.assertTrue(check_res in caplog.text)
        if test_fun == "copy_dir":
            mocker.patch("os.path.exists", return_value=True)
            mocker.patch("os.access", return_value=True)
            mocker.patch("os.path.isdir", return_value=True)
            mocker.patch("shutil.copytree", return_value=True)
            mocker.patch("os.path.realpath", side_effect=["/source", "/source/child"])
            FileOperate.copy_dir("dir1", "dir2")
            self.assertTrue(check_res in caplog.text)
        if test_fun == "collect_file_to_dir":
            FileOperate.collect_file_to_dir("dir1", "dir2", "l")
            self.assertTrue(check_res in caplog.text)
        if test_fun == "collect_dir":
            FileOperate.collect_dir("dir1", "dir2", "l")
            self.assertTrue(check_res in caplog.text)

    @pytest.mark.parametrize("file_path", [None, ""])
    def test_append_write_file_invalid_path(self, file_path):
        self.assertTrue(FileOperate.append_write_file(file_path, "info") is None)

    def test_create_out_dir_no_write_permission(self, mocker, caplog):
        mocker.patch.object(ParamDict, "get_command", return_value="collect")
        mocker.patch("os.access", return_value=False)
        self.assertTrue(create_out_timestamp_dir() == RetCode.PERMISSION_FAILED)
        self.assertTrue(
            "No write permission to asys output root directory" in caplog.text
        )
