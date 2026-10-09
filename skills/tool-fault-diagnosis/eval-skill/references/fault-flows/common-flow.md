# 典型故障处理流公共约定

所有场景剧本先消费 `case-match.md → scenario.md → clean-result.md` 并核对原始文件。本库只做离线日志评估，现场操作命令（`npu-smi`、`msnpureport`、`ascend-dmi` 压测、`gdb` 附加进程、复跑等）一律不执行、不补采、不复跑，只在已有材料中找对应证据/字段。案例命中是检索线索，不证明当前根因。缺少前置产物时先生成，不在剧本内部跳过案例检索或分类。

## 场景路由入口（怎么进入对应处理流）

诊断由 `orchestrator-skill` 的 `detect` 阶段（[场景识别规范](../../../orchestrator-skill/references/scenario-recognition.md)）完成场景分类后路由到对应剧本。下表把每个场景的**识别信号**与**路由目标**写清楚，供 eval-skill 内部核对入口是否正确，也供 orchestrator 同步分类表：

| 场景 ID | 识别信号（错误码 / 关键字 / 现象） | 路由剧本 | 备注 |
| --- | --- | --- | --- |
| `card_drop` | `npu-smi info` 查不到卡、`EL0001` Device_Absent/Abnormal、PCIe link down、BMC 告警卡消失、卡不在位 | [掉卡](card-drop-flow.md) | 卡仍在但平台告警→非掉卡，按故障码转其他场景 |
| `aicore_error` | `EZ9999` + `aicore/aivec error exception`、`fault kernel_name`、`Aicore kernel execute failed`、AI Core 寄存器详情 | [AI Core Error](aicore-error-flow.md) | 单独 `EZ9999` 不足以确定；须核对嵌套详情 |
| `hang` / `comm_timeout` | `no progress`、`deadlock detected`、`task not finish`、`EI0002` 通信超时、`EE1002` Stream 同步超时、Notify/Event Wait 超时 | [卡住与通信超时](hang-flow.md) | 细分 Notify/Event/Host 建链/流同步 4 类超时 |
| `crash` | `SIGSEGV`/`SIGABRT`、`Segmentation fault`、`core dumped`、退出码 139/134、未捕获致命异常 | [进程中断](crash-flow.md) | 分 host dump / device dump 两条线 |
| `oom` | `EL0004`、`HBM allocation failed`、`memory not enough`、OOM Killer 明确事件、框架 `Out of memory` | [OOM](oom-flow.md) | 退出码 137 不等于 OOM；须核对内存分配失败原文 |
| `precision` | `NaN`/`Inf`、`loss` 突变、`max_diff` 超过同条记录的 `threshold`、精度不达标 | [精度异常](precision-flow.md) | 调优前检查→浮点溢出→融合检测 |
| `performance` | 性能下降/回归记录、profiling 瓶颈、吞吐/延迟劣化、用户描述性能问题 | [性能问题](performance-flow.md) | 基线对比→Host/Device 分维→瓶颈定位 |
| `offline_inference` | ATC 报错/模型转换失败、`soc_version` 不匹配、离线推理报错、参数校验失败 | [离线推理/ATC](offline-inference-flow.md) | 版本确认→报错类型分支 |
| `network` | 网络诊断异常、端口闪断/Down、`EI0013` ROCE CQE 错误、丢包、网络设备告警 | [网络排查](network-flow.md) | 也作为 comm_timeout 的网络假设分支 |
| `compile_error` | 编译操作明确失败、`UB memory overflow`、`EB` 类编译码 | [错误码](../err-messages.md) + [背景](../background.md) | 保留原有路由 |
| `generic_error` | 有错误码/失败但未形成具体专题证据 | [错误码](../err-messages.md) | 保留原有路由 |
| `unknown` | 无足够信号 | 原始证据盘点与一般诊断 | 禁止猜根因 |

**识别优先级**：强现场信号（错误码原文 + 模块 + 故障特征同行）优先于话术和文件名；多个强场景同时出现时保留 `secondary` 和 `uncertain`，不静默丢弃。同一信号只贡献一次分值，重复报错只增加 hit_count。具体强弱与冲突规则见 orchestrator 的 [场景识别规范](../../../orchestrator-skill/references/scenario-recognition.md)。

> **同步状态**：orchestrator-skill 的 `scenario-recognition.md` 分类表已同步 `card_drop`/`offline_inference`/`network` 场景，`precision`/`perf_degradation`（flow 文件为 performance-flow.md）的路由已指向对应 fault-flow 文件。详见本文件 §6 场景剧本索引。

## 知识库索引边界

知识库分三层使用：`cases.md` 是唯一参与自动命中的正式案例库；`cases-pending.md` 只存放待补证候选，不参与自动命中；各专项 reference 的“案例索引/案例详解”供诊断阶段人工核对和流程引用，也不直接参与自动命中。高价值 reference 或候选案例须先补齐证据并按入库流程转正为 CASE，才能进入自动匹配。诊断可信度只依据 `diagnosis.md` 的 `causal_chain` 及证据字段；产物索引中的阶段链路仅表示流水线依赖，不表示故障因果。

## 0. 找到报错的首节点

所有场景诊断的第一步都是定位首报错。先确认入口 `errors` 数组，再用下列方法在已有材料中核对首报错；不可把最后一条框架异常或最早可见行直接当作首报错。

### 方法一：Ascend-faultdiag 故障诊断工具（背景）

`Ascend-faultdiag` 是现场一键诊断工具，可能误诊。本库不运行该工具；若已有材料中包含其诊断结果，作为候选线索引用，仍须用下列人工方法在原始日志中核对，不能直接采信工具结论。

### 方法二：人工核对首报错

先用已收集的所有 rank 的 host 日志（plog 和回传到 host 的 device 日志，如 aicpu、hccp 组件日志）。核对目录结构：`plog/debug`（ERROR 级别）、`plog/run`（INFO 级别）、`device-x`、`security`。

在清洗视图或原始日志中按时间对所有 ERROR 排序，找到最先报错的 rank 以及报错内容（等效于现场 `grep ERROR -rn > err.log` 后按时间排序）。然后按 rank 异常情况分类核对：

| rank 异常情况 | 核对方向 | 证据要点 |
| --- | --- | --- |
| 有进程早于首报错发生 coredump | 以 core/堆栈定位该进程崩溃，首报错可能是其传播 | core 文件时间、PID 与首报错的时间/PID 关联；core 早于首报错才能作为上游 |
| 存在未报错 rank | 定位未报错原因：个别 rank 提前正常结束 / 卡间设置问题 / 框架或业务原因 | 该 rank 最后一条日志的角色（正常完成/退出/无输出）、与报错 rank 的时间关系 |
| 所有 rank 都报错 | CANN 上层有报错导致所有 rank 报错，框架/平台定位报错原因 | 各 rank 首报错是否同一来源、是否有共同上游框架异常 |
| 未报错卡都是首报错之后被 kill | 关闭 watchdog 或平台主动 kill 功能 | kill 记录时间是否在首报错之后、kill 来源（watchdog/平台/调度器） |
| 复测有个别 rank 卡在 Host | 用已有 host 堆栈定位卡住位置 | 堆栈快照时间、等待函数、是否阻塞在系统调用 |

锁定首报错 rank 日志后，进入对应场景剧本定位问题。首报错 rank 是首报者，不自动是故障源；异步场景下取 `serial number` 最小的首报错，且只在可比较的同一记录范围内排序，不跨主机/进程机械取全局最小值。

## 1. 输入与证据保护

- 仅分析已提供的文件和已有验证记录，不要求补采、不访问运行进程、不重跑业务。
- 原文件只读；原始日志位置为证据锚点，清洗视图必须能映射回原文。INFO/DEBUG、成功事件、心跳、重复次数和多行续行均可能是有效证据，不能因级别低或"看起来正常"而排除。
- 先核对 host/PID/rank/device、业务阶段、版本与时间窗，再连接因果链。不同主机时钟未对齐时，保留局部顺序和偏差，不将打印最早者直接认定为根因。
- 材料缺失不阻断现有证据分析，也不裁剪必需的诊断字段。工具失败与业务故障分开记录。
- 已有材料是否包含该类日志、是否覆盖故障时间窗；缺失时记 `evidence_gaps` 并说明影响，继续其他现有证据。

## 2. `diagnosis.md` 字段

公共外壳按 [流水线产物契约](../../../orchestrator-skill/references/pipeline-artifacts.md) 定义：`schema_version / run_id / stage / owner_skill / status / attempt / started_at / finished_at / inputs / outputs / summary / evidence_gaps / error / next_action / result`。只保留一个 `json` 结构块。

以下字段全部属于 `result`，无信息时使用 `null`、空数组或明确的 `unknown`，不可省略后伪装为完成：

| 字段 | 必须包含 |
| --- | --- |
| `first_error` | 原始文件、行号/字节范围、原文、原始时间、PID/TID/rank/device/stream/task、关联依据；找不到首错为 null，并记录最早可见候选及范围限制 |
| `timeline` | 事件 ID、时间及其时钟来源、实体、业务阶段、原文引用、角色（正常进展/首错候选/传播/清理/未知）；保留无法排序的事件 |
| `causal_chain` | 每一跳的 from/to、支持证据、反证、状态（supported/unresolved）；不能只串接关键词 |
| `root_cause` | description、status（confirmed/hypothesis/undetermined）、location、evidence、limitations；"已确认失败现象"与"根因确认"分开 |
| `alternatives` | 假设、支持证据、反证、状态（supported/excluded/unresolved）、未解决缺口 |
| `recommendations` | 建议、适用前提、支持证据、预期影响、已有验证状态；不自动执行修复或复现 |
| `checks` | 原有 17 项检查键，每项 `{value: true/false, evidence: [...], reason: "..."}`；只有实际支持该项的证据才记 true |
| `references` | 当前材料的原始位置、案例 ID/版本适用性、文档位置、实际核对过的源码 ref；引用不能代替当前现场证据 |
| `steps` | 各剧本下列子步骤记录；每项含 step_id、status、input_refs、findings、evidence_refs、evidence_gaps、next_step |
| `classification_review` | 对 scenario.md 的一致性结论、新增/冲突信号及其位置、需复核的主/次场景；不静默改写调度分类 |

`evidence_gaps` 每项写清"缺什么、影响哪项判断、当前最多能说到哪里"。只写事实缺口，不写补采命令或阻塞等待补齐。各步骤的 `findings` 字段由对应剧本逐项定义。

Markdown 人读部分至少包含"问题摘要""关键日志""根因分析""修复建议""证据缺口与结论边界"；这也让案例工具能从同一 `diagnosis.md` 抽取业务内容。日志引用使用原始文本代码块，不能在 JSON 结构块里虚构日志。无法确认根因或没有适用修复建议时如实写明，不为了凑案例字段补写未经支持的方案。

## 3. 案例模板（4 段式）

沉淀到 [案例库](../cases.md) 的案例统一采用 4 段式结构，入库门槛与脚本见 [案例沉淀规范](../case-contribution.md)：

| 段 | 内容 | 说明 |
| --- | --- | --- |
| 1. 问题现象描述及版本信息 | 1.1 问题描述（现象、触发场景、影响范围）；1.2 配套版本信息（CANN 版本、HDK 版本、芯片型号、训推框架版本、Atlas 900 A3 SuperPoD 等可选项） | 版本信息是案例可复用的前提，缺失版本区间的案例须标注适用边界 |
| 2. 问题分析 | 再次发生同问题时维护人员如何确认是同一个问题（如通过 plog 日志的关键字、导出 device 日志的报错特征比对） | 给出可复用的同问题识别特征，便于下一次诊断命中 |
| 3. 问题根因 | 具体到算子/模块/file:line | "已确认失败现象"与"根因"分开 |
| 4. 解决方案 | 临时规避 / 长期解决（升级到某个版本等） | 两条都要写；只有长期方案时如实写明无临时规避 |

`promotion.md` 抽取案例时按此 4 段式生成候选块。关键日志特征必须是真实日志原文，不能复述或臆造。

## 4. 子步骤与恢复

1. 进入核对：使用 §0 找首节点方法与案例候选，确认事件归属和分类边界。
2. 证据盘点：已提供/缺失/不匹配分别记录，只解析可用材料。
3. 时序与分支：区分触发、传播、正常进展和未知，按各剧本判定矩阵评估竞争假设。
4. 结论与检查：输出事实、假设、限制、建议及 17 项检查依据。

以上是 `diagnose` 内部步骤，不另造多套主产物。每完成一项就更新同一个 `diagnosis.md`；失败也保留相同公共外壳、已完成 `steps`、错误与下一动作。重试按公共契约存留原 Markdown 快照，不能用单独错误 TXT/JSON 替代业务文档。只在输入指纹与前置产物引用一致时复用已有子步骤；低可信度或缺证不能触发无限重试。

调度可以改变等价执行方式，但不得省略分析步骤、证据标准或输出字段，也不得通过换工具虚构缺失证据。未提供文件与解析工具暂时失败是不同情况。

## 5. 17 项检查与结论

评分完全沿用 [可信度规范](../confidence-assessment.md)；本页说明现场解释，不增加分数上限：

- D1：`has_first_error_line`、`has_env_version`、`has_full_timeline`、`has_crash_artifacts`、`has_repro_input`。最早可见行不自动是首错（见 §0）；非崩溃结论的 crash 产物项按原规则记 true 并标"非适用"，涉及真实崩溃则核对产物。
- D2：`multi_source_agree`、`timeline_consistent`、`no_contradiction`。同一日志的副本、清洗版、工具转述不算独立来源；没看到反证不等于充分检查过且无矛盾。
- D3：`root_cause_localized`、`chain_no_gap`、`alternatives_excluded`。只有错误模块或等待函数的位置不足以证明根因；缺失某类日志不能用于排除该竞争假设。
- D4：`reproducible`、`fix_verified`、`regression_checked`。只依据已提供的触发条件、复现和修复/回归记录，建议尚未执行时不记已验证。
- D5：`errcode_documented`、`case_matched`、`source_code_confirmed`。只有检索 hit 不足以记 case_matched，必须说明实际异同；源码必须匹配版本并证实所述路径。

高分不自动把未知的根因变为事实。按 score 原样输出等级，同时保留每一条主张的证据边界；关键项影响案例准入，不额外改分。分数低时继续输出可信度与报告，`promotion.md` 记录拒绝入库理由。

## 6. 场景剧本索引

| 场景 ID | 剧本 | 流程 |
| --- | --- | --- |
| `card_drop` | [掉卡](card-drop-flow.md) | 掉卡定位流程 |
| `aicore_error` | [AI Core Error](aicore-error-flow.md) | AIC Error 定位流程 |
| `comm_timeout` / `hang` | [卡住与通信超时](hang-flow.md) | 超时类问题定位流程 |
| `crash` | [进程中断](crash-flow.md) | coredump 类问题定位流程 |
| `oom` | [OOM](oom-flow.md) | NPU OOM 问题定位流程 |
| `precision` | [精度异常](precision-flow.md) | 精度异常定位流程 |
| `performance` | [性能问题](performance-flow.md) | 性能问题定位流程 |
| `offline_inference` | [离线推理/ATC](offline-inference-flow.md) | 离线推理定位流程/ATC |
| `network` | [网络排查](network-flow.md) | 排查网络 |

其他场景按 [错误码](../err-messages.md)、[日志规范](../log-spec.md) 和 [背景](../background.md) 分析，保留其原场景，不硬塞进上述类别。若新证据与分类冲突，在 `diagnosis.md` 记录冲突并请求调度复核 `scenario.md`，保持下游引用一致。
