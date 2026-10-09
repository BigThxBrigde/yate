# multi-cursor plan-a：TextBuffer 多光标模型与多点原语（L0）

> wave-1。依赖：无。总纲见 `overview.md`。
> 输入：总纲 §四.4（模型事实）、§四.1（undo 事实）、本文件 §二。

## 一、输入

- `yate/editor_core/buffer.py`（820 行，豁免名单内）：
  `_Snapshot`（:44-48）、`_snapshot/_restore/_commit`（:164-201）、
  公共事务 `snapshot()/commit()`（:209-215）、`set_cursor`（:276-291）、
  `_delete_range`（:301-309）、`insert_text`/`_apply_text`
  （:311-339）、`type_char`（:356-423）、`delete_backward`（:478-513）。
- `tests/test_editor_core.py`（既有 undo/selection 用例风格）。

## 二、独占文件清单

只改以下文件，不要动其它任何文件：

| 文件 | 改动 |
|---|---|
| `yate/editor_core/buffer.py` | 模型字段 + 4 个多点方法 + `_apply_text`/`_delete_range` 参数化 |
| `tests/test_editor_core.py` | 新增 `TestMultiCursor` 用例组（§四） |
| （行数回填不在此做——统一归 plan-e，避免与 wave-2 子计划争抢规则文件） | |

## 三、具体修改（yate/editor_core/buffer.py）

### 3.1 模型字段

1. `__init__`（:66-103）在 `self.anchor: Pos | None = None`（:76）之后加：

   ```python
   #: Additional multi-cursor points (issue IKKJHH).  Empty list = the
   #: regular single-cursor behaviour everywhere.  Points are bare
   #: ``(row, col)`` cursors without anchors -- multi-cursor selections
   #: are a non-goal -- and the primary cursor stays :attr:`cursor`, so
   #: every existing consumer keeps working unchanged.
   self.extra_cursors: list[Pos] = []
   ```

2. `_Snapshot`（:44-48）追加带默认值字段（现有位置构造
   `_Snapshot(tuple(self.lines), self.cursor, self.anchor)` 全部保持兼容）：

   ```python
   @dataclass
   class _Snapshot:
       lines: tuple[str, ...]
       cursor: Pos
       anchor: Pos | None
       #: Multi-cursor points captured with the lines (empty = single cursor).
       extra_cursors: tuple[Pos, ...] = ()
   ```

   `==` 比较自动包含点集合：`_commit` 的 no-op 判定（:178）与
   `"char"` 合并判定（:187）语义随快照自动扩展，无需改动。

### 3.2 快照读写

- `_snapshot`（:164-165）：`extra_cursors` 填 `tuple(self.extra_cursors)`。
- `_restore`（:167-174）：恢复 `self.extra_cursors = list(snap.extra_cursors)`
  后逐点 clamp（行号夹到 `[0, len(lines)-1]`，列夹到 `[0, len(lines[r])]`），
  与 `set_cursor` 的夹取同规；越界点**静默夹取**不丢弃（undo 后文档可能
  变短，点保留在最近合法位置符合 VS Code 行为）。
- `set_text`（:135-145）：清 `self.extra_cursors`（内容整体替换，点必失
  效），与 `self.anchor = None`（:140）并排。

### 3.3 底层原语参数化（内部重构，公共语义不变）

- `_delete_range(self, start: Pos, end: Pos) -> None`（:301-309）：
  **签名不变**，仅移除末尾的 `self.cursor = (r1, c1)`（:309）——该副作用
  是单点语义，挪到调用方（`insert_text` :320、`type_char` :404、
  `delete_selection` :473、`delete_to_line_start` :784 在 `_delete_range`
  调用后显式设 `self.cursor`；`replace_range` :351 在调用前已
  `self.cursor = start`（:349），行为等价）。每处调用点逐一核对：调用后
  若原代码依赖 `:309` 的游标副作用则显式补 `self.cursor = start`。
- `_apply_text(self, text: str) -> None`（:325-339）改为
  `_apply_text(self, text: str, pos: Pos) -> Pos`：以 *pos* 为插入位置，
  返回插入后的新位置；原 `self.cursor` 读写（:327、:332-339）替换为局部
  `r, c = pos` 与返回值。调用方（`insert_text` :321、`type_char` :405/:419、
  `replace_range` :352）改为：

  ```python
  self.cursor = self._apply_text(text, self.cursor)
  ```

  （`replace_range` 处 `self.cursor` 已是 start，同形。）

### 3.4 多点公共方法（新增，紧跟 `clear_selection` :272-274 之后）

```python
def add_cursor_at(self, pos: Pos) -> bool:
    """Add a multi-cursor point at *pos*; ``False`` when it already exists.

    Entering multi-cursor mode clears the primary selection (the anchor),
    keeping the two state axes (selection vs extra cursors) exclusive.
    *pos* is clamped exactly like :meth:`set_cursor`.
    """

def add_cursor_below(self) -> bool:
    """Add a cursor on the next row at the last point's column.

    The "last point" is the bottom-most of the primary cursor and the
    extra cursors, so repeated ``ALT+C`` walks downward one point per
    press.  ``False`` (no-op) when there is no next row.
    """

def clear_extra_cursors(self) -> None:
    """Drop every extra multi-cursor point (back to single cursor)."""

def has_extra_cursors(self) -> bool:
    """Whether multi-cursor mode is active (any extra point exists)."""
```

### 3.5 多点编辑原语（新增，紧跟 `delete_forward` :515-533 之后）

```python
def _multi_points(self) -> list[Pos]:
    """All active points (primary first, then extras), deduplicated and
    clamped.  Primary is always present; extras equal to the primary are
    dropped so one physical location never edits twice."""

def insert_at_points(self, text: str, kind: str = "char") -> None:
    """Insert *text* at every active point as ONE undo step.

    Points are processed in descending (row, col) order so an insertion
    containing newlines never invalidates a not-yet-processed point's
    position; the primary cursor ends at its own post-insert position.
    No bracket auto-completion (a single-cursor ``type_char`` affordance).
    Read-only buffers raise :class:`BufferReadOnlyError`.
    """

def delete_at_points(self) -> None:
    """Delete one character before every active point as ONE undo step.

    At column 0 the point joins the previous row (newline deletion);
    (0, 0) is a no-op for that point.  Descending order, deduplicated.
    """

def delete_forward_at_points(self) -> None:
    """Delete one character after every active point as ONE undo step.

    At end-of-row the point joins the next row; end of document is a
    no-op for that point.
    """
```

实现要点（写代码时遵守）：

1. 每个公共原语：`_ensure_writable()` → `before = self._snapshot()` →
   降序逐点 `_delete_range`/`_apply_text`（**不设 cursor**，仅收集每点
   新位置）→ 主点/附加点位置回写 → `self._goal_col = None` →
   `self._commit(before, kind)`（打字用 `"char"` 以便与相邻击键合并）。
2. `_commit` 自动处理 `content_version`/`content_edits`（:199-201）。
3. 插入 `\n` 时各点独立换行，无缩进（已知限制，docstring 注明）。
4. 行数用现有 `log.debug` 惰性 `%` 风格记录（R12），消息如
   `log.debug("multi-cursor insert: points=%d", len(points))`。

## 四、测试用例（tests/test_editor_core.py，新增类 `TestMultiCursor`）

测试命名 `test_<behavior>_<condition>_<expected>`；构造器统一
`TextBuffer("alpha beta\ngamma delta\nepsilon zeta")`（3 行样例）。

| 用例名 | arrange | act | assert |
|---|---|---|---|
| `test_add_cursor_at_clamps_and_clears_selection` | `set_cursor((0,1), select=True)` 建选区 | `add_cursor_at((0, 99))` | 返回 `True`；`extra_cursors == [(0, 10)]`（列夹到行长）；`anchor is None`；`has_extra_cursors() is True` |
| `test_add_cursor_at_rejects_duplicate_point` | `add_cursor_at((0, 5))` | 再次 `add_cursor_at((0, 5))` | 第二次返回 `False`；`extra_cursors == [(0, 5)]`（不重复） |
| `test_add_cursor_below_walks_down_from_bottom_most_point` | 初始光标 (0,2) | `add_cursor_below()` → `add_cursor_below()` | 第一次返回 `True` 且 `extra_cursors == [(1, 2)]`；第二次 `extra_cursors == [(1, 2), (2, 2)]`（从最底点 (1,2) 再下一行）；`cursor` 仍 `(0, 2)` |
| `test_add_cursor_below_at_last_row_is_noop` | 光标在末行 (2,0) | `add_cursor_below()` | 返回 `False`；`extra_cursors == []` |
| `test_clear_extra_cursors_restores_single_cursor` | 两个附加点 | `clear_extra_cursors()` | `extra_cursors == []`；`cursor`/`anchor` 不变 |
| `test_insert_at_points_single_char_edits_all_rows` | 光标 (0,0) + `add_cursor_below()` ×2（三点 (0,0)(1,0)(2,0)） | `insert_at_points("X")` | `lines == ["Xalpha beta", "Xgamma delta", "Xepsilon zeta"]`；`cursor == (0, 1)`（主点前移）；`extra_cursors == [(1, 1), (2, 1)]` |
| `test_insert_at_points_descending_order_with_newline` | 三点 (0,0)(1,0)(2,0) | `insert_at_points("\n")` | `line_count == 6`；每原行上方多一个空行（`lines[0] == ""`、`lines[1] == "alpha beta"`、`lines[2] == ""` …）；降序处理保证 (2,0) 点不因前两点插行而错位 |
| `test_insert_at_points_same_row_two_points_no_double_edit` | `add_cursor_at((0, 5))` + `add_cursor_at((0, 8))`（同行两点） | `insert_at_points("-")` | `lines[0] == "alpha- beta-"`（列大先插，两点都生效且互不错位） |
| `test_insert_at_points_is_one_undo_step` | 三点 | `insert_at_points("X")` 后 `undo()` | 一次 `undo` 后 `lines` 完全复原且 `extra_cursors` 复原（快照含点集合）；`content_edits` 增量与单点打字相同（1） |
| `test_insert_at_points_coalesces_with_adjacent_typing` | 三点 | `insert_at_points("a")`; `insert_at_points("b")`; `undo()` | 一次 undo 撤掉两个字符（`"char"` 合并语义）：`lines` 回到只插了 0 次的状态；再 `redo()` 恢复两字符 |
| `test_delete_at_points_backspace_joins_rows_at_column_zero` | 三点 (0,1)(1,1)(2,1) | `delete_at_points()` | `lines == ["lpha beta", "amma delta", "psilon zeta"]`；`cursor == (0, 0)` |
| `test_delete_at_points_at_document_origin_is_noop_for_that_point` | 点 (0,0) + `add_cursor_at((1, 3))` | `delete_at_points()` | (0,0) 点不动、(1,3) 点删 "m"；`lines == ["alpha beta", "gama delta", "epsilon zeta"]`；一次 undo 完整复原 |
| `test_delete_forward_at_points_at_row_end_joins_next_row` | 点 (0, len("alpha beta")) + 附加点 (2,0) | `delete_forward_at_points()` | (0,EOL) 点合并下一行：`lines[0] == "alpha betagamma delta"`；(2,0) 点删 "e" |
| `test_undo_restores_extra_cursors_clamped_after_shrink` | 三点；`insert_at_points("\n" * 3)` 制造 6 行 | `undo()` | `extra_cursors` 全部回到合法位置（clamp 断言：每点 `pos[0] < line_count`）；无 IndexError |
| `test_set_text_clears_extra_cursors` | 两附加点 | `set_text("new")` | `extra_cursors == []`；`cursor == (0, 0)` |
| `test_insert_at_points_on_read_only_raises` | `TextBuffer(read_only=True)` + 一附加点 | `pytest.raises(BufferReadOnlyError)` 包住 `insert_at_points("X")` / `delete_at_points()` | 两个原语都抛 `BufferReadOnlyError`，buffer 内容不变 |

**既有回归重点**（`_delete_range` 副作用挪动、`_apply_text` 签名变化的
爆炸半径）：`tests/test_editor_core.py` 既有全部用例 + `tests/test_vim_keymap.py`
+ `tests/test_action_table.py` + `tests/test_input_assist.py`
（type_char 路径）必须全绿。

**验证命令**（每步验收 + wave-1 收尾）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_editor_core.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pyright yate/editor_core/ tests/test_editor_core.py
```

## 五、风险与回滚

| 风险 | 缓解 |
|---|---|
| `_delete_range` 去掉 cursor 副作用后某个调用点漏补 | §3.3 列全 4 个调用点逐一核对；全量 pytest 回归兜底 |
| 降序处理遗漏同行去重 | `_multi_points` 去重 + 专项用例（同行两点） |
| buffer.py 膨胀 | 预估 +~180 行 → ~1000 行，豁免名单内；plan-e 回填规则文本 |
| 回滚 | 本子计划独立 commit `feat(editor-core): multi-cursor model on TextBuffer`；`git revert` 即净 |

## 六、验收标准（本子计划完成判定）

1. §四 全部新用例通过，`pytest tests/test_editor_core.py -q` 退出码 0；
2. `pytest tests/ -q` 全绿（既有回归无破坏）；
3. `pyright yate/editor_core/` 零诊断；
4. `pytest tests/test_architecture.py -q` 28 passed（`buffer.py` 仍在
   `SIZE_EXEMPT_FILES`，无新豁免）。
