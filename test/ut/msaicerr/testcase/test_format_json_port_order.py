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

import copy
import json

import pytest

from ms_interface.single_op_test_frame.utils.op_param_util import gen_all_format_params


def parameter(dtype="float32"):
    return {
        "dtype": dtype,
        "shape": [1, 3, 2, 2],
        "format": "NCHW",
        "ori_shape": [1, 3, 2, 2],
        "ori_format": "NCHW",
    }


def test_reordered_json_does_not_discard_valid_dtype_combination():
    entries = {
        "input1": {"dtype": "float32", "format": "NC1HWC0"},
        "input0": {"dtype": "float16", "format": "ND"},
    }
    params = [parameter("float16"), parameter()]
    original = copy.deepcopy(params)
    result = gen_all_format_params(json.dumps(entries), params)
    assert len(result) == 1
    assert [p["format"] for p in result[0]] == ["ND", "NC1HWC0"]
    assert params == original


def test_reordered_same_dtype_entries_keep_formats_on_the_right_ports():
    entries = {
        "input1": {"dtype": "float32", "format": "NC1HWC0"},
        "input0": {"dtype": "float32", "format": "ND"},
    }
    result = gen_all_format_params(json.dumps(entries), [parameter(), parameter()])
    assert [p["format"] for p in result[0]] == ["ND", "NC1HWC0"]
    assert [p["shape"] for p in result[0]] == [[1, 3, 2, 2], [1, 1, 2, 2, 16]]


def test_double_digit_ports_use_numeric_order():
    entries = {
        f"input{i}": {"dtype": "float32", "format": "NC1HWC0" if i == 10 else "ND"}
        for i in reversed(range(12))
    }
    result = gen_all_format_params(
        json.dumps(entries), [parameter() for _ in range(12)]
    )
    assert [p["format"] for p in result[0]] == [
        "NC1HWC0" if i == 10 else "ND" for i in range(12)
    ]


def test_original_input_and_output_order_is_preserved():
    entries = {
        "input0": {"dtype": "float32", "format": "ND"},
        "output0": {"dtype": "float16", "format": "ND"},
    }
    result = gen_all_format_params(
        json.dumps(entries), [parameter(), parameter("float16")]
    )
    assert len(result) == 1
    assert [p["dtype"] for p in result[0]] == ["float32", "float16"]


@pytest.mark.parametrize("key", ["input_weight", "outputGrad", "input", "output-1"])
def test_invalid_port_key_is_reported(key):
    entries = {key: {"dtype": "float32", "format": "ND"}}
    with pytest.raises(ValueError, match="Invalid format port key"):
        gen_all_format_params(json.dumps(entries), [parameter()])


def test_double_digit_output_ports_use_numeric_order():
    entries = {
        f"output{i}": {"dtype": "float32", "format": "NC1HWC0" if i == 10 else "ND"}
        for i in reversed(range(12))
    }
    result = gen_all_format_params(
        json.dumps(entries), [parameter() for _ in range(12)]
    )
    assert [p["format"] for p in result[0]] == [
        "NC1HWC0" if i == 10 else "ND" for i in range(12)
    ]


@pytest.mark.parametrize("count", [0, 2])
def test_port_count_mismatch_is_reported(count):
    entries = {"input0": {"dtype": "float32", "format": "ND"}}
    with pytest.raises(ValueError, match="port count"):
        gen_all_format_params(json.dumps(entries), [parameter() for _ in range(count)])


@pytest.mark.parametrize(
    "entries,message",
    [
        ({"input0": {"dtype": "float32,float16", "format": "ND"}}, "dtype and format"),
        ({"output0": {"dtype": "float32", "format": "ND,NCHW"}}, "dtype and format"),
        (
            {
                "input0": {"dtype": "float32,float32", "format": "ND,NCHW"},
                "output0": {"dtype": "float32", "format": "ND"},
            },
            "combination count",
        ),
    ],
)
def test_mismatched_combination_lists_are_rejected(entries, message):
    params = [parameter() for _ in entries]
    original = copy.deepcopy(params)
    with pytest.raises(ValueError, match=message):
        gen_all_format_params(json.dumps(entries), params)
    assert params == original


def test_equal_combination_lists_preserve_all_columns():
    entries = {
        "input0": {"dtype": "float32,float32", "format": "ND,NC1HWC0"},
        "output0": {"dtype": "float32,float32", "format": "ND,NC1HWC0"},
    }
    result = gen_all_format_params(json.dumps(entries), [parameter(), parameter()])
    assert [[p["format"] for p in column] for column in result] == [
        ["ND", "ND"],
        ["NC1HWC0", "NC1HWC0"],
    ]
