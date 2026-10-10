# 评审记录：多光标任务（issue IKKJHH）

- 日期：2026-10-10
- 评审者：code-review-expert（python-code-review skill 工具在本环境不可用，按角色剧本内置的 6 维度评审 + 三级严重等级框架执行）
- 范围：分支 feat/multi-cursor，基线 master 5d0c9ea，git diff 5d0c9ea..HEAD 共 6 提交（85b5079 - 7ca2c87，+2578/-39）
- 方案总纲：[.trae/documents/multi-cursor-plans/overview.md](../documents/multi-cursor-plans/overview.md)（其 §六采纳/排除清单为红线）
- 规范来源：.trae/rules/architecture-boundaries.md（R1-R13）、python-coding-style.md、doc-conventions.md

## 结论

无 blocker（CRITICAL）；2 个 major（WARNING，W-1/W-2）建议合并前处理；其余为 minor（SUGGESTION）。产品代码正确性、架构红线、全部门禁实测达标。

### 门禁实测（评审者亲自重跑，非引用自述数字）

| 命令 | 结果 | 退出码 |
|---|---|---|
| pyright yate/ tests/ tools/ | 0 errors, 0 warnings, 0 informations | 0 |
| pytest tests/ -q（后台落盘重跑，收集 2107 例） | 全绿 | 0 |
| pytest tests/test_architecture.py -q | 28 passed | 0 |
| pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 | TOTAL 91%（分支模式，阈值 75 达标） | 0 |
| tools.smoke_test run --no-color --fail-only | 109/109 场景、1323/1323 checks（含新场景 vim_multi_cursor_ops / vsc_multi_cursor_mouse） | 0 |

注 1：pytest 后台重定向的摘要行未落盘（进度行到 100% 即止），以退出码 0 为准；首次前台运行在收集序第 44 位出现 1 个 F，定位为 tests/test_app_explorer.py::test_new_file_and_folder_from_explorer（本分支未触碰的 Textual pilot 时序型用例），复跑全绿，判定环境偶发，与本分支无关。
注 2：新改文件覆盖明细：buffer.py 98%（缺行 457-458 为存量 type_char 分支；640/669-671/696 见 W-2）、mouse_flows.py 90%、statusbar.py 94%、actions.py 98%。

## 执行者登记偏离的核实（全部属实）

1. plan-b 断言笔误修正：plan §四原断言 lines[1][:4] == gamX 与实现行为（gamma delta 列 2 插 X 得 gaXmma delta）矛盾，执行者修正为 lines[1][:3] == gaX（tests/test_vim_keymap.py:714-715）。属实。
2. 方向键不清点裁决：plan-b §3.2.5 文本两可（入口处清点 vs 括注方向键属原操作）；执行者取不清点，与总纲 §二『方向键保持原操作（只动主光标）』一致，且有测试钉住（test_motion_keeps_extra_cursors_and_moves_primary_only；vim.py _handle_insert 的 _ARROW 分支注明保点）。属实。
3. plan-c _on_down 次序：与 plan §3.2 代码块逐行一致（pos 判 None 提前返回、vim 判型在 meta 分支之前）。属实。
4. clear_selection action 双语义：plan-c §3.1.5 原样落地（actions.py 模块级 _clear_selection 先清点再清选区，action 注册名不变）。属实。
5. plan-e 手册路径：计划写 yate/docs/manual.*.md 为笔误，实际 yate/resources/manual.*.md；双语成对新增、章节结构对齐。属实。

## 总纲 §六红线逐条核对（全部通过）

| 红线 | 结论 | 证据 |
|---|---|---|
| 无块选模型全套（block 标志 / begin_block_selection / block_region / selected_block_text / yank_block / delete_block / insert_block / replace_block） | 通过 | git diff 全量 grep：关键字仅出现在 .trae/documents 方案文本，零代码命中 |
| 无 VimMode.VISUAL_BLOCK / Ctrl+V 入口 | 通过 | vim.py 枚举与绑定表未引入 |
| 无 alt+shift 管道移植（select_block_* / _MOD_ARROWS 补行 / parse_key 组合分支） | 通过 | 同上，零代码命中 |
| type_char 未动 | 通过 | buffer.py diff 仅 _apply_text 签名适配的 3 处调用点（:475/:487/:492），配对/跳过/wrap 逻辑逐行未变 |
| 鼠标 Alt 走 event.meta 通道 | 通过 | mouse_flows.py _on_down 判 event.meta and not isinstance(keymap, VimKeymap)；未使用不存在的 event.alt |
| R4：keymaps 无 editor_view 导入 | 通过 | keymaps/* 导入面仅 editor_core / session / keymaps 内部 / services.clipboard |
| R13：无 .styles 直改新增 | 通过 | statusbar 的 self.styles.background 为存量行（L2 组件自持，合规）；editor.py 无样式写点 |
| R10 / R11 / R12：无新派发点、mouse_flows 冻结导入面未扩、日志惰性百分号 | 通过 | buffer.py 新增 log.debug 均为惰性 % 占位（:643/:662/:690）；架构 28 用例全绿背书 |
| 架构守卫 28 用例 | 通过 | 实测 28 passed，退出码 0 |
| 规划先行（plan-before-execute） | 通过 | 5 个子计划 + 总纲齐备，波次纪律与独占文件清单在 diff 中得到遵守（无跨计划文件越界） |

## 发现清单（按严重度排序）

### W-1 [WARNING] plan-d 提交误删既有测试的收尾断言（合并前必须修复）

- 位置：tests/test_app_render.py:337-340（引入提交 4ebbe8f，git log -S 定位）
- 问题：test_doc_search_enter_flushes_pending_query_immediately（S40：enter 立即 flush 搜索）的末尾三行——await pilot.press(enter) / await pilot.pause() / assert calls == [key]——在插入新渲染用例时被整块删除，函数在 pilot.press(k, e, y) 后直接 asyncio.run 收尾。测试仍通过但空转：既不提交查询也不断言，S40 回归语义静默丢失。
- 建议：恢复三行断言；今后向既有测试文件插入新用例时，diff 不得触碰既有函数体。

### W-2 [WARNING] 新增多点原语的两个行为分支零测试覆盖

- 位置：yate/editor_core/buffer.py:669-671（delete_at_points 列 0 合并上一行分支）、:696（delete_forward_at_points 文档末行 no-op 分支）、:640（insert_at_points 空 text 卫语句，trivial）
- 问题：分支覆盖实测未覆盖（cov-report term-missing）。其中 669-671 是 docstring 明文承诺的行为（At column 0 the point joins the previous row），属多点退格的核心路径，却无任何用例（既有用例点均在列 ≥1）；696 是末行 forward-delete no-op。总量 91% 的覆盖率门禁掩盖了这两处新代码缺口。
- 建议：补 2 个用例：其一，点在 (r, 0)（r 大于 0）加另一行点，退格后行合并且一次 undo 复原；其二，点在文档末行行尾，forward delete 无操作。plan-a §四用例表本身也漏了这两格，属方案级缺口，建议回填 plan-a。

### S-1 [SUGGESTION] add_cursor_at 不拒绝与主光标重合的点

- 位置：yate/editor_core/buffer.py:296-308
- 问题：重复判定只查 extra_cursors，不查 self.cursor。ALT+click 点在主光标原位会加入冗余点：has_extra_cursors() 为 True 导致状态栏显示 V-COLUMN 但等效单光标；渲染层 editor_view/editor.py:385-390 行尾补位可能主光标一格加附加点一格双重追加。编辑路径经 _multi_points（:612-626）去重自愈，无正确性风险。
- 建议：add_cursor_at 对等于主光标的位置也返回 False，或渲染前归一化。

### S-2 [SUGGESTION] _restore clamp 可能产生重复点

- 位置：yate/editor_core/buffer.py:191-198
- 问题：undo 恢复时逐点 clamp 不去重，两个不同点可能被夹到同一位置，出现与 S-1 相同的渲染与 chip 语义失真。
- 建议：恢复循环内做 not-in 去重。

### S-3 [SUGGESTION] vim 模式下 ALT+点击不清附加点

- 位置：yate/flows/mouse_flows.py _on_down else 分支
- 问题：vim 模式 meta+click 落 else 分支，not event.meta 为 False，不清点——vim 下普通点击清点、ALT+点击保留点集，两种点击行为不一致。设计上 vim 不接鼠标多光标（plan-b §3.2.6），此缝隙 plan 未覆盖。
- 建议：补注释说明，或让 vim 模式 meta+click 同样走清点路径。

### S-4 [SUGGESTION] vim 与 vsc 对 Delete 键的多点语义不一致

- 位置：yate/keymaps/vim.py _handle_insert（\x1b[3~ 分支先 _exit_multi 再单点删除）vs yate/actions.py delete_forward 多点分支（vsc Delete 走 delete_forward_at_points）
- 问题：两个键位各自符合 plan-b / plan-c 的规定，但跨键位行为不一致（vim 的 Delete 退点多光标、vsc 的 Delete 多点删除），总纲 §二与手册的已知限制均未登记该差异。
- 建议：在手册已知限制补一句，或后续任务对齐。

### S-5 [SUGGESTION] 冒烟场景 docstring 与 tags 不符

- 位置：tools/smoke_test/scenarios/multi_cursor.py:1（docstring 写 tags 为 edit 与 select）与 :1039（vsc_multi_cursor_mouse 只注册 edit）
- 建议：对齐其一。

## 亮点（正面确认）

- 多点原语的降序 (row, col) 处理 + 去重设计正确，含换行插入、同行两点、相邻点退格、(0,0) no-op 等尖锐场景均有用例钉住（test_editor_core.py TestMultiCursor 16 例）；
- undo 快照扩展用带默认值字段（extra_cursors: tuple[Pos, ...] = ()），既有位置构造零破坏，no-op 判定与 char 合并语义随快照自动扩展；
- _delete_range 去掉 cursor 副作用的重构按 plan-a §3.3 逐调用点核对无遗漏（insert_text / replace_range / type_char / cut_selection / delete_to_line_start 全部显式回写），全量回归背书；
- 键位清点规则覆盖 plan-b 列出的全部分支（x / p / P / u / ctrl-r / J / 翻页 / d y c / v V / o O / 大小缩进 / ? : n N），_exit_multi helper 避免 13 处重复；
- 冒烟场景以用户路径进出（:vim / :vsc）并恢复键位状态，符合 harness 不变量清扫要求；
- 提交信息符合 git-commit-message.md 约定（type(scope): 摘要 + 正文），每波独立 commit 可单独 revert。

## 严重等级对照

按 python-code-review skill 的三级标记：本报告 W- = [WARNING]（旧 major），S- = [SUGGESTION]（旧 minor）；本次无 [CRITICAL]（旧 blocker）。
