# plan-c：体积解耦 / astral 重放 / 失败与关闭竞态回归（wave-2）

> 主计划：[`../lsp-incremental-sync-acceptance-plan.md`](../lsp-incremental-sync-acceptance-plan.md)
> 独占文件：`../../../tests/test_lsp.py`（**只改这一文件**，与 plan-a 同文件故必须等 wave-1 通过）。
> 产品源码：`yate/` 零改动。

## 一、输入

- `../../../tests/test_lsp.py:1993-2024`：`_sync_session(tmp_path, sync_kind, text)` 与 `_did_changes(client)`。
- `../../../tests/test_lsp.py:2048-2087`：既有 Full↔增量逐字节对拍模式。
- `../../../tests/test_lsp.py:2090-2129`：`OSError` 失败重试形态；`:2240-2286`：增量关闭竞态形态。
- `../../../tests/test_lsp_diff.py:77-90`：`apply_changes` 服务器模拟器（已在 `test_lsp.py:35` 导入）。
- `../../../yate/editor_lsp/protocol.py:39-42,55-60`：`encode_message` / `build_notification` 用于计算**真实帧字节数**。
- `../../../yate/editor_core/buffer.py:30,733`：`Pos = tuple[int, int]` 与 `set_cursor`。
- 已导入可直接复用：`asyncio`、`json`、`pytest`、`Any`/`cast`、`LspError`、`protocol`、`Document`、`apply_changes`。

## 二、具体修改：仅追加 4 条测试到增量 didChange 段落末尾

### 2.1 `test_large_file_single_key_edit_payload_is_decoupled_from_document_length`

- **前置**：`tmp_path`；两段文本共用**同一 URI**（`_sync_session` 固定写 `mod.py`）：
  - `small = "x = 1\n" + ("a" * 80 + "\n") * 200`（约 16 KB）
  - `large = "x = 1\n" + ("a" * 80 + "\n") * 4000`（约 324 KB）
- **arrange/act**：顺序执行两次会话（第一次结束必须 `await mgr.shutdown_all()`）：
  1. `mgr, fakes, doc, internals = _sync_session(tmp_path, 2, text)`
  2. `await mgr.on_document_shown(doc)`
  3. `doc.buffer.insert_text("X")`（光标初始 `(0,0)`）
  4. `internals._flush_change(doc, internals._uri(doc))`；`await asyncio.sleep(0)`
  5. `params = _did_changes(fakes[0])[0]`；断言只发 1 条。
  6. `frame = protocol.encode_message(protocol.build_notification("textDocument/didChange", params))`
- **assert**：
  - 两次的 `contentChanges` 字典**完全相等**，且 `change["text"] == "X"`、`change["range"]["start"] == {"line": 0, "character": 0}`。
  - 两帧字节数**相等**且均 `< 1024`。
  - `len(large.encode("utf-8")) > 100 * len(frame_large)`（全文与 payload 至少两个数量级解耦）。
  - `large not in json.dumps(params)`（参数里不存在全文）。
  - 帧以 `b"Content-Length: "` 开头，可被 `protocol.read_message(FakeReader(frame))` 解码（若需断言可复用本文件 `FakeReader`）。
- **清理**：每次会话 `finally` 中 `await mgr.shutdown_all()`。

### 2.2 `test_incremental_wire_replay_matches_full_mode_for_astral_and_cross_line_edits`

- **前置**：`initial = "a\U0001F600b\n你好\nc\n"`；`inc = _sync_session(tmp_path / "inc", 2, initial)`；`full = _sync_session(tmp_path / "full", 1, initial)`；`server_lines = initial.split("\n")`。
- **act**：两次 `on_document_shown` 后，依次对两份 doc 施加同一组显式光标编辑：
  1. `set_cursor((0, 2)); insert_text("X")`（emoji 之后；UTF-16 列 3）
  2. `set_cursor((1, 2)); insert_text("\nZ")`（跨行 splice）
  3. `set_cursor((3, 0)); insert_text("\U0001F40D")`（插入 astral 字符）
  每步后分别 `internals._flush_change(...)` 并 `await asyncio.sleep(0)`；
  对 inc 用 `apply_changes(server_lines, params["contentChanges"])` 推进模拟器，对 full 断言 `params["contentChanges"] == [{"text": full_doc.buffer.get_text()}]`。
- **assert**：
  - 每步 `"\n".join(server_lines) == inc_doc.buffer.get_text() == full_doc.buffer.get_text()`（逐字节一致）。
  - inc 三条 didChange 的 `version` 为 `[2, 3, 4]`（严格递增）。
  - 第一条 inc change 的 `range.start == {"line": 0, "character": 3}`、`range.end` 相同、`rangeLength == 0`、`text == "X"`。
  - 第二步按 LSP 零宽插入语义断言：`range.start == range.end == {"line": 1, "character": 2}`、`rangeLength == 0`，换行由 `text == "\nZ"` 携带（实测形态；原备选条件「跨行 end」不成立，已在主计划 §九登记）。
- **清理**：两个 manager 均 `shutdown_all()`。

### 2.3 `test_incremental_send_failure_keeps_snapshot_and_retries`（参数化）

- **前置**：`_sync_session(tmp_path, 2, "abc\n")`；`client.notify` 用 monkeypatch 包一层，仅第一次 didChange 抛参数化异常：`OSError("pipe closed")` 或 `LspError("notify failed")`（`pytest.param(..., id=...)`）。
- **act**：先 `insert_text("X")` + flush，断言失败未推进；再 `insert_text("Y")` + flush。
- **assert**：失败后 `state.last_synced_lines == ("abc", "")`、`state.version == 1`、`_did_changes(client) == []`；重试后恰好 1 条 didChange、`version == 2`、`last_synced_lines == tuple(doc.buffer.lines)`、`last_synced_version == doc.buffer.content_version`。
- **说明**：原独立 `test_incremental_send_lsp_error_keeps_snapshot_and_retries` 已并入本参数化用例，`sync.py:148` 异常元组两个分支均覆盖（pr-review MINOR #2 闭环）。

### 2.4 `test_full_mode_did_change_race_with_did_close_sends_nothing_after_close`

- **前置**：`_sync_session(tmp_path, 1, "abc\n")`；`client.notify` 包一层 `hanging`，对 didChange `await release.wait()` 后放行。
- **act**：`insert_text("X")` + flush（挂起）；`insert_text("Y")` + flush（排队）；`await mgr.on_document_closed(doc)`；`release.set()`；用既有 `for _ in range(10): await asyncio.sleep(0)` 模式等待任务收敛。
- **assert**：
  - 只有 1 条 didChange，且其 `contentChanges == [{"text": "Xabc\n"}]`（关闭后编辑未上线）。
  - didClose 存在；`internals._open.get(uri) is None`；`uri not in internals._change_locks`。
  - 帧/参数无 `range` 字段（Full 分支形态不变）。

## 三、详细验证方案

| 验证目标 | 命令 | 通过标准 |
|---|---|---|
| 四条新回归单独通过 | `.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q -k "payload_is_decoupled or astral_and_cross_line or lsp_error_keeps_snapshot or full_mode_did_change_race" -n 1` | 退出码 0 |
| 与 wave-1 合并后整文件回归 | `.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_lsp_diff.py -q -n 1` | 退出码 0 |
| 类型检查 | `.venv\Scripts\python.exe -m pyright tests/test_lsp.py` | 0 errors / 0 warnings |

## 四、风险与回滚

- 显式 `set_cursor` 的行号依赖前一步编辑结果；实现时若发现漂移，改为每步后按 `doc.buffer.get_text().split("\n")` 计算下一光标，并在报告中登记偏差。
- 4000 行文本只用于字符串比较，不进入渲染/高亮；若 CI 超时可降到 2000 行，但需保证 `>100 * frame_size` 仍成立并登记。
- 挂起/关闭竞态沿用既有轮询模式，不新增固定 sleep。
- 回滚：`git revert` 本子计划提交；`yate/` 无 diff。

## 五、报告要求

交付时列出：4 条用例名、执行命令与退出码、是否出现偏差（光标/文本规模）、未解决项。
