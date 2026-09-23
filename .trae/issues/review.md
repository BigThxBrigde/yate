# yate Code Review

## 历史问题

- [x] 输入时候，屏幕会闪烁，影响输入体验，加入放抖动机制。
- [x] yate 输入一个不存在的文件名，进程会卡住无任何输出，希望和vim一样，直接进入enew新建一个bug。

---

## 全量代码审查 — 2026-09-16

> **2026-09-23 复核**：对照当前代码逐条核实（其间完成 L4→L0 分层重构，原
> `app_features/*` 路径已迁移）。已修复的条目标记 `[x]` 并附证据；经核实
> 不再成立的条目收录在文末「已失效条目」章节。
>
> **修复计划**（只计划、未实施，位于
> `.trae/documents/code-review-fix-plans/`）：
>
> - Critical → [P0_critical_fixes_plan.md](../documents/code-review-fix-plans/P0_critical_fixes_plan.md)
> - Suggestion → [P1_suggestions_plan.md](../documents/code-review-fix-plans/P1_suggestions_plan.md)
> - Nice-to-have → [P2_nice_to_have_plan.md](../documents/code-review-fix-plans/P2_nice_to_have_plan.md)

### 🔴 Critical（必须修复）→ 计划：[P0](../documents/code-review-fix-plans/P0_critical_fixes_plan.md)

- [x] **`:wq` 保存失败时仍退出，导致数据丢失** — `app_features/commands.py:54`
  `_wq` 调用 `save_document()` 后无条件 `quit(force=True)`。若保存失败（无路径、用户取消、权限错误），`force=True` 跳过未保存检查直接退出，丢失工作内容。
  **修复：** 保存失败时检查 `doc.modified` 或让 `save_document` 返回成功标志，仅在保存成功时退出。

- [x] **补全弹窗过期检查仅比较行号，可能导致文本损坏** — `app_features/completion.py:121`
  LSP await 返回后仅检查 `buf.row != row`。若用户在同一行继续输入（列号变化），过期补全仍显示，接受后 `replace_range` 使用过时坐标。
  **修复：** 同时比较 `col` 和/或前缀文本。

- [x] **文件夹删除关闭标签时未通知 LSP** — `app_features/explorer.py:107`
  删除文件夹导致已打开标签关闭时，文档从 `app.docs` 移除但未调用 `lsp.on_document_closed()`，LSP 服务器保留过时的 `didOpen` 状态。
  **修复：** 遍历被关闭的文档并调用 `lsp.on_document_closed()`。

- [ ] **LSP `_read_loop` 未捕获所有异常，导致请求永久挂起** — `editor_lsp/client.py:345`
  意外错误（OSError、ValueError 等）会静默终止读取循环，而客户端仍保持 `READY` 状态，所有待处理请求永久挂起。
  **修复：** 在 `_read_loop` 中添加 `except Exception` 捕获，触发客户端状态转为 `FAILED`。
  *复核：仍存在 — [client.py:426-428](../../yate/editor_lsp/client.py) 仅捕获 `CancelledError` 与 `(LspError, ConnectionError, EOFError)`，其余异常仍会逸出。*

- [ ] **LSP `register_server` 竞态条件** — `editor_lsp/manager.py:118`
  取消正在进行的启动任务是 fire-and-forget 方式。被取消任务的 `finally` 块可能稍后移除新替换任务在 `_starting` 中的条目，导致其失去跟踪。
  **修复：** 在取消前检查任务是否为当前活跃任务，或使用取消安全的方式清理。
  *复核：仍存在 — [manager.py:224-229](../../yate/editor_lsp/manager.py) 的 `finally: self._starting.pop(key, None)` 无 identity 检查，被取消任务的 awaiter 仍可能弹出新任务的条目。*

- [ ] **`replace_all` 修改行后未钳制光标位置** — `editor_core/search.py:148-170`
  批量替换后光标列号可能超出新的（更短的）行长度。在下次重绘前读取 `buffer.col` 的代码会看到无效位置。
  **修复：** 替换循环结束后钳制光标：`c = min(c, len(buffer.lines[r]))`。
  *复核：仍存在 — [search.py:118-145](../../yate/editor_core/search.py) 替换后仅清 anchor，无钳制。*

- [x] **补全弹窗拦截所有按键，包括 Ctrl+S、Ctrl+Z** — `editor_view/editor.py:163`
  补全弹窗打开时所有按键被消费，用户无法保存或撤销。
  **修复：** 对高优先级命令（Ctrl+S、Ctrl+Z、Ctrl+Q 等）放行到 keymap 分发。
  *已修复（2026-09-23）— [editor.py:551-570](../../yate/editor.py) 现在只消费 `tab` / `enter` / `up` / `down` / `escape`，
  其余按键 fall-through 到正常分发（`event_to_raw` → `handle_raw_key` → `CompletionController.after_editor_key`）：
  字符继续写入缓冲区并按新前缀重新查询候选，`Ctrl+S` / `Ctrl+Z` / `Ctrl+P` 等全局快捷键恢复可用。
  守卫见 `tests/test_app_textual.py::test_completion_popup_keeps_typing_and_filters`、冒烟场景 `regress_completion_staleness`（字符落盘且弹窗按新前缀重查）
  与 `regress_completion_popup_keys`（键位分工：可打印字符与全局键 fall-through，`tab`/`down`/`escape` 仍归弹窗）。
  *归因（2026-09-23 复核修正）：吞键代码由 `e70dd15`（2026-09-12）引入，但当时 `EditorView.on_key` 对未识别键不 `stop()`，
  事件会冒泡到 `YateApp.on_key` 的 fallback 路由，因此 **master（`673b077`）实测无此问题**：弹窗打开时输入 `p`/`h` 正常进缓冲区（`alp`/`alph`）、`Ctrl+Z` 正常撤销。
  本轮分层重构（Plan D）把 `EditorView.on_key` 改为无条件 `stop()` 并把弹窗分支搬进 `Editor.handle_key`，未消费的键不再冒泡，该缺陷才首次真正显现。*

- [ ] **命令面板 CJK 字符对齐错误** — `editor_view/palette.py:178`
  使用 `len(display)` 而非 `theme.cell_len(display)` 计算填充。CJK 字符（2 单元格宽）导致提示列错位。
  **修复：** 改用 `cell_len()` 计算显示宽度。
  *复核：仍存在 — [palette.py:266](../../yate/editor_view/palette.py) 仍用 `len(display)`。*

- [ ] **发布工具硬编码 `"master"` 分支** — `tools/release/cli.py:~186`
  `git_push(repo, "master")` 在使用 `main` 或其他默认分支的仓库上会失败——且此时所有昂贵操作（bump、changelog、gate、tag）已经完成。
  **修复：** 动态检测默认分支，或接受 `--branch` 参数。
  *复核：仍存在 — [cli.py:187-234](../../tools/release/cli.py) 仍硬编码 `git_push(repo, "master")`。*

- [ ] **Changelog `check` 和 `zh-commit` 忽略 `overrides_path`** — `tools/changelog/cli.py`
  这两个子命令始终使用 `DEFAULT_OVERRIDES_PATH`，`--overrides` 参数被静默忽略。
  **修复：** 将 `overrides_path` 一致地传递给所有子命令函数。
  *复核：仍存在 — 函数签名已支持 `overrides_path`，但 [cli.py:268-300](../../tools/changelog/cli.py) 的 CLI 绑定未为 `check` / `zh-commit` 暴露 `--overrides` 参数。*

---

### 🟡 Suggestion（建议修复）→ 计划：[P1](../documents/code-review-fix-plans/P1_suggestions_plan.md)

- [ ] **正则模式每次 tokenize 重新编译** — `editor_syntax/regex_backend.py:570`
  每次 `tokenize_document` 调用都重新构建并编译主正则。spec 不可变，结果始终相同。
  **建议：** 按 filetype 缓存编译后的模式。
  *复核：仍存在 — [regex_backend.py:412-431](../../yate/editor_syntax/regex_backend.py) `_code_line_pattern(spec)` 每次调用重建并 `re.compile`，无缓存。*

- [ ] **配置模式布尔值正则每行编译 7 次** — `editor_syntax/regex_backend.py:647`
  `_tokenize_config_line` 中为 7 个布尔值单词各编译一次正则。
  **建议：** 预编译为单一交替模式 `_CONFIG_BOOL_RE`。
  *复核：仍存在 — [regex_backend.py:674-676](../../yate/editor_syntax/regex_backend.py) 仍在循环内逐词构造模式。*

- [x] **`Document.modified` 每次访问执行 O(n) 字符串比较** — `editor_core/document.py:82`
  每次访问调用 `get_text()` 并比较全文。UI 可能在每个渲染周期读取此属性。
  **建议：** 使用 `_dirty` 标志或按 `content_version` 缓存结果。
  **已修复（2026-09-23，提交 `05106d5` + `5190225`）：** 改为 `content_edits` 编辑计数 O(1) 快路径 + 行元组精确回退，跨 undo/redo 恒精确；`_Edit.weight` 保证合并打字场景计数对齐。

- [ ] **`create()` 同步打开新文件** — `app_features/explorer.py:82`
  应使用 `open_path_later()` 保持一致性。
  *复核：仍存在 — [explorer.py:385-387](../../yate/editor_view/explorer.py) 仍同步调用 `self.open_path(target)`。*

- [ ] **`_original_excepthook` 在导入时捕获** — `crash.py:32`
  应在 `install()` 内部捕获，避免导入顺序问题。
  *复核：仍存在 — [logs.py:278-280](../../yate/logs.py) `CrashService` 构造时捕获 `sys.excepthook`，注释标明 import time。*

- [ ] **宽字符（CJK）在最后一列被静默丢弃** — `editor_term/emulator.py:315`
  应换行到下一行显示，而非丢弃。
  *复核：仍存在 — [emulator.py:426-430](../../yate/editor_term/emulator.py) 宽字符到达最后一列仅设 autowrap 标记即返回，未实际换行。*

- [ ] **`fc-cache` 使用 `shell=True`** — `services/fonts.py:230`
  不必要且可移植性差。
  **建议：** 使用列表参数直接调用。
  *复核：仍存在 — [fonts.py:265-270](../../yate/services/fonts.py) 仍 `shell=True`。*

- [x] **补全解析器中存在未使用变量** — `editor_lsp/manager.py:520`
  `kind_raw` / `sort_raw` 未使用。
  **已修复（核实 2026-09-23）：** [manager.py:537-544](../../yate/editor_lsp/manager.py) 两个变量现已参与 `kind=` / `sort_text=` 的类型窄化。

- [x] **Vim `e` 动作不跳过词间空白** — `keymaps/vim.py:295`
  与真实 vim 行为不一致。
  **已修复（核实 2026-09-23）：** [buffer.py:56-69](../../yate/editor_core/buffer.py) `word_end()` 先跳过空白再找词尾，vim `e` 动作基于该实现。

- [ ] **`_exit_code` 对"仍活跃"和"API 失败"均返回 `None`** — `editor_term/pty_proc.py:495`
  语义模糊，应区分两种状态。
  *复核：仍存在 — [pty_proc.py:557-566](../../yate/editor_term/pty_proc.py) `STILL_ACTIVE` 与 `GetExitCodeProcess` 失败均返回 `None`。*

- [ ] **递归 `walk_files` 可能超出递归限制** — `services/workspace.py:185`
  极深目录树会触发 `RecursionError`。
  **建议：** 改用迭代方式（`os.walk` 或显式栈）。
  *复核：部分修复 — 符号链接环已防护（2026-09-23，提交 `a89a720`，[workspace.py:244-248](../../yate/services/workspace.py)）；但实现仍为嵌套递归函数，极深目录的递归深度风险未变。*

- [ ] **`diagnostics_on_line` 每行渲染调用两次** — `editor_view/editor.py:440`
  一次用于 gutter 标记，一次用于下划线。
  **建议：** 计算一次并作为参数传递。
  *复核：仍存在 — [editor.py:424-427](../../yate/editor_view/editor.py) 与 [editor.py:571-590](../../yate/editor_view/editor.py) 各调一次。*

- [ ] **`_welcome_lines()` 每次渲染重建** — `editor_view/editor.py:506`
  内容仅在 keymap 变化时改变，应缓存。
  *复核：仍存在 — [editor.py:495-510](../../yate/editor_view/editor.py) 无缓存。*

- [ ] **丢弃后未清除过期 highlight keys** — `editor_view/editor.py:365`
  导致即使没有待处理编辑也强制 80ms 防抖延迟。
  *复核：仍存在 — [editor.py:346-357](../../yate/editor_view/editor.py) discard 路径只清 scheduled key，未清 `_hl_tokens/_hl_doc/_hl_version/_hl_filetype`。*

- [ ] **`_cursor_anchor()` 每行渲染调用 3+ 次** — `editor_view/editor.py:131`
  每次调用重新遍历 pane 树评估 `is_active_view`。
  **建议：** 计算一次并传递。
  *复核：仍存在 — [editor.py:151-158](../../yate/editor_view/editor.py) 渲染路径多处各自调用。*

- [ ] **死条件分支** — `editor_view/terminal.py:251`
  `cell.char if cell.char != ' ' else ' '` 两个分支相同——重构残留。
  *复核：仍存在 — [terminal.py:280](../../yate/editor_view/terminal.py) 恒等分支原样保留。*

- [ ] **冗余滚动恢复** — `editor_view/panes.py:415`
  `reconcile` 为活动叶子恢复滚动，但 `apply_doc`（调用方）已经做过。
  *复核：仍存在 — [panes.py:474-483](../../yate/editor_view/panes.py)。*

- [x] **`id(document)` 作为字典键存在风险** — `editor_view/panes.py:32`
  若文档被 GC 且地址复用，会取到过期状态。
  **已修复（核实 2026-09-23）：** [pane_types.py:47-52](../../yate/editor_view/pane_types.py) 已改用稳定的 `Document.uid` 作为 view state 字典键。

- [x] **`_FakePtyImpl.instances` 是类级可变状态** — `tests/test_terminal.py`
  测试间可能泄漏。
  **建议：** 使用 fixture 作用域列表或 `monkeypatch.setattr`。
  **已修复（核实 2026-09-23）：** [test_terminal.py:268-311](../../tests/test_terminal.py) fixture 已在每个测试前重置 `instances` 并 monkeypatch PTY 实现，泄漏路径已消除。

- [ ] **测试生成 30 秒 sleep 子进程** — `tests/test_lsp.py`
  清理失败时有孤儿进程风险。
  **建议：** 使用更短的 sleep 或自终止脚本。
  *复核：仍存在 — [test_lsp.py:847](../../tests/test_lsp.py) 仍 `time.sleep(30)`。*

- [ ] **硬编码版本号 `"0.2.4"`** — `tests/test_theme_palettes.py`
  每次发版需手动更新。
  **建议：** 添加 semver 可解析断言，或交叉引用发布工具。
  *复核：仍存在 — [test_theme_palettes.py:271](../../tests/test_theme_palettes.py) 仍 `assert yate.__version__ == "0.2.4"`。*

- [ ] **`generate()` 使用 `date.today()` 导致输出不可复现** — `tools/changelog/cli.py`
  **建议：** 接受可选 `date` 参数。
  *复核：仍存在 — [cli.py:92](../../tools/changelog/cli.py) 仍 `datetime.date.today()`，CLI 无 `--date`。*

- [ ] **`--limit` 标志无测试** — `tests/test_changelog_tool.py`
  *复核：仍存在 — CLI 已有 `--limit`（[cli.py:251](../../tools/changelog/cli.py)），测试文件无对应用例。*

- [x] **大小写不敏感匹配机制未文档化** — `tests/test_workspace_filter.py`
  **已修复（核实 2026-09-23）：** [test_workspace_filter.py:160-164](../../tests/test_workspace_filter.py) 已有专门用例 `test_matching_is_case_insensitive` 固化该行为。

- [ ] **`position` 变量名用于两个不同概念** — `tools/changelog/segments.py`
  **建议：** 重命名循环变量为 `seg_index`。
  *复核：仍存在 — [segments.py:102](../../tools/changelog/segments.py)（段序号）与 [segments.py:122](../../tools/changelog/segments.py)（commit 位置）同名。*

- [ ] **subject 字段可能包含嵌入的字段分隔符** — `tools/changelog/gitdata.py`
  理论上的问题，实际极不可能。
  *复核：仍存在（理论性）— body 经 `maxsplit` 保留杂散分隔符，subject 字段本身无防护。*

- [ ] **`files_dirty` 路径解析可能误处理前导空格** — `tools/release/cli.py`
  *复核：仍存在 — [cli.py:63-75](../../tools/release/cli.py) 解析逻辑未变。*

- [ ] **测试深度访问私有 highlight 属性** — `tests/test_app_textual.py`
  与实现紧耦合，重构时易碎。
  **建议：** 暴露窄接口（如 `HighlightProbe` protocol）。
  *复核：仍存在 — [test_app_textual.py:204-314](../../tests/test_app_textual.py) 仍直接断言 `_hl_tokens` 等私有属性。*

- [ ] **`_FakeApp` 未实现所有 app hooks** — `tests/test_editor_core.py`
  新增 keymap action 调用未实现方法时会抛 `AttributeError`。
  *复核：仍存在 — [test_editor_core.py:394-406](../../tests/test_editor_core.py) 仍为最小 stand-in（已有 docstring 说明边界）。*

---

### 🟢 Nice-to-have（锦上添花）→ 计划：[P2](../documents/code-review-fix-plans/P2_nice_to_have_plan.md)

- [ ] **保存始终使用 LF，忽略原始/平台换行符** — `editor_core/document.py:97`
  *复核：仍存在 — [document.py:50-53](../../yate/editor_core/document.py) 打开时统一归一为 LF，保存按 LF 写出。*

- [ ] **配置模式 tokenizer 可能产生重叠 token** — `editor_syntax/regex_backend.py:636`
  *复核：仍存在 — `_tokenize_config_line` 各 `finditer` 独立发射，字符串内的数字/布尔词会重复着色。*

- [ ] **共享库缺少符号时错误无上下文** — `editor_syntax/ts_backend/languages.py:172`
  *复核：仍存在（部分改善）— 依赖缺失已有清晰提示（[languages.py:218-221](../../yate/editor_syntax/ts_backend/languages.py)），但缺符号时 `getattr(dll, symbol)` 仍抛裸 `AttributeError`。*

- [ ] **`_to_char` 中间字符字节偏移边界情况缺注释** — `editor_syntax/ts_backend/backend.py:115`

- [ ] **Outdent 移除 `tab_width` 个空格而非回到上一个 tab stop** — `editor_core/buffer.py:277`
  *复核：基本仍存在 — [buffer.py:510-525](../../yate/editor_core/buffer.py) 已支持整 Tab 剥离，但空格缩进仍按 `tab_width` 移除而非对齐上一个 stop。*

- [ ] **`replace_current` 可用 `replace_range` 简化** — `editor_core/search.py:126`
  *复核：仍存在 — [search.py:102](../../yate/editor_core/search.py) 独立实现保留。*

- [ ] **`_soft_reset`（ESC c）不退出备用屏幕** — `editor_term/emulator.py:250`
  *复核：仍存在 — [emulator.py:387-397](../../yate/editor_term/emulator.py) 未切换回主屏幕。*

- [ ] **ctrl+digit 绑定使用 kitty 协议，大多数终端不支持** — `keymaps/base.py:105`
  *复核：仍存在 — [base.py:118-121](../../yate/keymaps/base.py) 仍编码为 CSI-u。*

- [ ] **`cycle_tab` 允许空操作循环** — `app.py:453`
  *复核：仍存在 — [editor.py:476-484](../../yate/editor.py) 单 tab 时仅提示。*

- [ ] **smoke test 工具自身无测试** — `tools/smoke_test/`
  *复核：仍存在 — `tests/` 下无 smoke 工具自测。*

- [ ] **SVG 提取正则脆弱，依赖 Textual 版本** — `tools/smoke_test/testsuite.py`
  *复核：仍存在 — 提取仍基于 SVG 文本解析（[harness.py:130](../../tools/smoke_test/harness.py) `extract_svg_rows`）。*

- [ ] **单个场景执行无超时** — `tools/smoke_test/testsuite.py`
  *复核：仍存在 — 断言轮询有 5s 超时（`wait_until`），但场景整体执行无超时保护。*

- [ ] **`check_commit_pushed` 仅支持 `gitee.com`** — `tools/changelog/gitee.py`
  *复核：仍存在 — [gitee.py:61-85](../../tools/changelog/gitee.py) 其他 host 返回 `None`。*

- [ ] **`strip_unreleased` 边界情况（仅有 Unreleased 段）未测试** — `tools/changelog/render.py`
  *复核：仍存在 — 测试文件无 `strip_unreleased` 直接用例。*

- [x] **文档提到 e2e git 测试但实际不存在** — `tests/test_changelog_tool.py`
  **已修复（核实 2026-09-23）：** [test_changelog_tool.py:689](../../tests/test_changelog_tool.py) 已有「real git end-to-end」测试段（真实临时 git 仓库，无 git 环境时跳过）。

---

## 全量代码审查 — 2026-09-23

> 7 项全部修复，方案与验证记录见
> [`.trae/documents/code_review_fixes_plan.md`](../documents/code_review_fixes_plan.md)
> （提交 `05106d5` / `5190225` / `b0d154d` / `a89a720`）。

- [x] **`Document.save()` 非原子写入（High，数据完整性）** — 崩溃/磁盘满可毁原文件。
  已改 temp + `os.replace` 原子替换（`05106d5`）。
- [x] **undo 栈无深度上限（Medium）** — 全量快照无界增长。
  新增 `MAX_UNDO_STEPS = 1000` 淘汰最旧步骤（`05106d5`）。
- [x] **`doc.modified` 每键 O(n) 全文对比（Medium）** — 即上文 Suggestion 第 3 条。
  `content_edits` 计数 + 精确回退（`05106d5`，回归由 `5190225` 修复）。
- [x] **垂直移动丢失期望列（Medium）** — 短行截断后列永久丢失。
  `_goal_col` 追踪，编辑/水平移动/undo 等全路径清除（`b0d154d`）。
- [x] **扩展从 CWD 静默自动加载（Medium，供应链）** — 打开仓库即执行仓库自带代码。
  工作区信任门控：`~/.yate/trusted_workspaces` + `:trust` 显式确认（`a89a720`）。
- [x] **6 处 `except Exception: pass` 静默吞异常（Low）** — 违反规则 §4.5。
  保留隔离语义，全部补 `log.exception`（`05106d5`）。
- [x] **`walk_files` 不防符号链接环（Low）** — `ln -s . loop` 无限递归。
  不再进入符号链接目录（`05106d5`，即上文 Suggestion 第 11 条的环部分）。

---

## 已失效条目

> 审查条目经核实后不再成立的记录，仅存档。复核基准：2026-09-23 当前代码
> （分层重构 L4→L0 完成后）。

| 原条目 | 原位置 | 失效原因 |
|---|---|---|
| `is_relative_to()` 需要 Python 3.9+ | 原 `app_features/explorer.py:104` | 项目已要求 Python 3.10+（`pyproject.toml`），兼容性顾虑不复存在；代码现位于 `yate/editor_view/explorer.py` |
| 中文 docstring 与英文代码库不一致 | 原 `app.py:1690` | 分层重构随文档英文化一并清除；当前 `yate/app.py` 已检索不到中文 docstring |
| 未使用的导入 `replace`（from dataclasses） | 原 `editor_view/panes.py:11` | 该导入已不存在；panes.py 现从 `pane_types` 导入的 `replace_node` 在 [panes.py:235](../../yate/editor_view/panes.py) 有实际调用（被误判） |

---

## 冒烟补场景调查 — 2026-09-23

> 来源：按 `run --coverage` 缺口补冒烟场景（计划 §7.10，提交 `0984361`）。仅记录，未修产品源码。

- [ ] **action `quit` 注册后在 UI 上不可达（Low，注册冗余）** — [`keymaps/vsc.py:87`](../../yate/keymaps/vsc.py)
  两条独立原因：① vsc 的 `<ctrl+q>` 绑定被 Textual App 级 priority binding 遮蔽
  （`App.BINDINGS` 内置 `('ctrl+q','quit', priority=True)`，[`app.py`](../../yate/app.py) 覆写 `action_quit` 直接调 `Editor.quit()`）；
  ② 命令面板刻意去重与同名 `:command` 重名的 action（[`palette.py:186-190`](../../yate/editor_view/palette.py)），
  `quit` 命令存在 → 同名 action 条目被丢弃。用户可见的退出路径（ctrl+q 键、`:quit` 命令）均正常，无用户可见症状；
  只有 `execute_action("quit")`（扩展/测试路径）能触达该注册条目。
  **可选修法（三选一）：** ① `YateApp.action_quit` 改调 `editor.execute_action("quit")`；② 面板保留同名 action；③ 删除冗余的 vsc `<ctrl+q>` 绑定。
  冒烟侧已由 [`scenarios/files.py::quit_action_dispatch`](../../tools/smoke_test/scenarios/files.py) 覆盖，`--coverage` 达 65/65。

- [ ] **终端面板显示时无法用按键把焦点交回编辑器（Nice-to-have）** — [`terminal.py:193-204`](../../yate/editor_view/terminal.py)
  面板获得焦点后 `TerminalView.on_key` 吞掉除 `ctrl+`` 之外的所有按键（`ctrl+1`、`Esc`、F5 等均被 stop 并转发给 shell），
  关闭/回焦只能靠 toggle 键。这是"终端独占键盘"的设计选择且有明确出路（`ctrl+`` 关闭），但对 vscode 习惯（`ctrl+1`）不友好。
  **可选修法：** 在 `TOGGLE_KEYS` 之外放行 `ctrl+1`（`focus_editor`）；`Esc` 需先确认 shell 是否依赖。

---

## 补全弹窗按键放行修复的附带发现 — 2026-09-23

> 来源：修复「补全弹窗吞掉所有按键」（提交 `bbeb5f6`）期间实测到的相邻竞态，本轮**未修**、仅登记。
> 冒烟 [`regress_completion_popup_keys`](../../tools/smoke_test/scenarios/regression.py) 用 0.3s 落定等待规避它，
> 是为了让断言只测"键位分工"，并未掩盖该现象本身。

- [ ] **Esc 关闭补全弹窗后，在途的自动补全 worker 会把它重新显示（Low，UX 抖动）** — [`completion.py:128`](../../yate/completion.py)
  `popup.close()` 只改弹窗状态、不取消已排队的请求：`CompletionController._stale()`
  （[`completion.py:202-219`](../../yate/completion.py)）只比较文档 / 行 / 列 / 前缀与挂载状态，
  不检查弹窗是否被用户显式关闭，因此 worker 落地后仍会调用 `popup.show()`。
  按键触发的 0.12s 防抖查询（`_DEBOUNCE_S`，[`completion.py:38`](../../yate/completion.py)）
  恰好落在 Esc 之后时，弹窗会在约 0.1s 后重新出现：探针实测 Esc 后立即 `is_open=False`，
  在途 worker 落地后回到 `True`（临时探针脚本已删除，未落盘）。
  **修复：** 关闭时记录"用户已忽略"标记（或递增 generation / 取消在途 worker），
  `_worker` 与 `_stale()` 一并检查；用户再次主动触发（`Ctrl+Space`，或继续输入使前缀变化）时清除。
  注意与 `after_editor_key` 的 `schedule()` 区分：后者属于主动输入路径的 guarded re-query，应保留。
