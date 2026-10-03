# editor_dap：DAP 调试支持与内置 Python 调试实施计划（2026-10-03 重锚版）

> **实施状态：❌ 未实施。** 分支 `feat/dap-support`（worktree `../yate-dap-support`）。
>
> **2026-10-03 全面再锚定**：本版依据当前 master（`2c124a7`）逐文件核对重锚。
> 相比 2026-09-15/09-28 版本，**集成层架构已彻底变化**，旧引用全部作废：
>
> - `yate/app_features/` **已删除**（架构测试明言 "stays deleted"）：
>   ex 命令注册表在 [yate/commands.py](../../yate/commands.py)（`register_commands` :80-365），
>   动作表在 [yate/actions.py](../../yate/actions.py)（`populate` :26-196），
>   `ActionRegistry` / `CommandRegistry` 定义在 [yate/registries.py](../../yate/registries.py)（:37 / :72）。
> - **L3 中枢是 `Editor`（yate/editor.py），不是 app.py**：`ed.lsp = LspManager(...)` 在
>   [editor.py:91-94](../../yate/editor.py#L91-L94)；事件落点 `yate/lsp_sync.py::LspSync.on_event`
>   （[lsp_sync.py:80](../../yate/lsp_sync.py#L80)）；`shutdown_all` 在 `Editor.on_unmount`
>   （[editor.py:462](../../yate/editor.py#L462)）；worker 范式
>   `run_worker(..., group="lsp-sync", exclusive=False, exit_on_error=False)` 在
>   [editor.py:832-835](../../yate/editor.py#L832-L835)；app.py 全文无 `lsp` 字样。
>   DAP 同构：`ed.dap` + 新流程模块 `yate/dap_sync.py::DapSync`（须登记
>   `tests/test_architecture.py:114-165` 的 `UI_FROZEN_FILES`，R11）。
> - 终端面板开关**无模块级编排函数**：`TerminalPanel.toggle/open/close` 自持于
>   [editor_view/terminal.py:453/460/474](../../yate/editor_view/terminal.py#L453)，
>   Editor 按键路由 [editor.py:576-578](../../yate/editor.py#L576-L578)，
>   ex 命令 `term/terminal/termclose` 注册于 [commands.py:333-335](../../yate/commands.py#L333-L335)。
>   DebugPanel 完全镜像此形态（**不再新建 app_features/debug.py**）。
> - 底部 dock 挂载在 `Editor.compose`（[editor.py:416-420](../../yate/editor.py#L416-L420)），
>   高度/隐藏在 `Editor.on_mount`（[:425-426](../../yate/editor.py#L425-L426)）。
> - 扩展加载是 `ExtensionFlows.load_extensions`（editor.py:429 调用；
>   `load_startup_extensions` 定义于 [services/extensions.py:543-631](../../yate/services/extensions.py#L543-L631)），
>   yaterc 声明注册是 `ExtensionFlows.register_configured_servers`
>   （[extension_flows.py:104](../../yate/extension_flows.py#L104)）——**没有 `load_startup_services`**。
> - JS 扩展示例**禁用 TYPE_CHECKING**（R6 全仓 0 处），改为直接
>   `from yate.services.extensions import ExtensionAPI`（与
>   [python_lsp.py:34](../../yate/extensions/python_lsp.py#L34) 同型）。
> - 实施按**六个波次、12 份子计划**精细拆分，见 §8 与
>   [dap-support-plans/overview.md](dap-support-plans/overview.md)。
>
> 其余既有结论仍成立：仓库无任何 DAP 产物（2026-10-03 grep 复核 0 命中）；
> 打包零改动（hatchling `packages=["yate"]` [pyproject.toml:111-112](../../pyproject.toml#L111-L112)，
> PyInstaller 整树收集 [yate.spec:106-113](../../pack/yate.spec#L106-L113) /
> [yate-onefile.spec:114-121](../../pack/yate-onefile.spec#L114-L121)）。

新增 `yate/editor_dap` 包（零第三方依赖、纯标准库、UI 无关），架构完全镜像
`editor_lsp`：DAP-over-stdio 客户端 + 会话/断点管理器；内置
`extensions/python_dap.py` 扩展通过 debugpy 提供 Python 调试；随包附带
`extensions/example_js_dap.py.example`，演示用同一套 `api.dap` 接入
js-debug-adapter；TUI 层新增断点 gutter 标记、调试面板、状态栏段与
F5/F9/F10/F11 键位及 `:debug` 系列命令。本计划按三期切分，**本期实施
Phase 1（MVP）**，Phase 2/3 仅冻结方向。

---

## 1. 现状与可复用资产（2026-10-03 核对行号）

| 资产 | 位置 | DAP 复用方式 |
|------|------|--------------|
| Content-Length 分帧 | [protocol.py:28](../../yate/editor_lsp/protocol.py#L28) `MAX_MESSAGE_BYTES`、:35 `encode_message`、:73 `parse_headers`、:94 `decode_body`、:105 `read_message` | DAP 与 LSP stdio 分帧相同，**直接 import 复用**（§4.1） |
| 单进程 JSON-RPC 客户端范式 | [client.py](../../yate/editor_lsp/client.py)：`ServerState` :53、`LspError` :67、`LspResponseError` :71、`LspConnectionError` :81、`ServerConfig` :85、`LspClient.__init__` :180-188（`connect=` 注入、`init_timeout`）、`start()` :215-268、`_connect()` :270-308（**无 spawn 方法**，`create_subprocess_exec` :278-286）、`stop()` :310-335、`_cleanup()` :337-375 | `DapClient` 照此结构重写；消息模型改 seq/request_seq |
| 多配置管理器 + 事件回调 | [manager.py](../../yate/editor_lsp/manager.py)：Document 运行时 import :24、`LspManager.__init__` :74-92（全 keyword-only）、注册/替换 :102-131、`states()` :154-169、`error_for` :176-181、`root_for` :193-212、`_make_client` :214-220 | `DapManager`：注册表 + 单会话 + 断点存储 + 事件回调；`on_event(kind: str)` 签名一致 |
| 包 docstring/__all__ 形态 | [editor_lsp/__init__.py:1-36](../../yate/editor_lsp/__init__.py)（`__all__` 7 项） | `editor_dap/__init__.py` 同型 |
| 扩展注册桥 | [extensions.py:93-138](../../yate/services/extensions.py#L93-L138) `LspExtensionBridge`（`register_server` :99-111：`name` 位置参 + 其余 keyword-only；`statuses` :131-133；`has_state` :135-138）；`ExtensionAPI` :277-413；`lsp` property :314-317 | 新增姊妹 `DapExtensionBridge`（`api.dap.register_debugger`），同文件同风格 |
| 内置扩展注册与发现 | [python_lsp.py](../../yate/extensions/python_lsp.py)：直接 import ExtensionAPI :34、`_venv_langserver` :37-50、env 覆盖/opt-out :64-83、`setup(api)` :86-105 | `python_dap.py` 五级发现（含解释器相邻 launcher 与 find_spec 兜底） |
| 声明式配置 | [config.py](../../yate/config.py)：`_KNOWN_OPTIONS` :60-64（不含 language_servers——列表/字典类选项走独立 `_extract_*`，入口 `_extract_options` :668）、`LanguageServerSpec` :77-94、`_extract_language_servers` :672-701、`terminal_height` 默认 12 :158 | Phase 2 再做 `debug_adapters`；Phase 1 加 dict 选项 `debug_options`（走 `_extract_debug_options`，非 `_KNOWN_OPTIONS`） |
| gutter 渲染 | [editor_view/editor.py](../../yate/editor_view/editor.py)：`gutter_width()` :344-346（`max(3, digits) + 3`）、行号+诊断拼接 :666-687、当前行底色 `t.surface` :664 | 公式 +1（●/▶ 一列）；诊断列逻辑不动 |
| gutter 宽度下游消费 | [completion.py:283](../../yate/completion.py#L283)（全仓唯一消费点，:280-285） | 宽度 +1 自动传播，无需改 completion |
| LSP 事件刷 UI | editor.py:91-94 构造 + lambda → [lsp_sync.py:80](../../yate/lsp_sync.py#L80) `on_event`；worker 范式 [editor.py:832-835](../../yate/editor.py#L832-L835)（`group="lsp-sync"`） | `ed.dap` 同构 + `yate/dap_sync.py::DapSync`（R11 白名单登记） |
| Editor 持有与关闭 | editor.py:91-94（构造）、on_mount 扩展加载 :429 / yaterc 注册 :430、on_unmount :449-464（`lsp.shutdown_all` :462） | `ed.dap` 同构；退出并列 `shutdown_all()`；DAP 无 yaterc 声明注册（Phase 1 仅扩展） |
| 动作表 | [actions.py:26-196](../../yate/actions.py#L26-L196) `populate`；`command_prompt` :175；注册表 [registries.py:37](../../yate/registries.py#L37) | 新增 `debug_start_or_continue/toggle_breakpoint/step_over/step_into/step_out/pause_debug/debug_stop/debug_panel` |
| ex 命令注册表 | [commands.py:80-365](../../yate/commands.py#L80-L365) `register_commands`；`term/terminal/termclose` :333-335 | `:debug` 系列在此注册 |
| 底部面板范式（widget 自持） | [editor_view/terminal.py](../../yate/editor_view/terminal.py)：`TerminalView(Widget)` :73、`TerminalPanel(Vertical)` :377、`TOGGLE_KEYS` :56-59、`toggle` :453 / `open` :460 / `close` :474 / `apply_height` :485；挂载 editor.py:416-420 `#bottom-dock`；高度/隐藏 :425-426；按键路由 editor.py:576-578 | `DebugPanel(Vertical)` 同构挂同一 dock、terminal 之上；同一时刻只显一个（互斥在 Editor 路由侧实现，terminal.py 零改动）；高度复用 `terminal_height` |
| 集成终端后端 | [yate/editor_term/](../../yate/editor_term)：emulator / pty_proc / shells | **Phase 1 不碰**；Phase 3 RunInTerminal 复用（§13） |
| 状态栏分段 | [statusbar.py](../../yate/editor_view/statusbar.py)：`refresh_status` :91-159、`_lsp_segment` :161-185、右段拼装 :149-158（lsp :155-157） | 仿加 `_debug_segment()`，插在 lsp 段后 |
| 键位层（原始字节） | [keymaps/base.py](../../yate/keymaps/base.py)：`SPECIAL_KEYS` :29-59（f1-f12 :47-58）、`KEY_ALIASES` :62-85、`parse_key` :88-126（shift 只大写单字符 :104-106）、`key_name` :128-158、`Keymap.add_binding` :234-252；[keyproto/legacy.py](../../yate/keyproto/legacy.py)：`_NAMED_KEYS` :15、`_MOD_ARROWS` :38-43、`_MOD_SPECIAL` :45-49、`event_to_raw` :52-84、`textual_key_to_raw` :87-124（**修饰表不含 F 键**，带修饰 F 键返回 None :124） | **需先扩展**（§6.0 前置）：`<shift-f5>` 等当前解析为裸 F5 |
| vsc 键位现状 | [vsc.py](../../yate/keymaps/vsc.py)：帮助分类 :10-18（9 类）、F5→command_prompt :95（注释 :92-94）；空闲 **f6/f7/f9/f10/f11/f12** | F5 让给调试、command_prompt 迁 F7（§6.0 决策 1） |
| vim 键位现状 | [vim.py](../../yate/keymaps/vim.py)：`:` :170、f5→command_prompt :175-177；f6/f7/f9-f12 无绑定 | vim 调试键仅 NORMAL/VISUAL 生效；`:` 不变 |
| 诊断报告 | [diagnostics.py](../../yate/diagnostics.py)：节注册表是 `format_report` 内**局部列表** :75-88（lsp 注册 :85，`_section_lsp` :380-403；config 节 :277-291），当前 **12 节**；`--diag` 入口 [cli.py:357-375](../../yate/cli.py#L357-L375)（print_report :374） | lsp 后插 `dap` 节；测试硬编码 12 节清单须同步（§9.2） |
| welcome 页 | [editor.py:736-779](../../yate/editor_view/editor.py#L736-L779) `_welcome_lines`（hints :766-779：Ctrl+P/Alt+Shift+P/:/Ctrl+F/Ctrl+`/Ctrl+S/F1，**不含 F5**） | 无 F5 文案迁移；是否增列调试键实施时自定 |
| 模板分发 | [user_setup.py:104-105](../../yate/services/user_setup.py#L104-L105) `*.py.example` 通配拷贝 | `example_js_dap.py.example` 零改动自动随 `--setup-defaults` 分发 |
| 架构守卫 | [tests/test_architecture.py](../../tests/test_architecture.py)：`UI_FREE_PACKAGES` :102-108、`UI_FROZEN_FILES` :114-165（现登记 8 个流程模块） | `dap_sync.py` 新增 editor_view 导入须登记（R11）；命名守卫禁 `*Controller/*Host` 等 |

---

## 2. DAP 与 LSP 的协议差异（设计依据，冻结不变）

| 维度 | LSP（JSON-RPC 2.0） | DAP |
|------|--------------------|-----|
| 分帧 | `Content-Length: N\r\n\r\n` + JSON | **相同** |
| 请求 | `{jsonrpc, id, method, params}` | `{seq, type:"request", command, arguments}` |
| 响应 | `{jsonrpc, id, result/error}` | `{seq, type:"response", request_seq, command, success, body, message}` |
| 服务端推送 | method 的 notification | `{seq, type:"event", event, body}` |
| 反向请求 | server request（少见） | `runInTerminal` 等（Phase 1 统一回 unsupported） |
| 握手 | `initialize` → `initialized` 通知 | `initialize` → 响应含 capabilities → server **`initialized` event** → `setBreakpoints`/`setExceptionBreakpoints` → `launch` → `configurationDone` |
| 坐标 | 0-based 行/列 | **1-based 行、1-based 列**（manager 边界转换，UI 永远收 0-based） |
| 进程模型 | 一 project root 一 server | 一调试会话一 adapter；MVP 全局单会话 |

debugpy 接入（与 pylsp 一样走 stdio）：`pip install debugpy` 提供
`debugpy-adapter`（等价 `python -m debugpy.adapter`）；debuggee 的
stdout/stderr 经 DAP `output` event 回传（`console: "internalConsole"` +
`redirectOutput: true`）。不需要 socket/attach，不引入 `runInTerminal`。

---

## 3. `editor_dap` 包设计（UI 无关、纯标准库，L0 叶包）

```text
yate/editor_dap/
  __init__.py     # 公共导出（仿 editor_lsp/__init__.py:1-36 的包 docstring 与 __all__）
  protocol.py     # DAP 消息构造/解析；复用 editor_lsp 的分帧原语
  client.py       # DapClient：一个 adapter 进程 + 握手 + seq/future + event
  manager.py      # DapManager：注册器、会话、断点存储、高层调试动作
  types.py        # DebuggerConfig / Breakpoint / StackFrame / Scope / Variable /
                  # StoppedSnapshot / SessionState（LSP 无独立 types 模块，DAP 独立建）
```

### 3.1 protocol.py

分帧原语从 LSP 直接复用并 re-export（零拷贝、零回归，不改动 LSP）：

```python
from yate.editor_lsp.protocol import (  # 与 LSP 共享的纯 Content-Length 分帧
    MAX_MESSAGE_BYTES, decode_body, encode_message,
    parse_headers, read_message,
)
```

> 备选（不做）：分帧下沉中立模块 `yate/editor_rpc/framing.py`；列入 §13 重构项。

DAP 消息层：

```python
JSON_MESSAGES = ("request", "response", "event")

def build_request(seq: int, command: str, arguments: dict | None = None) -> dict
def build_response_body(message: dict) -> tuple[int, bool, str, object]
    # 从 response 取 (request_seq, success, message, body)
def is_event(message: dict, name: str | None = None) -> bool
def event_body(message: dict) -> dict
```

`DapError(RuntimeError)` 为本包错误基类（对照 `LspError`
[client.py:67](../../yate/editor_lsp/client.py#L67)）；`DapResponseError` /
`DapConnectionError` 继承它（对照 :71 / :81）。

### 3.2 types.py

```python
@dataclass(frozen=True)
class DebuggerConfig:            # 镜像 ServerConfig（client.py:85）的形状
    name: str                    # "python"
    command: str                 # debugpy-adapter 绝对路径；空串=不可用
    args: list[str]
    filetypes: list[str]         # ["py"]
    env: dict[str, str] | None
    launch: dict[str, Any]       # 静态 launch 参数模板（type/request/console/...）
    root_markers: list[str]
    def handles(self, filetype: str) -> bool: ...

@dataclass(frozen=True)
class Breakpoint:
    path: Path
    row: int                     # 永远 0-based（manager 发协议时 +1）
    condition: str | None = None # Phase 2

@dataclass(frozen=True)
class StackFrame:
    id: int
    name: str                    # 函数名 / "<module>"
    path: Path | None
    row: int                     # 0-based（协议行-1）；无源码时 -1
    column: int                  # 0-based
    source_present: bool

@dataclass(frozen=True)
class Variable:
    name: str
    value: str
    type_name: str
    variables_reference: int     # >0 可展开
    indexed_variables: int
    named_variables: int

@dataclass(frozen=True)
class Scope:
    name: str                    # "Locals" / "Globals"
    variables_reference: int
    expensive: bool

@dataclass(frozen=True)
class StoppedSnapshot:
    reason: str                  # breakpoint | step | exception | pause | entry
    thread_id: int
    thread_name: str
    frames: list[StackFrame]
    active_frame: StackFrame | None
    scopes: list[Scope]
    variables: dict[int, list[Variable]]  # variables_reference → 已拉取列表
```

会话状态枚举（**不与 LSP 共用**——`ServerState`
[client.py:53](../../yate/editor_lsp/client.py#L53) 表达不了运行/暂停）：

```python
class SessionState(str, enum.Enum):
    CONFIGURED = "configured"   # 已注册、无会话
    STARTING = "starting"       # initialize → configurationDone 期间
    RUNNING = "running"
    PAUSED = "paused"           # stopped event 后
    TERMINATED = "terminated"   # debuggee 退出（会话残留可重启 launch）
    FAILED = "failed"           # 启动失败 / adapter EOF
```

manager → UI 的事件回调签名与 LSP 完全一致：`on_event(kind: str)`，kind 取
`stopped | continued | output | terminated | initialized | failed`。UI 收到
回调后从 manager 读 `snapshot()` / `output_text()` / `session_state()`。

### 3.3 client.py — DapClient

结构对照 `LspClient`（同名私有件：`_next_seq`、`_pending: dict[int, Future]`、
`_read_task`、`_bg_tasks`、`_write_lock`、`connect=` 传输注入、`init_timeout`、
`_connecting` future；构造签名对齐以便 `client_factory` 形态一致，对照
[manager.py:214-220](../../yate/editor_lsp/manager.py#L214-L220)）：

```python
class DapResponseError(DapError):  # success=False：command + message + body
class DapConnectionError(DapError):

class DapClient:
    def __init__(self, config: DebuggerConfig, root_path: Path, *,
                 on_event=None, connect=None,
                 init_timeout: float = 20.0) -> None: ...

    async def start(self) -> dict:
        """拉起 adapter（_connect）+ initialize 握手；返回 capabilities。"""
        # initialize arguments 冻结（不允许扩展覆盖公共参数）:
        # {"adapterID": "yate", "clientID": "yate", "clientName": "yate",
        #  "locale": "en", "linesStartAt1": True, "columnsStartAt1": True,
        #  "pathFormat": "path", "supportsRunInTerminalRequest": False,
        #  "supportsVariableType": True, "supportsVariablePaging": False,
        #  "supportsConditionalBreakpoints": False}   # Phase 2 改 True

    async def wait_initialized_event(self, timeout: float = 10.0) -> None: ...
    async def set_breakpoints(self, path: Path, rows_1based: list[int]) -> list[dict]: ...
    async def set_exception_breakpoints(self, filters: list[str]) -> None: ...
    async def launch(self, arguments: dict) -> None: ...
    async def configuration_done(self) -> None: ...
    async def threads(self) -> list[tuple[int, str]]: ...
    async def stack_trace(self, thread_id: int, levels: int = 50) -> list[dict]: ...
    async def scopes(self, frame_id: int) -> list[dict]: ...
    async def variables(self, variables_reference: int) -> list[dict]: ...
    async def evaluate(self, expression: str, *, frame_id: int | None,
                       context: str = "repl") -> dict: ...
    async def continue_(self, thread_id: int) -> None: ...
    async def next_(self, thread_id: int) -> None: ...
    async def step_in(self, thread_id: int) -> None: ...
    async def step_out(self, thread_id: int) -> None: ...
    async def pause(self, thread_id: int) -> None: ...
    async def terminate(self) -> None: ...           # 礼貌终止 debuggee
    async def disconnect(self, *, terminate_debuggee: bool = True) -> None: ...
    async def stop(self) -> None: ...                # 兜底 terminate/kill
```

dispatch 规则（`_dispatch`）：

- `type=="response"`：以 `request_seq` 取 future；`success=false` 用
  `DapResponseError` 完成；
- `type=="event"`：转发 `on_event(event_name, body)`；client 自身只捕获
  `initialized`（置 future）、`exited`/`terminated`（记录退出码）；
- `type=="request"`（reverse request）：Phase 1 统一回
  `success=false, message="unsupported by yate"`。

`launch()` 特殊点：**launch 发出后直接发 configurationDone，不等 launch
响应**（DAP 标准序列；launch 用 start_request 拿 future 不 await，响应晚到
由 future 收口）。测试必须固化此顺序。

进程拉起/teardown 复刻 LSP 经验件：`_connect()`
[client.py:270-308](../../yate/editor_lsp/client.py#L270-L308)（`stderr=DEVNULL`、
cwd=root）+ 在途停止分支；`stop()`/`_cleanup`
[:310-375](../../yate/editor_lsp/client.py#L310-L375) 借 `_connecting` future
等在途 `_connect()` 收尾（Windows cwd 占用链路，测试固化于
[test_lsp.py:466-548](../../tests/test_lsp.py#L466-L548) 与真实子进程版
[:1054-1111](../../tests/test_lsp.py#L1054-L1111)）。

### 3.4 manager.py — DapManager

```python
class DapManager:
    def __init__(self, *, workspace_root=None, on_event=None,
                 client_factory=None) -> None: ...

    # ---- 注册（扩展），镜像 LspManager（:102-131 同名替换语义）
    def register_debugger(self, config: DebuggerConfig) -> None: ...
    def configs(self) -> list[DebuggerConfig]: ...
    def config_for(self, filetype: str) -> DebuggerConfig | None: ...
    def states(self) -> dict[str, SessionState]: ...
    def error_for(self, name: str) -> str: ...

    # ---- 断点（dict[path, set[row]]，0-based）
    def toggle_breakpoint(self, path: Path, row: int) -> bool: ...
    def breakpoints_for(self, path: Path) -> list[int]: ...
    def has_breakpoint(self, path: Path, row: int) -> bool: ...
    def clear_breakpoints(self, path: Path | None = None) -> None: ...

    # ---- 会话（MVP 单会话）
    async def launch(self, doc_or_path, *, program_args=None) -> bool: ...
    async def resume(self) -> None: ...
    async def step_over(self) -> None: ...
    async def step_into(self) -> None: ...
    async def step_out(self) -> None: ...
    async def pause(self) -> None: ...
    async def stop_session(self) -> None: ...
    async def evaluate(self, expression: str) -> str: ...
    async def expand_variable(self, variables_reference: int) -> list[Variable]: ...

    def snapshot(self) -> StoppedSnapshot | None: ...
    def session_state(self) -> SessionState: ...
    def output_text(self) -> str: ...            # 环形缓冲（上限 256KB）
    def active_location(self) -> tuple[Path, int] | None: ...  # 0-based

    async def shutdown_all(self) -> None: ...
    def set_debug_options(self, options: dict) -> None: ...
```

关键行为：

1. **root/program 解析**：复刻 `root_for` 三层逻辑
   [manager.py:193-212](../../yate/editor_lsp/manager.py#L193-L212)；
   `program` 必须绝对路径；仅支持已保存且无未保存改动的文件，否则返回
   False 并回调 `failed`。
2. **launch 参数合成**：`{**config.launch, "program": ..., "args": ...,
   "cwd": str(root), **self._debug_options}`；debug_options 只合并跨 adapter
   通用键（Phase 1：env/stopOnEntry/args），未知键收集为错误不盲传；模板误写
   program/cwd 与注入键冲突时以注入值为准并在诊断记录。
3. **启动序列**（事件循环内串行）：`client.start()` → 等 `initialized` →
   对所有已存断点文件逐个 `set_breakpoints` → `set_exception_breakpoints([])`
   → `launch(args)`（不 await 响应）→ `configurationDone()`；任一步失败：
   状态 FAILED、回调 failed、teardown。
4. **stopped 事件处理**：threads（取 threadId 名字，失败给 "Thread N"）→
   stackTrace（≤50 帧）→ 第 0 帧 scopes → 非 expensive scopes 拉 variables →
   组装 `StoppedSnapshot` → `on_event("stopped")`；单项失败降级（如
   variables 失败保留 frames），事件处理绝不抛异常。
5. **continued/output/terminated**：continued 清 snapshot；output 追加环形
   缓冲（区分 category，`\r\n` 归一）；terminated/exited：回调、状态
   TERMINATED、输出保留到下次 launch、client 清理但**断点保留**。
6. **单会话约束**：RUNNING/PAUSED/STARTING 再 launch 返回 False 并回调
   failed（"debug session already active; use :debug-stop"）。
7. **坐标转换**：仅 client↔manager 边界做 1-based↔0-based；无源码
   `StackFrame.row = -1`。
8. **纯异步、无 Textual import**：只 import asyncio/dataclasses/pathlib/
   typing + 本包 + `editor_core.document.Document`（运行时直接 import，同
   [manager.py:24](../../yate/editor_lsp/manager.py#L24) 先例）。

---

## 4. 扩展层：`api.dap` 与内置 `python_dap.py`

### 4.1 DapExtensionBridge（services/extensions.py）

与 [LspExtensionBridge :93-138](../../yate/services/extensions.py#L93-L138)
对称（`name` 位置参、其余 keyword-only、空 command 懒失败）；
`ExtensionAPI` 增加 `dap` property（紧邻 [lsp property :314-317](../../yate/services/extensions.py#L314-L317)）：

```python
class DapExtensionBridge:
    """``api.dap`` -- register debug adapters from an extension."""
    def register_debugger(self, name: str, *, command: str, args=None,
                          filetypes=None, env=None,
                          launch: dict | None = None,
                          root_markers=None) -> None: ...
    def statuses(self) -> dict[str, str]: ...
    def has_state(self, name: str, state: str) -> bool: ...  # 对齐 :135-138
```

参数校验/默认值在桥内完成（`root_markers=None` 给 DAP 默认 marker 元组，
与 LSP 桥同构），构造 `DebuggerConfig` 交给 manager。

### 4.2 extensions/python_dap.py（内置，可禁用）

镜像 [python_lsp.py](../../yate/extensions/python_lsp.py) 的文档串与发现逻辑，
直接 `from yate.services.extensions import ExtensionAPI`（:34 先例，
**禁止 TYPE_CHECKING**），**五级发现**：

```python
# 禁用：disabled_extensions = ["python_dap"]
# 覆盖：set YATE_PYTHON_DAP=C:\venv\Scripts\debugpy-adapter.exe
# opt-out：YATE_PYTHON_DAP=0 只注册不 spawn（懒失败）

def discover_command() -> tuple[str, list[str]]:
    # 1) YATE_PYTHON_DAP（shlex.split(posix=True)；0/off/false/none/no 为 opt-out）
    # 2) shutil.which("debugpy-adapter")
    # 3) 解释器相邻 launcher：sys.executable 目录下 debugpy-adapter.*（复刻 _venv_langserver :37-50）
    # 4) importlib.util.find_spec("debugpy") → (sys.executable, ["-m", "debugpy.adapter"])
    # 5) ("", [])

def setup(api: ExtensionAPI) -> None:
    api.dap.register_debugger(
        name="python", command=command, args=args, filetypes=["py"],
        root_markers=["pyproject.toml", "setup.py", "setup.cfg",
                      "requirements.txt", "Pipfile", ".git"],
        launch={"type": "python", "request": "launch",
                "console": "internalConsole", "redirectOutput": True,
                "justMyCode": False, "subProcess": True, "stopOnEntry": False},
    )
```

注册时序：`Editor.on_mount` 的扩展加载（editor.py:429 → `ExtensionFlows` →
`load_startup_extensions` [extensions.py:543-631](../../yate/services/extensions.py#L543-L631)）
在同一遍 setup(api) 中自然生效，Phase 1 无需第三步。

### 4.3 yaterc：`debug_options`

**不走 `_KNOWN_OPTIONS`**（[config.py:60-64](../../yate/config.py#L60-L64) 只收
标量选项；language_servers 等结构化选项走独立 `_extract_*`，入口
`_extract_options` :668）。新增 `_extract_debug_options`（镜像
`_extract_language_servers` :672-701 的形状与 `config.errors.append` 收集风格
:684-686）：

```python
# Phase 1 白名单仅三个跨 adapter 通用键：env / stopOnEntry / args
debug_options = {"stopOnEntry": False}
debug_options = {"env": {"FLASK_DEBUG": "1"}}
# console 固定 internalConsole，Phase 3 随 integratedTerminal 放开
```

值必须为 dict，键在白名单内，否则记入 `config.errors`（启动消息行 +
yaterc 节 + `--diag` 可见）并忽略该键。adapter 专有键（debugpy 的
`justMyCode`/`subProcess`、js-debug 的 `outputCapture` 等）**不进** yaterc，
只在扩展 launch 模板里给。声明式 `debug_adapters` 列入 Phase 2。

### 4.4 扩展示例：`extensions/example_js_dap.py.example`（新增）

随包提供 JS/Node 调试扩展示例（适配器
[microsoft/vscode-js-debug](https://github.com/microsoft/vscode-js-debug)
独立 npm 包，命令 `js-debug-adapter`，`npm install -g js-debug-adapter`）。
与 example_ext.py.example 同级同后缀；`--setup-defaults` 经
[user_setup.py:104-105](../../yate/services/user_setup.py#L104-L105) 通配拷贝，
改名 `.py` 即激活。**代码纪律（2026-10-03 修正）**：直接
`from yate.services.extensions import ExtensionAPI` +
`from __future__ import annotations`，**不得使用 TYPE_CHECKING**（R6 全仓 0 处，
架构测试扫描 yate/ 会拦截；旧版示例中的 TYPE_CHECKING 写法作废）。

要点（写入 dap 文档）：

- `initialize` 的 `adapterID` 由 yate 固定发 `"yate"`，adapter 选择以
  `launch["type"]`（`pwa-node`）为准；client 不允许扩展覆盖 initialize 公共参数；
- 与 python_dap 的差异只有三处：发现命令、filetypes/root_markers、adapter
  专有 launch 模板；会话/断点/步进/变量链路完全复用；
- Windows 全局 npm 产出 `js-debug-adapter.CMD`，`shutil.which` 与
  `create_subprocess_exec` 按现有 LSP spawn 链路处理；
- 未安装适配器时懒失败：注册照常，F5 才报
  `js-debug-adapter not found — npm install -g js-debug-adapter`；
- js-debug 会发 `startDebugging` reverse request 自动挂子进程；Phase 1 回
  unsupported 只调根进程（Phase 2 放开）。

### 4.5 同一模式可接的其他 stdio adapter（文档列表示例，不内置）

| 语言 | adapter 命令 | launch type/备注 |
|------|--------------|------------------|
| JS/TS/Node | `js-debug-adapter` | `pwa-node`（本计划随示例） |
| C/C++/Rust | `gdb -i dap` / `lldb-dap` / `codelldb` | args 用 `["-i","dap"]` |
| Go | `dlv dap` | `mode: debug` 等专有键走 launch 模板 |
| Ruby | `rdbg --open --command --` | |
| Bash | `bash-debug` | 需要 pathBash 等 launch 键 |

---

## 5. TUI 集成（按当前架构：Editor 中枢 + 面板自持 + DapSync）

### 5.0 前置改造：键位层与 F5 冲突（必须先做）

**事实 1：F5 已被占用。** vsc 键位 F5 → `command_prompt`
（[vsc.py:95](../../yate/keymaps/vsc.py#L95)，注释 :92-94；动作注册
[actions.py:175](../../yate/actions.py#L175)）；vim 模式 F5 → `command_prompt`
（[vim.py:175-177](../../yate/keymaps/vim.py#L175-L177)），`:` 是 vim 的
ex 入口（:170）。手册 F5=命令行 en 6 处：191/341/359/561/585/1382；
zh 6 处：182/324/341/526/545/1244（`yate/resources/manual.{en,zh}.md`）。
README 键位表各一处：[README.md:98](../../README.md#L98)、
[README.zh.md:123](../../README.zh.md#L123)。F1 help、F2 shell、F3 find next、
F4 replace、F8 manual；**f6/f7/f9/f10/f11/f12 空闲**（vsc 与 vim 相同）。

**事实 2：带修饰 F 键无法解析。** `parse_key` shift 分支只大写单字符
（[base.py:104-106](../../yate/keymaps/base.py#L104-L106)）；
`textual_key_to_raw` 修饰表（`_MOD_ARROWS` :38-43、`_MOD_SPECIAL` :45-49）
不含 F 键，带修饰 F 键返回 None（[legacy.py:124](../../yate/keyproto/legacy.py#L124)）。

**决策**：

1. **F5 按 VS Code 惯例让给调试**（无会话=launch、PAUSED=continue、
   RUNNING=noop 提示）；vsc 模式 ex 命令行迁 **F7**；vim 模式删除 F5 的
   command_prompt 绑定（`:` 保持唯一入口）。同步 vsc.py :92-95、手册 en/zh
   各 6 处、README 键位表 1 处；帮助覆盖层自动生成，新增 DBG 分类后自动出现。
   - 备选 A（保守）：F5 保留给 ex 行，调试命令驱动——偏离 VS Code 肌肉记忆；
   - 备选 B：F5 按 filetype 隐式复用——行为不可预测，不推荐。
2. **扩展键位层支持带修饰 F 键**：xterm `~` 族基准码 F5=15、F6=17、F7=18、
   F8=19、F9=20、F10=21、F11=23、F12=24；带修饰发
   `\x1b[<code>;<param>~`，param=2(shift)/3(alt)/5(ctrl)/6(ctrl+shift)。
   改造点：`parse_key` 对 `~` 族 F 键按修饰符拼参数序列（命名风格与
   `test_modified_arrows` [test_app_textual.py:97](../../tests/test_app_textual.py#L97)
   的修饰键名一致）、`key_name` 与 `KEY_ALIASES`（base.py :62-85/:128-158）
   增加逆映射；`textual_key_to_raw` 识别 Textual 的 `shift+f5`/
   `ctrl+shift+f5` 事件名（mods 匹配风格同 :38-49）。本期只绑定
   Shift+F5、Shift+F11，其余参数序列一次性支持但不绑定。
3. **两套键位都加调试键**：vsc 全局；vim 仅 NORMAL/VISUAL（INSERT 不拦截）。
   vim 用户始终可用 `:debug` 系列。
4. 新增帮助分类常量 `DBG = "Debug"`（vsc.py 常量区 :10-18）。

### 5.1 断点与会话状态模型（Editor 侧）

- 断点唯一存储在 `DapManager`（按 path），Editor 不另存；
- 执行行 `dap.active_location()` 供 gutter 读取；
- `ed.dap = DapManager(...)` 构造于 editor.py:91-94 旁，事件经 lambda 落
  **`yate/dap_sync.py::DapSync.on_event(kind)`**（镜像
  [lsp_sync.py:80](../../yate/lsp_sync.py#L80) `LspSync.on_event`）：
  - stopped/continued：所有 editor view refresh（gutter/执行行）、调试面板
    刷新、状态栏刷新；stopped 面板自动切 info；
  - output：面板开着则追加渲染；未开则消息行 "●" 提示；
  - terminated：消息行提示退出码、恢复 gutter、面板保留输出；
  - failed：消息行红字原因（adapter 不存在时给 `pip install debugpy` 提示）；
- 所有调试动作用 `self.app.run_worker(..., group="dap", exclusive=False,
  exit_on_error=False)` 发起（范式 [editor.py:832-835](../../yate/editor.py#L832-L835)；
  Editor 是 L3 唯一 App 句柄持有者，能力注入守卫 `test_flow_modules_hold_no_app_handle`）。

### 5.2 gutter 标记（editor_view/editor.py）

`gutter_width()` :344-346 由 `max(3, digits) + 3` 改 `+ 4`，gutter 布局从
`空|行号|空|诊断`（:666-687）扩为 `空|行号|空|诊断|调试点`，宽度恒定（与
会话无关，防抖动）；补全弹层复用 gutter_width（[completion.py:283](../../yate/completion.py#L283)）
自动跟随。调试点列：

| 情况 | 字符 | 样式 |
|------|------|------|
| 执行行（active_location 命中） | `▶` | t.yellow + bold |
| 普通断点行 | `●` | t.red |
| 命中断点的执行行 | `▶` 优先（黄） | |
| 其他 | 空格 | |

执行行整行：行号 bold + 行底 `t.surface`（复用 :664 既有逻辑，零 Theme 变更）。
welcome 页经同一 gutter 渲染（`_welcome_lines` :736），核对居中不错位。

### 5.3 调试面板：widget 自持（单文件，镜像 TerminalPanel）

`yate/editor_view/debug_panel.py`（新）：`DebugPanel(Vertical)` 对照
`TerminalPanel`（[editor_view/terminal.py:377](../../yate/editor_view/terminal.py#L377)），
包可聚焦 `DebugView(Widget, can_focus=True)` 对照 :73；**toggle/open/close/
apply_height 方法自持**（对照 :453/:460/:474/:485），只渲染与按键，不持有
调试状态；依赖经构造注入具体协作者或 `Callable`（R3：不 import
`yate.editor`）；**不引入 editor_term 依赖**（无 PTY）。挂载、取引用、
设高、初始 `display=False` 由 Editor 侧完成（editor.py compose :416-420 /
on_mount :425-426，见 §6 波次 j）。

与终端面板**互斥**：互斥逻辑在 **Editor 路由侧**（editor.py 按键处理与
命令入口），开 DebugPanel 前调 `terminal_panel.close()`，反向亦然；
`yate/editor_view/terminal.py` **零改动**。高度共用 `terminal_height`
（config.py :158/:619-631），`:set terminal_height` 对两者同时生效。

双模式：

- **out 模式**：debuggee 输出流（环形缓冲渲染，stderr 行 dim+红头标记，
  不做 ANSI 解析）；底部 evaluate 输入，`>` 开头，Enter 发
  `evaluate(context="repl")`，结果作为 console 类 output 追加；
- **info 模式**：stopped 时显示 Threads → Stack frames（当前帧 ▶）→
  Scopes → Variables（两级树缩进，`variables_reference>0` 标 `+`，Enter
  展开调 `expand_variable`）。未停止显示 "program is running / not started"。
- 模式切换：面板聚焦 Tab 或 `:debug-panel out|info`；stopped 自动切 info，
  continued 自动切 out。

MVP 不做：watch、多线程切换（默认 stopped 事件 threadId）、setVariable、
hover 求值。

### 5.4 状态栏（statusbar.py）

仿 `_lsp_segment`（:161-185）新增 `_debug_segment()`，接入右段拼装链
（:149-158，插在 lsp 段 :155-157 后）。仅会话非 CONFIGURED/TERMINATED 时
显示，无会话零占位：

```text
▮ debug: python  paused at main.py:42
▮ debug: python  running
▮ debug: python  failed: debugpy-adapter not found (pip install debugpy)
```

### 5.5 动作、命令与键位

动作注册在 [actions.py](../../yate/actions.py) `populate`（:26-196；键位只
引用动作名，动作体转发到 editor/dap_sync）：
`debug_start_or_continue`（按会话状态分发）、`toggle_breakpoint`、
`step_over`、`step_into`、`step_out`、`pause_debug`、`debug_stop`、
`debug_panel`。

命令注册在 [commands.py](../../yate/commands.py) `register_commands`
（:80-365；`term` 系列范式 :333-335）：

| ex 命令 | 动作 | vsc 默认键 | vim |
|---------|------|-----------|-----|
| `:debug [path]` | 启动调试（未保存先提示） | **F5**（无活动会话） | NORMAL F5 |
| `:cont`（`:continue`） | 继续 | **F5**（PAUSED 时） | NORMAL F5 |
| `:break` | 切换当前行断点 | **F9** | NORMAL F9 |
| `:next` | step over | **F10** | NORMAL F10 |
| `:step` | step into | **F11** | NORMAL F11 |
| `:finish` | step out | **Shift+F11**（§5.0 改造） | 同 |
| `:pause-debug` | 暂停 | F6 | NORMAL F6 |
| `:debug-stop` | 终止会话 | **Shift+F5**（§5.0 改造） | 同 |
| `:debug-restart` | Phase 2（本期报 "not yet"） | — | — |
| `:eval [expr]` | 暂停态求值 | 无（面板输入） | 同 |
| `:debug-panel [out\|info]` | 打开/切换调试面板 | F12 | NORMAL F12 |
| （迁移）ex 命令行 | 原 F5 动作 `command_prompt` | **F7** | `:` 不变 |

F5 上下文行为：无活动会话=launch、PAUSED=continue、RUNNING=noop 提示。
F9 无会话时也允许切换断点（断点先于会话存在，launch 时统一下发）。

### 5.6 关闭路径

- 退出：`Editor.on_unmount`（:449-464）在 `lsp.shutdown_all()`（:462）后并列
  `await self.dap.shutdown_all()`；terminate 3s 宽限再 disconnect/kill；
  各 teardown 相互隔离（沿用现有 try/except 模式）；
- 关闭被调试文件：不影响会话（断点按 path 存）；重开同名文件标记自然恢复；
- adapter 崩溃/EOF：reader 结束 → FAILED → 事件 failed（"debug adapter
  exited"）+ 面板保留输出。

---

## 6. 实施波次与子计划索引（Phase 1）

实施以子计划为唯一执行规范，每份子计划含独占文件清单与验收命令；
总纲与依赖关系见 [dap-support-plans/overview.md](dap-support-plans/overview.md)。

| 波次 | 子计划 | 内容 | 依赖 |
|------|--------|------|------|
| W1（并行） | [plan-a](dap-support-plans/dap-support-keys-plan-a.md) | 键位层带修饰 F 键（base.py + keyproto/legacy.py） | — |
| W1（并行） | [plan-b](dap-support-plans/dap-support-f5-migration-plan-b.md) | F5→F7 迁移（vsc/vim/手册/README） | — |
| W2（串行） | [plan-c](dap-support-plans/dap-support-protocol-plan-c.md) | `editor_dap/` protocol.py + types.py + `__init__` | — |
| W2（串行） | [plan-d](dap-support-plans/dap-support-client-plan-d.md) | `DapClient` | c |
| W2（串行） | [plan-e](dap-support-plans/dap-support-manager-plan-e.md) | `DapManager` + 包导出 | d |
| W3（并行） | [plan-f](dap-support-plans/dap-support-ext-bridge-plan-f.md) | `DapExtensionBridge` + `api.dap` | e |
| W3（并行） | [plan-g](dap-support-plans/dap-support-python-ext-plan-g.md) | python_dap.py + JS 范例 + 模板分发测试 | f |
| W3（并行） | [plan-h](dap-support-plans/dap-support-config-plan-h.md) | `debug_options` 配置 + yaterc.example | e |
| W4 | [plan-i](dap-support-plans/dap-support-tui-views-plan-i.md) | DebugPanel / gutter / 状态栏段（视图层） | c-e |
| W5 | [plan-j](dap-support-plans/dap-support-wiring-plan-j.md) | Editor 接线 / dap_sync / 动作 / 命令 / 调试键位 | a,b,e,f,i |
| W6（并行） | [plan-k](dap-support-plans/dap-support-diagnostics-plan-k.md) | `--diag` dap 节（12→13） | j |
| W6（并行） | [plan-l](dap-support-plans/dap-support-docs-plan-l.md) | 双语 dap 文档 / 手册调试章 / README / example_ext | j,k |

---

## 7. 错误处理与可发现性

| 场景 | 行为 |
|------|------|
| 未安装 debugpy | 扩展照常注册（懒失败）；`:debug` 时消息行 `no Python debug adapter found — pip install debugpy (or set YATE_PYTHON_DAP)` |
| initialize 超时/进程拉起失败 | FAILED + 消息行；teardown 不残留子进程（复刻 LSP in-flight 处理） |
| debuggee 立即退出 | terminated 事件 + 退出码；面板保留输出 |
| 未保存/无路径文件启动 | 拒绝并提示保存 |
| 调试中再按 F5 | continue；非暂停态给消息提示，不重复 launch |
| evaluate 在运行态调用 | 返回 "paused only"，不发请求 |
| js-debug `startDebugging` reverse request | Phase 1 回 unsupported，只调根进程 |
| 终端不上报带修饰 F 键 | 所有动作有 `:命令` 与命令面板兜底；dap 文档列出限制与原始序列 |
| 单文件单测全用内存假 adapter | `client_factory`/`connect` 双注入点，零真实进程 |

`yate --diag`（[cli.py:357-375](../../yate/cli.py#L357-L375)）在 lsp 节后新增
**`[dap]`** 节：debugger 名单、filetypes、发现 command（或 `(none)`）、
opt-out 状态、launch 模板键名、当前会话状态。风格沿用 lsp 节
（[diagnostics.py:380-403](../../yate/diagnostics.py#L380-L403)）两列缩进。

---

## 8. 测试方案

### 8.1 单元（无真实进程，镜像 LSP 测试手法）

LSP 手法照搬：分帧内存假 reader（`FakeReader`
[test_lsp.py:41-64](../../tests/test_lsp.py#L41-L64)）、TCP 回环假 server
（`FakeProc` :148 / `ServerHarness` :161-551，`connect=` 注入 :240）、manager 层
`FakeClient` :554-608 + `client_factory` session fixture
[:665-692](../../tests/test_lsp.py#L665-L692)（cast :687）。

- **tests/test_dap_protocol.py**：build_request 形状；response 解析
  （success/error、request_seq 关联）；event 判定；framing 往返；超长
  Content-Length 拒绝。
- **tests/test_dap_client.py**：脚本化 in-memory adapter——initialize 参数、
  **顺序固化**（setBreakpoints → launch 不 await → configurationDone）、
  request_seq 匹配（乱序也正确）、success=false → DapResponseError、
  initialize 超时 → FAILED + teardown、stop() 终止在途 spawn（对照
  [test_lsp.py:466-548](../../tests/test_lsp.py#L466-L548)）、reverse request
  收 unsupported。
- **tests/test_dap_manager.py**：注册/按 filetype 查/同名替换；断点 toggle
  去重、1-based 转换断言（lines=[n+1...]）；launch 合成参数（program 绝对
  路径、cwd=root、白名单合并、未知键拒绝）；未保存拒绝；二次 launch 拒绝；
  stopped 拉取链与快照组装（scopes 失败降级、无 source row=-1）；step/continue/
  pause/terminate 透传 threadId；output 分类与环形上限；terminated 清
  snapshot 保留断点；shutdown_all 幂等。
- **tests/test_python_dap_ext.py**：discover 五级、launch 模板与 filetypes、
  disabled_extensions 不加载（手法参照现有 test_python_lsp_ext.py）。
- **tests/test_dap_examples.py**：`example_js_dap.py.example` 静态/加载校验
  （compile 通过；假 ExtensionAPI exec 断言注册参数；`YATE_JS_DAP` 三态；
  **断言无 TYPE_CHECKING、直接 import ExtensionAPI**）。
- **tests/test_dap_bridge.py**（新建；注意 test_extensions.py 无任何桥测试
  先例）：`api.dap.register_debugger` 默认值与转发、空 command 仍注册、
  `statuses()`/`has_state()`。
- **tests/test_config.py 增补**：debug_options 合法 dict 合并、非 dict 报错、
  未知键报错（风格参照 language_servers 区 :244-488）。
- **键位层测试**：`parse_key("<shift-f5>")` ↔ `textual_key_to_raw("shift+f5")`
  双向一致、`key_name` 逆映射、裸 F5 不被覆盖（归入现有
  [test_keyproto.py](../../tests/test_keyproto.py) /
  [test_key_notation.py](../../tests/test_key_notation.py)）。

### 8.2 UI / 集成

- **tests/test_dap_tui.py**（新建，pilot headless 范式
  [test_app_textual.py:109-117](../../tests/test_app_textual.py#L109-L117)，
  `wait_until` :39-47）：gutter 断言（●/▶/叠加优先/宽度恒定 +1/welcome 不错位）；
  F9 切换/取消；无会话状态栏无 debug 段、PAUSED 段含 `paused at`；F7 开
  ex 行、F5 启动/继续；`:debug/:next/:cont/:debug-stop` 在假 manager 下
  动作正确、未保存提示；debug panel output 追加/stopped 切 info/变量展开/
  evaluate 回显；与 terminal 面板互斥；Editor 关闭路径调用 dap.shutdown_all。
- **tests/test_architecture.py 增补**：`UI_FROZEN_FILES`（:114-165）登记
  `dap_sync.py`（R11；负向演练确认拦截）。
- **tests/test_diagnostics.py 必改**：`_ALL_SECTIONS`（:24-27，12 节）与
  `test_report_contains_all_twelve_sections`（:45）改 13 节，按 lsp 节用例
  （:96-135）补 dap 节用例。
- **tests/test_user_setup.py 增补**：资源清单（:24-25）含
  `extensions/example_js_dap.py.example`。
- **tests/test_cli.py 增补**：`--diag` 报告含 `[dap]`（走查范式 :291-310）。

### 8.3 手动真实验证（安装 debugpy 的 venv）

```powershell
pip install debugpy
# 准备 t.py：import sys; for i in range(3): print("hello", i, file=sys.stderr if i == 1 else sys.stdout)
yate t.py
# F9 设断点 → F5 暂停、面板 info 显示 i、F10 单步、F11/Shift+F11、:eval i+10、
# F5 继续、Shift+F5 终止；输出面板 hello 0/1/2（1 为 stderr 样式）；
# 自然跑完 terminated + 退出码 0；故意 raise：stopped(reason=exception)
yate --diag    # 核对 dap 节
```

Node/js-debug 走查（验证扩展范例端到端）：

```powershell
npm install -g js-debug-adapter
yate --setup-defaults
Move-Item $HOME\.yate\extensions\example_js_dap.py.example $HOME\.yate\extensions\example_js_dap.py
yate app.js   # F9 → F5 暂停、info 看 i、步进、输出 hello 0/1/2、Shift+F5 终止
```

收尾门禁（主代理亲自跑，退出码 0）：

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-fail-under=75
```

---

## 9. 文档与资源

| 文件 | 内容 |
|------|------|
| `yate/docs/dap.zh.md` / `dap.en.md`（新增，双语成对硬约束） | 调试指南：架构一图、debugpy 安装、键位表、断点/求值/面板用法、`YATE_PYTHON_DAP`/`YATE_JS_DAP` 与 `debug_options`、internalConsole/startDebugging 限制、带修饰 F 键终端兼容说明、"扩展接入其他 adapter"教程（JS 范例走查 + gdb/dlv 差异表）；与 [lsp.zh.md](../../yate/docs/lsp.zh.md) 同级同风格 |
| `yate/resources/manual.zh.md` / `manual.en.md` | 新增"调试"章；**同步改写 F5=命令行既有条目**（en 191/341/359/561/585/1382；zh 182/324/341/526/545/1244） |
| `yate/yaterc.example` | language_servers 段（:112-146）后加 debug_options 注释段；内置扩展清单（:68-79）补 `python_dap` |
| `yate/extensions/example_ext.py.example` | API 面清单（:21-36）增加 `api.dap.register_debugger` 注释态小例 |
| `yate/extensions/example_js_dap.py.example`（新增） | JS/Node 完整扩展示例 |
| `README.md` / `README.zh.md` | 特性区（en :28-47 / zh :25-73）加 debugging 行；键位表 F5 行改 F7 + 补调试键（[README.md:98](../../README.md#L98)、[README.zh.md:123](../../README.zh.md#L123)）；结构树（en :215-252 / zh :230-267）补 editor_dap |
| `yate/editor_dap/__init__.py` | 包 docstring（仿 [editor_lsp/__init__.py](../../yate/editor_lsp/__init__.py)） |
| `dap-support-plan.md` + `dap-support-plans/` | 本文档与子计划 |

---

## 10. 文件变更清单（Phase 1，按子计划归口）

| 子计划 | 文件 | 操作 |
|--------|------|------|
| a | `yate/keymaps/base.py`、`yate/keyproto/legacy.py` | 修改（前置）：带修饰 F 键 parse/key_name/KEY_ALIASES/textual_key_to_raw |
| a | `tests/test_keyproto.py`、`tests/test_key_notation.py` | 修改 |
| b | `yate/keymaps/vsc.py`、`yate/keymaps/vim.py` | 修改：F7=command_prompt 迁移、vim F5 解绑 |
| b | `yate/resources/manual.en.md`、`manual.zh.md`、`README.md`、`README.zh.md` | 修改：F5→F7 六处+一处 |
| b | `tests/test_vsc_keymap.py`、`tests/test_vim_keymap.py` | 修改 |
| c | `yate/editor_dap/__init__.py`、`protocol.py`、`types.py` | 新增 |
| c | `tests/test_dap_protocol.py` | 新增 |
| d | `yate/editor_dap/client.py` | 新增 |
| d | `tests/test_dap_client.py` | 新增 |
| e | `yate/editor_dap/manager.py`（+ `__init__.py` 导出） | 新增/修改 |
| e | `tests/test_dap_manager.py` | 新增 |
| f | `yate/services/extensions.py` | 修改：DapExtensionBridge + `api.dap` property |
| f | `tests/test_dap_bridge.py` | 新增 |
| g | `yate/extensions/python_dap.py`、`example_js_dap.py.example` | 新增 |
| g | `tests/test_python_dap_ext.py`、`tests/test_dap_examples.py`、`tests/test_user_setup.py` | 新增/修改 |
| h | `yate/config.py`、`yate/yaterc.example` | 修改：`_extract_debug_options` 白名单；配置段 |
| h | `tests/test_config.py` | 修改 |
| i | `yate/editor_view/debug_panel.py` | 新增 |
| i | `yate/editor_view/editor.py`、`yate/editor_view/statusbar.py` | 修改：gutter +1/执行行；`_debug_segment` |
| i | `tests/test_dap_tui.py` | 新增 |
| j | `yate/editor.py`、`yate/dap_sync.py`、`yate/actions.py`、`yate/commands.py` | 修改/新增：ed.dap 构造与关闭、事件接线、面板挂载与互斥、8 个动作、`:debug` 系列 |
| j | `yate/keymaps/vsc.py`、`yate/keymaps/vim.py` | 修改：调试键位 + DBG 分类 |
| j | `tests/test_architecture.py`、`tests/test_dap_tui.py` | 修改：UI_FROZEN_FILES 登记；接线集成测试 |
| k | `yate/diagnostics.py` | 修改：dap 节 |
| k | `tests/test_diagnostics.py`、`tests/test_cli.py` | 修改：13 节；[dap] 断言 |
| l | `yate/docs/dap.en.md`、`dap.zh.md` | 新增（双语成对） |
| l | `yate/resources/manual.en.md`、`manual.zh.md`、`README.md`、`README.zh.md`、`yate/extensions/example_ext.py.example` | 修改：调试章 / 特性区与结构树 / API 面清单 |
| — | `pack/yate.spec`、`pack/yate-onefile.spec`、`pyproject.toml` | **不改**（整树收集自动覆盖） |

**明确不做（Phase 1）**：不动 editor_lsp 任何代码（只 import 分帧）、不改
Theme 数据结构、不做 socket/attach、不做 integratedTerminal（runInTerminal）、
不做条件断点/日志断点、不做断点持久化、不做 watch/inline hover/setVariable、
不做键位自定义配置、不新增 Protocol / TYPE_CHECKING / `*Controller` 命名。

---

## 11. 关键握手/事件时序（实现与测试的冻结基准）

```text
yate（client）                         debugpy-adapter
        │  initialize ────────────────────────▶│
        │ ◀──────────────────── response(caps) │
        │ ◀──────────── event "initialized" ──│
        │  setBreakpoints(file A, [lines]) ───▶│ ─ response
        │  setBreakpoints(file B, [lines]) ───▶│ ─ response
        │  setExceptionBreakpoints([]) ───────▶│ ─ response
        │  launch(arguments) ─────────────────▶│  (不等待响应)
        │  configurationDone ─────────────────▶│ ─ response
        │ ◀──────────── launch response ──────│（晚到，future 收口）
        │ ◀ event "process" / "output" ... ───│
        │ ◀ event "stopped"(reason,threadId) ─│
        │  threads ───────────────────────────▶│ → frames 选择
        │  stackTrace(threadId) ──────────────▶│
        │  scopes(frameId) ───────────────────▶│
        │  variables(ref) × N ────────────────▶│ → 组装快照 → 刷 UI
        │  next/stepIn/stepOut/continue ──────▶│
        │ ◀ event "continued" ────────────────│
        │ ◀ event "terminated" (+ "exited") ──│ → 会话清理，断点保留
```

---

## 12. 后续分期

**Phase 2（可用性补全）**：条件/日志断点、`debug_adapters` 声明式 yaterc 注册、
断点持久化（`.yate/debug-state.json`）、restart、多线程切换、变量分页、
setVariable、watch、hover 求值、异常断点过滤器 UI、更多 adapter 文档、
attach 配置示例、键位自定义配置、`startDebugging` reverse request（多会话）、
JS 范例提升为内置扩展的评估。

**Phase 3（深度集成）**：`console: "integratedTerminal"`（RunInTerminal，
debuggee 经 [editor_term](../../yate/editor_term) PTY 跑入集成终端）、attach
（socket，传输层抽象 stream 工厂）、远程调试、跳转栈帧开源码、repl 增强、
测试调试模板。

**重构项（独立于功能）**：分帧下沉 `yate/editor_rpc/framing.py`，消除
editor_dap 对 editor_lsp 的 import。

---

## 13. 风险与对策

| 风险 | 对策 |
|------|------|
| debugpy 版本间 launch/initialized 时序差异 | 严格不 await launch 响应；capabilities 逐项防御；手动验证当前 PyPI 版 |
| Windows 路径/反斜杠/空格 | pathFormat="path"、program 绝对路径、subprocess_exec 不经 shell；与 LSP 同套 spawn 代码 |
| adapter 泄漏进程（cwd 占用） | 复刻 `_connecting` future + stop 宽限 + terminate/kill 链路；manager shutdown 测试在 Windows 跑 |
| 1-based 坐标错位 | 转换只在 manager 边界；双向断言 |
| F5 迁移引发肌肉记忆冲突 | 手册/帮助/README 全量同步；`:debug` 与命令面板双入口；否决则回退 §5.0 备选 A |
| 部分终端不上报 Shift+F5/Shift+F11 | 键位层双向单测固化 xterm 序列；`:命令` 兜底；文档明列限制 |
| DebugPanel 与 TerminalPanel 争底部空间 | Editor 路由侧互斥；共用 `terminal_height` |
| 新流程模块破坏 R11/能力注入守卫 | `dap_sync.py` 登记 UI_FROZEN_FILES；不持 App 句柄（worker 经 Editor 注入 `spawn`）；架构测试负向演练 |
| 大 variables/输出刷屏 | 懒展开 + 环形缓冲（256KB） |
| 断点设在注释/空行 | Phase 1 信任 setBreakpoints 响应但仅 info 提示数量，不回填 gutter；Phase 2 回填 |
