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
import tempfile

from testcase.conftest import ut_root_path

from common import consts
from collect.ops import collect_ops
from testcase.conftest import AssertTest, test_case_tmp
from params import ParamDict


def setup_module():
    print("TestOpsCollect ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestOpsCollect ut test finish.")  # noqa: T201  # test diagnostic output


class TestOpsCollect(AssertTest):
    def setup_method(self):
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
        pass

    def test_ops_collect_success(self, mocker):
        ret = [
            ("dir", ["subdir"], ["test1.o", "test1.json"]),
            ("dir/subdir", [], ["test2.o", "test2.json"]),
        ]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)

        # collect task
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        self.assertTrue(collect_ops("./output") is None)

        # launch task
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="bash ./test.bash")
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        ParamDict().asys_output_timestamp_dir = ut_root_path
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_collect_sk_scenario(self, mocker):
        # SK场景：dump目录下的host.o仍正常收集，仅跳过按算子名搜索的兜底路径，配置类收集保持不变
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("collect.ops.ops_collect.is_sk_scenario", return_value=True)
        dump_mock = mocker.patch(
            "collect.ops.ops_collect.collect_ops_from_dump", return_value=False
        )
        file_mock = mocker.patch(
            "collect.ops.ops_collect.collect_file", return_value=None
        )
        debug_mock = mocker.patch(
            "collect.ops.ops_collect.collect_debug_kernel", return_value=None
        )
        opp_mock = mocker.patch(
            "collect.ops.ops_collect.collect_opp_config", return_value=True
        )
        custom_mock = mocker.patch(
            "collect.ops.ops_collect.collect_custom_opp_config", return_value=True
        )
        self.assertTrue(collect_ops("./output") is None)
        # dump目录收集仍执行，按算子名搜索的兜底路径在collect_file内部跳过
        dump_mock.assert_called_once()
        file_mock.assert_called_once()
        # 配置类收集仍执行
        debug_mock.assert_called_once()
        opp_mock.assert_called_once()
        custom_mock.assert_called_once()

    def test_ops_collect_sk_scenario_host_o_in_dump(self, mocker):
        # SK场景：dump目录下有host.o时，跳过按算子名搜索的兜底路径，配置类收集保持不变
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("collect.ops.ops_collect.is_sk_scenario", return_value=True)
        dump_mock = mocker.patch(
            "collect.ops.ops_collect.collect_ops_from_dump", return_value=True
        )
        file_mock = mocker.patch(
            "collect.ops.ops_collect.collect_file", return_value=None
        )
        debug_mock = mocker.patch(
            "collect.ops.ops_collect.collect_debug_kernel", return_value=None
        )
        opp_mock = mocker.patch(
            "collect.ops.ops_collect.collect_opp_config", return_value=True
        )
        custom_mock = mocker.patch(
            "collect.ops.ops_collect.collect_custom_opp_config", return_value=True
        )
        self.assertTrue(collect_ops("./output") is None)
        dump_mock.assert_called_once()
        file_mock.assert_not_called()
        # 配置类收集在 collect_ops 里位于 if 块之外，与 dump 收集结果无关，仍须执行
        debug_mock.assert_called_once()
        opp_mock.assert_called_once()
        custom_mock.assert_called_once()

    def test_ops_collect_switch_off(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="0")
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_collect_get_source_dir_failed(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value=False)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_collect_copy_failed(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value=ut_root_path)
        ret = [
            ("dir", ["subdir"], ["test1.o", "test1.json"]),
            ("dir/subdir", [], ["test2.o", "test2.json"]),
        ]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=False)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_collect_get_debug_kernel(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value=ut_root_path)
        mocker.patch("common.FileOperate.check_access", return_value=True)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_OPP_PATH"] = ut_root_path
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_launch_get_debug_kernel(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="0")
        mocker.patch("common.FileOperate.check_access", return_value=True)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_OPP_PATH"] = ut_root_path
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_launch_get_debug_kernel_check_path(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        mocker.patch("common.FileOperate.check_access", return_value=True)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_OPP_PATH"] = ut_root_path
        self.assertTrue(collect_ops(ut_root_path + "/debug_kernel") is None)

    def test_ops_collect_opp_config(self, mocker):
        from collect.ops.ops_collect import collect_opp_config

        mocker.patch("collect.ops.ops_collect.collect_file", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_debug_kernel", return_value=True)
        mocker.patch(
            "collect.ops.ops_collect.collect_custom_opp_config", return_value=True
        )
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_OPP_PATH"] = ut_root_path + "/data/"
        self.assertTrue(collect_opp_config(ut_root_path + "/tempdir/"))
        self.assertTrue(
            os.path.join(ut_root_path, "tempdir", "dfx", "ops", "vendor_config")
        )
        shutil.rmtree(ut_root_path + "/tempdir/")

    def test_ops_collect_custom_opp_config(self, mocker):
        from collect.ops.ops_collect import collect_custom_opp_config

        mocker.patch("collect.ops.ops_collect.collect_file", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_debug_kernel", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_opp_config", return_value=True)
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = (
            ut_root_path + "/data/vendors/customize_1/"
        )
        self.assertTrue(collect_custom_opp_config(ut_root_path + "/tempdir/"))
        self.assertTrue(
            os.path.join(ut_root_path, "tempdir", "dfx", "ops", "custom_config")
        )
        shutil.rmtree(ut_root_path + "/tempdir/")

    def test_ops_collect_get_fault_kernel_name(self, mocker):
        from collect.ops.ops_collect import get_fault_kernel_name

        self.assertTrue(get_fault_kernel_name("./") is None)

        mocker.patch("common.FileOperate.check_dir", return_value=True)
        self.assertTrue(get_fault_kernel_name("./") is None)

        mocker.patch("collect.ops.ops_collect._grep_lines", return_value=[])
        self.assertTrue(get_fault_kernel_name("./") is None)

        mocker.patch(
            "collect.ops.ops_collect._grep_lines",
            return_value=[
                "Aicore kernel execute failed, device_id=0, stream_id=5, report_stream_id=5, task_id=5, flip_num=0, "
                "fault kernel_name=GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision_900016000, program id=1"
            ],
        )
        self.assertTrue(
            get_fault_kernel_name("./")
            == "GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision_900016000"
        )

        mocker.patch(
            "collect.ops.ops_collect._grep_lines",
            return_value=[
                "Aicore kernel execute failed, device_id=0, stream_id=5, report_stream_id=5, task_id=5, flip_num=0, "
                "fault kernel_name=GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision_900016000_mix_aic, program id=1"
            ],
        )
        self.assertTrue(
            get_fault_kernel_name("./")
            == "GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision_900016000"
        )

        mocker.patch(
            "collect.ops.ops_collect._grep_lines",
            return_value=[
                "Aicore kernel execute failed, device_id=0, stream_id=5, report_stream_id=6, task_id=0, flip_num=0, "
                "fault kernel_name=00_11_2_GatherV2, fault kernel info ext=te_gatherv2_097ab5be870f5abfbee16f82ff397"
                "32eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0, program id=1"
            ],
        )
        self.assertTrue(
            get_fault_kernel_name("./")
            == "te_gatherv2_097ab5be870f5abfbee16f82ff39732eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0"
        )

    def test_ops_collect_get_fault_kernel_name_sk_scenario(self, mocker):
        from collect.ops.ops_collect import get_fault_kernel_name

        mocker.patch("common.FileOperate.check_dir", return_value=True)

        # SK场景：标志性打印中的kernelName才是正确的算子名，且优先于fault kernel_name
        mocker.patch(
            "collect.ops.ops_collect._grep_lines",
            return_value=[
                "[Dump][Exception] Begin to dump callback exception. coreType=0, coreId=1, argAddr=0x1, "
                "argSize=64, binHandle=0x2, extraTensorNum=2, kernelName=Add_sk_kernel_900016000."
            ],
        )
        self.assertTrue(get_fault_kernel_name("./") == "Add_sk_kernel_900016000")

    def test_ops_collect_get_fault_kernel_name_sk_not_match(self, mocker):
        from collect.ops.ops_collect import get_sk_kernel_name

        mocker.patch("common.FileOperate.check_dir", return_value=True)

        # 标志性打印存在但无kernelName字段，返回None，退回普通场景逻辑
        mocker.patch(
            "collect.ops.ops_collect._grep_lines",
            return_value=[
                "[Dump][Exception] Begin to dump callback exception. coreType=0, coreId=1."
            ],
        )
        self.assertTrue(get_sk_kernel_name("./") is None)

    def test_ops_collect_grep_lines_oserror(self, mocker):
        # grep 不存在时 subprocess.run 抛 OSError，_grep_lines 应兜住并返回空列表
        from collect.ops.ops_collect import _grep_lines

        mocker.patch("subprocess.run", side_effect=FileNotFoundError("no grep"))
        self.assertTrue(_grep_lines("pattern", "./") == [])

    def test_ops_collect_grep_is_str_when_which_misses(self, mocker):
        # shutil.which 取不到 grep 时 GREP 必须回退为 str，否则 argv[0]=None 会抛 TypeError
        import importlib
        from collect.ops import ops_collect

        mocker.patch("shutil.which", return_value=None)
        try:
            importlib.reload(ops_collect)
            self.assertTrue(isinstance(ops_collect.GREP, str))
        finally:
            mocker.stopall()
            importlib.reload(ops_collect)

    def test_ops_collect_get_fault_kernel_name_files(self, mocker):
        from collect.ops.ops_collect import get_fault_kernel_name_files

        kernel_name = "te_gatherv2_097ab5be870f5abfbee16f82ff39732eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0"
        collect_path = ut_root_path + "/data/"

        self.assertTrue(
            get_fault_kernel_name_files(collect_path, kernel_name)
            == [
                ut_root_path
                + "/data/ops/kernel/GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision.json"
            ]
        )

    def test_ops_collect_collect_fault_kernel_name_files(self, mocker):
        from collect.ops.ops_collect import collect_ops_files_env_var

        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        mocker.patch(
            "collect.ops.ops_collect.get_fault_kernel_name_files", return_value=["./"]
        )
        self.assertTrue(collect_ops_files_env_var("./", "./"))

    def test_ops_collect_collect_ops_from_exception_dump(self, mocker):
        from collect.ops.ops_collect import collect_ops_from_dump

        self.assertTrue(collect_ops_from_dump("./") is False)

        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(collect_ops_from_dump(ut_root_path + "/data/output") is True)

    def test_ops_collect_collect_ops_from_dump_only_o_files(self, mocker):
        from collect.ops.ops_collect import collect_ops_from_dump

        ret = [("data-dump/0", [], ["test_kernel.o"])]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_op_files", return_value=True)
        self.assertTrue(collect_ops_from_dump(ut_root_path + "/data/output") is True)

    def test_ops_collect_collect_ops_from_dump_host_o_real_dir(self):
        # 端到端：真实临时目录下构造 host.o，不mock文件操作，验证确实被搬到 dfx/ops。
        # 相邻用例都mock掉了 os.walk 与 collect_op_files，无法发现 collect_ops_from_dump
        # 的真实行为与mock假设不符。
        from collect.ops.ops_collect import collect_ops_from_dump

        output_root = tempfile.mkdtemp(prefix="ut_ops_dump_")
        try:
            dump_dir = os.path.join(output_root, "dfx", "data-dump", "0")
            os.makedirs(dump_dir)
            host_o = os.path.join(dump_dir, "host.o")
            with open(host_o, "wb") as fw:
                fw.write(b"\x7fELF stub")
            # 非算子文件不应被收集
            with open(
                os.path.join(dump_dir, "exception_info.1"), "w", encoding="utf-8"
            ) as fw:
                fw.write("noise")

            self.assertTrue(collect_ops_from_dump(output_root) is True)

            collected = os.path.join(output_root, "dfx", "ops", "host.o")
            self.assertTrue(os.path.isfile(collected))
            # MOVE_MODE：源文件应已移走
            self.assertTrue(not os.path.exists(host_o))
            # 只收 .o/.json，噪声文件留在原地
            self.assertTrue(os.path.isfile(os.path.join(dump_dir, "exception_info.1")))
            self.assertTrue(
                os.listdir(os.path.join(output_root, "dfx", "ops")) == ["host.o"]
            )
        finally:
            shutil.rmtree(output_root, ignore_errors=True)

    def test_ops_collect_collect_ops_from_dump_no_dump_dir_real(self):
        # 端到端：data-dump 目录不存在时应返回 False，且不创建 dfx/ops。
        from collect.ops.ops_collect import collect_ops_from_dump

        output_root = tempfile.mkdtemp(prefix="ut_ops_nodump_")
        try:
            self.assertTrue(collect_ops_from_dump(output_root) is False)
            self.assertTrue(not os.path.exists(os.path.join(output_root, "dfx", "ops")))
        finally:
            shutil.rmtree(output_root, ignore_errors=True)

    def test_ops_collect_collect_ops_from_dump_no_ops_files(self, mocker):
        from collect.ops.ops_collect import collect_ops_from_dump

        ret = [("data-dump/0", [], ["exception_info.5.1.1706152473105513"])]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        self.assertTrue(collect_ops_from_dump(ut_root_path + "/data/output") is False)

    def test_collect_l0_exception_dump_cache_path(self, mocker):
        from collect.ops.ops_collect import collect_ops_files_env_var

        mocker.patch(
            "collect.ops.ops_collect.get_fault_kernel_name",
            return_value="te_gatherv2_097ab5be870f5abfbee16f82ff39732eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0",
        )
        mocker.patch(
            "collect.ops.ops_collect.collect_ops_from_dump", return_value=False
        )
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        os.environ["ASCEND_PROCESS_LOG_PATH"] = (
            ut_root_path + "/data/asys_test_dir/ascend/log/"
        )
        os.environ["ASCEND_CACHE_PATH"] = ut_root_path + "/data/ops/"
        self.assertTrue(collect_ops_files_env_var(test_case_tmp, "./"))

    def test_collect_l0_exception_dump_work_path(self, mocker):
        from collect.ops.ops_collect import collect_ops_files_env_var

        mocker.patch(
            "collect.ops.ops_collect.get_fault_kernel_name",
            return_value="te_gatherv2_097ab5be870f5abfbee16f82ff39732eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0",
        )
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        mocker.patch(
            "collect.ops.ops_collect.collect_ops_from_dump", return_value=False
        )
        os.environ["ASCEND_WORK_PATH"] = ut_root_path + "/data/"
        os.environ["ASCEND_PROCESS_LOG_PATH"] = (
            ut_root_path + "/data/asys_test_dir/ascend/log/"
        )
        self.assertTrue(collect_ops_files_env_var(test_case_tmp, "./"))

    def test_ops_collect_env_var_empty_state_is_info(self, mocker, caplog):
        # 无故障环境的预期空态：无 dump、无故障 kernel_name 可按名搜索，
        # 应降级为 INFO 空态提示并返回成功语义，不再触发 caller 的
        # "Ops collect failed." WARNING（#385）
        import logging

        from collect.ops.ops_collect import collect_ops_files_env_var

        mocker.patch("params.ParamDict.get_arg", return_value=False)
        mocker.patch("common.FileOperate.check_dir", return_value=False)
        mocker.patch("collect.ops.ops_collect.get_fault_kernel_name", return_value=None)
        with caplog.at_level(logging.INFO):
            self.assertTrue(collect_ops_files_env_var("./output", "./ops") is True)
        self.assertTrue("WARNING" not in caplog.text)
        self.assertTrue("No fault operator file" in caplog.text)

    def test_ops_collect_kernel_found_but_files_missing_is_warning(
        self, mocker, caplog
    ):
        # plog 已解析出故障算子名但候选路径无对应 .o/.json，属真实采集缺失，
        # 必须保留 WARNING 并带上 kernel_name，不得降级为正常空态（#385）
        from collect.ops.ops_collect import collect_ops_files_env_var

        mocker.patch("params.ParamDict.get_arg", return_value=False)
        mocker.patch("common.FileOperate.check_dir", return_value=False)
        mocker.patch(
            "collect.ops.ops_collect.get_fault_kernel_name",
            return_value="fault_kernel_0",
        )
        self.assertTrue(collect_ops_files_env_var("./output", "./ops") is False)
        self.assertTrue("WARNING" in caplog.text)
        self.assertTrue("fault_kernel_0" in caplog.text)
        self.assertTrue("no fault occurred" not in caplog.text)

    def test_collect_file_empty_state_no_warning(self, mocker, caplog):
        # 端到端：无故障空态经过 collect_file 整条路径也不应出现任何 WARNING，
        # 否则 INFO"正常空态"与 WARNING"Ops collect failed."自相矛盾（#385）
        import logging

        from collect.ops.ops_collect import collect_file

        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value=False)
        mocker.patch("collect.ops.ops_collect.is_sk_scenario", return_value=False)
        mocker.patch("common.FileOperate.check_dir", return_value=False)
        mocker.patch("collect.ops.ops_collect.get_fault_kernel_name", return_value=None)
        with caplog.at_level(logging.INFO):
            collect_file("./output")
        self.assertTrue("WARNING" not in caplog.text)

    def test_collect_file_sk_scenario_skip_env_search(self, mocker):
        from collect.ops.ops_collect import collect_file

        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("collect.ops.ops_collect.is_sk_scenario", return_value=True)
        env_search_mock = mocker.patch(
            "collect.ops.ops_collect.collect_ops_files_env_var"
        )
        info_mock = mocker.patch("collect.ops.ops_collect.log_info")
        warn_mock = mocker.patch("collect.ops.ops_collect.log_warning")
        collect_file("./output")
        info_mock.assert_called_once_with(
            "SuperKernel scenario detected, skip searching operator files by kernel name."
        )
        env_search_mock.assert_not_called()
        warn_mock.assert_not_called()

    def test_collect_file_non_sk_calls_env_search(self, mocker):
        from collect.ops.ops_collect import collect_file

        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("collect.ops.ops_collect.is_sk_scenario", return_value=False)
        env_search_mock = mocker.patch(
            "collect.ops.ops_collect.collect_ops_files_env_var", return_value=False
        )
        mocker.patch("collect.ops.ops_collect.log_warning")
        collect_file("./output")
        env_search_mock.assert_called_once()

    def test_collect_file_launch_cmd(self, mocker):
        from collect.ops.ops_collect import collect_file

        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        collect_dir_mock = mocker.patch(
            "common.FileOperate.collect_dir", return_value=True
        )
        warn_mock = mocker.patch("collect.ops.ops_collect.log_warning")
        ParamDict().asys_output_timestamp_dir = ut_root_path
        collect_file("./output")
        collect_dir_mock.assert_called_once()
        warn_mock.assert_not_called()
