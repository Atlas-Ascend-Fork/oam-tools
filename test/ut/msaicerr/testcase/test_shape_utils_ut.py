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

import pytest

from conftest import MSAICERR_PATH
from ms_interface.single_op_test_frame.utils import shape_utils

sys.path.append(MSAICERR_PATH)


def test_calc_shape_size_scalar_and_missing():
    assert shape_utils.calc_shape_size([]) == 1
    assert shape_utils.calc_shape_size(()) == 1
    assert shape_utils.calc_shape_size(None) == 0


def test_calc_shape_size_normal():
    assert shape_utils.calc_shape_size([2, 3, 4]) == 24


def test_calc_shape_size_filter_negative():
    # negative dims are filtered out before product
    assert shape_utils.calc_shape_size([2, -1, 4]) == 8


def test_calc_shape_size_all_negative():
    assert shape_utils.calc_shape_size([-1, -2]) == 0


def test_calc_op_param_size_normal():
    # shape_size * dtype_byte
    assert shape_utils.calc_op_param_size(24, "float16") == 48
    assert shape_utils.calc_op_param_size(10, "int32") == 40


def test_calc_op_param_size_invalid_dtype():
    with pytest.raises(TypeError):
        shape_utils.calc_op_param_size(10, 123)
