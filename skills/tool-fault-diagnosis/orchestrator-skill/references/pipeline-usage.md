# 流水线、度量报告与案例维护

仅在用户明确要求流水线产物、HTML/度量报告、案例维护，或继续已有计划时读取。本指南的步骤与契约沿用现有实现。五个 skill 安装在同一父目录，以下命令从该父目录执行，Python 3.8+。

## 阶段与产物

原始日志 → errors 入口错误识别 → case_lookup 案例检索 → detect 场景识别 → clean 保守清洗 → diagnose 实质诊断 → confidence 完整性评分 → promote 案例处置 → report 度量报告。

入口由 orchestrator 保留错误原文、位置、级别、错误码和时间；案例 hit/miss/unavailable 均继续。主产物分别为 `case-match.md`、`scenario.md`、`clean-result.md`、`diagnosis.md`、`confidence.md`、`promotion.md`、`report.md`，位于 `.cann-orchestrator/artifacts/`。唯一字段规范见 [流水线产物契约](pipeline-artifacts.md)。JSON 用于计划、状态和脚本兼容输入，不替代 Markdown 交付。

`collect-skill` 用于明确安排的初始采集；已有日志进入本流程后不回调采集，也不因完整性低分补采。按 [场景识别规范](scenario-recognition.md) 记录主/次场景和冲突候选，案例命中不确认根因。相关专项按现场选读。

## 准备与清洗

ZIP 先解压至新的临时目录；对原始材料保留可回查的只读副本。目录与单文件使用现有脚本：

```bash
python3 eval-skill/scripts/clean.py --input ./logs/plog.log --output ./cleaned/plog.log
python3 eval-skill/scripts/clean.py --input-dir ./logs/ --output-dir ./cleaned/
python3 eval-skill/scripts/clean.py --input ./logs/merged.log --level ERROR --output ./cleaned/focus.log
```

清洗保留全部级别、正常进展、重复错误、堆栈续行、空行和文件内顺序。只折叠连续完全相同且符合明确 DEBUG 心跳模式的噪声，保留原文、次数和原行号。`--level ERROR` 只标重点；合并不按单行时间戳排序。编码错误、覆盖原文和输出冲突须报错。详见 [清洗与处理流公共约定](../../eval-skill/references/fault-flows/common-flow.md)。

## 运行与人工诊断交接

```bash
python3 orchestrator-skill/scripts/detect_scenario.py --input ./logs/ --request "训练中断" --plan-out plan.json
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json --dry-run
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json --status
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json --resume
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json --restart-from clean
```

`diagnose` 调用 trace-skill 准备时间线和证据草稿，以 `blocked` 交给当前 Agent。Agent 继续核对原文、专项适用条件及竞争解释，完成 `diagnosis.md` 的业务字段、17项依据和人读结论；将 `result.analysis_status` 改为 `reviewed`、顶层 `status` 改为 `success`，保留 `run_id/inputs/outputs` 及附件哈希，再 `--resume`。无需因正常交接再次索要确认。

根因未确定时仍解释已证实机制、候选、限制和下一步，填 `root_cause.status=undetermined`。`stages.diagnose.execution="evidence_only"` 只用于明确要求证据摘要的任务，不表示根因诊断完成。report 使用 metric-skill 保留已审核的诊断、时间线和建议。

专项脚本不可用或计划明确安排人工等价执行时，可设 `stages.<step>.execution="manual_equivalent"`；保留同一步骤、Markdown模板和当前 `run_id/stage/attempt/inputs`，不能重命名旧报告代替本次产物。脚本缺失进入该等待接口。

## 完整性与案例维护

按 [可信度规范](../../eval-skill/references/confidence-assessment.md) 逐项核对五维17项材料依据，没有把握填 `false`；非崩溃场景的 `has_crash_artifacts` 填 `true`。脚本汇总不是根因验证：

```bash
python3 eval-skill/scripts/assess_confidence.py --template > confidence.json
python3 eval-skill/scripts/assess_confidence.py --input confidence.json
python3 eval-skill/scripts/assess_confidence.py --input confidence.json --json > confidence_result.json
```

HIGH≥85、MEDIUM70–84、LOW50–69、INSUFFICIENT<50 原样记录；低分仍交付已支持的机制、候选和证据边界。`missing_items` 记录具体材料缺口，不触发补采或降低诊断要求。关键项（首错定位、因果链无跳跃）不满足时禁止入库；高分不自动确认根因。

案例维护遵循 [案例沉淀规范](../../eval-skill/references/case-contribution.md)，默认处置不写库。明确安排维护时先 dry-run：

```bash
python3 eval-skill/scripts/promote_case.py --report ./diagnosis_report.md --confidence ./confidence_result.json --dry-run
python3 eval-skill/scripts/promote_case.py --report ./diagnosis_report.md --confidence ./confidence_result.json
python3 eval-skill/scripts/promote_case.py --promote PCASE-001 --confidence ./confidence_result.json
```

`case_gate` 决定 accept/pending/reject。脚本以退出码2拒绝未达门槛、3拒绝未脱敏信息、4报告疑似重复；先核对现有条目，只有确认不同根因才使用 `--force`。正式案例与候选区保持区分。

## 重试与恢复

调度降级仅换等价执行方式，不跳诊断、切场景、改清洗级别或压低评分上限。transient/resource 执行错误沿现有契约重试；永久、未知、中断错误停止。blocked 不耗重试次数；案例写入副作用不确定时先核对回执。低可信度或缺证不触发无限重试。

已完成阶段仅在输入、参数、脚本、上游和附件内容哈希一致时复用；重试保留原 Markdown 快照。详见 [调度降级与重试](degradation-retry.md)、[断点恢复](checkpoint-recovery.md)。最终回复仍包含完整诊断正文，文件或 HTML 作为附属交付。
