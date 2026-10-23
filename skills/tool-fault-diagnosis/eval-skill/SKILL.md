---
name: eval-skill
description: 根据已有 CANN/Ascend NPU 日志与故障现场进行专项诊断，结合错误码、字段语义和案例定位故障机制及修复方向。用户明确指定本技能、单一故障专项或由 orchestrator-skill 路由时使用；泛化或多组件诊断由 orchestrator-skill 协调。
license: Apache-2.0
---

# CANN 专项诊断

当前 Agent 负责从已有原文解释具体失败机制及传播链，比较有依据的上游原因，给出对应的条件修复与验证方向。先读 [诊断与字段约定](references/diagnostic-reasoning.md)。用户报告的观察、定位和处置结果按其来源、版本与条件保留，与本次独立验证区分；作者的猜测作为待核候选。

主结论给出有证据支持的优先诊断和针对性修复，并注明其为已确认还是最可能。某个源码行、参数值或补丁未知，只限制该实现细节；不要把整份诊断写成未知，也不要把没有本例支持的理论可能性与优先根因等量并列。错误日志描述的是当前实现的行为，是否符合预期接口契约须另行核对，不能由参数检查报错直接认定调用方有错。

## 用户材料线索优先绑定

开始读日志前，先盘点用户描述、附件、环境清单和原始材料中的现象、日志源、硬件、CANN/Driver/Firmware、分支或提交、测试脚本/包名、算子或 API、已知问题单及复现条件。把这些字段建立为“现场线索表”，逐项绑定到后续日志中的 PID、设备、任务、时间窗和版本。用户材料明确写出的 `OOM`、`crash`、分支名、包名或“已知修复”不是装饰性标签，也不能仅因日志没有重复同一个词就排除；它们是需要用日志、公开源码和版本差异验证的上游候选。只有在同一故障窗口存在相反证据时，才降低该候选，并说明冲突。

现象字段里的具体错误串、触发条件和对照结果同样是证据：例如 `invalid port speed`、非连续
`asstrided`、某个 kernel/模式、注入 HBM UCE 后出现 Oops，或“打开 debug 后不复现”。
它们必须出现在首错证据表和候选排序中，并与日志的更底层对象、时间和版本绑定；不能只复述
后置的 `507034/507035`、`EZ9999` 或“任务失败”。对照条件可降低或提高竞争候选的优先级，
但不能单独证明因果；用户材料与日志冲突时保留两层事实并指出需要的判别材料。

错误串若已经明确写出访问对象和违反的约束（例如 scalar 访问内部 buffer 越界、GM 地址超过
48 位、FIXP 读取 L0C 越界、LOAD3D 起始点非法），要把这条“对象 + 约束违反”直接写入主诊断和
`direct_mechanism`；与同一故障任务绑定后可确认这一级机制。不要退化成只有 `AI Core exception`、
`507035` 或“地址可能有问题”。`upstream_trigger` 仍需独立的触发证据；源码变量、实际地址、偏移常量和触发指令须单独标成
`implementation_root_cause` 的待确认细节；这条边界不应阻止交付已被错误串直接支持的机制。

用户报告的线索与现场直接机制分层表达：日志可确认的异常仍作为直接机制，用户材料提供的版本/分支/问题单作为上游触发候选。若用户报告或附件使用“经定位/根因是/已确认/重复问题单/回退后恢复/修复后恢复”等措辞给出既有结论，应保留为 `reported_finding`，与日志直接机制并列核对，不得被后置传播错误覆盖。此类结论必须进入最终答复的“主诊断”首段，明确标注来源、适用的版本/条件以及本次日志是否独立复核；不能因为缺少源码、core 或同一批次的复现而把它改写成“无法确定”。独立验证不足时，只降低 `implementation_root_cause` 的确认状态，不删除 `reported_finding`。若用户材料已经给出明确的分支、问题单或修复时间，优先查本地公开资料和对应实现，核对该版本是否包含修复；不要把“缺少现场 OOM 字符串”当成排除软件回退或已知缺陷的充分理由。

用户提供的附件、排查记录和复测结果中的既有结论同样按 `reported_finding` 处理，引用实际文件及位置；区分作者已报告定位和作者推测。材料中的“当前检查要求”与“预期应允许/应拦截”冲突时，要解释该冲突，按 [契约与优先诊断](references/diagnostic-reasoning.md#契约与优先诊断) 比较接口实现、封装适配与调用方的责任。

## 现场与专项知识

读取用户描述、环境和原始材料，保留任务身份、阶段、关键原文及位置。大日志或多次运行按 [日志窗口与签名](references/diagnostic-reasoning.md#大日志与重复运行) 检查覆盖和失败归属。根据当前错误机制查阅下表；只加载相关资料。

需要核实具名 API 的参数、单位、存储空间或生命周期时，先读取
[离线官方文档入口](references/api-docs.md)选择所属仓库的语料，再按完整 API 名查询并读取
匹配变体的参数和约束原文。检索器默认只查 Ascend C，不会自动搜索 ACLNN 等其他语料。
核对版本及型号条件；头文件摘要或另一型号的测试不能代替本型号的接口约束。

用户材料给出仓库、commit、具名API或测试入口时，先核对[离线公开源码](references/offline-source-code.md)
是否包含对应实现。即使日志短或未提供core，也利用匹配实现追踪参数检查、调用与资源依赖，
给出有源码依据的具体机制候选和修复对象；公开实现事实与本次实际执行到该路径的证据分开。

| 现场问题 | 参考入口 |
| --- | --- |
| 错误码、嵌套错误 | [err-messages](references/err-messages.md)；字段或路径含义不明时查 [log-spec](references/log-spec.md) |
| AI Core / AI Vector / UB / MTE / FIXP | [AI Core 处理流](references/fault-flows/aicore-error-flow.md)、[CANN 9.0.0 专项](references/ai-core-reference.md)；自定义 kernel 的 Fixpipe、GM/UB 搬运或队列问题选读 [API 约束](references/ascend-kernel-api-contracts.md)，CUBE、LOAD3D 或 DataCopyPad 选读 [Cube/MTE 约束](references/ascend-cube-mte-contracts.md)，核对型号、版本及条件 |
| 掉卡、设备不可见 | [掉卡处理流](references/fault-flows/card-drop-flow.md) |
| 卡住、HCCL / Notify / Event / Stream 超时 | [超时处理流](references/fault-flows/hang-flow.md) |
| Host core、Device Stackcore、进程中断 | [崩溃处理流](references/fault-flows/crash-flow.md)、[离线解析命令](references/coredump-command-playbook.md)、[专项报告](references/coredump-report-template.md) |
| 内存分配失败、OOM | [OOM 处理流](references/fault-flows/oom-flow.md) |
| HIXL、单边通信、UB/灵衢 | [HIXL 专项](references/hixl-reference.md) |
| 精度、NaN/Inf、融合 | [精度处理流](references/fault-flows/precision-flow.md) |
| 性能劣化 | [性能处理流](references/fault-flows/performance-flow.md) |
| ATC、离线推理 | [离线推理处理流](references/fault-flows/offline-inference-flow.md) |
| RoCE、网络、端口告警 | [网络处理流](references/fault-flows/network-flow.md) |

[故障处理专题](references/fault-handling.md) 和 [背景](references/background.md) 提供补充知识；[代码仓地址](references/code-repos.md) 用于获准的源码溯源。按现场签名定向检索 [案例库](references/cases.md)，核对适用条件后使用，不把相似案例当作当前根因。

## AI Core 字段工具

需要核对 kernel/hash、PC、task、args 等多字段时，先执行现有只读提取器，再回读来源上下文。以下命令从本技能目录执行：

```bash
python3 scripts/extract_aicore_evidence.py --input <已解压日志路径> --summary --max-file-bytes 268435456 --max-total-bytes 536870912
```

核对 `files` 覆盖、完整多值异常签名和 `partial` 范围。计数是逐行观测，不是独立任务数；相同签名不证明同一根因。需要全部字段时去掉 `--summary`，按 [字段视图](references/diagnostic-reasoning.md#ai-core-字面字段视图) 控制输出。执行失败则保留实际错误并继续原文分析。

AI Core 设备错误解码后，必须在当前 `log/` 全范围检索并回读上下文：`DataCopyPad|Fixpipe|LoadData2D|LoadData3D|asc_copy|workspace|tiling|PI|capture|IMP|DISP|ACSVIOL|ECC`，同时用 kernel/hash/PC 绑定源码或产物线索。命中 API、参数转储、源码片段或用户材料已报告的实现结论时，将具体字段/值写入 `implementation_root_cause`；未命中时才保留为 `hypothesis/undetermined`。只引用错误码、kernel 名或最后一条 `Task run failed` 不算完成该步骤。

若 `errorStr` 本身已经给出对象和边界，命中该语义即可形成“直接机制 + 约束违反”的两层结论：例如
`The GM address accessed by scalar exceeds 48 bits` 应明确写成“scalar 对 GM 的有效地址超出
48 位约束”，`The address for FIXP to read L0C is out of bounds` 应明确写成“FIXP 读取 L0C
的地址/跨度越界”。只有在需要落到源码变量、指令操作数或具体偏移时，才等待参数、反汇编或
源码证据；不要因为缺少这些更深层材料而把已明确的约束违反写成未知。

`build_error.log`、编译器输出和产物路径也属于当前现场材料。若其中出现 `Build files have been written to`、目标名或稳定的测试目录标签（例如 `.../fixp_...`、`.../load3d_...`、`.../mte_...`），必须记录该标签，并与 `errorStr`、错误位、PC、kernel/hash 交叉核对。标签能直接说明该运行产物针对的缺陷类别时，可作为 `reported_finding` 或最可能上游触发写入主诊断；它不能单独证明源码行、现场参数值或实际执行分支。若标签与设备错误冲突，保留冲突并以同一任务的设备首错为直接机制。

## 交付与其他模式

直接交付诊断正文和关键日志引用。正文固定包含：首错证据表；`direct_mechanism / upstream_trigger / implementation_root_cause` 三层根因状态；每跳带证据和反证的因果链；绑定具体字段/约束、修改对象和验证判据的修复表；证据缺口与可信度。错误模块、kernel 名、等待函数或单个错误码只能确认直接机制；没有现场参数、源码 `file:line` 或等价实现证据时，实现根因必须写为 `hypothesis/undetermined`，不能把检查清单写成已确认根因。未执行的验证写为计划。无需为普通诊断运行清洗、完整性评分或入库脚本；确需清洗时查 [证据保护约定](references/fault-flows/common-flow.md)。

若存在 `reported_finding`，正文顺序固定为：用户材料已报告的主诊断及来源/边界；日志独立支持的直接机制和首错；三层根因状态及其中哪些尚未独立确认；冲突或缺口；修复与验证。用户材料报告的具体问题单、PR、分支回退或恢复现象必须按原意复述，并与“本次现场已确认”的措辞区分。

明确要求流水线、度量/HTML报告或案例维护时，读取 [流水线使用指南](../orchestrator-skill/references/pipeline-usage.md)。`run_pipeline.py` 只准备证据草稿，其固定未知结论不能代替分析。完整性分数决定案例准入，不是根因概率。
