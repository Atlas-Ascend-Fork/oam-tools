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

import pytest
from testcase.conftest import ut_root_path, great_bin, create_dir, check_atrace_file

from collect.trace import collect_trace, ParseTrace
from testcase.conftest import AssertTest


def setup_module():
    print("TestAtraceCollect ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestAtraceCollect ut test finish.")  # noqa: T201  # test diagnostic output


class TestAtraceCollect(AssertTest):
    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    @pytest.mark.parametrize(
        "directory, source_name, result_name",
        [
            ("logs", "trace.bin", "trace.txt"),
            ("logs.bin", "trace.bin", "trace.txt"),
            ("logs", "capture.bin.001.bin", "capture.bin.001.txt"),
        ],
    )
    def test_parse_preserves_path_before_suffix(
        self, tmp_path, directory, source_name, result_name
    ):
        trace_dir = tmp_path / directory
        trace_dir.mkdir()
        source = trace_dir / source_name
        result = trace_dir / result_name
        great_bin(str(source))

        self.assertTrue(ParseTrace().start_parse_file(str(source), count=1, num=1))

        self.assertTrue(check_atrace_file(str(result)))
        self.assertTrue(not source.exists())
        self.assertTrue(list(trace_dir.iterdir()) == [result])

    def test_atrace_collect_success(self, mocker):
        create_dir(os.path.join(ut_root_path, "data", "dfx", "atrace"))
        great_bin(os.path.join(ut_root_path, "data", "dfx", "atrace", "test.bin"))
        collect_trace(os.path.join(ut_root_path, "data"))
        self.assertTrue(
            check_atrace_file(
                os.path.join(ut_root_path, "data", "dfx", "atrace", "test.txt")
            )
        )

    def test_get_struct_data_failed(self, mocker):
        mocker.patch("struct.unpack", Exception("mock error"))
        parse_trace = ParseTrace()
        try:
            parse_trace.get_struct_data("test", 1, "s")
        except ValueError as e:
            self.assertTrue(
                "Unable to parse data, check whether the version matches or whether the file content is complete"
                in str(e)
            )
        else:
            self.assertTrue(False)

    def test_get_res_data_failed(self, mocker):
        data_file = os.path.join(
            ut_root_path,
            "data/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_2024.bin",
        )
        parse_trace = ParseTrace()
        with open(data_file, "rb") as fp:
            try:
                parse_trace.get_res_data(fp, 0.1)
            except ValueError as e:
                self.assertTrue(
                    "Unable to parse data, check whether the version matches or whether the file content is complete"
                    in str(e)
                )
            else:
                self.assertTrue(False)

    @pytest.mark.parametrize(
        "struct_data, log_data",
        [
            (
                [
                    [0x1, "3"],
                ],
                "check the version",
            ),
            ([[0xD928, "2"], ["0", "0", "0", "0"]], "check trace type"),
            (
                [[0xD928, "2"], ["0", "0", "0", 0], [10000, 10], [1], [2], [], []],
                "is incomplete and cannot be parsed",
            ),
            (
                [[0xD928, "2"], ["0", "0", "0", 0], [-100, 10000], [1], [2], [], []],
                "which may cause data loss",
            ),
        ],
    )
    def test_parse_ctrl_head_failed(self, struct_data, log_data, mocker, caplog):
        data_file = os.path.join(
            ut_root_path,
            "data/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_2024.bin",
        )
        parse_trace = ParseTrace(is_file=True)
        mocker.patch.object(parse_trace, "get_struct_data", side_effect=struct_data)
        with open(data_file, "rb") as fp:
            try:
                parse_trace.parse_ctrl_head(fp, data_file)
            except ValueError as e:
                self.assertTrue(f"{log_data}" in str(e))
            else:
                if "which may cause data loss" not in log_data:
                    self.assertTrue(False)

    def test_parse_msg_data_failed(self):
        data_file = os.path.join(
            ut_root_path,
            "data/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_2024.bin",
        )

        parse_trace = ParseTrace(is_file=True)
        with open(data_file, "rb") as fp:
            try:
                parse_trace.parse_msg_data(fp, ["item_name", 8, 0, 1], 2)
            except ValueError as e:
                self.assertTrue(
                    "The data type or data length is incorrect and cannot be parsed"
                    in str(e)
                )
            else:
                self.assertTrue(False)

    def test_parse_data_segment_failed(self, mocker):
        data_file = os.path.join(
            ut_root_path,
            "data/atrace/trace_17965_17965_20240302100542653636/stackcore_tracer_35_12345_2024.bin",
        )
        parse_trace = ParseTrace(is_file=True)
        mocker.patch.object(parse_trace, "parse_ctrl_head")
        mocker.patch.object(parse_trace, "parse_struct_segment", return_value=dict())
        with open(data_file, "rb") as fp:
            try:
                parse_trace.parse_data_segment(fp, data_file)
            except ValueError as e:
                self.assertTrue(
                    "Failed to parse the data, check whether the file is complete"
                    in str(e)
                )
            else:
                self.assertTrue(False)

    def test_parse_file_not_found(self, caplog):
        parse_trace = ParseTrace(is_file=True)
        parse_trace.parse("test.log")
        self.assertTrue("The test.log cannot be read or cannot be found" in caplog.text)
