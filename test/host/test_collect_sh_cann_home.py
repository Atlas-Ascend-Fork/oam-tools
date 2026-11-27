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
"""Host tests for CANN log path probing in collect.sh."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/tool-fault-diagnosis/collect-skill/scripts/collect.sh"

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or not shutil.which("bash"),
    reason="Linux Bash is required for collect.sh probing semantics",
)


def _create_cann_tree(root, rel_path, marker="marker"):
    log_dir = root / rel_path / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "cann.log").write_text(f"{marker}\n", encoding="utf-8")
    return root / rel_path


def _prepare_runner(tmp_path):
    work = tmp_path / "collect_work"
    work.mkdir(exist_ok=True)
    system_root = tmp_path / "system_ascend"
    user_root = tmp_path / "user_ascend"
    slog_root = tmp_path / "npu_slog"
    output_dir = tmp_path / "collected_logs"
    system_root.mkdir(exist_ok=True)
    user_root.mkdir(exist_ok=True)
    slog_root.mkdir(exist_ok=True)

    source = SCRIPT.read_text(encoding="utf-8")
    source = source.replace(
        "/usr/local/Ascend/ascend-toolkit/*",
        '"${OAM_TEST_SYSTEM_ROOT}"/ascend-toolkit/*',
    )
    source = source.replace(
        "/usr/local/Ascend/cann-*",
        '"${OAM_TEST_SYSTEM_ROOT}"/cann-*',
    )
    source = source.replace("/usr/local/Ascend", "${OAM_TEST_SYSTEM_ROOT}")
    source = source.replace("${HOME}/Ascend", "${OAM_TEST_USER_ROOT}")
    source = source.replace("$HOME/Ascend", "${OAM_TEST_USER_ROOT}")
    source = source.replace("/var/log/npu/slog", "${OAM_TEST_SLOG_DIR}")
    assert "/usr/local/Ascend" not in source
    assert "/var/log/npu/slog" not in source
    assert "${HOME}/Ascend" not in source
    assert "$HOME/Ascend" not in source
    script_copy = work / "collect_patched.sh"
    script_copy.write_text(source, encoding="utf-8")

    return {
        "script": script_copy,
        "system_root": system_root,
        "user_root": user_root,
        "slog_root": slog_root,
        "output_dir": output_dir,
    }


def _run_collect(ctx, extra_env=None):
    env = dict(os.environ)
    for key in ("CANN_HOME", "ASCEND_INSTALL_PATH", "ASCEND_HOME_PATH"):
        env.pop(key, None)
    env.update(
        OAM_TEST_SYSTEM_ROOT=ctx["system_root"].as_posix(),
        OAM_TEST_USER_ROOT=ctx["user_root"].as_posix(),
        OAM_TEST_SLOG_DIR=ctx["slog_root"].as_posix(),
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [
            shutil.which("bash"),
            ctx["script"].as_posix(),
            "--msnpureprot",
            "--output",
            ctx["output_dir"].as_posix(),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def _collected_cann_logs(output_dir):
    return sorted((output_dir / "msnpureprot/cann").rglob("cann.log"))


def test_cann_home_probes_install_root_subdirectories(tmp_path):
    ctx = _prepare_runner(tmp_path)
    install_root = tmp_path / "custom_install"
    _create_cann_tree(install_root, "cann", marker="from-cann-home-root")

    res = _run_collect(ctx, {"CANN_HOME": install_root.as_posix()})

    assert res.returncode == 0
    assert (
        f"CANN 日志已从 {(install_root / 'cann/log').as_posix()} 复制到" in res.stdout
    )
    copied = _collected_cann_logs(ctx["output_dir"])
    assert len(copied) == 1
    assert copied[0].read_text(encoding="utf-8").strip() == "from-cann-home-root"
    assert "未包含有效 log 子目录" not in res.stderr
    assert "未探测到有效的 CANN 日志目录" not in res.stderr


def test_env_precedence_and_invalid_env_fallback(tmp_path):
    ctx = _prepare_runner(tmp_path)
    cann_root = _create_cann_tree(tmp_path / "env_a", "cann", marker="picked-cann-home")
    _create_cann_tree(tmp_path / "env_b", "cann", marker="picked-install-path")

    res_primary = _run_collect(
        ctx,
        {
            "CANN_HOME": cann_root.parent.as_posix(),
            "ASCEND_INSTALL_PATH": (tmp_path / "env_b").as_posix(),
        },
    )
    assert res_primary.returncode == 0
    assert (
        f"CANN 日志已从 {(cann_root / 'log').as_posix()} 复制到" in res_primary.stdout
    )
    copied_primary = _collected_cann_logs(ctx["output_dir"])
    assert len(copied_primary) == 1
    assert copied_primary[0].read_text(encoding="utf-8").strip() == "picked-cann-home"

    shutil.rmtree(ctx["output_dir"])
    res_fallback = _run_collect(
        ctx,
        {
            "CANN_HOME": (tmp_path / "does_not_exist").as_posix(),
            "ASCEND_INSTALL_PATH": (tmp_path / "env_b").as_posix(),
        },
    )
    assert res_fallback.returncode == 0
    assert "环境变量 CANN_HOME" in res_fallback.stderr
    copied_fallback = _collected_cann_logs(ctx["output_dir"])
    assert len(copied_fallback) == 1
    assert (
        copied_fallback[0].read_text(encoding="utf-8").strip() == "picked-install-path"
    )


def test_wildcard_probe_warns_when_multiple_versions_exist(tmp_path):
    ctx = _prepare_runner(tmp_path)
    _create_cann_tree(ctx["system_root"], "cann-8.5.0", marker="v850")
    _create_cann_tree(ctx["system_root"], "cann-9.3.0", marker="v930")

    res = _run_collect(ctx)

    assert res.returncode == 0
    assert "通过通配探测选中 CANN 目录" in res.stderr
    assert len(_collected_cann_logs(ctx["output_dir"])) == 1


def test_exact_candidate_takes_precedence_over_wildcard(tmp_path):
    ctx = _prepare_runner(tmp_path)
    _create_cann_tree(ctx["system_root"], "cann-8.5.0", marker="wildcard-old")
    _create_cann_tree(ctx["system_root"], "cann", marker="exact-cann")

    res = _run_collect(ctx)

    assert res.returncode == 0
    assert "通过通配探测选中 CANN 目录" not in res.stderr
    assert (
        f"CANN 日志已从 {(ctx['system_root'] / 'cann/log').as_posix()} 复制到"
        in res.stdout
    )
    copied = _collected_cann_logs(ctx["output_dir"])
    assert len(copied) == 1
    assert copied[0].read_text(encoding="utf-8").strip() == "exact-cann"


def test_no_candidates_skips_cleanly_without_hardcoded_version(tmp_path):
    ctx = _prepare_runner(tmp_path)

    res = _run_collect(ctx)

    assert res.returncode == 0
    assert "未探测到有效的 CANN 日志目录" in res.stdout
    assert "CANN 日志已从" not in res.stdout
    assert "cann-8.5.0" not in res.stdout + res.stderr
    assert not (ctx["output_dir"] / "msnpureprot/cann").exists()
