---
name: cann-perf-breakdown
description: |
  NPU 性能数据拆解技能。以模型源码为主证据拆解结构，再把 kernel_details.csv 的性能数据挂到该结构上。
  触发场景：分析 kernel_details.csv、拆解性能数据到模型层级、分析大模型性能瓶颈、仅模型代码做架构拆解、仅性能数据做诊断（委托 cann-npu-perfanalysis）。
  适用于任意 Transformer 模型族，不假定任何特定模型的模块名或 kernel 名。
---

# NPU 性能数据拆解技能

将 NPU profiling 输出的 `kernel_details.csv` 按 Transformer 模型结构进行层级拆解，生成结构化的 JSON 和 Markdown/HTML 分析报告。

---

## 适用场景

| 场景 | 说明 |
|------|------|
| 大模型性能分析 | 分析各类 Transformer 模型 |
| 层级耗时拆解 | 拆解 Embedding/Block/Head 各层耗时 |
| Block 内部分析 | 分析 Attention、MLP、Norm 子层 |
| 架构特征识别 | 识别 MLA、MoE、GQA 等架构 |
| 仅模型代码 | 仅做结构拆解，不绑定具体性能数据（多分支用 `branches` 表达） |
| 仅性能数据 | 委托给仓库内的 `cann-npu-perfanalysis` skill 做 8 维诊断 |

---

## 环境前置检查（每次会话首次使用本 Skill 时，先于一切 Mode 判定）

```bash
python3 -c "import yaml" || pip3 install "PyYAML>=5.4"
```

- 依赖只有 PyYAML 这一项，供本阶段（1-perf-breakdown）的 runtime YAML 解析（`extract_model_manifest.py` / `detect_trace_scope.py`）使用；其余脚本只依赖标准库。
- 探测失败（返回非 0 且报 `No module named 'yaml'`）时：先自行安装；无外网或安装失败时，**停止一切 runtime YAML 相关步骤**（checkpoint 判定、trace scope），向用户转述安装命令并说明「`--checkpoint-config` 可绕过 runtime YAML」，不得继续对 runtime YAML 做任何文本扫描式替代。
- 此检查失败不影响 Mode 判定与不读 YAML 的脚本；但 runtime YAML 相关步骤在依赖就绪前不可执行。

## 入口分派（Mode 判定）

启动时检查工作目录，按以下优先级判定模式：

| 条件 | 模式 | 行为 |
|---|---|---|
| 有模型源码（`*modeling*.py` 等） **且** 有 `kernel_details.csv` 或 `raw_ops*.json` | **Mode A** | 完整 12 步批判闭环（schema v2），输出 manifest + config + critique + validation + score；达标后才输出报告与指标 |
| 仅模型源码 | **Mode B** | 提取并**校验**架构（`model_manifest.json`）后输出结构树 `model_structure.json`（v2，`op_indices=[]`，可加 `branches`）。**不是**空 op tree，须过架构校验。详见 `references/mode_b_branches.md` |
| 仅性能数据（csv 或 `ASCEND_PROFILER_OUTPUT/`） | **Mode C** | 委托仓库内的 `cann-npu-perfanalysis` skill。详见 `references/mode_c_delegate.md` |

> Mode C 不进入结构拆解；Mode A 走完整 12 步；Mode B 至少走 Step 1-3（架构提取+校验+结构树）。

**核心区分（schema v2，详见 `references/structure_analysis_guide.md` §C/§E）**：
- **学习到的模型层**（`architecture.layer_groups` / `prediction_modules`）≠ **运行时调用**（`trace_instances`）。
- MTP/spec decoding：外层循环重复调用**同一个**学习到的 decoder layer，记为“1 learned layer + N invocations”，**禁止**写成 N 个模型层或伪层号 `6,7,8`。
- **`children` 只表达包含关系**，相邻不等于有数据流边。残差、并行支路、skip 一律走变量传递，必须在 `branches` 里显式声明；未声明的边在下游就不存在，**下游禁止猜测补边**。
- **性能数据只覆盖采集到的范围**：未被采集的层不得外推指标。采集范围可选地记在 `trace_scope`（`full_model` / `rank_local` / `pipeline_stage_local` / `unknown`），无证据时留空或写 `unknown`，不得声称 pipeline rank。

**覆盖四分类（严格模式 unmapped 必须为 0）**：
- `mapped_model_ops`：模型模块算子（trace_instances + stages + structures 叶子）。
- `mapped_runtime_ops`：运行时辅助算子（runtime_auxiliary）。
- `excluded_profiler_ops`：**仅**纯 profiler/bookkeeping，`reason_code` 用有限枚举 + `evidence`；主计算算子（MatMul/Attention/Norm/MoE/通信/Gather/KVcache/采样）禁止 excluded。
- `unmapped_ops`：归属未知 = 映射未完成，**严格校验必然失败**（填 reason 不算完成）。
- 探索模式 `--allow-unmapped` 状态为 `exploratory`，绝不为 `passed`，报告显著标注未验证。
- 每个代表 step 的全部 op 必须落入前三类之一；映射规程见 `references/ai_mapping_protocol.md`。
- **100% Kernel 覆盖不等于语义正确**：覆盖率只证明每个 op **有** owner，不证明 owner **对**。把 Attention 的 MatMul 整段塞进 MLP，覆盖率仍是 100%。Q/K/V 分支、残差、层边界和尾部阶段必须通过 `critique_report.json` 的独立批判。

---

## 职责边界（先读这一节）

本 skill 是**流程组织者**，不是自动拆解器。四个角色各司其职，越界即为错误：

| 角色 | 负责 | 禁止 |
|---|---|---|
| **Skill** | 组织流程、准备证据、规定输出格式、提供候选提示 | 替 LLM 决定模块归属 |
| **拆解 LLM** | 阅读源码，完成模块结构拆解与 trace 归属 | 把候选提示当答案照抄 |
| **诊断 LLM** | 普通定向证据不足或错误属于非候选产物时，提出哈希绑定、路径受限的补丁 | 修改原始证据、基础 manifest、校验器或 Skill 代码 |
| **批判 LLM** | 独立复查候选，只输出问题 | 直接修改 `analysis_config.json` |
| **确定性脚本** | 只验证可机械证明的事实 | 对语义归属下结论 |

**adapters、重复区间（`op_segments.json`）和 Kernel anchor 只是候选提示**，不得直接决定最终模块
归属，也不得单独产生 `passed`。**禁止**把本 skill 改造成基于固定 Kernel 名或固定模型模板的自动
拆解器：同一语义在不同模型族、不同后端版本下 kernel 名完全不同，把某个族的名字写死就是把适配器
该做的事变成协议。

Mode A/B 运行只读取本 Skill 的白名单资源，不得读取 Skill 2 或 Skill 3；下游只通过正式输出接口衔接。

---

## Mode A 会话编排（薄 orchestrator agent）

当运行环境支持 subagent 时，主会话只创建一次不继承历史的 **orchestrator agent**，传入本 Skill
路径、`--model-dir`、`--csv`、可选运行参数和固定 `--out`。创建时必须使用 `fork_turns=none`；禁止把
主会话历史、旧候选或旧批判复制给 orchestrator。Mode C 继续使用自己的委托协议，不经过本节。

orchestrator 不是第二个状态机，也不自行判断语义路由。`run_breakdown.py` 输出 JSON 的 `final` 字段是
唯一状态来源，`handoff` 是唯一 CLI 回灌来源；进程退出码只表示 CLI 交接结果，不得把退出码 0 当成
整个拆解完成，也不得把 `needs_revision` 的非零退出码当成工具缺陷。orchestrator 只执行以下机械循环：

| `final` | 动作 |
|---|---|
| `awaiting_ai_mapping` | 用 `fork_turns=none` 创建 mapping worker，消费 `ai_mapping_request.json` envelope 及其 `context_manifest.inputs`，写入 `output_expected` |
| `needs_revision` | 用 `fork_turns=none` 创建 revision worker，消费 `revision_request.json` envelope 及其 `context_manifest.inputs`，写入完整的 `output_expected` |
| `awaiting_controlled_diagnosis` | 用 `fork_turns=none` 创建 diagnosis worker，消费 `diagnostic_request.json` 并写入 `diagnostic_patch.json` |
| `awaiting_targeted_critique` | 用 `fork_turns=none` 创建独立 targeted critic，消费当前定向请求并写入定向报告 |
| `awaiting_final_critique` | 用 `fork_turns=none` 创建独立 final critic，完成当前 SHA256 的十一项批判 |
| `passed_at_cap` / `blocked_*` / `failed_*` | 停止循环，向主会话返回终态收据 |

worker 可以读取 request envelope 中的 `task`、`blocking_issues`、`rules`、`output_expected` 和 session
约束；证据文件仍严格限于 `context_manifest.inputs`。每个 worker 完成后，orchestrator 直接应用
`handoff.set_options`、移除 `handoff.clear_options`，然后重新调用 `run_breakdown.py`；禁止自行推导或保留
另一套 CLI 路由。diagnostic patch 是一次性输入：应用后 `handoff` 会清除 `--diagnostic-patch` 并把
`--analysis-config` 切到 `analysis_config.diagnostic.json`；驱动通过 `diagnostic_application.json` 继续绑定
已验证的 `model_manifest.hypothesis.json`，不得重放 patch 覆盖后续 revision。

orchestrator 仅保留阶段名、request/output 路径、SHA256、阻断计数和 `handoff`，不得读取 worker 的完整
源码片段、raw op、候选正文或批判正文，也不得把 worker 对话带到下一阶段。普通 `awaiting_*` 由
orchestrator 内部消费，不唤醒主会话。

主会话只验收 `terminal_receipt`：`final`、`out_dir`、正式产物路径与 SHA256、validation/critique/score 状态、
阻断计数和 `decision_required`。主会话不得重复执行十一项语义批判；最终语义结论仍只来自独立 final
critic。`blocked_tool_defect`、`blocked_missing_external_evidence` 和 `failed_*` 必须设置
`decision_required=true` 并交回主会话，不得由 orchestrator 擅自扩大修复权限。

若运行环境不支持 subagent，允许在当前会话按相同 request/response 契约执行，但每个阶段仍只能读取
其 `context_manifest.inputs`，不能用聊天历史补足 request 缺失字段。

---

## 工作流（Mode A）

```
1  发现输入：模型源码、checkpoint config.json、runtime config、trace
   ↓
2  单次完整源码扫描 + 提取证据（确定性）：
     extract_source_index.py     → source_index.json
     extract_model_manifest.py  → model_manifest.json
     extract_dataflow.py        → dataflow_source.json
     analyze_kernels.py         → raw_ops.json / _details / .compact
     device_freq.py             → device_freq.json
     segment_layers.py          → op_segments.json（候选提示，非答案）
   ↓
3  prepare_ai_mapping            → 自包含 ai_mapping_request.json + contexts/initial_mapping/context_manifest.json
   ↓
4  【干净 mapping worker】按 ai_mapping_protocol.md 输出 analysis_config.json
   ↓
5  写入 source_scan_receipt.json；后续禁止重新向 LLM 投喂完整源码
   ↓
6  run_validation.py（schema/structure/dataflow/coverage 预终态门禁）
   ↓ 未通过或候选经修正
7  prepare_revision_context.py + prepare_targeted_critique.py
     → 完整当前候选、issue 相关候选节点/源码函数片段/raw op 切片和阶段 context_manifest.json
   ↘ 普通证据不足或需协调非候选产物：prepare_diagnostic_context.py
     → 干净上下文诊断 → validate/apply_diagnostic_patch.py → 派生候选/manifest hypothesis
   ↓
8  【独立定向批判 LLM】仅检查改动范围 → targeted_critique_report.json
   ↓ 预终态确定性门禁和定向批判全部通过
9  prepare_critique.py → critique_request.json；使用干净上下文（fork_turns=none）
   ↓
10 【独立批判 LLM】完成最终十一项检查 → critique_report.json
   ↓
11 validate_critique.py + score_breakdown.py
     → quality_rate × evidence_cap = final_score
   ↓ 有阻断问题
12 回到 7；修正后的候选先过确定性门禁和定向批判，再对新文件哈希重做最终十一项批判
   ↓ 通过
13 compute_metrics.py → metrics_report.md + metrics_findings.json（咨询性质）
```

完整 checkpoint 配置可用 `run_breakdown.py --checkpoint-config <config.json>` 显式传入；它优先于
runtime YAML 的 `model_path` 和 Python 默认参数，并以路径 + SHA256 绑定 manifest。不要把完整配置
正文交给 mapping worker，worker 只消费 manifest 中确定性提取后的 facts。

同一 learned layer 因采集流或 profiler 行为形成多个模板时，每个顶层 structure 必须声明
`architecture_group_type`（learned owner）和 `runtime_pattern`（采集模板身份）。pattern 名不是新的
`architecture.layer_groups[].type`；`invocation_index` 也不是 `model_layer_index`。

**状态机**（`run_breakdown.py` 的 `stage`）：

| 状态 | 含义 | 下一步 |
|---|---|---|
| `awaiting_ai_mapping` | 缺候选拆解 | 消费 `ai_mapping_request.json`，产出 `analysis_config.json` |
| `awaiting_controlled_diagnosis` | 普通定向修正无法安全覆盖当前错误 | 在 `fork_turns=none` 上消费 `diagnostic_request.json`，输出 `diagnostic_patch.json` |
| `awaiting_targeted_critique` | 修正候选需要与改动范围对应的独立检查 | 消费 `targeted_critique_request.json`，产出定向报告 |
| `awaiting_final_critique` | 候选已过全部预终态门禁 | 在新窗口或 `fork_turns=none` 的 subagent 中完成最终十一项批判；这是独立上下文，不是新输出目录 |
| `needs_revision` | 确定性门禁、定向批判或最终批判有阻断问题 | 在 `fork_turns=none` worker 中只消费当前 `revision_request.json` 白名单，输出完整当前候选；禁止读取历史产物 |
| `passed_at_cap` | 在当前证据上限下通过 | 进入指标与下游 |
| `blocked_no_progress` | 连续两轮没有定义内进展 | 输出仍未减少的阻断类别 |
| `blocked_max_revisions` | 4 次语义修正仍未通过 | 输出根因分析，不得降门槛 |
| `blocked_missing_external_evidence` | 必须补充 checkpoint/runtime 证据 | 保持 unknown，报告缺失证据，不得猜值 |
| `blocked_tool_defect` | 解析器、checker 或路由协议有缺陷 | 修复 Skill；模型不得修改工具代码绕过 |

### 通过条件

`passed_at_cap` 需要**同时**满足三条，缺一不可：

1. **批判无阻断问题**：`critique_report` 的十一项全为 `passed`，无 `error` issue，且哈希绑定当前输入。
2. **质量达标**：`quality_rate >= 0.95`，且每个可运行核心维度达最低比例（架构 `0.88`、
   数据流与分支 `0.90`、层与子模块边界 `0.90`、Kernel 覆盖 `1.00`、证据 `0.80`）。
3. **全部 hard gates 通过**（见下「硬性否决项」）。

> **禁止**重新使用 `final_score >= 95` 作为门禁。`final_score = quality_rate × evidence_cap`
> 只是描述，不是阈值。证据上限为 90 的输入若质量达标，同样是 `passed_at_cap`——上限描述的是
> **输入有什么**，不是**拆解对不对**。

**停止条件**：

1. `passed_at_cap`。
2. 连续 `--stall-limit` 轮无进展（默认 **2**）→ `blocked_no_progress`。
3. 语义修正达到 `--max-revisions`（默认 **4**）仍未达标 → `blocked_max_revisions`；旧参数名
   `--max-iterations` 保留为兼容别名。

进展只指以下阻断计数在其他类别不恶化时至少一项减少：deterministic error、hard gate、
`unmapped`、duplicate、out-of-range、定向批判阻断项。分数变化本身不算进展。`--stall-limit 0`
仍为兼容而接受，可显式关闭早停。中间轮只运行确定性校验和定向批判；最终十一项批判不参与
中间轮，也不复用旧报告。候选修正后若再次进入最终阶段，必须对新文件 SHA256 重做全部十一项。
候选 SHA256 与最近一次已评估快照相同，不得再次启动 targeted critique，直接记为无进展；targeted
报告若把当前确定性 validation 中仍为 error 的同 ID blocker 判为 passed，报告无效且不能清除 scope，
并直接回到候选修订而不是再次请求批判。

历史最佳候选排序依次使用：**hard gate 数量 → quality rate → final score**。hard gate 在最前，
因为它是分类判定而非程度判定：把主计算藏进 `excluded` 的候选不是"稍差一点"，若按分数优先排序，
它会成为下一轮的修正基线，把缺陷带着更好看的分数继续传下去。

### 证据上限（evidence_cap）

| 输入 | evidence_cap |
|---|---:|
| 源码 + checkpoint config + trace | 100 |
| 源码 + trace，无 checkpoint config | 90 |
| 源码 + checkpoint config，无 trace | 75 |
| 只有源码 | 65 |
| config + trace，无源码 | 45 |
| 只有 trace | 30 |
| 只有 config | 25 |

**必须区分 checkpoint `config.json` 与源码中的 Python 默认参数**：Python 默认值不能视为已绑定
checkpoint（部署时可能被覆盖），对应 `evidence_level=4`，不计入 `has_checkpoint_config`。

### 硬性否决项（任一存在即不得通过）

- trace 主计算 op 没有 owner
- 同一 op 有多个 owner
- 主计算 op 被放入 profiler excluded
- runtime invocation 被写成多个 learned layer
- 源码明确调用的主模块在候选结果中缺失
- 候选包含源码无法解释且未声明 deviation 的模块
- 残差、并行或 skip 拓扑与源码矛盾
- 伪造或错误 source_ref
- checkpoint config 与源码/候选属于不同模型变体
- critique 报告未绑定当前输入文件哈希
- 源码已证明两个不同顶层 owner 之间存在激活依赖，但候选没有声明顶层 `dataflow.edges`

不得通过删除主计算 Kernel、扩大 `excluded_profiler_ops`、伪造 source_ref、合并本应独立的分支或
降低阈值来消除失败项。达到 4 次修正上限时**必须**输出根因分析：当前 quality_rate 与证据上限、每个
未达标维度的分差、卡住的批判检查项、以及缺失的证据类型。

### 判据库分层

| 层 | 内容 | 权限 |
|---|---|---|
| `deterministic` | schema、索引、覆盖、重复、source_ref、层号集合、哈希 | 可独立判定失败 |
| `semantic_critic` | 模块归属、边界、数据流语义、trace 与源码对应关系 | 由批判 LLM 判定 |
| `hints_only` | Kernel anchor、shape、重复序列、模型族 adapters | **不得**单独产生 `passed`，**不得**决定模块 owner |

达到 4 次修正上限仍未达标时，**必须**输出根因分析：当前分数、每个未达标维度的分差、卡住的语义检查项、以及缺失的证据类型；禁止通过降低门槛、删除主计算 Kernel 或扩大 excluded 来提分。

### 单次源码扫描与上下文白名单

- 一次拆解从启动到通过或阻断必须固定使用同一个 `--out`。诊断、校验或批判失败后修正对应输入并在
  原目录重入，禁止自行创建 `*-final`、`*-retry` 等兄弟目录重新运行；只有用户明确要求独立对照实验时
  才能新建输出目录。
- raw ops 和 dataflow 产物按输入哈希复用：`evidence_extraction_receipt.json` 同时绑定输入、提取器和
  产物 SHA256；任一哈希变化才重新提取。
- 步骤 2 只完整扫描一次源码，确定性生成 `source_index.json`：记录源码相对路径、文件 SHA256、
  类/函数和 `__init__`/`forward` 行号范围，并计算整体 `source_bundle_hash`。
- 首次候选完成后写 `source_scan_receipt.json`。后续脚本可重算文件哈希以检测漂移，但 LLM 只能读取
  index、哈希、issue 相关函数片段和 raw op 片段，不得再次接收源码树。
- 首次候选和源码漂移后的新候选都必须通过 `--source-bundle-hash` 确认当前 mapping request；驱动还会
  交叉校验 request/context 固化的 `source_index.json` SHA256 后才记录 receipt。
- `source_bundle_hash` 变化立即废弃 receipt、候选上下文和全部批判，回到 `awaiting_ai_mapping` 重新扫描。
  新候选必须用 `--source-bundle-hash <当前 hash>` 显式确认其基于新扫描生成，否则驱动拒绝重新记录 receipt。
- 每个 LLM 阶段都生成独立 `contexts/<stage>/context_manifest.json`。`inputs` 是唯一白名单；
  `iterations/` 中的旧 config/validation/critique/revision request 仅供审计，禁止进入当前请求。
- 确定性校验由脚本消费完整产物，主会话只读取 `run_breakdown.py` 输出的状态摘要；失败时只把当前
  `revision_request.json` 白名单交给修正 LLM，不得把完整 `validation_report.json` 回读到主会话。
- Markdown、HTML、UI JSON、截图和浏览器验收产物永远不得进入拆解、修正或批判请求的 `inputs`。

### 受控诊断与补丁边界

默认仍走 `revision_request.json` 的 candidate-only 定向修正。只有目标不在候选中、错误属于 manifest
等非候选产物，或 checker 要求的定向证据无法形成时，才进入受控诊断。路由只读取 checker 声明的
通用 `repair_policy`：owner artifact、repair class、allowed targets/path prefixes、required evidence
和 trace selectors；禁止按模型族或 issue ID 写死中央分支。
只有本轮确定性 validation/checker 输出是可信策略来源。LLM 生成的 targeted/final critique 可以补充
问题与证据，但其中即使出现 `repair_policy` 也必须剥离，不能据此增加目标文件或路径权限。

诊断 LLM 只读 `diagnostic_request.json` 的 `context_manifest.inputs`，按
`schemas/diagnostic_patch.schema.json` 输出 `proposed_patch`、`insufficient_external_evidence` 或
`tool_defect`。每项补丁操作必须带当前源码片段或 op slice 证据，且路径位于 `allowed_targets` 内。
`raw_ops*`、源码/索引、validation、checker/Skill 代码和基础 `model_manifest.json` 永远只读；manifest
修正只能写入绑定基础 SHA256 的 `model_manifest.hypothesis.json`。

```bash
python scripts/run_breakdown.py ... \
  --analysis-config outputs/analysis_config.json \
  --diagnostic-patch outputs/diagnostic_patch.json \
  --out outputs
```

驱动先验证请求、基础产物哈希、路径权限与证据范围，再生成派生产物并重新运行确定性门禁。诊断不评分、
不自行通过；最终 `passed_at_cap` 时才将派生候选发布回正式 `analysis_config.json`，下游接口保持不变。

> **通用能力 vs 外部输入**：正式流程对**每个具体 trace** 用 `scripts/run_breakdown.py`
> 驱动确定性步骤 + AI 按 `references/ai_mapping_protocol.md` 生成映射（op 数/顺序随
> batch/seq/next_n/并行而变）。仓库不携带模型源码、权重、profiling 数据或测试 fixture；
> 使用时通过 `--model-dir`、`--source-dir` 和 profiling 输入路径提供外部证据。

**独立批判与统一校验命令**：

```bash
# 仅在预终态确定性门禁和必要的定向批判全部通过后打包最终证据
python scripts/prepare_critique.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --dataflow outputs/dataflow_source.json \
  --checkpoint-config models/<your_model>/config.json \
  --source-index outputs/source_index.json \
  --raw-ops-compact outputs/raw_ops.compact.json \
  --context-manifest outputs/contexts/final_critique/context_manifest.json \
  -o outputs/critique_request.json

# 使用新窗口，或 Codex subagent `fork_turns=none`；只读取 context_manifest.inputs

# Step 8：确定性复核批判证据
python scripts/validate_critique.py \
  -q outputs/critique_report.json \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --dataflow outputs/dataflow_source.json \
  --source-index outputs/source_index.json \
  --source-dir models/<your_model> \
  -o outputs/critique_validation.json
# 这里的 status 只回答「报告是否可采纳」（格式、哈希、定位符真实性）；
# 「候选是否放行」看 detail.clears_candidate，两者不可互相推断

python scripts/run_validation.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir models/<your_model> \
  -o outputs/validation_report.json
# status != passed 时阻断；--allow-warnings 仅用于分诊，不属于正式通过

# Step 9：按证据上限评分
python scripts/score_breakdown.py \
  -v outputs/validation_report.json \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  -q outputs/critique_report.json \
  --critique-validation outputs/critique_validation.json \
  -o outputs/breakdown_score.json
# passed_at_cap != true 时读取 revision_request.json 定向修正，禁止生成正式报告
```

---

### Step 1: 提取单 Step 数据

先枚举所有 step 并选择非 warmup 的代表 step。未显式传 `-s` 时，
`analyze_kernels.py` 会按 kernel_count + kernel 类型分布寻找稳定 step 组；
若该组最早 step 的 kernel_sum 相比后续 step 中位数是明显离群值，则跳过该
warmup/outlier step，并选择后续 step 中最接近中位数的一步。若最早 step 不离群，
保留最早稳定 step。需要强制复现某个 step 时再显式传 `-s`。

```bash
python scripts/analyze_kernels.py \
  -f kernel_details.csv \
  -o outputs/raw_ops.json \
  -d outputs/raw_ops_details.json \
  -m outputs/steps_summary.md \
  --compact-out outputs/raw_ops.compact.json
```

**作用**：从 `kernel_details.csv` 提取单个 step 数据，避免后续分析 token 消耗过大。

| 输出 | 用途 |
|---|---|
| `steps_summary.md` | 所有 step 的 kernel_count、kernel 类型和耗时概览，含自动选步原因 |
| `raw_ops.json` | 自动选择或 `-s` 指定的单 Step kernel 概要，enrich/校验脚本用 |
| `raw_ops_details.json` | 单 Step kernel 详情（含 CSV 全部字段），Step 4/5 报告与指标用 |
| `raw_ops.compact.json` | Step 2 投喂给 AI 的精简视图（删除 `start_time_us`/`duration_us`，连续相同算子折叠）|
| `device_freq.json` | AI Core 实测频率与交叉验证结果，下游所有 cycle 派生指标的分母 |

每个 operator 含 `org_index`，表示其在 `kernel_details.csv` 中的 0-based 行号。

### AI Core 频率（Step 4b）

```bash
python scripts/device_freq.py \
  -d outputs/raw_ops_details.json \
  --trace ASCEND_PROFILER_OUTPUT/trace_view.json \
  -o outputs/device_freq.json
```

两个彼此独立的来源，分别上报，不合并：

- `declared`：trace_view.json 里的 `AI Core Freq` 计数器事件。**一次采集通常只有
  两个采样点**，所以它是标称值，不是频率曲线。
- `derived`：逐 kernel 用 `cycles / time / cores` 反推，样本密集，而且它才是下游
  cycle 派生指标真正依赖的那个值。两者冲突时以 `derived` 为准，并在
  `cross_check.agreement` 里显式报出 mismatch，绝不取平均掩盖分歧。

**核数除数是关键**。`aic_total_cycles` 是该 kernel 占用的所有 core 的累加，所以只除
时间得到的是 cores × clock —— 24 核 kernel 会读成约 44 GHz。AIV 计数器在 `MIX_AIC`
kernel 上要优先用 `Mix Block Dim`（向量段与 cube 段的核数不同），用 `Block Dim` 会
正好差 2 倍。

采集里没有计数器不算错误：频率与全部派生字段一律为 `null`，UI 显示不可用。**绝不用
假设频率替代**，那会静默缩放整套指标。DS3.2 实测两个来源一致为 1850 MHz，spread
0.18%，无降频。

### MoE 专家计数（Step 2 产出，供 stage 2 使用）

MoE 模型的 `model_manifest.json` 会带三项 fact，各自带 `source_ref` 指向配置源码行：

| fact | DS3.2 实测 | 用途 |
|---|---|---|
| `n_routed_experts` | 256 | 路由专家总数 |
| `n_shared_experts` | 1 | 共享专家数；**不被 EP 分片**，每个 rank 都有副本 |
| `num_experts_per_tok` | 8 | top-k 路由宽度 |

这三项是**声明值**，来自模型源码 AST，不是从 kernel shape 推断的。**绝不从
`GroupedMatmul` 的权重 shape 反推专家总数** —— 那个首维只是本 rank 的分片
（DS3.2 上是 16），当成总数会把模型规模少报一个 EP 倍数。

专家清单（`<model-id>_expert_inventory.json`）属于下游产物，不在本 Skill 生成。本 Skill 只负责把
上面三项声明值连同 source_ref 准确提取出来，不读取下游 Skill 的实现说明。

**可选**：

```bash
python scripts/segment_layers.py -r outputs/raw_ops.json -o outputs/op_segments.json
```

为 Step 2 生成 layer 边界**候选**（基于最长重复子段）。AI 可作为定位参考，最终边界以源码语义为准。

**参考**：`references/kernel_data_guide.md`

---

### Step 2: 拆解模型结构

按 `references/structure_analysis_guide.md` §D.1 执行：

1. 选择代表性 step 与 decoder layer 实例
2. 阅读模型源码，提取模块层级和稳定函数边界
3. 在 op 序列中定位 decoder layer 边界（可参考 `op_segments.json`）
4. 逐层映射 op 到源码模块或函数语义
5. 输出 `analysis_config.json`
6. 运行 enrich：

```bash
python scripts/analyze_kernels.py --enrich \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json
```

字段规范、节点来源规则、命名规则、边界规则、**显式数据流边的写法**等**全部细节**见 `references/structure_analysis_guide.md`。SKILL.md 不再重述以避免分歧。

`shape_semantic` 是可选注解，不进入正式门禁：它是叠加在 profiler 维度上的解释，缺失并不说明拆解错误。

---

### Step 3: 校验、评分并迭代拆解

按 `references/structure_analysis_guide.md` §D.2 执行：

统一入口输出**单一合法 JSON**（不要再用 `>>` 拼接多个 JSON 文档到 `issues.json`）：

```bash
python scripts/run_validation.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir models/<your_model> \
  -o outputs/validation_report.json
```

- 先运行确定性预终态校验；未通过时不得准备完整十一项批判，也不得评分
- 中间修正只读取当前 `revision_request.json` 的白名单并运行确定性校验和独立定向批判；定向报告使用独立 schema/文件名，不能产生 `passed_at_cap`，不能交给 `score_breakdown.py`
- `ModuleList` 静态整数下标保留调用身份（如 `[0]` ↔ `name_0`）；折叠 `name` 可表示共享模板，动态下标不猜索引。首个、代表和末尾 invocation 都必须参与模板兼容性批判
- 候选哈希未变化时不重复 targeted critique；targeted passed 与当前同 ID 确定性 error 冲突时，由 `TC_DETERMINISTIC_CONFLICT` 拒绝报告
- 候选通过全部预终态门禁后才准备最终 `critique_request.json`；正常成功路径只运行一次完整十一项批判
- 最终批判必须使用新窗口或 `fork_turns=none`；旧候选、旧批判、旧聊天记录和 UI/报告产物不得进入上下文
- 最终报告除既有正式输入外，还必须绑定实际投喂的 `raw_ops.compact.json`、`source_snippets.json`
  和最终 `context_manifest.json`；任一 SHA256 漂移都会使完整批判失效
- 最终批判发现阻断错误时进入修正阶段；修正后先过确定性/定向门禁，再对当前文件哈希重做完整十一项，旧报告不得复用
- 默认最多 4 次语义修正并启用 `stall-limit=2`；连续两轮定义内阻断计数没有减少即 `blocked_no_progress`，第 4 次仍失败即 `blocked_max_revisions`
- 初始候选失败只建立基线，不占用四次语义修正额度；阻断终态写入 `iteration_history.json`，同一 run 后续重入直接停止
- 完整量表、硬性否决项和防刷分规则见 `references/breakdown_scoring.md`
- 单独调试某一维度时可直接运行 `check_structure.py` / `check_dataflow.py` / `check_op_coverage.py`（各自 `--json` 输出单一 JSON，不要 `>>` 追加）
- `validate_shapes.py` 与 `run_validation.py --with-shapes` 仅供排查，不属于正式流程
- `check_manifest_trace.py`（MT1）默认只作 `info`：一次采集可能只覆盖单个 step 或单个 rank，trace 是辅助证据，不能反驳源码读出的结构；确需阻断时显式传 `--fail-on-trace-mismatch`

---

### Step 4: 生成报告

```bash
python scripts/generate_report.py \
  -r outputs/raw_ops_details.json \
  -c outputs/analysis_config.json \
  --validation-report outputs/validation_report.json \
  -o outputs/{prefix}_report.md \
  --html -d 3
```

> 正式流程必须同时满足 `validation_report.status=passed` 和 `breakdown_score.passed_at_cap=true`（后者已包含批判无阻断问题、quality_rate 达标与全部 hard gates 通过）。`run_breakdown.py` 已执行这些门禁。`--allow-warnings` 只用于探索排查，不能通过正式评分门禁。

| 输出 | 说明 |
|---|---|
| `{prefix}_report.md` | Markdown 分析报告 |
| `{prefix}_report.html` | HTML 分析报告（默认产出） |

---

### Step 5: 计算性能指标

```bash
python scripts/compute_metrics.py \
  -r outputs/raw_ops_details.json \
  -c outputs/analysis_config.json \
  -o outputs/metrics_report.md \
  --findings-out outputs/metrics_findings.json \
  -d 3
```

**四维基础指标**：

| 指标 | 定义 | 含义 |
|------|------|------|
| `wall_ms` | 最后 kernel 结束 - 首个 kernel 开始 | 实际墙上时钟耗时（含间隙） |
| `busy_union_ms` | 合并后的设备忙碌时间 | 设备实际利用率（去重叠） |
| `kernel_sum_ms` | 所有 kernel 时长的算术和 | 总计算量（忽略重叠） |
| `total_cost_ms` | Σ(duration + wait) | 完整成本（含等待） |

**衍生指标**：`并行度 = kernel_sum_ms / wall_ms`、`bubble_ms = wall_ms - busy_union_ms`、`占比% = wall_ms / step_wall × 100`。

**诊断规则**：

| 条件 | 阈值 | 诊断结论 |
|------|------|----------|
| kernel_sum > wall | > 1.5× | 高流并行度（多流重叠执行） |
| kernel_sum > wall | > 1.2× | 中等流并行 |
| wall > busy_union | > 1.5× | 存在间隙气泡 |
| total_cost > kernel_sum | > 1.3× | 等待时间显著，检查 wait-anchor 热点 |
| busy_union / wall | 80%~95% | 利用率良好 |
| busy_union / wall | < 80% | 利用率偏低 |
| busy_union ≈ wall ≈ kernel_sum | 偏差 < 10% | 干净顺序执行 |

**适用范围**：decoder layer 及子节点、stages、runtime_auxiliary 及子节点。

**诊断建议（咨询性质）**：

`--findings-out` 输出 `metrics_findings.json`，把上表的诊断结论结构化为 `findings[{code, severity, metrics, text, advice_l1, next_data, not_applicable}]`，并按 `references/diagnosis_advice.md` 挂上「下一步该看什么数据」的建议。`metrics_report.md` 末尾同时生成按 `code` 聚类的建议段落。

- `code` 取有限枚举：`STREAM_PARALLEL_HIGH` / `STREAM_PARALLEL_MID` / `GAP_BUBBLE` / `WAIT_DOMINANT` / `UTIL_GOOD` / `UTIL_LOW` / `CLEAN_SEQUENTIAL` / `NORMAL` / `NO_DATA`。
- **建议不进任何门禁**：不参与 `validation_report`、`breakdown_score`、`hard_gates`，不影响上文的两个停止条件，不参与迭代循环。文档中 `advisory_only: true` 是契约的一部分，下游读到该文件必须视其为咨询信息。
- 建议只回答「下一步看什么数据」，**不断言根因**；指标本身不足以证明根因。
- `metric_scope == "aggregate"` 的节点（多 invocation 合并）其 gap/利用率/占比只描述该组总体，**不得外推到单实例**；此类建议自动带 `[聚合口径]` 前缀。
- 建议正文的唯一来源是 `references/diagnosis_advice.md`，改建议只改该文档、不改代码；该文档缺失时静默降级为「无建议」，不影响指标产出。

---

## 输出文件

| 文件 | 说明 |
|------|------|
| `raw_ops.json` | 单 Step kernel 概要（脚本用） |
| `raw_ops_details.json` | 单 Step kernel 详情（Step 4/5 用） |
| `raw_ops.compact.json` | Step 2 投喂 AI 的精简视图 |
| `source_index.json` / `source_scan_receipt.json` | 确定性源码索引、整体 bundle hash 与首次完整扫描收据 |
| `evidence_extraction_receipt.json` | raw ops/dataflow 的输入、提取器和产物 SHA256，用于同目录重入复用 |
| `device_freq.json` | Step 4b AI Core 实测频率与交叉验证；下游所有 cycle 派生指标的分母 |
| `model_manifest.json` | Step 2 架构真值；MoE 模型含 `n_routed_experts` / `n_shared_experts` / `num_experts_per_tok` 三项 fact（各带 source_ref）|
| `dataflow_source.json` | Step 5 从 `forward()` 提取的数据流真值；拆解 LLM 与批判 LLM 都必须引用其边 ID |
| `op_segments.json`（可选） | layer 边界候选 |
| `analysis_config.json` | 拆解配置（Mode A 终版）|
| `model_structure.json` | 仅结构（Mode B）|
| `contexts/<stage>/context_manifest.json` | 每个 LLM 阶段的输入白名单；白名单外产物禁止读取 |
| `targeted_critique_request.json` / `targeted_critique_report.json` / `targeted_critique_validation.json` | 中间修改阶段的定向批判；独立 schema，不参与评分 |
| `diagnostic_request.json` / `diagnostic_patch.json` / `diagnostic_patch_validation.json` | 普通修正无法覆盖时的受控诊断；绑定当前请求与基础产物哈希 |
| `analysis_config.diagnostic.json` / `model_manifest.hypothesis.json` / `diagnostic_application.json` | 确定性应用器产生的派生候选、manifest 假设和应用收据 |
| `critique_request.json` / `critique_report.json` | 最终十一项独立批判；只在全部预终态门禁通过后生成并绑定当前 SHA256 |
| `critique_validation.json` | 步骤 8 对批判证据的确定性复核（哈希绑定、定位符真实性、`clears_candidate`） |
| `validation_report.json` | Step 9 统一校验结果（单一 JSON，`status`/`error_count`/`checks`/`issues`）|
| `breakdown_score.json` | 步骤 9 评分：`quality_rate` / `evidence_cap` / `final_score` 三值分列、分项结果、硬性否决项与修正动作 |
| `iteration_history.json` | 修正轮次、六类阻断计数及是否有定义内进展 |
| `revision_request.json` | 当前修正白名单：只含当前候选、normalized issues、源码函数片段和 raw op 切片 |
| `iterations/` | 仅供审计的历史快照；禁止出现在任何当前 LLM 请求 `inputs` 中 |
| `{prefix}_report.md` / `.html` | 分析报告 |
| `metrics_report.md` | 性能指标分析报告（含按 code 聚类的诊断建议段落） |
| `metrics_findings.json` | 结构化诊断 + L1 建议，`advisory_only: true`；**不进任何门禁** |

---

## 参考资源

| 文件 | 何时查阅 |
|------|----------|
| `references/structure_analysis_guide.md` | Step 2 拆解 + Step 3 Review 全部规则细节 |
| `references/kernel_data_guide.md` | Step 1 — `kernel_details.csv` 字段说明 |
| `references/mode_b_branches.md` | Mode B 多分支表达约定 |
| `references/mode_c_delegate.md` | Mode C 委托 `cann-npu-perfanalysis` 模板 |
| `references/diagnosis_advice.md` | 诊断码 → L1 建议对照表；建议正文的唯一来源，咨询性质不进门禁 |
| `scripts/extract_model_manifest.py` | Step 2 架构真值提取 → `model_manifest.json`（取 modeling 实际 import 的 config 类；可达时以 checkpoint `config.json` 覆盖默认参数，不可达则降级为 `low` 并记 gap） |
| `scripts/validate_architecture.py` | Step 3 全局架构校验（层号完整/互斥、Dense/MoE、MTP、partial trace）；manifest 为低置信度时 A1/A4 降为 warning，避免门禁强制执行错误层数 |
| `scripts/check_manifest_trace.py` | manifest 层数 × trace per-layer kernel 数交叉校验（MT1），并反推 trace 支持的层数 |
| `scripts/analyze_kernels.py` | Step 4 提取与 enrich |
| `scripts/device_freq.py` | Step 4b AI Core 实测频率 → `device_freq.json`（trace 声明值 × 逐 kernel 反推值交叉验证）|
| `scripts/extract_dataflow.py` | **Step 5 数据流真值提取**：AST 解析 `forward()` 得到调用顺序、残差汇合（含 fused add-norm 与 `+=`）、并行 fork、config-gated 变体；data-dependent 分支记为 `unsupported` 而不猜测 |
| `scripts/check_dataflow.py` | **D1-D10 校验**：配置声明的边必须与源码一致，并在源码证明跨顶层 owner 的激活依赖时要求显式 `dataflow.edges`；无源码或无法唯一匹配 owner 时不出结论 |
| `scripts/detect_trace_scope.py` | 可选：trace scope / 并行归属检测。`trace_scope` 已非必填字段，仅在需要标注采集范围时使用 |
| `scripts/segment_layers.py` | layer 边界候选 |
| `references/ai_mapping_protocol.md` | **Step 6 AI 映射规程 + 提示词模板（全 op 归属，禁止 unmapped 冒充）** |
| `references/critique_protocol.md` | **步骤 7 独立批判协议：角色边界、十一项强制检查、证据规则、哈希绑定** |
| `references/breakdown_scoring.md` | **步骤 9 分证据上限评分、硬性否决项、迭代与停止规则** |
| `scripts/map_trace_instances.py` | Step 6 观测 invocation → `trace_instances` 精确映射 |
| `scripts/check_structure.py` | 树结构良构性（v1/v2） |
| `scripts/validate_shapes.py` | 可选排查：shape_semantic 一致性。**不在正式门禁内**，需 `run_validation.py --with-shapes` 才运行 |
| `scripts/check_op_coverage.py` | 精确 op 覆盖（union，非数量外推） |
| `scripts/check_sublayers.py` | 代表结构树子模块一致性（父=子 union、无重叠、主节点有真实 op、模板⊆代表实例） |
| `scripts/extract_source_index.py` | 单次完整源码扫描，生成确定性 `source_index.json` 与 bundle hash |
| `scripts/prepare_revision_context.py` | 生成当前修正上下文白名单、issue 源码函数片段和 raw op 切片 |
| `scripts/prepare_diagnostic_context.py` / `validate_diagnostic_patch.py` / `apply_diagnostic_patch.py` | 非候选/证据不足错误的通用受控诊断、权限校验和派生补丁应用 |
| `scripts/prepare_targeted_critique.py` / `validate_targeted_critique.py` | 中间修改阶段独立定向批判；永不进入评分 |
| `scripts/prepare_critique.py` / `validate_critique.py` | 生成最终十一项干净上下文请求，并复核候选/源码索引/证据哈希 |
| `scripts/run_breakdown.py` | 驱动单次扫描、预终态门禁、定向批判和最终批判；支持 `awaiting_targeted_critique` / `awaiting_final_critique` / 新阻断状态 |
| `scripts/run_validation.py` | Step 9 统一校验入口，输出单一 JSON |
| `scripts/score_breakdown.py` | 步骤 9 确定性评分入口，输出 breakdown_score.json（三值分列 + critique gates） |
| `scripts/migrate_config.py` | v1 → v2 迁移（标记 `legacy_unverified`） |
| `scripts/regression_check.py` | 结构回归 + 对 manifest 的语义架构回归（MA1-MA3） |
| `scripts/generate_report.py` | Step 11 报告生成（v2 架构/执行分区，MTP 标签，validation gate） |
| `scripts/compute_metrics.py` | Step 11 指标计算 + 结构化诊断/建议（`--findings-out`） |
| `schemas/*.schema.json` | 正式接口 schema，以及 source index、targeted critique、controlled diagnostic patch schema |
| `adapters/*.py` | 模型族架构提取差异封装（deepseek/gemma/qwen/longcat） |
