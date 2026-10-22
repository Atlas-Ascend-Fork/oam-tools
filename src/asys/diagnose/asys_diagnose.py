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
from pathlib import Path
import re
import sys
import threading
from datetime import datetime, timezone

from common import log_error, log_warning, log_info, log_debug
from common.const import RetCode, UNKNOWN, ScreenResult
from common.const import HBM_MIN_TIMEOUT, CPU_MIN_TIMEOUT, DETECT_MAX_TIMEOUT
from common.cmd_run import run_linux_cmd, run_cmd_output
from common import AsysDiagnoseSupportedChip, DeviceInfo, ChipHandler
from common.file_operate import FileOperate as f
from params.param_dict import ParamDict
from view.table import generate_report
from view.progress_display import waiting
from drv import EnvVarName, LoadSoType

HBM_MODE = "hbm_detect"
CPU_MODE = "cpu_detect"
COMPONENT_MODE = "component"
AICORE_STL_MODE = "aicore_stl_detect"
opp_kernels = ["ops_cv", "ops_legacy", "ops_math", "ops_nn", "ops_transformer"]
SUPPORT_CHIPS = ChipHandler().get_support_chip_regex_list()


class AsysDiagnose:
    """"""

    def __init__(self):
        self.finish_flag = False
        self.device_obj = DeviceInfo()
        self.devices_num = self.device_obj.get_device_count()

    @staticmethod
    def __get_hbm_table_data(device_id, ret):
        link_symbol = ", "
        devices_ecc = []

        if device_id is False:
            devices_ret = [ret[key][0] for key in sorted(ret.keys())]
            devices_ecc = [ret[key][1] for key in sorted(ret.keys())]
            if (
                ScreenResult.PASS.value in devices_ret
                and ScreenResult.WARN.value in devices_ret
            ) or len(devices_ret) == 1:
                devices_str = ", ".join(devices_ret)
            else:
                devices_str = f"{devices_ret[0]} - All"
        else:
            devices_str = ret[device_id][0]

        hbm_table = "HBM Detect"
        if device_id is False and len(devices_ecc) != 1:
            devices_hbm = "(" + link_symbol.join(devices_ecc) + ")"
            ret_data_str = [[hbm_table, devices_str], ["", devices_hbm]]
        elif len(devices_ecc) == 1:
            devices_str += "(" + link_symbol.join(devices_ecc) + ")"
            ret_data_str = [[hbm_table, devices_str]]
        else:
            devices_str += "(" + ret[device_id][1] + ")"
            ret_data_str = [[hbm_table, devices_str]]

        return ret_data_str

    @staticmethod
    def __get_other_table_data(device_id, ret):
        if device_id is False:
            # without '-d', displays information about all devices.
            devices_ret = [ret[key] for key in sorted(ret.keys())]
            if len(set(devices_ret)) > 1 or len(devices_ret) == 1:
                devices_str = ", ".join(devices_ret)
            else:
                devices_str = f"{devices_ret[0]} - All"
        else:
            # with '-d', displays information about the input device.
            devices_str = ret[device_id]

        return devices_str

    def print_save(self, device_id, ret, run_mode):
        """print screen & save file"""
        if device_id is False:
            # without '-d', displays information about all devices.
            table_header = [[f"Group of {len(ret)} Device", "Diagnostic Result"]]
        else:
            # with '-d', displays information about the input device.
            table_header = [[f"Device ID: {device_id}", "Diagnostic Result"]]

        if run_mode == HBM_MODE:
            ret_data_str = self.__get_hbm_table_data(device_id, ret)
            table_data = {" Hardware ": ret_data_str}
        elif run_mode == CPU_MODE:
            ret_data_str = self.__get_other_table_data(device_id, ret)
            table_data = {" Hardware ": [["CPU Detect", ret_data_str]]}
        elif run_mode == COMPONENT_MODE:
            ret_data_str = self.__get_other_table_data(device_id, ret)
            table_data = {" Component ": [["AI Vector", ret_data_str]]}
        elif run_mode == AICORE_STL_MODE:
            ret_data_str = self.__get_other_table_data(device_id, ret)
            table_data = {" Hardware ": [["AICore STL Detect", ret_data_str]]}
        else:
            ret_data_str = self.__get_other_table_data(device_id, ret)
            table_data = {" Performance ": [["Stress Detect", ret_data_str]]}
        ret_str = generate_report(table_header, table_data)
        sys.stdout.write(ret_str)  # print screen

        # save result to file
        output_path = ParamDict().get_arg("output")
        utc_dt = datetime.now(timezone.utc)  # UTC time
        dir_name = utc_dt.astimezone().strftime("%Y%m%d%H%M%S%f")[:-3]
        if output_path is not False:
            try:
                output_file = os.path.join(
                    ParamDict().get_arg("output"), f"diagnose_result_{dir_name}.txt"
                )
                with open(output_file, "w", encoding="utf8") as file:
                    file.write(ret_str)
                log_info(f"output file: {os.path.abspath(output_file)}", force=True)
            except (OSError, TypeError) as e:
                log_error(f"Failed to save result: {e}.")

    def _check_support(self, run_mode):
        # check VMs and docker
        if not run_linux_cmd("systemd-detect-virt", "none"):
            log_error("The diagnose command cannot be executed on VMs and docker.")
            return False

        # username
        if os.getuid() != 0:  # 0 -> administrator
            log_error("The diagnose command must be executed as the root user.")
            return False

        if run_mode == "stress_detect":
            # check opp_kernel, ${install_path}/latest/opp_kernel
            opp_path = EnvVarName().opp_path
            if not opp_path:
                log_error(
                    "The diagnose command can be executed only after the opp_kernel is installed."
                )
                return False
            for ops in opp_kernels:
                if not os.path.isfile(
                    os.path.join(opp_path, "..", "share", "info", ops, "version.info")
                ):
                    log_error(
                        f"The diagnose command can be executed only after the {ops} is installed."
                    )
                    return False

        timeout = ParamDict().get_arg("timeout")
        if run_mode == HBM_MODE and timeout is not False:
            if timeout < HBM_MIN_TIMEOUT or timeout > DETECT_MAX_TIMEOUT:
                log_error(
                    f"The value of timeout must be in the range of [{HBM_MIN_TIMEOUT}, {DETECT_MAX_TIMEOUT}]."
                )
                return False

        if run_mode == CPU_MODE and timeout is not False:
            if timeout < CPU_MIN_TIMEOUT or timeout > DETECT_MAX_TIMEOUT:
                log_error(
                    f"The value of timeout must be in the range of [{CPU_MIN_TIMEOUT}, {DETECT_MAX_TIMEOUT}]."
                )
                return False
        if run_mode == AICORE_STL_MODE and timeout is not False:
            log_warning(
                "The --timeout argument is not supported in aicore_stl_detect mode and will be ignored.",
                force=True,
            )
        if self.devices_num == 0:
            return False
        return True

    @staticmethod
    def check_chip_support(_chip_info):
        if any(re.search(regexp, _chip_info) for regexp in SUPPORT_CHIPS):
            return True
        return False

    def get_diagnose_devices_chip_info(self, device_id):
        diagnose_devices = []
        chip_info = UNKNOWN
        diagnose_supported = AsysDiagnoseSupportedChip()
        if device_id is False:
            for i in range(self.devices_num):
                ret, _chip_info = diagnose_supported.get_supported_chip_info(i)
                if not ret:
                    log_error(
                        f"The diagnose command does not support on device_{i}: {_chip_info}."
                    )
                    continue
                diagnose_devices.append(i)
                chip_info = _chip_info
        else:
            ret, _chip_info = diagnose_supported.get_supported_chip_info(device_id)
            if not ret:
                log_error(f"The diagnose command does not support {_chip_info}.")
            else:
                chip_info = _chip_info
                diagnose_devices = [device_id]
        return diagnose_devices, chip_info

    def hardware_detect(self, run_mode):
        """detect cmd main"""
        device_id = ParamDict().get_arg("device_id")
        diagnose_devices, chip_info = self.get_diagnose_devices_chip_info(device_id)
        if not diagnose_devices or chip_info == UNKNOWN:
            return False

        # aicore_stl_detect is supported on Ascend950 and Ascend960DT only.
        if run_mode == AICORE_STL_MODE:
            diagnose_devices = self.__filter_aicore_stl_devices(diagnose_devices)
            if not diagnose_devices:
                log_error(
                    "The aicore_stl_detect mode is only supported on Ascend950 and Ascend960DT."
                )
                return False

        if not self._check_support(run_mode):
            return False

        # load dll: libascend_ml.so (or libaml_aicore_stl.so for AICore STL mode)
        if run_mode == AICORE_STL_MODE:
            self.device_obj.aml_aicore_stl = LoadSoType().get_aml_aicore_stl()
            if (
                self.device_obj.aml_aicore_stl == RetCode.FAILED
                or self.device_obj.aml_aicore_stl is None
            ):
                log_error("Failed to load libaml_aicore_stl.so for aicore_stl_detect.")
                return False
        elif self.device_obj.ascend_ml == RetCode.FAILED:
            return False

        t = threading.Thread(target=self.wait_view, daemon=True)
        t.start()
        # Multi-thread parallel execution
        handler = ChipHandler().get_handler(chip_info)
        if handler is None:
            log_error(f"{chip_info} is not supported.")
            return False
        ret = handler.run_diagnose(self.device_obj, diagnose_devices, run_mode)

        # ret add not support device
        if device_id is False:
            for i in range(self.devices_num):
                if i in diagnose_devices:
                    continue
                ret[i] = (
                    [ScreenResult.WARN.value, "0"]
                    if run_mode == HBM_MODE
                    else ScreenResult.WARN.value
                )

        if ScreenResult.WARN.value in ret.values():
            log_warning("Diagnosis results have failed, please analyze aml logs")
        self.finish_flag = True
        t.join()
        # screen print & save ret to file
        self.print_save(device_id, ret, run_mode)
        return True

    @staticmethod
    def run_msaicerr_cmd(msaicerr_path, device_id, res):
        cmd = f"{sys.executable} {msaicerr_path} --env -dev={device_id}"
        log_debug(f"Start run: {cmd}")
        ret, output = run_cmd_output(cmd)
        res[device_id] = ScreenResult.PASS.value if ret else ScreenResult.FAIL.value
        return output

    def env_detect(self, run_mode):
        device_id = ParamDict().get_arg("device_id")
        msaicerr_path = (
            ParamDict().tools_path.parents[1].joinpath("msaicerr", "msaicerr.py")
        )
        log_debug(f"Start load msaicerr tools path: {msaicerr_path}")
        log_debug(f"Device num is {self.devices_num}")
        if not self.devices_num:
            log_error("The chip does not have a device for execution.")
            return False
        if not os.path.exists(msaicerr_path):
            log_error(
                "The path of the msaicerr tool cannot be found, please install the whole package."
            )
            return False
        res = {}
        output = ""
        if device_id is False:
            for i in range(self.devices_num):
                log_debug(f"Start run device {i}")
                output = self.run_msaicerr_cmd(msaicerr_path, i, res)
        else:
            output = self.run_msaicerr_cmd(msaicerr_path, device_id, res)
        self.print_save(device_id, res, run_mode)
        if ScreenResult.FAIL.value in res.values():
            debug_info_path = Path(os.getcwd(), "debug_info.txt")
            if not f.check_access(os.getcwd(), os.W_OK) or (
                debug_info_path.exists()
                and not f.check_access(debug_info_path, os.W_OK)
            ):
                log_error(
                    "The current directory or debug_info.txt is immutable, Please check."
                )

            else:
                sys.stdout.write(output)
            return False
        return True

    def run(self):
        """diagnose cmd main"""
        run_mode = ParamDict().get_arg("run_mode")
        if run_mode == COMPONENT_MODE:
            return self.env_detect(run_mode)
        else:
            return self.hardware_detect(run_mode)

    def wait_view(self):
        while not self.finish_flag:
            waiting()
            continue

    def __filter_aicore_stl_devices(self, diagnose_devices):
        """aicore_stl_detect 仅支持 Ascend950 与 Ascend960DT:过滤不支持的 device 并告警。"""
        stl_devices = []
        for dev in diagnose_devices:
            chip_info = self.device_obj.get_chip_info(dev)
            # 960 家族仅 960DT 接入 STL:裸 "960" 会把 960PR 一并放行(两者为不同型号,
            # diag 侧形态表也只注册了 Ascend960DT),故 960 必须带 DT 后缀匹配。
            if chip_info != UNKNOWN and re.search("950|960DT", chip_info):
                stl_devices.append(dev)
            else:
                log_warning(
                    f"device_{dev} ({chip_info}) does not support aicore_stl_detect "
                    "(Ascend950/Ascend960DT only), skipped."
                )
        return stl_devices
