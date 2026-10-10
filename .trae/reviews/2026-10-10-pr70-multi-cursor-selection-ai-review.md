# Gitee PR !70 AI 队友评审第三轮（multi-cursor 选区并存）— 2026-10-10

> 来源：[PR !70 评论 note 51515103](https://gitee.com/jermaine/yate/pulls/70#note_51515103_conversation_191772130)
> （AI 队友"PR观察者" `pull_review_bot_2f642dd39f557e6f`，响应 `jermaine` 的 `/review` 指令
> [note 51515102](https://gitee.com/jermaine/yate/pulls/70#note_51515102_conversation_191772130)，
> 2026-10-10 20:27:38 创建 / 20:42:18 完成，正文经 Gitee API 取回，页面不展开评论；
> 评审范围为第二轮修复（M1 重映射 + O2 提变量）合并 master `dfaebca` 后的全量 diff）。

## 一、评审结论（机器人自评）

**⛔ 发现 1 个阻断项，3 个改进项。请修改后再合并。风险等级 high
（correctness：选区与附加光标并存时多点删除使 anchor 悬空，cut/copy 可触发
IndexError）。**

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ❌ 未通过 |
| 安全性 | ✅ 通过 |
| 性能 | ✅ 通过 |
| 可维护性 | ⚠️ 待优化（3 项，见下） |

## 二、阻断项与改进项处置

| # | 级别 | 问题 | 机器人建议 | 核实结论（2026-10-10） | 处置 |
|---|---|---|---|---|---|
| M2 | 🚫 阻断 | 选区与附加光标并存时多点删除使 anchor 悬空，cut/copy 可触发 IndexError（`yate/editor_core/buffer.py` / `yate/actions.py` / `yate/flows/mouse_flows.py`）：vsc 下先 ALT+click 建点再 shift 点击建选区，selection 与 extra_cursors 并存；Backspace 走 `delete_at_points()` 列 0 并上一行分支删行但从不回写 `self.anchor`，anchor 行号越界；`cut`/`copy` 仅判 `has_selection()` 无多光标守卫，`selected_text()` 对 `self.lines[r1]` 取索引抛 IndexError | 三个多点原语入口显式清除主选区，把「选区轴与附加光标轴互斥」不变量贯穿到编辑期；补崩溃路径回归用例 | ✅ **核实属实**。`mouse_flows.py:82-84` 非 meta 的 shift+click 只 `set_cursor(select=True)` 设 anchor、不清 `extra_cursors`（并存可达）；三原语（`buffer.py:649/681/723`）区间内无任何 `self.anchor` 赋值；并行分支（`:700-711`）删行只重映射 `new_pos`；`has_selection()`（`:281`）仅比 anchor≠cursor；`selected_text()`（`:295-300`）与 `yank_selection()`（`:921-922`）均无行号 clamp；`actions.py:148/165` cut/copy 无守卫 | ✅ **已修复**（2026-10-10，commit `370bbd5`，方案 [multi-cursor-review-fixes-plan.md](../documents/multi-cursor-review-fixes-plan.md) §七）：三原语入口（`_ensure_writable` 后、`_snapshot` 前）统一 `self.anchor = None`（insert 的空文本 no-op 先行返回，不产生副作用）；新增 2 例回归用例钉住崩溃路径与三原语入口清理 |
| O3 | ⚠️ 改进 | `_remap_after_insert` docstring 末句与实际调用次序描述有歧义（`yate/editor_core/buffer.py`）："Call this *before* recording the current point's own position" 读起来像要求调用方挪动记录动作，实际重映射对象是更早迭代的记录项 | 改写末句为准确描述被重映射对象 | ✅ **核实属实**（`buffer.py:74-75` vs `insert_at_points` 循环 `:672-675`：`_apply_text` 得 recorded → remap → 写入 `new_pos[pos]`） | ✅ **已修复**（commit `5ca3b34`）：末句改为 "Remaps entries recorded by *earlier* loop iterations; the caller writes *pos*'s own entry right after." |
| O4 | ⚠️ 改进 | `actions.py` 的 `newline`/`delete_backward`/`delete_forward` 三层三元 lambda 可读性达 plan-c §五预设的切换条件；`add_cursor_below` 注册 lambda 返回 bool 与同文件其余 handler 返回 None 不一致 | 按 `cut`/`copy` 同风格落具名小函数，`add_cursor_below` 丢弃返回值 | ✅ **核实属实**（`actions.py:36-63,119-123`；plan-c 风险表原文：「若超 100 列或评审认为难读，落成模块级 `_newline(ctx)` 函数（与 `cut`/`copy` 同风格）」） | ✅ **已修复**（commit `ffd4c9a`）：populate 内具名函数 `_newline` / `_delete_backward` / `_delete_forward` / `_add_cursor_below`（与 `cut`/`copy`/`_clear_selection` 同风格），返回值统一 None |
| O5 | ⚠️ 改进 | vim 侧 `<alt-c>` help 绑定与实际分发硬编码分叉易漂移（`yate/keymaps/vim.py`）：help 条目注册了 `KeyBinding(parse_key("<alt-c>"), ...)`，真实分发在 `_handle_normal` 硬编码 `if key == "\x1bc"` 分支，后人可能误以为该条目参与 dispatch | KeyBinding 行旁补注释指明该条目仅用于帮助索引 | ✅ **核实属实**（`vim.py:171-174` vs `:458-460`） | ✅ **已修复**（commit `77e823a`）：KeyBinding 上方注明 help-only、真实分发位置与 NORMAL 静默语义 |

## 三、关联

- 修复方案：[multi-cursor-review-fixes-plan.md](../documents/multi-cursor-review-fixes-plan.md) §七
- 第二轮评审（同源，M1/O1/O2）：[2026-10-10-pr70-multi-cursor-ai-review.md](2026-10-10-pr70-multi-cursor-ai-review.md)
- 首轮内部评审（code-review-expert）：[2026-10-10-multi-cursor.md](2026-10-10-multi-cursor.md)
- 评审建议先例：#67（[2026-10-09-pr67-big-module-split-ai-review.md](2026-10-09-pr67-big-module-split-ai-review.md)）
