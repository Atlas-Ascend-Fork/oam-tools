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

from threading import Thread
from common.device import DeviceInfo
import common.interface as interface


class Ascend91093Handler(DeviceInfo):
    @classmethod
    def need_lp_param(cls):
        return False

    @classmethod
    def support_dvpp(cls):
        return True

    @staticmethod
    def run_diagnose(device_obj, diagnose_devices, run_mode):
        """Multi-thread parallel execution"""
        threads = []
        ret = {}
        master_ids = {}

        logic_master_info = interface.get_devices_master_id(
            device_obj, diagnose_devices
        )
        if run_mode == "hbm_detect":
            _target_func = interface.run_hbm
        elif run_mode == "cpu_detect":
            _target_func = interface.run_cpu
        else:
            return interface.run_diagnose(device_obj, diagnose_devices, run_mode)

        # detected_by maps a logic id to the logic id whose detection result is
        # reported for it. Devices sharing one master id are detected only once
        # and share that result.
        detected_by = {}

        for device_id in diagnose_devices:
            master_id = logic_master_info[device_id]
            if master_id == interface.ERROR_DEVICE_ID:
                # The master id of this device could not be resolved, so it
                # cannot be grouped with any other device. Detect it on its
                # own and report its own result, instead of silently reusing
                # the result of an unrelated device.
                t = Thread(
                    target=_target_func, args=(device_id, device_obj, ret), daemon=True
                )
                t.start()
                threads.append(t)
                detected_by[device_id] = device_id
                continue
            if master_id not in master_ids:
                # new thread
                t = Thread(
                    target=_target_func, args=(device_id, device_obj, ret), daemon=True
                )
                t.start()
                threads.append(t)
                master_ids[master_id] = device_id
            detected_by[device_id] = master_ids[master_id]

        # wait for all threads to end.
        for t in threads:
            t.join()

        ret_logic_id = {}
        for device_id in diagnose_devices:
            ret_logic_id[device_id] = ret[detected_by[device_id]]

        return ret_logic_id
