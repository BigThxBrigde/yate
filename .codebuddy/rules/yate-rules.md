---
alwaysApply: true
scene: yate_master_rules_loader
---

# yate 项目规则总纲（强制加载器）

本文件是 CodeBuddy 侧的**唯一规则入口**，自身不含规则内容，只负责强制加载
仓库内被 git 跟踪的规则源（`.codebuddy/` 已被 .gitignore 忽略，任何规则都
不允许落在这里——worktree 中本目录不存在，只有 `.trae/` 永远可用）。

## 一、强制加载（每个任务动手前必须完成）

任务开始时，**先读后干**：逐个读取下列规则源文件全文，再分析任务。

### 1.1 必读（每次任务，8 个）

以 `../../.trae/rules/` 为唯一权威规则来源：

| # | 文件 | 管什么 |
|---|---|---|
| 1 | `task-orchestration.md` | 非平凡任务闭环流程（优先级最高） |
| 2 | `plan-before-execute.md` | 方案先行判据与方案文档格式 |
| 3 | `subagent-workflow.md` | 子代理并行纪律（批大小、判死、只认落盘结果） |
| 4 | `architecture-boundaries.md` | 架构边界 R1-R13（触碰架构前必须精读） |
| 5 | `python-coding-style.md` | Python 编码风格（pyright strict 零诊断） |
| 6 | `doc-conventions.md` | 文档命名与相对路径引用 |
| 7 | `git-commit-message.md` | 提交信息格式 |
| 8 | `misc-rules.md` | PowerShell here-string、解释器路径等环境约束 |

冲突裁决：`task-orchestration.md` 优先级最高；产品侧冲突以
`architecture-boundaries.md` 为准。

### 1.2 按需读

- 方案落盘与计划文档命名：`../../.trae/documents/` 下既有计划即模板
  （主计划 `<task>-plan.md`、子计划目录 `<task>-plans/` + `overview.md`，
  总纲见 `doc-conventions.md` §一）；
- 架构改动参照 `../../.trae/documents/app-layering-refactoring-plans/overview.md`；
- 对应领域的既有计划文档（如 LSP / pytest 隔离 / editor 重构）在实现同类
  功能前先读，作为"唯一规范来源"下发给子代理。

## 二、硬性要求

1. **禁止绕过**：不得以"任务简单"为由跳过本加载；只有用户给了完整逐步指令的
   单文件小修，可只读规则 1/2 的判据部分确认豁免后直接执行。
2. **加载即生效**：读到的规则对本次会话全部后续步骤生效，收尾门禁
   （pyright + pytest + 架构测试，覆盖率 `--cov-fail-under=75`）必须主代理亲自跑。
3. **worktree 自举**：本文件属机器本地数据，worktree 中不存在——若会话内发现
   规则未加载（如凭记忆直接开工），必须立即补读 §1.1 全部 8 个文件再继续。
