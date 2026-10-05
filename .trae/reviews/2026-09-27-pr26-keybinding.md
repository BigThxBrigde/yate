# yate Code Review — Gitee PR #26 评审（键位修复分支）— 2026-09-27

## Gitee PR #26 评审（键位修复分支）— 2026-09-27

> **范围**：PR #26 `feat(keyproto): add keyproto to fix keybinding in wt`
> （`issues/keybinding-fix-wt` → `master`，含合入的 PR #25 分层日志；47 commits / 56 files），
> 关联 Issue [IKH1RA](https://gitee.com/jermaine/yate/issues/IKH1RA)。本次登记
> **Gitee AI 队友审查**（[原始评论](https://gitee.com/jermaine/yate/pulls/26#note_51376461_conversation_190970238)，
> 审查时间 2026-09-27 07:56）：结论 ⚠️ **无阻断项，3 个改进建议，可优化后合并**；风险等级
> **medium**。四维度判定：功能性与逻辑 ✅ 通过；安全性 ⚠️ 待优化；性能 ⚠️ 待优化；
> 可维护性 ⚠️ 待优化。潜在影响（原文摘要）：正确性显著提升 Windows 平台键盘兼容性；
> 帧解码与日志默认开销极低，高负载/开启追踪时需监控；`keyproto` 结构清晰但复刻上游
> 增加长期维护负担；输入线程异常处理策略略显脆弱。
> 比对说明：本地先行评审（[2026-09-27-keybinding-branch-review.md](2026-09-27-keybinding-branch-review.md)，
> 2 项发现修复于 `b21ff37`）已覆盖 AI 3 项改进中的 2 项且修复在先；逐条比对**无遗漏、
> 无新增**，AI 唯一超出本地清单的是改进 1 的残余建议（见下）。

### AI 改进项逐条登记

- [x] **输入线程宽泛 `except Exception` 可致键盘永久失灵（安全性）** —
  [`driver_windows.py`](../../yate/keyproto/driver_windows.py) `ChordEventMonitor.run`
  捕获所有异常后仅记日志，输入线程静默退出后键盘失灵且无提示（AI 原文注明畸形帧崩溃
  "虽已修复但仍有风险"）。
  *✅ 崩溃根因已先行修复（2026-09-27，`b21ff37`）——畸形帧空字段 `int('')` 的 ValueError
  改为按 0 解码（代码与 docstring 对齐）+ `;;` 帧 fixture 守卫；宽泛 except 为照抄
  stock（Textual 8.2.8）的既有形态，与本地评审判定一致（触发面窄、后果重）。*
  - [ ] **残余建议（登记待评估）**：AI 建议补 `exc_info=True` 堆栈信息 / 重置驱动状态 /
        UI 通知 / 极端时安全退出。与改进 2 的 stock 复刻基线存在张力——偏离 stock 会让
        升级 diff 变复杂；若采纳，应与上游修法对齐并同步更新版本 pin 注释。

- [x] **复刻上游代码存在静默漂移风险（可维护性）** —
  [`driver_windows.py`](../../yate/keyproto/driver_windows.py) `ChordEventMonitor.run` /
  `start_application_mode` 大量复刻 Textual 上游实现，上游升级时子类可能静默失配。
  *✅ 已先行处理（2026-09-27，`b21ff37`）——两处 docstring 注明基于 Textual 8.2.8 复刻、
  升级时先 diff stock（[driver_windows.py:110](../../yate/keyproto/driver_windows.py#L110)、
  [driver_windows.py:254](../../yate/keyproto/driver_windows.py#L254)，后者已标注唯一
  "insertion point" 即 chord 分支）。AI 追加建议（升级时建立 diff 检查流程、标注插入点）
  属流程改进，现文档已承载：插入点与 9001h 启停读写均写入 docstring 与
  [keybinding-fix-wt-steps-plan-g.md PB6 节](../documents/keybinding-fix-wt-plans/keybinding-fix-wt-steps-plan-g.md)，无需改码。*

- [x] **热路径 `log.debug` 开销（性能）** —
  [`editor.py`](../../yate/editor.py) `Editor.handle_key` 高频路径日志在 `YATE_TRACE=1`
  时或产生格式化/对象创建开销，影响按键响应延迟。
  *✅ 无需行动（设计即满足）——`tracing` 默认关闭零 IO；惰性 `%` 占位由 AST 守卫
  `test_log_calls_use_lazy_percent_formatting`
  （[test_architecture.py:340](../../tests/test_architecture.py#L340)）强制，禁用态无
  字符串格式化；被评语句实参求值仅为属性访问与类型名，开销可忽略。AI 评审自身亦注明
  "目前实现看起来是安全的（使用 % 格式化）"。*
