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

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).parents[1] / "scripts"
SELECTORS = [
    ({"0": "value"}, "$[0]", False),
    (["value"], '$["0"]', False),
    ({"00": "value"}, "$[00]", False),
    (["value"], '$["00"]', False),
    ({"items": {"0": "value"}}, "$.items[0]", False),
    ({"items": ["value"]}, '$.items["0"]', False),
    ({"items": {"0": "value"}}, '$.items["0"]', True),
    ({"items": ["value"]}, "$.items[0]", True),
    ({"0": "value"}, '$["0"]', True),
    (["value"], "$[0]", True),
    ({"00": "value"}, '$["00"]', True),
    ({"items": [{"0": "value"}]}, '$.items[0]["0"]', True),
    ({"items": [{"0": "value"}]}, "$.items[0][0]", False),
    ({"items": [["value"]]}, '$.items[0]["0"]', False),
    ({"items": [["value"]]}, "$.items[0][0]", True),
    ({"a.b": {"0": "value"}}, '$["a.b"][0]', False),
    ({"a.b": {"0": "value"}}, '$["a.b"]["0"]', True),
    ({"items": []}, "$.items[0]", False),
    ({"items": ["value"]}, "$.items[1]", False),
    ({"items": ["value"]}, "$.items[-1]", False),
    ({"items": ["value"]}, '$.items["-1"]', False),
    ({"items": ["value"]}, "$.missing[0]", False),
    ({"items": ["value"]}, "$.items[", False),
    ({"items": ["value"]}, "$", True),
]


@pytest.fixture
def common():
    spec = importlib.util.spec_from_file_location("breakdown_common", SCRIPTS / "breakdown_common.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("config, locator, expected", SELECTORS)
def test_config_path_preserves_selector_type(common, config, locator, expected):
    assert common.resolve_config_path(config, locator) is expected


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.mark.parametrize("locator, expected", [
    ("$.structures[0].name", False),
    ('$.architecture.layer_groups["0"].type', False),
    ('$.architecture.layer_groups["00"].type', False),
    ('$.architecture.layer_groups[0].model_layer_indices["0"]', False),
    ('$.structures["0"].name', True),
    ("$.architecture.layer_groups[0].type", True),
])
def test_targeted_critique_cli_rejects_wrong_selector(common, tmp_path, locator, expected):
    config = {
        "schema_version": 2, "model_name": "selector fixture",
        "architecture": {"source_of_truth": [], "num_main_layers": 1,
                         "layer_groups": [{"type": "0", "model_layer_indices": [0]}],
                         "prediction_modules": []},
        "structures": {"0": {"name": "layer", "semantic": "Host fixture", "op_indices": [0]}},
    }
    schema = common.load_schema(SCRIPTS.parent / "schemas/analysis_config_v2.schema.json")
    assert common.validate_json_schema(config, schema) == []
    candidate = write_json(tmp_path / "config.json", config)
    bundle_hash = hashlib.sha256(b"").hexdigest()
    source = write_json(tmp_path / "source.json", {"source_bundle_hash": bundle_hash, "files": []})
    raw = write_json(tmp_path / "raw.json", {"operators": []})
    inputs = {"config": candidate, "source_index": source}
    bindings = {"raw_ops": raw}
    context = write_json(tmp_path / "context.json", {"inputs": inputs, "bindings_not_llm_inputs": bindings})
    scope = {"config_paths": [locator], "source_refs": [], "op_indices": []}
    binding = {"scope": scope, "check_ids": ["locator_type"]}
    scope_hash = hashlib.sha256(
        json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    write_json(tmp_path / "request.json", {
        "candidate_sha256": candidate["sha256"], "inputs": inputs,
        "bindings_not_llm_inputs": bindings, "scope": scope,
        "blocking_items": [{"id": "locator_type"}], "context_manifest": context["path"],
    })
    write_json(tmp_path / "report.json", {
        "schema_version": 1, "critique_kind": "targeted", "status": "passed",
        "candidate_sha256": candidate["sha256"], "source_bundle_hash": bundle_hash,
        "context_manifest_sha256": context["sha256"], "scope_sha256": scope_hash,
        "scope": scope, "issues": [],
        "checks": [{"id": "locator_type", "status": "passed",
                    "evidence": [{"config_path": locator, "explanation": "configuration locator"}]}],
    })
    command = [sys.executable, str(SCRIPTS / "validate_targeted_critique.py"),
               "-q", str(tmp_path / "report.json"), "-c", candidate["path"],
               "--source-index", source["path"], "-r", raw["path"],
               "--request", str(tmp_path / "request.json")]
    result = subprocess.run(command, text=True, capture_output=True)
    output = json.loads(result.stdout)
    assert result.returncode == (0 if expected else 1), output
    assert output["detail"]["schema_valid"] is True
    assert output["detail"]["clears_scope"] is expected
    assert [item["id"] for item in output["issues"]] == ([] if expected else ["TC_CONFIG_PATH"])
    assert output["eligible_for_scoring"] is False


@pytest.mark.parametrize("config, locator, expected", SELECTORS)
def test_revision_context_preserves_selector_types(monkeypatch, config, locator, expected):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "typed_revision_context", SCRIPTS / "prepare_revision_context.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found, value = module._resolve(config, locator)
    assert found is expected
    if not expected:
        assert value is None


def load_path_consumer(monkeypatch, name):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("host_path_" + name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_path_consumers_keep_string_segments(monkeypatch, tmp_path):
    revision = load_path_consumer(monkeypatch, "prepare_revision_context")
    path = "$.structures.Block.name"
    assert revision._path_parts(path) == ["structures", "Block", "name"]
    assert revision._structure_path(path) == "$.structures.Block"
    config = {"structures": {"Block": {"name": "Block", "op_indices": [0]}}}
    issues = [{"id": "path-consumer", "_repair_policy_source": "deterministic_checker",
               "node_path": path, "config_paths": [path],
               "trace_evidence": [], "source_evidence": []}]
    revision._add_legacy_candidate_policies(config, issues)
    assert issues[0]["repair_policy"]["allowed_targets"]["analysis_config"] == [path]
    evidence = revision._candidate_evidence(config, issues)
    assert evidence["nodes"] == [{"path": path, "value": "Block"}]
    assert issues[0]["trace_evidence"] == [0]
    model = tmp_path / "model.py"
    model.write_text("class Block:\n    pass\n")
    index = {"files": [{"path": "model.py", "root": str(tmp_path),
                        "classes": [{"name": "Block", "forward": {"line_start": 1, "line_end": 2}}]}]}
    revision._dataflow_source_refs(index, issues, {"modules": [
        {"class_name": "Block", "source_path": "model.py", "is_primary": True}]})
    assert issues[0]["source_evidence"] == ["model.py:1-2"]


def test_diagnostic_pointer_prefix_uses_string_keys(monkeypatch):
    validator = load_path_consumer(monkeypatch, "validate_diagnostic_patch")
    assert validator._path_allowed("/structures/0/name", ['$.structures["0"]'])
    assert validator._path_allowed("/structures/a~1b/name", ['$.structures["a/b"]'])
    assert not validator._path_allowed("/structures/00/name", ['$.structures["0"]'])
    assert not validator._path_allowed("/architecture/name", ['$.structures["0"]'])


@pytest.mark.parametrize("trusted", [False, True])
def test_revision_cli_preserves_controlled_and_legacy_routes(tmp_path, trusted):
    config = {"schema_version": 2, "model_name": "path consumer fixture",
              "architecture": {"source_of_truth": [], "num_main_layers": 1,
                               "layer_groups": [], "prediction_modules": []},
              "structures": {"Block": {"name": "Block", "semantic": "Host fixture", "op_indices": [0]}}}
    write_json(tmp_path / "config.json", config)
    write_json(tmp_path / "source.json", {"source_bundle_hash": hashlib.sha256(b"").hexdigest(), "files": []})
    write_json(tmp_path / "raw.json", {"operators": []})
    write_json(tmp_path / "issues.json", {"issues": [
        {"id": "HOST_PATH", "severity": "error", "node_path": "structures.Block.name",
         "config_paths": ["$.structures.Block.name"], "message": "needs source evidence"}]})
    command = [sys.executable, str(SCRIPTS / "prepare_revision_context.py"),
               "-c", str(tmp_path / "config.json"), "--source-index", str(tmp_path / "source.json"),
               "-r", str(tmp_path / "raw.json"), "--issues", str(tmp_path / "issues.json"),
               "--context-manifest", str(tmp_path / "context.json"), "-o", str(tmp_path / "request.json")]
    if trusted:
        command += ["--trusted-policy-issues", str(tmp_path / "issues.json")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == (0 if trusted else 2), result.stderr
    assert "Traceback" not in result.stderr
    request = json.loads((tmp_path / "request.json").read_text())
    if trusted:
        assert request["task"] == "revise only the evidence-backed blocking items"
        policy = request["blocking_issues"][0]["repair_policy"]
        assert policy["repair_class"] == "legacy_candidate_path_repair"
        assert policy["allowed_targets"] == {"analysis_config": ["$.structures.Block.name"]}
    else:
        assert json.loads(result.stdout)["status"] == "needs_controlled_diagnosis"
        assert request["status"] == "needs_controlled_diagnosis"
