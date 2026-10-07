# Gitee PR !60 AI 队友评审记录（第一轮，ctrlp-preview，2026-10-07）

> **本文是只读事实文档**：只记录发现与核对结论；修复安排见方案文档
> [pr60-ctrlp-preview-review-fixes-plan.md](../documents/pr60-ctrlp-preview-review-fixes-plan.md)。
>
> 这是 PR !60 的第一轮 AI 队友评审。同分支前序记录：
> [2026-10-03-python-code-review.md](2026-10-03-python-code-review.md) 等为本轮之前的
> skill / 人工评审；本轮首次出现 `PR观察者`（AI 队友）对 PR !60 的结论。

- **对象**：[Gitee PR !60](https://gitee.com/jermaine/yate/pulls/60)
  （`feat/ctrlp-preview` → `master`，issue **IKJRGP**「Ctrl+P 搜索文件带 preview」），评论
  [`note_51460834`](https://gitee.com/jermaine/yate/pulls/60#note_51460834_conversation_191452840)
  conversation 191452840（作者 `PR观察者` / `pull_review_bot_2f642dd39f557e6f`，
  评审完成 2026-10-07 09:07:25 +08:00）。
- **触发**：仓库所有者 Jermaine007 在 PR !60 下发 `@PR观察者 /review`（评审完成前约 1 分钟）。
- **取回方式**：抓取 PR 页面（本次页面渲染含评论正文全文；与 PR !59 各轮"页面不展开正文、
  需走 Gitee API"的情形不同，无需另走 API）。
- **核对基准**：worktree `D:/Programming/yate-ctrlp-preview`（分支 `feat/ctrlp-preview`，
  HEAD `2e138a8`，10 笔提交，工作区干净）。下文所有 `palette.py` 行号均以该 HEAD 为准。

## 一、评审自评结论（原样登记）

| 评审规则 | 结论 | 完成时间 |
|---|---|---|
| 功能性与逻辑 | ❌ 未通过 | 2026-10-07 09:07:25 |
| 安全性 | ✅ 通过 | 2026-10-07 09:07:25 |
| 性能 | ✅ 通过 | 2026-10-07 09:07:25 |
| 可维护性 | ⚠️ 待优化 | 2026-10-07 09:07:25 |

AI 队友结论：**⛔ 1 个阻断项 + 1 个改进项，请修改后再合并**，风险等级 `medium`。其正面评价：
worker 线程模型与 FIFO 缓存策略合理，安全性无风险（路径来自 Workspace 索引且解码声明
`errors="replace"`），"整体架构清晰、测试覆盖全面，上述两个问题均为边缘路径缺陷，
不影响主流程正确性"。

## 二、两项发现与本仓库核对结论

| # | 级别 | 位置 | 评审所述问题 | 本仓库核对 | 处置 |
|---|---|---|---|---|---|
| B1 | ⛔ 阻断（功能性） | `yate/editor_view/palette.py` `_load_preview` / `_preview_text` | tokenize 异常降级后 `tokens` 保持 `[]`，`zip(data.lines, data.tokens)` 产生零对元素，预览窗格全空白而非纯文本，与代码注释声明的设计意图矛盾 | ✅ **属实**（§3.1） | 🔧 闭环修复（方案 §步骤 1） |
| I1 | ⚠️ 改进（可维护性） | `yate/editor_view/palette.py` `_update_preview` | `run_worker` 传协程表达式而非可调用对象，违反同文件/全仓既有惯例；`filterwarnings = ["error::RuntimeWarning"]` 下极端时序可致间歇性测试失败 | ✅ **属实**（§3.2） | 🔧 闭环修复（方案 §步骤 2） |

结论：**1 阻断 / 1 改进，全部属实，按用户指令走闭环修复**（复用 `feat/ctrlp-preview`
分支与 worktree，方案见
[pr60-ctrlp-preview-review-fixes-plan.md](../documents/pr60-ctrlp-preview-review-fixes-plan.md)）。

## 三、逐条取证

### 3.1 B1：tokenize 异常降级路径丢失全部行内容（属实）

- `palette.py:412` `tokens: list[list[Token]] = []` 初始为空；
  `:414` 成功路径整体赋值；`:415-418` `except` 块仅记日志后**保持 `tokens == []`**，
  而此时 `lines` 非空（能走到 tokenize 说明读文件成功）。
- `palette.py:471` `_preview_text` 以 `zip(data.lines, data.tokens)` 组装渲染——
  `zip` 以最短可迭代为准，`tokens == []` 时产生**零对**元素，所有行被跳过，
  预览窗格除截断注记外完全空白。
- 与意图矛盾的直接证据在注释自身：`:416-417` 写明 *"A tokenizer crash must never
  leave the pane stuck on 'loading…'; empty tokens render the plain lines via t.fg"*——
  声称空 tokens 会走纯文本渲染，实际 `zip` 语义使然根本到不了行循环。
- 评审给的修法（except 内 `tokens = [[] for _ in lines]` 对齐行数）核对成立：
  行对齐后每行 token 列表为空，`_preview_text` 的 `pos < len(line)` 分支
  （`palette.py:479-480`）以 `t.fg` 渲染整行，正是注释声称的行为。

### 3.2 I1：`run_worker` 传协程表达式而非可调用对象（属实）

- `palette.py:354-357`：`self.run_worker(self._load_preview_worker(path), ...)` 在
  **调用 `run_worker` 的那一刻**就创建了协程对象；若 worker 因 `exclusive=True`
  或界面关闭从未启动，协程永不被 await。
- 同文件先例：`palette.py:525-530` `on_mount` 的索引 worker 传的是
  `self._index_files` 函数引用，且注释明说 *"an eager coroutine would leak if the
  worker never starts (closing pump)"*——评审所述"项目既有规范"在同文件内即可印证。
- 放大器：`pyproject.toml:118` `filterwarnings = ["error::RuntimeWarning"]`，
  未消费协程的 "coroutine was never awaited" 警告会升格为错误，造成间歇性测试失败。
- 修法（`partial(self._load_preview_worker, path)`）核对成立：Textual 的
  `run_worker` 接受可调用对象并自行调度，`partial` 保持 pyright 在接线处的完整签名推导。

## 四、状态

| 编号 | 摘要 | 分类 | 状态 |
|---|---|---|---|
| B1 | tokenize 异常降级后 `zip` 丢行，预览全空白（注释声称的纯文本降级不成立） | 阻断（功能性） | 🔧 闭环修复（2026-10-07，方案见 [pr60-ctrlp-preview-review-fixes-plan.md](../documents/pr60-ctrlp-preview-review-fixes-plan.md) §步骤 1；修复后实测回填该文档） |
| I1 | `run_worker` 传 eager 协程对象，违反同文件 `on_mount` 既有惯例；RuntimeWarning-as-error 下可致测试间歇失败 | 改进（可维护性） | 🔧 闭环修复（同上，§步骤 2） |

## 五、取证范围声明

- 本轮核对全部为静态只读取证（`yate/editor_view/palette.py`、
  `tests/test_palette_preview.py`、`pyproject.toml`，基准 HEAD `2e138a8`）+ PR 页面抓取；
  未复现 tokenize 异常场景、未运行测试——修复后的运行时验证与门禁数字记录在方案文档。
- 评审的正面结论（性能、安全性、worker 模型与缓存策略合理）未逐项复核，
  仅登记原文；与本仓前几轮评审（skill 六维度、python-code-review）无重叠发现。
