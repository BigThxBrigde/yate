# 2026-10-26 性能审计（全仓库）

## 审计方法

- 分支 `enh/perf-audit`（worktree `../yate-perf-audit`，基于 master `f8c1b73`）。
- 三个并行只读审计（editor_core+editor_syntax / editor_view+flows+editor+app+session /
  editor_lsp+services+keyproto+editor_term+keymaps+启动路径），全部发现经实际读码取证；
- 主代理对全部 major 发现逐条亲自读码复核（含两个审计独立交叉印证的条目），下述
  证据行号均已核对。

## 结论总览

分块加载原语（`rows_loaded`/`fill_lines`/bisect 水位线）、regex 高亮后端（模块级预编译
- lru_cache）、高亮后台 worker（防抖 + to_thread + 排他 worker）、cells 宽度缓存、
启动路径懒导入均实现正确。问题集中在**每击键路径上的 O(文档) 工作**与**无节流的
全应用刷新链**两类，共 9 条 major、12 条 minor。

| # | 严重度 | 主题 | 位置 |
|---|---|---|---|
| P1 | major | 快照式撤销每击键 4 次全文档遍历 + 撤销栈内存驻留 | editor_core/buffer.py:319-364 |
| P2 | major | 渲染路径同步重分词：每键 O(全文档) diff 与整表重建 | editor_view/highlighting.py:254-312 |
| P3 | major | refresh_ui 无条件全应用重绘；未消费键也全刷 | editor.py:713-741, 856-869 |
| P4 | major | 鼠标拖选每个 MouseMove 触发全应用刷新 | flows/mouse_flows.py:92-100 |
| P5 | major | LSP 同步每键物化整篇文本；didChange 全量重发 | editor_lsp/manager.py:397-414, 440-461 |
| P6 | major | LspClient._pending 完成后不清理，无界泄漏 | editor_lsp/client.py:392-422 + manager.py:520-530 |
| P7 | major | 无 LSP 补全词缓存每键失效、全量重扫且跑在事件循环 | editor_view/completion.py:295-307 |
| P8 | major | 实时搜索每键全文档重扫，缺防抖 | editor_core/search.py:50-64 + flows/prompt_flows.py:57-61 |
| P9 | major | 终端 VT 逐字符解析跑在 UI 事件循环 | editor_term/emulator.py:201-211 + pty_proc.py:140-147 |
| P10 | minor | Path.resolve 每键/每渲染行重复调用，无缓存 | editor_lsp/manager.py:687-689, editor_view/chrome.py:191 |
| P11 | minor | 诊断按行查询全表拷贝 + 线性扫描，每渲染行一次 | editor_view/editor.py:415 + editor_lsp/manager.py:605-637 |
| P12 | minor | 单次替换后全文档重扫 | editor_core/search.py:129-131 |
| P13 | minor | 多光标 O(k²) 重映射与每点 O(N) 行拼接 | editor_core/buffer.py:86-90, 793, 827-928 |
| P14 | minor | Document.modified 回退路径每键 O(N) 拷贝比较 | editor_core/document.py:190-194 |
| P15 | minor | tree-sitter 整文档双重编码、Parser 重建、端点前缀解码 | editor_syntax/ts_backend/backend.py:62-67, 139-143 |
| P16 | minor | hex 脏字节每块全量线性扫描，O(编辑数²) | editor_core/chunked.py:318-340 |
| P17 | minor | 保存/打开全量重建 explorer 树，侧栏隐藏不跳过 | flows/document_flows.py:258, 396, 471 |
| P18 | minor | 词移动逐字符调用正则 | editor_core/words.py:15-49 |
| P19 | minor | Lua 捆绑库每扩展重复读盘重编译 | services/extensions/loader.py:188-195 + lua/library.py:36-75 |
| P20 | minor | walk_files 每次全树 stat，无会话缓存 | services/workspace.py:240-301 |
| P21 | minor | which-key 隐藏态每键仍标脏 | editor_view/whichkey.py:148-154 |

## Major 发现

### P1 快照式撤销：每击键 2 次全文档行列表拷贝 + 最多 3 次全量比较

- 证据：`_snapshot` 返回 `tuple(self.lines)`（buffer.py:319-322）；`_commit` 再做一次
  `after = self._snapshot()`（341），随后 `after == before`（342）、
  `after.lines != before.lines`（347）、char 合并时 `top.after == before`（351）均为
  N 行元组逐元素比较。每个 `_Edit` 持 before/after 双快照，上限 1000 步。
- 另有多个早退路径在快照之后才返回：`delete_backward` 731-734、`delete_forward`
  764-768、`move_line` 1152-1156、`join_lines` 1168-1171。
- 影响：大文件每击键约 4 次全文档遍历；20 万行文件撤销栈峰值滞留约
  2×1000×20 万行指针（GB 级）。
- 修复建议：改增量撤销记录（变更行区间 + 替换文本 delta）；至少让 `_commit` 复用
  before 元组、只对变更区间比较；早退卫语句前移到快照之前。

### P2 渲染路径同步重分词：每键 O(全文档) 行 diff + 整表重建

- 证据：`_rebuild_tokens_on_edit`（highlighting.py:254-312）在渲染路径触发：
  `changed = {i for i in range(common) if snapshot[i] != lines[i]}`（257）全行扫描；
  `rebuilt`/`states` 整表重建（273 起）；`self._hl_line_snapshot = tuple(lines)`
  （310）整表快照拷贝。行内 O(1) 复用（281-294）只省分词，不省 diff 与拷贝。
- 影响：防抖后台 worker（0.08s）本会整体替换缓存，这段同步扫描只为补偿窗口内
  数帧，但每键在主事件循环付出 O(lines)——10 万行文件每键数十毫秒。
- 修复建议：让 buffer 编辑时记录变更行区间（dirty range），把 diff 限制在区间内；
  快照改用版本号 + 区间失效，避免 `tuple(lines)` 整表拷贝。

### P3 refresh_ui 无条件全应用重绘；未消费键也全刷

- 证据：`refresh_ui`（editor.py:713-741）无条件执行 `_refresh_views`（对所有视图
  `content_changed()`，内部 `reveal_cursor()` + `refresh()` 双重标脏）、
  `_refresh_chrome`（状态栏整条 Rich Text、标签栏重排、面包屑、which-key）、
  `_refresh_lsp`；`handle_raw_key`（856-869）在 867 行不看 `handled` 无条件调用。
- 影响：每按键、每次鼠标事件的全应用刷新链，多窗格线性放大；未绑定键同样付全款。
- 修复建议：只对文档实际变化的视图调 `content_changed()`；chrome 组件做"文本未变
  则跳过"短路（terminal.py:562-576 已有先例）；`handle_raw_key` 改
  `if handled: self.refresh_ui()`。

### P4 鼠标拖选每个 MouseMove 触发全应用刷新

- 证据：`_on_move`（mouse_flows.py:92-100）每次 move 执行
  `set_cursor` + `content_changed` + `self._refresh()`（= `Editor.refresh_ui`）；
  `_on_down`/`_on_click` 同模式（88/127）。
- 影响：MouseMove 可达每秒数十至上百次，叠加 P3 全链成本与 P5 的每键 LSP 物化。
- 修复建议：拖拽路径只刷被拖视图；`refresh_ui` 用 `call_after_refresh` 或脏标记
  合并到每帧一次。

### P5 LSP 同步每键物化整篇文本；didChange 全量重发

- 证据：`notify_edit`（manager.py:397-414）在"是否变化"短路之前执行
  `text = doc.buffer.get_text()`（405，即 `"\n".join(self.lines)` 整篇拼接）与
  整篇字符串比较（406）；防抖（0.25s）只延迟发送不延迟构建；didChange 声明
  `_SYNC_FULL`（44-46）全量文本同步（440-461），每防抖窗口全文重序列化。
  该方法经 `refresh_ui → _refresh_lsp`（editor.py:740）每键执行。
- 影响：LSP 会话中大文件（数 MB）每键数十毫秒级拼接+比较；持续输入时每 0.25s
  再加一次全量序列化写入。
- 修复建议：用 `buffer.content_version`/`content_edits`（O(1) 脏计数，已存在）与
  上次同步版本比较；`get_text()` 推迟到 `_flush_change` 防抖回调内；中长期改
  增量同步（range/rangeLength）。

### P6 LspClient._pending 完成后不清理，无界泄漏

- 证据：`request()` 有 `finally: self._pending.pop(request_id, None)`
  （client.py:392-396）；而 `request_completion`（manager.py:520-530）直接
  `start_request` + `await future`，成功、报错（`return []`）、取消（re-raise）
  三条路径均不弹出；已核对 `flows/completion_flows.py` 亦不清理。
- 影响：每次补全请求泄漏一个 future 及其原始响应 payload（pyright/rust-analyzer
  动辄数百 KB），长会话内存持续增长，直到连接 teardown。
- 修复建议：`request_completion` 用 `try/finally: client._pending.pop(request_id,
  None)` 包裹 await（镜像 `request()`），一行修复。

### P7 无 LSP 补全：词缓存每键失效、全量重扫且跑在事件循环上

- 证据：`_buffer_row_words`（completion.py:295-307）以 `content_version` 为缓存键，
  打字每键推进 version → 每次查询必然重算
  `rows = [set(_WORD_RE.findall(line)) for line in buf.lines]`（305）全量扫描；
  调用链 `completion_flows.py:186-221` 的 worker 经 `run_worker` 跑在事件循环上
  （无 `to_thread`）。
- 影响：无 LSP 文档每输入一个字符（0.12s 防抖后）在主循环做全 buffer 正则扫描。
- 修复建议：按行增量维护词集（只重算变更行）；或把扫描放 `asyncio.to_thread`。

### P8 实时搜索每键全文档重扫，缺防抖

- 证据：`Search.update`（search.py:50-64）全量重算（逐行 `finditer`）；
  `_live_search`（prompt_flows.py:57-61）在搜索提示词 on_input_changed 每键同步
  调用。本仓库其他长任务路径均有防抖先例（补全 0.12s、高亮 0.08s、find&replace
  0.3s、LSP 0.25s），此处独缺。
- 影响：大缓冲区搜索面板每敲一个字符一次纯 Python 全文档扫描。
- 修复建议：给 `_live_search` 套同款 `call_later` 防抖（空查询立即清除分支保留）；
  中长期做前缀增量细化。

### P9 终端 VT 逐字符解析跑在 UI 事件循环上

- 证据：`feed`（emulator.py:201-211）对每个字符执行 `_consume → _ground → _print
  → _char_width`（含每打印字符 2 次 `unicodedata` 调用）+ 每字符一个 8 字段 Cell
  分配；读线程每输出块（最大 64KB）经 `call_soon_threadsafe`（pty_proc.py:140-147,
  186-192）投递，回调 `_on_output`（editor_view/terminal.py:195-205）在主循环上
  解析，无预算上限。`refresh()` 会被 Textual 合帧，解析不合帧。
- 影响：批量输出（构建日志、cat 大文件）时每秒数百 chunk 的解析全部占用主循环，
  UI 卡顿、按键延迟。
- 修复建议：chunk 排入有界队列按帧合并解析；或线程内解析、循环只消费快照；
  纯 ASCII 段加批量快路径。

## Minor 发现（简录，均经复核）

- P10 `path_to_uri` = `Path(path).resolve().as_uri()`（protocol.py:156-158）无缓存，
  notify_edit 每键、`diagnostics_on_line` 每渲染行各一次；`chrome.py:191` 面包屑
  对 `doc.path` 同样每次刷新 resolve。建议按 doc.path / Document 缓存。
- P11 `diagnostics_on_line`（manager.py:605-637）每调用全表拷贝 + 全表过滤，
  渲染循环每行一次（editor_view/editor.py:415）；同文件搜索匹配已有
  `_matches_for_row` 按行桶缓存先例。建议诊断发布时按行建索引。
- P12 `replace_current`（search.py:129-131）单行替换后 `self.update(...)` 全文档
  重扫。建议只重扫被编辑行、其余匹配按列差平移。
- P13 多光标 `_remap_after_insert`（buffer.py:86-90）每点全字典遍历 O(k²)；
  `_multi_points`:793 对列表做成员测试；每点行拼接 O(N)。建议 set 去重 +
  按行偏移运行增量。
- P14 `Document.modified`（document.py:190-194）回退路径每键
  `tuple(self.buffer.lines)` 拷贝 + 比较。建议 O(1) 布尔（content_edits 已足够）。
- P15 ts_backend（backend.py:62-67）每轮高亮整文档编码两遍（join+encode 一次、
  逐行 encode 一次）、`ts.Parser` 每次重建；`_to_char`（139-143）每端点前缀解码
  O(byte_col)。整文档重解析为已文档化 v1 取舍（防抖 + 后台线程缓解），
  按既有计划落 `Tree.edit()` 增量。
- P16 `ChunkedBinaryFile.read`（chunked.py:318-340）对每块遍历整个 `_dirty`
  字典，`apply_edit` 只增不清。建议按块索引分桶。
- P17 保存/打开（document_flows.py:258, 396, 471）→ `explorer_tree.refresh_tree()`
  全树重建（含每个展开目录同步 `list_dir`），不检查 `self.display`。建议隐藏时
  跳过、显示时只刷受影响子树。
- P18 words.py（15-49）扫描循环每字符 `_WORD_CHARS.match(ch)`。建议整段贪心匹配
  或字符集判定。
- P19 `lua_api_library_source`/`lua_module_sources`（library.py:36-75）无缓存，
  每个扩展重复读盘（~45KB）重编译。建议 lru_cache（资源只读不变）。
- P20 `walk_files`（workspace.py:240-301）每次全树重遍历、每条目一次 `is_dir()`
  stat；ctrl+p 与全项目查找各自重复。建议会话级缓存 + 失效签名。
- P21 whichkey `clear()`（whichkey.py:148-154）隐藏态每键 `update("")` 标脏。
  建议开头早退。

## 已排查、确认无问题（供未来审计免重复）

分块加载原语（bisect，无隐藏线性扫描）；regex_backend（预编译 + lru_cache +
单遍扫描）；高亮后台 worker 全链（防抖/排他/版本键）；`_matches_for_row` 按行桶；
cells 宽度缓存；welcome 缓存；pane 树遍历（O(窗格数)）；app.py 空闲轮询（三重
早退）；find_replace/manual/palette/diffview（to_thread + 防抖）；hexview 与
chunked_flows 的 ensure_row；screensaver；终端回滚（有界 + 帧快照缓存）；
manager._diagnostics 生命周期；events.py emit（低频点，docstring 契约）；
keyproto 驱动（与 Textual 8.2.8 原版对齐、有界等待）；启动路径懒导入与 rc 单次
exec；api/bridges 无热路径桥接往返。
