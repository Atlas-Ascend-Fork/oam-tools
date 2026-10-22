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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

"""看护安装包 cleanup 生命周期钩子脚本的删除安全性。

cleanup.sh 注册于 oam_tools.xml 的 <cleanup> 钩子，包管理器在卸载/升级时以解压
临时目录为当前目录执行它并整体删除该目录。历史实现直接 rm -rf "$(pwd)"，无任何
路径校验：脚本被手动执行或调用方 CWD 与预期不符时，会把当前目录（家目录、/ 等）
下全部内容递归删除。本用例两层看护：
1. 静态扫描：删除前必须解析物理路径并拒绝空路径与根目录，rm 须带 -- 并引用；
2. 行为验证：正常路径可整体删除目录树；CWD 为 / 时拒绝执行且不调用 rm。
"""

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
CLEANUP_SH = REPO_ROOT / "scripts" / "package" / "oam_tools" / "scripts" / "cleanup.sh"
_BASH = shutil.which("bash") or "/bin/bash"

# 与脚本内容强绑定的守卫片段：静态断言按此逐字匹配。
_TARGET_CAPTURE = 'target_dir="$(pwd -P)"'
_REJECT_GUARD = (
    '[ -z "${target_dir}" ] || [ "${target_dir}" = "/" ] || [ "${target_dir}" = "//" ]'
)


def get_cleanup_script_content():
    return CLEANUP_SH.read_text(encoding="utf-8")


def test_cleanup_script_validates_target_before_rm():
    # rm 之前必须先解析物理路径并拒绝空路径/根目录，且校验先于删除执行，
    # 否则脚本在错误目录执行时会递归删除该目录全部内容。
    content = get_cleanup_script_content()
    assert _TARGET_CAPTURE in content, "应通过 pwd -P 解析当前目录物理路径"
    assert _REJECT_GUARD in content, "必须拒绝空路径与根目录"
    assert content.find(_REJECT_GUARD) < content.find("rm -rf --"), (
        "路径校验必须位于 rm 执行之前"
    )


def test_cleanup_script_rm_uses_guarded_form():
    # rm 须带 --（防目标路径被解析为选项）并引用校验过的同一变量；
    # 不得回归为直接删除未校验的 $(pwd)。
    content = get_cleanup_script_content()
    assert 'chmod -R u+w "${target_dir}"' in content
    assert 'rm -rf -- "${target_dir}"' in content
    assert 'rm -rf "$(pwd)"' not in content
    assert "rm -rf $(pwd)" not in content


def test_cleanup_script_removes_staging_tree(tmp_path):
    # 行为验证（正常路径）：模拟包管理器以解压临时目录为 CWD 执行钩子，
    # 目录树（含 550 权限子目录，对应与正式安装路径对齐的场景）应被整体删除。
    staging = tmp_path / "staging"
    inner = staging / "tools"
    inner.mkdir(parents=True)
    (inner / "marker.txt").write_text("payload", encoding="utf-8")
    inner.chmod(0o550)

    package_script_dir = staging / "share/info/oam_tools/script"
    package_script_dir.mkdir(parents=True)
    package_script = package_script_dir / "cleanup.sh"
    shutil.copyfile(CLEANUP_SH, package_script)
    package_script.chmod(0o755)
    result = subprocess.run(
        [_BASH, str(package_script)],
        cwd=staging,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    # 删除前应打印待删除路径（可观测性要求）
    assert str(staging.resolve()) in result.stdout, "执行前应打印待删除的目标路径"
    assert not staging.exists(), "临时目录树应被整体删除"


def test_cleanup_script_refuses_double_slash_root_cwd(tmp_path):
    stub_dir = tmp_path / "stubs"
    stub_dir.mkdir()
    rm_log = tmp_path / "rm.log"
    chmod_log = tmp_path / "chmod.log"
    (stub_dir / "rm").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> {rm_log}\nexit 0\n', encoding="utf-8"
    )
    (stub_dir / "chmod").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> {chmod_log}\nexit 0\n',
        encoding="utf-8",
    )
    for name in ("rm", "chmod"):
        (stub_dir / name).chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
    env["PWD"] = "//"
    result = subprocess.run(
        [_BASH, "-c", 'cd // && exec bash "$0"', str(CLEANUP_SH)],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 1
    assert "[ERROR]" in result.stderr
    assert not rm_log.exists()
    assert not chmod_log.exists()


def test_cleanup_script_refuses_manual_execution_outside_package(tmp_path):
    result = subprocess.run(
        [_BASH, str(CLEANUP_SH)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1
    assert "[ERROR]" in result.stderr
    assert "lifecycle path" in result.stderr


def test_cleanup_script_refuses_root_cwd(tmp_path):
    # 行为验证（拒绝路径）：CWD 为 / 时必须退出非零且不调用 rm。
    # 即便脚本回归为无校验版本，PATH 前置的 rm/chmod 桩也会拦截真实删除，
    # 保证本用例在任何实现下都不会触碰文件系统。
    stub_dir = tmp_path / "stubs"
    stub_dir.mkdir()
    rm_log = tmp_path / "rm.log"
    chmod_log = tmp_path / "chmod.log"
    (stub_dir / "rm").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> {rm_log}\nexit 0\n', encoding="utf-8"
    )
    (stub_dir / "chmod").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> {chmod_log}\nexit 0\n',
        encoding="utf-8",
    )
    for name in ("rm", "chmod"):
        (stub_dir / name).chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        [_BASH, str(CLEANUP_SH)],
        cwd="/",
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 1, "CWD 为根目录时必须拒绝执行"
    assert "[ERROR]" in result.stderr, "拒绝时应输出明确的错误提示"
    assert not rm_log.exists(), "拒绝路径不得调用 rm"
    assert not chmod_log.exists(), "拒绝路径不得调用 chmod"
