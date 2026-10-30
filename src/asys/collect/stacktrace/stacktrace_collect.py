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
import re
import time

from common import log_error, popen_run_cmd, log_warning, log_info
from common import FileOperate as f
from common.file_operate import COPY_MODE
from common.const import (
    ATRACE_LOG_NAME,
    RetCode,
    CHECK_BIN_MAX_TIMEOUT,
    CHECK_BIN_DEFAULT_TIMEOUT,
)
from params import ParamDict
from collect.stacktrace import AscendTraceDll
from drv import EnvVarName

EVERY_ROUND_TIME = 0.5


class AsysStackTrace(AscendTraceDll):
    """
    Send signal to export stackcore
    """

    def __init__(self):
        super(AsysStackTrace, self).__init__()
        self.run_mode = ParamDict().get_arg("run_mode")
        self.remote_id = ParamDict().get_arg("remote")
        self.is_all_task = ParamDict().get_arg("all")
        self.quiet = ParamDict().get_arg("quiet")
        self.timeout = ParamDict().get_arg("timeout")
        self.output = ParamDict().asys_output_timestamp_dir
        self.trace_work_path = ""

    def _get_target_work_path(self):
        target_env_file = os.path.join("/proc", str(self.remote_id), "environ")
        try:
            with open(
                target_env_file, "r", encoding="utf-8", errors="ignore"
            ) as target_env:
                env_content = target_env.read()
            env_list = env_content.split("\0")
            env_name = "ASCEND_WORK_PATH"
            for env in env_list:
                if not env:
                    continue

                env_info = env.split("=", 1)
                if len(env_info) >= 2 and env_info[0] == env_name:
                    return env_info[1]
            return None
        except PermissionError:
            log_warning(
                f"permission denied: cannot read env of process {self.remote_id}."
            )
            return None
        except FileNotFoundError:
            log_warning(f"process {self.remote_id} does not exist: {target_env_file}.")
            return None
        except OSError as e:
            log_warning(f"failed to get env for process {self.remote_id}：{str(e)}.")
            return None
        except UnicodeDecodeError as e:
            log_warning(f"failed to decode env for process {self.remote_id}: {str(e)}.")
            return None

    def _set_trace_work_path(self):
        asys_env_var = EnvVarName()
        target_work_path = self._get_target_work_path()
        if target_work_path:
            self.trace_work_path = os.path.join(target_work_path, ATRACE_LOG_NAME)
            log_info(
                f"bin file generate path is {os.path.abspath(self.trace_work_path)}, "
                f"get from environment variables of process {self.remote_id}."
            )
        else:
            self.trace_work_path = os.path.join(
                asys_env_var.home_path, "ascend", ATRACE_LOG_NAME
            )
            log_info(
                f"bin file generate path is {os.path.abspath(self.trace_work_path)}, "
                f"get from default path."
            )
        return

    def _get_bin_file_path(self, all_exists_bin):
        for path, _, files in os.walk(os.path.abspath(self.trace_work_path)):
            for file in files:
                if not (
                    file.startswith(f"stackcore_tracer_35_{self.remote_id}_")
                    and file.endswith(".bin")
                ):
                    continue
                bin_file_path = os.path.join(path, file)
                if bin_file_path in all_exists_bin:
                    continue
                return bin_file_path

    def _get_exists_bin_file_num(self):
        cmd = (
            f"ls -lt {os.path.abspath(self.trace_work_path)}/trace_*/stackcore_event_{self.remote_id}_*/"
            f"stackcore_tracer_35_{self.remote_id}_*.bin | wc -l"
        )
        ret = popen_run_cmd(cmd).replace("\n", "")
        if not ret.isdigit():
            return 0
        return int(ret)

    def _get_last_bin_file_name(self):
        cmd = (
            f"ls -lt {os.path.abspath(self.trace_work_path)}/trace_*/stackcore_event_{self.remote_id}_*/"
            f"stackcore_tracer_35_{self.remote_id}_*.bin | head -n 1 | awk '{{print $9}}'"
        )
        return popen_run_cmd(cmd).replace("\n", "")

    def _wait_bin_file_generate(self, exists_bin_file_num):
        bin_file_name = None
        for _ in range(int(self.timeout // EVERY_ROUND_TIME)):  # 20 * 0.5 = 10s
            if not bin_file_name:
                current_bin_file_num = self._get_exists_bin_file_num()
                if current_bin_file_num == exists_bin_file_num:
                    time.sleep(EVERY_ROUND_TIME)
                    continue
                if current_bin_file_num > exists_bin_file_num:
                    bin_file_name = self._get_last_bin_file_name()
                    log_info("bin file generated, awaiting stack trace completion.")
                    continue

            if popen_run_cmd(f"lsof {bin_file_name}"):
                time.sleep(EVERY_ROUND_TIME)
                continue
            return bin_file_name
        log_error(
            f"get the stackcore bin file in path {os.path.abspath(self.trace_work_path)} timeout."
        )
        return None

    def _check_other_param(self):
        task_dir = ParamDict().get_arg("task_dir")
        tar = ParamDict().get_arg("tar")
        if task_dir or tar:
            log_error(
                "'--task_dir', and '--tar' can be used only when '-r' is not used."
            )
            return False
        if isinstance(self.timeout, int) and not isinstance(self.timeout, bool):
            if self.timeout <= 0 or self.timeout > CHECK_BIN_MAX_TIMEOUT:
                log_error("The value of timeout must in the range [1,60]")
                return False
        else:
            self.timeout = CHECK_BIN_DEFAULT_TIMEOUT
        return True

    def _check_remote_id_validity(self):
        if self.remote_id < 2:
            log_error(
                f'The value of "--remote" must be greater than 1, input: {self.remote_id}.'
            )
            return False

        try:
            os.kill(self.remote_id, 0)
        except (OSError, OverflowError):
            log_error(f"No such process, id: {self.remote_id}.")
            return False

        # check remote pid ?
        cmd = f"ps -p {self.remote_id}"
        # Split the command output into logical lines without manually
        # trimming a presumed trailing newline.
        ret = popen_run_cmd(cmd).splitlines()
        if len(ret) != 2:
            log_error("The remote parameter must be set to the PID of the process.")
            return False
        return True

    def _get_all_tid_of_process(self, current_pid):
        cmd = (
            rf"ps -efT | grep ' {self.remote_id} ' | grep -v {current_pid} | awk '{{print $2}}' | xargs ps -Lf \
                 | awk '{{print $4}}'"
        )
        ret = popen_run_cmd(cmd).split("\n")
        ret = [i for i in ret if i.isdigit()]
        if not ret:
            log_error(f"Get pid failed by remote: {self.remote_id}.")
            return []
        return ret

    @staticmethod
    def _get_other_stacktrace_remote_id(current_pid):
        all_remote_id = []
        cmd = rf"ps -ef | grep -E asys[\.py]{{0\,3}}\ collect | grep stacktrace | grep -v ' {current_pid} '"
        ret = popen_run_cmd(cmd).split("\n")
        ret = [i for i in ret if i]
        if not ret:
            return all_remote_id

        p_pid = os.getppid()
        for process in ret:
            process_info_list = [i for i in process.split(" ") if i]
            _pid = process_info_list[1]
            # exclude current process ppid is other process pid
            if _pid.isdigit() and int(_pid) == p_pid:
                continue
            _remote_id = re.search(r" --remote[ =](\d+)", process)
            if _remote_id:
                all_remote_id.append(_remote_id.group(1))
        return all_remote_id

    def _check_collect_stacktrace_parallel(self):
        current_pid = os.getpid()
        all_remote_id = self._get_other_stacktrace_remote_id(current_pid)
        if not all_remote_id:
            return True
        # other running remote_id contains the current remote_id.
        if str(self.remote_id) in all_remote_id:
            return False

        all_tid_of_process = self._get_all_tid_of_process(current_pid)
        # abnormal state
        if not all_tid_of_process:
            return False

        all_tid_remote_id = all_remote_id + all_tid_of_process
        # tid contained in the current remote_id is running
        if len(all_tid_remote_id) > len(set(all_tid_remote_id)):
            return False
        return True

    @staticmethod
    def _clear_dfx_log(folder_path):
        for file in os.listdir(folder_path):
            if file.endswith(".log") and file.startswith("stackcore_tracer_35_"):
                log_path = os.path.join(folder_path, file)
                try:
                    os.remove(log_path)
                except OSError:
                    continue

    def run(self):
        """
        send signals to export stackcore files.
        """
        f.remove_dir(self.output)
        param_ret = self._check_other_param()
        if not param_ret:
            return False

        if self.remote_id is False or not self.is_all_task:
            log_error(
                '"-r=stacktrace" must be used together with "--remote" and "--all".'
            )
            return False

        if self.trace_dll == RetCode.FAILED:
            return False

        if not self._check_remote_id_validity():
            return False
        log_warning(
            f"This command sends signal 35 to the process:{self.remote_id}. "
            "If the process is executed to disable signal receiving through the environment variable "
            f"ASCEND_COREDUMP_SIGNAL=none, the process:{self.remote_id} will be killed. "
        )
        if not self.quiet:
            log_warning("Are you sure that signal reception is not disabled? (Y/N)")
            if input().upper() != "Y":
                return True

        self._set_trace_work_path()

        if not self._check_collect_stacktrace_parallel():
            log_error("Collect stacktrace not support Parallelism.")
            return False

        exists_bin_num = self._get_exists_bin_file_num()
        signal_ret = self.send_signal_to_pid(self.is_all_task, self.remote_id)
        if not signal_ret:
            return False

        bin_file_path = self._wait_bin_file_generate(exists_bin_num)
        if not bin_file_path:
            return False

        parse_ret = self.parse_stackcore_bin_to_txt(bin_file_path)
        if not parse_ret:
            return False

        folder_path = os.path.dirname(bin_file_path)
        self._clear_dfx_log(folder_path)
        ret = f.collect_dir(folder_path, self.output, COPY_MODE)
        if not ret:
            log_warning(f"Copy output file from {folder_path} to {self.output} failed.")

        log_info(f"Stacktrace output directory: {self.output}")
        return True
