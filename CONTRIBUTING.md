# 贡献指南

本项目欢迎广大开发者体验并参与贡献。在参与社区贡献之前，请参见 [cann-community](https://gitcode.com/cann/community) 了解[行为准则](https://gitcode.com/cann/community/blob/master/contributor/code-of-conduct.md)、完成 [CLA 协议签署](https://gitcode.com/cann/infrastructure/blob/master/docs/cla/cla使用指南.md)，并了解源码仓的贡献流程。除代码贡献外，社区同样欢迎会议、邮件、测试等多种形式的贡献，详见社区[参与贡献](https://gitcode.com/cann/community#参与贡献)总览。

若您希望参与社区非本仓的进阶贡献（如新建 SIG、成为核心贡献者、新建仓库、引入开源三方件等），请参阅 [CANN 社区贡献指南](https://gitcode.com/cann/community#进阶贡献)。

## 贡献场景

开发者贡献场景主要包括：

- [贡献新特性](#一贡献新特性)
- [Bug 修复](#二bug-修复)
- [文档纠错](#三文档纠错)
- [体验反馈](#四体验反馈)
- [帮助解决他人 Issue](#五帮助解决他人-issue)

---

## 一、贡献新特性

感谢您参与 OAM-Tools 建设，为昇腾运维工具注入更多价值！完整的贡献流程如下：

> **创建 Issue** → **方案评审** → **开发环境准备** → **PR 提交** → **CI 门禁** → **Committer 检视与 Maintainer 合入**

### 1. 创建 Issue（方案讨论）

若您的贡献不是简单的 Bug 修复，而是涉及新增特性、新增接口、新增配置参数或修改代码流程等，请务必先通过 Issue 进行方案讨论，以避免您的代码被拒绝合入。若您不确定本次修改是否可归为"简单的 Bug 修复"，亦可通过提交 Issue 进行讨论。

请新建 `Requirement|需求建议` 类 Issue 提出您的想法，Issue 中请至少包含以下内容：

- **特性的背景和动机**：比如该特性解决了什么场景的需求。
- **核心设计方案**：简要说明该特性实现的技术思路、关键模块的设计方案。
- **预期达成的功能性能目标**：例如该特性需实现的核心功能、预期的性能表现或定位精度提升。
- **预计完成时间**：方便社区了解开发进度，也便于后续协同支持。

具体操作步骤请参阅：[Issue 操作指南](https://gitcode.com/cann/community/blob/master/contributor/issue-operation.md)。

### 2. 方案评审

创建需求类 Issue 后，需申报 SIG 议题，并参加 [Tools SIG](https://gitcode.com/cann/community/blob/master/CANN/sigs/tools/README.md) 评审。会议安排、议题申请方式及 Maintainer 联系方式请查阅 [Tools SIG 说明](https://gitcode.com/cann/community/blob/master/CANN/sigs/tools/README.md)。

**紧急需求处理**：若需求紧急，可根据 Tools SIG 说明联系 Maintainer，申请临时 SIG 评审。

**需求接纳**：若需求被接纳，[SIG 成员](https://gitcode.com/cann/community/blob/master/CANN/sigs/tools/sig-info.yaml)将为您分配合适的合入路径（如 `experiment/` 实验目录），请将特性代码提交至对应目录。

### 3. 开发环境准备

OAM-Tools 依赖昇腾 CANN 软件栈，请先完成环境搭建与源码构建，确保本地可复现验证：

**基础依赖**（完整环境部署请参见[快速安装指南](docs/zh/quick_install.md)）：

| 依赖 | 版本要求 |
| ---- | -------- |
| Python | >= 3.10.0 |
| GCC / CMake / patch | >= 7.3.0 / >= 3.18.0 / >= 2.7.6 |
| ccache | 无版本要求（构建加速） |
| CANN（Toolkit & Ops） | >= 8.5.0（需提前安装 NPU 驱动 / 固件） |

其中 C++ 组件（msprof collector、hccl_test）编译还依赖 protobuf >= 25.1、abseil >= 20230802.1、json >= 3.11.3（由 `cmake/` 自动拉取链接）；执行 UT 还需 pytest / pytest-mock / coverage / googletest / mockcpp，版本建议见[快速安装指南](docs/zh/quick_install.md)。

**源码构建与安装验证**：

```bash
# 1. 安装 Python 依赖并启用本地代码检查（见附录 B）
pip3 install -r requirements.txt
pip3 install pre-commit
pre-commit install

# 2. 加载 CANN 环境变量后构建
#    root 用户默认路径为 /usr/local/Ascend/cann，非 root 用户为 ${HOME}/Ascend/cann，
#    指定路径安装时为 ${install_path}/cann
source <CANN安装路径>/set_env.sh
bash build.sh

# 3. 安装构建产物并验证
#    ${cann_version} 与 ${arch} 从 build_out/ 目录的文件名获取，
#    如 cann-oam-tools_9.1.0_linux-aarch64.run（arch 为 x86_64 或 aarch64）
./build_out/cann-oam-tools_${cann_version}_linux-${arch}.run --full
source <CANN安装路径>/set_env.sh
asys -h    # 能正常打印帮助信息即表示安装成功
```

> **注意**：
>
> - 编译过程中会通过 `git clone` 拉取 `msprobe` 子仓（用于同步 msaccucmp 工具），使用 HTTPS 协议克隆前需[配置 gitcode 个人访问令牌](https://gitcode.com/setting/token-classic)以替代登录密码，否则克隆会失败。msprof 分析 wheel 构建期直接从 OBS 下载 profiler run 包，无需 clone `msprof` 源码；仅离线编译预置（`cmake/download_libs.py`）才需要额外拉取 `msprof`。
> - 若编译环境无法访问网络，请参考[离线编译环境准备](docs/zh/quick_install.md#离线编译环境准备)提前完成依赖包下载，并通过 `--cann_3rd_lib_path` 指定依赖包目录。
> - 无昇腾设备的开发者可通过 Docker 或 CANNLab 云端环境编译构建，详见[快速安装指南](docs/zh/quick_install.md)。

**单元测试**（建议提交 PR 前本地自测）：

```bash
bash build.sh -u                     # 构建并运行全部测试
bash build.sh -u --component asys    # 仅运行指定组件（可选：host / asys / msaicerr / msprof / install / upgrade / uninstall / all）
```

### 4. PR 提交

#### 交付件要求

| 场景 | 交付件要求 | 参考资料 |
| ---- | ---------- | -------- |
| asys / msaicerr 工具能力新特性（新增命令、子命令、参数或解析能力） | 特性代码 + UT / ST 用例 + 中英文用户指南更新（`docs/zh/user_guide/`、`docs/en/user_guide/`） | [asys 用户指南](docs/zh/user_guide/asys/README.md)、[msaicerr 用户指南](docs/zh/user_guide/msaicerr/README.md) |
| msprof / hccl_test 组件特性（C++ collector、集合通信测试） | 特性代码 + gtest UT 用例 + 中英文用户指南更新（`docs/zh/user_guide/`、`docs/en/user_guide/`） | [msprof 用户指南](docs/zh/user_guide/profiling/README.md)、[hccl_test 用户指南](docs/zh/user_guide/hccl_test/README.md) |
| 实验特性（`experiment/`） | 特性代码 + README 文档 | [experiment/](experiment/) |
| 运行示例（`examples/`） | 示例脚本 + 示例文档 | [examples/README.md](examples/README.md) |

若您的特性尚未经过较强的泛化性测试，建议将特性代码合入到 `experiment/` 目录下，目录组织可参考已有特性（如 [msprof_experience_demo](experiment/task-book/msprof_experience_demo/)），完整结构参见[附录 A](#附录-a交付件目录结构)。

#### 合规检查

提交前请逐项自查：

- [ ] 代码是否符合 [C++ 编程规范](https://gitcode.com/cann/community/blob/master/contributor/coding-standards/C++%20Coding%20standards.md)或 Python 规范（本仓工具矩阵见[附录 B](#附录-b代码规范与本地检查)）
- [ ] 代码是否编译通过（`bash build.sh`），UT / ST 是否通过（`bash build.sh -u`）
- [ ] Markdown 文档语法是否符合规范
- [ ] 所使用的 LICENSE 是否合规，建议使用 Apache 2.0 等协议，并按照实际情况标注版权信息
- [ ] 合入的代码里不包含二进制文件（README 或文档中需要的配图除外）
- [ ] 若涉及第三方数据集，只需在文档中说明下载方式、使用方法，无需直接提供数据集
- [ ] 若修改涉及公共代码（非该特性内部代码），能通过 CI 验证

#### 提交规范

- **目标分支**：向 `master` 分支提交 PR。
- **PR 标题**：遵循 Conventional Commits 规范（`feat:` / `fix:` / `docs:` / `perf:` / `refactor:` 等），建议关联 Issue 编号，如 `feat(asys): 新增 XX 解析能力(#123)`。
- **PR 描述**：请按照 PR 模板仔细填写本次 PR 的业务背景、目的、方案等信息，并关联前述需求 Issue。

Fork、克隆、同步、冲突处理等具体操作步骤，请参阅 [PR 操作指南](https://gitcode.com/cann/community/blob/master/contributor/pull_request_operation.md)与 [GitCode 工作流说明](https://gitcode.com/cann/community/blob/master/contributor/gitcode-workflow.md)。

### 5. CI 门禁

通过在 PR 评论框输入 `/compile` 指令触发开源仓门禁，并依据 CI 检测结果进行修改。目前 CI 门禁主要包含以下检查项：

- 代码编译（x86 / aarch64）
- 静态检查（如涉及 codecheck 误报，请提交给 SIG 成员屏蔽）
- UT 测试
- 冒烟测试

门禁通过后，请在 PR 评论区 @ Committer 提醒其检视。

### 6. Committer 检视与 Maintainer 合入

Committer 检视后将反馈检视意见，请根据意见修改，完成后 @ Committer。

Committer 检视通过后，将标注 `/lgtm` 标签；Maintainer 最终审核，确认无问题后，将标注 `/approve` 标签合入 PR。

---

## 二、Bug 修复

如果您在本项目中发现了某些 Bug，希望对其进行修复，欢迎您新建 Issue 进行反馈和跟踪处理。

您可以按照[提交 Issue / 处理 Issue 任务](https://gitcode.com/cann/community#提交Issue处理Issue任务)指引新建 `Bug-Report|缺陷反馈` 类 Issue 对 Bug 进行描述。若为简单 Bug 修复，亦可直接提交 PR（仍请按 PR 模板说明背景与验证方式）。

## 三、文档纠错

如果您在本项目中发现某些文档描述错误，欢迎您新建 Issue 进行反馈和修复，文档写作规范可参考[文档贡献指南](https://gitcode.com/cann/community/blob/master/contributor/docs/document_writing_specs.md)。

您可以按照[提交 Issue / 处理 Issue 任务](https://gitcode.com/cann/community#提交Issue处理Issue任务)指引新建 `Documentation|文档反馈` 类 Issue 指出对应文档的问题，然后在评论框中输入"/assign"或"/assign @yourself"，将该 Issue 分配给您纠正对应文档描述。

## 四、体验反馈

如果您在使用 OAM-Tools 的过程中，发现文档、命令行与配置、运行示例、构建工具链或运行时反馈等环节存在体验问题（如不易学习、不易使用、报错信息不清晰等），欢迎您新建 Issue 进行反馈，帮助我们持续优化易用性。

您可以按照[提交 Issue / 处理 Issue 任务](https://gitcode.com/cann/community#提交Issue处理Issue任务)指引新建 `Experience Request|体验需求` 类 Issue，说明体验问题所属的功能链路与工具（asys / msaicerr / msprof / hccl_test）、实际遇到的问题以及期望的改进方式。若您希望直接参与改进，也可以在评论框中输入"/assign"或"/assign @yourself"，将该 Issue 分配给您进行处理。

## 五、帮助解决他人 Issue

如果社区中他人遇到的问题您有合适的解决方法，欢迎您在 Issue 中发表评论交流，帮助他人解决问题和痛点，共同优化易用性。

如果对应 Issue 需要进行代码修改，您可以在 Issue 评论框中输入"/assign"或"/assign @yourself"，将该 Issue 分配给您，跟踪协助解决问题。

---

## 附录 A：交付件目录结构

本仓按"组件源码 + 实验特性 + 运行示例 + 测试 + 文档"组织交付件，新增特性时请参照以下结构落盘：

```text
├── src/                                      # 组件源码
│   ├── asys/                                 # asys：故障信息收集（Python）
│   │   ├── <module>/                         # 功能模块（analyze / collect / diagnose / cmdline 等）
│   │   └── ...
│   ├── msaicerr/                             # msaicerr：AI Core Error 分析（Python）
│   ├── msprof/                               # msprof：性能调优（C++ collector + Python 分析）
│   └── hccl_test/                            # hccl_test：HCCL 集合通信测试（C++）
├── experiment/                               # 实验特性（未经过强泛化性测试的特性）
│   └── task-book/
│       └── <feature_name>/                   # 特性名称（如 msprof_experience_demo）
│           ├── README.md                     # 特性说明文档
│           ├── 01_cmdline/                   # 按接入方式组织的特性代码与说明
│           └── ...
├── examples/                                 # 运行示例
│   ├── <component>/                          # 组件目录（asys / msaicerr / msprof）
│   │   ├── run.sh                            # 一键运行脚本
│   │   └── ...
│   └── README.md                             # 示例总览
├── test/
│   ├── ut/                                   # 单元测试（test/ut/{asys,msaicerr,msprof}/）
│   └── st/                                   # 系统测试（test/st/{asys,msaicerr,install,upgrade,uninstall}/）
└── docs/
    ├── zh/                                   # 中文文档（用户指南：docs/zh/user_guide/<component>/）
    └── en/                                   # 英文文档（docs/en/user_guide/<component>/）
```

## 附录 B：代码规范与本地检查

本仓通过 `pre-commit` 在提交时自动执行代码检查，主要检查项包括：

| 检查项 | 说明 |
| ------ | ---- |
| clang-format | C/C++ 代码格式化（遵循仓库根目录 `.clang-format`） |
| ruff | Python 代码检查与格式化（遵循 PEP 8 规范） |
| bandit | Python 安全检查（medium 及以上严重度） |
| codespell / typos | 拼写检查（昇腾专有词白名单见 `.typos.toml` 与 `.pre-commit-config.yaml`） |
| OAT | 开源合规检查（远程 Python hook，由 pre-commit 自动安装运行，无需手动配置） |
| 文本 / 安全检查 | 行尾空白、文件末尾换行、YAML / JSON 语法、大文件（>1MB）、私有密钥检测等 |

```bash
pip install pre-commit
pre-commit install
```

更多规范请参考社区文档：

- [C++ 编程规范](https://gitcode.com/cann/community/blob/master/contributor/coding-standards/C++%20Coding%20standards.md)
- [安全编码规范](https://gitcode.com/cann/community/blob/master/contributor/coding-standards/SecureCoding.md)
- [试验特性规范](https://gitcode.com/cann/community/blob/master/contributor/experimental-feature-conventions.md)
- [开源代码片段引用指导](https://gitcode.com/cann/community/blob/master/contributor/third_party/snippet-reference-guideline.md)

如果在贡献过程中有任何疑问，随时欢迎在社区中交流；再次感谢您的支持，期待您的精彩贡献！
