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
"""Regression for ambiguous capture selection (issue #282).

``run_pipeline.find_one`` recursively discovers capture files under
``--capture-dir``. A multi-rank capture directory holds one such file per
rank, and the old implementation returned ``sorted(glob(...))[0]``
unconditionally: handing it a multi-rank directory without naming a rank
silently analysed whichever rank sorted first, and the resulting report could
not prove it used the intended capture.

The contract under test: accept only a unique automatic candidate; report every
path and require an explicit selection when there are several; keep honouring an
explicit path, which overrides discovery.
"""

import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "cann-perf-breakdown"
DOCS = (
    SKILL / "MODEL_BREAKDOWN_TO_UI_WORKFLOW.md",
    SKILL / "MODEL_BREAKDOWN_TO_UI_WORKFLOW_en.md",
)
# ``find_one`` is generic over the capture file name, so both names the issue
# reports are held to the same rule even though the conversion entry point now
# auto-discovers only the trace.
CAPTURE_NAMES = ("kernel_details.csv", "trace_view.json")
# ``--capture-dir`` is a caller-supplied path and glob metacharacters are legal in directory
# names, so discovery has to treat the search root literally rather than as pattern syntax.
METACHAR_DIRS = ("capture[0]", "capture*2026", "capture?0")


def pipeline_scripts():
    """Every ``run_pipeline.py`` under the skill that defines ``find_one``.

    Discovered rather than hard-coded: the legacy
    ``skills/cann-perf-breakdown-to-ui-json`` copy named in the issue has since
    been deleted upstream, and a returning second applicable copy must be
    covered without editing this file.
    """
    scripts = []
    for path in sorted(SKILL.rglob("run_pipeline.py")):
        if "def find_one(" in path.read_text(encoding="utf-8"):
            scripts.append(path)
    return scripts


SCRIPTS = pipeline_scripts()


def script_id(path):
    return path.parent.parent.name


def load_script(path, monkeypatch):
    """Import a pipeline script without letting its siblings leak across tests."""
    monkeypatch.syspath_prepend(str(path.parent))
    monkeypatch.delitem(sys.modules, "breakdown_paths", raising=False)
    name = f"pipeline_under_test_{script_id(path)}"
    monkeypatch.delitem(sys.modules, name, raising=False)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def make_ranks(root, name, ranks=("rank0", "rank1")):
    """Lay out one capture file per rank and return the paths in sorted order."""
    paths = []
    for rank in ranks:
        rank_dir = root / rank
        rank_dir.mkdir()
        candidate = rank_dir / name
        candidate.write_text("host fixture only", encoding="utf-8")
        paths.append(str(candidate))
    return paths


def call_find_one(module, root, name, explicit=None, stages=None):
    """Call ``find_one`` without depending on the pre-fix signature.

    The buggy version had no ``stages`` parameter. Passing it unconditionally
    would fail that version with ``TypeError`` and hide the real regression: it
    returns the lexicographically first candidate instead of refusing to guess.
    """
    kwargs = {}
    if explicit is not None:
        kwargs["explicit"] = explicit
    if stages is not None and "stages" in inspect.signature(module.find_one).parameters:
        kwargs["stages"] = stages
    return module.find_one(root, name, **kwargs)


def test_pipeline_scripts_are_discovered():
    assert SCRIPTS, f"no run_pipeline.py defining find_one under {SKILL}"


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
@pytest.mark.parametrize("name", CAPTURE_NAMES)
def test_multiple_candidates_report_every_path(
    script, name, tmp_path, monkeypatch, capsys
):
    module = load_script(script, monkeypatch)
    paths = make_ranks(tmp_path, name)

    with pytest.raises(SystemExit) as excinfo:
        call_find_one(module, str(tmp_path), name, stages={"readiness": "ready"})

    assert excinfo.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["stage"] == "conversion_inputs"
    assert payload["stages"] == {"readiness": "ready"}
    assert payload["candidates"] == paths
    for path in paths:
        assert path in payload["message"]


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
@pytest.mark.parametrize("name", CAPTURE_NAMES)
def test_unique_candidate_is_accepted(script, name, tmp_path, monkeypatch, capsys):
    module = load_script(script, monkeypatch)
    paths = make_ranks(tmp_path, name, ranks=("rank0",))

    assert call_find_one(module, str(tmp_path), name) == paths[0]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
@pytest.mark.parametrize("name", CAPTURE_NAMES)
def test_explicit_path_overrides_ambiguous_discovery(
    script, name, tmp_path, monkeypatch, capsys
):
    module = load_script(script, monkeypatch)
    paths = make_ranks(tmp_path, name)

    # Naming the later rank selects it instead of the lexicographic first hit.
    assert call_find_one(module, str(tmp_path), name, explicit=paths[1]) == paths[1]
    # An explicit path outside the search root is still honoured verbatim.
    outside = tmp_path / "picked_by_operator"
    outside.mkdir()
    chosen = outside / name
    chosen.write_text("host fixture only", encoding="utf-8")
    assert call_find_one(module, str(tmp_path), name, explicit=str(chosen)) == str(
        chosen
    )
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
def test_missing_capture_still_reports_no_candidate(script, tmp_path, monkeypatch):
    module = load_script(script, monkeypatch)

    assert call_find_one(module, str(tmp_path), "trace_view.json") is None


@pytest.mark.parametrize("doc", DOCS, ids=lambda path: path.stem)
def test_workflow_doc_states_the_unique_candidate_rule(doc):
    text = doc.read_text(encoding="utf-8")

    assert "conversion_inputs" in text
    assert "--trace" in text
    assert "--csv" in text


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
@pytest.mark.parametrize("dirname", METACHAR_DIRS)
def test_metachar_capture_dir_finds_unique_candidate(
    script, dirname, tmp_path, monkeypatch, capsys
):
    """A capture directory whose name is valid glob syntax is still searched literally.

    With the root left unescaped, ``capture[0]`` is parsed as a character class, so an existing
    ``trace_view.json`` is reported missing instead of found.
    """
    module = load_script(script, monkeypatch)
    root = tmp_path / dirname
    root.mkdir()
    paths = make_ranks(root, "trace_view.json", ranks=("rank0",))

    assert call_find_one(module, str(root), "trace_view.json") == paths[0]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
@pytest.mark.parametrize("dirname", METACHAR_DIRS)
def test_metachar_capture_dir_still_reports_ambiguity(
    script, dirname, tmp_path, monkeypatch, capsys
):
    """Escaping the root must not weaken the uniqueness rule under a metacharacter directory."""
    module = load_script(script, monkeypatch)
    root = tmp_path / dirname
    root.mkdir()
    paths = make_ranks(root, "trace_view.json")

    with pytest.raises(SystemExit) as excinfo:
        call_find_one(
            module, str(root), "trace_view.json", stages={"readiness": "ready"}
        )

    assert excinfo.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["stage"] == "conversion_inputs"
    # Reported candidates are real paths, never the escaped pattern form.
    assert payload["candidates"] == paths
    for path in paths:
        assert path in payload["message"]


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
def test_metachar_capture_dir_does_not_leak_into_siblings(
    script, tmp_path, monkeypatch, capsys
):
    """A wildcard in the capture directory name must not widen discovery to other captures.

    Unescaped, ``capture*2026`` also matches the unrelated ``captureX2026`` beside it, so a
    single-rank capture is reported ambiguous -- and before the uniqueness rule existed it was
    silently analysed as whichever sibling sorted first.
    """
    module = load_script(script, monkeypatch)
    root = tmp_path / "capture*2026"
    root.mkdir()
    paths = make_ranks(root, "trace_view.json", ranks=("rank0",))
    decoy = tmp_path / "captureX2026"
    decoy.mkdir()
    make_ranks(decoy, "trace_view.json", ranks=("rank0",))

    assert call_find_one(module, str(root), "trace_view.json") == paths[0]
    assert capsys.readouterr().out == ""
