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
import subprocess
import shutil

from testcase.conftest import ASYS_SRC_PATH, ut_root_path, test_case_tmp
import asys

from params import ParamDict
from collect import AsysCollect
from launch import AsysLaunch
from ..conftest import AssertTest
from common import FileOperate as f
from common.const import RetCode


def setup_module():
    print("TestAsysLaunch ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestAsysLaunch ut test finish.")  # noqa: T201  # test diagnostic output


class TestAsysLaunch(AssertTest):
    def setup_method(self):
        ParamDict().asys_output_timestamp_dir = os.path.join(
            ut_root_path, "asys_output_20230227093645758"
        )
        ParamDict().set_ini("DUMP_GE_GRAPH", "2")
        ParamDict().set_ini("DUMP_GRAPH_LEVEL", "2")
        ParamDict().set_ini("ASCEND_GLOBAL_LOG_LEVEL", "1")
        ParamDict().set_ini("ASCEND_GLOBAL_EVENT_ENABLE", "1")
        ParamDict().set_ini("ASCEND_SLOG_PRINT_TO_STDOUT", "0")
        ParamDict().set_ini("ASCEND_HOST_LOG_FILE_NUM", "1000")
        ParamDict().set_ini(
            "NPU_COLLECT_PATH",
            os.path.join(
                ParamDict().asys_output_timestamp_dir, "npu_collect_intermediates"
            ),
        )

    def teardown_method(self):
        ParamDict.clear()

    def test_launch_env_missing_ini_item(self, mocker, monkeypatch, caplog):
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        obj = AsysLaunch()
        obj.env_prepare = {
            "NPU_COLLECT_PATH": test_case_tmp + "/test_collect",
            "ASCEND_WORK_PATH": test_case_tmp + "/test_work",
            "DUMP_GE_GRAPH": ParamDict().get_ini("DUMP_GE_GRAPH_NOT_EXIST"),
        }
        # The ini item is absent, get_ini() returns the boolean False.
        self.assertTrue(obj.env_prepare["DUMP_GE_GRAPH"] is False)
        # Pre-set a user value: the skip must neither overwrite nor delete it
        # (the warning promises "keeps a user-set value unchanged"), so the
        # surviving ext_val pins both aspects at once.
        monkeypatch.setenv("DUMP_GE_GRAPH", "ext_val")
        monkeypatch.delenv("ASCEND_WORK_PATH", raising=False)
        monkeypatch.delenv("NPU_COLLECT_PATH", raising=False)

        ret = obj.prepare_for_launch()
        self.assertTrue(ret != RetCode.FAILED)
        self.assertTrue(os.environ.get("DUMP_GE_GRAPH") == "ext_val")
        # Pin the warning semantics: blame the missing asys.ini item
        # (with ini key and default), not "the variable is not set".
        self.assertTrue(
            "The asys.ini item dump_ge_graph is not configured" in caplog.text
        )
        self.assertTrue("default value: 2." in caplog.text)

    def test_launch_env_missing_ini_item_uses_ini_key_name(
        self, mocker, monkeypatch, caplog
    ):
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        obj = AsysLaunch()
        obj.env_prepare = {
            "NPU_COLLECT_PATH": test_case_tmp + "/test_collect",
            "ASCEND_WORK_PATH": test_case_tmp + "/test_work",
            "ASCEND_GLOBAL_LOG_LEVEL": ParamDict().get_ini(
                "ASCEND_GLOBAL_LOG_LEVEL_NOT_EXIST"
            ),
        }
        self.assertTrue(obj.env_prepare["ASCEND_GLOBAL_LOG_LEVEL"] is False)
        monkeypatch.setenv("ASCEND_GLOBAL_LOG_LEVEL", "ext_val")
        monkeypatch.delenv("ASCEND_WORK_PATH", raising=False)
        monkeypatch.delenv("NPU_COLLECT_PATH", raising=False)

        ret = obj.prepare_for_launch()
        self.assertTrue(ret != RetCode.FAILED)
        self.assertTrue(os.environ.get("ASCEND_GLOBAL_LOG_LEVEL") == "ext_val")
        # ASCEND_GLOBAL_LOG_LEVEL maps to the ini key "log_level", not the
        # lowercased env name: the warning must name the real ini key (a
        # user configuring "ascend_global_log_level" would be rejected by
        # config_parser as not available) and the mapped default "INFO".
        self.assertTrue("The asys.ini item log_level is not configured" in caplog.text)
        self.assertTrue("default value: INFO." in caplog.text)

    def test_launch_env_ini_item_present(self, mocker, monkeypatch):
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        ParamDict().set_ini("DUMP_GE_GRAPH", "2")
        obj = AsysLaunch()
        obj.env_prepare = {
            "NPU_COLLECT_PATH": test_case_tmp + "/test_collect",
            "ASCEND_WORK_PATH": test_case_tmp + "/test_work",
            "DUMP_GE_GRAPH": ParamDict().get_ini("DUMP_GE_GRAPH"),
        }
        # delenv up front so monkeypatch restores the external values and
        # reverts what this test writes, replacing handwritten pops.
        monkeypatch.delenv("DUMP_GE_GRAPH", raising=False)
        monkeypatch.delenv("ASCEND_WORK_PATH", raising=False)
        monkeypatch.delenv("NPU_COLLECT_PATH", raising=False)

        ret = obj.prepare_for_launch()
        self.assertTrue(ret != RetCode.FAILED)
        self.assertTrue(os.environ.get("DUMP_GE_GRAPH") == "2")

    def test_launch_task_success(self, mocker):
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("params.ParamDict.get_arg", return_value="bash ./test.bash")
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("collect.AsysCollect.collect", return_value=True)
        asys_launch = AsysLaunch()
        self.assertTrue(asys_launch.launch())

    def test_launch_task_failed(self, mocker):
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("params.ParamDict.get_arg", return_value="bash ./test.bash")
        fake_ret = subprocess.Popen(
            "unknown_command",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("collect.AsysCollect.collect", return_value=True)
        asys_launch = AsysLaunch()
        self.assertTrue(asys_launch.launch())

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

    def test_launch_status_health(self):
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        os.chdir(test_case_tmp)

        sys.argv = [ASYS_SRC_PATH, "launch", "--task=bash ./test.bash"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        dirs = os.listdir(test_case_tmp)
        if not dirs:
            return False
        asys_out_dir = os.path.join(test_case_tmp, dirs[0])
        self.assertTrue(
            not os.path.exists(os.path.join(asys_out_dir, "npu_collect_intermediates"))
        )
        shutil.rmtree(test_case_tmp)

    def test_launch_prepare(self, mocker, caplog):
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("params.ParamDict.get_arg", return_value="bash ./test.bash")
        fake_ret = subprocess.Popen(
            "sleep 30",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("collect.AsysCollect.collect", return_value=True)
        mocker.patch("launch.AsysLaunch.prepare_for_launch", return_value=False)
        asys_launch = AsysLaunch()
        self.assertTrue(not asys_launch.launch())
        self.assertTrue("Prepare for launch failed." in caplog.text)

    def test_task_out_collect(self, mocker, caplog):
        mocker.patch("os.path.join")
        mocker.patch.object(f, "write_file")
        mocker.patch.object(AsysCollect, "collect", return_value=False)
        launch = AsysLaunch()
        launch.task_out_collect(test_case_tmp)
        self.assertTrue("Collect information after task failed" in caplog.text)
