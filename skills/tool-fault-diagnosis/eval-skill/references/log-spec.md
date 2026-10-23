# CANN 日志规范

> 本文档提供常见日志格式和分析索引；具体字段、路径、默认值及行为需与现场版本、部署形态对应。下文简化序列是机制示意，不是所有版本都会打印的固定日志。
> 官方参考：[日志简介（社区版 9.0.0-beta.2）](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/maintenref/logreference/logreference_0001.html) / [查看日志（Ascend EP）](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/maintenref/logreference/logreference_0002.html)

## 通用日志格式

### 标准行格式（官方定义）

```
[Level] ModuleName(PID,PName):DateTimeMS [FileName:LineNumber]LogContent
```

**实际示例：**
```
[ERROR] TEFUSION(12940,atc):2021-10-17-05:54:07.599.074 [tensor_engine/te_fusion/pywrapper.cc:33]InitPyLogger Failed to import te.platform.log_util
```

| 字段 | 说明 | 示例 |
|------|------|------|
| `Level` | 日志级别：ERROR / WARNING / INFO / DEBUG | `[ERROR]` |
| `ModuleName` | 产生日志的模块名称 | `TEFUSION`、`GE`、`HCCL` |
| `PID` | 模块进程 ID | `12940` |
| `PName` | 模块进程名称 | `atc` |
| `DateTimeMS` | 日志打印时间，格式 `yyyy-mm-dd-hh:mm:ss.fff.zzz`（年-月-日-时:分:秒:毫秒:微秒） | `2021-10-17-05:54:07.599.074` |
| `FileName:LineNumber` | 调用日志打印接口的源码文件名及行号 | `pywrapper.cc:33` |
| `LogContent` | 各模块具体日志内容 | `InitPyLogger Failed to import te.platform.log_util` |

### 常见模块名称

| ModuleName | 模块 |
|------|------|
| `GE` | Graph Engine（图编译与调度） |
| `TBE` / `TE` / `TEFUSION` | TBE 算子编译器 / TE Fusion |
| `ACL` | ACL 设备管理接口 |
| `HCCL` | 集合通信库 |
| `SCHE` / `RUNTIME` | 任务调度器 / 运行时 |
| `AICPU` | AI CPU 算子执行进程 |
| `HCCP` | HCCL 代理进程 |
| `PROF` | Profiling 模块 |

---

## 日志分类与路径（Ascend EP 形态）

> **日志分类**：应用类日志（AI 应用程序产生）和系统类日志（Device 侧系统运行信息）。
> 系统类日志需用 `msnpureport` 工具导出到 Host 侧查看。

### 应用类日志路径

```
$HOME/ascend/log/
├── debug/
│   ├── device-<id>/
│   │   └── device-<pid>_<timestamp>.log   # Device 侧调试日志（AI CPU、HCCP 等）
│   └── plog/
│       └── plog-<pid>_<timestamp>.log     # Host 侧调试日志（GE/FE/TBE/HCCL/Runtime 等）
├── run/
│   ├── device-<id>/
│   │   └── device-<pid>_<timestamp>.log   # Device 侧运行日志
│   └── plog/
│       └── plog-<pid>_<timestamp>.log     # Host 侧运行日志
└── security/
    ├── device-<id>/
    │   └── device-<pid>_<timestamp>.log   # Device 侧安全日志
    └── plog/
        └── plog-<pid>_<timestamp>.log     # Host 侧安全日志
```

| 路径 | 主要内容 | 关键模块 |
|------|---------|--------|
| `debug/plog/plog-<pid>_*.log` | Host 侧调试日志 | GE、FE、AI CPU、TBE/HCCL（compiler）；AscendCL、GE、Runtime、Driver 用户态（runtime） |
| `run/plog/plog-<pid>_*.log` | Host 侧运行日志 | 同上（运行级别） |
| `debug/device-<id>/device-<pid>_*.log` | Device 侧调试日志 | AI CPU、HCCP 等 Device 侧组件 |
| `run/device-<id>/device-<pid>_*.log` | Device 侧运行日志 | 同上（运行级别） |

> Device应用日志的回传与落盘取决于版本、配置及服务状态。容器内的设备可见性和权限也需核对；缺少系统日志时检查Host侧导出，不把容器内缺文件当作设备没有报错。

### 相关环境变量

| 环境变量 | 作用 | 示例 |
|---------|------|------|
| `ASCEND_GLOBAL_LOG_LEVEL` | 设置全局日志级别（0=DEBUG, 1=INFO, 2=WARNING, 3=ERROR） | `export ASCEND_GLOBAL_LOG_LEVEL=1` |
| `ASCEND_PROCESS_LOG_PATH` | 指定应用类日志落盘路径 | `export ASCEND_PROCESS_LOG_PATH=/data/logs` |
| `ASCEND_SLOG_PRINT_TO_STDOUT` | 同时将日志打印到屏幕（1=开启） | `export ASCEND_SLOG_PRINT_TO_STDOUT=1` |
| `ASCEND_HOST_LOG_FILE_NUM` | Host日志文件留存数量；核对版本定义及有效值 | `export ASCEND_HOST_LOG_FILE_NUM=50` |
| `ASCEND_LOG_DEVICE_FLUSH_TIMEOUT` | Device日志回传超时；核对版本支持及单位后设置 | 按现场版本文档配置 |
| `ASCEND_LOG_SYNC_SAVE` | 日志拥塞时不丢弃日志（1=开启，影响性能） | `export ASCEND_LOG_SYNC_SAVE=1` |
| `ASCEND_WORK_PATH` | 设置单机独享文件（含日志）的存储路径 | `export ASCEND_WORK_PATH=/workspace/rank0` |

---

## plog 日志规范

### 文件命名

```
plog-<pid>_<timestamp>.log
```
示例：`plog-16027_20220618001623878.log`

### 关键日志序列（正常执行）

```
[INFO][GE] Build graph start, graph_id=1
[INFO][GE] Graph optimize success
[INFO][TBE] Start compile op: MatMulV2, shape=[1024,1024]x[1024,512]
[INFO][TBE] Compile op success: MatMulV2, cost=234ms
[INFO][GE] Load graph to device success, graph_id=1
[INFO][SCHE] Dispatch task, task_id=100, stream_id=3, op=MatMulV2
[INFO][SCHE] Task done, task_id=100, retcode=0, time_cost=1.23ms
```

### 关键字段

| 字段名 | 示例 | 含义 |
|--------|------|------|
| `graph_id` | `graph_id=1` | 图标识；结合进程、会话和生命周期解释，不代表图数量 |
| `task_id` | `task_id=100` | 任务标识；结合设备、流、进程和生命周期关联，不是全局唯一或任务数量 |
| `stream_id` | `stream_id=3` | 执行流编号（并行流） |
| `op` / `op_type` | `op=MatMulV2` | 算子类型名称 |
| `shape` | `shape=[1024,1024]` | Tensor 维度 |
| `dtype` | `dtype=FP16` | 数据类型 |
| `retcode` | `retcode=0` | 返回码（0=成功） |
| `time_cost` | `time_cost=1.23ms` | 执行耗时 |
| `cost` | `cost=234ms` | 编译耗时 |

---

## msnpureport 导出材料

`msnpureport`是Device系统日志和其他维测信息导出工具，不是协议名。
本技能的`msnpureprot`仅为采集脚本旧参数/目录名。导出方式见[全量采集流程](../../collect-skill/references/full-log-collection.md)。

导出目录中的日志由Driver、Firmware、系统进程等不同组件产生，各有格式；Stackcore等二进制材料另需匹配的解析工具。保留原文件及来源层级，按实际字段关联设备和进程。设备ID范围取现场清单，不固定为0～7；不能虚构一套统一的Send/Recv协议日志作为缺失证据。

---

## host 日志规范

### dmesg / syslog 关键模式

| 模式 | 含义 |
|------|------|
| `ascend: device 0 reset` | 设备 0 发生复位（严重） |
| `npu driver loaded` | 驱动加载成功 |
| `Out of memory: Kill process` | 宿主机 OOM，进程被杀 |
| `HCCL rank X disconnected` | 通信 rank X 断联 |

---

## 日志时序关系

```
宿主机时间       设备时间（偏移与漂移需核对）
    │                   │
    ├── Send cmd ───────►│
    │                   ├── Execute op
    │                   │    (time_cost)
    │◄─── Notify ───────┤
    │
  Host观测跨度与Device执行时间分别定义和计算
```

> **注意**：先核对时钟来源、时区、同步/偏移、缓冲与异步上报。没有校准或关联事件时，不能将跨端时间戳直接排序为因果链。即使时间可比，首尾日志跨度也不等于kernel时长；使用匹配的开始/结束事件及同口径计时。

---

## 日志留存与轮转

记录实际版本、有效日志路径、文件大小/数量配置及运行时环境变量。各组件可能采用不同轮转策略，不能用统一大小和保留数量解释日志缺失。本仓`src/asys/launch/asys_launch.py`还会设置`ASCEND_HOST_LOG_FILE_NUM=1000`，说明采集/复跑工具可能覆盖常规配置。

盘点全部相关轮转和压缩文件，检查故障前后覆盖、运行用户与采集范围。文件缺失只说明当前材料不可见；需有轮转记录或配置/时间覆盖证据才归因为轮转，不能据此认定没有更早错误。
