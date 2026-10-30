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

import pytest

from info import asys_info
from testcase.conftest import AssertTest

DEP_KEY = " Dependent Packet "


class TestDependentPackageRows(AssertTest):
    @pytest.fixture(autouse=True)
    def _isolate(self, mocker):
        # The table is built from the shipped conf file and a live command
        # probe; both are replaced so the case only exercises the row handling.
        self.commands = []
        mocker.patch.object(
            asys_info,
            "run_command",
            side_effect=lambda cmd: self.commands.append(cmd) or "1.0.0",
        )

    def _build(self, mocker, rows):
        mocker.patch.object(asys_info.f, "read_file", return_value=rows)
        table = {}
        asys_info.AsysInfo._AsysInfo__software_set_dep(table)
        return table

    def test_blank_line_does_not_drop_the_whole_section(self, mocker):
        # A trailing newline in dependent_package.csv makes csv.reader emit an
        # empty row; reading item[1] there raised IndexError.
        table = self._build(mocker, [["pkg", "cmd"], []])
        assert table.get(DEP_KEY) == [["pkg", "1.0.0"]]

    def test_skipped_row_is_named_in_the_log(self, mocker):
        # A package that disappears from the report leaves no trace, so the
        # skipped row has to be named in the log; without this the warning
        # could be dropped and no case would notice.
        warnings = []
        mocker.patch.object(
            asys_info,
            "log_warning",
            side_effect=lambda msg: warnings.append(str(msg)),
        )

        table = self._build(mocker, [["pkg", "cmd"], ["only-name"]])

        assert table.get(DEP_KEY) == [["pkg", "1.0.0"]]
        assert len(warnings) == 1, warnings
        assert "only-name" in warnings[0], warnings

    def test_single_column_row_is_skipped(self, mocker):
        table = self._build(mocker, [["pkg", "cmd"], ["only-name"]])
        assert table.get(DEP_KEY) == [["pkg", "1.0.0"]]

    def test_two_column_comment_row_is_skipped(self, mocker):
        # The real shape a comment takes: a comment text plus a command column.
        # Before the guard this row ran the command and wrote "# note" into the
        # report, so the case pins both the table and the executed commands.
        table = self._build(mocker, [["# note", "cmd"], ["pkg", "cmd"]])
        assert table.get(DEP_KEY) == [["pkg", "1.0.0"]]
        assert self.commands == ["cmd"]

    def test_blank_name_row_is_skipped(self, mocker):
        table = self._build(mocker, [["  ", "cmd"], ["pkg", "cmd"]])
        assert table.get(DEP_KEY) == [["pkg", "1.0.0"]]

    def test_rows_keep_their_order(self, mocker):
        table = self._build(mocker, [["a", "cmd-a"], [], ["b", "cmd-b"]])
        assert table.get(DEP_KEY) == [["a", "1.0.0"], ["b", "1.0.0"]]
        assert self.commands == ["cmd-a", "cmd-b"]
