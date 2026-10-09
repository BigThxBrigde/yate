# vim-column-mode 子计划 f：鼠标 Alt+拖拽列选择（wave-2）

> 输入：plan-a 的块 API。依赖：plan-a 已合入。

## 一、目标

`yate/flows/mouse_flows.py` 支持 `Alt` + 左键按下/拖拽产生列选择：
`MouseDown(alt)` 在点击处起块锚，`MouseMove` 扩展矩形，`MouseUp` 保留块选
（VS Code 行为）；普通拖拽（无 Alt）路径逐字节不变。

## 二、非目标

- 不新增鼠标派发点（R10/support_mouse 闸门复用现状，见 overview §六）；
- Alt+click 无拖拽（MouseDown 与 MouseUp 同点）：保留零宽度块锚，与 VS Code
  一致（后续 Alt+Shift+方向键可从该锚扩展）。

## 三、独占文件清单

- `yate/flows/mouse_flows.py`
- `tests/test_app_mouse.py`（追加用例）

## 四、具体修改（yate/flows/mouse_flows.py）

### 1. `_on_down`（:65-78）

vim visual 退出与光标定位保持，选区分支按 `event.alt` 分叉：

```python
    def _on_down(self, view: EditorView, event: MouseDown) -> bool:
        if event.button != LEFT_BUTTON:
            return False
        keymap = self.keymaps.active
        if isinstance(keymap, VimKeymap):
            keymap.drop_visual()
        pos = view.buffer_pos_from_mouse(event)
        if pos is None:
            return False
        if event.alt:
            # Column selection: anchor at the press point; the block flag
            # survives the select=True extends below (TextBuffer.set_cursor
            # keeps it while an anchor exists).
            view.buffer.set_cursor(pos)
            view.buffer.begin_block_selection()
        else:
            view.buffer.set_cursor(pos, select=event.shift)
        view.content_changed()
        self._refresh()
        self._dragging = True
        return True
```

### 2. `_on_move`（:80-88）——无需修改

`set_cursor(pos, select=True)` 在 anchor 已存在时保持 `block` 标志
（plan-a §四.2），alt 拖拽自动扩展矩形；普通拖拽在 alt 松开后的 move 仍按
charwise 扩展（块标志在 `_on_down` 已按当次按下决定，拖拽中途切 Alt 不换轨——
与 VS Code 相同，注释说明）。

### 3. `_on_up`（:90-98）——无需修改

`_dragging` 收尾；块选保留（不 clear）。

### 4. docstring 补充

模块 docstring（:1-9）补一句 Alt+drag 列选择；`_on_down` 内注释如上。

## 五、新增测试（tests/test_app_mouse.py 追加；沿用该文件 `_mouse_app` /
pilot 鼠标合成风格）

| 用例名 | 前置与操作 | 断言 |
|---|---|---|
| `test_alt_drag_makes_block_selection` | vsc 键位 app；alt+MouseDown 于 (row0, col1)，alt+MouseMove 于 (row1, col3)，MouseUp | `buffer.has_block_selection() is True`；`block_region() == (0, 1, 1, 3)`；`_dragging` 收尾为 False |
| `test_plain_drag_makes_charwise_selection` | 无 alt 同路径 | `buffer.has_block_selection() is False`；charwise 选区存在（回归钉） |
| `test_alt_drag_under_vim_keymap_drops_visual_then_blocks` | vim 键位 app，先 `v` 进 VISUAL，再 alt+drag | `keymap.mode is VimMode.NORMAL`（drop_visual 生效）；块选成立 |
| `test_alt_click_without_drag_keeps_zero_width_anchor` | alt+MouseDown 后直接 MouseUp（同点） | anchor==cursor（零宽），`buffer.block is True`；后续 `select_block_down` 动作可从锚扩展（与 plan-d 动作协同） |
| `test_support_mouse_off_blocks_alt_drag` | `support_mouse=False` 配置下 alt+drag | 事件被 App 闸门丢弃（既有闸门测试同构），buffer 无选区变化 |

## 六、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_app_mouse.py tests/test_support_mouse.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/flows/mouse_flows.py tests/test_app_mouse.py
```

通过判定：退出码 0；既有鼠标/闸门用例零回归；
`test_support_mouse_gate_lives_in_app_on_event`（架构守卫 #26）持续通过——
本计划不改 `YateApp.on_event`，闸门文本断言不受影响。

## 七、风险与回滚

- 风险：Textual `MouseDown.alt` 属性可用性（Textual 8.2.8 `MouseEvent` 自带
  `ctrl/alt/shift`，`on_mouse_down` 已用 `event.shift` 同源，风险低）——
  若属性缺失由 pyright 在验收时暴露；
  并发 Textual pilot timing 偶发（`subagent-workflow.md` §三.3）：失败先重跑确认。
- 回滚：独立 commit（`feat(flows): alt+drag column selection`），单提交 revert；
  与 plan-d/e 无文件交集。
- **偏离记录（2026-10-10）**：Textual 8.2.8 `MouseEvent` 无 `alt` 属性
  （pyright 实测暴露），§四.1 的 `if event.alt:` 改为 `if event.meta:`；
  依据：Textual 的 SGR 鼠标解码把 modifier 位 8（Alt）映射为 `meta`
  （`textual/_xterm_parser.py:129-141` 实测）——真实终端里 Alt+拖拽到达
  yate 时即 `meta=True`，终端语义等价，非语义变更。§四.3 测试用例改用
  pilot/合成路径的 `meta=True` 构造（pilot `_get_mouse_message_arguments`
  支持 `meta` 参数，实测确认）。主代理裁决采纳。
