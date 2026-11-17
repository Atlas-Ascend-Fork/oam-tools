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

import sys

from conftest import MSAICERR_PATH
from ms_interface import dsmi_interface
from ms_interface.dsmi_interface import DSMIInterface, DsmiChipInfoStru

sys.path.append(MSAICERR_PATH)

# reached by name to avoid direct protected-member access at call sites
PARSE_ERROR = "_parse_error"


def test_get_vector_core_count(mocker):
    mocker.patch("ctypes.CDLL")
    dsmi = DSMIInterface()
    assert dsmi.get_vector_core_count(0) == 0


def test_get_ai_core_count(mocker):
    mocker.patch("ctypes.CDLL")
    dsmi = DSMIInterface()
    assert dsmi.get_aicore_count(0) == 0


def test_chip_info_stru_platform():
    stru = DsmiChipInfoStru()
    stru.chip_type = b"Ascend"
    stru.chip_name = b"910B"
    assert stru.get_complete_platform() == "Ascend910B"
    stru.chip_ver = b"V1"
    assert stru.get_ver() == "V1"


def test_get_device_count_ok(mocker):
    mocker.patch("ctypes.CDLL")
    dsmi = DSMIInterface()
    mocker.patch.object(DSMIInterface, "_parse_error", return_value=False)
    dsmi.dsmidll.dsmi_get_device_count.return_value = 0
    # device_count[0] stays 0 because the mocked C call does not write it
    assert dsmi.get_device_count() == 0


def test_get_device_count_error(mocker):
    mocker.patch("ctypes.CDLL")
    dsmi = DSMIInterface()
    mocker.patch.object(DSMIInterface, "_parse_error", return_value=True)
    assert dsmi.get_device_count() == 0


def test_get_chip_info_ok(mocker):
    mocker.patch("ctypes.CDLL")
    dsmi = DSMIInterface()
    mocker.patch.object(DSMIInterface, "_parse_error", return_value=False)
    result = dsmi.get_chip_info(0)
    assert isinstance(result, DsmiChipInfoStru)


def test_get_chip_info_error(mocker):
    mocker.patch("ctypes.CDLL")
    dsmi = DSMIInterface()
    mocker.patch.object(DSMIInterface, "_parse_error", return_value=True)
    assert dsmi.get_chip_info(0) is None


def test_get_vector_core_count_success(mocker):
    mocker.patch("ctypes.CDLL")
    dsmi = DSMIInterface()
    dsmi.drvhal.halGetDeviceInfo.return_value = 0
    # halGetDeviceInfo writes nothing to the pointer, contents stays 0
    assert dsmi.get_vector_core_count(0) == 0


def test_get_aicore_count_ret_nonzero(mocker):
    mocker.patch("ctypes.CDLL")
    dsmi = DSMIInterface()
    dsmi.drvhal.halGetDeviceInfo.return_value = 1
    assert dsmi.get_aicore_count(0) == 0


def test_parse_error_zero():
    assert getattr(DSMIInterface, PARSE_ERROR)(0, "fn") is False


def test_parse_error_known_code():
    # use a code present in DsmiErrorCode
    result = getattr(DSMIInterface, PARSE_ERROR)(1, "fn")
    assert isinstance(result, bool)


def test_parse_error_unknown_code():
    assert getattr(DSMIInterface, PARSE_ERROR)(999999, "fn") is True


def test_parse_error_allow_positive():
    assert getattr(DSMIInterface, PARSE_ERROR)(5, "fn", allow_positive=True) is False


def test_get_soc_version(mocker):
    chip = mocker.Mock()
    chip.get_complete_platform.return_value = "Ascend910B"
    mocker.patch.object(dsmi_interface.DSMIInterface, "__init__", return_value=None)
    mocker.patch.object(
        dsmi_interface.DSMIInterface, "get_chip_info", return_value=chip
    )
    assert dsmi_interface.get_soc_version() == "Ascend910B"
