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
"""Regression for conversion-output discovery under glob metacharacters.

``validate_conversion.find_one`` locates the three emitted fact files by joining its
``out_dir`` straight into a ``glob`` pattern. ``out_dir`` is caller-supplied -- the pipeline
passes ``<--out>/ui_facts`` -- so a directory whose name contains glob syntax is normal
input, not a malformed one. Left unescaped, ``out[0]`` parses as a character class and
matches nothing, so a present fact file is reported missing; ``out*2026`` also matches the
unrelated ``outX2026`` beside it, so a single legitimate file is reported ambiguous.

Both failure modes abort the conversion check on inputs that are fine. The contract under
test: search the given directory literally, keep refusing to guess when there really are
several matches, and keep naming the suffix when there are none.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "cann-perf-breakdown"
# ``find_one`` is generic over the suffix, so every fact file the validator loads is held to
# the same rule rather than only the one named in the reproduction.
SUFFIXES = ("_analysis_config.json", "_perf_data.json", "_timeline.json")
# ``--out`` is a caller-supplied path, and glob metacharacters are legal in directory names.
METACHAR_DIRS = ("out[0]", "out*2026", "out?0")


def validator_scripts():
    """Every ``validate_conversion.py`` under the skill that defines ``find_one``.

    Discovered rather than hard-coded so a second applicable copy is covered without
    editing this file, matching ``test_ambiguous_capture_selection.py``.
    """
    scripts = []
    for path in sorted(SKILL.rglob("validate_conversion.py")):
        if "def find_one(" in path.read_text(encoding="utf-8"):
            scripts.append(path)
    return scripts


SCRIPTS = validator_scripts()


def script_id(path):
    return path.parent.parent.name


def load_script(path, monkeypatch):
    """Import a validator script without letting its siblings leak across tests."""
    monkeypatch.syspath_prepend(str(path.parent))
    name = f"validator_under_test_{script_id(path)}"
    monkeypatch.delitem(sys.modules, name, raising=False)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def write_fact(directory, suffix, stem="fixture"):
    directory.mkdir(parents=True, exist_ok=True)
    fact = directory / (stem + suffix)
    fact.write_text("host fixture only", encoding="utf-8")
    return str(fact)


def test_validator_scripts_are_discovered():
    assert SCRIPTS, f"no validate_conversion.py defining find_one under {SKILL}"


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
@pytest.mark.parametrize("dirname", METACHAR_DIRS)
@pytest.mark.parametrize("suffix", SUFFIXES)
def test_metachar_out_dir_finds_the_single_fact(
    script, dirname, suffix, tmp_path, monkeypatch
):
    """A fact file under a directory whose name is valid glob syntax is still found."""
    module = load_script(script, monkeypatch)
    out_dir = tmp_path / dirname
    expected = write_fact(out_dir, suffix)

    assert module.find_one(str(out_dir), suffix) == expected


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
def test_metachar_out_dir_does_not_leak_into_siblings(script, tmp_path, monkeypatch):
    """A wildcard in the output directory name must not widen discovery to other outputs.

    Unescaped, ``out*2026`` also matches the unrelated ``outX2026`` beside it, so one
    legitimate fact file is reported as an ambiguous pair and the check aborts.
    """
    module = load_script(script, monkeypatch)
    suffix = "_perf_data.json"
    out_dir = tmp_path / "out*2026"
    expected = write_fact(out_dir, suffix)
    write_fact(tmp_path / "outX2026", suffix)

    assert module.find_one(str(out_dir), suffix) == expected


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
@pytest.mark.parametrize("dirname", METACHAR_DIRS)
def test_metachar_out_dir_still_refuses_to_guess(
    script, dirname, tmp_path, monkeypatch
):
    """Escaping the directory must not weaken the existing ambiguity refusal."""
    module = load_script(script, monkeypatch)
    suffix = "_timeline.json"
    out_dir = tmp_path / dirname
    later = write_fact(out_dir, suffix, stem="b_second")
    write_fact(out_dir, suffix, stem="a_first")

    with pytest.raises(SystemExit) as excinfo:
        module.find_one(str(out_dir), suffix)

    # Both real paths are named, never the escaped pattern form.
    assert "ambiguous" in str(excinfo.value)
    assert later in str(excinfo.value)


@pytest.mark.parametrize("script", SCRIPTS, ids=script_id)
def test_missing_fact_still_names_the_suffix(script, tmp_path, monkeypatch):
    """An empty output directory keeps reporting the missing suffix rather than a glob error."""
    module = load_script(script, monkeypatch)
    out_dir = tmp_path / "out[0]"
    out_dir.mkdir()

    with pytest.raises(SystemExit) as excinfo:
        module.find_one(str(out_dir), "_analysis_config.json")

    assert "no *_analysis_config.json" in str(excinfo.value)
