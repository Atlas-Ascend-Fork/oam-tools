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
import tarfile
from common import FileOperate as f
from common import log_warning
from params import ParamDict


def compress_output_dir_tar():
    """
    Compress the output directory using tar.
    """

    output_dir = ParamDict().asys_output_timestamp_dir
    if not (output_dir and f.check_dir(output_dir)):
        return
    with tarfile.open(
        os.path.join(
            os.path.dirname(output_dir), os.path.basename(output_dir) + ".tar.gz"
        ),
        "w:gz",
    ) as tar:
        tar.add(output_dir, arcname=os.path.basename(output_dir))

    # remove output dir. The archive is already complete, so an undeletable
    # directory (read-only files, another process holding it) must not turn
    # the whole collection into a failure.
    try:
        shutil.rmtree(output_dir)
    except OSError as err:
        log_warning(f"Compressed {output_dir} but failed to remove it: {err}")
