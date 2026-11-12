# 宏录制与回放（统一键位）任务进度记录 — 2026-11-12 新任务轮

> 来源：Gitee issue IKUOAM，用户 2026-11-12 指令「进入无人值守，无须过问；
> 根据 IKUOAM 描述执行新任务，严格按照纪律执行，唯一例外的是全程使用 Hy4
> 模型，如果模型限流，请切换 GLM-5.3-Flash」。
> 本文件是进度事实的唯一落盘处；每步完成后回填实测数字与偏离记录。

## 0. 环境与纪律核对（【领会】）

| 项 | 事实 |
| --- | --- |
| 必读规则 | `.trae/rules/` 8 份已全文加载（task-orchestration / plan-before-execute / subagent-workflow / architecture-boundaries / python-coding-style / doc-conventions / git-commit-message / misc-rules） |
| 分支基线 | 主工作区 `master` HEAD `be6b4a54`，`git rev-list --left-right --count master...origin/master` = `0 0`（已同步）；`git show master:.trae/rules/task-orchestration.md` 核对为单主干 master 口径 |
| 新 worktree | `yate-macro-record-replay-unified`，分支 `feature/feat-macro-record-replay-unified`，parent `master be6b4a54`；`git worktree list` 已复核 |
| 独立沙箱 | worktree 内 `python -m venv .venv` + `pip install -e ".[dev]"`；自证 `.venv\Scripts\python.exe -c "import yate; print(yate.__file__)"` 输出本 worktree 的 `yate/__init__.py` |
| 主仓未提交改动 | `yate/resources/changelog.{en,zh}.md`（生成器刷新），本轮不触碰、不提交 |
| 分流 | 用户消息含「新任务」关键字 → `task-orchestration.md` §1.2 闭环流程；无人值守【批准】按通过处理（§硬性要求 5），不向用户发起询问或审批 |
| 子代理模型 | 用户指定全程 Hy4，限流回退 GLM-5.3-Flash（本轮唯一例外）。实测：`task` 工具无模型参数，运行时按主工作区 `.trae/agents/<role>.md` frontmatter 解析；`qwen-3.7-plus` / `Hy4 preview` / `qwen-3.8-plus` 均未注册，**有效名 `Hy4`**。三角色 frontmatter 已临时统一为 `Hy4`（收尾还原）；未触发 GLM-5.3-Flash 回退。主仓并发提交 `68c4d781 chore: update subagent model` 曾把方案角色改成 `qwen-3.8-plus` 导致一次 spawn 失败，恢复 `Hy4` 后成功 |
| 既有分支 | `feature/feat-macro-record-replay`（14 提交、未合流未推送）为同一 issue 的上一轮产物，本轮作**只读情报**，不合流、不推送 |

## 1. 步骤状态

| 步骤 | 状态 | 产物 / 提交 / 实测 |
| --- | --- | --- |
| 【领会】 | 完成 | 素材 `macro-record-replay-unified-issue.md`、本进度文件；worktree + venv 自证；提交 `05c180a1` |
| 【方案】 | 完成 | `plan-architect-designer`（Hy4）产出主计划 + 12 份子计划/总纲（13 文档 / 2554 行）；【批准】前审查发现 AC2 count 前缀缺口，二次 spawn 定点修订补齐（`Keymap.take_pending_count()` + dispatch 捕获），13 文档一致性复核通过 |
| 【批准】 | 完成 | 2026-11-12 08:22 无人值守按通过处理，主计划 §11 已回填结论 + D1–D6 偏离；详见该节 |
| 【执行】 | 完成 | wave-1..5 共 11 名执行者全部落盘、零产出 0；5 波主代理复核全绿、D8–D14 全部裁决；详见 §4 |
| 【审核】 | 完成 | `code-review-expert`（Hy4）只读评审 21 笔提交，**APPROVE**：0 BLOCKER / 0 MAJOR / 3 MINOR；记录 `.trae/reviews/2026-11-12-pr-review-feat-macro-record-replay-unified.md`，索引 #76 |
| 【迭代】 | 完成 | 无 blocker / major，按 `task-orchestration.md` §二.6 仅登记 3 条 MINOR 待办；执行阶段已修的 D9 / D11 / D13 三处 MAJOR 全部复核转绿 |
| 【收尾】 | 完成 | 主代理亲跑五道全量门禁全绿（详见 §5）；回填真实数字、按步提交、还原临时模型配置、更新记忆；不 push / 不合流 |

## 2. 待回填

- 方案文档路径、波次划分、独占文件清单、验收命令。
- 每波执行者存活数、零产出成员及名下文件状态、主代理复核命令与退出码。
- 评审轮次、blocker / major / minor 清单与修复提交。
- 收尾七项门禁真实数字（pyright / pytest / 架构 / 覆盖率 / 冒烟 / changelog / diffcheck）。
- 偏离计划项与实测依据；模型可用性与回退处置的实测记录。

## 3. 批准后的文档一致性勘误（进入【执行】前）

- D7：statusbar 测试文件名在方案组内出现两种写法（`test_statusbar_macro.py` 与
  `test_macro_statusbar.py`）。主代理裁定统一为 `tests/test_macro_statusbar.py`
  （子计划 c / plan-f / plan-k 既有口径，且执行者以子计划为唯一规范来源），
  主计划 §6 与 `overview.md` §1.10 / §4 共 4 处同步订正；不改任何设计、键位、
  波次与 API 契约。订正先于 wave-1 下发。

## 4. 执行波次实测（主代理独立复核，非采信执行者自述）

### wave-1：plan-a ∥ plan-b ∥ plan-c（3 并行，Hy4，bypassPermissions）

| 项 | 实测 |
| --- | --- |
| 存活 / 落盘 | 3/3 全部交付；零产出成员 0；各成员只改名下文件（主代理 `git status --short` 复核：3 个 `M` 产品文件 + 3 个 `??` 新测试文件） |
| pyright | `.venv\Scripts\python.exe -m pyright yate/keymaps/keys.py yate/session.py yate/editor_components/statusbar.py` → `0 errors, 0 warnings, 0 informations`，exit 0 |
| 新增测试 | `.venv\Scripts\python.exe -m pytest tests/test_macro_constants.py tests/test_macro_state.py tests/test_macro_statusbar.py -q` → 19 passed（点阵 19），exit 0 |
| 架构守卫 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` → 38 passed，exit 0 |
| 空白检查 | `git diff --check` → exit 0 |
| 提交 | `5edf48c8`（plan-a）、`fb7aab69`（plan-b）、`9a86c37f`（plan-c），三笔按子计划分开 |

**执行者自述验收**（仅作参考，以上主代理复核为准）：plan-a 2 条命令 exit 0；plan-b 3 条 exit 0（首跑 pyright 报 2 个 `reportUnknownVariableType`，最小适配后 0）；plan-c 4 条 exit 0。

**偏离裁定（主代理）**：
- A1（plan-a）生成器局部变量名 `key` 代替契约示意 `k`、行号平移：集合值相同、求值顺序契约实测成立，**接受**（非设计偏离）。
- D1（plan-b）`field(default_factory=dict)` / `list` 改为参数化 `dict[str, tuple[str, ...]]` / `list[str]`：pyright strict 首跑 2 errors → 改后 0 errors 有实测；字段类型契约未变，项目既有 21 处同形态，**接受**（实现细节适配，非契约冲突）。
- C1（plan-c）`used` 表达式补 `+ rec_cells`：窄宽 40 渲染不溢出有探测 + 用例实测，无 label 时 `rec_cells=0` 零影响，**接受**。
- 三成员均未跑计划外全量门禁；全量由 wave-6 / 收尾统一执行（符合剧本）。

### wave-2：plan-d ∥ plan-e（2 并行，Hy4，bypassPermissions）

| 项 | 主代理独立复核实测 |
| --- | --- |
| 存活 / 落盘 | 2/2 全部交付；零产出 0；`git status --short` 6 文件（4 个 `M`：`vim.py` / `vsc.py` / `base.py` / `test_architecture.py`；2 个 `??`：`macro_flows.py` / `test_macro_flows.py`） |
| pyright | `pyright yate/keymaps/vim.py yate/keymaps/vsc.py yate/keymaps/base.py yate/flows/macro_flows.py` → `0 errors, 0 warnings, 0 informations`，exit 0 |
| 新测试 + 架构 | `pytest tests/test_macro_flows.py tests/test_architecture.py -q` → 62 passed（21 flows + 41 架构 = 38 既有 + 3 新增守卫），exit 0 |
| 跨波用例 | `pytest tests/ -q -k "keymap or keys"` → exit 1，失败 `tests/test_vsc_keymap.py:47::test_vsc_bindings_use_registered_actions`（`unknown == []` 多出 3 个宏动作名），与执行者自述一致、稳定复现两次；排除该用例后 `exit 0` |
| AC3 负向演练（主代理补做） | 保留 3 个常量引用的同时临时插入 `_k("<f10>", "macro_probe_literal", ...)` → `pytest tests/test_architecture.py -q -k macro_keys` exit 1，断言 `assert '<f10>' not in literals` 明确失败（`test_architecture.py:1694`）→ 精确还原 → exit 0；`git diff -- yate/keymaps/vsc.py` 中 `f10` / `macro_probe` 残留计数 0 |
| 空白检查 | `git diff --check` → exit 0 |

**执行者自述验收**（仅参考）：plan-d 命令 1/2 exit 0、命令 3 exit 1 后按纪律停下上报（未改断言 / 未改清单外文件）；其负向演练（替换常量为字面量）exit 1 → 还原 exit 0；实测 `VimKeymap().handle_key(..., parse_key(MACRO_RECORD_KEY))` 命中 `macro_record`。plan-e 三条命令全 exit 0（21 新用例、6 守卫）。

**偏离裁定（主代理）**：
- D8（**方案波次缺陷，MAJOR 级流程问题**）：`test_vsc_bindings_use_registered_actions` 在 wave-2 预期红，因 3 个宏动作按 `overview.md` §1.2 归 wave-4 plan-h 注册。裁决：不改既有断言、不改 `actions.py`、不提前注册（保文件互斥与波次）；本波出口判据改用排除版命令；**wave-4 完成后主代理必须复核原 `pytest tests/ -q -k "keymap or keys"` 转绿**，已回填 plan-d §5 与 `overview.md` §3 作为硬条件。此偏离不改变设计 / 键位 / API / 波次顺序。
- D1（plan-d）`VimKeymap.take_pending_count` 补 `@override`：pyright strict `reportImplicitOverride` 首跑 1 error、补后 0 errors 有实测，符合 `python-coding-style.md` §五，**接受**。
- D2–D6（plan-d）import 位置 / 命令前缀 / 守卫 forbidden 含 `<f7>` / 负向断言触发点 / cmd shell 适配：均为形态或环境适配，**接受**。
- E1（plan-e）`tests/conftest.py` 无全局 `config` fixture，测试内定义局部 fixture 返回 `YateConfig()`：与 wave-1 已落盘构造风格一致，不改产品契约，**接受**。
- 两名成员均未跑计划外全量门禁，符合剧本。

### wave-3：plan-f ∥ plan-g（2 并行，Hy4，bypassPermissions）

| 项 | 主代理独立复核实测 |
| --- | --- |
| 存活 / 落盘 | 2/2 全部交付；零产出 0；`git status --short` 10 文件（8 个 `M` + 2 个 `??`），含 plan-f 独占 4 件、plan-g 独占 2 件、D9 补登 1 件、方案修订 3 件 |
| pyright | `pyright yate/editor.py yate/editor_compose.py yate/editor_dispatch.py yate/flows/macro_flows.py` → `0 errors, 0 warnings, 0 informations`，exit 0 |
| 新测试 + 架构 | `pytest tests/test_macro_wiring.py tests/test_macro_dispatch.py tests/test_architecture.py -q` → 68 passed（10 接线 + 17 派发 + 41 架构），exit 0 |
| D9 回归 | `pytest tests/ -q -k "editor or compose"` → 修复前 exit 1（`test_editor_compose_exports_five_factories` 硬编码 5 工厂），主代理按 D9 修改后 **exit 0**（1 skipped） |
| 派发回归 | `pytest tests/ -q -k "dispatch or handle_raw_key or editor_key"` → 56 passed，exit 0 |
| 空白检查 | `git diff --check` → exit 0 |
| D8 状态 | `pytest tests/ -q -k "keymap or keys"` 仍按方案预期红（宏动作归 wave-4 注册），**wave-4 后硬复核**条件不变 |

**执行者自述验收**（仅参考）：plan-f 命令 1/2 exit 0、命令 3 exit 1 后按纪律停下上报；另做单文件 pyright 自检（0/0/0）与负向演练（临时删 `macro_flows: MacroFlows` → pyright `2 errors` → 还原 → `0/0/0`）。plan-g 四条 §5 命令全部 exit 0（38 / 51 / 4 / 1 用例），并实测只读拒绝路径「不记录按键」与 §2.1(B) 裁定相符。

**关键实测**：`editor.py` 改后 `splitlines()` = **807**（基线 800）> 800，§三.7 体量豁免成立；规则文本回填写的是执行阶段实测值（41 个架构用例 / `41 passed` / 对照表 #39-#41），未臆测。`editor_dispatch.py` 卫语句 0 在 `try:` 与 `handle_key` 之前（`:179-183` vs `:198-199`），卫语句 3 在 `except` 之后（`:207-209`），R10 单次派发不变。

**偏离裁定（主代理）**：
- D9（**方案遗漏，MAJOR 级**）：`tests/test_editor_compose.py::test_editor_compose_exports_five_factories` 硬编码「恰好 5 个工厂」，新增第 6 个 `_build_macro_flows` 后确定性冲突，而该文件原不在任何子计划独占清单。执行者按纪律停下上报、未改断言。裁决：**先回填**主计划 §6 S3 / plan-f §1 / `overview.md` §4，**再由主代理亲自**把 expected 集合补为 6 个工厂、同步 `test_editor_imports_factories_from_compose` 的名字列表与两处 docstring，保持「恰好」断言强度不降；实测命令 3 由 exit 1 → exit 0。
- F1–F6（plan-f）：`_build_macro_flows as ...` 显式导入、3 行 ASCII 组装注释、§六 对照表按实测补 3 行（而非措辞「两行」）、无 editor fixture 改用项目既有 `YateApp` 构造、用例 2 用构造前 monkeypatch、额外自检/负向演练 —— 均为形态适配且有实测，**接受**。
- G1（plan-g）子计划中文注释改为等价英文（overview §1 硬契约 + 编码风格）：逻辑未变，**接受**；G2 并行半成品观察：非偏离，**记录**。
- 两名成员均未跑计划外全量门禁，符合剧本。

### wave-4：plan-h ∥ plan-i（2 并行，Hy4，bypassPermissions）

| 项 | 主代理独立复核实测 |
| --- | --- |
| 存活 / 落盘 | 2/2 全部交付；零产出 0；`git status --short` 6 文件（4 个 `M`：`actions.py` / `commands.py` / `which-key.en.md` / `which-key.zh.md`；2 个 `??`：两份新测试） |
| pyright（修复后） | `pyright yate/actions.py yate/commands.py tests/test_macro_commands.py tests/test_macro_whichkey.py` → `0 errors, 0 warnings, 0 informations`，exit 0（**修复前 2 errors**，见 D11） |
| 新测试 + 架构（修复后） | `pytest tests/test_macro_commands.py tests/test_macro_whichkey.py tests/test_architecture.py -q` → 71 passed（22 命令 + 8 which-key + 41 架构），exit 0（**修复前** `test_comments_and_docstrings_stay_ascii` 1 failed） |
| D8 硬复核 | `pytest tests/ -q -k "keymap or keys"` → **308 passed，exit 0**，由 wave-2 的预期红转绿；执行者另重跑一次仍 308 passed。宏动作名与双表逐字一致，未改既有断言 |
| which-key 回归 | `pytest tests/ -q -k "whichkey or which_key"` → 45 passed，exit 0 |
| 冒烟 | plan-i 自述 `123/123 scenarios passed`、`1493/1493 checks`、`unknown_command_and_action PASS`、exit 0；主代理将在 wave-6 独立复跑 |
| 空白检查 | `git diff --check` → exit 0 |

**执行者自述验收**（仅参考）：plan-h §5 四条命令 + D8 命令全 exit 0（43 / 198 / 4 / 308 用例）；plan-i §5 四条命令全 exit 0（8 / 45 用例、冒烟 123/123、架构子集 2），并复核 `guards.py` / `whichkey_flows.py` 零 diff（sha256 与开工前基线 MATCH）、`VscKeymap().lookup("\x1b[17~") is None`。

**偏离裁定（主代理）**：
- D11（**MAJOR，验收命令覆盖不足**）：plan-i §5 只跑架构守卫子集且完全不跑 pyright，漏掉两项——`tests/test_macro_whichkey.py` 导入私有 `_spec_label` / 调用 `flows._sheet_entries()` 触发 `reportPrivateUsage` 2 errors；其注释与 docstring 含 `§` / CJK 触发 `test_comments_and_docstrings_stay_ascii` 失败。主代理独立复核（`pyright` exit 1、`pytest ... test_architecture.py -q` exit 1）发现后**亲改测试文件**：改用公开 `WhichKeyFlows.toggle()` + `panel.show_entries` 取证、本地 raw→label 映射替代私有函数、注释/docstring 全改 ASCII；复跑 pyright `0 errors`、71 passed、45 passed、diffcheck 0 全绿。已在 plan-i §5 **补登 pyright 与全量架构守卫为出口硬条件**，后续 wave 不得再以「无产品源码改动」为由省略。
- D10（plan-h 上报的 AC6 交互疑点）：裁定**不改产品代码**。只读取证：`macro_flows.py:48-60` `toggle_record()` 录制中走 `stop()`（issue 明文「再次触发录制开关即停止」）、`:82-100` `begin_with()` 在 `awaiting is None` 时早返回且 `:96` `registers.pop(reg)` 实现同名覆盖；`commands.py:625-632` 的 `:macro-record` 先 toggle 再 begin_with。故「录制中 `:macro-record b`」= 停止且不开始 b（符合 issue），AC6 同名覆盖由「停止 → 再次 `:macro-record a`」满足。plan-h §3 的 AC6 用例 arrange（「已录制 a 序列」）表述含糊，执行者具体化为「已冻结 a、当前空闲」并有实测依据，**接受**；wave-5 plan-k 的 `test_macro_same_register_overwrite_and_other_register_untouched` 端到端覆盖该语义，并追加「录制中再触发开关即停止」断言（见 wave-5 任务书）。
- H1（plan-h）22 条用例 vs 任务书写「21 条」：以子计划 §3 全表为准，**接受**；H2（AC6 用例 arrange 具体化）并入 D10。
- I1–I5（plan-i）用例口径放宽（description OR action 含 macro、标题配对按数量/编号/主题而非文本全等、全文检查路径、插入位置微调）：均有实测依据且未改产品源码，**接受**；I6 命令 1 首跑红（`numeric prefix` 被 Markdown 软换行拆开）→ 只改本人独占文档后 8 passed，**接受**。
- 遗留：`which-key` 面板与手册的**真实 GUI 视觉验证**未做（两执行者均如实声明），登记为遗留项，收尾汇报列出。

### wave-5：plan-j ∥ plan-k（2 并行，Hy4，bypassPermissions）

| 项 | 主代理独立复核 / 执行者实测 |
| --- | --- |
| 存活 / 落盘 | 2/2 全部交付；零产出 0；`git status --short`：plan-j 3 件（`manual.en.md` / `manual.zh.md` / `test_macro_docs.py`）、plan-k 1 件（`test_macro_integration.py`）、D12 修订 1 件、D13 主代理修复 1 件。可选冒烟场景**零改动** |
| plan-j 自述验收 | `pytest test_macro_docs.py -q` 8 passed、`pytest tests/ -q -k "manual"` 45 passed、`pyright tests/test_macro_docs.py` 0/0/0、`pytest tests/test_architecture.py -q` 41 passed，四条 exit 0；双语各 +31 / +28 行，标题 46/46 配对，F7/F5/TOC 零改动 |
| plan-k 自述验收 | `pytest test_macro_integration.py -q` 17 passed、`pytest tests/test_architecture.py -q` 41 passed、`pyright yate/ tests/ tools/` 0/0/0、`tools.smoke_test run --jobs 4` **123/123 scenarios、1493/1493 checks、exit 0**；`pytest tests/ -q -n auto` **exit 1**（见 D13） |
| 主代理复核 | `pyright yate/ tests/ tools/` → 0/0/0 exit 0；`pytest tests/test_architecture.py -q` → 41 passed exit 0；全量 `pytest tests/ -q -n auto` 修复前 exit 1、修复后 **exit 0**；`git diff --check` exit 0 |
| 空白检查 | `git diff --check` → exit 0 |

**D12（并发冒烟避让）**：plan-j §5 原第 3 条全量冒烟与 plan-k §5 同名命令并发，存在 `subagent-workflow.md` §三.3 与 plan-k §7 已登记的 timing 干扰。主代理裁定 plan-j 本波不跑全量冒烟，改跑 `pyright tests/test_macro_docs.py` + 全量架构守卫（D11 延伸硬条件）；manual modal 场景由 plan-k 全量冒烟与 wave-6 主代理覆盖。plan-j 实测遵守，覆盖不降低。

**D13（阻塞 MAJOR，方案遗漏）**：`pytest tests/ -q -n auto` 确定性失败
`tests/test_action_table.py::test_every_action_runs_and_forwards_only_known_hooks`
（`AttributeError: 'function' object has no attribute 'request_play'`，`yate/actions.py:243`）。
根因：既有守卫的 `_FLOW_NAMESPACES` 未登记 `macro_flows`、`FORWARDED_HOOKS` 缺
3 个 `macro_flows.*` hook，且 `_StubEditor` 无 `session.macro.pending_count`（wave-4
宏动作读取之）。该文件原不在任何子计划独占清单，plan-k 执行者按纪律停下上报、未改它。
主代理裁定：**先回填** plan-h §1 / `overview.md` §4，**再亲自**给守卫补
`macro_flows` 命名空间、3 个 hook 与带类型化 `_StubSession` / `_StubMacroState` 的
真实 `session` 替身（不用豁免注释）。实测 `pytest test_action_table.py -q` 27 passed
exit 0、`pyright tests/test_action_table.py` 0/0/0、全量 `pytest tests/ -q -n auto`
**exit 0**。

**D14（可选冒烟场景未采用）**：plan-k 依 §2.3 明确不采用 `tools/smoke_test/scenarios/macro.py`
与 `__init__.py`，零改动且写明四条理由（可选、AC1–AC7 已由 17 个 pilot 用例覆盖、
避免与 plan-j 并行扩大共享面、波次时间），**接受**；不得声称已改。

**plan-k 偏离裁定（主代理）**：
- K1（AC1 用 `:enew` 复位 A 缓冲区 + 两 app 先切 vim）：不复位则 A = 录制+回放、B = 手动一次，无法逐值相等；有实测，**接受**。
- K2（AC7 B 侧用 `<f10>` 停止而非 `:macro-stop`）：录制态按 f5 会把 `\x1b[15~` 录入宏序列（f5 不属 `MACRO_CONTROL_KEYS`），这是「录什么重放什么」的正确行为；B 仍用 `:macro-record a` 开始、`:macro-play a` 回放，双入口覆盖不变。**不改产品代码，接受**。
- K3（`test_macro_rejects_nested_recording` 语义）：issue N4「录制中跨寄存器嵌套回放」明确暂不做，AC4 只要求回放中拒绝回放；落地为「回放中调用 `macro_record` 被拒绝」符合 AC4。**不改产品代码，接受**，嵌套录制/回放列为遗留候选。
- K4（`3<f12>` 后 `pending_count` 保持 3）：`replay_last()` 不经 `begin_with()` 复位，属 §1.8 契约内；执行者移除计划外断言，**接受**。
- K5（全量套件用例未写成递归 pytest 测试函数）：它是 §5 波出口命令而非用例，**接受**；K6 首轮 pyright 2 errors / 1 failed 自修（`Callable[[], object]` 标注等）有实测，**接受**。

**回填**：主计划 §12 已按执行实测补 8–12 项（F4/F23 时序、F18 零 diff、`manual.*.md` 路径裁决、`editor.py` 807 行、N2 与 GUI 遗留）。

## 5. 收尾门禁（主代理亲跑，2026-11-12 10:5x 本地时间）

| # | 命令 | 实测 | 退出码 |
| --- | --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/` | `0 errors, 0 warnings, 0 informations` | 0 |
| 2 | `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | 点阵至 `[100%]`（`-q` 无汇总行，只认退出码） | 0 |
| 3 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 41 passed | 0 |
| 4 | `.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto` | `TOTAL 20049/1108/6392/582 = 93%`、`Required test coverage of 75.0% reached. Total coverage: 93.01%`、`3758 passed, 10 skipped in 151.37s` | 0 |
| 5 | `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` | `123/123 scenarios passed`、`1493/1493 checks (100%)`、`83.88s total`、`exit 0` | 0 |
| 附 | `git diff --check` | 无输出 | 0 |
| 附 | `.venv\Scripts\python.exe -m tools.changelog check` | `released changelog sections are up to date`；unreleased lag 51 提交为 release 期刷新提示，非失败 | 0 |

批量执行五条命令曾因「长时间无输出」触发工具空闲超时被取消（**非门禁失败**）；
改为逐条运行后全部取得真实输出与退出码。评审者独立复跑同组命令得覆盖率
92.99% / 冒烟 80.00s，差异属负载波动，结论一致。

## 6. 评审结论与遗留

- **评审**：`code-review-expert`（Hy4，bypassPermissions，103 tool uses）只读评审
  `git diff master..HEAD`（21 笔提交 `05c180a1..b1386b38`），结论 **APPROVE**：
  **0 BLOCKER / 0 MAJOR / 3 MINOR**。记录 `.trae/reviews/2026-11-12-pr-review-feat-macro-record-replay-unified.md`，
  索引 `.trae/reviews/README.md` #76。评审者自撤 4 条初版疑点并逐条登记证伪依据。
- **核验**：AC1–AC8 全部满足（含 AC3 负向演练、AC4 双层拒绝、AC2 按键 count 前缀
  与 `:` 双入口）；架构条款逐条对照通过；D1–D14 均有实测依据、无静默改设计；
  D11 / D13 两处主代理修复经复核**未削弱守卫强度**（`test_action_table.py:471` 仍为
  「恰好」集合相等，which-key 仍硬断言 3 个 pinned-sheet label）；双语文档与相对
  路径纪律通过。
- **3 条 MINOR（按 §二.6 登记待办，不改代码）**：
  1. `yate/commands.py:22` / `yate/editor_dispatch.py:22` 新增 L3→L3 连线
     （`from yate.flows.macro_flows import MACRO_REGISTER_CHARS`）未在
     `.trae/rules/architecture-boundaries.md` §一 连线图补登；建议常量下沉 L0
     `keys.py` 或补登连线 + 守卫。同层合法、无循环依赖，不升 MAJOR。
  2. 录制中经 `:` 命令可触发回放，形成 `recording` + `playing` 同时为真并污染录制
     buffer（`editor_dispatch.py:208` / `macro_flows.py:105`）；属 issue N4 明确
     「暂不做」范围，AC4 仍满足、无死循环。
  3. `yate/commands.py:666-667`（`:macro-replay-last` 多参数 usage warn）为新增
     代码但无用例覆盖，建议补一条边界用例。
- **遗留（需人工 / 另行立项）**：① which-key pinned sheet、状态栏 `rec @a`、
  应用内手册渲染的**真实 GUI 视觉验证**未做（无人值守会话无法启动 GUI）；
  ② issue N1（寄存器持久化）/ N2（回放合并单步 undo）/ N3（宏编辑 UI）/
  N4（嵌套录制回放）按 issue「暂不做」保留；③ 同步回放循环；
  ④ changelog unreleased lag 属 release 期统一刷新；⑤ 既有未合流分支
  `feature/feat-macro-record-replay`（14 提交）仍独立存在，本轮未合流、未推送。
- **纪律确认**：全程不 push、不合流、不向用户发起询问或审批（无人值守按通过处理）；
  主仓 `.trae/agents/*.md` 的临时 Hy4 frontmatter 配置在收尾还原；主工作区
  `yate/resources/changelog.{en,zh}.md` 的既有未提交改动全程未触碰。
