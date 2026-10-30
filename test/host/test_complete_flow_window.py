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
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ("skills/cann-perf-breakdown/2-adapt-breakdown-to-ui-json/scripts",)


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("times", [(0, 15, 30), (15, 30, 40)])
def test_selected_flow_keeps_start_step_and_end(adapter, times, tmp_path):
    events = [
        {"ph": phase, "cat": "selected", "name": "work", "id": 7, "ts": timestamp}
        for phase, timestamp in zip(("s", "t", "f"), times)
    ]
    events += [
        {"ph": "s", "cat": "other", "name": "other_work", "id": 7, "ts": 100},
        {"ph": "f", "cat": "other", "name": "other_work", "id": 7, "ts": 120},
    ]
    trace, ops, output = (
        tmp_path / "trace.json",
        tmp_path / "ops.json",
        tmp_path / "out.json",
    )
    trace.write_text(json.dumps(events))
    ops.write_text(
        json.dumps({"operators": [{"start_time_us": 10, "duration_us": 10}]})
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / adapter / "narrow_trace_window.py"),
            "--trace",
            str(trace),
            "--raw-ops",
            str(ops),
            "--output",
            str(output),
            "--pad-us",
            "0",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == events[:3]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_idless_flow_is_diagnosed_and_zero_id_is_retained(adapter, tmp_path):
    idless = [{"ph": phase, "ts": 15} for phase in ("s", "t", "f")]
    selected = [
        {"ph": phase, "id": 0, "ts": ts}
        for phase, ts in zip(("s", "t", "f"), (0, 15, 30))
    ]
    trace, ops, output = (
        tmp_path / "trace.json",
        tmp_path / "ops.json",
        tmp_path / "out.json",
    )
    trace.write_text(json.dumps(idless + selected))
    ops.write_text(
        json.dumps({"operators": [{"start_time_us": 10, "duration_us": 10}]})
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / adapter / "narrow_trace_window.py"),
            "--trace",
            str(trace),
            "--raw-ops",
            str(ops),
            "--output",
            str(output),
            "--pad-us",
            "0",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == selected
    summary = json.loads(result.stdout)
    assert summary["flow_events_missing_id"] == 3
    assert summary["flow_events_kept"] == 3
