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

import json
import struct

import numpy as np

from conftest import MSAICERR_PATH, RES_PATH, CommonAssert
import os
import sys
import pytest

sys.path.append(MSAICERR_PATH)

from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.constant import Constant
from ms_interface.dump_data_parser import DumpDataParser

dump_file = "exception_info.2.1.20250609144925349"


def create_dump_file(file_name, header_length, body_length):
    with open(file_name, "wb") as f:
        f.write(struct.pack("Q", header_length))
        f.write(bytearray(range(header_length)))
        f.write(bytearray(range(body_length)))


class Selflib:
    @staticmethod
    def ParseDumpProtoToJson(_data_ptr, _data_size, _path_ptr):
        return 0


class Selfliberr:
    @staticmethod
    def ParseDumpProtoToJson(_data_ptr, _data_size, _path_ptr):
        return 1


class SelflibWriteJson:
    """在被调用时才生成json，模拟解析so的落盘时机"""

    def __init__(self, dump_json):
        self.dump_json = dump_json

    def ParseDumpProtoToJson(self, _data_ptr, _data_size, path_ptr):
        with open(path_ptr.decode("utf-8"), "w", encoding="utf-8") as json_file:
            json_file.write(json.dumps(self.dump_json))
        return 0


class TestUtilsMethods(CommonAssert):
    # fixture/setup_method 中赋值，此处声明以明确实例属性集合
    debug_info = None
    old_cwd = None
    temp = None

    @pytest.fixture(autouse=True)
    def change_test_dir(self, tmp_path):
        self.old_cwd = os.getcwd()
        self.temp = tmp_path
        self.debug_info = tmp_path.joinpath("debug_info.txt")
        os.chdir(tmp_path)
        yield
        os.chdir(self.old_cwd)

    @staticmethod
    def common_mock(mocker, dump_json):
        # mock通用方法
        mocker.patch("ctypes.CDLL", return_value=Selflib())
        with open(f"{dump_file}.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(dump_json))

    @staticmethod
    def _make_dump_json(output_data_type=0, output_size="10", output_dim=None):
        """构造仅output的dtype/size/shape可变的dump json，用于dtype落盘相关用例"""
        return {
            "version": "2.0",
            "dump_time": "1749451765349986",
            "output": [
                {
                    "data_type": output_data_type,
                    "format": 0,
                    "shape": {"dim": output_dim or ["2", "2048"]},
                    "data": "",
                    "size": output_size,
                    "sub_format": 0,
                    "address": "0",
                    "dim_range": [],
                    "offset": "3",
                }
            ],
            "input": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["10240", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 0,
                    "input_type": 2,
                }
            ],
            "buffer": [],
            "op_name": "",
            "attr": [],
            "space": [{"type": 0, "data": "", "size": "10"}],
            "dfx_message": "[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, \n",
        }

    def test_parser_dump_file(self, mocker):
        dump_json = {
            "version": "2.0",
            "dump_time": "1749451765349986",
            "output": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "dim_range": [],
                    "offset": "3",
                }
            ],
            "input": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["10240", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 0,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 1,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["1"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 2,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 5,
                    "input_type": 7,
                },
            ],
            "buffer": [],
            "op_name": "",
            "attr": [],
            "space": [{"type": 0, "data": "", "size": "10"}],
            "dfx_message": "[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n",
        }
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        dump_data_parser = DumpDataParser(dump_file, info)
        dump_data_parser.parse()
        # info.result_info
        # 该tensor实际数据为10字节，不是float32 itemsize的整数倍，保持原始bin
        self.assertIn(
            info.dump_info, "exception_info.2.1.20250609144925349.input.0.float32.bin"
        )
        self.assertIn(info.dump_info, "shape: (10240, 2048) size: 10 dtype: float32")

        self.assertIn(
            info.dump_info, "exception_info.2.1.20250609144925349.workspace.0.int8.npy"
        )
        self.assertIn(info.dump_info, "shape: () size: 10 dtype: int8")

        self.assertEqual(dump_data_parser.get_input_data(), [])
        self.assertEqual(dump_data_parser.get_output_data(), [])
        # int64的32字节数据可被itemsize整除，保存为npy
        self.assertIn(
            dump_data_parser.get_bin_data(),
            "exception_info.2.1.20250609144925349.input.1.int64.npy",
        )
        self.assertIn(
            dump_data_parser.get_workspace_data(),
            "exception_info.2.1.20250609144925349.workspace.0.int8.npy",
        )
        self.assertIn(dump_data_parser.get_dfx_message(), "[AIC_INFO] args(20 to 39)")

    def test_ctype_cdll_parse_dump_error(self, mocker, capsys):
        mocker.patch(
            "ctypes.CDLL",
            side_effect=OSError(
                "libascend_dump_parser.so: cannot open shared object file"
            ),
        )
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        self.assertIn(
            capsys.readouterr().out,
            "libascend_dump_parser.so: cannot open shared object file",
        )

    def test_parser_dump_to_json_file_error(self, mocker, capsys):
        mocker.patch("ctypes.CDLL", return_value=Selfliberr())
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        # 解析 proto 失败的根因是 dump 数据非法(4)，错误码不得误报为库加载失败(3)
        self.assertIn(
            capsys.readouterr().out, "Error Detail: [4] invalid or corrupted dump file"
        )

    def test_parser_dump_file_file_size_lt_uint64_size_error(self, mocker, capsys):
        dump_json = {
            "version": "2.0",
            "dump_time": "1749451765349986",
            "output": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "dim_range": [],
                    "offset": "3",
                }
            ],
            "input": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["10240", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 0,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 1,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["1"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 2,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 5,
                    "input_type": 7,
                },
            ],
            "buffer": [],
            "op_name": "",
            "attr": [],
            "space": [{"type": 0, "data": "", "size": "10"}],
            "dfx_message": "[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n",
        }
        self.common_mock(mocker, dump_json)
        with open(dump_file, "wb") as f:
            f.write(struct.pack("Q", 8))
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        self.assertIn(capsys.readouterr().out, "[4] invalid or corrupted dump file")

    def test_parser_dump_file_header_len_gt_file_size_error(self, mocker, capsys):
        dump_json = {
            "version": "2.0",
            "dump_time": "1749451765349986",
            "output": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "dim_range": [],
                    "offset": "3",
                }
            ],
            "input": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["10240", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 0,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 1,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["1"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 2,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 5,
                    "input_type": 7,
                },
            ],
            "buffer": [],
            "op_name": "",
            "attr": [],
            "space": [{"type": 0, "data": "", "size": "10"}],
            "dfx_message": "[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n",
        }
        self.common_mock(mocker, dump_json)
        with open(dump_file, "wb") as f:
            f.write(struct.pack("Q", 100))
            f.write(struct.pack("Q", 10))
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        # 头长度超界的根因是数据非法(4)，外层须透传内层错误码而非包装成读文件失败(5)
        self.assertIn(
            capsys.readouterr().out, "Error Detail: [4] invalid or corrupted dump file"
        )

    def test_parser_dump_file_use_size_gt_file_size_error(self, mocker, capsys):
        dump_json = {
            "version": "2.0",
            "dump_time": "1749451765349986",
            "output": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2", "2048"]},
                    "data": "",
                    "size": "100000",
                    "sub_format": 0,
                    "address": "0",
                    "dim_range": [],
                    "offset": "3",
                }
            ],
            "input": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["10240", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 0,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 1,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["1"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 2,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 5,
                    "input_type": 7,
                },
            ],
            "buffer": [],
            "op_name": "",
            "attr": [],
            "space": [{"type": 0, "data": "", "size": "10"}],
            "dfx_message": "[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n",
        }
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        self.assertIn(
            capsys.readouterr().out,
            "The size of exception_info.2.1.20250609144925349 is invalid, please check the dump file",
        )

    def test_parser_dump_file_not_dump_file_error(self):
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        DumpDataParser("test.bin", info).parse()
        self.assertEqual(info.dump_info, "")

    def test_parser_dump_file_not_dump_dir_error(self):
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        info.node_name = "test"
        with open("test.bin", "wb") as f:
            f.write(struct.pack("Q", 10))
        DumpDataParser(self.temp, info).parse()
        self.assertEqual(info.dump_info, "")

    def test_parser_dump_file_not_dtype(self, mocker):
        dump_json = {
            "version": "2.0",
            "dump_time": "1749451765349986",
            "output": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "dim_range": [],
                    "offset": "3",
                }
            ],
            "input": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["10240", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 0,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 1,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["1"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 2,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 5,
                    "input_type": 7,
                },
            ],
            "buffer": [],
            "op_name": "",
            "attr": [],
            "space": [{"type": 0, "data": "", "size": "10"}],
            "dfx_message": "[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n",
        }
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        DumpDataParser(dump_file, info).parse()
        # 未指定json文件时无dtype回退来源，data_type=0映射为undefined
        self.assertIn(info.dump_info, "shape: () size: 10 dtype: undefined")
        self.assertIn(info.dump_info, "If dtype is float32")
        self.assertIn(info.dump_info, "If dtype is float16")
        self.assertIn(info.dump_info, "If dtype is bfloat16")
        self.assertIn(info.dump_info, "If dtype is int32")
        self.assertIn(info.dump_info, "If dtype is int64")

    def test_parser_dump_file_not_output(self, mocker):
        dump_json = {
            "version": "2.0",
            "dump_time": "1749451765349986",
            "input": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["10240", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 0,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 1,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["1"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 2,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 5,
                    "input_type": 7,
                },
            ],
            "buffer": [],
            "op_name": "",
            "attr": [],
            "space": [{"type": 0, "data": "", "size": "10"}],
            "dfx_message": "[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n",
        }
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        DumpDataParser(dump_file, info).parse()
        self.assertNotIn(info.dump_info, "exception_info.2.1.20250609144925349.output")

    def test_parser_dump_file_dtype_not_in_map(self, mocker):
        """需求1: dtype枚举值不在映射表中且json无该dtype时，直接记录枚举值"""
        dump_json = self._make_dump_json(output_data_type=88, output_size="8")
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        # 不指定json文件，无dtype回退来源
        DumpDataParser(dump_file, info).parse()
        self.assertIn(info.dump_info, "dtype: 88")
        self.assertIn(
            info.dump_info, "exception_info.2.1.20250609144925349.output.0.88.bin"
        )
        self.assertNotIn(info.dump_info, "dtype: unknown")

    def test_parser_dump_file_dtype_not_in_map_json_first(self, mocker):
        """需求1: 枚举值不在映射表但json中有dtype时，以json的dtype为准"""
        dump_json = self._make_dump_json(
            output_data_type=88, output_size="8", output_dim=["2"]
        )
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json"))
        DumpDataParser(dump_file, info).parse()
        self.assertIn(
            info.dump_info, "exception_info.2.1.20250609144925349.output.0.float32.npy"
        )
        self.assertNotIn(info.dump_info, "dtype: 88")

    def test_parser_dump_file_numpy_dtype_saved_as_npy(self, mocker):
        """需求2: numpy支持的dtype直接保存为npy，可按dtype和shape回读"""
        dump_json = self._make_dump_json(
            output_data_type=1, output_size="8", output_dim=["2"]
        )
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json"))
        parser = DumpDataParser(dump_file, info)
        parser.parse()
        self.assertIn(
            info.dump_info, "exception_info.2.1.20250609144925349.output.0.float32.npy"
        )
        npy_files = [
            f for f in parser.get_bin_data() if f.endswith("output.0.float32.npy")
        ]
        self.assertEqual(len(npy_files), 1)
        array = np.load(npy_files[0])
        self.assertEqual(str(array.dtype), "float32")
        self.assertEqual(array.shape, (2,))

    def test_parser_dump_file_non_numpy_dtype_keep_bin(self):
        """需求2: numpy不支持的dtype仍保存为bin，且保留带真实dtype名的提示"""
        info = AicErrorInfo()
        parser = DumpDataParser(dump_file, info)
        res = getattr(parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 33,
                        "shape": {"dim": ["4"]},
                        "size": "4",
                        "data": b"\x01\x02\x03\x04",
                    }
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        assert parser.get_bin_data()[0].endswith("input.0.hifloat8.bin")
        self.assertIn(res, "If dtype is hifloat8, summary is: ")

    def test_parser_dump_file_by_mapped_name(self, mocker):
        """超长场景: dump目录下只有随机名文件和mapping.csv，按原始data_name反查映射名完成解析"""
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_json = self._make_dump_json(
            output_data_type=1, output_size="8", output_dim=["2"]
        )
        # 解析so会在dump文件同级生成json，此处在调用时写入，避免提前污染待匹配目录
        mocker.patch("ctypes.CDLL", return_value=SelflibWriteJson(dump_json))
        create_dump_file(str(dump_dir.joinpath(rename)), 10, 200)
        dump_dir.joinpath(Constant.MAPPING_CSV_FILE).write_text(
            f"{rename},{data_name}\n", encoding="utf-8"
        )
        info = AicErrorInfo()
        info.node_name = "GatherV2"  # L1场景下node_name是plog中的短名，与映射key不同
        info.data_name = data_name
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json"))
        parser = DumpDataParser(str(dump_dir), info)
        parser.parse()
        # 命中随机名文件，且mapping.csv没有被当成dump文件解析
        self.assertEqual(info.dump_file, [str(dump_dir.joinpath(rename))])
        self.assertIn(info.dump_info, f"{rename}.output.0.float32.npy")

    def test_parser_dump_file_oversize_result_renamed(self, mocker):
        """超长场景: 解析结果文件名超过NAME_MAX时重命名为随机数字串，并记录到同级mapping.csv"""
        dump_json = self._make_dump_json(
            output_data_type=1, output_size="8", output_dim=["2"]
        )
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.kernel_name = "a" * 260  # 拼装后的结果文件名必然超长
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json"))
        parser = DumpDataParser(dump_file, info)
        parser.parse()
        npy_files = [f for f in parser.get_bin_data() if f.endswith(".npy")]
        self.assertEqual(len(npy_files), 1)
        file_name = os.path.basename(npy_files[0])
        # 落盘成功，文件名为随机数字串 + 原后缀
        assert len(file_name) <= Constant.MAX_FILE_NAME_LEN
        assert file_name[: -len(".npy")].isdigit()
        self.assertEqual(os.path.isfile(npy_files[0]), True)
        self.assertEqual(str(np.load(npy_files[0]).dtype), "float32")
        # mapping.csv中记录了 {映射后},{映射前}
        mapping_text = self.temp.joinpath(Constant.MAPPING_CSV_FILE).read_text(
            encoding="utf-8"
        )
        self.assertIn(
            mapping_text, f"{file_name},{info.kernel_name}.output.0.float32.npy"
        )

    def test_parser_dump_file_bfloat16_dtype_success(self, mocker):
        dump_json = {
            "version": "2.0",
            "dump_time": "1749451765349986",
            "output": [
                {
                    "data_type": 27,
                    "format": 0,
                    "shape": {"dim": ["2", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "dim_range": [],
                    "offset": "3",
                }
            ],
            "input": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["10240", "2048"]},
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 0,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 1,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["1"]},
                    "data": "",
                    "size": "32",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 2,
                    "input_type": 2,
                },
                {
                    "data_type": 0,
                    "format": 0,
                    "data": "",
                    "size": "10",
                    "sub_format": 0,
                    "address": "0",
                    "offset": "0",
                    "arg_index": 5,
                    "input_type": 7,
                },
            ],
            "buffer": [],
            "op_name": "",
            "attr": [],
            "space": [{"type": 0, "data": "", "size": "10"}],
            "dfx_message": "[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n",
        }
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        # info.result_info
        self.assertIn(
            info.dump_info, "exception_info.2.1.20250609144925349.output.0.bfloat16.bin"
        )
