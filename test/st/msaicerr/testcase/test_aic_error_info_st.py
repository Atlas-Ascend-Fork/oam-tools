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

import struct
import unittest
from unittest.mock import patch

# conftest 已把 MSAICERR_PATH 加入 sys.path，且其导入早于下面的 ms_interface
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.constant import RetCode
from ms_interface.utils import ExceptionRootCause


class TestUtilsMethods(unittest.TestCase):
    def test_get_conclusion_pc_err(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = True
        aicerr_info.flag_check = False
        aicerr_info.rts_block_dim = 40
        aicerr_info.driver_aicore_num = 20
        aicerr_info.data_dump_result = True
        aicerr_info.aic_error_info["current_pc"] = "0x0"
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res, "The line number of the operator error instruction is 0.\n"
        )

    def test_get_conclusion_data_invalid(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = True
        aicerr_info.flag_check = False
        aicerr_info.rts_block_dim = 40
        aicerr_info.driver_aicore_num = 20
        aicerr_info.data_dump_result = True
        aicerr_info.aic_error_info["current_pc"] = "0x1"
        aicerr_info.atomic_add_err = False
        aicerr_info.dump_info = "data invalid"
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res,
            "The maintenance and test information is insufficient or the format is incorrect, contact technical support.\n",
        )

    def test_block_dim(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = True
        aicerr_info.flag_check = False
        aicerr_info.rts_block_dim = 41
        aicerr_info.driver_aicore_num = 20
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res,
            "The number of AI Cores in the environment is less than that required by the operator.\n",
        )

    def test_atomic_clean_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = False
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res,
            "The memset or atomic_clean operator is not inserted before this operator in the graph, while memory cleanup is required before operator execution.\n",
        )

    def test_flag_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = True
        aicerr_info.flag_check = True
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res,
            "The set_flag and wait_flag instructions are not used together in the operator code.\n",
        )

    @patch("builtins.open")
    def test_tiling_data(self, mock_open_func):
        aicerr_info = AicErrorInfo()
        aicerr_info.tiling_data = "tiling data"
        mock_file = mock_open_func.return_value.__enter__.return_value
        mock_file.read.return_value = struct.pack("q", int("1234567891234567"))
        res = getattr(aicerr_info, "_get_tiling_str")()
        self.assertIn("tiling data in int32: [1016835847, 287445]", res)
        self.assertIn("tiling data in int64: [1234567891234567]", res)
        self.assertIn(
            "tiling data in float16: [-0.10980224609375, 1.1513671875, 874.5, 2.384185791015625e-07]",
            res,
        )

    def test_args_result_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.check_args_result = False
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            True,
            "If the arguments are inconsistent before and after operator execution"
            in res,
        )

    def test_abnormal_addr_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.addr_valid = False
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            True, "The input/output memory address of the operator is abnormal" in res
        )
        aicerr_info2 = AicErrorInfo()
        aicerr_info2.data_dump_result = False
        res2 = aicerr_info2.get_conclusion()
        self.assertEqual(
            True, "The input/output memory address of the operator is abnormal" in res2
        )

    def test_env_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.env_available = False
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res,
            "Failed to execute the built-in sample operator. Check the environment.\n",
        )

    def test_single_op_exec_succ(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.single_op_test_result = RetCode.SUCCESS
        res = aicerr_info.get_conclusion()
        self.assertEqual(True, "the AI Core error was not reproduced" in res)

    def test_internal_err(self):
        ExceptionRootCause().causes = []
        aicerr_info = AicErrorInfo()
        res = aicerr_info.get_conclusion()
        self.assertEqual(res, "Internal error. Contact technical support.\n")

        aicerr_info = AicErrorInfo()
        ExceptionRootCause().causes.append("Can not find xxx")
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            True,
            "The maintenance and test information is insufficient or the format is incorrect"
            in res,
        )
