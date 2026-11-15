# 子计划 a：宏状态与核心逻辑（wave-1，主代理亲改）

> 【历史产物 · 方案已排除】本组文档记录 2026-11-11 第一轮宏录制回放方案
> （`<f6>` 单前缀 chord：`r` 录制 / `p` 回放 / `@` 重复），其实现**未并入**现行代码。
> 现行实现是 2026-11-12 第二轮方案（`<f10>` / `<f11>` / `<f12>` 三单键，
> 见 `../macro-record-replay-unified-progress.md`），键位、API 与命令契约以产品源码为准。
> 本文出现的 `MACRO_PREFIX_KEY`、`pre_dispatch`、`macro_awaiting`、`<f6>` 等符号
> 在现行代码中不存在，**不得**作为开发或施工依据。
> 2026-11-12 合并 `replay` 分支时仅为保留历史轨迹收录本组文档，代码未采纳。

> 唯一规范来源：本文件 + `../overview.md` §二 API 契约 +
> `../macro-record-replay-plan.md` §2/§3/§4。

## 1. 输入

- `yate/session.py:49-64`（`__init__` 字段先例 `self.search` / `self.welcome_visible`）。
- `yate/flows/whichkey_flows.py`（flows 模块形态先例：模块 docstring、
  构造注入、无 editor_components 导入）。
- 调研证据：`editor_dispatch.py:163-181`（回放复用 `handle_raw_key` 契约：
  handled 自动 `refresh_ui` + `completion.after_editor_key`）。

## 2. 独占文件

只改 `yate/session.py`、新建 `yate/flows/macro_flows.py`、新建
`tests/test_macro_flows.py`。

## 3. 具体修改

1. `session.py`：按总纲 §2.1 追加 5 个字段（`#:` 注释英文、ASCII、惰性
   无副作用；不改既有字段与钩子）。
2. `macro_flows.py`（新）：
   - 模块 docstring（英文）：macro registers / recording / replay flow，
     state lives on the session (L1); this module only orchestrates。
   - `type RawKeySink = Callable[[str], bool]`、`type MessageSink =
     Callable[[str], None]`（PEP 695 `type` 语句，回调别名守卫）。
   - `REGISTER_CHARS: frozenset[str]`。
   - `MacroFlows`：构造注入 `session` / `handle_raw_key` / `message`；
     全部公共方法 docstring；按总纲 §2.4 分支规格实现 `pre_dispatch` /
     `toggle_record` / `play` / `repeat_last` / `is_control_key`；
     日志 `log = tracing.get_logger(__name__)`（R12，惰性 % 格式）；
     用户可见提示走 `message` 回调；禁 print；注释全英文 ASCII。
   - `play` 内回放循环用 `list(seq)` 快照（录制覆盖写入不迭代中变导）；
     `finally` 复位 `macro_playing`。
   - 停止录制时序列为空：允许（vim 允许空宏），写 `macro_registers[reg] = []`。

## 4. 测试用例（headless，真 `EditorSession(YateConfig())` + 收集型 sink）

| 用例 | 三要素 |
| --- | --- |
| `test_pre_dispatch_when_record_prefix_then_register_starts_recording` | `pre_dispatch("q")` True + awaiting=="record"；`pre_dispatch("a")` True + recording==("a", []) |
| `test_pre_dispatch_when_record_cancelled_by_non_register_falls_through` | awaiting 后按 `"?"` → warn + False，awaiting 清空 |
| `test_pre_dispatch_while_recording_appends_every_raw_key` | 录制态喂 `"x"`, `"3"`, `"j"` → False 且序列逐个入列 |
| `test_pre_dispatch_when_record_key_while_recording_stops_and_stores` | 录制 `"a"` 序列 `["x","x"]` 后 `pre_dispatch("q")` → True、寄存器覆盖写入、last_register=="a"、recording None |
| `test_pre_dispatch_when_play_prefix_then_register_replays` | 预置寄存器 `a=["x","x"]` + 记录 sink 调用；`pre_dispatch("@")` True、`pre_dispatch("a")` True → sink 收到 ["x","x"]、last_register=="a" |
| `test_pre_dispatch_when_play_prefix_at_repeats_last` | last=="a" 时 `"@"`,`"@"` → 重放 last |
| `test_play_when_already_playing_warns_and_is_ignored` | `macro_playing=True` 直接 `play` → warn、不重放（AC4） |
| `test_play_when_register_empty_warns` | 缺寄存器 → warn、sink 零调用（AC5/AC6） |
| `test_play_when_replay_sequence_contains_control_keys_they_dispatch_plainly` | 序列含 `"@"` → 回放中该 raw 到 sink 而非再触发宏（AC4 无递归） |
| `test_play_runs_sequence_count_times` | count=3 → sink 调用序为 3 遍完整序列（AC2） |
| `test_toggle_record_via_command_path_toggles_and_stops` | `toggle_record("b")` → recording；再 `toggle_record(None)`（录制中）→ 停止 |
| `test_repeat_last_without_last_warns` | 无 last → warn |

## 5. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_macro_flows.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 6. 风险与回滚

状态字段只增不改（既有测试零影响）；`macro_flows.py` 独立新文件可整文件
revert；分支序回归由用例表逐态锁定。
