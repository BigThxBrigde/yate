# editor_view：滚动条主题化 + Tab 点击切换 实施计划

> **实施状态（2026-09-22 核对）：✅ 已实现。**
>
> - **滚动条主题化**：`EditorView.apply_scrollbar_theme()`
>   （`yate/editor_view/editor.py`，`on_mount` 中调用）写入 5 个
>   `scrollbar_*` 样式（track=border / thumb=fg_dim / hover / active=accent）；
>   `YateApp.apply_theme()` 对 `explorer_tree` 写同款色。
> - **Tab 点击切换**：`yate/app.py` 新增 `TabBar(Static)`（命中区间 +
>   `on_mouse_down`），`render_content()` 调 `YateApp.build_tabbar(width)`
>   取得 `(Text, regions)`；`compose` 中 `yield TabBar(self, id="tabbar")`，
>   `on_mount` / `update_tabbar` 已接线。
> - 与本文档命名差异：计划中的 `_apply_scrollbar_theme` 实际为公开方法
>   `apply_scrollbar_theme`；`render_tabbar` 实际为公开方法 `build_tabbar`
>   （返回 `(Text, regions)`），`TabBar.render_content` 为其调用方。

## 与当前实现的差异（回写，2026-09-22）

- **方法命名**：计划中的 `EditorView._apply_scrollbar_theme()` 实际为公开方法
  `EditorView.apply_scrollbar_theme()`（`yate/editor_view/editor.py`）；
  `YateApp.apply_theme()` 中调用它并给 `explorer_tree` 写同款 scrollbar 色。
- **TabBar 接线**：`render_tabbar` 实际为
  `YateApp.build_tabbar(width) -> tuple[Text, list[tuple[int, int, int]]]`；
  `TabBar`（`yate/app.py`）的 `render_content()` 调用它并保存命中区间，
  `on_mouse_down` 完成点击切换。
- **Repository Research 中的行号已漂移**（如 `editor.py:48`、
  `app.py:1647/1662` 等），以当前代码为准。
- 其余设计（色值选择、命中区间复用 `cell_len` 宽度、`event.stop()`）与实现一致。

## 需求

1. **滚动条样式与主题不符**：`EditorView`（`ScrollView`）的垂直滚动条使用 Textual 默认颜色，未随 Catppuccin 主题切换，视觉割裂。
2. **Tab 无法点击切换**：当前支持鼠标（滚轮），但 `#tabbar` 是纯文本 `Static`，没有点击命中处理，无法点击切文档。

## Repository Research（现状结论）

- 唯一运行依赖 `textual>=8.0`。`EditorView(ScrollView)` 位于 `yate/editor_view/editor.py:48`，滚动条由 Textual 框架自动绘制，项目内**无任何 `scrollbar-color` / `scrollbar-background` 样式**。
- 主题是进程全局状态：`theme.active()` 返回 `Theme` dataclass（`yate/editor_view/theme.py:30`），含 `border`（分隔线）、`surface`、`fg_dim`/`fg_muted`/`fg_bright`、`accent`/`accent2` 等适合做滚动条的色值。主题色在 `app.apply_theme()`（`app.py:536`）和各 widget 的 `on_mount` 中**以编程方式**写入 `styles`，而非静态 CSS。
- `#tabbar` 是 `Static`（`app.py:1647` 产出、`1662` 绑定），`render_tabbar()`（`app.py:1523`）拼扁平 Rich Text；每个 tab 的 cell 宽度 `seg_cells` 已算出但**丢弃了边界**，没有命中表。
- 文档切换入口已存在：`_activate_doc(doc)`（`app.py:283`），`cycle_tab`/`close_tab` 等皆调用它。
- 项目内唯一鼠标处理是 `terminal.py` 的 `on_mouse_scroll_up/down`；**无 `on_mouse_down` 先例**，但 Textual 的 `MouseDown` 事件会派发到光标下的 widget（无需 `can_focus`），命中后 `event.stop()` 阻止冒泡即可。
- Tab 栏样式：活动 tab 背景 `t.bg`（与编辑器融合），非活动 tab 背景 `t.panel`。滚动条出现在编辑器右侧，应与 `EditorView` 同色系。

## 设计

### 一、滚动条主题化

**策略**：沿用项目"编程式写 styles"惯例，在 `apply_theme()` 中给所有 `EditorView` 写入滚动条色；同时 `EditorView.on_mount` 兜底写一次（防止 apply_theme 在 widget 未挂载时被跳过）。

**色值选择**（Catppuccin 语义化）：

| Scrollbar 部件 | CSS 属性 | 主题色 | 说明 |
|---|---|---|---|
| 轨道（track） | `scrollbar_background` | `t.border` | 极浅分隔色，几乎隐身 |
| 滑块（thumb） | `scrollbar_color` | `t.fg_dim` | 注释灰，低调可辨 |
| 滑块 hover | `scrollbar_color_hover` | `t.fg_muted` | 稍亮 |
| 滑块 active | `scrollbar_color_active` | `t.accent` | 拖动时高亮为强调色 |
| 轨道 hover | `scrollbar_background_hover` | `t.surface` | 悬停时轨道略提亮 |

- 尺寸保持 Textual 默认（1 cell），不设 `scrollbar_size`，避免在窄终端挤压内容。
- `ExplorerTree`（`Tree`，也是 ScrollView）的滚动条一并主题化，保持侧边栏与编辑器一致；在 `apply_theme` 中对 `self.explorer_tree` 同样写入。

**代码落点**：

`editor_view/editor.py` — `EditorView.on_mount` 追加：
```python
def on_mount(self) -> None:
    self.styles.background = theme.active().bg
    self._apply_scrollbar_theme()

def _apply_scrollbar_theme(self) -> None:
    t = theme.active()
    s = self.styles
    s.scrollbar_background = t.border
    s.scrollbar_background_hover = t.surface
    s.scrollbar_color = t.fg_dim
    s.scrollbar_color_hover = t.fg_muted
    s.scrollbar_color_active = t.accent
```

`app.py` — `apply_theme()` 在遍历 views 时调用 `view._apply_scrollbar_theme()`；并对 `self.explorer_tree` 写同款色（`Tree` 的 styles 同样支持 scrollbar 属性）。

### 二、Tab 点击切换

**策略**：不重构为 `Button` 容器（会改变 VS Code 风格扁平外观），保留 `Static` 渲染，新增**命中表** + `on_mouse_down` 命中检测。

**新增 `TabBar(Static)` 类**（放 `app.py`，与 `StatusBar` 同级，避免新建模块）：

```python
class TabBar(Static):
    """Flat VS Code-style tab bar with click-to-switch support."""

    def __init__(self, yate: YateApp, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.yate = yate
        # [(start_cell, end_cell, doc_index), ...] for the last render
        self._regions: list[tuple[int, int, int]] = []

    def render_content(self, width: int) -> None:
        """Rebuild text and hit-test regions; called by app.update_tabbar."""
        text, regions = self.yate._build_tabbar(width)
        self._regions = regions
        self.update(text)

    def on_mouse_down(self, event: MouseDown) -> None:
        x = event.x  # cell column relative to this widget
        for start, end, doc_idx in self._regions:
            if start <= x < end:
                if doc_idx != self.yate.doc_index:
                    self.yate._activate_doc(self.yate.docs[doc_idx])
                    self.yate.ui_refresh()
                event.stop()
                return
```

**改造 `render_tabbar` → `_build_tabbar`**：返回 `tuple[Text, list[tuple[int, int, int]]]`。在现有循环里记录每个 tab 的 `[used, used+seg_cells)` 区间与 `doc_index`（即循环变量 `i`）。末尾填充空格不计入 regions。

**接线**：
- `compose`：`yield TabBar(self, id="tabbar")`。
- `on_mount`：`self.tabbar = self.query_one("#tabbar", TabBar)`。
- `update_tabbar`：改为 `self.tabbar.render_content(self.tabbar.size.width or 80)`，背景仍设 `t.panel`。
- `apply_theme` 中 `update_tabbar()` 调用不变（内部走新方法）。

**注意**：`event.x` 是相对 widget 左上角的 cell 坐标，`#tabbar` 高 1，`y` 恒为 0，无需判 y。`MouseDown` 需在 `app.py` 顶部 `from textual.events import MouseDown`。

## 文件清单

**修改**
- `yate/app.py`：新增 `TabBar` 类 + `MouseDown` 导入；`compose`/`on_mount`/`update_tabbar`/`apply_theme` 接线；`render_tabbar` 重构为返回 `(text, regions)` 的 `_build_tabbar`。
- `yate/editor_view/editor.py`：`EditorView` 新增 `_apply_scrollbar_theme`，`on_mount` 调用。
- `tests/test_app_textual.py`：新增 tab 点击与滚动条主题断言的 pilot 测试（可选，若 pilot 难以断言样式则至少断言点击后 `doc_index` 变化）。

## 实施步骤

1. **滚动条主题化**（低风险，独立）
   - `editor.py` 加 `_apply_scrollbar_theme` + `on_mount` 调用。
   - `app.apply_theme` 遍历 views 时调 `_apply_scrollbar_theme`，并给 `explorer_tree` 写 scrollbar 色。
   - 手测：切换 4 种主题，滚动条颜色跟随。
2. **Tab 点击切换**
   - `app.py` 导入 `MouseDown`，新增 `TabBar` 类。
   - `render_tabbar` 改名为 `_build_tabbar` 并返回 regions；`update_tabbar` 调 `tabbar.render_content`。
   - `compose`/`on_mount` 换用 `TabBar`。
   - 手测：多文档下点击任意 tab 切换，点击空白区无反应。
3. **测试 + 收尾**：补 pilot 测试；跑 `pyright` 与 `pytest` 全绿。

## 验证

- `.venv\Scripts\python.exe -m pyright` → 0 errors。
- `$env:PYTHONDONTWRITEBYTECODE='1'; .venv\Scripts\python.exe -m pytest tests -q` → 全绿。
- 手测：mocha / latte / frappe / macchiato 四主题下编辑器与资源管理器滚动条配色协调；多 tab 环境点击非活动 tab 立即切换，活动 tab 点击无副作用，点击 tab 间空白不触发。

## 风险与处理

- **`MouseDown` 未派发到 `Static`**：若 Textual 要求 widget 可聚焦才收鼠标事件，给 `TabBar.can_focus = False` 不变（鼠标事件与焦点无关）；若仍不触发，改在 `YateApp.on_mouse_down` 中判断 `event.target is self.tabbar`。先按 widget 级 handler 实现，失败再回退到 app 级。
- **命中区间与渲染字符宽度不一致**：`render_tabbar` 已用 `theme.cell_len` 计算显示宽度，regions 直接复用 `used`/`seg_cells`，与渲染逐 cell 对齐，宽字符/CJK 不受影响（icon 为 Nerd Font 单宽字符）。
- **滚动条 CSS 属性名**：Textual 8.x 的 `styles` 属性为 `scrollbar_background` / `scrollbar_color` 及其 `_hover`/`_active` 变体；若某变体不存在（老版本 Textual 无 hover/active），用 `getattr` 防御或只设基础两项，避免 AttributeError 崩溃。
- **主题切换时 explorer_tree 未挂载**：`apply_theme` 已有 `if self.explorer_tree is not None` 守卫，复用即可。