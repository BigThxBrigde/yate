# 子计划 b：L1 会话级宏状态 `MacroState`（wave-1）

> 唯一规范来源：`overview.md` §1.5 + 主计划 `../macro-record-replay-unified-plan.md`
> §5.1 / §5.5；本文件自包含。状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F11（`session.py` 为 L1 UI-free 会话模型单一所有者）、F21
  （§五「状态放在正确的层」、R4/R8）。
- 上游依赖：**无**（与 plan-a / plan-c 并行，三者文件互斥）。
- 输出：`MacroState` 数据模型挂到 `EditorSession.macro`（含 `pending_count` 缺省 1，
  承载按键入口 count 前缀）；跨标签共享、内存级、不持久化；纯数据单测。

## 1. 独占文件清单（只改这些）

- `yate/session.py`
- `tests/test_macro_state.py`（新增）

> 不改 `yate/keymaps/*`、`yate/flows/*`、`tests/test_architecture.py`。产品源码
> `yate/**` 归属依据见 `overview.md` §2。

## 2. 具体修改（文件:行号）

### 2.1 `yate/session.py`

- **不要新增 import**：第 26 行已有 `from dataclasses import dataclass, field`、
  第 28 行已有 `from typing import Literal`，`MacroState` 所需全部齐备。
- 在 `OpenedHook` 别名（**第 41 行**）之后、`log = tracing.get_logger(__name__)`
  （**第 43 行**）之前，新增 `@dataclass class MacroState`，字段与方法严格按
  `overview.md` §1.5：

```python
@dataclass
class MacroState:
    """Session-level macro registers and the recording / replay state (L1)."""

    registers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    recording: str | None = None
    buffer: list[str] = field(default_factory=list)
    awaiting: Literal["record", "play"] | None = None
    last_played: tuple[str, int] | None = None
    playing: bool = False
    play_depth: int = 0
    pending_count: int = 1

    def recording_label(self) -> str | None:
        """Return the ``rec @<reg>`` status-bar label, or ``None``."""
        return f"rec @{self.recording}" if self.recording is not None else None

    def get(self, reg: str) -> tuple[str, ...]:
        """Return the recorded raw keys for *reg*, or ``()`` when unrecorded."""
        return self.registers.get(reg, ())
```

  - `pending_count: int = 1` 是标量缺省（N 缺省 1）：由 `editor_dispatch.py`
    （plan-g）在 `handle_key` 之前调 `take_pending_count()` 写入，`MacroFlows.begin_with`
    （plan-e）读之传给 `play(reg, count)` 后复位为 1；本层只存值，不含逻辑。
  - 可变默认值一律 `field(default_factory=...)`（`python-coding-style.md` §6.2
    「禁止可变默认参数」）。
  - docstring 用散文式（§二），ASCII；`#:` 常量注释风格不适用（这是类）。
  - **不引入**任何 `Editor` / `editor_components` / Textual 依赖（R4）。
- 在 `EditorSession.__init__`（**第 49-64 行**）末尾追加一行
  `self.macro = MacroState()`（放在 `self._on_opened = on_opened` 之后），
  并在模块 docstring（第 1-20 行）补一句说明「macro registers are session-level,
  in-memory, never persisted」——**只加一句 ASCII 说明，不改既有段落**。
- 不改动 `doc` / `buffer` / `open` / `activate` / 树操作等任何既有方法。

### 2.2 `tests/test_macro_state.py`（新增）

`from __future__ import annotations`；`from yate.session import EditorSession, MacroState`；
需要构造 `EditorSession` 时用项目既有 `YateConfig` fixture（沿用
`tests/conftest.py` 的现成 fixture，不得自建魔法配置）。用例见 §3。

## 3. 详细测试用例（`tests/test_macro_state.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_macro_state_defaults_empty_and_not_recording` | 无 | `MacroState()` | `registers == {}`、`buffer == []`、`recording is None`、`awaiting is None`、`last_played is None`、`playing is False`、`play_depth == 0`、`pending_count == 1`（N 缺省 1）、`recording_label() is None`、`get("a") == ()` |
| `test_macro_state_recording_label_formats_register` | `MacroState()` | 分别置 `recording="a"` / `"9"` / `None` 后调 `recording_label()` | 依次为 `"rec @a"` / `"rec @9"` / `None` |
| `test_macro_state_get_returns_immutable_tuple` | `MacroState()`，置 `registers["a"] = ("x", "y")` | `get("a")` / `get("z")` | `get("a") == ("x", "y")` 且 `isinstance(..., tuple)`；`get("z") == ()`；`registers` 未被 `get` 改写 |
| `test_macro_state_is_shared_across_documents_of_one_session`（跨标签共享） | `EditorSession(config)`，用 `open()` 打开两个临时路径（或既有 `open` fixture） | 置 `s.macro.registers["a"] = ("x",)`，切到另一 doc 后再读 | `s.macro is s.macro` 且 `s.macro.registers["a"] == ("x",)` 在切换前后恒等；`id(s.macro)` 不变 |
| `test_macro_state_is_not_shared_between_sessions`（不持久化 / 会话隔离） | 两个 `EditorSession(config)` 实例 | 对 `s1.macro` 写 `registers["a"]=("x",)`，读 `s2.macro` | `s1.macro is not s2.macro`；`s2.macro.registers == {}`、`s2.macro.get("a") == ()` |
| `test_macro_state_fields_reject_no_default_mutation_leak`（边界 / 异常流） | 两个 `MacroState()` 实例 | `m1.buffer.append("x")`；`m1.registers["a"] = ("y",)` | `m2.buffer == []`、`m2.registers == {}`（证明 `default_factory` 未共享可变默认值） |
| `test_macro_state_literal_awaiting_values_are_constrained` | 无 | 类型层面：pyright strict 对 `awaiting` 注解 `Literal["record","play"] | None` 校验 | pyright 零诊断；运行时用例断言默认 `awaiting is None`；赋 `"record"` / `"play"` 后可读取原值 |
| `test_macro_state_pending_count_defaults_to_one_and_is_resettable`（count 契约 / 边界） | `MacroState()` | 读默认 `pending_count`；置 `pending_count = 3` 后再写回 `1` | 默认 `pending_count == 1`（N 缺省 1）；置 3 后可读到 `3`；复位后 `pending_count == 1`；其它字段不受影响（`last_played is None`、`playing is False`、`play_depth == 0`） |

## 4. 验证方案

- **验证目标**：证明宏状态落在 L1 `EditorSession`（issue「架构落点」）、会话级
  内存、跨标签共享、不持久化、可变默认值无泄漏、`pending_count` 缺省 1 且可复位
  （按键 count 前缀的落盘载体）、类型注解满足 pyright strict。
- **需一并回归的既有测试**：`tests/test_architecture.py::test_keymaps_services_and_models_stay_ui_free`
  （R4 / `UI_FREE_FILES` 含 `session.py`）、`test_no_unregistered_upward_imports`；
  以及 `pytest tests/ -k "session" -q`（既有会话模型测试，执行者按实际文件名取）。
- **通过判定标准**：pyright 退出码 0 零诊断；pytest 退出码 0、断言全绿；R4 守卫
  无违规（`session.py` 不出现 `editor_components` / Textual 导入）。
- **无法自动化部分**：无。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pyright yate/session.py
.venv\Scripts\python.exe -m pytest tests/test_macro_state.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k "ui_free or upward_imports"
```

## 6. 架构边界与守卫

- 触碰层级：仅 L1（`session.py`，`_LAYER_RANKS` 第 154 行；`UI_FREE_FILES` 第 187 行）。
- R 条款：R4（模型层 UI-free）、R8（具体对象共享，不为宏状态造协议）、
  §五自检清单「状态放在正确的层」。
- 守卫用例：`tests/test_architecture.py::test_keymaps_services_and_models_stay_ui_free`、
  `test_pane_model_lives_in_l1_session`、`test_no_unregistered_upward_imports`
  （**只跑不改**；新增守卫归 plan-d）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 误用可变默认参数导致跨实例状态泄漏 | `field(default_factory=...)` + 专门用例 | `git checkout -- yate/session.py tests/test_macro_state.py` |
| 状态误挂到 `Document` / `TextBuffer`（变成 per-tab）破坏跨标签共享 | §2.1 只改 `EditorSession.__init__` + 跨标签用例 | 同上 |
| 新 import 触发 R4 / 层秩违规 | 明确不新增 import；跑 R4 与层秩守卫 | 同上 |
| 模块 docstring 补句引入非 ASCII 注释 | 只加一句 ASCII 英文；跑 `test_comments_and_docstrings_stay_ascii` | 同上 |
| `pending_count` 未复位泄漏到下一次回放 | `MacroFlows.begin_with`（plan-e）读后复位为 1 + 本计划默认 / 复位用例 | 同上 |
