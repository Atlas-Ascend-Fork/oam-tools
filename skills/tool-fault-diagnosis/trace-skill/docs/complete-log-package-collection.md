# CANN 9.x 故障日志包获取建议

> 核验时间：2026-09-07。本文优先采用华为昇腾官方 CANN 9.0.X 文档和华为官方 `cann/driver` 仓库。命令与目录仍应以故障环境中实际安装的 CANN、Toolkit、Driver 版本为准。

## 结论

不存在一个在所有部署形态中都能保证取得“完整 Host/Device 调用链”的单一日志包。

- **对 `trace-skill` 获取验收样本的稳定基线**：合并同一次复现的 Host 应用日志、CANN Trace、Host OS message/syslog，以及在 Host 物理机执行 `msnpureport` 得到的 Device 包。这样不会把单一工具的适用范围误认为全部数据来源。
- **EP 标准形态、物理机、Toolkit 已安装且现场版本确认提供 asys**：可以在复现前使用 `asys launch` 代为组织上述来源。它会收集 Host CANN 日志、Host message/syslog、Device 日志、Trace 落盘文件、软硬件状态及可选 dump/算子信息，但仍要检查产物清单是否齐全。
- **业务已经故障且不能复跑**：执行 `asys collect`，但它只能收集当时仍存在且可被当前权限、环境变量定位到的内容。
- **容器、集群、虚拟机、云场景，或没有 asys**：采用手工合包。至少合并同一次复现的 Host 应用日志、CANN Trace 和在 Host 物理机执行 `msnpureport` 得到的 Device 包；Host OS 的 syslog/message 也应一并取得。
- **不要把 `msnpureport` 包当成完整业务日志包**：它不负责 Host AscendCL/GE/Runtime/HCCL 的应用 `plog`，也不负责 CANN `$HOME/ascend/atrace` Trace。它的主范围是 Device 系统类日志、黑匣子/stackcore/事件调度等维测信息，以及 Host 驱动内核日志。

官方依据：[CANN 9.0.X 收集 AI Core Error 问题信息](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/troubleshooting/troubleshooting_0006.html)、[asys 功能及约束](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/troubleshooting/troubleshooting_0096.html)、[msnpureport 简介（官方驱动仓）](https://gitcode.com/cann/driver/blob/master/docs/zh/msnpureport/description.md)。

## 推荐获取方式

### 方式一：手工合包，作为跨版本的稳定基线

手工步骤见下文“手工合包的具体步骤”。其核心是同次复现、同一业务进程、四类来源一起保留：Host 应用日志、CANN Trace、Host OS 日志、`msnpureport` Device 包。

### 方式二：复现前用 `asys launch`，仅适用于现场版本明确支持的 EP 物理机

前提是运行环境已安装 Toolkit，并由 CANN 运行用户加载环境：

```sh
source /usr/local/Ascend/cann/set_env.sh
asys launch --task="sh ../run.sh" --tar=True --output=$HOME/dfx_info
```

实际安装路径不是 `/usr/local/Ascend/cann` 时，应使用对应 `${INSTALL_DIR}/set_env.sh`。`--task` 中必须是可感知结束点的前台命令；业务脚本内部用 `&` 直接转后台的方式不受支持。

`asys launch` 会临时设置 `NPU_COLLECT_PATH`、`ASCEND_PROCESS_LOG_PATH`、`ASCEND_HOST_LOG_FILE_NUM` 和 `ASCEND_WORK_PATH`。默认配置包括 `log_level=INFO`、`log_event_enable=TRUE`、`log_print_to_stdout=FALSE`，还会默认开启算子编译文件和 GE/TF Adapter dump 图收集。业务脚本如果再次覆盖这些环境变量，可能使对应信息无法收集。

官方依据：[asys 环境准备](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/troubleshooting/troubleshooting_0097.html)、[业务复跑 + 故障信息收集](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/troubleshooting/troubleshooting_0502.html)。

### 方式三：故障后用 `asys collect`

```sh
source /usr/local/Ascend/cann/set_env.sh
asys collect --tar=True --output=$HOME/dfx_info
```

如已知 dump 和算子编译文件所在目录，可增加 `--task_dir=$HOME/cache_path`。执行 `collect` 时，`ASCEND_PROCESS_LOG_PATH`、`NPU_COLLECT_PATH`、`DUMP_GRAPH_PATH`、`ASCEND_WORK_PATH`、`ASCEND_CACHE_PATH`、`ASCEND_CUSTOM_OPP_PATH` 等环境变量必须与业务运行时保持一致，否则自动发现结果可能不准确。

典型输出为 `${output}/asys_output_<timestamp>`，其中包括：

| 输出 | 主要内容 |
|---|---|
| `software_info.txt` | 安装包版本、环境变量、软件依赖、系统信息 |
| `hardware_info.txt` / `status_info.txt` / `health_result.txt` | Host/Device 硬件、状态和健康信息 |
| `dfx/log/host/cann` | Host CANN 应用类日志；是否包含所需 `run/debug/plog` 取决于原日志是否存在及是否可被环境变量定位 |
| `dfx/log/host/message` | Host message/syslog |
| `dfx/log/host/driver` | Host 驱动日志 |
| `dfx/log/device` | Device firmware、system、application、slogd、`dev-os-*` 等日志 |
| `dfx/atrace` | Trace 落盘文件及 Trace 二进制文件解析出的明文 |
| `dfx/bbox` / `stackcore` / `data-dump` / `graph` / `ops` | 黑匣子、core、异常 dump、图与算子编译信息 |

这意味着 **asys 是官方可用的一键组织方式**，但“一键”不等于“必然完整”：非 root 用户的 Device 固件、系统、黑匣子/stackcore/coretrace 等信息会受限；Trace 过多会延长扫描时间；旧日志可能已被覆盖；同一用户在同一时间段并发跑多个作业时，数据会交叉。

官方依据：[故障信息收集 `asys collect`](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/troubleshooting/troubleshooting_0501.html)、[asys 功能及约束](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/troubleshooting/troubleshooting_0096.html)。

### 手工合包的具体步骤

在复现前为同一次业务运行设置统一输出根目录：

```sh
mkdir -p "$HOME/aic_err_info"
export ASCEND_WORK_PATH="$HOME/aic_err_info"
export ASCEND_PROCESS_LOG_PATH="$HOME/aic_err_info/plog"
export NPU_COLLECT_PATH="$HOME/aic_err_info"
```

复现后应保留：

1. `ASCEND_PROCESS_LOG_PATH` 指定目录中的 Host 应用类日志；未设置时默认从 `$HOME/ascend/log` 获取。
2. `ASCEND_WORK_PATH` 下的 Trace；未设置时默认从 `$HOME/ascend/atrace` 获取。按进程取件时可用官方示例模式 `trace_{进程组pid}*`，避免混入其他作业。
3. Host 物理机上以 root 用户执行 `msnpureport` 得到的 Device 日志包。
4. Host OS message/syslog。`asys` 会把它放到 `dfx/log/host/message`；手工合包时需由环境管理员从同一故障时间窗口提供。
5. 若是 AI Core Error，还应保留 `NPU_COLLECT_PATH` 下的 `extra-info/data-dump/{device_id}`、异常算子 `.o/.json` 等信息。官方明确提示 `NPU_COLLECT_PATH` 会降低业务性能，不建议长期开启。

官方依据：[CANN 9.0.X 手工收集步骤](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/troubleshooting/troubleshooting_0006.html)、[CANN 9.0.X Trace 日志](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/logreference/logreference_0022.html)。

## `msnpureport` 的位置、命令和边界

### 工具位置

工具随昇腾驱动软件包部署，实际文件位于：

```text
<Driver安装目录>/driver/tools/msnpureport
```

驱动安装完成后通常可在任意目录直接运行。容器中需要显式配置时，官方示例为：

```sh
export PATH=/usr/local/Ascend/driver/tools:$PATH
```

官方依据：[msnpureport 简介](https://gitcode.com/cann/driver/blob/master/docs/zh/msnpureport/description.md)、[单次导出](https://gitcode.com/cann/driver/blob/master/docs/zh/msnpureport/export-device-logs-and-files/export-device-logs-and-files-at-one-time.md)。

### 命令

CANN 9.0.X 的 AI Core Error 手工收集页给出的命令是：

```sh
# 在 Host 上当前用户可写的安全目录中，以 root 执行
msnpureport -f
```

当前官方驱动仓的推荐形式是：

```sh
msnpureport report --force
```

当前文档同时保留 `msnpureport [options]` 兼容形式，所以 `msnpureport -f` 仍有文档依据。`-f/--force` 相比无参数导出，多包含黑匣子设备事件及黑匣子存储空间中的历史维测信息。输出写入**命令当前目录**下的时间戳目录，因此应先进入专门的、普通用户不可访问的安全目录。

需要在故障发生前持续保存 Device 日志、避免长任务轮转覆盖时，可在物理 Host 预先运行：

```sh
msnpureport report --permanent
```

结束时使用 `Ctrl+C` 或 `kill -15 <pid>`。持续导出仍可能因 Device 异常失败，不能视为绝对无损采集。

官方依据：[CANN 9.0.X 手工收集步骤](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/troubleshooting/troubleshooting_0006.html)、[单次导出](https://gitcode.com/cann/driver/blob/master/docs/zh/msnpureport/export-device-logs-and-files/export-device-logs-and-files-at-one-time.md)、[连续导出](https://gitcode.com/cann/driver/blob/master/docs/zh/msnpureport/export-device-logs-and-files/consecutively-export-device-logs-and-files.md)。

### 输出内容

`msnpureport -f` / `report --force` 的主要输出包括：

- `slog/dev-os-*/debug`、`run`、`event`、`security`、`slogd`：Device Control CPU/非 Control CPU、系统进程和未及时回传的 Device 应用日志。
- `hisi_logs`：黑匣子、设备事件和历史维测信息。
- `stackcore`：Device 进程 coredump 调用栈信息。
- `message`：**Device OS 系统日志**，不是 Host syslog。
- `system_info`：事件调度、HAL/proc、启动 dmesg、TEE 等，产品不同会有差异。
- `slog/host/host_kernel.log`：Host 驱动内核日志。

它不会替代 Host 应用 `plog`、Host OS syslog/message 或 CANN `atrace` 的单独采集。

### 权限和容器限制

- 单次导出命令按当前官方文档仅支持 root。
- 工具仅适用于 Ascend EP，虚拟化实例不支持。
- 普通容器中单次导出只支持 Host 驱动内核日志；其他 Device 日志不支持。特权容器例外，但更稳妥的做法仍是在 Host 物理机采集。
- 容器调用需加 `--docker`；普通容器看不到 syslog 时，`--print 1` 只会把 **msnpureport 自身维测输出**打印到终端，并不会补回缺失的 Host/Device syslog。
- `report --permanent` 普通容器不支持，特权容器例外。

官方依据：[msnpureport 使用约束](https://gitcode.com/cann/driver/blob/master/docs/zh/msnpureport/description.md)、[单次导出容器限制](https://gitcode.com/cann/driver/blob/master/docs/zh/msnpureport/export-device-logs-and-files/export-device-logs-and-files-at-one-time.md)、[`--print` 说明](https://gitcode.com/cann/driver/blob/master/docs/zh/msnpureport/config-maintenance-and-debug-logs-of-msnpureport/config-position-for-display.md)。

## Trace 和日志级别：复现前需要做什么

### Trace

CANN 9.0.X 官方说明中没有一个要求用户先开启的“Trace 总开关”。在 **Ascend EP 标准形态**中，软件栈维测信息在运行时记录于内存，在业务流程异常、进程崩溃/异常信号或正常退出时落盘。默认根目录是 `$HOME/ascend/atrace`；设置 `ASCEND_WORK_PATH` 可改变落盘根目录。

复现前真正需要保证的是：

- 在启动业务进程之前设置并记录 `ASCEND_WORK_PATH`，保证采集方知道 Trace 在哪里。
- 不要在故障后才设置路径，因为环境变量必须由产生日志的业务进程继承。
- 长期或高并发环境按需配置 `ASCEND_TRACE_RECORD_NUM` 的老化规格；Device 日志回传延迟问题可按官方环境变量参考配置 `ASCEND_LOG_DEVICE_FLUSH_TIMEOUT`。本文不指定任意数值，应按安装版本的环境变量约束设置。
- Trace 仅支持 Ascend EP 标准形态；其他形态不能把“没有 atrace”直接判断为采集失败。

官方依据：[查看 Trace 日志](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/logreference/logreference_0022.html)。

### Host 应用日志级别

初次复现无需无条件把所有模块提升到 `DEBUG`。官方 `asys launch` 默认使用 `INFO`，并开启 EVENT 日志；这是更合适的基线。只有已有定位假设、明确需要某模块更细粒度记录并评估性能/磁盘影响后，再按安装版本的环境变量参考提高日志级别。

对于 `trace-skill` 验收，关键不是“日志越多越好”，而是一次复现中同时获得：

- Host AscendCL/GE/Runtime/HCCL 应用日志，且保留微秒时间、PID/TID、stream/task 等可用关联字段；
- `$HOME/ascend/atrace` 或 `ASCEND_WORK_PATH` 对应 Trace；
- Device 系统/事件/调试日志与 `host_kernel.log`；
- Host message/syslog；
- 能证明 Host 下发、Device 执行、Host 返回属于同一调用的关联标识。

官方日志分类说明 Host 应用类日志包括 AscendCL、GE、Runtime、HCCL，Device 应用类日志包括 AI CPU；Trace 是独立机制，不能仅根据 `plog` 推定其已包含 Trace。[日志简介](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/maintenref/logreference/logreference_0001.html)

## 版本差异与未确定项

- 本文的 CANN 主流程来自 **CANN Community Edition 9.0.X**。用户提供的 `canncommercial/latest` 链接会随最新商用文档变化，不能作为固定版本链接。
- CANN 9.0.X 故障页使用旧式 `msnpureport -f`；当前官方 `cann/driver` 主干推荐 `msnpureport report --force`。两种语法在当前驱动文档中均有说明，但现场应执行 `msnpureport --help` 并以安装驱动版本为准。
- 当前驱动主干文档覆盖的产品比早期 CANN 9.0 文档更多；`-t` 类型、Device ID 是物理 ID 还是逻辑 ID、vmcore/UB/AO 等目录均有产品差异，不应写死在解析器中。
- 官方资料没有承诺每个日志事件都带齐 `stream_id/task_id`，也没有承诺 Host/Device 时钟天然同步。即使采集成功，仍可能只能生成部分调用链。
- `asys` 输出目录中明确有 `dfx/atrace`，但它只能收集已成功落盘且可发现的 Trace；“目录存在”不等于“本次故障一定有完整 Trace”。

## 给日志提供方的最小请求模板

请提供同一次故障复现产生的完整目录/压缩包，并注明 CANN、Toolkit、Driver、固件版本，硬件型号，容器/物理机形态，复现命令，故障时间与时区：

1. 稳定基线是同时提供 `$HOME/ascend/log`（或 `ASCEND_PROCESS_LOG_PATH`）、`$HOME/ascend/atrace`（或 `ASCEND_WORK_PATH`）、Host 物理机上 root 执行 `msnpureport -f`/`report --force` 的完整时间戳目录，以及 Host message/syslog 的故障时间窗口。
2. 现场版本已确认支持 asys 的 EP 物理机，也可提供 `asys launch --task="<前台复现命令>" --tar=True --output=<目录>` 生成的完整 `asys_output_<timestamp>.tar.gz`，但应先按本文产物表检查四类关键来源是否齐全。
3. 不要只摘取 ERROR 行；保留轮转文件、目录结构和时间戳。对外传输前可脱敏用户名、主机名、IP 和业务路径，但应稳定保留或匿名映射 PID/TID、device/stream/task/event ID 等关联键。
