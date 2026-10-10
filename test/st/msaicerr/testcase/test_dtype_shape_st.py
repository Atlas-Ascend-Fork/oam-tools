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

sys.path.append(MSAICERR_PATH)
from ms_interface.single_op_test_frame.common import dtype_trans
from ms_interface.single_op_test_frame.utils import shape_utils


def test_get_all_str_dtypes_covers_common_types():
    dtypes = list(dtype_trans.get_all_str_dtypes())
    assert "float16" in dtypes
    assert "int32" in dtypes


def test_str_to_np_dtype_maps_known_str():
    assert dtype_trans.str_to_np_dtype("float32") is np.float32


def test_str_to_np_dtype_passes_through_non_str():
    # 非 str 入参原样返回（提前返回分支）
    assert dtype_trans.str_to_np_dtype(np.float16) is np.float16


def test_str_to_np_dtype_unknown_str_returns_none():
    assert dtype_trans.str_to_np_dtype("no_such_dtype") is None


def test_np_dtype_to_str_passes_through_str():
    # str 入参原样返回（提前返回分支）
    assert dtype_trans.np_dtype_to_str("float16") == "float16"


def test_np_dtype_to_str_maps_np_dtype():
    assert dtype_trans.np_dtype_to_str(np.dtype(np.int32)) == "int32"


def test_get_dtype_byte_known_dtype():
    assert dtype_trans.get_dtype_byte("float16") == 2
    assert dtype_trans.get_dtype_byte("int8") == 1


def test_calc_shape_size_normal():
    assert shape_utils.calc_shape_size((2, 3, 4)) == 24


def test_calc_shape_size_scalar_missing_and_zero_axis():
    assert shape_utils.calc_shape_size(()) == 1
    assert shape_utils.calc_shape_size([]) == 1
    assert shape_utils.calc_shape_size(None) == 0
    assert shape_utils.calc_shape_size((0, 3)) == 0


def test_calc_shape_size_all_negative_dims_returns_zero():
    # 动态 shape 的 -1 被过滤后无剩余维度，返回 0
    assert shape_utils.calc_shape_size((-1, -1)) == 0


def test_calc_shape_size_ignores_negative_dims():
    assert shape_utils.calc_shape_size((2, -1, 3)) == 6


def test_calc_op_param_size_normal():
    assert shape_utils.calc_op_param_size(24, "float16") == 48


def test_calc_op_param_size_rejects_invalid_dtype():
    with pytest.raises(TypeError):
        shape_utils.calc_op_param_size(24, 12345)
