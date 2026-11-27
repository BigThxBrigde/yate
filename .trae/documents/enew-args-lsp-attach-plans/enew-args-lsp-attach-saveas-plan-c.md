# 无名称缓冲区 LSP 接入子计划 c — `:saveas` 在首次路径上接入 LSP（wave-2）

主计划：[`../enew-args-lsp-attach-plan.md`](../enew-args-lsp-attach-plan.md) · 波次表：
[`overview.md`](overview.md)。从 `../yate-enew-args-lsp-attach` worktree 根目录运行。
**依赖子计划 b**：在本子计划开始之前，`LspManager.on_document_retargeted` 必须已经存在且测试通过。

## 1. 输入

- issue 记录 [`../enew-args-lsp-attach-issue-notes.md`](../enew-args-lsp-attach-issue-notes.md) §3 预期行为、§6 方向 3。
- 主计划 §2 事实 F11-F15、§3 决策 C、§4 时序图。
- [`enew-args-lsp-attach-state-plan-b.md`](enew-args-lsp-attach-state-plan-b.md) §3.5，了解确切的
  协程签名：`async def on_document_retargeted(self, doc: Document, previous_path: Path | None) -> None`。
- 规则：`.trae/rules/architecture-boundaries.md`（R11：`flows/*` 可以使用注入的 L0 管理器；不得向上导入；§三.8 不得新增上下文类型）、`.trae/rules/python-coding-style.md`（完整标注、docstring、日志）、`.trae/rules/misc-rules.md` §四（英文注释/docstring）。

## 2. 独占文件

- `yate/flows/document_flows.py`（写 —— 仅限 `_submit_save_as`）
- `tests/test_document_flows_saveas.py`（新建文件）

`yate/commands.py`、`yate/editor_lsp/manager.py`、`yate/flows/lsp_sync.py`、
手册、冒烟文件以及所有 `.trae/**` 文档在此均为只读。

## 3. 具体改动 — `yate/flows/document_flows.py:457-509`

当前方法体（有删节，除所列改动外须逐字保留）：

```python
def _submit_save_as(self, text: str) -> None:
    ...
    doc = self.session.doc
    if doc.chunked is not None: ... return
    buf = doc.buffer
    locked = buf.read_only
    if locked: buf.read_only = False
    path = self.resolve_input_path(Path(text))
    saved = False
    try:
        self.session.doc.save(path)
        saved = True
        ...
        self.workspace.set_root(path.parent)
        self.explorer_tree.refresh_tree()
        self._message(f"saved {path}", "ok")
        self._events.emit(EditorEvent.DOCUMENT_SAVED, DocumentSaved(self.session.doc))
    except (OSError, UnicodeError) as exc:
        self._message(f"save failed: {exc}", "error")
    finally:
        if locked and not saved:
            buf.read_only = True
```

按顺序执行的改动：

1. 紧跟在 `doc = self.session.doc` 之后添加：

   ```python
   previous_path = doc.path
   ```

   这是写入*之前*的路径；`Document.save` 只有在 `os.replace` 成功之后才会重定向
   文档（F11）。

2. 在 `try` 块中将 `self.session.doc.save(path)` 替换为
   `doc.save(path)`（同一对象，更清晰且与新的
   `previous_path` 局部变量一致）。下一行的 `saved = True` 保持不变。

3. 在**成功的 `try` 分支末尾**、现有的
   `self._events.emit(...)` 调用之后，添加：

   ```python
   self._spawn(
       partial(self.lsp.on_document_retargeted, doc, previous_path),
       group="lsp-sync", exclusive=False, exit_on_error=False,
   )
   ```

   `partial` 和 `lsp-sync` worker 组在 `:426-429` 已用于
   `notify_saved`；无新增导入、无新增构造器参数、无新增
   事件名。spawn 必须留在 `try` 内部、`saved = True` 之后，这样
   写入失败或记账失败都不会安排 retarget。

4. 在 `finally` 块之后、方法作用域内添加：

   ```python
   self._refresh_ui()
   ```

   这与 `save_document` 的尾部（`:436`）一致。它会重绘标签栏
   （`[no name]` → 文件名）和状态栏，并通过
   `Editor.refresh_ui → _refresh_lsp → LspSync.doc_shown_later` 提供
   常规的 shown 事件路径；子计划 b 的 `_opening` 守卫使额外的
   `doc_shown_later` 与 retarget worker 保持幂等。它在失败时也会运行
   （与 `save_document` 相同），因此出错后消息行也会被重绘。

5. 用一句话更新 `_submit_save_as` 的 docstring：“写入成功后，LSP 管理器被要求重新绑定该文档，它会为新获得的
   URI 发送 didOpen（并为被替换的 URI 发送 didClose）。”

**不要**改动 `save_document`（`:402-436`）、`save_as`（`:445-455`）、`prompt_save_as`（`:438-443`）、只读解除/`finally` 恢复、消息文本或 `DOCUMENT_SAVED` 载荷。不要在本模块中导入 `lsp_sync`（它不是构造器协作者）。

## 4. 测试 — 新建 `tests/test_document_flows_saveas.py`

无头构造模式：`tests/test_overlay_flows_hex.py:395-419`
（使用 `cast(Any, ...)` 替代对象的 DocumentFlows）和
`tests/test_cmd_cd.py:82-115`。使用真实的 `EditorSession(YateConfig())` 并调用
`session.new_buffer()`，使 `Document.name`、`Document.save` 和缓冲区状态都是
真实的；使用 `tmp_path` 进行真实磁盘写入。每个测试都必须有完整
类型标注、英文 docstring、`from __future__ import annotations`、绝对
导入，且不使用 `TYPE_CHECKING`。

记录用替代对象（名称仅供参考，行为固定）：

- `spawn`：追加 `(work, kwargs)` 并返回 `None`；`work` 是一个
  `functools.partial`，因此断言可以检查 `work.func.__name__`、
  `work.args[0]`（`Document`）和 `work.args[1]`（之前的路径）。
- `lsp`：暴露异步的 `on_document_retargeted(doc, previous_path)` 和异步的
  `notify_saved(doc)`，二者会追加到调用列表；如果借助 `cast(Any, ...)` 使 pyright 保持零诊断，也可用 `MagicMock`。
- `workspace`：`.root: Path | None = None` 加上 `set_root(path)` 记录器
  （`resolve_input_path` 会读取 `.root`，`yate/flows/document_flows.py:132-146`）。
- `explorer_tree.refresh_tree()`、`events.emit(event, payload)`、
  `prompt_bar.activate(mode, initial=..., on_submit=...)`、
  `message(text, kind)`、`report(text, kind)`、`refresh_ui()`、
  `mounted() -> True`、`reveal_explorer()` 等记录器。

精确的测试用例：

| # | 测试名称 | 安排/执行 | 断言（具体值） |
|---|---|---|---|
| 1 | `test_save_as_on_unnamed_buffer_spawns_retarget_with_none_previous_path` | `session.new_buffer()`；`session.doc.buffer.insert_text("print(1)\n")`；`flows.save_as(str(tmp_path / "new.py"))` | `dest.read_text(...) == "print(1)\n"`；`doc.path == dest`；`doc.name == "new.py"`；恰好 1 次 spawn，满足 `work.func.__name__ == "on_document_retargeted"`、`work.args == (doc, None)`、`kwargs["group"] == "lsp-sync"`；`refresh_ui` 调用次数 == 1；消息包含 `"saved"` |
| 2 | `test_save_as_on_named_buffer_passes_previous_path` | 创建 `source = tmp_path/"old.py"`，内容为 `"seed"`；`session.open(source)`；`flows.save_as(str(tmp_path/"renamed.py"))` | spawn 参数 `(doc, source)`；`doc.path == renamed`；`source.read_text() == "seed"`；`renamed.read_text() == "seed"`；spawn 次数 == 1 |
| 3 | `test_save_as_failure_spawns_no_retarget_and_keeps_previous_path` | 无名称文档；monkeypatch `Document.save` 使其抛出 `OSError("disk full")`（或让目标成为目录，使 `os.replace` 失败）；`flows.save_as(str(dest))` | spawn 次数 == 0；`doc.path is None`；`refresh_ui` 调用次数 == 1；记录了一条 `"save failed"` 错误消息；无异常逸出 |
| 4 | `test_save_as_prompt_path_uses_the_same_retarget_path` | 无名称文档；`flows.save_as(None)` | `prompt_bar.activate` 被调用一次且 `mode == "save"`；随后 `flows._submit_save_as(str(dest))` | 恰好 1 次 retarget spawn，参数为 `(doc, None)`；`doc.path == dest` |
| 5 | `test_write_on_named_buffer_still_spawns_notify_saved` | `session.open(source)`；用 `insert_text("x")` 将缓冲区标脏；`flows.save_document()` | 恰好 1 次 spawn，其 `work.func.__name__ == "notify_saved"`；无 retarget spawn；`source.read_text()` 反映写入结果；`refresh_ui` 调用次数 == 1 |

负向演练（记录在 §6）：在改动 `_submit_save_as` 之前，用例 #1 必须因 `spawn count == 0` 和 `refresh_ui calls == 0` 而失败；改动后必须转绿。不要在未经产品改动就自动成功的假对象上做断言。

## 5. 验收命令（可复制粘贴，从 worktree 根目录执行）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_document_flows_saveas.py -q
.venv\Scripts\python.exe -m pytest tests/test_cmd_cd.py tests/test_shell_flows.py tests/test_overlay_flows_hex.py -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -c "from pathlib import Path; print(len(Path('yate/flows/document_flows.py').read_text(encoding='utf-8').splitlines()))"
```

通过标准：所有命令退出码为 0；pyright 0 错误；架构 37 通过；
`document_flows.py` 保持低于 800 行。注意本子计划的第一条命令要求
子计划 b 的产品改动已就位（wave-1 门禁）。

## 6. 执行记录（填入实测数字）

| 命令 | 结果 | 退出码 |
|---|---|---|
| 负向演练（改动前的用例 #1） | 如预期失败：`spawn count == 0`、`refresh_ui calls == 0` | 1（负向演练） |
| `pytest tests/test_document_flows_saveas.py -q` | 5 通过 | 0 |
| `pytest ... -n auto`（cmd_cd / shell_flows / overlay_flows_hex） | 全部通过 | 0 |
| `pytest tests/test_lsp.py -q -n auto` | 全部通过 | 0 |
| `pyright ...` | `0 errors, 0 warnings, 0 informations` | 0 |
| `pytest tests/test_architecture.py -q` | 37 通过 | 0 |
| `document_flows.py` 行数 | 533 | 0 |

偏差（一处，有证据支撑）：用例 #4 调用
`cast(Any, fx.flows)._submit_save_as(...)`，而不是直接调用该私有方法，因为 pyright strict 会在直接调用时报告 `reportPrivateUsage`；使用 `cast(Any, ...)` 是方案中记载的接缝。已在评审第 1 轮 §4 中验证。产品行为未改变。

## 7. 风险与回滚

- 风险：两个 worker（`retarget` + `doc_shown_later`）都发送 didOpen。由子计划 b 的 `_opening` 闸门缓解；本子计划的验收命令会重跑子计划 b 的用例 #7 和完整 LSP 套件。
- 风险：保存失败仍会使 LSP 管理器绑定到旧 URI。缓解：spawn 只位于成功分支内；`Document.save` 在失败时保持 `path` 不变（F11）；用例 #3 对此加以固定。
- 风险：prompt 路径上的 `_refresh_ui()` 会触发一次额外重绘。这与 `save_document` 已有的调用相同；没有新增定时器/worker 组。
- 回滚：revert 本波次的提交。子计划 b 仍然独立可用（其管理器 API 未被使用但无害）；但随后也必须回退子计划 d 手册中关于另存为接入的措辞。
