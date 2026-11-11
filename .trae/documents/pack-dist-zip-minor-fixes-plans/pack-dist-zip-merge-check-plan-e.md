# 子计划 e：合并模拟验证 F14/F15（wave-3，主代理执行）

> 路径基准同总纲。唯一规范来源：本文件 +
> `../pack-dist-zip-minor-fixes-plan.md` §2/§3 +
> `../pack-dist-zip-minor-fixes-issue.md` F14/F15 +
> `pack-dist-zip-pr-review-feature-feat-pack-dist-zip` 评审记录 §五。
> 本波**不写当前分支源码**；合并模拟在隔离的临时 worktree 内进行。

## 1. 输入与目标

- 现状：`master` 已推进 `18e96d2a`（IKTPC2 合入，架构守卫 37→38）；本分支
  merge-base `b982c06`。分支侧七项门禁全绿（架构 37）；评审把「合并到
  master 后架构 38 重跑门禁」与「`tools.changelog check` 合并时人工确认」
  登记为合并时流程项 F14/F15。
- 目标：在隔离、可逆、不推送的合并树上**实测**这两项，把「合并时待办」
  转成「已实测」结论并回填；主工作树 `git status --short` 保持为空。
- 前置：wave-1 / wave-2 全部验收命令退出码 0；提交态 `git merge-tree`
  精确冲突块数为 0（前轮已实测）。

## 2. 步骤（顺序，逐条记录退出码）

1. **落盘记录**（git 安全协议）：先在 `../pack-dist-zip-progress.md`
   「全量 minor 修复轮」章节追加一条「即将创建临时 worktree 做合并模拟，
   完成后 `git worktree remove` 删除合并提交与目录」，声明不推送、不合流。
2. 创建隔离 worktree（detached HEAD）：
   `git worktree add ../yate-pack-dist-zip-merge-check HEAD`
   目录名语义化、位于仓库同级；`git worktree list` 复核登记。
3. 在临时 worktree 内 `git merge --no-edit master`：
   - 预期 0 冲突（提交态 `merge-tree` 已验证）；
   - 若出现冲突，立即 `git merge --abort`，记录实测错误与退出码，按
     `pack-dist-zip-minor-fixes-plan.md` §7 登记偏离，不得静默调整。
4. 用**主 worktree 的 venv 解释器**（绝对路径仅在命令中使用，不写入文档）
   在临时 worktree 的 cwd 下跑：
   ```
   <main-venv-python> -m pytest tests/test_architecture.py -q
   <main-venv-python> -m pytest tests/ -q -n 1
   <main-venv-python> -m tools.changelog check
   git diff --check master...HEAD
   ```
   - 判据：架构用例数为 **38**（master 新增 hover key guard）；
     全量 pytest exit 0、changelog exit 0、diffcheck exit 0；
   - pyright 不在合并树跑（临时 worktree 无独立 `.venv`，代码与分支同源、
     分支侧 pyright 已 0；如实登记该跳过及理由，不得声称跑过）。
5. 记录结果后清理：
   `git worktree remove ../yate-pack-dist-zip-merge-check`
   （若因未推送合并提交被拒，先落盘再用 `--force`，并在收尾汇报显式列出
   该删除动作）；`git worktree list` 确认已移除。
6. 回到主 worktree：`git status --short` 为空、`git branch --show-current`
   仍为 `feature/feat-pack-dist-zip`、HEAD 未变。

## 3. 验收判据与回填

| 判据 | 期望 |
| --- | --- |
| 临时 worktree 合并 | exit 0、0 冲突 |
| 合并树架构用例 | 38 passed、exit 0 |
| 合并树全量 pytest | exit 0（用例数 ≥ 分支侧） |
| 合并树 changelog / diffcheck | 均 exit 0 |
| 主工作树 | `git status --short` 空、HEAD 不变、未推送未合流 |
| 临时产物 | worktree 已移除，收尾汇报显式列出 |

结果回填到 `../pack-dist-zip-progress.md`、主计划 §6 与主代理收尾文档；
评审记录/方案中「合并时待办」措辞改为「合并模拟已实测（架构 38、
changelog 0），合并者仍应在最终合并提交上复核」，不篡改历史时点数字。

## 4. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 合并模拟在当前分支产生提交 | 用独立 worktree + detached HEAD，主分支不参与 | `git worktree remove --force` |
| master 与分支仍有冲突 | 提交态 `merge-tree` 已实测 0；冲突则 `--abort` 并登记 | 记录偏离，不强行解决 |
| 临时 worktree 无 venv 导致解释器失败 | 显式使用主 worktree venv 解释器路径；只跑 pytest/changelog | 记录失败与原因 |
| `git worktree remove` 删除未跟踪产物 | 先落盘记录、收尾显式列出；不删 `.codebuddy/`、不动主 worktree | 不适用 |
| 覆盖率 `-n auto` 触发 safe-delete 钩子 | 合并树用 `-n 1`；若钩子仍拦，如实记录并按 §4.7 复核 | 不适用 |

回滚总路径：临时 worktree 完全隔离，`git worktree remove` 即撤销；F14/F15
若无法实测，保留「合并时待办」原状并如实登记，不冒充已验证。
