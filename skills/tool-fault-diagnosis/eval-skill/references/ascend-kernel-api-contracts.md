# 自定义 kernel 的地址、搬运与队列约束

当原始日志、构建路径或已给源码涉及 Fixpipe、GlobalTensor、GM/UB 搬运或
TQue 时选读本页。以下知识来自公开 asc-devkit v9.0.0-beta.2，提交
`b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b`；先核对芯片、API 变体、布局和
现场版本。公开契约是检查依据，不证明当前 kernel 的私有参数值或故障指令。

## Fixpipe：源布局和 stride 单位

适用于公开文档中的 `FixpipeParamsV220`。FIXP 读 L0C 越界时，优先检查
**源基址、实际 NZ 布局、源 stride、搬运的 M/N 范围及多矩阵间隔**；写目的
越界则检查目的基址、布局、stride 和容量。不能用目的 stride 修复源越界。

| 参数 | 公开契约 | 对应修复对象 |
| --- | --- | --- |
| `srcStride` | 相邻 Z 排布起始地址的间隔，单位为 `C0_Size = 16 * sizeof(src_type)` 字节 | 按实际源 NZ 布局的物理间距赋值，不把字节数或额外 gap 直接填进此字段；逐块检查起点与读取末端是否都在源分配范围内 |
| `dstStride` | **NZ 和 NZ2ND 两种输出均要求非零**；NZ 单位为 32 字节 datablock，NZ2ND 为目的每行元素数 | 先检查跨模式非零约束，再按实际输出布局、元素类型和行距重算，不能沿用另一模式的单位 |
| `mSize/nSize` | 本次读取源矩阵的 M/N 大小；取值和倍数约束随 NZ2ND/channelSplit 改变 | 与 MMAD 实际有效结果、尾块和源容量对齐，不把完整矩阵形状直接套到每个 tile |
| `ndNum/srcNdStride` | `ndNum` 是矩阵数；此变体 `srcNdStride` 单位为 `16 * C0_Size`，`ndNum=1` 时不生效 | 多矩阵时连同最后一矩阵累计检查；单矩阵可先去掉不需要的批次搬运，再验证原功能 |

官方完整 NZ2ND 示例把 `srcStride=m`、`dstStride=n`、`mSize=m`、`nSize=n`。
这里的 m/n 来自该示例实际分配和布局，**不是所有 kernel 的通用修复常量**。
若现场源码证实相同的紧密源 NZ 布局和目的 ND 行距，可按对应物理 M/N 修正
stride；有 padding、切片、其它布局或不同 API 时重算。未提供参数时，明确
建议修改哪个字段、应满足什么地址约束和如何验证，不声称已读到其值。

`FixpipeParamsArch3510` 等其它变体的间隔单位与范围可能不同，不能套用
V220 的 `srcNdStride`。channelSplit、量化或同步线索也须结合实际报错对象；
构建路径提到某开关，不表示该开关已经生效或就是读越界的原因。

来源：[Fixpipe 参数表、模式与示例](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/Fixpipe.md)。

## GM 绑定与 GM/UB 搬运

`GlobalTensor.SetGlobalBuffer(buffer, bufferSize)` 以给定 GM 指针初始化对象；
`bufferSize` 是元素个数，调用方需保证不超实际数据长度。只传指针的重载使
`GetSize()` 返回 0，不能单凭该 0 判定分配失败或实际 buffer 为空。

GM 地址高位非法时，沿 Host 实参、kernel 入口、`SetGlobalBuffer`、切片与实际
访存逐级核对指针来源、偏移单位、溢出和有效期。入口 args 数值满足位宽，仍
不能排除 kernel 内部绑定时加错偏移。若确认绑定/偏移错误，修正为有效 GM
分配的基址加合法元素偏移，并保证整个访问跨度在同一对象内；不以截断高位
或地址掩码掩盖错误，也不只调整 bufferSize 声明而保留非法指针。

`asc_copy_gm2ub_sync(dst, src, size)` 的 `dst` 是 UB 目的地址，`src` 是 GM
源地址，`size` 是**字节数**；公开 A2/A3 契约要求 UB 起点 32 字节对齐，GM
起点按对应数据类型字节数对齐。高维重载的 burst 长度和 gap 又以 32 字节
datablock 计，不能混用。逐项核对两端对象、偏移、长度与声明容量：

- 若证实 UB 目的落在分配区间之外或禁区，去掉非法目的偏移，改用合法 UB
  区间并缩小/分块搬运；只修 GM 源指针不能修复 UB 目的越界。
- 若证实 GM 源地址或跨度非法，恢复有效 GM 绑定和访问范围；只扩大 UB
  不修复 GM 高位或映射错误。
- 若原始解码与目录提示的内存对象不同，两者分别说明。目录可支持优先检查
  对应搬运的另一端，不能据此替换硬件直接机制、宣称缺失的 UB 地址或解码位。

该接口的同步版本包含等待，但不使错误地址合法；异步多次搬运的 UB 目的
重叠时，公开文档要求同步以保证串行。具体同步位置仍按实际生产者与消费者
确定，不对任意越界统一添加 barrier。

来源：[SetGlobalBuffer](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/SetGlobalBuffer.md)、
[asc_copy_gm2ub](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/c_api/vector_datamove/asc_copy_gm2ub.md)。

## TQue：交付与释放是不同操作

对已有源码或队列线索，按每次迭代、同一队列和同一 tensor 核对：

```text
AllocTensor -> 生产数据 -> EnQue -> DeQue -> 消费数据 -> FreeTensor
```

这是常见生产/消费路径，不要求只有分配后立即释放的临时对象也必须入队。
`FreeTensor` 释放对象，不能代替把结果交给消费者的 `EnQue`；`DeQue` 取出
的是已入队对象。公开文档说明空队列执行 DeQue 属异常行为，CPU 调测会报错；
不能据此直接确认某次 Device 现场必然死锁。

若源码证实缺少生产者的 `EnQue`，在数据生产完成后、消费者 `DeQue` 前
补齐正确队列上的入队；若提前释放，把释放移到对应消费完成的生命周期位置。
同时核对分支、循环次数、队列深度和对象是否对应；`EnQue` 返回 false 表示
队列已满，不能假定交付成功后继续消费。没有源码时保留这些为具体条件修复，
不能把单条 task exception 或同步参数 `timeout=-1` 当作队列死锁证据。

来源：[EnQue](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/EnQue.md)、
[DeQue](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/DeQue.md)、
[FreeTensor](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/FreeTensor.md)。

## 对应验证

以上是修复建议。只有已有执行记录才能写修复成功；验证计划保持原设备、版本、
失败输入和 kernel 变体，检查原错误签名消失、同步返回、输出正确，以及尾块、
布局/批次、队列循环等相关边界。不以编译通过或一次无报错代替完整业务结果。
