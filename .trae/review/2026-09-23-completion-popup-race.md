# yate Code Review — 补全弹窗按键放行修复的附带发现 — 2026-09-23

## 补全弹窗按键放行修复的附带发现 — 2026-09-23

> 来源：修复「补全弹窗吞掉所有按键」（提交 `bbeb5f6`）期间实测到的相邻竞态，本轮**未修**、仅登记。
> 冒烟 [`regress_completion_popup_keys`](../../tools/smoke_test/scenarios/regression.py) 用 0.3s 落定等待规避它，
> 是为了让断言只测"键位分工"，并未掩盖该现象本身。

- [x] **Esc 关闭补全弹窗后，在途的自动补全 worker 会把它重新显示（Low，UX 抖动）** — [`completion.py:128`](../../yate/completion.py)
  `popup.close()` 只改弹窗状态、不取消已排队的请求：`CompletionController._stale()`
  （[`completion.py:202-219`](../../yate/completion.py)）只比较文档 / 行 / 列 / 前缀与挂载状态，
  不检查弹窗是否被用户显式关闭，因此 worker 落地后仍会调用 `popup.show()`。
  按键触发的 0.12s 防抖查询（`_DEBOUNCE_S`，[`completion.py:38`](../../yate/completion.py)）
  恰好落在 Esc 之后时，弹窗会在约 0.1s 后重新出现：探针实测 Esc 后立即 `is_open=False`，
  在途 worker 落地后回到 `True`（临时探针脚本已删除，未落盘）。
  **修复：** 关闭时记录"用户已忽略"标记（或递增 generation / 取消在途 worker），
  `_worker` 与 `_stale()` 一并检查；用户再次主动触发（`Ctrl+Space`，或继续输入使前缀变化）时清除。
  注意与 `after_editor_key` 的 `schedule()` 区分：后者属于主动输入路径的 guarded re-query，应保留。
  *✅ 已修复（2026-09-24）— [completion.py](../../yate/completion.py) 三状态标记（`_dismissed`/`_scheduled_open`/`_inflight_open`）：`close()` 记录已忽略、`schedule()` 主动输入重 arm、非手动 `request()` 遇已忽略或「调度时开着、触发前已被关闭」放弃、`_stale()` 增在途关闭抑制子句；校准：Esc 分支在 editor.py widget 级直调 `popup.close()` 不经过控制器，配合 `is_open` 差分检测（`_scheduled_open` + `_inflight_open`）；守卫 `test_esc_keeps_the_popup_closed_until_retriggered` 及防抖抑制、gated LSP stub 在途抑制共 3 条。*
