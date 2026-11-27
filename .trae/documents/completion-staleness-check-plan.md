# 补全陈旧性检查修复计划

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
>
> - `yate/app_features/completion.py` 已有 `_current_prefix()` 辅助；两条路径
>   （buffer-based 与 LSP）的陈旧守卫同时比较 `buf.row`、当前列与前缀文本
>   （`buf.col != cur_col or cur_prefix != prefix`），不再只看 row。
> - `accept()` 已改为按行列范围判定（等价于 `row < r0 or row > r1`），
>   评审指出的 `row != r0 or row != r1` 逻辑错误不存在。
> - 本文档保留为设计记录（含根因分析与备选方案）。

## 摘要

`yate/app_features/completion.py` 中的补全弹出窗口陈旧性检查在 LSP `await` 返回后只比较行（`buf.row != row`），却忽略了列位置。如果用户在 LSP 请求进行期间继续在同一行输入，陈旧的补全仍会显示。当用户接受其中一个陈旧项时，`replace_range` 会使用过时的坐标，可能因替换错误的区间而破坏文本。本计划通过同时检查列和前缀文本来强化陈旧性守卫。

## 当前状态分析

### 文件：`yate/app_features/completion.py`

#### 1. 陈旧性检查 —— 基于 buffer 的路径（第 117–123 行）

```python
if (
    not app.mounted
    or app.doc is not doc
    or buf.row != row
    or not popup.is_mounted
):
    return
```

只比较行。同一行上的列变化会被放过。

#### 2. 陈旧性检查 —— LSP 路径（第 156–163 行）

```python
if (
    not app.mounted
    or app.doc is not doc
    or buf.row != row
    or not popup.is_mounted
):
    return
```

同样的缺陷 —— 在 `await app.lsp.request_completion(...)` 之后只比较了行。

#### 3. `_worker` 开始时的捕获（第 98–104 行）

```python
row, col = buf.row, buf.col
line = buf.lines[row] if row < buf.line_count else ""
col = min(col, len(line))
i = col
while i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
    i -= 1
prefix = line[i:col]
```

`col` 和 `prefix` 都已被捕获并可用于比较 —— 只是没有在陈旧性检查中使用。

#### 4. Accept 方法 —— 现有守卫（第 202–219 行）

```python
row, col = buf.row, buf.col
if item.has_range():
    r0 = item.range_start_row or 0
    c0 = item.range_start_col or 0
    r1 = item.range_end_row or 0
    c1 = item.range_end_col or 0
    if row == r1 and col >= c1:
        c1 = col   # extend range forward if cursor moved right
    if (row, col) < (r0, c0) or (r0, c0) > (r1, c1):
        return     # discard if cursor moved away
    start, end = (r0, c0), (r1, c1)
else:
    i = col
    line = buf.lines[row]
    while i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
        i -= 1
    start, end = (row, i), (row, col)
buf.replace_range(start, end, item.insert_text)
```

`accept` 方法已有防御性的范围检查，但当光标位于原始范围*前方*时它仍允许替换（`if row == r1 and col >= c1: c1 = col` 将替换向前扩展）。这对基于 buffer 的补全来说是安全的，但当行未改变而列已经越过补全所对应的位置时，它不足以防止陈旧项破坏文本。

### 根因

`_worker` 协程在 await LSP 之前捕获 `row` 和 `col`（第 98 行）以及 `prefix`（第 104 行）。第 120 行和第 160 行的陈旧性检查只重新检查 `row`。`col` 和 `prefix` 从未被重新比较。因此：

- 用户输入 `"pr"` → 防抖 → `_worker` 启动，捕获 `row=5, col=7, prefix="pr"`
- 用户继续输入 `"pri"`（3 个字符）→ 防抖定时器重新调度；但第一个 `_worker` 仍在 `await` LSP
- LSP 响应；`buf.row` 仍是 5（检查通过），`buf.col` 现在是 8 或 9（未检查）
- 显示陈旧的补全；接受其中一个会将范围 `(5, 4)-(5, 7)`（过时）替换为补全文本

## 提议的修改

### 修改 1：强化基于 buffer 的补全路径中的陈旧性检查
**文件：** `yate/app_features/completion.py`  
**位置：** 第 117–123 行  
**内容：** 在守卫中加入 `buf.col != col`，并验证当前前缀仍与最初捕获的前缀匹配。  
**方式：** 将现有条件替换为：

```python
# Recompute prefix at current cursor position
cur_line = buf.lines[row] if row < buf.line_count else ""
cur_col = min(buf.col, len(cur_line))
j = cur_col
while j > 0 and (cur_line[j - 1].isalnum() or cur_line[j - 1] == "_"):
    j -= 1
cur_prefix = cur_line[j:cur_col]

if (
    not app.mounted
    or app.doc is not doc
    or buf.row != row
    or buf.col != col
    or cur_prefix != prefix
    or not popup.is_mounted
):
    return
```

**原因：** 比较 `col` 是一种廉价而直接的守卫。比较前缀文本更稳健 —— 它能捕获用户*删除*字符、在同一前缀内移动光标或粘贴内容的情况。它还能防范在不改变行号的情况下改变行长度的静默 buffer 编辑。

### 修改 2：强化 LSP 补全路径中的陈旧性检查
**文件：** `yate/app_features/completion.py`  
**位置：** 第 156–163 行  
**内容：** 与上面相同的修改 —— 加入列比较和前缀文本比较。  
**方式：** 将现有条件替换为与修改 1 相同的逻辑。  
**原因：** 与修改 1 的理由相同。这是 issue 中引用的主要位置。

### 修改 3：抽取辅助方法（可选但推荐）
**文件：** `yate/app_features/completion.py`  
**内容：** 将"计算位置处前缀"的逻辑抽取到一个小的辅助方法中，避免在两处检查点重复。  
**方式：** 在 `CompletionController` 上添加一个私有辅助方法：

```python
def _current_prefix(self, buf: "TextBuffer", row: int) -> tuple[str, int]:
    line = buf.lines[row] if row < buf.line_count else ""
    col = min(buf.col, len(line))
    i = col
    while i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
        i -= 1
    return line[i:col], col
```

然后两处检查点变为：

```python
cur_prefix, cur_col = self._current_prefix(buf, row)
if (
    not app.mounted
    or app.doc is not doc
    or buf.row != row
    or buf.col != cur_col
    or cur_prefix != prefix
    or not popup.is_mounted
):
    return
```

**原因：** DRY —— 前缀重算逻辑与 `_worker` 在第 99–104 行以及 `accept` 在第 216–218 行所做的相同。单一辅助方法降低了漂移风险。

### 修改 4：让 `accept` 拒绝明显陈旧的补全
**文件：** `yate/app_features/completion.py`  
**位置：** `accept()` 方法，在 `popup.close()` 之后、`buf.replace_range(...)` 之前  
**内容：** 关闭弹出窗口后，*再次*捕获当前行/列（它们可能在弹出窗口被接受与替换之间发生了移动），并在执行范围替换前验证它们仍在预期的行上。  
**方式：** 插入一个守卫：

```python
# Popup-close may have been followed by another keystroke; re-capture.
cur_row, cur_col = buf.row, buf.col
if item.has_range():
    r0 = item.range_start_row or 0
    ...
    if cur_row != r1:
        return  # cursor left the row the completion was for
    ...
```

**原因：** 关闭弹出窗口会消耗一次按键（Enter/Tab），但在弹出窗口被选中与 `accept()` 被调用之间，编辑器可能已处理了额外的按键。最后的行检查可防止跨行破坏。

## 假设与决策

1. **行是主要守卫，列是次要守卫。** 如果行发生变化，补全显然已陈旧。列/前缀检查用于捕获同一行的情况。

2. **前缀文本比较比单纯列比较更稳健。** 如果用户输入的字符超出原始前缀（`"pr"` → `"priority"`），当前前缀会变长；比较完整前缀可以捕获这种情况。如果用户回删到原始前缀之前，前缀会缩短；这同样会被捕获。单纯的列比较无法可靠地捕获删除或粘贴场景。

3. **`_current_prefix` 辅助方法与 worker 的前缀定义保持一致。** worker 使用 `isalnum() or "_"` 作为前缀边界。该辅助方法必须使用相同的定义，而不是 `buffer_completions._ident_prefix`（后者为路径补全还包含 `/`、`\`、`~` —— 这是一个略宽的定义，仅用于文件系统路径检测，而非通用的 LSP/弹出窗口守卫）。

4. **不更改防抖 / worker 独占模型。** `run_worker` 上现有的 `exclusive=True` 会串行化 LSP 补全 worker；陈旧性检查是针对一个 worker 完成而下一个 worker 正等待运行这种情况的深度防御。

5. **不更改 `editor_view/completion.py` 中的 `buffer_completions`。** 那里的补全项已带有精确的 `range_start_row/col/end_row/end_col` 值。问题不在于范围如何计算，而在于何时被接受。

## 验证步骤

### 单元 / 集成测试
1. 运行现有的补全测试：
   - `pytest tests/test_app_textual.py -k completion -v`
   - `pytest tests/test_lsp.py -k completion -v`
2. 为陈旧性场景添加一个针对性测试：
   - 打开一个文档，模拟一个耗时 >200 ms 的 LSP 补全响应
   - 输入 `"pr"` → 触发补全请求
   - 在 LSP 响应之前立即在同一行输入更多字符
   - 断言弹出窗口没有出现（或立即关闭）
3. 为接受路径守卫添加一个针对性测试：
   - 模拟一个补全，显示弹出窗口，将光标移到另一行，接受
   - 断言 `replace_range` 未被调用（无文本破坏）

### 手动（Textual 试点）验证
1. 打开一个 Python 文件，触发一次缓慢的 LSP 补全（例如在一个大型项目中使用 `pylsp` 输入 `"im"`）
2. 在等待弹出窗口时，快速输入更多字符
3. 等待 —— 验证弹出窗口没有出现，或者如果它短暂出现，显示的是更新后的补全
4. 测试删除：输入 `"import o"` → 补全 → 回删到 `"import"` → 验证弹出窗口更新

### 需确认的边界情况
- 用户在 await 期间在同一行将光标**向左**移动（删除字符）→ 陈旧守卫应关闭弹出窗口
- 用户在 await 期间在同一行将光标**向右**移动（添加字符）→ 陈旧守卫应关闭弹出窗口
- 用户在 await 期间切换到另一个标签页 → 现有的 `app.doc is not doc` 检查已覆盖此情况
- 用户在 await 期间移动到另一行 → 现有的 `buf.row != row` 检查已覆盖此情况

---

## 优化任务执行的实用建议

1. **首先实施修改 3（辅助方法）**，然后在修改 1 和修改 2 中使用它 —— 这可避免复制粘贴错误，并保持两处守卫点同步。
2. **在修复之前编写测试**（轻量级 TDD）：陈旧弹出窗口场景更容易通过先失败后通过的测试来验证。
3. **在每次修改后运行 `pytest tests/test_app_textual.py -k "wq or completion" -v`** —— 这两个区域最近被修改过，且隔离 fixture（每个测试一个 `YateApp`）与补全测试所使用的一致。

## 潜在风险与缓解策略

| 风险 | 可能性 | 影响 | 缓解措施 |
|---|---|---|---|
| 过于激进的陈旧性检查在有效情况下关闭弹出窗口（例如光标抖动） | 低 —— 前缀比较是确定性的；输入*总是*改变前缀 | 中（用户体验烦人） | 该检查仅在 `await` 之后触发；防抖已对请求设门。比较完整前缀，而非仅单个列的增量。 |
| 辅助方法与 `accept()` 自身的前缀逻辑产生漂移 | 中 —— 有三处计算前缀（`_worker`、`accept`、新辅助方法） | 低（轻微不一致） | 新辅助方法使用与 `_worker` 和 `accept` 相同的 `isalnum() or "_"` 规则。添加注释说明它们必须保持同步。 |
| 回归：`buffer_completions` 路径包含路径前缀字符（`/`、`\`、`~`），但辅助方法不包含 | 低 —— 基于 buffer 的路径补全已带有显式范围 | 低 | 通过阅读代码确认：`buffer_completions` 始终发出带有 `range_start_row/col/end_row/end_col` 的项，因此 `accept()` 使用范围，而非重新计算的前缀。陈旧守卫只需决定*是否显示弹出窗口*，而非如何替换。 |
| 当用户输入的字符超出范围时，`accept()` 守卫（修改 4）破坏了 Tab 接受 | 低 —— 现有的 `if row == r1 and col >= c1: c1 = col` 行已扩展结束列 | 低 | 修改 4 只增加行检查；列由现有的扩展逻辑处理。 |

## 可行的扩展方向

1. **基于内容版本的陈旧性判断。** `TextBuffer.content_version` 在每次文本变更时递增。在 `_worker` 开始时捕获它并在 `await` 后重新检查，只需一次整数比较即可覆盖*所有*变更场景（输入、删除、粘贴、撤销），而不仅是行/列变化。这比前缀文本比较更清晰、更通用。无需对 `TextBuffer` 进行 API 更改 —— `content_version` 已是公开的。

2. **显式取消进行中的 worker。** `CompletionController._timer` 已取消防抖定时器。控制器还可以跟踪当前 `_worker` 任务，并在调用 `schedule()` 时取消它。结合 `exclusive=True`，这将使陈旧性检查纯粹成为防御性措施，而非必需。

3. **任何 buffer 变更时弹出窗口自动关闭。** 弹出窗口可以监听 buffer 的 `content_version` 变化，并在 buffer 被修改时自行关闭，而不是在 await 之后检查陈旧性。这将完全消除对每个 worker 进行陈旧性检查的需要，代价是弹出窗口生命周期更具响应性（但更简单）。

---

## 后续修复（2026-09-23）：弹出窗口不再吞掉所有按键

上面的陈旧守卫只覆盖查询返回*之后*发生的事情。第二个更早就存在的缺陷位于按键路径中：当弹出窗口打开时，分发器会消耗**每一个**按键（`if popup.is_open: ... return True`），因此输入无法扩展前缀，`after_editor_key()` 中带守卫的重新查询无法到达（参见 `../issues/review.md`，"completion popup intercepts all keys"）。

- **源码修复** —— `yate/editor.py::handle_key` 现在只消耗 `tab` / `enter` / `up` / `down` / `escape`；其他所有按键都会落入正常分发（`event_to_raw` → `handle_raw_key` → `CompletionController.after_editor_key`），后者会用新的前缀重新查询。当弹出窗口打开时，全局组合键（`Ctrl+S`、`Ctrl+Z`、`Ctrl+P` 等）再次可用。
- **守卫** —— `tests/test_app_textual.py::test_completion_popup_keeps_typing_and_filters`（在 `Ctrl+Space` 后输入 `p` / `h` 会扩展 buffer 并持续过滤）以及冒烟场景 `regress_completion_staleness`，后者现在断言弹出窗口确实打开了（`popup_was_open`），而不是空泛地通过。
- **归因**（2026-09-23 重新验证）—— `return True` 是随 `e70dd15`（2026-09-12）引入的，但当时 `EditorView.on_key` **不会**对无法识别的按键调用 `stop()`，因此它们会冒泡到 `YateApp.on_key` 的后备路由并仍到达 buffer：在 master（`673b077`）上运行同样的探针时，即使弹出窗口打开，输入 `p` / `h` 也正常，且 `Ctrl+Z` 仍能撤销。分层重构（`9fa5ac8`）使 `EditorView.on_key` 无条件停止每个按键，并将弹出窗口分支移入 `Editor.handle_key`，因此陈旧的 `return True` 最终吞掉了输入。
