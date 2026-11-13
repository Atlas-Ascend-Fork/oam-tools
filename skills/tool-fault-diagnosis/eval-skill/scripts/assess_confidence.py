#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
assess_confidence.py — 诊断报告可信度评分工具

按 references/confidence-assessment.md 的五维模型对诊断结论打分，
并给出可信度等级和案例库入库判定（case_gate）。

用法：
  python3 assess_confidence.py --template > confidence.json
  python3 assess_confidence.py --input confidence.json
  python3 assess_confidence.py --input confidence.json --json > confidence_result.json
"""

import argparse
import json
import sys
from pathlib import Path

# ===================== 五维评分模型 =====================
# 每项：(键名, 分值, 说明)
DIMENSIONS = [
    (
        "D1",
        "证据完整性",
        25,
        [
            ("has_first_error_line", 8, "已定位并引用首报错原文"),
            ("has_env_version", 4, "CANN/Driver/Firmware/OS 版本已确认"),
            ("has_full_timeline", 5, "关键日志时间线完整无断档"),
            ("has_crash_artifacts", 5, "崩溃产物齐备（非崩溃场景填 true）"),
            ("has_repro_input", 3, "复现输入（命令行/shape/环境变量）已记录"),
        ],
    ),
    (
        "D2",
        "证据一致性",
        20,
        [
            ("multi_source_agree", 8, "≥2 个独立来源指向同一结论"),
            ("timeline_consistent", 6, "时间戳/PID/device 信息可跨来源对齐"),
            ("no_contradiction", 6, "无与结论冲突且未解释的证据"),
        ],
    ),
    (
        "D3",
        "因果链闭合性",
        25,
        [
            ("root_cause_localized", 8, "根因定位到算子/模块/file:line"),
            ("chain_no_gap", 9, "根因到现象每一跳都有证据"),
            ("alternatives_excluded", 8, "竞争假设已用证据排除"),
        ],
    ),
    (
        "D4",
        "复现与验证",
        15,
        [
            ("reproducible", 6, "有稳定复现步骤或必然触发条件"),
            ("fix_verified", 6, "按建议修复后问题消失并有记录"),
            ("regression_checked", 3, "修复后回归未再出现同类错误"),
        ],
    ),
    (
        "D5",
        "知识对齐",
        15,
        [
            ("errcode_documented", 5, "首报错错误码在 err-messages.md 有定义"),
            ("case_matched", 5, "在 cases.md 找到同类案例并说明异同"),
            ("source_code_confirmed", 5, "已通过源码证实推断"),
        ],
    ),
]

# 关键项：这些检查项直接决定结论能否被采信，未满足时不允许入库
# （不额外压分，分值已体现在各维度权重中）
CRITICAL_KEYS = [
    ("has_first_error_line", "首报错日志行已定位"),
    ("chain_no_gap", "因果链无跳跃"),
]

LEVELS = [
    (85, "HIGH", "高可信"),
    (70, "MEDIUM", "基本可信"),
    (50, "LOW", "存疑"),
    (0, "INSUFFICIENT", "证据不足"),
]


def build_template() -> dict:
    """生成空白检查表，所有检查项默认 false"""
    checks = {}
    for _, _, _, items in DIMENSIONS:
        for key, _, desc in items:
            checks[key] = {"value": False, "_desc": desc}
    return {
        "meta": {
            "report": "<诊断报告文件名>",
            "scenario": "<crash / aicore-error / oom / hang / perf / precision / other>",
            "first_error_code": "<ExxYYYY>",
            "cann_version": "<version>",
        },
        "checks": checks,
    }


def _flag(container: dict, key: str) -> bool:
    """兼容 {"key": true} 和 {"key": {"value": true}} 两种写法"""
    item = container.get(key, False)
    if isinstance(item, dict):
        return bool(item.get("value", False))
    return bool(item)


def score(data: dict) -> dict:
    checks = data.get("checks", {})

    dim_results = []
    total = 0
    missing = []

    for code, name, full, items in DIMENSIONS:
        earned = 0
        for key, points, desc in items:
            if _flag(checks, key):
                earned += points
            else:
                missing.append({"dimension": code, "key": key, "points": points, "desc": desc})
        total += earned
        dim_results.append(
            {"dimension": code, "name": name, "earned": earned, "full": full}
        )

    # 关键项未满足清单（不压分，仅作入库门槛）
    unmet_critical = [
        {"key": key, "desc": desc}
        for key, desc in CRITICAL_KEYS
        if not _flag(checks, key)
    ]

    level, level_cn = "INSUFFICIENT", "证据不足"
    for threshold, name, cn in LEVELS:
        if total >= threshold:
            level, level_cn = name, cn
            break

    # 入库判定
    gate, gate_reason = _gate(total, level, unmet_critical, checks)

    return {
        "final_score": total,
        "level": level,
        "level_cn": level_cn,
        "dimensions": dim_results,
        "unmet_critical": unmet_critical,
        "missing_items": sorted(missing, key=lambda x: -x["points"]),
        "case_gate": gate,
        "case_gate_reason": gate_reason,
        "meta": data.get("meta", {}),
    }


def _gate(total: int, level: str, unmet_critical: list, checks: dict) -> tuple[str, str]:
    """按 case-contribution.md §2 给出入库判定"""
    if unmet_critical:
        names = "、".join(u["desc"] for u in unmet_critical)
        return "reject", f"关键项未满足：{names}"

    if total < 70:
        return "reject", f"可信度 {total} < 70，证据不足以沉淀为案例"

    if level == "HIGH":
        if not _flag(checks, "root_cause_localized"):
            return "pending", "根因未定位到具体算子/模块，先进候选区"
        if not _flag(checks, "fix_verified"):
            return "pending", "修复未验证，先进候选区待验证后转正"
        return "accept", f"可信度 {total}（HIGH），可写入对应分类文件并同步 cases.md 索引"

    return "pending", f"可信度 {total}（{level}），进候选区待补证"


def render(result: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("诊断报告可信度评估")
    lines.append("=" * 60)

    meta = result.get("meta", {})
    if meta:
        for k in ("report", "scenario", "first_error_code", "cann_version"):
            if meta.get(k):
                lines.append(f"{k:<18}: {meta[k]}")
        lines.append("")

    lines.append(f"综合可信度: {result['final_score']}/100  [{result['level']} · {result['level_cn']}]")
    lines.append("")

    lines.append("维度得分:")
    for d in result["dimensions"]:
        bar_full = 20
        filled = int(round(d["earned"] / d["full"] * bar_full)) if d["full"] else 0
        bar = "█" * filled + "░" * (bar_full - filled)
        lines.append(f"  {d['dimension']} {d['name']:<8} {bar} {d['earned']:>2}/{d['full']}")
    lines.append("")

    if result["unmet_critical"]:
        lines.append("关键项未满足（阻止入库）:")
        for u in result["unmet_critical"]:
            lines.append(f"  ✗ {u['desc']}")
    else:
        lines.append("关键项: 全部满足")
    lines.append("")

    if result["missing_items"]:
        lines.append("未达标项（按影响排序，补齐可提分）:")
        for m in result["missing_items"][:8]:
            lines.append(f"  - [{m['dimension']}] {m['desc']}  (+{m['points']})")
        if len(result["missing_items"]) > 8:
            lines.append(f"  ... 另有 {len(result['missing_items']) - 8} 项")
        lines.append("")

    gate_mark = {"accept": "✓", "pending": "~", "reject": "✗"}[result["case_gate"]]
    lines.append(f"案例库入库判定: {gate_mark} {result['case_gate'].upper()}")
    lines.append(f"  理由: {result['case_gate_reason']}")

    action = {
        "accept": "执行 promote_case.py 写入对应分类文件并同步 cases.md 索引",
        "pending": "执行 promote_case.py 写入 cases-pending.md（PCASE 候选）",
        "reject": "先补齐缺失证据并重新评估，暂不入库",
    }[result["case_gate"]]
    lines.append(f"  下一步: {action}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="诊断报告可信度评分工具")
    parser.add_argument("--template", action="store_true", help="输出空白检查表 JSON")
    parser.add_argument("--input", type=Path, help="填写后的检查表 JSON")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 结果")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(build_template(), ensure_ascii=False, indent=2))
        return

    if not args.input:
        parser.error("需要 --input 或 --template")

    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except OSError as e:
        print(f"[ERROR] 无法读取 {args.input}: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    result = score(data)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result))


if __name__ == "__main__":
    main()
