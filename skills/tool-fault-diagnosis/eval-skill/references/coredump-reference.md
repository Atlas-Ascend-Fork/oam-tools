# Coredump 专项诊断参考

本页提供 core 关联、保存条件和通信伴随信号的解释。诊断主流程及责任边界统一见
[进程中断处理流](fault-flows/crash-flow.md)，离线命令见
[Coredump 命令手册](coredump-command-playbook.md)。只分析已有材料，不修改现场
配置、附加运行进程或重新触发崩溃。

## 来源与材料关联

| 材料 | 核对内容 |
| --- | --- |
| Host Linux core | exe、架构、PID/线程、信号、时间、映射、build-id与符号 |
| Host tracer Stackcore | 实际来源、采样/异常类型、线程与解析工具；不直接套 Host Linux core 开关 |
| Device Stackcore | Device、组件、subProcPid、故障时窗及适用解析工具 |
| stdout / plog / device / atrace / message | 本次任务的异常、正常进展、退出及清理顺序 |
| 容器/系统/调度记录 | 退出状态、信号来源、OOM Kill、取消或其他外部终止 |
| 已有配置与保存记录 | 故障进程实际限制、转储处理器、存储、导出及清理范围 |

按同一作业、PID/rank/Device、任务和时间窗关联，不用目录中的任意 core 解释
本次错误。跨主机比较需时钟依据，未校准时保留局部顺序。

Device 导出中可从 `slog/dev-os-*/debug/device-os/` 查组件与 `subProcPid`，再在
`stackcore/dev-os-*/` 匹配文件，如 `stackcore.aicpu_scheduler.<pid>.*`。PID 可复用，
须同时核对时间与设备；文件存在只证明已有产物，不证明根因已定位。

## 离线解析

符号、exe/so、core 的架构、版本、build-id 和加载映射匹配后，再解释故障线程、
PC、寄存器和调用链。`??` 可能来自符号缺失、错误配对、优化或栈损坏，不能
直接跳过或当作某一种根因。工具解析失败本身也不是业务故障原因。

部分版本的 Device 组件库可能来自 OPP 的
`Ascend910-aicpu_syskernels.tar.gz`、`Ascend910-aicpu_extend_syskernels.tar.gz`，
或驱动包 `filesystem-le.cpio.gz`；这些是查找线索，不保证适用于所有产品。
已有 `stackview.sh` 的参数先按其版本帮助核对，使用独立解析目录，不能将生产
运行库替换成调试库。二进制 core 按字节保留，不通过终端文本复制。

## Core 生成与保存条件

没有 core 文件不能直接反推未开开关。先区分 Host Linux core、Host tracer
Stackcore 和 Device Stackcore，再核对实际生成、保存、导出与清理链路。

| 核对项 | 解释与边界 |
| --- | --- |
| Host 进程 dumpable / 权限 | 核对故障进程状态及权限变化；`suid_dumpable` 针对受保护进程，普通可 dump 进程不要求设置为1 |
| `core_pattern` 直接文件模式 | 核对实际模板、目录权限、命名、文件/空间限制和写入失败；`core.%t.%e.%p` 仅为示例，不是必需格式 |
| `core_pattern` 管道模式 | 以 `|` 开头表示交给用户态处理器；按内核/处理器版本核对保存位置、过滤、限额和失败记录，不因未写模板目录判失败 |
| 故障进程实际 RLIMIT | 读取进程/服务实际限制，不能用当前终端的 `ulimit -c` 代替；直接文件模式的有限上限可允许生成，但完整性仍需检查；管道模式对该限制的处理不同 |
| 信号与转储条件 | 确认是否实际发生可转储的中断、信号处理及已有生成记录；SIGKILL 不生成信号 core，其他材料仍可支持退出诊断 |
| Device/Host tracer 配置 | 按真实来源和版本核对，不能用 Host Linux 的 `suid_dumpable` 或 RLIMIT 解释所有 Stackcore 缺失 |
| 收集覆盖 | 核对处理器存储、namespace/路径、导出范围、清理及保留记录；未收集不等于未生成 |

只有已关联的配置或失败记录证明本次转储受阻时，才确认缺失原因；否则记录
具体缺口。新的配置或复现仅作为后续验证建议，不由离线诊断自行执行。

## 通信与清理信号

| 信号 | 解释与后续核对 |
| --- | --- |
| `E39999` | 核对具体详情和现场版本，关联 Device 进程异常；单码及无 deviceos ERROR 不确认 core |
| `HDC send err ret(25)` / `hdc recv error 25` | 核对该版本返回码和会话详情；关闭状态不证明正常/异常原因或谁先关闭 |
| `-25` / `session has been closed` / `Server destroy success` | 回查对应会话的正常销毁、取消、异常和进程活动，不直接排除 Host 路径 |
| `GEfinalize` / `GEFinalize` / `Destructor` | 对应组件/对象的清理线索，不等于进程退出或退出原因 |
| `error cqe status: 0x15` | 按适用版本解码 CQE/重试状态，关联实际端点、QP/连接、通信域和操作；不单码确认交换机、链路或对端退出 |
| `cqe error status[12]` | 独立保留原码与详情；如包含 `localIP`/`remoteIP`，用于端点关联，不能与0x15或其他层状态混为一个定义 |
| `status[ERROR CQE]` / `status[LOST]` / `by rank` | 关联参与者和故障窗口，按实体及同次操作去重；次数或最高频IP不直接确定故障设备 |

沿 `localIP`/`remoteIP` 结合 rank/连接映射查对端进展。若真实退出记录和依赖
证明对端先失去推进能力，追其退出原因；对端对象 `Destructor` 早于本端 CQE
只提示可能的清理顺序，不证明整个进程已退出，也不排除同时存在网络异常。
缺少 `Destructor` 不证明对端存活，时刻晚于报错也不直接确认网络故障。

链路闪断、心跳、丢包、拥塞、错包及交换机候选按本次端点、路径、协议、负载
和故障窗口与已有诊断/告警互证，详见 [网络处理流](fault-flows/network-flow.md)。
网络检测通过只限所测范围；CQE 或心跳失败自身不能补齐未测路径。

## 机制索引

CD001-CD007 保留为机制检索编号，没有完整原始现场、修复和复跑记录，不能
直接作为本次故障已命中已验证案例的证据。

| 编号 | 方向 | 区分所需证据 |
| --- | --- | --- |
| CD001 | Device/AICPU 中断 | 匹配进程异常、信号或 Stackcore，继续查故障指令和输入 |
| CD002 | HDC 关闭伴随异常 | 会话、任务及真实活动/退出记录，区分正常清理与异常传播 |
| CD003 | 对端退出使本端通信失败 | 实际退出、对应依赖、可用时序与退出原因；不凭 Destructor 排网络 |
| CD004 | 丢包/交换机候选 | 匹配故障负载和路径的计数、告警或诊断；无 Destructor 与 LOST 高频不闭合根因 |
| CD005 | TDT 相关 Device 中断 | 组件、subProcPid、时间窗、core与版本匹配，帧归属不直接定责 |
| CD006 | core 材料缺失 | 生成、保存、导出/清理链路的实际记录；见上文保存条件 |
| CD007 | 心跳/链路候选 | 端点/链路和同次操作对应的状态、告警及业务进展，区分退出与链路失败 |

## 结论与验证

没有 core、部分符号或对端日志时，继续交付已证实中断/通信事实、具体候选与
缺口。当前栈只定位直接执行点，责任组件还需参数、生命周期或上游写入证据。
未执行的修复和回归写为计划，实际通过才限定已验证范围。

相关：[Crash 参考](crash-reference.md)、[通信等待流](fault-flows/hang-flow.md)、
[崩溃报告模板](coredump-report-template.md)、[公共约定](fault-flows/common-flow.md)。
