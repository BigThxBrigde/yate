# 评审记录：marks 与 jump list（issue IKUOCI）

- 日期：2026-11-16
- 分支：feature/feat-marks-jumplist（基于 master 9c304548）
- 评审者：code-review-expert（python-code-review skill）；修复轮次由 general-purpose executor 执行
- 结论：0 个阻塞项 / 0 个严重 / 6 个次要；全部修复或登记为 v2 待办

## 评审时实测的门禁（worktree venv）

- `pytest tests/ -q -n auto` -> 全绿，退出码 0
- `pytest tests/test_architecture.py -q` -> 42 passed，退出码 0
- `pyright yate/ tests/ tools/` -> 0 errors / 0 warnings / 0 informations，退出码 0
- `pytest --cov=yate --cov-branch --cov-fail-under=75 -n auto` -> 92.69%，退出码 0
- `python -m tools.smoke_test run --jobs 4` -> 124/124 场景，1511/1511 检查，退出码 0

## 发现项（逐条）

| # | 严重程度 | 位置 | 处置 |
|---|---|---|---|
| 1 | minor | marks_palette.py 中 JumpsScreen 表头与行错开 1 列 | 已修复：用 `STACK:<10` 补偿，仿照 MarksScreen 模式 |
| 2 | minor | marks_palette.py 中 LINE 从 1 起算而 COL 从 0 起算，混用 | 已修复：COL 按从 1 起算渲染 |
| 3 | minor | `_current_entry` 在 session.py 与 navigation_flows.py 中重复 | 已修复：公开 `EditorSession.current_jump_entry`，移除 flows 侧副本 |
| 4 | minor | navigation_flows.py 模块级 `log` 未使用 | 已修复：删除（最小改动形式） |
| 5 | minor | marks_palette.py 携带了仓库首个 `# pyright: ignore[reportPrivateUsage]` | 已修复：在 modals.py 中新增公开别名 `OverlayScreen`/`OverlayScroll`；移除 ignore；全仓新增抑制为零 |
| 6 | minor | 面板跳转到返回栈条目不会弹出该条目；第二次 alt-left 是无操作按键 | 已登记 v2 待办（已记录 D7 契约；可选改进：`take_*` 对当前位置去重） |
| s1 | suggestion | MarksScreen/JumpsScreen 的 on_key 交互缺少运行时测试 | 已登记 v2 待办（textual-pilot 或冒烟场景） |

## 修复后复验

- 功能测试文件：31 passed
- 全量套件 `-n auto`：全绿（7 处既有平台跳过）
- pyright：0 诊断；marks_palette.py 中 `pyright: ignore` 计数为 0；未引入新的抑制

## 备注

- 评审发现项已回写至 `.trae/documents/marks-jumplist-plans/overview.md`（偏差登记、评审表、待办清单）。
- 已记录评审者自我批评：经可达性分析撤回 2 个候选问题（chord-clear 排序不可达；modal 单线程删除路径无可达失败）。

## 第 2 轮：pr-review skill 最终检查（2026-11-16）

- 结论：APPROVE。门禁复测：pyright 0 诊断（退出码 0）；pytest 全绿（退出码 0）；覆盖率 `--cov-fail-under=75` -> 92.70%（退出码 0）；架构测试 42 项全绿；editor.py 811 行与豁免一致。
- 第 1 轮修复质量逐项复验（current_jump_entry 公开访问器、COL 从 1 起算、表头对齐、删除无用 log、OverlayScreen/OverlayScroll 公开别名、新增抑制为零）。
- 发现项：
  - [minor] marks_palette.py 覆盖率 44%，面板交互未测试 -> 已修复：新增 tests/test_marks_palette.py（6 个 pilot 测试），现覆盖率 100%（navigation_flows 89% -> 91%）。
  - [minor] vim VISUAL 模式在导航键分发后仍保持 VISUAL（锚点已清除、无高亮）-> 已登记待办 T4（与 F 键全模式先例一致；v1 未改动）。
  - [minor] JumpsScreen 光标可停留在当前行；Enter 为静默无操作 -> 已登记待办 T5（语义已在 docstring 中记录）。

## 第 3 轮：完整 pr-review 检查 + 修复迭代（2026-11-16，用户要求闭环）

- 对 `master...HEAD` 执行完整 `pr-review` skill 检查（6 笔提交，含 pilot 测试）：**APPROVE**；门禁复测：pyright 0 诊断、pytest 全绿、覆盖率 93.07%（退出码 0）。
- 新增次要项，均在提交 b49a7b4b 中修复，并由一次聚焦的后续评审收敛为 CLEAN：
  - [minor] session.py 的 docstring（`JumpList.stacks` 中有多余空格、`all_marks` 排序描述不准确）-> 已修复，仅文档改动。
  - [minor] `jump_forward` 空栈边界在 flows 层未测试 -> 已修复：`test_jump_forward_boundary_is_info_not_loop`（断言 "no later jump" 信息、光标未移动）。
  - [minor] JumpsScreen 在当前行按 Enter 静默无操作（与 T5 重叠）-> 已修复：注入 `MessageFn` 回调（PEP 695 别名，沿用 find_replace 先例），当前行按 Enter 报告 "already at latest jump" 信息，界面保持打开、光标未移动；pilot 测试已更新；marks_palette.py 覆盖率保持 100%（145 stmts / 0 miss，22 branches / 0 partial）。
- 收敛验证：注入链完整（2 处 JumpsScreen 构造点，均已接线）、语义与边界信息提示一致、ASCII 干净、架构守卫通过。最终门禁：pytest marks+arch 子集 75 passed（退出码 0）；pyright 0 诊断（退出码 0）。
- T5 状态：已通过信息提示方案闭合（行过滤变体仍为可选项，并入 v2 润色）。

## 第 4 轮：完整 pr-review 检查，合并前确认（2026-11-17）

- 范围：`master...HEAD`，7 笔提交，+3418/-5。结论：**APPROVE**。
- 门禁复测（退出码 0）：pyright 0 诊断；pytest 全绿；覆盖率 93.15%（marks_palette 100%、navigation_flows 95%）；架构测试 42 项全绿。
- 第 3 轮修复已在全分支上下文中验证（边界测试存在且全绿、MessageFn 注入链完整、docstring 准确、key-drift 守卫就位）。未引入新问题。
- 新增次要项，登记为 v2（非阻塞，依评审者建议）：
  - [minor] navigation_flows.py 有 4 个未覆盖的防御分支（closed-buffer 警告、`_on_jump_entry` 当前行双重守卫、closed-target `_go_to`）—— 界面层已拦截该双重守卫路径；可选 v2 清理：删除冗余守卫或通过 flows 层测试覆盖。
  - [minor] `JumpEntry.path` 是入栈时取的显示快照；buffer 另存后，`:jumps` 显示旧名称（uid 解析不受影响）—— v2：在渲染/`_go_to` 时通过 `doc_by_uid` 重新解析显示路径。

## 第 5 轮：T6/T7 闭合（2026-11-18，用户指定）

- 提交 46805d1a：T6 通过新增 4 个 flows 层测试闭合（jump_forward 成功路径、`_on_jump_entry` 当前行守卫、`_go_to` closed-target 警告；守卫保留而未删除）。经核实实际未覆盖集合为 3 处 / 4 条语句（closed-buffer 警告已被覆盖）。navigation_flows.py 覆盖率 95% -> 100%（117 stmts / 0 miss，32 branches / 0 partial）。
- T7 闭合：`show_jumps` 的行通过 `_display_entry` 助手构建（通过 `session.doc_by_uid` 重新解析显示路径，对已关闭 buffer 回退到快照）；`_go_to` 已仅用 uid。新增测试：另存等价状态（doc.path setter）的重解析 + 已关闭 buffer 的快照回退；断言 uid 落点不受影响。
- 修复代理复测门禁（退出码 0）：marks 测试子集、全量 pytest `-n auto`、pyright strict、全量套件覆盖率运行。观察到一次既有的无关 flake（test_diffview save-io 线程 join 超时），在复跑 + 全量复跑中重新验证为全绿。
- 剩余未闭合的 v2 待办：T1（面板跳转不弹出返回栈条目）、T3（搜索命中未入栈）、T4（导航键分发后的 VISUAL 模式语义）。
