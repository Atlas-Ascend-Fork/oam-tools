# AGENTS.md

本文件为 agent 在此代码仓库中工作时提供指导。

## 项目概述

oam-tools（Operations, Administration, and Maintenance）是CANN的运维工具集，为开发者提供故障定位工具和性能测试调优工具。

主要功能：

- **故障信息收集**（asys）：故障信息收集、软硬件信息展示、健康检查、综合检测等
- **AI Core Error 分析**（msaicerr）：AI Core Error 问题分析、Dump 文件解析、环境检查等
- **性能调优**（msprof）：采集和分析运行在昇腾 AI 处理器上的 AI 任务各个运行阶段的关键性能指标
- **HCCL 性能测试**（hccl_test）：分布式训练或推理场景下，测试集合通信的功能与性能

## 构建命令

### 基础构建

```bash
# 构建项目
bash build.sh

# 指定第三方库路径构建
bash build.sh --cann_3rd_lib_path=${third_party_path}

# 查看构建选项
bash build.sh -h
```

### 执行测试

```bash
# 执行所有测试用例
bash build.sh -u

# 执行指定组件测试
bash build.sh -u --component msprof
```

### 安装依赖

```bash
# 安装 Python 依赖
pip3 install -r requirements.txt

# 下载第三方库和子仓（仅在网络不通时使用）
python3 cmake/download_libs.py
```

## 目录结构

| 目录 | 用途 |
|------|------|
| `src/asys/` | asys 故障信息收集模块 |
| `src/msaicerr/` | AI Core Error 分析模块 |
| `src/msprof/` | 性能调优模块 |
| `src/hccl_test/` | HCCL 性能测试模块 |
| `src/third_party/` | 依赖的第三方库头文件 |
| `cmake/` | 构建配置 |
| `scripts/` | 辅助构建相关文件 |
| `test/` | UT/ST 用例 |
| `docs/` | 项目文档 |
| `bundle/` | 打包相关文件 |
| `.clang-format` | 代码格式化配置 |

## 开发规范

### gitcode pr/issue 操作

@.claude/skills/default-skills/SKILL.md

SKILL内容可参考[SKILL.md](.claude/skills/default-skills/SKILL.md)

### 代码风格

- 使用 .clang-format 格式化代码
- 遵循项目既有的代码风格
- Python 代码遵循 PEP 8 规范

### pre-commit

- 项目已配置 pre-commit，请参考 CANN 社区的 pre-commit 配置指导书安装和使用

## 短语

使用中文
