#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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

import sys
from pathlib import Path


ASYS_SRC = Path(__file__).resolve().parents[5] / "src" / "asys"
sys.path.insert(0, str(ASYS_SRC))

from collect.stackcore import stackcore_collect  # noqa: E402


def test_stackcore_run_reports_failure_when_all_files_fail(monkeypatch, tmp_path):
    parser = stackcore_collect.ParseStackCore(["/symbols"])
    monkeypatch.setattr(
        stackcore_collect.f,
        "walk_dir",
        lambda _path: [(str(tmp_path), [], ["stackcore_sample.txt"])],
    )
    monkeypatch.setattr(parser, "check_tool_exists", lambda: True)
    monkeypatch.setattr(
        parser, "save_file_result", lambda *_args: _args[-1].append(False)
    )

    assert parser.run(str(tmp_path / "stackcore")) is False


def test_stackcore_run_returns_true_when_any_file_succeeds(monkeypatch, tmp_path):
    parser = stackcore_collect.ParseStackCore(["/symbols"])
    monkeypatch.setattr(
        stackcore_collect.f,
        "walk_dir",
        lambda _path: [(str(tmp_path), [], ["a.txt", "b.txt"])],
    )
    monkeypatch.setattr(parser, "check_tool_exists", lambda: True)
    outcomes = iter([True, False])
    monkeypatch.setattr(
        parser, "save_file_result", lambda *_args: _args[-1].append(next(outcomes))
    )

    assert parser.run(str(tmp_path / "stackcore")) is True


def test_stackcore_run_returns_false_without_files(monkeypatch, tmp_path):
    parser = stackcore_collect.ParseStackCore(["/symbols"])
    # A directory that holds no processable (.txt) file: run() must reach the
    # changed `return any(results)` with an empty results list, not return
    # early at `if not stackcore_dirs`.
    monkeypatch.setattr(
        stackcore_collect.f,
        "walk_dir",
        lambda _path: [(str(tmp_path), [], ["notes.log"])],
    )
    monkeypatch.setattr(parser, "check_tool_exists", lambda: True)

    assert parser.run(str(tmp_path / "stackcore")) is False
