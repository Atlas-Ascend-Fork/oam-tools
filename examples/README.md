# 功能运行示例

简体中文 | [English](./README_en.md)

本目录提供 OAM-Tools 各组件的开箱即用调用样例。完成[编译](../README.md#执行编译)与[安装](../README.md#安装)后，即可参考本文在真实环境中运行示例，快速验证工具功能。

## 目录

- [环境准备](#环境准备)
- [一键运行脚本](#一键运行脚本)
- [asys（故障信息收集与诊断）](#asys故障信息收集与诊断)
- [msaicerr（AI Core Error 分析）](#msaicerrai-core-error-分析)
- [msprof（性能调优）](#msprof性能调优)

## 环境准备

完成安装后，工具会被释放到 CANN 安装目录下的 `tools/` 子目录（root 用户默认在 `/usr/local/Ascend/cann/tools/`）。运行示例前请先加载环境变量：

```bash
# root 用户默认路径；非 root 用户将 /usr/local 替换为 ${HOME}
source /usr/local/Ascend/cann/set_env.sh
# 指定路径安装时：source ${install_path}/cann/set_env.sh
```

> 执行上方命令后，`${ASCEND_HOME_PATH}` 即为 CANN 安装目录：
>
> - root 用户默认：`/usr/local/Ascend/cann`
> - 非 root 用户默认：`${HOME}/Ascend/cann`
> - 指定路径安装：`${install_path}/cann`

## 一键运行脚本

本目录下为各场景预置了可直接执行的脚本，加载环境变量后即可运行：

| 脚本 | 说明 |
| --- | --- |
| [`asys/run.sh`](./asys/run.sh) | 使用 asys 基础命令体检 device 健康状态，入门首选 |
| [`msaicerr/run.sh`](./msaicerr/run.sh) | 运行内置 sample 算子检测软硬件环境是否具备 msaicerr 运行条件，装完即跑 |
| [`msprof/run.sh`](./msprof/run.sh) | 采集 5 秒系统级 CPU/内存性能数据，装完即跑 |
| [`deploy.sh`](./deploy.sh) | 依次执行上述三个脚本，一键跑通全部样例 |

```bash
# 一键运行全部样例
bash deploy.sh

# 或单独运行某个组件的样例
bash asys/run.sh
```

以下章节按组件展开更多命令示例。

## asys（故障信息收集与诊断）

`src/asys/` 目录下同时存在 `asys.py` 和指向它的软链接 `asys`（`src/asys/asys -> ./asys.py`），CMake 通过 `install(DIRECTORY ${ASYS_DIR} ...)` 将整个目录原样拷贝，软链接也会保留。因此安装后两种调用都能直接用：

```bash
# 形式一：显式 python3 调用 .py
python3 ${ASCEND_HOME_PATH}/tools/ascend_system_advisor/asys/asys.py -h

# 形式二：直接调用软链接 asys（asys.py 自带 #!/usr/bin/env python3 shebang）
${ASCEND_HOME_PATH}/tools/ascend_system_advisor/asys/asys -h
```

asys 的子命令在 `src/asys/cmdline/cmd_parser.py` 的 `Command` 枚举中定义，包含 `info / health / collect / launch / diagnose / analyze / config / profiling`。在环境变量加载生效后，可以直接以 asys 调用：

```bash
# 采集主机与 device 的软硬件信息（不依赖待诊断任务，通常作为环境自检）
asys info -r="status" -d=0

# 体检 device 健康状态
asys health

# 采集环境中已存在的运维信息并打包到指定输出目录
asys collect --output <output_dir>
```

更多用法详见 [asys 工具用户指南](../docs/zh/user_guide/asys/README.md)。

## msaicerr（AI Core Error 分析）

msaicerr 入口为 `src/msaicerr/msaicerr.py`，安装后位于 `${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py`。

```bash
# 1) 解析一个已有的 AI Core Error 报告路径，结果输出到 <output_dir>
python3 ${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py -p <report_dir> -out <output_dir> -dev 0

# 2) 解析单个 dump 文件（dtype 取值参见 -h 输出）
python3 ${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py -d <dump_file> -out <output_dir> -dtype float16

# 3) 检测当前环境是否具备运行 msaicerr 所需的条件（仅依赖 device 编号）
python3 ${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py -e -dev 0

# 完整参数说明
python3 ${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py -h
```

更多用法详见 [msaicerr 工具用户指南](../docs/zh/user_guide/msaicerr/README.md)。

## msprof（性能调优）

msprof 由 C++ 侧 collector（`basic`、`dvvp`）和 `msprof` Python wheel（分析脚本）组成。`bash build.sh` 完成后，wheel（`msprof-0.0.1-py3-none-any.whl`）会被拷贝到 `src/msprof/collector/dvvp/msprofbin/` 并打包进 `.run` 安装包；安装时自动解包到 `${ASCEND_HOME_PATH}/tools/profiler/profiler_tool/` 目录下，无需手动 `pip install`。

分析脚本由 msprof collector 流水线内部调用（入口为 `profiler_tool/analysis/msprof/msprof.py`），不会在 `PATH` 中注册独立的命令行命令。如需手动运行分析脚本，可直接以 python3 调用安装目录下的入口：

```bash
python3 ${ASCEND_HOME_PATH}/tools/profiler/profiler_tool/analysis/msprof/msprof.py -h
```

C++ 侧 collector 一般作为 CANN profiler 流水线的内置组件被调用，开发者无需直接执行；回归通过 `bash build.sh -u --component msprof` 运行 gtest 用例（产物 `build/test/ut/msprof/msprofbin/msprof_bin_utest`）。

更多用法详见[性能调优工具用户指南](../docs/zh/user_guide/profiling/README.md)。
