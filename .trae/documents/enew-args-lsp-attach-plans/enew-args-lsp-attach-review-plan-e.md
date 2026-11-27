# 无名称缓冲区 LSP 接入子计划 e — 评审第 1 轮严重/次要项修复（wave-3，串行）

主计划：[`../enew-args-lsp-attach-plan.md`](../enew-args-lsp-attach-plan.md) · 波次表：
[`overview.md`](overview.md)。从 `../yate-enew-args-lsp-attach` worktree 根目录运行。
由第 5 步评审第 1 轮触发：**0 阻塞项 / 2 严重 / 4 次要**，因此在任何进一步的代码改动之前，第 6 步返回第 2 步完成本设计。

## 1. 输入

- 评审第 1 轮发现项（严重#1：retarget 到另一个标签页拥有的 URI；
  严重#2：路径拼写与 URI 等价性；次要#3：开启过程中关闭留下幽灵
  条目；次要#4：三行未覆盖；次要#5：783/800 行预算；
  次要#6：缺少多参数 `:enew` 用例）。
- 主计划 §3 决策 C（尤其是被否决的备选方案 C4：“路径未变则保留 didSave，在相同路径上重启服务端文档会无谓地丢弃诊断信息”）以及 §6 风险表。
- [`enew-args-lsp-attach-state-plan-b.md`](enew-args-lsp-attach-state-plan-b.md) §3.4/§3.5，了解
  `on_document_shown` / `_close_uri` / `on_document_retargeted` 的当前形态。
- 规则：`.trae/rules/architecture-boundaries.md` §三.7（>800 行需要豁免或拆分）、R4/R2/R6、`.trae/rules/python-coding-style.md`、`.trae/rules/misc-rules.md` §四（英文注释/docstring）。

### 设计裁决（第 2 步增补，必须按原文实现）

1. **开放文档的身份是 URI，而不是 `Path`。** `previous_path`
   与 `doc.path` 通过 `protocol.path_to_uri(...)` 比较（该方法会解析路径，
   `../../yate/editor_lsp/protocol.py:156-158`）。因此像 `sub/../a.py` 这样的拼写算作*同一个*文档，保留现有的
   didOpen，只发送 didSave。旧拼写的 `_uri_cache` 键会被丢弃，以免等价路径累积重复键。
2. **retarget 可能会从另一个标签页夺取 URI。** 如果 `_open[new_uri]` 存在
   且 `state.doc is not doc`，先关闭该条目（尽力而为的 didClose），
   再让 `on_document_shown` 打开被重定向的文档。否则
   `on_document_shown` 会在 `uri in self._open` 处短路，服务端
   永远看不到新拥有者的内容。
3. **关闭优先于进行中的开启。** `_close_uri` 会从 `_opening` 中丢弃该 URI；
   `on_document_shown` 在 `await
   ensure_client` 之后以及 `await client.notify("didOpen")` 之后重新检查成员资格，若期间发生关闭则中止，不写入 `_open`。
4. **不新增模块 / 不新增公开方法。** `manager.py` 目前 783 行
   （比 §三.7 阈值低 17 行）。所有修复都是对三个现有方法的就地重写；必要时缩短 docstring/注释。
   执行者在验收时必须断言行数 `< 800`。
5. **`DocumentFlows` 中不引入 `resolve()`/`normpath`。** 已否决：`resolve()`
   会跟随符号链接，从而改变保存目标文件；而 `normpath` 在某些平台上会改变 `link/../file` 的词法含义。
   URI 比较在不触碰保存路径或 `workspace.set_root(path.parent)` 的前提下修复 LSP 行为。

## 2. 独占文件

- `yate/editor_lsp/manager.py`（写 —— 仅限 `_close_uri`、
  `on_document_shown`、`on_document_retargeted`）
- `tests/test_lsp.py`（仅追加新用例）
- `tests/test_cmd_enew.py`（仅追加一个用例）

其它一切只读，包括 `yate/flows/document_flows.py`、
`yate/commands.py`、手册、冒烟文件、`tests/test_architecture.py` 以及所有
`.trae/**` 文档（回填由主代理负责）。

## 3. `yate/editor_lsp/manager.py` 中的具体改动

### 3.1 `_close_uri`（`:405-425`）— 一行代码 + 一条注释

紧跟在 `state = self._open.pop(uri, None)` 之后添加：

```python
# A close during an in-flight didOpen wins: the opener checks this set
# after each await and must not resurrect the URI.
self._opening.discard(uri)
```

所有其它语句、`R3 N5` 注释以及
`log.debug("didClose failed for %s: %s", uri, exc)` 消息保持逐字不变。

### 3.2 `on_document_shown`（`:361-403`）— 两次成员资格复查

保留现有结构。将：

```python
client = await self.ensure_client(doc)
if client is None:
    return
```

替换为：

```python
client = await self.ensure_client(doc)
# _close_uri drops the uri from _opening, so a close during the handshake
# aborts this open instead of writing a ghost entry back into _open.
if client is None or uri not in self._opening:
    return
```

并且在 `didOpen` 通知的 `except (LspError, OSError): return` 块之后
（即 `self._open[uri] = OpenDocState(...)` 之前）紧接着添加：

```python
if uri not in self._opening:
    return
```

`finally: self._opening.discard(uri)` 保持在原位置不变。

### 3.3 `on_document_retargeted`（`:433-451`）— 替换整个方法体

```python
async def on_document_retargeted(
    self, doc: Document, previous_path: Path | None
) -> None:
    """Rebind a saved-as document on its server.

    *previous_path* is the path before the successful write (``None`` for a
    buffer that was unnamed).  Paths are compared by URI, not spelling: an
    unchanged URI keeps didSave, a changed one closes the old URI before
    didOpen.  A first path is treated as a document-shown event.  When another
    tab owns the target URI, its entry is closed so this document can own it.
    """
    if doc.path is None:
        return
    new_uri = self._uri(doc)
    if previous_path is not None:
        previous_uri = protocol.path_to_uri(previous_path)
        if previous_uri == new_uri:
            self._uri_cache.pop(previous_path, None)
            await self.notify_saved(doc)
            return
        await self._close_uri(previous_uri)
    owner = self._open.get(new_uri)
    if owner is not None and owner.doc is not doc:
        await self._close_uri(new_uri)
    await self.on_document_shown(doc)
```

不要改动 `state_for_doc`、`supports`、`states`、`ensure_client`、
`notify_saved`、`notify_edit`、`shutdown_all` 或任何线路载荷。不新增
导入（`Path`、`protocol` 已经存在）。不要引入新的
`ServerState`、回调或上下文类型（R2/R8，§三.1）。

## 4. 测试

### 4.1 `tests/test_lsp.py` — 追加 7 个用例

复用该模块现有的假客户端 fixture 和 `asyncio.run(scenario())`
模式。下面每条断言都是具体的可观察值。

| # | 测试名称 | 安排/执行 | 断言 |
|---|---|---|---|
| 1 | `test_on_document_retargeted_same_uri_with_different_spelling_only_sends_did_save` | 假客户端会话；`doc.path = tmp_path/"a.py"`；`await mgr.on_document_shown(doc)`；设置 `doc.path = tmp_path/"sub"/".."/"a.py"`（无需文件 I/O）；`await mgr.on_document_retargeted(doc, tmp_path/"a.py")` | `didClose` 次数 == 0；`didOpen` 次数 == 1（仅最初那一次）；恰好 1 个 `didSave`；`mgr.is_open(doc) is True`；`len(cast(Any, mgr)._uri_cache) == 1` |
| 2 | `test_on_document_retargeted_to_uri_owned_by_another_document_reopens_for_new_owner` | 假客户端会话；`a = Document(Path("x.py"))` 文本为 `"a\n"`，`b = Document(Path("y.py"))` 文本为 `"b\n"`；`await mgr.on_document_shown(a)`；`await mgr.on_document_shown(b)`；设置 `a.path = Path(b.path)`；`await mgr.on_document_retargeted(a, Path("x.py"))` | 旧 `x.py` URI 收到 `didClose`；`y.py` URI 收到 `didClose`；恰好 1 个 `didOpen`，其 `uri == protocol.path_to_uri(y.py)` 且 `text == "a\n"`（按新 URI 过滤）；`cast(Any, mgr)._open[new_uri].doc is a`；`mgr.is_open(a) is True` |
| 3 | `test_on_document_retargeted_without_path_is_noop` | `doc = Document(None)`；`await mgr.on_document_retargeted(doc, None)` | 未创建客户端；`_open` 为空；`_opening` 为空；无通知 |
| 4 | `test_on_document_shown_without_path_is_noop` | `doc = Document(None)`，且 `filetype_override = "py"`；`await mgr.on_document_shown(doc)` | 未创建客户端；`_open` 为空；`_opening` 为空 |
| 5 | `test_on_document_shown_notify_failure_leaves_no_open_state` | 假客户端的 `notify` 对 `didOpen` 抛出 `LspError`；`await mgr.on_document_shown(doc)` | `_open` 为空；`_opening` 为空；无异常逸出 |
| 6 | `test_on_document_closed_during_open_handshake_leaves_no_ghost_state` | 假客户端的 `start()` 会等待 `asyncio.sleep(0)`；`task = asyncio.create_task(mgr.on_document_shown(doc))`；`await asyncio.sleep(0)`；`await mgr.on_document_closed(doc)`；`await task` | 无 `didOpen` 通知（或者，如果通知已经发出，则之后 `_open` 中没有该 URI）；`_opening == set()`；`mgr.is_open(doc) is False` |
| 7 | `test_on_document_retargeted_same_uri_does_not_leave_duplicate_cache_keys` | 与 #1 相同的设置，但显式断言缓存键 | `protocol.path_to_uri(a.py)` 在 `_uri_cache.values()` 中恰好出现一次；当旧拼写键 `tmp_path/"a.py"` 与 `doc.path` 不同时，该键不存在 |

负向演练（记录在 §6）：在改动产品代码之前，用例 #1 和 #2 必须失败（#1 当前会发送 didClose+didOpen，因为 `Path(sub/../a.py) !=
Path(a.py)`；#2 当前会留下 `_open[new_uri].doc is b`，且不为 `a` 发送 didOpen）。改动之后两者都必须转绿。不要削弱断言。

### 4.2 `tests/test_cmd_enew.py` — 追加 1 个用例

| # | 测试名称 | 安排/执行 | 断言 |
|---|---|---|---|
| 8 | `test_enew_with_multiple_arguments_warns_and_creates_no_buffer` | 全新 fixture；`fx.entry.func("a.py b.py")` | `new_buffer_calls == []`；`notes == [(_USAGE_MESSAGE, "warn")]` |

## 5. 验收命令（可复制粘贴，从 worktree 根目录执行）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_cmd_enew.py -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_cmd_enew.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_document_flows_saveas.py tests/test_app_lsp.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_cmd_enew.py --cov=yate.editor_lsp.manager --cov=yate.commands --cov-branch --cov-report=term-missing --cov-fail-under=0 -q
.venv\Scripts\python.exe -c "from pathlib import Path; n=len(Path('yate/editor_lsp/manager.py').read_text(encoding='utf-8').splitlines()); print('manager.py lines:', n); assert n < 800"
```

通过标准：每条命令退出码均为 0；`-n auto` 与 `-n 1` 结果一致；pyright 0
错误；架构 37 通过；覆盖率报告不再将
`manager.py:364`、`:387-388`、`:445` 列为未覆盖（行号可能变动）；
行数 `< 800`。仅在并行时出现的失败必须用 `-n 1` 复核并修复，不能记为偶发抖动。

## 6. 执行记录（填入实测数字）

| 命令 | 结果 | 退出码 |
|---|---|---|
| 负向演练（改动前的 #1、#2） | 在旧实现上均已失败（`assert ['textDocument/didClose'] == []`、`assert new_uri in closes`）；评审第 2 轮针对 `383affe` 的克隆重跑了 4/4 个 wave-3 用例 —— 在那里 4 个全失败，在 `28a5fdf` 上全部通过 | 1（负向演练） |
| `pytest tests/test_lsp.py tests/test_cmd_enew.py -q -n auto` | 主代理独立复跑：96 通过（含 flows/app_lsp）；最终第 7 步全量套件：3422 通过、10 跳过 | 0 |
| `pytest ... -n 1` | 与 `-n auto` 一致（评审第 2 轮：聚焦集合 83 通过） | 0 |
| `pytest tests/test_document_flows_saveas.py tests/test_app_lsp.py -q -n auto` | 全部通过 | 0 |
| `pyright ...` | `0 errors, 0 warnings, 0 informations` | 0 |
| `pytest tests/test_architecture.py -q` | 37 通过 | 0 |
| 局部覆盖率 `--cov-fail-under=0` | `manager.py` 在聚焦集合上 88%；全量套件 `--cov-fail-under=75`：`Total coverage: 92.86%`；原有的 `:364`、`:387-388`、`:445` 以及新增的第二处 `_opening` 复查均已覆盖 | 0 |
| `manager.py` 行数 | 797（`< 800`，未登记 `SIZE_EXEMPT_FILES`） | 0 |

偏差（两处，有证据支撑）：
1. 用例 #2 的 didOpen 断言按新 URI 的 `text == "a\n"` 过滤
   （方案本来就说“按新 URI 过滤”），因为事先打开了两个文档，didOpen 总数为 3。
2. 主代理额外追加了一个测试
   `test_on_document_closed_during_didopen_notify_leaves_no_open_state`，用于覆盖
   方案 §3.2 新增的第二处 `_opening` 复查分支；实测聚焦覆盖率从存在未覆盖的 `:393` 变为新增行全部覆盖。

两处偏差都只涉及测试，位于子计划 e 的独占文件清单内，并已通过 pyright 0 / 72 通过 / 评审第 2 轮（0 阻塞项 / 0 严重）验证。

## 7. 风险与回滚

- 风险：关闭另一个标签页的 URI 会使该标签页后续的编辑共享新拥有者的 `OpenDocState`。这是两个标签页绑定到同一路径所固有的（这是 `EditorSession` 模型既有的限制，可通过 `:saveas` 触发）；LSP 线路协议规定每个 URI 只有一个文档。该项已登记为后续待办，不在本次修复中解决（超出本次修复范围）。
- 风险：如果某些无关代码丢弃了 URI，`_opening` 成员资格检查会使一次合法的开启中止。只有 `_close_uri` 会丢弃（加上开启者自身的 `finally`），所以这是有意为之：关闭优先。
- 风险：行数守卫。所有改动都是就地的；执行者断言 `< 800`，若触到上限必须精简文字，绝不能新增模块。
- 回滚：revert 本波次的提交；wave-1/2 的行为保持不变，但两处严重问题会回来，因此任何回滚后都必须重做第 5 步评审。
