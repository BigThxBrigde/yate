# yate Code Review — 全量代码审查 — 2026-09-16

## 全量代码审查 — 2026-09-16

> **2026-09-23 复核**：对照当前代码逐条核实（其间完成 L4→L0 分层重构，原
> `app_features/*` 路径已迁移）。已修复的条目标记 `[x]` 并附证据；经核实
> 不再成立的条目收录在文末「已失效条目」章节。
>
> **修复计划**（位于
> `.trae/documents/code-review-fix-plans/`；2026-09-24 起随状态复核更新，
> 已修复 / 方案变更 / 补入条目均标注在各计划内）：
>
> - Critical → [code_review_fix_critical_plan_a.md](../documents/code-review-fix-plans/code_review_fix_critical_plan_a.md)
> - Suggestion → [code_review_fix_suggestions_plan_b.md](../documents/code-review-fix-plans/code_review_fix_suggestions_plan_b.md)
> - Nice-to-have → [code_review_fix_nice_to_have_plan_c.md](../documents/code-review-fix-plans/code_review_fix_nice_to_have_plan_c.md)

### 🔴 Critical（必须修复）→ 计划：[P0](../documents/code-review-fix-plans/code_review_fix_critical_plan_a.md)

- [x] **`:wq` 保存失败时仍退出，导致数据丢失** — `app_features/commands.py:54`
  `_wq` 调用 `save_document()` 后无条件 `quit(force=True)`。若保存失败（无路径、用户取消、权限错误），`force=True` 跳过未保存检查直接退出，丢失工作内容。
  **修复：** 保存失败时检查 `doc.modified` 或让 `save_document` 返回成功标志，仅在保存成功时退出。

- [x] **补全弹窗过期检查仅比较行号，可能导致文本损坏** — `app_features/completion.py:121`
  LSP await 返回后仅检查 `buf.row != row`。若用户在同一行继续输入（列号变化），过期补全仍显示，接受后 `replace_range` 使用过时坐标。
  **修复：** 同时比较 `col` 和/或前缀文本。

- [x] **文件夹删除关闭标签时未通知 LSP** — `app_features/explorer.py:107`
  删除文件夹导致已打开标签关闭时，文档从 `app.docs` 移除但未调用 `lsp.on_document_closed()`，LSP 服务器保留过时的 `didOpen` 状态。
  **修复：** 遍历被关闭的文档并调用 `lsp.on_document_closed()`。

- [x] **LSP `_read_loop` 未捕获所有异常，导致请求永久挂起** — `editor_lsp/client.py:345`
  意外错误（OSError、ValueError 等）会静默终止读取循环，而客户端仍保持 `READY` 状态，所有待处理请求永久挂起。
  **修复：** 在 `_read_loop` 中添加 `except Exception` 捕获，触发客户端状态转为 `FAILED`。
  *✅ 已修复（2026-09-24，提交 `e5a3001`）— [client.py:429-465](../../yate/editor_lsp/client.py) 失败收尾
  提取为 `_fail_pending()`，`_read_loop` 增加 `except Exception` 兜底（`log.exception` + fail pending）
  并在 `finally` 对非 STOPPED 退出统一置 `FAILED`；`start_request` 在 FAILED 态直接拒绝新请求。
  守卫 `test_malformed_frame_marks_failed_and_fails_requests`（畸形帧 → FAILED、在途请求以异常
  结束、后续请求立即失败）。*

- [x] **LSP `register_server` 竞态条件** — `editor_lsp/manager.py:118`
  取消正在进行的启动任务是 fire-and-forget 方式。被取消任务的 `finally` 块可能稍后移除新替换任务在 `_starting` 中的条目，导致其失去跟踪。
  **修复：** 在取消前检查任务是否为当前活跃任务，或使用取消安全的方式清理。
  *✅ 已修复（2026-09-24，提交 `dc1f3ac`）— [manager.py:227-235](../../yate/editor_lsp/manager.py)
  `ensure_client` 收尾改为 identity 条件弹出（「谁跟踪谁清」），被取消路径的清理仍由
  `register_server` 同步过滤完成。守卫 `test_register_replace_race_keeps_new_starting_task_tracked`
  （慢启动中途替换配置：旧任务被取消、新任务条目不被旧收尾弹掉、并发只产生一个 client）。*

- [x] **`replace_all` 修改行后未钳制光标位置** — `editor_core/search.py:148-170`
  批量替换后光标列号可能超出新的（更短的）行长度。在下次重绘前读取 `buffer.col` 的代码会看到无效位置。
  **修复：** 替换循环结束后钳制光标：`c = min(c, len(buffer.lines[r]))`。
  *✅ 已修复（核实 2026-09-24）— [search.py:143-151](../../yate/editor_core/search.py) 替换循环结束
  后、记录 undo 前做 `min(col, len(line))` 钳制；守卫为冒烟 harness 的全局 `invariant:cursor_col`。*

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

- [x] **命令面板 CJK 字符对齐错误** — `editor_view/palette.py:178`
  使用 `len(display)` 而非 `theme.cell_len(display)` 计算填充。CJK 字符（2 单元格宽）导致提示列错位。
  **修复：** 改用 `cell_len()` 计算显示宽度。
  *✅ 已修复（2026-09-24）— [palette.py:266-268](../../yate/editor_view/palette.py) 已改用
  `theme.cell_len(display)`（同记录于下文 2026-09-24 审查 Minor 段）。*

- [x] **发布工具硬编码 `"master"` 分支** — `tools/release/cli.py:~186`
  `git_push(repo, "master")` 在使用 `main` 或其他默认分支的仓库上会失败——且此时所有昂贵操作（bump、changelog、gate、tag）已经完成。
  **修复：** 动态检测默认分支，或接受 `--branch` 参数。
  *✅ 已修复（2026-09-24）— [cli.py:188-201](../../tools/release/cli.py) 新增 `_default_branch()`
  （symbolic-ref 检测 `origin/HEAD`，`GitError` → None 不猜测）；[cli.py:262-267](../../tools/release/cli.py)
  push 前 `branch or _default_branch(repo)`，不可判定则 RuntimeError `cannot determine the default
  branch; pass --branch`；`main()` 暴露 `--branch`。守卫 `tests/test_release_tool.py` 四条
  （检测 / 无 origin / 中止不 push / 透传）。*

- [x] **Changelog `check` 和 `zh-commit` 忽略 `overrides_path`** — `tools/changelog/cli.py`
  这两个子命令始终使用 `DEFAULT_OVERRIDES_PATH`，`--overrides` 参数被静默忽略。
  **修复：** 将 `overrides_path` 一致地传递给所有子命令函数。
  *✅ 已修复（2026-09-24）— [cli.py:270-294](../../tools/changelog/cli.py) generate / check /
  zh-commit 三个子命令 parser 均暴露 `--overrides`，main() 统一解析并透传 `overrides_path`
  （实测 generate 的 parser 同样缺失，按本条目「所有子命令」口径一并补齐）。守卫：
  `test_check_overrides_flag_is_honored` / `test_zh_commit_overrides_flag_writes_custom_file` /
  `test_generate_overrides_flag_renders_translations`。*

---

### 🟡 Suggestion（建议修复）→ 计划：[P1](../documents/code-review-fix-plans/code_review_fix_suggestions_plan_b.md)

- [x] **正则模式每次 tokenize 重新编译** — `editor_syntax/regex_backend.py:570`
  每次 `tokenize_document` 调用都重新构建并编译主正则。spec 不可变，结果始终相同。
  **建议：** 按 filetype 缓存编译后的模式。
  *复核：仍存在 — [regex_backend.py:412-431](../../yate/editor_syntax/regex_backend.py) `_code_line_pattern(spec)` 每次调用重建并 `re.compile`，无缓存。*
  *✅ 已修复（2026-09-24）— [regex_backend.py](../../yate/editor_syntax/regex_backend.py) `_code_line_pattern` 加 `@lru_cache(maxsize=None)`（`LangSpec` 为 frozen dataclass 全不可变字段，specs 注册表单例无泄漏风险）；守卫 `test_code_line_pattern_is_cached_per_spec`。*

- [x] **配置模式布尔值正则每行编译 7 次** — `editor_syntax/regex_backend.py:647`
  `_tokenize_config_line` 中为 7 个布尔值单词各编译一次正则。
  **建议：** 预编译为单一交替模式 `_CONFIG_BOOL_RE`。
  *复核：仍存在 — [regex_backend.py:674-676](../../yate/editor_syntax/regex_backend.py) 仍在循环内逐词构造模式。*
  *✅ 已修复（2026-09-24）— [regex_backend.py](../../yate/editor_syntax/regex_backend.py) 模块级 `_CONFIG_BOOL_RE` 预编译交替模式替换循环内编译；守卫 `test_config_bool_words_match_on_word_boundaries_only`（on/off/yes/no 命中、`only` 词内不命中）。*

- [x] **`Document.modified` 每次访问执行 O(n) 字符串比较** — `editor_core/document.py:82`
  每次访问调用 `get_text()` 并比较全文。UI 可能在每个渲染周期读取此属性。
  **建议：** 使用 `_dirty` 标志或按 `content_version` 缓存结果。
  **已修复（2026-09-23，提交 `05106d5` + `5190225`）：** 改为 `content_edits` 编辑计数 O(1) 快路径 + 行元组精确回退，跨 undo/redo 恒精确；`_Edit.weight` 保证合并打字场景计数对齐。

- [x] **`create()` 同步打开新文件** — `app_features/explorer.py:82`
  应使用 `open_path_later()` 保持一致性。
  *复核：仍存在 — [explorer.py:385-387](../../yate/editor_view/explorer.py) 仍同步调用 `self.open_path(target)`。*
  *✅ 已修复（核实 2026-09-24，免实施）— explorer 的 `open_path` 协作者在接线层已注入异步形态（[editor.py:156](../../yate/editor.py)、:214、:1348 三处均为 `open_path=self.open_path_later`），explorer.py 内 `self.open_path(target)` 调用点保持原样即正确形态，无需改动。*

- [x] **`_original_excepthook` 在导入时捕获** — `crash.py:32`
  应在 `install()` 内部捕获，避免导入顺序问题。
  *复核：仍存在 — [logs.py:278-280](../../yate/logs.py) `CrashService` 构造时捕获 `sys.excepthook`，注释标明 import time。*
  *✅ 已修复（2026-09-24）— [logs.py](../../yate/logs.py) `CrashService.__init__` 不再触碰 `sys.excepthook`（初始 `None`），捕获延迟到 `install()` 首次调用、`uninstall()` 恢复 install 时刻值；守卫 `test_install_chains_to_and_restores_a_hook_installed_after_import`。*

- [x] **宽字符（CJK）在最后一列被静默丢弃** — `editor_term/emulator.py:315`
  应换行到下一行显示，而非丢弃。
  *复核：仍存在 — [emulator.py:426-430](../../yate/editor_term/emulator.py) 宽字符到达最后一列仅设 autowrap 标记即返回，未实际换行。*
  *✅ 已修复（2026-09-24）— [emulator.py](../../yate/editor_term/emulator.py) 宽字符到达末列且 DECAWM 开时：末列写空占位 → `_index()` 立即换行 → 新行 col 0 完整放置（宽字符物理放不进末列，无法延迟换行；DECAWM 关闭与行中间路径不变）；守卫 `test_wide_character_at_the_last_column_is_drawn_on_the_next_line` 等三条。*

- [x] **`fc-cache` 使用 `shell=True`** — `services/fonts.py:230`
  不必要且可移植性差。
  **建议：** 使用列表参数直接调用。
  *✅ 已修复（2026-09-24，PR #13 审查修复）— [fonts.py:267-283](../../yate/services/fonts.py)
  改列表参数 + `timeout=10`，失败记 `log.debug`（守卫见下文 PR #13 段）。*

- [x] **补全解析器中存在未使用变量** — `editor_lsp/manager.py:520`
  `kind_raw` / `sort_raw` 未使用。
  **已修复（核实 2026-09-23）：** [manager.py:537-544](../../yate/editor_lsp/manager.py) 两个变量现已参与 `kind=` / `sort_text=` 的类型窄化。

- [x] **Vim `e` 动作不跳过词间空白** — `keymaps/vim.py:295`
  与真实 vim 行为不一致。
  **已修复（核实 2026-09-23）：** [buffer.py:56-69](../../yate/editor_core/buffer.py) `word_end()` 先跳过空白再找词尾，vim `e` 动作基于该实现。

- [x] **`_exit_code` 对"仍活跃"和"API 失败"均返回 `None`** — `editor_term/pty_proc.py:495`
  语义模糊，应区分两种状态。
  *复核：仍存在 — [pty_proc.py:557-566](../../yate/editor_term/pty_proc.py) `STILL_ACTIVE` 与 `GetExitCodeProcess` 失败均返回 `None`。*
  *✅ 已修复（2026-09-24）— [pty_proc.py](../../yate/editor_term/pty_proc.py) 新增 `ExitState = Union[int, Literal["running", "failed"]]` 与三态方法 `_exit_code_or_failed()`，公开 `_exit_code()` 改为兼容包装（`Optional[int]` 签名不变）；校准：计划所称「L533 状态栏轮询」实为 `read_loop` 收尾的退出码查询；守卫为 ConPTY 三态各一条（Windows-only skip）。*

- [x] **递归 `walk_files` 可能超出递归限制** — `services/workspace.py:185`
  极深目录树会触发 `RecursionError`。
  **建议：** 改用迭代方式（`os.walk` 或显式栈）。
  *复核：部分修复 — 符号链接环已防护（2026-09-23，提交 `a89a720`，[workspace.py:244-248](../../yate/services/workspace.py)）；但实现仍为嵌套递归函数，极深目录的递归深度风险未变。*
  *✅ 已修复（2026-09-24）— [workspace.py](../../yate/services/workspace.py) `walk_files` 与 `visible_tree` 均改显式栈迭代（严格保持原 DFS 前序：目录优先、`name.lower()`），`visible_tree` 补齐 symlink 环防护；守卫：1500 层深链不炸（合成虚拟链构造，跨平台可跑）+ 真实 symlink 环用例。*

- [x] **`diagnostics_on_line` 每行渲染调用两次** — `editor_view/editor.py:440`
  一次用于 gutter 标记，一次用于下划线。
  **建议：** 计算一次并作为参数传递。
  *复核：仍存在 — [editor.py:424-427](../../yate/editor_view/editor.py) 与 [editor.py:571-590](../../yate/editor_view/editor.py) 各调一次。*
  *✅ 已修复（2026-09-24）— [editor.py](../../yate/editor_view/editor.py) `render_line` 行内查一次 `line_diags` 后下传 gutter 与 `_diagnostic_underlines`（单行渲染 2 次→1 次，按降级策略落地——widget 层无逐帧钩子）；守卫 `test_render_line_queries_diagnostics_once_per_row`。*

- [x] **`_welcome_lines()` 每次渲染重建** — `editor_view/editor.py:506`
  内容仅在 keymap 变化时改变，应缓存。
  *复核：仍存在 — [editor.py:495-510](../../yate/editor_view/editor.py) 无缓存。*
  *✅ 已修复（2026-09-24）— [editor.py](../../yate/editor_view/editor.py) `_welcome_lines` 改实例方法并按 `(theme.name, vim_keys)` 缓存（缓存键较原策略多一维主题，防主题切换返回旧色）；守卫 `test_welcome_rows_cached_per_theme_and_keymap`。*

- [x] **丢弃后未清除过期 highlight keys** — `editor_view/editor.py:365`
  导致即使没有待处理编辑也强制 80ms 防抖延迟。
  *复核：仍存在 — [editor.py:346-357](../../yate/editor_view/editor.py) discard 路径只清 scheduled key，未清 `_hl_tokens/_hl_doc/_hl_version/_hl_filetype`。*
  *✅ 已修复（2026-09-24）— [editor.py](../../yate/editor_view/editor.py) discard 分支 `refresh()` 后追加 `_schedule_highlight(0.0)` 立即重排、跳过多余防抖窗口（旧 `_hl_tokens` 继续上色的防闪白设计保留，未清缓存）；守卫 `test_discarded_highlight_pass_reschedules_immediately`（不等 0.08s）。*

- [x] **`_cursor_anchor()` 每行渲染调用 3+ 次** — `editor_view/editor.py:131`
  每次调用重新遍历 pane 树评估 `is_active_view`。
  **建议：** 计算一次并传递。
  *复核：仍存在 — [editor.py:151-158](../../yate/editor_view/editor.py) 渲染路径多处各自调用。*
  *✅ 已修复（2026-09-24）— [editor.py](../../yate/editor_view/editor.py) `render_line` 行内 cursor/anchor 算一次，下传 `_selection` 与 `_row_style_ranges`（每行 3 次→1 次，与 S12 同模式）；守卫 `test_render_line_computes_cursor_anchor_once_per_row`。*

- [x] **死条件分支** — `editor_view/terminal.py:251`
  `cell.char if cell.char != ' ' else ' '` 两个分支相同——重构残留。
  *复核：仍存在 — [terminal.py:280](../../yate/editor_view/terminal.py) 恒等分支原样保留。*
  *✅ 已修复（2026-09-24）— [terminal.py](../../yate/editor_view/terminal.py) 简化为 `cell.char`，删除恒等分支；终端渲染用例全绿。*

- [x] **冗余滚动恢复** — `editor_view/panes.py:415`
  `reconcile` 为活动叶子恢复滚动，但 `apply_doc`（调用方）已经做过。
  *复核：仍存在 — [panes.py:474-483](../../yate/editor_view/panes.py)。*
  *✅ 已修复（2026-09-24；缺口与二次竞态补全 2026-09-25）— [panes.py](../../yate/editor_view/panes.py) reconcile 恢复循环跳过 focus 叶子（split/close/only 调用方均随后 `apply_doc` 恢复活动叶子，重复仅此一份），守卫 `test_split_close_restores_scroll_for_focus_and_inactive_leaves`；守卫探明的 mount 期存量缺口（首次 layout 前 `scroll_to` 被 Textual 钳回原点）已修复：新增 `PaneHost.restore_scroll` 重试至落点到位，reconcile 与 `apply_doc` 统一走它；同日全量验证抓到的二次竞态（视图已测得但延迟 `_scroll_to` 未落地时 `capture_active` 回写占位 0）以 `PaneManager.pending_restores` 登记在途叶子修复；守卫升级为直接断言 close 后 `scroll_offset.y == saved`，连跑 3 遍无抖动。*

- [x] **`id(document)` 作为字典键存在风险** — `editor_view/panes.py:32`
  若文档被 GC 且地址复用，会取到过期状态。
  **已修复（核实 2026-09-23）：** [session.py:250-254](../../yate/session.py) 已改用稳定的 `Document.uid` 作为 view state 字典键。
  *链接校准（文档整理时核对）：原指向 `yate/editor_view/pane_types.py`，该模块后续已删除并并入
  `yate/session.py`（`ViewState` 与窗格树操作一并迁入），故改为 `session.py`。*

- [x] **`_FakePtyImpl.instances` 是类级可变状态** — `tests/test_terminal.py`
  测试间可能泄漏。
  **建议：** 使用 fixture 作用域列表或 `monkeypatch.setattr`。
  **已修复（核实 2026-09-23）：** [test_terminal.py:268-311](../../tests/test_terminal.py) fixture 已在每个测试前重置 `instances` 并 monkeypatch PTY 实现，泄漏路径已消除。

- [x] **测试生成 30 秒 sleep 子进程** — `tests/test_lsp.py`
  清理失败时有孤儿进程风险。
  **建议：** 使用更短的 sleep 或自终止脚本。
  *复核：仍存在 — [test_lsp.py:847](../../tests/test_lsp.py) 仍 `time.sleep(30)`。*
  *✅ 已修复（2026-09-24）— [test_lsp.py](../../tests/test_lsp.py) 改 `time.sleep(2)` 自终止脚本，等 STARTING 上限收窄至 1.5s、`wait_for(proc.wait(), 4.0)`；清理失败路径的暴露窗口从 30s 收窄到 ~2s（目标用例实测 0.23s）。*

- [x] **硬编码版本号 `"0.2.4"`** — `tests/test_theme_palettes.py`
  每次发版需手动更新。
  **建议：** 添加 semver 可解析断言，或交叉引用发布工具。
  *复核：仍存在 — [test_theme_palettes.py:271](../../tests/test_theme_palettes.py) 仍 `assert yate.__version__ == "0.2.4"`。*
  *✅ 已修复（2026-09-24）— [test_theme_palettes.py](../../tests/test_theme_palettes.py) 改 `re.fullmatch(r"\d+\.\d+\.\d+", yate.__version__)` + 非空校验，与发版解耦；`test_pyproject_keeps_the_single_dynamic_version_source` 保留。*

- [x] **`generate()` 使用 `date.today()` 导致输出不可复现** — `tools/changelog/cli.py`
  **建议：** 接受可选 `date` 参数。
  *复核：仍存在 — [cli.py:92](../../tools/changelog/cli.py) 仍 `datetime.date.today()`，CLI 无 `--date`。*
  *✅ 已修复（2026-09-24）— [cli.py](../../tools/changelog/cli.py) `generate(..., date: Optional[str] = None)` + CLI `--date YYYY-MM-DD`，未给时保持 `today()`（行为不变）；守卫 `test_generate_date_option_stamps_generated_notes` / `test_generate_cli_date_flag_is_honored`。*

- [x] **`--limit` 标志无测试** — `tests/test_changelog_tool.py`
  *复核：仍存在 — CLI 已有 `--limit`（[cli.py:251](../../tools/changelog/cli.py)），测试文件无对应用例。*
  *✅ 已修复（2026-09-24）— 守卫 `test_generate_limit_1_keeps_only_the_newest_commit`（并断言两次 `read_commits` 均转发 limit=1）、`test_generate_limit_zero_and_negative_forwarded_verbatim`（实测固化：`limit=0` → 空条目文档、`limit=-1` → 全部条目，git log -n 语义）。*

- [x] **大小写不敏感匹配机制未文档化** — `tests/test_workspace_filter.py`
  **已修复（核实 2026-09-23）：** [test_workspace_filter.py:160-164](../../tests/test_workspace_filter.py) 已有专门用例 `test_matching_is_case_insensitive` 固化该行为。

- [x] **`position` 变量名用于两个不同概念** — `tools/changelog/segments.py`
  **建议：** 重命名循环变量为 `seg_index`。
  *复核：仍存在 — [segments.py:102](../../tools/changelog/segments.py)（段序号）与 [segments.py:122](../../tools/changelog/segments.py)（commit 位置）同名。*
  *✅ 已修复（2026-09-24）— [segments.py](../../tools/changelog/segments.py) 循环变量改名 `seg_index`（L102-114），commit 拓扑位置 `position` 保持；纯重命名零行为变化，changelog 53 用例全绿。*

- [x] **subject 字段可能包含嵌入的字段分隔符** — `tools/changelog/gitdata.py`
  理论上的问题，实际极不可能。
  *复核：仍存在（理论性）— body 经 `maxsplit` 保留杂散分隔符，subject 字段本身无防护。*
  *✅ 已修复（2026-09-25，P2 波次一 SP4）：按实现固化——`maxsplit=4` 处补一行注释说明边界（subject 内嵌 `\x1f` 被截断进 body），一条固化用例 `test_parse_log_output_subject_with_stray_separator_truncates_into_body`；零解析逻辑变更。*

- [x] **`files_dirty` 路径解析可能误处理前导空格** — `tools/release/cli.py`
  *复核：仍存在 — [cli.py:63-75](../../tools/release/cli.py) 解析逻辑未变。*
  *✅ 已修复（2026-09-24）— [cli.py](../../tools/release/cli.py) `files_dirty` 改 `git status --porcelain -z` NUL 分隔解析（路径 verbatim，R/C 记录消耗第二 NUL 字段，实测新路径在前），返回签名不变；守卫 `test_files_dirty_returns_verbatim_paths_from_a_real_repo` / `test_files_dirty_consumes_z_rename_records_and_keeps_quotes`。*

- [x] **测试深度访问私有 highlight 属性** — `tests/test_app_textual.py`
  与实现紧耦合，重构时易碎。
  **建议：** 暴露窄接口（如 `HighlightProbe` protocol）。
  *复核：仍存在 — [test_app_textual.py:204-314](../../tests/test_app_textual.py) 仍直接断言 `_hl_tokens` 等私有属性。*
  *✅ 已修复（2026-09-24）— [editor.py](../../yate/editor_view/editor.py) 新增公开 `highlight_probe()`（`HighlightProbe` frozen dataclass 只读快照，含 tokens/doc/version/filetype/scheduled_key/timer）与公开 `tokens_for(row)`；[test_app_textual.py](../../tests/test_app_textual.py) 全部 30 处私有访问迁移至探针，`cast(Any, editor)` 已删除（无 Protocol，合规 R2）。*

- [x] **`_FakeApp` 未实现所有 app hooks** — `tests/test_editor_core.py`
  新增 keymap action 调用未实现方法时会抛 `AttributeError`。
  *复核：仍存在 — [test_editor_core.py:394-406](../../tests/test_editor_core.py) 仍为最小 stand-in（已有 docstring 说明边界）。*
  *✅ 已修复（2026-09-24）— [test_editor_core.py](../../tests/test_editor_core.py) `_FakeApp` 加 `__getattr__`（非下划线名返回记录调用的 no-op，`_`/dunder 抛 AttributeError 防递归），docstring 注明「新 action 默认 no-op」；守卫：未实现 hook 可调且被记录、`_private` 仍抛 AttributeError。*

---

### 🟢 Nice-to-have（锦上添花）→ 计划：[P2](../documents/code-review-fix-plans/code_review_fix_nice_to_have_plan_c.md)

- [x] **保存始终使用 LF，忽略原始/平台换行符** — `editor_core/document.py:97`
  *复核：仍存在 — [document.py:50-53](../../yate/editor_core/document.py) 打开时统一归一为 LF，保存按 LF 写出。*
  *✅ 已修复（2026-09-25，P2 波次一 SP1）：Document 打开时记录主导 EOL（crlf/lf/cr，并列偏 CRLF），保存按其写回；新文件一律 LF。守卫：`test_save_round_trips_a_crlf_file_with_crlf_endings` 等 3 条；行为变更待用户在真实 CRLF 文件上人工确认。*

- [x] **配置模式 tokenizer 可能产生重叠 token** — `editor_syntax/regex_backend.py:636`
  *复核：仍存在 — `_tokenize_config_line` 各 `finditer` 独立发射，字符串内的数字/布尔词会重复着色。*
  *✅ 已修复（2026-09-25，P2 波次一 SP2）：`_CONFIG_TOKEN_RE` 单次交替扫描（string|number|bool，首字符互斥），消费式扫描天然不重叠；键名内数字/布尔词不再双着色。守卫：`test_config_number_inside_string_is_not_double_colored` 等 3 条。*

- [x] **共享库缺少符号时错误无上下文** — `editor_syntax/ts_backend/languages.py:172`
  *复核：仍存在（部分改善）— 依赖缺失已有清晰提示（[languages.py:218-221](../../yate/editor_syntax/ts_backend/languages.py)），但缺符号时 `getattr(dll, symbol)` 仍抛裸 `AttributeError`。*
  *✅ 已修复（2026-09-25，P2 波次一 SP2）：`getattr` 包 `try/except AttributeError`，`raise RuntimeError`（含库路径与符号名）`from exc`；`_FAILED` 缓存语义不变。守卫：`test_missing_symbol_error_includes_library_path_and_symbol`。*

- [x] **`_to_char` 中间字符字节偏移边界情况缺注释** — `editor_syntax/ts_backend/backend.py:115`
  *✅ 已补（2026-09-25，P2 波次一 SP2）：`_to_char` 补 docstring——多字节中间偏移经 `errors="ignore"` 丢弃不完整尾字符、映射到所切字符首列（纯注释，与既有用例实测行为逐字核对）。*

- [x] **Outdent 移除 `tab_width` 个空格而非回到上一个 tab stop** — `editor_core/buffer.py:277`
  *复核：基本仍存在 — [buffer.py:510-525](../../yate/editor_core/buffer.py) 已支持整 Tab 剥离，但空格缩进仍按 `tab_width` 移除而非对齐上一个 stop。*
  *✅ 已修复（2026-09-25，P2 波次一 SP1）：空格缩进改 `rrem = removed % tab_width` 对齐上一个 stop（3 空格→0、8 空格→4）；整 Tab 剥离不变。守卫 2 条。附带效应（符合策略本意）：1~3 空格从无操作变为归零。*

- [x] **`replace_current` 可用 `replace_range` 简化** — `editor_core/search.py:126`
  *复核：仍存在 — [search.py:102](../../yate/editor_core/search.py) 独立实现保留。*
  *✅ 已修复（2026-09-25，P2 波次一 SP1）：`replace_current` 改调 `buffer.replace_range`，重复实现删除；单步 undo 契约有守卫。语义校准：替换为空串从静默 no-op 变为删除匹配（与 `replace_all` 对齐；`replace_current` 无产品调用方，差异不可达）。*

- [x] **`_soft_reset`（ESC c）不退出备用屏幕** — `editor_term/emulator.py:250`
  *复核：仍存在 — [emulator.py:387-397](../../yate/editor_term/emulator.py) 未切换回主屏幕。*
  *✅ 已修复（2026-09-25，P2 波次一 SP3）：`_soft_reset` 入口调 `_set_alt_screen(False, save_cursor=False)` 回主屏（计划提名的 `_exit_alt_screen` 不存在，采用预授权的等价复位路径）。守卫：`test_soft_reset_in_alternate_screen_returns_to_primary`。*

- [ ] **ctrl+digit 绑定使用 kitty 协议，大多数终端不支持** — `keymaps/base.py:105`
  *复核：仍存在 — [base.py:118-121](../../yate/keymaps/base.py) 仍编码为 CSI-u。*
  *⏸ 暂缓（2026-09-25，P2 决策门 G1）：保留 kitty 现状，备注「待 KeyBinding 在 WT 重构后彻底修复」；届时与 N19 落地的 `FOCUS_EDITOR_KEY` 单点常量一并处理。*

- [x] **`cycle_tab` 允许空操作循环** — `app.py:453`
  *复核：仍存在 — [editor.py:476-484](../../yate/editor.py) 单 tab 时仅提示。*
  *✅ 已修复（2026-09-25，P2 波次二 SP6）：`cycle_tab` 入口判 `len(session.docs) <= 1` 静默 return（`session.cycle` 返回 None 仅此一种情形，改写等价）；多 tab 循环不变。守卫：`test_cycle_tab_with_single_tab_is_silent_noop`（原「断言有提示」用例按新行为改写）。*

- [x] **smoke test 工具自身无测试** — `tools/smoke_test/`
  *复核：仍存在 — `tests/` 下无 smoke 工具自测。*
  *✅ 已修复（2026-09-25，P2 波次一 SP4）：新建 [test_smoke_tool.py](../../tests/test_smoke_tool.py) 14 条——`select_scenarios` 5、`Reporter` 4、`extract_svg_rows` 4、场景超时 1（harness 端到端按约定不测）。*

- [x] **SVG 提取正则脆弱，依赖 Textual 版本** — `tools/smoke_test/testsuite.py`
  *复核：仍存在 — 提取仍基于 SVG 文本解析（[harness.py:130](../../tools/smoke_test/harness.py) `extract_svg_rows`）。*
  *✅ 已修复（2026-09-25，P2 波次一 SP4）：正则收紧至 Textual 8.2.8 实测格式并注释版本；新增 `SvgDriftError`——`<text` 出现数与匹配数不符时抛错并附 SVG 头部片段；收紧前做过新旧正则等价性验证（真实 SVG 17k 字符提取结果一致）。守卫 4 条。*

- [x] **单个场景执行无超时** — `tools/smoke_test/testsuite.py`
  *复核：仍存在 — 断言轮询有 5s 超时（`wait_until`），但场景整体执行无超时保护。*
  *✅ 已修复（2026-09-25，P2 波次一 SP4）：`RunOptions.timeout`（默认 60s）+ CLI `--timeout`；`asyncio.wait_for` 包裹场景，超时记 error 继续跑后续场景；`--repeat` 下 `_worse()` 保证 error 结果不被好结果覆盖。守卫：`test_run_scenarios_timeout_fails_scenario_and_continues`；`--timeout 0.001` 端到端实测 exit 1。*

- [x] **`check_commit_pushed` 仅支持 `gitee.com`** — `tools/changelog/gitee.py`
  *复核：仍存在 — [gitee.py:61-85](../../tools/changelog/gitee.py) 其他 host 返回 `None`。*
  *✅ 已修复（2026-09-25，P2 波次一 SP4）：按 host 分派（gitee OpenAPI v5 / github REST / 其它 None）；新增 `check_supported`，调用方 `cli.py` 对不支持 host 打印 `cannot verify pushes ... skipping gate` 并跳过（不再静默空过）。守卫 6 条（monkeypatch，零网络）。*

- [x] **`strip_unreleased` 边界情况（仅有 Unreleased 段）未测试** — `tools/changelog/render.py`
  *复核：仍存在 — 测试文件无 `strip_unreleased` 直接用例。*
  *✅ 已修复（2026-09-25，P2 波次一 SP4）：三条边界用例（仅有 Unreleased 段 → 只剩 header；空 Unreleased 段 → 标题连同空行剔除；Unreleased 在末尾 → 整段丢弃）。*

- [x] **文档提到 e2e git 测试但实际不存在** — `tests/test_changelog_tool.py`
  **已修复（核实 2026-09-23）：** [test_changelog_tool.py:689](../../tests/test_changelog_tool.py) 已有「real git end-to-end」测试段（真实临时 git 仓库，无 git 环境时跳过）。
