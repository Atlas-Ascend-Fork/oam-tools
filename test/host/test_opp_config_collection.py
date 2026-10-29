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

"""Collect available OPP configuration after an independent source fails."""

import importlib.util
import logging
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


ASYS = Path(__file__).resolve().parents[2] / "src/asys"


def load_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def collector(monkeypatch):
    # Isolate driver/environment imports while retaining real collection and I/O.
    common = ModuleType("common")
    logger = logging.getLogger(__name__)
    common.consts = SimpleNamespace()
    common.log_debug = logger.debug
    common.log_info = logger.info
    common.log_warning = logger.warning
    log_module = ModuleType("common.log")
    log_module.log_debug = logger.debug
    log_module.log_error = logger.error
    constants = ModuleType("common.const")
    constants.CONFIG_TABLE_FILE = ""
    params = ModuleType("params")
    params.ParamDict = SimpleNamespace
    driver = ModuleType("drv")
    driver.EnvVarName = lambda: SimpleNamespace(
        opp_path=os.getenv("ASCEND_OPP_PATH"),
        custom_opp_path=os.getenv("ASCEND_CUSTOM_OPP_PATH"),
    )
    for name, module in {
        "common": common,
        "common.log": log_module,
        "common.const": constants,
        "params": params,
        "drv": driver,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    files = load_source("host_file_operate", ASYS / "common/file_operate.py")
    monkeypatch.setitem(sys.modules, "common.file_operate", files)
    common.FileOperate = files.FileOperate
    walk = os.walk

    def posix_walk(root):
        # Collection paths are POSIX; keep these host tests portable on Windows.
        for path, directories, names in walk(root):
            yield Path(path).as_posix(), directories, names

    monkeypatch.setattr(os, "walk", posix_walk)
    return load_source("host_ops_collect", ASYS / "collect/ops/ops_collect.py")


def make_vendor(root, name):
    config = root / "vendors" / name / "op_impl/config/ascend910b"
    config.mkdir(parents=True)
    (config / "available.json").write_text('{"available": true}', encoding="utf-8")


@pytest.mark.parametrize("missing_first", [True, False])
def test_missing_vendor_does_not_skip_available_vendor_or_manifest(
    collector, monkeypatch, tmp_path, missing_first
):
    opp = tmp_path / "opp"
    make_vendor(opp, "available")
    order = "missing,available" if missing_first else "available,missing"
    manifest = opp / "vendors/config.ini"
    manifest.write_text(f"load_priority={order}\n", encoding="utf-8")
    monkeypatch.setenv("ASCEND_OPP_PATH", str(opp))
    output = tmp_path / "output"

    assert collector.collect_opp_config(str(output)) is False
    target = output / "dfx/ops/vendor_config"
    assert (
        target / "available/op_impl/config/ascend910b/available.json"
    ).read_bytes() == (
        opp / "vendors/available/op_impl/config/ascend910b/available.json"
    ).read_bytes()
    assert (target / "config.ini").read_bytes() == manifest.read_bytes()


def test_all_available_vendors_still_succeed(collector, monkeypatch, tmp_path):
    opp = tmp_path / "opp"
    for vendor in ["first", "second"]:
        make_vendor(opp, vendor)
    (opp / "vendors/config.ini").write_text(
        "load_priority=first,second\n", encoding="utf-8"
    )
    monkeypatch.setenv("ASCEND_OPP_PATH", str(opp))
    output = tmp_path / "output"

    assert collector.collect_opp_config(str(output)) is True
    target = output / "dfx/ops/vendor_config"
    assert (target / "config.ini").is_file()
    for vendor in ["first", "second"]:
        assert (target / vendor / "op_impl/config/ascend910b/available.json").is_file()


def test_disappearing_json_does_not_skip_next_file(collector, monkeypatch, tmp_path):
    source = tmp_path / "custom/op_impl/config/ascend910b"
    source.mkdir(parents=True)
    vanished = source / "vanished.json"
    vanished.write_text("{}", encoding="utf-8")
    (source / "available.json").write_text("{}", encoding="utf-8")
    walk = os.walk

    def remove_after_listing(root):
        for path, directories, names in walk(root):
            if Path(path) == source:
                vanished.unlink()
                names = ["vanished.json", "available.json"]
            yield path, directories, names

    monkeypatch.setattr(collector.os, "walk", remove_after_listing)
    monkeypatch.setenv("ASCEND_CUSTOM_OPP_PATH", str(tmp_path / "custom"))
    output = tmp_path / "output"

    assert collector.collect_custom_opp_config(str(output)) is False
    assert (
        output / "dfx/ops/custom_config/op_impl/config/ascend910b/available.json"
    ).is_file()
