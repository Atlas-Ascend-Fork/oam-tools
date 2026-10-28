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

import time
from pathlib import Path
import os
import sys
import pytest

FILE_PATH = os.path.dirname(os.path.realpath(__file__))
MSAICERR_PATH = os.path.join(FILE_PATH, "../../../../src/msaicerr")
RES_PATH = Path(FILE_PATH).joinpath("../res")
TEST_CASE_TMP = Path(FILE_PATH).joinpath("../test_tmp")
CUR_TIME_STR = time.strftime("%Y%m%d%H%M%S", time.localtime())
ORIGINAL_DIR = os.getcwd()
cur_abspath = os.path.dirname(__file__)
ori_data_path = Path(cur_abspath).joinpath("../res/ori_data/")

AICORE_KERNEL_EXECUTE_FAILED = "[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:08.360.397 [stream.cc:1078]1592077 GetError:[INIT][DEFAULT]Aicore kernel execute failed, device_id=0, stream_id=42, report_stream_id=42, task_id=1, flip_num=0, fault kernel_name=FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic, fault kernel info ext=FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic, program id=0, hash=1208019939949783628."
AICORE_KERNEL_EXECUTE_FAILED_2 = "[ERROR] RUNTIME(370,python3):2023-07-13-07:42:40.565.016 [stream.cc:1193]1432 GetError:[EXEC][EXEC]Aicore kernel execute failed, device_id=0, stream_id=2, report_stream_id=2, task_id=6, flip_num=0, fault kernel_name=2_0_11_GatherV2, program id=1, hash=15656883929986130445."
GE_DUMP_EXCEPTION_TO_FILE_L1 = (
    "[ERROR] GE(1582604,python3):2024-12-06-15:17:06.252.046 [exception_dumper.cc:424]1582604 DumpNodeInf"
    "o: ErrorNo: 4294967295(failed) [INIT][DEFAULT][Dump][Exception] dump exception to file, file: /home/"
    "donghongru/aic_test/dump/extra-info/data-dump/1/GatherV2.GatherV21.1.1733469426252033"
)
DUMP_EXCEPTION_TO_FILE = (
    "[ERROR] IDEDD(1592077,python3):2024-09-12-16:40:08.360.226 [dump_args.cpp:807][tid:1592077] [Dump][E"
    "xception] dump exception to file, file: ./new/extra-info/data-dump/0/exception_info.42.1.17261592074"
    "69285"
)
DUMP_CUSTOM_EXCEPTION_TO_FILE = (
    "[ERROR] IDEDD(1592077,python3):2024-09-12-16:40:08.360.500 [dump_args.cpp:807][tid:1592077] [Dump][E"
    "xception] dump custom exception to file, file: ./new/extra-info/data-dump/0/exception_info.42.1.1726"
    "159207469285.custom.1726159207469500"
)
os.environ["PYTHONPATH"] = ""
sys.path.append(MSAICERR_PATH)


class CommonAssert:
    @staticmethod
    def assertEqual(received, expected):
        assert received == expected

    @staticmethod
    def assertNotEqual(received, expected):
        assert received != expected

    @staticmethod
    def assertIn(received, expected):
        assert expected in received

    @staticmethod
    def assertNotIn(received, expected):
        assert expected not in received


def make_mock_device():
    """Return a fresh Runtime double without importing another test module."""
    from unittest.mock import Mock
    import ctypes

    device = Mock()
    device.malloc.side_effect = lambda *_: ctypes.c_void_p(4096)
    device.copy_bin_to_hbm.return_value = ctypes.c_void_p(8192)
    device.memcpy.return_value = 0
    device.free.return_value = 0
    device.get_c2c_ctrl_addr.return_value = ctypes.c_void_p(12288)
    device.launch_kernel.return_value = 0
    device.synchronize_with_stream.return_value = 0
    device.register_device_binary_kernel.return_value = Mock()
    device.register_function.return_value = ctypes.c_void_p(16384)
    return device


@pytest.fixture
def kernel_mock_device():
    return make_mock_device()
