# support-mouse plan-b：面板拖拽 resize（wave-1）

输入：overview.md 调研结论 §窗格模型与分隔条形态；issue IKJRFK 需求 3
（面板拖拽 resize）。
分隔条现状是子 widget 的 CSS 边框类（`pane-sep-h`/`pane-sep-v`，
`yate/resources/pane-host.tcss:15-20`），不是独立 widget。

## 一、形态选型（定案与否决理由）

**选定：PaneHost 容器层命中 + 拖拽（不新增 widget）**。MouseDown 落在
子 widget 的边框格上、未被消费时按 Textual 事件冒泡到 `PaneHost`
（`yate/editor_view/panes.py:422`，`PaneHost(Widget)` 是这些容器的父），
由它做命中测试并 `capture_mouse()` 接管后续 MouseMove。

否决的备选：

1. **独立 Separator widget 插入 splits**：`_build`/`_style_split`/
   `_apply_sizes`（panes.py:489-569）的 fraction 现在直接对齐
   `Split.children`；插入 1 格高的分隔 widget 会破坏
   "children 与 sizes 平行列表"的模型不变式（`yate/session.py:331` 的
   assert 即守卫此式），要么改 L1 模型要么在 UI 层做第二套 fraction 几何，
   两边都越界。否决。
2. **meta 命中（scrollbars 的 `meta={"@mouse.down": ...}` 路线）**：
   需要重写 EditorView/容器的 render_line 输出 meta——EditorView 的
   strip 不含边框格（边框是 Textual 框架画的），meta 挂不上。否决。
3. **每个 EditorView 自己识别"我是分隔子"处理拖拽**：分隔逻辑属于
   窗格树布局（PaneHost/PaneManager 职责），散进叶子组件会让 n 个
   叶子各持一份几何推断。否决。

对 plan-c 的契约：pane-sep 边框格上的按下必须**不被文本区消费**
（冒泡给 PaneHost）——该守卫落在 plan-c 的 `EditorView.on_mouse_down`
（见 plan-c §二.4），本计划在 wave-1 期间 EditorView 尚无鼠标
handler，冒泡天然成立，不阻塞。

## 二、独占文件清单

| 文件 | 操作 |
|---|---|
| `yate/editor_view/panes.py` | 修改 |
| `tests/test_panes.py` | 新增用例 |
| `tests/test_app_panes.py` | 新增用例 |

## 三、具体修改（定位到行号）

### 1. `PaneManager.resize_fractions`（新增，置于 `resize`（381-404 行）之后）

```python
def resize_fractions(self, split: Split, index: int, delta: float) -> bool:
    """Transfer *delta* fraction between child *index* and its neighbor.

    Drag-resize primitive behind the separator gesture: *delta* is the
    pointer travel converted to fraction units.  The transfer is clamped
    so both slots keep at least MIN_FRACTION (pinned at the boundary
    instead of refusing, so a long drag parks at the limit); ``False``
    when nothing moved.
    """
    neighbor = index + 1 if index + 1 < len(split.children) else index - 1
    if delta > 0:
        delta = min(delta, split.sizes[neighbor] - MIN_FRACTION)
    else:
        delta = max(delta, -(split.sizes[index] - MIN_FRACTION))
    if delta == 0.0:
        return False
    split.sizes[index] += delta
    split.sizes[neighbor] -= delta
    if self.host is not None:
        self.host.apply_sizes()
    return True
```

语义与 `resize`（381-404 行）的钳制规则一致（MIN_FRACTION 下限、
`host.apply_sizes()` 收尾），只是步长来源从 RESIZE_STEP 变为指针位移。

### 2. `PaneHost` 拖拽状态与命中测试（类体新增）

`__init__`（427-433 行）追加两个实例属性：

```python
#: (box widget, model Split) pairs recorded by _build; the separator
#: hit-test walks this mapping (reconcile clears it on rebuild).
self._split_boxes: list[tuple[Widget, Split]] = []
#: Active separator drag: (split, child index, axis, last screen coord).
self._drag: tuple[Split, int, str, int] | None = None
```

`_build`（489-501 行）：在 `box = box_cls(*children, classes="pane-box")`
与 `self._style_split(box, node)` 之间记录 `self._split_boxes.append((box, node))`。
`reconcile`（514-550 行）：方法体开头（`self.manager.views.clear()` 处）
同步 `self._split_boxes.clear()`（整树重建后旧 box 全部失效）。

新增三个 handler 与一个命中测试：

```python
def _separator_hit(self, x: int, y: int) -> tuple[Widget, Split, int, str] | None:
    """Hit-test separator border cells; (box, split, child index, axis)."""
    for box, split in self._split_boxes:
        children = list(box.children)
        for i in range(len(children) - 1):
            region = children[i].region
            if split.axis == "vertical":
                if (
                    region.x + region.width - 1 == x
                    and region.y <= y < region.y + region.height
                ):
                    return (box, split, i, "vertical")
            elif (
                region.y + region.height - 1 == y
                and region.x <= x < region.x + region.width
            ):
                return (box, split, i, "horizontal")
    return None

def on_mouse_down(self, event: MouseDown) -> None:
    """Start a separator drag when the press lands on a divider border."""
    if event.button != 1:
        return
    hit = self._separator_hit(event.screen_x, event.screen_y)
    if hit is None:
        return
    box, split, index, axis = hit
    self._drag = (
        split, index, axis,
        event.screen_x if axis == "vertical" else event.screen_y,
    )
    self.capture_mouse()
    event.stop()
    event.prevent_default()

def on_mouse_move(self, event: MouseMove) -> None:
    """Convert pointer travel to a fraction transfer (live resize)."""
    if self._drag is None or len(self._drag) != 4:
        return
    split, index, axis, last = self._drag
    pos = event.screen_x if axis == "vertical" else event.screen_y
    delta_cells = pos - last
    self._drag = (split, index, axis, pos)
    if delta_cells == 0:
        return
    box = next(
        (box for box, s in self._split_boxes if s is split), None
    )
    if box is None:
        return
    span = box.region.width if axis == "vertical" else box.region.height
    if span <= 0:
        return
    if self.manager.resize_fractions(split, index, delta_cells / span):
        event.stop()

def on_mouse_up(self, event: MouseUp) -> None:
    """End the separator drag."""
    if self._drag is None:
        return
    self._drag = None
    self.release_mouse()
    event.stop()
```

imports 追加：`from textual.events import MouseDown, MouseMove, MouseUp`。

注意：`_drag` 的第三元存的是模型轴语义（`"vertical"` = 左右分布，
对应 `Split.axis` 的取值，见 `yate/session.py:225-227`），与 CSS 类名的
`pane-sep-v`（border-right）一致；`_separator_hit` 返回值含 box，
`on_mouse_move` 不再二次查找。上例 `on_mouse_move` 中先取 box 再算 span
的写法以返回四元组为准（实现时保持一处返回 `(box, split, index, axis)`）。

## 四、新增测试（详细用例）

### `tests/test_panes.py`（模型级，无 App；夹具参照本文件既有 PaneManager 用例）

1. `test_resize_fractions_grows_first_slot`
   - 前置：`Split("vertical", [leaf_a, leaf_b], [0.5, 0.5])` 的 manager。
   - 操作：`resize_fractions(split, 0, 0.1)`。
   - 断言：返回 `True`；`split.sizes == [0.6, 0.4]`（pytest.approx）。
2. `test_resize_fractions_clamps_at_min_fraction`
   - 前置：sizes `[0.5, 0.5]`。
   - 操作：`resize_fractions(split, 0, 0.9)`（远超可用空间）。
   - 断言：`split.sizes[1] >= MIN_FRACTION`，且
     `split.sizes == [1 - MIN_FRACTION, MIN_FRACTION]`（approx）。
3. `test_resize_fractions_negative_delta_shrinks_first_slot`
   - 操作：`resize_fractions(split, 0, -0.2)`。
   - 断言：`split.sizes == [0.3, 0.7]`（approx）。
4. `test_resize_fractions_zero_delta_returns_false`
   - 操作：sizes 已在钳制边界（`[MIN_FRACTION, 1 - MIN_FRACTION]`）时
     请求继续缩小 `resize_fractions(split, 0, -0.1)`。
   - 断言：返回 `False`，sizes 不变。

### `tests/test_app_panes.py`（pilot 级，参照本文件既有 run_test 用例）

5. `test_separator_drag_updates_split_sizes`
   - 前置：`app.run_test()`；`pilot.press(":", "vsplit", "enter")` 触发
     二分（sizes `[0.5, 0.5]`）；`pilot.pause()` 等布局。
   - 操作：query `PaneHost`，取 `app.editor.pane_host`，由
     `_split_boxes` 与子 region 计算竖向分隔格屏幕坐标
     `(sx, sy)`；`pilot.mouse_down(None, offset=(sx, sy))`；再用
     `pilot._post_mouse_events([MouseMove, MouseUp], offset=(sx + 4, sy))`
     模拟右拖（`_post_mouse_events` 是 pilot 公开鼠标方法共用的底层，
     pilot.py:383）。
   - 断言：`app.editor.panes.root.sizes[0] > 0.5`（approx 大于），且两个
     EditorView 的 `region.width` 差随 fraction 变化（左宽于右）。
6. `test_separator_click_does_not_move_cursor`
   - 前置：同上二分布局；先记 `panes.active` 与其 `buf.cursor`。
   - 操作：仅在分隔格上 `pilot.click(None, offset=(sx, sy))`。
   - 断言：`panes.active` 不变、`buf.cursor` 不变（分隔格点击不落进
     文本区、不改变焦点——plan-c 落地后由 plan-c 的边框守卫维持）。

## 五、验证方案

| 项 | 命令 | 通过判定 |
|---|---|---|
| 单测 | `.venv\Scripts\python.exe -m pytest tests/test_panes.py tests/test_app_panes.py -q` | 退出码 0，含上述 6 个新用例 |
| 回归 | `.venv\Scripts\python.exe -m pytest tests/test_session.py tests/test_dispatch_guards.py -q` | 退出码 0（窗格树模型与调度守卫无回归） |
| 类型 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | 零诊断 |
| 手工 | 运行 `yate`，`:vsplit`/`:split` 后按住分隔线拖动 | 分隔线实时跟随、到边界停住；松手后键盘 `ctrl+w +/-` 仍工作 |

## 六、风险与回滚

- 风险：命中依赖 `Widget.region` 的屏幕坐标（含边框 1 格），终端缩放/
  DPI 变化不影响（cell 坐标系）；`region` 在布局未完成时可能为 0 尺寸
  ——`_separator_hit` 的 range 判断天然为 False，安全。
- 风险：`on_mouse_move` 在捕获期间事件持续到达 PaneHost；若 `_drag`
  期间发生 reconcile（`:only` 等），`_split_boxes` 已清空、box 查找
  返回 None → 拖拽静默失效，不会崩溃（模型已重建，fraction 以模型为准）。
- 风险：wave-2 落地 plan-c 后，EditorView 会先消费文本区按下——分隔格
  守卫是 plan-c 的硬性步骤（见其 §二.4），本计划的用例 6 在 wave-2 后
  仍须通过（它就是跨计划契约的回归钉）。
- 回滚：单提交还原 `yate/editor_view/panes.py`；`resize_fractions`
  为新方法无既有调用方，还原即回到纯键盘 resize。
