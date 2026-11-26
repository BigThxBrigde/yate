# plan-a：真实 wire 帧捕获与 Full-only 回退（wave-1）

> 主计划：[`../lsp-incremental-sync-acceptance-plan.md`](../lsp-incremental-sync-acceptance-plan.md)
> 独占文件：`../../../tests/test_lsp.py`（**只改这一文件**）。
> 产品源码：`yate/` 零改动。

## 一、输入

- `../../../yate/editor_lsp/client.py:443-451`：`notify()` 经 `build_notification` + `_write_raw` 上线。
- `../../../yate/editor_lsp/client.py:462-470`：`_write_raw()` 内 `protocol.encode_message(payload)` 是唯一的真实帧编码点。
- `../../../yate/editor_lsp/protocol.py:39-42,55-60`：帧编码与通知构造器。
- `../../../tests/test_lsp.py:55-72`：`FakeReader`；`:176-263`：`ServerHarness`；`:640-644`：`make_python_doc`；`:1993-2024`：`_sync_session` / `_did_changes` 形态参考。
- 基线已确认：`ServerHarness` 目前只回 `completionProvider`，无法协商 `textDocumentSync`；只能在解码后 dict 层观测，拿不到真实帧字节。

## 二、具体修改（定位到代码）

### 2.1 `ServerHarness` 可选 capabilities

在 `tests/test_lsp.py:179-208` 的 `ServerHarness.__init__` 增加 **keyword-only** 参数：

```python
def __init__(
    self,
    *,
    completion_result: Any = None,
    server_capabilities: dict[str, Any] | None = None,
) -> None:
    ...
    self.server_capabilities: dict[str, Any] = (
        {"completionProvider": {"triggerCharacters": [".", "["]}}
        if server_capabilities is None
        else server_capabilities
    )
```

`start()`（`:203-208`）的 initialize 响应改为使用 `{"capabilities": self.server_capabilities}`。默认值与现状逐字一致，`test_handshake_triggers_and_stops`（`:266-291`）无需修改即可继续断言 `trigger_characters == (".", "[")`。

### 2.2 帧捕获助手

在 harness 之后新增：

```python
def _capture_wire_frames(client: LspClient) -> list[bytes]:
    frames: list[bytes] = []
    inner = client._write_raw

    async def capture(payload: dict[str, Any]) -> None:
        frames.append(protocol.encode_message(payload))
        await inner(payload)

    # noqa: Any - test seam: wrap the production encoder boundary.
    cast(Any, client)._write_raw = capture
    return frames
```

文件头已有 `# pyright: reportPrivateUsage=false`（`:5`），故 `client._write_raw` 不产生诊断；`cast(Any, ...)` 附 `noqa` 理由注释，符合 coding-style §3.3。

### 2.3 共享驱动骨架

两条用例共用一个本地 async 辅助（写在测试附近，不抽公共模块）：

```python
async def _drive_manager_with_harness(
    harness: ServerHarness, tmp_path: Path, text: str
) -> tuple[LspManager, LspClient, Document, Any, list[bytes]]:
    client = await harness.start()
    frames = _capture_wire_frames(client)
    managers: list[LspManager] = []

    def factory(config: ServerConfig, root: Path) -> LspClient:
        return client

    mgr = LspManager(
        workspace_root=lambda: tmp_path,
        client_factory=cast(Any, factory),
    )
    managers.append(mgr)
    mgr.register_server(PY_CONFIG)
    doc = make_python_doc(str(tmp_path), text)
    await mgr.on_document_shown(doc)
    internals = cast(Any, mgr)
    return mgr, client, doc, internals, frames
```

`factory` 的形参虽未用但签名必须与 `client_factory` 一致；`client.start()` 在 `on_document_shown` 内幂等，不会二次握手。

### 2.4 新增用例 1：`test_did_change_wire_capture_carries_only_changed_range`

- **前置**：`tmp_path`；harness capabilities `{"textDocumentSync": {"openClose": True, "change": 2, "save": True}}`；文本 `"a\U0001F600b\ncd\n"`。
- **arrange**：`_drive_manager_with_harness(...)`；断言 `client.sync_kind == 2`；`doc.buffer.set_cursor((0, 2))`（`Pos = tuple[int, int]`，`buffer.py:30`；行内 code point 列 2 = emoji 之后）。
- **act**：`doc.buffer.insert_text("X")`；`internals._flush_change(doc, internals._uri(doc))`；用 `asyncio.timeout(2.0)` 有界轮询直到捕获到至少一个 `textDocument/didChange` 帧（每轮 `await asyncio.sleep(0.02)`，禁止固定 sleep 后断言）。
- **assert**：
  - 对帧 `await protocol.read_message(FakeReader(frame))`，断言非 `None`；按 `msg["method"]` 过滤出 didChange。
  - `params["textDocument"]["version"] == 2`；`len(params["contentChanges"]) == 1`。
  - `change = params["contentChanges"][0]`；`set(change) == {"range", "rangeLength", "text"}`。
  - `change["range"]["start"] == {"line": 0, "character": 3}`、`end` 同为 `{"line": 0, "character": 3}`（astral 计 2 个 UTF-16 code unit）。
  - `change["rangeLength"] == 0`；`change["text"] == "X"`。
  - `json.dumps(msg)` 中不含 `"a\U0001F600b\ncd\n"`（片段而非全文）。
  - 帧 `frame.startswith(b"Content-Length: ")` 且 `len(frame) < 1024`。
- **清理**：`finally: await mgr.shutdown_all(); await harness.close()`。

### 2.5 新增用例 2：`test_full_only_server_wire_capture_sends_whole_document`

- **前置**：`tmp_path`；harness capabilities `{"textDocumentSync": {"openClose": True, "change": 1, "save": True}}`；文本 `"abc\ndef\n"`。
- **arrange**：`_drive_manager_with_harness(...)`；断言 `client.sync_kind == 1`。
- **act**：`doc.buffer.set_cursor((0, 1)); doc.buffer.insert_text("X")`；`internals._flush_change(...)`；同上轮询 didChange 帧；随后 `await mgr.on_document_closed(doc)` 并轮询 didClose 帧。
- **assert**：
  - didChange `version == 2`，`len(contentChanges) == 1`。
  - `set(change) == {"text"}` 且 `change["text"] == doc.buffer.get_text() == "aXbc\ndef\n"`（证明 Full-only 服务器收到全量而非补丁）。
  - 帧可被 `protocol.read_message` 解码，证明 Content-Length 与 JSON 完整。
  - didClose 帧存在，且 `params["textDocument"]["uri"]` 与 didChange 相同。
- **清理**：同上。

## 三、详细验证方案

| 验证目标 | 命令 | 通过标准 |
|---|---|---|
| 增量线上帧只有变更区间且 astral 列正确 | `.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q -k "wire_capture or full_only" -n 1` | 退出码 0；两条新用例与既有 handshake 用例全过 |
| 类型检查（测试夹具形态） | `.venv\Scripts\python.exe -m pyright tests/test_lsp.py` | 0 errors / 0 warnings |

## 四、风险与回滚

- `_write_raw` 包装会捕获 initialize/didOpen/didClose；用 method 过滤，不假设帧序号。
- `ServerHarness` 默认值变化会影响既有测试：默认值保持逐字一致，wave-1 命令覆盖 handshake 用例。
- 回滚：`git revert` 本子计划提交；测试文件回基线，产品行为不受影响。

## 五、报告要求

交付时列出：改动清单（`tests/test_lsp.py` 的新增符号/用例名）、实际执行命令与退出码、未解决项。禁止声称未跑的门禁。
