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
    "MSNPUREPORT_TYPE_TIMEOUTS",
    "collect_msnpureport_type_info",
    "merge_dir",
]

CMD_PREFIX = "msnpureport report -t "
EXPORT_TMP_DIR = "export_type_tmp"

# Suffix-preserving merge must not exceed the filesystem single-name limit
# (getconf NAME_MAX / 255 on ext4/xfs); os.replace on a longer name fails
# with Errno 36 and strands the source copy in the doomed temp directory.
_CONFLICT_NAME_MAX = os.pathconf("/", "PC_NAME_MAX") if hasattr(os, "pathconf") else 255
# An extension longer than this bound cannot be trimmed without eating the
# suffix that identifies the copy, so it is swapped for ".conf" instead.
_CONFLICT_EXT_MAX = 64

# #399 超时规格：全量导出(-f) 60s；类型化导出 -t5 120s / -t6 100s / -t7 120s /
# -t8 240s / -t9 120s / -t10 100s / -t11 40s（单位秒），挂死时按既有失败
# 告警路径降级，collect 流程不永久阻塞。
MSNPUREPORT_TYPE_TIMEOUTS = {
    "-f": 60,
    5: 120,
    6: 100,
    7: 120,
    8: 240,
    9: 120,
    10: 100,
    11: 40,
}

# The command support matrix is table-driven; a driver-side support change
# only updates this one place.
MSNPUREPORT_TYPE_TABLE = {
    5: {
        "chips": [r"350", r"910B\d", r"910_93", r"950", r"960"],
        "dirs": ["system_info"],
    },
    6: {"chips": [r"350", r"950", r"960"], "dirs": ["ub_info"]},
    7: {"chips": [r"350", r"950", r"960"], "dirs": ["ao_info"]},
    8: {"chips": [r"350", r"950", r"960"], "dirs": ["ao_info"]},
    9: {"chips": [r"350", r"950", r"960"], "dirs": ["ao_info"]},
    10: {"chips": [r"350", r"950", r"960"], "dirs": ["ccu_info"]},
    11: {"chips": [r"350", r"950", r"960"], "dirs": ["network_info"]},
}


def merge_dir(source_dir_path, target_dir_path, source_tag=None):
    """Move a directory tree without deleting an existing target tree.

    When a same-named file with different content already exists at the
    target, the source copy is preserved next to it under a suffixed name
    instead of being dropped (the temporary export directory is deleted
    afterwards, so dropping it would lose the data).
    """
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
            if not merge_dir(source_item, target_item, source_tag):
                moved = False
            continue
        if os.path.exists(target_item):
            # The -f export and a typed export (e.g. -t 5) both write
            # system_info, so the same relative path is merged twice per
            # collect run. Identical content is an idempotent no-op;
            # genuinely different content is a conflict: keep both copies,
            # the source one under a suffixed name tagged with its origin.
            if _same_file_content(source_item, target_item):
                try:
                    os.remove(source_item)
                except OSError as err:
                    log_error("Remove %s failed: %s" % (source_item, err))
                    moved = False
                continue
            # Both copies are kept, so no data is lost: the diverging content
            # is a warning, not a collect failure.
            conflict_item = _conflict_target_path(target_item, source_tag)
            log_warning(
                "The merge target file already exists with different content: %s, "
                "keep the source copy as %s" % (target_item, conflict_item)
            )
            try:
                os.replace(source_item, conflict_item)
            except OSError as err:
                log_error(
                    "Move %s to %s failed: %s" % (source_item, conflict_item, err)
                )
                moved = False
                continue
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


def _conflict_target_path(target_item, source_tag):
    # <name>.log -> <name>__<tag>.log; the tag identifies which export the
    # copy came from so both sides of a conflict remain distinguishable.
    # Repeated conflicts under the same relative path must not clobber each
    # other: several typed exports (e.g. -t 7/-t 8/-t 9 all write ao_info)
    # may each produce a different version, so an already-taken suffixed
    # name gets a __2, __3, ... sequence appended.
    tag = source_tag or "conflict"
    item_base, item_ext = os.path.splitext(os.path.basename(target_item))
    item_dir = os.path.dirname(target_item)
    sequence = 1
    while True:
        suffix = tag if sequence == 1 else "%s__%d" % (tag, sequence)
        conflict_path = os.path.join(
            item_dir, _suffixed_name(item_base, suffix, item_ext)
        )
        # An over-long candidate cannot be probed with os.path.exists (it
        # silently returns False for Errno 36), so existence is checked
        # only after _suffixed_name guaranteed a legal name.
        if conflict_path != target_item and not os.path.exists(conflict_path):
            return conflict_path
        sequence += 1


def _suffixed_name(base, suffix, ext):
    """Build "<base>__<suffix><ext>" within the filesystem single-name limit.

    The conflict copy name must stay within NAME_MAX (255 bytes on common
    Linux filesystems): an over-long name would fail os.replace with
    Errno 36, stranding the source copy in the temporary export directory
    where the cleanup deletes it. The suffix is appended after truncating
    the base (never before), so the characters distinguishing one
    candidate of a conflict sequence from another always survive the cut;
    the base is truncated by characters, never splitting a multi-byte
    one. An extension that leaves no room for a distinguishable base (a
    near-NAME_MAX extension) is replaced by ".conf": trimming such an
    extension would eat into the identifying suffix.
    """
    if len(ext.encode("utf-8", "surrogateescape")) > _CONFLICT_EXT_MAX:
        ext = ".conf"
    budget = _CONFLICT_NAME_MAX - len(
        ("__%s%s" % (suffix, ext)).encode("utf-8", "surrogateescape")
    )
    while base and len(base.encode("utf-8", "surrogateescape")) > budget:
        base = base[:-1]
    return "%s__%s%s" % (base, suffix, ext)


def _same_file_content(source_item, target_item):
    try:
        if os.path.getsize(source_item) != os.path.getsize(target_item):
            return False
        with open(source_item, "rb") as src_f, open(target_item, "rb") as tgt_f:
            while True:
                src_chunk = src_f.read(64 * 1024)
                tgt_chunk = tgt_f.read(64 * 1024)
                if src_chunk != tgt_chunk:
                    return False
                if not src_chunk:
                    return True
    except OSError:
        return False


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
        if not merge_dir(source_dir_path, target_dir_path, "typed_export"):
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
        cmd_res = run_cmd_output(export_cmd, timeout=MSNPUREPORT_TYPE_TIMEOUTS[type_id])
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
