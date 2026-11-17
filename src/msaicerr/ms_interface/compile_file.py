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


def get_compile_from_tik(soc_version, compile_temp_dir):
    try:
        from tbe.common.platform import set_current_compile_soc_info as te_set_version
        from tbe import tik
    except (ImportError, AttributeError) as e:
        utils.print_warn_log(
            f"failed to import te or tbe to compile op golden op, skipped it. error: {e}"
        )
        return []
    build_dir = Path(compile_temp_dir).joinpath(
        ModeCustom.ADD_CUSTOM.value, "build_out", "op_kernel"
    )
    utils.check_path_valid(str(build_dir), isdir=True, output=True)
    te_set_version(soc_version)
    m = 256
    n = 32
    k = 128
    tik_instance = tik.Tik()

    input_a = tik_instance.Tensor("float16", (m, n), name="a", scope=tik.scope_gm)
    input_b = tik_instance.Tensor("float16", (n, k), name="b", scope=tik.scope_gm)

    input_a_ub = tik_instance.Tensor(
        "float16", (m, n), name="a_ub", scope=tik.scope_ubuf
    )
    input_b_ub = tik_instance.Tensor(
        "float16", (m, n), name="b_ub", scope=tik.scope_ubuf
    )
    output_ub = tik_instance.Tensor(
        "float16", (m, k), name="out_ub", scope=tik.scope_ubuf
    )
    output_gm = tik_instance.Tensor(
        "float16", (m, k), name="out_ub", scope=tik.scope_gm
    )

    index_scalar = tik_instance.Scalar("int32", init_value=0)
    tik_instance.data_move(input_a_ub, input_a[index_scalar], 0, 1, 32, 0, 0)
    tik_instance.data_move(input_b_ub, input_b, 0, 1, 32, 0, 0)
    tik_instance.vabs(64, output_ub, output_ub, 1, 1, 1, 8, 8)
    tik_instance.data_move(output_gm, output_ub, 0, 1, 1, 0, 0)

    kernel_name = ModeCustom.ADD_CUSTOM.value
    tik_instance.BuildCCE(
        kernel_name,
        inputs=[input_a, input_b],
        outputs=[output_gm],
        output_files_path=str(build_dir),
    )
    build_bins, build_jsons = (
        list(build_dir.rglob(f"{kernel_name}*.o")),
        list(build_dir.rglob(f"{kernel_name}*.json")),
    )
    if not (build_bins and build_jsons):
        utils.print_warn_log("The file generated after compilation does not exist.")
        return []
    return [build_bins[0], build_jsons[0]]


def get_compile_file(soc_version, temp_dir):
    handlers = utils.load_ascend_handlers()
    for handler in handlers:
        if handler.is_chip_handler(soc_version):
            return handler.get_compile_file(soc_version, temp_dir)
    build_result = get_compile_from_tik(soc_version, temp_dir)
    return build_result
