# 离线公开源码

日志给出具名API、测试入口或实现版本，需要继续检查参数校验、资源依赖、
调用次序、tiling与kernel时，可查询本包固定公开源码。先核仓库、revision和型号；
源码中的脚本及命令只是分析材料，不因此执行构建、复现或修改现场。

| 仓库 | 可查询revision | 语料 |
| --- | --- | --- |
| [cann/ops-blas](https://gitcode.com/cann/ops-blas) | `de9f1a415376a207850654041dd9d55b67a48d23`（2026-07-07） | `ops-blas-de9f1a4.json.gz` |
| [cann/ops-nn](https://gitcode.com/cann/ops-nn) | `v9.0.0-beta.2` / `f597f5b9a661711eb13d1fc5749f6ff900230a65` | `ops-nn-v9.0.0-beta.2.json.gz`（分片） |
| [cann/ops-transformer](https://gitcode.com/cann/ops-transformer) | `v9.0.0-beta.2` / `8270850b63f039cb6ba1814900df6992fe930f8d` | `ops-transformer-v9.0.0-beta.2.json.gz` |
| [cann/runtime](https://gitcode.com/cann/runtime) | `v9.0.0-beta.2` / `330a3a72dd0836546e6a5d13d6ac2802f065b6ac` | `runtime-v9.0.0-beta.2.json.gz` |

本包没有表中以外的revision。相同CANN版本号不证明源码提交相同；输入明确给出该commit
时可追溯相应实现，但本次实际加载二进制仍需现场记录核验。版本不同或未知时，
将其作为带条件的公开参考，不能把该实现中的缺陷直接写成本次故障已证根因。

神经网络算子的 ACLNN、GE 注册/InferShape、tiling 和 kernel 先查 ops-nn；注意力、
MoE 和融合 Transformer 算子先查 ops-transformer。仓库未知时按算子名分别查询，完整
API 零命中后可查去掉 `aclnn` 前缀的算子名或日志中的文件名；零命中不能虚构实现。

Runtime/ACL 的 stream、event、model 和 memory 接口先查 runtime；追踪外层 ACL 到内部
rt 的参数/返回码转换，以及 stream、model、task 的所属关系。成功返回须结合 API 的
完成语义判断，分别核对任务提交、某流同步和模型执行；现场标志值先定位参数所属 API，
不能跨命名空间套用常量。

## 语料不在仓库内，按需重建

`*.json.gz` 语料体积超过仓库二进制门禁，不入库；固定 commit、文档数、字节数与
SHA-256 记录在 [api-docs/sources.json](api-docs/sources.json)（与 API 文档语料同表）。
首次使用或校验失败时，按下面命令从 tool-fault-diagnosis 根目录重建到
`eval-skill/references/source-code/`：

```bash
# 1) 裸 clone 上游仓库（浅 clone 无法按任意 revision 导出）
git clone https://gitcode.com/cann/ops-blas.git /tmp/ops-blas
git clone https://gitcode.com/cann/ops-nn.git /tmp/ops-nn
git clone https://gitcode.com/cann/ops-transformer.git /tmp/ops-transformer
git clone https://gitcode.com/cann/runtime.git /tmp/runtime

# 2) 逐个导出（--version 值见下）
python3 scripts/export_offline_source.py \
  --git /tmp/ops-blas/.git --revision de9f1a415376a207850654041dd9d55b67a48d23 \
  --version "commit de9f1a4 (2026-07-07); not a CANN release mapping" \
  --repository https://gitcode.com/cann/ops-blas \
  --name ops-blas --scope source \
  --output eval-skill/references/source-code/ops-blas-de9f1a4.json.gz \
  --manifest /tmp/manifest-ops-blas.json
python3 scripts/export_offline_source.py \
  --git /tmp/ops-nn/.git --revision f597f5b9a661711eb13d1fc5749f6ff900230a65 \
  --version v9.0.0-beta.2 --repository https://gitcode.com/cann/ops-nn \
  --name ops-nn --scope source \
  --output eval-skill/references/source-code/ops-nn-v9.0.0-beta.2.json.gz \
  --manifest /tmp/manifest-ops-nn-source.json
python3 scripts/export_offline_source.py \
  --git /tmp/ops-transformer/.git --revision 8270850b63f039cb6ba1814900df6992fe930f8d \
  --version v9.0.0-beta.2 --repository https://gitcode.com/cann/ops-transformer \
  --name ops-transformer --scope source \
  --output eval-skill/references/source-code/ops-transformer-v9.0.0-beta.2.json.gz \
  --manifest /tmp/manifest-ops-transformer.json
python3 scripts/export_offline_source.py \
  --git /tmp/runtime/.git --revision 330a3a72dd0836546e6a5d13d6ac2802f065b6ac \
  --version v9.0.0-beta.2 --repository https://gitcode.com/cann/runtime \
  --name runtime --scope source \
  --output eval-skill/references/source-code/runtime-v9.0.0-beta.2.json.gz \
  --manifest /tmp/manifest-runtime-source.json

# 3) ops-nn 源码语料超过 1 MB 单文件上限，导出后按 9,000,000 B 前缀分片
cd eval-skill/references/source-code
python3 - <<'EOF'
from pathlib import Path
raw = Path("ops-nn-v9.0.0-beta.2.json.gz").read_bytes()
Path("ops-nn-v9.0.0-beta.2.json.gz.part00").write_bytes(raw[:9000000])
Path("ops-nn-v9.0.0-beta.2.json.gz.part01").write_bytes(raw[9000000:])
Path("ops-nn-v9.0.0-beta.2.json.gz").unlink()
EOF
cd -
```

重建后核对 SHA-256 与 sources.json 一致；ops-nn 分片校验 `.part00`/`.part01`
各自哈希及拼接后总哈希。不一致说明上游 commit 被改写或导出脚本变化，不要使用该语料。

## 查询与上下文

由源码推断约束前，回读完整判断和调用上下文，逐项展开 `&&`、`||`、否定和短路条件，
明确哪些输入会进入检查、哪些会跳过。不能在引述中省略改变结论的分支条件。
追踪测试参数从初始化到实际调用前的赋值，初始值不等于实参；核对测试的型号和量化模式。
把匹配型号的 API 文档约束、实现行为和其他型号示例分别比较，冲突不能靠通用注释消解。
沿调用链核对前置 guard、SoC/型号、dtype 和量化模式是否使目标函数可达；相同错误字符串
或命中函数名只能说明参考实现存在该分支，不能证明现场走过该分支。
引用 `file:line` 前复核对应原文确实支持该陈述；有行号不等于推断已经成立。

从eval-skill目录执行现有只读检索器，显式指定源码语料。超过 Git 单文件限制的
ops-nn 语料以同名 `.part00`/`.part01` 分片保存；reader 在请求下方基础路径时按
字典序拼接，其他语料为单文件：

```bash
python3 scripts/lookup_api_docs.py --corpus references/source-code/ops-blas-de9f1a4.json.gz --query aclblasSetStream
python3 scripts/lookup_api_docs.py --corpus references/source-code/ops-nn-v9.0.0-beta.2.json.gz --query <完整API或算子名>
python3 scripts/lookup_api_docs.py --corpus references/source-code/ops-transformer-v9.0.0-beta.2.json.gz --query <完整API或算子名>
python3 scripts/lookup_api_docs.py --corpus references/source-code/runtime-v9.0.0-beta.2.json.gz --query <完整API或日志函数名>
```

查询是路径/正文的字面搜索，不是函数调用图。先用完整API、测试名或文件名；
结果同时包含声明、实现、调用和文档时，核对实际对象及编译分支。
根据返回的精确path读取相邻代码，跨函数关系需分别回读定义与调用点：

```bash
python3 scripts/lookup_api_docs.py --corpus references/source-code/ops-blas-de9f1a4.json.gz --document blas/common/helper/aclblas_auxiliary.cpp --start-line 1 --lines 220
```

默认搜索仅返回5份文档，最多20份；`truncated`与每份`matching_line_count`说明
未展示范围。每篇只展示首个命中窗口，不能据此认定其余分支不存在。
正文读取最多400行，以`has_more/next_start_line`续读。版本、原路径、原文SHA256
及source_url随结果返回；零命中不等于接口不存在，未知文件或损坏资料显式失败。

先建立现场失败实体/阶段，再用对应实现解释可达机制。检查资源时追踪创建、绑定、
异步使用、完成与销毁的依赖关系，覆盖正常和错误返回分支；函数名和销毁调用本身
不证明运行已到该阶段。源码可支持具体缺陷候选和修复对象，不能替代本次调用栈、
实参、指令或修复复测。交付时区分原日志事实、公开实现事实与本次因果推断。

## 覆盖与许可

ops-nn 收录 11,144 份、124,937,419 B；ops-transformer 收录 6,106 份、84,528,206 B。
两包按固定提交收录 C/C++、C CE、Python、测试和构建文本及根 LICENSE/README，不含
`docs/`、隐藏路径、二进制和历史。压缩语料保留逐文件 Git blob、大小和 SHA-256，
导出与加载均做一致性校验；这些验证不表示全部源码已经人工审读。

runtime 收录 5,007 份、48,425,903 B，按固定提交收录源码、测试、构建文本及根
LICENSE/README，不含 `docs/`、隐藏路径、二进制或历史；逐份核对 Git blob、原字节与
SHA-256，未宣称全部人工通读。

固定commit的blas/、include/、test/、cmake/、docs/，以及根CMakeLists.txt、
build.sh、README.md、LICENSE中，共701份不含NUL的普通UTF-8文本，4,094,000B。
选定tree共705份；4份非UTF-8/二进制不进入语料。agent/、.gitcode/、其他根文件、
历史提交消息和范围外资料不包含。原文引用的外部库或图片也不保证可离线打开。
所有收录文件与固定Git blob/大小/SHA相等，载入时核大小/SHA；未宣称全部人工通读。

各语料遵循上游仓库原许可（许可原文可从 sources.json 记录的固定 commit 读取，
重建时随导出生成），不受本技能Apache-2.0声明重新许可。
