# yate Code Review — 全量代码审查 — 2026-09-23

## 全量代码审查 — 2026-09-23

> 7 项全部修复，方案与验证记录见
> [`.trae/documents/code-review-fixes-plan.md`](../documents/code-review-fixes-plan.md)
> （提交 `05106d5` / `5190225` / `b0d154d` / `a89a720`）。

- [x] **`Document.save()` 非原子写入（High，数据完整性）** — 崩溃/磁盘满可毁原文件。
  已改 temp + `os.replace` 原子替换（`05106d5`）。
- [x] **undo 栈无深度上限（Medium）** — 全量快照无界增长。
  新增 `MAX_UNDO_STEPS = 1000` 淘汰最旧步骤（`05106d5`）。
- [x] **`doc.modified` 每键 O(n) 全文对比（Medium）** — 即上文 Suggestion 第 3 条。
  `content_edits` 计数 + 精确回退（`05106d5`，回归由 `5190225` 修复）。
- [x] **垂直移动丢失期望列（Medium）** — 短行截断后列永久丢失。
  `_goal_col` 追踪，编辑/水平移动/undo 等全路径清除（`b0d154d`）。
- [x] **扩展从 CWD 静默自动加载（Medium，供应链）** — 打开仓库即执行仓库自带代码。
  工作区信任门控：`~/.yate/trusted_workspaces` + `:trust` 显式确认（`a89a720`）。
- [x] **6 处 `except Exception: pass` 静默吞异常（Low）** — 违反规则 §4.5。
  保留隔离语义，全部补 `log.exception`（`05106d5`）。
- [x] **`walk_files` 不防符号链接环（Low）** — `ln -s . loop` 无限递归。
  不再进入符号链接目录（`05106d5`，即上文 Suggestion 第 11 条的环部分）。
