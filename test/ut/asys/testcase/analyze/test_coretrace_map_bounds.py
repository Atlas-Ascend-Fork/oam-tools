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

from collect.coretrace.coretrace_collect import ParseCoreTrace, ParseData


def test_coretrace_resolves_adjusted_addresses_in_half_open_map(monkeypatch):
    parser = ParseCoreTrace([])
    calls = []

    def run_addr2line(command):
        calls.append(command)
        return ["resolved_symbol\n"]

    monkeypatch.setattr(parser, "run_addr2line", run_addr2line)
    monkeypatch.setattr(parser, "warn_missing", lambda _path: None)
    data = ParseData()

    parser.parse_line("00400000-00401000 /bin/example", data)
    below_start = parser.parse_line("#1 00400001", data)
    assert below_start == ""
    assert calls == []

    at_start = parser.parse_line("#0 00400000", data)
    at_end_return_address = parser.parse_line("#1 00401000", data)
    interior = parser.parse_line("#0 00400010", data)
    at_exclusive_end = parser.parse_line("#0 00401000", data)

    assert "0x400000" in at_start
    assert "0x401000" in at_end_return_address
    assert "0x400010" in interior
    assert at_exclusive_end == ""
    assert [command[-1] for command in calls] == ["0x0", "0xffc", "0x10"]


def test_coretrace_does_not_symbolize_gaps_between_maps_with_same_binary(monkeypatch):
    parser = ParseCoreTrace([])
    calls = []

    def run_addr2line(command):
        calls.append(command)
        return ["resolved_symbol\n"]

    monkeypatch.setattr(parser, "run_addr2line", run_addr2line)
    monkeypatch.setattr(parser, "warn_missing", lambda _path: None)
    data = ParseData()

    parser.parse_line("00400000-00401000 /root/test", data)
    parser.parse_line("0041f000-00420000 /root/test", data)
    parser.parse_line("00420000-00421000 /root/test", data)

    in_gap = parser.parse_line("#0 00410000", data)
    in_mapping = parser.parse_line("#0 00420000", data)

    assert in_gap == ""
    assert "0x420000" in in_mapping
    assert [command[-1] for command in calls] == ["0x20000"]
