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

"""Host regressions with real regular files and real Python subprocesses."""

import stat
import sys

import pytest

from ms_interface import utils


OLD_CONTENT = "previous report with trailing text"
OWNER_READ_ONLY = stat.S_IRUSR


@pytest.mark.parametrize("content", ["short", "", "界"])
@pytest.mark.parametrize("mode", [None, "w"])
def test_overwrite_existing_file(tmp_path, content, mode):
    output = tmp_path / "report.txt"
    output.write_text(OLD_CONTENT)
    if mode is None:
        utils.write_file(str(output), content)
    else:
        utils.write_file(str(output), content, write_mode=mode)
    assert output.read_text() == content
    assert stat.S_IMODE(output.stat().st_mode) == OWNER_READ_ONLY


@pytest.mark.parametrize("mode", ["wt", "w+", "w+t", "tw"])
def test_text_and_update_write_modes_replace_existing_file(tmp_path, mode):
    output = tmp_path / "report.txt"
    output.write_text(OLD_CONTENT)
    utils.write_file(str(output), "new", write_mode=mode)
    assert output.read_text() == "new"


def test_exclusive_mode_preserves_existing_file(tmp_path):
    output = tmp_path / "report.txt"
    output.write_text(OLD_CONTENT)
    with pytest.raises(utils.AicErrException):
        utils.write_file(str(output), "new", write_mode="x")
    assert output.read_text() == OLD_CONTENT


@pytest.mark.parametrize("mode", ["a", "a+"])
def test_append_preserves_existing_content(tmp_path, mode):
    output = tmp_path / "report.txt"
    output.write_text("prefix")
    utils.write_file(str(output), "suffix", write_mode=mode)
    assert output.read_text() == "prefixsuffix"


@pytest.mark.parametrize("mode", ["a", "a+"])
def test_consecutive_appends_stay_writable_and_ordered(tmp_path, mode):
    output = tmp_path / "report.txt"
    utils.write_file(str(output), "first", write_mode=mode)
    utils.write_file(str(output), "second", write_mode=mode)
    assert output.read_text() == "firstsecond"
    assert stat.S_IMODE(output.stat().st_mode) == stat.S_IRUSR | stat.S_IWUSR


@pytest.mark.parametrize("mode", ["w", "x"])
def test_new_output_is_owner_read_only(tmp_path, mode):
    output = tmp_path / "new_report.txt"
    utils.write_file(str(output), "new", write_mode=mode)
    assert output.read_text() == "new"
    assert stat.S_IMODE(output.stat().st_mode) == OWNER_READ_ONLY


@pytest.mark.parametrize("content", ["fresh", "", "界"])
def test_execute_command_overwrites_stdout_file(tmp_path, content):
    output = tmp_path / "decompile.txt"
    output.write_text(OLD_CONTENT)
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write(sys.argv[1])",
        content,
    ]
    status, stderr = utils.execute_command(command, file_out=str(output))
    assert status == 0
    assert stderr == ""
    assert output.read_text() == content
    assert stat.S_IMODE(output.stat().st_mode) == OWNER_READ_ONLY


def test_execute_command_new_file_keeps_stdout_and_stderr_separate(tmp_path):
    output = tmp_path / "decompile.txt"
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write('output'); sys.stderr.write('warning')",
    ]
    status, stderr = utils.execute_command(command, file_out=str(output))
    assert status == 0
    assert stderr == "warning"
    assert output.read_text() == "output"
    assert stat.S_IMODE(output.stat().st_mode) == OWNER_READ_ONLY


def test_execute_command_without_file_keeps_combined_output():
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write('output'); sys.stderr.write('warning')",
    ]
    status, combined = utils.execute_command(command)
    assert status == 0
    assert "output" in combined
    assert "warning" in combined


@pytest.mark.parametrize("mode", ["wa", "wbt"])
def test_invalid_modes_do_not_modify_existing_file(tmp_path, mode):
    output = tmp_path / "report.txt"
    output.write_text(OLD_CONTENT)
    with pytest.raises(ValueError):
        utils.write_file(str(output), "new", write_mode=mode)
    assert output.read_text() == OLD_CONTENT
