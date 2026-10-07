# Gitee PR !60 AI 队友评审记录（第二轮，ctrlp-preview，2026-10-07）

> **本文是只读事实文档**：只记录发现与核对结论，不含修复排期。按用户指令**本轮只登记、
> 不修复**（`doc-conventions.md` §二.2 的"评审发现需要修复时"不适用），处置另案。
>
> - **本文是第二轮**：第一轮（note 51460834，⛔ 1 阻断 + 1 改进）记录见
>   [2026-10-07-pr60-ctrlp-preview-ai-review.md](2026-10-07-pr60-ctrlp-preview-ai-review.md)，
>   其整改方案与门禁实测见
>   [pr60-ctrlp-preview-review-fixes-plan.md](../documents/pr60-ctrlp-preview-review-fixes-plan.md)。
>   第一轮两项发现（B1/I1）已修（`e7c2f25`），**本轮评审已明确认可两处修复**，未再提出。

- **对象**：[Gitee PR !60](https://gitee.com/jermaine/yate/pulls/60)
  （`feat/ctrlp-preview` → `master`，issue **IKJRGP**），评论
  [`note_51461681`](https://gitee.com/jermaine/yate/pulls/60#note_51461681_conversation_191456117)
  conversation 191456117（作者 `PR观察者` / `pull_review_bot_2f642dd39f557e6f`，
  评审完成 2026-10-07 10:45:59 +08:00）。
- **触发**：仓库所有者 Jermaine007 在修复推送后于 PR 下再次 `@PR观察者 /review`。
- **取回方式**：抓取 PR 页面（正文随页面渲染完整取回，同第一轮）。
- **核对基准**：worktree `D:/Programming/yate-ctrlp-preview`（分支 `feat/ctrlp-preview`，
  HEAD `271ba88`，16 笔提交，工作区干净）。下文行号均以该 HEAD 为准。

## 一、评审自评结论（原样登记）

| 评审规则 | 结论 | 完成时间 |
|---|---|---|
| 功能性与逻辑 | ✅ 通过 | 2026-10-07 10:45:59 |
| 安全性 | ✅ 通过 | 2026-10-07 10:45:59 |
| 性能 | ✅ 通过 | 2026-10-07 10:45:59 |
| 可维护性 | ⚠️ 待优化 | 2026-10-07 10:45:59 |

AI 队友结论：**⚠️ 无阻断项，但发现 2 个改进建议，可优化后合并**，风险等级 `low`。
其改动检查中明确认可第一轮整改：*"修复了评审发现的两个问题：B1（tokenize 失败时
tokens 对齐为空列表以避免 zip 丢行）和 I1（使用 partial 避免 eager coroutine 泄漏）"*
——与 [pr60-ctrlp-preview-review-fixes-plan.md](../documents/pr60-ctrlp-preview-review-fixes-plan.md)
§步骤 1/2 的落地方式一致。PR 侧审查/测试指派均已完成（1/1）。

## 二、两项发现与本仓库核对结论

| # | 级别 | 位置 | 评审所述问题 | 本仓库核对 | 处置 |
|---|---|---|---|---|---|
| I2 | ⚠️ 改进（可维护性） | `yate/editor_view/palette.py` `_load_preview` | `line.rstrip("\n")` 仅去 `\n`，CRLF 文件的 `\r` 残留在预览行尾，可能与编辑器主视图显示不一致 | ✅ **属实，且不一致为实锤**（§3.1）：主视图 `Document.open` 将 `\r\n`/`\r` 全部归一为 `\n`，预览未归一 | 👀 登记待处置（2026-10-07） |
| I3 | ⚠️ 改进（可维护性） | `yate/config.py` `_extract_file_preview` | 未知键排序 `sorted(key for key in values if key not in known)` 对混合类型键可能抛 `TypeError`；`_extract_screen_saver` 同样模式 | ✅ **属实，两处同型**（§3.2）：`config.py:500` 与 `config.py:607` | 👀 登记待处置（2026-10-07） |

结论：**0 阻断 / 2 改进，均属实，本轮按用户指令只登记不修复**。

## 三、逐条取证

### 3.1 I2：CRLF 预览行残留 `\r`（属实，主视图对照成立）

- `palette.py:404`：`line.rstrip("\n") for line in islice(fh, self.preview.max_lines)`
  ——只剥 `\n`；CRLF 文件每行末尾留 `\r`，随 `t.fg` 文本渲染（行尾不可见字符），
  也会参与 tokenize 的列位置。
- **"与主视图不一致"的实锤**：编辑器主视图走 `Document.open`
  （`yate/editor_core/document.py:74-75`）——先记下主导行尾，随后
  `text.replace("\r\n", "\n").replace("\r", "\n")` **全部归一为 LF**，缓冲区行永不含 `\r`。
  即同一 CRLF 文件，主视图无 `\r`、预览窗格有 `\r`，不一致属实。
- 评审建议 `rstrip("\r\n")` 与主视图语义等效（`splitlines()` 会改变空行/EOF 语义，
  不如前者贴切）；评审自己标注的"需确认主视图行尾处理策略"以上文 document.py 取证回答。

### 3.2 I3：未知键排序对混合类型键的潜在 `TypeError`（属实，两处同型）

- `config.py:607`（`_extract_file_preview`）与 `config.py:500`（`_extract_screen_saver`）
  均为 `unknown = sorted(key for key in values if key not in known)`。
- yaterc 经 `exec` 字面量解析，键在理论上可为任意 hashable 字面量（如 `{1: "x"}` 或
  混入 `True`）；`sorted` 对不可互比的键（`str` vs `int`）抛 `TypeError`。评审自身
  也定性为"实际场景极罕见"，纯防御性加固；其 `sorted(str(key) ...)` 修法核对可行。
- 备注：`key not in known` 还要求键 hashable，不可 hash 的键会在 `in` 检查处先行
  抛错——若做加固需一并考虑（登记原文事实，裁决另案）。

## 四、状态

| 编号 | 摘要 | 分类 | 状态 |
|---|---|---|---|
| I2 | CRLF 文件预览行尾残留 `\r`，与主视图（EOL 归一）不一致 | 改进（可维护性） | 👀 登记待处置（2026-10-07，本轮按指令只登记） |
| I3 | `_extract_file_preview` / `_extract_screen_saver` 未知键 `sorted` 对混合类型键潜在 `TypeError` | 改进（可维护性） | 👀 登记待处置（2026-10-07，本轮按指令只登记） |

## 五、轮次小结

| 轮次 | 结论 | 阻断 / 改进 | 处置 |
|---|---|---|---|
| 第一轮（09:07:25，note 51460834） | ⛔ 未通过 | 1 阻断 / 1 改进 | ✅ 两项已修并经门禁回填（`e7c2f25`，见修复方案文档） |
| 第二轮（10:45:59，note 51461681） | ⚠️ 无阻断，可优化后合并 | 0 阻断 / 2 改进 | 👀 2 项登记待处置（本轮按用户指令只登记不修） |

第二轮未再提出第一轮的任何发现，并正面确认 B1/I1 修复——**PR !60 连续两轮收敛，
阻断项已清零**。

## 六、取证范围声明

- 本轮核对全部为静态只读取证（`yate/editor_view/palette.py`、`yate/config.py`、
  `yate/editor_core/document.py`，基准 HEAD `271ba88`）+ PR 页面抓取；
  未运行测试、未构造混合类型 yaterc 复现 `TypeError`、未渲染 CRLF 预览实测——
  I2 的"不一致"结论基于 `Document.open` 与 `_load_preview` 的代码语义对照。
- 评审的正面结论（功能/安全/性能通过、"测试覆盖全面、对现有行为无破坏性影响"）
  未逐项复核，仅登记原文。
