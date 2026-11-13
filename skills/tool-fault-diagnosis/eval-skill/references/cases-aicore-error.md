# AI Core Error 案例集

## CASE-AIC-001：MoeFinalizeRoutingV2Grad 缺少 MTE3 与向量单元同步
### 1. 问题现象描述及版本信息

**1.1 问题描述**
使用mssanitizer对MoeFinalizeRoutingV2Grad内核进行memcheck、racecheck和synccheck检测时，检测到UB上的潜在RAW hazard，涉及向量流水线写入与MTE3流水线读取，提示内核存在数据竞争和内存越界风险。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | — |
| 芯片型号 | — |
| 训推框架版本 | — |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
[mssanitizer] ERROR: Potential RAW hazard detected at UB in MoeFinalizeRoutingV2Grad_10203314ec7002121aebee0a51794189_20001:
====== ERROR: Potential RAW hazard detected at UB in MoeFinalizeRoutingV2Grad_10203314ec7002121aebee0a51794189_20001:
======    PIPE_V Write at RAW()+0x2fee0 in block 0 (aiv) on device 0 at pc current 0xec2c (serialNo )
======    PIPE_MTE3 Read at RAW()+0x2fee0 in block 0 (aiv) on device 0 at pc current 0xf440 (serialNo )
======    #3 /usr1/turing/ops/ops-transformer/build/binary/ascend910_93/src/moe_finalize_routing_v2_grad/op_kernel/moe_finalize_routing_v2_grad_base.h  ======    #2 /usr1/turing/ops/ops-transformer/build/binary/ascend910_93/src/moe_finalize_routing_v2_grad/op_kernel/moe_finalize_routing_v2_grad_base.h
```

**排查路径**

报告MoeFinalizeRoutingV2Grad在UB上的Potential RAW 汇聚到moe_finalize_routing_v2_grad_base.h的相邻路径，因此排除单纯的外部内存分配、框架调度和普通算子输入错误，聚焦到算子内核中V与MTE3之间的硬件流水线依赖。日志本身只能直接证明跨流水线RAW冲突，缺少同步事件这一更深层源代码根因由该访问关系结合根因结论补齐。

### 3. 问题根因

moe_finalize_routing_v2_grad内核在MTE3与向量单元(V)访问共享UB数据的路径上缺少硬件事件同步，导致PIPE_V写入与PIPE_MTE3读取发生RAW数据竞争并产生内存越界风险。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
在moe_finalize_routing_v2_grad内核基类的相关数据路径中补充正确的MTE3→V和V→MTE3硬件事件同步，确保MTE3写入完成后向量单元再读取、向量写入完成后MTE3再读取或搬运；随后使用mssanitizer重新执行memcheck、racecheck和synccheck，并覆盖相关算子冒烟测试。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=MoeFinalizeRoutingV2Grad,mssanitizer；stage=kernel_sync；error_code=—；fault_type=raw_hazard
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-AIC-002：QuantBatchMatMulV3 非法地址访问触发 AICore 异常
### 1. 问题现象描述及版本信息

**1.1 问题描述**
CANNJudge运行选手提交的QuantBatchMatMulV3融合算子时，任务在stream 46上执行失败，流同步返回AICore exception，随后设备侧报告AICore任务异常，导致该NPU无法继续正常承载任务。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | — |
| 芯片型号 | — |
| 训推框架版本 | — |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
[ERROR] RUNTIME(2850263,judge) -01-13  .708.434 [davinci_kernel_task.cc ]2850308 PrintErrorInfoForDavinciTask:[DFX_INFO]Aicore kernel execute failed, device_id=0, stream_id=46, report_stream_id=46, task_id=9, flip_num=0, fault kernel_name=QuantBatchMatMulV3_976087cc1146bf2729c85696ec47a2a3_0, fault kernel info ext=none, program id=0, hash=3504003475495803671。
[ERROR] RUNTIME(2850263,judge) -01-13  .708.434 [davinci_kernel_task.cc ]2850308 PrintErrorInfoForDavinciTask:[DFX_INFO]Aicore kernel execute failed, device_id=0, stream_id=46, report_stream_id=46, task_id=9, flip_num=0, fault kernel_name=QuantBatchMatMulV3_976087cc1146bf2729c85696ec47a2a3_0, fault kernel info ext=none, program id=0, hash=3504003475495803671。明确故障内核为QuantBatchMatMulV3。
[ERROR] RUNTIME(2850263,judge) -01-13  .708.467 [stream.cc ]2850263 GetError:Stream Synchronize failed, stream_id=46, retCode=0x26, [aicore exception]。确认执行阶段发生AICore异常。
[ERROR] RUNTIME(2850263,judge) -01-13  .741.322 [device_error_core_proc.cc ]2850308 PrintCoreInfo:The extend info: errcode:(0, 0x200000000000000, 0) errorStr: The MPU address access is invalid. fixp_error0 info: 0x8ff9089, fixp_error1 info: 0x33, fsmId , tslot , thread , ctxid , blk , sublk , subErrType 。明确硬件侧错误为MPU非法地址访问。
```

**排查路径**

1. 开始，RUNTIME在内核任务错误处理路径中明确打印fault kernel_name=QuantBatchMatMulV3_...，因此故障对象首先落在该融合算子，而不是一个未识别的通用设备任务。2. 报告Stream Synchronize failed及AICORE Kernel task happen 显示507015从RUNTIME经aclnn/ASCENDCL向上层传播，排除普通API调用参数或同步超时作为首因。3. 记录task exception、aicore 进一步给出The MPU address access is invalid，故最终聚焦为QuantBatchMatMulV3内核实现的非法访存。日志未直接记录NPU状态切换为ERROR的状态管理过程，但已完成从算子任务到AICORE MPU异常的日志定界，状态不可恢复由给定根因结论补齐。

### 3. 问题根因

QuantBatchMatMulV3融合算子实现存在非法地址访问，触发AICore MPU异常并使设备进入无法自动恢复的ERROR状态。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
修正QuantBatchMatMulV3融合算子的地址计算、指针传递、张量边界和tiling参数校验，确保AICORE所有访存地址均落在合法分配及有效范围内；在提交或执行前增加算子参数和边界检查，并由设备管理侧补充AICore异常后的隔离、复位和自动恢复机制，避免单个非法算子拖垮整卡。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=QuantBatchMatMulV3,AICore；stage=kernel_execute；error_code=0x26；fault_type=invalid_address
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-AIC-003：SDMA 目的地址越界导致 SMMU 页表翻译失败
### 1. 问题现象描述及版本信息

**1.1 问题描述**
使用 PyTorch 框架运行业务时，设备侧 SDMA 任务执行异常，Runtime 侧报错 errType=0x1(task exception) sqe_type=11(sdma)，模块错误 EE8888，Stream Synchronize failed retCode=0x20b memcpy exception

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | — |
| 芯片型号 | — |
| 训推框架版本 | — |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
[ERROR] RUNTIME(1483982,python) -04-11  .074.439 [engine.cc ]1483982 ProcLogicCqReport:[LOAD][LOAD]Task run failed, device_id=3, stream_id=2, task_id=978, sqe_type=11(sdma), errType=0x1(task exception), sqSwStatus=0x3
[ERROR] RUNTIME(1483982,python) -04-11  .074.439 [engine.cc ]1483982 ProcLogicCqReport:[LOAD][LOAD]Task run failed, device_id=3, stream_id=2, task_id=978, sqe_type=11(sdma), errType=0x1(task exception), sqSwStatus=0x3
[ERROR] RUNTIME(1483982,python) -04-11  .074.976 [device_error_proc.cc ]1483982 ProcessStarsSdmaErrorInfo:[LOAD][LOAD]report error module_type=3, module_name=EE8888
[ERROR] RUNTIME(1483982,python) -04-11  .074.999 [device_error_proc.cc ]1483982 ProcessStarsSdmaErrorInfo: there is a sdma error, sdma channel is 22, sdmaBlkFsmState=0x7, dfxSdmaBlkFsmOstCnt=0x0, sdmaChFree=0x0, irqStatus=0x220000, cqeStatus=0x3
cqe status x70000 / channelid x17, status:transfer page error, smmu return terminate
[ERROR] RUNTIME(1483982,python) -04-11  .079.712 [stream.cc ]1483982 GetError: Stream Synchronize failed, stream_id=2, retCode=0x20b, [memcpy exception]
[INFO] GE(1483982,python) -04-11  .990.202 [davinci_model.cc ]1483982 CopyInputForNoZeroCopy:[Force Copy] model_id , input_index , id , offset x3c19c00, base x125aa4082a00, dst_addr x125aa7c9c600, dst_size , src_addr x12553e410200, src_size [INFO] GE(1483982,python) -04-11  .698.176 [davinci_model.cc ]1483982 InitFixedFeatureMap: memory_base x125818646a00, memory_type / [davinci_model.cc ] fixed_mem_size_: 10999809536
pytorch fix地址内存范围 x125818646a00 ~ 125AA8083000 / sdma bad dst_addr x125aa7c9c600 copysize 范围 x125aa7c9c600 ~ 125AA849C620 超过pytorch fix区间
sdma ok dst_addr x125aa6c9c200 copysize 范围 x125aa6c9c200 ~ 125AA749C220 在pytorch fix区间内
```

**排查路径**

Runtime 侧 SDMA Task run failed errType=0x1 sqe_type=11(sdma) EE8888，retCode=0x20b memcpy exception，定界到 SDMA 拷贝异常 → Device 侧 cqe status x70000 status:transfer page error smmu return terminate，定界到 SMMU 页表翻译失败（内存未申请或大内存偏移越界）→ 追溯 SQE 地址来源：grep DevMalloc 未命中排除 Runtime 接口申请，grep InitFixedFeatureMap 命中确认 PyTorch 框架申请（0x125 开头）→ 计算 PyTorch fix 区间 0x125818646a00 ~ 0x125AA8083000 → 对比坏地址 0x125aa7c9c600+8388640=0x125AA849C620 超出上限，正常地址 0x125aa6c9c200+8388640=0x125AA749C220 在区间内 → 定界为 PyTorch 固定内存申请大小不足导致 SDMA 地址越界，非 SDMA 硬件故障、非 SMMU 故障、非 Runtime 接口错误

### 3. 问题根因

PyTorch 框架申请的固定内存区域（FixedFeatureMap）大小不足，SDMA 任务计算出的目的地址（dst_addr）加上拷贝长度后超出了该固定内存区域的边界，导致 SMMU 页表翻译失败（transfer page error）。具体表现为 dst_addr 0x125aa7c9c600 加上长度 8388640 后的结束地址 0x125AA849C620 超过了 PyTorch 申请的内存上限 0x125AA8083000。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
检查 PyTorch 固定内存（FixedFeatureMap）的申请大小是否满足模型实际需求；排查 GE 下发任务时的 offset 计算逻辑，确认是否存在越界偏移；若为模型结构问题，调整模型或增加内存预留

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=见正文；stage=见正文；error_code=—；fault_type=见正文
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-AIC-004：CheckShape 误用 storage_shape 校验非连续输出
### 1. 问题现象描述及版本信息

**1.1 问题描述**
调用aclnnNLLLoss2d接口时，任务在参数检查阶段失败，日志报告输出tensor形状应为[1]但当前形状不符合要求，随后workspace size获取失败并触发执行器资源释放。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | — |
| 芯片型号 | — |
| 训推框架版本 | — |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
[ERROR] OP(3780436,opapi_test) -16 07  .715.994 [aclnn_nll_loss2d.cpp ][NNOP][CheckShape][3780436] errno[161002] OpName:[aclnnNLLLoss2d_0] Shape of out tensor should be [1], but current is [[1
[ERROR] OP(3780436,opapi_test) -16 07  .716.067 [aclnn_nll_loss2d.cpp ][NNOP][CheckParams][3780436] errno[561000] OpName:[aclnnNLLLoss2d_0] check CheckShape(self, target, weight, out, totalWeig
[ERROR] OP(3780436,opapi_test) -16 07  .716.075 [aclnn_nll_loss2d.cpp ][NNOP][aclnnNLLLoss2dGetWorkspaceSize][3780436] errno[561000] OpName:[aclnnNLLLoss2d_0] check ret == ACLNN_SUCCESS failed.
```

**排查路径**
最早错误发生在aclnn_nll_loss2d.cpp的CheckShape，而不是设备执行或底层运行时阶段。后续CheckParams、GetWorkspaceSize和执行器释放错误均由该形状校验失败向上游传播，问题聚焦于aclnnNLLLoss2d的输出形状检查逻辑。

### 3. 问题根因

根因：aclnnNLLLoss2d的CheckShape在reduction非none时错误使用storage_shape校验输出tensor元素个数，非连续输出tensor应使用view_shape，导致合法输出被误报为形状错误。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
修改aclnnNLLLoss2d的CheckShape逻辑：当reduction不为none时，使用输出tensor的view_shape计算和校验元素个数；补充非连续输出tensor及不同reduction取值的回归测试，确保合法的视图元素个数为1时不再触发形状错误。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=ops-nn,aclnnNLLLoss2d,CheckShape；stage=validation；error_code=161002；fault_type=validation_failure
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-AIC-005：TP/FSDP 并行下 Tensor 与 DTensor 混用
### 1. 问题现象描述及版本信息

**1.1 问题描述**
DeepSeek-V4模型训练进入前向计算后失败，调用MHC相关融合路径时触发npu_rms_norm类型错误；在包含CP的并行路径中，分布式send操作还因缺少DTensor分片策略而失败，训练进程无法正常完成。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | 参考仓库readme |
| HDK 版本 | — |
| 芯片型号 | 910B |
| 训推框架版本 | torchtitan-npu（master分支6-26最新代码） |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
File "<home>/torchtitan_npu/converters/kernels/mhc_prepost.py", line 326, in forward — 前向调用进入MHC融合算子封装。
File "<home>/torchtitan_npu/ops/triton/mhc_triton.py", line 222, in forward — MHC Triton实现继续调用归一化路径。
RuntimeError: npu.npu_rms_norm.default got mixed torch.Tensor and DTensor, need to convert all torch.Tensor to DTensor before calling distributed operators!` — 明确指出npu_rms_norm输入类型混用。
NotImplementedError: Operator c10d.send.default does not have a sharding strategy registered.` — TP+CP路径中的另一分布式张量分片策略缺失错误。
```

**排查路径**
堆栈从模型前向进入mhc_prepost和mhc_triton，最终在npu_rms_norm的分布式算子分发处报错，直接排除为训练调度、优化器或普通业务数据异常。另一条CP路径定位到c10d.send的DTensor分片策略分发，但共同指向TP相关分布式张量与融合算子的兼容性边界。

### 3. 问题根因

根因：TP/FSDP并行下npu_mhc_post融合算子未正确适配DTensor分布式张量，导致其内部npu_rms_norm混用torch.Tensor和DTensor并触发运行时检查。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
修复npu_mhc_post融合算子的DTensor适配，确保进入npu_rms_norm的所有输入及参数统一为DTensor并正确传播TP布局；同时为TP+CP涉及的c10d.send.default补充分片策略注册。短期规避可关闭npu_mhc_post融合算子，改用兼容的非融合实现或启用经过验证的编译路径，并重新验证TP、TP+CP及FSDP组合。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=torchtitan-npu,DTensor,FSDP,TP；stage=distributed_runtime；error_code=—；fault_type=type_mismatch
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注
