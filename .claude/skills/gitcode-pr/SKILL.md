---
name: gitcode-pr
description: |
  使用 GitCode API 创建 Pull Request 和获取 PR 评论。当用户需要**创建** GitCode PR、将代码**推送并创建合并请求**、**获取 PR 评论**、**查看 PR 讨论**、**查看 PR 改动**或**删除 PR 评论**时使用此 skill。支持读取普通评论和行内(diff)评论，包括评论内容、文件路径、代码行号等详细信息。
  **必须触发此 skill 的场景**（用户提到以下任何内容时使用）：
  - 创建/提交 PR：创建PR、提个PR、发PR、做个PR、帮我PR、生成PR、需要PR、pull request、merge request
  - 推送代码到远程：push代码、推代码、把代码推上去、提交到远程、推送到gitcode、提交代码到GitCode
  - 合并请求：合并请求、代码合入请求、请求合并、merge request
  - PR模板/描述：PR模板、PR描述、PR格式
  - 关联issue创建PR：关issue的PR、关联issue创建PR
  - 获取PR改动：查看PR变更、PR文件列表、PR改了什么、看PRdiff、获取PR文件
  - **获取 PR 评论**：查看PR评论、PR评论、获取评论、read comments
  - **查看 PR 讨论**：PR discussions、查看讨论、discussions
  - **删除 PR 评论**：删除评论、删除PR评论、移除评论、delete comment、移除这条评论
---

# GitCode PR Skill

创建 GitCode Pull Request 和获取 PR 评论的标准化流程。

## 强制约定：一律走脚本，禁止手写 curl/jq

**所有读写 PR 的操作必须调用 `scripts/pr_ops.py` 对应子命令，禁止手写 curl/jq。** 脚本已固化分页(per_page=100)、流水线终态筛选(排除"触发成功")、引用回复、v5 接口选择与 v4 写接口禁用后的替代指引、fork 来源校验等踩坑逻辑；手写 curl 会重新引入这些错误（漏分页、误判流水线结果、回复发错位置等本 skill 历史反复踩过的坑）。创建 PR 用 `scripts/create_pr.py`。

脚本能力速查（`--owner/--repo` 传 PR 目标仓，即 `resolve-repo` 输出的 `parent_owner/parent_repo`；token 取 `GITCODE_API_TOKEN`）：

| 子命令 | 用途 | 示例 |
|--------|------|------|
| `resolve-repo` | 探测 owner/repo 与 fork 目标仓 | `pr_ops.py resolve-repo` |
| `get-state` | 查 PR 状态(open/merged/closed) | `pr_ops.py get-state --pr N --owner O --repo R` |
| `get-pipeline` | 取最新流水线完成结果(支持 `--since`) | `pr_ops.py get-pipeline --pr N --owner O --repo R` |
| `get-codecheck` | 取 CI 结论(codecheck/precommit pass + commit_id) | `pr_ops.py get-codecheck --pr N --owner O --repo R` |
| `get-reviews` | 列出人类评审意见(排除 robot/自己/lgtm) | `pr_ops.py get-reviews --pr N --owner O --repo R --me ME` |
| `get-files` | 取 PR 文件变更 | `pr_ops.py get-files --pr N --owner O --repo R` |
| `reply` | 引用回复评审(普通评论) | `pr_ops.py reply --pr N --owner O --repo R --body-file F` |
| `reply-review` | 回复进已有评论线程(行内首选) | `pr_ops.py reply-review --pr N --owner O --repo R --discussion-id D --body-file F` |
| `review` | 发行内评审意见(绑定 文件:行号)，**当前不可用**(依赖已禁用的 v4 写接口) | `pr_ops.py review --pr N --owner O --repo R --path P --line L --body-file F` |
| `update-pr` | 更新 PR 描述/标题 | `pr_ops.py update-pr --pr N --owner O --repo R --body-file F` |
| `trigger` | 触发 compile 流水线 | `pr_ops.py trigger --pr N --owner O --repo R` |
| `delete-comment` | 删除指定评论 | `pr_ops.py delete-comment --owner O --repo R --comment-id ID` |
| `issue-prs` | 查 issue 关联的 PR | `pr_ops.py issue-prs --owner O --repo R --issue N` |

脚本路径前缀 `python3 .claude/skills/gitcode-pr/scripts/`。`poll_pipeline.sh` 后台轮询见第 12 节。下文各节给出对应脚本调用；原始 API 细节见 `references/gitcode_api.md`，仅供排查/扩展脚本时查阅，日常操作不直接用。

改动 `pr_ops.py` 后跑一次回归测试（覆盖 `reply-review` 的落点判定与 v4 403 指引；本目录不在云端 `UT_Test` 范围，需手动跑）：

```bash
python3 -m pytest .claude/skills/gitcode-pr/scripts/test_pr_ops.py -q
```

## 工作流程

### 1. 获取访问令牌（第一步必须）

**询问用户**："请提供您的 GitCode 访问令牌（Access Token）"

检查环境变量：
```bash
echo $GITCODE_API_TOKEN
```

如果不存在，提示用户获取令牌：
1. 登录 [GitCode](https://gitcode.com)
2. 点击头像 → 设置 → 访问令牌
3. 创建新令牌，选择 `read_repository`、`write_repository` 和 `read_api` 权限
4. 复制令牌，建议保存到 `~/.bashrc`：`export GITCODE_API_TOKEN="your_token_here"`

### 2. 识别PR的目标仓库

#### 2.1 查询远程仓库

```bash
git remote -v
```

根据远程仓库 URL 确定目标仓库：
- **目标仓库**：PR 要合并到的仓库（通常是 origin 或 upstream）
- **源仓库**：当前工作分支所在的仓库

#### 2.2 提取仓库 owner/repo 信息

**关键**：所有 API 调用都需要使用当前仓库的 owner/repo，而非硬编码。

```bash
# 从远程 URL 提取 owner 和 repo
repo_url=$(git remote get-url origin)

# 处理不同 URL 格式
# SSH 格式: git@gitcode.com:owner/repo.git
# HTTPS 格式: https://gitcode.com/owner/repo.git
if [[ $repo_url == git@* ]]; then
  owner=$(echo $repo_url | sed 's|.*:\([^/]*\)/\([^/]*\)\.git$|\1|')
  repo=$(echo $repo_url | sed 's|.*:\([^/]*\)/\([^/]*\)\.git$|\2|')
else
  owner=$(echo $repo_url | sed 's|.*gitcode\.com/\([^/]*\)/\([^/]*\)\.git$|\1|')
  repo=$(echo $repo_url | sed 's|.*gitcode\.com/\([^/]*\)/\([^/]*\)\.git$|\2|')
fi

# URL 编码（用于 API 路径）
encoded_repo=$(printf '%s' "${owner}/${repo}" | jq -sRr @uri)

echo "Owner: $owner"
echo "Repo: $repo"
echo "Encoded: $encoded_repo"  # 例如: cann%2Fge
```

**后续所有 API 调用都应使用这些变量**：
- GitLab API v4 格式：`/projects/${encoded_repo}/...`
- GitHub API v5 格式：`/repos/${owner}/${repo}/...`

#### 2.3 查询 Fork 的原仓库（当当前仓库是 fork 时）

当当前仓库是 fork 时，PR 目标仓应为其 fork 来源（源仓）。**用脚本一步探测**（已固化 HTTP/jq 校验，查询失败报错退出、绝不静默回退当前仓）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py resolve-repo
```

返回：

```json
{
  "owner": "<当前fork owner>", "repo": "<当前fork repo>",
  "is_fork": true,
  "parent_owner": "<源仓owner>", "parent_repo": "<源仓repo>",
  "parent_encoded_repo": "<源仓owner%2Frepo>"
}
```

**后续约定**：
- 创建 PR / 查 PR 状态、评论、流水线等所有脚本调用的 `--owner/--repo` 一律传 `parent_owner/parent_repo`（源仓）。
- 非 fork（`is_fork=false`）时 `parent_*` 即当前仓，用法不变。

**响应关键字段**：
| 字段 | 说明 |
|------|------|
| `fork` | 是否为 fork 仓库（`true`/`false`） |
| `parent.full_name` | 原仓库完整名称（格式：`owner/repo`） |
| `parent.html_url` | 原仓库网页地址 |
| `parent.default_branch` | 原仓库默认分支 |

**默认目标仓库策略（重要）**：
- **当前仓库是 fork（`fork=true`）时，PR 默认创建到源仓（`parent.full_name`）**，而非当前 fork 仓。
- 创建 PR 时 API 路径中的 `${owner}/${repo}` 使用**源仓**，`head` 使用 `当前fork的owner:分支名` 形式进行跨仓提交。
- 仅当用户明确要求在 fork 仓内部提 PR 时，才使用当前 fork 仓作为目标。

**示例输出**：
```json
{
  "fork": true,
  "parent": {
    "full_name": "cann-agent/skills",
    "html_url": "https://gitcode.com/cann-agent/skills",
    "default_branch": "main"
  }
}
```

### 3. 获取 PR 评论和评审意见

**用脚本拉取人类评审意见**（已固化 per_page=100、排除 cann-robot/自己/`lgtm`-`approve`）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-reviews \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> --me <自己用户名>
```

返回 `{count, reviews:[{discussion_id, comment_type, user, created_at, body}]}`。

**字段说明**（解析时参考）：

| 字段 | 说明 |
|------|------|
| `comment_type` | `diff_comment`=行内评论，`pr_comment`=独立评论 |
| `discussion_id` | 讨论 ID |
| `user` | 评审者用户名 |
| `created_at` | 评论时间 |
| `body` | 评论内容 |

流水线/CI 结论不在此列，分别用 `get-pipeline`、`get-codecheck`（见第 12 节）。

### 4. 获取 PR 文件变更

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-files \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo>
```

返回 `{count, files:[{new_path, old_path}]}`。

### 5. 回复评审意见 / 发表行内评审意见

三种场景，**按评论类型选子命令**：

- **回复 `diff_comment`（已有行内评论）** → 用 `reply-review`，回复挂进该行内线程（见 5.3）。**这是回复行内意见的首选**。
- **回复 `pr_comment`（总结/独立评论）** → 用 `reply`（引用回复，见 5.1）。
- **作为评审者新发起行内意见**（绑定 diff 某一行）→ 用 `review`（见 5.2；依赖已禁用的 v4 写接口，当前不可用，脚本会给替代指引）。

#### 5.1 回复评审意见（引用回复，reply）

**适用对象：`pr_comment` 类型的总结/独立评论**（含机器人 `cann-tool-pr-reviewer` 的整轮结论）。这类评论的内容通常是"一轮多条意见的汇总"，逐条对应关系需要自己在正文里建立，故用引用回复：发一条普通 PR 评论，正文 `@评审者` 并用引用块（`>`）逐条摘录每条意见的 `文件:行号` + 原文，紧跟处理说明（已采纳/commit、替代方案、或不成立的理由），一一对应。

> 实测边界（2026-08-01 复测）：v5 `discussions/<id>/comments` 对 `diff_comment` 与 `pr_comment` **都能挂进线程**（两者回查 `discussion_id` 均与目标一致）。既然两类都能挂，选哪种就不看"能不能"，而按下面的判据看"哪种读起来对得上"：
>
> | 目标评论 | 该评论承载的意见数 | 选择 | 理由 |
> | --- | --- | --- | --- |
> | `diff_comment`（行内） | 1 条，已绑定 `文件:行号` | `reply-review`（5.3） | 回复落在该代码行旁，与意见天然一对一 |
> | `pr_comment`（总结） | 一轮多条，未绑定行号 | `reply` 引用回复（本节） | 挂进线程只是一条长回复跟在一条长意见后，逐条对应关系全靠读者自己对齐；引用块能把每条意见的 `文件:行号` + 原文与处理说明并排摆出 |
>
> 即**判据是"一条评论对应几条意见"**：一对一走线程回复，一对多走引用回复。`pr_comment` 能挂线程但仍不首选，原因只是落点不直观、非接口不支持。

**用脚本发引用回复**（已固化 v5 普通评论 + 发后回查确认可见）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py reply \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
  --me <自己用户名> --body-file /tmp/reply.md
```

正文（你撰写，写入 `/tmp/reply.md`）结构示例：

```markdown
[@评审者](https://gitcode.com/评审者) 感谢评审，意见已处理（commit <sha>）。

> 文件路径:行号 评审意见原文摘录（major/...）

已处理：<具体改动说明>。
```

#### 5.2 发表行内评审意见（review，绑定文件:行号）

作为评审者给 PR 提意见、且要让意见**挂在 diff 的具体代码行旁**时，用 `review`。脚本自动从 `files.json` 取 `diff_refs`(base/start/head sha) 拼 position，再 POST v4 discussions，无需手动取 sha：

> **当前不可用**：v4 **写接口**已被服务端禁用（POST 恒 403 `当前 /api/v4 接口已禁用`；**读接口 GET 仍返回 200**，故"v4 全废"的说法不准确），且 v5 无等价接口——v5 发评论虽接受 `path/line` 却静默忽略、落成普通评论。故**新发起**行内评论暂无可用接口。已有行内评论的**回复**不受影响（走 5.3 `reply-review`，v5 可用）。需要新提行内意见时，改用 `reply` 发普通评论、正文内注明 `文件:行号`。
>
> 脚本已把该 403 映射为替代指引（不再抛原始 403），直接跑 `review` 会得到：`发行内评论失败 (HTTP 403): v4 写接口已被服务端禁用…替代：回复已有评论用 reply-review；新提意见用 reply…`。**禁用是服务端状态而非本仓决定**，故实现保留未删——v4 写接口若恢复，本命令无需改动即可自愈。

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py review \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
  --path <文件相对路径> --line <行号> \
  --body-file /tmp/review.md [--start-line <起始行号>] [--severity suggestion|warning]
```

- `--line`：评论锚定的（结束）行号，对应新代码（`new_line`）。
- `--start-line`：多行选择的起始行号；省略即单行评论。
- `--severity`：`suggestion`（默认）或 `warning`。
- 返回 `{posted, discussion_id, path, line}`。

#### 5.3 回复已有行内评论（reply-review，落在对应线程）

回复**别人发起的某条行内评论**、且要让回复**挂在那条行内评论的线程里**（而非另起独立评论）时，用 `reply-review`。先用 `get-reviews` 取目标评论的 `discussion_id`，再回复：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py reply-review \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
  --discussion-id <目标行内评论的 discussion_id> --body-file /tmp/reply.md
```

脚本走 v5 `POST /repos/O/R/pulls/<pr>/discussions/<discussion_id>/comments` 回复后，用 v5 单条评论接口回查，返回 `{posted, note_id, discussion_id, comment_type, in_thread}`。**`in_thread=true` 才表示回复确实落在该线程里**（GET discussion 接口不可用、v5 列表不收线程回复，故 `in_thread` 由单条接口核对 discussion_id 得出，是权威判据）。回复行内评论时 `comment_type=DiffNote`。

> **`in_thread` 为 `null` 时看 `warn` 字段**：落点判不出来时脚本会多输出一个 `warn`，说明是"响应缺 `note_id`（附实际响应 keys）"还是"回查失败（附 HTTP 码）"——`posted:true` 只代表 POST 成功，**不代表落点已确认**，见到 `warn` 要人工到 PR 页面核对回复位置。
>
> **ID 语义（易错）**：该接口响应里 `id` 是 **discussion_id(hex)**、`note_id` 是**数字评论 id**。回查（`/pulls/comments/<X>`）与 `delete-comment` 都必须传**数字 `note_id`**，传 hex 会 400。脚本已按此取值，手动排查时注意别取错。
>
> 三者区别：`reply` 发**不绑定行**的独立评论（回复总结类评审/汇总，v5 可用）；`reply-review` 把回复**挂进别人已有的评论线程**（顺着某条行内意见往下答，v5 可用，回复行内意见首选）；`review` **新发起**绑定 diff 某行的行内评论（逐行提意见，依赖已禁用的 v4 写接口，当前不可用）。

### 6. 删除 PR 评论

**重要**：只能删除自己创建的评论，或具有仓库管理权限。

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py delete-comment \
  --owner <parent_owner> --repo <parent_repo> --comment-id <COMMENT_ID>
```

返回 `{deleted, http_code}`。评论 ID 可从 `get-reviews` 输出中取。

### 7. 创建 PR 的正确流程

**关键**：源分支必须基于**源仓**的目标分支，确保 PR 只包含期望的变更。

fork 场景下需区分两个远程：
- **源仓远程**（通常是 `upstream`，指向 `parent.full_name`）：PR 要合入的仓库，基线应从这里拉。
- **个人 fork 远程**（通常是 `origin`）：自己的工作分支推送到这里。

```bash
# 0. 确认/添加/校正源仓远程，确保 upstream 确实指向源仓
upstream_url="https://gitcode.com/${parent_owner}/${parent_repo}.git"
if git remote get-url upstream >/dev/null 2>&1; then
  # 已存在 upstream：归一化后精确比对 owner/repo，避免基于错误仓库拉分支。
  # 归一化：去协议/主机、去结尾 .git，兼容 https://host/o/r(.git) 与 git@host:o/r(.git)
  cur=$(git remote get-url upstream)
  cur_path=$(echo "$cur" | sed -E 's#^[^:]+://[^/]+/##; s#^[^@]+@[^:]+:##; s#\.git$##')
  if [ "$cur_path" = "${parent_owner}/${parent_repo}" ]; then
    : # 已正确指向源仓
  else
    echo "WARN: upstream 当前指向 $cur, 修正为源仓"
    git remote set-url upstream "$upstream_url"
  fi
else
  git remote add upstream "$upstream_url"
fi

# 1. 从源仓拉取目标分支（默认 master）
git fetch upstream <目标分支>

# 2. 基于源仓的目标分支创建新分支
git checkout -b <新分支名> upstream/<目标分支>

# 3. Cherry-pick 需要的 commit
git cherry-pick <commit-sha>          # 单个 commit
# 或
git cherry-pick <sha1> <sha2>         # 多个 commit

# 4. 推送到个人 fork 远程（origin）
git push origin <新分支名> -u
```

> 仅当明确要在 fork 仓内部提 PR 时，才改用 `origin/<目标分支>` 作为基线。

> **提交前本地检查（强烈建议，按顺序执行）——先检查、后推送**：
> 1. **首次克隆后装钩子**：`pre-commit install`（`.git/hooks/` 不随仓库走，每个 clone 各装一次）；之后每次 `git commit` 自动对改动文件检查。
> 2. **保持 diff 精准**：本地钩子及其排除目录以 `.pre-commit-config.yaml` 为准，其中包含 Ruff 检查和格式化。自动修复与格式化可能修改文件；检查后用 `git diff` 和 `git diff --cached` 核对工作区及暂存区，确认只保留本次意图改动。
> 3. **运行本地检查**：提交前执行 `pre-commit run --files <本次修改文件>`，运行当前配置中适用于这些文件的钩子。若钩子修改了文件，核对差异后重新暂存并运行检查。
> 4. **核对云端结果**：本地钩子与云端 CodeCheck 的规则和扫描范围可能不同，提交后仍需确认流水线对应当前 PR 的 HEAD，并按具体检查日志处理失败项。
> 5. **改动文档必须中英文同步（强制）**：本仓文档成对维护（中文 + `_en` 英文版）。**每改一个文档，先查它有无对应语言版本，有则在同一个 commit 里一并改**——只改单语会让两版内容长期背离，评审会要求补齐。
>
>    改完中文（或英文）后，用下面命令列出本次改动文档的对应版本，逐个同步。判据是**整个 PR 范围**（已提交 + 暂存 + 工作区），而非只看暂存区——否则先提交的那一版会被误报成"未同步"：
>
>    ```bash
>    # <source_remote>/<base_branch> 同"控制 commit 数量"一节, 通常 upstream/master
>    BASE=upstream/master
>    # 本 PR 内改动过的全部 .md（已提交 + 暂存 + 工作区）
>    changed=$( { git diff --name-only "$BASE"...HEAD -- '*.md'; git diff --name-only -- '*.md'; \
>                 git diff --cached --name-only -- '*.md'; } | sort -u )
>    for f in $changed; do
>      case "$f" in
>        *_en.md) peer="${f%_en.md}.md" ;;
>        */en/*)  peer="${f/\/en\//\/zh\/}" ;;
>        */zh/*)  peer="${f/\/zh\//\/en\/}" ;;
>        *)       peer="${f%.md}_en.md" ;;
>      esac
>      if [ ! -f "$peer" ]; then
>        echo "NONE 无对应版本(无需同步): $f"
>      elif printf '%s\n' "$changed" | grep -qx "$peer"; then
>        echo "OK   已同步: $f + $peer"
>      else
>        echo "TODO 需同步: $f -> $peer"
>      fi
>    done
>    ```
>
>    本仓已知成对文档：`README.md`↔`README_en.md`、`examples/README.md`↔`examples/README_en.md`、`AGENTS.md`↔`AGENTS_en.md`、`CONTRIBUTING.md`↔`CONTRIBUTING_en.md`、`SECURITY.md`↔`SECURITY_en.md`、`src/hccl_test/README.md`↔`src/hccl_test/README_en.md`、`docs/zh/**`↔`docs/en/**`。
>
>    同步的是**结构与事实**：章节增删、表格列增删、链接目标、命令与环境变量（如 `${ASCEND_HOME_PATH}`）、锚点，两版都要一致；英文版按英文标题重算锚点（`## 🔧 Source Code Compilation` → `#source-code-compilation`，见下方「锚点按 GitCode 规则生成」）。若对应语言的下游文档尚未翻译（如组件指南仅有 `docs/zh/`），英文版链接指向中文文档并加一句说明，不要留死链。
>
>    上面命令输出 `TODO 需同步` 时，补齐后再进入下一步；`NONE` 表示该文档无对应版本，跳过即可。
>
>    **锚点只指向"两套规则一致"的标题**。本仓锚点要同时满足两个互不相让的判定方，二者对同一标题给出的 slug 可能不同：
>
>    | 判定方 | 作用 | 不满足的后果 |
>    | --- | --- | --- |
>    | GitCode 渲染器 | 决定网页上点击能否跳转 | 链接点不动（人工可见，评审会提） |
>    | 流水线 `StaticCheck_link_validity` | 决定门禁过不过 | 报「锚点无法访问」→ **FAILED 阻断合入** |
>
>    **两者只在两类标题上分歧**（实测于 PR #443）：
>
>    | 标题形态 | GitCode 渲染 | 流水线期望 | 结论 |
>    | --- | --- | --- | --- |
>    | `## 🔧 源码编译`（含 emoji） | `#源码编译` | `#-源码编译` | ⚠️ 冲突，无两边皆可的写法 |
>    | `## asys（故障信息收集 / 诊断）`（含 ` / `） | `#asys故障信息收集-诊断` | `#asys故障信息收集--诊断` | ⚠️ 冲突 |
>    | `### 安装`、`## 环境准备`（纯文字） | `#安装` | `#安装` | ✅ 一致，安全 |
>    | `## msprof（性能调优）`（含括号，无 emoji 无 `/`） | `#msprof性能调优` | 同 | ✅ 一致，括号删除且不补 `-` |
>
>    因此**写锚点前先看目标标题属于哪类**，按下面两条处理：
>
>    1. **目标标题是纯文字或仅含括号** → 直接写锚点，两边都过。
>    2. **目标标题含 ` / `** → 分隔符改为「与」/`and`（`asys（故障信息收集 / 诊断）` → `asys（故障信息收集与诊断）`），标题即脱离冲突形态，深链照常写。
>    3. **目标标题含 emoji（本仓 `README*.md` 的 h2 全部如此）** → **保留 h2 的 emoji 不动，在其下按内容拆出无 emoji 的 h3，锚点指向 h3**。这样既不动仓库既有观感，又能让链接精确落到子章节、比链到整个大节更有用：
>
>       ```markdown
>       ## 🔧 源码编译          ← h2 保留 emoji, 不作为锚点目标
>       ### 加载环境变量         ← 无 emoji, 可作锚点
>       ### 执行编译             ← [源码编译](#执行编译) 指向这里
>       ### 编译参数与依赖说明
>
>       ## 📦 安装与验证         ← h2 保留 emoji
>       ### 安装                 ← [安装](#安装)
>       ### 验证                 ← [验证](#验证)
>       ```
>
>       链接指向语义最贴近的那个 h3，而非笼统指向大节：正文「按 `[源码编译](#执行编译)` 构建」落在「执行编译」、「参考 `[安装](#安装)` 与 `[验证](#验证)`」分别落在两个子节。跨文件同理（`[编译](../README.md#执行编译)`）。
>
>       原 h2 下若没有子标题可指，就按内容拆出来——拆分本身也让长章节更易读。仅当章节内容确实无法再分时，才退化为不写锚点（同文件内改纯文字「见下方「X」章节」，跨文件只链到文件）。
>
>    **本仓现状**：`README.md`/`README_en.md` 的 h2 全带 emoji，其下已拆出无 emoji 的 h3（`加载环境变量`/`执行编译`/`编译参数与依赖说明`、`安装`/`验证`，英文对应 `Loading Environment Variables`/`Running the Build`/`Build Parameters and Dependencies`、`Installation`/`Verification`），锚点一律指向这些 h3；`examples/README*.md` 的组件标题无 emoji，可直接深链。
>
>    改完后用流水线产物自查（该 CSV 公开、无需 token，逐条列出被拒锚点）：
>
>    ```bash
>    curl -sL "https://ascend-ci.obs.cn-north-4.myhuaweicloud.com/<repo>/package/<PR>/link_validity_check.csv"
>    ```
>
>    需要确认 GitCode 侧真实 `id` 时（仅在源仓 + 不含 `/` 的分支名上返回服务端渲染结果；fork 仓或分支名带 `/` 时是客户端渲染、grep 不到）：
>
>    ```bash
>    curl -sL "https://gitcode.com/<owner>/<repo>/blob/<branch>/README.md" \
>      | grep -oE '<h[123][^>]*id="[^"]*"' | sed 's/.*id="/id="/'
>    ```
>
>    **判断锚点是否有效只看这两个来源的实际输出**：仓内已有同样写法只说明该写法被重复过，不构成它能跳转的证据——本仓 `#-源码编译` 这类 GitHub 式写法曾在十余处并存，在 GitCode 上全部失效。
> 6. **push 前必跑全量 UT（强制，无论创建 PR 还是后续修改）**：云端 `UT_Test` 跑**全部组件**（`asys`/`msaicerr`/`msprof` 等），任一用例失败即 FAILED 阻断。**只跑自己改动相关的测试不够**——改动可能被其他组件的测试间接依赖（例如改 `build.sh` 会让 `test/ut/asys/testcase/common/test_build_script.py` 这种"校验脚本写法"的测试失败）。因此每次 push 前在仓库根目录跑：
>    ```bash
>    bash build.sh -u --ut --noexec 2>/dev/null  # 若已 build 过, 可直接复用下面 pytest
>    # 或直接对各组件 pytest（已 build 过、环境就绪时更快）：
>    python3 -m pytest test/ut/asys/ test/ut/msaicerr/ -q
>    ```
>    全绿才 push。本地缺依赖跑不全的组件（如 msprof gtest 需编译）要在汇报里说明"本地未覆盖 X，依赖云端 UT_Test"。
>
> **`--no-verify` 慎用**：仅在确认钩子报的是未触及行的存量问题时才用，且用前必须 `git diff --cached` 核对——否则会把 pre-commit 自动改动（如历史遗留的 ruff-format 重排）一并提交，正是 diff 被污染的根源。
>
> **`git reset --hard` 慎用**：它会丢弃未提交的工作区改动与未跟踪新文件。清理临时测试文件用 `git rm --cached` + `rm`；动 `reset --hard` 前先 `git stash` 或 commit 未完成工作。

> **推送后固定动作（先完成上面的本地检查并 push，再每次按顺序执行）**：
> 1. **push 必须先于 trigger，且必须确认 PR 页面 HEAD 已更新后再触发**：
>    ```bash
>    # Step 1: push
>    git push origin <branch> --force-with-lease
>    # Step 2: 等待 GitCode PR 页面刷新（push 后可能有短暂延迟）
>    sleep 3
>    # Step 3: 确认 PR head.sha 已是本次 commit，再触发；否则报错不触发
>    LOCAL_SHA=$(git rev-parse HEAD)
>    REMOTE_SHA=$(curl -s -H "private-token: $GITCODE_API_TOKEN" \
>      "https://gitcode.com/api/v5/repos/<parent_owner>/<parent_repo>/pulls/<PR>" \
>      | python3 -c "import sys,json; print(json.load(sys.stdin)['head']['sha'])")
>    if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
>      python3 .claude/skills/gitcode-pr/scripts/pr_ops.py trigger --pr <PR> --owner <parent_owner> --repo <parent_repo>
>    else
>      echo "ERROR: PR head.sha ($REMOTE_SHA) != local HEAD ($LOCAL_SHA), do NOT trigger. Retry after a few seconds."
>    fi
>    ```
>    **原因**：GitCode 流水线由 `compile` 评论触发，触发时拉取的是 PR 的 `head.sha`；若 PR 页面尚未刷新到最新 commit，流水线跑的不是本次改动。push 成功不等于 PR 页面立即刷新，必须用 if/else 真正拦截（python3 exit 0 不会阻断 `&&`）。trigger 返回 `{triggered:true}` 后立即 `date '+%Y-%m-%dT%H:%M:%S%z'` 记下时间戳，供第 12 节监控 `--since` 用。无条件触发，即便纯文档改动也触发。
> 2. **判断是否同步 PR 描述**：本次改动若使描述过时（新增文件/功能、改变实现方式、解决新评审、累积多块改动）→ 用 `pr_ops.py update-pr` 更新；纯小修通常无需。是否更新由你判断，接口调用由脚本完成。
> 3. **跟进流水线结果**：按第 12 节监控（脚本轮询 + 模型判断）。

> **控制 commit 数量（云端 `Check_Pr` 硬门禁，每次 commit 前必须执行）**：
>
> ```bash
> # 每次 commit 前必跑，输出 >4 立即停下按规则处理
> # <source_remote> = 指向源仓的 remote（有 upstream 用 upstream，否则查 git remote -v 确认）
> # <base_branch>   = PR 目标分支（通常 master）
> git rev-list --count <source_remote>/<base_branch>..HEAD
> ```
>
> CANN 仓 `Check_Pr` 要求**单个 PR 的 commit 数不超过 5 个**，超过即 `Check_Pr` FAILED 阻断合入。按下列规则选提交方式：
> 1. **非重大逻辑变更**（修流水线、采纳评审、补门禁、文档/注释微调等）→ 用 `git commit --amend` 合并进上一个相关 commit，不新增 commit 数。amend 已推送的 commit 后用 `git push --force-with-lease` 覆盖远程。
> 2. **重大变更**（新增功能/文件、改变实现方式、引入独立主题）→ 自主判断：可新增一个 commit，**但新增后 commit 总数仍须 ≤5**；若新增会超 5，则改用 `git reset --soft <source_remote>/<base_branch>` 收回全部改动到暂存区、再按逻辑主题分组重提为 ≤5 个 commit（reset 前先 `git branch -f backup-xxx HEAD` 备份，重提后用 `git diff backup-xxx --stat` 校验内容零差异，确保未丢改动）。
> 3. **任何时候 commit 数逼近或超过 5** → 立即按主题 squash 到 ≤5（同上 reset --soft + 分组重提），再 `--force-with-lease` 推送。
>
> **红线**：`git rev-list --count` 返回 ≥5 时，禁止直接 `git commit`，必须先 squash 或 amend。

**示例：基于源仓 master 提交单个 commit**
```bash
git fetch upstream master
git checkout -b fix/gcc13-link-error upstream/master
git cherry-pick 4fbf3b183
git push origin fix/gcc13-link-error -u
```

### 8. 创建 PR

**目标仓库策略**：
- **当前仓库是 fork 时，PR 默认创建到源仓（`parent.full_name`）**，API 路径中的 `${owner}/${repo}` 使用源仓。
- `head` 使用 `当前fork的owner:分支名` 形式跨仓提交。

**目标分支策略**：
- **默认合入源仓的 `master` 分支**，除非用户明确要求合入其他分支（如 `develop`、`release/x.y`）。

**用脚本创建 PR**（以源仓 `cann/oam-tools`、fork owner `sinat_31531339` 为例）：

```bash
python3 .claude/skills/gitcode-pr/scripts/create_pr.py \
  --owner <parent_owner> --repo <parent_repo> \
  --title "docs: 优化文档描述(#32)" \
  --head "fork_owner:fix/issue-32-description" \
  --base master --body-file /tmp/pr_body.md
```

**参数说明**：
- `--title`: PR 标题（必填）
- `--head`: 源分支，格式 `fork_owner:branch`（必填，跨仓提交时使用 fork 仓 owner）
- `--base`: 目标分支，**默认为源仓的 `master`**，除非用户明确要求合入其他分支
- `--body-file`: PR 描述文件（按下方模板撰写后传入；避免命令行转义问题）

**关联 Issue（解决 issue 的 PR 必须做）**：

当 PR 是为了解决某个 issue 时，**必须将 PR 关联到对应 issue**，便于追溯。

- **标题**：以 `(#issue_number)` 结尾，如 `test: msprof UT 新增覆盖率(#108)`。
- **描述**：正文包含 `关联 Issue #issue_number`，并在 PR 右侧「关联 Issue」面板添加对应 issue 链接。
- **issue 关闭时机**：保持 issue 开启，由用户在 PR 合入后自行手动关闭。为此：描述里用纯文本 `关联 Issue #issue_number`（而非 `Closes`/`Fixes` 等触发自动关闭的关键字），「合并后关闭已关联的 Issue」复选框保持不勾选。
- **合并后**：保持 issue 开启不动；如需确认关联是否生效，查 issue 关联的 PR：

```bash
# 查 issue 关联的 PR（确认关联生效，但不关闭 issue）
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py issue-prs \
  --owner <parent_owner> --repo <parent_repo> --issue <ISSUE_NUMBER>
```

### 9. PR URL 格式

创建 PR 后，PR 的访问地址格式为（注意是 `/pull/` 而非 `/pulls/`）：

```
https://gitcode.com/${parent_owner}/${parent_repo}/pull/<PR_NUMBER>
```

> fork 场景下 PR 位于源仓，故用 `${parent_owner}/${parent_repo}`；仅 fork 内部 PR 才用 `${owner}/${repo}`。

**示例**：`https://gitcode.com/cann/ge/pull/1807`

### 10. 触发构建流水线

PR 创建后，通过在 PR 评论区发布 `compile`（纯文本，不带斜杠）触发流水线。**用脚本触发，不要现写 curl**——脚本已固化评论正文与接口选择：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py trigger \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo>
```

返回 `{"triggered": true, "via": "v5", "ts": "<触发时刻>"}`。

**原理参考**（脚本内已实现，无需手动操作）：
- 触发指令必须是 `compile` 纯文本；`/build`、`/compile`（带斜杠）无效。
- 直接 POST v5 `/pulls/<PR>/comments`。早期实现先试 v4 `merge_requests/<PR>/notes`（为绕开 v4 长文本返回 `{id:null}`）再回退 v5；**v4 写接口已被服务端禁用（POST 恒 403），该尝试是每次调用都白跑一次的往返，已去掉**，`via` 恒为 `"v5"`。
- fork 场景 PR 位于源仓，`--owner/--repo` 传源仓（即 `resolve-repo` 输出的 `parent_owner/parent_repo`）。

### 11. CLA 与审批门禁

PR 创建后 `cann-robot` 会自动评论检查 CLA 签署与审批进度：

- **CLA 未签署**：常见原因是 commit 使用了 Git 自动生成的邮箱（如 `user@hostname.local`）。需先[签署 CLA](https://clasign.osinfra.cn)，或将 `git config user.email` 改为已签署邮箱后 `git commit --amend --reset-author` 并强推，然后评论 `/check-cla` 复检。
- **审批门禁**：通常需 ≥2 人 `/lgtm` + ≥1 人 `/approve`，committer 可在评论区操作。

### 12. 后续跟进（监控 PR 状态）

**创建 PR 并触发流水线后，默认不自动启动监控**。完成第 7 步（push && trigger）后，向用户展示进度报告表格（见"输出格式 → 进度报告"），并提供以下选择：

> **是否启动流水线监控？**
> - **A. 启动后台监控**（推荐）：脚本在后台轮询，流水线出结果后自动唤醒处理。适合不想手动盯的场景。
> - **B. 我自己查看**：不启动监控，你在 PR 页面查看结果后回来告知。
> - **C. 立即查询一次**：现在主动查一次流水线状态，不持续轮询。

用户选 A 才启动 `poll_pipeline.sh`；选 B/C 则按需执行对应动作，不启动后台进程。

**启动监控（单轮，固化命令——必须照抄，避免误判进程与取到旧结果）**：

> 两个历史踩坑：①用 `pgrep -f poll_pipeline.sh` 判断进程会**误匹配自己这条含该字符串的命令**，把"没在跑"误判成"在跑"；②刚 push 后新流水线还没出结果，`get-pipeline` 取到的是**上一轮旧结果表**，会把旧的 FAILED 当成本轮结果误报。下面命令固化了两者的正确做法。

1. **记录本次 push 时间**（用于 `--since` 过滤，绝不能省）：push 完立即 `date '+%Y-%m-%dT%H:%M:%S%z'` 存为 `PUSH_TS`。

2. **清旧结果 + 后台启动轮询脚本**（`--since` 传 `PUSH_TS`，脚本只认该时刻之后的新结果表，旧结果一律不取）：

   ```bash
   rm -f .gitcode-handoff/result-<PR>.json   # 清掉上一轮残留, 避免 Monitor 立即被旧结果唤醒
   nohup bash .claude/skills/gitcode-pr/scripts/poll_pipeline.sh \
     --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
     --interval 120 --max-wait 3600 --since "<PUSH_TS>" > /tmp/poll-<PR>.log 2>&1 &
   disown
   ```

3. **确认进程真在跑**（用 `ps aux | grep` 且**排除 grep 自身和当前命令**，不要用 `pgrep -f`）：

   ```bash
   sleep 2
   ps aux | grep "poll_pipeline.sh" | grep -v grep | grep -q "pr <PR_NUMBER>" \
     && echo "poll running ok" || echo "poll NOT running"
   ```

4. **用 Monitor 监听结果文件**，脚本写出 `result-<PR>.json` 即唤醒本 agent，无需自己 sleep 轮询。

5. **被唤醒后先核对结果是不是本轮的**（防旧结果误报）：读 result 后用 `get-pipeline --since "<PUSH_TS>"` 复核，若返回 `has_result=false` 说明本轮流水线**还没出结果**（读到的是旧残留），继续等待、不要据此判断；只有 `--since` 过滤后仍有结果表才是本轮真实结果。

6. **读 result 判断**（脚本输出 `{state, has_result, pipeline_pass, failed_tasks, timeout}`）：
   - `state=merged` → 完成。
   - `state=closed` → 被关闭，向用户汇报。
   - `pipeline_pass=true` → 流水线通过，按 12.2 取评审意见、回复。
   - `pipeline_pass=false`（真失败）→ 按 12.1 定位根因 → 改码 → `git push` → `pr_ops.py reply` 回复评审 → `pr_ops.py trigger` 重新触发 → 回到第 1 步重起一轮 poll（多轮循环）。
   - `timeout=true` → 超时仍无结果，向用户汇报由人工查看。

**监控对象是 PR 本身**（按 PR 号持续盯它的 `state`、最新流水线结果与新评审），不绑定某一次 commit；推送新 commit、重新触发后复用同一轮询循环，不为每个 commit 另起监控。每轮关注三件事：①流水线结果 ②人类评审意见（非 robot、非自己，可能在流水线通过后分多轮陆续提出，故每轮重新拉取）③PR `state`。直到 `merged`/`closed` 或出现需人工介入的阻塞为止。

**职责边界**：脚本做轮询/取结果/触发/回复的 API 调用（确定性）；本 agent 只做定位根因、改代码、判断评审是否采纳、撰写回复正文（需判断力）。所有读取/回复操作都调 `pr_ops.py` 子命令拿 JSON，不要现写 curl/jq（脚本已固化 per_page=100、终态筛选、引用回复等踩坑逻辑）。先用 `resolve-repo` 拿 `parent_owner/parent_repo`，下文 `--owner/--repo` 均传这两个值。

> **可选：跨独立 agent 交接**。若用户要求把轮询交给另一台机器/另一个独立 agent（而非本地脚本），改写交接文件 `.gitcode-handoff/pipeline-<PR>.json`（含 pr/owner/repo/branch/head_sha），由该 agent 读取后调用同一套 `pr_ops.py` 执行。

下面 12.1–12.4 是被唤醒后处理流水线、评审、闭环、描述同步的具体动作。

#### 12.1 流水线：未通过则查因、修复、重新触发

构建/门禁结果由 `cann-robot` 在评论区回报。但 `cann-robot` 还会发布 CLA、审批进度、label notification、「流水线任务触发成功」等**非结果**评论，不能取最后一条当结果。**用脚本取完成结果，已固化"只认含任务表与终态(SUCCESS/FAILED/WARNING)、排除触发成功"的筛选**：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-pipeline \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo>
```

返回 `{has_result, all_success, tasks, failed_tasks, created_at}`。判断：
- `has_result=false` → 流水线仍在跑，**继续等待**，不要据此判断状态。
- `has_result=true && all_success=true` → 流水线通过，进入 12.2 看评审意见。
- `has_result=true && all_success=false` → 看 `failed_tasks`：含 `FAILED`/`FAILURE`/`ERROR` 为真失败；仅 `WARNING` 通常不阻断合入，由你结合任务名判断是否需处理。

真失败时**必须**：
  1. **UT_Test / codecheck 失败 → 直接向用户索要报错日志**，不要自己尝试获取（OBS 产物 `ut_cov.tar.gz` 有鉴权 AccessDenied、openlibing 看板需登录有 WAF，程序化都拿不到；自己反复试既耗 token 又拿不到、还易被旧结果误导）。向用户明确请求："请把 PR 页面里 `UT_Test`（或 codecheck）失败的报错日志贴给我"，拿到日志再定位。其他类型失败（如 `Check_Pr` commit 数超限、编译错误评论可见）可自行从评论/规则判断。
  2. 拿到日志后定位**根因**。
  3. 在本地分支**修复**，提交并推送到 PR 源分支（`git push origin <branch>`）；推送前按第 7 节"提交前本地检查"**跑全量 UT**确认本地全绿。
  4. 执行**推送后固定动作**（见第 8 节）：一律 `pr_ops.py trigger` 触发 → 判断是否 update-pr → 跟进。
  5. 回到 12.1 继续轮询，直到流水线通过。

> **每次修改并推送后，判断是否需同步更新 PR 描述**（见第 12.4 节）。新增文件/功能、改变实现方式、解决新的评审问题时，描述应随之更新；纯 bugfix/格式调整通常无需改。

**codecheck / precommit 门禁专项**：这两项的"通过与否"结论可脚本化获取——

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-codecheck \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo>
```

返回 `{codecheck_pass, codecheck_result, precommit_result, commit_id, detail_url}`。`commit_id` 可确认结论对应哪次提交。但**逐条告警明细只能由用户提供**：明细在 `detail_url`（openlibing 看板）需登录查看、有 WAF 拦截程序化访问，且严禁把 token 发往该第三方域名——`get-codecheck` 只能告诉你 pass/fail，**拿不到逐条明细**。codecheck 失败时**直接请用户把报错明细贴给你**（用户在浏览器看板复制，或导出 xlsx 后贴关键行），不要自己反复尝试下载/解析（既拿不到又耗 token）。拿到明细后再定位修复。codecheck 是 Python 增量检查，编码须守仓库规范（print→logging、避免函数内 sys.exit、subprocess 用绝对路径、返回值一致、推导式不超两子句等），可先按第 7 节运行当前配置的本地检查，再结合云端明细定位。

#### 12.2 评审意见：标准处理流程

**第 1 步：拉取全部评审意见**

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-reviews \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> --me <自己用户名>
```

返回 `{count, reviews:[{discussion_id, comment_type, user, created_at, body}]}`。

**第 2 步：对每条意见，先审视再决定**（不无脑照改）：
- 合理且应采纳 → 改码。
- 不认同或有更优方案 → 在回复里说明理由与替代方案。
- 疑问/澄清类 → 回复解答，无需改码。

判断依据参考 `superpowers:receiving-code-review`：先理解意图、技术上核实，再决定采纳与否，而非表演式同意或盲目实现。

**第 3 步：逐条回复——按 `comment_type` 选对子命令，每条都要回**：

| `comment_type` | 含义 | 回复方式 |
|----------------|------|----------|
| `diff_comment` | 绑定 `文件:行号` 的行内意见 | `reply-review --discussion-id <该条 did>` 逐条挂进对应行内线程；回查 `in_thread=true` 才算成功 |
| `pr_comment`（有实质内容） | 整轮总结意见 | `reply` 引用回复（`@评审者` + 引用块逐条摘录 + 处理说明） |
| `pr_comment` 为 `/lgtm`、`/approve` | 门禁指令 | 无需回复 |

逐条行内回复（`get-reviews` 输出里每条 `diff_comment` 的 `discussion_id`）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py reply-review \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
  --discussion-id <该行内意见的 discussion_id> --body-file /tmp/r.md
```

总结意见的引用回复见第 5.1 节。

> 覆盖性要求：`get-reviews` 返回的每条意见（除 `/lgtm`-`/approve`）都要有对应回复——逐条遍历 reviews，按 `comment_type` 各走对应子命令，行内与总结均覆盖。

**第 4 步：改码并推送后**，执行第 8 节**推送后固定动作**（一律 trigger 触发 → 判断 update-pr → 跟进），回到 12.1 轮询。

#### 12.3 闭环条件

**流水线通过 ≠ 可以停止监控。** 监控的终点只有一个：PR `state` 变为 `merged`（或 `closed`）。在那之前必须**持续监控**，因为人类评审意见往往在流水线通过后才陆续出现，且 `/lgtm`、`/approve` 等审批要等评审被回应、问题被解决后才会给。因此：

- **持续轮询直到 `state=merged`/`closed`**，不要因"流水线全绿"就结束跟进或交接。流水线绿只是必要条件之一，合入还需评审通过 + 审批门禁满足。
- **每轮都重新 `get-reviews` 拉取人类评审意见**（评审可能分多轮、在不同时间点提出）。**只要有未回复的评审意见，就必须按 12.2 逐条回复**（采纳则改码+回复、不采纳则说明理由）——评审者通常要看到回应才会 `/lgtm`，漏回复会卡住合入。
- 改码回复后按第 8 节推送后固定动作（push && trigger 一条命令）重新触发，复用同一监控继续。

持续轮询直到满足其一：
- `state=merged`（流水线通过 + 评审通过 + 门禁满足，通常 `cann-robot` 自动合入）→ 完成，向用户汇报合入。
- `state=closed` 或出现需用户决策的阻塞（如 CLA 无法自动解决、评审分歧无法达成一致）→ 停止并向用户汇报。

> 简言之：**监控的对象是"直到合入"，不是"直到流水线通过"**。流水线通过后仍要盯评审、回评审、等审批，直到 `merged` 才算闭环。

#### 12.4 同步更新 PR 描述（多轮修改后）

PR 创建后经多轮修改（修流水线、采纳评审、新增文件/功能），初版描述会逐渐与实际内容脱节。**每轮修改推送后，判断 PR 描述是否已过时**：
- **应更新**：新增了文件/功能、改变了实现方式、解决了新的评审问题、累积了多块改动。
- **通常无需**：纯 bugfix、格式调整、不改变描述所述范围的小修。

是否更新、更新成什么由你（模型）据改动判断并撰写；写好新描述后用脚本调接口更新（PATCH，只改传入字段）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py update-pr \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> --body-file /tmp/pr_body.md
```

返回 `{updated, pr, fields}`。仅传 `--body/--body-file` 改描述；需改标题再加 `--title`（不传则不动）。描述应继续遵循仓库模板 `.gitcode/PULL_REQUEST_TEMPLATE.zh-CN.md` 的结构。

---

## PR 代码审查

当用户说"检视 PR"、"审查 PR"、"review PR"、"给 PR 提意见"时触发。

### 执行步骤

1. **读取 commands/review.md** - 使用 Read 工具获取完整审查流程

2. **执行 review.md 中的审查流程**：
   - 步骤 1: 前置检查（PR 状态、草稿、是否已审查）
   - 步骤 2: 获取项目规范上下文
   - 步骤 3: 获取 PR 变更摘要
   - 步骤 4: 代码审查（Bug 扫描、规范合规性）
   - 步骤 5: 验证问题
   - 步骤 6: 过滤问题
   - 步骤 7: 输出审查摘要
   - 步骤 8: 准备评论列表（仅当提供 `--comment` 时）
   - 步骤 9: 发布行内评论（仅当提供 `--comment` 时）

**注意**：review.md 中包含每个步骤的详细说明和 API 示例。

---

## 输出格式

### 进度报告（创建 PR 后必须输出）

每次完成 PR 创建流程后，输出如下表格，标注每个步骤的完成状态：

| 步骤 | 操作 | 状态 | 备注 |
|------|------|------|------|
| 1 | 获取访问令牌 | ✅ / ❌ | |
| 2 | 识别目标仓库 | ✅ / ❌ | `parent_owner/parent_repo` |
| 3 | 本地检查（UT / pre-commit） | ✅ / ⚠️ 跳过 | 说明原因 |
| 4 | 准备分支并推送 | ✅ / ❌ | 分支名 |
| 5 | 创建 PR | ✅ / ❌ | PR #N · URL |
| 6 | 触发流水线 | ✅ / ❌ | 触发时间戳 |
| 7 | 监控 | 等待用户选择 | A/B/C |

> 状态说明：✅ 已完成 · ❌ 失败/跳过（说明原因）· ⚠️ 有警告

### 评论列表格式

获取 PR 评论后，使用以下格式输出：

```markdown
# PR 评论摘要

## 总体统计
- 讨论数量: X
- 行内评论: Y
- 已解决评论: Z

## 行内评论详情

### 1. 文件路径 - 第 N 行

**评论内容**: ...
**评论者**: @username
**时间**: YYYY-MM-DD HH:mm
**状态**: 未解决/已解决

**代码片段**:
```cpp
// 被评论的代码行
```

---

## PR 标题格式

遵循 Conventional Commits 规范：

```
<type>: <描述>(#issue_id)
```

**类型**：

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码风格 |
| `refactor` | 重构 |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具 |

**示例**：
- `docs: 优化docs/api/README.md中的ge命名空间描述(#32)`
- `fix: 修复三库json下载安装问题`
- `feat: 添加operator注册V2接口支持(#45)`

---

## PR 描述模板

创建 PR 时使用以下模板格式化描述。

**重要**：
- **变更类型**：根据实际变更内容，将对应选项的 `[ ]` 改为 `[x]` 勾选
- **核对清单**：提交 PR 前所有项都应满足，默认全部勾选 `[x]`
- **从 `## 描述` 开始**：PR body 首个标题即 `## 描述`（PR 页面已有标题栏，无需再加 `# Pull Request` 顶级标题）

```markdown
## 描述
<!-- 根据代码变更内容填写描述 -->

## 变更类型
请选择本次引入的变更类型（勾选对应项）：
- [ ] 🐛 Bug 修复
- [ ] ✨ 新功能
- [ ] 💄 代码风格更新（格式化，局部变量）
- [ ] ♻️ 重构（既不修复错误也不增加功能的代码变动）
- [ ] 📦 构建过程或辅助工具的变动
- [ ] 📝 文档内容更新

## 关联的Issue
<!-- 在 PR 右侧「关联 Issue」面板添加链接；「合并后关闭已关联的 Issue」保持不勾选，issue 由用户在合入后手动关闭。 -->
关联 Issue #<issue_number>

## 如何测试
描述测试此变更的步骤和前提条件：

## 核对清单
- [ ] 我的代码遵循了项目的代码风格
- [ ] 我已对代码进行了自测
- [ ] 我已更新了相关的文档
- [ ] 我在标题中使用了合适的类型标签（如：`feat:`, `fix:`）
- [ ] 我已经详细阅读了贡献指南（CONTRIBUTING.md）

## 其他信息
在此添加任何其他关于本次 PR 的说明。
```

---

## Resources

### references/gitcode_api.md

GitCode API 完整参考文档，用于：
- 了解 API 参数格式
- 查看响应结构
- 排查 API 调用问题
