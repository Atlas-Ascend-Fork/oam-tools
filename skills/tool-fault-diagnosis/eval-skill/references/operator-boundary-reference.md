# 算子切分、搬运与资源约束

已有 shape、切分、搬运参数，或明确的 unroll/缓冲配置变化时，使用本页把变化
展开为可检查的约束。队列指针 `sq_tail` 等不是 tensor 尾块，不按名字套用。
先核同一任务、对象、存储层级、dtype、布局、转置及单位；缺定义的日志字段
保留原值。下面的区间关系是普通布局的数学推导；API 与实现例子限定公开
asc-devkit v9.0.0-beta.2，提交 `b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b`，
使用时核对现场版本、型号及分支，不证明现场调用或私有参数。

## 1. 分开有效长度、物理容量与步进

分别列出全局逻辑 shape、单核范围、当前 tile 有效 shape、对齐后的容量、物理
行 pitch 和当前块号。有效尾长不能代替物理 pitch，padding 容量不是额外有效
输入；分配范围内的错误行/错误 tile 仍会导致精度异常。packed 4bit、NZ/分形、
转置与转换须按实际映射处理，不能统一用逻辑元素数乘 dtype 字节数。

对本层有效长度 `L>=0`、常规块长 `B>0`，先读循环和分支，再解释 tail：

- 若执行 `n=ceil(L/B)` 个 tile，则 `0<=i<n` 时起点 `o=i*B`、有效长度
  `v=min(B,L-o)`。`L>0` 且整除时，实际最后一块有效长度是 B；`L=0` 没有块。
- 若先处理 `floor(L/B)` 个完整块，余数 `r=L%B>0` 才追加一块，`r=0` 就表示
  不存在额外余数块。不能把所有 tail=0 都改成 B，否则会多处理一块。

非整除时逐项核 padding 的初始化、计算掩码、归约/累加和有效写回范围；
padding 不必恒为0。若规则和已给值矛盾，算出具体哪一块及哪段覆盖出错，
修正该层长度/循环/offset 的生成和使用，而非强行修改输入使其整除。

公开 Matmul 样例在 ceil 循环的末块将0余数解释成常规块，Softmax 样例仅在
余数大于0时追加处理，见[Matmul分块][matmul]与[额外余数块][residual]。
[SetSingleShape][single] 设置运行时单核有效 M/N/K，单位为元素，与 SetTail
功能一致；完整原始 shape/布局与本次有效 shape 分开设置。

## 2. 源、目的分别检查完整访问

先核具体API的单位、地址空间和stride含义。头到头 pitch 与尾到头 gap 不同；
等宽且单位一致时才有 `pitch=width+gap`。对普通固定非负行步进，基址 A、
首行字节偏移 O、行数 R、每行实际触及 W 字节、字节 pitch P，逐行范围是：

```text
[A + O + j*P, A + O + j*P + W), 0 <= j < R
R > 0 且 P >= 0 时，包络长度 = (R-1)*P + W
```

包络含可能未访问的洞，不等于payload字节数。源读、局部写、GM写回各自
换算，核实际分配范围、逻辑有效区、跨行/块重叠和padding；目的对齐、转换
或布局不同时重新建目的映射。负步进、scatter/gather和特殊布局不套此简式。
缺实际分配区间仍可证明已定义shape/索引/参数的逻辑冲突，但不能把逻辑越界
直接写成已越过GM allocation。所有现场派生计算按诊断约定用计算工具核对。

[ND搬运封装][nd]的普通非4bit分支分别使用 `row*gCol+col` 与原始行pitch
`gCol`；[DataCopyPad][pad]中blockLen/GM gap为字节、Local gap为32B块，
左右padding为元素。只作为具名版本依据，不推广到任意DataCopy或通路。

## 3. 当前、下一次预取及 A/B 独立核对

依次跟踪 `迭代索引 -> 有效长度/容量 -> offset/pitch -> src/dst范围 -> buffer`。
主循环安全不证明预取安全；核预取是否执行、缓存是否命中、下次索引是否跨到
下一维及buffer复用条件。当前尾长不能覆盖所有常规块，也不能充当下次块长。

适用的MDL/TCubeTiling分支中，A/B常规K跨度分别为 `baseK*stepKa` 与
`baseK*stepKb`，各自核循环次数、尾长和全载状态。现场字段名相似不证明其
定义等价。[KLoop][kloop]区分当前长度和指定索引的 `GetTileShapeAOf/BOf`；
[预取调度][preload]使用下一次B索引对应的长度。它们是该版本内部实现依据，
不建议直接修改或特化这些内部类，也不证明当前故障由预取触发。

## 4. 参数变化与资源压力

先解释题面明确的参数变化影响哪个局部工作集，再按支持强弱排序候选。
unroll或并行缓冲增加时，优先核实际活跃tensor的shape、存储类型、同时驻留
份数及编译分配结果；若同一局部对象随变化增大，具体检查对应UB/L1预算，
给出回退已知可用配置或分块/缩短生命周期的条件方案。不停在“可能资源问题”，
也不由unroll倍数直接推出峰值UB同比增加或已超限。

对该版本普通 `TPipe.InitBuffer(que,num,len)`，num为份数、len为每份字节数，
每份长度向上补齐32B。同层、独立且不共享的已知申请，可核已知保留量
`sum(num*align_up(len,32))`；普通TBuf按单份处理。先按实际布局得到len，
别把逻辑tensor逐个相加，别把L1份数与UB容量比较。生命周期、pool复用、
编译临时量及未计入申请分别说明；只有已知预算与对应平台可用容量足够时
才确认超限。FreeTensor不等于TPipe物理预算已释放，见[InitBuffer][init]。

[TBufPool][pool]允许物理UB/L1复用，复用同时受有效期和同步约束。
若只有参数变化和通用断言，资源超限仍是候选；同时检查布局、索引和同步
是否随变化改变，不把内部错误包装直接当运行期AI Core容量事实。

## 5. 给出对应修复与验证

已有值足以形成矛盾时，写清对象、来源、表达式、单位及成立条件，并给具体
修改位置和满足的约束。Tiling生成成功不证明手工offset或每次搬运正确；
缺dump限制输出首个diff及传播确认，不阻止已有参数机制的分析。

修复保持算子语义，核对性能、容量和同步副作用。验证计划覆盖原失败输入、
整除/非整除、单块/多块及主/预取边界，检查原首错消失和有效输出正确。
尚未执行的回退、复跑与修复验证保持为建议。

[matmul]: https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/examples/01_simd_cpp_api/03_libraries/00_matrix/matmul_tscm_mdl_setorgshape/matmul_tscm_mdl_setorgshape.asc#L141
[residual]: https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/examples/01_simd_cpp_api/03_libraries/01_activation/softmaxflashv2/softmaxflashv2.asc#L222
[single]: https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/SetSingleShape.md#L37
[nd]: https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/impl/adv_api/detail/matmul/stage/copy_cube_in/copy_tile_to_cube/data_copy_wrapper_nd.h#L73
[pad]: https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/DataCopyPad%28ISASI%29.md#L242
[kloop]: https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/impl/adv_api/detail/matmul/scheduler/iterator/k_loop/k_loop_mdl_base.h#L196
[preload]: https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/impl/adv_api/detail/matmul/scheduler/base/scheduler_mdl_base.h#L527
[init]: https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/InitBuffer.md#L105
[pool]: https://gitcode.com/cann/asc-devkit/blob/b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b/docs/api/context/TBufPool%E7%AE%80%E4%BB%8B.md#L3
