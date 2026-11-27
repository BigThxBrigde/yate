# 计划 a — LSP 请求层（波次 1）

父计划：[../lsp-navigation-plan.md](../lsp-navigation-plan.md)。

## 输入 / 输出

输入：issue 简报 AC1-AC7，父计划 §2 中的代码事实。
输出：L0 请求+解析模块、规范化 URI 映射、薄 manager 包装、单元测试。
本计划不涉及 UI，也不改按键。

## 独占文件

- `yate/editor_lsp/navigation.py`（新增）
- `yate/editor_lsp/protocol.py`
- `yate/editor_lsp/manager.py`
- `tests/test_lsp_navigation.py`（新增）

此处不要改动 `tests/test_architecture.py` 或任何规则文件；行数同步属于计划 e。

## 具体改动

### 1. `editor_lsp/protocol.py`

新增 `canonical_uri(uri: str) -> str`（公开）：先经 `uri_to_path(uri)` 转换，
再经 `path_to_uri(...)`；当来源不是 `file:` URI 时，原样返回输入。用该函数替换
manager 中原始的 diagnostic 键和对外 URI 生成，使 pyright 的盘符转义回显与本地
构造的 URI 比较结果相等。保持 `uri_to_path` / `path_to_uri` 的签名不变。

### 2. 新增 `editor_lsp/navigation.py`（L0，仅 stdlib + 本地导入）

- `class LspFeatureUnavailable(Exception)` — 当服务器能力缺失/为 false 时抛出；
  流程将其转为一条提示消息（AC1/AC4/AC6）。
- 冻结数据类：`LspLocation(uri, row, col, end_row, end_col)`、
  `LspSymbol(name, kind, detail, uri, row, col, end_row, end_col, depth)`、
  `LspTextEdit(start_row, start_col, end_row, end_col, text)`、
  `WorkspaceEdit(changes: dict[str, tuple[LspTextEdit, ...]], unsupported: bool)`、
  `LspCodeAction(title, kind, edit: WorkspaceEdit | None, command: str | None,
  arguments: tuple[object, ...])`、
  `LspSignature(text: str, active_parameter: int)`。
- `supports_feature(caps: dict[str, object], feature: str) -> bool`：缺失、
  `False` 或 `None` => False；`True` 或任意 dict/list => True。处理对象形式的
  `renameProvider` / `codeActionProvider`。
- `request(client, method: str, params: dict[str, object]) -> object`：
  `start_request` + `asyncio.wait_for(future, NAV_TIMEOUT_S=3.0)`；超时时调用
  `send_cancel(req_id)`；始终调用 `settle_request(req_id)`。重新抛出
  `asyncio.CancelledError`；把 `LspError`/`OSError`/`TimeoutError` 包装为带方法名的
  `LspFeatureFailed`（新异常）。
- 纯解析器（均为防御式：形态错误时返回空值，不抛异常）：
  `parse_locations(raw)`、`parse_symbols(raw)`、`parse_workspace_edit(raw)`、
  `parse_code_actions(raw)`、`parse_signature_help(raw)`。
  - `parse_locations`：接受 `Location`、`LocationLink`（`targetUri` +
    `targetRange`）以及 `null`；像 `parsing._range_to_buffer_cols` 一样钳制行/列。
  - `parse_symbols`：同时接受 `DocumentSymbol[]`（递归，按递增的 `depth` 展平，
    用 `selectionRange` 跳转）和 `SymbolInformation[]`
    （`location.uri` + `location.range`）。
  - `parse_workspace_edit`：支持 `changes: dict[uri, TextEdit[]]` 以及带 `edits` 的
    `documentChanges` 项；一旦出现任何 `CreateFile` / `DeleteFile` / `RenameFile`
    就设置 `unsupported=True`，且不返回任何部分改动。
  - `parse_code_actions`：接受 `Command` 和 `CodeAction` 形态；保留 title、kind、
    edit、命令名和参数。
  - `parse_signature_help`：选取活动签名/参数，格式化为一张 markdown 卡片，
    其中带标签、活动参数以粗体标记。

### 3. `editor_lsp/manager.py`

保持现有行为不变。增加来自 `navigation` 和 `protocol.canonical_uri` 的导入。
在 `request_hover` 之后增加以下薄包装方法：

```python
def supports_feature(self, doc: Document, feature: str) -> bool
async def request_definition(self, doc: Document, row: int, col: int) -> list[LspLocation]
async def request_references(self, doc: Document, row: int, col: int) -> list[LspLocation]
async def request_document_symbols(self, doc: Document) -> list[LspSymbol]
async def request_rename(self, doc: Document, row: int, col: int, new_name: str) -> WorkspaceEdit
async def request_code_actions(self, doc: Document, row: int, col: int, diagnostics: list[Diagnostic]) -> list[LspCodeAction]
async def request_signature_help(self, doc: Document, row: int, col: int) -> LspSignature | None
async def execute_command(self, client: LspClient, name: str, arguments: list[object]) -> None
```

每个请求方法：`_ready_client_for(doc)` → `supports_feature(...)`（为 false 时抛出
`LspFeatureUnavailable`）→ 通过现有 `_to_utf16` 用 UTF-16 列构造 LSP 参数 →
`navigation.request(...)` → 解析器。`request_references` 传入
`{"includeDeclaration": True}`。`request_code_actions` 传入 diagnostics 范围，
并尽可能按服务器声明过滤 `only: ["quickfix", "refactor", "source"]`。
`execute_command` 通过 client 发送 `workspace/executeCommand` 并忽略结果。

按上述说明修改 `_uri()` 和 `handle_notification()` 以使用 `canonical_uri`。

## 测试（`tests/test_lsp_navigation.py`）

使用 `tests/test_lsp_hover.py:36-121` 中的 `_FakeClient` / `_Harness` 模式
（读该文件；不要修改它）。必需的用例：

- `test_canonical_uri_maps_drive_escaped_and_plain_forms_to_one`：`canonical_uri("file:///d%3A/x.py") == canonical_uri("file:///D:/x.py")`。
- `test_parse_locations_accepts_location_link_and_null`：一个带 `targetUri`/`targetRange` 的 `LocationLink` 和一个 `None` -> 一个行列符合预期的 `LspLocation`。
- `test_parse_symbols_flattens_nested_document_symbols`：父 + 子 -> 两个 `LspSymbol`，深度为 0/1，位置取自子项的 `selectionRange`。
- `test_parse_workspace_edit_rejects_file_operations`：一处有效文本编辑外加一个 `CreateFile` -> `unsupported is True` 且 `changes == {}`。
- `test_parse_code_actions_keeps_command_and_edit`：一个命令动作和一个编辑动作 -> 字段被保留。
- `test_parse_signature_help_marks_active_parameter`：两个签名，active 1/1 -> 卡片文本包含第二个参数的粗体标记。
- `test_manager_request_definition_without_provider_raises_unavailable`：假客户端能力中没有 `definitionProvider` -> `pytest.raises(LspFeatureUnavailable)`。
- `test_manager_request_definition_returns_locations`：假响应含两个位置 -> 两个 `LspLocation`，并记录请求方法 `textDocument/definition`。
- `test_manager_request_references_timeout_sends_cancel`：假 future 永不完成，monkeypatch `navigation.NAV_TIMEOUT_S=0.001` -> `LspFeatureFailed`，`send_cancel` 被调用，`settle_request` 被调用。
- `test_manager_notification_uses_canonical_diagnostic_uri`：发布带盘符转义 URI 的 diagnostics -> `manager` 的 diagnostic 键等于 `canonical_uri` 形式。

## 验收命令（在任务 worktree 根目录运行）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_navigation.py -q
.venv\Scripts\python.exe -m pyright yate/editor_lsp tests/test_lsp_navigation.py
```

两者都必须以 0 退出。此处不要运行完整测试套件。

## 风险 / 回滚

风险：假客户端脚手架可能需要 `OpenDocState` 字段；从 `tests/test_lsp_hover.py` 原样复制。
风险：`manager.py` 超过 893 行 —— 符合预期且可接受（已豁免）；计划 e 负责同步计数。
回滚：回退本计划的提交；在波次 3 之前没有其他波次依赖其运行时行为。
