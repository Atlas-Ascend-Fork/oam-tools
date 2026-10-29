#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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
"""
Function:
The file mainly involves main function of parsing input arguments.
Copyright Information:
Huawei Technologies Co., Ltd. All Rights Reserved © 2025
"""

import argparse
import sys
import time

from ms_interface import utils
from ms_interface.tiling_data_parser import TilingDataParser
from ms_interface.constant import Constant


def parse_tiling_data(plog):
    tiling_data = TilingDataParser(plog).parse()
    if not tiling_data:
        utils.print_warn_log("No valid tiling data was found; no binary file created.")
        return Constant.MS_AICERR_FIND_DATA_ERROR
    tiling_data_file = f"tilingdata_{int(time.time())}.bin"
    try:
        with open(tiling_data_file, "wb") as f:
            f.write(tiling_data)
    except OSError as err:
        utils.print_warn_log(f"Failed to write {tiling_data_file}: {err}")
        return Constant.MS_AICERR_OPEN_FILE_ERROR
    utils.print_info_log(f"Tiling data saved in {tiling_data_file}")
    return Constant.MS_AICERR_NONE_ERROR


def main():
    """
    main function
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--tiling_data",
        dest="tiling_data",
        default="",
        help=argparse.SUPPRESS,
        required=False,
    )
    args, _ = parser.parse_known_args()

    if args.tiling_data:
        utils.print_info_log("Start to get tiling data.")
        return parse_tiling_data(args.tiling_data)

    return Constant.MS_AICERR_NONE_ERROR


if __name__ == "__main__":
    sys.exit(main())
