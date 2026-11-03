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

"""Collect installed custom operator packages using their ordered CANN path."""

import json
import os

import pytest

from collect.ops import ops_collect
from drv import EnvVarName
from drv import env_var as env_var_module


@pytest.fixture(autouse=True)
def reset_warned_invalid_env_paths(monkeypatch):
    monkeypatch.setattr(env_var_module, "_WARNED_INVALID_ENV_PATHS", set())


@pytest.fixture
def packages(tmp_path, monkeypatch):
    home = tmp_path / "private-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    original_get_arg = ops_collect.ParamDict.get_arg
    monkeypatch.setattr(
        ops_collect.ParamDict,
        "get_arg",
        lambda self, name: None if name == "task_dir" else original_get_arg(self, name),
    )
    for name in (
        "ASCEND_OPP_PATH",
        "ASCEND_CACHE_PATH",
        "ASCEND_WORK_PATH",
        "NPU_COLLECT_PATH",
        "ASCEND_CUSTOM_OPP_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    for vendor in ("vendor_a", "vendor_b"):
        package = tmp_path / vendor
        config = package / "config" / "ascend910b" / "aic-ops-info.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"vendor": vendor}), encoding="utf-8")
        kernel = package / "kernel" / "ascend910b" / "AsysRegressionKernel.json"
        kernel.parent.mkdir(parents=True)
        kernel.write_text(
            json.dumps({"kernelName": "AsysRegressionKernel"}), encoding="utf-8"
        )
        kernel.with_suffix(".o").write_bytes(vendor.encode("ascii"))
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    monkeypatch.chdir(analysis)
    # Relative entries avoid Windows drive colons, while testing the actual
    # colon convention that CANN uses on Linux. All package files are real.
    return tmp_path


@pytest.mark.parametrize(
    "custom_path,first_has_kernel,expected",
    [
        ("../vendor_b", True, b"vendor_b"),
        (os.pathsep.join(["../vendor_a", "../vendor_b"]), False, b"vendor_b"),
        (os.pathsep.join(["../vendor_a", "../vendor_b"]), True, b"vendor_a"),
    ],
)
def test_custom_package_kernel_search(
    packages, monkeypatch, custom_path, first_has_kernel, expected
):
    monkeypatch.setenv("ASCEND_CUSTOM_OPP_PATH", custom_path)
    if not first_has_kernel:
        metadata = packages / "vendor_a/kernel/ascend910b/AsysRegressionKernel.json"
        metadata.write_text(json.dumps({"kernelName": "OtherKernel"}), encoding="utf-8")
    log = packages / "output/dfx/log/host/cann/run/plog/plog.log"
    log.parent.mkdir(parents=True)
    log.write_text(
        "Aicore kernel execute failed, device_id=0, stream_id=5, task_id=5, "
        "fault kernel_name=AsysRegressionKernel, program id=1\n",
        encoding="utf-8",
    )
    output = packages / "result"
    assert ops_collect.collect_ops_files_env_var(str(packages / "output"), str(output))
    assert (output / "AsysRegressionKernel.o").read_bytes() == expected
    metadata = json.loads((output / "AsysRegressionKernel.json").read_text("utf-8"))
    assert metadata["kernelName"] == "AsysRegressionKernel"


@pytest.mark.parametrize("multiple", [False, True])
def test_custom_package_configs_keep_source_identity(packages, monkeypatch, multiple):
    custom_path = (
        os.pathsep.join(["../vendor_a", "../vendor_b"]) if multiple else "../vendor_b"
    )
    monkeypatch.setenv("ASCEND_CUSTOM_OPP_PATH", custom_path)
    output = packages / "config-result"
    assert ops_collect.collect_custom_opp_config(str(output))
    config_root = output / "dfx/ops/custom_config"
    expected = {"0": "vendor_a", "1": "vendor_b"} if multiple else {"": "vendor_b"}
    for directory, vendor in expected.items():
        config = config_root / directory / "config/ascend910b/aic-ops-info.json"
        assert json.loads(config.read_text("utf-8")) == {"vendor": vendor}


def test_custom_config_is_false_when_the_env_var_is_unset(packages):
    assert not ops_collect.collect_custom_opp_config(str(packages / "unset-result"))


def test_custom_config_ignores_entries_that_are_not_directories(packages, monkeypatch):
    monkeypatch.setenv(
        "ASCEND_CUSTOM_OPP_PATH",
        os.pathsep.join(["../vendor_a", "../nonexistent", "", "../vendor_b"]),
    )
    output = packages / "mixed-result"
    assert ops_collect.collect_custom_opp_config(str(output))
    config_root = output / "dfx/ops/custom_config"
    assert json.loads(
        (config_root / "0/config/ascend910b/aic-ops-info.json").read_text("utf-8")
    ) == {"vendor": "vendor_a"}
    assert json.loads(
        (config_root / "1/config/ascend910b/aic-ops-info.json").read_text("utf-8")
    ) == {"vendor": "vendor_b"}


def test_custom_config_succeeds_when_one_package_cannot_be_copied(
    packages, monkeypatch
):
    # A single unreadable package must not fail the whole collection.
    monkeypatch.setenv(
        "ASCEND_CUSTOM_OPP_PATH", os.pathsep.join(["../vendor_a", "../vendor_b"])
    )
    real_copy = ops_collect.f.copy_file_to_dir

    def fail_vendor_a(src, dst):
        if "vendor_a" in str(src).replace("\\", "/"):
            return False
        return real_copy(src, dst)

    monkeypatch.setattr(ops_collect.f, "copy_file_to_dir", fail_vendor_a)
    output = packages / "partial-result"
    assert ops_collect.collect_custom_opp_config(str(output))
    lost = output / "dfx/ops/custom_config/0/config/ascend910b/aic-ops-info.json"
    assert not lost.exists()
    config = output / "dfx/ops/custom_config/1/config/ascend910b/aic-ops-info.json"
    assert json.loads(config.read_text("utf-8")) == {"vendor": "vendor_b"}


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, []),
        ("", []),
        (os.pathsep.join(["../vendor_a", "../vendor_b"]), ["vendor_a", "vendor_b"]),
        (
            os.pathsep.join(["", "../vendor_a", "../nonexistent", "", "../vendor_b"]),
            ["vendor_a", "vendor_b"],
        ),
    ],
)
def test_env_var_splits_custom_opp_path_on_the_platform_separator(
    packages, monkeypatch, value, expected
):
    if value is None:
        monkeypatch.delenv("ASCEND_CUSTOM_OPP_PATH", raising=False)
    else:
        monkeypatch.setenv("ASCEND_CUSTOM_OPP_PATH", value)
    paths = EnvVarName().custom_opp_paths
    assert [os.path.basename(path) for path in paths] == expected
    assert all(os.path.isabs(path) for path in paths)


def test_env_var_drops_the_unsplit_single_path_attribute(packages, monkeypatch):
    monkeypatch.setenv(
        "ASCEND_CUSTOM_OPP_PATH", os.pathsep.join(["../vendor_a", "../vendor_b"])
    )
    env_var = EnvVarName()
    # The old attribute held the raw "a:b" string, which is never a directory.
    assert not hasattr(env_var, "custom_opp_path")
    assert len(env_var.custom_opp_paths) == 2


def test_invalid_entry_warning_is_emitted_once_per_process(
    packages, monkeypatch, mocker
):
    monkeypatch.setenv(
        "ASCEND_CUSTOM_OPP_PATH",
        os.pathsep.join(["../nonexistent", "../vendor_a"]),
    )
    warn_mock = mocker.patch("drv.env_var.log_warning")
    paths = []
    for _ in range(3):
        paths = EnvVarName().custom_opp_paths
    assert [os.path.basename(path) for path in paths] == ["vendor_a"]
    assert warn_mock.call_count == 1
    assert "../nonexistent" in warn_mock.call_args[0][0]


def test_each_unique_invalid_entry_warns_once(packages, monkeypatch, mocker):
    monkeypatch.setenv(
        "ASCEND_CUSTOM_OPP_PATH",
        os.pathsep.join(["../nonexistent_a", "../nonexistent_b", "../vendor_a"]),
    )
    warn_mock = mocker.patch("drv.env_var.log_warning")
    EnvVarName()
    assert warn_mock.call_count == 2
    warned = {call[0][0] for call in warn_mock.call_args_list}
    assert any("../nonexistent_a" in text for text in warned)
    assert any("../nonexistent_b" in text for text in warned)


def test_package_without_config_subtree_warns_and_returns_true(
    packages, tmp_path, monkeypatch, mocker
):
    kernel_only = tmp_path / "vendor_kernel_only"
    kernel = kernel_only / "kernel" / "ascend910b" / "AsysRegressionKernel.json"
    kernel.parent.mkdir(parents=True)
    kernel.write_text('{"kernelName": "AsysRegressionKernel"}', encoding="utf-8")
    monkeypatch.setenv("ASCEND_CUSTOM_OPP_PATH", "../vendor_kernel_only")
    warn_mock = mocker.patch("collect.ops.ops_collect.log_warning")
    output = tmp_path / "no-config-result"
    assert ops_collect.collect_custom_opp_config(str(output))
    assert not (output / "dfx/ops/custom_config").exists()
    assert warn_mock.call_count == 1
    assert "No custom operator config was collected" in warn_mock.call_args[0][0]


@pytest.mark.parametrize(
    "value,expected",
    [
        (os.pathsep.join(["../vendor_a", "../vendor_a"]), ["vendor_a"]),
        (os.pathsep.join(["../vendor_a", "./vendor_a"]), ["vendor_a"]),
        (
            os.pathsep.join(["../vendor_b", "../vendor_a", "../vendor_b"]),
            ["vendor_b", "vendor_a"],
        ),
    ],
)
def test_env_var_dedupes_entries_resolving_to_the_same_directory(
    packages, monkeypatch, value, expected
):
    monkeypatch.setenv("ASCEND_CUSTOM_OPP_PATH", value)
    paths = EnvVarName().custom_opp_paths
    assert [os.path.basename(path) for path in paths] == expected


def test_duplicate_entries_keep_the_single_package_layout(packages, monkeypatch):
    monkeypatch.setenv(
        "ASCEND_CUSTOM_OPP_PATH", os.pathsep.join(["../vendor_a", "./vendor_a"])
    )
    output = packages / "dedupe-result"
    assert ops_collect.collect_custom_opp_config(str(output))
    config_root = output / "dfx/ops/custom_config"
    config = config_root / "config/ascend910b/aic-ops-info.json"
    assert json.loads(config.read_text("utf-8")) == {"vendor": "vendor_a"}
    assert not (config_root / "0").exists()
    assert not (config_root / "1").exists()


def test_env_var_drops_unreadable_entries(packages, monkeypatch, mocker):
    # chmod 000 stays readable for root, so simulate the unreadable directory
    # instead of relying on file modes to keep the test root-proof.
    monkeypatch.setenv(
        "ASCEND_CUSTOM_OPP_PATH", os.pathsep.join(["../vendor_a", "../vendor_b"])
    )
    real_check_access = env_var_module.f.check_access

    def unreadable_vendor_a(path, mode=os.F_OK):
        if os.path.basename(path) == "vendor_a":
            return False
        return real_check_access(path, mode)

    monkeypatch.setattr(env_var_module.f, "check_access", unreadable_vendor_a)
    warn_mock = mocker.patch("drv.env_var.log_warning")
    paths = EnvVarName().custom_opp_paths
    assert [os.path.basename(path) for path in paths] == ["vendor_b"]
    assert warn_mock.call_count == 1
    assert "../vendor_a" in warn_mock.call_args[0][0]
    assert "not readable" in warn_mock.call_args[0][0]


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="root bypasses directory read permission checks",
)
def test_env_var_drops_a_directory_without_read_permission(packages, monkeypatch):
    locked = packages / "vendor_locked"
    locked.mkdir()
    locked.chmod(0o000)
    try:
        monkeypatch.setenv("ASCEND_CUSTOM_OPP_PATH", "../vendor_locked")
        assert EnvVarName().custom_opp_paths == []
    finally:
        locked.chmod(0o755)


def test_custom_config_drops_unreadable_packages(packages, monkeypatch):
    vendor_c = packages / "vendor_c"
    config = vendor_c / "config" / "ascend910b" / "aic-ops-info.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"vendor": "vendor_c"}), encoding="utf-8")
    real_check_access = env_var_module.f.check_access

    def unreadable_vendor_b(path, mode=os.F_OK):
        if os.path.basename(path) == "vendor_b":
            return False
        return real_check_access(path, mode)

    monkeypatch.setattr(env_var_module.f, "check_access", unreadable_vendor_b)
    monkeypatch.setenv(
        "ASCEND_CUSTOM_OPP_PATH",
        os.pathsep.join(["../vendor_a", "../vendor_b", "../vendor_c"]),
    )
    output = packages / "unreadable-result"
    assert ops_collect.collect_custom_opp_config(str(output))
    config_root = output / "dfx/ops/custom_config"
    # The unreadable middle entry is dropped before indexing, so the
    # remaining packages keep contiguous indexes without an empty slot.
    assert json.loads(
        (config_root / "0/config/ascend910b/aic-ops-info.json").read_text("utf-8")
    ) == {"vendor": "vendor_a"}
    assert json.loads(
        (config_root / "1/config/ascend910b/aic-ops-info.json").read_text("utf-8")
    ) == {"vendor": "vendor_c"}


def test_all_failed_copies_with_leftover_dirs_still_warn_nothing_collected(
    packages, monkeypatch, mocker
):
    # collect_cfg_json creates the per-package directories before copying, so
    # an all-failed run still leaves empty directories behind; the empty
    # result must be detected by counting files, not directory entries.
    monkeypatch.setenv("ASCEND_CUSTOM_OPP_PATH", "../vendor_a")
    monkeypatch.setattr(ops_collect.f, "copy_file_to_dir", lambda src, dst: False)
    warn_mock = mocker.patch("collect.ops.ops_collect.log_warning")
    output = packages / "all-failed-result"
    assert not ops_collect.collect_custom_opp_config(str(output))
    assert (output / "dfx/ops/custom_config/config/ascend910b").is_dir()
    assert not any(
        files for _, _, files in os.walk(output / "dfx/ops/custom_config") if files
    )
    assert warn_mock.call_count == 2
    assert (
        "No custom operator config was collected" in warn_mock.call_args_list[-1][0][0]
    )


def test_successful_collection_does_not_warn_about_an_empty_result(
    packages, monkeypatch, mocker
):
    monkeypatch.setenv("ASCEND_CUSTOM_OPP_PATH", "../vendor_a")
    warn_mock = mocker.patch("collect.ops.ops_collect.log_warning")
    output = packages / "ok-result"
    assert ops_collect.collect_custom_opp_config(str(output))
    assert warn_mock.call_count == 0
