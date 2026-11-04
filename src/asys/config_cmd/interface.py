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

import ctypes
import sys
import re

from common import log_info, log_error, FileOperate
from common.const import ConfigOptionName, ALL_SUPPORTED_CHIP_TYPE, ConfigOperateType
from view import generate_report


def _check_supported_chips(device_obj, device_id, operate):
    options = FileOperate().read_config()
    if not options:
        return False, False, None
    aic_supported_chips = options[ConfigOptionName.AIC_VOLTAGE.value][operate]
    bus_supported_chips = options[ConfigOptionName.BUS_VOLTAGE.value][operate]
    chip_info = device_obj.get_chip_info(device_id)
    aic_res = ALL_SUPPORTED_CHIP_TYPE in aic_supported_chips or any(
        re.search(rf"{i}", chip_info) for i in aic_supported_chips
    )
    bus_res = ALL_SUPPORTED_CHIP_TYPE in bus_supported_chips or any(
        re.search(rf"{i}", chip_info) for i in bus_supported_chips
    )
    return aic_res, bus_res, chip_info


def get_stress_detect_config(device_id, device_obj):
    """config get stress_detect, aic & bus volt"""
    aic_res, bus_res, _ = _check_supported_chips(
        device_obj, device_id, ConfigOperateType.GET.value
    )
    config_data = []
    aic_info = device_obj.get_device_aic_info(device_id)
    if aic_info[1] != device_obj.UNSUPPORTED_KEY_WORDS[-1] and aic_res:
        config_data.append(["AI Core Voltage (MV)", aic_info[1]])
    bus_info = device_obj.get_device_bus_info(device_id)
    if bus_info[0] != device_obj.UNSUPPORTED_KEY_WORDS[-1] and bus_res:
        config_data.append(["Bus Voltage (MV)", bus_info[0]])
    # get ai core volt & bus volt, all failed
    if not config_data:
        log_error(f"Configuration unsuccessfully get, on device {device_id}.")
        return False

    table_header = [[f"Device ID: {device_id}", "CURRENT CONFIGURATION"]]
    table_data = {"none": config_data}
    ret_str = generate_report(table_header, table_data)
    sys.stdout.write(ret_str)  # print screen
    return True


def restore_stress_detect_config(device_id, device_obj):
    """config restore stress_detect, aic & bus volt"""
    aic_res, bus_res, chip_info = _check_supported_chips(
        device_obj, device_id, ConfigOperateType.RESTORE.value
    )
    if not aic_res and not bus_res:
        log_error(f"Restore aic_voltage and bus_voltage not supported at {chip_info}")
        return False
    try:
        ret_code = device_obj.ascend_ml.AmlStressRestore(ctypes.c_int32(device_id))
    except (AttributeError, OSError, TypeError, ctypes.ArgumentError) as e:
        log_error(f"AmlStressRestore raised {type(e).__name__}: {e}")
        ret_code = None

    if ret_code != 0:
        log_error(f"Configuration unsuccessfully restore, on device {device_id}.")
        return False

    log_info(f"Configuration successfully restore, on device {device_id}.")
    return True
