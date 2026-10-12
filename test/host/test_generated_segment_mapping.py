# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Consume actual generated layer candidates while preserving legacy inputs."""

import csv
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS = (
    Path(__file__).resolve().parents[2]
    / "skills/cann-perf-breakdown/1-perf-breakdown/scripts"
)


def _cli(script, *args):
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _generate_segments(tmp_path, layers, compact):
    source = tmp_path / "kernel_details.csv"
    fields = [
        "Step Id",
        "Name",
        "Duration(us)",
        "Start Time(us)",
        "Stream ID",
        "Accelerator Core",
    ]
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index in range(layers * 2):
            writer.writerow(
                {
                    "Step Id": "0",
                    "Name": "RmsNorm" if index % 2 == 0 else "MatMul",
                    "Duration(us)": 1,
                    "Start Time(us)": index * 10,
                    "Stream ID": "40",
                    "Accelerator Core": "AI_CORE",
                }
            )
    raw_path, compact_path = (
        tmp_path / "raw_ops.json",
        tmp_path / "raw_ops.compact.json",
    )
    _cli(
        "analyze_kernels.py",
        "-f",
        source,
        "-o",
        raw_path,
        "--compact-out",
        compact_path,
    )
    path = tmp_path / "op_segments.json"
    _cli(
        "segment_layers.py",
        "--raw-ops",
        compact_path if compact else raw_path,
        "-o",
        path,
    )
    return path, json.loads(path.read_text(encoding="utf-8"))


def _map(path):
    return json.loads(_cli("map_trace_instances.py", "--from-segments", path, "--json"))


@pytest.mark.parametrize("compact", (False, True))
def test_real_csv_generated_ranges_become_unknown_layer_instances(tmp_path, compact):
    path, segments = _generate_segments(tmp_path, 16, compact)
    assert segments["confidence"] == 1.0
    assert len(segments["ranges"]) == 16
    mapped = _map(path)
    instances = mapped["trace_instances"]
    assert len(instances) == 16
    assert [item["op_range"] for item in instances] == [
        item["op_range"] for item in segments["ranges"]
    ]
    assert all(item["model_layer_index"] == "unknown" for item in instances)
    assert [item["invocation_index"] for item in instances] == list(range(16))
    assert len({item["instance_id"] for item in instances}) == 16
    assert mapped["execution_counts"] == {"unknown": 16}


@pytest.mark.parametrize("compact", (False, True))
@pytest.mark.parametrize("layers", (2, 4))
def test_no_confident_ranges_does_not_invent_instances(tmp_path, compact, layers):
    path, segments = _generate_segments(tmp_path, layers, compact)
    assert segments["confidence"] < 0.5
    assert segments["ranges"] == []
    assert _map(path) == {"trace_instances": [], "execution_counts": {}}


@pytest.mark.parametrize(
    "payload,expected",
    (
        ({"segments": [{"op_range": [0, 3]}, {"op_range": [4, 7]}]}, [[0, 3], [4, 7]]),
        ({"candidates": [{"op_range": [1, 2]}]}, [[1, 2]]),
        ({"segments": [{"start": 2, "end": 5}]}, [[2, 5]]),
    ),
)
def test_legacy_coordinate_inputs_still_work(tmp_path, payload, expected):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    instances = _map(path)["trace_instances"]
    assert [item["op_range"] for item in instances] == expected
    assert all(item["model_layer_index"] == "unknown" for item in instances)


def test_generated_ranges_take_priority_over_statistical_candidate_metadata(tmp_path):
    payload = {
        "ranges": [{"layer_idx": 0, "op_range": [0, 1], "marker_index": 0}],
        "candidates": [{"kernel": "RmsNorm", "count": 16, "mean": 2, "cv": 0}],
    }
    path = tmp_path / "segments.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert _map(path)["trace_instances"][0]["op_range"] == [0, 1]


def test_empty_segment_artifact_stays_empty(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"ranges": [], "candidates": []}), encoding="utf-8")
    assert _map(path) == {"trace_instances": [], "execution_counts": {}}


@pytest.mark.parametrize(
    "legacy",
    (
        {"candidates": [{"op_range": [1, 2]}]},
        {"segments": [{"op_range": [1, 2]}]},
        {
            "segments": [{"op_range": [1, 2]}],
            "candidates": [{"op_range": [3, 4]}],
        },
    ),
)
def test_explicit_empty_ranges_override_legacy_coordinates(tmp_path, legacy):
    path = tmp_path / "empty-with-legacy.json"
    path.write_text(json.dumps({"ranges": [], **legacy}), encoding="utf-8")
    assert _map(path) == {"trace_instances": [], "execution_counts": {}}


def test_explicit_learned_layer_boundary_identity_is_unchanged(tmp_path):
    path = tmp_path / "boundaries.json"
    path.write_text(
        json.dumps(
            [{"model_layer_index": 4, "invocation_index": 2, "op_range": [0, 5]}]
        ),
        encoding="utf-8",
    )
    result = json.loads(_cli("map_trace_instances.py", "--boundaries", path, "--json"))
    assert result["trace_instances"] == [
        {
            "instance_id": "layer_4_iter_2",
            "model_layer_index": 4,
            "invocation_index": 2,
            "op_range": [0, 5],
        }
    ]
    assert result["execution_counts"] == {"4": 1}


@pytest.mark.parametrize("ranges", [None, 3, "unknown", {}])
def test_non_list_ranges_fall_back_to_legacy_coordinates(tmp_path, ranges):
    path = tmp_path / "non-list-ranges.json"
    path.write_text(
        json.dumps({"ranges": ranges, "candidates": [{"op_range": [1, 2]}]}),
        encoding="utf-8",
    )
    instances = _map(path)["trace_instances"]
    assert [item["op_range"] for item in instances] == [[1, 2]]
