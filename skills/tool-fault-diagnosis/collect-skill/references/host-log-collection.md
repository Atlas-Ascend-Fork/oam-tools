# 宿主机日志采集规范

## 概述

宿主机日志（host logs）记录 Ascend NPU 运行时的操作系统层面信息，包括设备驱动加载状态、内存分配、进程调度、网络通信（HCCL）等。在排查训练崩溃、OOM、通信超时等问题时不可或缺。

## 日志来源

| 来源 | 路径 | 说明 |
|------|------|------|
| 系统 syslog | `/var/log/syslog` 或 `/var/log/messages` | 内核驱动事件、设备挂载 |
| NPU 驱动日志 | `/var/log/npu/driver/` | Ascend 驱动层事件 |
| HCCL 通信日志 | `./hccl_logs/` 或 `$ASCEND_HOME/log/hccl/` | 多卡通信日志 |
| 应用进程日志 | 任务工作目录下的 `stdout`/`stderr` | 训练框架输出 |
| dmesg | 内核环形缓冲区 | 驱动故障、硬件错误 |

## 采集命令

```bash
# 采集系统日志（最近 500 行）
journalctl -n 500 --no-pager > ./logs/host/journalctl.log

# 或从文件复制
cp /var/log/syslog ./logs/host/syslog.log

# 采集 dmesg（过滤 npu/ascend 相关）
dmesg | grep -iE "npu|ascend|davinci|hisi" > ./logs/host/dmesg_npu.log

# 采集 NPU 驱动日志
cp -r /var/log/npu/driver/ ./logs/host/driver/

# 查看设备状态（快照）
npu-smi info > ./logs/host/npu_smi_info.txt
npu-smi info -t board -i 0 >> ./logs/host/npu_smi_info.txt

# 采集 HCCL 日志（若已执行 collect.sh --msnpureprot，可优先从 [INFO] CANN 日志已从 <path> 复制到 ... 输出确认实际目录）
cp -r ./hccl_logs/ ./logs/host/hccl/ 2>/dev/null || {
  hccl_src=""
  for base in "${CANN_HOME:-}" "${ASCEND_INSTALL_PATH:-}" "${ASCEND_HOME_PATH:-}" \
              /usr/local/Ascend /usr/local/Ascend/ascend-toolkit/latest \
              "$HOME/Ascend" "$HOME/Ascend/ascend-toolkit/latest"; do
    [ -n "$base" ] || continue
    for cand in "$base/log/hccl" "$base/cann/log/hccl" "$base/ascend-toolkit/latest/log/hccl"; do
      [ -d "$cand" ] && hccl_src="$cand" && break 2
    done
  done
  if [ -n "$hccl_src" ]; then
    cp -r "$hccl_src/" ./logs/host/hccl/
  else
    echo "[WARN] 未找到 HCCL 日志目录（可设置 CANN_HOME / ASCEND_INSTALL_PATH / ASCEND_HOME_PATH，或先执行 collect.sh --msnpureprot）" >&2
  fi
}

# 进程资源快照
ps aux | grep -E "python|train|ascend" > ./logs/host/processes.txt
free -h > ./logs/host/memory.txt
df -h > ./logs/host/disk.txt
```

## 关键检查项

| 检查项 | 排查命令 | 异常特征 |
|--------|----------|----------|
| 设备是否在线 | `npu-smi info` | device 状态非 OK |
| 内存是否溢出 | `free -h` + syslog OOM 关键字 | `Out of memory` |
| 驱动版本匹配 | `npu-smi info -t board` | 驱动与 CANN 版本不匹配 |
| 温度/功耗异常 | `npu-smi info -t temp` | 温度 > 85°C |
| 通信超时 | HCCL 日志中 `timeout` | rank 间同步超时 |

## 权限说明

- dmesg：通常需要 root 权限（或 `sudo dmesg`）
- `/var/log/npu/driver/`：需要 root 或 HwHiAiUser 用户组
- npu-smi：需要 HwHiAiUser 用户组或 root

## 注意事项

- 多机训练时，每台宿主机都需要单独采集
- 采集完成后统一放入 `./logs/host/<hostname>/` 目录便于区分
