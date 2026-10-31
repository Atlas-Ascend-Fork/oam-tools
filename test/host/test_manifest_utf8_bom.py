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
"""A leading UTF-8 BOM must not change what extract_model_manifest.py reports.

The BOM is valid UTF-8, so ``errors='replace'`` cannot absorb it: it decodes to U+FEFF and
then either breaks ``ast.parse`` or silently defeats the ``model_path:`` prefix match on
runtime.yaml's first line. Both shapes are exercised through the real CLI, because the
silent one (exit 0, wrong layer count) is the dangerous half. See issue #311.
"""

import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "skills/cann-perf-breakdown/1-perf-breakdown/scripts/extract_model_manifest.py"
)

# Source default is 61; the checkpoint says 14. A manifest reporting 61 proves the
# checkpoint was never found, which is exactly what a BOM on runtime.yaml causes.
CONFIG_SRC = textwrap.dedent(
    """\
    class DeepseekV3Config:
        def __init__(self, num_hidden_layers=61, num_nextn_predict_layers=0,
                     first_k_dense_replace=3, n_routed_experts=64,
                     n_shared_experts=1, num_experts_per_tok=6):
            self.num_hidden_layers = num_hidden_layers
            self.num_nextn_predict_layers = num_nextn_predict_layers
            self.first_k_dense_replace = first_k_dense_replace
            self.n_routed_experts = n_routed_experts
            self.n_shared_experts = n_shared_experts
            self.num_experts_per_tok = num_experts_per_tok
    """
)
MODELING_SRC = "class DeepseekV3DecoderLayer:\n    pass\n"
CHECKPOINT = {
    "num_hidden_layers": 14,
    "num_nextn_predict_layers": 0,
    "first_k_dense_replace": 3,
    "n_routed_experts": 64,
    "n_shared_experts": 1,
    "num_experts_per_tok": 6,
}
BOM = "\ufeff"


def _write(path, text, bom):
    """Write text, optionally prefixed with a real UTF-8 BOM, and assert it is legal Python."""
    path.write_text((BOM if bom else "") + text, encoding="utf-8")
    if path.suffix == ".py":
        # CPython compiles BOM-prefixed bytes fine; a tool that cannot is the bug.
        compile(path.read_bytes(), str(path), "exec")


@pytest.fixture
def bundle(tmp_path):
    """A model dir plus a checkpoint dir, with per-file BOM control."""
    model = tmp_path / "model"
    weights = tmp_path / "weights"
    model.mkdir()
    weights.mkdir()

    def build(
        bom_configuration=False,
        bom_modeling=False,
        bom_runtime=False,
        bom_checkpoint=False,
        line_ending="\n",
    ):
        _write(model / "configuration_deepseek.py", CONFIG_SRC, bom_configuration)
        _write(model / "modeling_deepseek.py", MODELING_SRC, bom_modeling)
        _write(weights / "config.json", json.dumps(CHECKPOINT), bom_checkpoint)
        runtime = tmp_path / "runtime.yaml"
        runtime.write_bytes(
            ((BOM if bom_runtime else "") + f"model_path: {weights.as_posix()}").encode(
                "utf-8"
            )
            + line_ending.encode("ascii")
        )
        return model, runtime

    return build


def _run(tmp_path, model, runtime):
    output = tmp_path / "manifest.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--model-dir",
            str(model),
            "--runtime-config",
            str(runtime),
            "--base-dir",
            str(tmp_path),
            "--model-name",
            "deepseek",
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    return proc, report


def _assert_checkpoint_layers(report):
    assert report["num_main_layers"] == 14
    assert report["capture_provenance"]["checkpoint_config"]["present"] is True


def test_no_bom_baseline_reads_checkpoint_layers(bundle, tmp_path):
    """Control: without any BOM the checkpoint overrides the 61-layer source default."""
    model, runtime = bundle()
    proc, report = _run(tmp_path, model, runtime)
    assert proc.returncode == 0, proc.stderr
    _assert_checkpoint_layers(report)


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"bom_configuration": True}, id="configuration"),
        pytest.param({"bom_modeling": True}, id="modeling"),
        pytest.param({"bom_runtime": True}, id="runtime_yaml"),
        pytest.param({"bom_checkpoint": True}, id="checkpoint_config_json"),
        pytest.param(
            {
                "bom_configuration": True,
                "bom_modeling": True,
                "bom_runtime": True,
                "bom_checkpoint": True,
            },
            id="all_four",
        ),
    ],
)
def test_bom_on_any_entry_matches_the_no_bom_baseline(bundle, tmp_path, kwargs):
    """Every BOM entry point must produce exactly the control's answer.

    `runtime_yaml` and `checkpoint_config_json` are the ones that used to fail *quietly*
    or with a json decoder error rather than an AST SyntaxError.
    """
    model, runtime = bundle(**kwargs)
    proc, report = _run(tmp_path, model, runtime)
    assert proc.returncode == 0, proc.stderr
    assert "U+FEFF" not in proc.stderr
    _assert_checkpoint_layers(report)


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_bom_with_either_line_ending(bundle, tmp_path, line_ending):
    """Line endings are not the trigger; the BOM is. Both endings must behave alike."""
    model, runtime = bundle(bom_runtime=True, line_ending=line_ending)
    proc, report = _run(tmp_path, model, runtime)
    assert proc.returncode == 0, proc.stderr
    _assert_checkpoint_layers(report)


def test_interior_bom_character_is_preserved_not_stripped(tmp_path):
    """utf-8-sig consumes only the leading marker; a body U+FEFF is content and must survive.

    Guards against "fixing" this by deleting the character globally, which would corrupt
    real paths and excerpts that legitimately contain it.
    """
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import extract_model_manifest as tool
    finally:
        sys.path.pop(0)

    interior = tmp_path / "runtime_record.log"
    interior.write_text(
        BOM + "num_hidden_layers: 14\nweird/path/\ufeff/kept\n", encoding="utf-8"
    )
    text = tool.read(str(interior))

    assert not text.startswith(BOM), "leading BOM must be consumed"
    assert text.splitlines()[0] == "num_hidden_layers: 14"
    assert "weird/path/\ufeff/kept" in text, "interior U+FEFF must be preserved"
