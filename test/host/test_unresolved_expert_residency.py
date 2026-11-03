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
"""Expert residency must stay unresolved while the EP mapping is unknown (issue #276).

``build_expert_inventory.py`` needs two independent observations before it can name a
global expert as resident: the local expert count (leading dim of the stacked weight in
a ``GroupedMatmul``) and the rank that produced the capture (``--ep-rank``, which msprof
never records). The baseline asserted an identity from the *complement* instead: with 4
declared and 2 observed locally it called indices 2-3 ``remote_ep_shard`` although a
rank-1 capture holds exactly those two locally, and with no observed topology it called
every expert remote even when ``--ep-rank 0`` was supplied. A negative or out-of-range
rank was accepted as well.

``skills/`` is excluded from ruff / bandit / typos in ``.pre-commit-config.yaml``, so
``test/host`` -- collected by the ``host_ut`` case of ``scripts/run_tests.sh`` -- is the
only gate guarding this. Every adapter copy that ships the script is exercised, so a
second copy cannot drift back into the old behaviour unnoticed.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Every copy of the script in the tree, so a re-added legacy adapter is covered too.
ADAPTERS = tuple(
    sorted(
        str(script.parent.relative_to(ROOT).as_posix())
        for script in ROOT.glob("skills/*/scripts/build_expert_inventory.py")
    )
    + sorted(
        str(script.parent.relative_to(ROOT).as_posix())
        for script in ROOT.glob("skills/*/*/scripts/build_expert_inventory.py")
    )
)


def load_script(adapter, monkeypatch):
    path = ROOT / adapter / "build_expert_inventory.py"
    monkeypatch.syspath_prepend(str(path.parent))
    monkeypatch.delitem(sys.modules, "breakdown_paths", raising=False)
    spec = importlib.util.spec_from_file_location("inventory_under_test", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def attribution(local):
    """Kernel rows whose stacked expert weight reveals ``local`` resident experts."""
    if local is None:
        return {"rows": []}
    return {
        "rows": [
            {
                "op_index": 167,
                "op_type": "GroupedMatmul",
                "input_shapes": [[512, 7168], [local, 128, 448, 16, 32], [local]],
                "output_shapes": [[512, 4096]],
            }
        ]
    }


def performance():
    return {
        "model_id": "host-fixture",
        "report_id": "host-run",
        "representative_step": "15",
        "modules": [
            {
                "node_id": "m/decoder_layers_moe/mlp/routed_experts",
                "time_us": 1602.98,
                "nops": 9,
            }
        ],
    }


def config(routed, shared=0):
    architecture = {"n_routed_experts": routed}
    if shared:
        architecture["n_shared_experts"] = shared
    return {"architecture": architecture}


def build(adapter, monkeypatch, routed=4, local=2, ep_rank=None):
    return load_script(adapter, monkeypatch).build(
        config(routed), performance(), attribution(local), None, ep_rank
    )


def states(inventory):
    return {
        expert["expert_index"]: expert["data_state"]
        for expert in inventory["experts"]
        if expert["kind"] == "routed"
    }


def test_adapters_are_discovered():
    """A silent empty parametrisation would pass every case below without running it."""
    assert ADAPTERS, "no build_expert_inventory.py copy found under skills/"
    assert all(
        (ROOT / adapter / "build_expert_inventory.py").is_file() for adapter in ADAPTERS
    )


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_unknown_rank_asserts_neither_local_nor_remote(adapter, monkeypatch):
    """4 declared, 2 observed, rank unknown: indices 2-3 are rank 1's residents.

    Calling them remote is as fabricated as calling 0-1 local, so all four stay
    ``residency_unresolved`` and no expert is claimed resident.
    """
    inventory = build(adapter, monkeypatch, routed=4, local=2, ep_rank=None)

    assert states(inventory) == {index: "residency_unresolved" for index in range(4)}
    assert inventory["counts"]["remote_ep_shard"] == 0
    assert inventory["counts"]["fused_measured"] == 0
    assert inventory["counts"]["residency_unresolved"] == 4
    parallelism = inventory["expert_parallelism"]
    assert parallelism["resident_expert_indices"] is None
    assert parallelism["ep_rank_validation"] == "not_provided"
    # The observed count is still a fact and must survive; only the identity is unknown.
    assert parallelism["local_routed_experts"] == 2
    assert parallelism["moe_ep_size"] == 2
    assert not any(
        expert["resident_on_profiled_rank"]
        for expert in inventory["experts"]
        if expert["kind"] == "routed"
    )


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_unresolved_experts_carry_no_slot_no_node_and_no_time(adapter, monkeypatch):
    """An unresolved entry must not smuggle an identity in through another field."""
    inventory = build(adapter, monkeypatch, routed=4, local=2, ep_rank=None)

    for expert in inventory["experts"]:
        assert expert["data_state"] == "residency_unresolved"
        assert expert["local_slot"] is None
        assert expert["time_us"] is None
        assert expert["measured_by_node_id"] == []
        # The reason states what is missing, never which expert ran where.
        assert "Weights live on a different" not in expert["reason"]
        assert "--ep-rank" in expert["reason"]


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    "ep_rank, expected",
    [
        (
            0,
            {
                0: "fused_measured",
                1: "fused_measured",
                2: "remote_ep_shard",
                3: "remote_ep_shard",
            },
        ),
        (
            1,
            {
                0: "remote_ep_shard",
                1: "remote_ep_shard",
                2: "fused_measured",
                3: "fused_measured",
            },
        ),
    ],
    ids=["rank0", "rank1"],
)
def test_observed_topology_plus_valid_rank_resolves_the_window(
    adapter, monkeypatch, ep_rank, expected
):
    """Both observations present: rank r owns [r*local, (r+1)*local), and only that."""
    inventory = build(adapter, monkeypatch, routed=4, local=2, ep_rank=ep_rank)

    assert states(inventory) == expected
    parallelism = inventory["expert_parallelism"]
    assert parallelism["resident_expert_indices"] == [ep_rank * 2, ep_rank * 2 + 1]
    assert parallelism["ep_rank_validation"] == "observed_topology"
    # The resolved note is the only one allowed to name indices.
    assert parallelism["identity_note"] == (
        f"Rank {ep_rank} owns global routed experts {ep_rank * 2}-{ep_rank * 2 + 1}."
    )
    slots = [
        expert["local_slot"]
        for expert in inventory["experts"]
        if expert["data_state"] == "fused_measured"
    ]
    assert slots == [0, 1]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_no_observed_topology_leaves_a_supplied_rank_unusable(adapter, monkeypatch):
    """``--ep-rank 0`` without a GroupedMatmul shape must not mark everyone remote."""
    inventory = build(adapter, monkeypatch, routed=4, local=None, ep_rank=0)

    assert states(inventory) == {index: "residency_unresolved" for index in range(4)}
    assert inventory["counts"]["remote_ep_shard"] == 0
    parallelism = inventory["expert_parallelism"]
    assert parallelism["local_routed_experts"] is None
    assert parallelism["moe_ep_size"] is None
    assert parallelism["ep_rank"] == 0
    assert parallelism["ep_rank_validation"] == "unverified_without_topology"
    assert parallelism["resident_expert_indices"] is None


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_rank_beyond_an_underivable_topology_is_not_honoured(adapter, monkeypatch):
    """3 declared against 2 observed gives no moe_ep_size, so no window can be located."""
    inventory = build(adapter, monkeypatch, routed=3, local=2, ep_rank=1)

    assert inventory["expert_parallelism"]["moe_ep_size"] is None
    assert states(inventory) == {index: "residency_unresolved" for index in range(3)}
    assert inventory["counts"]["remote_ep_shard"] == 0
    # The NOTE line the CLI prints (and the UI reads) must name the same obstruction as the
    # per-expert reason. It used to fall through to "this capture establishes no
    # expert-parallel topology" -- the opposite of the fact, since a topology WAS observed
    # and merely does not divide -- while every expert's reason said the counts are not a
    # multiple. One inventory, two contradictory explanations.
    note = inventory["expert_parallelism"]["identity_note"]
    reason = next(e["reason"] for e in inventory["experts"] if e["kind"] == "routed")
    assert "not a multiple" in reason
    assert "not a multiple" in note
    assert "establishes no expert-parallel" not in note


# routed, local, ep_rank, expected case, what the note must say, what the reason must say,
# and the neighbouring case's wording the note must NOT borrow.
RESIDENCY_CASES = [
    pytest.param(
        4,
        2,
        None,
        "rank_missing",
        "does not record ep_rank",
        "does not record which expert-parallel rank",
        "not a multiple",
        id="rank-missing",
    ),
    pytest.param(
        4,
        None,
        0,
        "topology_missing",
        "establishes no expert-parallel topology",
        "observed no stacked expert weight shape",
        "not a multiple",
        id="topology-missing",
    ),
    pytest.param(
        3,
        2,
        1,
        "not_divisible",
        "not a multiple",
        "not a multiple",
        "establishes no expert-parallel topology",
        id="not-divisible",
    ),
    pytest.param(
        4,
        0,
        0,
        "zero_local",
        "observes no routed expert",
        "leading dimension is 0",
        "not a multiple",
        id="zero-local-rank",
    ),
    pytest.param(
        4,
        0,
        None,
        "zero_local",
        "observes no routed expert",
        "leading dimension is 0",
        "not a multiple",
        id="zero-local-no-rank",
    ),
]


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    "routed, local, ep_rank, case, note_says, reason_says, note_must_not_say",
    RESIDENCY_CASES,
)
def test_identity_note_and_reason_describe_the_same_case(
    adapter,
    monkeypatch,
    routed,
    local,
    ep_rank,
    case,
    note_says,
    reason_says,
    note_must_not_say,
):
    """Both human-readable residency fields branch on one classification of the capture.

    ``identity_note`` is the CLI's NOTE line and a field the UI reads, while ``reason`` is
    per expert; they used to branch independently and their branch sets did not match, so
    one inventory could explain itself two contradictory ways. Every unresolved case must
    keep both fields on the same explanation and leave every expert unresolved.
    """
    module = load_script(adapter, monkeypatch)
    inventory = module.build(
        config(routed), performance(), attribution(local), None, ep_rank
    )

    parallelism = inventory["expert_parallelism"]
    assert (
        module.residency_case(ep_rank, local, parallelism["moe_ep_size"], routed)
        == case
    ), parallelism
    assert parallelism["resident_expert_indices"] is None
    assert states(inventory) == {
        index: "residency_unresolved" for index in range(routed)
    }
    assert inventory["counts"]["remote_ep_shard"] == 0

    note = parallelism["identity_note"]
    reason = next(e["reason"] for e in inventory["experts"] if e["kind"] == "routed")
    assert note_says in note, note
    assert note_must_not_say not in note, note
    assert reason_says in reason, reason


# declared routed count, ep_rank. Both a missing and a zero count reach the same case.
NO_ROUTED_DECLARED = [
    pytest.param(None, None, id="count-missing-no-rank"),
    pytest.param(None, 0, id="count-missing-rank0"),
    pytest.param(0, None, id="count-zero-no-rank"),
    pytest.param(0, 0, id="count-zero-rank0"),
]


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("declared_routed, ep_rank", NO_ROUTED_DECLARED)
def test_no_declared_routed_count_never_asserts_a_multiple(
    adapter, monkeypatch, declared_routed, ep_rank
):
    """No routed count means no divisibility operands, so neither field may claim any.

    ``residency_case`` used to fall through to ``not_divisible`` here, and both
    human-readable fields then rendered Python's ``None`` — or a literal ``0`` — into an
    assertion about a multiple relation nobody could evaluate: "None declared routed
    experts are not a multiple of the 2 observed locally". ``identity_note`` is the CLI's
    NOTE line and Skill 3 packs it into the report, so that wording reaches users even
    when no routed expert exists to carry a per-expert ``reason``.
    """
    module = load_script(adapter, monkeypatch)

    case = module.residency_case(ep_rank, 2, None, declared_routed)
    assert case == "no_routed_declared", case
    note = module.identity_note(case, ep_rank, 2, declared_routed)
    reason = module.unresolved_reason(case, ep_rank, 2, declared_routed)
    for field in (note, reason):
        assert "None" not in field, field
        assert "not a multiple" not in field, field
        if declared_routed is None:
            assert "n_routed_experts" in field, field
        else:
            assert "declares 0 routed experts" in field, field
    if ep_rank is None:
        assert "--ep-rank" not in note, note
    else:
        assert f"--ep-rank {ep_rank} was supplied" in note, note

    # Through ``build``: no routed expert exists, so nothing is left unresolved and the
    # note in the inventory is the same sentence the helper produced.
    architecture = {"n_shared_experts": 1}
    if declared_routed is not None:
        architecture["n_routed_experts"] = declared_routed
    inventory = module.build(
        {"architecture": architecture}, performance(), attribution(2), None, ep_rank
    )
    assert [e for e in inventory["experts"] if e["kind"] == "routed"] == []
    assert inventory["counts"]["residency_unresolved"] == 0
    assert inventory["counts"]["remote_ep_shard"] == 0
    parallelism = inventory["expert_parallelism"]
    assert parallelism["moe_ep_size"] is None
    assert parallelism["resident_expert_indices"] is None
    assert parallelism["identity_note"] == note, parallelism["identity_note"]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_disagreeing_shapes_are_reported_as_unknown_not_as_an_error(
    adapter, tmp_path, monkeypatch
):
    """Conflicting local expert counts exit 0 and still write an honest inventory.

    Two ``GroupedMatmul`` kernels whose stacked weights carry different leading
    dimensions mean the layers do not share one EP topology, so no single count is
    right. That is deliberately not one of the two non-zero exits the pipeline treats
    as a caller error (readiness gate, impossible ``--ep-rank``): failing here would
    discard a capture that can still say "unknown", which is a result this run is
    allowed to report. Pinning it here keeps the docstring's claim about the exit
    codes tied to the real CLI instead of to whoever last read it.
    """
    breakdown = tmp_path / "breakdown"
    breakdown.mkdir()
    write_formal_breakdown(breakdown)
    perf_path = tmp_path / "perf_data.json"
    perf_path.write_text(json.dumps(performance()), encoding="utf-8")
    conflicting = {
        "rows": [
            {
                "op_index": 167,
                "op_type": "GroupedMatmul",
                "input_shapes": [[512, 7168], [2, 128, 448, 16, 32], [2]],
                "output_shapes": [[512, 4096]],
            },
            {
                "op_index": 211,
                "op_type": "GroupedMatmul",
                "input_shapes": [[512, 7168], [3, 128, 448, 16, 32], [3]],
                "output_shapes": [[512, 4096]],
            },
        ]
    }
    attribution_path = tmp_path / "kernel_attribution.json"
    attribution_path.write_text(json.dumps(conflicting), encoding="utf-8")
    out_path = tmp_path / "expert_inventory.json"

    command = [
        sys.executable,
        str(ROOT / adapter / "build_expert_inventory.py"),
        "--breakdown",
        str(breakdown),
        "--performance",
        str(perf_path),
        "--attribution",
        str(attribution_path),
        "--out",
        str(out_path),
        # An unusable rank is accepted here: with no local count there is no topology
        # to bound it, so nothing can be called impossible.
        "--ep-rank",
        "5",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert out_path.is_file()

    inventory = json.loads(out_path.read_text(encoding="utf-8"))
    parallelism = inventory["expert_parallelism"]
    assert parallelism["local_routed_experts"] is None
    assert parallelism["moe_ep_size"] is None
    assert parallelism["ep_rank_validation"] == "unverified_without_topology"
    assert parallelism["resident_expert_indices"] is None
    assert "disagree" in parallelism["residency_evidence"], parallelism
    assert states(inventory) == {index: "residency_unresolved" for index in range(4)}
    assert inventory["counts"]["remote_ep_shard"] == 0
    assert inventory["counts"]["residency_unresolved"] == 4

    # And the pipeline reads that real exit as a produced inventory, not as a failure.
    pipeline = load_pipeline(adapter, monkeypatch)
    outcome, detail = pipeline.inventory_stage_outcome(
        result.returncode, result.stdout, result.stderr, str(out_path)
    )
    assert outcome == "ok", detail
    assert not detail.startswith("skipped"), detail


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_impossible_ranks_are_rejected(adapter, monkeypatch):
    """Negative ranks never exist; a rank at or beyond moe_ep_size names no shard."""
    module = load_script(adapter, monkeypatch)

    with pytest.raises(ValueError, match="negative"):
        module.build(config(4), performance(), attribution(2), None, -1)
    with pytest.raises(ValueError, match="outside the observed"):
        module.build(config(4), performance(), attribution(2), None, 2)
    with pytest.raises(ValueError, match="outside the observed"):
        module.build(config(4), performance(), attribution(2), None, 99)
    # A negative rank is rejected even when no topology was observed to bound it.
    with pytest.raises(ValueError, match="negative"):
        module.build(config(4), performance(), attribution(None), None, -3)
    # The highest existing rank is still accepted.
    assert module.build(config(4), performance(), attribution(2), None, 1)[
        "expert_parallelism"
    ]["resident_expert_indices"] == [2, 3]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_buckets_still_partition_every_declared_expert(adapter, monkeypatch):
    """The UI totals add up only if each expert lands in exactly one bucket."""
    for routed, local, ep_rank in [
        (4, 2, None),
        (4, 2, 1),
        (4, None, 0),
        (256, 16, 5),
        (256, 16, None),
    ]:
        inventory = build(
            adapter, monkeypatch, routed=routed, local=local, ep_rank=ep_rank
        )
        counts = inventory["counts"]
        assert len(inventory["experts"]) == routed
        assert (
            counts["individually_measured"]
            + counts["fused_measured"]
            + counts["residency_unresolved"]
            + counts["remote_ep_shard"]
        ) == len(inventory["experts"])
        assert (
            counts["residency_unresolved"]
            + counts["remote_ep_shard"]
            + counts["fused_measured"]
            == routed
        )
        assert all(value >= 0 for value in counts.values())


def write_formal_breakdown(directory):
    """The five formal Skill 1 files, so the CLI gate is reached before rank parsing."""
    config_path = directory / "analysis_config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "architecture": {"n_routed_experts": 4},
                "trace_scope": {"kind": "unknown"},
                "structures": {},
                "stages": {},
                "runtime_auxiliary": [],
                "unmapped_ops": [],
            }
        ),
        encoding="utf-8",
    )
    (directory / "validation_report.json").write_text(
        json.dumps({"status": "passed", "issues": []}), encoding="utf-8"
    )
    (directory / "critique_report.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "passed",
                "artifacts": {
                    "analysis_config": {
                        "path": str(config_path),
                        "sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (directory / "critique_validation.json").write_text(
        json.dumps(
            {"status": "passed", "error_count": 0, "detail": {"clears_candidate": True}}
        ),
        encoding="utf-8",
    )
    (directory / "breakdown_score.json").write_text(
        json.dumps(
            {
                "status": "verified",
                "passed_at_cap": True,
                "convertible": True,
                "hard_gates": {"passed": True, "blocking_issues": []},
                "critique_gates": {"passed": True, "blocking_issues": []},
            }
        ),
        encoding="utf-8",
    )
    return config_path


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    "ep_rank, expect_ok",
    [(None, True), (1, True), (-1, False), (2, False)],
    ids=["no-rank", "rank1", "negative-rank", "out-of-range-rank"],
)
def test_cli_rejects_impossible_ranks_instead_of_writing_them(
    adapter, tmp_path, ep_rank, expect_ok
):
    """Through the real CLI: an impossible rank exits non-zero and writes no inventory."""
    breakdown = tmp_path / "breakdown"
    breakdown.mkdir()
    write_formal_breakdown(breakdown)
    perf_path = tmp_path / "perf_data.json"
    perf_path.write_text(json.dumps(performance()), encoding="utf-8")
    attribution_path = tmp_path / "kernel_attribution.json"
    attribution_path.write_text(json.dumps(attribution(2)), encoding="utf-8")
    out_path = tmp_path / "expert_inventory.json"

    command = [
        sys.executable,
        str(ROOT / adapter / "build_expert_inventory.py"),
        "--breakdown",
        str(breakdown),
        "--performance",
        str(perf_path),
        "--attribution",
        str(attribution_path),
        "--out",
        str(out_path),
    ]
    if ep_rank is not None:
        command += ["--ep-rank", str(ep_rank)]
    result = subprocess.run(command, capture_output=True, text=True)

    assert (result.returncode == 0) is expect_ok, result.stdout + result.stderr
    assert out_path.is_file() is expect_ok
    if not expect_ok:
        assert "ERROR" in result.stderr
        return
    inventory = json.loads(out_path.read_text(encoding="utf-8"))
    assert inventory["counts"]["remote_ep_shard"] == (2 if ep_rank is not None else 0)
    assert inventory["counts"]["residency_unresolved"] == (
        0 if ep_rank is not None else 4
    )


def write_validator_facts(directory):
    """The fact files ``validate_conversion.py`` needs beside the inventory."""
    identity = {
        "model_id": "host-fixture",
        "report_id": "host-run",
        "representative_step": 0,
    }
    node = {"node_id": "model/layer/shared_expert", "mapped_kernels": 1}
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
    performance_facts = {**identity, "modules": [record]}
    timeline = {
        **identity,
        "events": [{"owner_node_id": node["node_id"], "op_index": 0}],
    }
    for suffix, value in (
        ("analysis_config", analysis),
        ("perf_data", performance_facts),
        ("timeline", timeline),
    ):
        (directory / f"fixture_{suffix}.json").write_text(
            json.dumps(value), encoding="utf-8"
        )
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
    (directory / "outputs").mkdir(exist_ok=True)
    (directory / "outputs/model_architecture_graph.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    return performance_facts


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    "assert_remote", [False, True], ids=["clean", "asserted-remote"]
)
def test_validator_rejects_a_remote_claim_without_a_resolved_window(
    adapter, assert_remote, tmp_path, monkeypatch
):
    """The mirror guard: an unresolved inventory must not call anyone remote."""
    write_validator_facts(tmp_path)
    perf_facts = json.loads(
        (tmp_path / "fixture_perf_data.json").read_text(encoding="utf-8")
    )
    module = load_script(adapter, monkeypatch)
    inventory = module.build(
        {"architecture": {"n_routed_experts": 4, "n_shared_experts": 1}},
        perf_facts,
        attribution(2),
        None,
        None,
    )
    assert inventory["expert_parallelism"]["resident_expert_indices"] is None
    assert inventory["counts"]["remote_ep_shard"] == 0
    if assert_remote:
        routed = next(e for e in inventory["experts"] if e["kind"] == "routed")
        routed["data_state"] = "remote_ep_shard"
        inventory["counts"]["residency_unresolved"] -= 1
        inventory["counts"]["remote_ep_shard"] += 1
    assert all(value >= 0 for value in inventory["counts"].values())
    (tmp_path / "fixture_expert_inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )

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

    assert (result.returncode != 0) is assert_remote, result.stdout + result.stderr
    if assert_remote:
        assert "no expert is asserted remote" in result.stdout


def recount(inventory):
    """Recompute ``counts`` from the expert list, mirroring the generator.

    A mutation fixture that leaves the counters stale would trip the bucket-sum check and
    pass for the wrong reason; the validator's residency verdicts must be what fail.
    """
    experts = inventory["experts"]
    counts = inventory["counts"]
    counts["resident_on_profiled_rank"] = sum(
        1 for e in experts if e["resident_on_profiled_rank"]
    )
    for key in (
        "individually_measured",
        "fused_measured",
        "residency_unresolved",
        "remote_ep_shard",
        "source_only",
    ):
        state = "measured" if key == "individually_measured" else key
        counts[key] = sum(1 for e in experts if e["data_state"] == state)
    return inventory


def routed_expert(inventory, index):
    return next(
        e
        for e in inventory["experts"]
        if e["kind"] == "routed" and e["expert_index"] == index
    )


def forge_window(inventory):
    """The bypass the review named: a window the capture never observed, but self-consistent
    enough to satisfy a validator that trusts ``resident_expert_indices``.

    The capture observed no GroupedMatmul, so the topology is unknown and the generator
    honestly wrote ``unverified_without_topology`` with a null window. A stale generator or a
    hand edit can keep that verdict while filling the window in: indices 0/1 resident, 2/3
    remote, and every downstream number derived from the fabrication.
    """
    parallelism = inventory["expert_parallelism"]
    assert parallelism["ep_rank_validation"] == "unverified_without_topology"
    assert parallelism["resident_expert_indices"] is None
    assert parallelism["local_routed_experts"] is None
    parallelism["resident_expert_indices"] = [0, 1]
    for index in (0, 1):
        expert = routed_expert(inventory, index)
        expert["data_state"] = "fused_measured"
        expert["local_slot"] = index
        expert["resident_on_profiled_rank"] = True
    for index in (2, 3):
        expert = routed_expert(inventory, index)
        expert["data_state"] = "remote_ep_shard"
        expert["resident_on_profiled_rank"] = False
    return recount(inventory)


def shift_window(inventory):
    """A resolved inventory whose window contradicts its own rank arithmetic."""
    parallelism = inventory["expert_parallelism"]
    assert parallelism["ep_rank_validation"] == "observed_topology"
    assert parallelism["resident_expert_indices"] == [2, 3]
    parallelism["resident_expert_indices"] = [0, 1]
    return inventory


def contradict_window(inventory):
    """Window arithmetic intact, per-expert states swapped across it."""
    parallelism = inventory["expert_parallelism"]
    assert parallelism["resident_expert_indices"] == [2, 3]
    for index, state in ((0, "fused_measured"), (2, "remote_ep_shard")):
        expert = routed_expert(inventory, index)
        expert["data_state"] = state
        expert["resident_on_profiled_rank"] = state == "fused_measured"
    return recount(inventory)


def drop_validation_field(inventory):
    """An inventory from before ``ep_rank_validation`` existed, still claiming identities."""
    del inventory["expert_parallelism"]["ep_rank_validation"]
    return inventory


def swap_identities(inventory):
    """Routed ids paired with another expert's index — the states stay window-consistent.

    The generator writes ``routed/{i}`` with ``expert_index i`` as a bijection; a hand edit
    that swaps the ids of an in-window and an out-of-window expert keeps every per-state
    bucket balanced and every state on the right side of the window, so the window checks
    place the wrong expert without noticing: the counts partition holds because it counts
    states, not identities.
    """
    first, second = routed_expert(inventory, 0), routed_expert(inventory, 2)
    first["expert_id"], second["expert_id"] = second["expert_id"], first["expert_id"]
    return inventory


def crush_indices(inventory):
    """Every routed expert collapsed onto one window-internal index.

    Duplicating ``expert_index`` for every expert keeps the state buckets balanced while the
    window checks see every expert inside the window: ``seen`` never had to be a permutation
    of ``0..declared-1`` before the identity check existed.
    """
    parallelism = inventory["expert_parallelism"]
    low = parallelism["resident_expert_indices"][0]
    for expert in inventory["experts"]:
        if expert["kind"] == "routed":
            expert["expert_index"] = low
    return inventory


def shift_one_index(inventory):
    """One expert moved onto another's index — exactly enough detail to fill the truncation.

    Two per-expert problems plus the summary make three lines, the most a truncated tail
    prints, so a summary left at the end still shows — in the wrong place — and a summary
    prepended without being lifted from the tail shows twice. Larger relabels hide behind
    ``(N more)`` instead, which is why this small one guards the ordering.
    """
    routed_expert(inventory, 2)["expert_index"] = 1
    return inventory


def forge_wrong_window(inventory):
    """A resolved inventory whose window contradicts the rank arithmetic in several ways.

    The four contradictions this fixture produces are also the construction's maximum, and
    the last one — ``rank r holding local experts owns [..]`` — is the only line that says
    what the correct window is. The bounded list must print all four, not three plus
    ``(1 more)`` dropping exactly that line. The declared count is set to 5 on purpose: a
    count not divisible by the local one adds the "not a multiple" contradiction, and it
    takes all four to exceed the old three-line truncation.

    It also breaks the index set the way a lift-and-prepend bug shows: the four listed
    experts keep self-consistent ids and indices, so the identity check emits only its
    summary line, which a summary left inside the truncated tail printed twice verbatim.
    """
    parallelism = inventory["expert_parallelism"]
    assert parallelism["ep_rank_validation"] == "observed_topology"
    assert parallelism["resident_expert_indices"] == [2, 3]
    inventory["declared"]["routed_experts"] = 5
    inventory["declared"]["total"] = 6
    parallelism["ep_rank"] = 5
    parallelism["moe_ep_size"] = 2
    parallelism["resident_expert_indices"] = [8, 9]
    return inventory


def forge_separable_time(inventory):
    """A routed expert relabelled ``measured`` with a time the profiler never reported.

    The generator can only label a routed expert ``fused_measured`` / ``remote_ep_shard`` /
    ``residency_unresolved`` — its work is fused inside one GroupedMatmul, so a separable
    per-expert time never exists for it. Inside the window this dodged both guards once:
    the no-per-expert-time check exempts ``measured``, and the window-state check tested
    only "inside yet remote" and "outside yet local", so a fabricated ``time_us`` sailed
    through into the UI.
    """
    parallelism = inventory["expert_parallelism"]
    assert parallelism["resident_expert_indices"] == [2, 3]
    expert = routed_expert(inventory, 2)
    assert expert["data_state"] == "fused_measured"
    expert["data_state"] = "measured"
    expert["time_us"] = 7.0
    return recount(inventory)


def bury_unresolved_signal(inventory):
    """Every routed expert relabelled ``source_only`` on an unresolved inventory.

    The twin of ``forge_separable_time``: the guard used to live inside
    ``window_state_problems`` and only ran against a resolved window, while the
    unresolved branch compared only the local/remote states — ``source_only`` is
    neither, so the relabelling passed and replaced the honest "pass --ep-rank"
    reason with a wrong "no kernel attributed" one.
    """
    parallelism = inventory["expert_parallelism"]
    assert parallelism["ep_rank_validation"] != "observed_topology"
    assert parallelism["resident_expert_indices"] is None
    for expert in inventory["experts"]:
        if expert["kind"] == "routed":
            expert["data_state"] = "source_only"
    return recount(inventory)


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    "local, ep_rank, mutation, expect_ok, expected_message",
    [
        pytest.param(2, None, None, True, "", id="unresolved-clean"),
        pytest.param(2, 1, None, True, "", id="observed-topology-clean"),
        pytest.param(
            None,
            0,
            forge_window,
            False,
            "no expert is asserted remote or resident",
            id="fabricated-window",
        ),
        pytest.param(
            2,
            1,
            shift_window,
            False,
            "resident window follows from ep_rank",
            id="window-contradicts-rank",
        ),
        pytest.param(
            2,
            1,
            contradict_window,
            False,
            "data_state agrees with the resident window",
            id="states-contradict-window",
        ),
        pytest.param(
            2,
            1,
            drop_validation_field,
            False,
            "predates the residency contract",
            id="legacy-inventory-without-validation",
        ),
        pytest.param(
            2,
            1,
            forge_separable_time,
            False,
            "a state only a shared expert can carry",
            id="fabricated-separable-per-expert-time",
        ),
        pytest.param(
            None,
            None,
            bury_unresolved_signal,
            False,
            "a state only a shared expert can carry",
            id="unresolved-window-buried-by-source-only",
        ),
        pytest.param(
            2,
            1,
            swap_identities,
            False,
            "pair routed/<i> with expert_index i",
            id="swapped-expert-identities",
        ),
        pytest.param(
            2,
            1,
            crush_indices,
            False,
            "pair routed/<i> with expert_index i",
            id="duplicated-expert-indices",
        ),
        pytest.param(
            2,
            1,
            shift_one_index,
            False,
            "the routed expert indices are not 0..3",
            id="summary-leads-a-short-identity-list",
        ),
        pytest.param(
            2,
            1,
            forge_wrong_window,
            False,
            "owns [10, 11], not [8, 9]",
            id="window-contradictions-are-all-printed",
        ),
    ],
)
def test_validator_never_takes_the_resident_window_on_faith(
    adapter,
    local,
    ep_rank,
    mutation,
    expect_ok,
    expected_message,
    tmp_path,
    monkeypatch,
):
    """``resident_expert_indices`` is the claim under test, so it cannot vouch for itself."""
    write_validator_facts(tmp_path)
    perf_facts = json.loads(
        (tmp_path / "fixture_perf_data.json").read_text(encoding="utf-8")
    )
    inventory = load_script(adapter, monkeypatch).build(
        {"architecture": {"n_routed_experts": 4, "n_shared_experts": 1}},
        perf_facts,
        attribution(local),
        None,
        ep_rank,
    )
    if mutation is not None:
        inventory = mutation(inventory)
    assert all(value >= 0 for value in inventory["counts"].values())
    (tmp_path / "fixture_expert_inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )

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

    assert (result.returncode == 0) is expect_ok, result.stdout + result.stderr
    if expected_message:
        assert expected_message in result.stdout, result.stdout
        assert any(
            line.startswith("FAIL") and expected_message in line
            for line in result.stdout.splitlines()
        ), result.stdout
    if "pair routed/<i>" in result.stdout:
        # When the bijection summary is emitted at all (the index set is broken, not just
        # the id pairing), it must lead the line — after the per-expert tail, `(N more)`
        # would swallow it on a large relabel — and it must not be printed twice: a list
        # short enough not to truncate used to keep the summary in the tail as well,
        # doubling it verbatim. The summary is conditional (a pure id swap leaves the index
        # set intact and emits none), so the assertions guard only the lines that have it.
        for line in result.stdout.splitlines():
            if not (line.startswith("FAIL") and "pair routed/<i>" in line):
                continue
            if "the routed expert indices" not in line:
                continue
            detail = line.split("— ", 1)[1]
            assert detail.startswith("the routed expert indices"), line
            assert detail.count("the routed expert indices") == 1, line
    if expect_ok and "resident window" in result.stdout:
        # A genuine window must not be rejected by the stricter gate -- otherwise the fix
        # would read as "the validator now fails everything that has an identity".
        assert all(
            line.startswith("PASS")
            for line in result.stdout.splitlines()
            if "resident window" in line
        ), result.stdout


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    "ep_size",
    [
        pytest.param("2", id="string"),
        pytest.param([2], id="list"),
        pytest.param(2.0, id="float"),
        pytest.param(True, id="bool"),
        pytest.param(0, id="zero"),
    ],
)
def test_validator_reports_a_malformed_ep_size_instead_of_raising(
    adapter, ep_size, tmp_path, monkeypatch
):
    """A hand-edited ``moe_ep_size`` is data to report, not an exception to raise.

    The window re-derivation compares ``ep_rank >= ep_size`` and used to reach that
    comparison with whatever type the inventory carried, so ``"2"`` or ``[2]`` raised
    ``TypeError`` before the result-printing loop ran. The validator then died with empty
    stdout, and the pipeline -- which reports stdout -- showed the operator an empty
    message for an inventory that simply had a bad field in it.
    """
    write_validator_facts(tmp_path)
    perf_facts = json.loads(
        (tmp_path / "fixture_perf_data.json").read_text(encoding="utf-8")
    )
    inventory = load_script(adapter, monkeypatch).build(
        {"architecture": {"n_routed_experts": 4, "n_shared_experts": 1}},
        perf_facts,
        attribution(2),
        None,
        1,
    )
    assert inventory["expert_parallelism"]["ep_rank_validation"] == "observed_topology"
    inventory["expert_parallelism"]["moe_ep_size"] = ep_size
    (tmp_path / "fixture_expert_inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )

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
    assert "Traceback" not in result.stderr, result.stderr
    # The failure is legible on stdout, where the pipeline reads it.
    assert result.stdout.strip(), result.stderr
    assert any(
        line.startswith("FAIL") and "moe_ep_size" in line
        for line in result.stdout.splitlines()
    ), result.stdout
    # Reported as the malformed count it is, not as some arithmetic it cannot take part in.
    assert "is not a positive count" in result.stdout, result.stdout


# Adapters that ship the documented pipeline entry point as well as the inventory script.
PIPELINE_ADAPTERS = tuple(
    adapter for adapter in ADAPTERS if (ROOT / adapter / "run_pipeline.py").is_file()
)


def load_pipeline(adapter, monkeypatch):
    """``run_pipeline.py`` as a module, so its stage decisions can be called directly."""
    path = ROOT / adapter / "run_pipeline.py"
    monkeypatch.syspath_prepend(str(path.parent))
    monkeypatch.delitem(sys.modules, "breakdown_paths", raising=False)
    spec = importlib.util.spec_from_file_location("pipeline_under_test", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_pipeline_adapters_are_discovered():
    """An empty ``PIPELINE_ADAPTERS`` would silently skip every pipeline case below."""
    assert PIPELINE_ADAPTERS, (
        "no run_pipeline.py copy found beside the inventory script"
    )


@pytest.mark.parametrize("adapter", PIPELINE_ADAPTERS)
def test_pipeline_refuses_to_read_an_inventory_error_as_a_skip(
    adapter, monkeypatch, tmp_path
):
    """A non-zero inventory exit is a caller error, not "no MoE experts here".

    The pipeline used to record ``skipped: ERROR ...`` and carry on. Without the inventory
    file the overlay drops ``expertInventory``, the conversion validator has nothing to
    gate, every MoE residency check stops running, and the run still exits 0 with a
    complete-looking report that merely lacks the expert panel -- one mistyped
    ``--ep-rank`` buying a report that reads as normal.
    """
    module = load_pipeline(adapter, monkeypatch)
    absent = str(tmp_path / "fixture_expert_inventory.json")

    outcome, detail = module.inventory_stage_outcome(
        2,
        "",
        "ERROR --ep-rank 5 is outside the observed expert-parallel topology "
        "(moe_ep_size=2, valid ranks 0-1)\n",
        absent,
    )
    assert outcome == "failed"
    assert "--ep-rank 5 is outside the observed expert-parallel topology" in detail
    assert not detail.startswith("skipped"), detail

    # A crash that explains nothing must still fail with a message, never silently.
    outcome, detail = module.inventory_stage_outcome(1, "", "", absent)
    assert outcome == "failed"
    assert detail.strip(), detail


@pytest.mark.parametrize("adapter", PIPELINE_ADAPTERS)
def test_pipeline_keeps_the_dense_model_skip(adapter, monkeypatch, tmp_path):
    """Exit 0 with no inventory file is the one legitimate skip, and it stays one."""
    module = load_pipeline(adapter, monkeypatch)
    absent = str(tmp_path / "fixture_expert_inventory.json")

    outcome, detail = module.inventory_stage_outcome(
        0, "no MoE experts declared in this model; nothing to inventory\n", "", absent
    )
    assert outcome == "ok"
    assert detail.startswith("skipped: "), detail
    assert "no MoE experts declared" in detail

    written = tmp_path / "fixture_expert_inventory.json"
    written.write_text("{}", encoding="utf-8")
    outcome, detail = module.inventory_stage_outcome(
        0, "WROTE x\nremote 0\nresidency unresolved 4\n", "", str(written)
    )
    assert outcome == "ok"
    assert detail == "residency unresolved 4"


class _PipelineStopped(Exception):
    """Stands in for ``run_pipeline.die`` so the stopping stage can be asserted."""

    def __init__(self, stage, message):
        super().__init__(stage)
        self.stage = stage
        self.message = message


@pytest.mark.parametrize("adapter", PIPELINE_ADAPTERS)
def test_pipeline_main_stops_at_the_inventory_stage(adapter, monkeypatch, tmp_path):
    """``main()`` really does stop there: no graph, no overlay, no report after a bad rank."""
    module = load_pipeline(adapter, monkeypatch)
    breakdown = tmp_path / "breakdown"
    breakdown.mkdir()
    (breakdown / "raw_ops.json").write_text("[]", encoding="utf-8")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(" ".join(str(part) for part in cmd))
        if "build_expert_inventory.py" in calls[-1]:
            return subprocess.CompletedProcess(
                cmd,
                2,
                "",
                "ERROR --ep-rank 5 is outside the observed expert-parallel topology "
                "(moe_ep_size=2, valid ranks 0-1)\n",
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(
        module,
        "die",
        lambda status, stage, message, **extra: _raise_stop(stage, message),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--breakdown",
            str(breakdown),
            "--model-id",
            "fixture",
            "--out",
            str(tmp_path / "out"),
            "--ep-rank",
            "5",
        ],
    )

    with pytest.raises(_PipelineStopped) as stopped:
        module.main()

    assert stopped.value.stage == "expert_inventory"
    assert "--ep-rank 5" in stopped.value.message
    inventory_call = next(call for call in calls if "build_expert_inventory.py" in call)
    assert "--ep-rank 5" in inventory_call
    # Nothing downstream of the refused inventory ran.
    assert not any("build_architecture_graph.py" in call for call in calls), calls
    assert not any("validate_conversion.py" in call for call in calls), calls


def _raise_stop(stage, message):
    raise _PipelineStopped(stage, message)
