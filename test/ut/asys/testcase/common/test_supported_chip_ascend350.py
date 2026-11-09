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
from pathlib import Path
import pytest

from testcase.conftest import ut_root_path

from common.supported_chip import AsysConfigSupportedChip, AsysDiagnoseSupportedChip
from common.device import DeviceInfo
from common.chip_handler import ChipHandler, g_device_map
from ..conftest import AssertTest


class TestSupportedChip(AssertTest):
    test_file_path = os.path.join(ut_root_path, "test_file")

    def setup_method(self):
        testfile = Path(self.test_file_path)
        testfile.touch(exist_ok=True)
        self.fp = open(testfile, encoding="utf-8")
        g_device_map.clear()

    def teardown_method(self):
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    @pytest.mark.parametrize(
        ["chip_type", "expect"], [("Ascend 350 V1", True), ("Unknown", False)]
    )
    def test_asys_config_supported_chip(self, mocker, chip_type, expect):
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_type)
        self.assertTrue(
            AsysConfigSupportedChip().get_supported_chip_info(0)[0] == expect
        )

    @pytest.mark.parametrize(
        ["chip_type", "expect"], [("Ascend 350 V1", True), ("Unknown", False)]
    )
    def test_asys_diagnose_supported_chip(self, mocker, chip_type, expect):
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_type)
        self.assertTrue(
            AsysDiagnoseSupportedChip().get_supported_chip_info(0)[0] == expect
        )

    def test_chip_handler_returns_ascend350_handler(self):
        handler = ChipHandler().get_handler("Ascend 350 V1")
        self.assertTrue(type(handler).__name__ == "Ascend350Handler")

    def test_ascend350_behavior_matches_ascend950(self):
        """Ascend350 为 Ascend950 裁剪版，接口与行为须与 950 一致。"""
        handler_350 = ChipHandler().get_handler("Ascend 350 V1")
        handler_950 = ChipHandler().get_handler("Ascend 950 V1")
        self.assertTrue(handler_350.need_lp_param() == handler_950.need_lp_param())
        self.assertTrue(handler_350.support_dvpp() == handler_950.support_dvpp())
