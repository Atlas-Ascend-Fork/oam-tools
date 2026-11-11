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
import numpy as np
from ms_interface import utils
from ms_interface.ascend950.compile_op import CompileOP
from ms_interface.constant import ModeCustom
from ms_interface.single_op_test_frame.common.ascend_tbe_op import (
    AscendOpKernel,
    AscendOpKernelRunner,
    AscendOpKernelRunnerParam,
)


class AscendHandlerBase:
    handle_chip_pre = ""
    # 传给 msopgen 编译（-c ai_core-<chip>）的芯片名；为 None 时与 handle_chip_pre 一致。
    # 裁剪版芯片复用母片编译流程时覆写（如 Ascend350 复用 Ascend950）。
    compile_chip = None

    def get_compile_chip(self):
        return self.compile_chip or self.handle_chip_pre

    def run_dirty_ub(self, configs, soc_version, device_id):
        # Step 1. get soc_version to compile dirty_ub
        utils.print_info_log(f"get soc_version of {soc_version}.")
        inputs = [
            {
                "name": "x",
                "param_type": "required",
                "format": ["ND"],
                "type": ["float32"],
            }
        ]
        outputs = [
            {
                "name": "z",
                "param_type": "required",
                "format": ["ND"],
                "type": ["float32"],
            }
        ]
        compile_op = CompileOP(
            ModeCustom.DIRTY_CUSTOM.value,
            inputs,
            outputs,
            soc_version,
            self.get_compile_chip(),
        )
        ub_num = compile_op.get_ub_size()
        if ub_num == 0:
            utils.print_warn_log("Get ub size failed, skip dirty ub")
            return False
        # Step 2. compile dirty_ub kernel
        try:
            build_result = compile_op.get_compile_file(configs.get("compile_temp_dir"))
        except (
            OSError,
            TypeError,
            ValueError,
            RuntimeError,
            utils.AicErrException,
        ) as e:
            utils.print_warn_log(
                f"Compile dirty_ub op failed, skip dirty ub. Error Detail: {e}."
            )
            return False

        # Step 3. find dirty_ub kernel
        if not build_result:
            utils.print_warn_log("Compile dirty_ub op failed, skip dirty ub")
            return False
        bin_path, json_path = build_result
        # Step 4. run dirty_ub kernel
        utils.print_info_log(f"Find bin_file {bin_path} and json_file {json_path}")
        op_kernel = AscendOpKernel(bin_path, json_path)
        # kernel without output can not run
        output_info = {"size": 4, "dtype": "float32", "shape": (1,)}
        input_a = np.full((ub_num,), 1.7976931348623157e30, dtype=np.float32)
        ascend_op_param = AscendOpKernelRunnerParam(
            kernel=op_kernel,
            inputs=[
                input_a,
            ],
            actual_out_info=(output_info,),
            tiling_key=0,
            block_dim=1,
        )
        with AscendOpKernelRunner(device_id=device_id) as runner:
            runner.run(ascend_op_param)
        return True

    def get_compile_file(self, soc_version, temp_dir):
        inputs = [
            {
                "name": "x",
                "param_type": "required",
                "format": ["ND"],
                "type": ["float16"],
            },
            {
                "name": "y",
                "param_type": "required",
                "format": ["ND"],
                "type": ["float16"],
            },
        ]
        outputs = [
            {
                "name": "z",
                "param_type": "required",
                "format": ["ND"],
                "type": ["float16"],
            }
        ]
        build_result = CompileOP(
            ModeCustom.ADD_CUSTOM.value,
            inputs,
            outputs,
            soc_version,
            self.get_compile_chip(),
        ).get_compile_file(temp_dir)
        return build_result

    def is_chip_handler(self, soc_version):
        return soc_version.startswith(self.handle_chip_pre)
