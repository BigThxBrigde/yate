# plan-a — L1 会话模型：MarkBook / JumpList / push_jump（wave-1）

父文档：[overview.md](overview.md)。输入：overview 调研事实 F5、设计决策
D2/D3/D4/D7。

## 目标与非目标

- 目标：在 `yate/session.py`（L1，UI-free）内实现 marks（按 `Document.uid` 键控、
  a-z、同名覆盖、关闭清理）与会话级 jump list（双栈 back/forward、容量 100、
  连续同位置去重、关闭剪枝），暴露唯一推入契约 `EditorSession.push_jump()` 与
  两个导航动词 `jump_back()/jump_forward()`。
- 非目标：任何 UI/键位/流程接线（plan-b/c/d 负责）；持久化；精确列平移（D3）。

## 独占文件清单（只改这些，不要动其它任何文件）

- `yate/session.py`
- `tests/test_marks_session.py`（新建）

## 具体修改（定位到行号）

### 1. `yate/session.py`：新模型类型（插在 `MacroState` 之后、`log = ...`（L70）之前）

紧邻 `MacroState`（L46-67）同类会话级状态先例，新增（全部 `from __future__
import annotations` 已在文件头 L24）：

```python
#: Legal single-character mark names (v1: lowercase letters only). Lives
#: here (L1) instead of keymaps/keys.py so the L3 command table can import
#: it downward without a cross-L3 module dependency.
MARK_NAME_CHARS: str = "abcdefghijklmnopqrstuvwxyz"

#: Capacity of each jump-list stack (issue IKUOCI: 100).
JUMP_LIST_LIMIT: int = 100


@dataclass(frozen=True)
class Mark:
    """One buffer-local named mark: an exact buffer position (row, col)."""

    row: int
    col: int


class MarkBook:
    """Per-buffer named marks keyed by ``Document.uid`` (L1, UI-free)."""

    def __init__(self) -> None:
        self._by_doc: dict[int, dict[str, Mark]] = {}

    def set(self, uid: int, name: str, row: int, col: int) -> None:
        """Set (or overwrite) mark *name* on document *uid* at (row, col)."""
        if len(name) != 1 or name not in MARK_NAME_CHARS:
            raise ValueError(f"mark name must be one of a-z: {name!r}")
        self._by_doc.setdefault(uid, {})[name] = Mark(row, col)

    def get(self, uid: int, name: str) -> Mark | None:
        """The mark *name* on *uid*, or ``None``."""
        return self._by_doc.get(uid, {}).get(name)

    def delete(self, uid: int, name: str) -> bool:
        """Delete mark *name* on *uid*; ``False`` when it was not set."""
        marks = self._by_doc.get(uid)
        if marks is None or name not in marks:
            return False
        del marks[name]
        return True

    def drop_doc(self, uid: int) -> None:
        """Drop every mark of document *uid* (buffer close cleanup)."""
        self._by_doc.pop(uid, None)

    def all_marks(self) -> list[tuple[int, str, Mark]]:
        """Every mark as ``(uid, name, mark)`` rows, ordered by doc then name."""
        rows: list[tuple[int, str, Mark]] = []
        for uid in self._by_doc:
            for name in sorted(self._by_doc[uid]):
                rows.append((uid, name, self._by_doc[uid][name]))
        return rows


@dataclass(frozen=True)
class JumpEntry:
    """One jump-list entry: where a jump started (resolved via uid)."""

    uid: int
    path: str  # display string ("[no name]" for scratch buffers)
    row: int
    col: int


class JumpList:
    """Session-level jump history: a back stack and a forward stack (L1).

    Producers call :meth:`push` with the position a jump *leaves*;
    navigation pops one stack while pushing the current position onto the
    other, so alt-left/alt-right round-trip and boundaries are empty stacks
    (no looping, no pointer arithmetic).
    """

    def __init__(self) -> None:
        self._back: list[JumpEntry] = []
        self._forward: list[JumpEntry] = []

    def push(self, origin: JumpEntry) -> None:
        """Record *origin* as the position a new jump leaves behind.

        A new jump discards the forward branch; pushing the same position
        consecutively dedups (the forward branch still clears).
        """
        self._forward.clear()
        if self._back and self._back[-1] == origin:
            return
        self._back.append(origin)
        if len(self._back) > JUMP_LIST_LIMIT:
            del self._back[0]

    def take_back(self, current: JumpEntry) -> JumpEntry | None:
        """Pop the newest back entry; *current* becomes forward-reachable."""
        if not self._back:
            return None
        target = self._back.pop()
        self._forward.append(current)
        if len(self._forward) > JUMP_LIST_LIMIT:
            del self._forward[0]
        return target

    def take_forward(self, current: JumpEntry) -> JumpEntry | None:
        """Pop the newest forward entry; *current* becomes back-reachable."""
        if not self._forward:
            return None
        target = self._forward.pop()
        self._back.append(current)
        if len(self._back) > JUMP_LIST_LIMIT:
            del self._back[0]
        return target

    def drop_docs(self, uids: set[int]) -> None:
        """Prune entries whose document closed (buffer close cleanup)."""
        self._back = [e for e in self._back if e.uid not in uids]
        self._forward = [e for e in self._forward if e.uid not in uids]

    def stacks(self) -> tuple[list[JumpEntry], list[JumpEntry]]:
        """ ``(back, forward)`` snapshots for the :jumps view (back is
        oldest-to-newest; the current position sits between the stacks)."""
        return (list(self._back), list(self._forward))
```

### 2. `yate/session.py`：`EditorSession` 持有 + 推入/导航契约

- `__init__`（L76-92）：在 `self.macro = MacroState()`（L92）之后加
  `self.marks = MarkBook()` 与 `self.jumps = JumpList()`。
- documents 区（`reset_search` L215 之后、`cycle` L219 之前）新增四个方法：

```python
    def doc_by_uid(self, uid: int) -> Document | None:
        """The open document with *uid*, or ``None`` (closed buffers)."""
        for doc in self.docs:
            if doc.uid == uid:
                return doc
        return None

    def _current_entry(self) -> JumpEntry:
        """The active document's cursor as a jump-list entry."""
        doc = self.doc
        return JumpEntry(
            doc.uid, doc.display_path, doc.buffer.row, doc.buffer.col
        )

    def push_jump(
        self, doc: Document | None = None, *, row: int | None = None,
        col: int | None = None,
    ) -> None:
        """Record the position a jump leaves behind (the single push contract).

        Defaults capture the active document's cursor.  Jump producers --
        mark jumps, ``:42``/ctrl-g line jumps, and the future LSP
        goto-definition flow -- call only this; the stacks are L1-internal.
        """
        origin_doc = doc if doc is not None else self.doc
        r = origin_doc.buffer.row if row is None else row
        c = origin_doc.buffer.col if col is None else col
        self.jumps.push(
            JumpEntry(origin_doc.uid, origin_doc.display_path, r, c)
        )

    def jump_back(self) -> JumpEntry | None:
        """Step one entry back; ``None`` at the boundary (empty back stack)."""
        return self.jumps.take_back(self._current_entry())

    def jump_forward(self) -> JumpEntry | None:
        """Step one entry forward; ``None`` at the boundary."""
        return self.jumps.take_forward(self._current_entry())
```

### 3. `yate/session.py`：关闭清理（AC5 后半）

- `close_active`（L229-249）：在 `closed.chunked = None`（L240）之后、
  `log.debug`（L241）之前插入：
  `self.marks.drop_doc(closed.uid)` 与
  `self.jumps.drop_docs({closed.uid})`。
- `close_under`（L251-277）：在 `for doc in closed: doc.chunked = None`
  （L274-275）循环内各文档追加 `self.marks.drop_doc(doc.uid)`；循环后追加
  `self.jumps.drop_docs({doc.uid for doc in closed})`。

## 新增测试（tests/test_marks_session.py，全部纯 L1，无 Textual）

fixture：`_session()` 用 `YateConfig()` + 两个手工 `Document`（`doc.buffer`
直接 `set_cursor` 造位），不依赖盘上文件；跳转后位置由测试手工写
`buffer.set_cursor`（L3 导航接线在 plan-c，此处只验证模型语义）。

| 用例 | 前置/操作/断言 |
|---|---|
| `test_markbook_set_get_overwrite` | set(uid=1,"a",5,2) 两次不同位 → get 返回第二次 (5,2) |
| `test_markbook_rejects_illegal_name` | set(uid=1,"A",0,0) / set(uid=1,"ab",0,0) → 均抛 `ValueError`；get("A") 为 None |
| `test_markbook_delete_returns_false_for_missing` | 未 set 直接 delete → 返回 False；set 后 delete → True 且 get 为 None；二次 delete → False（AC6 重复删除基础） |
| `test_markbook_drop_doc_removes_all_marks` | uid=1 set a/b，uid=2 set a → drop_doc(1) → all_marks 只剩 uid=2 一行；names 有序（a 在 b 前） |
| `test_push_jump_records_active_cursor` | docA 光标 (0,0)，push_jump() → `jumps.stacks()[0][-1]` 为 `(uidA, display_path, 0, 0)` |
| `test_push_jump_dedups_consecutive_same_position` | 同位 push 两次 → back 长 1 |
| `test_push_jump_clears_forward_branch` | push X → jump_back（手工把光标移到 Y 先）→ forward=[X] → 再 push Z → forward 空、back=[X,Z] |
| `test_jump_back_roundtrip_then_boundary` | 光标 A push（模拟跳转）→ 光标移到 B → jump_back() 返回 A 条目；再 jump_back() 返回 None；jump_forward() 返回 B 条目；再 jump_forward() 返回 None（AC2 边界不循环） |
| `test_jump_list_trims_to_limit` | push 120 个不同 row 的条目 → back 长 100 且 back[0].row == 20（最老被裁） |
| `test_close_active_drops_marks_and_jumps` | 两 doc：doc1 set 标记 + push 条目 → close_active()（关 doc1）→ `doc_by_uid(uid1)` None、`marks.all_marks()` 空、`jumps.stacks()` 两栈均不含 uid1（AC5） |
| `test_close_under_drops_marks_and_jumps` | 两 doc 同目录不同文件（临时目录内 tmp_path）→ close_under(dir) → 同上断言 |
| `test_doc_by_uid_roundtrip` | doc_by_uid(存在 uid) 返回该 doc；doc_by_uid(999) 返回 None |

正反路径覆盖：正常流（set/get/jump 往返）、边界（空栈、裁剪、非法名、
重复删除）、异常流（ValueError、关闭后清理）。

## 验证方案与验收命令

- 验证目标：marks/jumps 语义（AC2/AC3/AC5 的模型面）、R4（session.py 保持
  UI-free，不加任何 import）、体量（session.py 466 → 约 620 行 < 800）。
- 命令（worktree 根，PowerShell）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_marks_session.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/session.py tests/test_marks_session.py
```

- 通过判定：三条命令退出码 0；架构测试全绿（session.py 已在 UI_FREE_FILES
  守卫面，加错 import 会失败）；pyright strict 零诊断。

## 风险与回滚

- 风险1：session.py 增量过大破坏单一职责 → 新类型都是会话级文档模型状态
  （`MacroState` 同类先例），增量后约 620 行 < 800（F11 口径），无需豁免。
- 风险2：`JumpEntry` 冻结 dataclass 的 eq 语义被误用（path 变化导致去重失效）
  → 去重按全字段相等；doc 重定向（retarget）后旧条目仍按 uid 解析，path 仅展示。
- 回滚：`git checkout -- yate/session.py` + 删除 `tests/test_marks_session.py`；
  无其它文件牵连（独占清单保证）。
