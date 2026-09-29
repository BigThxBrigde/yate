# yate Code Review — 冒烟补场景调查 — 2026-09-23

## 冒烟补场景调查 — 2026-09-23

> 来源：按 `run --coverage` 缺口补冒烟场景（计划 §7.10，提交 `0984361`）。仅记录，未修产品源码。

- [x] **action `quit` 注册后在 UI 上不可达（Low，注册冗余）** — [`keymaps/vsc.py:87`](../../yate/keymaps/vsc.py)
  两条独立原因：① vsc 的 `<ctrl+q>` 绑定被 Textual App 级 priority binding 遮蔽
  （`App.BINDINGS` 内置 `('ctrl+q','quit', priority=True)`，[`app.py`](../../yate/app.py) 覆写 `action_quit` 直接调 `Editor.quit()`）；
  ② 命令面板刻意去重与同名 `:command` 重名的 action（[`palette.py:186-190`](../../yate/editor_view/palette.py)），
  `quit` 命令存在 → 同名 action 条目被丢弃。用户可见的退出路径（ctrl+q 键、`:quit` 命令）均正常，无用户可见症状；
  只有 `execute_action("quit")`（扩展/测试路径）能触达该注册条目。
  **可选修法（三选一）：** ① `YateApp.action_quit` 改调 `editor.execute_action("quit")`；② 面板保留同名 action；③ 删除冗余的 vsc `<ctrl+q>` 绑定。
  冒烟侧已由 [`scenarios/files.py::quit_action_dispatch`](../../tools/smoke_test/scenarios/files.py) 覆盖，`--coverage` 达 65/65。
  *✅ 已修复（2026-09-25，P2 决策门 G2 拍板选①）：`YateApp.action_quit` 改调 `editor.execute_action("quit")`（[app.py](../../yate/app.py)），ctrl+q 与 palette/扩展走同一注册表条目；冒烟两个 quit 场景 docstring 同步更新；守卫 `test_ctrl_q_routes_through_the_registered_quit_action`（spy 重注册 `quit` 证明键路径过注册表）。*

- [x] **终端面板显示时无法用按键把焦点交回编辑器（Nice-to-have）** — [`terminal.py:193-204`](../../yate/editor_view/terminal.py)
  面板获得焦点后 `TerminalView.on_key` 吞掉除 `ctrl+`` 之外的所有按键（`ctrl+1`、`Esc`、F5 等均被 stop 并转发给 shell），
  关闭/回焦只能靠 toggle 键。这是"终端独占键盘"的设计选择且有明确出路（`ctrl+`` 关闭），但对 vscode 习惯（`ctrl+1`）不友好。
  **可选修法：** 在 `TOGGLE_KEYS` 之外放行 `ctrl+1`（`focus_editor`）；`Esc` 需先确认 shell 是否依赖。
  *✅ 已修复（2026-09-25，P2 波次二 SP6）：新增 `FOCUS_EDITOR_KEY = "ctrl+1"` 分支（stop+prevent_default 后调 `panel.focus_editor`，置于 dead-shell 复活分支之前——焦点切换不复活 shell）；`Esc` 本轮不动。R10 自检：放行键不二次派发。守卫：`test_terminal_focused_ctrl1_returns_focus_to_editor`（含 shell 输入流未收到该键断言）。*
  *✅ 收尾批补做冒烟场景（2026-09-25）：`terminal_focus_editor`（integration.py，内存 fake PTY 不起真 shell，未标 slow；断言焦点回编辑区 + ctrl+1 字节未进 shell 流）——补齐 P2 原文要求的冒烟验收面。*
