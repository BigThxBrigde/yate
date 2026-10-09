# vim-column-mode 子计划 e：EditorView 块选渲染（wave-2）

> 输入：plan-a 的块查询 API（`has_block_selection` / `block_region`）。依赖：
> plan-a 已合入。

## 一、目标

`yate/editor_view/editor.py` 的选区高亮支持矩形：块选存在时逐行画
`[c1, min(c2, len(line)))` 的 `S_SELECTION` 覆盖，且抑制同帧的 charwise 高亮
（两者共享 anchor/cursor，不抑制会叠画错形）。

## 二、非目标

- 非活动窗格的块选渲染：`ViewState`（`yate/session.py:237-243`）只有
  cursor/anchor 两字段，V1 不扩字段——非活动窗格按 charwise 归一化渲染，
  代码注释显式登记该限制（overview §七）；
- 块光标形状（cursor 仍按现规则画单格反色）。

## 三、独占文件清单

- `yate/editor_view/editor.py`
- `tests/test_app_render.py`（追加用例）

## 四、具体修改（yate/editor_view/editor.py）

### 1. 新增私有助手（`_selection`（:160-166）之后）

```python
    def _block_region(self) -> tuple[int, int, int, int] | None:
        """Block bounds for the active view's live buffer, ``None`` otherwise.

        Inactive panes render a block selection as the normalized charwise
        span: ``ViewState`` carries no block flag (V1 limitation, see the
        pane-state model in :mod:`yate.session`).
        """
        if self.is_active_view and self.buffer.has_block_selection():
            return self.buffer.block_region()
        return None
```

### 2. `_row_style_ranges`（:508-557）选区段改造

现 :522-538 的 charwise 段改为：

```python
        region = self._block_region()
        sel = None if region is not None else self._selection(cursor, anchor)
        if sel is not None:
            ...  # 原 charwise 分支体不变
        if region is not None:
            r1, c1, r2, c2 = region
            if r1 <= row <= r2:
                line_len = len(line)
                start = theme.char_to_cell(line, min(c1, line_len), tw)
                end = theme.char_to_cell(line, min(c2, line_len), tw)
                if end > start:
                    ranges.append((start, end, S_SELECTION))
```

要点：
- 抑制逻辑用"块存在则跳过 charwise"，不是叠加；
- 列夹取在 char 域做（`min` 到行长），再经 `char_to_cell` 转 cell 域，与
  既有 tab/宽字符几何处理同源；
- 搜索高亮（:542-550）与光标（:552-554）段不动——块选与搜索高亮叠加时按
  既有 `sid` 大者优先规则合成（`render_line` :392-395）。

### 3. docstring 更新

`_row_style_ranges` docstring（:508-516）补一句块选语义（散文式，符合
`python-coding-style.md` §2.3）。

## 五、新增测试（tests/test_app_render.py 追加；沿用该文件既有
app-pilot/渲染夹具风格，构造块选直接写 buffer 的 anchor/cursor/block）

| 用例名 | 前置与操作 | 断言 |
|---|---|---|
| `test_block_selection_paints_only_rectangle_cells` | 2 行 `"abcd\nefgh"`，块 (0,1,1,3)；渲染 row0/row1/row2 | row0 与 row1 的 cell 1..2 为 `S_SELECTION`（经 `_row_style_ranges` 返回值断言，不逐段解析 Strip）；row2 无选区 range |
| `test_block_selection_clamps_short_rows_to_line_length` | 行 `"ef"` 落在块 (0,1,1,4) 内 | 该行 range 为 cell 1..2（`char_to_cell("ef", 2)`），不越界到 cell 4 |
| `test_charwise_highlight_suppressed_while_block_active` | 块 (0,0,1,1)（anchor=(0,0), cursor=(1,1), block=True） | `_row_style_ranges` 中无 charwise 斜跨 range：row0 恰为 cell 0..1、row1 恰为 cell 0..1（若未抑制，row1 会被 charwise 画成 0..len(line)） |
| `test_block_selection_zero_width_paints_nothing` | anchor==cursor 列相同跨行（block=True, region c1==c2） | 无选区 range（`end > start` 守卫） |
| `test_inactive_pane_block_selection_renders_charwise` | 双窗格，活动窗格持块选；对非活动 view 调 `_block_region()` | 返回 `None`（charwise 回退，V1 限制钉住） |

反向：无块选时 `_block_region() is None`、charwise 渲染与改前逐字节一致
（既有 `test_app_render.py` 用例即回归）。

## 六、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_app_render.py -q
.venv\Scripts\python.exe -m pytest tests/test_highlight.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/editor_view/editor.py tests/test_app_render.py
```

通过判定：退出码 0；渲染/高亮既有用例零回归；R3 守卫（editor_view 不向上
import）持续成立。

## 七、风险与回滚

- 风险：`_row_style_ranges` 是每帧每行热路径——块分支只加一次
  `has_block_selection()`（O(1) 标志读）与常数夹取，无回归性开销；
  与搜索高亮叠加的合成顺序由既有 `sid` 优先规则决定，不新增规则。
- 手工验证（随 wave-3 总门禁）：块选跨越 tab 行时高亮 cell 对齐无错位
  （`char_to_cell` 同源转换，预期无问题）。
- 回滚：独立 commit（`feat(editor-view): block selection rendering`），单提交
  revert。
