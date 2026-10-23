# 度量结果文档规范

> 本文档定义每次度量运行后原始结果的记录规范，确保数据可追溯、可对比。

## 一、记录目的

- 保留每次测试的原始数据，供后续趋势分析
- 作为度量报告中定量分析的数据来源
- 便于复现或对比不同版本/配置的测试结果

---

## 二、结果文件命名规范

```
result_<算子或模型名>_<YYYYMMDD_HHMMSS>_rank<N>.json
```

示例：`result_MatMulV2_20260325_102345_rank0.json`

---

## 三、结果数据结构（JSON 格式）

```json
{
  "meta": {
    "name": "MatMulV2",
    "date": "2026-03-25T10:23:45",
    "cann_version": "8.5.0",
    "device": "AscendNPU",
    "rank": 0,
    "dtype": "FP16",
    "input_shapes": ["1024x1024", "1024x512"],
    "batch_size": 1,
    "warmup_iters": 10,
    "measure_iters": 100,
    "test_script": "tests/test_matmul.py"
  },
  "performance": {
    "end2end_time_ms": {
      "mean": 0.35,
      "min": 0.32,
      "max": 0.41,
      "p50": 0.35,
      "p99": 0.40,
      "std": 0.01
    },
    "aicore_time_ms": {
      "mean": 0.21,
      "min": 0.19,
      "max": 0.25
    },
    "throughput_samples_per_sec": 2857,
    "aicore_utilization_pct": 76.3,
    "hbm_bandwidth_utilization_pct": 68.1,
    "hbm_peak_usage_mb": 512
  },
  "accuracy": {
    "reference_dtype": "FP32",
    "max_diff": 0.004,
    "mean_diff": 0.0008,
    "pass_threshold": {
      "max_diff": 0.01,
      "mean_diff": 0.001
    },
    "passed": true
  },
  "errors": [],
  "warnings": ["FP16 overflow detected in 2/100 iterations, auto-recovered"],
  "errmsg_analysis": {
    "identification": {
      "total_errmsg_count": 3,
      "unique_code_count": 2,
      "first_error_code": "EZ9999",
      "first_error_module": "Z",
      "error_cascade_depth": 2,
      "all_codes": ["EZ9999", "EE1002"],
      "all_messages": [
        "EZ9999: Inner Error! Aicore kernel execute failed, device_id=0, stream_id=10, task_id=42, fault kernel_name=MatMulV2.op123",
        "EE1002: Execution_Error_Stream_Synchronize_Timeout"
      ]
    },
    "doc_compliance": {
      "documented_rate": 1.0,
      "documented_codes": ["EZ9999", "EE1002"],
      "undocumented_codes": [],
      "internal_error_count": 1,
      "internal_error_rate": 0.5,
      "description_match": true
    },
    "format_compliance": {
      "code_format_compliant_rate": 1.0,
      "has_ascend_error_block": true,
      "log_line_format_compliant_rate": 0.95,
      "has_file_line_info_rate": 0.90,
      "noncompliant_samples": []
    },
    "guidance": {
      "has_module_identified": true,
      "has_fault_kernel": true,
      "fault_kernel_name": "MatMulV2.op123",
      "has_device_stream_task_info": true,
      "has_root_cause_hint": true,
      "matched_case_ids": [],
      "actionable_rate": 1.0,
      "guidance_score": 85
    },
    "overall_quality_score": 88,
    "quality_level": "GOOD"
  },
  "diagnosis_confidence": {
    "final_score": 78,
    "level": "MEDIUM",
    "dimensions": {
      "D1_evidence_completeness": 20,
      "D2_evidence_consistency": 20,
      "D3_causal_chain": 25,
      "D4_reproduction": 3,
      "D5_knowledge_alignment": 10
    },
    "unmet_critical": [],
    "conclusion_strength": "most_likely",
    "confirmed_facts": ["LayerNorm 中间激活 FP16 溢出（源码 + profiling 证实）"],
    "inferences": ["溢出起始 step 的具体触发条件（缺复现数据）"],
    "missing_evidence": ["debug so 完整符号包", "稳定复现脚本"],
    "case_gate": "pending",
    "case_id": "PCASE-001"
  }
}
```

---

## 四、字段说明

### meta 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 测试目标名称 |
| `date` | ISO8601 | 测试时间 |
| `cann_version` | string | CANN 版本 |
| `device` | string | 设备型号 |
| `rank` | int | 多卡时的 rank 编号 |
| `dtype` | string | 数据类型 |
| `input_shapes` | array | 输入 Tensor shape 列表 |
| `batch_size` | int | 批量大小 |
| `warmup_iters` | int | 预热迭代次数 |
| `measure_iters` | int | 计时迭代次数 |
| `test_script` | string | 测试脚本路径 |

### performance 字段

| 字段 | 单位 | 说明 |
|------|------|------|
| `end2end_time_ms` | ms | 端到端延迟（含 H2D/D2H） |
| `aicore_time_ms` | ms | 仅 AICore 执行时间（来自 profiling） |
| `throughput_samples_per_sec` | samples/s | 吞吐量 |
| `aicore_utilization_pct` | % | AICore 算力利用率 |
| `hbm_bandwidth_utilization_pct` | % | HBM 带宽利用率 |
| `hbm_peak_usage_mb` | MB | HBM 峰值占用 |

### accuracy 字段

| 字段 | 说明 |
|------|------|
| `reference_dtype` | 参考精度类型（通常 FP32） |
| `max_diff` | 最大绝对误差 |
| `mean_diff` | 平均绝对误差 |
| `pass_threshold` | 精度达标阈值 |
| `passed` | 是否达标（true/false） |

### errmsg_analysis 字段

#### identification（识别完整性）

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_errmsg_count` | int | 日志中识别到的 errMsg 总条数 |
| `unique_code_count` | int | 唯一错误码数量 |
| `first_error_code` | string | **首报错错误码**（最优先排查入口） |
| `first_error_module` | string | 首报错所属模块字母（对应 err-messages.md 模块表） |
| `error_cascade_depth` | int | 错误级联深度：首报错触发的次报错链路长度 |
| `all_codes` | array | 所有识别到的错误码列表（去重） |
| `all_messages` | array | 原始错误消息完整文本（含上下文关键行） |

#### doc_compliance（文档符合度）

| 字段 | 类型 | 说明 | 达标标准 |
|------|------|------|--------|
| `documented_rate` | float | 识别到的错误码中，在官方 err-messages.md 中有记录的比例 | ≥ 0.8 |
| `documented_codes` | array | 已在文档中找到定义的错误码列表 | — |
| `undocumented_codes` | array | 未在文档中找到的错误码（可能是新错误或内部码） | 应为空或仅含 E\*9\*\*\* |
| `internal_error_count` | int | 内部错误码（序号 9000~9999 段）数量 | — |
| `internal_error_rate` | float | 内部错误码占所有错误码的比例（内部码需提交ISSUE） | 越低越好 |
| `description_match` | bool | 屏幕打印的错误描述是否与文档定义一致 | true |

#### format_compliance（格式规范度）

| 字段 | 类型 | 说明 | 达标标准 |
|------|------|------|--------|
| `code_format_compliant_rate` | float | 符合官方 6 字符格式（`[E/W/I][模块字母][4位]`）的错误码比例 | = 1.0 |
| `has_ascend_error_block` | bool | 是否存在标准 `Ascend Error Message` 块（AI Core Error 场景必须有） | true |
| `log_line_format_compliant_rate` | float | 日志行符合官方格式 `[Level] ModuleName(PID,PName):DateTimeMS [File:Line]` 的比例 | ≥ 0.9 |
| `has_file_line_info_rate` | float | 日志行中包含 `[FileName:LineNumber]` 字段的比例 | ≥ 0.8 |
| `noncompliant_samples` | array | 不符合格式规范的日志行样本（最多 5 条） | 应为空 |

#### guidance（问题指导性）

| 字段 | 类型 | 说明 | 达标标准 |
|------|------|------|--------|
| `has_module_identified` | bool | 是否能从错误码确定问题所属模块 | true |
| `has_fault_kernel` | bool | AI Core Error 场景是否包含 `fault kernel_name` 字段 | true（EZ9999 时） |
| `fault_kernel_name` | string | AI Core Error 报错算子名称（fault_kernel_name 字段值） | — |
| `has_device_stream_task_info` | bool | 是否包含 `device_id`、`stream_id`、`task_id` 定位三要素 | true（AI Core Error 时） |
| `has_root_cause_hint` | bool | 错误描述是否含有明确根因提示词（timeout/memory/invalid/unsupported 等） | true |
| `matched_case_ids` | array | 在 cases.md 中找到的匹配历史案例 ID 列表 | 越多越好 |
| `actionable_rate` | float | 有明确排查方向（来自 err-messages.md"排查方向"列）的错误码比例 | ≥ 0.8 |
| `guidance_score` | int | 综合问题指导性评分（0~100），见下方评分规则 | ≥ 70 |

#### 综合评分字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `overall_quality_score` | int | errMsg 综合质量评分（0~100）= 识别×25% + 文档×25% + 格式×25% + 指导×25% |
| `quality_level` | string | 质量等级：EXCELLENT(≥90) / GOOD(70~89) / FAIR(50~69) / POOR(<50) |

### diagnosis_confidence 字段

> 直接取评估 Skill `assess_confidence.py --json` 的输出，字段名保持一致。
> 与 `errmsg_analysis` 的区别：后者衡量日志质量，前者衡量结论可信程度。

| 字段 | 类型 | 说明 | 达标标准 |
|------|------|------|--------|
| `final_score` | int | 综合可信度（0~100）= 五维得分之和 | ≥ 70 |
| `level` | string | HIGH(≥85) / MEDIUM(70~84) / LOW(50~69) / INSUFFICIENT(<50) | ≥ MEDIUM |
| `dimensions.D1_evidence_completeness` | int | 证据完整性（满分 25） | ≥ 20 |
| `dimensions.D2_evidence_consistency` | int | 证据一致性（满分 20） | ≥ 14 |
| `dimensions.D3_causal_chain` | int | 因果链闭合性（满分 25） | ≥ 20 |
| `dimensions.D4_reproduction` | int | 复现与验证（满分 15） | ≥ 9 |
| `dimensions.D5_knowledge_alignment` | int | 知识对齐（满分 15） | ≥ 10 |
| `unmet_critical` | array | 未满足的入库关键项（`has_first_error_line` / `chain_no_gap`） | 应为空 |
| `conclusion_strength` | string | `definitive` / `most_likely` / `preliminary` / `direction_only` | — |
| `confirmed_facts` | array | 已由源码/复现/多源日志证实的结论 | 非空 |
| `inferences` | array | 仍属推断的内容（含缺失的证据环节） | — |
| `missing_evidence` | array | 待补材料清单（取评分结果的 `missing_items`） | 应为空 |
| `case_gate` | string | 案例库入库判定：`accept` / `pending` / `reject` | — |
| `case_id` | string | 已沉淀的案例编号（`CASE-xxx` / `PCASE-xxx`），未入库时为 null | — |

关键项未满足时，`case_gate` 一律为 `reject`，与总分无关。

---

## 五、多卡结果汇总规范

多卡测试时，每个 rank 输出独立 JSON 文件，汇总时取各 rank 的：
- **性能**：所有 rank 的 `end2end_time_ms.mean` 取最大值（木桶效应）
- **精度**：所有 rank 的 `max_diff` 取最大值
- **errMsg 质量**：取所有 rank 中 `overall_quality_score` 的最小值（取最差 rank 作为整体质量评估）
- **诊断可信度**：不按 rank 取值。可信度评估的对象是整体诊断结论，多卡场景做一次评估；
  但若各 rank 现象不一致（如仅个别 rank 崩溃），`D2 证据一致性` 需体现该矛盾是否已解释

---

## 六、与基线对比计算公式

$$\text{变化率} = \frac{\text{本次值} - \text{基线值}}{\text{基线值}} \times 100\%$$

- 性能指标（时间越小越好）：变化率为负数表示性能提升
- 精度指标（diff 越小越好）：变化率为负数表示精度改善
