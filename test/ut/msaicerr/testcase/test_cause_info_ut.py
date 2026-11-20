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
"""根因信息（cause_info）：检测收集、info.txt渲染与info.json输出测试。"""

import json
import os

from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.aicore_error_parser import AicoreErrorParser
from ms_interface.constant import RegexPattern
from ms_interface import json_report_builder as jrb
from ms_interface.utils import regexp_match_dict


HINT = (
    "GatherV2 failed to access the host memory through PCIe. You can enable "
    "the environment variable OP_PCIE_THROUGH_ACCESS_HOST_MEM_CHECK_ENABLE "
    "to enable the address check for the PCIe through feature."
)
OTHER_HINT = "OtherOp " + HINT[len("GatherV2 ") :]


def _hint_line(tid, hint):
    return (
        f"[ERROR] IDEDD({tid},python3):2026-11-05-15:33:29.760.012 "
        f"[dump_file.cpp:640][tid:{tid}] [Dump][Exception] " + hint
    )


def test_get_pcie_through_hint_matches_main_thread(monkeypatch):
    parser = AicoreErrorParser("/collect")
    # plog混入其他线程的提示语：只取与主记录thread_id一致的那条
    monkeypatch.setattr(
        "ms_interface.aicore_error_parser.utils.get_inquire_result",
        lambda *_args, **_kwargs: [
            {"thread_id": "2", "hint": OTHER_HINT},
            {"thread_id": "1534205", "hint": HINT},
        ],
    )
    ret = parser._get_pcie_through_hint("/plog", "1534205")
    assert ret == HINT


def test_get_pcie_through_hint_first_of_same_thread(monkeypatch):
    parser = AicoreErrorParser("/collect")
    monkeypatch.setattr(
        "ms_interface.aicore_error_parser.utils.get_inquire_result",
        lambda *_args, **_kwargs: [
            {"thread_id": "1534205", "hint": HINT},
            {"thread_id": "1534205", "hint": HINT},
        ],
    )
    assert parser._get_pcie_through_hint("/plog", "1534205") == HINT


def test_get_pcie_through_hint_no_match(monkeypatch):
    parser = AicoreErrorParser("/collect")
    # 全部失配（其他线程/其他进程）：返回空串不追加，宁漏勿错配，并 warn
    warns = []
    monkeypatch.setattr(
        "ms_interface.aicore_error_parser.utils.print_warn_log", warns.append
    )
    monkeypatch.setattr(
        "ms_interface.aicore_error_parser.utils.get_inquire_result",
        lambda *_args, **_kwargs: [
            {"thread_id": "999", "hint": OTHER_HINT},
        ],
    )
    assert parser._get_pcie_through_hint("/plog", "1534205") == ""
    assert len(warns) == 1
    assert "1534205" in warns[0] and "1 pcie through hint(s)" in warns[0]


def test_collect_cause_info_gathers_each_category(monkeypatch):
    parser = AicoreErrorParser("/collect")
    monkeypatch.setattr(
        AicoreErrorParser,
        "_get_pcie_through_hint",
        lambda _self, _plog_path, _thread_id: HINT,
    )
    assert parser._collect_cause_info("/plog", "1534205") == [HINT]


def test_collect_cause_info_empty_when_no_match(monkeypatch):
    parser = AicoreErrorParser("/collect")
    monkeypatch.setattr(
        AicoreErrorParser,
        "_get_pcie_through_hint",
        lambda _self, _plog_path, _thread_id: "",
    )
    assert parser._collect_cause_info("/plog", "1534205") == []


def test_set_info_fills_cause_info(monkeypatch):
    parser = AicoreErrorParser("/collect")
    monkeypatch.setattr(
        AicoreErrorParser,
        "_get_pcie_through_hint",
        lambda _self, _plog_path, thread_id: HINT if thread_id == "1534205" else "",
    )
    record = {
        "error_code": "0x200000000",
        "core_id": "1",
        "thread_id": "1534205",
        "extra_info": "",
    }
    info = parser.set_info(record, "/plog", "exception_info.1.0", 1)
    assert info.cause_info == [HINT]


def test_pcie_through_hint_regex_captures_tid_and_text():
    ret = regexp_match_dict(
        RegexPattern.ADUMP_PCIE_THROUGH, _hint_line("1534205", HINT)
    )
    assert ret[0]["thread_id"] == "1534205"
    assert ret[0]["hint"] == HINT


def test_pcie_through_hint_regex_excludes_prefix_and_next_match():
    # 走生产同款路径 regexp_match_dict（match_dict=True 分支，re.compile
    # 不带 flag）：hint 组只取 [Dump][Exception] 之后且不越过行尾的内容，
    # 时间戳/文件名前缀与第二条命中行都不混入。
    data = (
        "plog/host.log:10:" + _hint_line("1", HINT) + "\n"
        "plog/host.log:25:" + _hint_line("2", OTHER_HINT) + "\n"
    )
    ret = regexp_match_dict(RegexPattern.ADUMP_PCIE_THROUGH, data)
    assert [(r["thread_id"], r["hint"]) for r in ret] == [
        ("1", HINT),
        ("2", OTHER_HINT),
    ]


def test_pcie_through_hint_regex_no_cross_line_tid():
    data = (
        "plog/host.log:5:[ERROR] IDEDD(111,python3):2026-11-19-10:00:00.000.000 "
        "[dump_args.cpp:807][tid:111] [Dump][Exception] dump exception to file, "
        "file: ./x/exception_info.1.0.123\n"
        "plog/host.log:10:" + _hint_line("222", HINT) + "\n"
    )
    ret = regexp_match_dict(RegexPattern.ADUMP_PCIE_THROUGH, data)
    assert [(r["thread_id"], r["hint"]) for r in ret] == [("222", HINT)]


def _make_report_info(cause_info=None):
    info = AicErrorInfo()
    info.aic_error_info = {
        "error_code": "0x200000000",
        "core_id": "1",
        "extra_info": "MTE_ERR_INFO=0x1",
    }
    info.extra_info = "MTE_ERR_INFO=0x1"
    info.aic_error_groups = [
        ("0x200000000", {"records": [dict(info.aic_error_info)], "cores_aic": ["1"]}),
        ("0x200000001", {"records": [dict(info.aic_error_info)], "cores_aic": ["1"]}),
    ]
    info.cause_info = [HINT] if cause_info is None else cause_info
    return info


def test_analyse_appends_cause_info_once_after_dfx():
    info = _make_report_info()
    report = info.analyse()
    section = report.split("***********************3.")[0]
    assert section.count(HINT) == 1
    assert "cause info" in section
    assert section.rstrip().endswith(HINT)


def test_analyse_multiple_cause_info_lines():
    info = _make_report_info(cause_info=[HINT, "Another root cause hint."])
    report = info.analyse()
    section = report.split("***********************3.")[0]
    assert section.count("cause info") == 2
    assert HINT in section and "Another root cause hint." in section


def test_analyse_without_cause_info_keeps_section():
    info = _make_report_info(cause_info=[])
    report = info.analyse()
    assert HINT not in report
    assert "cause info" not in report


def test_json_report_cause_info_semantics(tmp_path):
    info = _make_report_info(cause_info=[])
    report = jrb.build_report(info, str(tmp_path))
    assert report["aic_error"]["cause_info"] == []

    info.cause_info = [HINT]
    report = jrb.build_report(info, str(tmp_path))
    assert report["aic_error"]["cause_info"] == [HINT]


def test_write_json_report_cause_info_field(tmp_path):
    info = _make_report_info()
    jrb.write_json_report(str(tmp_path), info, str(tmp_path))
    with open(os.path.join(tmp_path, "info.json"), encoding="utf-8") as file:
        report = json.load(file)
    assert report["aic_error"]["cause_info"] == [HINT]
