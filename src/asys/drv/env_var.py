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

from common import FileOperate as f
from common import log_warning

# (env_var, raw_path) pairs whose "not a directory" warning was already
# emitted in this process, so one collection run logs each unique dropped
# entry exactly once no matter how many times EnvVarName is constructed.
_WARNED_INVALID_ENV_PATHS = set()


class EnvVarName:
    def __init__(self):
        self.process_log_path = self._set_env_path("ASCEND_PROCESS_LOG_PATH")
        self.npu_collect_path = self._set_env_path("NPU_COLLECT_PATH")
        self.dump_graph_path = self._set_env_path("DUMP_GRAPH_PATH")
        self.work_path = self._set_env_path("ASCEND_WORK_PATH")
        self.cache_path = self._set_env_path("ASCEND_CACHE_PATH")
        self.opp_path = self._set_env_path("ASCEND_OPP_PATH")
        # ``custom_opp_path`` used to hold the raw, unsplit value, which is not
        # a directory once more than one package is configured.  Only the split
        # list is kept.
        self.custom_opp_paths = self._set_env_paths("ASCEND_CUSTOM_OPP_PATH")
        self.current_path = os.getcwd()
        self.home_path = os.path.expanduser("~")

    @staticmethod
    def _set_env_path(env_var):
        env_path = os.getenv(env_var)
        if env_path and f.check_dir(env_path):
            ret = os.path.abspath(env_path)
        else:
            ret = None
        return ret

    @staticmethod
    def _set_env_paths(env_var):
        """Return the absolute directories listed in a search-path variable.

        ``os.pathsep`` is the platform separator (``:`` on Linux, ``;`` on
        Windows), so an entry that carries a Windows drive letter is not split
        apart.  Entries that are not directories, or that cannot be read, are
        dropped, but not silently: each unique one is logged with its raw value
        so a typo or a permission problem can be found instead of quietly
        shrinking the search path.  Entries resolving to the same directory
        after ``os.path.abspath`` keep only their first occurrence, so one
        package yields exactly one entry no matter how it is spelled.
        """
        paths = []
        seen = set()
        for raw_path in os.getenv(env_var, "").split(os.pathsep):
            if not raw_path:
                continue
            if not f.check_dir(raw_path):
                reason = "not a directory."
            elif not f.check_access(raw_path, os.R_OK):
                reason = "not readable."
            else:
                abs_path = os.path.abspath(raw_path)
                if abs_path not in seen:
                    seen.add(abs_path)
                    paths.append(abs_path)
                continue
            warned_key = (env_var, raw_path)
            if warned_key not in _WARNED_INVALID_ENV_PATHS:
                _WARNED_INVALID_ENV_PATHS.add(warned_key)
                log_warning(f"Ignore {env_var} entry {raw_path}: {reason}")
        return paths
