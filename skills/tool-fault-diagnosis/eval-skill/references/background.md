# CANN 日志分析背景介绍

本文提供组件和执行阶段的索引。硬件规格、日志格式及 API 行为需要与现场型号和软件版本对应。

## 先核对平台

| 信息 | 核对方式与诊断用途 |
|------|--------------------|
| NPU 型号、设备与可见资源 | 现场 `npu-smi`、asys 的 hardware/status 信息；区分物理设备与进程可见设备 |
| Host CPU 架构 | Host OS 信息；不能由 Ascend NPU 推定宿主机一定为 aarch64 |
| AI Core / AI Vector Core、UB 等片上存储 | 对应型号的平台信息及编译目标；不通用假设48核或256KB UB |
| HBM 容量、带宽及支持的数据类型 | 对应型号和数据类型的规格，结合现场可用容量、配额及有效配置 |
| CANN、Driver、Firmware、框架及插件版本 | 安装记录、实际加载库和构建目标；不能仅由安装目录名认定运行版本 |

本仓 asys 的现场信息结构见 oam-tools 的`docs/zh/user_guide/asys/rerun_fault_information_collection.md`。已有产物可以直接读取；复跑需属于当前任务范围。

## 软件栈与日志线索

应用可能通过框架、图执行或单算子接口使用 CANN。并非每次故障都经过全部组件。

| 组件 | 作用 | 常见日志线索 |
|------|------|--------------|
| GE（Graph Engine） | 图优化、编译、加载和执行管理 | 图ID、编译阶段、内存规划与图执行错误 |
| TBE / Ascend C 等算子工具链 | 生成面向目标芯片的算子产物 | shape/dtype约束、编译目标、tiling及产物hash |
| AscendCL / Runtime | 设备、上下文、流、任务、内存与执行接口 | API返回码、device/stream/task、任务异常及同步报错 |
| HCCL | AllReduce、AllGather、Broadcast、ReduceScatter等集合通信 | rank、通信域、操作序列、建链与执行阶段 |
| HIXL / LLM-DataDist | 单边点对点传输 / KV Cache 数据传输 | engine/endpoint、协议、建链请求/响应、底层通道和传输完成；见[HIXL参考](hixl-reference.md) |
| Driver / Firmware | 设备管理、资源与异常上报 | 驱动返回值、设备事件、RAS/ECC及恢复记录 |

HCCL 的传输路径随设备和拓扑变化；建链超时与执行超时分别核对现场配置及版本定义，不能统一写成默认120秒。等待方报超时还需回查对端进展、退出及更早错误。

### msnpureport 与本技能的旧命名

`msnpureport` 是导出 Device 系统日志和其他维测信息的工具，不是通信协议。
本技能 `collect.sh --msnpureprot` 和 `logs/msnpureprot/` 是沿用的本地复制参数/目录名；它们不会自动执行该工具。
实际导出方式见[全量采集流程](../../collect-skill/references/full-log-collection.md)，先核对现场工具帮助。
导出产物的日志来源、设备范围和文件类型需逐一确认，不能把全部内容当成算子下发/完成轨迹。

## 执行阶段与诊断方向

| 已观察到的阶段或现象 | 继续核对的证据 |
|--------------------|----------------|
| 图/算子编译失败 | 首个具体约束、输入shape/dtype、编译目标及匹配源码 |
| 图加载或内存申请失败 | 请求大小、资源类型、同口径可用量、配额和对象生命周期 |
| AI Core执行异常 | 内嵌errorStr、分名寄存器、任务关联与匹配产物；同步API可能只是上报位置 |
| 通信等待或无输出 | 各rank进展、相同通信序列、对端退出及超时阶段 |
| NaN或精度不达标 | 首次异常位置、输入范围、计算/累加类型、参考值和业务容限 |
| 性能下降 | 同条件基线与profiling关键路径，区分Host、计算、访存、通信及同步 |

这些是调查入口，不构成唯一根因。错误码、局部资源统计与正常清理均应放回同一故障事件解释。
