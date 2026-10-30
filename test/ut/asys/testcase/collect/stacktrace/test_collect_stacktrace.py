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
from argparse import Namespace

from testcase.conftest import ut_root_path

from common import RetCode
from collect.stacktrace.stacktrace_collect import AsysStackTrace, AscendTraceDll
from testcase.conftest import AssertTest
from params import ParamDict


class AsysTrace:
    def sigqueue(self, *_args):
        os.mknod(
            f"{ut_root_path}/data/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_202411.bin"
        )

        return 0

    def AtraceStackcoreParse(self, *_args):
        return 0


class AsysTraceError:
    def sigqueue(self, *_args):
        return 1

    def AtraceStackcoreParse(self, *_args):
        return 1


def setup_module():
    print("TestCollectStackAtrace ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestCollectStackAtrace ut test finish.")  # noqa: T201  # test diagnostic output


class TestCollectStackAtrace(AssertTest):
    def setup_method(self):
        ParamDict.clear()

    def teardown_method(self):
        if os.path.exists(
            f"{ut_root_path}/data/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_202411.bin"
        ):
            os.remove(
                f"{ut_root_path}/data/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_202411.bin"
            )
        ParamDict.clear()

    def test_get_all_tid_accepts_single_thread_process(self, mocker):
        stacktrace = AsysStackTrace.__new__(AsysStackTrace)
        stacktrace.remote_id = 12345
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.popen_run_cmd",
            return_value="23456\n",
        )

        self.assertTrue(
            stacktrace._get_all_tid_of_process(current_pid=99999) == ["23456"]
        )

    def test_collect_stacktrace_send_signal_attr_error(self, mocker, caplog):
        class AsysTraceNoSigqueue:
            def inotify_init(self):
                return 0

        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTraceNoSigqueue(),
        )
        obj = AscendTraceDll()
        obj.send_signal_to_pid(True, 12345)
        expected_msg = "Send signal failed, error msg: 'AsysTraceNoSigqueue' object has no attribute 'sigqueue'."
        self.assertTrue(expected_msg in caplog.text)

    def test_get_target_work_path_decode_error(self, mocker):
        from collect.stacktrace.stacktrace_collect import AsysStackTrace

        mocker.patch.object(AsysStackTrace, "__init__", return_value=None)
        asys_stack = AsysStackTrace()
        asys_stack.remote_id = 12345
        mocker.patch(
            "builtins.open",
            side_effect=UnicodeDecodeError(
                "utf-8", b"\xff", 0, 1, "invalid start byte"
            ),
        )
        mocker.patch("os.path.join", return_value="/proc/12345/environ")
        self.assertTrue(asys_stack._get_target_work_path() is None)

    def test_collect_stacktrace_send_signal_error(self, mocker):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTraceError(),
        )
        obj = AscendTraceDll()
        ret = obj.send_signal_to_pid(True, 12345)
        self.assertTrue(ret is False)

    def test_collect_stacktrace_send_signal_success(self, mocker):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        obj = AscendTraceDll()
        ret = obj.send_signal_to_pid(True, 12345)
        self.assertTrue(ret is True)

    def test_collect_stacktrace_parse_bin_attr_error(self, mocker, caplog):
        class AsysTraceNoParse:
            def inotify_init(self):
                return 0

        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTraceNoParse(),
        )
        obj = AscendTraceDll()
        obj.parse_stackcore_bin_to_txt("./test.bin")
        self.assertTrue("Parse stackcore bin file failed, error msg:" in caplog.text)

    def test_collect_stacktrace_parse_bin_error(self, mocker):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTraceError(),
        )
        obj = AscendTraceDll()
        ret = obj.parse_stackcore_bin_to_txt("./test.bin")
        self.assertTrue(ret is False)

    def test_collect_stacktrace_parse_bin_success(self, mocker):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        obj = AscendTraceDll()
        ret = obj.parse_stackcore_bin_to_txt("./test.bin")
        self.assertTrue(ret is True)

    def test_collect_stacktrace_param_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        args = Namespace(
            subparser_name="collect",
            task_dir="./",
            output=None,
            tar=None,
            r="stacktrace",
            remote=12345,
            all=None,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        AsysStackTrace().run()
        self.assertTrue(
            "'--task_dir', and '--tar' can be used only when '-r' is not used."
            in caplog.text
        )

    def test_collect_stacktrace_with_remote_0_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=0,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        AsysStackTrace().run()
        self.assertTrue(
            'The value of "--remote" must be greater than 1, input: 0.' in caplog.text
        )

    def test_collect_stacktrace_without_remote_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=None,
            all=None,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        AsysStackTrace().run()
        self.assertTrue(
            '"-r=stacktrace" must be used together with "--remote" and "--all".'
            in caplog.text
        )

    def test_collect_stacktrace_trace_dll_error(self, mocker):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=RetCode.FAILED,
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=12345,
            all=None,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        ret = AsysStackTrace().run()
        self.assertTrue(ret is False)

    def test_collect_stacktrace_remote_exists_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=1,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        AsysStackTrace().run()
        self.assertTrue(
            'The value of "--remote" must be greater than 1, input: 1.' in caplog.text
        )

    def test_collect_stacktrace_pid_not_exists_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=9999999999999999,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        AsysStackTrace().run()
        self.assertTrue("No such process, id: 9999999999999999." in caplog.text)

    def test_collect_stacktrace_parallel_pid_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        cmd_ret = "root       43389    3488  0 08:20 pts/2    00:00:00 \npython3 tools/asys/asys.py collect -r=stacktrace --remote=123456"
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.popen_run_cmd", return_value=cmd_ret
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=12345,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        ret = AsysStackTrace().run()
        self.assertTrue(not ret)
        self.assertTrue("Get pid failed by remote: 12345." in caplog.text)

    def test_collect_stacktrace_parallel_remote_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
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
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=12345,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        ret = AsysStackTrace().run()
        self.assertTrue(not ret)
        self.assertTrue("Collect stacktrace not support Parallelism." in caplog.text)

    def test_collect_stacktrace_parallel_all_tid_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
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
            return_value=[],
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=23456,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        ret = AsysStackTrace().run()
        self.assertTrue(not ret)
        self.assertTrue("Collect stacktrace not support Parallelism." in caplog.text)

    def test_collect_stacktrace_parallel_tid_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
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
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=23456,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        ret = AsysStackTrace().run()
        self.assertTrue(not ret)
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
        cmd_ret = (
            "root       43389    3488   0 08:20 pts/2    00:00:00 python3 tools/asys/asys.py collect -r=stacktrace --remote=12345\n"
            "root       22652    8264   0 08:20 pts/2    00:00:00 cd /home;source setenv.bash;python3 tools/asys/asys.py collect -r=stacktrace --remote=23456\n"
        )
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.popen_run_cmd", return_value=cmd_ret
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        mocker.patch("os.kill", return_value=True)
        mocker.patch("os.getppid", return_value=22652)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=23456,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        ret = AsysStackTrace()._get_other_stacktrace_remote_id(43390)
        self.assertTrue(ret == ["12345"])

    def test_collect_stacktrace_asys_send_signal_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        mocker.patch(
            "collect.stacktrace.interface.AscendTraceDll.send_signal_to_pid",
            return_value=False,
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=12345,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        ret = AsysStackTrace().run()
        self.assertTrue(not ret)

    def test_collect_stacktrace_asys_bin_file_timeout(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        mocker.patch(
            "collect.stacktrace.stacktrace_collect.AsysStackTrace._check_remote_id_validity",
            return_value=True,
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("time.sleep", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = ut_root_path + "/data/test/"
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=12345,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        ret = AsysStackTrace().run()
        self.assertTrue(not ret)
        self.assertTrue(
            "get the stackcore bin file in path" in caplog.text
            and "timeout" in caplog.text
        )

    def test_collect_stacktrace_asys_parse_error(self, mocker, caplog):
        mocker.patch(
            "collect.stacktrace.interface.LoadSoType.get_ascend_trace",
            return_value=AsysTrace(),
        )
        mocker.patch("collect.stacktrace.stacktrace_collect.f.remove_dir")
        mocker.patch(
            "collect.stacktrace.interface.AscendTraceDll.parse_stackcore_bin_to_txt",
            return_value=False,
        )
        mocker.patch("os.kill", return_value=True)
        mocker.patch("time.sleep", return_value=True)
        mocker.patch("collect.stacktrace.stacktrace_collect.input", return_value="y")
        os.environ["ASCEND_WORK_PATH"] = ut_root_path + "/data/"
        args = Namespace(
            subparser_name="collect",
            task_dir=None,
            output=None,
            tar=None,
            r="stacktrace",
            remote=12345,
            all=True,
            quiet=None,
            timeout=None,
        )
        ParamDict().set_args(args)
        ret = AsysStackTrace().run()
        self.assertTrue(not ret)

    def test_collect_stacktrace_wait_bin_file_generate(self, mocker, caplog):
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
        os.environ["ASCEND_WORK_PATH"] = ut_root_path + "/data/"
        ret = AsysStackTrace()._wait_bin_file_generate(5)
        self.assertTrue(not ret)

    def test_clear_dfx_log_remove_log_files(self, mocker):
        mocker.patch(
            "os.listdir",
            return_value=["stackcore_tracer_35_a.log", "stackcore_tracer_35_b.log"],
        )
        mocker.patch("os.path.isfile", return_value=True)
        mock_remove = mocker.patch("os.remove")
        AsysStackTrace._clear_dfx_log("/fake/dir")
        self.assertTrue(mock_remove.call_count == 2)
        mock_remove.assert_any_call(
            os.path.join("/fake/dir", "stackcore_tracer_35_a.log")
        )
        mock_remove.assert_any_call(
            os.path.join("/fake/dir", "stackcore_tracer_35_b.log")
        )

    def test_clear_dfx_log_keep_non_log_files(self, mocker):
        mocker.patch(
            "os.listdir",
            return_value=[
                "stackcore_tracer_35_trace.log",
                "stackcore.bin",
                "stackcore.txt",
            ],
        )
        mocker.patch("os.path.isfile", return_value=True)
        mock_remove = mocker.patch("os.remove")
        AsysStackTrace._clear_dfx_log("/fake/dir")
        self.assertTrue(mock_remove.call_count == 1)
        mock_remove.assert_called_once_with(
            os.path.join("/fake/dir", "stackcore_tracer_35_trace.log")
        )

    def test_clear_dfx_log_empty_dir(self, mocker):
        mocker.patch("os.listdir", return_value=[])
        mock_remove = mocker.patch("os.remove")
        AsysStackTrace._clear_dfx_log("/fake/dir")
        self.assertTrue(mock_remove.call_count == 0)
