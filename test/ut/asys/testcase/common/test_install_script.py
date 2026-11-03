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

"""install.sh --docker-root 校验与参数解析的回归测试（Issue #290）。

除内容断言外，还把 install.sh 里真实的 check_docker_path 函数与
--docker-root case 分支原样抽取到子 shell 中执行，覆盖 Issue #290
「建议的回归测试」的四条断言：相对目录拒绝、存在的绝对目录通过、
--docker-root=/tmp/root=stage 完整解析、不含等号的绝对路径保持原值。
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]


def get_install_script_content():
    return (REPO_ROOT / "scripts/package/oam_tools/scripts/install.sh").read_text(
        encoding="utf-8"
    )


def get_check_docker_path_function():
    content = get_install_script_content()
    match = re.search(r"\ncheck_docker_path\(\)\s*\{(?P<body>.*?)\n\}", content, re.S)
    assert match is not None, "check_docker_path 函数未定义"
    return f"check_docker_path() {{{match.group('body')}\n}}"


def get_docker_root_case_branch():
    content = get_install_script_content()
    match = re.search(r"--docker-root=\*\)(?P<body>.*?;;)", content, re.S)
    assert match is not None, "--docker-root 分支未定义"
    return f"--docker-root=*){match.group('body')}"


def run_docker_root_case(value):
    # 用 install.sh 原文中的 case 分支与 check_docker_path 组装子 shell：
    # 退出码 0 = 校验通过且 stdout 为解析出的 docker_root；1 = 校验拒绝。
    script = (
        "exitlog() { :; }\n"
        f"{get_check_docker_path_function()}\n"
        "is_docker_install=n\n"
        'docker_root=""\n'
        'case "$1" in\n'
        f"{get_docker_root_case_branch()}\n"
        "esac\n"
        "printf '%s' \"${docker_root}\"\n"
    )
    return subprocess.run(
        [
            "/bin/bash",
            "-c",
            script,
            "install_docker_root_probe",
            f"--docker-root={value}",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_check_docker_path_rejects_relative_path():
    # 相对目录拒绝：绝对前缀判断必须走 case 模式匹配（#745 修复形态），
    # 旧的 [ "${docker_path}" != "/"* ] 写法在 test 中不按模式匹配，会漏放行相对路径。
    function_body = get_check_docker_path_function()
    assert 'case "${docker_path}" in' in function_body
    assert "/*) ;;" in function_body
    assert (
        "must with absolute path that which is start with root directory /"
        in function_body
    )
    assert "exit 1" in function_body
    assert '!= "/"*' not in function_body, "不应回退为 test 比较的旧写法"


def test_check_docker_path_requires_existing_directory():
    # 存在的绝对目录通过：函数仅在目录不存在时报错退出。
    function_body = get_check_docker_path_function()
    assert '[ ! -d "${docker_path}" ]' in function_body
    assert "not exist, please create this directory" in function_body


def test_docker_root_branch_parses_full_value_with_parameter_expansion():
    # --docker-root=/tmp/root=stage 完整解析：取值须用 ${1#*=}（只去掉最长参数名前缀），
    # 不能回退为 cut -d"=" -f2（会把含等号的取值截断）。
    branch_body = get_docker_root_case_branch()
    assert 'docker_root="${1#*=}"' in branch_body
    assert 'cut -d"=" -f2' not in branch_body, "不应回退为 cut 截断取值"
    assert "$(echo $1 | cut" not in branch_body, "不应回退为无引号 echo 管道截断取值"


def test_docker_root_branch_calls_check_docker_path_quoted():
    # 调用必须加引号：取值含 glob 元字符或空格时，
    # 未加引号会先做词分割/glob 展开，校验对象与实际安装目标分叉。
    branch_body = get_docker_root_case_branch()
    assert 'check_docker_path "${docker_root}"' in branch_body
    assert "check_docker_path ${docker_root}" not in branch_body, "不应回退为无引号调用"


def test_case_branch_rejects_relative_dir():
    # Issue #290 断言 1：真相对目录（.）被拒绝，且必须命中绝对路径校验分支。
    # base 旧写法会放行 --docker-root=.（#290 缺陷复现，rc=0 且 stdout 为 "."）；
    # 而不存在的绝对路径只会走"目录不存在"分支，对绝对路径校验无区分力。
    result = run_docker_root_case(".")
    assert result.returncode != 0, f"相对目录应被拒绝，实际输出：{result.stdout}"
    assert "must with absolute path" in result.stdout, (
        f"应命中绝对路径校验分支而非目录不存在分支，实际输出：{result.stdout}"
    )


def test_case_branch_accepts_existing_absolute_dir(tmp_path):
    # Issue #290 断言 2：存在的绝对目录通过校验，且取值原样保留。
    result = run_docker_root_case(str(tmp_path))
    assert result.returncode == 0, (
        f"存在的绝对目录应通过校验，实际输出：{result.stdout}"
    )
    assert result.stdout == str(tmp_path)


def test_case_branch_parses_full_value_with_equal_sign(tmp_path):
    # Issue #290 断言 3：--docker-root=/tmp/root=stage 解析为完整取值。
    docker_root_dir = tmp_path / "root=stage"
    docker_root_dir.mkdir()
    result = run_docker_root_case(str(docker_root_dir))
    assert result.returncode == 0, f"含等号目录应通过校验，实际输出：{result.stdout}"
    assert result.stdout == str(docker_root_dir), "含等号的取值必须完整保留"


def test_case_branch_keeps_value_without_equal_sign(tmp_path):
    # Issue #290 断言 4：不含等号的绝对路径保持原值。
    result = run_docker_root_case(str(tmp_path))
    assert result.returncode == 0
    assert result.stdout == str(tmp_path), "不含等号的取值必须保持原值"


def test_case_branch_rejects_glob_literal_even_when_entries_exist(tmp_path):
    # glob 取值：即使目录下存在条目，字面量 dir/* 也不是已存在的目录，
    # 必须被拒绝（无引号调用会展开成首个条目而误过检）。
    glob_base = tmp_path / "globB"
    (glob_base / "dir1").mkdir(parents=True)
    result = run_docker_root_case(f"{glob_base}/*")
    assert result.returncode != 0, (
        f"glob 取值应被拒绝而非展开为 {glob_base}/dir1，实际输出：{result.stdout}"
    )


def test_case_branch_accepts_existing_dir_with_spaces(tmp_path):
    # 含空格的已存在目录：整串参与校验并通过（无引号调用只会取到第一个词而误拒）。
    spaced_dir = tmp_path / "a b"
    spaced_dir.mkdir()
    result = run_docker_root_case(str(spaced_dir))
    assert result.returncode == 0, (
        f"含空格的已存在目录应通过校验，实际输出：{result.stdout}"
    )
    assert result.stdout == str(spaced_dir)
