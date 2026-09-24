# P2 Nice-to-have 修复计划

> 来源：[review.md](../../issues/review.md) 2026-09-16 审查 Nice-to-have 段（2026-09-23 复核后
> 仍存在的条目）。均为锦上添花，不阻塞发布；随手清理即可，无独立排期。
> **本文档仅为计划，未实施。**
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
| N1 | 保存始终 LF，忽略原始/平台换行 | [document.py:50-61](../../../yate/editor_core/document.py) | 打开时记录原始主导 EOL（crlf/lf/cr），保存按其写回；默认保持 LF。仅对已存在文件生效，新文件一律 LF | crlf 文件往返 round-trip 断言 EOL 不变 |
| N2 | config tokenizer 重叠 token | [regex_backend.py:651-677](../../../yate/editor_syntax/regex_backend.py) | 各 `finditer` 独立发射；改为按 start 排序后对重叠区间取先到者（或合并为一次交替扫描） | `"true1"` / 字符串内数字用例断言不双着色 |
| N3 | 缺符号时报错无上下文 | [ts_backend/languages.py:249-255](../../../yate/editor_syntax/ts_backend/languages.py) | `getattr(dll, symbol)` 包 try，`raise RuntimeError(f"{library_path} lacks entry point {symbol!r} ...") from e`（`_FAILED` 缓存已防重复） | monkeypatch 假 dll 缺符号，断言错误消息含路径与符号名 |
| N4 | `_to_char` 字节偏移边界缺注释 | [ts_backend/backend.py:127-133](../../../yate/editor_syntax/ts_backend/backend.py) | 纯注释补充：说明 UTF-8 多字节中间偏移经 `errors="ignore"` 丢弃后续字节、映射到字符首列的行为 | 无（注释） |
| N5 | Outdent 按 tab_width 而非上一个 tab stop | [buffer.py:510-535](../../../yate/editor_core/buffer.py) | 空格行改算 `rrem = removed % tab_width`，`removed - (rrem or tab_width)` 对齐上一个 stop；整 Tab 剥离保留 | 3 空格缩进 + tab_width=4 → 移除 3；8 空格 → 移除 4 |
| N6 | `replace_current` 可用 `replace_range` 简化 | [search.py:102-116](../../../yate/editor_core/search.py) | 内部改调 `replace_range(buffer, match_span, replacement)`，删重复实现 | 现有 replace 用例全绿 |
| N7 | `_soft_reset`（ESC c）不退备用屏幕 | [emulator.py:387-397](../../../yate/editor_term/emulator.py) | 加 `self._exit_alt_screen()`（或等价状态复位），对齐 xterm RIS 部分语义 | 写入 `ESC c` 后断言 alt_screen 为 False |
| N8 | ctrl+digit 用 kitty CSI-u | [base.py:118-121](../../../yate/keymaps/base.py) | 换绑到多数终端可发的替代键（如 alt+digit），或保留 kitty 绑定同时文档标注终端要求；**实施前先在 Windows Terminal / cmd 验证** | 手动验证 + 冒烟关键路径 |
| N10 | `cycle_tab` 空操作循环 | [editor.py:489-493](../../../yate/editor.py) | 单 tab 时 no-op 且不提示（或保留提示但仅 verbose）；倾向静默 no-op | 单 tab 连按断言无消息、无异常 |
| N13 | smoke 工具自身无测试 | [tools/smoke_test/](../../../tools/smoke_test/) | 对纯函数部分（场景解析、报告渲染、`extract_svg_rows`）补 `tests/test_smoke_tool.py`；harness 端到端不测（冒烟本身即验证） | 新测试文件 |
| N14 | SVG 提取正则依赖 Textual 版本 | [harness.py:130](../../../tools/smoke_test/harness.py) | 提取失败时给明确报错并打印 SVG 头部片段（诊断版本漂移）；正则收紧为当前实测格式并在注释记录适配的 Textual 版本 | 喂旧版/新版 SVG 样例断言行为 |
| N15 | 单场景执行无整体超时 | [tools/smoke_test/](../../../tools/smoke_test/) | harness 用 `asyncio.wait_for(scenario, timeout=per_scenario)`（默认 60s，`--timeout` 可调），超时记 failed 并继续 | 人造挂起场景断言超时生效 |
| N16 | `check_commit_pushed` 仅支持 gitee | [gitee.py:62-72](../../../tools/changelog/gitee.py) | 其它 host 返回 `None` 时由调用方输出「无法核验，跳过 gate」而非当失败；github 可用 `api.github.com` 同构实现 | 单测 host 分派 |
| N17 | `strip_unreleased` 边界未测 | [render.py:89-108](../../../tools/changelog/render.py) | 补用例：仅有 Unreleased 段、Unreleased 为空、Unreleased 在末尾三种 | 新增 3 条单测 |
| N18 | action `quit` 注册后 UI 不可达（注册冗余，Low） | [vsc.py:87](../../../yate/keymaps/vsc.py) | 三选一：① `YateApp.action_quit` 改调 `editor.execute_action("quit")`；② 面板保留同名 action；③ 删冗余 vsc `<ctrl+q>` 绑定。倾向 ①（保留面板去重语义） | 冒烟 `quit_action_dispatch` 已覆盖可达性 |
| N19 | 终端面板获焦后无法用按键回焦编辑器 | [terminal.py:193-204](../../../yate/editor_view/terminal.py) | `TOGGLE_KEYS` 之外放行 `ctrl+1`（`focus_editor`）；`Esc` 先确认 shell 是否依赖再定 | 冒烟断言终端获焦时 `ctrl+1` 回焦编辑区 |
| N20 | visual 模式 `gg` 永不跳转（死代码） | [vim.py:240-245](../../../yate/keymaps/vim.py) | `pending` 恒空且 `"g"` ∈ motion 表，第二分支不可达；删除死分支或修正条件使其可达 | visual 下 `gg` 跳转用例（若决定支持） |
| N21 | `if key == "o": pass` 死代码 | [vim.py:372-373](../../../yate/keymaps/vim.py) | 删除 | 现有 vim 用例全绿 |
| N22 | `score += 0  # consecutive: best` 死语句 | [palette.py:58-59](../../../yate/editor_view/palette.py) | 删除 | 现有 palette 用例全绿 |
| N23 | `add_binding` 覆盖 `_index` 但旧 binding 残留（help 双条目） | [keymaps/base.py:229-240](../../../yate/keymaps/base.py) | 覆盖时从 `bindings` 列表移除同 raw key 旧条目 | 同 key 重复 `add_binding` 后断言 modals 帮助只展示一条 |
| N24 | `PromptBar.on_cancel` 落入 Textual `on_*` 反射命名空间 | [commandline.py:213](../../../yate/editor_view/commandline.py) | 实例属性改名 `cancel_hook`（当前无冲突消息，纯命名隐患） | 现有 prompt 用例全绿 |
| N25 | 两个无关类型同名 `Action` | [base.py:160](../../../yate/keymaps/base.py) / [registries.py:26](../../../yate/registries.py) | callable 别名改 `ActionFunc`，扩展作者不易混淆 | pyright 全绿 + 扩展文档同步 |
| N26 | `handle_key` docstring「every check is pure」不实 | [editor.py:529-535](../../../yate/editor.py) | 修正表述（`try_window_prefix` 变更 `_window_pending`、popup 分支执行 `accept_completion`） | 无（注释） |
| N27 | 内部导入组非字母序 | [extensions.py:49-53](../../../yate/services/extensions.py) | 排序 | 无 |
| N28 | trust.py 全用 `Path \| None` | [trust.py:27,50,71](../../../yate/services/trust.py) | 统一 `Optional[X]`（与 explorer 条目同类，可合并修） | pyright 全绿 |
| N29 | harness 重写行沿用 `# type: ignore` 无理由注释 | [harness.py:274-283](../../../tools/smoke_test/harness.py) | 补理由注释归档豁免（工具代码，若属既定豁免） | 无（注释） |
| N30 | L0 config 惰性 import L2 `editor_view.theme`（层级债） | [config.py:171-173](../../../yate/config.py) | 后续下沉或注入回调，并在 `architecture-boundaries.md` 登记冻结（类似 R11）；**动架构前需评审** | 架构测试 + pyright 全绿 |
| N31 | `warn()` 在 `sys.stderr` 为 None 时退化写 stdout | [logs.py:85-87](../../../yate/logs.py) | `if sys.stderr is not None:` 再 print——stderr 不可用时静默丢弃，与 docstring「Never raises」一致 | monkeypatch `sys.stderr = None` 断言不抛且不写 stdout |
| N32 | subject 字段可能包含嵌入的分隔符（理论性 Low） | tools/changelog/gitdata.py | body 经 maxsplit 保留杂散分隔符，subject 字段本身无防护；按实现固化行为或加断言/文档说明（2026-09-25 复核补入——review.md 2026-09-16 Suggestion 段唯一漏登记条目） | 现有 changelog 测试全绿 |

## 建议处理方式

- **N4 / N6 / N10** 属「顺手清」级，可在任何触碰对应文件的 PR 里捎带完成
  （S16 已随 P1 波次二完成，不再列入）；新增的 **N20 / N21 / N22 / N27 / N29 / N31** 同级；
- **N1 / N8** 涉及行为变化，实施前需在目标环境人工验证；
- **N30**（config → editor_view 层级债）牵动架构规则，须先评审并同步
  `architecture-boundaries.md`，不随普通 PR 捎带；
- 其余为纯增益，按批次随 P1 工具链改动同批处理；
- **N18** 的三个修法任选其一即可，倾向改动面最小的 ①；
- **N25** 改名会波及扩展作者可见的 `Action` 导出名，需同步扩展文档。
- **N32** 为理论性条目，随手清理即可。
