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
"""L7 compares exact native-v2 ownership, including nonrepresentative calls."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/cann-perf-breakdown/1-perf-breakdown/scripts/regression_check.py"
FIXTURE = ROOT / "skills/cann-perf-breakdown/2-adapt-breakdown-to-ui-json/tests/fixtures/synthetic/analysis_config_v2.json"


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _run(tmp_path, baseline, new, *arguments):
    baseline_path, new_path = tmp_path / "baseline.json", tmp_path / "new.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    new_path.write_text(json.dumps(new), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--baseline", str(baseline_path),
                             "--new", str(new_path), "--json", *arguments],
                            capture_output=True, text=True, encoding="utf-8", check=False)
    assert result.returncode in (0, 1), result.stdout + result.stderr
    report = json.loads(result.stdout)
    return result, report


def _coverage(report):
    return next(row for row in report["findings"] if row["id"] == "L7")


def _expect_loss(tmp_path, baseline, new, missing, extra=()):
    result, report = _run(tmp_path, baseline, new)
    check = _coverage(report)
    assert result.returncode == 1
    assert not check["pass"]
    assert check["detail"]["baseline_count"] == 32
    assert check["detail"]["missing_in_new"] == list(missing)
    assert check["detail"]["extra_in_new"] == list(extra)


def _expect_same(tmp_path, baseline, new):
    result, report = _run(tmp_path, baseline, new)
    assert result.returncode == 0
    check = _coverage(report)
    assert check["pass"]
    assert check["detail"]["baseline_count"] == check["detail"]["new_count"] == 32


def test_nonrepresentative_mtp_range_loss_blocks_by_default(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    assert new["trace_instances"][-1]["representative_instance_id"] == "mtp_iter_0"
    new["trace_instances"][-1]["op_range"][1] = 27
    _expect_loss(tmp_path, baseline, new, [28])


def test_same_count_replacement_still_reports_set_difference(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["trace_instances"][-1]["op_indices"] = [26, 27, 32]
    _expect_loss(tmp_path, baseline, new, [28], [32])


def test_deleting_observed_call_reports_its_exact_ops(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["trace_instances"].pop()
    _expect_loss(tmp_path, baseline, new, [26, 27, 28])


def test_adding_observed_call_reports_all_new_ops(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    extra = deepcopy(new["trace_instances"][-1])
    extra.update(instance_id="mtp_iter_2", invocation_index=2, op_range=[32, 34])
    new["trace_instances"].append(extra)
    _expect_loss(tmp_path, baseline, new, [], [32, 33, 34])


def test_equivalent_inclusive_range_and_explicit_indices_are_equal(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["trace_instances"][-1].pop("op_range")
    new["trace_instances"][-1]["op_indices"] = [26, 27, 28]
    _expect_same(tmp_path, baseline, new)


def test_explicit_sparse_indices_take_priority_over_range(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["trace_instances"][-1]["op_indices"] = [26, 28]
    _expect_loss(tmp_path, baseline, new, [27])


def test_reordering_instances_does_not_change_total_coverage(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["trace_instances"].reverse()
    _expect_same(tmp_path, baseline, new)


def test_representative_template_omission_does_not_erase_observed_coverage(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["structures"] = {}
    _expect_same(tmp_path, baseline, new)


def test_unknown_learned_layer_still_contributes_observed_ops(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["trace_instances"][-1]["model_layer_index"] = "unknown"
    _expect_same(tmp_path, baseline, new)


def test_changed_instance_partition_with_same_union_is_not_a_coverage_loss(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["trace_instances"][-2]["op_range"] = [21, 22]
    new["trace_instances"][-1].pop("op_range")
    new["trace_instances"][-1]["op_indices"] = [23, 26, 27, 28]
    _expect_same(tmp_path, baseline, new)


def test_excluded_profiler_ops_are_part_of_total_accounting(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["excluded_profiler_ops"].append({"op_indices": [32], "reason_code": "profiler_marker",
                                         "evidence": "synthetic extra profiler marker index"})
    _expect_loss(tmp_path, baseline, new, [], [32])


def test_unmapped_declared_ops_are_part_of_total_accounting(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["unmapped_ops"].append({"op_indices": [32], "reason": "unresolved"})
    _expect_loss(tmp_path, baseline, new, [], [32])


def test_category_change_preserves_total_union(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["trace_instances"][-1]["op_range"][1] = 27
    new["unmapped_ops"].append({"op_indices": [28], "reason": "ownership remains unresolved"})
    _expect_same(tmp_path, baseline, new)


def test_implicit_native_v2_marker_uses_existing_schema_detection(tmp_path):
    baseline = _fixture()
    baseline.pop("schema_version")
    new = deepcopy(baseline)
    new["trace_instances"][-1]["op_range"][1] = 27
    _expect_loss(tmp_path, baseline, new, [28])


def test_mode_b_continues_to_skip_op_coverage(tmp_path):
    baseline = _fixture()
    new = deepcopy(baseline)
    new["trace_instances"].pop()
    result, report = _run(tmp_path, baseline, new, "--mode", "B")
    assert result.returncode == 0
    assert not any(row["id"] == "L7" for row in report["findings"])


def test_legacy_layer_structure_coverage_is_unchanged(tmp_path):
    baseline = {"schema_version": 1, "layer_types": {"Dense": {"layer_indices": [0]}},
                "layer_structure": {"Dense": {"name": "Dense", "op_indices": [1, 2]}},
                "stages": {"input": {"name": "input", "op_indices": [0]}},
                "runtime_auxiliary": [{"name": "sampling", "op_indices": [3]}]}
    new = deepcopy(baseline)
    new["layer_structure"]["Dense"]["op_indices"] = [1]
    result, report = _run(tmp_path, baseline, new)
    assert result.returncode == 1
    check = _coverage(report)
    assert not check["pass"]
    assert check["detail"] == {"baseline_count": 4, "new_count": 3,
                               "missing_in_new": [2], "extra_in_new": []}


@pytest.mark.parametrize("lose_observed_op", (False, True))
def test_module_loading_preserves_all_regression_findings(tmp_path, lose_observed_op):
    # A fresh interpreter and a different cwd do not inherit a prior script import
    # that accidentally makes breakdown_common discoverable.
    code = """
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("regression_check_module", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
baseline = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
new = deepcopy(baseline)
if sys.argv[3] == "True":
    new["trace_instances"][-1]["op_range"][1] = 27
print(json.dumps(module.check_regression(baseline, new)))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(SCRIPT), str(FIXTURE), str(lose_observed_op)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    findings = json.loads(result.stdout)
    assert [finding["id"] for finding in findings] == [f"L{index}" for index in range(1, 9)]
    assert all(finding["pass"] for finding in findings if finding["id"] != "L7")
    coverage = next(finding for finding in findings if finding["id"] == "L7")
    assert coverage["pass"] is not lose_observed_op
    assert coverage["detail"]["baseline_count"] == 32
    assert coverage["detail"]["missing_in_new"] == ([28] if lose_observed_op else [])
