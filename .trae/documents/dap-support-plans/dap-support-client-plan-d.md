# dap-support plan-d：DapClient（W2 串行）

主计划依据：§3.3 client 设计；§11 时序。

## 目标

`DapClient` 全生命周期：进程拉起、initialize 握手、seq/future 请求匹配、
event 分发、步进/求值/终止/清理；内存假 adapter 单测固化协议顺序。

## 非目标

不实现会话/断点策略（plan-e）；不接 UI。

## 独占文件清单（只改这些）

- `yate/editor_dap/client.py`（新增）；
- `tests/test_dap_client.py`（新增）。

## 实施要点（结构对照 `LspClient`）

1. 构造签名对齐：`(config, root_path, *, on_event=None, connect=None,
   init_timeout=20.0)`（对照 [editor_lsp/client.py:180-188](../../yate/editor_lsp/client.py#L180-L188)）；
   同名私有件 `_next_seq` / `_pending` / `_read_task` / `_bg_tasks` /
   `_write_lock` / `_connect_override` / `_connecting`。
2. `start()` :215-268 范式 → initialize 公共参数冻结（主计划 §3.3 注释块，
   不允许扩展覆盖）；`wait_initialized_event()`。
3. `_connect()` :270-308 范式 → `create_subprocess_exec`（`stderr=DEVNULL`、
   cwd=root；无 spawn 方法名）。
4. `stop()`/`_cleanup()` :310-375 范式 → 借 `_connecting` future 等在途
   spawn 收尾（Windows cwd 占用链路）。
5. `launch()` 特殊点：`start_request` 拿 future **不 await**，直接
   configurationDone；响应晚到 future 收口。`_dispatch`：response 按
   `request_seq` 配 future（success=false → `DapResponseError`）；event 转发
   `on_event(name, body)`，client 自身只捕 `initialized`/`exited`/`terminated`；
   reverse request 回 `success=false, message="unsupported by yate"`。
6. 错误类：`DapResponseError` / `DapConnectionError`（对照 :71/:81）。
7. 测试手法照搬 LSP：`FakeReader`（[test_lsp.py:41-64](../../tests/test_lsp.py#L41-L64)）、
   `FakeProc`/`ServerHarness`（:148/:161-551，`connect=` 注入）；
   必测：initialize 参数、**顺序固化**（setBreakpoints → launch 不 await →
   configurationDone）、乱序 response 配对、超时 FAILED+teardown、
   stop 终止在途 spawn（对照 :466-548）、reverse request unsupported。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dap_client.py tests/test_dap_protocol.py -q
.venv\Scripts\python.exe -m pyright yate/editor_dap
.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q
```

## 风险与回滚

- debugpy 版本时序差异：顺序断言按 DAP 规范而非实现观察；手动验证在收尾
  （主计划 §8.3）。
- 回滚：删除 client.py + 测试文件（plan-e 尚未引用时无连带）。
