# AI Core 字面字段视图

本文的字段语义和证据边界见[现场字段语义](diagnostic-field-reference.md)。

大日志先用`--summary`扫描字面异常签名，仍从技能包根目录执行：

```bash
python3 eval-skill/scripts/extract_aicore_evidence.py --input <已解压日志目录或文件> --summary --max-file-bytes 268435456 --max-total-bytes 536870912
```

该视图按来源文件及同一物理行上的`error_code/mte_error_code/errcode/error_str`精确分组，
保留完整多值和多句文本、逐行次数及首末原始观测。首末行的其他字段和PC减法仅属于该行，
不代表组内全部值一致；相同签名不等于同一任务或同一上游原因。它不会跨行关联header、
扩展解释或task，也不解析数字的设备位定义。无这些字段的行不会进入签名汇总。
`--max-observations`不限制汇总扫描；字节、文件和编码限制仍生效。
默认最多200组，可用`--max-summary-groups`调整。组数超限后仍扫描并更新已保留组，
`omitted_observations`记录未纳入组的观测条数，不冒充不同签名个数；此时整体为`partial`。
确认文件覆盖、无遗漏后，按每类来源行回读完整上下文，不能只凭次数作根因判断。

需要从现有文本日志提取多项 AI Core 字段或核对长 hash 时，从技能包根目录执行：

```bash
python3 eval-skill/scripts/extract_aicore_evidence.py --input <已解压日志目录或文件> --max-observations 200
```

命令只向stdout打印单行JSON，不创建文件；需要人工缩进时加`--pretty`。通过`--max-observations`控制输出，保持JSON完整，避免用`head`切断记录；工具返回或读取发生截断时，继续核对未读范围。`observations`保留`source/line/raw/fields`，hash等数值保持字符串；同一行同名字段重复时保留为列表，不能取第一个值冒充唯一值。`para base`与参数值分别存为`parameter_block_address/arguments`，before/after保留各自阶段；不跨行拼接任务，不合并重复来源。只有同一行出现对应kernel或PC标签时，才提取kernel hash或current PC；未提取不表示原文不存在。

`complete`只表示本次选定扫描范围完成，不代表诊断完成。`files`逐项报告已读字节、大小及错误；默认每文件16 MiB、总64 MiB、10,000条观测、1,000文件，上述示例把观测数降为200以控制输出。遇到`partial`、读取失败或任一限额时，对未读文件及尾部用原文检索或缩小输入范围继续检查，不把前缀当完整现场。工具适用于稳定的已解压UTF-8文本目录；二进制、其他编码、符号链接须另行处理。

按来源回读完整上下文后再解释字段。结构化提取不证明指针合法、任务全集、重复来源独立或因果关系；仍遵守上文的字段语义和证据边界。

视图将`mte_error_info`与`mte_error_code`等原始字段分别保留，数值本身不作为故障位解码。schema 1.1在同一原文行的PC起点和当前值均唯一且不超过16个十六进制数字时，另给`calculations.pc_offset_bytes`，包含减法的操作数、十进制/十六进制结果及字节单位。多值、缺值或过长时只保留原字段，不计算，也不跨行配对。这只是代码地址差，不能从中推出执行顺序、耗时或确定性。
