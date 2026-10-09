# closure-sweep-plans 总纲

无人值守闭环清扫任务（2026-10-09）：风格合规审查 / 模块结构审查 / reviews 非闭环点修复。
worktree `../yate-closure-sweep`，分支 `fix/closure-sweep`（自 master `25e17d3`），沙箱 venv 已自证。

## 子计划

| 子计划 | 对应任务 | 波次 |
|---|---|---|
| [closure-sweep-style-plan-a.md](closure-sweep-style-plan-a.md) | 任务 2：python-coding-style 合规审查 | Wave A |
| [closure-sweep-structure-plan-b.md](closure-sweep-structure-plan-b.md) | 任务 3：模块结构清晰度审查 | Wave B |
| [closure-sweep-reviews-plan-c.md](closure-sweep-reviews-plan-c.md) | 任务 4：reviews 非闭环点核实与修复 | Wave C（主体） |

## 执行模型

- `yate/` 产品源码修复由主代理亲自执行（subagent-workflow §一.3 禁子代理改产品源码）；
  tools/tests 修复按文件独占派给子代理并行（`acceptEdits`，批大小 2）。
- 偏离记录：DeepSeek-V40-Pro / GLM-5.3-Flash 模型指定不可用（运行时无模型选择能力），
  计划与执行均由当前主代理（GLM-5.3-Flash 会话）承担。
- 每步产物单独提交（git-commit-message.md），只提交不推送。
- 收尾门禁主代理亲自跑：pyright 0 + pytest 全绿 + 架构 28 用例 + 覆盖率 `--cov-fail-under=75` + 冒烟。

## 状态

- [ ] Wave A/B/C 执行
- [ ] 门禁
- [ ] reviews/README 索引回填 + 本目录回填
