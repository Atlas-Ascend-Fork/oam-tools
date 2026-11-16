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

import ctypes
import os
import sys
from configparser import ConfigParser

import pytest
from unittest.mock import MagicMock
import shutil
from .conftest import CONF_SRC_PATH, ASYS_SRC_PATH, test_case_tmp
from .conftest import AssertTest
from .conftest import enter_test_tmp, restore_cwd


import asys
from common.const import RetCode
from params import ParamDict
from common import FileOperate
from drv import LoadSoType
from collect import AsysCollect


class TestAsys(AssertTest):
    @staticmethod
    def setup_method():
        print("init test environment")  # noqa: T201  # test diagnostic output
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        enter_test_tmp()
        ParamDict.clear()

    @staticmethod
    def teardown_method():
        print("clean test environment.")  # noqa: T201  # test diagnostic output
        restore_cwd()
        if os.path.exists(test_case_tmp):
            os.chmod(test_case_tmp, 0o777)  # nosec B103  # test asserts permission-mask behavior
            shutil.rmtree(test_case_tmp)

    @pytest.mark.parametrize(
        "read_file",
        [
            ([[["g++", "g++ --version | grep g++"]], False]),
            ([False, False]),
        ],
    )
    def test_config_parser_failed(self, mocker, read_file, caplog):
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        mocker.patch.object(FileOperate, "read_file", side_effect=read_file)
        self.assertTrue(not asys.main())

    @pytest.mark.parametrize(
        "parser_data", [[("graph", "TRUE1")], [("graph1", "TRUE")]]
    )
    def test_config_parse_ini_failed(self, mocker, parser_data, caplog):
        sys.argv = [CONF_SRC_PATH, "launch", '--task="bash test.sh"']
        mocker.patch.object(ConfigParser, "items", return_value=parser_data)
        mocker.patch("asys.create_out_timestamp_dir", return_value=RetCode.FAILED)
        ParamDict().set_env_type("EP")
        self.assertTrue(not asys.main())

    @pytest.mark.parametrize("ent", [0, 1])
    def test_asys_get_ent_ret_ep(self, ent, mocker, caplog):
        self.assertTrue(True)
        # 创建一个模拟的 ctypes 函数指针
        mock_dev = MagicMock()
        mock_dev.drvGetPlatformInfo.return_value = 0
        mock_dev.drvGetPlatformInfo.argtypes = [ctypes.POINTER(ctypes.c_int)]
        num = ctypes.c_int(0)
        mock_dev.drvGetPlatformInfo(ctypes.pointer(num))

        # 使用 side_effect 来模拟 drvGetPlatformInfo 修改 num 的值
        def side_effect(num_ptr):
            num_ptr.contents.value = ent
            return 0

        mock_dev.drvGetPlatformInfo.side_effect = side_effect
        mocker.patch.object(LoadSoType, "get_drvhal_env_type", return_value=mock_dev)
        sys.argv = [CONF_SRC_PATH, "collect"]
        mocker.patch.object(AsysCollect, "run", return_value=True)
        self.assertTrue(asys.main())
        LoadSoType.clear()

    def test_clean_env(self, mocker):
        mock_file_path = mocker.Mock()
        mock_file_path.endswith.return_value = True
        sys.argv = [CONF_SRC_PATH, "collect"]
        ParamDict().set_env_type("EP")
        mocker.patch.object(AsysCollect, "run", return_value=True)
        self.assertTrue(asys.main())
        LoadSoType.clear()
        check = False
        asys.clean_pycache()
        for root, dirs, files in os.walk(ASYS_SRC_PATH):
            if "__pycache__" in dirs:
                check = True
        self.assertTrue(not check)
