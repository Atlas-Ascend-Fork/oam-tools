# HIXL 建链与传输故障

HIXL（Huawei Xfer Library）提供单边点对点传输；LLM-DataDist 基于它提供
KV Cache 语义。它与 HCCL 集合通信不能互换：先核对实际 API、协议、端点与
失败阶段，再选择排查分支，不给点对点建链套用 AllReduce 次序或全 rank 参与要求。

## 协议与实体

HIXL 可使用 RDMA、HCCS、UB_CTP、UB_RTP、UBoE 等路径，支持范围随平台和版本
变化。通信上下文中的 UB/灵衢、URMA 与 AI Core 的 Unified Buffer 片上存储
不同；`UB(lingqu)` 也不是“已知软件 bug”的标记。Host 控制连接、通信 endpoint
与底层通道可能属于不同协议或位置，不能用一项成功证明其他层已就绪。

保留 local/remote engine 或 endpoint、Host/PID、device、socket、channel index、
协议、接口和本次操作身份；只有现场给出对应关系时才换算 rank 或物理卡号。
线程/进程数量不等于参与 endpoint 数量，重复接收超时也不证明互等闭环。

## 建链超时的层次

公开 HIXL CS 实现包含以下阶段，现场仍须核对对应版本：

| 阶段 | 现有材料中可核对的内容 |
| --- | --- |
| 控制连接与 endpoint 匹配 | 连接/匹配请求和响应、实际 socket 与端点；发送成功不证明远端已处理 |
| 准备本端通道 | endpoint 类型、协议、底层创建调用及返回；版本可能有内存预取/注册步骤 |
| 对端处理建链请求 | 对端收到请求、endpoint 查找、底层通道创建与响应发送；缺少对端记录时保持未知 |
| 接收建链响应 | 是接收超时、连接关闭、报文格式错误，还是收到明确失败状态；这些不是同一结果 |
| 数据传输与完成 | 通道就绪后的提交、完成队列/错误、两端资源与内存生命周期；不能由建链等待反推传输已执行 |

`RecvCreateChannelResponse` 超时只能定位为本端未在该等待预算内取得所需响应。
外层失败日志里的 `timeout=... ms` 可能只是配置预算，其他错误返回也会打印它；
先查内层错误和实际状态，不能仅凭该字段判定接收已超时或已等待这么久。
在下述实现中，server 在调用 endpoint 的 `CreateChannel` 后才发送成功响应，
endpoint 又会调用底层通道创建。因此底层设备/驱动/通信资源创建的失败或阻塞
可能表现为上层响应问题；不能因报错来自 Host socket 接收就排除这些候选。
反过来，接收超时也不确认底层资源冲突、网络故障、特定队列耗尽或软件死锁。

沿同次操作查双方最早的具体返回值与正常进展，区分请求未达、处理未推进、
底层创建失败、响应发送/接收异常及进程退出。只有客户端片段时，说明本端
已到达的阶段、各候选的支持与仍缺的对端证据；不编造资源编号或返回码定义。
若已有 UB/URMA 创建、激活、mailbox 或 UMMU/cmdq 线索，按
[UB/URMA 资源与地址转换](fault-flows/network-flow.md#uburma-资源与地址转换)
继续追踪底层错误与原文上下文；仅有响应等待时不假定这类故障。

## 条件修复与验证

已有 `bind` 冲突、协议/版本不匹配或具体底层创建错误时，针对其已确认的资源、
配置或兼容条件修复。扩大 timeout 需要同次有效依赖的持续进展和延迟依据；
重启只能作为受控止损，不能证明根因。验证区分建链成功、实际传输/校验通过、
并发条件和重复建断链后的资源回收，不把收到响应当成完整业务已恢复。

## 公共来源与适用范围

以下内容核对于 HIXL revision
`a11125d6fe7d15863b6364c3a37e25a7f5a1843a`；用于解释可能的阶段和检查位置，
不证明现场运行相同源码，也不将新版本配置或修复套给旧版本。

- [README：HIXL、LLM-DataDist 与支持协议](https://gitcode.com/cann/hixl/blob/a11125d6fe7d15863b6364c3a37e25a7f5a1843a/README.md)
- [HixlCSClient::ExchangeEndpointAndCreateChannel](https://gitcode.com/cann/hixl/blob/a11125d6fe7d15863b6364c3a37e25a7f5a1843a/src/hixl/cs/hixl_cs_client.cc)：本地创建与响应接收。
- [HixlCSServer::CreateChannel](https://gitcode.com/cann/hixl/blob/a11125d6fe7d15863b6364c3a37e25a7f5a1843a/src/hixl/cs/hixl_cs_server.cc)：对端创建及成功/失败响应。
- [Endpoint::CreateChannel](https://gitcode.com/cann/hixl/blob/a11125d6fe7d15863b6364c3a37e25a7f5a1843a/src/hixl/cs/endpoint.cc)：调用具体底层通道实现。
- [RecvCreateChannelOnlyResponse](https://gitcode.com/cann/hixl/blob/a11125d6fe7d15863b6364c3a37e25a7f5a1843a/src/hixl/cs/conn_msg_handler.cc)：接收、解析与返回状态检查。

通用等待、事件关联和网络证据分别见[超时流](fault-flows/hang-flow.md)与
[网络流](fault-flows/network-flow.md)。
