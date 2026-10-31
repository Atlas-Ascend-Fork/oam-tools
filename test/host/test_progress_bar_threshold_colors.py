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
"""Static regression for ``progress_bar`` threshold colors (issue #291).

``skills/`` is excluded from ruff-check / ruff-format / bandit / typos in
``.pre-commit-config.yaml``, so ``test/host`` -- collected by the ``host_ut``
case of ``scripts/run_tests.sh`` -- is the only gate guarding the HTML
generator.  Before the fix, the ``higher_is_bad=False`` branch tested
``v >= warn`` before ``v >= severe``; with ``warn < severe`` (Computing is
called with ``30, 50`` and the core-type breakdown with ``50, 80``) every
value at or above ``warn`` rendered green, the orange warning band was
unreachable, and a 40% Computing bar showed green next to a "偏低" verdict
in the same row.
"""

import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "skills/cann-npu-perfanalysis/references/generate_html.py"

GREEN = "#2ecc71"
ORANGE = "#e67e22"
RED = "#e74c3c"

BACKGROUND_RE = re.compile(r"background:(#[0-9a-f]{6})")
COMPUTING_ROW_RE = re.compile(r"<tr><td>Computing</td>.*?</tr>", re.DOTALL)


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_html_under_test", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATE_HTML = _load_generator()


def bar_color(value, warn, severe, higher_is_bad=False):
    """Return the fill color ``progress_bar`` picked for ``value``."""
    rendered = GENERATE_HTML.progress_bar(
        value, warn, severe, higher_is_bad=higher_is_bad
    )
    colors = BACKGROUND_RE.findall(rendered)
    assert len(colors) == 1, f"进度条应恰好含一个背景色，实得 {colors}：{rendered}"
    return colors[0]


def computing_row(computing_ratio):
    """Render 每步时间拆分 and return the Computing row of 指标可视化."""
    data = {
        "iteration_efficiency": {
            "steps": [],
            "warmup_steps": [],
            "normal_steps": [1],
            "avg": {
                "computing_ratio": computing_ratio,
                "comm_no_ratio": 0.10,
                "free_ratio": 0.50,
                "stage_us": 1000.0,
            },
        }
    }
    rendered = GENERATE_HTML.render_iter_efficiency(data)
    match = COMPUTING_ROW_RE.search(rendered)
    assert match, f"渲染结果里没有 Computing 行：{rendered}"
    return match.group(0)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (20, RED),
        (29.9, RED),
        (30, ORANGE),
        (40, ORANGE),
        (49.9, ORANGE),
        (50, GREEN),
        (60, GREEN),
    ],
)
def test_computing_thresholds(value, expected):
    """Computing 用 warn=30 / severe=50，红橙绿三档都必须可达。"""
    assert bar_color(value, 30, 50) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (49.9, RED),
        (50, ORANGE),
        (65, ORANGE),
        (79.9, ORANGE),
        (80, GREEN),
    ],
)
def test_core_type_breakdown_thresholds(value, expected):
    """核心类型分布用 warn=50 / severe=80，50%-80% 必须是橙色警告。"""
    assert bar_color(value, 50, 80) == expected


@pytest.mark.parametrize(
    ("value", "warn", "severe", "expected"),
    [
        (14, 15, 30, GREEN),
        (15, 15, 30, ORANGE),
        (29.9, 15, 30, ORANGE),
        (30, 15, 30, RED),
        (9, 10, 20, GREEN),
        (10, 10, 20, ORANGE),
        (20, 10, 20, RED),
    ],
)
def test_negative_metric_thresholds_are_unchanged(value, warn, severe, expected):
    """higher_is_bad=True（CommNO 15/30、Free 10/20）语义保持原样。"""
    assert bar_color(value, warn, severe, higher_is_bad=True) == expected


def test_computing_row_color_matches_verdict():
    """40% Computing：条形为橙色，且同行文字判定为「⚠️ 偏低」。"""
    row = computing_row(0.40)
    assert BACKGROUND_RE.findall(row) == [ORANGE], row
    assert "⚠️ 偏低" in row, row


def test_computing_row_green_matches_normal_verdict():
    """60% Computing：条形为绿色，同行文字判定为「✅ 正常」。"""
    row = computing_row(0.60)
    assert BACKGROUND_RE.findall(row) == [GREEN], row
    assert "✅ 正常" in row, row


@pytest.mark.parametrize("ratio", [0.20, 0.30, 0.40, 0.499, 0.50, 0.60])
def test_computing_bar_and_verdict_never_disagree(ratio):
    """绿色当且仅当文字判「✅ 正常」，防止颜色与判定再次分叉。"""
    row = computing_row(ratio)
    colors = BACKGROUND_RE.findall(row)
    assert len(colors) == 1, row
    assert (colors[0] == GREEN) == ("✅ 正常" in row), row
