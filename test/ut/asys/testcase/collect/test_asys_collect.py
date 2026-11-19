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

from argparse import Namespace

import pytest
import os
import shutil

from testcase.conftest import ut_root_path, set_env, unset_env
from testcase.conftest import AssertTest


from collect import AsysCollect
from collect.msnpureport_type_collect import MSNPUREPORT_TYPE_TIMEOUTS
from params import ParamDict


def setup_module():
    print("TestAsysMain ut test start.")  # noqa: T201  # test diagnostic output
    set_env()


def teardown_module():
    print("TestAsysMain ut test finish.")  # noqa: T201  # test diagnostic output
    unset_env()


class TestAsysCollect(AssertTest):
    def setup_method(self):
        if os.path.exists(os.path.join(ut_root_path, "asys_output_20230227093645758")):
            shutil.rmtree(os.path.join(ut_root_path, "asys_output_20230227093645758"))
        ParamDict().asys_output_timestamp_dir = os.path.join(
            ut_root_path, "asys_output_20230227093645758"
        )

    def teardown_method(self):
        ParamDict.clear()
        if os.path.exists(os.path.join(ut_root_path, "asys_output_20230227093645758")):
            shutil.rmtree(os.path.join(ut_root_path, "asys_output_20230227093645758"))

    def test_collect_calls_msnpureport_type_collect(self, mocker):
        ParamDict().set_env_type("EP")
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch(
            "common.FileOperate.list_dir", return_value=["asys_ut_test_export_tmp"]
        )
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("os.walk")
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)
        type_collect = mocker.patch(
            "collect.asys_collect.collect_msnpureport_type_info", return_value=True
        )

        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())
        type_collect.assert_called_once_with(asys_collect.output_root_path)

    def test_collect_uses_report_subcommand_for_full_export(self, mocker):
        ParamDict().set_env_type("EP")
        commands = []
        timeouts = []

        def fake_run_cmd_output(command, timeout=None, **_kwargs):
            commands.append(command)
            timeouts.append(timeout)
            return True, ""

        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.remove_dir")
        mocker.patch(
            "collect.asys_collect.run_cmd_output",
            side_effect=fake_run_cmd_output,
        )
        mocker.patch("common.FileOperate.list_dir", return_value=["20261112000000"])
        mocker.patch(
            "collect.asys_collect.collect_msnpureport_type_info", return_value=True
        )
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)

        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())
        self.assertTrue(any("msnpureport report -f" in command for command in commands))
        # #399 拍板规格：全量导出命令必须携带 60s 预算
        self.assertTrue(timeouts[-1] == MSNPUREPORT_TYPE_TIMEOUTS["-f"])

    def test_clean_work_removes_typed_export_dir(self, mocker):
        typed_export_path = os.path.join(
            ParamDict().asys_output_timestamp_dir, "export_type_tmp"
        )
        os.makedirs(typed_export_path, exist_ok=True)
        delete_dirs = mocker.patch("common.FileOperate.delete_dirs")

        AsysCollect().clean_work()

        full_export_path = os.path.join(
            ParamDict().asys_output_timestamp_dir, "export_tmp"
        )
        delete_dirs.assert_called_once_with([full_export_path, typed_export_path])

    def test_collect_msnpureport_double_failure_logs_single_error(self, mocker, caplog):
        # The full export fails: collect() must emit exactly one ERROR record
        # for the whole fault (no sys.stderr fragment - msnpureport often
        # fails with an empty stderr). Assert on the record list by level
        # instead of text substrings so unrelated loggers cannot skew it.
        import logging

        caplog.set_level(logging.DEBUG)
        commands = []

        def fake_run_cmd_output(command, timeout=None, **_kwargs):  # noqa: ARG001
            commands.append(command)
            return False, ""

        mocker.patch(
            "collect.asys_collect.run_cmd_output", side_effect=fake_run_cmd_output
        )
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.remove_dir")
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)
        ParamDict().set_env_type("EP")

        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())
        self.assertTrue(len(commands) == 1)
        # Filter to the messages this fault produces: unrelated ERROR noise
        # from the environment-type probe (unsupported platform code) must
        # not make the assertion brittle.
        fault_records = [
            r
            for r in caplog.records
            if r.levelno == logging.ERROR and "msnpureport" in r.getMessage()
        ]
        self.assertTrue(len(fault_records) == 1)
        self.assertTrue(
            "msnpureport tool export device files failed"
            in fault_records[0].getMessage()
        )
        self.assertTrue(all("sys.stderr" not in r.getMessage() for r in caplog.records))

    def test_device_file_export_failure_logs_nothing(self, mocker, caplog):
        # A failed export does not log an error inside _device_file_export
        # (not even a debug with the "failed" wording: the command, ret_code
        # and stderr are already recorded at debug level by run_cmd_output).
        # The single summary error is left to collect().
        import logging

        caplog.set_level(logging.DEBUG)

        def fake_run_cmd_output(command, timeout=None, **_kwargs):  # noqa: ARG001
            return False, ""

        mocker.patch(
            "collect.asys_collect.run_cmd_output", side_effect=fake_run_cmd_output
        )
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.remove_dir")

        asys_collect = AsysCollect()
        self.assertTrue(not asys_collect._device_file_export())
        # _device_file_export itself stays silent about the failure: no ERROR
        # and no debug line carrying "failed" (both wording rules).
        self.assertTrue(
            not any(
                r.levelno == logging.ERROR and "msnpureport" in r.getMessage()
                for r in caplog.records
            )
        )
        self.assertTrue(
            not any(
                r.levelno == logging.DEBUG and "failed" in r.getMessage().lower()
                for r in caplog.records
            )
        )

    @pytest.mark.parametrize(["msnpureport_ok"], [(True,), (False,)])
    def test_collect_msnpureport_failed(self, msnpureport_ok, mocker, caplog):
        # 旧写法 mock subprocess.run 在 #955 传 timeout 后不再被拦截
        # （cmd_run 走 Popen 定时路径），改在 run_cmd_output 层 mock：
        # 导出"成功"但目录为空 → "No files or directories in"；
        # 导出失败 → "msnpureport tool export device files failed"。
        ParamDict().set_env_type("EP")
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("common.FileOperate.remove_dir")
        mocker.patch(
            "collect.asys_collect.run_cmd_output",
            return_value=((True, "") if msnpureport_ok else (False, "boom")),
        )
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)
        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())
        if msnpureport_ok:
            self.assertTrue("No files or directories in" in caplog.text)
        else:
            self.assertTrue(
                "msnpureport tool export device files failed" in caplog.text
            )

    def test_collect_success(self, mocker):
        ParamDict().set_env_type("EP")
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch(
            "common.FileOperate.list_dir", return_value=["asys_ut_test_export_tmp"]
        )
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("os.walk")
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)

        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())

    def test_collect_other_para_error(self, mocker, caplog):
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r=None,
            remote=12345,
            all=None,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)

        asys_collect = AsysCollect()
        self.assertTrue(not asys_collect.collect())
        self.assertTrue(
            "'--remote', '--all' and '--quiet' can be used only when '-r=stacktrace'."
            in caplog.text
        )

    def test_collect_rc_software(self):
        from collect.asys_collect import AsysCollect

        ParamDict().set_env_type("RC")
        AsysCollect().collect_status_info()
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    ut_root_path, "asys_output_20230227093645758", "software_info.txt"
                )
            )
        )
        os.remove(
            os.path.join(
                ut_root_path, "asys_output_20230227093645758", "software_info.txt"
            )
        )

    def test_collect_ep_health_status(self):
        from collect.asys_collect import AsysCollect

        ParamDict().set_env_type("EP")
        AsysCollect().collect_status_info()
        AsysCollect().collect_health_info()
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    ut_root_path, "asys_output_20230227093645758", "software_info.txt"
                )
            )
        )
        os.remove(
            os.path.join(
                ut_root_path, "asys_output_20230227093645758", "software_info.txt"
            )
        )
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    ut_root_path, "asys_output_20230227093645758", "hardware_info.txt"
                )
            )
        )
        os.remove(
            os.path.join(
                ut_root_path, "asys_output_20230227093645758", "hardware_info.txt"
            )
        )
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    ut_root_path, "asys_output_20230227093645758", "health_result.txt"
                )
            )
        )
        os.remove(
            os.path.join(
                ut_root_path, "asys_output_20230227093645758", "health_result.txt"
            )
        )

    def test_collect_run(self, mocker):
        mocker.patch.object(AsysCollect, "collect", return_value=True)
        mocker.patch.object(AsysCollect, "clean_work")
        self.assertTrue(AsysCollect().run())

    def test_collect_status_info_timeout(self, mocker, caplog):
        ParamDict().set_env_type("EP")
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch(
            "common.FileOperate.list_dir", return_value=["asys_ut_test_export_tmp"]
        )
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("os.walk")
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)
        mocker.patch.object(
            AsysCollect, "collect_status_info", side_effect=TimeoutError
        )
        mocker.patch.object(
            AsysCollect, "collect_health_info", side_effect=TimeoutError
        )

        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())
        self.assertTrue(
            "Timeout in retrieving device status information" in caplog.text
        )
        self.assertTrue(
            "Timeout in retrieving device health information" in caplog.text
        )

    def test_collect_status_info_child_process_error(self, mocker, caplog):
        # A worker that dies is not a timeout, so the log has to say so.
        # Otherwise #338's failure reason is invisible in the asys log.
        ParamDict().set_env_type("EP")
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch(
            "common.FileOperate.list_dir", return_value=["asys_ut_test_export_tmp"]
        )
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("os.walk")
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)
        mocker.patch.object(
            AsysCollect,
            "collect_status_info",
            side_effect=ChildProcessError("write_info failed in the timeout worker"),
        )
        mocker.patch.object(
            AsysCollect,
            "collect_health_info",
            side_effect=ChildProcessError("health worker died"),
        )

        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())
        self.assertTrue(
            "Failed to collect device status information: write_info failed in the timeout worker"
            in caplog.text
        )
        self.assertTrue(
            "Failed to collect device health information: health worker died"
            in caplog.text
        )
        # A worker crash is not a timeout, so the timeout message must be gone.
        self.assertTrue(
            "Timeout in retrieving device status information" not in caplog.text
        )

    def test_collect_status_info_raises_child_process_error(self, mocker):
        # The entry point has to carry raise_on_error=True, so a failing
        # AsysInfo.write_info surfaces as a ChildProcessError instead of
        # silently returning None.
        mocker.patch("info.AsysInfo.write_info", side_effect=RuntimeError)
        ParamDict().set_env_type("EP")

        with pytest.raises(ChildProcessError):
            AsysCollect.collect_status_info()
