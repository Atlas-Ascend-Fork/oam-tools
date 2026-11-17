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

import json
import os.path
import sys
import time
from pathlib import Path
import platform

FILE_PATH = os.path.dirname(os.path.realpath(__file__))
MSAICERR_PATH = os.path.join(FILE_PATH, "../../../../src/msaicerr")
# conftest 早于同目录测试模块加载，在此统一入 sys.path，
# 用例文件即可把 ms_interface 的 import 写在顶部（无需 E402 豁免）。
if MSAICERR_PATH not in sys.path:
    sys.path.append(MSAICERR_PATH)
RES_PATH = Path(FILE_PATH).joinpath("../res")
TEST_CASE_TMP = Path(FILE_PATH).joinpath("../test_tmp")
CUR_TIME_STR = time.strftime("%Y%m%d%H%M%S", time.localtime())
ORIGINAL_DIR = os.getcwd()
cur_abspath = os.path.dirname(__file__)
ori_data_path = Path(cur_abspath).joinpath("../res/ori_data/")

# 关键词
DUMP_EXCEPTION_STR = "[ERROR] IDEDD(1592077,python3):2024-09-12-16:40:07.468.927 [dump_args.cpp:548][tid:1592077] [Dump][Exception] the begin tensor's index of arg is:0, args dump count[17]"
FFTS_PLUS_TASK_EXECUTE_FAILED = "fftsplus task execute failed, device_id=0, stream_id=2, report_stream_id=2, task_id=6, flip_num=0, fault kernel_name=2_0_11_GatherV2, program id=1."
AIC_INFO_DEV_FUNC = "[AIC_INFO] dev_func:te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1__kernel0"
EXCEPTION_INFO_DUMP_ARGS_DATA = (
    "exception info dump args data, addr:0x12c200000000; size:268448256 bytes"
)
L1_DUMP_EXCEPTION_TO_FILE = (
    "[ERROR] GE(1582604,python3):2024-12-06-15:17:06.252.046 [exception_dumper.cc:424]1582604 DumpNodeInf"
    "o: ErrorNo: 4294967295(failed) [INIT][DEFAULT][1] dump exception to file, file: /home/donghongru/aic"
    "_test/dump/extra-info/data-dump/0/GatherV2.GatherV21.1.1733469426252033"
)
L0_DUMP_EXCEPTION_TO_FILE0 = (
    "[ERROR] IDEDD(1592077,python3):2024-09-12-16:40:08.360.226 [dump_args.cpp:807][tid:1592077] [1] dump"
    " exception to file, file: ./new/extra-info/data-dump/0/exception_info.42.1.1726159207469285"
)
AIC_INFO_NODE_NAME = (
    ":[AIC_INFO] node_name:GatherV2, node_type:GatherV2, stream_id:2, task_id:6"
)
AICORE_KERNEL_EXECUTE_FAILED = "Aicore kernel execute failed, device_id=0, stream_id=42, report_stream_id=42, task_id=1, flip_num=0, fault kernel_name=FlashAttentionScore_1_mix_aic, fault kernel info ext=FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic, program id=0, hash=1208019939949783628."
ERROR_INFO = "[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:07.362.023 [device_error_proc.cc:1402]1592077 ProcessStarsCoreErrorInfo:[INIT][DEFAULT]The error from device(chipId:0, dieId:0), serial number is 87, there is an fftsplus aivector error exception, core id is 0, error code = 0, dump info: pc start: 0x12c042d73754, current: 0x12c042d75b18, vec error info: 0x99000000a2, mte error info: 0x5003000031, ifu error info: 0x200000007ffc0, ccu error info: 0x280d00000084, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12c040569000."
RUNTIME_BLOCK_DIM = "[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:07.468.854 [davinci_kernel_task.cc:1122]1592077 GetArgsInfo:[INIT][DEFAULT]tilingKey = 10000000000022420943, print 16 Times totalLen=(308*8)Bytes, argsSize=2464, blockDim=20"
THE_EXTEND_INFO_ERRCODE = "[ERROR] RUNTIME(588579,execute_add_op):2025-04-02-07:19:26.376.635 [device_error_proc.cc:1446]588579 ProcessStarsCoreErrorInfo:The extend info: errcode:(0x200000000, 0, 0) errorStr: The write address of the MTE instruction is out of range. fixp_error0 info: 0x6a, fixp_error1 info: 0xb9, fsmId:0, tslot:1, thread:0, ctxid:0, blk:2, sublk:0, subErrType:4."
HASH = "Aicore kernel execute failed, device_id=0, stream_id=2, report_stream_id=2, task_id=1, flip_num=0, fault kernel_name=GatherV3_9e31943a1a48bf81ddff1fc6379e0be3_high_performance_10330, fault kernel info ext=none, program id=0, hash=9005124917278870274."
AIC_INFO_TILING_KEY = "[INFO] GE(370,python3):2023-07-13-07:42:40.520.747 [exception_dumper.cc:277]1432 LogExceptionTvmOpInfo:[AIC_INFO] tiling_key:0"
AIC_INFO_BLOCK_DIM = "[INFO] GE(370,python3):2023-07-13-07:42:40.519.087 [exception_dumper.cc:270]1432 LogExceptionTvmOpInfo:[AIC_INFO] block_dim:32"
AIC_INFO_ARGS_AFTER_EXC = "[AIC_INFO] args(0 to 12) after execute:0x12c0c0013000, 0x12c0c001c000, 0x12c0c0025000, 0, 0x12c100010038, 0x12c0c0011000, 0, 0x800004000, 0xa5a5a5a500000000, 0, 0, 0"
AIC_INFO_ARGS_BEFORE_EXC = "[AIC_INFO] args before execute: 20068234969088, 20068234838016, 20068234903552, 20068235034624, 20069311840368, 20068234825728, 0, 0, 0, 0, 0, 0, 0, 20068234825728, 4, 1, 64, 1, 2, 0, 1, 0, 2, 0, 0, 19712, 2, 19712, 0, 1, 19712, 2, 0, 64, 0, 0, 0, 0, 1, 1, 0, 1, , addr:0xfff4543002f0"
ATOMICLAYNCHKERNELWITHFLAG = "AtomicLaunchKernelWithFlag_GatherV2"

# 异常关键词
AIC_INFO_DEV_FUNC_ERROR = "[AIC_INFO] dev_func:te_gatherv2_1__?kernel0."
AIC_INFO_NODE_NAME_ERROR = "[AIC_INFO] node_name:GatherV2."
AICORE_KERNEL_EXECUTE_FAILED_ERROR = "Aicore kernel execute failed, device_id=0, stream_id=42, report_stream_id=42, task_id=1, flip_num=0, fault kernel_name FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic, fault kernel info ext=FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic, program id=0, hash=1208019939949783628."
FFTS_PLUS_TASK_EXECUTE_FAILED_ERROR = "fftsplus task execute failed,"
SK_DUMP_CALLBACK_EXCEPTION = (
    "[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:08.360.500 [task.cc:600]1592077 PrintInfo:"
    "[Dump][Exception] Begin to dump callback exception. coreType=0, coreId=1, argAddr=0x12c200000000, "
    "argSize=64, binHandle=0x12c200000100, extraTensorNum=2, kernelName=Add_sk_kernel_900016000."
)

# ge 文件名
GE_GRAPH_FILE = "ge_proto_test_Build.txt"


class CommonAssert:
    @staticmethod
    def assertEqual(received, expected):
        assert received == expected

    @staticmethod
    def assertIn(received, expected):
        assert expected in received

    @staticmethod
    def assertNotIn(received, expected):
        assert expected not in received


def mkdir_dump_file_path(node_name: str, input_path: Path):
    dump_path = input_path.joinpath("extra-info/data-dump/0/")
    dump_path.mkdir(parents=True, exist_ok=True)
    dump_path.joinpath(f"{node_name}").touch(exist_ok=True)
    dump_path.joinpath("te_gatherv2.o").touch(exist_ok=True)
    dump_path.joinpath("te_gatherv2_host.o").touch(exist_ok=True)


def write_log_keyword_to_file(file_path: Path, keywords: list, file_name="test"):
    keyword_str = ""
    for keyword in keywords:
        keyword_str += keyword + "\n"
    file_path.joinpath(f"plog_{file_name}.txt").write_text(
        keyword_str, encoding="utf-8"
    )


def mkdir_o_json_file(kernel_name: str, input_path: Path):
    input_path.mkdir(parents=True, exist_ok=True)
    input_path.joinpath(f"{kernel_name}.o").touch()
    json_path = input_path.joinpath(f"{kernel_name}.json")
    data = {"compileInfo": {}, "parameters": ["null", "null"]}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def make_cce_obj_dump_file(current_path: Path):
    tools_path = current_path.joinpath("tools")
    tools_path.mkdir(parents=True, exist_ok=True)
    if "aarch64" in platform.machine():
        tools_path.joinpath("cce-objdump_aarch64").touch()
    else:
        tools_path.joinpath("cce-objdump").touch()
