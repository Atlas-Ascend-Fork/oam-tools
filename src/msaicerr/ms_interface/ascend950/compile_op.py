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
import os
import json
import sys
from pathlib import Path
import shutil

from ms_interface import utils
from ms_interface.ascend950.ascend_c_template import (
    ADD_OP_KERNEL_TEMPLATE,
    DIRTY_OP_KERNEL_TEMPLATE,
)
from ms_interface.dsmi_interface import DSMIInterface


class CompileOP:
    # 记录某个算子编译产物所对应芯片的标记文件名，用于跨芯片复用时的校验
    COMPILE_CHIP_MARKER = ".compile_chip"

    def __init__(self, op_name, inputs, outputs, soc_version, chip="Ascend950"):
        self.op_name = op_name
        self.inputs = inputs
        self.outputs = outputs
        self.soc_version = soc_version
        self.chip = chip

    @staticmethod
    def get_ub_size():
        try:
            from tbe.common import platform
        except (ImportError, AttributeError) as e:
            utils.print_warn_log(f"failed to import tbe, skipped it. error: {e}")
            return 0
        try:
            soc_version = DSMIInterface().get_chip_info(0).get_complete_platform()
            platform.set_current_compile_soc_info(soc_version)
            ub_size = platform.get_soc_spec("UB_SIZE")
        except OSError:
            return 0
        # float32数据类型每个数4字节, 数据个数=size/4
        return ub_size // 4

    def make_json_file(self, compile_temp_dir):
        template = [
            {"op": self.op_name, "language": "cpp", "input_desc": [], "output_desc": []}
        ]
        template[0]["input_desc"] = self.inputs
        template[0]["output_desc"] = self.outputs
        utils.check_path_valid(str(compile_temp_dir), isdir=True, output=True)
        json_file = compile_temp_dir.joinpath(f"{self.op_name}.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(template, f)
        return json_file

    def get_compile_file_from_temp(self, compile_temp_dir):
        utils.print_debug_log("Searching for Compiled Files")
        build_dir = compile_temp_dir.joinpath(self.op_name, "build_out", "op_kernel")
        build_bins, build_jsons = (
            list(build_dir.rglob(f"{self.op_name}*.o")),
            list(build_dir.rglob(f"{self.op_name}*.json")),
        )
        if not (build_bins and build_jsons):
            utils.print_warn_log("The file generated after compilation does not exist.")
            return []
        return [build_bins[0], build_jsons[0]]

    def compile(self, python_bin_path, compile_temp_dir, json_file, kernel_info):
        new_env = os.environ.copy()
        if not new_env.get("ASCEND_HOME_PATH"):
            # 如果环境变量中没有ASCEND_HOME_PATH，通过TOOLCHAIN_HOME推导
            new_env["ASCEND_HOME_PATH"] = os.path.join(
                new_env.get("TOOLCHAIN_HOME", ""), "../"
            )
        # 将python_path/bin路径添加到环境变量中,用于查找msopgen工具
        new_env["PATH"] = new_env["PATH"] + ":" + python_bin_path
        # 1、生成自定义算子模板
        utils.print_debug_log("Start run msopgen!")
        # G.EDV.05：用绝对路径调外部程序；msopgen 在上面拼进 PATH 的 python_bin_path 里。
        msopgen_bin = shutil.which("msopgen", path=new_env["PATH"])
        if not msopgen_bin:
            utils.print_error_log("Cannot find msopgen in PATH!")
            return False
        cmd = [
            msopgen_bin,
            "gen",
            "-i",
            str(json_file),
            "-c",
            f"ai_core-{self.chip}",
            "-lan",
            "cpp",
            "-out",
            self.op_name,
        ]
        res = utils.run_cmd_output(cmd, cwd=compile_temp_dir, env=new_env)
        utils.print_debug_log("Generating a custom operator Template")
        if not res:
            utils.print_error_log("Run msopgen gen failed!")
            return False
        # 2、更新op_kernel 算子文件
        utils.print_debug_log("Update the kernel file.")
        op_kernel_file = compile_temp_dir.joinpath(
            self.op_name, "op_kernel", kernel_info[self.op_name]["op_kernel_file"]
        )
        op_kernel_file.write_text(kernel_info[self.op_name]["file_content"])
        #  3、编译自定义算子
        bash_bin = shutil.which("bash")
        if not bash_bin:
            utils.print_error_log("Cannot find bash in PATH!")
            return False
        res = utils.run_cmd_output(
            [bash_bin, "build.sh"],
            cwd=compile_temp_dir.joinpath(self.op_name),
            env=new_env,
        )
        utils.print_debug_log("Compiling the custom operator")
        if not res:
            utils.print_error_log(
                "Compiling the operator failed. Check the environment."
            )
            return False
        return True

    def get_compile_file(self, compile_temp_dir):
        kernel_info = {
            "AddCustom": {
                "op_kernel_file": "add_custom.cpp",
                "file_content": ADD_OP_KERNEL_TEMPLATE,
            },
            "DirtyCustom": {
                "op_kernel_file": "dirty_custom.cpp",
                "file_content": DIRTY_OP_KERNEL_TEMPLATE.replace(
                    "uint32_t total_length = 256;",
                    f"uint32_t total_length = {self.get_ub_size()};",
                ),
            },
        }
        compile_temp_dir = Path(compile_temp_dir)
        # 判断temp是否存在之前编译过，如果能查询到且芯片一致则直接复用，否则重新编译
        if compile_temp_dir.exists() and self._is_cache_chip_matched(compile_temp_dir):
            find_res = self.get_compile_file_from_temp(compile_temp_dir)
            if find_res:
                return find_res
        # 检查msopgen 工具是否存在
        python_bin_path = os.path.join(sys.base_prefix, "bin")
        if not (
            shutil.which("msopgen") or shutil.which("msopgen", path=python_bin_path)
        ):
            utils.print_error_log("The msopgen tool does not exist.")
            return []
        # 清理可能残留的旧芯片编译目录，避免 msopgen 生成失败或复用到旧产物
        if not self._clean_op_build_dir(compile_temp_dir):
            return []
        # 1、生成json文件
        json_file = self.make_json_file(compile_temp_dir)
        if not json_file:
            return []
        # 2、编译
        compile_res = self.compile(
            python_bin_path, compile_temp_dir, json_file, kernel_info
        )
        if not compile_res:
            return []
        # 3、查找.o 和 .json 文件
        find_res = self.get_compile_file_from_temp(compile_temp_dir)
        if not find_res:
            utils.print_error_log(
                "Compiling the operator failed. Check the environment."
            )
            return []
        # 4、记录本次编译产物所属芯片，供后续复用校验
        self._write_chip_marker(compile_temp_dir)
        # get_compile_file_from_temp 返回 [] 或 [bin, json]；上面已判非空，
        # 此处按下标取值（pylint 无法从 [] 的初值推断长度，解包会误报）
        build_bin, build_json = find_res[0], find_res[1]
        # 5、修改json
        with open(build_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 算子中未使用workspace，所以需要删除
            if "workspace" in data:
                del data["workspace"]
        with open(build_json, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return [build_bin, build_json]

    def _get_chip_marker_file(self, compile_temp_dir):
        # 标记文件放在算子编译目录下，记录该产物对应的芯片
        return compile_temp_dir.joinpath(self.op_name, CompileOP.COMPILE_CHIP_MARKER)

    def _write_chip_marker(self, compile_temp_dir):
        marker_file = self._get_chip_marker_file(compile_temp_dir)
        try:
            marker_file.parent.mkdir(parents=True, exist_ok=True)
            marker_file.write_text(self.chip)
        except OSError as ex:
            utils.print_warn_log(
                f"Failed to write compile chip marker {marker_file}: {ex}"
            )

    def _is_cache_chip_matched(self, compile_temp_dir):
        # 仅当标记文件存在且与当前芯片一致时，才允许复用已有编译产物
        marker_file = self._get_chip_marker_file(compile_temp_dir)
        if not marker_file.exists():
            utils.print_debug_log(
                "The compile chip marker does not exist, recompile to avoid reusing artifacts of another chip."
            )
            return False
        try:
            cached_chip = marker_file.read_text().strip()
        except OSError as ex:
            utils.print_warn_log(
                f"Failed to read compile chip marker {marker_file}: {ex}"
            )
            return False
        if cached_chip != self.chip:
            utils.print_debug_log(
                f"The cached compile artifacts belong to chip {cached_chip}, "
                f"but current chip is {self.chip}, recompile is required."
            )
            return False
        return True

    def _clean_op_build_dir(self, compile_temp_dir):
        # 重新编译前清理旧的算子目录，避免 msopgen 因目录已存在而失败或复用旧芯片产物
        op_dir = compile_temp_dir.joinpath(self.op_name)
        if op_dir.exists():
            try:
                shutil.rmtree(op_dir)
            except OSError as ex:
                utils.print_error_log(
                    f"Failed to clean old compile dir {op_dir}: {ex}, clean it manually please"
                )
                return False
        return True
