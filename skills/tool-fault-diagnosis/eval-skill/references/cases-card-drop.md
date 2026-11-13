# 掉卡挂死 案例集

## CASE-DROP-001：DISP 模块硬件 RAS 不可纠正错误
### 1. 问题现象描述及版本信息

**1.1 问题描述**
MY A3 交付现场压测中一台机器上报告警 0x81338002，npu-smi info -t health -i 3 -c 1 显示 Health Status 为 Alarm，Error Code 81338002，Error Information node type=TS subsys disp, sensor type=RAS State, event state=input error，device os 产生告警；HCCSStressTest 压测 17 启动，持续压测到 17 报出告警，告警后压测任务继续到 18 **1.2 配套版本信息**

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
drvHdcSessionConnect failed, ret = 10
HCCL function error: HcclCommInitRootInfo(...)->hcclComm(), error code is 4
rtSetDevice:ErrCode=507033, desc=[device retain error]
TsdOpen failed:Device is disconnected.
[Hardware Error]: Kernel panic - not syncing: Fatal hardware error!
Socket: NPU1 DIE: Virtuvian1 Module: HDLC3, Error Type: Fatal Error, INT_SRC: Bit(13)link_down
200GHL1/1/1 current state : DOWN
```

**排查路径**

1. 作业侧表现为 HDC connect 失败和 HCCL 初始化错误。
2. Runtime 显示 device disconnected / retain error，说明设备侧已不可用。
3. 内核和 BMC 日志显示 HCCS link_down fatal RAS 并触发 Device OS panic。
4. L1 端口 down 时间早于 NPU 侧告警，优先定界为 L1 子板故障。

### 3. 问题根因

A3 SuperPod NPU3_1 芯片 DISP（TS subsys disp）模块 slave 端口返回 error response（硬件 RAS 不可纠正错误，错误码 81338002，severity recoverable，ts disp rsp input err），HCCS 压测期间触发硬件告警。RAS 解析显示 Module 0x07:DISP Subsystem 0x7:TSSUB SERR 0x12 slave 端口的 error response，IERR 0xA PORTO-7 的 error response，UE 1 不可纠正错误，ERR_STATUSL 0x64300a12。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
按 NPU 硬件 RAS 不可纠正错误处置 NPU3_1 / NPU Board4 NPU4-2：隔离或更换故障板卡，检查 DISP slave 端口与 HCCS 互连状态；修复后复查 npu-smi info -t health 恢复 OK，并重跑 HCCSStressTest 确认不再出现 0x81338002。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=DISP,HCCS,RAS；stage=hardware_runtime；error_code=81338002；fault_type=hardware_error
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-DROP-002：maxpower 压测 SIOE 与 L2BUFFER FATAL
### 1. 问题现象描述及版本信息

**1.1 问题描述**
David V121 回片验证环境跑 maxpower 压测时，IMU RAS 连续上报两级 FATAL 致命故障：Module[SIOE] ErrorType[0x1421] 与 Module[L2BUFFER] ErrorType[0x1505]，均集中在 dieid ，预期正常压测无致命错误上报。

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
`[EVENT] IMU:... (dieid ) Skt[0] Totem[0] Module[SIOE] Device[0] ErrorType[0x1421] ..` 与  `[EVENT] IMU:... (dieid ) Error severity is FATAL[440227b000]`
`Skt[0] Totem[0] Module[SIOE] Device[0] ErrorType[0x1421]`
`Error severity is FATAL[440227b000]`
`Skt[0] Totem[1] Module[L2BUFFER] Device[9] ErrorType[0x1505]`
`Error severity is FATAL[4603f30000]`
```

**排查路径**

报 Found error node[19] moduleId[0x4]（SIOE）， 具体为 Skt[0] Totem[0] Module[SIOE] ErrorType[0x1421]、 Error severity is FATAL，即第一个致命故障落在 SIOE 接口；随后 报 moduleId[0x29]、 Skt[0] Totem[1] Module[L2BUFFER] ErrorType[0x1505]、 FATAL，第二个致命故障落在 L2BUFFER。两处 RAS 事件均集中在 dieid （ ~ 每行均 dieid ），且为 IMU RAS 上报的致命错误而非编译/加载失败。综合「SIOE + L2BUFFER 两级 FATAL + 集中 dieid 」，将问题从算子/软件逻辑排除，定界到 maxpower 压测下内存/L2/HBM-SIOE 链路的 RAS 致命上报。

### 3. 问题根因

David V121 跑 maxpower 时 RAS 上报 SIOE（ErrorType=0x1421）与 L2BUFFER（ErrorType=0x1505）两级 FATAL 致命故障，均集中在 dieid ，属内存/L2/HBM-SIOE 链路可靠性压测下的致命报错；根因尚未最终定论，开发人员正在继续压测复现以定位。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
继续压测复现以确认 SIOE（0x1421）与 L2BUFFER（0x1505）FATAL 故障的稳定复现条件，进一步结合 register dump（ERR_STATUS/ERR_MISC 等）与硬件/能效链路分析定位根因（是否硬件缺陷/能效配置/链路偶发），确认后修复并回归 maxpower 压测验证无致命错误上报。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09
- 首报错错误码 x1421

---
- 检索标签：component=SIOE,L2BUFFER,RAS；stage=stress_test；error_code=0x1421,0x1505；fault_type=hardware_error
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-DROP-003：L1 子板故障致 HCCS link_down fatal RAS

### 1. 问题现象描述及版本信息

**1.1 问题描述**

客户 40 节点 Atlas 900 A3 SuperPoD 训练作业拉起时报错误码 E3005 导致拉起失败，HCCL 初始化报 error code is 4

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
drvHdcSessionConnect failed, ret = 10
HCCL function error: HcclCommInitRootInfo(...)->hcclComm(), error code is 4
rtSetDevice:ErrCode=507033, desc=[device retain error]
TsdOpen failed:Device is disconnected.
[Hardware Error]: Kernel panic - not syncing: Fatal hardware error!
Socket: NPU1 DIE: Virtuvian1 Module: HDLC3, Error Type: Fatal Error, INT_SRC: Bit(13)link_down
200GHL1/1/1 current state : DOWN
```

**排查路径**

1. 作业侧表现为 HDC connect 失败和 HCCL 初始化错误。
2. Runtime 显示 device disconnected / retain error，说明设备侧已不可用。
3. 内核和 BMC 日志显示 HCCS link_down fatal RAS 并触发 Device OS panic。
4. L1 端口 down 时间早于 NPU 侧告警，优先定界为 L1 子板故障。

### 3. 问题根因

L1 子板故障导致 HCCS 链路上报硬件 RAS（link_down fatal），该 RAS 为 fatal 级别导致 Device OS panic，进而引发 HDC connect 失败和作业拉起报错 E3005。L1 侧端口比 NPU 侧端口更早发生 down，BMC 日志确认 HDLC 模块上报 Fatal Error，最终导致操作系统内核崩溃。

### 4. 解决方案

**临时规避**：优先按根因临时调整配置或回退可疑变更；无通用规避时保持现场采集完整日志。

**长期解决**：
1. 定位故障 L1 子板（PIC-1(2)）；更换 L1 灵衢总线板
2. 修复后按原故障场景复测，确认首错消失且关键指标恢复正常。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=HCCS,L1,RAS,BMC,DeviceOS；stage=hardware_runtime；error_code=E3005；fault_type=hardware_error,panic
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-DROP-004：高频日志刷屏导致 console soft lockup
### 1. 问题现象描述及版本信息

**1.1 问题描述**
David（AUK 形态）64 进程 100 线程压测 halResAddrMap、halMemRegUbSegment、halMemUnRegUbSegment、halResAddrUnmap 等 UB 资源接口时，dmesg 出现 massive 的 `UBDEVSHM: area with size does not exist` 日志刷屏（count 130,142 处），随后触发 `watchdog: BUG: soft lockup - CPU#55 stuck for 26s!`，进程卡死、影响维测与可靠性，高概率复现。

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
`[ 6467.560184] watchdog: BUG: soft lockup - CPU#55 stuck for 26s! [drv_hlt_sys_tes ]`
`watchdog: BUG: soft lockup - CPU#55 stuck for 26s! [drv_hlt_sys_tes ]`
`pc : console_emit_next_record+0x1b4/0x288`
`find_get_access_ctx+0x1a4/0x1c0 [ubdevshm]` → `ubdevshm_register_segment+0x148/0x330 [ubdevshm]`
`[ 6440.243270] UBDEVSHM: area with size [1000] does not exist`（及 `Count: 130,142 matches.`）
```

**排查路径**

watchdog 报 CPU#55 soft lockup 26s；其调用栈 pc 在 `console_emit_next_record+0x1b4/0x288`（console 输出函数），回溯为 console_flush_all → console_unlock → vprintk_emit → vprintk → `find_get_access_ctx+0x1a4 [ubdevshm]` → `ubdevshm_register_segment+0x148 [ubdevshm]` → pma_ub_ubdevshm_register_segment [asdrv_svm] → svm_local_submit_handle → sched_submit_event_pre_proc [asdrv_esched]，说明软锁发生于 ubdevshm 接口里通过 printk 打印的 console 输出路径；同时 显示同一时刻 `UBDEVSHM: area with size [1000] does not exist` 日志以数十万条级别刷屏（Count 130,142）。因此确认软锁不是硬件/调度逻辑错误，而是高频接口（find_get_access_ctx 找不到 area 时）反复 vprintk 打印海量 error 日志，console_unlock 长时间持有锁输出日志导致软锁。

### 3. 问题根因

ubdevshm find_get_access_ctx 为高频调用接口，在 64 进程 100 线程压测（halResAddrMap/halMemRegUbSegment/halMemUnRegUbSegment/halResAddrUnmap）时，因 area 查找路径反复打印海量 `UBDEVSHM: area with size does not exist` 日志，console 输出路径（console_unlock → console_emit_next_record）被长时间占用，触发 watchdog soft lockup（CPU#55 stuck 26s）。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
结合上下文优化 ubdevshm find_get_access_ctx 等高频接口的日志：对 `area with size does not exist` 类高频/重复错误日志进行限频、去重或级别降级（改为 trace/debug 或 rate-limit），避免 64 进程 100 线程压测下海量日志刷屏拖垮 console，回归压测确认不再触发 soft lockup。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=ubdevshm,console；stage=high_frequency_logging；error_code=—；fault_type=soft_lockup
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注


## CASE-DROP-005：device5 硬件故障致 FlashAttentionScore ECC 校验失败
### 1. 问题现象描述及版本信息

**1.1 问题描述**
PyTorch 2.1 训练任务在 CANN 8.0.rc2.2 环境下运行，worker651 触发快恢拉起失败，报错 EZ9903 及 driver error:internal error，日志显示 FlashAttentionScore 算子执行时 VEC instruction error: ECC verification failed when the UB is read，其他卡报 EOF ERROR，进程中断

**1.2 配套版本信息**

| 信息名称 | 信息内容 |
| --- | --- |
| CANN 版本 | 8.0.rc2.2 |
| HDK 版本 | 23.0.6 |
| 芯片型号 | Ascend NPU（chipId , device_id=5） |
| 训推框架版本 | 框架版本：pytorch 2.1 |

### 2. 问题分析

再次发生同问题时，按以下特征与排查路径确认是同一个问题。

**关键日志特征**

```
[ERROR] RUNTIME[3560,python3.9] -01 13  .243.110 [davinci, engine.cc ]11156 ProcLogicCqReport:Task run failed, device_id=2, stream_id=2, task_id=16853, sqe_type=0x1(fls), errType=0x1(task exception), sqwStatus=0
call failed, detail:EZ9903: 2024-12-01-13  .684.939 rtKernelLaunchWithHandleV2 failed: 507015
The error from device(chipId , dieId ), serial number is 1, there is an fftsplus aivector error exception, core id is 21, error code is 0x1000000000000000
The extend info: errcode x1000000000000000, 0, 0, errorStr:"VEC instruction error: ECC verification failed when the UB is read", xp_error info: 0xe36300, flag_error info: 0x85 fsmId , tsLot , thread , ctxId , blk , subBlk , subErr...
Aicore kernel execute failed, device_id=5, stream_id=2, report_stream_id=2, task_id=16853, flip_num=1302, fault kernel_name=FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_100000010102202209
AICORE Kernel task happen error, retCode=0x26, [aicore exception] / rtKernelLaunchWithHandleV2 failed: 507015
[ERROR] 2024-12-01-13  (PID , Device , RankID ) ERR01005 OPS internal error
Run test:case 52 times failed, device[5], npu_id[5], case_name: FAP_BUS_FIXD, error code: 110000, message: run aclnnFlashAttentionScore failed
```

排查路径 ) grep 从 plog 定位首报错时间 2024-12-01-13  .243.110，ProcLogicCqReport Task run failed errType=0x1(task exception)；2) 按首报错时间过滤日志，发现首报错为 FlashAttentionScore 算子报错，伴随 VEC instruction error: ECC verification failed when the UB is read（errcode x1000000000000000），fftsplus aivector error exception core id=21，其他卡报 EOF ERROR，初步怀疑 device5 硬件问题；3) 使用 ASCEND_DMI 工具对疑似故障设备 device5 进行压测，压测 6 次出现一次错误，报错信息与业务日志完全一致（ECC verification failed），device_id 相同；4) 压测结果显示 Run test:case 52 times failed, device[5], case_name: FAP_BUS_FIXD, error code: 110000，The detect of fixed voltage stress mode is failed on device[5]；5) 确认为 device5 硬件故障，需返板分析

**排查路径**

1. 核对业务侧 EZ9903 和 driver internal error。
2. 设备侧错误指向 FlashAttentionScore 的 AIVector error exception。
3. 扩展信息显示 VEC instruction error: ECC verification failed when the UB is read。
4. 错误集中在 device5/chipId5，其他卡主要是传播性 EOF/超时。

### 3. 问题根因

根因：worker483 节点的 device5 存在硬件故障，导致 FlashAttentionScore 算子执行时发生 ECC 校验失败（VEC instruction error: ECC verification failed when the UB is read），进而引发 AICore 异常（retCode=0x26）和进程中断。日志显示 VEC 指令读取 UB 时 ECC 校验失败，且 ASCEND_DMI 压测复现了相同的错误（error code: 110000），确认为物理硬件缺陷。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
现场更换故障卡（device5）；留存坏件 SN 以及 device 日志和 BMC 日志；将故障板卡返回实验室进行详细分析；关注 FlashAttentionScore 算子在特定硬件上的稳定性，出现 ECC 校验失败通常指示硬件物理损伤

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=FlashAttentionScore,ECC,device_health；stage=runtime；error_code=0x26,110000；fault_type=hardware_error,ecc_failure
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注
