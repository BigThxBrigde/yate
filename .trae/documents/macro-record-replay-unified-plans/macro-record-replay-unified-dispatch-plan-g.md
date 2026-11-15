# 子计划 g：派发链路录制 / awaiting / 回放拒绝挂点（wave-3）

> 唯一规范来源：`overview.md` §1.8 + 主计划
> `../macro-record-replay-unified-plan.md` §5.5(1)(2)(4) / AC1 / AC4 / R10；
> 本文件自包含。状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F8（`_handle_raw_key` 是 raw 唯一收口点）、F7
  （`event_to_raw` 规范化）、F2（`MACRO_CONTROL_KEYS`）、F4（双表 f 键 dispatch）、
  F23（`vim.py:255-264` 的 `_clear_pending()` 会清 `count_str`，故 count 必须在
  `handle_key` 之前捕获；`Keymap.take_pending_count()` 定义在 plan-d 的 `base.py`）、
  `overview.md` §1.8 五条卫语句（含新增卫语句 0）。
- 上游依赖：**wave-2 全部验收通过**（plan-a 常量、plan-b 状态含 `pending_count`、
  plan-d `Keymap.take_pending_count()` 两侧定义、plan-e `MacroFlows` +
  `MACRO_REGISTER_CHARS` 已落盘）。与 plan-f **同波并行**：本计划用 stub / `cast`
  提供 `ed.macro_flows`，**不依赖** plan-f 的真实 `Editor.macro_flows` 属性即可
  独立验收。
- 输出：`_handle_raw_key` 在 `handle_key` 之前对 `MACRO_PLAY_KEY` /
  `MACRO_REPLAY_LAST_KEY` 调 `take_pending_count()` 捕获 count 写入 `pending_count`
  （`macro_record` 不消耗），并挂上录制捕获、awaiting 消费（读 `pending_count`）、
  回放拒绝；派发单测（含 `3<play>` / `3<replay-last>` / vsc 恒 1 / count 越界）。

## 1. 独占文件清单（只改这些）

- `yate/editor_dispatch.py`
- `tests/test_macro_dispatch.py`（新增）

> **不动** `yate/editor.py` / `editor_compose.py`（plan-f）、`yate/actions.py` /
> `commands.py`（plan-h）、`tests/test_architecture.py`（plan-d）。

## 2. 具体修改（文件:行号）

### 2.1 `yate/editor_dispatch.py`

- 顶部内部导入组（**第 17-24 行**）追加（L3→L0 / L3→L3 同层，合法）：

```python
from yate.flows.macro_flows import MACRO_REGISTER_CHARS
from yate.keymaps.keys import (
    MACRO_CONTROL_KEYS,
    MACRO_PLAY_KEY,
    MACRO_REPLAY_LAST_KEY,
    parse_key,
)
```

  并在 import 之后定义模块级常量（供卫语句 0 判断，避免每键重算）：

```python
_MACRO_COUNT_KEYS: frozenset[str] = frozenset({
    parse_key(MACRO_PLAY_KEY),
    parse_key(MACRO_REPLAY_LAST_KEY),
})
```

  - `MACRO_RECORD_KEY`（`<f10>`）**不在** `_MACRO_COUNT_KEYS` → 录制键不消耗 count
    （overview §1.8 卫语句 0）。
  - `macro_flows.py` 只 import `session` / `keys` / `logs`，**不** import
    `editor_dispatch`；文件末 `import yate.editor`（**第 243 行**）防循环形态
    **保持不动** —— 新增 import 不引入环，须在 pyright / 导入自检中确认。
- `_handle_raw_key`（**第 163-181 行**）按 `overview.md` §1.8 插入三段卫语句，
  **既有 `BufferReadOnlyError` / `refresh_ui` / `completion.after_editor_key`
  一行不改**：

**(A) 在 `try:`（第 165 行）之前插入卫语句 0（新增）+ 1 + 2：**

```python
    macro = ed.session.macro
    # 卫语句 0（新增）：在 handle_key 之前捕获按键 count 前缀（AC2）
    if (not macro.playing and macro.awaiting is None
            and raw in _MACRO_COUNT_KEYS):
        macro.pending_count = ed.keymaps.active.take_pending_count()
    # 卫语句 1：回放期拒绝（AC4）
    if raw in MACRO_CONTROL_KEYS and macro.playing:
        ed.message("macro replay already in progress", kind="warn")
        return True
    # 卫语句 2：awaiting 消费寄存器字符
    if macro.awaiting is not None:
        if len(raw) == 1 and raw in MACRO_REGISTER_CHARS:
            ed.macro_flows.begin_with(raw)
        else:
            ed.message(
                "macro register must be one character in a-z0-9", kind="warn"
            )
            macro.awaiting = None
        return True
```

  - 卫语句 0 仅对 `MACRO_PLAY_KEY` / `MACRO_REPLAY_LAST_KEY` 的 raw 生效
    （`_MACRO_COUNT_KEYS`，见 §2.1 导入段）：`MACRO_RECORD_KEY`（`<f10>`）不在集合
    → **不消耗 count**；普通按键也不调 `take_pending_count()` → 不干扰 vim 正常
    数字前缀；`playing` / `awaiting` 分支提前 return，不会误捕获。取值**必须**在
    `handle_key` 之前（F23：`vim.py:255-264` 的 `_clear_pending()` 会清 `count_str`）。
    捕获值写入 `macro.pending_count`，由 `begin_with`（plan-e）读之传给
    `play(reg, count)` 并复位为 1；`<f12>` 动作体读之传给 `replay_last(count)`。
  - 卫语句 1 覆盖「回放期任何 raw 命中宏控制键」的直接拒绝（AC4）；间接自递归
    由 `MacroFlows.reject_if_playing()`（plan-e）守动作入口，双保险。
  - 卫语句 2 统一在派发层消费 awaiting 寄存器字符：**不改 vim / vsc 状态机**，
    保证两套 keymap 行为一致（主计划 §5.5(2)）；`begin_with` 读 `pending_count`
    得到回放次数。非法字符（含 `<esc>` 的 `\x1b`、大写、多字符）warn 并取消
    awaiting，不进入录制、不进 keymap。
  - **回放防护与 R10 单次派发不变**：卫语句 1 `return True` 仍只消费一次，
    `handle_key` 仍只调用一次（见 §2.1(C)）；卫语句 0 不 return、不额外派发。

**(B) 在 `except BufferReadOnlyError:` 块（第 169-173 行）之后、
`if handled:`（第 178 行）之前插入卫语句 3：**

```python
    if macro.recording is not None and raw not in MACRO_CONTROL_KEYS:
        ed.macro_flows.record_raw(raw)
```

  - **位置理由**：放在 `try/except` 之外，使只读缓冲区拒绝路径（第 169-173 行
    `return True` 之前不会执行到这里 —— 裁定见下）与正常路径都按同一规则记录；
    实际 `except` 分支 `return True` 会提前返回，**故只读拒绝的按键不记录**
    （回放时同样被拒绝 → 缓冲区状态一致，AC1 不受影响）。执行者若实测发现需要
    记录只读拒绝键，**停下来上报**，不得静默改顺序。
  - **不依赖 `handled`**：录制所有用户按下的 raw 键（含 keymap 未消费的键），
    回放时逐个经同一路径重派发，未消费键同样未消费 → 与手动执行一致。
  - **排除**：`MACRO_CONTROL_KEYS`（控制键自身不进序列，防自触发递归）与
    awaiting 消费字符（卫语句 2 已 `return True`）。

**(C) 其余不变**：`handled = ed.keymaps.active.handle_key(...)`（第 166-168 行）、
`if handled: ed.refresh_ui()`（第 178-179 行）、`ed.completion.after_editor_key(raw)`
（第 180 行）、`return handled`（第 181 行）。R10：一次按键只派发一次。

- **不改** `_handle_key`（第 40-160 行）、`_execute_action`（第 203-223 行）、
  `_readonly_notice` / `_insert_char` / 鼠标函数 / `__all__`。

### 2.2 `tests/test_macro_dispatch.py`（新增）

- 用 `tests/conftest.py` 既有 editor / app fixture；若 fixture 构造过重，允许用
  `cast("yate.editor.Editor", stub)` 显式窄化的轻量 stub（python-coding-style
  §4.4，禁止 `# type: ignore`）。stub 提供：`session`（真 `EditorSession`）、
  `keymaps.active.handle_key`（记录 + 可控返回 / 抛 `BufferReadOnlyError`）、
  `keymaps.active.take_pending_count`（记录调用次数 + 可控返回 `int`，缺省 1；
  模拟 vsc 恒 1 / vim 数字前缀 N）、
  `macro_flows`（真 `MacroFlows` 或记录 stub）、`message`（记录）、
  `handle_raw_key`（记录，供回放闭环）、`refresh_ui`（计数）、
  `completion.after_editor_key`（计数）、`readonly_notice`（计数）。
- 直接调用模块函数 `_handle_raw_key(ed, raw)`（签名 `ed: yate.editor.Editor`）。
- 用例见 §3。

## 3. 详细测试用例（`tests/test_macro_dispatch.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_handle_raw_key_records_every_raw_while_recording` | `macro.recording="a"`；`handle_key` 返回 True | 依次 `_handle_raw_key(ed, "x")` / `("y")` / `("\x1b")` | `macro.buffer == ["x","y","\x1b"]`；`handle_key` 被调 3 次、参数依次为 `"x","y","\x1b"`；`refresh_ui` 被调 3 次 |
| `test_handle_raw_key_excludes_macro_control_keys_from_recording` | `macro.recording="a"`；`handle_key` 记录 raw 并返回 True | `_handle_raw_key(ed, parse_key(MACRO_RECORD_KEY))`、`parse_key(MACRO_PLAY_KEY)`、`parse_key(MACRO_REPLAY_LAST_KEY)` | `macro.buffer == []`（三个控制键都不进序列）；`handle_key` 被调 3 次（键仍正常派发，未被吞） |
| `test_handle_raw_key_consumes_awaiting_register_without_dispatch` | `macro.awaiting="record"` | `_handle_raw_key(ed, "a")` | 返回 `True`；`macro.recording == "a"`、`awaiting is None`、`buffer == []`；`keymaps.active.handle_key` **0 次**；`after_editor_key` **0 次** |
| `test_handle_raw_key_invalid_awaiting_char_warns_and_cancels` | `macro.awaiting="play"`；分别传 `"!"` / `"A"` / `"ab"` / `"\x1b"` | 四次调用（每次重设 awaiting） | 每次 `message` 收到 `("macro register must be one character in a-z0-9","warn")`；`awaiting is None`、`recording is None`；`handle_key` 全程 0 次 |
| `test_handle_raw_key_rejects_macro_key_while_playing`（AC4） | `macro.playing=True` | `_handle_raw_key(ed, parse_key(MACRO_PLAY_KEY))` | 返回 `True`；`message` 恰含 `("macro replay already in progress","warn")`；`handle_key` 0 次、`refresh_ui` 0 次、`after_editor_key` 0 次 |
| `test_handle_raw_key_not_playing_macro_key_dispatches_normally`（反路径） | `macro.playing=False`、`recording=None`、`awaiting=None` | `_handle_raw_key(ed, parse_key(MACRO_RECORD_KEY))` | `handle_key` 被调 1 次；`message` 无 warn；返回 `handle_key` 的返回值 `True` |
| `test_handle_raw_key_dispatches_each_raw_once`（R10） | 非录制态 | `_handle_raw_key(ed, "x")`，`handle_key` 返回 True | `handle_key` 1 次、`after_editor_key` 1 次、`refresh_ui` 1 次；返回值 `True` |
| `test_handle_raw_key_unhandled_key_skips_refresh_but_feeds_completion`（边界） | 非录制态；`handle_key` 返回 False | `_handle_raw_key(ed, "q")` | 返回 `False`；`refresh_ui` 0 次；`after_editor_key` 1 次；`macro.buffer == []` |
| `test_handle_raw_key_readonly_refusal_consumes_key_and_skips_recording`（异常流） | `macro.recording="a"`；`handle_key` 抛 `BufferReadOnlyError` | `_handle_raw_key(ed, "z")` | 返回 `True`；`readonly_notice` 1 次；`macro.buffer == []`（except 提前返回）；`refresh_ui` 按既有第 221-222 行语义（若 stub 走 `_readonly_notice` 则按实际计数） |
| `test_handle_raw_key_play_via_begin_with_dispatches_sequence`（小闭环） | `macro.awaiting="play"`；`registers["a"]=("x","y")`；`macro_flows` 为真对象且 `dispatch_raw=ed.handle_raw_key` | `_handle_raw_key(ed, "a")` | `ed.handle_raw_key` 被回调 2 次、参数 `["x","y"]`；`macro.playing is False`、`play_depth == 0`、`last_played == ("a",1)`；`awaiting is None` |
| `test_handle_raw_key_awaiting_char_is_not_recorded_when_recording`（边界组合） | `macro.recording="a"`、`awaiting="play"`（异常组合，验证优先级） | `_handle_raw_key(ed, "b")` | awaiting 分支优先：字符不进 `buffer`；`handle_key` 0 次；`recording` 保持 `"a"`（不破坏录制态） |
| `test_handle_raw_key_captures_count_three_for_macro_play_key`（按键 count 前缀） | `macro` 初始态；`take_pending_count` 返回 3 | `_handle_raw_key(ed, parse_key(MACRO_PLAY_KEY))` | `take_pending_count` 1 次；`macro.pending_count == 3`；`handle_key` 1 次（R10 单次派发） |
| `test_handle_raw_key_captures_count_three_for_replay_last_key`（`3<replay-last>` 捕获） | 同上，`take_pending_count` 返回 3 | `_handle_raw_key(ed, parse_key(MACRO_REPLAY_LAST_KEY))` | `take_pending_count` 1 次；`macro.pending_count == 3`（交 `replay_last(count)`）；`handle_key` 1 次 |
| `test_handle_raw_key_macro_record_key_does_not_consume_count` | `take_pending_count` 记录调用 | `_handle_raw_key(ed, parse_key(MACRO_RECORD_KEY))` | `take_pending_count` **0 次**；`macro.pending_count == 1`；`handle_key` 1 次 |
| `test_handle_raw_key_vsc_take_pending_count_is_one`（vsc 恒 1） | `take_pending_count` 返回 1（模拟 vsc 继承缺省） | `_handle_raw_key(ed, parse_key(MACRO_PLAY_KEY))` | `macro.pending_count == 1`；`take_pending_count` 1 次 |
| `test_handle_raw_key_three_play_then_register_plays_three_times`（`3<play>` 闭环） | `registers["a"]=("x","y")`；`take_pending_count` 返回 3；`macro_flows` 真对象 `dispatch_raw=ed.handle_raw_key` | 先 `_handle_raw_key(ed, parse_key(MACRO_PLAY_KEY))`（进 awaiting），再 `_handle_raw_key(ed, "a")` | `ed.handle_raw_key` 被回调 6 次、参数 `["x","y"]*3`；`macro.pending_count == 1`（读后复位）；`last_played == ("a",3)`；`playing is False`、`play_depth == 0` |
| `test_handle_raw_key_count_out_of_range_warns_and_dispatches_nothing`（越界 / 异常流） | `take_pending_count` 返回 `MAX_MACRO_KEYS + 1`；`registers["a"]=("x",)`；`macro_flows` 真对象 | 先 `_handle_raw_key(ed, parse_key(MACRO_PLAY_KEY))`，再 `_handle_raw_key(ed, "a")` | `message` 恰含 `("macro count must be a positive integer","warn")`；`ed.handle_raw_key` 回调 0 次；`playing is False`、`play_depth == 0` |

## 4. 验证方案

- **验证目标**：证明录制捕获「录什么重放什么」、awaiting 链统一在派发层（双表
  行为一致）、AC4 拒绝、AC1 回放一致性、**按键 count 前缀在 `handle_key` 之前
  被 `take_pending_count()` 捕获并写入 `pending_count`（`3<play>` 精确 3 次、
  `3<replay-last>` 捕获到 3、vsc 恒 1、`<f10>` 不消耗、越界 warn）**、R10 单次
  派发、`event_to_raw` 之后的 raw 形态不被改写。
- **需一并回归的既有测试**：`pytest tests/ -q -k "dispatch or handle_raw_key or editor_key"`；
  `tests/test_architecture.py -q -k "import_upward or ui_free or hold_no_app_handle"`
  （新 import 为 L3→L0 / L3→L3，无向上连线）；`tests/test_macro_flows.py`（plan-e）。
- **通过判定标准**：pyright 退出码 0 零诊断；pytest 退出码 0、断言全绿；架构守卫
  无违规；`_handle_key` / `_execute_action` 等既有路径零回归。
- **实测项（不可凭假设）**：卫语句 3 相对 `except` 的位置（只读拒绝是否被记录）
  须按 §2.1(B) 实测并在报告登记；与裁定不符须上报而非静默改。
- **无法自动化部分**：真实终端 raw 键序列（尤其 `<esc>` / f 键）由 wave-5 冒烟 /
  人工复核。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pyright yate/editor_dispatch.py
.venv\Scripts\python.exe -m pytest tests/test_macro_dispatch.py tests/test_macro_flows.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -k "dispatch or handle_raw_key or editor_key"
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k "import_upward or ui_free or hold_no_app_handle"
```

## 6. 架构边界与守卫

- 触碰层级：L3（`editor_dispatch.py`，`_LAYER_RANKS` 第 147 行）；新增 import
  `yate.keymaps.keys`（L0）/ `yate.flows.macro_flows`（L3 同层）均为向下或同层。
- R 条款：R10（一次按键只派发一次；卫语句 0 不 return、不额外派发，卫语句 1/2
  提前 `return True` 均只消费一次）、R4（`keys.py` / `session.py` 保持 UI-free）、
  R5（不 import 内置表）、R8 / §四（`take_pending_count()` 经 `ed.keymaps.active`
  具体对象调用，不新增协议 / `Any` / `TYPE_CHECKING`）、
  R12（新代码不新增日志则无违规；若加日志须 tracing 惰性 `%`）、
  §五「按键分支只消费自己真正处理的键」（卫语句 0 仅对 play / replay-last 两键
  捕获 count，awaiting / 拒绝分支只处理宏相关 raw，其余 fall-through）。
- 守卫用例：`test_no_unregistered_upward_imports`、`test_keymaps_services_and_models_stay_ui_free`、
  `test_flow_modules_hold_no_app_handle`（**只跑不改**；新增守卫归 plan-d）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| awaiting 吞掉普通输入 / 双表行为不一致 | 统一在 `_handle_raw_key` 消费、非法即取消并 warn + 组合边界用例 | `git checkout -- yate/editor_dispatch.py tests/test_macro_dispatch.py` |
| 录制录到宏控制键导致回放自递归 | 卫语句 1 + 卫语句 3 排除 + `MacroFlows.record_raw` 双保险 | 同上 |
| 卫语句位置破坏 `BufferReadOnlyError` / `refresh_ui` / completion 既有语义 | §2.1 明确既有行不改 + 只读取证 + 异常流 / 边界用例 | 同上 |
| 新 import 触发循环导入或层秩违规 | `macro_flows` 不 import dispatch；保持文件末 `import yate.editor`；跑层秩守卫 | 同上 |
| pyright 对 stub `ed` 报类型诊断 | `cast()` 显式窄化或沿用既有 editor fixture；禁止 `# type: ignore` | 同上 |
| `take_pending_count()` 在 `handle_key` 之后才调用 → `_clear_pending()` 已清 `count_str`，count 恒 1（AC2 落空） | 卫语句 0 明确在 `handle_key` 之前；F23 取证 + `test_handle_raw_key_captures_count_three_for_macro_play_key` + wave-3 实测时序 | `git checkout -- yate/editor_dispatch.py tests/test_macro_dispatch.py`，回填偏离 |
