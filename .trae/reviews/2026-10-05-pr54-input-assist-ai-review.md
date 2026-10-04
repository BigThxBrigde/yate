# Gitee PR !54 评审（enh/input-assist 输入辅助，AI 队友审查）— 2026-10-05

> **本文登记 PR !54 的两轮 Gitee AI 队友评审**（同一 PR、同一评审者「PR观察者」）：
>
> | 轮次 | 评论 | 时间 | 结论 |
> |---|---|---|---|
> | 第二轮 | [`note_51443873`](https://gitee.com/jermaine/yate/pulls/54#note_51443873_conversation_191386654)（conversation `191386654`） | 2026-10-04 23:12:02 → 23:28:27 +08:00 | ⛔ 未通过：1 阻断 / 2 改进 |
> | 第三轮 | [`note_51445224`](https://gitee.com/jermaine/yate/pulls/54#note_51445224_conversation_191392268)（conversation `191392268`） | 2026-10-05 07:37:20 → 07:46:21 +08:00 | ⚠️ 无阻断，2 改进建议 |
>
> 第二轮的触发评论是 `note_51443872`（作者本人于 2026-10-04 23:12:01 发 `/review`）。
> 第二轮修复方案与门禁回填见
> [`../documents/input-assist-review-fixes-plan.md`](../documents/input-assist-review-fixes-plan.md) 第五节；
> 第三轮见本文第七 / 八节（§七.1 改进项 1 已由用户手动处置，§七.2 登记为 G9-3）。

- **评审对象**：分支 `enh/input-assist`（worktree `../yate-input-assist`），PR !54 标题
  `Merge branch 'master' into enh/input-assist`，评审时点 13 提交 / 13 文件；实现 issue
  **IKJMQ2**（输入辅助）。
- **这是本分支第二轮评审**：第一轮为 `.trae/skills/python-code-review` skill 审核
  （0 CRITICAL / 2 WARNING / 6 SUGGESTION，F1–F9 已于 2026-10-04 处置完毕，见
  [`input-assist-review-fixes-plan.md`](../documents/input-assist-review-fixes-plan.md) 第一节）。
  本轮为 Gitee 侧 AI 队友审查，两轮结论互不覆盖。
- **总体结论**：⛔ **未通过**——1 阻断 / 2 改进。四维表：功能性与逻辑 ❌、安全性 ✅、
  性能 ⚠️、可维护性 ⚠️；AI 队友明确「请修改后再合并」。风险等级自评 **low**。
- **处置**：**已修复**（2026-10-05，阻断项与改进项 1 采纳对齐 vim 方案，改进项 2 按
  评审者自评仅作登记）。逐条处置与门禁回填见方案文档第五节。
- **门禁实测**（worktree 沙箱，主代理亲自跑，退出码均 0）：`pyright yate/ tests/ tools/`
  → `0 errors, 0 warnings, 0 informations`；`pytest tests/test_architecture.py` → `22 passed`；
  `pytest tests/test_input_assist.py` → `63 passed`（改前 59）；`pytest tests/ --cov=yate
  --cov-fail-under=75` → `1788 passed, 30 skipped`，覆盖率 **91.27%**。

---

## 一、评论原文要点（评审表格）

| 评审规则 | 评审内容 | 评审结论 | 完成时间 |
|---|---|---|---|
| 功能性与逻辑 | 代码是否按预期执行？有无逻辑错误或未处理的边缘情况？ | ❌ 未通过 | 2026-10-04 23:28:27 |
| 安全性 | 是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？ | ✅ 通过 | 2026-10-04 23:28:27 |
| 性能 | 是否有明显的性能瓶颈？ | ⚠️ 待优化 | 2026-10-04 23:28:27 |
| 可维护性 | 代码是否清晰易读？注释是否充分？命名是否合理？ | ⚠️ 待优化 | 2026-10-04 23:28:27 |

AI 队友摘要：「⛔ 发现 1 个阻断项，2 个改进项。请修改后再合并。」

## 二、评审者列出的改动检查（7 组）

1. **新增 `yate/editor_core/indentation.py`**：`PAIRS` / `CLOSERS` 符号对表、`LanguageRules`
   数据类、`PYTHON_RULES` 与 6 个纯函数（`rules_for` / `indent_unit` / `opens_block` /
   `closes_block` / `pair_for` / `is_pair_of`），语言规则与 buffer 解耦。
2. **`yate/editor_core/buffer.py`**：`type_char(ch, *, language)` 作为 modeless 可打印字符
   唯一入口（选区包裹 → 右符号跳过 → 配对补全 → 普通插入，均以 `kind="char"` 提交保证
   单撤销步，显式 `_ensure_writable()` 拦只读）；`insert_newline(*, language)` 增 Python
   块级缩进（尾 `:` → +1 级）、扫描收敛为 2 次、修行尾空白切片越界 bug；
   `delete_backward(word=False)` 增成对删除分支（`(|)` 之间一次删两字符，守卫早于所有分支）；
   `insert_tab()` 有选区时一律走 `indent_selection()`。
3. **`yate/keymaps/base.py`**：`handle_unbound` 可打印分支由 `insert_text(key)` 改为
   `type_char(key, language=ctx.doc.filetype)`。
4. **`yate/keymaps/vim.py`**：`_handle_insert` 同样改走 `type_char`；新增模块级
   `_SHIFT_KEYS: frozenset({">", "<"})` 替换两处字面量比较；`_handle_visual` 增 `>` / `<`
   分支并清理残留 `count_str`；`_handle_normal` 增 `>` / `<` 分支（先取计数再清 pending，
   调新 `_shift_row`）；新增 `_shift_row`（两次 `set_cursor` 造整行选区后调
   `indent_selection` / `outdent_selection`，结束落在首个非空白列）；`build_bindings` 增
   两条帮助条目（EDT 类）。
5. **`yate/actions.py`**：`newline` 动作透传 `filetype`。
6. **新增 `tests/test_input_assist.py`**（911 行 / 58 条）：逐条对应 issue 8 个复现步骤，
   含 closes_block 契约、缩进单位配置与 G9 性能基准。
7. **文档**：manual 中英各增「输入辅助」小节（章节号顺延 3.5→3.9），同步 VIM / VSC
   缩进键差异说明；yaterc 中英补充 `tab_width` / `use_spaces` 与缩进单位的关联。

## 三、阻断项（1）

**B1 [功能性与逻辑] `yate/keymaps/vim.py::_shift_row` 多计数语义与 vim 不一致**

问题描述：`_shift_row` 的 `row = buf.row` 在循环外仅取一次，导致 `3>` 实际是对**当前行
重复缩进 3 级**，而非向下 3 行各缩进 1 级，与用户按 vim 直觉的预期不符。

修正建议（评审给了两条互斥路线，原文口径）：

- 若维持「当前行 ×N 级」语义，请在中英手册 3.5 节及 KeyBinding 帮助文案中将
  `[count] lines` 改为明确措辞（如「重复 N 次缩进当前行」），避免与 vim 惯例冲突；
- 若要对齐 vim 的多行语义，则需在每次迭代基于 `buf.row` 重新取行并向下一行推进。

风险自评：影响范围**仅限 NORMAL 模式下带多计数的 `>` / `<`**，单次按键与 VISUAL 模式
均不受影响。

**主代理核实（2026-10-05）**：属实。`vim.py:690-697` 循环体内 `row` 不变，每次都对同一行
调用一次 `indent_selection()` / `outdent_selection()`，即 count 次单级缩进。

## 四、改进项（2）

**M1 [可维护性] `yate/editor_core/buffer.py::delete_backward` 成对删除分支应使用 `set_cursor`**

问题描述：该分支直接赋值 `self.cursor = (r, c - 1)`，绕过 `set_cursor` 的
`_goal_col = None` 复位逻辑，与本 PR 自身在 F3 / m5 结论中确立的「统一使用 `set_cursor`」
约定不一致。

修正建议：改为 `self.set_cursor((r, c - 1))`（默认 `select=False` 会清 anchor，与此处
语义一致）。

**主代理核实（2026-10-05）**：属实。`buffer.py:548` 是第一轮 F3 遗漏的同族位置——F3 已把
`type_char` 包裹分支改成 `set_cursor`，本分支未同步。

**M2 [性能] G9 基准测的是平均值而非单次上限**

问题描述：`tests/test_input_assist.py` 的 G9 性能断言校验 1000 次按键的**平均**耗时
< 5ms，而非单次上限，个别 O(n) 尖峰可能被摊薄。

修正建议：评审者**自评无需改动**（作者已在 docstring 与计划文档 §7.2 声明这是刻意选择：
用均值兜底捕捉整体退化、阈值留足余量防 CI 抖动；实测 ~0.01ms/键，预算 5ms，余量约
500 倍）。本项目按「仅作登记」处理。

## 五、评审未覆盖但本轮修复触及的连带项

评审只点了 `_shift_row` 一处代码，但语义变更会连带以下既有事实，它们是同一决定的
组成部分，一并在此登记（详证见方案文档第五节）：

- `vim.py:151-152` 的帮助文案 `KeyBinding(">", "indent", "Indent [count] lines", EDT)` /
  `("<>", "outdent", "Outdent [count] lines", EDT)`：字面写 **lines**，与原实现的
  「当前行 ×N 级」矛盾——文案侧站的才是 vim 惯例，这是判定「实现偏差而非文档偏差」的
  关键证据；
- `input-assist-plan.md` §七 D5 记载的实测结论「`3>` = 3 级」是**实施记录**，方案
  §3.3（`:114-116`）只写「支持 `3>` 计数」，从未规定计数作用于行还是级；issue 原文
  （G6）也只写「增/减一级」，未排除多行语义；
- 手册 3.5 节缩进键表（zh `:206-207`）、5.2 节（zh `:496`）与速查表（zh `:1359`）三处
  只写「支持计数（`3>`）」，未说明计数作用于行数还是级数，属**含糊而非错误**，任何
  一条路线都需一并明确。

## 六、遗留登记（不修）

| # | 项 | 标记 | 理由 |
|---|---|---|---|
| G9-1 | VISUAL 模式下 `3>` 忽略计数前缀，与 vim（visual 中 `>` 是 operator，count 应重复缩进）仍有差异 | ⏸ 登记不修 | 评审明确将影响范围限定为 NORMAL 模式（"单次按键和 VISUAL 模式均不受影响"）；手册 3.5 / 5.2 两处表格已按 NORMAL / VISUAL 分行写明"按 vim 惯例忽略计数前缀"，测试亦 pin（`test_vim_visual_indent_does_not_leak_a_typed_count_into_normal_mode`）。改动属评审范围外的行为变更，需产品决策 |
| G9-2 | G9 性能基准取均值而非单次上限 | ⏸ 登记不修 | 评审者自评无需改动（阈值余量约 500 倍） |

---

## 七、第三轮：Gitee PR !54 第二条 AI 队友评审（note 51445224）

- **来源**：Gitee PR !54 评论
  [`note_51445224`](https://gitee.com/jermaine/yate/pulls/54#note_51445224_conversation_191392268)
  （conversation `191392268`，同为「PR观察者」），创建 2026-10-05 07:37:20 +08:00，
  最后更新 2026-10-05 07:46:21 +08:00。会话级评论，`path` / `position` / `new_line` /
  `commit_id` 均为 `null`，未锚定具体代码行。
- **总体结论**：⚠️ **无阻断项，2 个改进建议，可优化后合并**。四维表：功能性与逻辑 ✅、
  安全性 ✅、性能 ✅、可维护性 ⚠️。风险等级自评 **low**。
- **与前两轮的关系**：本轮在第二轮（B1 / M1 / M2）修复**之后**产生，
  功能侧三项（补全、跳过、包裹、删除、缩进）经代码追踪验证无误，**第二轮的阻断项
  未再出现**，评审焦点已转向 PR 范围整洁度与未接线代码。
- **本轮处置**：改进项 1 已由用户手动处置；改进项 2 登记为遗留观察项。
  按用户指示**本轮不做测试验证**（未跑 pyright / pytest / 架构测试 / 覆盖率）。

### 7.1 改进项 1（PR 范围混入无关文档）— 已由用户处置

问题描述：PR 中包含 `.trae/documents/ai-specs/add-ai-chat-agent/` 下的
`spec.md` / `tasks.md` / `checklist.md`，描述的是一个**尚未实现**、与 input-assist
主题完全无关的 AI Chat/Agent 特性；混合提交会稀释提交历史清晰度并增加评审噪音。

修正建议（原评）：拆分到独立 PR 或分支，保持当前 PR 专注 input-assist。

**处置（2026-10-05，用户手动执行）**：三个文档已删除，提交 `6937900`
（`docs: remove irrelevant docs`）。主代理核实：worktree 内该目录已不存在，
`git log --diff-filter=D` 确认删除即在 `6937900`。按用户指示，此项**不作为待办登记**。

### 7.2 改进项 2（`closes_block` 未接入产品路径）— 登记为遗留观察项

问题描述：`closes_block` 已在 `yate/editor_core/indentation.py` 实现并有完整契约测试，
但**产品路径从不调用**，仅作为预留扩展接缝存在；长期保留未使用代码可能增加维护负担。

修正建议（原评）：**认可**保留为扩展接缝的裁决，但建议后续版本若长期不接线，
需评估移除或明确标记为实验性。

**主代理核实（2026-10-05，只读取证）**：属实。`closes_block` 全仓 5 处命中——
`indentation.py:118`（定义）、`:61`（`LanguageRules` 注释说明其剥离尾随冒号）、
`tests/test_input_assist.py:29`（import）与 `:871-900`（契约测试
`test_closes_block_matches_the_python_dedent_keywords`，12 组断言）。**产品路径
（`buffer.py` / `keymaps/*` / `actions.py`）零调用**，与
[`../documents/input-assist-plan.md`](../documents/input-assist-plan.md) §七 **D2** 的
裁决一致——保留为未接线的扩展点，由契约测试直接定契约，docstring 已写明"本版未接线"。

**登记为遗留观察项 G9-3**（见 §八），理由：接线与否属产品功能决策（语法级回退缩进是
issue IKJMQ2 明确列出的"V1 可选、暂不实现"非目标），不是评审要求当场修的缺陷；
评审本身也认可保留裁决，仅建议后续版本复评。

### 7.3 事实注记

评审正文称"新增了 58 条验收测试用例 `tests/test_input_assist.py`"——该数字对应
**第二轮修复前**的文件状态（第一轮 F1–F9 处置后即为 59 条）。当前分支经第二轮修复后
为 **63 条**（+4：末行截断 / 撤销单步 / 反缩进下限 / 孤立空行）。此处仅作快照差异
说明，不构成对评审的异议。

## 八、遗留登记（第三轮新增）

| # | 项 | 标记 | 理由 |
|---|---|---|---|
| G9-3 | `closes_block` 已实现且有契约测试，但产品路径零调用，作为"未来语法级回退缩进"的扩展接缝长期未接线 | 👀 登记待复评 | 评审**认可**保留裁决（§七.2），仅建议后续版本若长期不接线则评估移除或标记为实验性。接线与否属产品功能决策（语法级回退缩进是 issue IKJMQ2 明确列出的"V1 可选、暂不实现"非目标），不由评审驱动；docstring 已写明"本版未接线" |
