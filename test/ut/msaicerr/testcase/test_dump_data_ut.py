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
import warnings
import importlib.util

from conftest import MSAICERR_PATH, RES_PATH, CommonAssert
import os
import sys
import pytest
import numpy as np
from unittest.mock import Mock

sys.path.append(MSAICERR_PATH)
from ms_interface.constant import Constant
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.utils import AicErrException
from ms_interface.dump_data_parser import DumpDataParser, BigDumpDataParser


dump_file = "exception_info.2.1.20250609144925349"
bin_file = "aclnnAbs_0_L0.AbsAicore.2.20260202152928444.input.0.bin"


def create_dump_file(file_name, header_length, body_length):
    with open(file_name, "wb") as f:
        f.write(struct.pack("Q", header_length))
        f.write(bytearray(range(header_length)))
        for _ in range(body_length // 256 + 1):
            f.write(bytearray(range(256)))


class Selflib:
    @staticmethod
    def ParseDumpProtoToJson(_data_ptr, _data_size, _path_ptr):
        return 0


class Selfliberr:
    @staticmethod
    def ParseDumpProtoToJson(_data_ptr, _data_size, _path_ptr):
        return 1


class SelflibCheckPath:
    @staticmethod
    def ParseDumpProtoToJson(_data_ptr, _data_size, path_ptr):
        return len(path_ptr) != 0


@pytest.mark.usefixtures("change_test_dir")
class TestUtilsMethods(CommonAssert):
    # fixture/setup_method 中赋值，此处声明以明确实例属性集合
    debug_info = None
    temp = None

    @staticmethod
    def common_mock(mocker, dump_json):
        # mock通用方法
        mocker.patch("ctypes.CDLL", return_value=Selflib())
        with open(f"{dump_file}.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(dump_json))

    def test_big_dump_parser(self, mocker):
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
        big_dump_parser = BigDumpDataParser(dump_file)
        dump_json_data = big_dump_parser.parse()
        self.assertEqual(dump_json_data.get("output")[0].get("data_type"), 0)
        self.assertEqual(
            dump_json_data.get("input")[0].get("shape").get("dim"), ["10240", "2048"]
        )
        self.assertEqual(dump_json_data.get("input")[0].get("size"), "10")
        self.assertEqual(dump_json_data.get("input")[0].get("input_type"), 2)
        self.assertIn(
            dump_json_data.get("dfx_message"), "[AIC_INFO] args(0 to 20) after"
        )

    def test_big_dump_parser_error(self, mocker, capsys):
        big_dump_parser = BigDumpDataParser(dump_file)
        mocker.patch.object(big_dump_parser, "check_argument_valid")
        mocker.patch.object(big_dump_parser, "_read_header_length")
        mocker.patch.object(big_dump_parser, "_parse_binary_to_json_data")
        with pytest.raises(AicErrException) as exc_info:
            big_dump_parser.parse()
        self.assertEqual(str(exc_info.value), "5")
        self.assertIn(
            capsys.readouterr().out,
            "No such file or directory: 'exception_info.2.1.20250609144925349'",
        )

    def test_check_argument_valid_file_size_lt_uint64_size_err(self):
        big_dump_parser = BigDumpDataParser(dump_file)
        with open(dump_file, "wb") as f:
            f.write(struct.pack("Q", 10))
        with pytest.raises(AicErrException) as exc_info:
            big_dump_parser.check_argument_valid()
        self.assertEqual(str(exc_info.value), "4")

    def test_check_argument_valid_file_get_size_failed(self, mocker):
        big_dump_parser = BigDumpDataParser(dump_file)
        mocker.patch("os.path.getsize", effect=IOError("test"))
        with pytest.raises(AicErrException) as exc_info:
            big_dump_parser.check_argument_valid()
        self.assertEqual(str(exc_info.value), "2")

    def test_parse_dump_to_json_load_so_failed(self):
        big_dump_parser = BigDumpDataParser(dump_file)
        create_dump_file(dump_file, 10, 200)
        with pytest.raises(AicErrException) as exc_info:
            getattr(big_dump_parser, "_parse_dump_to_json")()
        self.assertEqual(str(exc_info.value), "3")

    def test_parse_dump_to_json_check_path(self, mocker):
        big_dump_parser = BigDumpDataParser(dump_file)
        mocker.patch("ctypes.CDLL", return_value=SelflibCheckPath())
        create_dump_file(dump_file, 10, 200)
        with pytest.raises(AicErrException) as exc_info:
            getattr(big_dump_parser, "_parse_dump_to_json")()
        self.assertEqual(str(exc_info.value), "3")

    def test_parse_dump_to_json_load_func_failed(self, mocker):
        big_dump_parser = BigDumpDataParser(dump_file)
        mocker.patch("ctypes.CDLL", return_value=Selfliberr())
        create_dump_file(dump_file, 10, 200)
        with pytest.raises(AicErrException) as exc_info:
            getattr(big_dump_parser, "_parse_dump_to_json")()
        self.assertEqual(str(exc_info.value), "3")

    def test_parse_binary_to_json_data_use_gt_file_size(self, mocker):
        dump_json = {
            "version": "2.0",
            "dump_time": "1749451765349986",
            "output": [
                {
                    "data_type": 0,
                    "format": 0,
                    "shape": {"dim": ["2", "2048"]},
                    "data": "",
                    "size": "10000",
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
        big_dump_parser = BigDumpDataParser(dump_file)
        with pytest.raises(AicErrException) as exc_info:
            big_dump_parser.parse()
        self.assertEqual(str(exc_info.value), "5")

    def test_dump_data_parser(self, mocker):
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
        # the payload is 10 bytes, not a whole number of float32 elements, keep the raw bin
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
        self.assertIn(
            dump_data_parser.get_bin_data(),
            "exception_info.2.1.20250609144925349.input.1.int64.npy",
        )
        self.assertIn(
            dump_data_parser.get_workspace_data(),
            "exception_info.2.1.20250609144925349.workspace.0.int8.npy",
        )
        self.assertIn(dump_data_parser.get_dfx_message(), "[AIC_INFO] args(20 to 39)")

    def test_dump_data_parser_other_file(self, mocker):
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        with open("text.bin", "wb") as f:
            f.write(struct.pack("Q", 10))
        dump_data_parser = DumpDataParser("test.bin", info)
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="")
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [])

    def test_dump_data_parser_other_path(self, tmp_path, mocker):
        info = AicErrorInfo()
        info.json_file = str(
            RES_PATH.joinpath("ori_data/collect_json/test.json")
        )  # 指定json文件路径
        dump_data_parser = DumpDataParser(tmp_path, info)
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="")
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [])

    def test_parse_dump_data_error(self, mocker, capsys):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        mocker.patch.object(BigDumpDataParser, "parse", return_value={})
        mocker.patch.object(dump_data_parser, "_get_json_dtypes", return_value={})
        mocker.patch.object(
            dump_data_parser, "_save_data_to_bin_file", side_effect=ValueError("test")
        )
        dump_data_parser.parse_dump_data(dump_file)
        self.assertIn(capsys.readouterr().out, "Error Detail: test")

    def test_summary_tensor_without_dtype_bfloat16(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_summary_tensor_without_dtype")(
            "text.bin", "bfloat16"
        )
        self.assertIn(res, "Can not read with dtype bfloat16")

    def test_summary_tensor_empty_array(self, mocker):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        empty_arr = np.array([], dtype=np.float32)
        mocker.patch.object(np, "fromfile", return_value=empty_arr)
        res = getattr(dump_data_parser, "_summary_tensor_without_dtype")(
            "text.bin", "float32"
        )
        self.assertIn(res, "Max: N/A, Min: N/A, Mean: N/A, Std: N/A")

    def test_check_tensor_data_type_error(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_check_tensor_data")(
            "input", 1, np.array([1, 2]), "bfloat112"
        )
        self.assertIn(res, "Can not read with dtype bfloat112!")

    def test_check_input_nonbin_with_dtype(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo(), "float16")
        dump_data_parser.parse()

    def test_convert_bin_check_input(self):
        dump_data_parser = DumpDataParser(bin_file, AicErrorInfo())
        res = dump_data_parser.convert_bin_file_to_npy()
        self.assertIn(res, "Need to specify the dtype when convert a bin file.")

    def test_convert_bin_check_input_dtype_error(self):
        dump_data_parser = DumpDataParser(bin_file, AicErrorInfo(), "fint8")
        res = dump_data_parser.convert_bin_file_to_npy()
        self.assertIn(res, "Invalid dest_dtype: fint8")

    def test_check_tensor_data_type_inf_error(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_check_tensor_data")(
            "input", 1, np.array([np.inf, 2]), "float16"
        )
        print(res)
        self.assertIn(res, "input[1] NaN/INF. Input data invalid. Please check!")

    def test_check_tensor_data_type_gt_max_error(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_check_tensor_data")(
            "input", 1, np.array([59000, 2]), "float16"
        )
        self.assertIn(
            res, "input[1] max 59000 or min 2. Input data maybe invalid. Please check!"
        )

    def test_save_data_to_bin_file_not_parse_type(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {"input": []}, "output", {}, dump_file
        )
        self.assertEqual(res, "")

    def test_save_data_to_bin_file_parse_type_not_dtype(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        save_to_bin = getattr(dump_data_parser, "_save_data_to_bin_file")
        tensor_data = {
            "input": [
                {
                    "shape": {"dim": ["1", "2"]},
                    "size": "2",
                    "data": struct.pack("Q", 10),
                }
            ]
        }
        res = save_to_bin(tensor_data, "input", {"input": {}}, dump_file)
        # data_type is absent, it defaults to enum 0 which maps to undefined
        self.assertIn(res, "shape: (1, 2) size: 2 dtype: undefined")

    def test_save_data_to_bin_file_dtype_not_in_map(self):
        """the dtype enum is not in the map, the raw enum value is recorded"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 99,
                        "shape": {"dim": ["8"]},
                        "size": "8",
                        "data": struct.pack("Q", 10),
                    }
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertIn(res, "shape: (8,) size: 8 dtype: 99")
        self.assertIn(res, "input.0.99.bin")

    def test_save_data_to_bin_file_numpy_dtype_saved_as_npy(self):
        """numpy supported dtype is saved as npy with the right dtype and shape"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(6, dtype=np.float32).tobytes()
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 1,
                        "shape": {"dim": ["2", "3"]},
                        "size": "24",
                        "data": raw,
                    }
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertIn(res, "shape: (2, 3) size: 24 dtype: float32")
        npy_file = dump_data_parser.get_bin_data()[0]
        assert npy_file.endswith("input.0.float32.npy")
        array = np.load(npy_file)
        self.assertEqual(str(array.dtype), "float32")
        self.assertEqual(array.shape, (2, 3))

    def test_save_data_to_bin_file_custom_dump_isolated(self):
        """自定义dump的张量写入custom_dump子目录，且不并入bin/workspace列表，
        避免与原始报错dump的解析产物互相覆盖、污染单算子复跑"""
        custom_file = dump_file + ".custom.1726159207469500"
        dump_data_parser = DumpDataParser(
            dump_file, AicErrorInfo(), custom_dump_files=[custom_file]
        )
        # 真实场景下原始dump先解析并设置kernel_name，自定义dump复用同一名字
        dump_data_parser.info.kernel_name = "AbsAicore"
        raw = np.arange(6, dtype=np.float32).tobytes()
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 1,
                        "shape": {"dim": ["2", "3"]},
                        "size": "24",
                        "data": raw,
                    }
                ]
            },
            "input",
            {"input": {}},
            custom_file,
        )
        self.assertIn(res, "shape: (2, 3) size: 24 dtype: float32")
        self.assertEqual(dump_data_parser.get_bin_data(), [])
        self.assertEqual(dump_data_parser.get_workspace_data(), [])
        self.assertEqual(
            os.path.isfile(
                os.path.join("custom_dump", "AbsAicore.input.0.float32.npy")
            ),
            True,
        )
        ws_res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "space": [
                    {
                        "data_type": 1,
                        "shape": {"dim": ["4"]},
                        "size": "16",
                        "data": np.arange(4, dtype=np.float32).tobytes(),
                    }
                ]
            },
            "space",
            {},
            custom_file,
        )
        self.assertIn(ws_res, "shape: (4,) size: 16 dtype: int8")
        self.assertEqual(dump_data_parser.get_workspace_data(), [])
        self.assertEqual(
            os.path.isfile(
                os.path.join("custom_dump", "AbsAicore.workspace.0.int8.npy")
            ),
            True,
        )

    def test_save_dfx_message_keeps_original_dump(self):
        """dfx_message固定取自原始报错dump文件，自定义dump的头部信息不覆盖它"""
        custom_file = dump_file + ".custom.1726159207469500"
        dump_data_parser = DumpDataParser(
            dump_file, AicErrorInfo(), custom_dump_files=[custom_file]
        )
        save_dfx = getattr(dump_data_parser, "_save_dfx_message")
        save_dfx({"dfx_message": "origin err msg"}, dump_file)
        save_dfx({"dfx_message": "custom msg"}, custom_file)
        self.assertEqual(dump_data_parser.get_dfx_message(), "origin err msg")

    def test_save_data_to_bin_file_user_tag_not_inline(self):
        """user_tag不再内联到shape行展示，_save_data_to_bin_file不输出任何user tag"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(6, dtype=np.float32).tobytes()
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 1,
                        "shape": {"dim": ["2", "3"]},
                        "size": "24",
                        "data": raw,
                    }
                ],
                "attr": [{"name": "user_tag", "value": "component=demo;stage=forward"}],
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertIn(res, "shape: (2, 3) size: 24 dtype: float32\n")
        self.assertNotIn(res, "user tag")

    def test_save_data_to_bin_file_no_inline_user_tag_multi_items(self):
        """多tensor场景下每个tensor行均不再内联user tag"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(2, dtype=np.float32).tobytes()
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {"data_type": 1, "shape": {"dim": ["2"]}, "size": "8", "data": raw},
                    {"data_type": 1, "shape": {"dim": ["2"]}, "size": "8", "data": raw},
                ],
                "attr": [{"name": "user_tag", "value": "my_tag"}],
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertNotIn(res, "user tag")
        self.assertEqual(res.count("shape: (2,) size: 8 dtype: float32"), 2)

    def test_save_data_to_bin_file_other_attr_not_shown(self):
        """非user_tag的attr不展示，且不影响原有字段"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(2, dtype=np.float32).tobytes()
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {"data_type": 1, "shape": {"dim": ["2"]}, "size": "8", "data": raw}
                ],
                "attr": [{"name": "other_attr", "value": "other_value"}],
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertIn(res, "shape: (2,) size: 8 dtype: float32\n")
        self.assertNotIn(res, "user tag")
        self.assertNotIn(res, "other_value")

    def test_save_data_to_bin_file_without_user_tag(self):
        """头部无attr时保持原有展示，不输出user tag占位"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(2, dtype=np.float32).tobytes()
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {"data_type": 1, "shape": {"dim": ["2"]}, "size": "8", "data": raw}
                ],
                "attr": [],
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertIn(res, "shape: (2,) size: 8 dtype: float32\n")
        self.assertNotIn(res, "user tag")

    def test_get_user_tag_invalid_attr(self):
        """attr字段异常(None/非dict/空value)时不抛异常，按无user tag处理"""
        get_user_tag = getattr(
            DumpDataParser(dump_file, AicErrorInfo()), "_get_user_tag"
        )
        self.assertEqual(get_user_tag({"attr": None}), "")
        self.assertEqual(get_user_tag({}), "")
        self.assertEqual(get_user_tag({"attr": ["user_tag"]}), "")
        self.assertEqual(get_user_tag({"attr": [{"name": "user_tag"}]}), "")

    def test_get_user_tag_data_invalid_sanitized(self):
        """user tag 含"data invalid"判据子串时被剔除，不污染退出码判定"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        get_user_tag = getattr(dump_data_parser, "_get_user_tag")
        sanitized = get_user_tag(
            {"attr": [{"name": "user_tag", "value": "case=data invalid check"}]}
        )
        self.assertEqual(sanitized, "case=data_invalid check")
        self.assertNotIn(sanitized, "data invalid")

    def test_parse_dump_data_data_invalid_user_tag_not_in_dump(self, mocker):
        """user tag含"data invalid"时，parse_dump_data输出被清洗后的user tag行，不污染结论"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        mocker.patch.object(
            BigDumpDataParser,
            "parse",
            return_value={
                "attr": [{"name": "user_tag", "value": "case=data invalid check"}]
            },
        )
        mocker.patch.object(dump_data_parser, "_get_json_dtypes", return_value={})
        mocker.patch.object(
            dump_data_parser,
            "_save_data_to_bin_file",
            side_effect=["shape: (2,) size: 8 dtype: float32\n", "", ""],
        )
        mocker.patch.object(dump_data_parser, "_save_dfx_message")
        res = dump_data_parser.parse_dump_data(dump_file)
        self.assertIn(res, "user tag: case=data_invalid check\n")
        self.assertNotIn(res, "data invalid")

    def test_parse_dump_data_user_tag_extra_line(self, mocker):
        """user tag存在时在result_info最前面新增一行，整个文件仅一行"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        mocker.patch.object(
            BigDumpDataParser,
            "parse",
            return_value={"attr": [{"name": "user_tag", "value": "tag14"}]},
        )
        mocker.patch.object(dump_data_parser, "_get_json_dtypes", return_value={})
        mocker.patch.object(
            dump_data_parser,
            "_save_data_to_bin_file",
            side_effect=["shape: (2, 3) size: 24 dtype: float32\n", "", ""],
        )
        mocker.patch.object(dump_data_parser, "_save_dfx_message")
        res = dump_data_parser.parse_dump_data(dump_file)
        self.assertEqual(
            res, "user tag: tag14\nshape: (2, 3) size: 24 dtype: float32\n"
        )

    def test_parse_dump_data_without_user_tag_no_extra_line(self, mocker):
        """无user_tag时不输出该行、不占位"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        mocker.patch.object(BigDumpDataParser, "parse", return_value={"attr": []})
        mocker.patch.object(dump_data_parser, "_get_json_dtypes", return_value={})
        mocker.patch.object(
            dump_data_parser,
            "_save_data_to_bin_file",
            side_effect=["shape: (2,) size: 8 dtype: float32\n", "", ""],
        )
        mocker.patch.object(dump_data_parser, "_save_dfx_message")
        res = dump_data_parser.parse_dump_data(dump_file)
        self.assertEqual(res, "shape: (2,) size: 8 dtype: float32\n")
        self.assertNotIn(res, "user tag")

    def test_save_data_to_bin_file_json_dtype_fallback(self):
        """data_type为0(undefined)时回退到json中的dtype"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(4, dtype=np.int64).tobytes()
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {"data_type": 0, "shape": {"dim": ["4"]}, "size": "32", "data": raw}
                ]
            },
            "input",
            {"input": {0: "int64"}},
            dump_file,
        )
        self.assertIn(res, "dtype: int64")
        assert dump_data_parser.get_bin_data()[0].endswith("input.0.int64.npy")

    def test_save_data_to_bin_file_size_not_aligned_keep_bin(self):
        """字节数不是itemsize整数倍时无法按该dtype解析，保留原始bin"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 1,
                        "shape": {"dim": ["1"]},
                        "size": "3",
                        "data": b"\x01\x02\x03",
                    }
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertIn(res, "dtype: float32")
        assert dump_data_parser.get_bin_data()[0].endswith("input.0.float32.bin")

    def test_save_data_to_bin_file_non_numpy_dtype_keep_bin(self):
        """numpy不支持的dtype(int4)保存为bin，先给出真实dtype的提示再按常用dtype猜测"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 28,
                        "shape": {"dim": ["8"]},
                        "size": "4",
                        "data": b"\x01\x02\x03\x04",
                    }
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertIn(res, "dtype: int4")
        self.assertIn(res, "If dtype is int4, summary is: ")
        self.assertIn(res, "If dtype is float32")
        assert dump_data_parser.get_bin_data()[0].endswith("input.0.int4.bin")

    def test_save_data_to_bin_file_non_numpy_dtype_hint_when_unreadable(self, mocker):
        """numpy无法解析该dtype时，提示中必须带真实dtype名，用户据此安装第三方库"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        # 固定np.dtype对int4抛异常，不依赖环境是否装了注册int4的第三方库
        real_dtype = np.dtype
        mocker.patch(
            "numpy.dtype",
            side_effect=lambda x: (
                (_ for _ in ()).throw(TypeError()) if x == "int4" else real_dtype(x)
            ),
        )
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 28,
                        "shape": {"dim": ["8"]},
                        "size": "4",
                        "data": b"\x01\x02\x03\x04",
                    }
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertIn(
            res, "If dtype is int4, summary is: Can not read with dtype int4!"
        )

    def test_save_data_to_bin_file_undefined_no_named_hint(self):
        """undefined并非真实dtype，不输出带undefined的提示，只做常用dtype猜测"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 0,
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
        self.assertNotIn(res, "Can not read with dtype undefined")
        self.assertIn(res, "If dtype is float32")

    def test_save_data_to_bin_file_not_aligned_no_duplicate_summary(self):
        """字节未对齐但numpy认识该dtype时，只按该dtype给一行summary，不重复猜测"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 1,
                        "shape": {"dim": ["1"]},
                        "size": "3",
                        "data": b"\x01\x02\x03",
                    }
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        self.assertEqual(res.count("If dtype is float32"), 1)
        self.assertNotIn(res, "If dtype is int64")

    def test_save_data_to_bin_file_space_multi_items(self):
        """space有多个item时全部按workspace的int8 npy落盘"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        item = {"size": "4", "data": b"\x01\x02\x03\x04"}
        res = getattr(dump_data_parser, "_save_data_to_bin_file")(
            {"space": [dict(item), dict(item)]}, "space", {"input": {}}, dump_file
        )
        self.assertIn(res, "dtype: int8")
        workspaces = dump_data_parser.get_workspace_data()
        self.assertEqual(len(workspaces), 2)
        assert workspaces[0].endswith("workspace.0.int8.npy")
        assert workspaces[1].endswith("workspace.1.int8.npy")
        self.assertEqual(dump_data_parser.get_bin_data(), [])

    def test_save_data_to_bin_file_bool_and_complex(self):
        """bool与complex同为numpy支持的dtype，落盘为npy且可正常load"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 11,
                        "shape": {"dim": ["2"]},
                        "size": "2",
                        "data": np.array([True, False]).tobytes(),
                    },
                    {
                        "data_type": 16,
                        "shape": {"dim": ["1"]},
                        "size": "8",
                        "data": np.array([1 + 2j], dtype=np.complex64).tobytes(),
                    },
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        bin_files = dump_data_parser.get_bin_data()
        bool_file, complex_file = bin_files[0], bin_files[1]
        assert bool_file.endswith("input.0.bool.npy")
        assert complex_file.endswith("input.1.complex64.npy")
        self.assertEqual(np.load(bool_file).tolist(), [True, False])
        self.assertEqual(np.load(complex_file).tolist(), [1 + 2j])

    def test_save_data_to_bin_file_shape_mismatch_keeps_flat(self):
        """元素个数与shape不一致时不做reshape，保持一维"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(4, dtype=np.float32).tobytes()
        getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 1,
                        "shape": {"dim": ["100", "100"]},
                        "size": "16",
                        "data": raw,
                    }
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        array = np.load(dump_data_parser.get_bin_data()[0])
        self.assertEqual(array.shape, (4,))

    def test_to_numpy_dtype(self):
        """numpy原生dtype可解析，非numpy dtype与空值返回None"""
        self.assertEqual(
            getattr(DumpDataParser, "_to_numpy_dtype")("float32"), np.dtype("float32")
        )
        self.assertEqual(getattr(DumpDataParser, "_to_numpy_dtype")("int4"), None)
        self.assertEqual(getattr(DumpDataParser, "_to_numpy_dtype")("string"), None)
        self.assertEqual(getattr(DumpDataParser, "_to_numpy_dtype")("99"), None)
        self.assertEqual(getattr(DumpDataParser, "_to_numpy_dtype")(None), None)
        self.assertEqual(getattr(DumpDataParser, "_to_numpy_dtype")(""), None)

    def test_to_numpy_dtype_bfloat16_without_ext(self):
        """bfloat16ext缺失(或装了但numpy仍不认识)时，bfloat16按非numpy dtype处理，落盘为bin"""
        if importlib.util.find_spec("bfloat16ext") is not None:
            pytest.skip("bfloat16ext已安装，该分支不适用")
        self.assertEqual(getattr(DumpDataParser, "_to_numpy_dtype")("bfloat16"), None)
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        getattr(dump_data_parser, "_save_data_to_bin_file")(
            {
                "input": [
                    {
                        "data_type": 27,
                        "shape": {"dim": ["2"]},
                        "size": "4",
                        "data": b"\x01\x02\x03\x04",
                    }
                ]
            },
            "input",
            {"input": {}},
            dump_file,
        )
        assert dump_data_parser.get_bin_data()[0].endswith("input.0.bfloat16.bin")

    def test_to_numpy_dtype_bfloat16_with_ext(self, mocker):
        """bfloat16ext可用时bfloat16视为numpy支持的dtype"""
        bf16_dtype = np.dtype("int16")
        mocker.patch.dict(sys.modules, {"bfloat16ext": Mock()})
        # 桩掉np.dtype模拟扩展注册后numpy可识别bfloat16
        mocker.patch("numpy.dtype", return_value=bf16_dtype)
        self.assertEqual(
            getattr(DumpDataParser, "_to_numpy_dtype")("bfloat16"), bf16_dtype
        )

    def test_to_numpy_dtype_ext_imported_but_dtype_unregistered(self, mocker):
        """bfloat16ext导入成功但numpy仍未注册该dtype时安全返回None"""
        mocker.patch.dict(sys.modules, {"bfloat16ext": Mock()})
        mocker.patch("numpy.dtype", side_effect=TypeError("not understood"))
        self.assertEqual(getattr(DumpDataParser, "_to_numpy_dtype")("bfloat16"), None)

    def test_get_item_dtype(self):
        """dtype取值优先级: 枚举映射 > json > 原始枚举值"""
        get_item_dtype = getattr(DumpDataParser, "_get_item_dtype")
        self.assertEqual(get_item_dtype({"data_type": 2}, "input", {}, 0), "float16")
        # workspace固定int8
        self.assertEqual(get_item_dtype({}, "workspace", {}, 0), "int8")
        # 枚举不在映射表中，直接记录枚举值
        self.assertEqual(
            get_item_dtype({"data_type": 77}, "input", {"input": {}}, 0), "77"
        )
        # 枚举不在映射表但json有dtype，优先json
        self.assertEqual(
            get_item_dtype({"data_type": 77}, "input", {"input": {0: "float16"}}, 0),
            "float16",
        )
        # undefined不作为有效dtype，回退json
        self.assertEqual(
            get_item_dtype({"data_type": 0}, "input", {"input": {0: "int32"}}, 0),
            "int32",
        )
        self.assertEqual(
            get_item_dtype({"data_type": 0}, "input", {"input": {}}, 0), "undefined"
        )

    def test_build_typed_array(self):
        """字节数据按dtype视图化并reshape，无法解析时退化为int8"""
        raw = np.arange(6, dtype=np.float32).tobytes()
        array, np_dtype = getattr(DumpDataParser, "_build_typed_array")(
            raw, "float32", [2, 3]
        )
        self.assertEqual(np_dtype, np.dtype("float32"))
        self.assertEqual(array.shape, (2, 3))
        # 非numpy dtype
        array, np_dtype = getattr(DumpDataParser, "_build_typed_array")(
            raw, "int4", [6]
        )
        self.assertEqual(np_dtype, None)
        self.assertEqual(str(array.dtype), "int8")
        # 字节数未对齐
        array, np_dtype = getattr(DumpDataParser, "_build_typed_array")(
            b"\x01\x02\x03", "float32", [1]
        )
        self.assertEqual(np_dtype, None)
        # data为None时按空数组处理
        array, np_dtype = getattr(DumpDataParser, "_build_typed_array")(
            None, "float32", [1]
        )
        self.assertEqual(array.size, 0)

    def test_summary_tensor_array(self):
        """已知dtype的数组直接由内存计算summary"""
        res = getattr(DumpDataParser, "_summary_tensor_array")(
            np.array([1, 3], dtype=np.int32), "int32"
        )
        self.assertIn(
            res, "If dtype is int32, summary is: Max: 3, Min: 1, Mean: 2.0, Std: 1.0"
        )

    def test_summary_tensor_array_empty(self):
        res = getattr(DumpDataParser, "_summary_tensor_array")(
            np.array([], dtype=np.float32), "float32"
        )
        self.assertIn(res, "Max: N/A, Min: N/A, Mean: N/A, Std: N/A")

    def test_summary_tensor_array_complex_no_warning(self):
        """complex数组按complex128累加，不产生丢弃虚部的告警"""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            res = getattr(DumpDataParser, "_summary_tensor_array")(
                np.array([1 + 2j, 3 + 4j], dtype=np.complex64), "complex64"
            )
        self.assertIn(res, "If dtype is complex64")

    def test_summary_tensor_array_error(self, mocker):
        mocker.patch("numpy.mean", side_effect=ValueError("test"))
        res = getattr(DumpDataParser, "_summary_tensor_array")(
            np.array([1, 2], dtype=np.int32), "int32"
        )
        self.assertIn(res, "Can not read with dtype int32!")

    def test_save_data_to_bin_file_parse_type_error(self, mocker):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        mocker.patch.object(
            dump_data_parser,
            "_summary_tensor_without_dtype",
            side_effect=ValueError("test"),
        )
        with pytest.raises(AicErrException) as exc_info:
            save_to_bin = getattr(dump_data_parser, "_save_data_to_bin_file")
            tensor_data = {
                "input": [
                    {
                        "shape": {"dim": ["1", "2"]},
                        "size": "2",
                        "data": struct.pack("Q", 10),
                    }
                ]
            }
            save_to_bin(tensor_data, "input", {"input": {}}, dump_file)
        self.assertEqual(str(exc_info.value), "4")

    def test_build_dst_file_name_normal_len(self):
        """不超长的解析结果文件名原样返回，不生成mapping.csv"""
        info = AicErrorInfo()
        info.kernel_name = "GatherV2"
        dump_data_parser = DumpDataParser(str(self.temp), info)
        build_dst_file_name = getattr(dump_data_parser, "_build_dst_file_name")
        res = build_dst_file_name(
            str(self.temp), "input", 0, "float32", np.dtype("float32")
        )
        self.assertEqual(
            res, os.path.join(str(self.temp), "GatherV2.input.0.float32.npy")
        )
        self.assertEqual(self.temp.joinpath(Constant.MAPPING_CSV_FILE).exists(), False)

    def test_build_dst_file_name_oversize_renamed(self):
        """超长的解析结果文件名被重命名为随机数字串，并记录到同级mapping.csv"""
        info = AicErrorInfo()
        info.kernel_name = "a" * 260
        dump_data_parser = DumpDataParser(str(self.temp), info)
        build_dst_file_name = getattr(dump_data_parser, "_build_dst_file_name")
        res = build_dst_file_name(
            str(self.temp), "input", 0, "float32", np.dtype("float32")
        )
        file_name = os.path.basename(res)
        # 重命名后为随机数字串 + 原后缀，落盘不会超过NAME_MAX
        assert len(file_name) <= Constant.MAX_FILE_NAME_LEN
        assert file_name.endswith(".npy")
        assert file_name[: -len(".npy")].isdigit()
        # 回读mapping.csv，确认记录了 {映射后},{映射前}
        mapping_text = self.temp.joinpath(Constant.MAPPING_CSV_FILE).read_text(
            encoding="utf-8"
        )
        self.assertIn(
            mapping_text, f"{file_name},{info.kernel_name}.input.0.float32.npy"
        )
        # 重命名后的文件名可以正常落盘
        np.save(res, np.zeros(2, dtype=np.float32))
        self.assertEqual(os.path.isfile(res), True)

    def test_build_dst_file_name_oversize_multi_byte(self):
        """多字节kernel_name按字节数判超长，字符数未超但字节数已超时同样重命名"""
        info = AicErrorInfo()
        info.kernel_name = "算" * 100  # 100个字符，UTF-8编码为300字节
        dump_data_parser = DumpDataParser(str(self.temp), info)
        build_dst_file_name = getattr(dump_data_parser, "_build_dst_file_name")
        res = build_dst_file_name(
            str(self.temp), "input", 0, "float32", np.dtype("float32")
        )
        file_name = os.path.basename(res)
        assert len(os.fsencode(file_name)) <= Constant.MAX_FILE_NAME_LEN
        assert file_name[: -len(".npy")].isdigit()
        np.save(res, np.zeros(2, dtype=np.float32))
        self.assertEqual(os.path.isfile(res), True)

    def test_build_dst_file_name_oversize_bin_keeps_suffix(self):
        """超长的bin结果同样保留.bin后缀，保证下游按裸字节读取"""
        info = AicErrorInfo()
        info.kernel_name = "a" * 260
        dump_data_parser = DumpDataParser(str(self.temp), info)
        res = getattr(dump_data_parser, "_build_dst_file_name")(
            str(self.temp), "input", 0, "hifloat8", None
        )
        assert os.path.basename(res).endswith(".bin")

    def test_gen_random_numeric_name(self, mocker):
        """随机数字串与已有文件冲突时重新生成"""
        dump_data_parser = DumpDataParser(str(self.temp), AicErrorInfo())
        self.temp.joinpath("1111111111111111.npy").touch()
        mocker.patch("random.randint", side_effect=[1111111111111111, 2222222222222222])
        res = getattr(dump_data_parser, "_gen_random_numeric_name")(
            str(self.temp), ".npy"
        )
        self.assertEqual(res, "2222222222222222.npy")

    def test_record_mapping_append(self):
        """多条映射追加写入同一份mapping.csv"""
        dump_data_parser = DumpDataParser(str(self.temp), AicErrorInfo())
        getattr(dump_data_parser, "_record_mapping")(
            str(self.temp), "1111111111111111.npy", "long_name_a.npy"
        )
        getattr(dump_data_parser, "_record_mapping")(
            str(self.temp), "2222222222222222.bin", "long_name_b.bin"
        )
        mapping_text = self.temp.joinpath(Constant.MAPPING_CSV_FILE).read_text(
            encoding="utf-8"
        )
        self.assertIn(mapping_text, "1111111111111111.npy,long_name_a.npy")
        self.assertIn(mapping_text, "2222222222222222.bin,long_name_b.bin")

    def test_load_name_mapping(self):
        """读取dump目录下的mapping.csv，构造 原名 -> 映射名 的查找字典"""
        dump_data_parser = DumpDataParser(str(self.temp), AicErrorInfo())
        self.temp.joinpath(Constant.MAPPING_CSV_FILE).write_text(
            "1234567890123456,long_name_a\nbad_line\n", encoding="utf-8"
        )
        self.assertEqual(
            getattr(dump_data_parser, "_load_name_mapping")(),
            {"long_name_a": "1234567890123456"},
        )

    def test_load_name_mapping_not_exist(self):
        dump_data_parser = DumpDataParser(str(self.temp), AicErrorInfo())
        self.assertEqual(getattr(dump_data_parser, "_load_name_mapping")(), {})

    def test_parse_matches_by_mapped_name(self, mocker):
        """dump目录下只有随机名文件 + mapping.csv时，按data_name反查映射名命中"""
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.joinpath(rename).touch()
        dump_dir.joinpath(Constant.MAPPING_CSV_FILE).write_text(
            f"{rename},{data_name}\n", encoding="utf-8"
        )
        info = AicErrorInfo()
        info.node_name = "GatherV2"
        info.data_name = data_name
        dump_data_parser = DumpDataParser(str(dump_dir), info)
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="")
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [str(dump_dir.joinpath(rename))])

    def test_parse_skips_mapping_csv(self, mocker):
        """mapping.csv不会被当成dump文件解析"""
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.joinpath("GatherV2.1.1.123").touch()
        dump_dir.joinpath(Constant.MAPPING_CSV_FILE).write_text(
            "1234,GatherV2.mapping\n", encoding="utf-8"
        )
        info = AicErrorInfo()
        info.node_name = "GatherV2"
        dump_data_parser = DumpDataParser(str(dump_dir), info)
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="")
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [str(dump_dir.joinpath("GatherV2.1.1.123"))])

    def test_parse_parses_custom_dump_files(self, mocker):
        """自定义dump文件与原始dump一起被逐一解析"""
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.joinpath("GatherV2.1.1.123").touch()
        custom_file = str(dump_dir.joinpath("exception_info.custom.1726159207469000"))
        with open(custom_file, "w", encoding="utf-8") as f:
            f.write("custom")
        info = AicErrorInfo()
        info.node_name = "GatherV2"
        dump_data_parser = DumpDataParser(
            str(dump_dir), info, custom_dump_files=[custom_file]
        )
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="")
        dump_data_parser.parse()
        self.assertEqual(
            set(info.dump_file),
            {str(dump_dir.joinpath("GatherV2.1.1.123")), custom_file},
        )

    def test_parse_marks_custom_dump_file(self, mocker):
        """自定义dump的解析块前额外输出一行Custom dump file:说明，原始dump不加"""
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        original_file = dump_dir.joinpath("GatherV2.1.1.123")
        original_file.touch()
        custom_file = str(dump_dir.joinpath("exception_info.custom.1726159207469000"))
        with open(custom_file, "w", encoding="utf-8") as f:
            f.write("custom")
        info = AicErrorInfo()
        info.node_name = "GatherV2"
        dump_data_parser = DumpDataParser(
            str(dump_dir), info, custom_dump_files=[custom_file]
        )
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="data")
        dump_data_parser.parse()
        self.assertIn(
            info.dump_info,
            f"Custom dump file:\nOriginal file: {custom_file}\nafter convert:\ndata",
        )
        self.assertEqual(info.dump_info.count("Custom dump file:"), 1)
        self.assertNotIn(
            info.dump_info, f"Custom dump file:\nOriginal file: {original_file}"
        )

    def test_parse_skips_unregistered_custom_file_in_walk(self, mocker):
        """walk按node_name命中的自定义dump文件未登记进custom_dump_files时，不作为报错dump解析"""
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.joinpath("GatherV2.custom.1726159207469000").touch()
        info = AicErrorInfo()
        info.node_name = "GatherV2"
        dump_data_parser = DumpDataParser(str(dump_dir), info)
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="")
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [])

    def test_parse_custom_dump_file_missing_skipped(self, mocker):
        """日志指示但文件不存在的自定义dump不进入解析列表"""
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.joinpath("GatherV2.1.1.123").touch()
        info = AicErrorInfo()
        info.node_name = "GatherV2"
        dump_data_parser = DumpDataParser(
            str(dump_dir),
            info,
            custom_dump_files=[str(dump_dir.joinpath("exception_info.custom.123"))],
        )
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="")
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [str(dump_dir.joinpath("GatherV2.1.1.123"))])

    def test_parse_custom_dump_file_deduped(self, mocker):
        """自定义dump文件被walk按node_name命中时只解析一次"""
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        custom_file = str(dump_dir.joinpath("GatherV2.custom.1726159207469000"))
        with open(custom_file, "w", encoding="utf-8") as f:
            f.write("custom")
        info = AicErrorInfo()
        info.node_name = "GatherV2"
        dump_data_parser = DumpDataParser(
            str(dump_dir), info, custom_dump_files=[custom_file]
        )
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="")
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [custom_file])

    def test_parse_without_custom_dump_files(self, mocker):
        """未传custom_dump_files时行为与原来一致"""
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.joinpath("GatherV2.1.1.123").touch()
        info = AicErrorInfo()
        info.node_name = "GatherV2"
        dump_data_parser = DumpDataParser(str(dump_dir), info)
        mocker.patch.object(dump_data_parser, "parse_dump_data", return_value="")
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [str(dump_dir.joinpath("GatherV2.1.1.123"))])

    def test_parse_separates_dump_files_with_blank_line(self, mocker):
        """多个dump文件解析块之间用空行分隔，便于阅读"""
        dump_dir = self.temp.joinpath("dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        first_file = str(dump_dir.joinpath("GatherV2.1.1.123"))
        dump_dir.joinpath("GatherV2.1.1.123").touch()
        custom_file = str(dump_dir.joinpath("exception_info.custom.1726159207469000"))
        with open(custom_file, "w", encoding="utf-8") as f:
            f.write("custom")
        info = AicErrorInfo()
        info.node_name = "GatherV2"
        dump_data_parser = DumpDataParser(
            str(dump_dir), info, custom_dump_files=[custom_file]
        )
        mocker.patch.object(
            dump_data_parser, "parse_dump_data", side_effect=["AA\n", "BB\n"]
        )
        dump_data_parser.parse()
        self.assertEqual(
            info.dump_info,
            f"Original file: {first_file}\n"
            "after convert:\n"
            "AA\n"
            "\n"
            "Custom dump file:\n"
            f"Original file: {custom_file}\n"
            "after convert:\n"
            "BB\n",
        )
