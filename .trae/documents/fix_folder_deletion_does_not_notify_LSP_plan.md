# 修复文件夹删除未通知 LSP

> **实施状态（2026-09-22 核对）：✅ 已实现。**
>
> 实现落在 `yate/app_features/explorer.py::apply_delete(app: AppProtocol,
> path, confirm)`：先收集将被关闭的文档，逐个
> `app.run_worker(partial(app.lsp.on_document_closed, doc), group="lsp-sync",
> exclusive=False, exit_on_error=False)`，再赋值 `app.docs = kept`，
> 参数与 `app.py::close_tab()` 完全一致（含"传绑定函数而非协程"的注释说明）。
>
> **仍未做的后续项**：本文档"后续建议 3"提到的 `apply_rename`/`submit_rename`
> 未通知 LSP —— `YateApp.retarget_document()` 只更新 `doc.path`，
> 没有对旧 URI 发 `didClose` / 对新 URI 发 `didOpen`。

> 

---

## 修复计划：文件夹删除关闭标签时未通知 LSP

### 问题定位

**文件：** `yate/app_features/explorer.py` — `apply_delete()` 函数（第121–146行）

**根因：** 当删除文件夹导致多个已打开标签关闭时，第134–135行通过列表推导式直接过滤掉受影响的文档并更新 `app.docs`，但**没有**对这些被关闭的文档调用 `lsp.on_document_closed()`。对比 `app.py` 中的 `close_tab()`（第491–514行），它在关闭单个标签时正确调用了 `run_worker(self.lsp.on_document_closed(closed), ...)`。

**影响：** LSP 服务器保留过时的 `didOpen` 状态，后续在同一文件上打开标签时可能出现诊断信息重复、补全上下文错误等问题。

---

### 任务 1：修复 `apply_delete` 函数中的 LSP 通知缺失

#### 操作步骤

**修改文件：** `yate/app_features/explorer.py`（第132–146行）

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

1. **静态代码检查：** 确认 `AppProtocol` 已暴露 `lsp: LspManager`（第87行）和 `run_worker()`（第244行），类型检查不会报错。
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
2. **回归测试**：确认 `tests/test_lsp.py` 中已有 `on_document_closed` 相关测试（第632行、第758行）仍然通过
3. **运行完整测试套件**：`pytest tests/` 确认无回归

---

### 风险分析

| 风险                                                                                | 概率  | 影响  | 缓解措施                                                                       |
| --------------------------------------------------------------------------------- | --- | --- | -------------------------------------------------------------------------- |
| **调用顺序问题**：在更新 `app.docs = kept` 之后才调用 `on_document_closed`，可能导致 LSP 内部状态与实际文档不同步 | 低   | 中   | 代码中**先调用** `on_document_closed` 再赋值 `app.docs = kept`，与 `close_tab()` 模式一致 |
| **`run_worker` 异步调度问题**：多个 `run_worker` 调用可能被调度器延迟执行                              | 低   | 低   | `close_tab()` 用的也是相同的 `group="lsp-sync"` 模式，Textual 的 worker 组确保同组任务顺序执行   |
| **空文件夹 / 无打开标签的文件夹删除**：`closed_docs` 为空，跳过通知循环                                    | 低   | 无影响 | `if closed_docs:` 守卫正确处理了边界情况                                              |
| **接口兼容性**：`AppProtocol` 需暴露 `lsp` 和 `run_worker`                                  | 极低  | 低   | 已确认两者在 interfaces.py 中都已声明                                                 |

---

### 后续建议

1. **LSP 关闭通知的统一入口：** 后续可考虑将"关闭多个文档并通知 LSP"的逻辑抽成 `YateApp` 的一个私有方法（如 `_close_docs_with_lsp_notification(docs)`），供 `close_tab()` 和 `apply_delete()` 共用，避免两处实现漂移。
2. **诊断清理验证：** 修复后，可在实际使用中观察删除文件夹时 LSP 诊断面板是否正确清除对应文件的诊断信息，作为端到端验证。
3. **同系列问题排查：** 建议排查 `app_features/explorer.py` 中的 `apply_rename`（第98–118行）是否也需要 LSP 通知——重命名应先 `didClose` 旧 URI 再 `didOpen` 新 URI，当前实现似乎只更新了 `doc.path` 而未通知 LSP。

---
