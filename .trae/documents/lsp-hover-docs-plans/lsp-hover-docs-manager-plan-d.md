# 计划 d — `LspManager.request_hover`（波次 2，L0）

父计划：[overview.md](overview.md) · 主计划：[../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)，决策 D3
依赖：计划 a（`parsing.parse_hover_contents`）。

## 输入

- `yate/editor_lsp/manager.py:45-46`（重新导出的 UTF-16 辅助函数），
  `:50`（常量），`:212-239`（`config_for` / `supports` / `states`），
  `:300-329`（`ensure_client` **会启动**客户端），`:361-408`
  （`on_document_shown` 发出 `didOpen`），`:467-516`（`didChange`），
  `:541-618`（`request_completion` 模板），`:785`（`_uri`）。
- `yate/editor_lsp/client.py:62`（`ServerState.READY`），`:394-429`
  （`request` / `start_request` / `settle_request`）。
- `yate/editor_lsp/parsing.py`（计划 a 之后）：`parse_hover_contents`。

## 独占文件

- `yate/editor_lsp/manager.py`
- `tests/test_lsp_hover.py`（新建）

## 具体改动

1. `yate/editor_lsp/manager.py:50` —— 添加
   `HOVER_TIMEOUT_S: float = 2.0` 并附 `#:` 注释（必须有界等待：
   `LspClient.request()` 没有超时）。
2. 在 `state_for_doc` 附近（`manager.py:241`）添加一个私有查找方法：

   ```python
   def _ready_client_for(self, doc: Document) -> LspClient | None:
       """Return an already-READY client with *doc* open; never start one."""
   ```

   步骤：`doc.path is None` → `None`；`config = self.config_for(doc.filetype)`
   → `None` 守卫；`root = self.root_for(config, doc)`；
   `key = (config.name, str(root))`；`client = self._clients.get(key)`；
   **仅当** `client.state is ServerState.READY` **且**该文档的 URI 已打开时才返回它
   （在 `manager.py:220` 使用 `self.is_open(...)`，与其实际签名保持一致；否则检查 `uri in self._open`）。
   绝不调用 `ensure_client`、`_start_client`、`_make_client`、
   `on_document_shown` 或 `notify`。
3. 在 `request_completion` 之后（`manager.py:618`）添加公开方法：

   ```python
   async def request_hover(self, doc: Document, row: int, col: int) -> str:
       """Fetch normalized hover Markdown; "" when unavailable or empty."""
   ```

   - `client = self._ready_client_for(doc)`；`None` → `""`（仅记录 debug 日志）。
   - `uri = self._uri(doc)`；
     `cursor_line = doc.buffer.lines[row] if row < doc.buffer.line_count else ""`；
     `params = {"textDocument": {"uri": uri}, "position": {"line": row,
     "character": _to_utf16(cursor_line, col)}}`。
   - 参照 `request_completion:584-600`：先 `request_id, future = await
     client.start_request("textDocument/hover", params)`，然后在嵌套的
     `try/finally: client.settle_request(request_id)` 内执行
     `raw = await asyncio.wait_for(future, HOVER_TIMEOUT_S)`；重新抛出
     `asyncio.CancelledError`；`except (LspError, OSError, TimeoutError)`
     → `""`；不调用 `dispatch_change`，不调用 `on_document_shown`。
   - 在 `try/except Exception:  # noqa: BLE001 - hostile server payload` 内用
     `parsing.parse_hover_contents(raw)` 解析 →
     `log.debug(...)` 和 `""`（绝不抛出异常，绝不暴露到 UI）。
   - docstring 必须与 `request_completion` 形成对比：不发送 `didOpen`，不发送
     `didChange`，不启动服务器。
4. 不改动 `request_completion`、`ensure_client`、`notify_edit`、
   `on_document_shown`、`states` 或诊断路径（AC6）。

## 测试（`tests/test_lsp_hover.py`）

夹具：`_FakeClient` 的 `state = ServerState.READY`，
`async def start_request(method, params)` 记录调用并返回
`(id, future)`，`settle_request(id)` 记录清理动作；通过 `manager.register_server(...)`
注册一个 `ServerConfig`，并将这个假对象注入
`manager._clients`（参照 `tests/test_lsp.py:37-70` 和
`tests/test_app_lsp.py` 的模式）。对 `manager.ensure_client` 和
`manager.on_document_shown` 打 monkeypatch，使其一旦被调用就令测试失败。使用
`tests/test_lsp.py` 中已有的异步风格（`asyncio.run` 或项目自带的异步
fixture —— 以该文件为准，不要引入新的依赖）。

| 测试 | 安排 / 执行 | 断言 |
| --- | --- | --- |
| `test_request_hover_sends_hover_method_and_uri` | 就绪 + 已打开文档，`await manager.request_hover(doc, 3, 2)` | 记录的方法 `== "textDocument/hover"`，且 `params["textDocument"]["uri"]` 与 `manager._uri(doc)` 一致 |
| `test_request_hover_encodes_position_in_utf16_units` | 行 `"aé中x"`，光标 `col=3` | `params["position"] == {"line": row, "character": _to_utf16(line, 3)}` 且等于 3（é=1 个单元，中=1 个单元）—— 针对 `_to_utf16` 断言，不要用硬编码的猜测值 |
| `test_request_hover_without_ready_server_returns_empty_without_starting_one` | 空的 `_clients` | `== ""`；`ensure_client` / `on_document_shown` 从未被调用；没有 `start_request` |
| `test_request_hover_with_failed_server_state_returns_empty` | 假对象 `state = ServerState.FAILED` | `== ""` |
| `test_request_hover_with_unopened_document_returns_empty` | 就绪客户端，`is_open` 为 false | `== ""`，没有 `start_request` |
| `test_request_hover_does_not_flush_didChange` | 对 `dispatch_change` 打 monkeypatch 使其抛错 | 调用正常返回，且 spy 未被调用 |
| `test_request_hover_with_null_result_returns_empty` | `future.set_result(None)` | `== ""` |
| `test_request_hover_with_error_response_returns_empty` | `future.set_exception(LspResponseError(...))` | `== ""` 且 `settle_request` 被调用 |
| `test_request_hover_with_timeout_returns_empty` | 永不 settle 该 future，将 `HOVER_TIMEOUT_S` monkeypatch 为一个极小值 | `== ""` 且 `settle_request` 被调用（不做固定 sleep 时长的断言） |
| `test_request_hover_with_malformed_payload_returns_empty` | `future.set_result(object())` | `== ""`，无异常 |
| `test_request_hover_returns_normalized_markdown_from_markup_array` | `{"contents": [{"language":"python","value":"def f():"}, {"kind":"markdown","value":"docs"}]}` | 结果包含带代码围栏的签名和 `docs` |
| `test_request_hover_settles_pending_request_on_success` | 正常结果 | `settle_request` 以发出的 id 恰好调用一次 |
| `test_request_hover_with_cancelled_worker_reraises_cancellation` | 取消正在等待的任务 | `pytest.raises(asyncio.CancelledError)` |

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp_hover.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_lsp_parsing.py tests/test_app_lsp.py -q -n 1
```

两条命令的退出码均为 0；第二条证明补全/诊断未被改动。

## 风险与回滚

- 风险：`is_open()` 的签名与假设不符 —— 先读
  `manager.py:220`；若它接受 `Document`，则传入 `doc`；绝不调用会打开文档的方法。
- 风险：`asyncio.wait_for` 会取消底层 future；`settle_request`
  仍必须在 `finally` 中执行。超时测试已覆盖这一点。
- 风险：若计划 a 失败，`parsing.parse_hover_contents` 尚不可导入 ——
  波次 1 通过前不得启动波次 2。
- 回滚：回退此提交；计划 g 是波次 3 中唯一的消费方。
