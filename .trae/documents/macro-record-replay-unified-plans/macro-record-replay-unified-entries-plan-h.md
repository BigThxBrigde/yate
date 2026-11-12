# 子计划 h：动作表与 `:` 命令入口（wave-4）

> 唯一规范来源：`overview.md` §1.2 / §1.3 / §1.4 / §1.6 + 主计划
> `../macro-record-replay-unified-plan.md` §3（AC7 / AC2）/ F12 / F13 / F14；
> 本文件自包含。状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F12（`populate` 闭包注册形态）、F13（`register_commands` /
  `editor.message(kind="warn")` 报错先例）、F14（`CommandFunc = Callable[[str], object]`）、
  F7（按键入口经 `event_to_raw` → `handle_raw_key` → keymap action）。
- 上游依赖：**wave-3 全部验收通过**（`Editor.macro_flows` 契约由 plan-f 落盘，
  派发挂点由 plan-g 落盘）。
- 输出：3 个内置动作 + 4 个 `:macro-*` 命令（含参数解析与逐字 warn 文案），
  按键入口与 `:` 命令入口行为一致（AC7），**含 count 口径一致**：按键动作体读
  `pending_count`（plan-g 捕获）传 `MacroFlows`，四命令处理器代码零改动。

## 1. 独占文件清单（只改这些）

- `yate/actions.py`
- `yate/commands.py`
- `tests/test_macro_commands.py`（新增）

> **不动** `yate/editor.py`（plan-f）、`yate/editor_dispatch.py`（plan-g）、
> `yate/keymaps/*`（plan-d）、`tests/test_architecture.py`（plan-d）、
> `yate/docs/which-key.*.md`（plan-i）。

## 2. 具体修改（文件:行号）

### 2.1 `yate/actions.py::populate`（第 26-240 行）

在 view 动作区（**第 209-238 行**，`toggle_whichkey` / `toggle_keymap` 一带）追加
3 行，形态与既有 `reg(name, lambda ctx: editor.xxx(), desc)` 一致（闭包捕获
`editor`，R7）：

```python
    reg("macro_record", lambda ctx: editor.macro_flows.toggle_record(),
        "Toggle macro recording")
    reg("macro_play",
        lambda ctx: editor.macro_flows.request_play(
            editor.session.macro.pending_count),
        "Play a recorded macro")
    reg("macro_replay_last",
        lambda ctx: editor.macro_flows.replay_last(
            editor.session.macro.pending_count),
        "Repeat the last macro replay")
```

- 动作名**必须与 plan-d 双表登记的 3 个动作名逐字一致**（`overview.md` §1.2）。
- `ctx` 未使用不得改写签名（既有 lambda 形态）；pyright strict 对未使用 lambda
  参数不报诊断，须实测。
- **不**在 `actions.py` 里实现任何宏逻辑（编排全在 `MacroFlows`，plan-e）。
- `macro_record` 不带参数（`<f10>` 不消耗 count）；`macro_play` / `macro_replay_last`
  两个动作体读 `editor.session.macro.pending_count`（由 plan-g 卫语句 0 在
  `handle_key` 之前调 `take_pending_count()` 捕获写入）并传参，使按键入口支持
  count 前缀（AC2 / AC7）。**四命令处理器（§2.2）代码零改动**——命令直接给
  `MacroFlows.play(reg, count)` 传参，与按键入口在 N≥2 / 无前缀两情形结果一致。

### 2.2 `yate/commands.py::register_commands`（第 260-617 行）

在文件末尾追加 `# ---- macros` 分组（放在最后一个既有 `reg(...)` 之后、`log.info`
若有则之前），定义 4 个处理器 + 1 个补全器，处理器签名一律
`def _xxx(args: str) -> None`：

```python
    def _macro_record(args: str) -> None:
        parts = args.split()
        if len(parts) > 1:
            editor.message("<usage 文案>", kind="warn")
            return
        editor.macro_flows.toggle_record()          # 置 awaiting="record"（或在录制中停止）
        if parts:
            editor.macro_flows.begin_with(_strip_quotes(parts[0]))

    def _macro_stop(args: str) -> None:
        if args.strip():
            editor.message("<usage 文案>", kind="warn")
            return
        if editor.session.macro.recording is None:
            editor.message("not recording a macro", kind="warn")
            return
        editor.macro_flows.stop()

    def _macro_play(args: str) -> None:
        parts = args.split()
        if not parts or len(parts) > 2:
            editor.message("<usage 文案>", kind="warn")
            return
        reg_name = _strip_quotes(parts[0])
        if len(reg_name) != 1 or reg_name not in MACRO_REGISTER_CHARS:
            editor.message("macro register must be one character in a-z0-9",
                           kind="warn")
            return
        count = 1
        if len(parts) == 2:
            try:
                count = int(parts[1])
            except ValueError:
                editor.message("macro count must be a positive integer",
                               kind="warn")
                return
        editor.macro_flows.play(reg_name, count)   # 复用编排的校验与防护

    def _macro_replay_last(args: str) -> None:
        parts = args.split()
        if len(parts) > 1:
            editor.message("<usage 文案>", kind="warn")
            return
        last = editor.session.macro.last_played
        if last is None:
            editor.message("no last macro replay", kind="warn")
            return
        count = last[1]
        if parts:
            try:
                count = int(parts[0])
            except ValueError:
                editor.message("macro count must be a positive integer",
                               kind="warn")
                return
        editor.macro_flows.play(last[0], count)     # §2.3 口径：命令走 play()

    def _complete_register(prefix: str) -> list[str]:
        return [r for r in editor.session.macro.registers
                if r.startswith(prefix) and r != prefix]

    reg("macro-record", _macro_record, "start/stop macro recording")
    reg("macro-stop", _macro_stop, "stop macro recording")
    reg("macro-play", _macro_play, "play a macro register [count]",
        arg_completer=_complete_register)
    reg("macro-replay-last", _macro_replay_last, "repeat the last replay [count]",
        arg_completer=_complete_register)
```

- `<usage 文案>` 处**逐字**使用 `overview.md` §1.4 的
  `"usage: :macro-record [reg] | :macro-stop | :macro-play <reg> [count] | :macro-replay-last [count]"`。
- 所有 warn 文案逐字取 `overview.md` §1.4，**不得自创**。
- `MACRO_REGISTER_CHARS` 从 `yate.flows.macro_flows` 导入（plan-e 契约常量，
  L3→L3 同层合法）；`_strip_quotes` 用文件内既有辅助（第 270 行先例）。
- `int(parts[1])` 的 `<= 0` / 越界由 `MacroFlows.play` 的 `count < 1 or
  count > MAX_MACRO_KEYS` 校验并 warn（**不在这里重复实现**，避免文案漂移）；
  非整数由本层 `except ValueError` 兜住（python-coding-style §4.5：捕获具体异常、
  不静默吞、给 warn）。
- **不改**任何既有命令 / 处理器 / `log.info` 计数行。

### 2.3 `:macro-replay-last` 的 count 口径（定死）

命令走 `editor.macro_flows.play(last[0], count)`（`MacroFlows.play` 已含校验、
防护、`last_played` 写入）；**不**调用 `replay_last()`（后者仅供 `<f12>` 按键动作，
由动作体读 `pending_count` 传 `replay_last(count)`：`count >= 2` 覆盖、None / 1
沿用 `last_played`）。依据：`macro-record-replay-unified-flows-plan-e.md` §2.2 裁定。
**四命令契约（§1.3 / §1.4）本轮不变**：`:macro-play <reg> [count]` /
`:macro-replay-last [count]` 仍按原参数解析与 warn 文案；仅新增「按键入口与 `:` 命令
入口 count 口径一致」的说明与用例（AC7），不改任何命令处理器代码。

### 2.4 `tests/test_macro_commands.py`（新增）

- 用 `CommandRegistry()` + `register_commands(registry, editor)` 得到注册表；
  经 `registry.get(name).func(args)` 调用（`CommandFunc` 契约）；`editor` 用既有
  `tests/conftest.py` 的 editor / app fixture 或 `cast` 的 stub（禁止
  `# type: ignore`）。
- 动作一致性用 `ActionRegistry()` + `populate(registry, editor)` 后
  `registry.execute("macro_record", ActionContext(ed.session, ed.key_ui))` 验证。

## 3. 详细测试用例（`tests/test_macro_commands.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_macro_record_command_with_valid_register_starts_recording` | 空 `macro` | `func("a")` | `macro.recording == "a"`、`awaiting is None`、`registers == {}`、`recording_label() == "rec @a"` |
| `test_macro_record_command_without_register_enters_awaiting` | 空 `macro` | `func("")` | `macro.awaiting == "record"`、`recording is None` |
| `test_macro_record_command_too_many_args_warns_usage` | 空 `macro` | `func("a b")` | `message` 恰含 `(usage 文案, "warn")`；`awaiting is None` |
| `test_macro_record_command_invalid_register_warns`（异常 / 边界） | `awaiting="record"` 前置由命令自身产生 | `func("A")` / `func("ab")` / `func("!")` / `func("1a")` | 每次 warn `"macro register must be one character in a-z0-9"`；`recording is None`；`awaiting is None` |
| `test_macro_record_command_restarts_when_already_recording`（AC6） | 已录制 "a" 序列 `["x"]` | `func("b")` | `registers["a"] == ("x",)`（旧内容冻结）；`recording == "b"`；`buffer == []` |
| `test_macro_stop_command_freezes_sequence_and_warns_when_idle` | 录制态 `recording="a"`、`buffer=["x","y"]`；再置空闲 | 第一次 `func("")`；第二次 `func("")` | 第一次 `registers["a"] == ("x","y")`、`recording is None`；第二次 warn `"not recording a macro"` |
| `test_macro_stop_command_rejects_extra_args`（边界） | 空 | `func("x")` | warn usage 文案；`macro` 状态不变 |
| `test_macro_play_command_plays_exact_count`（AC2） | `registers["a"] = ("x","y")` | `func("a 3")` | `dispatch_raw` 调用序列 `["x","y"]*3`；`last_played == ("a",3)`；`playing is False` |
| `test_macro_play_command_defaults_count_to_one` | `registers["q"] = ("j",)` | `func("q")` | 派发 `["j"]`；`last_played == ("q",1)` |
| `test_macro_play_command_missing_register_warns_usage` | 空 | `func("")` | warn usage 文案；0 次派发 |
| `test_macro_play_command_non_integer_count_warns`（异常流） | `registers["a"]=("x",)` | `func("a abc")` / `func("a 1.5")` | 每次 warn `"macro count must be a positive integer"`；0 次派发 |
| `test_macro_play_command_non_positive_count_warns_via_flow`（边界） | `registers["a"]=("x",)` | `func("a 0")` / `func("a -1")` | warn `"macro count must be a positive integer"` 由 `MacroFlows.play` 发出；0 次派发；`playing is False` |
| `test_macro_play_command_empty_register_warns`（AC5） | `registers == {}` | `func("z")` | warn `"macro register @z is empty"`；0 次派发 |
| `test_macro_play_command_arg_completer_returns_recorded_names` | `registers = {"a": ("x",), "b": ("y",)}` | `registry.get("macro-play").arg_completer("")` | 返回 `["a","b"]`（排序按既有注册表语义，断言集合相等）；`arg_completer("a") == []` |
| `test_macro_replay_last_command_reuses_last_count` | 先 `play("a",2)`（`registers["a"]=("x","y")`） | `func("")` | 派发 `["x","y","x","y"]`；`last_played == ("a",2)` |
| `test_macro_replay_last_command_overrides_count`（AC2） | 先 `play("a",2)` | `func("3")` | 派发 `["x","y"]*3`；`last_played == ("a",3)` |
| `test_macro_replay_last_command_without_history_warns` | `last_played is None` | `func("")` | warn `"no last macro replay"`；0 次派发 |
| `test_macro_commands_and_actions_are_registered_with_exact_names` | 两个注册表 populate / register_commands 后 | 读 `names()` | 动作表含 `macro_record` / `macro_play` / `macro_replay_last`；命令表含 4 个 `:macro-*` 名；每个 `describe()` / `description` 非空 |
| `test_key_and_command_entries_produce_identical_state`（AC7） | 两个独立 editor 实例 | 实例 A 经 `ActionRegistry.execute("macro_record", ctx)`；实例 B 经 `:macro-record`（无参） | 两者 `macro.awaiting == "record"`、`recording is None`（行为一致）；再各 `begin_with("a")` 后 `recording == "a"` |
| `test_all_command_warnings_use_warn_kind`（异常汇总） | 逐条触发 8 类拒绝 | 收集所有 `message` 调用 | 每条 `(text, "warn")`，`kind` 恒为 `"warn"` |
| `test_key_and_command_entries_agree_on_count_prefix`（AC7 / count 双入口） | 两个独立 editor 实例，均录 "a" 序列 `("x","y")`；A 置 `A.session.macro.pending_count = 3` 后触发 `macro_play` 动作再 `begin_with("a")`；B 执行 `:macro-play a 3` | 分别断言 `dispatch_raw` 序列与 `last_played` | A 与 B 都等于 `["x","y"]*3`；两者 `last_played == ("a",3)`、`playing is False`（N≥2 情形双入口一致） |
| `test_key_and_command_entries_agree_on_replay_last_count`（AC7 / `3<replay-last>`） | 两个独立 editor，均先 `play("a",2)`；A 置 `pending_count = 3` 触发 `macro_replay_last` 动作；B 执行 `:macro-replay-last 3` | 分别断言回放次数 | A（`replay_last(3)`）与 B（`play("a",3)`）都回放 3 次、`last_played == ("a",3)`；无前缀 / vsc 恒 1 时两者都沿用 2 次 |

## 4. 验证方案

- **验证目标**：证明 AC7（按键 / `:` 命令双入口一致、**含 count 口径一致**、
  非法输入明确报错）、AC2（count / 重复上次 / 按键 `3<play>` / `3<replay-last>`）、
  AC5/AC6 的提示与覆盖、R7（外壳装载内置表）、文案逐字一致（不漂移）、
  四命令处理器契约不变（只加说明与用例）。
- **需一并回归的既有测试**：`pytest tests/ -q -k "command or actions or registry"`；
  `tests/test_architecture.py -q -k "shell_loads or import_action_tables or lazy_percent or banned_identifier"`；
  `tests/test_macro_flows.py`（plan-e）。
- **通过判定标准**：pyright 退出码 0 零诊断（特别验证 lambda 未使用 `ctx`、
  `arg_completer` 签名、`Notify` 兼容）；pytest 退出码 0、断言全绿；架构守卫
  无违规。
- **无法自动化部分**：真实 `:` 命令行输入与 tab 补全交互由 wave-5 冒烟 / 人工验证。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pyright yate/actions.py yate/commands.py
.venv\Scripts\python.exe -m pytest tests/test_macro_commands.py tests/test_macro_flows.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -k "command or actions or registry"
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k "shell_loads or import_action_tables or lazy_percent or banned_identifier"
```

## 6. 架构边界与守卫

- 触碰层级：L3（`actions.py` / `commands.py`，`_LAYER_RANKS` 第 148-149 行）。
- R 条款：R5（表可 import `editor`，本计划只在闭包用 `editor`，不新增反向边）、
  R7（`YateApp.__init__` 的 `populate` / `register_commands` 装载，本计划不改 app.py）、
  R12（新增代码不记日志则无违规）、§四（跨层只用具体对象 / 既有回调）。
- 守卫用例：`test_shell_loads_the_builtin_tables`、
  `test_editor_does_not_import_action_tables`、`test_no_banned_identifier_names`、
  `test_log_calls_use_lazy_percent_formatting`（**只跑不改**；新增守卫归 plan-d）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 动作名与 plan-d 双表登记不一致 → 按键落空 | 逐字按 `overview.md` §1.2；用例校验两侧名字集合 | `git checkout -- yate/actions.py yate/commands.py tests/test_macro_commands.py` |
| warn 文案自创导致 AC7 判定漂移 | 逐字取 §1.4；用例断言精确字符串 | 同上 |
| count 校验在命令层与 `MacroFlows` 重复实现、口径分叉 | §2.2 定死：非整数本层兜、数值范围交 `play()`；`replay_last` 走 `play()` | 同上 |
| `:macro-record a` 依赖 `begin_with` 需 `awaiting` 前置 | §2.2 先 `toggle_record()` 再 `begin_with()`；用例覆盖 | 同上 |
| `int()` 解析引入裸 except / 静默吞异常 | 只 `except ValueError` + warn（§4.5） | 同上 |
| 按键动作体读 `pending_count` 传参与命令直接传 count 口径分叉（AC7） | §2.1 / §2.3 定死四命令处理器零改动、按键走 `pending_count`；`test_key_and_command_entries_agree_on_count_prefix` 双入口断言 | `git checkout -- yate/actions.py yate/commands.py tests/test_macro_commands.py` |
