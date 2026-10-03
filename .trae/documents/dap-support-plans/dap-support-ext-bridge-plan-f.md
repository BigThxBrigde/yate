# dap-support plan-f：DapExtensionBridge 与 api.dap（W3）

主计划依据：§4.1；§1 扩展注册桥行。

## 目标

扩展经 `api.dap.register_debugger(...)` 注册调试器，与 `api.lsp` 完全对称。

## 非目标

不改 `load_startup_extensions`（[services/extensions.py:543-631](../../yate/services/extensions.py#L543-L631)
——DAP 注册在同一遍 setup(api) 自然生效）；不写内置扩展（plan-g）。

## 独占文件清单（只改这些）

- `yate/services/extensions.py` — 新增 `DapExtensionBridge`（镜像
  `LspExtensionBridge` [extensions.py:93-138](../../yate/services/extensions.py#L93-L138)：
  `register_debugger(name, *, command, args=None, filetypes=None, env=None,
  launch=None, root_markers=None)`，`name` 位置参其余 keyword-only，空 command
  懒失败；`statuses()` / `has_state()` 对照 :131-133/:135-138）；
  `ExtensionAPI` 增加 `dap` property（紧邻 `lsp` property :314-317）；
  `root_markers=None` 给 DAP 默认 marker 元组（与 LSP 桥默认同构）；
- `tests/test_dap_bridge.py`（**新建**；注意
  [tests/test_extensions.py](../../tests/test_extensions.py) 无任何桥测试先例，
  不要往里塞——该文件归 trust/load/lifecycle 用例）。

## 实施要点

1. 桥内完成参数校验/默认值，构造 `DebuggerConfig`（types 来自 plan-e）交给
   manager `register_debugger`；manager 未就绪（diag 场景）时的状态查询走
   `statuses()`/`has_state()`。
2. `launch` 模板原样透传存入 `DebuggerConfig.launch`，不在桥内校验键
   （adapter 专有键合法，白名单在 manager 注入层）。
3. 测试必测：参数默认值与转发、同名替换、空 command 仍注册、
   `statuses()`/`has_state()`、`filetypes` 转入 `handles()`。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dap_bridge.py tests/test_extensions.py -q
.venv\Scripts\python.exe -m pyright yate/services
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 风险与回滚

- `ExtensionAPI` 面变大：只加一个 property，不新增协议/基类（R2/R8）。
- 回滚：删除桥类 + property + 测试（无其他消费方）。
