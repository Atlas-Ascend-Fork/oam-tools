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
"""Check the documented L3 contract through the public regression CLI."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/cann-perf-breakdown/1-perf-breakdown/scripts/regression_check.py"
FIXTURE = ROOT / "skills/cann-perf-breakdown/2-adapt-breakdown-to-ui-json/tests/fixtures/synthetic/analysis_config_v2.json"


def _run_check(tmp_path, baseline, updated, mode="A", report=False):
    baseline_path = tmp_path / "baseline.json"
    updated_path = tmp_path / "updated.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    updated_path.write_text(json.dumps(updated), encoding="utf-8")
    args = [sys.executable, str(SCRIPT), "--baseline", str(baseline_path),
            "--new", str(updated_path), "--mode", mode, "--json"]
    if report:
        args += ["--report", str(tmp_path / "report.md")]
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", check=False)
    assert not result.stderr, result.stderr
    # Without a report, stdout is the public JSON contract.
    data = json.loads(result.stdout) if not report else None
    return result, data


@pytest.fixture
def config():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("indices", ([0], [0, 1, 2], [0, 2]))
@pytest.mark.parametrize("mode", ("A", "B"))
def test_changed_stage_instances_fail_l3(tmp_path, config, indices, mode):
    updated = deepcopy(config)
    updated["stages"]["mtp_scaffold"]["stage_indices"] = indices
    result, data = _run_check(tmp_path, config, updated, mode)
    finding = next(item for item in data["findings"] if item["id"] == "L3")
    assert result.returncode == 1
    assert finding["pass"] is False
    assert data["hard_fails"] == 1
    assert all(item["pass"] for item in data["findings"] if item["id"] != "L3")
    assert finding["detail"]["stage_indices_mismatches"] == [
        {"stage": "mtp_scaffold", "baseline": [0, 1], "new": indices}
    ]


def test_stage_indices_compared_per_stage_not_as_global_union(tmp_path, config):
    config["stages"]["mtp_output"]["stage_indices"] = [2, 3]
    updated = deepcopy(config)
    updated["stages"]["mtp_scaffold"]["stage_indices"] = [2, 3]
    updated["stages"]["mtp_output"]["stage_indices"] = [0, 1]
    result, data = _run_check(tmp_path, config, updated)
    assert result.returncode == 1
    assert data["hard_fails"] == 1
    finding = next(item for item in data["findings"] if item["id"] == "L3")
    assert [item["stage"] for item in finding["detail"]["stage_indices_mismatches"]] == [
        "mtp_output", "mtp_scaffold"
    ]


@pytest.mark.parametrize("variant", ("unchanged", "reordered", "explicit_singleton"))
def test_equivalent_stage_instances_pass(tmp_path, config, variant):
    updated = deepcopy(config)
    if variant == "reordered":
        updated["stages"]["mtp_scaffold"]["stage_indices"] = [1, 0]
    elif variant == "explicit_singleton":
        # Non-repeated stages have one instance when stage_indices is omitted.
        updated["stages"]["embedding"]["stage_indices"] = [0]
    result, data = _run_check(tmp_path, config, updated)
    assert result.returncode == 0
    assert data["hard_fails"] == 0
    assert all(item["pass"] for item in data["findings"])


@pytest.mark.parametrize("operation", ("add", "remove"))
def test_changed_stage_names_still_fail_l3(tmp_path, config, operation):
    updated = deepcopy(config)
    if operation == "add":
        updated["stages"]["new_stage"] = {"name": "new_stage", "op_indices": [0]}
    else:
        updated["stages"].pop("embedding")
    result, data = _run_check(tmp_path, config, updated)
    assert result.returncode == 1
    assert next(item for item in data["findings"] if item["id"] == "L3")["pass"] is False


def test_changed_stage_instances_report_explains_difference(tmp_path, config):
    updated = deepcopy(config)
    updated["stages"]["mtp_scaffold"]["stage_indices"] = [0]
    result, _ = _run_check(tmp_path, config, updated, report=True)
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert result.returncode == 1
    assert "| L3 | ✗ |" in report
    assert "mtp_scaffold" in report


def test_removing_repetition_field_cannot_hide_lost_instance(tmp_path, config):
    updated = deepcopy(config)
    updated["stages"]["mtp_scaffold"].pop("stage_indices")
    result, data = _run_check(tmp_path, config, updated)
    assert result.returncode == 1
    finding = next(item for item in data["findings"] if item["id"] == "L3")
    assert finding["pass"] is False
