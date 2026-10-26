# Hex View - Plan B: HexView Widget + HexScreen

## 目标

实现 hex view 的呈现层：
1. `HexView` widget（L2）：类似 `xxd` 的十六进制只读视图，每行 = 偏移量 + 十六进制字节 + ASCII 回显；
2. `HexScreen`（L2）：全屏覆盖层，承载 HexView，类似 `OverlayScreen`（`yate/editor_view/modals.py:58`）的 ModalScreen 模式。

## 非目标

- 大文件分段加载（留作后续 feature）；
- hex view 内的编辑功能（只读视图）。

## 输入

- `yate/editor_view/diffview.py` + `yate/editor_view/diff_pane.py`（先例：DiffScreen + DiffPane 的拆分模式）；
- `yate/editor_view/modals.py:58`（OverlayScreen 先例：ModalScreen 形态）；
- `yate/editor_view/theme.py:120-133`（`ThemeListener = Callable[[], None]`，`Unsubscribe = Callable[[], None]`，`subscribe(listener: ThemeListener) -> Unsubscribe`）；
- `yate/editor_view/diff_pane.py:294` / `yate/editor_view/manual.py:270` / `yate/editor_view/completion.py:192`（`render_line(self, y: int) -> Strip` 先例）；
- `yate/editor_view/commandline.py:79` / `yate/editor_view/diffview.py:74`（`DEFAULT_CSS = load_tcss("...")` 先例）。

## 独占文件清单

- `yate/editor_view/hexview.py`（新增：HexView widget + HexScreen + `MAX_HEX_VIEW_SIZE` 常量）；
- `yate/resources/hex-view.tcss`（新增：HexView 样式）；
- `tests/test_hex_view.py`（新增：HexView 单元测试）。

## 具体修改

### 1. 新增 `yate/editor_view/hexview.py`

**模块职责**：HexView widget（纯渲染 + 滚动）+ HexScreen（ModalScreen 覆盖层）+ `MAX_HEX_VIEW_SIZE` 常量。

**关键设计**：
- `HexView` 继承 `ScrollView`，按行渲染 hex dump（每行 16 字节）；
- 构造注入 `path: Path` + `data: bytes`（一次性读入，上限 100MB）；
- **必须设置 `virtual_size`**：ScrollView 需要 `virtual_size.height = len(data) // 16 + 1` 才能滚动；
- 主题自持（R13）：订阅 `theme.subscribe`，挂载时上色，广播时重绘；
- 按键消费（R10）：`q` / `Esc` 关闭 screen，其余键 fall-through；
- 日志走 tracing（R12）：`log = tracing.get_logger(__name__)`；
- 不 import `yate.editor` / `yate.app`（R3）。

**核心类签名**：
```python
from __future__ import annotations

from pathlib import Path
from textual.strip import Strip
from textual.widget import ScrollView
from textual.screen import ModalScreen
from textual.compose import ComposeResult

from yate import tracing
from yate.editor_view.theme import ThemeListener, Unsubscribe, subscribe
from yate.paths import load_tcss

log = tracing.get_logger(__name__)

MAX_HEX_VIEW_SIZE: int = 100 * 1024 * 1024  # 100 MB


class HexView(ScrollView, can_focus=True):
    """Read-only hex dump viewer (xxd-style layout).

    Each line renders 16 bytes: offset (8 hex digits + ':') + hex groups
    (2 groups of 8 bytes, no intra-byte spaces, 2 spaces between groups) +
    ASCII column (printable 0x20-0x7e as-is, else '.').
    """

    DEFAULT_CSS = load_tcss("hex-view.tcss")

    def __init__(
        self,
        path: Path,
        data: bytes,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._path = path
        self._data = data
        # ScrollView requires virtual_size to enable scrolling.
        self.virtual_size.height = (len(data) + 15) // 16

    def on_mount(self) -> None:
        """Subscribe to theme broadcasts (R13)."""
        self._unsub: Unsubscribe = subscribe(self._on_theme_changed)

    def on_unmount(self) -> None:
        """Unsubscribe on exit."""
        self._unsub()

    def _on_theme_changed(self) -> None:
        """Repaint on theme broadcast (ThemeListener = Callable[[], None])."""
        self.refresh()

    def render_line(self, y: int) -> Strip:
        """Render one line of hex dump (offset + hex + ASCII)."""
        offset = y * 16
        chunk = self._data[offset : offset + 16]
        if not chunk:
            return Strip.blank(self.size.width)
        # Format: 00000000: 4d5a 9000 0300 0000 0400 0000 ffff 0000  MZ..............
        hex_part = self._format_hex(chunk)
        ascii_part = self._format_ascii(chunk)
        line = f"{offset:08x}: {hex_part}  {ascii_part}"
        return Strip.from_text(line.ljust(self.size.width))

    def _format_hex(self, chunk: bytes) -> str:
        """Format 16 bytes as 2 groups of 8 bytes (xxd-style)."""
        groups = []
        for i in range(0, len(chunk), 8):
            group = chunk[i : i + 8]
            hex_str = "".join(f"{b:02x}" for b in group)
            # Pad to 16 chars if last group is short.
            groups.append(hex_str.ljust(16))
        return "  ".join(groups)

    def _format_ascii(self, chunk: bytes) -> str:
        """Format 16 bytes as ASCII (printable 0x20-0x7e, else '.')."""
        return "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)


class HexScreen(ModalScreen[None]):
    """Full-screen overlay hosting a HexView.

    ModalScreen[None] is the precise annotation (守卫 test_screen_annotations_are_precise).
    """

    def __init__(self, path: Path, data: bytes) -> None:
        super().__init__()
        self._path = path
        self._data = data

    def compose(self) -> ComposeResult:
        yield HexView(self._path, self._data, id="hex-view")

    def on_key(self, event: Key) -> None:
        if event.key in ("q", "escape"):
            self.dismiss(None)
            event.stop()
```

**hex dump 格式**（每行 16 字节，对齐 `xxd`）：
```
00000000: 4d5a 9000 0300 0000 0400 0000 ffff 0000  MZ..............
```
- 偏移量：8 位十六进制 + `:`；
- 十六进制：16 字节分 2 组（各 8 字节），每组内字节间无空格，组间 2 空格；
- ASCII 列：可打印字符（0x20-0x7e）原样显示，其余显示 `.`。

### 2. 新增 `yate/resources/hex-view.tcss`

**样式**：
```tcss
HexView {
    width: 1fr;
    height: 1fr;
    background: $surface;
    color: $foreground;
}
```

### 3. 新增 `tests/test_hex_view.py`

**测试用例**：

| 用例名 | 验证行为 |
|---|---|
| `test_hex_view_renders_offset_hex_ascii` | 给定 16 字节数据，`render_line(0)` 输出格式正确（偏移 + hex + ASCII） |
| `test_hex_view_handles_partial_last_line` | 数据长度非 16 倍数时，最后一行正确填充空格 |
| `test_hex_view_ascii_column_replaces_nonprintable` | 非打印字符（0x00-0x1f, 0x7f-0xff）显示为 `.` |
| `test_hex_view_theme_subscription` | 挂载时订阅 theme，广播时触发 refresh |
| `test_hex_screen_dismisses_on_q` | 按 `q` / `Esc` 关闭 screen |
| `test_hex_view_virtual_size_matches_line_count` | `virtual_size.height == (len(data) + 15) // 16` |

**测试文件独占**：`tests/test_hex_view.py`。

## 输出

- `HexView` widget 可渲染任意 bytes 数据的 hex dump；
- `HexScreen` 可作为 ModalScreen 推送；
- `MAX_HEX_VIEW_SIZE` 常量定义在此模块（OverlayFlows import 它）；
- 测试覆盖正反路径。

## 验收命令

```powershell
cd D:\Programming\yate-hex-view
.venv\Scripts\python.exe -m pytest tests/test_hex_view.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/editor_view/hexview.py tests/test_hex_view.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

通过判定标准：
- pytest 退出码 0，所有用例通过；
- pyright 零诊断；
- 架构测试无新增违规（R3/R13 守卫通过）。

## 风险清单

| 风险 | 缓解 |
|---|---|
| HexView 渲染大文件性能（100MB ~ 6.25M 行） | 上限 100MB；ScrollView 按行懒渲染，实际可见行数受终端高度限制 |
| 主题广播导致频繁重绘 | `_on_theme_changed` 只调 `self.refresh()`，Textual 合并同帧重绘 |
| HexScreen 按键吞掉未识别键 | `on_key` 只消费 `q` / `Esc`，其余 fall-through（R10） |
| ScrollView 未设 virtual_size 导致无法滚动 | 构造器内显式设置 `virtual_size.height` |

## 回滚路径

删除 `yate/editor_view/hexview.py` + `yate/resources/hex-view.tcss` + `tests/test_hex_view.py` 即可回滚。

## 触碰架构边界

- **R3**：`editor_view/hexview.py` 不得 import `yate.editor` / `yate.app`（守卫：`test_editor_view_does_not_import_upward`）；
- **R13**：HexView 自持主题，订阅 `theme.subscribe`（守卫：`test_no_class_level_scrollbar_renderer_patch` + T2）；
- **R9**：HexView 的 id `#hex-view` 是 widget id，不被外壳 CSS 引用（同 `#statusbar` 先例），样式由组件 `DEFAULT_CSS` 自持。

## 【执行】【审核】迭代记录段

- 2026-10-24 主代理复核修订：补充 `virtual_size` 设置要求（ScrollView 必须）；
  `ModalScreen[None]` 精确形态（守卫 `test_screen_annotations_are_precise`）；
  `ThemeListener = Callable[[], None]` 签名对齐（`theme.py:120`）；
  `MAX_HEX_VIEW_SIZE` 只在此模块定义一次（OverlayFlows import 它）。
