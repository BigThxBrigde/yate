# perf-audit-fixes-lsp-sync-plan-a（成员 A1：P6 + P5 + P10a）

总纲：[overview.md](overview.md)（目标/纪律/波次以它为准）。证据与修复方向来源：
[评审记录](../../reviews/2026-10-26-perf-audit.md) §Major P5/P6、§Minor P10。

## 一、目标

修复 editor_lsp 同步路径的三条性能缺陷：
1. **P6（major）**：`LspClient._pending` 完成后不清理，每次补全请求泄漏一个 future
   及其原始响应 payload（数百 KB 级），直到连接 teardown；
2. **P5（major）**：`notify_edit` 在"是否变化"短路之前物化整篇文档文本
   （`get_text()` = `"\n".join(self.lines)`），每键 O(文档)；didChange 防抖只延迟
   发送不延迟构建；
3. **P10a（minor）**：`_uri` 每次调用 `Path.resolve().as_uri()`（Windows 上是真实
   文件系统调用），每键 + 每渲染行各一次，无缓存。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/editor_lsp/manager.py`
- `yate/editor_lsp/client.py`（仅当 P6 实现需要时才动；预期主要在 manager.py）

关联测试（可改/可新增用例）：
- `tests/test_lsp.py`、`tests/test_lsp_parsing.py`、`tests/test_app_lsp.py`、
  `tests/test_python_lsp_ext.py`、`tests/test_completion_popup.py`

## 三、实施要点（带证据）

### P6
- 证据：`client.py:388-396` 的 `request()` 有 `finally: self._pending.pop(request_id, None)`；
  而 `manager.py:520-530` 的 `request_completion` 直接 `start_request` + `await future`，
  成功（524）、报错（529-530 `return []`）、取消（525-528 re-raise）三条路径均不弹出。
- 改法：`request_completion` 用 `try/finally` 包裹 await，finally 中
  `client._pending.pop(request_id, None)`（镜像 `request()`）。取消路径同样弹出
  （finally 天然覆盖）。
- 注意：`$/cancelRequest` 逻辑若依赖 `_pending` 查找 in-flight 请求，确认弹出时机
  在 future settle 之后即可（await 返回/抛出时请求已结束，弹出无副作用）。

### P5
- 证据：`manager.py:397-414`——405 行 `text = doc.buffer.get_text()` 先物化，406 行
  才比较 `state.last_synced`；调用点 `editor.py:740`（每键经 `refresh_ui → _refresh_lsp`）。
- 改法：
  1. `OpenDocState` 增字段 `last_synced_version: int`（打开时记录当时 `buffer.content_version`）；
  2. `notify_edit` 先比 `doc.buffer.content_version != state.last_synced_version`：
     相等直接 return（零分配）；不等才 `get_text()` 并与 `state.last_synced` 比对
     （保留该精确比较，防止 version 推进但文本未变的双保险——如 fill_lines），
     决定是否重排防抖 timer；`last_synced_version` 在 `_flush_change` 发送成功后更新；
  3. `get_text()` 的调用从每键路径移入 `_flush_change`（防抖回调内物化一次）：
     timer 携带 doc/uri，回调内重新 `get_text()` 再发送——注意回调运行时 buffer 可能
     又变了，这正是期望（发送最新文本），比较仍以回调内文本对 `last_synced`。
- 约束：didChange 协议形态不变（仍 Full，增量同步是非目标）；对外行为（防抖 0.25s、
  didSave、版本号递增）保持。

### P10a
- 证据：`manager.py:687-689` `_uri` → `protocol.py:156-158` `path_to_uri` =
  `Path(path).resolve().as_uri()`；调用点：`notify_edit`:401（每键）、
  `diagnostics_for`:609 等诊断查询（每渲染行经 `editor_view/editor.py:415`）。
- 改法：manager 内加 URI 缓存 `dict[Path, str]`（`_uri` 查缓存，未命中才
  `protocol.path_to_uri`）；文档关闭（`_open` 移除处）时同步移除对应缓存键，
  防止长会话累积。`protocol.py` 不改（保持纯函数）。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_lsp_parsing.py tests/test_app_lsp.py tests/test_python_lsp_ext.py tests/test_completion_popup.py -q
```

pyright 零诊断、pytest 全绿为硬门槛。测试文件不存在时先列 `tests/` 确认名称。
为 P6/P5 各补至少一条回归用例（泄漏可断言 `_pending` 为空；P5 断言 version 未变时
不物化全文——可用 monkeypatch 计数 `get_text` 调用）。

## 五、报告格式

改动清单（文件 + 要点）→ 实际执行的命令与结果摘要（通过/失败数）→ 偏离与未解决项。

## 六、风险与回滚

P5 行为风险：version 双保险比较若误删，可能出现"version 推进但文本未变仍重排 timer"
（无害）或"文本已变但不发送"（有害）——必须保留文本精确比较作双保险。
回滚：本成员产物单独提交，可独立 revert。
