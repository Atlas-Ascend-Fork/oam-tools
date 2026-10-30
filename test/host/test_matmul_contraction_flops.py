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
import importlib.util
import sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ("skills/cann-perf-breakdown/2-adapt-breakdown-to-ui-json/scripts",)


def load_script(path, monkeypatch):
    path = ROOT / path
    monkeypatch.syspath_prepend(str(path.parent))
    monkeypatch.delitem(sys.modules, "breakdown_paths", raising=False)
    spec = importlib.util.spec_from_file_location("host_script", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("transpose_b", [False, True])
def test_matmul_flops_use_contraction_axis(adapter, transpose_b, monkeypatch):
    module = load_script(adapter + "/emit_ui_facts.py", monkeypatch)
    left = np.zeros((256, 64))
    stored_weight = np.zeros((128, 64) if transpose_b else (64, 128))
    result = left @ (stored_weight.T if transpose_b else stored_weight)
    row = {
        "op_type": "MatMul",
        "input_shapes": [list(left.shape), list(stored_weight.shape)],
        "output_shapes": [list(result.shape)],
        "duration_us": 1,
    }
    metrics = module.node_metrics([row], 1, 2, 1)
    assert metrics.get("gflops") == round(2 * 256 * 128 * 64 / 1e9, 6)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_batched_matmul_counts_output_batches(adapter, monkeypatch):
    module = load_script(adapter + "/emit_ui_facts.py", monkeypatch)
    row = {
        "op_type": "BatchMatMulV2",
        "input_shapes": [[2, 256, 64], [2, 64, 128]],
        "output_shapes": [[2, 256, 128]],
        "duration_us": 1,
    }
    assert module.node_metrics([row], 1, 2, 1).get("gflops") == round(
        2 * 2 * 256 * 128 * 64 / 1e9, 6
    )


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    "weight",
    [
        64,
        [64],
        [64, 32],
        [-1, 128],
        [0, 128],
        [64.5, 128],
        ["64", 128],
        [128, -1],
    ],
)
def test_invalid_shapes_do_not_reduce_valid_work(adapter, weight, monkeypatch):
    module = load_script(adapter + "/emit_ui_facts.py", monkeypatch)
    invalid = {
        "op_type": "MatMul",
        "input_shapes": [[256, 64], weight],
        "output_shapes": [[256, 128]],
        "duration_us": 1,
    }
    valid = {
        "op_type": "MatMul",
        "input_shapes": [[256, 64], [64, 128]],
        "output_shapes": [[256, 128]],
        "duration_us": 1,
    }
    expected = 2 * 256 * 128 * 64
    assert module.node_metrics([invalid], 1, 2, 1)["gflops"] == 0.0
    assert module.node_metrics([invalid, valid], 1, 2, 1)["gflops"] == round(
        expected / 1e9, 6
    )
    assert module.node_metrics([valid, invalid], 1, 2, 1)["gflops"] == round(
        expected / 1e9, 6
    )
