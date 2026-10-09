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
"""Install all tool-fault-diagnosis sub-skills for Codex, Claude Code, OpenCode, or CodeFuse."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import sys
from pathlib import Path


TARGETS = ("codex", "claude", "opencode", "codefuse")
SUB_SKILLS = [
    ("orchestrator-skill", "orchestrator-skill"),
    ("collect-skill", "collect-skill"),
    ("eval-skill", "eval-skill"),
    ("trace-skill", "trace-skill"),
    ("metric-skill", "metric-skill"),
]
TEMPLATE_DIR = "template"
TEMPLATE_MODULE_FILES = ("report-template-rules.md", "index.html")


class InstallError(RuntimeError):
    pass


def codex_skills_dir() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return codex_home / "skills"


def claude_skills_dir() -> Path:
    claude_home = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude")).expanduser()
    return claude_home / "skills"


def opencode_skills_dir() -> Path:
    opencode_config = Path(
        os.environ.get("OPENCODE_CONFIG_DIR", Path.home() / ".config" / "opencode")
    ).expanduser()
    return opencode_config / "skills"


def codefuse_skills_dir() -> Path:
    return Path.home() / ".codefuse" / "fuse" / "skills"


def default_skills_dir(target: str) -> Path:
    if target == "codex":
        return codex_skills_dir()
    if target == "claude":
        return claude_skills_dir()
    if target == "opencode":
        return opencode_skills_dir()
    if target == "codefuse":
        return codefuse_skills_dir()
    raise InstallError(f"未知安装目标: {target}")


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_skill_name(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    match = re.search(r"^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$", text, flags=re.M)
    if not match:
        raise InstallError(f"无法从 {skill_md} 读取 skill name")
    return match.group(1).strip()


def verify_skill_name(skill_md: Path, fallback: str) -> str:
    if not skill_md.exists():
        return fallback
    try:
        return read_skill_name(skill_md)
    except InstallError:
        return fallback


def restore_script_exec_bits(dest: Path) -> None:
    scripts_dir = dest / "scripts"
    if not scripts_dir.exists():
        return
    for path in scripts_dir.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".sh"}:
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def copy_skill(src: Path, dest: Path, overwrite: bool, dry_run: bool) -> str:
    if not (src / "SKILL.md").exists():
        raise InstallError(f"缺少 SKILL.md: {src}")
    if dest.exists() and not overwrite:
        return "skip-existing"
    if dry_run:
        return "would-overwrite" if dest.exists() else "would-install"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns("tests", "__pycache__", "*.py[co]"),
    )
    restore_script_exec_bits(dest)
    return "installed"


def verify_installation(src_root: Path, dest_root: Path) -> list[str]:
    problems: list[str] = []
    for subdir, fallback_name in SUB_SKILLS:
        src = src_root / subdir
        name = verify_skill_name(src / "SKILL.md", fallback_name)
        dest = dest_root / name
        if not (dest / "SKILL.md").exists():
            problems.append(f"未安装: {name} -> {dest}")
            continue
        for script in (src / "scripts").glob("*") if (src / "scripts").exists() else []:
            installed_script = dest / "scripts" / script.name
            if script.is_file() and script.suffix in {".py", ".sh"} and not os.access(installed_script, os.X_OK):
                problems.append(f"脚本不可执行: {installed_script}")
    metric_name = verify_skill_name(src_root / "metric-skill" / "SKILL.md", "metric-skill")
    installed_template_dir = dest_root / metric_name / TEMPLATE_DIR
    installed_entries = {
        str(path.relative_to(installed_template_dir))
        for path in installed_template_dir.rglob("*")
    } if installed_template_dir.is_dir() else set()
    expected_files = set(TEMPLATE_MODULE_FILES)
    if installed_entries != expected_files:
        problems.append(
            "模板模块入口必须且只能是 "
            f"{', '.join(TEMPLATE_MODULE_FILES)}；实际为 {', '.join(sorted(installed_entries)) or '空'}"
        )
    return problems


def selected_targets(target: str) -> list[str]:
    if target == "all":
        return list(TARGETS)
    return [target]


def install_to_dest(src_root: Path, dest_root: Path, overwrite: bool, dry_run: bool) -> int:
    if not dry_run:
        dest_root.mkdir(parents=True, exist_ok=True)

    rows: list[tuple[str, str, str]] = []
    for subdir, _ in SUB_SKILLS:
        src = src_root / subdir
        name = read_skill_name(src / "SKILL.md")
        dest = dest_root / name
        status = copy_skill(src, dest, overwrite, dry_run)
        rows.append((name, str(dest), status))

    for name, dest, status in rows:
        print(f"{status:15} {name:20} {dest}")

    if not dry_run:
        problems = verify_installation(src_root, dest_root)
        if problems:
            for problem in problems:
                print(f"FAIL {problem}", file=sys.stderr)
            return 1
        print(f"OK installed all tool-fault-diagnosis sub-skills in {dest_root}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install all tool-fault-diagnosis sub-skills")
    parser.add_argument(
        "--target",
        choices=[*TARGETS, "all"],
        default="codex",
        help="Install target: codex, claude, opencode, codefuse, or all",
    )
    parser.add_argument("--dest", help="Destination skills directory; only valid with one --target")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing installed skills")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be installed without writing")
    parser.add_argument("--verify-only", action="store_true", help="Only verify installed tool-fault-diagnosis sub-skills")
    args = parser.parse_args()

    src_root = source_root()
    targets = selected_targets(args.target)
    if args.dest and len(targets) != 1:
        print("ERROR --dest cannot be used with --target all", file=sys.stderr)
        return 2

    try:
        rc = 0
        for target in targets:
            dest_root = Path(args.dest).expanduser().resolve() if args.dest else default_skills_dir(target).resolve()
            print(f"==> target={target} dest={dest_root}")
            if args.verify_only:
                problems = verify_installation(src_root, dest_root)
                if problems:
                    for problem in problems:
                        print(f"FAIL {problem}")
                    rc = 1
                else:
                    print(f"OK all tool-fault-diagnosis sub-skills installed for {target} in {dest_root}")
                continue
            rc = max(rc, install_to_dest(src_root, dest_root, args.overwrite, args.dry_run))

        if not args.dry_run and not args.verify_only and rc == 0:
            target_label = ", ".join(targets)
            print(f"OK installed all tool-fault-diagnosis sub-skills for {target_label}")
        return rc
    except InstallError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
