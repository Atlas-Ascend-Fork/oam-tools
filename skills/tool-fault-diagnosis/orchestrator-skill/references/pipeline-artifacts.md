# Pipeline 逐步产物契约

本页是五个 skill 与调度层共享的产物定义。每个 stage 交付一个 Markdown，成功、等待、失败、重试和恢复均使用同一公共外壳与业务字段；重试记录不能另造只有错误摘要的 JSON/TXT。

## 文件与消费者

主产物默认在 `artifacts/`，使用固定文件名（`scenario.md`、`diagnosis.md` 等）；每次运行在独立的 state-dir下，不同运行互不覆盖。

| 顺序 / step | owner_skill | 主 Markdown | 主要消费者 | 附属材料 |
| --- | --- | --- | --- | --- |
| 入口错误识别（前置） | orchestrator-skill | `case-match.md`、`scenario.md` 中的 `errors` | case_lookup、detect | 原始日志错误证据 |
| 前置初始采集（明确安排时） | collect-skill | `collection.md` | case_lookup | 原始日志、已有现场文件 |
| 1 case_lookup | orchestrator-skill | `case-match.md` | detect、diagnose | 主案例库只读引用 |
| 2 detect | orchestrator-skill | `scenario.md` | clean、diagnose、report | plan.json 为控制计划 |
| 3 clean | eval-skill | `clean-result.md` | diagnose | `clean-audit.md`、清洗视图日志 |
| 4 diagnose | eval-skill + trace-skill | `diagnosis.md` | confidence、promote、report | fault-trace.json、时间线、调用链与证据引用 |
| 5 confidence | eval-skill | `confidence.md` | promote、report | 内部兼容评分输入 |
| 6 promote | eval-skill | `promotion.md` | report、后续任务 | 可选案例写入回执 |
| 7 report | metric-skill | `report.md` | 用户 | 可选 HTML 与图表 |

初始采集不是七步诊断流水线的一部分。流水线不执行补采。JSON 允许作为 plan/state、内部脚本参数或写入回执；正式步骤交付始终是上表 Markdown。

## 公共外壳：所有流水线 Markdown 必填

文件包含**唯一一个 `json` 围栏块**用于无歧义校验，以及中文可读正文。围栏块是 Markdown 的结构化部分，不是另交 JSON。由 runner 生成工作模板，Agent 按模板填写，不手造 run_id 或输入指纹。

| 字段 | 类型与含义 |
| --- | --- |
| schema_version | 字符串，当前 `1.0`；不同于 plan 的 `2.0` 和 state 的 `2` |
| run_id | 字符串，本次分析唯一标识，重试/恢复保持不变 |
| stage | 七个固定 step ID 之一 |
| owner_skill | 上表对应的负责 skill，等价调度也不变 |
| status | pending/running/success/skipped/failed/blocked |
| attempt | 正整数；重试使用新序号，blocked 的重复检查不增号 |
| started_at / finished_at | ISO 8601 时间；pending/running 的 finished_at 可为 null |
| inputs.fingerprint | 当前步骤输入、参数及依赖的 SHA-256 |
| inputs.materials | 数组，每项 `{path, sha256}`；原始文件内容哈希 |
| inputs.upstream | 数组，每项 `{stage, path, sha256}`；前置 Markdown 引用 |
| inputs.parameters | 当前步骤参数对象，如 clean 的 level/mode、execution |
| inputs.dependencies | runner 附加的脚本、输入配置、修订及案例库依赖；Agent 保留 |
| outputs | 数组，每项 `{path, kind, sha256?}`；附属文件必须带 sha256，主文件哈希由 state 保存避免自引用 |
| summary | 当前步骤做了什么、得到什么、停止在何处 |
| evidence_gaps | 数组，列出缺失内容、影响判断与结论边界；不能填未经取得的材料 |
| error | 成功为 null；失败为 `{class, code, message}`，class 区分 transient/permanent/resource/unknown |
| next_action | 下一步骤或当前步骤需完成的动作；缺证只写限制，不自动安排补采 |
| result | 下列各 step 的业务对象，失败也保留已经完成的字段和数据 |

`success` 表示这一步按规范完成，**不表示根因已经证实**。`skipped` 只用于不适用的清洗或未启用/被门槛拒绝的案例写入，并需说明原因。`blocked` 表示等待 Agent 或等价执行产物；未提供某种故障证据本身不能触发无限 blocked。

`result.errors` 表示原始日志中的业务错误证据；公共外壳的 `error` 表示流水线执行失败。两者含义不同，不能相互替代。

## Step 1：case-match.md

以下均为 `result` 字段：

| 字段 | 明确内容 |
| --- | --- |
| status | hit / miss / unavailable，和公共外壳的 success/failed 不同 |
| library_path / library_sha256 | 实际检索的主案例库绝对路径与内容哈希；不存在时 hash=null |
| query_features | codes/modules/operations/symptoms 四类检索特征 |
| errors | 原始输入中识别到的错误证据数组；每项保留 file/line/byte_start/text/level/codes/keyword/timestamp/at |
| matches | 数组，按下述字段记录每个候选，miss 时为空 |
| limitations | 检索覆盖范围、不可读材料、版本未知等限制 |
| input_fingerprint | 检索所用原始扫描与用户描述的指纹，供 detect 核对前驱 |

每个 match 包含 `case_id/title/library_line/signature/applicable_versions/evidence/matched_features/differences/root_cause_status`。
`evidence` 每项给出 `file/line/byte_start/text/at`；`differences` 包含未命中的签名特征及版本/环境适用性待核实状态。
`root_cause_status=candidate_only`：历史结论不能直接作为当前结论。主库不可用时输出 unavailable 与具体原因，然后分类。

## Step 2：scenario.md

| result 字段 | 明确内容 |
| --- | --- |
| primary | 当前分析主入口的场景 ID，不能确定则 unknown |
| secondary | 其他竞争场景 ID 数组，不静默丢弃混合信号 |
| recognition_confidence | HIGH/MEDIUM/LOW/UNKNOWN，只描述路线识别依据，非诊断五维分 |
| uncertain | 布尔值，是否仍有歧义 |
| scenarios | 各场景的证据、优先依据等分类记录；具体键以脚本输出为准 |
| materials | plog/device_log/coredump/stackcore/asys_output/npu_smi/app_log/profiling，每项 present/count/samples |
| errors | 原始输入中识别到的错误证据数组；与 case_lookup.errors 一致，供场景与首错分析使用 |
| missing_materials | 当前未发现的材料 key 数组；仅盘点，不安排补采 |
| route | entry_skill、downstream_skills、selection_reason、skills、references、pipeline_stages；固定七步，references 覆盖主/次场景 |
| input | path/kind/request/max_bytes/max_files/level、coverage 等扫描说明 |
| case_lookup | 实际前驱检索结果，保留 hit/miss/unavailable 与候选 |
| notes | 识别边界与限制 |

`input.coverage` 每文件记录读取字节数、0 基半开扫描/未扫描字节区间、1 基原始行号范围、状态。截断不意味着未扫描段没有异常。阶段不输出根因。

## Step 3：clean-result.md

| result 字段 | 明确内容 |
| --- | --- |
| mode / focus_level / encoding | conservative；关注级别（不删上下文）；实际使用的输入编码 |
| ordering | original_line 或 source_path_then_original_line |
| processed_files | 实际成功处理的文件数 |
| input_lines / kept_lines / collapsed_lines | 输入/保留/仅折叠的明确噪声行数；输入=保留+折叠 |
| files | 每文件 source/sha256/output/input_lines/kept_lines/collapsed_lines |
| audit_path / source_map | 同一个 clean-audit.md 的路径 |
| source_aliases | ZIP 输入时记录提取路径、archive/member/member_index/original_ref/sha256，原行号通过审计回指压缩包条目 |
| applicability / reason | 只有二进制现场、无文本日志时标 not_applicable 并解释，原现场继续交诊断 |

审计文件的 `records` 逐行包含 `source/line/output/output_line/action/reason/focus/text`：
line 是原始 1 基行号；被折叠行的 output_line=null、action=collapsed，text 仍保存完整原文（包括换行）；其他为 kept。
重复 ERROR 不去重，DEBUG/INFO 不按级别删除，无时间戳的堆栈保持位置。审计自身是明细附件，不替代 clean-result.md。

## Step 4：diagnosis.md

| result 字段 | 明确内容 |
| --- | --- |
| analysis_status | 自动证据草稿为 draft，Agent 完成实质诊断和逐项审核后改为 reviewed；evidence_only 仅用于用户明确要求的证据摘要。保留 draft 不能进入后续评分和报告 |
| first_error | `{file,line,text,timestamp,entities,association}` 或 null；明确是否仅为最早可见候选 |
| timeline | 事件数组：ID、时间/时钟、host/PID/rank/device、业务阶段、原文引用、正常/异常/传播角色；无时序证据时明确写无法建立时序 |
| causal_chain | 每跳 from/to、支持证据、反证、supported/unresolved；无闭合链可为空 |
| root_cause | `{description,status,location,evidence,limitations}`，status=confirmed/hypothesis/undetermined |
| alternatives | 竞争假设、支持/反驳证据、excluded/supported/unresolved、缺口 |
| recommendations | 建议、前提、证据、预期影响、已有验证状态；建议不等于执行记录 |
| checks | 原评分 17 项检查，每项 `{value:boolean,evidence,reason}`；不知道即 false |
| references | 实际使用的原始位置、案例 ID/版本、文档、源码 ref；不使用空泛“已查文档” |
| steps | 内部子步骤 `{step_id,status,input_refs,findings,evidence_refs,evidence_gaps,next_step}` |
| classification_review | 当前诊断与 scenario.md 的一致性、冲突信号及复核方向 |

四类剧本每个内部 step 的 findings 字段见 [公共处理流](../../eval-skill/references/fault-flows/common-flow.md) 及对应场景文件。
这些子步骤增量写同一个 diagnosis.md，不产生与子 skill 不一致的错误文件。不能确认根因时使用 undetermined；首错缺失可为 null。

## Step 5：confidence.md

`result` 保留原评分脚本输出：`meta/final_score/level/level_cn/dimensions/unmet_critical/missing_items/case_gate/case_gate_reason`。
`dimensions` 每项是 dimension/name/earned/full，列出 D1–D5 的实得分和满分；17项判定依据通过 inputs.upstream 指向 diagnosis.md 的 checks。`unmet_critical` 是未满足的入库关键项；`missing_items` 是未满足检查的证据缺口。
五维总分 100；HIGH≥85、MEDIUM 70–84、LOW 50–69、INSUFFICIENT<50。保留真实评分，不加调度上限或自动改 checks。
case_gate 为 accept/pending/reject，低分仍产评分 Markdown 并继续报告。

## Step 6：promotion.md

`result` 必含 `enabled/decision/case_gate/target/case_id/mutation_id/reason`。
enabled 默认 false；decision 说明未启用、门槛拒绝、候选/正式入库或已提交复用；target/case_id/mutation_id 未产生时可为 null。
实际写入还记录目标与前后内容哈希、回执；必须能区分“已生成候选正文”和“已写入案例库”。
这是写入步骤的实际处置，不是要求每次都新增案例。诊断事实内容取同一个 diagnosis.md。

## Step 7：report.md

`result` 必含 `conclusion/confidence/findings/recommendations/limitations`。
confidence 引用 confidence.md 的真实分数、等级和 case_gate；findings 每项指向本次诊断的事实/推断及证据。
有真实度量数据时另记 `metrics`（name/value/unit/window/source）、`baseline_comparison`（source/适用版本/base/current/delta）与 `environment`；没有数据写未提供，不套示例数值。
正文包含场景与案例异同、原始证据链、结论及边界、建议、可信度、每步状态与案例处置。HTML 是可选附属交付，其事实来自同一 report.md。

## 前置 collection.md

独立初始采集的清单包含 `collection_id/status/started_at/finished_at/environment/source_root/time_window/files/missing_sources/errors/next_action`。
files 每项包含 path/source_type/size_bytes/sha256/time_range/host/device_id/rank；未提供实体字段为 null。
它是原始材料的说明，不使用七步 stage 枚举，也不是重试失败后请求补采的入口。

## 提交、重试与恢复校验

主产物默认在 `artifacts/`，使用固定文件名；每次运行在独立的 state-dir下，不同运行互不覆盖。
Agent 产物必须维持当前 inputs/run_id/stage，业务内容完整、附属文件真实存在且哈希相符，才可以标成功并恢复。
只存在文件、只写“已完成”、旧输入下的报告、缺字段的 MD 都不能通过。控制状态单独保存主文件哈希，不能人工改 state 来伪造通过。
