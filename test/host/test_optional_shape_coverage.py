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
"""Exercise optional shape annotations and real coverage errors via CLI."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills/cann-perf-breakdown/1-perf-breakdown/scripts"
FIXTURE = (
    ROOT
    / "skills/cann-perf-breakdown/2-adapt-breakdown-to-ui-json/tests/fixtures/synthetic"
)


@pytest.fixture
def inputs():
    config = json.loads(
        (FIXTURE / "analysis_config_v2.json").read_text(encoding="utf-8")
    )
    raw = json.loads((FIXTURE / "raw_ops.json").read_text(encoding="utf-8"))
    return config, raw


def _norm_node(config):
    return config["structures"]["SynDecoderLayer_dense"]["children"][0]["children"][1]


def _register_norm(config, shape=None):
    node = _norm_node(config)
    assert node["name"] == "input_norm" and node["op_indices"] == [4]
    kernel = {"name": "RmsNorm", "index": 4}
    if shape is not None:
        kernel["shape_semantic"] = shape
    node["kernels"] = [kernel]
    return node


def _reference_sources(tmp_path):
    root = tmp_path / "source"
    folder = root / "tests/fixtures/synthetic"
    folder.mkdir(parents=True)
    (folder / "configuration_synthetic.py").write_text(
        "num_main_layers = 2\n", encoding="utf-8"
    )
    (folder / "modeling_synthetic.py").write_text(
        "# Synthetic source reference for this host CLI fixture.\n" * 29
        + "class SynDecoderLayer: pass\n",
        encoding="utf-8",
    )
    return root


def _run(tmp_path, config, raw, script="check_op_coverage.py", extra=()):
    config_path, raw_path = tmp_path / "config.json", tmp_path / "raw.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    command = [sys.executable, str(SCRIPTS / script), "-c", str(config_path), "--json"]
    if script == "check_op_coverage.py":
        command += ["-r", str(raw_path)]
    command += list(extra)
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert not result.stderr, result.stderr
    return result, json.loads(result.stdout)


@pytest.mark.parametrize("location", ("normalization", "prolog", "communication"))
def test_registered_kernel_without_optional_shape_is_nonblocking(
    tmp_path, inputs, location
):
    config, raw = inputs
    if location == "normalization":
        _register_norm(config)
    elif location == "prolog":
        node = config["structures"]["SynDecoderLayer_dense"]["children"][0]["children"][
            0
        ]
        node["kernels"] = [{"name": "MlaPrologV3", "index": 3}]
    else:
        config["stages"]["embedding"]["kernels"] = [
            {"name": "HcomAllGather", "index": 1}
        ]
    result, data = _run(tmp_path, config, raw)
    assert result.returncode == 0
    assert data["error_count"] == 0
    assert data["summary"]["exact_coverage_pct"] == 100.0
    assert [(item["id"], item["severity"]) for item in data["issues"]] == [
        ("C5", "info")
    ]
    assert "可选" in data["issues"][0]["message"]


def test_empty_optional_annotation_is_also_nonblocking(tmp_path, inputs):
    config, raw = inputs
    _register_norm(config, "")
    result, data = _run(tmp_path, config, raw)
    assert result.returncode == 0
    assert data["error_count"] == 0
    assert (
        next(item for item in data["issues"] if item["id"] == "C5")["severity"]
        == "info"
    )


def test_complete_annotation_does_not_emit_missing_note(tmp_path, inputs):
    config, raw = inputs
    _register_norm(config, "[4, 128] → [4, 128]")
    result, data = _run(tmp_path, config, raw)
    assert result.returncode == 0
    assert data["issues"] == []


@pytest.mark.parametrize(
    "problem,expected",
    (
        ("missing", "C1"),
        ("duplicate", "C2"),
        ("out_of_range", "C3"),
        ("unmapped", "C4"),
        ("excluded_compute", "C6"),
        ("no_evidence", "C7"),
    ),
)
def test_real_coverage_errors_remain_blocking(tmp_path, inputs, problem, expected):
    config, raw = inputs
    _register_norm(config)
    if problem == "missing":
        config["stages"]["embedding"]["op_indices"].remove(2)
    elif problem == "duplicate":
        config["runtime_auxiliary"][0]["op_indices"].append(4)
    elif problem == "out_of_range":
        config["stages"]["embedding"]["op_indices"].append(100)
    elif problem == "unmapped":
        config["stages"]["embedding"]["op_indices"].remove(2)
        config["unmapped_ops"] = [{"op_indices": [2], "reason": "unresolved"}]
    else:
        config["stages"]["embedding"]["op_indices"].remove(2)
        entry = {"op_indices": [2], "reason_code": "profiler_marker"}
        if problem == "excluded_compute":
            entry["evidence"] = "controlled invalid exclusion for regression"
        config["excluded_profiler_ops"] = [entry]
    result, data = _run(tmp_path, config, raw)
    assert result.returncode == 1
    assert data["error_count"] > 0
    assert any(
        item["id"] == expected and item["severity"] == "error"
        for item in data["issues"]
    )


@pytest.mark.parametrize(
    "shape,returncode", (("[4, 128] → [4, 128]", 0), ("[4, 256] → [4, 256]", 1))
)
def test_explicit_strict_shape_validation_keeps_real_dimension_checks(
    tmp_path, inputs, shape, returncode
):
    config, raw = inputs
    node = _register_norm(config, shape)
    op = deepcopy(next(item for item in raw["operators"] if item["index"] == 4))
    op["name"] = op["normalized_name"]
    node["op_data"] = [op]
    result, data = _run(tmp_path, config, raw, "validate_shapes.py", ("--strict",))
    assert result.returncode == returncode
    if returncode:
        assert data["warning_count"] > 0 or data["error_count"] > 0


def test_unchanged_fixture_keeps_exact_coverage(tmp_path, inputs):
    config, raw = inputs
    result, data = _run(tmp_path, config, raw)
    assert result.returncode == 0
    assert data["issues"] == []
    assert data["summary"]["exact_coverage_pct"] == 100.0


@pytest.mark.parametrize("annotation", (None, ""))
def test_unified_validation_with_baseline_keeps_shapes_optional(
    tmp_path, inputs, annotation
):
    config, raw = inputs
    kernel = {"name": "HcomAllGather", "index": 1}
    if annotation is not None:
        kernel["shape_semantic"] = annotation
    config["stages"]["embedding"]["kernels"] = [kernel]
    config_path, raw_path, baseline_path, report = (
        tmp_path / name
        for name in ("config.json", "raw.json", "baseline.json", "report.json")
    )
    for path, value in (
        (config_path, config),
        (raw_path, raw),
        (baseline_path, config),
    ):
        path.write_text(json.dumps(value), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_validation.py"),
            "-c",
            str(config_path),
            "-r",
            str(raw_path),
            "--baseline",
            str(baseline_path),
            "--source-dir",
            str(_reference_sources(tmp_path)),
            "-o",
            str(report),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    data = json.loads(report.read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert data["status"] == "passed"
    assert data["error_count"] == data["warning_count"] == 0
    assert any(
        item["id"] == "L8" and item["severity"] == "info" for item in data["issues"]
    )


def test_unified_validation_still_blocks_missing_coverage_with_baseline(
    tmp_path, inputs
):
    config, raw = inputs
    _register_norm(config)
    baseline = deepcopy(config)
    config["stages"]["embedding"]["op_indices"].remove(2)
    paths = [tmp_path / name for name in ("config.json", "raw.json", "baseline.json")]
    for path, value in zip(paths, (config, raw, baseline)):
        path.write_text(json.dumps(value), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_validation.py"),
            "-c",
            str(paths[0]),
            "-r",
            str(paths[1]),
            "--baseline",
            str(paths[2]),
            "--source-dir",
            str(_reference_sources(tmp_path)),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    data = json.loads(result.stdout)
    assert result.returncode == 1
    assert data["status"] == "failed"
    assert any(
        item["id"] == "C1" and item["severity"] == "error" for item in data["issues"]
    )
