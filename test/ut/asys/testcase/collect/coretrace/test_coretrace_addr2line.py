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

# ruff: noqa: E501  # the fake addr2line body is a shell one-liner

import os
import stat
import threading

import pytest

from collect.coretrace.coretrace_collect import ParseCoreTrace
from testcase.conftest import AssertTest


def _write_noisy_addr2line(directory, stderr_bytes):
    """A stand-in for addr2line that writes line-folded noise to stderr.

    The folding matters: without newlines the noise would join the trailing
    "main" and an exact-output assertion could not tell DEVNULL from STDOUT.
    """
    path = os.path.join(str(directory), "addr2line")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n")
        if stderr_bytes:
            handle.write(
                f'head -c {stderr_bytes} /dev/zero | tr "\\0" "x" | fold -w 64 >&2\n'
            )
        handle.write('echo "main"\n')
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


class TestCoreTraceAddr2line(AssertTest):
    @pytest.mark.skipif(os.name != "posix", reason="needs a shell stand-in binary")
    def test_noisy_addr2line_does_not_block_the_collector(self, tmp_path):
        # stderr used to be a PIPE nobody drained: once addr2line had more than
        # a pipe buffer of diagnostics it blocked in write(stderr) while the
        # collector blocked in readlines(stdout), hanging the whole run.
        exe = _write_noisy_addr2line(tmp_path, 128 * 1024)
        result = {}

        def call():
            result["out"] = ParseCoreTrace.run_addr2line([exe, "-e", "/bin/ls", "0x1"])

        worker = threading.Thread(target=call, daemon=True)
        worker.start()
        worker.join(timeout=8)

        assert not worker.is_alive(), "run_addr2line blocked on an undrained stderr"
        # Exact output: switching DEVNULL back to STDOUT would put the folded
        # diagnostics into stdout and this no longer holds.
        assert result["out"] == ["main\n"], result["out"][:5]

    @pytest.mark.skipif(os.name != "posix", reason="needs a shell stand-in binary")
    def test_quiet_addr2line_keeps_its_output(self, tmp_path):
        exe = _write_noisy_addr2line(tmp_path, 0)
        out = ParseCoreTrace.run_addr2line([exe, "-e", "/bin/ls", "0x1"])

        assert out == ["main\n"], out

    @pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
    def test_child_is_fully_reaped_before_returning(self):
        """Without reaping the child, its output would never arrive.

        #955 检视意见后 run_addr2line 走 run_timed（communicate 等待，退出
        即已回收）：只有子进程被完整回收（且无孤儿），stdout 才能完整到达，
        返回行列表与旧 readlines 契约一致。
        """
        out = ParseCoreTrace.run_addr2line(["echo", "main"])
        assert out == ["main\n"], out
