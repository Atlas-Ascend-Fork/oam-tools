# 离线 API 契约

`aclrt*`、`aclmdl*` 等 Runtime 接口先查官方 runtime 文档：

```bash
python3 scripts/lookup_api_docs.py --corpus references/api-docs/runtime-v9.0.0-beta.2.json.gz --query <完整接口名>
```

语料来自 `https://gitcode.com/cann/runtime`，固定 `v9.0.0-beta.2` /
`330a3a72dd0836546e6a5d13d6ac2802f065b6ac`，收录全部 docs 目录 Markdown 与根 LICENSE
共 614 份、861,768 B。许可遵循上游仓库固定 commit 的原 LICENSE。型号支持、输入标志、
完成语义和错误返回均按匹配接口原文核对；公开版本只作对应版本参考。

按接口所属层选择语料。Ascend C/C API 使用默认 asc-devkit；`aclnn*` 接口查询
ops-nn 文档，并核对参数是否可选、空指针与空 Tensor 的区别及产品/量化模式限制：

```bash
python3 scripts/lookup_api_docs.py --corpus references/api-docs/ops-nn-v9.0.0-beta.2.json.gz --query <完整aclnn接口名>
```

ops-nn 语料包含固定 `v9.0.0-beta.2` 提交
`f597f5b9a661711eb13d1fc5749f6ff900230a65` 下全部 406 份 `docs/` Markdown
与根 LICENSE，来源为 `https://gitcode.com/cann/ops-nn`。不包含实现源码、图片或
其他版本，也不覆盖所有 ACLNN 所属仓库。它和下文 asc-devkit 是两个独立来源。
原始 UTF-8 字节、Git blob、大小与 SHA-256 在导出时核验，查询时再核大小与 SHA。
公开文档版本不等于现场实际加载版本。

搜索命中后用同一 `--corpus` 和精确 `--document` 分页读取参数、返回值和约束。
可选参数不自动意味着支持零元素 Tensor；文档各节相互冲突时引用冲突并保留条件，
不能只挑一条描述定责。公开文档版本不等于现场实际加载版本；零命中只说明本语料
未收录，继续依据已有材料分析。

现场涉及具名 Ascend C/C API，且需要确认参数、类型、单位、存储空间、约束或
生命周期时，可以直接查询包内原文。完整名称优先，注意同名接口的重载、变体和型号。
以下命令从eval-skill目录执行；工具只读取压缩资料并向stdout返回JSON，不联网或写现场。

```bash
python3 scripts/lookup_api_docs.py --query SetSingleShape
python3 scripts/lookup_api_docs.py --query asc_copy_l12fb
```

搜索遍历全部文档，先按文件名匹配，再按正文匹配。`truncated`只表示返回文档数量
受`--limit`限制（默认5，最多20）；每篇仅展示首个命中窗口，不代表正文已读完。
按结果中的精确`path`继续读取参数和约束上下文：

```bash
python3 scripts/lookup_api_docs.py --document docs/api/context/SetSingleShape.md --start-line 1 --lines 120
```

`has_more/next_start_line`指明后续范围；每次最多400行，行号对应原始文本。
支持中文词句和不区分大小写的字面搜索，不支持正则。零命中只说明本资料未找到，
不证明现场没有该API或不支持该能力。语料缺失、损坏、路径未知时退出非零并返回错误，
保留实际错误后继续已有材料分析。

## 语料不在仓库内，按需重建

`*.json.gz` 语料体积超过仓库二进制门禁，不入库。[sources.json](api-docs/sources.json)
记录每个语料的固定 commit、文档数、字节数与 SHA-256。首次使用或校验失败时，按
sources.json 的固定 revision 用 `scripts/export_offline_source.py` 重建：

```bash
# 1) 裸 clone 上游仓库（浅 clone 无法按任意 revision 导出）
git clone https://gitcode.com/cann/runtime.git /tmp/runtime
git clone https://gitcode.com/cann/ops-nn.git /tmp/ops-nn
git clone https://gitcode.com/cann/asc-devkit.git /tmp/asc-devkit

# 2) 从 tool-fault-diagnosis 根目录执行，重建到 references/api-docs/
python3 scripts/export_offline_source.py \
  --git /tmp/runtime/.git --revision 330a3a72dd0836546e6a5d13d6ac2802f065b6ac \
  --version v9.0.0-beta.2 --repository https://gitcode.com/cann/runtime \
  --name runtime --scope docs \
  --output eval-skill/references/api-docs/runtime-v9.0.0-beta.2.json.gz \
  --manifest /tmp/manifest-runtime.json
python3 scripts/export_offline_source.py \
  --git /tmp/ops-nn/.git --revision f597f5b9a661711eb13d1fc5749f6ff900230a65 \
  --version v9.0.0-beta.2 --repository https://gitcode.com/cann/ops-nn \
  --name ops-nn --scope docs \
  --output eval-skill/references/api-docs/ops-nn-v9.0.0-beta.2.json.gz \
  --manifest /tmp/manifest-ops-nn.json
python3 scripts/export_offline_source.py \
  --git /tmp/asc-devkit/.git --revision b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b \
  --version v9.0.0-beta.2 --repository https://gitcode.com/cann/asc-devkit \
  --name asc-devkit --scope docs \
  --output eval-skill/references/api-docs/asc-devkit-v9.0.0-beta.2.json.gz \
  --manifest /tmp/manifest-asc-devkit.json
```

导出脚本自带 refuse-to-overwrite：目标目录已有同名语料或 LICENSE 时拒绝执行，
重建前先删除旧文件。重建后核对 SHA-256 与 sources.json 一致；不一致说明上游
commit 被改写或导出脚本变化，不要使用该语料。

## Ascend C 版本与来源

资料是官方asc-devkit v9.0.0-beta.2，固定提交
`b0a2865d589f87342e4ef1e2a41aed7fcdffcf0b`下docs/api/context全部2092份Markdown
和根LICENSE，2093个原字节对象可从gzip/JSON恢复。查询返回固定版本、原路径、
原文SHA256和公开source_url；当前包不包含图片及该范围以外的源码/文档，不从缺失图片
推断结构或参数。所有文件在打包时核固定Git blob，工具载入时再校验字节数和SHA256。
资料的存在和摘要校验不表示全部文档已获人工语义审查。

先核现场产品、CANN/编译器版本和具体API变体。公开参考不能代替现场二进制、
实参或源码；契约可解释应满足的约束，不单独证明哪个参数违反了约束。已有对应版本
原文时优先使用，版本不匹配或适用条件不明时保留条件。

原资料遵循上游原许可，不受本技能Apache-2.0声明重新许可；许可原文可从
sources.json 记录的上游固定 commit 读取，重建语料时也会随导出生成。
