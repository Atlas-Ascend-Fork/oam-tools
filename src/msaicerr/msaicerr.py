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
"""
Function:
The file mainly involves main function of parsing input arguments.
"""

import sys
import os
import time
import argparse
import tarfile
import traceback
from ms_interface import utils
from ms_interface.collection import Collection
from ms_interface.constant import Constant
from ms_interface.aicore_error_parser import AicoreErrorParser
from ms_interface.dsmi_interface import DSMIInterface, get_soc_version
from ms_interface.dump_data_parser import DumpDataParser
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.utils import screen_error


def handle_exception(exc_type, exc_value, exc_traceback):
    utils.GLOBAL_RESULT = False
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    utils.print_error_log("Uncaught exception:")
    traceback.print_exception(exc_type, exc_value, exc_traceback)


sys.excepthook = handle_exception


def _is_safe_tar_member(member, path):
    """校验解压成员不会逃逸出目标目录（防 tar-slip），且不是链接/特殊文件。"""
    if member.issym() or member.islnk():
        return False
    if member.isdev() or member.isfifo():
        # 设备节点/FIFO 不是采集数据的正常内容，高权限下解压会真的创建出来。
        return False
    dest = os.path.realpath(os.path.join(path, member.name))
    base = os.path.realpath(path)
    return dest == base or dest.startswith(base + os.sep)


def safe_tar_members(tar, tar_file, path):
    """筛掉会逃逸出 path 的成员，返回可安全解压的成员列表。"""
    safe_members = []
    for member in tar.getmembers():
        if _is_safe_tar_member(member, path):
            safe_members.append(member)
        else:
            utils.print_warn_log(
                "Skip unsafe member %s in %s." % (member.name, tar_file)
            )
    return safe_members


def extract_tar(tar_file, path):
    tar = tarfile.open(tar_file, "r")
    try:
        tar.extractall(path, members=safe_tar_members(tar, tar_file, path))
    finally:
        tar.close()


def get_select_dir(path):
    subdir = os.listdir(path)
    if len(subdir) != 1:
        raise ValueError("[ERROR] found more than one subdir in collect tar")
    report_path = os.path.join(path, subdir[0])
    return report_path


def check_device_valid(device_id):
    if not verify_device_id(device_id):
        utils.print_error_log(f"Invalid device_id {device_id}")
        return False

    utils.print_info_log(f"Valid device_id {device_id}")
    return True


def is_sub_path(path, parent_path):
    path = os.path.realpath(path)
    parent_path = os.path.realpath(parent_path)
    try:
        return os.path.commonpath([path, parent_path]) == parent_path
    except ValueError:
        return False


def analyse_report_path(args):
    if not check_device_valid(args.device_id):
        return Constant.MS_AICERR_INVALID_PARAM_ERROR

    if not args.output_path:
        utils.print_info_log(
            "The current directory will be used to as the output directory of the analysis report."
        )
        args.output_path = os.getcwd()
    try:
        current_path = os.getcwd()
        input_path = os.path.abspath(args.report_path)
        if is_sub_path(current_path, input_path) or is_sub_path(
            args.output_path, input_path
        ):
            utils.print_error_log(
                "Do not run msaicerr in the directory specified by -p or its subdirectory."
                " Make sure -out specifies a different directory (including its subdirectory) from -p."
            )
            return Constant.MS_AICERR_INVALID_PATH_ERROR
        collect_time = time.localtime()
        cur_time_str = time.strftime("%Y%m%d%H%M%S", collect_time)
        utils.check_path_valid(
            os.path.realpath(args.output_path), isdir=True, output=True
        )
        output_path = os.path.join(
            os.path.realpath(args.output_path), "info_" + cur_time_str
        )
        utils.check_path_valid(output_path, isdir=True, output=True)
        # 解压路径存在就不需要再次解压了
        if not args.report_path and args.tar_file:
            utils.print_info_log("Start to unzip tar.gz package.")
            extract_path = "extract_" + cur_time_str
            extract_tar(args.tar_file, extract_path)
            args.report_path = get_select_dir(extract_path)

        # collect info
        collection = Collection(args.report_path, output_path)
        collect_succ = collection.collect()

        # parse ai core error
        parser = AicoreErrorParser(output_path, args.device_id, collect_succ)
        return parser.parse()

    except utils.AicErrException as error:
        utils.print_error_log(
            f"The aicore error analysis tool has an exception, and error code is {error.error_info}."
        )
        return Constant.MS_AICERR_INVALID_PATH_ERROR


# noinspection PyBroadException
def convert_dump_data(args, data_path):
    try:
        utils.check_path_valid(args.data)
        if not args.output_path:
            dump_file_path, _ = os.path.split(os.path.realpath(args.data))
            utils.check_path_valid(dump_file_path, isdir=True, output=True)
            utils.print_info_log(
                "The dump file directory will be used to as the output directory of the parsed results."
            )
        else:
            utils.check_path_valid(args.output_path, isdir=True, output=True)
    except (OSError, ValueError, utils.AicErrException):
        return Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR

    try:
        info = AicErrorInfo()
        DumpDataParser(data_path, info, args.dest_dtype, args.output_path).parse()
        utils.print_debug_log(info.dump_info)
        return Constant.MS_AICERR_NONE_ERROR
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        RuntimeError,
        utils.AicErrException,
    ):
        return Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR


def verify_device_id(device_id):
    total_device_count = DSMIInterface().get_device_count()
    utils.print_info_log(f"Total device count: {total_device_count}")
    if device_id < 0 or device_id >= total_device_count:
        return False
    return True


@screen_error
def test_env(device_id=0):
    if not check_device_valid(device_id):
        return Constant.MS_AICERR_INVALID_PARAM_ERROR
    try:
        soc_version = get_soc_version()
        utils.print_info_log(f"Get soc_version: {soc_version}")
        utils.print_info_log("Start to test env with golden op.")
        result = AicoreErrorParser.run_test_env(soc_version, device_id=device_id)
        if result:
            utils.print_info_log(
                "The built-in sample operator runs successfully, The environment is normal."
            )
            return Constant.MS_AICERR_NONE_ERROR
        else:
            utils.print_error_log(
                "The built-in sample operator running failed. See the detailed error logs above for "
                "specific failure cause (e.g. chip incompatibility, driver issue, missing dependencies)."
            )
            return Constant.MS_AICERR_HARDWARE_ERR
    # AttributeError：get_soc_version() 内 get_chip_info() 取芯片信息失败会返回
    # None，对其取 get_complete_platform() 即抛该异常，需按环境检查失败上报。
    # TypeError：run_test_env() 拼 PYTHONPATH 等环境变量时若取到 None 会抛该异常
    # （根因已在 aicore_error_parser 用 or '' 兜底，此处作为边界兜底一并纳入）。
    except (
        OSError,
        ValueError,
        RuntimeError,
        AttributeError,
        TypeError,
        utils.AicErrException,
    ) as e:
        utils.print_error_log(f"Exception occurred during environment test: {str(e)}")
        return Constant.MS_AICERR_HARDWARE_ERR


# dest 到选项串的映射，由 _register_argument 在注册参数时登记。
# 有了它，RequireOtherArgs 无需读取 argparse 的内部属性 _option_string_actions。
DEST_OPTIONS_MAP = {}


def _register_argument(parser, *option_strings, **kwargs):
    """包装 parser.add_argument，同时登记 option_strings 与 dest 的映射。"""
    if kwargs.get("action") == "store_true":
        kwargs.update(action=RecordArgument, nargs=0, const=True, default=False)
    elif "action" not in kwargs:
        kwargs["action"] = RecordArgument
    action = parser.add_argument(*option_strings, **kwargs)
    DEST_OPTIONS_MAP[action.dest] = list(option_strings)
    return action


class RecordArgument(argparse.Action):
    """Record destinations recognized by argparse, including aliases and abbreviations."""

    def __call__(self, parser, namespace, values, option_string=None):
        del parser, option_string
        provided = getattr(namespace, "_provided_dest", None)
        if provided is None:
            provided = set()
            namespace._provided_dest = provided
        provided.add(self.dest)
        setattr(namespace, self.dest, self.const if self.nargs == 0 else values)


class RequireOtherArgs(RecordArgument):
    def __init__(self, option_strings, dest, required_args=None, **kwargs):
        super().__init__(option_strings, dest, **kwargs)
        self.required_args = required_args or []

    @staticmethod
    def formatted_arg(dest, parser):
        """把 dest 还原为用户可见的选项串，如 "-p/--report_path"。"""
        del parser  # 保留参数以兼容既有调用；映射已在参数注册时建立。
        # 兜底 f'--{dest}'：若有人绕过 _register_argument 直接 add_argument，
        # 这里不至于抛 KeyError 让报错信息不可读。
        return "/".join(DEST_OPTIONS_MAP.get(dest, [f"--{dest}"]))

    def __call__(self, parser, namespace, values, option_string=None):
        super().__call__(parser, namespace, values, option_string)
        pending = getattr(namespace, "_dependent_actions", None)
        if pending is None:
            pending = []
            namespace._dependent_actions = pending
        pending.append((self, option_string))


def validate_dependencies(parser, namespace):
    """Validate after parsing so argument order does not affect dependencies."""
    provided = getattr(namespace, "_provided_dest", set())
    for action, option_string in getattr(namespace, "_dependent_actions", []):
        if provided.isdisjoint(action.required_args):
            options = [
                action.formatted_arg(dest, parser) for dest in action.required_args
            ]
            formatted_args = (
                ", ".join(options[:-1]) + f" or {options[-1]}"
                if len(options) > 1
                else options[0]
            )
            parser.error(f"{option_string} must be used with {formatted_args}")
    for name in ("_provided_dest", "_dependent_actions"):
        if hasattr(namespace, name):
            delattr(namespace, name)


def main() -> int:
    """
    main function
    """
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]))
    _register_argument(
        parser,
        "-p",
        "--report_path",
        dest="report_path",
        default="",
        help="Specify the directory where the AI Core error information is stored when analyzing the AI Core error.",
        required=False,
    )
    _register_argument(
        parser,
        "-d",
        "--data",
        dest="data",
        default="",
        help="Specify the dump file path when parsing the dump file.",
        required=False,
    )
    _register_argument(
        parser,
        "-e",
        "--env",
        dest="env",
        action="store_true",
        help="Check the environment when running the built-in sample operator.",
        required=False,
    )
    _register_argument(
        parser,
        "-out",
        "--output_path",
        dest="output_path",
        default="",
        help="Specify the output directory of the result. This argument is valid only for --report_path and --data.",
        required=False,
        action=RequireOtherArgs,
        required_args=["report_path", "data"],
    )
    _register_argument(
        parser,
        "-dev",
        "--device_id",
        dest="device_id",
        default=0,
        type=int,
        help="Specify the ID of the device for running the operator. Defaults to 0 if not specified. "
        "This argument is valid only for --report_path and --env.",
        required=False,
        action=RequireOtherArgs,
        required_args=["report_path", "env"],
    )
    _register_argument(
        parser,
        "-dtype",
        "--dest_dtype",
        dest="dest_dtype",
        default="",
        help="Specify the data type when parsing dump files. This argument is valid only for --data. ",
        required=False,
        action=RequireOtherArgs,
        required_args=["data"],
    )

    ascend_opp_path = os.environ.get("ASCEND_OPP_PATH")
    if not ascend_opp_path:
        utils.print_error_log(
            "Environment variable not set after the CANN software is installed."
        )
        return Constant.MS_AICERR_INVALID_PATH_ERROR

    if len(sys.argv) <= 1:
        utils.print_error_log("Please execute : python msaicerr.py -h")
        parser.print_usage()
        return Constant.MS_AICERR_INVALID_PARAM_ERROR

    args, unknown = parser.parse_known_args()
    validate_dependencies(parser, args)
    debug_log = "debug_info.txt"
    if not os.access(os.getcwd(), os.W_OK) or (
        os.path.exists(debug_log) and not os.access(debug_log, os.W_OK)
    ):
        # debug_info.txt 不可写，走只打 stdout 的公开入口；
        # print_error_log 会再往 debug_info.txt 落盘，此处不能用。
        utils.print_log_stdout_only(
            "ERROR",
            "The current directory or debug_info.txt is immutable, Please check.",
        )
        return Constant.MS_AICERR_INVALID_PATH_ERROR

    if args.data:
        return convert_dump_data(args, args.data)
    elif args.report_path:
        return analyse_report_path(args)
    elif args.env:
        return test_env(args.device_id)

    if unknown:
        utils.print_error_log(
            f"Invalid argument {unknown}, please run help to check the usage."
        )
        return Constant.MS_AICERR_INVALID_PARAM_ERROR
    return Constant.MS_AICERR_INVALID_PARAM_ERROR


if __name__ == "__main__":
    sys.exit(main())
