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
import sys

from common import DeviceInfo
from common import log_error
from common import consts
from common.const import UNKNOWN, NONE
from params import ParamDict
from view import generate_report


class AsysHealth:
    """device health check"""

    def __init__(self):
        self.device = DeviceInfo()

    @staticmethod
    def _get_highest_status(ret):
        critical = "Critical"
        alarm = "Alarm"
        warn = "Warning"
        healthy = "Healthy"
        # ret[device_id] is [status, err_info] (run_health_check), so info[0]
        # is the whole status string. Keep taking it exactly as before and only
        # guard the shape, so a malformed entry degrades instead of raising.
        all_device_status = [
            info[0]
            if isinstance(info, (list, tuple)) and info and isinstance(info[0], str)
            else ""
            for info in ret.values()
        ]

        if UNKNOWN in all_device_status:
            return UNKNOWN
        if critical in all_device_status:
            return critical
        if alarm in all_device_status:
            return alarm
        if warn in all_device_status:
            return warn
        if healthy in all_device_status:
            return healthy
        return UNKNOWN

    @staticmethod
    def _save_file(ret):
        """save file"""
        save_str = ""
        # Example: err_info = [health, [[error_code, error_msg], [error_code, error_msg] ...]]
        for device_id in sorted(ret.keys()):
            err_info = ret[device_id]
            table_header = [
                [f"Device ID: {device_id}", f"Overall Health: {err_info[0]}"],
                ["", f"ErrorCode Num: {len(err_info[1])}"],
            ]
            table_data = {NONE: err_info[1]}
            save_str += generate_report(table_header, table_data, split_line=True)
        try:
            output_file = os.path.join(
                ParamDict().asys_output_timestamp_dir, "health_result.txt"
            )
            with open(output_file, "w", encoding="utf8") as file:
                file.write(save_str)
        except OSError as e:
            log_error(f"Failed to save result: {e}.")

    def run_health_check(self, diagnose_devices):
        """Multi-thread parallel execution"""
        ret = {}
        for device_id in diagnose_devices:
            # status -> "Healthy"/"Warning"/"Alarm"/"Critical"/"Unknown"
            status = self.device.get_device_health(device_id)
            # Example: err_info = [[error_code, error_msg], [error_code, error_msg] ...]
            err_info = self.device.get_device_errorcode(device_id)
            ret[device_id] = [status, err_info]
        return ret

    def _print_screen(self, device_id, ret):
        """print screen"""
        if device_id is False:
            # without '-d', displays brief information about all devices.
            highest_status = self._get_highest_status(ret)
            table_header = [
                [f"Group of {len(ret)} Device", f"Overall Health: {highest_status}"]
            ]
            table_data = {
                NONE: [[f"Device ID: {idx}", ret[idx][0]] for idx in sorted(ret.keys())]
            }
        else:
            # with '-d', displays detailed information about the input device.
            table_header = [
                [f"Device ID: {device_id}", f"Overall Health: {ret[device_id][0]}"],
                ["", f"ErrorCode Num: {len(ret[device_id][1])}"],
            ]
            table_data = {NONE: ret[device_id][1]}
            # Only the first five records are displayed on the screen.
            if len(table_data[NONE]) > 5:
                table_data[NONE] = table_data[NONE][:5]
                table_data[NONE].append(["......", "......"])
        print_str = generate_report(table_header, table_data, split_line=True)
        sys.stdout.write(print_str)

    def run(self):
        """health check main"""
        devices_num = self.device.get_device_count()
        if devices_num is None:
            return False

        device_id = ParamDict().get_arg("device_id")
        if device_id is False:
            diagnose_devices = [i for i in range(devices_num)]
        else:
            diagnose_devices = [device_id]

        # Example: ret = {device_id: [health, [[error_code, error_msg], [error_code, error_msg] ...]]}
        ret = self.run_health_check(diagnose_devices)

        if ParamDict().get_command() == consts.health_cmd:
            self._print_screen(device_id, ret)
        else:
            # only collect or launch save file
            self._save_file(ret)

        return True
