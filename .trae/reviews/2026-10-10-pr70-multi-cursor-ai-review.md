# Gitee PR !70 AI 队友评审第二轮（multi-cursor）— 2026-10-10

> 来源：[PR !70 评论 note 51507419](https://gitee.com/jermaine/yate/pulls/70#note_51507419_conversation_191719613)
> （AI 队友"PR观察者" `pull_review_bot_2f642dd39f557e6f`，响应 `jermaine` 的 `/review` 指令
> [note 51507416](https://gitee.com/jermaine/yate/pulls/70#note_51507416_conversation_191719613)，
> 2026-10-10 13:57:01 创建 / 14:01:11 完成，正文经 Gitee API 取回，页面不展开评论；
> PR !70 即 worktree 分支 `feat/multi-cursor`，标题
> `docs(plan): backfill the multi-cursor execution record`）。
> 评审对象：基于 `TextBuffer.extra_cursors` 的多光标模式（列模式分支废弃后重新设计：
> buffer 多点插入/删除原语、vim/vsc 键位接入、editor_view 多点渲染与 `V-COLUMN` 提示）。
> 机器人确认首轮评审的 W-1/W-2 已在 diff 中修复。

## 一、评审结论（机器人自评）

**⛔ 发现 1 个阻断项，2 个改进项，请修改后再合并。风险等级 high
（多点回车或跨行删除后附加光标停在错误行，破坏多光标协同编辑核心可用性）。**

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ❌ 未通过 |
| 安全性 | ✅ 通过 |
| 性能 | ✅ 通过 |
| 可维护性 | ⚠️ 待优化（2 项，见下） |

## 二、阻断项与改进项处置

| # | 级别 | 问题 | 机器人建议 | 处置 |
|---|---|---|---|---|
| M1 | 🚫 阻断 | 多点原语在行数变化后未重映射已记录位置，附加光标漂移（`yate/editor_core/buffer.py`）：`insert_at_points` / `delete_at_points` / `delete_forward_at_points` 降序处理保护了未处理的源位置，但已记录的 `new_pos` 不随后续上方行的插行/并做行号平移。三点 `(0,0)(1,0)(2,0)` 执行 `insert_at_points("\n")` 后内容正确变为 `["",A,"",B,"",C]`，主光标 `(1,0)`，附加光标被回写为 `(2,0)(3,0)`，正确应为 `(3,0)(5,0)` | 每次行数变化的操作后对已记录位置统一重映射（插入下移、删除上移），并补钉住坐标的测试 | 🔧 **修复**（2026-10-10，方案 [multi-cursor-review-fixes-plan.md](../documents/multi-cursor-review-fixes-plan.md)）。核实属实，且实测漂移不止跨行：同行的后续退格/前删同样使已记录列号失效（机器人给的 `_shift_recorded` 只平行号不够），方案扩展为行、列联合重映射 |
| O1 | ⚠️ 改进 | `add_cursor_below` 未做去重检查，与 `add_cursor_at` 语义不一致（`yate/editor_core/buffer.py`）：下一行较短、列号夹取后可能撞上已存在的附加点，产生重复点 | 追加前检查 `point in self.extra_cursors or point == self.cursor`，保持语义一致 | 🔍 **核实不成立，不改行为**（2026-10-10）。结构性证明：`add_cursor_below` 以 `_multi_points()` 的最大点（最低行）为基准，目标行 = 最低行 + 1，严格大于全部现存点（含主光标）的行号，重复在结构上不可达；加了也属永不触发的死分支（还会成为分支覆盖永久空洞）。处置：docstring 注明该不变量 |
| O2 | ⚠️ 改进 | `mouse_flows._on_down` 中条件表达式重复计算（`yate/flows/mouse_flows.py`）：`event.meta and not isinstance(keymap, VimKeymap)` 在分支条件与 `_dragging` 赋值处各出现一次 | 提取局部变量 `adds_point` | 🔧 **修复**（2026-10-10，同上方案）：提取局部变量，行为零变化 |

## 三、关联

- 修复方案：[multi-cursor-review-fixes-plan.md](../documents/multi-cursor-review-fixes-plan.md)
- 首轮内部评审（code-review-expert）：[2026-10-10-multi-cursor.md](2026-10-10-multi-cursor.md)
- 评审建议先例：#67（同源 AI 队友评审，见 [2026-10-09-pr67-big-module-split-ai-review.md](2026-10-09-pr67-big-module-split-ai-review.md)）。
