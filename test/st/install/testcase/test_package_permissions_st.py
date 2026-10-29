# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""ST: package payload and installed tree permissions."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"
_BASH = shutil.which("bash") or "/bin/bash"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from package_permission_guard import (  # noqa: E402
    UPSTREAM_DAILY_WHL_ZONE_ANCHORS,
    assert_run_package_mode,
    assert_tree_matches,
    current_installation_is_private,
)


def test_guard_detects_permission_regression(tmp_path):
    root = tmp_path / "payload"
    root.mkdir()
    (root / "tool").write_text("tool", encoding="utf-8")
    (root / "tool").chmod(0o555)
    baseline = tmp_path / "baseline.tsv"
    baseline.write_text("type\tmode\tpath\ttarget\nf\t0555\ttool\t\n", encoding="utf-8")
    assert_tree_matches(root, baseline)

    (root / "tool").chmod(0o777)
    try:
        assert_tree_matches(root, baseline)
    except AssertionError as error:
        assert "expected" in str(error)
    else:
        pytest.fail("permission regression was not detected")


# 上游日构建 whl 漂移区（见 package_permission_guard.
# UPSTREAM_DAILY_WHL_SUBTREES）：tools/profiler/profiler_tool 前三层目录
# 本身在区外，须与基线精确匹配；analysis 及更深路径在区内。
_ZONE_DIR = "tools/profiler/profiler_tool/analysis/msinterface"
_ZONE_PARENT_DIRS = (
    "tools",
    "tools/profiler",
    "tools/profiler/profiler_tool",
)
# 锚点在盘上物化时使用的 whl 版本号：collect_tree 的归一化会把
# msprof-<version> 折叠成 msprof-{{VERSION}}，与基线/锚点常量对齐。
_ZONE_WHL_VERSION = "8.0.0"


def _materialize_zone_anchors(root):
    for anchor in UPSTREAM_DAILY_WHL_ZONE_ANCHORS:
        disk_path = root / anchor.replace("{{VERSION}}", _ZONE_WHL_VERSION)
        disk_path.parent.mkdir(parents=True, exist_ok=True)
        # mkdir 默认 mode 0o777 & ~umask：umask 002 的环境（Ubuntu/Debian
        # 普通用户默认）会得到 0775，group-write 被 _entry_safe 判为 unsafe
        # extra，与被测逻辑无关地翻红；analysis/lib64 这类区内中间目录与
        # 三个父目录一样显式归一 0755。
        disk_path.parent.chmod(0o755)
        if disk_path.suffix == ".dist-info":
            disk_path.mkdir()
            disk_path.chmod(0o755)
        else:
            disk_path.write_text("anchor", encoding="utf-8")
            disk_path.chmod(0o644)


def _zone_tree_with_baseline(tmp_path, baseline_rows=(), materialize_anchors=True):
    root = tmp_path / "payload"
    zone = root / _ZONE_DIR
    zone.mkdir(parents=True)
    current = root
    for name in ("tools", "profiler", "profiler_tool"):
        current = current / name
        current.chmod(0o755)
    # 同上：zone.mkdir(parents=True) 创建的区内中间目录（analysis、
    # msinterface）mode 随进程 umask 漂移，显式归一 0755 使用例结果
    # 不依赖运行环境。
    zone.parent.chmod(0o755)
    zone.chmod(0o755)
    if materialize_anchors:
        _materialize_zone_anchors(root)
    rows = [f"d\t0755\t{path}\t" for path in _ZONE_PARENT_DIRS]
    # 基线始终携带锚点行，与真实基线一致（真实 payload/installed 基线
    # 都含这三个锚点条目），锚点行不代表盘上一定存在（materialize_anchors
    # 控制），整树消失场景正是靠这一差距触发锚点断言。
    for anchor in UPSTREAM_DAILY_WHL_ZONE_ANCHORS:
        kind = "d" if anchor.endswith(".dist-info") else "f"
        mode = 0o755 if kind == "d" else 0o644
        rows.append(f"{kind}\t{mode:04o}\t{anchor}\t")
    rows.extend(baseline_rows)
    baseline = tmp_path / "baseline.tsv"
    baseline.write_text("type\tmode\tpath\ttarget\n" + "\n".join(rows) + "\n",
                        encoding="utf-8")
    return root, baseline


def _zone_file(root, name, mode):
    path = root / _ZONE_DIR / name
    path.write_text(name, encoding="utf-8")
    path.chmod(mode)
    return path


def test_guard_tolerates_daily_whl_zone_extra_safe_file(tmp_path):
    # CI run#1448：上游日构建 whl 在两次构建之间新增 3 个
    # analysis/msinterface 文件。区内 extra 且权限安全（0644）时容忍。
    root, baseline = _zone_tree_with_baseline(tmp_path)
    _zone_file(root, "prof_parallel_plan.py", 0o644)
    assert_tree_matches(root, baseline)


def test_guard_rejects_daily_whl_zone_extra_unsafe_file(tmp_path):
    # 区内 extra 仍强制安全断言：上游投放 0666（group/world 可写）必须拦截。
    root, baseline = _zone_tree_with_baseline(tmp_path)
    _zone_file(root, "prof_parallel_plan.py", 0o666)
    with pytest.raises(AssertionError, match="prof_parallel_plan.py"):
        assert_tree_matches(root, baseline)


def test_guard_tolerates_daily_whl_zone_missing_entry(tmp_path):
    # 区内非锚点条目被上游删除属正常演进，missing 不报错。
    root, baseline = _zone_tree_with_baseline(
        tmp_path,
        baseline_rows=[f"f\t0644\t{_ZONE_DIR}/removed_by_upstream.py\t"],
    )
    assert_tree_matches(root, baseline)


def test_guard_rejects_daily_whl_zone_wholesale_removal(tmp_path):
    # 评审 2026-10-23 实测场景：物化整棵安装树后清空
    # tools/profiler/profiler_tool/ 下全部内容（whl 本体、dist-info、
    # analysis/lib64/msprof_analysis.so 全没了），此前因区内 missing
    # 双向容忍而静默通过。锚点存在性断言必须拦下整棵工具消失。
    root, baseline = _zone_tree_with_baseline(
        tmp_path,
        materialize_anchors=False,
    )
    with pytest.raises(AssertionError) as error:
        assert_tree_matches(root, baseline)
    message = str(error.value)
    for anchor in UPSTREAM_DAILY_WHL_ZONE_ANCHORS:
        assert anchor in message


def test_guard_rejects_baseline_without_zone_anchors(tmp_path):
    # 基线完整性：基线建模了漂移区却不含锚点（上游改名后基线重生成
    # 未同步），必须显式报错，否则区内 missing 容忍会静默重开缺口。
    # 基线保留一个普通区内条目（kept.py，盘上缺失属区内 missing 容忍）
    # 以确保仍算"建模了漂移区"。
    root, baseline = _zone_tree_with_baseline(
        tmp_path,
        baseline_rows=[f"f\t0644\t{_ZONE_DIR}/kept.py\t"],
    )
    lines = baseline.read_text(encoding="utf-8").splitlines()
    stripped = [
        line
        for line in lines
        if not any(line.endswith(f"{anchor}\t") for anchor in UPSTREAM_DAILY_WHL_ZONE_ANCHORS)
    ]
    baseline.write_text("\n".join(stripped) + "\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="anchor entries"):
        assert_tree_matches(root, baseline)


def test_guard_rejects_extra_outside_daily_whl_zone(tmp_path):
    root, baseline = _zone_tree_with_baseline(tmp_path)
    outside = root / "outside_tool.py"
    outside.write_text("tool", encoding="utf-8")
    outside.chmod(0o644)
    with pytest.raises(AssertionError, match="outside_tool.py"):
        assert_tree_matches(root, baseline)


def test_guard_rejects_missing_outside_daily_whl_zone(tmp_path):
    root, baseline = _zone_tree_with_baseline(
        tmp_path,
        baseline_rows=["f\t0644\toutside_tool.py\t"],
    )
    with pytest.raises(AssertionError, match="outside_tool.py"):
        assert_tree_matches(root, baseline)


def test_guard_reports_only_outside_mismatch_in_mixed_tree(tmp_path):
    # 区内 missing/extra 安全条目全部容忍，报错只含区外 missing 条目。
    root, baseline = _zone_tree_with_baseline(
        tmp_path,
        baseline_rows=[
            "f\t0644\toutside_tool.py\t",
            f"f\t0644\t{_ZONE_DIR}/keep.py\t",
            f"f\t0644\t{_ZONE_DIR}/removed_by_upstream.py\t",
        ],
    )
    _zone_file(root, "keep.py", 0o644)
    _zone_file(root, "added_by_upstream.py", 0o644)
    with pytest.raises(AssertionError) as error:
        assert_tree_matches(root, baseline)
    message = str(error.value)
    assert "outside_tool.py" in message
    assert "removed_by_upstream.py" not in message
    assert "added_by_upstream.py" not in message


def test_package_payload_matches_baseline(run_package, install_dir):
    payload_dir = Path(install_dir).parent / "permission_payload"
    result = subprocess.run(
        [_BASH, run_package, "--extract=" + str(payload_dir), "--noexec"],
        capture_output=True,
        text=True,
        timeout=180,
        # --noexec --extract 走 tar 解压，目录 mode 为 0o777 & ~umask：
        # umask 002 的本地环境（Ubuntu/Debian 普通用户默认）解出 0775 目录，
        # 与按 CI 口径（umask 022）生成的基线冲突，属环境差异而非包内容
        # 问题。基线在生成与比对两侧都取 umask 022 口径，解压子进程强制
        # 对齐（安装路径不受影响：安装器脚本内部自带 umask 归一）。
        preexec_fn=lambda: os.umask(0o022),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert_tree_matches(
        payload_dir,
        DATA_DIR / "package_payload.tsv",
    )


def test_run_package_is_executable(run_package):
    assert_run_package_mode(run_package)


@pytest.mark.parametrize("install_type", ["--full", "--run", "--devel"])
def test_installed_tree_matches_baseline(run_package, install_dir, install_type):
    result = subprocess.run(
        [
            _BASH,
            run_package,
            install_type,
            "--quiet",
            f"--install-path={install_dir}",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert_tree_matches(
        Path(install_dir) / "cann",
        DATA_DIR / "installed_tree.tsv",
        # root installs (CI runners) apply shared modes even without
        # --install-for-all, so the expected column must follow the runtime
        # environment rather than assume a private install.
        mode_column="mode_private"
        if current_installation_is_private()
        else "mode_shared",
        # install_type is reserved for a future copy_all=false package: the
        # installer would then trim filelist entries whose install_type is
        # neither "all" nor the requested mode, and the expected set must be
        # filtered the same way. Under today's copy_all=true every mode lands
        # the whole payload via `cp -af`, the exclusion set is empty, and this
        # parameter has no effect (same tree for --full/--run/--devel).
        install_type=install_type.lstrip("-"),
    )


def test_installed_tree_matches_shared_baseline(run_package, install_dir):
    result = subprocess.run(
        [
            _BASH,
            run_package,
            "--full",
            "--quiet",
            "--install-for-all",
            f"--install-path={install_dir}",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert_tree_matches(
        Path(install_dir) / "cann",
        DATA_DIR / "installed_tree.tsv",
        mode_column="mode_shared",
    )
