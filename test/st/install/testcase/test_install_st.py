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
ST: install – validates the oam-tools .run package installation and extraction.

Tested command forms:
  ./cann-oam-tools_<ver>_linux-<arch>.run --full  --quiet --install-path=<dir>
  ./cann-oam-tools_<ver>_linux-<arch>.run --run   --quiet --install-path=<dir>
  ./cann-oam-tools_<ver>_linux-<arch>.run --devel --quiet --install-path=<dir>
  ./cann-oam-tools_<ver>_linux-<arch>.run --noexec --extract=<dir>

Checks:
  - Exit code is 0
  - No [ERROR] in combined stdout + stderr
  - Key installed artefacts exist on disk after successful install

[WARNING] lines are deliberately not asserted on: the installer treats them as
non-fatal advisories (parent-dir owner/mode != root/755, install dir already
populated, ver_check soft failures, etc.) and emits them on environments that
are perfectly fine for a successful install. Failing the suite on any WARNING
elevates these advisories to errors, which contradicts the installer contract
and makes the suite environment-fragile.
"""

import os
import platform
import re
import shutil
import subprocess

import pytest

_BASH = shutil.which("bash") or "/bin/bash"

_LOG_GUARD_PATTERNS = (
    ("permission denied", re.compile(r"permission\s+d(?:enied|eined)", re.IGNORECASE)),
    ("no such file or directory", re.compile(r"no such file or directory", re.IGNORECASE)),
    ("error", re.compile(r"\berror\b", re.IGNORECASE)),
    ("not found", re.compile(r"\bnot found\b", re.IGNORECASE)),
    ("unexpected/unexcepted", re.compile(r"\bun(?:expected|excepted)\b", re.IGNORECASE)),
    ("failed", re.compile(r"\bfailed\b", re.IGNORECASE)),
)


def _run(run_package, install_dir, install_type, extra_args=None):
    """Execute the .run package and return CompletedProcess."""
    cmd = [_BASH, run_package, install_type, "--quiet",
           f"--install-path={install_dir}"]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def _output(result):
    return result.stdout + result.stderr


def _assert_clean_log(result, operation):
    """Fail when installer output contains a known error indicator."""
    matches = []
    for line in _output(result).splitlines():
        matched = [name for name, pattern in _LOG_GUARD_PATTERNS if pattern.search(line)]
        if matched:
            matches.append(f"[{', '.join(matched)}] {line}")
    assert not matches, (
        f"{operation} output contains guarded error indicators:\n"
        + "\n".join(matches)
    )


class TestInstallArtefacts:
    @staticmethod
    @pytest.mark.parametrize("install_type", ["--full", "--run", "--devel"])
    def test_install_artefacts(run_package, install_dir, install_type):
        result = _run(run_package, install_dir, install_type)
        assert result.returncode == 0, (
            f"'{install_type}' install exited {result.returncode}:\n{_output(result)}"
        )
        _assert_clean_log(result, f"'{install_type}' install")

        info_dir = os.path.join(install_dir, "cann", "share", "info", "oam_tools")
        assert os.path.isdir(info_dir), f"Missing oam_tools info dir: {info_dir}"

        install_info = os.path.join(info_dir, "ascend_install.info")
        assert os.path.isfile(install_info), f"Missing ascend_install.info: {install_info}"

        arch = platform.machine()
        version_h = os.path.join(
            install_dir, "cann", f"{arch}-linux",
            "include", "version", "oam_tools_version.h"
        )
        assert os.path.isfile(version_h), f"Missing version header: {version_h}"

        uninstall_sh = os.path.join(install_dir, "cann", "cann_uninstall.sh")
        assert os.path.isfile(uninstall_sh), f"Missing cann_uninstall.sh: {uninstall_sh}"


class TestExtract:
    @staticmethod
    def test_extract(run_package, install_dir):
        extract_dir = os.path.join(install_dir, "extract")
        result = subprocess.run(
            [_BASH, run_package, "--noexec", f"--extract={extract_dir}"],
            capture_output=True, text=True, timeout=180,
        )
        out = _output(result)

        assert result.returncode == 0, (
            f"--noexec --extract exited {result.returncode}:\n{out}"
        )
        _assert_clean_log(result, "--noexec --extract")
        assert os.path.isdir(extract_dir), (
            f"Extract target directory was not created: {extract_dir}"
        )


def _collect_tree(root):
    """Return a set of (rel_path, kind) entries under root.

    kind is 'd' for directories and 'f' for regular files; symlinks are skipped.
    """
    entries = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for d in dirnames:
            full = os.path.join(dirpath, d)
            if os.path.islink(full):
                continue
            entries.add((os.path.relpath(full, root), "d"))
        for f in filenames:
            full = os.path.join(dirpath, f)
            if os.path.islink(full):
                continue
            entries.add((os.path.relpath(full, root), "f"))
    return entries


class TestExtractInstallConsistency:
    """看护解压和安装后共有文件夹的文件目录树保持一致。

    --noexec --extract 产生的 staging 目录树应当与 --full 安装产生的
    ${install}/cann/ 目录树在共有路径上保持一致（解压目录是安装目录的子集）。
    特别关注 tools/profiler/profiler_tool 子树（msprof whl 解包目标）。
    """

    @staticmethod
    def test_extract_subset_of_install(run_package, install_dir):
        extract_dir = os.path.join(install_dir, "extract")
        install_root = os.path.join(install_dir, "install_root")
        os.makedirs(install_root, exist_ok=True)

        extract_res = subprocess.run(
            [_BASH, run_package, "--noexec", f"--extract={extract_dir}"],
            capture_output=True, text=True, timeout=180,
        )
        assert extract_res.returncode == 0, (
            f"--noexec --extract failed: {_output(extract_res)}"
        )
        _assert_clean_log(extract_res, "--noexec --extract")

        install_res = _run(run_package, install_root, "--full")
        assert install_res.returncode == 0, (
            f"--full install failed: {_output(install_res)}"
        )
        _assert_clean_log(install_res, "--full install")

        installed_cann = os.path.join(install_root, "cann")
        assert os.path.isdir(installed_cann), (
            f"Expected cann install root not found: {installed_cann}"
        )

        extract_entries = _collect_tree(extract_dir)
        install_entries = _collect_tree(installed_cann)

        missing = extract_entries - install_entries
        assert not missing, (
            "Entries present after --noexec --extract but missing in "
            f"--full install root: {sorted(missing)[:20]}"
        )

    @staticmethod
    def test_profiler_tool_tree_matches(run_package, install_dir):
        extract_dir = os.path.join(install_dir, "extract")
        install_root = os.path.join(install_dir, "install_root")
        os.makedirs(install_root, exist_ok=True)

        extract_res = subprocess.run(
            [_BASH, run_package, "--noexec", f"--extract={extract_dir}"],
            capture_output=True, text=True, timeout=180,
        )
        assert extract_res.returncode == 0, (
            f"--noexec --extract failed: {_output(extract_res)}"
        )
        _assert_clean_log(extract_res, "--noexec --extract")
        install_res = _run(run_package, install_root, "--full")
        assert install_res.returncode == 0, (
            f"--full install failed: {_output(install_res)}"
        )
        _assert_clean_log(install_res, "--full install")

        rel = os.path.join("tools", "profiler", "profiler_tool")
        extract_subtree_root = os.path.join(extract_dir, rel)
        install_subtree_root = os.path.join(install_root, "cann", rel)

        assert os.path.isdir(extract_subtree_root), (
            f"profiler_tool missing in extract dir: {extract_subtree_root}"
        )
        assert os.path.isdir(install_subtree_root), (
            f"profiler_tool missing in install dir: {install_subtree_root}"
        )

        # __pycache__ 由运行期 compileall 用目标机 python3 生成（cmake 构建期已
        # 把 staging 里的 .pyc 清掉，避免锁死在构建机 Python 版本），因此解压目录
        # 无 __pycache__、安装目录有。比较时排除该子树。
        def _drop_pycache(entries):
            return {(p, k) for (p, k) in entries
                    if "__pycache__" not in p.split(os.sep)}

        extract_subtree = _drop_pycache(_collect_tree(extract_subtree_root))
        install_subtree = _drop_pycache(_collect_tree(install_subtree_root))

        assert extract_subtree == install_subtree, (
            "profiler_tool subtree differs between extract and install "
            "(ignoring __pycache__).\n"
            f"only in extract: {sorted(extract_subtree - install_subtree)[:20]}\n"
            f"only in install: {sorted(install_subtree - extract_subtree)[:20]}"
        )
