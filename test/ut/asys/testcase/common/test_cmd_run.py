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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

import gc
import importlib
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time

import pytest

from common import (
    popen_run_cmd,
    real_time_output,
    run_command,
    run_cmd_output,
    run_linux_cmd,
)
from common import cmd_run
from ..conftest import AssertTest


def setup_module():
    print("TestCmdRun ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestCmdRun ut test finish.")  # noqa: T201  # test diagnostic output


class TestCmdRun(AssertTest):
    def test_run_command_success(self, mocker):
        cmd = "ls"
        fake_ret = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command(cmd) != "NONE")

    def test_run_command_failed(self, mocker):
        cmd = "not_exist_cmd"
        fake_ret = subprocess.CompletedProcess(
            args=cmd,
            returncode=127,
            stdout="",
            stderr="/bin/sh: 1: not_exist_cmd: not found\n",
        )
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command(cmd) == "NONE")

    def test_run_command_success_with_warning_on_stderr(self, mocker):
        # rc==0 with valid stdout: stderr warnings must not discard it (#205).
        fake_ret = subprocess.CompletedProcess(
            args="query", returncode=0, stdout="value\n", stderr="warning\n"
        )
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command("query") == "value")

    def test_run_command_success_with_empty_stdout(self, mocker):
        # rc==0, stdout empty, stderr non-empty: upstream pipeline failure
        # (cat reports the missing file while awk still exits 0) keeps the
        # NONE sentinel for failure visibility.
        fake_ret = subprocess.CompletedProcess(
            args="query", returncode=0, stdout="", stderr="cat: no such file\n"
        )
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command("query") == "NONE")

    def test_run_command_success_without_any_output(self, mocker):
        # rc==0 with both streams empty: historical empty-string contract.
        fake_ret = subprocess.CompletedProcess(
            args="query", returncode=0, stdout="", stderr=""
        )
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command("query") == "")

    def test_run_command_success_with_blank_stderr(self, mocker):
        # rc==0, stdout empty, whitespace-only stderr: the emptiness criterion
        # is stripped for both streams, so a blank stderr must not trigger the
        # NONE sentinel.
        fake_ret = subprocess.CompletedProcess(
            args="query", returncode=0, stdout="", stderr="  \n\t"
        )
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command("query") == "")

    def test_run_msnpureport_success(self, mocker):
        cmd = "ls"
        fake_ret = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_cmd_output(cmd)[0])
        self.assertTrue(run_cmd_output(cmd)[1] != "NONE")

    def test_run_msnpureport_failed(self, mocker):
        cmd = "not supported cmd"
        fake_ret = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(not run_cmd_output(cmd)[0])

    def test_run_linux_cmd(self):
        self.assertTrue(run_linux_cmd("ls"))

    def test_run_linux_cmd_error(self):
        self.assertTrue(not run_linux_cmd(1))

    def test_bash_is_str_when_which_misses(self, mocker):
        # shutil.which 取不到 bash 时 BASH 必须回退为 str，否则 argv[0]=None 会抛 TypeError
        mocker.patch("shutil.which", return_value=None)
        try:
            importlib.reload(cmd_run)
            self.assertTrue(isinstance(cmd_run.BASH, str))
        finally:
            mocker.stopall()
            importlib.reload(cmd_run)

    def test_run_command_oserror(self, mocker):
        # bash 不存在时 subprocess.run 抛 OSError，run_command 应兜住并返回 NONE
        mocker.patch("subprocess.run", side_effect=FileNotFoundError("no bash"))
        self.assertTrue(run_command("ls") == "NONE")

    def test_run_cmd_output_oserror(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError("no bash"))
        self.assertTrue(run_cmd_output("ls") == (False, ""))


class TestCmdRunTimeout(AssertTest):
    """Issue #399 P2 root fix: the five cmd_run executors accept an optional
    timeout; on expiry the whole process group is killed (no orphaned
    grandchildren) and the historical return contract is kept."""

    SLEEP = "sleep 30"

    def test_run_linux_cmd_timeout_returns_false(self):
        self.assertTrue(run_linux_cmd(self.SLEEP, timeout=0.2) is False)

    def test_run_command_timeout_returns_none_sentinel(self):
        self.assertTrue(run_command(self.SLEEP, timeout=0.2) == "NONE")

    def test_run_cmd_output_timeout_returns_failure_pair(self):
        self.assertTrue(run_cmd_output(self.SLEEP, timeout=0.2) == (False, ""))

    def test_popen_run_cmd_timeout_returns_empty(self):
        self.assertTrue(popen_run_cmd(self.SLEEP, timeout=0.2) == "")

    def test_real_time_output_timeout_returns_false(self):
        self.assertTrue(
            real_time_output(self.SLEEP, output=False, timeout=0.2) is False
        )

    def test_real_time_output_timeout_covers_stdout_read(self):
        result = real_time_output("printf 'started\\n'; sleep 1", timeout=0.1)
        self.assertTrue(result is False)

    def test_real_time_output_discards_large_output(self):
        result = real_time_output("yes | head -n 100000", output=False, timeout=1)
        self.assertTrue(result is True)

    @pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
    def test_timeout_kills_process_group_no_orphan(self, tmp_path):
        # grandchild `sleep 30` must not survive the timeout of its parent
        marker = tmp_path / "child pid"
        cmd = "sleep 30 & echo $! > {0}; wait".format(shlex.quote(str(marker)))
        self.assertTrue(run_linux_cmd(cmd, timeout=1) is False)
        deadline = time.monotonic() + 1
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "grandchild pid marker was not created"
        child_pid = int(marker.read_text(encoding="utf-8").strip())

        deadline = time.monotonic() + 2
        while True:
            ps = subprocess.run(
                ["ps", "-o", "stat=", "-p", str(child_pid)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=False,
            )
            state = ps.stdout.strip()
            if not state or state.startswith("Z"):
                break
            assert time.monotonic() < deadline, "grandchild is still running"
            time.sleep(0.05)

    def test_no_timeout_keeps_historical_contract(self):
        # default timeout=None: behavior byte-for-byte unchanged
        self.assertTrue(run_command("echo hi") == "hi")
        self.assertTrue(run_linux_cmd("true") is True)
        self.assertTrue(run_cmd_output("echo hi") == (True, "hi\n"))

    def test_real_time_output_returns_false_when_grandchild_outlives_child(self):
        start = time.monotonic()
        result = real_time_output("sleep 3 & exit", output=False, timeout=0.2)
        elapsed = time.monotonic() - start
        self.assertTrue(result is False)
        self.assertTrue(elapsed < 1.0)

    @pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
    def test_run_command_timeout_is_bounded_with_detached_grandchild(self):
        launcher = (
            "import subprocess; "
            "subprocess.Popen(['sleep', '3'], start_new_session=True)"
        )
        command = "{} -c {} & wait".format(
            shlex.quote(sys.executable), shlex.quote(launcher)
        )
        start = time.monotonic()
        result = run_command(command, timeout=0.2)
        elapsed = time.monotonic() - start
        self.assertTrue(result == "NONE")
        self.assertTrue(elapsed < 1.5)

    def test_timeout_encoding_contracts(self):
        command = "printf '\\346\\265'; sleep 3"
        start = time.monotonic()
        self.assertTrue(run_command(command, timeout=0.1) == "NONE")
        self.assertTrue(run_cmd_output(command, timeout=0.1) == (False, ""))
        self.assertTrue(popen_run_cmd(command, timeout=0.1) == "")
        self.assertTrue(time.monotonic() - start < 1.5)

    def test_timeout_uses_warning_log(self, mocker):
        warning = mocker.patch("common.cmd_run.log_warning")
        self.assertTrue(run_command("sleep 1", timeout=0.1) == "NONE")
        warning.assert_called_once()
        self.assertTrue("timed out" in warning.call_args.args[0])

    def test_real_time_reader_is_daemon(self, mocker):
        thread = mocker.patch("common.cmd_run.threading.Thread", wraps=threading.Thread)
        self.assertTrue(real_time_output("true", output=False, timeout=1) is True)
        self.assertTrue(thread.call_args.kwargs.get("daemon") is True)

    def test_real_time_timeout_does_not_close_stdout_wrapper(self, mocker):
        # 检视意见 A：清理路径不能 close(process.stdout)。读线程可能正阻塞在
        # `for line in process.stdout` 内部，BufferedReader 整个读取期间持锁，
        # close() 会与被阻塞的读互相等待而死锁，超时就不再是墙钟边界。
        process = mocker.Mock()
        process.stdout.fileno.return_value = -1
        reader = mocker.Mock()
        mocker.patch("common.cmd_run._kill_process_group")
        mocker.patch("common.cmd_run._wait_after_kill")
        mocker.patch("common.cmd_run._log_timeout")
        result = cmd_run._stop_real_time(process, reader, "command", 0.2)
        self.assertTrue(result is False)
        process.stdout.close.assert_not_called()

        unraisable = []
        mocker.patch("sys.unraisablehook", side_effect=unraisable.append)
        result = real_time_output("sleep 3 & exit", output=False, timeout=0.2)
        self.assertTrue(result is False)
        gc.collect()
        self.assertTrue(
            not any("Bad file descriptor" in str(error) for error in unraisable)
        )

    @pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
    def test_real_time_timeout_with_detached_writer_does_not_block(self, tmp_path):
        # 检视意见 A 回归：脱离进程组的孙进程仍持有 stdout 管道写端时，读线程
        # 会一直阻塞在 read 上；清理路径若 close(process.stdout) 就会死锁。
        # 这里断言 real_time_output 在墙钟上及时返回 False。
        pid_file = tmp_path / "detached.pid"
        pid_arg = shlex.quote(str(pid_file))
        if shutil.which("setsid"):
            detached = "setsid sleep 100000"
        else:
            # macOS 等无 setsid 的环境：用 os.setsid() 复现同样的拓扑
            # （孙进程自建会话、不随原进程组被杀，且继承 stdout）。
            launcher = "import os, time; os.setsid(); time.sleep(100000)"
            detached = "{} -c {}".format(
                shlex.quote(sys.executable), shlex.quote(launcher)
            )
        command = "{} & echo $! > {}; sleep 100000".format(detached, pid_arg)
        try:
            start = time.monotonic()
            result = real_time_output(command, output=False, timeout=0.5)
            elapsed = time.monotonic() - start
            self.assertTrue(result is False)
            assert elapsed < 5.0, "real_time_output blocked for {0:.2f}s".format(
                elapsed
            )
        finally:
            # 脱离会话的孙进程不受进程组 kill 影响，测试自己回收，避免残留。
            deadline = time.monotonic() + 2
            while not pid_file.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            if pid_file.exists():
                try:
                    os.kill(
                        int(pid_file.read_text(encoding="utf-8").strip()),
                        signal.SIGKILL,
                    )
                except (OSError, ValueError):
                    pass

    def test_real_time_output_write_error_without_timeout_raises(self, mocker):
        # 检视意见 B：同步路径下的写错误必须抛给调用方（与基线一致），不能被
        # `except (OSError, ValueError)` 吞掉，否则默认 timeout=None 的生产调用
        # 会从快速失败退化为一直读到子进程结束。
        mocker.patch("sys.stdout.write", side_effect=BrokenPipeError("broken pipe"))
        start = time.monotonic()
        with pytest.raises(BrokenPipeError):
            real_time_output("echo hi; sleep 2", output=True)
        elapsed = time.monotonic() - start
        assert elapsed < 1.5, "write error was swallowed for {0:.2f}s".format(elapsed)

    def test_real_time_output_timed_write_error_is_reraised(self, mocker):
        # 检视意见 B：超时（线程）路径下写错误由读线程捕获，real_time_output 在
        # 完成进程组清理后重新抛出，既不静默丢弃也不变成挂死。
        mocker.patch("sys.stdout.write", side_effect=BrokenPipeError("broken pipe"))
        start = time.monotonic()
        with pytest.raises(BrokenPipeError):
            real_time_output("echo hi; sleep 30", output=True, timeout=0.3)
        elapsed = time.monotonic() - start
        assert elapsed < 3.0, "timed write error took {0:.2f}s".format(elapsed)

        # 子进程在超时前正常退出时同样要重新抛出（join 之后检查）。
        with pytest.raises(BrokenPipeError):
            real_time_output("echo hi", output=True, timeout=2)

    INVALID_UTF8 = "printf 'ok\\200tail\\n'"

    def test_invalid_utf8_without_timeout_matches_base_contract(self):
        # 检视意见 C：timeout=None 时必须逐字节还原基线行为——encoding 为纯
        # utf-8，非法字节抛 UnicodeDecodeError（ValueError），由调用方转为
        # 失败返回值；real_time_output 则直接抛出（基线同样直接抛出）。
        self.assertTrue(run_command(self.INVALID_UTF8) == "NONE")
        self.assertTrue(run_cmd_output(self.INVALID_UTF8) == (False, ""))
        with pytest.raises(UnicodeDecodeError):
            real_time_output(self.INVALID_UTF8, output=True)
        with pytest.raises(UnicodeDecodeError):
            popen_run_cmd(self.INVALID_UTF8)

    def test_invalid_utf8_with_timeout_is_replaced(self, mocker):
        # 检视意见 C：只有带超时的路径才注入 errors="replace"，截断的多字节
        # 序列不应抛解码错误。
        result = run_command(self.INVALID_UTF8, timeout=2)
        self.assertTrue(isinstance(result, str))
        self.assertTrue(result.startswith("ok"))
        self.assertTrue(result.endswith("tail"))
        self.assertTrue("\ufffd" in result)

        ok, out = run_cmd_output(self.INVALID_UTF8, timeout=2)
        self.assertTrue(ok is True)
        self.assertTrue("\ufffd" in out)

        write = mocker.patch("sys.stdout.write")
        self.assertTrue(
            real_time_output(self.INVALID_UTF8, output=True, timeout=2) is True
        )
        write.assert_called_once_with("ok\ufffdtail\n")

    @pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
    def test_cleanup_without_kill_stays_bounded(self, mocker):
        # 检视意见 D：_kill_process_group 失效（此处 no-op）时，_wait_after_kill
        # 仍以 _CLEANUP_GRACE 兜底，超时不会被拖成对子进程的无界等待。
        mocker.patch("common.cmd_run._kill_process_group")
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            cmd_run._run_timed(
                [cmd_run.BASH, "-c", "sleep 5"],
                timeout=0.3,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        elapsed = time.monotonic() - start
        self.assertTrue(elapsed >= 0.3)
        assert elapsed < 3.0, "_run_timed waited {0:.2f}s".format(elapsed)

        start = time.monotonic()
        result = real_time_output("sleep 5", output=False, timeout=0.3)
        elapsed = time.monotonic() - start
        self.assertTrue(result is False)
        assert elapsed < 3.5, "real_time_output waited {0:.2f}s".format(elapsed)

    def test_run_timed_keyboardinterrupt_kills_process_group(self, mocker):
        # 检视意见（diff 198750377）：communicate() 期间的非超时异常（交互式 CLI
        # 下最常见的是 Ctrl-C）必须像 base 的 subprocess.run 那样先回收进程组
        # 再原样抛出，否则 start_new_session 出来的整个会话无人可达。
        process = mocker.Mock()
        process.communicate.side_effect = KeyboardInterrupt
        mocker.patch("common.cmd_run.subprocess.Popen", return_value=process)
        kill = mocker.patch("common.cmd_run._kill_process_group")
        wait = mocker.patch("common.cmd_run._wait_after_kill")
        with pytest.raises(KeyboardInterrupt):
            cmd_run._run_timed(["cmd"], timeout=1)
        kill.assert_called_once_with(process)
        wait.assert_called_once_with(process)

    def test_real_time_output_keyboardinterrupt_kills_process_group(self, mocker):
        # 同上，real_time_output 的超时（自建会话）分支：中断时也要 kill + 有界
        # 回收后原样抛出。
        process = mocker.Mock()
        process.wait.side_effect = KeyboardInterrupt
        mocker.patch("common.cmd_run.subprocess.Popen", return_value=process)
        mocker.patch("common.cmd_run._drain_output")
        kill = mocker.patch("common.cmd_run._kill_process_group")
        wait = mocker.patch("common.cmd_run._wait_after_kill")
        with pytest.raises(KeyboardInterrupt):
            real_time_output("cmd", output=False, timeout=1)
        kill.assert_called_once_with(process)
        wait.assert_called_once_with(process)

        # timeout=None 路径与 base 逐字节一致：不 kill，异常直接透出。
        untimed = mocker.Mock()
        untimed.wait.side_effect = KeyboardInterrupt
        mocker.patch("common.cmd_run.subprocess.Popen", return_value=untimed)
        with pytest.raises(KeyboardInterrupt):
            real_time_output("cmd", output=False)
        kill.assert_called_once_with(process)
        wait.assert_called_once_with(process)

    @pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
    def test_run_timed_keyboardinterrupt_leaves_no_orphan(self, tmp_path, mocker):
        # 检视意见（diff 198750377）无孤儿回归：真实 sleep 孙进程被中断后必须消失。
        pid_file = tmp_path / "timed_orphan.pid"
        command = "sleep 30 & echo $! > {0}; wait".format(shlex.quote(str(pid_file)))

        def interrupting_communicate(self, input=None, timeout=None):
            # 先让 bash 建好孙进程并写盘，再模拟 Ctrl-C。
            time.sleep(0.3)
            raise KeyboardInterrupt

        mocker.patch.object(subprocess.Popen, "communicate", interrupting_communicate)
        with pytest.raises(KeyboardInterrupt):
            cmd_run._run_timed(
                [cmd_run.BASH, "-c", command],
                timeout=10,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        _assert_pid_reaped(pid_file)

    @pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
    def test_real_time_output_keyboardinterrupt_leaves_no_orphan(
        self, tmp_path, mocker
    ):
        # 同上，real_time_output 自建会话分支的无孤儿回归。首次 wait 抛
        # KeyboardInterrupt，_wait_after_kill 的第二次 wait 仍走真实实现。
        pid_file = tmp_path / "real_time_orphan.pid"
        command = "sleep 30 & echo $! > {0}; wait".format(shlex.quote(str(pid_file)))
        real_wait = subprocess.Popen.wait
        calls = []

        def interrupting_wait(self, timeout=None):
            calls.append(timeout)
            if len(calls) == 1:
                time.sleep(0.3)
                raise KeyboardInterrupt
            return real_wait(self, timeout=timeout)

        mocker.patch.object(subprocess.Popen, "wait", interrupting_wait)
        with pytest.raises(KeyboardInterrupt):
            real_time_output(command, output=False, timeout=10)
        # 第二次 wait 来自 _wait_after_kill 的有界回收，而不是再来一次无界等待。
        self.assertTrue(len(calls) >= 2)
        self.assertTrue(calls[1] is not None)
        _assert_pid_reaped(pid_file)


def _assert_pid_reaped(pid_file):
    """Poll os.kill(pid, 0) until ProcessLookupError (2s cap); a pid that is
    still observable there means the interrupted session left an orphan."""
    deadline = time.monotonic() + 2
    pid = None
    while time.monotonic() < deadline:
        if pid is None and pid_file.exists():
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        if pid is not None:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
        time.sleep(0.02)
    assert pid is not None, "grandchild pid marker was not created"
    raise AssertionError("orphaned grandchild survived: pid {0}".format(pid))
