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
ST: upgrade – validates re-installation (upgrade) of oam-tools over an existing install.

Tested scenarios:
  1. --full  → --full  (same type upgrade)
  2. --run   → --full  (type change upgrade)
  3. --full  → --run   (type change upgrade)
  4. --devel → --full  (type change upgrade)

For each scenario the first install is the baseline; the SECOND install (upgrade)
is what is checked for exit code and errors.

Note: the installer always emits [WARNING] lines when upgrading over an existing
installation ("Install folder has files existed") – this is by-design behaviour and
is therefore not checked in upgrade tests.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

_BASH = shutil.which("bash") or "/bin/bash"

_ERROR_KW = "[ERROR]"


def _run(run_package, install_dir, install_type):
    cmd = [_BASH, run_package, install_type, "--quiet", f"--install-path={install_dir}"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def _output(result):
    return result.stdout + result.stderr


def _assert_script_layout(script_dir, optional_bin, phase):
    """issue #317: script 必须是目录、bin 不得以任何链接形态残留。phase 仅用于失败信息。"""
    assert script_dir.is_dir(), f"Expected a script directory{phase}: {script_dir}"
    assert not os.path.lexists(optional_bin), f"Unexpected bin path{phase}: {optional_bin}"


_UPGRADE_SCENARIOS = [
    ("--full", "--full"),
    ("--run", "--full"),
    ("--full", "--run"),
    ("--devel", "--full"),
]


@pytest.mark.parametrize(
    "script_form, expected_message",
    [
        ("regular-file", "Expected a script directory"),
        ("dangling-bin", "Unexpected bin path"),
        ("normal-dir", None),
        ("missing", "Expected a script directory"),
    ],
)
def test_script_layout_guard(tmp_path, script_form, expected_message):
    # issue #317 回归：同权限普通文件伪装 script 与 bin 悬空软链必须被拒绝，
    # 正常目录是唯一通过形态（PR #784 检视意见：新增断言需主机侧看护）。
    info = tmp_path / "cann/share/info/oam_tools"
    script_dir = info / "script"
    optional_bin = info / "bin"
    if script_form == "regular-file":
        info.mkdir(parents=True)
        script_dir.touch(mode=0o750)
    elif script_form == "dangling-bin":
        info.mkdir(parents=True)
        script_dir.mkdir()
        optional_bin.symlink_to(info / "missing-target")
    elif script_form == "normal-dir":
        info.mkdir(parents=True)
        script_dir.mkdir()
    if expected_message is None:
        _assert_script_layout(script_dir, optional_bin, "")
        return
    with pytest.raises(AssertionError, match=expected_message):
        _assert_script_layout(script_dir, optional_bin, "")


class TestUpgrade:
    @pytest.mark.parametrize(
        "first_type,upgrade_type",
        _UPGRADE_SCENARIOS,
        ids=[f"{a}->{b}" for a, b in _UPGRADE_SCENARIOS],
    )
    def test_upgrade(self, run_package, install_dir, first_type, upgrade_type):
        r1 = _run(run_package, install_dir, first_type)
        assert r1.returncode == 0, (
            f"Baseline '{first_type}' install failed:\n{_output(r1)}"
        )
        script_dir = Path(install_dir) / "cann/share/info/oam_tools/script"
        optional_bin = script_dir.parent / "bin"
        expected_mode = 0o755 if os.geteuid() == 0 else 0o750
        _assert_script_layout(script_dir, optional_bin, "")
        initial_mode = stat.S_IMODE(script_dir.stat().st_mode)
        owner_before = (script_dir.stat().st_uid, script_dir.stat().st_gid)
        assert initial_mode == expected_mode

        r2 = _run(run_package, install_dir, upgrade_type)
        out = _output(r2)
        assert r2.returncode == 0, (
            f"Upgrade '{first_type}→{upgrade_type}' exited {r2.returncode}:\n{out}"
        )
        assert _ERROR_KW not in out, (
            f"Upgrade '{first_type}→{upgrade_type}' output contains {_ERROR_KW!r}:\n{out}"
        )
        _assert_script_layout(script_dir, optional_bin, " after upgrade")
        assert stat.S_IMODE(script_dir.stat().st_mode) == initial_mode
        assert (script_dir.stat().st_uid, script_dir.stat().st_gid) == owner_before

    def test_upgrade_with_optional_bin(self, run_package, install_dir):
        r1 = _run(run_package, install_dir, "--run")
        assert r1.returncode == 0, f"Baseline '--run' install failed:\n{_output(r1)}"

        info_dir = Path(install_dir) / "cann/share/info/oam_tools"
        original_info_mode = stat.S_IMODE(info_dir.stat().st_mode)
        info_dir.chmod(original_info_mode | stat.S_IWUSR)
        bin_dir = info_dir / "bin"
        tool = bin_dir / "subdir/tool"
        tool.parent.mkdir(parents=True)
        tool.touch()
        bin_dir.chmod(0o711)
        tool.parent.chmod(0o700)
        tool.chmod(0o600)
        owner_before = {
            path: (path.stat().st_uid, path.stat().st_gid)
            for path in (bin_dir, tool.parent, tool)
        }
        info_dir.chmod(original_info_mode)

        r2 = _run(run_package, install_dir, "--full")
        out = _output(r2)
        assert r2.returncode == 0, (
            f"Upgrade '--run→--full' exited {r2.returncode}:\n{out}"
        )
        assert _ERROR_KW not in out

        # bin 和 subdir 目录期望 755/750
        expected_bin_mode = 0o755 if os.geteuid() == 0 else 0o750
        for path in (bin_dir, tool.parent):
            assert stat.S_IMODE(path.stat().st_mode) == expected_bin_mode
            assert (path.stat().st_uid, path.stat().st_gid) == owner_before[path]

        # tool 文件权限保持不变
        expected_file_mode = 0o600
        assert stat.S_IMODE(tool.stat().st_mode) == expected_file_mode
        assert (tool.stat().st_uid, tool.stat().st_gid) == owner_before[tool]
