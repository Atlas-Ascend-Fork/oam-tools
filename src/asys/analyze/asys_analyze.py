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
import shlex
import stat
import time
import sys
import struct

from analyze.coredump_analyze import CoreDump
from common import log_error, log_warning, log_info, log_debug
from common import FileOperate as f
from common.cmd_run import check_command, real_time_output
from common.task_common import get_target_cnt
from common.const import (
    DSMI_UB_PORT_NUM,
    DL_PORT_RX_VL_NUM,
    STATS_ITEM_NUM,
    UBQOS_MAX_SL_NUM,
)
from common.const import UB_ENTIRE_STATUS_MAP, UB_PORT_STATUS_MAP, BALANCE_ALGORITHM_MAP
from collect.coretrace import ParseCoreTrace
from collect.trace import ParseTrace
from collect.stackcore import ParseStackCore
from collect import AsysCollect
from params import ParamDict

ub_file_names = [
    "ubnl_dfx_statistic",
    "ubnl_dfx_ssu_schedule",
    "ubnl_dfx_config_item",
    "ubmem_daw",
    "ubtpl_acl_src",
    "sl_to_vl",
]


class AsysAnalyze:
    def __init__(self):
        self.file = self.get_param_arg("file")
        self.path = self.get_param_arg("path")
        self.exe_file = self.get_param_arg("exe_file")
        self.core_file = self.get_param_arg("core_file")
        self.symbol = self.get_param_arg("symbol")
        self.symbol_path = self.get_param_arg("symbol_path")
        self.output = ParamDict().asys_output_timestamp_dir
        self.run_mode = self.get_param_arg("run_mode")
        self.device_id = ParamDict().get_arg("device_id", 0)

    def clean_output(self):
        f.remove_dir(self.output)

    @staticmethod
    def get_param_arg(mode):
        if mode == "symbol":
            return ParamDict().get_arg(mode)
        return ParamDict().get_arg(mode) if ParamDict().get_arg(mode) else None

    @staticmethod
    def _convert_ub_port_status(bin_file_path, txt_file_path):
        fmt = f"I{DSMI_UB_PORT_NUM}I"
        try:
            with open(bin_file_path, "rb") as bin_f:
                bin_data = bin_f.read()

            expected_size = struct.calcsize(fmt)
            if len(bin_data) < expected_size:
                raise ValueError(
                    f"Binary expected {expected_size} bytes, actual {len(bin_data)} bytes"
                )

            unpacked_data = struct.unpack(fmt, bin_data[:expected_size])
            link_status = unpacked_data[0]
            port_status = unpacked_data[1 : 1 + DSMI_UB_PORT_NUM]

            with open(txt_file_path, "w", encoding="utf-8") as txt_f:
                txt_f.write("=== DSMI UB Port Status Data ===\n\n")
                txt_f.write("1. Overall UB Link Status:\n")
                ub_link_desc = UB_ENTIRE_STATUS_MAP.get(
                    link_status, f"Unknown status (Value: {link_status})"
                )
                txt_f.write(f"   Status Value: {link_status} -> {ub_link_desc}\n\n")
                txt_f.write("2. Status of Each UB Port (Total 36 ports):\n")
                txt_f.write("   Port No | Status Val | Status Description\n")
                txt_f.write("   --------|------------|-------------------\n")
                for port_idx in range(DSMI_UB_PORT_NUM):
                    status_val = port_status[port_idx]
                    status_desc = UB_PORT_STATUS_MAP.get(
                        status_val, f"Unknown status (Value: {status_val})"
                    )
                    txt_f.write(
                        f"   {port_idx:7d} | {status_val:10d} | {status_desc}\n"
                    )

            log_info(
                f"Conversion successful! {bin_file_path} has been converted to text file {txt_file_path}"
            )

        except FileNotFoundError:
            log_warning(f"Error: {bin_file_path} not found")
        except (struct.error, ValueError) as e:
            log_error(f"Parse error: port_status {e}")
        except (OSError, TypeError, IndexError, KeyError) as e:
            log_error(f"Unexpected error: port_status {e}")

    @staticmethod
    def _convert_ub_port_perf_test(bin_file_path, txt_file_path):
        fmt = f"4I{DL_PORT_RX_VL_NUM}I{DL_PORT_RX_VL_NUM}I28I4I{DL_PORT_RX_VL_NUM}I{DL_PORT_RX_VL_NUM}I28I"
        expected_size = struct.calcsize(fmt)

        try:
            with open(bin_file_path, "rb") as bin_f:
                d = struct.unpack(fmt, bin_f.read())
            if len(d) * 4 < expected_size:
                raise ValueError(
                    f"Binary expected {expected_size} bytes, actual {len(d) * 4} bytes"
                )

            p, s = 0, DL_PORT_RX_VL_NUM
            rx_cnt = (d[p + 1] << 32) | d[p]
            p += 2
            rx_max = (d[p + 1] << 32) | d[p]
            p += 2
            rx_vl_cnt, rx_vl_max = d[p : p + s], d[p + s : p + 2 * s]
            p += 2 * s
            p += 28  # skip rsv1
            tx_cnt = (d[p + 1] << 32) | d[p]
            p += 2
            tx_max = (d[p + 1] << 32) | d[p]
            p += 2
            tx_vl_cnt, tx_vl_max = d[p : p + s], d[p + s : p + 2 * s]

            with open(txt_file_path, "w", encoding="utf-8") as txt_f:
                txt_f.write("=== MAMI Port Performance Test Counter ===\n")
                txt_f.write(
                    f"RX Total: 0x{rx_cnt:016X} ({rx_cnt}) | RX Max: 0x{rx_max:016X} ({rx_max})\n"
                )
                txt_f.write(
                    f"TX Total: 0x{tx_cnt:016X} ({tx_cnt}) | TX Max: 0x{tx_max:016X} ({tx_max})\n\n"
                )
                txt_f.write(
                    f"{'VL':<4}|{'RX Cnt':<20}|{'RX Max':<20}|{'TX Cnt':<20}|{'TX Max':<20}\n{'-' * 90}\n"
                )
                for i in range(s):
                    txt_f.write(
                        f"{i:<4}|{rx_vl_cnt[i]:<20}|{rx_vl_max[i]:<20}|"
                        f"{tx_vl_cnt[i]:<20}|{tx_vl_max[i]:<20}\n"
                    )
            log_info(
                f"Conversion successful! {bin_file_path} has been converted to text file {txt_file_path}"
            )

        except FileNotFoundError:
            log_warning(f"Error: {bin_file_path} not found")
        except (struct.error, ValueError) as e:
            log_error(f"Parse error: port_perf_test {e}")
        except (OSError, TypeError, IndexError, KeyError) as e:
            log_error(f"Unexpected error: port_perf_test {e}")

    @staticmethod
    def _convert_ub_ubnl_dfx(bin_file_path, txt_file_path, dfx_type):
        item_fmt = "64BQ"
        struct_fmt = f"I{item_fmt * STATS_ITEM_NUM}"
        expected_size = struct.calcsize(struct_fmt)
        try:
            with open(bin_file_path, "rb") as bin_f:
                bin_data = bin_f.read()

            if len(bin_data) < expected_size:
                raise ValueError(
                    f"Binary expected {expected_size} bytes, actual {len(bin_data)} bytes"
                )

            unpacked = struct.unpack(struct_fmt, bin_data[:expected_size])
            ptr = 0
            count = unpacked[ptr]
            ptr += 1

            stats_items = []
            for _ in range(count):
                # 提取64个char的原始字节
                name_raw = bytes(unpacked[ptr : ptr + 64])
                ptr += 64
                value = unpacked[ptr]
                ptr += 1

                name = name_raw.split(b"\x00")[0].decode("utf-8", errors="replace")
                name = name.strip() or "Unnamed_Stat"
                stats_items.append((name, value))

            with open(txt_file_path, "w", encoding="utf-8") as txt_f:
                txt_f.write(f"=== MAMI {dfx_type} Data (UBNL DFX) ===\n")
                txt_f.write(f"Reported Count (from struct): {count}\n")
                txt_f.write("-" * 90 + "\n")
                txt_f.write(
                    f"{'Index':<6} | {'Stats Name':<40} | {'64-bit Value':<20}\n"
                )
                txt_f.write(
                    f"{'------':<6} | {'----------------------------------------':<40} | "
                    f"{'--------------------':<20}\n"
                )

                for idx, (name, value) in enumerate(stats_items, 1):
                    txt_f.write(f"{idx:<6} | {name:<40} | {value:<20}\n")

            log_info(
                f"Conversion successful! {bin_file_path} has been converted to text file {txt_file_path}"
            )

        except FileNotFoundError:
            log_warning(f"Error: {bin_file_path} not found")
        except (struct.error, ValueError) as e:
            log_error(f"Parse error: ubnl_dfx {dfx_type} {e}")
        except (OSError, TypeError, IndexError, KeyError) as e:
            log_error(f"Unexpected error: ubnl_dfx {dfx_type} {e}")

    @staticmethod
    def _convert_ub_ubmem_daw(bin_file_path, txt_file_path):
        fmt = "4B"
        try:
            with open(bin_file_path, "rb") as bin_f:
                bin_data = bin_f.read()

            expected_size = struct.calcsize(fmt)
            if len(bin_data) < expected_size:
                raise ValueError(
                    f"Binary expected {expected_size} bytes, actual {len(bin_data)} bytes"
                )

            unpacked_data = struct.unpack(fmt, bin_data[:expected_size])

            template_id = unpacked_data[0]
            balance_algorithm = unpacked_data[1]
            balance_start_bit = unpacked_data[2]
            reserved = unpacked_data[3]

            algorithm_desc = BALANCE_ALGORITHM_MAP.get(
                balance_algorithm, f"Unknown algorithm (value: {balance_algorithm})"
            )

            with open(txt_file_path, "w", encoding="utf-8") as txt_f:
                txt_f.write(
                    "=== MAMI Dynamic Address Window (DAW) Table Properties ===\n\n"
                )
                txt_f.write("DAW Table Configuration:\n")
                txt_f.write(
                    "--------------------------------------------------------\n"
                )
                txt_f.write(
                    f"Template ID: {template_id} (Defined by BIOS, used by control plane)\n"
                )
                txt_f.write(
                    f"Balance Algorithm: {balance_algorithm} -> {algorithm_desc}\n"
                )
                txt_f.write(
                    f"Balance Start Bit: {balance_start_bit} (Lowest address bit for hash)\n"
                )
                txt_f.write(f"Reserved Field: {reserved} (For struct alignment)\n")

            log_info(
                f"Conversion successful! {bin_file_path} has been converted to text file {txt_file_path}"
            )

        except FileNotFoundError:
            log_warning(f"Error: {bin_file_path} not found")
        except (struct.error, ValueError) as e:
            log_error(f"Parse error: ubmem_daw {e}")
        except (OSError, TypeError, IndexError, KeyError) as e:
            log_error(f"Unexpected error: ubmem_daw {e}")

    @staticmethod
    def _convert_ub_ubtpl_acl_src(bin_file_path, txt_file_path):
        head_fmt = "HHI8B"
        head_size = struct.calcsize(head_fmt)
        eid_fmt = "B3B4I"
        struct_fmt = f"IH2B{eid_fmt}IBI12B"
        struct_size = struct.calcsize(struct_fmt)
        try:
            with open(bin_file_path, "rb") as bin_f:
                bin_data = bin_f.read()
            if len(bin_data) < head_size:
                raise ValueError(
                    f"Binary too short! expected ≥{head_size}B, act {len(bin_data)}B"
                )

            # 解析固定头部+位段
            hdr = struct.unpack(head_fmt, bin_data[:head_size])
            num, flag_rsv, end_idx = hdr[0], hdr[1], hdr[2]
            more_flag, _rsv = flag_rsv & 0x01, (flag_rsv >> 1) & 0x7FFF
            body = bin_data[head_size:]

            expected_size = num * struct_size + head_size
            if len(bin_data) < expected_size:
                raise ValueError(
                    f"Binary expected {expected_size} bytes, actual {len(bin_data)} bytes"
                )

            acl_list = []
            for i in range(num):
                acl = struct.unpack(
                    struct_fmt, body[i * struct_size : (i + 1) * struct_size]
                )
                # 解析mamiEid：compressedFlag(acl[4]) + union(acl[8:12])
                eid_flag = acl[4]
                if eid_flag == 0:  # 128位非压缩EID，4个uint32_t拼接
                    eid_hex = "".join([f"{x:08X}" for x in acl[8:12]]).upper()
                else:  # 20位压缩EID，提取低20位
                    eid_20bit = acl[8] & 0x000FFFFF
                    eid_hex = f"{eid_20bit:05X}".upper()
                # 提取aclGrpId低24位，整理核心字段
                acl_grp_id = acl[14] & 0x00FFFFFF
                acl_list.append(
                    (acl[0], acl[1], eid_flag, eid_hex, acl[12], acl[13], acl_grp_id)
                )

            with open(txt_file_path, "w", encoding="utf-8") as txt_f:
                txt_f.write("=== UBTPL Source ACL Config (Support 128/20bit EID) ===\n")
                txt_f.write(
                    f"Return Count: {num} | More Flag: {more_flag} (0=No/1=Yes)\n"
                )
                txt_f.write(f"End Index: 0x{end_idx:08X} ({end_idx})\n")
                txt_f.write(f"{'-' * 130}\n")
                txt_f.write(
                    f"{'Idx':<4}|{'PlaneId':<10}|{'UEIdx':<8}|{'EidFlag':<8}|{'EID':<32}|"
                    f"{'TransType':<10}|{'AclType':<8}|{'AclGrpId':<10}\n"
                )
                txt_f.write(
                    f"{'-' * 4}|{'-' * 10}|{'-' * 8}|{'-' * 8}|{'-' * 32}|{'-' * 10}|{'-' * 8}|{'-' * 10}\n"
                )
                for idx, (p, u, c, e, t, a, g) in enumerate(acl_list):
                    txt_f.write(
                        f"{idx:<4}|{p:<10}|{u:<8}|{c:<8}|{e:<32}|{t:<10}|{a:<8}|{g:<10}\n"
                    )

            log_info(
                f"Conversion successful! {bin_file_path} has been converted to text file {txt_file_path}"
            )

        except FileNotFoundError:
            log_warning(f"Error: {bin_file_path} not found")
        except (struct.error, ValueError) as e:
            log_error(f"Parse error: ubtpl_acl_src {e}")
        except (OSError, TypeError, IndexError, KeyError) as e:
            log_error(f"Unexpected error: ubtpl_acl_src {e}")

    @staticmethod
    def _convert_ub_sl_to_vl(bin_file_path, txt_file_path):
        struct_fmt = f"2I{UBQOS_MAX_SL_NUM * 2}H"
        expected_size = struct.calcsize(struct_fmt)

        try:
            with open(bin_file_path, "rb") as bin_f:
                bin_data = bin_f.read()
            if len(bin_data) < expected_size:
                raise ValueError(
                    f"Binary expected {expected_size} bytes, actual {len(bin_data)} bytes"
                )

            # 解包数据并提取核心字段
            d = struct.unpack(struct_fmt, bin_data[:expected_size])
            plane_id, num = d[0], d[1]
            # 校验有效配置数范围，非法值自动修正
            num = max(0, min(num, UBQOS_MAX_SL_NUM))
            # 提取SL-VL配置，按索引分组
            sl2vl = [(d[2 + 2 * i], d[3 + 2 * i]) for i in range(UBQOS_MAX_SL_NUM)]

            with open(txt_file_path, "w", encoding="utf-8") as txt_f:
                txt_f.write("=== UBQOS SL to VL Mapping Configuration ===\n")
                txt_f.write(
                    f"Plane ID: {plane_id} | Valid Config Num: {num} (Max: {UBQOS_MAX_SL_NUM})\n"
                )
                txt_f.write(f"Struct Total Size: {expected_size} bytes\n{'-' * 60}\n")
                txt_f.write(
                    f"{'Idx':<6}|{'SL(0-15)':<10}|{'VL(0-15)':<10}|{'Status':<10}\n"
                )
                txt_f.write(f"{'-' * 6}|{'-' * 10}|{'-' * 10}|{'-' * 10}\n")
                for i, (sl, vl) in enumerate(sl2vl):
                    status = "Valid" if i < num else "Reserved"
                    txt_f.write(f"{i:<6}|{sl:<10}|{vl:<10}|{status:<10}\n")
            log_info(
                f"Conversion successful! {bin_file_path} has been converted to text file {txt_file_path}"
            )

        except FileNotFoundError:
            log_warning(f"Error: {bin_file_path} not found")
        except (struct.error, ValueError) as e:
            log_error(f"Parse error: sl_to_vl {e}")
        except (OSError, TypeError, IndexError, KeyError) as e:
            log_error(f"Unexpected error: sl_to_vl {e}")

    def write_res_file(self, file_name, file_content):
        try:
            flags = os.O_WRONLY | os.O_CREAT
            modes = stat.S_IWUSR | stat.S_IRUSR
            with os.fdopen(
                os.open(f"{self.output}/{file_name}", flags, modes), "w"
            ) as fw:
                fw.write(file_content)
        except (OSError, TypeError) as e:
            log_error(e)

    def run(self):
        if f.check_exists(self.path) and f.check_exists(self.output):
            if os.path.relpath(self.path, self.output).endswith(".."):
                self.clean_output()
                log_error(
                    'The output directory cannot be the same as the "path" directory or its subdirectories.'
                )
                return False
        mode_function = {
            "trace": self.__atrace_analyze,
            "stackcore": self.__atrace_analyze,
            "coretrace": self.__atrace_analyze,
            "coredump": self.__core_dump_analyze,
            "aicore_error": self.__aicore_error_analyze,
            "ub": self.__ub_analyze,
        }
        func = mode_function.get(self.run_mode)
        return func()

    def __copy_dir(self):
        if self.run_mode == "trace":
            return f.copy_dir(self.path, self.output)
        # stackcore, coretrace
        for root, _, files in os.walk(self.path):
            for file in files:
                if self.run_mode in {"stackcore", "coretrace"} and not file.startswith(
                    self.run_mode
                ):
                    continue
                root_path = os.path.relpath(root, self.path)
                if not f.copy_file_to_dir(
                    os.path.join(root, file), os.path.join(self.output, root_path)
                ):
                    return False
        return True

    def __atrace_analyze(self):
        """
        parse the trace file. If the file exists, parse the file. If the directory exists, parse the directory.
        """
        if self.run_mode == "trace":
            parse_struct = ParseTrace(True)
        elif self.run_mode == "stackcore":
            parse_struct = ParseStackCore(self.symbol_path, self.file)
            if not self.symbol_path:
                log_warning(
                    "'--symbol_path' is not set, the default path will be used to analyze."
                )
        elif self.run_mode == "coretrace":
            parse_struct = ParseCoreTrace(self.symbol_path, self.file)
            if not self.symbol_path:
                log_warning(
                    "'--symbol_path' is not set, the default path will be used to analyze."
                )
        else:
            return False

        if self.file:
            f.copy_file_to_dir(self.file, self.output)
            log_info(f"Copy source file {self.file} into {self.output}")
            return parse_struct.start_parse_file(
                os.path.join(self.output, os.path.basename(self.file))
            )
        elif self.path:
            self.path = os.path.abspath(self.path)
            self.output = os.path.join(self.output, self.path.split(os.sep)[-1])
            copy_res = self.__copy_dir()
            if not copy_res:
                return False
            # Each run mode names its artefacts differently: trace uses .bin,
            # stackcore uses .txt, and coretrace keeps the bare coretrace* name,
            # so the denominator has to follow the naming or it is 0 and the
            # progress bar disappears.
            if self.run_mode == "trace":
                count = get_target_cnt(self.output, ".bin")
            elif self.run_mode == "coretrace":
                count = get_target_cnt(self.output, prefix="coretrace")
            else:
                count = get_target_cnt(self.output, ".txt")
            return parse_struct.run(self.output, count=count)
        else:
            log_error("Analyze requires either the --file or --path argument")
            return False

    def __core_dump_analyze(self):
        stack_txt = "[process]\n"
        if not check_command("gdb"):
            log_error("Gdb does not exist, install gdb before using it.")
            return False
        if not self.exe_file:
            log_error("The --exe_file parameter must exist for analyze coredump.")
            return False
        if not self.core_file:
            log_error("The --core_file parameter must exist for analyze coredump.")
            return False
        core_dump = CoreDump(self.exe_file, self.core_file, self.symbol, self.output)
        stack_txt, pid = core_dump.start_gdb(stack_txt)
        if pid == 0:
            return False
        file_name = f"stackcore_{os.path.basename(self.exe_file)}_{pid}_{int(round(time.time() * 1000))}.txt"
        self.write_res_file(file_name, stack_txt)
        return True

    def __aicore_error_analyze(self):
        output_path = os.path.dirname(self.output)
        msaicerr_path = (
            ParamDict().tools_path.parents[1].joinpath("msaicerr", "msaicerr.py")
        )
        log_debug(f"Start load msaicerr tools path: {msaicerr_path}")
        if not os.path.exists(msaicerr_path):
            log_error(
                "The path of the msaicerr tool cannot be found, please install the whole package."
            )
            return False
        if self.path:
            log_debug(f"msaicerr analyze path {self.path}")
            cmd = (
                f"{sys.executable} {msaicerr_path} -p {shlex.quote(self.path)} "
                f"-dev {self.device_id} -out {shlex.quote(output_path)}"
            )
        else:
            asys_collector = AsysCollect()
            task_res = AsysCollect().run()
            log_debug(
                f"Asys collect path {asys_collector.output_root_path} res {task_res}"
            )
            if not task_res:
                log_error("Asys collect log failed")
                return False
            cmd = (
                f"{sys.executable} {msaicerr_path} -p {shlex.quote(str(asys_collector.output_root_path))} "
                f"-dev {self.device_id} -out {shlex.quote(output_path)}"
            )
        log_debug(f"Start run: {cmd}")
        res = real_time_output(cmd)
        self.clean_output()
        return res

    def __ub_analyze(self):
        if self.path:
            self.path = os.path.abspath(self.path)
        else:
            log_error("Please enter the path to the UB data collection file.")
            return False
        for ub_file_name in ub_file_names:
            func_name = "_convert_ub_" + ub_file_name
            bin_file_name = ub_file_name + ".bin"
            txt_file_name = ub_file_name + ".txt"
            bin_file_path = os.path.join(self.path, bin_file_name)
            txt_file_path = os.path.join(self.output, txt_file_name)
            func = getattr(self, func_name, None)
            if func is not None:
                func(bin_file_path, txt_file_path)
        return True

    def _convert_ub_ubnl_dfx_statistic(self, bin_file_path, txt_file_path):
        self._convert_ub_ubnl_dfx(bin_file_path, txt_file_path, "Statistic")

    def _convert_ub_ubnl_dfx_ssu_schedule(self, bin_file_path, txt_file_path):
        self._convert_ub_ubnl_dfx(bin_file_path, txt_file_path, "Ssu Schedule")

    def _convert_ub_ubnl_dfx_config_item(self, bin_file_path, txt_file_path):
        self._convert_ub_ubnl_dfx(bin_file_path, txt_file_path, "Config Item")
