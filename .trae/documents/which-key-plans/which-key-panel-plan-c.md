# which-key 子计划 c：L2 面板组件（WhichKeyPanel + 资源 tcss）

wave-1（与 plan-a、plan-b 并行，文件互不重叠）。自包含任务书。

## 输入（调研事实）

- L2 组件自持样式与主题的既有范本：[statusbar.py](../../../yate/editor_view/statusbar.py)
  `DEFAULT_CSS = load_tcss("status-bar.tcss")`（:75）、
  `theme.attach(self, self.refresh_status)`（:101-104）+ `on_unmount` detach（:106-108）；
  Rich `Text` 分段上色（:156-196）。tcss 资源统一放 `yate/resources/`
  （现有 status-bar.tcss / editor-view.tcss 等 16 个，见 resources 目录）。
- `Static` 无焦点、不处理按键（面板 R10 安全：不 stop 任何键事件）。
- 主题 API：[theme.py](../../../yate/editor_view/theme.py) 的 `theme.active()`
  / `theme.subscribe`（R13 组件自持主题的唯一通道）。
- 布局落点由 plan-e 决定：面板将组合进 L3 `Editor.compose` 的 `#bottom`
  Vertical（[editor.py](../../../yate/editor.py) :466-470），位于 statusbar 之上；
  本子计划只保证组件在任何宽度 / 高度下渲染正确。

## 目标

新建纯渲染组件 `WhichKeyPanel`：接收 ``(header, entries)`` 数据并渲染
which-key 风格网格；显示 / 清除 / 截断三种状态；自持主题；无任何按键消费。

## 非目标

- 不持有 KeymapSet、不算候选集（数据流归 plan-d 的 WhichKeyFlows）；
- 不处理鼠标 / 键盘事件；不做 yaterc 配置项。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `yate/editor_view/whichkey.py` | 新建（预计 ~150 行） |
| `yate/resources/which-key.tcss` | 新建 |
| `tests/test_whichkey_panel.py` | 新建 |

## 具体修改

### 1. [whichkey.py](../../../yate/editor_view/whichkey.py) — 新建

模块 docstring（英文）声明：面板是 which-key 的纯渲染端；数据由 L3 流程模块
推送；主题自持（R13）；不消费键事件（R10）。

```python
#: One row of the which-key grid: a display key label and its description.
@dataclass(frozen=True)
class ChordEntry:
    key: str          # display label, e.g. "dd" or "<ctrl-d>"
    desc: str         # short description
    category: str = ""  # group header in pinned-sheet mode

#: Maximum rendered rows before the overflow hint line.
MAX_ROWS: int = 12

class WhichKeyPanel(Static):
    """The which-key popup: pending chord header plus next-key grid.

    Pure renderer: :meth:`show_entries` receives precomputed entries from
    the L3 flow module and paints a compact grid; :meth:`clear` hides it.
    The widget never takes focus and never consumes key events (R10).
    """

    DEFAULT_CSS = load_tcss("which-key.tcss")

    _theme_unsubscribe: theme.Unsubscribe | None = None

    def __init__(self, **kwargs: Any) -> None: ...
    def on_mount(self) -> None:      # theme.attach + 初始隐藏
    def on_unmount(self) -> None:    # theme.detach
    def show_entries(self, header: str, entries: Sequence[ChordEntry]) -> None
    def clear(self) -> None          # 清空并 display: False
```

渲染规则（`show_entries` 内，Rich `Text`）：

1. 首行 header：挂起 chord 的人读序列（如 `"2d`），样式
   `bold {t.accent2}`；空 header 时该行不渲染。
2. 条目按 `category` 分组（空 category 跳过分组头），每组先渲染组名行
   （`bold {t.accent2}`），行内 `key.ljust(GRID_KEY_WIDTH=12)` + desc；
   key 用 `{t.green}`，desc 用 `{t.fg_bright}`（对齐 HelpScreen 配色，
   [modals.py:76-77](../../../yate/editor_view/modals.py)）。
3. 超过 `MAX_ROWS` 条时截断并追加一行 `… N more — F1 for the full map`
   （`t.fg_muted`）。
4. `entries` 为空且 header 非空：只渲染 header（纯 count 提示态）。
5. 全程 `self.display = True`；`clear()` 置 `display = False`。

### 2. [which-key.tcss](../../../yate/resources/which-key.tcss) — 新建

对齐 [status-bar.tcss](../../../yate/resources/status-bar.tcss) 的文件头注释
惯例（英文，注明组件自持、R9 的 id 由 Editor 传入）：

```tcss
/* WhichKeyPanel self-owned styles; the #which-key id is assigned by the
   Editor at compose time (R9). Display defaults to off: the flow module
   toggles visibility through show_entries/clear. */
WhichKeyPanel {
    display: none;
    height: auto;
    max-height: 14;
    padding: 0 1;
    background: $panel;
    border-top: solid $accent;
}
```

着色以 R13 为准：CSS 只给结构（height / padding / border），颜色仍以
`theme.active()` 在渲染时写入 Rich style（与 statusbar 同策略，避免
CSS 变量与广播双源）。

## 新增测试

### tests/test_whichkey_panel.py（新建；Textual 组件测试沿用仓库既有
`run_test()` pilot 形态）

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_show_entries_renders_header_and_grid` | 挂载 `WhichKeyPanel()` | `show_entries("2d", [ChordEntry("dd", "Delete line"), ChordEntry("{motion}", "Delete over motion")])` | 面板 `display` 为 `True`；渲染文本含 `"2d"`、`dd`、`Delete line`、`{motion}` |
| `test_clear_hides_panel` | 已 show 的面板 | `clear()` | `display` 为 `False`，文本为空 |
| `test_entries_over_max_rows_truncate_with_hint` | 构造 20 条 entry | `show_entries("", entries)` | 可见行数 ≤ MAX_ROWS；文本含 `more` 与 `F1` |
| `test_empty_entries_with_header_keeps_header` | — | `show_entries('"', [])` | `display` 为 `True` 且文本含 `"`、不含任何 key 列 |
| `test_theme_change_repaints_panel` | show 后 | 改 `theme.set_theme(...)` 广播 | 面板仍 display 且文本含 header（不抛异常即认为自持重绘路径通） |
| `test_panel_never_consumes_key_events` | 挂载后聚焦编辑区 widget | pilot 按 `x` | 事件未被面板 stop（`event.is_stopped` 为 `False` / 键到达目标 widget）——R10 守卫 |

## 验收命令

```text
.venv\Scripts\python.exe -m pytest tests/test_whichkey_panel.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pyright yate/editor_view/whichkey.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q --cov-fail-under=0
```

通过判定：退出码 0；R13 守卫（T1/T2 用例）与 R10 相关既有用例仍绿。

## 风险与回滚

- 面板高度挤压编辑区：CSS `max-height: 14` + 默认 `display: none`，最坏情况
  手工测试发现后调阈值，不影响其余布局。
- Rich 截断 / 宽字符对齐：复用 `theme.cell_len`（statusbar 既有面），不重造。
- 回滚：组件未被任何既有模块 import（plan-e 接线之前），删除两文件即完全回滚；
  无状态迁移。
