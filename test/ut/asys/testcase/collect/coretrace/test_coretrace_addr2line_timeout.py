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

# ruff: noqa: E501  # long lines

import subprocess
import threading

import pytest

from common.const import ADDR2LINE_TIMEOUT
from testcase.conftest import AssertTest

from collect.coretrace.coretrace_collect import ParseCoreTrace


def setup_module():
    print("TestCoretraceAddr2lineTimeout ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestCoretraceAddr2lineTimeout ut test finish.")  # noqa: T201  # test diagnostic output


class TestCoretraceAddr2lineTimeout(AssertTest):
    def test_run_addr2line_passes_the_budget(self, mocker):
        # #399 超时规格：addr2line 逐帧符号化超时 1 分钟。预算必须真的传给
        # run_timed 的 communicate(timeout)——不传的话挂死的 addr2line 把解析
        # 线程永久阻塞在等待上（#399 清单 #7，检视意见后由自建 Timer 改为
        # run_timed，确保超时 kill 进程组、部分输出被丢弃）。
        from collect.coretrace import coretrace_collect

        seen = {}
        real_run_timed = coretrace_collect.run_timed

        def spy_run_timed(cmd, **kwargs):
            seen.update(kwargs)
            kwargs["stdout"] = subprocess.PIPE
            kwargs.setdefault("encoding", "utf-8")
            return real_run_timed(["echo", "main"], **kwargs)

        mocker.patch.object(coretrace_collect, "run_timed", spy_run_timed)
        out = ParseCoreTrace.run_addr2line(["addr2line"])
        self.assertTrue(out == ["main\n"])
        self.assertTrue(seen.get("timeout") == ADDR2LINE_TIMEOUT)

    @pytest.mark.skipif(
        not hasattr(subprocess, "TimeoutExpired"),
        reason="needs subprocess timeouts",
    )
    def test_run_addr2line_timeout_returns_empty(self, tmp_path, monkeypatch):
        # 挂死的 addr2line：整条命令在预算内返回空列表（既有"该帧无符号"
        # 降级），调用线程不阻塞。用真子进程验证墙钟边界；预算压到 1s，
        # 站位进程用 python 单进程 sleep（无孙进程持有管道）。
        import time

        monkeypatch.setattr("collect.coretrace.coretrace_collect.ADDR2LINE_TIMEOUT", 1)
        exe = tmp_path / "addr2line"
        exe.write_text(
            "#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n", encoding="utf-8"
        )
        exe.chmod(0o755)
        result = {}

        def call():
            result["out"] = ParseCoreTrace.run_addr2line(
                [str(exe), "-e", "/bin/ls", "0x1"]
            )

        worker = threading.Thread(target=call, daemon=True)
        start = time.monotonic()
        worker.start()
        worker.join(timeout=5)
        elapsed = time.monotonic() - start
        assert not worker.is_alive(), "run_addr2line blocked past the timeout budget"
        assert result["out"] == []
        assert elapsed < 4.5
