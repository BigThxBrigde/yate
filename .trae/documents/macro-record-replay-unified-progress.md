# 宏录制与回放（统一键位）任务进度记录 — 2026-11-12 新任务轮

> 来源：Gitee issue IKUOAM，用户 2026-11-12 指令「进入无人值守，无须过问；
> 根据 IKUOAM 描述执行新任务，严格按照纪律执行，唯一例外的是全程使用 Hy4
> 模型，如果模型限流，请切换 GLM-5.3-Flash」。
> 本文件是进度事实的唯一落盘处；每步完成后回填实测数字与偏离记录。

## 0. 环境与纪律核对（【领会】）

| 项 | 事实 |
| --- | --- |
| 必读规则 | `.trae/rules/` 8 份已全文加载（task-orchestration / plan-before-execute / subagent-workflow / architecture-boundaries / python-coding-style / doc-conventions / git-commit-message / misc-rules） |
| 分支基线 | 主工作区 `master` HEAD `be6b4a54`，`git rev-list --left-right --count master...origin/master` = `0 0`（已同步）；`git show master:.trae/rules/task-orchestration.md` 核对为单主干 master 口径 |
| 新 worktree | `yate-macro-record-replay-unified`，分支 `feature/feat-macro-record-replay-unified`，parent `master be6b4a54`；`git worktree list` 已复核 |
| 独立沙箱 | worktree 内 `python -m venv .venv` + `pip install -e ".[dev]"`；自证 `.venv\Scripts\python.exe -c "import yate; print(yate.__file__)"` 输出本 worktree 的 `yate/__init__.py` |
| 主仓未提交改动 | `yate/resources/changelog.{en,zh}.md`（生成器刷新），本轮不触碰、不提交 |
| 分流 | 用户消息含「新任务」关键字 → `task-orchestration.md` §1.2 闭环流程；无人值守【批准】按通过处理（§硬性要求 5），不向用户发起询问或审批 |
| 子代理模型 | 用户指定全程 Hy4，限流回退 GLM-5.3-Flash（本轮唯一例外）。本机 `task` 工具无模型参数、frontmatter 生效的环境事实已登记在上一轮进度文档；本轮 spawn 实测结果与处置见 §1 |
| 既有分支 | `feature/feat-macro-record-replay`（14 提交、未合流未推送）为同一 issue 的上一轮产物，本轮作**只读情报**，不合流、不推送 |

## 1. 步骤状态

| 步骤 | 状态 | 产物 / 提交 / 实测 |
| --- | --- | --- |
| 【领会】 | 完成 | 素材 `macro-record-replay-unified-issue.md`、本进度文件；worktree + venv 自证 |
| 【方案】 | 待办 | 主计划 `<task>-plan.md` + 子计划目录 `<task>-plans/`（含总纲 `overview.md`）、执行波次与文件互斥矩阵 |
| 【批准】 | 待办 | 无人值守按通过处理，须落盘「批准记录」章节 |
| 【执行】 | 待办 | 按波次并行，2~3 个一批、硬上限 6；只认落盘结果 |
| 【审核】 | 待办 | `code-review-expert` 评审 + 门禁五项实测 |
| 【迭代】 | 待办 | blocker / major 归零；minor 登记 |
| 【收尾】 | 待办 | 主代理亲跑全量门禁、回填真实数字、按步提交、更新记忆 |

## 2. 待回填

- 方案文档路径、波次划分、独占文件清单、验收命令。
- 每波执行者存活数、零产出成员及名下文件状态、主代理复核命令与退出码。
- 评审轮次、blocker / major / minor 清单与修复提交。
- 收尾七项门禁真实数字（pyright / pytest / 架构 / 覆盖率 / 冒烟 / changelog / diffcheck）。
- 偏离计划项与实测依据；模型可用性与回退处置的实测记录。
