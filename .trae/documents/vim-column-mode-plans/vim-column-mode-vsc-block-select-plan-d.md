# vim-column-mode 子计划 d：vsc 列选择动作与块感知剪贴板（wave-2）

> 输入：plan-a 的块 API；plan-b 的 `<alt-shift-*>` 可解析。依赖：a、b 已合入。

## 一、目标

1. 动作表新增 `select_block_left/right/up/down`：首按在光标处起块，续按扩展；
2. `yate/keymaps/vsc.py` 绑定 `Alt+Shift+方向键`（raw `\x1b[1;4A..D`）；
3. 内置 `copy`/`cut`/`paste` 动作块感知：块选下复制取矩形文本、剪切删矩形、
   粘贴按 VS Code 语义逐行替换。

## 二、非目标

- vim 键位不动（plan-c）；`Ctrl+V` 在 vsc 保持 paste（:85，不改）；
- 鼠标路径不动（plan-f）。

## 三、独占文件清单

- `yate/actions.py`
- `yate/keymaps/vsc.py`
- `tests/test_action_table.py`（追加）
- `tests/test_vsc_keymap.py`（追加）

## 四、具体修改

### 1. `yate/actions.py`

#### 1a. selection 段（:78-99）新增块扩展动作

文件顶部 import 区（:13-19）补 `from yate.editor_core.buffer import TextBuffer`。
selection 段尾部（`clear_selection` :99 之前）插入：

```python
    def _block_extend(move: Callable[[TextBuffer], None]) -> Callable[[ActionContext], None]:
        """Build a column-selection action: anchor on first use, extend after."""
        def run(ctx: ActionContext) -> None:
            buf = ctx.buffer
            if not buf.has_block_selection():
                buf.begin_block_selection()
            move(buf)
        return run

    reg("select_block_left",
        _block_extend(lambda buf: buf.move_left(select=True)),
        "Extend column selection left")
    reg("select_block_right",
        _block_extend(lambda buf: buf.move_right(select=True)),
        "Extend column selection right")
    reg("select_block_up",
        _block_extend(lambda buf: buf.move_up(select=True)),
        "Extend column selection up")
    reg("select_block_down",
        _block_extend(lambda buf: buf.move_down(select=True)),
        "Extend column selection down")
```

`Callable` 需补 `from collections.abc import Callable`（:12 附近）。
类型注解完整（pyright strict）；不新增类型别名（回调别名守卫：这是内联
参数形态，非模块级别名，`test_callable_aliases_use_type_statements` 放行）。

#### 1b. `cut`（:106-127）

`if buf.has_selection():` 分支前插块分支：

```python
        if buf.has_block_selection():
            text = buf.delete_block() or ""
            if text:
                clipboard.copy_text(text)
            return
```

（`delete_block(named=None)` 已写 `buf.register` + `register_block=True`。）

#### 1c. `copy`（:129-140）

`if buf.has_selection():` 分支前插：

```python
        if buf.has_block_selection():
            text = buf.selected_block_text() or ""
            if text:
                buf.register = text
                buf.register_block = True
                clipboard.copy_text(text)
            return
```

#### 1d. `paste`（:142-155）

`buf.read_only` 守卫之后、`buf.paste()` 之前插：

```python
        if buf.has_block_selection():
            text = clipboard.paste_text()
            if text is None or text == "":
                text = buf.register
            buf.replace_block(text)
            return
```

语义：块选 + 多行剪贴板 → 逐行替换矩形（VS Code 列粘贴）；剪贴板不可用回退
内部寄存器。

### 2. `yate/keymaps/vsc.py` — selection 段（:70-79）追加四条

plan-b 后 `_k` 可直接解析 spec：

```python
            _k("<alt-shift-left>", "select_block_left",
                "Extend column selection left", SEL),
            _k("<alt-shift-right>", "select_block_right",
                "Extend column selection right", SEL),
            _k("<alt-shift-up>", "select_block_up",
                "Extend column selection up", SEL),
            _k("<alt-shift-down>", "select_block_down",
                "Extend column selection down", SEL),
```

插在 shift+方向键四条（:70-73）之后，帮助面板按块分组。

## 五、新增测试

### tests/test_action_table.py（沿用文件内 registry/editor 夹具风格）

| 用例名 | 前置与操作 | 断言 |
|---|---|---|
| `test_select_block_down_begins_at_cursor_and_extends` | 3 行 buffer，光标 (0,1)；执行 `select_block_down` 两次 | `buffer.block_region() == (0, 1, 1, 1)`；第二次后仍为块扩展（anchor 未重置） |
| `test_select_block_right_then_up_normalizes_region` | 光标 (2,2)；right、up | `block_region() == (1, 2, 2, 3)` |
| `test_plain_select_down_after_block_clears_block_flag` | 建块后执行既有 `select_down` | `buffer.has_block_selection() is False`（charwise 接管，plan-a 卫生） |
| `test_copy_action_yanks_block_text` | 块 (0,1,1,3) 于 `"abcd\nefgh"`；执行 `copy` | `buffer.register == "bc\nfg"`；`register_block is True`；系统剪贴板 mock（沿用文件内 clipboard 替身方式）收到同值 |
| `test_cut_action_deletes_block_and_copies` | 同上执行 `cut` | lines == `["ad", "eh"]`；register 同上；单步 undo 可恢复 |
| `test_paste_action_replaces_block_selection_per_row` | 块 (0,1,1,3)；clipboard 替身返回 `"X\nYY"`；执行 `paste` | lines == `["aXd", "eYYh"]` |
| `test_paste_action_block_falls_back_to_register` | 块选 + clipboard 替身返回 `None`、`register="Z\nW"` | lines == `["aZd", "eWh"]` |

反向：无块选时 copy/cut/paste 走原路径（既有用例即回归，无需重复）。

### tests/test_vsc_keymap.py

| 用例名 | 断言 |
|---|---|
| `test_vsc_binds_alt_shift_arrows_to_block_select_actions` | `VscKeymap().lookup("\x1b[1;4A").action == "select_block_up"`（及 B/C/D → down/right/left） |
| `test_vsc_ctrl_v_still_binds_paste` | `lookup("\x16").action == "paste"`（防 plan-c 串扰的回归钉） |
| `test_vsc_esc_clears_block_flag` | 构造块选后 `handle_key(ctx, "\x1b")` → `buffer.block is False` |

## 六、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_action_table.py tests/test_vsc_keymap.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/actions.py yate/keymaps/vsc.py tests/test_action_table.py tests/test_vsc_keymap.py
```

通过判定：退出码 0；`test_action_table.py`/`test_vsc_keymap.py` 零回归；
R5/R7 架构守卫（actions 表只在 app 装载）不受影响（本计划不新增 import
editor 的位置，`actions.py` 已有）。

## 七、风险与回滚

- 风险：`copy` 动作手工置 `register_block = True` 与 plan-a 的 buffer 内部
  置位点并存——两处写同一语义，测试钉住；`select_block_*` 在只读 buffer 上
  仅移动光标（不触发 `_ensure_writable`），与现有 select 行为一致。
- 回滚：独立 commit（`feat(actions): column selection actions and block-aware clipboard`），
  单提交 revert；vsc 绑定与动作同文件回滚，无跨计划牵连。
