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

import ctypes
from types import SimpleNamespace
import numpy as np
import pytest
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner


@pytest.mark.parametrize(
    "parameters,arg_count", [([], 0), ([None], 1), ([None], 2), ([None], 0)]
)
def test_output_without_initialization_metadata(
    mocker, kernel_mock_device, parameters, arg_count
):
    mocker.patch.object(
        AscendOpKernelRunner, "get_rts_api", return_value=kernel_mock_device
    )
    runner = AscendOpKernelRunner()
    kernel = SimpleNamespace(parameters=parameters)
    args = [ctypes.c_void_p(1)] * arg_count
    output = runner._create_output_param_with_pages(
        kernel, [{"dtype": "float32"}, args, [2]], "magic"
    )
    assert output.size == 8
    assert output.dtype == "float32"
    assert output.allocated_hbm_pointer.value is not None
    assert kernel.parameters is parameters


def test_present_metadata_still_initializes_a_new_output(mocker, kernel_mock_device):
    mocker.patch.object(
        AscendOpKernelRunner, "get_rts_api", return_value=kernel_mock_device
    )
    runner = AscendOpKernelRunner()
    metadata = {"dtype": "float32", "init_value": 3}
    kernel = SimpleNamespace(parameters=[metadata])
    output = runner._create_output_param_with_pages(
        kernel, [{"dtype": "float32"}, [], [2]], "magic"
    )
    np.testing.assert_array_equal(output._np_data, np.array([3, 3], dtype=np.float32))
    assert output.dtype == "float32"
    assert kernel.parameters == [metadata]


def test_caller_registers_new_output_and_argument(mocker, kernel_mock_device):
    mocker.patch.object(
        AscendOpKernelRunner, "get_rts_api", return_value=kernel_mock_device
    )
    runner = AscendOpKernelRunner()
    kernel = SimpleNamespace(
        parameters=[None], output_infos=[{"shape": [2], "dtype": "float32"}]
    )
    args, outputs = [ctypes.c_void_p(1)], []
    runner._fill_outputs(kernel, None, None, [], outputs, args, "magic")
    assert outputs[0] in runner._kernel_params
    assert args[-1].value == outputs[0].allocated_hbm_pointer.value
    assert len(args) == 2
