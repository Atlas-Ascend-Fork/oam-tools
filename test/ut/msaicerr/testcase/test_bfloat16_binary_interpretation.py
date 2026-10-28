#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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

import numpy as np
import pytest
from ms_interface import dump_data_parser as module
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.dump_data_parser import DumpDataParser
from ms_interface.utils import AicErrException


class RegisteredBfloatNumpy:
    """CPU extension double that decodes real bytes without patching global NumPy."""

    def __init__(self):
        self.events = []

    def __getattr__(self, name):
        return getattr(np, name)

    def dtype(self, value):
        if value == "bfloat16":
            self.events.append("dtype")
            return "registered_bfloat16"
        return np.dtype(value)

    def fromfile(self, filename, dtype):
        if dtype != "registered_bfloat16":
            return np.fromfile(filename, dtype=dtype)
        self.events.append("read")
        return (np.fromfile(filename, dtype=np.uint16).astype(np.uint32) << 16).view(
            np.float32
        )


@pytest.fixture
def registered_bfloat(mocker):
    proxy = RegisteredBfloatNumpy()
    mocker.patch.object(module, "np", proxy)

    def register():
        proxy.events.append("register")
        return True

    mocker.patch.object(DumpDataParser, "_register_ext_dtype", side_effect=register)
    return proxy


def test_bfloat16_converter_preserves_binary_values(registered_bfloat, tmp_path):
    source = tmp_path / "values.bfloat16.bin"
    source.write_bytes(bytes.fromhex("803f00c0003f"))
    parser = DumpDataParser(str(source), AicErrorInfo(), dest_dtype="bfloat16")
    parser.convert_bin_file_to_npy()
    assert registered_bfloat.events == ["register", "dtype", "read"]
    np.testing.assert_array_equal(np.load(parser.bin_data_list[0]), [1, -2, 0.5])


@pytest.mark.parametrize(
    "payload,expected",
    [
        ("803f00c0003f", "Max: 1.0, Min: -2.0"),
        ("", "Max: N/A"),
        ("807fc07f", "NaN/INF values present"),
    ],
)
def test_bfloat16_summary_values_empty_and_nonfinite(
    registered_bfloat, tmp_path, payload, expected
):
    source = tmp_path / "values.bin"
    source.write_bytes(bytes.fromhex(payload))
    result = DumpDataParser._summary_tensor_without_dtype(str(source), "bfloat16")
    assert registered_bfloat.events == ["register", "dtype", "read"]
    assert expected in result


def test_missing_extension_converter_reports_error(mocker, tmp_path):
    mocker.patch.object(DumpDataParser, "_register_ext_dtype", return_value=False)
    source = tmp_path / "values.bin"
    source.write_bytes(b"")
    parser = DumpDataParser(str(source), AicErrorInfo(), dest_dtype="bfloat16")
    with pytest.raises(AicErrException):
        parser.convert_bin_file_to_npy()
    assert not parser.bin_data_list


def test_missing_extension_summary_has_explicit_diagnostic(mocker):
    mocker.patch.object(DumpDataParser, "_register_ext_dtype", return_value=False)
    assert (
        "bfloat16ext is not installed"
        in DumpDataParser._summary_tensor_without_dtype("unused.bin", "bfloat16")
    )


def test_bfloat16_binary_preserves_real_values_when_extension_is_available(tmp_path):
    pytest.importorskip("bfloat16ext")
    source = tmp_path / "values.bfloat16.bin"
    source.write_bytes(bytes.fromhex("803f00c0003f"))
    parser = DumpDataParser(str(source), AicErrorInfo(), dest_dtype="bfloat16")
    parser.convert_bin_file_to_npy()
    data = np.load(parser.bin_data_list[0]).view(np.dtype("bfloat16"))
    np.testing.assert_array_equal(data.astype(np.float32), [1, -2, 0.5])
    assert data.tobytes() == source.read_bytes()
