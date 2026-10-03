# dap-support plan-e：DapManager 与包导出（W2 串行收口）

主计划依据：§3.4 manager 设计与关键行为 1-8。

## 目标

注册表 + 断点存储 + 单会话生命周期 + stopped 快照 + 输出环形缓冲 +
`shutdown_all`；`editor_dap/__init__.py` 导出补全。此后包为 plan-i/j 的
唯一依赖面。

## 非目标

不含扩展桥（plan-f）；不含 launch 参数的 yaterc 注入实现
（`set_debug_options` 接口先冻结，数据来自 plan-h）。

## 独占文件清单（只改这些）

- `yate/editor_dap/manager.py`（新增）；
- `yate/editor_dap/__init__.py`（修改：补 `DapManager` 等导出）；
- `tests/test_dap_manager.py`（新增）。

## 实施要点（结构对照 `LspManager`）

1. 构造 keyword-only `(workspace_root=None, on_event=None, client_factory=None)`
   （对照 [editor_lsp/manager.py:74-92](../../yate/editor_lsp/manager.py#L74-L92)）；
   `_make_client` 工厂 :214-220 范式。
2. 注册/同名替换 :102-131 语义；`config_for(filetype)`；`states()`（注册表
   视角，未启动=CONFIGURED，对照 :154-169）；`error_for` :176-181。
3. `root_for` 三层逻辑 :193-212 复刻；`program` 绝对路径；未保存文件拒绝
   （返回 False + 回调 failed）。`Document` 运行时直接 import（对照
   [manager.py:24](../../yate/editor_lsp/manager.py#L24)）。
4. launch 序列（主计划 §3.4 行为 3）：start → initialized → 全部断点文件
   setBreakpoints → setExceptionBreakpoints([]) → launch（不 await）→
   configurationDone；失败 FAILED + teardown。launch 参数合成 + 白名单
   （env/stopOnEntry/args）+ 未知键报错不盲传。
5. stopped 拉取链与 `StoppedSnapshot` 组装；单项失败降级；continued 清
   snapshot；output 环形缓冲（256KB，category 区分）；terminated 保留断点。
6. 单会话约束（RUNNING/PAUSED/STARTING 再 launch → False + failed）。
7. 坐标 1-based↔0-based 只在 client↔manager 边界。
8. `shutdown_all` 幂等；`set_debug_options(options: dict)` 存储注入。
9. 测试用 `FakeClient` + `client_factory` session fixture（照搬
   [test_lsp.py:554-608](../../tests/test_lsp.py#L554-L608) /
   [:665-692](../../tests/test_lsp.py#L665-L692) 手法，含 cast）。
   必测清单见主计划 §8.1。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dap_manager.py tests/test_dap_client.py tests/test_dap_protocol.py -q
.venv\Scripts\python.exe -m pyright yate/editor_dap
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 风险与回滚

- 事件回调抛异常拖垮读循环：manager 内全部 try/except + 降级 + `failed` 回调，
  绝不让事件处理抛异常（行为 4）。
- 回滚：删除 manager.py 与测试；`__init__` 导出还原（client/protocol 不受影响）。
