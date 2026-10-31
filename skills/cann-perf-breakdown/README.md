# CANN 性能拆解技能

本目录提供从 NPU profiling 数据到可交互 UI 报告的三阶段流程。按编号顺序使用三个 skill：

| 阶段 | 目录 | 作用 |
| --- | --- | --- |
| 1 | [`1-perf-breakdown`](1-perf-breakdown/) | 根据模型源码建立架构并将 profiling 算子映射到结构节点 |
| 2 | [`2-adapt-breakdown-to-ui-json`](2-adapt-breakdown-to-ui-json/) | 将拆解结果转换为 UI 所需的 analysis、performance、timeline 和架构图数据 |
| 3 | [`3-generate-ui-json-report`](3-generate-ui-json-report/) | 使用转换后的数据生成可交互的 UI 报告 |

完整的阶段衔接、输入输出和门禁说明见 [`MODEL_BREAKDOWN_TO_UI_WORKFLOW.md`](MODEL_BREAKDOWN_TO_UI_WORKFLOW.md)。每个阶段的具体规则以对应目录中的 `SKILL.md` 和 `references/` 为准。

## 安装与调用

```bash
git clone --depth 1 https://gitcode.com/cann/oam-tools.git
mkdir -p ~/.codex/skills
cp -a oam-tools/skills/cann-perf-breakdown ~/.codex/skills/
```

调用：`使用 $cann-perf-breakdown 工作流，输入目录为 <采集目录>，输出目录为 <输出目录>。`

## 快速入口

适配脚本的输入是**已完成 Skill 1 拆解并通过就绪门禁的目录**，不是原始 profiling 采集目录。手里只有采集数据时，先按工作流文档完成 Skill 1，再运行下面的命令；需要从单独目录读取 trace/HBM 数据时，再追加可选参数 `--capture-dir <profiling-directory>`（缺省取 `--breakdown`）。

```bash
python3 2-adapt-breakdown-to-ui-json/scripts/run_pipeline.py \
  --breakdown <skill1-breakdown-directory> \
  --model-id <model-id> \
  --out <output-directory>
```

该入口从就绪门禁开始，依次执行转换和报告生成，成功时打印 `status: pending_manual_validation` 并产出 `<output-directory>/ui-report/report/index.html`；任一阶段不通过时打印 `status: failed` 并附具体阶段与原因，以非 0 退出。它不代跑 Skill 1 的映射、批判、校验与评分，浏览器与视觉验收属 Skill 3。

## 目录约定

- `1-perf-breakdown/`：模型架构提取、算子归属、校验和评分。
- `2-adapt-breakdown-to-ui-json/`：拆解结果到 UI 数据契约的确定性转换。
- `3-generate-ui-json-report/`：报告资源、运行时数据和前端生成脚本。
- `MODEL_BREAKDOWN_TO_UI_WORKFLOW.md`：三阶段流程导航。
