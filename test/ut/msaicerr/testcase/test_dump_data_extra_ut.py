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
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from conftest import MSAICERR_PATH
from ms_interface import dump_data_parser as dump_module
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.dump_data_parser import DumpDataParser
from ms_interface.utils import AicErrException

sys.path.append(MSAICERR_PATH)


def _make_parser(dest_dtype="", output_path="", dump_path=None):
    # 默认值在导入期求值，取不到 tmp_path fixture；用 gettempdir 避免硬编码 /tmp
    if dump_path is None:
        dump_path = os.path.join(tempfile.gettempdir(), "data.bin")
    return DumpDataParser(dump_path, AicErrorInfo(), dest_dtype, output_path)


def test_no_dest_dtype():
    parser = _make_parser(dest_dtype="")
    result = parser.convert_bin_file_to_npy()
    assert "Need to specify the dtype" in result


def test_invalid_dest_dtype():
    parser = _make_parser(dest_dtype="not_a_dtype")
    result = parser.convert_bin_file_to_npy()
    assert "Invalid dest_dtype" in result


def test_convert_success(mocker, tmp_path):
    parser = _make_parser(
        dest_dtype="float16",
        output_path=str(tmp_path),
        dump_path=str(tmp_path / "data.bin"),
    )
    mocker.patch("numpy.fromfile", return_value=np.ones(4, dtype=np.float16))
    saved = mocker.patch("numpy.save")
    _ = parser.convert_bin_file_to_npy()
    assert saved.called
    assert len(parser.bin_data_list) == 1


def test_convert_dtype_mismatch_warning(mocker, tmp_path):
    # file name carries .int8 but dest_dtype is float16 -> warning branch
    parser = _make_parser(
        dest_dtype="float16",
        output_path=str(tmp_path),
        dump_path=str(tmp_path / "data.int8.bin"),
    )
    mocker.patch("numpy.fromfile", return_value=np.ones(4, dtype=np.float16))
    mocker.patch("numpy.save")
    result = parser.convert_bin_file_to_npy()
    assert "different from dest_dtype" in result


def test_convert_failure_raises(mocker, tmp_path):
    parser = _make_parser(
        dest_dtype="float16",
        output_path=str(tmp_path),
        dump_path=str(tmp_path / "data.bin"),
    )
    mocker.patch("numpy.fromfile", side_effect=RuntimeError("boom"))
    with pytest.raises(AicErrException):
        parser.convert_bin_file_to_npy()


def test_convert_bfloat16_registers_ext_dtype(mocker, tmp_path):
    parser = _make_parser(
        dest_dtype="bfloat16",
        output_path=str(tmp_path),
        dump_path=str(tmp_path / "data.bin"),
    )
    events = []
    dtype = mocker.sentinel.registered_bfloat16_dtype
    fake = Mock()
    original_numpy_dtype = np.dtype

    def register():
        events.append("register")
        return True

    def resolve_dtype(value):
        assert value == "bfloat16"
        events.append("dtype")
        return dtype

    def read_file(filename, dtype):
        assert filename == parser.dump_path
        assert dtype is mocker.sentinel.registered_bfloat16_dtype
        events.append("read")
        return fake

    register_mock = mocker.patch.object(
        DumpDataParser, "_register_ext_dtype", side_effect=register
    )
    saved = Mock()
    # Patch only this module's NumPy binding; the global NumPy module is untouched.
    mocker.patch.object(
        dump_module,
        "np",
        SimpleNamespace(dtype=resolve_dtype, fromfile=read_file, save=saved),
    )
    parser.convert_bin_file_to_npy()
    register_mock.assert_called_once_with()
    assert events == ["register", "dtype", "read"]
    assert np.dtype is original_numpy_dtype
    fake.astype.assert_not_called()
    saved.assert_called_once_with(parser.bin_data_list[0], fake)


def test_convert_bfloat16_without_ext_raises(mocker, tmp_path):
    # bfloat16ext 未安装时给出明确报错，而不是让 astype 抛出难懂的 TypeError
    parser = _make_parser(
        dest_dtype="bfloat16",
        output_path=str(tmp_path),
        dump_path=str(tmp_path / "data.bin"),
    )
    mocker.patch.object(DumpDataParser, "_register_ext_dtype", return_value=False)
    with pytest.raises(AicErrException):
        parser.convert_bin_file_to_npy()
