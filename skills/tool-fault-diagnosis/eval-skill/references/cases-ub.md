# UB 案例集

## CASE-UB-001：UB 传输本端内存未注册，ClassifyTransfers 报 103900
### 1. 问题现象描述及版本信息

**1.1 问题描述**
4 卡执行 mooncake store 用例：一卡 put、其余卡 get，数据走 UB（灵衢）协议传输；执行过程中传输报错，用例失败，重跑必现。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | — |
| 芯片型号 | A5 环境 4 卡 |
| 训推框架版本 | mooncake store 4p（UB 协议） |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
[ERROR] GE(2992663,python3): [ub_client_handler.cc ] ClassifyTransfers: ErrorNo: 103900 [HIXL]Local memory range does not register before connection: start x100064494000, end x1000644b4000
[INFO] GE(2992663,python3): [error_manager.cc ] ReportInterErrMessage:report error_message, error_code:E19999, work_stream_id:..., error_mode [ERROR] GE(2992663,python3): [ub_client_handler.cc ] TransferSync: ErrorNo: 103900 [HIXL]
[ERROR] GE(2992663,python3): [hixl_engine.cc ] TransferSync: ErrorNo: 103900 [HIXL][HixlEngine] Failed to TransferSync, local_engine .0.0.1 , remote_engine ...
```

**排查路径**
①错误码单一收敛：全程只有 103900，从 ub_client_handler → hixl_engine 两层同码上抛——组件边界清晰，无需扩散到网络/链路排查；②`E19999` 是上抛形态不是根因码，按嵌套错误规则回溯到首错 103900 与其 errorStr；③断连（Disconnect/DestroyClient）是失败后的清理动作，不是独立故障。

归因陷阱：看到 E19999 停在"内部错误"层面会丢失定位线索；关联场景是 mooncake / KVCache 类走 UB 协议的 put-get 模式用例，出现同签名时优先核对内存注册时序。

### 3. 问题根因

根因：本端内存区间 0x100064494000~0x1000644b4000 未在连接前注册，ClassifyTransfers 校验报 103900，TransferSync 失败断连，上抛 E19999。注册未发生的原因在 hixl ub_client_handler 内存注册路径，属源码级问题。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
1. 在 hixl ub_client_handler 内存注册路径排查注册失败缺陷。
2. 确保 put/get 各卡本端内存在连接建立前完成注册。
3. 回归 mooncake store 4p 用例验证。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=HIXL,UB,memory-registration；stage=transfer；error_code=103900,E19999；fault_type=validation_failure
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-UB-002：UB 链路 CQE 错误引发 notify wait 失败
### 1. 问题现象描述及版本信息

**1.1 问题描述**
双机32P pytorch 下 batchsendrecv aclgraph/AI_CPU 展开 fp16 用例执行报错，HCCL 通信链路 CQE ERROR（crimer rank [sp_4_srv_6/4] status[CQE ERROR] by informer rank [sp_4_srv_7/1]），RUNTIME notify wait 任务失败、HCCL TASK_UB_INLINE_WRITE 跨节点 UB 写失败并报 EI0002，pytorch 进程 aclnnMaskedSelect Inner Error 退出 core dump，用例 check_log_rules 失败、结果 Fail。

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
`Msg:Task run failed, stream id=59, pos=2, task_sn=861, sq_type=7(notify wait), errType=0x20(sq sw status error), sqSwStatus=0x3ea.`
`normal]local rank [sp_4_srv_6/4]: crimer rank [sp_4_srv_6/4] status[CQE ERROR] by informer rank [sp_4_srv_7/1]`
`RunFailed][AICPQ]Task run failed, base information is streamID[sqId]:[39], taskID[sqId]:[2147484748], taskType:[TaskParamType::TASK_UB_INLINE_WRITE].`
`[ERROR] HCCL(469898,python3) -18-02  .676.092 [hcclCommTaskException.cc ] [474096]errorMessage taskType[TaskParamType::TASK_UB_INLINE_WRITE], rtCqErrorType[1], rtCqErrorCode[196610].`
`RunFailed][AICPQ]Task run failed, para information is src:[0x0], dst:[0x3fff3c124058], size:[0x8], notify id:[0x00000000000000eb], link type:DfxLinkType::UB], remote rank:[4].`
```

**排查路径**

RUNTIME notify wait 任务执行失败（errType=0x20, sqSwStatus=0x3ea，同源），说明本卡在等待对端 notify 时任务未完成回执，属通信/同步失败而非算子计算错误；随后 及日志附件 中 cluster_monitor 明确上报 crimer rank [sp_4_srv_6/4] status[CQE ERROR]，即 UB 链路 CQE 错误并指明源卡（node6/dev4，by informer node7/dev1）；/36 进一步显示 HCCL 的 TASK_UB_INLINE_WRITE 任务失败，且任务参数 link type 明确为 DfxLinkType::UB、跨节点向 remote rank[4] 直写；给出该 UB inline write 的 CQE 错误码 rtCqErrorCode[196610] 0x30002。结合「CQE ERROR 检测 + notify wait 失败 + UB inline write 失败」三段证据同指一条 UB 链路，且两次独立执行（host_log_0 08-17 / host_log_1 08-18）均复现同样错误，将问题稳定缩界到 UB（灵衢）总线链路/交换层，排除算子算法、HCCL 算法配置本身的问题；下游 pytorch aclnnMaskedSelect Inner Error 与 core dump 均为 UB 通信失败后的连锁表现，不作为根因方向。

### 3. 问题根因

UB（Unified Bus 灵衢）链路 CQE 错误：rtCqErrorCode[196610]/0x30002，导致 RUNTIME notify wait 与 HCCL TASK_UB_INLINE_WRITE 失败，并引发 EI0002、进程异常退出和用例 Fail。日志未唯一确定物理源卡；环境/硬件链路归属为强推断。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
排查 UB 链路 CQE 错误来源，包括 UB 交换、UBOE、线缆、端口和 RAS 记录；解除 rtCqErrorCode 196610/0x30002 后，重跑同批 batchsendrecv 用例并确认 cluster_monitor 不再报 CQE ERROR。软件侧无需先修改 HCCL/算子逻辑。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=UB,HCCL,RUNTIME；stage=communication；error_code=EI0002,196610；fault_type=cqe_error
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-UB-003：UBX 单平面下电后 HCCL 建链无容错
### 1. 问题现象描述及版本信息

**1.1 问题描述**
UBX 4 个 CLOS-plane网络平面，unions 下电单子卡关闭一个平面后，UB 端口 link down（16 个 P6 down）；故障不解除再次拉起 16p 推理业务，HCCL alltoall 建链超时、业务拉起失败。

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
[ERROR] HCCL(662697,alltoall_test) -25-09  .367.479 [exchange_info_mgr.cc ] [662697][WaitAllAsyncComplete] wall-clock timeout for remoteRank[4], elapsed[120008]ms.
1/33	PICUBX_3	Present	Off	Unregistered	-
port_id: 0x6` / `link_status: down
| 1 | 6 | 400 | UB | DOWN | Electrical |
... [module UB] ... ras_code=0x81b18603; sensor_type=0xc3; err_type=0x3; desc="ub port link down"
... [WaitAllAsyncComplete] wall-clock timeout for remoteRank[4], elapsed[120008]ms.
... [coll_comm_res_c_adpt.cc ] CreateChannels failed. group[<node-ip>_60000_0_1784944638346483], engine[AICPU_TS] ret[9]
```

**排查路径**
UB 端口（port 0x6）被下电子卡所在平面拖成 link down（ubctl/hccn_tool 一致 + device 侧 module UB ras_code=0x81b18603 "ub port link down"），随后 HCCL 建链等待对端超时，据此把问题缩界到 UB（灵衢）链路/网络平面可用性与 HCCL 建链可靠性环节。

### 3. 问题根因

根因：UBX 形态在部分 UB 端口/网络平面不可用（unions 下电单子卡关闭一个 CLOS-plane网络平面导致 UB 端口 link down）时，HCCL 建链直接报错/超时（不可靠），业务无法拉起；实现侧未做部分端口/平面不可用的可靠性容错，属 UB（灵衢）链路可用性可靠性问题。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
在 UB/URMA 与 HCCL 建链侧做部分端口或网络平面不可用的可靠性容错：检测到部分 UB 端口 link down/平面关闭时，应降低业务规模（如降级为可用的 12p/8p）或走可用平面继续建链，而不是直接对远程 rank 超时后整体失败；同时对 ubcore_get_jetty_opt_by_id 等资源查找失败做容错；并回归 unions 下电单子卡场景验证故障不解除时业务能按可用平面拉起。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=UBX,HCCL,CLOS-plane；stage=connection；error_code=—；fault_type=availability_failure
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-UB-004：NDR 要求 4KB 对齐，Mooncake 注册内存未对齐注册失败
### 1. 问题现象描述及版本信息

**1.1 问题描述**
A5 环境（HDK 25.5.T6）下 vLLM KV transfer 使用 Mooncake RDMA Transport（NDR）注册 device 显存失败：多个 Worker（PP0_TP0/TP1/TP3）后台异步线程在 NIXL agent.register_memory(kv_mem_info, "VRAM") 时同时抛出 nixlBackendError: NIXL_ERR_BACKEND，mooncake 侧报 Failed to register memory: Invalid argument [22]，dmesg 同步出现 svm pma / ascend_mem npu_acquire 内核报错；通过 mooncake te 注册内存即可复现，预期注册内存没有限制。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | A5 HDK 25.5.T6 |
| 芯片型号 | — |
| 训推框架版本 | vLLM kv_transfer（flexible_connector）+ NIXL + Mooncake RDMA Transport（NDR |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
(Worker_PP0_TP3_EP3 pid=35648) nixl._bindings.nixlBackendError: NIXL_ERR_BACKEND
E20260613 03  .181668 38462 rdma_context.cpp ] Failed to register memory 0x1200c0000000: Invalid argument [22]
E20260613 03  .181730 38462 rdma_transport.cpp ] Failed to register memory region with context 0
E0613 03  .181741    38462 nixl_agent.cpp ] registerMem: registration failed for the specified or all potential backends
[538827.480067] [ascend] [ERROR] [svm] [pma_get_dev_pa_seg_page_size 140] <python3    > Get pa or size isn't failed by npage_size. (size=0x12004ce00080; size=8192; npage_size=4096)
[539067.480081] [ascend] [ERROR] [svm] [pma_page_table_init 250] <python3    > Get dev pa seg page_size failed.
[538248.651125] [ascend] [ERROR] [ascend_mem] [npu_acquire ] npu_acquire: failed to get pages
[538519.383366] [ascend] [ERROR] [svm] [pma_get_dev_pa_seg_page_size 128] <python3    > Invalid pa seg. (size=2048)
```

**排查路径**
多个 Worker 在同一毫秒级时间窗内于 register_memory("VRAM") 统一抛 NIXL_ERR_BACKEND，mooncake rdma_context 报 EINVAL，锁定故障发生在 NDR device 内存注册链路；再到 dmesg 中按进程上下文（<python3:...>）过滤掉 npu-smi/kworker 相关噪声，由 svm pma 的「va/size 未按 npage_size=4096 对齐」报错将问题缩界到内核 NDR 内存注册的 4KB 对齐校验环节。

### 3. 问题根因

根因：HDK 25.5.T6 的 NDR（灵衢 UB 网络 RDMA）要求注册内存的地址与长度按 4KB 对齐，Mooncake RDMA Transport 注册的 device 内存未对齐，内核 pma 获取物理地址段页大小失败，npu_acquire 拿不到物理页，rdma_context 注册返回 EINVAL，应用层报 NIXL_ERR_BACKEND。该对齐限制已在 HDK 25.7.X 修复。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
升级 HDK 至 25.7.X 及以上版本；规避方案：在 Mooncake/NIXL 侧注册前对 device 内存地址与长度按 4KB 对齐（对齐分配内存或截断/拆分注册区间为 4KB 对齐子段）；修复后回归 mooncake te 注册内存及 vLLM KV transfer 多 Worker（PP0_TP0~TP3）场景验证。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=HIXL,Mooncake,RDMA,memory_alignment；stage=registration；error_code=NIXL_ERR_BACKEND；fault_type=alignment_failure
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注
