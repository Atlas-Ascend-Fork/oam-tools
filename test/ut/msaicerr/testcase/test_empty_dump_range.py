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

import numpy as np
import pytest
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.dump_data_parser import ConstManager, DumpDataParser


@pytest.mark.parametrize(
    "dtype",
    ["float16", "float32", "float64", "int16", "uint64", "int8", "uint8", "bool"],
)
def test_empty_tensor_does_not_have_invalid_values(dtype):
    assert (
        DumpDataParser._check_tensor_data("input", 0, np.array([], dtype=dtype), dtype)
        == ""
    )


def test_empty_tensor_keeps_invalid_dtype_error():
    assert "Can not read with dtype unknown" in DumpDataParser._check_tensor_data(
        "input", 0, np.array([]), "unknown"
    )


def test_empty_bfloat_tensor_after_dtype_validation(mocker):
    mocker.patch.object(
        DumpDataParser, "_to_numpy_dtype", return_value=np.dtype("float32")
    )
    assert (
        DumpDataParser._check_tensor_data(
            "input", 0, np.array([], dtype=np.float32), "bfloat16"
        )
        == ""
    )


def test_empty_dump_item_is_saved_and_summarized(tmp_path):
    info = AicErrorInfo()
    info.kernel_name = "EmptyOp"
    parser = DumpDataParser(str(tmp_path), info)
    float_enum = next(
        key
        for key, value in ConstManager.DATA_TYPE_TO_DTYPE_MAP.items()
        if value == "float32"
    )
    result = parser._parse_one_item(
        {"data": b"", "data_type": float_enum, "shape": {"dim": [0]}, "size": 0},
        "input",
        {},
        0,
        str(tmp_path),
    )
    assert "Max: N/A" in result
    assert parser.bin_data_list
    assert np.load(parser.bin_data_list[0]).size == 0
