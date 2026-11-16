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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

import os
import random
import shutil
import struct
import sys


def get_root():
    return os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


FILE_PATH = os.path.dirname(os.path.realpath(__file__))
ASYS_SRC_PATH = os.path.join(FILE_PATH, "../../../../", "src/asys/")
sys.path.insert(0, ASYS_SRC_PATH)
CONF_SRC_PATH = os.path.join(FILE_PATH, "../../../../", "src/asys/")
sys.argv.insert(0, CONF_SRC_PATH)
ASYS_MAIN_PATH = os.path.join(ASYS_SRC_PATH, "asys.py")
st_root_path = os.path.join(get_root(), "asys")  # root dir: st
test_case_tmp = os.path.join(st_root_path, "test_tmp")

path_env = os.environ["PATH"]
home_env = os.environ["HOME"]

_saved_cwd = os.getcwd()


def enter_test_tmp():
    """记录当前工作目录并切入 test_case_tmp。

    与 restore_cwd 配对使用；若 teardown 不恢复，rmtree(test_case_tmp) 后
    进程 cwd 将指向已删除目录（#235）。
    """
    global _saved_cwd
    _saved_cwd = os.getcwd()
    os.chdir(test_case_tmp)


def restore_cwd():
    """恢复 enter_test_tmp() 记录的工作目录。

    必须在 teardown_method 删除 test_case_tmp 之前调用，否则后续用例或
    pytest 自身调用 os.getcwd()/相对路径操作会抛 FileNotFoundError。
    """
    if os.path.isdir(_saved_cwd):
        os.chdir(_saved_cwd)


def set_env():
    os.environ["PATH"] = "{}/data/scripts".format(st_root_path) + os.pathsep + path_env
    os.environ["HOME"] = "{}/data/asys_test_dir/".format(st_root_path)


def unset_env():
    os.environ["PATH"] = path_env
    os.environ["HOME"] = home_env


def find_dir(dir_path, key_word):
    if not os.access(dir_path, os.R_OK):
        return False
    for dir_name in os.listdir(dir_path):
        if dir_name.startswith(key_word):
            return dir_name
    return ""


def create_dir(dir_path, exist_ok=False):
    try:
        os.makedirs(dir_path, mode=0o777, exist_ok=exist_ok)  # nosec B103  # test dir needs subprocess access
        return True
    except OSError:
        return False


def create_file(file_path):
    if os.path.exists(file_path):
        return False
    else:
        with open(file_path, "w", encoding="utf-8") as fp:
            fp.close()
        return True


def remove_dir(dir_path):
    if not os.access(dir_path, os.F_OK):
        return False
    if not os.access(dir_path, os.W_OK):
        return False
    shutil.rmtree(dir_path)
    return True


def check_output_file(check_dir, file_name):
    dirs = os.listdir(test_case_tmp)
    if not dirs:
        return False
    asys_out_dir = os.path.join(test_case_tmp, dirs[0])
    file_path = os.path.join(asys_out_dir, "dfx", check_dir, file_name)
    if not os.path.exists(file_path):
        return False
    return True


def check_output_structure(check_list):
    # check log, stackcore, bbox, graph, ops and software_info.txt
    dirs = os.listdir(test_case_tmp)
    if not dirs:
        return False
    asys_out_dir = os.path.join(test_case_tmp, dirs[0])
    dfx_dir = os.path.join(asys_out_dir, "dfx")
    if "software" in check_list:
        software_info_file = os.path.join(asys_out_dir, "software_info.txt")
        if not os.path.exists(software_info_file):
            return False
    if "hardware" in check_list:
        software_info_file = os.path.join(asys_out_dir, "hardware_info.txt")
        if not os.path.exists(software_info_file):
            return False
    if "status" in check_list:
        software_info_file = os.path.join(asys_out_dir, "status_info.txt")
        if not os.path.exists(software_info_file):
            return False
    if "log" in check_list:
        log_host_dir = os.path.join(dfx_dir, "log", "host")
        log_device_dir = os.path.join(dfx_dir, "log", "device")
        if not os.path.exists(log_host_dir) or not os.listdir(log_host_dir):
            return False
        if not os.path.exists(log_device_dir) or not os.listdir(log_device_dir):
            return False
    if "stackcore" in check_list:
        stackcore_dir = os.path.join(dfx_dir, "stackcore")
        if not os.path.exists(stackcore_dir) or not os.listdir(stackcore_dir):
            return False
    if "bbox" in check_list:
        bbox_dir = os.path.join(dfx_dir, "bbox")
        if not os.path.exists(bbox_dir) or not os.listdir(bbox_dir):
            return False
    if "graph" in check_list:
        graph_dir = os.path.join(dfx_dir, "graph")
        if not os.path.exists(graph_dir) or not os.listdir(graph_dir):
            return False
    if "ops" in check_list:
        op_dir = os.path.join(dfx_dir, "ops")
        if not os.path.exists(op_dir) or not os.listdir(op_dir):
            return False
    if "debug_kernel" in check_list:
        op_dir = os.path.join(dfx_dir, "ops/debug_kernel")
        if not os.path.exists(op_dir) or not os.listdir(op_dir):
            return False
    if "vendor_config" in check_list:
        ini_file = os.path.join(dfx_dir, "ops/vendor_config/config.ini")
        vendor_config_path = os.path.join(dfx_dir, "ops/vendor_config/")
        if (
            not os.path.isfile(ini_file)
            or not os.path.isdir(vendor_config_path)
            or not os.listdir(vendor_config_path)
        ):
            return False
    if "custom_config" in check_list:
        custom_config_path = os.path.join(dfx_dir, "ops/custom_config/")
        if not os.path.exists(custom_config_path) or not os.listdir(custom_config_path):
            return False
    if "data-dump" in check_list:
        dump_path = os.path.join(dfx_dir, "data-dump")
        if not os.path.exists(dump_path) or not os.listdir(dump_path):
            return False
    if "atrace" in check_list:
        atrace_path = os.path.join(dfx_dir, "atrace")
        if not os.path.exists(atrace_path) or not os.listdir(atrace_path):
            return False
    if "atrace_file" in check_list:
        atrace_file = os.path.join(
            dfx_dir,
            "atrace/trace_17965_17965_20240302100542653636/ts_0_event_17990_20240302100546637402/ts_0_17990_20240302100546761462.txt",
        )
        if not os.path.exists(atrace_file) or not os.path.isfile(atrace_file):
            return False
    if "npu_collect_intermediates" in check_list:
        npu_collect_path = os.path.join(asys_out_dir, "npu_collect_intermediates")
        if os.path.exists(npu_collect_path):
            return False
    if "host_driver" in check_list:
        host_driver_path = os.path.join(
            asys_out_dir, "dfx/log/host/driver/host-driver_20240524062534026.log"
        )
        if not os.path.isfile(host_driver_path):
            return False
    return True


def check_atrace_file(file_name, asys_out_dir, mode="collect"):
    if mode == "collect":
        file_path = os.path.join(asys_out_dir, "dfx", file_name)
    else:
        file_path = os.path.join(asys_out_dir, file_name)
    if os.path.exists(file_path):
        if file_path.endswith(".bin"):
            return True
        with open(file_path, "r", encoding="utf-8") as fr:
            data = fr.read()
            if "item_name0[a]" not in data:
                return False
            if "item_name2[0b10]" not in data:
                return False
            if "item_name4[0b100]" not in data:
                return False
            if "item_name6[0x6]" not in data:
                return False
            if "item_name9[aa]" not in data:
                return False
            if "item_name11[0b1100110, 0b1100110]" not in data:
                return False
            if "item_name14[0x69, 0x69]" not in data:
                return False
            return True
    return False


STRUCT_TYPE = [0, 1, 2, 3, 4, 5, 6, 7, 8, 100, 101, 102, 103, 104, 105, 106, 107, 108]


def get_length_byte(item_type):
    if item_type in [0, 1, 2, 100, 101, 102]:
        return 1
    elif item_type in [3, 4, 103, 104]:
        return 2
    elif item_type in [5, 6, 105, 106]:
        return 4
    elif item_type in [7, 8, 107, 108]:
        return 8


def write_ctrl_head(fw):
    magic = 0xD928
    version = random.randint(2, 3)
    type = 0
    structSize = 0
    dataSize = 0
    tzOffset = 480
    realTime = 1715252892408752464
    data = struct.pack(
        "@6IQ16s",
        magic,
        version,
        type,
        structSize,
        dataSize,
        tzOffset,
        realTime,
        "0".encode(),
    )
    fw.write(data)


def write_ctrl_head_error(fw):
    magic = 0xD927
    version = random.randint(2, 3)
    type = 0
    structSize = 0
    dataSize = 0
    tzOffset = 480
    realTime = 1715252892408752464
    data = struct.pack(
        "@6IQ16s",
        magic,
        version,
        type,
        structSize,
        dataSize,
        tzOffset,
        realTime,
        "0".encode(),
    )
    fw.write(data)


def write_struct_segment(fw):
    struct_dict = dict()
    structCount = 3
    fw.write(struct.pack("@I36s", structCount, "0".encode()))
    for i in range(structCount):
        struct_name = f"demo{i}"
        itemNum = 18
        structType = i
        fw.write(
            struct.pack(
                "@32sIB3s", struct_name.encode(), itemNum, structType, "0".encode()
            )
        )
        item_lists = []
        for j in range(itemNum):
            item_name = f"item_name{j}"
            item_type = STRUCT_TYPE[j]
            if item_type in [0, 100]:
                item_mode = 3
            elif item_type in [1, 3, 101, 103, 7]:
                item_mode = 0
            elif item_type in [2, 4, 102, 104, 108]:
                item_mode = 1
            else:
                item_mode = 2
            item_length = 2
            if item_type < 100:
                item_length = 1
            fw.write(
                struct.pack(
                    "@32s2BH4s",
                    item_name.encode(),
                    item_type,
                    item_mode,
                    item_length * get_length_byte(item_type),
                    "0".encode(),
                )
            )
            item_lists.append([item_name, item_type, item_mode, item_length])
        struct_dict[structType] = {"struct_name": struct_name, "item_lists": item_lists}
    return struct_dict


def write_data(fw, item_list):
    item_name, item_type, item_mode, item_length = item_list
    for _ in range(item_length):
        if item_type in [0, 100]:
            fw.write(struct.pack("@s", "a".encode()))
        else:
            if item_type in [1, 2, 101, 102]:
                fw.write(struct.pack("@B", item_type))
            elif item_type in [3, 4, 103, 104]:
                fw.write(struct.pack("@H", item_type))
            elif item_type in [5, 6, 105, 106]:
                fw.write(struct.pack("@I", item_type))
            elif item_type in [7, 8, 107, 108]:
                fw.write(struct.pack("@Q", item_type))


def write_data_segment(fw):
    write_ctrl_head(fw)
    struct_dict = write_struct_segment(fw)
    msgSize = 128
    msgTxtSize = 112
    msgNum = 3
    res = 0
    fw.write(struct.pack("@4I", msgSize, msgTxtSize, msgNum, res))
    for i in range(msgNum):
        cycle = i
        txtSize = 93
        busy = False
        struct_type = i
        fw.write(
            struct.pack("@QI?B2s", cycle, txtSize, busy, struct_type, "0".encode())
        )
        struct_info = struct_dict.get(struct_type)
        for item_list in struct_info.get("item_lists"):
            write_data(fw, item_list)


def great_bin(trace_file):
    with open(trace_file, "wb") as fw:
        # magic
        write_data_segment(fw)


def great_error_bin(trace_file):
    with open(trace_file, "wb") as fw:
        # magic
        write_ctrl_head_error(fw)


def check_file_contents(check_file, content):
    if not os.path.exists(check_file):
        return False
    if not os.path.isfile(check_file):
        return False
    try:
        with open(check_file, "r", encoding="utf-8") as rd:
            read_res = rd.read()
        if content in read_res:
            return True
    except Exception:
        return False
    return False


class AssertTest:
    def assertTrue(self, value):
        assert value


class DrvDsmi:
    device_count = 0
    device_health = 0
    device_errorcode = 0
    query_errorstring = 0
    device_power_info = 0
    device_temperature = 0
    device_frequency = 0
    device_voltage = 0
    device_utilization_rate = 0
    memory_info = 0
    hbm_info = 0
    total_ecc_isolated_pages_info = 0
    clear_ecc_isolated_statistics_info = 0
    get_device_info = 0
    get_soc_sensor_info = 0

    @staticmethod
    def set_res(
        device_count=0,
        device_health=0,
        device_errorcode=0,
        query_errorstring=0,
        device_power_info=0,
        device_temperature=0,
        device_frequency=0,
        device_voltage=0,
        device_utilization_rate=0,
        memory_info=0,
        hbm_info=0,
        total_ecc_isolated_pages_info=0,
        clear_ecc_isolated_statistics_info=0,
        get_device_info=0,
        get_soc_sensor_info=0,
    ):
        DrvDsmi.device_count = device_count
        DrvDsmi.device_health = device_health
        DrvDsmi.device_errorcode = device_errorcode
        DrvDsmi.query_errorstring = query_errorstring
        DrvDsmi.device_power_info = device_power_info
        DrvDsmi.device_temperature = device_temperature
        DrvDsmi.device_frequency = device_frequency
        DrvDsmi.device_voltage = device_voltage
        DrvDsmi.device_utilization_rate = device_utilization_rate
        DrvDsmi.memory_info = memory_info
        DrvDsmi.hbm_info = hbm_info
        DrvDsmi.total_ecc_isolated_pages_info = total_ecc_isolated_pages_info
        DrvDsmi.clear_ecc_isolated_statistics_info = clear_ecc_isolated_statistics_info
        DrvDsmi.get_device_info = get_device_info
        DrvDsmi.get_soc_sensor_info = get_soc_sensor_info

    @staticmethod
    def dsmi_get_device_count(p_device_count):
        return DrvDsmi.device_count

    @staticmethod
    def dsmi_get_device_health(device_id, p_health_count):
        return DrvDsmi.device_health

    @staticmethod
    def dsmi_get_device_errorcode(device_id, p_error_count, perrorcode):
        return DrvDsmi.device_errorcode

    @staticmethod
    def dsmi_query_errorstring(device_id, error_code, error_info, number):
        return DrvDsmi.query_errorstring

    @staticmethod
    def dsmi_get_device_power_info(device_id, p_power_info):
        return DrvDsmi.device_power_info

    @staticmethod
    def dsmi_get_device_temperature(device_id, p_temperature):
        return DrvDsmi.device_temperature

    @staticmethod
    def dsmi_get_device_frequency(device_id, device_type, p_frequency):
        return DrvDsmi.device_frequency

    @staticmethod
    def dsmi_get_device_voltage(device_id, p_voltage):
        return DrvDsmi.device_voltage

    @staticmethod
    def dsmi_get_device_utilization_rate(device_id, device_type, p_utilization):
        return DrvDsmi.device_utilization_rate

    @staticmethod
    def dsmi_get_memory_info(device_id, p_memory_info):
        return DrvDsmi.memory_info

    @staticmethod
    def dsmi_get_hbm_info(device_id, p_memory_info):
        return DrvDsmi.hbm_info

    @staticmethod
    def dsmi_get_total_ecc_isolated_pages_info(
        device_id, dsmi_device_type_hbm, p_device_ecc_info
    ):
        return DrvDsmi.total_ecc_isolated_pages_info

    @staticmethod
    def dsmi_clear_ecc_isolated_statistics_info(device_id):
        return DrvDsmi.clear_ecc_isolated_statistics_info

    @staticmethod
    def dsmi_get_device_info(device_id, cmd, gbm, mem_info, normal_mem):
        return DrvDsmi.get_device_info

    @staticmethod
    def dsmi_get_soc_sensor_info(device_id, soc_id, p_temperature):
        return DrvDsmi.get_soc_sensor_info


class DrvHal:
    ChipInfo = 0
    GetDeviceInfo = 0
    GetPhyIdByIndex = 0

    @staticmethod
    def set_res(ChipInfo=0, GetDeviceInfo=0, GetPhyIdByIndex=0):
        DrvHal.ChipInfo = ChipInfo
        DrvHal.GetDeviceInfo = GetDeviceInfo
        DrvHal.GetPhyIdByIndex = GetPhyIdByIndex

    @staticmethod
    def halGetChipInfo(device_id, p_chip_info):
        return DrvHal.ChipInfo

    @staticmethod
    def halGetDeviceInfo(device_id, module_type_aicpu, type_core_num, p_aicpu_count):
        return DrvHal.GetDeviceInfo

    @staticmethod
    def drvDeviceGetPhyIdByIndex(device_id, phyid):
        return DrvHal.GetPhyIdByIndex


class DrvAml:
    DeviceGetCpuInfo = 0
    DeviceGetAicoreInfo = 0
    DeviceGetBusInfo = 0
    DeviceGetHbmInfo = 0

    @staticmethod
    def set_res(
        DeviceGetCpuInfo=0,
        DeviceGetAicoreInfo=0,
        DeviceGetBusInfo=0,
        DeviceGetHbmInfo=0,
    ):
        DrvAml.DeviceGetCpuInfo = DeviceGetCpuInfo
        DrvAml.DeviceGetAicoreInfo = DeviceGetAicoreInfo
        DrvAml.DeviceGetBusInfo = DeviceGetBusInfo
        DrvAml.DeviceGetHbmInfo = DeviceGetHbmInfo

    @staticmethod
    def AmlDeviceGetCpuInfo(device_id, cpu_info):
        return DrvAml.DeviceGetCpuInfo

    @staticmethod
    def AmlDeviceGetAicoreInfo(device_id, aic_info):
        return DrvAml.DeviceGetAicoreInfo

    @staticmethod
    def AmlDeviceGetBusInfo(device_id, bus_info):
        return DrvAml.DeviceGetBusInfo

    @staticmethod
    def AmlDeviceGetHbmInfo(device_id, hbm_info):
        return DrvAml.DeviceGetHbmInfo
