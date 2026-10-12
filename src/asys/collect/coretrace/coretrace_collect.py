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
import subprocess
from threading import Thread, Lock

from common import FileOperate as f
from common import log_error, log_warning
from common.cmd_run import check_command
from common.task_common import out_progress_bar


class ParseData:
    def __init__(self):
        self.maps = {}
        self.sig = 0
        self.pid = -1
        self.tgid = -1
        self.comm = ""


class ParseCoreTrace:
    missing_binary = set()
    lock = Lock()

    def __init__(self, symbol, file=None):
        self.file = file
        self.symbol_path = symbol
        self.__addr2line = "addr2line"
        self.warned = False

    def check_tool_exists(self):
        if not check_command(self.__addr2line):
            log_error("The addr2line tool does not exist, install it before using it.")
            return False
        return True

    def warn_missing(self, binary_path):
        with self.lock:
            if binary_path not in self.missing_binary:
                log_warning(f"{os.path.realpath(binary_path)} is not exists.")
                self.missing_binary.add(binary_path)

    def get_binary_path(self, bin_name_path):
        bin_name_str = bin_name_path.split("/")[-1]
        if self.symbol_path:
            for path in self.symbol_path:
                binary_path = os.path.join(path, bin_name_str)
                if os.path.exists(binary_path):
                    return binary_path
                self.warn_missing(binary_path)
        elif not os.path.exists(bin_name_path):
            self.warn_missing(bin_name_path)
        return bin_name_path

    @staticmethod
    def run_addr2line(cmd):
        ret = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8"
        )
        return ret.stdout.readlines()

    def parse_addr_src_line(self, fp, data, shift):
        parsed_line = ""
        for bin_name, addrs in data.maps.items():
            if bin_name == "":
                continue
            bin_path = self.get_binary_path(bin_name)
            start_addr, end_addr = addrs
            if start_addr < fp < end_addr:
                delta = hex(fp - start_addr - shift)
                cmd = [self.__addr2line, "-Cifps", "-e", bin_path, "-a", delta]
                try:
                    out = self.run_addr2line(cmd)
                except (OSError, ValueError) as e:
                    if not self.warned:
                        log_warning(f'Run "{" ".join(cmd)}" failed, error detail: {e}')
                        self.warned = True
                    out = []
                if len(out) == 0:
                    parsed_line += "0x%x    %s    %s" % (fp, delta, bin_name) + "\n"
                else:
                    for func in out:
                        parsed_line += (
                            "0x%x    %s    %s" % (fp, func.strip(), bin_name.strip())
                            + "\n"
                        )
                return parsed_line
        return parsed_line

    def parse_line(self, line, parse_data):
        line_parts = line.split()
        this_line = line.strip() + "\n"
        try:
            if line_parts[0] == "Signal":
                parse_data.sig = int(line_parts[1])
                return this_line
            elif line_parts[0] == "PID":
                parse_data.pid = int(line_parts[1])
                parse_data.tgid = int(line_parts[3])
                parse_data.comm = line_parts[5]
                return "\n" + this_line
            elif line_parts[0].startswith("#"):
                shift = 0 if line_parts[0] == "#0" else 4
                fp = int(line_parts[1].strip("\x00"), base=16)
                return self.parse_addr_src_line(fp, parse_data, shift)
            elif line_parts[0] == "[<0>]" or "(deleted)" in line:
                return this_line
            elif "uburma" in line or "davinci_manager" in line:
                return ""
            else:
                start_addr, end_addr = map(
                    lambda x: int(x, base=16), line_parts[0].split("-")
                )
                bin_name = line_parts[1].strip("\x00")
                if bin_name in parse_data.maps:
                    start_addr = min(parse_data.maps[bin_name][0], start_addr)
                    end_addr = max(parse_data.maps[bin_name][1], end_addr)
                parse_data.maps[bin_name] = [start_addr, end_addr]
                return ""
        except (IndexError, ValueError):
            return this_line

    def parse_file(self, file_lines, count):
        if self.file:
            count = len(file_lines)
        parse_data = ParseData()
        parsed_lines = ""
        for index, line in enumerate(file_lines):
            if self.file:
                out_progress_bar(count, index)
            parsed_lines += self.parse_line(line, parse_data)
        return parsed_lines

    def start_parse_file(self, coretrace_file, count=0):
        """Parsing a single file"""
        coretrace_file_name = coretrace_file.split(os.sep)[-1]
        if not coretrace_file_name.startswith("coretrace"):
            log_error(f"The {coretrace_file} file is not in coretrace format.")
            return False
        # Check whether the addr2line tools exist.
        if not self.check_tool_exists():
            return False
        with open(coretrace_file, "r", encoding="utf-8") as fp:
            file_lines = fp.readlines()
        if not file_lines:
            log_error(f"The {coretrace_file_name} file is empty.")
            return False

        try:
            parsed_lines = self.parse_file(file_lines, count)
        except (ValueError, IndexError, TypeError) as e:
            log_error(f"Parse {coretrace_file} failed, error detail: {e}")
            return False

        with open(coretrace_file, "w", encoding="utf-8") as fw:
            fw.writelines(parsed_lines)
        return True

    def save_file_result(self, coretrace_file, count, num, results):
        ret = self.start_parse_file(coretrace_file, count)
        out_progress_bar(count, num)
        if not ret:
            log_error(f'Failed to analyze the "{coretrace_file}" file.')
        results.append(ret)

    def run(self, coretrace_path, count=0):
        coretrace_dirs = f.walk_dir(coretrace_path)
        if not coretrace_dirs or not self.check_tool_exists():
            return False
        num = 0
        threads = []
        results = []
        for dirs, _, files in coretrace_dirs:
            for file in files:
                coretrace_file = os.path.join(dirs, file)
                num += 1
                t = Thread(
                    target=self.save_file_result,
                    args=(coretrace_file, count, num, results),
                    daemon=True,
                )
                t.start()
                threads.append(t)
        # wait for all threads to end.
        for t in threads:
            t.join()
        out_progress_bar(count, count)
        return any(results)
