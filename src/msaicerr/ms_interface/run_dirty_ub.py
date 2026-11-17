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
from pathlib import Path

from ms_interface import utils
from ms_interface.constant import ModeCustom
from ms_interface.single_op_test_frame.common.ascend_tbe_op import (
    AscendOpKernel,
    AscendOpKernelRunner,
    AscendOpKernelRunnerParam,
)


def run_dirty_ub_tik(configs, soc_version, device_id):
    try:
        from tbe import tik
        from tbe.common import platform as cce
        from tbe.common.platform import set_current_compile_soc_info as te_set_version
    except (ImportError, AttributeError) as e:
        utils.print_warn_log(
            f"failed to import te or tbe to compile op dirty_ub, skipped it. error: {e}"
        )
        return False
    build_dir = Path(configs.get("compile_temp_dir"))
    utils.check_path_valid(str(build_dir), isdir=True, output=True)
    te_set_version(soc_version)
    ub_size = cce.get_soc_spec("UB_SIZE")
    tik_instance = tik.Tik()
    output_gm = tik_instance.Tensor(
        "float32", (1,), name="output_gm", scope=tik.scope_gm
    )
    all_ub = tik_instance.Tensor(
        "float32", (ub_size // 4,), name="all_ub", scope=tik.scope_ubuf
    )
    with tik_instance.for_range(0, ub_size // 256) as loop_idx:
        tik_instance.vec_dup(64, all_ub[loop_idx * 64], 1.7976931348623157e30, 1, 8)
    kernel_name = ModeCustom.DIRTY_CUSTOM.value
    tik_instance.BuildCCE(
        kernel_name=kernel_name,
        inputs=[],
        outputs=[output_gm],
        output_files_path=str(build_dir),
    )
    build_bins, build_jsons = (
        list(build_dir.rglob(f"{kernel_name}*.o")),
        list(build_dir.rglob(f"{kernel_name}*.json")),
    )
    if not (build_bins and build_jsons):
        utils.print_warn_log("The file generated after compilation does not exist.")
        return False

    bin_path = str(build_bins[0])
    json_path = str(build_jsons[0])
    # Step 4. run dirty_ub kernel
    utils.print_info_log(f"Find bin_file {bin_path} and json_file {json_path}")
    op_kernel = AscendOpKernel(bin_path, json_path)
    # kernel without output can not run
    output_info = {"size": 4, "dtype": "float32", "shape": (1,)}
    ascend_op_param = AscendOpKernelRunnerParam(
        kernel=op_kernel, actual_out_info=(output_info,)
    )
    with AscendOpKernelRunner(device_id=device_id) as runner:
        runner.run(ascend_op_param)
    return True


def run_dirty_ub(configs, soc_version, device_id):
    handlers = utils.load_ascend_handlers()
    for handler in handlers:
        if handler.is_chip_handler(soc_version):
            return handler.run_dirty_ub(configs, soc_version, device_id)
    return run_dirty_ub_tik(configs, soc_version, device_id)
