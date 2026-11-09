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

import multiprocessing
import os
import queue
import time
from datetime import datetime, timezone
from functools import wraps
import sys

from params import ParamDict
from common.const import RetCode, CANN_LOG_NAME, consts, STACKTRACE
from common.log import log_error, log_info
from common.file_operate import FileOperate as f
from drv import EnvVarName

__all__ = [
    "create_out_timestamp_dir",
    "get_asys_output_path",
    "get_target_cnt",
    "out_progress_bar",
    "is_hexadecimal",
    "str_to_hex",
    "int_to_hex",
    "get_cann_log_path",
    "timeout_decorator",
]


_asys_output_path = [None]


def get_asys_output_path():
    return _asys_output_path[0]


def create_out_timestamp_dir():
    def init_output_dir_parent():
        output_arg = ParamDict().get_arg("output")
        return EnvVarName().current_path if not output_arg else output_arg

    if ParamDict().get_command() not in [
        consts.collect_cmd,
        consts.launch_cmd,
        consts.analyze_cmd,
    ]:
        return RetCode.SUCCESS

    output_dir = init_output_dir_parent()
    if not os.access(output_dir, os.W_OK):
        if not os.path.isdir(output_dir):
            log_error(
                "asys output root directory does not exist: {}.".format(output_dir)
            )
            return RetCode.ARG_NO_EXIST_DIR
        log_error(
            "No write permission to asys output root directory: {}.".format(output_dir)
        )
        return RetCode.PERMISSION_FAILED

    utc_dt = datetime.now(timezone.utc)  # UTC time
    dir_name = "asys_output_" + utc_dt.astimezone().strftime("%Y%m%d%H%M%S%f")[:-3]

    output_path = os.path.abspath(os.path.join(output_dir, dir_name))
    _asys_output_path[0] = output_path
    if not f.create_dir(output_path):
        return RetCode.ARG_CREATE_DIR_FAILED
    ParamDict().asys_output_timestamp_dir = output_path
    if not (
        ParamDict().get_command() == consts.collect_cmd
        and ParamDict().get_arg("run_mode") == STACKTRACE
    ):
        log_info("asys output directory: {0}".format(output_path))
    return RetCode.SUCCESS


def is_hexadecimal(value):
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def str_to_hex(str_number):
    return int(str_number, 16)


def int_to_hex(value):
    return hex(int(value, 16))


def get_target_cnt(dir_path, suffix=".bin", prefix=None):
    """
    Counts the number of bin files in the trace folder.
    """
    count = 0
    atrace_dirs = f.walk_dir(dir_path)
    if not atrace_dirs:
        return count
    for *_, files in atrace_dirs:
        for name in files:
            # Count only what the caller will actually parse: trace files are
            # .bin, stackcore files are .txt, and coretrace artefacts keep the
            # bare coretrace* name. Counting every artefact made the
            # denominator too large; counting .bin unconditionally hid the bar
            # entirely for the other two run modes.
            if prefix is not None:
                matched = name.startswith(prefix)
            else:
                matched = name.endswith(suffix)
            if matched:
                count += 1
    return count


def out_progress_bar(count, num):
    """
    Show progress bar
    """
    if count == 0:
        return
    sys.stdout.write("\r")
    sys.stdout.write("Parse progress: {:.2f}%: ".format(num / count * 100))
    sys.stdout.write("\r")
    sys.stdout.flush()


def get_cann_log_path(log_type):
    """
    get trace or cann log path from env
    """
    env_var = EnvVarName()
    if log_type == CANN_LOG_NAME:
        if env_var.process_log_path:
            return env_var.process_log_path, "${ASCEND_PROCESS_LOG_PATH}"

    if env_var.work_path:
        return os.path.join(
            env_var.work_path, log_type
        ), f"${{ASCEND_WORK_PATH}}/{log_type}"
    return os.path.join(
        env_var.home_path, "ascend", log_type
    ), f"${{HOME}}/ascend/{log_type}"


def timeout_decorator(timeout, raise_on_error=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use fork context explicitly: forkserver (Python 3.14+ default on Linux)
            # requires pickling bound methods, which fails when the method is decorated.
            ctx = multiprocessing.get_context("fork")
            # The callable runs in a child process, so only results reported
            # through this queue reach the caller; the return value of func
            # itself is otherwise silently dropped.
            result_queue = ctx.Queue()

            def target(*target_args, **target_kwargs):
                target_kwargs.pop("result_queue", None)
                result_queue.put(func(*target_args, **target_kwargs))

            p = ctx.Process(
                target=target, args=args, kwargs={**kwargs, "result_queue": None}
            )
            p.daemon = True
            p.start()
            # Drain the queue BEFORE joining: a result larger than the pipe
            # buffer (64 KiB) blocks the child's feeder thread on put(), so
            # the child only exits after the parent has consumed it. Joining
            # first reported a false TimeoutError for such payloads.
            # Poll in small steps so a child that dies instantly is detected
            # on the next tick instead of waiting out the whole timeout.
            deadline = time.monotonic() + timeout
            ret = None
            got_result = False
            while time.monotonic() < deadline:
                try:
                    ret = result_queue.get(timeout=0.2)
                    got_result = True
                    break
                except queue.Empty:
                    if not p.is_alive():
                        # The callable died without reporting (its exception
                        # cannot cross the process border). One non-blocking
                        # drain first: the child's exit only becomes visible
                        # here after its feeder thread finished (or was
                        # killed), so any completed write is already in the
                        # pipe — a poll result racing the exit tick is picked
                        # up instead of being reported as None. A write that
                        # never completed is lost either way, so a bounded
                        # wait would only add latency on the crash path.
                        try:
                            ret = result_queue.get_nowait()
                            got_result = True
                        except queue.Empty:
                            pass
                        break
            if not got_result and p.is_alive():
                # Still running at the deadline: a real timeout.
                p.terminate()
                p.join(timeout)
                if p.is_alive():
                    # SIGTERM can be ignored or blocked by the child; kill it
                    # so the decorator cannot hang forever on a stubborn worker.
                    p.kill()
                    p.join()
                result_queue.close()
                raise TimeoutError()
            # The result is in hand, but a non-daemon thread could still keep
            # the child alive; the wall-clock budget caps this join.
            p.join(max(0.0, deadline - time.monotonic()))
            if p.is_alive():
                p.terminate()
                p.join()
            result_queue.close()
            # The callable runs in a child process, so its exception never
            # reaches this frame. Without this check a failure looks exactly
            # like a silent success and the caller keeps going with None.
            if p.exitcode and raise_on_error:
                raise ChildProcessError(
                    f"{getattr(func, '__name__', 'callable')} failed in the "
                    f"timeout worker, exitcode={p.exitcode}"
                )
            return ret

        return wrapper

    return decorator
