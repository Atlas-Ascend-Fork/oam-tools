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

import importlib
import sys

from unittest.mock import Mock, MagicMock

from conftest import MSAICERR_PATH, CommonAssert

sys.path.append(MSAICERR_PATH)


class TestCompileFileMethods(CommonAssert):
    def test_get_compile_from_tik_import_error(self, mocker, tmp_path):
        mocker.patch("ms_interface.compile_file.Path")
        mocker.patch("ms_interface.compile_file.utils")

        from ms_interface.compile_file import get_compile_from_tik

        result = get_compile_from_tik("Ascend910B1", str(tmp_path))
        self.assertEqual(result, [])

    def test_get_compile_from_tik_attribute_error(self, mocker, tmp_path):
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("tbe"):
                raise AttributeError("module 'numpy' has no attribute 'bool'")
            return real_import(name, *args, **kwargs)

        mocker.patch("builtins.__import__", side_effect=mock_import)
        from ms_interface.compile_file import get_compile_from_tik

        result = get_compile_from_tik("Ascend910B1", str(tmp_path))
        self.assertEqual(result, [])

    def test_get_compile_file_with_handler(self, mocker, tmp_path):
        mock_handler = Mock()
        mock_handler.is_chip_handler.return_value = True
        mock_handler.get_compile_file.return_value = (
            str(tmp_path / "bin.o"),
            str(tmp_path / "bin.json"),
        )
        mocker.patch(
            "ms_interface.compile_file.utils.load_ascend_handlers",
            return_value=[mock_handler],
        )

        from ms_interface.compile_file import get_compile_file

        result = get_compile_file("Ascend910B1", str(tmp_path))
        self.assertEqual(result, (str(tmp_path / "bin.o"), str(tmp_path / "bin.json")))

    def test_get_compile_file_no_handler_fallback(self, mocker, tmp_path):
        mock_handler = Mock()
        mock_handler.is_chip_handler.return_value = False
        mocker.patch(
            "ms_interface.compile_file.utils.load_ascend_handlers",
            return_value=[mock_handler],
        )
        mocker.patch(
            "ms_interface.compile_file.get_compile_from_tik",
            return_value=[
                str(tmp_path / "fallback.o"),
                str(tmp_path / "fallback.json"),
            ],
        )

        from ms_interface.compile_file import get_compile_file

        result = get_compile_file("Ascend910B1", str(tmp_path))
        self.assertEqual(
            result, [str(tmp_path / "fallback.o"), str(tmp_path / "fallback.json")]
        )

    def test_get_compile_file_no_handlers(self, mocker, tmp_path):
        mocker.patch(
            "ms_interface.compile_file.utils.load_ascend_handlers", return_value=[]
        )
        mocker.patch(
            "ms_interface.compile_file.get_compile_from_tik",
            return_value=[
                str(tmp_path / "fallback.o"),
                str(tmp_path / "fallback.json"),
            ],
        )

        from ms_interface.compile_file import get_compile_file

        result = get_compile_file("Ascend910B1", str(tmp_path))
        self.assertEqual(
            result, [str(tmp_path / "fallback.o"), str(tmp_path / "fallback.json")]
        )

    def test_get_compile_from_tik_no_build_files(self, mocker, tmp_path):
        from pathlib import PosixPath

        mock_build_dir = MagicMock(spec=PosixPath)
        mock_build_dir.__str__ = Mock(
            return_value=str(tmp_path / "build_out/op_kernel")
        )
        mocker.patch(
            "ms_interface.compile_file.Path.joinpath", return_value=mock_build_dir
        )
        mocker.patch("ms_interface.compile_file.utils")
        mock_build_dir.rglob.return_value = []

        tbe_mock = MagicMock()
        tbe_common = MagicMock()
        tbe_tik = MagicMock()
        tbe_common_platform = MagicMock()
        sys.modules["tbe"] = tbe_mock
        sys.modules["tbe.common"] = tbe_common
        sys.modules["tbe.common.platform"] = tbe_common_platform
        sys.modules["tbe.tik"] = tbe_tik
        mod = importlib.import_module("ms_interface.compile_file")
        importlib.reload(mod)

        from ms_interface.compile_file import get_compile_from_tik

        result = get_compile_from_tik("Ascend910B1", str(tmp_path))
        self.assertEqual(result, [])
