# 计划 e — 自包含的悬停卡片（波次 2，L2）

父计划：[overview.md](overview.md) · 主计划：[../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)，决策 D4

## 输入

- `yate/editor_components/completion.py:78-179`（`can_focus=False`、`DEFAULT_CSS = load_tcss(...)`、`show()`/`close()`、`styles.offset`、溢出翻转）。
- `yate/editor_components/manual.py:146-165`（`render_doc_lines` 使用 `theme.active()` 进行纯 Markdown→`Strip` 测量），`:41`（`rich.markdown`）。
- `yate/editor_components/scrollbars.py:94-130`、`yate/editor_components/theme/__init__.py:174-193`（attach/detach）、`yate/editor_components/view.py:206-228`（mount/unmount 模式）。
- `yate/paths.py::load_tcss`；以 `yate/resources/completion-popup.tcss` 作为格式先例；R9 组件自有 id、R13、R15。

## 独占文件

- `yate/editor_components/hover_popup.py`（新建）
- `yate/resources/hover-popup.tcss`（新建）
- `tests/test_hover_popup.py`（新建）

## 具体改动

1. `yate/editor_components/hover_popup.py` —— 模块 docstring 用英文
   （ASCII），`from __future__ import annotations`，然后按
   stdlib / 第三方 / `yate` 分组导入。定义：

   ```python
   class HoverPopup(VerticalScroll):
       """Non-focusable floating Markdown card for LSP hover docs."""
   ```

   - `can_focus = False`；`DEFAULT_CSS = load_tcss("hover-popup.tcss")`。
   - 常量 `MAX_ROWS: int = 12`、`MIN_WIDTH: int = 24`、`MAX_WIDTH: int = 72`，各带 `#:` 注释。
   - `compose()` 产出一个 `Static("", id="hover-docs-body")`；在 `show` 中通过 `self.query_one(...)` 保留其引用（不新增 protocol/类型）。
   - `is_open` 属性：`bool(self.display) and bool(self._text)`。
   - `show(text: str, anchor: tuple[int, int], inner_size: tuple[int, int],
     gutter: int, origin_y: int = 0) -> None`：
     - `if not text.strip(): self.close(); return`（AC5 的第二道防线）。
     - `box_w = max(MIN_WIDTH, min(MAX_WIDTH, max(theme.cell_len(line) for
       line in text.splitlines()) + 2))`；用
       `render_doc_lines(text, box_w - 2, active=theme.active())` 计算行数，
       再算 `box_h = min(MAX_ROWS, len(rows) + 2)`。
     - 水平/垂直翻转照搬 `completion.py:142-153`
       （`x = min(gutter + anchor[0], max(0, inner_size[0] - box_w))`，
       y 方向为下方放不下则改到上方），然后 `styles.width/height/offset =
       ScalarOffset.from_offset((x, y))`。
     - 用 `Markdown(text)`（Rich 可渲染对象）更新 `Static`，设置
       `display = True`，`refresh()`。
   - `close() -> None`：清空 `_text`，清空正文，`display = False`。
   - `on_mount`：`display = False`；`apply_slim_scrollbars(self)`；
     `_apply_theme()`；`theme.attach(self, self._apply_theme)`。
   - `on_unmount`：`theme.detach(self)`。
   - `_apply_theme()`：`t = theme.active()`；设置 `styles.background = t.panel`、
     `styles.color = t.fg`；`apply_scrollbar_theme(self)`；`refresh()`。
     **R13**：组件负责全部绘制；L3 代码不得触碰其样式。
   - **R15**：模块中同时包含 `apply_slim_scrollbars` 和
     `apply_scrollbar_theme` 调用，满足
     `test_scrollable_widgets_apply_theme_scrollbar_pair` 的要求。
   - 不使用 `Any`、不使用 `TYPE_CHECKING`、不使用相对导入；仅在需要 debug 日志时使用 `log = tracing.get_logger(__name__)`（延迟 `%` 格式化）。
2. `yate/resources/hover-popup.tcss` —— 头部注释："selector id frozen by
   R9: `#hover-docs`; component-owned CSS, not referenced by app.tcss"。
   为 `#hover-docs` 和 `#hover-docs-body` 编写规则，使用 Textual 主题令牌
   （`$panel`、`$foreground`、`$accent`）、`border: round $accent`、
   `padding: 0 1`、`height: auto`、`max-height`、`overflow-y: auto`；不得
   硬编码颜色。该 id 由计划 h 中的 Editor 传入。
3. 模块保持在 800 行以内（预计约 130 行）；不改动 `SIZE_EXEMPT_FILES`。

## 测试（`tests/test_hover_popup.py`）

纯几何测试尽可能使用 `tests/test_completion_popup.py:29-43` 中的无 App 构造模式，挂载/主题测试使用 `app.run_test()`。使用 `theme.active()` 快照；不做真实 sleep。

| 测试 | 安排 / 执行 | 断言 |
| --- | --- | --- |
| `test_show_with_empty_or_whitespace_text_closes_card` | 参数化 `""`、`"  \n "` | `is_open is False`，`display is False` |
| `test_show_positions_card_below_anchor` | `inner_size=(80,24)`、`anchor=(10,5)`、`gutter=6`、`origin_y=2` | `styles.offset` 解析为 `(16, 8)`（gutter+列，origin+底边） |
| `test_show_flips_above_when_bottom_overflows` | `anchor=(5, 22)`，卡片高 10 行 | 得到的 y 位于锚点上方且 `>= origin_y` |
| `test_show_clamps_x_when_card_would_overflow_right_edge` | `anchor=(78, 3)` | `x == inner_size[0] - box_w` 且 `x >= 0` |
| `test_show_renders_markdown_source_in_body` | `text = "**f()** docs"` | `query_one(...).renderable` 是一个 `Markdown`，其 `markup` 等于该文本 |
| `test_long_text_caps_card_height` | 40 行文本 | `styles.height <= MAX_ROWS` |
| `test_card_never_grabs_focus` | 构造 | `HoverPopup.can_focus is False` 且 `popup.can_focus is False` |
| `test_mount_applies_scrollbar_pair_and_theme_subscription` | 用 spy 对两个滚动条函数及 `theme.attach` 打 monkeypatch，在 pilot 中挂载 | 每个 spy 以该 popup 为参数调用一次；`attach` 收到 `popup._apply_theme` |
| `test_theme_change_repaints_scrollbar_theme` | 调用 `theme.set_theme(...)`（或直接调用 `_apply_theme()`） | `apply_scrollbar_theme` 的 spy 再次被调用，且 `styles.background` 等于 `theme.active().panel` |
| `test_unmount_detaches_theme_listener` | 挂载后卸载 | `theme.detach` 的 spy 以该 popup 为参数被调用 |
| `test_close_hides_card_and_clears_body` | 显示后关闭 | `display is False`、`_text == ""`、正文可渲染对象为空 |
| `test_architecture_scrollbar_pair_guard_covers_new_widget` | 运行 `tests/test_architecture.py::test_scrollable_widgets_apply_theme_scrollbar_pair` | 退出码 0 |

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_hover_popup.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_completion_popup.py tests/test_architecture.py -q -n 1
```

两条命令的退出码均为 0。此处的架构测试套件是对 R15/R9 在接线波次之前的特意提前检查。

## 风险与回滚

- 风险：在 Textual 8.2.8 上，`Static.update(Markdown(...))` 可能需要显式的 `rich` 可渲染对象适配。若失败，保持相同的公开 API，改为通过一个小的子 `Widget.render_line` 渲染 `render_doc_lines` 产出的 `Strip` 行；在改动设计前**必须附上失败命令的输出来上报这一偏离**。
- 风险：`scroll_offset` 单元测试依赖 `ScalarOffset` 内部实现。应针对 `popup.styles.offset.x`/`.y` 的值断言，而非字符串表示；若该值不稳定，则针对 `completion.py` 测试所用的解析后 `(x, y)` 辅助函数断言。
- 风险：主题令牌名不同（`$foreground` 与 `$text`）。从 `completion-popup.tcss` / 其他组件的 tcss 中照抄确切令牌；绝不杜撰硬编码颜色。
- 回滚：回退此提交；计划 g/h 是唯一的消费方（波次 3/4）。
