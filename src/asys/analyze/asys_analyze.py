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
import shlex
import stat
import time
import sys

from analyze.coredump_analyze import CoreDump
from common import log_error, log_warning, log_info, log_debug
from common import FileOperate as f
from common.cmd_run import check_command, real_time_output
from common.task_common import get_target_cnt
from common.const import MSAICERR_ANALYZE_TIMEOUT
from collect.coretrace import ParseCoreTrace
from collect.trace import ParseTrace
from collect.stackcore import ParseStackCore
from collect import AsysCollect
from collect.msnpureport_type_collect.ub_parse import convert_ub_files
from params import ParamDict


class AsysAnalyze:
    def __init__(self):
        self.file = self.get_param_arg("file")
        self.path = self.get_param_arg("path")
        self.exe_file = self.get_param_arg("exe_file")
        self.core_file = self.get_param_arg("core_file")
        self.symbol = self.get_param_arg("symbol")
        self.symbol_path = self.get_param_arg("symbol_path")
        self.output = ParamDict().asys_output_timestamp_dir
        self.run_mode = self.get_param_arg("run_mode")
        self.device_id = ParamDict().get_arg("device_id", 0)

    def clean_output(self):
        f.remove_dir(self.output)

    @staticmethod
    def get_param_arg(mode):
        if mode == "symbol":
            return ParamDict().get_arg(mode)
        return ParamDict().get_arg(mode) if ParamDict().get_arg(mode) else None

    def write_res_file(self, file_name, file_content):
        try:
            flags = os.O_WRONLY | os.O_CREAT
            modes = stat.S_IWUSR | stat.S_IRUSR
            with os.fdopen(
                os.open(f"{self.output}/{file_name}", flags, modes), "w"
            ) as fw:
                fw.write(file_content)
        except (OSError, TypeError) as e:
            log_error(e)

    def run(self):
        if f.check_exists(self.path) and f.check_exists(self.output):
            real_path = os.path.realpath(self.path)
            real_output = os.path.realpath(self.output)
            # commonpath, not a ``startswith`` on ``real_path + os.path.sep``:
            # for ``--path /`` that concatenation is ``//``, which no absolute
            # output starts with, so the guard would let everything through.
            try:
                output_in_path = (
                    os.path.commonpath([real_path, real_output]) == real_path
                )
            except ValueError:
                # Different Windows drives cannot nest.
                output_in_path = False
            if output_in_path:
                # The output directory may have been created below the input
                # directory for this run. It is safe to remove that new
                # directory, but never remove the input directory itself.
                if real_output != real_path:
                    self.clean_output()
                log_error(
                    'The output directory cannot be the same as the "path" directory or its subdirectories.'
                )
                return False
        mode_function = {
            "trace": self.__atrace_analyze,
            "stackcore": self.__atrace_analyze,
            "coretrace": self.__atrace_analyze,
            "coredump": self.__core_dump_analyze,
            "aicore_error": self.__aicore_error_analyze,
            "ub": self.__ub_analyze,
        }
        func = mode_function.get(self.run_mode)
        return func()

    def __copy_dir(self):
        if self.run_mode == "trace":
            return f.copy_dir(self.path, self.output)
        # stackcore, coretrace
        for root, _, files in os.walk(self.path):
            for file in files:
                if self.run_mode in {"stackcore", "coretrace"} and not file.startswith(
                    self.run_mode
                ):
                    continue
                root_path = os.path.relpath(root, self.path)
                if not f.copy_file_to_dir(
                    os.path.join(root, file), os.path.join(self.output, root_path)
                ):
                    return False
        return True

    def __atrace_analyze(self):
        """
        parse the trace file. If the file exists, parse the file. If the directory exists, parse the directory.
        """
        if self.run_mode == "trace":
            parse_struct = ParseTrace(True)
        elif self.run_mode == "stackcore":
            parse_struct = ParseStackCore(self.symbol_path, self.file)
            if not self.symbol_path:
                log_warning(
                    "'--symbol_path' is not set, the default path will be used to analyze."
                )
        elif self.run_mode == "coretrace":
            parse_struct = ParseCoreTrace(self.symbol_path, self.file)
            if not self.symbol_path:
                log_warning(
                    "'--symbol_path' is not set, the default path will be used to analyze."
                )
        else:
            return False

        if self.file:
            f.copy_file_to_dir(self.file, self.output)
            log_info(f"Copy source file {self.file} into {self.output}")
            return parse_struct.start_parse_file(
                os.path.join(self.output, os.path.basename(self.file))
            )
        elif self.path:
            self.path = os.path.abspath(self.path)
            self.output = os.path.join(self.output, self.path.split(os.sep)[-1])
            copy_res = self.__copy_dir()
            if not copy_res:
                return False
            # Each run mode names its artefacts differently: trace uses .bin,
            # stackcore uses .txt, and coretrace keeps the bare coretrace* name,
            # so the denominator has to follow the naming or it is 0 and the
            # progress bar disappears.
            if self.run_mode == "trace":
                count = get_target_cnt(self.output, ".bin")
            elif self.run_mode == "coretrace":
                count = get_target_cnt(self.output, prefix="coretrace")
            else:
                count = get_target_cnt(self.output, ".txt")
            return parse_struct.run(self.output, count=count)
        else:
            log_error("Analyze requires either the --file or --path argument")
            return False

    def __core_dump_analyze(self):
        stack_txt = "[process]\n"
        if not check_command("gdb"):
            log_error("Gdb does not exist, install gdb before using it.")
            return False
        if not self.exe_file:
            log_error("The --exe_file parameter must exist for analyze coredump.")
            return False
        if not self.core_file:
            log_error("The --core_file parameter must exist for analyze coredump.")
            return False
        core_dump = CoreDump(self.exe_file, self.core_file, self.symbol, self.output)
        stack_txt, pid = core_dump.start_gdb(stack_txt)
        if pid == 0:
            return False
        file_name = f"stackcore_{os.path.basename(self.exe_file)}_{pid}_{int(round(time.time() * 1000))}.txt"
        self.write_res_file(file_name, stack_txt)
        return True

    def __aicore_error_analyze(self):
        output_path = os.path.dirname(self.output)
        msaicerr_path = (
            ParamDict().tools_path.parents[1].joinpath("msaicerr", "msaicerr.py")
        )
        log_debug(f"Start load msaicerr tools path: {msaicerr_path}")
        if not os.path.exists(msaicerr_path):
            log_error(
                "The path of the msaicerr tool cannot be found, please install the whole package."
            )
            return False
        if self.path:
            log_debug(f"msaicerr analyze path {self.path}")
            cmd = (
                f"{sys.executable} {msaicerr_path} -p {shlex.quote(self.path)} "
                f"-dev {self.device_id} -out {shlex.quote(output_path)}"
            )
        else:
            asys_collector = AsysCollect()
            task_res = AsysCollect().run()
            log_debug(
                f"Asys collect path {asys_collector.output_root_path} res {task_res}"
            )
            if not task_res:
                log_error("Asys collect log failed")
                return False
            cmd = (
                f"{sys.executable} {msaicerr_path} -p {shlex.quote(str(asys_collector.output_root_path))} "
                f"-dev {self.device_id} -out {shlex.quote(output_path)}"
            )
        log_debug(f"Start run: {cmd}")
        # msaicerr -p 是重操作：超时预算 3 分钟，挂死时 kill 进程组并按
        # 失败返回，不让 analyze 主流程永久阻塞（#399 超时规格）。
        res = real_time_output(cmd, timeout=MSAICERR_ANALYZE_TIMEOUT)
        self.clean_output()
        return res

    def __ub_analyze(self):
        if self.path:
            self.path = os.path.abspath(self.path)
        else:
            log_error("Please enter the path to the UB data collection file.")
            return False
        convert_ub_files(self.path, self.output)
        return True
