# 诊断报告沉淀到案例库规范

> 高可信度的诊断报告应回流到 [案例库](cases.md)，让下一次诊断能在 Step 5「案例匹配」
> 直接命中。本文档定义入库门槛、案例格式、去重合并和候选区管理。
> 可信度评分规范见 [confidence-assessment.md](confidence-assessment.md)；
> 自动化脚本为 `scripts/promote_case.py`。

---

## 1. 闭环位置

```
评估结论 / 崩溃报告
        │
        ▼
  可信度评估（五维打分 + 关键项）
        │
   ┌────┴─────┬──────────────┐
   ▼          ▼              ▼
 accept    pending         reject
   │          │              │
   ▼          ▼              ▼
cases.md  cases-pending.md  补证后重评
   │
   ▼
下一次诊断的 Step 5 案例匹配（知识库增强）
```

案例库是被复用的知识，一条错误案例会让后续所有相似问题被误导。因此入库是**带门槛的**，
宁可留在候选区，也不要污染主库。

---

## 2. 入库门槛

三档判定由可信度脚本的 `case_gate` 字段给出：

| 判定 | 条件 | 去向 |
| --- | --- | --- |
| **accept** | 可信度 ≥ 85（HIGH）**且** 关键项全部满足 **且** 根因已定位 **且** 修复已验证 | 写入 `cases.md`，分配 `CASE-xxx` |
| **pending** | 可信度 70–84（MEDIUM），或 HIGH 但根因未定位 / 修复未验证 | 写入 `cases-pending.md`，分配 `PCASE-xxx` |
| **reject** | 可信度 < 70，或关键项（首报错已定位、因果链无跳跃）未满足 | 不入库，先补证据 |

额外硬性要求（任一不满足即降为 reject）：

1. 关键日志特征必须是**真实日志原文**，不能是复述或臆造的日志行。
2. 必须包含可操作的解决方案，而非"建议进一步排查"。
3. 不得包含内网 IP、主机名、账号、密钥、业务数据等敏感信息（见 §5）。

---

## 3. 案例格式

案例应包含问题现象与版本信息、问题分析、问题根因、解决方案四部分，解决方案应说明临时规避措施和长期解决措施。新案例追加到 `cases.md` 末尾，与既有 CASE-001~006 保持同一结构，并附来源元信息：

````markdown
## CASE-xxx：<一句话问题标题>

### 1. 问题现象描述及版本信息

**1.1 问题描述**
<现象、触发场景、影响范围>

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | <版本>（必选） |
| HDK 版本 | <版本>（必选） |
| 芯片型号 | <型号>（必选） |
| 训推框架版本 | <版本>（可选） |
| Atlas 900 A3 SuperPoD | <如适用>（可选） |

### 2. 问题分析

再次发生同问题时，维护人员如何确认是同一个问题（如通过 plog 日志的关键字、导出 device 日志的报错特征比对）：

```
<真实日志原文，保留错误码、算子名、device/stream/task 等定位信息>
```

### 3. 问题根因
<根因，具体到算子 / 模块 / file:line；"已确认失败现象"与"根因"分开>

### 4. 解决方案

**临时规避**：<临时绕过问题的措施，含命令或代码；无则如实写明>

**长期解决**：
1. <可操作步骤，含命令或代码>
2. ...

**元信息**
- 可信度：<score>/100（HIGH）
- 首报错错误码：<ExxYYYY>
- 验证状态：已验证修复有效
- 来源报告：<报告文件名或链接>
- 收录日期：<YYYY-MM-DD>
````

候选区 `cases-pending.md` 用相同 4 段式结构，编号为 `PCASE-xxx`，并在元信息后额外写明：

```markdown
- 待补证据：<缺什么材料 / 哪个维度未达标>
- 转正条件：<补齐什么后可升为 CASE>
```

---

## 4. 去重与合并

入库前先在 `cases.md` 中检索是否已有同类案例：

```bash
# 按错误码检索
grep -n "EZ9999" eval-skill/references/cases.md

# 按算子名或关键现象检索
grep -ni "layernorm\|allreduce timeout" eval-skill/references/cases.md
```

| 情形 | 处理 |
| --- | --- |
| 同错误码 + 同根因 | 不新增案例；把新增的触发条件、环境或解决方案补进已有案例 |
| 同错误码 + 不同根因 | 新增案例，并在两条案例中互相引用（`参见 CASE-xxx`） |
| 同根因 + 不同错误码 | 新增案例，在关键日志特征里同时列出两个错误码 |
| 完全新问题 | 新增案例，取当前最大编号 +1 |

合并时按适用版本、因果证据和验证记录保留根因表述，不以综合分数替代证据比较；解决方案保留各自适用前提和验证状态。

---

## 5. 脱敏检查

写入前必须清理。入库检查会扫描最终写入的完整案例块；规则包括：

- 内网 IP、主机名、集群名 → `<host>` / `10.x.x.x`
- 用户名、绝对家目录路径 → `$HOME` / `<user>`
- token、密钥、证书路径 → `<redacted>`
- 业务模型名、数据集名（如涉密）→ 泛化为 `<大模型>` / `<业务数据集>`

新增扫描还包括：认证信息（Authorization/Bearer/Cookie/Session）、私钥或证书材料（.pem/.crt/.key/.p12/.pfx）、`/root/<path>` 与 `/Users/<user>`、`host/hostname/node/cluster/server/pod/rack` 标识，以及 model/dataset 名称或路径。

保留对诊断有价值的信息：错误码、算子名、CANN/Driver 版本、shape、dtype、device/stream/task ID。

---

## 5.1 只读脱敏扫描

入库前检查覆盖最终写入的完整案例块，包括问题描述、关键日志、根因、方案和元信息。除入库检查外，可用以下命令只读扫描既有 Markdown，不修改文件：

```bash
python3 scripts/promote_case.py --check --files \
    references/cases.md \
    references/cases-pending.md
```

输出为 `文件:行号 类型 片段`。命中的内容只表示疑似敏感信息，仍需人工确认后修改；脚本不会自动替换。扫描范围包括 IP、用户目录、凭据/认证信息、邮箱、SSH 公钥、私钥或证书材料、主机或集群标识，以及业务模型或数据集标识。

## 6. 脚本用法

正式主产物是 `promotion.md`，字段遵循 [流水线产物契约](../../orchestrator-skill/references/pipeline-artifacts.md)。必须记录评分门槛、候选内容、去重/脱敏结果、目标文件、实际是否写入、案例 ID 和未写原因。`accept/pending` 是准入判定，只有核对实际落盘后才写“已入库”。`reject` 或没有写入时也必须有业务 Markdown。

流水线中以 `diagnosis.md` 为来源，避免在 report 阶段尚未完成时依赖 report.md。诊断的人读章节须包含问题摘要、关键日志、根因分析、修复建议，以匹配脚本抽取规则；JSON 结构字段不能代替这些人读章节。

JSON 评分文件与工具输出只作辅助证据。重试先检查目标文件是否已包含同一来源报告/同一案例，再决定是否需要写入，防止上次已落盘但返回失败时重复追加。不得通过自动 `--force` 绕过去重或缺证。

```bash
# 干跑：只打印将写入的案例内容和目标文件，不落盘
python3 scripts/promote_case.py \
    --report ./diagnosis.md \
    --confidence ./confidence_result.json \
    --dry-run

# 正式写入（自动分配编号、按 gate 选择 cases.md 或 cases-pending.md）
python3 scripts/promote_case.py \
    --report ./diagnosis.md \
    --confidence ./confidence_result.json \
    --cases-dir eval-skill/references

# 候选案例补齐证据后转正
python3 scripts/promote_case.py --promote PCASE-001 --cases-dir eval-skill/references
```

脚本行为：

1. 读取 `confidence_result.json` 的 `case_gate`，reject 时直接退出并打印原因。
2. 从报告中抽取问题标题、日志特征、根因、解决方案，生成规范案例块。
3. 按错误码在目标文件中做重复检索，命中时提示改为合并而非新增。
4. 扫描敏感信息模式，命中时中断并列出需要脱敏的行。
5. 分配下一个可用编号并追加写入。

---

## 7. 案例库维护

| 场景 | 动作 |
| --- | --- |
| 案例被后续诊断证伪 | 从 `cases.md` 移除，并在提交说明写明证伪依据 |
| CANN 版本升级导致方案失效 | 保留案例，在解决方案中标注适用版本区间 |
| 候选案例长期无法补证 | 超过两个版本周期仍为 pending，从候选区归档移除 |
| 案例数量增长 | 每积累 20 条，按故障类型（AI Core Error / OOM / 通信 / 编译 / 崩溃 / 精度）分节整理 |
