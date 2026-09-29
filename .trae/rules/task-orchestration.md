# task-orchestration（任务闭环编排）

本规则规定非平凡任务在**主代理会话**内的执行方式：主代理按角色剧本推进闭环，
角色定义文件（`.trae/agents/*.md`）是唯一执行剧本，本规则只做强制入口，细节以剧本为准。

## 一、判据：哪些任务必须走闭环

满足 `plan-before-execute.md` §一任一判据（≥3 文件 / 跨层触架构边界 / 多方案需选型 /
需先调研 / 用户要求），即走下述闭环流程；其余任务可直接执行。

## 二、闭环流程（逐步登记，文档是唯一事实来源）

1. 【领会】分析任务；**新任务**先建独立 worktree 与分支
   （`git worktree add ../yate-<task> -b <fix|feat|enh|ref>/<task>`），
   **续作任务**先 `git worktree list` 复用现有 worktree，禁止重复新建。
2. 【方案】按 `plan-architect-designer` 剧本产出方案，落盘
   `.trae/documents/<task>_plan.md`（相对路径；复杂任务拆子计划到
   `.trae/documents/<task>_plans/` 并严格定制执行波次）。
3. 【批准】向用户呈现方案，**未经批准不得进入执行**（plan-before-execute 硬性流程）。
4. 【执行】按 `plan-executor` 剧本实施：独占文件清单 + 计划内验收命令；
   文件不重叠的步骤按波次并行，波次间串行。
5. 【审核】按 `code-review-expert` 剧本评审全部改动：pyright / pytest /
   架构测试 / 覆盖率（`--cov-fail-under=75`）/ 冒烟，结论附实测结果与退出码。
6. 【迭代】存在 blocker / major → 回到步骤 2 重新设计；仅 minor → 登记待办。
   迭代上不封顶，直至无 blocker / major。
7. 【收尾】主代理亲自跑全量门禁（pyright + pytest + 架构测试，退出码 0），
   回填文档（真实前后数字、偏离记录），按 `git-commit-message.md` 提交。

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
