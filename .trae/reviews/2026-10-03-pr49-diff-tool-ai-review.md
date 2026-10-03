# yate Code Review — Gitee PR #49 评审（diff-tool 分支）— 2026-10-03

## Gitee PR #49 评审（diff-tool 分支）— 2026-10-03

> **范围**：PR #49 `feat/diff-tool` → `master`（issue IKJC88：两路/三路 diff
> 查看器——L0 纯 diff 引擎 [`yate/editor_core/diff.py`](../../yate/editor_core/diff.py)
> （stdlib difflib 行级/字符级 diff + diff3 合并分类）、L2
> [`yate/editor_view/diffview.py`](../../yate/editor_view/diffview.py)
> （DiffScreen / DiffPane：导航、块复制、vsc/vim 编辑键表、保存守卫、防抖重算）、
> L3/L4 经 `:diff` 命令与 `--diff` CLI 参数接入；评审时点含二轮评审修复与
> S2/S3/W2 backlog 清理）。本次登记 **Gitee AI 队友审查**
> （[原始评论](https://gitee.com/jermaine/yate/pulls/49#note_51434360_conversation_191342700)，
> 2026-10-03 11:27）：结论 **⚠️ 无阻断项，可优化后合并**——安全性 ✅ 通过，
> 功能性与逻辑 / 性能 / 可维护性 ⚠️ 待优化，风险等级 **low**
> （0 阻断 / 3 改进）。审查总评：架构分层清晰（L0/L2/L3/L4），安全防御完备
> （read-only / TOCTOU / IO 异常），测试覆盖充分。

### AI 发现逐条登记与处置

- [ ] **改进项 1：含 tab 的行上 inline diff 高亮偏移**（功能性与逻辑）—
  [`yate/editor_view/diffview.py`](../../yate/editor_view/diffview.py)
  `render_line` 的字符索引 `span` 计数器把 tab 展开的每个空格 cell 都计入
  （非空 cell 即 `span += 1`），`diff_words` 返回的 char-based 范围映射到
  错误 display cells；影响视觉不影响功能逻辑。审查者建议循环前用
  `theme.char_to_cell` 将 char-ranges 预转 cell-index set（参照 EditorView 模式）。

  *核对结论（2026-10-03）：未复核——本次登记不修，后续修复时先复现
  含 tab 行的高亮偏移再定修法。*

- [ ] **改进项 2：超长行全量展开的性能浪费**（性能）— `render_line` 先对整行
  `expand_char` 构建完整 cells 列表、渲染只取前 `text_w` 个 cell，终端 80 列 /
  行长 200+ 字符时一半以上展开计算被浪费。审查者建议展开前按
  `min(len(line), text_w * 2 + buf.tab_width)` 预截断输入。

  *核对结论（2026-10-03）：未复核——与改进项 1 同处 `render_line`，
  后续修复时一并评估。*

- [x] **改进项 3：两处 `on_unmount` 缺 `@override` 装饰器**（可维护性）—
  同文件 `DiffPane.on_mount` 标记了 `@override`，而
  `DiffPane.on_unmount`（[diffview.py:287](../../yate/editor_view/diffview.py#L287)）
  与 `DiffScreen.on_unmount`（[diffview.py:620](../../yate/editor_view/diffview.py#L620)）
  未标记，hook 风格不一致（两函数分属防抖修复 / 既有代码新增段）。

  *核对结论（2026-10-03）：属实（grep 核实两处均缺标记，同文件
  `DiffPane.on_mount` 有标记）。*

### 处置（2026-10-03 用户决策）

**本次登记不另修**（⏸）：3 项均无阻断（渲染偏移 / 微优化 / 风格一致性），
条 1 / 2 未经复核、条 3 属一致性。条目同步登记于
[diff-tool-plan.md](../documents/diff-tool-plan.md) 遗留待办，
后续修复时先复核条 1 / 2 再动手。
