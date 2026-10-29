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
"""Check bundle branch selection with real Git histories and CMake."""

import importlib.util
import os
from pathlib import Path
import re
import subprocess
import shutil

import pytest

REPO = Path(os.environ.get("OAM_BUNDLE_TEST_ROOT", Path(__file__).resolve().parents[2]))
SPEC = importlib.util.spec_from_file_location(
    "offline_download", REPO / "cmake/download_libs.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CMAKE = shutil.which("cmake")


@pytest.fixture
def history(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init", "-q")
    git(
        "-c",
        "user.name=Local fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "common base",
    )
    base = git("rev-parse", "HEAD")
    git(
        "-c",
        "user.name=Local fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "release-only commit",
    )
    release = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/master", base)
    git("update-ref", "refs/remotes/origin/9.1.0", release)
    return tmp_path, git, base, release


@pytest.mark.parametrize("feature_commits", [0, 1])
@pytest.mark.parametrize("selected", ["master", "9.1.0"])
@pytest.mark.parametrize("implementation", ["python", "cmake"])
def test_prefers_closer_ref_when_ahead_counts_tie(
    history, monkeypatch, selected, implementation, feature_commits
):
    root, git, base, release = history
    git("checkout", "--detach", base if selected == "master" else release)
    if feature_commits:
        git(
            "-c",
            "user.name=Local fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "feature commit",
        )
    if implementation == "python":
        monkeypatch.chdir(root)
        assert MODULE.detect_bundle_branch() == selected
    else:
        if CMAKE is None:
            pytest.skip("CMake is required")
        text = (REPO / "cmake/install_bundle.cmake").read_text(encoding="utf-8")
        prefix = text[: text.index("function(oam_resolve_bundle_branch")]
        function = re.search(
            r"^function\(oam_resolve_bundle_branch RESULT_VAR\).*?^endfunction\(\)",
            text,
            re.MULTILINE | re.DOTALL,
        ).group()
        driver = root / "branch.cmake"
        driver.write_text(
            "cmake_minimum_required(VERSION 3.18)\n"
            + prefix
            + function
            + f'\nset(OAM_TOOLS_DIR "{root.as_posix()}")\n'
            'oam_resolve_bundle_branch(chosen)\nmessage(STATUS "CHOSEN=${chosen}")\n',
            encoding="utf-8",
        )
        result = subprocess.run(
            [str(CMAKE), "-P", str(driver)], capture_output=True, text=True, check=True
        )
        assert f"CHOSEN={selected}" in result.stdout, result.stdout
        assert f"(ahead {feature_commits}, behind 0)" in result.stdout, result.stdout
