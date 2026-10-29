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
            p = ctx.Process(target=func, args=args, kwargs=kwargs)
            p.daemon = True
            p.start()
            p.join(timeout)
            if p.is_alive():
                p.terminate()
                p.join()
                raise TimeoutError()
            # The callable runs in a child process, so its exception never
            # reaches this frame. Without this check a failure looks exactly
            # like a silent success and the caller keeps going with None.
            if p.exitcode and raise_on_error:
                raise ChildProcessError(
                    f"{getattr(func, '__name__', 'callable')} failed in the "
                    f"timeout worker, exitcode={p.exitcode}"
                )

        return wrapper

    return decorator
