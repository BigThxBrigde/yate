# 无名称缓冲区 LSP 接入子计划 b — L0 管理器：路径闸门、URI 重定向、单次 didOpen（wave-1）

主计划：[`../enew-args-lsp-attach-plan.md`](../enew-args-lsp-attach-plan.md) · 波次表：
[`overview.md`](overview.md)。从 `../yate-enew-args-lsp-attach` worktree 根目录运行。

## 1. 输入

- issue 记录 [`../enew-args-lsp-attach-issue-notes.md`](../enew-args-lsp-attach-issue-notes.md) §1 问题 2/3、§5 LSP 位置、§6 方向 2/3。
- 主计划 §2 事实 F4-F11、F18、§3 决策 B/C、§4 时序图。
- 规则：`.trae/rules/architecture-boundaries.md`（R4：`editor_lsp` 是无 UI 的
  L0 叶子节点；R2/R6/§三.3）、`.trae/rules/python-coding-style.md`（完整类型标注、docstring、惰性 `%` 日志）、`.trae/rules/misc-rules.md` §四（英文
  注释/docstring）。

## 2. 独占文件

- `yate/editor_lsp/manager.py`（写）
- `tests/test_lsp.py`（写，仅追加新用例；不要重写该文件）

其它一切只读。尤其不要触碰
`yate/flows/document_flows.py`（子计划 c）或 `tests/test_architecture.py`。

## 3. 具体改动（全部在 `yate/editor_lsp/manager.py` 中）

### 3.1 模块 docstring（`:3-9`）

在 `on_document_closed` 旁边添加第五条生命周期要点：

```
* :meth:`on_document_retargeted` -- a save-as gave the document a new URI
  (didClose of the old URI, didOpen of the new one)
```

保留周围的文字和 ASCII 标点。

### 3.2 `__init__`（`:113` 附近，紧邻 `_uri_cache`）

添加：

```python
#: URIs with an in-flight ``on_document_shown`` handshake.  The check in
#: ``is_open`` happens before ``await ensure_client``, so without this set two
#: overlapping refresh workers could both send didOpen for the same uri.
self._opening: set[str] = set()
```

无新增导入（`set[str]` 是内置类型）。`shutdown_all`（`:682+`）可以在取消任务后调用
`self._opening.clear()` —— 前提是不改变现有的
清理顺序；进行中的协程也会在 `finally` 中清除自己的条目。

### 3.3 `state_for_doc`（`:235-238`）— 与 `supports` 统一闸门

替换为：

```python
def state_for_doc(self, doc: Document) -> ServerState | None:
    """Aggregated server state relevant to *doc*, for the status bar.

    An unnamed document has no URI, so no server can ever serve it: return
    ``None`` instead of advertising a configured/ready server.  This mirrors
    the ``path is not None`` gate in :meth:`supports` and
    :meth:`ensure_client`.
    """
    if doc.path is None:
        return None
    cfg = self.config_for(doc.filetype)
    return self.states().get(cfg.name) if cfg is not None else None
```

`states()` / `configs()`（由 `diagnostics.py` 和扩展桥使用）
必须保持不变：它们描述的是*已注册的服务端*，而不是某个文档。

### 3.4 `on_document_shown`（`:347-383`）— 并发下仅一次 didOpen

重构为以下代码（保留现有的 `didOpen` 载荷、
`OpenDocState` 字段、`_forget_diagnostics(uri)` 调用以及
`(LspError, OSError)` 的尽力而为返回）：

```python
async def on_document_shown(self, doc: Document) -> None:
    """Open *doc* on its server when it becomes the active document."""
    if doc.path is None:
        return
    uri = self._uri(doc)
    if uri in self._open or uri in self._opening:
        return
    config = self.config_for(doc.filetype)
    if config is None:
        return
    self._opening.add(uri)
    try:
        client = await self.ensure_client(doc)
        if client is None:
            return
        root = self.root_for(config, doc)
        text = doc.buffer.get_text()
        try:
            await client.notify("textDocument/didOpen", {
                "textDocument": {
                    "uri": uri,
                    "languageId": config.language_id(doc.filetype),
                    "version": 1,
                    "text": text,
                },
            })
        except (LspError, OSError):
            return
        self._open[uri] = OpenDocState(
            uri=uri,
            config_name=config.name,
            client_key=(config.name, str(root)),
            language_id=config.language_id(doc.filetype),
            version=1,
            last_synced_lines=tuple(doc.buffer.lines),
            last_synced_version=doc.buffer.content_version,
            doc=doc,
        )
        # Pending diagnostics may already be stale relative to buffer content;
        # the server republishes after didOpen.
        self._forget_diagnostics(uri)
    finally:
        self._opening.discard(uri)
```

`finally` 必须覆盖 `try` 内部的每一处提前返回（客户端启动
失败、通知失败），以免 URI 永远滞留在 `_opening` 中。

### 3.5 抽取 `_close_uri` 并添加 `on_document_retargeted`（`:385-408`）

将 `on_document_closed` 中位于 `if doc.path is None:
return` 守卫之后的方法体原样移入一个新的私有协程：

```python
async def _close_uri(self, uri: str) -> None:
    """Forget one open URI and best-effort notify its server with didClose."""
    state = self._open.pop(uri, None)
    self._change_timers.pop(uri, None)
    # Queued senders for this uri hold their own lock reference and
    # bail out on the pre-notify state check; dropping the entry here
    # keeps a reopened document from reusing the stale lock (R3 N5).
    self._change_locks.pop(uri, None)
    self._drop_uri_cache(uri)
    if state is None:
        return
    client = self._clients.get(state.client_key)
    if client is not None and client.state is ServerState.READY:
        try:
            await client.notify("textDocument/didClose",
                               {"textDocument": {"uri": uri}})
        except (LspError, OSError) as exc:
            # The document already left the session, so a lost didClose
            # only leaves the server's view stale -- logged (never
            # raised) to keep the close path total and traceable.
            log.debug("didClose failed for %s: %s", uri, exc)

async def on_document_closed(self, doc: Document) -> None:
    """Forget *doc*'s didOpen state and notify didClose (best effort)."""
    if doc.path is None:
        return
    await self._close_uri(self._uri(doc))
```

然后在 `on_document_closed` 之后紧接着添加 retarget 入口点：

```python
async def on_document_retargeted(
    self, doc: Document, previous_path: Path | None
) -> None:
    """Rebind a saved-as document on its server.

    *previous_path* is the path the document had *before* the successful
    write (``None`` for a buffer that was unnamed).  An unchanged path keeps
    the ordinary didSave; a changed one drops the old URI (with didClose)
    before the new document is opened.  A first path is treated exactly like
    a document-shown event, so ``:saveas test.py`` really attaches the server.
    """
    if doc.path is None:
        return
    if previous_path is not None and Path(previous_path) == doc.path:
        await self.notify_saved(doc)
        return
    if previous_path is not None:
        await self._close_uri(protocol.path_to_uri(previous_path))
    await self.on_document_shown(doc)
```

`Path` 和 `protocol` 已经导入（`:28`、`:34`）。保持
`previous_path` 比较为按位置、基于路径对象的方式（避免字符串
规范化带来的意外）；在保存流程中，`doc.path` 经过
`resolve_input_path` 后是绝对路径，而 `previous_path` 来自同一个
`Document.path` 属性。

### 3.6 明确不变的部分

`supports`、`is_open`、`states`、`ensure_client`、`notify_saved`、
`notify_edit`、`request_completion`、`shutdown_all` 的中断顺序以及所有线路载荷。除 `on_document_retargeted` 外不新增公开 API；
`yate/editor_lsp/` 的 `__all__` 不作修改。

## 4. 测试（追加到 `tests/test_lsp.py`）

复用该模块现有的 fixture/辅助函数（`PY_CONFIG`、`make_python_doc`、
假客户端 `session` fixture 以及 `asyncio.run(scenario())` 模式 —— 编写前先阅读
`tests/test_lsp.py:640-810` 和 `:1060-1085`）。不新增 conftest，
除现有的 `cast(Any, mgr)` 接缝外，不模拟管理器内部实现。

| # | 测试名称 | 安排/执行 | 断言（具体值） |
|---|---|---|---|
| 1 | `test_state_for_doc_is_none_for_unnamed_buffer_with_filetype_override` | `mgr = LspManager(); mgr.register_server(PY_CONFIG); doc = Document(None); doc.filetype_override = "py"`；`state_for_doc(doc)`、`supports(doc)`、`ensure_client(doc)` | `state_for_doc(doc) is None`；`supports(doc) is False`；`await mgr.ensure_client(doc) is None`；`mgr._clients` 中无客户端 |
| 2 | `test_state_for_doc_reports_configured_for_named_buffer` | 同一管理器；`doc = Document(Path("a.py"))` | `state_for_doc(doc) is ServerState.CONFIGURED`；`supports(doc) is True` |
| 3 | `test_on_document_retargeted_from_unnamed_sends_did_open` | 假客户端会话；`doc = Document(None)`，`filetype_override = "py"`，文本为 `"x = 1\n"`；`doc.path = tmp_path / "new.py"`；`await mgr.on_document_retargeted(doc, None)` | 恰好一条 `textDocument/didOpen` 通知；其 `uri == protocol.path_to_uri(doc.path)`、`languageId == PY_CONFIG.language_id("py")`、`text == "x = 1\n"`；`mgr.is_open(doc) is True`；`client.started is True` |
| 4 | `test_on_document_retargeted_from_named_path_closes_old_uri_and_opens_new` | 假客户端会话；`old = tmp_path/"old.py"`、`new = tmp_path/"new.py"`；以 `doc.path = old` 执行 `await mgr.on_document_shown(doc)`；随后 `doc.path = new`；`await mgr.on_document_retargeted(doc, old)` | `didClose` 携带 `protocol.path_to_uri(old)` 发送；`didOpen` 携带 `protocol.path_to_uri(new)` 发送；`mgr.is_open(doc) is True`；`protocol.path_to_uri(old) not in cast(Any, mgr)._open`；基于 `uri_to_path` 的缓存检查：`protocol.path_to_uri(old) not in cast(Any, mgr)._uri_cache.values()` |
| 5 | `test_on_document_retargeted_same_path_only_sends_did_save` | 假客户端会话；`await mgr.on_document_shown(doc)`；`await mgr.on_document_retargeted(doc, doc.path)` | 恰好一个 `didSave`；`didOpen` 次数保持为 1；`didClose` 次数为 0 |
| 6 | `test_on_document_retargeted_without_matching_server_is_noop` | `mgr.register_server(PY_CONFIG)`；`doc = Document(None)`，`doc.path = tmp_path/"note.txt"`（无 override）；`await mgr.on_document_retargeted(doc, None)` | 未启动客户端；`mgr.is_open(doc) is False`；`_open` 为空 |
| 7 | `test_concurrent_document_shown_sends_single_did_open` | 假客户端的 `start()` 会等待 `asyncio.sleep(0)`（如有现成的慢启动假对象则复用）；创建两个任务 `asyncio.create_task(mgr.on_document_shown(doc))`；`await asyncio.gather(*tasks)` | 恰好一个 `didOpen`；`len(mgr._open) == 1`；`cast(Any, mgr)._opening == set()` |
| 8 | `test_on_document_closed_still_clears_state_after_uri_extraction` | 假客户端会话；`await mgr.on_document_shown(doc)`；用 `doc.buffer.insert_text("x"); mgr.notify_edit(doc)` 准备一个待发送的变更；`await mgr.on_document_closed(doc)` | `mgr.is_open(doc) is False`；一条 `didClose`；`cast(Any, mgr)._change_timers` 不再持有 `uri`；`uri not in cast(Any, mgr)._uri_cache.values()` |

负向演练（记录在 §6）：改动前，用例 #1 必须失败（`state_for_doc` 当前返回 `CONFIGURED`），用例 #7 必须失败（出现两个 `didOpen`）。改动后两者都必须转绿。不要为了让演练通过而削弱断言。

## 5. 验收命令（可复制粘贴，从 worktree 根目录执行）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_app_lsp.py tests/test_lsp_diff.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -c "from pathlib import Path; print(len(Path('yate/editor_lsp/manager.py').read_text(encoding='utf-8').splitlines()))"
```

通过标准：所有 pytest/pyright 命令退出码为 0；`-n auto` 与 `-n 1` 结果一致；
架构测试套件 37 通过；`manager.py` 保持低于 800 行。

## 6. 执行记录（填入实测数字）

| 命令 | 结果 | 退出码 |
|---|---|---|
| 负向演练（改动前的用例 #1、#7） | `state_for_doc` 在无名称文档上返回了 `CONFIGURED`；两个重叠的 `on_document_shown` worker 发送了两个 didOpen —— 两条断言均如预期失败 | 1（负向演练） |
| `pytest tests/test_lsp.py -q -n auto` | 64 通过（子计划 b 波次）；wave-3 增补后 72+ | 0 |
| `pytest tests/test_lsp.py -q -n 1` | 与 `-n auto` 一致，无偶发抖动 | 0 |
| `pytest tests/test_app_lsp.py tests/test_lsp_diff.py -q -n auto` | 全部通过 | 0 |
| `pyright ...` | `0 errors, 0 warnings, 0 informations` | 0 |
| `pytest tests/test_architecture.py -q` | 37 通过 | 0 |
| `manager.py` 行数 | 子计划 b 之后 783；wave-3 之后 797（仍 `< 800`） | 0 |

偏差：wave-1 无。第 5 步评审第 1 轮随后在 §3.5 基于 `Path` 的比较中发现两处严重设计缺口；它们已在
[`enew-args-lsp-attach-review-plan-e.md`](enew-args-lsp-attach-review-plan-e.md) 中重新设计，并在
wave-3 中修复，4/4 负向演练在旧实现上均失败。当前代码遵循子计划 e，而不是上面 §3.5 的原始片段。

## 7. 风险与回滚

- 风险：如果任务在 `finally` 之前被取消，`_opening` 会泄漏。由
  `try/finally` 缓解；用例 #7 断言该集合为空。`shutdown_all` 的取消也会在下一个循环轮次到达 `finally`。
- 风险：抽取 `_close_uri` 会改变 `didClose` 的记账方式。缓解：逐字复制语句顺序，并用用例 #8 和完整的 `tests/test_lsp.py` 回归加以固定。
- 风险：`:saveas` 之后旧 URI 在 `_open` 中留下陈旧条目。用例 #4 断言旧 URI 已从 `_open` 和 URI 缓存中移除。
- 回滚：revert 本波次的提交；子计划 c 依赖
  `on_document_retargeted`，因此若回滚本子计划，wave-2 不得启动。
