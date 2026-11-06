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

import subprocess
import sys
from pathlib import Path


ASYS_SRC = Path(__file__).resolve().parents[5] / "src" / "asys"
sys.path.insert(0, str(ASYS_SRC))

from collect.stackcore import stackcore_collect  # noqa: E402


def test_readelf_command_is_escaped(monkeypatch):
    """A binary path with shell metacharacters must not break out of the pipe.

    The path goes through ``bash -c "readelf -h <path> | grep EXEC"``; without
    shlex.quote an unquoted ``;`` ends the readelf command and lets the rest of
    the path run as a separate shell command.
    """
    parser = stackcore_collect.ParseStackCore([])
    parser.file = "stackcore.txt"  # make self.warning() emit through log_warning
    seen = {}

    def fake_run_linux_cmd(cmd, cmp_str=""):
        seen["cmd"] = cmd
        return False

    monkeypatch.setattr(stackcore_collect, "run_linux_cmd", fake_run_linux_cmd)
    # The existence checks only gate the readelf branch; bypass them because
    # the crafted path does not exist on disk.
    monkeypatch.setattr(stackcore_collect.os.path, "exists", lambda _p: True)
    monkeypatch.setattr(stackcore_collect.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(
        stackcore_collect.os,
        "stat",
        lambda _p, **_kw: type("S", (), {"st_mode": 0})(),
    )

    line = "0 00007f 00007f /tmp/dir;rm-rf;/libldsvo.so\n"
    parser.parse_line(0, line, [line])

    cmd = seen["cmd"]
    assert cmd.startswith("readelf -h ")
    # The metacharacter path must appear as one shell-escaped token.
    assert "'/tmp/dir;rm-rf;/libldsvo.so'" in cmd


def test_get_source_location_reports_real_error(monkeypatch, caplog):
    """A non-zero addr2line exit must surface its real cause, not a fixed text.

    The old handler swallowed CalledProcessError and always printed
    "is not permitted to read", which misdirected troubleshooting on healthy
    files.
    """
    caplog.set_level("DEBUG")

    def fake_check_output(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            returncode=1, cmd="addr2line", output=b"addr2line: corrupt ELF"
        )

    monkeypatch.setattr(stackcore_collect.subprocess, "check_output", fake_check_output)
    parser = stackcore_collect.ParseStackCore([])
    parser.file = "stackcore.txt"

    assert parser.get_source_location("/lib/libc.so", 4096) == []
    assert "cannot be parsed by addr2line" in caplog.text
    # The warning stays deduplicable: it names the exception type instead of
    # str(e), whose CalledProcessError repr embeds the per-frame hex address.
    assert "error: CalledProcessError." in caplog.text
    # The detailed message (with exit status) is kept at debug level.
    assert "returned non-zero exit status 1" in caplog.text
    assert "is not permitted to read" not in caplog.text


def test_get_source_location_warning_dedup_across_frames(monkeypatch, caplog):
    """Two frames of the same so must yield exactly one warning.

    warning() deduplicates by exact text per so_name; str(e) of a
    CalledProcessError embeds the per-frame address, so building the warning
    from str(e) printed one line per frame. The exception-type based text
    keeps the dedup working.
    """
    addresses = iter([0x1000, 0x2000])

    def fake_check_output(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            returncode=1, cmd=["addr2line", hex(next(addresses))], output=b""
        )

    monkeypatch.setattr(stackcore_collect.subprocess, "check_output", fake_check_output)
    parser = stackcore_collect.ParseStackCore([])
    parser.file = "stackcore.txt"

    parser.get_source_location("/lib/libc.so", 0x1000)
    parser.get_source_location("/lib/libc.so", 0x2000)

    warnings = [
        r
        for r in caplog.records
        if r.levelname == "WARNING" and "addr2line" in r.message
    ]
    assert len(warnings) == 1
