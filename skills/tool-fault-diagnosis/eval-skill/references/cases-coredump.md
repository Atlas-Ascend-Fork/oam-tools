# coredump 案例集

## CASE-CORE-001：通信域析构重复调用 RsRdevDeinit 导致段错误
### 1. 问题现象描述及版本信息

**1.1 问题描述**
集合通信结束后通信域进入进程退出析构阶段，主线程收到SIGSEGV，崩溃调用栈位于RDMA资源释放流程，并最终落在ibverbs的保护域释放调用路径上。

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

```text
WRITE of size 128 at 0x7fff1603a580 thread T0
#2 0x7f... in optiling::PromptFlashAttentionTilingData::PromptFlashAttentionTilingData()
/git/ops-transformer/attention/prompt_flash_attention/op_host/prompt_flash_attention_tiling_v2.cpp
at /git/ops-transformer/attention/prompt_flash_attention/op_host/prompt_flash_attention_tiling_v2.cpp
```

**排查路径**

1. ASAN 报告栈内存写越界。
2. 崩溃帧位于 PromptFlashAttentionTilingData 构造链路。
3. 源码位置对应 DoOpTiling，且关闭 ASAN 后仍同位置崩溃。

### 3. 问题根因

RdmaHandleManager与HccpPeerManager分别析构并重复调用RsRdevDeinit，导致ibverbs so先被一个析构流程关闭，另一个流程随后调用已失效的ibverbs函数指针，在RsIbvDeallocPd处发生段错误。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
统一RdmaHandleManager与HccpPeerManager对HCCP/RDMA资源及ibverbs so的所有权和析构顺序，避免两个析构流程重复执行RsRdevDeinit；可通过集中式反初始化、引用计数或幂等保护保证所有RsIbvDeallocPd等ibverbs函数调用完成后再关闭so，并在so已关闭时禁止后续资源释放调用。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=HCCL,RDMA,ibverbs；stage=destructor；error_code=—；fault_type=double_deinit
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-CORE-002：跨版本通信域类型不兼容导致运行时 coredump
### 1. 问题现象描述及版本信息

**1.1 问题描述**
在A5场景下，使用不同版本的HCCL与HCOMM组合运行，初始化通信域后调用通信域相关接口，进程在运行时发生coredump并崩溃。

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
运行时不兼容，HCCL仓会直接coredump
HcclGetRankId(HcclComm, 仅支持Hccl::Communicator
HcclGetRankId(HcclComm, 仅支持hccl::HcclComm
```

**排查路径**

和27显示接口仅支持Hccl::和33显示接口仅支持hccl::HcclComm；这排除了普通业务调用失败，聚焦到HCCL/HCOMM通信域ABI或对象类型不一致。日志中的兼容方案还明确涉及算子入口判断hcomm版本，进一步说明问题边界是跨版本接口兼容，而非设备或链路故障。

### 3. 问题根因

跨版本组合使HcclComm接口在Hccl::Communicator与hccl::HcclComm两种不兼容通信域类型之间发生错配，接口直接按错误类型访问对象，最终触发运行时coredump。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
统一A5/A3对外通信域类型，优先统一到hccl::HcclComm，并确保HCCL与HCOMM使用匹配版本；在无法立即统一的兼容场景下，在算子入口识别hcomm版本并将新版本与330老版本组合路由到兼容的HcclAllReduceInner等实现，避免接口按错误类型直接访问。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=HCCL,HCOMM；stage=runtime；error_code=—；fault_type=type_mismatch
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-CORE-003：PromptFlashAttentionTilingData 栈对象过大导致栈溢出

### 1. 问题现象描述及版本信息

**1.1 问题描述**

运行 prompt_flash_attention 算子的 Tiling 单元测试时，进程在 DoOpTiling 执行过程中触发 AddressSanitizer 栈缓冲区溢出并终止；禁用 ASAN 后同一位置继续发生 Segmentation fault。InferShape 测试正常通过，故障集中在 Tiling 路径。

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

```text
WRITE of size 128 at 0x7fff1603a580 thread T0
#2 0x7f... in optiling::PromptFlashAttentionTilingData::PromptFlashAttentionTilingData()
/git/ops-transformer/attention/prompt_flash_attention/op_host/prompt_flash_attention_tiling_v2.cpp
at /git/ops-transformer/attention/prompt_flash_attention/op_host/prompt_flash_attention_tiling_v2.cpp
```

**排查路径**

1. ASAN 报告栈内存写越界。
2. 崩溃帧位于 PromptFlashAttentionTilingData 构造链路。
3. 源码位置对应 DoOpTiling，且关闭 ASAN 后仍同位置崩溃。

### 3. 问题根因

PromptFlashAttentionTilingData 体积过大，在 PromptFlashAttentionTilingV2::DoOpTiling 中作为栈对象构造时耗尽栈空间并发生栈缓冲区溢出。

### 4. 解决方案

**临时规避**：优先按根因临时调整配置或回退可疑变更；无通用规避时保持现场采集完整日志。

**长期解决**：
1. 避免在 DoOpTiling 栈上直接分配过大的 PromptFlashAttentionTilingData；将其改为安全的堆分配或其他受控存储方式，并检查结构体布局及成员规模，确保构造和后续序列化访问不会超出可用空间。修复后应重新执行 Tiling 测试并在 ASAN 下验证无 stack-buffer-overflow，同时回归 InferShape 测试。
2. 修复后按原故障场景复测，确认首错消失且关键指标恢复正常。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=PromptFlashAttention,tiling,stack；stage=compile；error_code=—；fault_type=stack_overflow
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-CORE-004：Context 清理残留 Model 触发已析构的 ModelDestroyCallback 崩溃
### 1. 问题现象描述及版本信息

**1.1 问题描述**
进程退出并进入 Runtime 析构阶段时，清理 Context 中残留 Model 的链路继续执行 ModelDestroyCallback；同时 callback 执行过程中出现 HCOMM 找不到对应 model 记录的错误，Runtime 可能沿该 callback 路径发生 coredump。

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
Runtime::~Runtime() -> Context::TearDownForFinalRelease() -> Context::TearDownModelsOnContextTearDown() -> Context::DeleteModelOnContextTearDown() -> CaptureModel::TearDown() -> Model::TearDown() -> Model::ModelDestroyCallback()：明确显示 Run...
func [%p] mdlDestroy callback start：证明 Model destroy callback 已被实际拉起执行。
modelID[32] is not record：证明 callback 执行时 HCOMM 侧已不存在对应 modelID 记录，体现析构顺序或生命周期失配。
```

**排查路径**
日志先显示 Runtime 析构进入 Context/Model 清理链路，再显示用户 ModelDestroyCallback 已启动并报 HCOMM modelID 无记录。由此将故障定界到 Runtime 析构期间触发外部 Model destroy callback，而非普通模型运行或编译阶段。

### 3. 问题根因

根因：Runtime 析构时 Context 清理残留 Model 触发了用户注册的 ModelDestroyCallback，而 callback 所在 so、私有数据或依赖状态可能已经析构，导致 callback 执行产生 coredump，并引发 HCOMM modelID 记录缺失。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
在 ModelDestroyCallback() 入口判断 Runtime 是否处于 exiting 状态；Runtime 析构阶段跳过用户 destroy callback并记录 warning、返回成功，避免继续访问已析构的 callback so、私有数据和 HCOMM 状态。显式 rtModelDestroy、rtCtxDestroy、rtDeviceReset 等非 exiting 路径继续保持原有 callback 语义；长期应将 direct-exit 与完整 Context/Model 业务销毁链路分流。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=Runtime,Context,ModelDestroyCallback；stage=cleanup；error_code=—；fault_type=coredump,callback_lifetime
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注
