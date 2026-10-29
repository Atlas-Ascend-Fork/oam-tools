#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
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

import sys

from testcase.conftest import ASYS_SRC_PATH

sys.path.insert(0, ASYS_SRC_PATH)

from collect.trace.trace_collect import (
    TRACE_STRUCT_SHOW_MODE_BIN,
    TRACE_STRUCT_SHOW_MODE_HEX,
    trace_show_mode,
)

from testcase.conftest import AssertTest
from view.table import display_width, generate_report


class TestTableWidth(AssertTest):
    def test_chinese_cell_keeps_every_line_the_same_display_width(self):
        # Column widths used to be counted in characters, so a CJK cell made
        # its own row wider on screen and broke the right border.
        report = generate_report(
            [["Device", "Value"]],
            {"none": [["设备名称", "ok"], ["dev-0", "ok"]]},
            split_line=True,
        )
        widths = {display_width(line) for line in report.splitlines() if line.strip()}
        assert len(widths) == 1, sorted(widths)

    def test_ascii_table_is_unchanged(self):
        report = generate_report([["A", "B"]], {"none": [["1", "2"]]})
        widths = {display_width(line) for line in report.splitlines() if line.strip()}
        assert len(widths) == 1, sorted(widths)

    def test_display_width_counts_wide_glyphs_twice(self):
        # The production helper is the one under test here; a copy inside
        # this file would stay green even if view.table went back to len().
        assert display_width("ab") == 2
        assert display_width("中文") == 4


class TestTraceShowMode(AssertTest):
    def test_binary_and_hex_still_convert_numbers(self):
        assert trace_show_mode(TRACE_STRUCT_SHOW_MODE_BIN, 12) == "0b1100"
        assert trace_show_mode(TRACE_STRUCT_SHOW_MODE_HEX, 12) == "0xc"

    def test_non_numeric_value_falls_back_to_text(self):
        # The mode byte comes from the file, so a broken trace used to abort
        # the whole parse with ValueError here.
        assert trace_show_mode(TRACE_STRUCT_SHOW_MODE_BIN, "abc") == "abc"
        assert trace_show_mode(TRACE_STRUCT_SHOW_MODE_HEX, "") == ""
