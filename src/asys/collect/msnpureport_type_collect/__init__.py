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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

import os
import re
import shlex

from common import FileOperate as f
from common import DeviceInfo
from common import run_cmd_output
from common import log_debug, log_error, log_info, log_warning
from params import ParamDict
from collect.msnpureport_type_collect.ub_parse import parse_ub_in_place

__all__ = [
    "MSNPUREPORT_TYPE_TABLE",
    "collect_msnpureport_type_info",
    "merge_dir",
]

CMD_PREFIX = "msnpureport report -t "
EXPORT_TMP_DIR = "export_type_tmp"

# The command support matrix is table-driven; a driver-side support change
# only updates this one place.
MSNPUREPORT_TYPE_TABLE = {
    5: {
        "chips": [r"350", r"910B\d", r"910_93", r"950", r"960"],
        "dirs": ["system_info"],
    },
    6: {"chips": [r"950", r"960"], "dirs": ["ub_info"]},
    7: {"chips": [r"950", r"960"], "dirs": ["ao_info"]},
    8: {"chips": [r"950", r"960"], "dirs": ["ao_info"]},
    9: {"chips": [r"950", r"960"], "dirs": ["ao_info"]},
    10: {"chips": [r"950", r"960"], "dirs": ["ccu_info"]},
    11: {"chips": [r"950", r"960"], "dirs": ["network_info"]},
}


def merge_dir(source_dir_path, target_dir_path):
    """Move a directory tree without deleting an existing target tree."""
    if not os.path.isdir(source_dir_path):
        return False
    if os.path.exists(target_dir_path) and not os.path.isdir(target_dir_path):
        log_error(
            "The merge target already exists and is not a directory: %s"
            % target_dir_path
        )
        return False

    try:
        os.makedirs(target_dir_path, exist_ok=True)
        source_items = os.listdir(source_dir_path)
    except OSError as err:
        log_error("Merge %s to %s failed: %s" % (source_dir_path, target_dir_path, err))
        return False

    moved = True
    for item in source_items:
        source_item = os.path.join(source_dir_path, item)
        target_item = os.path.join(target_dir_path, item)
        if os.path.isdir(source_item):
            if not merge_dir(source_item, target_item):
                moved = False
            continue
        if os.path.exists(target_item):
            log_warning("The merge target file already exists: %s" % target_item)
            moved = False
            continue
        try:
            os.replace(source_item, target_item)
        except OSError as err:
            log_error("Move %s to %s failed: %s" % (source_item, target_item, err))
            moved = False
    if moved:
        try:
            os.rmdir(source_dir_path)
        except OSError as err:
            log_error("Remove empty directory %s failed: %s" % (source_dir_path, err))
            moved = False
    return moved


def _get_chip_infos():
    device = DeviceInfo()
    device_count = device.get_device_count()
    return [device.get_chip_info(device_id) for device_id in range(device_count)]


def _supported_type_ids(chip_infos):
    supported = []
    for type_id, desc in MSNPUREPORT_TYPE_TABLE.items():
        if any(
            any(re.search(pattern, chip_info) for pattern in desc["chips"])
            for chip_info in chip_infos
        ):
            supported.append(type_id)
    return sorted(supported)


def _archive_type_output(type_dir_path, output_root_path, dirs):
    in_export_dir = f.list_dir(type_dir_path)
    if not in_export_dir:
        return False

    output_dir_path = os.path.join(type_dir_path, in_export_dir[0])
    if not f.check_valid_dir(output_dir_path):
        return False

    archive_result = True
    found_dir = False
    for dir_name in dirs:
        source_dir_path = os.path.join(output_dir_path, dir_name)
        if not f.check_valid_dir(source_dir_path):
            continue
        found_dir = True
        target_dir_path = os.path.join(output_root_path, "dfx", dir_name)
        if not merge_dir(source_dir_path, target_dir_path):
            archive_result = False
    if not found_dir:
        log_warning(
            "No expected msnpureport output directories in %s" % output_dir_path
        )
        return False
    return archive_result


def collect_msnpureport_type_info(output_root_path):
    """Collect typed msnpureport data and parse UB binary files in place."""
    if ParamDict().get_env_type() != "EP":
        return True

    chip_infos = _get_chip_infos()
    type_ids = _supported_type_ids(chip_infos)
    if not type_ids:
        log_info("No device supports msnpureport typed export, skip.")
        return True

    export_root_path = os.path.join(output_root_path, EXPORT_TMP_DIR)
    if not f.create_dir(export_root_path):
        log_error(
            "Create msnpureport typed export directory failed: %s" % export_root_path
        )
        return False

    failed_list = []
    failed_details = []
    for type_id in type_ids:
        type_dir_path = os.path.join(export_root_path, "type_%s" % type_id)
        if not f.create_dir(type_dir_path):
            failed_list.append(type_id)
            continue
        export_cmd = "cd {};{}{}".format(
            shlex.quote(type_dir_path), CMD_PREFIX, type_id
        )
        cmd_res = run_cmd_output(export_cmd)
        if not cmd_res[0] or not _archive_type_output(
            type_dir_path, output_root_path, MSNPUREPORT_TYPE_TABLE[type_id]["dirs"]
        ):
            failed_list.append(type_id)
            failed_details.append((type_id, cmd_res[1] if not cmd_res[0] else ""))
            continue

    if failed_list:
        failed_args = "/".join("-t %s" % type_id for type_id in sorted(failed_list))
        log_error(
            "msnpureport report %s execute failed, which may be caused by a low driver package version."
            % failed_args
        )
        for type_id, detail in failed_details:
            log_debug("msnpureport report -t %s stderr: %s" % (type_id, detail.strip()))

    parse_ub_in_place(os.path.join(output_root_path, "dfx", "ub_info"))
    f.delete_dirs([export_root_path])
    return len(failed_list) != len(type_ids)
