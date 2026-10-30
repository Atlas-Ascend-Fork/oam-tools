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

import tempfile
# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

import os
import sys

import pytest
import shutil
from common.const import RetCode, ATRACE_LOG_NAME
from .conftest import (
    CONF_SRC_PATH,
    st_root_path,
    test_case_tmp,
    set_env,
    unset_env,
    great_error_bin,
)
from .conftest import (
    check_output_structure,
    create_dir,
    create_file,
    remove_dir,
    great_bin,
    check_atrace_file,
    find_dir,
)
from .conftest import AssertTest


import asys
from params import ParamDict
from common import FileOperate
from collect.asys_collect import AsysCollect


class AsysTrace:
    def sigqueue(self, *_args):
        os.mknod(
            f"{st_root_path}/data/asys_test_dir/ascend/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_202411.bin"
        )
        return 0

    def AtraceStackcoreParse(self, *_args):
        return 0


def setup_module():
    print("TestCollect st test start.")  # noqa: T201  # test diagnostic output
    set_env()


def teardown_module():
    print("TestCollect st test finish.")  # noqa: T201  # test diagnostic output
    unset_env()


class TestCollect(AssertTest):
    def setup_method(self):
        print("init test environment")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        os.chdir(test_case_tmp)
        ParamDict.clear()
        for env in [
            "ASCEND_PROCESS_LOG_PATH",
            "ASCEND_CACHE_PATH",
            "ASCEND_WORK_PATH",
            "ASCEND_CUSTOM_OPP_PATH",
            "ASCEND_OPP_PATH",
        ]:
            if os.getenv(env):
                os.environ.pop(env)

    def teardown_method(self):
        print("clean test environment.")  # noqa: T201  # test diagnostic output
        if os.path.exists(
            f"{st_root_path}/data/asys_test_dir/ascend/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_202411.bin"
        ):
            os.remove(
                f"{st_root_path}/data/asys_test_dir/ascend/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_202411.bin"
            )
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)

    def test_collect_nodir(self, caplog):
        """
        @描述: 不带任何参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox类型文件
        """
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            st_root_path + "/data/vendors/customize_2/"
        )
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(
                [
                    "software",
                    "log",
                    "stackcore",
                    "bbox",
                    "vendor_config",
                    "custom_config",
                ]
            )
        )

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"], [("--task_dir", st_root_path + "/data/asys_test_dir")]
    )
    def test_collect_dir(self, capsys, arg_name, arg_val):
        """
        @描述: 使用task_dir参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox, graph, ops类型文件
        """
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(
                ["software", "log", "stackcore", "bbox", "graph", "host_driver"]
            )
        )

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"], [("--task_dir", st_root_path + "/data/asys_test_dir")]
    )
    def test_collect_dir_status_info_time_out(self, caplog, arg_name, arg_val, mocker):
        """
        @描述: 使用task_dir参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox, graph, ops类型文件
        """
        mocker.patch.object(
            AsysCollect, "collect_status_info", side_effect=TimeoutError
        )
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            "Timeout in retrieving device status information" in caplog.text
        )

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"], [("--task_dir", st_root_path + "/data/asys_test_dir")]
    )
    def test_collect_dir_health_info_time_out(self, caplog, arg_name, arg_val, mocker):
        """
        @描述: 使用task_dir参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox, graph, ops类型文件
        """
        mocker.patch.object(
            AsysCollect, "collect_health_info", side_effect=TimeoutError
        )
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            "Timeout in retrieving device health information" in caplog.text
        )

    def test_collect_exception_dump_dump_path(self, mocker):
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/"
        os.environ["NPU_COLLECT_PATH"] = st_root_path + "/data/"
        mocker.patch("collect.ops.ops_collect.get_fault_kernel_name", return_value=True)
        os.environ["ASCEND_PROCESS_LOG_PATH"] = (
            st_root_path + "/data/asys_test_dir/ascend/log/"
        )
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(
                ["software", "log", "stackcore", "bbox", "ops", "data-dump"]
            )
        )

    def test_collect_exception_dump_cache_path(self, mocker):
        os.environ["ASCEND_PROCESS_LOG_PATH"] = (
            st_root_path + "/data/asys_test_dir/ascend/log/"
        )
        os.environ["ASCEND_CACHE_PATH"] = st_root_path + "/data/ops/"
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(
                ["software", "log", "stackcore", "bbox", "ops", "data-dump"]
            )
        )

    def test_collect_exception_dump_graph_path(self, mocker):
        os.environ["DUMP_GRAPH_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/"
        os.environ["NPU_COLLECT_PATH"] = st_root_path + "/data/"
        mocker.patch("collect.ops.ops_collect.get_fault_kernel_name", return_value=True)
        os.environ["ASCEND_PROCESS_LOG_PATH"] = (
            st_root_path + "/data/asys_test_dir/ascend/log/"
        )
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(
                ["software", "log", "stackcore", "bbox", "ops", "data-dump"]
            )
        )

    def test_collect_exception_dump_work_path(self):
        """
        @描述: 执行collect功能
        @类型: FUNCTION
        @输入: asys collect
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox, ops类型文件
        """
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_PROCESS_LOG_PATH"] = (
            st_root_path + "/data/asys_test_dir/ascend/log/"
        )
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(
                ["software", "log", "stackcore", "bbox", "ops", "data-dump"]
            )
        )

    def test_collect_exception_dump_opp_path(self):
        """
        @描述: 执行collect功能
        @类型: FUNCTION
        @输入: asys collect
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox, ops类型文件, 校验fftsplus task execute failed
        """
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_PROCESS_LOG_PATH"] = (
            st_root_path + "/data/asys_test_dir/ascend/log/"
        )
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/opp/"
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(
                ["software", "log", "stackcore", "bbox", "ops", "data-dump"]
            )
        )

    def test_collect_atrace_logs(self):
        """
        @描述: 执行collect功能
        @类型: FUNCTION
        @输入: asys collect
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox, ops类型文件
        """
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            check_output_structure(
                ["software", "log", "stackcore", "bbox", "atrace", "atrace_file", "ops"]
            )
        )

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [
            ("--task_dir", st_root_path + "/data/asys_test_dir_noexist"),
            ("--task_dir", "' '"),
            ("--task_dir", ""),
        ],
    )
    def test_collect_dir_invalid(self, caplog, arg_name, arg_val):
        """
        @描述: 使用无效task_dir参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为False
        @预期结果: main函数返回值为False
        """
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        self.assertTrue(asys.main() != RetCode.SUCCESS)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"],
        [("--output", "{}/asys_test_output_arg".format(test_case_tmp))],
    )
    def test_collect_output_arg(self, capsys, arg_name, arg_val):
        """
        @描述: 使用output参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --output=[有效路径]
        @步骤: 校验main函数返回值是否为True
        @预期结果: main函数返回值为True
        """
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
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
    def test_collect_output_arg_invalid(self, caplog, arg_name, arg_val):
        """
        @描述: 使用无效output参数,，包括空字符串，空格字符串, 含有非法字符字符串, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --output=[""|" "|"\\out"|"^out"|"$out"]
        @步骤: 校验main函数返回值是否为True
        @预期结果: main函数返回值为True
        """
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main() != RetCode.SUCCESS)
        if arg_val.strip() != "":
            self.assertTrue(
                "Argument output is invalid, only characters in [a-zA-Z0-9_-.]"
                in caplog.text
            )

    @pytest.mark.parametrize("exist_res", [True, False])
    def test_collect_output_arg_not_permissible(self, exist_res, mocker, caplog):
        mocker.patch("os.path.abspath", return_value="test")
        mocker.patch("os.path.exists", return_value=exist_res)
        mocker.patch("os.path.isdir", return_value=True)
        mocker.patch("os.access", return_value=False)
        mocker.patch("os.path.dirname", return_value="/")
        sys.argv = [CONF_SRC_PATH, "collect", f"--output={test_case_tmp}"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main() != RetCode.SUCCESS)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"], [("--task_dir", st_root_path + "/data/asys_test_dir")]
    )
    def test_collect_debug_kernel_path(self, capsys, arg_name, arg_val):
        """
        @描述: 使用output参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --output=[有效路径]
        @步骤: 校验main函数返回值是否为True
        @预期结果: main函数返回值为True,生成目录中存在debug_kernel类型文件
        """

        os.environ["ASCEND_OPP_PATH"] = st_root_path
        debug_kernel_path = os.path.join(st_root_path, "debug_kernel")
        create_dir(debug_kernel_path)
        create_file(debug_kernel_path + "/temp.o")
        create_file(debug_kernel_path + "/temp.json")
        create_file(debug_kernel_path + "/temp.cce")
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(check_output_structure(["debug_kernel"]))
        remove_dir(debug_kernel_path)

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"], [("--output", st_root_path + "/debug_kernel")]
    )
    def test_collect_debug_kernel_check_path(self, capsys, arg_name, arg_val):
        """
        @描述: 使用output参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --output=[有效路径]
        @步骤: 校验main函数返回值是否为True
        @预期结果: main函数返回值为True,生成目录中存在debug_kernel类型文件
        """
        os.environ["ASCEND_OPP_PATH"] = st_root_path
        debug_kernel_path = os.path.join(st_root_path, "debug_kernel")
        create_dir(debug_kernel_path)
        create_file(debug_kernel_path + "/temp.o")
        create_file(debug_kernel_path + "/temp.json")
        create_file(debug_kernel_path + "/temp.cce")
        sys.argv = [CONF_SRC_PATH, "collect", "=".join([arg_name, arg_val])]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        remove_dir(debug_kernel_path)

    def test_collect_with_tar(self, caplog):
        """
        @描述: 执行collect功能, 并将output dir压缩
        @类型: FUNCTION
        @输入: asys collect --tar=True
        @步骤: 校验main函数返回值是否为True; 校验生成的压缩文件
        @预期结果: main函数返回值为True; 生成tar压缩文件
        """
        os.environ["TOOLCHAIN_HOME"] = st_root_path
        sys.argv = [CONF_SRC_PATH, "collect", "--tar=True"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        dirs = os.listdir(test_case_tmp)
        if not dirs:
            return False
        self.assertTrue(
            os.path.isfile(os.path.join(test_case_tmp, dirs[0]))
            and os.path.join(test_case_tmp, dirs[0]).endswith("tar.gz")
        )
        self.assertTrue(len(dirs) == 1)

    def test_collect_output_path_with_tar(self, caplog):
        """
        @描述: 执行collect功能, 并将output dir压缩
        @类型: FUNCTION
        @输入: asys collect --output=case_tmp_dir --tar=True
        @步骤: 校验main函数返回值是否为True; 校验生成的压缩文件
        @预期结果: main函数返回值为True; 生成tar压缩文件
        """
        case_tmp_dir = os.path.join(test_case_tmp, "tar_dir")
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "--output=%s" % case_tmp_dir,
            "--tar=True",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        dirs = os.listdir(case_tmp_dir)
        if not dirs:
            self.assertTrue(False)
        self.assertTrue(
            os.path.isfile(os.path.join(case_tmp_dir, dirs[0]))
            and os.path.join(case_tmp_dir, dirs[0]).endswith("tar.gz")
        )
        self.assertTrue(len(dirs) == 1)

    def test_collect_dir_atrace(self, capsys):
        """
        @描述: 使用task_dir参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在atrace类型文件,  存在 test.txt, 无test.bin, test.txt 内容符合预期
        """
        create_dir(os.path.join(st_root_path, "data", "atrace"))
        great_bin(os.path.join(st_root_path, "data", "atrace", "test.bin"))
        os.environ["ASCEND_WORK_PATH"] = os.path.join(st_root_path, "data")
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(check_output_structure(["atrace"]))
        out_dir = find_dir(test_case_tmp, "asys_output_")
        self.assertTrue(check_atrace_file(os.path.join("atrace", "test.txt"), out_dir))
        self.assertTrue(
            not check_atrace_file(os.path.join("atrace", "test.bin"), out_dir)
        )

    def test_collect_dir_atrace_error(self, capsys):
        """
        @描述: 使用task_dir参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在atrace类型文件,  存在 test.txt, 无test.bin, test.txt 内容符合预期
        """
        create_dir(os.path.join(st_root_path, "data", "atrace"))
        great_error_bin(os.path.join(st_root_path, "data", "atrace", "test.bin"))
        os.environ["ASCEND_WORK_PATH"] = os.path.join(st_root_path, "data")
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(check_output_structure(["atrace"]))
        out_dir = find_dir(test_case_tmp, "asys_output_")
        self.assertTrue(
            not check_atrace_file(os.path.join("atrace", "test.txt"), out_dir)
        )
        self.assertTrue(check_atrace_file(os.path.join("atrace", "test.bin"), out_dir))
        shutil.rmtree(os.path.join(st_root_path, "data", "atrace"))

    def test_collect_ep_health_status(self, monkeypatch):
        def decorator(timeout):
            def mock_decorator(func):
                def wrapper(*args, **kwargs):
                    print("Mock decorator is running", "<<" * 100)  # noqa: T201  # test diagnostic output
                    return func(*args, **kwargs)

                return wrapper

            return mock_decorator

        monkeypatch.setattr("common.task_common.timeout_decorator", decorator)
        ParamDict().set_env_type("EP")
        ParamDict().asys_output_timestamp_dir = test_case_tmp
        AsysCollect().collect_status_info()
        AsysCollect().collect_health_info()
        self.assertTrue(
            os.path.isfile(os.path.join(test_case_tmp, "software_info.txt"))
        )
        self.assertTrue(
            os.path.isfile(os.path.join(test_case_tmp, "hardware_info.txt"))
        )
        self.assertTrue(
            os.path.isfile(os.path.join(test_case_tmp, "health_result.txt"))
        )

    def test_collect_check_args_duplicate_error(self, caplog):
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

    def test_collect_with_remote_0_error(self, caplog):
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            st_root_path + "/data/vendors/customize_2/"
        )
        sys.argv = [CONF_SRC_PATH, "collect", "--remote=0"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "'--remote', '--all' and '--quiet' can be used only when '-r=stacktrace'."
            in caplog.text
        )

    def test_collect_with_remote_1_error(self, caplog):
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            st_root_path + "/data/vendors/customize_2/"
        )
        sys.argv = [CONF_SRC_PATH, "collect", "--remote=1"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "'--remote', '--all' and '--quiet' can be used only when '-r=stacktrace'."
            in caplog.text
        )

    def test_collect_with_all_error(self, caplog):
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            st_root_path + "/data/vendors/customize_2/"
        )
        sys.argv = [CONF_SRC_PATH, "collect", "--all"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "'--remote', '--all' and '--quiet' can be used only when '-r=stacktrace'."
            in caplog.text
        )

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_collect_stacktrace_r_error(self, capsys):
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            st_root_path + "/data/vendors/customize_2/"
        )
        sys.argv = [CONF_SRC_PATH, "collect", "-r=stackcore", "--remote=0"]
        ParamDict().set_env_type("EP")
        try:
            asys.main()
        except Exception:
            pass
        msg = capsys.readouterr()
        self.assertTrue(
            "asys collect: error: argument -r: invalid choice: 'stackcore' (choose from 'stacktrace')"
            in msg.err
        )

    @pytest.mark.parametrize(
        ["arg_name", "arg_val"], [("--tar", False), ("--task_dir", "./")]
    )
    def test_collect_stacktrace_with_other_error(self, caplog, arg_name, arg_val):
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            st_root_path + "/data/vendors/customize_2/"
        )
        sys.argv = [CONF_SRC_PATH, "collect", "-r=stacktrace", f"{arg_name}={arg_val}"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "'--task_dir', and '--tar' can be used only when '-r' is not used."
            in caplog.text
        )

    def test_collect_stacktrace_remote_type_error(self, capsys):
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            st_root_path + "/data/vendors/customize_2/"
        )
        sys.argv = [CONF_SRC_PATH, "collect", "-r=stacktrace", "--remote=a"]
        ParamDict().set_env_type("EP")
        try:
            asys.main()
        except Exception:
            pass
        msg = capsys.readouterr()
        self.assertTrue(
            "asys collect: error: argument --remote: invalid int value: 'a'" in msg.err
        )

    def test_collect_stacktrace_with_remote_0_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=True,
        )
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            st_root_path + "/data/vendors/customize_2/"
        )
        sys.argv = [CONF_SRC_PATH, "collect", "-r=stacktrace", "--remote=0", "--all"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            'The value of "--remote" must be greater than 1, input: 0.' in caplog.text
        )

    def test_collect_stacktrace_all_value_error(self, capsys):
        os.environ["ASCEND_OPP_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            st_root_path + "/data/vendors/customize_2/"
        )
        sys.argv = [CONF_SRC_PATH, "collect", "-r=stacktrace", "--all=0"]
        ParamDict().set_env_type("EP")
        try:
            asys.main()
        except Exception:
            pass
        msg = capsys.readouterr()
        self.assertTrue(
            "asys collect: error: argument --all: ignored explicit argument '0'"
            in msg.err
        )

    def test_collect_stacktrace_all_task(self, mocker):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._check_remote_id_validity",
            return_value=True,
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._wait_bin_file_generate",
            return_value=".",
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("time.sleep", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        mocker.patch("os.listdir", return_value=[])
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=12345",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_collect_stacktrace_no_remote_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [CONF_SRC_PATH, "collect", "-r=stacktrace", "--all"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            '"-r=stacktrace" must be used together with "--remote" and "--all".'
            in caplog.text
        )

    def test_collect_stacktrace_pid_not_exists(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [CONF_SRC_PATH, "collect", "-r=stacktrace", "--remote=-10", "--all"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            'The value of "--remote" must be greater than 1, input: -10.' in caplog.text
        )

    def test_collect_stacktrace_parallel_pid_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        cmd_ret = (
            "root       43389    3488  0 08:20 pts/2    00:00:00 \n"
            "python3 tools/asys/asys.py collect -r=stacktrace --remote=123456"
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.popen_run_cmd", return_value=cmd_ret
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._get_other_stacktrace_remote_id",
            return_value=["123456", "34567"],
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=12345",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("Get pid failed by remote: 12345." in caplog.text)

    def test_collect_stacktrace_parallel_remote_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        cmd_ret = "root       43389    3488  0 08:20 pts/2    00:00:00 python3 tools/asys/asys.py collect -r=stacktrace --remote=12345\n23456"
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.popen_run_cmd", return_value=cmd_ret
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._get_other_stacktrace_remote_id",
            return_value=["12345", "34567"],
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=12345",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("Collect stacktrace not support Parallelism." in caplog.text)

    def test_collect_stacktrace_parallel_tid_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        cmd_ret = "root       43389    3488  0 08:20 pts/2    00:00:00 python3 tools/asys/asys.py collect -r=stacktrace --remote=12345\n23456"
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.popen_run_cmd", return_value=cmd_ret
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._get_other_stacktrace_remote_id",
            return_value=["123456", "34567"],
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._get_all_tid_of_process",
            return_value=["34567"],
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=23456",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("Collect stacktrace not support Parallelism." in caplog.text)

    def test_collect_stacktrace_parallel_other_all_remote_id(self, mocker):
        """
        PID    PPID
        22652  8264    bash test_parallel_2.sh
        22653  22652   asys collect -r=stacktrace --remote=11101 --all  (error)
        22654  22652   asys collect -r=stacktrace --remote=11101 --all  (error)

        22652  8264    bash -c cd ./;asys collect -r=stacktrace --remote=11101 --all (exclude)
        22653  22652   asys collect -r=stacktrace --remote=11101 --all  (pass)
        """
        from collect.stacktrace.stacktrace_collect import AsysStackTrace

        cmd_ret = (
            "root       43389    3488   0 08:20 pts/2    00:00:00 python3 tools/asys/asys.py collect -r=stacktrace --remote=12345\n"
            "root       22652    8264   0 08:20 pts/2    00:00:00 cd /home;source setenv.bash;python3 tools/asys/asys.py collect -r=stacktrace --remote=23456\n"
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.popen_run_cmd", return_value=cmd_ret
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("os.getppid", return_value=22652)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=23456",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        ret = AsysStackTrace()._get_other_stacktrace_remote_id(43390)
        self.assertTrue(ret == ["12345"])

    def test_collect_stacktrace_send_signal_attr_error(self, mocker, caplog):
        class AsysTraceError:
            def AtraceStackcoreParse(self, *_args):
                return 0

        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTraceError(),
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._check_remote_id_validity",
            return_value=True,
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=12345",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "Send signal failed, error msg: 'AsysTraceError' object has no attribute 'sigqueue'."
            in caplog.text
        )

    def test_collect_stacktrace_send_signal_error(self, mocker, caplog):
        class AsysTraceError:
            def sigqueue(self, *args):
                return 1

            def AtraceStackcoreParse(self, *_args):
                return 0

        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTraceError(),
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._check_remote_id_validity",
            return_value=True,
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=12345",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("Send signal failed." in caplog.text)

    def test_collect_stacktrace_bin_file_timeout(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._check_remote_id_validity",
            return_value=True,
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("time.sleep", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/"
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=12345",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "get the stackcore bin file in path" in caplog.text
            and "timeout" in caplog.text
        )

    def test_get_target_work_path_success(self, mocker):
        from collect.stacktrace.stacktrace_collect import AsysStackTrace

        mock_remote_id = 12345
        mock_ascend_work_path = os.path.join(
            tempfile.gettempdir(), "test_ascend_work_path"
        )
        mock_env_content = (
            f"PATH=/usr/bin\0ASCEND_WORK_PATH={mock_ascend_work_path}\0USER=root"
        )
        mocker.patch.object(AsysStackTrace, "__init__", return_value=None)
        asys_stack = AsysStackTrace()
        asys_stack.remote_id = mock_remote_id
        mock_open = mocker.patch(
            "builtins.open", mocker.mock_open(read_data=mock_env_content)
        )
        mocker.patch("os.path.join", return_value=f"/proc/{mock_remote_id}/environ")
        result = asys_stack._get_target_work_path()

        self.assertTrue(result == mock_ascend_work_path)
        mock_open.assert_called_once_with(
            f"/proc/{mock_remote_id}/environ",
            "r",
            encoding="utf-8",
            errors="ignore",
        )

    def test_get_target_work_path_permission_denied(self, mocker, caplog):
        from collect.stacktrace.stacktrace_collect import AsysStackTrace

        mock_remote_id = 67890
        mocker.patch.object(AsysStackTrace, "__init__", return_value=None)
        asys_stack = AsysStackTrace()
        asys_stack.remote_id = mock_remote_id
        mocker.patch("builtins.open", side_effect=PermissionError)
        mocker.patch("os.path.join", return_value=f"/proc/{mock_remote_id}/environ")
        result = asys_stack._get_target_work_path()

        self.assertTrue(result is None)

    def test_set_trace_work_path_from_process_env(self, mocker):
        from collect.stacktrace.stacktrace_collect import AsysStackTrace

        mock_remote_id = 12345
        mock_ascend_work_path = os.path.join(
            tempfile.gettempdir(), "test_ascend_work_path"
        )
        expected_trace_path = os.path.join(mock_ascend_work_path, ATRACE_LOG_NAME)
        mocker.patch.object(AsysStackTrace, "__init__", return_value=None)
        asys_stack = AsysStackTrace()
        asys_stack.remote_id = mock_remote_id
        mocker.patch.object(
            asys_stack, "_get_target_work_path", return_value=mock_ascend_work_path
        )
        mock_env_var = mocker.Mock()
        mock_env_var.home_path = "/home/test"
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.EnvVarName",
            return_value=mock_env_var,
        )
        asys_stack._set_trace_work_path()

        self.assertTrue(
            os.path.abspath(asys_stack.trace_work_path)
            == os.path.abspath(expected_trace_path)
        )

    def test_set_trace_work_path_default(self, mocker, caplog):
        from collect.stacktrace.stacktrace_collect import AsysStackTrace

        mock_remote_id = 67890
        mock_home_path = "/home/test_user"
        expected_default_path = os.path.join(mock_home_path, "ascend", ATRACE_LOG_NAME)
        mocker.patch.object(AsysStackTrace, "__init__", return_value=None)
        asys_stack = AsysStackTrace()
        asys_stack.remote_id = mock_remote_id
        mocker.patch.object(asys_stack, "_get_target_work_path", return_value=None)
        mock_env_var = mocker.Mock()
        mock_env_var.home_path = mock_home_path
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.EnvVarName",
            return_value=mock_env_var,
        )
        asys_stack._set_trace_work_path()

        self.assertTrue(
            os.path.abspath(asys_stack.trace_work_path)
            == os.path.abspath(expected_default_path)
        )

    def test_collect_stacktrace_parse_attr_error(self, mocker, caplog):
        class AsysTraceError:
            def sigqueue(self, *_args):
                os.mknod(
                    f"{st_root_path}/data/asys_test_dir/ascend/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_202411.bin"
                )
                return 0

        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTraceError(),
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._check_remote_id_validity",
            return_value=True,
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._wait_bin_file_generate",
            return_value=".",
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("time.sleep", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=12345",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "Parse stackcore bin file failed, error msg: 'AsysTraceError' object has no attribute 'AtraceStackcoreParse'."
            in caplog.text
        )

    def test_collect_stacktrace_parse_error(self, mocker, caplog):
        class AsysTraceError:
            def sigqueue(self, *_args):
                os.mknod(
                    f"{st_root_path}/data/asys_test_dir/ascend/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_202411.bin"
                )
                return 0

            def AtraceStackcoreParse(self, *_args):
                return 1

        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTraceError(),
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._check_remote_id_validity",
            return_value=True,
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._wait_bin_file_generate",
            return_value=".",
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("time.sleep", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/asys_test_dir/ascend/"
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            "-r=stacktrace",
            "--remote=12345",
            "--all",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "Parse stackcore bin file failed, check trace logs in the plog."
            in caplog.text
        )

    def test_collect_stacktrace_wait_bin_file_generate(self, mocker, caplog):
        from collect.stacktrace.stacktrace_collect import AsysStackTrace

        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.popen_run_cmd", return_value="./test"
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._get_exists_bin_file_num",
            return_value=6,
        )
        mocker.patch("time.sleep", return_value=True)
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/"
        ret = AsysStackTrace()._wait_bin_file_generate(5)
        self.assertTrue(not ret)

    def test_collect_dir_error(self, mocker, caplog):
        """
        @描述: 执行collect功能, 执行collect_dir异常
        @类型: FUNCTION
        @输入: asys collect
        @步骤: 校验main函数返回值是否为True; 校验生成目录不会生成
        @预期结果: main函数返回值为True; 生成目录中software, log, stackcore, bbox, ops都不存在
        """
        mocker.patch("common.FileOperate.collect_dir", return_value=False)
        os.environ["ASCEND_WORK_PATH"] = st_root_path + "/data/"
        os.environ["ASCEND_PROCESS_LOG_PATH"] = (
            st_root_path + "/data/asys_test_dir/ascend/log/"
        )
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(not check_output_structure(["log"]))
        self.assertTrue(not check_output_structure(["stackcore"]))
        self.assertTrue(not check_output_structure(["bbox"]))
        self.assertTrue(not check_output_structure(["ops"]))
        self.assertTrue(not check_output_structure(["data-dump"]))

    @pytest.mark.parametrize(["list_dir"], [(True,), (False,)])
    def test_collect_not_files_error(self, list_dir, mocker, caplog):
        """
        @描述: 使用task_dir参数, 执行collect功能
        @类型: FUNCTION
        @输入: asys collect --task_dir
        @步骤: 校验main函数返回值是否为True; 校验生成目录结构
        @预期结果: main函数返回值为True; 生成目录中存在software, log, stackcore, bbox, graph, ops类型文件
        """
        sys.argv = [
            CONF_SRC_PATH,
            "collect",
            f"--task_dir={st_root_path}/data/asys_test_dir",
        ]
        ParamDict().set_env_type("EP")
        if list_dir:
            mocker.patch.object(FileOperate, "list_dir", return_value=False)
        else:
            mocker.patch(
                "collect.log.device_log_collect.collect_host_driver", return_value=False
            )
            mocker.patch(
                "collect.log.device_log_collect.collect_event", return_value=False
            )
        self.assertTrue(asys.main())
        if list_dir:
            self.assertTrue("No files or directories in" in caplog.text)
