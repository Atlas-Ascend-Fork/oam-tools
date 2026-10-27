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
import copy
import re
import os
import stat
import subprocess
import sys
import time
import json
import platform
from pathlib import Path
import shutil
from collections import namedtuple
from dataclasses import dataclass
from functools import reduce
from typing import Optional

import numpy as np
from ms_interface import utils
from ms_interface.tiling_data_parser import TilingDataParser
from ms_interface.constant import (
    Constant,
    RegexPattern,
    RetCode,
    ModeCustom,
    NOT_RUN_EXEC_FAILED,
    NOT_RUN_LAUNCH_FAILED,
)
from ms_interface.aic_error_info import (
    AicErrorInfo,
    detect_chip_type_by_dump_info,
    detect_core_err_type,
)
from ms_interface import pc_corrector
from ms_interface import json_report_builder
from ms_interface.dump_data_parser import DumpDataParser
from ms_interface.single_op_test_frame.utils import shape_utils
from ms_interface.dsmi_interface import DSMIInterface
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase
from ms_interface.utils import screen_error


def _load_kernel_io_counts(info: AicErrorInfo) -> None:
    """读一次 kernel json 的输入/输出数量，缓存到 info.kernel_io_counts。

    解析阶段（Step 4）调用一次；JSON 构建阶段与 normal 标记细分均只读该
    内存字段，不再回读文件（SRS FR-AJR-001：新增小文件读取不超过 1 次）。
    json_file 由文件名匹配得到、不校验内容结构，故对非 dict 根/非 dict
    supportInfo 一并兜底，异常输入退化为"数量未取到"而不中断 parse()。
    """
    if info.kernel_io_counts != (None, None):
        return
    if not info.json_file or not os.path.exists(info.json_file):
        return
    try:
        with open(info.json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
        support = data.get("supportInfo", {})
        if not isinstance(support, dict):
            return
        info.kernel_io_counts = (
            len(support.get("inputs") or []),
            len(support.get("outputs") or []),
        )
    except (OSError, ValueError, AttributeError, TypeError):
        return


def _refine_normal_marks(info: AicErrorInfo) -> None:
    """将 normal tensor 标记按 kernel json 的输入/输出数量细分为 input/output。

    L0 日志的 normal tensor 不区分输入输出；kernel json 的 supportInfo
    inputs/outputs 数量给出分界：inputs 数量内为 input，其后 outputs 数量内
    为 output。json 读不到或序号超出分界时降级为 other，保证 arg_type
    始终在六值枚举内。
    """
    marks = info.args_type_marks
    if not any(mark == "normal" for mark in marks.values()):
        return
    num_inputs, num_outputs = info.kernel_io_counts
    if num_inputs is None:
        num_inputs, num_outputs = 0, 0
    for idx in list(marks.keys()):
        if marks[idx] != "normal":
            continue
        if idx < num_inputs:
            marks[idx] = "input"
        elif num_outputs is not None and idx < num_inputs + num_outputs:
            marks[idx] = "output"
        else:
            marks[idx] = "other"


def _find_runtime_so():
    ld_lib_paths = os.environ["LD_LIBRARY_PATH"]
    if not ld_lib_paths:
        raise RuntimeError("LD_LIBRARY_PATH is empty")
    ld_lib_path_list = ld_lib_paths.split(":")

    for ld_lib_path in ld_lib_path_list:
        runtime_so_path_tmp = os.path.join(ld_lib_path, "libruntime.so")
        if os.path.exists(runtime_so_path_tmp):
            return runtime_so_path_tmp
    return ""


@dataclass
class KernelFile:
    bin_file: str
    json_file: str
    cce_file: str

    def __setattr__(self, name, value):
        if not isinstance(value, str) or not os.path.exists(value):
            value = ""
        super().__setattr__(name, value)


class AicoreErrorParser:
    """
    The AicoreErrorParser class, parse aicore error info
    """

    def __init__(self: any, collect_path: str, device_id=0, collect_succ=True) -> None:
        self.collect_path = collect_path
        self.parse_level = 0
        self.ffts_flag = False
        self.is_sk = False
        self.device_id = device_id
        self.collect_succ = collect_succ

    @staticmethod
    def _check_args(args_before, args_after) -> bool:
        if sum(args_before) == 0:
            utils.print_warn_log(
                "args_before is empty, maybe GE unable to print it. Skip args check!"
            )
            return True
        for arg_after in args_after:
            for arg_before in args_before:
                if arg_after == arg_before:
                    return True
            return False

    @staticmethod
    def _find_sk_host_o(kernel_path: str, kernel_name: str) -> str:
        # host.o命名为<kernel_name>*_host.o，kernel_name与_host.o之间可能有额外字符，需glob匹配
        host_files = sorted(Path(kernel_path).glob(f"{kernel_name}*_host.o"))
        if not host_files:
            return ""
        if len(host_files) > 1:
            utils.print_debug_log(
                f"Multiple host.o found for {kernel_name}, use {host_files[0]}."
            )
        return str(host_files[0])

    @staticmethod
    def _get_kernel_file_by_name(kernel_path: str, kernel_name: str, tiling_key: str):
        # 算子名能直接拼出.o时，按命名约定取.o/.json/.cce
        if not os.path.exists(os.path.join(kernel_path, kernel_name + ".o")):
            return None
        bin_file = os.path.join(kernel_path, kernel_name + ".o")
        json_file = os.path.join(kernel_path, kernel_name + ".json")
        cce_file = os.path.join(
            kernel_path, kernel_name + "_" + str(tiling_key) + ".cce"
        )
        if not os.path.exists(cce_file):
            cce_file = os.path.join(kernel_path, kernel_name + ".cce")
        return KernelFile(bin_file, json_file, cce_file)

    @staticmethod
    def _match_kernel_by_json(kernel_path: str, kernel_file_list: list) -> tuple:
        # 读取.json中的binFileName，定位成对的.o/.json
        bin_file = ""
        json_file = ""
        for file_name in kernel_file_list:
            if (
                (not os.path.exists(file_name))
                or file_name.endswith("_loc.json")
                or (not file_name.endswith(".json"))
            ):
                continue
            json_file = os.path.join(kernel_path, file_name)
            with open(json_file, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                if not json_data:
                    continue
                bin_file_name = json_data.get("binFileName")
                if not bin_file_name:
                    continue
                # bin_file已是绝对路径，不能再用于拼json路径，否则得到永不存在的
                # {kernel_path}/{kernel_path}/xxx.o.json，导致此处永远匹配不上
                bin_file = os.path.join(kernel_path, bin_file_name + ".o")
                json_file = os.path.join(kernel_path, bin_file_name + ".json")
                if not os.path.exists(bin_file) or not os.path.exists(json_file):
                    continue
                else:
                    break
        return bin_file, json_file

    @staticmethod
    def _fill_kernel_backup(
        kernel_file_list: list, bin_file: str, json_file: str, tiling_key: str
    ) -> tuple:
        # 用文件列表里的.o/.json/.cce兜底填充缺失项，.cce优先匹配tiling_key
        bin_file_backup = ""
        json_file_backup = ""
        cce_file_backup = ""
        cce_file = ""
        for file_name in kernel_file_list:
            if not os.path.exists(file_name):
                continue
            if file_name.endswith(".o"):
                bin_file_backup = file_name
            elif file_name.endswith(".json") and (not file_name.endswith("_loc.json")):
                json_file_backup = file_name
            elif file_name.endswith(".cce"):
                tiling_key = "_" + str(tiling_key) + "."
                if tiling_key in file_name:
                    cce_file = file_name
                cce_file_backup = file_name
        if not os.path.exists(bin_file):
            bin_file = bin_file_backup
        if not os.path.exists(json_file):
            json_file = json_file_backup
        if not os.path.exists(cce_file):
            cce_file = cce_file_backup
        return bin_file, json_file, cce_file

    @staticmethod
    def parser_kernel_info(kernel_name_ret, err_stream_id, err_task_id):
        stream_id, task_id, kernel_name, hash_id = kernel_name_ret[0]
        if err_stream_id and err_task_id:
            for k_stream_id, k_task_id, k_kernel_name, k_hash_id in kernel_name_ret:
                if k_stream_id == err_stream_id and k_task_id == err_task_id:
                    stream_id, task_id, kernel_name, hash_id = (
                        k_stream_id,
                        k_task_id,
                        k_kernel_name,
                        k_hash_id,
                    )
                    break
        return stream_id, task_id, kernel_name, hash_id

    @staticmethod
    def parser_kernel_info_with_ext_info(kernel_name_ret, err_stream_id, err_task_id):
        stream_id, task_id = kernel_name_ret[0][0], kernel_name_ret[0][1]
        kernel_name, hash_id = kernel_name_ret[0][3], kernel_name_ret[0][4]
        if err_stream_id and err_task_id:
            for k_r in kernel_name_ret:
                if (
                    k_r[0] == err_stream_id
                    and k_r[1] == err_task_id
                    and k_r[3] != "none"
                ):
                    stream_id, task_id, kernel_name, hash_id = (
                        k_r[0],
                        k_r[1],
                        k_r[3],
                        k_r[4],
                    )
                    break
        return stream_id, task_id, kernel_name, hash_id

    @staticmethod
    def get_sk_kernel_name(plog_dir) -> str:
        # SK场景标志性打印中的kernelName才是正确的算子名
        sk_marker = "Begin to dump callback exception"
        sk_cmd = ["grep", sk_marker, "-inrE", plog_dir]
        sk_regexp = r"kernelName=([^\n]*?)\.\s*$"
        sk_ret = utils.get_inquire_result(sk_cmd, sk_regexp)
        if sk_ret:
            return sk_ret[0]
        return ""

    def get_kernel_name_l0(self: any, data_name) -> Optional[tuple]:
        # 获取kernel_name
        plog_dir = os.path.join(self.collect_path, "collection", "plog")
        err_stream_id, err_task_id = self.parser_data_name(data_name)
        # 优先查找SK场景标志性打印，命中则该打印中的kernelName才是正确的算子名
        sk_kernel_name = self.get_sk_kernel_name(plog_dir)
        # stream_id/task_id 默认采用从dump文件名解析出的值，避免纯SK场景下丢失该信息；
        # 普通场景下会被plog中解析出的更精确的值覆盖。hash_id 在SK场景下无来源，置空。
        stream_id, task_id, kernel_name, hash_id = (
            err_stream_id or "",
            err_task_id or "",
            "",
            "",
        )
        if not self.ffts_flag:
            error_log = "Aicore kernel execute failed|AI Core kernel execution failed"
            kernel_name_cmd = ["grep", error_log, "-inrE", plog_dir]

            kernel_name_regexp = (
                r" stream_id=(\d+),.*?task_id=(\d+),.*?fault kernel_name=(.*?),.*?"
                r"fault kernel info ext=(.*?),.*?hash=(\d+)"
            )
            kernel_name_ret = utils.get_inquire_result(
                kernel_name_cmd, kernel_name_regexp
            )
            if kernel_name_ret and kernel_name_ret[0][3] != "none":
                stream_id, task_id, kernel_name, hash_id = (
                    self.parser_kernel_info_with_ext_info(
                        kernel_name_ret, err_stream_id, err_task_id
                    )
                )
            else:
                kernel_name_regexp = r" stream_id=(\d+),.*?task_id=(\d+),.*?fault kernel_name=(.*?),.*?hash=(\d+)"
                kernel_name_ret = utils.get_inquire_result(
                    kernel_name_cmd, kernel_name_regexp
                )
                if not kernel_name_ret and not sk_kernel_name:
                    utils.print_error_log(f'Failed to get "{error_log}" in plog.')
                    return None
                if kernel_name_ret:
                    stream_id, task_id, kernel_name, hash_id = self.parser_kernel_info(
                        kernel_name_ret, err_stream_id, err_task_id
                    )
                    utils.print_debug_log(
                        f"AicoreError Found, Stream id: {stream_id}, task_id: {task_id},"
                        f"kernel_name: {kernel_name}"
                    )
        else:
            kernel_name_cmd = [
                "grep",
                "fftsplus task execute failed",
                "-inrE",
                plog_dir,
            ]
            kernel_name_regexp = r" stream_id=(\d+),.*?task_id=(\d+),.*?fault kernel_name=(.*?),.*?hash=(\d+)"
            kernel_name_ret = utils.get_inquire_result(
                kernel_name_cmd, kernel_name_regexp
            )
            if not kernel_name_ret and not sk_kernel_name:
                utils.print_error_log(
                    'Failed to get "fftsplus task execute failed" in plog.'
                )
                return None
            if kernel_name_ret:
                stream_id, task_id, kernel_name, hash_id = self.parser_kernel_info(
                    kernel_name_ret, err_stream_id, err_task_id
                )
                utils.print_debug_log(
                    f"AicoreError Found, Stream id: {stream_id}, task_id: {task_id},"
                    f"kernel_name: {kernel_name}"
                )

        # SK场景：用标志性打印中的kernelName覆盖原逻辑解析出的算子名
        if sk_kernel_name:
            kernel_name = sk_kernel_name
            utils.print_debug_log(
                f"SuperKernel scenario found, kernel_name: {kernel_name}"
            )

        node_name = data_name
        AicoreErrorInfo = namedtuple(
            "AicoreErrorInfo",
            ["stream_id", "task_id", "node_name", "kernel_name", "hash_id"],
        )
        error_info = AicoreErrorInfo(
            stream_id, task_id, node_name, kernel_name, hash_id
        )
        return error_info

    def _get_node_and_kernel_name(self: any, data_name) -> list:
        if self.parse_level == 1:
            return self.get_node_and_kernel_name_l1()
        else:
            return self.get_kernel_name_l0(data_name)

    def check_plog_info(self: any):
        find_path_cmd = ["grep", r"\[AIC_INFO\] dev_func:", "-inrE", self.collect_path]
        find_path_regexp = r"(/[_\-/0-9a-zA-Z.]{1,}.[log|txt]):"
        plog_path_ret = utils.get_inquire_result(find_path_cmd, find_path_regexp)

        ffts_check_path_cmd = [
            "grep",
            "fftsplus task execute failed",
            "-inrE",
            self.collect_path,
        ]
        ffts_check_path_regexp = r"(/[_\-/0-9a-zA-Z.]{1,}.[log|txt]):"
        ffts_check_path_ret = utils.get_inquire_result(
            ffts_check_path_cmd, ffts_check_path_regexp
        )
        if ffts_check_path_ret:
            self.ffts_flag = True
        if plog_path_ret:
            self.parse_level = 1
        else:
            self.parse_level = 0

        # SK场景标志性打印，命中则只生成host.o，没有device .o/.json/.cce
        sk_check_path_cmd = [
            "grep",
            "Begin to dump callback exception",
            "-inrE",
            self.collect_path,
        ]
        sk_check_path_regexp = r"(/[_\-/0-9a-zA-Z.]{1,}.[log|txt]):"
        sk_check_path_ret = utils.get_inquire_result(
            sk_check_path_cmd, sk_check_path_regexp
        )
        if sk_check_path_ret:
            self.is_sk = True

    @staticmethod
    def _get_extra_info(aic_extra_error):
        """
         为兼容原device log框架生成一个extra info参数
        :param aic_extra_error: 正则匹配结果
        :return: 返回的extra info
        """
        extra_re = {
            "IFU_ERR_INFO": r"ifu error info:\s(\S+),",
            "CCU_ERR_INFO": r"ccu error info:\s(\S+),",
            "BIU_ERR_INFO": r"biu error info:\s(\S+),",
            "CUBE_ERR_INFO": r"cube error info:\s(\S+),",
            "MTE_ERR_INFO": r"mte error info:\s(\S+),",
            "VEC_ERR_INFO": r"vec error info:\s(\S+),",
        }
        result = "extra info:\n"
        for key, regexp in extra_re.items():
            res = re.search(regexp, aic_extra_error)
            if res:
                result += "{}={}\n".format(key, res.group(1))
        return result

    def _get_v300_error_code(self: any) -> list:
        plog_path = os.path.join(self.collect_path, "collection", "plog")
        cmd = ["grep", "The extend info: errcode:", "-nr", plog_path]
        regexp = r"\(([0-9xa-fA-F]+),\s*([0-9xa-fA-F]+),\s*([0-9xa-fA-F]+)\)"
        ret = utils.get_inquire_result(cmd, regexp)
        new_code = 0
        if ret:
            code0, code1, code2 = ret[0]
            code0_int = utils.get_hexstr_value(code0)
            code1_int = utils.get_hexstr_value(code1)
            code1_int = code1_int << 64
            code2_int = utils.get_hexstr_value(code2)
            code2_int = (((code2_int >> 32) << 17) | (code2_int & 0x1FFFF)) << 128
            new_code = code0_int | code1_int | code2_int
        return str(hex(new_code))

    @staticmethod
    @screen_error
    def collect_driver_aicore_number():
        import ctypes

        rts_so_path = _find_runtime_so()
        lib = ctypes.cdll.LoadLibrary(rts_so_path)
        driver_aicore_number = ctypes.c_int()
        get_core_num = ctypes.byref(driver_aicore_number)
        result = lib.rtGetAiCoreCount(get_core_num)
        if result != 0:
            utils.print_error_log("Get driver aicore number failed")
            raise utils.AicErrException(
                Constant.MS_AICERR_GET_DRIVER_AICORE_NUMBER_ERROR
            )
        return driver_aicore_number.value

    @staticmethod
    def get_workspace_info(parse_level, workspace_list):
        if parse_level == 0:
            return 0
        else:
            workspace_info = 1
            for woskspace_npy in workspace_list:
                workspace = np.load(woskspace_npy)
                workspace_info = (
                    shape_utils.calc_shape_size(workspace.shape) * workspace.itemsize
                )
            return workspace_info

    def get_dump_data_info(self: any):
        plog_dir = os.path.join(self.collect_path, "collection", "plog")
        if self.parse_level == 1:
            dump_data_cmd = ["grep", "dump exception to file", "-inrE", plog_dir]
            adump_dump_data_regexp = (
                r"(\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).*?"
                r"tid\:(\d+).*?extra-info\/data-dump\/\d+\/([\w.]+)"
            )
            ge_dump_data_regexp = (
                r"(\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).*?"
                r"(\d+) DumpNodeInfo:.*?extra-info\/data-dump\/\d+\/([\w.]+)"
            )
            adump_dump_data_ret = utils.get_inquire_result(
                dump_data_cmd, adump_dump_data_regexp
            )
            adump_dump_data_ret = [item[1:] for item in sorted(adump_dump_data_ret)]
            ge_dump_data_ret = utils.get_inquire_result(
                dump_data_cmd, ge_dump_data_regexp
            )
            ge_dump_data_ret = [item[1:] for item in sorted(ge_dump_data_ret)]
            if not adump_dump_data_ret and not ge_dump_data_ret:
                utils.print_error_log(
                    f"Dump file cannot be found in {self.collect_path}."
                )
                raise utils.AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR)
            if adump_dump_data_ret:
                return adump_dump_data_ret[:2]
            else:
                return ge_dump_data_ret[:2]
        else:
            dump_data_cmd = ["grep", "dump exception to file", "-inrE", plog_dir]

            dump_data_regexp = (
                r"(\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).*?"
                r"tid\:(\d+).*?extra-info\/data-dump\/\d+\/([\w.]+)"
            )
            dump_data_ret = utils.get_inquire_result(dump_data_cmd, dump_data_regexp)
            dump_data_ret = [item[1:] for item in sorted(dump_data_ret)]
            if not dump_data_ret:
                utils.print_error_log(
                    f"Dump file cannot be found in {self.collect_path}."
                )
                raise utils.AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR)
            return dump_data_ret[:2]

    def _get_custom_dump_files(self, dump_dir):
        """从已采集的plog中检测用户自定义dump文件路径。

        自定义dump由runtime在原始dump之外额外落盘，仅在日志中以
        "dump custom exception to file"关键字指示，文件名形如
        <name>.custom.<毫秒时间戳>。采集侧已按报错device过滤文件，
        解析侧不再按命令行device再次过滤，仅保留dump目录下实际存在
        的文件，避免命令行device与报错device不一致时漏解析。
        """
        plog_dir = os.path.join(self.collect_path, "collection", "plog")
        dump_data_cmd = ["grep", "dump custom exception to file", "-inrE", plog_dir]
        dump_data_regexp = (
            r"(\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).+?"
            r"extra-info\/data-dump\/(\d+)\/([\w.]+\.custom\.\d+)"
        )
        custom_files = []
        name_mapping = utils.parse_name_mapping_csv(
            os.path.join(dump_dir, Constant.MAPPING_CSV_FILE)
        )
        dump_data_ret = utils.get_inquire_result(dump_data_cmd, dump_data_regexp)
        for _, _, data_name in dump_data_ret:
            dump_file = os.path.join(dump_dir, data_name)
            if not os.path.isfile(dump_file) and name_mapping:
                # 超长自定义dump被runtime改为随机数字串，按mapping.csv反查实际文件名
                dump_file = os.path.join(dump_dir, name_mapping.get(data_name, ""))
            if os.path.isfile(dump_file):
                custom_files.append(dump_file)
        if custom_files:
            utils.print_info_log(
                f"{len(custom_files)} custom dump file(s) will be parsed."
            )
        elif dump_data_ret:
            # plog有自定义dump日志却一个都没落盘，提示不作为自定义dump解析
            utils.print_warn_log(
                "Custom dump file(s) are detected in the plog but none can be found "
                "in the dump directory, skip parsing them as custom dump."
            )
        return custom_files

    def _build_dump_parser(self, collect_dump_data, info):
        return DumpDataParser(
            collect_dump_data,
            info,
            custom_dump_files=self._get_custom_dump_files(collect_dump_data),
        )

    def set_info(self, aic_err_ret, plog_path, data_name, rts_block_dim, records=None):
        info = AicErrorInfo()
        if records is None:
            records = [aic_err_ret]

        # extra_info 包括各寄存器信息ifu、ccu、biu、cube、mte、vec的寄存器错误码。
        # 逐条抽取 raw extra_info 并预转为报告格式，分组渲染与逐组 PC 修正各用各的；
        # 主记录的 raw 额外用于芯片判型（950 独有 sc/su/l1 error info 只在 raw 里）。
        for rec in records:
            raw_extra_info = rec.pop("extra_info", "")
            if rec is aic_err_ret:
                chip_type = detect_chip_type_by_dump_info(raw_extra_info)
            rec["extra_info"] = self._get_extra_info(raw_extra_info)
        info.extra_info = aic_err_ret["extra_info"]
        info.aic_error_info = aic_err_ret

        # v300 的 error_code 是壳 "0"/"0x0"，真实位在 extend info。兜底要在分组之前
        # 统一改写并缓存结果，否则组键残留壳值，报告头会打出 AIC_ERROR : 0。
        v300_code = None
        for rec in records:
            if rec.get("error_code", "") in ("0", "0x0"):
                if v300_code is None:
                    v300_code = self._get_v300_error_code()
                rec["error_code"] = v300_code

        # Preserve all same-thread register errors and group by error code.
        # AIC 与 AIV 共用同一份数字 core id，按核型分桶去重避免重复统计。
        groups = {}
        for rec in records:
            code = rec.get("error_code", "") or "unknown/0"
            group = groups.setdefault(
                code, {"records": [], "cores_aic": [], "cores_aiv": []}
            )
            group["records"].append(rec)
            kind = detect_core_err_type(rec.get("core_err_type", ""))
            cores_key = "cores_aiv" if kind == "aiv" else "cores_aic"
            core = rec.get("core_id", "")
            if core not in group[cores_key]:
                group[cores_key].append(core)
        info.aic_error_groups = list(groups.items())

        info.data_name = data_name

        # 此处附加判断是L0还是L1
        error_info = self._get_node_and_kernel_name(data_name)
        # 访问具名元组的属性
        if error_info is not None:
            info.stream_id = error_info.stream_id
            info.task_id = error_info.task_id
            info.node_name = error_info.node_name
            info.kernel_name = error_info.kernel_name
            info.hash_id = error_info.hash_id

            info.kernel_path = os.path.join(self.collect_path, "collection", "compile")
            info.rts_block_dim = rts_block_dim
            info.driver_aicore_num = self.collect_driver_aicore_number()
            info.tiling_key, info.block_dim = self.get_tiling_info(info.kernel_name)
            kernel_file = self._get_kernel_and_json_file(
                info.kernel_name, info.tiling_key
            )
            if kernel_file is not None:
                info.bin_file = kernel_file.bin_file
                info.json_file = kernel_file.json_file
                info.cce_file = kernel_file.cce_file

        utils.print_debug_log(
            f"err_time: {info.aic_error_info.get('err_time', '')}, "
            f"dev_id: {info.aic_error_info.get('dev_id', '')}, "
            f"core_id: {info.aic_error_info.get('core_id', '')}, "
            f"error_code: {info.aic_error_info.get('error_code', '')}, "
            f"start_pc: {info.aic_error_info.get('start_pc', '')}, "
            f"current_pc: {info.aic_error_info.get('current_pc', '')}, stream_id: {info.stream_id}, "
            f"task_id: {info.task_id}, node_name: {info.node_name}, kernel_name: {info.kernel_name}, "
            f"bin_file: {info.bin_file}, json_file: {info.json_file}, cce_file: {info.cce_file}, "
            f"rts_block_dim: {info.rts_block_dim}, driver_aicore_num: {info.driver_aicore_num}."
        )

        # error_code 兜底已提前到分组之前，这里直接做 PC 修正：修正命中的
        # 模块由 error_code 决定。chip_type 由上面的 dump info 字段判出，
        # 不受兜底改写 error_code 影响。
        info.corrected_pc = pc_corrector.get_corrected_pc(plog_path, info, chip_type)
        # 与 corrected_pc 同处填充：_get_info_for_decompile 只在 L1 反编译路径上
        # 执行，放那里会让其余路径拿到 corrected_pc 却没有错误行号。
        self._set_corrected_instr(info)
        # 每个 AIC_ERROR 类别按自身首条记录独立做 PC 修正。多核同报时各组
        # start/current pc 不同，若沿用主记录那份 Corrected Info，后续组会
        # 错配第一组的 current pc。结果存入 group 供 _get_group_pc 使用。
        main_aic_info = info.aic_error_info
        main_corrected_pc = info.corrected_pc
        main_corrected_instr = info.corrected_instr
        try:
            for group in groups.values():
                rec = group["records"][0]
                if rec is main_aic_info:
                    # 主记录所在组复用主记录已算好的结果，避免重复 grep + 符号化。
                    group["corrected_pc"] = main_corrected_pc
                    group["corrected_instr"] = main_corrected_instr
                    continue
                info.aic_error_info = rec
                info.extra_info = rec.get("extra_info", "")
                group["corrected_pc"] = pc_corrector.get_corrected_pc(
                    plog_path, info, chip_type
                )
                group["corrected_instr"] = ""
                if group["corrected_pc"]:
                    info.corrected_pc = group["corrected_pc"]
                    self._set_corrected_instr(info)
                    group["corrected_instr"] = info.corrected_instr or ""
        finally:
            info.aic_error_info = main_aic_info
            info.extra_info = aic_err_ret.get("extra_info", "")
            info.corrected_pc = main_corrected_pc
            info.corrected_instr = main_corrected_instr

        return info

    def get_op_info(self: any) -> Optional[AicErrorInfo]:
        try:
            dump_data_info_list = self.get_dump_data_info()
        except utils.AicErrException:
            return None

        plog_path = os.path.join(self.collect_path, "collection", "plog")
        aicore_err_cmd = ["grep", "error info:", "-inrE", plog_path]
        aic_err_rets = utils.get_inquire_result(
            aicore_err_cmd, RegexPattern.AICORE_ERR_OCCUR, match_dict=True
        )
        if not aic_err_rets:
            utils.print_info_log("Aicore error exception use outstanding regex.")
            aic_err_rets = utils.get_inquire_result(
                aicore_err_cmd, RegexPattern.AICORE_ERR_OCCUR_OST, match_dict=True
            )
            if not aic_err_rets:
                utils.print_error_log("Aicore error exception does not match.")
                return None

        aic_err_rets = sorted(
            aic_err_rets, key=lambda x: (x.get("err_time") is None, x.get("err_time"))
        )

        error_stream_task, dump_data_info = self.update_dumpinfo_for_outstanding(
            plog_path, dump_data_info_list, aic_err_rets
        )

        thread_id, data_name = dump_data_info
        aic_err_ret = aic_err_rets
        # aic_err_rets按err_time排序，dump侧tid未必与最早那条记录一致（多线程下发、
        # 多卡、日志混入其他进程时很常见），需遍历完所有记录再判定失败
        matched = False
        for aic_err_info in aic_err_rets:
            if thread_id == aic_err_info["thread_id"]:
                aic_err_ret = aic_err_info
                if (
                    "s_start_pc" in aic_err_ret.keys()
                    and error_stream_task
                    and error_stream_task["is_second_error"]
                ):
                    aic_err_ret["start_pc"] = aic_err_ret["s_start_pc"]
                matched = True
                break
        if not matched:
            utils.print_error_log(
                f"Dump data tid is not the same with rts tid. The tid of the dump data is {thread_id}, "
                f"the tids in the aicore error logs are "
                f"{[err_info.get('thread_id') for err_info in aic_err_rets]}."
            )
            return None

        rts_info_cmd = ["grep", "-r", "RUNTIME", plog_path]
        _, rts_info = utils.execute_command(rts_info_cmd)
        block_dim_regexp = r"blockDim=(\d+)"
        block_dim_ret = re.findall(block_dim_regexp, rts_info, re.M)
        if not block_dim_ret:
            utils.print_error_log("Get runtime block_dim failed")
            return None

        block_dim = 0
        for block_dim_num in block_dim_ret:
            if block_dim <= int(block_dim_num):
                block_dim = int(block_dim_num)
        rts_block_dim = block_dim
        # 只保留与主记录同线程的寄存器错误：跨线程的 err_time/dev_id 混入会
        # 并成一组错误，报告头写的是主记录时间却列出别的线程的错误码。
        same_thread = [
            err_info
            for err_info in aic_err_rets
            if err_info.get("thread_id") == aic_err_ret.get("thread_id")
        ]
        return self.set_info(
            aic_err_ret, plog_path, data_name, rts_block_dim, same_thread
        )

    @staticmethod
    def _get_args(plog_path) -> list:
        key_word_list = []
        get_args_cmd = ["grep", "after execute:", "-inrE", plog_path]
        get_args_regexp = (
            r"(args\(0 to .*?\) after execute:.*?)after execute:args print end"
        )
        get_args_ret = utils.get_inquire_result(get_args_cmd, get_args_regexp)
        if not get_args_ret or len(get_args_ret) == 0:
            utils.print_warn_log("Failed to get all args after execute.")
            return []

        get_args_ret = get_args_ret[0]
        get_arg_regexp = r" after execute:(.*?)$"
        get_arg_ret = re.findall(get_arg_regexp, get_args_ret, re.M | re.S)
        if not get_arg_ret:
            utils.print_warn_log("Failed to get arg after execute.")
            return []

        for args in get_arg_ret:
            split_tmp = args.split(",")
            for str2 in split_tmp:
                if str2.find("\n") != -1:
                    continue
                str2 = str2.replace(" ", "")
                if not str2:
                    continue
                key_word_list.append(str2)
        return key_word_list

    @staticmethod
    def _get_para_base(plog_path) -> int:
        para_base_cmd = ["grep", "para base", "-inrE", plog_path]
        para_base_regexp = r"para base:\s+(.*?)\."
        param_base_ret = utils.get_inquire_result(para_base_cmd, para_base_regexp)
        if not param_base_ret or len(param_base_ret) == 0:
            utils.print_warn_log("Failed to get para_base after execute.")
            return -1
        utils.print_debug_log(f"para_base address is {param_base_ret[0]}")
        return utils.get_hexstr_value(param_base_ret[0])

    def _get_sub_ptr(self: any, info) -> dict:
        utils.print_debug_log("Start to get sub ptr.")
        plog_path = os.path.join(self.collect_path, "collection", "plog")
        sub_ptr_rst = {}
        sub_ptr_index = []
        sub_ptr_addrs = []
        dynamic_tensor_count = []
        de_deplicate = []
        get_io_cmd = ["grep", r"\[Dump\]\[Exception\]", "-inrE", plog_path]
        get_io_regexp = r"begin to load .*? tensor.*?end to load .*? tensor"
        get_io_ret = utils.get_inquire_result(get_io_cmd, get_io_regexp)
        idx = 0

        for ret in get_io_ret:
            if idx > len(info.bin_list) - 1:
                break
            get_tensor_regexp = r"exception info dump args data, addr:(.*?);"
            get_tensor_ret = re.findall(get_tensor_regexp, ret, re.M | re.S)
            tensor_cnt = len(get_tensor_ret)
            if "pointer tensor" in ret:
                get_sub_ptr_regexp = r"begin to load .*? pointer tensor.*?addr:(.*?)$"
                get_sub_ptr_ret = re.findall(get_sub_ptr_regexp, ret, re.M | re.S)
                sub_ptr_addr = get_sub_ptr_ret[0]
                # is pointer tensor
                if sub_ptr_addr not in sub_ptr_addrs:
                    sub_ptr_index.append(idx)
                    sub_ptr_addrs.append(sub_ptr_addr)
                    dynamic_tensor_count.append(tensor_cnt)
            de_deplicate.extend(get_tensor_ret)
            idx = len(list(de_deplicate))
        key_word_list = self._get_args(plog_path)
        if key_word_list is None or len(key_word_list) == 0:
            utils.print_warn_log("Failed to get args after execute.")
            return {}
        para_base = self._get_para_base(plog_path)
        if para_base == -1:
            utils.print_warn_log("Failed to get para base. The sub ptr process ends.")
            return {}

        for idx, addr, tensor_cnt in zip(
            sub_ptr_index, sub_ptr_addrs, dynamic_tensor_count
        ):
            addr = utils.get_hexstr_value(addr)
            offset = (addr - para_base) // 8
            if offset >= len(key_word_list):
                utils.print_warn_log(
                    f"Tensor with index {idx} is sub_ptr tensor,"
                    f"sub_ptr offset is {offset}, out of bounds in args"
                )
                continue
            sub_addr = key_word_list[offset]
            utils.print_debug_log(
                f"Tensor with index {idx} is sub_ptr tensor,"
                f"sub_ptr offset is {offset}, and sub_ptr address is {sub_addr}"
            )
            clip_offset = utils.get_hexstr_value(sub_addr) // 8
            if (offset + clip_offset) >= len(key_word_list):
                utils.print_warn_log(
                    f"Tensor with index {idx} is sub_ptr tensor,"
                    f"sub_ptr offset is {offset}, clip_offset is {clip_offset},"
                    f"out of bounds in args"
                )
                continue
            clip_args = key_word_list[offset : offset + clip_offset]
            utils.print_debug_log(
                f"clip_offset is {clip_offset}, and clip_args is {clip_args}"
            )
            sub_ptr_rst[idx] = {"args_list": clip_args}
            sub_ptr_rst[idx]["dynamic_tensor_count"] = tensor_cnt
        return sub_ptr_rst

    def _get_graph_file(self: any) -> str:
        utils.print_debug_log("Start to get graph file.")
        match_list = []
        for top, _, files in os.walk(
            os.path.join(self.collect_path, "collection", "graph")
        ):
            for name in files:
                file_name_pattern = re.compile(r"^ge_proto_(.*?)_Build\.txt$")
                pattern_match = file_name_pattern.match(name)
                if pattern_match:
                    match_list.append((pattern_match.group(1), os.path.join(top, name)))
        new_match_list = sorted(match_list, key=lambda s: s[0], reverse=True)
        if len(new_match_list) > 0 and len(new_match_list[0]) > 0:
            choose_file = new_match_list[0][1]
        else:
            choose_file = ""
        utils.print_debug_log(f"Choose {choose_file} to read op info.")
        return choose_file

    @staticmethod
    def _get_op_by_graph(graph_file: str, node_name, kernel_name):
        try:
            if not isinstance(graph_file, str):
                utils.print_warn_log(f"graph_file: {graph_file} cannot find.")
                return None
            if not os.path.exists(graph_file):
                utils.print_warn_log(f"Failed to find graph_file: {graph_file}.")
                return None
            with open(graph_file, "r", encoding="utf-8") as graph:
                text = graph.read()
                regexp = r'(op\s+\{\s+name:\s+"%s".+?%s.+?\})\s+op\s+\{' % (
                    node_name,
                    kernel_name,
                )
                ret = re.findall(regexp, text, re.M | re.S)
                if not ret:
                    utils.print_warn_log(
                        f"Failed to get op for node({node_name}) kernel({kernel_name})."
                    )
                    return None
                return ret[0]
        except (OSError, UnicodeDecodeError, re.error):
            utils.print_warn_log(f"Failed to open file graph_file: {graph_file}.")
            return None

    def _write_summary_file(self: any, summary_info_list: list) -> None:
        summary = """本次信息收集发生于%s，只收集第1个AICERROR，概要如下：
        ***************************************************************************************************
        %s
        ***************************************************************************************************
        建议选择最近发生的AICERROR，查看其中的info.txt， 日志打印信息查看其中的debug_info.txt。

        """ % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())),
            "\n".join(summary_info_list),
        )
        summary_file = os.path.join(self.collect_path, "README.txt")
        utils.write_file(summary_file, summary)
        utils.print_info_log("The summary info is saved in %s" % summary_file)

        utils.print_info_log(
            "Analysis finished, please check %s, you can "
            "view README.txt first." % self.collect_path
        )
        current_path = os.getcwd()
        print_info_path = current_path + "/debug_info.txt"
        print_info_cmd = ["mv", print_info_path, self.collect_path]
        utils.execute_command(print_info_cmd)

    def _get_atomic_err_log(self: any) -> list:
        cmd = ["grep", "dha status 1", "-nr", self.collect_path]
        status, _ = utils.execute_command(cmd)
        if status == 0:
            utils.print_debug_log("#" * 70)
            utils.print_debug_log(
                'Find "dha status 1" in plogs. Maybe atomic add error happened!'
            )
            utils.print_debug_log("#" * 70)
            return True
        return False

    def _get_aic_info(self, kernel_name):
        plog_path = os.path.join(self.collect_path, "collection", "plog")
        aic_info_cmd = [
            "grep",
            "-r",
            "-C",
            "1024",
            f"\\[AIC_INFO\\] dev_func:{kernel_name}",
            plog_path,
        ]
        _, aic_info = utils.execute_command(aic_info_cmd)
        return aic_info

    def _get_tiling_l1(self, kernel_name) -> tuple:
        aic_info = self._get_aic_info(kernel_name)
        tiling_key_regexp = r"\[AIC_INFO\]\stiling_key:([0-9]{1,})"
        tiling_key_ret = re.findall(tiling_key_regexp, aic_info, re.M)
        if len(tiling_key_ret) == 0:
            utils.print_warn_log(f"Failed to get {tiling_key_regexp}")
            tiling_key = "0"
        else:
            tiling_key = utils.get_str_value(tiling_key_ret[0])

        block_dim_regexp = r"\[AIC_INFO\]\sblock_dim:(\d+)"
        block_dim_ret = re.findall(block_dim_regexp, aic_info, re.M)
        if not block_dim_ret:
            utils.print_warn_log(f"Failed to get {block_dim_regexp} is null.")
            block_dim = -1
        else:
            block_dim = utils.get_str_value(block_dim_ret[0])
        return tiling_key, block_dim

    def _get_tiling_l0(self) -> tuple:
        if not self.ffts_flag:
            plog_path = os.path.join(self.collect_path, "collection", "plog")
            aic_info_cmd = ["grep", "-r", "tilingKey =", plog_path]
            _, aic_info = utils.execute_command(aic_info_cmd)
            tiling_key_regexp = r"tilingKey = (.*?),"
            tiling_key_ret = re.findall(tiling_key_regexp, aic_info, re.M)
            if not tiling_key_ret:
                utils.print_warn_log("Unable to get tilingKey in plog, set tilingKey=0")
                tiling_key = 0
            else:
                tiling_key = utils.get_str_value(tiling_key_ret[0])
                tiling_key = 0 if tiling_key == -1 else tiling_key
            block_dim_regexp = r"blockDim=(\d+)"
            block_dim_ret = re.findall(block_dim_regexp, aic_info, re.M)
            if not block_dim_ret:
                utils.print_warn_log("Unable to get blockDim in plog, set block_dim=0")
                block_dim = 0
            else:
                block_dim = utils.get_str_value(block_dim_ret[0])
            return tiling_key, block_dim
        else:
            plog_path = os.path.join(self.collect_path, "collection", "plog")
            aic_info_cmd = ["grep", "-r", "fftsplus aivector error", plog_path]
            _, aic_info = utils.execute_command(aic_info_cmd)
            kernel_name_regexp = r"kernel_name=(.*?),"
            kernel_name_ret = re.findall(kernel_name_regexp, aic_info, re.M)
            if not kernel_name_ret:
                utils.print_warn_log("Unable to get tilingKey in plog, set tilingKey=0")
                tiling_key = 0
            else:
                kernel_name = (
                    kernel_name_ret[0].replace("_mix_aic", "").replace("_mix_aiv", "")
                )
                tiling_key = utils.get_str_value((kernel_name.split("_")[-1]))
                tiling_key = 0 if tiling_key == -1 else tiling_key
            block_dim_regexp = r"blockDim=(\d+)"
            block_dim_ret = re.findall(block_dim_regexp, aic_info, re.M)
            if not block_dim_ret:
                utils.print_warn_log("Unable to get block_dim in plog, set block_dim=0")
                block_dim = 0
            else:
                block_dim = utils.get_str_value(block_dim_ret[0])
            return tiling_key, block_dim

    def _get_tiling_data_l1(self, kerel_name):
        aic_info = self._get_aic_info(kerel_name)
        tiling_data_regexp = r"\[AIC_INFO\]\stiling_data:(.*)"
        tiling_data_ret = re.findall(tiling_data_regexp, aic_info, re.M)
        if len(tiling_data_ret) == 0:
            utils.print_warn_log(f"Failed to get {tiling_data_regexp}")
            tiling_data = ""
        else:
            if tiling_data_ret[0].startswith("0x"):
                temp_tiling_data = ""
                for tiling_data in tiling_data_ret:
                    temp_tiling_data += (
                        tiling_data.replace(" 0x", "").replace("0x", "").strip()
                    )
                try:
                    tiling_data = bytes.fromhex(temp_tiling_data)
                except ValueError:
                    utils.print_warn_log(
                        f"Failed to decode tiling_data {temp_tiling_data}"
                    )
                    tiling_data = bytes.fromhex("0000")
            else:
                temp_tiling_data = ""
                for tiling_data in tiling_data_ret:
                    temp_tiling_data += tiling_data.strip()
                tiling_data = bytes(temp_tiling_data, "utf-8")
        return tiling_data

    def get_tiling_info(self, kernel_name=""):
        if self.parse_level == 0:
            return self._get_tiling_l0()
        else:
            return self._get_tiling_l1(kernel_name)

    def get_tiling_data(self, kernel_name=""):
        if self.parse_level == 0:
            plog_path = os.path.join(self.collect_path, "collection", "plog")
            tiling_data = TilingDataParser(plog_path).parse()
        else:
            tiling_data = self._get_tiling_data_l1(kernel_name)
        return tiling_data

    def write_tiling_data_to_file(self, info):
        # 优先l0_exception_dump 获取tiling data 信息
        target_bin = os.path.join(info.kernel_path, info.kernel_name + "_tiling.bin")
        if info.tiling_data_bytes:
            tiling_data = info.tiling_data_bytes
        else:
            tiling_data = self.get_tiling_data(info.kernel_name)

        if tiling_data and os.path.exists(info.kernel_path):
            with open(target_bin, "wb") as f:
                f.write(tiling_data)
            info.tiling_data = target_bin
            utils.print_debug_log(f"Tiling data is saved to {target_bin} successfully.")
        else:
            utils.print_debug_log("No tiling data is found in dump files and logs.")

    def get_ffts_addrs_num(self):
        plog_path = os.path.join(self.collect_path, "collection", "plog")
        get_idx_cmd = ["grep", "begin to load normal tensor", "-inrE", plog_path]
        get_idx_regexp = r".*?index:(\d+)"
        get_idx_ret = utils.get_inquire_result(get_idx_cmd, get_idx_regexp)
        if not get_idx_ret:
            return 0
        return int(get_idx_ret[0])

    @staticmethod
    def _cal_shape_size(shape_str):
        utils.print_debug_log("shape_str is {}".format(shape_str))
        if shape_str == "[]":
            return 1
        shape_str_list = shape_str.replace("[", "").replace("]", "").split(",")
        return reduce(lambda x, y: int(x) * int(y), shape_str_list)

    @staticmethod
    def _check_addr_in_range(addr, size, ranges):
        if not isinstance(addr, int):
            addr = int(addr)

        for addr_range in ranges:
            if "0x" in addr_range[0]:
                range_left = utils.get_hexstr_value(addr_range[0])
                range_right = utils.get_hexstr_value(addr_range[0]) + addr_range[1]
            else:
                range_left = int(addr_range[0])
                range_right = int(addr_range[0]) + addr_range[1]
            if range_left <= addr <= addr + size <= range_right:
                return True
        return False

    def _get_info_for_decompile(self: any, info: any) -> tuple:
        info.instr = ""
        # 最后一条指令 算差值
        utils.print_debug_log("Calculate the address offset.")
        current_pc5 = "0" + info.aic_error_info.get("current_pc", "")[-5:]
        start_pc5 = "0" + info.aic_error_info.get("start_pc", "")[-5:]
        current_pc5_value = utils.get_hexstr_value(current_pc5)
        start_pc5_value = utils.get_hexstr_value(start_pc5)
        utils.print_debug_log(
            f"The address offset is {hex(current_pc5_value - start_pc5_value)[2:]}."
        )

        # 估算err pc
        err_pc = ""
        try:
            err_pc = self._get_err_pc(info, current_pc5_value, start_pc5_value)
        except (ValueError, TypeError, IndexError, AttributeError):
            utils.print_debug_log("_get_err_pc failed")
        if err_pc == "":
            utils.print_debug_log("This aicore error has no estimated offset.")
        else:
            utils.print_debug_log(f"Estimated error address offset is {err_pc}.")

        return err_pc

    @classmethod
    def _get_symbolize_o_file(cls, info: any) -> str:
        """Pick the *.o to symbolize: the kernel *.o, host.o only as a fallback.

        仅当 kernel 的 *.o 不存在时才退到 <kernel_name>*_host.o，两者都拿不到则
        返回空串，交由 symbolize 打告警。
        """
        if info.bin_file and os.path.exists(info.bin_file):
            return info.bin_file
        if not info.kernel_path or not info.kernel_name:
            return info.bin_file
        # host.o 按去后缀名命名（与 _get_kernel_and_json_file 取 .o 时一致），
        # mix 算子直接拿 Foo_mix_aic 去 glob 恒不命中。
        host_o = cls._find_sk_host_o(
            info.kernel_path, cls._strip_kernel_name_suffix(info.kernel_name)
        )
        if not host_o:
            return info.bin_file
        utils.print_info_log(
            f"The *.o file {info.bin_file} does not exist, fall back to {host_o}."
        )
        return host_o

    @classmethod
    def _set_corrected_instr(cls, info: any) -> None:
        """Fill in the corrected error line and its source locations.

        源码位置两路取值，优先级同 PC 修正：先取 adump 汇总日志的
        outerSrc/innerSrc（BuildGroupSummaryText），没有再本地 llvm-symbolizer
        解析。修正后的 PC 与两者都无关，故位置解析失败（未安装、执行失败、
        .o 无调试信息）时照常输出修正 PC，仅把位置部分换成提示。
        """
        if not info.corrected_pc:
            return
        offset = info.corrected_pc.get("offset", 0)
        plog_path = info.corrected_pc.get("plog_path", "")
        core_id = info.aic_error_info.get("core_id", "")
        # 每个组的首报错核独立定位源码：id+coreType 一起匹配 adump 汇总，
        # .o 编译文件跨核复用。AIC 与 AIV 共用数字 core id，type 必须校验。
        core_type = pc_corrector.derive_core_type(info.aic_error_info)
        src = pc_corrector.get_corrected_src(
            plog_path, core_id, cls._get_symbolize_o_file(info), offset, core_type
        )
        info.corrected_instr = f"Error occurred most likely at line: {hex(offset)}\n"
        if not src:
            info.corrected_instr += "Unable to calculate the corrected source location, check the logs for more details.\n"
            return
        info.corrected_instr += f"outerSrc: {src.get('outermost', '')}\n"
        innermost = src.get("innermost", "")
        if innermost:
            info.corrected_instr += f"innerSrc: {innermost}\n"

    @staticmethod
    def _get_decompile_status(o_file: str, decompile_file: str) -> int:
        if shutil.which(Constant.OBJ_DUMP_FILE):
            objdump = Constant.OBJ_DUMP_FILE
        elif shutil.which(Constant.NEW_DUMP_FILE):
            objdump = Constant.NEW_DUMP_FILE
        else:
            utils.print_error_log("No cce-objdump or llvm-objdump found.")
            return -1
        cmd = [objdump, "-d", "--line-numbers", o_file]
        status, _ = utils.execute_command(cmd, file_out=decompile_file)
        return status

    @staticmethod
    def _update_err_pc(err_pc: str, decompile_file: str, kernel_name: str) -> None:
        # 模板类算子是多个.o合成需找到对应的行号
        utils.print_debug_log(f"Start to update err pc: {err_pc}.")
        update_pc_cmd = ["grep", f"{kernel_name}$local", decompile_file]
        update_pc_regexp = r"([0-9A-Za-z]*?)\s+<{}\$local>".format(kernel_name)
        update_pc_ret = utils.get_inquire_result(update_pc_cmd, update_pc_regexp)
        if not update_pc_ret:
            utils.print_debug_log("No need to update err pc.")
            return err_pc
        else:
            err_pc = hex(int(err_pc, 16) + int(update_pc_ret[0], 16))[2:]
            utils.print_debug_log(
                f"find base pc is 0x{update_pc_ret[0]}, err pc after update is  0x{err_pc}."
            )
            return err_pc

    def _decompile(
        self: any, kernel_meta_path: str, dir_path: str, info: AicErrorInfo
    ) -> bool:
        kernel_name = info.kernel_name

        tiling_key = info.tiling_key

        # 获取cce, o, json路径
        cce_file = info.cce_file
        o_file = info.bin_file
        json_file = info.json_file
        if not os.path.exists(o_file) and not os.path.exists(json_file):
            utils.print_error_log(
                "The *.o and *.json file that needs to be decompiled does not exist."
            )
            return False

        # decompile .o file
        decompile_file = o_file + ".txt"
        status = self._get_decompile_status(o_file, decompile_file)
        if status != 0:
            utils.print_error_log(
                f"Failed to decompile {o_file}, you can fix problem according to the message above, "
                f"or copy {Constant.OBJ_DUMP_FILE} and {o_file} to another host and execute : "
                f"{Constant.OBJ_DUMP_FILE} -d {kernel_name}.o > {kernel_name}.o.txt"
            )
            return False
        if self.is_sk:
            # SK场景下只有host.o，没有cce/json，仅复制host.o，跳过L1的cce/tbe行号匹配
            utils.copy_src_to_dest([o_file], dir_path)
            return True
        utils.copy_src_to_dest([cce_file, o_file, json_file], dir_path)
        loc_json_file = os.path.join(kernel_meta_path, kernel_name + "_loc.json")
        err_pc = self._get_info_for_decompile(info)
        if self.parse_level == 1:
            err_pc = self._update_err_pc(
                err_pc, decompile_file, f"{kernel_name}_{tiling_key}"
            )
            cce_tbe_result = self._get_cce_tbe_code_number(
                decompile_file, loc_json_file, err_pc, info
            )

            return cce_tbe_result
        else:
            return True

    @staticmethod
    def _get_err_pc(info: any, current_pc5_value: int, start_pc5_value: int) -> str:
        # 估算err pc
        extra_pc = info.find_extra_pc()  # [9:2]
        if extra_pc != "":
            ori_pc = bin(current_pc5_value)[2:]
            if len(extra_pc) == 16:
                new_pc_bin = extra_pc + "00"
            elif len(ori_pc) == 1:
                new_pc_bin = extra_pc + "0" + ori_pc
            elif len(ori_pc) <= 10:
                new_pc_bin = extra_pc + ori_pc[-2:]
            else:
                new_pc_bin = ori_pc[:-10] + extra_pc + ori_pc[-2:]
            new_pc_value = int(new_pc_bin, 2)
            if (
                new_pc_value - 1024 > start_pc5_value
                and new_pc_value > current_pc5_value
                and len(extra_pc) != 16
            ):
                new_pc_value -= 1024
            if new_pc_value - start_pc5_value > 0:
                err_pc = hex(new_pc_value - start_pc5_value)[2:]
            else:
                err_pc = hex(current_pc5_value - start_pc5_value)[2:]
        else:
            err_pc = hex(current_pc5_value - start_pc5_value)[2:]
        info.instr += "\nError occurred most likely at line: 0x%s\n\n" % err_pc
        return err_pc

    @staticmethod
    def _read_decompile_file(decompile_file: str, err_pc: str, info: any) -> str:
        with open(decompile_file, "r", encoding="utf-8") as fo_file:
            cce_code = ""
            cce_code_num = ""
            for line in fo_file.readlines():
                regexp = r"cce:(\d+)"
                ret = re.findall(regexp, line, re.M)
                if len(ret) > 0:
                    cce_code = line
                    cce_code_num = ret[0]
                elif err_pc + ":" in line:
                    info.instr += "%s:%s\n" % (fo_file.name, err_pc)
                    break
            cce_line_number = cce_code.split(os.sep)[-1]
            utils.print_debug_log(
                f"Maybe find cce code line number is {cce_line_number}"
            )
            info.instr += "%s" % cce_line_number
        return cce_code_num

    @staticmethod
    def _read_loc_json_file(loc_json_file: str, cce_code_num: str, info: any) -> None:
        with open(loc_json_file, "r", encoding="utf-8") as load_f:
            load_dict = json.load(load_f)
            for line in load_dict[0]["cce_line2loc"]:
                if str(line["cce_line"]) == cce_code_num and line["loc"][0] != "":
                    info.instr += "%s:%s\n" % (line["loc"][0], line["loc"][1])

    def _get_cce_tbe_code_number(
        self: any, decompile_file: str, loc_json_file: str, err_pc: str, info: any
    ) -> bool:
        # txt code to cce number
        if os.path.exists(decompile_file) is False:
            utils.print_error_log("The decompile file does not exist.")
            return False

        if err_pc != "":
            cce_code_num = self._read_decompile_file(decompile_file, err_pc, info)
            if not cce_code_num:
                utils.print_warn_log(
                    f"The cce code num is not exist in decompile file {decompile_file}."
                )
                return False

            # cce to tbe code number
            if not os.path.exists(loc_json_file) or os.stat(loc_json_file).st_size == 0:
                utils.print_warn_log(
                    f"The file {loc_json_file} is not exist or file is empty."
                )
                return True
            self._read_loc_json_file(loc_json_file, cce_code_num, info)

            cce_file = info.cce_file
            if os.path.exists(cce_file):
                with open(cce_file, "r", encoding="utf-8") as f:
                    for index, line in enumerate(f):
                        if int(cce_code_num) - 1 == index:
                            if "PIPE_ALL" in line:
                                info.flag_check = "Please check the set_flag/wait_flag is match or not!!!."
                                break
            else:
                utils.print_error_log("The cce file does not exist.")
                return False
        return True

    @staticmethod
    def __generate_case(config, case_path, op_test):
        config_str = json.dumps(config, indent=4)
        op_test_str = json.dumps(op_test, indent=4)
        case_content = f"""
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase
config = {config_str}
OP_TEST = {op_test_str}
SingleOpCase.run(config, OP_TEST)
exit()"""

        case_file = os.path.join(case_path, f"test_{op_test}.py")
        utils.print_debug_log(f"Generate case file {case_file}")
        with open(case_file, "w", encoding="utf-8") as f:
            f.write(case_content)
        return case_file

    @staticmethod
    def _test_single_op(
        aic_info: AicErrorInfo, case_path: str, compile_temp_dir: str, op_test: str
    ):
        single_op_case = SingleOpCase(aic_info, op_test)
        config = single_op_case.generate_config()
        config.update({"compile_temp_dir": compile_temp_dir})
        case_file = AicoreErrorParser.__generate_case(config, case_path, op_test)

        date_string = time.strftime("%Y%m%d%H%M%S", time.localtime(int(time.time())))
        single_op_log_path = os.path.join(case_path, f"{op_test}_{date_string}")
        utils.print_debug_log(f"The single_op_log_path is {single_op_log_path}")
        current_path = os.path.dirname(os.path.abspath(__file__))
        new_env = os.environ.copy()
        new_env["ASCEND_SLOG_PRINT_TO_STDOUT"] = "0"
        new_env["ASCEND_PROCESS_LOG_PATH"] = single_op_log_path
        # or '' 兜底：干净环境未设 PYTHONPATH 时 get() 返回 None，直接 + 会抛 TypeError
        new_env["PYTHONPATH"] = (
            (new_env.get("PYTHONPATH") or "") + ":" + os.path.dirname(current_path)
        )

        AicoreErrorParser.comment_cce_in_case(case_file)
        # G.EDV.05：用 sys.executable 绝对路径，避免依赖 PATH 里的 python3
        _exec_run = subprocess.run(
            [sys.executable, case_file],
            env=new_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        _stdout = _exec_run.stdout.decode("utf-8")
        _len = _stdout.find("SingleOpCase.run Execute Info")
        mem_key = "Access Memory without OverBoundary"
        test_info: str = (
            "Out-of-bounds memory access." if mem_key in _stdout[_len:] else ""
        )
        single_op_ret = not AicoreErrorParser.search_aicerr_log(
            aic_info.kernel_name, single_op_log_path
        )
        if _exec_run.returncode != 0 and single_op_ret:
            # 用例进程非 0 退出、且日志里没有 aicore error：说明用例没真正跑起来
            # （依赖缺失/语法错误等），不能按"执行成功"上报，否则掩盖故障原因。
            utils.print_error_log(
                f"The single op case {case_file} exited with code {_exec_run.returncode} "
                f"and no aicore error was found in {single_op_log_path}. "
                f"stdout: {_stdout}, stderr: {_exec_run.stderr.decode('utf-8')}"
            )
            return RetCode.NOT_RUN, test_info, single_op_log_path
        if not single_op_ret:
            AicoreErrorParser.print_single_op_result(case_file)
            return RetCode.FAILED, test_info, single_op_log_path

        # 日志里没有aicore error时，才需要区分"跑通了但没复现"和"用例根本没跑起来"
        # （如kernel符号注册失败、launch失败），后者不能作为"未复现"的依据
        not_run_keys = (
            NOT_RUN_EXEC_FAILED,  # exec_single_case 抛异常
            NOT_RUN_LAUNCH_FAILED,  # launch_ret/sync_ret 非0
        )
        for not_run_key in not_run_keys:
            if not_run_key in _stdout:
                utils.print_error_log(
                    f"The {op_test} case was not executed successfully, so the AI Core exception cannot be "
                    f"confirmed by it. Please check {single_op_log_path} and the case file {case_file}."
                )
                AicoreErrorParser.print_single_op_result(case_file)
                return RetCode.NOT_RUN, test_info, single_op_log_path

        return RetCode.SUCCESS, test_info, single_op_log_path

    @staticmethod
    def comment_cce_in_case(case_file):
        with open(case_file, "r+", encoding="utf-8") as f:
            content = f.read().replace('"cce_file"', '# "cce_file"')
            f.seek(0)
            f.truncate(0)
            f.write(content)

    @staticmethod
    def print_single_op_result(case_file):
        split_line = "#" * 50
        utils.print_debug_log(split_line)
        utils.print_debug_log("Single op test failed! Please check OP or input data!")
        current_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        utils.print_debug_log(
            f"Run 'export PYTHONPATH={current_path}:$PYTHONPATH;cd {current_path};"
            f"python3 {case_file}' can test op!"
        )
        utils.print_debug_log(split_line)

    @staticmethod
    def _write_errorinfo_file(err_i_folder: str, analyse_result: str) -> None:
        info_file = os.path.join(err_i_folder, "info.txt")
        utils.write_file(info_file, analyse_result)
        utils.print_info_log(f"Analysis info is saved in {info_file}")

    def _get_data_dump_result(self: any):
        try:
            data_dump_failed_cmd = [
                "grep",
                "exception_dumper.cc.*Dump exception.*failed",
                "-nr",
                self.collect_path,
            ]
            data_dump_ret, _ = utils.execute_command(data_dump_failed_cmd)
            if data_dump_ret == 0:
                utils.print_warn_log(
                    "Data dump failed in exception dump. Please contact GE to resolve it!"
                )
                return False
        except utils.AicErrException:
            utils.print_error_log("Failed to dump data!")
        try:
            data_dump_failed_cmd1 = [
                "grep",
                r"\[Dump\]\[Exception\] D2H failed",
                "-nr",
                self.collect_path,
            ]
            data_dump_failed_cmd2 = [
                "grep",
                r"\[Exception\] the address maybe invalid",
                "-nr",
                self.collect_path,
            ]
            data_dump_ret1, _ = utils.execute_command(data_dump_failed_cmd1)
            data_dump_ret2, _ = utils.execute_command(data_dump_failed_cmd2)
            if data_dump_ret1 == 0 or data_dump_ret2 == 0:
                utils.print_warn_log(
                    "Data dump failed. Maybe memory is invalid. Search 'D2H failed' in plog!"
                )
                return False
        except utils.AicErrException:
            utils.print_error_log("Failed to dump data!")
        return True

    def check_dump_result(self: any, dfx_message: str, info: AicErrorInfo) -> bool:
        data_dump_failed_cmd = [
            "grep",
            "exception_dumper.cc.*Dump exception.*failed",
            "-nr",
            self.collect_path,
        ]
        data_dump_ret, _ = utils.execute_command(data_dump_failed_cmd)
        if data_dump_ret == 0:
            utils.print_error_log(
                "Data dump failed in exception dump. Please contact GE to resolve it!"
            )
            return False
        data_dump_copy_failed_cmd = [
            "grep",
            r"\[Dump\]\[Exception\] D2H failed",
            "-nr",
            self.collect_path,
        ]
        data_dump_copy_ret, _ = utils.execute_command(data_dump_copy_failed_cmd)
        if data_dump_copy_ret == 0:
            utils.print_error_log(
                "Data dump failed. Copy data from device to host fail!"
            )
            return False
        memory_failed_str = r"\[Dump\]\[Exception\] the address maybe invalid"
        memory_faided_ret = re.findall(memory_failed_str, dfx_message)
        if memory_faided_ret:
            utils.print_error_log("Data dump failed. Maybe memory is invalid!")
            return False
        ffts_addr_num_str = r"begin to load normal tensor, index:(\d+)"
        ffts_addr_num_ret = re.findall(ffts_addr_num_str, dfx_message)
        if not ffts_addr_num_ret:
            info.ffts_addrs_num = 0
            return True
        info.ffts_addrs_num = int(ffts_addr_num_ret[0])
        return True

    def _need_atomic_clean(self: any, kernel_meta_path: str, info: any) -> bool:
        kernel_name = info.kernel_name
        json_file = os.path.join(kernel_meta_path, kernel_name + ".json")
        if not os.path.exists(json_file):
            utils.print_warn_log(f"Can not find {json_file}!")
            return False
        with open(json_file, "r", encoding="utf-8") as f:
            json_obj = json.load(f)
            # compileInfo in json file means the kernel is dynamic
            if (
                json_obj.get("compileInfo") is None
                and json_obj.get("compile_info") is None
            ):
                utils.print_debug_log(
                    "No compile_info found in json file, no need to check atomic clean!"
                )
                return False
            parameters = json_obj.get("parameters")
            for param in parameters:
                if param is not None:
                    return True
        return False

    def _check_atomic_clean(
        self: any, kernel_meta_path: str, info: AicErrorInfo
    ) -> bool:
        need_atomic_clean = self._need_atomic_clean(kernel_meta_path, info)
        if need_atomic_clean:
            cmd = [
                "grep",
                f"AtomicLaunchKernelWithFlag_{info.node_name}",
                "-nr",
                self.collect_path,
            ]
            status, _ = utils.execute_command(cmd)
            if status == 0:
                return True
            utils.print_warn_log(
                f"Can not find AtomicLaunchKernelWithFlag_{info.node_name} in plog!"
            )
            return False
        return True

    def _get_args_from_info(self: any, key_words: str) -> list:
        args_exec_cmd = ["grep", key_words, "-nr", self.collect_path]
        args_exec_regexp = r":([x0-9a-fA-F,\s]+)addr"
        args_exec_rets = utils.get_inquire_result(args_exec_cmd, args_exec_regexp)

        if not args_exec_rets:
            args_exec_cmd = ["grep", key_words, "-Enr", self.collect_path]
            args_exec_regexp = r"args.*?after execute:([x0-9a-fA-F,\s]+)"
            args_exec_rets = utils.get_inquire_result(args_exec_cmd, args_exec_regexp)

        if not args_exec_rets:
            args_exec_rets = []

        args_exec_result = []
        result = []
        for args_exec_ret in args_exec_rets:
            args_array = re.split(",|\\s", args_exec_ret)
            args_list = []
            for arg in args_array:
                if (not isinstance(arg, str)) or (not arg.strip()):
                    continue
                arg = arg.strip()
                if (not arg.startswith("0x")) and (arg != "0"):
                    continue
                if arg.startswith("0x") or arg == "0":
                    args_list.append(utils.get_hexstr_value(arg))
                else:
                    args_list.append(int(arg))
            args_tuple = tuple(args_list)
            if args_tuple not in args_exec_result:
                args_exec_result.append(args_tuple)
                result.extend(args_list)
        return result

    def _get_args_after_exc(self: any) -> list:
        after_key = r"\[AIC_INFO\] args.*after execute"
        return self._get_args_from_info(after_key)

    def _get_args_before_exc(self: any) -> list:
        before_key = r"\[AIC_INFO\] args before execute"
        return self._get_args_from_info(before_key)

    def _get_args_type_marks(self: any) -> dict:
        """plog IDEDD dump 标记 -> arg 序号到类型映射（info.json args 语义化用）。

        日志形态 `begin to load input/output tensor|normal tensor|workspace|
        tiling data, index:N`：normal tensor 无法区分输入输出，记为 normal，
        交由 json_report_builder 按 kernel json 数量细分；workspace/tiling
        直接定型。同一 index 以最后一条标记为准（与 IDEDD 顺序打印一致）。
        """
        plog_path = os.path.join(self.collect_path, "collection", "plog")
        cmd = ["grep", r"\[Dump\]\[Exception\] begin to load", "-inrE", plog_path]
        regexp = (
            r"begin to load (input tensor|output tensor|normal tensor|workspace|tiling data)"
            r", index:(\d+)"
        )
        ret = utils.get_inquire_result(cmd, regexp)
        type_map = {"input tensor": "input", "output tensor": "output"}
        marks = {}
        for marker, index in ret:
            idx = int(index)
            if marker in type_map:
                marks[idx] = type_map[marker]
            elif marker == "workspace":
                marks[idx] = "workspace"
            elif marker == "tiling data":
                marks[idx] = "tiling_data"
            else:  # normal tensor：输入输出待细分
                marks[idx] = "normal"
        return marks

    @staticmethod
    def _check_file_content(kernel_name, content):
        error_strings = [
            "there is an aivec error exception",
            "there is an aicore error exception",
            "there is an exception of aivec error",
            "there is an exception of aicore error",
            "aicore exception",
            "An error occurs on the device",
        ]
        for s in error_strings:
            if s in content and kernel_name in content:
                return True
        return False

    @staticmethod
    def _wait_for_log_stabilization(log_path):
        log_size = os.path.getsize(log_path)
        while True:
            time.sleep(0.2)
            current_log_size = os.path.getsize(log_path)
            if current_log_size == log_size:
                break
            log_size = current_log_size

    @staticmethod
    def search_aicerr_log(kernel_name, path):
        kernel_name = kernel_name.replace("_mix_aic", "").replace("_mix_aiv", "")
        for root, _, files in os.walk(path):
            for file in files:
                if not file.endswith(".log"):
                    continue
                log_path = os.path.abspath(os.path.join(root, file))
                AicoreErrorParser._wait_for_log_stabilization(log_path)
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if AicoreErrorParser._check_file_content(kernel_name, content):
                    return True
        return False

    @staticmethod
    def get_soc_version_from_cce(cce_file):
        if not os.path.isfile(cce_file):
            utils.print_error_log(
                f"Can not find {cce_file}, use default version Ascend910B2"
            )
            return "Ascend910B2"
        try:
            content = Path(cce_file).read_text(encoding="utf-8")

            soc_version_ret = re.findall(r'//.*?(Ascend.*?)"', content)
            if soc_version_ret:
                utils.print_debug_log(
                    f"Get soc_version {soc_version_ret[0]} from cce file {cce_file}"
                )
                if soc_version_ret[0] == "Ascend310B":
                    return "Ascend310B1"
                return soc_version_ret[0]
        except (OSError, UnicodeDecodeError, re.error):
            utils.GLOBAL_RESULT = False
        utils.print_warn_log(f"Can not get soc_version from cce file {cce_file}")
        return "Ascend910B2"

    @staticmethod
    def run_test_env(soc_version, device_id=0):
        date_string = time.strftime("%Y%m%d%H%M%S", time.localtime(int(time.time())))
        compile_temp_dir = os.path.abspath(f"temp_{date_string}")
        golden_op_path = os.path.abspath(f"golden_op_{date_string}")
        current_path = os.path.dirname(os.path.abspath(__file__))
        new_env = os.environ.copy()
        new_env["ASCEND_SLOG_PRINT_TO_STDOUT"] = "0"
        new_env["ASCEND_PROCESS_LOG_PATH"] = golden_op_path
        # or '' 兜底：干净环境未设 PYTHONPATH 时 get() 返回 None，直接 + 会抛 TypeError
        new_env["PYTHONPATH"] = (
            (new_env.get("PYTHONPATH") or "") + ":" + os.path.dirname(current_path)
        )

        # G.EDV.05：用 sys.executable 绝对路径，避免依赖 PATH 里的 python3
        cmd = [
            sys.executable,
            f"{current_path}/golden_op.py",
            soc_version,
            str(device_id),
            compile_temp_dir,
        ]
        ret = subprocess.run(cmd, env=new_env, check=False)
        if ret.returncode != 0:
            utils.print_error_log(
                f"The built-in sample operator subprocess exited with code {ret.returncode}. "
                f"Possible causes: driver not loaded, chip not supported (soc_version={soc_version}), "
                f"or golden_op.py dependencies missing. Check log at {golden_op_path}."
            )
            return False
        build_dir = Path(compile_temp_dir).joinpath(
            ModeCustom.ADD_CUSTOM.value, "build_out", "op_kernel"
        )
        build_jsons = list(build_dir.rglob(f"{ModeCustom.ADD_CUSTOM.value}*.json"))
        if not build_jsons:
            utils.print_error_log(
                f"Can not find compiled json in {build_dir}. "
                f"Possible causes: soc_version mismatch (got '{soc_version}'), "
                f"or CANN toolkit (atc/ccec) not correctly installed."
            )
            return False
        with open(build_jsons[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        # 删除临时文件夹
        if os.path.exists(compile_temp_dir):
            shutil.rmtree(compile_temp_dir)
        kernel_name = data.get("kernelName")
        if kernel_name:
            if AicoreErrorParser.search_aicerr_log(kernel_name, golden_op_path):
                utils.print_error_log(
                    f"AI Core error detected while running the built-in sample operator. "
                    f"Possible causes: hardware fault, driver version mismatch, or insufficient device memory. "
                    f"Check the device log at {golden_op_path} for details."
                )
                return False
        if os.path.exists(golden_op_path):
            shutil.rmtree(golden_op_path)
        return True

    @staticmethod
    @screen_error
    def add_objdump_to_path():
        # decompile
        utils.print_debug_log("Start looking for the location of cce-objdump.")
        obj_dump_file = (
            "cce-objdump_aarch64" if "aarch64" in platform.machine() else "cce-objdump"
        )
        obj_dump_file = os.path.join(os.getcwd(), "tools", obj_dump_file)
        if os.path.exists(obj_dump_file):
            # 原实现用 os.system("chmod 755") 失败只回非零码不抛异常；改用 os.chmod 后
            # 需自行兜住 OSError（文件刚被删、权限不足等），否则会中断整个分析流程。
            try:
                os.chmod(
                    obj_dump_file,
                    stat.S_IRWXU
                    | stat.S_IRGRP
                    | stat.S_IXGRP
                    | stat.S_IROTH
                    | stat.S_IXOTH,
                )
            except OSError as error:
                utils.print_warn_log(f"Failed to chmod {obj_dump_file}. {error}")
            os.environ["PATH"] = (
                os.path.join(os.getcwd(), "tools") + ":" + os.environ["PATH"]
            )
        else:
            cce_dump = shutil.which("cce-objdump") or shutil.which("llvm-objdump")
            if not cce_dump:
                # guess where is cce-objdump
                parent_path = (
                    "aarch64-linux"
                    if "aarch64" in platform.machine()
                    else "x86_64-linux"
                )
                cce_dump_guess = os.path.join(
                    "/usr/local/Ascend/latest",
                    parent_path,
                    "ccec_compiler/bin/cce-objdump",
                )
                llvm_dump_guess = os.path.join(
                    "/usr/local/Ascend/latest",
                    parent_path,
                    "ccec_compiler/bin/llvm-objdump",
                )
                if os.path.exists(cce_dump_guess):
                    cce_dump = cce_dump_guess
                elif os.path.exists(llvm_dump_guess):
                    cce_dump = llvm_dump_guess
                else:
                    utils.print_error_log(
                        "Cannot find cce-objdump! please add cce-objdump path in env PATH."
                    )
                    raise utils.AicErrException(
                        Constant.MS_AICERR_EXECUTE_COMMAND_ERROR
                    )
            os.environ["PATH"] = os.path.dirname(cce_dump) + ":" + os.environ["PATH"]

    def check_hash_id(self, hash_id, single_op_log_path) -> bool:
        error_log = "Aicore kernel execute failed|AI Core kernel execution failed"
        kernel_name_cmd = ["grep", error_log, "-inrE", single_op_log_path]
        kernel_name_regexp = r".*?hash=(\d+)"
        kernel_name_ret = utils.get_inquire_result(kernel_name_cmd, kernel_name_regexp)
        if not kernel_name_ret:
            utils.print_warn_log(
                f"Can't find hash id in single_op_log_path:{single_op_log_path}."
            )
            return False

        if hash_id != kernel_name_ret[0]:
            utils.print_warn_log(
                "The hash_id from plog is different with the hash_id which from the device."
            )
            return False

        return True

    @staticmethod
    def get_soc_version(cce_file):
        try:
            soc_version = DSMIInterface().get_chip_info(0).get_complete_platform()
        except (OSError, AttributeError, UnicodeDecodeError, IndexError):
            utils.print_error_log("Get soc_version form platform failed!")
            soc_version = None
        if not soc_version:
            soc_version = AicoreErrorParser.get_soc_version_from_cce(cce_file)
        utils.print_debug_log(f"Get soc_version of {soc_version}.")
        return soc_version

    def run_single_operator(self, info, err_i_folder):
        date_string = time.strftime("%Y%m%d%H%M%S", time.localtime(int(time.time())))
        compile_temp_dir = os.path.abspath(f"temp_{date_string}")
        utils.print_info_log("Step 9. Verify a single operator.")
        # SK场景下只有host.o、没有json，仅校验bin_file；非SK场景校验bin_file+json_file
        if self.is_sk:
            kernel_file_exist = os.path.exists(info.bin_file)
        else:
            kernel_file_exist = os.path.exists(info.bin_file) and os.path.exists(
                info.json_file
            )
        if not kernel_file_exist:
            utils.print_info_log(
                "Skip exec single op case because the kernel file dose not exist."
            )
        else:
            host_info = copy.deepcopy(info)
            compile_path = os.path.join(self.collect_path, "collection", "compile")
            host_info.bin_file = self._find_sk_host_o(compile_path, info.kernel_name)
            if host_info.bin_file and os.path.exists(host_info.bin_file):
                _, _, host_op_test_log_path = self._test_single_op(
                    host_info, err_i_folder, compile_temp_dir, "host_single_op"
                )
                if not self.check_hash_id(host_info.hash_id, host_op_test_log_path):
                    utils.print_error_log(
                        "According to the execution results of host.o single op case, "
                        "the kernel load on the host is different from the device."
                    )

            # SK场景下没有device .o，跳过device单算子测试
            if not self.is_sk:
                info.run_device_id = self.device_id
                if info.data_dump_result:
                    info.single_op_attempted = True
                    (
                        info.single_op_test_result,
                        info.single_op_mem_monitor,
                        info.single_op_log_path,
                    ) = self._test_single_op(
                        info, err_i_folder, compile_temp_dir, "single_op"
                    )
                if info.single_op_test_result != RetCode.SUCCESS:
                    self.check_hash_id(info.hash_id, info.single_op_log_path)
                else:
                    _, _, error_op_test_log_path = self._test_single_op(
                        info, err_i_folder, compile_temp_dir, "error_single_op"
                    )
                    self.check_hash_id(info.hash_id, error_op_test_log_path)

                if info.single_op_test_result == RetCode.FAILED:
                    utils.print_info_log(
                        "Successfully reproduced the AI Core exception by running the single-operator test case."
                    )
                elif (
                    info.single_op_attempted
                    and info.single_op_test_result == RetCode.NOT_RUN
                ):
                    utils.print_warn_log(
                        "The single-operator test case was not executed successfully. Whether the AI Core exception "
                        "can be reproduced is unknown."
                    )
                else:
                    utils.print_debug_log(
                        "Failed to reproduce the AI Core exception by running the single-operator test case."
                    )
        if os.path.exists(compile_temp_dir):
            # 如果编译临时文件存在，则删除临时文件夹
            shutil.rmtree(compile_temp_dir)

    def parse(self: any) -> None:
        """
        parse by collection info
        """
        utils.print_info_log("*******************Analysis*******************")
        summary_info_list = []

        self.add_objdump_to_path()
        # 检查日志是L0还是L1，以及是否为ffts+场景
        self.check_plog_info()

        # 1.收集aicore error的基本信息
        utils.print_info_log(
            "Step 1. Extract operator information, including registers, tiling, and operator files."
        )
        info = self.get_op_info()

        # 2.创建对应的aicore error文件夹
        if info is None or not self.collect_succ:
            err_i_folder = os.path.join(self.collect_path, "aicerror")
            empty_info = AicErrorInfo()
            self._write_errorinfo_file(err_i_folder, empty_info.root_cause_conclusion)
            json_report_builder.write_json_report(
                err_i_folder, empty_info, self.collect_path, collect_succ=False
            )
            return Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR
        else:
            info.err_time_obj = utils.strplogtime(
                info.aic_error_info.get("err_time", "")
            )
            err_i_folder_name = f"aicerror_0_{time.strftime('%Y%m%d%H%M%S', info.err_time_obj.timetuple())}"
            err_i_folder = os.path.join(self.collect_path, err_i_folder_name)
        utils.print_info_log(
            f"Step 2. Create a directory for storing parsing result files."
            f"The directory is {err_i_folder}"
        )

        utils.check_path_valid(err_i_folder, isdir=True, output=True)

        # 3. 分析图中的算子信息(非必须)
        utils.print_info_log(
            "Step 3. Extract the node information of an operator in the GE graph."
        )
        graph_file = self._get_graph_file()
        info.graph_file = (
            graph_file
            if self._get_op_by_graph(graph_file, info.node_name, info.kernel_name)
            else None
        )

        # 4. 分析args before 以及 args after的区别(非必须)
        utils.print_info_log(
            "Step 4. Extract and compare the data between 'args before' and 'args after'."
        )
        info.args_after_list = self._get_args_after_exc()
        info.args_before_list = self._get_args_before_exc()
        info.check_args_result = self._check_args(
            info.args_before_list, info.args_after_list
        )
        # info.json args 语义化用的 plog 类型标记（normal 待按 kernel json 细分）
        info.args_type_marks = self._get_args_type_marks()
        _load_kernel_io_counts(info)
        _refine_normal_marks(info)

        # 5. 反编译kernel文件
        utils.print_info_log(
            "Step 5. Decompile the operator file, which triggers an instruction."
        )
        kernel_meta_path = os.path.join(self.collect_path, "collection", "compile")
        # 反编译  出错指令
        result = self._decompile(kernel_meta_path, err_i_folder, info)
        if not result:
            utils.print_warn_log(
                f"decompile kernel_meta file \
                {os.path.join(kernel_meta_path, info.kernel_name)}.o failed."
            )

        # 6. 检查框架是否正确插入memset
        utils.print_info_log(
            "Step 6. Check whether memset or atomic_clean is correctly inserted"
            " before the operator in the graph."
        )
        info.atomic_clean_check = self._check_atomic_clean(kernel_meta_path, info)
        # 日志报错有0x800000，并且插入了memset才进行累加误差相关的检查
        if ("0x800000" == info.aic_error_info.get("error_code", "")) and (
            not info.atomic_clean_check
        ):
            info.atomic_add_err = self._get_atomic_err_log()

        # 7. 原方法检查输入输出地址是否在合法范围已放弃，使用exceptiondump是否成功来判断内存问题并解析dump数据, 并生成tiling data
        utils.print_info_log(
            "Step 7. Parse dump data and check whether flushing data to disk is normal."
        )
        collect_dump_data = os.path.join(self.collect_path, "collection", "dump")
        dump_parser = self._build_dump_parser(collect_dump_data, info)
        dump_parser.parse()
        if self.parse_level == 1:
            info.data_dump_result = self._get_data_dump_result()
            info.ffts_addrs_num = self.get_ffts_addrs_num()
        else:
            dfx_message = dump_parser.get_dfx_message()
            info.data_dump_result = self.check_dump_result(dfx_message, info)
        if info.data_dump_result:
            info.input_list = dump_parser.get_input_data()
            info.output_list = dump_parser.get_output_data()
            info.workspace_list = dump_parser.get_workspace_data()
            info.bin_list = dump_parser.get_bin_data()
            info.workspace = self.get_workspace_info(
                self.parse_level, info.workspace_list
            )
        else:
            info.dump_file = "Failed to get dump data of error op!"

        # tiling data 写入文件中
        self.write_tiling_data_to_file(info)

        # 8. 解析二级指针
        utils.print_info_log("Step 8. Check whether the pointer tensor exists.")
        if self.parse_level == 0:
            info.sub_ptr_addrs = self._get_sub_ptr(info)
        else:
            utils.print_warn_log(
                "The current Log is L1 exception."
                "If the operator contains pointer tensors,"
                "msaicerr tool does not support the operator."
            )

        # 9. 单算子验证
        self.run_single_operator(info, err_i_folder)

        # 10. 使用标杆算子测试环境
        utils.print_info_log(
            "Step 10. Verify the environment using the sample operator."
        )
        soc_version = self.get_soc_version(info.cce_file)
        try:
            info.env_available = AicoreErrorParser.run_test_env(
                soc_version, self.device_id
            )
            info.env_check_attempted = True
        except (OSError, ValueError, RuntimeError, TypeError, utils.AicErrException):
            # 环境检查未执行成功，保持 env_available 默认值但标记未采集，
            # info.json 的 env_check.result 据此输出 not_collected
            utils.print_info_log("run golden op failed.Test env skip!")
        # write info file
        utils.print_info_log(
            f"Step 11. Write the parsing result."
            f" The result file is saved in the {self.collect_path} directory."
        )
        self._write_errorinfo_file(err_i_folder, info.analyse())
        # 与 info.txt 同源、同目录的结构化报告（旁路可失败，不影响主流程）
        json_report_builder.write_json_report(
            err_i_folder, info, self.collect_path, collect_succ=True
        )

        summary_info_list.append(
            "%s   %s   device_id=%s   core_id=%s   task_id=%s   node=%s   "
            "kernel=%s"
            % (
                err_i_folder_name,
                info.aic_error_info.get("error_code", ""),
                info.aic_error_info.get("dev_id", ""),
                info.aic_error_info.get("core_id", ""),
                info.task_id,
                info.node_name,
                info.kernel_name,
            )
        )

        # write summary info
        self._write_summary_file(summary_info_list)

        return self.get_return_code(info)

    @staticmethod
    def get_return_code(aic_info: AicErrorInfo):
        if not aic_info.atomic_clean_check:
            return Constant.MS_AICERR_FRAMEWORK_MEMSET_MISSING
        elif aic_info.atomic_add_err:
            return Constant.MS_AICERR_ATOMIC_OPERATOR_OVERFLOW
        elif "data invalid" in aic_info.dump_info:
            return Constant.MS_AICERR_OPERATOR_INPUT_DATA_ERR
        elif not aic_info.check_args_result:
            return Constant.MS_AICERR_OPERATOR_ARGS_OVERWRITTEN
        elif not aic_info.data_dump_result:
            return Constant.MS_AICERR_MEMORY_ALLOCATION_ERR
        # NOT_RUN也返回非0：用例没跑起来时不能认为"没有发现问题"
        elif aic_info.single_op_test_result != RetCode.SUCCESS:
            return Constant.MS_AICERR_SINGLE_OP_ERR
        elif not aic_info.env_available:
            return Constant.MS_AICERR_HARDWARE_ERR  # 103
        else:
            return Constant.MS_AICERR_NONE_ERROR

    @staticmethod
    def parser_data_name(data_name):
        err_stream_id, err_task_id = None, None
        exception_file_split_str = data_name.split(".")
        if len(exception_file_split_str) > 3:
            try:
                int(exception_file_split_str[1])
                int(exception_file_split_str[2])
                err_stream_id, err_task_id = (
                    exception_file_split_str[1],
                    exception_file_split_str[2],
                )
            except ValueError:
                return err_stream_id, err_task_id
        return err_stream_id, err_task_id

    @staticmethod
    def is_scalar_register_err(tid, aic_err_rets):
        ost_su_err_code_start_include = (
            256  # outstanding 场景下 su 寄存器的错误码，起始错误码，包含256
        )
        ost_su_err_code_end_noincldue = (
            320  # outstanding 场景下 su 寄存器的错误码，结束错误码，不包含320
        )
        if not aic_err_rets:
            return False
        for aic_err_ret in aic_err_rets:
            if tid == aic_err_ret["thread_id"]:
                error_code = utils.get_str_value(aic_err_ret["error_code"])
                if (
                    ost_su_err_code_start_include
                    <= error_code
                    < ost_su_err_code_end_noincldue
                ):
                    return True
        return False

    @staticmethod
    def get_is_concurrentexe_value(log_path):
        result = {}
        if not os.path.exists(log_path):
            utils.print_info_log(f"log path is not exist : {log_path}")
            return result

        isconcurrentexe_data_cmd = ["grep", "isconcurrentexe", "-inrE", log_path]
        regex_str = (
            r"^.*\[(?:[^:]+:\d+)\](\d+).*?first taskid:\s*(\d+).*?first streamid:\s*(\d+)"
            r".*?second taskid:\s*(\d+).*?second streamid:\s*(\d+).*?isconcurrentexe:\s*(\d+)"
        )
        status, data = utils.execute_command(isconcurrentexe_data_cmd)
        if status != 0:
            utils.print_warn_log(
                f"Failed to execute command:{isconcurrentexe_data_cmd}."
            )
            return result
        match_result = re.findall(regex_str, data, re.M)
        if len(match_result) == 0:
            utils.print_warn_log(
                f"Log info does not match:{regex_str} in command result."
            )
            return result

        task_set = set()
        for _, ftsk_id, ftsk_stream_id, stsk_id, stsk_stream_id, _ in match_result:
            task_set.add((ftsk_id, ftsk_stream_id))
            task_set.add((stsk_id, stsk_stream_id))
        task_num = len(task_set)
        if task_num > 2:
            task_info = ", ".join(
                [
                    f"[task id: {tsk_id}, stream id: {stream_id}]"
                    for tsk_id, stream_id in task_set
                ]
            )
            utils.print_warn_log(
                f"{task_num} tasks detected, manual analysis required. Task info: {task_info}."
            )
            return result
        for (
            tid,
            ftsk_id,
            ftsk_stream_id,
            stsk_id,
            stsk_stream_id,
            is_concurrentexe,
        ) in match_result:
            if tid not in result.keys():
                result = {
                    tid: {
                        "first": "{}.{}".format(ftsk_stream_id, ftsk_id),
                        "second": "{}.{}".format(stsk_stream_id, stsk_id),
                        "is_concurrentexe": is_concurrentexe,
                    }
                }
        return result

    def get_node_and_kernel_name_l1(self: any) -> Optional[tuple]:
        plog_dir = os.path.join(self.collect_path, "collection", "plog")
        # 获取kernel_name
        kernel_name_cmd = ["grep", r"\[AIC_INFO\] dev_func:", "-inrE", plog_dir]
        kernel_name_regexp = r"dev_func:([a-zA-Z0-9_]{0,})$"
        kernel_name_ret = utils.get_inquire_result(kernel_name_cmd, kernel_name_regexp)
        if not kernel_name_ret:
            utils.print_error_log(
                'Failed to get "[AIC_INFO] dev_func:" in plog. Cannot run L1 test.'
            )
            return None

        if "__" in kernel_name_ret[0]:
            kernel_name_list = kernel_name_ret[0].split("__")
            kernel_name = kernel_name_list[0]
        else:
            kernel_name = kernel_name_ret[0]

        # 获取node_name、stream_id、task_id
        node_name_cmd = ["grep", r"\[AIC_INFO\] node_name:", "-inrE", plog_dir]
        regexp = r".+?node_name:(.*?),.*stream_id:(\d+)\s*.+?\s*task_id:(\d+)\s*"
        result = utils.get_inquire_result(node_name_cmd, regexp)
        if not result:
            utils.print_error_log(
                "Failed to get node name in plog. Cannot run L1 test."
            )
            return None
        node_name, stream_id, task_id = result[0]
        node_name = node_name.replace("/", "_").replace(".", "_")
        hash_id_cmd = ["grep", "hash=", "-inrE", plog_dir]
        hash_id_regexp = (
            r" stream_id=(\d+),.*?task_id=(\d+),.*?fault kernel_name=.*?,.*?hash=(\d+)"
        )
        hash_id_ret = utils.get_inquire_result(hash_id_cmd, hash_id_regexp)
        if not hash_id_ret:
            utils.print_error_log("Cannot get hash id in plog.")
            return None
        hash_id = hash_id_ret[0][2]
        AicoreErrorInfo = namedtuple(
            "AicoreErrorInfo",
            ["stream_id", "task_id", "node_name", "kernel_name", "hash_id"],
        )
        # 使用具名元组
        error_info = AicoreErrorInfo(
            stream_id, task_id, node_name, kernel_name, hash_id
        )
        return error_info

    def update_dumpinfo_for_outstanding(
        self, plog_path, dump_data_info_list, aic_err_rets
    ):
        error_stream_task = None
        dump_data_info = dump_data_info_list[0]
        isconcurrentexe_dict = self.get_is_concurrentexe_value(plog_path)
        for tid, task_info in isconcurrentexe_dict.items():
            error_stream_task = {tid: task_info["first"], "is_second_error": False}
            if int(task_info["is_concurrentexe"]) == 1 and self.is_scalar_register_err(
                tid, aic_err_rets
            ):
                error_stream_task[tid] = task_info["second"]
                error_stream_task["is_second_error"] = True

        if error_stream_task is not None:
            for dump_info in dump_data_info_list:
                thread_id, data_name = dump_info
                if (
                    thread_id in error_stream_task.keys()
                    and error_stream_task[thread_id] in data_name
                ):
                    dump_data_info = dump_info

        return error_stream_task, dump_data_info

    def _get_sk_kernel_file(
        self: any, kernel_path: str, kernel_name: str
    ) -> "KernelFile":
        # SK场景下只生成host.o，反编译目标为host.o，没有json/cce
        host_file = self._find_sk_host_o(kernel_path, kernel_name)
        if not host_file:
            utils.print_warn_log(
                f"The {kernel_name}*_host.o cannot be found in {kernel_path}."
            )
        return KernelFile(host_file, "", "")

    def _find_kernel_file_list(self: any, kernel_name: str) -> list:
        find_path_cmd = ["grep", kernel_name, "-inrE", self.collect_path]
        regexp = r"([_\-/0-9a-zA-Z.]{1,}\.json|[_\-/0-9a-zA-Z.]{1,}\.o|[_\-/0-9a-zA-Z.]{1,}\.cce)"
        kernel_file_list = utils.get_inquire_result(find_path_cmd, regexp)
        return [
            kernel_file
            for kernel_file in kernel_file_list
            if kernel_file.startswith(self.collect_path)
        ]

    @staticmethod
    def _strip_kernel_name_suffix(kernel_name: str) -> str:
        """Drop the suffixes that never appear in the compiled file names."""
        return (
            kernel_name.replace("__kernel0", "")
            .replace("_mix_aic", "")
            .replace("_mix_aiv", "")
        )

    def _get_kernel_and_json_file(self: any, kernel_name: str, tiling_key: str):
        kernel_path = os.path.join(self.collect_path, "collection", "compile")
        kernel_name = self._strip_kernel_name_suffix(kernel_name)
        if self.is_sk:
            return self._get_sk_kernel_file(kernel_path, kernel_name)

        kernel_file = self._get_kernel_file_by_name(
            kernel_path, kernel_name, tiling_key
        )
        if kernel_file is not None:
            return kernel_file

        kernel_file_list = self._find_kernel_file_list(kernel_name)
        if not kernel_file_list:
            utils.print_error_log(
                f"The {kernel_name}.o or {kernel_name}.json cannot be found in {self.collect_path}."
            )
            return None

        bin_file, json_file = self._match_kernel_by_json(kernel_path, kernel_file_list)
        if os.path.exists(bin_file) and os.path.exists(json_file):
            utils.print_info_log(
                f"kernel_file {bin_file}, json_file: {json_file} found."
            )

        bin_file, json_file, cce_file = self._fill_kernel_backup(
            kernel_file_list, bin_file, json_file, tiling_key
        )
        return KernelFile(bin_file, json_file, cce_file)
