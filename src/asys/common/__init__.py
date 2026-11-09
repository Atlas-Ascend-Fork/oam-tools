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

from common import log
from common.log import log_debug, log_info, log_warning, log_error, close_log, open_log
from common.const import consts, RetCode, Singleton, STACKTRACE, ScreenResult
from common.file_operate import FileOperate
from common.cmd_run import (
    run_command,
    run_cmd_output,
    run_cmd_list,
    run_linux_cmd,
    popen_run_cmd,
    real_time_output,
)
from common.path import get_project_conf, get_ascend_home, get_log_conf_path
from common.device import DeviceInfo
from common.chip_handler import ChipHandler, get_device
from common.compress_output_dir import compress_output_dir_tar
from common.task_common import get_cann_log_path, timeout_decorator
from common.supported_chip import (
    AsysConfigSupportedChip,
    AsysDiagnoseSupportedChip,
    AsysProfilingSupportedChip,
)


__all__ = [
    "log",
    "log_debug",
    "log_info",
    "log_warning",
    "log_error",
    "close_log",
    "open_log",
    "consts",
    "RetCode",
    "Singleton",
    "STACKTRACE",
    "ScreenResult",
    "FileOperate",
    "run_command",
    "run_cmd_output",
    "run_cmd_list",
    "run_linux_cmd",
    "popen_run_cmd",
    "real_time_output",
    "get_project_conf",
    "get_ascend_home",
    "get_log_conf_path",
    "DeviceInfo",
    "ChipHandler",
    "get_device",
    "compress_output_dir_tar",
    "get_cann_log_path",
    "timeout_decorator",
    "AsysConfigSupportedChip",
    "AsysDiagnoseSupportedChip",
    "AsysProfilingSupportedChip",
]
