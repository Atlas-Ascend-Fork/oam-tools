# 环境部署

本文是Oam-tools工具的基础环境搭建，主要目的是在运行环境中，完成NPU驱动、固件和CANN软件（`Ascend-cann-toolkit`和`Ascend-cann-ops`）安装以及完成Oam-Tools源码下载， 请您先参考下面步骤完成基础环境搭建和源码下载。

## 环境准备

本项目提供多种搭建昇腾环境的方式，请按需选择。

> **说明**：本文提到的编译态和运行态含义如下，请根据实际情况选择。
>
> - 编译态：针对仅编译本项目不运行的场景，只需安装CANN toolkit包。
> - 运行态：针对运行本项目的场景（编译运行或纯运行），需安装驱动与固件、CANN toolkit包、CANN ops包。

|  安装方式  |  使用说明  |  使用场景  |
| ----- | ------ | ------ |
|  WebIDE  | CANNLab是为CANN社区开发者提供的开箱即用的云端开发环境，内置CANN 软件、NPU算力和WebIDE等全套开发工具提供浏览器和本地IDE客户端双接入方式，支撑社区开发者算子开发、模型训&调优和 AI 应用开发三大领域的开发活动。 | 适用于没有昇腾设备的开发者。|
|  Docker  | Docker镜像是一种高效部署方式，已预集成CANN包和必备依赖。<br>当前仅适用于Atlas A2系列产品，OS仅支持Ubuntu操作系统。**默认安装最新商发版CANN包**。 | 需要快速搭建环境的开发者，有无昇腾设备均可|
|  手动安装  | 按照本文中[方式3：手动安装](#section_manual_install)进行环境准备 |适用有昇腾设备，想体验手动安装CANN包或体验最新master分支能力的开发者。|

### 方式1：WebIDE环境

对于无昇腾设备的开发者，可直接使用CANNLab云开发环境，即“**CANN一站式开发平台**”，该平台为您提供在线可直接运行的昇腾环境，环境中已安装必备的驱动固件、软件包和依赖，无需手动安装。

> **说明**：环境默认安装最新商发版CANN包，源码下载时注意与软件配套。更多关于开发平台的介绍请参考[CANNLab指导](https://gitcode.com/org/cann/cannlab/docs)。

1. 进入开源项目，单击“`CANNLab`”按钮，若未注册或认证，请根据页面提示进行注册和认证。

2. 根据页面提示创建环境并配置规格，启动云开发环境后，单击“连接”进入一站式开发平台。

环境部署完成后，请继续以下步骤：

1. **安装 Python 依赖**

   WebIDE 环境已预装核心依赖，如运行 UT 时缺少其他库，可执行以下命令补充：

   ```bash
   pip3 install -r requirements.txt
   ```

2. **验证环境**

   请参考[环境验证](#环境验证)章节，确认环境和驱动正常。

### 方式2：Docker部署

若您想快速搭建昇腾环境，可使用Docker镜像部署。

> **说明**：镜像文件比较大，下载需要一定时间，请您耐心等待。关于docker命令的选项介绍可通过`docker --help`查询。

1.**下载镜像**

- 步骤1：以root用户登录宿主机。确保宿主机已安装Docker引擎（版本1.11.2及以上）。
- 步骤2：从[昇腾镜像仓库](https://www.hiascend.com/developer/ascendhub/detail/17da20d1c2b6493cb38765adeba85884)拉取已预集成CANN软件包及开发所需依赖的镜像。命令如下，根据实际架构选择：

    ```bash
    # 示例：拉取ARM架构的CANN开发镜像
    docker pull --platform=arm64 swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10
    # 示例：拉取X86架构的CANN开发镜像
    docker pull --platform=amd64 swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10
    ```

2.**运行Docker**
拉取镜像后，需要以特定参数启动容器。根据是否需要在容器内运行样例（访问NPU设备），选择以下对应场景：

**场景1：需要运行样例（需要访问NPU设备）**

如果需要运行样例或测试，容器需要访问宿主机的NPU设备。以Atlas A2系列产品为例：

```bash
docker run \
    --name  oam-tools \
    --device /dev/davinci0 \
    --device /dev/davinci_manager \
    --device /dev/devmm_svm \
    --device /dev/hisi_hdc \
    -v /usr/local/dcmi:/usr/local/dcmi \
    -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
    -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/ \
    -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info \
    -v /etc/ascend_install.info:/etc/ascend_install.info \
    -it swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10 bash
```

| 参数 | 说明 | 注意事项 |
| :--- | :--- | :--- |
| `--name oam-tools` | 为容器指定名称，便于管理。 | 可自定义。 |
| `--device=/dev/davinci0` | 挂载第 0 张 NPU 设备节点。 | 若有多张卡，需逐个添加（如 `--device=/dev/davinci1`）。 |
| `--device=/dev/davinci_manager` | 挂载设备管理接口。 | 必须挂载。 |
| `--device=/dev/devmm_svm` | 挂载设备内存管理模块。 | 必须挂载。 |
| `--device=/dev/hisi_hdc` | 挂载 HDC 通信通道。 | 必须挂载。 |
| `-v /usr/local/dcmi:/usr/local/dcmi` | 挂载DCMI（Device Communication Management Interface）目录。 | 必选（运行样例时）。 |
| `-v /usr/local/bin/npu-smi:...` | 挂载NPU监控工具，用于查看NPU状态。 | 必选（运行样例时）。 |
| `-v /usr/local/Ascend/driver/...` | 挂载NPU驱动库和版本信息。 | 必选（运行样例时）。 |
| `-v /etc/ascend_install.info:...` | 挂载昇腾软件安装信息。 | 必选（运行样例时）。 |
| `-it` | `-i`（交互式）和 `-t`（分配伪终端）的组合参数。 | - |
| `swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10` | 指定要运行的Docker镜像。 |请确保此镜像名和标签（tag）与你通过`docker pull`拉取的镜像完全一致。 |
| `bash` | 容器启动后立即执行的命令。 | - |

**场景2：仅编译构建（不需要运行样例）**

如果只需要进行代码编译构建，无需访问NPU设备，使用以下简化命令：

```bash
docker run --name oam-tools -it swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10 bash
```

| 参数 | 说明 | 注意事项 |
| :--- | :--- | :--- |
| `--name oam-tools` | 为容器指定名称，便于管理。 | 可自定义。 |
| `-it` | `-i`（交互式）和 `-t`（分配伪终端）的组合参数。 | - |
| `swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10` | 指定要运行的Docker镜像。 |请确保此镜像名和标签（tag）与你通过`docker pull`拉取的镜像完全一致。 |
| `bash` | 容器启动后立即执行的命令。 | - |

3.**初始化环境**
进入容器后，执行以下命令初始化环境：

```bash
curl -fsSL -o init_env.sh https://raw.gitcode.com/cann/oam-tools/raw/master/init_env.sh \
  && bash init_env.sh
```

> 建议先审阅 `init_env.sh` 内容再执行；请勿通过 `curl ... | bash` 直接执行未经审查的远程脚本。脚本下载的 CANN 安装包会经官方 sha256 校验后才执行。

`init_env.sh` 会自动安装仓库根目录 `requirements.txt` 中声明的 Python 依赖。环境部署完成后，请继续以下步骤：

1. **验证环境**

   请参考[环境验证](#环境验证)章节，确认环境和驱动正常。

<a id="section_manual_install"></a>

### 方式3：手动安装

对于有昇腾设备的开发者，若您想手动搭建昇腾环境，请参考下述步骤。

#### 前置依赖

    本项目源码编译用到的依赖如下，请注意版本要求。

    - python >= 3.10.0
    - gcc >= 7.3.0
    - cmake >= 3.18.0
    - ccache
    - CANN toolkit组合包：`Ascend-cann-toolkit_${cann_version}_linux-${arch}.run`
    - CANN ops组合包：`Ascend-cann-${chip_type}-ops_${cann_version}_linux-${arch}.run`
    - protobuf >= 25.1（C++ 编译依赖，由 cmake 拉取/链接，用于生成 .pb.cc）
    - abseil >= 20230802.1
    - json >= 3.11.3
    - patch >= 2.7.6
    - dpkg >= 1.19.0.5（仅构建 deb 包时依赖）
    - rpmbuild >= 4.14.0（仅构建 rpm 包时依赖，由 rpm-build/rpm 软件包提供）
    - coverage (仅执行UT时依赖，建议版本 7.13.2)
    - googletest（仅执行UT时依赖，建议版本 1.14.0）
    - mockcpp（仅执行UT时依赖，建议版本 2.7）
    - pytest（仅执行UT时依赖，建议版本 9.0.2）
    - pytest-mock (仅执行UT时依赖，建议版本 3.15.1)

    Python 运行时依赖（asys / msaicerr 等工具运行所需，由 `pip install -r requirements.txt` 安装）的版本要求见仓库根目录的 `requirements.txt`。其中 `protobuf>=6.33.4` 指 Python 包 `protobuf`（PyPI 上独立发版，与上文 C++ 编译用的 protobuf 25.1 是不同的版本号体系），二者不冲突。

 其中：

    - \$\{chip\_type\}：表示昇腾AI处理器型号（与下文`${soc_name}`等价），用于拼接CANN ops包名。可通过`npu-smi info`命令查看`Name`列得到本机芯片型号，再按下表选择对应的ops包。
    - \$\{cann\_version\}：表示CANN包版本号，需要与Toolkit包版本号相同。
    - \$\{arch\}：表示CPU架构，如aarch64、x86_64。

当前支持的芯片型号与CANN ops包对应关系如下：

| `npu-smi info` Name 列 | 适用产品 | `${chip_type}` / `${soc_name}` | CANN ops 包名 |
| --- | --- | --- | --- |
| `910B` | Atlas A2 训练系列产品 / Atlas 800I A2 推理产品 | `910b` | `Ascend-cann-910b-ops_${cann_version}_linux-${arch}.run` |
| `910_93` | Atlas A3 训练系列产品 / Atlas A3 推理系列产品（业内"910C"对应此项） | `910_93` | `Ascend-cann-A3-ops_${cann_version}_linux-${arch}.run` |
| `950` | Atlas 950 系列产品 | `950` | `Ascend-cann-950-ops_${cann_version}_linux-${arch}.run` |

> **说明**
>
> - 上表 Name 列为本工具识别的型号关键字；`npu-smi info`实际可能显示带子型号的字符串（如`910B`类会显示为`910B1` / `910B2` / `910B3` / `910B4`），按"Name 列包含上述关键字"的规则匹配即可。
> - "910C"是商用别称，对应包名中的`A3`（CANN 8.5.0 起统一使用 `Ascend-cann-A3-ops_*`），请勿手动拼写为`910c`、`910_c`、`910_93`等形式。
> - ops 包的实际文件名与可用版本以 [CANN 官方下载页](https://www.hiascend.com/cann/download) 为准，本工具仅识别上表三类芯片，其它芯片暂不支持，欢迎提交 issue 反馈。

#### 软件安装

1. **安装驱动与固件（运行态依赖）**

    驱动与固件的下载和安装操作请参考《[CANN软件安装指南](https://www.hiascend.com/document/redirect/CannCommunityInstWizard)》中“准备软件包”和“安装NPU驱动和固件”章节。驱动与固件是运行态依赖，若仅编译算子，可以不安装。

2. **安装CANN包**

    - **场景1：体验master版本能力或基于master版本进行开发**

        请单击[下载链接](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run-mirror/software/master/)，选择最新时间版本，并根据产品型号和环境架构下载对应包。安装命令如下，更多指导参考《[CANN软件安装指南](https://www.hiascend.com/document/redirect/CannCommunityInstWizard)》。

        1. 安装CANN toolkit包

            ```bash
            # 确保安装包具有可执行权限
            chmod +x Ascend-cann-toolkit_${cann_version}_linux-${arch}.run
            # 安装命令
           ./Ascend-cann-toolkit_${cann_version}_linux-${arch}.run --install --install-path=${install_path}
           ```

        2. 安装CANN ops包（运行态依赖）

            ops包是运行态依赖，若仅编译算子，可不安装此包。

            ```bash
            # 确保安装包具有可执行权限
            chmod +x Ascend-cann-${soc_name}-ops_${cann_version}_linux-${arch}.run
            # 安装命令
            ./Ascend-cann-${soc_name}-ops_${cann_version}_linux-${arch}.run --install --install-path=${install_path}
            ```

        - \$\{cann\_version\}：表示CANN包版本号。
        - \$\{arch\}：表示CPU架构，如aarch64、x86_64。
        - \$\{soc\_name\}：表示NPU型号名称，与上文`${chip_type}`等价，可选值参见[前置依赖](#前置依赖)章节中的"芯片型号与CANN ops包对应关系"表。
        - \$\{install\_path\}：表示指定安装路径，ops包需与toolkit包安装在相同路径，root用户默认安装在`/usr/local/Ascend`目录。

    - **场景2：体验已发布版本能力或基于已发布版本进行开发**

        请访问[CANN官网下载中心](https://www.hiascend.com/cann/download)，选择发布版本（仅支持CANN 8.5.0及后续版本），并根据产品型号和环境架构下载对应包，最后参考网页提供的命令完成安装。

环境部署完成后，请继续以下步骤：

1. **安装 Python 依赖**

   手动安装环境需要自行配置 Python 依赖，请执行以下命令安装 UT 所需的核心包：

   ```bash
   pip3 install -r requirements.txt
   ```

2. **验证环境**

   请参考[环境验证](#环境验证)章节，确认环境和驱动正常。

## 源码下载

源码下载命令如下，请将`${branch}`替换为目标分支标签名，源码分支标签与CANN版本配套关系参见[release仓库](https://gitcode.com/cann/release-management)。

```bash
# 下载项目对应分支源码
git clone -b ${branch} https://gitcode.com/cann/oam-tools.git
```

对于WebIDE或Docker环境，已默认提供最新商发版本的项目源码，如需获取其他版本的源码，也需通过上述命令下载源码。

> **注意**
>
> - gitcode平台在使用HTTPS协议的时候要配置并使用个人访问令牌代替登录密码进行克隆，推送等操作。
> - 若您的编译环境无法访问网络，无法通过git指令下载代码，请先在联网环境中下载源码，再手动上传至目标环境。

## 离线编译环境准备

若您的编译环境无法访问网络，需要在联网环境中手动下载第三方库、闭源二进制包、子仓，并手动上传至您的编译环境中。

### 下载依赖包

在联网环境中运行下载脚本，该脚本会在执行命令的路径下，直接下载并保存上述第三方库、闭源二进制包和子仓（下载子仓需要在有git的环境且[配置gitcode的个人访问令牌](https://gitcode.com/setting/token-classic), 确保能够正确执行git clone）

```bash
# 在当前执行路径下保存文件，可以在不同的路径下执行命令(需要修改脚本的相对路径，或者使用绝对路径)来改变保存的位置
python cmake/download_libs.py
```

闭源二进制包按分支拉取，脚本默认根据当前 git 提交自动探测所属发布分支（探测不出时回退 `master`），与联编时 `build.sh` / `install_bundle.cmake` 的分支解析规则一致。如需预置指定分支的包，用 `--bundle_branch` 显式指定（当前可选 `master`、`9.1.0`，其它值会报错）：

```bash
# 显式预置 9.1.0 分支的闭源包；须与后续联编时 build.sh --bundle_branch=9.1.0 保持一致
python cmake/download_libs.py --bundle_branch=9.1.0
```

> 注意：离线预置的 bundle 分支须与目标环境联编时解析出的分支一致，否则联编阶段会因本地缺对应分支的包而失败。个人分支探测可能不准，建议下载与联编都显式指定 `--bundle_branch`。

### 上传依赖包

在编译环境中新建一个`third_party_path`目录来存放第三方开源软件和闭源软件

```bash
mkdir -p ${third_party_path}
```

创建好目录后，将下载好的第三方库、闭源二进制包和子仓，上传至目录`third_party_path`。

### 依赖包清单

第三方库、闭源二进制包和子仓包括：

| 开源软件 | 版本 | 下载地址 |
|---|---|---|
|protobuf|v25.1|[protobuf-25.1.tar.gz](https://gitcode.com/cann-src-third-party/protobuf/releases/download/v25.1/protobuf-25.1.tar.gz)|
|makeself|2.5.0|[makeself-release-2.5.0.tar.gz](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/makeself/makeself-release-2.5.0.tar.gz)|
|makeself-patch|2.5.0|[makeself-2.5.0.patch](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/makeself/fix/makeself-2.5.0.patch)|
|abseil-cpp|20230802.1|[abseil-cpp-20230802.1.tar.gz](https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download/20230802.1/abseil-cpp-20230802.1.tar.gz)|
|abseil-cpp-patch|20230802.1-h0|[backport-CVE-2025-0838.patch](https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download/20230802.1-h0/backport-CVE-2025-0838.patch)|
|boost|v1.87.0|[boost_1_87_0.tar.gz](https://gitcode.com/cann-src-third-party/boost/releases/download/v1.87.0/boost_1_87_0.tar.gz)|
|gtest|1.14.0|[googletest-1.14.0.tar.gz](https://gitcode.com/cann-src-third-party/googletest/releases/download/v1.14.0/googletest-1.14.0.tar.gz)|
|mockcpp-patch|2.7-h5|[mockcpp-2.7-h5.patch](https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h5/mockcpp-2.7-h5.patch)|
|mockcpp|2.7-h2|[mockcpp-2.7.tar.gz](https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h2/mockcpp-2.7.tar.gz)|

> 注意：上表地址与联编时 cann-cmake 实际拉取的三方件一致（gitcode 上的 protobuf / abseil-cpp / boost / googletest / mockcpp 源码包与 cann-cmake 校验的 OBS 包内容一致）。手工下载时，makeself-2.5.0.patch、backport-CVE-2025-0838.patch 与 mockcpp-2.7-h5.patch 三个补丁文件需存放于依赖目录的 patch/ 子目录下，其余文件直接存放于依赖目录根目录；使用 cmake/download_libs.py 脚本下载时会自动按此布局保存。

闭源二进制包按分支拉取，下表以默认的 `master` 分支为例；预置其它分支时把地址中的 `master` 替换为对应分支名（如 `9.1.0`），或直接用 `python cmake/download_libs.py --bundle_branch=<分支>` 自动下载对应分支的包。

| 闭源二进制 | 分支 | 下载地址 |
|---|---|---|
|cann-oam-tools-release-x86_64.tar.gz|master|[Download](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cann/oam-tools-diag/master/cann-oam-tools-release-x86_64.tar.gz)|
|cann-oam-tools-release-aarch64.tar.gz|master|[Download](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cann/oam-tools-diag/master/cann-oam-tools-release-aarch64.tar.gz)|

| 子仓 | 版本 | 下载地址 |
|---|---|---|
|msprobe|master|<https://gitcode.com/Ascend/msprobe>|
|msprof|master|<https://gitcode.com/Ascend/msprof>|
|cann-cmake|master-059|[cmake-master-059.tar.gz](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cmake/cmake-master-059.tar.gz)|

## 环境验证

安装完CANN包后，需验证环境和驱动是否正常。

- **检查NPU设备**

    ```bash
    # 运行npu-smi，若能正常显示设备信息，则驱动正常
    npu-smi info
    ```

    请记录输出中的`Name`列，并对照[前置依赖](#前置依赖)章节中的"芯片型号与CANN ops包对应关系"表，确认本机芯片型号与已安装的CANN ops包匹配；若`Name`列不在表内，说明本工具尚未适配，请在 issue 中反馈。
- **检查CANN安装**

    ```bash
    # 查看CANN toolkit包版本信息（默认路径安装），WebIDE场景下将/usr/local替换为/home/developer
    cat /usr/local/Ascend/cann/${arch}-linux/ascend_toolkit_install.info
    # 查看CANN ops包版本信息（默认路径安装），WebIDE场景下将/usr/local替换为/home/developer
    cat /usr/local/Ascend/cann/${arch}-linux/ascend_ops_install.info
    ```

- **检查 Python 依赖**

    ```bash
    # 检查 pytest 版本
    pytest --version
    # 检查 coverage 版本
    coverage --version
    ```

    > 如果命令执行失败，请执行 `pip3 install -r requirements.txt` 安装依赖。

## 环境变量配置

按需选择合适的命令使环境变量生效。

```bash
# 默认路径安装，以root用户为例（非root用户，将/usr/local替换为${HOME}）
source /usr/local/Ascend/cann/set_env.sh
# 指定路径安装
# source ${install_path}/cann/set_env.sh
```
