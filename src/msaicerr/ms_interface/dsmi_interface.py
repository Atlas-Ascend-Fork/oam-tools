#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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
"""
DRV Interface
"""

# Standard Packages
import ctypes
import logging
from enum import Enum
from typing import Optional

MODULE_TYPE_VECTOR_CORE = 7
INFO_TYPE_CORE_NUM = 3
MODULE_TYPE_AICORE = 4


class DsmiErrorCode(Enum):
    DSMI_ERROR_NONE = 0
    DSMI_ERROR_NO_DEVICE = 1
    DSMI_ERROR_INVALID_DEVICE = 2
    DSMI_ERROR_INVALID_HANDLE = 3
    DSMI_ERROR_INNER_ERR = 7
    DSMI_ERROR_PARA_ERROR = 8
    DSMI_ERROR_NOT_EXIST = 11
    DSMI_ERROR_BUSY = 13
    DSMI_ERROR_WAIT_TIMEOUT = 16
    DSMI_ERROR_IOCRL_FAIL = 17
    DSMI_ERROR_SEND_MESG = 27
    DSMI_ERROR_OPER_NOT_PERMITTED = 46
    DSMI_ERROR_TRY_AGAIN = 51
    DSMI_ERROR_MEMORY_OPT_FAIL = 58
    DSMI_ERROR_PARTITION_NOT_RIGHT = 86
    DSMI_ERROR_RESOURCE_OCCUPIED = 87
    DSMI_ERROR_NOT_SUPPORT = 0xFFFE


class DsmiChipInfoStru(ctypes.Structure):
    _fields_ = [
        ("chip_type", ctypes.c_char * 32),
        ("chip_name", ctypes.c_char * 32),
        ("chip_ver", ctypes.c_char * 32),
    ]

    def get_complete_platform(self) -> str:
        res = self.chip_type + self.chip_name
        return res.decode("UTF-8")

    def get_ver(self) -> str:
        return self.chip_ver.decode("UTF-8")


class DSMIInterface:
    """
    DRV Function Wrappers
    """

    prof_online: dict = {}

    def __init__(self):
        self.dsmidll = ctypes.CDLL("libdrvdsmi_host.so")
        self.drvhal = ctypes.CDLL("libascend_hal.so")

    def get_device_count(self) -> int:
        device_count = (ctypes.c_int * 1)()
        self.dsmidll.dsmi_get_device_count.restype = ctypes.c_int
        error_code = self.dsmidll.dsmi_get_device_count(device_count)
        if self._parse_error(error_code, "dsmi_get_device_count"):
            return 0
        return device_count[0]

    def get_chip_info(self, device_id: int) -> Optional[DsmiChipInfoStru]:
        device_id = ctypes.c_int(device_id)
        result_struct = DsmiChipInfoStru()
        self.dsmidll.dsmi_get_chip_info.restype = ctypes.c_int
        error_code = self.dsmidll.dsmi_get_chip_info(
            device_id, ctypes.c_void_p(ctypes.addressof(result_struct))
        )
        if self._parse_error(error_code, "dsmi_get_chip_info"):
            return None
        return result_struct

    def get_vector_core_count(self, device_id: int) -> int:
        type_vector_core = ctypes.c_int(MODULE_TYPE_VECTOR_CORE)
        type_core_num = ctypes.c_int(INFO_TYPE_CORE_NUM)
        p_veccore_count = ctypes.pointer(ctypes.c_int())
        try:
            ret = self.drvhal.halGetDeviceInfo(
                device_id, type_vector_core, type_core_num, p_veccore_count
            )
        except AttributeError:
            logging.error("Failed to obtain core information.")
            return 0
        if ret != 0:
            return 0
        return p_veccore_count.contents.value

    def get_aicore_count(self, device_id: int) -> int:
        module_type_aicore = ctypes.c_int(MODULE_TYPE_AICORE)
        type_core_num = ctypes.c_int(INFO_TYPE_CORE_NUM)
        p_aicore_count = ctypes.pointer(ctypes.c_int())
        try:
            ret = self.drvhal.halGetDeviceInfo(
                device_id, module_type_aicore, type_core_num, p_aicore_count
            )
        except AttributeError:
            logging.error("Failed to obtain core information.")
            return 0
        if ret != 0:
            return 0
        return p_aicore_count.contents.value

    @staticmethod
    def _parse_error(error_code: int, function_name: str, allow_positive=False) -> bool:
        if error_code != 0:
            if allow_positive and error_code > 0:
                logging.debug(
                    "DRV API Call %s() Success with return code %d",
                    function_name,
                    error_code,
                )
            else:
                try:
                    logging.error(
                        "DSMI API Call %s failed: %s",
                        function_name,
                        DsmiErrorCode(error_code).name,
                    )
                    return True
                except ValueError:
                    pass
                logging.error(
                    "DSMI API Call %s failed with unknown code: %s",
                    function_name,
                    error_code,
                )
                return True
        else:
            logging.debug("DSMI API Call %s() Success", function_name)
        return False


def get_soc_version():
    return DSMIInterface().get_chip_info(0).get_complete_platform()
