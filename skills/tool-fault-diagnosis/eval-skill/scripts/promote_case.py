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
promote_case.py — 将高可信诊断报告沉淀到案例库

按 references/case-contribution.md 的门槛和格式，把诊断报告转换为规范案例块，
写入 cases.md（accept）或 cases-pending.md（pending）。

用法：
  python3 promote_case.py --report report.md --confidence confidence_result.json --dry-run
  python3 promote_case.py --report report.md --confidence confidence_result.json \
      --cases-dir eval-skill/references
  python3 promote_case.py --promote PCASE-001 --cases-dir eval-skill/references
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

CASES_FILE = "cases.md"
PENDING_FILE = "cases-pending.md"

PENDING_HEADER = """# 候选案例库（待补证）

> 可信度 70~84 或存在待补证据的诊断结论暂存于此，编号为 `PCASE-xxx`。
> 补齐证据并重新评估达到 HIGH（≥85）且关键项全部满足后，
> 用 `promote_case.py --promote PCASE-xxx` 转正到 [cases.md](cases.md)。
> 入库规范见 [case-contribution.md](case-contribution.md)。

---
"""

# 敏感信息模式：命中即中断，要求先脱敏
SENSITIVE_PATTERNS = [
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IP 地址"),
    (r"/home/(?!<)[A-Za-z0-9._-]+", "用户家目录绝对路径"),
    (r"(?i)\b(?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+", "凭据信息"),
    (r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "邮箱地址"),
    (r"(?i)\bssh-(?:rsa|ed25519)\s+\S+", "SSH 公钥"),
    (r"(?i)\b(?:Authorization|Bearer|Cookie|Session[_-]?Id)\s*[=:]\s*\S+", "认证信息"),
    (r"(?i)\bprivate[_-]?key\b|\.(?:pem|crt|key|p12|pfx)\b", "私钥或证书材料"),
    (r"(?i)\b(?:host|hostname|node|cluster|server|pod|rack)\s*[=:]\s*[A-Za-z][A-Za-z0-9._-]{2,}", "主机或集群标识"),
    (r"/root/[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+", "用户绝对路径"),
    (r"(?i)\b(?:model|dataset)(?:[_-](?:name|path|file))?\s*[=:]\s*(?!<)[\w./-]{4,}", "业务模型或数据集标识"),
]

# IP 白名单：文档中常见的示例/占位地址不算敏感
IP_ALLOW = {"0.0.0.0", "127.0.0.1", "255.255.255.255", "10.x.x.x", "1.2.3.4"}

# 报告章节 → 案例字段的抽取规则
SECTION_MAP = [
    ("problem", [r"问题摘要", r"问题描述", r"现象"]),
    ("log_feature", [r"关键证据链", r"关键日志", r"崩溃线程与堆栈", r"日志时间线", r"相关日志"]),
    ("root_cause", [r"根因分析", r"根本原因", r"直接触发点"]),
    ("solution", [r"修复建议", r"解决方案", r"建议修复方向", r"代码修复"]),
]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[ERROR] 无法读取 {path}: {e}", file=sys.stderr)
        sys.exit(1)


def split_sections(md: str) -> list[tuple[str, str]]:
    """把 markdown 拆成 (标题, 正文) 列表"""
    sections = []
    current_title = ""
    buf: list[str] = []
    in_fence = False

    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and re.match(r"^#{1,6}\s+", line):
            if current_title or buf:
                sections.append((current_title, "\n".join(buf).strip()))
            current_title = re.sub(r"^#{1,6}\s+", "", line).strip()
            buf = []
        else:
            buf.append(line)

    if current_title or buf:
        sections.append((current_title, "\n".join(buf).strip()))
    return sections


def extract_fields(md: str) -> dict:
    """从诊断报告抽取案例所需字段"""
    sections = split_sections(md)
    fields: dict[str, str] = {}

    for field, keywords in SECTION_MAP:
        for title, body in sections:
            if not body:
                continue
            if any(re.search(kw, title) for kw in keywords):
                fields.setdefault(field, body)
                break

    # 标题：优先取一级标题，否则取问题摘要首行
    title = ""
    for t, _ in sections:
        if t and not re.search(r"报告|模板|摘要", t):
            title = t
            break
    if not title:
        first = fields.get("problem", "").splitlines()
        title = first[0].strip("-• ") if first else "未命名问题"
    fields["title"] = re.sub(r"^[#\s]*", "", title).strip()[:80]

    return fields


def extract_log_block(text: str) -> str:
    """从正文中提取第一个代码块作为关键日志特征"""
    m = re.search(r"```[a-zA-Z]*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).rstrip()
    # 无代码块时取包含错误码或 ERROR 的行
    hits = [
        ln.strip()
        for ln in text.splitlines()
        if re.search(r"\bE[A-Z]\d{4}\b|ERROR|FATAL|SIG[A-Z]+", ln)
    ]
    return "\n".join(hits[:10])


def find_error_code(text: str) -> str:
    m = re.search(r"\b([EWI][A-Z]\d{4})\b", text)
    return m.group(1) if m else ""


def check_sensitive(text: str) -> list[tuple[str, str]]:
    """扫描敏感信息，返回 (类型, 命中片段) 列表"""
    found = []
    for pattern, label in SENSITIVE_PATTERNS:
        for m in re.finditer(pattern, text):
            hit = m.group(0)
            if label == "IP 地址":
                if hit in IP_ALLOW or hit.startswith("0."):
                    continue
                # 版本号形如 8.5.0.1 不算 IP（各段都是小数字，且首段 ≤ 9）
                octets = [int(x) for x in hit.split(".")]
                if octets[0] <= 9 and all(o <= 9 for o in octets[1:]):
                    continue
            if label == "用户家目录绝对路径" and "<user>" in hit:
                continue
            found.append((label, hit))
    return found


def scan_sensitive_lines(text: str):
    """Return line-numbered sensitive findings for read-only checks."""
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for label, hit in check_sensitive(line):
            findings.append((number, label, hit))
    return findings


def next_case_id(content: str, prefix: str) -> str:
    ids = [int(n) for n in re.findall(rf"{prefix}-(\d+)", content)]
    return f"{prefix}-{max(ids) + 1 if ids else 1:03d}"


def find_duplicate(content: str, error_code: str, title: str) -> str | None:
    """按错误码或标题关键词查找已有案例"""
    if error_code:
        for block in re.split(r"\n(?=## )", content):
            if error_code in block:
                m = re.search(r"## ((?:P?CASE)-\d+)[：:]?\s*(.*)", block)
                if m:
                    return f"{m.group(1)}（{m.group(2).strip()}）"
    keywords = [w for w in re.split(r"[\s，,、（）()]+", title) if len(w) >= 4][:3]
    for kw in keywords:
        for block in re.split(r"\n(?=## )", content):
            if kw in block:
                m = re.search(r"## ((?:P?CASE)-\d+)[：:]?\s*(.*)", block)
                if m:
                    return f"{m.group(1)}（{m.group(2).strip()}）— 关键词「{kw}」"
    return None


def build_case_block(case_id: str, fields: dict, conf: dict, report_name: str) -> str:
    meta = conf.get("meta", {})
    gate = conf.get("case_gate", "pending")
    error_code = meta.get("first_error_code") or fields.get("error_code") or "—"
    if error_code.startswith("<"):
        error_code = fields.get("error_code") or "—"
    cann = meta.get("cann_version", "—")
    if cann.startswith("<"):
        cann = "—"

    log_block = fields.get("log_block") or "<待补充关键日志原文>"
    problem = fields.get("problem") or "<待补充问题描述>"
    root_cause = fields.get("root_cause") or "<待补充根因>"
    solution = fields.get("solution") or "<待补充解决方案>"

    verify = "已验证修复有效" if gate == "accept" else "待验证"

    parts = [
        f"## {case_id}：{fields.get('title', '未命名问题')}",
        "",
        "**问题描述**",
        problem,
        "",
        "**关键日志特征**",
        "```",
        log_block,
        "```",
        "",
        "**根因分析**",
        root_cause,
        "",
        "**解决方案**",
        solution,
        "",
        "**元信息**",
        f"- 可信度：{conf.get('final_score', '—')}/100（{conf.get('level', '—')}）",
        f"- 环境：CANN {cann}",
        f"- 首报错错误码：{error_code}",
        f"- 验证状态：{verify}",
        f"- 来源报告：{report_name}",
        f"- 收录日期：{date.today().isoformat()}",
    ]

    if gate != "accept":
        missing = conf.get("missing_items", [])[:5]
        gaps = "；".join(m["desc"] for m in missing) or conf.get("case_gate_reason", "—")
        parts += [
            f"- 待补证据：{gaps}",
            "- 转正条件：补齐上述证据后重新评估达 HIGH（≥85）且关键项全部满足",
        ]

    return "\n".join(parts) + "\n"


def append_case(target: Path, block: str, header: str = "") -> None:
    if target.exists():
        content = target.read_text(encoding="utf-8").rstrip()
        new = content + "\n\n---\n\n" + block
    else:
        new = header.rstrip() + "\n\n" + block
    target.write_text(new, encoding="utf-8")


def do_promote(case_ref: str, cases_dir: Path, conf: dict | None = None) -> None:
    """把候选案例从 cases-pending.md 转正到 cases.md"""
    pending_path = cases_dir / PENDING_FILE
    cases_path = cases_dir / CASES_FILE

    if conf is not None and conf.get("case_gate") != "accept":
        print(
            f"[STOP] 重评结果为 {conf.get('case_gate', '?').upper()}"
            f"（{conf.get('final_score')}/100 {conf.get('level')}），未达转正门槛。",
            file=sys.stderr,
        )
        print(f"       理由：{conf.get('case_gate_reason', '')}", file=sys.stderr)
        sys.exit(2)

    if not pending_path.exists():
        print(f"[ERROR] 候选案例库不存在：{pending_path}", file=sys.stderr)
        sys.exit(1)

    pending = pending_path.read_text(encoding="utf-8")
    blocks = re.split(r"\n---\n", pending)
    target_block, rest = None, []
    for b in blocks:
        if re.search(rf"##\s+{re.escape(case_ref)}[：:]", b):
            target_block = b.strip()
        else:
            rest.append(b)

    if target_block is None:
        print(f"[ERROR] 在 {PENDING_FILE} 中未找到 {case_ref}", file=sys.stderr)
        sys.exit(1)

    cases_content = cases_path.read_text(encoding="utf-8") if cases_path.exists() else ""
    new_id = next_case_id(cases_content, "CASE")

    promoted = re.sub(rf"##\s+{re.escape(case_ref)}", f"## {new_id}", target_block, count=1)
    # 清理候选专属字段，更新验证状态
    promoted = "\n".join(
        ln for ln in promoted.splitlines()
        if not re.match(r"^- (待补证据|转正条件)[：:]", ln.strip())
    )
    promoted = re.sub(r"- 验证状态：.*", "- 验证状态：已验证修复有效", promoted)
    if conf is not None:
        promoted = re.sub(
            r"- 可信度：.*",
            f"- 可信度：{conf.get('final_score')}/100（{conf.get('level')}）",
            promoted,
        )
    promoted = promoted.rstrip() + f"\n- 转正日期：{date.today().isoformat()}（原 {case_ref}）\n"

    sensitive = check_sensitive(promoted)
    if sensitive:
        labels = ", ".join(sorted({label for label, _ in sensitive}))
        print(f"[STOP] 候选案例含疑似敏感信息（{labels}），请先脱敏后转正。", file=sys.stderr)
        sys.exit(3)

    append_case(cases_path, promoted)
    pending_path.write_text("\n---\n".join(b for b in rest).rstrip() + "\n", encoding="utf-8")
    print(f"[DONE] {case_ref} → {new_id}，已写入 {cases_path}")


def main():
    parser = argparse.ArgumentParser(description="诊断报告沉淀到案例库")
    parser.add_argument("--report", type=Path, help="诊断报告 markdown 文件")
    parser.add_argument("--confidence", type=Path, help="assess_confidence.py --json 的输出")
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references",
        help="案例库目录（默认 eval-skill/references）",
    )
    parser.add_argument(
        "--promote",
        metavar="PCASE-xxx",
        help="将候选案例转正到 cases.md（可配合 --confidence 传入重评结果）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印将写入的内容")
    parser.add_argument("--force", action="store_true", help="跳过重复案例提示，强制新增")
    parser.add_argument("--check", action="store_true", help="只读扫描文件中的敏感信息")
    parser.add_argument("--files", nargs="+", type=Path, help="配合 --check 指定待扫描文件")
    args = parser.parse_args()

    if args.check and args.promote:
        parser.error("--check 与 --promote 不能同时使用")

    if args.promote:
        conf = json.loads(read_text(args.confidence)) if args.confidence else None
        do_promote(args.promote, args.cases_dir, conf)
        return

    if args.check:
        if not args.files:
            parser.error("--check 需要至少一个 --files 文件")
        findings = 0
        for file_path in args.files:
            try:
                content = read_text(file_path)
            except SystemExit:
                raise
            for number, label, hit in scan_sensitive_lines(content):
                findings += 1
                print(f"[WARN] {file_path}:{number} {label}: {hit}", file=sys.stderr)
        if findings:
            print(f"[STOP] 检测到 {findings} 处疑似敏感信息，请人工确认后处理。", file=sys.stderr)
            sys.exit(10)
        print("[OK] 未检测到疑似敏感信息。")
        return

    if not args.report or not args.confidence:
        parser.error("需要 --report 和 --confidence，或使用 --promote")

    conf = json.loads(read_text(args.confidence))
    gate = conf.get("case_gate", "reject")
    reason = conf.get("case_gate_reason", "")

    print(
        f"[INFO] 可信度 {conf.get('final_score')}/100（{conf.get('level')}），入库判定：{gate.upper()}",
        flush=True,
    )
    print(f"[INFO] 理由：{reason}", flush=True)

    if gate == "reject":
        print("[STOP] 未达入库门槛，不写入案例库。请先补齐以下证据后重新评估：", file=sys.stderr)
        for m in conf.get("missing_items", [])[:6]:
            print(f"  - [{m['dimension']}] {m['desc']} (+{m['points']})", file=sys.stderr)
        sys.exit(2)

    report_md = read_text(args.report)
    fields = extract_fields(report_md)
    fields["log_block"] = extract_log_block(report_md)
    fields["error_code"] = find_error_code(report_md)

    is_accept = gate == "accept"
    target = args.cases_dir / (CASES_FILE if is_accept else PENDING_FILE)
    prefix = "CASE" if is_accept else "PCASE"

    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    case_id = next_case_id(existing, prefix)

    # 重复检索（accept 时同时查主库）
    dup_source = existing
    if not is_accept:
        main_cases = args.cases_dir / CASES_FILE
        if main_cases.exists():
            dup_source += "\n" + main_cases.read_text(encoding="utf-8")
    dup = find_duplicate(dup_source, fields.get("error_code", ""), fields.get("title", ""))
    if dup and not args.force:
        print(f"[WARN] 疑似重复案例：{dup}", file=sys.stderr)
        print("[WARN] 按 case-contribution.md §4 优先合并到已有案例；", file=sys.stderr)
        print("       确认为不同根因时用 --force 强制新增。", file=sys.stderr)
        sys.exit(4)

    # 脱敏检查必须覆盖最终写入正文，包括元信息和日志块。
    block = build_case_block(case_id, fields, conf, args.report.name)
    sensitive = check_sensitive(block)
    if sensitive:
        print("[STOP] 检测到敏感信息，请先脱敏后重试：", file=sys.stderr)
        seen = set()
        for label, hit in sensitive:
            if (label, hit) in seen:
                continue
            seen.add((label, hit))
            print(f"  - {label}: {hit}", file=sys.stderr)
        sys.exit(3)

    if args.dry_run:
        print(f"\n[DRY-RUN] 目标文件：{target}")
        print("-" * 60)
        print(block)
        print("-" * 60)
        return

    append_case(target, block, PENDING_HEADER if not is_accept else "# 常见问题案例库\n")
    print(f"[DONE] {case_id} 已写入 {target}")
    if not is_accept:
        print(f"[NEXT] 补齐证据后执行：promote_case.py --promote {case_id}")


if __name__ == "__main__":
    main()
