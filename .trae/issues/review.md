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

---

## 测试 mock 目标核对 — 2026-09-23

> 来源：分层重构后的大规模机械改路径（`app.doc` → `app.editor.session.doc`）可能造成 mock 目标漏改而**静默失效**
> （patch 目标仍可解析，但被测代码已不从那里查找）。核对判据因此不是"目标是否存在"，而是"**使用点是否经该模块查找**"。

- [x] **22 处 mock 目标（15 个不同目标）全部核对，无静默失效** — `tests/`
  - `yate.app.YateApp` / `yate.config.load_config` / `yate.editor_view.manual.load_changelog_markdown`：
    使用方 `yate/cli.py` 全是**函数内 lazy import**（[`cli.py:155`](../../yate/cli.py) / `:178` / `:229` / `:279`），
    绑定发生在 patch 生效期间 ✓；
  - `yate.logs.crash.install` / `.uninstall`：patch 的是 `CrashService` **实例属性**，cli 经同一实例调用
    （[`cli.py:157`](../../yate/cli.py) / `:216`）✓；
  - `yate.editor.run_shell`：`editor.py` 以模块全局调用（[`editor.py:1081`](../../yate/editor.py) / `:1112`）✓
    —— 即本次评审建议的 `yate.app.run_shell` → `yate.editor.run_shell` 的正确形态，已迁移到位；
  - `yate.diagnostics._section_fonts` / `format_report`：`sections` 列表是 `format_report` 的**函数内局部变量**
    （[`diagnostics.py:84-97`](../../yate/diagnostics.py)），运行时按模块全局解析；`print_report` 同理（`:126`）✓；
  - `yate.editor_syntax.ts_backend.ts_available` / `yate.editor_syntax.resolve_filetype` / `available_filetypes`：
    被测方 [`diagnostics.py:313-316`](../../yate/diagnostics.py) 为**函数内 import** ✓；
  - `yate.editor_lsp.manager.CHANGE_DEBOUNCE_S`：同模块全局使用（[`manager.py:330`](../../yate/editor_lsp/manager.py)）✓；
  - `yate.editor_view.manual.files`：`manual.py` 内 `files(...)` 模块全局 ✓；
  - `yate.editor_term.shells.shutil.which` / `yate.extensions.python_lsp.sys.executable`：
    属"patch 打到真实模块对象"（`shutil` / `sys`），生效但影响面是**全局**，依赖 mock 的自动恢复兜底 ✓；
  - 另有 12 处 `patch.object(<运行期对象>, ...)`（`ts_langs._LANGS`、`app.editor.lsp`、`Workspace.walk_files` 等），
    不依赖字符串路径，天然无重构漂移风险 ✓。
  - 证据：`pytest tests/test_cli.py tests/test_diagnostics.py tests/test_shell.py tests/test_changelog_view.py
    tests/test_lsp.py tests/test_python_lsp_ext.py tests/test_ts_backend.py -q` → **exit 0 全绿**。
  - 结论：`tests/` **无需改动**；核对脚本为临时文件、已删除。

---

## PR #13 审查修复 — 2026-09-24

> 来源：Gitee PR [!13](https://gitee.com/jermaine/yate/pulls/13) 的 AI 审查（`/review` 于 2026-09-23 23:09 与 23:56 两次触发，
> 第二份为 2026-09-24 00:07 的复评）。第一份的阻断项「补全弹窗按键吞噬」已由 `bbeb5f6` 修复并附回归场景；
> 本条目记录其后修复的 **2 个阻断项 + 4 个改进项**（含第一份审查中未处理的 trust 目录权限建议）。

### 🚫 阻断项

- [x] **原子写丢失原文件权限与元数据** — [`editor_core/document.py`](../../yate/editor_core/document.py)
  `os.replace` 交换的是 inode：原文件的权限位（如 `0600`）、时间戳与以 xattr 承载的 POSIX ACL 会随旧 inode 一起丢失；
  固定名 `.yate-tmp` 还存在并发保存冲突。
  现改为 `tempfile.mkstemp(dir=parent, prefix="<name>.yate-tmp-")` 生成唯一临时文件，写完后
  `shutil.copystat(target, tmp)` 继承目标元数据（POSIX 上同时复制 xattr，即 ACL 载体），再 `os.replace`。
  守卫：`test_save_preserves_the_existing_permission_bits`（POSIX，Windows skip）、
  `test_save_creates_a_missing_path_without_leaving_a_temp_file`（跨平台，断言无 `*.yate-tmp-*` 残留）。
- [x] **信任检查与扩展加载的路径不一致（TOCTOU）** — [`services/extensions.py`](../../yate/services/extensions.py)
  此前用 `Path.cwd()`（resolve 后）判定信任、却用未 resolve 的 `cwd / "extensions"` 加载：符号链接的 cwd 可以"以 A 通过校验、以 B 被加载"。
  现统一为 `cwd = Path.cwd().resolve()`，判定与加载共用同一路径。
  守卫：`test_startup_resolves_a_symlinked_cwd_for_trust_and_loading`（加载路径 `== real.resolve()`）、
  `test_startup_reports_the_resolved_path_when_skipping_a_symlinked_cwd`。

### ⚠️ 改进项

- [x] **信任列表读取未处理编码错误** — [`services/trust.py`](../../yate/services/trust.py)
  非法 UTF-8 字节此前抛 `UnicodeDecodeError`（可能让编辑器启动失败）；现用 `errors="replace"`，坏字节降级为 U+FFFD、合法行照常加载。
  守卫：`test_load_tolerates_invalid_utf8_bytes`。
- [x] **未知 action 名绑定静默吞键** — [`keymaps/base.py`](../../yate/keymaps/base.py)
  `dispatch` 现检查 `KeyUi.execute_action` 的返回值；未注册时向消息行写 `unknown action: <name>` 并返回 `False`，按键落到后续处理器。
  联动把 `KeyUi.execute_action` / `Editor.execute_action` / `PaletteScreen.execute_action` 改为返回 `bool`（palette 调用点、
  smoke harness 的覆盖率包装器与 3 处测试替身同步）。
  守卫：`test_binding_to_an_unknown_action_is_not_swallowed`、`test_binding_to_a_registered_action_is_dispatched`。
- [x] **`modified` 回退比较的 O(N) 成本未说明** — [`editor_core/document.py`](../../yate/editor_core/document.py)
  按审查建议的"注释说明"选项处理：属性 docstring 明确写出快路径 O(1)、回退路径 **O(N) in the line count**。
- [x] **字体缓存命令 `shell=True` + 硬编码路径** — [`services/fonts.py`](../../yate/services/fonts.py)
  改为列表参数 `[fc_cache, "-f", str(Path.home() / ".local" / "share" / "fonts")]`（无 shell、无重定向字符串），
  补 `timeout=10`，失败记 `log.debug` 而不打断安装。
  守卫：`test_install_unix_refreshes_the_cache_when_available`（含 `"shell" not in kwargs`）、
  `test_install_unix_survives_a_failing_cache_refresh`（timeout / OSError 两变体）。
- [x] **（第一份审查）信任文件目录权限** — [`services/trust.py`](../../yate/services/trust.py)
  首次创建 `~/.yate` 时用 `mkdir(parents=True, mode=0o700)`，避免宽松 umask 或预置目录让其他用户注入受信路径。
  守卫：`test_trust_workspace_creates_owner_only_directory`（POSIX）。

### 门禁（实测）

- `pytest tests/ -q` → exit 0 全绿（POSIX-only 用例在 Windows 上按预期 skip，共 2 条）
- `pyright yate/ tests/ tools/` → **0 errors, 0 warnings, 0 informations**
- `tools.smoke_test run --fail-only` → **87/87 场景、907/907 checks**，exit 0
- 修复前置状态：3 个测试成员并行补守卫（`test_fonts` / `test_trust` + `test_editor_core` / `test_vim_keymap` + `test_extensions`），
  产物均由主代理独立重跑复核

### 实施注记（两处任务前提与实现不符，已校准）

- **vim 普通模式仍吞未映射键**：`VimKeymap._handle_normal` 末尾无条件 `return True`（*swallow unmapped normal keys*，
  既有 `test_unmapped_normal_key_is_swallowed` 依赖此语义）。因此普通模式下若扩展绑定指向未注册 action，
  `dispatch` 会写 `unknown action: <name>` 提示、但按键最终仍被 vim 吞掉——这与"未映射键不插入也不冒泡"一致，
  故**不改** `yate/keymaps/vim.py`；守卫改用唯一把 dispatch 结果直接上抛的功能键路径（`<f7>`）。
- **信任条目在读取时逐条 resolve**：`load_trusted_workspaces` 对每条记录做 `Path(entry).resolve()`（既有行为），
  所以 store 里写 symlink 路径与其目标等价，无法构造"只记录字面 link → 不被信任"的断言。
  守卫因此改用两个真实可观测点：**被加载的目录**与 **skipped 消息**都必须使用 resolve 后的拼写
  （`test_startup_resolves_a_symlinked_cwd_for_trust_and_loading`、`test_startup_reports_the_resolved_path_when_skipping_a_symlinked_cwd`），
  并单列 `test_startup_treats_a_literal_symlink_entry_as_its_resolved_root` 显式记录该归一化行为。

- [ ] **（附带发现，Low/中）symlink 重定向即可改变信任对象** — [`services/trust.py`](../../yate/services/trust.py)
  信任按"读取时 resolve 后的路径"匹配：若 store 中某条目本身是 symlink 路径，链接被重定向后**无需重新 `:trust`** 即信任到新目标。
  彻底修复需改存储策略（落盘真实路径 / inode 校验，或在 `:trust` 时拒绝写入 symlink 路径），改动面超出本轮审查范围，**未修**。

---

## 全量代码审查 — 2026-09-24（issues/appprotocol-refactoring 分支）

> 审查对象：分支相对 `master` 的全部改动（merge-base `673b077`，HEAD = `33584e6`，
> 工作区变更已随该提交落盘）。规模：54 个提交，132 个文件，+16655 / −4469 行
> （其中 `yate/` 源码 52 文件 +4101 / −3260）。
> 方法：5 个分组审查子代理（L3/L4 外壳、L1 会话注册表、L2 组件、服务与流程、L0 内核与测试）
> → 2 个独立验证员全量复核 43 条 → 主代理对全部 Major 逐一现场核实。
> 门禁（主代理实跑）：`pyright yate/ tests/ tools/` **0 errors**；`pytest tests/ -q` **全绿**。

### 变更总览

**架构迁移（技术流）：**

```mermaid
flowchart TB
    subgraph BEFORE["重构前 master"]
        OLD["YateApp ~1800 行<br/>业务操作全在外壳"] --> AP["AppProtocol / interfaces.py"]
        OLD --> AF["app_features/*"]
    end
    subgraph AFTER["重构后本分支"]
        APP["YateApp（薄壳）<br/>CSS / 主题 / 生命周期"] --> ED["Editor（L3 新建）<br/>跨协作者的操作"]
        ED --> SE["Session（L1）<br/>Leaf / Split / ViewState"]
        ED --> EV["editor_view（L2）<br/>chrome / panes / terminal 注入协作者"]
        ED --> RG["Registries + Keymaps（L1）"]
        ED --> EX["services/*（L0）<br/>extensions + trust"]
        ED --> CO["editor_core（L0）<br/>buffer / document 原子写"]
    end
    BEFORE -.->|分层重构| AFTER
    style OLD fill:#ffcdd2,color:#7f0000
    style AP fill:#ffcdd2,color:#7f0000
    style AF fill:#ffcdd2,color:#7f0000
    style ED fill:#c8e6c9,color:#1a5e20
    style SE fill:#c8e6c9,color:#1a5e20
    style RG fill:#c8e6c9,color:#1a5e20
```

**原子写保存链（本次改动核心路径，标注缺陷位置）：**

```mermaid
flowchart LR
    TXT["buffer.get_text()"] --> ENC["encode(encoding)<br/>编码前置"] --> MK["mkstemp 兄弟目录<br/>恒 0600 ⚠Minor"]
    MK --> WR["fdopen + write<br/>⚠Minor fd 边角"]
    WR --> CS{"target.exists()?"}
    CS -->|是| CP["shutil.copystat<br/>❗Major mtime 冻结"]
    CS -->|否| SK["跳过 → 新文件 0600 ⚠Minor（POSIX）"]
    CP --> RP["os.replace<br/>⚠Minor 句柄占用面变宽 / symlink 语义"]
    SK --> RP
    RP --> OK["保存成功"]
    CP -.->|异常| CL["unlink tmp<br/>⚠Minor 顶掉原异常"]
    style CP fill:#ffcdd2,color:#7f0000
    style MK fill:#fff3e0,color:#e65100
    style WR fill:#fff3e0,color:#e65100
    style RP fill:#fff3e0,color:#e65100
    style SK fill:#fff3e0,color:#e65100
    style CL fill:#fff3e0,color:#e65100
```

**变更意图**：完成「去 AppProtocol」分层重构——删除 `AppProtocol` / `interfaces.py` / `app_features/*`，
把 ~1800 行的 `YateApp` 拆薄为纯 Textual 外壳（CSS、主题桥、生命周期），全部编辑器状态与操作下沉到
新建的 L3 `Editor`；新建 L1 `session.py`（`Leaf`/`Split`/`ViewState` 窗格树纯操作）与 `registries.py`
（`ActionRegistry` / `CommandRegistry`）；L2 组件全部改为构造注入具体协作者；新增 `trust.py`
（工作区信任存储，防陌生仓库自动执行其 `./extensions` 代码）；`Document.save` 改造为
mkstemp + `os.replace` 原子写；扩展系统经 `ExtensionContext` 暴露具体注册表。

**总体结论**：迁移忠实于分层方案，R1–R11 架构边界全部落实（无 Protocol 倒退、无 TYPE_CHECKING、
R7/R9/R10 经调用链核实合规），门禁全绿。但重构过程引入 **4 处可复现的功能回归**（下述 Major），
另有若干存量缺陷在本次大改文件中未顺手消除。

### 🔴 Critical — 无

### 🟠 Major（4 条，均为本次引入，主代理逐一现场核实）

- [ ] **M1 `cycle_tab` 丢失搜索状态重置，`:bn`/`:bp` 后搜索串扰** —
  [`editor.py:475-483`](../../yate/editor.py#L475-L483)
  旧 `app.py` 的 `cycle_tab` 在切换后重建 `SearchEngine`；重构后只调 `session.cycle(delta)`，
  对比 `open_path`/`close_tab`/`new_buffer` 均有重置。`SearchEngine.matches` 缓存的是**旧文档**
  的 `(row, start, end)`，`next()` 不重扫直接设置新 buffer 光标。
  **复现**：文件 A 中 `/pattern` 多行匹配 → `:bn` 切到文件 B → 高亮按 A 的坐标画在 B 上；
  `n` 跳转坐标越界。**修复**：`show_doc` 后补 `self.session.reset_search()`。

- [ ] **M2 `remove_node` 收缩 split 时 sizes 按位置错配** —
  [`session.py:303-321`](../../yate/session.py#L303-L321)
  `node.sizes[: len(new_children)]` 取的是**前** N−1 个 size，而非**存活子节点**的 size
  （children 与 sizes 按下标平行）。**复现**：三分栏 sizes `[0.5, 0.25, 0.25]`，关闭第一个窗格
  → 存活者被归一化为 `[0.667, 0.333]`，正确应为 `[0.5, 0.5]`；关闭中间窗格同理错配，
  `panes.apply_sizes` 直接消费该错误比例。
  **修复**：先按索引过滤 `(child, size)` 对，再用存活 size 列表做 `_normalized`。

- [ ] **M3 路径补全对尾分隔符前缀产出损坏候选** —
  [`prompt_completion.py:107-138`](../../yate/prompt_completion.py#L107-L138)
  `Path("src/")` 被 pathlib 规范化吞掉尾斜杠 → `p.name == "src"`，走父目录分支；
  `dir_part = prefix[: len(prefix) - len(base)]` = `"src/"[:1]` = `"s"`，
  候选变成 `"s" + entry.name`（如 `ssrc`），且匹配范围错到父目录。
  **复现**：工作区根输入 `:e src/` 触发补全，得到以 `s` 开头的乱串而非 `src/` 内条目。
  **修复**：入口检测 `expanded.endswith(("/", os.sep))`，尾分隔符时令 `parent = Path(expanded)`、
  `base = ""`、`dir_part = prefix`。

- [ ] **M4 `copystat` 把旧 mtime 带到新文件，保存后时间戳冻结** —
  [`document.py:140-152`](../../yate/editor_core/document.py#L140-L152)
  `shutil.copystat(target, tmp)` 复制 mode 之外还复制 atime/mtime，`os.replace` 后文件的
  mtime = **上次保存**时间而非 now，破坏外部消费者（`make`、轮询型文件监视器、mtime 比对的备份工具）；
  旧实现（write_bytes）mtime = 保存时刻。
  *本条是上文「PR #13 审查修复」copystat 保留元数据方案的附带产物；docstring 把「复制时间戳」写成了
  特性，但该论证只对权限位/ACL 成立，对 mtime 不成立。*
  **修复**：只复制 mode（`os.chmod(tmp, stat.S_IMODE(...))`），或 `copystat` 后 `os.utime(tmp)` 复位时间戳。

### 🟡 Minor（27 条）

**本次引入（17 条）：**

- [ ] **`run_worker` 传裸协程对象，与模块自身约定相悖** —
  [`editor.py:667-682`](../../yate/editor.py#L667-L682)
  `only_pane`/`close_pane` 传 `self.panes.only_active()` 协程对象；同文件 `_split_pane` 用
  `partial(...)`，且 `_lsp_documents_closed` docstring 明确「绝不传协程，worker 未启动时泄漏
  never-awaited coroutine」。**修复**：改 `partial(self.panes.only_active)` 等。

- [ ] **`--version` 拖入整个 TUI 栈** — [`diagnostics.py:24`](../../yate/diagnostics.py#L24)
  模块顶部 `from yate.editor import Editor` 使 `cli.py --version` 的「stays instant」承诺失效
  （textual/editor_view/keymaps/services 全量加载）。受 R6 约束不能走 TYPE_CHECKING 老路。
  **修复**：把 `version_lines` 下沉到叶子模块，或接受代价并在 docstring 说明。

- [ ] **`Editor.message()` 相比旧版丢两处行为** — [`editor.py:303-305`](../../yate/editor.py#L303-L305)
  旧版写消息后调 `status_bar.refresh_status()` 且有 `mounted` 守卫；新版仅 `prompt_bar.write`，
  扩展经 `api.message` 提示时 mode chip 可能短暂过期、未挂载时直接写入。
  **修复**：恢复 `refresh_status()` 并按 `self.mounted` 分流缓冲。

- [ ] **三个公共方法缺 docstring** —
  [`editor.py:439`](../../yate/editor.py#L439)、[621](../../yate/editor.py#L621)、[1190](../../yate/editor.py#L1190)
  `new_buffer` / `insert_char` / `close_completion`，违反规范 §2.1。

- [ ] **新建代码用遗留 `Dict`/`List` 泛型** — [`registries.py:17,38,58`](../../yate/registries.py#L17-L58)
  违反 §3.2「新代码不使用 Dict/List」；同文件 62/71/79 行已是小写泛型，风格自相矛盾。

- [ ] **行宽超 100 上限** — [`vim.py:106`](../../yate/keymaps/vim.py#L106)（102 字符）、
  [`actions.py:38,70-71`](../../yate/actions.py#L70-L71)（102/105/108 字符）

- [ ] **F 键 dispatch 失败时行为不一致** — [`vim.py:122-128`](../../yate/keymaps/vim.py#L122-L128)
  扩展绑定的 F 键 action 失效时 `return dispatch(...)` 让 False 上抛冒泡，而
  `_extension_binding` 同类 False 在 421 行被 `return True` 吸收。影响面小（仅扩展失效场景）。

- [ ] **trust 存储权限保证与注释不符** — [`trust.py:61-68`](../../yate/services/trust.py#L61-L68)
  `0o700` 仅在目录**新建**时生效，已存在的宽松目录不收紧；store 文件本身按默认 umask（0644）
  创建，信任列表对同机其他用户可读；Windows 忽略 mode（平台限定）。
  **修复**：已存在目录时 `os.chmod`（POSIX），或修正注释。

- [ ] **rc 声明路径即 bundled 目录时产生假 shadowed 警告** —
  [`extensions.py:489-499`](../../yate/services/extensions.py#L489-L499)
  同一 resolved path 去重返回自身记录，`owner == record` 仍触发「shadowed by the bundled default」。
  **修复**：比较 `owner.path.resolve() != record.path.resolve()` 再告警。

- [ ] **explorer 混用 `X | None` 与 `Optional[X]`** —
  [`explorer.py:124,146-148,157,163`](../../yate/editor_view/explorer.py#L124-L163)
  新增签名用 `| None`，同文件 prompt 流用 `Optional`，违反 §3.2。**修复**：统一 `Optional[...]`。

- [ ] **palette 提示列对齐用 `len()` 而非 cell 数，CJK 文件名错位** —
  [`palette.py:266`](../../yate/editor_view/palette.py#L266)
  `pad = max(1, 30 - len(display))`，宽字符占 2 cell 导致 hint 列逐行左移。
  **修复**：改 `theme.cell_len(display)`。

- [ ] **Windows `os.replace` 对外部占用句柄的兼容面变窄** —
  [`document.py:149`](../../yate/editor_core/document.py#L149)
  需 `FILE_SHARE_DELETE`；杀软/预览器持句柄时旧版能存、新版抛 `PermissionError`
  （错误路径安全，无数据丢失，Windows 限定）。

- [ ] **首次保存的新文件权限 0600（POSIX 限定）** —
  [`document.py:140-148`](../../yate/editor_core/document.py#L140-L148)
  mkstemp 恒 0600 且 `copystat` 仅在目标存在时调用；新文件落盘 owner-only，旧实现走 umask(0644)。
  **修复**：目标不存在时 `os.chmod(tmp, 0o666 & ~umask)`。

- [ ] **保存路径两个罕见边角** — [`document.py:144-152`](../../yate/editor_core/document.py#L144-L152)
  ① `os.fdopen(fd)` 本身抛错时 fd 泄漏；② except 内 `tmp.unlink` 若抛错会顶掉原始异常
  （`__context__` 仍留痕）。**修复**：fdopen 移入 try；unlink 包 try/except OSError。

- [ ] **symlink/硬链接语义变化未声明** —
  [`document.py:147-149`](../../yate/editor_core/document.py#L147-L149)
  `os.replace` 把符号链接**本体**替换为普通文件（旧实现写穿透到目标），硬链接分叉。
  **修复**：保存前 resolve，或文档注明行为变化。

- [ ] **过时注释与已落地行为矛盾** —
  [`test_app_textual.py:3781-3786`](../../tests/test_app_textual.py#L3781-L3786)
  注释仍称原子写是「separate hardening change」，实际已实现。
  **修复**：更新注释并断言磁盘字节完好。

- [ ] **`except BaseException:` 缺理由注释** —
  [`pty_proc.py:78`](../../yate/editor_term/pty_proc.py#L78)、
  [`document.py:150`](../../yate/editor_core/document.py#L150)
  同文件其他宽捕获均有理由注释，这两处没有（re-raise 不吞异常，纯风格）。

**存量（非本分支引入，大改文件中未顺手消除）（10 条）：**

- [ ] **操作符删除（`dw`/`d$`）不写寄存器，`p` 粘贴旧内容** —
  [`vim.py:477-490`](../../yate/keymaps/vim.py#L477-L490)
  `buf.delete_selection()` 返回值被丢弃且该方法不自设 register；对照 visual 路径
  （vim.py:217-219）显式写 `buf.register`。复现：`yy` → 移动 → `dw` → `p` 粘出旧行。
  **修复**：同 visual 路径捕获返回值写寄存器。*存量（旧 vim.py 相同），影响真实故保留登记。*

- [ ] **PTY 启动失败后终端永久空白无法复活** —
  [`terminal.py:104-121`](../../yate/editor_view/terminal.py#L104-L121)
  `self.proc = proc` 在 `await proc.start()` **之前**赋值；spawn 失败只 settle future 不调
  `_on_exit`，`dead` 恒 False → `started` 恒 True → 重生分支永不触发，只能重启应用。
  *存量（旧 terminal.py 逻辑相同）；本分支把 spawn 生命周期收进新写的 `TerminalPanel`，
  恢复契约已是新代码职责。**修复**：`spawn_shell` 失败分支复位 `proc=None`/`dead=True`。*

- [ ] **`add_binding` 覆盖 `_index` 但旧 binding 残留，help 双条目** —
  [`keymaps/base.py:229-240`](../../yate/keymaps/base.py#L229-L240)
  modals 帮助遍历 `bindings` 列表，同 raw key 展示两条。*存量。*

- [ ] **visual 模式 `gg` 永不跳转，条件为死代码** —
  [`vim.py:240-245`](../../yate/keymaps/vim.py#L240-L245)
  `pending` 恒空且 `"g"` ∈ `_MOTION_CODES`，第二分支不可达。*存量。*

- [ ] **渲染热路径每行重复查询 LSP 诊断两次** —
  [`editor_view/editor.py:424,576`](../../yate/editor_view/editor.py#L424-L576)
  `render_line` 与 `_diagnostic_underlines` 对同一行各查一次（每次遍历全诊断）。
  *存量；本轮大改该文件，可顺手把结果传参消除。*

- [ ] **文档搜索每按键全量重渲染所有块 widget，无防抖** —
  [`manual.py:341-379`](../../yate/editor_view/manual.py#L341-L379)
  大文档输入卡顿。*存量。* **修复**：仿 `EditorView._HIGHLIGHT_DEBOUNCE_S` 用 `call_later` 防抖。

- [ ] **失败扩展模块残留 `sys.modules`** —
  [`extensions.py:389-423`](../../yate/services/extensions.py#L389-L423)
  `exec_module` 抛异常后不清理。*存量。*

- [ ] **`bind_key` 的 keymap 名拼写错误静默无绑定** —
  [`extensions.py:290-301`](../../yate/services/extensions.py#L290-L301)
  `keymaps.get(target)` 返回 None 直接跳过无提示。*存量。*

- [ ] **L0 config 惰性 import L2 `editor_view.theme`，层级方向违规** —
  [`config.py:171-173`](../../yate/config.py#L171-L173)
  存量耦合仅改为惰性；建议后续下沉或注入回调，并在架构规则中登记（类似 R11 冻结）。

- [ ] **`visible_tree` 递归无 symlink 环防护** —
  [`workspace.py:255-272`](../../yate/services/workspace.py#L255-L272)
  同轮已修 `walk_files`，此递归路径未覆盖，展开指向祖先的链接可栈溢出。*存量，Windows 影响有限。*

### 💡 Suggestion（12 条）

- [ ] **`KeymapSet` 空字典时抛裸 `StopIteration`** —
  [`keymaps/registry.py:19-21`](../../yate/keymaps/registry.py#L19-L21)
  显式 `raise ValueError(...)` 更可定位。
- [ ] **两个无关类型同名 `Action`**（callable 别名 vs dataclass）—
  [`base.py:160`](../../yate/keymaps/base.py#L160) / [`registries.py:26`](../../yate/registries.py#L26)，
  扩展作者易混淆；别名可改 `ActionFunc`。
- [ ] **`if key == "o": pass` 死代码** — [`vim.py:372-373`](../../yate/keymaps/vim.py#L372-L373)。*存量。*
- [ ] **`dg`/`yg` 空 motion 仍报 "deleted"/"yanked"** —
  [`vim.py:303-321`](../../yate/keymaps/vim.py#L303-L321)：`"g"` 应排除出操作符 motion。
- [ ] **`handle_key` docstring「every check is pure」不实** —
  [`editor.py:529-535`](../../yate/editor.py#L529-L535)：
  `try_window_prefix` 变更 `_window_pending`、popup 分支执行 `accept_completion`；当前无双重派发，
  但该表述会误导后续维护者。
- [ ] **`PromptBar.on_cancel` 属性名落入 Textual `on_*` 反射命名空间** —
  [`commandline.py:213`](../../yate/editor_view/commandline.py#L213)
  实例属性非类方法、当前无冲突消息，纯命名隐患；可改 `cancel_hook`。
- [ ] **`score += 0  # consecutive: best` 死语句** —
  [`palette.py:58-59`](../../yate/editor_view/palette.py#L58-L59)。
- [ ] **删除最后选中项后 `_last_selected` 悬挂** —
  [`explorer.py:107,119-123`](../../yate/editor_view/explorer.py#L107-L123)
  `_restore_cursor` 未命中时清 `None`。
- [ ] **内部导入组非字母序** — [`extensions.py:49-53`](../../yate/services/extensions.py#L49-L53)。
- [ ] **trust.py 全用 `Path | None`**（[`trust.py:27,50,71`](../../yate/services/trust.py#L27-L71)）
  与规范 `Optional[X]` 不一致（与 Minor 的 explorer 条目同类，合并修）。
- [ ] **dirty 状态下每次 `modified` 查询 O(N) tuple 分配** —
  [`document.py:86-88`](../../yate/editor_core/document.py#L86-L88)
  状态栏每键查询；可按 `content_edits` 缓存上次判定（代码注释已自认知该权衡）。
- [ ] **harness 重写行沿用 `# type: ignore`** —
  [`harness.py:274-283`](../../tools/smoke_test/harness.py#L274-L283)
  工具代码沿旧模式；若属既定豁免，补理由注释归档。

### 四维度结论

| 维度 | 结论 |
|---|---|
| **功能正确性** | 4 处 Major 回归（M1–M4）+ 2 处存量功能缺陷（操作符寄存器、PTY 失败卡死）；其余逻辑与旧 app.py 逐段比对忠实：`close_tab` LSP 通知经 session 回调等价、`content_edits` 记账推演自洽、search clamp 正确、补全防抖与按键分工无吞键回归。 |
| **性能** | 无新增深循环/重复计算。`modified` O(N) 兜底与 `manual` 无防抖为存量；`render_line` 重复查诊断为存量可顺手消；fc-cache 带 timeout 不阻塞。 |
| **可读性可维护性** | docstring 质量整体高（散文式 + Sphinx 引用）；日志全部 `%` 占位、无裸 except 漏注释（除 2 处 BaseException）；瑕疵集中在缺 docstring ×3、遗留泛型、行宽、死代码 ×3、过时注释 ×1。 |
| **设计质量** | R1–R11 全部合规：app.py 薄壳、R7 装载点正确、R9 id 全由 Editor 传入、R10 无二次派发（含新增的「未知 action 报错 fall-through」路径经调用链核实安全）、R2/R6 零违规、`__init__.py` 惰性达成。原子写方向正确、失败恢复完整；缺口为 mtime/权限/句柄三个边角。存量方向违规仅 config→editor_view 一处（已登记）。 |

### 验证与置信度说明

- 每条问题经 **2 个独立验证员**复核（存在性 + 严重级 + 误报排除）；分歧处理：
  操作符寄存器 / PTY 失败两条因属存量由 Major 降级 Minor（保留，因影响真实且触及新代码契约）；
  新文件 0600 因 POSIX-only 降级 Minor；`PromptBar.on_cancel` 因实例属性不进 Textual 类扫描保持
  Suggestion；`vim.py:106` 行宽由主代理实测 102 字符裁定成立。
- 全部 4 条 Major 由主代理**亲自读码核实**（非仅引用子代理结论）。
- 排除项：验证中发现但不足以成条的表达问题（如「同文件他处均有 noqa」对 document.py
  不准确）已修正表述，无整条剔除。
