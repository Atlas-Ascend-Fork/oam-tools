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
from pathlib import Path

from common import log_debug, log_warning
from common.file_operate import FileOperate
from common import consts
from common import Singleton
from drv import LoadSoType

__all__ = ["ParamDict"]


class ParamDict(metaclass=Singleton):
    def __init__(self):
        self.__command = None
        self.__asys_output_timestamp_dir = None
        self.__args = dict()
        self.__deps = dict()
        self.__ini = dict()
        self.__env_type = None
        self.__task_pid = None

    @property
    def tools_path(self):
        return Path(os.path.dirname(__file__)).parent

    def get_command(self):
        return self.__command

    @property
    def asys_output_timestamp_dir(self) -> str:
        return self.__asys_output_timestamp_dir

    @asys_output_timestamp_dir.setter
    def asys_output_timestamp_dir(self, path):
        self.__asys_output_timestamp_dir = path

    def get_ini(self, key):
        return self.__ini.get(key, False)

    def set_ini(self, ini_name, ini_value):
        self.__ini[ini_name] = ini_value

    def get_arg(self, key, default=False):
        if key in self.__args.keys():
            return self.__args.get(key, default)
        return default

    def get_deps(self):
        return self.__deps

    def get_env_type(self):
        if self.__env_type is None:
            self.set_env_type()
        return self.__env_type

    def set_env_type(self, env_type=None):
        if env_type is None:
            self.__env_type = LoadSoType().get_env_type()
        else:
            self.__env_type = env_type

    def set_task_pid(self, pid):
        self.__task_pid = pid

    def get_task_pid(self):
        return self.__task_pid

    def _set_arg_d(self, args):
        if getattr(args, "d") is not None:
            self.__add_arg("device_id", args.d)
            log_debug('set arg: -d="{0}" success.'.format(self.__args.get("d")))

    def _set_arg_r(self, args):
        if getattr(args, "r") is not None:
            self.__add_arg("run_mode", args.r)
            log_debug('set arg: -r="{0}" success.'.format(self.__args.get("r")))

    def _set_arg_tar(self, args):
        arg_name = "tar"
        if getattr(args, arg_name) is not None:
            self.__add_arg(arg_name, args.tar.upper())
            log_debug(
                'set arg: --output="{0}" success.'.format(self.__args.get(arg_name))
            )

    def _set_arg_symbol_path(self, args):
        arg_name = "symbol_path"
        if getattr(args, arg_name) is not None:
            self.__add_arg(arg_name, args.symbol_path.split(","))
            log_debug(
                'set arg: --symbol_path="{0}" success.'.format(
                    self.__args.get(arg_name)
                )
            )

    def _set_arg_common(self, args, arg_name):
        if getattr(args, arg_name) is not None:
            self.__add_arg(arg_name, getattr(args, arg_name))
            log_debug(f'set arg: --{arg_name}="{self.__args.get(arg_name)}" success.')

    def set_args(self, args):
        self.__command = args.subparser_name

        if self.__command == consts.diagnose_cmd:
            self._set_arg_d(args)
            self._set_arg_r(args)
            self._set_arg_common(args, "timeout")

        if self.__command == consts.health_cmd:
            self._set_arg_d(args)
            return

        if self.__command == consts.info_cmd:
            self._set_arg_d(args)
            self._set_arg_r(args)
            return

        if self.__command == consts.analyze_cmd:
            self._set_arg_d(args)
            self._set_arg_r(args)
            self._set_arg_common(args, "file")
            self._set_arg_common(args, "path")
            self._set_arg_common(args, "core_file")
            self._set_arg_common(args, "exe_file")
            self._set_arg_common(args, "symbol")
            self._set_arg_symbol_path(args)
            self._set_arg_common(args, "reg")

        if self.__command == consts.config_cmd:
            self._set_arg_d(args)
            self._set_arg_common(args, "get")
            self._set_arg_common(args, "restore")
            self._set_arg_common(args, "stress_detect")
            return

        if self.__command == consts.collect_cmd:
            self._set_arg_common(args, "task_dir")
            self._set_arg_r(args)
            self._set_arg_common(args, "remote")
            self._set_arg_common(args, "all")
            self._set_arg_common(args, "quiet")
            self._set_arg_common(args, "timeout")
            self._set_arg_tar(args)

        if self.__command == consts.launch_cmd:
            self._set_arg_common(args, "task")
            self._set_arg_tar(args)

        if self.__command == consts.profiling_cmd:
            self._set_arg_d(args)
            self._set_arg_r(args)
            self._set_arg_p(args)
            self._set_arg_common(args, "aic_metrics")

        self._set_arg_common(args, "output")

    def set_deps(self, deps):
        # main() reaches this before any command runs, so an unusable row in
        # dependent_package.csv used to abort the whole invocation here.
        for item in deps:
            if not FileOperate.is_dep_row(item):
                # A missing comma silently removes a package from the report;
                # say so, the way config_parser does for unusable ini entries.
                log_warning(
                    f"Skip unusable dependency row in dependent_package.csv: {item}"
                )
                continue
            self.__add_dep(item[0], item[1])

    def __add_arg(self, key, value):
        if key in self.__args.keys():
            return False
        else:
            self.__args[key] = value
            return True

    def __add_dep(self, key, value):
        if key in self.__deps.keys():
            return False
        else:
            self.__deps[key] = value
            return True

    def _set_arg_p(self, args):
        if getattr(args, "p") is not None:
            self.__add_arg("period", args.p)
            log_debug('set arg: -p="{0}" success.'.format(self.__args.get("p")))
