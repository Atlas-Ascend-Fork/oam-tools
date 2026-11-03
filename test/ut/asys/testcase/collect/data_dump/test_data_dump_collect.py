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

from testcase.conftest import ut_root_path

from collect.data_dump.data_dump_collect import collect_data_dump, get_source_dir
from params import ParamDict
from common import consts
from testcase.conftest import AssertTest


def setup_module():
    print("TestDataDumpCollect ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestDataDumpCollect ut test finish.")  # noqa: T201  # test diagnostic output


class TestDataDumpCollect(AssertTest):
    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_data_dump_collect_success_launch(self, mocker, caplog):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        ParamDict.asys_output_timestamp_dir = ut_root_path
        collect_data_dump("./output")
        self.assertTrue("failed" not in caplog.text)

    def test_data_dump_collect_success_collect(self, mocker, caplog):
        mocker.patch(
            "params.ParamDict.asys_output_timestamp_dir", return_value=ut_root_path
        )
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        collect_data_dump("./output")
        self.assertTrue("failed" not in caplog.text)

    def test_data_dump_collect_empty_state_is_info(self, mocker, caplog):
        # 无故障环境的预期空态：候选路径下没有 extra-info/data-dump 可采集，
        # 应降级为 INFO 空态提示，不再以 WARNING + "failed" 误导用户（#385）
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=False)
        with caplog.at_level(logging.INFO):
            collect_data_dump("./output")
        self.assertTrue("WARNING" not in caplog.text)
        self.assertTrue("No dump data" in caplog.text)

    def test_data_dump_collect_copy_failed_is_warning(self, mocker, caplog):
        # 源目录存在但拷贝失败属真实采集失败，必须保留 WARNING（#385）
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=False)
        collect_data_dump("./output")
        self.assertTrue("WARNING" in caplog.text)
        self.assertTrue("failed" in caplog.text)

    def test_data_dump_get_collect_path_npu(self, mocker):
        mocker.patch(
            "params.ParamDict.asys_output_timestamp_dir", return_value=ut_root_path
        )
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("os.path.exists", return_value=True)

        os.environ["NPU_COLLECT_PATH"] = ut_root_path
        path = get_source_dir()
        self.assertTrue(path == os.path.join(ut_root_path, "extra-info", "data-dump"))

        os.environ.pop("NPU_COLLECT_PATH")

    def test_data_dump_get_collect_path_work(self, mocker, caplog):
        mocker.patch(
            "params.ParamDict.asys_output_timestamp_dir", return_value=ut_root_path
        )
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)

        os.environ["ASCEND_WORK_PATH"] = ut_root_path
        path = get_source_dir()
        self.assertTrue(path == os.path.join(ut_root_path, "extra-info", "data-dump"))

        self.assertTrue("failed" not in caplog.text)
        os.environ.pop("ASCEND_WORK_PATH")
