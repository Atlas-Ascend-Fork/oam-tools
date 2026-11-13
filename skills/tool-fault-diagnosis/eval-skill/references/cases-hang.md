# 进程卡住 案例集

## CASE-HANG-001：SQ/CQ 资源耗尽且解绑失败导致卡住
### 1. 问题现象描述及版本信息

**1.1 问题描述**
运行 ACL_ACLGRAPH_PATH_0001 期间，设备初始化成功后出现通道分配失败和模型流解绑失败，随后模型执行返回错误，进程最终卡住无响应。

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
E10002: The wait execution of the Notify register times out
HCCL CheckChannelParam / CreateChannels failed
worker0 与其他 rank 的通信算子数据量或数据类型不一致
```

**排查路径**

1. 先定位首个异常 rank，而不是把全量超时视为根因。
2. 对比各 rank 的通信算子下发记录。
3. 发现 worker0/device0 与其他 rank 在数据量和数据类型上不一致。
4. 该不一致导致 HCCL 参数校验失败，其余 rank 等待并最终卡死超时。

### 3. 问题根因

高并发导致 SQ/CQ 资源耗尽；模型维护流程尝试解绑仍在运行的 SQ，解绑失败后资源无法释放，新分配持续失败，最终进程卡住。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
降低并发线程数与每个模型的 stream 数，使总 SQ/CQ 需求不超过设备上限；修正执行后的同步逻辑，确保模型包含的所有 stream 完成后再进入维护和解绑；资源不足时避免回收仍在运行的 SQ，应等待其完成或安全返回资源不足；同时在错误模式下优先停止后续重试，并验证模型销毁后 SQ/CQ 是否真正释放。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=RUNTIME,SQ,CQ；stage=resource_cleanup；error_code=—；fault_type=resource_exhaustion,hang
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-HANG-002：fixed-rank RDMA 建链等待未设 timeout
### 1. 问题现象描述及版本信息

**1.1 问题描述**
运行 A2 上的 SHMEM RDMA 算子时，设备初始化、内存预留与注册以及前置组同步均完成，但程序在后续 RDMA socket 建链阶段无响应，进程持续等待且不退出。

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | — |
| 芯片型号 | A2 |
| 训推框架版本 | — |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
2026-04-29 14  .218005 info 227987 pid[227987] [SHM_SHMEM device_rdma_transport_manager.cpp ] 0 open device with TransportOptions(rankId=0, count=2, protocol=3, role=0, nid=10002, iptype=0) success.
2026-04-29 14  .235725 debug 228007 pid[228007] [SHM_SHMEM device_rdma_transport_manager.cpp ] 1 register MR result=RegMemResult(size=1080033280)
2026-04-29 14  .236874 info 228007 pid[228007] [SHM_SHMEM store_net_group_engine.cpp ] groupBarrier successfully, key: SHM_(0)_S_0_2_BW, size: 2, timeCostUs: total(463) add(106) getStatus(347)
2026-04-29 14  .237288 debug 228007 pid[228007] [SHM_SHMEM transport_manager.cpp ] ConnectWithOptions now connected=0
2026-04-29 14  .237380 debug 228007 pid[228007] [SHM_SHMEM fixed_ranks_qp_manager.cpp ] 1 add connecting server HccpSocketConnectInfo(socketHandle=0xaaaafccc46f0, remoteIp=<node-ip>, port=10002)
2026-04-29 14  .237774 debug 228086 pid[228007] [SHM_SHMEM fixed_ranks_qp_manager.cpp ] 1 begin wait connections, size=1
```

**排查路径**
日志显示设备打开、RDev 初始化、内存注册和 Barrier 均成功，故障不在设备初始化或共享内存准备阶段。随后 fixed-rank QP 管理器进入连接等待且没有后续完成或失败日志，问题收敛到 RDMA socket 建链等待路径。

### 3. 问题根因

根因：fixed-rank RDMA socket 建链等待未设置有效 timeout，也缺少连接失败诊断和退出处理，底层连接异常时因此陷入永久等待。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
为 fixed-rank RDMA socket/QP 建链设置真实有效且可配置的超时时间；在连接超时或底层连接异常时记录远端 IP、端口、rank、socket/QP 状态及错误码，执行连接清理并向上层返回失败，避免无期限阻塞。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=shmem,RDMA,socket；stage=connection；error_code=—；fault_type=hang
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-HANG-003：AIV 模式下多通信域并行违反 HCCL 约束
### 1. 问题现象描述及版本信息

**1.1 问题描述**
XDS 推理框架适配 DSV3.2 时在 Atlas 900 A3 SuperPoD 上运行 AllGather 通信算子遇到 AIV timeout 后中断，用户组网 D 实例使用 2 个节点总共 32 个 Device，其中 8 个 Device 发生报错

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
[ERROR] RUNTIME(1344,) -28-15  .554.370 [da Vinci_kernel_task.cc ]2178 PreCheckTaskErr:Kernel task happen err, retCode=0x30, [vector core timeout].
[ERROR] RUNTIME(1344,) -28-15  .554.370 [da Vinci_kernel_task.cc ]2178 PreCheckTaskErr:Kernel task happen err, retCode=0x30, [vector core timeout].
[ERROR] RUNTIME(1344,) -28-15  .554.950 [da Vinci_kernel_task.cc ]2178 PrintErrorInfoForDaVinciTask:Aicore kernel execute failed, device_id=5, stream_id=11, task_id=43241, fault kernel_name=aiv_all_gather_int32_t
[ERROR] HCCL(1344,) -28-15  .556.863 [task_exception_handler.cc ] [2178][TaskExceptionHandler][PrintCommAivInfo] multi groups include aiv alg, may cause execution stuck. has aiv group count[2]
[ERROR] HCCL(1344,) -28-15  .556.880 [task_exception_handler.cc ] [2178][group_name_157] [group_name_7]
[INFO] HCCL(1108,) -28-14  .877.124 [externalinput.cc ] [2082]environmental variable HCCL_OP_EXPANSION_MODE is [AIV], aicpuUnfold[1], aivMode[1], enableFfts[1]
该配置项不支持多通信域并行的场景（因为不支持多个通信域同时配置为“AIV”模式），否则可能会导致不可预期行为
```

**排查路径**

现象为 32 个 Device 中 8 个报 Allgather aiv timeout → 检查 plog 首报错定位到 RUNTIME da Vinci_kernel_task.cc retCode=0x30 [vector core timeout]，fault kernel_name=aiv_all_gather_int32_t，确认为 AllGather AIV 算子 timeout → 排除单纯硬件/AI Core 异常：HCCL task_exception_handler.cc 主动打印 multi groups include aiv alg, may cause execution stuck. has aiv group count[2]，明确指向多通信域并行 AIV 算法导致卡死 → 列出具体 AIV 组名 [group_name_157] [group_name_7]，确认为 2 个通信域同时配置 AIV → 查环境变量日志 externalinput.cc 显示 HCCL_OP_EXPANSION_MODE is [AIV]，确认作业配置为 AIV 展开模式 → 排除 HCCL 代码 Bug：查阅官方文档约束，AIV 配置项不支持多通信域并行场景，否则可能导致不可预期行为 → 与用户确认实际使用场景为 AIV + 多通信域并行，违反约束 → 定界为环境配置问题，非硬件、非 HCCL 代码缺陷

### 3. 问题根因

在集合通信配置编排展开位置配置为 AIV 时存在多个通信域并行的情况，违反了 HCCL 在 AIV 模式下的使用约束，导致执行卡死和超时。用户设置了环境变量 HCCL_OP_EXPANSION_MODE 为 AIV，但在该模式下不允许存在多个通信域并行，日志显示有 2 个 aiv group（group_name_157、group_name_7）同时存在。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
建议用户按照符合约束的方式使用，优先 unset HCCL_OP_EXPANSION_MODE 环境变量，使能 HCCL 通信算法编排展开位置为 AI_CPU 模式

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

## CASE-HANG-004：数据加载代码死循环，DataLoader 残留进程占显存致 HCCL 初始化失败
### 1. 问题现象描述及版本信息

**1.1 问题描述**
12 节点 96 卡分布式训练，95 张卡报错 EZ9903 (rtKernelLaunchWithHandleV2 fail)，1 张卡（worker1 device7）未报错但主进程退出且显存未释放，重启任务后报 E30001 提示残留进程占用设备

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | 8.0.rc3 |
| HDK 版本 | 23.0.3 |
| 芯片型号 | 910B3 |
| 训推框架版本 | PyTorch 2.1 |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
[E compiler_depend.ts ] call failed, detail:EZ9903: [PID: 1157] 2025-03-28-01  .823.868 rtKernelLaunchWithHandleV2 fail
The error from device(chipId , dieId ), serial number is 3, event wait timeout occurred during task execution
Failed to submit kernel task, retCode=0x7150059.[FUNC:LaunchKernelSubmit][FILE:context.cc][LINE ] / rtKernelLaunchWithHandleV2 failed: 107020
RuntimeError: create:build/CMakeFiles/torch_npu.dir/compiler_depend.ts HCCL function error: HcclCommInitRootInfo(numRanks, &rootInfo, rank, &(comm->hcclComm)), error code is 7
E30001 (PID: 68164) 2025-03-28 09  .577.018 Failed to initialize the HCCL process. Reason: Maybe the last training process is running. / tsd client wait response fail, hostpid , device response code[1]. unknown device error
| 7 910B3 | OK | ... | 0 / 0 56312 / 65536 | / No running processes found in NPU 7
ma-user 5939 1 0 12 ? 01  <home>/anaconda3/envs/PyTorch-2.1.0/bin/python3.9 -u <业务模块>/train.py
Thread 0xFFFF91EC5010 (active+tail): "MainThread" _randbelow_with_getrandbits (random.py ) randrange (random.py ) randint (random.py ) random_half_area_box_on_mask (<业务模块>/mask.py ) _read_img_mask (<业务模块>/mask.py...
```

**排查路径**
从 plog 查找首报错时间及错误码，发现 fftsplus task timeout 错误码 EZ9903/E1999，确认首报错为任务超时 → 排查是否全量报错，对比各卡状态，发现 worker1 device7 未报错但 npu-smi 显示其显存占用 56312MB 且无运行进程，存在残留进程占用显存 → 用户未重启直接重跑任务，出现 EJ0001/E30001 'Maybe the last training process is running'，验证 device 上有残留进程 → 复现问题并 hold 住现状，使用 ps -ef 查找残留进程，发现 PID 5939 进程父进程为 1 运行时间长达 1 小时 24 分，定位到可疑僵尸进程 → 使用 py-spy dump 查看可疑进程堆栈，堆栈显示进程停留在 random_half_area_box_on_mask 函数 (<业务模块>/mask.py ) 处于死循环 → 确认为用户代码逻辑死循环导致

### 3. 问题根因

根因：用户训练代码中数据加载部分存在死循环逻辑（random_half_area_box_on_mask），导致 DataLoader 进程卡死无法退出。主进程退出后该残留进程仍占用 NPU 显存，导致后续任务初始化 HCCL 失败或超时。具体代码逻辑在 ratio==1 时调用 random_half_area_box_on_mask 进入死循环。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
定位到 <业务模块> 中 random_half_area_box_on_mask 调用处；注释掉涉及死循环的代码段（if ratio == 1 分支）；重新拉起训练任务验证无报错；遇 HCCL 初始化失败需排查是否有残留进程占用设备并清理

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=DataLoader,HCCL,process_lifecycle；stage=initialization；error_code=EZ9903；fault_type=resource_leak,timeout
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-HANG-005：MoXing 并发下载单文件挂死，触发通信 event wait 超时
### 1. 问题现象描述及版本信息

**1.1 问题描述**
18 节点 144 卡业务，超时时间配置为2h，重新拉起后业务在 09-18-20 分卡死，两小时后 plog 全量上报 event wait 超时。环境 A, HDK 23.0.RC2, CANN 6.3.RC2, mindspore 2.1.0

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | 6.3.RC2 |
| HDK 版本 | 23.0.RC2 |
| 芯片型号 | 910A |
| 训推框架版本 | mindspore 2.1.0 |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
time: 2025-09-18 19  . begin download dataset, path is obs://<业务数据集>/<文件>, size is 304.49 MB
time: 2025-09-18 19  . Dataset download succeed! / time: 2025-09-18 19  . Dataset download succeed!
[EVENT] RUNTIME(1678,python) -18-21  .672 [engine.cc ] 6054 ReportTimeoutProc: report timeout! streamId=3, taskId=5, pendingTaskNum=4, reportCount=2703
[ERROR] RUNTIME(1678,python) -18-22  .400.822 [engine.cc ]6054 ReportExceptProc:Real task exception! device id=2, stream id=54, task id=2, task type=3 (EVENT_WAIT)
[ERROR] RUNTIME(1678,python) -18-22  .400.860 [engine.cc ]6054 ReportExceptProc:Task exception! device id=2, stream id=3, task id=13(MODEL_EXECUTE), failuremode =1, retCode=0x91
time="2025-09-18T22  +08 " level=info msg="NPU startup not caught within 3 hours" file="watch_routine.go "
mox.file.copy_parallel(src_url=src_data_url, dst_url=cache_url)
用户使用MoXing中的copy_parallel函数并发地下载单个大文件，导致了多进程同时读取该大文件进而卡死，下载失败。需要使用copy函数代替copy_parallel下载单个大文件数据
```

排查路径 节点144卡业务 09-18-20 卡死，2h 后 plog 全量上报 event wait 超时 → 分析训练日志，发现报错前 begin download dataset 和 Dataset download succeed 存在不成对打印（19  那次只有 begin 无 succeed），与用户确认正常日志这两条打印成对，定界到有一次下载数据操作未成功 → 排查 OBS 远程存储网络无异常 → 分析业务代码确定在做 mox.file.copy_parallel 时失败 → 联系 MoXing 同事分析，反馈用户使用 copy_parallel 并发下载单大文件导致多进程同时读取大文件卡死，且 MoXing 版本过低 → 建议 copy_parallel 适用于文件夹下载、copy 适用于单文件下载，需升级 MoXing 版本并纠正用法 → 用户升级 MoXing 后问题解决

**排查路径**

1. begin download dataset 后没有 Dataset download succeed。
2. event wait 超时是数据下载卡住后的传播结果。
3. 业务代码使用 copy_parallel 并发下载单个大文件。
4. 单文件应使用 copy。

### 3. 问题根因

根因：MoXing 版本过低，且业务错误使用 mox.file.copy_parallel 并发下载单个大文件，导致多进程同时读取该大文件进而卡死、数据集下载未完成，最终触发通信 event wait 超时。用户环境使用 OBS 远程存储，旧版本 MoXing 在处理特定下载任务时出现挂死。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
检查当前 MoXing 版本；升级 MoXing 到最新版本；纠正用法：copy_parallel 适用于文件夹下载、copy 适用于单文件下载（超过5G默认走多并发）；重试训练任务

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=moxing,OBS,DataLoader；stage=data_loading；error_code=—；fault_type=hang,timeout
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-HANG-006：GridSampler3DGrad 执行超阈值，tsdaemon 杀 aicpu 进程
### 1. 问题现象描述及版本信息

**1.1 问题描述**
业务打屏日志显示 EL9999: Inner Error! halQueueDestroy failed，HDC 通信报 ret(25)，多节点 send/recv 失败，Device status failure ret=118554641，AICPU 算子 GridSampler3DGrad 执行超时被 tsdaemon 杀掉 aicpu-sd 进程

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | — |
| HDK 版本 | — |
| 芯片型号 | Ascend NPU 多卡服务器（serverid <node-ip>，16 rank 分布式训练） |
| 训推框架版本 | 软件版本: Ascend Toolkit（/usr/local/Ascend/ascend-toolkit/latest），MindSpore |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
[ERROR] CECPU[20156,aicpu_scheduler] -23-03  .776 [aicpusd_monitor.cpp ][HandleTaskTimeOut][tid ] Send timeout to tsdaemon, tsdaemon will kill aicpu-sd process, thread index[1], op name=[GridSampler3DGrad], serialNo=63...
The first error on serverid[<node-ip>] deviceid[0] [rank8]. Error time[2023-09-23-03  .393022]
[ERROR] HCCP(13996,python) -23-03  .393.022 [ra_hdc.c ]tid ,hdc_send_recv_pkt_recv(101) : [recv]hdc_send_recv_pkt]HDC recv msg err ret(25)
[ERROR] RUNTIME(14004,python) -23-03  .539.117 [engine.cc ]14263 ReportStatusFailProc:Device status failure, ret=118554641,start exception...
[ERROR] DRV(14004,python) -23-03  .402.982 [ascend][curpid: 14004, 44646][drv][event-sche][halEschedSubmitEventSync 219]failed. (ret=16; event_id=4; gid=16; tid=0; timeout=5000ms; subevent_id=2746)
[ERROR] RUNTIME(14004,python) -23-03  .403.210 [api_c.cc ]44646 rtMemQueueQueryInfo:ErrCode=507899, desc=[driver error:internal error], InfoCode=0X70200 / module_name=EE8888
EL9999: Inner Error! EL9999 [drv api] halQueueDestroy failed: deviceId=6, qid=1, drvRetCode=7. rtMemQueueDestroy execute failed, reason=[driver error:internal error] retCode is 507899
[ERROR] HCCL(14004,python) -23-03  .890.464 [adapter_hccp.cc ][14004][333111][hrtRaGetCqeErrInfo]Get Cqe err info failed
```

**排查路径**
parse_pkg_hccn.py process_log 分析日志，脚本输出首错 serverid[<node-ip>] deviceid[0] rank8，Error time 2023-09-23-03  .393，伴随 HCCP HDC recv/send err ret(25)，定界到通信层报错 → 深入分析首错设备 device-app 日志，过滤非 HCCP 错误，发现 Device status failure ret=118554641、halEschedSubmitEventSync failed ret=16 timeout=5000ms、EL9999 报错，定界到 EL9999 是衍生错误，底层存在设备状态异常和事件同步失败 → 查找最早的算子执行日志对比时间戳，在 device-4 日志中发现 GridSampler3DGrad 算子 03  .776 报 HandleTaskTimeOut，早于 EL9999 出现时间 03  ，定界到 AICPU 算子超时是根因 → 获取超时算子 dtype 和 shape 准备单算子复现验证 → 确认 GridSampler3DGrad 算子在该场景下必然超时非偶发

### 3. 问题根因

根因：AICPU 算子 GridSampler3DGrad 在该业务场景下执行超过 2.8s 超时阈值（timeOut ），必然超时非偶发故障，触发 tsdaemon 杀死 aicpu-sd 进程，引发设备状态异常（Device status failure ret=118554641）、驱动事件同步超时（halEschedSubmitEventSync ret=16 timeout=5000ms）、队列查询/销毁失败（rtMemQueueQueryInfo ErrCode=507899/halQueueDestroy drvRetCode=7），最终级联为 HCCL 通信报错 EL9999 与 HDC recv/send err ret(25)。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
修改模型或算子配置，不使用 AICPU 算子执行 GridSampler3DGrad；寻找替代算子实现或优化算子逻辑以避免超时

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=GridSampler3DGrad,AICPU,tsdaemon；stage=runtime；error_code=507899,EL9999；fault_type=timeout,process_kill
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-HANG-007：worker0 通信算子下发不一致，HCCL 参数校验失败引发卡死

### 1. 问题现象描述及版本信息

**1.1 问题描述**

<业务> 40 卡强化学习作业，训练日志上报 E10002: The wait execution of the Notify register times out

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
E10002: The wait execution of the Notify register times out
HCCL CheckChannelParam / CreateChannels failed
worker0 与其他 rank 的通信算子数据量或数据类型不一致
```

**排查路径**

1. 先定位首个异常 rank，而不是把全量超时视为根因。
2. 对比各 rank 的通信算子下发记录。
3. 发现 worker0/device0 与其他 rank 在数据量和数据类型上不一致。
4. 该不一致导致 HCCL 参数校验失败，其余 rank 等待并最终卡死超时。

### 3. 问题根因

通信算子下发不一致，worker0 的 device0 下发的通信算子数据量及数据类型与其他节点不一致，导致 HCCL 集合通信前参数校验失败，引发卡死超时。

### 4. 解决方案

**临时规避**：优先按根因临时调整配置或回退可疑变更；无通用规避时保持现场采集完整日志。

**长期解决**：
1. 梳理业务逻辑，确认各 Rank 执行的代码分支；修改代码，保证同一通信域内所有节点下发的通信算子数据量和数据类型一致
2. 修复后按原故障场景复测，确认首错消失且关键指标恢复正常。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09


---
- 检索标签：component=HCCL,collective,parameter_consistency；stage=collective；error_code=—；fault_type=hang,parameter_mismatch
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注
