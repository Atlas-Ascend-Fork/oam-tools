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
clean.py — Ascend NPU 日志清洗脚本

保留日志原文、级别、重复记录、堆栈及文件内顺序。
--level 仅用于标记关注级别，不删除上下文；合并不跨主机排序。

用法：
  python3 clean.py --input <log_file> --output <output_file>
  python3 clean.py --input-dir <dir> --output-dir <out_dir>
  python3 clean.py --input <log_file> --level ERROR --output <output_file>
"""

import argparse
import re
import sys
from pathlib import Path
from datetime import datetime

# ===================== 配置 =====================
# 日志级别优先级（数值越小越详细）
LOG_LEVELS = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "WARN": 2, "ERROR": 3, "FATAL": 4}

# 噪声行模式：匹配后会被过滤（DEBUG 心跳、定时轮询）
NOISE_PATTERNS = [
    r"\[DEBUG\].*heartbeat",
    r"\[DEBUG\].*polling",
    r"\[DEBUG\].*tick",
    r"^\s*$",  # 空行
]

# 关键字：包含这些词的行即使是 DEBUG 也保留
IMPORTANT_KEYWORDS = [
    "error", "fail", "exception", "crash", "oom", "timeout",
    "retcode", "assert", "panic", "killed",
]

# 时间戳正则（多种格式兼容）
TS_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[.,]\d+)"),
    re.compile(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{2}:\d{2}:\d{2}[.,]\d+)"),
]
CANN_TS_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2})-(\d{2}:\d{2}:\d{2})[.,](\d{3})(?:[.,](\d{3}))?"
)


# ===================== 工具函数 =====================

def parse_log_level(line: str) -> str:
    """从日志行中提取日志级别"""
    for level in LOG_LEVELS:
        if f"[{level}]" in line.upper() or f" {level} " in line.upper():
            return level
    return "INFO"  # 默认视为 INFO


def extract_timestamp(line: str) -> datetime | None:
    """提取日志行中的时间戳"""
    cann_match = CANN_TS_PATTERN.search(line)
    if cann_match:
        date_part, time_part, millis, micros = cann_match.groups()
        fraction = millis + (micros or "")
        try:
            return datetime.strptime(
                f"{date_part} {time_part}.{fraction}",
                "%Y-%m-%d %H:%M:%S.%f",
            )
        except ValueError:
            pass

    for pattern in TS_PATTERNS:
        m = pattern.search(line)
        if m:
            ts_str = m.group(1)
            for fmt in [
                "%Y-%m-%d %H:%M:%S,%f",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%H:%M:%S,%f",
                "%H:%M:%S.%f",
            ]:
                try:
                    return datetime.strptime(ts_str, fmt)
                except ValueError:
                    continue
    return None


def is_noise(line: str) -> bool:
    """判断是否为噪声行"""
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            # 即使命中噪声，若包含重要关键字则保留
            if any(kw in line.lower() for kw in IMPORTANT_KEYWORDS):
                return False
            return True
    return False


def clean_lines(lines: list[str], min_level: str = "INFO") -> list[str]:
    """Return a lossless line view; level selection never discards evidence."""
    if min_level.upper() not in LOG_LEVELS:
        raise ValueError("Unknown focus level: " + min_level)
    return [line.rstrip("\n") for line in lines]


def merge_files(log_files: list[Path], output_path: Path) -> int:
    """Validate all inputs before creating an output, preserving local byte order."""
    if output_path.exists() or output_path.is_symlink():
        raise ValueError("Refusing to overwrite existing evidence: " + str(output_path))
    if any(path.resolve() == output_path.resolve() for path in log_files):
        raise ValueError("Input and output paths must differ")
    payloads = [path.read_bytes() for path in log_files]
    for payload in payloads:
        payload.decode("utf-8-sig", errors="strict")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as stream:
        previous = b""
        for payload in payloads:
            if payload and previous and not previous.endswith(b"\n"):
                stream.write(b"\n")
            stream.write(payload)
            if payload:
                previous = payload
    return sum(len(payload.splitlines()) for payload in payloads)


def process_file(input_path: Path, output_path: Path, min_level: str = "INFO") -> int:
    """处理单个日志文件，返回保留的行数"""
    if min_level.upper() not in LOG_LEVELS:
        raise ValueError("Unknown focus level: " + min_level)
    return merge_files([input_path], output_path)


# ===================== CLI =====================

def main():
    parser = argparse.ArgumentParser(
        description="Ascend NPU 日志清洗工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path, help="单个输入日志文件路径")
    group.add_argument("--input-dir", type=Path, help="批量输入目录（递归处理 *.log）")

    out_group = parser.add_mutually_exclusive_group()
    out_group.add_argument("--output", type=Path, help="单文件输出路径")
    out_group.add_argument("--output-dir", type=Path, help="批量输出目录")

    parser.add_argument(
        "--level",
        default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "FATAL"],
        help="关注级别（保留全部上下文，默认：DEBUG）",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="按文件名合并，保留各文件原始顺序（配合 --output 使用）",
    )

    args = parser.parse_args()

    total_kept = 0

    if args.input:
        # 单文件模式
        output_path = args.output or args.input.with_suffix(".clean.log")
        kept = process_file(args.input, output_path, args.level)
        print(f"[INFO] {args.input} → {output_path}（保留 {kept} 行）")
        total_kept = kept

    elif args.input_dir:
        # 批量模式
        log_files = sorted(args.input_dir.rglob("*.log"))
        if not log_files:
            print(f"[WARN] 在 {args.input_dir} 中未找到 .log 文件", file=sys.stderr)
            sys.exit(0)

        output_dir = args.output_dir or args.input_dir.parent / (args.input_dir.name + "_cleaned")

        if args.merge and args.output:
            total_kept = merge_files(log_files, args.output)
            print(f"[INFO] 合并完成 → {args.output}（保留 {total_kept} 行）")
        else:
            for log_file in log_files:
                rel = log_file.relative_to(args.input_dir)
                out_path = output_dir / rel.with_suffix(".clean.log")
                kept = process_file(log_file, out_path, args.level)
                print(f"[INFO] {log_file} → {out_path}（保留 {kept} 行）")
                total_kept += kept

    print(f"[DONE] 共保留 {total_kept} 行日志")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
