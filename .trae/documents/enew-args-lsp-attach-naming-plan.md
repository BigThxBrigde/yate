# 描述性命名迁移计划 —— `enew-args-lsp-attach`

Issue: <https://gitee.com/jermaine/yate/issues/IKSFS7>（保留为来源链接；issue 编号**不再**用作名称）。
迁移前 worktree：`../yate-iksfs7` · 迁移前分支：`fix/iksfs7`。

## 0. 分类与流程状态

续作任务（按 `task-orchestration.md` §二.1 不新建 worktree/分支：`git worktree list` 显示既有 worktree，其 `.venv` 被复用）。它属于非平凡任务（≥3 个文件，`plan-before-execute.md` §一.1），因此适用闭环；它是**纯文档/重命名变更**，所以 `misc-rules.md` §三豁免测试门禁（pyright / pytest / coverage / smoke）—— 但不豁免规则加载、命名、相对路径、提交格式和如实汇报的要求。

| 步骤 | 状态 |
|---|---|
| 1 领会 | 完成：重载 8 项规则，探查 `git worktree list` / 分支 / 状态，收集所有 `iksfs7` 令牌 |
| 2 方案 | 完成：本文档 |
| 3 批准 | 已豁免：用户的长期无人值守指令（"进入无人值守模式，所有问题无须过问"）加上本条消息的"取个有意义的名字"委派了命名决策；不发起任何询问/批准（always-applied 工作区加载器 §二.5，无人值守 bypass —— 并非 `.trae/rules/` 条款） |
| 4 执行 | 完成：§3（提交 `9c90c8d`、`06e6743`；检测到 10 处重命名，相似度 86%-96%） |
| 5 审核 | 完成：第 1 轮 **0 blocker / 4 major / 2 minor** → 第 2 轮 **0 blocker / 1 major / 0 minor**（悬置的偏离 #7）→ 第 3 轮 **0 blocker / 0 major / 2 minor**（均为非阻塞的措辞/计数说明）；三轮均为只读一致性评审，适用 `misc-rules.md` §三 纯文档豁免 |
| 6 迭代 | 完成：§6 迭代设计（`4ea44fc`）、M1/M2/M3 修复（`1123856`）、§4 偏离 #7/#8 回填（`9d3721b`） |
| 7 收尾 | 完成：回填 §4 实测结果，记录第 3 轮结论，按步骤提交，`git status --short` 为空，未 push |

子代理：机械式重命名未派发给子代理，因为文件**不可独立验证** —— 每篇文档的链接都依赖其他文档的新名称，因此不满足 `subagent-workflow.md` §一.1 的"disjoint files and independent verification"拆分判据。由主代理原子执行（§三 兜底）。

## 1. 目标 / 非目标

目标：

1. 将分支重命名为 `fix/enew-args-lsp-attach`，将 worktree 目录重命名为 `../yate-enew-args-lsp-attach`，使本地沙箱路径也具有描述性。
2. 将所有 plan / issue-notes / 子计划 / 评审文档重命名为符合 `doc-conventions.md` §一/§二 的描述性名称，统一基于同一任务词干 `enew-args-lsp-attach`。
3. 重写仓库内所有引用（相对链接、分支/worktree 提及、评审索引条目、那一处测试 docstring），使不再有悬空链接。
4. 在 worktree 移动后保持沙箱可自证，并保持 git 历史完整（12 笔提交，无 amend / rebase / force）。

非目标：

- 除 `tests/test_document_flows_saveas.py` 中单个 docstring 令牌外，不改动产品代码、测试、手册、基线或规则。
- 不重写提交信息。现有 12 个主题都是描述性的且都遵循 `type(scope): subject`，但**其中 6 个仍在主题行引用 issue 编号**（`7011ff2`、`68a1ada`、`2c6989b`、`20e6b9c`、`6ec91ec`、`0619086`）。这是一个已知且被接受的偏离（见 §4 的 #9）：此处主题不可变（无 amend / rebase），因此 issue 编号残留在历史中，而每个文件名、文档标题、分支和 worktree 名称都使用描述性词干。
- 不执行 `git push`，不合并。
- 不移除 Gitee issue URL，也不移除在正文中**作为来源引用**使用的 `IKSFS7` issue 编号（见 §2 否决方案 C）。

## 2. 命名决策、备选方案与否决理由

选定词干：`enew-args-lsp-attach` —— 它以小写连字符 ASCII 形式（`doc-conventions.md` §一、§六）命名了该 issue 的两个用户可见修复（`:enew` 参数守卫和 `:saveas` 后无路径 buffer 的 LSP attach）。

| 否决方案 | 理由 |
|---|---|
| A. `unnamed-buffer-lsp` / `enew-arg-guard`（单一症状名称） | 每个只覆盖所交付变更的一半；分支和文档必须描述整个任务。 |
| B. `issue-IKSFS7` / `iksfs7-*` 加描述性副标题 | 用户明确否决以 issue 编号作为名称；副标题并不能修正文件/分支名。 |
| C. 删除每一个 `IKSFS7` 令牌，包括 issue URL 和正文引用 | 会丢失来源信息，并破坏仓库按编号引用 issue 的惯例（`issue IKRZ41`、`issue IKSFMQ`…）。只重命名**名称和标题**；URL 和正文引用保留。评审索引的段落标题算作**名称/标题**，因此使用任务名；issue 编号仅保留在 issue 笔记和主计划顶部的 Gitee URL 中。 |
| D. 保留 `../yate-iksfs7` 作为沙箱目录 | 会留下无意义的本地名称，并使文档中的 worktree 路径与分支名不一致；`git worktree move` 是原生的可逆操作。 |
| E. `git push` 重命名后的分支 | 闭环禁止 push（§二 提交纪律）；用户也未要求。 |

### 精确重命名映射

| 旧 | 新 |
|---|---|
| `fix/iksfs7` | `fix/enew-args-lsp-attach` |
| `../yate-iksfs7` | `../yate-enew-args-lsp-attach` |
| `iksfs7-issue-notes.md` | `enew-args-lsp-attach-issue-notes.md` |
| `iksfs7-plan.md` | `enew-args-lsp-attach-plan.md` |
| `iksfs7-plans/` | `enew-args-lsp-attach-plans/` |
| `iksfs7-enew-args-plan-a.md` | `enew-args-lsp-attach-guard-plan-a.md` |
| `iksfs7-lsp-state-plan-b.md` | `enew-args-lsp-attach-state-plan-b.md` |
| `iksfs7-saveas-attach-plan-c.md` | `enew-args-lsp-attach-saveas-plan-c.md` |
| `iksfs7-docs-smoke-plan-d.md` | `enew-args-lsp-attach-docs-plan-d.md` |
| `iksfs7-review-fixes-plan-e.md` | `enew-args-lsp-attach-review-plan-e.md` |
| `2026-11-06-iksfs7-review-round1.md` | `2026-11-06-enew-args-lsp-attach-review.md` |
| `2026-11-06-iksfs7-review-round2.md` | `2026-11-06-enew-args-lsp-attach-iteration-review.md` |

评审记录名称遵循 `doc-conventions.md` §二.1（`YYYY-MM-DD-<topic>.md`，同一天的评审以主题区分，而非 `-2`/`-v2` 后缀）。子计划名称保持 `<task>-<subtask>-plan-<letter>.md`；目录保持为 `<task>-plans/`，含 `overview.md`。

文档标题改为描述性：`Unnamed-buffer LSP attach fix plan — …`、`Issue source notes — …`、`… sub-plan overview — …`、`plan-a — …` 等，评审记录 / 评审索引段落使用描述性任务短语。机器本地的记忆文件 `project_iksfs7_status.md` 重命名为 `project_enew_args_lsp_attach_status.md`，其 `MEMORY.md` 索引行也更新（机器本地数据，不是仓库提交）。

趁修改该行之际，顺带消除一处环境信息泄露：主计划中的沙箱自证目前内嵌了 `D:\Programming\yate-iksfs7\...`；`doc-conventions.md` §五 要求可移植的措辞，因此该**单行证据**改为 "the worktree-local `yate` package"。这一承诺刻意限定在该行：本计划仍必须写出新旧 worktree 目录（重命名映射、实测输出证据和可执行的 §6 命令），因为它们是迁移自身的目标产物，而非对仓库文件的引用。关于该区分的长期裁决见 [pr-review 迭代设计](enew-args-lsp-attach-pr-review-plan.md)。

## 3. 实施步骤

### Step 1 —— 计划（本文档）

输入：规则集 + 令牌清单。输出：本文件。验收：`git status --short` 只显示这个新的未跟踪文件；提交 `docs(plan): add naming migration plan for unnamed-buffer LSP attach`。

### Step 2 —— 分支与 worktree

输入：干净的 worktree。命令（主仓库 / worktree）：

```powershell
# From the main repository root:
git worktree move ../yate-iksfs7 ../yate-enew-args-lsp-attach
# From the moved worktree root:
git branch -m fix/enew-args-lsp-attach
.venv\Scripts\python.exe -m pip install -e . --no-deps
.venv\Scripts\python.exe -c "import yate; print(yate.__file__)"
```

输出：分支 `fix/enew-args-lsp-attach`，worktree `D:/Programming/yate-enew-args-lsp-attach`，沙箱导入指向新路径。验收：`git branch --show-current`、`git worktree list` 和自证输出三者一致。`pip install -e . --no-deps` 刷新仍指向旧目录的可编辑 `.pth`；不下载依赖。

### Step 3 —— 文档与引用（一次原子提交）

输入：§2 的重命名映射。文件：10 次 `git mv` 操作，`.trae/documents/` 和 `.trae/reviews/` 下的所有 `.md`、`.trae/reviews/README.md`，以及 `tests/test_document_flows_saveas.py`（仅 docstring 令牌）。实施：`git mv` + 对受影响的 Markdown 文件做一次性 Python 替换（先用占位符保护 URL，最后恢复），然后针对标题、索引段落、沙箱自证行和测试 docstring 做定点 `replace_in_file` 编辑。

验收命令（从新 worktree 根目录执行）：

```powershell
git branch --show-current
git worktree list
git status --short
git diff --check
# Lowercase token scan (case-sensitive; exclude this plan's rename map):
Get-ChildItem .trae,tests -Recurse -Include *.md,*.py | Where-Object { $_.Name -ne 'enew-args-lsp-attach-naming-plan.md' } | ForEach-Object { Select-String -Path $_.FullName -Pattern 'iksfs7' -CaseSensitive }
# Scoped link check (11 target docs + README; strip '#Lxx' and scheme URLs):
Get-ChildItem .trae -Recurse -Filter *.md | Where-Object { $_.Name -like 'enew-args-lsp-attach*' -or $_.DirectoryName -like '*enew-args-lsp-attach-plans*' -or $_.Name -eq 'README.md' } | ForEach-Object { $f = $_; Select-String -Path $f.FullName -Pattern '\]\(([^)]+)\)' -AllMatches | ForEach-Object { $_.Matches.Groups[1].Value } | Where-Object { $_ -notmatch '^[a-z]+://' -and $_ -notmatch '^#' } | ForEach-Object { $clean = ($_ -split '#')[0]; if ($clean -and -not (Test-Path (Join-Path $f.DirectoryName $clean))) { "MISSING: $($f.Name) -> $_" } } }
.venv\Scripts\python.exe -c "import yate; print(yate.__file__)"
```

通过标准：分支/worktree 名称与 §2 一致；小写 `iksfs7` 计数为 0（**排除本计划的重命名映射**，该映射保留旧名称作为迁移证据，见 §2）；范围内的检查中没有 `MISSING:` 链接 —— 全量扫描 `.trae` 不是有效检查，因为历史文档含 `file:///` URL 和 `#Lxx` 行片段；`git diff --check` 退出码 0；沙箱自证打印新 worktree 路径。实测结果和精确的范围命令记录在 §4。提交：`docs(plan): rename issue-numbered artifacts to descriptive task name`。

### Step 4 —— 评审、回填、收尾

输入：step-3 的 diff。只读一致性评审（命名规范、相对链接、评审索引 #59/#60 条目、git 重命名检测、无代码改动）。纯文档豁免（`misc-rules.md` §三）意味着不运行 pytest/pyright/coverage/smoke；上述沙箱自证和链接/令牌检查即为门禁。用实测结果回填 §4，提交 `docs(plan): backfill naming migration results`，最终 `git status --short` 为空，不 push。

## 4. 执行记录（填入真实数字）

| 命令 | 结果 | 退出码 |
|---|---|---|
| `git worktree move` | `fatal: failed to move ...: Permission denied`（Windows）；由 `Move-Item` + `repair` 取代，见偏离 #1/#3 | 1（按设计失败） |
| `git branch -m` | `git branch --show-current` = `fix/enew-args-lsp-attach`；`git worktree list` 显示该分支上的新路径；未配置 upstream | 0 |
| `pip install -e . --no-deps` + 沙箱自证 | `.pth` = `D:\Programming\yate-enew-args-lsp-attach`；`sys.prefix` = 该 `.venv`；`import yate` = `...\yate-enew-args-lsp-attach\yate\__init__.py`；`pip show yate` 的可编辑位置一致 | 0 |
| 替换后小写 `iksfs7` 令牌计数 | 在 `.trae` + `tests` 中（排除本计划的重命名映射）为 **0**（`Get-ChildItem ... -CaseSensitive`）；`git grep -n 'iksfs7'` 排除本计划 = 无匹配；大写 `IKSFS7` = 恰好 2 个 Gitee URL | 0（grep：1 = 无匹配） |
| 相对链接检查 | 用 §3 step 3 的范围命令为 **0 个 `MISSING`**（该口径下 141 条链接）；第 1 轮的 11 文档口径也是 0/40 | 0 |
| `git diff --check` | 空（无空白错误 / 冲突标记） | 0 |
| 收尾时的 `git status --short` | 每次按步骤提交后均为空；在 step-7 最终门禁中重跑 | 0 |
| `git diff 0619086..HEAD -M --summary` | **10 处重命名**，相似度 86%-96% + 1 个 `create mode`（本计划）；代码 diff = `tests/test_document_flows_saveas.py` 中 1 行 docstring | 0 |
| worktree 元数据 / venv 探查 | `.git` 的 `gitdir:` 和 admin key 均使用新名称；`git worktree list` / `rev-parse --git-dir` / `prune --dry-run -v` = 0，无陈旧或 `locked` 条目；测量时对 `.venv` 中 8244 个文本文件的递归扫描 = **0** 个 `yate-iksfs7`（后来因探查产生的 `.pyc` 文件重新扫描计为 8248 个，仍为 0 命中）；`activate.bat` 的 `VIRTUAL_ENV` 路径存在 | 0 |

偏离（按 §5 记录；均有实测证据）：

1. **原生 `git worktree move` 失败**：`git worktree move ../yate-iksfs7
   ../yate-enew-args-lsp-attach` 在 Windows 上打印 `fatal: failed to move ...: Permission denied`。设计的 step-2 命令未完成。
2. **三条后续命令在主仓库中执行**：因为 `cd` 进入尚未创建的 worktree 失败，`git branch -m fix/enew-args-lsp-attach` 把**主仓库的 `master`** 重命名为该名称，且 `pip install -e . --no-deps` 重新安装了主仓库的可编辑包。恢复证据：`git branch -m master` 恢复了主仓库（`git branch --show-current` = `master`，`git reflog show master` 显示一对匹配的 rename-out/rename-back，`git status --short` 为空，`git worktree list` 显示 `D:/Programming/yate [master]`）；主仓库的 `import yate` 解析到 `D:\Programming\yate\yate\__init__.py`，其可编辑 `.pth` 指向 `D:\Programming\yate`，因此没有残留损害。
3. **worktree 移动方法改变**：`Move-Item -Path yate-iksfs7
   -Destination yate-enew-args-lsp-attach` + 从移动后的 worktree 执行 `git worktree repair`。`repair` 打印 `repair: gitdir incorrect: ...` 并重写了 `gitdir` 指针；随后 `git worktree list` 显示
   `D:/Programming/yate-enew-args-lsp-attach [fix/iksfs7]`（那一刻分支仍是旧的）。然后 **从 worktree 内部**重新运行 `git branch -m`，得到 `[fix/enew-args-lsp-attach]`；未配置 upstream。
4. **可编辑安装刷新了两次**：一次意外在主仓库中执行（见 #2），然后在移动后的 worktree 中用 `pip install -e . --no-deps` 正确执行；自证 `import yate` 解析到 `D:\Programming\yate-enew-args-lsp-attach\yate\__init__.py`（exit 0）。
5. **可移植措辞的承诺在 `06e6743` 中只部分兑现**：step-2 设计承诺 "the worktree-local `yate` package"，但第一遍替换成了 `../../yate/__init__.py`，这是一个仍假设 worktree 位于主仓库旁边的相对路径。在 §6 迭代波次中修复。
6. **全量扫描检查不可用**：§3 step 3 中原有的令牌/链接命令会产生误报（本计划的重命名映射；历史 `file:///` 和 `#Lxx` 链接）。改用现在写入 §3 step 3 的、经过实测的范围命令（见 §4 表格和第 1 轮评审第 11 项）。
7. **迭代波次仅涉及环境且最初未记录**：M1 将主仓库的 git admin key `.git/worktrees/yate-iksfs7` 重命名为 `yate-enew-args-lsp-attach`（前后以 `git worktree lock` / `unlock` 包围），M2 在检查的五个候选文件中对携带该令牌的四个 venv 文本文件（`activate`、`activate.bat`、`activate.fish`、`pyvenv.cfg`）做了就地重写（`Activate.ps1` 无命中）。两者都不产生被跟踪的 diff 或提交 —— `.venv` 被 gitignore，`.git` 元数据是机器本地的 —— 因此 `git status --short` 保持为空。`git worktree repair` **首次返回 exit 1**，报 `error: unable to
   locate repository; .git file does not reference a repository`，同时仍重写了 worktree 的 `.git` 指针；第二次 `repair` 返回 exit 0。已验证：`.git` = `gitdir: .../worktrees/yate-enew-args-lsp-attach`，旧 admin key 不存在，`git status` / `worktree list` / `rev-parse --git-dir` / `prune --dry-run -v` 均 exit 0，无陈旧或 `locked` 残留，`.venv` 递归残留为 0，沙箱自证仍解析到该 worktree。第 2 轮把缺失的 #7 标记为其唯一 major；本条目将其闭合。
8. **自证测量范围**：从主仓库 cwd 运行 `.venv\Scripts\python.exe -c
   "import yate; ..."` 会打印主仓库的 `yate\__init__.py`，因为 `sys.path[0]` 遮蔽了可编辑安装；从 worktree 根目录运行则打印 worktree 的包。这是测量范围问题，而非沙箱缺陷，因此 §3 step 3 的自证命令必须从 worktree 根目录运行。
9. **issue 编号残留在 6 个提交主题中**：命名迁移重命名了分支、worktree、10 篇文档、评审索引标题和一处测试 docstring，但未重写历史。`git log --format=%s 8e60598..9c90c8d` 显示 12 个主题中有 6 个仍引用 `IKSFS7`（`7011ff2`、`68a1ada`、`2c6989b`、`20e6b9c`、`6ec91ec`、`0619086`）。§1 原先断言相反（"contain no issue-number name"）；2026-11-07 的合并前 PR 评审确认了这一不符，现已在 §1 用实测哈希更正。理由：在禁止重写历史的约束下主题不可变，因此 issue 编号仅残留在提交历史中，而每个名称/标题/文件都使用描述性词干。

第 1 轮评审（0 blocker / 4 major / 2 minor）发现两处环境/元数据残留和一处措辞偏离；均在 §6 迭代波次中修复并记录在 #5、#7 和 #8。第 2 轮评审（0 blocker / 1 major / 0 minor）发现悬置的 "deviation #7" 承诺；回填增加了 #7/#8。第 3 轮评审（0 blocker / 0 major / 2 minor）确认闭合；其两个 minor 是措辞/计数澄清，已并入收尾提交（#7 现在写明 "4 of 5 candidates"，且 `.venv` 扫描计数带有测量时间限定）。任何一轮都未运行 Pyright / pytest / architecture / coverage / smoke（`misc-rules.md` §三 纯文档豁免）。稍后对合并后分支（含产品代码）的[合并前 PR 评审](../reviews/2026-11-07-pr-review-fix-enew-args-lsp-attach.md)解除了该豁免并运行了完整的六道门禁。

## 5. 风险与回滚

| 风险 | 缓解措施 | 回滚 |
|---|---|---|
| `git worktree move` 因 Windows 文件锁而失败 | 从干净的主仓库运行；无进程占用该 worktree | 保留旧目录，回退文档中两处 worktree 路径行，记录偏离 |
| 可编辑安装的 `.pth` 仍指向旧路径 | `pip install -e . --no-deps` + 自证 | 重新运行安装；若失败，`git worktree move` 回去并保留旧路径行 |
| 分支重命名破坏 worktree HEAD 或已配置的 upstream | 从 worktree 内部重命名（`git branch -m`），分支无 upstream（从未 push），用 `git branch --show-current` 验证 | 从 worktree 执行 `git branch -m fix/iksfs7` |
| 遗漏某条链接或索引条目 | §3 step 3 中的链接检查和令牌计数命令 | 回退 step-3 提交（git 保留重命名检测），重新应用遗漏的替换 |
| 过度替换 issue URL / 来源引用 | 替换脚本中的 URL 占位符保护；只重写小写名称和标题 | 回退并用更正后的映射重跑 |
| 记忆索引漂移（机器本地） | 在同一步中重命名记忆文件及其 `MEMORY.md` 行 | 恢复旧文件名/索引行 |

通用回滚：对两笔文档提交执行 `git revert`，然后 `git branch -m fix/iksfs7` 并 `git worktree move` 回去。不重写历史。

## 6. 迭代设计（第 1 轮评审 → 第 2 轮）

触发：step-5 只读一致性评审返回 **0 blocker / 4 major / 2 minor**（M1-M4、m5-m6）。按 `task-orchestration.md` §二.6 循环回到 step 2；本节即该 step-2 重新设计。批准由长期无人值守指令覆盖，因此不发起任何询问或授权请求（always-applied 工作区加载器 §二.5，无人值守 bypass —— 并非 `.trae/rules/` 条款）。不涉及新 worktree/分支、产品代码、历史重写或 push。

| ID | 发现项 | 根因 | 修复设计 | 验收 |
|---|---|---|---|---|
| M1 | git admin key `.git/worktrees/yate-iksfs7` 和 worktree 的 `.git` 中 `gitdir:` 值仍带旧名称 | 原生 `git worktree move` 在 Windows 上失败；`Move-Item` + `git worktree repair` 修复了 `gitdir` 的*内容*，但未修复注册键名 | 从主仓库执行：`git worktree lock`，将 admin 目录重命名为 `yate-enew-args-lsp-attach`，`git worktree repair <worktree>`，`git worktree unlock`；仅当 `repair` 未改写 worktree 的 `.git` 指针时才手动改写 | `Get-ChildItem .git/worktrees` 或 worktree 的 `.git` 文件中无 `iksfs7`；`git status --short`、`git worktree list`、`git rev-parse --git-dir`、`git worktree prune --dry-run -v` 均 exit 0 且无陈旧条目 |
| M2 | `.venv/Scripts/activate*`、`.venv/pyvenv.cfg` 仍含 `yate-iksfs7` | step-2 设计只刷新了可编辑的 `.pth`（`pip install -e . --no-deps`） | 在命中的激活脚本及 `pyvenv.cfg` 中对 `yate-iksfs7` → `yate-enew-args-lsp-attach` 做就地文本替换；不重装、不下载依赖、不提交（被 gitignore 的机器本地数据） | `.venv` 递归残留扫描 = 0；`activate.bat` 中的 `VIRTUAL_ENV` 路径存在；沙箱自证仍解析到新 worktree |
| M3 | `.trae/documents/enew-args-lsp-attach-plan.md:11` 的自证写的是 `../../yate/__init__.py` | 第一遍替换成了相对路径，而非 §2 承诺的可移植措辞 | 逐字使用 §2 的措辞："the worktree-local `yate` package" | `git grep -n '../../yate/__init__.py'` 无匹配；该行不再假设同级目录布局 |
| M4 | §4 的 `Deviations: none recorded yet.` 与已知偏离矛盾 | 第 1 轮评审时 step-7 回填尚未开始 | 在 §4 改写为 8 项有证据支撑的偏离列表（第 2 轮后增加 #7/#8）；§4 结果表在 step 7 用实测值填充 | 收尾时不再有 `pending` 行，也不再有 "none recorded" 断言 |
| m5 | §3 step 3 的令牌/链接命令按原文无法执行 | 全量扫描口径会产生误报（本计划自身的重命名映射、历史 `file:///` / `#Lxx` 链接） | §3 step 3 现改为区分大小写的、排除本计划的小写扫描，以及范围链接检查；§4 记录实测命令 | 两条命令均 exit 0，命中数 0 / `MISSING:` 0 |
| m6 | 评审索引标题的裁决边界隐含未明 | §2 否决方案 C 原先只覆盖 URL/正文 | §2 C 现在声明评审索引段落标题属于名称/标题，issue 编号仅存在于两个 Gitee URL 中 | 第 2 轮评审确认没有仓库文件把 issue 编号用作名称/标题 |

### 迭代波次命令（step 6）

```powershell
# M1 — main repo metadata (environment-only, not committed)
$main = 'D:/Programming/yate'
$wt = 'D:/Programming/yate-enew-args-lsp-attach'
git -C $main worktree lock $wt
Rename-Item -LiteralPath "$main/.git/worktrees/yate-iksfs7" -NewName 'yate-enew-args-lsp-attach'
git -C $main worktree repair $wt
git -C $main worktree unlock $wt
Get-Content "$wt/.git"
git -C $wt status --short
git -C $wt rev-parse --git-dir
git -C $wt worktree list
git -C $main worktree prune --dry-run -v

# M2 — venv text files (environment-only, not committed)
$root = 'D:/Programming/yate-enew-args-lsp-attach'
$files = @("$root/.venv/Scripts/activate", "$root/.venv/Scripts/activate.bat",
           "$root/.venv/Scripts/activate.fish", "$root/.venv/Scripts/Activate.ps1",
           "$root/.venv/pyvenv.cfg")
foreach ($f in $files) {
    if (Test-Path -LiteralPath $f) {
        $t = [System.IO.File]::ReadAllText($f)
        if ($t.Contains('yate-iksfs7')) {
            [System.IO.File]::WriteAllText($f, $t.Replace('yate-iksfs7', 'yate-enew-args-lsp-attach'))
        }
    }
}

# M3 — tracked document (committed as the step-6 product)
# replace ../../yate/__init__.py with the §2 portable wording in the main plan §0
```

### 决策与范围

- M1/M2 是**仅环境**修复。它们不产生被跟踪的 diff 或提交；在 §4 中以实测证据记录为偏离 #7/#8。`git` 元数据写入正是第 1 轮要求的操作；长期无人值守指令提供了第 1 轮本想请求的批准。
- 本次命名迁移的评审结论**内联记录在本计划中**（§0 流程状态、§4 执行记录、§6），而非新增 `.trae/reviews/` 记录：记录 #59/#60 已经是本任务的评审记录，且本波次只改名称。`doc-conventions.md` §二.1 仅在*创建*记录时约束命名；它并不强制创建记录，因此评审索引无需新条目。
- 门禁：纯文档/元数据变更，因此 `misc-rules.md` §三豁免 pyright / pytest / architecture / coverage / smoke。§3 step 3 中的可执行检查加上 M1/M2 探查即为门禁；第 2 轮是只读一致性评审，其结论带有实测结果和退出码。第 2 轮派发给 `code-review-expert`（`.trae/agents/code-review-expert.md`），任务书中声明纯文档豁免；spawn 失败则按 §三 主代理兜底处理并汇报为"子代理零产出"。
- step-7 产物：§4 结果表用真实数字回填，§0 状态表闭合，按步骤提交，`git status --short` 为空，不 push。

### 风险与回滚

| 风险 | 缓解措施 | 回滚 |
|---|---|---|
| 重命名 git admin 目录使 worktree 不可用 | 先 lock；保留旧名称可用；在任何其他 git 写操作前 repair；unlock 前验证四条 git 命令 | 将 admin 目录重命名回 `yate-iksfs7`，恢复 `.git` 的 `gitdir:` 行，运行 `git worktree repair`，解锁 |
| `git worktree repair` 改写了错误的指针 | repair 后回读 `.git` 文件和 `gitdir` 内容；之后再继续 | 迭代前恢复 §4 中记录的原始 `.git` 行（逐字） |
| 就地替换 venv 破坏编码 / 行尾 | 用 `[System.IO.File]` 做原始文本读写，只替换单个 ASCII 令牌；之后验证残留计数和 `import yate` | 把新令牌替换回去；这些文件可用 `python -m venv` + `pip install -e ".[dev]"` 重新生成 |
| 第 2 轮评审返回新的 major | 留在循环中（§二.6），扩展本节 | 无需回滚；设计是增量式的 |
