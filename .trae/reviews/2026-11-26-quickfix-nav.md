# 2026-11-26 quickfix 结果导航闭环评审

分支：`feature/enh-quickfix-nav`；基线：`b97a695c`（master）；评审范围 `b97a695c..6808e062`（8 笔提交，含方案、5 个实现波、空批次修复与 doc/smoke 波）。
唯一规范来源：[`../documents/quickfix-nav-plan.md`](../documents/quickfix-nav-plan.md) 与 [`../documents/quickfix-nav-plans/`](../documents/quickfix-nav-plans/overview.md)。

## 1. 评审执行

`code-review-expert` 子代理按剧本交付完整报告，含强制自我批判与实测命令结果；主代理逐条回读复核，不引用子代理自述数字。初评结论 **REQUEST_CHANGES**：3 BLOCKER / 6 MAJOR / 5 MINOR（其中 1 MINOR 自我批判阶段撤回）。

| 级别 | 问题 | 处置 |
|---|---|---|
| BLOCKER | `:diagnostics` 改推 quickfix 面板后 `tests/test_app_lsp.py` 仍断言 `OutputScreen` | 断言改为 `quickfix_panel.display` + `quickfix_flows.active_entries` 标签；已闭环 |
| BLOCKER | 新 quickfix action 未登记进 `tests/test_action_table.py` 的 flow/hook 白名单 | 补 `quickfix_flows` 命名空间与 `next/prev/open` hooks；已闭环 |
| BLOCKER | 初评覆盖率 17.42% 未达 75%（与上述两条失败同时出现） | 两条失败修复后主代理重跑：92.79%；已闭环 |
| MAJOR | `editor_compose.py` 出现 `_file_match_entries`，打破六工厂契约 | 转换下沉到 `QuickFixFlows.set_search_results`；组装模块恢复六工厂；已闭环 |
| MAJOR | 搜索空批次注释与实现矛盾 | 注释对齐“清空但静默”；R15 流程不再发通用空消息，避免覆盖 replace 报告；已闭环 |
| MAJOR | `set_quickfix` 可选注入偏离方案且掩盖漏注入 | 两个 flow 改为必填 keyword-only；`test_events` / `test_lsp_navigation_flows` 夹具显式注入；已闭环 |
| MINOR | `QuickFixList.clear()` 不清 label | 同步清 label 并补断言；已闭环 |
| MINOR | `jump_to` 在 reveal 失败时已推 jump-list | 提交 `983b1e77` 闭环：原点在 reveal 前捕获、成功后显式 push；负向演练先红后绿；已闭环 |
| MINOR | `editor_compose` 过时“provider 后续波次注入”注释 | 改为 late-bound adapter 说明；已闭环 |
| MINOR | 方案文档真实绝对路径 | 自我批判撤回：文档内为可移植命令与 worktree 名，无盘符路径 |
| MINOR | 提交带 `Co-authored-by` trailer | 规则未禁止，仅与基线惯例不一致；登记不阻塞 |

## 2. 迭代结论

修复提交 `6808e062` 后，初评 BLOCKER / MAJOR 全部关闭；3 个有效 MINOR 当轮修复，1 个 MINOR 误报撤回，1 个 MINOR 仅作惯例提示。剩余 1 条 jump-list 边界 MINOR 由 `983b1e77` 后续闭环（负向演练先红后绿），无遗留功能缺口。主代理复核后结论：**APPROVE**。

## 3. 主代理亲跑门禁（最终态，全部 exit 0）

| 命令 | 结果 |
|---|---|
| `python -m pyright yate/ tests/ tools/ pack/` | 0 errors / 0 warnings / 0 informations |
| `python -m pytest tests/ -q -n auto` | 退出码 0 |
| `python -m pytest tests/test_architecture.py -q` | 48 passed |
| `python -m pytest tests/ --cov=yate --cov-branch -n auto` | 4084 passed / 10 skipped；TOTAL 93%、`fail_under=75` 实测 92.83% |
| `python -m tools.smoke_test run --jobs 4` | 129/129 scenarios、1575/1575 checks |
| `python -m tools.changelog check` | released 段最新，退出码 0（未发布段滞后 2 commits 属生成器机制） |

## 4. 纪律与偏离记录

- 规划者子代理两次因 `Model "qwen-3.8-plus" not found` 失败；按 `../rules/task-orchestration.md` 主代理代笔方案，并用只读 explorer 取证，已在主计划 §1 登记。
- 执行者分 4 波并行/串行交付，评审者成功交付；所有成员自报数字均由主代理重跑复核。
- `QuickFixList.replace` 采用原位替换（新批次占据被替换批次位置），与主计划测试期望一致。
- `set_quickfix` 与面板回调均为必填注入；`on_search_results` 通过 late-bound adapter 注入以适配组装顺序。
- 冒烟场景的 next/prev 落点按实测 references 条目顺序实现（def → call-site），核心语义与 AC9 一致。
- 全流程未推送、未合入 master；AC10 的外部 roadmap 勾选在合流后执行。
