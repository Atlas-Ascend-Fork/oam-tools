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
import re
import sys

from common import log_error, log_warning


__all__ = ["get_project_conf", "get_ascend_home", "get_log_conf_path"]


def get_project_conf():
    candidate_paths = [
        os.path.join(os.path.dirname(sys.argv[0]), "conf"),
        # project_path when running from the installed layout ...
        os.path.join(
            os.path.abspath(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            "conf",
        ),
        # ... and src/asys/conf when running from the source tree.
        os.path.join(
            os.path.abspath(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            "asys/conf",
        ),
    ]
    for project_conf_path in candidate_paths:
        if os.path.exists(project_conf_path):
            return project_conf_path
    # All candidates missing: keep the historical return value (the last
    # candidate) so the callers' "read failed" path reports a concrete path.
    return candidate_paths[-1]


def get_ascend_home():
    # TOOLCHAIN_HOME -> ${install_path}/latest/toolkit
    toolchain_home = os.getenv("TOOLCHAIN_HOME")
    if toolchain_home:
        latest_path = toolchain_home.split(":")[0]
        return os.path.abspath(os.path.join(latest_path, "../.."))
    else:
        return os.path.abspath("/usr/local/Ascend")


def get_log_conf_path(name):
    log_path = None
    if name == "slog":
        log_conf_paths = [
            "/etc/slog.conf",
            "/var/log/npu/conf/slog.conf",
            "/var/log/npu/conf/slog/slog.conf",
        ]
        search_re = r"^[ \t]*logAgentFileDir[ \t]*=[ \t]*([^\r\n]+)"
        log_path = "/var/log/npu/slog/"
    elif name == "bbox":
        log_conf_paths = [
            "/var/bbox.conf",
            "/etc/bbox.conf",
            "/var/log/npu/conf/bbox.conf",
            "/var/log/npu/conf/bbox/bbox.conf",
        ]
        search_re = r"^[ \t]*MNTN_PATH[ \t]*=[ \t]*([^\r\n]+)"
        log_path = "/var/log/npu/hisi_logs/"
    else:
        log_error("The input parameter is incorrect.")
        return log_path

    for conf_path in log_conf_paths:
        if not os.path.exists(conf_path):
            continue
        try:
            with open(conf_path, "r", encoding="utf-8-sig", errors="replace") as conf_f:
                conf_info = conf_f.read()
        except (OSError, UnicodeDecodeError):
            log_warning(f"Failed to read log config file: {conf_path}.")
            continue

        log_path_f = re.search(search_re, conf_info, re.MULTILINE)
        if log_path_f is not None:
            value = log_path_f.groups()[0].strip()
            if value:
                log_path = value

    return log_path
