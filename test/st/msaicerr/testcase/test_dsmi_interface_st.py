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
from unittest.mock import Mock

import pytest

from conftest import MSAICERR_PATH

sys.path.append(MSAICERR_PATH)
from ms_interface import dsmi_interface
from ms_interface.dsmi_interface import DSMIInterface, DsmiChipInfoStru, DsmiErrorCode


@pytest.fixture
def dsmi(mocker):
    """构造 DSMIInterface，但不真的 dlopen 设备库（ST 环境无昇腾驱动）。"""
    mocker.patch.object(dsmi_interface.ctypes, "CDLL", return_value=Mock())
    return DSMIInterface()


def test_chip_info_get_complete_platform_concats_type_and_name():
    info = DsmiChipInfoStru()
    info.chip_type = b"Ascend"
    info.chip_name = b"910B"
    assert info.get_complete_platform() == "Ascend910B"


def test_chip_info_get_ver():
    info = DsmiChipInfoStru()
    info.chip_ver = b"V100"
    assert info.get_ver() == "V100"


def test_get_device_count_success(dsmi):
    # 出参由 ctypes 数组承载，桩函数需回填才能与失败路径（也返回 0）区分开，
    # 否则成功分支逻辑回归时用例依然通过。
    def fill_count(count_arr):
        count_arr[0] = 3
        return 0

    dsmi.dsmidll.dsmi_get_device_count = Mock(side_effect=fill_count)
    assert dsmi.get_device_count() == 3


def test_get_device_count_known_error_code_returns_zero(dsmi):
    # 错误码经 _parse_error 判定为失败，公有方法应兜底返回 0
    dsmi.dsmidll.dsmi_get_device_count = Mock(
        return_value=DsmiErrorCode.DSMI_ERROR_NO_DEVICE.value
    )
    assert dsmi.get_device_count() == 0


def test_get_device_count_unknown_error_code_returns_zero(dsmi):
    # 不在 DsmiErrorCode 枚举内的码走 ValueError 分支，仍判为失败
    dsmi.dsmidll.dsmi_get_device_count = Mock(return_value=123456)
    assert dsmi.get_device_count() == 0


def test_get_chip_info_success_returns_struct(dsmi):
    dsmi.dsmidll.dsmi_get_chip_info = Mock(return_value=0)
    assert isinstance(dsmi.get_chip_info(0), DsmiChipInfoStru)


def test_get_chip_info_error_returns_none(dsmi):
    dsmi.dsmidll.dsmi_get_chip_info = Mock(
        return_value=DsmiErrorCode.DSMI_ERROR_INVALID_DEVICE.value
    )
    assert dsmi.get_chip_info(0) is None


def test_get_vector_core_count_non_zero_ret_returns_zero(dsmi):
    dsmi.drvhal.halGetDeviceInfo = Mock(return_value=-1)
    assert dsmi.get_vector_core_count(0) == 0


def test_get_vector_core_count_success(dsmi):
    # 回填 byref 出参，与失败路径（也返回 0）区分开
    def fill_core_num(dev_id, module_type, info_type, count_ptr):
        count_ptr.contents.value = 7
        return 0

    dsmi.drvhal.halGetDeviceInfo = Mock(side_effect=fill_core_num)
    assert dsmi.get_vector_core_count(0) == 7


def test_get_vector_core_count_missing_symbol_returns_zero(dsmi):
    # 老驱动无 halGetDeviceInfo 符号时 ctypes 抛 AttributeError，需兜底为 0
    dsmi.drvhal.halGetDeviceInfo = Mock(side_effect=AttributeError("no symbol"))
    assert dsmi.get_vector_core_count(0) == 0


def test_get_aicore_count_non_zero_ret_returns_zero(dsmi):
    dsmi.drvhal.halGetDeviceInfo = Mock(return_value=-1)
    assert dsmi.get_aicore_count(0) == 0


def test_get_aicore_count_success(dsmi):
    # 同上：回填 byref 出参，避免与失败路径的 0 混淆
    def fill_core_num(dev_id, module_type, info_type, count_ptr):
        count_ptr.contents.value = 5
        return 0

    dsmi.drvhal.halGetDeviceInfo = Mock(side_effect=fill_core_num)
    assert dsmi.get_aicore_count(0) == 5


def test_get_aicore_count_missing_symbol_returns_zero(dsmi):
    dsmi.drvhal.halGetDeviceInfo = Mock(side_effect=AttributeError("no symbol"))
    assert dsmi.get_aicore_count(0) == 0


def test_get_soc_version_reads_chip_info(mocker):
    info = DsmiChipInfoStru()
    info.chip_type = b"Ascend"
    info.chip_name = b"910B"
    mocker.patch.object(dsmi_interface.ctypes, "CDLL", return_value=Mock())
    mocker.patch.object(DSMIInterface, "get_chip_info", return_value=info)
    assert dsmi_interface.get_soc_version() == "Ascend910B"
