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

import pytest

from conftest import MSAICERR_PATH, CommonAssert

sys.path.append(MSAICERR_PATH)


class TestTestSingleOpMethods(CommonAssert):
    def test_config_structure(self, mocker):
        mocker.patch(
            "ms_interface.single_op_test_frame.single_op_case.SingleOpCase.run"
        )
        from test_single_op import config

        expected_keys = [
            "cce_file",
            "bin_path",
            "json_path",
            "tiling_data",
            "tiling_key",
            "block_dim",
            "device_id",
            "ffts_addrs_num",
            "input_file_list",
            "output_file_list",
            "kernel_name",
            "compile_temp_dir",
        ]
        for key in expected_keys:
            self.assertIn(config, key)

    def test_config_values(self, mocker):
        mocker.patch(
            "ms_interface.single_op_test_frame.single_op_case.SingleOpCase.run"
        )
        from test_single_op import config

        assert isinstance(config["block_dim"], int)
        assert isinstance(config["device_id"], int)
        assert isinstance(config["input_file_list"], list)
        assert isinstance(config["output_file_list"], list)
        assert isinstance(config["kernel_name"], str)

    def test_op_test_constant(self, mocker):
        mocker.patch(
            "ms_interface.single_op_test_frame.single_op_case.SingleOpCase.run"
        )
        from test_single_op import OP_TEST

        self.assertEqual(OP_TEST, "single_op")

    @pytest.mark.skip
    def test_single_op_case_run(self, mocker):
        mocker.patch(
            "ms_interface.single_op_test_frame.single_op_case.SingleOpCase.run"
        )
        from test_single_op import config, OP_TEST
        from ms_interface.single_op_test_frame.single_op_case import SingleOpCase

        SingleOpCase.run(config, OP_TEST)
        SingleOpCase.run.assert_called_once()
