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
import subprocess
from datetime import datetime, timezone

from common import log_error, log_info, log_debug
from common.cmd_run import BASH
from common.const import MAX_PERIOD, UNKNOWN, LP_MODE_NO, LP_MODE_AIC, LP_MODE_LP
from params import ParamDict
from common import AsysProfilingSupportedChip, ChipHandler

support_profiling_list = set(["aicore", "dvpp", "os", "link", "memory", "power"])


class AsysProfiling:
    def __init__(self):
        self.device_id = int(ParamDict().get_arg("device_id"))
        self.period = ParamDict().get_arg("period", 0)
        self.output_path = ParamDict().get_arg("output")
        self.run_modes = ParamDict().get_arg("run_mode")
        self.aic_metrics = ParamDict().get_arg("aic_metrics", "PipeUtilization")
        self.lp_mode = LP_MODE_NO

    @staticmethod
    def concat_dvpp(cmd):
        concat_cmd = "--dvpp-profiling=on"
        log_debug("Concat dvpp command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    @staticmethod
    def concat_link(cmd):
        concat_cmd = "--sys-interconnection-profiling=on --sys-io-profiling=on"
        log_debug("Concat link command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    @staticmethod
    def concat_memory(cmd):
        concat_cmd = "--sys-hardware-mem=on --llc-profiling=read"
        log_debug("Concat memory command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    @staticmethod
    def concat_os(cmd):
        concat_cmd = "--sys-profiling=on"
        log_debug("Concat os command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    def concat_power(self, cmd):
        out_cmd = cmd
        if self.lp_mode == LP_MODE_AIC:
            concat_cmd = "--ai-core=on"
            out_cmd += " " + concat_cmd
        elif self.lp_mode == LP_MODE_LP:
            concat_cmd = "--sys-lp=on"
            out_cmd += " " + concat_cmd
        return out_cmd

    def concat_aicore(self, cmd):
        concat_cmd = (
            f"--ai-core=on --aic-mode=sample-based --aic-metrics={self.aic_metrics}"
        )
        log_debug("Concat aicore command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    def run(self):
        if not self._check_param():
            return False
        log_info(f"Run mode is {self.run_modes}.")
        cmd = (
            f"msprof --output={shlex.quote(self.output_path)} --sys-period={str(self.period)} "
            f"--sys-devices={self.device_id} "
        )
        for run_mode in self.run_modes:
            func_name = "concat_" + run_mode
            func = getattr(self, func_name, None)
            if func:
                cmd = func(cmd)
        ret = self._run_cmd(cmd)
        return ret

    def _check_param(self):
        if self.period < 1 or self.period > MAX_PERIOD:
            log_error("Period is invalid, it should be in [1,2592000].")
            return False

        profiling_supported = AsysProfilingSupportedChip()
        ret, _chip_info = profiling_supported.get_supported_chip_info(self.device_id)
        if not ret:
            if _chip_info == UNKNOWN:
                log_error(
                    f"device id {self.device_id} is invalid, please enter a valid value."
                )
                return False
            else:
                log_error(f"The profiling command does not support {_chip_info}.")
                return False

        self.run_modes = {
            mode.strip() for mode in self.run_modes.split(",") if mode.strip()
        }
        if not self.run_modes:
            log_error("Run mode is empty, run 'asys profiling -h' to get help.")
            return False
        if not self.run_modes.issubset(support_profiling_list):
            log_error(
                "Run mode type is unsupported, run 'asys profiling -h' to get help."
            )
            return False

        handler = ChipHandler().get_handler(_chip_info)
        if handler is None:
            log_error(f"{_chip_info} is not supported.")
            return False
        if (
            "dvpp" in self.run_modes
            and not getattr(handler, "support_dvpp", lambda: True)()
        ):
            log_error(f"{_chip_info} does not support dvpp profiling.")
            return False
        if handler.need_lp_param():
            self.lp_mode = LP_MODE_LP
        elif "aicore" not in self.run_modes:
            self.lp_mode = LP_MODE_AIC

        utc_dt = datetime.now(timezone.utc)  # UTC time
        dir_name = utc_dt.astimezone().strftime("%Y%m%d%H%M%S%f")[:-3]
        if not self.output_path:
            self.output_path = f"asys_profiling_result_{dir_name}"
        else:
            self.output_path = os.path.join(
                self.output_path, f"asys_profiling_result_{dir_name}"
            )
        return True

    def _run_cmd(self, cmd):
        log_info(f"Start run: {cmd}, please wait about {self.period} seconds.")
        # Run msprof command
        ret = subprocess.run(
            [BASH, "-c", cmd],
            shell=False,
            stdout=subprocess.PIPE,
            encoding="utf-8",
            env=os.environ,
            check=False,
        )
        if ret.returncode == 0:
            log_info(f"Succeeded in running profiling.\n{ret.stdout}")
        else:
            log_error(f"Failed to run profiling.\n{ret.stdout}")
            return False
        return True
