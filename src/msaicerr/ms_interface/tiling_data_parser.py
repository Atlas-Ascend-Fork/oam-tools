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
"""Module providing a function printing tiling data."""

import os.path
import re
from ms_interface import utils


class TilingDataParser:
    def __init__(self, path):
        self.file_path = path

    @staticmethod
    def __get_args(path):
        key_word_list = []

        get_args_cmd = ["grep", "after execute:", "-inrE", path]
        get_args_regexp = (
            r"(args\(0 to .*?\) after execute:.*?)after execute:args print end"
        )
        get_args_ret = utils.get_inquire_result(get_args_cmd, get_args_regexp)
        if not get_args_ret:
            utils.print_warn_log("Failed to get all args after execute.")
            return [], -1

        # A directory input can match several logs.  Only the first "after
        # execute:" block is parsed here, so an explicit tiling index resolved
        # below may come from a different log than these args.  That asymmetry
        # predates this change; pass a single log file to avoid it.
        get_args_ret = get_args_ret[0]
        get_arg_regexp = r" after execute:(.*?)$"
        get_arg_ret = re.findall(get_arg_regexp, get_args_ret, re.M | re.S)
        if not get_arg_ret:
            utils.print_warn_log("Failed to get arg after execute.")
            return [], -1

        for args in get_arg_ret:
            split_tmp = args.split(",")
            for str2 in split_tmp:
                if str2.find("\n") != -1:
                    continue
                str2 = str2.replace(" ", "").replace(".", "")
                if not str2:
                    continue
                key_word_list.append(str2)
        get_io_ptr_cmd = ["grep", "exception info dump args data", "-inrE", path]
        get_io_ptr_regexp = r"exception info dump args data, addr:(.*?);"
        get_io_ptr_ret = utils.get_inquire_result(get_io_ptr_cmd, get_io_ptr_regexp)
        if not get_io_ptr_ret:
            get_io_ptr_ret = []

        get_io_cmd = ["grep", r"\[Dump\]\[Exception\]", "-inrE", path]
        get_io_regexp = (
            r"begin to load tiling data, index:\d+"
            r"|begin to load [^\n]*? pointer tensor.*?end to load [^\n]*? pointer tensor"
        )
        get_io_ret = utils.get_inquire_result(get_io_cmd, get_io_regexp)
        explicit_tiling_index = -1
        pointer_tensors = []
        for ret in get_io_ret or []:
            tiling_index = re.fullmatch(r"begin to load tiling data, index:(\d+)", ret)
            if tiling_index and explicit_tiling_index == -1:
                explicit_tiling_index = int(tiling_index.group(1))
            elif not tiling_index:
                pointer_tensors.append(ret)

        if pointer_tensors:
            utils.print_info_log("The operator has sub_pointer tensor.")
            for ret in pointer_tensors:
                get_key_regexp = r"begin to load .*? pointer tensor.*?addr:(.*?)$"
                get_key_ret = re.findall(get_key_regexp, ret, re.M | re.S)

                get_value_regexp = r"exception info dump args data, addr:(.*?);"
                get_value_ret = re.findall(get_value_regexp, ret, re.M | re.S)
                for value in get_value_ret:
                    if value in get_io_ptr_ret:
                        i = get_io_ptr_ret.index(value)
                        get_io_ptr_ret[i] = get_key_ret[0]
            get_io_ptr_ret = list(set(get_io_ptr_ret))
        guess_tiling_index = explicit_tiling_index
        if explicit_tiling_index == -1:
            for io_ptr in get_io_ptr_ret:
                if io_ptr in key_word_list:
                    i = len(key_word_list) - 1 - key_word_list[::-1].index(io_ptr)
                    if i + 1 > guess_tiling_index:
                        guess_tiling_index = i + 1
        if guess_tiling_index >= len(key_word_list):
            utils.print_warn_log(
                "Failed to get tiling_ptr after execute, maybe static shape case."
            )
            return key_word_list, -1

        para_base_cmd = ["grep", "para base", "-inrE", path]
        para_base_regexp = r"para base:\s+(.*?)\."
        param_base_ret = utils.get_inquire_result(para_base_cmd, para_base_regexp)
        if not param_base_ret or not param_base_ret[0].startswith("0x"):
            utils.print_warn_log("Failed to get para_base after execute.")
            return key_word_list, -1
        _end_offset = len("0x")
        for c in param_base_ret[0][_end_offset:]:
            if c not in "0123456789abcdefABCDEF":
                break
            _end_offset = _end_offset + 1
        para_base = utils.get_hexstr_value(param_base_ret[0][:_end_offset])

        if guess_tiling_index == -1:
            utils.print_info_log(
                "Unable to get L0 dump log, start to guess tilingptr index."
            )
            for io_ptr in key_word_list:
                guess_tiling_ptr = utils.get_hexstr_value(io_ptr)
                offset = (guess_tiling_ptr - para_base) // 8
                if 0 < offset < len(key_word_list):
                    utils.print_info_log(f"Find tiling_data index: {offset}")
                    guess_tiling_index = key_word_list.index(io_ptr)
                    break

        # Both explicit and inferred indices refer to the complete args list.
        tiling_ptr_idx = guess_tiling_index
        idx_is_valid = 0 <= tiling_ptr_idx < len(key_word_list)
        tiling_ptr = (
            utils.get_hexstr_value(key_word_list[tiling_ptr_idx])
            if idx_is_valid
            else -1
        )
        offset = (tiling_ptr - para_base) // 8 if idx_is_valid else -1
        utils.print_debug_log(
            f"get args: {key_word_list}, "
            f"tiling_ptr:{hex(tiling_ptr)}, para_base: {hex(para_base)}, offset: {offset}"
        )
        if not 0 <= offset < len(key_word_list):
            utils.print_warn_log(
                f"Tiling data offset {offset} is outside the captured args "
                f"(count={len(key_word_list)}, tiling_ptr={hex(tiling_ptr)}, "
                f"para_base={hex(para_base)})."
            )
            return key_word_list, -1
        return key_word_list, offset

    @staticmethod
    def __reverse_str(sss):
        ss = ""
        for i in range(7, -1, -1):
            ss = ss + sss[2 * i : 2 * i + 2]
        return ss

    def __gen_tiling_data(self, key_word_list, offset):
        ss_concate = ""
        for key in key_word_list[offset:]:
            # remove "0x"
            str_tmp = key.replace("0x", "")
            str_tmp = str_tmp.zfill(16)
            str_tmp = self.__reverse_str(str_tmp)
            ss_concate = ss_concate + str_tmp
        tiling_datas = bytes.fromhex(ss_concate)
        return tiling_datas

    def _get_files(self):
        file_list = []
        for filepath, _, filenames in os.walk(self.file_path):
            for filename in filenames:
                file_list.append(os.path.join(filepath, filename))
        return file_list

    def parse(self):
        """Return the tiling payload as ``bytes``, or ``b""`` when it is absent.

        The failure value used to be ``""``.  Both are falsy and callers only
        test truthiness (``aicore_error_parser`` guards the file write with
        ``if tiling_data``; ``parse_tiling`` turns a falsy result into an
        error code), so the change is source compatible.  ``b""`` is used
        because the payload is binary and is written straight to a file.
        """
        key_word_list, offset = self.__get_args(self.file_path)
        if offset == -1:
            return b""
        tiling_data = self.__gen_tiling_data(key_word_list, int(offset))
        utils.print_debug_log("Get tiling data success from the log!")
        return tiling_data
