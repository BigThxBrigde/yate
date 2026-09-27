# P2 Nice-to-have 修复计划

> 来源：[review.md](../../issues/review.md) 2026-09-16 审查 Nice-to-have 段（2026-09-23 复核后
> 仍存在的条目）。均为锦上添花，不阻塞发布；随手清理即可，无独立排期。
> **实施状态（2026-09-25）：29 条全部落账——波次一 14 条 + 波次二 12 条（表中 ✅），
> 决策门三项已拍板：N18 选①已落地（✅），N8 挂起备注（⏸），
> N30 已于 2026-09-26 按重构方案落地（✅，见下）。**
>
> **2026-09-24 状态复核**：原 N1–N17 逐条对照当前代码核实，**全部仍存在**（行号已按
> 现状修正）；另将 review.md 2026-09-23 / 2026-09-24 各审查段仍未修复的低影响条目
> 补入为 **N18–N31**。已修复条目（如 e2e git 测试缺失）见 review.md 对应 [x] 标注。
> 编号 N9 / N11 / N12 为登记时的跳号（无对应条目），非遗漏。
>
> 统一门槛同 [P0](P0_critical_fixes_plan.md)（pyright 零诊断、pytest 全绿、
> **冒烟 `python -m tools.smoke_test run --fail-only` 全绿**——每批收尾必跑；
> 纯注释 / 纯文档条目也不例外，随批验证）。

| # | 条目 | 位置 | 策略 | 测试 |
|---|---|---|---|---|
| N1 ✅ | 保存始终 LF，忽略原始/平台换行 | [document.py:50-61](../../../yate/editor_core/document.py) | 打开时记录原始主导 EOL（crlf/lf/cr），保存按其写回；默认保持 LF。仅对已存在文件生效，新文件一律 LF | crlf 文件往返 round-trip 断言 EOL 不变 |
| N2 ✅ | config tokenizer 重叠 token | [regex_backend.py:651-677](../../../yate/editor_syntax/regex_backend.py) | 各 `finditer` 独立发射；改为按 start 排序后对重叠区间取先到者（或合并为一次交替扫描） | `"true1"` / 字符串内数字用例断言不双着色 |
| N3 ✅ | 缺符号时报错无上下文 | [ts_backend/languages.py:249-255](../../../yate/editor_syntax/ts_backend/languages.py) | `getattr(dll, symbol)` 包 try，`raise RuntimeError(f"{library_path} lacks entry point {symbol!r} ...") from e`（`_FAILED` 缓存已防重复） | monkeypatch 假 dll 缺符号，断言错误消息含路径与符号名 |
| N4 ✅ | `_to_char` 字节偏移边界缺注释 | [ts_backend/backend.py:127-133](../../../yate/editor_syntax/ts_backend/backend.py) | 纯注释补充：说明 UTF-8 多字节中间偏移经 `errors="ignore"` 丢弃后续字节、映射到字符首列的行为 | 无（注释） |
| N5 ✅ | Outdent 按 tab_width 而非上一个 tab stop | [buffer.py:510-535](../../../yate/editor_core/buffer.py) | 空格行改算 `rrem = removed % tab_width`，`removed - (rrem or tab_width)` 对齐上一个 stop；整 Tab 剥离保留 | 3 空格缩进 + tab_width=4 → 移除 3；8 空格 → 移除 4 |
| N6 ✅ | `replace_current` 可用 `replace_range` 简化 | [search.py:102-116](../../../yate/editor_core/search.py) | 内部改调 `replace_range(buffer, match_span, replacement)`，删重复实现 | 现有 replace 用例全绿 |
| N7 ✅ | `_soft_reset`（ESC c）不退备用屏幕 | [emulator.py:387-397](../../../yate/editor_term/emulator.py) | 加 `self._exit_alt_screen()`（或等价状态复位），对齐 xterm RIS 部分语义 | 写入 `ESC c` 后断言 alt_screen 为 False |
| N8 ✅ | ctrl+digit 用 kitty CSI-u | [base.py:118-121](../../../yate/keymaps/base.py) | **已落地（2026-09-26）**：保留 kitty 绑定 + 双语文档标注终端要求与替代路径；`ctrl+/` 同族命名漂移问题已随 [keybinding-fix-wt](../keybinding-fix-wt/README.md) 修复 | 255 定向 / 1228 全量 passed，pyright 0 |
| N10 ✅ | `cycle_tab` 空操作循环 | [editor.py:489-493](../../../yate/editor.py) | 单 tab 时 no-op 且不提示（或保留提示但仅 verbose）；倾向静默 no-op | 单 tab 连按断言无消息、无异常 |
| N13 ✅ | smoke 工具自身无测试 | [tools/smoke_test/](../../../tools/smoke_test/) | 对纯函数部分（场景解析、报告渲染、`extract_svg_rows`）补 `tests/test_smoke_tool.py`；harness 端到端不测（冒烟本身即验证） | 新测试文件 |
| N14 ✅ | SVG 提取正则依赖 Textual 版本 | [harness.py:130](../../../tools/smoke_test/harness.py) | 提取失败时给明确报错并打印 SVG 头部片段（诊断版本漂移）；正则收紧为当前实测格式并在注释记录适配的 Textual 版本 | 喂旧版/新版 SVG 样例断言行为 |
| N15 ✅ | 单场景执行无整体超时 | [tools/smoke_test/](../../../tools/smoke_test/) | harness 用 `asyncio.wait_for(scenario, timeout=per_scenario)`（默认 60s，`--timeout` 可调），超时记 failed 并继续 | 人造挂起场景断言超时生效 |
| N16 ✅ | `check_commit_pushed` 仅支持 gitee | [gitee.py:62-72](../../../tools/changelog/gitee.py) | 其它 host 返回 `None` 时由调用方输出「无法核验，跳过 gate」而非当失败；github 可用 `api.github.com` 同构实现 | 单测 host 分派 |
| N17 ✅ | `strip_unreleased` 边界未测 | [render.py:89-108](../../../tools/changelog/render.py) | 补用例：仅有 Unreleased 段、Unreleased 为空、Unreleased 在末尾三种 | 新增 3 条单测 |
| N18 ✅ | action `quit` 注册后 UI 不可达（注册冗余，Low） | [vsc.py:87](../../../yate/keymaps/vsc.py) | 三选一：① `YateApp.action_quit` 改调 `editor.execute_action("quit")`；② 面板保留同名 action；③ 删冗余 vsc `<ctrl+q>` 绑定。倾向 ①（保留面板去重语义） | 冒烟 `quit_action_dispatch` 已覆盖可达性 |
| N19 ✅ | 终端面板获焦后无法用按键回焦编辑器 | [terminal.py:193-204](../../../yate/editor_view/terminal.py) | `TOGGLE_KEYS` 之外放行 `ctrl+1`（`focus_editor`）；`Esc` 先确认 shell 是否依赖再定 | 冒烟断言终端获焦时 `ctrl+1` 回焦编辑区 |
| N20 ✅ | visual 模式 `gg` 永不跳转（死代码） | [vim.py:240-245](../../../yate/keymaps/vim.py) | `pending` 恒空且 `"g"` ∈ motion 表，第二分支不可达；删除死分支或修正条件使其可达 | visual 下 `gg` 跳转用例（若决定支持） |
| N21 ✅ | `if key == "o": pass` 死代码 | [vim.py:372-373](../../../yate/keymaps/vim.py) | 删除 | 现有 vim 用例全绿 |
| N22 ✅ | `score += 0  # consecutive: best` 死语句 | [palette.py:58-59](../../../yate/editor_view/palette.py) | 删除 | 现有 palette 用例全绿 |
| N23 ✅ | `add_binding` 覆盖 `_index` 但旧 binding 残留（help 双条目） | [keymaps/base.py:229-240](../../../yate/keymaps/base.py) | 覆盖时从 `bindings` 列表移除同 raw key 旧条目 | 同 key 重复 `add_binding` 后断言 modals 帮助只展示一条 |
| N24 ✅ | `PromptBar.on_cancel` 落入 Textual `on_*` 反射命名空间 | [commandline.py:213](../../../yate/editor_view/commandline.py) | 实例属性改名 `cancel_hook`（当前无冲突消息，纯命名隐患） | 现有 prompt 用例全绿 |
| N25 ✅ | 两个无关类型同名 `Action` | [base.py:160](../../../yate/keymaps/base.py) / [registries.py:26](../../../yate/registries.py) | callable 别名改 `ActionFunc`，扩展作者不易混淆 | pyright 全绿 + 扩展文档同步 |
| N26 ✅ | `handle_key` docstring「every check is pure」不实 | [editor.py:529-535](../../../yate/editor.py) | 修正表述（`try_window_prefix` 变更 `_window_pending`、popup 分支执行 `accept_completion`） | 无（注释） |
| N27 ✅ | 内部导入组非字母序 | [extensions.py:49-53](../../../yate/services/extensions.py) | 排序 | 无 |
| N28 ✅ | trust.py 全用 `Path \| None` | [trust.py:27,50,71](../../../yate/services/trust.py) | 统一 `Optional[X]`（与 explorer 条目同类，可合并修） | pyright 全绿 |
| N29 ✅ | harness 重写行沿用 `# type: ignore` 无理由注释 | [harness.py:274-283](../../../tools/smoke_test/harness.py) | 补理由注释归档豁免（工具代码，若属既定豁免） | 无（注释） |
| N30 ✅ | L0 config 惰性 import L2 `editor_view.theme`（层级债） | [config.py](../../../yate/config.py) | **已落地（2026-09-26）**：注入回调方案——`load_config` 增 keyword-only `register_theme` / `load_theme_paths`（PEP 695 别名），L4 `cli.py` 注入同名函数；缺省 `None` 即 headless。`config.py` 收编 `UI_FREE_FILES`（负向验证过）；R4 / §四交互表 / §六 已登记。方案比选与实测：[theme-layer-refactor-plans](../theme-layer-refactor-plans/README.md) | 架构测试 13 passed + pyright 全仓 0 ✅ |
| N31 ✅ | `warn()` 在 `sys.stderr` 为 None 时退化写 stdout | [logs.py:85-87](../../../yate/logs.py) | `if sys.stderr is not None:` 再 print——stderr 不可用时静默丢弃，与 docstring「Never raises」一致 | monkeypatch `sys.stderr = None` 断言不抛且不写 stdout |
| N32 ✅ | subject 字段可能包含嵌入的分隔符（理论性 Low） | tools/changelog/gitdata.py | body 经 maxsplit 保留杂散分隔符，subject 字段本身无防护；按实现固化行为或加断言/文档说明（2026-09-25 复核补入——review.md 2026-09-16 Suggestion 段唯一漏登记条目） | 现有 changelog 测试全绿 |

## 实施状态与剩余处理方式（2026-09-25 波次二收尾后更新）

- **波次一已完成 14 条（表中 ✅）**：N1–N7（SP1/SP2/SP3）、N13–N17 + N29 + N32（SP4）。
- **波次二已完成 12 条（表中 ✅）**：N20/N21/N23/N25（SP5）、N10/N19/N22/N24/N26（SP6）、
  N27/N28/N31（SP7）。门禁实测（两波收尾各跑一轮，数字相同）：pyright 全仓 0 诊断；
  pytest 全量全绿（7 个既有 POSIX skip）；冒烟 **87/87 场景 · 907/907 checks · exit 0**
  （收尾批补入 `terminal_focus_editor` 后为 88/88 · 917/917，见下）。
  逐条证据见 [review.md](../../issues/review.md) 对应条目的 ✅ 注记。
- **N1 行为变更待用户人工确认**：CRLF 文件保存后保留 CRLF（不再强制 LF）——请在真实
  CRLF 文件上编辑保存一次确认；不满意可低成本回退（`Document.eol` 单点）。
- **波次二校准**：N10 锚点为 `session.docs`（计划写 `tabs`，实际属性名 `docs`），既有用例
  `test_cycle_tab_with_one_tab_warns` 按新行为改写为静默 no-op 守卫；N19 冒烟场景未新增
  （`tools/smoke_test/scenarios/` 不在 SP6 独占域），pilot 用例覆盖同一断言，冒烟场景已在
  收尾批补做（见下）；N22 死语句以 `penalty` 变量等价改写（直接删会改变 consecutive 分支语义）；
  N25 复核强化——`docs/` 目录不存在（计划按「零引用」记载），`keymaps/__init__` 不
  re-export，改名收敛 base.py 单文件；N27 排序幅度扩为全组字母序（仅移 `registries` 会留下
  `trust`/`shell` 次生乱序）；N28 实测行号 45/68/115（锚点 27/50/71 为 P1 改前旧号）。
- **决策门已拍板（2026-09-25）**：
  - **N18 → 选①已落地**：`YateApp.action_quit` 改调 `editor.execute_action("quit")`
    （[app.py](../../../yate/app.py)），ctrl+q 与 palette/扩展走同一注册表条目；
    冒烟两个 quit 场景 docstring 同步更新；守卫 `test_ctrl_q_routes_through_the_registered_quit_action`
    （spy 重注册 `quit` 证明键路径过注册表）。门禁：pyright 全仓 0 诊断、pytest 全绿
    （1 例既有 timing 偶发单独复跑 ×3 全绿）、冒烟 87/87 · 907/907 · exit 0。
  - **N8 → 已落地（✅，2026-09-26，分支 `issues/keybinding-fix-wt`）**：IKH1RA（Windows Terminal
    键位失效）随 keybinding-fix 计划闭环——`ctrl+/`（`\x1f`→Textual `ctrl+underscore` 命名漂移）
    经 `keys.py` `_CTRL_PUNCT` 补条目修复（全平台），`ctrl+1` 保留 kitty CSI-u 绑定并在双语
    manual/README 标注「仅 kitty/CSI-u 终端可用」+ 替代路径。实测：Textual 8.2.8 XTermParser 对
    `\x1f` 输出 `ctrl+underscore`；WT/conhost 无 kitty 协议且 Textual win32 驱动不读修饰键，
    `ctrl+1` 物理不可达，彻底根治需自建输入通道（`win_keybinding_plan.md` 方案 B，另行排期）。
    详见 [keybinding-fix-wt](../keybinding-fix-wt/README.md) 与
    [wt_keybinding_fix_plan.md](../wt_keybinding_fix_plan.md)；N19 的 `FOCUS_EDITOR_KEY`
    单点常量随方案 B 一并处理。门禁：255 定向 / 1228 全量 passed，pyright 0 诊断。
  - **N30 → 已落地（✅，2026-09-26）**：按原策略「二选一」拍板**注入回调**并单独立项实施；
    方案比选、19 步拆分与门禁实测见
    [theme-layer-refactor-plans](../theme-layer-refactor-plans/README.md)（分支 `issues/refine-arch`）。
- **收尾批（2026-09-25，登记项清账）**：① N19 冒烟场景 `terminal_focus_editor` 补做
  （[integration.py](../../../tools/smoke_test/scenarios/integration.py)：内存 fake PTY
  不起真 shell，故未标 `slow`；断言焦点回编辑区 + `ctrl+1` 字节未进 shell 流）；
  ② `Reporter.summary` 的 "scenarios passed" 分子排除 error 场景（对齐 cli 退出码口径，
  守卫 `test_summary_counts_errored_scenario_as_not_passed`）；③ `commandline.py`
  `active_mode` 改 `Optional[str]`；④ `terminal.py` `start()` 两处 `Any` 补 `# noqa: Any`
  理由注释。附带：3 个全量负载下时序敏感的 pilot 用例加固（manual_search 等布局就绪、
  palette 等输入框焦点就位、f8 worker 超时放宽至 15s；加固前全量跑 5 次 3 败、
  单跑必绿，根因均为按键/搜索先于布局或焦点完成，加固后连续两次全量全绿）。
  收尾门禁：pyright 全仓 0 诊断、pytest 连续两次全量全绿、冒烟 **88/88 场景 ·
  917/917 checks · exit 0**。
- **波次一校准**：N16 的调用方 `tools/changelog/cli.py` 经主代理实测（`pushed_flags`
  调用点在 cli.py:133）补入 SP4 授权；N15 真实落点为 harness.py（testsuite.py 仅重导出）；
  N14 收紧前做过新旧正则等价性验证；N29 以消除（cast + 直删，7 处 ignore 清零）而非注释归档；
  **N25 波及面已核实收窄**——`keymaps/__init__` 不 re-export `Action`、`docs/` 零引用，
  改名收敛在 base.py 单文件，无需扩展文档同步。
