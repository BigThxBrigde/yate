# 子计划 e：L3 编排模块 `MacroFlows`（wave-2）

> 唯一规范来源：`overview.md` §1.4 / §1.6 + 主计划
> `../macro-record-replay-unified-plan.md` §5.5(1)(4)(5) / AC2 / AC4 / AC6；
> 本文件自包含。状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F11（`MacroState` 契约，含 `pending_count`）、F8
  （`ed.handle_raw_key` 派发契约）、F23（count 由 dispatch 调
  `take_pending_count()` 在 `handle_key` 之前捕获，写入 `pending_count`）、
  F21（§四回调注入 / R12 日志）、`overview.md` §1.6 全部签名与文案。
  **本模块不直接调用** `take_pending_count()`（那是 L1 keymap 方法，归 plan-d，
  由 dispatch 调用），只消费已落盘的 `MacroState.pending_count` 值。
- 上游依赖：**wave-1 全部验收通过**（尤其 plan-b 的 `EditorSession.macro` 含
  `pending_count`）。
- 输出：新增 `yate/flows/macro_flows.py`（`MacroFlows` 编排 + 防护 + 上限，
  含 `request_play(count)` / `replay_last(count)` / `begin_with` 读 `pending_count`）；
  完整单元覆盖（正常 / 边界 / 异常流，含按键 count 前缀 N 次 / 沿用 / 越界）。

## 1. 独占文件清单（只改这些）

- `yate/flows/macro_flows.py`（**新增**）
- `tests/test_macro_flows.py`（**新增**）

> 不改 `yate/session.py`（plan-b）、`yate/editor_dispatch.py`（plan-g）、
> `yate/actions.py` / `commands.py`（plan-h）、`tests/test_architecture.py`（plan-d）。
> 产品源码归属依据见 `overview.md` §2。

## 2. 具体修改（文件:行号）

### 2.1 `yate/flows/macro_flows.py`（新增，预计远低于 800 行）

- 模块 docstring（ASCII 散文式）：说明本模块是宏录制 / 回放的 L3 流程编排，
  状态由 L1 `EditorSession.macro` 持有，派发 / 提示经构造注入的回调，不持 App
  句柄（守卫 `test_flow_modules_hold_no_app_handle`）。
- 强制首行可执行语句 `from __future__ import annotations`；导入分组：标准库
  `from collections.abc import Callable`；项目内部 `from yate.session import
  EditorSession`、`from yate.keymaps.keys import MACRO_CONTROL_KEYS`（L3→L0，
  用于 `record_raw` 排除宏控制键）、`from yate.logs import tracing`（若记日志）。
  **不 import** `yate.editor` / `yate.app` / `editor_components`（R11 免登记）。
- 模块级 `log = tracing.get_logger(__name__)`（R12）；日志一律惰性 `%` 格式
  （`log.debug("macro play: reg=%s count=%d", reg, count)`），**禁止** f-string /
  `print()` / `self.log`。
- 契约常量（`#:` 注释，ASCII）：

```python
type DispatchRaw = Callable[[str], bool]          # PEP 695，注入 ed.handle_raw_key
type Notify = Callable[[str, str], None]          # (text, kind)，注入 ed.message

MAX_PLAY_DEPTH: int = 1
MAX_MACRO_KEYS: int = 10000
MACRO_REGISTER_CHARS: str = "abcdefghijklmnopqrstuvwxyz0123456789"
```

  两个别名用 PEP 695 `type` 语句（`test_callable_aliases_use_type_statements`
  会拦截 `X = Callable[...]` 写法）；别名留在本模块，不建全局别名模块。

- `class MacroFlows:`（docstring 说明职责与不变量）方法严格按 `overview.md` §1.6：
  - `__init__(self, session: EditorSession, dispatch_raw: DispatchRaw,
    notify: Notify) -> None`：保存 `self._session`、`self._dispatch_raw`、
    `self._notify`（带类型注解）。
  - `toggle_record()`：先 `reject_if_playing()`；`macro.recording is not None`
    → `stop()`；否则 `macro.awaiting = "record"`。**不读写 `pending_count`**
    （`<f10>` 录制键不消耗 count，见 overview §1.8 卫语句 0）。
  - `request_play(count: int = 1)`：先 `reject_if_playing()`；否则写
    `macro.pending_count = count`（幂等，参数来自按键动作读取的 `pending_count`
    或单测缺省 1）、置 `macro.awaiting = "play"`。
  - `replay_last(count: int | None = None)`：先 `reject_if_playing()`；
    `last_played is None` → notify `"no last macro replay"` / `"warn"`；否则
    `effective = last_played[1] if (count is None or count == 1) else count`
    （None / 1 沿用上次次数、≥2 覆盖），调 `play(last_played[0], effective)`。
    `:macro-replay-last [count]` 命令（plan-h）仍走 `play(last_reg, count)`
    （§2.2 裁定不变）。
  - `begin_with(reg)`：`awaiting is None` → return；`reg` 校验
    `len(reg) == 1 and reg in MACRO_REGISTER_CHARS`；非法 → notify
    `"macro register must be one character in a-z0-9"` / `"warn"`、清 awaiting；
    合法且 `awaiting == "record"` → `recording = reg`、`buffer = []`、
    `registers.pop(reg, None)`（同名覆盖语义：开始即清旧）、清 awaiting；合法且
    `awaiting == "play"` → 清 awaiting，取 `count = macro.pending_count`、
    复位 `macro.pending_count = 1`，调 `play(reg, count)`（**不再固定 1**）。
  - `play(reg, count)`：① `reject_if_playing()` 真 → return；② `macro.get(reg) == ()`
    → notify `"macro register @<reg> is empty"` / `"warn"`、return；③ `count < 1`
    或 `count > MAX_MACRO_KEYS` → notify `"macro count must be a positive integer"`
    / `"warn"`、return；④ `macro.play_depth += 1`，若 `> MAX_PLAY_DEPTH` 则复位、
    notify `"macro replay already in progress"` / `"warn"`、return；⑤
    `macro.playing = True`；⑥ `try:` 循环 `count` 次、每次 `for raw in
    macro.get(reg): self._dispatch_raw(raw)`；`finally:` `macro.playing = False`、
    `macro.play_depth -= 1`；⑦ 成功写 `macro.last_played = (reg, count)`。
    **不吞异常**（`python-coding-style.md` §4.5）：`dispatch_raw` 抛异常时 `finally`
    复位后向上传递；测试用 `pytest.raises` 覆盖。
  - `stop()`：`macro.registers[macro.recording] = tuple(macro.buffer)`、
    `macro.recording = None`、`macro.buffer = []`；未在录制时 no-op（`:macro-stop`
    的 warn 由 plan-h 命令层负责）。
  - `record_raw(raw)`：`recording is None` → no-op；`raw in MACRO_CONTROL_KEYS` →
    跳过（与 plan-g 的排除双保险）；`len(macro.buffer) >= MAX_MACRO_KEYS` →
    notify `"macro sequence limit reached"` / `"warn"`、不追加；否则 append。
  - `reject_if_playing()`：`macro.playing` 真 → notify
    `"macro replay already in progress"` / `"warn"`、返回 `True`；否则 `False`。
  - `is_playing` 只读属性（可选）：`return self._session.macro.playing`，供 plan-g
    的拒绝分支复用（若 plan-g 直接读 `ed.session.macro.playing` 则不必）。
- **不新增** `Protocol` / `TYPE_CHECKING` / `Any` / `# type: ignore`；不用
  `*Feature` / `*Host` / `*Ops` / `*Delegate` / `*Controller` 命名。

### 2.2 `replay_last` 与按键 count 的口径（定死，避免 plan-h 歧义）

`replay_last(count: int | None = None)` 仅供 `<f12>` 按键动作使用；count 由 dispatch
（plan-g）在 `handle_key` 之前调 `ed.keymaps.active.take_pending_count()` 捕获并写入
`MacroState.pending_count`，按键动作体（plan-h）读之作为 `count` 传入。语义：
`count is None or count == 1` → 沿用 `last_played[1]`（无数字前缀 / vsc 恒 1）；
`count >= 2`（如 `3<f12>`）→ 覆盖为 `count` 次。`1<f12>` 与「无前缀」因
`take_pending_count() -> int` 无法区分而并入「沿用」，登记为 v1 已知边界
（overview §1.8 / 主计划 §5.5(3)）。

`:macro-replay-last [count]` 命令（plan-h）契约**不变**：命令体调
`editor.macro_flows.play(last_reg, count)`（复用 `MacroFlows.play` 的校验与防护，
无参时 `count = last_played[1]`），**不调用** `replay_last()`。四命令入口与按键入口
在 N≥2 与无前缀两情形结果一致（AC7）。须在报告中登记。

### 2.3 `tests/test_macro_flows.py`（新增）

`from __future__ import annotations`；用 `EditorSession(config)` 真对象（沿用
`tests/conftest.py` 的 `config` fixture）+ 记录调用的假回调：

```python
calls: list[str] = []
notes: list[tuple[str, str]] = []
dispatch = lambda raw: calls.append(raw) or True   # 实际写成 def，禁止 lambda 堆叠
notify = lambda text, kind: notes.append((text, kind))
flow = MacroFlows(session, dispatch, notify)
```

（测试代码同样遵守 `python-coding-style.md`；回调写成有名字的函数 / `def`，
不用堆叠 lambda。）

## 3. 详细测试用例（`tests/test_macro_flows.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_toggle_record_enters_awaiting_then_starts_with_register` | `flow` + 空 `session.macro` | `flow.toggle_record()`；`flow.begin_with("a")` | 第一步 `macro.awaiting == "record"`、`recording is None`；第二步 `recording == "a"`、`awaiting is None`、`buffer == []`、`registers == {}`、`recording_label() == "rec @a"` |
| `test_toggle_record_while_recording_stops_and_freezes_tuple` | `flow`；录制态 `recording="a"`，`buffer=["x","y"]` | `flow.toggle_record()` | `macro.registers["a"] == ("x","y")` 且类型为 `tuple`；`recording is None`、`buffer == []` |
| `test_stop_overwrites_same_register_and_keeps_others` | `flow`；先录 "a"=["x","y"] 停止，再录 "b"=["p"] 停止，再录 "a"=["z"] 停止 | 三次 stop | `registers == {"a": ("z",), "b": ("p",)}`（同名覆盖、其它寄存器不干扰，AC6） |
| `test_play_repeats_raw_sequence_exact_count` | `flow`；`registers["a"]=("x","y")` | `flow.play("a", 3)` | `calls == ["x","y","x","y","x","y"]`（6 次、顺序精确）；`last_played == ("a",3)`；`playing is False`、`play_depth == 0`；`notes == []` |
| `test_play_default_count_is_one_via_begin_with_play` | `flow`；`registers["q"]=("j",)` | `flow.request_play()`（缺省 1）→ `flow.begin_with("q")` | `calls == ["j"]`（1 次）；`last_played == ("q",1)`；`awaiting is None`；`macro.pending_count == 1`（缺省 / 读后复位） |
| `test_play_empty_register_warns_and_dispatches_nothing` | `flow`；`registers == {}` | `flow.play("a", 1)` | `notes == [("macro register @a is empty", "warn")]`；`calls == []`；`playing is False`、`play_depth == 0`、`last_played is None` |
| `test_rejects_replay_while_playing_direct`（AC4 直接） | `flow`；`registers["a"]=("x",)`；`dispatch` 在第一次被调用时**同步**再次 `flow.play("a",1)` | `flow.play("a",1)` | `notes` 恰含 1 条 `("macro replay already in progress","warn")`；`calls == ["x"]`（未翻倍、无死循环）；最终 `playing is False`、`play_depth == 0` |
| `test_rejects_indirect_self_recursion_via_replay_last`（AC4 间接） | 同上，但嵌套调用改为 `flow.replay_last()`（此时 `last_played` 已置） | `flow.play("a",1)` | 嵌套被拒、`calls == ["x"]`、warn 出现；无递归 |
| `test_replay_last_without_history_warns` | `flow`；`last_played is None` | `flow.replay_last()` | `notes == [("no last macro replay","warn")]`；`calls == []` |
| `test_replay_last_reuses_last_count` | `flow`；`registers["a"]=("x","y")`，先 `play("a",2)` | `flow.replay_last()`（无参 / `None` → 沿用） | `calls == ["x","y","x","y"]`；`last_played == ("a",2)` |
| `test_begin_with_invalid_register_warns_and_clears_awaiting`（异常 / 边界） | `flow`；`awaiting="record"`；分别传 `"A"` / `"ab"` / `"!"` / `""` | 四次 `begin_with` | 每次 `notes` 追加 `("macro register must be one character in a-z0-9","warn")`；`recording is None`、`awaiting is None`；`calls == []` |
| `test_play_invalid_count_warns_and_dispatches_nothing`（边界） | `flow`；`registers["a"]=("x",)`；分别 `count=0 / -1 / MAX_MACRO_KEYS+1` | `flow.play("a", c)` | 每次 warn `"macro count must be a positive integer"`；`calls == []`；`playing is False`、`play_depth == 0` |
| `test_record_raw_enforces_sequence_limit` | `flow`；`monkeypatch` `MAX_MACRO_KEYS` 为 2；录制态 | 依次 `record_raw("x")` / `("y")` / `("z")` | `buffer == ["x","y"]`；第三次产生 warn `"macro sequence limit reached"`；`playing is False` |
| `test_record_raw_skips_macro_control_keys` | `flow`；录制态 | `record_raw("x")` → `record_raw(parse_key(MACRO_RECORD_KEY))` → `record_raw("y")` | `buffer == ["x","y"]`（控制键不进序列） |
| `test_play_resets_playing_after_dispatch_raises`（异常流） | `flow`；`registers["a"]=("x",)`；`dispatch` 抛 `RuntimeError("boom")` | `pytest.raises(RuntimeError)` 包 `flow.play("a",1)` | 异常向上传播；`finally` 后 `playing is False`、`play_depth == 0`、`last_played is None`（未写成功记录） |
| `test_all_rejection_notifications_use_warn_kind` | `flow`；构造 4 类拒绝（空寄存器 / 非法 count / 回放中 / 无上次回放） | 依次触发 | 每条 `notes` 元组的第二项均为 `"warn"`（用户可见提示，AC4/AC5/AC7） |
| `test_request_play_with_count_three_then_begin_with_plays_three`（按键 count 前缀） | `flow`；`registers["q"]=("j",)` | `flow.request_play(3)` → `flow.begin_with("q")` | `calls == ["j","j","j"]`（3 次）；`macro.pending_count == 1`（读后复位）；`last_played == ("q",3)`；`awaiting is None` |
| `test_begin_with_reads_pending_count_directly_and_resets`（dispatch 写入值） | `flow`；`registers["a"]=("x","y")`；直接置 `macro.pending_count=3`、`macro.awaiting="play"` | `flow.begin_with("a")` | `calls == ["x","y"]*3`（6 次）；`macro.pending_count == 1`；`last_played == ("a",3)` |
| `test_replay_last_with_count_three_overrides_last_count`（按键 `3<f12>`） | `flow`；先 `play("a",2)`（`registers["a"]=("x","y")`） | `flow.replay_last(3)` | `calls == ["x","y"]*3`（6 次）；`last_played == ("a",3)` |
| `test_replay_last_with_count_one_falls_back_to_last_played_count`（边界登记） | 同上，先 `play("a",2)` | `flow.replay_last(1)` | 沿用 2 次 → `calls == ["x","y","x","y"]`；`last_played == ("a",2)`（登记 `1<f12>` 并入沿用） |
| `test_play_count_out_of_range_via_pending_count_warns`（越界 / 异常流） | `flow`；`registers["a"]=("x",)`；置 `macro.pending_count = MAX_MACRO_KEYS + 1`、`awaiting="play"` | `flow.begin_with("a")` | `notes` 恰含 `("macro count must be a positive integer","warn")`；`calls == []`；`playing is False`、`play_depth == 0`；`macro.pending_count == 1`（仍复位） |

## 4. 验证方案

- **验证目标**：证明 AC2（精确 N 次 / 重复上次 / **按键 count 前缀经
  `pending_count` 传入 `play` / `replay_last` 覆盖与沿用**）、AC4（拒绝 + warn +
  无死循环）、AC6（同名覆盖 / 隔离）、录制序列上限、控制键排除、异常安全复位、
  `pending_count` 读后复位为 1、非法 / 越界 count 由 `play` 统一 warn；证明
  `MacroFlows` 不违反 R10（每个 raw 恰一次 `dispatch_raw`）、R11/R12、§三.8 命名。
- **需一并回归的既有测试**：`tests/test_architecture.py -q -k "no_banned_identifier_names or callable_aliases or hold_no_app_handle or size_threshold or lazy_percent or debug_prints"`
  （命名 / 回调别名 / 无 App 句柄 / 体量 / 日志 / 禁 print）；
  `tests/test_macro_state.py`（plan-b）、`tests/test_macro_constants.py`（plan-a）。
- **通过判定标准**：pyright 退出码 0 零诊断；pytest 退出码 0、断言全绿；架构守卫
  无违规；新模块 `splitlines()` 行数 < 800（无需豁免）。
- **无法自动化部分**：真实 `ed.handle_raw_key` 的派发效果由 plan-g / plan-k
  端到端覆盖；本计划用假回调只验证编排契约。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pyright yate/flows/macro_flows.py
.venv\Scripts\python.exe -m pytest tests/test_macro_flows.py tests/test_macro_state.py tests/test_macro_constants.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k "no_banned_identifier_names or callable_aliases or hold_no_app_handle or size_threshold or lazy_percent or debug_prints"
```

## 6. 架构边界与守卫

- 触碰层级：L3 新增模块（`_LAYER_RANKS` 第 151 行 `("flows/", 3)` 前缀自动命中，
  **无需改 `_LAYER_RANKS`**）。
- R 条款：R2（无新 Protocol）、R6（无 `TYPE_CHECKING`）、R8（具体对象
  `EditorSession` + `Callable` 回调）、R11（**不** import `editor_components`，
  免 `UI_FROZEN_FILES` 登记）、R12（tracing 惰性日志）、§三.6（函数优先；本模块
  因需持有注入回调而用类，docstring 说明）、§三.8 第 1 条（`macro_flows.py` /
  `MacroFlows` 命名）、§三.7（新模块 < 800 行）。
- 守卫用例：`test_flow_modules_hold_no_app_handle`、
  `test_callable_aliases_use_type_statements`、`test_no_banned_identifier_names`、
  `test_source_files_within_size_threshold`、`test_log_calls_use_lazy_percent_formatting`、
  `test_no_debug_prints_in_library_modules`（**只跑不改**）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 回放递归 / 死循环 | `playing` + `MAX_PLAY_DEPTH=1` + `reject_if_playing` 双保险 + 直接 / 间接自递归用例 | `git checkout -- yate/flows/macro_flows.py tests/test_macro_flows.py` |
| 异常路径 `playing` 未复位导致后续全部被拒 | `try/finally` + `pytest.raises` 复位用例 | 同上 |
| 回调别名写成 `X = Callable[...]` 触发守卫 | 一律 PEP 695 `type` 语句；跑别名守卫 | 同上 |
| 为取派发能力 import `yate.editor` 破 R5 / 成环 | 只经注入的 `dispatch_raw`；import 面限定 `session` / `keys` / `logs` | 同上 |
| 录制序列无界（上一轮 MINOR） | `MAX_MACRO_KEYS` + 专门用例 + monkeypatch 边界 | 同上 |
| `replay_last` / 按键 count 口径与 plan-h 命令不一致（AC7） | §2.2 定死：四命令走 `play(reg,count)`、按键 `<f12>` 走 `replay_last(count)`；N≥2 与无前缀两情形一致 + `test_replay_last_with_count_three_overrides_last_count` | 同上，并回填偏离 |
| `pending_count` 读后未复位泄漏到下一次回放 / 录制键误消耗 count | `begin_with` 读后复位为 1、`toggle_record` 不读写该字段；`test_begin_with_reads_pending_count_directly_and_resets` 与 plan-b 复位用例 | 同上 |
