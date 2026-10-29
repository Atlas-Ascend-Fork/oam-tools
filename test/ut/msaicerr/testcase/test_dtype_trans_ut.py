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

import numpy as np
import pytest

from conftest import MSAICERR_PATH
from ms_interface.single_op_test_frame.common import dtype_trans

sys.path.append(MSAICERR_PATH)


def test_get_all_str_dtypes():
    dtypes = dtype_trans.get_all_str_dtypes()
    assert "float16" in dtypes
    assert "int64" in dtypes
    assert "bfloat16" in dtypes


def test_str_to_np_dtype_with_str():
    assert dtype_trans.str_to_np_dtype("float32") is np.float32
    assert dtype_trans.str_to_np_dtype("int8") is np.int8


def test_str_to_np_dtype_with_unknown_str():
    assert dtype_trans.str_to_np_dtype("not_a_dtype") is None


def test_str_to_np_dtype_with_non_str():
    # non-str input is returned as-is
    assert dtype_trans.str_to_np_dtype(np.float16) is np.float16


def test_np_dtype_to_str_with_str():
    assert dtype_trans.np_dtype_to_str("float16") == "float16"


@pytest.mark.parametrize(
    "np_type, expected",
    [
        (np.float16, "float16"),
        (np.float32, "float32"),
        (np.float64, "float64"),
        (np.int8, "int8"),
        (np.uint8, "uint8"),
        (np.int16, "int16"),
        (np.uint16, "uint16"),
        (np.int32, "int32"),
        (np.uint32, "uint32"),
        (np.int64, "int64"),
        (np.uint64, "uint64"),
    ],
)
def test_np_dtype_to_str_with_np_dtype(np_type, expected):
    assert dtype_trans.np_dtype_to_str(np.dtype(np_type)) == expected


@pytest.mark.parametrize(
    "dtype, size",
    [
        ("bool", 1),
        ("int8", 1),
        ("uint8", 1),
        ("int16", 2),
        ("uint16", 2),
        ("int32", 4),
        ("uint32", 4),
        ("int64", 8),
        ("uint64", 8),
        ("float16", 2),
        ("float32", 4),
        ("float64", 8),
    ],
)
def test_get_dtype_byte(dtype, size):
    assert dtype_trans.get_dtype_byte(dtype) == size


def test_get_dtype_byte_unknown():
    with pytest.raises(ValueError, match="unsupported dtype: not_a_dtype"):
        dtype_trans.get_dtype_byte("not_a_dtype")
