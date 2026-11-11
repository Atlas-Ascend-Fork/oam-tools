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
"""
ST: uninstall – validates oam-tools uninstallation via two methods:

  Method A: ./cann-oam-tools_<ver>.run --uninstall --quiet --install-path=<dir>
  Method B: <install_dir>/cann/cann_uninstall.sh   (no arguments – script rejects all args)

Each test:
  1. Verifies the uninstall command exits with code 0
  2. Verifies no [ERROR] appears in combined stdout + stderr
  3. Verifies no oam-tools specific files/dirs remain (no residuals)
"""

import os
import platform
import shutil
import subprocess

import pytest

_BASH = shutil.which("bash") or "/bin/bash"
_CHMOD = shutil.which("chmod") or "/bin/chmod"

_ERROR_KW = "[ERROR]"


def _output(result):
    return result.stdout + result.stderr


def _force_writable(path):
    """Unlock any read-only directories so os.walk / rmdir work correctly."""
    subprocess.run([_CHMOD, "-R", "u+w", path], check=False, capture_output=True)


def _residual_candidates(install_path):
    """
    Return paths under install_path that belong to oam-tools and should not
    remain after a clean uninstall.

    Checks:
      - cann/share/info/oam_tools/          (oam-tools install-info directory)
      - cann/<arch>-linux/include/aclnnop/  (SDK header directory)
      - cann/<arch>-linux/include/version/oam_tools_version.h
      - cann/<arch>-linux/lib64/libopapi_oam.so
    """
    arch = platform.machine()
    arch_linux = os.path.join(install_path, "cann", f"{arch}-linux")

    candidates = [
        os.path.join(install_path, "cann", "share", "info", "oam_tools"),
        os.path.join(arch_linux, "include", "aclnnop"),
        os.path.join(arch_linux, "include", "version", "oam_tools_version.h"),
        os.path.join(arch_linux, "lib64", "libopapi_oam.so"),
    ]
    return candidates


def _collect_residuals(install_path):
    """Return candidate paths that still exist after uninstallation."""
    return [p for p in _residual_candidates(install_path) if os.path.lexists(p)]


@pytest.mark.parametrize("candidate_index", range(len(_residual_candidates("."))))
def test_collect_residuals_reports_dangling_symlink(tmp_path, candidate_index):
    residual = _residual_candidates(str(tmp_path))[candidate_index]
    os.makedirs(os.path.dirname(residual), exist_ok=True)
    os.symlink(str(tmp_path / "missing-target"), residual)

    assert _collect_residuals(str(tmp_path)) == [residual]


@pytest.mark.parametrize("candidate_index", range(len(_residual_candidates("."))))
def test_collect_residuals_reports_regular_file(tmp_path, candidate_index):
    # 正向对照：普通文件残留同样必须被报告——防止判据回退为 os.path.islink
    # 之类只覆盖链接形态的写法（PR #913 检视意见：断链用例对该变异体无区分力）。
    residual = _residual_candidates(str(tmp_path))[candidate_index]
    os.makedirs(os.path.dirname(residual), exist_ok=True)
    open(residual, "w").close()
    assert _collect_residuals(str(tmp_path)) == [residual]


# ---------------------------------------------------------------------------
# Method A: run --uninstall
# ---------------------------------------------------------------------------

class TestUninstallViaRunPackage:
    @staticmethod
    def test_uninstall(run_package, installed_dir):
        result = subprocess.run(
            [_BASH, run_package, "--uninstall", "--quiet",
             f"--install-path={installed_dir}"],
            capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 0, (
            f"--uninstall exited {result.returncode}:\n{_output(result)}"
        )

        out = _output(result)
        assert _ERROR_KW not in out, (
            f"--uninstall output contains {_ERROR_KW!r}:\n{out}"
        )

        residuals = _collect_residuals(installed_dir)
        assert not residuals, (
            "Residual oam-tools files/dirs found after --uninstall:\n"
            + "\n".join(f"  {p}" for p in residuals)
        )


# ---------------------------------------------------------------------------
# Method B: cann_uninstall.sh
# ---------------------------------------------------------------------------

class TestUninstallViaCannUninstallSh:


    @staticmethod
    def _find_cann_uninstall(install_path):
        uninstall_sh = os.path.join(install_path, "cann", "cann_uninstall.sh")
        if not os.path.isfile(uninstall_sh):
            pytest.fail(
                f"cann_uninstall.sh not found at expected path: {uninstall_sh}\n"
                "Was the install step successful?"
            )
        return uninstall_sh

    def test_uninstall(self, installed_dir):
        uninstall_sh = self._find_cann_uninstall(installed_dir)
        result = subprocess.run(
            [_BASH, uninstall_sh],
            capture_output=True, text=True, timeout=180,
            cwd=installed_dir,
        )
        assert result.returncode == 0, (
            f"cann_uninstall.sh exited {result.returncode}:\n{_output(result)}"
        )

        out = _output(result)
        assert _ERROR_KW not in out, (
            f"cann_uninstall.sh output contains {_ERROR_KW!r}:\n{out}"
        )

        residuals = _collect_residuals(installed_dir)
        assert not residuals, (
            "Residual oam-tools files/dirs found after cann_uninstall.sh:\n"
            + "\n".join(f"  {p}" for p in residuals)
        )
