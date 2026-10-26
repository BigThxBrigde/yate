# Hex View - Plan D: 既有测试改写与冒烟场景同步

## 目标

同步改写既有测试与冒烟场景，使其与 `is_text_file` 语义变更及 hex view 新行为对齐。

## 非目标

- 新增 hex view 功能（plan-b / plan-c 已完成）；
- 修改 `is_text_file` 语义（plan-a 已完成）。

## 输入

- `tests/test_workspace_filter.py:486-490`（`test_is_text_file_rejects_unknown_suffixes`，plan-a 已改写）；
- `tests/test_diff_integration.py:131`（依赖 TEXT_SUFFIXES 信任语义）；
- `tools/smoke_test/scenarios/diffview.py:271-302`（断言 `not a text file: blob.bin`）；
- `tests/test_architecture.py:193-248`（`UI_FROZEN_FILES` 登记）。

## 独占文件清单

- `tests/test_diff_integration.py`（核查：diff 场景不变，断言仍成立）；
- `tools/smoke_test/scenarios/diffview.py`（核查：冒烟场景不变，断言仍成立）；
- `tests/test_architecture.py`（修改：`UI_FROZEN_FILES` 登记 `flows/overlay_flows.py` 新增 `yate.editor_view.hexview`）；
- `tools/smoke_test/scenarios/hexview.py`（可选新增：hex view 冒烟场景）；
- `tools/smoke_test/scenarios/__init__.py`（可选修改：注册新场景）。

## 具体修改

### 1. 核查 `tests/test_diff_integration.py:131`

**当前注释**：
```python
``Workspace.is_text_file`` trusts TEXT_SUFFIXES before any content
sniffing, so the entry point must check ``is_file()`` first --
``Document.open`` would otherwise raise ``IsADirectoryError`` straight
into the crash path (command actions have no try/except).
```

**决策**：diff 场景仍拒绝二进制文件（`overlay_flows.py:155` 不变），该注释描述的语义（TEXT_SUFFIXES 信任）仍成立——白名单文件仍快速路径，未知扩展名才嗅探。**无需修改**。

### 2. 核查 `tools/smoke_test/scenarios/diffview.py:271-302`

**当前断言**：
```python
await run_command(pilot, "diff blob.bin b.txt")
checks.append(Check("binary_no_screen", 1, len(app.screen_stack)))
checks.append(Check("binary_message", True,
                    "not a text file: blob.bin" in message_text(app)))
```

**决策**：diff 命令仍拒绝二进制文件（`overlay_flows.py:155` 不变），`.bin` 后缀不在 `TEXT_SUFFIXES` 且内容为二进制字节，嗅探后仍判非文本。**断言仍成立，无需修改**。

### 3. 修改 `tests/test_architecture.py`

**在 `UI_FROZEN_FILES["flows/overlay_flows.py"]` 集合中追加**（`test_architecture.py:234-243`）：
```python
"flows/overlay_flows.py": {
    "yate.editor_view",
    "yate.editor_view.commandline",
    "yate.editor_view.diffview",
    "yate.editor_view.find_replace",
    "yate.editor_view.hexview",  # NEW
    "yate.editor_view.manual",
    "yate.editor_view.modals",
    "yate.editor_view.palette",
    "yate.editor_view.screensaver",
},
```

**说明**：`flows/document_flows.py` 不新增 `editor_view` 导入（hex view 打开改走回调注入），故无需修改其登记。

### 4. 全仓 grep 核实旧行为测试

**核实清单**（plan-a 已覆盖 `test_workspace_filter.py:486`，此处列出其余命中）：

| 文件:行号 | 测试名 | 是否需改 |
|---|---|---|
| `tests/test_workspace_filter.py:486` | `test_is_text_file_rejects_unknown_suffixes` | **需改**（plan-a 已改写） |
| `tests/test_diff_integration.py:131` | （注释，非断言） | 不变 |
| `tools/smoke_test/scenarios/diffview.py:271` | （冒烟场景） | 不变（diff 仍拒绝二进制） |

**结论**：除 `test_workspace_filter.py:486` 外，无其他测试依赖「未知扩展名 + 文本内容 → 被拒」旧行为。

### 5. （可选）新增冒烟场景 `tools/smoke_test/scenarios/hexview.py`

**场景注册机制**（`tools/smoke_test/scenarios/__init__.py`）：
- 每个场景模块导出 `SCENARIOS: list[Scenario]`；
- `__init__.py` 按功能分组拼接（core → edit → ... → diffview → integration → ...）。

**场景设计**：
```python
from tools.smoke_test.harness import Check, Scenario, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import run_command

async def _hex_view_opens_for_binary(pilot, app):
    """Open a binary file in hex view; verify SVG contains offset:hex:ASCII."""
    # Create a binary fixture.
    bin_path = app.workspace.root / "test.bin" if app.workspace.root else Path("test.bin")
    bin_path.write_bytes(b"\x00\x01\x02\x03" * 16)
    # Open via :e command.
    await run_command(pilot, f"e {bin_path.name}")
    # Verify HexScreen is pushed (check SVG for offset pattern).
    svg = snapshot_svg(app)
    return [
        Check("hex_screen_pushed", True, "00000000:" in svg),
    ]

SCENARIOS = [
    Scenario(
        name="hex_view_opens_for_binary",
        fn=_hex_view_opens_for_binary,
        tags={"hex", "view"},
    ),
]
```

**注册**：在 `tools/smoke_test/scenarios/__init__.py` 追加：
```python
from tools.smoke_test.scenarios.hexview import SCENARIOS as _HEXVIEW
...
SCENARIOS: list[Scenario] = [
    ...
    *_HEXVIEW,  # Append after *_DIFFVIEW
]
```

**判定**：若注册机制复杂或冒烟场景不稳定，可判为可选并说明。

## 输出

- 既有测试与 `is_text_file` 新语义对齐；
- `UI_FROZEN_FILES` 登记完整；
- （可选）新增 hex view 冒烟场景。

## 验收命令

```powershell
cd D:\Programming\yate-hex-view
.venv\Scripts\python.exe -m pytest tests/test_diff_integration.py -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
```

通过判定标准：
- pytest 退出码 0，所有用例通过；
- 架构测试无新增违规；
- 冒烟场景通过（仓库根执行，非 `cd tools\smoke_test`）。

## 风险清单

| 风险 | 缓解 |
|---|---|
| 冒烟场景实际依赖旧行为 | 核查确认 diff 拒绝二进制不变，断言仍成立 |
| `UI_FROZEN_FILES` 登记遗漏 | 本波次显式列出新增键 |
| 新增冒烟场景不稳定 | 判为可选，若失败可跳过 |

## 回滚路径

恢复 `tests/test_architecture.py` 的 `UI_FROZEN_FILES` 即可回滚。

## 触碰架构边界

- **R11**：`UI_FROZEN_FILES` 登记 `flows/overlay_flows.py` 新增 `yate.editor_view.hexview`。

## 【执行】【审核】迭代记录段

- 2026-10-24 主代理复核修订：冒烟验证命令统一为仓库口径（`.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4`）；
  增加可选冒烟场景 `tools/smoke_test/scenarios/hexview.py`；
  全仓 grep 核实无其他测试依赖旧行为（除 `test_workspace_filter.py:486` 外）。
