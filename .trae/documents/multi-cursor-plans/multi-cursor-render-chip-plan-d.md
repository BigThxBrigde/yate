# multi-cursor plan-d：多点渲染与 V-COLUMN chip（L2 + editor.py）

> wave-2。依赖：plan-a（`extra_cursors` 模型）。与 plan-b/plan-c 无文件
> 交集。输入：总纲 §四.7（状态栏）、§一.5（渲染目标）。

## 一、输入

- `yate/editor_view/editor.py`：`render_line`（:337-448，cursor 画法
  :378-384 与 :552-554）、`_row_style_ranges`（:508-557）、
  `_cursor_anchor`（:151-158）、`reveal_cursor`（:285-310）。
- `yate/editor_view/statusbar.py`：`mode_chip`（:32-52）、
  `refresh_status`（:89-157，:99 调用点）。
- `yate/editor.py`：`mode_label`（:785-791，冒烟脚本断言面）。
- 主题色：`t.mode_visual_bg`（V-COLUMN 沿用，总纲 §四.7）。

## 二、独占文件清单

只改以下文件，不要动其它任何文件：

| 文件 | 改动 |
|---|---|
| `yate/editor_view/editor.py` | `render_line` 逐附加点画光标 |
| `yate/editor_view/statusbar.py` | `mode_chip` 签名 + V-COLUMN 分支 |
| `yate/editor.py` | `mode_label` 传 buf |
| `tests/test_app_render.py` | 多点渲染快照用例 |
| `tests/test_mode_chip.py` | 新文件：mode_chip 单测 |

## 三、具体修改

### 3.1 editor_view/editor.py — 多点光标渲染

`render_line` 中 cursor 绘制有两处：

1. **行尾块光标补位**（:383-384）：

   ```python
   if y == cursor_row and cursor_col == len(line):
       cells.append(" ")  # block cursor at end of line
   ```

   多点时同样需要：任一附加点落在 `(y, len(line))` 也补一格。
   实现为对每点判断（追加在原判断后，不合并条件以保持可读）：

   ```python
   for point in buf.extra_cursors:
       if point[0] == y and point[1] == len(line):
           cells.append(" ")
           break
   ```

   注意在 `n_cells = len(cells)`（:386）**之前**（补位格计入 styles）。

2. **`_row_style_ranges` 光标 range**（:552-554）：主光标 range 之后为
   每个落在本行的附加点追加 S_CURSOR range：

   ```python
   for point in buf.extra_cursors:
       if point[0] == row:
           cell = theme.char_to_cell(line, point[1], tw)
           ranges.append((cell, cell + 1, S_CURSOR))
   ```

   - S_CURSOR=4 是最高 overlay 优先级，`render_line` 的
     `if sid > styles[c]`（:393-395）天然处理与 selection/match 重叠。
   - 附加点画在**本 pane 显示的文档**上：`buf = self.buffer`（:349），
     非活动 pane 显示同一文档时同样画（点集合是文档状态，总纲 §四.4）。
     `_cursor_anchor` 的 inactive-pane ViewState 路径**不含**附加点
     渲染差异——附加点直接读 `buf.extra_cursors`，与活动/非活动无关。
   - `reveal_cursor`（:285-310）**不改**：滚动跟随主光标（VS Code 同
     语义：跟随 primary）。
   - 宽字符：`char_to_cell` 与主光标同一条路径，无需特判。

### 3.2 statusbar.py — mode_chip 签名与 V-COLUMN

`mode_chip`（:32-52）签名扩为 `mode_chip(prompt, keymaps, buf: TextBuffer)`
（import `TextBuffer` 已在模块可用：`from yate.editor_core import Document`
的包根 re-export 允许；按 §三.5 叶包 re-export 例外直接
`from yate.editor_core.buffer import TextBuffer`）。分支顺序：

```python
def mode_chip(prompt: PromptBar, keymaps: KeymapSet, buf: TextBuffer) -> tuple[str, str]:
    t = theme.active()
    if prompt.active_mode:
        ...  # 原样
    if buf.has_extra_cursors():
        return "V-COLUMN", t.mode_visual_bg
    if keymaps.name == "vim":
        ...  # 原样
    return "VSC", t.mode_normal_bg
```

- V-COLUMN 在 prompt 之后、vim 映射之前：多光标激活时无论
  NORMAL/INSERT、无论键位都显示 `V-COLUMN`（总纲 §一.4）。
- docstring 补一句多光标优先级说明。

`StatusBar.refresh_status`（:99）：

```python
mode, chip_bg = mode_chip(self.prompt, self.keymaps, buf)
```

（`buf = doc.buffer`，:93 已有局部变量。）

### 3.3 editor.py — mode_label（:785-791）

```python
return mode_chip(self.prompt_bar, self.keymaps, self.session.buffer)
```

`Editor.mode_label` 的返回形状（tuple[str, str]）不变，冒烟脚本
（`tools/smoke_test/scenarios/view.py`、`vim_advanced.py`）零改动；
`label_restored == "VSC"` 类既有断言在无附加点时不受影响。

## 四、测试用例

### tests/test_mode_chip.py（新文件，纯函数单测，无 App）

fixture：`PromptBar` 构造（沿用 `statusbar.py` 依赖；prompt 未激活时
`active_mode` 为 None 的最小构造——参照 `tests/test_app_render.py` 或
现有 prompt 测试的构造方式）、`KeymapSet({"vsc": VscKeymap(), "vim": VimKeymap()}, name)`、
`TextBuffer("ab\ncd")`。

| 用例名 | arrange | act | assert |
|---|---|---|---|
| `test_mode_chip_multi_cursor_shows_v_column_in_vim_normal` | vim keymap、NORMAL、`add_cursor_at((0,1))` | `mode_chip(prompt, keymaps, buf)` | `("V-COLUMN", t.mode_visual_bg)`（色值断言用 `theme.active().mode_visual_bg` 变量，不硬编码 hex） |
| `test_mode_chip_multi_cursor_shows_v_column_in_insert` | vim INSERT（`vim.mode = VimMode.INSERT`）+ 附加点 | 同上 | 仍 `("V-COLUMN", ...)`（INSERT 不遮蔽多光标 chip） |
| `test_mode_chip_multi_cursor_shows_v_column_in_vsc` | vsc keymap + 附加点 | 同上 | `("V-COLUMN", ...)`（vsc 兜底 "VSC" 被覆盖） |
| `test_mode_chip_no_extra_cursors_keeps_vim_mapping` | vim NORMAL 无附加点 | 同上 | `("NORMAL", t.mode_normal_bg)` |
| `test_mode_chip_no_extra_cursors_vsc_fallback` | vsc 无附加点 | 同上 | `("VSC", t.mode_normal_bg)` |
| `test_mode_chip_prompt_active_beats_multi_cursor` | prompt `active_mode="command"` + 附加点 | 同上 | `("COMMAND", t.mode_command_bg)`（prompt 优先级最高，钉住分支顺序） |

### tests/test_app_render.py（渲染快照/strip 用例）

沿用文件内既有 render 断言方式（`render_line` → Strip / Segment 或
快照 SVG 管线，参照文件现状）。

| 用例名 | arrange | act | assert |
|---|---|---|---|
| `test_render_paints_cursor_block_on_each_extra_point_row` | app 内 buffer `"alpha beta\ngamma delta"`，`add_cursor_at((1, 5))` | 渲染 row 1 的 Strip | row 1 在 char_to_cell(line,5) 处出现 S_CURSOR 样式段（反向 bold），其余区段正常；row 0 主光标样式不变 |
| `test_render_extra_point_at_row_end_expands_cells` | 附加点 `(1, len(lines[1]))` | 渲染 row 1 | 行尾补一块光标格（cells 扩展生效），无越界/缺格 |
| `test_render_no_extra_points_matches_baseline` | 无附加点 | 渲染全屏 strip | 与改动前基线一致（既有快照用例回归——`tests/test_app_render.py` 既有 welcome/cache 断言全绿即钉） |

### 验证命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_mode_chip.py tests/test_app_render.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pyright yate/editor_view/ yate/editor.py tests/test_mode_chip.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 五、风险与回滚

| 风险 | 缓解 |
|---|---|
| 行尾补位格计入门控（`n_cells` 与 styles 长度）错位 | 补位在 `n_cells = len(cells)` 之前；快照用例覆盖行尾点 |
| 附加点与 selection/match 样式重叠 | S_CURSOR 优先级最高的既有取 max 机制（:393-395）；用例钉住 |
| `mode_chip` 签名变化的调用方遗漏 | 全仓仅 2 处（§3.2/§3.3），grep `mode_chip(` 复核为零遗漏；新单测文件直接锁行为 |
| 非 Windows 终端色值断言脆弱 | 色值经 `theme.active()` 变量断言，不硬编码 |
| 回滚 | 独立 commit `feat(editor-view): multi-cursor rendering and V-COLUMN chip`；`git revert` 净回 |

## 六、验收标准

1. §四 全部新用例通过；
2. `pytest tests/ -q` 全绿（含 `test_app_render.py` 既有 welcome 缓存、
   渲染基线回归）；
3. pyright `yate/editor_view/ yate/editor.py` 零诊断；
4. `tests/test_architecture.py` 28 passed（R3：editor_view 未新增向上
   import；R13：未直改 widget 样式着色——S_CURSOR 是既有 overlay id，
   非主题着色改动）。
