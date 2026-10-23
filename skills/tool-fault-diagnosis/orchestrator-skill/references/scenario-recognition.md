只检索 `eval-skill/references/cases.md` 的 CASE 块内“关键日志特征/日志特征签名/Signature”段。
不搜索候选区，不从根因、解决方案段落反向吸取关键词。用户话术参与分类，但不冒充现场日志用于案例命中。
识别决定分析入口，不决定根因。输入是已提供的目录、单文件或 ZIP 以及用户描述。
泛化的“分析日志/诊断故障/生成完整诊断报告”请求入口固定记录为
`route.entry_skill=orchestrator-skill`，下游按现场协调 eval-skill、trace-skill、metric-skill 等能力；用户明确指定
专项 skill 或已提供上游评估产物时才允许专项直达。日志内容中的 AI Core Error、coredump 等词本身不改变入口。

## 1. 案例检索

已验证案例只检索 `eval-skill/references/cases.md` 的 CASE 块内“关键日志特征/日志特征签名/Signature”段。
不从根因、解决方案段落反向吸取关键词。用户话术参与分类，但不冒充现场日志用于案例命中。

每个签名行与当前原始日志行核对：除 EZ9999 外的相同明确错误码，或同一行同时包含相同模块、操作和故障特征，才生成候选。
单个 ERROR、HBM、timeout 等泛词不足以命中。EZ9999 是外层包裹码，不能单独定位案例。
命中后记录实际日志位置、匹配特征、未匹配签名、版本/环境适用性未核实项，root_cause_status=candidate_only。
未命中记 miss；案例库不可读或无可解析签名记 unavailable 并说明原因。三种结果都继续现场分类。

自动命中只允许读取主案例库 `cases.md`。`cases-pending.md` 是补证候选区，专项 reference 案例是人工排查知识库，二者都不参与自动命中；后续若要复用其中高价值案例，必须先补证、重评并按流程转正为 CASE。用户描述只参与场景分类，不参与案例命中。命中案例仅代表日志签名相似，必须继续核对版本、环境和当前证据，不能直接作为根因。

案例检索和现场分类都保留入口 `errors` 数组。数组逐条记录原始错误证据的位置、原文、级别、错误码、关键字和时间戳（如有），不因场景未知而丢弃未映射的错误码；否定描述和仅用于配置的超时文本不计入错误证据。

## 2. 分类表

| 场景 | 强现场信号或关键条件 | 路由 |
| --- | --- | --- |
| crash | SIGSEGV/SIGABRT、Segmentation fault、core dumped、未捕获致命异常 | fault-flows/crash-flow.md + coredump 手册 |
| aicore_error | 明确 aicore/aivec error exception、fault kernel_name、错误寄存器详情 | fault-flows/aicore-error-flow.md |
| oom | 内存分配失败、EL0004、OOM Killer 明确事件 | fault-flows/oom-flow.md，侧别与细分交诊断核实 |
| hang | no progress for/detected、deadlock detected、task not finish | fault-flows/hang-flow.md |
| comm_timeout | HCCL/集合通信操作与 timeout 同行，或明确通信超时码 | fault-handling.md + hang-flow.md 通信竞争分支 |
| card_drop | npu-smi 查不到卡、EL0001 Device_Absent/Abnormal、PCIe link down、BMC 告警卡消失 | fault-flows/card-drop-flow.md + card-drop-reference.md |
| compile_error | 编译操作明确失败、UB memory overflow、EB 类编译码 | background.md + err-messages.md |
| precision | 明确非有限数值结果，或 max_diff 实测超过同条记录给出的 threshold | fault-flows/precision-flow.md + err-messages.md |
| perf_degradation | 明确性能下降/回归记录或用户描述 | fault-flows/performance-flow.md + metric 基线与分析文档 |
| offline_inference | ATC 报错/模型转换失败、soc_version 不匹配、离线推理报错、参数校验失败 | fault-flows/offline-inference-flow.md |
| network | EI0013 ROCE CQE 错误、端口闪断/Down、网络诊断异常、丢包记录；EI0002/HCCL 超时须有网络侧证据才归本场景 | fault-flows/network-flow.md |
| generic_error | 有错误码/失败但未形成具体专题证据 | err-messages.md |
| unknown | 无足够信号 | 原始证据盘点与一般诊断，禁止猜根因 |

普通诊断按字段疑问查阅 log-spec.md，按当前主/次场景选读相关专项；缺材料时说明具体限制并继续现有证据分析。仅在明确要求完整性评分、案例维护或流水线产物时读取可信度规范。

## 3. 强弱与冲突

- 同一信号只贡献一次分值，重复报错只增加 hit_count，不能刷高识别把握。
- 内容信号分值 20–60，各场景内容分封顶 80；描述信号仅加 12。强现场（content_score≥50）先于话术和文件名。
- 具体强场景存在时 generic_error 退为通用背景，不覆盖专题。
- 多个强场景出现在同一原文件时，原行序可用来选择分析入口；记录全部竞争场景。跨文件不推断统一时序。
- `secondary` 非空、无强信号或扫描有限制则 uncertain=true；强场景通常为 MEDIUM，无歧义且至少两个内容信号才 HIGH；弱线索 LOW，无信号 UNKNOWN。
- 识别等级是路线可靠程度，**不是诊断五维分数**，不能用它修改评分或限制能力。

不能将退出码137认定为OOM，不能由旧core文件名认定本次崩溃，不能由事后低HBM占用认定碎片。
futex_wait 等等待位置只是弱线索；正常心跳、成功事件和退出清理阶段要保留给诊断核对。
同一文件最早可见报错也不自动是首个根因事件，轮转、跨rank时钟和关联实体必须在诊断里检查。

## 4. 原文与扫描边界

默认最多500个文件，每文件读取前8MiB，不做日志级别过滤。可显式调整 --max-files/--max-bytes。
扫描超限时只使用完整前缀行，不把截断的半行当证据，也不拼接尾部后伪造连续行号。
coverage 给出每文件的读取量、已扫/未扫字节区间（0基半开）、原始行号范围（1基）、编码警告或不可读原因。
ZIP 不在识别步骤解压；条目证据写 `archive.zip!member#n:line`，n 用于区别重复文件名。
未知/二进制材料只盘点，不冒充可读日志。未扫描部分不能写“未发现异常”。

材料清单固定 plog/device_log/coredump/stackcore/asys_output/npu_smi/app_log/profiling。
present/count/samples 只是文件名盘点，verification 明确“与本次故障的关联尚未核实”。缺项只记录缺口。

## 5. 执行与交付

```bash
python3 orchestrator-skill/scripts/detect_scenario.py --input ./logs.zip --request "训练卡住" --plan-out plan.json
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json
```

runner 先执行 --phase case_lookup，写 case-match.md，再通过 --case-match 把成功前驱传给 --phase detect，写 scenario.md。
直接执行识别脚本也会先进行真实案例检索。前驱的输入指纹与库hash不一致时拒绝复用。
明确字段见 [产物契约](pipeline-artifacts.md)，异常处置见 [调度与重试](degradation-retry.md)。
