---
name: eval-skill
description: 对 Ascend NPU 的已有日志和故障现场进行清洗、专项评估和诊断分析。当用户明确指定 eval-skill、已经由 orchestrator-skill 路由到本技能，或明确指定单一故障类型（如 AI Core Error、OOM、coredump、通信超时）时使用；仅从日志内容看到这些词不构成直接触发，缺少明确专项或上游编排结果时由 orchestrator-skill 先处理。技能结合领域知识、错误库和历史案例定位根因，评估诊断可信度并输出供度量报告使用的评估结论。
license: Apache-2.0
---

# 日志评估技能 (Eval Skill)

## 适用场景

- 已有完整日志（msnpureport / host / plog 或其组合），需要分析问题根因
- orchestrator-skill 已完成案例检索和场景识别，并路由到本技能进行清洗、诊断或可信度评估
- 用户明确指定单一故障类型、专项分析或直接使用 eval-skill；泛化的“分析/诊断日志”请求先走 orchestrator-skill
- 用户提供或提到 coredump / Linux core / Stackcore / msnpureport / asys 输出，需要分析 CANN 崩溃根因
- 算子执行失败、训练 loss 异常、精度不达标、任务挂死或性能劣化
- 需要将日志信息映射到具体算子/代码位置

## 与统一调度的边界

本技能负责被路由后的日志清洗、专项诊断、可信度评估和案例处置，不负责决定是否需要多个专项 skill 协作。没有上游 `scenario.md` 时，遇到泛化日志分析请求应先让 orchestrator-skill 完成入口检索和场景分类；本技能的 `diagnosis.md` 必须保留证据时间线，供最终报告汇总。

## 评估流程

```
原始日志
  │
  ▼
[Step 1] 清洗 → 去噪、格式化、提取关键片段
  │
  ▼
[Step 2] 错误识别 → 比对 errMsg 文档，分类问题类型
  │
  ▼
[Step 3] 上下文分析 → 结合日志规范和背景介绍，理解执行时序
  │
  ▼
[Step 4] 代码定位 → 通过算子名称和堆栈查找源码
  │
  ▼
[Step 5] 案例匹配 → 比对历史案例库，查找已知解决方案
  │
  ▼
评估结论
  │
  ▼
[Step 6] 可信度评估 → 五维打分 → HIGH/MEDIUM/LOW/INSUFFICIENT
  │
  ├─ HIGH 且关键项满足 ──→ [Step 7] 沉淀到案例库 cases.md ──┐
  ├─ MEDIUM/待补证 ──→ 写入候选区 cases-pending.md      │
  └─ LOW/证据不足 ──→ 回到采集补齐证据后重评             │
                                                        │
              案例匹配增强下一次诊断 ←──────────────────┘
```

可信度决定结论的表述强度和能否入库：HIGH 可作定论，MEDIUM 表述为"最可能原因"，
LOW 必须写作"初步判断"，INSUFFICIENT 只给排查方向不给根因结论。

## 子组件

| 组件 | 路径 | 用途 |
|------|------|------|
| 清洗脚本 | `scripts/clean.py` | 预处理日志，去除冗余信息，提取关键行 |
| 背景介绍 | `references/background.md` | 为 LLM 提供 CANN 领域上下文 |
| errMsg 文档 | `references/err-messages.md` | 官方错误码体系（模块映射、完整错误码列表、常见消息速查） |
| 日志规范 | `references/log-spec.md` | 官方日志格式、字段定义、路径结构、相关环境变量与时序说明 |
| 故障处理参考 | `references/fault-handling.md` | AI Core Error / 内存 OOM / 进程中断 / 进程卡住 四大典型故障专题（含完整定位流程、msaicerr/asys 工具使用、子类型判断和典型案例），以及故障定位工具使用指南 |
| AI Core Error 专项参考 | `references/ai-core-reference.md` | CANN 9.0.0 官方 AI Core / AI Vector Core 排查流程、关键证据和典型案例；仅在现场版本和适用条件可核对时使用 |
| Coredump 命令手册 | `references/coredump-command-playbook.md` | Host core、Device Stackcore、msnpureport/asys、符号路径、源码映射和日志关联的命令模板 |
| Coredump 报告模板 | `references/coredump-report-template.md` | CANN 崩溃专项分析报告模板和证据完整性检查清单 |
| 代码仓地址 | `references/code-repos.md` | CANN 及相关开源仓库地址，便于溯源 |
| 常见案例库 | `references/cases.md` | 历史典型问题及解决方案 |
| 可信度评估规范 | `references/confidence-assessment.md` | 五维评分模型（证据完整性/一致性/因果链/复现验证/知识对齐）、入库关键项、可信度等级与处置 |
| 可信度评分脚本 | `scripts/assess_confidence.py` | 按检查表计算可信度分数、等级和案例库入库判定 |
| 案例沉淀规范 | `references/case-contribution.md` | 入库门槛、案例格式、去重合并、脱敏要求、案例库维护 |
| 案例沉淀脚本 | `scripts/promote_case.py` | 把高可信报告转为规范案例写入 `cases.md` 或候选区 |
| 候选案例库 | `references/cases-pending.md` | 待补证的候选案例（首次沉淀时自动创建） |

## 使用步骤

### 1. 清洗日志

先识别用户提供的日志路径：
- 如果是 `.zip` 压缩包，先解压到临时目录，再按目录模式清洗
- 如果是目录，递归清洗目录中的 `*.log`
- 如果是单个日志文件，按单文件模式清洗

```bash
# 解压 zip 日志包
unzip ./logs.zip -d ./logs_unpacked/

# 清洗单个日志文件
python3 scripts/clean.py --input ./logs/plog_runtime.log --output ./cleaned/plog_clean.log

# 清洗整个目录
python3 scripts/clean.py --input-dir ./logs/ --output-dir ./cleaned/

# 仅提取 ERROR 及以上级别
python3 scripts/clean.py --input ./logs/merged.log --level ERROR --output ./cleaned/errors_only.log
```

### 2. 分析清洗后日志

将清洗后的日志与以下参考文档结合进行分析：
- 先查阅 `references/err-messages.md`，识别错误码含义
- 对照 `references/log-spec.md`，理解日志字段和时序
- 搜索 `references/cases.md`，查找相似历史案例
- 如果存在 coredump、core 文件、Stackcore、SIGSEGV/SIGABRT 或 asys/msnpureport 崩溃产物，加载 `references/coredump-command-playbook.md` 与 `references/coredump-report-template.md` 做专项分析

### 3. 典型故障分析

当识别到以下典型故障时，先读 [处理流公共约定](references/fault-flows/common-flow.md)，再按对应处理流进行深入分析：

| 场景 | 剧本 | 流程 | 重点 |
| --- | --- | --- | --- |
| `card_drop` | [掉卡](references/fault-flows/card-drop-flow.md) | 掉卡定位流程 | npu-smi 查卡/PCIe 断链/告警/单点芯片故障更换 |
| `aicore_error` | [AI Core Error](references/fault-flows/aicore-error-flow.md) | AIC Error 定位流程 | EZ9999 嵌套详情、首错、RAS/ECC、DMI 压测、软硬件判定 |
| `hang` / `comm_timeout` | [卡住与通信超时](references/fault-flows/hang-flow.md) | 超时类问题定位流程 | Notify/Event/Host 建链/流同步 4 类超时、各 rank 进展/退出 |
| `crash` | [进程中断](references/fault-flows/crash-flow.md) | coredump 类问题定位流程 | host dump/device dump 两条线、信号/符号匹配、首错组件 |
| `oom` | [OOM](references/fault-flows/oom-flow.md) | NPU OOM 问题定位流程 | 长稳变化/各组件内存/空闲占用/变化点 |
| `precision` | [精度异常](references/fault-flows/precision-flow.md) | 精度异常定位流程 | 调优前检查/浮点溢出/融合检测/UB Fusion 伪码 |
| `performance` | [性能问题](references/fault-flows/performance-flow.md) | 性能问题定位流程 | Host 慢/Device 瓶颈、profiling 定位、计算/访存/通信/IO 分维 |
| `offline_inference` | [离线推理/ATC](references/fault-flows/offline-inference-flow.md) | 离线推理定位流程/ATC | 版本确认/参数校验/环境变量/内存不足/算子报错 |
| `network` | [网络排查](references/fault-flows/network-flow.md) | 排查网络 | 诊断平台/端口闪断/RoCE 侧/超时代答 |

其他场景按 [错误码](references/err-messages.md)、[日志规范](references/log-spec.md) 和 [背景](references/background.md) 分析，保留其原场景，不硬塞进上述类别。

### 4. 代码定位

如果日志中出现算子名称或文件路径，参考 `references/code-repos.md` 找到对应源码仓库进行深入分析。

### 5. 可信度评估（必做）

得出评估结论后，必须按 `references/confidence-assessment.md` 对结论本身做可信度评估，
不要直接把推断当成定论输出。

```bash
# 生成检查表
python3 scripts/assess_confidence.py --template > confidence.json

# 按诊断实际情况把 checks 中的 value 填为 true/false，然后打分
python3 scripts/assess_confidence.py --input confidence.json

# 输出机器可读结果，供案例沉淀脚本消费
python3 scripts/assess_confidence.py --input confidence.json --json > confidence_result.json
```

填写要点：

- 五维共 17 个检查项，逐项按"是否有证据支撑"判定，没有把握的一律填 `false`
- 关键项（首报错已定位、因果链无跳跃）未满足时不允许入库，无论总分多少
- 非崩溃场景的 `has_crash_artifacts` 填 `true`
- 评分结果的 `missing_items` 直接作为"待补材料"清单写进报告

按可信度等级调整结论表述：

| 等级 | 分数 | 表述方式 |
| --- | --- | --- |
| HIGH | ≥ 85 | 可作定论 |
| MEDIUM | 70–84 | "当前证据下最可能的原因" |
| LOW | 50–69 | "初步判断" |
| INSUFFICIENT | < 50 | 不给根因结论，只给排查方向和补采建议 |

### 6. 沉淀到案例库

可信度评估的 `case_gate` 字段决定是否入库，规则见 `references/case-contribution.md`。

```bash
# 干跑确认将写入的案例内容
python3 scripts/promote_case.py \
    --report ./diagnosis_report.md \
    --confidence ./confidence_result.json \
    --dry-run

# 正式写入（accept → cases.md，pending → cases-pending.md）
python3 scripts/promote_case.py \
    --report ./diagnosis_report.md \
    --confidence ./confidence_result.json

# 候选案例补齐证据、重评达 HIGH 后转正
python3 scripts/promote_case.py --promote PCASE-001 --confidence ./confidence_result.json
```

脚本会自动做三件事，命中任一即中断，需要人工处理后重试：

- **入库门槛**：`reject` 时直接退出并列出缺失证据（退出码 2）
- **脱敏检查**：命中 IP、家目录、凭据、邮箱等模式时中断（退出码 3）
- **重复检索**：疑似已有同类案例时提示优先合并，确认为不同根因用 `--force`（退出码 4）

案例库是被后续诊断复用的知识，错误案例会持续误导诊断。宁可留在候选区，也不要污染主库。

## 评估输出

评估结论应包含以下内容：

```markdown
## 评估结论

### 问题分类
- 类型：[算子计算错误 / 编译失败 / 性能劣化 / 通信超时 / OOM / 其他]
- 严重程度：[FATAL / ERROR / WARNING]

### 根因分析
- 根因描述（具体到算子/模块）
- 相关日志行：`<日志片段>`
- 对应错误码：ExxYYYZZZ（含义：...）

### 影响范围
- 受影响的 rank/设备
- 执行阶段（编译期/运行时）

### 建议修复方向
1. ...
2. ...

### 关联案例
- 参考案例：cases.md#<案例ID>

### 诊断可信度

- 综合可信度：<score>/100（<HIGH/MEDIUM/LOW/INSUFFICIENT>）
- 维度得分：证据完整性 <x>/25 · 证据一致性 <x>/20 · 因果链 <x>/25 · 复现验证 <x>/15 · 知识对齐 <x>/15
- 关键项：<全部满足 / 首报错日志行未定位 / 因果链存在跳跃>
- 已证实事实：
  - <由源码/复现/多源日志证实的结论>
- 仍属推断：
  - <推断内容 + 缺哪一步证据>
- 待补材料：
  - <具体材料 + 拿到后能提升哪个维度>
- 案例库沉淀：<已入库 CASE-xxx / 进候选区 PCASE-xxx / 不入库（原因）>
```
