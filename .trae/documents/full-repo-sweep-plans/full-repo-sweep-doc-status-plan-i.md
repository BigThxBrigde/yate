# D2：统一状态块并移除本地路径（计划 i）

> **实施状态**：✅ 已实施 —— 2026-11-20（`e6723300`，四份文档状态块统一）

父计划：[../full-repo-sweep-plan.md](../full-repo-sweep-plan.md)。

## 输入

- `../toggle-comment-plan.md:7-10` 暴露了本地 worktree 路径（违反 `../../rules/doc-conventions.md` §五），且没有统一的状态块。
- `../macro-record-replay-unified-plans/overview.md:3-4` 称仓库引用使用相对于仓库根目录的路径，与 `../../rules/doc-conventions.md` §五 矛盾。
- `../which-key-auto-trigger-plan.md:7`、`../soft-wrap-plans/overview.md:3`、`../macro-record-replay-unified-plan.md:6`、`../extension-trust-hardening-plan.md:3` 使用了临时的 `状态：` / `流程状态：` 行。

## 独占文件

- `../toggle-comment-plan.md`
- `../macro-record-replay-unified-plans/overview.md`
- `../which-key-auto-trigger-plan.md`
- `../soft-wrap-plans/overview.md`

仅这四个文件在范围内；其他临时示例仅供观察，本波次不做编辑。

## 设计

1. 在 `toggle-comment-plan.md` 中，将本地 worktree 路径行替换为可移植的陈述（分支名和父提交即可；不要盘符或用户目录）。在标题正下方添加一个统一状态块：`> **实施状态**：✅ 已实施 —— 2026-11-20（merged as !143 / ebe8fee6）`，正文其余部分保持不变。
2. 在 `macro-record-replay-unified-plans/overview.md` 中，仅删除仓库根目录相对路径那句话；保留“相对于本目录”规则，并添加统一状态块，其状态以文档自身历史为依据。
3. 在 `which-key-auto-trigger-plan.md` 和 `soft-wrap-plans/overview.md` 中，用统一块替换临时状态行，在块文本中保留事实性状态和日期。不要重写周围正文。

## 验证

- 纯文档变更：无需运行测试。
- 重读每份编辑过的文件开头并确认：(a) 恰好一个 `**实施状态**` 块；(b) `toggle-comment-plan.md` 中没有盘符或用户目录；(c) macro overview 中没有仓库根目录相对路径的声明。

## 风险 / 回滚

风险：合并临时行时丢失历史状态细节；将原文措辞保留在块内。回滚：逐个还原这四个文件。
