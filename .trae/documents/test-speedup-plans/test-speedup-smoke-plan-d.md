# test-speedup-smoke-plan-d：补全冒烟场景

**波次**：wave-3（依赖 wave-2 完成）

## 一、目标

新增 which-key、补全类等冒烟场景，冒烟总数从 117 升至 120+。

## 二、非目标

- 不修改现有冒烟场景；
- 不修改冒烟测试框架（`tools/smoke_test/harness.py`）；
- 不追 LSP 相关场景（`YATE_PYTHON_LSP=off` 下跳过，不属缺口）。

## 三、冒烟缺口清单

| 场景 | 功能模块 | 优先级 |
|---|---|---|
| which-key | `yate/flows/whichkey_flows.py`, `yate/editor_view/whichkey.py` | P0 |
| 补全类（参数补全 / 命令补全） | `yate/flows/prompt_completion.py`, `yate/flows/completion_flows.py` | P1 |

**说明**：素材提及"无 input_assist 场景"，经调研 `yate/flows/` 下无 `input_assist_flows.py`，
但有 `prompt_completion.py`（参数补全）和 `completion_flows.py`（通用补全）。
计划中按"补全类"场景统一处理。

## 四、实施步骤

### 步骤 1：新增 which-key 冒烟场景

**新增文件**：`tools/smoke_test/scenarios/whichkey.py`

**场景设计**：

```python
"""Which-key smoke scenarios."""

from __future__ import annotations

from pathlib import Path

from tools.smoke_test.harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import run_command, type_text, wait_until

__all__ = ["SCENARIOS"]


async def _which_key_toggle(tmp: Path) -> ScenarioResult:
    """Toggle which-key panel via F9 and verify it appears."""
    app = new_app(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Press F9 to toggle which-key panel
        await pilot.press("f9")
        await pilot.pause()
        # Verify which-key panel is visible (check screen stack or panel presence)
        # The exact assertion depends on how WhichKeyPanel is rendered
        checks.append(Check("which_key_visible", True, ...))
        # Press F9 again to hide
        await pilot.press("f9")
        await pilot.pause()
        checks.append(Check("which_key_hidden", False, ...))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("which_key_toggle", checks, rows)


async def _which_key_ctrl_w_chord(tmp: Path) -> ScenarioResult:
    """Press ctrl+w and verify which-key shows window chord hints."""
    app = new_app(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Press ctrl+w to enter window chord mode
        await pilot.press("ctrl+w")
        await pilot.pause()
        # Verify which-key panel shows chord hints
        checks.append(Check("chord_hints_visible", True, ...))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("which_key_ctrl_w_chord", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("which_key_toggle", _which_key_toggle),
    Scenario("which_key_ctrl_w_chord", _which_key_ctrl_w_chord),
]
```

**注册场景**：修改 `tools/smoke_test/scenarios/__init__.py`

```python
# 新增导入
from tools.smoke_test.scenarios.whichkey import SCENARIOS as _WHICHKEY

# 在 SCENARIOS 列表中添加
SCENARIOS: list[Scenario] = [
    *_CORE,
    *_EDIT,
    # ...
    *_WHICHKEY,  # 新增
    # ...
]
```

**生成基线**：

```powershell
.venv\Scripts\python.exe -m tools.smoke_test snapshot
```

### 步骤 2：新增补全类冒烟场景（视时间）

**新增文件**：`tools/smoke_test/scenarios/completion.py`

**场景设计**：

```python
"""Completion smoke scenarios (command completion, parameter completion)."""

from __future__ import annotations

from pathlib import Path

from tools.smoke_test.harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import run_command, type_text, wait_until

__all__ = ["SCENARIOS"]


async def _command_completion(tmp: Path) -> ScenarioResult:
    """Type : and verify command completion appears."""
    app = new_app(target=tmp / "scratch.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Press : to enter command mode
        await pilot.press(":")
        await pilot.pause()
        # Type partial command
        await type_text(pilot, "fin")
        await pilot.pause()
        # Verify completion popup appears
        checks.append(Check("completion_visible", True, ...))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("command_completion", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("command_completion", _command_completion),
]
```

**注册场景**：修改 `tools/smoke_test/scenarios/__init__.py`

```python
from tools.smoke_test.scenarios.completion import SCENARIOS as _COMPLETION

SCENARIOS: list[Scenario] = [
    # ...
    *_COMPLETION,  # 新增
    # ...
]
```

**生成基线**：

```powershell
.venv\Scripts\python.exe -m tools.smoke_test snapshot
```

## 五、新增测试清单

| 场景文件 | 新增场景数 | 验证目标 |
|---|---|---|
| `tools/smoke_test/scenarios/whichkey.py` | 2 | which-key 面板切换、ctrl+w 和弦提示 |
| `tools/smoke_test/scenarios/completion.py` | 1 | 命令补全弹窗 |

## 六、验证方案

### 验证目标

证明新增冒烟场景可正常运行，且基线已登记。

### 验证命令

```powershell
# 1. 单场景验证
.venv\Scripts\python.exe -m tools.smoke_test run which_key_toggle
.venv\Scripts\python.exe -m tools.smoke_test run which_key_ctrl_w_chord
.venv\Scripts\python.exe -m tools.smoke_test run command_completion

# 2. 基线更新（首次运行）
.venv\Scripts\python.exe -m tools.smoke_test snapshot

# 3. 基线校验（后续运行）
.venv\Scripts\python.exe -m tools.smoke_test compare

# 4. 全量冒烟
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4

# 5. 全量 pytest（确保无回归）
.venv\Scripts\python.exe -m pytest tests/ -q -n auto

# 6. 架构守卫
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q

# 7. pyright
.venv\Scripts\python.exe -m pyright tools/
```

### 通过判定

- 新增场景全部通过（退出码 0）；
- 基线 JSON 文件已生成（`tools/smoke_test/smoke_baselines/which_key_toggle.json` 等）；
- `compare` 无 drift；
- 全量冒烟通过；
- 全量 pytest 全绿；
- 架构守卫 37 项全绿；
- pyright 零诊断。

## 七、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 新增场景 flake | 用 `wait_until` 等待 UI 收敛 | 删除场景或登记 issue |
| 基线漂移 | 用 `snapshot` 子命令重新登记 | 基线 JSON 文件 `git checkout` |
| 场景失败无法定位 | 确保底层功能已被单元测试覆盖（wave-2 已补强） | 查看单元测试结果 |

## 八、独占文件清单

- `tools/smoke_test/scenarios/whichkey.py`（新增）
- `tools/smoke_test/scenarios/completion.py`（新增，视时间）
- `tools/smoke_test/scenarios/__init__.py`（修改）
- `tools/smoke_test/smoke_baselines/*.json`（新增基线文件）

## 九、预计影响

- **冒烟场景数**：从 117 升至 120+；
- **冒烟时长**：预计增加 2-3s（每个场景 ≈ 1s）；
- **覆盖度**：which-key、补全类功能纳入冒烟防护面。

## 十、修订记录

1. （第 2 轮，主代理核验）冒烟 CLI 不存在 `--update-baselines` 旗标
   （tools/smoke_test/cli.py 参数面核验）：基线登记命令统一改为
   `python -m tools.smoke_test snapshot` 子命令，风险表同步修正。
