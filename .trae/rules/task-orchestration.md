---
alwaysApply: true
scene: task
---

# task-orchestration（任务闭环编排）

本规则规定非平凡任务在**主代理会话**内的执行方式：主代理按角色剧本推进闭环，
角色定义文件（`.trae/agents/*.md`）是唯一执行剧本，本规则只做强制入口，细节以剧本为准。

## 一、判据：哪些任务必须走闭环

满足 `plan-before-execute.md` §一任一判据（≥3 文件 / 跨层触架构边界 / 多方案需选型 /
需先调研 / 用户要求），即走下述闭环流程；其余任务可直接执行。

**关键字触发**：用户消息中出现「新任务」「新issue」「新计划」任一关键字，
即视为新任务，必须走闭环流程，无需再对照其余判据。

**优先级最高**：本规则与其他规则（含 `plan-before-execute.md`、`subagent-workflow.md`）
同时被触发时，**以本规则为准**——闭环流程是唯一执行路径，其它规则的流程要求
（如方案先行、子代理并行）并入本闭环的对应环节（【方案】/【执行】）执行，
不各自独立成流程。

## 二、闭环流程（逐步登记，文档是唯一事实来源）

1. 【领会】分析任务；**新任务**先建独立 worktree 与分支
   （`git worktree add ../yate-<task> -b <fix|feat|enh|ref>/<task>`）；
   **worktree 不与主仓共享虚拟环境**——新建 worktree 后必须在其目录内重建沙箱，
   否则后续 pyright / pytest / 冒烟全部指向主仓 `.venv`，污染主环境：
   ```powershell
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```
   安装完成须在 worktree 内自证沙箱生效
   （`.venv\Scripts\python.exe -c "import yate; print(yate.__file__)"` 应指向该 worktree 路径）；
   **续作任务**先 `git worktree list` 复用现有 worktree（含其已有 `.venv`，不得重复新建）。
2. 【方案】按 [plan-architect-designer](../agents/plan-architect-designer.md) 剧本产出方案，落盘
   `.trae/documents/<task>-plan.md`（相对路径；复杂任务拆子计划到
   `.trae/documents/<task>-plans/` 并严格定制执行波次）。**命名规范**：
   主计划 `<task>-plan.md`；子计划 `<task>-<subtask>-plan-<a|b|c...>.md`
   （subtask 可省略，SP/P 等波次标记一律转字母序）；子计划目录总纲命名
   `overview.md`；目录名统一连字符 `<task>-plans/`。
3. 【批准】向用户呈现方案，**未经批准不得进入执行**（plan-before-execute 硬性流程）。
4. 【执行】按 [plan-executor](../agents/plan-executor.md) 剧本实施：独占文件清单 + 计划内验收命令；
   文件不重叠的步骤按波次并行，波次间串行。
5. 【审核】按 [code-review-expert](../agents/code-review-expert.md) 剧本评审全部改动：pyright / pytest /
   架构测试 / 覆盖率（`--cov-fail-under=75`）/ 冒烟，结论附实测结果与退出码。
6. 【迭代】存在 blocker / major → 回到步骤 2 重新设计；仅 minor → 登记待办。
   迭代上不封顶，直至无 blocker / major。
7. 【收尾】主代理亲自跑全量门禁（pyright + pytest + 架构测试，退出码 0），
   回填文档（真实前后数字、偏离记录），按 `git-commit-message.md` 提交。

> **提交纪律**：以上每一步完成后，须按 `git-commit-message.md` 将本步骤产物
> **单独提交一次**（scope 取该步对象，如 `docs(rules): ...`），不得把多步改动
> 攒成一笔提交；**只提交、不推送** —— 闭环流程内禁止执行 `git push`，
> 推送必须由用户显式要求后才进行。

## 三、调度方式

- 子代理可以派发时：派 `general-purpose` 成员，任务书指定其先读对应角色文件
  再干活（「先读 `.trae/agents/<role>.md`，严格按其职责执行」），并遵守
  `subagent-workflow.md` 的批大小、探活、判死与只认落盘结果纪律。
- 无法派发或成员零产出时：主代理亲自按剧本执行，如实标注，不得阻塞主任务。
- 每步的输入、产出、审核结论、迭代轮次必须回填方案文档；偏离计划须显式记录并附实测依据。

## 四、上下文管理（context 压缩）

- context 占用超过 75% 立即压缩，宁早勿满：先落盘进度（已完成步骤、结论、下一步），
  再执行压缩；压缩后凭落盘记录续作，不得凭记忆重建事实。
- 派发子代理任务书时同样要求成员遵守本条。
