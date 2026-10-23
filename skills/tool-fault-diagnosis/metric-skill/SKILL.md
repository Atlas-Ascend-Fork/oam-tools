---
name: metric-skill
description: 基于已有 eval-skill 评估结论，生成结构化度量报告或可离线打开的单文件 HTML 故障报告。仅在用户明确要求度量、HTML 或可视化交付且已有评估/诊断上游产物时使用；缺少上游结论时由 orchestrator-skill 先处理入口和诊断。
license: Apache-2.0
---

# 度量报告技能 (Metric Skill)

## 适用场景

- 评估 Skill 已输出评估结论，需要生成正式的度量报告
- orchestrator-skill 已完成诊断和可信度阶段，并提供 `diagnosis.md`/`confidence.md` 等上游产物
- 用户明确要求 HTML、离线、可视化或基线度量交付
- 需要与历史基线数据进行对比，量化性能/精度的变化
- 需要将分析结果结构化呈现，便于团队共享和问题追踪
- 迭代优化完成后，验证修改效果

### 与统一调度的边界

本技能只负责消费已有评估结论、时间线和可信度结果并生成报告。没有这些上游产物时，不把“生成完整诊断报告”解释成直接度量请求；先由 orchestrator-skill 完成检索、场景识别和 eval-skill 诊断。

## 子组件

| 组件 | 路径 | 用途 |
|------|------|------|
| 展示格式 | `references/display-format.md` | 报告输出格式与 Markdown 模板定义 |
| 基线数据 | `references/baseline-data.md` | 用于对比的基准性能、精度及 errMsg 质量指标 |
| 度量结果文档 | `references/metric-results.md` | 本次度量原始结果记录规范（含 errMsg 分析字段） |
| 度量结果分析文档 | `references/metric-analysis.md` | 深度分析框架，含 errMsg 质量分析与改进建议模板 |
| HTML 报告模板模块 | 仓库态 `metric-skill/template/report-template-rules.md`；安装态 `metric-skill/template/report-template-rules.md` | HTML 作图与交付的唯一使用规范；同目录包含空白模板 |
| HTML 打包脚本 | `scripts/build_html_report.py` | 初始化工作副本、校验并填充结构化数据、内嵌素材为单文件 HTML |

## 度量维度

| 维度 | 说明 | 关键指标 |
|------|------|---------|
| 性能 | 算子/模型的执行速度 | aicore_time、end2end_time、throughput |
| 精度 | 计算结果的数值准确度 | max_diff、mean_diff vs FP32 参考值 |
| 资源利用率 | 硬件资源使用效率 | AICore 利用率、HBM 带宽利用率 |
| 稳定性 | 多次运行结果的一致性 | 方差、P99 延迟 |
| **errMsg 质量** | 日志中错误信息的完整性与有效性 | 识别完整性、文档符合度、格式规范度、问题指导性 |
| **诊断可信度** | 评估结论本身的证据充分程度 | 证据完整性、证据一致性、因果链闭合性、复现验证、知识对齐 |

## 生成报告步骤

### 1. 填写度量结果

参照 `references/metric-results.md` 中的规范，记录本次运行的原始指标数据。

### 2. 对比基线

按 `references/baseline-data.md` 核对基线来源与环境可比性。只有存在匹配的实测记录时才计算差异及达标判断；没有基线时记录缺口，不使用文档示例或通用固定阈值补造基线。

### 3. 撰写结构化报告

按照 `references/display-format.md` 的模板，将以下内容组织为标准报告：
- 测试环境信息
- 度量结果汇总表
- 与基线的对比分析
- 问题清单（来自评估 Skill）
- 诊断可信度（来自评估 Skill 的可信度评估结果）
- 改进建议（参考 `references/metric-analysis.md`）

报告完成后按 `references/analysis-record.md` 生成本次分析记录副本，写明字段来源、计算或判断过程、证据和限制，与报告一同交付。

### 4. 保留逐项证据强度

沿用 eval 产物中的分数与等级，判定统一见 [可信度规范](../eval-skill/references/confidence-assessment.md)。总分反映诊断材料完整程度；每项主张沿用其实际证据和状态，不按等级升级或抹去已证实机制。保留已确认的直接失败、优先上游假设与未决细节；缺证写清影响，不自动补采。

### 5. 输出用于迭代

报告结论应明确指出：
- 需要修改的算子/配置
- 优先级排序
- 预期优化目标（对照基线的改进幅度）
- 证据缺口及其限制的具体判断

## 生成 HTML 故障报告

用户要求正式故障、诊断、根因、HTML、离线或可视化交付报告时，必须调用报告模板模块。先按以下顺序定位并完整读取第一个存在的文件：

1. 仓库态：`metric-skill/template/report-template-rules.md`
2. 安装态：`metric-skill/template/report-template-rules.md`

模板模块是 HTML 版式、图例、着色、布线、案例隔离和验收规则的唯一来源。metric-skill 只向它传递当前 eval 结论、可信度和报告数据，不在本文件复制或另造作图规则。

读取模板模块后，通过打包脚本初始化、填充和构建：

```bash
python3 scripts/build_html_report.py --init ./report-work
# 按 template/report-template-rules.md 将当前案例的 eval 产物填入 report-data.json
python3 scripts/build_html_report.py \
    --input ./report-work/index.html \
    --data ./report-work/report-data.json \
    --output ./diagnostic-report.html
```

`--init` 从模板模块的空白 `index.html` 生成工作副本和结构化数据入口。所有案例事实必须来自当前 eval 产物；未知信息写“未提供”。构建结束后执行模板模块定义的验收清单。

## 快速报告模板

```markdown
# 度量报告 — <算子/模型名称> — <日期>

## 测试环境
- 设备：Ascend NPU × <N 卡>
- CANN：8.5.0
- 框架：<PyTorch/MindSpore> <版本>
- 批量大小/序列长度：<值>

## 度量结果摘要（与基线对比）

| 指标 | 基线 | 本次 | 变化 |
|------|------|------|------|
| 端到端时间 | Xms | Yms | ±Z% |
| AICore 时间 | Xms | Yms | ±Z% |
| 精度 max_diff | X | Y | — |
| HBM 带宽利用率 | X% | Y% | ±Z% |

## 问题清单
<来自评估 Skill 的评估结论>

## 诊断可信度
- 综合可信度：<score>/100（<HIGH/MEDIUM/LOW/INSUFFICIENT>）
- 关键项：<全部满足 / 未满足项>
- 逐项结论：<已确认机制 / 有依据的候选根因 / 未决细节及证据>
- 案例库沉淀：<CASE-xxx / PCASE-xxx / 不入库（原因）>

## 改进建议
<参考 metric-analysis.md 输出的具体建议>

## 结论
<达标 / 未达标，下一步行动>
```


## 流水线Markdown交付

接收本次 scenario.md、diagnosis.md、confidence.md、promotion.md，交付同一公共外壳的report.md。
字段遵循 [产物契约](../orchestrator-skill/references/pipeline-artifacts.md)：result必含conclusion/confidence/findings/recommendations/limitations。
confidence直接引用confidence.md结果；未知指标/环境为"未提供"，不能将本页模板8.5.0或示例数值写成现场事实。
报告等待、失败、重试都保存同结构report.md，已有章节保留。缺证不触发补采，也不降低诊断能力或额外封顶评分。
HTML作为附属产物仍按原模板生成，Markdown是调度校验与恢复的主交付。
