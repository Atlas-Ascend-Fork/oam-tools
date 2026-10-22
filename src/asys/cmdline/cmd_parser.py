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

import argparse
import sys
import textwrap
import enum

from params import ParamDict
from common.const import RetCode, consts
from cmdline.arg_checker import ArgChecker

KEY_NAME = "name"
KEY_TYPE = "type"
KEY_HELP = "help"
KEY_CHECKER = "checker"
KEY_REQUIRED = "required"
KEY_ARGS = "args"
KEY_CHOICES = "choices"
KEY_METAVAR = "metavar"
KEY_ACTION = "action"

OPTIONAL_Y = "\033[33m<Optional>\033[0m"  # yellow
POSITIONAL_R = "\033[31m<Positional>\033[0m"  # red


class Arg(enum.Enum):
    """The support arg."""

    TASK_DIR = {
        KEY_NAME: "task_dir",
        KEY_CHECKER: ArgChecker.DIR_EXIST,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies the directory for collecting operator build files, GE dump graphs, "
        "and TF Adapter dump graphs. If task_dir is not set, these files are not collected by default.",
    }
    TASK = {
        KEY_NAME: "task",
        KEY_CHECKER: ArgChecker.EXECUTABLE,
        KEY_REQUIRED: True,
        KEY_METAVAR: " ",
        KEY_HELP: f"{POSITIONAL_R} Specifies the execution command for the service. "
        "It collects maintenance and debugging information during command execution.",
    }
    OUTPUT = {
        KEY_NAME: "output",
        KEY_CHECKER: ArgChecker.DIR_CREATE,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies the path to save the command execution results, Default: current dir.",
    }
    TAR = {
        KEY_NAME: "tar",
        KEY_CHECKER: ArgChecker.TAR_CHECK,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies whether to compress the asys result directory into a tar.gz file."
        " The original directory is not retained after compression. No compression by default.",
    }
    COLLECT_RUN = {
        KEY_NAME: "r",
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_CHOICES: ["stacktrace"],
        KEY_HELP: f"{OPTIONAL_Y} Specifies the collect logs mode, this parameter must be used together with '--remote'"
        " and '--all'. It can be set to 'stacktrace' (send signal to the process specified by remote, "
        "and generating the stackcore file). "
        "If r is not set, collects existing maintenance and debugging information in the environment.",
    }
    REMOTE = {
        KEY_NAME: "remote",
        KEY_TYPE: int,
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies the ID of the process that receives signal, "
        "this parameter must be used together with '-r=stacktrace'.",
    }
    ALL = {
        KEY_NAME: "all",
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies the stackcore files for all tasks, this parameter must be used together with"
        " '-r=stacktrace'.",
    }
    QUIET = {
        KEY_NAME: "quiet",
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Disable the interaction function during stack information export, "
        "this parameter must be used together with '-r=stacktrace'.",
    }
    STACKTRACE_TIMEOUT = {
        KEY_NAME: "timeout",
        KEY_TYPE: int,
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies the stacktrace collect duration, in seconds, value range: [1, 60]. "
        "If this argument is not specified, the default 10s is used.",
    }

    DEVICE = {
        KEY_NAME: "d",
        KEY_TYPE: int,
        KEY_CHECKER: ArgChecker.DEVICE_ID,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies the ID of the device for command execution.",
    }

    ANALYZE_DEVICE = {
        KEY_NAME: "d",
        KEY_TYPE: int,
        KEY_CHECKER: ArgChecker.DEVICE_ID,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies the ID of the device for command execution. This argument "
        "is valid only for 'aicore_error'.",
    }

    DIS_RUN = {
        KEY_NAME: "r",
        KEY_CHECKER: None,
        KEY_REQUIRED: True,
        KEY_CHOICES: [
            "stress_detect",
            "hbm_detect",
            "cpu_detect",
            "component",
            "aicore_stl_detect",
        ],
        KEY_HELP: f"{POSITIONAL_R} Specifies the hardware detection mode. It can be set to 'stress_detect' (AI Core "
        "stress test), 'hbm_detect' (HBM detection),  'cpu_detect' (CPU detection), 'component' "
        "(Operator detection) or 'aicore_stl_detect' (AICore STL self-diagnose, support Ascend950 "
        "and Ascend960DT only).",
    }
    TIMEOUT = {
        KEY_NAME: "timeout",
        KEY_TYPE: int,
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies the detection duration, in seconds. "
        "In HBM detection mode, value range: [0, 604800]. In CPU detection mode, value range: [1, 604800]. "
        "If this argument is not specified, the default 600s is used.",
    }

    INFO_RUN = {
        KEY_NAME: "r",
        KEY_CHECKER: None,
        KEY_REQUIRED: True,
        KEY_CHOICES: ["hardware", "software", "status"],
        KEY_HELP: f"{POSITIONAL_R} Specifies the type of information to be collected."
        " It can be set to 'status' (device information), 'software' (software information of the host), "
        "or 'hardware' (hardware information of the host and device).",
    }

    ANALYZE_RUN = {
        KEY_NAME: "r",
        KEY_CHECKER: None,
        KEY_REQUIRED: True,
        KEY_CHOICES: [
            "trace",
            "coredump",
            "coretrace",
            "stackcore",
            "aicore_error",
            "ub",
        ],
        KEY_HELP: f"{POSITIONAL_R} Specifies the type of data to be analyzed. It can be set to 'trace' "
        "(trace binary file), 'coredump' (system core file), 'coretrace' (coretrace file), "
        "'stackcore' (stackcore file), 'aicore_error' (aicore error dump and log) or "
        "'ub' (UB binary files).",
    }
    FILE = {
        KEY_NAME: "file",
        KEY_CHECKER: ArgChecker.FILE_PATH_EXIST_R,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{POSITIONAL_R} Specifies the single file to be analyzed. This argument is valid only for 'trace', "
        "'coretrace' and 'stackcore'. Mutually exclusive with '--path'.",
    }
    PATH = {
        KEY_NAME: "path",
        KEY_CHECKER: ArgChecker.FILE_PATH_EXIST_R,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{POSITIONAL_R} Specifies the path to be analyzed. This argument is valid only for 'trace', "
        "'coretrace' and 'stackcore'. Mutually exclusive with '--file'.",
    }
    EXE_FILE = {
        KEY_NAME: "exe_file",
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{POSITIONAL_R} Specifies the executable file to be debugged. "
        "This argument is valid only for 'coredump'.",
    }
    CORE_FILE = {
        KEY_NAME: "core_file",
        KEY_CHECKER: ArgChecker.CORE_FILE,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{POSITIONAL_R} Specifies the core file to be debugged. This argument is valid only for 'coredump'.",
    }
    SYMBOL = {
        KEY_NAME: "symbol",
        KEY_TYPE: int,
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_CHOICES: [0, 1],
        KEY_HELP: f"{OPTIONAL_Y} Specifies whether to retain the stack frame information that fails to be analyzed "
        "in the result (represented by double questions marks '??'). "
        "This argument is valid only for 'coredump'. Defaults to 0, indicating not to retain.",
    }
    SYMBOL_PATH = {
        KEY_NAME: "symbol_path",
        KEY_CHECKER: ArgChecker.SYMBOL_PATH,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Specifies the path of executable files and dependent dynamic library files. "
        "Subpaths are not searched. This argument is valid only for 'stackcore'. "
        "Defaults to the dynamic library path in the stackcore file.",
    }
    REG = {
        KEY_NAME: "reg",
        KEY_TYPE: int,
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_CHOICES: [0, 1, 2],
        KEY_HELP: f"{OPTIONAL_Y} Specifies the mode of adding register data for analysis. "
        "0: not add; 1: add only for threads; 2: add for all stack frames. Defaults to 0.",
    }
    GET = {
        KEY_NAME: "get",
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Gets the configuration. Use either this argument or '--restore'.",
    }
    RESTORE = {
        KEY_NAME: "restore",
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_HELP: f"{OPTIONAL_Y} Restores the configuration. Use either this argument or '--get'.",
    }
    STRESS_DETECT = {
        KEY_NAME: "stress_detect",
        KEY_CHECKER: None,
        KEY_REQUIRED: True,
        KEY_METAVAR: " ",
        KEY_HELP: f"{POSITIONAL_R} Specifies the configuration options to be queried or restored, "
        "indicating the configurations related to the pressure test.",
    }
    PROFILING_RUN = {
        KEY_NAME: "r",
        KEY_CHECKER: None,
        KEY_REQUIRED: True,
        KEY_METAVAR: " ",
        KEY_HELP: f"{POSITIONAL_R} Specifies the type of profile information to be collected. "
        "It can be set to 'aicore' (aicore information), 'dvpp' (dvpp information), "
        "'memory' (hardware memory information), 'link' (interconnection information), "
        "'os' (system information), 'power' (low power information), "
        "or any combination of these values, separated by ','.",
    }
    PERIOD = {
        KEY_NAME: "p",
        KEY_TYPE: int,
        KEY_CHECKER: None,
        KEY_REQUIRED: True,
        KEY_METAVAR: " ",
        KEY_HELP: f"{POSITIONAL_R} Specifies the profile information collection period, in seconds. "
        "Value range: [1, 2592000].",
    }
    AIC_METRICS = {
        KEY_NAME: "aic_metrics",
        KEY_CHECKER: None,
        KEY_REQUIRED: False,
        KEY_METAVAR: " ",
        KEY_CHOICES: [
            "PipeUtilization",
            "ArithmeticUtilization",
            "Memory",
            "MemoryL0",
            "MemoryUB",
            "ResourceConflictRatio",
            "L2Cache",
            "MemoryAccess",
        ],
        KEY_HELP: f"{OPTIONAL_Y} Specifies the aicore metrics to be collected. "
        "It takes effect when the run mode includes aicore. It can be set to 'PipeUtilization' "
        "(time consumption and proportion of computing unit and handling unit), "
        "'ArithmeticUtilization' (time consumption and proportion of cube and vector instructions), "
        "'Memory' (Memory IO bandwidth), 'MemoryL0' (L0 IO bandwidth), 'MemoryUB' (UB IO bandwidth), "
        "'ResourceConflictRatio' (percentage of pipeline queue class instructions) or "
        "'L2Cache' (read/write cache hit count and re-allocation count after misses). "
        "'MemoryAccess' (Bandwidth and data volume of operators accessing memory on the aicore). "
        "If this argument is not specified, the default PipeUtilization is used.",
    }


class Command(enum.Enum):
    """The support command."""

    COLLECT = {
        KEY_NAME: "collect",
        KEY_ARGS: [
            Arg.TASK_DIR,
            Arg.OUTPUT,
            Arg.TAR,
            Arg.COLLECT_RUN,
            Arg.REMOTE,
            Arg.ALL,
            Arg.QUIET,
            Arg.STACKTRACE_TIMEOUT,
        ],
        KEY_HELP: "Collects existing maintenance and debugging information in the environment, "
        "or export stacktrace information in real time.",
    }
    LAUNCH = {
        KEY_NAME: "launch",
        KEY_ARGS: [Arg.TASK, Arg.OUTPUT, Arg.TAR],
        KEY_HELP: "Executes the script of task parameters, and collects the maintenance "
        "and debugging information during the script execution.",
    }
    DIAGNOSE = {
        KEY_NAME: "diagnose",
        KEY_ARGS: [Arg.DIS_RUN, Arg.DEVICE, Arg.TIMEOUT, Arg.OUTPUT],
        KEY_HELP: "Diagnoses the hardware status of the device. It has diagnostic capabilities for "
        "component, stress_detect, hbm_detect, cpu_detect and aicore_stl_detect. "
        "The detect diagnostic only supports Ascend series chips: 910B, 910_93, 950, 960. ",
    }
    HEALTH = {
        KEY_NAME: "health",
        KEY_ARGS: [Arg.DEVICE],
        KEY_HELP: "Diagnoses the health status of the device.",
    }
    INFO = {
        KEY_NAME: "info",
        KEY_ARGS: [Arg.INFO_RUN, Arg.DEVICE],
        KEY_HELP: "Collects the software and hardware information of the host and device.",
    }
    ANALYZE = {
        KEY_NAME: "analyze",
        KEY_ARGS: [
            Arg.ANALYZE_RUN,
            Arg.ANALYZE_DEVICE,
            Arg.FILE,
            Arg.PATH,
            Arg.EXE_FILE,
            Arg.CORE_FILE,
            Arg.SYMBOL,
            Arg.SYMBOL_PATH,
            Arg.REG,
            Arg.OUTPUT,
        ],
        KEY_HELP: "Analyzes the trace, coredump, coretrace, stackcore, aicore_error and ub info.",
    }
    CONFIG = {
        KEY_NAME: "config",
        KEY_ARGS: [Arg.GET, Arg.DEVICE, Arg.RESTORE, Arg.STRESS_DETECT],
        KEY_HELP: "Gets or restores configuration information.",
    }
    PROFILING = {
        KEY_NAME: "profiling",
        KEY_ARGS: [
            Arg.DEVICE,
            Arg.PROFILING_RUN,
            Arg.OUTPUT,
            Arg.PERIOD,
            Arg.AIC_METRICS,
        ],
        KEY_HELP: "Collects the profiling information of the device.",
    }


class CommandLineParser:
    """
    The definition of command line parser.
    """

    def __init__(self):
        description_msg = textwrap.dedent("""\
            command help:
                asys {command} [-h, --help]
                """)
        self.parser = argparse.ArgumentParser(
            prog="asys",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=description_msg,
        )
        subparsers = self.parser.add_subparsers(
            dest="subparser_name", help="asys supported commands"
        )
        self.__config_parser = None

        # Config the parser from Command and Args
        for cmd in Command:
            cmd_conf = cmd.value
            # analyze, diagnose only support EP
            if ParamDict().get_env_type() == "RC" and cmd_conf[KEY_NAME] not in [
                consts.collect_cmd,
                consts.launch_cmd,
            ]:
                continue
            parser = subparsers.add_parser(
                cmd_conf[KEY_NAME], help=cmd_conf[KEY_HELP], allow_abbrev=False
            )
            if cmd_conf[KEY_NAME] == consts.config_cmd:
                self.__config_parser = parser
                self.__set_config_cmd_parser(parser, cmd_conf)
                continue
            if cmd_conf[KEY_NAME] == consts.analyze_cmd:
                self.__set_analyze_cmd_parser(parser, cmd_conf)
                continue

            supported_args = cmd_conf[KEY_ARGS]
            for arg in supported_args:
                arg_conf = arg.value
                if arg_conf.get(KEY_NAME) in ["d", "r", "p"]:
                    arg_name = "-" + arg_conf[KEY_NAME]
                else:
                    arg_name = "--" + arg_conf[KEY_NAME]
                _metavar = " "
                if arg_conf.get(KEY_CHOICES):
                    _metavar = None
                if arg_conf[KEY_NAME] in ["all", "quiet"]:
                    parser.add_argument(
                        arg_name,
                        required=arg_conf[KEY_REQUIRED],
                        action="store_true",
                        help=arg_conf[KEY_HELP],
                    )
                else:
                    parser.add_argument(
                        arg_name,
                        type=arg_conf.get(KEY_TYPE, str),
                        required=arg_conf[KEY_REQUIRED],
                        choices=arg_conf.get(KEY_CHOICES),
                        help=arg_conf[KEY_HELP],
                        metavar=arg_conf.get(KEY_METAVAR),
                    )

    @staticmethod
    def __set_config_cmd_parser(parser, cmd_conf):
        # 不使用 add_mutually_exclusive_group：Python 3.14 的 argparse 会将互斥
        # 组成员合并渲染为 "[--get | --restore]"，与历史 3.12 风格 "[--get] [-d ]
        # [--restore]"（保留参数声明顺序）不一致。这里改为常规 add_argument，
        # 在 parse() 阶段手动校验互斥关系，并复用 argparse 错误信息格式。
        supported_args = cmd_conf[KEY_ARGS]
        for arg in supported_args:
            arg_conf = arg.value
            arg_name = "--" + arg_conf[KEY_NAME]
            if arg_conf.get(KEY_NAME) == "d":
                arg_name = "-" + arg_conf[KEY_NAME]
                parser.add_argument(
                    arg_name,
                    type=arg_conf.get(KEY_TYPE, str),
                    required=arg_conf[KEY_REQUIRED],
                    choices=arg_conf.get(KEY_CHOICES),
                    help=arg_conf[KEY_HELP],
                    metavar=arg_conf.get(KEY_METAVAR),
                )
                continue

            parser.add_argument(
                arg_name,
                required=arg_conf[KEY_REQUIRED],
                action="store_true",
                help=arg_conf[KEY_HELP],
            )

    @staticmethod
    def __set_analyze_cmd_parser(parser, cmd_conf):
        group = parser.add_mutually_exclusive_group(required=False)
        supported_args = cmd_conf[KEY_ARGS]
        for arg in supported_args:
            arg_conf = arg.value
            arg_name = "--" + arg_conf[KEY_NAME]
            if arg_conf.get(KEY_NAME) in ["d", "r"]:
                arg_name = "-" + arg_conf[KEY_NAME]

            if arg_conf.get(KEY_NAME) in ["file", "path"]:
                group.add_argument(
                    arg_name,
                    type=arg_conf.get(KEY_TYPE, str),
                    required=arg_conf[KEY_REQUIRED],
                    help=arg_conf[KEY_HELP],
                    metavar=arg_conf.get(KEY_METAVAR),
                )
            else:
                parser.add_argument(
                    arg_name,
                    type=arg_conf.get(KEY_TYPE, str),
                    required=arg_conf[KEY_REQUIRED],
                    choices=arg_conf.get(KEY_CHOICES),
                    help=arg_conf[KEY_HELP],
                    metavar=arg_conf.get(KEY_METAVAR),
                )

    def print_help(self):
        """Print the help information generated by parser"""
        self.parser.print_help()

    @classmethod
    def check_arg_with_checker(cls, arg_name, arg_val, checker):
        """
        Check arg with checker.

        Args:
            arg_val: The value of arg to check
            checker: The check function to use

        Returns:
            RetCode: return code (SUCCESS:0, FAILED:1)
        """
        if checker is None:
            return RetCode.SUCCESS
        return checker(arg_name, arg_val)

    @classmethod
    def match_command(cls, cmd):
        """
        Match input command to Enum cmd type.

        Args:
            cmd: Input command

        Returns:
            command: Enum cmd type
        """
        for command in Command:
            command_conf = command.value
            if command_conf[KEY_NAME] == cmd:
                return command
        return None

    @classmethod
    def check_args(cls, args):
        """
        Check args according to command type.

        Args:
            args: The namespace returned by parse_args

        Returns:
            RetCode: return code (SUCCESS:0, FAILED:1)
        """
        input_cmd = args.subparser_name
        command = CommandLineParser.match_command(input_cmd)
        if not command:
            return RetCode.FAILED
        supported_args = command.value[KEY_ARGS]
        for support_arg in supported_args:
            arg_info = support_arg.value
            arg_val = getattr(args, arg_info[KEY_NAME])
            if arg_val is None:
                continue  # this arg is optional and not set, check next arg
            checker = arg_info[KEY_CHECKER]
            ret = CommandLineParser.check_arg_with_checker(
                arg_info[KEY_NAME], arg_val, checker
            )
            if ret != RetCode.SUCCESS:
                return RetCode.FAILED
        return RetCode.SUCCESS

    def parse(self):
        """
        Parse the command and args from cmd line.

        Returns:
            RetCode: return code (SUCCESS:0, FAILED:1)
        """
        # config 子命令的 --get / --restore 互斥校验：原本通过 argparse 的
        # mutually_exclusive_group 实现，但 3.14 改变了 usage 渲染顺序，故改为
        # 手动校验。在 parse_args 之前预扫描 argv，确保互斥错误优先于 required
        # 缺失错误抛出，与历史 mutex group 行为一致；错误信息复用
        # subparser.error()，与原 argparse 输出格式完全相同。
        self.__check_config_mutex_in_argv()
        args = self.parser.parse_args()
        if args.subparser_name is None:  # -h, --help, and only asys
            return RetCode.SUCCESS
        if CommandLineParser.check_args(args) == RetCode.FAILED:
            return RetCode.FAILED
        ParamDict().set_args(args)
        return RetCode.SUCCESS

    def __check_config_mutex_in_argv(self):
        if self.__config_parser is None:
            return
        argv = sys.argv[1:]
        if not argv or argv[0] != consts.config_cmd:
            return
        sub_argv = argv[1:]
        has_get = any(tok == "--get" or tok.startswith("--get=") for tok in sub_argv)
        has_restore = any(
            tok == "--restore" or tok.startswith("--restore=") for tok in sub_argv
        )
        if has_get and has_restore:
            self.__config_parser.error(
                "argument --restore: not allowed with argument --get"
            )
