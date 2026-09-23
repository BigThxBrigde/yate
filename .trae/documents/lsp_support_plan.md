# editor_lsp：LSP 支持（autocomplete + diagnostics）实施计划

> **实施状态（2026-09-22 核对）：✅ 已实现。**
>
> - `yate/editor_lsp/`（`protocol.py` / `client.py` / `manager.py`）、
>   `yate/editor_view/completion.py`、`extensions/python_lsp.py`、
>   `tests/test_lsp.py` 均已落地。
> - 架构现状（2026-09-23 更新）：`AppProtocol`（`yate/interfaces.py`）已在
>   「分层重构」中删除。当前 `EditorView` / 补全弹窗等接收具体对象
>   （`EditorSession` / `LspManager` / `KeymapSet` 等），不再依赖任何 `Protocol`。
> - 后续演进：补全陈旧守卫已按 `completion_staleness_check_plan.md` 加强；
>   文档屏/主题等 UI 细节以当前代码为准。
> - 枚举与数据类命名（如 `ServerState`、`ServerConfig`）请以
>   `yate/editor_lsp/client.py` 现状为准，本文档正文为其早期形态。

## 需求

- 新增 `editor_lsp` 子系统，为 yate 接入 Language Server Protocol：**自动补全（completion）** 与 **诊断（diagnostics）**。
- 具体 LSP server 的配置通过 **extensions** 完成（核心包不内置任何语言）。
- 提供一个 **Python 扩展**（`extensions/python_lsp.py`），自动探测 `pyright-langserver`，回退 `pylsp`。
- 用户确认的默认选择：① Python server 自动探测（pyright → pylsp，皆无则优雅禁用）；② 补全**输入时自动弹出 + Ctrl+Space 手动触发**。

## Repository Research（现状结论）

- Python ≥3.10，唯一运行依赖 `textual>=8.0`（8.2.8）；**不引入 pygls/lsprotocol 等第三方 LSP 库**，用 stdlib `asyncio` + subprocess 实现最小 JSON-RPC 客户端，与项目"零额外依赖"风格一致。
- 分层：`editor_core`（纯逻辑、无 UI）/ `editor_view`（Textual 组件）/ `services`（扩展、shell、workspace）。LSP 客户端属于 UI 无关核心，新建 `yate/editor_lsp/` 包；补全弹窗 UI 放 `editor_view`。
- 扩展机制：`ExtensionAPI`（`services/extensions.py`）暴露 app 能力，`setup(api)` 注册命令/按键；扩展在 `on_mount` 里 `_load_extensions()` 加载，默认目录含 `Path.cwd()/extensions`。扩展报错不得崩溃 app。
- 异步约定（刚完成的异步化改造）：交互重活用 `app.run_worker(coro, group, exclusive, exit_on_error=False)` + `asyncio.to_thread`；worker 不随屏幕卸载自动取消，需 `is_mounted`/身份守卫；**禁止在事件循环里嵌套 `asyncio.run`**。
- 按键链：Textual `Key` → `event_to_raw` → keymap dispatch（`handle_raw_key` → `ui_refresh()`）；`EditorView.on_key` 可在 raw dispatch 前拦截（vim ctrl+w 已是此模式）。`ctrl+space`（0x00）当前 `textual_key_to_raw` 返回 None，需补映射。
- 渲染：`EditorView.render_line` 逐行生成 Rich Segment，overlay 用 per-cell style id；诊断样式可在此叠加。gutter 由行号+空格组成。
- 文档同步钩子点：打开/切换/关闭在 `app.py`（`_open_document_path(_async)`、`open_path(_async)`、`new_buffer`、`cycle_tab`、`close_tab`）；编辑后统一走 `ui_refresh()`；保存走 `save_document()`。
- 测试：`python -m pytest`，Textual 用 `app.run_test()` + `pilot`；pyright strict 对 `yate`/`tests`/`extensions` 全部零错误；基线 123 tests。
- 关键测试约束：仓库内 `extensions/` 会被测试自动加载，Python 扩展加载时只能注册配置，**不得产生消息行输出/不得 spawn 进程**（否则污染现有 123 个测试的消息断言）。

## 设计

### 协议与客户端（UI 无关，纯异步）

**`yate/editor_lsp/protocol.py`**
- `encode_message(obj: dict) -> bytes`：`Content-Length: N\r\n\r\n` + JSON（UTF-8）。
- `async def read_message(reader) -> dict | None`：解析 header（容忍额外 header 字段、大小写），按长度读 body；EOF 返回 None。
- 纯函数 `build_request(id, method, params)`、`build_notification(method, params)`、`build_response/error`（供测试假 server 用）。
- URI 工具：`path_to_uri` / `uri_to_path`（Windows 盘符 `file:///c%3a/...` 形态，用 `pathlib.Path.as_uri()`/`urllib` 处理，空格/中文不手工拼）。

**`yate/editor_lsp/client.py`**
- 数据类（轻量 typed，不用 dict 贯穿）：`ServerConfig`（name, cmd, args, filetypes, language_ids, init_options, settings, env）、`ServerStatus` 枚举（CONFIGURED/STARTING/READY/FAILED/STOPPED）、`Completion`（label, detail, kind, insert_text, range start/end 可选）、`Diagnostic`（row, col, end_row, end_col, severity, message, source）。
- `LspClient`：
  - `async start()`：`asyncio.create_subprocess_exec`（Windows 靠 ProactorEventLoop，Textual/py3.13 默认即此）；发 `initialize`（capabilities 声明 textDocumentSync、completion（snippets=false、resolve 不需要）、publishDiagnostics；rootUri/root markers 选择）；发 `initialized`；启动单一 reader task 分发：响应→future 映射（id 关联），通知→注册的 handler（`textDocument/publishDiagnostics`、`log/message` 等）。
  - `request(method, params, *, cancellable=False, timeout=...)`、`notify(...)`、`cancel(id)`（`$/cancelRequest`）。
  - 每请求独立 id；completion 用递增 token，旧响应靠请求序号丢弃。
  - `async stop()`：`shutdown`（有超时）→ `exit` → `terminate()` 兜底，防僵尸进程。
  - 可注入 reader/writer 构造参数，便于测试用内存双工管道驱动假 server，不真起进程。

**`yate/editor_lsp/manager.py`**
- `LspManager`（app 持有一个）：
  - `register_server(config)`：扩展调用；按 filetype（扩展名）索引。
  - `client_for(doc)`：按 (config, root_uri) 缓存并惰性启动 client（worker 中）；root = workspace.root 或文件所在目录（root_markers 匹配）。
  - 文档同步：`on_document_changed(doc)`（切换标签/打开：旧 doc 不关闭（多视图同 server），新 doc 若未 open 则 didOpen 全量）、`notify_edited(doc)`（去抖 ~250ms 发 didChange，**Full 同步**，带 version 自增）、`notify_saved(doc)`（didSave）、`close_document(doc)`（didClose，引用计数）。
  - `async request_completion(doc, row, col) -> list[Completion]`：取消上一个未完成请求；解析 `CompletionList`/裸数组/`itemDefaults.editRange`；取 `textEdit.newText`/`insertText`/`label`；忽略 snippet（InsertTextFormat=2 时回退 label）。
  - diagnostics：`dict[uri, list[Diagnostic]]`；`diagnostics_for(doc)`、`counts(doc) -> (errors, warnings)`、`at(doc, row, col)`；收到 publishDiagnostics 后回调 UI 刷新（注入回调，避免核心依赖 Textual）。
  - 状态：`status(config_name)`；可执行文件不存在（FileNotFoundError）→ FAILED + 保存错误信息，**不弹消息行**，仅状态栏可见；同名 server 启动只尝试一次，避免反复 spawn。
  - `async shutdown_all()`：app 卸载/退出时调用。

### UI（editor_view + app 接线）

**`yate/editor_view/completion.py`：`CompletionPopup`**
- 非 focusable 的轻量 `Container`（内含一个 `Static` 自绘列表，避免 ListView 抢焦点），挂到 `#editor-col`，用 CSS `layer: popup` + `offset: x y` 定位到光标屏幕位置（由 EditorView 的 scroll_offset、scroll_col、gutter、tab/wide-cell 映射计算）。
- 显示 ≤8 行：kind 图标/缩写 + label + 浅色 detail；选中行高亮；`display=False` 初始隐藏。
- 公开纯数据接口：`show(items, prefix)`、`select_next/prev`、`accept()`→返回选中 `Completion`、`close()`、`is_open`、`index`。

**EditorView 改造（`editor_view/editor.py`）**
- `on_key` 在 raw dispatch 前：弹窗打开时拦截 `tab`/`enter`（接受）、`up/down`（选择）、`esc`（关闭）、其他键照常分发后按结果决定刷新/关闭；`Ctrl+Space` 任何模式下直接触发 manual completion（vim NORMAL 不触发）。
- 弹窗未打开时：可打印字符分发后，若该文件有注册 server 且字符为标识符字符或 server 声明的 triggerCharacters，调度去抖 ~120ms 的自动补全请求。
- 诊断渲染叠加：
  - 行号着色：含 error 的行行号/行首用红，warning 用黄（复用 theme 的 red/yellow）。
  - 诊断区间：Rich `Style(underline=True, color=...)` 无法给下划线单独着色且会改字色——采用 **underline + 保持语法色叠加**不可行，故区间用 `bgcolor` 极浅底色区分（error=红系、warn=黄系，优先用下划线：Rich 支持 `Style(underline=True)` + 语法前景色，错误/警告统一用下划线，严重性靠行号颜色和 gutter 图标区分，避免破坏语法高亮）。最终：gutter 加一列诊断标记（`✖` 红 / `▲` 黄 / `●` 信息，宽度+1，无诊断留空），区间加下划线。
- 光标停留行有诊断时，由 app 侧去抖在消息行显示 `message`（不抢输入焦点）。

**app.py 接线**
- `__init__`：`self.lsp = LspManager(on_diagnostics=self._on_lsp_diagnostics)`；`on_mount` 末尾 mount popup（需在扩展加载之后，扩展注册在加载期只写注册表）。
- 文档生命周期钩子：open/switch/new/close/save 各点调用 manager；`ui_refresh()` 中以 `(doc, version)` 去重后调 `notify_edited`（避免每次光标移动都通知——比对 buffer 文本快照或脏标记：manager 内部记录每个 uri 上次同步文本，相同则跳过）。
- `request_completion_later(manual)` worker；接受补全后计算 prefix（触发位置到光标的标识符）并用 buffer 替换插入，随后继续输入。
- `:diagnostics` 命令：OutputScreen 列出当前文档诊断（行:列 严重性 消息），无诊断时消息行提示。
- `on_unmount`：调度 `shutdown_all`（best-effort，不阻塞退出）。

**statusbar.py**：右侧 meta 区增加 LSP 状态与计数（如 `{} 2 ! 1`，无 server/无诊断时不显示）；新增图标从 `icons.py` 取（无合适则用文本 `LSP`）。

**keys.py**：`("ctrl",) + "space"` → `\x00`；补全不走 raw binding，而由 EditorView 直接认 `event.key == "ctrl+space"`（与现有显式分支风格一致，且能在 vim INSERT 下工作）。

### 扩展 API（`services/extensions.py`）

- 新增 `LspExtensionBridge`（窄接口，包一层 manager）：
  - `register_server(name, *, command, args=None, filetypes, language_ids=None, initialization_options=None, settings=None, env=None, root_markers=None)`；`filetypes` 支持扩展名列表（`["py"]`），`language_ids` 缺省同名映射。
  - 只读 `statuses()`。
- `ExtensionAPI` 增加 `lsp` 属性。
- 类型完整（pyright strict），扩展侧调用带完整类型标注。

### Python 扩展 `extensions/python_lsp.py`

- setup(api)：
  - 命令解析：环境变量 `YATE_PYTHON_LSP`（如 `pyright-langserver --stdio`，shlex 切分）优先；否则 `shutil.which("pyright-langserver")` → `["pyright-langserver","--stdio"]`；再 `shutil.which("pylsp")` → `["pylsp"]`；都没有则仍注册配置但标记"惰性失败"（核心侧首次打开 .py 时 FAILED，无消息行噪音）——扩展本身不主动报错，仅暴露状态。
  - `filetypes=["py"]`，languageId `python`；pylsp 提供保守 initializationOptions（不强制装插件：jedi completion 可用即可）；pyright 不给额外 options。
  - 顶部 docstring 写明 `pip install python-lsp-server` 或 `npm i -g pyright` / `pip install pyright`。

### 文档

- `manual.en.md` / `manual.zh.md`：新增 "LSP / Language servers" 章节（能力、Ctrl+Space、`:diagnostics`、如何通过扩展注册、Python 扩展安装方式与 `YATE_PYTHON_LSP`）。
- `README.md`：feature 列表加一条 LSP。
- `docs/yaterc.md`：如涉及配置提及一句（扩展发现机制已存在，不新增 rc 选项）。
- `extensions/example_ext.py` 顶部 api 列表补一行 `api.lsp`（小改）。

## 文件清单

**新增**
- `yate/editor_lsp/__init__.py`、`protocol.py`、`client.py`、`manager.py`
- `yate/editor_view/completion.py`
- `extensions/python_lsp.py`
- `tests/test_lsp.py`

**修改**
- `yate/app.py`（manager 生命周期、文档钩子、补全 worker、`:diagnostics`、popup mount）
- `yate/editor_view/editor.py`（弹窗按键拦截、自动触发、诊断渲染：gutter 标记+下划线+行号色）
- `yate/editor_view/statusbar.py`（LSP 状态/计数）
- `yate/editor_view/keys.py`（ctrl+space）
- `yate/services/extensions.py`（api.lsp 桥）
- `tests/test_app_textual.py`（补全/诊断 UI 测试）
- `yate/resources/manual.en.md`、`manual.zh.md`、`README.md`、`docs/yaterc.md`（小）、`extensions/example_ext.py`（docstring 小改）

## 实施步骤（依赖序）

1. `editor_lsp/protocol.py`：framing + URI 工具 + 单测（内存 StreamReader/Writer 双工，半包/多包粘连）。
2. `editor_lsp/client.py`：进程生命周期、initialize 握手、请求/响应/通知分发、cancel、stop；用假 server 协程（管道双工）单测。
3. `editor_lsp/manager.py`：注册、client 缓存、文档同步 payload、completion 映射、诊断存储、缺可执行文件的 FAILED 路径；单测。
4. `CompletionPopup` + EditorView 渲染/按键接线 + app 钩子 + `:diagnostics` + statusbar；Textual pilot 测试（注入假 LspClient，不依赖真 server）。
5. ExtensionAPI.lsp 桥 + `extensions/python_lsp.py`（which 探测、env 覆盖）+ 扩展加载测试。
6. 文档更新。
7. 全量验证与收尾。

## 验证

- `.venv\Scripts\python.exe -m pyright` → 0 errors（含新扩展、新测试）。
- `$env:PYTHONDONTWRITEBYTECODE='1'; .venv\Scripts\python.exe -m pytest tests -q` → 原 123 + 新增约 10~12 个全绿。
- 若本机 venv/系统装有 pylsp 或 pyright-langserver，做一次真实 smoke（临时 .py 文件触发补全/诊断）；不满足安装条件则跳过，不为此安装软件。
- 重点回归：现有 `.py` 文件打开的测试（test_syntax_highlight 等）在 python_lsp 扩展被自动加载后仍通过（注册不 spawn、失败不发消息行）。

## 风险与处理

- **Windows asyncio subprocess**：需 ProactorEventLoop；Textual 在 Windows 默认使用它。若 `create_subprocess_exec` 抛 NotImplementedError，manager 捕获→FAILED 状态，不崩溃。
- **僵尸 server 进程**：shutdown 有超时 + terminate 兜底；app.on_unmount best-effort 关闭。
- **补全响应竞态**：请求序号 + 取消上一个；应用结果前校验 doc/光标位置/prefix 未变化。
- **didChange 风暴**：manager 内全文本快照去重 + 250ms 去抖；Full sync 规避增量位置计算。
- **popup 定位/滚动**：用 EditorView 几何（scroll_offset/scroll_col/gutter/tab cell 映射）计算 offset；光标在底部时向上弹；超右界左移。
- **严格 pyright 与 JSON dict**：协议边界保留 dict，业务层全部转 dataclass；窄化用类型守卫辅助函数。
- **测试环境无 server**：所有核心测试走内存管道假 server；UI 测试注入假 client；测试不断言本机安装了 pylsp/pyright。
- **扩展重复加载**：register_server 同名覆盖语义明确（后注册者替换），避免目录扫描重复注册。
