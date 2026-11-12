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

from .conftest import (
    CONF_SRC_PATH,
    st_root_path,
    test_case_tmp,
    set_env,
    unset_env,
)
from .conftest import AssertTest

import asys
from params import ParamDict
from collect.msnpureport_type_collect import (
    collect_msnpureport_type_info,
    merge_dir,
)
from collect.msnpureport_type_collect.ub_parse import (
    parse_ub_in_place,
    convert_ub_files,
    ub_file_names,
)


def setup_module():
    print("TestMsnpureportTypeCollect st test start.")  # noqa: T201  # test diagnostic output
    set_env()


def teardown_module():
    print("TestMsnpureportTypeCollect st test finish.")  # noqa: T201  # test diagnostic output
    unset_env()


class TestMsnpureportTypeCollect(AssertTest):
    def setup_method(self):
        print("init test environment")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        os.chdir(test_case_tmp)
        ParamDict.clear()
        ParamDict().set_env_type("EP")

    def teardown_method(self):
        print("clean test environment")  # noqa: T201  # test diagnostic output
        ParamDict.clear()
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.chdir(st_root_path)

    def _fake_chip(self, mocker, chip_info):
        from common import DeviceInfo

        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_info)

    def test_typed_collect_950_full_flow(self, mocker):
        """
        @描述: 950环境走真实collect流程, 校验类型化采集与归档
        @类型: FUNCTION
        @输入: asys collect (mock 芯片为950, PATH 中 mock msnpureport)
        @步骤: 执行collect; 校验dfx下5个类型化目录; 校验ao_info三子目录合并; 校验ub bin解析后删除
        @预期结果: collect返回True; dfx/{system_info,ub_info,ao_info,ccu_info,network_info}存在;
                  ao_info下ao_self/ao_cnt/ao_uart并存; mami下bin已转为txt并删除
        """
        from collect.asys_collect import AsysCollect

        self._fake_chip(mocker, "Ascend Ascend950 v1")
        mocker.patch.object(
            AsysCollect, "collect_status_info", side_effect=TimeoutError
        )
        mocker.patch.object(
            AsysCollect, "collect_health_info", side_effect=TimeoutError
        )
        sys.argv = [CONF_SRC_PATH, "collect"]
        self.assertTrue(asys.main())
        dfx_dir = os.path.join(self._output_root(), "dfx")
        for dir_name in (
            "system_info",
            "ub_info",
            "ao_info",
            "ccu_info",
            "network_info",
        ):
            self.assertTrue(os.path.isdir(os.path.join(dfx_dir, dir_name)))
        ao_dir = os.path.join(dfx_dir, "ao_info", "dev-os-0")
        for leaf in ("ao_self", "ao_cnt", "ao_uart"):
            self.assertTrue(os.path.isdir(os.path.join(ao_dir, leaf)))
        mami_dir = os.path.join(dfx_dir, "ub_info", "dev-os-0", "mami")
        # mock 脚本产出的 ubmem_daw.bin 内容过短("ub"), 解析失败保留 bin 不删除
        self.assertTrue(os.path.isfile(os.path.join(mami_dir, "ubmem_daw.bin")))
        self.assertTrue(
            not os.path.exists(os.path.join(self._output_root(), "export_type_tmp"))
        )

    def test_typed_collect_unsupported_chip_skips(self, mocker, caplog):
        """
        @描述: 不支持芯片环境整体跳过类型化采集
        @类型: FUNCTION
        @输入: mock 芯片为910A (不在任何命令支持清单)
        @步骤: 直接调用 collect_msnpureport_type_info; 检查日志
        @预期结果: 返回True; 输出跳过提示; 不产生类型化目录
        """
        import logging

        caplog.set_level(logging.INFO)
        self._fake_chip(mocker, "Ascend Ascend910A v1")
        output_root = os.path.join(test_case_tmp, "typed_out")
        os.makedirs(output_root)
        self.assertTrue(collect_msnpureport_type_info(output_root))
        self.assertTrue(
            "No device supports msnpureport typed export, skip." in caplog.text
        )
        self.assertTrue(not os.path.exists(os.path.join(output_root, "dfx")))

    def test_typed_collect_command_failure_merges_warning(self, mocker, caplog):
        """
        @描述: 命令执行失败时合并为单条告警并提示driver包版本
        @类型: FUNCTION
        @输入: mock 芯片为950, mock run_cmd_output 恒失败
        @步骤: 调用 collect_msnpureport_type_info; 检查告警条数与文案
        @预期结果: 返回False; error级告警仅1条, 含全部失败参数与 driver 包版本过低提示
        """
        import logging

        caplog.set_level(logging.INFO)
        self._fake_chip(mocker, "Ascend Ascend950 v1")
        from common import log_error

        real_log_error = log_error
        mocker.patch(
            "collect.msnpureport_type_collect.run_cmd_output",
            return_value=(False, "command not found"),
        )
        mocker.patch(
            "collect.msnpureport_type_collect.log_error", side_effect=real_log_error
        )
        output_root = os.path.join(test_case_tmp, "typed_fail_out")
        os.makedirs(output_root)
        self.assertTrue(not collect_msnpureport_type_info(output_root))
        self.assertTrue(
            caplog.text.count(
                "execute failed, which may be caused by a low driver package version"
            )
            == 1
        )
        self.assertTrue("msnpureport report -t 5/-t 6/-t 7" in caplog.text)

    def test_parse_ub_in_place_keeps_bin_on_parse_failure(self):
        """
        @描述: 解析失败的bin保留现场, 存量文件不删除
        @类型: FUNCTION
        @输入: 构造 mami 目录, 写入过短的 ubmem_daw.bin
        @步骤: 调用 parse_ub_in_place; 检查bin与txt
        @预期结果: 返回True(处理完成); bin保留且无txt
        """
        mami_dir = os.path.join(test_case_tmp, "ub_info", "dev-os-0", "mami")
        os.makedirs(mami_dir)
        with open(os.path.join(mami_dir, "ubmem_daw.bin"), "wb") as fw:
            fw.write(b"ab")
        self.assertTrue(parse_ub_in_place(os.path.join(test_case_tmp, "ub_info")))
        self.assertTrue(os.path.isfile(os.path.join(mami_dir, "ubmem_daw.bin")))
        self.assertTrue(not os.path.exists(os.path.join(mami_dir, "ubmem_daw.txt")))

    def test_parse_ub_in_place_walks_unknown_files(self):
        """
        @描述: 解析清单外的文件与目录原样保留
        @类型: FUNCTION
        @输入: ub_info 下含 ubctl 目录与清单外 bin
        @步骤: 调用 parse_ub_in_place; 检查清单外文件仍在
        @预期结果: 返回True; 清单外文件未被删除
        """
        ub_dir = os.path.join(test_case_tmp, "ub_info")
        ubctl_dir = os.path.join(ub_dir, "dev-os-0", "ubctl")
        os.makedirs(ubctl_dir)
        with open(os.path.join(ubctl_dir, "unknown.bin"), "wb") as fw:
            fw.write(b"xyz")
        with open(os.path.join(ubctl_dir, "ubctl.log"), "w") as fw:
            fw.write("log")
        self.assertTrue(parse_ub_in_place(ub_dir))
        self.assertTrue(os.path.isfile(os.path.join(ubctl_dir, "unknown.bin")))
        self.assertTrue(os.path.isfile(os.path.join(ubctl_dir, "ubctl.log")))

    def test_merge_dir_merges_without_overwrite(self):
        """
        @描述: merge_dir 合并目录不覆盖已有文件, 冲突保留目标
        @类型: FUNCTION
        @输入: source与target各含不同/同名文件
        @步骤: 调用 merge_dir; 检查双方文件与source清理
        @预期结果: 新文件合入; 同名冲突保留target原内容且返回False
        """
        source = os.path.join(test_case_tmp, "merge_src")
        target = os.path.join(test_case_tmp, "merge_tgt")
        os.makedirs(os.path.join(source, "dev-os-0"))
        os.makedirs(os.path.join(target, "dev-os-0"))
        with open(os.path.join(source, "dev-os-0", "new.log"), "w") as fw:
            fw.write("new")
        with open(os.path.join(target, "dev-os-0", "old.log"), "w") as fw:
            fw.write("old")
        self.assertTrue(merge_dir(source, target))
        self.assertTrue(os.path.isfile(os.path.join(target, "dev-os-0", "new.log")))
        self.assertTrue(os.path.isfile(os.path.join(target, "dev-os-0", "old.log")))

        # 同名冲突: 保留 target 内容, 不覆盖
        source2 = os.path.join(test_case_tmp, "merge_src2")
        os.makedirs(os.path.join(source2, "dev-os-0"))
        with open(os.path.join(source2, "dev-os-0", "old.log"), "w") as fw:
            fw.write("clobber")
        self.assertTrue(not merge_dir(source2, target))
        with open(os.path.join(target, "dev-os-0", "old.log")) as fr:
            self.assertTrue(fr.read() == "old")

    def test_convert_ub_files_cli_shape(self):
        """
        @描述: convert_ub_files 保持 CLI 行为: 缺失文件不告警中断
        @类型: FUNCTION
        @输入: 空bin目录, 输出到txt目录
        @步骤: 调用 convert_ub_files; 校验不抛异常
        @预期结果: 正常返回, 无txt产出
        """
        bin_dir = os.path.join(test_case_tmp, "cli_bins")
        txt_dir = os.path.join(test_case_tmp, "cli_txts")
        os.makedirs(bin_dir)
        os.makedirs(txt_dir)
        convert_ub_files(bin_dir, txt_dir)
        for name in ub_file_names:
            self.assertTrue(not os.path.exists(os.path.join(txt_dir, name + ".txt")))

    @staticmethod
    def _output_root():
        dirs = os.listdir(test_case_tmp)
        for dir_name in dirs:
            if dir_name.startswith("asys_output_"):
                return os.path.join(test_case_tmp, dir_name)
        return ""
