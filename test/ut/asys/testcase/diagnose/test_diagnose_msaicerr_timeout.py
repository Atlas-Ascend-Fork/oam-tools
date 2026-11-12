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

# ruff: noqa: E501, S607  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock patterns

import os
import subprocess
import threading
import time

import pytest

from common.const import MSAICERR_ENV_TIMEOUT
from diagnose.asys_diagnose import AsysDiagnose
from ..conftest import AssertTest


def setup_module():
    print("TestDiagnoseMsaicerrTimeout ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestDiagnoseMsaicerrTimeout ut test finish.")  # noqa: T201  # test diagnostic output


class TestDiagnoseMsaicerrTimeout(AssertTest):
    def test_env_timeout_budget_is_one_minute_per_card(self):
        # #399 已拍板的超时规格：msaicerr --env 单卡执行超时 1 分钟
        self.assertTrue(MSAICERR_ENV_TIMEOUT == 60)

    def test_run_msaicerr_cmd_passes_the_budget(self, mocker):
        # 超时预算必须真的传给 run_timed：不传的话 msaicerr --env 挂死时
        # diagnose 主流程永久阻塞（#399 清单 #6）。
        from diagnose import asys_diagnose

        seen = {}
        real_run_timed = asys_diagnose.run_timed

        def spy_run_timed(cmd, **kwargs):
            seen.update(kwargs)
            return real_run_timed(["true"], check=False, stdout=subprocess.DEVNULL)

        mocker.patch.object(asys_diagnose, "run_timed", side_effect=spy_run_timed)
        result = {}
        AsysDiagnose.run_msaicerr_cmd("/any/msaicerr.py", 0, result)
        self.assertTrue(seen.get("timeout") == MSAICERR_ENV_TIMEOUT)

    def test_run_msaicerr_cmd_timeout_marks_device_failed(self, mocker, caplog):
        # 挂死的 msaicerr --env：TimeoutExpired 须按设备记 Fail 并返回空输出，
        # 与 OSError 失败路径同一契约，且给出可检索的超时告警日志。
        from diagnose import asys_diagnose

        mocker.patch.object(
            asys_diagnose,
            "run_timed",
            side_effect=subprocess.TimeoutExpired(cmd="msaicerr --env", timeout=60),
        )
        result = {}

        output = AsysDiagnose.run_msaicerr_cmd("/missing/msaicerr.py", 3, result)

        self.assertTrue(output == "")
        self.assertTrue(result == {3: "Fail"})
        self.assertTrue("timed out" in caplog.text)

    @pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
    def test_run_msaicerr_cmd_timeout_kills_the_whole_group(
        self, tmp_path, monkeypatch
    ):
        # 检视意见：subprocess.run 超时只杀直接子进程 msaicerr.py，孙进程
        # golden_op.py 会继续运行。改用 run_timed 后超时 kill 整个进程组，
        # 模拟 msaicerr 再拉起孙进程的形态，断言超时后孙进程一并消失。
        monkeypatch.setattr("diagnose.asys_diagnose.MSAICERR_ENV_TIMEOUT", 1)
        # 形态与真实链路一致：直接子进程(msaicerr 占位，忽略 --env/-dev 入参)
        # 再启动孙进程(golden_op 占位)并 wait 它，孙进程写 pid 后 sleep 30 挂死。
        grandchild_pid_file = tmp_path / "golden.pid"
        golden_stub = tmp_path / "golden_stub.py"
        golden_stub.write_text(
            "#!/usr/bin/env python3\n"
            "import os, time\n"
            f"open({str(grandchild_pid_file)!r}, 'w').write(str(os.getpid()))\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )
        msaicerr_stub = tmp_path / "msaicerr_stub.py"
        msaicerr_stub.write_text(
            "#!/usr/bin/env python3\n"
            "import os, subprocess, sys\n"
            "proc = subprocess.Popen([sys.executable, os.environ['GOLDEN_STUB']])\n"
            "proc.wait()\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("GOLDEN_STUB", str(golden_stub))

        result = {}
        worker_output = {}

        def call():
            worker_output["out"] = AsysDiagnose.run_msaicerr_cmd(
                str(msaicerr_stub), 0, result
            )

        worker = threading.Thread(target=call, daemon=True)
        start = time.monotonic()
        worker.start()
        worker.join(timeout=5)
        elapsed = time.monotonic() - start
        assert not worker.is_alive(), "run_msaicerr_cmd blocked past the budget"
        assert worker_output["out"] == ""
        assert result == {0: "Fail"}
        assert elapsed < 4.5
        # 孙进程必须已被回收：pid 文件写出后轮询 os.kill(pid, 0)，
        # ProcessLookupError 即消亡（2s 上限）。
        deadline = time.monotonic() + 2
        assert grandchild_pid_file.exists(), "grandchild never started"
        pid = int(grandchild_pid_file.read_text())
        reaped = False
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except (ProcessLookupError, PermissionError):
                reaped = True
                break
            time.sleep(0.05)
        assert reaped, f"grandchild golden_op stub (pid {pid}) survived the timeout"
