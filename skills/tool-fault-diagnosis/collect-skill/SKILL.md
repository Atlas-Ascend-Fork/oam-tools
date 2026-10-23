---
name: collect-skill
description: 采集 Ascend NPU / CANN 的日志和故障现场。当用户要求“采集所有日志”“收集所有日志”“采集全量日志”“全量日志采集”“一键采集日志”“收集完整日志”，或需要补采、汇总多源日志时使用此技能。支持本地 slog、Host、plog 及 msnpureport/asys 现场导出；已有完整日志且只要求分析时使用 eval-skill。
license: Apache-2.0
---

# 日志采集技能 (Collect Skill)

## 适用场景

- 算子或训练/推理任务执行后，需要从运行环境中采集日志
- 日志分散在多个来源（设备日志、宿主机日志、框架日志）
- 需要对齐时间戳、合并多路日志

## 触发与采集范围

本 Skill 是 `tool-fault-diagnosis` 的采集入口。以下请求均进入全量采集流程：

```text
采集所有日志
收集所有日志
采集全量日志
全量日志采集
一键采集日志
收集完整日志
帮我把 CANN 的日志全部收集起来
```

用户未限定日志类型时，默认采集所有来源；明确指定 plog、Host、设备或时间范围时遵循其范围。全量指目标运行环境中现有、可访问的各类日志及现场，覆盖相关节点、设备和 rank；缺失材料必须列出，不能将部分采集描述为全量成功。

## 平台信息

从目标现场记录Host架构、NPU型号、可见设备、CANN/Driver/Firmware及框架版本、实际安装路径。核数、UB与HBM容量取对应型号和配置；不能把脚本中的历史默认路径或规格当成现场事实。

## 采集来源说明

| 来源 | 说明 | 参考文档 |
|------|------|----------|
| msnpureprot（脚本旧名称） | 复制本地slog及CANN安装目录日志；不是协议名，也不会自动执行msnpureport导出 | `references/msnpureprot-collection.md` |
| host 日志 | 宿主机侧系统日志，包含设备挂载、内存分配、进程状态等信息 | `references/host-log-collection.md` |
| plog | CANN 框架运行时日志，记录图编译、算子调度、执行时序等 | `references/plog-collection.md` |
| 全量补采 | 轮转日志、应用/HCCL/profiling、msnpureport/asys、已有 core/Stackcore/dump 和环境信息 | [全量采集流程](references/full-log-collection.md) |

## 采集步骤

1. **确认环境**：确定任务所在的 Linux Ascend 主机、运行用户、CANN/Driver 路径和输出目录，检查设备可见性及日志读取权限。已知连接信息时直接使用；只有无法确定目标主机时才询问。不要在无 NPU 的开发机上采集并宣称获得了目标日志。
2. **执行基础采集**：全量请求使用 `scripts/collect.sh --all`，默认不传时间过滤参数；使用新的输出目录，避免混入旧产物。脚本路径相对于本 Skill 安装目录解析，不依赖用户当前工作目录。
3. **完成补采**：全量请求必须读取并执行 [全量采集流程](references/full-log-collection.md)。脚本只复制部分本地日志，`--all` 不会自动调用 `msnpureport`、`asys`，也不会收集全部轮转文件、应用日志、profiling 或崩溃材料。
4. **验证完整性**：检查产物非空、时间覆盖、节点/设备/rank 覆盖，记录每个来源的成功、缺失、不适用或采集失败状态。某个来源失败时继续采集其他可访问来源，保留失败原因。
5. **交付**：补采结束后更新文件清单，输出采集目录、清单、各来源结果及待补材料。用户要求采集时实际执行可用命令并交付产物；已有完整日志且用户要求分析时再进入评估 Skill。

## 使用采集脚本

```bash
# 采集所有日志源
bash scripts/collect.sh --all --output ./logs/

# 仅采集 plog
bash scripts/collect.sh --plog --output ./logs/

# 指定时间范围采集
bash scripts/collect.sh --all --start "2026-03-25 10:00:00" --end "2026-03-25 11:00:00" --output ./logs/
```

## 输出物

- `logs/msnpureprot/`：本地 slog 和 CANN 安装目录日志，保留源路径层级；名称沿用脚本，与 `msnpureport` 工具导出目录不同。
- `logs/host/`：内核/系统/驱动日志、`npu_smi_info.txt`、`memory.txt`、`disk.txt`、`processes.txt`。
- `logs/plog/`：框架日志及 `ir/` 下的 `.ir`、`.dot` 图文件。
- `logs/supplement/`、`logs/msnpureport/`、`logs/asys/`：全量流程按实际环境补充的原始文件和工具导出产物，目录约定见全量采集参考。
- `logs/collection_status.md`：全量流程记录的各来源状态、执行结果、覆盖范围和缺失项。
- `logs/manifest.txt`：最终文件清单，补采后刷新。

`merged.log` 和压缩包需要另行生成，脚本不会自动产出；合并或打包时保留原始文件。


## 与统一调度的边界和清单交付

本skill提供明确安排的初始采集，已有日志进入七步分析流水线后不因缺证、失败或低评分再次调用采集。
初始采集除原日志外交付collection.md；字段见 [产物契约](../orchestrator-skill/references/pipeline-artifacts.md) 的前置collection.md一节。
清单记录collection_id/status/时间/environment/source_root/time_window/files/missing_sources/errors/next_action。
files必须含原路径、类型、字节数、SHA-256、时间范围和可核实实体。记录实际成功与失败，不能因命令退出就宣称材料完整。
采集脚本只负责文件操作，skill负责从实际输出生成清单；集合关系/时钟未核对时不声称日志已形成统一时间线。
