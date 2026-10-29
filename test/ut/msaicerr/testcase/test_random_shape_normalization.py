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

from ms_interface.single_op_test_frame.utils import op_param_util


@pytest.mark.parametrize("samples", [[0, 10], [-2, 10], [0, 0], [-5, -5], [0.2, 0.3]])
def test_degenerate_normal_samples_remain_finite(monkeypatch, samples):
    monkeypatch.setattr(
        op_param_util.np.random,
        "normal",
        lambda **kwargs: np.array(samples, dtype=float),
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        shape = op_param_util.gen_shape(rank_range=[2, 2], size_range=[100, 100])
    assert all(isinstance(dim, int) and 1 <= dim <= 40 for dim in shape)
    assert np.prod(shape) <= 200


def test_positive_samples_and_dimension_limit(monkeypatch):
    monkeypatch.setattr(
        op_param_util.np.random,
        "normal",
        lambda **kwargs: np.array([10, 10], dtype=float),
    )
    assert op_param_util.gen_shape(rank_range=[2, 2], size_range=[100, 100]) == [10, 10]
    assert op_param_util.gen_shape(
        rank_range=[2, 2], size_range=[100, 100], dim_limit=6
    ) == [6, 6]


@pytest.mark.parametrize("samples", [[-5, -5], [0.2, 0.3], [1, 1000000]])
def test_small_size_keeps_final_dimensions_positive(monkeypatch, samples):
    monkeypatch.setattr(
        op_param_util.np.random,
        "normal",
        lambda **kwargs: np.array(samples, dtype=float),
    )
    shape = op_param_util.gen_shape(rank_range=[2, 2], size_range=[1, 1])
    assert all(isinstance(dim, int) and dim >= 1 for dim in shape)
    # Existing ceil rounding can exceed the sampled size; it is not an exact product cap.
    assert np.isfinite(np.prod(shape))


@pytest.mark.parametrize("rank,size", [([0, 0], [1, 1]), ([2, 2], [0, 0])])
def test_nonpositive_generation_ranges_are_reported(rank, size):
    with pytest.raises(ValueError, match="positive lower bounds"):
        op_param_util.gen_shape(rank_range=rank, size_range=size)


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_dimension_limit_is_reported(limit):
    with pytest.raises(ValueError, match="dim_limit must be positive"):
        op_param_util.gen_shape(
            rank_range=[2, 2], size_range=[100, 100], dim_limit=limit
        )
