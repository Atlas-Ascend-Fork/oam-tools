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

from conftest import MSAICERR_PATH

sys.path.append(MSAICERR_PATH)
from unittest.mock import patch, MagicMock
from ms_interface.utils import load_ascend_handlers


class TestChipHandler:
    # fixture/setup_method 中赋值，此处声明以明确实例属性集合
    ascend_folder = None
    bad_class_file = None
    correct_file = None
    invalid_file = None
    tmp_dir = None
    tmp_path = None

    def setup_method(self):
        # 创建临时文件夹
        self.tmp_dir = tempfile.TemporaryDirectory(dir="./")
        self.tmp_path = self.tmp_dir.name

        # 创建测试文件夹结构
        self.ascend_folder = os.path.join(self.tmp_path, "ascend_test")
        os.mkdir(self.ascend_folder)

        # 创建正确的handler文件
        self.correct_file = os.path.join(self.ascend_folder, "ascend_testhandler.py")
        with open(self.correct_file, "w", encoding="utf-8") as f:
            f.write(
                "class AscendTestHandler:\n"
                "    def __init__(self):\n"
                "        self.chip_type = 'test'\n"
                "        self.chip_regex = 'test_regex'\n"
            )

        # 创建一个没有正确类名的文件
        self.bad_class_file = os.path.join(self.ascend_folder, "ascend_badhandler.py")
        with open(self.bad_class_file, "w", encoding="utf-8") as f:
            f.write("class WrongName:\n    pass\n")

        # 创建一个无效的Python文件
        self.invalid_file = os.path.join(self.ascend_folder, "ascend_errorhandler.py")
        with open(self.invalid_file, "w", encoding="utf-8") as f:
            f.write("invalid syntax")

    def teardown_method(self):
        # 清理临时文件夹
        self.tmp_dir.cleanup()

    def assertTrue(self, value):
        assert value is True

    def assertIsInstance(self, instance, cls_type):
        assert isinstance(instance, cls_type)

    @patch("importlib.import_module")
    @patch("os.listdir")
    @patch("os.path.dirname")
    def test_load_ascend_handlers(self, mock_dirname, mock_listdir, mock_import_module):
        # 模拟os.path.realpath的返回值
        mock_dirname.return_value = self.tmp_path
        mock_listdir.side_effect = [["ascend_test"], ["ascend_testhandler.py"]]
        # 模拟模块导入和类实例化
        mock_module = MagicMock()
        mock_class = MagicMock()
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        mock_module.AscendTestHandler = mock_class
        mock_import_module.return_value = mock_module

        # 调用需要测试的方法
        handlers = load_ascend_handlers()
        # 验证结果
        self.assertTrue(len(handlers) == 1)
        self.assertIsInstance(handlers[0], MagicMock)

    @patch("importlib.import_module")
    @patch("os.listdir")
    @patch("os.path.dirname")
    def test_load_ascend_handlers_module_not_found(
        self, mock_dirname, mock_listdir, mock_import_module
    ):
        # 模拟os.path.realpath的返回值
        mock_dirname.return_value = self.tmp_path
        mock_listdir.side_effect = [["ascend_test"], ["ascend_testhandler.py"]]

        # 模拟模块导入失败
        mock_import_module.side_effect = ModuleNotFoundError("Module not found")
        handlers = load_ascend_handlers()
        self.assertTrue(len(handlers) == 0)
