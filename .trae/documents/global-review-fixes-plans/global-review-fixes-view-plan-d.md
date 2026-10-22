# plan-d：`editor_view` 组件修复

- 波次：wave-2（与 plan-c 并行）
- 覆盖：W-04 / W-09 / S-07 / S-08 / S-11
- 独占文件清单：
  - `yate/editor_view/cells.py`
  - `yate/editor_view/themes.py`
  - `yate/editor_view/terminal.py`
  - `yate/editor_view/find_replace.py`
  - `yate/editor_view/manual.py`
  - `tests/test_cells.py`
  - `tests/test_theme_palettes.py`
  - `tests/test_manual.py`
  - `tests/test_app_find_replace.py`
- 只改以上文件，不得动其它任何文件。

## 一、输入事实（已核对源码）

- W-04：[cells.py](../../yate/editor_view/cells.py) `cell_offsets` 第 97-118 行与
  `char_to_cell` / `cell_to_char` 第 71-94 行对零宽字符都按 `max(1, ...)` 前进，
  而 `expand_char` 第 121-134 行把组合符附加到前一格。
- W-09：[themes.py](../../yate/editor_view/themes.py) `validate_theme` 第 488-502 行
  只遍历 `_MAPPED_COLOR_FIELDS` 的 13 个字段。
- S-07：[terminal.py](../../yate/editor_view/terminal.py) `_cell_style` /
  `_cursor_style` 第 393-415 行用 `Any`。
- S-08：[find_replace.py](../../yate/editor_view/find_replace.py) `_render_results`
  第 249-294 行在渲染路径调用 `_relative`，每个命中文件同步 `resolve()`。
- S-11：[manual.py](../../yate/editor_view/manual.py) `_load_doc` 第 476-488 行只捕
  `OSError`；`UnicodeDecodeError` 会让 `exit_on_error=False` 的 worker 静默退出，
  loading 行永久停留。

## 二、分步修改

### 步骤 D1：W-04 三处零宽字符语义统一

**文件**：`yate/editor_view/cells.py`

把 `char_to_cell` / `cell_to_char` / `cell_offsets` 的非 tab 分支改为：

```python
        width = cell_width(ch)
        if width == 0 and cells:
            # combining mark attaches to the previous cell (expand_char)
            continue  # or: no cell advance
        cells += max(1, width)
```

具体：

- `char_to_cell`：循环体内在 `if ch == "\t": ... else: ...` 的 else 分支按上式
  处理；零宽且已有格子时不前进。
- `cell_to_char`：同样零宽且 `cells > 0` 时不前进（`cells >= cell` 判断仍在循环
  开头）。
- `cell_offsets`：同样规则；`offsets[i]` 对组合符沿用前一格偏移。

同步更新 `cell_offsets` docstring：明确“零宽字符（组合符）占用 0 格，首字符为
组合符时按 `expand_char` 退化为 1 格”。

### 步骤 D2：W-09 校验全部颜色字段

**文件**：`yate/editor_view/themes.py`

1. `from dataclasses import dataclass, field` 改为
   `from dataclasses import dataclass, field, fields`。
2. 在 `Theme` 类定义之后、`_MAPPED_COLOR_FIELDS` 之前加：

```python
#: Every color slot on :class:`Theme` (``name`` / ``label`` / ``dark`` /
#: ``extra`` are not colors).  Derived from the dataclass so a new color field
#: cannot silently escape validation.
_COLOR_FIELDS: tuple[str, ...] = tuple(
    f.name for f in fields(Theme)
    if f.name not in ("name", "label", "dark", "extra")
)
```

3. `validate_theme` 的 `for field_name in _MAPPED_COLOR_FIELDS:` 改为
   `for field_name in _COLOR_FIELDS:`；docstring 第 3 点改为 “every color slot
   declared on Theme parses ... the `_OPAQUE_FIELDS` subset ...”。

`_OPAQUE_FIELDS` 判定保持只在字段命中时生效。

### 步骤 D3：S-07 收敛 `Any`

**文件**：`yate/editor_view/terminal.py`

1. 顶部已 `from yate.editor_term import Cell`，无需新增导入。
2. 新增 `from yate.editor_view.themes import Theme`（与现有
   `from yate.editor_view import theme` 并存；不改包惰性约定，只 import 类型）。
3. 两个签名改为：

```python
    def _cell_style(cell: Cell, t: Theme) -> Style:
    def _cursor_style(cell: Cell, t: Theme) -> Style:
```

（`Cell` 的属性 `fg/bg/dim/reverse/bold/...` 均为具体类型；若 pyright 报
`Cell.fg` 类型，按 `editor_term` 的声明为准，不用 `Any` 掩盖。）

### 步骤 D4：S-08 把相对路径标签计算移到搜索 worker

**文件**：`yate/editor_view/find_replace.py`

1. 删除 `_relative_cached` / `_relative` 与 `functools.lru_cache` 导入（若不再使用）。
2. 新增纯函数：

```python
def _relative_text(path: Path, root: Path | None) -> str:
    """Workspace-relative display label; bare name outside the root."""
    if root is not None:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    return path.name
```

3. `FindReplaceScreen.__init__` 增加 `self._labels: dict[Path, str] = {}`。
4. `_scan`（第 385-395 行）返回三元组 `(results, truncated, labels)`，其中

```python
        labels = {
            fm.path: _relative_text(fm.path, self._workspace.root)
            for fm in results
        }
```

   在 worker 线程内执行。
5. `_run_search` 第 397-404 行接收三元组，保存 `self._labels = labels`。
6. `_clear_results` 同时 `self._labels = {}`。
7. `_render_results` 第 272 行改为
   `text.append(self._labels.get(fm.path, fm.path.name), style=t.fg_muted)`；
   `root` 局部变量与 `_relative` 调用删除。

### 步骤 D5：S-11 文档读取兜底

**文件**：`yate/editor_view/manual.py`

`_load_doc` 第 478-483 行改为：

```python
        try:
            source = await asyncio.to_thread(
                load_doc_markdown, self._kind, self._lang
            )
        except Exception as exc:  # noqa: BLE001 - a bad read must not hang the viewer
            log.exception("failed to load the %s", self._title)
            source = f"failed to load the {self._title}: {exc}"
```

## 三、新增测试

### `tests/test_cells.py`

1. `test_cell_offsets_keep_a_combining_mark_in_the_previous_cell`
   - 准备：`line = "a\u0301b"`。
   - 断言：`cell_offsets(line) == [0, 1, 1, 2]`。
2. `test_char_to_cell_and_cell_offsets_agree_on_combining_marks`
   - 断言：对 `range(len(line) + 1)` 每个 i，`offsets[i] == char_to_cell(line, i)`。
3. `test_leading_combining_mark_still_occupies_one_cell`
   - 断言：`cell_offsets("\u0301a") == [0, 1, 2]`（与 `expand_char` 首字符退化一致）。

### `tests/test_theme_palettes.py`

4. `test_validate_theme_rejects_an_invalid_unmapped_color`
   - 准备：`validate_theme(_bad(name="bad-syn", syn_keyword="nope"))`
   - 断言：`any("syn_keyword" in p for p in problems)`。
5. `test_validate_theme_rejects_an_invalid_selection_color`
   - 准备：`_bad(name="bad-selection", selection_bg="not-a-color")`
   - 断言：problems 提到 `selection_bg`。
6. `test_set_theme_normalizes_case_and_whitespace`
   - 操作：`theme.set_theme("  MoChA  ")`
   - 断言：`theme.active().name == "mocha"`；`finally` 中恢复 `"mocha"`。

### `tests/test_manual.py`

7. `test_unreadable_manual_degrades_to_an_error_row`
   - 准备：`patch("yate.editor_view.manual.load_doc_markdown", side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"))`
   - 操作：F8 打开手册，`wait_until(not loading.display, timeout=15)`
   - 断言：`"failed to load" in screen.query_one("#doc-md", DocBody).source`；
     屏幕仍挂载（未崩）。

### `tests/test_app_find_replace.py`

8. 既有“结果列表显示相对路径”用例保持通过（S-08 无可见行为变化）；
   若现有用例未覆盖，则补 `test_results_show_workspace_relative_labels`：
   - 工作区根 `tmp`，文件 `sub/a.txt` 含命中；
   - 执行项目查找，断言结果文本包含 `sub/a.txt`。

## 四、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_cells.py tests/test_theme_palettes.py tests/test_manual.py tests/test_app_find_replace.py -q
.venv\Scripts\python.exe -m pyright yate/editor_view tests/test_cells.py tests/test_theme_palettes.py tests/test_manual.py tests/test_app_find_replace.py
```

通过判定：两条命令退出码均为 0。

## 五、风险与回滚

- 零宽语义变更会改变鼠标列→字符换算；三函数统一后与渲染一致，属修复目标。
- `_labels` 由 worker 计算，渲染路径不再 stat；主题重绘复用同一标签，
  文件重命名后的陈旧标签由下一次搜索结果重建（与原 lru 注释一致）。
- 手册读取改为兜底所有异常，错误文本仍显示在正文，不吞异常（记 `log.exception`）。
- 回滚：本子计划单独提交。
