# 修复文件夹删除未通知 LSP

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
>
> 原实现位于 `yate/app_features/explorer.py::apply_delete(app: AppProtocol, ...)`，
> 该目录已在「分层重构」中删除。当前逻辑迁移至 `yate/editor_view/explorer.py`
> 与 `yate/session.py`（`EditorSession.close_under`），使用具体对象
> （`EditorSession` / `LspManager`）而非 `AppProtocol`。
>
> **仍未做的后续项**：本文档"后续建议 3"提到的重命名未通知 LSP 问题
> 可能仍然存在，需检查当前 `ExplorerTree` 的重命名流程。

> 

---

## 修复计划：文件夹删除关闭标签时未通知 LSP

### 问题定位

**文件：** `yate/session.py` — `EditorSession.close_under()`（第182–197行）；删除入口在 `yate/editor_view/explorer.py::submit_delete()`（第537–550行）。原 `yate/app_features/explorer.py::apply_delete` 已在分层重构中删除，逻辑迁移至此（2026-09-28 核对修正）。

**根因：** 当删除文件夹导致多个已打开标签关闭时，第134–135行通过列表推导式直接过滤掉受影响的文档并更新 `app.docs`，但**没有**对这些被关闭的文档调用 `lsp.on_document_closed()`。对比 `editor.py` 中的 `Editor.close_tab()`（第499行起），它通过 `self.session.close_active()`（最终经 `EditorSession._notify_closed` → 注入于 `editor.py:113` 的 `on_closed` 回调 `Editor._lsp_documents_closed`，于 `editor.py:1335–1339` 调用 `self.lsp.on_document_closed`）正确通知 LSP（2026-09-28 核对修正）。

**影响：** LSP 服务器保留过时的 `didOpen` 状态，后续在同一文件上打开标签时可能出现诊断信息重复、补全上下文错误等问题。

---

### 任务 1：修复 `apply_delete` 函数中的 LSP 通知缺失

#### 操作步骤

**修改文件：** `yate/session.py`（`EditorSession.close_under`，第182–197行）（2026-09-28 核对修正：原 `app_features/explorer.py` 已删除，逻辑迁移至此）。

**当前代码（问题段）：**

```python
    # close tabs whose file lived under the deleted path
    target = path.resolve()
    kept = [d for d in app.docs
            if d.path is None or not d.path.resolve().is_relative_to(target)]
    closed = len(app.docs) - len(kept)
    if closed:
        app.docs = kept
        ...
```

**修复思路：** 在过滤出 `kept` 之前，先显式收集被关闭的文档列表，然后对每个有 `path` 的文档调用 `app.run_worker(app.lsp.on_document_closed(doc), group="lsp-sync", exclusive=False, exit_on_error=False)`。

**修复后代码结构：**

```python
    # close tabs whose file lived under the deleted path
    target = path.resolve()
    closed_docs = [d for d in app.docs
                   if d.path is not None and d.path.resolve().is_relative_to(target)]
    kept = [d for d in app.docs if d not in closed_docs]
    if closed_docs:
        # Notify LSP for each closed document BEFORE removing from app.docs
        for doc in closed_docs:
            app.run_worker(
                app.lsp.on_document_closed(doc),
                group="lsp-sync", exclusive=False, exit_on_error=False,
            )
        app.docs = kept
        if not app.docs:
            app.new_buffer(show=False)
        app.doc_index = max(0, min(app.doc_index, len(app.docs) - 1))
        app.search = SearchEngine()
        app.message(f"closed {len(closed_docs)} open tab(s)", kind="warn")
```

#### 验证方法

1. **静态代码检查：** 当前已无 `AppProtocol`（`interfaces.py` 在分层重构中删除，`AppProtocol` 被架构守卫 `tests/test_architecture.py::test_no_app_protocol` 显式禁止）；`lsp` 是 `Editor`/`YateApp` 上的具体 `LspManager`，`run_worker` 由 Textual 的 `Widget`/`App` 提供。类型检查（pyright strict 0 诊断）通过即可（2026-09-28 核对修正）。
2. **手动集成测试场景：**
   - 打开一个包含子文件夹的工作区
   - 在该文件夹中打开 2–3 个文件标签
   - 触发删除文件夹操作并确认
   - 观察：标签关闭后，重新打开其中某个文件 → 确认无诊断信息重复 / LSP 服务器无报错日志
3. **对比现有 `close_tab()` 实现：** 调用参数（`group="lsp-sync"`, `exclusive=False`, `exit_on_error=False`）保持完全一致，确保行为对称。

---

### 任务 2：补充单元测试覆盖（可选但推荐）

#### 操作步骤

**修改文件：** `tests/test_lsp.py`（或新建 `tests/test_explorer_lsp.py`）

编写测试验证 `apply_delete` 正确触发 `didClose` 通知：

```python
async def test_apply_delete_notifies_lsp_did_close(tmp_path):
    """Deleting a folder with open tabs sends didClose for each."""
    # 1. 创建测试文件夹结构
    folder = tmp_path / "folder"
    folder.mkdir()
    file_a = folder / "a.py"
    file_b = folder / "b.py"
    file_a.write_text("x = 1\n")
    file_b.write_text("y = 2\n")

    # 2. Mock app：docs 列表包含两个有 path 的文档
    mock_docs = [
        Document(str(file_a), TextBuffer("x = 1\n")),
        Document(str(file_b), TextBuffer("y = 2\n")),
        Document(None, TextBuffer("scratch\n")),  # 无路径，不受影响
    ]
    app = make_mock_app_with_lsp(mock_docs)

    # 3. 调用 apply_delete
    apply_delete(app, folder, "y")

    # 4. 断言：LSP 收到了 2 次 didClose
    closed_uris = [m[1]["textDocument"]["uri"]
                   for m in app.lsp.client.sent
                   if m[0] == "textDocument/didClose"]
    assert len(closed_uris) == 2
    assert str(file_a.resolve()) in closed_uris[0]  # URI 包含路径
    assert str(file_b.resolve()) in closed_uris[1]
    # 无路径的 scratch buffer 不应触发 didClose
```

#### 验证方法

1. **运行 `pytest`**：确认新测试通过
2. **回归测试**：确认 `tests/test_lsp.py` 中已有 `on_document_closed` 相关测试（第703行、第829行）仍然通过（2026-09-28 核对修正）。
3. **运行完整测试套件**：`pytest tests/` 确认无回归

---

### 风险分析

| 风险                                                                                | 概率  | 影响  | 缓解措施                                                                       |
| --------------------------------------------------------------------------------- | --- | --- | -------------------------------------------------------------------------- |
| **调用顺序问题**：在更新 `app.docs = kept` 之后才调用 `on_document_closed`，可能导致 LSP 内部状态与实际文档不同步 | 低   | 中   | 代码中**先调用** `on_document_closed` 再赋值 `app.docs = kept`，与 `close_tab()` 模式一致 |
| **`run_worker` 异步调度问题**：多个 `run_worker` 调用可能被调度器延迟执行                              | 低   | 低   | `close_tab()` 用的也是相同的 `group="lsp-sync"` 模式，Textual 的 worker 组确保同组任务顺序执行   |
| **空文件夹 / 无打开标签的文件夹删除**：`closed_docs` 为空，跳过通知循环                                    | 低   | 无影响 | `if closed_docs:` 守卫正确处理了边界情况                                              |
| **接口兼容性**：`EditorSession`/`Editor` 使用具体类型（`LspManager` 等），无 `AppProtocol`；`run_worker` 由 Textual 提供 | 极低  | 低   | `interfaces.py` 已删除，`AppProtocol` 被架构守卫禁止（2026-09-28 核对修正） |

---

### 后续建议

1. **LSP 关闭通知的统一入口：** 后续可考虑将"关闭多个文档并通知 LSP"的逻辑抽成 `YateApp` 的一个私有方法（如 `_close_docs_with_lsp_notification(docs)`），供 `close_tab()` 和 `apply_delete()` 共用，避免两处实现漂移。
2. **诊断清理验证：** 修复后，可在实际使用中观察删除文件夹时 LSP 诊断面板是否正确清除对应文件的诊断信息，作为端到端验证。
3. **同系列问题排查：** 建议排查 `app_features/explorer.py` 中的 `apply_rename`（第98–118行）是否也需要 LSP 通知——重命名应先 `didClose` 旧 URI 再 `didOpen` 新 URI，当前实现似乎只更新了 `doc.path` 而未通知 LSP。

---
