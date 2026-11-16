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
from .conftest import AssertTest
from .conftest import enter_test_tmp, restore_cwd


from params import ParamDict

import asys


def setup_module():
    print("TestLaunch st test start.")  # noqa: T201  # test diagnostic output
    set_env()


def teardown_module():
    print("TestLaunch st test finish.")  # noqa: T201  # test diagnostic output
    unset_env()


class TestLaunchRC(AssertTest):
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

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [("--task", "bash {}/data/asys_test_dir/test.bash".format(st_root_path))],
    )
    def test_launch_task_rc(self, capsys, arg_name, arg_val, mocker):
        """
        @描述: 执行launch功能, task参数有效
        @类型: FUNCTION
        @输入: asys launch --task={有效可执行指令}
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox类型文件
        """
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("RC")
        self.assertTrue(asys.main())

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("--task", ""), ("--task", " ")])
    def test_launch_task_unablerun_rc(self, caplog, arg_name, arg_val, mocker):
        """
        @描述: 执行launch功能, task参数无效, 包括task不可执行
        @类型: EXCEPTION
        @输入: asys launch --task={有效可执行指令}
        @步骤: 校验main函数返回值是否为False
        @预期结果: main函数返回值为False
        """
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("RC")
        self.assertTrue(not asys.main())
