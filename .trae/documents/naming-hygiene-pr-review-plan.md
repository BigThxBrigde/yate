# 命名规范清理合并前 PR 评审修复计划

来源评审记录：[2026-11-07-pr-review-naming-hygiene.md](../reviews/2026-11-07-pr-review-naming-hygiene.md)
（合并前 PR 级预评审，`review` 模式，3 只读审查员并行 + 主代理逐条回读复核）。
来源方案：[iktbxc-plan.md](iktbxc-plan.md)、
[iktbxc-review-fixes-plan.md](iktbxc-review-fixes-plan.md)、
[iktbxc-plans/overview.md](iktbxc-plans/overview.md)。
无人值守会话：批准视为已通过，不询问；本计划是迭代波的唯一规范来源。

## 1. 范围与基线（只读证据）

| 项目 | 实测值 |
|---|---|
| merge-base / PR HEAD / master | `3e92532` / `38a918b` / `d53d238` |
| master 领先量 | 47 commits ahead of merge-base |
| PR diff | 48 files changed, 1641 insertions(+), 65 deletions(-) |
| worktree / 分支 | `yate-naming-hygiene` / `ref/naming-hygiene` |
| 沙箱 | `.venv/Scripts/python.exe` resolves `yate/__init__.py` inside this worktree |
| 与 master 修改文件的重叠 | `.trae/reviews/README.md`, `.trae/rules/architecture-boundaries.md` |
| `git merge-tree 3e92532 master HEAD` | 恰好 1 对冲突标记，均位于 `.trae/reviews/README.md` 的正文中；层级规则文件自动合并 |
| `git diff --check 3e92532..HEAD` | 退出码 2：`iktbxc-plan.md:300: new blank line at EOF` |
| 未跟踪的探针产物 | `base_cf.txt`, `base_disp.txt`, `base_ed.txt`, `base_mouse.txt`, `base_term.txt`, `base_to.txt`（6 个文件，来自 PR 评审侦察） |

三个实现 blob 与更改前的来源保持逐字节等价（审查员 A/C 独立确认）；重命名波次中没有运行时行为变化。

## 2. 主代理裁决（最终严重级别）

| # | 发现项 | 来源 | 裁决 | 最终结果 | 处置 |
|---|---|---|---|---|---|
| F1 | `.trae/reviews/README.md` 索引 #59 与 master 的 #59/#60/#61 冲突，且正文插入是真正的三方合并冲突 | B 阻塞项；C 严重；A 次要 | 冲突经 `git merge-tree` 确认。从阻塞项降级：Markdown 索引冲突既不是安全问题、架构违规、红色硬门禁，也不是崩溃，因此该 skill 的阻塞项定义不适用。它是阻碍合并的文档损坏，故为严重。 | 严重 | 将分支条目重新编号为 #62（首次评审）和 #63（PR 评审）；添加编号分歧说明；重新安置分支正文使冲突消失；重新运行 `git merge-tree` |
| F2 | 新增文档中的盘符绝对路径（`iktbxc-plan.md:8`、`:275`；评审记录 `:122`） | B/C 严重 | 确认：PR 新增行中有 3 处。`doc-conventions.md` §五/§六 禁止此类路径；"旧文档逐步迁移"条款不能为新的违规开脱。 | 严重 | 替换为相对于 worktree 的 / 可移植的表述 |
| F3 | 评审记录的范围与结论失真（`44 files/+1139/-65` 被标注为 `3e92532..HEAD`、worktree 元数据、导入顺序主张） | B 严重 | `44/+1139/-65` 恰好是 `3e92532..f3299a1`（评审时的 HEAD），而当前 HEAD 为 `48/+1641/-65`；错的是标注，不是数字。§三 的导入顺序行在事实上被 F6 的机械复核推翻。 | 严重 | 将范围固定为 `f3299a1`，注明当前 HEAD，添加带日期的更正附录，对环境行做脱敏处理 |
| F4 | `yate/editor.py:61` 导入顺序回退 | A 次要 | 确认并扩展：重命名后有 5 个文件的 `view` 导入仍留在旧的 `editor` 位置。机械证据：`yate/editor.py`、`yate/editor_dispatch.py`、`yate/flows/completion_flows.py`、`tests/test_app_mouse.py`、`tests/test_panes.py`。 | 次要 | 修复全部 5 处（行为中立；经门禁验证） |
| F5 | `tools/smoke_test/scenarios/stress.py` 收敛判定：丢弃 `wait_until` 返回值、魔法数字 `3`、用单键字典代替 `nonlocal` | C 次要 ×3 | 三项均确认。 | 次要 | 修复魔法数字和字典；将丢弃返回值的问题延后处理（§5） |
| F6 | 6 个未跟踪的 PR 评审探针文件 | 主代理 | 通过 `git status --short` 确认。与迭代 1 的 M1 属于同一类交付卫生问题。 | 次要 | 本计划落盘后删除；在收尾报告中列出 |
| F7 | `git diff --check` 在 EOF 处发现空行 | 主代理 | 确认。 | 次要 | 删除 `iktbxc-plan.md` 末尾的空行 |
| F8 | master `task-orchestration.md` 现在要求从 `develop` 创建 `feature/<fix|feat|enh|ref>-<task>`；而分支是从 `master@3e92532` 创建的 `ref/naming-hygiene` | A/B 次要 | 确认存在偏离。该分支早于 master 的规则变更，且由用户在 2026-11-07 明确命名；再次重命名将违背该指示。 | 次要（延后） | 在 §5 登记，不改代码 |
| F9 | `iktbxc-*` 文档词干与语义命名方向冲突 | B 次要 | 确认。用户反馈约束的是分支/worktree 名称，而非文档名称；计划文档遵循 `<task>-plan.md`，以 issue id 作为 `task`，现在重命名将破坏 9 条交叉链接。 | 次要（延后） | 在 §5 登记 |

基线裁决：A `APPROVE`（0/0/1）、B `BLOCKED`（1/2/4）、C `REQUEST_CHANGES`（0/1/3）。
F1-F3 归零后，最终 PR 评审裁决为 **APPROVE**。

## 3. 目标 / 非目标

目标：将 3 个最终严重发现项归零；修复或登记每个次要项；在 PR 评审阶段重跑六道硬门禁；归档 PR 评审记录并登记索引；回填计划；保持 `git merge-tree` 无冲突标记。

非目标：不推送；不将 master 合并进分支；不重写三个实现提交或首次评审的发现项；不新增架构守卫；不新增冒烟 `Check`（冻结的 `1463/1463` 基线保持不变）。

## 4. 步骤与验收命令

1. 将本计划作为独立提交落盘（`docs(plan): ...`）。
2. F1 + F2 + F3 + F7 + F9：编辑 `.trae/reviews/README.md`、
   `.trae/reviews/2026-11-07-iktbxc-naming-refactor.md`、
   `.trae/documents/iktbxc-plan.md`、
   `.trae/documents/iktbxc-review-fixes-plan.md`；删除 6 个探针文件（F6）。
   验收：`git merge-tree 3e92532 master HEAD` 报告 0 个 `<<<<<<<`；
   对 PR 改动文件中的盘符路径进行定向 grep 返回 0 处命中；
   `git diff --check 3e92532..HEAD` 退出码 0；`git status --short` 无 `??`。
3. F4：重排 5 对导入；F5：`_SETTLED_POLLS` 常量 + `nonlocal` 计数。验收：`pyright yate/ tests/ tools/ pack/` 0 错误；
   `pytest tests/test_architecture.py -q` 37 passed；
   `tools.smoke_test run --scenario stress_rapid_toggles --repeat 5 --jobs 4` 12/12。
4. 归档 PR 评审记录并登记为 #63；提交。
5. 主代理亲自运行六道硬门禁（均退出码 0）：
   `pyright yate/ tests/ tools/ pack/`、`pytest tests/ -q -n auto`、
   `pytest tests/test_architecture.py -q`、
   `pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75`、
   `tools.smoke_test run --jobs 4`、`python -m tools.changelog check`；
   外加 `python -m yate --help`、`git diff --check`、残留旧路径 grep 和
   `git status --short`。
6. 回填下面的 §7、`iktbxc-plan.md` §9.8 及评审记录；提交。
   任何步骤均不得推送（§二 提交纪律）。

## 5. 延后项与偏离登记

| 项目 | 原因 |
|---|---|
| F5 丢弃 `wait_until` 返回值 | `wait_until` 仅在超时时返回 `False`，且现有的 `Check("toggles_back", before, ...)` 已断言同一收敛失败。再添加一个 `Check` 会抬高冻结的 `1463/1463` 冒烟基线，并对仅与时序相关的辅助方法造成重复覆盖。 |
| F8 分支命名偏离 | 分支在 master 引入从 `develop` 创建 `feature/...` 的规则之前从 `master@3e92532` 创建；语义名称 `ref/naming-hygiene` 由用户在 2026-11-07 明确选定。重新登记分支还将改写文档中记载的 worktree。 |
| F9 `iktbxc-*` 文档词干 | Issue id 是仓库中计划文档的 `<task>` 标记；重命名将破坏 9 条仓库内链接，并违背"只读历史文档"惯例。 |
| `key_codec.py` 首行"遗留"措辞、R11 枚举偏离、包级 `--follow` 溯源 | 首次评审中已有的观察；超出 PR 评审范围。 |
| master 侧 `.trae/rules/architecture-boundaries.md` 与 `task-orchestration.md` 的改动 | 可自动合并 / 单侧；未被本分支修改。 |

## 6. 风险与回滚

| 风险 | 缓解措施 |
|---|---|
| 导入重排改变模块初始化顺序 | `terminal.py` / `panes.py` 本身已导入 `view.py`，因此不会形成新循环；编辑后重跑 pyright + 全量 pytest + 冒烟 |
| README 正文迁移丢失增量日志 | 两次评审仍保留在编号表格中，并新增分歧说明；重新核查 `git merge-tree` |
| 删除探针文件会丢失证据 | 它们是临时的 docstring 转储；所有证据均已在 PR 评审记录中复现 |
| 重新编号留下陈旧的 `#59` 引用 | 对 `.trae/**` 进行定向 grep 并修正 4 处已知位置 |

回滚：每个迭代提交均可单独 `git revert`；三个实现提交与首次评审记录保持不变。

## 7. 回填（2026-11-07，已关闭）

**最终裁决：APPROVE。** F1-F3（3 个严重项）已归零；F4-F7（6 个次要项）已修复；F5 的丢弃返回值问题、F8 和 F9 已登记为延后（§5）。通过对 PR 改动的 Markdown 进行机械链接检查，发现 `iktbxc-plans/overview.md` 中一条相对链接损坏，已修复。

主代理门禁（均退出码 0）：pyright `0 errors, 0 warnings`；`pytest tests/ -q -n auto` 0；架构 `37 dots` 0；覆盖率 `TOTAL 19392/1092/6190/579 = 93%`、`Total coverage: 92.88%`、`3395 passed, 10 skipped` 0；冒烟 `1463/1463 checks`、`121/121 scenarios`、95.16s 0；`python -m tools.changelog check` 0。补充：`python -m yate --help` 0；`git diff --check` 0；三处旧路径 grep 0 处命中（退出码 1）；盘符扫描 0 处命中；旧分支/worktree 名称 grep 0 处命中（退出码 1）；`git merge-tree 3e92532 master HEAD` 0 个冲突标记；`git status --short` 为空；PR 改动的 Markdown 链接检查 0 处损坏。

迭代提交：`c0f3672`（本计划）、`12e2570`（索引/范围/路径修复）、`b2ab44d`（导入顺序）、`81f8486`（stress 判定）、`f783bb0`（PR 评审记录 + 索引 #63），以及收尾回填提交。门禁时 `81f8486` 处的 PR 范围为 49 个文件 / +1784 / -66；评审记录与回填提交在其上增加了评审/计划文本。未推送。
