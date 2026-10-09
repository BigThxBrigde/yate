# vim-column-mode 子计划 c：vim 列模式（VISUAL_BLOCK）（wave-2）

> 输入：plan-a 的块 API（`begin_block_selection` / `block_region` / `yank_block`
> / `delete_block` / `insert_block`）。依赖：plan-a 已合入。

## 一、目标

1. `VimMode` 增加 `VISUAL_BLOCK`；Normal 模式 `Ctrl+V`（raw `\x16`）进入列模式；
2. 块模式下 motions（`_motion` select=True，经 `set_cursor` 保持块标志）扩展矩形；
3. `y` 块 yank、`d`/`x` 块删除（经 plan-a 的块 API，unnamed 写置
   `register_block`）；`v`/`V` 与其它 visual 形态互切；`esc`/`:`/`/`/`?` 退出；
4. `p`/`P` 无需改动：`TextBuffer.paste` 已按 `register_block` 分派块回贴（plan-a）。

## 二、非目标

- 块模式 `I`/`A`/`c`（多插入点，overview §二）；
- 虚列扩展（`j`/`k` 的列坐标按 `set_cursor` 夹取到行长，短行不保留虚拟列——
  与现有视觉行宽度语义一致，记为已知限制）。

## 三、独占文件清单

- `yate/keymaps/vim.py`
- `tests/test_vim_keymap.py`（追加用例）
- `.trae/rules/architecture-boundaries.md`（§三.7 豁免名单 vim.py 行数回填）

## 四、具体修改（yate/keymaps/vim.py）

### 1. `VimMode`（:43-49）

```python
    VISUAL_BLOCK = "visual_block"
```

### 2. 绑定表（:148-149 `v`/`V` 之后）

```python
            KeyBinding(parse_key("<ctrl-v>"), "visual block mode",
                "Blockwise visual mode (column selection)", EDT,
            ),
```

`parse_key("<ctrl-v>")` 产出 `\x16`（`yate/keymaps/base.py:130-139` C0 映射）；
两驱动路径均收敛到该 raw（overview §四）。vsc 的 `<ctrl-v>`→paste 在另一张
绑定表，互不影响。

### 3. `handle_key` 路由（:220）

```python
        if self.mode in (VimMode.VISUAL, VimMode.VISUAL_LINE, VimMode.VISUAL_BLOCK):
            return self._handle_visual(ctx, key)
```

### 4. `_handle_visual`（:291-394）

- 行首 `linewise` 改为双形态判定：

```python
        kind = self.mode  # VISUAL | VISUAL_LINE | VISUAL_BLOCK
        linewise = kind == VimMode.VISUAL_LINE
        blockwise = kind == VimMode.VISUAL_BLOCK
```

- `esc` 分支（:296-301）不变（`clear_selection` 已由 plan-a 清块标志）。
- `v` 分支（:317-324）：`VISUAL`→退出逻辑不变；非 VISUAL 一律切到 `VISUAL`
  并显式 `buf.block = False`（块角直接转 charwise 两端，vim 同款行为）。
- `V` 分支（:325-328）：切 `VISUAL_LINE` 前显式 `buf.block = False`，再走
  `_fix_linewise`（块角转整行，行为可接受；vim 同样把块转成行选）。
- 新增 `Ctrl+V`（`\x16`）分支（放在 `v` 分支之后）：

```python
        if key == "\x16":
            if blockwise:
                buf.clear_selection()
                self.mode = VimMode.NORMAL
                self.pending_register = None  # same cleanup as the ESC branch
            else:
                self.mode = VimMode.VISUAL_BLOCK
            return True
```

- `y`/`d`/`x` 分支（:329-354）：在 linewise 分支之前插块分支：

```python
            if blockwise:
                if key == "y":
                    text = buf.yank_block(named=reg)
                    assert text is not None  # a live block selection is guaranteed
                    self._mirror(text, reg)
                    sel = buf.block_region()
                    assert sel is not None
                    buf.clear_selection()
                    buf.cursor = (sel[0], sel[1])
                    ui.message("yanked block")
                else:
                    self._store_deleted(buf, buf.delete_block(named=reg), reg)
                    # delete_block already recorded register_block for the
                    # unnamed register; keep the clipboard mirror alive
                    ui.message("deleted block")
                self.mode = VimMode.NORMAL
                return True
```

  注意：`_store_deleted` 会用 `buf.register = text` 覆盖 unnamed 寄存器但不碰
  `register_block`——plan-a 的 `delete_block(named=None)` 已在覆盖前置
  `register_block = True`，且写入同一文本，语义一致（此处加一行注释钉住该
  契约）。named 寄存器路径下 `register_block` 不置位（`p` 走 charwise）——
  与 vim "named register 不记类型" 的简化一致，登记为已知限制。

- `_SHIFT_KEYS` 分支（:370-381）不动：`indent_selection`/`outdent_selection`
  按 `selected_rows()` 取 r1..r2 整行位移，块模式下即"矩形覆盖行整体缩进"，
  与 vim 的块 `>` 行为等价。
- motions 段（:382-394）：`_motion(..., select=True)` 经 `set_cursor` 保持
  block 标志（plan-a §四.2），`_fix_linewise` 仅 linewise 时调用——保持原
  `if self.mode == VimMode.VISUAL_LINE` 判定。

### 5. Normal 模式入口（:595-606 `v`/`V` 之后）

```python
        if key == "\x16":
            self.mode = VimMode.VISUAL_BLOCK
            buf.anchor = buf.cursor
            ui.message("-- VISUAL BLOCK --")
            return True
```

位置约束：必须在 `_extension_binding`（:633）之前、`_PREFIX_KEYS`/operator
判定（:481-494）之后——`\x16` 不是 motion/prefix/operator，天然不冲突；
:636-640 的未识别键吞噬不会到达（先命中本分支）。

### 6. `drop_visual`（:396-404）

```python
        if self.mode in (VimMode.VISUAL, VimMode.VISUAL_LINE, VimMode.VISUAL_BLOCK):
            self.mode = VimMode.NORMAL
```

（鼠标点击退出列模式；anchor 由调用方随后的 `set_cursor` 清除，含块标志——
plan-a 卫生。）

### 7. `_handle_insert`（:283-287）不动

插入模式下 `\x16` 不可打印、走末行吞键返回——与现状一致（vim 的字面插入
`Ctrl+V` 非目标）。

## 五、新增测试（tests/test_vim_keymap.py 追加，沿用 `_setup`/`_press` 风格；
`Ctrl+V` 的 raw 为 `"\x16"`）

| 用例名 | 前置与操作 | 断言 |
|---|---|---|
| `test_ctrl_v_enters_visual_block_mode` | `_setup("abc")`；`_press("\x16")` | `keymap.mode is VimMode.VISUAL_BLOCK`；`editor.messages[-1] == "-- VISUAL BLOCK --"`；`buffer.anchor == (0,0)` |
| `test_ctrl_v_in_block_mode_exits_and_clears` | `\x16`、`\x16` | mode 回 `NORMAL`；`buffer.has_selection() is False`；`buffer.block is False` |
| `test_block_motions_extend_rectangle` | `"abcd\nefgh\nijkl"`；`\x16`、`l`、`j` | `buffer.block_region() == (0, 0, 1, 1)`；mode 仍 VISUAL_BLOCK |
| `test_block_yank_copies_rectangle_and_lands_at_corner` | `\x16`、`l`、`j`、`y` | `buffer.register == "ab\nef"`；`buffer.register_block is True`；cursor == (0,0)；mode NORMAL |
| `test_block_delete_removes_rectangle_one_undo` | 同上但 `d` | lines == `["cd\n"…]`——精确为 `["cd", "gh", "ijkl"]`；`undo()` 后恢复三行原值 |
| `test_block_delete_feeds_block_paste` | `\x16`、`j`、`d`、`j`（下移）、`p` | 被删矩形在光标列按块回贴；`buffer.lines` 与删除前只差插入位置 |
| `test_v_from_block_mode_converts_to_charwise` | `"abcd"`；`\x16`、`j`、`v` | mode `VISUAL`；`buffer.block is False`；anchor 保持 |
| `test_V_from_block_mode_converts_to_linewise` | 同上用 `V` | mode `VISUAL_LINE`；`buffer.anchor == (0, 0)`、cursor 在行尾（`_fix_linewise` 生效） |
| `test_escape_leaves_block_mode` | `\x16`、`j`、`esc` | mode NORMAL；无选区；无残留块标志 |
| `test_prompt_keys_leave_block_mode` | `\x16` 后 `:`/`/`/`?` 三例 | mode NORMAL + 对应 prompt 打开（与既有 `test_escape_and_prompts_leave_visual_mode` 同构） |
| `test_drop_visual_from_block_returns_to_normal` | `\x16` 后 `keymap.drop_visual()` | mode NORMAL |
| `test_block_shift_indents_covered_rows` | `"ab\ncd"`；`\x16`、`j`、`>` | 两行各缩进一个单位；mode 保持 VISUAL_BLOCK（选择保留可再次 `>`） |
| `test_ctrl_v_unbound_under_vsc_keymap` | vsc 键位 `lookup("\x16")` | `binding.action == "paste"`（vsc 语义不变，防串扰回归；断言放本文件需构造 VscKeymap，亦可放 `tests/test_vsc_keymap.py`——按归属放那边，此处不重复） |

## 六、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_vim_keymap.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/keymaps/vim.py tests/test_vim_keymap.py
```

通过判定：退出码 0；`test_vim_keymap.py` 既有用例（visual/visual-line/registe
系列）零回归。

## 七、文档同步

- `.trae/rules/architecture-boundaries.md` §三.7 豁免名单 `keymaps/vim.py`
  行数按守卫口径实测回填。

## 八、风险与回滚

- 风险：`_handle_visual` 从布尔 `linewise` 改为三态 kind——逐分支核对既有
  用例（y/d/x linewise 路径、`v`/`V` 互切、prompt 退出）保证零回归（验收命令
  覆盖）；`_store_deleted` 与 `delete_block` 的寄存器契约靠注释钉住。
- 回滚：独立 commit（`feat(keymaps): vim visual block mode via ctrl+v`），
  单提交 revert；statusbar 的 `VISUAL_BLOCK` 映射在 plan-g 合入前回退默认
  `NORMAL` chip（overview §五表注），revert 本提交无残留引用。
