# plan-b（W-B）：渲染组件与终端 — 7 条

- 波次：W-B（依赖 W-A 完成；与 W-C / W-D 并行）
- 独占文件（**只改这些**）：`yate/editor_view/terminal.py`、`yate/editor_view/diff_pane.py`、
  `yate/editor_view/find_replace.py`、`yate/editor_view/chrome.py`、`yate/editor_view/theme_files.py`、
  `yate/editor_view/panes.py`、`yate/editor_term/emulator.py`；
  测试：`tests/test_terminal.py`、`tests/test_app_terminal.py`、`tests/test_diffview.py`、
  `tests/test_app_find_replace.py`、`tests/test_chrome.py`、`tests/test_theme_files.py`、
  `tests/test_panes.py`、`tests/test_terminal_emulator.py`
- 输入：评审记录 §五 M-4、§六 m-1/m-2/m-5/m-12/m-13/m-20

## 1. M-4（MAJOR，性能）`yate/editor_view/terminal.py:311-315` 每行重建网格

**根因**：`render_line(y)` 每行都调 `emulator.view_lines(self._scroll)`，后者对全部 `rows` 行
逐个 `list(line)` 复制（`editor_term/emulator.py:755-778`）→ 每帧 O(rows²·cols)。

**前置测量**（`overview.md` §四）：先用一次性脚本对 80×24 网格连续调用 `view_lines` 1000 次计时，
得到基线并记录；达不到 5× / 1 ms 判据则本条转"登记不修"。

**修法（只改 L2，不动 emulator）**：在 `TerminalView` 内缓存一帧快照 + 失效序号：

```python
# __init__ 内
self._snapshot: list[list[Cell]] | None = None
self._snapshot_key: tuple[int, int, int, int] = (-1, -1, -1, -1)

def _grid(self) -> list[list[Cell]]:
    key = (self._scroll, int(self.size.width), int(self.size.height), self._grid_seq)
    if self._snapshot is None or key != self._snapshot_key:
        self._snapshot = self.emulator.view_lines(self._scroll)
        self._snapshot_key = key
    return self._snapshot
```

`_grid_seq` 在 `_on_output`（:174-178）、`resize` 分支（:215-219）、`_on_exit`（:185-189）、
`scroll_by`（:302-306）里自增（或直接用 `self.refresh()` 前后自增）；`render_line` 改为
`lines = self._grid()`。注意 `Cell` 类型来自 `editor_term`，`_snapshot` 注解用
`list[list[Cell]] | None`（保持 pyright strict 零诊断）。

**回归测试**（`tests/test_terminal.py`）：
- `test_render_line_reuses_one_grid_snapshot_per_frame`（同一帧内两次 `render_line` 只调一次
  `view_lines`：用 `monkeypatch` 计数）
- `test_grid_snapshot_invalidates_after_output`（`feed` 后新内容出现在渲染结果里）

## 2. m-1（MINOR）`yate/editor_view/diff_pane.py:362-379` tab 行内联高亮错位

**根因**：`cells` 由 `theme.expand_char` 展开（`\t` → 多个 `" "` 单元），而 `span` 只在
非空单元自增 → `span` 跑在真实字符索引前面，`_in_spans(inline, span)` 取错位。

**修法**：构建 `cells` 时同步构建 `cell_char: list[int]`（每个 cell 对应的字符下标；宽字符续位
沿用前一个下标），渲染循环用 `char_index = cell_char[cell_idx]` 传给 `_in_spans`。

**回归测试**（`tests/test_diffview.py`）：
`test_inline_highlight_lines_up_after_a_leading_tab`（tab 缩进 + 行内变更段，断言被着色的
Segment 文本区间与 `inline` 字符区间经 `char_to_cell` 换算后一致）。

## 3. m-2（MINOR，性能）`yate/editor_view/find_replace.py:102-109,256` 渲染期 `resolve()`

**前置测量**：构造 500 个 `FileMatch`，`_render_results` 计时；达不到 30% 降幅则登记不修。

**修法**：给 `_relative` 加缓存：`@functools.lru_cache(maxsize=1024)` 包一层
`_relative_cached(path: Path, root: Path | None) -> str`，`_relative` 转调；docstring 注明
"标签用途，重命名后最坏显示旧相对路径，下一次结果重建即修正"。

**回归测试**：`tests/test_app_find_replace.py` 既有用例全绿即可（行为不变）；
新增 `test_result_labels_are_cached_per_path`（两次渲染只解析一次，用 `monkeypatch` 计数 `Path.resolve`）。

## 4. m-5（MINOR）`yate/editor_term/emulator.py:276` DEL 当可打印

**修法**：`elif ord(ch) >= 0x20 and ch != "\x7f": self._print(ch)`（或显式 `elif ch == "\x7f": pass`）。

**回归测试**（`tests/test_terminal_emulator.py`）：
`test_del_byte_does_not_advance_the_cursor`（`feed(b"a\x7fb")` → 网格为 `a b` 位置 0/1，光标在第 2 列）。

## 5. m-12（MINOR，性能）`yate/editor_view/chrome.py:181` 每次重绘两次 `resolve()`

**前置测量**：同一路径 `refresh_crumbs` 1000 次计时；< 30% 降幅则登记不修。

**修法**：`root.resolve()` 结果缓存到实例字段（workspace 根变化时失效）；
`path.resolve()` 只算一次再 `relative_to`。

**回归测试**：`tests/test_chrome.py` 既有用例全绿；新增 `test_breadcrumbs_resolve_root_once`（计数）。

## 6. m-13（MINOR）`yate/editor_view/theme_files.py:73` 失败主题文件重复 `exec`

**修法**：把 `_loaded_theme_files.add(resolved)` 移到 `exec` 之前（或 `finally`），
失败文件也记入已加载集，只报一次错。

**回归测试**（`tests/test_theme_files.py`）：
`test_a_broken_theme_file_reports_once`（同一路径调两次 `load_theme_file`，第二次返回 `None` 且
`load_theme_paths` 只产生一条错误）。

## 7. m-20（MINOR）`yate/editor_view/panes.py:530` `compose()` 缺返回注解

**修法**：`def compose(self) -> ComposeResult:`（从 `textual.app` 导入该别名，按文件既有导入分组）。

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.\.venv\Scripts\python.exe -m pytest tests/test_terminal.py tests/test_terminal_emulator.py tests/test_app_terminal.py tests/test_diffview.py tests/test_app_find_replace.py tests/test_chrome.py tests/test_theme_files.py tests/test_panes.py -q --cov-fail-under=0
```

## 风险与回滚

- M-4 缓存键漏项会造成"终端不刷新"（比性能更严重）：必须覆盖 `feed` / `resize` / `scroll` /
  `exit` 四条失效路径，用例逐条断言；漏一条即不得合并。
- 回滚：按条 `git revert`；四条性能项互不依赖。
