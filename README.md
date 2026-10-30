<div align="center">

# OAM-Tools

简体中文 | [English](./README_en.md)

**CANN 运维工具集（Operations, Administration, and Maintenance）**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CANN](https://img.shields.io/badge/CANN-%E2%89%A58.5.0-green.svg)](./docs/zh/quick_install.md)

</div>

## 📖 项目简介

OAM-Tools（Operations, Administration, and Maintenance）是CANN的开源运维工具集，为昇腾 AI 处理器开发者提供**故障定位**与**性能调优**两大核心能力。工具集覆盖从故障信息采集、AI Core Error 分析到 AI 任务性能采集与分析的完整运维链路，帮助开发者快速定位软硬件问题、优化 AI 任务性能。

**适用场景**：

- AI 训练/推理任务运行异常时，一键采集故障信息、分析 AI Core Error 根因
- AI 任务性能调优，采集各运行阶段关键性能指标，定位性能瓶颈
- 分布式训练场景下，测试集合通信（HCCL）的功能与性能

## ✨ 核心特性

OAM-Tools 包含四大核心组件，协同覆盖昇腾 AI 处理器的运维全场景：

| 组件 | 功能定位 | 核心能力 | 文档 | 运行示例 |
| --- | --- | --- | --- | --- |
| **asys**（故障信息收集） | 一键式故障信息采集与诊断 | 故障信息收集、业务复跑+信息收集、软硬件/Device 状态展示、健康检查、综合检测、组件检测、trace/coredump/stackcore/coretrace/UB 文件解析、实时堆栈导出、AI Core Error 故障信息解析、性能数据采集 | [用户指南](./docs/zh/asys/README.md) | [示例](./examples/README.md#asys故障信息收集与诊断) |
| **msaicerr**（AI Core Error 分析） | AI Core Error 问题定位 | AI Core Error 问题分析、Dump 文件解析与数据类型转换、运行环境检查 | [用户指南](./docs/zh/msaicerr/README.md) | [示例](./examples/README.md#msaicerrai-core-error-分析) |
| **msprof**（性能调优） | AI 任务性能采集与分析 | 采集 AI 任务运行性能数据、AI 处理器系统数据、Host 侧系统数据、msproftx 数据；支持动态/延迟采集；提供 ACL/Ascend Graph/acl.json/环境变量多种采集方式 | [用户指南](./docs/zh/profiling/README.md) | [示例](./examples/README.md#msprof性能调优) |
| **hccl_test**（HCCL 性能测试） | 集合通信功能与性能测试 | 分布式训练/推理场景下，基于 HCCL 单算子 API 测试集合通信的功能正确性与性能 | [用户指南](./docs/zh/hccl_test/README.md) | — |

## 🏗️ 项目架构

OAM-Tools 采用模块化设计，四大组件相互独立又协同工作：asys 与 msaicerr 聚焦故障诊断，msprof 聚焦性能分析，hccl_test 聚焦通信测试。所有组件共享 CANN 运行时环境，通过统一的构建系统（CMake + build.sh）编译打包为 `.run`（默认）/`.rpm`/`.deb` 安装包，安装后释放到 CANN 安装目录的 `tools/` 子目录下。

**目录结构**：

```text
oam-tools/
├── cmake/                      # 构建配置（CMake 模块、第三方库下载脚本）
├── scripts/                    # 辅助构建与检查脚本（oat_check.sh 等）
├── src/                        # 源代码
│   ├── asys/                   # asys：故障信息收集工具（Python）
│   ├── msaicerr/               # msaicerr：AI Core Error 分析工具（Python）
│   ├── msprof/                 # msprof：性能调优工具（C++ collector + Python 分析脚本）
│   ├── hccl_test/              # hccl_test：HCCL 性能测试工具（C++）
│   ├── operator_cmp/           # 算子比对工具
│   └── third_party/            # 依赖的第三方库头文件
├── test/                       # UT/ST 测试用例
├── docs/                       # 项目文档（中/英文）
│   ├── zh/                     # 中文文档（asys/msaicerr/profiling/hccl_test 用户指南）
│   ├── en/                     # 英文文档
│   └── figures/                # 图片资源
├── init_env.sh                 # 开发环境一键安装脚本
├── build.sh                    # 项目编译脚本
├── CMakeLists.txt              # CMake 主配置文件
└── version.cmake               # 版本与依赖声明
```

## 🧩 支持的硬件环境

在搭建环境之前，请先确认硬件在本工具的支持范围内，若无昇腾设备也可以通过 docker 方式编译构建（详见[快速安装](./docs/zh/quick_install.md#方式2docker部署)）。

- **CPU 架构**：`aarch64`、`x86_64`
- **昇腾 AI 处理器**：

  | `npu-smi info` Name 列 | 适用产品 | 对应 CANN ops 包代号 |
  | --- | --- | --- |
  | `910B` | Atlas A2 训练系列产品 / Atlas 800I A2 推理产品 | `910b` |
  | `910_93` | Atlas A3 训练系列产品 / Atlas A3 推理系列产品（业内"910C"对应此项） | `A3` |
  | `950` | Atlas 950 系列产品 | `950` |

  > - `npu-smi info` 实际可能显示带子型号的字符串（如 `910B1` / `910B2` / `910B3` / `910B4`），按"Name 列包含上述关键字"的规则匹配即可。
  > - "910C"是商用别称。自 CANN 8.5.0 起，ops 包统一命名为 `Ascend-cann-A3-ops_*`，请勿在包名中拼写为 `910c`、`910_c`、`910_93` 等形式。
  > - 其它芯片暂不支持，欢迎提交 issue 反馈。CANN ops 包名拼接规则与下载详见[快速安装](./docs/zh/quick_install.md#方式3手动安装)。

## 🚀 快速开始：从零编译到验证

以下为 root 用户默认安装路径下从零跑通的最短路径，四步即可得到可用的工具。第三方库定制、离线编译、调试构建等完整参数，以及分组件的测试验证方式，见后续的「源码编译」与「安装与验证」章节。

### 1. 安装依赖

参考[快速安装指南](./docs/zh/quick_install.md)完成 CANN 软件包与编译依赖的安装。

### 2. 编译

```bash
# 非 root 用户将 /usr/local 替换为 ${HOME}
source /usr/local/Ascend/cann/set_env.sh
bash build.sh
```

编译产物为 `build_out/cann-oam-tools_<cann_version>_linux-<arch>.run`（`<arch>` 为 `x86_64` 或 `aarch64`）。

### 3. 安装

```bash
./build_out/cann-oam-tools_<cann_version>_linux-<arch>.run --full
```

### 4. 验证

重新加载环境变量后调用 asys，能正常打印帮助信息即表示安装成功：

```bash
source /usr/local/Ascend/cann/set_env.sh
asys -h
```

需要在真实环境中跑通各组件功能，见[运行示例](./examples/README.md)。

## 🔧 源码编译

### 加载环境变量

编译前请先根据 CANN 安装路径加载环境变量：

```bash
source <CANN安装路径>/set_env.sh
```

> root 用户默认路径为 `/usr/local/Ascend/cann`；非 root 用户默认为 `${HOME}/Ascend/cann`；指定路径安装时为 `${install_path}/cann`。

### 执行编译

执行以下命令进行编译：

```bash
bash build.sh
```

如需指定第三方库路径，可通过 `--cann_3rd_lib_path` 参数传入：

```bash
bash build.sh --cann_3rd_lib_path=${third_party_path}
```

如需构建 rpm/deb 格式的安装包，可通过 `--pkg-type` 参数指定：

- `--pkg-type=<TYPE>`：指定安装包格式，取值 `run`/`rpm`/`deb`/`deb,rpm`/`all`（`deb,rpm` 与 `all` 为一次构建多种包格式），默认 `run`（`--pkg` 为 `--pkg-type=run` 的别名）。
- 编译产物：run 包为 `cann-oam-tools_<cann_version>_linux-<arch>.run`，rpm/deb 包为 `cann-oam-tools_<cann_version>_linux-<arch>.rpm/.deb`。
- 构建 rpm/deb 包还需 rpmbuild >= 4.14.0 / dpkg（>= 1.19.0.5），仅构建期需要；rpm/deb 包的安装与卸载详见[安装包格式说明](./docs/zh/package_install.md)。

### 编译参数与依赖说明

- `--cann_3rd_lib_path`：第三方库存储目录，默认值为 `./third_party`。若本地不存在第三方库，编译脚本将自动从 gitcode 开源仓库下载各第三方库源码。
- 编译过程中会自动下载闭源二进制包，该包含有保证功能正常运行所需的库及头文件，且仅提供 release 版本，**即使编译选项指定为 debug，也只会下载 release 版本的 tar 包**。
- 闭源二进制包按分支拉取：不指定时，编译脚本会依据当前 git 提交自动探测所属发布分支（从 `master` 拉出的分支拉 master 包，从 9.1.0 线拉出的分支拉 9.1.0 包），探测不出时回退 `master`。也可通过 `--bundle_branch=<NAME>` 显式指定分支，个人分支探测不准时建议显式指定。当前 OBS 上提供包的分支为 `master` 与 `9.1.0`；指定其它分支会在配置阶段报错。
- 编译过程中会通过 `git clone` 拉取 `msprof` 和 `msprobe` 子仓（分别用于构建 msprof 分析 wheel 和同步 msaccucmp 工具）。子仓源码位于 gitcode，使用 HTTPS 协议克隆前需[配置 gitcode 个人访问令牌](https://gitcode.com/setting/token-classic)以替代登录密码，否则克隆会失败。
- 若编译环境无法访问网络，请参考[离线编译环境准备](./docs/zh/quick_install.md#离线编译环境准备)提前完成依赖包的下载与配置，并通过 `--cann_3rd_lib_path` 参数指定依赖包所在目录后再执行编译。离线预置脚本 `cmake/download_libs.py` 同样支持 `--bundle_branch` 指定要预置的闭源包分支（默认自动探测），须与联编时的分支保持一致。
- 闭源二进制包会解压到仓库根目录的 `bundle/` 下。若 `bundle/` 已存在且非空，构建会复用该目录并跳过下载；如需强制重新下载或修复残缺的 `bundle/` 目录，可执行 `bash build.sh --make_clean` 后重新编译，也可手动删除 `bundle/` 后再次执行 `bash build.sh`。
- 更多编译参数请通过 `bash build.sh -h` 查看。

编译完成后，`build_out` 目录下会生成 `cann-oam-tools_<cann_version>_linux-<arch>.run` 软件包，其中 `<cann_version>` 为版本号，`<arch>` 为操作系统架构（可选值：`x86_64` 或 `aarch64`）。

## 📦 安装与验证

### 安装

oam-tools 安装包支持 `.run`（默认）、`.rpm`、`.deb` 三种格式，概览如下：

| 包格式 | 适用系统 | 安装命令 | 安装路径 | 路径自定义 |
| --- | --- | --- | --- | --- |
| `.run` | 通用 | `./build_out/cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}` | `${install_path}` | 支持（`--install-path`） |
| `.rpm` | RHEL/CentOS/openEuler 等 rpm 系 | `sudo rpm -ivh --nodeps <rpm>`（详见[安装包格式说明](./docs/zh/package_install.md)） | `/usr/local/Ascend/cann-<cann_version>` | 不支持 |
| `.deb` | Ubuntu/Debian 等 dpkg 系 | `sudo dpkg -i --force-depends <deb>`（详见[安装包格式说明](./docs/zh/package_install.md)） | `/usr/local/Ascend/cann-<cann_version>` | 不支持 |

rpm 包不支持在 Ubuntu/Debian 上安装，此类系统请使用 deb 或 run 包（背景见[安装包格式说明](./docs/zh/package_install.md)）。

> **注意**：在 CANN 未以 deb/rpm 包方式安装的主机上，通过 deb 包安装本工具后执行 `apt upgrade` 等升级操作会因依赖不满足报错（`apt --fix-broken install` 会移除本包），执行 apt 升级前请先卸载本包，详见[安装包格式说明](./docs/zh/package_install.md)。

可执行如下命令安装编译生成的 oam-tools 软件包：

```bash
./build_out/cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}
```

安装完成之后，用户编译生成的 oam-tools 软件包会替换已安装 CANN 开发套件包中的 oam-tools 相关软件。

> 如果您的环境上 `grep` 版本大于 3.8.0，安装时会出现告警，例如 `grep: warning: stray \ before -`，这是由于 grep 高版本对表达式有更严格的校验，但并不影响安装和使用。

### 验证

编译完成后，用户可以进行测试验证项目功能是否正常。

> Python 依赖安装已在[环境准备](./docs/zh/quick_install.md)中处理，无需额外操作。

```bash
# 执行所有组件测试
bash build.sh -u

# 指定单独组件测试（可选：asys / msaicerr / msprof / install / upgrade / uninstall / all）
bash build.sh -u --component msprof
```

`--component` 与测试范围、环境准备章节的对应关系如下：

| component | 测试范围 | 环境准备索引 | 示例 |
| --- | --- | --- | --- |
| `asys` | asys Python UT + ST | [环境准备](./docs/zh/quick_install.md#环境准备)、[环境变量配置](./docs/zh/quick_install.md#环境变量配置) | `bash build.sh -u --component asys` |
| `msaicerr` | msaicerr Python UT + ST | [环境准备](./docs/zh/quick_install.md#环境准备)、[环境变量配置](./docs/zh/quick_install.md#环境变量配置) | `bash build.sh -u --component msaicerr` |
| `msprof` | msprof C++ gtest UT | [源码编译](#执行编译)、[离线编译环境准备](./docs/zh/quick_install.md#离线编译环境准备) | `bash build.sh -u --component msprof --ut` |
| `install` | 安装包安装 ST | [源码编译](#执行编译)、[安装](#安装) | `bash build.sh -u --component install --st` |
| `upgrade` | 安装包升级 ST | [源码编译](#执行编译)、[安装](#安装) | `bash build.sh -u --component upgrade --st` |
| `uninstall` | 安装包卸载 ST | [源码编译](#执行编译)、[安装](#安装) | `bash build.sh -u --component uninstall --st` |
| `all` | 全部可用 UT + ST | [环境准备](./docs/zh/quick_install.md#环境准备)、[源码编译](#执行编译) | `bash build.sh -u` |

> `install`、`upgrade`、`uninstall` 仅包含 ST，用例依赖 `build_out/cann-oam-tools_<cann_version>_linux-<arch>.run`。推荐通过上表中的 `build.sh -u --component ... --st` 运行，脚本会先完成构建打包；若直接执行 `scripts/run_tests.sh`，需先确保 `build_out/` 下已有可用 `.run` 包。

UT 测试用例编译输出目录为 `build`，如果想清除历史编译记录：

```bash
rm -rf build_out/ build/
```

## 🅿️ Pre-commit

pre-commit 是一个用于管理和维护 Git 预提交钩子（hooks）的框架，通过在代码提交前自动化执行代码检查、格式化和安全扫描，确保代码质量并统一团队规范，显著减少 CI/CD 流水线失败并提升协作效率。
本仓已配置 pre-commit，用户可以参考 CANN 社区的[pre-commit 配置指导书中第 3 章节](https://gitcode.com/cann/infrastructure/blob/main/docs/SC/pre-commit/pre-commit%E9%85%8D%E7%BD%AE%E6%8C%87%E5%AF%BC%E4%B9%A6.md#3-%E7%A4%BE%E5%8C%BA%E8%B4%A1%E7%8C%AE%E8%80%85%E4%BD%BF%E7%94%A8pre-commit%E8%83%BD%E5%8A%9B)安装 pre-commit。OAT 检查工具已改用 Python 版本 oat-py（通过 `pip install oat-py>=1.0.0` 安装），无需配置 Java/Maven 环境；首次运行时 pre-commit 会为各 hook 创建隔离的虚拟环境，耗时稍长。

## ℹ️ 相关信息

- [快速安装指南](./docs/zh/quick_install.md)：CANN 软件包与编译依赖的安装
- [安装包格式说明](./docs/zh/package_install.md)：rpm/deb 包的安装与卸载
- [环境变量参考](https://hiascend.com/document/redirect/CannCommunityEnvRef)
- [贡献指南](CONTRIBUTING.md)：社区贡献流程与规范
- [安全声明](SECURITY.md)
- [许可证](LICENSE)
