# 进程卡住与关联通信超时处理流

> **执行入口**：入口场景 `hang`；`comm_timeout` 复用本流的通信分支并保留原场景 ID。仅分析已有日志、堆栈、配置、采样与验证记录，不执行 `asys stack`、进程附加、信号注入、连通性探测或新 profiling。超时类型分流转为在已有日志中按首报错归类超时类型。需要清洗或流水线产物时查 [公共约定](common-flow.md)。

## 问题现象

常见入口包括：

```text
[INFO] step=1000, loss=2.345   # 之后无新输出
[ERROR][HCCL] EI0002 Communication_Error_Timeout
[ERROR] EE1002 Execution_Error_Stream_Synchronize_Timeout
[ERROR] EE9999 Event Wait Timeout
no progress for 300s
deadlock detected
```

进程仍存在、低 CPU 或长期无新日志是等待线索；须结合观察窗口和进展记录判断是否卡住。超时类问题分为 Host 侧超时与 Device 侧超时两大类。

## 排查流程

超时类问题定位流程主干：**找到首报错 → 首报错是哪种超时 → 按超时类型进入对应子流程**。

```mermaid
flowchart TD
    A[找到首报错] --> B{首报错是哪种超时}
    B -->|框架层超时/HCCL拓扑探测超时| C[Host 侧超时子流程]
    B -->|明确 socket 建链超时| D[建链超时子流程]
    B -->|EE1002 流同步超时| E[流同步超时子流程]
    B -->|明确 Notify Wait 超时| F[Notify Wait 超时子流程]
    B -->|明确 Event Wait 超时| G[Event Wait 超时子流程]
    C --> C1{框架超时 or HCCL拓扑超时}
    C1 -->|框架超时| C2[核对 Master/Scheduler/TcpStore 连接记录]
    C1 -->|HCCL拓扑超时| C3[核对 rank_table/防火墙/端口/网卡配置]
    D --> D1{排查链路/网络是否有异常}
    D1 -->|是| D2[转网络排查流]
    D1 -->|否| D3[找到报错链路本端和对端]
    D3 --> D4[排查卡间不一致/软件问题]
    E --> E1{排查网络问题}
    E1 -->|是| E2[转网络排查流]
    E1 -->|否| E3{是否全量超时}
    E3 -->|全量| E4[核对同次操作的进入/进展/超时与生效预算]
    E3 -->|非全量| E5[核对不报超时的卡是否少下发通信算子]
    F --> F1{排查网络问题}
    F1 -->|是| F2[转网络排查流]
    F1 -->|否| F3{是否全量超时}
    F3 -->|全量| F4[核对同次操作的依赖/进展与生效预算]
    F3 -->|非全量| F5[核对不报超时的卡是否少下发通信算子]
    G --> G1{是否全量超时}
    G1 -->|全量| G2[关联 Record/Notify 依赖及各阶段预算]
    G1 -->|非全量| G3[核对其他 rank 的进展/退出/错误, 保留首错候选]
```

| 顺序 | 证据 | 判断条件 | 下一步 | 中间过程记录 |
| --- | --- | --- | --- | --- |
| 1 | plog/应用日志首报错 | 超时类型归类 | 进入对应子流程 | 记录首报错原文、错误码、超时类型、rank/device |
| 2 | 框架日志/Master/Scheduler 连接记录 | Host 侧：框架超时 or HCCL 拓扑超时 | 框架→核对连接；HCCL→核对配置 | 记录连接超时原文、rank_table 配置、防火墙/端口状态 |
| 3 | 网络诊断记录 | 建链/流同步/Notify：排查网络是否有异常 | 有→转网络流；无→继续 | 记录网络诊断结论、是否有端口闪断/告警 |
| 4 | 同一通信域和操作的参与集合 | 参与实体的超时/完成/退出/未知状态 | 全量或非全量均继续依赖分析；缺覆盖则未知 | 记录去重 rank/device、参与集合、材料覆盖和状态 |
| 5 | 进入、进展、完成与超时事件及生效预算 | 是否同次操作、时钟可比、生产端仍有进展且延迟可恢复 | 有依据才考虑调整对应阶段预算；退出/错配/不可满足依赖按根因处理 | 记录操作身份、等待区间、配置单位和生效范围；报错差只作线索 |
| 6 | 各参与者同次通信的下发与进展记录 | 是否有覆盖充分的下发差异 | 已证实差异→追踪缺席/错配原因；未证实则继续比较延迟、退出、依赖和缺日志 | 记录操作身份、覆盖、差异和 atrace 依据，不用累计数量替代同次操作 |
| 7 | Event Wait、对应 Record 及其 Notify 依赖 | 外层预算是否先于可恢复的内层工作到期 | 按实际依赖和版本核对预算；配置大小关系本身不证明根因 | 记录任务/事件身份、生产端状态、各阶段预算和单位 |

采用流水线产物模式时，每步过程写入 `diagnosis.md.result.steps`；默认诊断答复在正文说明关键核对过程及证据，不要求生成该文件。

### 超时类型分类

| 大类 | 子类型 | 识别特征 | 子流程 |
| --- | --- | --- | --- |
| Host 侧超时 | 训推框架超时 | 框架层超时报错（PyTorch TcpStore/连接 Master 超时、MindSpore 连接 Scheduler 超时） | §1.1 |
| Host 侧超时 | HCCL Host 侧建链超时 | HCCL 拓扑探测超时、通信域 rankSize 不符、防火墙/IP 端口被占用 | §1.1 |
| Device 侧超时 | 建链超时 | `wait socket establish timeout` 等具体建链超时原文；`EI0006` 单独只表示 Socket 获取失败 | §1.2 |
| Device 侧超时 | 流同步超时（EE1002） | `EE1002`、Stream 同步超时 | §1.3 |
| Device 侧超时 | Notify Wait 超时 | 具体 Notify Wait timeout 和任务信息；`EI0002` 单独只表示通信超时 | §1.4 |
| Device 侧超时 | Event Wait 超时 | 具体 Event Wait timeout 或匹配版本的 waitType/事件信息；`EE9999` 单独是通用内部错误 | §1.5 |

### 1.1 Host 侧超时子流程

| 子类型 | 核对节点 | 离线核对内容 |
| --- | --- | --- |
| 训推框架超时（PyTorch） | Worker 节点从 TcpStore 获取元信息超时 / Worker 节点连接 Master 节点超时 | 已有框架日志中超时报错、Master/TcpStore 连接记录 |
| 训推框架超时（MindSpore） | Worker 节点连接 Scheduler 超时 | 已有框架日志中 Scheduler 连接记录 |
| HCCL 拓扑探测超时 | 通信域 rankSize 与实际不符 / 同一 Device 在同一通信域充当不同 rank / 超时时间内有卡未初始化（是否为固定卡）/ Host 防火墙未开放 / IP 或端口被占用 / 通信域内不同 rank 使用 Host 网卡不一样 | rank_table 配置、防火墙记录、端口占用记录、网卡配置、各 rank 初始化时间 |

`EI0002`/AllReduce timeout 支持通信等待超时，不自动证明网络故障或某个 rank 是根因。`EE1002` 是 Stream 同步超时，结合实际任务和首错核对，不自动写"算子死循环"。核对同一任务中所有可用 rank 的早期异常与退出：较早 OOM/crash 可解释其他 rank 后续等待，但缺对端记录时不能假设对端已死。案例命中后仍核对通信类型、配置、版本、rank 映射与早期事件；不把 CASE-002 的 OOM 原因套给所有 HCCL timeout。

### 1.2 建链超时子流程（EI0006）

建链超时流程：**找到首报错 → 首报错是否为 socket 建链超时 → 判断设备型号 → 排查链路/网络 → 找到报错链路的本端和对端 → 排查软件问题/卡间不一致**。

| 核对节点 | 离线核对内容 | 结论边界 |
| --- | --- | --- |
| 首报错是否为 socket 建链超时 | 建链超时报错原文、`EI0006` | 否→解决首报错（转其他流程） |
| 判断设备型号 | A3→排查 1520 是否有超时代答或其他问题；通用→排查链路网络是否有异常 | A3 场景须核对 1520 日志 |
| 排查链路/网络是否有异常 | 已有网络诊断记录、链路状态 | 是→解决网络链路问题（转 [网络排查](network-flow.md)）；否→继续找本端对端 |
| 找到报错异常链路的本端和对端 | 报错链路的两端 rank/device/IP | 定位到具体链路 |
| 排查卡间不一致 | 核对各端进入/建链进展及生效预算、同次操作下发差异、对端业务卡住或提前退出 | 首尾报错差不等于建链耗时；各候选须有同次操作关联 |
| 排查软件问题 | 通信算子类型下发不一致 / 其他问题 | 通信算子类型不一致→转 HCCL 研发分析 |

**重要**：检查建链之间的机器是否有版本混跑的情况，不允许混跑。

判断是否全量建链超时见 [子检查](#子检查)：按同一通信域/操作的有效参与集合核对去重实体，不能用文件数或物理卡总数代替。

### 1.3 流同步超时子流程（EE1002）

流同步超时流程：**首报错流同步超时 → 排查网络问题 → 是否全量超时 → 全量/非全量分支**。

| 核对节点 | 离线核对内容 | 结论边界 |
| --- | --- | --- |
| 排查网络问题 | 已有网络诊断记录 | 是→解决网络问题；否→继续 |
| 是否全量超时 | 是否所有卡都报流同步超时 | 全量→§1.3.1；非全量→§1.3.2 |

#### 1.3.1 全量超时

对齐同一操作的进入、最后进展、完成及超时记录，比较实际等待区间与生效预算。
首尾报错时间差只描述各报错的离散程度，不能由其大于/小于 timeout 决定根因。
继续比较各 rank 的 traceback、生产端进展、退出及下发一致性；只有工作仍可推进且
延迟可恢复时，才将调整适用版本的 `ACL_DEVICE_SYNC_TIMEOUT` 列为待验证缓解。

#### 1.3.2 非全量超时

关注不报超时的卡是否少下发通信算子：
- **少下发** → 分析 atrace 日志找到少下发算子 / host 慢卡在 host 侧 / 其他情况找 HCCL 分析
- **未证实少下发** → 核对编译、权重加载、阶段调度和额外操作，保持原因未定；有持续进展和可恢复延迟证据才考虑增加对应预算，下发错配或退出须针对原因处理。

### 1.4 Notify Wait 超时子流程（EI0002）

**重要提示：不要看见有 Notify wait 超时就认为是 CANN 或 HCCL 的问题！先确认是否是全量 Notify wait 超时！**

Notify wait 超时流程：**找到首报错 → 首报错 notify wait timeout → 排查网络问题 → 判断是否全量超时 → 全量/非全量分支**。

| 核对节点 | 离线核对内容 | 结论边界 |
| --- | --- | --- |
| 排查网络问题 | 已有网络诊断记录 | 是→解决网络问题；否→继续判断全量 |
| 判断是否全量超时 | 是否所有卡都报 notify wait timeout（统计方法见子检查） | 非全量→§1.4.1；全量→§1.4.2 |

#### 1.4.1 非全量超时

关注不报超时的卡是否少下发通信算子：
- **少下发** → 分析 atrace 日志找到少下发算子 / host 慢卡在 host 侧 / 其他情况找 HCCL 分析
- **未证实少下发** → 核对编译、ckpt/数据加载和迭代内额外操作；缺少下发差异不证明只是慢卡。生产端持续进展、依赖有效且延迟可恢复时，才考虑调整适用的执行预算。

#### 1.4.2 全量超时

按同一 communicator/操作对齐进入、Record/Wait、最后进展、退出和超时记录，并核对
`HCCL_EXEC_TIMEOUT` 的单位、作用阶段和实际生效值。首尾报错差大于或小于预算都
不能单独区分慢卡、错配、互等或提前退出。继续检查下发一致性、依赖和建链/执行
阶段；只在工作持续推进且延迟可恢复时，提出增加对应预算的未验证缓解。

**核对等待关系**：按 `NOTIFY WAIT, localRank:` 检索时，保留 group、操作轮次、
stream/task/notify ID、等待生效区间及对应 Record。rank 箭头组成 `A->B->A` 只是
互等候选；不同轮次或先后完成的正常双向同步也会形成这种投影。只有同一未完成
依赖形成闭环，且对应生产端无法继续提交/完成 Record 时，才能确认死锁。脚本找环
只能定位需要核对的边，不能补齐缺失的身份和进展证据。

### 1.5 Event Wait 超时子流程

Event Wait 超时流程：**首报错为 Event Wait 超时 → 是否全量超时 → 全量/非全量分支**。

| 核对节点 | 离线核对内容 | 结论边界 |
| --- | --- | --- |
| 是否全量超时 | 按有效参与集合核对 Event Wait timeout、事件和任务身份 | 关联对应 Record 和其依赖；内外层预算关系仅为线索，有可恢复进展才考虑调整预算 |
| 非全量超时 | 对照其他 rank 的进展、退出和业务错误 | 未报错不等于正常；其他报错也可能提供源头证据，不能因较晚打印而忽略 |
| 排查历史案例 | 已有案例匹配 | 已知问题→按历史案例解决方案处理；非已知问题→研发分析 |

### 子检查

| 子检查 | 离线核对内容 |
| --- | --- |
| 如何判断是否全量 notify wait 超时 | 检索具体 timeout，A2 的 `stuck notify num` 只作待核线索；按同次作业、通信域、操作和时间窗去重 host/PID/rank/device，与有效参与集合逐项比较。轮转文件、副本及重复报错不增加实体数，文件数和行数不能代替 rank 数。缺失参与者标 unknown，材料不全不确认全量 |
| 如何判断是否全量建链超时 | 检索 `wait socket establish timeout`，按同次建链操作去重端点实体，与该通信域的有效参与集合比较；缺失实体保留 unknown，不以节点数乘物理卡数默认当前参与集合 |
| notify wait timeout 如何核对等待关系 | 保存 group/操作轮次、stream/task/notify、有效等待区间及对应 Record；找环后逐边核对是否仍未完成、生产端是否可推进。只有不可推进的同一依赖闭环才确认互等；单纯 rank 重现只作为候选 |
| 大模型训推 host 慢/卡住 | host 慢需业务分析：权重加载慢、dataloader 慢。host 卡住候选原因：模型权重加载卡住、训练数据加载卡住。程序不打印日志看似卡住时，核对已有堆栈快照：Python 程序核对 py-spy dump 结果，C++ 程序核对 gdb attach 后 bt 结果。记录卡住进程 PID、堆栈快照中等待位置（如权重加载/数据加载/IO 等待） |
| 如何排查通信算子下发不一致 | 在 plog 找 HCCL `TaskExceptionHandler` 的 `run failed, base info` 及邻近多行，提取 tag/算法、group/rankSize/rankId、任务/操作序号、count/reduceType/dataType 和时间。先对齐同一通信域、迭代/操作及参与集合，再比较类型、参数和调用次序；不同轮次的正常 AllGather/AllReduce 不能拼成冲突。记录匹配身份、覆盖、不一致实体和差异字段，缺序号关联则保留候选 |

## 证据盘点与保真要求

| 材料 | 提取字段 | 缺失时保留的边界 |
| --- | --- | --- |
| 应用/plog 的完整时间窗 | 首末时间、最后完成与首次未完成步骤、持续心跳、dispatch/done、Record/Wait | 文件截止不等于业务停滞；日志级别或轮转可使完成事件不可见 |
| 所有已提供 rank 日志 | host/PID/rank/device、collective 类型/序号/group、进入/完成事件、退出与异常 | 不能假定未提供 rank 健康或故障；不同机器时钟可能有偏差 |
| 已有线程/进程堆栈（atrace） | 快照时间、线程、等待函数、锁/队列/任务身份 | 单个 futex/waitpid/recv 帧不证明死锁及其根因 |
| 配置/启动与已有进程记录 | world size、rank 映射、rank table、启动方式、端点、退出原因、HCCL_EXEC_TIMEOUT、ACL_DEVICE_SYNC_TIMEOUT | 配置意图不一定等于实际生效状态 |
| 已有 profiling / 状态存档 | 同任务的活动区间、进展、耗时和资源等待 | 没有基线时不能凭"很久"确认异常长任务 |

必须保留 INFO/DEBUG 级别的心跳、每 rank 的正常完成、通信进入/退出、数据加载和初始化事件；重复事件保留次数、位置和时间差。它们是区分"无进展""仍在运行"和"日志已截断"的主要依据。

## 判定矩阵与竞争假设

| 分支 | 支持所需证据 | 不能单独作为根因的信号 |
| --- | --- | --- |
| 某 rank 先退出/失败，其余等待 | 该 rank 的明确退出/首错、同次 collective 身份和其他 rank 后续等待 | 单条 Rank not ready、最后打印者或只有内存高占用 |
| collective 调用不一致 | 同 group/迭代/序号的调用类型、shape/count 或进入顺序差异 | 各 rank 打印顺序不同；可能是时钟/缓冲差异 |
| 初始化/配置问题 | 有效 rank 配置、启动记录和具体异常可关联 | 没有 GE/HCCL 行就推定网络不通 |
| 网络/连接问题 | 已有连接错误/网络诊断记录、端点/时间与故障关联 | HCCL timeout 本身；不能默认通过增加超时修复。详见 [网络排查流](network-flow.md) |
| fork / 资源继承或锁依赖 | 实际启动方式、ACL 初始化先后、相关代码/栈及资源或等待关系 | DataLoader、fork、waitpid 或 futex 字样本身 |
| 数据加载/IO 等待 | 任务阶段、队列/worker/IO 栈和生产消费进展记录 | 主线程停在 DataLoader，不足以证明 worker 死锁 |
| 算子/流依赖等待 | dispatch/done、Event Record/Wait、任务/流依赖与上下游异常 | 缺 done 或同步函数超时，不直接证明死循环 |
| 正常长任务/日志中断 | 已有活动或后续完成、性能基线、文件截止/轮转/级别信息 | 无后续日志不能排除此分支 |
| 超时预算不适合当前负载 | 同次操作的实际等待和生效预算、有效依赖、持续进展及可恢复延迟证据 | 首尾报错差、内外层配置大小关系或单独 timeout 均不证明预算不当 |

锁循环/死锁的结论需要等待关系形成闭环或已有验证证据；否则表述为"在 <位置> 等待，原因未定"。Event/Notify Wait 应核对对应 Record 端，不能只凭等待端闭合因果链。

### `comm_timeout` 专用判断

当入口场景为 `comm_timeout` 时，保留 `scenario_id=comm_timeout`，先识别通信库、实际 API、协议和阶段。HIXL/LLM-DataDist 点对点场景按[HIXL 参考](../hixl-reference.md)核对 endpoint、控制请求/响应和底层通道，不要求不存在的 collective/group 字段，也不从客户端等待直接排除 Device/驱动资源。下列步骤中的 collective 一致性用于 HCCL 等集合通信；点对点场景对应比较同次两端操作及状态：

1. **定位超时操作**：从原始日志提取 collective 类型（AllReduce、Broadcast 等）、group、迭代/序号、参与 rank、进入和超时时间，确认超时属于同一次通信操作。
2. **建立 rank 对照表**：为每个可见 rank 标记 `entered`、`completed`、`exited` 或 `unknown`。缺失 rank 日志使用 `unknown`，不推断其状态。
3. **寻找首发异常**：在超时前的时间窗内搜索 OOM、崩溃、设备错误、进程退出和数据/IO 停滞，并通过 PID、rank、device、任务序号和时间关系确认是否与超时相关。
4. **核对调用一致性**：比较各 rank 的 collective 名称、group、序号、shape/count 和进入顺序；字段缺失时将该分支标记为 `unresolved`。
5. **评估网络假设**：只有已有连接错误、端点信息和时间关系共同支持时，才将网络/连接问题列为 `supported`；`EI0002` 或 timeout 文本本身只能证明等待超时。
6. **区分传播与根因**：若某 rank 的已确认首错先于其他 rank 等待，可输出"首错导致通信等待"；通信超时自身仍记录为传播事件，首错原因单独给出状态。

该分支至少在 `H1`–`H4` 中填充 `collective_alignment`、`rank_coverage`、`rank_exit_chain`、`network_evidence`、`propagation_status` 和 `unresolved_links`。无法闭合因果链时，结论使用"通信操作在指定时间窗内未完成，具体原因未确定"，并列出尚未排除的 rank、调用一致性和网络假设。

## 子步骤产物

流水线模式每步更新同一个 `diagnosis.md.result.steps`，并保留公共状态、输入/证据引用、缺口和 next_step。

| step_id | 执行动作 | findings 必含字段 |
| --- | --- | --- |
| H1 | 案例/分类与观察区间核对，归类超时类型 | signals、case_comparison、event_identity、observation_window、expected_progress、hang_confirmed、timeout_type（notify/event/host_link/stream_sync/framework/host_topo）、is_all_timeout（全量/非全量/未知）、classification_conflicts |
| H2 | 盘点多 rank、堆栈、配置和正常进展 | material_inventory、versions、rank_map、rank_coverage、clock_alignment、last_progress_by_rank、stack_snapshots、atrace_logs、effective_config、timeout_config（HCCL_EXEC_TIMEOUT/ACL_DEVICE_SYNC_TIMEOUT） |
| H3 | 按对应子流程核对，对齐通信/任务依赖、首错和竞争假设 | first_error_candidate、timeout_subflow、first_last_time_diff、time_diff_vs_timeout、collective_alignment、task_dependencies、rank_exit_chain、branch_decisions、alternative_decisions、unresolved_links |
| H4 | 输出等待位置、因果边界和检查依据 | confirmed_facts、wait_location、root_cause_status、limitations、recommendations、check_evidence |

H4 填满公共诊断字段。`hang_confirmed=false` 不代表分析失败，仍应完成报告，说明"现有日志不足以区分真实卡住与观察窗口结束"。

## 结论与评分边界

- 事实与根因分开："<rank/group/task> 在 <观察区间> 未见进展/发生等待超时"；只有关联证据充分时才写退出源、通信不一致或锁循环。
- D1 没有 ERROR 的真实 hang 不虚构首报错，`has_first_error_line=false`；可在时间线保留最早明确异常/停滞候选。继续原评分与报告，关键项按原规则限制入库。
- D2 多 rank 日志需确认独立来源与同次事件，时钟未对齐不能机械全局排序。D3 未提供对端、网络或 Record 端时保留对应未排除假设。
- D4 仅已有修复/回归记录可加分。建议修改超时或启动方式必须注明条件和未验证状态，不执行改配置或重跑。
- 没有现场堆栈不裁剪本流、不额外封顶；现有日志可支持到何种范围就写到何种范围。

参考：[公共约定](common-flow.md)、[故障处理专题](../fault-handling.md)、[错误码](../err-messages.md)、[网络排查流](network-flow.md)、[CASE-002 与案例库](../cases.md)、[可信度规范](../confidence-assessment.md)；案例相似只形成候选，实际异同核对后才评估是否匹配。
