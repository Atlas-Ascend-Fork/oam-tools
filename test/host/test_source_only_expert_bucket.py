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
"""An unobserved shared expert stays a legal inventory state (issue #279).

The generator emits `source_only` for a declared shared expert whose kernels fell outside
this capture, but `counts` used to carry only the other four buckets, and both validators
summed only those four. With 1 shared expert declared and none observed, a legitimate
single-entry `source_only` inventory summed to 0 against 1 listed expert and was rejected.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ("skills/cann-perf-breakdown/2-adapt-breakdown-to-ui-json/scripts",)

#: The five mutually exclusive `data_state` buckets `counts` must partition.
STATE_BUCKETS = (
    "individually_measured",
    "fused_measured",
    "residency_unresolved",
    "remote_ep_shard",
    "source_only",
)

#: `counts` key -> the `data_state` value it tallies.
BUCKET_TO_STATE = {
    "individually_measured": "measured",
    "fused_measured": "fused_measured",
    "residency_unresolved": "residency_unresolved",
    "remote_ep_shard": "remote_ep_shard",
    "source_only": "source_only",
}


def load_script(path, monkeypatch):
    path = ROOT / path
    monkeypatch.syspath_prepend(str(path.parent))
    monkeypatch.delitem(sys.modules, "breakdown_paths", raising=False)
    spec = importlib.util.spec_from_file_location("host_script", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def unobserved_shared_inventory(adapter, monkeypatch, shared_experts=1):
    """Inventory for a model declaring shared experts that this capture never observed."""
    module = load_script(adapter + "/build_expert_inventory.py", monkeypatch)
    return module.build(
        {"architecture": {"n_shared_experts": shared_experts}},
        # No `.../shared_expert` module: nothing was attributed to the shared expert.
        {"model_id": "host-fixture", "report_id": "host-run", "modules": []},
        {"rows": []},
    )


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_source_only_is_counted(adapter, monkeypatch):
    inventory = unobserved_shared_inventory(adapter, monkeypatch)
    experts = inventory["experts"]
    assert len(experts) == 1
    assert experts[0]["data_state"] == "source_only"
    # The measurement limit is preserved: unknown, never zero.
    assert experts[0]["time_us"] is None
    assert inventory["counts"]["source_only"] == 1


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_counts_partition_every_listed_expert(adapter, monkeypatch):
    """The buckets sum to the listed experts, whatever the mix of states."""
    for shared_experts in (1, 2, 3):
        inventory = unobserved_shared_inventory(adapter, monkeypatch, shared_experts)
        actual = Counter(expert["data_state"] for expert in inventory["experts"])
        counts = inventory["counts"]
        assert set(STATE_BUCKETS) <= set(counts), sorted(
            set(STATE_BUCKETS) - set(counts)
        )
        assert sum(counts[key] for key in STATE_BUCKETS) == len(inventory["experts"])
        for key in STATE_BUCKETS:
            assert counts[key] == actual.get(BUCKET_TO_STATE[key], 0)


def write_validator_facts(directory, inventory):
    """Minimal, self-consistent conversion facts plus the inventory under test."""
    identity = {
        "model_id": "host-fixture",
        "report_id": "host-run",
        "representative_step": 0,
    }
    node = {"node_id": "model/layer/routed_experts", "mapped_kernels": 1}
    analysis = {**identity, "stages": {"a": node}, "source_only_structure": []}
    record = {
        "node_id": node["node_id"],
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
        "events": [{"owner_node_id": node["node_id"], "op_index": 0}],
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
        "nodes": [{"id": "a", "backendNodeId": node["node_id"]}, {"id": "b"}],
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
    inventory = {**identity, **inventory}
    (directory / "fixture_expert_inventory.json").write_text(json.dumps(inventory))


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_validator_accepts_source_only_inventory(adapter, monkeypatch, tmp_path):
    """The reported failure: buckets sum=0, listed=1 rejected a legitimate inventory."""
    inventory = unobserved_shared_inventory(adapter, monkeypatch)
    write_validator_facts(tmp_path, inventory)
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
    assert result.returncode == 0, result.stdout + result.stderr
    assert "every expert falls in exactly one data_state bucket" in result.stdout
    assert "FAIL" not in result.stdout


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_validator_still_rejects_an_unbalanced_partition(
    adapter, monkeypatch, tmp_path
):
    """Counting `source_only` must not weaken the check: a dropped expert still fails."""
    inventory = unobserved_shared_inventory(adapter, monkeypatch)
    inventory["counts"]["source_only"] = 0
    write_validator_facts(tmp_path, inventory)
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
    assert result.returncode != 0
    assert "buckets sum to 0, listed 1" in result.stdout


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_validator_rejects_a_miscounted_split_that_still_sums(
    adapter, monkeypatch, tmp_path
):
    """The total-only blind spot: re-labelled buckets still add up, so only a per-bucket
    comparison sees them.

    Claiming `fused_measured=1, source_only=0` for the one unobserved shared expert keeps the
    five buckets summing to the 1 listed expert, while telling the UI a GroupedMatmul measured
    an expert that this capture never observed.
    """
    inventory = unobserved_shared_inventory(adapter, monkeypatch)
    inventory["counts"]["source_only"] = 0
    inventory["counts"]["fused_measured"] = 1
    write_validator_facts(tmp_path, inventory)
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
    assert result.returncode != 0, result.stdout + result.stderr
    # The sum check passes — that is exactly why it cannot be the only guard.
    assert "PASS  every expert falls in exactly one data_state bucket" in result.stdout
    assert (
        "FAIL  each data_state bucket count matches the listed experts" in result.stdout
    )
    assert "fused_measured: counts=1, listed 0" in result.stdout
    assert "source_only: counts=0, listed 1" in result.stdout


def write_inventory_cli_inputs(directory):
    """A 256-routed + 1-unobserved-shared capture: local=16, so `--ep-rank` resolves residency.

    The GroupedMatmul weight `[16, 7168, 2048]` is what `observed_local_experts` reads the
    rank's local expert count from; no `.../shared_expert` module means the declared shared
    expert stays `source_only`.
    """
    config = {"architecture": {"n_routed_experts": 256, "n_shared_experts": 1}}
    performance = {
        "model_id": "host-fixture",
        "report_id": "host-run",
        "modules": [
            {"node_id": "model/layers.0/mlp/routed_experts", "time_us": 12.5},
        ],
    }
    attribution = {
        "rows": [
            {
                "op_index": 0,
                "op_type": "GroupedMatmul",
                "input_shapes": [[128, 7168], [16, 7168, 2048], [16]],
            }
        ]
    }
    paths = {}
    for name, value in (
        ("config", config),
        ("performance", performance),
        ("attribution", attribution),
    ):
        paths[name] = directory / f"fixture_{name}.json"
        paths[name].write_text(json.dumps(value))
    paths["out"] = directory / "fixture_expert_inventory.json"
    return paths


def run_inventory_main(adapter, monkeypatch, paths, ep_rank):
    """Run the real `main()` in-process and return its stdout lines.

    Only the Skill 1 readiness gate is stubbed: it validates the whole five-file handoff,
    which this test is not about. Every line the CLI prints comes from the real function.
    """
    scripts = ROOT / adapter
    monkeypatch.syspath_prepend(str(scripts))
    monkeypatch.delitem(sys.modules, "breakdown_paths", raising=False)
    stub = types.ModuleType("breakdown_paths")
    stub.require_breakdown_ready = lambda *args, **kwargs: None
    stub.config_or_die = lambda *args, **kwargs: str(paths["config"])
    monkeypatch.setitem(sys.modules, "breakdown_paths", stub)

    argv = [
        "build_expert_inventory.py",
        "--breakdown",
        str(paths["config"].parent),
        "--performance",
        str(paths["performance"]),
        "--attribution",
        str(paths["attribution"]),
        "--out",
        str(paths["out"]),
    ]
    if ep_rank is not None:
        argv += ["--ep-rank", str(ep_rank)]
    monkeypatch.setattr(sys, "argv", argv)

    module = load_script(adapter + "/build_expert_inventory.py", monkeypatch)
    # `main()` re-imports `breakdown_paths` after prepending its own directory to sys.path;
    # the stub is already in sys.modules, so that import resolves to the stub.
    monkeypatch.setitem(sys.modules, "breakdown_paths", stub)
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        assert module.main() == 0
    return captured.getvalue().strip().splitlines()


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("ep_rank", [None, 3])
def test_cli_summary_keeps_the_bucket_split_last(
    adapter, monkeypatch, tmp_path, ep_rank
):
    """`run_pipeline.py` records stdout's LAST line as this stage's status, so the
    `source_only` count must not push the bucket split out of it.

    With `--ep-rank` nothing prints after the summary (`residency_unresolved` is 0), and a
    separate source-only note used to become the recorded status — the operator then read
    prose where `individually measured 0, fused 16, residency unresolved 0, remote 240`
    belonged.
    """
    paths = write_inventory_cli_inputs(tmp_path)
    lines = run_inventory_main(adapter, monkeypatch, paths, ep_rank)

    summary = [line for line in lines if line.startswith("individually measured")]
    assert len(summary) == 1, lines
    # All five buckets on that one line, so no informational line has to follow it.
    # `--ep-rank` turns the 16 resident slots into fused measurements; without it they stay
    # residency_unresolved, which is the pre-existing behaviour this PR does not touch.
    resolved = ep_rank is not None
    for expected in (
        "individually measured 0",
        "fused 16" if resolved else "fused 0",
        "residency unresolved 0" if resolved else "residency unresolved 16",
        "remote 240",
        "source-only 1",
    ):
        assert expected in summary[0], summary[0]
    # The unknown-time caveat survives inline instead of as its own displacing line.
    assert "time_us is null, not 0.0" in summary[0], summary[0]
    assert not [line for line in lines if line.startswith("source-only ")], lines

    if ep_rank is None:
        # Pre-existing behaviour, untouched: the actionable hint stays the last line.
        assert lines[-1].startswith("NOTE the capture does not record ep_rank"), lines
        assert lines[-2] == summary[0], lines
    else:
        assert lines[-1] == summary[0], lines
