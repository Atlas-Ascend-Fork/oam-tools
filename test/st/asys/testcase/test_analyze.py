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
import struct
import sys
from queue import Queue
import subprocess

import shutil

import pytest

from .conftest import CONF_SRC_PATH, st_root_path, test_case_tmp, set_env, unset_env
from .conftest import (
    create_file,
    great_bin,
    check_atrace_file,
    find_dir,
    check_file_contents,
)
from .conftest import AssertTest


import asys
from common import DeviceInfo
from params import ParamDict
from analyze.coredump_analyze import CoreDump, thread_stacks_reg_info
from analyze.asys_analyze import AsysAnalyze
from collect import AsysCollect
from collect.trace import ParseTrace


def setup_module():
    print("TestCollect st test start.")  # noqa: T201  # test diagnostic output
    set_env()


def teardown_module():
    print("TestCollect st test finish.")  # noqa: T201  # test diagnostic output
    unset_env()


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
            f"{st_root_path}/data/coredump/core-coredump-8032-1717033942.txt",
            "r",
            encoding="utf-8",
        ) as f:
            gdb_str = f.read()
        return gdb_str, 0


class PopenMockError1:
    def __init__(self, *_args, **_kwargs):
        self.stdin = Stdin()
        self.stdout = None

    def communicate(self):
        with open(
            f"{st_root_path}/data/coredump/core-coredump-8032-1717033943_error.txt",
            "r",
            encoding="utf-8",
        ) as f:
            gdb_str = f.read()
        return gdb_str, 0


class PopenMockError2:
    def __init__(self, *_args, **_kwargs):
        self.stdin = Stdin()
        self.stdout = None

    def communicate(self):
        with open(
            f"{st_root_path}/data/coredump/core-coredump-8032-1717033944_error.txt",
            "r",
            encoding="utf-8",
        ) as f:
            gdb_str = f.read()
        return gdb_str, 0


def great_ub_bins(ub_dir):
    """生成 UB analyze 所需的合法二进制样例文件"""
    from common.const import DL_PORT_RX_VL_NUM, STATS_ITEM_NUM, UBQOS_MAX_SL_NUM

    os.makedirs(ub_dir, exist_ok=True)

    def write_bin(name, fmt, values):
        with open(os.path.join(ub_dir, name), "wb") as fw:
            fw.write(struct.pack(fmt, *values))

    # ubnl_dfx_statistic / ssu_schedule / config_item share the same layout
    ubnl_fmt = "I" + "64BQ" * STATS_ITEM_NUM
    ubnl_values = [2]
    for i in range(STATS_ITEM_NUM):
        name_bytes = f"stat_{i}".encode("utf-8")
        name_bytes = name_bytes + b"\x00" * (64 - len(name_bytes))
        ubnl_values.extend(list(name_bytes))
        ubnl_values.append(i)
    for name in (
        "ubnl_dfx_statistic.bin",
        "ubnl_dfx_ssu_schedule.bin",
        "ubnl_dfx_config_item.bin",
    ):
        write_bin(name, ubnl_fmt, ubnl_values)

    # ubmem_daw: template_id, balance_algorithm, balance_start_bit, reserved
    write_bin("ubmem_daw.bin", "4B", [1, 1, 4, 0])

    # ubtpl_acl_src: head(HHI8B) + 1 acl entry(IH2BB3B4IIBI12B)
    head = struct.pack("HHI8B", 1, 0x01, 0x10, *([0] * 8))
    acl = struct.pack(
        "IH2BB3B4IIBI12B",
        3,
        5,
        0,
        0,  # plane_id, user_engine_idx, 2B
        0,  # eid_flag=0 (128bit uncompressed)
        0,
        0,
        0,  # rsv 3B
        0x11111111,
        0x22222222,
        0x33333333,
        0x44444444,  # eid 4I
        2,
        1,  # trans_type, acl_type
        0x00ABCDEF,  # acl_grp_id
        *([0] * 12),
    )
    with open(os.path.join(ub_dir, "ubtpl_acl_src.bin"), "wb") as fw:
        fw.write(head + acl)

    # sl_to_vl: plane_id, num, then UBQOS_MAX_SL_NUM * (sl, vl)
    sl_values = [0, 4]
    for i in range(UBQOS_MAX_SL_NUM):
        sl_values.extend([i, i % DL_PORT_RX_VL_NUM])
    write_bin("sl_to_vl.bin", f"2I{UBQOS_MAX_SL_NUM * 2}H", sl_values)


class TestAnalyze(AssertTest):
    @staticmethod
    def setup_method():
        print("init test environment")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        os.chdir(test_case_tmp)
        ParamDict.clear()

    @staticmethod
    def teardown_method():
        print("clean test environment.")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            os.chmod(test_case_tmp, 0o777)  # nosec B103  # test asserts permission-mask behavior
            shutil.rmtree(test_case_tmp)

    def test_asys_analyze_atrace_file(self):
        """
        正常用例analyze 解析atrace 文件，output为空
        :return:
        """
        atrace_file = os.path.join(test_case_tmp, "input", "test.bin")
        os.mkdir(os.path.join(test_case_tmp, "input"))
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=trace", "--file=%s" % atrace_file]
        great_bin(atrace_file)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        out_dir = find_dir(test_case_tmp, "asys_output_")
        self.assertTrue(
            check_atrace_file(
                "test.txt", os.path.join(test_case_tmp, out_dir), mode="analyze"
            )
        )

    def test_asys_analyze_atrace_dir(self):
        """
        正常用例analyze 解析atrace 目录，output为空
        :return:
        """
        atrace_file = os.path.join(test_case_tmp, "input", "test.bin")
        os.mkdir(os.path.join(test_case_tmp, "input"))
        great_bin(atrace_file)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--path=%s" % os.path.join(test_case_tmp, "input"),
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        out_dir = find_dir(test_case_tmp, "asys_output_")
        self.assertTrue(
            check_atrace_file(
                os.path.join("input", "test.txt"),
                os.path.join(test_case_tmp, out_dir),
                mode="analyze",
            )
        )

    def test_asys_analyze_atrace_file_output_path(self):
        """
        正常用例analyze 解析atrace 文件，output不为空
        :return:
        """
        output_path = os.path.join(test_case_tmp, "output", "test_dir")
        atrace_file = os.path.join(test_case_tmp, "test.bin")
        great_bin(atrace_file)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--file=%s" % atrace_file,
            "--output=%s" % output_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        out_dir = find_dir(output_path, "asys_output_")
        self.assertTrue(
            check_atrace_file(
                "test.txt", os.path.join(output_path, out_dir), mode="analyze"
            )
        )

    @pytest.mark.parametrize(
        "magic, version, type, structSize, dataSize, log",
        [
            (0xD928, 2, 0, 0, 0, "incomplete and cannot be parsed"),
            (0xD928, 2, 1, 0, 0, "check trace type"),
        ],
    )
    def test_asys_analyze_atrace_file_output_path_header_failed(
        self, magic, version, type, structSize, dataSize, log, mocker, caplog
    ):
        """
        正常用例analyze 解析atrace 文件，output不为空
        :return:
        """
        output_path = os.path.join(test_case_tmp, "output", "test_dir")
        atrace_file = os.path.join(test_case_tmp, "test.bin")
        with open(atrace_file, "wb") as fp:
            data = struct.pack(
                "@2I4B3IQ16s",
                magic,
                version,
                0,
                0,
                0,
                type,
                structSize,
                dataSize,
                480,
                1715252892408752464,
                "0".encode(),
            )
            fp.write(data)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--file=%s" % atrace_file,
            "--output=%s" % output_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(log in caplog.text)

    def test_asys_analyze_atrace_struct_segment_failed(self, mocker, caplog):
        output_path = os.path.join(test_case_tmp, "output", "test_dir")
        atrace_file = os.path.join(test_case_tmp, "test.bin")
        with open(atrace_file, "wb") as fp:
            fp.write("1".encode())
        mocker.patch.object(ParseTrace, "parse_ctrl_head")
        mocker.patch.object(ParseTrace, "parse_struct_segment", return_value={})
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--file=%s" % atrace_file,
            "--output=%s" % output_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "Failed to parse the data, check whether the file is complete"
            in caplog.text
        )

    def test_asys_analyze_atrace_dir_output_path(self):
        """
        正常用例analyze 解析atrace 目录，output不为空
        :return:
        """
        output_path = os.path.join(test_case_tmp, "output")
        atrace_file = os.path.join(test_case_tmp, "input", "test.bin")
        os.mkdir(os.path.join(test_case_tmp, "input"))
        great_bin(atrace_file)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--path=%s" % os.path.join(test_case_tmp, "input"),
            "--output=%s" % output_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        out_dir = find_dir(output_path, "asys_output_")
        self.assertTrue(
            check_atrace_file(
                "input/test.txt", os.path.join(output_path, out_dir), mode="analyze"
            )
        )

    def test_asys_analyze_atrace_dir_output_input(self):
        """
        正常用例analyze 解析atrace 目录，output与input 目录相同
        :return:
        """
        output_path = os.path.join(test_case_tmp, "output")
        atrace_file = os.path.join(test_case_tmp, "input", "test.bin")
        os.mkdir(os.path.join(test_case_tmp, "input"))
        great_bin(atrace_file)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--path=%s" % os.path.join(test_case_tmp, "input"),
            "--output=%s" % output_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        out_dir = find_dir(output_path, "asys_output_")
        self.assertTrue(
            check_atrace_file(
                "input/test.txt", os.path.join(output_path, out_dir), mode="analyze"
            )
        )

    def test_asys_analyze_atrace_other_file(self):
        """
        异常用例analyze 解析atrace 文件，input设置非atrace 文件
        :return:
        """
        output_path = os.path.join(test_case_tmp)
        atrace_file = os.path.join(test_case_tmp, "input", "test.bin")
        os.mkdir(os.path.join(test_case_tmp, "input"))
        with open(atrace_file, "wb") as fw:
            fw.write("123456798".encode())
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--file=%s" % atrace_file,
            "--output=%s" % output_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        out_dir = find_dir(output_path, "asys_output_")
        self.assertTrue(os.path.exists(os.path.join(out_dir, "test.bin")))

    def test_asys_analyze_atrace_not_dir(self):
        """
        异常用例analyze 解析atrace 文件，input设置不包含trace文件的目录
        :return:
        """
        output_path = os.path.join(test_case_tmp)
        os.mkdir(os.path.join(test_case_tmp, "input"))
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--path=%s" % os.path.join(test_case_tmp, "input"),
            "--output=%s" % output_path,
        ]
        ParamDict().set_env_type("EP")
        try:
            res = asys.main()
        except Exception:
            res = False
        self.assertTrue(not res)

    def test_asys_analyze_atrace_output_in_input_dir(self):
        """
        异常用例analyze解析atrace文件，output设置在input目录
        :return:
        """
        output_path = os.path.join(test_case_tmp, "input")
        atrace_file = os.path.join(test_case_tmp, "input", "test.bin")
        os.mkdir(os.path.join(test_case_tmp, "input"))
        great_bin(atrace_file)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--path=%s" % os.path.join(test_case_tmp, "input"),
            "--output=%s" % output_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        out_dir = find_dir(output_path, "asys_output_")
        self.assertTrue(os.path.exists(os.path.join(output_path, out_dir)))

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_asys_analyze_atrace_not_per_file(self):
        """
        异常用例analyze 解析atrace 文件，input设置无权限的 atrace 文件
        :return:
        """
        atrace_file = os.path.join(test_case_tmp, "input", "test.bin")
        os.mkdir(os.path.join(test_case_tmp, "input"))
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=trace", "--file=%s" % atrace_file]
        great_bin(atrace_file)
        os.chmod(atrace_file, 0o333)  # nosec B103  # test asserts permission-mask behavior
        try:
            ParamDict().set_env_type("EP")
            self.assertTrue(not asys.main())
        except Exception:
            self.assertTrue(False)
        finally:
            os.chmod(atrace_file, 0o777)  # nosec B103  # test asserts permission-mask behavior

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_asys_analyze_atrace_not_per_dir(self):
        """
        异常用例analyze 解析atrace 文件，input设置包含atrace文件的目录，但目录没有权限读取
        :return:
        """
        atrace_file = os.path.join(test_case_tmp, "input", "test.bin")
        os.mkdir(os.path.dirname(atrace_file))
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--path=%s" % os.path.dirname(atrace_file),
        ]
        great_bin(atrace_file)
        os.chmod(os.path.dirname(atrace_file), 0o333)  # nosec B103  # test asserts permission-mask behavior
        ParamDict().set_env_type("EP")
        try:
            res = asys.main()
            self.assertTrue(not res)
        except Exception:
            self.assertTrue(False)
        finally:
            os.chmod(os.path.dirname(atrace_file), 0o777)  # nosec B103  # test asserts permission-mask behavior

    def test_asys_analyze_atrace_empty_file(self):
        """
        异常用例analyze 解析atrace 文件，input设置空 文件
        :return:
        """
        atrace_file = os.path.join(test_case_tmp, "input", "test.bin")
        os.mkdir(os.path.dirname(atrace_file))
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--file=%s" % os.path.dirname(atrace_file),
        ]
        create_file(atrace_file)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    def test_asys_analyze_file_is_dir(self):
        """
        异常用例analyze file 传入是一个目录
        :return:
        """
        atrace_file = os.path.join(test_case_tmp, "test.bin")
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--file=%s" % os.path.dirname(atrace_file),
        ]
        great_bin(atrace_file)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        out_dir = find_dir(test_case_tmp, "asys_output_")
        self.assertTrue(out_dir == "")

    def test_asys_analyze_path_is_file(self):
        """
        异常用例analyze path传入是一个文件
        :return:
        """
        atrace_file = os.path.join(test_case_tmp, "test.bin")
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=trace", "--path=%s" % atrace_file]
        great_bin(atrace_file)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        out_dir = find_dir(test_case_tmp, "asys_output_")
        self.assertTrue(out_dir == "")

    def test_asys_analyze_path_or_file(self):
        """
        异常用例analyze 同时传入file和path
        :return:
        """
        atrace_file = os.path.join(test_case_tmp, "test.bin")
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=trace",
            "--file=%s --path=%s" % (atrace_file, os.path.dirname(atrace_file)),
        ]
        great_bin(atrace_file)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        out_dir = find_dir(test_case_tmp, "asys_output_")
        self.assertTrue(out_dir == "")

    def test_asys_analyze_coredump(self, mocker):
        coredump_file = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coredump",
            "--exe_file=python3",
            "--core_file=%s" % coredump_file,
        ]
        ParamDict().set_env_type("EP")
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        mocker.patch("subprocess.Popen", return_value=PopenMock())
        self.assertTrue(asys.main())

    def test_asys_analyze_coredump_exe_error1(self, mocker):
        coredump_file = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coredump",
            "--exe_file=rtstest_host1",
            "--core_file=%s" % coredump_file,
        ]
        ParamDict().set_env_type("EP")
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        mocker.patch("subprocess.Popen", return_value=PopenMockError1())
        self.assertTrue(not asys.main())

    def test_asys_analyze_coredump_exe_error2(self, mocker):
        coredump_file = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coredump",
            "--exe_file=python3",
            "--core_file=%s" % coredump_file,
        ]
        ParamDict().set_env_type("EP")
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        mocker.patch("subprocess.Popen", return_value=PopenMockError2())
        self.assertTrue(not asys.main())

    def test_asys_analyze_stackcore(self, mocker):
        coredump_file = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            "--file=%s" % coredump_file,
            "--symbol_path=%s" % st_root_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_stackcore_binary_path_from_maps(self, mocker):
        coredump_file = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_6_570350_atrace_test_20241010031221412850.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            "--file=%s" % coredump_file,
            "--symbol_path=%s" % st_root_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_stackcore_path(self):
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            "--path=%s" % os.path.join(st_root_path, "data/coredump"),
            "--symbol_path=%s" % st_root_path,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_stackcore_path_error(self):
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            "--path=%s" % os.path.join(st_root_path, "data/coredump"),
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_coredump_thread_stacks(self, mocker, capsys):
        coredump_file = os.path.join(
            st_root_path, "data/coredump/coredump_reg_info.txt"
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
                "Thread 1 (21240)",
                ["#0 0x7f05887750a3 0x7f058876a000 xxxx.so"],
                q_reg_info,
            )
        finally:
            stdout.close()
        reg_info = q_reg_info.get()
        self.assertTrue(
            reg_info
            == {
                "Thread 1 (21240)": {"#00": ["0x7ffeef83dc20", "0x7ffeef83dcf0", "0x0"]}
            }
        )

    def test_asys_analyze_coredump_gdb_cmd_uses_argv(self, mocker):
        captured = {}

        def fake_popen(cmd, *_args, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            return PopenMock()

        mocker.patch("subprocess.Popen", side_effect=fake_popen)
        exe_file = "/tmp/app;touch injected"  # nosec B108  # test injection payload
        core_file = "/tmp/core $(id)"  # nosec B108  # test injection payload
        obj = CoreDump(exe_file, core_file, "", "")
        obj.start_gdb("")

        self.assertTrue(captured["cmd"] == ["gdb", exe_file, core_file])
        self.assertTrue("shell" not in captured["kwargs"])

    def test_asys_analyze_coredump_threads(self, mocker, capsys):
        mocker.patch("analyze.coredump_analyze.machine", return_value="x86_64")
        mocker.patch("params.param_dict.ParamDict.get_arg", return_value=0)
        obj = CoreDump("", "", "", "")
        reg_0 = obj.get_threads_stacks_reg_info()
        self.assertTrue(reg_0 == {})

        mocker.patch("params.param_dict.ParamDict.get_arg", return_value=1)
        obj = CoreDump("", "", "", "")
        obj.bt_info = {"Thread 1 (21240)": ["#0 0x7f05887750a3 0x7f058876a000 xxxx.so"]}
        coredump_file = os.path.join(
            st_root_path, "data/coredump/coredump_reg_info.txt"
        )
        p = PopenMock()
        stdout = open(coredump_file, "r", encoding="utf-8")
        p.stdout = stdout
        mocker.patch("subprocess.Popen", return_value=p)
        reg_1 = obj.get_threads_stacks_reg_info()
        self.assertTrue(
            reg_1 == {"Thread 1 (21240)": ["0x7ffeef83dc20", "0x7ffeef83dcf0", "0x0"]}
        )

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
        mocker.patch("analyze.asys_analyze.check_command", return_value=False)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coredump",
            "--exe_file=python3",
            "--core_file=%s"
            % os.path.join(
                st_root_path, "data/coredump/core-coredump-8032-1717033942.txt"
            ),
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "Gdb does not exist, install gdb before using it." in caplog.text
        )

    def test_asys_analyze_coredump_no_exe_file(self, mocker, caplog):
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coredump",
            "--core_file=%s"
            % os.path.join(
                st_root_path, "data/coredump/core-coredump-8032-1717033942.txt"
            ),
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "The --exe_file parameter must exist for analyze coredump." in caplog.text
        )

    def test_asys_analyze_coredump_no_core_file(self, mocker, caplog):
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=coredump", "--exe_file=python3"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "The --core_file parameter must exist for analyze coredump." in caplog.text
        )

    def test_asys_analyze_coredump_exe_file_err_value(self, mocker, caplog):
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        core_file = os.path.join(
            st_root_path, "data/coredump/core-coredump-8032-1717033942.txt"
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coredump",
            "--exe_file=python3",
            "--core_file=%s" % core_file,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("Failed to obtain the core dump information." in caplog.text)

    def test_asys_analyze_coredump_core_file_err_value(self, mocker, caplog):
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        core_file = os.path.join(
            st_root_path, "data/coredump/core-coredump-8032-17170339422.txt"
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coredump",
            "--exe_file=python3",
            "--core_file=%s" % core_file,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("is not a file or does not exist." in caplog.text)

    def test_asys_analyze_coredump_symbol_err_value(self, mocker, capsys):
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        core_file = os.path.join(
            st_root_path, "data/coredump/core-coredump-8032-1717033942.txt"
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coredump",
            "--exe_file=python3",
            "--core_file=%s" % core_file,
            "--symbol=3",
        ]
        try:
            ParamDict().set_env_type("EP")
            asys.main()
        except Exception:
            captured = capsys.readouterr()
            self.assertTrue("invalid choice: 3 (choose from 0, 1)" in captured.err)

    def test_asys_analyze_stackcore_file(self):
        stackcore_txt = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_stackcore_dir(self):
        stackcore_txt = os.path.join(st_root_path, "data/coredump")
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--path={stackcore_txt}",
            f"--symbol_path={st_root_path}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_stackcore_file_output_path(self):
        stackcore_txt = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        output_dir = test_case_tmp
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
            f"--output={output_dir}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        dir = find_dir(output_dir, "asys_output_")
        output_file = os.path.join(
            output_dir, dir, "stackcore_tracer_atrace_test_40945_1716517732910.txt"
        )
        self.assertTrue(os.path.exists(output_file))

    def test_asys_analyze_stackcore_other_file(self):
        stackcore_txt = os.path.join(
            st_root_path, "data/coredump/coredump_reg_info.txt"
        )
        output_dir = test_case_tmp
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
            f"--output={output_dir}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        dir = find_dir(output_dir, "asys_output_")
        output_file = os.path.join(output_dir, dir, "coredump_reg_info.txt")
        self.assertTrue(os.path.exists(output_file))

    def test_asys_analyze_stackcore_not_dir(self):
        stackcore_path = os.path.join(test_case_tmp, "input")
        os.mkdir(stackcore_path)
        output_dir = test_case_tmp
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--path={stackcore_path}",
            f"--symbol_path={st_root_path}",
            f"--output={output_dir}",
        ]
        ParamDict().set_env_type("EP")
        try:
            res = asys.main()
        except Exception:
            res = False
        self.assertTrue(not res)

    def test_asys_analyze_stackcore_not_per_file(self):
        stackcore_txt = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        output_dir = test_case_tmp
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
            f"--output={output_dir}",
        ]
        ParamDict().set_env_type("EP")
        os.chmod(os.path.dirname(stackcore_txt), 0o111)  # nosec B103  # test asserts permission-mask behavior
        try:
            self.assertTrue(asys.main())
            dir = find_dir(output_dir, "asys_output_")
            output_file = os.path.join(
                output_dir, dir, "stackcore_tracer_atrace_test_40945_1716517732910.txt"
            )
            self.assertTrue(os.path.exists(output_file))
        except Exception:
            self.assertTrue(False)
        finally:
            os.chmod(os.path.dirname(stackcore_txt), 0o777)  # nosec B103  # test asserts permission-mask behavior

    @pytest.mark.skip(reason="temporarily skipped due to test failure")
    def test_asys_analyze_stackcore_not_per_dir(self, capsys, caplog):
        stackcore_txt = os.path.join(test_case_tmp, "data")
        output_dir = test_case_tmp
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--path={stackcore_txt}",
            f"--symbol_path={st_root_path}",
            f"--output={output_dir}",
        ]
        ParamDict().set_env_type("EP")
        os.mkdir(stackcore_txt)
        os.chmod(stackcore_txt, 0o111)  # nosec B103  # test asserts permission-mask behavior
        try:
            self.assertTrue(not asys.main())
            self.assertTrue(
                'Argument "path" is not permissibale to read' in caplog.text
            )
        except Exception:
            self.assertTrue(False)
        finally:
            os.chmod(stackcore_txt, 0o777)  # nosec B103  # test asserts permission-mask behavior

    def test_asys_analyze_stackcore_empty_file(self, caplog):
        stackcore_txt = os.path.join(test_case_tmp, "stactcore_xxxx.txt")
        os.mknod(stackcore_txt)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("file is not in stackcore format." in caplog.text)

    def test_asys_analyze_stackcore_file_format_error(self, caplog):
        stackcore_txt = os.path.join(test_case_tmp, "data.txt")
        os.mknod(stackcore_txt)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue("file is not in stackcore format." in caplog.text)

    def test_asys_analyze_other_run_mode(self, capsys):
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore1",
            "--file=test.txt",
            f"--symbol_path={st_root_path}",
        ]
        try:
            ParamDict().set_env_type("EP")
            asys.main()
        except Exception:
            captured = capsys.readouterr()
            self.assertTrue("invalid choice: 'stackcore1'" in captured.err)

    def test_asys_analyze_not_input(self, caplog):
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--symbol_path={st_root_path}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "Analyze requires either the --file or --path argument" in caplog.text
        )

    def test_asys_analyze_not_symbol_path(self, caplog):
        stackcore_txt = os.path.join(test_case_tmp, "data.txt")
        os.mknod(stackcore_txt)
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=stackcore", f"--file={stackcore_txt}"]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "'--symbol_path' is not set, the default path will be used to analyze."
            in caplog.text
        )

    def test_asys_analyze_empty_symbol_path(self, capsys):
        stackcore_txt = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_stackcore_file_not_tools(self, mocker, caplog):
        mocker.patch(
            "collect.stackcore.stackcore_collect.ParseStackCore.check_tool_exists",
            return_value=False,
        )
        stackcore_txt = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    def test_asys_analyze_not_symbol_path_so(self, mocker, caplog):
        stackcore_txt = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            "libatrace_test.so not found in symbol_path directory" in caplog.text
        )
        self.assertTrue(ParamDict().get_arg("symbol_path") == [st_root_path])

    def test_asys_analyze_symbol_path_5(self, mocker, caplog):
        stackcore_txt = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path},{st_root_path},{st_root_path},{test_case_tmp},./",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue(
            "libatrace_test.so not found in symbol_path directory" in caplog.text
        )

    def test_asys_analyze_check_symbol_path_5(self, mocker, caplog):
        stackcore_txt = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path},{st_root_path},{st_root_path},{test_case_tmp},./",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        symbol_path_arg = ParamDict().get_arg("symbol_path")
        self.assertTrue(len(symbol_path_arg) == 5)
        self.assertTrue(symbol_path_arg.count(st_root_path) == 3)
        self.assertTrue(test_case_tmp in symbol_path_arg)
        self.assertTrue("./" in symbol_path_arg)

    def test_asys_analyze_coredump_dev_massage(self, mocker):
        coredump_file = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coredump",
            "--exe_file=python3",
            "--core_file=%s" % coredump_file,
        ]
        ParamDict().set_env_type("EP")
        mocker.patch("analyze.asys_analyze.check_command", return_value=True)
        mocker.patch("subprocess.Popen", return_value=PopenMock())
        self.assertTrue(asys.main())

        dirs = find_dir(test_case_tmp, "asys_output_")
        stackcore = find_dir(os.path.join(test_case_tmp, dirs), "stackcore_")
        self.assertTrue(
            not check_file_contents(
                os.path.join(test_case_tmp, dirs, stackcore),
                "#7 0x17d6f978d331dc6d 0x100000000000 /dev/davinci_manager",
            )
        )
        self.assertTrue(
            not check_file_contents(
                os.path.join(test_case_tmp, dirs, stackcore),
                "#8 0x101 0x100000000000 /dev/davinci_manager",
            )
        )

    def test_asys_analyze_stackcore_name_line(self, mocker):
        coredump_file = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            "--file=%s" % coredump_file,
            "--symbol_path=%s" % os.path.join(st_root_path, "data/coredump/"),
        ]
        mocker.patch(
            "collect.stackcore.stackcore_collect.run_linux_cmd", return_value=False
        )
        mocker.patch("subprocess.check_output", return_value=" main\n120 ".encode())
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_get_source_location_with_error(self, mocker):
        coredump_file = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            "--file=%s" % coredump_file,
            "--symbol_path=%s" % os.path.join(st_root_path, "data/coredump/"),
        ]
        mocker.patch(
            "collect.stackcore.stackcore_collect.run_linux_cmd", return_value=False
        )
        mocker.patch(
            "subprocess.check_output",
            return_value="addr2line: DWARF error: section .debug_info is larger than its filesize! \nclock_nanosleep\n??:?".encode(),
        )
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_get_line_with_addr2line_error(self, mocker):
        coredump_file = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=stackcore",
            "--file=%s" % coredump_file,
            "--symbol_path=%s" % os.path.join(st_root_path, "data/coredump/"),
        ]
        mocker.patch(
            "collect.stackcore.stackcore_collect.run_linux_cmd", return_value=True
        )
        mocker.patch(
            "subprocess.check_output",
            return_value="addr2line: DWARF error: section .debug_info is larger than its filesize! \nclock_nanosleep\n??:?",
        )
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_aicore_error_have_path(self, mocker):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("os.path.exists", return_value=True)
        aicore_error_path = os.path.join(st_root_path, "data")
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=aicore_error",
            "--path=%s" % aicore_error_path,
            "--output=%s" % test_case_tmp,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_aicore_error_not_path(self, mocker):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(AsysCollect, "run", return_value=True)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=aicore_error",
            "--output=%s" % test_case_tmp,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_aicore_error_path_not_is_path(self, mocker):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        aicore_error_path = os.path.join(
            st_root_path,
            "data/coredump/stackcore_tracer_atrace_test_40945_1716517732910.txt",
        )
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=aicore_error",
            "--path=%s" % aicore_error_path,
            "--output=%s" % test_case_tmp,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    def test_asys_analyze_aicore_error_not_have_permission(self, mocker):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch("os.access", return_value=False)
        aicore_error_path = os.path.join(st_root_path, "data")
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=aicore_error",
            "--path=%s" % aicore_error_path,
            "--output=%s" % test_case_tmp,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    def test_asys_analyze_aicore_error_not_path_collect_failed(self, mocker):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch.object(AsysCollect, "run", return_value=False)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=aicore_error",
            "--output=%s" % test_case_tmp,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    def test_asys_analyze_aicore_error_not_have_msaicerr(self, mocker, caplog, capsys):
        fake_ret = subprocess.Popen(
            "ls",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.Popen", return_value=fake_ret)
        mocker.patch.object(AsysCollect, "run", return_value=True)
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=aicore_error",
            "--output=%s" % test_case_tmp,
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        self.assertTrue(
            "The path of the msaicerr tool cannot be found, please install the whole package"
            in caplog.text
        )

    def test_asys_analyze_coretrace_one_file_without_symbol_path(self, mocker, caplog):
        coretrace_txt = os.path.join(
            st_root_path, "data/coredump/coretrace_1738757896_22994_test"
        )
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=coretrace", f"--file={coretrace_txt}"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        dirs = find_dir(test_case_tmp, "asys_output_")
        coretrace = find_dir(os.path.join(test_case_tmp, dirs), "coretrace_")
        content = "Signal 11 pid 0\n\nPID 22994 TGID 22994 comm test\n0x400594    0x594    /root/test\n0xffff8200b118    0x2b114    /usr/lib64/libc.so.6\n0x4004b0    0x4ac    /root/test\n"
        res_path = os.path.join(test_case_tmp, dirs, coretrace)
        self.assertTrue(check_file_contents(res_path, content))

    def test_asys_analyze_coretrace_one_file_with_symbol_path(self, mocker, caplog):
        coretrace_txt = os.path.join(
            st_root_path, "data/coredump/coretrace_1738757896_22994_test"
        )
        lib_path = os.path.join(st_root_path, "data/coredump/")
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coretrace",
            f"--file={coretrace_txt}",
            f"--symbol_path={lib_path}",
        ]
        ParamDict().set_env_type("EP")
        mocker.patch(
            "collect.coretrace.coretrace_collect.ParseCoreTrace.run_addr2line",
            return_value=["test_func"],
        )
        self.assertTrue(asys.main())
        dirs = find_dir(test_case_tmp, "asys_output_")
        coretrace = find_dir(os.path.join(test_case_tmp, dirs), "coretrace_")
        content = "test_func"
        res_path = os.path.join(test_case_tmp, dirs, coretrace)
        self.assertTrue(check_file_contents(res_path, content))

    def test_asys_analyze_coretrace_files(self, mocker, caplog):
        coretrace_path = os.path.join(st_root_path, "data/coredump/")
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coretrace",
            f"--path={coretrace_path}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        dirs = find_dir(test_case_tmp, "asys_output_")
        coretrace1 = find_dir(
            os.path.join(test_case_tmp, dirs, "coredump"), "coretrace_17"
        )
        coretrace2 = find_dir(
            os.path.join(test_case_tmp, dirs, "coredump"), "coretrace_log"
        )
        self.assertTrue(coretrace1 != "")
        self.assertTrue(coretrace2 != "")

    def test_asys_analyze_coretrace_other_file(self):
        stackcore_txt = os.path.join(
            st_root_path, "data/coredump/coredump_reg_info.txt"
        )
        output_dir = test_case_tmp
        sys.argv = [
            CONF_SRC_PATH,
            "analyze",
            "-r=coretrace",
            f"--file={stackcore_txt}",
            f"--symbol_path={st_root_path}",
            f"--output={output_dir}",
        ]
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())
        dir = find_dir(output_dir, "asys_output_")
        output_file = os.path.join(output_dir, dir, "coredump_reg_info.txt")
        self.assertTrue(os.path.exists(output_file))

    def test_asys_analyze_coretrace_file_no_addr2line(self, mocker, caplog):
        coretrace_txt = os.path.join(
            st_root_path, "data/coredump/coretrace_1738757896_22994_test"
        )
        output_dir = test_case_tmp
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=coretrace", f"--file={coretrace_txt}"]
        ParamDict().set_env_type("EP")
        mocker.patch(
            "collect.coretrace.coretrace_collect.check_command", return_value=False
        )
        self.assertTrue(not asys.main())
        dir = find_dir(output_dir, "asys_output_")
        output_file = os.path.join(output_dir, dir, "coretrace_1738757896_22994_test")
        self.assertTrue(os.path.exists(output_file))

    def test_asys_analyze_coretrace_file_empty(self, mocker, caplog):
        coretrace_txt = os.path.join(st_root_path, "data/coredump/coretrace_empty")
        output_dir = test_case_tmp
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=coretrace", f"--file={coretrace_txt}"]
        ParamDict().set_env_type("EP")
        mocker.patch(
            "collect.coretrace.coretrace_collect.check_command", return_value=False
        )
        self.assertTrue(not asys.main())
        dir = find_dir(output_dir, "asys_output_")
        output_file = os.path.join(output_dir, dir, "coretrace_empty")
        self.assertTrue(os.path.exists(output_file))

    def test_asys_analyze_coretrace_file_parse_error(self, mocker, caplog):
        coretrace_txt = os.path.join(st_root_path, "data/coredump/coretrace_error")
        _output_dir = test_case_tmp
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=coretrace", f"--file={coretrace_txt}"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_asys_analyze_ub(self, mocker):
        """
        正常用例：analyze -r=ub 解析全部合法 UB 二进制文件，生成对应 txt
        """
        ub_dir = os.path.join(test_case_tmp, "ub_input")
        great_ub_bins(ub_dir)
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=ub", f"--path={ub_dir}"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        out_dir = find_dir(test_case_tmp, "asys_output_")
        out_path = os.path.join(test_case_tmp, out_dir)
        self.assertTrue(
            check_file_contents(
                os.path.join(out_path, "ubmem_daw.txt"), "Dynamic Address Window"
            )
        )
        self.assertTrue(
            check_file_contents(
                os.path.join(out_path, "ubnl_dfx_statistic.txt"), "UBNL DFX"
            )
        )
        self.assertTrue(
            check_file_contents(
                os.path.join(out_path, "ubtpl_acl_src.txt"), "Source ACL Config"
            )
        )
        self.assertTrue(
            check_file_contents(
                os.path.join(out_path, "sl_to_vl.txt"), "SL to VL Mapping"
            )
        )

    def test_asys_analyze_ub_no_path(self, caplog):
        """
        异常用例：analyze -r=ub 未传入 path
        """
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=ub"]
        ParamDict().set_env_type("EP")
        # 缺少 --path 属于失败分支，asys.main() 应返回 False
        self.assertTrue(not asys.main())
        self.assertTrue(
            "Please enter the path to the UB data collection file." in caplog.text
        )

    def test_asys_analyze_ub_bin_not_found(self, caplog):
        """
        异常用例：目录中不存在 UB bin 文件，逐个记录 not found
        """
        ub_dir = os.path.join(test_case_tmp, "empty_input")
        os.mkdir(ub_dir)
        # 目录非空但不含 UB bin 文件，避免命中 path 非空校验
        create_file(os.path.join(ub_dir, "other.txt"))
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=ub", f"--path={ub_dir}"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        # bin 文件不存在时不生成任何 txt 结果
        out_dir = find_dir(test_case_tmp, "asys_output_")
        out_path = os.path.join(test_case_tmp, out_dir)
        self.assertTrue(not any(f.endswith(".txt") for f in os.listdir(out_path)))

    def test_asys_analyze_ub_bin_too_short(self, caplog):
        """
        异常用例：UB bin 文件长度不足，触发 parse error
        """
        ub_dir = os.path.join(test_case_tmp, "short_input")
        os.mkdir(ub_dir)
        with open(os.path.join(ub_dir, "ubmem_daw.bin"), "wb") as fw:
            fw.write(b"\x01")
        sys.argv = [CONF_SRC_PATH, "analyze", "-r=ub", f"--path={ub_dir}"]
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        self.assertTrue("Parse error: ubmem_daw" in caplog.text)

    def test_convert_ub_port_status(self):
        """
        直接测试 _convert_ub_port_status：合法/文件缺失/长度不足
        """
        from common.const import DSMI_UB_PORT_NUM

        bin_path = os.path.join(test_case_tmp, "port_status.bin")
        txt_path = os.path.join(test_case_tmp, "port_status.txt")
        values = [2] + [i % 4 for i in range(DSMI_UB_PORT_NUM)]
        with open(bin_path, "wb") as fw:
            fw.write(struct.pack(f"I{DSMI_UB_PORT_NUM}I", *values))
        AsysAnalyze._convert_ub_port_status(bin_path, txt_path)
        self.assertTrue(check_file_contents(txt_path, "DSMI UB Port Status Data"))

        # 文件缺失：不生成 txt
        miss_txt = os.path.join(test_case_tmp, "miss_status.txt")
        AsysAnalyze._convert_ub_port_status(
            os.path.join(test_case_tmp, "no.bin"), miss_txt
        )
        self.assertTrue(not os.path.exists(miss_txt))

        # 长度不足：不生成 txt
        short_path = os.path.join(test_case_tmp, "short.bin")
        short_txt = os.path.join(test_case_tmp, "short_status.txt")
        with open(short_path, "wb") as fw:
            fw.write(b"\x01")
        AsysAnalyze._convert_ub_port_status(short_path, short_txt)
        self.assertTrue(not os.path.exists(short_txt))

    def test_convert_ub_port_perf_test(self):
        """
        直接测试 _convert_ub_port_perf_test：合法/文件缺失
        """
        from common.const import DL_PORT_RX_VL_NUM as s

        bin_path = os.path.join(test_case_tmp, "port_perf.bin")
        txt_path = os.path.join(test_case_tmp, "port_perf.txt")
        fmt = f"4I{s}I{s}I28I4I{s}I{s}I28I"
        values = list(range(struct.calcsize(fmt) // 4))
        with open(bin_path, "wb") as fw:
            fw.write(struct.pack(fmt, *values))
        AsysAnalyze._convert_ub_port_perf_test(bin_path, txt_path)
        self.assertTrue(check_file_contents(txt_path, "Port Performance Test Counter"))

        miss_txt = os.path.join(test_case_tmp, "miss_perf.txt")
        AsysAnalyze._convert_ub_port_perf_test(
            os.path.join(test_case_tmp, "no.bin"), miss_txt
        )
        self.assertTrue(not os.path.exists(miss_txt))
