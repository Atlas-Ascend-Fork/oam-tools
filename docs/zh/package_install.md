# 安装包格式与安装指南

## 概述

OAM-Tools 支持构建 `.run`（默认）、`.rpm`、`.deb` 三种格式的安装包。`.run` 包不依赖系统包管理器，其编译、安装与验证的完整说明见 [README.md](../../README.md)；本文介绍 `.rpm` 与 `.deb` 包的操作系统匹配、编译、安装、运行验证与卸载方法。三种包格式的关键差异如下表所示，其中安装命令的适用场景说明见[安装](#安装)章节：

| 包格式 | 适用操作系统 | 安装命令 | 安装路径 | 路径可否自定义 |
| --- | --- | --- | --- | --- |
| `.run`（默认） | 不依赖系统包管理器，全部操作系统（需本机已装配套 CANN 环境） | `./cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}` | 随本机已安装的 CANN 套件目录 | 支持，通过 `--install-path=<路径>` 指定 |
| `.rpm` | RHEL/CentOS/openEuler 等 rpm 系操作系统 | CANN 依赖已登记本机 rpm 数据库：<br>`sudo rpm -ivh cann-oam-tools_<cann_version>_linux-<arch>.rpm`<br>CANN 经 `.run` 包安装：<br>`sudo rpm -ivh --nodeps cann-oam-tools_<cann_version>_linux-<arch>.rpm` | `/usr/local/Ascend/cann-<cann_version>` | 固定，不可自定义 |
| `.deb` | Ubuntu/Debian 等 deb 系操作系统 | CANN 依赖已登记本机 dpkg 数据库：<br>`sudo dpkg -i cann-oam-tools_<cann_version>_linux-<arch>.deb`<br>CANN 经 `.run` 包安装：<br>`sudo dpkg -i --force-depends cann-oam-tools_<cann_version>_linux-<arch>.deb` | `/usr/local/Ascend/cann-<cann_version>` | 固定，不可自定义 |

## 操作系统匹配背景

Linux 主流的包管理生态分为两大阵营：Debian 系（Ubuntu、Debian 等）以 dpkg 为底层包管理器（前端有 apt 等多种）；RHEL 系（RHEL、CentOS、openEuler、openSUSE、Kylin 等）以 rpm 为底层包管理器（前端有 yum/dnf/zypper 等多种）。请按本机所属生态选择对应的安装包格式。

> **选择建议**：Ubuntu/Debian 系统请安装 deb 包，不支持以 rpm 包方式安装本工具（在 Ubuntu/Debian 上**构建** rpm 包是可行的）；RHEL/CentOS/openEuler/openSUSE/Kylin 等 rpm 系系统请安装 rpm 包，deb 包同样不用于 rpm 系系统；`.run` 包与包管理器无关，全部操作系统均可安装。

## 前置要求

构建 rpm/deb 包时，构建环境需额外满足以下工具的版本要求（均为构建期依赖）：

- rpmbuild >= 4.14.0（仅构建 rpm 包时依赖；由 rpm-build（RHEL 系）或 rpm（Debian 系）软件包提供，可通过 `rpmbuild --version` 校验，已在 4.18.2 验证）
- dpkg >= 1.19.0.5（仅构建 deb 包时依赖）
- cmake >= 3.18（闭源二进制包解压使用 `file(ARCHIVE_EXTRACT)` 命令，低版本会在闭源包拉取阶段阻塞于 `cmake/install_bundle.cmake`；首次构建或执行 `build.sh --make_clean` 后的任意包格式构建均会触发，并非仅限 rpm/deb 包）

> **说明**：rpm 版本口径依据本工具 rpm 包载荷采用 gzip 压缩格式。其余编译依赖（Python、gcc、CANN toolkit/ops 套件包等）与 `.run` 包构建一致，其中 cmake 须 >= 3.18；上述 rpm/dpkg 打包工具条目与全部编译依赖的完整清单见[环境部署"前置依赖"章节](quick_install.md#前置依赖)。

## 编译

通用的编译前置条件与环境准备（加载 CANN 环境变量、第三方库路径、离线编译等）与 `.run` 包构建一致，详见 [README.md](../../README.md) 的"源码编译"章节，本文不再重复。在此基础上，通过 `--pkg-type` 参数指定目标包格式：

```bash
# 构建 rpm 包
bash build.sh --pkg-type=rpm

# 构建 deb 包
bash build.sh --pkg-type=deb
```

`--pkg-type` 支持 `run`/`rpm`/`deb`/`deb,rpm`/`all` 五种取值，默认为 `run`；`--pkg` 为 `--pkg-type=run` 的别名。其中 `deb,rpm` 一次构建 deb 与 rpm 两种包；`all` 一次构建 run、rpm、deb 三种包。

构建产物位于 `build_out` 目录：

| 包格式 | 产物名 |
| --- | --- |
| rpm 包 | `build_out/cann-oam-tools_<cann_version>_linux-<arch>.rpm` |
| deb 包 | `build_out/cann-oam-tools_<cann_version>_linux-<arch>.deb` |
| run 包（默认） | `build_out/cann-oam-tools_<cann_version>_linux-<arch>.run` |

实测产物名示例：`cann-oam-tools_9.1.0_linux-aarch64.deb`。

> **说明**：`<cann_version>` 为 CANN 版本号，`<arch>` 为操作系统架构。产物名模式经实测构建验证，x86_64 架构产物名按模板推断。

## 安装

rpm/deb 包通过包管理器的依赖字段声明了 16 项 CANN 依赖（完整清单见下方），安装命令因本机 CANN 套件的安装方式而异：CANN 依赖已通过 deb/rpm 包安装并登记在本机包管理器数据库的主机（依赖检查可通过）可直接安装；CANN 经 `.run` 包安装（开源自建自装的常见形态，CANN 组件未注册到系统包管理器数据库）的主机，须使用 `--force-depends`/`--nodeps` 跳过依赖检查后安装。

依赖子包清单（deb 的 `Depends` 字段与 rpm 的 `Requires` 字段一致，最低版本均为 9.0）：`npu-runtime`、`bisheng-compiler`、`ops-cv`、`ops-math`、`ops-legacy`、`metadef`、`hcomm`、`hccl`、`ge-executor`、`ge-compiler`、`tbe-tik`、`asc-devkit`、`graph-autofusion`、`opbase`、`ops-nn`、`ops-transformer`。

### 安装 deb 包

```bash
# 场景一：CANN 依赖已通过 deb 包安装并登记在本机 dpkg 数据库
sudo dpkg -i cann-oam-tools_<cann_version>_linux-<arch>.deb

# 场景二：CANN 经 .run 包安装（未注册到 dpkg 数据库）
sudo dpkg -i --force-depends cann-oam-tools_<cann_version>_linux-<arch>.deb
```

场景二的失败形态（实测）：在 CANN 经 `.run` 包安装的主机上直接执行 `sudo dpkg -i`（不带 `--force-depends`），包会解包成功但配置失败（退出码 1），停留在半配置状态（dpkg 状态 iU）：安装后脚本（postinst）不会执行，`bin`/`include`/`lib64`/`conf`/`pkg_inc` 等符号链接不会创建。此时工具文件已解包、仍可通过绝对路径调用，但包状态异常，并会触发[注意事项](#注意事项)中所述的 apt 问题；直接再次执行场景二命令即可恢复为正常已配置状态。

### 安装 rpm 包

```bash
# 场景一：CANN 依赖已通过 rpm 包安装并登记在本机 rpm 数据库
sudo rpm -ivh cann-oam-tools_<cann_version>_linux-<arch>.rpm

# 场景二：CANN 经 .run 包安装（未注册到 rpm 数据库）
sudo rpm -ivh --nodeps cann-oam-tools_<cann_version>_linux-<arch>.rpm
```

场景二的失败形态（实测）：在 rpm 数据库无 CANN 依赖记录的主机上直接执行 `sudo rpm -ivh`（不带 `--nodeps`），会以 "Failed dependencies" 报错失败（实测 17 条：16 项 CANN 依赖与 `/bin/sh`），且不会解包任何文件。

> **注意**：场景一（CANN 依赖已登记本机 rpm 数据库、无需 `--nodeps`）的安装场景待实装验证；场景二已在实测环境验证。
>
> **说明**：`dpkg -i` / `rpm -ivh` 仅校验本机包数据库、不会从软件源自动补齐缺失依赖；若希望由软件源解析并安装依赖，可改用 `apt install ./<deb>`（deb 系）或 `dnf|yum|zypper install ./<rpm>`（按发行版选择），该方式要求软件源中已提供对应 CANN 依赖包。

### 安装路径

rpm/deb 包的安装路径固定为 `/usr/local/Ascend/cann-<cann_version>`，**不可自定义**。安装完成后，asys、msaicerr、msprof、hccl_test 四大组件位于该目录的 `tools/` 子目录下。与 `.run` 包的路径差异如下：

| 包格式 | 安装路径 | 路径可否自定义 |
| --- | --- | --- |
| `.rpm` / `.deb` | 固定为 `/usr/local/Ascend/cann-<cann_version>` | 不可自定义 |
| `.run` | 随本机已安装的 CANN 套件目录 | 支持，通过 `--install-path=<路径>` 指定 |

该固定前缀由打包配置（CPACK_PACKAGING_INSTALL_PREFIX）在构建期生成（形如 `/usr/local/Ascend/cann-9.1.0`），与 `.run` 包默认安装路径 `/usr/local/Ascend/cann` 不同，属 rpm/deb 包格式的预期行为。

## 运行与验证

rpm/deb 包内不包含 `set_env.sh` 环境脚本，安装后也不会自动配置环境变量，可通过以下两种方式运行工具：

- **绝对路径调用（适用于安装验证）**：直接使用工具完整路径调用即可完成帮助信息、模块导入等安装验证，无需配置环境变量。
- **执行完整功能前加载 CANN 环境**：采集、解析、profiling 等完整功能依赖本机 CANN 的库路径与环境变量，执行前请先加载本机已安装 CANN 的环境变量（如 `source <CANN安装路径>/set_env.sh`，与 `.run` 包使用方式一致）。

安装完成后，执行以下命令验证（asys 与 msprof 能正常打印帮助信息、msaicerr 模块可正常导入即表示安装成功，三条命令均实测通过）：

```bash
# 验证 asys（故障信息收集）
python3 /usr/local/Ascend/cann-<cann_version>/tools/ascend_system_advisor/asys/asys.py --help

# 验证 msprof（性能调优）
/usr/local/Ascend/cann-<cann_version>/tools/profiler/bin/msprof --help

# 验证 msaicerr（AI Core Error 分析）Python 模块可导入
python3 -c "import sys; sys.path.insert(0, '/usr/local/Ascend/cann-<cann_version>/tools/msaicerr'); import ms_interface"
```

hccl_test 为源码编译型工具，安装后位于 `<安装路径>/tools/hccl_test/`（含 Makefile 与源码），使用方式见其目录内 README。

## 卸载与重装

rpm 包与 deb 包的包名相同，均为 `oam-tools`，卸载时以该包名为操作对象：

```bash
# 卸载 deb 包
sudo dpkg -r oam-tools

# 卸载 rpm 包
sudo rpm -e oam-tools
```

卸载行为（实测）：

- 卸载清理本包自身文件与安装时创建的 `bin`/`include`/`lib64`/`conf`/`pkg_inc` 符号链接；共享路径仅在无其它 CANN 包占用时删除空目录（卸载脚本通过 `var/ascend_package_db.info` 的组件注册信息判断，`rmdir` 仅删除空目录）。
- 安装根目录 `/usr/local/Ascend/cann-<cann_version>` 仅在本工具单独安装（前缀未被其它 CANN 包共用）时才会一并移除（该场景实测零残留）；场景一共用前缀时根目录会保留，且不会影响同前缀下其它 CANN 包的内容。
- `rpm -e` 卸载时会打印 2 条无害的警告（如 `file lib64/include: remove failed`），这是卸载脚本先行删除符号链接所致，不影响清理结果。
- rpm 安装时额外创建的 `/usr/lib/.build-id/` 符号链接，卸载时也会一并清理。

重新安装 deb 包时无需先卸载，直接再次执行与安装场景对应的命令即可（场景二实测通过，安装后脚本可幂等重复执行）：

```bash
# 场景一：CANN 依赖已通过 deb 包安装并登记在本机 dpkg 数据库
sudo dpkg -i cann-oam-tools_<cann_version>_linux-<arch>.deb

# 场景二：CANN 经 .run 包安装（未注册到 dpkg 数据库）
sudo dpkg -i --force-depends cann-oam-tools_<cann_version>_linux-<arch>.deb
```

重装同版本 rpm 包须加 `--replacepkgs`：对已安装的同版本包，直接重复 `rpm -ivh` 或 `rpm -Uvh` 均会报 `package oam-tools-... is already installed` 而拒绝安装（实测）；加 `--replacepkgs` 可覆盖重装（场景二实测通过，安装后脚本可幂等重复执行）；升级到新版本的 rpm 包则使用 `rpm -Uvh <新版本包>`：

```bash
# 场景一：CANN 依赖已通过 rpm 包安装并登记在本机 rpm 数据库
sudo rpm -ivh --replacepkgs cann-oam-tools_<cann_version>_linux-<arch>.rpm

# 场景二：CANN 经 .run 包安装（未注册到 rpm 数据库）
sudo rpm -ivh --nodeps --replacepkgs cann-oam-tools_<cann_version>_linux-<arch>.rpm
```

## 注意事项

- **CANN 版本兼容性需自行保障**：`.run` 包安装时会基于包内 `version.info` 校验与本机 CANN 的版本兼容性；rpm/deb 包不做该版本兼容性校验，而是以包管理器依赖字段声明 16 项 CANN 依赖（完整清单见[安装](#安装)章节）。使用 rpm/deb 包时，请自行确保本机已安装版本配套的 CANN toolkit 与 ops 套件（依赖字段声明的最低版本为 9.0）。该 9.0 下限来自 `version.cmake` 中 `set_cann_run_dependencies` 的依赖声明（构建/运行依赖均声明 >= 9.0），与 `.run` 包安装期基于 `version.info` 的兼容性校验相互独立。
- **执行 apt 升级操作前请先卸载本包**：在 CANN 未以 deb 包方式安装的主机上，本包安装后（无论处于半配置还是已配置状态），`apt --fix-broken install` 会移除 oam-tools，`apt upgrade` 会因依赖不满足而报错，`apt-mark hold` 无法缓解。执行 apt 升级类操作前，请先执行 `sudo dpkg -r oam-tools` 卸载本包。
- **同一环境仅使用一种包格式**：建议同一环境只用一种包格式（`.run`/`.rpm`/`.deb` 之一）安装本工具，避免混装。
- **openEuler 实机安装待实装验证**：本文所述 rpm 包 `--nodeps` 安装、卸载行为已在实测环境验证；openEuler 等 rpm 系操作系统上、CANN 依赖已登记本机 rpm 数据库（无需 `--nodeps`）的安装场景尚未实机验证。
