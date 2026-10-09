# multi-cursor plan-c：多点 actions 与鼠标 ALT+点击加光标（L3）

> wave-2。依赖：plan-a。与 plan-b 无文件交集（plan-b 提供 vsc 的
> `<alt-c>` 绑定，指向本计划注册的 `add_cursor_below` action）。
> 输入：总纲 §四.3（鼠标链路）、§四.6（vsc 键位接入点）。

## 一、输入

- `yate/actions.py`：editing 段（:36-57）、navigation/selection 段
  （:59-99，含 `clear_selection` :99）、cut/copy/paste（:106-160）。
- `yate/flows/mouse_flows.py`：`handle_view_mouse`（:39-54）、
  `_on_down`（:65-78，vim 模式先 `drop_visual()` :69-70）、
  `_on_move`（:80-88）、`_on_up`（:90-98）。
- plan-a 的 buffer API；`VimKeymap` 判型（`mouse_flows.py:21` 已 import）。

## 二、独占文件清单

只改以下文件，不要动其它任何文件：

| 文件 | 改动 |
|---|---|
| `yate/actions.py` | `add_cursor_below` action；`newline`/`delete_backward`/`delete_forward`/`clear_selection` 多点分支 |
| `yate/flows/mouse_flows.py` | `_on_down` meta 分支 + 普通点击清点 |
| `tests/test_action_table.py` | action 注册与多点分支用例 |
| `tests/test_app_mouse.py` | ALT+点击 / 普通点击清点用例 |

## 三、具体修改

### 3.1 actions.py

1. **新增 action**（selection 段，`clear_selection`（:99）之前）：

   ```python
   reg("add_cursor_below",
       lambda ctx: ctx.buffer.add_cursor_below(),
       "Add a cursor on the next row (multi-cursor)")
   ```

2. **`newline`（:36-40）多点分支**：

   ```python
   reg(
       "newline",
       lambda ctx: (
           ctx.buffer.insert_at_points("\n")
           if ctx.buffer.has_extra_cursors()
           else ctx.buffer.insert_newline(language=ctx.doc.filetype)
       ),
       "Insert newline (auto-indent)",
   )
   ```

   （多点换行无 auto-indent——总纲已知限制。）

3. **`delete_backward`（:42-43）多点分支**：同形，多点走
   `ctx.buffer.delete_at_points()`。
4. **`delete_forward`（:43）多点分支**：同形，多点走
   `ctx.buffer.delete_forward_at_points()`。
5. **`clear_selection`（:99）扩展**：

   ```python
   def _clear_selection(ctx: ActionContext) -> None:
       ctx.buffer.clear_extra_cursors()
       ctx.buffer.clear_selection()

   reg("clear_selection", _clear_selection, "Clear selection")
   ```

   （vsc `<esc>` 经此同时清点与选区；vim 的 ESC 走 plan-b 的 vim 分支，
   不经 action。）
6. **cut/copy/paste 不动**：多光标选区是非目标（总纲 §二），现有多点为
   裸光标无选区，`has_selection()` 为 False 走整行/粘贴原语义即可。

### 3.2 mouse_flows.py — `_on_down`（:65-78）

改为三分支（保持既有缩进/卫语句风格）：

```python
def _on_down(self, view: EditorView, event: MouseDown) -> bool:
    if event.button != LEFT_BUTTON:
        return False
    pos = view.buffer_pos_from_mouse(event)
    if pos is None:
        return False
    keymap = self.keymaps.active
    if isinstance(keymap, VimKeymap):
        keymap.drop_visual()  # 既有行为：vim 模式点击退出 visual
    if event.meta and not isinstance(keymap, VimKeymap):
        # ALT+click adds a multi-cursor point (vsc mode).  Textual maps
        # the SGR Alt bit (8) to ``meta``; MouseEvent has no ``alt``.
        # Click semantics: no drag starts, so the point survives MouseUp.
        view.buffer.clear_selection()
        view.buffer.add_cursor_at(pos)
    else:
        if not event.shift and not event.meta:
            view.buffer.clear_extra_cursors()  # a plain click collapses
        view.buffer.set_cursor(pos, select=event.shift)
    view.content_changed()
    self._refresh()
    self._dragging = not (event.meta and not isinstance(keymap, VimKeymap))
    return True
```

行为矩阵：

| 场景 | 行为 |
|---|---|
| vsc + meta（ALT）左键 | 加点（`add_cursor_at`），不启动拖拽，不清既有附加点 |
| vsc 普通左键（无修饰） | **清附加点** + 移动光标（VS Code 语义）+ 启动拖拽 |
| vsc shift+左键 | 保持选区扩展原语义 + 启动拖拽（不清点——shift 点击扩展选区与多光标并存无意义，但保留现状行为最小改动；若 shift 点击时有点集，`set_cursor(select=True)` 以既有 anchor 为锚，行为与现状一致） |
| vim 模式任意左键 | `drop_visual()` + 原单光标行为（普通点击同样清附加点——vim 模式的点集只能来自 ALT+C，点击视为"回到单光标"是预期） |

- `_on_move`/`_on_up` 不改：meta 点击未启动拖拽（`_dragging=False`），
  move/up 走既有卫语句自然忽略。
- **注意次序**：`drop_visual()` 保持在 meta 分支之前（vim 判型在先）；
  `buffer_pos_from_mouse` 判 `None` 提前返回（避免无 pos 时改状态）。

## 四、测试用例

### tests/test_action_table.py（新增用例组）

沿用文件内既有 registry/ctx fixture 风格。

| 用例名 | arrange | act | assert |
|---|---|---|---|
| `test_add_cursor_below_action_registers_and_adds_point` | registry + ctx（光标 (0,1)） | `execute("add_cursor_below")` | 返回 True；`buf.extra_cursors == [(1, 1)]` |
| `test_newline_action_multi_cursor_inserts_at_all_points` | 两附加点 | `execute("newline")` | 每点处换行（`line_count` 增加 2）；一次 undo 复原 |
| `test_delete_backward_action_multi_cursor_deletes_at_all_points` | 两附加点 (0,1)(1,1) | `execute("delete_backward")` | 两行各删前一字符；一次 undo 复原 |
| `test_clear_selection_action_drops_extra_cursors_too` | 两附加点 + anchor | `execute("clear_selection")` | `extra_cursors == []` 且 `anchor is None` |
| `test_single_cursor_actions_unchanged_when_no_extras` | 无附加点 | `execute("newline")` / `execute("delete_backward")` | 走原语义：newline 带 auto-indent（对 `"if x:"` 尾行插入缩进行）；与改动前断言一致（既有用例回归） |

### tests/test_app_mouse.py（新增用例组）

沿用文件内既有 pilot/mouse 事件合成方式（`MouseDown`/`MouseMove` 合成，
`meta=True` 通道——废弃分支 plan-f 的 pilot 合成先例：`MouseEvent` 无
`alt` 属性，meta 是 Alt 通道）。

| 用例名 | arrange | act | assert |
|---|---|---|---|
| `test_meta_mouse_down_adds_cursor_point_vsc` | vsc 键位、app 运行中 | 向编辑区发 `MouseDown(meta=True, button=1)` 于行内某 cell | `buf.extra_cursors` 含该点；`_dragging` 为 False（mouse_flows 实例）；`content_changed` 已刷（渲染刷新由 pilot.pause 后状态断言） |
| `test_meta_mouse_down_in_vim_mode_stays_single_cursor` | vim 键位 | 同上发 meta MouseDown | `buf.extra_cursors == []`；cursor 移到点击处（原行为） |
| `test_plain_mouse_down_clears_extra_cursors_vsc` | 先 ALT+click 建点 | 普通左键 MouseDown 另一位置 | `extra_cursors == []`；cursor 在新位置 |
| `test_shift_mouse_down_keeps_selection_semantics` | 无点集 | shift+MouseDown | `anchor`/`cursor` 成选区（原语义回归钉） |
| `test_meta_click_then_type_via_pilot_inserts_at_all_points` | vsc、ALT+click 两处 | `pilot.press("x")` | 两点同步插入（端到端：鼠标加点 → 键盘多点编辑贯通）；`undo` 一次复原 |

**验证命令**：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_action_table.py tests/test_app_mouse.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pyright yate/actions.py yate/flows/ tests/test_action_table.py tests/test_app_mouse.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 五、风险与回滚

| 风险 | 缓解 |
|---|---|
| meta 判型遗漏（vim 模式误加点） | `isinstance(keymap, VimKeymap)` 双重卫语句 + 专项用例；`mouse_flows.py:21` 已 import VimKeymap，无新依赖边 |
| 普通点击清点改变 vim ALT+C 后的鼠标交互预期 | 行为矩阵写入 `_on_down` docstring；用例钉住"vim 模式点击清点" |
| `_dragging` 语义变化引入拖拽回归 | meta 分支显式 `_dragging=False`；`tests/test_app_mouse.py` 既有拖拽用例回归 |
| `newline` 三元表达式可读性 | 若超 100 列或评审认为难读，落成模块级 `_newline(ctx)` 函数（与 `cut`/`copy` 同风格）；两形态均合规 |
| 回滚 | 独立 commit `feat(actions): multi-cursor actions and ALT+click cursor`；`git revert` 净回 |

## 六、验收标准

1. §四 全部新用例通过；两个测试文件 `-q` 退出码 0；
2. `pytest tests/ -q` 全绿；
3. pyright `yate/actions.py yate/flows/` 零诊断；
4. `tests/test_architecture.py` 28 passed（R11：mouse_flows 的
   editor_view 导入为存量冻结面，无新增；`test_flow_modules_hold_no_app_handle`
   不触碰——mouse_flows 不持有 App 句柄）。
