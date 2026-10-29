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

import collect.stackcore.stackcore_collect as stackcore
import collect.trace.trace_collect as trace
from collect.stackcore import ParseStackCore
from collect.trace import ParseTrace
from testcase.conftest import AssertTest


class TestProgressNumerator(AssertTest):
    """A skipped file must not advance the progress numerator.

    The numerator feeds out_progress_bar(count, num). Counting a file that
    the same run skips makes the bar report more than 100% (2 .bin plus 3
    other artefacts reported 200%) and, in the other direction, drops the
    parsed files to a fraction of the denominator.
    """

    def test_stackcore_numerator_ignores_the_files_it_skips(self, tmp_path, mocker):
        # stackcore parses .txt only, so a .log sitting next to them must not
        # advance the numerator.
        for name in ("core_a.txt", "core_b.txt", "notes.log"):
            (tmp_path / name).write_text("", encoding="utf-8")

        instance = object.__new__(ParseStackCore)
        instance.symbol_path = None
        mocker.patch.object(ParseStackCore, "check_tool_exists", return_value=True)
        mocker.patch.object(ParseStackCore, "start_parse_file", return_value=True)
        seen = []
        mocker.patch.object(
            stackcore, "out_progress_bar", side_effect=lambda _c, n=0: seen.append(n)
        )

        assert instance.run(str(tmp_path), count=2) is True
        assert max(seen) == 2, seen

    def test_trace_numerator_ignores_the_files_it_skips(self, tmp_path, mocker):
        # trace parses .bin only, so the .txt artefact must not advance the
        # numerator. The progress bar is written inside start_parse_file, so
        # only the parsing itself is stubbed out here.
        for name in ("atrace_0.bin", "atrace_1.bin", "notes.txt"):
            (tmp_path / name).write_text("", encoding="utf-8")

        instance = object.__new__(ParseTrace)
        instance.is_file = True
        mocker.patch.object(ParseTrace, "parse", return_value="")
        seen = []
        mocker.patch.object(
            trace, "out_progress_bar", side_effect=lambda _c, n=0: seen.append(n)
        )

        assert instance.run(str(tmp_path), count=2) is True
        assert max(seen) == 2, seen
