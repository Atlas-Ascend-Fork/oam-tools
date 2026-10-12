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

from collect.coretrace import coretrace_collect  # noqa: E402


def test_coretrace_run_checks_addr2line_before_starting_workers(monkeypatch, tmp_path):
    parser = coretrace_collect.ParseCoreTrace(None)
    called = []

    monkeypatch.setattr(
        coretrace_collect.f,
        "walk_dir",
        lambda _path: [(str(tmp_path), [], ["coretrace_sample.txt"])],
    )
    monkeypatch.setattr(parser, "check_tool_exists", lambda: False)
    monkeypatch.setattr(
        parser,
        "save_file_result",
        lambda *_args: called.append(True),
    )

    assert parser.run(str(tmp_path / "coretrace")) is False
    assert called == []
