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
| 【执行】 | 进行中 | wave-1 完成（3/3 执行者落盘、主代理复核全绿、3 笔提交）；wave-2..5 待办，详见 §4 |
| 【审核】 | 待办 | `code-review-expert` 评审 + 门禁五项实测 |
| 【迭代】 | 待办 | blocker / major 归零；minor 登记 |
| 【收尾】 | 待办 | 主代理亲跑全量门禁、回填真实数字、按步提交、更新记忆 |

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
