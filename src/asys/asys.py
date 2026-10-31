#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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
import shutil
import signal
import sys

from common import consts, log_info, log_error, close_log
from common import RetCode
from common.task_common import create_out_timestamp_dir
from common import compress_output_dir_tar
from params import ParamDict
from cmdline import CommandLineParser
from config import AsysConfigParser
from collect import AsysCollect
from launch import AsysLaunch
from info import AsysInfo
from diagnose import AsysDiagnose
from health import AsysHealth
from analyze import AsysAnalyze
from config_cmd import AsysConfig
from profiling import AsysProfiling

__all__ = ["main"]


def _check_args_duplicate():
    input_args = [arg.split("=")[0] for arg in sys.argv[1:] if "-" in arg.split("=")[0]]
    # remove args duplicate
    args_no_duplicate = set(input_args)
    if len(input_args) > len(args_no_duplicate):
        log_error(f"Only one of the {list(args_no_duplicate)} args can be specified.")
        return False
    return True


def clean_pycache():
    """clean __pycache__"""
    current_file = os.path.dirname(os.path.abspath(__file__))
    for root, dirs, _ in os.walk(current_file):
        if "__pycache__" in dirs and os.path.exists(os.path.join(root, "__pycache__")):
            shutil.rmtree(os.path.join(root, "__pycache__"), ignore_errors=True)


EXECUTE_CMD_FUNC = {
    consts.collect_cmd: AsysCollect,
    consts.launch_cmd: AsysLaunch,
    consts.info_cmd: AsysInfo,
    consts.diagnose_cmd: AsysDiagnose,
    consts.health_cmd: AsysHealth,
    consts.analyze_cmd: AsysAnalyze,
    consts.config_cmd: AsysConfig,
    consts.profiling_cmd: AsysProfiling,
}


def main():
    """entrance of Ascend system advisor"""
    # check args duplicate
    if not _check_args_duplicate():
        return False

    # error stack when ctrl c is ignored
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # 1. parse the command line and check args
    asys_parser = CommandLineParser()
    try:
        parse_ret = asys_parser.parse()
    except SystemExit as exc:
        return exc.code in (0, None)
    param_dict = ParamDict()
    command = param_dict.get_command()
    if command is None:
        if parse_ret == RetCode.SUCCESS:  # -h, --help, and only asys
            asys_parser.print_help()
            return True
        else:
            log_error("Arguments parse failed, asys exit.")
            return False

    # info/diagnose/health/config(get)/analyze(aicore_error) close info & warning level log
    if any(
        [
            command in [consts.info_cmd, consts.diagnose_cmd, consts.health_cmd],
            command == consts.config_cmd and param_dict.get_arg("get"),
            command == consts.analyze_cmd
            and param_dict.get_arg("run_mode") == "aicore_error",
        ]
    ):
        close_log()

    # 2. check the environment type
    env_ret = param_dict.get_env_type()
    if not env_ret:
        log_error("Failed to obtain the execution environment type.")
        return False
    if env_ret == "RC":
        if any(
            [
                command not in [consts.collect_cmd, consts.launch_cmd],
                command == consts.collect_cmd and param_dict.get_arg("run_mode"),
            ]
        ):
            log_error(
                "The RC supports the launch command and the collect command without the -r parameter."
            )
            return False

    # 2. read the config file and load configs
    conf_parser = AsysConfigParser()
    conf_res = conf_parser.parse()
    if not conf_res:
        log_error("Configs parse failed, asys exit.")
        return False

    log_info("asys start.")

    if create_out_timestamp_dir() != RetCode.SUCCESS:
        log_error("Create asys output directory failed.")
        return False

    # 3. execute the command
    obj = EXECUTE_CMD_FUNC.get(command)
    task_res = obj().run() if obj else False

    log_info(f"{command} task execute finish.")

    # 4. Compress the output dir using tar.
    if param_dict.get_arg("tar") in ["T", "TRUE"]:
        compress_output_dir_tar()

    log_info("asys finish.")
    return task_res


def _run_cli():
    result = main()
    clean_pycache()
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(_run_cli())
