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
"""
info.json 结构化报告构建（json_report_builder）的单元测试。
覆盖 SRS FR-AJR-001~005：报告生成、空值语义、args 语义化、根因映射、路径规范。
"""

import json


from ms_interface import json_report_builder as jrb
from ms_interface.aic_error_info import AicErrorInfo, CONCLUSION_TEXT
from ms_interface.constant import Constant, RetCode

MILAN_EXTRA_INFO = (
    "extra info:\n"
    "VEC_ERR_INFO=0x51000070f7\n"
    "MTE_ERR_INFO=0xb90000006a\n"
    "IFU_ERR_INFO=0x29883d2080000\n"
    "CCU_ERR_INFO=0xc791c207288000f7\n"
)


def _make_info(**overrides):
    info = AicErrorInfo()
    info.aic_error_info = {
        "err_time": "2025-04-02-07:19:26.376.879",
        "dev_id": "0",
        "core_id": "15",
        "error_code": "0x200000000",
        "start_pc": "0x12c0c002e000",
        "current_pc": "0x12c0c002e5e8",
        "extra_info": MILAN_EXTRA_INFO,
    }
    info.extra_info = MILAN_EXTRA_INFO
    info.kernel_name = "AddCustom_test_0"
    info.task_id = "0"
    info.stream_id = "2"
    info.node_name = "exception_info.2.0"
    for key, value in overrides.items():
        setattr(info, key, value)
    return info


# ---------------- FR-AJR-002 空值语义 ----------------


def test_num_sentinel_to_not_collected(tmp_path):
    info = _make_info(rts_block_dim=-1, driver_aicore_num=-1)
    report = jrb.build_report(info, str(tmp_path))
    assert report["basic_info"]["rts_block_dim"] == "not_collected"
    assert report["basic_info"]["driver_aicore_num"] == "not_collected"


def test_num_normal_value_kept(tmp_path):
    info = _make_info(rts_block_dim=8, driver_aicore_num=40)
    report = jrb.build_report(info, str(tmp_path))
    assert report["basic_info"]["rts_block_dim"] == 8
    assert report["basic_info"]["driver_aicore_num"] == 40


def test_missing_file_to_not_collected(tmp_path):
    info = _make_info(
        cce_file=str(tmp_path / "no_such.cce"),
        json_file="",
    )
    report = jrb.build_report(info, str(tmp_path))
    assert report["basic_info"]["cce_file"] == "not_collected"
    assert report["basic_info"]["json_file"] == "not_collected"


def test_scene_not_applicable_null(tmp_path):
    info = _make_info()  # corrected_pc 为空 dict、graph_file 未命中
    report = jrb.build_report(info, str(tmp_path))
    assert report["basic_info"]["graph_file"] is None
    assert report["op_in_graph"] is None
    assert report["dump_info"]["exception_dump_file"] is None


def test_collected_empty_value(tmp_path):
    info = _make_info(single_op_mem_monitor="")
    report = jrb.build_report(info, str(tmp_path))
    assert report["single_op_test"]["memory_status"] == ""


def test_args_not_collected(tmp_path):
    info = _make_info(args_before_list=[], args_after_list=[])
    report = jrb.build_report(info, str(tmp_path))
    assert report["args"]["before_execute"] == "not_collected"
    assert report["args"]["after_execute"] == "not_collected"


def _iter_values(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _iter_values(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_values(value)
    else:
        yield node


def test_no_out_of_spec_empty_marker(tmp_path):
    """全报告扫描：空值仅允许 null / not_collected / "" / []。"""
    bad_markers = ["N/A", "None", "unknown/0"]
    info = _make_info(single_op_test_result=RetCode.NOT_RUN)
    report = jrb.build_report(info, str(tmp_path))
    for value in _iter_values(report):
        if isinstance(value, str):
            assert value not in bad_markers
            assert value != "-1"


# ---------------- FR-AJR-003 args 语义化 ----------------


def test_args_type_by_marks(tmp_path):
    info = _make_info(
        args_after_list=[
            0x12C0C0013000,
            0x12C0C001C000,
            0x12C0C0025000,
            0,
            0x12C100010038,
        ],
        args_type_marks={
            0: "input",
            1: "input",
            2: "output",
            3: "workspace",
            4: "tiling_data",
        },
    )
    report = jrb.build_report(info, str(tmp_path))
    args = report["args"]["after_execute"]
    assert [a["arg_type"] for a in args] == [
        "input",
        "input",
        "output",
        "workspace",
        "tiling_data",
    ]
    assert args[0]["address"] == "0x12c0c0013000"
    # workspace/tiling_data 的 dtype/shape 不适用为 null
    assert args[3]["dtype"] is None and args[3]["shape"] is None
    assert args[4]["dtype"] is None and args[4]["shape"] is None


def test_args_meta_backfill(tmp_path):
    info = _make_info(
        args_after_list=[0x1000, 0x2000],
        args_type_marks={0: "input", 1: "output"},
        dump_tensor_meta=[
            {
                "parse_type": "input",
                "index": 0,
                "dtype": "float16",
                "shape": [8, 2048],
                "size": 32768,
                "file": str(tmp_path / "in.npy"),
                "data_stats": [
                    {
                        "Possible_dtype": "float16",
                        "summary": {"max": 1.0, "min": 0.0, "mean": 0.5, "std": 0.1},
                    }
                ],
            },
            {
                "parse_type": "output",
                "index": 1,
                "dtype": "float16",
                "shape": [8, 2048],
                "size": 32768,
                "file": str(tmp_path / "out.npy"),
                "data_stats": [],
            },
        ],
    )
    report = jrb.build_report(info, str(tmp_path))
    arg0 = report["args"]["after_execute"][0]
    assert arg0["dtype"] == "float16"
    # shape 单行展示
    assert arg0["shape"] == "[8, 2048]"
    assert arg0["size_bytes"] == 32768
    # dump_info.files 与 args 对齐：file/arg_index/data_stats
    files = report["dump_info"]["files"]
    assert files[0]["arg_index"] == 0
    assert files[0]["data_stats"][0]["Possible_dtype"] == "float16"
    assert files[0]["data_stats"][0]["summary"]["max"] == 1.0
    assert files[1]["arg_index"] == 1
    assert files[1]["data_stats"] == []
    # dump_info.files 不再输出 shape/dtype 字段
    assert "shape" not in files[0]
    assert "dtype" not in files[0]


def test_dump_files_arg_index_global_semantics(tmp_path):
    """dump 内部序号换算为全局 args 序号，两套语义不再撞号（检视意见）。"""
    info = _make_info(
        args_after_list=[0x1000, 0x2000, 0x3000],
        args_type_marks={0: "input", 1: "input", 2: "output"},
        # output 的 dump 内部序号为 0（无 arg_index），args 全局下标为 2
        kernel_io_counts=(2, 1),
        dump_tensor_meta=[
            {
                "parse_type": "input",
                "index": 0,
                "dtype": "float16",
                "shape": [8],
                "size": 16,
                "file": str(tmp_path / "a.npy"),
                "data_stats": [],
            },
            {
                "parse_type": "output",
                "index": 0,
                "dtype": "float16",
                "shape": [4],
                "size": 8,
                "file": str(tmp_path / "b.npy"),
                "data_stats": [],
            },
        ],
    )
    report = jrb.build_report(info, str(tmp_path))
    files = report["dump_info"]["files"]
    # output 内部序号 0 + num_inputs 2 = 全局序号 2，与 args[].arg_index 一致
    assert [f["arg_index"] for f in files] == [0, 2]
    assert report["args"]["after_execute"][2]["arg_index"] == 2


def test_args_by_kernel_json_counts(tmp_path):
    # 无 plog 标记，仅 json 推算：inputs=2/outputs=1
    kernel_json = tmp_path / "kernel.json"
    kernel_json.write_text(
        json.dumps({"supportInfo": {"inputs": [{}, {}], "outputs": [{}]}})
    )
    info = _make_info(
        json_file=str(kernel_json),
        args_after_list=[0x1000, 0x2000, 0x3000, 0x4000],
    )
    report = jrb.build_report(info, str(tmp_path))
    types = [a["arg_type"] for a in report["args"]["after_execute"]]
    assert types == ["input", "input", "output", "other"]


def test_args_ffts_shape(tmp_path):
    info = _make_info(
        args_after_list=[0x1000, 0x2000, 0x3000, 0x4000],
        ffts_addrs_num=2,
    )
    report = jrb.build_report(info, str(tmp_path))
    args = report["args"]["after_execute"]
    assert args[-1]["arg_type"] == "shape"
    assert args[-2]["arg_type"] == "shape"


def test_args_degrade_to_other(tmp_path):
    info = _make_info(args_after_list=[0x1000, 0x2000])
    report = jrb.build_report(info, str(tmp_path))
    assert all(a["arg_type"] == "other" for a in report["args"]["after_execute"])
    assert all(a["dtype"] is None for a in report["args"]["after_execute"])


# ---------------- FR-AJR-004 根因映射 ----------------


def test_root_cause_summary_from_error_code_desc(tmp_path):
    """summary 输出 AIC_ERROR_INFO_DICT 登记的 desc。"""
    info = _make_info()
    report = jrb.build_report(info, str(tmp_path))
    root = report["root_cause"]
    # 0x200000000 命中位 33：mte_gdma_write_overflow
    expected = Constant.AIC_ERROR_INFO_DICT[33].split(",", 1)[1].strip()
    assert root["summary"] == expected
    # 证据首条指出 summary 来源
    first = root["evidence"][0]
    assert first["field"] == "aic_error.groups[0].error_code"
    assert first["value"] == "0x200000000"
    assert "AIC_ERROR_INFO_DICT" in first["interpretation"]


def test_root_cause_summary_fallback_to_conclusion(tmp_path):
    """错误码无法登记 desc 时退回结论文本。"""
    info = _make_info()
    info.aic_error_info["error_code"] = ""
    info.single_op_test_result = RetCode.FAILED
    report = jrb.build_report(info, str(tmp_path))
    assert report["root_cause"]["summary"] == CONCLUSION_TEXT["single_op_reproduced"]


def test_root_cause_structure(tmp_path):
    info = _make_info(single_op_test_result=RetCode.FAILED)
    report = jrb.build_report(info, str(tmp_path))
    root = report["root_cause"]
    assert root["summary"]
    assert root["evidence"] and root["evidence"][0]["field"]
    assert root["action_items"]
    assert all("action" in a and "purpose" in a for a in root["action_items"])
    # 字段顺序 action → target（可选）→ purpose
    for action in root["action_items"]:
        keys = list(action.keys())
        assert keys[0] == "action"
        assert keys[-1] == "purpose"
        if "target" in action:
            assert keys == ["action", "target", "purpose"]


def test_action_items_field_order_with_target(tmp_path):
    """含 target 的 action：顺序为 action → target → purpose。"""
    info = _make_info(atomic_clean_check=False)
    # graph_file 存在时 target 才输出
    graph = tmp_path / "ge_proto.txt"
    graph.write_text("")
    info.graph_file = str(graph)
    report = jrb.build_report(info, str(tmp_path))
    with_target = [a for a in report["root_cause"]["action_items"] if "target" in a]
    assert with_target
    for action in with_target:
        assert list(action.keys()) == ["action", "target", "purpose"]


def test_root_cause_atomic_clean_branch(tmp_path):
    info = _make_info(atomic_clean_check=False)
    report = jrb.build_report(info, str(tmp_path))
    root = report["root_cause"]
    assert any("memset" in a["action"] for a in root["action_items"])


def test_root_cause_args_mismatch_branch(tmp_path):
    info = _make_info(check_args_result=False)
    report = jrb.build_report(info, str(tmp_path))
    assert any(
        "memory error detection" in a["action"].lower()
        for a in report["root_cause"]["action_items"]
    )


def test_root_cause_not_reproduced_multi_actions(tmp_path):
    info = _make_info(single_op_test_result=RetCode.SUCCESS, single_op_attempted=True)
    report = jrb.build_report(info, str(tmp_path))
    assert len(report["root_cause"]["action_items"]) >= 2


def test_root_cause_env_error_branch(tmp_path):
    # env_check_attempted=True 表示环境检查已执行且失败
    info = _make_info(env_available=False, env_check_attempted=True)
    report = jrb.build_report(info, str(tmp_path))
    assert report["env_check"]["result"] == "failed"


def test_single_op_not_run_conclusion_keeps_log_path(tmp_path):
    """info.txt 回归：single_op_not_run 结论保留单算子日志路径（问题1）。"""
    log_path = str(tmp_path / "single_op_20260101")
    info = AicErrorInfo()
    info.single_op_attempted = True
    info.single_op_test_result = RetCode.NOT_RUN
    info.single_op_log_path = log_path
    conclusion = info.get_conclusion()
    assert log_path in conclusion
    assert "check the single-operator log in" in conclusion


def test_normal_mark_degrades_to_other(tmp_path):
    """normal 标记在 json 缺失场景降级为 other，不输出非法枚举（问题2）。"""
    info = _make_info(
        args_after_list=[0x1000, 0x2000],
        args_type_marks={0: "normal", 1: "workspace"},
        # json 缺失：kernel_io_counts 未缓存且 json_file 为空
        json_file="",
    )
    report = jrb.build_report(info, str(tmp_path))
    types = [a["arg_type"] for a in report["args"]["after_execute"]]
    assert types == ["other", "workspace"]


def test_output_meta_backfill_without_arg_index(tmp_path):
    """output dump 元数据无 arg_index 时按内部序号换算回填（问题4）。"""
    info = _make_info(
        args_after_list=[0x1000, 0x2000, 0x3000],
        args_type_marks={0: "input", 1: "input", 2: "output"},
        # output 的 dump 内部序号为 0（无 arg_index 场景），全局下标为 2
        dump_tensor_meta=[
            {
                "parse_type": "input",
                "index": 0,
                "dtype": "float16",
                "shape": [8],
                "size": 16,
                "file": str(tmp_path / "a.npy"),
                "data_stats": [],
            },
            {
                "parse_type": "output",
                "index": 0,
                "dtype": "float16",
                "shape": [4],
                "size": 8,
                "file": str(tmp_path / "b.npy"),
                "data_stats": [],
            },
        ],
        kernel_io_counts=(2, 1),
    )
    report = jrb.build_report(info, str(tmp_path))
    args = report["args"]["after_execute"]
    assert args[2]["arg_type"] == "output"
    assert args[2]["dtype"] == "float16"
    assert args[2]["shape"] == "[4]"
    assert args[2]["size_bytes"] == 8


def test_env_check_not_attempted(tmp_path):
    """环境检查被跳过（Step 10 异常）时输出 not_collected，不误报 success。"""
    info = _make_info()  # env_check_attempted 默认 False，env_available 默认 True
    report = jrb.build_report(info, str(tmp_path))
    assert report["env_check"]["result"] == "not_collected"
    assert "skipped" in report["env_check"]["detail"]


def test_env_check_not_attempted_collect_failed(tmp_path):
    """采集失败路径（未走到 Step 10）detail 留空，不把原因错归到样例算子。"""
    info = _make_info()
    report = jrb.build_report(info, str(tmp_path), collect_succ=False)
    assert report["env_check"]["result"] == "not_collected"
    assert report["env_check"]["detail"] == ""


def test_summary_stat_entry_json_safe():
    """complex 与 nan/inf 统计值转字符串，保证可被严格 JSON 序列化。"""
    import numpy as np

    from ms_interface.dump_data_parser import DumpDataParser

    # complex 标量
    entry = DumpDataParser._summary_stat_entry("complex64", np.array([1 + 2j]))
    assert isinstance(entry["summary"]["max"], str)
    assert json.dumps({"data_stats": [entry]})  # 不抛 TypeError

    # nan/inf
    entry2 = DumpDataParser._summary_stat_entry(
        "float32", np.array([float("nan"), 1.0])
    )
    text = json.dumps({"data_stats": [entry2]}, allow_nan=False)
    assert "NaN" not in text and "Infinity" not in text


def test_write_json_report_no_partial_file(tmp_path):
    """序列化失败时不残留半截 info.json（检视意见：严重）。"""
    info = _make_info()
    # 注入无法序列化的统计值触发 dumps 失败
    info.dump_tensor_meta = [
        {
            "parse_type": "input",
            "index": 0,
            "dtype": "complex64",
            "shape": [2],
            "size": 16,
            "file": str(tmp_path / "a.npy"),
            "data_stats": [{"Possible_dtype": "complex64", "summary": {"max": 1 + 2j}}],
        }
    ]
    err_dir = tmp_path / "aicerror_0"
    err_dir.mkdir()
    jrb.write_json_report(str(err_dir), info, str(tmp_path))
    assert not (err_dir / "info.json").exists()


def test_load_kernel_io_counts_non_dict_json(tmp_path):
    """非 dict 根/非 dict supportInfo 的 kernel json 不中断，退化为未取到。"""

    from ms_interface.aicore_error_parser import _load_kernel_io_counts

    kj = tmp_path / "kernel.json"
    for content in ("[1, 2, 3]", '{"supportInfo": [1, 2]}'):
        kj.write_text(content)
        info = AicErrorInfo()
        info.json_file = str(kj)
        _load_kernel_io_counts(info)  # 不应抛异常
        assert info.kernel_io_counts == (None, None)


def test_root_cause_fallback_branch(tmp_path):
    info = _make_info()  # 全分支不命中
    info.aic_error_info["error_code"] = ""
    report = jrb.build_report(info, str(tmp_path))
    root = report["root_cause"]
    assert root["summary"]  # 兜底文本非空
    assert root["action_items"] == []


def test_conclusion_branches_all_mapped():
    """映射表分支与 match_conclusion_branch 全分支一一对应。"""
    cases = [
        ("atomic_clean_missing", {"atomic_clean_check": False}),
        ("flag_mismatch", {"flag_check": "please check"}),
        ("core_num_insufficient", {"rts_block_dim": 100, "driver_aicore_num": 40}),
        ("pc_zero", {"_patch": ("aic_error_info", "current_pc", "0x0")}),
        ("atomic_overflow", {"atomic_add_err": True}),
        ("data_invalid", {"dump_info": "data invalid"}),
        ("single_op_reproduced", {"single_op_test_result": RetCode.FAILED}),
        ("args_mismatch", {"check_args_result": False}),
        ("addr_invalid", {"addr_valid": False}),
        ("env_error", {"env_available": False}),
        # single_op_not_run 在分支序中先于 single_op_not_reproduced，
        # 但单算子 SUCCESS 场景必须先构造 NOT_RUN 才能走 not_run 分支
        (
            "single_op_not_run",
            {"single_op_attempted": True, "single_op_test_result": RetCode.NOT_RUN},
        ),
        ("single_op_not_reproduced", {"single_op_test_result": RetCode.SUCCESS}),
    ]
    seen = set()
    for expected, overrides in cases:
        info = AicErrorInfo()
        patch = overrides.pop("_patch", None)
        for key, value in overrides.items():
            setattr(info, key, value)
        if patch:
            field, key, value = patch
            getattr(info, field)[key] = value
        branch = info.match_conclusion_branch()
        assert branch == expected, f"expected {expected}, got {branch}"
        seen.add(branch)
        # 每个结论分支都有映射：summary 文本与 action 模板
        if branch != "single_op_not_run":
            assert CONCLUSION_TEXT[branch]
        assert branch in jrb._CONCLUSION_ACTIONS
    assert seen == set(CONCLUSION_TEXT.keys())


# ---------------- FR-AJR-005 路径规范 ----------------


def test_paths_relative_to_collection_dir(tmp_path):
    collection = tmp_path / "info_x" / "collection"
    compile_dir = collection / "compile"
    compile_dir.mkdir(parents=True)
    kernel = compile_dir / "kernel.o"
    kernel.write_text("")
    info = _make_info(bin_file=str(kernel))
    report = jrb.build_report(info, str(tmp_path / "info_x"))
    assert report["collection_dir"] == str(collection)
    assert report["basic_info"]["kernel_file"] == "compile/kernel.o"
    assert "\\" not in report["basic_info"]["kernel_file"]


def test_path_outside_collection(tmp_path):
    collection = tmp_path / "info_x" / "collection"
    collection.mkdir(parents=True)
    outside = tmp_path / "info_x" / "aicerror_0" / "log.txt"
    outside.parent.mkdir(parents=True)
    outside.write_text("")
    info = _make_info(single_op_log_path=str(outside))
    report = jrb.build_report(info, str(tmp_path / "info_x"))
    assert report["single_op_test"]["log_path"].startswith("../")


def test_exception_dump_file_relative(tmp_path):
    collection = tmp_path / "info_x" / "collection"
    dump_dir = collection / "dump"
    dump_dir.mkdir(parents=True)
    dump_file = dump_dir / "exception_info.2.0.20250402071926393"
    dump_file.write_text("")
    info = _make_info(dump_file=[str(dump_file)])
    report = jrb.build_report(info, str(tmp_path / "info_x"))
    assert report["dump_info"]["exception_dump_file"] == (
        "dump/exception_info.2.0.20250402071926393"
    )


def test_relpath_failure_fallback(tmp_path):
    # 路径不存在时走 not_collected / 空串，不抛异常
    info = _make_info(tiling_data="/no/such/dir/x_tiling.bin")
    report = jrb.build_report(info, str(tmp_path))
    assert report["dump_info"]["tiling_data"] == "not_collected"


# ---------------- FR-AJR-001 报告生成 ----------------


def test_build_report_top_level(tmp_path):
    info = _make_info()
    report = jrb.build_report(info, str(tmp_path))
    for key in (
        "report_version",
        "report_type",
        "analysis_result",
        "collection_dir",
        "generated_at",
        "root_cause",
        "basic_info",
        "aic_error",
        "instructions",
        "args",
        "dump_info",
        "single_op_test",
        "env_check",
        "op_in_graph",
    ):
        assert key in report
    assert report["analysis_result"] == "success"
    assert report["report_type"] == "aicore_error_analysis"


def test_build_report_collect_failed(tmp_path):
    info = _make_info()
    report = jrb.build_report(info, str(tmp_path), collect_succ=False)
    assert report["analysis_result"] == "failed"


def test_write_json_report_and_failure_bypass(tmp_path, mocker):
    info = _make_info()
    err_dir = tmp_path / "aicerror_0"
    err_dir.mkdir()
    jrb.write_json_report(str(err_dir), info, str(tmp_path))
    out = err_dir / "info.json"
    assert out.exists()
    with open(out, "r", encoding="utf-8") as f:
        assert json.load(f)["report_type"] == "aicore_error_analysis"

    # 写失败旁路：不抛异常、只告警
    real_open = open

    def fake_open(file, mode="r", *args, **kwargs):
        if str(file).endswith("info.json") and "w" in mode:
            raise OSError("disk full")
        return real_open(file, mode, *args, **kwargs)

    mocker.patch("builtins.open", side_effect=fake_open)
    jrb.write_json_report(str(err_dir), info, str(tmp_path))  # 不应抛异常


def test_910b_registers_structured(tmp_path):
    info = _make_info()
    report = jrb.build_report(info, str(tmp_path))
    group = report["aic_error"]["groups"][0]
    # chip_type / error_bits 字段均已删除
    assert "chip_type" not in group
    assert "error_bits" not in group
    regs = group["registers"]
    assert "vec" in regs and regs["vec"]["bits"] == "[28:16]"
    assert regs["vec"]["meaning"] == "VEC Error Address [17:5]"
    assert regs["ifu"]["approximate"].startswith("0x")


def test_950_registers_empty(tmp_path):
    info = _make_info()
    info.aic_error_info["error_code"] = "12, 34"
    info.aic_error_groups = []
    report = jrb.build_report(info, str(tmp_path))
    group = report["aic_error"]["groups"][0]
    # 950 风格错误码无 910B 寄存器位段
    assert group["registers"] == {}
    assert "chip_type" not in group
    assert "error_bits" not in group


def test_multi_group_cores(tmp_path):
    info = _make_info()
    info.aic_error_groups = [
        (
            "0x200000000",
            {
                "records": [{**info.aic_error_info, "core_id": "1"}],
                "cores_aic": ["1"],
                "cores_aiv": [],
            },
        ),
        (
            "0x200000000",
            {
                "records": [{**info.aic_error_info, "core_id": "15"}],
                "cores_aic": [],
                "cores_aiv": ["15", "16"],
            },
        ),
    ]
    report = jrb.build_report(info, str(tmp_path))
    groups = report["aic_error"]["groups"]
    assert len(groups) == 2
    assert groups[0]["cores_aic"] == ["1"]
    assert groups[1]["cores_aiv"] == ["15", "16"]


def test_instructions_original_section(tmp_path):
    info = _make_info()
    info.instr = "\nError occurred most likely at line: 0x5e8\n\n"
    report = jrb.build_report(info, str(tmp_path))
    ins = report["instructions"]
    # original 含 start_pc/current_pc/likely_error_line
    assert ins["original"]["start_pc"] == "0x12c0c002e000"
    assert ins["original"]["current_pc"] == "0x12c0c002e5e8"
    assert ins["original"]["likely_error_line"] == 0x5E8
    # 顶层不再平铺这些字段，instruction 字段已删除
    assert "start_pc" not in ins
    assert "instruction" not in ins


def test_instructions_corrected_section(tmp_path):
    info = _make_info()
    info.corrected_pc = {"start_pc": "0xa", "current_pc": "0xb", "offset": 0x5E8}
    info.corrected_instr = (
        "Error occurred most likely at line: 0x5e8\n"
        "outerSrc: /src/op.py:120:5\n"
        "innerSrc: /src/kernel.cce:45:9\n"
    )
    report = jrb.build_report(info, str(tmp_path))
    ins = report["instructions"]
    # corrected 含 start_pc/current_pc/likely_error_line/src_locations
    assert ins["corrected"]["start_pc"] == "0xa"
    assert ins["corrected"]["current_pc"] == "0xb"
    assert ins["corrected"]["likely_error_line"] == 0x5E8
    assert ins["corrected"]["src_locations"] == [
        "/src/op.py:120:5",
        "/src/kernel.cce:45:9",
    ]
    # notice 与 original/corrected 平级
    assert "corrected PC" in ins["notice"]


def test_instructions_src_not_parsed(tmp_path):
    info = _make_info()
    info.instr = "Error occurred most likely at line: 0x10\n"
    report = jrb.build_report(info, str(tmp_path))
    ins = report["instructions"]
    # 无修正时 corrected 为 null、notice 为 null
    assert ins["corrected"] is None
    assert ins["notice"] is None
    # original 无法解析行号/无 src 时按空值语义
    assert ins["original"]["likely_error_line"] == 0x10


def test_single_op_section(tmp_path):
    info = _make_info(
        single_op_test_result=RetCode.FAILED,
        single_op_attempted=True,
        single_op_mem_monitor="Access Memory without OverBoundary",
    )
    report = jrb.build_report(info, str(tmp_path))
    section = report["single_op_test"]
    assert section["result"] == "Aicore Error"
    assert "reproduced" in section["execute_info"]
    assert section["memory_status"] == "Access Memory without OverBoundary"

    # SUCCESS → Execute Success；NOT_RUN → Execute Failed
    info2 = _make_info(single_op_test_result=RetCode.SUCCESS)
    report2 = jrb.build_report(info2, str(tmp_path))
    assert report2["single_op_test"]["result"] == "Execute Success"

    info3 = _make_info(single_op_test_result=RetCode.NOT_RUN)
    report3 = jrb.build_report(info3, str(tmp_path))
    # attempted=False：用例根本没跑，输出 Not Run（跑过但失败才是 Execute Failed）
    assert report3["single_op_test"]["result"] == "Not Run"

    # attempted=True + NOT_RUN：跑了但执行失败
    info4 = _make_info(single_op_test_result=RetCode.NOT_RUN, single_op_attempted=True)
    report4 = jrb.build_report(info4, str(tmp_path))
    assert report4["single_op_test"]["result"] == "Execute Failed"


def test_instructions_corrected_notice(tmp_path):
    """notice 与 original/corrected 平级；未修正时为 null。"""
    info = _make_info()
    info.corrected_pc = {"start_pc": "0xa", "current_pc": "0xb", "offset": 0x5E8}
    report = jrb.build_report(info, str(tmp_path))
    assert "corrected PC" in report["instructions"]["notice"]

    info2 = _make_info()  # 无修正
    report2 = jrb.build_report(info2, str(tmp_path))
    assert report2["instructions"]["notice"] is None


def test_build_report_no_kernel_json_read(tmp_path, mocker):
    """解析阶段已缓存 kernel_io_counts 时，构建阶段不读 kernel json（问题7）。"""
    kernel_json = tmp_path / "kernel.json"
    kernel_json.write_text(
        json.dumps({"supportInfo": {"inputs": [{}, {}], "outputs": [{}]}})
    )
    info = _make_info(
        json_file=str(kernel_json),
        args_after_list=[0x1000, 0x2000, 0x3000],
        kernel_io_counts=(2, 1),
    )
    real_open = open

    def spy_open(file, mode="r", *args, **kwargs):
        if str(file).endswith("kernel.json"):
            raise AssertionError("build_report must not read kernel json when cached")
        return real_open(file, mode, *args, **kwargs)

    mocker.patch("builtins.open", side_effect=spy_open)
    report = jrb.build_report(info, str(tmp_path))
    types = [a["arg_type"] for a in report["args"]["after_execute"]]
    assert types == ["input", "input", "output"]


def test_dump_info_no_tiling_views(tmp_path):
    info = _make_info(tiling_data="")
    report = jrb.build_report(info, str(tmp_path))
    assert "tiling_data_views" not in report["dump_info"]
    assert report["dump_info"]["files"] == []
