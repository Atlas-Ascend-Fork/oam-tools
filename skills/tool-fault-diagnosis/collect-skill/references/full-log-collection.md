# 全量日志采集流程

用户要求“采集所有日志”等全量采集时，在 `collect.sh --all` 基础上完成本流程。这里的目录名是归档约定；工具内部生成的文件和目录保留原样。不要为了制造日志而重跑任务、开启 profiling 或触发崩溃；需要复现时遵循用户已授权的任务范围。

## 1. 基础采集与路径核对

为本次采集创建独立输出根目录 `<collection_root>`，多机使用 `<collection_root>/<hostname>/` 分开存放。下文 `<node_root>` 表示单机输出目录；将占位符替换为实际路径后执行命令。

```bash
bash <skill_root>/scripts/collect.sh --all --output <node_root>
```

检查实际 CANN 安装位置及运行用户。脚本默认按 `CANN_HOME`、`ASCEND_INSTALL_PATH`、`ASCEND_HOME_PATH` 及常见安装路径（`/usr/local/Ascend/`、`$HOME/Ascend/` 下的 `cann`、`ascend-toolkit/latest`、`ascend-toolkit/*`、`cann-*` 等）自动探测 `<cann_home>/log`，同时使用 `/var/log/npu/slog`、`/var/log/npu/driver` 和 `${ASCEND_LOG_PATH:-$HOME/ascend/log/plog}`；实际路径不同的日志在下一步补采。特别检查 `$HOME/ascend/log/debug/plog/`、应用工作目录和运行用户的日志目录，不能只检查采集用户的 `$HOME`。

脚本的日志复制只匹配 `*.log`，IR 搜索只取前 50 项且平铺复制，部分命令失败会被忽略。因此，脚本退出成功或存在 `manifest.txt` 都不能作为完整性判据。

## 2. 补齐已有文件

检查以下来源，将基础脚本未覆盖的文件复制到 `supplement/<来源>/`，保留原有子目录、主机、设备和 rank 信息。对已有日志目录可使用 `cp -a <source_dir> <destination_dir>`；不要把输出目录放在被递归复制的源目录中。只读取与目标 CANN 任务相关的运行目录，不遍历无关用户数据。

| 来源 | 应补采的内容 |
|------|----------------|
| slog / CANN / Driver / plog | 已有日志目录中的轮转日志、压缩日志及其他日志文件；包括实际安装路径、自定义 `ASCEND_LOG_PATH`、`ASCEND_WORK_PATH` 下的日志和所有相关 rank |
| Host | 可访问的 `/var/log/syslog`、`/var/log/messages` 及其轮转文件；完整 `dmesg` 和 `journalctl --no-pager` 输出。用户指定时间范围时对 journal 使用 `--since`/`--until`；基础脚本的 journal 默认只有最近 1000 行，dmesg 仅包含关键字匹配行 |
| 应用 / HCCL | 任务 stdout/stderr、训练或推理框架日志、任务目录 `hccl_logs/` 或实际 HCCL 输出目录 |
| profiling / 图编译 | 已有 profiling 输出目录、相关 `.ir` / `.dot` 文件，保留路径以避免同名文件覆盖；profiling 参考路径为 `$HOME/ascend/log/profiling/` |
| 崩溃 / AI Core Error | 已有 Linux core/coredump、Stackcore、exception dump、Device event 日志、对应算子 `.o`/`.json`；保留关联的可执行文件、依赖库、可用符号文件及版本/hash 信息 |
| 已有分析结果 | 已生成的 gdb/asys 分析目录、msaicerr 完整 `info_<timestamp>/`，包括 `info.txt`、`debug_info.txt` 和复现脚本；不要只收集结论文件 |

记录任务启动命令、故障时间和时区、PID/rank/Device ID，保存可获取的 OS、CANN、Driver、Firmware、框架版本及设备状态。无法定位任务目录或 core 路径时记录缺失信息，同时继续其他来源采集。

## 3. 导出 Device 和综合现场

发现实际安装的工具后，先查看其帮助确认当前版本支持的参数。每个工具单独记录命令、退出码和标准输出/错误；工具不存在或执行失败时记录原因并继续其他采集，不要将空目录标记为成功。

### msnpureport

`collect.sh` 的 `--msnpureprot` 只复制本地文件；完整 Device 现场需要另行导出。在新的可写目录运行实际 Driver 安装路径下的工具：

```bash
mkdir -p <node_root>/msnpureport
cd <node_root>/msnpureport
<driver_install_path>/driver/tools/msnpureport --help
<driver_install_path>/driver/tools/msnpureport report -a
```

若当前版本不支持 `-a`，按帮助使用支持的全设备导出方式或逐设备导出，并核对覆盖情况。保留生成的整个时间戳目录，通常包含 `slog/`、`message/`、`hisi_logs/`、`stackcore/`，部分版本还有 `event_sched/`、`module_info/`。目录内容随版本、设备状态和部署形态变化。

### asys

加载实际 CANN 环境后，使用当前版本支持的主动采集命令：

```bash
asys collect --help
asys collect --tar=True --output=<node_root>/asys
```

保留完整目录和压缩包，特别是 `software_info.txt`、`hardware_info.txt`、`status_info.txt`、`health_result.txt`、`dfx/` 及日志/Stackcore 相关文件。普通全量采集使用 `asys collect`；`asys launch` 会运行任务，仅在用户要求复现采集时使用。

## 4. 完整性与交付

在 `<node_root>/collection_status.md` 记录每个来源的源路径、产物路径、采集命令/退出码、文件数量、非空检查、可确认的时间范围及节点/Device/rank 覆盖情况。状态使用“已采集”“缺失”“不适用”“失败”，并注明原因；文件存在但为空、工具报错、关键设备未覆盖时不能标记为完整成功。

全部补采和状态记录完成后刷新清单，避免清单计入自身：

```bash
find <node_root> -type f ! -path '<node_root>/manifest.txt' | sort > <node_root>/manifest.txt
```

交付实际输出路径、各来源结果和待补材料；用户需要归档时再打包，并给出压缩包路径。若某些日志尚未生成、已经轮转删除、工具不可用或权限不足，明确说明当前采集范围和缺口。
