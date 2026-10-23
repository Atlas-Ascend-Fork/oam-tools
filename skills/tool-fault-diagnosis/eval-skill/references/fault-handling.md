# CANN 故障处理参考

> 本文档基于 CANN 8.5.0（商用版）/ CANN 9.0.0-beta.2（社区版）官方故障处理文档整理，用于日志评估阶段的故障定位与处理。
> 官方参考：[故障处理简介（商用版 8.5.0）](https://www.hiascend.com/document/detail/zh/canncommercial/850/maintenref/troubleshooting/troubleshooting_0001.html) / [AI Core Error 问题现象描述（商用版 8.5.0）](https://www.hiascend.com/document/detail/zh/canncommercial/850/maintenref/troubleshooting/troubleshooting_0002.html)

> 执行范围遵守 [处理流公共约定](fault-flows/common-flow.md#1-输入与证据保护)。下文现场采集、检测、修复和复跑步骤用于理解既有记录或提出有条件的计划，已有日志诊断不自动执行；缺少结果时记录影响并继续分析现有材料。
> 实时堆栈导出会向目标进程发送信号 35。执行 `asys collect -r=stacktrace` 前须核对信号处理配置；`ASCEND_COREDUMP_SIGNAL=none` 等禁用接收的状态可能导致进程终止，不能当作无副作用的离线解析。

---

## 故障处理总体流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 收集故障信息                                               │
│    应用类日志（plog）+ Device侧系统日志（msnpureport）+       │
│    环境信息（npu-smi、dmesg、Python堆栈）                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 分析故障原因                                               │
│    自上而下日志分析法：按业务流程逐步缩小到底层故障现象          │
│    从首报错算子开始排查（异步场景下可能出现多算子报错）          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 故障排除 + 记录                                           │
│    排除故障后记录处理要点，给出防范改进措施                    │
└─────────────────────────────────────────────────────────────┘
```

**故障信息类别：**
- **应用类日志**：Host 侧和 Device 侧应用程序产生的用户态日志，常用 `plog-<pid>_*.log`
- **Device 侧系统类日志**：内核态日志和系统进程日志，需用 `msnpureport` 工具导出
- **其他维测信息**：`npu-smi info`、`dmesg`、堆栈信息、coredump 文件

---

## AI Core Error 问题定位专题

### 问题现象

用户应用程序报错退出，屏幕日志错误码为 **EZ9999**，且日志中包含"**there is an aivec error exception**"或"**there is an aicore error exception**"；或者 plog 日志中存在报错日志"**Aicore kernel execute failed**"。

> **说明**：EZ9999 是屏幕层面的通用错误码，真正的诊断信息在嵌套的错误详情中（error code、errorStr、fault kernel_name 等字段）。

**报错示例：**

```
-----------------------------------------
   Ascend Error Message:
-----------------------------------------
EZ9999: Inner Error!
EZ9999: The error from device(chipId:4, dieId:0), serial number is 2,
there is an aivec error exception, core id is 11, error code = 0x10, dump info:
  pc start: 0x1240c46650b8,
  vec error info: 0xd019ddc1a,
  mte error info: 0x2ffeba07af,
  ifu error info: 0x4e5c097530000,
  ccu error info: 0x30c255954a000023,
  cude error info: 0,0,
  aic error mask: 0x65000020bd000288,
  para base: 0x1240c51b1dd0.
[FUNC:ProcessStarsCoreErrorInfo][FILE:device_error_proc.cc][LINE:1100]
  The extend info: errcode:(0x10, 0, 0) errorStr: Illegal instruction,
  which is usually caused by unaligned UUB addresses.
  Aicore kernel execute failed, device_id=4, stream_id=450,
  report_stream_id=2, task_id=442, flip_num=0,
  fault kernel_name=00_131_Grandients/Default/AddN.op56419/program id=2089,
  hash=16296079633597215637.[FUNC:GetError][FILE:stream.cc][LINE:1467]

  rtStreamSynchronize execute failed,
  reason=[The model stream execute failed]
```

### 报错日志字段解读

| 字段 | 说明 | 诊断用途 |
|------|------|---------|
| `chipId` / `dieId` | 报错芯片 ID | 关联物理位置及独立事件；固定位置也可能与作业分配或相同输入有关 |
| `serial number` | 报错序号 | 在同一可比较范围内结合任务标识和局部时序选择首报错候选 |
| `core id` | 报错芯片核 ID | 固定位置是候选线索，须结合负载、RAS/ECC 与受控设备对照 |
| `error code` | AI Core Error 错误码 | 按型号/版本结合 errorStr 解码；`0x800000` 单独出现不证明数组越界 |
| `errorStr` | 错误码文字描述 | 直接说明错误类型 |
| `fault kernel_name` | 报错算子 kernel 名称 | **分析的首要入口**，定位到具体算子 |
| `task_id` / `stream_id` | 报错任务和流编号 | 关联 plog 中的算子执行记录 |
| `hash` | 算子 hash | 在编译缓存中定位对应编译产物 |
| `pc start` | 程序计数器起始地址 | 定位算子内部的出错指令位置 |
| `vec error info` | 向量单元错误信息 | AI Vector Core (aivec) 报错时的寄存器 dump |
| `mte error info` | 内存传输单元错误信息 | 数据搬运相关错误 |
| `ifu error info` | 取指单元状态 | 按版本解码错误位，非零原始值不单独证明校验失败或硬件损坏 |
| `ccu error info` | CCU 状态 | 不等同 `cube error info`；结合该版本寄存器定义解释 |
| `aic error mask` | AI Core 错误掩码 | 掩码不是已触发错误清单，结合状态寄存器和解码文本 |
| `para base` | 任务参数块基址 | 不是全部 GM buffer 的合法区间，也不单独证明越界/释放后使用 |
| `aivec error exception` | AI Vector Core 报错 | 向量运算单元异常 |
| `aicore error exception` | AI Core 异常 | 结合解码判断具体故障单元，不能仅据此认定 Cube 异常 |

> **注意**：异步场景下首报错算子可能是受害者；serial number 只在可比较范围内辅助排序，继续回溯其输入和依赖。

### 完整定位流程

```
Step 1: 从屏幕日志提取 fault kernel_name
    │   确认报错算子名称，记录 device_id / stream_id / task_id
    ▼
Step 2: 在 plog 中搜索 "Aicore kernel execute failed"
    │   获取完整错误上下文，确认是否多个算子报错
    │   如有多个，按同一可比较范围内的序号及任务时序选择首错候选
    ▼
Step 3: 收集 Device 侧系统日志
    │   按现场 msnpureport --help 确认导出参数、设备范围与输出位置
    │   保留实际生成的整个目录，参见全量采集流程
    ▼
Step 4: 使用 msaicerr 工具分析 AI Core Error
    │   msaicerr -p ./aic_err_info/ -out ./analysis/
    │   在生成结果中核对 device_id / stream_id / task_id，再查看 Root cause conclusion
    ▼
Step 5: 核对芯片/核与负载的关联
    │   固定或不固定均不独立判定软硬件；结合 RAS/ECC、既有检测与受控对照
    ▼
Step 6: 根据 msaicerr 分析结果判断子类型
    │   按 "常见 AI Core Error 子类型" 表格匹配
    ▼
Step 7: 按子类型进行针对性排查
```

### msaicerr 工具使用详解

msaicerr 专门用于解析 AI Core Error，将二进制错误信息还原为可读的算子错误报告。
以下参数来自 oam-tools 的 `src/msaicerr/msaicerr.py`：`-p/--report_path` 指向故障信息目录，
`-out/--output_path` 指定输出位置。现场版本仍须核对帮助；离线诊断仅引用已有结果。
本接口没有 task_id 过滤参数，应在结果中关联设备、流和任务，不能用不存在的选项筛选。

```bash
# 分析含匹配日志、exception dump 与算子产物的故障信息目录
msaicerr -p ./aic_err_info/ -out ./analysis_result/

# 查找实际生成的报告；不要假定输出根目录直接包含 info.txt
find ./analysis_result/ -name info.txt
```

**info.txt 输出结构：**

```
********************Root cause conclusion********************
[此处为根因结论，常见结论如下]

# 结论1：精度溢出
"Atomic add has a precision overflow. Check the operator precision."
→ 见 "atomic add 精度溢出" 子类型

# 结论2：地址异常
"The input/output memory address of the operator is abnormal"
→ 见 "算子输入输出数据地址异常" 子类型

# 结论3：其他硬件/软件错误
→ 结合 error code 和 errorStr 进一步分析

************4. Operator Input/Output Memory************
# 检查算子输入输出地址是否在合法范围
input[0] addr: 0x124080042000 end_addr:0x124080042100 size: 0x100
input[1] addr: 0xaaaaaaaa end_addr:0xaaaaaab2 size: 0x8   # [ERROR] out of range
input[2] addr: 0x0 end_addr:0x4 size: 0x4                 # [ERROR] out of range
# 以上仅为异常地址示例；须核对有效分配范围和地址来源，UAF 还需释放时序
```

**分析结果包含：**
- 报错算子名称和对应源码位置
- AI Core Error 类型（向量/矩阵/内存/指令）
- 硬件寄存器状态（用于硬件故障判定）
- 算子输入输出内存地址合法性检查

### 收集 AI Core Error 问题信息

```bash
# 1. 收集 plog 日志
cp -r $HOME/ascend/log/debug/plog/ ./collected/plog/
cp -r $HOME/ascend/log/run/plog/ ./collected/plog_run/

# 2. 查看现场工具帮助，再按支持的参数导出Device系统日志
msnpureport --help
# 完整步骤见 collect-skill/references/full-log-collection.md；保留整个导出目录

# 3. 手动收集算子编译信息（算子 .o 和 .json 文件）
find ~/.cache/atc/ -name "*.o" -o -name "*.json" | \
    xargs -I{} cp {} ./collected/op_compile/

# 4. 收集环境信息
npu-smi info > ./collected/npu_smi_info.txt
dmesg | tail -200 > ./collected/dmesg.txt

# 5. 收集算子 dump 数据（精度分析需要）
# 在 acl.json 中配置 Dump 后重跑任务
# Dump 文件可用于对比算子输入输出与期望值

# 6. 收集 Profiling 数据（性能分析）
npu-smi info -t board -i 0 > ./collected/board_info.txt
```

### 常见 AI Core Error 子类型

| 子类型 | 典型现象 | 判断依据 | 根因 | 处理方向 |
|--------|---------|---------|------|---------|
| **HBM 比特 ECC 候选** | 匹配设备和时间的 ECC 事件 | 按型号/版本解码事件类型、地址和严重程度；区分 Host 内存与 Device HBM | 支持相应内存硬件分支，关联本次任务后判断影响 | 根据具体告警处置，必要时安排受控设备对照 |
| **icache 数据校验候选** | 解码明确指向取指/缓存校验 | 核对实际错误位、产物及已有 RAS/检测记录；IFU 非零或固定 core 不单独成立 | 缓存、取指或产物相关原因待缩界 | 比较匹配产物、设备记录和故障指令，不直接宣告坏卡 |
| **AI Core 超时故障** | `EE1002 Execution_Error_Stream_Synchronize_Timeout` | 结合任务类型、日志覆盖范围及 dispatch/done/依赖 | 已确认未按期完成；死循环、等待、丢失进展记录等需区分 | 追踪生产者及调度进展，有执行证据再检查内核循环 |
| **AI Core 硬件候选** | 重复设备异常并有相关健康/检测信息 | 解释实际健康告警，并核对 RAS/ECC、受控复现及作业分配 | 可能硬件故障；固定位置和笼统 health 异常不等于芯片损坏 | 按具体硬件事件隔离或检测，证据确认后安排硬件处理 |
| **索引类算子索引越界** | 索引算子发生地址异常 | 必须比较实际 index 与对应维度，不能仅凭 `0x800000` | 只有范围约束确被违反才确认输入索引越界 | 修正非法 index；缺输入时保留地址来源、tiling 和生命周期分支 |
| **atomic add 精度溢出候选** | msaicerr 输出 "Atomic add has a precision overflow" | 核对产品适用性、并发误报、slog 覆盖与输入范围；缺少 `Vm fault failed` 不独立确诊 | 可能数值溢出，亦可能工具误报或其他访问异常 | 证实数值分支后再评估累加精度与输入范围，并验证数值语义 |
| **算子输入输出数据地址异常** | msaicerr 输出 "memory address is abnormal" | 核对该工具使用的实际有效分配区间、访问大小和异常原文 | 地址访问异常；越界、未初始化或释放后使用等须追踪来源 | 检查传入地址与分配记录；UAF 需关联实际释放与使用时序 |
| **算子输入 args 下发前后不一致** | 同一任务执行前后参数快照有实际差异 | 核对任务、参数块、快照阶段及其预期可变性；随机错误本身不足 | 参数区可能被覆写或存在竞争，具体写入者待核实 | 追踪参数区写入者、访问范围与多流依赖 |
| **Dump 数据失败** | 原始日志明确报告 dump 失败 | 区分配置/路径/权限/空间错误与输入输出地址不可读；目录空不独立确诊 | 工具采集失败，可能另有上游访问异常 | 按实际失败原文处理，不把 dump 失败当作业务根因 |

### atomic add 精度溢出详细诊断

当 msaicerr 分析结果显示 "Atomic add has a precision overflow" 时，需进一步确认：

```bash
# 检查 Device slog 日志中是否有 "Vm fault failed"
grep -r "Vm fault failed" ./msnpureport_output/*/slog/dev-os-*/debug/device-os/device-os_*.log
```

- **未见 "Vm fault failed"**：先确认已提供的 slog 覆盖本次任务和时间窗，再结合产品型号、并发误报和输入范围评估精度溢出候选，不能凭关键词缺失确诊。
- **出现相关 "Vm fault failed"**：优先追踪地址映射、访问范围及生命周期；关联本次任务后分析访问异常，不能把它泛化为所有任务的唯一根因。

> **注意**：Atlas A2 训练/推理系列产品上，由于硬件优化，不会出现 atomic add 精度溢出问题。

### 判断是否为硬件故障

```
判断硬件故障的依据：
1. chipId 是否固定 — 多次报错是否都是同一 chipId
2. core id 是否固定 — 是否总是同一 core 报错
3. npu-smi info -t ecc -i <id> — ECC 错误计数是否持续增长
4. dmesg | grep -i "ecc\|hardware\|pcie" — 是否有硬件相关报错
5. 同一算子在其他芯片上是否正常执行 — 交叉验证
6. npu-smi info -t health -i <id> — 健康状态是否异常
```

```bash
# 快速硬件故障排查脚本
echo "=== ECC 错误计数 ==="
npu-smi info -t ecc -i 0

echo "=== 设备健康状态 ==="
npu-smi info -t health -i 0

echo "=== dmesg 硬件错误 ==="
dmesg | grep -i "ecc\|hardware\|pcie\|ascend.*error" | tail -20

echo "=== HBM 内存状态 ==="
npu-smi info -t memory -i 0
```

---

## 内存 OOM 问题定位专题

### 问题现象

**Device 侧 HBM OOM：**
```
[ERROR][GE] Load graph to device failed: memory not enough
[ERROR][ACL] HBM memory allocation failed, requested=32GB, available=28GB
EL0004: Memory_Allocation_Failure
```

**Host 侧 CPU 内存 OOM：**
```
Out of memory: Kill process <pid> (python)
```

**框架层 OOM：**
```
RuntimeError: [Core] Out of memory. (DT: 2026-04-29)
# torch_npu 报类似 CUDA OOM 的错误信息
```

### 快速判断流程

```
OOM 现象
    │
    ├── Device 侧 HBM OOM?
    │   ├── 日志含 "HBM memory allocation failed" / "EL0004" / "memory not enough"
    │   ├── npu-smi info -t memory 显示 HBM 使用率接近 100%
    │   └── → 减小 batch size / 开启模型并行 / 使用量化 / 开启重计算
    │
    ├── Host 侧 CPU 内存 OOM?
    │   ├── dmesg 含 "Out of memory: Kill process"
    │   ├── 某个 rank 突然消失（进程被杀）
    │   ├── free -h 显示内存不足
    │   └── → 增大宿主机内存 / 减少 num_workers / 减小数据预取缓存
    │
    └── 训练框架层 OOM?
        ├── PyTorch: "RuntimeError: Out of Memory"
        ├── MindSpore: "Out of Memory"
        └── → 检查框架内存配置（如 torch.npu.set_per_process_memory_fraction）
```

### HBM 内存分析工具

```bash
# 核对现场npu-smi帮助中卡/芯片ID定义后查看内存，勿混用逻辑device_id
npu-smi info -t memory -i 0

# 从已有日志核对内存统计，保留文件内顺序；新增统计需核对版本支持
grep -i "memory\|alloc\|free" $HOME/ascend/log/debug/plog/plog-*.log | \
    grep -i "GE\|ACL"

# Device业务进程内存：按现场帮助完成msnpureport导出后，检索实际目录
grep -Ri "memory" <device_export_dir> | grep -i "used\|free\|total"
```

### Host 侧内存分析

```bash
# 查看 OOM Killer 记录
dmesg | grep -i "out of memory\|oom-kill\|killed process"

# 查看进程内存占用排序
ps aux --sort=-%mem | head -20

# 实时监控内存
watch -n 1 free -h

# HCCL 通信 buffer 占用分析
grep -i "hccl.*buffer\|hccl.*memory" $HOME/ascend/log/debug/plog/plog-*.log
```

### asan 工具检测内存错误（Host 侧）

ASan需要编译器插桩及匹配的运行库。可重构建的Host native模块按对应工具链在编译与链接阶段启用`-fsanitize=address`，保留符号并核对Host架构和运行库版本，再在复现条件下分析报告。仅给现有Python进程预加载固定路径的libasan，不会给全部未插桩native代码补上访存检查，也不检查Device kernel。

没有可重构建模块或匹配运行库时，说明检测覆盖限制，继续分析已有core/堆栈和内存证据。不要把未执行的插桩验证写成已排除越界。

### 典型 OOM 场景与解决方案

| 场景 | 现象 | 待验证候选 | 条件修复与验证 |
|------|------|------|---------|
| 推理图加载申请失败 | `Load graph failed`及内存错误 | 容量/预算、图资源、其他占用或碎片 | 先量化故障时刻同口径占用，按已确认组成调整，不由阶段推定KV/激活大小 |
| 训练step内存申请失败 | step内出现OOM | 活跃tensor峰值、保留缓存、额外图/通信等 | 激活占用已证实时测试检查点；比较同输入峰值与训练语义 |
| 通信阶段资源失败 | HCCL分配或资源创建失败 | 通信内存、SQ/CQ等配额、其他进程/通信域占用 | 先确认失败资源类型；调整buffer仅适用于已证实的内存贡献 |
| 预处理进程退出 | DataLoader附近退出及内存压力 | Host/cgroup内存上限或其他退出原因 | 先关联OOM事件与PID/rank，再按实测worker/预取贡献调整 |
| 某rank退出、其他rank等待 | Kill记录与通信等待 | OOM、人工/调度器信号、应用错误等 | 核对退出来源及首错；不能由Kill直接判额外内存或泄漏 |

### 内存优化手段速查

按实际占用来源选择条件修复，具体API和参数查现场框架/后端版本：

- batch或训练激活主导峰值时，再测试减小batch、梯度累积或检查点/重计算，核对语义与吞吐影响。
- 参数/激活类型确实主导占用且任务支持时，评估混合精度；导入迁移工具本身不等于启用AMP。
- 框架每进程内存比例是分配预算/上限，不能称为“内存增长模式”；提高上限需核对物理可用量与其他进程，降低上限也可能更早OOM。
- 清理缓存只可能释放未使用的缓存块，不能释放活跃tensor，也不解决所有碎片或其他组件的资源耗尽。
- HCCL buffer调整须先证实其实际占用和通信约束，不能一律设为固定数值。
- `ASCEND_OPP_PATH`用于算子库路径，不是减少编译缓存的开关；修改它可能改变加载产物，不能作为通用OOM修复。

---

## 进程中断问题定位专题

### 问题现象

应用程序异常退出（非正常结束），可能伴随 coredump 文件或 Python 异常栈：

```
Segmentation fault (core dumped)
RuntimeError: CANN error, error code: ...
Fatal Python error: Segmentation fault
Aborted (core dumped)
# 有时无明显报错，进程直接消失
```

### 完整定位流程

```
Step 1: 确认进程退出方式
    ├── 进程退出码 → echo $?
    │   139 = SIGSEGV (段错误)
    │   134 = SIGABRT (异常终止)
    │   137 = 常见shell中的128+SIGKILL；结合退出记录确认信号来源，不能单凭137断定OOM
    ├── dmesg 中是否有 OOM Kill / signal 信息
    └── 是否产生 coredump 文件

Step 2: 收集故障信息
    ├── plog 日志 → 以末尾异常为回溯入口，核对同一任务的首错候选、传播及清理事件
    ├── coredump 文件 → 按进程实际限制、dumpable及文件/管道处理器配置核对已有产物
    ├── Python 堆栈 → faulthandler 模块
    └── Host 侧 dmesg / syslog

Step 3: 分析 coredump
    ├── 使用 asys 工具: asys analyze -r=coredump --exe_file=<exe> --core_file=<core>
    ├── 或使用 gdb: gdb -c core.xxx <executable>
    └── 查看崩溃时线程堆栈

Step 4: 结合 plog 分析时序
    ├── plog 中最后几条日志判断崩溃阶段
    ├── 是否在 aclrtSetDevice / aclFinalize 等关键接口
    └── 是否有内存相关报错先于崩溃

Step 5: 按典型场景匹配处理
```

### coredump 分析工具

```bash
# Host直接文件模式的限制设置示例；有限上限也可生成core，管道处理器另按其语义核对
ulimit -c unlimited

# 查找 coredump 文件
find / -name "core.*" -newer /tmp/task_start_time 2>/dev/null

# 使用匹配本次 core 的可执行文件分析
asys analyze -r=coredump --exe_file=/usr/bin/python3 --core_file=core.python.12345 --output=./core_analysis/

# 使用 gdb 分析
gdb /usr/bin/python3 core.python.12345 -batch \
    -ex "thread apply all bt" -ex "info threads" -ex "quit"

# Python faulthandler（在代码中启用）
import faulthandler
faulthandler.enable()
# 崩溃时会自动打印线程堆栈到 stderr
# 也可输出到文件: faulthandler.enable(file=open('/tmp/crash.log', 'w'))
```

### 典型案例

以下是故障机制的调查示例，不附独立现场与修复记录。现象与命令仅作入口，各候选须由本次证据确认，不能由一条通用报错直接套用根因。

#### 无可用 Context

**现象**：多线程/多进程场景下程序崩溃，日志出现 `context not available`

**诊断命令**：
```bash
grep -i "context.*not.*available\|SetDevice" plog-*.log
```

**候选与核对**：检查当前线程绑定的设备/Context、创建与销毁顺序、进程边界和实际API返回。`context not available`不能单独证明某线程的SetDevice调用使其他线程Context失效。

**条件处理**：按现场版本的Context/线程语义修正绑定与生命周期；用调用轨迹确认失败点获得有效Context，不假设所有场景都需每线程独立创建。

#### rtMemcpyAsync 异步参数校验报错

**现象**：`rtMemcpyAsync execute failed, errorStr=Invalid_Argument`，进程退出

**诊断命令**：
```bash
grep -i "rtMemcpyAsync.*failed\|Invalid_Argument" plog-*.log
```

**候选与核对**：检查完整参数错误详情、src/dst分配区间、长度/目标容量、拷贝方向、stream/Context和异步内存约束。`Invalid_Argument`本身不能锁定空指针或释放后使用。

**条件处理**：修正已证实违反的参数约束，并确认对象生命周期覆盖异步完成；地址非空不等于有效。

#### 算子执行过程中 D2D 拷贝出错

**现象**：`EI0012 Execution_Error_SDMA` 或 `D2D copy failed`

**诊断命令**：
```bash
grep -i "EI0012\|SDMA\|D2D.*failed" plog-*.log
npu-smi info -t board -i 0
dmesg | grep -i "pcie.*error\|sdma"
```

**候选与核对**：区分同设备与跨设备拷贝，检查地址、长度、方向、生命周期、资源和Driver/SDMA详情。D2D失败本身不证明经过PCIe或发生链路故障。

**条件处理**：按已确认的参数/资源机制修正；只有路径和链路事件关联时才进入对应硬件/互联调查，命令参数按现场帮助核对。

#### 环境变量访问冲突导致应用程序异常终止

**现象**：多进程场景下随机崩溃，堆栈指向 `getenv`/`setenv` 相关调用

**诊断命令**：
```bash
gdb /usr/bin/python3 core.python.xxx -batch -ex "thread apply all bt"
# 堆栈中出现 getenv/setenv 调用
```

**候选与核对**：同一进程并发修改环境可能与读取竞争，但栈在`getenv/setenv`不证明发生此竞争；还需核对有效栈、线程访问、内存破坏及对应libc语义。多进程本身不等于共享一份可变环境。

**条件处理**：已证实并发环境修改问题时，将配置在启动阶段完成或按接口约束串行管理；不要将只读`getenv`一概描述为非线程安全。

#### 析构函数中调用去初始化接口 aclFinalize 导致 coredump

**现象**：程序正常结束但产生 coredump，堆栈在 `aclFinalize`

**诊断命令**：
```bash
gdb /usr/bin/python3 core.python.xxx -batch -ex "bt"
# 堆栈显示在 aclFinalize 或 __gcov_exit 等 cleanup 函数中
```

**候选与核对**：检查资源销毁顺序、重复去初始化、未完成任务、全局析构及更早内存破坏。崩溃栈在`aclFinalize`不单独证明全局对象析构顺序问题。

**条件处理**：生命周期问题已证实时，按匹配API契约先完成任务、释放相关资源，再统一去初始化；用实际调用轨迹和复跑验证。

#### Signal 11 (SIGSEGV) 段错误

**现象**：进程退出码 139，有 coredump 文件

**诊断命令**：
```bash
echo $?  # 返回 139
ls -la core.*  # coredump 存在
gdb /usr/bin/python3 core.python.xxx -batch -ex "thread apply all bt" -ex "quit"
```

**候选与核对**：确认信号、故障地址和有效帧，再区分空指针、越界、释放后使用、权限或栈破坏等。139本身不确定哪一项，也不定位责任库。

**处理**：gdb 分析 coredump 定位具体代码行；结合 asan 工具检测内存错误

---

## 进程卡住问题定位专题

### 问题现象

应用程序无输出、无超时报错，长时间挂起：

```bash
# 进程存在但无进展
ps aux | grep python
# CPU 使用率 ~0%，但进程未退出

# 训练 loss 长时间不变
[INFO] step=1000, loss=2.345   # 之后无新输出

# plog 最后一条日志停留在很久以前
# 无 ERROR 日志，但最后一条 INFO 日志时间戳在几分钟甚至几十分钟前
```

### 完整定位流程

```
Step 1: 确认卡住状态
    ├── 进程是否存在: ps aux | grep <pid>
    ├── CPU 使用率: top -p <pid> → 低CPU仅提示等待，结合预期耗时、业务和Device进展判断
    ├── 是否有新日志输出: tail -f $HOME/ascend/log/debug/plog/plog-*.log
    └── strace 快速查看: strace -p <pid> -c -f
        （看是否阻塞在某个系统调用）

Step 2: 判断卡住阶段
    ├── plog 最后一条日志内容 → 判断在编译/执行/通信哪个阶段
    ├── 如果在 HCCL 通信阶段 → 检查多卡同步
    ├── 如果在数据加载阶段 → 检查 DataLoader / IO
    └── 如果在算子执行阶段 → 检查是否有 AI Core 超时

Step 3: 导出进程堆栈
    ├── Python 进程: py-spy dump --pid <PID>
    ├── C++ 进程: gdb -p <PID> -batch -ex "thread apply all bt" -ex "quit"
    ├── asys collect -r=stacktrace --remote=<PID> --all --output=./stack/
    └── Python faulthandler: kill -SIGUSR1 <PID> (部分框架支持)

Step 4: 多卡场景特殊排查
    ├── 各 rank 进程状态是否一致（是否某 rank 已退出）
    ├── dmesg 检查 OOM Kill: dmesg | grep -i "kill process"
    ├── 各 rank plog 对比，找到最后完成同步的步骤
    └── 检查 HCCL 超时日志: grep -i "EI0002\|timeout" plog-*.log

Step 5: 根据卡住类型针对性处理
```

### 典型案例

以下示例提供待核对的机制，不是仅凭现象即可确认的历史案例。

#### fork 后应用卡死

**现象**：训练脚本在 `DataLoader` 或 `multiprocessing.Pool` 初始化后卡死

**诊断**：
```bash
# 导出卡住进程的堆栈
py-spy dump --pid <PID>
# 或
asys collect -r=stacktrace --remote=<PID> --all --output=./stack/

# 如果堆栈显示在 fork/waitpid 等调用，且使用了 ACL Context
```

**候选与核对**：父进程已初始化运行时后fork，可能使子进程继承不适用的运行时/锁状态；但DataLoader初始化卡住或栈在waitpid不能单独证明这个机制，须核对启动方式、初始化顺序及各进程栈。

**条件处理**：该候选有证据且框架支持时，测试`spawn`或受支持的`forkserver`路径。下例仅示意配置；核对主入口保护、对象可序列化及初始化顺序：
```python
# PyTorch DataLoader
torch.utils.data.DataLoader(
    dataset,
    num_workers=4,
    multiprocessing_context='spawn'  # 关键设置
)

# 全局设置
torch.multiprocessing.set_start_method('spawn')
```

#### HCCL AllReduce 超时导致所有 rank 卡死

**示意现象**：多卡训练在某一步等待，观测到120s后触发`EI0002 Communication_Error_Timeout`。此处120s仅为示例观测，不代表建链/执行的统一默认值。

**诊断步骤**：
```bash
# 1. 检查各 rank 进程状态
for i in $(ps aux | grep "torchrun\|python.*train" | awk '{print $2}'); do
    echo "PID=$i, CPU=$(ps -p $i -o %cpu= | tr -d ' ')%"
done

# 2. 检查是否有 rank 被 OOM Killer 杀掉
dmesg | grep -i "out of memory\|killed process"

# 3. 查看各 rank 最后的日志
for f in plog-*.log; do echo "=== $f ==="; tail -5 "$f"; done

# 4. 检查 HCCL 超时日志
grep -i "EI0002\|timeout\|AllReduce.*timeout" plog-*.log
```

**机制与候选**：对应通信阶段未在有效预算内完成，报超时rank可能是等待方。需要区分对端提前退出、collective序列/参数不一致、负载延迟和链路异常等；不能优先把超时等同OOM。

**条件处理**：
1. 按通信域、操作序列、rank与局部时间线核对各端进展及最早具体错误。
2. Host OOM仅在内核/cgroup杀进程记录与任务PID/rank关联后成立；再按实际worker、预取或其他占用贡献调整。
3. 超时配置按现场版本、实际阶段和有效值核对；只有确认任务持续进展且预算不合理时再评估调整，不能用延长超时掩盖退出、死锁或序列不一致。

#### 数据加载卡死

**现象**：训练启动后第一个 step 都无法完成，卡在 DataLoader

**诊断**：
```bash
# 导出堆栈
py-spy dump --pid <PID>
# 堆栈显示在 DataLoader worker 进程的 fork 相关调用
```

**候选与核对**：检查worker异常/退出、队列、IO、锁与启动方式。仅有fork相关帧不能证明已继承ACL Context。

**条件处理**：fork运行时继承问题已获支持时，再验证spawn配置与数据加载语义：
```python
torch.utils.data.DataLoader(
    dataset, num_workers=4,
    multiprocessing_context='spawn'
)
```

#### 算子执行挂起导致 AI Core 超时

**现象**：单算子或特定算子执行后无返回，最终触发 `EE1002`

**诊断**：
```bash
# plog 显示 task_id 已 dispatch 但无 done 记录
grep -i "dispatch.*task_id=442\|done.*task_id=442" plog-*.log
# 未观察到匹配done；先核对任务、日志级别、时间窗、轮转及执行/依赖进展
```

**候选原因**：已确认任务执行且长时间无进展时，检查内核循环、tiling工作量及依赖等待。只有dispatch而缺少done也可能是日志覆盖不全，不能确认算子挂起、排除正常完成或锁定上述根因。

**处理**：
1. 检查算子 tiling 参数是否合理
2. 使用 Profiling 分析算子执行时间
3. 简化算子输入 shape 排查

#### 分布式初始化阶段卡住

**现象**：训练脚本启动后停留在 `init_process_group` 阶段

**诊断**：
```bash
# 未见 GE/HCCL 日志时先核对覆盖范围和级别，不能据此确认图编译尚未开始
grep -c "GE\|HCCL" plog-*.log  # 输出 0

# 检查网络连通性
ping <other_node_ip>
nc -zv <other_node_ip> <port>
```

**候选原因**：rank_table 配置错误/网络不通/端口占用，须由对应配置、连通性或端口记录支持。

**处理**：
1. 检查 rank_table 文件中各 rank 的 IP 和端口
2. 确认各节点间网络连通
3. 确认端口未被占用：`netstat -tlnp | grep <port>`

### asys 工具在卡住场景的使用

```bash
# 实时导出卡住进程堆栈
asys collect -r=stacktrace --remote=<PID> --all --output=./stack_dump/

# 健康检查（检查 Device 硬件和驱动状态）
asys health -d 0

# 硬件检测按待验证分支选择模式与设备，先核对芯片支持范围
asys diagnose --help

# 性能数据采集（分析是否有性能瓶颈）
asys profiling -r=aicore -p=60 -d=0 --output=./profiling/
```

---

## 故障定位工具

### asys 工具

asys 是一站式故障信息收集与分析工具。下列接口对应 oam-tools 的
`src/asys/cmdline/cmd_parser.py`；先核对现场版本的子命令帮助和材料要求。
离线诊断只引用已有产物，现场采集、复跑和检测应由获准的现场流程执行。

| 功能 | 命令示例 | 说明 |
|------|---------|------|
| 故障信息收集 | `asys collect --output=./output/` | 收集日志、环境信息 |
| 业务复跑+收集 | `asys launch --task="python3 train.py" --output=./output/` | 运行业务并收集信息 |
| 健康检查 | `asys health -d 0` | 检查 Device 0 硬件和驱动状态 |
| 硬件检测 | `asys diagnose --help` | 按芯片和故障分支选择检测模式 |
| AI Core Error 解析 | `asys analyze -r=aicore_error --path=./aic_err_info/` | 显式提供匹配的故障信息目录 |
| coredump 解析 | 见 [命令手册](coredump-command-playbook.md#4-cann-asys-coredump) | 必须匹配可执行文件、core 与符号 |
| trace 文件解析 | `asys analyze -r=trace --file=./trace_file --output=./analysis/` | 解析 trace 文件 |
| stackcore 解析 | 见 [命令手册](coredump-command-playbook.md#7-stackcore-analysis) | 核对文件及符号路径 |
| 实时堆栈导出 | `asys collect -r=stacktrace --remote=<PID> --all --output=./stack/` | 导出指定进程的堆栈 |
| 性能数据采集 | `asys profiling -r=aicore -p=60 -d=0 --output=./profiling/` | 按所选指标采集 |

### msaicerr 工具

专门用于解析 AI Core Error，输入要求与参数见上文 [msaicerr 工具使用详解](#msaicerr-工具使用详解)。
报告生成后按 device、stream/task、kernel 和故障时间核对归属。

**分析结果包含**：
- 报错算子名称和对应源码位置
- AI Core Error 类型（向量/矩阵/内存/指令）
- 硬件寄存器状态（用于硬件故障判定）
- 算子输入输出内存地址合法性检查

---

## 常用定位操作

### 通过 Device 日志获取故障 ID 并排查 RAS 硬件故障

以下`device_syslog/`、`syslog/`代表实际导出材料目录。先按[全量采集流程](../../collect-skill/references/full-log-collection.md#3-导出-device-和综合现场)核对现场`msnpureport --help`及设备范围，保留工具生成的整个目录。参数和内部目录随Driver版本变化，不能通用使用未经核对的`-d/-output`组合。

```bash
# 1. 按现场工具帮助完成导出，以下检索已有材料

# 2. 搜索 RAS 故障 ID
grep -Ri "fault_id\|ras\|ecc\|hardware" ./device_syslog/

# 3. 通过 npu-smi 查看 ECC 错误计数
npu-smi info -t ecc -i 0
```

### 通过 Device 日志查看资源占用过高的信息

```bash
grep -RE "memory|stream|event|notify" ./syslog/ | grep -i "high\|overflow\|exceed"
```

### 通过 Device 日志确认 Host 进程的拉起与结束时间

```bash
grep -RE "process_start|process_end|pid=[0-9]+" ./syslog/
```

### 查看 Python / C++ 应用程序的堆栈

```bash
# Python 进程实时堆栈（py-spy 工具）
pip install py-spy
py-spy dump --pid <PID>

# Python 内置方式（向进程发送信号）
kill -SIGUSR1 <PID>   # 部分框架支持

# C++ 进程实时堆栈（gdb）
gdb -p <PID> -batch -ex "thread apply all bt" -ex "quit"

# 使用 asys 工具（推荐）
asys collect -r=stacktrace --remote=<PID> --all --output=./stack_dump/
```

---

## 故障案例集索引

以下ID指向 [cases.md](./cases.md) 的未验证机制示例，保留用于解释与检索，不能当作已验证历史修复或本次根因证据：

| 案例 ID | 问题类型 | 关键现象 |
|---------|---------|---------|
| CASE-001 | 精度 | 训练loss出现NaN，区分输入、前向及梯度机制 |
| CASE-002 | 进程卡住 / HCCL 超时 | 等待超时与对端进展/退出的关联 |
| CASE-003 | 算子编译失败 | UB需求与目标容量约束 |
| CASE-004 | HBM OOM | 大模型推理图加载失败 |
| CASE-005 | 精度不达标 | FP16 MatMul 结果差异超阈值 |
| CASE-006 | 日志缺失 | 核对轮转、配置与采集覆盖 |
