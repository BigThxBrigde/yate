# dap-support plan-c：editor_dap 协议层与类型（W2 串行起点）

主计划依据：§3 包设计、§3.1 protocol、§3.2 types；§11 时序。

## 目标

建立 `yate/editor_dap/` L0 叶包骨架：分帧复用 + DAP 消息构造/解析 +
数据类型与状态枚举，纯标准库、UI 无关、零 Textual import。

## 非目标

不含 client/manager（plan-d/e）；不改 editor_lsp 任何代码。

## 独占文件清单（只改这些）

- `yate/editor_dap/__init__.py`（新增）— 包 docstring + `__all__`，形态仿
  [editor_lsp/__init__.py:1-36](../../yate/editor_lsp/__init__.py)
  （本期 `__all__` 仅收 types/protocol 公共名，plan-e 增补 manager）；
- `yate/editor_dap/protocol.py`（新增）— re-export 分帧原语
  （`MAX_MESSAGE_BYTES`/`encode_message`/`parse_headers`/`decode_body`/
  `read_message`，来源 [editor_lsp/protocol.py:28/:35/:73/:94/:105](../../yate/editor_lsp/protocol.py#L28)）；
  `build_request` / `build_response_body` / `is_event` / `event_body` /
  `JSON_MESSAGES` / `DapError(RuntimeError)`；
- `yate/editor_dap/types.py`（新增）— `DebuggerConfig` / `Breakpoint` /
  `StackFrame` / `Scope` / `Variable` / `StoppedSnapshot`（全部
  `@dataclass(frozen=True)`，字段见主计划 §3.2）+ `SessionState(str, enum.Enum)`
  六态；`DebuggerConfig.handles(filetype)`；
- `tests/test_dap_protocol.py`（新增）。

## 实施要点

1. 0-based 语义在 types 里冻结：`Breakpoint.row` / `StackFrame.row` 永远
   0-based（无源码 -1），转换只发生在 plan-e 的 manager 边界。
2. `SessionState` 不与 LSP 的 `ServerState`（client.py:53）共用。
3. 禁止 `Any`（`launch: dict[str, Any]` 除外，附理由注释）、`TYPE_CHECKING`、
   Protocol；模块头 `from __future__ import annotations`。
4. 架构边界：editor_dap 是 L0 叶包，不 import 上层（可 import
   `editor_lsp.protocol` 与 `editor_core`）。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dap_protocol.py -q
.venv\Scripts\python.exe -m pyright yate/editor_dap
.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/test_lsp.py -q
```

## 风险与回滚

- 分帧 re-export 与 LSP 演化耦合：只 re-export 五个稳定函数，零拷贝；
  中立化下沉列入 Phase 后重构项（主计划 §12）。
- 回滚：整目录删除即可（无外部依赖方）。
