# support-mouse plan-d：其余组件鼠标补齐（wave-2）

输入：overview.md 调研结论 §现有鼠标面；issue IKJRFK 需求 3
（"所有界面元素必须有对应鼠标响应"）。
本计划补终端点击聚焦，并核验/钉死其余组件的鼠标现状。

## 一、组件面现状与处置定案

| 组件 | 现状（行号） | 处置 |
|---|---|---|
| TabBar | 点击切标签已有（`yate/editor_view/chrome.py:119-128`） | 不改；plan-e 闸门禁用态覆盖它 |
| explorer | Textual Tree 内建点击选中（`textual/widgets/_tree.py:1453`）→ `NodeSelected` → 打开文件（`yate/editor_view/explorer.py:290-302`） | 不改代码；新增验证用例钉住链路 |
| terminal | 仅滚轮（`yate/editor_view/terminal.py:268-276`），`TerminalView can_focus=True`（72-75 行）但点击不聚焦 | **新增点击聚焦**（本计划唯一代码改动） |
| 命令行（PromptBar/Input） | Textual Input 内建点击定位光标 | 不改；手工验证 |
| statusbar / breadcrumbs / sidebar-head | 纯展示（`yate/editor_view/statusbar.py:55`、chrome.py:131/235） | 定案无鼠标动作（见 §二） |
| 滚动条 | Textual 内建拖拽 + slim 渲染保留 meta（`yate/editor_view/scrollbars.py:60-74`） | 不改 |
| 屏保 | MouseMove 响应已有（`yate/editor_view/screensaver.py:323-335`） | 不改 |

**statusbar/breadcrumbs 无鼠标动作的理由**：二者是被动信息展示（模式芯片、
位置、路径面包屑），无任何可点语义；issue 的"对应鼠标响应"对展示性元素
的合理解释是"点击落空且不抢焦点"——现状即满足（Static 不消费鼠标，
事件冒泡无副作用）。为它们发明点击动作（如点 LSP 段开诊断浮层）属新
功能设计，超出本 issue 范围，列为 overview 非目标。

**终端模拟器无鼠标捕获冲突**：`yate/editor_term/` 不支持 DECSET
1000/1002/1006（overview 调研），终端内程序从不申请鼠标事件，yate 侧
点击聚焦/滚轮翻历史无竞争。若未来模拟器支持鼠标转发，需回头设计
聚焦 vs 转发的仲裁（此处留档）。

## 二、独占文件清单

| 文件 | 操作 |
|---|---|
| `yate/editor_view/terminal.py` | 修改 |
| `tests/test_app_terminal.py` | 新增用例 |
| `tests/test_app_explorer.py` | 新增用例 |

## 三、具体修改

### `yate/editor_view/terminal.py`：`TerminalView` 点击聚焦

imports（检查文件头部 `textual.events` 导入行，追加 `MouseDown`；现存
MouseScrollUp/MouseScrollDown 在 268-276 行使用）。在 `on_key`
（215 行）之前新增：

```python
def on_mouse_down(self, event: MouseDown) -> None:
    """Focus the terminal so typed keys reach the shell (click-to-focus).

    The panel accepts the click (R10 analogue: the event is stopped) but
    does not write to the shell -- a stray click must never send input.
    """
    if event.button == 1:
        self.focus()
        event.stop()
        event.prevent_default()
```

说明：`TerminalView` 已是键收点（on_key 215 行），聚焦后键盘通路即达；
滚轮 handler（268-276 行）自带 `event.stop()`，不受影响。

## 四、新增测试（详细用例）

### `tests/test_app_terminal.py`

1. `test_terminal_click_focuses_view`
   - 前置：`app.run_test()`；`pilot.press("ctrl+`")` 打开终端面板并等待
     shell 就绪（参照本文件既有用例的就绪等待模式）。
   - 操作：先把焦点放回编辑器（`pilot.press("ctrl+1")`），再
     `pilot.click(TerminalView, offset=(5, 0))`。
   - 断言：`app.focused` 是该 `TerminalView` 实例。
2. `test_terminal_click_does_not_write_shell`
   - 前置：同上。
   - 操作：点击后断言进程输入未变——以 `view.emulator` 行内容/进程
     写入口径断言（本文件已有仿真断言手段；最低限度：点击后
     `emulator.view_lines(0)` 与点击前逐行相等）。
   - 断言：输出无新行（点击不发输入）。

### `tests/test_app_explorer.py`

3. `test_explorer_click_opens_file`（验证内建链路，防上游行为漂移）
   - 前置：`app.run_test()` 以临时目录为目标（含 `a.txt`），explorer
     可见（目录目标启动即显示，参照本文件既有用例）。
   - 操作：由 `app.editor.explorer_tree` 定位 `a.txt` 节点的可见行
     （`ExplorerTree._line_of`，explorer.py:156-176），对该行执行
     `pilot.click(ExplorerTree, offset=(2, line))`。
   - 断言：`app.editor.session.doc.path is not None` 且名字为
     `a.txt`（`NodeSelected` → `open_path` 链路贯通）。

### 手工验证（Textual Input 内建，不自动化）

- 运行 yate，按 `:` 打开命令行，点击输入行内不同位置：光标（Input 光标）
  跟随点击；`esc` 后焦点回落。预期现象记录进执行回填。

## 五、验证方案

| 项 | 命令 | 通过判定 |
|---|---|---|
| 单测 | `.venv\Scripts\python.exe -m pytest tests/test_app_terminal.py tests/test_app_explorer.py -q` | 退出码 0，含上述 3 个新用例 |
| 回归 | `.venv\Scripts\python.exe -m pytest tests/test_terminal.py tests/test_terminal_emulator.py -q` | 退出码 0 |
| 类型 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | 零诊断 |
| 手工 | 命令行点击定位光标（步骤见上） | 现象符合预期 |

## 六、风险与回滚

- 风险：终端尚未就绪时点击（`started=False`）——`on_mouse_down` 仅聚焦
  不写进程，行为安全；死 shell 的复活语义归 `on_key`（241-245 行）不变。
- 风险：Tree 内建点击的节点命中依赖上游（Textual 版本锁定 `>=8.0`），
  用例 3 就是漂移哨兵；上游行为变化时该用例失败并提示改用显式
  `on_click` 适配（届时另立小改）。
- 回滚：单提交还原 `yate/editor_view/terminal.py`；explorer 用例可独立
  保留（纯验证）。
