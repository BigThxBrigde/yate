# 计划 h —— 接线、架构守卫与集成（波次 4）

父计划：[overview.md](overview.md) · 主计划：[../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)，§6
依赖：全部波次 1-3 的计划，尤其是计划 g 的 `HoverFlows.__init__` 签名和 `HoverPopup(id=...)`。

## 输入（精确的基线位置）

- `yate/editor.py:101-139`（类属性）、`:164-175`（装配顺序）、`:327-336`（`on_mount` 中挂载 popup）、`:484-488`（`_refresh_lsp`）、`:500-506`。
- `yate/editor_compose.py:125-142`（`_build_widgets`、`CompletionPopup()`）、`:213-241`（`_build_pane_stack`、`MouseFlows(...)`）、`:295-330`（`LspSync` / `CompletionFlows` 的构造）。
- `yate/editor_dispatch.py:40-51`（`_handle_key` 入口）、`:189-197`（`_cancel_mouse_state`）。
- `yate/flows/mouse_flows.py:28-58`, `:60-67`, `:69-134`.
- `yate/actions.py:26-32`、`:209-238`（view 组）。
- `tests/test_architecture.py:141`（`_LAYER_RANKS`）、`:198`（`UI_FROZEN_FILES`）、`:360`（`SIZE_EXEMPT_FILES`）、`:436`（`SCROLLABLE_BASES`）、`:1556-1597`（R15 守卫）。
- `tests/conftest.py:311-331`（`wait_until`）、`:334-344`（`plain_text` / `message_text`）、`:347-377`（`make_key_ui` / `make_action_context`）。
- `tests/test_action_table.py:20-135`（`_StubEditor` 钩子列表）。

## 独占文件

- `yate/editor.py`
- `yate/editor_compose.py`
- `yate/editor_dispatch.py`
- `yate/flows/mouse_flows.py`
- `yate/actions.py`
- `tests/test_architecture.py`
- `tests/test_hover_integration.py`（新建）
- `tests/test_app_mouse.py`
- `tests/test_action_table.py`
- `tests/test_editor_dispatch.py`
- `tests/test_dispatch_guards.py`

`.trae/rules/architecture-boundaries.md` **不在**本计划的改动范围内：新增守卫用例后（架构用例 37 → 38），主代理会在第 7 步（文档回写）中用实测数字更新该规则的 §六 计数/表格。

## 具体改动

### 1. `yate/editor.py`

- `:101-139`：在 `completion_popup` / `completion` 旁添加 `hover_popup: HoverPopup` 和 `hover: HoverFlows`；在顶部与现有的分组绝对导入一起添加这两个导入（不新增向上的边：Editor 是 L3）。
- `:164-175`：在装配顺序注释中补充 "hover flows are built
  after `panes` and before `mouse_flows`, which receives its `on_mouse_move`
  callback"。
- `:336`：在 `await self.editor_col.mount(self.completion_popup)` 之后添加
  `await self.editor_col.mount(self.hover_popup)`。两次独立的 await 保持现有的挂载语义。
- **不要**添加任何 `def apply_theme` / `.styles.background` 绘制代码（T2），也不要在悬停路径中调用 `lsp.notify_edit`（AC6）。

### 2. `yate/editor_compose.py`

- `_build_widgets`（`:138`）：`ed.hover_popup = HoverPopup(id="hover-docs")`
  （R9：id 由 dispatch 层提供；在 `hover-popup.tcss` 中固定）。
- `_build_pane_stack`：在 `ed.panes = PaneManager(...)`（`:225-231`）之后、
  `ed.mouse_flows = MouseFlows(...)`（`:233`）之前，构造

  ```python
  ed.hover = HoverFlows(
      spawn=ed.app.run_worker,
      lsp=ed.lsp,
      session=ed.session,
      panes=ed.panes,
      popup=ed.hover_popup,
      has_modal_screen=ed.has_modal_screen,
  )
  ```

  然后将 `on_hover_move=ed.hover.on_mouse_move` 传入 `MouseFlows(...)`。
  更新工厂函数的 docstring（`:213-222`），列出 `HoverFlows`。
- 任何 flow 中都不保存 App 句柄（守卫 `test_flow_modules_hold_no_app_handle`）。

### 3. `yate/flows/mouse_flows.py`

- `__init__`（`:28-41`）：将
  `on_hover_move: Callable[[Pos | None], None] | None = None` 作为**最后一个**带默认值的参数添加，使现有的所有直接构造仍然可用；保存它。从 `yate.editor_core.buffer`（L0）导入 `Pos`。
- 添加 `_notify_hover(self, pos: Pos | None) -> None`，在回调存在时调用它（普通 `Callable`，不用 protocol）。
- `handle_view_mouse` 的门控分支（`:45-49`）：在返回 `False` 前调用 `_notify_hover(None)`，使关闭 `support_mouse` 时移除可见卡片。
- `_on_move`（`:96-106`）：当**未在拖拽**时（`not self._dragging or
  event.button != LEFT_BUTTON`），计算
  `pos = view.buffer_pos_from_mouse(event)`，调用 `_notify_hover(pos)`，并
  `return False` —— 事件保持未被消费（AC3 / "不改变既有鼠标行为"）。
  在拖拽分支的开头调用 `_notify_hover(None)`。
- `_on_down`、`_on_up`、`_on_click` 和 `cancel_drag`：在各自现有逻辑之前调用 `_notify_hover(None)`（编辑交互会关闭卡片）。保持所有现有返回值和刷新调用不变。

### 4. `yate/editor_dispatch.py`

- `_handle_key`（`:40-52`）：在模态屏守卫之后，添加一行幂等的 `ed.hover.dismiss()`。它**不得** `return`，也不得消费按键：每个键都保持现有的分发路径（R10、AC6、"卡片不吞键"）。这一处即可覆盖光标移动、编辑键和 `Esc`。
- 若 `tests/test_editor_dispatch.py` / `tests/test_dispatch_guards.py` 构造了 stub editor，则为该 stub 添加一个带空操作 `dismiss()` 的 `hover` 对象 —— 不要在生产代码中引入 `getattr` 回退。

### 5. `yate/actions.py`

- 在 view 组（`:209-236`）中添加
  `reg("show_hover_docs", lambda ctx: editor.hover.request_at_cursor(),
  "Show API documentation at cursor")`。
- `tests/test_action_table.py`：在 `_StubEditor` 记录的钩子列表中加入 `hover`（一个带 `request_at_cursor` 的记录用替身），并添加测试 `test_show_hover_docs_action_forwards_to_hover_flows`，断言 `registry.execute("show_hover_docs", ctx) is True` 且调用次数为 1。

### 6. `tests/test_architecture.py`

- `UI_FROZEN_FILES`（`:198`）：添加 `yate/flows/hover_flows.py` 实际导入的 L2 模块集合，例如
  `"flows/hover_flows.py": {"yate.editor_components",
  "yate.editor_components.hover_popup", "yate.editor_components.view",
  "yate.editor_components.theme", "yate.editor_components.panes"}` —— 将该集合收敛为实际导入项；R11 禁止更宽的白名单。
- 添加 `test_hover_key_is_shared_and_identical`：用 AST 断言
  `yate/keymaps/vsc.py` 和 `yate/keymaps/vim.py` 各自在 `build_bindings` 中引用
  `HOVER_DOC_KEY`，且不包含字面量 `"<f7>"`；
  运行时断言 `VscKeymap().lookup(parse_key(HOVER_DOC_KEY))` 和
  `VimKeymap().lookup(...)` 均解析为 `show_hover_docs`。这样单边改动按键就会让架构门禁失败（AC2）。
- 不要改动 `_LAYER_RANKS`、`SIZE_EXEMPT_FILES`、`UPWARD_EDGES_FROZEN` 或 `SCROLLBAR_EXEMPT`。预期架构测试结果：**38 项通过**（37 + 1）。

### 7. `tests/test_hover_integration.py`（新建）

使用 Textual pilot（`app.run_test()`）、按 `tests/test_app_lsp.py` 的方式注入的假 READY LSP 客户端、`wait_until` 等待异步 worker，并用 `plain_text`/`message_text` 辅助函数做 UI 输出断言。不使用真实服务器（`tests/conftest.py:41` 强制 `YATE_PYTHON_LSP=off`）。

| 测试 | 安排 / 执行 | 断言 |
| --- | --- | --- |
| `test_f7_shows_hover_docs_in_vsc_keymap` | 伪造带签名 + docstring 的悬停载荷，`pilot.press("f7")` | `app.editor.hover_popup.is_open is True`，且正文包含 Markdown 文本 |
| `test_f7_shows_hover_docs_in_vim_keymap_after_ctrl_slash_toggle` | `pilot.press("ctrl+/")`，然后 `pilot.press("f7")` | 同一张卡片；`app.editor.keymaps.active.name == "vim"` |
| `test_null_hover_result_has_zero_ui_output` | 假对象返回 `None` | 卡片关闭，`message_text(app) == ""`，状态栏文本快照不变，`plain_text(app)` 不变 |
| `test_empty_whitespace_and_empty_array_results_have_zero_ui_output` | 参数化载荷 `{}`、`"  "`、`[]` | 上述三项断言相同 |
| `test_failed_and_timed_out_requests_are_silent` | 假对象抛错 / 永不解析（打补丁为极小超时） | 上述三项断言相同 |
| `test_card_is_cleared_when_a_later_result_is_empty` | 第一个载荷有文档，第二个为 `None` | 第二次 `f7` 后，`is_open is False`，消息/状态无变化 |
| `test_typing_dismisses_card_without_swallowing_key` | 卡片可见，`pilot.press("x")` | 卡片关闭**且** `x` 被插入缓冲区（vsc） |
| `test_escape_dismisses_card_and_keeps_existing_behavior` | 卡片可见，`pilot.press("escape")` | 卡片关闭；现有的 clear_selection/keymap 行为不变 |
| `test_hover_does_not_start_server_or_open_document` | 无 READY 客户端，对 `ensure_client` / `on_document_shown` 打 monkeypatch 使其失败 | `pilot.press("f7")` 不显示任何内容，且两个方法均未被调用 |
| `test_switching_buffer_drops_stale_hover_response` | 延迟响应，在解析前切换标签页 | 旧文档不出现卡片 |
| `test_cursor_move_drops_stale_keyboard_response` | 延迟响应，在解析前移动光标 | 不出现卡片 |
| `test_support_mouse_off_disables_hover_and_keeps_mouse_behavior` | `:set support_mouse off`（或构造该选项关闭的配置），投递一个非拖拽 `MouseMove` | `request_hover` 调用次数为 0，缓冲区不变，事件未被消费 |
| `test_support_mouse_on_non_drag_move_triggers_debounced_hover` | 防抖打补丁为 0，在符号上触发 `MouseMove` | 一次请求；卡片显示文档 |
| `test_non_drag_mouse_move_is_not_consumed` | 直接以一次 move 调用 `MouseFlows.handle_view_mouse` | 返回 `False`（现有行为），未调用 `event.stop` |
| `test_bind_key_both_retargets_hover_action_in_both_keymaps` | `ExtensionAPI.bind_key(..., keymap="both")` 使用新键（使用 `tests/test_extensions.py` 中的 fixture） | `vsc` 和 `vim` 均将新键解析为 `show_hover_docs`；旧键不再如此 |

### 8. `tests/test_app_mouse.py`

添加 `test_non_drag_mouse_move_keeps_existing_selection_and_cursor_behavior`（无悬停卡片、光标不变、无刷新风暴），守卫新的回调注入没有改变既有鼠标契约。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_hover_integration.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_app_mouse.py tests/test_action_table.py tests/test_editor_dispatch.py tests/test_dispatch_guards.py tests/test_architecture.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_hover_integration.py tests/test_architecture.py -q -n auto
```

所有命令退出码均为 0；最后一条检查并行/类 CI 路径。任何 flake 都必须用 `-n 1` 复跑并修复测试，不得姑息。主代理的波次 4 门禁还运行完整 pyright。

## 风险与回滚

- 风险：每个按键都执行 `ed.hover.dismiss()` 会不会使同一次 `f7` 按下所启动的在途请求失效？不会 —— dismiss 在动作执行**之前**运行；动作随后递增一个全新的 token。`test_f7_shows_hover_docs_in_vsc_keymap` 已覆盖。
- 风险：在无头 Textual 中 `pilot.press("f7")` 可能不会产生 `\x1b[18~`。`key_codec._NAMED_KEYS` 对其做了映射；若 pilot 使用了不同的拼写，先通过 `event_to_raw` 断言，并在调整测试前用实际的事件键上报这一偏离。
- 风险：`hover_flows.py` 中新增的 `editor_components` 导入在白名单条目落地前会导致 R11 失败 —— 两者都在本计划内，须保持同步。
- 风险：架构计数变为 38；主代理必须在第 7 步把真实数字回写到 `architecture-boundaries.md` §六。
- 回滚：回退这一波次的单个提交；波次 5 的冒烟测试是唯一的消费方。
