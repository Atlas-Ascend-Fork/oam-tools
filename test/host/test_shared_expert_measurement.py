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
from collections import Counter
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
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
def test_shared_group_duration_cannot_be_duplicated_per_expert(adapter, monkeypatch):
    module = load_script(adapter + "/build_expert_inventory.py", monkeypatch)
    inventory = module.build(
        {"architecture": {"n_shared_experts": 2}},
        {"modules": [{"node_id": "model/layer/shared_expert", "time_us": 12}]},
        {"rows": []},
    )
    experts = inventory.get("experts", [])
    assert len(experts) == 2
    assert all(e.get("time_us", object()) is None for e in experts)
    assert all(e.get("data_state") == "fused_measured" for e in experts)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_one_shared_expert_keeps_its_measured_duration(adapter, monkeypatch):
    module = load_script(adapter + "/build_expert_inventory.py", monkeypatch)
    inventory = module.build(
        {"architecture": {"n_shared_experts": 1}},
        {"modules": [{"node_id": "model/layer/shared_expert", "time_us": 12}]},
        {"rows": []},
    )
    expert = inventory.get("experts", [])[0]
    assert expert.get("time_us") == 12
    assert expert.get("data_state") == "measured"


def write_validator_facts(directory):
    identity = {
        "model_id": "host-fixture",
        "report_id": "host-run",
        "representative_step": 0,
    }
    node = {"node_id": "model/layer/shared_expert", "mapped_kernels": 1}
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


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("invalid_routed_identity", [False, True])
def test_shared_aggregate_does_not_bypass_routed_residency(
    adapter, invalid_routed_identity, tmp_path, monkeypatch
):
    write_validator_facts(tmp_path)
    performance = json.loads((tmp_path / "fixture_perf_data.json").read_text())
    config = {"architecture": {"n_routed_experts": 8, "n_shared_experts": 2}}
    inventory = load_script(adapter + "/build_expert_inventory.py", monkeypatch).build(
        config, performance, {"rows": []}
    )
    assert inventory["counts"]["fused_measured"] == 2
    assert inventory["expert_parallelism"]["ep_rank"] is None
    if invalid_routed_identity:
        routed = next(e for e in inventory["experts"] if e["kind"] == "routed")
        routed["data_state"] = "fused_measured"
        inventory["counts"]["remote_ep_shard"] -= 1
        inventory["counts"]["fused_measured"] += 1
        inventory["counts"]["resident_on_profiled_rank"] += 1
    actual_counts = Counter(expert["data_state"] for expert in inventory["experts"])
    assert all(value >= 0 for value in inventory["counts"].values())
    expected_counts = {
        "declared_total": len(inventory["experts"]),
        "resident_on_profiled_rank": actual_counts["measured"]
        + actual_counts["fused_measured"],
        "individually_measured": actual_counts["measured"],
        "fused_measured": actual_counts["fused_measured"],
        "residency_unresolved": actual_counts["residency_unresolved"],
        "remote_ep_shard": actual_counts["remote_ep_shard"],
    }
    assert inventory["counts"] == expected_counts
    (tmp_path / "fixture_expert_inventory.json").write_text(json.dumps(inventory))
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / adapter / "validate_conversion.py"),
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert (result.returncode != 0) == invalid_routed_identity, (
        result.stdout + result.stderr
    )
    if invalid_routed_identity:
        assert "without ep_rank" in result.stdout


@pytest.mark.parametrize("ep_rank", [None, 1], ids=["rank-unspecified", "rank1"])
def test_shared_expert_ui_reasons_preserve_aggregation_explanation(
    monkeypatch, ep_rank
):
    config = {"architecture": {"n_shared_experts": 2}}
    performance = {"modules": [{"node_id": "model/layer/shared_expert", "time_us": 12}]}
    copies = [
        load_script(adapter + "/build_expert_inventory.py", monkeypatch).build(
            config, performance, {"rows": []}, ep_rank=ep_rank
        )["experts"]
        for adapter in ADAPTERS
    ]
    expected = (
        "The shared-expert nodes aggregate multiple declared experts. "
        "Their duration cannot identify an individual expert's time."
    )
    assert all(expert["reason"] == expected for expert in copies[0])
