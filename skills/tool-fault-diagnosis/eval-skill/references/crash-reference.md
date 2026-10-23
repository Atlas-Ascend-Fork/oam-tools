# 进程中断（Crash）专项诊断参考

本页保留日志索引和机制线索。诊断步骤、首错关联、责任边界和验证状态统一见
[进程中断处理流](fault-flows/crash-flow.md)，core 关联及保存条件见
[Coredump 参考](coredump-reference.md)。只离线分析已有材料，不附加运行进程、
修改转储配置或重新触发崩溃。

## 问题现象

`Segmentation fault`、`Aborted`、native 信号、明确的进程退出或 core 可作为
中断入口。Python 异常退出、Host Linux core、Host tracer Stackcore 和 Device
Stackcore 按来源区分，不能因名称含 core 就使用同一种解析方法。

常见 shell 的 `139/134/137` 可分别提示 SIGSEGV/SIGABRT/SIGKILL，但须核对实际
退出状态、容器或调度记录；程序也可能主动返回该数值。SIGKILL 不证明 OOM，
SIGSEGV 不独自证明空指针，SIGABRT 需追断言或主动 abort 的上游条件。

## 关键日志字段

| 信号 | 解释与核对 |
| --- | --- |
| `E39999` | 读取具体详情、现场版本与 Device 进程状态；单码及无 deviceos ERROR 不确认 Device core |
| `HDC send err ret(25)` / `hdc recv error 25` | 核对该版本返回值及关联会话；若详情为 closed，只确认关闭状态，继续查原因 |
| `-25` / `session has been closed` | 关闭线索；正常销毁、取消、外部终止和异常均需按具体记录比较 |
| `Server destroy success` | server 销毁记录，不证明崩溃或谁先关闭 |
| `GEfinalize` / `GEFinalize` | GE 资源清理，不单独证明进程退出；须关联 PID/rank 和真实退出记录 |
| `subProcPid` | Device 子进程关联线索，须同时匹配设备、故障时间窗和组件，防止 PID 复用 |
| `stackcore.aicpu_scheduler*` | 一类 Stackcore 命名线索，不代表所有版本固定命名，也不说明根因已定位 |
| atrace / native 栈 | 记录来源、故障线程、符号匹配及覆盖；存在 CANN 帧不直接确认责任，缺少 CANN 帧不排除更早写入者 |

## 证据与定位

核对已有 input、stdout、plog、device、atrace、message、退出记录及 core 的时间与
实体；没有某类材料时说明限制，继续分析可见机制。缺少超时日志或 plog 较小只
提示覆盖、退出或进展差异，不能直接认定某 rank 先退出。

定位 core 时沿 Device/组件、时间窗和 `subProcPid` 到
`slog/dev-os-*/debug/device-os/` 与 `stackcore/dev-os-*/`；同名 PID 不能替代事件
匹配。符号和 exe/so 核对架构、build-id、版本及加载映射，再解释故障指令和栈帧。
已有文件的离线命令见 [命令手册](coredump-command-playbook.md)。

栈顶只定位观测时执行点。`strcmp`/`memcpy` 还可能访问悬空、越界或损坏的非空
地址；对象分配、释放、参数流或更早写入者可能不在当前栈。ABI 入参寄存器在
函数内部可被改写，不能把故障点寄存器直接等同原始入参。先解释直接失败，再
比较有证据的上游原因及相应条件修复。

### ACLNN executor 所有权与重复释放

ACLNN 二阶段调用附近出现 `double free`、释放时崩溃或悬空对象时，核对
`aclOpExecutor` 的模式和调用顺序。官方 opbase v8.5.0 与 v9.0.0-beta.2 的契约为：

| 模式 | 生命周期 | 对应检查与修复 |
| --- | --- | --- |
| 普通、未启用复用 | 一阶段生成 executor，二阶段由框架自动释放 | 若调用方在二阶段后再次销毁或使用该 executor，修正重复释放/使用；新一轮执行取得新的 executor |
| 已成功启用复用 | 一阶段后立即调用 `aclSetAclOpExecutorRepeatable`，二阶段保留 executor | 使用结束后由调用方以 `aclDestroyAclOpExecutor` 销毁；检查重复销毁、过早销毁及未清理 |

先从已有源码、调用记录或有效栈确认释放的对象与复用设置是否成功。
只有 ACLNN 附近的 allocator 报错时，可将 executor 所有权列为有 API 依据的
优先检查方向，同时保留 tensor、workspace 或更早内存破坏等有依据的候选；
不能直接宣布 executor 就是被重复释放的对象。`free()` 栈顶也不证明 glibc 缺陷。
失败返回不表示调用方必然仍拥有 executor：公开实现的部分错误分支同样销毁对象，
应核对匹配版本、实际 API 路径及返回分支，再决定清理方式。

修复后在原调用方式下核对资源释放次数和完整运行结果；若要切换为复用模式，
先确认对应算子和调用满足该版本的复用约束，不能仅为绕开崩溃盲目启用。
executor 的 Host 管理规则不证明异步 Device 任务已完成，也不替代输入、输出和
workspace 各自的有效期检查。

来源：[v8.5.0 销毁契约](https://gitcode.com/cann/opbase/blob/b27e949de1ce29df366a279adf3976f2660e669c/docs/zh/nnopbase/aclnn/aclDestroyAclOpExecutor.md)、
[复用约束](https://gitcode.com/cann/opbase/blob/b27e949de1ce29df366a279adf3976f2660e669c/docs/zh/nnopbase/aclnn/aclSetAclOpExecutorRepeatable.md)、
[v9.0.0-beta.2 销毁契约](https://gitcode.com/cann/opbase/blob/ed5bab5da501bc4af61d0518b70f9b3689582a74/docs/zh/nnopbase/aclnn/aclDestroyAclOpExecutor.md)。
普通与复用分支见两个发布版的 `src/nnopbase/composite_op/aclnn_engine/op_executor.cpp`
中 `CommonOpExecutorRun`，显式销毁见 `src/nnopbase/common/api/acl_op_api.cpp`。
这些公开标签不保证对应所有商用包或后续版本，使用时核对现场配套。

### x86 对齐异常与信号地址

x86 的 SSE `MOVAPS` 内存操作数要求 16 字节对齐，未对齐可触发 `#GP`。
Linux x86 的用户态 `#GP` 路径可生成 `SIGSEGV/SI_KERNEL`，此路径不提供实际
访存地址。因此报告中的 `addr=(nil)` 不总是指令访问了地址零，也不能反解
出基址寄存器；用假设的零地址做减法或对齐运算只验证该假设下的算术。
需结合匹配指令、现场寄存器、`si_code`/trap 信息和映射区分地址映射、对齐及
其他保护异常；缺这些值时保留分支，不写“已验证空指针”或“已排除对齐”。

替包前后的一次成功/失败支持该输入的构建或依赖差异候选，不能据此推广为
所有调用方必崩或整个包已定责。比较相同复现条件、实际加载库、构建选项及
对象/栈对齐；回退后的业务结果和包级影响范围分别验证。

来源：[Intel SDM Volume 2B，MOVAPS](https://cdrdv2.intel.com/v1/dl/getContent/671241)；
Linux v6.12 的 [gp_user_force_sig_segv](https://github.com/torvalds/linux/blob/v6.12/arch/x86/kernel/traps.c#L684)
与 [force_sig](https://github.com/torvalds/linux/blob/v6.12/kernel/signal.c#L1666)。
这些说明限定于相应指令和操作系统路径，不把 x86 语义套到 AArch64，也不证明
现场就是 `#GP`。

## 机制索引

以下 C001-C005 保留原编号用于检索；本库没有其完整原始现场、修复和复跑记录，
它们是机制参考，不是已验证案例或本次命中证明。

| 编号 | 方向 | 区分所需证据 |
| --- | --- | --- |
| C001 | AICPU/Device 中断 | 关联 Device 异常退出、信号或 Stackcore；不能仅用 E39999 和日志缺失 |
| C002 | HDC 关闭与 Device 状态 | 会话、任务及关闭/退出顺序，区分正常清理和异常传播 |
| C003 | 某 rank 提前退出后其他 rank 等待 | 真实退出原因、生产者依赖、参与集合及可靠时序 |
| C004 | TDT 相关 Device 中断 | 匹配的组件、subProcPid、故障时窗、Stackcore 与符号 |
| C005 | core 材料缺失 | 实际生成/保存/导出/清理证据及转储模式，不由文件未找到反推开关 |

### C001：AICPU/Device 中断

匹配的异常退出或 Stackcore 支持 Device 中断。继续定位故障线程、指令与参数，
区分直接触发和上游原因；没有 core 时仍可解释已有异常，不编造源码位置。

### C002：HDC 会话关闭

HDC 也在正常析构时关闭。先关联会话和任务，再核对对端活动、取消、退出或
异常记录。关闭不能直接确认 Device 崩溃，也不能据此排除 Host/HDC 路径。

### C003：提前退出与等待传播

以真实退出记录和任务依赖证明参与者无法推进后，追其 OOM、信号、业务异常或
外部终止原因。GE 清理、析构、文件大小和未报超时只提供检索线索。

### C004：TDT 相关中断

组件名和 PID 帮助找到材料；故障是否由 TDT 内部逻辑、输入、生命周期或其他
路径引起，需匹配栈、指令和更早事件，不由当前组件名直接定责。

### C005：core 材料缺失

按 [core 保存条件](coredump-reference.md#core-生成与保存条件)核对实际模式。
未找到文件先记材料缺口；已有配置或处理器失败证据支持时才确定缺失原因。

## 结论边界

没有 core 或符号仍交付已知中断事实、局部机制、候选及缺口。没有实际修复和
原条件/回归执行记录时，验证是计划，不能宣称解决。流水线产物约定见
[处理流](fault-flows/crash-flow.md#子步骤产物)，普通诊断直接交付完整正文。
