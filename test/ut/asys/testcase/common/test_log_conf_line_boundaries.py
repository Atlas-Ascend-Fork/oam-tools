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

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def asys_modules(monkeypatch):
    root = Path(__file__).resolve().parents[5] / "src/asys"
    common = ModuleType("common")
    common.log_error = Mock()
    common.log_warning = Mock()
    monkeypatch.setitem(sys.modules, "common", common)

    def load(name, relative):
        spec = importlib.util.spec_from_file_location(name, root / relative)
        api = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, api)
        spec.loader.exec_module(api)
        return api

    return load


@pytest.fixture
def api(asys_modules):
    return asys_modules("_log_conf_boundary", "common/path.py")


@pytest.mark.parametrize(
    "kind,key,config",
    [
        ("slog", "logAgentFileDir", "/etc/slog.conf"),
        ("bbox", "MNTN_PATH", "/etc/bbox.conf"),
    ],
)
@pytest.mark.parametrize(
    "contents",
    [
        "{key}=/active",
        "\ufeff{key}=/active\n",
        "{key}=/active   \n",
        "# comment\r\n{key}=/active",
        "#{key}=/disabled\n{key}=/active\n",
        "  {key} = /active\r\n",
        "other_{key}=/disabled\n{key}=/active\n",
    ],
)
def test_only_active_assignments_define_paths(
    api, monkeypatch, tmp_path, kind, key, config, contents
):
    path = tmp_path / "config.txt"
    path.write_bytes(contents.format(key=key).encode("utf-8"))
    monkeypatch.setattr(api.os.path, "exists", lambda name: name == config)
    # Replace only lookup of the system configuration file with a real temp file.
    monkeypatch.setattr(
        api,
        "open",
        lambda _name, *args, **kwargs: path.open(*args, **kwargs),
        raising=False,
    )
    assert api.get_log_conf_path(kind) == "/active"


def test_missing_configuration_retains_default(api, monkeypatch):
    monkeypatch.setattr(api.os.path, "exists", lambda _name: False)
    assert api.get_log_conf_path("slog") == "/var/log/npu/slog/"


def test_unknown_log_kind_retains_none(api):
    assert api.get_log_conf_path("unknown") is None


@pytest.mark.parametrize(
    "kind,key,config,default",
    [
        ("slog", "logAgentFileDir", "/etc/slog.conf", "/var/log/npu/slog/"),
        ("bbox", "MNTN_PATH", "/etc/bbox.conf", "/var/log/npu/hisi_logs/"),
    ],
)
@pytest.mark.parametrize("value", ["", " ", "   ", "\t "])
def test_empty_assignment_keeps_default(
    api, monkeypatch, tmp_path, kind, key, config, default, value
):
    path = tmp_path / "config.txt"
    path.write_bytes(f"{key}={value}\n".encode("utf-8"))
    # os.path is shared; pytest restores the patch after each case.
    monkeypatch.setattr(api.os.path, "exists", lambda name: name == config)
    monkeypatch.setattr(
        api,
        "open",
        lambda _name, *args, **kwargs: path.open(*args, **kwargs),
        raising=False,
    )
    assert api.get_log_conf_path(kind) == default
