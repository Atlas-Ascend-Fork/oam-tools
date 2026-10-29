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
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def asys_modules(monkeypatch):
    relative = Path("src/asys/cmdline/arg_checker.py")
    repository = next(
        (
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / relative).is_file()
            and ((parent / ".git").exists() or (parent / "pyproject.toml").is_file())
        ),
        None,
    )
    assert repository is not None, (
        "Cannot locate the OAM repository containing the argument checker"
    )
    root = repository / "src/asys"
    common = ModuleType("common")
    common.__path__ = [str(root / "common")]
    common.log_error = Mock()
    common.DeviceInfo = Mock()
    log = ModuleType("common.log")
    log.log_error = common.log_error
    log.log_debug = Mock()
    monkeypatch.setitem(sys.modules, "common", common)
    monkeypatch.setitem(sys.modules, "common.log", log)

    def load(name, relative):
        spec = importlib.util.spec_from_file_location(name, root / relative)
        api = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, api)
        spec.loader.exec_module(api)
        return api

    const = load("common.const", "common/const.py")
    files = load("common.file_operate", "common/file_operate.py")
    common.FileOperate = files.FileOperate
    return load, const, files


@pytest.fixture
def checker(asys_modules):
    load, const, _files = asys_modules
    return load("_output_mkdir_checker", "cmdline/arg_checker.py"), const.RetCode


def test_regular_file_parent_reports_real_mkdir_failure(checker, tmp_path, monkeypatch):
    api, codes = checker
    monkeypatch.chdir(tmp_path)
    (tmp_path / "parent").write_text("preserve", encoding="utf-8")
    assert (
        api.check_arg_create_dir("output", "parent/child")
        == codes.ARG_CREATE_DIR_FAILED
    )
    assert (tmp_path / "parent").read_text(encoding="utf-8") == "preserve"
    assert not (tmp_path / "parent/child").exists()


def test_missing_nested_output_is_created(checker, tmp_path, monkeypatch):
    api, codes = checker
    monkeypatch.chdir(tmp_path)
    assert api.check_arg_create_dir("output", "new/child") == codes.SUCCESS
    assert (tmp_path / "new/child").is_dir()


def test_existing_output_remains_success(checker, tmp_path, monkeypatch):
    api, codes = checker
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing").mkdir()
    assert api.check_arg_create_dir("output", "existing") == codes.SUCCESS


def test_unwritable_parent_reports_creation_failure(checker, tmp_path, monkeypatch):
    api, codes = checker
    monkeypatch.chdir(tmp_path)
    actual_access = api.os.access
    monkeypatch.setattr(
        api.os,
        "access",
        lambda path, mode: False if mode == os.W_OK else actual_access(path, mode),
    )
    assert (
        api.check_arg_create_dir("output", "new-output") == codes.ARG_CREATE_DIR_FAILED
    )
    assert not (tmp_path / "new-output").exists()


def test_existing_regular_file_keeps_existing_nondirectory_error(
    checker, tmp_path, monkeypatch
):
    api, codes = checker
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "output-file"
    target.write_text("preserve", encoding="utf-8")
    assert api.check_arg_create_dir("output", "output-file") == codes.ARG_NO_EXIST_DIR
    assert target.read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize("kind", ["writable-directory", "file", "unwritable-directory"])
def test_concurrent_creator_requires_writable_directory(
    checker, tmp_path, monkeypatch, kind
):
    api, codes = checker
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "raced-output"
    actual_access = api.os.access

    def concurrent_create(path):
        assert path == str(target)
        if kind == "file":
            target.write_text("preserve", encoding="utf-8")
        else:
            target.mkdir()
        return False

    def access(path, mode):
        if kind == "unwritable-directory" and path == str(target) and mode == os.W_OK:
            return False
        return actual_access(path, mode)

    monkeypatch.setattr(api.f, "create_dir", concurrent_create)
    monkeypatch.setattr(api.os, "access", access)
    expected = (
        codes.SUCCESS if kind == "writable-directory" else codes.ARG_CREATE_DIR_FAILED
    )
    assert api.check_arg_create_dir("output", "raced-output") == expected
    if kind == "file":
        assert target.read_text(encoding="utf-8") == "preserve"
