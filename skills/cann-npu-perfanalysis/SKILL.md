---
name: cann-npu-perfanalysis
description: >
  分析 Ascend NPU profiling 数据，覆盖 8 个性能维度（迭代效率、算子热点、硬件利用率/MFU、
  通信效率、设备空泡、等待锚点、层级结构、多卡均衡），并给出 Host/Device Bound 总判定、
  Device 内 compute/memory/communication/latency bound 分类、算子级 compute/memory bound、
  wait pollution / total_cost 双排名、AICPU 暴露程度，输出有主次逻辑的诊断理由与优化建议，
  生成 Markdown + HTML 双格式报告。
  触发场景：NPU 性能分析、step time 分析、算子热点、通信瓶颈、MFU 计算、
  Host Dispatch 瓶颈、host bound、device bound、compute bound、memory bound、communication bound、
  Free Time 高、wait anchor、device bubble、kernel gap、wait pollution、total cost、
  cube utilization、AICPU 暴露、AICPU masked、多卡负载不均、快慢卡、AllReduce 开销、
  overlap 比例、ASCEND_PROFILER_OUTPUT、kernel_details.csv、op_statistic.csv、
  step_trace_time.csv、communication.json、profiling report。
---

# npu-perf-analysis

分析 Ascend NPU Profiler 输出，覆盖 8 个性能维度，输出 Host/Device Bound 判定、瓶颈理由、优化建议与双格式报告（Markdown + HTML）。

---

## 输出组织原则（主次逻辑）

报告必须按以下逻辑组织，不得把所有指标平铺：

1. **先给结论**：执行摘要必须先回答“主要瓶颈是什么、优先级是多少、为什么”。
2. **再给 Bound 总判定**：明确输出 `HOST_BOUND` / `DEVICE_COMPUTE_BOUND` / `DEVICE_MEMORY_BOUND` / `DEVICE_COMMUNICATION_BOUND` / `DEVICE_LATENCY_BOUND` / `MIXED_BOUND` / `INSUFFICIENT_EVIDENCE`。
3. **再给证据链**：每个诊断必须包含 `事实指标 → 阈值对比 → 判定理由 → 置信度`。
4. **最后给行动建议**：建议必须按 P0-P3 排序，且说明“针对哪个瓶颈、改什么、预期影响哪个指标”。
5. **避免指标堆砌**：详细表格放在各维度章节；摘要只放 Top 3 发现和主因/次因。

---

## 参考文件加载指引

| 参考文件 | 何时加载 |
|---|---|
| `references/data-schema.md` | Phase 0 开始时，了解各 CSV/JSON 字段含义 |
| `references/metrics-formulas.md` | Phase 1-2 计算指标时 |
| `references/thresholds.md` | Phase 1-3 判定瓶颈优先级时 |
| `references/hardware-specs.md` | Phase 2B 计算 MFU 时 |

---

## 数据层次结构

```
ASCEND_PROFILER_OUTPUT/
├── step_trace_time.csv   → Phase 1（迭代效率）+ Phase 2C（通信概况）
├── op_statistic.csv      → Phase 2A（算子热点）
├── kernel_details.csv    → Phase 2B/2D/2E/2F（MFU / 空泡 / 等待锚点 / 层级结构）
├── communication.json    → Phase 2C（通信带宽）
├── communication_matrix.json → Phase 2H（多卡均衡，通常为空）
├── trace_view.json       → Phase 2G（Host evidence / wait pollution，可选）
├── operator_details.csv  → Phase 2G（Host-Device 算子归因，可选）
└── OPPROF_*/             → Phase 2I（msprof op PMU 算子级 bound，可选）
```

---

## Phase 0：数据预检（Data Inventory & Validation）

**目标**：建立本次分析的能力矩阵，后续各维度按矩阵决定执行或跳过。

**步骤：**

1. **定位 ASCEND_PROFILER_OUTPUT**
   - 若用户给定路径直接包含 `ASCEND_PROFILER_OUTPUT/`，使用该路径。
   - 否则，递归扫描子目录（最多 2 层），找到第一个 `ASCEND_PROFILER_OUTPUT/` 目录。
   - 在报告中记录"实际数据路径"（`actual_path`）。

2. **文件清点**：列出存在的文件，建立能力矩阵：

   | 文件 | 缺失时的降级策略 |
   |---|---|
   | `step_trace_time.csv` | 跳过 Phase 1；无法判定迭代效率 |
   | `op_statistic.csv` | 跳过 Phase 2A；无法统计算子热点 |
   | `kernel_details.csv` | 跳过 Phase 2B/2D/2E/2F |
   | `communication.json` | Phase 2C 仅用 step_trace_time 的 overlap 列 |
   | `communication_matrix.json` | 跳过 Phase 2H 带宽矩阵部分 |
   | `trace_view.json` | Phase 2G 仅做指标级 Host/Device 判定，无法做 host event overlap 软归因 |
   | `operator_details.csv` | Phase 2G 不输出 PyTorch 算子 Host/Device 归因 |
   | `OPPROF_*/*.csv` | Phase 2I 仅用 `kernel_details.csv` V2 做算子级 bound，无法用 PMU 细分 GM/UB/Bank Conflict |

3. **Schema 版本检测**（`kernel_details.csv`）：
   - 读取表头，若存在 `cube_utilization(%)` 列 → **V2 Schema**；否则 → **V1 Schema**。
   - V1 Schema 下 MFU 改用 `aic_cube_fops / Duration_us / 1e6` 估算，置信度低，报告中须注明。

4. **设备与步数统计**（`step_trace_time.csv`）：
   - 统计 `Device_id` 的唯一值 → 单卡 / 多卡模式。
   - 统计 `Step` 的唯一值 → 步数列表。

5. **芯片型号检测**（优先级从高到低）：
   - 用户在问题中直接指定 → 使用用户值。
   - `profiler_metadata.json` 或 `profiler_info_N.json` 中记录的设备信息 → 解析。
   - `kernel_details.csv` 的 `Block Dim` 最大值（910B3 通常为 64，910B4 通常为 32）→ 推断。
   - 以上均不可用 → 默认 **Ascend 910B3（294.91 TFLOPs/s BF16）**，并在报告中标注。

---

## Phase 1：迭代效率（Dimension 1）

**数据源**：`step_trace_time.csv`

**计算以下每步指标**（公式见 `references/metrics-formulas.md`）：

```
computing_ratio      = Computing / Stage
comm_not_overlap_ratio = Communication(Not Overlapped) / Stage
free_ratio           = Free / Stage
overlap_ratio        = Overlapped / Communication   （若 Communication=0 则跳过）
```

**预热步检测规则**（依次检查）：
1. 若第一步的 `comm_not_overlap_ratio` 比后续步骤均值高出 **> 20 个百分点** → 标注为"疑似预热步，不参与均值统计"。
2. 若第一步的 `free_ratio` 或 `computing_ratio` 与后续步骤均值偏差 **> 20 个百分点** → 同上标注。
3. 仅有 1 步时 → 注明"单步采集，无法进行预热步判断"。

**正常步均值**：排除预热步后，计算各指标的算术均值。

**瓶颈判定**（阈值见 `references/thresholds.md`）：

| 指标 | 警告 | 严重 | 优先级规则 |
|---|---|---|---|
| free_ratio | > 10% | > 10% | 超过严重阈值 2 倍 → P0；超过严重阈值 → P1；超过警告线 → P3 |
| comm_not_overlap_ratio | > 15% | > 30% | 超过严重阈值 2 倍 → P0；超过 → P1；超过警告线 → P2 |
| overlap_ratio | < 50% 良好；< 20% 差 | — | < 20% 且 CommNO > 15% → P2 |

**多卡模式**：额外计算每设备的 Stage 均值和 `variance_ratio = (max_Stage - min_Stage) / avg_Stage`。

---

## Phase 2：深度分析（Dimensions 2–8 + Bound 扩展）

### 2A. 算子热点（Dimension 2）

**数据源**：`op_statistic.csv`

1. 按 `Total Time(us)` 降序排列，取 Top-10。
2. 热点标注：`Ratio(%) > 20` → `hotspot`；`> 10%` → `watch`；其余 → `normal`。
3. 若出现 MoE 专属算子（MoeGatingTopK / GroupedMatmul / DispatchFFNCombine / MoeInitRouting 系列），标注为 `moe_normal`（MoE 架构正常开销，不是瓶颈）。
4. 若出现 `Core Type = AI_CPU`，标注为 `aicpu`，并在报告中警告 AICPU 暴露风险。
5. 按 `Core Type` 分组，计算各组的 Total Time 占比。
6. 若 `kernel_details.csv` 存在，同时生成两类热点视图：
   - **duration_hotspots**：按 `Duration_us` 聚合，代表真实设备执行耗时。
   - **total_cost_hotspots**：按 `Duration_us + Wait_Time_us` 聚合，代表时间线可见总成本。
   - 若某算子 `total_cost` 排名高但 `wait_ratio > 0.95` 或 wait 与通信窗口重叠，标记 `WAIT_ANCHOR_FALSE_HOTSPOT` 或 `WAIT_POLLUTION_RISK`，不得作为真实计算热点。

**重要背景说明**：在 `free_ratio` 极高（> 50%）的情况下，op_statistic 的 `Total Time` 仅代表设备有效工作期间的算子耗时，不是 Stage 总时间的占比。高 `Ratio(%)` 不等于该算子是瓶颈，首要问题仍是减少 Free Time。

### 2B. 硬件利用率 / MFU（Dimension 3）

**数据源**：`kernel_details.csv`

**V2 Schema**（存在 `cube_utilization(%)` 列）：
- 对 MatMul / GroupedMatmul / FusedInferAttentionScore kernel，解析 `Input Shapes`：
  - MatMul：`M,K;K,N` 或 `M,K;N,K`（转置，FLOPs 相同）→ `FLOPs = 2 × M × K × N`
  - FIA：`FLOPs = 2 × q_batch × q_heads × q_seq × kv_seq × (q_dim + kv_dim)` × 0.5（因果掩码）
- `MFU = (FLOPs / Duration_us / 1e6) / Peak_TFLOPs_s`（Peak 见 `references/hardware-specs.md`）
- 直接读取 `cube_utilization(%)` 作为 Cube 流水线内部效率。
- `aic_mte2_ratio > 0.8` → 该 kernel Memory Bound（权重加载是瓶颈）。
- `aic_mac_ratio > 0.8` → 该 kernel Compute Bound（Cube 饱和）。
- `aic_fixpipe_ratio > 0.3` → 该 kernel FixPipe Bound。
- `aiv_scalar_ratio > 0.8` → 该 kernel Scalar / Latency Bound。
- `aiv_mte2_ratio > 0.5` 或 `aiv_mte3_ratio > 0.5` → 该 Vector kernel Memory Bound 风险。

**V1 Schema**：
- `Achieved_TFLOPs_s = aic_cube_fops / Duration_us / 1e6`，`MFU = Achieved_TFLOPs_s / Peak`，置信度低，须在报告中注明。

**特殊情况**：Decode 阶段 M=1 的矩阵乘法，MFU 天然极低（< 5%），**不标注为异常**。

### 2C. 通信效率（Dimension 4）

**数据源**：`communication.json` + `step_trace_time.csv`

1. 从 `communication.json` 读取 `collective` 下各操作的 `Elapse Time`、`Transit Size`、`Bandwidth`。
2. 按操作名前缀归类：`HcomAllReduce_*` → AllReduce，`HcomAllGather_*` → AllGather，`HcomReduceScatter_*` → ReduceScatter。
3. 若所有传输介质的 `Bandwidth(GB/s)` 均为 0 → **单 Rank 采集**，仅报告 Elapse Time，注明"无法获取跨 Rank 带宽"。
4. 跨引用 `step_trace_time.csv` 的 `overlap_ratio`（Phase 1 已算）。
5. `Communication = 0`（step_trace_time）且无通信数据 → 跳过本维度，注明"无通信操作"。

### 2D. 设备空泡（Dimension 5）

**数据源**：`kernel_details.csv`

对每步（Step）：
1. 收集该步所有 kernel 的时间区间 `[Start_Time_us, Start_Time_us + Duration_us]`。
2. 合并重叠区间 → `busy_union`。
3. 步窗口 = 从该步第一个 kernel 的 Start 到 `Stage_us` 结束。
4. 计算：`prelaunch_gap`（步窗口开始到第一个 kernel）、`internal_bubble_total`（区间间隙之和）、`underfeed_ratio = (prelaunch_gap + internal_bubble_total) / stage_us`。
5. 阈值：`underfeed_ratio > 20%` → 严重（见 `references/thresholds.md`）。

**注意**：设备空泡与 step_trace_time 的 `Free Time` 粒度不同，不要混淆（Free Time 是 Host 调度视角，空泡是 Device 时间轴视角）。

### 2E. 等待锚点假热点（Dimension 6）

**数据源**：`kernel_details.csv`

1. 对每个 kernel 计算：`wait_ratio = Wait_Time_us / (Duration_us + Wait_Time_us)`。
2. 判定等待锚点：`wait_ratio > 0.95` **且** `Duration_us < 10.0`。
3. 按 `total_cost = Duration_us + Wait_Time_us` 降序列出所有等待锚点。
4. 对每个等待锚点，找出同 Stream 内时间上紧邻的**前一个 kernel** 和**后一个 kernel**，作为上下文信息。

### 2F. 层级结构（Dimension 7）

**数据源**：`kernel_details.csv`

1. **MoE 检测**：若出现 `MoeGatingTopK` / `MoeGatingTopKSoftmax` / `MoeComputeExpertTokens` / `DispatchFFNCombine` / `MoeInitRoutingV3` / `GroupedMatmul` 中的两个以上 → 判定为 MoE 模型。
2. **层数估算**：`FusedInferAttentionScore` 的 count ÷ 步数内出现频率 → 估算 Transformer 层数。
3. **推理阶段**：FIA Input Shapes 中 Q 维度 seq_len=1 → Decode 阶段；seq_len > 1 → Prefill 阶段。
4. `kernel_details.csv` 行数 < 500 → 跳过层级分析，注明"数据过稀疏"。

### 2G. Host/Device Bound 总判定（新增核心能力）

**数据源**：`step_trace_time.csv` + `kernel_details.csv` + 可选 `trace_view.json` / `operator_details.csv`

按以下顺序判定整体主瓶颈：

1. **Host Bound 候选**：
   - `free_ratio > 10%` 或 `underfeed_ratio > 20%`。
   - 若 `trace_view.json` 存在，扫描 bubble 窗口内 host events：
     - sync/H2D marker 覆盖率 ≥ 20% → `possible_sync_or_h2d`
     - comm marker 覆盖率 ≥ 20% → `possible_comm_wait`
     - host event 可见但无 sync/comm 主导 → `possible_host_launch_lag`
     - host event 覆盖率 < 5% 且 bubble 高 → `possible_untraced_host_blocking`
   - 输出 `HOST_BOUND` 或 `HOST_ORIGINATED_RISK`，并说明证据是否充足。

2. **Device Bound 候选**：
   - `free_ratio <= 10%` 且 `underfeed_ratio <= 20%`，但 `computing_ratio`、kernel busy 或通信未重叠占比高。
   - 继续细分：
     - `DEVICE_COMPUTE_BOUND`：MFU / cube / vector 利用率高，或 `aic_mac_ratio > 0.8`。
     - `DEVICE_MEMORY_BOUND`：`aic_mte2_ratio > 0.8`，或 Vector MTE / GM-UB 带宽证据占主导。
     - `DEVICE_COMMUNICATION_BOUND`：`comm_not_overlap_ratio > 30%` 或通信 wait / bandwidth 异常。
     - `DEVICE_LATENCY_BOUND`：compute 与 memory 利用率都低，小 kernel 多、scalar 占比高、launch/同步碎片明显。

3. **Mixed / Insufficient Evidence**：
   - Host 与 Device 证据同时超过阈值 → `MIXED_BOUND`，按贡献排序写主因/次因。
   - 关键文件缺失或证据冲突 → `INSUFFICIENT_EVIDENCE`，必须说明缺哪些数据，不得强行归因。

### 2H. 多卡均衡（Dimension 8）

**数据源**：`step_trace_time.csv` + 可选 `communication_matrix.json`

若存在多个 `Device_id`，计算 per-device Stage / Computing / Free / CommNO 均值和 `variance_ratio`。
若仅单设备数据，跳过并注明"仅单卡数据"。

### 2I. 算子级 Compute/Memory Bound（新增核心能力）

**数据源**：优先 `OPPROF_*/ArithmeticUtilization.csv` + `Memory.csv` + `ResourceConflictRatio.csv`，否则退化为 `kernel_details.csv` V2。

1. **PMU 数据存在时**：
   - 计算 `AI = (aic_cube_fops + aiv_vector_fops) / (GM_to_UB_datas + UB_to_GM_datas)`。
   - 若 AI 低于硬件平衡点或经验阈值（无硬件带宽时用 50 FLOPs/Byte）→ `OP_MEMORY_BOUND`。
   - 若 AI 高于硬件平衡点且 Cube/Vector 利用率高 → `OP_COMPUTE_BOUND`。
   - 若 `GM_to_UB_bw_usage_rate < 30%` 或 `UB_to_GM_bw_usage_rate < 30%`，标记低带宽利用率。
   - 若 `aiv_vec_bankgroup_cflt_ratio > 0.1` 或 `aiv_vec_bank_cflt_ratio > 0.1`，标记 `BANK_CONFLICT_RISK`。

2. **仅 kernel_details V2 时**：
   - `aic_mte2_ratio > 0.8` → `OP_MEMORY_BOUND`
   - `aic_mac_ratio > 0.8` → `OP_COMPUTE_BOUND`
   - `aiv_scalar_ratio > 0.8` → `OP_SCALAR_BOUND`
   - `aic_fixpipe_ratio > 0.3` → `OP_FIXPIPE_BOUND`

3. **仅 op_statistic 时**：
   - 只输出热点，不输出 compute/memory bound；标注"证据不足"。

---

## Phase 3：瓶颈诊断（Bottleneck Synthesis）

综合 Phase 1-2 的所有发现，先输出整体 Bound 判定，再按优先级输出瓶颈列表：

| 优先级 | 判定条件 |
|---|---|
| **P0** | 任一指标超过其严重阈值 2 倍 |
| **P1** | 任一指标超过严重阈值但 < 2 倍 |
| **P2** | 多个指标处于警告范围；或单个次要指标略超严重阈值 |
| **P3** | 单个指标超过警告线，其余正常 |

- 对每个瓶颈，写明：标签（如 `HOST_DISPATCH_BOTTLENECK`）、指标数值、与阈值的对比。
- 对每个瓶颈，必须写明：**诊断理由**（为什么这个指标说明该瓶颈）和**反证/降级条件**（哪些数据缺失或冲突）。
- 预热步异常**不计入**正常步瓶颈（用括号单独说明）。
- 等待锚点的高 `total_cost` **不作为算子热点瓶颈**（须明确区分假热点）。
- 若 Host/Device Bound 与单项指标结论冲突，以证据链说明主因/次因，不得只给单标签。

---

## Phase 4：报告生成

Phase 4 分为三步，其中步骤 A 由 Agent 完成，步骤 B-C 由脚本完成。

### 步骤 A：生成 Markdown 报告（report.md）

按以下固定章节顺序输出（共 14 章），用 Write 工具写入 `report.md`：

```
一、分析上下文        — 路径、芯片、Schema、步数、设备数、文件清单、数据质量
二、执行摘要          — Top 3 发现、主因/次因、P0-P3 优先级
三、整体 Bound 判定   — Host/Device Bound、Device 子类、理由与置信度
四、维度 1：迭代效率  — 逐步时间拆分表格 + 瓶颈判定
五、维度 2：算子热点  — duration 热点 + total_cost 热点 + 核心类型分布
六、维度 3：硬件利用率/MFU — 代表性 kernel MFU + cube_utilization
七、算子级 Bound 分析 — compute/memory/scalar/fixpipe/bank conflict
八、维度 4：通信效率  — 集合通信类型 + 带宽数据 + wait pollution
九、维度 5：设备空泡  — underfeed_ratio + host evidence 来源分析
十、维度 6：等待锚点  — 假热点列表 + 前后 kernel 上下文
十一、维度 7：层级结构 — 模型类型 + 层数 + MoE 特征
十二、维度 8：多卡均衡 — per-device Stage 对比（或跳过说明）
十三、瓶颈诊断        — P0-P3 排列，含事实、理由、反证、置信度
十四、优化建议        — 按优先级，每条含具体措施 + 预期收益
```

被跳过的维度用一行说明原因（文件缺失 / 数据不足 / 单卡等）。

### 步骤 B：写出 analysis_data.json

将本次分析的所有计算结果整理为结构化 JSON，写入 `analysis_data.json`。JSON Schema 见下方。

**此步骤由 Agent 完成**：Agent 将 Phase 1-3 计算出的所有指标按 Schema 整理。

### 步骤 C：运行 HTML 生成器（脚本完成）

```bash
# 按 SKILL.md 内容里的规范标题定位（目录名可能与 Skill 标题不同），未找到匹配即显式失败
skill_md="$(grep -rl --include=SKILL.md '^# npu-perf-analysis$' . | head -1)"
[ -n "$skill_md" ] || { echo "未找到标题为 '# npu-perf-analysis' 的 SKILL.md" >&2; exit 1; }
generate_html="$(dirname "$skill_md")/references/generate_html.py"
[ -f "$generate_html" ] || { echo "未找到 HTML 生成器：$generate_html" >&2; exit 1; }
python3 "$generate_html" analysis_data.json report.html
```

HTML 生成器支持多种主题风格，参考 cann-perf-breakdown：

```bash
python3 references/generate_html.py analysis_data.json report.html --theme dracula
python3 references/generate_html.py analysis_data.json report.html --theme vscode-dark
python3 references/generate_html.py analysis_data.json report.html --theme github-light
python3 references/generate_html.py analysis_data.json report.html --theme solarized-light
```

可选主题：`dracula`（默认）、`vscode-dark`、`one-dark`、`github-light`、`solarized-light`。

若无法定位 SKILL.md 路径，也可直接用绝对路径：

```bash
python3 /path/to/npu-perf-analysis/references/generate_html.py analysis_data.json report.html
```

脚本读取 `analysis_data.json`，渲染带导航栏、进度条、严重度徽章、可折叠章节的单文件 HTML 报告，写入 `report.html`。

---

## analysis_data.json Schema

```json
{
  "meta": {
    "data_path": "用户输入的路径",
    "actual_path": "实际找到的 ASCEND_PROFILER_OUTPUT 路径",
    "chip": "Ascend 910B3",
    "peak_tflops": 294.91,
    "schema_version": "V2",
    "steps": [3, 4, 5],
    "steps_desc": "Step 3、4、5（Step 3 为预热步）",
    "devices": [0],
    "devices_desc": "Device_id=0（单设备）",
    "files_present": ["kernel_details.csv", "op_statistic.csv", "..."],
    "generated_at": "2026-05-07",
    "quality_notes": "数据质量说明..."
  },
  "iteration_efficiency": {
    "steps": [
      {
        "step": 3,
        "computing_us": 11841.0,
        "comm_no_us": 17543.0,
        "overlapped_us": 5.8,
        "communication_us": 17549.0,
        "free_us": 4642.0,
        "stage_us": 34027.0,
        "computing_ratio": 0.348,
        "comm_no_ratio": 0.516,
        "free_ratio": 0.136,
        "overlap_ratio": 0.00033,
        "is_warmup": true,
        "warmup_reason": "CommNO 占比 51.6%，比后续步骤（8-10%）高出 40+ 个百分点"
      }
    ],
    "warmup_steps": [3],
    "normal_steps": [4, 5],
    "avg": {
      "computing_ratio": 0.704,
      "comm_no_ratio": 0.087,
      "free_ratio": 0.209,
      "overlap_ratio": 0.004,
      "stage_us": 16839.5
    },
    "bottleneck": {
      "label": "HOST_DISPATCH_MILD",
      "priority": "P3",
      "evidence": "free_ratio=20.9%（正常步均值），超过警告线 10%，未超过严重阈值 10% 的 2 倍"
    }
  },
  "bound_classification": {
    "overall_bound": "HOST_BOUND",
    "device_bound_type": null,
    "primary_bottleneck": "Host Dispatch",
    "secondary_bottlenecks": ["WAIT_POLLUTION_RISK"],
    "priority": "P0",
    "confidence": "高",
    "facts": [
      "free_ratio=82.0%，超过严重阈值 10% 的 8.2 倍",
      "underfeed_ratio=73.0%，超过严重阈值 20%"
    ],
    "reasoning": "Stage 主要由 Free/underfeed 构成，设备没有持续被 AI Core/HCCL 喂满，因此主瓶颈是 Host 侧下发或同步等待，而不是单个 MatMul kernel 算力不足。",
    "counter_evidence": "未提供 trace_view.json，无法进一步区分 Python 调度、H2D 同步或未采样 Host 阻塞。",
    "host_evidence": {
      "available": false,
      "sync_or_h2d_overlap_ratio": null,
      "comm_marker_overlap_ratio": null,
      "host_visible_coverage_ratio": null,
      "soft_labels": ["possible_untraced_host_blocking"]
    }
  },
  "operator_hotspots": {
    "top_ops": [
      {
        "rank": 1,
        "name": "MatMul",
        "core_type": "AI_CORE",
        "count": 96,
        "total_us": 4674.0,
        "avg_us": 48.7,
        "max_us": 125.3,
        "ratio": 48.5,
        "flag": "hotspot"
      }
    ],
    "core_type_breakdown": {
      "AI_CORE": 48.5,
      "AI_VECTOR_CORE": 35.3,
      "MIX_AIC": 16.3,
      "AI_CPU": 0.0
    },
    "has_aicpu": false,
    "note": "可选背景说明文字"
  },
  "hardware_utilization": {
    "skipped": false,
    "skip_reason": null,
    "schema_version": "V2",
    "representative_kernels": [
      {
        "name": "MatMul",
        "input_shapes": "1,4096;4096,4096",
        "flops": 33554432.0,
        "duration_us": 48.7,
        "mfu": 0.023,
        "cube_utilization": 74.5,
        "memory_bound": false,
        "verdict": "✅ 正常（Decode M=1）"
      }
    ],
    "avg_cube_utilization": 74.5,
    "avg_mfu": 0.023,
    "note": "Decode 阶段 M=1，MFU 天然极低，不标注为异常。"
  },
  "operator_bound_analysis": {
    "skipped": false,
    "source": "kernel_details_v2",
    "summary": {
      "compute_bound_count": 12,
      "memory_bound_count": 4,
      "scalar_bound_count": 1,
      "fixpipe_bound_count": 0,
      "bank_conflict_count": 0
    },
    "top_operators": [
      {
        "name": "MatMul",
        "core_type": "AI_CORE",
        "duration_us": 48.7,
        "bound_type": "OP_COMPUTE_BOUND",
        "evidence": "aic_mac_ratio=0.84 > 0.8，Cube 单元占主导",
        "confidence": "中",
        "recommendation_hint": "优先检查 shape/batch 是否能提高 MFU；若 Decode M=1，不建议以提升 MFU 为主目标。"
      }
    ],
    "pmu_notes": "未发现 OPPROF_* msprof op 输出，未计算 GM/UB 带宽与 Bank Conflict。"
  },
  "communication_efficiency": {
    "skipped": false,
    "skip_reason": null,
    "overlap_ratio_avg": 0.004,
    "collectives": {
      "AllReduce": 32,
      "AllGather": 1,
      "ReduceScatter": 0,
      "Broadcast": 0
    },
    "bandwidth": {
      "RDMA": 0.0,
      "HCCS": 0.0,
      "PCIE": 0.0
    },
    "single_rank": true,
    "max_elapse_ms": 16.3,
    "note": "communication.json 中所有传输介质带宽数据为 0，判断为单 Rank 采集，无法获取跨 Rank 通信带宽。"
  },
  "device_bubbles": {
    "skipped": false,
    "skip_reason": null,
    "underfeed_ratio": 0.21,
    "prelaunch_gap_ms": 0.8,
    "internal_bubble_ms": 2.5,
    "note": "主要来源为 Host 下发间隙（prelaunch + inter-kernel gaps）。"
  },
  "wait_anchors": [
    {
      "name": "AivKernel",
      "duration_us": 6.0,
      "wait_us": 16293.0,
      "wait_ratio": 0.9996,
      "total_cost_us": 16299.0,
      "stream_id": "43",
      "prev_kernel": "HcomAllReduce_xxxxx",
      "next_kernel": "MatMul_xxxxx"
    }
  ],
  "layer_structure": {
    "skipped": false,
    "skip_reason": null,
    "model_type": "MoE",
    "num_layers": 32,
    "has_moe": true,
    "moe_ops_detected": ["MoeGatingTopKSoftmax", "MoeComputeExpertTokens", "GroupedMatmul"],
    "inference_phase": "Decode",
    "note": "32 层 MoE Transformer，Decode 阶段单 token 生成。"
  },
  "multi_card": {
    "skipped": true,
    "skip_reason": "仅有 Device_id=0 的单设备数据，无法进行多卡负载均衡分析",
    "devices": [0],
    "variance_ratio": null
  },
  "bottleneck_diagnosis": [
    {
      "priority": "P3",
      "label": "HOST_DISPATCH_MILD",
      "dimension": "迭代效率",
      "evidence": "free_ratio=20.9%（Step 4-5 均值），超过警告线 10%，未超过严重阈值 10% 的 2 倍",
      "reasoning": "Free Time 计入 Stage 且设备无计算/通信执行，说明设备侧等待 Host 下发或同步解除。",
      "counter_evidence": "无 trace_view.json，无法唯一定位 Python 调度、H2D 同步或外部阻塞。",
      "confidence": "中"
    }
  ],
  "recommendations": [
    {
      "priority": "P3",
      "title": "减少小算子下发次数",
      "action": "合并 Add、Mul、Cast 等高频小算子为融合算子，减少 Host-Device 往返",
      "benefit": "Free Time 从 21% 降至 <15%"
    }
  ],
  "not_recommended": [
    "MatMul 内核效率优化（Decode M=1 低 MFU 属正常）",
    "通信策略优化（CommNO=8.7% 在正常范围内）"
  ]
}
```

---

## NEVER 列表（禁止行为）

- **NEVER** 将 `step_trace_time.csv` 的 `Free Time` 与 kernel 级设备空泡混同——两者粒度、来源、修复方式均不同。
- **NEVER** 仅凭高 `Ratio(%)` 就判断某算子是性能瓶颈，必须先检查该 kernel 的 `wait_ratio`（可能是等待锚点假热点）。
- **NEVER** 仅凭 `op_statistic.csv` 判断算子 compute/memory bound；没有 `kernel_details.csv` V2 或 msprof op PMU 时只能说"热点"，不能说"compute bound/memory bound"。
- **NEVER** 把 Host Bound 说成确定根因（如 Python/GIL/H2D）而不给 host event 证据；证据不足时必须输出 soft label 和缺失数据。
- **NEVER** 忽略 `total_cost` 与 `duration` 的差异；total_cost 高且 wait 高时必须检查等待锚点和 wait pollution。
- **NEVER** 对 `Communication=0` 的数据集输出任何通信优化建议（如 AllReduce overlap、减少通信量）。
- **NEVER** 为 Decode 单 token（M=1）场景的低 MFU 标注异常或给出"提升 MFU"的建议。
- **NEVER** 将预热步（Step 1 或 CommNO 异常偏高步）的数据纳入正常步均值。
- **NEVER** 报告跨 Rank 带宽为 0 时不加说明——必须注明"单 Rank 采集，带宽数据不可用"。
- **NEVER** 对仅有单设备数据的场景进行多卡均衡分析。
- **NEVER** 仅报告一种粒度的指标——必须同时输出 step 级效率（step_trace_time）和 op 级热点（op_statistic）。
- **NEVER** 对 MoE 模型的 GroupedMatmul、MoeGatingTopK 等算子建议"减少计算量"——这是 MoE 架构的正常开销。

---

## 优雅降级（Graceful Degradation）

| 缺失场景 | 降级行为 |
|---|---|
| 无 `kernel_details.csv` | 跳过维度 3/5/6/7，仅凭 op_statistic 做算子热点 |
| V1 Schema | 低置信度 MFU（基于 aic_cube_fops），报告中注明 |
| 无 `communication.json` | Phase 2C 仅报告 step_trace_time 的 overlap_ratio |
| 无 `trace_view.json` | Host/Device Bound 仍可基于 Free/underfeed 判定，但 Host 根因只输出 soft label，置信度下降 |
| 无 `OPPROF_*` | 算子级 bound 退化为 `kernel_details.csv` V2；若也缺失 V2 字段，则只输出热点不输出 compute/memory bound |
| 单 Device_id | 跳过维度 8，注明"仅单卡数据" |
| 单步采集 | 注明"无法预热步判断和步间周期性分析" |
| FIA Input Shapes 为空 | 跳过 FIA MFU 计算，仅报告 cube_utilization |
| 所有带宽为 0 | 注明"单 Rank 采集"，仅报告 Elapse Time |
| 嵌套目录 | Phase 0 自动扫描，在 actual_path 中记录完整路径 |
| `kernel_details.csv` 行数 < 500 | 跳过维度 7（层级结构），注明"数据过稀疏" |

---

## 评测用例参考

评测用例集见 `eval/eval-cases.md`，包含 5 个标准场景：

| 用例 | 数据集 | 核心验证点 |
|---|---|---|
| 1 | gemma | 预热步识别（Step 3 CommNO=51.6%），MoE 特征，等待锚点 AivKernel |
| 2 | qwen7b | P0 Host Dispatch（free_ratio=82%），不推荐通信优化 |
| 3 | ds3.2 | 单设备声明（Device_id=3），预热步（Step 10 CommNO=68.7%），双瓶颈 |
| 4 | longcat | 嵌套目录自动发现，P0 通信瓶颈（74.1%），单 Rank 带宽声明 |
| 5 | gemma | 等待锚点专项（AivKernel wait_ratio=99.96%），假热点降级 |
