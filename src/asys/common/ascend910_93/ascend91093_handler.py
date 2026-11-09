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
from common.const import ScreenResult


def _safe_target_func(target_func, device_id, device_obj, ret, fallback_value):
    """Run one detection, keeping the WARN contract even on an inner crash.

    A thread that dies (e.g. on a read of ParamDict or an ecc page query
    outside the try blocks) leaves its key missing from ret, and the merge
    below used to index that key directly, crashing the whole diagnosis.
    The fallback keeps the result shape the reporting stage expects for the
    run mode: hbm_detect reports [result, ecc_count], other modes a scalar.
    """
    try:
        target_func(device_id, device_obj, ret)
    except Exception as e:  # noqa: BLE001  # a diagnose thread must never take the CLI down
        interface.log_error(
            f"Detect device {device_id} failed with {type(e).__name__}: {e}"
        )
        ret[device_id] = fallback_value


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
            _fallback_value = [ScreenResult.WARN.value, "0"]
        elif run_mode == "cpu_detect":
            _target_func = interface.run_cpu
            _fallback_value = ScreenResult.WARN.value
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
                    target=_safe_target_func,
                    args=(_target_func, device_id, device_obj, ret, _fallback_value),
                    daemon=True,
                )
                t.start()
                threads.append(t)
                detected_by[device_id] = device_id
                continue
            if master_id not in master_ids:
                # new thread
                t = Thread(
                    target=_safe_target_func,
                    args=(_target_func, device_id, device_obj, ret, _fallback_value),
                    daemon=True,
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
            # A detection thread that failed to write any result (the crash
            # is logged by _safe_target_func) must not take the whole
            # diagnosis down; report WARN with the mode's result shape for
            # the affected device instead.
            ret_logic_id[device_id] = ret.get(detected_by[device_id], _fallback_value)

        return ret_logic_id
