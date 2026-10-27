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
info.json 结构化报告构建。与 info.txt 同源（均渲染自 AicErrorInfo），按
FR-AJR-001~005 输出：空值语义统一、args 语义化、根因分层映射、路径相对化。
"""

import json
import os
import re
import time

from ms_interface import utils
from ms_interface.aic_error_info import (
    AicErrorInfo,
    CORRECTED_PC_NOTICE,
    SINGLE_OP_RESULT_MSG,
)
from ms_interface.aic_error_info import (
    detect_chip_type,
    parse_david_error_codes,
    parse_stars_error_bits,
)
from ms_interface.constant import Constant, RetCode

REPORT_VERSION = "1.0"
REPORT_TYPE = "aicore_error_analysis"
NOT_COLLECTED = "not_collected"
# 数值哨兵 -1 表示未取到，统一转 not_collected
SENTINEL_DEFAULT = -1

# 910B 各模块错误地址位段：模块 -> (寄存器键, 高位, 低位, 地址含义, 补零位数)
_STARS_ADDR_SEGMENTS = {
    "vec": (Constant.VEC_KEY, 28, 16, "VEC Error Address [17:5]", 5),
    "mte": (Constant.MTE_KEY, 22, 8, "MTE Error Address [19:5]", 5),
    "ifu": (Constant.IFU_KEY, 47, 2, "IFU Error Address [47:2]", 2),
    "ccu": (Constant.CCU_KEY, 22, 8, "CCU Error Address [17:3]", 3),
    "cube": (Constant.CUBE_KEY, 16, 8, "CUBE Error Address [17:9]", 9),
    "biu": (Constant.BIU_KEY, 24, 0, "BIU Error Address [24:0]", 0),
}

# 结论分支 -> 证据与动作模板。分支命中优先级见 match_conclusion_branch。
# evidence 的 field 为 info.json 内字段路径，value 取自 AicErrorInfo。
_CONCLUSION_ACTIONS = {
    "atomic_clean_missing": [
        {
            "action": "Check whether the memset or atomic_clean operator is inserted "
            "before this operator in the GE graph.",
            "purpose": "Locate the missing memory cleanup insertion in the graph.",
            "target": "graph_file",
        }
    ],
    "flag_mismatch": [
        {
            "action": "Check the set_flag and wait_flag instructions in the operator cce code.",
            "purpose": "Confirm the set_flag/wait_flag pairs are used together.",
            "target": "cce_file",
        }
    ],
    "core_num_insufficient": [
        {
            "action": "Check the block_dim configuration and the available AI Core count "
            "of the running environment.",
            "purpose": "Match the operator core requirement with the environment.",
        }
    ],
    "pc_zero": [
        {
            "action": "Check the PC registers in the plog and the operator binary.",
            "purpose": "Confirm whether the kernel is loaded and executed correctly.",
        }
    ],
    "atomic_overflow": [
        {
            "action": "Check the operator precision of the atomic add calculation.",
            "purpose": "Locate the precision overflow in atomic accumulation.",
        }
    ],
    "data_invalid": [
        {
            "action": "Collect the maintenance and test information again and contact "
            "technical support.",
            "purpose": "The collected data is insufficient for automatic analysis.",
        }
    ],
    "single_op_reproduced": [
        {
            "action": "Check the operator implementation logic of the reproduced kernel.",
            "purpose": "The single-operator case reproduced the AI Core error, the "
            "operator logic may be incorrect.",
            "target": "cce_file",
        }
    ],
    "args_mismatch": [
        {
            "action": "Use the memory error detection model (msSanitizer) to locate the "
            "suspected out-of-bounds memory access.",
            "purpose": "The arguments changed during operator execution.",
        }
    ],
    "addr_invalid": [
        {
            "action": "Check the framework or application that allocates the input/output "
            "memory of the operator.",
            "purpose": "The operator input/output memory address is abnormal.",
        }
    ],
    "env_error": [
        {
            "action": "Check the running environment with the built-in sample operator "
            "(python3 msaicerr.py -e).",
            "purpose": "The environment failed to execute the sample operator.",
        }
    ],
    "single_op_not_run": [
        {
            "action": "Check whether the *.o and *.json files of the operator are complete "
            "and match each other, and check the single-operator log.",
            "purpose": "The single-operator case was not executed successfully.",
            "target": "single_op_log_path",
        }
    ],
    "single_op_not_reproduced": [
        {
            "action": "Check the operator again by using the msSanitizer tool.",
            "purpose": "The error was not reproduced by the single-operator case.",
        },
        {
            "action": "Enable memory error detection with op_debug_config=oom and check "
            "the operators if out-of-bounds memory access occurs on other operators.",
            "purpose": "Catch memory errors not reproduced by the single-operator case.",
        },
        {
            "action": "Contact technical support for details about the framework.",
            "purpose": "Escalate the undetermined error mode.",
        },
    ],
}


def _not_collected_if_missing(value, sentinel=None):
    """空值语义：数值哨兵/None 转 not_collected，其余原样返回。"""
    if value is None or value == sentinel:
        return NOT_COLLECTED
    return value


def _num_field(value, sentinel=SENTINEL_DEFAULT):
    """数值字段：哨兵 -1（未取到）转 not_collected。"""
    if value == sentinel:
        return NOT_COLLECTED
    return value


def _path_or_not_collected(path, collection_dir):
    """文件路径字段：不存在转 not_collected，存在转相对路径。"""
    if not path or not os.path.exists(path):
        return NOT_COLLECTED
    return _to_rel(path, collection_dir)


def _to_rel(path, collection_dir):
    """绝对路径 -> 相对 collection_dir 的正斜杠相对路径；失败保留原路径。"""
    if not path:
        return path
    try:
        rel = os.path.relpath(path, collection_dir)
    except (ValueError, OSError):
        utils.print_warn_log(f"Cannot relativize path {path} against {collection_dir}.")
        return path.replace(os.sep, "/")
    return rel.replace(os.sep, "/")


def _hex_addr(value):
    """地址统一为 0x 前缀十六进制字符串。"""
    try:
        return hex(int(value))
    except (TypeError, ValueError):
        return NOT_COLLECTED


def _chip_type_name(error_code):
    from ms_interface.constant import ChipType

    chip = detect_chip_type(error_code)
    return "ascend950" if chip is ChipType.ASCEND_950 else "ascend910b"


def _error_code_desc(info):
    """错误码在 AIC_ERROR_INFO_DICT(_DAVID) 中登记的 desc 列表。

    910B：位号命中条目取 "name, desc" 的 desc 部分；950：位号查 David 表。
    任一位号未登记或无错误位时返回 not_collected。
    """
    error_code = str(info.aic_error_info.get("error_code", ""))
    descs = []
    if _chip_type_name(error_code) == "ascend950":
        for code in parse_david_error_codes(error_code):
            entry = Constant.AIC_ERROR_INFO_DICT_DAVID.get(code)
            if entry is None:
                return NOT_COLLECTED
            descs.append(entry.get("desc", ""))
    else:
        for bit in parse_stars_error_bits(error_code):
            entry = Constant.AIC_ERROR_INFO_DICT.get(bit)
            if not entry:
                return NOT_COLLECTED
            descs.append(entry.split(",", 1)[1].strip())
    return descs if descs else NOT_COLLECTED


def _build_registers(record):
    """910B 寄存器位段结构化：复用 extra_info 中已抽取的寄存器值。

    位段规则与 aic_error_info._analyse_*_errinfo 一致（bits/value/meaning/
    approximate），输出为对象而非文本。record 为分组首条记录，其 extra_info
    由 _get_extra_info 渲染为 "KEY=value" 多行文本。
    """
    extra_info = record.get("extra_info", "") if isinstance(record, dict) else ""
    registers = {}
    for module, (key, high, low, meaning, pad) in _STARS_ADDR_SEGMENTS.items():
        regexp = key + r"=(\S+)"
        ret = re.findall(regexp, extra_info or "", re.M)
        if not ret:
            continue
        raw = ret[0]
        bits = utils.get_01_from_hexstr(raw, high, low)
        entry = {
            "raw_value": raw,
            "bits": f"[{high}:{low}]",
            "value": bits,
            "meaning": meaning,
        }
        try:
            entry["approximate"] = (
                hex(int(bits + "0" * pad, 2)) if pad else hex(int(bits, 2))
            )
        except ValueError:
            entry["approximate"] = NOT_COLLECTED
        registers[module] = entry
    return registers


def _build_aic_error(info):
    if not info.aic_error_groups:
        groups = [
            {
                "error_code": info.aic_error_info.get("error_code", ""),
                "records": [info.aic_error_info],
                "cores_aic": [info.aic_error_info.get("core_id", "")],
                "cores_aiv": [],
            }
        ]
    else:
        groups = [
            {"error_code": code, **group} for code, group in info.aic_error_groups
        ]

    out_groups = []
    for group in groups:
        code = str(group["error_code"])
        if _chip_type_name(code) == "ascend950":
            registers = {}
        else:
            registers = _build_registers(group["records"][0])
        out_groups.append(
            {
                "error_code": code,
                "cores_aic": group.get("cores_aic") or [],
                "cores_aiv": group.get("cores_aiv") or [],
                "registers": registers,
            }
        )
    return {"groups": out_groups, "extend_info": info.extra_info}


def _build_basic_info(info, collection_dir):
    # 空值口径统一：文本类字段取不到输出 not_collected，与文件/数值字段
    # 一致，避免同一字典两种空值语义（"" 与 not_collected 含义不同）
    return {
        "error_time": _not_collected_if_missing(info.aic_error_info.get("err_time")),
        "device_id": _not_collected_if_missing(info.aic_error_info.get("dev_id")),
        "core_id": _not_collected_if_missing(info.aic_error_info.get("core_id")),
        "task_id": _not_collected_if_missing(info.task_id),
        "stream_id": _not_collected_if_missing(info.stream_id),
        "node_name": _not_collected_if_missing(info.node_name),
        "kernel_name": _not_collected_if_missing(info.kernel_name),
        "kernel_file": _path_or_not_collected(info.bin_file, collection_dir),
        "json_file": _path_or_not_collected(info.json_file, collection_dir),
        "cce_file": _path_or_not_collected(info.cce_file, collection_dir),
        "graph_file": (
            _path_or_not_collected(info.graph_file, collection_dir)
            if info.graph_file
            else None
        ),
        "rts_block_dim": _num_field(info.rts_block_dim),
        "driver_aicore_num": _num_field(info.driver_aicore_num),
    }


_LIKELY_LINE_RE = re.compile(r"Error occurred most likely at line:\s*(0x[0-9a-fA-F]+)")
_SRC_LOCATION_RE = re.compile(r"^(?:outerSrc|innerSrc):\s*(.+)$", re.M)


def _parse_likely_error_line(instr_text):
    """从 instr/corrected_instr 文本提取错误行号（十六进制偏移）。"""
    ret = _LIKELY_LINE_RE.findall(instr_text or "")
    if not ret:
        return NOT_COLLECTED
    try:
        return int(ret[-1], 16)
    except ValueError:
        return NOT_COLLECTED


def _parse_src_locations(instr_text):
    """从 corrected_instr 文本提取 outerSrc/innerSrc 源码位置，无法解析返回 None。"""
    locations = _SRC_LOCATION_RE.findall(instr_text or "")
    # 保持文本顺序：outerSrc 在前、innerSrc 在后
    return locations or None


def _build_instructions(info):
    # original：原始 PC 与反编译得到的错误行号（instr 来源）
    original = {
        "start_pc": info.aic_error_info.get("start_pc", ""),
        "current_pc": info.aic_error_info.get("current_pc", ""),
        "likely_error_line": _parse_likely_error_line(info.instr),
    }
    # corrected：PC 修正可用时输出修正后的 PC/行号/源码位置，未修正为
    # null（不适用）。notice 与 original/corrected 平级，携带修正提示。
    if info.corrected_pc:
        corrected = {
            "start_pc": info.corrected_pc.get("start_pc", ""),
            "current_pc": info.corrected_pc.get("current_pc", ""),
            "likely_error_line": _parse_likely_error_line(info.corrected_instr),
            "src_locations": _parse_src_locations(info.corrected_instr)
            or NOT_COLLECTED,
        }
        notice = CORRECTED_PC_NOTICE.strip()
    else:
        corrected = None
        notice = None
    return {
        "original": original,
        "corrected": corrected,
        "notice": notice,
    }


def _kernel_io_counts(info):
    """kernel json supportInfo 的输入/输出数量，读不到返回 (None, None)。

    供 UT 与独立调用兜底使用；主流程由 aicore_error_parser.
    _load_kernel_io_counts 在 Step 4 读一次并缓存到 info.kernel_io_counts，
    构建阶段只读内存字段、不再访问文件。
    """
    if not info.json_file or not os.path.exists(info.json_file):
        return None, None
    try:
        with open(info.json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None, None
    support = data.get("supportInfo", {})
    return len(support.get("inputs") or []), len(support.get("outputs") or [])


def _shape_inline(shape):
    """shape 单行展示：[8, 2048] 形式的字符串。"""
    if shape is None:
        return None
    return "[" + ", ".join(str(dim) for dim in shape) + "]"


def _build_args_list(args, info, num_inputs, num_outputs):
    """单个 args 列表语义化。"""
    result = []
    for idx, value in enumerate(args):
        if idx in info.args_type_marks:
            # normal 已在解析阶段细分/降级，此处兜底防御：normal 不属六值枚举
            arg_type = info.args_type_marks[idx]
            if arg_type == "normal":
                arg_type = "other"
        elif info.ffts_addrs_num and idx >= len(args) - info.ffts_addrs_num:
            arg_type = "shape"
        elif num_inputs is not None and idx < num_inputs:
            arg_type = "input"
        elif (
            num_inputs is not None
            and num_outputs is not None
            and idx < num_inputs + num_outputs
        ):
            arg_type = "output"
        else:
            arg_type = "other"
        entry = {
            "arg_index": idx,
            "arg_type": arg_type,
            "address": _hex_addr(value),
            "dtype": None,
            "shape": None,
            "size_bytes": None,
        }
        if arg_type in ("input", "output", "workspace"):
            meta = _match_tensor_meta(info, arg_type, idx, num_inputs)
            if meta:
                entry["dtype"] = meta.get("dtype")
                entry["shape"] = _shape_inline(meta.get("shape"))
                entry["size_bytes"] = meta.get("size")
        result.append(entry)
    return result


def _match_tensor_meta(info, arg_type, arg_index, num_inputs):
    """按 (类型, arg 序号) 匹配 dump 解析阶段记录的张量元数据。

    dump 元数据的序号语义（dump_data_parser._parse_one_item 记录）：
    - dump json 带 arg_index 字段时为全局 args 序号，直接匹配；
    - 不带时回退为 parse_type 内部序号（input 序号即全局序号；output 为
      dump 内 0 起序，需加 num_inputs 换算为全局序号；workspace 同理按
      dump 序号顺序对齐 args 中 workspace 段的局部序号）。
    """
    for meta in info.dump_tensor_meta:
        if meta.get("parse_type") != arg_type:
            continue
        meta_index = meta.get("index")
        if meta_index == arg_index:
            return meta
    # 内部序号回退匹配：output 的 dump 序号 + num_inputs = 全局序号
    if arg_type == "output" and num_inputs is not None:
        for meta in info.dump_tensor_meta:
            if (
                meta.get("parse_type") == "output"
                and meta.get("index") == arg_index - num_inputs
            ):
                return meta
    # workspace：dump 内 0 起序，args 中 workspace 段按出现顺序对齐
    if arg_type == "workspace":
        workspaces = [
            meta
            for meta in info.dump_tensor_meta
            if meta.get("parse_type") == "workspace"
        ]
        for pos, meta in enumerate(workspaces):
            if meta.get("index") == pos:
                # 找到 dump 序号为 pos 的 workspace 元数据；再对齐 args 段序号
                ws_args = [
                    idx
                    for idx, mark in info.args_type_marks.items()
                    if mark == "workspace" and idx < len(info.args_after_list or [])
                ]
                if arg_index in ws_args and pos == sorted(ws_args).index(arg_index):
                    return meta
    return None


def _build_args_section(info):
    # 解析阶段已缓存的 kernel json 输入/输出数量；未缓存（独立调用/UT 场景）
    # 时兜底读取一次。主流程不走到兜底分支。
    num_inputs, num_outputs = info.kernel_io_counts
    if num_inputs is None:
        num_inputs, num_outputs = _kernel_io_counts(info)
    section = {}
    for key, args in (
        ("before_execute", info.args_before_list),
        ("after_execute", info.args_after_list),
    ):
        if not args:
            section[key] = NOT_COLLECTED
        else:
            section[key] = _build_args_list(args, info, num_inputs, num_outputs)
    return section


def _dump_arg_index(info, meta):
    """dump 元数据序号换算为全局 args 序号，与 args[].arg_index 同一语义。

    dump json 带 arg_index 时已是全局序号，原样返回；无该字段时回退为
    dump 内部序号（input 序号即全局序号；output 为 0 起序，需加 num_inputs；
    workspace 按 dump 序号顺序对齐），避免与 args 在同一报告里两套序号
    语义（2 输入 1 输出时 output 内部序号 0 与 input 0 撞号）。
    """
    parse_type = meta.get("parse_type")
    index = meta.get("index")
    if parse_type == "output":
        num_inputs, _ = _args_io_counts(info)
        # 带全局 arg_index 时 index >= num_inputs；内部序号则 < num_inputs
        if num_inputs is not None and index < num_inputs:
            return index + num_inputs
    if parse_type == "workspace":
        workspaces = [
            m for m in info.dump_tensor_meta if m.get("parse_type") == "workspace"
        ]
        for pos, m in enumerate(workspaces):
            if m is meta:
                ws_args = sorted(
                    idx
                    for idx, mark in info.args_type_marks.items()
                    if mark == "workspace"
                )
                if pos < len(ws_args):
                    return ws_args[pos]
                return index
    return index


def _args_io_counts(info):
    """args 语义化用的 kernel json 输入/输出数量（解析阶段缓存优先）。"""
    num_inputs, num_outputs = info.kernel_io_counts
    if num_inputs is None:
        num_inputs, num_outputs = _kernel_io_counts(info)
    return num_inputs, num_outputs


def _build_dump_info(info, collection_dir):
    files = []
    for meta in info.dump_tensor_meta:
        entry = {
            "file": _to_rel(meta.get("file", ""), collection_dir)
            if meta.get("file")
            else NOT_COLLECTED,
            "arg_index": _dump_arg_index(info, meta),
            "data_stats": meta.get("data_stats", []),
        }
        files.append(entry)
    # 报错 dump 的采集文件（Collection 拷入 collection/dump 的原始 dump，
    # parse() 后 dump_file 为解析命中的文件列表、含临时 .json，取首个真实
    # 存在的原始 dump 文件）
    exception_dump_file = None
    if isinstance(info.dump_file, list):
        for dump_path in info.dump_file:
            if dump_path and os.path.exists(dump_path):
                exception_dump_file = dump_path
                break
    elif info.dump_file and os.path.exists(info.dump_file):
        exception_dump_file = info.dump_file
    return {
        "exception_dump_file": _to_rel(exception_dump_file, collection_dir)
        if exception_dump_file
        else (NOT_COLLECTED if info.dump_file else None),
        "tiling_data": _path_or_not_collected(info.tiling_data, collection_dir),
        "files": files,
    }


def _build_single_op_test(info, collection_dir):
    # 复现 aicore error / 执行成功未复现 / 执行失败 / 未执行，与结论分支口径
    # 一致：attempted=False 时用例根本没跑，输出 Not Run，避免 result 与
    # execute_info（"was not executed"）自相矛盾
    if info.single_op_test_result is RetCode.NOT_RUN and not info.single_op_attempted:
        result = "Not Run"
    else:
        result = {
            RetCode.FAILED: "Aicore Error",
            RetCode.SUCCESS: "Execute Success",
            RetCode.NOT_RUN: "Execute Failed",
        }.get(info.single_op_test_result, "Not Run")
    return {
        "result": result,
        "execute_info": SINGLE_OP_RESULT_MSG.get(
            info.single_op_test_result, NOT_COLLECTED
        ),
        "memory_status": info.single_op_mem_monitor or "",
        "log_path": _path_or_not_collected(info.single_op_log_path, collection_dir)
        if info.single_op_log_path
        else NOT_COLLECTED,
    }


def _evidence(field, value, interpretation):
    return {"field": field, "value": value, "interpretation": interpretation}


def _action_target(info, action, collection_dir):
    target_field = action.get("target")
    if not target_field:
        return None
    raw = getattr(info, target_field, "")
    if not raw or not os.path.exists(raw):
        return NOT_COLLECTED
    return _to_rel(raw, collection_dir)


def _build_root_cause(info, collection_dir):
    # summary 优先输出错误码登记的 desc；无错误码信息时退回结论分支文本
    summary = _error_code_desc(info)
    if summary == NOT_COLLECTED:
        summary = info.get_conclusion()
    branch = info.match_conclusion_branch()

    evidence_map = {
        "atomic_clean_missing": [
            lambda i: _evidence(
                "basic_info.kernel_name",
                i.kernel_name,
                "The operator requires memory cleanup before execution.",
            )
        ],
        "flag_mismatch": [
            lambda i: _evidence(
                "aic_error.groups[0].error_code",
                str(i.aic_error_info.get("error_code", "")),
                "PIPE_ALL found in the error line of the cce code.",
            )
        ],
        "core_num_insufficient": [
            lambda i: _evidence(
                "basic_info.rts_block_dim",
                _num_field(i.rts_block_dim),
                f"rts_block_dim exceeds twice driver_aicore_num "
                f"({_num_field(i.driver_aicore_num)}).",
            )
        ],
        "pc_zero": [
            lambda i: _evidence(
                "instructions.current_pc",
                i.aic_error_info.get("current_pc", ""),
                "The current PC is 0x0.",
            )
        ],
        "atomic_overflow": [
            lambda i: _evidence(
                "aic_error.groups[0].error_code",
                str(i.aic_error_info.get("error_code", "")),
                "Error code 0x800000 with atomic add error in plog.",
            )
        ],
        "data_invalid": [
            lambda i: _evidence(
                "dump_info",
                i.dump_info,
                "The dump data is invalid.",
            )
        ],
        "single_op_reproduced": [
            lambda i: _evidence(
                "single_op_test.result",
                "Aicore Error",
                "The single-operator test case reproduced the AI Core error.",
            )
        ],
        "args_mismatch": [
            lambda i: _evidence(
                "args",
                "before/after lists differ",
                "The arguments are inconsistent before and after operator execution.",
            )
        ],
        "addr_invalid": [
            lambda i: _evidence(
                "single_op_test / dump_info",
                "memory monitor or dump result is abnormal",
                "The input/output memory address is abnormal or the dump failed.",
            )
        ],
        "env_error": [
            lambda i: _evidence(
                "env_check",
                "failed",
                "The built-in sample operator failed to run.",
            )
        ],
        "single_op_not_run": [
            lambda i: _evidence(
                "single_op_test.result",
                "Execute Failed",
                "The single-operator test case was not executed successfully.",
            )
        ],
        "single_op_not_reproduced": [
            lambda i: _evidence(
                "single_op_test.result",
                "Execute Success",
                "The single-operator case was executed without reproducing the error.",
            )
        ],
    }

    evidence = []
    for builder in evidence_map.get(branch, []):
        try:
            evidence.append(builder(info))
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            continue

    # summary 来源：错误码 desc 可用时补充一条证据指向登记表
    if isinstance(summary, list):
        summary = "; ".join(summary)
        evidence.insert(
            0,
            _evidence(
                "aic_error.groups[0].error_code",
                str(info.aic_error_info.get("error_code", "")),
                "Summary comes from the error code description registered in "
                "constant.AIC_ERROR_INFO_DICT(_DAVID).",
            ),
        )

    actions = []
    for action in _CONCLUSION_ACTIONS.get(branch, []):
        # 字段顺序 action → target（可选）→ purpose
        entry = {
            "action": action["action"],
        }
        target = _action_target(info, action, collection_dir)
        if target is not None:
            entry["target"] = target
        entry["purpose"] = action["purpose"]
        actions.append(entry)

    return {"summary": summary, "evidence": evidence, "action_items": actions}


def _build_env_check(info, collect_succ=True):
    if not info.env_check_attempted:
        # 未真正执行（Step 10 抛异常跳过，或采集失败路径根本没走到 Step 10）。
        # 采集失败时分析未成立，不再把原因归到样例算子上，detail 留空。
        detail = (
            ""
            if not collect_succ
            else (
                "The environment check was skipped because running the "
                "sample operator failed. Check the logs for more details."
            )
        )
        return {"result": NOT_COLLECTED, "detail": detail}
    if info.env_available:
        return {"result": "success", "detail": ""}
    return {
        "result": "failed",
        "detail": "Failed to execute the built-in sample operator. Check the environment.",
    }


def build_report(
    info: AicErrorInfo, collect_path: str, collect_succ: bool = True
) -> dict:
    """从 AicErrorInfo 构建完整 info.json dict（不落盘，供 UT 直接断言）。"""
    collection_dir = os.path.join(collect_path, "collection")
    report = {
        "report_version": REPORT_VERSION,
        "report_type": REPORT_TYPE,
        "analysis_result": "success" if collect_succ else "failed",
        "collection_dir": collection_dir,
        "generated_at": time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime()),
        "root_cause": _build_root_cause(info, collection_dir),
        "basic_info": _build_basic_info(info, collection_dir),
        "aic_error": _build_aic_error(info),
        "instructions": _build_instructions(info),
        "args": _build_args_section(info),
        "dump_info": _build_dump_info(info, collection_dir),
        "single_op_test": _build_single_op_test(info, collection_dir),
        "env_check": _build_env_check(info, collect_succ),
        "op_in_graph": None,
    }
    return report


def write_json_report(
    err_i_folder: str,
    info: AicErrorInfo,
    collect_path: str,
    collect_succ: bool = True,
) -> None:
    """构建并落盘 info.json；任何异常仅告警，不影响主流程与退出码。"""
    json_file = os.path.join(err_i_folder, "info.json")
    try:
        report = build_report(info, collect_path, collect_succ)
        # 先序列化成完整字符串再落盘：序列化失败时不产生半截文件，
        # 下游按"文件存在"读取时不会拿到损坏报告
        content = json.dumps(report, indent=2, ensure_ascii=False)
        with open(json_file, "w", encoding="utf-8") as f:
            f.write(content)
        utils.print_info_log(f"Analysis info (json) is saved in {json_file}")
    except Exception as error:  # pylint: disable=broad-except
        # 旁路可失败：info.txt 已先行落盘，此处只记录不影响主流程。
        # 清理本次未完成的 info.json，避免残留半截产物。
        try:
            if os.path.exists(json_file):
                os.remove(json_file)
        except OSError:
            pass
        utils.print_error_log(f"Failed to write info.json: {error}")
