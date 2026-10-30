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
import subprocess
import sys

from common.log import log_debug

__all__ = [
    "run_command",
    "run_cmd_output",
    "check_command",
    "run_linux_cmd",
    "popen_run_cmd",
    "real_time_output",
]

# Prefer bash where available, but keep the command channel usable on POSIX-only
# systems where only sh is installed.
BASH = shutil.which("bash") or shutil.which("sh") or "/bin/sh"


def check_command(command):
    return shutil.which(command) is not None


def run_linux_cmd(cmd, cmp_str="") -> bool:
    if not isinstance(cmd, str):
        return False
    ret = subprocess.run(
        [BASH, "-c", cmd],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if cmp_str:
        return ret.stdout.strip().decode() == cmp_str
    if ret.returncode == 0:
        return True
    return False


def run_command(command) -> str:
    try:
        ret = subprocess.run(
            [BASH, "-c", command],
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            env=os.environ,
            check=False,
        )
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


def run_cmd_output(command) -> [bool, str]:
    try:
        ret = subprocess.run(
            [BASH, "-c", command],
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            env=os.environ,
            check=False,
        )
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


def real_time_output(command, output=True) -> bool:
    process = subprocess.Popen(
        [BASH, "-c", command],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
        env=os.environ,
    )
    if output:
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
    process.wait()
    return process.returncode == 0


def popen_run_cmd(command):
    """
    run the command and return stdout (stderr suppressed).
    """
    ret = subprocess.run(
        [BASH, "-c", command],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )
    return ret.stdout
