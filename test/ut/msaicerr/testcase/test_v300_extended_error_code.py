#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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

"""Parse actual plog files through the production grep command and parser."""

import pytest
from ms_interface.aicore_error_parser import AicoreErrorParser
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.constant import Constant


def parse_code(tmp_path, words):
    plog = tmp_path / "collection" / "plog"
    plog.mkdir(parents=True)
    (plog / "runtime.log").write_text(
        "The extend info: errcode: (" + ",".join(words) + ")\n",
        encoding="utf-8",
    )
    return int(AicoreErrorParser(str(tmp_path))._get_v300_error_code(), 16)


@pytest.mark.parametrize("digit", ["f", "F"])
@pytest.mark.parametrize("word", [0, 1])
def test_full_hex_alphabet(tmp_path, word, digit):
    words = ["0x0", "0x0", "0x0"]
    words[word] = "0x" + digit
    assert parse_code(tmp_path, words) == 15 << (word * 64)


@pytest.mark.parametrize(
    ("third", "expected"),
    [
        ("0x1", 1 << 128),
        ("0x100000000", 1 << 145),
        ("0x100000001", (1 << 128) | (1 << 145)),
    ],
)
def test_third_word_fields_are_combined(tmp_path, third, expected):
    assert parse_code(tmp_path, ["0x0", "0x0", third]) == expected


def test_normal_lower_two_words(tmp_path):
    assert parse_code(tmp_path, ["0x12", "0x34", "0x0"]) == 0x12 | (0x34 << 64)


def test_zero_code(tmp_path):
    assert parse_code(tmp_path, ["0x0", "0x0", "0x0"]) == 0


def test_unrelated_log_preserves_zero_fallback(tmp_path):
    plog = tmp_path / "collection" / "plog"
    plog.mkdir(parents=True)
    (plog / "runtime.log").write_text("unrelated runtime message\n", encoding="utf-8")
    assert AicoreErrorParser(str(tmp_path))._get_v300_error_code() == "0x0"


@pytest.mark.parametrize("low", ["0x0", "0x1"])
def test_unregistered_stars_bit_remains_reportable(tmp_path, low):
    code = parse_code(tmp_path, [low, "0x0", "0x8000000000000000"])
    assert code & (1 << 176)
    info = AicErrorInfo()
    info.aic_error_info["error_code"] = hex(code)
    report = info._get_aicerror_info()
    assert "unknown error bit 176" in report
    if low == "0x1":
        assert Constant.AIC_ERROR_INFO_DICT[0] in report


@pytest.mark.parametrize("low", ["0x0", "0x1"])
def test_unregistered_stars_bit_does_not_break_extra_pc(tmp_path, low):
    code = parse_code(tmp_path, [low, "0x0", "0x8000000000000000"])
    info = AicErrorInfo()
    info.aic_error_info["error_code"] = hex(code)
    info.extra_info = Constant.BIU_KEY + "=0xab"
    assert info.find_extra_pc() == ("10101011" if low == "0x1" else "")
