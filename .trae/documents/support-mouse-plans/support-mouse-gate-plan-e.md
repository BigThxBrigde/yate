# support-mouse plan-e：`support_mouse` 全局闸门 + 架构守卫 + 收尾（wave-3）

输入：overview.md §三 禁用语义定案；plan-a 的 `config.support_mouse`；
plan-b/c/d 的全部鼠标行为。issue IKJRFK 需求 2 的禁用侧语义 +
全量收尾门禁。

## 一、闸门选型（定案）

**单一入口：`YateApp.on_event` 在 Textual 转发前丢弃一切 MouseEvent。**
实证依据（overview §Textual 运行时事实）：Textual 8.2.8 中未转发的鼠标
事件只在 `App.on_event` 一处转发给 screen（`textual/app.py:4060-4082`
`self.screen._forward_event(event)`），Click 的 chain 合成同样发生在其中
（4086-4117）——在这里拦截 = 内建 widget（ScrollBar/Tree/Input）、
屏幕（屏保）、Textual 合成 Click 全部失效，语义"完全不响应任何鼠标
交互"一步达成。逐组件闸门被否决（盖不住内建 widget；理由详见
overview §三）。

`YateApp.on_event`（`yate/app.py:223-235`）已覆写该钩子并在
`super().on_event` 前做 idle 探测——闸门插在同一位置，空闲探测保持
（鼠标移动仍计作用户活动，与"不响应交互"不冲突：交互=改变编辑器状态）。

## 二、独占文件清单

| 文件 | 操作 |
|---|---|
| `yate/app.py` | 修改（on_event 一处） |
| `tests/test_architecture.py` | 新增守卫用例 |
| `tests/test_support_mouse.py` | 新文件 |

## 三、具体修改

### 1. `yate/app.py`：`on_event`（223-235 行）

```python
@override
async def on_event(self, event: events.Event) -> None:
    """Poke the idle tracker on every input event, then dispatch normally.

    ``App.on_event`` sees every Key / Mouse record before the focused
    widget does -- including records a widget then consumes -- which
    makes it the only reliable "user is active" probe.  Only
    ``InputEvent`` subclasses count as activity; every event continues
    through the normal dispatch either way.

    ``support_mouse = False`` drops every mouse record right here,
    before Textual forwards it to the screen: this is the single gate
    for the whole app (built-in widgets included), and it also
    suppresses Textual's Click synthesis, which runs inside
    ``App.on_event`` (issue IKJRFK).
    """
    if self._idle is not None and isinstance(event, events.InputEvent):
        self._idle.poke()
    if not self.config.support_mouse and isinstance(event, events.MouseEvent):
        event.stop()
        event.prevent_default()
        return
    await super().on_event(event)
```

不需要 `is_forwarded` 附加条件：被丢弃的事件永远不会被转发，也就没有
bubbled 重入；即便重入也被同一条件再次丢弃。

### 2. `tests/test_architecture.py`：闸门守卫（文本断言，风格同 T2
`test_editor_does_not_paint_widget_styles`）

```python
def test_support_mouse_gate_lives_in_app_on_event() -> None:
    """``support_mouse = false`` drops mouse events in ``YateApp.on_event``
    before ``super().on_event`` forwards them (issue IKJRFK): the gate
    must appear before the forward call in the source."""
    source = (YATE / "app.py").read_text(encoding="utf-8")
    assert "support_mouse" in source
    gate = source.index("support_mouse")
    forward = source.index("await super().on_event(event)")
    assert gate < forward
```

（`YATE` 常量为该测试文件既有的仓库根句柄；执行时若文件内常量名不同，
随本文件现状适配。）

### 3. `tests/test_support_mouse.py`（新文件；harness 参照
`tests/test_app_textual.py` 的 run_test 模式；`YateApp(config=YateConfig(
support_mouse=False))` 构造禁用态 App，config 形参见
`yate/app.py:85-100`）

用例 1 `test_support_mouse_disabled_click_does_not_move_cursor`
- 前置：禁用态 App，tmp 目标文件含已知文本；`pilot.pause()`。
- 操作：`pilot.click(EditorView, offset=(8, 0))`。
- 断言：`buf.cursor == (0, 0)`（点击前后的值不变）。

用例 2 `test_support_mouse_disabled_click_does_not_switch_tab`
- 前置：禁用态 App 打开两个文档（session.index == 0）。
- 操作：按 TabBar 布局点击第二个 tab 的单元区
  （`app.editor.tabbar` region 内 offset，执行时以 `build` 的
  regions 口径计算，chrome.py:52-87）。
- 断言：`app.editor.session.index == 0` 不变。

用例 3 `test_support_mouse_disabled_click_does_not_open_explorer_file`
- 前置：禁用态 App 以目录为目标（含 `a.txt`）。
- 操作：对 explorer 文件行 `pilot.click(...)`。
- 断言：`len(session.docs)` 不变、`session.doc.path` 不变。

用例 4 `test_support_mouse_enabled_click_moves_cursor`（正向对照）
- 前置：默认配置 App（`support_mouse=True`），同一 tmp 文本。
- 操作：同用例 1 的点击。
- 断言：`buf.cursor == (0, 5)`（与 plan-c 用例 8 同口径，此处验证
  默认闸门放行）。

用例 5 `test_support_mouse_disabled_wheel_does_not_scroll_terminal`
- 前置：禁用态 App，打开终端并产生若干仿真输出（参照
  `tests/test_app_terminal.py` 的就绪/注水手段）。
- 操作：`pilot.hover`+滚轮——以 `pilot._post_mouse_events(
  [MouseScrollUp], widget=TerminalView)` 注入。
- 断言：terminal view 的 `_scroll` 保持 0。

## 四、验证方案（收尾门禁 = 全量）

| 项 | 命令 | 通过判定 |
|---|---|---|
| 闸门用例 | `.venv\Scripts\python.exe -m pytest tests/test_support_mouse.py -q` | 退出码 0，5 用例全绿 |
| 架构 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 全绿（26 用例 = 25 既有 + 本计划守卫） |
| 全量回归 | `.venv\Scripts\python.exe -m pytest tests/ -q` | 退出码 0 |
| 类型 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | 零诊断 |
| 手工 | rc 写 `support_mouse = False` 启动：点击/拖拽/滚轮/双击全部无反应，键盘编辑不受影响；删掉该行重启恢复 | 现象符合 §一语义定案 |

## 五、风险与回滚

- 风险：闸门把 idle 探测一起拦掉 → 已规避（poke 在闸门前，顺序固定）。
- 风险：屏保 MouseMove 在禁用态失效 → 语义定案内含（overview §三），
  `tests/test_screensaver.py` 全量回归确认非禁用态无回归。
- 风险：文本守卫 `gate < forward` 在未来 on_event 重构时脆弱 → 与 T2
  同风格的既有实践，失败即提示人工复核，可接受。
- 回滚：还原 `yate/app.py` 的 on_event 与两个测试文件；config 字段
  留存无害（plan-a 回滚口径）。

## 六、收尾回填（对 overview 与本文）

1. 本文"验证方案"表逐项回填真实结果（退出码、用例数）。
2. 若执行中出现设计偏离（如 `_on_move` 降级备选被采用、
   `MouseFlows` 签名收缩），在对应子计划文档"风险与回滚"小节后追加
   "偏离记录"小节：偏离点 + 实测依据，并同步 overview §四 波次表备注。
3. 提交拆分建议：每波次一组 commit（`feat(config): add support_mouse
   option` / `feat(panes): drag-resize via separator borders` /
   `feat(editor): mouse cursor & selection in the text area` /
   `feat(terminal): click to focus` / `feat(app): support_mouse gate`），
   遵循 `git-commit-message.md`（英文、`type(scope): subject`）与
   `misc-rules.md` §一（PowerShell here-string 多行提交体）。
