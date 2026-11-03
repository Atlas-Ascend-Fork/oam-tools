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
#
"""MoE expert inventory: all declared experts listed, none given fabricated per-expert time."""
import os
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)
import build_expert_inventory as bei  # noqa: E402


def manifest(routed=256, shared=1, top_k=8):
    facts = []
    if routed is not None:
        facts.append({"key": "n_routed_experts", "value": routed, "source_ref": "cfg.py:128"})
    if shared is not None:
        facts.append({"key": "n_shared_experts", "value": shared, "source_ref": "cfg.py:127"})
    if top_k is not None:
        facts.append({"key": "num_experts_per_tok", "value": top_k, "source_ref": "cfg.py:139"})
    return {"facts": facts}


def attribution(local=16):
    """One GroupedMatmul whose stacked weight leading dim is the local expert count."""
    return {"rows": [{
        "op_index": 167,
        "op_type": "GroupedMatmul",
        # activation, stacked weight (fractal-Z quantised), group_list
        "input_shapes": [[512, 7168], [local, 128, 448, 16, 32], [local]],
        "output_shapes": [[512, 4096]],
    }]}


def performance(routed_time=1602.98, shared_time=309.66):
    modules = []
    if routed_time is not None:
        modules.append({"node_id": "m/decoder_layers_moe/mlp/routed_experts",
                        "time_us": routed_time, "nops": 9})
    if shared_time is not None:
        modules.append({"node_id": "m/decoder_layers_moe/mlp/shared_expert",
                        "time_us": shared_time, "nops": 12})
    return {"model_id": "m", "report_id": "r", "representative_step": "15",
            "modules": modules}


def test_lists_every_declared_expert():
    """257 = 256 routed + 1 shared. All are declared, regardless of what was measured."""
    inv = bei.build({}, performance(), attribution(), manifest(), ep_rank=0)
    assert inv["declared"]["total"] == 257
    assert len(inv["experts"]) == 257
    assert sum(1 for e in inv["experts"] if e["kind"] == "routed") == 256
    assert sum(1 for e in inv["experts"] if e["kind"] == "shared") == 1


def test_ep_size_derived_from_weight_shape_not_assumed():
    """256 declared with a 16-wide stacked weight means EP=16, observed from the capture."""
    inv = bei.build({}, performance(), attribution(local=16), manifest(), ep_rank=0)
    parallelism = inv["expert_parallelism"]
    assert parallelism["local_routed_experts"] == 16
    assert parallelism["moe_ep_size"] == 16
    assert "leading dim" in parallelism["residency_evidence"]


def test_remote_experts_get_no_time_and_are_not_zero():
    """240 experts on other ranks are unknown, not idle. Zero would read as a measurement."""
    inv = bei.build({}, performance(), attribution(), manifest(), ep_rank=0)
    remote = [e for e in inv["experts"] if e["data_state"] == "remote_ep_shard"]
    assert len(remote) == 240
    assert all(e["time_us"] is None for e in remote)
    assert all(e["measured_by_node_id"] == [] for e in remote)


def test_fused_experts_carry_no_per_expert_time():
    """The 16 resident experts share one GroupedMatmul; splitting it would invent numbers."""
    inv = bei.build({}, performance(), attribution(), manifest(), ep_rank=0)
    fused = [e for e in inv["experts"] if e["data_state"] == "fused_measured"]
    assert len(fused) == 16
    assert all(e["time_us"] is None for e in fused)
    # They do point at the node that owns the real measurement, so the figure is findable.
    assert all(e["measured_by_node_id"] for e in fused)
    assert inv["measurability"]["separable_per_expert"] is False


def test_shared_expert_is_genuinely_measured():
    """Not EP-sharded and not fused, so it is the one expert with a real per-expert time."""
    inv = bei.build({}, performance(), attribution(), manifest(), ep_rank=0)
    shared = [e for e in inv["experts"] if e["kind"] == "shared"]
    assert len(shared) == 1
    assert shared[0]["data_state"] == "measured"
    assert shared[0]["time_us"] == pytest.approx(309.66)


def test_without_ep_rank_no_identity_is_claimed():
    """The capture does not record ep_rank; asserting experts 0-15 ran would be a guess.

    Rank 5 owns 80-95. The count is observable from the weight shape, the identity is not —
    and neither is its complement, so the other 240 must not be labelled remote either.
    """
    inv = bei.build({}, performance(), attribution(), manifest(), ep_rank=None)
    assert inv["expert_parallelism"]["resident_expert_indices"] is None
    assert inv["counts"]["fused_measured"] == 0
    assert inv["counts"]["residency_unresolved"] == 256
    assert inv["counts"]["remote_ep_shard"] == 0
    assert not any(e["resident_on_profiled_rank"] for e in inv["experts"]
                   if e["kind"] == "routed")


def test_ep_rank_resolves_the_resident_window():
    inv = bei.build({}, performance(), attribution(), manifest(), ep_rank=5)
    assert inv["expert_parallelism"]["resident_expert_indices"] == [80, 95]
    fused = [e for e in inv["experts"] if e["data_state"] == "fused_measured"]
    assert [fused[0]["expert_index"], fused[-1]["expert_index"]] == [80, 95]
    assert [fused[0]["local_slot"], fused[-1]["local_slot"]] == [0, 15]


def test_buckets_partition_the_expert_list():
    """Every expert lands in exactly one state, or the UI's totals will not add up."""
    inv = bei.build({}, performance(), attribution(), manifest(), ep_rank=0)
    counts = inv["counts"]
    assert (counts["individually_measured"] + counts["fused_measured"]
            + counts["residency_unresolved"] + counts["remote_ep_shard"]
            + counts["source_only"]) == len(inv["experts"])


def test_source_only_shared_expert_is_counted_and_still_partitions():
    """An unobserved shared expert is a legal state; without its bucket the sum falls short.

    This is the inventory `validate_conversion.py` rejected: 1 shared expert declared, none
    observed, so the four measured/unresolved buckets summed to 0 while 1 expert was listed.
    """
    inv = bei.build({}, performance(shared_time=None), attribution(), manifest(), ep_rank=0)
    counts = inv["counts"]
    assert counts["source_only"] == 1
    shared = [e for e in inv["experts"] if e["kind"] == "shared"][0]
    assert shared["data_state"] == "source_only"
    assert shared["time_us"] is None
    assert (counts["individually_measured"] + counts["fused_measured"]
            + counts["residency_unresolved"] + counts["remote_ep_shard"]
            + counts["source_only"]) == len(inv["experts"])


def test_declared_total_never_taken_from_kernel_shapes():
    """Shapes show only this rank's 16. Reading the total from them under-reports by EP."""
    inv = bei.build({}, performance(), attribution(local=16), manifest(routed=256), ep_rank=0)
    assert inv["declared"]["routed_experts"] == 256
    assert inv["declared"]["source_refs"]["n_routed_experts"] == "cfg.py:128"


def test_disagreeing_grouped_kernels_refuse_to_pick_a_count():
    """Two different local counts mean the layers do not share one EP topology."""
    rows = attribution(local=16)["rows"] + attribution(local=8)["rows"]
    inv = bei.build({}, performance(), {"rows": rows}, manifest(), ep_rank=0)
    assert inv["expert_parallelism"]["local_routed_experts"] is None
    assert "disagree" in inv["expert_parallelism"]["residency_evidence"]


def test_no_grouped_kernel_leaves_residency_unknown():
    """A capture with no expert GEMM cannot establish residency; say so, do not default to all."""
    inv = bei.build({}, performance(), {"rows": []}, manifest(), ep_rank=0)
    assert inv["expert_parallelism"]["local_routed_experts"] is None
    assert inv["expert_parallelism"]["moe_ep_size"] is None
    # Still lists all 257 from the source; none can be claimed resident.
    assert len(inv["experts"]) == 257
    # A supplied rank without an observed topology resolves nothing: claiming all 256 routed
    # experts live on other ranks would assert a residency the capture never established.
    assert inv["counts"]["remote_ep_shard"] == 0
    assert inv["counts"]["residency_unresolved"] == 256


def test_unmeasured_shared_expert_reports_source_only():
    """Declared but with no attributed kernel is source_only, with time null not zero."""
    inv = bei.build({}, performance(shared_time=None), attribution(), manifest(), ep_rank=0)
    shared = [e for e in inv["experts"] if e["kind"] == "shared"][0]
    assert shared["data_state"] == "source_only"
    assert shared["time_us"] is None


def test_dense_model_declares_no_experts():
    """A model without experts yields an empty inventory rather than a fabricated one."""
    inv = bei.build({}, performance(), {"rows": []}, manifest(routed=None, shared=None))
    assert inv["declared"]["total"] is None
    assert inv["experts"] == []


def test_plain_three_dim_expert_weight_is_recognised():
    """Unquantised MoE stacks weights as [E, K, N]; residency must work there too."""
    rows = [{"op_index": 1, "op_type": "GroupedMatmul",
             "input_shapes": [[512, 7168], [32, 7168, 2048], [32]],
             "output_shapes": [[512, 2048]]}]
    local, evidence = bei.observed_local_experts(rows)
    assert local == 32
    assert "leading dim" in evidence
