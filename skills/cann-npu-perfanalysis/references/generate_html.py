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
NPU 性能分析 HTML 报告生成器

用法：
    python3 generate_html.py <analysis_data.json> <output.html>

analysis_data.json 由 Claude 在完成分析后写出，本脚本负责将其渲染为美观的 HTML 报告。
"""

import json
import html
import logging
import sys
import argparse
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── 优先级颜色映射 ────────────────────────────────────────────────────────────
PRIORITY_COLOR = {
    'P0': ('#e74c3c', '#fff'),
    'P1': ('#e67e22', '#fff'),
    'P2': ('#f1c40f', '#333'),
    'P3': ('#3498db', '#fff'),
    'OK': ('#2ecc71', '#333'),
}
CARD_BORDER = {
    'P0': '#e74c3c', 'P1': '#e67e22', 'P2': '#f1c40f',
    'P3': '#3498db', 'OK': '#2ecc71', 'INFO': '#95a5a6',
}


def badge(label, priority=None):
    if priority and priority in PRIORITY_COLOR:
        bg, fg = PRIORITY_COLOR[priority]
    else:
        bg, fg = '#95a5a6', '#fff'
    return (f'<span style="background:{bg};color:{fg};padding:2px 8px;'
            f'border-radius:12px;font-size:11px;font-weight:700">{html.escape(str(label))}</span>')


def progress_bar(value_pct, warn=15, severe=30, higher_is_bad=True, width_scale=1.8):
    """按阈值给 value_pct 上三档颜色，返回进度条 HTML。

    阈值顺序约定：本函数两个分支都要求 warn < severe（先比 severe 定最高档，
    再比 warn 定中间档），否则中间档不可达。正向指标（higher_is_bad=False，
    如 Computing 传 30/50、核心类型分布传 50/80）为 绿(>=severe) > 橙(>=warn)
    > 红；负向指标（higher_is_bad=True，如 CommNO 传 15/30、Free 传 10/20）为
    红(>=severe) > 橙(>=warn) > 绿。

    注意：同文件 cell_style 的 higher_is_bad=False 分支顺序相反，要求
    severe < warn（先比 v <= severe 定红，再比 v <= warn 定橙），如
    Computing 单元格传的是 50/30。两个 helper 的阈值参数顺序不通用，
    改动任一侧的判定顺序前先看 test/host/test_progress_bar_threshold_colors.py。
    """
    v = float(value_pct)
    if higher_is_bad:
        color = '#e74c3c' if v >= severe else '#e67e22' if v >= warn else '#2ecc71'
    else:
        color = '#2ecc71' if v >= severe else '#e67e22' if v >= warn else '#e74c3c'
    w = max(4, int(min(v, 100) * width_scale))
    return (f'<div style="display:flex;align-items:center;gap:8px">'
            f'<div style="height:10px;width:{w}px;background:{color};border-radius:5px;min-width:4px"></div>'
            f'<span style="font-size:12px;color:var(--text-secondary)">{v:.1f}%</span></div>')


def cell_style(value, warn, severe, higher_is_bad=True, is_pct=False):
    v = float(value) * (100 if is_pct else 1)
    if higher_is_bad:
        if v >= severe:
            return 'background:#fdecea;color:#e74c3c;font-weight:600'
        if v >= warn:
            return 'background:#fff8e1;color:#e67e22;font-weight:600'
        return 'background:#f0faf4;color:#27ae60'
    else:
        if v <= severe:
            return 'background:#fdecea;color:#e74c3c;font-weight:600'
        if v <= warn:
            return 'background:#fff8e1;color:#e67e22;font-weight:600'
        return 'background:#f0faf4;color:#27ae60'


def fmt_us(v):
    v = float(v)
    if v >= 1000:
        return f'{v:,.0f}'
    return f'{v:.1f}'


def section(anchor, title, body, open_=False):
    open_attr = ' open' if open_ else ''
    return f'''
<section id="{anchor}">
<details{open_attr}>
<summary>{html.escape(title)}</summary>
<div class="sb">{body}</div>
</details>
</section>'''


def note(text, kind='info'):
    colors = {'info': ('var(--note-info-bg)', 'var(--note-info-border)'),
              'warn': ('var(--note-warn-bg)', 'var(--note-warn-border)'),
              'alert': ('var(--note-alert-bg)', 'var(--note-alert-border)')}
    bg, border = colors.get(kind, colors['info'])
    return (f'<div style="background:{bg};border-left:4px solid {border};'
            f'padding:10px 14px;margin:10px 0;border-radius:0 6px 6px 0;'
            f'font-size:13px;line-height:1.6">{text}</div>')


def skip_div(reason):
    return f'<div style="padding:12px 0;color:#95a5a6;font-style:italic">⏭️ {html.escape(reason)}</div>'


# ── 各章节渲染 ────────────────────────────────────────────────────────────────

def render_meta(d):
    m = d.get('meta', {})
    rows = [
        ('输入路径', html.escape(m.get('data_path', '—'))),
        ('实际数据路径', f'<code>{html.escape(m.get("actual_path", m.get("data_path","—")))}</code>'),
        ('芯片型号', html.escape(m.get('chip', 'Ascend 910B3'))),
        ('Schema 版本', f'<strong>{html.escape(m.get("schema_version","—"))}</strong>'),
        ('采集步数', html.escape(str(m.get('steps_desc', ', '.join(str(s) for s in m.get('steps', [])))))),
        ('设备数', html.escape(str(m.get('devices_desc', ', '.join(str(x) for x in m.get('devices', [])))))),
        ('文件清单', html.escape(', '.join(m.get('files_present', [])))),
        ('数据质量说明', html.escape(m.get('quality_notes', '—'))),
    ]
    trs = ''.join(f'<tr><td style="width:140px;font-weight:600;color:var(--text-primary)">'
                  f'{k}</td><td>{v}</td></tr>' for k, v in rows)
    return f'<table>{trs}</table>'


def render_summary(d):
    diag = d.get('bottleneck_diagnosis', [])
    # Summary cards (top 3)
    cards_html = ''
    if not diag:
        cards_html += _card('OK', '整体健康', '无已知瓶颈', '所有指标在正常范围内')
    else:
        for item in diag[:3]:
            p = item.get('priority', 'P3')
            lbl = item.get('label', '')
            ev = item.get('evidence', '')[:80]
            cards_html += _card(p, lbl, '', ev)
    # Table
    trs = ''
    for item in diag:
        p = item.get('priority', 'P3')
        trs += (f'<tr><td>{badge(p, p)}</td><td>{html.escape(item.get("dimension",""))}</td>'
                f'<td>{html.escape(item.get("evidence","")[:120])}</td></tr>')
    if not trs:
        trs = '<tr><td colspan="3" style="color:#27ae60">✅ 无显著瓶颈</td></tr>'
    table = f'<table><tr><th>优先级</th><th>维度</th><th>核心发现</th></tr>{trs}</table>'
    return f'<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:16px">{cards_html}</div>{table}'


def _card(priority, title, subtitle, desc):
    border = CARD_BORDER.get(priority, '#ccc')
    bdg = badge(priority, priority)
    return (f'<div class="summary-card" style="border-left-color:{border}">'
            f'{bdg}<div class="card-subtitle">{html.escape(str(subtitle))}</div>'
            f'<div class="card-title">{html.escape(str(title))}</div>'
            f'<div class="card-desc">{html.escape(str(desc))}</div></div>')


def render_bound_classification(d):
    bc = d.get('bound_classification', {})
    if not bc:
        return skip_div('bound_classification 数据缺失；旧版 analysis_data.json 可忽略本章节')
    priority = bc.get('priority', 'P3')
    overall = bc.get('overall_bound', 'INSUFFICIENT_EVIDENCE')
    device_type = bc.get('device_bound_type') or '—'
    primary = bc.get('primary_bottleneck', '—')
    secondary = ', '.join(str(x) for x in bc.get('secondary_bottlenecks', [])) or '—'
    confidence = bc.get('confidence', '—')
    facts = bc.get('facts', [])
    facts_html = ''.join(f'<li>{html.escape(str(x))}</li>' for x in facts) or '<li>—</li>'
    reasoning = html.escape(str(bc.get('reasoning', '—')))
    counter = html.escape(str(bc.get('counter_evidence', '—')))
    rows = [
        ('整体 Bound', f'<code>{html.escape(str(overall))}</code> {badge(priority, priority)}'),
        ('Device 子类', f'<code>{html.escape(str(device_type))}</code>'),
        ('主瓶颈', html.escape(str(primary))),
        ('次要瓶颈', html.escape(str(secondary))),
        ('置信度', html.escape(str(confidence))),
    ]
    trs = ''.join(f'<tr><td style="width:130px;font-weight:600;color:var(--text-primary)">'
                  f'{k}</td><td>{v}</td></tr>' for k, v in rows)
    host = bc.get('host_evidence', {})
    host_html = ''
    if host:
        labels = ', '.join(str(x) for x in host.get('soft_labels', [])) or '—'
        host_rows = [
            ('Host evidence', '可用' if host.get('available') else '不可用'),
            ('sync/H2D overlap', _fmt_ratio_or_dash(host.get('sync_or_h2d_overlap_ratio'))),
            ('comm marker overlap', _fmt_ratio_or_dash(host.get('comm_marker_overlap_ratio'))),
            ('host visible coverage', _fmt_ratio_or_dash(host.get('host_visible_coverage_ratio'))),
            ('soft labels', html.escape(labels)),
        ]
        host_trs = ''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in host_rows)
        host_html = f'<h3>Host Evidence</h3><table>{host_trs}</table>'
    return (
        f'<table>{trs}</table>'
        f'<h3>事实指标</h3><ul class="facts-list">{facts_html}</ul>'
        f'{note("<strong>诊断理由：</strong>" + reasoning, "info")}'
        f'{note("<strong>反证 / 降级条件：</strong>" + counter, "warn")}'
        f'{host_html}'
    )


def _fmt_ratio_or_dash(v):
    if v is None:
        return '—'
    try:
        return f'{float(v) * 100:.1f}%'
    except (TypeError, ValueError):
        return html.escape(str(v))


def _iter_step_rows(steps, warmup_steps):
    """渲染迭代效率每步表格行。"""
    trs = ''
    for s in steps:
        is_w = s.get('step') in warmup_steps or s.get('is_warmup', False)
        row_style = 'background:#fff3cd' if is_w else ''
        free_r = s.get('free_ratio', 0) * 100
        comm_r = s.get('comm_no_ratio', 0) * 100
        comp_r = s.get('computing_ratio', 0) * 100
        over_r = s.get('overlap_ratio', 0) * 100
        free_st = cell_style(free_r, 10, 20)
        comm_st = cell_style(comm_r, 15, 30)
        comp_st = cell_style(comp_r, 50, 30, higher_is_bad=False)
        remark = '⚠️ 预热步' if is_w else '正常步'
        trs += (f'<tr style="{row_style}">'
                f'<td>{s.get("step")}</td>'
                f'<td>{fmt_us(s.get("stage_us",0))}</td>'
                f'<td style="{comp_st}">{comp_r:.1f}%</td>'
                f'<td style="{comm_st}">{comm_r:.1f}%</td>'
                f'<td style="{free_st}">{free_r:.1f}%</td>'
                f'<td>{over_r:.2f}%</td>'
                f'<td>{remark}</td></tr>')
    return trs


def render_iter_efficiency(d):
    ie = d.get('iteration_efficiency', {})
    if not ie:
        return skip_div('iteration_efficiency 数据缺失')
    steps = ie.get('steps', [])
    warmup_steps = set(ie.get('warmup_steps', []))
    # Step table
    header = ('<tr><th>Step</th><th>Stage (μs)</th><th>Computing%</th><th>CommNO%</th>'
              '<th>Free%</th><th>Overlap%</th><th>备注</th></tr>')
    trs = _iter_step_rows(steps, warmup_steps)
    step_table = f'<table>{header}{trs}</table>'
    # Averages
    avg = ie.get('avg', {})
    avg_free = avg.get('free_ratio', 0) * 100
    avg_comm = avg.get('comm_no_ratio', 0) * 100
    avg_comp = avg.get('computing_ratio', 0) * 100
    avg_stage = avg.get('stage_us', 0)
    norm_steps = ie.get('normal_steps', [])
    avg_note = ''
    if norm_steps:
        avg_note = note(
            f'正常步均值（Step {", ".join(str(s) for s in norm_steps)}）：'
            f'Computing={avg_comp:.1f}%，CommNO={avg_comm:.1f}%，Free={avg_free:.1f}%，Stage≈{fmt_us(avg_stage)} μs',
            'info'
        )
    # Progress bars
    bars = f'''<table>
<tr><th>指标</th><th>均值</th><th>可视化</th><th>判定</th></tr>
<tr><td>Computing</td><td>{avg_comp:.1f}%</td>
    <td>{progress_bar(avg_comp,30,50,higher_is_bad=False,width_scale=1.4)}</td>
    <td>{"✅ 正常" if avg_comp>=50 else "⚠️ 偏低"}</td></tr>
<tr><td>CommNO</td><td>{avg_comm:.1f}%</td><td>{progress_bar(avg_comm,15,30,width_scale=2)}</td>
    <td>{"🔴 严重" if avg_comm>=30 else "⚠️ 警告" if avg_comm>=15 else "✅ 正常"}</td></tr>
<tr><td>Free</td><td>{avg_free:.1f}%</td><td>{progress_bar(avg_free,10,20,width_scale=2)}</td>
    <td>{"🔴 严重" if avg_free>=20 else "⚠️ 警告" if avg_free>=10 else "✅ 正常"}</td></tr>
</table>'''
    # Bottleneck
    bn = ie.get('bottleneck', {})
    bn_html = ''
    if bn and bn.get('label'):
        p = bn.get('priority', 'P3')
        bg_colors = {'P0': '#fef5f5', 'P1': '#fef9f0', 'P2': '#fefdf0', 'P3': '#f0f8ff'}
        bg = bg_colors.get(p, '#f0f8ff')
        bn_html = (f'<div style="background:{bg};border-radius:8px;padding:12px 16px;margin:10px 0">'
                   f'<strong>{badge(p, p)} {html.escape(bn.get("label",""))}</strong>'
                   f'<div style="margin-top:6px;font-size:13px;color:#555">{html.escape(bn.get("evidence",""))}</div>'
                   f'</div>')
    return (f'<h3 style="margin:16px 0 8px;font-size:14px">每步时间拆分</h3>{step_table}{avg_note}'
            f'<h3 style="margin:16px 0 8px;font-size:14px">指标可视化</h3>{bars}{bn_html}')


def render_op_hotspots(d):
    oh = d.get('operator_hotspots', {})
    if not oh:
        return skip_div('operator_hotspots 数据缺失')
    ops = oh.get('top_ops', [])
    flag_map = {
        'hotspot': badge('🔴 热点', 'P0'),
        'watch': badge('⚠️ 关注', 'P2'),
        'normal': badge('✅ 正常', 'OK'),
        'moe_normal': badge('✅ MoE正常', 'OK'),
        'aicpu': badge('🚨 AICPU', 'P0'),
    }
    header = ('<tr><th>#</th><th>算子类型</th><th>核心类型</th><th>次数</th><th>Total (μs)</th>'
              '<th>Avg (μs)</th><th>Ratio%</th><th>标注</th></tr>')
    trs = ''
    for op in ops:
        ratio = float(op.get('ratio', 0))
        ratio_st = cell_style(ratio, 10, 20)
        flag_html = flag_map.get(op.get('flag', 'normal'), badge('✅', 'OK'))
        trs += (f'<tr><td>{op.get("rank")}</td>'
                f'<td><code>{html.escape(op.get("name",""))}</code></td>'
                f'<td>{html.escape(op.get("core_type",""))}</td>'
                f'<td>{op.get("count")}</td>'
                f'<td>{fmt_us(op.get("total_us",0))}</td>'
                f'<td>{fmt_us(op.get("avg_us",0))}</td>'
                f'<td style="{ratio_st}">{ratio:.2f}%</td>'
                f'<td>{flag_html}</td></tr>')
    table = f'<table>{header}{trs}</table>'
    # Core type breakdown
    ct = oh.get('core_type_breakdown', {})
    ct_rows = ''
    for name, pct in ct.items():
        ct_rows += (f'<tr><td>{html.escape(name)}</td>'
                    f'<td>{progress_bar(float(pct),50,80,higher_is_bad=False,width_scale=1.5)}</td></tr>')
    ct_table = f'<h3 style="margin:16px 0 8px;font-size:14px">核心类型分布</h3><table>{ct_rows}</table>' if ct_rows else ''
    extra_note = note(oh['note']) if oh.get('note') else ''
    return f'<h3 style="margin:0 0 8px;font-size:14px">Top-10 算子</h3>{table}{ct_table}{extra_note}'


def render_hw_util(d):
    hw = d.get('hardware_utilization', {})
    if not hw or hw.get('skipped'):
        return skip_div(hw.get('skip_reason', '硬件利用率数据不可用'))
    kernels = hw.get('representative_kernels', [])
    header = '<tr><th>算子</th><th>Input Shapes</th><th>MFU</th><th>cube_utilization%</th><th>判定</th></tr>'
    trs = ''
    for k in kernels:
        mfu = k.get('mfu')
        cu = k.get('cube_utilization')
        mfu_str = f'{float(mfu)*100:.1f}%' if mfu is not None else '—'
        cu_str = f'{float(cu):.1f}%' if cu is not None else '—'
        cu_st = cell_style(float(cu) if cu else 50, 40, 20, higher_is_bad=False) if cu else ''
        verdict = k.get('verdict', '')
        trs += (f'<tr><td><code>{html.escape(k.get("name",""))}</code></td>'
                f'<td style="font-size:11px">{html.escape(k.get("input_shapes","")[:50])}</td>'
                f'<td>{mfu_str}</td>'
                f'<td style="{cu_st}">{cu_str}</td>'
                f'<td>{html.escape(verdict)}</td></tr>')
    table = f'<table>{header}{trs}</table>' if trs else ''
    extra = note(hw['note']) if hw.get('note') else ''
    avg_cu = hw.get('avg_cube_utilization')
    avg_cu_html = ''
    if avg_cu is not None:
        avg_cu_html = (f'<p style="margin:8px 0;font-size:13px">MatMul 平均 cube_utilization：'
                       f'<strong>{float(avg_cu):.1f}%</strong> '
                       f'{badge("✅ 健康", "OK") if float(avg_cu)>=40 else badge("⚠️ 偏低","P2")}</p>')
    return f'{table}{avg_cu_html}{extra}'


def render_operator_bound(d):
    oba = d.get('operator_bound_analysis', {})
    if not oba:
        return skip_div('operator_bound_analysis 数据缺失；旧版 analysis_data.json 可忽略本章节')
    if oba.get('skipped'):
        return skip_div(oba.get('skip_reason', '算子级 Bound 分析被跳过'))
    src = html.escape(str(oba.get('source', '—')))
    summary = oba.get('summary', {})
    summary_rows = ''
    for key, label in [
        ('compute_bound_count', 'Compute Bound'),
        ('memory_bound_count', 'Memory Bound'),
        ('scalar_bound_count', 'Scalar / Latency Bound'),
        ('fixpipe_bound_count', 'FixPipe Bound'),
        ('bank_conflict_count', 'Bank Conflict'),
    ]:
        if key in summary:
            summary_rows += f'<tr><td>{label}</td><td>{summary.get(key)}</td></tr>'
    summary_html = f'<p style="margin:6px 0 12px;color:var(--text-secondary)">数据源：<code>{src}</code></p>'
    if summary_rows:
        summary_html += f'<table><tr><th>分类</th><th>数量</th></tr>{summary_rows}</table>'

    ops = oba.get('top_operators', [])
    rows = ''
    for op in ops:
        bt = op.get('bound_type', 'UNKNOWN')
        p = _bound_priority(bt)
        rows += (
            f'<tr><td><code>{html.escape(str(op.get("name","")))}</code></td>'
            f'<td>{html.escape(str(op.get("core_type","—")))}</td>'
            f'<td>{fmt_us(op.get("duration_us", 0))}</td>'
            f'<td>{badge(bt, p)}</td>'
            f'<td style="font-size:12px">{html.escape(str(op.get("evidence","")))}</td>'
            f'<td>{html.escape(str(op.get("confidence","")))}</td>'
            f'<td style="font-size:12px">{html.escape(str(op.get("recommendation_hint","")))}</td></tr>'
        )
    op_table = ''
    if rows:
        op_table = ('<h3>Top 算子 Bound</h3><table><tr><th>算子</th><th>Core</th>'
                    '<th>Duration(μs)</th><th>Bound</th><th>证据</th><th>置信度</th>'
                    '<th>建议提示</th></tr>' + rows + '</table>')
    pmu_notes = note(html.escape(str(oba.get('pmu_notes'))), 'warn') if oba.get('pmu_notes') else ''
    return summary_html + op_table + pmu_notes


def _bound_priority(bound_type):
    if bound_type in ('OP_MEMORY_BOUND', 'DEVICE_MEMORY_BOUND', 'OP_COMPUTE_BOUND', 'DEVICE_COMPUTE_BOUND'):
        return 'P1'
    if bound_type in ('OP_SCALAR_BOUND', 'DEVICE_LATENCY_BOUND', 'OP_FIXPIPE_BOUND', 'BANK_CONFLICT_RISK'):
        return 'P2'
    return 'P3'


def render_comm(d):
    ce = d.get('communication_efficiency', {})
    if not ce or ce.get('skipped'):
        return skip_div(ce.get('skip_reason', '无通信数据'))
    rows = []
    or_ = ce.get('overlap_ratio_avg', 0) * 100
    or_st = cell_style(or_, 20, 50, higher_is_bad=False)
    rows.append(('overlap_ratio（均值）', f'<span style="{or_st}">{or_:.2f}%</span>', '目标 > 50%'))
    coll = ce.get('collectives', {})
    coll_str = ', '.join(f'{k}×{v}' for k, v in coll.items() if v)
    if coll_str:
        rows.append(('集合通信类型', coll_str, ''))
    bw = ce.get('bandwidth', {})
    for medium, bw_val in bw.items():
        if bw_val is not None:
            bw_st = ''
            if medium == 'RDMA' and float(bw_val) > 0:
                bw_st = cell_style(float(bw_val), 0.5, 0.5, higher_is_bad=False)
            rows.append((f'{medium} 带宽', f'<span style="{bw_st}">{float(bw_val):.2f} GB/s</span>', ''))
    single = ce.get('single_rank', False)
    if single:
        rows.append(('带宽数据', '⚠️ 单 Rank 采集，所有带宽数据为 0，不可用', ''))
    trs = ''.join(f'<tr><td style="font-weight:600">{k}</td><td>{v}</td>'
                  f'<td style="color:#95a5a6">{r}</td></tr>' for k, v, r in rows)
    table = f'<table><tr><th>指标</th><th>数值</th><th>说明</th></tr>{trs}</table>'
    extra = note(ce['note']) if ce.get('note') else ''
    return f'{table}{extra}'


def render_bubbles(d):
    db = d.get('device_bubbles', {})
    if not db or db.get('skipped'):
        return skip_div(db.get('skip_reason', '设备空泡数据不可用') if db else '设备空泡数据缺失')
    ur = float(db.get('underfeed_ratio', 0)) * 100
    ur_st = cell_style(ur, 5, 20)
    rows = [
        ('underfeed_ratio', f'<span style="{ur_st}">{ur:.1f}%</span>', '严重 > 20%'),
        ('prelaunch_gap', f'{db.get("prelaunch_gap_ms", 0):.2f} ms', '严重 > 5ms'),
        ('internal_bubble_total', f'{db.get("internal_bubble_ms", 0):.2f} ms', ''),
    ]
    trs = ''.join(f'<tr><td style="font-weight:600">{k}</td><td>{v}</td>'
                  f'<td style="color:#95a5a6">{r}</td></tr>' for k, v, r in rows)
    extra = note(db['note']) if db.get('note') else ''
    return f'<table><tr><th>指标</th><th>估算值</th><th>说明</th></tr>{trs}</table>{extra}'


def render_wait_anchors(d):
    wa = d.get('wait_anchors', [])
    if not wa:
        return '<div style="color:#27ae60;padding:8px 0">✅ 未检测到等待锚点假热点。</div>'
    header = ('<tr><th>Kernel</th><th>Duration(μs)</th><th>Wait(μs)</th><th>wait_ratio</th>'
              '<th>total_cost(μs)</th><th>前序Kernel</th><th>判定</th></tr>')
    trs = ''
    for k in wa:
        wr = float(k.get('wait_ratio', 0)) * 100
        wr_st = cell_style(wr, 50, 95)
        trs += (f'<tr><td><code>{html.escape(k.get("name",""))}</code></td>'
                f'<td style="color:#27ae60">{fmt_us(k.get("duration_us",0))}</td>'
                f'<td style="color:#e74c3c">{fmt_us(k.get("wait_us",0))}</td>'
                f'<td style="{wr_st}">{wr:.1f}%</td>'
                f'<td>{fmt_us(k.get("total_cost_us",0))}</td>'
                f'<td style="font-size:11px;color:#95a5a6">{html.escape(k.get("prev_kernel","")[:40])}</td>'
                f'<td>{badge("🔴 假热点","P0")}</td></tr>')
    desc = note(
        '以上 kernel 按 total_cost 排名靠前，但 wait_ratio > 95% 且 Duration &lt; 10μs，判定为<strong>等待锚点假热点</strong>。'
        '真实计算耗时极短，不是性能瓶颈；实际问题是上游操作（通常为通信）导致设备等待。',
        'warn'
    )
    return f'<table>{header}{trs}</table>{desc}'


def render_layer_struct(d):
    ls = d.get('layer_structure', {})
    if not ls or ls.get('skipped'):
        return skip_div(ls.get('skip_reason', '层级结构数据不可用') if ls else '层级结构数据缺失')
    rows = [
        ('模型类型', f'<strong>{html.escape(ls.get("model_type","Unknown"))}</strong>'),
        ('推理阶段', html.escape(ls.get('inference_phase', '—'))),
        ('层数（估算）', str(ls.get('num_layers', '—'))),
        ('MoE 特征算子', html.escape(', '.join(ls.get('moe_ops_detected', [])) or '未检测到')),
    ]
    trs = ''.join(f'<tr><td style="font-weight:600">{k}</td><td>{v}</td></tr>' for k, v in rows)
    extra = note(ls['note']) if ls.get('note') else ''
    return f'<table>{trs}</table>{extra}'


def render_multi_card(d):
    mc = d.get('multi_card', {})
    if not mc or mc.get('skipped'):
        return skip_div(mc.get('skip_reason', '仅单设备数据，无法进行多卡分析') if mc else '多卡数据不可用')
    vr = mc.get('variance_ratio')
    if vr is not None:
        vr_pct = float(vr) * 100
        vr_st = cell_style(vr_pct, 10, 20)
        return f'<p>Stage variance_ratio = <span style="{vr_st}">{vr_pct:.1f}%</span>（阈值：警告 10%，严重 20%）</p>'
    return '<p>多卡数据存在，但 variance_ratio 未计算。</p>'


def render_diagnosis(d):
    diag = d.get('bottleneck_diagnosis', [])
    if not diag:
        return '<div style="color:#27ae60;padding:8px 0">✅ 无已知性能瓶颈。</div>'
    header = '<tr><th>优先级</th><th>标签</th><th>维度</th><th>指标证据</th><th>诊断理由</th><th>反证/降级</th><th>置信度</th></tr>'
    trs = ''
    for item in diag:
        p = item.get('priority', 'P3')
        trs += (f'<tr><td>{badge(p, p)}</td>'
                f'<td><code>{html.escape(item.get("label",""))}</code></td>'
                f'<td>{html.escape(item.get("dimension",""))}</td>'
                f'<td style="font-size:12px">{html.escape(item.get("evidence",""))}</td>'
                f'<td style="font-size:12px">{html.escape(item.get("reasoning",""))}</td>'
                f'<td style="font-size:12px;color:var(--text-secondary)">'
                f'{html.escape(item.get("counter_evidence",""))}</td>'
                f'<td>{html.escape(item.get("confidence",""))}</td></tr>')
    return f'<table>{header}{trs}</table>'


def render_recommendations(d):
    recs = d.get('recommendations', [])
    not_rec = d.get('not_recommended', [])
    if not recs:
        return '<div style="color:#95a5a6">暂无具体优化建议。</div>'
    header = '<tr><th>优先级</th><th>建议</th><th>具体措施</th><th>预期收益</th></tr>'
    trs = ''
    for r in recs:
        p = r.get('priority', 'P3')
        trs += (f'<tr><td>{badge(p, p)}</td>'
                f'<td><strong>{html.escape(r.get("title",""))}</strong></td>'
                f'<td style="font-size:12px">{html.escape(r.get("action",""))}</td>'
                f'<td style="font-size:12px;color:#27ae60">{html.escape(r.get("benefit",""))}</td></tr>')
    table = f'<table>{header}{trs}</table>'
    not_rec_html = ''
    if not_rec:
        items = '、'.join(html.escape(x) for x in not_rec)
        not_rec_html = note(f'<strong>不建议优先优化</strong>：{items}', 'warn')
    return f'{table}{not_rec_html}'


# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = '''
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg-primary:#282a36;--bg-secondary:#21222c;--bg-tertiary:#343746;--bg-hover:#44475a;
  --text-primary:#f8f8f2;--text-secondary:#aab0d4;--accent-blue:#8be9fd;--accent-green:#50fa7b;--accent-orange:#ffb86c;
  --border-color:#44475a;--button-bg:#bd93f9;--button-hover:#ff79c6;--nav-bg:#1d1e26;--nav-text:#d8dcff;
  --table-head:#343746;--table-row-alt:#2e3040;--table-hover:#3b3f55;--code-bg:#3b3f55;--card-bg:#343746;
  --note-info-bg:rgba(139,233,253,.12);--note-info-border:#8be9fd;
  --note-warn-bg:rgba(255,184,108,.14);--note-warn-border:#ffb86c;
  --note-alert-bg:rgba(255,85,85,.14);--note-alert-border:#ff5555;
}
[data-theme="vscode-dark"]{
--bg-primary:#1e1e1e;--bg-secondary:#252526;--bg-tertiary:#2d2d2d;--bg-hover:#333333;
--text-primary:#d4d4d4;--text-secondary:#9a9a9a;--accent-blue:#4fc1ff;--accent-green:#6a9955;--accent-orange:#ce9178;
--border-color:#3c3c3c;--button-bg:#0e639c;--button-hover:#1177bb;--nav-bg:#181818;--nav-text:#cccccc;
--table-head:#2d2d2d;--table-row-alt:#252526;--table-hover:#303030;--code-bg:#333333;--card-bg:#252526}
[data-theme="one-dark"]{
--bg-primary:#282c34;--bg-secondary:#21252b;--bg-tertiary:#2c313a;--bg-hover:#353b45;
--text-primary:#abb2bf;--text-secondary:#7f8794;--accent-blue:#61afef;--accent-green:#98c379;--accent-orange:#d19a66;
--border-color:#181a1f;--button-bg:#4d78cc;--button-hover:#528bff;--nav-bg:#1f2329;--nav-text:#abb2bf;
--table-head:#2c313a;--table-row-alt:#252a31;--table-hover:#333944;--code-bg:#353b45;--card-bg:#2c313a}
[data-theme="github-light"]{
--bg-primary:#ffffff;--bg-secondary:#f6f8fa;--bg-tertiary:#ffffff;--bg-hover:#eaeef2;
--text-primary:#1f2328;--text-secondary:#656d76;--accent-blue:#0969da;--accent-green:#1a7f37;--accent-orange:#bc4c00;
--border-color:#d1d9e0;--button-bg:#0969da;--button-hover:#0550ae;--nav-bg:#24292f;--nav-text:#d1d9e0;
--table-head:#f6f8fa;--table-row-alt:#f6f8fa;--table-hover:#eef4ff;--code-bg:#f6f8fa;--card-bg:#ffffff;
--note-info-bg:#ddf4ff;--note-info-border:#0969da;--note-warn-bg:#fff8c5;--note-warn-border:#bc4c00;
--note-alert-bg:#ffebe9;--note-alert-border:#cf222e}
[data-theme="solarized-light"]{
--bg-primary:#fdf6e3;--bg-secondary:#eee8d5;--bg-tertiary:#fff8e8;--bg-hover:#e0dac7;
--text-primary:#073642;--text-secondary:#657b83;--accent-blue:#268bd2;--accent-green:#859900;--accent-orange:#cb4b16;
--border-color:#d3cbb7;--button-bg:#268bd2;--button-hover:#1a6da8;--nav-bg:#073642;--nav-text:#eee8d5;
--table-head:#eee8d5;--table-row-alt:#f4edda;--table-hover:#e8e1cc;--code-bg:#eee8d5;--card-bg:#fff8e8;
--note-info-bg:#e4f2f7;--note-info-border:#268bd2;--note-warn-bg:#faedcf;--note-warn-border:#cb4b16;
--note-alert-bg:#f7dfd8;--note-alert-border:#dc322f}
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;font-size:14px;
background:var(--bg-primary);color:var(--text-primary)}
code{background:var(--code-bg);color:var(--text-primary);padding:1px 5px;
border-radius:3px;font-size:12px;font-family:monospace}
nav{position:fixed;top:0;left:0;width:230px;height:100vh;background:var(--nav-bg);
color:var(--nav-text);overflow-y:auto;z-index:100;padding:16px 0}
nav h2{font-size:12px;color:var(--text-secondary);padding:0 14px 10px;
border-bottom:1px solid var(--border-color);letter-spacing:1px}
nav ul{list-style:none;margin-top:6px}
nav ul li a{display:block;padding:6px 14px;color:var(--nav-text);font-size:12px;
transition:all .2s;border-left:3px solid transparent;text-decoration:none}
nav ul li a:hover,nav ul li a.active{color:#fff;background:rgba(255,255,255,.08);border-left-color:var(--accent-blue)}
main{margin-left:230px;padding:20px 28px;max-width:1180px}
h1{font-size:22px;font-weight:700;color:var(--text-primary);margin:20px 0 4px}
.sub{color:var(--text-secondary);font-size:12px;margin-bottom:14px}
.controls{display:flex;gap:10px;align-items:center;background:var(--bg-secondary);
border:1px solid var(--border-color);border-radius:8px;padding:10px 12px;
margin-bottom:14px;color:var(--text-secondary);font-size:12px}
.controls select{background:var(--bg-tertiary);color:var(--text-primary);
border:1px solid var(--border-color);border-radius:4px;padding:5px 8px}
details{background:var(--bg-tertiary);border:1px solid var(--border-color);
border-radius:8px;margin-bottom:12px;box-shadow:0 1px 6px rgba(0,0,0,.12);overflow:hidden}
details[open]{box-shadow:0 2px 10px rgba(0,0,0,.10)}
summary{padding:13px 18px;cursor:pointer;font-size:14px;font-weight:600;
color:var(--text-primary);list-style:none;user-select:none;display:flex;align-items:center;gap:6px}
summary::-webkit-details-marker{display:none}
summary::before{content:"▶";font-size:9px;color:var(--text-secondary);transition:transform .2s;min-width:11px}
details[open]>summary::before{transform:rotate(90deg)}
.sb{padding:4px 18px 18px}
table{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0}
th{background:var(--table-head);text-align:left;padding:8px 10px;font-weight:600;
color:var(--text-primary);border-bottom:1px solid var(--border-color)}
td{padding:7px 10px;border-bottom:1px solid var(--border-color);vertical-align:middle;color:var(--text-primary)}
tr:nth-child(even) td{background:var(--table-row-alt)}
tr:hover td{background:var(--table-hover)!important}
section{scroll-margin-top:20px}
footer{margin-top:36px;padding:14px 0;border-top:1px solid var(--border-color);
color:var(--text-secondary);font-size:11px}
h3{font-size:13px;font-weight:600;color:var(--text-primary);margin:14px 0 8px}
.summary-card{flex:1;min-width:220px;background:var(--card-bg);border-radius:8px;
padding:14px 18px;box-shadow:0 2px 8px rgba(0,0,0,.12);border-left:5px solid var(--border-color)}
.card-subtitle{font-size:12px;color:var(--text-secondary);margin:6px 0 2px}
.card-title{font-size:17px;font-weight:700;color:var(--text-primary)}
.card-desc{font-size:12px;color:var(--text-secondary);margin-top:4px}
.facts-list{margin:8px 0 8px 20px;color:var(--text-primary);line-height:1.7}
'''

NAV_ITEMS = [
    ('ctx', '一、分析上下文'),
    ('summary', '二、执行摘要'),
    ('bound', '三、整体 Bound'),
    ('dim1', '四、迭代效率'),
    ('dim2', '五、算子热点'),
    ('dim3', '六、硬件利用率'),
    ('opbound', '七、算子 Bound'),
    ('dim4', '八、通信效率'),
    ('dim5', '九、设备空泡'),
    ('dim6', '十、等待锚点'),
    ('dim7', '十一、层级结构'),
    ('dim8', '十二、多卡均衡'),
    ('diag', '十三、瓶颈诊断'),
    ('opt', '十四、优化建议'),
]


THEMES = ['dracula', 'vscode-dark', 'one-dark', 'github-light', 'solarized-light']


def _build_sections(data):
    """按顺序渲染全部分析维度 section 并拼接。"""
    return (
        section('ctx', '一、分析上下文', render_meta(data), open_=True) +
        section('summary', '二、执行摘要', render_summary(data), open_=True) +
        section('bound', '三、整体 Bound 判定', render_bound_classification(data), open_=True) +
        section('dim1', '四、维度 1：迭代效率', render_iter_efficiency(data), open_=True) +
        section('dim2', '五、维度 2：算子热点', render_op_hotspots(data), open_=True) +
        section('dim3', '六、维度 3：硬件利用率 / MFU', render_hw_util(data)) +
        section('opbound', '七、算子级 Bound 分析', render_operator_bound(data), open_=True) +
        section('dim4', '八、维度 4：通信效率', render_comm(data)) +
        section('dim5', '九、维度 5：设备空泡', render_bubbles(data)) +
        section('dim6', '十、维度 6：等待锚点假热点', render_wait_anchors(data)) +
        section('dim7', '十一、维度 7：层级结构', render_layer_struct(data)) +
        section('dim8', '十二、维度 8：多卡负载均衡', render_multi_card(data)) +
        section('diag', '十三、瓶颈诊断', render_diagnosis(data), open_=True) +
        section('opt', '十四、优化建议', render_recommendations(data), open_=True)
    )


_NAV_SCRIPT = '''<script>
const secs=document.querySelectorAll('section[id]');
const links=document.querySelectorAll('nav a');
window.addEventListener('scroll',()=>{
  let cur='';
  secs.forEach(s=>{if(window.scrollY+80>=s.offsetTop)cur=s.id});
  links.forEach(a=>a.classList.toggle('active',a.getAttribute('href')==='#'+cur));
});
links.forEach(a=>a.addEventListener('click',()=>{
  const id=a.getAttribute('href').slice(1);
  document.getElementById(id)?.querySelector('details') &&
    (document.getElementById(id).querySelector('details').open=true);
}));
const themeSelect=document.getElementById('theme-select');
const savedTheme=localStorage.getItem('npu-perf-theme');
if(savedTheme && @@THEMES@@.includes(savedTheme)){
  document.body.dataset.theme=savedTheme;
  themeSelect.value=savedTheme;
}
themeSelect.addEventListener('change',()=>{
  document.body.dataset.theme=themeSelect.value;
  localStorage.setItem('npu-perf-theme',themeSelect.value);
});
</script>'''


def generate(data: dict, theme: str = 'dracula') -> str:
    if theme not in THEMES:
        theme = 'dracula'
    m = data.get('meta', {})
    chip = m.get('chip', 'Ascend 910B3')
    schema = m.get('schema_version', '—')
    generated_at = m.get('generated_at', datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d'))
    subtitle = f"{html.escape(m.get('data_path',''))} · {html.escape(chip)} · {schema} Schema · {generated_at}"

    nav_links = '\n'.join(f'<li><a href="#{a}">{t}</a></li>' for a, t in NAV_ITEMS)

    sections_html = _build_sections(data)
    options = ''.join(f'<option value="{t}"{" selected" if t == theme else ""}>{t}</option>' for t in THEMES)
    nav_script = _NAV_SCRIPT.replace('@@THEMES@@', repr(THEMES))

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NPU 性能分析报告</title>
<style>{CSS}</style>
</head>
<body data-theme="{theme}">
<nav>
  <h2>NPU 分析导航</h2>
  <ul>{nav_links}</ul>
</nav>
<main>
  <h1>NPU 性能分析报告</h1>
  <div class="sub">{subtitle}</div>
  <div class="controls"><label>主题风格 <select id="theme-select">{options}</select></label></div>
  {sections_html}
  <footer>生成时间：{generated_at} &nbsp;|&nbsp; 数据路径：{html.escape(m.get("actual_path", m.get("data_path","")))}
  &nbsp;|&nbsp; Schema：{schema} &nbsp;|&nbsp; 芯片：{html.escape(chip)}</footer>
</main>
{nav_script}
</body>
</html>'''


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    parser = argparse.ArgumentParser(description='NPU 性能分析 HTML 报告生成器')
    parser.add_argument('analysis_data_json', help='analysis_data.json 路径')
    parser.add_argument('output_html', help='输出 HTML 路径')
    parser.add_argument('--theme', choices=THEMES, default='dracula',
                        help='HTML 主题风格，默认 dracula')
    args = parser.parse_args()
    json_path, html_path = args.analysis_data_json, args.output_html
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    html_content = generate(data, args.theme)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info('HTML 报告已生成：%s', html_path)


if __name__ == '__main__':
    main()
