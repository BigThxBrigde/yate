# plan-d — 行跳转推入接线（goto_line 调 push_jump）+ 集成测试（wave-2）

父文档：[overview.md](overview.md)。输入：F7；设计决策 D2/D4。
前置：wave-1 plan-a（`push_jump` 契约存在）。与 plan-c 文件零重叠，可并行。

## 目标与非目标

- 目标：`PromptFlows.goto_line`（`:42` 与 ctrl-g 的唯一落点）在移动光标前调
  `session.push_jump()`，使行跳转产生历史条目（AC3），alt-left 可回退。
- 非目标：搜索命中推入（D4 定稿：v1 不推，未来只需一行）；标记跳转推入
  （plan-c 的 `jump_to_mark` 已含）。

## 独占文件清单

- `yate/flows/prompt_flows.py`
- `tests/test_marks_integration.py`（新建）

## 具体修改（定位到行号）

- `yate/flows/prompt_flows.py` `goto_line`（L291-308）：在 `buf.anchor = None`
  （L300）**之前**插入一行：

```python
        self.session.push_jump()
```

- 放置语义：`push_jump` 默认捕获**当前**光标（跳转源），随后 goto_line 才把
  光标移到目标行——顺序不可颠倒（AC3"alt-left 可回退到跳转前位置"）。
- 去重语义：连续 `:42` 跳到同一行时 `JumpList.push` 丢弃重复条目
  （plan-a 语义），不产生噪音。
- `:+5`/`:-3` 相对跳转与 ctrl-g（`_jump_to_line` 类调用方）都汇入
  `goto_line`，单一注入点全覆盖（F7）。

## 新增测试（tests/test_marks_integration.py）

fixture：真实 `EditorSession` + 手工 `Document`（20 行文本）+ stub
panes/prompt/message/refresh，构造 `PromptFlows`（构造签名按 L157-175 现状）。

| 用例 | 前置/操作/断言 |
|---|---|
| `test_goto_line_pushes_jump_before_moving` | 光标 (0,0) → goto_line(15) → `jumps.stacks()[0][-1]` 为 `(uid, path, 0, 0)` 且光标 row=14（0-based：目标 15 → row 14） |
| `test_goto_line_same_position_dedups` | goto_line(15) 连续两次 → back 长 1 |
| `test_goto_line_two_targets_two_entries` | goto_line(5) → goto_line(10) → back 长 2、`jump_back()` 回 row=4 |
| `test_relative_goto_pushes_history` | goto_line("+5") → back 长 1 且光标前进 5 行 |
| `test_goto_line_out_of_range_still_clamps_and_records` | goto_line(999) → clamp 到末行、back 有条目（记录的是跳转前位置，与 clamp 无关） |

反向覆盖：`test_jump_back_after_goto_returns_to_previous_line`（goto 两行 →
alt-left 模拟：session.jump_back() → 光标回原行）。

## 验证方案与验收命令

- 验证目标：AC3 前半（行跳转产生历史条目、指针一致）；契约单一性
  （goto_line 只调 `push_jump`，不触栈内部）。

```powershell
.venv\Scripts\python.exe -m pytest tests/test_marks_integration.py -q
.venv\Scripts\python.exe -m pytest tests/test_prompt_flows.py -q
.venv\Scripts\python.exe -m pyright yate/flows/prompt_flows.py tests/test_marks_integration.py
```

- 通过判定：三条命令退出码 0（既有 prompt_flows 回归不红）。

## 风险与回滚

- 风险1：goto_line 有多个调用路径遗漏语义（如 ctrl-g 不想推入）→ ctrl-g 与
  `:42` 共用 goto_line，issue 将两者都列为推入点，统一推入正确。
- 风险2：prompt_flows 构造签名将来变化 → 测试 fixture 以关键字参数构造，
  偏差在实施时对齐现状签名（以 L157-175 为锚）。
- 回滚：`git checkout -- yate/flows/prompt_flows.py` + 删除
  `tests/test_marks_integration.py`；单文件回滚，无连带。
