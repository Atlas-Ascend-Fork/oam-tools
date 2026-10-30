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


def write_facts(directory):
    identity = {
        "model_id": "host-fixture",
        "report_id": "host-run",
        "representative_step": 0,
    }
    node = {"node_id": "model/host-fixture/a", "mapped_kernels": 1}
    analysis = {**identity, "stages": {"a": node}, "source_only_structure": []}
    record = {
        "node_id": node.get("node_id"),
        "time_us": 1,
        "time_pct": 100,
        "nops": 1,
        "hbm_mb": None,
        "mfu_int8_pct": None,
        "mfu_bf16_pct": None,
        "metric_scope": "single_instance",
        "op_ratio": {},
        "aicore_time_us": None,
        "mac_ratio": None,
        "mte2_ratio": None,
    }
    performance = {**identity, "modules": [record]}
    timeline = {
        **identity,
        "events": [{"owner_node_id": node.get("node_id"), "op_index": 0}],
    }
    for suffix, value in (
        ("analysis_config", analysis),
        ("perf_data", performance),
        ("timeline", timeline),
    ):
        (directory / ("fixture_" + suffix + ".json")).write_text(json.dumps(value))
    graph = {
        "schema_version": "model_architecture_graph.v1",
        "roots": ["section/source_architecture", "section/runtime_auxiliary"],
        "nodes": [{"id": "a", "backendNodeId": node.get("node_id")}, {"id": "b"}],
        "edges": [
            {
                "id": "a-b",
                "source": "a",
                "target": "b",
                "tensor": {"shape": [1]},
                "provenance": ["Host schema fixture"],
            }
        ],
    }
    (directory / "outputs").mkdir()
    (directory / "outputs/model_architecture_graph.json").write_text(json.dumps(graph))


def validate(adapter, directory):
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / adapter / "validate_conversion.py"),
            "--out",
            str(directory),
        ],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_missing_mapped_performance_record_is_rejected(adapter, tmp_path):
    write_facts(tmp_path)
    path = tmp_path / "fixture_perf_data.json"
    performance = json.loads(path.read_text())
    performance["modules"] = []
    path.write_text(json.dumps(performance))
    result = validate(adapter, tmp_path)
    assert result.returncode != 0
    assert "every mapped analysis node has a performance record" in result.stdout


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_mapped_record_is_preserved(adapter, tmp_path):
    write_facts(tmp_path)
    result = validate(adapter, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
