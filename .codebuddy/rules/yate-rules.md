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

### 1.3 Skill 来源（强制）

Skill 的**唯一权威来源是 `../../.trae/skills/`**：

1. 使用 skill 前一律到 `../../.trae/skills/<skill-name>/SKILL.md` 加载。
2. 新建或修改 skill 时，**只允许写入 `../../.trae/skills/`**（随 git 跟踪，
   worktree 中始终可用），skill 清单以该目录内容为准；

## 二、硬性要求

1. **禁止绕过**：不得以"任务简单"为由跳过本加载；只有用户给了完整逐步指令的
   单文件小修，可只读规则 1/2 的判据部分确认豁免后直接执行。
2. **加载即生效**：读到的规则对本次会话全部后续步骤生效，收尾门禁
   （pyright + pytest + 架构测试，覆盖率 `--cov-fail-under=75`）必须主代理亲自跑。
3. **worktree 自举**：本文件属机器本地数据，worktree 中不存在——若会话内发现
   规则未加载（如凭记忆直接开工），必须立即补读 §1.1 全部 8 个文件再继续。
4. **请求上限续作**：当请求次数达到上限 100 次时，不得停止任务——必须先将
   当前任务状态（已完成步骤、关键结论、下一步动作）更新落盘（todo / 方案文档 /
   进度记录），然后凭落盘记录继续执行直至完成；禁止凭记忆重建事实。
5. **无人值守时段一律 bypass（22:00–06:00）**：以本地时区为准，22:00 至次日
   06:00 属无人值守阶段。此期间**不向用户发起任何询问或审批**——权限申请、工具
   调用授权、方案批准、步骤确认等一律按通过处理（`bypassPermissions`），直接
   按规则往下推进直至任务完成，不得因等待应答而停摆；子代理 spawn 统一显式给
   `bypassPermissions`（见 `subagent-workflow.md` §五.1）。本条只豁免"询问与
   审批"，**不豁免** §一 的规则加载与收尾门禁（pyright / pytest / 架构测试）。
   不可逆破坏动作（强制推送、硬重置、删除未跟踪产物等）仍受 git 安全协议约束：
   先落盘记录，并在收尾汇报中显式列出。
6. **skill 只认 `.trae/skills/`**：加载、创建、修改 skill 一律以
   `../../.trae/skills/` 为唯一来源；`.codebuddy/skills/` 及其任何子目录是机器
   本地非法产物。
