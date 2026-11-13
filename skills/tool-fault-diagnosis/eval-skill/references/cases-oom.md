# 内存OOM 案例集

## CASE-OOM-001：NPU OOM 致 RoCE QP 分配失败
### 1. 问题现象描述及版本信息

**1.1 问题描述**
跨节点数据传输压测中，HIXL 无法与远端引擎完成 RoCE 通道建链，客户端等待 10000 ms 后超时，报 Channel 创建及 Transfer 失败。表面现象是网络连接超时；日志未见进程退出。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | 9.1.0 |
| HDK 版本 | 25.5.2 |
| 芯片型号 | A3 |
| 训推框架版本 | vllm-ascend + glm5.2 + mooncakestore PD 分离部署 |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```text
Resource_Error_Insufficient_Device_Memory(EI0011): Failed to allocate [262144~3145728] bytes of NPU memory.
Failed to allocate resource qp with info aicpu rank,localUserrank,localIpAddr: <node-ip>,deviceLogicId,sendCqDepth. Reason: Resources are exhausted.
[Channel] Create failed, local=[protocol=roce, addr=IPv4:<node-ip>, devPhyId=0], remote=[protocol=roce, addr=IPv4:<node-ip>, devPhyId=15]
[ERROR] HCCL(...): [Recv][RaSocket]errNo[0x000000000500000d] recv fail, rtRet[228205]
[ERROR] GE(...): WaitChannelConnected: ErrorNo: 103901 Wait channel connected timeout, status=2, timeout=10000 ms
```

**排查路径**

1. 本端表现为 HIXL 连接超时和 RaSocket 接收失败。
2. 回查对端日志，可见 QP 分配在 EI0011 处失败。
3. 双端故障对象和时间线咬合，说明超时是 QP 分配失败的下游结果。
4. 排除网络不可达、HIXL 超时参数和进程退出，根因收敛到 Device 0 NPU 内存耗尽。

### 3. 问题根因

根因：Device 0 NPU 内存耗尽（EI0011），RoCE QP 资源申请失败，Channel 创建失败，对端等待 10000 ms 超时。本端超时链与对端 QP 分配失败链时间戳咬合，双端日志闭环。内存被什么占满需现场确认。

### 4. 解决方案

**临时规避**：清理无关占用进程，释放 Device 0 内存后重试。

**长期解决**：
1. 下调推理批处理 token 数 / KV Cache 规模 / 设备内存利用率 / 并行建链数量。
2. 重试前确认 Device 0 具备创建 sendCqDepth 2048 对应 QP 的可用资源。
3. 建链期间监控设备内存余量。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=HIXL,RoCE,HCCL；stage=connection；error_code=EI0011,103901；fault_type=resource_exhaustion,timeout
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-OOM-002：Host 可用内存不足导致 AOE 调优失败
### 1. 问题现象描述及版本信息

**1.1 问题描述**
在 Ascend 310B 上执行 AOE 模型调优并连接远端 NCS 服务。算子调优流程显示完成后触发内存检查失败，随后进程因 Bus error 异常退出；重复执行仍出现相同的内存不足提示。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | — |
| 芯片型号 | Ascend 310B |
| 训推框架版本 | AOE 调优 + 远端 NCS 服务 |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```text
Resource_Error_Insufficient_Host_Memory(WG00000): Memory check failed. Reason: The memory is insufficient. To ensure proper tuning, use a memory of 32 GB or more
Progress Show >>> [best_64_2048] Operator tuning process finished.
/dev/root 229G 50G 169G 23% /
Bus error
```

**排查路径**
1. 首先确认算子调优流程已经完成，排除任务未启动或算子编译立即失败。
2. 首错明确为 Resource_Error_Insufficient_Host_Memory，错误码语义指向 Host 可用内存检查失败。
3. df 输出显示根文件系统仍有 169G 可用，排除把磁盘容量误认为内存容量。
4. Bus error 发生在内存检查失败之后，是进程异常退出的次生表现，不作为首因。

### 3. 问题根因
AOE 调优所在 Host 的可用内存低于工具要求的 32GB，触发 Resource_Error_Insufficient_Host_Memory 内存检查失败，后续 Bus error 是进程异常退出表现。

### 4. 解决方案

**临时规避**：释放当前 Host 内存，或将 AOE 调优任务迁移到可用内存不低于 32GB 的主机后重试。

**长期解决**：
1. 在执行 AOE 前检查 Host 侧可用内存，不能以磁盘剩余空间或设备显存容量替代。
2. 为 AOE 调优进程设置明确的内存资源预算和监控。
3. 修复后复跑 AOE，确认不再出现 Resource_Error_Insufficient_Host_Memory。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=AOE,Host_memory,NCS；stage=tuning；error_code=WG00000；fault_type=resource_exhaustion,host_oom
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-OOM-003：Node 40 Normal zone 内存耗尽导致 SVM 映射失败
### 1. 问题现象描述及版本信息

**1.1 问题描述**
vLLM 推理服务在 KV transfer 压测时，Worker 创建 NPU Event 失败并抛出 OutOfMemoryError，底层错误码为 207001，随后 EngineCore 致命错误、服务退出，API 返回 500。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | — |
| 芯片型号 | A5 |
| 训推框架版本 | vLLM + Hierarchy KV transfer |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```text
Exception in (GPU, Hierarchy) transfer 42385: OutOfMemoryError(createEvent ... AclrtCreateEventWithFlag, error code is 207001)
Memory_Allocation_Failure(EL0004): Failed to allocate memory requested by UNKNOWN module.
svm_smm_remote_map: Smm mmap msg handle failed. (devid=0; devpid=20838; ret=6)
MapMem: Call driver api halMemMap failed, drvRetCode=6.
[ascend] [bbox] [bbox_oom_process 46] system oom happened, trigger exception!
page allocation failure: order , mode xcc0(GFP_KERNEL), nodemask=32-40
Node 40 Normal free kB boost kB min kB low kB high kB ... all_unreclaimable? yes
Node 40 ... pagetables kB ... mapped kB shmem kB
SLUB: Unable to allocate memory ... node 40: slabs: 20, objs: 320, free: 41
```

**排查路径**
1. 业务侧错误链为 transfer_async、event.record、AclrtCreateEventWithFlag 失败，错误码 207001。
2. 驱动日志显示 svm_smm_remote_map 失败、Smm map failed、halMemMap failed drvRetCode=6，说明上层事件创建失败是底层 SVM 映射失败的传播结果。
3. Kernel 日志出现 system OOM、page allocation failure，且 nodemask 指向 Node 32-40。
4. Node 40 的 Normal zone free 仅 1040kB，低于 min 水位 3284kB，all_unreclaimable=yes，同时页表占用约 500MB。
5. SLUB 无法在该 Node 分配 maple_node，最终导致 SVM 映射和 NPU Event 创建失败。由此排除单纯 NPU 显存不足。

### 3. 问题根因
A5 Node 40 处于 Normal zone 并与 OS 内核共用。vLLM 业务大量消耗该 Node 内存，页表占用约 500MB 后，剩余 free 仅 1040kB，低于内核最低水位 3284kB。内核尝试从 Node 40 分配 maple_node 时触发 page allocation failure 和 OOM，进而导致 SVM 映射失败、rtEventCreateExWithFlag 返回 207001，vLLM 服务崩溃。

### 4. 解决方案

**临时规避**：释放 Node 40 内存或降低业务内存占用后重启服务；短期可改绑到内存充足的 NUMA Node。

**长期解决**：
1. 将 Node 40 的 zone 类型调整为 Movable，隔离 OS 内核与 device 业务内存。
2. 重启系统使配置生效，并确认 OS 分配转向 Node 0、device 业务独占 Node 40。
3. 修复后复跑 KV transfer 压测，确认不再出现 page allocation failure、SVM ret=6 或 207001。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=vLLM,SVM,NUMA,OS_memory；stage=memory_mapping；error_code=207001,EL0004；fault_type=host_oom,watermark_exhaustion
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注
