# CANN Coredump Expert Report Template

Use the evidence and analysis sections to structure the final answer. Write in Chinese by default and include concrete evidence, not only conclusions. Default diagnosis replies explain confidence per claim and do not create scoring or archive files. The numeric score and case maintenance sections below apply only to an explicitly requested pipeline report or case maintenance task.

## 1. 问题摘要

- 结论：`<已确认的直接机制、最可能的上游原因及尚未确定的细节；每项按实际证据表述。>`
- 影响范围：`<进程/服务/模型/设备/版本/复现概率>`
- 崩溃位置：`<模块/文件/函数/行号；未知则写未解析原因>`
- 崩溃类型：`<SIGSEGV/SIGABRT/Device Stackcore/其他>`
- 可信程度：`<已确认机制、上游候选和未决细节的证据及限制>`；流水线报告另附第10节评分

## 2. 输入材料与完整性

| 类型 | 路径/来源 | 状态 | 备注 |
| --- | --- | --- | --- |
| core/stackcore | `<path>` | 已提供/缺失/不匹配 | `<说明>` |
| 可执行文件 | `<path>` | 已提供/缺失 | `<说明>` |
| CANN/Driver/Firmware | `<version>` | 已确认/待确认 | `<说明>` |
| debug so/符号 | `<path>` | 完整/部分/缺失 | `<说明>` |
| msnpureport/asys 输出 | `<path>` | 已提供/缺失 | `<说明>` |
| 源码仓 | `<git url/ref 或 local path>` | 已匹配/待确认 | `<说明>` |

完整性判断：

- `<哪些证据足以支持结论>`
- `<哪些缺口会影响根因准确性>`

## 3. 环境与版本

- OS/Kernel/Arch：`<uname/os-release/arch>`
- CANN Toolkit/Runtime：`<version>`
- Driver/Firmware：`<version>`
- 运行形态：`裸机/容器/EP/非EP/未知`
- 设备信息：`<npu-smi info 摘要>`
- 业务入口：`<命令行、模型、算子、输入规模、环境变量>`

## 4. 关键证据链

### 4.1 崩溃线程与堆栈

```text
<粘贴最关键的 bt full / asys stackcore 片段，保留帧号、函数、文件、行号、模块>
```

解释：

- 崩溃线程：`<thread id/name>`
- 顶层帧：`<frame #0>`
- 首个业务/CANN 有效帧：`<frame #n>`
- 异常地址/寄存器：`<pc/sp/lr/fault address>`
- 符号解析状态：`完整/部分/缺失`

### 4.2 日志时间线

| 时间 | 来源 | 级别 | 内容 | 判断 |
| --- | --- | --- | --- | --- |
| `<time>` | `<slog/message/app log>` | `<level>` | `<key line>` | `<first error/secondary cleanup/noise>` |

### 4.3 符号与源码匹配

- 符号路径：`<debug so/symbol path>`
- Build ID/版本匹配：`<匹配/不匹配/未确认>`
- 源码 ref：`<git url + commit/tag/branch>`
- 定位文件：`<file:line>`
- 关键代码路径：

```text
<短代码片段或伪代码说明；不要粘贴大段源码>
```

匹配结论：

- `已由源码证实：<事实>`
- `由堆栈推断：<推断>`
- `仍需复现确认：<问题>`

## 5. 根因分析

### 5.1 直接触发点

`<说明崩溃发生在什么函数、访问了什么对象/地址、为什么触发信号或 abort。>`

### 5.2 上游原因

`<说明该非法状态如何进入崩溃函数，例如空指针、越界、生命周期、并发、版本/ABI 不匹配、Device 侧异常传播等。>`

### 5.3 排除项

- `<已排除的假设及证据>`
- `<未能排除的假设及原因>`

## 6. 修复建议

### 6.1 代码修复

- `<建议修改的文件/函数>`
- `<需要增加的校验、生命周期约束、同步、错误处理或版本检查>`
- `<建议日志或断言>`

### 6.2 版本/部署修复

- `<CANN/Driver/Firmware/debug so/业务二进制需要对齐的项>`
- `<容器挂载、LD_LIBRARY_PATH、符号包、运行用户等修复建议>`

### 6.3 临时规避

- `<可降低影响的配置、降级、禁用路径、复启策略或输入约束>`

## 7. 验证计划

- 复现验证：`<如何稳定复现或确认不再复现>`
- 单元/集成测试：`<覆盖触发条件和边界>`
- 压力/并发测试：`<如适用>`
- 回归观察：`<日志关键字、指标、core/stackcore 是否再出现>`

## 8. 待补充材料

- `<缺失 core/exe/debug so/source ref/log 的具体项>`
- `<为什么这些材料重要>`
- `<拿到后下一步做什么>`

## 9. 附录：执行过的关键命令

```bash
<gdb/asys/msnpureport/git/rg/readelf/addr2line 命令>
```

## 10. 流水线报告的完整性评分

按 [confidence-assessment.md](confidence-assessment.md) 五维模型评分，
用 `scripts/assess_confidence.py` 计算。总分描述材料完整程度，不代替逐项因果证据；缺证时仍保留已证实机制和有依据的候选根因，不自动补采。

- 综合可信度：`<score>/100（HIGH/MEDIUM/LOW/INSUFFICIENT）`
- 维度得分：证据完整性 `<x>`/25 · 证据一致性 `<x>`/20 · 因果链 `<x>`/25 · 复现验证 `<x>`/15 · 知识对齐 `<x>`/15
- 入库关键项：`<全部满足 / 首报错日志行未定位 / 因果链存在跳跃>`

崩溃场景两项最容易失分：符号缺失会让栈帧函数名不可信（影响 D1），
版本/ABI 未确认会让符号与源码映射整体失效（影响 D1、D5）。

| 类别 | 内容 |
| --- | --- |
| 已证实事实 | `<由源码/复现/多源日志证实>` |
| 仍属推断 | `<推断内容 + 缺哪一步证据>` |
| 已排除 | `<假设 + 排除依据>` |

- 逐项证据状态：`<已确认机制 / 候选根因 / 未决细节及对应依据>`

## 11. 案例维护任务的入库处置

按 [case-contribution.md](case-contribution.md) 判定：

- 入库判定：`<accept / pending / reject>`
- 去向：`<cases.md CASE-xxx / cases-pending.md PCASE-xxx / 不入库>`
- 判定理由：`<可信度等级、关键项、修复验证状态>`
- 脱敏确认：`<已清理 IP/主机名/家目录/凭据 / 无敏感信息>`
- 重复检查：`<无同类案例 / 已合并到 CASE-xxx>`

沉淀命令：

```bash
python3 scripts/promote_case.py --report <本报告> --confidence confidence_result.json
```

## Report Quality Bar

Before finalizing, check:

- 是否明确区分 Host core、Device Stackcore、msnpureport 日志。
- 是否说明 core 与 exe 是否匹配。
- 是否说明 debug so/符号是否完整。
- 是否给出源码仓 ref，而不只是文件名。
- 是否避免在证据不足时下确定性结论。
- 是否给出可执行的修复和验证建议。
- 是否区分「已证实」与「仍属推断」，并说明各自证据；流水线报告另核对完整性分数与关键项。
- 明确执行案例维护时，是否给出入库判定；判定为 accept 时是否已完成脱敏和重复检查。
