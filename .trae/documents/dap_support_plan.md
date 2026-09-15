# editor_dap：DAP 调试支持与内置 Python 调试实施计划

> 新增 `yate/editor_dap` 包（零第三方依赖、纯标准库、UI 无关），
> 架构完全镜像 `editor_lsp`：DAP-over-stdio 客户端 + 会话/断点管理器；
> 内置 `extensions/python_dap.py` 扩展通过 debugpy 提供 Python 调试，
> 镜像 `extensions/python_lsp.py` 的注册/发现模式；随包附带
> `extensions/example_js_dap.py.example`，演示如何用同一套 `api.dap`
> 扩展接口接入 js-debug-adapter 调试 JavaScript/Node（改名 `.py` 即
> 激活，也是其他语言 adapter 的接入模板）；TUI 层新增断点 gutter
> 标记、调试面板、状态栏段与 F5/F9/F10/F11 键位及 `:debug` 系列命令。
>
> 本计划按三期切分，**本期实施 Phase 1（MVP）**，Phase 2/3 仅冻结方向。

> **2026-09-15 校准版**：本版依据当前代码基线全面核对。事实状态：
>
> - 仓库中**尚不存在任何 DAP 代码**（无 `editor_dap` 包、无
>   `python_dap.py`、无 debug 面板、无相关测试），Phase 1 从零开始；
> - 自旧版计划以来代码库完成了 feature 层拆分：ex 命令注册表在
>   [app_features/commands.py](yate/app_features/commands.py)，
>   终端生命周期在
>   [app_features/terminal.py](yate/app_features/terminal.py)，
>   另有与键位解耦的动作表
>   [actions.py](yate/actions.py)；旧计划中的
>   `editor_view/commands.py` **不存在**；
> - 旧计划引用的行号均已漂移，本版全部按当前行号重锚；
> - 新发现两个**前置改造项**（旧计划未覆盖）：键位层不支持带修饰的
>   F 键（Shift+F5 等），且 **F5 当前是 vsc 模式打开 ex 命令行的专用键**，
>   必须先做决策与改造，见 §5.0；
> - 打包侧无需改动：wheel 由 hatchling `packages = ["yate"]`
>   （[pyproject.toml:58-63](pyproject.toml#L58-L63)，
>   包内非 `.py` 资源自动随包；sdist `include` 见 L65-66；hatchling
>   没有 force-include 配置，那是 PyInstaller 术语），
>   PyInstaller 两个 spec 均以 `Tree(pkg_path("extensions"))` 与
>   `docs` 目录整树收集（[yate.spec:76-83](pack/yate.spec#L76-L83)、
>   [yate-onefile.spec:84-91](pack/yate-onefile.spec#L84-L91)），
>   新增的 `.py.example` 与 `docs/dap.*.md` 自动入包。
> - 二次复核修正：LSP 并**无 `spawn()` 方法**（进程拉起在
>   `LspClient._connect()` L247-285，握手指 `start()` L192-245）；
>   welcome 页 hints **不含 F5 文案**（F5 迁移不含该项）；手册
>   en/zh 两版 F5 行号不同（zh：172/314/331/499/518/1213）；
>   补录现状已存在的 `editor_term` PTY/VT 包（Phase 1 不碰，Phase 3
>   RunInTerminal 复用）；manager 对 Document 是运行时硬 import
>   （非 TYPE_CHECKING）。

---

## 1. 现状与可复用资产（基于代码事实，2026-09-15 核对）

| 资产 | 位置 | DAP 复用方式 |
|------|------|--------------|
| Content-Length 分帧（协议无关） | [protocol.py:28](yate/editor_lsp/protocol.py#L28) `MAX_MESSAGE_BYTES`、[L35-38](yate/editor_lsp/protocol.py#L35-L38) `encode_message`、[L69-87](yate/editor_lsp/protocol.py#L69-L87) `parse_headers`、[L90-98](yate/editor_lsp/protocol.py#L90-L98) `decode_body`、[L101-120](yate/editor_lsp/protocol.py#L101-L120) `read_message` | DAP 与 LSP 的 stdio 分帧完全相同，**直接 import 复用**（见 §3.1 决策） |
| 单进程 JSON-RPC 客户端范式 | [client.py](yate/editor_lsp/client.py) `LspClient`：构造于 [L157-188](yate/editor_lsp/client.py#L157-L188)（`connect=` 注入、`init_timeout`）、`_connecting` future [L186-188](yate/editor_lsp/client.py#L186-L188)、`start()` 握手 [L192-245](yate/editor_lsp/client.py#L192-L245)、`_connect()` 进程拉起块 [L247-285](yate/editor_lsp/client.py#L247-L285)（**没有名为 spawn 的方法**，subprocess 在 `_connect()` 内）、stop/`_cleanup` [L287-352](yate/editor_lsp/client.py#L287-L352)（`_cleanup` 始于 L314） | `DapClient` 照此结构重写，构造签名同样取 `(config, root_path, *, on_event, connect, init_timeout)`；消息模型改为 seq/request_seq |
| 配置/状态数据类的摆放 | LSP 把 `ServerConfig`、`ServerState` 放在 [client.py:47-96](yate/editor_lsp/client.py#L47-L96)（**没有独立 types 模块**）；`ServerState` 成员为 CONFIGURED/STARTING/READY/FAILED/STOPPED | DAP 状态机不同（需 RUNNING/PAUSED/TERMINATED），**不共用枚举**；DAP 独立建 `types.py`（§3.2） |
| 多配置管理器 + 事件回调 | [manager.py:60](yate/editor_lsp/manager.py#L60) `LspManager`，`__init__(workspace_root=, on_event=, client_factory=)` [L63-87](yate/editor_lsp/manager.py#L63-L87)；注册/替换 [L91-115](yate/editor_lsp/manager.py#L91-L115)；状态聚合 [L134-149](yate/editor_lsp/manager.py#L134-L149)；`error_for` [L156-160](yate/editor_lsp/manager.py#L156-L160)；root 解析 `root_for` [L172-185](yate/editor_lsp/manager.py#L172-L185)；`_make_client` 工厂 [L187-193](yate/editor_lsp/manager.py#L187-L193) | `DapManager`：注册表 + 单会话 + 断点存储 + 事件回调；`on_event` 签名与 LSP 一致（单参 kind 字符串），UI 从 manager 拉快照 |
| 扩展注册桥 | [extensions.py:52-96](yate/services/extensions.py#L52-L96) `LspExtensionBridge`（`api.lsp.register_server`，`name` 位置参其余 keyword-only）；`ExtensionAPI` [L190-234](yate/services/extensions.py#L190-L234)、`lsp` property [L221-224](yate/services/extensions.py#L221-L224)；加载器 [L312-384](yate/services/extensions.py#L312-L384) | 新增姊妹 `DapExtensionBridge`（`api.dap.register_debugger`），同文件同风格 |
| 内置扩展注册与发现 | [python_lsp.py](yate/extensions/python_lsp.py)：env 覆盖/opt-out [L66-85](yate/extensions/python_lsp.py#L66-L85)、解释器相邻 launcher 探测 [L39-52](yate/extensions/python_lsp.py#L39-L52)、无参 `setup(api)` [L88-106](yate/extensions/python_lsp.py#L88-L106) | `python_dap.py`：`YATE_PYTHON_DAP` → `debugpy-adapter` → 解释器相邻 launcher → `sys.executable -m debugpy.adapter` |
| 声明式配置 | [config.py:48-51](yate/config.py#L48-L51) `_KNOWN_OPTIONS`、`LanguageServerSpec` [L56-73](yate/config.py#L56-L73)、`language_servers` 校验 `_extract_language_servers` [L374-469](yate/config.py#L374-L469) | Phase 2 再做 `debug_adapters` 声明式注册；Phase 1 只加普通 dict 选项 `debug_options` |
| gutter 渲染 | [editor.py:269-271](yate/editor_view/editor.py#L269-L271) `gutter_width()`（现为 `max(3, digits) + 3`）；行号列+诊断标记拼于 [L441-463](yate/editor_view/editor.py#L441-L463)（✖/▲）；当前行底色 `t.surface` [L438-439](yate/editor_view/editor.py#L438-L439) | 公式 +1（断点/执行行一列 ●/▶）；诊断列逻辑不动 |
| gutter 宽度的下游消费 | [app_features/completion.py:135](yate/app_features/completion.py#L135) 与 [L184](yate/app_features/completion.py#L184) 用 `editor.gutter_width()` 定位补全弹层 | 宽度 +1 自动传播，无需改 completion |
| 事件回调刷 UI | [app.py:1316-1325](yate/app.py#L1316-L1325) `_on_lsp_event`（遍历 `panes.all_views()` refresh + 状态栏 refresh）；worker 范式见 [L1310-1313](yate/app.py#L1310-L1313)（`group="lsp-sync", exclusive=False, exit_on_error=False`） | `_on_dap_event` 紧随其后：刷 gutter、面板、状态栏；动作用 `run_worker(group="dap", exit_on_error=False)` |
| App 持有与关闭 | [app.py:199-202](yate/app.py#L199-L202) `self.lsp = LspManager(...)`；teardown 中 [app.py:1747-1750](yate/app.py#L1747-L1750) `await self.lsp.shutdown_all()`；启动加载 [app.py:1754-1761](yate/app.py#L1754-L1761)、rc 声明注册 [L1815-1836](yate/app.py#L1815-L1836) | `self.dap` 同构；退出时并列 `await self.dap.shutdown_all()`；DAP 无 rc 声明注册（Phase 1 仅扩展） |
| 动作表（键位解耦） | [actions.py:25-55](yate/actions.py#L25-L55) `ActionRegistry`；内置动作 `populate` [L58-168](yate/actions.py#L58-L168)（如 `command_prompt` [L156](yate/actions.py#L156)） | 新增 `debug_start_or_continue`（单动作按会话状态分发，见 §5.5）、`toggle_breakpoint/step_over/step_into/step_out/pause_debug/debug_stop/debug_panel` 动作；键位只引用动作名 |
| ex 命令注册表 | [app_features/commands.py:25-42](yate/app_features/commands.py#L25-L42) `CommandRegistry`；内置命令 `register_commands` [L45-197](yate/app_features/commands.py#L45-L197)（`:term` 等 [L190-196](yate/app_features/commands.py#L190-L196)）；App 构造于 [app.py:181-182](yate/app.py#L181-L182) | `:debug` 系列在此注册；**不是** `editor_view/commands.py`（不存在） |
| feature 生命周期模块范式 | [app_features/terminal.py](yate/app_features/terminal.py)：`toggle/open/close/spawn` 均为接收 app 的模块级函数，面板 widget 与状态标志留在 app | 新增 `app_features/debug.py` 同构：面板开关、launch/步进动作的 worker 编排、与终端面板互斥 |
| 底部面板范式（widget） | [editor_view/terminal.py](yate/editor_view/terminal.py)：`TerminalPanel(Vertical)`（[L326](yate/editor_view/terminal.py#L326)）包 `TerminalView(Widget, can_focus=True)`（[L56](yate/editor_view/terminal.py#L56)），`TOGGLE_KEYS` [L45-47](yate/editor_view/terminal.py#L45-L47)；挂载于 [app.py:1695-1699](yate/app.py#L1695-L1699) `#bottom-dock`（注释在 L1693-1694），初始 `display=False` [L1710-1712](yate/app.py#L1710-L1712) | `DebugPanel(Vertical)` 同构挂同一 dock、terminal 之上；同一时刻只显一个；高度复用 `terminal_height` |
| 集成终端后端（PTY/VT，新包） | [`yate/editor_term/`](yate/editor_term)：`emulator.py`（VT 仿真，内含自己的 `_MOD_ARROWS` [L108](yate/editor_term/emulator.py#L108)）、`pty_proc.py`（跨平台 PTY/`PtyProcessError`）、`shells.py`（`resolve_shell`）；`TerminalView` 经 [terminal.py:23](yate/editor_view/terminal.py#L23) import 使用，feature 层在 [terminal.py:68](yate/app_features/terminal.py#L68) 解析 shell | **Phase 1 不碰**（internalConsole 经 DAP output event 回传）；Phase 3 的 `console: "integratedTerminal"`/RunInTerminal 让 debuggee 经该 PTY 后端跑入面板（§12） |
| 状态栏分段 | [statusbar.py:40-95](yate/editor_view/statusbar.py#L40-L95) `refresh_status`；`_lsp_segment` [L97-122](yate/editor_view/statusbar.py#L97-L122)（state→文案/样式，READY 附 ✖/▲ 计数） | 仿加 `_debug_segment()`，插入右侧拼装链 [L57-60](yate/editor_view/statusbar.py#L57-L60) |
| 键位层（原始字节） | [keymaps/base.py:22-52](yate/keymaps/base.py#L22-L52) `SPECIAL_KEYS`、[L80-117](yate/keymaps/base.py#L80-L117) `parse_key`、[L120-150](yate/keymaps/base.py#L120-L150) `key_name`、[L204-215](yate/keymaps/base.py#L204-L215) `add_binding`；Textual 键名→原始字节 [editor_view/keys.py:49-86](yate/editor_view/keys.py#L49-L86) `textual_key_to_raw`（修饰表 `_MOD_ARROWS` L18-23/`_MOD_SPECIAL` L25-29 在同文件顶部） | **需先扩展**：`<shift-f5>` 等带修饰 F 键当前解析为裸 F5（[base.py:96-98](yate/keymaps/base.py#L96-L98) 只处理单字符 shift），详见 §5.0 |
| 诊断报告 | [diagnostics.py:86-99](yate/diagnostics.py#L86-L99) 节注册表；lsp 节 [L391-414](yate/diagnostics.py#L391-L414)；config 节 [L288-302](yate/diagnostics.py#L288-L302)；`--diag` 入口 [cli.py:256-268](yate/cli.py#L256-L268) | 在 lsp 之后插入 `dap` 节；注意测试里有硬编码 12 节清单（见 §8.2） |
| 模板分发 | [services/user_setup.py:102-106](yate/services/user_setup.py#L102-L106) 对内置扩展目录通配拷贝 `*.py.example` | `example_js_dap.py.example` 零改动自动随 `--setup-defaults` 分发 |

---

## 2. DAP 与 LSP 的协议差异（设计依据）

DAP（Debug Adapter Protocol）与 LSP **不是同一套消息模型**，不能共用
client，只能共用分帧：

| 维度 | LSP（JSON-RPC 2.0） | DAP |
|------|--------------------|-----|
| 分帧 | `Content-Length: N\r\n\r\n` + JSON | **相同** |
| 请求 | `{jsonrpc, id, method, params}` | `{seq, type:"request", command, arguments}` |
| 响应 | `{jsonrpc, id, result/error}` | `{seq, type:"response", request_seq, command, success, body, message}` |
| 服务端推送 | `method` 的 notification | `{seq, type:"event", event, body}` |
| 反向请求 | server request（少见） | `runInTerminal` 等 reverse request（Phase 1 声明不支持） |
| 握手 | `initialize` → `initialized` 通知 | `initialize` → 响应含 capabilities → 收到 server **`initialized` event** 后：`setBreakpoints`/`setExceptionBreakpoints` → `launch` → `configurationDone` |
| 坐标 | 0-based 行/列 | **1-based 行、1-based 列**（manager 层转换，UI 永远收 0-based） |
| 进程模型 | 一个 server × project root 一个进程 | 一个**调试会话**一个 adapter；MVP 全局单会话 |

debugpy 接入方式（与 pylsp 一样走 stdio）：

- `pip install debugpy` 后提供 `debugpy-adapter` 可执行（等价
  `python -m debugpy.adapter`）：stdio 说 DAP，由 adapter 自己 spawn
  debuggee，debuggee 的 stdout/stderr 经 DAP `output` event 回传
  （`console: "internalConsole"` + `redirectOutput: true`）。
- 不需要 socket/attach 端口协商，不引入 `runInTerminal`，与 LSP 的
  subprocess 工厂几乎一致（`stderr=DEVNULL`，cwd=workspace root）。

---

## 3. `editor_dap` 包设计（UI 无关、纯标准库）

```text
yate/editor_dap/
  __init__.py     # 公共导出（仿 editor_lsp/__init__.py 的包 docstring 与 __all__）
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

> 备选（不推荐本期做）：把分帧下沉为中立模块 `yate/editor_rpc/framing.py`
> 再让两边 import。收益是命名干净，代价是改动已稳定的 LSP 模块与其测试；
> 列入 §12 重构项。

DAP 消息层：

```python
JSON_MESSAGES = ("request", "response", "event")

def build_request(seq: int, command: str, arguments: dict | None = None) -> dict
def build_response_body(message: dict) -> tuple[int, bool, str, object]
    # 从 response 取 (request_seq, success, message, body)
def is_event(message: dict, name: str | None = None) -> bool
def event_body(message: dict) -> dict
```

`DapError(RuntimeError)` 为本包错误基类（对照 LSP 的 `LspError`
[client.py:55](yate/editor_lsp/client.py#L55)）；
§3.3 的 `DapResponseError`/`DapConnectionError` 均继承它（对照
`LspResponseError` [L59](yate/editor_lsp/client.py#L59)）。

### 3.2 types.py

```python
@dataclass(frozen=True)
class DebuggerConfig:            # 镜像 lsp ServerConfig（client.py:73-96）的形状
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
    name: str                   # 函数名 / "<module>"
    path: Path | None
    row: int                    # 0-based（协议行-1）；无源码时为 -1
    column: int                 # 0-based
    source_present: bool

@dataclass(frozen=True)
class Variable:
    name: str
    value: str
    type_name: str
    variables_reference: int    # >0 可展开；children_count 供 UI 标记
    indexed_variables: int
    named_variables: int

@dataclass(frozen=True)
class Scope:
    name: str                   # "Locals" / "Globals"
    variables_reference: int
    expensive: bool

@dataclass(frozen=True)
class StoppedSnapshot:
    reason: str                 # breakpoint | step | exception | pause | entry
    thread_id: int
    thread_name: str
    frames: list[StackFrame]
    active_frame: StackFrame | None
    scopes: list[Scope]         # active frame 的 scopes
    variables: dict[int, list[Variable]]  # variables_reference → 已拉取列表
```

会话状态枚举（**不与 LSP 共用**——LSP 的 `ServerState`
[client.py:47-52](yate/editor_lsp/client.py#L47-L52)
只有 CONFIGURED/STARTING/READY/FAILED/STOPPED，表达不了运行/暂停）：

```python
class SessionState(str, enum.Enum):
    CONFIGURED = "configured"   # 已注册、无会话
    STARTING = "starting"       # initialize → configurationDone 期间
    RUNNING = "running"         # debuggee 在跑
    PAUSED = "paused"           # stopped event 后
    TERMINATED = "terminated"   # debuggee 退出（会话残留可重启 launch）
    FAILED = "failed"           # 启动失败 / adapter EOF
```

（adapter 连上但 debuggee 未 launch 的 READY 窗口并入 STARTING，不单列。）

manager → app 的事件回调签名与 LSP 完全一致：`on_event(kind: str)`，
kind 取值 `stopped | continued | output | terminated | initialized | failed`。
UI 收到回调后从 manager 读 `snapshot()`/`output_text()`/`session_state()`，
避免再设计一套事件负载类型（若内部需要附带文本，仅作 manager 私有记录）。

### 3.3 client.py — DapClient

结构对照 `LspClient`（同名私有件：`_next_seq`、`_pending: dict[int, Future]`、
`_read_task`、`_bg_tasks`、`_write_lock`、`connect=` 传输注入、
`init_timeout`、`_connecting` future）。构造签名刻意对齐 LSP 以便
`client_factory` 形态一致（对照
[manager.py:187-193](yate/editor_lsp/manager.py#L187-L193)）：

```python
class DapResponseError(DapError):  # success=False：command + message + body
class DapConnectionError(DapError):

class DapClient:
    def __init__(self, config: DebuggerConfig, root_path: Path, *,
                 on_event=None, connect=None,
                 init_timeout: float = 20.0) -> None: ...

    async def start(self) -> dict:
        """拉起 adapter（_connect）+ initialize 握手；返回 capabilities。"""
        # initialize arguments（冻结，不允许扩展覆盖公共参数）:
        # {
        #   "adapterID": "yate", "clientID": "yate",
        #   "clientName": "yate", "locale": "en",
        #   "linesStartAt1": True, "columnsStartAt1": True,
        #   "pathFormat": "path",
        #   "supportsRunInTerminalRequest": False,
        #   "supportsVariableType": True,
        #   "supportsVariablePaging": False,
        #   "supportsConditionalBreakpoints": False,   # Phase 2 改 True
        # }

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
    async def restart(self) -> None: ...              # Phase 2
    async def terminate(self) -> None: ...           # 礼貌终止 debuggee
    async def disconnect(self, *, terminate_debuggee: bool = True) -> None: ...
    async def stop(self) -> None: ...                # 兜底 terminate/kill（镜像 LSP teardown）
```

dispatch 规则（`_dispatch`）：

- `type=="response"`：以 `request_seq` 取 future；`success=false` 用
  `DapResponseError` 完成；
- `type=="event"`：转发 `on_event(event_name, body)`；client 自身只捕获
  `initialized`（置 future）、`exited`/`terminated`（记录退出码供报告）；
- `type=="request"`（reverse request）：Phase 1 统一回
  `success=false, message="unsupported by yate"`（capabilities 已声明
  不支持 runInTerminal，正常 adapter 不会发）。

`launch()` 的特殊点：debugpy 对 `launch` 请求的响应在 debuggee 启动后
才返回，不能等它再 configurationDone——**DAP 标准序列是 launch 发出后
直接发 configurationDone，不等 launch 响应**（响应后续自然回来）。
实现上 launch 用 `start_request`（拿 future 但不 await），随后 await
configurationDone。测试必须固化此顺序。

进程拉起/teardown 直接复刻 LSP 的经验件：`_connect()`
[client.py:247-285](yate/editor_lsp/client.py#L247-L285)
内 `create_subprocess_exec`（`stderr=DEVNULL`、cwd=root，L255-263）+
在途停止分支（L265-284）；`stop()`/`_cleanup`
[L287-352](yate/editor_lsp/client.py#L287-L352)
借 `_connecting` future 等在途 `_connect()` 收尾，Windows cwd
占用/子进程残留由同一链路兜底（测试固化于
[test_lsp.py:387](tests/test_lsp.py#L387)）。

### 3.4 manager.py — DapManager

```python
class DapManager:
    def __init__(self, *, workspace_root=None, on_event=None,
                 client_factory=None) -> None:
        # client_factory: Callable[[DebuggerConfig, Path], DapClient] | None
        ...

    # ---- 注册（扩展/yaterc），镜像 LspManager
    def register_debugger(self, config: DebuggerConfig) -> None: ...  # 同名替换，同 L91-115 语义
    def configs(self) -> list[DebuggerConfig]: ...
    def config_for(self, filetype: str) -> DebuggerConfig | None: ...
    def states(self) -> dict[str, SessionState]: ...   # 注册表视角（diag 用；未启动=CONFIGURED）
    def error_for(self, name: str) -> str: ...

    # ---- 断点（UI 无关；dict[path, set[row]]，0-based）
    def toggle_breakpoint(self, path: Path, row: int) -> bool: ...  # 返回新状态
    def breakpoints_for(self, path: Path) -> list[int]: ...
    def has_breakpoint(self, path: Path, row: int) -> bool: ...
    def clear_breakpoints(self, path: Path | None = None) -> None: ...

    # ---- 会话（MVP 单会话；内部保留 sessions 字典的演进位置）
    async def launch(self, doc_or_path, *, program_args=None) -> bool: ...
    async def resume(self) -> None: ...          # continue
    async def step_over(self) -> None: ...
    async def step_into(self) -> None: ...
    async def step_out(self) -> None: ...
    async def pause(self) -> None: ...
    async def stop_session(self) -> None: ...
    async def evaluate(self, expression: str) -> str: ...
    async def expand_variable(self, variables_reference: int) -> list[Variable]: ...

    def snapshot(self) -> StoppedSnapshot | None: ...
    def session_state(self) -> SessionState: ...
    def output_text(self) -> str: ...            # 面板输出缓冲（环形上限 N KB）
    def active_location(self) -> tuple[Path, int] | None: ...  # 执行行（0-based）

    async def shutdown_all(self) -> None: ...
    def set_debug_options(self, options: dict) -> None: ...     # yaterc debug_options
```

关键行为：

1. **root/program 解析**：复刻 LSP `root_for` 的三层逻辑
   （[manager.py:172-185](yate/editor_lsp/manager.py#L172-L185)：
   `workspace_root` 回调且文件在其下 → workspace root；否则沿
   root_markers 向上找；再否则文件父目录）；`program` 必须是绝对路径；
   仅支持**已保存且无未保存改动**的文件，否则返回 False 并回调
   `failed`，UI 提示先保存。
2. **launch 参数合成**：`{**config.launch, "program": ..., "args": ...,
   "cwd": str(root), **self._debug_options}`；debug_options 只合并
   **跨 adapter 通用键**（Phase 1：env/stopOnEntry/args），未知键收集为
   错误不盲传；adapter 专有键（justMyCode、outputCapture 等）由扩展的
   `launch` 模板提供（见 §4.3 的分层理由）。模板误写 program/cwd 与注入
   键冲突时，以注入值为准并在诊断中记录。
3. **启动序列**（事件循环内串行）：
   `client.start()` → 等 `initialized` event → 对**所有已存断点文件**
   逐个 `set_breakpoints` → `set_exception_breakpoints([])` →
   `launch(args)`（不 await 响应）→ `configurationDone()`；
   任一步失败：状态 FAILED、回调 failed（含原因）、teardown。
4. **stopped 事件处理**：拉 threads（取事件 threadId 的名字，失败给
   "Thread N"）→ stackTrace（上限 50 帧）→ 对第 0 帧拉 scopes →
   对非 expensive 的 scopes 拉 variables（expensive 展开时按需拉，
   `expand_variable`）→ 组装 `StoppedSnapshot` 存 `self._snapshot` →
   `on_event("stopped")`。拉取失败单项降级（如 variables 失败保留
   frames），绝不让事件处理抛异常。
5. **continued/output/terminated**：continued 清 snapshot、回调
   "continued"；output 追加环形缓冲（区分 stdout/stderr/console 的
   `category`，`\r`/`\n` 归一），回调 "output"；terminated/exited：
   回调 "terminated"（含退出码）、状态 TERMINATED、保留输出缓冲直到
   下次 launch、client 入清理但断点**保留**（VS Code 同此行为）。
6. **单会话约束**：RUNNING/PAUSED/STARTING 时再 launch 返回 False 并
   回调 failed（"debug session already active; use :debug-stop"）。
7. **坐标转换**：仅 client↔manager 边界做 1-based↔0-based；
   `StackFrame.row` 无源码（`source is None`）时为 -1。
8. **纯异步、无 Textual import**：manager 只 import asyncio/dataclasses/
   pathlib/typing + 本包 + `editor_core.document.Document`（**运行时直接
   import，不是 TYPE_CHECKING**——
   [manager.py:23](yate/editor_lsp/manager.py#L23)
   即如此；`editor_core` 是 UI 无关核心层，不牵出 textual，DAP 同一边界）。

---

## 4. 扩展层：`api.dap` 与内置 `python_dap.py`

### 4.1 DapExtensionBridge（services/extensions.py）

与 [LspExtensionBridge](yate/services/extensions.py#L52-L96)
对称（`name` 位置参、其余 keyword-only、空 command 懒失败的文档约定一致）；
`ExtensionAPI` 增加 `dap` property（紧邻
[lsp property L221-224](yate/services/extensions.py#L221-L224)）：

```python
class DapExtensionBridge:
    """``api.dap`` -- register debug adapters from an extension."""
    def register_debugger(self, name: str, *, command: str, args=None,
                          filetypes=None, env=None,
                          launch: dict | None = None,
                          root_markers=None) -> None: ...
    def statuses(self) -> dict[str, str]: ...
    def has_state(self, name: str, state: str) -> bool: ...   # 对齐 LSP 桥 L94-96
```

参数校验/默认值在桥内完成（`root_markers=None` 给 DAP 默认 marker 元组，
与 LSP 桥 [L86-87](yate/services/extensions.py#L86-L87)
同构），构造 `DebuggerConfig` 交给 `self._app.dap.register_debugger(...)`。

### 4.2 extensions/python_dap.py（内置，可禁用）

镜像 [python_lsp.py](yate/extensions/python_lsp.py)
的文档串与发现逻辑，**五级发现（含全空兜底）**（比旧计划多一级解释器相邻 launcher，
复刻 LSP 的 `_venv_langserver`
[python_lsp.py:39-52](yate/extensions/python_lsp.py#L39-L52)，
覆盖 venv 的 Scripts 不在 PATH 的情况）：

```python
# 禁用：disabled_extensions = ["python_dap"]
# 覆盖：set YATE_PYTHON_DAP=C:\venv\Scripts\debugpy-adapter.exe
# opt-out：YATE_PYTHON_DAP=0 只注册不 spawn（懒失败）

def discover_command() -> tuple[str, list[str]]:
    # 1) YATE_PYTHON_DAP（shlex.split(posix=True)；0/off/false/none/no 为 opt-out）
    # 2) shutil.which("debugpy-adapter")
    # 3) 解释器相邻 launcher：sys.executable 目录下的
    #    debugpy-adapter.exe / .cmd / .bat / 无后缀（venv\Scripts 不在 PATH 时）
    # 4) importlib.util.find_spec("debugpy") 存在 →
    #    (sys.executable, ["-m", "debugpy.adapter"])
    # 5) ("", [])

def setup(api):
    command, args = discover_command()
    api.dap.register_debugger(
        name="python", command=command, args=args,
        filetypes=["py"],
        root_markers=["pyproject.toml", "setup.py", "setup.cfg",
                      "requirements.txt", "Pipfile", ".git"],
        launch={
            "type": "python", "request": "launch",
            "console": "internalConsole", "redirectOutput": True,
            "justMyCode": False, "subProcess": True, "stopOnEntry": False,
        },
    )
```

launch 时的 `program/args/cwd/env/pythonPath` 由 manager 注入；
`justMyCode=False` 在 Phase 1 写死为模板默认（调试第三方/标准库更直观），
该键属 debugpy 专有，**不**开放 yaterc 覆盖（理由与后续通道见 §4.3 末注）。

扩展加载时序：现有 `load_startup_services`
（[app.py:1754-1761](yate/app.py#L1754-L1761)）
只有 `_load_extensions()` + `_register_configured_servers()` 两步；
DAP 注册在同一遍 setup(api) 中自然生效，Phase 1 无需第三步。

### 4.3 yaterc：`debug_options`

config.py 增加一个普通 dict 选项（不走 LanguageServerSpec 那套复杂校验）：

```python
# Phase 1 白名单仅三个跨 adapter 通用键：env / stopOnEntry / args
debug_options = {"stopOnEntry": False}
debug_options = {"env": {"FLASK_DEBUG": "1"}}   # 合并进 debuggee 环境
# console 固定 internalConsole；console 键 Phase 3 随 integratedTerminal 一起放开
```

`_KNOWN_OPTIONS`（[config.py:48-51](yate/config.py#L48-L51)）
增加 `"debug_options"`；值必须为 dict，键在**跨 adapter 通用白名单**
（Phase 1：`env`/`stopOnEntry`/`args`；`console` 待 Phase 3）内，否则按现有 config 错误收集
风格记入 `config.errors`（启动消息行 + yaterc 节 load errors +
`--diag` 可见）并忽略该键。adapter 专有键（debugpy 的 `justMyCode`/
`subProcess`、js-debug 的 `outputCapture`/`sourceMaps`/`skipFiles`）
**不进** yaterc 白名单，只在扩展的 `launch` 模板里给出——保证换
adapter 时 yaterc 选项不会把未知键盲传出去。

> 实施备注：上文示例中的 `justMyCode` 若要允许用户经 yaterc 覆盖，
> 走 debugpy 扩展自己读取的专用环境变量/文档化做法，**不**通过放宽通用
> 白名单实现；Phase 1 直接不提供该覆盖（模板值 justMyCode=False 定稿），
> 需求真实出现再在 Phase 2 设计 adapter 专有选项通道。声明式
> `debug_adapters` 列入 Phase 2。

### 4.4 扩展示例：`extensions/example_js_dap.py.example`（新增）

随包提供 JavaScript/Node 调试扩展示例，演示"任何 stdio DAP adapter 都
能用 `api.dap` 接入"。与 `example_ext.py.example` 同级、同后缀约定
（`.py.example` 不自动加载；`--setup-defaults` 通过
[user_setup.py:102-106](yate/services/user_setup.py#L102-L106)
的 `*.py.example` 通配一并拷到 `~/.yate/extensions/`，用户改名为
`.py` 即激活）。

适配器：[microsoft/vscode-js-debug](https://github.com/microsoft/vscode-js-debug)
的独立 npm 包，命令名 `js-debug-adapter`（stdio DAP），安装
`npm install -g js-debug-adapter`。示例文件完整内容：

```python
# Example yate extension: debug JavaScript / Node.js programs via DAP.
#
# Install:
#   1) npm install -g js-debug-adapter
#      (the standalone stdio build of microsoft/vscode-js-debug)
#   2) copy this file to ~/.yate/extensions/example_js_dap.py
#      (drop the .example suffix; or run: yate --setup-defaults, then rename)
#   3) open a .js file and press F5.
#
# Override the adapter with YATE_JS_DAP, e.g.
#   set YATE_JS_DAP=C:\node\js-debug-adapter.cmd
# Set YATE_JS_DAP=0 to register but never spawn (lazy failure on F5).
#
# Phase-1 limitations (see yate/docs/dap.en.md):
#   * internalConsole only — debuggee stdout/stderr appear in the debug panel;
#   * js-debug sends a "startDebugging" reverse request to auto-attach child
#     processes; yate answers "unsupported" in Phase 1, so only the root
#     process is debugged (subProcess-style nesting arrives in Phase 2).

from __future__ import annotations

import os
import shlex
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yate.services.extensions import ExtensionAPI


def discover_command() -> tuple[str, list[str]]:
    """(executable, args) for the standalone js-debug DAP adapter."""
    override = os.environ.get("YATE_JS_DAP", "").strip()
    if override.lower() in {"0", "off", "false", "none", "no"}:
        return "", []
    if override:
        parts = shlex.split(override, posix=True)
        if parts:
            return parts[0], parts[1:]
    found = shutil.which("js-debug-adapter")
    return (found, []) if found else ("", [])


def setup(api: "ExtensionAPI") -> None:
    command, args = discover_command()
    api.dap.register_debugger(
        name="node",
        command=command,
        args=args,
        filetypes=["js", "mjs", "cjs", "jsx"],
        # TypeScript ("ts", "tsx") works too when the program is runnable,
        # e.g. NODE_OPTIONS with a loader / tsx; add the filetypes as needed.
        root_markers=["package.json", "jsconfig.json", ".git"],
        # Adapter-specific launch keys live here (never in yaterc):
        launch={
            "type": "pwa-node",      # js-debug session type (also "node")
            "request": "launch",
            "console": "internalConsole",
            "outputCapture": "std", # route console.log/process.stdout to DAP output
            "sourceMaps": True,
            "cascadeTerminateToParents": True,
            "skipFiles": ["<node_internals>/**"],
            # "program", "args", "cwd" are injected by DapManager at launch.
        },
    )
```

要点说明（写入 dap 文档，示例头注释保持简短）：

- `initialize` 的 `adapterID` 由 yate 固定发 `"yate"`，adapter 的选择
  以 `launch["type"]`（`pwa-node`）为准——这是多 adapter 共存的关键，
  §3.3 client 不允许扩展覆盖 initialize 公共参数；
- 与 python_dap 的差异只有三处：发现命令、filetypes/root_markers、
  adapter 专有 launch 模板；会话/断点/步进/变量链路完全复用；
- Windows 上全局 npm 安装常产出 `js-debug-adapter.CMD`，
  `shutil.which` 与 `asyncio.create_subprocess_exec` 按现有 LSP spawn
  路径处理（与 pyright-langserver.cmd 同一已验证链路）；
- 未安装适配器时懒失败：注册照常，F5 才报
  `js-debug-adapter not found — npm install -g js-debug-adapter`。

### 4.5 同一模式可接的其他 stdio adapter（文档列表示例，不内置）

| 语言 | adapter 命令 | launch type/备注 |
|------|--------------|------------------|
| JS/TS/Node | `js-debug-adapter` | `pwa-node`（本计划随示例） |
| C/C++/Rust | `gdb -i dap` / `lldb-dap` / `codelldb` | args 不是可执行文件路径时用 `args=["-i","dap"]`，bridge 参数已支持 |
| Go | `dlv dap` | `mode: debug` 等专有键走 launch 模板 |
| Ruby | `rdbg --open --command --` | |
| Bash | `bash-debug`（`@vscode/bash-debug` 的 adapter） | 需要 pathBash 等 launch 键 |

dap 文档以 JS 示例为完整走查，其余以"发现命令 + launch 模板差异点"
表格呈现。

---

## 5. TUI 集成（editor_view / app_features / app）

### 5.0 前置改造：键位层与 F5 冲突（旧计划遗漏，必须先做）

**事实 1：F5 已被占用。** vsc 键位中 F5 是 ex 命令行入口
（[vsc.py:88-91](yate/keymaps/vsc.py#L88-L91)，
动作为 `command_prompt`，注册于
[actions.py:156](yate/actions.py#L156)）。
vsc 模式下 `:` 是**普通输入字符**（冒号要直接写进代码，刻意未绑定；
见 [editor.py:539-542](yate/editor_view/editor.py#L539-L542)
欢迎页注释）；ex 命令行仅 vim 模式由 `:` 触发
（[vim.py:200](yate/keymaps/vim.py#L200)、
[L381](yate/keymaps/vim.py#L381)）。
手册中 F5=命令行的说明 en/zh 各 6 处（**两版行号不同**）：
[manual.en.md](yate/resources/manual.en.md)
L181/L329/L347/L530/L554/L1346；
[manual.zh.md](yate/resources/manual.zh.md)
L172/L314/L331/L499/L518/L1213。
其余 F 键占用：F1 help、F2 shell、F3 find next、F4 replace、F8 manual；
**F6/F7/F9/F10/F11/F12 空闲**。

**事实 2：带修饰的 F 键当前无法解析。** [parse_key](yate/keymaps/base.py#L80-L117)
对 `<shift-f5>` 会退化为裸 F5 序列（shift 分支只大写单字符，
[base.py:96-98](yate/keymaps/base.py#L96-L98)）；
[textual_key_to_raw](yate/editor_view/keys.py#L49-L86)
的修饰表只覆盖方向键/home/end/tab，没有 F 键。Shift+F5/Shift+F11
无可用键位。

**决策（推荐落地方案，评审可推翻）**：

1. **F5 按 VS Code 惯例让给调试**（无会话=launch、PAUSED=continue、
   RUNNING=noop 给消息提示）；ex 命令行在 vsc 模式迁至 **F7**（当前
   空闲；`:set keymap` 式自定义留给后续键位可配置化，Phase 2）。
   `:` 维持普通输入字符不变。同步更新 vsc.py 注释（L88-90）与绑定
   （L91）、手册中英文
   各 6 处引用（行号见事实 1）、README 键位表（[README.md:89](README.md#L89)、
   [README.zh.md:109](README.zh.md#L109) 与 [L412](README.zh.md#L412)）；
   F1 帮助覆盖层由键位表自动生成（manual.en.md L260-261 说明），新增
   DBG 分类后自动出现，无需单独改。**welcome 页 hints 不含 F5**
   （[editor.py:535-548](yate/editor_view/editor.py#L535-L548)
   只有 Ctrl+P / Alt+Shift+P / Ctrl+F / Ctrl+` / Ctrl+S / F1，以及
   vim-only 的 `:` 注释 L539-542），没有 F5 文案要迁移；是否在 welcome
   增列调试键属新增内容，实施时自行决定。
   - 备选 A（保守）：F5 保留给 ex 行，调试启动不绑 F5，改用
     `:debug`/命令面板与 F9-F11 步进——偏离 VS Code 肌肉记忆；
   - 备选 B：F5 按"当前 filetype 是否注册 debugger"隐式复用——行为
     不可预测，不推荐。
2. **扩展键位层支持带修饰 F 键**。xterm 约定：F5-F12 的 `~` 族基准码
   为 F5=15、F6=17、F7=18、F8=19、F9=20、F10=21、F11=23、F12=24；
   带修饰发 `\x1b[<code>;<param>~`，param = 2(shift)/3(alt)/
   5(ctrl)/6(ctrl+shift)。改造点：
   - [base.py](yate/keymaps/base.py)：
     `parse_key` 对 `~` 族 F 键按修饰符拼参数序列；`key_name` 与
     `KEY_ALIASES`（[L55-77](yate/keymaps/base.py#L55-L77)）
     增加逆映射，帮助覆盖层能显示 `<shift+f5>`；
   - [editor_view/keys.py](yate/editor_view/keys.py)：
     `textual_key_to_raw` 识别 Textual 的 `shift+f5`/`ctrl+shift+f5`
     事件名（mods 排序元组匹配，风格同现有 `_MOD_ARROWS`
     [L18-23](yate/editor_view/keys.py#L18-L23)）；
   - 本期只实现调试实际用到的 shift 组合（Shift+F5、Shift+F11），
     其余参数序列一次性支持但不绑定。
3. **两套键位都加调试键**：vsc 全局生效；vim 仅 NORMAL/VISUAL 模式
   生效（INSERT 不拦截，由 vim 键位的模式判断处理，与其现有 F 键空白
   不冲突）。vim 用户始终可用 `:debug` 系列命令。
4. 新增帮助分类常量 `DBG = "Debug"`（vsc.py 顶部常量区
   [L8-16](yate/keymaps/vsc.py#L8-L16)），
   帮助页自动分组。

### 5.1 断点与会话状态模型（app 侧）

- 断点的唯一存储在 `DapManager`（按 path），App 不另存；
- 执行行 `self.dap.active_location()` 供 gutter 读取；
- `_on_dap_event(kind: str)`（紧随
  [_on_lsp_event L1316-1325](yate/app.py#L1316-L1325)，
  事件循环线程安全约定相同）：
  - stopped/continued：所有 editor view refresh（gutter 标记/执行行）、
    调试面板刷新（栈/变量/输出）、状态栏刷新；stopped 时面板自动切 info；
  - output：面板若打开则追加渲染，未打开则状态栏/消息行给 "●" 提示有
    新输出；
  - terminated：消息行提示退出码、恢复 gutter、面板保留输出；
  - failed：消息行红字原因（adapter 不存在时给出
    `pip install debugpy` 提示）；
- 所有动作用 `self.run_worker(coro, group="dap", exclusive=False,
  exit_on_error=False)` 发起（范式同
  [app.py:1310-1313](yate/app.py#L1310-L1313)
  的 lsp-sync 组），动作函数本身不阻塞事件循环。

### 5.2 gutter 标记（editor.py）

[gutter_width()](yate/editor_view/editor.py#L269-L271)
由 `max(3, digits) + 3` 改为 `+ 4`，gutter 布局从
`空|行号|空|诊断`（[L460-463](yate/editor_view/editor.py#L460-L463)）
扩为 `空|行号|空|诊断|调试点`，宽度恒定（与有无会话无关，避免文本
左右抖动）；补全弹层因复用 gutter_width
（[completion.py:135](yate/app_features/completion.py#L135)）
自动跟随，无需另改：

| 情况 | 调试点列 |
|------|----------|
| 执行行（active_location 命中文档+行） | `▶`，t.yellow，bold |
| 普通断点行 | `●`，t.red |
| 命中断点的执行行 | `▶` 优先（黄） |
| 其他 | 空格 |

执行行额外整行处理：行号 bold + 行底 `t.surface`（MVP 直接复用当前行
已有的 surface 底 [L438-439](yate/editor_view/editor.py#L438-L439)，
零 Theme 变更；不加新颜色字段）。诊断列逻辑不动。
断点红/执行黄都是既有字段（t.red/t.yellow）。welcome 页经同一 gutter
渲染，实施时核对其居中（`_render_welcome` 以 gutter_w 为左边界）不错位。

### 5.3 调试面板：widget + feature 分层（两个新文件）

**widget**：`editor_view/debug_panel.py`（仿
[editor_view/terminal.py](yate/editor_view/terminal.py)
的 Textual 部件：`DebugPanel(Vertical)` 对照 `TerminalPanel`
[terminal.py:326](yate/editor_view/terminal.py#L326)，
包一个可聚焦的 `DebugView(Widget, can_focus=True)` 对照
`TerminalView` [L56](yate/editor_view/terminal.py#L56)，
只负责渲染与按键，不持有调试状态；**不引入 editor_term 依赖**，面板
无 PTY）。挂载于
[compose 的 #bottom-dock](yate/app.py#L1695-L1699)
（`TerminalPanel` 之上），初始 `display=False`，on_mount 中与 terminal
同样取引用并设高（[L1710-1712](yate/app.py#L1710-L1712)）。

**feature 生命周期**：`app_features/debug.py`（仿
[app_features/terminal.py](yate/app_features/terminal.py)：
模块级 `toggle_debug_panel/open_debug_panel/close_debug_panel(app)`，
状态标志 `_debug_visible` 留在 app；launch/step/stop 的 worker 编排也
放这里）。与终端面板**互斥**：开 debug panel 时调用
`close_terminal(app)`（[terminal.py:49-58](yate/app_features/terminal.py#L49-L58)），
反向亦然；高度共用配置 `terminal_height`
（[config.py:93](yate/config.py#L93)），
`:set terminal_height` 对两者同时生效，不新增配置项。

双模式：

- **out 模式**：debuggee 输出流（output events 环形缓冲渲染，彩色区分
  stderr：MVP 用 t.fg_dim+红消息头标记 stderr 行，不做 ANSI 解析）。
  底部一行 evaluate 输入，按 `>` 开头输入，Enter 发
  `evaluate(context="repl")`，结果/异常作为 console 类 output 追加；
- **info 模式**：stopped 时显示
  `Threads → Stack frames（当前帧高亮 ▶）→ Scopes → Variables（两级
  树缩进，variables_reference>0 标 `+`，Enter 展开调 manager
  expand_variable）`。未停止时显示 "program is running / not started"。
- 模式切换：面板聚焦时 Tab 或命令 `:debug-panel out|info`；stopped
  事件自动切 info，continued 自动切 out。

MVP 不做：watch 表达式窗口、多线程间切换（默认取 stopped 事件的
threadId；其他线程只读展示在 info 顶部但不可切换）、变量就地编辑
（setVariable）、悬浮 inline 值（hover 求值）。

### 5.4 状态栏（statusbar.py）

仿照 `_lsp_segment`
（[statusbar.py:97-122](yate/editor_view/statusbar.py#L97-L122)）
新增 `_debug_segment()` 并接入右侧拼装链
（[L57-60](yate/editor_view/statusbar.py#L57-L60)）。
仅在会话非 CONFIGURED/TERMINATED 时显示，无会话时零占位、不影响现有
宽度预算：

```text
▮ debug: python  paused at main.py:42
▮ debug: python  running
▮ debug: python  failed: debugpy-adapter not found (pip install debugpy)
```

### 5.5 动作、命令与键位

动作注册在 [actions.py](yate/actions.py) 的
`populate`（键位只引用动作名；动作体转发到 `app_features/debug.py`）：
`debug_start_or_continue`（F5 单动作按会话状态分发：无会话→launch、
PAUSED→continue、RUNNING→消息提示）、`toggle_breakpoint`、`step_over`、
`step_into`、`step_out`、`pause_debug`、`debug_stop`、`debug_panel`。

命令注册在
[register_commands](yate/app_features/commands.py#L45)
（命令面板可搜、可绑键、扩展可调）：

| ex 命令 | 动作 | vsc 默认键（迁移后） | vim |
|---------|------|-----------|-----|
| `:debug [path]` | 启动调试（当前文件/指定文件；未保存先提示） | **F5**（无活动会话） | NORMAL 下 F5 |
| `:cont`（`:continue`） | 继续 | **F5**（PAUSED 时） | NORMAL 下 F5 |
| `:break` | 切换当前行断点 | **F9** | NORMAL 下 F9 |
| `:next` | step over | **F10** | NORMAL 下 F10 |
| `:step` | step into | **F11** | NORMAL 下 F11 |
| `:finish` | step out | **Shift+F11**（需 §5.0 键位层改造） | 同 |
| `:pause-debug` | 暂停（pause） | F6 | NORMAL 下 F6 |
| `:debug-stop` | 终止会话（terminate→disconnect） | **Shift+F5**（需改造） | 同 |
| `:debug-restart` | 重启（Phase 2，本期命令报 "not yet"） | — | — |
| `:eval [expr]` | 暂停态求值，结果到消息行/面板 | 无（面板输入） | 同 |
| `:debug-panel [out\|info]` | 打开/切换调试面板 | F12 | NORMAL 下 F12 |
| （迁移）ex 命令行 | 原 F5 动作 `command_prompt` | **F7**（§5.0 决策） | `:` 不变 |

F5 上下文行为：无活动会话=launch、PAUSED=continue、RUNNING=noop 给
消息提示。F9 在无会话时也允许切换断点（断点先于会话存在，launch 时
统一下发，见 §3.4 启动序列）。

### 5.6 关闭路径

- 退出 App：teardown 序列中
  [app.py:1741-1750](yate/app.py#L1741-L1750)
  在 terminal/lsp 之间插入 `await self.dap.shutdown_all()`，
  terminate 给 3s 宽限再 disconnect/kill，退出不被挂死；各 teardown
  相互隔离（沿用现有 try/except 模式）；
- 关闭被调试文件：不影响会话（断点按 path 存）；重新打开同名文件
  断点标记自然恢复；
- adapter 崩溃/EOF：reader 结束 → 状态 FAILED → 事件 failed
  （"debug adapter exited"）+ 面板保留已有输出。

---

## 6. 错误处理与可发现性

| 场景 | 行为 |
|------|------|
| 未安装 debugpy | 扩展照常注册（懒失败，与 pylsp 一致）；`:debug` 时消息行：`no Python debug adapter found — pip install debugpy (or set YATE_PYTHON_DAP)`，不弹 traceback |
| initialize 超时/进程拉起失败 | FAILED + 消息行；teardown 不残留子进程（复用 LSP 的 in-flight spawn 处理） |
| debuggee 立即退出 | terminated 事件 + 退出码；面板保留输出供排查 |
| 未保存/无路径文件启动 | 拒绝并提示保存 |
| 调试中再按 F5 | continue；非暂停态给消息提示，不重复 launch |
| evaluate 在运行态调用 | 返回 "paused only" 消息，不发请求 |
| js-debug 请求 `startDebugging` 反向请求（自动挂子进程） | Phase 1 回 unsupported，只调根进程；文档/示例注释明确，Phase 2 支持 |
| 终端不发送带修饰 F 键序列（个别终端/多路复用器） | 所有动作都有 `:命令` 与命令面板兜底；dap 文档"键位"节列出该限制与 Shift+F5 的原始序列 |
| 单文件单测全用内存假 adapter | `client_factory`/`connect` 双注入点，零真实进程（与 LSP 测试同手法） |

`yate --diag` 在 `[lsp]` 节（[diagnostics.py:391-414](yate/diagnostics.py#L391-L414)）
之后新增 **`[dap]`** 节：注册的 debugger 名单、filetypes、发现的
command（或 `(none)`）、扩展 opt-out 状态、launch 模板键名、当前会话
状态。风格沿用 lsp 节的两列缩进。

---

## 7. 实施步骤（Phase 1）

0. **前置**：键位层支持带修饰 F 键（§5.0 事实 2），含
   base.py/keys.py/key_name 与单元测试；F5→F7 迁移（vsc.py 绑定 L91 与
   L88-90 注释、手册中英文各 6 处、README 三行键位表；welcome 页无
   F5 文案，不改；帮助覆盖层自动生成，见 §5.0 决策 1）。
1. `editor_dap/protocol.py`、`types.py`、`client.py`（先无 UI 跑通
   内存假 adapter 的全序列测试）。
2. `editor_dap/manager.py`（注册、断点、launch 序列、stopped 快照、
   output 缓冲、单会话、shutdown）+ `__init__.py` 导出。
3. `services/extensions.py` 增加 `DapExtensionBridge` 与 `api.dap`。
4. `extensions/python_dap.py`（五级 discover + launch 模板）。
5. `extensions/example_js_dap.py.example`（Node/js-debug 完整范例，
   含安装/限制头注释）。
6. `config.py`：`debug_options` 选项与跨 adapter 通用白名单；
   yaterc.example 补段。
7. `actions.py` 调试动作；`app_features/debug.py` 生命周期与 worker
   编排；`app_features/commands.py` 注册 `:debug` 系列；vsc/vim
   键位（§5.5）。
8. `app.py`：`self.dap` 构造（L199 区）、`_on_dap_event`（L1316 区）、
   compose/on_mount 挂 DebugPanel（L1695/L1710 区）、面板互斥、
   teardown shutdown（L1747 区）。
9. `editor_view/debug_panel.py`；editor.py gutter +1 列与执行行底；
   statusbar debug 段。
10. `diagnostics.py` dap 节（同步测试的节清单常量，§8.2）。
11. 文档（§9）；全量测试 + pyright strict + 手动真 debugpy/js-debug
    验证（§8.3）。

---

## 8. 测试方案

### 8.1 单元（无真实进程，镜像 LSP 测试手法）

LSP 测试现有手法（直接照搬）：分帧内存假 reader
（`FakeReader`，[test_lsp.py:40](tests/test_lsp.py#L40)）、
TCP 回环假 server harness
（`FakeProc`/`ServerHarness`，[L144-240](tests/test_lsp.py#L144-L240)，
经 `connect=` 注入）、manager 层 `FakeClient` + `client_factory`
session fixture（[L471](tests/test_lsp.py#L471)、
[L573-600](tests/test_lsp.py#L573-L600)）。

**tests/test_dap_protocol.py**：build_request 形状
（seq/type/command/arguments）；response 解析（success/error、
request_seq 关联）；event 判定；复用的 framing 往返
（encode→parse_headers→decode_body）；超长 Content-Length 拒绝。

**tests/test_dap_client.py**：脚本化 in-memory adapter（队列收消息、
按序回 initialize response / initialized event / 各 response /
stopped+output events / terminated）：
- initialize 参数含 adapterID/linesStartAt1/pathFormat；
- **顺序固化**：setBreakpoints → launch（不 await）→
  configurationDone；断言收到消息的命令序列；
- response 按 request_seq 匹配（乱序返回也正确）；
- success=false → DapResponseError；initialize 超时 → FAILED + teardown；
- stop() 终止在途 spawn（复刻 LSP 的 Windows cwd 占用教训，对照
  [test_lsp.py:387](tests/test_lsp.py#L387)）；
- reverse request 收到 unsupported 响应。

**tests/test_dap_manager.py**：
- 注册/按 filetype 查/同名替换（对照 LSP
  [test_lsp.py:530](tests/test_lsp.py#L530)）；
- 断点 toggle 去重、按文件分组、1-based 转换断言（捕获
  setBreakpoints 参数 lines=[n+1...]）；
- launch 合成参数（program 绝对路径、cwd=root、debug_options 白名单
  合并、未知键拒绝）；未保存文件拒绝；活动会话二次 launch 拒绝；
- stopped 事件驱动的 threads→stackTrace→scopes→variables 拉取链与
  快照组装（含 scopes 拉取失败降级、frame 无 source 时 row=-1）；
- step/continue/pause/terminate 透传正确 threadId；
- output 缓冲分类与环形上限；terminated 清 snapshot 但保留断点；
- shutdown_all 幂等。

**tests/test_python_dap_ext.py**：discover 五级（env 覆盖/opt-out、
which 命中、解释器相邻 launcher 命中、find_spec 命中→
`sys.executable -m debugpy.adapter`、全空）；注册的 launch 模板与
filetypes；disabled_extensions 机制下不加载（走现有
[test_extensions.py](tests/test_extensions.py)
的加载设施）。

**tests/test_dap_examples.py**：对随包的
`extensions/*_dap.py.example` 做静态/加载校验：
- 文件存在、UTF-8 可解析、`compile()` 语法通过；
- 以假 `ExtensionAPI`（记录 `api.dap.register_debugger` 调用参数）
  exec 模块并调用 `setup(fake_api)`：断言注册名 `node`、filetypes 含
  `js`、launch 含 `type=pwa-node`/`request=launch`/`outputCapture`、
  root_markers 含 `package.json`；
- `discover_command()` 在 monkeypatch 的
  `YATE_JS_DAP`/`shutil.which` 下三级返回正确（覆盖值/opt-out/未找到）；
- 源码纪律：示例不 import yate（仅 TYPE_CHECKING），保证拷到
  `~/.yate/extensions/` 后运行环境一致。

**tests/test_extensions.py 增补**（注意：仓库**没有**
test_extensions_bridge.py，桥相关测试集中在 test_extensions.py）：
`api.dap.register_debugger` 参数默认值与转发、空 command 仍注册、
`api.dap.statuses()`/`has_state()`。

**tests/test_config.py 增补**（现有文件，风格参照其 language_servers
系列 [L173-421](tests/test_config.py#L173-L421)，
节首为 L173 注释、用例 L176-421）：
debug_options 合法 dict 合并、非 dict 报错、未知键报错。

**键位层测试（§5.0 前置）**：`parse_key("<shift-f5>")` 等与
`textual_key_to_raw("shift+f5")` 双向一致、`key_name` 逆映射正确、
裸 F5 不被 shift 序列覆盖；归入现有键位测试区
（[test_app_textual.py:56-86](tests/test_app_textual.py#L56-L86)
的 named/ctrl/alt/modified-arrows 组，或 test_panes.py 同层）。

### 8.2 UI / 集成

- **tests/test_app_textual.py**（pilot headless，范式见
  [L88-140](tests/test_app_textual.py#L88-L140)）：
  gutter 字符串断言（断点行 ●、执行行 ▶、两者叠加优先 ▶、gutter 宽度
  恒定 +1、welcome 页不错位、补全弹层左边界随 gutter 移动）；
  F9 切换→再按取消；无会话时状态栏无 debug 段，PAUSED 段含
  `paused at`；F7 在 vsc 模式打开 ex 命令行、F5 启动/继续；
- 命令分发：`:debug/:next/:cont/:debug-stop` 在假 manager 下动作
  正确、未保存文件出提示；
- debug panel：output 追加（stdout/stderr 区分）、stopped 切 info、
  变量 `+` 展开触发 expand_variable、evaluate 输入结果回显；与
  terminal 面板互斥；
- App 关闭路径调用 dap.shutdown_all（与 lsp 同一测试范式）；
- **tests/test_diagnostics.py 必改**：节顺序常量硬编码了 12 节
  （[_ALL_SECTIONS L19-22](tests/test_diagnostics.py#L19-L22)）
  与 `test_report_contains_all_twelve_sections`
  （[L54-57](tests/test_diagnostics.py#L54-L57)），
  插入 dap 后改 13 节，并按 lsp 节测试
  [L107-122](tests/test_diagnostics.py#L107-L122)
  的样子补 dap 节用例；
- **tests/test_user_setup.py 增补**：`--setup-defaults` 输出包含
  `extensions/example_js_dap.py.example`（通配拷贝
  [user_setup.py:102-106](yate/services/user_setup.py#L102-L106)）；
- **tests/test_cli.py**：`--diag` 报告含 `[dap]`（现有 diag 走查
  [L183-206](tests/test_cli.py#L183-L206)）。

### 8.3 手动真实验证（安装 debugpy 的 venv）

```powershell
pip install debugpy
# 准备 t.py：
#   import sys
#   for i in range(3):
#       print("hello", i, file=sys.stderr if i == 1 else sys.stdout)
yate t.py
# F9 在 print 行设断点 → F5：暂停在该行、面板 info 显示 i 的值、
# F10 单步观察变量变化、F11/F10/Shift+F11、:eval i+10、F5 继续、
# Shift+F5 终止；输出面板出现 hello 0/1/2（1 为 stderr 样式）
# 自然跑完：terminated + 退出码 0；故意 raise：stopped(reason=exception)
yate --diag    # 核对 dap 节
```

Node/js-debug 走查（验证扩展范例端到端可用）：

```powershell
npm install -g js-debug-adapter
# 安装示例扩展：yate --setup-defaults（拷为 *.example）后改名
Copy-Item yate\extensions\example_js_dap.py.example `
          $HOME\.yate\extensions\example_js_dap.py
# 准备 app.js：
#   for (let i = 0; i < 3; i++) console.log("hello", i);
yate app.js
# F9 设断点 → F5：暂停、info 面板看 i（含原型/闭包变量）、F10/F11 步进、
# 输出面板出现 hello 0/1/2、Shift+F5 终止；--diag 中 dap 节出现 node。
# 未装 js-debug-adapter 时 F5 给 npm 安装提示而非 traceback。
```

```powershell
python -m pytest tests/test_dap_protocol.py tests/test_dap_client.py `
  tests/test_dap_manager.py tests/test_python_dap_ext.py `
  tests/test_dap_examples.py -v
python -m pytest tests/ -v
```

---

## 9. 文档与资源

| 文件 | 内容 |
|------|------|
| `yate/docs/dap.zh.md` / `dap.en.md`（新增） | 调试指南：架构一图、debugpy 安装、F5/F9/F10/F11 键位表、断点/求值/面板用法、`YATE_PYTHON_DAP`/`YATE_JS_DAP` 与 `debug_options`、internalConsole/startDebugging 当前限制、**带修饰 F 键的终端兼容说明**、**"用扩展接入其他 adapter"教程（以随包 JS 范例完整走查 + gdb/dlv 等差异点表）**；与现有 [lsp.zh.md](yate/docs/lsp.zh.md) 同级同双语风格 |
| `yate/resources/manual.zh.md` / `manual.en.md` | 新增"调试"章（置于 §13 集成终端/§14 Shell 集成 之后）：快速开始（t.py 走查）、命令/键位表、JS 范例一段（改名即装）、限制；**同步改写 F5=命令行的既有条目**（en 版 L181/L329/L347/L530/L554/L1346 及 5.1 键位表（标题 L263）；zh 版 L172/L314/L331/L499/L518/L1213——两版行号不同，逐条改） |
| `yate/yaterc.example` | 在 `language_servers` 段（[L94-128](yate/yaterc.example#L94-L128)）之后增加 debug_options 注释段（只列跨 adapter 通用键），内置扩展清单（L52-56）补 `python_dap` 一行 |
| `yate/extensions/example_ext.py.example` | API 面清单（[L30-31](yate/extensions/example_ext.py.example#L30-L31)）增加 `api.dap.register_debugger` 小例（注释态，指向完整 JS 范例） |
| `yate/extensions/example_js_dap.py.example`（新增） | JS/Node（js-debug-adapter）完整扩展示例：discover + 注册 + pwa-node launch 模板 + 限制注释 |
| `README.md` / `README.zh.md` | 特性区（[README.md:24-40](README.md#L24-L40)）特性行增加 debugging（DAP：内置 debugpy + JS 扩展示例）；F5=命令行的键位表行改写为 F7 并补调试键（[README.md:89](README.md#L89)、[README.zh.md:109](README.zh.md#L109) 与 [L412](README.zh.md#L412)，zh 有两处表）；结构树（L212-228 的 app_features/extensions/docs 说明）补 editor_dap/editor_term |
| `yate/editor_dap/__init__.py` | 包 docstring 说明模块划分与 UI 无关边界（仿 [editor_lsp/__init__.py](yate/editor_lsp/__init__.py)） |
| `.trae/documents/dap_support_plan.md` | 本文档 |

---

## 10. 文件变更清单（Phase 1）

| 文件 | 操作 | 说明 |
|------|------|------|
| `yate/editor_dap/__init__.py` | 新增 | 公共导出 + 包 docstring |
| `yate/editor_dap/protocol.py` | 新增 | DAP 消息层；复用 LSP 分帧 |
| `yate/editor_dap/types.py` | 新增 | 配置/断点/帧/变量/快照数据类、SessionState 枚举 |
| `yate/editor_dap/client.py` | 新增 | DapClient 全生命周期 |
| `yate/editor_dap/manager.py` | 新增 | 注册器/会话/断点/快照/输出 |
| `yate/extensions/python_dap.py` | 新增 | debugpy 内置支持（可 disabled） |
| `yate/extensions/example_js_dap.py.example` | 新增 | JS/Node 扩展示例，改名 `.py` 即激活；`--setup-defaults` 通配拷贝（零改动） |
| `yate/services/extensions.py` | 修改 | DapExtensionBridge + `api.dap` property |
| `yate/config.py` | 修改 | `debug_options` 选项与白名单（`_KNOWN_OPTIONS` [L48-51](yate/config.py#L48-L51)） |
| `yate/keymaps/base.py` | **修改（前置）** | 带修饰 F 键 parse/key_name/KEY_ALIASES（§5.0） |
| `yate/editor_view/keys.py` | **修改（前置）** | textual_key_to_raw 识别 shift/ctrl+shift + F 键 |
| `yate/keymaps/vsc.py`、`yate/keymaps/vim.py` | 修改 | F7=command_prompt 迁移；F5/F6/F9/F10/F11/F12/Shift+F5/Shift+F11 调试动作；vim 限 NORMAL/VISUAL；DBG 分类 |
| `yate/actions.py` | 修改 | `populate` 增调试动作（L154 view 段附近） |
| `yate/app_features/commands.py` | 修改 | `register_commands` 注册 `:debug` 系列 |
| `yate/app_features/debug.py` | **新增** | 调试 feature 生命周期：面板开关互斥、launch/步进 worker 编排（仿 terminal.py） |
| `yate/app_features/terminal.py` | 修改 | open 时互斥关闭 debug 面板（一行钩子） |
| `yate/app.py` | 修改 | self.dap（L199 区）、`_on_dap_event`（L1316 区）、compose/on_mount 挂面板（L1695/L1710 区）、teardown（L1747 区） |
| `yate/editor_view/editor.py` | 修改 | gutter +1（●/▶，L269/L441 区）、执行行底色；welcome hints 无 F5 文案（L535-548 仅核对不错位，不做 F5 迁移） |
| `yate/editor_view/debug_panel.py` | 新增 | out/info 双模式面板 widget + evaluate |
| `yate/editor_view/statusbar.py` | 修改 | `_debug_segment()`（仿 L97-122） |
| `yate/diagnostics.py` | 修改 | sections 注册表 [L86-99](yate/diagnostics.py#L86-L99) 插 dap 节 + `_section_dap` |
| `yate/yaterc.example`、`example_ext.py.example` | 修改 | 配置段/API 示例 |
| `docs/dap.zh/en.md`、`manual.zh/en.md`、`README(.zh).md` | 新增/修改 | 文档（含手册 F5 条目迁移） |
| `tests/test_dap_protocol.py`、`test_dap_client.py`、`test_dap_manager.py`、`test_python_dap_ext.py`、`test_dap_examples.py` | 新增 | 核心测试 |
| `tests/test_extensions.py`、`test_config.py`、`test_app_textual.py`、`test_diagnostics.py`、`test_user_setup.py`、`test_cli.py` | 修改 | 桥接/配置/UI/节清单/模板分发/diag 接线测试（**无** test_extensions_bridge.py，该文件不存在） |
| `pack/yate.spec`、`pack/yate-onefile.spec`、`pyproject.toml` | **不改** | spec 的 Tree 整树收集与 hatchling `packages=["yate"]` 自动覆盖新文件（§首节说明） |
| `.trae/documents/dap_support_plan.md` | 修改 | 本文档（2026-09-15 校准） |

**明确不做（Phase 1）**：不动 editor_lsp 任何代码（只 import 分帧）、
不改 Theme 数据结构、不做 socket/attach、不做 integratedTerminal
（runInTerminal）、不做条件断点/日志断点、不做断点持久化、不做 watch/
inline hover/setVariable、不做键位自定义配置（F7 迁移写死，Phase 2
再做可配置键位）。

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

**Phase 2（可用性补全）**：条件断点/日志断点（capabilities 声明 + gutter
浮层输入）、`debug_adapters` 声明式 yaterc 注册、断点持久化
（`.yate/debug-state.json`）、restart、多线程切换、变量展开分页
（indexed/named variables）、setVariable、watch 列表、hover 求值、
异常断点过滤器 UI（debugpy 的 raised/uncaught）、更多 adapter 文档
（gdb/dlv/lldb-dap 的差异点示例；JS 已在 Phase 1 随包提供）、
debugpy/js-debug attach 配置示例、**键位自定义配置**（F5/F7 等动作
键允许 yaterc 重绑）。

**Phase 2 还包括**：DAP `startDebugging` reverse request（js-debug
自动挂子进程/worker、debugpy subProcess 自动附加所依赖的能力——
Phase 1 统一回 unsupported，需在 client 增加反向请求处理器与多会话
支持后才能放开）、把 JS 范例从 `.example` 提升为真正内置扩展的评估。

**Phase 3（深度集成）**：`console: "integratedTerminal"`（实现
RunInTerminal reverse request，debuggee 进程经
[`editor_term`](yate/editor_term)
PTY 后端（pty_proc/shells，TerminalView 的现有底层）跑入集成终端
面板，而非 Phase 1 的 internalConsole output 回流）、
attach 到已运行进程（socket 模式，client 传输层需抽象 stream 工厂）、
远程调试、跳转栈帧打开源码、调试控制台语法补全、repl 多行/绘图、
测试调试（pytest/npm run test launch 模板）。

**重构项（独立于功能）**：分帧下沉到中立模块（§3.1），消除
editor_dap 对 editor_lsp 的 import 依赖；届时 LSP/DAP 共享
`yate/editor_rpc/framing.py`。

---

## 13. 风险与对策

| 风险 | 对策 |
|------|------|
| debugpy 不同版本 launch 响应/initialized 时序差异 | 严格按 DAP 规范不 await launch 响应；capabilities 存在性逐项防御；手动验证 debugpy 当前 PyPI 版 |
| Windows 路径/反斜杠/空格 | pathFormat="path"、program 绝对路径、subprocess_exec（不经 shell）；与 LSP 同一套已验证的 spawn 代码 |
| adapter 泄漏进程（cwd 占用导致临时目录删不掉） | 复刻 LSP `_connecting` future + stop 宽限 + terminate/kill 链路；manager shutdown 测试在 Windows CI 跑 |
| 1-based 坐标错位 | 转换只在 manager 边界；测试对 setBreakpoints lines 与 StackFrame.row 做双向断言 |
| F5 迁移引发既有用户肌肉记忆冲突 | 手册/welcome/帮助/README 全量同步；`:debug` 与命令面板双入口；Phase 2 提供键位重绑；评审时若否决则回退 §5.0 备选 A（F5 保留，调试改命令驱动） |
| 部分终端/多路复用器不上报 Shift+F5/Shift+F11 序列 | 键位层加双向单测固化 xterm 序列；全部调试动作有 `:命令` 兜底；dap 文档明列限制与原始序列 |
| 调试面板与终端面板争底部空间 | 互斥打开（开 debug panel 关 terminal，反之亦然），共用 panel 高度配置 terminal_height |
| 大 variables/输出刷屏 | variables 按 scope 懒展开 + output 环形缓冲（默认 256KB） |
| 断点设在注释/空行 | setBreakpoints 响应体回传实际绑定行；manager 用响应校正（Phase 1 先信任响应但仅在 info 提示数量，不回填 gutter；Phase 2 回填） |
