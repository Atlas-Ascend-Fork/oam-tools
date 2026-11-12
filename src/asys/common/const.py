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

import enum
from pathlib import Path

PROCESSES_NUMBER = 4
DEVICE_ID_MIN = 0
DEVICE_ID_MAX = 63
MAX_CHAR_LINE = 100

MEMORY_FREQUENCY = 1
HBM_FREQUENCY = 6
CONTROL_CPU_FREQUENCY = 2
AI_CORE_FREQUENCY = 7

MEM_BANDWIDTH_USE = 5
HBM_BANDWIDTH_USE = 10
AI_CORE_USE = 2
AI_CPU_USE = 3
CONTROL_CPU_USE = 4

NOT_SUPPORT = "-"
UNKNOWN = "Unknown"
NONE = "none"

CANN_LOG_NAME = "log"
ATRACE_LOG_NAME = "atrace"

REG_OFF = 0
REG_THREAD = 1
REG_STACK = 2

HBM_MIN_TIMEOUT = 0  # detection side
CPU_MIN_TIMEOUT = 1  # detection 1s
DETECT_MAX_TIMEOUT = 604800  # one week
DETECT_DEFAULT_TIMEOUT = 600

CHECK_BIN_MAX_TIMEOUT = 60
CHECK_BIN_DEFAULT_TIMEOUT = 10

CPU_DETECT_ERROR_CODE_MIN = 500000
CPU_DETECT_ERROR_CODE_MAX = 599999

ADDR_LEN_HEX = 18  # 0x 0000 0000 0000 0000
ADDR_BIT_LEN = 16  # 0000 0000 0000 0000

GDB_LAYER_MAX = 32

MAX_PERIOD = 2592000  # 30*24*3600
LP_MODE_NO = 0
LP_MODE_AIC = 1
LP_MODE_LP = 2

# sigrtmin
SIGRTMIN = 34
STACKTRACE = "stacktrace"

DSMI_UB_PORT_NUM = 36
DL_PORT_RX_VL_NUM = 16
STATS_ITEM_NUM = 50
UBQOS_MAX_SL_NUM = 16

UB_ENTIRE_STATUS_MAP = {
    0: "DSMI_UB_ALL_PORT_NO_LINK (All ports have no link)",
    1: "DSMI_UB_ALL_PORT_LINK (All ports have link)",
    2: "DSMI_UB_PARTIAL_PORT_LINK (Partial ports have link)",
    3: "DSMI_UB_NO_NEED_LINK (No link required)",
}

UB_PORT_STATUS_MAP = {
    0: "DSMI_UB_PORT_STATUS_INITIAL (Initial status)",
    1: "DSMI_UB_PORT_STATUS_FULL_LANE (Full lane normal)",
    2: "DSMI_UB_PORT_STATUS_PARTIAL_LANE (Partial lane normal)",
    3: "DSMI_UB_PORT_STATUS_NONE_LANE (No lane normal)",
}

BALANCE_ALGORITHM_MAP = {
    1: "Hash by lower 2 bits of address (only check address low 2 bits)",
    2: "Hash by multiple bits of address (check multiple address bits)",
    0: "Reserved/Unspecified algorithm",
}

GET_DEVICES_INFO_TIMEOUT = 10

# #399 超时规格：msaicerr --env 单卡执行超时 1 分钟（asys diagnose 逐卡调用）
MSAICERR_ENV_TIMEOUT = 60
# #399 超时规格：msaicerr -p 报错分析超时 3 分钟（asys analyze aicore_error 转调）
MSAICERR_ANALYZE_TIMEOUT = 180
# #399 超时规格：grep / addr2line / readelf 等单条外部命令超时 1 分钟
CMD_TIMEOUT = 60
# stackcore/coretrace 的 addr2line 逐帧符号化：与 grep 同规格（#399）
ADDR2LINE_TIMEOUT = 60

ALL_NOT_SUPPORTED_CHIP_TYPE = "NULL"
ALL_SUPPORTED_CHIP_TYPE = "ALL"

CONFIG_TABLE_FILE = Path(__file__).parent.parent / "conf" / "config_table.csv"


class ScreenResult(enum.Enum):
    PASS = "Pass"
    FAIL = "Fail"
    WARN = "Warn"


class CannPkg:
    firmware = "firmware"
    driver = "driver"
    runtime = "runtime"
    ge_compiler = "ge-compiler"
    bisheng_compiler = "bisheng-compiler"
    toolkit = "oam_tools"
    dvpp = "dvpp"
    aoe = "aoe"
    hccl = "hccl"
    ncs = "ncs"
    opbase = "opbase"
    ops_cv = "ops_cv"
    ops_legacy = "ops_legacy"
    ops_math = "ops_math"
    ops_nn = "ops_nn"
    ops_transformer = "ops_transformer"

    @classmethod
    def get_all_pkg_list(cls):
        return [
            cls.firmware,
            cls.driver,
            cls.runtime,
            cls.ge_compiler,
            cls.bisheng_compiler,
            cls.toolkit,
            cls.dvpp,
            cls.aoe,
            cls.hccl,
            cls.ncs,
            cls.opbase,
            cls.ops_cv,
            cls.ops_legacy,
            cls.ops_math,
            cls.ops_nn,
            cls.ops_transformer,
        ]


class Singleton(type):
    """Singleton class"""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in Singleton._instances:
            Singleton._instances[cls] = super().__call__(*args, **kwargs)
        return Singleton._instances[cls]

    def clear(cls):
        try:
            del Singleton._instances[cls]
        except KeyError:
            pass


class RetCode(enum.Enum):
    SUCCESS = 0
    FAILED = 1
    ARG_PATH_INVALID = 2
    ARG_EMPTY_STRING = 3
    ARG_SAPCE_STRING = 4
    ARG_ILLEGAL_STRING = 5
    ARG_NO_EXIST_DIR = 6
    ARG_NO_EXECUTABLE = 7
    ARG_NO_WRITABLE_PERMISSION = 8
    ARG_CREATE_DIR_FAILED = 9
    READ_FILE_FAILED = 10
    PERMISSION_FAILED = 11


class ConfigOptionName(enum.Enum):
    CHIP_NAME = "chip_name"
    POWER = "power"
    TEMPERATURE = "temperature"
    HEALTH = "health"
    ACPU_CNT = "acpu_cnt"
    ACPU_USAGE = "acpu_usage"
    CCPU_USAGE = "ccpu_usage"
    CCPU_CNT = "ccpu_cnt"
    CCPU_FREQUENCY = "ccpu_frequency"
    CCPU_VOLTAGE = "ccpu_voltage"
    AIC_CNT = "aic_cnt"
    AIC_USAGE = "aic_usage"
    AIC_FREQUENCY = "aic_frequency"
    AIC_VOLTAGE = "aic_voltage"
    BUS_VOLTAGE = "bus_voltage"
    CPU_FREQUENCY = "cpu_frequency"
    RING_FREQUENCY = "ring_frequency"
    MATA_FREQUENCY = "mata_frequency"
    L2BUFFER_FREQUENCY = "l2buffer_frequency"
    DDR_TOTAL = "ddr_total"
    DDR_USED = "ddr_used"
    DDR_BANDWIDTH = "ddr_bandwidth"
    DDR_FREQUENCY = "ddr_frequency"
    HBM_TOTAL = "hbm_total"
    HBM_USED = "hbm_used"
    HBM_BANDWIDTH_USE = "hbm_bandwidth_usage"
    HBM_FREQUENCY = "hbm_frequency"
    HBM_VOLTAGE = "hbm_voltage"


class ConfigOperateType(enum.Enum):
    GET = "get"
    SET = "set"
    RESTORE = "restore"


class Constants:
    @property
    def help_cmd(self):
        return "help"

    @property
    def collect_cmd(self):
        return "collect"

    @property
    def launch_cmd(self):
        return "launch"

    @property
    def info_cmd(self):
        return "info"

    @property
    def diagnose_cmd(self):
        return "diagnose"

    @property
    def health_cmd(self):
        return "health"

    @property
    def analyze_cmd(self):
        return "analyze"

    @property
    def config_cmd(self):
        return "config"

    @property
    def profiling_cmd(self):
        return "profiling"

    @property
    def cmd_set(self):
        return [
            self.help_cmd,
            self.collect_cmd,
            self.launch_cmd,
            self.info_cmd,
            self.diagnose_cmd,
            self.health_cmd,
            self.analyze_cmd,
            self.config_cmd,
            self.profiling_cmd,
        ]


consts = Constants()
