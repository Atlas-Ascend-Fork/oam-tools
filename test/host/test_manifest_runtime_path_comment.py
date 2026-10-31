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
"""An inline comment after ``model_path`` must not become part of the checkpoint path.

A comment is legal YAML, so ``model_path: "/ckpt" # selected`` names the same checkpoint
as ``model_path: "/ckpt"``. The old ``strip('"\\'')`` trimmed quote characters off both
ends only: the comment's trailing ``t`` blocked the tail strip while the leading quote
was still removed, yielding ``/ckpt" # selected``. That directory cannot exist, so the
checkpoint was missed and the architecture report silently fell back to the source
default -- 61 layers instead of the checkpoint's 14 -- with exit code 0. See issue #310.

Every case runs the real CLI, because the failure is quiet by construction.
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

# The source default is 61 and the checkpoint says 14, so a report of 61 proves the
# checkpoint was never found -- exactly what a trailing comment used to cause.
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

# (id, weights dir name, model_path value as written; {w} is that dir's absolute path)
# All of these name one and the same checkpoint, so all must report the checkpoint's
# 14 layers. The first entry is the control that always worked.
RUNTIME_CASES = [
    pytest.param("weights", '"{w}"', id="control_double_quoted"),
    pytest.param("weights", '"{w}" # selected checkpoint', id="double_quoted_comment"),
    pytest.param("weights", "'{w}' # selected", id="single_quoted_comment"),
    pytest.param("weights", "{w} # selected", id="plain_scalar_comment"),
    pytest.param("weights", '"{w}"\t# tab separated', id="tab_before_comment"),
    pytest.param("weights", '"{w}" # a # b', id="comment_containing_hash"),
    pytest.param("weights", '"{w}" # say "hi"', id="comment_containing_quotes"),
    # A '#' inside quotes is content, never a comment.
    pytest.param("weights#v2", '"{w}"', id="hash_in_dir_double_quoted"),
    pytest.param("weights#v2", "'{w}'", id="hash_in_dir_single_quoted"),
    # A plain scalar only opens a comment after whitespace, so this '#' is content too.
    pytest.param("weights#v2", "{w}", id="hash_in_dir_plain_scalar"),
    # Same rule protects a space that is part of the path rather than a separator.
    pytest.param("weights dir", '"{w}"', id="space_in_dir_double_quoted"),
    pytest.param("weights dir", "'{w}'", id="space_in_dir_single_quoted"),
]


@pytest.fixture
def bundle(tmp_path):
    """Build a model dir plus a weights dir, and write a runtime YAML for it."""
    model = tmp_path / "model"
    model.mkdir()
    (model / "configuration_deepseek.py").write_text(CONFIG_SRC, encoding="utf-8")
    (model / "modeling_deepseek.py").write_text(MODELING_SRC, encoding="utf-8")

    def build(dir_name="weights", value='"{w}"', with_checkpoint=True):
        weights = tmp_path / dir_name
        weights.mkdir()
        if with_checkpoint:
            (weights / "config.json").write_text(
                json.dumps(CHECKPOINT), encoding="utf-8"
            )
        runtime = tmp_path / "runtime.yaml"
        runtime.write_text(
            "model_path: " + value.format(w=weights.as_posix()) + "\n", encoding="utf-8"
        )
        return model, weights, runtime

    return build


def _run(tmp_path, model, runtime, extra=()):
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
            *extra,
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    return proc, report


@pytest.mark.parametrize("dir_name,value", RUNTIME_CASES)
def test_comment_never_changes_which_checkpoint_is_read(
    bundle, tmp_path, dir_name, value
):
    """Every spelling above points at one real checkpoint and must report its 14 layers."""
    model, weights, runtime = bundle(dir_name, value)
    proc, report = _run(tmp_path, model, runtime)
    assert proc.returncode == 0, proc.stderr
    assert report["num_main_layers"] == 14
    assert report["capture_provenance"]["checkpoint_config"]["present"] is True
    # The recorded path is the real one: no leftover quote, no leftover comment text.
    assert report["declared_model_path"] == weights.as_posix()


def test_missing_checkpoint_reports_the_clean_path_not_the_comment(bundle, tmp_path):
    """A genuinely absent checkpoint still falls back, but the gap must be diagnosable.

    The fallback itself is intended behaviour; what issue #310 broke was the text a
    reader is given, which used to be `/ckpt" # selected` -- unfindable in the YAML.
    """
    model, weights, runtime = bundle(
        value='"{w}" # selected checkpoint', with_checkpoint=False
    )
    proc, report = _run(tmp_path, model, runtime)
    assert proc.returncode == 0, proc.stderr
    assert report["num_main_layers"] == 61
    assert report["capture_provenance"]["checkpoint_config"]["present"] is False
    declared = report["declared_model_path"]
    assert declared == weights.as_posix()
    assert "#" not in declared and '"' not in declared
    assert any(weights.as_posix() in gap for gap in report["evidence_gaps"])


def test_value_that_is_only_a_comment_is_skipped_not_treated_as_a_path(
    bundle, tmp_path
):
    """`model_path:` with nothing but a comment declares no path at all."""
    model, _weights, runtime = bundle(value="# nothing here")
    proc, report = _run(tmp_path, model, runtime)
    assert proc.returncode == 0, proc.stderr
    assert report["declared_model_path"] is None
    assert report["num_main_layers"] == 61
    assert any("未在 YAML 中声明" in gap for gap in report["evidence_gaps"])


def test_explicit_checkpoint_config_still_wins_over_a_commented_yaml(bundle, tmp_path):
    """`--checkpoint-config` keeps its precedence; the YAML comment is irrelevant."""
    model, weights, runtime = bundle(
        value='"{w}" # selected checkpoint', with_checkpoint=False
    )
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    (explicit / "config.json").write_text(json.dumps(CHECKPOINT), encoding="utf-8")
    proc, report = _run(
        tmp_path,
        model,
        runtime,
        extra=("--checkpoint-config", str(explicit / "config.json")),
    )
    assert proc.returncode == 0, proc.stderr
    assert report["num_main_layers"] == 14
    assert report["declared_model_path"] == explicit.as_posix()


def test_nested_declaration_under_a_mapping_key(bundle, tmp_path):
    """Indented `model_path:` under a parent key is the shape real runtime YAML uses."""
    model, weights, _runtime = bundle()
    nested = tmp_path / "nested.yaml"
    nested.write_text(
        'model:\n  model_path: "%s" # selected checkpoint\n' % weights.as_posix(),
        encoding="utf-8",
    )
    proc, report = _run(tmp_path, model, nested)
    assert proc.returncode == 0, proc.stderr
    assert report["num_main_layers"] == 14
    assert report["declared_model_path"] == weights.as_posix()


@pytest.mark.parametrize(
    "raw,expected",
    [
        pytest.param('"/ckpt"', '"/ckpt"', id="no_comment"),
        pytest.param('"/ckpt" # selected', '"/ckpt"', id="double_quoted"),
        pytest.param("'/ckpt' # selected", "'/ckpt'", id="single_quoted"),
        pytest.param("/ckpt # selected", "/ckpt", id="plain_scalar"),
        pytest.param("/ckpt\t# selected", "/ckpt", id="tab_separated"),
        pytest.param('"/ckpt" # a # b', '"/ckpt"', id="only_first_hash_opens"),
        pytest.param("/ckpt#v2", "/ckpt#v2", id="hash_needs_leading_space"),
        pytest.param('"/ckpt#v2"', '"/ckpt#v2"', id="hash_inside_quotes"),
        pytest.param('"/ckpt dir"', '"/ckpt dir"', id="space_inside_quotes"),
        pytest.param("# only a comment", "", id="value_is_entirely_a_comment"),
        pytest.param("   ", "", id="blank"),
        pytest.param('"/ckpt"   ', '"/ckpt"', id="trailing_spaces"),
        # Invalid YAML: the helper must not invent a path, the caller trims as before.
        pytest.param('"/ckpt', '"/ckpt', id="unterminated_double_quote"),
        pytest.param(
            '"/ckpt # still open', '"/ckpt # still open', id="unterminated_with_hash"
        ),
        pytest.param("'it''s /ckpt' # x", "'it''s /ckpt'", id="doubled_single_quote"),
    ],
)
def test_strip_inline_comment_boundaries(raw, expected):
    """Unit-level table for the helper: comments out, quoted content kept verbatim."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import extract_model_manifest
    finally:
        sys.path.pop(0)
    assert extract_model_manifest.strip_inline_comment(raw) == expected
