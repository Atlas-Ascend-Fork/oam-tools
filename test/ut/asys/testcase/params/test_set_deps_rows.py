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

from common.file_operate import FileOperate
from params import ParamDict
from params import param_dict
from testcase.conftest import AssertTest


def _blank_param_dict():
    obj = object.__new__(ParamDict)
    obj._ParamDict__deps = {}
    return obj


class TestDependencyRows(AssertTest):
    def test_set_deps_skips_unusable_rows(self):
        # main() parses dependent_package.csv through this before any command
        # runs, so an empty row aborted the whole invocation here.
        obj = _blank_param_dict()
        obj.set_deps(
            [["pkg", "cmd"], [], ["only-a-name"], ["# note", "cmd"], ["  ", "cmd"]]
        )
        assert list(obj._ParamDict__deps) == ["pkg"]

    def test_set_deps_warns_about_every_skipped_row(self, mocker):
        # A missing comma silently removes a package from the report, so the
        # skipped row has to be named in the log; without this the warning
        # could be dropped and no case would notice.
        warnings = []
        mocker.patch.object(
            param_dict,
            "log_warning",
            side_effect=lambda msg: warnings.append(str(msg)),
        )

        obj = _blank_param_dict()
        obj.set_deps([["pkg", "cmd"], [], ["only-a-name"]])

        assert len(warnings) == 2, warnings
        assert any("only-a-name" in msg for msg in warnings), warnings
        assert all("dependent_package.csv" in msg for msg in warnings), warnings

    def test_set_deps_delegates_to_the_shared_predicate(self, mocker):
        # The shared predicate is the point of this change: if set_deps ever
        # gets its own inlined copy, the two readers of dependent_package.csv
        # drift apart and every other case here still passes. Patching the
        # shared rule to reject the row is the only way to notice that.
        mocker.patch.object(FileOperate, "is_dep_row", return_value=False)

        obj = _blank_param_dict()
        obj.set_deps([["pkg", "cmd"]])

        assert obj._ParamDict__deps == {}

    def test_is_dep_row_matches_the_same_rule(self):
        assert FileOperate.is_dep_row(["pkg", "cmd"]) is True
        assert FileOperate.is_dep_row([]) is False
        assert FileOperate.is_dep_row(["only-a-name"]) is False
        assert FileOperate.is_dep_row(["# note", "cmd"]) is False
        # csv.reader keeps the leading spaces, so the comment rule has to strip
        # them first; this row used to be registered as a package and executed.
        assert FileOperate.is_dep_row(["  # note", "cmd"]) is False
        assert FileOperate.is_dep_row(["  ", "cmd"]) is False
        # Shape guard: csv.reader always hands back a list, so pin the other
        # shapes here or the isinstance branch has no coverage at all.
        assert FileOperate.is_dep_row(None) is False
        assert FileOperate.is_dep_row("pkg,cmd") is False
