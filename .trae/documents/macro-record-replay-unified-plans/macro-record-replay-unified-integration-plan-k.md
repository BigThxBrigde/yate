# 子计划 k：AC1–AC7 端到端集成 + 冒烟新增场景（wave-5）

> 唯一规范来源：`overview.md` §1.10 / §3（波次）+ 主计划
> `../macro-record-replay-unified-plan.md` §3（AC 对照表）/ §6 S5 / §9；
> 本文件自包含。状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：wave-1..4 全部落盘产物；主计划取证 F8/F10/F12/F13/F15/F16/F18；
  `python-coding-style.md` §4.7（时序敏感用例用 `-n 1` 复核）。
- 上游依赖：**wave-4 全部验收通过**（本波是最后一个子计划波，之后 wave-6
  由主代理亲跑全量门禁）。
- 输出：AC1–AC7 端到端用例（真实 Textual pilot 按键）+ 可选冒烟新增场景；
  全量回归与冒烟的波次出口证据。

## 1. 独占文件清单（只改这些）

- `tests/test_macro_integration.py`（新增）
- `tools/smoke_test/scenarios/macro.py`（**可选新增**）
- `tools/smoke_test/scenarios/__init__.py`（**仅当采用可选场景时**，追加登记）

> **不动** 任何 `yate/**` 产品源码、其它 `tests/test_*.py`、
> `tools/smoke_test/scenarios/guards.py`（plan-i 只读复核）、
> `tests/test_architecture.py`（plan-d）。
> 采用可选冒烟场景时，`__init__.py` 的改动仅限追加 `SCENARIOS` 登记行
> （对齐 `scenarios/__init__.py:36,66` 的 `*_WHICHKEY` 形态）。

## 2. 具体修改（文件:行号）

### 2.1 `tests/test_macro_integration.py`（新增）

- `from __future__ import annotations`；沿用 `tools/smoke_test/scenarios/_base.py`
  与 `tests/conftest.py` 的 app / pilot 惯例（`async with app.run_test(size=(100, 30))
  as pilot:` + `await pilot.press(...)` + `await pilot.pause()`，对齐
  `guards.py:157-187` 先例）。
- **键位借用纪律**（F18 / 主计划 §5.2）：宏键只用 `<f10>` / `<f11>` / `<f12>`；
  **不得在任何用例里按 `f6`**（冒烟 `unknown_command_and_action` 借用其
  「无内建绑定」前提）。
- 每个用例用**独立的 app 实例**（避免状态跨用例泄漏），断言落在具体缓冲区
  `app.editor.session.buffer` 的 lines / cursor 与 `app.editor` 的可观测状态，
  **禁止「应正常」类模糊断言**。
- 需要比对「手动执行同序列」时，用第二个独立 app 只按同序列按键，逐行比较。

### 2.2 AC → 用例映射（详见 §3）

| AC | 用例（节选） |
|---|---|
| AC1 | `test_macro_record_stop_play_matches_manual_sequence` |
| AC2 | `test_macro_play_three_times_is_exact`（`:` 命令）、`test_macro_key_prefix_three_play_is_exact`（按键 `3<play>`）、`test_macro_replay_last_repeats_previous_count`、`test_macro_key_prefix_three_replay_last_is_exact`（按键 `3<replay-last>`）、`test_macro_vsc_keymap_has_no_count_state_and_plays_once`（vsc 恒 1） |
| AC3 | `test_macro_keys_resolve_to_same_actions_in_vim_and_vsc` |
| AC4 | `test_macro_replay_during_replay_is_rejected_with_visible_warning` |
| AC5 | `test_macro_statusbar_indicator_shows_then_clears`、`test_macro_empty_register_warns` |
| AC6 | `test_macro_same_register_overwrite_and_other_register_untouched` |
| AC7 | `test_macro_command_and_key_entries_agree`、`test_macro_invalid_register_and_syntax_warn` |
| AC8 | 由 wave-6 全量门禁（本计划跑全量 pytest 作为波出口证据，不写实测数字） |

### 2.3 `tools/smoke_test/scenarios/macro.py`（可选新增）

若采用：一个 `async def _macro_record_replay(tmp: Path) -> ScenarioResult`，
流程：打开临时文件 → `pilot.press("f10")` → `pilot.press("a")` → 输入 `x`/`y`
→ `pilot.press("f10")` 停止 → 记录缓冲区 → `pilot.press("f11")` → `pilot.press("a")`
回放 → `Check` 断言回放后与手动同序列一致；末尾 `snapshot_svg(app, tmp)`。
`SCENARIOS` 列表 + `Scenario("macro_record_replay", _macro_record_replay,
("files", "regression"))`；在 `scenarios/__init__.py` 按既有
`from tools.smoke_test.scenarios.whichkey import SCENARIOS as _WHICHKEY`
（第 36 行）/ `*_WHICHKEY,`（第 66 行）形态追加 `*_MACRO` 登记两行。
**不采用时**：本文件与 `__init__.py` 零改动，须在报告写明「未采用可选场景」及
理由（如波次时间 / 冒烟基线约束），不得假装改了文件。

## 3. 详细测试用例（`tests/test_macro_integration.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_macro_record_stop_play_matches_manual_sequence`（AC1） | 两个独立 app，初始空缓冲区 | A：`<f10>` → `a` → 按 `i` `x` `y` `<esc>` → `<f10>` 停止；再 `<f11>` → `a` 回放。B：直接按 `i` `x` `y` `<esc>` | `A.session.buffer` 的 lines 与 cursor **逐值等于** `B.session.buffer`（具体断言 `lines == [...]` 与 `(row, col) == (...)`）；`A.session.macro.registers["a"]` 长度与录制的 raw 数相等 |
| `test_macro_play_three_times_is_exact`（AC2） | app；录制 `i` `x` `<esc>` 存入 "a" | 经 `:` 命令行执行 `:macro-play a 3` | 缓冲区出现 `x` 三次（断言具体 lines）；`last_played == ("a", 3)`；`playing is False` |
| `test_macro_play_defaults_to_once`（AC2 边界） | 同上 | `<f11>` → `a` | 缓冲区出现 `x` 一次；`last_played == ("a", 1)` |
| `test_macro_replay_last_repeats_previous_count`（AC2） | 先 `:macro-play a 2` | `<f12>` | 缓冲区再增加 2 次序列；`last_played == ("a", 2)` |
| `test_macro_replay_last_with_count_override`（AC2） | 先 `:macro-play a 2` | `:macro-replay-last 3` | 回放 3 次；`last_played == ("a", 3)` |
| `test_macro_keys_resolve_to_same_actions_in_vim_and_vsc`（AC3） | app；分别切到 vim / vsc keymap（用既有 `toggle_keymap` 动作 / `ctrl+/`） | 两套表各 `lookup(parse_key(MACRO_*_KEY))` | 三个键在两套表的 `.action` 分别等于 `macro_record` / `macro_play` / `macro_replay_last`（同 action 名）；按 `<f10>` 在两套表下都产生 `awaiting == "record"` |
| `test_macro_replay_during_replay_is_rejected_with_visible_warning`（AC4） | app；录制一段含 `<f11>` 触发意图的序列（或在 `dispatch_raw` 上挂 monkeypatch 在回放中再触发 `macro_play`） | 触发回放 | 底层消息含 `"macro replay already in progress"` 且 `kind == "warn"`；回放序列只执行一次（缓冲区变化精确）；`playing is False`、`play_depth == 0`；用例在超时上限内结束（无死循环） |
| `test_macro_statusbar_indicator_shows_then_clears`（AC5） | app | `<f10>` → `a`（开始录制）；`<f10>`（停止） | 录制中 `str(status_bar.render())` 含 `rec @a`；停止后不含 `rec @`；两次变化的 fingerprint 均触发重绘（借助 plan-c 用例语义） |
| `test_macro_empty_register_warns`（AC5） | app；未录制 "z" | `<f11>` → `z` 或 `:macro-play z` | 消息含 `"macro register @z is empty"` 且 `kind == "warn"`；缓冲区不变 |
| `test_macro_same_register_overwrite_and_other_register_untouched`（AC6） | app；录 "a" 序列 S1、录 "b" 序列 S2、再录 "a" 序列 S3 | 三次录制 + 分别回放 | `registers["a"]` 等于 S3（覆盖）、`registers["b"]` 等于 S2（不受干扰）；回放 "a" 只产生 S3 的效果 |
| `test_macro_command_and_key_entries_agree`（AC7） | 两个独立 app | A 用 `<f10>`/`a`/序列/`<f10>`；B 用 `:macro-record a` / 同序列 / `:macro-stop` | 两者 `registers["a"]` 的 raw 序列**逐值相等**；回放后缓冲区逐值相等 |
| `test_macro_invalid_register_and_syntax_warn`（AC7 异常流） | app | `:macro-play Z` / `:macro-play` / `:macro-record a b` / `:macro-replay-last abc` | 分别收到 `"macro register must be one character in a-z0-9"` / usage 文案 / usage 文案 / `"macro count must be a positive integer"`（逐字）；每条 `kind == "warn"`；缓冲区不变 |
| `test_macro_rejects_nested_recording`（N4 / AC4 组合） | app；录制态 | 录制中触发 `<f11>` 播放意图 | 被 `reject_if_playing` / dispatch 拒绝分支拦下；warn 可见；无嵌套录制 |
| `test_macro_full_suite_stays_green_under_parallel`（波出口 / 边界） | 全量测试 | `pytest tests/ -q -n auto` | 退出码 0；若出现时序 flake，按 `python-coding-style.md` §4.7 用 `-n 1` 复核并修用例，不得记为「偶发」 |
| `test_macro_key_prefix_three_play_is_exact`（AC2 / 按键 `3<play>`） | app；vim keymap；录制 `i` `x` `<esc>` 存入 "a" | `pilot.press("3")` → `pilot.press("f11")` → `pilot.press("a")` | 缓冲区出现 `x` 三次（具体 lines 断言）；`last_played == ("a", 3)`；`playing is False` |
| `test_macro_key_prefix_three_replay_last_is_exact`（AC2 / 按键 `3<replay-last>`） | app；vim keymap；先 `play("a",2)`（`last_played=("a",2)`） | `pilot.press("3")` → `pilot.press("f12")` | 回放 3 次（缓冲区精确增加 3 次序列）；`last_played == ("a", 3)` |
| `test_macro_vsc_keymap_has_no_count_state_and_plays_once`（AC2 / vsc 恒 1） | 默认 vsc app；录 "a" 序列 `("x",)` | `<f11>` → `a`（vsc 数字键为普通输入、不构成前缀，`take_pending_count()` 恒 1） | 缓冲区出现 `x` 一次；`last_played == ("a", 1)`；随后 `<f12>` 沿用 1 次（再出现一次 `x`） |
| `test_macro_key_prefix_count_out_of_range_warns`（AC2 越界 / 异常流） | app；vim keymap；录 "a" 序列 | 输入超大数字前缀（按 `overview.md` 契约的 `MAX_MACRO_KEYS` 取越界值，执行者按实测常量定）+ `<f11>` + `a` | 消息含 `"macro count must be a positive integer"` 且 `kind == "warn"`；缓冲区不变；`playing is False`、`play_depth == 0` |

## 4. 验证方案

- **验证目标**：以真实按键 / 真实派发链路证明 AC1–AC7 全部满足（**含按键入口
  count 前缀 `3<play>` / `3<replay-last>` 精确 N 次、vsc 恒 1、count 越界 warn**）；
  证明按键入口与 `:` 命令入口在 N≥2 / 无前缀两情形等价（AC2 / AC7）；证明 f6
  冒烟前提未被触碰（本计划用例不按 f6）。
- **需一并回归的既有测试**：`pytest tests/ -q -n auto`（全量）；
  `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4`（全量冒烟）；
  `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/`（全量静态，
  与 wave-6 口径一致）；`tests/test_architecture.py` 全量（含 plan-d 两条新守卫）。
- **通过判定标准**：全量 pytest 退出码 0、断言全绿；全量冒烟退出码 0；
  pyright 退出码 0 零诊断；架构守卫无违规；无任何用例按 `f6`。
- **无法自动化部分（手工 UI 验证步骤）**：
  1. 启动编辑器（默认 vsc），按 `<f10>`，输入 `a`：状态栏出现 `rec @a`。
  2. 输入一段编辑（如 `i` `hello` `<esc>`），再按 `<f10>`：`rec @a` 消失。
  3. 按 `<f11>` 输入 `a`：缓冲区重复出 `hello`；按 `<f12>`：再重复一次。
  4. 切到 vim keymap（`ctrl+/`）重复 1–3，现象一致。
  5. vim 下数字前缀 `3<f11>` 输入 `a` 精确出现 3 次、`3<f12>` 精确 3 次；
     vsc 下 `<f11>` 恒 1 次；`:macro-play a 3` 精确出现 3 次；
     `:macro-play Z` 出现 warn 提示；按键与 `:` 命令双入口结果一致。
  6. 真实终端若 f10/f11/f12 被吞键，记录终端名与现象，按「偏离计划」回填，
     不得静默改键位（键位变更须先修 `overview.md` §1.1 与主计划 §5.2）。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pytest tests/test_macro_integration.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
```

> 本子计划**不写未实测的门禁数字**：以上命令由执行者实际运行，输出与退出码
> 写入报告；wave-6 主代理再按主计划 §6 S6 独立复跑并回填真实数字。

## 6. 架构边界与守卫

- 触碰层级：仅 `tests/` 与（可选）`tools/smoke_test/scenarios/`；**不改产品源码**。
- R 条款：R10（回放每个 raw 只派发一次，由 AC1 用例间接证明）、
  R12（测试代码不引入 devtools 通道）、doc-conventions §五（测试内引用相对路径）、
  misc-rules §四（测试注释 ASCII）、`test_no_machine_local_home_paths_in_sources`
  （测试文件在扫描面内，不写本机家目录路径）。
- 守卫用例：`tests/test_architecture.py` 全量（含 `test_macro_keys_are_shared_and_identical`
  / `test_editor_size_exemption_is_registered`，**只跑不改**）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| Textual pilot 时序 flake（并行下偶发） | `python-coding-style.md` §4.7：用 `-n 1` 复核并修用例，禁止记「偶发」；`await pilot.pause()` 而非真实 sleep | `git checkout -- tests/test_macro_integration.py tools/smoke_test/scenarios/macro.py tools/smoke_test/scenarios/__init__.py` |
| 用例误按 `f6` 破坏冒烟前提 | §2.1 键位借用纪律 + 报告自查；全量冒烟回归 | 同上 |
| 并发跑冒烟互相干扰（subagent-workflow §三.3） | 本波 2 个执行者；冒烟用 `--jobs 4`，出现 timing 失败先重跑确认再下结论 | 同上 |
| 真实终端吞 f10/f11/f12 | §4 手工验证 + 偏离回填；键位变更须先改契约文档 | 同上，键位方案变更须重新走【方案】 |
| vim 数字前缀在真实终端被吞 / 未构成 `count_str`（按键 N 次落空） | 端到端 `3<play>` / `3<replay-last>` 用例 + wave-3 dispatch 在 `handle_key` 之前调 `take_pending_count()` 的时序实测 | 同上，并回填偏离依据 |
| 可选冒烟场景未采用却声称已改 | §2.3 明确「不采用则零改动并写明理由」，只认落盘文件 | 同上 |
| undo 粒度（N2 暂不做）导致 AC1 断言偏差 | 断言落在「缓冲区逐值相等」而非 undo 步数；N2 明确不在范围 | 同上 |
