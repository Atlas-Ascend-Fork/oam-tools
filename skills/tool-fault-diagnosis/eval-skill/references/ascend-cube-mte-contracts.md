# Cube 与 MTE 参数约束

当可见材料涉及 CUBE/MMAD、L1 到 Fixpipe Buffer、LOAD3DV2 或 DataCopyPad 时
选读。来源为官方 asc-devkit v9.0.0-beta.2，提交
`b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b`；以下限定 A2/A3 与具名 API。
先核现场型号、版本和变体；错误单码不证明当前调用了这些 API，也不提供私有实参。

## CUBE：检查实际操作数地址

C API 通用约束：L0A/L0B 起点 512B 对齐，L0C 64B，L1/UB 32B，Fixpipe
Buffer 64B；具体 API 明确给出对齐时，以该 API 为准。对齐必须检查**传入指令的
实际派生地址**：`base + element_offset * sizeof(T)`。分配基址对齐不保证带偏移
指针对齐。若确认偏移破坏对齐，修正 tile 的存储布局/步长和取址，不把地址向下
取整后访问别的元素；同时确认整个矩阵的物理跨度仍在实际分配内。

`asc_mmad` 的 A/B/C 分别位于 `__ca__`/`__cb__`/`__cc__`；
`left_height`、`n_dim`、`right_width` 各在 `[0,4095]`，任一为零则指令不执行，
**不能由零维度直接断言 CUBE 参数非法**。核查类型、实际布局、M/N/K、源目的
偏移与累加范围；没有操作数转储时，将不对齐、布局或范围错误列为条件候选，
不编造发生在哪个 tile、哪个指针或具体偏移。

来源：[C API 通用约束](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/c_api/general_instruction.md)、
[asc_mmad](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/c_api/cube_compute/asc_mmad.md)。

## L1 到 Fixpipe Buffer：单位与完整跨度

`asc_copy_l12fb(dst, src, ...)` 的源是 L1 `__cbuf__`，目的是存放量化参数的
Fixpipe Buffer `__fbuf__`，不是 L0C。该 API 明确要求**两端起点 32B 对齐**，
覆盖上述通用 Fixpipe Buffer 对齐规则。

- 连续重载的 `size` 单位是字节。
- 高维重载 `burst_num` 在 `[1,4095]`，`burst_len` 在 `[1,65535]`；
  `burst_len`、`src_gap_size`、`dst_gap_size` 的单位均为 32B datablock。
  gap 是前一块末端到下一块起点的间隔，不是两块起点间隔。
- 非负 gap 时，目的总跨度为
  `((burst_num - 1) * (burst_len + dst_gap_size) + burst_len) * 32` 字节；
  源端另用 `src_gap_size` 计算。对两端分别核
  `offset >= 0 && offset + span <= actual_capacity`，不能只检查首块。

若确认目的跨度超出 Fixpipe Buffer，修正目的偏移、gap、burst 配置或按合法空间
分块，保留业务量化语义；只增加 L0C 分配或更改 GM 指针不能修复该对象越界。
容量取自现场芯片与实际分配，不把其它型号或示例容量当通用常量。

来源：[asc_copy_l12fb](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/c_api/cube_datamove/asc_copy_l12fb.md)。

## LoadData3DParamsV2：滑动步长与尾分形

以下针对 `LoadData3DParamsV2`，不套用 V1、V2Pro 或其它结构的 repeat stride。

| 字段 | 公开约束与检查对象 |
| --- | --- |
| `strideH/strideW` | 卷积核在源 H/W 的滑动步长，范围 `[1,63]`；零不合法。按实际卷积语义恢复，不能统一改成 1 |
| `kStartPt` | `[0,65535]`；half 为 16 的倍数，int8/uint8 为 32 的倍数；在字段范围内仍须检查实际 img2col 起点 |
| `mStartPt/mExtension` | half/int8/uint8 未覆盖最下侧分形时为 16 的倍数；覆盖时有例外。起点 `[0,65535]`，extension `[1,65535]` |
| `kExtension` | `[1,65535]`；未覆盖最右侧分形时 half 为 16 的倍数，int8/uint8 为 32 的倍数；覆盖时无该倍数要求 |
| `channelSize` | `[1,63]`；half/bfloat16 允许 4、8、16N、16N+4、16N+8；int8/uint8 允许 4、8、16、32N、32N+4、32N+8、32N+16，N 为正整数。不是全部要求 16 的倍数 |

同时按真实输入 H/W/C、卷积核、padding、dilation、输出 img2col 布局和目标空间
核对起点与传输跨度。若确认错在起点或步长，修改对应字段及其 tiling 来源；
不能任意增加 padding 或裁减 extension 掩盖越界并改变算子语义。缺参数时明确
需要哪一组实参才能区分这些候选，不把 LOAD3D 单码当作某字段已为零的证据。

来源：[Load3D 的 V2 参数表](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/Load3D.md)。

## DataCopyPad：元素与字节不能混用

A2/A3 的 DataCopyPad(ISASI) 中，`leftPadding/rightPadding` 单位为**元素数**，
每侧均须满足 `padding * sizeof(T) <= 32` 字节。`blockLen` 则为字节；
`srcStride/dstStride` 是相邻块的尾到头间隔，GM 侧以字节计，VECIN/VECOUT
侧以 32B datablock 计。LocalTensor 起点须 32B 对齐，该 API 的 GlobalTensor
起点无地址对齐要求，不套普通 DataCopy 或其它搬运 API 的 GM 对齐规则。

核对元素类型、每侧 padding、blockCount、自动补齐/dummy、每块物理步长和
完整源目的容量。若确认 padding 字节数超限，按原语义调整分块/填充方案，
重新计算物理空间与搬运参数；不只截掉 padding 或扩大声明长度。只有 MTE
错误而没有 API 调用证据时，保持为候选，不确诊当前一定使用了 DataCopyPad。

来源：[DataCopyPad(ISASI)](https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/DataCopyPad%28ISASI%29.md)。

## 验证

保持原芯片、版本、故障输入及 kernel 变体，检查原错误签名、同步返回与输出
正确性，并覆盖相关 tile/尾块、布局、padding 和多 burst 边界。以上是条件修复
及验证计划；没有实际执行记录，不声称编译、运行或修复已经成功。
