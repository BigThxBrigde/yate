# yate Code Review（评审总纲索引）

> 本目录原名 `.trae/issues/`，本次整理后统一为 `.trae/reviews/`。
> 原 111 KB 巨型文件 `review.md` 已按「**一轮评审 = 一个带时间戳的文档**」逐章拆分为独立文件，
> 内容**逐字迁移**（含已修复条目的证据与处置记录，未删除任何评审内容）。
> 目录深度未变，文件内指向 `yate/**`、`tests/**`、`tools/**`、`.trae/documents/**`、
> `.trae/rules/**` 的相对链接全部保持有效，已逐条校验。

**命名规范**：`YYYY-MM-DD-<topic>.md`（topic 为英文小写连字符）。无日期可考的历史条目单独置于
`legacy-issues.md`（见文末「遗留问题」）。

---

## 一、速览：仍未闭环 / 尚未通过的项

下表为各轮评审的遗留条目总览（⏸＝暂缓/不修/挂起，🔧＝待修，👀＝待观察，
📌＝仅作记录，🟡＝部分闭环，✅ 已修＝已闭环销账）。共 30 条：
**未闭环 13 条**、已闭环 16 条（#1 / #3 / #5 / #6 / #12 / #13 / #15 / #17 / #19 /
#20 / #22 / #24 / #25 / #27 / #28 / #30）、部分闭环 1 条（#18：三轮评审中前两轮已修，
第三轮按用户决策登记不修）。已闭环条目保留行并标注处置；
#26 / #27 为 2026-10-05 全量清查轮补登记（此前索引漏记），
#28 为同轮的全量文档 review（文档治理，非代码缺陷），
#29 为 PR !56 的 AI 队友评审（0 阻断 / 4 改进，仅登记未处置），
#30 为 PR !57 的 AI 队友评审（1 阻断 + 2 改进，已全部销账）。
整改方案与提交号见 [reviews-open-issues-fixes-plan.md](../documents/reviews-open-issues-fixes-plan.md)
与 [reviews-plans-full-sweep-plan.md](../documents/reviews-plans-full-sweep-plan.md)（2026-10-01 全量清查轮）。

| # | 日期 | 未闭环项 | 标记 | 出处 |
|---|---|---|---|---|
| 1 | 2026-09-16 | `ctrl+digit` 绑定使用 kitty 协议，多数终端不支持 | ✅ 已修（2026-10-01 回填：keybinding-fix-wt Phase B win32-input-mode 落地覆盖 WT（PB6 探针实证 ctrl+1 帧）；legacy 终端限制由 PB4 双语 manual 标注；conhost / VS Code 残留并入 #10 PB5 人工矩阵） | [2026-09-16-full-review.md](2026-09-16-full-review.md) |
| 2 | 2026-09-24 | Windows `os.replace` 对外部占用句柄的兼容面变窄 | ⏸ 明确不修（既定取舍：错误路径安全、无数据丢失，Windows 限定） | [2026-09-24-appprotocol-refactoring-review.md](2026-09-24-appprotocol-refactoring-review.md) |
| 3 | 2026-09-25 | `HighlightProbe.doc` 应使用精确类型 `Document` | ✅ 已修（2026-10-01，`68ad332`：实为 `Document \| None`，首遍前可被调用；偏离记录见方案文档） | [2026-09-25-recheck-supplement.md](2026-09-25-recheck-supplement.md) |
| 4 | 2026-09-26 | Gitee Go 3.12 流水线从未实际运行，镜像可用性未验证 | 👀 待观察项（非代码缺陷，下次流水线触发时确认） | [2026-09-26-py312-upgrade.md](2026-09-26-py312-upgrade.md) |
| 5 | 2026-09-26 | 全项目评审 6 条建议级问题（ConPTY 句柄竞态 / 补全 worker 静默异常 / 高亮降级零日志 / 扩展 setup 半注册 / `editor.py` 组装过载 / 失败路径断言偏弱） | ✅ 已全修（2026-10-01 整改：4 项代码修复 `55e1055` / `9c8bd3a` / `aece343` / `962666c` + 2 项销项，见该文档 §八） | [2026-09-26-full-project-review.md](2026-09-26-full-project-review.md) |
| 6 | 2026-09-26 | WT 下 `ctrl+1` 物理层丢键（conhost 不编 C0 码、WT 无 kitty CSI-u） | ✅ 已修（2026-10-01 回填：Phase B 主体完成——chord 驱动启用 win32-input-mode（CSI ?9001h），WT 下 ctrl+1 可达，应用层 pilot 断言在位；conhost / VS Code 人工复测归 #10 PB5 矩阵） | [2026-09-26-wt-keybinding-ikh1ra.md](2026-09-26-wt-keybinding-ikh1ra.md) |
| 7 | 2026-09-27 | 输入线程宽泛 `except Exception` 的残余建议（`exc_info` / 重置驱动 / UI 通知） | 👀 登记待评估（与「复刻 stock 基线」存在张力，需与上游修法对齐） | [2026-09-27-pr26-keybinding.md](2026-09-27-pr26-keybinding.md) |
| 8 | 2026-09-27 | `explorer._apply_theme` 每次切主题全量 `refresh_tree()` | ⏸ 挂起（当前频率可接受，出现卡顿再拆分着色与重建） | [2026-09-27-ui-refine.md](2026-09-27-ui-refine.md) |
| 9 | 2026-09-27 | `scrollbars.py::render_bar` 复刻上游 1/8 粒度算法 | 📌 记录保留（Textual 升级需回归 `tests/test_scrollbars.py`） | [2026-09-27-ui-refine.md](2026-09-27-ui-refine.md) |
| 10 | 2026-09-27 | PB5 三终端矩阵：conhost / VS Code 待人工复测（WT 已由真机 harness 覆盖） | 🔧 遗留人工项 | [2026-09-27-keybinding-branch-review.md](2026-09-27-keybinding-branch-review.md) |
| 11 | 2026-09-29 | 配对/标签扫描无搜索半径上限（AI 建议 `max_lines` 兜底） | ⏸ 明确不修（与已批准偏离记录 #8「无界扫描」语义冲突，截断会让深层嵌套配对静默失配） | [2026-09-29-pr35-vim-keymap.md](2026-09-29-pr35-vim-keymap.md) |
| 12 | 2026-09-29 | `_submit_save_as` 临时解除的 `read_only` 标志仅 OSError/UnicodeError 分支恢复，未预期异常无兜底 | ✅ 已修（2026-10-01，`17e2804`：saved 标志 + finally 兜底 + 回归用例） | [2026-09-29-pr37-editor-split.md](2026-09-29-pr37-editor-split.md) |
| 13 | 2026-09-29 | `test_vsc_has_no_duplicate_raw_keys` 断言仅报数量不匹配，未列出重复的 raw key（`Keymap._index` 静默覆盖守护测试的失败输出应点名重复键） | ✅ 已修（2026-10-01，`3c1cee2`：Counter 形态，失败输出点名重复键） | [2026-09-29-pr38-vscode-keymap.md](2026-09-29-pr38-vscode-keymap.md) |
| 14 | 2026-09-30 | `_TracingGatedTextualHandler` 定义在 `create_devtools_bridge` 工厂内部，每次调用重新创建类对象（审查者自评"保持现状即可，仅作记录"） | ⏸ 明确不修（textual 懒加载约束下无法模块顶层继承；桥仅单点构造，出现复用需求再评估） | [2026-09-30-pr40-logs-tcss-shell-refactor.md](2026-09-30-pr40-logs-tcss-shell-refactor.md) |
| 15 | 2026-10-01 | `_collect_bilingual` TOCTOU：收集阶段 `exists()` 判定的 `en_source` 在 `run()` 读取时可能已被删除，未捕获 `FileNotFoundError` 致全流程崩溃 | ✅ 已修（2026-10-01，`714183b`：OSError 降级为缺失页走翻译路径 + 回归用例） | [2026-10-01-pack-wiki-round3-review.md](2026-10-01-pack-wiki-round3-review.md) |
| 16 | 2026-10-02 | PR #43 AI 评审 3 项改进：`_submit_save_as` 的 `saved = True` 位置致部分成功场景语义混淆（Low，功能）；`_rebuild_tokens_on_edit` 极端 multiline 场景全量遍历（Low，性能，评审自评现状合理仅记录）；`_warn_degraded_once` 占位符 `%r`/`%s` 风格不一（Nit，可维护） | 👀 登记待决策（3 项均 Low/Nit 无阻断） | [2026-10-02-pr43-reviews-sweep-review.md](2026-10-02-pr43-reviews-sweep-review.md) |
| 17 | 2026-10-02 | PR #44 AI 评审 1 项改进：`tools/__init__.py` 模块 docstring 的 RST 内联标记被误插（"hatchling" 前多一对反引号，inline-literal 永不闭合） | ✅ 已修（2026-10-02，`56815e0`） | [2026-10-02-pr44-py-style-audit-review.md](2026-10-02-pr44-py-style-audit-review.md) |
| 18 | 2026-10-02 | PR #45 AI 评审（三轮）：首轮 vsc paste 只读缓冲覆写 unnamed 寄存器；第二轮 pending_register 生命周期过宽、空串镜像守卫缺失、只读 paste 多余剪贴板读取、缺后端不可用钉用例；第三轮 vsc cut 原子性（先写寄存器后删除）、只读 paste 建议静默返回 | 🟡 首轮/第二轮已修（2026-10-02，`64f5eeb` + 3 修 1 钉）；第三轮 ⏸ 登记不修（2026-10-02 用户决策） | [2026-10-02-pr45-system-clipboard-review.md](2026-10-02-pr45-system-clipboard-review.md) |
| 19 | 2026-10-02 | PR #46 AI 评审 1 项改进：`test_app_css.py` 的 `_default_css_violations` 只扫 `ast.Assign`，`DEFAULT_CSS: str = "inline"`（`ast.AnnAssign`）静默放行 | ✅ 已修（分支 commit `5fca69b`：全模块扫 Assign + AnnAssign + 负向演练；评审时点未推送故 PR 可见提交不含修复，推送后随 PR 闭环）；本次 ⏸ 登记不另修（2026-10-02 用户决策） | [2026-10-02-pr46-remove-inline-default-css-review.md](2026-10-02-pr46-remove-inline-default-css-review.md) |
| 20 | 2026-10-03 | PR #47 AI 评审 2 项改进：`_section_packages()` 列宽按规范名（键）计算、渲染却用展示名（值），展示名更长时 `[packages]` 列对齐错乱；两 spec 硬编码 core 依赖名，与"单一事实来源"目标张力 | ✅ 已修（2026-10-03：`2696aa1` 抽取 stdlib-only `yate/dist_meta.py` + `c9c8348` 列宽按 `.values()` + `736c637` spec 构建期派生，见该文档） | [2026-10-03-pr47-ai-review.md](2026-10-03-pr47-ai-review.md) |
| 21 | 2026-10-03 | PR #49 AI 评审 3 项改进：含 tab 行 inline diff 高亮偏移（渲染正确性，未复核）；超长行全量 `expand_char` 展开浪费（性能，未复核）；两处 `on_unmount` 缺 `@override`（一致性，已核实属实） | ⏸ 本次登记不另修（2026-10-03 用户决策；登记于 diff-tool-plan.md 遗留待办） | [2026-10-03-pr49-diff-tool-ai-review.md](2026-10-03-pr49-diff-tool-ai-review.md) |
| 22 | 2026-10-03 | 全量 python-code-review 评审 83 项（0 CRITICAL / 15 WARNING / 68 SUGGESTION，覆盖 yate/ tools/ tests/ pack/）：R-19（on_key 无条件吞键）与架构规则 R10 冲突依规则不修，其余 82 项全部修复并回填 | ✅ 已全修（2026-10-03，`90ad524`…`867acea` 十笔修复/用例提交；方案与处置表见 [python-code-review-fixes-plan.md](../documents/python-code-review-fixes-plan.md)，门禁实测 pyright 0 errors + pytest 全绿 + 覆盖率 91.26%） | [2026-10-03-python-code-review.md](2026-10-03-python-code-review.md) |
| 23 | 2026-10-03 | PR #52 AI 队友评审 3 项改进（无阻断，风险 low）：① `session.py` split 不变量用 `assert`（`-O` 下被剥离）；② `pack/_common.py` `_pkg_path` 与 `SpecInputs.pkg_path` 重复；③ `gitdata.py` `read_tags` 空格分隔无法容忍含空格 tag 名 | 👀 登记待处置（2026-10-04 登记；评审记录 [2026-10-03-pr52-ai-review.md](2026-10-03-pr52-ai-review.md)） | [2026-10-03-pr52-ai-review.md](2026-10-03-pr52-ai-review.md) |
| 24 | 2026-10-04 | syntax-langs 分支评审 + 计划实施核对（[PR !53](https://gitee.com/jermaine/yate/pulls/53#note_51442774_conversation_191380732) note 51442774；issue IKJLTB 内置语法高亮扩展，7 提交 / 51 文件）：W3 验收未执行（`tree-sitter-fsharp` 未装，fsharp 查询节点名全未实测）；`markdown.scm:17` 的 `@builtin` 未登记进 `DEFAULT_CAPTURE_MAP` 静默失效；文档 4 处承诺超出实现（batch `%VAR%` / 手册"两个扩展示例"实为 7 / README 把 Perl 算进 ts 覆盖 / `.gitignore` 后缀推导）；scss/less 被路由到 CSS grammar；缺 scm 捕获名与三份清单一致性两道静态守护 | ✅ 已修（2026-10-04，用户批准全部范围；G1–G8 + H1–H10 逐条处置见 [syntax-langs-review-fixes-plan.md](../documents/syntax-langs-review-fixes-plan.md)；W3 验收由新增 `tests/test_extension_examples.py` 补做；门禁 pyright 0 + 1747 passed + 22 架构 + 覆盖率 91.19%） | [2026-10-04-syntax-langs.md](2026-10-04-syntax-langs.md) |
| 25 | 2026-10-05 | Gitee PR !54 AI 队友评审**两轮**（[note 51443873](https://gitee.com/jermaine/yate/pulls/54#note_51443873_conversation_191386654) conversation 191386654 + [note 51445224](https://gitee.com/jermaine/yate/pulls/54#note_51445224_conversation_191392268) conversation 191392268；`enh/input-assist` 输入辅助）：第二轮 ⛔ 1 阻断（`vim.py::_shift_row` 多计数语义为"当前行 ×N 级"，与 vim 的"`3>` 向下 3 行各 1 级"不一致）+ 2 改进（`delete_backward` 绕过 `set_cursor`；G9 基准取均值）；第三轮 ⚠️ 0 阻断 + 2 改进（PR 混入无关 ai-specs 文档；`closes_block` 未接线） | ✅ 第二轮阻断与改进 1 已修（2026-10-05，采纳**对齐 vim 语义**路线：`3>` 改向下 3 行各 1 级、文件末尾截断，帮助文案 `Indent [count] lines` 由此转为正确；连带改 `delete_backward`、3 条 pin 旧语义的用例 + 中英手册 3 处措辞；门禁 pyright 0 + 22 架构 + 1788 passed + 覆盖率 91.27%）；第三轮改进 1 已由用户手动处置（`6937900` 删除三个 ai-specs 文档，不登记为待办）；⏸ 第二轮改进 2 按评审者自评仅作登记；👀 第三轮改进 2 登记 G9-3（`closes_block` 长期未接线，评审认可保留裁决）；VISUAL 模式 count 差异登记不修（评审范围外）。处置见 [input-assist-review-fixes-plan.md](../documents/input-assist-review-fixes-plan.md) §五 | [2026-10-05-pr54-input-assist-ai-review.md](2026-10-05-pr54-input-assist-ai-review.md) |
| 26 | 2026-10-03 | Gitee PR #51 AI 队友评审（[note 51435445](https://gitee.com/jermaine/yate/pulls/51#note_51435445_conversation_191349311) conversation 191349311；`fix/path-space-handling`，issue IKJK0B，含空格路径解析 `_split_paths` / `_strip_quotes`）：1 改进 —— `_saveas` / `_split` / `_vsplit` 的 `_strip_quotes` 调用缺前置 `.strip()` | ⏸ 本次登记不另修（2026-10-03 用户决策；核对结论为场景当前不可达：`run_command` 入口已 `text.strip()` + `split(maxsplit=1)`，属防御性一致性问题） | [2026-10-03-pr51-path-space-ai-review.md](2026-10-03-pr51-path-space-ai-review.md) |
| 27 | 2026-10-03 | wiki 翻译进度改动评审（PR !50，`feat/wiki-translate-progress`，`tools/pack/wiki.py` 预扫描 + rich Progress）：2 major + 3 minor 已修（`19f44f0`），1 NTH 未采纳 | ✅ 已修（2026-10-03，`19f44f0`；本条为 2026-10-05 全量清查轮补登记，此前索引漏记） | [2026-10-03-wiki-translate-progress.md](2026-10-03-wiki-translate-progress.md) |
| 28 | 2026-10-05 | **全量文档 review**（207 篇受控 Markdown，排除 rules/agents；机械体检 + 12 篇用户可见文档语义深审 + 147 篇计划状态取证）：命名违规 26→0、真实机器路径 51→0、失效链接 22→6 篇（仅剩真正失效目标）、`yate/docs` 双语始终成对；发现并修正 README 9 类、`yate/docs` 8 类、wikis 12 类语义偏离 | ✅ 已处置（2026-10-05，分支 `ref/doc-review-sweep`；未实施 2 篇 / 部分实施 4 篇 / 已被取代 7 篇已统一标注状态块并汇总至 [`.trae/documents/overview.md`](../documents/overview.md)；门禁 pyright 0 + 1818 tests 0 failures + 22 架构 + 覆盖率 91.27%。本条为文档治理轮，非代码缺陷） | [2026-10-05-doc-review-sweep.md](2026-10-05-doc-review-sweep.md) |
| 29 | 2026-10-05 | Gitee PR !56 AI 队友评审（[note 51450173](https://gitee.com/jermaine/yate/pulls/56#note_51450173_conversation_191412615) conversation 191412615；`enh/pack-wiki-parallel`，issue IKJPEK，风险自评 low）：4 改进 —— ① `store_manifest` 经 `_write_page_text` 固定用 `WIKI_PAGE_WRITE`，已定义的 `WIKI_MANIFEST_WRITE`（`WIKI-0105`）无任何引用；② `_read_source_bytes` 把通用 `OSError` 也报成 `WIKI_ZH_SOURCE_MISSING`，`WIKI_SOURCE_UNREADABLE`（`WIKI-0103`）未使用；③ `_emit_mode` / `_COLLECTED_FAILURES` 模块级全局在 `finally` 早清空，`run()` 不可重入；④ `needs_translation` 与 `_prepare_pages` 判定逻辑重复 | 👀 登记未处置（2026-10-05 登记，0 阻断 / 4 改进，功能性 2 + 可维护性 2） | [2026-10-05-pr56-pack-wiki-parallel-ai-review.md](2026-10-05-pr56-pack-wiki-parallel-ai-review.md) |
| 30 | 2026-10-05 | Gitee PR !57 AI 队友评审（**两轮**：[note 51450178](https://gitee.com/jermaine/yate/pulls/57#note_51450178_conversation_191412657) conversation 191412657 + [note 51450575](https://gitee.com/jermaine/yate/pulls/57#note_51450575_conversation_191414938) conversation 191414938；`enh/smoke-test-scenarios` 冒烟扩充，场景 89 → 104）：第一轮 ⛔ 1 阻断（`screensaver.py` 两 app 共用 `rows`，第一个 app 的 SVG 快照成死存储，且因不变量只扫最后一个 app 而从未被覆盖）+ 2 改进（`guards.py` 主题候选数 `8` 与两处派生主题名硬编码；`workspace_nav.py` 循环上限 `12` 为魔法数字）；第二轮 ⚠️ 0 阻断 + 1 改进（`tests/test_smoke_cli.py` 无任何 fixture，与 `test_smoke_harness.py` 的全局状态隔离不对称） | ✅ 第一轮阻断与 2 改进已全修（2026-10-05，`c7099d0` 拆为两个单 app 场景 / `77475d8` 三处期望值改由 `theme.available()` 派生 / `6a95fd8` 上限改由 `MIN_FRACTION`+`RESIZE_STEP` 推导；评审建议的 `theme.names()` 不存在已替换；门禁 pyright 0 + 1875 passed / 8 skipped + 22 架构 + 冒烟 104/104（1252 checks，覆盖 45/45 与 66/66）+ `compare` 全 MATCH + 覆盖率 91.27%）；👀 第二轮 M3 登记待处置（2026-10-05 用户指令只登记不修；核实为**潜在**风险非现症——唯一真跑场景 `keymap_toggle` 自复原键位、未传 `--seed` 故不改全局种子、主题由 harness 收尾复原；评审称两个 fixture 均 autouse 有误，`restore_theme` 是按需 fixture）。处置见 [smoke-review-fixes-plan.md](../documents/smoke-review-fixes-plan.md) | [2026-10-05-pr57-smoke-expansion-ai-review.md](2026-10-05-pr57-smoke-expansion-ai-review.md) |

---

## 二、评审轮次总表

结论取自各文档自身记载（四维度表、⛔/✅ 结论行、条目勾选状态）；「当前处置状态」为照实标注，
本次仅为文档整理，未对任何未修条目做代码修改。

| 日期 | 评审范围 / 对象 | 结论（通过与否） | 阻断项 / 改进项数量 | 当前处置状态 | 文档 |
|---|---|---|---|---|---|
| （早期，无日期） | 历史问题登记：输入闪烁、不存在文件名卡住 | 通过 | 0 阻断 / 2 项 | ✅ 已全修 | [legacy-issues.md](legacy-issues.md) |
| 2026-09-16 | **全量代码审查（首次全量，`yate/` 全仓）** | ❌ 未通过（Critical 10 条必须修复） | 10 Critical / 29 Suggestion / 15 Nice-to-have | ✅ 已全修（2026-10-01 回填：末项 kitty `ctrl+digit` 由 Phase B win32-input-mode 覆盖，见速览 #1） | [2026-09-16-full-review.md](2026-09-16-full-review.md) |
| 2026-09-23 | 全量代码审查（第二轮：原子写 / undo 上限 / `modified` O(n) / 期望列 / 扩展自动加载 / 静默 except / symlink 环） | ✅ 通过 | 0 阻断 / 7 项 | ✅ 已全修（`05106d5` / `5190225` / `b0d154d` / `a89a720`） | [2026-09-23-full-review.md](2026-09-23-full-review.md) |
| 2026-09-23 | 已失效条目归档（复核基准 2026-09-23 当前代码） | ➖ 不适用（已失效，仅存档） | 0 / 0（3 条表格） | ⬜ 已失效：Python 3.9 兼容、中文 docstring、未使用导入 | [2026-09-23-invalidated-items.md](2026-09-23-invalidated-items.md) |
| 2026-09-23 | 冒烟补场景调查（`run --coverage` 缺口，`0984361`） | ✅ 通过 | 0 阻断 / 2 项 | ✅ 已全修（P2 决策门 G2 + 波次二 SP6，含冒烟 `terminal_focus_editor`） | [2026-09-23-smoke-scenarios.md](2026-09-23-smoke-scenarios.md) |
| 2026-09-23 | 补全弹窗按键放行修复的附带发现（Esc 后在途 worker 重开弹窗） | ✅ 通过 | 0 阻断 / 1 项 | ✅ 已全修（三状态标记 + 3 条守卫） | [2026-09-23-completion-popup-race.md](2026-09-23-completion-popup-race.md) |
| 2026-09-23 | 测试 mock 目标核对（22 处 / 15 个不同目标，分层重构后） | ✅ 通过（无需改动） | 0 阻断 / 0 缺陷 | ✅ 结论：无静默失效，`tests/` 无需改动 | [2026-09-23-test-mock-audit.md](2026-09-23-test-mock-audit.md) |
| 2026-09-24 | **PR #13 审查修复**（Gitee AI 审查，两轮触发） | ❌ 初评未通过 → ✅ 复评通过 | 2 阻断 / 4 改进（+1 附带发现） | ✅ 已全修（9/9），门禁实测全绿 | [2026-09-24-pr13-review.md](2026-09-24-pr13-review.md) |
| 2026-09-24 | **全量代码审查**（分支 `issues/appprotocol-refactoring`，54 commits / 132 files / +16655−4469） | ❌ 未通过（4 处可复现 Major 回归 M1–M4 + 2 处存量功能缺陷） | 0 Critical / 4 Major / 27 Minor / 12 Suggestion | 🟡 部分待修：42/43 已修，1 项 ⏸ 明确不修（Windows `os.replace`） | [2026-09-24-appprotocol-refactoring-review.md](2026-09-24-appprotocol-refactoring-review.md) |
| 2026-09-24 | 复审补充 `yate/logs.py`（外部审查工具 2 项） | ✅ 通过（均 Low） | 0 阻断 / 2 项 | ✅ 已全修（`warn()` stderr 为 None 静默丢弃；崩溃/trace 文件名加 pid） | [2026-09-24-logs-review.md](2026-09-24-logs-review.md) |
| 2026-09-25 | 复审补充（外部审查工具 2 项，`issues/nice-to-have-enh`） | 🟡 部分通过（1 误报 + 1 成立） | 0 阻断 / 2 项 | ✅ 已全修（2026-10-01 整改：EOL 写回＝⛔ 误报已归档；`HighlightProbe.doc` 已修 `68ad332`） | [2026-09-25-recheck-supplement.md](2026-09-25-recheck-supplement.md) |
| 2026-09-26 | Python 3.12 升级迁移审查（分支 `py-upgrade-3.12`，4 commits） | ✅ 通过（无 critical / major） | 0 阻断 / 2 minor | 🟡 部分待修：1 已修（`harness.py` 导入扁平化）；Gitee Go 3.12 镜像 👀 待观察 | [2026-09-26-py312-upgrade.md](2026-09-26-py312-upgrade.md) |
| 2026-09-26 | readonly feature 评审（两轮：本地自查 + Gitee PR #24） | ⛔ PR 初评未通过 → ✅ 修复后通过 | 1 阻断 / 13 改进（6 自查 + 8 PR，去重 1） | ✅ 已全修（`8b6b1b4` / `d960a08` / `1f82fae` / `dd47be0`） | [2026-09-26-readonly-feature.md](2026-09-26-readonly-feature.md) |
| 2026-09-26 | **全项目评审报告**（master `faa6d75`，5 只读子代理 + 主代理复核） | ✅ 通过（总评 8.5/10，无致命 / 严重） | 0 阻断 / 6 建议级 | ✅ 已全修（2026-10-01 整改轮：4 项代码修复 + 2 项销项，见该文档 §八） | [2026-09-26-full-project-review.md](2026-09-26-full-project-review.md) |
| 2026-09-26 | Windows Terminal 键位失效（Gitee Issue IKH1RA） | 🟡 部分通过 | 0 阻断 / 1 项（含 3 个子根因） | ✅ 已修（2026-10-01 回填：`ctrl+p` / `ctrl+/` 已修，`ctrl+1` 由 Phase B win32-input-mode 覆盖；残留人工复测归 PB5，见速览 #6 / #10） | [2026-09-26-wt-keybinding-ikh1ra.md](2026-09-26-wt-keybinding-ikh1ra.md) |
| 2026-09-27 | 日志/devtools 桥接评审（分支 `fix/logging-tracing-wt`，3 commits，2 名验证子代理交叉复核） | ✅ 通过（无致命 / 严重，全建议级） | 0 阻断 / 4 项 | ✅ 已全修（`44972c9` / `5d3399d` / `e754b27` / `905385f`） | [2026-09-27-devtools-bridge.md](2026-09-27-devtools-bridge.md) |
| 2026-09-27 | 日志/devtools 桥接评审（**PR #28** Gitee AI 审查） | ⚠️ 无阻断项，可优化后合并 | 0 阻断 / 3 改进 | ✅ 已全修（`c13f407`，3 项建议全部采纳） | [2026-09-27-pr28-devtools-bridge.md](2026-09-27-pr28-devtools-bridge.md) |
| 2026-09-27 | 分支评审 `issues/keybinding-fix-wt`（keyproto + 分层 trace 日志） | ✅ 通过（总评 9/10，分支可合并质量） | 0 阻断 / 2 项（1 严重 + 1 建议） | ✅ 已全修（`b21ff37`）；遗留 PB5 三终端矩阵 🔧 人工复测 | [2026-09-27-keybinding-branch-review.md](2026-09-27-keybinding-branch-review.md) |
| 2026-09-27 | **Gitee PR #26** 评审（键位修复分支，AI 队友审查） | ⚠️ 无阻断项，可优化后合并 | 0 阻断 / 3 改进 | 🟡 部分待修：3 项已处置，1 条残余建议 👀 登记待评估 | [2026-09-27-pr26-keybinding.md](2026-09-27-pr26-keybinding.md) |
| 2026-09-27 | tcss 拆分实现评审（分支 `enh/tcss-enh`，Issue IKINFT） | ✅ 通过（总评 93/100） | 0 阻断 / 3 建议 | ✅ 已全修（全部当场修复于 `7e51d6b`） | [2026-09-27-tcss-split.md](2026-09-27-tcss-split.md) |
| 2026-09-27 | UI refine 评审（分支 `enh/ui-refine`，Issue IKINF3）+ **PR #29** AI 审查 | ❌ PR #29 功能性未通过（1 阻断）→ ✅ 已修复 | 1 阻断 / 3 改进（PR #29）+ 2 架构张力 | 🟡 部分待修：阻断与改进已修 + T1/T2 已治理；1 性能项 ⏸ 挂起、1 项 📌 记录保留 | [2026-09-27-ui-refine.md](2026-09-27-ui-refine.md) |
| 2026-09-29 | **Gitee PR #35** 评审（vim 键位保真分支，AI 队友审查） | ⛔ 1 阻断（operator 排他端点未钳制）→ ✅ 修复后通过 | 1 阻断 / 3 改进 | ✅ 阻断与 2 项改进已修（`c7c7f69`）；1 项 ⏸ 明确不修（见速览 #11） | [2026-09-29-pr35-vim-keymap.md](2026-09-29-pr35-vim-keymap.md) |
| 2026-09-29 | editor-split 系列评审（分支 `ref/editor-refactoring`，5 提交，editor.py 1425→882 行） | ✅ 通过（0 阻断 / 0 major） | 0 阻断 / 3 minor | ✅ 3 项均修复（`a4990c2` + 同日 TRAE-code-review 复核 `8d1fb42`） | [2026-09-29-editor-split.md](2026-09-29-editor-split.md) |
| 2026-09-29 | **Gitee PR #37** 评审（editor-split 分支，AI 队友审查） | ⚠️ 无阻断项，可优化后合并 | 0 阻断 / 1 改进 | ✅ 已修（2026-10-01，`17e2804`：`read_only` 异常恢复兜底 + 回归用例） | [2026-09-29-pr37-editor-split.md](2026-09-29-pr37-editor-split.md) |
| 2026-09-29 | **Gitee PR #38** 评审（vscode keymap review 分支，AI 队友审查） | ⚠️ 无阻断项，可优化后合并 | 0 阻断 / 1 改进 | ✅ 已修（2026-10-01，`3c1cee2`：Counter 断言形态，见速览 #13） | [2026-09-29-pr38-vscode-keymap.md](2026-09-29-pr38-vscode-keymap.md) |
| 2026-09-30 | **Gitee PR #40** 评审（logs/tcss 外壳重构分支，AI 队友审查） | ⚠️ 无阻断项，可优化后合并 | 0 阻断 / 1 改进 | ✅ 无需改动（唯一改进项审查者自评"保持现状"，仅作记录，见速览 #14） | [2026-09-30-pr40-logs-tcss-shell-refactor.md](2026-09-30-pr40-logs-tcss-shell-refactor.md) |
| 2026-10-01 | **Gitee PR #39** 第三轮评审（wiki 生成器 + translate 模块，AI 队友审查） | ✅ 无阻断项，可优化后合并 | 0 阻断 / 1 改进 | ✅ 已修（2026-10-01，`714183b`：TOCTOU OSError 降级 + 回归用例，见速览 #15） | [2026-10-01-pack-wiki-round3-review.md](2026-10-01-pack-wiki-round3-review.md) |
| 2026-10-02 | **Gitee PR #43** 评审（reviews-open-issues-fixes 分支全量 22 提交，AI 队友审查） | ⚠️ 无阻断项，可优化后合并 | 0 阻断 / 3 改进（Low×2 + Nit×1）+ 2 正面 | 👀 登记待决策（改进项 2 评审自评现状合理仅记录，见速览 #16） | [2026-10-02-pr43-reviews-sweep-review.md](2026-10-02-pr43-reviews-sweep-review.md) |
| 2026-10-02 | **Gitee PR #44** 评审（py-style-audit 风格规范化分支全量，AI 队友审查，两轮） | ⚠️ 无阻断项，可优化后合并（首轮 1 阻断 → 复审降为 1 改进） | 首轮 1 阻断 / 1 改进 → 复审 0 阻断 / 1 改进 | ✅ 已修（2026-10-02，`56815e0`：还原 docstring 成对 RST 标记，见速览 #17） | [2026-10-02-pr44-py-style-audit-review.md](2026-10-02-pr44-py-style-audit-review.md) |
| 2026-10-02 | **Gitee PR #45** 评审（system-clipboard 系统剪贴板集成分支，AI 队友审查，三轮） | ⚠️ 无阻断项（三轮均无阻断；第三轮 2 项按用户决策登记不修） | 首轮 1 改进 → 第二轮 4 改进（low）→ 第三轮 2 改进（medium） | 🟡 首轮/第二轮已修（`64f5eeb`：只读守卫；`ec2606e`：pending 前缀生命周期 + 空串守卫 + paste 零读取对称）；⏸ 第三轮不修（只读契约保持显式抛错，见速览 #18） | [2026-10-02-pr45-system-clipboard-review.md](2026-10-02-pr45-system-clipboard-review.md) |
| 2026-10-02 | **Gitee PR #46** 评审（remove-inline-default-css 分支，issue IKJHPH，AI 队友审查） | ⚠️ 无阻断项，可优化后合并（风险 low） | 0 阻断 / 1 改进 | ✅ 改进项已在分支修复（`5fca69b`，AnnAssign 入扫；评审时点未推送）；⏸ 本次登记不另修（用户决策，见速览 #19） | [2026-10-02-pr46-remove-inline-default-css-review.md](2026-10-02-pr46-remove-inline-default-css-review.md) |
| 2026-10-03 | **Gitee PR #47** 评审（diag-package-sync 分支，issue IKJJFI，AI 队友审查） | ⚠️ 无阻断项，可优化后合并（风险 low） | 0 阻断 / 2 改进 | ✅ 已全修（2026-10-03，`2696aa1` / `c9c8348` / `736c637`，见速览 #20） | [2026-10-03-pr47-ai-review.md](2026-10-03-pr47-ai-review.md) |
| 2026-10-03 | **Gitee PR #49** 评审（diff-tool 分支，issue IKJC88，AI 队友审查） | ⚠️ 无阻断项，可优化后合并（风险 low） | 0 阻断 / 3 改进 | ⏸ 本次登记不另修（2026-10-03 用户决策，见速览 #21） | [2026-10-03-pr49-diff-tool-ai-review.md](2026-10-03-pr49-diff-tool-ai-review.md) |
| 2026-10-03 | **全量 python-code-review**（master `2c124a7` 全仓 Python，技能六维度框架，7 只读评审子代理并行 + 主代理核实修复） | ⚠️ MINOR ISSUES（0 CRITICAL，无阻断；R-19 与 R10 冲突依规则不修） | 0 CRITICAL / 15 WARNING / 68 SUGGESTION | ✅ 已全修（82/83，`90ad524`…`867acea`；处置表见 [python-code-review-fixes-plan.md](../documents/python-code-review-fixes-plan.md)） | [2026-10-03-python-code-review.md](2026-10-03-python-code-review.md) |
| 2026-10-03 | **Gitee PR #52 AI 队友评审**（python-code-review 修复分支，note 51438554，AI 队友"PR观察者"） | ⚠️ 无阻断项，可优化后合并（风险 low） | 0 阻断 / 3 改进 | 👀 登记待处置（2026-10-04 登记，见速览 #23） | [2026-10-03-pr52-ai-review.md](2026-10-03-pr52-ai-review.md) |
| 2026-10-03 | **Gitee PR #51 评审**（path-space-handling 分支，含空格路径解析，AI 队友审查） | ⚠️ 无阻断项，可优化后合并（风险 low） | 0 阻断 / 1 改进 | ⏸ 登记不另修（2026-10-03 用户决策；核对结论：场景不可达，属防御性一致性） | [2026-10-03-pr51-path-space-ai-review.md](2026-10-03-pr51-path-space-ai-review.md) |
| 2026-10-03 | **PR !50 评审**（wiki 翻译进度改动，`tools/pack/wiki.py` 预扫描 + rich Progress） | ⚠️ MINOR ISSUES（无阻断） | 2 major / 3 minor / 1 NTH | ✅ 2 major + 3 minor 已修（`19f44f0`）；1 NTH 未采纳 | [2026-10-03-wiki-translate-progress.md](2026-10-03-wiki-translate-progress.md) |
| 2026-10-04 | **syntax-langs 分支评审 + 计划实施核对 + 三轮修复**（[PR !53](https://gitee.com/jermaine/yate/pulls/53#note_51442774_conversation_191380732) note 51442774；`enh/syntax-langs`，issue IKJLTB，评审时点 7 提交 / 51 文件 / +2182 −223；3 只读评审子代理 + 2 轮 `code-review-expert` 复核 + 主代理逐条复核） | ⚠️ MINOR ISSUES（0 CRITICAL；W1/W2/W4/W5 通过，W3 验收未执行） | 0 CRITICAL / 5 WARNING（计划核对阶段 G1–G5）/ 若干 SUGGESTION（逐条共 18 条：G1–G8 + H1–H10） | ✅ 已全修（全部处置：G1–G8 + H1–H10，2026-10-04，三轮：评审 6 WARNING → 复核 5 条已修实 + W2' 过度着色 → 注释残留与断言加固；门禁 pyright 0 + 1747 passed + 22 架构 + 覆盖率 91.19%；见 [syntax-langs-review-fixes-plan.md](../documents/syntax-langs-review-fixes-plan.md)） | [2026-10-04-syntax-langs.md](2026-10-04-syntax-langs.md) |
| 2026-10-05 | **Gitee PR !54 AI 队友评审**（两轮：[note 51443873](https://gitee.com/jermaine/yate/pulls/54#note_51443873_conversation_191386654) conversation 191386654 + [note 51445224](https://gitee.com/jermaine/yate/pulls/54#note_51445224_conversation_191392268) conversation 191392268；`enh/input-assist` 输入辅助，issue IKJMQ2，风险自评均 low） | ⛔ 第二轮未通过（1 阻断 + 2 改进）→ ⚠️ 第三轮无阻断（2 改进，阻断项未再出现） | 第二轮 1 阻断 / 2 改进；第三轮 0 阻断 / 2 改进 | ✅ 第二轮阻断与改进 1 已修（2026-10-05，对齐 vim 多行语义 + `delete_backward` 走 `set_cursor`；连带 3 条用例与中英手册 3 处措辞）；第三轮改进 1 已由用户手动处置（`6937900`）；⏸ 第二轮改进 2（G9 均值基准）登记不修；👀 第三轮改进 2 登记 G9-3；VISUAL count 差异登记不修（见速览 #25） | [2026-10-05-pr54-input-assist-ai-review.md](2026-10-05-pr54-input-assist-ai-review.md) |

| 2026-10-05 | **Gitee PR !57 AI 队友评审**（两轮：[note 51450178](https://gitee.com/jermaine/yate/pulls/57#note_51450178_conversation_191412657) conversation 191412657 + [note 51450575](https://gitee.com/jermaine/yate/pulls/57#note_51450575_conversation_191414938) conversation 191414938；`enh/smoke-test-scenarios` 冒烟扩充，场景 89 → 104；正文经 Gitee API 取回，页面不展开评论） | ⛔ 第一轮未通过（1 阻断 + 2 改进）→ ⚠️ 第二轮无阻断（1 改进） | 第一轮 1 阻断 / 2 改进；第二轮 0 阻断 / 1 改进 | ✅ 第一轮阻断与 2 改进已全修（`c7099d0` 拆场景消除死存储并让第一个 app 重回不变量覆盖 / `77475d8` 主题期望值改由注册表派生 / `6a95fd8` 循环上限改由产品常量推导）；👀 第二轮 M3（CLI 测试全局状态隔离不对称）登记待处置，核实为潜在风险非现症；见速览 #30 与 [smoke-review-fixes-plan.md](../documents/smoke-review-fixes-plan.md) | [2026-10-05-pr57-smoke-expansion-ai-review.md](2026-10-05-pr57-smoke-expansion-ai-review.md) |
| 2026-10-05 | **全量文档 review（doc-review-sweep）**（207 篇受控 Markdown，排除 `.trae/rules` 与 `.trae/agents`；3 名只读子代理分文件并行 + 主代理逐条复核 + 机械体检脚本） | ✅ 通过（无阻断） | 命名 26 / 真实路径 51 / 断链 22 文件；语义偏离 29 类（README 9 + `yate/docs` 8 + wikis 12）；计划状态 147 篇逐篇取证 | ✅ 已处置（命名违规→0、真实路径→0、断链→6 篇仅剩真正失效目标；147 篇统一状态块 + `.trae/documents/overview.md` 汇总；门禁 pyright 0 + 1818 tests + 22 架构 + 覆盖率 91.27%） | [2026-10-05-doc-review-sweep.md](2026-10-05-doc-review-sweep.md) |
| 2026-10-05 | **Gitee PR !56 AI 队友评审**（[note 51450173](https://gitee.com/jermaine/yate/pulls/56#note_51450173_conversation_191412615) conversation 191412615；`enh/pack-wiki-parallel`，issue IKJPEK 的 pack wiki 增强：每批 ≤10 篇 + 并发上限 CPU×2 的线程池、`error[CODE]: message` 错误码体系、`--jobs`/`--debug`） | ⚠️ 无阻断项，可优化后合并（风险 low） | 0 阻断 / 4 改进（功能性 2 + 可维护性 2） | 👀 登记未处置（2026-10-05；P1 manifest 错误码 / P2 `_read_source_bytes` OSError 码 / P3 emitter 全局收尾竞态 / P4 `needs_translation` 与 `_prepare_pages` 判定重复） | [2026-10-05-pr56-pack-wiki-parallel-ai-review.md](2026-10-05-pr56-pack-wiki-parallel-ai-review.md) |

**状态图例**：✅ 已全修 ｜ 🟡 部分待修 ｜ ⬜ 已失效 ｜ ➖ 不适用

---

## 三、附录 A：原 `review.md` 章节 → 新文件映射表

| 原 `review.md` 章节（顶层 `##`） | 原行号区间 | 新文件 |
|---|---|---|
| `# yate Code Review`（文件标题） | 1 | 本文件（索引标题） |
| `## 历史问题` | 3–6 | `legacy-issues.md` |
| `## 日志/devtools 桥接评审（fix/logging-tracing-wt）— 2026-09-27`（首次，分支评审） | 8–57 | `2026-09-27-devtools-bridge.md` |
| `## 日志/devtools 桥接评审（fix/logging-tracing-wt）— 2026-09-27`（第二节，PR #28 AI 审查） | 61–97 | `2026-09-27-pr28-devtools-bridge.md` |
| `## Windows Terminal 键位失效（IKH1RA）— 2026-09-26` | 101–123 | `2026-09-26-wt-keybinding-ikh1ra.md` |
| `## 全量代码审查 — 2026-09-16`（含 Critical / Suggestion / Nice-to-have 三个子节） | 126–426 | `2026-09-16-full-review.md` |
| `## 全量代码审查 — 2026-09-23` | 428–448 | `2026-09-23-full-review.md` |
| `## 已失效条目` | 451–461 | `2026-09-23-invalidated-items.md` |
| `## 冒烟补场景调查 — 2026-09-23` | 464–483 | `2026-09-23-smoke-scenarios.md` |
| `## 补全弹窗按键放行修复的附带发现 — 2026-09-23` | 487–503 | `2026-09-23-completion-popup-race.md` |
| `## 测试 mock 目标核对 — 2026-09-23` | 507–532 | `2026-09-23-test-mock-audit.md` |
| `## PR #13 审查修复 — 2026-09-24` | 536–601 | `2026-09-24-pr13-review.md` |
| `## 全量代码审查 — 2026-09-24（issues/appprotocol-refactoring 分支）` | 605–984 | `2026-09-24-appprotocol-refactoring-review.md` |
| `## 复审补充（logs.py）— 2026-09-24` | 988–1010 | `2026-09-24-logs-review.md` |
| `## 复审补充 — 2026-09-25` | 1014–1058 | `2026-09-25-recheck-supplement.md` |
| `## Python 3.12 升级迁移审查 — 2026-09-26` | 1062–1123 | `2026-09-26-py312-upgrade.md` |
| `## readonly feature 评审（两轮）— 2026-09-26` | 1127–1235 | `2026-09-26-readonly-feature.md` |
| `## Gitee PR #26 评审（键位修复分支）— 2026-09-27` | 1237–1283 | `2026-09-27-pr26-keybinding.md` |

**原独立文件改名：**

| 原文件（`.trae/issues/`） | 新文件（`.trae/reviews/`） |
|---|---|
| `review_20260926.md` | `2026-09-26-full-project-review.md` |
| `review_20260927.md` | `2026-09-27-tcss-split.md` |
| `review_keybinding_20260927.md` | `2026-09-27-keybinding-branch-review.md` |
| `review_ui_refine_20260927.md` | `2026-09-27-ui-refine.md` |

---

## 四、附录 B：遗留问题（需主代理决策）

1. **`legacy-issues.md` 无日期**：原 `## 历史问题` 章节未记载任何日期（两条早期 UX 问题，
   早于 2026-09-16 首次全量审查），故未按 `YYYY-MM-DD-` 前缀命名。
   **（2026-09-29 决策：保持现状**——文件名保留 `legacy-issues.md` 不加日期前缀**）**。
2. ~~仓库内仍有 3 处指向旧路径 `.trae/issues/review.md` 的引用~~
   **（2026-09-29 已修复**：三处均已改为指向 `.trae/reviews/2026-09-24-pr13-review.md`，
   以 `tools/changelog/zh_overrides.json` 为源修改并重新生成全部四个 changelog 目标，
   `python -m tools.changelog check` 通过；同时按 d66ace9 惯例回填合并后新出现的
   8 个提交的中文摘要，缺译 112 → 104，剩余均为 v0.2.6 之前积压**）**：
   - `CHANGELOG.zh.md`（已重新生成）
   - `yate/resources/changelog.zh.md`（已重新生成）
   - `tools/changelog/zh_overrides.json`（源）
3. **同日同名章节**：原 `review.md` 中「日志/devtools 桥接评审（fix/logging-tracing-wt）— 2026-09-27」
   出现两次且标题完全相同（前者为分支评审，后者为 PR #28 AI 审查），拆分时按内容区分为
   `-devtools-bridge` 与 `-pr28-devtools-bridge` 两个文件，未合并。
