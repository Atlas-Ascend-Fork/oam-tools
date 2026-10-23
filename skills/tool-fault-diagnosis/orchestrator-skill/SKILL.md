---
name: orchestrator-skill
description: 分析 CANN/Ascend NPU 故障日志，定位根因、证据链、组件与修复方向；为泛化或多组件诊断协调案例检索和专项分析。用户明确指定单一专项或已有诊断产物时可直接进入对应子技能。
license: Apache-2.0
---

# CANN 故障诊断

根据用户描述、环境和当前原始日志，回答故障发生在哪个任务和阶段、违反什么约束、哪些原文支持判断，以及如何修复和验证。缺少某类材料时说明它限制的具体判断，继续分析现有证据。

## 普通诊断

默认直接交付完整诊断正文。读取 [CANN 诊断与字段约定](../eval-skill/references/diagnostic-reasoning.md)，结合当前现场使用 [eval-skill](../eval-skill/SKILL.md) 的专项参考。原始材料只读；保留上下文、原文位置和读取覆盖范围。只分析已有材料，不自行补采、改现场或重跑业务。

用户明确指定专项时可直接进入对应分析。泛化或多组件问题由本技能根据现场协调专项；需要区分场景时查 [场景识别规范](references/scenario-recognition.md)。分类只选择分析入口，不确认根因：`137` 不等于 OOM，`EZ9999` 不独立证明 AI Core Error，旧 core 文件名不证明本次崩溃。

按原始错误码、模块和故障操作定向检索 [案例库](../eval-skill/references/cases.md)。案例相似只形成候选，使用前核对版本、设备、输入和实际差异；未命中继续当前现场分析。无需重复上下游已完成的同一检索。多现场按任务、设备和时间窗分组，按关联证据解释传播关系。

最终正文包含具体结论、关键日志原文及位置、定界过程、定位与条件修复、验证方向和可信程度。固定先给首错证据，再分 `direct_mechanism`、`upstream_trigger`、`implementation_root_cause` 三层根因，并为每条因果链标出证据、反证和状态。错误模块、kernel 名、等待函数或单个错误码只能确认直接机制；没有现场参数、源码 `file:line` 或等价实现证据时，实现根因必须保留为 hypothesis/undetermined。修复建议绑定具体字段/约束、修改对象和验证判据。直接机制与上游候选在提出时说明各自依据；目录名、缺失记录或材料完整性分数不代替因果证据。按实际问题组织正文，不要求为未涉及的分支填表。

## 显式流水线与报告

用户明确要求流水线产物、HTML/度量报告、断点恢复，或继续已有计划时，读取 [流水线使用指南](references/pipeline-usage.md)，使用原有阶段、脚本和 [产物契约](references/pipeline-artifacts.md)。普通的“完整诊断报告”可直接是完整 Markdown 正文。

独立能力按实际任务使用：[collect-skill](../collect-skill/SKILL.md) 用于明确安排的初始采集；[trace-skill](../trace-skill/SKILL.md) 用于时间线和事件关联；[metric-skill](../metric-skill/SKILL.md) 汇总已有诊断。trace、分类和报告生成不代替当前 Agent 的实质诊断。
