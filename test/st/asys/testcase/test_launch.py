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

import logging
import os
import sys
import pytest
import shutil

from .conftest import (
    CONF_SRC_PATH,
    st_root_path,
    test_case_tmp,
    set_env,
    unset_env,
    great_bin,
)
from .conftest import (
    check_output_structure,
    create_dir,
    create_file,
    remove_dir,
    check_atrace_file,
    find_dir,
)
from .conftest import AssertTest


import asys
from params import ParamDict
from collect import AsysCollect


def setup_module():
    print("TestLaunch st test start.")  # noqa: T201  # test diagnostic output
    set_env()


def teardown_module():
    print("TestLaunch st test finish.")  # noqa: T201  # test diagnostic output
    unset_env()


class TestLaunch(AssertTest):
    def setup_method(self):
        print("init test environment")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        os.chdir(test_case_tmp)
        ParamDict.clear()

    def teardown_method(self):
        print("clean test environment.")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val", "res"],
        [
            (
                "--task",
                "bash {}/data/asys_test_dir/test.bash".format(st_root_path),
                True,
            ),
            (
                "--task",
                "bash {}/data/asys_test_dir/test.bash".format(st_root_path),
                False,
            ),
        ],
    )
    def test_launch_task(self, caplog, arg_name, arg_val, mocker, res):
        """
        @描述: 执行launch功能, task参数有效
        @类型: FUNCTION
        @输入: asys launch --task={有效可执行指令}
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox类型文件
        """
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        if res:
            self.assertTrue(asys.main())
            self.assertTrue(
                check_output_structure(["software", "log", "stackcore", "bbox"])
            )
        else:
            mocker.patch.object(AsysCollect, "collect", return_value=False)
            self.assertTrue(asys.main())
            self.assertTrue(
                not check_output_structure(["software", "log", "stackcore", "bbox"])
            )
            self.assertTrue("Collect information after task failed" in caplog.text)

    @pytest.mark.parametrize(["arg_name", "arg_val"], [("--task", ""), ("--task", " ")])
    def test_launch_task_unablerun(self, caplog, arg_name, arg_val):
        """
        @描述: 执行launch功能, task参数无效, 包括task不可执行
        @类型: EXCEPTION
        @输入: asys launch --task={有效可执行指令}
        @步骤: 校验main函数返回值是否为False
        @预期结果: main函数返回值为False
        """
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [
            (
                "--task",
                "bash {}/data/asys_test_dir/test_launch_error_task.sh".format(
                    st_root_path
                ),
            )
        ],
    )
    def test_launch_task_return_error(self, caplog, arg_name, arg_val):
        """
        @描述: 执行launch功能, task参数可执行, 任务返回码非0
        @类型: FUNCTION
        @输入: asys launch --task={执行返回码非0的任务}
        @步骤: 校验main函数返回值是否为True
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox类型文件
        """
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(
                ["software", "log", "stackcore", "bbox", "graph", "ops"]
            )
        )

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [("--task", "bash {}/data/asys_test_dir/test.bash".format(st_root_path))],
    )
    def test_launch_debug_kernel_task(self, capsys, arg_name, arg_val):
        """
        @描述: 执行launch功能, task参数有效
        @类型: FUNCTION
        @输入: asys launch --task={有效可执行指令}
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在debug_kernel类型文件
        """
        os.environ["ASCEND_OPP_PATH"] = st_root_path
        debug_kernel_path = os.path.join(st_root_path, "debug_kernel")
        create_dir(debug_kernel_path)
        create_file(debug_kernel_path + "/temp.o")
        create_file(debug_kernel_path + "/temp.json")
        create_file(debug_kernel_path + "/temp.cce")
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(check_output_structure(["debug_kernel"]))
        remove_dir(debug_kernel_path)

    def test_launch_create_env_dir_error(self):
        from launch.asys_launch import AsysLaunch
        from common.const import RetCode

        ParamDict().asys_output_timestamp_dir = "./"

        obj = AsysLaunch()
        obj.env_prepare = {
            "NPU_COLLECT_PATH": test_case_tmp + "/test_collect",
            "ASCEND_WORK_PATH": test_case_tmp + "/test_work",
        }

        obj.env_prepare["NPU_COLLECT_PATH"] = "./"
        ret = obj.prepare_for_launch()
        self.assertTrue(ret == RetCode.FAILED)
        obj.env_prepare["NPU_COLLECT_PATH"] = test_case_tmp + "/test_collect"

        obj.env_prepare["ASCEND_WORK_PATH"] = "./"
        ret = obj.prepare_for_launch()
        os.environ.pop("ASCEND_WORK_PATH")
        self.assertTrue(ret == RetCode.FAILED)
        shutil.rmtree(test_case_tmp)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [("--task", "bash {}/data/asys_test_dir/test.bash".format(st_root_path))],
    )
    def test_launch_atrace(self, capsys, arg_name, arg_val):
        """
        @描述: 执行launch功能, task参数有效
        @类型: FUNCTION
        @输入: asys launch --task={有效可执行指令}
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox类型文件
        """
        create_dir(os.path.join(st_root_path, "data", "atrace"))
        great_bin(os.path.join(st_root_path, "data", "atrace", "test.bin"))
        os.environ["ASCEND_WORK_PATH"] = os.path.join(st_root_path, "data")
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(check_output_structure(["atrace"]))
        out_dir = find_dir(test_case_tmp, "asys_output_")
        self.assertTrue(check_atrace_file(os.path.join("atrace", "test.txt"), out_dir))
        self.assertTrue(
            not check_atrace_file(os.path.join("atrace", "test.bin"), out_dir)
        )

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [("--task", "bash {}/data/asys_test_dir/test.bash".format(st_root_path))],
    )
    def test_launch_task_status_health(self, capsys, arg_name, arg_val):
        """
        @描述: 执行launch功能, task参数有效
        @类型: FUNCTION
        @输入: asys launch --task={有效可执行指令}
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中不存在npu_collect_intermediates类型文件
        """
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(check_output_structure(["npu_collect_intermediates"]))

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [
            ("--task", "bash"),
            ("--task", " bash"),
            ("--task", "bash "),
            ("--task", " bash "),
            ("--task", "bash ./data/asys_test_dir/test"),
            ("--task", "bash test1sh"),
            ("--task", "bash sh"),
            ("--task", "bash bash"),
            ("--task", "~/bash "),
            ("--task", "~/bash test.py"),
            ("--task", "~/bash test test2bash"),
            ("--task", "./sh "),
            ("--task", "./sh test1.py test2sh"),
            ("--task", "./sh test1sh test2.py"),
            ("--task", "/bin/sh test1sh test2.py"),
            ("--task", "/bin/bash test1sh test2.py"),
            ("--task", "python"),
            ("--task", " python "),
            ("--task", "python3"),
            ("--task", " python3 "),
            ("--task", "python3 test.sh"),
            ("--task", "python3 test.bash"),
            ("--task", "/usr/bin/python3.7 "),
            ("--task", "/usr/bin/python3.7 test"),
            ("--task", "/usr/bin/python3.7 test.sh"),
        ],
    )
    def test_launch_task_without_script(self, caplog, arg_name, arg_val):
        """
        @描述: 执行launch功能, task参数无效
        @类型: FUNCTION
        @输入: asys launch --task={无效可执行指令}
        @步骤: 校验main函数返回值是否为False; 校验错误日志;
        @预期结果: main函数返回值为False; 错误日志包含预期消息;
        """
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        caplog.set_level(logging.ERROR)
        self.assertTrue(not asys.main())
        expected_message = (
            f'Argument "{arg_name.lstrip("-")}" no executable script, '
            f'argument value: "{arg_val}"'
        )
        assert any(
            record.levelname == "ERROR" and expected_message in record.getMessage()
            for record in caplog.records
        ), caplog.text

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [
            ("--task", " test_sh "),
            ("--task", "test_bash"),
            ("--task", "test_python"),
            ("--task", "./sh test.sh"),
            ("--task", "/bin/sh test.sh test1"),
            ("--task", "~/sh test.bash"),
            ("--task", "../sh test.bash test1"),
            ("--task", "./bash test.sh"),
            ("--task", "/bin/bash test.sh test1"),
            ("--task", "~/bash test.bash"),
            ("--task", "../bash test.bash test1"),
            ("--task", "bash test test.sh"),
            ("--task", "./sh test1sh test2.sh"),
            ("--task", "python test.py"),
            ("--task", "./python3.7.5 test.py"),
            ("--task", "~/python3.11.0 test.py"),
            ("--task", "python3 test1py test.py"),
            ("--task", "/usr/bin/python3.7 test test.py"),
            ("--task", "/usr/local/python3.7.5/bin/python3 test.py test2"),
        ],
    )
    def test_launch_task_with_script(self, arg_name, arg_val, mocker):
        """
        @描述: 执行launch功能, task参数有效
        @类型: FUNCTION
        @输入: asys launch --task={有效可执行指令}
        @步骤: 校验main函数返回值是否为True;
        @预期结果: main函数返回值为True;
        """
        sys.argv = [CONF_SRC_PATH, "launch", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        mocker.patch("asys.AsysLaunch.launch", return_value=True)
        mocker.patch("asys.AsysLaunch.clean_work", return_value=True)
        self.assertTrue(asys.main())

    def test_launch_prepare_for_launch_failed(self, mocker, caplog):
        sys.argv = [CONF_SRC_PATH, "launch", "--task=bash test.sh"]
        ParamDict().set_env_type("EP")
        mocker.patch("asys.AsysLaunch.prepare_for_launch", return_value=False)
        self.assertTrue(not asys.main())
        self.assertTrue("Prepare for launch failed" in caplog.text)
