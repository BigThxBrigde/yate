# support-mouse plan-c：文本区鼠标 + keymap 协同（wave-2）

输入：overview.md 调研结论 §文本区坐标与选区映射要素、§Textual 运行时事实；
plan-a 产物 `config.support_mouse`；plan-b 产物 `pane-sep-h/v` 边框契约与
`PaneHost` 分隔拖拽。issue IKJRFK 需求 1（vsc/vim 双 keymap、vim
normal/visual/insert 协同）与需求 3 的文本区部分。

## 一、事件通路选型（定案与否决理由）

**选定：EditorView 转发 + 新 L3 流程模块 `flows/mouse_flows.py` 派发**。
EditorView 保持其 docstring 声明的角色（"pure renderer … forwards every
key to the editor"，`yate/editor_view/editor.py:124-131`）：它提供几何
换算并转发鼠标事件；跨协作者的操作（vim 模式迁移、选区语义、全 UI 刷新）
归 `MouseFlows`（`*Flows` 命名，§三.8 接入清单逐项满足）。

否决的备选：

1. **EditorView 内直接实现全部行为**：点击→光标是单协作者，但 visual
   退出、状态条刷新横跨 keymap + chrome，塞进 L2 组件违反分层职责表
   （"Editor 只新增横跨多个协作者的操作"）。否决。
2. **复用 `handle_key` 通路把鼠标伪造按键**：鼠标无键弦（keyproto 键弦
   模型不含鼠标），伪造 key 名会污染 keymap 表与 R10 派发语义。否决。
3. **不加 flow 模块、方法堆在 Editor 上**：editor.py 已 907 行（豁免
   名单），§三.8 明确"单一流程已拆成独立模块"为自检项。否决。

选区写入**复用 `TextBuffer.set_cursor(pos, select=...)`**
（`yate/editor_core/buffer.py:327-342`）：与 shift+方向键 / vim motion
同一条路径，不另立选区状态（overview §调研已证 anchor 即选区）。

### 事件 ↔ 语义映射（定案）

| 事件（Textual） | 条件 | 行为 |
|---|---|---|
| `MouseDown` button=1 | — | 焦点到该 view（激活窗格）；vim visual → 退出；光标移到命中位（`select=event.shift` 支持 shift 扩展选区）；`capture_mouse()` |
| `MouseMove` button=1 | 拖拽中 | `set_cursor(pos, select=True)`（press 后 anchor=press 位 → 字符选区） |
| `MouseUp` | 拖拽中 | 结束拖拽，刷新 |
| `Click.chain==2` | 双击 | 选词（`word_span`） |
| `Click.chain>=3` | 三击 | 选行（0..len(line)） |
| `MouseDown` 其他按键 | — | 不消费，冒泡（滚动条/后续用） |

insert 模式点击：`mode` 不动、只移光标（无 keymap 调用）；
vsc keymap 无模式态，点击即移光标——两条 keymap 天然"都开放"（需求 1）。

### 架构边界标注（R 条款与守卫）

- **R11**：`flows/mouse_flows.py` import `yate.editor_view.editor` →
  登记 `tests/test_architecture.py` 的 `UI_FROZEN_FILES`（本计划 §二.6）。
- **§三.8 接入清单**：命名 `MouseFlows`；editor.py 声明类属性；
  `_build_pane_stack` 工厂构造注入；不持有 App 句柄（守卫
  `test_flow_modules_hold_no_app_handle` 自动覆盖）；更新组装顺序注释。
- **R2/R6/命名守卫**：无新 Protocol、无 TYPE_CHECKING、`*Flows` 合名。
- **R10 同源约束**：消费的事件在 EditorView 侧 `event.stop() +
  prevent_default()`，未消费的放行（不许无条件吞）。

## 二、具体修改（定位到行号）

### 1. `yate/editor_core/buffer.py`：`word_span` 纯函数（置于 `word_end`（79 行）之后）

```python
def word_span(line: str, col: int) -> tuple[int, int]:
    """The (start, end) char span of the word at *col*.

    A non-word character or an out-of-range column yields an empty span
    ``(col, col)`` -- double-clicking whitespace moves the cursor without
    inventing a selection.  Word membership follows :func:`_is_word`.
    """
    if not 0 <= col < len(line) or not _is_word(line[col]):
        return (col, col)
    return (prev_word_start(line, col), word_end(line, col))
```

（buffer.py 在 800 行豁免名单内，新增约 10 行；执行时先核对 `_is_word`
的 46-48 行语义再写 docstring。）

### 2. `yate/keymaps/vim.py`：`drop_visual`（置于既有模式迁移辅助附近，约 350-370 行区）

```python
def drop_visual(self) -> None:
    """Leave visual mode back to NORMAL (a mouse click ends the selection).

    The anchor itself is cleared by the caller's following cursor move
    (:meth:`~yate.editor_core.buffer.TextBuffer.set_cursor` with
    ``select=False``), keeping this method free of buffer knowledge.
    """
    if self.mode in (VimMode.VISUAL, VimMode.VISUAL_LINE):
        self.mode = VimMode.NORMAL
```

### 3. `yate/flows/mouse_flows.py`（新文件，约 130 行）

```python
"""Mouse flows: text-area cursor moves, drag & click-chain selection.

Dispatches the mouse events forwarded by :class:`~yate.editor_view.editor.EditorView`
(mouse analogue of the key dispatch): single click positions the cursor,
left-button drag makes a characterwise selection, double/triple click
selects the word/line under the pointer, and a click ends vim visual
mode.  Selection state stays in the buffer (``set_cursor``), exactly like
the keyboard paths.  Constructed by the editor; never imports upward.
"""

from __future__ import annotations

from collections.abc import Callable

from textual.events import Click, MouseDown, MouseMove, MouseUp, MouseEvent

from yate.config import YateConfig
from yate.editor_core.buffer import word_span
from yate.editor_view.editor import EditorView
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap
from yate.logs import tracing
from yate.flows import MessageFn
from yate.session import EditorSession

log = tracing.get_logger(__name__)


class MouseFlows:
    """Mouse dispatch for editor views (one shared pointer, so the drag
    state lives here rather than per view)."""

    def __init__(
        self,
        session: EditorSession,
        keymaps: KeymapSet,
        config: YateConfig,
        refresh: Callable[[], None],
        message: MessageFn,
    ) -> None:
        self.session = session
        self.keymaps = keymaps
        self.config = config
        self._refresh = refresh
        self._message = message
        self._dragging: bool = False

    def handle_view_mouse(self, view: EditorView, event: MouseEvent) -> bool:
        """Dispatch one mouse event over *view*; ``True`` when consumed."""
        if not self.config.support_mouse:
            return False
        if isinstance(event, MouseDown):
            return self._on_down(view, event)
        if isinstance(event, MouseMove):
            return self._on_move(view, event)
        if isinstance(event, MouseUp):
            return self._on_up(view, event)
        if isinstance(event, Click):
            return self._on_click(view, event)
        return False

    def _on_down(self, view: EditorView, event: MouseDown) -> bool:
        if event.button != 1:
            return False
        keymap = self.keymaps.active
        if isinstance(keymap, VimKeymap):
            keymap.drop_visual()
        pos = view.buffer_pos_from_mouse(event)
        if pos is None:
            return False
        view.buffer.set_cursor(pos, select=event.shift)
        view.content_changed()
        self._refresh()
        self._dragging = True
        return True

    def _on_move(self, view: EditorView, event: MouseMove) -> bool:
        if not self._dragging or event.button != 1:
            return False
        pos = view.buffer_pos_from_mouse(event)
        if pos is not None:  # outside the text area: keep the drag alive
            view.buffer.set_cursor(pos, select=True)
            view.content_changed()
            self._refresh()
        return True

    def _on_up(self, view: EditorView, event: MouseUp) -> bool:
        if not self._dragging:
            return False
        self._dragging = False
        self._refresh()
        return True

    def _on_click(self, view: EditorView, event: Click) -> bool:
        if event.chain < 2:
            return False  # single click handled at mouse-down
        pos = view.buffer_pos_from_mouse(event)
        if pos is None:
            return False
        row, col = pos
        line = view.buffer.lines[row]
        start, end = word_span(line, col) if event.chain == 2 else (0, len(line))
        if end <= start:
            view.buffer.set_cursor(pos)
        else:
            view.buffer.set_cursor((row, start))
            view.buffer.set_cursor((row, end), select=True)
        view.content_changed()
        self._refresh()
        return True
```

（`session`/`message` 当前仅记录状态用；若 pyright 报未使用属性，将
`message` 从签名移除并回填本文——构造注入宁少勿多。`EditorSession`
import 相应调整。）

### 4. `yate/editor_view/editor.py`

1. imports（12 行）：`from textual.events import Click, Focus, Key,
   MouseDown, MouseMove, MouseEvent, MouseUp, Resize`。
2. `__init__`（146-156 行）：`handle_key` 之后加参数
   `handle_mouse: Callable[[MouseEvent], bool] | None = None`
   （keyword-only 区），存储 `self.handle_mouse = handle_mouse`，
   注释：鼠标 analogue of `dispatch_key`（`None` = 不接鼠标，headless/旧测试兼容）。
3. `on_key`（289-298 行）之后新增几何与转发：

```python
def buffer_pos_from_mouse(self, event: MouseEvent) -> Pos | None:
    """Map a mouse event over this view to a clamped buffer position.

    Same geometry the renderer uses in reverse: the widget-relative y is
    translated by the scroll offset, the x by the gutter width and the
    manual horizontal scroll, then ``cell_to_char`` resolves the character
    column (tab / wide-glyph aware).  Gutter clicks clamp to column 0.
    ``None`` for an empty buffer.
    """
    buf = self.buffer
    if buf.line_count == 0:
        return None
    row = max(0, min(event.y + self.scroll_offset.y, buf.line_count - 1))
    cell = event.x - self._gutter_w() + self.scroll_col
    col = theme.cell_to_char(buf.lines[row], max(0, cell), buf.tab_width)
    return (row, col)

def _is_pane_border(self, event: MouseEvent) -> bool:
    """True when the press lands on this view's pane-separator border
    (plan-b contract: the border cell belongs to PaneHost's drag)."""
    return (
        ("pane-sep-v" in self.classes and event.x >= self.size.width - 1)
        or ("pane-sep-h" in self.classes and event.y >= self.size.height - 1)
    )

def _forward_mouse(self, event: MouseEvent) -> None:
    """R10 analogue: stop only the events the dispatcher consumed."""
    if self.handle_mouse is not None and self.handle_mouse(event):
        event.stop()
        event.prevent_default()

def on_mouse_down(self, event: MouseDown) -> None:
    if self._is_pane_border(event):
        return  # bubbles to PaneHost: separator drag owns this cell
    if event.button == 1:
        self.focus()           # on_focus -> notify_focus activates the pane
        self.capture_mouse()   # drags continue outside the widget bounds
    self._forward_mouse(event)

def on_mouse_move(self, event: MouseMove) -> None:
    self._forward_mouse(event)

def on_mouse_up(self, event: MouseUp) -> None:
    self.release_mouse()
    self._forward_mouse(event)

def on_click(self, event: Click) -> None:
    """Double/triple click arrive as Click events with chain >= 2."""
    self._forward_mouse(event)
```

注意：`release_mouse()` 在未捕获时是安全 no-op（textual/widget.py:4624）。

### 5. `yate/editor.py`（L3 接线，§三.8 清单）

1. imports：27 行扩为 `from textual.events import Key, MouseEvent`；
   flows import 区（48-56 行）加
   `from yate.flows.mouse_flows import MouseFlows`。
2. 类属性声明区（317-346 行）：加 `mouse_flows: MouseFlows`。
3. `_build_pane_stack`（191-291 行）：`ed.pane_host = PaneHost(...)`
   （209 行）之后构造：

```python
ed.mouse_flows = MouseFlows(
    session=ed.session,
    keymaps=ed.keymaps,
    config=ed.config,
    refresh=ed.refresh_ui,
)
```

并同步 `_build_pane_stack` docstring 的控制器清单（202-199 行注释提及
LspSync/OverlayFlows/ShellFlows/CompletionFlows 处追加 MouseFlows）。

4. `make_view`（397-406 行）：`handle_key=self.handle_key` 之后加
   `handle_mouse=partial(self._on_view_mouse, leaf_id)`
   （`partial` 已 import，21 行）。
5. 新方法（`handle_raw_key` 附近）：

```python
def _on_view_mouse(self, leaf_id: int, event: MouseEvent) -> bool:
    """Dispatch one mouse event for the view of *leaf_id*."""
    view = self.panes.views.get(leaf_id)
    if view is None:
        return False
    return self.mouse_flows.handle_view_mouse(view, event)
```

### 6. `tests/test_architecture.py`：`UI_FROZEN_FILES` 登记（124 行起的 dict）

```python
"flows/mouse_flows.py": {
    "yate.editor_view",
    "yate.editor_view.editor",
},
```

（R11：flows 新增 editor_view 导入必须先登记；登记即
`test_collaborators_keep_widget_coupling_frozen` 的守卫面更新。）

## 三、新增测试（详细用例）

### `tests/test_vim_keymap.py`

1. `test_drop_visual_from_visual_returns_to_normal`：夹具照本文件既有
   keymap 用例；`v` 进入 VISUAL（或直接置 `keymap.mode = VimMode.VISUAL`）；
   `drop_visual()` 后断言 `keymap.mode is VimMode.NORMAL`。
2. `test_drop_visual_from_visual_line_returns_to_normal`：同上，`V` /
   `VimMode.VISUAL_LINE` → NORMAL。
3. `test_drop_visual_from_normal_is_noop`：NORMAL 下调用后
   `mode is VimMode.NORMAL`。
4. `test_drop_visual_from_insert_is_noop`：`i` 进入 INSERT 后调用，
   `mode is VimMode.INSERT`（鼠标点击不踢出插入模式）。

### `tests/test_editor_core.py`

5. `test_word_span_returns_word_bounds`：
   `word_span("hello world", 0) == (0, 5)`、`word_span("hello world", 8) == (6, 11)`。
6. `test_word_span_non_word_char_returns_empty`：
   `word_span("a b", 2) == (2, 2)`（空格上双击不造选区）。
7. `test_word_span_out_of_range_returns_empty`：
   `word_span("abc", 10) == (10, 10)`。

### `tests/test_app_mouse.py`（新文件；harness 参照 `tests/test_app_textual.py`
的 run_test 模式 / textual-pilot-smoke 技能；目标文件用 tmp_path 写入
已知内容如 `"hello world\nsecond line\n"`）

8. `test_mouse_click_moves_cursor`：
   - 操作：`pilot.click(EditorView, offset=(gutter+5, 0))`（gutter=6：
     `gutter_width() = max(3, 2)+3 = 6`，two-line doc；x=11 落在
     "hello world" 的 cell 5）。
   - 断言：`buf.cursor == (0, 5)`；`app.editor.panes.active_view is 该view`。
9. `test_mouse_gutter_click_clamps_column_zero`：
   `pilot.click(EditorView, offset=(2, 0))` → `buf.cursor == (0, 0)`。
10. `test_mouse_drag_selects_range`：
    `pilot.mouse_down(EditorView, offset=(6, 0))` →
    `pilot._post_mouse_events([MouseMove, MouseUp], widget=EditorView,
    offset=(9, 0))` → `buf.selected_text() == "hel"`。
11. `test_mouse_double_click_selects_word`：
    `pilot.double_click(EditorView, offset=(8, 0))` →
    `buf.selected_text() == "world"`（"world" 在 cell 6..11）。
12. `test_mouse_triple_click_selects_line`：
    连击三次（`pilot.click(..., times=3)`）→ 选区覆盖整行
    `buf.selected_text() == "hello world"`。
13. `test_visual_mode_click_exits_to_normal`：vim keymap（构造时
    `keymap="vim"` 或 `:set` 切换）；`pilot.press("v")` 后点击别处 →
    `VimKeymap.mode is VimMode.NORMAL` 且 `buf.has_selection() is False`。
14. `test_insert_mode_click_moves_cursor_keeps_insert`：`pilot.press("i")`
    后点击 → 光标移动且 `mode is VimMode.INSERT`。
15. `test_click_activates_clicked_pane`：`:vsplit` 后点击下窗格 →
    `panes.active.id` 变为下方 leaf id。
16. `test_shift_click_extends_selection`：先点 A 位，再
    `pilot.click(EditorView, offset=..., shift=True)` →
    `buf.selection()` 覆盖 A..B。
17. `test_separator_border_press_bubbles_to_pane_host`（plan-b 契约钉）：
    二分窗格中点击 `pane-sep-v` 边框格 → `buf.cursor` 不变（plan-b 用例 6
    的 wave-2 侧复核）。

## 四、验证方案

| 项 | 命令 | 通过判定 |
|---|---|---|
| 单测 | `.venv\Scripts\python.exe -m pytest tests/test_app_mouse.py tests/test_vim_keymap.py tests/test_editor_core.py -q` | 退出码 0，含上述 17 用例 |
| 架构 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 25+ 守卫全绿（含 UI_FROZEN_FILES 新登记面与 `test_flow_modules_hold_no_app_handle` 对新模块的覆盖） |
| 回归 | `.venv\Scripts\python.exe -m pytest tests/test_app_render.py tests/test_app_textual.py tests/test_dispatch_guards.py -q` | 退出码 0（渲染/派发无回归） |
| 类型 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | 零诊断 |
| 手工 | 运行 yate：单击/双击/三击/拖拽；vim 模式重复一遍 | 状态条模式芯片与选区表现符合 §一映射表 |

## 五、风险与回滚

- 风险：坐标映射错位（gutter/`scroll_col`/宽字符/中文）——映射与渲染同源
  （同一 `_gutter_w`/`scroll_col`/`cell_to_char`），用例 9-12 覆盖；宽字符
  第二格点击落在字形首列（`cell_to_char` 的 `cells >= cell` 语义），可接受。
- 风险：`_on_move` 每次 `_refresh()` 的开销——`lsp.notify_edit` 版本守卫
  （`yate/editor_lsp/manager.py:379-385`）、`doc_shown_later` 早退
  （`yate/flows/lsp_sync.py:66-74`），成本与键盘移动同阶；如实测大文件
  拖拽卡顿，备选降级：`_on_move` 改为 `view.content_changed()` +
  `self._message` 不动、状态条随 MouseUp 刷新（回填本文后实施）。
- 风险：双击的第一次 MouseDown 已移光标清 anchor，Click(chain=2) 再选词
  ——净效果正确；pilot 的 `double_click` 依赖合成 chain（app.py 4086-4117），
  用例 11 即验证链路。
- 风险：架构守卫回归——`MouseFlows` 无 App 句柄、命名 `*Flows`、
  UI_FROZEN_FILES 登记与代码同提交。
- 回滚：还原 `editor_view/editor.py` + 删除 `flows/mouse_flows.py` +
  editor.py/vim.py/buffer.py 三处小改；`handle_mouse=None` 默认值保证
  未接线时零行为（前向兼容，不需要回滚测试文件）。
