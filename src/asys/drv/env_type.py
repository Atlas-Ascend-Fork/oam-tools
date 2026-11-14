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
import ctypes

from common import log_error
from common import RetCode
from common import Singleton

AICORE_STL_SO_SUBPATH = "tools/aml/lib64/aicore_stl"
AICORE_STL_SO_NAME = "libaml_aicore_stl.so"


class LoadSoType(metaclass=Singleton):
    def __init__(self):
        self.drvdsmi = None
        self.drvhal = None
        self.asendml = None
        self.aml_aicore_stl = None
        self.ascend_trace = None
        self.ascendcl = None
        self.env_type = ""

    @staticmethod
    def load_dll(so_name):
        try:
            dll = ctypes.cdll.LoadLibrary(so_name)
        except OSError as err:
            log_error(f"OSError: {err}")
            return RetCode.FAILED
        return dll

    @staticmethod
    def ctypes_close_library(lib):
        if lib and lib != RetCode.FAILED:
            dlclose_func = ctypes.CDLL(None).dlclose
            dlclose_func.argtypes = [ctypes.c_void_p]
            dlclose_func.restype = ctypes.c_int
            dlclose_func(getattr(lib, "_handle"))

    @staticmethod
    def get_aicore_stl_so_path():
        # Resolve libaml_aicore_stl.so under ASCEND_HOME_PATH; return None if absent.
        home_path = os.getenv("ASCEND_HOME_PATH")
        if not home_path:
            log_error("ASCEND_HOME_PATH is not set.")
            return None
        so_path = os.path.realpath(
            os.path.join(home_path, AICORE_STL_SO_SUBPATH, AICORE_STL_SO_NAME)
        )
        if not os.path.isfile(so_path):
            return None
        return so_path

    def get_drvdsmi_env_type(self):
        if self.drvdsmi is None:
            env_type = self.get_env_type()
            if env_type == RetCode.FAILED:
                # The platform type is unknown: picking either DSMI flavor
                # could silently load the wrong library on this machine.
                return RetCode.FAILED
            if env_type == "EP":
                so_name = "libdrvdsmi_host.so"
            else:
                so_name = "libdrvdsmi.so"
            self.drvdsmi = self.load_dll(so_name)
        return self.drvdsmi

    def get_drvhal_env_type(self):
        if self.drvhal is None:
            so_name = "libascend_hal.so"
            self.drvhal = self.load_dll(so_name)
        return self.drvhal

    def get_ascend_ml(self):
        # libascend_ml.so is only in the toolkit run pkg.
        if self.asendml is None and self.get_env_type() == "EP":
            so_name = "libascend_ml.so"
            self.asendml = self.load_dll(so_name)
        return self.asendml

    def get_aml_aicore_stl(self):
        # libaml_aicore_stl.so exports AmlAicoreStlDetect (AICore STL self-diagnose).
        # Only in the toolkit run pkg, EP side.
        if self.aml_aicore_stl is None and self.get_env_type() == "EP":
            so_path = self.get_aicore_stl_so_path()
            if so_path is None:
                log_error(
                    f"{AICORE_STL_SO_NAME} not found under "
                    f"$ASCEND_HOME_PATH/{AICORE_STL_SO_SUBPATH}, "
                    "AICore STL detect unavailable."
                )
                return RetCode.FAILED
            self.aml_aicore_stl = self.load_dll(so_path)
        return self.aml_aicore_stl

    def get_ascend_trace(self):
        if self.ascend_trace is None:
            so_name = "libascend_trace.so"
            self.ascend_trace = self.load_dll(so_name)
        return self.ascend_trace

    def get_ascend_cl(self):
        if self.ascendcl is None:
            so_name = "libascendcl.so"
            self.ascendcl = self.load_dll(so_name)
        return self.ascendcl

    def get_env_type(self):
        if self.env_type:
            return self.env_type
        dev = self.get_drvhal_env_type()
        if dev == RetCode.FAILED:
            # The platform type cannot be detected, report the failure explicitly
            # instead of returning an empty string that is indistinguishable
            # from a valid "RC" platform.
            log_error("Failed to obtain the execution environment type.")
            return RetCode.FAILED
        dev.drvGetPlatformInfo.argtypes = [ctypes.POINTER(ctypes.c_int)]
        num = ctypes.c_int(-1)
        ret = dev.drvGetPlatformInfo(ctypes.pointer(num))
        if ret == 0:
            if num.value == 0:
                self.env_type = "RC"
            elif num.value == 1:
                self.env_type = "EP"
            else:
                # Covers both an unsupported platform code and a driver that
                # returns success without writing the out-param (num stays -1).
                log_error(
                    "Failed to obtain the execution environment type, "
                    "unsupported platform code {}.".format(num.value)
                )
                return RetCode.FAILED
        else:
            log_error(
                "Failed to obtain the execution environment type, "
                "drvGetPlatformInfo returned {}.".format(ret)
            )
            return RetCode.FAILED
        return self.env_type

    def dll_close(self):
        self.ctypes_close_library(self.drvdsmi)
        self.ctypes_close_library(self.drvhal)
        self.ctypes_close_library(self.asendml)
        self.ctypes_close_library(self.aml_aicore_stl)
        self.ctypes_close_library(self.ascend_trace)
        self.ctypes_close_library(self.ascendcl)
        self.drvdsmi = None
        self.drvhal = None
        self.asendml = None
        self.aml_aicore_stl = None
        self.ascend_trace = None
        self.ascendcl = None
