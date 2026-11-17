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

from conftest import MSAICERR_PATH, CommonAssert

sys.path.append(MSAICERR_PATH)

from ms_interface.single_op_test_frame.utils.op_param_util import (
    build_op_param,
    broadcast_shape,
    trans_shape,
    change_cur_format,
    gen_all_format_params,
    cartesian_set_format_dtype,
    gen_shape,
    gen_broadcast_shape,
    random_dtype,
)


class TestOpParamUtilMethods(CommonAssert):
    def test_build_op_param_with_tuple_3_elements(self):
        params = ("float16", [3, 4, 5, 6], "ND")
        result = build_op_param(params)
        self.assertEqual(result["dtype"], "float16")
        self.assertEqual(result["shape"], [3, 4, 5, 6])
        self.assertEqual(result["format"], "ND")
        self.assertEqual(result["ori_shape"], [3, 4, 5, 6])
        self.assertEqual(result["ori_format"], "ND")

    def test_build_op_param_with_tuple_5_elements(self):
        params = ("float32", [1, 3, 224, 224], "NCHW", [1, 3, 224, 224], "NCHW")
        result = build_op_param(params)
        self.assertEqual(result["dtype"], "float32")
        self.assertEqual(result["shape"], [1, 3, 224, 224])
        self.assertEqual(result["format"], "NCHW")
        self.assertEqual(result["ori_shape"], [1, 3, 224, 224])
        self.assertEqual(result["ori_format"], "NCHW")

    def test_build_op_param_with_list(self):
        params = ["int32", [64], "ND", [64], "ND"]
        result = build_op_param(params)
        self.assertEqual(result["dtype"], "int32")
        self.assertEqual(result["shape"], [64])

    def test_broadcast_shape_same_rank(self):
        result = broadcast_shape([3, 4, 5], [1, 4, 5])
        self.assertEqual(result, [3, 4, 5])

    def test_broadcast_shape_different_rank(self):
        result = broadcast_shape([5], [3, 4, 5])
        self.assertEqual(result, [3, 4, 5])

    def test_broadcast_shape_with_broadcast(self):
        result = broadcast_shape([4, 1], [1, 3])
        self.assertEqual(result, [4, 3])

    def test_broadcast_shape_with_all_ones(self):
        result = broadcast_shape([1, 1, 1], [3, 4, 5])
        self.assertEqual(result, [3, 4, 5])

    def test_broadcast_shape_no_broadcast(self):
        result = broadcast_shape([2, 3], [2, 3])
        self.assertEqual(result, [2, 3])

    def test_trans_shape_nchw_to_nc1hwc0(self):
        result = trans_shape([1, 3, 224, 224], "NCHW", "NC1HWC0")
        self.assertEqual(result, [1, 1, 224, 224, 16])

    def test_trans_shape_nhwc_to_nc1hwc0(self):
        result = trans_shape([1, 224, 224, 3], "NHWC", "NC1HWC0")
        self.assertEqual(result, [1, 1, 224, 224, 16])

    def test_trans_shape_default_to_nc1hwc0(self):
        result = trans_shape([3], "ND", "NC1HWC0")
        self.assertEqual(result, [1, 1, 1, 1, 16])

    def test_trans_shape_to_fractal_nz(self):
        result = trans_shape([1, 3, 224, 224], "NCHW", "FRACTAL_NZ")
        self.assertEqual(result, [1, 3, 14, 14, 16, 16])

    def test_trans_shape_to_fractal_z(self):
        result = trans_shape([1, 3, 224, 224], "NCHW", "FRACTAL_Z")
        self.assertEqual(result, [50176, 1, 16, 16])

    def test_trans_shape_to_c1hwncoc0(self):
        result = trans_shape([1, 3, 224, 224], "NCHW", "C1HWNCoC0")
        self.assertEqual(result, [1, 224, 224, 1, 16, 16])

    def test_trans_shape_to_nc1hwc0_c04(self):
        result = trans_shape([1, 3, 224, 224], "NCHW", "NC1HWC0_C04")
        self.assertEqual(result, [1, 1, 224, 224, 4])

    def test_trans_shape_to_nd(self):
        result = trans_shape([1, 3, 224, 224], "NCHW", "ND")
        self.assertEqual(result, [1, 3, 224, 224])

    def test_change_cur_format_single(self):
        op_params = [
            {
                "ori_shape": [1, 3, 224, 224],
                "ori_format": "NCHW",
                "format": "NCHW",
                "shape": [1, 3, 224, 224],
                "dtype": "float16",
            }
        ]
        result = change_cur_format(op_params, ["NC1HWC0"])
        self.assertEqual(result[0]["format"], "NC1HWC0")
        self.assertEqual(result[0]["shape"], [1, 1, 224, 224, 16])

    def test_gen_shape_default(self):
        shape = gen_shape()
        assert 1 <= len(shape) <= 8
        for dim in shape:
            assert dim >= 1

    def test_gen_shape_with_rank_range(self):
        shape = gen_shape(rank_range=[2, 4])
        assert 2 <= len(shape) <= 4

    def test_gen_broadcast_shape(self):
        a_shape, b_shape = gen_broadcast_shape()
        rank = len(a_shape)
        self.assertEqual(len(b_shape), rank)
        # verify broadcast relationship: for each dim, one of them is 1 or they're equal
        for i in range(rank):
            assert a_shape[i] == b_shape[i] or a_shape[i] == 1 or b_shape[i] == 1

    def test_random_dtype(self):
        dtype = random_dtype()
        self.assertIn(["float16", "float32", "int32"], dtype)

    def test_random_dtype_custom_list(self):
        dtype = random_dtype(("int8", "int16"))
        self.assertIn(["int8", "int16"], dtype)

    def test_cartesian_set_format_dtype(self):
        name_list = [["input0"], ["output0"]]
        dtype_list = [["float16"], ["float16"]]
        format_list = [["ND"], ["ND"]]
        result = cartesian_set_format_dtype(name_list, dtype_list, format_list)
        self.assertIn(result, "input0")
        self.assertIn(result, "output0")
        self.assertEqual(result["input0"]["dtype"], "float16")
        self.assertEqual(result["input0"]["format"], "ND")

    def test_cartesian_set_format_dtype_full(self):
        name_list = [["x", "y"], ["z"]]
        dtype_list = [["float16"], ["float32"], ["float16"]]
        format_list = [["ND"], ["NCHW"], ["ND"]]
        result = cartesian_set_format_dtype(name_list, dtype_list, format_list)
        self.assertEqual(result["input0"]["dtype"], "float16")
        self.assertEqual(result["input1"]["dtype"], "float32")
        self.assertEqual(result["output0"]["dtype"], "float16")

    def test_gen_all_format_params(self):
        op_params = [
            {
                "dtype": "float16",
                "shape": [1, 3, 224, 224],
                "format": "NCHW",
                "ori_shape": [1, 3, 224, 224],
                "ori_format": "NCHW",
            },
            {
                "dtype": "float16",
                "shape": [1, 3, 224, 224],
                "format": "NCHW",
                "ori_shape": [1, 3, 224, 224],
                "ori_format": "NCHW",
            },
        ]
        format_res = '{"input0": {"name": "a", "dtype": "float16", "format": "NC1HWC0"}, "output0": {"name": "b", "dtype": "float16", "format": "NC1HWC0"}}'
        result = gen_all_format_params(format_res, op_params)
        assert len(result) >= 1
        self.assertEqual(result[0][0]["format"], "NC1HWC0")
        self.assertEqual(result[0][1]["format"], "NC1HWC0")
