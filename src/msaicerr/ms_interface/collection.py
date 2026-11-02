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
from ms_interface import utils
from ms_interface.constant import Constant


def is_sub_path(path, parent_path):
    path = os.path.realpath(path)
    parent_path = os.path.realpath(parent_path)
    try:
        return os.path.commonpath([path, parent_path]) == parent_path
    except ValueError:
        return False


class Collection:
    def __init__(self: any, report_path: str, output_path: str) -> None:
        self.report_path = os.path.realpath(report_path)
        self.output_path = os.path.realpath(output_path)
        self.collect_level = 0
        self.ffts_flag = False
        self.is_sk = False
        # 超长文件名场景：dump文件被框架重命名为随机数字串
        self.dump_file_rename = ""  # 映射后的实际文件名
        self._mapping_csv_path = ""  # mapping.csv路径，首次解析后缓存，避免重复find

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

    def check_argument_valid(self: any) -> None:
        utils.check_path_valid(self.report_path, isdir=True)
        utils.check_path_valid(self.output_path, isdir=True, output=True)

    def get_node_and_kernel_name_l1(self: any) -> tuple:
        plog_dir = os.path.join(self.output_path, "collection", "plog")
        # 获取kernel_name
        kernel_name_cmd = ["grep", r"\[AIC_INFO\] dev_func:", "-inrE", plog_dir]
        kernel_name_regexp = r"dev_func:([a-zA-Z0-9_]{0,})$"
        kernel_name_ret = utils.get_inquire_result(kernel_name_cmd, kernel_name_regexp)
        if not kernel_name_ret:
            utils.print_error_log(
                'Failed to get "[AIC_INFO] dev_func:" in plog. Cannot run L1 test.'
            )
            raise utils.AicErrException(Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR)

        if "__" in kernel_name_ret[0]:
            kernel_name_list = kernel_name_ret[0].split("__")
            kernel_name = kernel_name_list[0]
        else:
            kernel_name = kernel_name_ret[0]

        # 获取node_name、stream_id、task_id
        node_name_cmd = ["grep", r"\[AIC_INFO\] node_name:", "-inrE", plog_dir]
        regexp = r".+?node_name:(.*?),"
        result = utils.get_inquire_result(node_name_cmd, regexp)
        if not result:
            utils.print_error_log(
                "Failed to get node name in plog. Cannot run L1 test."
            )
            raise utils.AicErrException(Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR)
        node_name = result[0]
        node_name = node_name.replace("/", "_").replace(".", "_")
        return kernel_name, node_name

    def get_kernel_name_l0(self: any, data_name) -> tuple:
        # 获取kernel_name
        plog_dir = os.path.join(self.output_path, "collection", "plog")
        # 优先查找SK场景标志性打印，命中则直接返回其中的kernelName
        sk_kernel_name = self.get_sk_kernel_name(plog_dir)
        if sk_kernel_name:
            utils.print_debug_log(
                f"SuperKernel scenario found, kernel_name {sk_kernel_name}, node_name {data_name}"
            )
            return sk_kernel_name, data_name
        if not self.ffts_flag:
            error_log = "Aicore kernel execute failed|AI Core kernel execution failed"
            kernel_name_cmd = ["grep", error_log, "-inrE", plog_dir]
            kernel_name_regexp = (
                r".*?fault kernel_name=(.*?),.*?fault kernel info ext=(.*?),"
            )
            kernel_name_ret = utils.get_inquire_result(
                kernel_name_cmd, kernel_name_regexp
            )
            if kernel_name_ret and kernel_name_ret[0][1] != "none":
                kernel_name = kernel_name_ret[0][1]
            else:
                kernel_name_regexp = r" .*?fault kernel_name=(.*?),"
                kernel_name_ret = utils.get_inquire_result(
                    kernel_name_cmd, kernel_name_regexp
                )
                if not kernel_name_ret:
                    utils.print_error_log(f'Failed to get "{error_log}" in plog.')
                    raise utils.AicErrException(
                        Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR
                    )
                kernel_name = kernel_name_ret[0]
        else:
            kernel_name_cmd = [
                "grep",
                "fftsplus task execute failed",
                "-inrE",
                plog_dir,
            ]
            kernel_name_regexp = r".*?fault kernel_name=(.*?),"
            kernel_name_ret = utils.get_inquire_result(
                kernel_name_cmd, kernel_name_regexp
            )
            if not kernel_name_ret:
                utils.print_error_log(
                    'Failed to get "fftsplus task execute failed" in plog.'
                )
                raise utils.AicErrException(Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR)
            kernel_name = kernel_name_ret[0]

        utils.print_debug_log(
            f"AicoreError Found, kernel_name {kernel_name}, node_name {data_name}"
        )
        return kernel_name, data_name

    def _get_node_and_kernel_name(self: any, data_name) -> tuple:
        if self.collect_level == 1:
            kernel_name, node_name = self.get_node_and_kernel_name_l1()
        else:
            kernel_name, node_name = self.get_kernel_name_l0(data_name)
        return kernel_name, node_name

    def get_dump_data_info(self):
        plog_dir = os.path.join(self.output_path, "collection", "plog")
        if self.collect_level == 1:
            dump_data_cmd = ["grep", "dump exception to file", "-inrE", plog_dir]
            adump_dump_data_regexp = (
                r"(\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).+?tid\:\d+"
                r".*?extra-info\/data-dump\/(\d+)\/([\w.\-]+)"
            )
            ge_dump_data_regexp = (
                r"(\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).+? "
                r"DumpNodeInfo:.*?extra-info\/data-dump\/(\d+)\/([\w.\-]+)"
            )
            adump_dump_data_ret = utils.get_inquire_result(
                dump_data_cmd, adump_dump_data_regexp
            )
            ge_dump_data_ret = utils.get_inquire_result(
                dump_data_cmd, ge_dump_data_regexp
            )
            if not adump_dump_data_ret and not ge_dump_data_ret:
                utils.print_error_log("Check whether open exception dump.")
                raise utils.AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR)
            if adump_dump_data_ret:
                adump_dump_data_ret = sorted(adump_dump_data_ret, key=lambda x: x[0])
                err_time, device_id, data_name = adump_dump_data_ret[0]
                return err_time, device_id, data_name
            else:
                ge_dump_data_ret = sorted(ge_dump_data_ret, key=lambda x: x[0])
                err_time, device_id, data_name = ge_dump_data_ret[0]
                return err_time, device_id, data_name

        else:
            dump_data_cmd = ["grep", "dump exception to file", "-inrE", plog_dir]

            dump_data_regexp = (
                r"(\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).+?tid\:\d+"
                r".*?extra-info\/data-dump\/(\d+)\/([\w.\-]+)"
            )
            dump_data_ret = utils.get_inquire_result(dump_data_cmd, dump_data_regexp)
            if not dump_data_ret:
                utils.print_error_log("Check whether open exception dump.")
                raise utils.AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR)
            dump_data_ret = sorted(dump_data_ret, key=lambda x: x[0])
            err_time, device_id, data_name = dump_data_ret[0]
            return err_time, device_id, data_name

    @staticmethod
    def _is_oversize_name(data_name: str) -> bool:
        # 超过NAME_MAX的算子名，异常dump框架会将落盘文件重命名为随机数字串
        # NAME_MAX是字节上限，多字节文件名下需按编码后的字节数判断
        return len(os.fsencode(data_name)) > Constant.MAX_FILE_NAME_LEN

    def _get_dump_mapping_csv_path(self, device_id) -> str:
        find_mapping_cmd = [
            "find",
            self.report_path,
            "-name",
            Constant.MAPPING_CSV_FILE,
        ]
        regexp = r"[_\.\-/0-9a-zA-Z.]{1,}"
        mapping_csv_list = utils.get_inquire_result(find_mapping_cmd, regexp)
        if not mapping_csv_list:
            return ""
        # mapping.csv与dump文件同级，只取报错device对应的那一份。
        # 此处匹配到目录分隔符与文件名，避免device_id为0时误命中data-dump/01/
        device_dump_suffix = os.path.join(
            "data-dump", str(device_id), Constant.MAPPING_CSV_FILE
        )
        for mapping_csv in mapping_csv_list:
            if mapping_csv.endswith(device_dump_suffix):
                return mapping_csv
        # 不回退到其它device的映射表：各device的随机名互不相通，用错会静默收集到别的卡的dump
        utils.print_warn_log(
            f"{Constant.MAPPING_CSV_FILE} of device {device_id} cannot be found in {self.report_path}, "
            f"{len(mapping_csv_list)} {Constant.MAPPING_CSV_FILE} of other devices are ignored."
        )
        return ""

    def _resolve_dump_file_rename(self, device_id, data_name) -> str:
        # 长度未超限时不查mapping.csv，避免大目录下不必要的全盘扫描
        if not self._is_oversize_name(data_name):
            return ""
        mapping_csv_path = self._get_dump_mapping_csv_path(device_id)
        self._mapping_csv_path = mapping_csv_path
        dump_name_mapping = utils.parse_name_mapping_csv(mapping_csv_path)
        rename = dump_name_mapping.get(data_name, "")
        if rename:
            utils.print_info_log(
                f"The dump file name exceeds {Constant.MAX_FILE_NAME_LEN}, "
                f"use mapped name {rename} instead of {data_name}."
            )
        elif not mapping_csv_path:
            utils.print_warn_log(
                f"The dump file name {data_name} exceeds {Constant.MAX_FILE_NAME_LEN}, "
                f"but {Constant.MAPPING_CSV_FILE} cannot be found in {self.report_path}."
            )
        else:
            utils.print_warn_log(
                f"The dump file name {data_name} exceeds {Constant.MAX_FILE_NAME_LEN}, "
                f"but it is not recorded in {mapping_csv_path}."
            )
        self.dump_file_rename = rename
        return rename

    def collect_plog_file(self):
        find_path_cmd = ["grep", r"\[Dump\]\[Exception\]", "-inrE", self.report_path]
        find_path_regexp = r"(/[_\-/0-9a-zA-Z.]{1,}.[log|txt]):"
        plog_path_ret = utils.get_inquire_result(find_path_cmd, find_path_regexp)
        if not plog_path_ret:
            utils.print_error_log(
                f"Adump log '[Dump][Exception]' cannot be found in {self.report_path}."
            )

        ffts_check_path_cmd = [
            "grep",
            "fftsplus task execute failed",
            "-inrE",
            self.report_path,
        ]
        ffts_check_path_regexp = r"(/[_\-/0-9a-zA-Z.]{1,}.[log|txt]):"
        ffts_check_path_ret = utils.get_inquire_result(
            ffts_check_path_cmd, ffts_check_path_regexp
        )
        if ffts_check_path_ret:
            self.ffts_flag = True

        # SK场景标志性打印，命中则只生成host.o，没有device .o/.json/.cce
        sk_check_path_cmd = [
            "grep",
            "Begin to dump callback exception",
            "-inrE",
            self.report_path,
        ]
        sk_check_path_regexp = r"(/[_\-/0-9a-zA-Z.]{1,}.[log|txt]):"
        sk_check_path_ret = utils.get_inquire_result(
            sk_check_path_cmd, sk_check_path_regexp
        )
        if sk_check_path_ret:
            self.is_sk = True

        original_files = list(set(plog_path_ret))
        dest_path = os.path.join(self.output_path, "collection", "plog")
        utils.check_path_valid(dest_path, isdir=True, output=True)
        utils.copy_src_to_dest(original_files, os.path.join(dest_path, "aicore_error"))

        find_path_cmd = ["grep", r"\[AIC_INFO\] dev_func:", "-inrE", self.report_path]
        find_path_regexp = r"(/[_\-/0-9a-zA-Z.]{1,}.[log|txt]):"
        plog_path_ret_1 = utils.get_inquire_result(find_path_cmd, find_path_regexp)
        if plog_path_ret_1:
            self.collect_level = 1
            original_file = sorted(plog_path_ret_1)[0]
            if original_file not in plog_path_ret:
                utils.copy_src_to_dest(
                    [
                        original_file,
                    ],
                    os.path.join(dest_path, "exception_dump"),
                )
        else:
            utils.print_debug_log(
                f"'[AIC_INFO] dev_func:' cannot be found in {self.report_path}. "
                "Only run L0 parse"
            )
        utils.print_debug_log(f"Debug Level is {self.collect_level}")

        find_path_cmd = [
            "grep",
            "exception info dump args data",
            "-inrE",
            self.report_path,
        ]
        find_path_regexp = r"(/[_\-/0-9a-zA-Z.]{1,}.[log|txt]):"
        plog_path_ret_2 = utils.get_inquire_result(find_path_cmd, find_path_regexp)

        if plog_path_ret_2:
            original_file = sorted(plog_path_ret_2)[0]
            if original_file not in plog_path_ret:
                utils.copy_src_to_dest(
                    [
                        original_file,
                    ],
                    os.path.join(dest_path, "exception_dump"),
                )

        return dest_path

    def collect_kernel_file(self, kernel_name):
        kernel_name = (
            kernel_name.replace("__kernel0", "")
            .replace("_mix_aic", "")
            .replace("_mix_aiv", "")
        )
        find_path_cmd = ["grep", kernel_name, "-inrE", self.report_path]
        regexp = r"([_\-/0-9a-zA-Z.]{1,}\.json|[_\-/0-9a-zA-Z.]{1,}\.o|[_\-/0-9a-zA-Z.]{1,}\.cce)"
        kernel_file_list = utils.get_inquire_result(find_path_cmd, regexp)
        if not kernel_file_list:
            utils.print_error_log(
                f"Kernel file cannot find. "
                f"Please move {kernel_name}`s related file to {self.report_path}."
            )
            return ""

        original_files = []
        for kernel_file in list(set(kernel_file_list)):
            if os.path.exists(kernel_file) and is_sub_path(
                kernel_file, self.report_path
            ):
                original_files.append(kernel_file)

        exist_op_kernel = any(
            kernel_file.endswith(".o") and not kernel_file.endswith("host.o")
            for kernel_file in original_files
        )
        exist_op_json = any(
            kernel_file.endswith(".json") for kernel_file in original_files
        )

        if self.is_sk:
            # SK场景下只生成host.o，没有device .o/.json，仅校验host.o是否存在
            exist_host_kernel = any(
                kernel_file.endswith("host.o") for kernel_file in original_files
            )
            if not exist_host_kernel:
                utils.print_warn_log(
                    f"The {kernel_name}`s host.o cannot be found in {self.report_path}."
                )
        elif not (exist_op_json and exist_op_kernel):
            utils.print_error_log(
                f"The {kernel_name}`s related file cannot be found in {self.report_path}."
            )

        original_files = list(set(original_files))
        dest_path = os.path.join(self.output_path, "collection", "compile")
        utils.check_path_valid(dest_path, isdir=True, output=True)
        utils.copy_src_to_dest(original_files, dest_path)
        return dest_path

    def collect_ge_graph(self):
        find_path_cmd = ["find", self.report_path, "-name", "ge_proto_*_Build.txt"]
        regexp = r"([_\-/0-9a-zA-Z.]{1,}_Build.txt)"
        graph_file_list = utils.get_inquire_result(find_path_cmd, regexp)
        if not graph_file_list:
            utils.print_warn_log(
                f"Graph file cannot be collected, the graph file cannot be found in {self.report_path}."
            )
        original_files = graph_file_list
        dest_path = os.path.join(self.output_path, "collection", "graph")
        utils.check_path_valid(dest_path, isdir=True, output=True)
        utils.copy_src_to_dest(original_files, dest_path)
        return dest_path

    def collect_data_dump(self, device_id, data_name, rename=""):
        dest_path = os.path.join(self.output_path, "collection", "dump")
        find_name = rename or data_name
        find_path_cmd = ["find", self.report_path, "-name", f"{find_name}"]
        regexp = r"[_\.\-/0-9a-zA-Z.]{1,}"
        original_files = utils.get_inquire_result(find_path_cmd, regexp)
        if not original_files:
            utils.print_error_log(
                f"Dump file cannot be collected, the dump file cannot be found in {self.report_path}."
            )
            return ""

        # 如果找到大于1个data, 则按文件自身所在的data-dump/<device_id>/目录取报错device的那一份。
        # 此处匹配完整目录段，避免device_id为0时误命中data-dump/01/
        if len(original_files) > 1:
            device_dump_dir = os.path.join("data-dump", str(device_id))
            matched_files = [
                file
                for file in original_files
                if os.path.dirname(file).endswith(device_dump_dir)
            ]
            if matched_files:
                utils.print_info_log(
                    f"Find dump file {os.path.basename(matched_files[0])}."
                )
                original_files = matched_files[:1]

        utils.check_path_valid(dest_path, isdir=True, output=True)
        utils.copy_src_to_dest(original_files, dest_path)
        if rename:
            # 超长场景下dump文件保持随机名，需一并收集mapping.csv供解析侧还原
            # 复用_resolve_dump_file_rename中已解析的路径，避免重复find
            mapping_csv_path = (
                self._mapping_csv_path or self._get_dump_mapping_csv_path(device_id)
            )
            if mapping_csv_path:
                utils.copy_src_to_dest([mapping_csv_path], dest_path)
        return dest_path

    def get_custom_dump_data_info(self):
        """从已采集的plog中识别全部用户自定义dump文件。

        runtime在原始dump之外额外落盘自定义dump文件，仅以日志关键字
        "dump custom exception to file"指示，文件名形如
        <name>.custom.<毫秒时间戳>。自定义dump非必选，无匹配时返回空列表。
        """
        plog_dir = os.path.join(self.output_path, "collection", "plog")
        dump_data_cmd = ["grep", "dump custom exception to file", "-inrE", plog_dir]
        dump_data_regexp = (
            r"(\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).+?"
            r"extra-info\/data-dump\/(\d+)\/([\w.\-]+\.custom\.\d+)"
        )
        dump_data_ret = utils.get_inquire_result(dump_data_cmd, dump_data_regexp)
        if not dump_data_ret:
            return []
        # get_inquire_result按正则捕获组数量返回字符串或元组列表；custom查询正则有
        # 3个捕获组，正常返回(time, device_id, data_name)元组。对其它形态（如find类
        # 单字符串结果）无法解析，视为无自定义dump，避免解包报错
        custom_result = [
            item for item in dump_data_ret if isinstance(item, tuple) and len(item) == 3
        ]
        if not custom_result:
            return []
        custom_result = sorted(custom_result, key=lambda x: x[0])
        return [(device_id, data_name) for _, device_id, data_name in custom_result]

    def collect_custom_dump(self, device_id):
        dest_path = os.path.join(self.output_path, "collection", "dump")
        custom_list = [
            item
            for item in self.get_custom_dump_data_info()
            if item[0] == str(device_id)
        ]
        if not custom_list:
            utils.print_debug_log("No custom dump file is found in the collected plog.")
            return dest_path
        # 自定义dump名比原始名多出".custom.<16位毫秒>"，更易超出NAME_MAX被runtime改为
        # 随机数字串。mapping.csv一个device只有一份，提到循环外只解析一次；rename只用
        # 局部变量，不改写Step 2按原始报错dump解析出的共享字段dump_file_rename
        dump_name_mapping = {}
        mapping_csv_path = ""
        if any(self._is_oversize_name(data_name) for _, data_name in custom_list):
            mapping_csv_path = (
                self._mapping_csv_path or self._get_dump_mapping_csv_path(device_id)
            )
            dump_name_mapping = utils.parse_name_mapping_csv(mapping_csv_path)
        need_mapping_copy = False
        for _, data_name in custom_list:
            rename = ""
            if self._is_oversize_name(data_name):
                rename = dump_name_mapping.get(data_name, "")
                if rename:
                    utils.print_info_log(
                        f"The dump file name exceeds {Constant.MAX_FILE_NAME_LEN}, "
                        f"use mapped name {rename} instead of {data_name}."
                    )
                elif not mapping_csv_path:
                    utils.print_warn_log(
                        f"The dump file name {data_name} exceeds {Constant.MAX_FILE_NAME_LEN}, "
                        f"but {Constant.MAPPING_CSV_FILE} cannot be found in {self.report_path}."
                    )
                else:
                    utils.print_warn_log(
                        f"The dump file name {data_name} exceeds {Constant.MAX_FILE_NAME_LEN}, "
                        f"but it is not recorded in {mapping_csv_path}."
                    )
            find_path_cmd = ["find", self.report_path, "-name", rename or data_name]
            regexp = r"[_\.\-/0-9a-zA-Z.]{1,}"
            original_files = list(set(utils.get_inquire_result(find_path_cmd, regexp)))
            if not original_files:
                utils.print_warn_log(
                    f"Custom dump file {data_name} cannot be found in "
                    f"{self.report_path}, skip it."
                )
                continue
            # 同名文件可能落在多个device的data-dump目录，按报错device取对应的一份
            if len(original_files) > 1:
                device_dump_dir = os.path.join("data-dump", str(device_id))
                matched_files = [
                    file
                    for file in original_files
                    if os.path.dirname(file).endswith(device_dump_dir)
                ]
                if matched_files:
                    original_files = matched_files[:1]
                else:
                    utils.print_warn_log(
                        f"Custom dump file {data_name} of device {device_id} "
                        f"cannot be found in {self.report_path}, skip it."
                    )
                    continue
            utils.check_path_valid(dest_path, isdir=True, output=True)
            utils.copy_src_to_dest(original_files, dest_path)
            if rename:
                need_mapping_copy = True
            utils.print_info_log(f"Collect custom dump file {data_name}.")
        if need_mapping_copy and mapping_csv_path:
            # 超长自定义dump保持随机名，mapping.csv只拷一份供解析侧还原；
            # 原始报错dump超长场景已收集过则不再重复拷贝
            mapping_dest = os.path.join(dest_path, Constant.MAPPING_CSV_FILE)
            if not os.path.exists(mapping_dest):
                utils.copy_src_to_dest([mapping_csv_path], dest_path)
        return dest_path

    def check_dump_data_is_valid(self, err_time, data_name, rename=""):
        find_dump_data_cmd = ["find", self.report_path, "-name", rename or data_name]
        regexp = r".*?\/data-dump\/\d+\/([\w.\-]+)"
        dump_data_file_list = utils.get_inquire_result(find_dump_data_cmd, regexp)
        home = os.environ.get("HOME")
        if not dump_data_file_list:
            utils.print_error_log(
                f"Cannot find dump file {data_name} when analyzing the AI Core error"
                f" generated at {err_time}. Possible causes:\n"
                f"(1) The dump file is missing in the"
                f" {self.report_path} directory. Add it to the directory.\n"
                f"(2) The analyzed log is not the one for the AI core error."
                f" According to the time window of the training task,"
                f" retain the log file within the time window"
                f"({home}/ascend/log/debug/plog/plog-pid_FileCreationTimestamp.log file),"
                f" and delete the one beyond the time window"
                f"({home}/ascend/log/debug/plog/plog-pid_FileCreationTimestamp.log)"
            )
            raise utils.AicErrException(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR)

    def check_host_and_device_kernel_name(self, data_name, rename=""):
        if self.is_sk:
            # SK场景下没有device .o，跳过host/device一致性检查
            return True
        find_name = rename or data_name
        kernel_cmd = ["find", self.report_path, "-name", find_name]
        _, kernel_info = utils.execute_command(kernel_cmd)
        kernel_path = kernel_info.split(find_name)[0]
        res = os.listdir(kernel_path)
        host_kernel_name = ""
        device_kernel_name = ""
        for file in res:
            if file.endswith(".o") and not file.endswith("host.o"):
                device_kernel_name = file
            if file.endswith(".o") and file.endswith("host.o"):
                host_kernel_name = file
        if not host_kernel_name or not device_kernel_name:
            utils.print_warn_log("Cannot find host kernel or device kernel.")
            return True
        if device_kernel_name[:-2] not in host_kernel_name[:-2]:
            return False
        return True

    def collect(self: any) -> bool:
        """
        collect info
        """
        utils.print_info_log(
            "Check the validity of the input and output paths for file parsing."
        )
        self.check_argument_valid()
        utils.print_info_log("******************Collection******************")
        collect_path = os.path.join(self.output_path, "collection")
        utils.check_path_valid(collect_path, isdir=True, output=True)

        # collect plog
        utils.print_info_log(
            "Step 1. Check key information in the log and copy the log."
        )
        self.collect_plog_file()

        # get dump data
        utils.print_info_log(
            "Step 2. Obtain the name and path of the flushed data file from the log."
        )
        try:
            err_time, device_id, data_name = self.get_dump_data_info()
            rename = self._resolve_dump_file_rename(device_id, data_name)
            self.check_dump_data_is_valid(err_time, data_name, rename)
            check_result = self.check_host_and_device_kernel_name(data_name, rename)
            if not check_result:
                utils.print_error_log(
                    "The kernel load on the host is different from the device."
                )
                return False
        except utils.AicErrException:
            return False

        # collect dump
        utils.print_info_log("Step 3. Obtain the operator name from the log.")
        self.collect_data_dump(device_id, data_name, rename)

        # collect custom dump (optional，user_tag仅存在于自定义dump中)
        utils.print_info_log("Step 3.1. Collect the custom dump files from the log.")
        self.collect_custom_dump(device_id)

        # get kernel_name
        utils.print_info_log(
            "Step 4. Obtain the compilation file based on the operator name."
        )
        try:
            kernel_name, _ = self._get_node_and_kernel_name(data_name)
        except utils.AicErrException:
            kernel_name = None

        # collect compile
        utils.print_info_log("Step 5. Start to collect compile file.")
        if kernel_name is not None:
            self.collect_kernel_file(kernel_name)

        # collect_ge_proto_graph
        utils.print_info_log("Step 6. Collect Graph Engine files.")
        self.collect_ge_graph()
        return True
