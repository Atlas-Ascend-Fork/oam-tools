# 进程中断 案例集

## CASE-EXIT-001：stream context 不一致导致 EE9999
### 1. 问题现象描述及版本信息

**1.1 问题描述**
车BU 200卡训练任务（驱动 23.0.6 / CANN 7.0.RC1），训练一段时间后出现首报错 EE9999，提示 Get stream id failed, stream is not in current ctx，后续引发 notify wait 超时和 HCCL AllGather 通信算子报错；用户描述之前有跑通过

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
Thread ... wrapper to_tensor element_all_reduce_tensor summary_log validate
[Metrics (Rank 0)] ... ADE_30=1.563 ... v_all_3s_fde=1.016
infer rslt saved in: obs://<bucket>/output/...
self.val = torch.tensor(self.val).double().cuda()
self.sum = torch.tensor(self.sum).double().cuda()
self.count = torch.tensor(self.count).double().cuda()
```

**排查路径**

1. 主线程卡在 to_tensor 后的 element_all_reduce_tensor，即 all_reduce 前的 H2D。
2. 推理指标已打印，结果保存完成，排除 OBS 写入异常。
3. 修复 diff 将 val/sum/count 统一为 double，说明各节点指标 dtype 不一致。
4. 该不一致导致 H2D 传输阻塞，进而引发全量超时。

### 3. 问题根因

stream 下发任务时所在线程的 context 与创建 stream 时记录的 context 不一致，Runtime 校验失败；典型场景为跨线程使用 stream，线程内 context 被重置亦属等价机制。

### 4. 解决方案

**临时规避**：无。

**长期解决**：
检查业务代码中 rtSetDevice、rtCtxCreate 和 rtCtxSetCurrent 的调用位置；确保 stream 创建和任务下发使用同一有效 context，或在下发前显式设置正确 context；增加 stream/context 归属日志后复跑训练，确认 EE9999 和 notify wait 超时不再出现。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=RUNTIME,stream,context；stage=task_submit；error_code=EE9999；fault_type=context_mismatch
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注

## CASE-EXIT-002：模型评价指标 dtype 跨节点不一致，H2D 阻塞引发全量超时

### 1. 问题现象描述及版本信息

**1.1 问题描述**

现网训推任务，30 节点全量超时，每 200 轮推理一次，推理完卡住，两小时后全量超时，30 节点共拉起四次任务四次均失败，10 节点和 16 节点拉起成功，任务前后代码数据均未改变，网络大脑正常

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
Thread ... wrapper to_tensor element_all_reduce_tensor summary_log validate
[Metrics (Rank 0)] ... ADE_30=1.563 ... v_all_3s_fde=1.016
infer rslt saved in: obs://<bucket>/output/...
self.val = torch.tensor(self.val).double().cuda()
self.sum = torch.tensor(self.sum).double().cuda()
self.count = torch.tensor(self.count).double().cuda()
```

**排查路径**

1. 主线程卡在 to_tensor 后的 element_all_reduce_tensor，即 all_reduce 前的 H2D。
2. 推理指标已打印，结果保存完成，排除 OBS 写入异常。
3. 修复 diff 将 val/sum/count 统一为 double，说明各节点指标 dtype 不一致。
4. 该不一致导致 H2D 传输阻塞，进而引发全量超时。

### 3. 问题根因

用户代码中部分模型评价指标在不同节点上的数据类型不统一，导致在执行 H2D（Host to Device）数据传输时发生异常卡死，进而引发全量超时。在遍历 22 个评价指标进行 all_reduce 规约前，需将数据从 Host 拷贝到 Device，由于部分指标在 30 个节点间数据类型不一致，触发底层传输阻塞。

### 4. 解决方案

**临时规避**：优先按根因临时调整配置或回退可疑变更；无通用规避时保持现场采集完整日志。

**长期解决**：
1. 检查所有模型评价指标在各节点的数据类型定义；将不一致的数据类型统一修改为双精度浮点型（在 nn_util.py 的 to_tensor 中对 self.val/self.sum/self.count 加 .double()）；重新提交任务验证
2. 修复后按原故障场景复测，确认首错消失且关键指标恢复正常。

**元信息**
- 可信度：90/100（HIGH）
- 首报错错误码：见关键日志特征
- 首报错特征：见关键日志特征
- 验证状态：已验证修复有效
- 来源报告：agent-benchmark
- 收录日期：2026-11-09

---
- 检索标签：component=H2D,all_reduce,metrics,dtype；stage=data_transfer；error_code=—；fault_type=hang,dtype_mismatch
- 证据边界：direct_mechanism=日志可证；implementation_root_cause=按正文标注；fix_verification=按元信息标注
