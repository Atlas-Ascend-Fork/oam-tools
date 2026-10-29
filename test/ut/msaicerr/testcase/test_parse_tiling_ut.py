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
import struct

from unittest.mock import mock_open
import pytest

from conftest import MSAICERR_PATH, CommonAssert

sys.path.append(MSAICERR_PATH)


@pytest.mark.parametrize("pointer", ["0xff8", "0x1020", "0x2000"])
def test_invalid_parser_offset_does_not_create_binary(
    mocker, monkeypatch, tmp_path, pointer
):
    from parse_tiling import parse_tiling_data
    from ms_interface.constant import Constant

    monkeypatch.chdir(tmp_path)
    text = "args(0 to 4) after execute:0x3000," + pointer + ",0x1,0x2"
    mocker.patch(
        "ms_interface.utils.get_inquire_result",
        side_effect=[[text], ["0x3000"], [], ["0x1000"]],
    )
    assert parse_tiling_data("/controlled/logs") == Constant.MS_AICERR_FIND_DATA_ERROR
    assert not list(tmp_path.glob("tilingdata_*.bin"))


def test_valid_parser_data_is_written_as_real_binary(mocker, monkeypatch, tmp_path):
    from parse_tiling import parse_tiling_data
    from ms_interface.constant import Constant

    monkeypatch.chdir(tmp_path)
    text = "args(0 to 3) after execute:0x3000,0x1010,0x1122334455667788,0x9"
    mocker.patch(
        "ms_interface.utils.get_inquire_result",
        # Four queries: args, IO pointer dump, [Dump][Exception] markers,
        # para base.  The dropped "begin to load normal tensor" query needed a
        # fifth return value, which is no longer consumed.
        side_effect=[[text], ["0x3000"], [], ["0x1000"]],
    )
    assert parse_tiling_data("/controlled/logs") == Constant.MS_AICERR_NONE_ERROR
    files = list(tmp_path.glob("tilingdata_*.bin"))
    assert len(files) == 1
    assert files[0].read_bytes() == struct.pack("<QQ", 0x1122334455667788, 9)


class TestParseTilingMethods(CommonAssert):
    def test_parse_tiling_data_writes_file(self, mocker):
        mock_parser = mocker.patch("parse_tiling.TilingDataParser")
        mock_instance = mock_parser.return_value
        mock_instance.parse.return_value = b"fake_tiling_data"
        mocker.patch("parse_tiling.open", mock_open())
        mocker.patch("parse_tiling.time")
        mocker.patch("parse_tiling.utils")

        from parse_tiling import parse_tiling_data
        from ms_interface.constant import Constant

        result = parse_tiling_data("/path/to/plog")
        self.assertEqual(result, Constant.MS_AICERR_NONE_ERROR)

    def test_parse_tiling_data_parser_called_with_plog(self, mocker):
        mock_parser = mocker.patch("parse_tiling.TilingDataParser")
        mock_instance = mock_parser.return_value
        mock_instance.parse.return_value = b"data"
        mocker.patch("parse_tiling.open", mock_open())
        mocker.patch("parse_tiling.time")
        mocker.patch("parse_tiling.utils")

        from parse_tiling import parse_tiling_data

        parse_tiling_data("/my/plog/file.log")
        mock_parser.assert_called_once_with("/my/plog/file.log")

    def test_main_with_tiling_data(self, mocker):
        mocker.patch("sys.argv", ["parse_tiling.py", "-t", "/path/to/plog"])
        mocker.patch("parse_tiling.parse_tiling_data", return_value=0)
        mocker.patch("parse_tiling.utils")

        from parse_tiling import main

        result = main()
        self.assertEqual(result, 0)

    def test_main_without_tiling_data(self, mocker):
        mocker.patch("sys.argv", ["parse_tiling.py"])
        mocker.patch("parse_tiling.utils")

        from parse_tiling import main
        from ms_interface.constant import Constant

        result = main()
        self.assertEqual(result, Constant.MS_AICERR_NONE_ERROR)

    def test_main_with_long_option(self, mocker):
        mocker.patch("sys.argv", ["parse_tiling.py", "--tiling_data", "/path/to/plog"])
        mocker.patch("parse_tiling.parse_tiling_data", return_value=0)
        mocker.patch("parse_tiling.utils")

        from parse_tiling import main

        result = main()
        self.assertEqual(result, 0)

    def test_parse_tiling_data_file_write_error(self, mocker):
        mock_parser = mocker.patch("parse_tiling.TilingDataParser")
        mock_instance = mock_parser.return_value
        mock_instance.parse.return_value = b"data"
        mocker.patch("parse_tiling.open", side_effect=OSError("Permission denied"))
        mocker.patch("parse_tiling.time")
        mocker.patch("parse_tiling.utils")

        from parse_tiling import parse_tiling_data
        from ms_interface.constant import Constant

        # A write failure is reported as an error code like every other
        # failure path, instead of letting the OSError reach the CLI.
        assert parse_tiling_data("/path/to/plog") == Constant.MS_AICERR_OPEN_FILE_ERROR
