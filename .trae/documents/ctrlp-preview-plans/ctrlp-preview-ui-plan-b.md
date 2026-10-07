# plan-b：预览窗格 UI（L2）

> 总纲见 `overview.md`。前置依赖：plan-a 的 `FilePreviewConfig`。
> 本波是唯一改动面较大的提交；`enable=False` 与 commands 模式的现有行为
> 必须逐字节保持，由测试钉死。

## 一、目标

`PaletteScreen` 文件模式下渲染预览窗格：读取当前光标文件、语法高亮、
缓存与 worker 并发控制、大文件/二进制降级提示，全部组件自持。

## 二、独占文件清单

- `yate/editor_view/palette.py`（改）
- `yate/resources/palette-screen.tcss`（改）
- `tests/test_palette_preview.py`（新建）

## 三、逐文件改动明细

### `yate/editor_view/palette.py`

1. **新 import**（各归其组）：
   - `from dataclasses import dataclass`（stdlib 组）；
   - `from textual.widgets import RichLog`（并入现有 textual.widgets 导入行）；
   - `from yate.config import FilePreviewConfig`（项目组；L2→L0，
     `editor_view/terminal.py:23` 先例）；
   - `from yate.editor_syntax.engine import tokenize_document`（L2→L0，
     `editor_view/editor.py:23` 先例）；
   - `from yate.editor_syntax.tokens import Token`。
2. **预览数据记录**（模块级，紧随 `MAX_VISIBLE`）：

   ```python
   @dataclass(frozen=True)
   class _PreviewData:
       """Worker-produced preview payload (raw lines + tokens, no widgets)."""

       path: Path
       lines: list[str]
       tokens: list[list[Token]]
       mtime_ns: int
       size: int
       truncated: bool
       note: str | None   # binary / oversize / unreadable explanation
   ```

   `#: preview cache entry cap (FIFO eviction)` `PREVIEW_CACHE_SIZE: int = 16`。
3. **`PaletteScreen.__init__`** 新增关键字参数 `preview: FilePreviewConfig`
   （放在 `refresh` 之后、`**kwargs` 之前），存 `self.preview = preview`；
   另初始化 `self._preview_cache: dict[Path, _PreviewData] = ()` —— 即
   `dict[Path, _PreviewData]`（有效性以记录内 mtime/size 判断）。
   docstring 补一句 preview 参数语义。
4. **`compose()`** 改造：

   ```python
   with Vertical(id="palette"):
       yield Input(...)                       # 原样
       with Horizontal(id="palette-body"):
           yield Static(id="palette-results") # 原样
           if self.mode == "files" and self.preview.enable:
               yield PreviewLog(id="palette-preview")
   ```

   - `position == "left"` 时先 yield preview 再 yield results（DOM 顺序即视觉顺序）；
   - compose 内对 `#palette-preview` 设置 `styles.width = f"{self.preview.size}%"`
     （组件自持几何尺寸，R13 允许；着色仍归 tcss/主题）；
   - `self.add_class("with-preview")` 仅在预览分支调用。
5. **`PreviewLog` 子类**（模块级，`PaletteScreen` 之前）：

   ```python
   class PreviewLog(RichLog):  # can_focus=False keeps focus on the input
       can_focus = False
   ```

   （R10：防鼠标点击抢焦点引出的二次派发/按键丢失。）
6. **预览线程函数** `_load_preview(path: Path) -> _PreviewData`（方法，
   worker 线程内执行，**不碰任何 widget**）：

   - `path.stat()` → OSError 时返回 `note=f"cannot read: {exc}"` 空载荷；
   - `st_size > max_size` → `note=f"file too large (> {max_size} bytes)"` 空载荷；
   - `not Workspace.is_text_file(path)` → `note="(binary file)"` 空载荷
     （`Workspace` 已 import）；
   - 按行读前 `max_lines` 行：`islice(fh, max_lines)` + `rstrip("\n")`，
     读毕 `next(fh, None) is not None` 判 `truncated`；
     `UnicodeDecodeError` 按 `errors="replace"` 容错（打开时声明）；
   - `filetype = path.suffix.lower().lstrip(".") or "plaintext"`
     （`Document.filetype` 同款判定，不建 Document）；
   - `tokens = tokenize_document(lines, filetype)`（纯函数，线程安全；
     空行列表时跳过调用直接给 `[]`）；
   - 返回完整 `_PreviewData`（含 `stat().st_mtime_ns` / `st_size`）。
7. **触发点 `_update_preview()`**（新方法）：

   - `self.mode != "files" or not self.preview.enable` → 直接返回；
   - 无选中项（`_filtered` 空或 status 中）→ 清空预览（`RichLog.clear()`）返回；
   - 取当前 `payload: Path`；缓存命中（记录的 `mtime_ns`/`size` 与现 `stat()` 一致）
     → 直接 `_render_preview(cached)`；
   - 未命中 → 预览区显示 `loading…`（dim），起
     `self.run_worker(self._load_preview_worker(path), group="palette-preview",
     exclusive=True, exit_on_error=False)`
     （coroutine 包装：`await asyncio.to_thread(self._load_preview, path)`
     后回到 UI 线程做回调部分——形态对齐 `_index_files`）；
   - 调用点：`refilter()` 末尾、`on_key` 两个光标移动分支
     （`_render_results()` 之后）。
8. **worker 完成回调**（同协程 UI 段）：
   - `if not self.is_mounted: return`（palette.py:180 先例）；
   - 写缓存：容量 ≥ `PREVIEW_CACHE_SIZE` 时 `pop(next(iter(...)))` FIFO 驱逐；
   - **竞态守卫**：重读当前光标 payload，与请求 path 不同则只写缓存不渲染；
   - 渲染：`_render_preview(data)`。
9. **`_render_preview(data: _PreviewData)`**（UI 线程）：
   - `t = theme.active()`；`log_widget = self.query_one("#palette-preview", PreviewLog)`；
   - `note` 非空 → `log_widget.clear(); write(Text(note, style=t.fg_dim))` 返回；
   - Rich Text 拼装 `_preview_text(data)`：

     ```python
     for line, row_tokens in zip(data.lines, data.tokens):
         pos = 0
         for tok in row_tokens:
             start, end = min(tok.start, len(line)), min(tok.end, len(line))
             if start > pos:
                 text.append(line[pos:start], style=t.fg)
             text.append(line[start:end], style=t.syntax_style(tok.kind))
             pos = max(pos, end)
         if pos < len(line):
             text.append(line[pos:], style=t.fg)
         text.append("\n")
     ```

     （列区间按行长夹紧，防后端越界；无 token 行整行 `t.fg`。）
   - `truncated` → 追加 `f"… truncated at {self.preview.max_lines} lines"`（`t.fg_dim`）；
   - `log_widget.clear()` 后**单次** `write(text)`。
10. **`on_mount`**：文件模式预览启用时先 `_update_preview()` 放在
    `_render_results()` 之后（索引未完成时走"无选中项"清空分支，无副作用）。

### `yate/resources/palette-screen.tcss`

追加（既有条目不动，仅 `#palette-results` 补一行宽度）：

```tcss
PaletteScreen #palette-results {
    width: 1fr;          /* 补充：无预览时铺满，行为不变 */
}
PaletteScreen.with-preview #palette {
    height: 70%;
    max-height: 30;
    width: 90%;
    max-width: 140;
}
PaletteScreen #palette-body {
    height: 1fr;
}
PaletteScreen #palette-preview {
    border-left: tall $panel;
    background: $surface;
    padding: 0 1;
}
```

（预览宽度百分比由 compose 运行时设置，tcss 不写死。）

### `tests/test_palette_preview.py`（新建）

结构照 `tests/test_diffview.py`：`_Host(App)` on_mount 里 push 构造好的
`PaletteScreen`，`asyncio.run(scenario())`，文件头
`# tests legitimately poke at screen internals:` + `pyright: reportPrivateUsage=false`；
等待用 `conftest.wait_until`（worker 异步完成不能只靠 `pilot.pause()`）。

夹具：tmp_path 造文件——`alpha.py`（含 `def`/字符串，断言 token 着色）、
`beta.md`、大文件（3000 行，超默认 max_lines）、二进制（含 `\x00` 字节）、
超大文件（写 `max_size` 用小上限配置绕开体积）。

| 用例 | 断言 |
|---|---|
| `test_files_mode_composes_preview_pane` | enable 时存在 `#palette-preview`；`PaletteScreen` 有 `with-preview` class；`#palette-body` 包裹 results+preview |
| `test_disabled_preview_keeps_legacy_dom` | `enable=False`：`query("#palette-preview")` 空、无 `with-preview` class、`filtered_count` 行为不变 |
| `test_commands_mode_has_no_preview` | mode="commands"：无 preview widget（构造仍传 preview 配置） |
| `test_preview_follows_cursor` | 两个不同文件命中搜索 → 移动光标后 `wait_until` 预览含第二文件内容（`_PreviewData.path` 断言） |
| `test_preview_shows_syntax_tokens` | `alpha.py` 预览的 Rich Text 中 keyword token span 带非默认色（探针：`data.tokens` 非空即可 + 至少一个 kind ∈ SYNTAX_KINDS） |
| `test_preview_truncates_large_file` | 3000 行文件 → 预览文本含 "truncated"；行数 ≤ max_lines |
| `test_preview_reports_binary` | 二进制文件 → 预览区显示 "(binary file)" |
| `test_preview_reports_oversize` | `max_size` 极小配置 → "file too large" 提示 |
| `test_preview_cache_hits_without_reread` | 同文件来回移动光标 → 第二次命中缓存（探针：`_load_preview` 调用计数，monkeypatch 计数器） |
| `test_preview_position_left_reorders_dom` | `position="left"` → compose 顺序 preview 在 results 前 |

## 四、架构边界自检

- R3：`palette.py` 只新增 L0 向下 import（config / editor_syntax），不触
  `yate.editor` / `yate.app` ✓
- R8：`preview: FilePreviewConfig` 具体对象注入，无协议 ✓
- R10：不新增按键路径；`PreviewLog.can_focus = False` 防焦点漂移 ✓
- R12：无 `self.log` / `app.log`；如需日志用模块级 `tracing.get_logger`（本波预计无需）✓
- R13：着色全部 `theme.active()` 自持；宽度是几何尺寸非着色；滚动条
  `apply_slim_scrollbars(preview)` per-widget 注入（on_mount 内，manual.py:223
  同款），无类级 patch ✓
- T1/T2 断言面（`editor.py`）零触碰 ✓
- R6：无 TYPE_CHECKING；无新 Protocol ✓

## 五、验收命令（worktree 内）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_palette_preview.py tests/test_config.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/editor_view/palette.py tests/test_palette_preview.py
```

预期：全绿 + 22 架构用例全绿 + pyright 零诊断。

## 六、回滚

随 plan-c 合并为一笔提交；revert 后 `palette.py`/`tcss` 恢复原状，
无残留（新增项均为纯增量，旧分支方法未改语义的仅 `compose` 结构）。
