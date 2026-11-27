# 计划 i —— 冒烟场景（波次 5）

父计划：[overview.md](overview.md) · 主计划：[../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)，§8
依赖：计划 h（应用持有 `hover_popup` / `hover` / `MouseFlows` 回调）。

## 输入

- `tools/smoke_test/scenarios/__init__.py:1-7`（每个模块导出 `SCENARIOS: list[Scenario]`）、`:13-36`（导入）、`:51-76`（单一聚合点）。
- `tools/smoke_test/scenarios/_base.py:3-11`（场景签名 `async def (tmp: Path) -> ScenarioResult`）、`:31-37`（`_COMMAND_KEY="f5"`、`_DRAIN_TIMEOUT_S`）、`:93-98`（`message_text`）、`:111-128`（`wait_until`，唯一允许的轮询原语）。
- `tools/smoke_test/harness.py:191-211`（`Check(label, expected, actual)`）、`:214-239`（`ScenarioResult`）、`:242-255`（`Scenario(name, run, tags)`）、`:361`（`new_app()`）、`:539-706`（运行器与选择逻辑）。
- `tools/smoke_test/scenarios/core.py:65-79`（`_keymap_toggle` 按下 `ctrl+/`）、`tools/smoke_test/scenarios/edit.py:48-52`（现有的 `ctrl+k` 删除行断言 —— 必须保持通过）。

## 独占文件

- `tools/smoke_test/scenarios/hover.py`（新建）
- `tools/smoke_test/scenarios/__init__.py`
- `tools/smoke_test/harness.py` —— **评审后追加（已登记偏离）**：首轮代码评审发现新标签 `("hover",)` 未出现在 `harness.TAGS` 中，导致 `tests/test_smoke_harness.py` 中的两条注册守卫使完整 pytest 门禁失败。在 `:102` 处向 `TAGS` 添加了一条 `"hover"` 条目；未改动其他 harness 代码。**原因：**每个场景标签都必须声明，否则 `--tag` 选择无法命中它。**证据：**首轮评审的 `[blocker]`，由主代理独立复现（`pytest tests/ -q -n auto` 退出码 1，2 个失败，`assert ['hover'] == []`）。

## 具体改动

1. `tools/smoke_test/scenarios/hover.py` —— 模块 docstring（ASCII 英文）、
   `from __future__ import annotations`、绝对导入、完整类型标注，底部为
   `SCENARIOS: list[Scenario]`。两个场景，标签均为
   `("hover",)`：
   - `"hover_docs_key_is_silent_without_a_server_in_both_keymaps"`：
     在 `app.run_test()` 内调用 `app = new_app()`（遵循 `_base.py`）；在默认 vsc keymap 中按
     `"f7"`，然后 `pilot.press("ctrl+/")` 并再次按
     `"f7"`。使用 `wait_until(pilot, predicate)` 等待 worker 排空，
     绝不使用固定 sleep。检查项：
     - `Check("keymap", "vim", app.editor.keymaps.active.name)`，
     - `Check("card", False, app.editor.hover_popup.is_open)`，
     - `Check("message", "", message_text(app))`，
     - `Check("lines", expected_lines, list(app.editor.session.doc.buffer.lines))`
       （新键不会造成意外编辑），
     - `Check("no_placeholder", False, "no documentation" in plain_text(app).lower())`。
   - `"hover_docs_non_drag_mouse_move_is_not_consumed"`：
     启用 `support_mouse`，通过视图的 `handle_mouse` 路径投递一个非拖拽 `MouseMove`
     （或按 `tests/test_app_mouse.py` 的模式使用 `pilot` 鼠标事件）；断言事件处理器返回 `False`、
     光标/缓冲区不变、不出现卡片、不写入任何消息。增加第二阶段，设置 `support_mouse=False`，断言悬停回调未被调用
     （若 harness 允许，用计数器对
     `app.editor.hover.on_mouse_move` 打 monkeypatch；
     否则只断言可观察状态：卡片关闭、无消息）。
   - 不启动真实 LSP 服务器（harness 将其禁用）；这些场景刻意检验
     **AC5 静默路径**和 **AC2/AC3 的按键与鼠标接线**，而非真实的悬停载荷。
2. `tools/smoke_test/scenarios/__init__.py`：将
   `from tools.smoke_test.scenarios.hover import SCENARIOS as _HOVER` 加入
   导入块（`:13-36`），并将 `_HOVER` 加入 `SCENARIOS` 聚合列表
   （`:51-76`），保持现有顺序约定（插入在 `_COMPLETION` 条目附近）。仅当模块列出了这些别名时才更新 `__all__`。
3. 不改动任何现有场景、harness、`edit.py` 的 `ctrl+k` 断言或任何产品代码。

## 验收命令

```powershell
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m pytest tests/test_hover_docs.py tests/test_hover_integration.py -q -n 1
```

两条命令的退出码均为 0；冒烟测试必须报告全部场景通过（基线数量加 2）。若某场景在 `--jobs 4` 下失败，先用 `--jobs 1` 复跑再下结论；真实的时序假设必须在场景中修复，不得记录为 flake。

## 风险与回滚

- 风险：无头 Textual 可能不会把 `f7` 合成为 `\x1b[18~`。若场景显示按键未被分发，记录观察到的 `event.key` / 来自 `keyproto.event_to_raw` 的原始映射，上报该偏离，并在所有地方使用同一个公开按键常量 —— 绝不再添加第二处硬编码按键字符串。
- 风险：若挂载被延迟，`new_app()` 可能不暴露 `editor.hover_popup`。在第一次断言前使用 `wait_until(pilot, lambda: app.editor.hover_popup.is_mounted)`。
- 风险：鼠标阶段可能需要视图引用；几何计算参照 `tests/test_app_mouse.py::_mouse_app`，不要另造辅助函数。
- 回滚：回退此提交；没有其他计划依赖冒烟测试。
