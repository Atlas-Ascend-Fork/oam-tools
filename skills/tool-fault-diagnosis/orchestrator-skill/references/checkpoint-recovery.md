# 断点恢复

状态位于 `.cann-orchestrator/state.json`（version=2），只由 runner 管理；
业务产物由各 skill 按 [统一 Markdown 契约](pipeline-artifacts.md) 交付。

## 状态字段

| 字段 | 含义 |
| --- | --- |
| version / run_id / created_at / updated_at | 控制状态版本、当前分析 ID、时间 |
| stages.<step>.status | pending/running/success/skipped/failed/blocked |
| attempts / failures | 执行尝试序号、自动重试预算所用失败次数 |
| revision | 使显式重跑及其下游失效的修订标识 |
| inputs_fingerprint | 输入材料、参数、脚本和上游依赖的 SHA-256 |
| artifact_sha256 | 已提交主 Markdown 内容 SHA-256 |
| last_error | 当前步骤最近执行错误 |

每个步骤保留一个当前主产物。
附属日志、清洗映射等通过 `outputs` 路径和 SHA-256 校验；原始材料按文件内容哈希，不能仅凭 mtime 或文件大小。

## 恢复决策

1. `--resume`：复用成功且全部指纹相符的步骤；最早失效步骤及其下游重新处理。
2. `--restart-from clean`：显式使 clean 及下游重新处理。
3. `--only confidence`：先校验前驱，只执行该步，并使下游失效；不是允许保留旧报告的快捷方式。
4. 输入材料、案例库、参数、脚本或前置产物内容变化，均不能用旧成功文件伪装为本次结果。
5. 上次 running 的步骤可以恢复；blocked 缺少新产物时继续等待，不循环消耗重试预算。
6. 接纳 Agent 产物必须同时通过公共字段、当前 run/stage/inputs、业务字段与附件校验。
7. 本次受控入库产生的案例库变化由 receipt 记录，不能在同一次恢复时误判自己刚完成的案例检索失效。

## 一次 Agent 交接

运行停止后打开 `artifacts/diagnosis.md`：保留外壳中的 run_id、stage、attempt、inputs；
根据路由文档填写 result 与人读正文，逐项审核 17 个 checks，将 result.analysis_status 从 draft 改为 reviewed，
设 status=success、finished_at 为完成时间。只有用户明确要求证据摘要时才使用 analysis_status=evidence_only；
该状态不表示已经完成根因诊断。
随后 `--resume` 执行真实评分；report 交接采用相同方法。证据不足也应如实完成结论边界，不能伪造证据凑字段。

## 锁与状态

状态与 Markdown 均通过临时文件后原子替换保存；`pipeline.lock` 包含进程、主机和令牌，防止双跑。
只有确认原进程结束时才可 `--force-unlock`，活进程或无法核实的进程不接管。
退出码：0 完成；1 执行失败；2 参数/契约不满足或等待 Agent 的 blocked；3 状态/锁冲突。
读取具体 status 和 next_action 区分 blocked 与失败，不把非零退出统一当作需要重试。
