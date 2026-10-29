#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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
import numpy as np

from ms_interface import utils
from ms_interface.constant import NOT_RUN_EXEC_FAILED, NOT_RUN_LAUNCH_FAILED
from ms_interface.single_op_test_frame.common.ascend_tbe_op import (
    AscendOpKernel,
    AscendOpKernelRunner,
    AscendOpKernelRunnerParam,
)
from ms_interface.dsmi_interface import DSMIInterface
from ms_interface.compile_file import get_compile_file


class GoldenOp:
    @staticmethod
    def get_block_dim(device_id):
        # 为vector算子所以查找core_count为block dim， 如果没有表示是aicore+vector芯片,则需要查找aicore个数
        block_dim = DSMIInterface().get_vector_core_count(device_id)
        if block_dim == 0:
            block_dim = DSMIInterface().get_aicore_count(device_id)
        return block_dim

    def run_golden_op(self, soc_version, device_id, temp_dir):
        build_result = get_compile_file(soc_version, temp_dir)
        if not build_result:
            return False
        build_bin, build_json = build_result
        # run golden op
        op_kernel = AscendOpKernel(build_bin, build_json)
        input_a = np.ones((256, 32), dtype=np.float16)
        input_b = np.ones((256, 32), dtype=np.float16)
        output_info = {
            "size": 16384,
            "dtype": "float16",
            "shape": (256, 32),
            "name": "output",
        }
        block_dim = self.get_block_dim(device_id)
        utils.print_debug_log("Start to run golden op. Please wait...")
        utils.print_debug_log(f"Block dim: {block_dim}")
        ascend_op_param = AscendOpKernelRunnerParam(
            kernel=op_kernel,
            inputs=[input_a, input_b],
            actual_out_info=(output_info,),
            tiling_key=0,
            block_dim=block_dim,
        )
        with AscendOpKernelRunner(device_id=device_id) as runner:
            ret = runner.run(ascend_op_param)
            if not isinstance(ret, str) or not ret:
                utils.print_error_log(
                    "Golden op runner returned an invalid execution report."
                )
                return False
            if NOT_RUN_EXEC_FAILED in ret or NOT_RUN_LAUNCH_FAILED in ret:
                return False
        return True


if __name__ == "__main__":
    RESULT = GoldenOp().run_golden_op(sys.argv[1], int(sys.argv[2]), sys.argv[3])
    if RESULT:
        utils.print_debug_log("Run golden op successfully.")
        sys.exit(0)
    else:
        utils.print_debug_log("Run golden op failed.")
        sys.exit(-1)
