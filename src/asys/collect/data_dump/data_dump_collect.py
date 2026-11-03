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

from params import ParamDict
from common import consts
from common import FileOperate as f
from common.file_operate import MOVE_MODE, COPY_MODE
from common import log_debug, log_info, log_warning
from drv import EnvVarName

__all__ = ["collect_data_dump"]


def _get_collect_path():
    collect_data_dump_path_list = []
    # asys launch
    if ParamDict().get_command() == consts.launch_cmd:
        collect_data_dump_path_list.append(
            os.path.join(
                ParamDict().asys_output_timestamp_dir, "npu_collect_intermediates"
            )
        )
        return collect_data_dump_path_list

    # asys collect
    task_dir = ParamDict().get_arg("task_dir")
    if task_dir:
        collect_data_dump_path_list.append(task_dir)
    env_var = EnvVarName()
    if env_var.npu_collect_path:
        log_debug(
            "Get env NPU_COLLECT_PATH successfully, add NPU_COLLECT_PATH to dump collect path."
        )
        collect_data_dump_path_list.append(env_var.npu_collect_path)

    if env_var.work_path:
        log_debug(
            "Get env ASCEND_WORK_PATH successfully, add ASCEND_WORK_PATH to dump collect path."
        )
        collect_data_dump_path_list.append(env_var.work_path)

    collect_data_dump_path_list.append(env_var.current_path)

    return collect_data_dump_path_list


def get_source_dir():
    for data_dump_path in _get_collect_path():
        data_dump_source_dir = os.path.join(data_dump_path, "extra-info", "data-dump")
        if data_dump_source_dir and f.check_dir(data_dump_source_dir):
            log_debug(
                "Data-dump source check success, path={}.".format(data_dump_source_dir)
            )
            return data_dump_source_dir
    return None


def collect_data_dump(output_root_path):
    data_dump_source_dir = get_source_dir()
    if data_dump_source_dir is None:
        # No fault dump data in the environment is an expected empty state, not a collect failure.
        log_info("No dump data to collect, this is normal when no fault occurred.")
        return

    data_dump_target_dir = os.path.join(output_root_path, "dfx", "data-dump")
    if ParamDict().get_command() == consts.launch_cmd:
        ret = f.collect_dir(data_dump_source_dir, data_dump_target_dir, MOVE_MODE)
    else:
        ret = f.collect_dir(data_dump_source_dir, data_dump_target_dir, COPY_MODE)
    if not ret:
        log_warning(
            "Data-dump collect failed, copy {} dir failed.".format(data_dump_source_dir)
        )
