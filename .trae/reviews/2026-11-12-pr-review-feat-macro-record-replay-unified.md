# PR 评审记录：宏录制与回放（vim/vsc 统一同一套按键与命令）

- 日期：2026-11-12
- 评审人：code-review-expert（Hy4）
- 范围：git diff master..HEAD，21 笔提交（05c180a1..b1386b38），分支 feature/feat-macro-record-replay-unified，parent master be6b4a54
- 工作目录：git worktree yate-macro-record-replay-unified（独立 .venv，Python 3.13.2，import yate 指向本 worktree）
- 性质：只读评审；未修改任何 yate/**、tests/**、.trae/** 被跟踪文件，未 commit / push / 合流；门禁临时结果文件已删除，写报告前 git status --short 干净
- 剧本：.trae/agents/code-review-expert.md（python-code-review skill 加载失败，按剧本第 1 条回退到内置 6 维度 + 三级严重等级框架，不阻塞评审）；规范来源为 .trae/documents/macro-record-replay-unified-{issue,plan,progress}.md、overview.md + 11 子计划、.trae/rules/ 8 份

## 结论

**APPROVE**

- BLOCKER 0 / MAJOR 0 / MINOR 3
- 依据：pyright strict 零诊断、pytest 全绿、架构 41 passed、分支覆盖率 92.99%（≥ 75）、冒烟 123/123 全绿、diffcheck 与 changelog check 均 0；AC1–AC8 全部有落盘代码与测试实证；3 条 MINOR 均为非阻塞的可维护性 / 覆盖完整性 / 范围外遗留，按 task-orchestration.md §二.6 登记待办即可。

## 门禁实测（逐条亲跑，输出与退出码）

| # | 命令 | 实测输出 | exit |
|---|---|---|---|
| 1 | .venv/Scripts/python.exe -m pyright yate/ tests/ tools/ pack/ | 0 errors, 0 warnings, 0 informations | 0 |
| 2 | .venv/Scripts/python.exe -m pytest tests/ -q -n auto | 点阵至 [100%]，10 skipped，无 F/E | 0 |
| 3 | .venv/Scripts/python.exe -m pytest tests/test_architecture.py -q | 41 点 [100%]（41 passed） | 0 |
| 4 | .venv/Scripts/python.exe -m pytest tests -q --cov=yate --cov-branch --cov-report=term-missing:skip-covered --cov-fail-under=75 -n auto | TOTAL 20049/1111/6392/584 = 93%；Required test coverage of 75% reached. Total coverage: 92.99%；79 files skipped due to complete coverage.；EXIT=0 | 0 |
| 5 | .venv/Scripts/python.exe -m tools.smoke_test run --jobs 4 | 123/123 scenarios passed；1493/1493 checks (100%)；80.00s total；exit 0 | 0 |
| 6 | git diff --check | 无输出 | 0 |
| 7 | git diff --check master..HEAD | 无输出 | 0 |
| 8 | .venv/Scripts/python.exe -m tools.changelog check | released changelog sections are up to date；unreleased lag 51 提交提示 | 0 |

说明：
- 命令 4 前两次因工具单次超时被截断（一次经 findstr 管道、一次直接输出到 97% 点阵），未取得有效结论；第三次改为后台运行 + 轮询读回完整结果文件，取到 TOTAL / Required / EXIT=0 后方记为实测。此为工具超时，非测试失败、非 flake。
- 所有门禁一次通过，无并行失败；按 python-coding-style.md §4.7 无需 -n 1 / --jobs 1 复核（无 flake 可复核）。
- 与主代理自述数字交叉核对：pyright 0、pytest 全绿、架构 41、覆盖率 93%（92.99% vs 93.01%）、冒烟 123/123 与 1493 checks 均一致；差异仅冒烟耗时 80.00s vs 83.88s，属正常负载波动。

### 覆盖率未覆盖行（新增 / 修改代码，term-missing:skip-covered 实测）

| 文件 | Cover | Missing |
|---|---|---|
| yate/flows/macro_flows.py | 92% | 65, 86, 116-118, 135, 144 |
| yate/commands.py | 92% | 67-68, 334, 380, 383, 415-419, 425-427, 446-453, 459-466, 491, 527, 545, 549-550, 565, 586-587, 614, 666-667 |
| yate/editor_dispatch.py | 89% | 96->99, 114-115, 144-145, 172-173, 224, 235->exit, 252, 254-259, 271 |
| yate/session.py | 98% | 414, 450->454, 455 |
| yate/editor_components/statusbar.py | 97% | 66->74, 293->295, 299, 303 |
| yate/keymaps/keys.py | 94% | 137-140, 196 |
| yate/keymaps/base.py | 99% | 119 |
| yate/editor.py | 87% | 202, 254 等既有行；新增接线 31-35 / 73-76 / 143-146 / 177-183 全覆盖 |
| yate/actions.py | 97% | 50（既有）；新增 240-248 全覆盖 |
| yate/keymaps/vim.py | 95% | 新增 234-242 / 1275-1279 全覆盖 |
| yate/keymaps/vsc.py、yate/editor_compose.py | 100%（在 79 files skipped 内） | 无 |

- 新增模块 macro_flows.py 未覆盖的 65 / 86 / 135 / 144 均为防御性早返回；116-118 为 play_depth > MAX_PLAY_DEPTH 分支，因 play() 前置 reject_if_playing() 使其不可达（属方案 §5.5(4) 要求的 playing + play_depth 双保险，非缺陷，但无用例能覆盖）。
- commands.py 的 666-667 是本次新增的 :macro-replay-last 多参数 usage warn 分支，无对应用例（见 MINOR-3）。
- 整体覆盖率与主代理基线 93.01% 持平，无明显下降；新增代码除上述防御分支外均有对应测试。

## AC1–AC8 逐条核验

| AC | 结论 | 实证 |
|---|---|---|
| AC1 录制→停止→回放与手动同序列一致 | 满足 | 录制存 raw 键弦（macro_flows.py 的 record_raw / stop 冻结 tuple），回放逐个经 ed.handle_raw_key 重派发；test_macro_integration.py:118 test_macro_record_stop_play_matches_manual_sequence 用 :enew 复位 + 两 app 切 vim 逐值相等（K1 有实测依据） |
| AC2 count 前缀 / : 命令双入口 / 重复上次回放 | 满足 | 3<f11> 与 3<f12> 精确 N（integration:479 / 502、dispatch:274 / 286 / 315）；vsc 恒 1（integration:525、base.py:237、守卫 #41）；:macro-play <reg> [count] 与 :macro-replay-last [count]（commands.py:643 / 663）；1<f12> 沿用上次次数为方案 §5.5(3) / §12(7) 已登记边界，手册 / which-key / 集成用例均覆盖；:macro-replay-last 1 精确 1 次 |
| AC3 双表共享常量 + 漂移守卫（含负向演练） | 满足 | keys.py:61-66 三个 MACRO_*_KEY + MACRO_CONTROL_KEYS（parse_key）；vim.py:234-242 / vsc.py:129-131 仅引用常量；test_architecture.py:1651 test_macro_keys_are_shared_and_identical 为 AST 引用名 + 禁 <f10>/<f11>/<f12>/<f7> 字面量 + 运行时双表 lookup 同 action；负向演练由 progress wave-2 主代理补做（临时插 <f10> 字面量 → 断言失败 → 还原 → 绿，vsc.py 残留计数 0） |
| AC4 回放期拒绝与无死循环 | 满足 | macro_flows.py 的 playing 标志 + reject_if_playing() + editor_dispatch.py Guard 1 双层；integration:266 / 450 断言 warn 文案、playing / play_depth 复位、缓冲区无额外变化；play() try/finally 复位，dispatch 抛异常时复位且异常不被吞（test_macro_flows.py:261） |
| AC5 状态栏 rec @a 与空寄存器 warn | 满足 | statusbar.py 注入 recording_label（缺省 None 保持独立构造）+ fingerprint 含 rec_text；test_macro_statusbar.py 7 条含重绘 / 抛异常降级 / name_budget；空寄存器 warn（macro_flows.py:109、test_macro_commands.py:217） |
| AC6 同名覆盖 / 其它寄存器不干扰 | 满足 | begin_with 在 recording 分支 registers.pop(reg, None)（macro_flows.py:96）；get() 未录制返回 ()；integration:346 端到端；D10 裁定「录制中 :macro-record b = 停止且不开始 b」符合 issue「再次触发录制开关即停止」，未改产品代码 |
| AC7 按键与 : 命令一致、非法输入 warn | 满足 | 3 动作（actions.py:240-248）与 4 命令（commands.py:625-691）共用 MacroFlows；test_macro_commands.py:278 / 313 / 331 双入口一致性；非法寄存器含大写 A / 多字符 / 标点（:122-128）、语法错误、count 非整数 / 0 / 负 / 越界（:192 / 204）全部 warn；9 条文案与 overview.md §1.4 逐字一致 |
| AC8 静态与测试门禁 | 满足 | 见门禁实测表，全部 exit 0，含 3 条新增架构守卫 |

## 架构条款对照（architecture-boundaries.md R1–R15 / §三.7 / §三.8 / §五 自检清单）

- MacroState 落 session.py（L1，UI-free，R4 / §五 状态放对层）：session.py:46-67 为 dataclass，EditorSession.__init__ 挂 self.macro（:92），纯数据 + 只读查询，不 import 上层 / Textual。✓
- MacroFlows 落 flows/macro_flows.py（L3，157 行）：PEP 695 type DispatchRaw / Notify、无 self.app（守卫 #23）、不 import editor_components（免 UI_FROZEN_FILES）；规则 §一 L3 清单 / R11 / §三.8 接入清单三处同步，editor.py 类属性 + _build_macro_flows 工厂（注入 session / dispatch_raw=ed.handle_raw_key / notify=ed.message）+ 组装顺序注释齐全。✓
- statusbar 自持（L2，R13 / R14）：只新增 recording_label: Callable[[], str | None] | None 构造参数，L3 侧仅注入 lambda: ed.session.macro.recording_label()；except Exception 带 noqa: BLE001 + log.exception（python-coding-style.md §4.5，不静默吞异常）。✓
- R10 单次派发：_handle_raw_key 中 Guard 0/1/2 在 try 之前（editor_dispatch.py:180-197）、Guard 3 在 except BufferReadOnlyError 之后（:207-209），handle_key 仅调用一次；test_macro_dispatch.py:214 断言单次派发。✓
- R7 装载：populate / register_commands 登记 3 动作 4 命令，editor.py 不反向 import 内置表（守卫 #10）。✓
- editor.py 807 行豁免两处同步：规则 §三.7 名单（wave-3 实测 807，基线 800）+ tests/test_architecture.py 的 SIZE_EXEMPT_FILES（len 6）+ 守卫 #40 + test_macro_wiring.py:95 / :128。✓
- 无新 Protocol / Any / TYPE_CHECKING / # type: ignore：pyright strict 0 诊断 + 守卫 #3 / #4 / #21 / #22 / #26 全绿；statusbar.py:18 的 Any 为既有 **kwargs 标注，非新增。✓
- 无向上未登记连线：test_no_unregistered_upward_imports（:782-810，仅拦 rank > src_rank，UPWARD_EDGES_FROZEN 为空集）41 passed。新增两条 flows 连线均为 L3→L3 同层，不构成向上违规（详见 MINOR-1）。✓
- §五 自检清单其余项（日志 tracing + 惰性 % 格式、注释 ASCII、无本机路径、无相对导入、命名 *Flows、回调别名 type 语句）均由既有守卫覆盖且全绿。✓

## Findings（按严重程度排序）

### MINOR-1：L3→L3 横向连线未在依赖连线图补登，常量放置层次可下沉
- 位置：yate/commands.py:22、yate/editor_dispatch.py:22
- 证据：两处新增 from yate.flows.macro_flows import MACRO_REGISTER_CHARS；规则文本 diff 仅把 macro_flows.py 补进 §一 L3 清单 / R11 / §三.8，未在 §一 连线图登记 TABLES→FLOWS 边，也未补守卫用例（§一 明文：需要新增合法连线时必须先修订本图并补守卫用例）。方案 §7 架构对照表只声明「无新增向上连线」，未识别该同层连线。
- 根因：MACRO_REGISTER_CHARS（合法寄存器字符集，纯数据）按 overview.md §1.6 定死在 L3 flows 模块，导致 L3 内置表为校验寄存器名反向引用流程模块。
- 不升级为 MAJOR 的理由：同层（rank 3→3）不在 test_no_unregistered_upward_imports 拦截面；R5 明文允许 TABLES→ED 同层且 commands.py:16 既有 from yate.editor import Editor 先例；不违反 R1–R15 任何硬禁线、不形成循环依赖（macro_flows 不 import commands/editor）；实现与批准方案逐字一致，非静默改设计；无运行时行为影响。
- 修复建议：优先把 MACRO_REGISTER_CHARS 下沉到 L0 yate/keymaps/keys.py（或 L1 session.py），commands / dispatch / flows 一律从低层引用，消除 L3 横向耦合；若保留现状，则在 §一 连线图补登 TABLES→FLOWS 并补一条守卫用例锁定该白名单。

### MINOR-2：录制中经 : 命令可触发回放，形成 recording 与 playing 同时为真（N4 范围外遗留）
- 位置：yate/editor_dispatch.py:208（Guard 3 只判 recording，不判 playing）、yate/flows/macro_flows.py:105（reject_if_playing 只判 playing）
- 证据：录制中 macro.playing 为 False，此时执行 :macro-play b 命令 → play() 不被拒绝 → 回放启动；回放期间 recording 仍非 None，Guard 3 把回放的每个非控制 raw 键 record_raw 进当前录制 buffer，污染录制内容。回放中再次触发宏动作 / 控制键仍被双层拒绝（AC4 满足），无死循环。
- 根因：录制与回放是两个独立标志，交叉激活时缺少互斥守卫；方案 §5.5(1) 只排除了宏控制键与 awaiting 寄存器字符，未处理命令行入口触发的录制中回放。
- 不升级理由：issue「暂不做」N4「跨寄存器嵌套录制（录制中调用其它寄存器回放）」明确范围外；progress K3 已登记「嵌套录制/回放列为遗留候选」；AC4 只要求回放中拒绝回放，已满足；不影响 AC1–AC8 常规路径。
- 修复建议：后续迭代在 play() 入口或 Guard 3 增加 recording is None 前置条件（或录制中回放先自动停止录制）；在手册 Limitations 登记该边界。

### MINOR-3：commands.py:666-667 新增防御分支缺对应测试
- 位置：yate/commands.py:665-667（_macro_replay_last 的 len(parts) > 1 → _MACRO_USAGE warn）
- 证据：覆盖率 term-missing 实测 commands.py Missing 含 666-667；test_macro_commands.py 中 :macro-record / :macro-stop / :macro-play 的多参数分支均有专门用例（:115 / :157），唯 :macro-replay-last 的多参数 warn 无用例（22 条测试名中无对应项）。
- 根因：plan-h §3 用例表未列该分支。
- 修复建议：补一条 test_macro_replay_last_command_too_many_args_warns_usage，断言 warn 文案为 _MACRO_USAGE、dispatch 为 0、playing 为 False，保持「恰好」断言强度。

## 强制自我批判（逐条反证 / 误报剔除 / 漏报自查 / 结论登记）

### 误报撤回（初版疑点，经回代码实证后删除）
1. 「_complete_register 的 r != prefix 使非空 prefix 恒空、补全失效」→ **删除**。理由：plan-h §2 伪代码（133-135 行）逐字定死该实现，test_macro_commands.py:224-232 显式断言 completer(空串) 返回全部寄存器且 completer(a) == []，属已批准设计 + 测试固化，非缺陷；报告该疑点即为无实证断言。
2. 「:macro-replay-last 复用寄存器 completer 与 count 参数语义不符」→ **删除**。理由：plan-h §2 第 141-142 行明文规定两命令共用 _complete_register，overview.md §1.3 允许「候选为已录制寄存器名 / 常量提示」；实现与方案一致，非偏离。
3. 「play_depth / MAX_PLAY_DEPTH 分支为不可达死代码」→ **删除（转为覆盖率说明）**。理由：方案 §5.5(4) 与 overview.md §1.6 明确要求 playing + MAX_PLAY_DEPTH 双层防护，属批准设计内的冗余保险；覆盖率 116-118 未覆盖已在上表如实列出并说明原因，不作为 finding。
4. 「D11 / D13 削弱守卫或假绿」→ **证伪，无 finding**。D11（test_macro_whichkey.py）改用公开 WhichKeyFlows.toggle() + panel.show_entries，硬断言 3 个宏 label 在 pinned sheet（labels == set(_MACRO_LABELS)），本地 _MACRO_LABEL_BY_RAW 映射、全 ASCII，不依赖私有实现、不放宽断言；D13 主断言 test_action_table.py:471 仍为 {hook for ...} == FORWARDED_HOOKS 的「恰好」集合相等，新增 3 个 hook 属登记合法动作而非放宽白名单，_StubSession 无 __getattr__ 反而使未登记的 session 字段访问直接 AttributeError，守卫更强。

### 逐条反证（保留项）
- MINOR-1：重新读取 commands.py:22 / editor_dispatch.py:22 / 规则 diff / test_architecture.py:782-810 核对，证据真实；确认守卫只拦 rank > src_rank、R5 有同层先例、方案逐字定死 → 维持 MINOR，不夸大、不漏判。
- MINOR-2：重新读取 editor_dispatch.py:177-217 与 macro_flows.py:105-128 核对交叉激活路径成立；确认 issue N4 / progress K3 范围外登记 → 维持 MINOR（范围外遗留），不升 MAJOR。
- MINOR-3：重新读取 commands.py:663-680 与覆盖率结果核对 666-667 未覆盖且测试清单无对应用例 → 维持 MINOR。

### 漏报自查（6 维度）
- 正确性：AC1–AC7 端到端 + 单测 + 双入口一致性全覆盖，未发现逻辑错误。
- 边界条件：count 0 / 负 / 非整数 / 越界、非法寄存器（大写 / 多字符 / 标点）、空寄存器、无上次回放、awaiting 非法字符取消、录制序列上限、f6 冒烟前提、1<f12> 沿用、casefold（严格小写校验）——均有落盘用例。
- 异常处理：statusbar provider 抛异常降级并记日志、play 派发异常 try/finally 复位且不吞、BufferReadOnlyError 有 readonly_notice，符合 §4.5「errors should never pass silently」。
- 并发安全：宏状态为会话级单线程具体对象，无 worker / 线程共享；playing / play_depth finally 复位；冒烟 --jobs 4 与 pytest -n auto 全绿无 flake。
- 性能：MAX_MACRO_KEYS / count 上限已设；回放为同步循环（最坏 count × keys），属上一轮已登记并由本轮设上限的边界，无 profiler 实证不做预优化指控。
- 类型与测试覆盖：pyright strict 零诊断；新增代码 92–99% 覆盖；两个具体缺口（666-667、116-118）已分别登记为 MINOR-3 与覆盖率说明。
- 结论：无明显遗漏。

### 结论登记
| 编号 | 状态 | 理由 |
|---|---|---|
| MINOR-1 | 确认保留 | 规则 §一 连线登记缺口有实证，同层 / 守卫放行 / 方案一致 → 维持 MINOR |
| MINOR-2 | 确认保留 | N4 范围外遗留，有代码实证，非阻塞 → 维持 MINOR |
| MINOR-3 | 确认保留 | 覆盖率实证缺用例 → 维持 MINOR |
| 疑点 1 | 删除 | 方案 + 测试显式固化，非缺陷 |
| 疑点 2 | 删除 | 方案明文规定，非偏离 |
| 疑点 3 | 删除 | 契约要求的双保险，转覆盖率说明 |
| 疑点 4 | 删除（证伪） | D11 / D13 不削弱守卫、不假绿 |

## 方案偏离 D1–D14 复核

- D1–D6（plan.md §11 批准记录）：均有依据；D5 在【批准】前发现 AC2 count 前缀缺口并退回【方案】定点修订（新增 Keymap.take_pending_count + dispatch 捕获），13 份文档一致性复核先于任何代码改动，体现「方案先行、不静默改设计」。
- D7（statusbar 测试文件名统一 test_macro_statusbar.py）：文档一致性勘误，4 处同步，不改设计 / 键位 / 波次 / API。✓
- D8（跨波动作注册，wave-2 预期红）：progress wave-4 实测 pytest -q -k keymap or keys → 308 passed exit 0 转绿；本次亲跑全量 pytest -n auto 全绿（含 test_vsc_bindings_use_registered_actions）交叉确认，无静默提前注册。✓
- D9（6 工厂断言）：test_editor_compose.py 保持 funcs == expected「恰好」集合断言，名字列表与两处 docstring 同步，强度不降。✓
- D10（AC6 toggle 语义，未改产品）：只读取证 + wave-5 集成用例覆盖，符合 issue「再次触发录制开关即停止」。✓
- D11 / D13（两处主代理修复）：见上，均正确且守卫强度不降；本次全量门禁（pyright / pytest / 架构 / 覆盖率 / 冒烟）全绿为修复有效性背书。✓
- D12（并发冒烟避让）：plan-j 改跑 pyright + 全量架构守卫，全量冒烟由 plan-k 与本次评审覆盖，依据 subagent-workflow.md §三.3，覆盖不降低。✓
- D14（可选冒烟场景未采用且零改动）：git diff --name-status master..HEAD 的 46 文件中无 tools/smoke_test/scenarios/ 任何文件，与「零改动」一致，未声称已改。✓
- 总体：D1–D14 均有实测依据、无静默改设计；偏离集中在测试用例 / 文档同步 / 波次时序，产品行为与批准方案一致。

## 文档纪律

- 双语手册 yate/resources/manual.en.md（+31）/ manual.zh.md（+28）：§3.6 状态栏 rec @a、§5 count 口径、§5.1 / §5.2 键位表各 3 行、§8 宏命令表，同章节同步；which-key.en.md（+27）/ which-key.zh.md（+21）：§2 awaiting 提示面、§4 limitations，同章节同步。test_macro_docs.py 8 条 + test_macro_whichkey.py:186 标题配对断言。✓
- 无本机绝对路径：ripgrep 对 .trae/documents/macro-record-replay-unified* 全 0 命中；手册 / which-key 由 test_macro_docs.py:158 与 test_macro_whichkey.py:259 全文正则扫描（URL 豁免）守卫。✓
- 无「按键回放次数写死为单次」旧限制残留：test_macro_whichkey.py:157-184 断言 fixed one replay / 把按键回放次数写死为单次 不在 §4；manual 新增段落明确写 count 语义与双入口。✓
- 提交信息：21 笔提交全为 type(scope): subject 英文格式（docs(plan) / feat(macro) / test(actions) 等），符合 git-commit-message.md。✓
- 规则文本与守卫两处同步（editor.py 807 行、41 用例、#39-#41）：已核对。✓

## 遗留待办（含 GUI 人工验证）

1. MINOR-1 / MINOR-2 / MINOR-3 三条，按 task-orchestration.md §二.6「仅 minor → 登记待办」处理。
2. 真实 GUI 视觉验证未做：which-key 面板 pinned sheet 中 3 条宏 binding 的显示、状态栏 rec @a 指示、应用内手册渲染（progress §12(12) / wave-4 遗留），无人值守会话无法执行，需人工验证。
3. issue「暂不做」保留项：N1 寄存器持久化、N2 回放合并为单步 undo（v1 跟随自然 undo 粒度）、N3 宏编辑 / 查看 / 寄存器列表 UI、N4 跨寄存器嵌套录制 / 回放（与 MINOR-2 相关）。
4. :macro-play / count 回放为同步循环（上限 MAX_MACRO_KEYS 已设），上一轮登记的「无上限同步阻塞」MINOR 已缓解但未改异步，留待后续评估。
5. tools.changelog check 的 unreleased lag 51 提交为 release 期刷新提示，非本轮失败。

## 评审产物与只读纪律

- 本文件是唯一写入产物；门禁产生的 cov_result.txt / cov_done.txt 临时结果文件已删除，git status --short 除本评审记录文件外为空；未修改任何 yate/** / tests/** / .trae/** 被跟踪文件，未 commit / push / 合流。
