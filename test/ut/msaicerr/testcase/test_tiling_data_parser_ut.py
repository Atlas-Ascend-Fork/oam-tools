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

import sys

from conftest import MSAICERR_PATH
from ms_interface.tiling_data_parser import TilingDataParser

sys.path.append(MSAICERR_PATH)

# private members are reached via getattr by name to keep the call sites free
# of direct protected-member access.
REVERSE = "_TilingDataParser__reverse_str"
GEN = "_TilingDataParser__gen_tiling_data"
GET_FILES = "_get_files"
GET_ARGS = "_TilingDataParser__get_args"


def test_reverse_str():
    # 8-byte little-endian reversal of a 16-hex-char string
    reverse = getattr(TilingDataParser, REVERSE)
    assert reverse("0102030405060708") == "0807060504030201"


def test_gen_tiling_data():
    parser = TilingDataParser("/p")
    data = getattr(parser, GEN)(["0x1", "0x2"], 0)
    assert isinstance(data, bytes)
    assert len(data) == 16


def test_get_files(mocker):
    parser = TilingDataParser("/p")
    mocker.patch("os.walk", return_value=[("/p", [], ["a.log", "b.log"])])
    files = getattr(parser, GET_FILES)()
    assert "/p/a.log" in files
    assert "/p/b.log" in files


def test_get_args_no_result(mocker):
    mocker.patch("ms_interface.utils.get_inquire_result", return_value=[])
    result = getattr(TilingDataParser, GET_ARGS)("/p")
    assert result == ([], -1)


def test_parse_offset_minus_one(mocker):
    mocker.patch.object(TilingDataParser, GET_ARGS, return_value=(["0x1"], -1))
    parser = TilingDataParser("/p")
    assert parser.parse() == b""


def test_parse_success(mocker):
    mocker.patch.object(TilingDataParser, GET_ARGS, return_value=(["0x1", "0x2"], 0))
    parser = TilingDataParser("/p")
    result = parser.parse()
    assert isinstance(result, bytes)
