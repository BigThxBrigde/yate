# plan-c：vim 键位状态机修复

- 波次：wave-2（与 plan-d 并行）
- 覆盖：W-06 / W-08 / S-09 / S-10
- 独占文件清单：
  - `yate/keymaps/vim.py`
  - `tests/test_vim_keymap.py`
- 只改以上文件，不得动其它任何文件。

## 一、输入事实（已核对源码）

- W-06：[vim.py](../../yate/keymaps/vim.py) 第 738-740 行只在
  `last_find is not None` 时处理 `;`/`,`；否则落到 `_extension_binding`，
  表项第 163-164 行名为 `"find repeat"`，全仓无该 action。
- W-08：第 764-830 行 `u` / `ctrl-r` / `J` / `ctrl-d,u,f,b` / `i` / `o` / `O`
  分支均未清 `count_str`；`_enter_insert` 第 1121-1124 行只清
  `pending_register`；INSERT 的 Esc 第 447-452 行不清 pending。
- S-09：VISUAL 处理第 500-603 行无前缀状态，`g`/`f`/`F`/`t`/`T`/`r` 被吞。
- S-10：`_apply_operator` 第 1261-1300 行把 `j`/`k`/`G` 当字符 motion，
  `dj` 会留下半行。

## 二、分步修改

### 步骤 C1：W-06 无历史查找时消费 `;` / `,`

**文件**：`yate/keymaps/vim.py`

NORMAL 分支第 738-740 行改为：

```python
        if key in (";", ","):
            if self.last_find is None:
                ui.message("no previous find")
                return True
            self._repeat_find(ctx, key)
            return True
```

操作符 pending 分支第 906-908 行保持“有历史才重复”；无历史时走第 912-916 行
既有的“取消操作符并回落到 NORMAL”，随后被上面的 NORMAL 分支消费并提示。

### 步骤 C2：W-08 非 motion 命令清理 count

**文件**：`yate/keymaps/vim.py`

1. `u` / `ctrl-r` / `J` / `ctrl-d` / `ctrl-u` / `ctrl-f` / `ctrl-b` 七个分支：
   把 `self.pending_register = None` 改为 `self._clear_pending()`，保留
   `self._exit_multi(buf)` 与动作调用。
2. `_enter_insert`（第 1121 行起）改为：

```python
    def _enter_insert(self, ui: KeyUi) -> None:
        self._clear_pending()  # i/o/O/c must not leak a typed count
        self.mode = VimMode.INSERT
        ui.message("-- INSERT --")
```

3. INSERT 的 Esc 分支（第 447-452 行）在 `buf.clear_extra_cursors()` 后加
   `self._clear_pending()`。

### 步骤 C3：S-09 VISUAL 前缀与查找重复

**文件**：`yate/keymaps/vim.py`

1. `_resolve_find` 增加关键字参数 `select: bool = False`；当 `op is None` 时：

```python
        if op is None:
            buf.set_cursor(target, select=select)
            return
```

   NORMAL/操作符调用保持默认 `select=False`。

2. VISUAL 处理中，在寄存器分支之后、`_SHIFT_KEYS` / 通用 motion 之前插入：

```python
        if self.prefix == "g" and key == "g":
            self._resolve_visual_gg(ctx)
            return True
        if self.prefix in ("f", "F", "t", "T") and len(key) == 1 and key.isprintable():
            self._resolve_find(
                ctx,
                key,
                backward=self.prefix in ("F", "T"),
                till=self.prefix in ("t", "T"),
                select=True,
            )
            if self.mode == VimMode.VISUAL_LINE:
                self._fix_linewise(buf)
            return True
        if self.prefix == "r" and len(key) == 1 and key.isprintable():
            self._resolve_visual_replace(ctx, key)
            return True
        if self.prefix is not None:
            self.prefix = None  # unknown follower: process as a fresh key
        if key in _PREFIX_KEYS:
            self.prefix = key
            return True
        if key in (";", ","):
            if self.last_find is not None:
                ch, backward, till = self.last_find
                if key == ",":
                    backward = not backward
                self._resolve_find(
                    ctx, ch, backward=backward, till=till,
                    record=False, select=True,
                )
                if self.mode == VimMode.VISUAL_LINE:
                    self._fix_linewise(buf)
            return True
```

3. 新增两个辅助方法（放在 `_handle_visual` 之后）：

```python
    def _resolve_visual_gg(self, ctx: ActionContext) -> None:
        """Complete ``gg`` in VISUAL: extend the selection to line 1/count."""
        self.prefix = None
        buf = ctx.buffer
        typed = self._typed_count()
        self.count_str = ""
        target = min((typed or 1) - 1, len(buf.lines) - 1)
        buf.set_cursor((target, first_non_blank(buf.lines[target])), select=True)
        if self.mode == VimMode.VISUAL_LINE:
            self._fix_linewise(buf)

    def _resolve_visual_replace(self, ctx: ActionContext, ch: str) -> None:
        """Replace every selected character with *ch* (vim visual ``r``)."""
        self.prefix = None
        buf = ctx.buffer
        sel = buf.selection()
        if sel is None or sel[0] >= sel[1]:
            ctx.ui.message("nothing to replace")
            return
        (r0, c0), (r1, c1) = sel
        parts: list[str] = []
        for row in range(r0, r1 + 1):
            line = buf.lines[row]
            start = c0 if row == r0 else 0
            end = c1 if row == r1 else len(line)
            parts.append(ch * max(0, end - start))
        buf.replace_range((r0, c0), (r1, c1), "\n".join(parts))
        self.mode = VimMode.NORMAL
        ctx.ui.message("replaced selection")
```

4. VISUAL 的 Esc / `v` 退出 / `V` 切换分支各加 `self.prefix = None`。

### 步骤 C4：S-10 `j`/`k`/`G` 整行操作符

**文件**：`yate/keymaps/vim.py`

1. `_apply_operator` 在 `self._clear_operator()` 之后、`start = buf.cursor` 之前加：

```python
        if code in ("j", "k", "G"):
            self._apply_vertical_operator(ctx, op, code, count, reg)
            return
```

2. 新增辅助方法（放在 `_apply_span` 之前）：

```python
    def _apply_vertical_operator(
        self, ctx: ActionContext, op: str, code: str, count: int | None,
        reg: str | None,
    ) -> None:
        """Run a linewise operator over ``j`` / ``k`` / ``G`` (vim semantics)."""
        buf = ctx.buffer
        ui = ctx.ui
        row = buf.row
        col = buf.col
        if code == "G":
            target = (count - 1) if count is not None else len(buf.lines) - 1
            target = max(0, min(target, len(buf.lines) - 1))
            r1, r2 = sorted((row, target))
        elif code == "j":
            r1 = row
            r2 = min(row + (count or 1), len(buf.lines) - 1)
        else:
            r1 = max(row - (count or 1), 0)
            r2 = row
        buf.anchor = (r1, 0)
        buf.cursor = (r2, len(buf.lines[r2]))
        if op == "y":
            self._mirror(buf.yank_lines(named=reg), reg)
            buf.anchor = None
            buf.cursor = (r1, min(col, len(buf.lines[r1])))
            ui.message("yanked")
            return
        if op == "d":
            self._mirror(buf.delete_lines(named=reg), reg)
            ui.message("deleted")
            return
        self._store_deleted(buf, buf.delete_selection(), reg)
        self._enter_insert(ui)
```

行为：`dj` 删除当前行与下一行；`dk` 删除上一行与当前行；`dG` 删除当前行到末行
（带 count 时删除到第 count 行）；`yj` / `cj` 对应整行 yank / change。

## 三、新增测试（`tests/test_vim_keymap.py`）

1. `test_semicolon_without_a_previous_find_is_consumed`
   - 准备：`_setup("abc")`
   - 操作：`_press(keymap, ctx, ";")`
   - 断言：`editor.messages[-1] == "no previous find"`；
     `"unknown action"` 不在消息中；文本不变。
2. `test_normal_commands_drop_a_leaked_count`
   - 参数化动作序列：`("3", "u")`、`("3", "J")`、`("3", CTRL_D)`。
   - 每组后按 `"x"`，断言只删 1 个字符。
3. `test_insert_entry_and_escape_drop_a_pending_count`
   - 准备：`"abcdef"`；操作：`"3", "i", "X", ESC, "x"`
   - 断言：最终文本 `"bcdef"`（插入的 X 被删，未一次删 3 字符）。
4. `test_visual_find_extends_the_selection`
   - 准备：`"a.b.c.d"`；操作：`"v", "f", "."`；断言 `buf.selection()` 覆盖
     列 0..1；再 `"d"` 后文本 `"b.c.d"`。
5. `test_visual_semicolon_repeats_the_find_and_extends`
   - 准备：`"a.b.c.d"`；操作：`"v", "f", ".", ";"`
   - 断言：`buf.cursor == (0, 3)` 且 anchor 仍在 `(0, 0)`。
6. `test_visual_gg_extends_to_the_first_line`
   - 准备：`"alpha\nbeta\ngamma"`，光标 `(2, 0)`；操作：`"v", "g", "g"`
   - 断言：`buf.cursor[0] == 0`；随后 `"d"` 删除整个跨行选区。
7. `test_visual_r_replaces_every_selected_character`
   - 准备：`"abcd"`；操作：`"v", "l", "l", "r", "X"`
   - 断言：文本 `"XXXd"`、模式回到 NORMAL。
8. `test_dj_deletes_two_whole_lines`
   - 准备：`"alpha\nbeta\ngamma"`；操作：`"d", "j"`
   - 断言：文本 `"gamma"`、寄存器 `"alpha\nbeta\n"`。
9. `test_dk_deletes_the_previous_and_current_lines`
   - 准备：`"alpha\nbeta\ngamma"`，光标行 1；操作：`"d", "k"` → `"gamma"`。
10. `test_dG_deletes_to_the_last_line`
    - 准备：`"alpha\nbeta\ngamma"`，光标行 1；操作：`"d", "G"` → `"alpha"`。
11. `test_counted_dj_deletes_three_lines`
    - 准备四行；操作：`"d", "2", "j"` → 删除前三行。

## 四、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_vim_keymap.py -q
.venv\Scripts\python.exe -m pyright yate/keymaps/vim.py tests/test_vim_keymap.py
```

通过判定：两条命令退出码均为 0。

## 五、风险与回滚

- `_apply_vertical_operator` 仅拦截 `j`/`k`/`G`，`dw`/`d$`/`de` 等字符操作不变。
- `visual r` 会一次替换整个选区，属新增能力，不改变现有键位。
- `_enter_insert` 改为 `_clear_pending()` 会同时清空操作符/前缀；所有调用点都
  在“进入 insert”前已消费操作符，语义一致。
- 回滚：本子计划单独提交。
