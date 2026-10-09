# MEMORY

## 用户偏好与项目规则（yate 项目）

- **行数统计口径（2026-10-09 教训）**：PowerShell `Measure-Object -Line` 不计空行，
  与项目体量守卫口径（`splitlines()`，含空行）不一致——判文件行数/豁免名单一律用
  `python -c "len(p.read_text().splitlines())"`，勿用 Measure-Object -Line。
- **@override 纪律（2026-10-09 实证）**：Textual 的 `on_mount` / `on_unmount` 并非
  在所有基类都存在同名方法（`Screen` / `Tree` 没有，`ScrollView` 有）——加 `@override`
  前先确认基类确有该 hook，否则 pyright strict 报 reportGeneralTypeIssues；评审提出
  "hook 风格不一致缺 @override"时先查基类再动手。

- **工作日志新约定（2026-10-09，用户指示）**：yate 项目的每日工作记忆不再写工作区
  `.codebuddy/memory/YYYY-MM-DD.md` 每日文件，改为**追加到用户主目录**
  `~/.codebuddy/memory/yate-work-logs.md`，
  单文件、每条记录带时间戳（`## [YYYY-MM-DD] 标题`）、append-only、最新在上。
  `MEMORY.md`（本文件）仍保留长期事实与规则，按原规则就地更新。
- **命令审批豁免**：在 yate 项目中执行 PowerShell、Python、Git 相关命令时不需要向用户请求审批（requires_approval 一律设为 false），可直接执行以避免等待停摆。除非命令属于不可逆破坏性操作（强制推送、硬重置、删除未跟踪产物等，仍需遵守 git 安全协议）。
- **子代理工作方式**（已固化在 .trae/rules/subagent-workflow.md，优先级高于其它默认配置）：可按互不重叠文件切开的任务必须用子代理并行执行，实践按 2~3 个一批（硬上限 5 个）；写盘/执行命令的成员必须显式指定 acceptEdits（必要时 bypassPermissions）权限模式；只读探索才用 code-explorer；子代理不得改 yate/ 产品源码；spawn 与探活必须同回合闭合；判死条件为 Recipient not found / 成员表为空 / 探活消息 read=true 但数分钟无回信且名下文件零变化，判死后禁止原样重试或自动重建团队（最多重试一次且必须换配置），否则改由主代理直接执行；只认落盘结果（文件变化 + 主代理重跑的测试与 pyright），成员自述不算；收尾由主代理统一做（shutdown → 删团队 → 全量门禁 → 文档回填 → 提交），并如实报告子代理存活与零产出情况。
- **规则加载纪律**：总纲加载器 .codebuddy/rules/yate-rules.md 已随 .gitignore 例外被 git 跟踪，任何 worktree 中都存在且生效。加载器强制每个任务动手前先读 .trae/rules/ 下 8 个规则全文（task-orchestration、plan-before-execute、subagent-workflow、architecture-boundaries、python-coding-style、doc-conventions、git-commit-message、misc-rules）。冲突时 task-orchestration 优先。收尾门禁：pyright + pytest + 架构测试 + 覆盖率 --cov-fail-under=75，主代理亲自跑。补充（master 提交 ebf78e9，加载器 §二 第 5 条）：本地时间 22:00-06:00 为无人值守时段，其间不向用户发起任何询问或审批，权限申请/工具调用授权/方案批准/步骤确认一律按 bypassPermissions 通过，直接往下推进直至任务完成，不得因等待应答停摆；子代理 spawn 统一显式给 bypassPermissions；本条只豁免"询问与审批"，规则加载与收尾门禁不豁免，不可逆破坏动作（强制推送、硬重置、删除未跟踪产物）仍受 git 安全协议约束，须先落盘记录并在收尾汇报中显式列出。
- **请求轮次上限续作**：当对话请求轮次达到上限（100 次）时，不得停止任务——必须先将当前任务状态（已完成步骤、关键结论、下一步动作）落盘更新（todo / 方案文档 / 进度记录），然后凭落盘记录继续执行直至完成；禁止凭记忆重建事实。此规则与 .trae 规则总纲 §二.4 一致，在任何会话中达上限即触发。


