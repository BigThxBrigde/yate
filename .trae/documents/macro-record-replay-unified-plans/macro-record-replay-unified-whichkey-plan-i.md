# 子计划 i：which-key 提示面双语登记 + 冒烟键位借用复核（wave-4）

> 唯一规范来源：`overview.md` §1.9（**不改 `whichkey_flows.py` 代码**的裁定）、
> §1.10 + 主计划 `../macro-record-replay-unified-plan.md` §8 / F16 / F18 / F19 / F20；
> 本文件自包含。状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F16（`_sheet_entries()` 遍历全部 binding，新宏 binding 自动进
  pinned sheet；`_candidates` 只处理 printable 前缀）、F18（`guards.py` 的
  `<f6>`「无内建绑定」前提）、F20（`yate/docs/which-key.en.md` 章节）、
  `overview.md` §1.9 裁定。
- 上游依赖：**wave-3 全部验收通过**（plan-d 的 3 条宏 binding 已落盘，
  `VscKeymap()` / `VimKeymap()` 可查）。
- 输出：which-key 双语文档登记宏 awaiting 提示面与限制；`guards.py` f6 前提
  复核（**本轮零改动**）；提示面自动收录与冒烟前提的回归测试。

> **裁定（重要）**：`WhichKeyFlows.__init__`（`yate/flows/whichkey_flows.py:58-66`）
> 只有 6 个既有注入、无 `session` / `editor`，其构造点又在 plan-f 独占文件里；
> 若给 awaiting 提示加注入会造成 wave-3 → wave-4 的依赖倒置（wave-3 验收时
> `WhichKeyFlows` 尚不接受新参数）。故**不改 `whichkey_flows.py` 代码**：
> 「新键位提示」由 `_sheet_entries()`（第 189-195 行）自动收录 3 条 binding，
> awaiting 寄存器提示面由本计划的双语文档登记。`UI_FROZEN_FILES` / R11 导入面
> 零改动。该裁定在 `overview.md` §1.9 与主计划 §5.1 已同步。

## 1. 独占文件清单（只改这些）

- `yate/docs/which-key.en.md`
- `yate/docs/which-key.zh.md`
- `tests/test_macro_whichkey.py`（新增）

> **只读复核、不改**：`tools/smoke_test/scenarios/guards.py`、
> `yate/flows/whichkey_flows.py`。**不动** `yate/actions.py` / `commands.py`
> （plan-h）、`yate/resources/manual.*.md`（plan-j）、`tests/test_architecture.py`
> （plan-d）。

## 2. 具体修改（文件:行号）

### 2.1 `yate/docs/which-key.en.md`

- `## 2. Keymap differences`（**第 35-63 行**）：在现有 register wait 描述段
  （第 48-52 行，已有 "the register wait shows a single `a-z` row"）之后追加一个
  小段落，登记宏 awaiting 提示面（英文）：

```
Macro recording / replay adds three shared function-key bindings (`F10`
record toggle, `F11` play, `F12` repeat last replay).  Pressing `F10` or
`F11` waits for one register name in `a-z0-9`; the pinned sheet lists all
three keys with their descriptions, and the register wait is documented
here because the pending register is session-level state, not a printable
keymap chord.  Function keys never continue a printable prefix (they are
raw-byte specs), so they appear only in the pinned sheet.  In vim a numeric
prefix before `F11` / `F12` (for example `3F11`) sets the replay count, with
N defaulting to one; vsc has no count state machine and always uses one.
The `:` commands `:macro-play <reg> [count]` and `:macro-replay-last [count]`
are the equivalent entry points.
```

- `## 4. Limitations`（**第 101 行**起）追加两条：
  - f 键不参与 printable 前缀（`_candidates` 第 144-148 行依据）；
  - 回放次数（count）口径：vim 数字前缀 `N<回放键>` 回放 N 次（N 缺省 1），
    vsc 无 count 状态机、`take_pending_count()` 恒 1（按 `<f11>` 回放 1 次、
    `<f12>` 沿用上次次数）；`:macro-play <reg> [count]` /
    `:macro-replay-last [count]` 命令参数提供等价双入口；`1<f12>` 并入「沿用」为
    已登记边界（主计划 §5.5(3) / overview §1.8）。
- 不改 `## 1. Overview` / `## 3. Conflict checking` 的既有内容。

### 2.2 `yate/docs/which-key.zh.md`

按 `doc-conventions.md` §三「两份文件必须同时新增、同时更新」：在**相同章节**
（`## 2` 与 `## 4`）加入与 §2.1 逐条对应的中文说明（键位 `F10` / `F11` / `F12`、
寄存器 `a-z0-9`、pinned sheet、vim 数字前缀 N 次 / vsc 恒 1 / `:` 命令双入口 /
`1<f12>` 沿用边界的 count 口径）。章节标题数量与顺序与英文版保持一致
（由 §3 用例断言）。

### 2.3 `tools/smoke_test/scenarios/guards.py`（**只读复核，不改**）

- 复核 F18：`_F6_RAW: str = "\x1b[17~"`（第 66 行）与第 150-155 行
  「`<f6>` has no built-in binding」前提仍在；第 185-186 行 `binding_not_leaked`
  断言仍成立。
- 本轮宏键选 `<f10>` / `<f11>` / `<f12>`（主计划 §5.2），**不占 `<f6>`**，
  故 `guards.py` 零改动；复核结论写入报告（含 `VscKeymap().lookup(_F6_RAW)
  is None` 的实测）。若实测与裁定不符，停下来上报，不得改冒烟场景而不回填。

### 2.4 `tests/test_macro_whichkey.py`（新增）

`from __future__ import annotations`；用 `VscKeymap` / `VimKeymap`、
`yate.flows.whichkey_flows.WhichKeyFlows`（或仅 `_sheet_entries` 的等价构造）
与 `Path` 读文档；用例见 §3。

## 3. 详细测试用例（`tests/test_macro_whichkey.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_whichkey_pinned_sheet_includes_all_three_macro_bindings` | 构造 `VscKeymap()` / `VimKeymap()`；用既有 `WhichKeyFlows` fixture 或等价取 `_sheet_entries()` | 收集两份 binding 表的 `_spec_label(...)` 结果 | 每份都含 `<f10>` / `<f11>` / `<f12>` 三个 label；对应 description 分别含 `"macro"`（大小写不敏感）；两份表的三个 label 集合**相等**（AC3 的面板侧证据） |
| `test_whichkey_macro_descriptions_name_the_actions` | 同上 | 取 3 条 binding 的 description | 分别含 `record` / `play` / `repeat`（或 `last`），且 vsc 与 vim 两侧同名（统一键位） |
| `test_whichkey_docs_register_macro_awaiting_hint_in_both_languages` | 无 | 读两份 md 的 `## 2` 段 | 两份都含 `F10` / `F11` / `F12` 与 `a-z0-9`（英文含 `register`，中文含「寄存器」）；均提到 pinned sheet |
| `test_whichkey_docs_document_count_and_fkey_limitations` | 无 | 读两份 md 的 `## 4` 段 | 两份都含「vim 数字前缀 N 次 / numeric prefix N」「vsc 恒 1 / always one」「`:macro-play` / `:macro-replay-last` 命令双入口」与「f 键不参与 printable 前缀」的对应表述（英文 / 中文各自断言关键词）；**不含**「把按键回放次数写死为单次 / fixed one replay」类旧限制 |
| `test_whichkey_en_zh_section_headings_stay_paired`（doc-conventions §三） | 无 | 正则取两份 md 的 `^## ` 标题列表 | 两个列表**完全相等**（数量与顺序），且都含 `## 2` / `## 4` 对应标题 |
| `test_guards_f6_premise_not_broken_by_macro_keys`（F18 复核） | 无 | 读 `guards.py`；构造全新 `VscKeymap()` 查 f6 | 文本含 `_F6_RAW: str = "\x1b[17~"` 与 `"<f6>` has no built-in binding"；`VscKeymap().lookup("\x1b[17~") is None`；`VimKeymap().lookup("\x1b[17~") is None`（f6 未被宏占用，冒烟前提成立） |
| `test_whichkey_flows_source_is_unchanged_by_macro_work`（边界 / 裁定证据） | 无 | 读 `yate/flows/whichkey_flows.py` 源码 | 不含 `macro_awaiting` / `session.macro` 等新增注入标识；`__init__` 参数名集合仍为既有 6 个（防止执行者私自加注入破坏波间顺序） |
| `test_whichkey_docs_contain_no_machine_local_paths`（异常 / doc-conventions §五） | 无 | 对两份 md 新增段落做逐行匹配 | 不含盘符 / 用户目录 / POSIX 家目录三类本机绝对路径形态（按 `doc-conventions.md` §五 的口径）；仓库内引用均为相对路径 |

## 4. 验证方案

- **验证目标**：证明 issue「which-key 面板如有前缀提示面，需同步登记新键位提示」
  以「pinned sheet 自动收录 + 双语文档登记」满足；证明 **count 口径（vim 数字前缀
  N 次 / vsc 恒 1 / `:` 双入口）双语同步且无「把按键回放次数写死为单次」旧限制残留**；
  证明 F18 的 f6 冒烟前提未被宏键位破坏（本轮 `guards.py` 零改动）；证明双语同步
  （doc-conventions §三）。
- **需一并回归的既有测试**：`pytest tests/ -q -k "whichkey or which_key"`；
  `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4`（全量冒烟，确认
  `unknown_command_and_action` 仍绿）；`tests/test_architecture.py -q -k
  "collaborators_keep_widget_coupling_frozen or no_unregistered_upward_imports"`
  （R11 导入面未变）。
- **通过判定标准**：pytest 退出码 0、断言全绿；冒烟退出码 0 且
  `unknown_command_and_action` 场景通过；架构守卫无违规；`guards.py` 与
  `whichkey_flows.py` 零 diff（复核结论须写入报告）。
- **无法自动化部分**：真实 which-key 面板（`<f9>` 切 pinned sheet）下三个宏键提示
  的视觉呈现，人工验证：启动编辑器 → `<f9>` 展开面板 → 肉眼确认 `F10` / `F11` /
  `F12` 三行及描述；按 `<f10>` 后确认消息 / 手册所述 awaiting 语义。记录在报告。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pytest tests/test_macro_whichkey.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -k "whichkey or which_key"
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k "collaborators_keep_widget_coupling_frozen or no_unregistered_upward_imports"
```

（本子计划无产品源码改动，故不单独跑 pyright；wave-6 全量门禁统一覆盖。）

## 6. 架构边界与守卫

- 触碰层级：文档（`yate/docs/`）+ 测试；**不改任何 `yate/**` 产品源码**
  （`whichkey_flows.py` / `guards.py` 只读复核）。
- R 条款：R11（`UI_FROZEN_FILES` 不变）、`UPWARD_EDGES_FROZEN` 保持空集、
  doc-conventions §三（双语同步）/ §五（相对路径、无本机真实路径）、
  misc-rules §四（代码注释 ASCII；本计划新增的是 md 文档，不受该守卫扫描面）。
- 守卫用例：`test_collaborators_keep_widget_coupling_frozen`、
  `test_no_unregistered_upward_imports`（**只跑不改**；新增守卫归 plan-d）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 双语只改一侧 / 章节不对齐 | §2.1/§2.2 同章节 + `test_whichkey_en_zh_section_headings_stay_paired` | `git checkout -- yate/docs/which-key.en.md yate/docs/which-key.zh.md tests/test_macro_whichkey.py` |
| 执行者私自给 `WhichKeyFlows` 加注入造成波间红测 | §0 裁定 + `test_whichkey_flows_source_is_unchanged_by_macro_work` | 同上（并回填偏离） |
| 宏键误占 f6 打破冒烟前提 | §2.3 只读复核 + `test_guards_f6_premise_not_broken_by_macro_keys` + 全量冒烟 | 若不符，停下来上报主代理；`guards.py` 改动须按「偏离计划」回填实测依据 |
| 文档写本机绝对路径 | doc-conventions §五 + 专门用例 | 同上 |
