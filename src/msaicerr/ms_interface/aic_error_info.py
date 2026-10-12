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

import re
import struct
from ms_interface import utils
from ms_interface.constant import ChipType, Constant, RetCode


CORRECTED_PC_NOTICE = (
    "The corrected PC is fixed by the AI Core error registers and is more "
    "credible than the original PC. Locate the fault by the corrected info first."
)


def detect_chip_type(error_code: str) -> ChipType:
    """Tell the two `error code = ...` dialects apart.

    910B (Stars architecture) prints the raw aicError[0] register value via
    %#PRIx64, so a non-zero code always carries the 0x prefix. 950 (David
    architecture) prints the already resolved bit numbers as a decimal,
    comma-separated list. A bare "0" is the 950 no-error marker, but 910B
    renders 0 the same way (%#x drops the prefix for zero), so it is left to
    the 910B path where the existing trap_or_timeout fallback handles it.
    """
    error_code = error_code.strip()
    if error_code.lower().startswith("0x") or error_code == "0":
        return ChipType.ASCEND_910B
    if re.fullmatch(r"\d+(?:\s*,\s*\d+)*", error_code):
        return ChipType.ASCEND_950
    return ChipType.ASCEND_910B


def detect_chip_type_by_dump_info(dump_info: str) -> ChipType:
    """Tell the two chips apart by which registers the `dump info:` line carries.

    比 error_code 可靠：error_code 为裸 "0" 时两种芯片同形，detect_chip_type 只能
    落到 910B。但两者打印的寄存器集不同 —— 950（device_error_proc_c.cc）打
    sc/su/l1 error info，910B（device_error_core_proc.cc）打 ifu/ccu/biu error
    info，互不重叠。都判不出时返回 None，由调用方决定回退口径。
    """
    if not dump_info:
        return None
    lowered = dump_info.lower()
    if any(key in lowered for key in Constant.DAVID_ONLY_DUMP_KEYS):
        return ChipType.ASCEND_950
    if any(key in lowered for key in Constant.STARS_ONLY_DUMP_KEYS):
        return ChipType.ASCEND_910B
    return None


def parse_stars_error_bits(error_code: str) -> list:
    """Bit-scan a 910B error code into bit numbers.

    Returns an empty list when no bit is set, and also when the code is blank
    or unparsable: get_hexstr_value reports those as -1, whose two's-complement
    binary form would otherwise be mistaken for bit 0 being set.
    """
    if utils.get_hexstr_value(error_code) <= 0:
        return []
    return utils.hexstr_to_list_bin(error_code)


def parse_david_error_codes(error_code: str) -> list:
    """Split a 950 error code into bit numbers, preserving runtime order."""
    codes = []
    for part in error_code.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            codes.append(int(part))
        except ValueError:
            utils.print_warn_log(f"Failed to parse 950 error code {part}.")
    return codes


def detect_core_err_type(core_err_type: str) -> str:
    """Bucket the '<type> error' word captured by AICORE_ERR_OCCUR(_OST).

    AIC 与 AIV 共用同一份数字 core id，日志用 "the error is aicore error" /
    "the error is aivec error" 区分核型（见 runtime PrintDavidCoreInfo 和
    GetStarsRingBufferHeadMsg）。此处把 aicore 归为 aic、aivec/aivector 归为
    aiv；取不到类型时按 aic 处理，保持历史行为。
    """
    raw = (core_err_type or "").lower()
    return "aiv" if "aiv" in raw else "aic"


class AicErrorInfo:
    """
    AI core Error info
    """

    def __init__(self: any) -> None:
        self.aic_error_info = {}
        self.aic_error_groups = []
        self.task_id = ""
        self.stream_id = ""
        self.node_name = ""
        self.data_name = ""  # plog解析出的原始data_name，可能超过NAME_MAX
        self.kernel_name = ""
        self.flip_num = ""
        self.instr = ""
        self.graph_file = ""
        self.extra_info = ""
        self.err_time_obj = None
        self.ifu_err_type = ""
        self.mte_err_type = ""
        self.args_num_in_json = None
        self.dump_file = []
        self.dump_info = ""
        self.aval_addrs = []
        self.necessary_addr = {}
        self.atomic_add_err = False
        self.single_op_test_result = RetCode.NOT_RUN
        self.single_op_attempted = False
        self.single_op_mem_monitor = ""
        self.data_dump_result = True
        self.atomic_clean_check = True
        self.args_before_list = []
        self.args_after_list = []
        self.addr_valid = True
        self.env_available = True
        self.flag_check = ""
        self.check_args_result = True
        self.debug_level = 0
        self.kernel_path = ""
        self.data_path = ""
        self.tiling_key = 0
        self.tiling_data = ""
        self.tiling_data_bytes = None
        self.block_dim = -1
        self.input_list = []
        self.output_list = []
        self.workspace_list = []
        self.bin_list = []
        self.cce_file = ""
        self.bin_file = ""
        self.json_file = ""
        self.run_device_id = 0
        self.sub_ptr_addrs = {}
        self.ffts_addrs_num = 0
        self.rts_block_dim = -1
        self.driver_aicore_num = -1
        self.workspace = 0
        self.hash_id = 0
        self.single_op_log_path = ""
        # PC 修正结果，见 pc_corrector.get_corrected_pc；拿不到时为空 dict。
        self.corrected_pc = {}
        self.corrected_instr = ""

    def analyse(self: any) -> str:
        """
        AI core error analyse
        """
        # 此步骤会解析出 mte_err_type ifu_err_type
        aicerror_info = self._get_aicerror_info()

        addr_check_str = self._get_addr_check_str()

        result_msg = {
            # SUCCESS表示用例执行完成但没有复现出AI Core error，不代表算子没问题
            RetCode.SUCCESS: "The single-operator test case was executed, "
            "but the AI Core error was not reproduced.",
            RetCode.FAILED: "The AI Core error was reproduced by the single-operator test case.",
            RetCode.NOT_RUN: "The single-operator test case was not executed, "
            "so it cannot be used to confirm the AI Core error.",
        }
        single_op_mem_monitor = self.single_op_mem_monitor

        msg = f"""{self.root_cause_conclusion}

***********************1. Basic information********************
error time        : {self.aic_error_info.get("err_time", "")}
device id         : {self.aic_error_info.get("dev_id", "")}
task id           : {self.task_id}
stream id         : {self.stream_id}
node name         : {self.graph_file}
kernel name       : {self.kernel_name}
flip num          : {self.flip_num}
kernel file       : {self.bin_file}
json file         : {self.json_file}
cce file          : {self.cce_file}
rts_block_dim     : {self.rts_block_dim}
driver_aicore_num : {self.driver_aicore_num}

***********************2. AI Core DFX Register***********************
{self._get_group_dfx(aicerror_info)}

***********************3. Operator Error Line Number************************
{self._get_group_pc()}

****************4. Operator Input/Output Memory*******************
{addr_check_str}
args before execution: {self._get_args_str(self.args_before_list)}
args after  execution: {self._get_args_str(self.args_after_list)}

***********************5. Operator Dump File Parsing*************************
{self._get_tiling_str()}
{self.dump_info}

********************6. Execution Result of the Single-Operator Test Case***********************
{result_msg.get(self.single_op_test_result)}

{single_op_mem_monitor}
"""
        return msg

    def get_conclusion(self: any) -> str:
        conclusion = ""
        num_default = -1
        if not self.atomic_clean_check:
            conclusion = (
                "The memset or atomic_clean operator is not inserted before this operator in the graph,"
                " while memory cleanup is required before operator execution.\n"
            )
        elif self.flag_check:
            conclusion = "The set_flag and wait_flag instructions are not used together in the operator code.\n"
        elif (
            self.rts_block_dim != num_default
            and self.driver_aicore_num != num_default
            and self.rts_block_dim > self.driver_aicore_num * 2
        ):
            conclusion = "The number of AI Cores in the environment is less than that required by the operator.\n"
        elif self.aic_error_info.get("current_pc", "") == "0x0":
            conclusion = "The line number of the operator error instruction is 0.\n"
        elif self.atomic_add_err:
            conclusion = (
                "Atomic add has a precision overflow. Check the operator precision."
                "Note that if tasks are concurrently executed on the NPU, a false warning may be reported.\n"
            )
        elif "data invalid" in self.dump_info:
            conclusion = (
                "The maintenance and test information is insufficient or the format is "
                "incorrect, contact technical support.\n"
            )
        elif self.single_op_test_result is RetCode.FAILED:
            conclusion = (
                "The AI Core error was reproduced by the single-operator test case. "
                "The operator logic may be incorrect.\n"
            )
        elif not self.check_args_result:
            conclusion = (
                "If the arguments are inconsistent before and after operator execution, "
                "memory access may be out of bounds. You are advised to use the memory error detection model "
                "to locate the fault.\n"
            )
        elif not self.addr_valid or not self.data_dump_result:
            conclusion = (
                "The input/output memory address of the operator is abnormal "
                "(or the original dumped data fails). Check the framework or application.\n"
            )
        elif not self.env_available:
            conclusion = "Failed to execute the built-in sample operator. Check the environment.\n"
        elif self.single_op_attempted and self.single_op_test_result is RetCode.NOT_RUN:
            conclusion = (
                f"The single-operator test case was not executed successfully, so it cannot be used to "
                f"confirm the AI Core error. Check whether the *.o and *.json files of the operator are "
                f"complete and match each other, and check the single-operator log in "
                f"{self.single_op_log_path} for the failure cause.\n"
            )
        elif self.single_op_test_result is RetCode.SUCCESS:
            conclusion = (
                "The single-operator test case was executed, but the AI Core error was not reproduced. "
                "In case of an unknown error mode, "
                "you are advised to:\n"
                "(1) check the operator again by using the msSanitizer tool.\n"
                "(2) If out-of-bounds memory access occurs on other operators, you are advised to enable "
                "memory error detection with op_debug_config=oom and then check the operators, "
                "For details: https://www.hiascend.com/zh/document.\n"
                "(3) For details about the framework, contact technical support.\n"
            )

        if not conclusion:
            if not utils.ExceptionRootCause().causes:
                conclusion = "Internal error. Contact technical support.\n"
            else:
                conclusion = (
                    "The maintenance and test information is insufficient or the format is incorrect, "
                    "contact technical support.\n"
                )
            conclusion += utils.ExceptionRootCause().format_causes()
        return conclusion

    @property
    def root_cause_conclusion(self):
        return self.get_conclusion()

    def _get_pc_str(self: any, include_notice=True) -> str:
        """Report the original PC, and the corrected PC when it is available."""
        result = (
            "Original Info:\n"
            f"start pc          : {self.aic_error_info.get('start_pc', '')}\n"
            f"current pc        : {self.aic_error_info.get('current_pc', '')}\n"
        )
        instr = (self.instr or "").strip()
        if instr:
            result += f"{instr}\n"
        if not self.corrected_pc:
            return result
        result += (
            "\nCorrected Info:\n"
            f"start pc          : {self.corrected_pc.get('start_pc', '')}\n"
            f"current pc        : {self.corrected_pc.get('current_pc', '')}\n"
        )
        corrected_instr = (self.corrected_instr or "").strip()
        if corrected_instr:
            result += f"{corrected_instr}\n"
        if include_notice:
            result += f"\n{CORRECTED_PC_NOTICE}\n"
        return result

    @staticmethod
    def _group_core_id_lines(group) -> str:
        """core-id lists of one AIC_ERROR category, bucketed by aic/aiv.

        AIC 与 AIV 共用同一份数字 core id，若混在一起会重复展示，因此按核型
        （aic/aiv）分行列出并保持冒号对齐。
        """
        out = []
        for kind, key in (("aic", "cores_aic"), ("aiv", "cores_aiv")):
            cores = group.get(key) or []
            if not cores:
                continue
            # 与 Basic information / start pc 对齐，标签统一按 18 位填充。
            label = f"core id({kind})".ljust(18)
            out.append(f"{label}: [{', '.join(cores)}]")
        return "\n".join(out)

    def _get_group_dfx(self, default):
        if not self.aic_error_groups:
            return default
        lines = []
        for code, group in self.aic_error_groups:
            old_info = self.aic_error_info
            old_extra = self.extra_info
            try:
                self.aic_error_info = group["records"][0]
                self.extra_info = self.aic_error_info.get("extra_info", "")
                desc = self._get_aicerror_info()
            finally:
                self.aic_error_info = old_info
                self.extra_info = old_extra
            # 错误描述内部可能包含历史格式产生的多余空行，分类展示时统一压缩。
            desc = re.sub(r"\n{2,}", "\n", desc.strip())
            # AIC_ERROR 标签 18 位填充，与 Basic information / start pc 冒号列对齐。
            lines.append(
                f"AIC_ERROR         : {code}\n{desc}\n{self._group_core_id_lines(group)}"
            )
        return "\n\n".join(lines)

    def _get_group_pc(self):
        if not self.aic_error_groups:
            return self._get_pc_str()
        out = []
        has_corrected = False
        for code, group in self.aic_error_groups:
            rec = group["records"][0]
            old_info = self.aic_error_info
            old_pc = self.corrected_pc
            old_instr = self.corrected_instr
            old_extra = self.extra_info
            try:
                self.aic_error_info = rec
                self.extra_info = rec.get("extra_info", "")
                # 每组带独立的 Corrected Info（set_info 已按组首条记录修正），
                # 换成组内那份，避免第二组起沿用第一组的 current pc。
                self.corrected_pc = group.get("corrected_pc") or {}
                self.corrected_instr = group.get("corrected_instr") or ""
                if self.corrected_pc:
                    has_corrected = True
                kind = detect_core_err_type(rec.get("core_err_type", ""))
                # 与 _get_group_dfx / Basic information 一致，AIC_ERROR / core id
                # 标签按 18 位填充，使本段冒号列和 start/current pc 对齐。
                err_label = "AIC_ERROR".ljust(18)
                core_label = f"core id({kind})".ljust(18)
                out.append(
                    f"{err_label}: {code}\n{core_label}: {rec.get('core_id', '')}\n"
                    + self._get_pc_str(include_notice=False)
                )
            finally:
                self.aic_error_info = old_info
                self.corrected_pc = old_pc
                self.corrected_instr = old_instr
                self.extra_info = old_extra
        result = "\n".join(out)
        if has_corrected:
            result += f"\n\n{CORRECTED_PC_NOTICE}"
        return result

    @staticmethod
    def _get_args_str(input_list: list) -> str:
        args_str = ""
        for arg in input_list:
            args_str += f"[{arg}],"
        return f"[{args_str[:-1]}]"

    def _get_tiling_str(self: any) -> str:
        if not self.tiling_data:
            return "\n"
        binfile = open(self.tiling_data, "rb")  # rb表示以二进制模式读取
        # 读取文件内容，返回一个bytes对象
        content = binfile.read()
        # 关闭文件
        binfile.close()
        result_str = f"tiling_data: {self.tiling_data}\n"
        tiling_datas = content
        int32_size = struct.calcsize("i")
        int64_size = struct.calcsize("q")
        float16_size = struct.calcsize("e")

        def parse_data(data, size, fmt):
            try:
                result = [
                    struct.unpack(fmt, data[i : i + size])[0]
                    for i in range(0, len(data), size)
                ]
            except struct.error:
                result = "Cannot decode in this dtype"
            return result

        int32_values = parse_data(tiling_datas, int32_size, "i")
        result_str += f"tiling data in int32: {int32_values}\n"

        int64_values = parse_data(tiling_datas, int64_size, "q")
        result_str += f"tiling data in int64: {int64_values}\n"

        float16_values = parse_data(tiling_datas, float16_size, "e")
        result_str += f"tiling data in float16: {float16_values}\n"

        return result_str + "\n"

    def _get_addr_check_str(self: any) -> str:
        result_str = ""
        used_addrs = self.necessary_addr

        if not used_addrs:
            input_params, output_params = [], []
        else:
            input_params = used_addrs.get("input_addr")
            output_params = used_addrs.get("output_addr")

        for input_param in input_params:
            index = input_param.get("index")
            if not input_param.get("in_range"):
                result_str += f"*[ERROR]input[{index}] is out of range\n"
                self.addr_valid = False

        for output_param in output_params:
            index = output_param.get("index")
            if not output_param.get("in_range"):
                result_str += f"*[ERROR]output[{index}] is out of range\n"
                self.addr_valid = False
        result_str += "\n"
        for input_param in input_params:
            index = int(input_param.get("index"))
            size = int(input_param.get("size"))
            if input_param.get("addr").startswith("0x"):
                addr = int(input_param.get("addr"), 16)
            else:
                addr = int(input_param.get("addr"))
            end_addr = addr + size
            result_str += f"input[{index}] addr: {hex(addr)} end_addr:{hex(end_addr)} size: {hex(size)}\n"

        for output_param in output_params:
            index = int(output_param.get("index"))
            size = int(output_param.get("size"))
            if output_param.get("addr").startswith("0x"):
                addr = int(output_param.get("addr"), 16)
            else:
                addr = int(output_param.get("addr"))
            end_addr = addr + size
            result_str += f"output[{index}] addr: {hex(addr)} end_addr:{hex(end_addr)} size: {hex(size)}\n"

        fault_arg_indexes = used_addrs.get("fault_arg_index")
        need_check_args = used_addrs.get("need_check_args")
        if fault_arg_indexes:
            for arg_index in fault_arg_indexes:
                result_str += (
                    f"arg[{arg_index}][0x{need_check_args[arg_index]:X}] cannot find alloc log, "
                    "if it is not tiling_gm, please check \n"
                )

        workspace = used_addrs.get("workspace")
        if workspace:
            result_str += f"workspace_bytes:{workspace}\n"

        return result_str

    def _get_aicerror_info(self: any) -> str:
        error_code = self.aic_error_info.get("error_code", "")
        if detect_chip_type(error_code) is ChipType.ASCEND_950:
            return self._get_david_error_info(error_code)
        return self._get_stars_error_info(error_code)

    def _get_david_error_info(self: any, error_code: str) -> str:
        """Resolve a David/950 error code.

        The runtime has already bit-scanned and masked the six error registers,
        so error_code is a comma-separated list of absolute bit numbers.
        """
        aicerror_info_list = []
        for code in parse_david_error_codes(error_code):
            entry = Constant.AIC_ERROR_INFO_DICT_DAVID.get(code)
            if entry is None:
                # Bit is set but absent from g_davidErrorMapInfo; the runtime
                # skips these too, so only note the bit number.
                aicerror_info_list.append(f"\nunknown error bit {code}")
            else:
                aicerror_info_list.append(f"\n{entry.get('name')}, {entry.get('desc')}")
            aicerror_info_list.append("\n\n")
        return "".join(aicerror_info_list).strip("\n")

    def _get_stars_error_info(self: any, error_code: str) -> str:
        aicerror_info_list = []
        handled_err_type = []
        ret = parse_stars_error_bits(error_code)
        if not ret:
            # No error bit set at all, which is distinct from bit 0 being set.
            return Constant.NO_ERROR_BIT_INFO
        for i in ret:
            aicerr_info = Constant.AIC_ERROR_INFO_DICT.get(i)
            if aicerr_info is None:
                aicerror_info_list.append(f"\nunknown error bit {i}\n\n")
                continue
            err_type = aicerr_info.split("_")[0].lower()
            if err_type in handled_err_type:
                continue
            handled_err_type.append(err_type)
            if err_type == "vec":
                aicerror_info_list.append(
                    "\nVEC_ERR_INFO : " + self._analyse_vec_errinfo()
                )
            elif err_type == "ifu":
                aicerror_info_list.append(
                    "\nIFU_ERR_INFO : " + self._analyse_ifu_errinfo()
                )
            elif err_type == "mte":
                aicerror_info_list.append(
                    "\nMTE_ERR_INFO : " + self._analyse_mte_errinfo(i)
                )
            elif err_type == "cube":
                aicerror_info_list.append(
                    "\nCUBE_ERR_INFO: " + self._analyse_cube_errinfo()
                )
            elif err_type == "ccu":
                aicerror_info_list.append(
                    "\nCCU_ERR_INFO : " + self._analyse_ccu_errinfo()
                )
            elif err_type == "biu":
                aicerror_info_list.append(
                    "\nBIU_ERR_INFO : " + self._analyse_biu_errinfo()
                )
            aicerror_info_list.append(f"\n{aicerr_info}")
            aicerror_info_list.append("\n\n")
        aicerror_info = "".join(aicerror_info_list).strip("\n")
        return aicerror_info

    # Error PC [9:2]
    def find_extra_pc(self: any) -> str:
        """
        find extra pc
        """
        error_code = self.aic_error_info.get("error_code", "")
        if detect_chip_type(error_code) is ChipType.ASCEND_950:
            # The 950 log has no *_ERR_INFO registers in extra_info, so there
            # is no [9:2] fragment to recover.
            return ""
        ret = parse_stars_error_bits(error_code)
        if not ret:
            # No error bit set, so no module register to read the fragment from.
            # Previously this aliased to bit 0, which only returned "" because
            # bit 0 held the trap_or_timeout placeholder; now that bit 0 is
            # biu_l2_read_oob the sentinel has to be explicit.
            return ""
        extra_err_key = ""
        key_map = {
            "vec": Constant.VEC_KEY,
            "mte": Constant.MTE_KEY,
            "cube": Constant.CUBE_KEY,
            "ccu": Constant.CCU_KEY,
            "biu": Constant.BIU_KEY,
            "ifu": Constant.IFU_KEY,
        }
        for ret_a in ret:
            error_info = Constant.AIC_ERROR_INFO_DICT.get(ret_a)
            if error_info is None:
                continue
            err_type = error_info.split("_")[0].lower()
            if err_type == "ccu":
                return ""
            if err_type in key_map.keys():
                extra_err_key = key_map.get(err_type)
                break

        if extra_err_key == "":
            return ""
        regexp = extra_err_key + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return ""
        if extra_err_key == Constant.MTE_KEY:
            high = utils.get_01_from_hexstr(ret[0], 39, 32)
            low = utils.get_01_from_hexstr(ret[0], 7, 0)
            return high + low
        return utils.get_01_from_hexstr(ret[0], 7, 0)

    def _analyse_ifu_errinfo(self: any) -> str:
        regexp = Constant.IFU_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No IFU_ERR_INFO found"

        errinfo = ret[0]
        # ifu_err_type
        code = utils.get_01_from_hexstr(ret[0], 50, 48)
        self.ifu_err_type = code

        if code in Constant.SOC_ERR_INFO_DICT:
            info = Constant.SOC_ERR_INFO_DICT.get(code)
        else:
            info = "NA"
        errinfo += f"\nifu_err_type bit[50:48]={code}  meaning:{info}"

        # ifu_err_addr
        code = utils.get_01_from_hexstr(ret[0], 47, 2)
        info = "IFU Error Address [47:2]"
        # 补2位0，猜测值
        approximate = hex(int(code + "00", 2))
        errinfo += f"\nifu_err_addr bit[47:2]={code}  meaning:{info}  approximate:{approximate}"
        return errinfo

    def _analyse_mte_errinfo(self: any, err_bit: any) -> str:
        regexp = Constant.MTE_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No MTE_ERR_INFO found"

        errinfo = ret[0]
        # mte_err_type
        code = utils.get_01_from_hexstr(ret[0], 26, 24)
        self.mte_err_type = code

        if err_bit == 46:
            mte_dict = Constant.UNZIP_ERR_INFO_DICT
        elif err_bit == 34:
            mte_dict = Constant.FMC_ERR_INFO_DICT
        elif err_bit == 25:
            mte_dict = Constant.FMD_ERR_INFO_DICT
        elif err_bit == 23:
            mte_dict = Constant.SOC_ERR_INFO_DICT
        elif err_bit == 21:
            mte_dict = Constant.AIPP_ERR_INFO_DICT
        else:
            mte_dict = {}

        if code in mte_dict:
            info = mte_dict.get(code)
        else:
            info = "NA"
        errinfo += "\nmte_err_type bit[26:24]={0:<14}  meaning:{1:}".format(code, info)

        # mte_err_addr
        code = utils.get_01_from_hexstr(ret[0], 22, 8)
        info = "MTE Error Address [19:5]"
        # 补5位0，猜测值
        approximate = hex(int(code + "00000", 2))
        errinfo += (
            "\nmte_err_addr bit[22:8]={0:<15}  meaning:{1:}  approximate:{2:}".format(
                code, info, approximate
            )
        )
        return errinfo

    def _analyse_biu_errinfo(self: any) -> str:
        regexp = Constant.BIU_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No BIU_ERR_INFO found"

        errinfo = ret[0]
        # biu_err_addr
        code = utils.get_01_from_hexstr(ret[0], 24, 0)
        approximate = hex(int(code, 2))
        errinfo += f"\nbiu_err_addr bit[24:0]={code}  in hex:{approximate}"
        return errinfo

    def _analyse_ccu_errinfo(self: any) -> str:
        regexp = Constant.CCU_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No CCU_ERR_INFO found"

        errinfo = ret[0]
        # ccu_err_addr
        code = utils.get_01_from_hexstr(ret[0], 22, 8)
        info = "CCU Error Address [17:3]"
        # 补3位0，猜测值
        approximate = hex(int(code + "000", 2))
        errinfo += f"\nccu_err_addr bit[22:8]={code}  meaning:{info}  approximate:{approximate}"
        return errinfo

    def _analyse_cube_errinfo(self: any) -> str:
        regexp = Constant.CUBE_KEY + r"=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if len(ret) == 0:
            return "No CUBE_ERR_INFO found"

        errinfo = ret[0]
        # cube_err_addr
        code = utils.get_01_from_hexstr(ret[0], 16, 8)
        info = "CUBE Error Address [17:9]"
        # 补9位0，猜测值
        approximate = hex(int(code + "000000000", 2))
        errinfo += f"\ncube_err_addr bit[16:8]={code}  meaning:{info}  approximate:{approximate}"
        return errinfo

    def _analyse_vec_errinfo(self: any) -> str:
        regexp = rf"{Constant.VEC_KEY}=(\S+)"
        ret = re.findall(regexp, self.extra_info, re.M)
        if not ret:
            return "No VEC_ERR_INFO found"

        errinfo = ret[0]
        # vec_err_addr
        code = utils.get_01_from_hexstr(ret[0], 28, 16)
        info = "VEC Error Address [17:5]"
        # 补5位0，猜测值
        approximate = hex(int(code + "00000", 2))
        errinfo += "\nvec_err_addr bit[28:16]={0:<13}  meaning:{1:<28}  approximate:{2}".format(
            code, info, approximate
        )

        # vec_err_rcnt
        code = utils.get_01_from_hexstr(ret[0], 15, 8)
        info = "VEC Error repeat count [7:0]"
        repeats = str(int(code, 2))
        errinfo += (
            "\nvec_err_rcnt bit[15:8]={0:<13}  meaning:{1:<28}  repeats:{2}".format(
                code, info, repeats
            )
        )
        return errinfo
