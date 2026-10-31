# multi-dim-review-fixes 修复方案

来源评审记录：[2026-10-31-multi-dim-review.md](../reviews/2026-10-31-multi-dim-review.md)
（#50 全仓库多维度评审，APPROVE / 0 BLOCKER / 0 MAJOR / 3 MINOR）。本方案只修三条
MINOR，不动其它已登记项。

- 分支：`fix/multi-dim-review-fixes`（自 master `4f011df` 新建 worktree）
- 基线门禁：pyright 0 / 全量 pytest exit 0 / 架构 37 / 覆盖率 92.25% / 冒烟 117/117

## F1 pty_proc 四处静默 pass 加一次性可观测（MINOR-1）

- 评审位置：yate/editor_term/pty_proc.py 的 write / resize / terminate / _finished
  四个 `except (OSError, ...): pass` 分支。
- 方案：`PtyProcess` 增加实例标志 `_io_failure_logged` 与助手
  `_note_io_failure(op, exc)` —— 首次失败以
  `log.debug("pty %s failed (child likely dead): %s", op, exc)` 记录一条，
  之后保持静默（write 在每次击键路径上，逐次日志会刷屏；死亡后的一次性
  状态转换日志即可区分「死了」与「安静」）。四个分支改为携带异常调用助手；
  best-effort 契约不变（仍不 raise，docstring 语义保留）。
- 验收：pyright 0；tests/test_pty_proc.py 新增一次性日志单测全绿；
  tests/test_app_terminal.py 全绿。

## F2 test_app_find 空清用例去真实睡眠（MINOR-2）

- 评审位置：tests/test_app_find.py:1151 `await asyncio.sleep(0.3)`（与已修的
  3 处防抖 flake 同族）。
- 方案：沿用同文件 test_live_search_debounces_rapid_typing 先例（1112-1131）——
  monkeypatch 冻结 `LIVE_SEARCH_DEBOUNCE_S = 30.0`，断言 `_live_timer` 在位后
  手动调 `_flush_live_search()` 交付查询，再退格验证空查询立即清除、
  定时器被丢弃；删除真实睡眠。
- 验收：pytest tests/test_app_find.py 全绿（单跑与 -n auto 并行均过）。

## F3 尺寸豁免行数登记同步（MINOR-3）

- 评审实测：editor.py 1239（登记 1238）、services/yxp.py 841（登记 830）、
  editor_syntax/langdefs.py 841（登记 813）。
- 方案：同步 `.trae/rules/architecture-boundaries.md` §三.7 三处行数登记与
  `tests/test_architecture.py` `SIZE_EXEMPT_FILES` 相应注释；豁免集合本身不变。
- 验收：pytest tests/test_architecture.py 全绿。

## 登记与回滚

- 评审记录头部补修复方案互链；reviews README #50 处置状态更新为已修（附提交号）。
- 回滚：三笔提交各自独立、互不依赖，逐笔 revert 即可。

## 收尾门禁（主代理亲跑）

pyright（yate/tests/tools）0 诊断；全量 `pytest tests/ -q -n auto` exit 0；
架构 37 passed；`python -m tools.smoke_test run --jobs 4` 全过（终端面板路径
被 F1 触碰，冒烟不豁免）。
