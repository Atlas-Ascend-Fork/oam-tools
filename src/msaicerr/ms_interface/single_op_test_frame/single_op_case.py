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

import re
import os
import subprocess
from time import sleep
import shutil
import platform
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.dsmi_interface import DSMIInterface
import numpy as np
from ms_interface import utils
from ms_interface.single_op_test_frame.common.ascend_tbe_op import (
    AscendOpKernel,
    AscendOpKernelRunner,
    AscendOpKernelRunnerParam,
)
from ms_interface.run_dirty_ub import run_dirty_ub


class SingleOpCase:
    def __init__(self, aic_info: AicErrorInfo, op_test: str) -> None:
        self.aic_info = aic_info
        # 生成的用例文件按位置传入 op_test，存下来供需要时取用（也避免参数未使用）
        self.op_test = op_test

    @staticmethod
    def _check_file_content(kernel_name, content):
        error_strings = [
            "there is an aivec error exception",
            "there is an aicore error exception",
            "aicore exception",
        ]
        for s in error_strings:
            if s in content and kernel_name in content:
                return True
        return False

    @staticmethod
    def _wait_for_log_stabilization(log_path):
        log_size = os.path.getsize(log_path)
        while True:
            sleep(0.2)
            current_log_size = os.path.getsize(log_path)
            if current_log_size == log_size:
                break
            log_size = current_log_size

    @staticmethod
    def search_aicerr_log(kernel_name, path):
        for root, _, files in os.walk(path):
            for file in files:
                if not file.endswith(".log"):
                    continue
                log_path = os.path.abspath(os.path.join(root, file))
                utils.print_info_log(f"The find single op log {log_path}")
                SingleOpCase._wait_for_log_stabilization(log_path)
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if SingleOpCase._check_file_content(kernel_name, content):
                    return True
        return False

    def generate_config(self):
        config = {
            "cce_file": self.get_cce_file(),
            "bin_path": self.aic_info.bin_file,
            "json_path": self.aic_info.json_file,
            "tiling_data": self.aic_info.tiling_data,
            "tiling_key": self.aic_info.tiling_key,
            "block_dim": self.aic_info.block_dim,
            "input_file_list": self.aic_info.input_list,
            "output_file_list": self.aic_info.output_list,
            "workspace_file_list": self.aic_info.workspace_list,
            "bin_file_list": self.aic_info.bin_list,
            "kernel_name": self.aic_info.kernel_name,
            "device_id": self.aic_info.run_device_id,
            "sub_ptr_addrs": self.aic_info.sub_ptr_addrs,
            "ffts_addrs_num": self.aic_info.ffts_addrs_num,
            "workspace": self.aic_info.workspace,
        }
        return config

    @staticmethod
    def get_soc_version_from_cce(cce_file):
        # TypeError：config 缺字段时 cce_file 可能是 None，open(None) 即抛该异常，
        # 须与其他读文件失败一样回退默认芯片版本，而不是让用例进程直接退出。
        try:
            with open(cce_file, "r", encoding="utf-8") as f:
                content = f.read()
            soc_version_ret = re.findall(r'//.*?(Ascend.*?)"', content)
            if soc_version_ret:
                utils.print_info_log(
                    f"get soc_version {soc_version_ret[0]} from cce file {cce_file}"
                )
                if soc_version_ret[0] == "Ascend910B":
                    return "Ascend910B1"
                elif soc_version_ret[0] == "Ascend310B":
                    return "Ascend310B1"
                return soc_version_ret[0]
            else:
                utils.print_warn_log(
                    f"Can not get soc_version from cce file {cce_file}"
                )
                return "Ascend310"
        except (OSError, TypeError, UnicodeDecodeError, re.error):
            utils.print_warn_log(f"Can not get soc_version from cce file {cce_file}")
            return "Ascend310"

    def get_cce_file(self):
        kernel_path = self.aic_info.kernel_path
        kernel_name = self.aic_info.kernel_name
        tiling_key = self.aic_info.tiling_key
        cce_file = self.aic_info.cce_file
        if not os.path.exists(cce_file):
            cce_file = os.path.join(kernel_path, f"{kernel_name}_{tiling_key}.cce")
            if not os.path.exists(cce_file):
                utils.print_warn_log(f"The cce file:{cce_file} does not exist")
                return ""
        return cce_file

    @staticmethod
    def update_kernel_by_cce(cce_file, kernel_name):
        if not os.path.exists(cce_file):
            utils.print_info_log("Does not get cce file !!!")
            return None

        with open(cce_file, "r", encoding="utf-8") as f:
            content = f.read()
        cce_pattern = r"(?<=//\s).+$"
        re_result = re.findall(cce_pattern, content)
        if not re_result:
            utils.print_info_log(
                "Does not match ccec command, use origin kernel to run single op!"
            )
            return None
        cmd = re_result[0].split(" ")
        ccec_file = shutil.which("ccec")
        if not ccec_file:
            # guess where is ccec
            parent_path = (
                "aarch64-linux" if "aarch64" in platform.machine() else "x86_64-linux"
            )
            ccec_file_guess = os.path.join(
                os.sep,
                "usr",
                "local",
                "Ascend",
                "latest",
                parent_path,
                "ccec_compiler",
                "bin",
                "ccec",
            )
            if shutil.which(ccec_file_guess):
                ccec_file = ccec_file_guess
            else:
                utils.print_warn_log(
                    "Cannot find ccec! please add ccec path in env PATH."
                )
                return None
        os.environ["PATH"] = os.path.dirname(ccec_file) + ":" + os.environ["PATH"]
        rename_o_file = os.path.join(os.getcwd(), kernel_name + "_new.o")
        cmd[3] = cce_file
        dst_bin_index = cmd.index("-o") + 1
        cmd[dst_bin_index] = rename_o_file
        subprocess.run(cmd, check=False)
        return rename_o_file

    @staticmethod
    def read_bin_file(bin_name):
        with open(bin_name, "rb") as f:
            data = f.read()
        return data

    @staticmethod
    def get_io_data_list(data):
        input_file_list = data.get("input_file_list", [])
        output_file_list = data.get("output_file_list", [])
        input_data_list = []
        for file in input_file_list:
            input_data = np.load(file)
            input_data_list.append(input_data)
        output_info_list = []
        for file in output_file_list:
            output_info = {}
            np_data = np.load(file)
            output_info["size"] = np_data.nbytes
            if str(np_data.dtype) == "|V2":
                utils.print_warn_log(
                    "np_data.dtype is V2, maybe bfloat16, same size with float16"
                )
                output_info["dtype"] = "float16"
            else:
                output_info["dtype"] = str(np_data.dtype)
            output_info["shape"] = np_data.shape
            output_info_list.append(output_info)
        return input_data_list, output_info_list

    @staticmethod
    def run_kernel(data, op_test) -> str:
        kernel_name = data.get("kernel_name")
        cce_file = data.get("cce_file")
        if cce_file and os.path.exists(cce_file):
            utils.print_info_log("Generate new kernel by cce_file")
            bin_path = SingleOpCase.update_kernel_by_cce(cce_file, kernel_name)
            if bin_path is None:
                utils.print_warn_log(
                    "update_kernel_by_cce failed, please check cce file."
                )
                bin_path = data.get("bin_path")
        else:
            bin_path = data.get("bin_path")
        json_path = data.get("json_path")
        tiling_data = data.get("tiling_data")
        if (
            tiling_data
            and isinstance(tiling_data, str)
            and tiling_data.endswith(".bin")
        ):
            tiling_data = SingleOpCase.read_bin_file(tiling_data)
        else:
            tiling_data = tiling_data.encode("utf-8")
        tiling_key = data.get("tiling_key")
        block_dim = data.get("block_dim")
        input_data_list, output_info_list = SingleOpCase.get_io_data_list(data)
        device_id = data.get("device_id")
        try:
            device_id = int(device_id)
        except ValueError:
            utils.print_warn_log("device_id should be an integer, device set default 0")
            device_id = 0

        op_kernel = AscendOpKernel(bin_path, json_path)
        ascend_op_param = AscendOpKernelRunnerParam(
            kernel=op_kernel,
            inputs=input_data_list,
            tiling_data=tiling_data,
            block_dim=block_dim,
            tiling_key=tiling_key,
            actual_out_info=output_info_list,
            bin_list=data.get("bin_file_list"),
            sub_ptr_addrs=data.get("sub_ptr_addrs"),
            ffts_addrs_num=data.get("ffts_addrs_num"),
            workspace=data.get("workspace"),
            op_test=op_test,
        )
        with AscendOpKernelRunner(device_id=device_id) as runner:
            ret = runner.run(ascend_op_param)
        return ret

    @staticmethod
    def run(configs: dict, op_test: str) -> str:
        try:
            soc_version = DSMIInterface().get_chip_info(0).get_complete_platform()
        except (OSError, AttributeError, UnicodeDecodeError, IndexError, RuntimeError):
            utils.print_warn_log("get soc_version form platform failed!")
            soc_version = None
        if not soc_version:
            soc_version = SingleOpCase.get_soc_version_from_cce(configs.get("cce_file"))
        if not soc_version:
            # Both DSMI probe and cce file fallback failed. Returning early
            # avoids handing None to run_dirty_ub -> te_set_version, which
            # raises a confusing `TypeError: expected str, bytes or
            # os.PathLike object, not NoneType` from deep inside tbe.
            err = (
                "Cannot determine soc_version: DSMI probe failed and "
                "cce_file fallback returned no result. Aborting single "
                "op case run."
            )
            utils.print_error_log(err)
            return err
        device_id = configs.get("device_id")
        try:
            device_id = int(device_id)
        except ValueError:
            utils.print_warn_log("device_id should be an integer, device set default 0")
            device_id = 0
        # set single op log path
        utils.print_info_log("Start run dirty_ub test case...")
        run_dirty_ub(configs, soc_version, device_id)
        utils.print_info_log("Start run kernel test case...")

        ret = SingleOpCase.run_kernel(configs, op_test)
        ret_str = f"Execute {op_test} SingleOpCase.run_kernel result: \r\n{ret}"
        utils.print_info_log(ret_str)
        return f"{ret_str}"
