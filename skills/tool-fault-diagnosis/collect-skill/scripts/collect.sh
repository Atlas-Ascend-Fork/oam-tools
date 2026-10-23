#!/bin/bash
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
# collect.sh — Ascend NPU 日志自动采集脚本
# 用途：复制本地 slog/CANN（旧名 msnpureprot）、host、plog 日志到指定目录
# 平台：Ascend NPU, CANN 8.5.0, aarch64

set -euo pipefail

# ===================== 默认配置 =====================
OUTPUT_DIR="./logs"
COLLECT_ALL=false
COLLECT_MSNPUREPROT=false
COLLECT_HOST=false
COLLECT_PLOG=false
START_TIME=""
END_TIME=""
CANN_HOME="/usr/local/Ascend/cann-8.5.0"
PLOG_DIR="${HOME}/ascend/log/plog"
NPU_SLOG_DIR="/var/log/npu/slog"
NPU_DRIVER_DIR="/var/log/npu/driver"

# ===================== 帮助信息 =====================
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --all                采集所有日志来源"
    echo "  --msnpureprot        复制本地 slog/CANN 日志（旧参数名，不执行 msnpureport 导出）"
    echo "  --host               采集宿主机系统日志"
    echo "  --plog               采集 plog 框架日志"
    echo "  --output DIR         指定输出目录（默认：./logs）"
    echo "  --start DATETIME     起始时间过滤，格式：'YYYY-MM-DD HH:MM:SS'"
    echo "  --end   DATETIME     结束时间过滤，格式：'YYYY-MM-DD HH:MM:SS'"
    echo "  -h, --help           显示此帮助"
    echo ""
    echo "示例："
    echo "  $0 --all --output ./collected_logs"
    echo "  $0 --plog --host --output ./logs"
    echo "  $0 --all --start '2026-03-25 10:00:00' --end '2026-03-25 11:00:00'"
    exit 0
}

# ===================== 参数解析 =====================
while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)           COLLECT_ALL=true ;;
        --msnpureprot)   COLLECT_MSNPUREPROT=true ;;
        --host)          COLLECT_HOST=true ;;
        --plog)          COLLECT_PLOG=true ;;
        --output)        OUTPUT_DIR="$2"; shift ;;
        --start)         START_TIME="$2"; shift ;;
        --end)           END_TIME="$2"; shift ;;
        -h|--help)       usage ;;
        *)               echo "[ERROR] Unknown option: $1"; usage ;;
    esac
    shift
done

if $COLLECT_ALL; then
    COLLECT_MSNPUREPROT=true
    COLLECT_HOST=true
    COLLECT_PLOG=true
fi

if ! $COLLECT_MSNPUREPROT && ! $COLLECT_HOST && ! $COLLECT_PLOG; then
    echo "[ERROR] 请指定至少一个采集来源（--all / --msnpureprot / --host / --plog）"
    usage
fi

# ===================== 工具函数 =====================
log_info()  { echo "[INFO]  $*"; }
log_warn()  { echo "[WARN]  $*"; }
log_error() { echo "[ERROR] $*" >&2; }

copy_with_time_filter() {
    local src_dir="$1"
    local dst_dir="$2"
    mkdir -p "$dst_dir"

    if [[ -n "$START_TIME" && -n "$END_TIME" ]]; then
        # 通过 touch 创建时间锚点文件再用 find -newer 过滤
        local tmp_start=$(mktemp)
        local tmp_end=$(mktemp)
        touch -d "$START_TIME" "$tmp_start"
        touch -d "$END_TIME"   "$tmp_end"
        find "$src_dir" -name "*.log" -newer "$tmp_start" ! -newer "$tmp_end" \
            -exec cp --parents {} "$dst_dir/" \; 2>/dev/null || true
        rm -f "$tmp_start" "$tmp_end"
    else
        find "$src_dir" -name "*.log" -exec cp --parents {} "$dst_dir/" \; 2>/dev/null || true
    fi
}

# ===================== 采集 msnpureprot =====================
collect_msnpureprot() {
    log_info "开始采集 msnpureprot 日志..."
    local dst="${OUTPUT_DIR}/msnpureprot"
    mkdir -p "$dst"

    if [[ -d "$NPU_SLOG_DIR" ]]; then
        copy_with_time_filter "$NPU_SLOG_DIR" "$dst"
        log_info "msnpureprot 日志已复制到 ${dst}"
    else
        log_warn "未找到 msnpureprot 日志目录：${NPU_SLOG_DIR}，请确认权限或路径"
    fi

    # 同时复制 CANN 框架内部协议日志
    local cann_log="${CANN_HOME}/log"
    if [[ -d "$cann_log" ]]; then
        copy_with_time_filter "$cann_log" "${dst}/cann"
    fi
}

# ===================== 采集 host 日志 =====================
collect_host() {
    log_info "开始采集宿主机日志..."
    local dst="${OUTPUT_DIR}/host"
    mkdir -p "$dst"

    # dmesg（NPU 相关）
    if command -v dmesg &>/dev/null; then
        dmesg | grep -iE "npu|ascend|davinci|hisi" > "${dst}/dmesg_npu.log" 2>/dev/null || true
        log_info "dmesg 日志已保存"
    fi

    # journalctl 或 syslog
    if command -v journalctl &>/dev/null; then
        if [[ -n "$START_TIME" && -n "$END_TIME" ]]; then
            journalctl --since "$START_TIME" --until "$END_TIME" --no-pager \
                > "${dst}/journalctl.log" 2>/dev/null || true
        else
            journalctl -n 1000 --no-pager > "${dst}/journalctl.log" 2>/dev/null || true
        fi
        log_info "journalctl 日志已保存"
    elif [[ -f /var/log/syslog ]]; then
        cp /var/log/syslog "${dst}/syslog.log" 2>/dev/null || true
    elif [[ -f /var/log/messages ]]; then
        cp /var/log/messages "${dst}/messages.log" 2>/dev/null || true
    fi

    # NPU 驱动日志
    if [[ -d "$NPU_DRIVER_DIR" ]]; then
        copy_with_time_filter "$NPU_DRIVER_DIR" "${dst}/driver"
        log_info "NPU 驱动日志已复制"
    fi

    # npu-smi 设备状态快照
    if command -v npu-smi &>/dev/null; then
        npu-smi info > "${dst}/npu_smi_info.txt" 2>/dev/null || true
        log_info "npu-smi 状态快照已保存"
    else
        log_warn "npu-smi 命令不可用，跳过设备状态采集"
    fi

    # 系统资源快照
    free -h > "${dst}/memory.txt" 2>/dev/null || true
    df -h  > "${dst}/disk.txt"   2>/dev/null || true
    ps aux > "${dst}/processes.txt" 2>/dev/null || true

    log_info "宿主机日志已保存到 ${dst}"
}

# ===================== 采集 plog =====================
collect_plog() {
    log_info "开始采集 plog 日志..."
    local dst="${OUTPUT_DIR}/plog"
    mkdir -p "$dst"

    # 支持自定义 ASCEND_LOG_PATH
    local actual_plog_dir="${ASCEND_LOG_PATH:-$PLOG_DIR}"

    if [[ -d "$actual_plog_dir" ]]; then
        copy_with_time_filter "$actual_plog_dir" "$dst"
        log_info "plog 日志已复制到 ${dst}"
    else
        log_warn "未找到 plog 目录：${actual_plog_dir}"
    fi

    # 采集 IR 图文件（图编译产物）
    local ir_dst="${dst}/ir"
    mkdir -p "$ir_dst"
    find "${HOME}/ascend/" -name "*.ir" -o -name "*.dot" 2>/dev/null \
        | head -50 | xargs -I{} cp {} "$ir_dst/" 2>/dev/null || true
}

# ===================== 主流程 =====================
log_info "===== Ascend NPU 日志采集脚本 ====="
log_info "输出目录：${OUTPUT_DIR}"
[[ -n "$START_TIME" ]] && log_info "时间范围：${START_TIME} ~ ${END_TIME}"

mkdir -p "$OUTPUT_DIR"

$COLLECT_MSNPUREPROT && collect_msnpureprot
$COLLECT_HOST        && collect_host
$COLLECT_PLOG        && collect_plog

# 生成采集清单
find "$OUTPUT_DIR" -type f | sort > "${OUTPUT_DIR}/manifest.txt"
log_info "采集完成，清单已写入 ${OUTPUT_DIR}/manifest.txt"
log_info "共采集文件：$(wc -l < "${OUTPUT_DIR}/manifest.txt") 个"
