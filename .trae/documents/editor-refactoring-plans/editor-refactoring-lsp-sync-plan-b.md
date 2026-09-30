# plan_B — lsp_sync 流程外移（Wave 2）

## 目标
把 Editor 的 LSP 胶水（worker 派发 / 事件重绘 / 诊断回显 / 诊断浮层）外移到
`yate/lsp_sync.py`。模块名对齐既有 worker 组名 `"lsp-sync"`（editor.py:1338 等多处）。
review 问题 5 点名的「completion/LSP 两块」之 LSP 半边。

## 改动文件（独占）
- 新建 `yate/lsp_sync.py`
- `yate/editor.py`（删原方法 + 接线 + 薄委托）
- `tests/test_architecture.py`（R11 `UI_FROZEN_FILES` 登记新条目）

## 输入（外移方法，editor.py 行号）
| 方法 | 行号 | 去向 |
|---|---|---|
| `_lsp_documents_closed` | 1327-1339 | `LspSync.documents_closed` |
| `_lsp_doc_shown_later` | 1341-1349 | `LspSync.doc_shown_later` |
| `_on_lsp_event` | 1351-1359 | `LspSync.on_event` |
| `_update_lsp_echo` | 1361-1377 | `LspSync.update_echo` |
| `show_diagnostics` | 1379-1395 | `LspSync.show_diagnostics` |

## 实施
1. `LspSync` 构造参数（全显式具体对象/回调）：`app: App[Any]`、`lsp: LspManager`、
   `session: EditorSession`、`panes: PaneManager`、`status_bar: StatusBar`、
   `prompt: PromptBar`、`message: Callable[[str, str], None]`、
   `mounted: Callable[[], bool]`。方法体逐行搬运，`self.xxx` 换构造协作者。
2. editor.py 接线（lambda 延迟解析，构造顺序不成环）：
   - `_build_models`：`EditorSession(config, on_closed=lambda docs: self.lsp_sync.documents_closed(docs))`；
     `LspManager(..., on_event=lambda ev: self.lsp_sync.on_event(ev))`。
   - `LspSync` 实例在 `_build_pane_stack`（panes 就绪后）创建：`self.lsp_sync = LspSync(...)`。
   - `_refresh_lsp`：`self._lsp_doc_shown_later()` → `self.lsp_sync.doc_shown_later()`；
     `self._update_lsp_echo()` → `self.lsp_sync.update_echo()`。
   - `on_event` 原回调里 `self.status_bar.refresh_status()` / `view.refresh()` 由
     LspSync 自持（status_bar/panes 已注入）。
3. Editor 保留薄委托（外部调用面不变）：
   - `show_diagnostics`（commands.py:284 调用）→ `self.lsp_sync.show_diagnostics()`。
   - `_update_lsp_echo` 若 tests/ 直接引用则保留 4 行委托（实施时 grep 确认，
     默认删除、由 `_refresh_lsp` 重接）。
4. `tests/test_architecture.py`：`UI_FROZEN_FILES["lsp_sync.py"] = {"yate.editor_view",
   "yate.editor_view.commandline", "yate.editor_view.statusbar",
   "yate.editor_view.modals"}`（模块 docstring 的 R11 条目同步补一句）。
5. 禁止项自查：lsp_sync.py 不 import yate.editor / yate.app / actions / commands；
   日志 `log = tracing.get_logger(__name__)`（如有日志；搬运体当前无日志调用）。

## 输出 / 验收
统一门禁（README §七）全 0 退出码；`grep -n "show_diagnostics" yate/commands.py`
调用点无需改动；架构测试含新条目全绿。

## 回滚
单提交 revert。
