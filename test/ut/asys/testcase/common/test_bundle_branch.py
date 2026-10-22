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

"""闭源包(bundle)分支解析的测试：build.sh 透传、cmake 三级决策、离线预置校验。

cmake 部分不做字符串匹配，而是真正跑 cmake 求值 oam_resolve_bundle_branch()，
这样 ahead-count 探测、白名单校验等逻辑的实际行为才被覆盖。
"""

import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[5]
INSTALL_BUNDLE_CMAKE = REPO_ROOT / "cmake" / "install_bundle.cmake"

GIT = shutil.which("git")
CMAKE = shutil.which("cmake")


def get_build_script_content():
    return (REPO_ROOT / "build.sh").read_text(encoding="utf-8")


# ---------------------------------------------------------------- build.sh 透传


def test_bundle_branch_passed_without_quotes():
    # CMAKE_ARGS 在 cmake_generate_make 里是 cmake ${cmake_args} .. 非引号展开，
    # 若给取值套引号，引号会作为字面量进入 CMake，白名单校验必然失配。
    build_content = get_build_script_content()
    assert "-DOAM_BUNDLE_BRANCH=${BUNDLE_BRANCH}" in build_content, (
        "应以不加引号的形式透传 OAM_BUNDLE_BRANCH"
    )
    assert '-DOAM_BUNDLE_BRANCH=\\"${BUNDLE_BRANCH}\\"' not in build_content, (
        "不应把转义引号拼入 CMake 参数（引号会成为字面量）"
    )


def test_bundle_branch_only_passed_when_explicit():
    # 不指定 --bundle_branch 时不得透传，否则会盖掉 cmake 配置期的 git 探测。
    build_content = get_build_script_content()
    match = re.search(
        r'if \[ -n "\$\{BUNDLE_BRANCH\}" \]; then\n(?P<body>.*?)\n    fi',
        build_content,
        re.S,
    )
    assert match is not None, "OAM_BUNDLE_BRANCH 应仅在 BUNDLE_BRANCH 非空时透传"
    assert "OAM_BUNDLE_BRANCH" in match.group("body")


def test_bundle_branch_initialized_in_checkopts():
    # 环境里的同名变量不得被当作"用户显式指定"：否则既盖掉配置期 git 探测，
    # 又绕过 --bundle_branch 解析处的字符校验（透传未校验的取值）。
    build_content = get_build_script_content()
    checkopts = re.search(
        r"^checkopts\(\) \{\n(?P<body>.*?)^\}", build_content, re.S | re.M
    )
    assert checkopts is not None, "build.sh 应有 checkopts() 函数"
    init_part = checkopts.group("body").split("parsed_args=", 1)[0]
    assert 'BUNDLE_BRANCH=""' in init_part, (
        "BUNDLE_BRANCH 应在 checkopts 解析选项前显式清空，避免继承环境变量"
    )


def test_bundle_branch_value_is_validated():
    # 取值未加引号，故必须在解析处拒绝含空格/shell 元字符的分支名。
    build_content = get_build_script_content()
    assert "^[A-Za-z0-9._/-]+$" in build_content, (
        "--bundle_branch 取值应做字符白名单校验"
    )


@pytest.mark.parametrize(
    "value,accepted",
    [
        ("master", True),
        ("9.1.0", True),
        ("release/1.0", True),
        ("bad name", False),
        ('x";rm -rf /', False),
        ("", False),
    ],
)
def test_bundle_branch_validation_regex_behavior(value, accepted):
    # 直接验证正则本身的接受/拒绝行为，避免只断言"字面量存在"。
    assert bool(re.fullmatch(r"[A-Za-z0-9._/-]+", value)) is accepted


# ------------------------------------------------- cmake 分支解析（真实求值）


def _run_resolve(tmp_path, *, explicit=None, refs=(), with_git=True):
    """在临时 git 仓里真正调用 oam_resolve_bundle_branch()，返回解析出的分支。

    refs: 要创建的分支名序列（模拟 origin/master、origin/9.1.0-beta.2 是否存在）。
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
    subprocess.run([GIT, "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run([GIT, "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "f").write_text("1", encoding="utf-8")
    subprocess.run([GIT, "add", "."], cwd=repo, check=True)
    subprocess.run([GIT, "commit", "-qm", "base"], cwd=repo, check=True)
    for ref in refs:
        # 用 update-ref 直接造出 refs/remotes/origin/<name>，模拟已 fetch 的远端分支。
        subprocess.run(
            [GIT, "update-ref", f"refs/remotes/{ref}", "HEAD"], cwd=repo, check=True
        )

    # install_bundle.cmake 末尾会调用 oam_install_bundle()（会联网下载），
    # 这里只取函数定义部分，单独求值分支解析逻辑。
    content = INSTALL_BUNDLE_CMAKE.read_text(encoding="utf-8")
    content = content.replace("oam_install_bundle()\n", "")

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "bundle_funcs.cmake").write_text(content, encoding="utf-8")
    (proj / "CMakeLists.txt").write_text(
        textwrap.dedent(f"""
        cmake_minimum_required(VERSION 3.14)
        project(bundle_branch_probe NONE)
        set(OAM_TOOLS_DIR "{repo.as_posix()}")
        include(${{CMAKE_CURRENT_SOURCE_DIR}}/bundle_funcs.cmake)
        oam_resolve_bundle_branch(_resolved)
        message(STATUS "RESOLVED=${{_resolved}}")
    """),
        encoding="utf-8",
    )

    args = [CMAKE, "-S", str(proj), "-B", str(tmp_path / "build")]
    if explicit is not None:
        args.append(f"-DOAM_BUNDLE_BRANCH={explicit}")
    if not with_git:
        # 强制 git 不可用，验证兜底路径。
        args.append("-DGIT_EXECUTABLE=")
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    match = re.search(r"RESOLVED=(\S*)", result.stdout)
    assert match, f"cmake 未输出解析结果:\n{result.stdout}\n{result.stderr}"
    return match.group(1)


@pytest.mark.skipif(not GIT or not CMAKE, reason="需要 git 与 cmake")
def test_resolve_explicit_takes_precedence(tmp_path):
    # 显式指定优先于 git 探测：即便 origin/master 存在也应取显式值。
    assert _run_resolve(tmp_path, explicit="9.1.0", refs=("origin/master",)) == "9.1.0"


@pytest.mark.skipif(not GIT or not CMAKE, reason="需要 git 与 cmake")
@pytest.mark.parametrize(
    "ref_name",
    [
        "9.1.0",
        "9.1.0-beta.1",
        "9.1.0-beta.2",
        "9.1.0-beta.3",
    ],
)
def test_resolve_detects_910_line(tmp_path, ref_name):
    # 同一发布线并存 9.1.0 与 9.1.0-beta.N 多个分支，任一存在都应归一到 OBS 名 9.1.0。
    # 早期实现只硬编码了 origin/9.1.0-beta.2，其余分支会探测不到而静默回退 master。
    assert _run_resolve(tmp_path, refs=(f"origin/{ref_name}",)) == "9.1.0"


@pytest.mark.skipif(not GIT or not CMAKE, reason="需要 git 与 cmake")
def test_resolve_ignores_branch_without_obs_package(tmp_path):
    # 9.2.0 线 OBS 上还没包，不应被探测出来（否则必然触发白名单 FATAL_ERROR）。
    assert _run_resolve(tmp_path, refs=("origin/9.2.0-beta.1",)) == "master"


@pytest.mark.skipif(not GIT or not CMAKE, reason="需要 git 与 cmake")
def test_resolve_detects_release_line_on_non_origin_remote(tmp_path):
    # fork 场景下发布线常只在 upstream 上，不应因 remote 名不是 origin 而漏掉。
    assert _run_resolve(tmp_path, refs=("upstream/9.1.0-beta.3",)) == "9.1.0"


@pytest.mark.skipif(not GIT or not CMAKE, reason="需要 git 与 cmake")
def test_resolve_detects_master(tmp_path):
    assert _run_resolve(tmp_path, refs=("origin/master",)) == "master"


@pytest.mark.skipif(not GIT or not CMAKE, reason="需要 git 与 cmake")
def test_resolve_falls_back_when_no_ref(tmp_path):
    # 候选 ref 都不存在（如浅克隆/未 fetch release 线）时兜底 master。
    assert _run_resolve(tmp_path, refs=()) == "master"


@pytest.mark.skipif(not GIT or not CMAKE, reason="需要 git 与 cmake")
def test_resolve_falls_back_without_git(tmp_path):
    # git 不可用时跳过探测、兜底 master，保持无 git 环境的原有行为。
    assert (
        _run_resolve(tmp_path, refs=("origin/9.1.0-beta.2",), with_git=False)
        == "master"
    )


# ------------------------------------- 已有 bundle 目录的分支校验（真实求值）


def _run_install_with_existing_bundle(tmp_path, *, present_branch, explicit):
    """预置一个非空 bundle 目录后真正跑 oam_install_bundle()，返回 cmake 结果。

    非空 bundle 会命中"跳过下载"分支并直接 return，故不会联网。
    present_branch=None 模拟本改动之前拉下的、没有元数据的旧 bundle。
    """
    repo = tmp_path / "repo"
    bundle = repo / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "aml").mkdir()
    if present_branch is not None:
        (bundle / ".bundle_branch").write_text(f"{present_branch}\n", encoding="utf-8")

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "bundle_funcs.cmake").write_text(
        INSTALL_BUNDLE_CMAKE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (proj / "CMakeLists.txt").write_text(
        textwrap.dedent(f"""
        cmake_minimum_required(VERSION 3.14)
        project(bundle_reuse_probe NONE)
        set(OAM_TOOLS_DIR "{repo.as_posix()}")
        include(${{CMAKE_CURRENT_SOURCE_DIR}}/bundle_funcs.cmake)
    """),
        encoding="utf-8",
    )

    return subprocess.run(
        [
            CMAKE,
            "-S",
            str(proj),
            "-B",
            str(tmp_path / "build"),
            f"-DOAM_BUNDLE_BRANCH={explicit}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(not CMAKE, reason="需要 cmake")
def test_existing_bundle_matching_branch_is_reused(tmp_path):
    # 分支一致时照旧复用，不应因新增校验而误报。
    result = _run_install_with_existing_bundle(
        tmp_path, present_branch="9.1.0", explicit="9.1.0"
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "skip download" in result.stdout


@pytest.mark.skipif(not CMAKE, reason="需要 cmake")
def test_existing_bundle_wrong_branch_is_rejected(tmp_path):
    # 从 master 构建后切到 9.1.0 直接 build.sh：旧 bundle 必须被拒而非静默复用。
    result = _run_install_with_existing_bundle(
        tmp_path, present_branch="master", explicit="9.1.0"
    )
    assert result.returncode != 0, "分支不一致的已有 bundle 应在配置阶段报错"
    combined = result.stdout + result.stderr
    assert "existing bundle" in combined and "master" in combined
    assert "--make_clean" in combined, "报错应提示如何刷新 bundle"


@pytest.mark.skipif(not CMAKE, reason="需要 cmake")
def test_existing_bundle_without_metadata_warns(tmp_path):
    # 本改动之前拉下的 bundle 没有元数据：告警但不阻断，
    # 否则既有工作目录都得先 --make_clean 才能继续构建。
    result = _run_install_with_existing_bundle(
        tmp_path, present_branch=None, explicit="9.1.0"
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "no .bundle_branch" in (result.stdout + result.stderr)


# ------------------------------------------------------- 白名单与离线包校验


def test_known_branches_whitelist_declared():
    # 白名单是防止拼出 OBS 上不存在的地址、下载到 403 空包的硬门禁。
    content = INSTALL_BUNDLE_CMAKE.read_text(encoding="utf-8")
    assert 'set(OAM_BUNDLE_KNOWN_BRANCHES "master" "9.1.0")' in content
    assert "IN_LIST OAM_BUNDLE_KNOWN_BRANCHES" in content, "应对解析结果做白名单校验"
    assert "FATAL_ERROR" in content, "白名单不命中应在配置阶段直接报错"


def test_whitelist_hint_has_no_shell_metachars():
    # 提示语会被用户整行复制到终端，含 <> 会被 shell 当重定向解析。
    # 只检查 FATAL_ERROR 消息正文与拼装 _hint 的语句：注释里为说明"为何不用尖括号"
    # 会出现 --bundle_branch=<name> 字样，那是文档而非用户可见提示，不应误判。
    content = INSTALL_BUNDLE_CMAKE.read_text(encoding="utf-8")
    code_lines = [
        line for line in content.splitlines() if not line.lstrip().startswith("#")
    ]
    hint_lines = [line for line in code_lines if "--bundle_branch=" in line]
    assert hint_lines, "错误提示应给出 --bundle_branch 用法"
    for line in hint_lines:
        assert "--bundle_branch=<" not in line, (
            f"提示不应出现 --bundle_branch=<...>（尖括号是 shell 重定向元字符）: {line}"
        )
    assert "--bundle_branch=${_b}" in content, "应逐个列出可用取值"


def test_local_tarball_branch_is_verified():
    # 预置包名不含分支，命中后必须校验旁写的 .branch 元数据，
    # 否则离线构建会静默混入其它分支的闭源包。
    content = INSTALL_BUNDLE_CMAKE.read_text(encoding="utf-8")
    assert "${_local_tar}.branch" in content, "命中本地预置包时应读取 .branch 元数据"
    assert "local bundle tarball branch mismatch" in content, (
        "预置包分支与目标分支不一致时应报错"
    )


def test_download_libs_writes_branch_metadata():
    # 元数据由离线预置脚本生成，两端须配对，否则校验永远走"无元数据"告警分支。
    content = (REPO_ROOT / "cmake" / "download_libs.py").read_text(encoding="utf-8")
    assert "def write_bundle_branch_metadata" in content
    assert "write_bundle_branch_metadata(bundle_branch" in content, (
        "主流程应在下载后写入分支元数据"
    )
    assert ".branch" in content


def test_existing_bundle_dir_branch_is_verified():
    # 从 master 构建后切到 9.1.0 直接 build.sh 会命中"bundle 已存在"分支，
    # 不校验就会静默复用 master 的闭源包——这正是本 PR 要修的场景。
    content = INSTALL_BUNDLE_CMAKE.read_text(encoding="utf-8")
    skip_block = re.search(
        r"if\(_bundle_entries\)(?P<body>.*?)\n        endif\(\)", content, re.S
    )
    assert skip_block is not None, "应有 bundle 已存在时跳过下载的分支"
    body = skip_block.group("body")
    assert "oam_resolve_bundle_branch" in body, "复用已有 bundle 前应先解析目标分支"
    assert "existing bundle at" in body and "FATAL_ERROR" in body, (
        "已有 bundle 分支与目标分支不一致时应在配置阶段报错"
    )
    # 元数据须在取包成功后写入，否则下次复用永远无从核对。
    assert 'file(WRITE "${_bundle_meta}"' in content, (
        "取包成功后应写入 bundle 分支元数据"
    )


def test_download_libs_metadata_only_for_fetched_tars():
    # 仅按文件是否存在来写元数据，会把目录里残留的旧分支 tar 误标成本轮分支，
    # 联编时反而错误通过校验（比没有元数据更糟）。
    content = (REPO_ROOT / "cmake" / "download_libs.py").read_text(encoding="utf-8")
    assert "downloaded = download_files_native(" in content, (
        "download_files_native 应返回本轮成功下载的集合"
    )
    assert "fetched_bundle_tars" in content, "应只给本轮下载成功的 bundle tar 写元数据"
    assert "write_bundle_branch_metadata(bundle_branch, fetched_bundle_tars)" in content
    # 本轮未取到的包若留着旧元数据，会被联编当成"已核对"错误放行。
    assert "stale_meta" in content, "本轮未下载到的包应清掉其陈旧元数据"


def test_download_libs_exits_when_no_bundle_fetched():
    # bundle 一个都没取到时，离线预置结果不可用，应显式失败而非静默成功。
    content = (REPO_ROOT / "cmake" / "download_libs.py").read_text(encoding="utf-8")
    assert "if not fetched_bundle_tars:" in content
    assert "sys.exit(1)" in content, "无任何 bundle 包下载成功时应以非零码退出"


def test_download_single_file_removes_partial_file_on_failure():
    # wget -O 失败会残留半截文件，留着会被后续当作可用预置包。
    content = (REPO_ROOT / "cmake" / "download_libs.py").read_text(encoding="utf-8")
    wget_block = re.search(
        r'if result\.returncode != 0:(?P<body>.*?)raise RuntimeError\(f"wget download failed',
        content,
        re.S,
    )
    assert wget_block is not None
    assert "os.remove(file_path)" in wget_block.group("body"), (
        "wget 失败应删除残留的半截文件"
    )


def test_download_libs_whitelist_matches_cmake():
    # 两处白名单必须同步，否则离线预置能拼出 cmake 会拒绝的分支。
    py_content = (REPO_ROOT / "cmake" / "download_libs.py").read_text(encoding="utf-8")
    cmake_content = INSTALL_BUNDLE_CMAKE.read_text(encoding="utf-8")
    py_match = re.search(r"OAM_BUNDLE_KNOWN_BRANCHES = \((?P<v>[^)]*)\)", py_content)
    assert py_match, "download_libs.py 应声明 OAM_BUNDLE_KNOWN_BRANCHES"
    py_branches = set(re.findall(r'"([^"]+)"', py_match.group("v")))
    cmake_match = re.search(
        r"set\(OAM_BUNDLE_KNOWN_BRANCHES (?P<v>[^)]*)\)", cmake_content
    )
    assert cmake_match
    cmake_branches = set(re.findall(r'"([^"]+)"', cmake_match.group("v")))
    assert py_branches == cmake_branches, (
        f"白名单不同步: py={py_branches} cmake={cmake_branches}"
    )


def test_cann_cmake_059_syncs_fetch_script_and_docs():
    fetch = (REPO_ROOT / "cmake" / "fetch_cann_cmake.cmake").read_text(encoding="utf-8")
    downloader = (REPO_ROOT / "cmake" / "download_libs.py").read_text(encoding="utf-8")
    zh = (REPO_ROOT / "docs" / "zh" / "quick_install.md").read_text(encoding="utf-8")
    en = (REPO_ROOT / "docs" / "en" / "quick_install.md").read_text(encoding="utf-8")

    assert 'set(CANN_CMAKE_TAG "master-059")' in fetch
    assert (
        "SHA256=9e59939b5c97c9498293969df22ab2dd40e450700c51f84f117d065880f40d25"
        in fetch
    )
    assert "/cmake-master-059.tar.gz" in downloader
    assert "master-059" in zh and "cmake-master-059.tar.gz" in zh
    assert "master-059" in en and "cmake-master-059.tar.gz" in en
    downloader_url_text = downloader.replace('"\n            "', "")

    # master-059 changes the local patch cache from pkg/ to patch/.
    assert "makeself/fix/makeself-2.5.0.patch" in downloader_url_text
    assert "makeself/makeself-2.5.0.patch" not in downloader_url_text
    assert "patch/makeself-2.5.0.patch" in downloader
    assert "patch/backport-CVE-2025-0838.patch" in downloader
    assert "patch/mockcpp-2.7-h5.patch" in downloader
    assert "pkg/makeself-2.5.0.patch" not in downloader
    assert "pkg/backport-CVE-2025-0838.patch" not in downloader
    assert "both patches" not in zh
