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

import configparser


from config import AsysConfigParser
from ..conftest import AssertTest


def setup_module():
    print("TestConfigParser ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestConfigParser ut test finish.")  # noqa: T201  # test diagnostic output


class TestConfigParser(AssertTest):
    def setup_method(self):
        self.parser = AsysConfigParser()
        self.ini_confs = configparser.ConfigParser()
        self.ini_confs["launch"] = {
            "graph": "TRUE",
            "ops": "TRUE",
        }
        self.dep_confs = {
            "g++": "g++ --version | grep g++",
            "gcc": "gcc --version | grep gcc",
        }

    def teardown_method(self):
        pass

    def test_parse_success(self, mocker):
        mocker.patch(
            "common.FileOperate.read_file", side_effect=(self.dep_confs, self.ini_confs)
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        mocker.patch("params.ParamDict.set_deps")
        mocker.patch("params.ParamDict.set_ini")
        self.assertTrue(self.parser.parse())

    def test_parse_deps_failed(self, mocker):
        mocker.patch(
            "common.FileOperate.read_file", side_effect=(False, self.ini_confs)
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        mocker.patch("params.ParamDict.set_deps")
        self.assertTrue(not self.parser.parse())

    def test_parse_ini_failed(self, mocker):
        mocker.patch(
            "common.FileOperate.read_file", side_effect=(self.dep_confs, False)
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        mocker.patch("params.ParamDict.set_deps")
        mocker.patch("params.ParamDict.set_ini")
        self.assertTrue(not self.parser.parse())

    def test_parse_deps_survives_a_broken_file(self, mocker, caplog):
        # parse() is a mandatory step of main(): a missing/corrupt
        # dependent_package.csv must turn into a clean READ_FILE_FAILED,
        # not an uncaught exception that kills every asys subcommand.
        mocker.patch(
            "common.FileOperate.read_file",
            side_effect=FileNotFoundError(2, "No such file or directory"),
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        mocker.patch("params.ParamDict.set_deps")
        self.assertTrue(not self.parser.parse())
        self.assertTrue("failed" in caplog.text)

    def test_parse_deps_survives_a_non_utf8_file(self, mocker):
        mocker.patch(
            "common.FileOperate.read_file",
            side_effect=UnicodeDecodeError(
                "utf-8", b"\xff", 0, 1, "invalid start byte"
            ),
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        mocker.patch("params.ParamDict.set_deps")
        self.assertTrue(not self.parser.parse())

    def test_parse_ini_survives_a_broken_file(self, mocker):
        mocker.patch(
            "common.FileOperate.read_file",
            side_effect=(self.dep_confs, PermissionError(13, "Permission denied")),
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        mocker.patch("params.ParamDict.set_deps")
        mocker.patch("params.ParamDict.set_ini")
        self.assertTrue(not self.parser.parse())

    def test_parse_ini_survives_a_missing_file(self, mocker):
        # ConfigParser.read() swallows a missing file and returns an empty
        # parser, so "no sections" used to look like a clean SUCCESS; the
        # existence check must turn it into READ_FILE_FAILED.
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch(
            "common.FileOperate.read_file", side_effect=(self.dep_confs, False)
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        mocker.patch("params.ParamDict.set_deps")
        mocker.patch("params.ParamDict.set_ini")
        self.assertTrue(not self.parser.parse())

    def test_parse_ini_survives_a_stray_percent_value(self, mocker, tmp_path):
        # items() interpolates values, so a single '%' in asys.ini raises
        # InterpolationSyntaxError at items() time (not during read());
        # the parse must convert it to READ_FILE_FAILED instead of an
        # uncaught exception killing every asys subcommand.
        ini_path = tmp_path / "asys.ini"
        ini_path.write_text("[launch]\nlog_level = %\n", encoding="utf-8")
        real_ini = configparser.ConfigParser()
        real_ini.read(str(ini_path), encoding="utf-8")
        parser = AsysConfigParser()
        parser.ini_file_path = str(ini_path)
        mocker.patch(
            "common.FileOperate.read_file", side_effect=(self.dep_confs, real_ini)
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        mocker.patch("params.ParamDict.set_deps")
        mocker.patch("params.ParamDict.set_ini")
        self.assertTrue(not parser.parse())

    def test_parse_deps_failure_logs_exactly_once(self, mocker, caplog):
        # A broken dependency file must produce one actionable log line with
        # the exception detail, not a second generic line right after it
        # (log rule #10: redundant logs).
        mocker.patch(
            "common.FileOperate.read_file",
            side_effect=FileNotFoundError(2, "No such file or directory"),
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        mocker.patch("params.ParamDict.set_deps")

        self.assertTrue(not self.parser.parse())

        failure_lines = [line for line in caplog.text.splitlines() if "failed" in line]
        self.assertTrue(len(failure_lines) == 1)
        self.assertTrue("No such file or directory" in failure_lines[0])
