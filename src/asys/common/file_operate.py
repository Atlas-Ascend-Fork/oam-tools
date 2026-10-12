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
import os
import shutil
import configparser

from common.log import log_error, log_debug
from common.const import CONFIG_TABLE_FILE

__all__ = ["FileOperate", "MOVE_MODE", "COPY_MODE"]

MOVE_MODE = "m"
COPY_MODE = "c"
ENCODE_UTF_8 = "utf-8"


class FileOperate:
    @staticmethod
    def check_file(file_path):
        if not file_path:
            return False
        return os.path.isfile(file_path)

    @staticmethod
    def check_dir(dir_path):
        if not dir_path:
            return False
        return os.path.isdir(dir_path)

    @staticmethod
    def check_exists(path):
        if not path:
            return False
        return os.path.exists(path)

    @staticmethod
    def check_empty(path):
        if not path:
            return True
        if os.path.exists(path) and os.path.isdir(path):
            return not os.listdir(path)
        return True

    @staticmethod
    def check_access(path, mode=os.F_OK):
        if not path:
            return False
        return os.access(path, mode)  # mode: F_OK, R_OK, W_OK, X_OK

    @staticmethod
    def remove_file(file_path):
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    @staticmethod
    def create_dir(dir_path, exist_ok=False):
        try:
            os.makedirs(dir_path, mode=0o750, exist_ok=exist_ok)
            return True
        except OSError as e:
            log_debug(f"Failed to create directory {dir_path}, error is {e}")
            return False

    @staticmethod
    def remove_dir(dir_path):
        if not dir_path or not os.access(dir_path, os.F_OK):
            log_debug("dir: {0} is not exist, do not need to remove.".format(dir_path))
            return False
        if not os.access(dir_path, os.W_OK):
            log_debug(
                "dir: {0} is not access to write, can not remove.".format(dir_path)
            )
            return False
        shutil.rmtree(dir_path)
        return True

    @staticmethod
    def walk_dir(dir_path):
        if not dir_path or not os.access(dir_path, os.R_OK):
            return False
        f = os.walk(dir_path)
        return f

    @staticmethod
    def list_dir(dir_path):
        if not os.access(dir_path, os.R_OK):
            return False
        f = os.listdir(dir_path)
        return f

    @staticmethod
    def write_file(file_path, info):
        if not file_path:
            return
        file_dir = os.path.split(file_path)[0]
        if (
            file_dir
            and not os.path.exists(file_dir)
            and not FileOperate.create_dir(file_dir)
        ):
            log_error(
                'Create path directory: "{}" failed in write file.'.format(file_dir)
            )
            return
        with open(file_path, mode="w", encoding=ENCODE_UTF_8) as f:
            f.write(info)

    @staticmethod
    def append_write_file(file_path, info):
        if not file_path:
            return
        file_dir = os.path.split(file_path)[0]
        if (
            file_dir
            and not os.path.exists(file_dir)
            and not FileOperate.create_dir(file_dir)
        ):
            log_error(
                'Create path directory: "{}" failed in write file.'.format(file_dir)
            )
            return
        with open(file_path, mode="a", encoding=ENCODE_UTF_8) as f:
            f.write(info)

    @staticmethod
    def read_file(file_path):
        if file_path.endswith(".ini"):
            cf = configparser.ConfigParser()
            cf.read(file_path, encoding=ENCODE_UTF_8)
            return cf
        elif file_path.endswith(".csv"):
            csv_buf = []
            with open(file_path, mode="r", encoding=ENCODE_UTF_8) as f:
                reader = csv.reader(f)
                for row in reader:
                    csv_buf.append(row)
            return csv_buf
        else:
            with open(file_path, mode="r", encoding=ENCODE_UTF_8) as f:
                file_buf = f.read()
            return file_buf

    @staticmethod
    def delete_dirs(dir_list):
        if not dir_list:
            return
        for inter_dir in dir_list:
            if inter_dir and os.path.exists(inter_dir):
                if not FileOperate.remove_dir(inter_dir):
                    log_error(
                        'Delete intermediate: "{}" failed in asys clean work.'.format(
                            inter_dir
                        )
                    )

    @staticmethod
    def copy_file_to_dir(source_file_path, target_dir_path):
        if (
            not os.path.exists(source_file_path)
            or not os.access(source_file_path, os.R_OK)
            or not os.path.isfile(source_file_path)
        ):
            return False
        if not os.path.exists(target_dir_path):
            os.makedirs(target_dir_path)
        shutil.copy(source_file_path, target_dir_path)
        return True

    @staticmethod
    def copy_dir(source_dir_path, target_dir_path):
        if (
            not os.path.exists(source_dir_path)
            or not os.access(source_dir_path, os.R_OK)
            or not os.path.isdir(source_dir_path)
        ):
            return False
        real_source = os.path.realpath(source_dir_path)
        real_target = os.path.realpath(target_dir_path)
        if real_target == real_source:
            log_error("The source and target directories cannot be the same.")
            return False
        if real_target.startswith(real_source + os.path.sep):
            log_error("The output directory cannot be in the data directory.")
            return False
        shutil.copytree(source_dir_path, target_dir_path)
        return True

    @staticmethod
    def move_file_to_dir(source_file_path, target_dir_path):
        if (
            not os.path.exists(source_file_path)
            or not os.access(source_file_path, os.R_OK)
            or not os.path.isfile(source_file_path)
        ):
            return False
        if not os.path.exists(target_dir_path):
            os.makedirs(target_dir_path)
        shutil.move(source_file_path, target_dir_path)
        return True

    @staticmethod
    def move_dir(source_dir_path, target_dir_path):
        if (
            not os.path.exists(source_dir_path)
            or not os.access(source_dir_path, os.R_OK)
            or not os.path.isdir(source_dir_path)
        ):
            return False
        if os.path.exists(target_dir_path):
            shutil.rmtree(target_dir_path)
        shutil.move(source_dir_path, target_dir_path)
        return True

    @staticmethod
    def collect_file_to_dir(source_file_path, target_dir_path, mode):
        if mode == MOVE_MODE:  # move mode
            return FileOperate.move_file_to_dir(source_file_path, target_dir_path)
        elif mode == COPY_MODE:  # copy mode
            return FileOperate.copy_file_to_dir(source_file_path, target_dir_path)
        else:
            log_error("Unknown mode in collect file.")
            return False

    @staticmethod
    def collect_dir(source_dir_path, target_dir_path, mode):
        if mode == MOVE_MODE:  # move mode
            return FileOperate.move_dir(source_dir_path, target_dir_path)
        elif mode == COPY_MODE:  # copy mode
            return FileOperate.copy_dir(source_dir_path, target_dir_path)
        else:
            log_error("Unknown mode in collect directory.")
            return False

    @staticmethod
    def check_valid_dir(dir_path):
        if not (
            os.path.exists(dir_path)
            and os.path.isdir(dir_path)
            and os.access(dir_path, os.R_OK)
        ):
            return False
        if len(os.listdir(dir_path)) == 0:
            return False
        return True

    def read_config(self):
        if not os.path.isfile(CONFIG_TABLE_FILE):
            log_error(
                f"Error: The file {CONFIG_TABLE_FILE} does not exist, please check env."
            )
            return {}
        try:
            return self._read_config()
        except PermissionError:
            log_error(f"Error: Permission denied for file {CONFIG_TABLE_FILE}.")
            return {}
        except (csv.Error, IndexError, ValueError) as exc:
            log_error(f"Error: {CONFIG_TABLE_FILE} format or content is error, {exc}")
            return {}

    @staticmethod
    def _read_config():
        """读取config配置清单并解析成字典"""
        config_table = {}
        with open(CONFIG_TABLE_FILE, newline="", encoding="utf-8") as f:
            data = csv.reader(f)
            header = next(data, None)
            if not header or len(header) < 4:
                raise csv.Error("configuration table header is missing or incomplete")
            _, cfg_get, cfg_set, cfg_restore = header[:4]
            for row_number, row in enumerate(data, start=2):
                if len(row) < 4:
                    raise csv.Error(
                        f"configuration table row {row_number} is incomplete"
                    )
                config_table[row[0]] = {
                    cfg_get: row[1].split(","),
                    cfg_set: row[2].split(","),
                    cfg_restore: row[3].split(","),
                }
        return config_table
