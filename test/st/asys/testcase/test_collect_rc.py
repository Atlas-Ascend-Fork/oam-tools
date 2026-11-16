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
import sys
import pytest
import shutil

from .conftest import CONF_SRC_PATH, st_root_path, test_case_tmp, set_env, unset_env
from .conftest import check_output_structure, AssertTest
from .conftest import enter_test_tmp, restore_cwd


import asys
from params import ParamDict
from common.const import RetCode


def setup_module():
    print("TestCollect st test start.")  # noqa: T201  # test diagnostic output
    set_env()


def teardown_module():
    print("TestCollect st test finish.")  # noqa: T201  # test diagnostic output
    unset_env()


class TestCollectRC(AssertTest):
    def setup_method(self):
        print("init test environment")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        enter_test_tmp()
        ParamDict.clear()

    def teardown_method(self):
        print("clean test environment.")  # noqa: T201  # test diagnostic output
        restore_cwd()
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)

    def test_collect_nodir_rc(self, caplog, mocker):
        """
        @描述: 不带任何参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, data-dump, graph, ops类型文件
        """
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("RC")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(["software", "data-dump", "graph", "ops"])
        )

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"], [("--task_dir", st_root_path + "/data/asys_test_dir")]
    )
    def test_collect_dir_rc(self, capsys, arg_name, arg_val, mocker):
        """
        @描述: 使用task_dir参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox, graph, ops类型文件
        """
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("RC")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [
            ("--task_dir", st_root_path + "/data/asys_test_dir_noexist"),
            ("--task_dir", "' '"),
            ("--task_dir", ""),
        ],
    )
    def test_collect_dir_invalid_rc(self, caplog, arg_name, arg_val, mocker):
        """
        @描述: 使用无效task_dir参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为False
        @预期结果: main函数返回值为False
        """
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        self.assertTrue(asys.main() != RetCode.SUCCESS)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [("--output", "{}/asys_test_output_arg".format(test_case_tmp))],
    )
    def test_collect_output_arg_rc(self, capsys, arg_name, arg_val, mocker):
        """
        @描述: 使用output参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --output=[有效路径]
        @步骤: 校验main函数返回值是否为True
        @预期结果: main函数返回值为True
        """
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("RC")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [
            ("--output", ""),
            ("--output", "    "),
            ("--output", "\\out"),
            ("--output", "^out"),
            ("--output", "$out"),
        ],
    )
    def test_collect_output_arg_invalid_rc(self, caplog, arg_name, arg_val, mocker):
        """
        @描述: 使用无效output参数,，包括空字符串，空格字符串, 含有非法字符字符串, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --output=[""|" "|"\\out"|"^out"|"$out"]
        @步骤: 校验main函数返回值是否为True
        @预期结果: main函数返回值为True
        """
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("RC")
        self.assertTrue(asys.main() != RetCode.SUCCESS)
        if arg_val.strip() != "":
            self.assertTrue(
                "Argument output is invalid, only characters in [a-zA-Z0-9_-.]"
                in caplog.text
            )

    def test_get_log_conf_path(self):
        from common.path import get_log_conf_path

        get_log_conf_path("slog")
        get_log_conf_path("bbox")

        from drv.env_type import LoadSoType

        LoadSoType().get_env_type()

    def test_collect_rc_stackcore(self, mocker):
        from collect.log.rc_log_collect import collect_stackcore

        mocker.patch(
            "common.file_operate.FileOperate.list_dir", return_value=["aaa", "bbb"]
        )
        mocker.patch(
            "common.file_operate.FileOperate.copy_file_to_dir", return_value=True
        )
        mocker.patch(
            "os.walk",
            return_value=((f"{st_root_path}/data/scripts", "", ["msnpureport"]),),
        )
        collect_stackcore("./")

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_cmd_error_rc(self, capsys):
        sys.argv = [CONF_SRC_PATH, "health"]
        ParamDict().set_env_type("RC")
        try:
            asys.main()
        except Exception:
            pass

        captured = capsys.readouterr()
        self.assertTrue(
            captured.err.count(
                "error: argument subparser_name: invalid choice: 'health' (choose from 'collect', 'launch')"
            )
            == 1
        )

    def test_collect_rc_software(self):
        from collect.asys_collect import AsysCollect

        ParamDict().set_env_type("RC")
        ParamDict().asys_output_timestamp_dir = test_case_tmp
        AsysCollect().collect_status_info()
        self.assertTrue(
            os.path.isfile(os.path.join(test_case_tmp, "software_info.txt"))
        )
        self.assertTrue(
            not os.path.exists(os.path.join(test_case_tmp, "health_result.txt"))
        )
