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

from types import SimpleNamespace
import pytest
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner


@pytest.mark.parametrize("mode", ["magic", "tail"])
@pytest.mark.parametrize(
    "initializers",
    [
        [{"dtype": "int8", "init_value": 7}],
        [None],
        [{"dtype": "int8", "init_value": None}],
        [{"dtype": "int8", "init_value": 7}, None],
    ],
)
def test_workspace_passes_payload_address_without_extra_allocation(
    mocker, kernel_mock_device, mode, initializers
):
    device = kernel_mock_device
    mocker.patch.object(AscendOpKernelRunner, "get_rts_api", return_value=device)
    runner = AscendOpKernelRunner()
    sizes = [32] * len(initializers)
    kernel = SimpleNamespace(parameters=initializers, workspace=sizes)
    pointers, args = [], []
    runner._fill_workspace(kernel, 32, pointers, args, mode)
    assert device.malloc.call_count == len(sizes)
    assert len(runner._kernel_params) == len(sizes)
    for param, pointer, argument in zip(runner._kernel_params, pointers, args):
        assert pointer.value == argument.value == param.allocated_hbm_pointer.value
        assert argument.value != param.origin_pointer.value
    if len(initializers) == 1 and initializers[0]:
        expected = bytes([initializers[0]["init_value"] or 0]) * 32
        assert device.memcpy.call_args.args[2] == expected


def test_workspace_copy_failure_propagates(mocker, kernel_mock_device):
    mocker.patch.object(
        AscendOpKernelRunner, "get_rts_api", return_value=kernel_mock_device
    )
    kernel_mock_device.memcpy.side_effect = RuntimeError("copy failed")
    runner = AscendOpKernelRunner()
    kernel = SimpleNamespace(
        parameters=[{"dtype": "int8", "init_value": 7}], workspace=[32]
    )
    with pytest.raises(RuntimeError, match="copy failed"):
        runner._fill_workspace(kernel, 32, [], [], "magic")
    assert kernel_mock_device.malloc.call_count == 1
