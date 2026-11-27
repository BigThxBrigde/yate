# 计划 c — 通用 LSP 选择器组件（波次 2）

父计划：[../lsp-navigation-plan.md](../lsp-navigation-plan.md)。

## 输入 / 输出

输入：`editor_components/marks_palette.py:59-119` 的浮层模式，issue AC1/AC3/AC4/AC6。
输出：一个由纯数据 + 回调驱动的可复用 L2 选择器界面。

## 独占文件

- `yate/editor_components/lsp_chooser.py`（新增）
- `tests/test_lsp_chooser.py`（新增）

不要修改 `marks_palette.py`、`modals.py` 或任何流程模块。

## 具体改动

### `editor_components/lsp_chooser.py`

- 模块 docstring：说明这是一个用于展示 LSP 结果的只读 L2 选择器，由注入的
  行/回调驱动；不持有 App 句柄，不保存 LSP 状态（R3/R13）。
- `from __future__ import annotations`，仅使用绝对导入。
- `@dataclass(frozen=True) class LspRow`，字段为：
  `label: str`、`detail: str`、`uri: str`、`row: int`、`col: int`、
  `end_row: int`、`end_col: int`、`kind: str`。位置从 0 开始。
- `class LspChooserScreen(OverlayScreen)`（来自 `yate.editor_components.modals`）：
  - `__init__(self, rows: list[LspRow], title: str, on_pick: Callable[[LspRow], None]) -> None`。
  - `BINDINGS = [("enter", "pick", "select row")]`。
  - `compose()` 产出 `Static(id="overlay-body")`，以及 `OverlayScroll(id="overlay")`
    内的一个 `.hint` Static（与 `marks_palette.py:85-89` 的 id 相同；
    组件自有，不改 shell CSS，R9 先例）。
  - `on_mount()` 绘制一次并调用 `theme.attach(self, self._paint)`；
    `on_unmount()` 调用 `theme.detach(self)`（R13）。共享的 `OverlayScreen`
    基类已经接好了细滚动条（R15）—— 不要再加第二层类级补丁。
  - `on_key(event: Key)`：只消费上/下键，消费后调用 `event.stop()` +
    `event.prevent_default()`（R10）；选择可循环。
  - `_body_text() -> Text`：带有 *title* 的头部，随后是格式化为
    ` > {label:<32} {detail:<20} {file}:{line+1}` 并套用主题样式的行；空行时
    渲染 `"  (no results)"`。文件名用 `uri_file_name(uri)` 取得。
  - `action_pick()`：调用 `self._on_pick(rows[self._selected])` 并 `dismiss()`。
  - 为测试暴露 `selected_row` 属性。

不新增 `.tcss` 文件：`OverlayScreen` 拥有冻结的 `#overlay` id 和样式。

## 测试（`tests/test_lsp_chooser.py`）

- `test_lsp_chooser_renders_label_detail_and_location`：两个 `LspRow`；挂载后，
  `#overlay-body` 文本包含两个 label 以及 `a.py:3` 和 `b.py:7`。
- `test_lsp_chooser_enter_calls_on_pick_with_selected_row`：向下移动，按回车，
  断言回调收到第二行且界面被关闭。
- `test_lsp_chooser_up_down_wraps_and_stops_event`：从第 0 行按上键 -> 选中最后一行；
  断言 `event.stop` / `prevent_default` 被调用（桩 Key）。
- `test_lsp_chooser_empty_rows_show_placeholder_and_ignore_enter`：无行 ->
  "(no results)" 可见，回调未被调用。
- `test_lsp_chooser_uses_theme_attach_detach`：monkeypatch `theme.attach/detach`，
  挂载/卸载，断言各调用一次。

使用 `tests/test_marks_palette.py` 中的 Textual pilot 模式
（在 `tests/` 下找到实际文件名；不要修改它）。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_chooser.py -q
.venv\Scripts\python.exe -m pyright yate/editor_components/lsp_chooser.py tests/test_lsp_chooser.py
```

要求以 0 退出。

## 风险 / 回滚

风险：`theme.attach` 可能要求 `OverlayScreen` 已挂载到 App 上；复用 marks 测试中
完全相同的 pilot fixture。风险：R15 守卫会扫描所有定义可滚动子类的 L2 模块 ——
本界面没有定义任何子类（它只实例化 `OverlayScroll`），因此无需注册守卫。
回滚：删除这两个新文件；在波次 3 之前没有其他波次导入它们。
