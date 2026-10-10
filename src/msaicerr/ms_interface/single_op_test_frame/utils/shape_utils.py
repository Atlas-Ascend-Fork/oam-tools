#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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
"""
shape utils module
"""

import numpy as np
from ms_interface.single_op_test_frame.common import dtype_trans


def calc_shape_size(shape):
    """
    calc shape size
    :param shape: shape
    :return: shape's size
    """
    if shape is None:
        return 0
    if len(shape) == 0:
        return 1

    shape_nums = np.array(shape, dtype=np.int64)
    shape_nums = shape_nums[np.where(shape_nums >= 0)]
    if len(shape_nums) == 0:
        return 0

    size = np.prod(shape_nums, dtype=np.int64)
    return int(size)


def calc_op_param_size(shape_size, dtype):
    """
    calculate operator parameter size
    """
    if not isinstance(dtype, str) and dtype not in dtype_trans.get_all_str_dtypes():
        raise TypeError(
            "dtype must be str and in [%s]" % ",".join(dtype_trans.get_all_str_dtypes())
        )
    dtype_size = dtype_trans.get_dtype_byte(dtype)
    return shape_size * dtype_size
