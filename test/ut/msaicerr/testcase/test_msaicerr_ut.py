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

from ms_interface.constant import Constant
import parse_tiling
import msaicerr
from conftest import MSAICERR_PATH, CommonAssert
import os
import pytest
import sys
from io import StringIO
import shutil
from unittest.mock import Mock

te = Mock(name="te")
te.__name__ = "te"
sys.modules["te"] = te
sys.path.append(MSAICERR_PATH)

REPORT_PATH_APPLOG = os.path.join(
    os.path.dirname(__file__), "../res/ori_data/2020-12-24-01-13-01/"
)
REPORT_PATH_TRAIN = os.path.join(
    os.path.dirname(__file__), "../res/ori_data/2020-12-24-01-13-03/"
)
REPORT_DOES_NOT_MATCH = os.path.join(
    os.path.dirname(__file__), "../res/ori_data/2020-12-24-01-13-04/"
)
COMPILE_PARH = os.path.join(os.path.dirname(__file__), "../res/ori_data/complie_path/")
COMPILE_PARH_TRAIN = os.path.join(
    os.path.dirname(__file__), "../res/ori_data/complie_path_train/aic_error/"
)
ST_OUTPUT = os.path.join(os.path.dirname(__file__), "../res/output/")
ASYS_OUTPUT = os.path.join(
    os.path.dirname(__file__), "../res/ori_data/asys_output_20230713074104794/"
)
EMPTY_TENSOR_ASYS_OUTPUT = os.path.join(
    os.path.dirname(__file__), "../res/ori_data/asys_output_20240912164014957/"
)
INVALID_TILING_DATA_PATH = os.path.join(
    os.path.dirname(__file__),
    "../res/ori_data/asys_output_20240912164014957/dfx/log/host/cann/debug/plog/invalid-tiling-test.log",
)

TILIGN_DATA_PARH = os.path.join(
    os.path.dirname(__file__),
    "../res/ori_data/asys_output_20240912164014957/dfx/log/host/cann/debug/plog/plog-1592007_20240912164003456.log",
)


def _clear_out_path(out_path):
    path = os.path.relpath(out_path)
    if os.path.exists(path):
        shutil.rmtree(path)
    if not os.path.exists(path):
        os.makedirs(path)


class DSMIInterface:
    def __init__(self):
        self.dsmidll = None

    def verify_device_id(self) -> int:
        return 1


class TestUtilsMethods(CommonAssert):
    @pytest.fixture(autouse=True)
    def clear_outpath(self):
        os.environ["ASCEND_OPP_PATH"] = "/"
        _clear_out_path(ST_OUTPUT)

    def test_msaicerr_success(self, mocker):
        args = ["msaicerr.py", "-p", ASYS_OUTPUT, "-out", ST_OUTPUT]
        mocker.patch("sys.argv", args)
        mocker.patch("ms_interface.aicore_error_parser.AicoreErrorParser._decompile")
        mocker.patch("shutil.which", return_value="/home/cce-objdump")
        mocker.patch(
            "ms_interface.aicore_error_parser.AicoreErrorParser._get_data_dump_result",
            return_value=False,
        )
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        mocker.patch(
            "ms_interface.aicore_error_parser."
            "AicoreErrorParser.collect_driver_aicore_number",
            return_value=24,
        )
        success_code = msaicerr.main()
        self.assertEqual(success_code, 8)

    def test_empty_tensor_success(self, mocker):
        args = ["msaicerr.py", "-p", EMPTY_TENSOR_ASYS_OUTPUT, "-out", ST_OUTPUT]
        mocker.patch("sys.argv", args)
        mocker.patch("ms_interface.aicore_error_parser.AicoreErrorParser._decompile")
        mocker.patch("shutil.which", return_value="/home/cce-objdump")
        mocker.patch(
            "ms_interface.aicore_error_parser.AicoreErrorParser._get_data_dump_result",
            return_value=False,
        )
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        mocker.patch(
            "ms_interface.aicore_error_parser."
            "AicoreErrorParser.collect_driver_aicore_number",
            return_value=24,
        )
        success_code = msaicerr.main()
        self.assertEqual(success_code, 8)

    def test_invalid_tiling_data_param(self, mocker):
        DSMIInterface()
        args = ["parse_tiling.py", "-t", INVALID_TILING_DATA_PATH]
        mocker.patch("sys.argv", args)
        error_code = parse_tiling.main()
        self.assertEqual(error_code, 0)

    def test_tiling_data_param(self, mocker):
        DSMIInterface()
        args = ["parse_tiling.py", "-t", TILIGN_DATA_PARH]
        mocker.patch("sys.argv", args)
        error_code = parse_tiling.main()
        self.assertEqual(error_code, 0)

    def test_path_invalid(self, mocker):
        args = ["msaicerr.py", "-p", "./"]
        mocker.patch("sys.argv", args)
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        error_code = msaicerr.main()
        self.assertEqual(error_code, Constant.MS_AICERR_INVALID_PATH_ERROR)

    def test_path_with_same_prefix_is_not_sub_path(self, tmp_path):
        self.assertEqual(
            msaicerr.is_sub_path(
                str(tmp_path / "report_output"), str(tmp_path / "report")
            ),
            False,
        )
        self.assertEqual(
            msaicerr.is_sub_path(
                str(tmp_path / "report/output"), str(tmp_path / "report")
            ),
            True,
        )

    def test_environment_invalid(self, mocker):
        args = ["msaicerr.py", "-p", ASYS_OUTPUT]
        os.environ["ASCEND_OPP_PATH"] = ""
        mocker.patch("sys.argv", args)
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        error_code = msaicerr.main()
        self.assertEqual(error_code, Constant.MS_AICERR_INVALID_PATH_ERROR)

    def test_no_param(self, mocker):
        args = ["msaicerr.py"]
        mocker.patch("sys.argv", args)
        error_code = msaicerr.main()
        self.assertEqual(error_code, 1)

    def test_parse_dump_data_with_dir(self, mocker):
        args = ["msaicerr.py", "-d", ASYS_OUTPUT]
        mocker.patch("sys.argv", args)
        mock_stdout = mocker.patch("sys.stdout", new_callable=StringIO)
        msaicerr.main()
        self.assertEqual("is not a file" in mock_stdout.getvalue(), True)

    def test_parse_dump_data(self, mocker):
        args = ["msaicerr.py", "-d", TILIGN_DATA_PARH]
        mocker.patch("sys.argv", args)
        mock_stdout = mocker.patch("sys.stdout", new_callable=StringIO)
        mocker.patch(
            "ms_interface.dump_data_parser.DumpDataParser.parse", return_value=None
        )
        msaicerr.main()
        self.assertEqual(
            "The dump file directory will be used to as the output"
            in mock_stdout.getvalue(),
            True,
        )

    def test_parse_dump_data_npy(self, mocker):
        npy_file = os.path.join(
            os.path.dirname(__file__), "../res/ori_data/dump_data/invalid.npy"
        )
        args = ["msaicerr.py", "-d", npy_file]
        mocker.patch("sys.argv", args)
        mock_stdout = mocker.patch("sys.stdout", new_callable=StringIO)
        msaicerr.main()
        self.assertEqual(
            "The dump file cannot be an npy file." in mock_stdout.getvalue(), True
        )

    def test_check_env_invalid_dev(self, mocker):
        args = ["msaicerr.py", "-e", "-dev", "6"]
        mocker.patch("sys.argv", args)
        mock_stdout = mocker.patch("sys.stdout", new_callable=StringIO)
        mocker.patch("msaicerr.verify_device_id", return_value=False)
        msaicerr.main()
        self.assertEqual("Invalid device_id 6" in mock_stdout.getvalue(), True)

    def test_check_env_success(self, mocker):
        args = ["msaicerr.py", "-e"]
        mocker.patch("sys.argv", args)
        mock_stdout = mocker.patch("sys.stdout", new_callable=StringIO)
        mocker.patch("msaicerr.get_soc_version", return_value="")
        mocker.patch(
            "ms_interface.aicore_error_parser.AicoreErrorParser.run_test_env",
            return_value=True,
        )
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        msaicerr.main()
        self.assertEqual(
            "The built-in sample operator runs successfully, The environment is normal."
            in mock_stdout.getvalue(),
            True,
        )

    def test_check_env_fail(self, mocker):
        args = ["msaicerr.py", "-e"]
        mocker.patch("sys.argv", args)
        mock_stdout = mocker.patch("sys.stdout", new_callable=StringIO)
        mocker.patch("msaicerr.get_soc_version", return_value="")
        mocker.patch(
            "ms_interface.aicore_error_parser.AicoreErrorParser.run_test_env",
            return_value=False,
        )
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        msaicerr.main()
        self.assertEqual(
            "See the detailed error logs above" in mock_stdout.getvalue(), True
        )

    def test_only_dev(self, mocker):
        args = ["msaicerr.py", "-dev", "0"]
        mocker.patch("sys.argv", args)
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        mock_stderr = mocker.patch("sys.stderr", new_callable=StringIO)
        try:
            msaicerr.main()
        except SystemExit:
            pass
        self.assertEqual(
            "-dev must be used with -p/--report_path or -e/--env"
            in mock_stderr.getvalue(),
            True,
        )

    def test_only_dev_before(self, mocker):
        args = ["msaicerr.py", "-dev", "0", "-d", "xxx"]
        mocker.patch("sys.argv", args)
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        mock_stderr = mocker.patch("sys.stderr", new_callable=StringIO)
        try:
            msaicerr.main()
        except SystemExit:
            pass
        self.assertEqual(
            "-dev must be used with -p/--report_path or -e/--env"
            in mock_stderr.getvalue(),
            True,
        )

    def test_only_out(self, mocker):
        args = ["msaicerr.py", "-out", "xxx"]
        mocker.patch("sys.argv", args)
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        mock_stderr = mocker.patch("sys.stderr", new_callable=StringIO)
        try:
            msaicerr.main()
        except SystemExit:
            pass
        self.assertEqual(
            "msaicerr.py: error: -out must be used with -p/--report_path or -d/--data"
            in mock_stderr.getvalue(),
            True,
        )

    def test_unknown_arg(self, mocker):
        args = ["msaicerr.py", "-foo", "-bar"]
        mocker.patch("sys.argv", args)
        mocker.patch("msaicerr.verify_device_id", return_value=True)
        mock_stdout = mocker.patch("sys.stdout", new_callable=StringIO)
        msaicerr.main()
        self.assertEqual(
            "Invalid argument ['-foo', '-bar'], please run help to check the usage"
            in mock_stdout.getvalue(),
            True,
        )
