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
This file mainly involves the common function.
Copyright Information:
Huawei Technologies Co., Ltd. All Rights Reserved © 2020
"""

import csv
import inspect
import os
import os.path
import shutil
import subprocess
import sys
import tempfile
import time
import re
import stat
import importlib

from datetime import datetime
from functools import wraps

from ms_interface.constant import Constant

GLOBAL_RESULT = True


def singleton(cls):
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


@singleton
class ExceptionRootCause:
    def __init__(self):
        self.causes = []
        self.cache_error = True

    def add_cause(self, cause):
        self.causes.append(cause)

    def format_causes(self):
        causes_str = ""
        for idx, cause in enumerate(self.causes):
            causes_str += f"{idx + 1}. {cause}\n"
        return causes_str


def screen_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        tmp = ExceptionRootCause().cache_error
        ExceptionRootCause().cache_error = False
        try:
            return func(*args, **kwargs)
        finally:
            ExceptionRootCause().cache_error = tmp

    return wrapper


class AicErrException(Exception):
    """
    The class for Op Gen Exception
    """

    def __init__(self: any, error_info: int) -> None:
        super().__init__(error_info)
        self.error_info = error_info


def _print_log(level: str, msg: str) -> None:
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(time.time())))
    pid = os.getpid()
    print(current_time + " (" + str(pid) + ") - [" + level + "] " + msg)
    sys.stdout.flush()


def print_log_stdout_only(level: str, msg: str) -> None:
    """只往 stdout 打印日志，不写 debug_info.txt。

    供 debug_info.txt 不可写的场景使用（print_error_log 会尝试落盘该文件）。
    这是 _print_log 的公开入口，避免跨模块访问受保护成员。
    """
    _print_log(level, msg)


def _print_log_to_txt(level: str, msg: str) -> None:
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(time.time())))
    pid = os.getpid()
    print_info = current_time + " (" + str(pid) + ") - [" + level + "] " + msg + "\r\n"
    with open("debug_info.txt", "a", encoding="utf-8") as file:
        file.write(print_info)


def print_info_log(info_msg: str) -> None:
    """
    print info log
    @param info_msg: the info message
    @return: none
    """
    _print_log("INFO", info_msg)
    _print_log_to_txt("INFO", info_msg)


def print_warn_log(warn_msg: str) -> None:
    """
    print warn log
    @param warn_msg: the warn message
    @return: none
    """
    _print_log_to_txt("WARNING", warn_msg)


def print_debug_log(debug_msg: str) -> None:
    """
    print debug log
    @param debug_msg: the debug message
    @return: none
    """
    _print_log_to_txt("DEBUG", debug_msg)


def print_error_log(error_msg: str) -> None:
    """
    print error log
    @param error_msg: the error message
    @return: none
    """
    stack = inspect.stack()
    call_locations = [
        "ms_interface/collection.py",
        "ms_interface/aicore_error_parser.py",
    ]

    save_to_root_cause = any(
        call_location in frame_info.filename and ExceptionRootCause().cache_error
        for frame_info in stack
        for call_location in call_locations
    )

    if save_to_root_cause:
        ExceptionRootCause().add_cause(error_msg)
    else:
        _print_log("ERROR", error_msg)

    _print_log_to_txt("ERROR", error_msg)


def check_path_special_character(path: str) -> None:
    """
    Function Description: check path special character
    @param path: the path to check
    """
    if path == "":
        print_error_log("The path is empty. Please enter a valid path.")
        raise AicErrException(Constant.MS_AICERR_INVALID_PARAM_ERROR)
    if " " in path:
        print_error_log("The path can not contain space.")
        raise AicErrException(Constant.MS_AICERR_INVALID_PARAM_ERROR)
    grep_str = "[';*?`!#$%^&+=<>{}]|~\""
    if set(path) & set(grep_str):
        print_error_log(
            "The path is not allowed with special characters " + grep_str + "."
        )
        raise AicErrException(Constant.MS_AICERR_INVALID_PARAM_ERROR)


@screen_error
def check_path_valid(path: str, isdir: bool = False, output: bool = False) -> None:
    """
    Function Description: check path valid
    @param path: the path to check
    @param isdir: the path is dir or file
    @param output: the path is output
    """
    check_path_special_character(path)
    path = os.path.realpath(path)
    if output and isdir and not os.path.exists(path):
        try:
            os.makedirs(path, mode=Constant.DIRECTORY_MASK)
        except OSError as ex:
            print_error_log(
                f"Failed to create {path}. "
                f"Please check that the path is accessible or the disk space is enough. {str(ex)}"
            )
            raise AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR) from ex
        finally:
            pass
    if not os.path.exists(path):
        print_error_log(
            f"The path {path} does not exist. Please check that the path exists."
        )
        raise AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR)

    if not os.access(path, os.R_OK):
        print_error_log(
            f"The path {path} does not have permission to read. Please check that the path is readable."
        )
        raise AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR)

    if isdir and not os.access(path, os.W_OK):
        print_error_log(
            f"The path {path} does not have permission to write. Please check that the path is writeable."
        )
        raise AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR)

    if isdir:
        if not os.path.isdir(path):
            print_error_log(
                f"The path {path} is not a directory. Please check the path."
            )
            raise AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR)
    else:
        if not os.path.isfile(path):
            print_error_log(f"The path {path} is not a file. Please check the path.")
            raise AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR)


def execute_command(cmd: list, file_out: str = None) -> tuple:
    """
    execute command
    :param cmd: the command to execute
    :param file_out: the stdout file
    :return: status and data
    """
    try:
        with tempfile.SpooledTemporaryFile() as out_temp:
            file_no = out_temp.fileno()
            if file_out is None:
                process = subprocess.Popen(
                    cmd, shell=False, stdout=file_no, stderr=file_no
                )
            else:
                with os.fdopen(
                    os.open(file_out, Constant.WRITE_FLAGS, Constant.WRITE_MODES), "w"
                ) as output_file:
                    process = subprocess.Popen(
                        cmd, shell=False, stdout=output_file, stderr=file_no
                    )
                    os.chmod(file_out, stat.S_IRUSR)
            process.wait()
            status = process.returncode
            out_temp.seek(0)
            data = out_temp.read().decode("utf-8")
        return status, data
    except FileNotFoundError as error:
        print_error_log("Failed to execute cmd %s. %s" % (cmd, error))
        raise AicErrException(Constant.MS_AICERR_EXECUTE_COMMAND_ERROR) from error
    finally:
        pass


def run_cmd_output(command, cwd=None, env=None) -> bool:
    """run linux cmd

    command 须为参数列表（如 ["bash", "build.sh"]），不走 shell，避免命令注入。
    """
    if isinstance(command, str):
        # shell=False 下字符串会被当成单个可执行文件名，必然 FileNotFoundError
        # 并被吞成 False（编译流程静默失败），故显式报错点明契约。
        print_error_log(
            "Run command failed: command must be a list of args, got str: {0}".format(
                command
            )
        )
        return False
    if not env:
        env = os.environ
    try:
        ret = subprocess.run(
            command,
            shell=False,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            env=env,
            check=False,
        )
    except (OSError, ValueError) as error:
        # shell=False 下命令不存在/参数非法会抛异常，转为 False 保持原有返回语义。
        print_error_log("Run command: {0} failed, {1}".format(command, error))
        return False
    if ret.returncode == 0:
        return True
    else:
        ret_err = ret.stdout
        print_error_log(
            "Run command: {0} failed, ret_code={1}, ret_err={2}".format(
                command, ret.returncode, ret_err
            )
        )
        return False


def __copy_file(src: str, dest: str) -> None:
    """
    copy file from src to dest
    :param src: the src path
    :param dest: the dest path
    """
    if os.path.exists(dest):
        base, extension = os.path.splitext(dest)
        dir_name, file = os.path.split(base)
        counter = 1
        while os.path.exists(dest):
            dest = os.path.join(dir_name, f"{file}_{counter}{extension}")
            counter += 1
    shutil.copy2(src, dest)


def copy_src_to_dest(src_file_list: list, dest_path: str):
    """
    copy file form src_file_list to dest_path
    :param src_file_list: the source file list
    :param dest_path: the dest path
    """
    check_path_valid(dest_path, isdir=True, output=True)
    if not src_file_list:
        print_warn_log("Failed to copy file.")
        return
    for file in src_file_list:
        dest_file = os.path.join(dest_path, os.path.basename(file))
        if os.path.isdir(file):
            original_files = [os.path.join(file, name) for name in os.listdir(file)]
            copy_src_to_dest(original_files, dest_file)
        else:
            try:
                __copy_file(file, dest_file)
            except (OSError, IOError) as error:
                print_warn_log(f"Failed to copy {file} to {dest_file}. {error}.")


def _iter_csv_rows(csv_path: str):
    """
    yield the rows of a csv file one by one
    :param csv_path: the csv path
    """
    # 显式指定utf-8，避免受locale影响；算子名可能含非utf-8字节，需兜住解码失败
    with open(csv_path, "r", encoding="utf-8") as csv_file:
        yield from csv.reader(csv_file)


def parse_name_mapping_csv(csv_path: str) -> dict:
    """
    parse the mapping.csv generated when a file name exceeds NAME_MAX,
    each line of which is {renamed random digits},{original file name}
    :param csv_path: the mapping.csv path
    :return: {original file name: renamed random digits}, empty when the csv is absent
    """
    mapping = {}
    if not csv_path or not os.path.isfile(csv_path):
        return mapping
    try:
        for row in _iter_csv_rows(csv_path):
            if len(row) == 2:
                mapping[row[1].strip()] = row[0].strip()
    except (OSError, IOError, csv.Error, UnicodeDecodeError) as error:
        print_warn_log(f"Failed to read {csv_path}. {error}.")
    return mapping


def write_file(output_path: str, file_content: str, write_mode="w") -> None:
    """
    write text to output file
    :param output_path: the output path
    :param file_content: the file content
    """
    dest_dir = os.path.dirname(output_path)
    check_path_valid(dest_dir, isdir=True, output=True)
    try:
        with os.fdopen(
            os.open(output_path, Constant.WRITE_FLAGS, Constant.WRITE_MODES), write_mode
        ) as output_file:
            output_file.write(file_content)
        os.chmod(output_path, stat.S_IRUSR)
    except IOError as io_error:
        print_error_log("Failed to write file %s. %s" % (output_path, io_error))
        raise AicErrException(Constant.MS_AICERR_OPEN_FILE_ERROR) from io_error
    finally:
        pass


def get_str_value(value_str: str) -> int:
    """
    get value by string
    """
    if not value_str:
        return -1
    value_str = value_str.strip()
    try:
        if value_str.lower().startswith("0x"):
            return int(value_str, 16)
        else:
            return int(value_str)
    except ValueError as value_error:
        print_warn_log(f"Failed to get value from {value_str}. {value_error}")
        return -1


def get_hexstr_value(hexstr: str) -> int:
    """
    get hex by string
    """
    hexstr = hexstr.strip()
    if hexstr == "0":
        return 0
    try:
        return int(hexstr, 16)
    except ValueError as value_error:
        print_warn_log(f"Failed to get value from {hexstr}. {value_error}")
        return -1


def hexstr_to_list_bin(hexstr: str) -> list:
    """
    convert hex str to list
    """
    value = get_hexstr_value(hexstr)
    binstr = bin(value)
    binstr_size = len(binstr)
    ret = []
    for i, bin_value in enumerate(binstr):
        if bin_value == "1":
            ret.append(binstr_size - i - 1)
    return ret


def get_01_from_hexstr(hexstr: str, high_bit: int, low_bit: int) -> str:
    """
    get 0 or 1 by hex string
    """
    ret = hexstr_to_list_bin(hexstr)
    code = ""
    for i in range(high_bit, low_bit - 1, -1):
        code += "1" if i in ret else "0"
    return code


def strplogtime(str_time: str):
    temp_list = str_time.split(".")
    if len(temp_list) != 3:
        print_warn_log(
            "str_time[{}] does not match %Y-%m-%d-%H:%M:%S.%f1.%f2, please check".format(
                str_time
            )
        )
        return datetime.strptime(str_time, "%Y-%m-%d-%H:%M:%S")
    new_str = "{}.{}{}".format(temp_list[0], temp_list[1], temp_list[2])
    return datetime.strptime(new_str, "%Y-%m-%d-%H:%M:%S.%f")


def regexp_match_dict(regexp, data):
    pattern = re.compile(regexp)
    result_map = [m.groupdict() for m in pattern.finditer(data)]
    return result_map


def get_inquire_result(grep_cmd, regexp, match_dict=False):
    status, data = execute_command(grep_cmd)
    if status != 0:
        print_warn_log(f"Failed to execute command:{grep_cmd}.")
        return []
    ret = (
        regexp_match_dict(regexp, data)
        if match_dict
        else re.findall(regexp, data, re.M | re.S)
    )
    if len(ret) == 0:
        print_warn_log(f"Log info does not match:{regexp} in command result.")
        return []
    return ret


def load_ascend_handlers():
    file_path = os.path.realpath(__file__)
    dir_path = os.path.dirname(file_path)
    current_dir = os.path.join(dir_path)
    handlers = []

    for folder in os.listdir(current_dir):
        folder_path = os.path.join(current_dir, folder)
        if not os.path.isdir(folder_path) or not folder.startswith("ascend"):
            continue

        for file in os.listdir(folder_path):
            if not (file.startswith("ascend") and file.endswith("handler.py")):
                continue

            base_name = os.path.splitext(file)[0]
            module_name = f"ms_interface.{folder}.{base_name}"
            try:
                # 导入模块
                module = importlib.import_module(module_name)
                # 从文件名中提取类名
                class_parts = base_name.split("_")
                class_name = "".join([part.capitalize() for part in class_parts])
                # 获取类并实例化
                cls = getattr(module, class_name)
                instance = cls()
                handlers.append(instance)
            # pylint: disable=broad-exception-caught
            # 插件式加载边界：handler 模块顶层代码可能抛任意异常（SyntaxError、
            # OSError、第三方库自定义异常等）。单个坏 handler 只应被跳过，
            # 不能中断整个 handler 发现流程，故保持宽捕获。
            except Exception as e:
                print_error_log(f"Error loading {module_name}: {str(e)}")
    return handlers
