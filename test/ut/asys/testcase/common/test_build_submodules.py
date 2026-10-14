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

"""cmake/build_submodules.cmake 中 msprof analysis 架构映射的看护。

本地 run 包与每日构建包名统一为 x86。用例锁定本地包匹配、每日构建 URL
与 so 架构校验使用同一个架构变量，避免包名再次漂移。
"""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
BUILD_SUBMODULES_CMAKE = REPO_ROOT / "cmake" / "build_submodules.cmake"


def get_cmake_content():
    return BUILD_SUBMODULES_CMAKE.read_text(encoding="utf-8")


def get_arch_mapping_block():
    content = get_cmake_content()
    match = re.search(
        r"# 2\. 架构映射。(?P<block>.*?)\n    # 3\. 临时目录", content, re.S
    )
    assert match is not None, "未找到架构映射代码块"
    return match.group("block")


def test_x86_package_name_uses_single_arch_variable():
    """x86_64/amd64 输入必须统一映射到 x86 包名。"""
    block = get_arch_mapping_block()
    assert 'set(_pkg_arch "x86")' in block, "每日构建包名应保持 x86"
    assert "_local_arch" not in block, "本地包名与每日构建包名一致，应复用 _pkg_arch"


def test_local_package_glob_uses_pkg_arch():
    """本地 mindstudio-profiler_*_x86.run 匹配必须使用 _pkg_arch。"""
    content = get_cmake_content()
    match = re.search(r"file\(GLOB _local_run_pkgs.*?\)", content, re.S)
    assert match is not None, "未找到本地 run 包 file(GLOB) 声明"
    assert "${_pkg_arch}" in match.group(0), "本地包匹配应复用 _pkg_arch"


def test_x86_so_check_uses_same_arch_variable():
    """x86 包名调整后，so 架构校验条件必须同步。"""
    content = get_cmake_content()
    match = re.search(
        r"if\(_pkg_arch STREQUAL \"x86\" AND NOT _so_file_out MATCHES \"x86-64\"\)",
        content,
    )
    assert match is not None, "so 架构校验仍使用旧 x86 条件，x86 包校验会被跳过"


def test_arm_mapping_keeps_aarch64():
    """aarch64/arm64 输入保持 aarch64 包名。"""
    block = get_arch_mapping_block()
    assert block.count('set(_pkg_arch "aarch64")') == 1


def test_arch_aliases_are_kept():
    """保留 x86_64/amd64 与 aarch64/arm64 别名，避免宿主机命名差异走失败分支。"""
    block = get_arch_mapping_block()
    assert '_machine STREQUAL "x86_64" OR _machine STREQUAL "amd64"' in block
    assert '_machine STREQUAL "aarch64" OR _machine STREQUAL "arm64"' in block
