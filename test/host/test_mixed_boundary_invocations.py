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
"""The supported optional invocation index follows prior declared calls."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "skills/cann-perf-breakdown/1-perf-breakdown/scripts/map_trace_instances.py"
)
FIXTURE = (
    ROOT
    / "skills/cann-perf-breakdown/2-adapt-breakdown-to-ui-json/tests/fixtures/synthetic/analysis_config_v2.json"
)


def _map(tmp_path, boundaries):
    path = tmp_path / "boundaries.json"
    path.write_text(json.dumps(boundaries), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--boundaries", str(path), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["trace_instances"]


def _boundaries(indices):
    rows = []
    for position, index in enumerate(indices):
        row = {"model_layer_index": 2, "op_range": [position * 2, position * 2 + 1]}
        if index is not None:
            row["invocation_index"] = index
        rows.append(row)
    return rows


@pytest.mark.parametrize("declared", (0, 3, 7))
def test_missing_invocation_continues_after_declared_index(tmp_path, declared):
    mapped = _map(tmp_path, _boundaries([declared, None]))
    assert [row["invocation_index"] for row in mapped] == [declared, declared + 1]
    assert len({row["instance_id"] for row in mapped}) == 2
    assert [row["op_range"] for row in mapped] == [[0, 1], [2, 3]]


@pytest.mark.parametrize(
    "indices,expected",
    (
        ([None, 1, None], [0, 1, 2]),
        ([0, None, 4, None], [0, 1, 4, 5]),
        ([0, 2, None], [0, 2, 3]),
    ),
)
def test_mixed_indexes_keep_declared_values_and_unique_inferred_calls(
    tmp_path, indices, expected
):
    mapped = _map(tmp_path, _boundaries(indices))
    assert [row["invocation_index"] for row in mapped] == expected
    assert len(
        {(row["model_layer_index"], row["invocation_index"]) for row in mapped}
    ) == len(mapped)


@pytest.mark.parametrize(
    "indices,expected",
    (
        ([None, 0], [1, 0]),
        ([None, None, 0, 2, None], [1, 3, 0, 2, 4]),
        ([None, 2, None, 0, None], [1, 2, 3, 0, 4]),
    ),
)
def test_automatic_calls_reserve_indexes_declared_later(tmp_path, indices, expected):
    mapped = _map(tmp_path, _boundaries(indices))
    assert [row["invocation_index"] for row in mapped] == expected
    assert len({row["instance_id"] for row in mapped}) == len(mapped)


def test_future_declared_indexes_are_reserved_per_learned_layer(tmp_path):
    rows = [
        {"model_layer_index": 0, "op_range": [0, 1]},
        {"model_layer_index": 2, "op_range": [2, 3]},
        {"model_layer_index": 0, "invocation_index": 0, "op_range": [4, 5]},
        {"model_layer_index": 2, "invocation_index": 2, "op_range": [6, 7]},
    ]
    mapped = _map(tmp_path, rows)
    assert [row["invocation_index"] for row in mapped] == [1, 0, 0, 2]
    assert (
        len({(row["model_layer_index"], row["invocation_index"]) for row in mapped})
        == 4
    )


def test_official_fixture_mtp_repeated_learned_layer_gets_distinct_identity(tmp_path):
    config = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = deepcopy(config["trace_instances"][-2:])
    assert [row["model_layer_index"] for row in rows] == [2, 2]
    for row in rows:
        row.pop("instance_id")
        row.pop("representative_instance_id", None)
    rows[1].pop("invocation_index")
    mapped = _map(tmp_path, rows)
    assert [row["invocation_index"] for row in mapped] == [0, 1]
    assert len({row["instance_id"] for row in mapped}) == 2
    assert [row["op_range"] for row in mapped] == [[21, 23], [26, 28]]
    assert all(row["layer_group_type"] == "SynDecoderLayer_mtp" for row in mapped)


def test_numbering_is_independent_between_learned_layers(tmp_path):
    rows = [
        {"model_layer_index": 0, "invocation_index": 0, "op_range": [0, 1]},
        {"model_layer_index": 2, "op_range": [2, 3]},
        {"model_layer_index": 0, "op_range": [4, 5]},
        {"model_layer_index": 2, "op_range": [6, 7]},
    ]
    mapped = _map(tmp_path, rows)
    assert [row["invocation_index"] for row in mapped] == [0, 0, 1, 1]


def test_all_automatic_calls_are_unchanged(tmp_path):
    assert [
        row["invocation_index"]
        for row in _map(tmp_path, _boundaries([None, None, None]))
    ] == [0, 1, 2]


def test_all_declared_calls_are_preserved(tmp_path):
    assert [
        row["invocation_index"] for row in _map(tmp_path, _boundaries([0, 2, 5]))
    ] == [0, 2, 5]


def test_user_instance_ids_are_preserved(tmp_path):
    rows = _boundaries([0, None])
    rows[0]["instance_id"], rows[1]["instance_id"] = "mtp_first", "mtp_second"
    mapped = _map(tmp_path, rows)
    assert [row["instance_id"] for row in mapped] == ["mtp_first", "mtp_second"]
    assert [row["invocation_index"] for row in mapped] == [0, 1]


def test_explicit_duplicate_is_not_silently_rewritten(tmp_path):
    # Explicit caller errors remain visible for the structure checker to reject.
    assert [row["invocation_index"] for row in _map(tmp_path, _boundaries([0, 0]))] == [
        0,
        0,
    ]


@pytest.mark.parametrize("declared", (None, "0", [0], {"value": 0}, 2.5))
@pytest.mark.parametrize("position", (0, 1))
def test_non_integer_explicit_value_is_preserved_without_advancing_automatic_calls(
    tmp_path, declared, position
):
    # Mapping does not validate or coerce caller-provided explicit values.
    rows = [
        {"model_layer_index": 2, "op_range": [0, 1]},
        {"model_layer_index": 2, "op_range": [4, 5]},
    ]
    explicit = {
        "model_layer_index": 2,
        "invocation_index": declared,
        "instance_id": "caller_supplied",
        "op_range": [2, 3],
    }
    rows.insert(position, explicit)
    mapped = _map(tmp_path, rows)
    assert mapped[position]["invocation_index"] == declared
    assert mapped[position]["instance_id"] == "caller_supplied"
    assert [
        row["invocation_index"]
        for row in mapped
        if row["instance_id"] != "caller_supplied"
    ] == [0, 1]
