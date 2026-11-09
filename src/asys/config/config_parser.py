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

import csv
import configparser
import os
from typing import NamedTuple

from params import ParamDict
from common import log_debug, log_warning, log_error
from common import FileOperate as f
from common import get_project_conf
from common.const import RetCode

__all__ = ["AsysConfigParser"]


class IniConfItem(NamedTuple):
    para_name: str
    conf_val_map: dict
    default_key: str


ASYS_INI_VALUE_MAP = {
    "graph": IniConfItem("graph", {"TRUE": "1", "FALSE": "0"}, "TRUE"),
    "ops": IniConfItem("ops", {"TRUE": "1", "FALSE": "0"}, "TRUE"),
    "dump_ge_graph": IniConfItem("DUMP_GE_GRAPH", {"1": "1", "2": "2", "3": "3"}, "2"),
    "dump_graph_level": IniConfItem(
        "DUMP_GRAPH_LEVEL", {"1": "1", "2": "2", "3": "3"}, "2"
    ),
    "log_level": IniConfItem(
        "ASCEND_GLOBAL_LOG_LEVEL",
        {"DEBUG": "0", "INFO": "1", "WARNING": "2", "ERROR": "3", "NULL": "4"},
        "INFO",
    ),
    "log_event_enable": IniConfItem(
        "ASCEND_GLOBAL_EVENT_ENABLE", {"FALSE": "0", "TRUE": "1"}, "TRUE"
    ),
    "log_print_to_stdout": IniConfItem(
        "ASCEND_SLOG_PRINT_TO_STDOUT", {"FALSE": "0", "TRUE": "1"}, "FALSE"
    ),
}


class AsysConfigParser:
    def __init__(self):
        self.dep_file_path = os.path.join(get_project_conf(), "dependent_package.csv")
        self.ini_file_path = os.path.join(get_project_conf(), "asys.ini")

    # Sentinel distinguishing "the read raised and was logged" (READ_FAILED)
    # from "the read succeeded but returned nothing usable" (empty csv/txt).
    READ_FAILED = object()

    def __read_dep_file(self, file_path):
        """Read dependent_package.csv; a broken file must not kill every asys
        subcommand, because parse() here is a mandatory step of main()."""
        try:
            return f.read_file(file_path)
        except (
            OSError,
            UnicodeDecodeError,
            csv.Error,
            configparser.Error,
            IndexError,
        ) as e:
            log_error(f"Read the dependencies file: {file_path} failed, {e}.")
            return self.READ_FAILED

    def __parse_deps(self):
        dep_info = self.__read_dep_file(self.dep_file_path)
        if dep_info is self.READ_FAILED:
            return RetCode.READ_FILE_FAILED
        if not dep_info:
            log_error(f"Read the dependencies file: {self.dep_file_path} failed.")
            return RetCode.READ_FILE_FAILED

        ParamDict().set_deps(dep_info)
        return RetCode.SUCCESS

    def __read_ini_file(self, file_path):
        """Read asys.ini; same tolerance rule as __read_dep_file.

        Note: ConfigParser.read() swallows a missing or unreadable file and
        returns an empty parser, so the OSError branches here mainly cover
        the other file types read by f.read_file; a missing ini is detected
        by the existence check below instead.
        """
        try:
            return f.read_file(file_path)
        except (
            OSError,
            UnicodeDecodeError,
            csv.Error,
            configparser.Error,
            IndexError,
        ) as e:
            log_error(f"Read the config file: {file_path} failed, {e}.")
            return self.READ_FAILED

    def __parse_ini(self):
        # A missing/unreadable ini must not pass silently through
        # ConfigParser.read()'s internal exception swallowing.
        if not os.path.isfile(self.ini_file_path):
            log_error(f"Read the config file: {self.ini_file_path} failed.")
            return RetCode.READ_FILE_FAILED
        ini_parser = self.__read_ini_file(self.ini_file_path)
        if ini_parser is self.READ_FAILED:
            return RetCode.READ_FILE_FAILED
        if not ini_parser:
            log_error(f"Read the config file: {self.ini_file_path} failed.")
            return RetCode.READ_FILE_FAILED

        command = ParamDict().get_command()
        try:
            if command not in ini_parser.sections():
                log_debug(f"No ini conf items for command: {command}.")
                return RetCode.SUCCESS
            k_v_pairs = ini_parser.items(command)
        except (
            configparser.Error,
            OSError,
            UnicodeDecodeError,
            IndexError,
        ) as e:
            # items() interpolates values, so a stray '%' in the ini raises
            # InterpolationSyntaxError here rather than during read().
            log_error(f"Read the config file: {self.ini_file_path} failed, {e}.")
            return RetCode.READ_FILE_FAILED
        for conf_k, conf_v in k_v_pairs:
            info_item = ASYS_INI_VALUE_MAP.get(conf_k)
            if info_item is None:
                log_warning(f"ini conf item: {conf_k} is not available.")
                continue

            ini_name = info_item.para_name
            ini_value = info_item.conf_val_map.get(conf_v)
            if ini_value is None:
                ini_value = info_item.conf_val_map.get(info_item.default_key)
                log_warning(
                    f"ini conf item {ini_name} value error: {conf_v} is not in available range, "
                    f"use default value: {info_item.default_key}."
                )
            ParamDict().set_ini(ini_name, ini_value)

        return RetCode.SUCCESS

    def parse(self):
        if self.__parse_deps() != RetCode.SUCCESS:
            return False
        if self.__parse_ini() != RetCode.SUCCESS:
            return False
        return True
