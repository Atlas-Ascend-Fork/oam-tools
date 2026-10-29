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

from ms_interface.single_op_test_frame.common import dtype_trans
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelParam


def test_every_declared_dtype_has_a_byte_width():
    expected = {
        "bool": 1,
        "int8": 1,
        "uint8": 1,
        "int16": 2,
        "uint16": 2,
        "int32": 4,
        "uint32": 4,
        "int64": 8,
        "uint64": 8,
        "float16": 2,
        "bfloat16": 2,
        "float32": 4,
        "float64": 8,
    }
    assert {
        name: dtype_trans.get_dtype_byte(name)
        for name in dtype_trans.get_all_str_dtypes()
    } == expected


def test_bfloat16_byte_width():
    assert dtype_trans.get_dtype_byte("bfloat16") == 2


def test_unknown_dtype_has_clear_parameter_error():
    with pytest.raises(ValueError, match="unsupported dtype: bfloat116"):
        AscendOpKernelParam(shape=[2, 3], dtype="bfloat116")


@pytest.mark.parametrize("shape,expected", [([2, 3], 12), ([1], 2), ([0, 3], 0)])
def test_bfloat16_shape_only_parameter_size(shape, expected):
    parameter = AscendOpKernelParam(shape=shape, dtype="bfloat16")
    assert parameter.size == expected
    assert parameter.dtype == "bfloat16"


@pytest.mark.parametrize(
    "dtype,width", [("float16", 2), ("float32", 4), ("bool", 1), ("int64", 8)]
)
def test_existing_widths_are_preserved(dtype, width):
    assert AscendOpKernelParam(shape=[2, 3], dtype=dtype).size == 6 * width
