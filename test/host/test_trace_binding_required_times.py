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


def run_binding(adapter, tmp_path, row, raw, *, event_count=1):
    timeline = {
        "model_id": "fixture",
        "report_id": "fixture",
        "events": [
            {"event_id": f"e{index}", "op_index": index, "owner_node_id": f"n{index}"}
            for index in range(event_count)
        ],
    }
    values = {
        "timeline": timeline,
        "attribution": {
            "rows": [{**row, "op_index": index} for index in range(event_count)]
        },
        "trace": raw,
    }
    for name, value in values.items():
        (tmp_path / (name + ".json")).write_text(json.dumps(value))
    output = tmp_path / "bindings.json"
    args = [sys.executable, str(ROOT / adapter / "build_trace_bindings.py")]
    for name in values:
        args += ["--" + name, str(tmp_path / (name + ".json"))]
    args += ["--out", str(output)]
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    return result, output


def inputs():
    return (
        {"op_index": 0, "op_name": "Kernel", "start_time_us": 0, "duration_us": 0},
        {"ph": "X", "name": "Kernel", "ts": 0, "dur": 0},
    )


def mutate(target, key, bad):
    if bad == "missing":
        target.pop(key)
    else:
        target[key] = {
            "none": None,
            "nan": float("nan"),
            "infinity": float("inf"),
            "negative": -1,
            "text": "not-a-time",
        }[bad]


def assert_clean_failure(result, output, field):
    assert result.returncode == 1
    assert not output.exists()
    diagnostic = result.stdout + result.stderr
    assert "UNRESOLVED op_index=0" in diagnostic
    assert field in diagnostic
    assert "could not be bound" in diagnostic
    assert "Traceback" not in diagnostic


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("which", ["row", "raw"])
@pytest.mark.parametrize(
    "bad", ["missing", "none", "nan", "infinity", "negative", "text"]
)
def test_invalid_used_duration_has_clean_contract_failure(
    adapter, which, bad, tmp_path
):
    row, raw = inputs()
    mutate(
        row if which == "row" else raw, "duration_us" if which == "row" else "dur", bad
    )
    result, output = run_binding(adapter, tmp_path, row, [raw])
    assert_clean_failure(result, output, "duration")


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("bad", ["missing", "nan", "negative"])
def test_bad_unused_candidate_does_not_abort_valid_match(adapter, bad, tmp_path):
    row, raw = inputs()
    invalid = dict(raw)
    mutate(invalid, "dur", bad)
    result, output = run_binding(adapter, tmp_path, row, [invalid, raw])
    assert result.returncode == 0, result.stdout + result.stderr
    binding = json.loads(output.read_text())["bindings"][0]
    assert binding["raw_source_event_index"] == 1


@pytest.mark.parametrize("which", ["row", "raw"])
@pytest.mark.parametrize("bad", ["missing", "nan"])
def test_duration_only_adapter_does_not_require_unused_timestamp(which, bad, tmp_path):
    # Timestamp-based ownership is a separate change; preserve this adapter's existing matcher.
    row, raw = inputs()
    mutate(
        row if which == "row" else raw, "start_time_us" if which == "row" else "ts", bad
    )
    result, output = run_binding(ADAPTERS[0], tmp_path, row, [raw])
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(output.read_text())["bindings"][0]["node_id"] == "n0"


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("timestamp", [0, -1])
def test_zero_duration_and_finite_timestamps_remain_valid(adapter, timestamp, tmp_path):
    row, raw = inputs()
    row["start_time_us"] = raw["ts"] = timestamp
    result, output = run_binding(adapter, tmp_path, row, [raw])
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(output.read_text())["bindings"][0]["node_id"] == "n0"


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("bad_first", [True, False])
def test_exhausted_same_name_candidates_report_no_free_raw_event(
    adapter, bad_first, tmp_path
):
    row, raw = inputs()
    unrelated = {**raw, "name": "OtherKernel"}
    unrelated.pop("dur")
    events = [unrelated, raw] if bad_first else [raw, unrelated]
    result, output = run_binding(adapter, tmp_path, row, events, event_count=2)
    assert result.returncode == 1
    assert not output.exists()
    diagnostic = result.stdout + result.stderr
    assert "UNRESOLVED op_index=1: no free raw X event named 'Kernel'" in diagnostic
    assert "invalid raw matching fields" not in diagnostic
    assert "1 Timeline event(s) could not be bound" in diagnostic
    assert "Traceback" not in diagnostic


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_distinct_same_name_candidates_bind_each_timeline_event_once(adapter, tmp_path):
    row, raw = inputs()
    result, output = run_binding(
        adapter, tmp_path, row, [raw, dict(raw)], event_count=2
    )
    assert result.returncode == 0, result.stdout + result.stderr
    bindings = json.loads(output.read_text())["bindings"]
    assert [binding["raw_source_event_index"] for binding in bindings] == [0, 1]
    assert [binding["node_id"] for binding in bindings] == ["n0", "n1"]
