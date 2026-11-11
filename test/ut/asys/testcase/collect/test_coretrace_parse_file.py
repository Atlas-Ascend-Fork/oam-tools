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

import sys
from pathlib import Path


ASYS_SRC = Path(__file__).resolve().parents[5] / "src" / "asys"
sys.path.insert(0, str(ASYS_SRC))

from collect.coretrace import coretrace_collect  # noqa: E402


def setup_module():
    print("TestCoretraceParseFile ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestCoretraceParseFile ut test finish.")  # noqa: T201  # test diagnostic output


class TestCoretraceParseFile:
    def test_parse_file_with_invalid_utf8_bytes(self, monkeypatch, tmp_path):
        """
        A coretrace file can contain bytes that are not valid UTF-8. The
        analysis must not abort with a UnicodeDecodeError, otherwise the
        whole collection fails on a single unparsable byte.
        """
        parser = coretrace_collect.ParseCoreTrace(None)
        monkeypatch.setattr(parser, "check_tool_exists", lambda: True)

        coretrace_file = tmp_path / "coretrace_invalid_utf8.txt"
        # "Signal 11\n" followed by a byte that is not a valid UTF-8 sequence.
        coretrace_file.write_bytes(b"Signal 11\n\x80invalid\n")

        ret = parser.start_parse_file(str(coretrace_file))
        assert ret is True

    def test_parse_file_with_valid_utf8_content(self, monkeypatch, tmp_path):
        """
        A well formed coretrace file is still parsed as before.
        """
        parser = coretrace_collect.ParseCoreTrace(None)
        monkeypatch.setattr(parser, "check_tool_exists", lambda: True)

        coretrace_file = tmp_path / "coretrace_valid.txt"
        coretrace_file.write_text("Signal 11\n", encoding="utf-8")

        ret = parser.start_parse_file(str(coretrace_file))
        assert ret is True
