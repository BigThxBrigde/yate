# yate Code Review — Gitee PR #35 评审（vim 键位保真分支）— 2026-09-29

## Gitee PR #35 评审（vim 键位保真分支）— 2026-09-29

> **范围**：PR #35 `review/vim-keymap` → `master`（vim 键位保真批次：
> w/b/$/G motion 边界、e/word_end_column 重写、textobjects 扩展等）。
> 本次登记 **Gitee AI 队友审查**（[原始评论](https://gitee.com/jermaine/yate/pulls/35#note_51401700_conversation_191134324)）：
> 结论 **1 个阻断项 + 3 个改进建议**；阻断项风险 **high**（功能性与逻辑）。
> 修复方案与执行记录见
> [vim-keymap-review-plan.md §三 PR35 批次](../documents/vim-keymap-review-plan.md)。

### AI 发现逐条登记与处置

- [x] **阻断项：operator 排他端点未钳制可致缓冲区数据损坏（功能性与逻辑，high）** —
  [`vim.py`](../../yate/keymaps/vim.py) `_resolve_find` forward 分支以
  `target[1] + 1` 构造半开端点、`_apply_text_object` 直接透传 `span[1]`，
  两者均未钳制；`_apply_span` 经 `buf.cursor = end` 直赋值绕过 `set_cursor`
  钳制，而 `TextBuffer._delete_range` 多行删除用 `lines[r1][:c1] + lines[r2][c2:]`
  拼接——`c2 > len(lines[r2])` 时切片为空，后段文本被静默吞掉。
  *取证（2026-09-29）：具体越界路径经公开行为**不可达**——forward `find_char`
  返回值受 `i < len(line)` 约束，`target[1] + 1 <= len(line)` 恒成立（EOL 命中时
  恰为 `len`，合法）；`_word_span` 的 end 循环均以 `end < len(line)` 为界，
  文本对象跨度不可能超界。但多调用点各自做 `+1`/透传算术，端点合法性靠调用方
  自律，钳制 `_apply_span` 入口是正确的单点防御，**采纳修复**：入口对
  `end` 列做 `min(ec, len(lines[er]))` 钳制（`ec == len` 合法保留——半开排他
  端点删到行尾是既有语义；评审者建议的 `min(ec, len+1)` 不采纳，`len+1` 对
  半开端点无意义且会重新引入越界）。顺带发现并修正 `_apply_span` docstring
  写 "(inclusive)" 与实际半开语义不符。*

- [x] **改进项 1：operator 状态清理在 6 处重复（可维护性）** —
  `op` / `obj_scope` / `op_count` 三连重置散布于
  `_linewise_op` / `_resolve_gg` / `_resolve_find` / `_apply_operator` /
  `_apply_text_object` / r 键取消分支，漂移风险高。
  *✅ 采纳修复——提取 `_clear_operator()` helper 统一三连重置，
  `_clear_pending` 复用之。*

- [x] **改进项 2：`word_end_column(lines[r], -1)` 负数哨兵耦合脆弱（功能性与逻辑）** —
  [`vim.py`](../../yate/keymaps/vim.py) e 分支跨行 wrap 扫描以 `col=-1`
  依赖 `range` 对负数起始的隐式行为（`range(0, n)`）实现"从行首扫"，意图不明。
  *✅ 采纳修复——`word_end_column` 增加关键字参数 `from_start: bool = False`
  显式表达"从列 0 起扫"，调用点改为
  `word_end_column(buf.lines[r], 0, from_start=True)`，行为不变。*

- [x] **改进项 3：配对/标签扫描无搜索半径上限（性能）** —
  [`textobjects.py`](../../yate/editor_core/textobjects.py)
  `_unmatched_backward` / `_matching_forward` / `_enclosing_tag` 全量扫描
  无上限，UI 主线程极端输入可能卡顿；AI 建议可选 `max_lines` 兜底。
  *⛔ won't-fix——与已批准的偏离记录 #8
  （[vim-keymap-review-motion-fixes-plan.md §五](../documents/vim-keymap-review-motion-fixes-plan.md)）
  直接冲突：该记录明确**取消 ±200 行搜索半径**、确立全量扫描语义（正确性优先，
  截断会让深层嵌套配对静默失配）。为兜底一个已被有意放弃的限制重新加参数，
  且默认不启用，属过度设计。极端输入卡顿若实际发生，应作为独立问题重新评估。*
