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
from argparse import Namespace
from pathlib import Path
from queue import Queue
import subprocess

import pytest
from testcase.conftest import test_trace_tmp, ut_root_path, great_bin


from analyze import AsysAnalyze
from collect import AsysCollect
from common.task_common import create_out_timestamp_dir
from analyze.coredump_analyze import CoreDump, thread_stacks_reg_info
from collect.stackcore.stackcore_collect import ParseStackCore
from params import ParamDict
from common import DeviceInfo
from ..conftest import AssertTest


class Put:
    def put(self, *args):
        pass


class Stdin:
    def write(self, a):
        pass


class PopenMock:
    def __init__(self, *_args, **_kwargs):
        self.stdin = Stdin()
        self.stdout = None

    def communicate(self):
        with open(
            f"{ut_root_path}/data/coredump/core-coredump-8032-1717033942.txt",
            "r",
            encoding="utf-8",
        ) as f:
            gdb_str = f.read()
        return gdb_str, 0


class PopenMockError:
    def __init__(self, *_args, **_kwargs):
        self.stdin = Stdin()
        self.stdout = None

    def communicate(self):
        with open(
            f"{ut_root_path}/data/coredump/core-coredump-8032-1717033943_error.txt",
            "r",
            encoding="utf-8",
        ) as f:
            gdb_str = f.read()
        return gdb_str, 0


class TestAsysAnalyze(AssertTest):
    @staticmethod
    def setup_method():
        if os.path.exists(test_trace_tmp):
            shutil.rmtree(test_trace_tmp)
        os.mkdir(test_trace_tmp)
        ParamDict.clear()

    @staticmethod
    def teardown_method():
        ParamDict.clear()
        if os.path.exists(test_trace_tmp):
            os.chmod(test_trace_tmp, 0o777)  # nosec B103  # test asserts permission-mask behavior
            shutil.rmtree(test_trace_tmp)

    def test_set_path_file(self, mocker):
        os.mkdir(os.path.join(test_trace_tmp, "test"))
        great_bin(os.path.join(test_trace_tmp, "test", "test.bin"))
        task_file = os.path.join(test_trace_tmp, "test", "test.bin")
        args = Namespace(
            subparser_name="analyze",
            r="trace",
            path=None,
            file=task_file,
            output=test_trace_tmp,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            reg=0,
            d=0,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        self.assertTrue(AsysAnalyze().run())

    def test_set_path_path(self, mocker):
        os.mkdir(os.path.join(test_trace_tmp, "test"))
        great_bin(os.path.join(test_trace_tmp, "test", "test.bin"))
        args = Namespace(
            subparser_name="analyze",
            r="trace",
            path=os.path.join(test_trace_tmp, "test"),
            file=None,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
            reg=0,
            d=0,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_coredump(self, mocker):
        coredump_file = os.path.join(
            ut_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        args = Namespace(
            subparser_name="analyze",
            r="coredump",
            path=None,
            file=None,
            reg=0,
            d=0,
            exe_file="python",
            core_file=coredump_file,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        mocker.patch("subprocess.Popen", return_value=PopenMock())
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_stackcore(self, mocker):
        coredump_file = os.path.join(
            ut_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        args = Namespace(
            subparser_name="analyze",
            r="stackcore",
            path=None,
            file=coredump_file,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=ut_root_path,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(ParseStackCore, "parse_line", return_value=True)
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_stackcore_binary_path_from_maps(self, mocker):
        coredump_file = os.path.join(
            ut_root_path,
            "data/coredump/stackcore_tracer_6_570350_atrace_test_20241010031221412850.txt",
        )
        args = Namespace(
            subparser_name="analyze",
            r="stackcore",
            path=None,
            file=coredump_file,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=ut_root_path,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(ParseStackCore, "parse_line", return_value=True)
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_stackcore_path(self, mocker):
        coredump_file = os.path.join(ut_root_path, "data")
        args = Namespace(
            subparser_name="analyze",
            r="stackcore",
            path=coredump_file,
            file=None,
            reg=0,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=ut_root_path,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_stackcore_no_symbol_path(self):
        coredump_file = os.path.join(ut_root_path, "data/coredump/")
        args = Namespace(
            subparser_name="analyze",
            r="stackcore",
            path=coredump_file,
            file=None,
            reg=1,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_stackcore_not_path(self, mocker):
        args = Namespace(
            subparser_name="analyze",
            r="stackcore",
            path=None,
            file=None,
            reg=0,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=ut_root_path,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        self.assertTrue(not AsysAnalyze().run())

    def test_asys_analyze_coredump_thread_stacks(self, mocker, capsys):
        coredump_file = os.path.join(
            ut_root_path, "data/coredump/coredump_reg_info.txt"
        )
        p = PopenMock()
        stdout = open(coredump_file, "r", encoding="utf-8")
        self.assertTrue(True)
        try:
            p.stdout = stdout

            mocker.patch("subprocess.Popen", return_value=p)
            q_reg_info = Queue()
            thread_stacks_reg_info(
                "",
                "Thread 2 (40896)",
                ["#0 0x7f05887750a3 0x7f058876a000 xxxx.so"],
                q_reg_info,
            )
        finally:
            stdout.close()
        reg_info = q_reg_info.get()
        self.assertTrue(
            reg_info
            == {
                "Thread 2 (40896)": {
                    "#00": ["0x7f97e0e6aec0", "0x7f97e0e6aec0", "0x7f97e37bd765"]
                }
            }
        )

    def test_asys_analyze_coredump_threads(self, mocker, capsys):
        mocker.patch("analyze.coredump_analyze.machine", return_value="x86_64")
        mocker.patch("params.param_dict.ParamDict.get_arg", return_value=0)
        obj = CoreDump("", "", "", "")
        reg_0 = obj.get_threads_stacks_reg_info()
        self.assertTrue(reg_0 == {})

        mocker.patch("params.param_dict.ParamDict.get_arg", return_value=1)
        obj = CoreDump("", "", "", "")
        obj.bt_info = {"Thread 2 (40896)": ["#0 0x7f05887750a3 0x7f058876a000 xxxx.so"]}
        coredump_file = os.path.join(
            ut_root_path, "data/coredump/coredump_reg_info.txt"
        )
        p = PopenMock()
        stdout = open(coredump_file, "r", encoding="utf-8")
        p.stdout = stdout
        mocker.patch("subprocess.Popen", return_value=p)
        reg_1 = obj.get_threads_stacks_reg_info()
        self.assertTrue(
            reg_1
            == {
                "Thread 2 (40896)": [
                    "0x7f97e0e6aec0",
                    "0x7f97e0e6aec0",
                    "0x7f97e37bd765",
                ]
            }
        )

    def test_asys_analyze_coredump_stack_uses_one_worker_on_single_cpu(self, mocker):
        worker_counts = []

        class PoolStub:
            def __init__(self, count):
                worker_counts.append(count)

            def apply_async(self, *args, **kwargs):
                return None

            def close(self):
                return None

            def join(self):
                return None

        mocker.patch("analyze.coredump_analyze.cpu_count", return_value=1)
        mocker.patch("analyze.coredump_analyze.Pool", PoolStub)
        mocker.patch(
            "analyze.coredump_analyze.Manager"
        ).return_value.Queue.return_value.qsize.return_value = 0
        obj = CoreDump("", "", "", "")
        obj._get_reg_info_level_stack()
        self.assertTrue(worker_counts == [1])

    def test_asys_analyze_coredump_stack_add_reg(self, mocker, capsys):
        self.assertTrue(True)
        mocker.patch("subprocess.Popen", return_value=PopenMock())

        class Put:
            def put(*args):
                pass

        obj = CoreDump("", "", "", "")
        self.assertTrue(obj._stack_add_reg("xxx", "", "") == "xxx")
        self.assertTrue(obj._stack_add_reg("xxx", "#0", {}) == "xxx")
        mocker.patch("analyze.coredump_analyze.machine", return_value="aarch64")
        self.assertTrue(
            obj._stack_add_reg("xxx", "#0", {"#0": [1, 2, 3]})
            == "xxx   fp = 1    sp = 2\n   pc = 3\n"
        )
        mocker.patch("analyze.coredump_analyze.machine", return_value="x86_64")
        self.assertTrue(
            obj._stack_add_reg("xxx", "#0", {"#0": [1, 2, 3]})
            == "xxx   rbp = 1    rsp = 2\n   rip = 3\n"
        )
        mocker.patch("analyze.coredump_analyze.machine", return_value="AMD64")
        self.assertTrue(obj._stack_add_reg("xxx", "#0", {"#0": [1, 2, 3]}) == "xxx")

    def test_asys_analyze_coredump_not_gdb(self, mocker, caplog):
        coredump_file = os.path.join(
            ut_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        args = Namespace(
            subparser_name="analyze",
            r="coredump",
            path=None,
            file=None,
            reg=0,
            d=0,
            exe_file="rtstest_host1",
            core_file=coredump_file,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("analyze.asys_analyze.check_command", return_value=False)
        self.assertTrue(not AsysAnalyze().run())
        self.assertTrue(
            "Gdb does not exist, install gdb before using it" in caplog.text
        )

    @pytest.mark.parametrize(
        "content, res",
        [
            (
                """Program terminated with signal SIGSEGV, Segmentation fault.\nrtstest_host1: No such file or directory.\n""",
                "No such file or directory",
            ),
            (
                """Program terminated with signal SIGSEGV, Segmentation fault.\ncore file may not match specified executable file.\n""",
                "Core file may not match specified executable file",
            ),
        ],
    )
    def test_asys_analyze_coredump_error(self, content, res, mocker, caplog):
        codedump_err = Path(
            f"{ut_root_path}/data/coredump/core-coredump-8032-1717033943_error.txt"
        )
        codedump_err.write_text(content, encoding="utf-8")
        coredump_file = os.path.join(
            ut_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        args = Namespace(
            subparser_name="analyze",
            r="coredump",
            path=None,
            file=None,
            reg=0,
            d=0,
            exe_file="rtstest_host1",
            core_file=coredump_file,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        mocker.patch("subprocess.Popen", return_value=PopenMockError())
        self.assertTrue(not AsysAnalyze().run())

    def test_asys_analyze_get_source_location(self, mocker):
        parse = ParseStackCore(os.path.join(ut_root_path))
        mocker.patch("subprocess.check_output", return_value=" main\n120 ".encode())
        func_name, file_line = parse.get_source_location("test.so", 10543)
        self.assertTrue(func_name == "main")
        self.assertTrue(file_line == "120")

    def test_asys_analyze_parse_line(self, mocker):
        self.assertTrue(True)
        parse = ParseStackCore(os.path.join(ut_root_path))
        mocker.patch("subprocess.check_output", return_value=" main\n120 ".encode())
        self.assertTrue(
            not parse.parse_line(
                0, "#0 0x7ffff7a17926 0x7ffff79d8000 /home/test/libatrace_test.so", [0]
            )
        )

    def test_asys_analyze_parse_line_symbol_path(self, mocker):
        self.assertTrue(True)
        parse = ParseStackCore(os.path.join(ut_root_path))
        parse.symbol_path = "./"
        mocker.patch("subprocess.check_output", return_value=" main\n120 ".encode())
        self.assertTrue(
            not parse.parse_line(
                0, "#0 0x7ffff7a17926 0x7ffff79d8000 /home/test/libatrace_test.so", [0]
            )
        )

    def test_asys_analyze_get_source_location_with_error(self, mocker):
        parse = ParseStackCore(
            "",
            os.path.join(
                ut_root_path,
                "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
            ),
        )
        mocker.patch(
            "subprocess.check_output",
            return_value="addr2line: DWARF error: section .debug_info is larger than its filesize! \nclock_nanosleep\n??:?".encode(),
        )
        func_name, file_line = parse.get_source_location("test.so", 10543)
        self.assertTrue(func_name == "clock_nanosleep")
        self.assertTrue(file_line == "??:?")
        msg = parse.output_logs["test.so"]
        self.assertTrue(
            msg == "test.so  section .debug_info is larger than its filesize! "
        )

    def test_asys_analyze_get_source_location_command_error(self, mocker):
        parse = ParseStackCore(
            "",
            os.path.join(
                ut_root_path,
                "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
            ),
        )
        mocker.patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(1, "addr2line"),
        )
        self.assertTrue(parse.get_source_location("test.so", 10543) == [])

    def test_asys_analyze_write_res_file_type_error(self, mocker, caplog):
        parse = object.__new__(AsysAnalyze)
        parse.output = ut_root_path
        mocker.patch("os.open", return_value=1)
        mocker.patch("os.fdopen", side_effect=TypeError("invalid content"))
        parse.write_res_file("result.txt", None)
        self.assertTrue("invalid content" in caplog.text)

    def test_asys_analyze_get_line_with_addr2line(self, mocker):
        self.assertTrue(True)

        def case_func(a, b):
            return ["clock_nanosleep", "??:?", "main", 120]

        mocker.patch("subprocess.check_output", return_value=" main\n120 ".encode())
        parse = ParseStackCore(os.path.join(ut_root_path))
        parse.get_source_location = case_func
        ret = parse._get_line_with_addr2line(
            "", "address", "0x00007ffff7a17926", "test.so"
        )
        self.assertTrue(
            ret
            == "### 0x00007ffff7a17926 clock_nanosleep in ??:? from test.so\n###                    main in 120 from test.so\n"
        )

    def test_asys_analyze_set_maps_addr_binary_path(self):
        stackcore_file = os.path.join(
            ut_root_path,
            "data/coredump/stackcore_tracer_6_570350_atrace_test_20241010031221412850.txt",
        )
        parse = ParseStackCore(None)
        with open(stackcore_file, "r", encoding="utf-8") as f:
            file_lines = f.readlines()
        parse.set_maps_addr_binary_path(file_lines)
        self.assertTrue(
            parse.maps_addr_binary_path[94218685685760]
            == "/home/gwb/stackcore_unwind/atrace_test"
        )
        self.assertTrue(
            parse.maps_addr_binary_path[139658125152256]
            == "/usr/lib/x86_64-linux-gnu/libnss_files-2.31.so"
        )
        self.assertTrue(
            parse.maps_addr_binary_path[139658125234176]
            == "/usr/lib/x86_64-linux-gnu/librt-2.31.so"
        )
        self.assertTrue(
            parse.maps_addr_binary_path[139658134937600]
            == "/usr/lib/x86_64-linux-gnu/libc-2.31.so"
        )
        self.assertTrue(
            parse.maps_addr_binary_path[139658137460736]
            == "/usr/lib/x86_64-linux-gnu/ld-2.31.so"
        )

    def test_asys_analyze_get_line_with_addr2line_error(self, mocker):
        self.assertTrue(True)

        def case_func(a, b):
            return ["clock_nanosleep", "??:?", "main", 120]

        mocker.patch("subprocess.check_output", return_value=" main\n120 ")
        parse = ParseStackCore(os.path.join(ut_root_path))
        ret = parse._get_line_with_addr2line(
            "", "address", "0x00007ffff7a17926", "test.so"
        )
        self.assertTrue(ret == "")

    def test_asys_analyze_aicore_error_have_path(self, mocker):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(
            ParamDict, "asys_output_timestamp_dir", return_value=test_trace_tmp
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        analyze = AsysAnalyze()
        analyze.output = test_trace_tmp
        analyze.path = os.path.join(ut_root_path, "data")
        analyze.run_mode = "aicore_error"
        self.assertTrue(analyze.run())

    def test_asys_analyze_aicore_error_not_path(self, mocker):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(AsysCollect, "run", return_value=True)
        mocker.patch.object(
            ParamDict, "asys_output_timestamp_dir", return_value=test_trace_tmp
        )
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        analyze = AsysAnalyze()
        analyze.output = test_trace_tmp
        analyze.run_mode = "aicore_error"
        self.assertTrue(analyze.run())

    def test_asys_analyze_aicore_error_not_path_collect_failed(self, mocker):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch.object(AsysCollect, "run", return_value=False)
        mocker.patch.object(
            ParamDict, "asys_output_timestamp_dir", return_value=test_trace_tmp
        )
        mocker.patch("os.path.exists", return_value=True)
        analyze = AsysAnalyze()
        analyze.output = test_trace_tmp
        analyze.run_mode = "aicore_error"
        ParamDict().set_env_type("EP")
        self.assertTrue(not analyze.run())

    def test_asys_analyze_ub_not_path(self, mocker):
        """
        The ub mode needs the path to the UB data collection file. Without
        it the command must fail instead of reporting success.
        """
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(
            ParamDict, "asys_output_timestamp_dir", return_value=test_trace_tmp
        )
        analyze = AsysAnalyze()
        analyze.output = test_trace_tmp
        analyze.path = None
        analyze.run_mode = "ub"
        self.assertTrue(not analyze.run())

    def test_asys_analyze_ub_have_path(self, mocker):
        """
        With the path given, the ub mode converts the UB files and
        reports success.
        """
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(
            ParamDict, "asys_output_timestamp_dir", return_value=test_trace_tmp
        )
        mocker.patch.object(AsysAnalyze, "_convert_ub_ubnl_dfx_statistic")
        mocker.patch.object(AsysAnalyze, "_convert_ub_ubnl_dfx_ssu_schedule")
        mocker.patch.object(AsysAnalyze, "_convert_ub_ubnl_dfx_config_item")
        analyze = AsysAnalyze()
        analyze.output = test_trace_tmp
        analyze.path = os.path.join(ut_root_path, "data")
        analyze.run_mode = "ub"
        self.assertTrue(analyze.run())

    def test_asys_analyze_aicore_error_not_have_msaicerr(self, mocker, caplog, capsys):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # nosec B602  # test mock creation
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch.object(AsysCollect, "run", return_value=True)
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch.object(
            ParamDict, "asys_output_timestamp_dir", return_value=test_trace_tmp
        )
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        analyze = AsysAnalyze()
        analyze.output = test_trace_tmp
        analyze.run_mode = "aicore_error"
        ParamDict().set_env_type("EP")
        self.assertTrue(not analyze.run())
        self.assertTrue(
            "The path of the msaicerr tool cannot be found, please install the whole package"
            in caplog.text
        )

    def test_asys_analyze_coretrace(self, mocker):
        coredump_file = os.path.join(
            ut_root_path, "data/coredump/coretrace_1738757896_22994_test"
        )
        args = Namespace(
            subparser_name="analyze",
            r="coretrace",
            path=None,
            file=coredump_file,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("os.path.exists", return_value=True)
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_coretrace_with_binary(self, mocker):
        coredump_file = os.path.join(
            ut_root_path, "data/coredump/coretrace_1738757896_22994_test"
        )
        lib_path = os.path.join(ut_root_path, "data/coredump/")
        args = Namespace(
            subparser_name="analyze",
            r="coretrace",
            path=None,
            file=coredump_file,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=lib_path,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch(
            "collect.coretrace.coretrace_collect.ParseCoreTrace.run_addr2line",
            return_value=["test_func"],
        )
        mocker.patch("os.path.exists", return_value=True)
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_coretrace_run_addr2line_failed(self, mocker, caplog):
        coredump_file = os.path.join(
            ut_root_path, "data/coredump/coretrace_1738757896_22994_test"
        )
        lib_path = os.path.join(ut_root_path, "data/coredump/")
        args = Namespace(
            subparser_name="analyze",
            r="coretrace",
            path=None,
            file=coredump_file,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=lib_path,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch(
            "collect.coretrace.coretrace_collect.ParseCoreTrace.run_addr2line",
            side_effect=OSError("run addr2line failed"),
        )
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_coretrace_no_addr2line(self, mocker, caplog):
        coredump_file = os.path.join(
            ut_root_path, "data/coredump/coretrace_1738757896_22994_test"
        )
        args = Namespace(
            subparser_name="analyze",
            r="coretrace",
            path=None,
            file=coredump_file,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch(
            "collect.coretrace.coretrace_collect.check_command", return_value=False
        )
        self.assertTrue(not AsysAnalyze().run())
        self.assertTrue(
            "The addr2line tool does not exist, install it before using it"
            in caplog.text
        )

    def test_asys_analyze_coretrace_dir(self, mocker, caplog):
        coretrace_path = os.path.join(ut_root_path, "data/coredump/")
        args = Namespace(
            subparser_name="analyze",
            r="coretrace",
            path=coretrace_path,
            file=None,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_coretrace_other_file(self, mocker, caplog):
        coredump_file = os.path.join(
            ut_root_path, "data/coredump/coredump_reg_info.txt"
        )
        args = Namespace(
            subparser_name="analyze",
            r="coretrace",
            path=None,
            file=coredump_file,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("os.path.exists", return_value=True)
        self.assertTrue(not AsysAnalyze().run())
        self.assertTrue("not in coretrace format" in caplog.text)

    def test_asys_analyze_coretrace_empty_file(self, mocker, caplog):
        coredump_file = os.path.join(ut_root_path, "data/coredump/coretrace_empty")
        with open(coredump_file, "w", encoding="utf-8"):
            pass
        args = Namespace(
            subparser_name="analyze",
            r="coretrace",
            path=None,
            file=coredump_file,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("os.path.exists", return_value=True)
        self.assertTrue(not AsysAnalyze().run())
        self.assertTrue("file is empty" in caplog.text)

    def test_asys_analyze_coretrace_parse_failed(self, mocker, caplog):
        coredump_file = os.path.join(ut_root_path, "data/coredump/coretrace_error")
        args = Namespace(
            subparser_name="analyze",
            r="coretrace",
            path=None,
            file=coredump_file,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=test_trace_tmp,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        mocker.patch("os.path.exists", return_value=True)
        self.assertTrue(AsysAnalyze().run())

    def test_asys_analyze_path_output_same(self, mocker, caplog):
        coredump_file = os.path.join(ut_root_path, "data/coredump")
        args = Namespace(
            subparser_name="analyze",
            r="coretrace",
            path=coredump_file,
            file=None,
            reg=2,
            d=0,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=None,
            output=coredump_file,
        )
        ParamDict().set_args(args)
        create_out_timestamp_dir()
        self.assertTrue(not AsysAnalyze().run())
        self.assertTrue(
            'The output directory cannot be the same as the "path" directory or its subdirectories.'
            in caplog.text
        )
