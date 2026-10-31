# test-speedup-flake-fix-plan-a：修复并行 flake

**波次**：wave-1（阻塞后续所有全量跑的可信度）

## 一、目标

修复 `tests/test_app_panes.py::test_separator_click_does_not_move_cursor` 在 `-n auto`
下的并行 flake：`textual.pilot.OutOfBounds: Target offset outside currently-visible screen region`。

## 二、非目标

- 不修改产品代码（`yate/editor_view/panes.py` 等）；
- 不修改其他测试用例；
- 不引入 `pytest.mark.flaky` 或重试机制（按 `python-coding-style.md` §4.7，
  时序敏感用例必须修用例本身）。

## 三、根因分析

**问题定位**：[test_app_panes.py:525-560](file:///D:/Programming/yate-test-speedup/tests/test_app_panes.py#L525-L560)

```python
await pilot.press(":", "v", "s", "p", "l", "i", "t", "enter")
assert await wait_until(pilot, lambda: panes.leaf_count == 2)
await pilot.pause()
# ...
sx = left_view.region.x + left_view.region.width - 1  # ← 用过期 region
sy = left_view.region.y + left_view.region.height // 2
```

**根因**：`:vsplit` 后 `wait_until(leaf_count==2)` 为真时，pane region 尚未完成布局
（Textual 的布局计算是异步的），`left_view.region.width` 仍为全屏宽，导致 `sx`
计算出的坐标越界。

**修复方向**：点击前用 `wait_until` 等待 region 收敛（如 `left_view.region.width < 屏宽`）
后再计算坐标。

## 四、实施步骤

### 步骤 1：修改测试用例

**改动文件**：`tests/test_app_panes.py`

**改动位置**：[L538-548](file:///D:/Programming/yate-test-speedup/tests/test_app_panes.py#L538-L548)

**改动内容**：

```python
# 原代码
await pilot.press(":", "v", "s", "p", "l", "i", "t", "enter")
assert await wait_until(pilot, lambda: panes.leaf_count == 2)
await pilot.pause()
root = panes.root
assert isinstance(root, PaneSplit)

host = panes.host
assert host is not None
box, _split = host._split_boxes[0]
left_view, _right_view = box.children
sx = left_view.region.x + left_view.region.width - 1
sy = left_view.region.y + left_view.region.height // 2

# 新代码
await pilot.press(":", "v", "s", "p", "l", "i", "t", "enter")
assert await wait_until(pilot, lambda: panes.leaf_count == 2)
root = panes.root
assert isinstance(root, PaneSplit)

host = panes.host
assert host is not None
box, _split = host._split_boxes[0]
left_view, _right_view = box.children

# Wait for layout to converge: region width must be less than full screen width
# (Textual's layout calculation is async, so leaf_count==2 doesn't mean regions
# are updated yet). The screen width is 100 (from run_test(size=(100, 30))).
assert await wait_until(
    pilot, lambda: left_view.region.width < 100, timeout=2.0
), "left_view region did not converge after vsplit"

sx = left_view.region.x + left_view.region.width - 1
sy = left_view.region.y + left_view.region.height // 2
```

**改动说明**：

1. 移除多余的 `await pilot.pause()`（`wait_until` 已包含等待语义）；
2. 新增 `wait_until` 等待 `left_view.region.width < 100`（屏宽 100，vsplit 后左 pane
   宽度应小于全屏宽）；
3. 超时设为 2.0s（并行负载下布局收敛可能需要更多时间，但不应超过 2s）。

## 五、新增测试

无新增测试（本次只修现有用例）。

## 六、验证方案

### 验证目标

证明修复后的用例在 `-n auto` 下不再 flake。

### 验证命令

```powershell
# 1. 单文件验证（连续跑 5 次，确保无 flake）
.venv\Scripts\python.exe -m pytest tests/test_app_panes.py::test_separator_click_does_not_move_cursor -n auto -v
# 重复 5 次，全部通过

# 2. 全量验证（确保无回归）
.venv\Scripts\python.exe -m pytest tests/ -q -n auto

# 3. 架构守卫（确保无违规）
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q

# 4. pyright（确保类型正确）
.venv\Scripts\python.exe -m pyright tests/test_app_panes.py
```

### 通过判定

- 连续 5 次 `-n auto` 跑该用例，全部通过（退出码 0）；
- 全量 pytest 全绿；
- 架构守卫 37 项全绿；
- pyright 零诊断。

## 七、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `wait_until` 超时仍 flake | 增加 timeout 到 5.0s | 回退到 `await pilot.pause()` 多次（不推荐） |
| 修改引入新 bug | 改动极小，只加等待条件 | `git checkout tests/test_app_panes.py` |

## 八、独占文件清单

- `tests/test_app_panes.py`（只改这一个文件）

## 九、预计影响

- **测试时长**：该用例原耗时 ≈ 0.5s，修复后预计 ≈ 0.6s（增加 wait_until 轮询）；
- **可信度**：修复后 `-n auto` 全量跑结果可信，不再需要 `-n 1` 复核。
