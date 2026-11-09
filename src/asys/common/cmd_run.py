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

import os
import shutil
import signal
import subprocess
import sys
import threading
import time

from common.log import log_debug, log_warning

__all__ = [
    "run_command",
    "run_cmd_output",
    "run_cmd_list",
    "check_command",
    "run_linux_cmd",
    "popen_run_cmd",
    "real_time_output",
]

# Prefer bash where available, but keep the command channel usable on POSIX-only
# systems where only sh is installed.
BASH = shutil.which("bash") or shutil.which("sh") or "/bin/sh"
_CLEANUP_GRACE = 1.0


def check_command(command):
    return shutil.which(command) is not None


def _popen_kwargs(timeout):
    # A timed command runs in its own session so that the whole process
    # group (bash pipeline + grandchildren) can be killed on expiry (#399).
    return {"start_new_session": True} if timeout is not None else {}


def _kill_process_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        # group leader already dead, or platform without process groups:
        # subprocess' own kill of the direct child already happened
        pass


def _wait_after_kill(process):
    try:
        process.wait(timeout=_CLEANUP_GRACE)
    except subprocess.TimeoutExpired:
        # An uninterruptible child must not turn the requested timeout into an
        # unbounded wait. The caller still receives the timeout contract.
        pass


def _close_process_pipes(process):
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def _run_timed(args, timeout=None, **kwargs):
    """subprocess.run equivalent that kills the whole process group on
    timeout. Raises subprocess.TimeoutExpired (like subprocess.run)."""
    if timeout is None:
        # Review finding C: replacement decoding is a timeout-only relaxation.
        # Without a timeout the base contract is a bare ``encoding`` argument,
        # so invalid UTF-8 still raises UnicodeDecodeError (a ValueError) and
        # callers keep their historical failure returns.
        kwargs.pop("errors", None)
        kwargs.setdefault("shell", False)
        kwargs.setdefault("check", False)
        return subprocess.run(args, **kwargs)
    kwargs.pop("check", False)  # run() semantics only; Popen never raises for rc
    kwargs.setdefault("start_new_session", True)
    kwargs.setdefault("shell", False)
    process = subprocess.Popen(args, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        _kill_process_group(process)
        _close_process_pipes(process)
        _wait_after_kill(process)
        raise subprocess.TimeoutExpired(
            process.args, timeout, output=error.output, stderr=error.stderr
        )
    except BaseException:
        # Review finding (diff comment 198750377): base subprocess.run kills the
        # child and re-raises for KeyboardInterrupt or any other BaseException
        # raised while waiting for the child. start_new_session=True moved the
        # child out of the terminal's foreground process group, so no terminal
        # signal can reach it any more: without this branch the whole session
        # would be orphaned. Kill the group and reap with the bounded wait, never
        # with a second unbounded communicate, then re-raise unchanged.
        _kill_process_group(process)
        _close_process_pipes(process)
        _wait_after_kill(process)
        raise
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def _log_timeout(command, timeout):
    log_warning(
        "Run command: {0} timed out after {1}s, process group killed".format(
            command, timeout
        )
    )


def run_linux_cmd(cmd, cmp_str="", timeout=None) -> bool:
    if not isinstance(cmd, str):
        return False
    try:
        ret = _run_timed(
            [BASH, "-c", cmd],
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _log_timeout(cmd, timeout)
        return False
    if cmp_str:
        return ret.stdout.strip().decode() == cmp_str
    if ret.returncode == 0:
        return True
    return False


def run_command(command, timeout=None) -> str:
    try:
        ret = _run_timed(
            [BASH, "-c", command],
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            env=os.environ,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _log_timeout(command, timeout)
        return "NONE"
    except (OSError, ValueError) as error:
        log_debug("Run command: {0} failed, {1}".format(command, error))
        return "NONE"
    if ret.returncode == 0:
        output = ret.stdout.strip()
        if output:
            # The exit status alone decides success: warnings on stderr
            # must not discard valid stdout (#205).
            return output
        # rc==0 with no stdout: keep the "NONE" sentinel only when stderr
        # is non-empty (an upstream failure in a ``cat | grep | awk``
        # pipeline, where the tail decides the exit status); a completely
        # quiet command keeps the historical empty-string contract.
        # Whitespace-only stderr counts as quiet (stripped criterion).
        return "NONE" if ret.stderr.strip() else ""
    else:
        ret_err = ret.stderr
        log_debug(
            "Run command: {0} failed, ret_code={1}, ret_err={2}".format(
                command, ret.returncode, ret_err
            )
        )
        if "not found" in ret_err:
            return "NONE"
        return ret.stderr.strip().replace("\n", "  ")


def run_cmd_output(command, timeout=None) -> [bool, str]:
    try:
        ret = _run_timed(
            [BASH, "-c", command],
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            env=os.environ,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _log_timeout(command, timeout)
        return False, ""
    except (OSError, ValueError) as error:
        log_debug("Run command: {0} failed, {1}".format(command, error))
        return False, ""
    if ret.returncode == 0:
        return True, ret.stdout
    else:
        ret_err = ret.stderr
        log_debug(
            "Run command: {0} failed, ret_code={1}, ret_err={2}".format(
                command, ret.returncode, ret_err
            )
        )
        return False, ret.stderr


def _read_stdout(process):
    # Review finding B: only the closed-pipe ValueError (I/O operation on
    # closed file), which is how the timeout cleanup used to wake this reader,
    # is a cleanup signal. A decoding error is a genuine contract violation and
    # must reach the caller; write errors are never swallowed at all.
    try:
        yield from process.stdout
    except UnicodeDecodeError:
        raise
    except ValueError:
        return


def _drain_output(process, output):
    for line in _read_stdout(process):
        if output:
            sys.stdout.write(line)
            sys.stdout.flush()


def _stop_real_time(process, reader, command, timeout):
    # Review finding A: do not close process.stdout here. The daemon reader may
    # be blocked inside ``for line in process.stdout``, and CPython's
    # BufferedReader keeps its lock for the whole read, so close() would
    # deadlock and the timeout would stop being a wall-clock bound. Killing the
    # process group leaves a reader blocked on a pipe still held by an
    # unreachable grandchild; as a daemon thread it cannot block the caller or
    # interpreter exit.
    _kill_process_group(process)
    _wait_after_kill(process)
    if reader is not None:
        reader.join(timeout=_CLEANUP_GRACE)
    _log_timeout(command, timeout)
    return False


def _raise_reader_error(reader_errors):
    # Review finding B: a writer error raised in the reader thread must not be
    # silently lost; the caller sees it after the process group was cleaned up.
    if reader_errors:
        raise reader_errors[0]


def real_time_output(command, output=True, timeout=None) -> bool:
    popen_kwargs = _popen_kwargs(timeout)
    if timeout is not None:
        # Review finding C: replacement decoding is a timeout-only relaxation,
        # so timeout=None keeps the base behaviour of raising on invalid UTF-8.
        popen_kwargs["errors"] = "replace"
    process = subprocess.Popen(
        [BASH, "-c", command],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
        env=os.environ,
        **popen_kwargs,
    )
    deadline = None if timeout is None else time.monotonic() + timeout
    reader = None
    reader_errors = []
    if timeout is not None:

        def forward_output():
            try:
                _drain_output(process, output)
            except Exception as error:  # noqa: BLE001 - re-raised by the caller
                reader_errors.append(error)

        reader = threading.Thread(target=forward_output, daemon=True)
        reader.start()
    elif output:
        # Review finding B: the synchronous path lets write errors propagate,
        # exactly like the base implementation.
        _drain_output(process, output)
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop_real_time(process, reader, command, timeout)
        _raise_reader_error(reader_errors)
        return False
    except BaseException:
        # Review finding (diff comment 198750377): only the timed path started
        # the child in its own session, so only that path has to clean up after
        # an interruption (Ctrl-C during the wait). timeout=None keeps the base
        # behaviour of letting the exception escape untouched.
        if timeout is not None:
            _kill_process_group(process)
            _wait_after_kill(process)
        raise
    if reader is not None:
        reader.join(timeout=max(0, deadline - time.monotonic()))
        if reader.is_alive():
            _stop_real_time(process, reader, command, timeout)
            _raise_reader_error(reader_errors)
            return False
        _raise_reader_error(reader_errors)
    return process.returncode == 0


def run_cmd_list(cmd_list, cwd=None, timeout=None) -> tuple:
    """Run a command from an argument list, without any shell interpolation.

    The string-command helpers above pass their cmd through ``bash -c``, so
    injection safety depends on every caller quoting its own fragments. A
    caller holding attacker-influenced fragments (a file name from disk, a
    pid) should come here instead: the list form keeps each argument intact
    no matter which characters it contains.

    The optional timeout matches the contract of the other runners: on
    expiry the whole process group is killed and (False, "") is returned,
    so a hung lsof scanning a stuck mount cannot wedge the caller.
    """
    try:
        ret = _run_timed(
            cmd_list,
            timeout=timeout,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            env=os.environ,
        )
    except subprocess.TimeoutExpired:
        _log_timeout(cmd_list, timeout)
        return False, ""
    except (OSError, ValueError) as error:
        log_debug("Run command: {0} failed, {1}".format(cmd_list, error))
        return False, ""
    if ret.returncode == 0:
        return True, ret.stdout
    log_debug(
        "Run command: {0} failed, ret_code={1}, ret_err={2}".format(
            cmd_list, ret.returncode, ret.stderr
        )
    )
    return False, ret.stderr


def popen_run_cmd(command, timeout=None):
    """
    run the command and return stdout (stderr suppressed).
    """
    try:
        ret = _run_timed(
            [BASH, "-c", command],
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except subprocess.TimeoutExpired:
        _log_timeout(command, timeout)
        return ""
    return ret.stdout
