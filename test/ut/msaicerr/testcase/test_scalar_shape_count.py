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

import numpy as np
import pytest
import ctypes
from unittest.mock import Mock

from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelParam
from ms_interface.single_op_test_frame.utils.shape_utils import calc_shape_size


@pytest.mark.parametrize("shape", [[], ()])
def test_explicit_scalar_shape_has_one_element(shape):
    assert calc_shape_size(shape) == 1
    parameter = AscendOpKernelParam(shape=shape, dtype="float32")
    assert parameter.shape_size == 1
    assert parameter.size == 4


def test_scalar_binary_is_loaded_without_discarding_its_value(tmp_path):
    binary = tmp_path / "scalar.bin"
    np.array([7], dtype=np.float32).tofile(binary)
    parameter = AscendOpKernelParam.build_op_param_by_data_file(
        str(binary), "float32", []
    )
    assert parameter.shape == ()
    assert parameter.shape_size == 1
    assert parameter.size == 4
    assert parameter._np_data.item() == 7


@pytest.mark.parametrize(
    "shape,expected",
    [(None, 0), ([0], 0), ([2, 0, 3], 0), ([2, 3], 6), ([-1], 0), ([-1, 3], 3)],
)
def test_existing_missing_zero_dynamic_and_normal_shapes(shape, expected):
    assert calc_shape_size(shape) == expected


@pytest.mark.parametrize("mode", ["tail", "magic"])
@pytest.mark.parametrize("shape", [[], [1], [2, 3]])
def test_binary_data_sync_copies_all_bytes(tmp_path, mode, shape):
    count = calc_shape_size(shape)
    values = np.arange(count, dtype=np.float32) + 7
    binary = tmp_path / "values.bin"
    values.tofile(binary)
    parameter = AscendOpKernelParam.build_op_param_by_data_file(
        str(binary), "float32", shape
    )
    runtime = Mock()
    runtime.malloc.return_value = ctypes.c_void_p(0x100000)
    parameter.sync_to_device(runtime, mode=mode)
    copied = runtime.memcpy.call_args.args
    assert copied[2] == values.tobytes()
    assert copied[3] == values.nbytes
    assert copied[1] >= values.nbytes
    assert copied[4] == "RT_MEMCPY_HOST_TO_DEVICE"
    assert parameter.size == values.nbytes
    parameter.release_device()
    runtime.free.assert_called_once()
