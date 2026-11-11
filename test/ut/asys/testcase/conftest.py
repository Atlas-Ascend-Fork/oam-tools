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
import re
import sys
import struct
import random

path_env = os.environ["PATH"]


def pytest_configure(config):
    config.addinivalue_line(
        "filterwarnings", "ignore::DeprecationWarning:multiprocessing.popen_fork"
    )


def get_root():
    return os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


file_path = os.path.dirname(os.path.realpath(__file__))
ut_root_path = os.path.join(get_root(), "asys")  # root dir: ut
ASYS_SRC_PATH = os.path.join(file_path, "../../../../", "src/asys/")
sys.path.insert(0, ASYS_SRC_PATH)
CONF_SRC_PATH = os.path.join(file_path, "../../../../", "src/asys/")
sys.argv[0] = CONF_SRC_PATH
ASYS_MAIN_PATH = os.path.join(ASYS_SRC_PATH, "asys.py")
test_case_tmp = os.path.join(ut_root_path, "test_tmp")
test_trace_tmp = os.path.join(ut_root_path, "test_trace_tmp")


# issue #219：时间戳必须为 YYYY-MM-DD HH:MM:SS.mmm 单点毫秒格式，
# 不允许回退为 SS.mmm.mmm 双小数点。
TRACE_LINE_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} ")
TRACE_DOUBLE_DOT_RE = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}\.\d{3}")


def check_atrace_file(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as fr:
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
            if TRACE_DOUBLE_DOT_RE.search(data):
                return False
            for line in data.splitlines():
                if line and not TRACE_LINE_TS_RE.match(line):
                    return False
            return True
    return False


def create_dir(dir_path, exist_ok=False):
    try:
        os.makedirs(dir_path, mode=0o777, exist_ok=exist_ok)  # nosec B103  # test dir needs subprocess access
        return True
    except OSError:
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


def set_env():
    os.environ["PATH"] = "{}/data/scripts".format(ut_root_path) + os.pathsep + path_env


def unset_env():
    os.environ["PATH"] = path_env


class AssertTest:
    def assertTrue(self, value):
        assert value
