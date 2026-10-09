# vim-column-mode 子计划 a：TextBuffer 块选择模型（wave-1）

> 输入：`overview.md` §四调研事实。依赖：无。下游：plan-c/d/e/f 全部依赖本计划的
> 块 API。

## 一、目标

在 L0 `TextBuffer`（`yate/editor_core/buffer.py`）上以最小状态实现块（列）选择：

1. `block: bool` 标志 + anchor/cursor 作两角（overview 方案 A）；
2. 归一化查询 `block_region()`、文本/删除/插入/替换四组块编辑 API；
3. `set_cursor` / `clear_selection` / `select_all` / `set_text` 及全部
   `anchor = None` 写点的块标志卫生；
4. `type_char` 块分支（打印字符整列替换）；
5. `paste()` 按寄存器类型走块回贴（`register_block` 标志）。

## 二、非目标

- 多光标 / `I`/`A` 逐行插入（overview §二）；
- 虚列（右界按各行行长夹取，不产生虚拟空白）。

## 三、独占文件清单

只改以下文件，不动其它任何文件：

- `yate/editor_core/buffer.py`
- `tests/test_editor_core.py`（追加用例）
- `.trae/rules/architecture-boundaries.md`（仅 §三.7 豁免名单的 buffer.py 行数回填）

## 四、具体修改（yate/editor_core/buffer.py）

### 1. 状态字段

- `__init__`（:76 之后）加：

```python
#: Block (column) selection flag: when True the anchor and cursor are the
#: two corners of a rectangular selection instead of a charwise span.
self.block = False
```

- `__init__`（:83 `self.register` 之后）加：

```python
#: True when :attr:`register` holds a newline-joined block (column) yank;
#: :meth:`paste` uses it to pick the block paste path.
self.register_block = False
```

### 2. 既有方法的状态卫生（`block = False` 同步点）

| 位置 | 改动 |
|---|---|
| `set_cursor`（:276-291） | `select=True` 且 `anchor is None` 分支（新建 charwise 选区）加 `self.block = False`；`select=False` 分支（清 anchor）加 `self.block = False`；扩展分支（anchor 已存在）保持 block 不变 |
| `clear_selection`（:272-274） | 加 `self.block = False` |
| `select_all`（:293-297） | 加 `self.block = False` |
| `set_text`（:135-145） | 加 `self.block = False`、`self.register_block = False` |
| 下列把 `self.anchor` 置 `None` 的写点逐一同行补 `self.block = False`：`insert_text`（:322）、`replace_range`（:353）、`delete_selection`（:474）、`delete_lines`（:724）、`duplicate_line`（:737）、`move_line`（:751）、`join_lines`（:772）、`delete_to_line_start`（:785） | 保证任何选区销毁路径不残留块标志 |
| `yank_lines`（:680）、`yank_selection`（:696）、`delete_lines`（:718） | 写 `self.register` 处同行补 `self.register_block = False`（charwise/linewise 覆盖块寄存器类型） |

### 3. 新增 "block selection" 段（插在 `select_all`（:298）与 `# mutations` 段之间）

```python
def has_block_selection(self) -> bool:
    """Return whether a rectangular (column) selection is active."""
    return self.block and self.has_selection()

def block_region(self) -> tuple[int, int, int, int] | None:
    """Return normalized block bounds ``(top, left, bottom, right)`` or ``None``.

    Columns are half-open character offsets; the right bound may exceed a
    short row's length -- callers clamp per row (rendering, deletion).
    """
    if not self.has_block_selection():
        return None
    assert self.anchor is not None
    r1, r2 = sorted((self.anchor[0], self.cursor[0]))
    c1, c2 = sorted((self.anchor[1], self.cursor[1]))
    return (r1, c1, r2, c2)

def begin_block_selection(self) -> None:
    """Anchor a rectangular selection at the current cursor position."""
    self.anchor = self.cursor
    self.block = True

def selected_block_text(self) -> str | None:
    """Return the block selection as newline-joined per-row fragments.

    Rows shorter than the left bound contribute an empty fragment; ``None``
    when no block selection is active.
    """
    region = self.block_region()
    if region is None:
        return None
    r1, c1, r2, c2 = region
    return "\n".join(self.lines[r][c1:c2] for r in range(r1, r2 + 1))

def yank_block(self, *, named: str | None = None) -> str | None:
    """Yank the block selection into a register (mirrors :meth:`delete_lines`).

    The unnamed write records ``register_block = True`` so a later
    :meth:`paste` re-lands the rectangle; named registers are pure internal
    storage.  ``None`` when no block selection is active.
    """
    text = self.selected_block_text()
    if text is None:
        return None
    if named is None:
        self.register = text
        self.register_block = True
    else:
        self.named_registers[named] = text
    return text

def delete_block(self, *, named: str | None = None) -> str | None:
    """Remove each covered row's block span; one ``"step"`` undo entry.

    Rows shorter than the span keep their text untouched.  The cursor lands
    at the clamped top-left corner and the selection is dropped.  The
    removed text is stored like :meth:`delete_lines` (unnamed writes set
    ``register_block = True``).
    """
    self._ensure_writable()
    region = self.block_region()
    if region is None:
        return None
    before = self._snapshot()
    text = self.selected_block_text() or ""
    r1, c1, r2, c2 = region
    for r in range(r1, r2 + 1):
        line = self.lines[r]
        start = min(c1, len(line))
        end = min(c2, len(line))
        if start < end:
            self.lines[r] = line[:start] + line[end:]
    self.anchor = None
    self.block = False
    self.cursor = (r1, min(c1, len(self.lines[r1])))
    if named is None:
        self.register = text
        self.register_block = True
    else:
        self.named_registers[named] = text
    self._commit(before, "step")
    return text

def insert_block(self, text: str) -> None:
    """Insert *text*'s newline-joined fragments at the cursor column.

    Fragment *i* lands on row ``cursor.row + i`` at the cursor column
    (clamped to that row's length), so a yanked block re-lands as a
    rectangle; missing rows are appended as empty lines.  One ``"step"``
    undo entry; the cursor ends on the first row's inserted text.
    """
    self._ensure_writable()
    fragments = text.split("\n")
    before = self._snapshot()
    r, c = self.cursor
    while len(self.lines) < r + len(fragments):
        self.lines.append("")
    for i, fragment in enumerate(fragments):
        row = self.lines[r + i]
        col = min(c, len(row))
        self.lines[r + i] = row[:col] + fragment + row[col:]
    self.anchor = None
    self.block = False
    self.cursor = (r, c + max(0, len(fragments[0]) - 1))
    self._commit(before, "step")

def replace_block(self, text: str) -> None:
    """Replace each covered row's block span with the matching fragment.

    Fragment *i* replaces row ``top + i``'s span; rows past the last
    fragment only lose their span (VS Code column-paste semantics).  One
    ``"step"`` undo entry; the cursor lands after the first fragment.
    """
    self._ensure_writable()
    region = self.block_region()
    if region is None:
        return
    before = self._snapshot()
    r1, c1, r2, c2 = region
    fragments = text.split("\n")
    for i, r in enumerate(range(r1, r2 + 1)):
        line = self.lines[r]
        start = min(c1, len(line))
        end = min(c2, len(line))
        fragment = fragments[i] if i < len(fragments) else ""
        self.lines[r] = line[:start] + fragment + line[end:]
    self.anchor = None
    self.block = False
    first = fragments[0] if fragments else ""
    self.cursor = (r1, min(c1 + len(first), len(self.lines[r1])))
    self._commit(before, "step")
```

### 4. `type_char` 块分支

`type_char`（:356-423）在可打印守卫（:384-387）之后、`sel = self.selection()`
（:389）之前插入：

```python
if self.has_block_selection():
    # Column typing replaces every covered row's span (VS Code semantics);
    # bracket auto-completion is a charwise affordance and stays off.
    self.replace_block(ch)
    return
```

### 5. `paste` 块分支

`paste`（:788-820）在空文本守卫（:798-799）之后插入：

```python
if self.register_block:
    self.insert_block(text)
    return
```

## 五、新增测试（tests/test_editor_core.py 追加；沿用文件内既有
`_FakeApp` / `TextBuffer` 直构风格）

| 用例名 | 前置与操作（arrange/act） | 断言（assert） |
|---|---|---|
| `test_block_region_normalizes_opposite_corners` | 3 行 `"abcd\nxy\nwxyz"`；`anchor=(0,2)`、`cursor=(2,1)`、`block=True` | `block_region() == (0, 1, 2, 2)`；`selected_block_text() == "bc\ny\nw"`（row1 右界夹取） |
| `test_begin_block_selection_then_extend_keeps_block_flag` | 光标 (1,1) 处 `begin_block_selection()`；`set_cursor((2,3), select=True)` | `has_block_selection() is True`；`block_region() == (1, 1, 2, 3)` |
| `test_charwise_selection_start_resets_block_flag` | `begin_block_selection()`；`set_cursor((0,0))`；`set_cursor((0,2), select=True)` | `has_block_selection() is False`（charwise 选区不吃残留块标志） |
| `test_clear_selection_resets_block_flag` | 建块选后 `clear_selection()` | `block is False`、`anchor is None` |
| `test_delete_block_removes_span_per_row_and_yanks` | `"abcd\nxy\nwxyz"`，块 (0,1,2,3)（用 begin+select 扩展构造） | `delete_block()` 返回 `"bc\ny\nyz"`；lines == `["ad", "x", "wz"]`；cursor == (0,1)；`register == "bc\ny\nyz"`；`register_block is True` |
| `test_delete_block_skips_rows_shorter_than_left_bound` | `"ab\nabcdef"`，块 (0,2,1,4) | row0 不变 `"ab"`；row1 → `"ab"`（start≥end 跳过）；返回 `"ab\n"` 段中 row0 片段为空串 |
| `test_insert_block_lands_fragments_at_same_column` | `"ab\ncd"`，cursor (0,1)，`insert_block("X\nYY")` | lines == `["aXb", "cYYd"]`；cursor == (0, 2) |
| `test_insert_block_appends_missing_rows` | 单行 `"ab"`，cursor (0,1)，`insert_block("x\ny\nz")` | 3 行，各行 col1 分别为 x/y/z |
| `test_replace_block_substitutes_each_row_span` | `"abcd\nefgh"`，块 (0,1,1,3)，`replace_block("Z\nWW")` | lines == `["aZd", "eWWh"]`；cursor == (0, 2) |
| `test_type_char_over_block_replaces_every_row` | 块 (0,1,1,3) 上 `type_char("#")` | 每行 span 变 `"#"`；单次 undo 可整体恢复 |
| `test_paste_after_block_yank_reinserts_rectangle` | `yank_block()` 后 `set_cursor((3, 2))`、`paste(below=True)` | 片段在第 3 行起、列 2 处按矩形落位 |
| `test_yank_lines_resets_register_block_flag` | 先 `yank_block()` 再 `yank_lines()` | `register_block is False`（标志卫生回归） |
| `test_delete_block_is_single_undo_step` | `delete_block()` 后 `undo()` | lines 恢复原值；`content_edits` 只减 1 |

反向路径：`has_block_selection` 在 `block=True` 但 anchor==cursor 时为
`False`（并入 `test_begin_block_selection_then_extend_keeps_block_flag` 前置
断言）；`delete_block`/`replace_block` 在无块选时返回 `None`/无操作
（`test_delete_block_skips_rows_shorter_than_left_bound` 之外补一个
`test_delete_block_without_selection_is_noop`：`delete_block() is None`、
undo 栈不变）。

## 六、验收命令（worktree 根，PowerShell）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_editor_core.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/editor_core/buffer.py tests/test_editor_core.py
```

通过判定：三条命令退出码 0；`test_editor_core.py` 原有用例零回归。

## 七、文档同步

- `.trae/rules/architecture-boundaries.md` §三.7 豁免名单中
  `editor_core/buffer.py` 的行数按 `len(content.splitlines())` 实测回填
  （守卫口径，`Get-Content | Measure-Object -Line` 不计空行，勿用）。

## 八、风险与回滚

- 风险：`anchor = None` 写点遗漏（§四.2 已枚举 8 处）→ 由 `test_*_resets_block_flag`
  与后续 wave 的渲染/键位用例兜底；`type_char` 块分支改变块选下打字行为——
  这是目标行为，现有测试无块选打字用例，零回归风险。
- 回滚：本计划独立 commit（`feat(editor-core): block selection model on TextBuffer`），
  `git revert` 单提交即可；无下游已合入时无连带。
