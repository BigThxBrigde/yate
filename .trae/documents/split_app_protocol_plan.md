# 拆分并移除 `AppProtocol` 重构方案

> **状态：DRAFT（草稿，评审中）** — 本文档为重构草案，尚未实施；
> 协议成员命名、语义化 Host 方法等细节可能在评审中调整。

> **目标**：删除 `yate/interfaces.py` 中的 `AppProtocol`（88 个成员的"全应用协议"），
> 改为 **每个模块持有自己的窄接口（Protocol）**，由 `YateApp` 作为组合根实现这些接口；
> 操作类逻辑（explorer / terminal / completion / docs / commands）迁移为
> **Feature 类**，直接持有自己的宿主接口与注入的服务，不再经由 `YateApp` 转发。
>
> **硬性验收**：pyright strict 0 诊断 · pytest 全绿 · 无 `TYPE_CHECKING` ·
> 无 `AppProtocol` 残留 · `yate/` 内除 `cli.py` 外无人 import `yate.app` · 无循环依赖。
>
> 行号基于当前分支 `issues/logs-refactoring` 的 HEAD。

---

## 1. 现状与问题（证据）

### 1.1 当前依赖结构

```
editor_core / editor_lsp / editor_syntax / editor_term / logs / paths   ← 叶子（无 AppProtocol）
        ↑
yate/interfaces.py  ── AppProtocol（88 成员，为打破循环而生）
        ↑
keymaps / services / actions / editor_view / app_features / diagnostics   ← 18 个模块 import 它
        ↑
yate/app.py（YateApp，1911 行、110 个方法） ← cli.py 组装
```

`AppProtocol` 设计上是"低层模块对 YateApp 的全部依赖面"。它靠
`TYPE_CHECKING`（`interfaces.py:42-56`）+ 字符串前向引用保持 leaf-level，
本身就是**为绕开循环依赖而引入的间接层**。

### 1.2 问题清单

| # | 问题 | 证据 |
|---|------|------|
| 1 | **上帝接口**：88 个成员混装状态、服务、UI、操作四类关注点；任何模块加需求都往里塞 | `interfaces.py:59-308` |
| 2 | **接口无隔离**：18 个模块共享同一接口，无法表达"谁需要什么"；每个模块实际只用其中 3~38 个成员 | 探索汇总（editor_view 只用 38 个，约 43%） |
| 3 | **app_features 直接读写 app 私有状态**（不是"持有接口"） | `explorer.py:43,44,57,68`；`terminal.py:23,34,38,49,53,59,64,70,76-77` |
| 4 | **YateApp 有 18 个纯转发方法**（薄委托），app.py 被迫变厚 | `app.py:1035-1057`（explorer×8）、`1534-1547`（terminal×4）、`1423-1438`（completion×4）、`1480-1486`（docs×2） |
| 5 | **反向写 app 状态**：低层模块直接改高层状态 | `panes.py:172` 写 `app.doc_index`；`commands.py:163-191` 改 `config.shell/terminal_height`、`workspace.show_hidden`、`_terminal_visible` |
| 6 | **死代码/死引用**：赋值后从未使用 | 见附录 A（7 处） |
| 7 | **eager `__init__` 放大依赖**：`from yate.editor_view import theme` 会全量加载 6 个 widget | `editor_view/__init__.py:18-23`；`services/__init__.py:3-5`；`config.py:42` |
| 8 | `TYPE_CHECKING` 必须保留（`interfaces.py`），与"消除 TYPE_CHECKING"目标冲突 | `interfaces.py:42-56`、`tests/test_editor_core.py:17-18` |

**核心判断**：问题的根因不是"类型不够精确"，而是 **依赖方向被一个中间协议统一收纳后失去了结构**。
正确解法是 **接口倒置 + 按消费者拆分 + 组合根接线**，而不是继续维护 `AppProtocol`。

---

## 2. 目标与验收标准

| 目标（用户原文） | 验收判据 |
|---|---|
| ① `AppProtocol` 不需要 | `yate/`、`tests/`、`tools/` 内 `AppProtocol` 命中数 = 0；`yate/interfaces.py` 删除 |
| ② 各模块指向接口实现，实际操作委托给实现实例 | 每个 widget/feature 只依赖自己模块定义的窄 Protocol；explorer/terminal 由 Feature 实现 Ops |
| ③ 跨模块交互机制明确 | 见 §3.4 决策表（直调 + 回调 + 注册表，不引入全局总线） |
| ④ 接口隔离、职责单一 | 每个协议成员数 ≤ 消费者实际访问数；无协议跨领域混装（见 §3.5 判定准则） |
| ⑤ 最终 `AppProtocol` 移除 | `interfaces.py` 删除、`__init__.py` 文档串同步 |
| ⑥ `app_features` 持有类型接口 | Feature 类构造注入 `XxxHost` / 服务；不再出现 `app._私有` 访问 |
| ⑦ YateApp 顶层 & 松耦合 | `yate/` 内只有 `cli.py` 导入 `yate.app`；`grep TYPE_CHECKING yate/` = 0；运行时导入图无环（新增架构测试守护） |
| ⑦ 性能与结构 | 协议为静态类型零运行时开销；删除转发层缩短调用链；无新增间接调用 |
| ⑦ 可扩展/可维护 | 新增 `tests/test_architecture.py` 防回归；扩展 API 文档同步 |

---

## 3. 设计决策

### 3.1 三类协议

| 类型 | 定义位置 | 实现者 | 消费者 | 例子 |
|---|---|---|---|---|
| **Host（宿主接口）** | 消费方组件模块内 | `YateApp` | 组件自身 | `EditorHost`、`PanesHost`、`StatusBarHost`、`ExtensionHost`、`DiagnosticsHost`、`ExplorerHost`、`TerminalHost` |
| **Ops（操作接口）** | 操作提供方（`app_features/*`）内 | Feature 类 | UI 组件 | `ExplorerOps`（←`ExplorerTree`）、`TerminalOps`（←`TerminalView/Panel`） |
| **能力接口（角色）** | 消费子系统内 | `YateApp` | 子系统 | `ActionHost`、`SessionOps`、`VimOps`、`CommandHost` |

规则：
- 协议成员类型只能来自 stdlib / textual / 叶子包（`editor_core`、`editor_lsp`、`editor_syntax`、`editor_term`、`logs`、`paths`、`services.workspace`、`services.shell`）/ 本模块内定义的类型或协议。
- **禁止**协议间互相 import 造成的跨层回指（见 §3.2 规则 R3/R4）。
- 不使用 `Any` 逃避类型；不使用 `# type: ignore` 掩盖协议不匹配（pyright strict 会强制 YateApp 真正满足协议——这是免费的编译期校验）。

### 3.2 依赖规则（硬性）

- **R1**：`yate/` 内除 `cli.py` 外，任何模块不得 `import yate.app`。
- **R2**：不得再出现"全应用"协议；每个协议只含单个消费者的实际访问成员。
- **R3**：`app_features/*.py` **不得在模块级导入 `editor_view` 的 widget**（`editor/explorer/panes/terminal/statusbar/commandline/modals/palette`）。
  - 原因：widget 会 import feature 的 Ops 协议（`editor_view/explorer.py → app_features/explorer.py`），若 feature 反向导入 widget 会形成模块级环：
    `app_features.terminal → editor_view(包 __init__) → editor_view.terminal → app_features.terminal`（对方尚未定义 `TerminalOps`）→ `ImportError`。
  - 需要面板/屏幕/提示条能力时改用**语义化 Host 方法**（如 `show_terminal_panel(height)`、`activate_prompt(...)`）。
  - 例外（安全且必要）：`app_features/docs.py → editor_view.manual`、`app_features/completion.py → editor_view.completion`（纯函数 + 弹窗）——被导入的 widget 不反向依赖对应 feature。
- **R4**：`editor_view` 的 widget 不得导入 `app_features` 的**实现类**，只能导入其**协议**（`ExplorerOps`）或数据类型（`CommandRegistry`）。
- **R5**：`services/extensions.py` 不得导入 `editor_view`；`app_features/commands.py` 也不得导入 `editor_view`（否则 `services.extensions → app_features.commands → editor_view 包 → statusbar → services.extensions` 成环）。
  - 措施：把 `commands.py` 唯一的 `from yate.editor_view import theme`（`:theme` 命令用，`commands.py:198-201`）改为 `CommandHost` 的语义方法（`theme_label()` / `available_themes()` / `set_theme()`）。
- **R6**：不使用 `TYPE_CHECKING`。所有协议成员类型在运行时安全可导入（按上述白名单校验）。

### 3.3 目标结构

```
                        ┌───────────────────────────────┐
                        │  cli.py  →  YateApp (组合根)   │  实现所有 Host 协议
                        └───────┬───────────┬───────────┘
            创建/注入 │                 │ 创建/注入
        ┌───────────▼──────┐   ┌──────▼────────────┐
        │ app_features/*    │   │ editor_view/*      │
        │  Feature 类        │◀──│  Widgets（依赖 Ops）│
        │  实现 Ops 协议     │Ops│  依赖 Host 协议     │
        │  依赖 Host 协议 ───┼──▶│                    │
        └───────────┬───────┘   └──────┬────────────┘
                    │ 依赖窄协议        │ 依赖窄协议
        ┌───────────▼─────────┐ ┌──────▼─────────────┐
        │ keymaps / actions    │ │ services/extensions │
        │ diagnostics          │ │（ExtensionHost）    │
        └──────────────────────┘ └─────────────────────┘
```

典型双向协议（以 explorer 为例）：

```
YateApp ──实现──▶ ExplorerHost ◀──依赖── ExplorerFeature ──实现──▶ ExplorerOps ◀──依赖── ExplorerTree
   (组合根)         (会话/服务/UI 原语)        (操作实现者)        (widget 需要的操作面)      (UI)
```

### 3.4 跨模块交互：直调 vs 消息机制（回答设计问题③）

**结论：不引入通用消息总线。** 按交互类型选择机制：

| 交互类型 | 场景 | 机制 | 理由 |
|---|---|---|---|
| 1:1 操作 | `ExplorerTree → ExplorerFeature.prompt_new_file` | 窄 Protocol 同步直调 | 类型安全、调用链可追踪、零额外开销 |
| 1:1 查询 | `StatusBar` 读 `doc/lsp/mode_label` | 窄 Protocol 只读属性/方法 | 同上 |
| 1:N 广播（低频） | LSP 诊断更新 → 所有 pane 重绘；主题切换 → 全局刷新 | 保持现有回调（`LspManager(on_event=...)`，`app.py:230-233`）；如未来新增需求，用轻量 `Signal`（回调列表 ~20 行），不建总线 | 订阅者固定、数量少 |
| UI 事件 | 按键、鼠标、`Input.Submitted` | 保持 Textual messages | 框架机制 |
| 异步任务 | shell、补全、LSP 通知、PTY 启动 | `host.spawn(coro_fn, group=...)` 原语（封装 `run_worker`） | 统一入口，杜绝 never-awaited 协程 |
| 插件注册 | 扩展注册命令/动作/键位 | 注册表（`ActionRegistry`/`CommandRegistry`/`Keymap.add_binding`） | 现状良好，不改 |

**引入总线的门槛**（写入代码注释/文档）：出现"通知方不知道谁在监听"且订阅者动态增删的场景 ≥ 3 处时，
再评估 `yate/signals.py`（`Signal[T].connect/emit`），并保持同线程同步派发。

**不做的事**：全局 EventBus、字符串事件名、跨线程消息队列（需要时用 `spawn` + Textual worker）。

### 3.5 接口隔离 vs 职责单一（回答设计问题④）

- **接口隔离（ISP）**：按"消费者"拆接口。同一个 `YateApp` 被 18 个消费者依赖，就有 18+ 个窄协议；
  协议成员 = 该消费者实际访问集。判定："这个成员是给这个消费者用的吗？"
  - 例：`PaneManager` 只需 5 个成员（`docs/doc_index/mounted/after_pane_focus/focus_explorer`）→ `PanesHost`；
    不得因为它"也是宿主"就复用 `EditorHost`（13 个成员）。
- **职责单一（SRP）**：按"功能"拆模块/类。判定："这个类改动的理由是否只有一个？"
  - `YateApp`：只负责**组合与接线**（创建服务/Feature/widget，实现 Host 协议），不含 explorer/terminal 业务逻辑；
  - `ExplorerFeature`：只负责 explorer 操作（提示流 + 文件系统变更 + 会话同步）；
  - `PaneManager`：只负责 pane 树模型；
  - 文档会话（`docs/doc_index/search`）现阶段仍归 `YateApp`，其操作以语义化 Host 方法暴露
    （`open_document` / `close_documents_under` / `retarget_document`），后续可选抽 `EditorSession`（附录 D）。
- 两者的结合：**ISP 决定接口边界，SRP 决定实现归属**。只拆接口不拆实现（=现在的 AppProtocol）无用；只拆实现不拆接口（=现在的私有访问）也不达标。

---

## 4. 接口清单（草案）

> 成员列表 = 当前实际访问面的最小化；标注了少量"语义化替换"（把直连 widget/服务改为宿主方法）。

### 4.1 `editor_view/` 层

| 模块 | 协议 | 成员（消费方实际访问） | 实现者 |
|---|---|---|---|
| `editor.py` | `EditorHost` | `doc`、`lsp`、`search`、`welcome_visible`、`keymap_name`、`completion_popup`、`panes: PaneRegistry`、`request_completion()`、`accept_completion()`、`toggle_terminal()`、`try_window_prefix(event)`、`handle_raw_key(raw)` | YateApp |
| `editor.py` | `PaneRegistry`（本地） | `leaf_by_id(id)`、`leaf_for(id)`、`active_view`、`notify_focus(leaf_id)` | PaneManager |
| `panes.py` | `PanesHost(EditorHost)` | 继承 EditorHost + `docs`、`doc_index`、`mounted`、`after_pane_focus()`、`focus_explorer()` | YateApp |
| `explorer.py` | （无协议） | 持有 `ExplorerOps`（§4.5） | — |
| `statusbar.py` | `StatusBarHost` | `doc`、`lsp`、`extension_loader`、`mode_label()` | YateApp |
| `modals.py` | `HelpHost` | `keymap_name`、`active_keymap`、`commands` | YateApp |
| `commandline.py` | `PromptHost` | `prompt_completions(text, mode)`、`on_prompt_cancel()` | YateApp |
| `palette.py` | `PaletteHost` | `workspace`、`commands`、`actions`、`open_path_later()`、`focus_editor()`、`execute_action()`、`run_command()`、`ui_refresh()` | YateApp |
| `completion.py` | （无协议） | 删除 `yate` 构造参数（死引用） | — |
| `terminal.py` | （无协议） | 持有 `TerminalOps`（§4.5） | — |
| `manual.py` | （无协议） | 删除 `yate` 构造参数（死引用） | — |

要点：
- `EditorHost.panes` 用**本地** `PaneRegistry` 协议而不是导入 `PaneManager`（避免 `editor ↔ panes` 环，`panes.py:36,417` 已导入 `EditorView`）。
- `PanesHost` 继承 `EditorHost`：因为 `PaneManager` 创建 `EditorView`（`panes.py:417`），其宿主必须同时满足两个协议。
- `editor.py:182` 的 `self.yate.screen_stack` 改用 Textual 自带的 `self.app.screen_stack`（widget 原生属性）。
- `CommandInput` 直接持有 `PromptBar` 引用（构造注入），消除 `commandline.py:99` 经 `app.prompt_bar` 反查父容器的绕行。

### 4.2 `keymaps` / `actions` 层

| 模块 | 协议 | 成员 | 实现者 |
|---|---|---|---|
| `keymaps/base.py` | `ActionHost` | `buffer`、`doc`、`execute_action(name)`、`insert_char(ch)` | YateApp |
| `keymaps/vim.py` | `VimOps(ActionHost)` | 继承 + `message(text, kind)`、`toggle_keymap()`、`command_prompt()`、`find_prompt(forward)`、`goto_prompt()` | YateApp |
| `actions.py` | `SessionOps` | `page()`、`save_document()`、`prompt_open()`、`new_buffer()`、`close_tab()`、`cycle_tab()`、`quit()`、`find_prompt()`、`find_next()`、`replace_prompt()`、`command_prompt()`、`goto_prompt()`、`open_file_palette()`、`open_command_palette()`、`shell_prompt()`、`focus_editor()`、`focus_explorer()`、`toggle_explorer()`、`toggle_keymap()`、`show_manual()`、`show_help()` | YateApp |

要点：
- `ActionContext(host: ActionHost)`；`ctx.app` 更名为 `ctx.host`（语义准确；~40 处机械替换）。
- `populate(registry, ops: SessionOps)`：会话类动作闭包捕获 `ops`，编辑类动作继续用 `ctx.host.buffer/doc`。
- `VimKeymap(ops: VimOps)`：`self._ops` 注入，`vim.py` 内 `app = ctx.app` → `self._ops`；
  `_enter_insert(app)` 改为 `_enter_insert()`。`VscKeymap` 无变化（纯字符串动作）。
- 这样 `ActionContext` 只有 4 个成员，`SessionOps`/`VimOps` 各司其职（ISP）。

### 4.3 `services` / `diagnostics`

| 模块 | 协议 | 成员 | 实现者 |
|---|---|---|---|
| `services/extensions.py` | `ExtensionHost` | `lsp`、`workspace`、`keymaps`、`actions`、`commands`、`buffer`、`doc`、`message()`、`run_shell_command()`、`open_path()`、`save_document()` | YateApp |
| `diagnostics.py` | `DiagnosticsHost` | `config`、`ext_dirs`、`ext_files`、`extension_loader`、`lsp` | YateApp |

要点：
- 前置修复（R5）：`app_features/commands.py` 去掉 `editor_view.theme` 导入，`ExtensionHost` 才能安全引用 `CommandRegistry`。
- `ExtensionAPI.app` 逃生舱口：**保留名字**（扩展生态兼容），类型标注改为 `ExtensionHost`；
  同步更新 4 处文档：`yate/docs/extensions.en.md:175`、`extensions.zh.md:163`、`resources/manual.en.md:1088`、`manual.zh.md:989`。
- `LspExtensionBridge` 只需 `lsp`，可收窄为只接收 `LspManager`（不再收整个 host）。

### 4.4 `app_features/` 层（Feature 类化）

| Feature | 提供的 Ops | 需要的 Host | 注入的服务 |
|---|---|---|---|
| `ExplorerFeature` | `ExplorerOps`（9 成员，见下） | `ExplorerHost` | `Workspace` |
| `TerminalFeature` | `TerminalOps`（`toggle_terminal()`、`open_terminal()`） | `TerminalHost` | — |
| `CompletionController` | （无 Ops，经 `EditorHost` 间接调用） | `CompletionHost` | — |
| `DocsFeature` | （无 Ops，经 `CommandHost` 间接调用） | `DocsHost` | — |
| `CommandFeature` / `register_commands` | `CommandRegistry`（已有） | `CommandHost` | — |

**`ExplorerOps`**（定义在 `app_features/explorer.py`，`ExplorerTree` 持有）：

```python
class ExplorerOps(Protocol):
    """ExplorerTree 使用的 explorer 门面（由 ExplorerFeature 实现）。"""
    @property
    def workspace(self) -> Workspace: ...          # 树构建 / 隐藏文件开关
    def message(self, text: str, kind: str = "info") -> None: ...
    def open_path_later(self, path: Path) -> None: ...
    def focus_editor(self) -> None: ...
    def try_window_prefix(self, event: Key) -> bool: ...
    def prompt_new_file(self, directory: Optional[Path]) -> None: ...
    def prompt_new_dir(self, directory: Optional[Path]) -> None: ...
    def prompt_rename(self, path: Optional[Path]) -> None: ...
    def prompt_delete(self, path: Optional[Path]) -> None: ...
```

**`ExplorerHost`**（`YateApp` 实现，含语义化替换，避免导入 widget）：

```python
class ExplorerHost(Protocol):
    lsp: LspManager
    def message(self, text: str, kind: str = "info") -> None: ...
    def open_document(self, path: Path) -> Optional[Document]: ...      # 原 _open_document_path
    def refresh_explorer(self) -> None: ...                             # 原 explorer_tree.refresh_tree()
    def activate_prompt(self, mode: str, *, placeholder: str = "",
                        initial: str = "") -> bool: ...                 # 原 prompt_bar.activate
    def close_documents_under(self, path: Path) -> int: ...             # 原 explorer.py:135-158
    def retarget_document(self, old: Path, new: Path) -> None: ...     # 原 explorer.py:114-116
    def spawn(self, work: Callable[[], Awaitable[None]], *, group: str,
              exclusive: bool = False, exit_on_error: bool = True) -> None: ...
```

**`TerminalHost`**（语义化面板控制，避免 feature → widget 环）：

```python
class TerminalHost(Protocol):
    @property
    def terminal_height(self) -> int: ...
    @property
    def shell_command(self) -> str: ...
    @property
    def terminal_factory(self) -> Optional[Callable[..., object]]: ...  # 测试注入
    def terminal_cwd(self) -> Path: ...
    def has_terminal_panel(self) -> bool: ...
    def show_terminal_panel(self, height: int) -> None: ...
    def hide_terminal_panel(self) -> None: ...
    def focus_terminal_panel(self) -> None: ...
    def terminal_panel_started(self) -> bool: ...
    async def start_terminal_panel(self, argv: list[str], cwd: Path) -> None: ...
    def message(self, text: str, kind: str = "info") -> None: ...
    def focus_editor(self) -> None: ...
    def spawn(self, ...) -> None: ...
```

**`CompletionHost`**：`completion_popup`、`mounted`、`editor_view`、`doc`、`docs`、`workspace`、`lsp`、
`keymap_name`、`keymaps`、`screen_stack`、`message()`、`ui_refresh()`、`spawn()`（13 成员）。
（`EditorView`/`CompletionPopup` 类型可安全导入，见 R3 例外：这两者不反向依赖 completion feature。）

**`DocsHost`**：`mounted`、`screen`、`push_overlay(screen, callback=None)`（原 `_push_overlay`，建议公开化）。

**`CommandHost(SessionOps)`**：继承动作能力 + `config` 语义化访问（见 R5）、`workspace`、
`open_path_later()`、`new_buffer()`、`show_welcome()`、`set_filetype()`、`select_keymap()`、`set_theme()`、
`theme_label()`、`available_themes()`、`refresh_explorer()`、`toggle_explorer()`、`open_terminal()`、
`close_terminal()`、`show_diagnostics()`、`install_font()`、`terminal_height` 等。

### 4.5 协议全景（20 个，替代 1 个 88 成员协议）

| # | 协议 | 定义位置 | 成员数 | 实现者 |
|---|---|---|---|---|
| 1 | `EditorHost` | `editor_view/editor.py` | 12 | YateApp |
| 2 | `PaneRegistry` | `editor_view/editor.py` | 4 | PaneManager |
| 3 | `PanesHost` | `editor_view/panes.py` | 继承+5 | YateApp |
| 4 | `StatusBarHost` | `editor_view/statusbar.py` | 4 | YateApp |
| 5 | `HelpHost` | `editor_view/modals.py` | 3 | YateApp |
| 6 | `PromptHost` | `editor_view/commandline.py` | 2 | YateApp |
| 7 | `PaletteHost` | `editor_view/palette.py` | 8 | YateApp |
| 8 | `ExplorerOps` | `app_features/explorer.py` | 9 | ExplorerFeature |
| 9 | `ExplorerHost` | `app_features/explorer.py` | 8 | YateApp |
| 10 | `TerminalOps` | `app_features/terminal.py` | 2 | TerminalFeature |
| 11 | `TerminalHost` | `app_features/terminal.py` | 13 | YateApp |
| 12 | `CompletionHost` | `app_features/completion.py` | 13 | YateApp |
| 13 | `DocsHost` | `app_features/docs.py` | 3 | YateApp |
| 14 | `CommandHost` | `app_features/commands.py` | 继承+~20 | YateApp |
| 15 | `ActionHost` | `keymaps/base.py` | 4 | YateApp |
| 16 | `VimOps` | `keymaps/vim.py` | 继承+5 | YateApp |
| 17 | `SessionOps` | `actions.py` | 21 | YateApp |
| 18 | `ExtensionHost` | `services/extensions.py` | 11 | YateApp |
| 19 | `DiagnosticsHost` | `diagnostics.py` | 5 | YateApp |
| 20 | `TaskSpawner`（可复用） | `yate/app_features/_protocols.py`（新，或各 Host 内联） | 1 | YateApp |

> 说明：成员数均为**消费方实际访问集**，不再"预留"。同一成员（如 `message`）在多个协议重复出现是**正确**的——
> 结构化子类型下不需要共享基接口，重复恰好体现各消费者的独立需求。

---

## 5. 实施步骤（每阶段独立可验收）

> 原则：**先定义接口共存、再迁移实现、最后删除**。每个 Stage 结束都要跑门禁（§7.1）。

### Stage 0 — 清理（无行为变化）

| 项 | 位置 | 动作 |
|---|---|---|
| 死方法 | `app.py:1041-1042` `_explorer_prompt_new`、`app.py:1546-1547` `_spawn_terminal` | 删除 |
| 死引用 | `completion.py:92-94`（`CompletionPopup.yate`） | 删除参数，`app.py:1790` 改 `CompletionPopup(id=...)` |
| 死引用 | `manual.py:232-234`（`MarkdownDocScreen.yate`） | 删除参数，`docs.py:30` 调用点同步 |
| 死引用 | `commandline.py:190`（`PromptBar.yate`）、`modals.py:46`（`_OverlayScreen.yate`）、`terminal.py:342`（`TerminalPanel.yate`） | 保留参数（转发需要），删除未用字段；或并入 Stage 1/2 |
| 文档串 | `app_features/__init__.py:4` 等 | 暂不动，Stage 4 统一 |

验证：pyright strict 0 诊断 + pytest（含 `test_changelog_view.py`）+ 冒烟启动。

### Stage 1 — `editor_view` 协议化（AppProtocol 仍在但不再被引用）

按依赖从最容易到最难：

1. `statusbar.py`：定义 `StatusBarHost`，替换注解（`statusbar.py:31`）。
2. `modals.py`：定义 `HelpHost`；`OutputScreen`/`_OverlayScreen` 去 `yate` 参数；`HelpScreen` 显式接收 host。
3. `completion.py`：已完成（Stage 0）。
4. `commandline.py`：定义 `PromptHost`；`PromptBar(host)`、`CommandInput(bar, host)`（消除 `app.prompt_bar` 反查）。
5. `panes.py`：定义 `PanesHost(EditorHost)`；`PaneManager(app: PanesHost, doc)`（`panes.py:74`）。
6. `editor.py`：定义 `EditorHost` + `PaneRegistry`；`EditorView(host: EditorHost, *, leaf_id)`；`screen_stack` 改用 widget 自身。
7. `palette.py`：定义 `PaletteHost`；`PaletteScreen(host, mode)`。
8. `explorer.py`：定义 `ExplorerOps`（放 `app_features/explorer.py`，YateApp 暂时实现）；`ExplorerTree(ops)`。
9. `terminal.py`：定义 `TerminalOps`（放 `app_features/terminal.py`，YateApp 暂时实现）；`TerminalView(ops)`、`TerminalPanel(ops)`。

验证：`grep AppProtocol` 仅剩 `interfaces.py` 自身；pyright/pytest/冒烟全绿。

### Stage 2 — `app_features` 类化（实现迁移）

1. `explorer.py` → `ExplorerFeature(host: ExplorerHost, workspace: Workspace)`，内部持有 `_target`/`_is_dir`（原 `app._explorer_target/_explorer_is_dir`）；把 `apply_delete` 的会话逻辑改调 `host.close_documents_under()`、重命名调 `host.retarget_document()`。
2. `terminal.py` → `TerminalFeature(host: TerminalHost)`，内部持有 `_visible`/`_starting`（原 `app._terminal_visible/_terminal_starting`）。
3. `completion.py` → `CompletionController(host: CompletionHost)`（类已有，改构造参数与访问路径）。
4. `docs.py` → `DocsFeature(host: DocsHost)`。
5. `commands.py` → `register_commands(host: CommandHost)` + 去 `theme` 导入（R5）。
6. `app.py`：
   - 创建 5 个 Feature 实例并注入 widget（`ExplorerTree(self.explorer_feature, ...)` 等）；
   - 删除 18 个转发方法（§1.2 第 4 项）；
   - `on_input_submitted` 分发表（`app.py:1131-1183`）改调 `self.explorer_feature.*`；
   - `_terminal_factory`/`_explorer_target` 等私有状态迁往 Feature（测试注入点同步改）。
7. 测试更新：`test_app_textual.py`（终端 factory 注入）、`test_changelog_view.py`（`_push_overlay` → `push_overlay`）、`test_panes.py`（`FakeApp` 保持 duck typing，`type: ignore` 视 pyright 反馈调整）。

验证：pyright/pytest/冒烟；重点回归 explorer 新建/重命名/删除、终端开关与重启、`:set terminal_height`。

### Stage 3 — `keymaps` / `actions` / `services` / `diagnostics`

1. `keymaps/base.py`：定义 `ActionHost`；`ActionContext(host)`；`ctx.app` → `ctx.host`。
2. `actions.py`：定义 `SessionOps`；`populate(registry, ops)`；会话动作改闭包捕获 `ops`。
3. `keymaps/vim.py`：定义 `VimOps(ActionHost)`；`VimKeymap(ops)`；`ctx.app.*` → `self._ops.*`。
4. `services/extensions.py`：定义 `ExtensionHost`；`ExtensionAPI(host)`；`api.app` 保留名字、类型改 `ExtensionHost`；文档 4 处同步。
5. `diagnostics.py`：定义 `DiagnosticsHost`。

验证：pyright/pytest；扩展加载冒烟（`--ext`、`~/.yate/extensions`）；vim 模式冒烟（i/esc/:/搜索/计数）。

### Stage 4 — 删除 `AppProtocol`（终局）

1. 确认 `grep -rn "AppProtocol" yate/ tests/ tools/` = 0。
2. 删除 `yate/interfaces.py`。
3. 清理文档串/注释中的过时描述（`app_features/__init__.py`、各模块 "Extracted YateApp collaborator" 注释可选更新）。
4. 可选（推荐，非阻塞）：清除 `tests/test_editor_core.py:17-18` 的 `TYPE_CHECKING`（该测试 `from yate.app import YateApp` 只在类型标注用，改为 `Any`/移除或保留；目标 0 处 TYPE_CHECKING）。
5. 可选（推荐）：`config.py:42` 的 `from yate.editor_view import theme` 改为函数内延迟导入（让 `config` 回归叶子，减少 `--diag`/CLI 路径的 UI 包加载）。
6. 可选：`editor_view/__init__.py` 的 eager re-export 改为 PEP 562 惰性 `__getattr__`（降低子模块导入的连带加载；需评估对 `from yate.editor_view import theme` 的影响）。

验证：全量门禁 + 架构测试 + 冒烟 + `python -m yate --diag`。

### Stage 5 — 验证与防回归

1. 新增 `tests/test_architecture.py`（§7.2）。
2. 依赖图脚本/测试确认无环、无禁区导入。
3. 冒烟 8 项场景（§7.3）。
4. 更新 `CHANGELOG.md` / `CHANGELOG.zh.md`（架构重构条目，扩展 API 文档变更说明）。

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 协议成员与 `YateApp` 签名不匹配（pyright strict 报错） | 高（预期内） | 低 | 这是**特性**：编译期强制实现与接口一致；按 pyright 报错逐个修正 |
| 新的模块级导入环（feature ↔ widget） | 中 | 高 | 遵守 R3/R4；每 Stage 后运行架构测试；必要时用语义化 Host 方法替代类型导入 |
| 测试 `FakeApp` 不再满足协议（pyright 检查测试） | 中 | 中 | 测试用 `cast(Any, fake)` 或更新 fake 成员；`test_panes.py` 的 `type: ignore` 已是现状 |
| 行为回归（终端/explorer 提示流状态迁移） | 中 | 中 | Stage 2 前先补 2~3 个针对 `ExplorerFeature`/`TerminalFeature` 的单元测试（用 fake host），再迁移 |
| 扩展 API 兼容（`api.app`） | 低 | 中 | 保留名字；文档同步说明类型；CHANGELOG 记录 |
| 深层解耦（`doc_index` 写、`docs` 替换）迁移影响面大 | 中 | 中 | Stage 2 用语义化 Host 方法封装；`EditorSession` 抽取放附录 D（可选，不进主线） |
| 性能回退 | 低 | 低 | 协议零运行时开销；删除转发层反而缩短链路；不引入总线/额外对象 |

---

## 7. 验证

### 7.1 每阶段门禁

```powershell
python -m pyright yate/ tests/ tools/     # 期望 0 error / 0 warning
python -m pytest tests/ -q                # 期望全绿
python -m yate --diag                     # 期望正常输出报告
python -m yate --version                  # CLI 冒烟
```

静态检查（目标态）：

```powershell
Select-String -Path yate\**\*.py -Pattern "AppProtocol"    # 期望 0
Select-String -Path yate\**\*.py -Pattern "TYPE_CHECKING"  # 期望 0
Select-String -Path yate\**\*.py -Pattern "from yate\.app|import yate\.app"  # 期望仅 cli.py
```

### 7.2 新增架构测试（草案：`tests/test_architecture.py`）

```python
"""Architecture guards: interfaces must stay local and acyclic."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "yate"
APP_IMPORTERS_ALLOWED = {"cli.py"}


def _modules() -> list[Path]:
    return [p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts]


def test_no_app_protocol() -> None:
    for p in _modules():
        assert "AppProtocol" not in p.read_text(encoding="utf-8"), p


def test_no_type_checking() -> None:
    for p in _modules():
        assert "TYPE_CHECKING" not in p.read_text(encoding="utf-8"), p


def test_only_cli_imports_app() -> None:
    for p in _modules():
        if p.name in APP_IMPORTERS_ALLOWED or p.name == "app.py":
            continue
        src = p.read_text(encoding="utf-8")
        assert "from yate.app import" not in src and "import yate.app" not in src, p


def test_feature_modules_do_not_import_widgets() -> None:
    """app_features 不得导入 editor_view 的 widget（R3）。"""
    widgets = {
        "editor", "explorer", "panes", "terminal",
        "statusbar", "commandline", "modals", "palette",
    }
    features = ROOT / "app_features"
    for p in features.rglob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("yate.editor_view"):
                    leaf = node.module.split(".")[-1]
                    assert leaf not in widgets, (p, node.module)
```

可选进阶：AST 构建 `yate.*` 模块依赖图做 DFS 环检测（把包 `__init__` 视作节点，允许已知的
`editor_view/__init__ → widgets` 边），检测到环即失败。

### 7.3 人工冒烟清单（Stage 5）

1. 启动空 buffer、`yate <file>`、`yate <dir>`。
2. explorer：`a` 新建文件、`A` 新建目录、`r` 重命名、`d` 删除（验证 tab 清理 + LSP didClose）。
3. 终端：`` Ctrl+` `` 开关、shell 退出后按键重启、`:set terminal_height=20`。
4. 补全：Ctrl+Space 手动触发、输入触发、Esc 关闭。
5. vim 模式：`i`/`Esc`/`:`/`/`/`Ctrl+w` 窗口前缀。
6. 命令：`:w`、`:q`、`:set theme=...`、`:theme`、`:files`、`:diagnostics`。
7. 扩展：`yate --ext ...`、`~/.yate/extensions` 自动加载（验证 `api.app` 可用）。
8. `yate --diag` / `--version` / `--changelog zh`。

---

## 8. 实施顺序总览

```
Stage 0 清理死代码/死引用 ──────────────────┐
Stage 1 editor_view 协议化（9 文件）────────┤ 每阶段：pyright + pytest + 冒烟
Stage 2 app_features 类化 + app.py 瘦身 ────┤
Stage 3 keymaps/actions/services/diagnostics┤
Stage 4 删除 AppProtocol / interfaces.py ───┘
Stage 5 架构测试 + 冒烟 + CHANGELOG
```

**提交建议**：每个 Stage 一个（或数个）独立 commit，信息遵循现有风格；
Stage 2 的 explorer/terminal 可拆两个 commit，便于 `git bisect`。

---

## 附录

### A. 死代码 / 死引用清单（全部删除）

| 位置 | 内容 | 处理 |
|---|---|---|
| `app.py:1041-1042` | `_explorer_prompt_new`（无调用者） | 删除 |
| `app.py:1546-1547` | `_spawn_terminal`（无调用者） | 删除 |
| `editor_view/completion.py:92-94` | `CompletionPopup.yate`（赋值后从未使用） | 删参数 + 调用点 |
| `editor_view/manual.py:232-234` | `MarkdownDocScreen.yate`（从未使用） | 删参数 + `docs.py:30` |
| `editor_view/commandline.py:190` | `PromptBar.yate`（从未使用；参数仍需转发） | 删除字段 |
| `editor_view/modals.py:46` | `_OverlayScreen.yate`（从未使用） | Stage 1 随 `HelpHost` 改造删除 |
| `editor_view/terminal.py:342` | `TerminalPanel.yate`（从未使用；参数需传给 view） | Stage 2 参数改名为 ops 注入 |

### B. 测试影响清单

| 测试 | 影响 | 动作 |
|---|---|---|
| `tests/test_panes.py:26` `FakeApp` | `PanesHost` 结构匹配 | 保留 duck typing；按 pyright 调整 `type: ignore` |
| `tests/test_changelog_view.py:31` `_FakeApp` | `DocsHost.push_overlay` 改名 | 同步方法名 |
| `tests/test_app_textual.py:2425` | `_terminal_factory` 注入点 | 改为 `app.terminal_feature` 或 host getter |
| `tests/test_extensions.py:16` `_FakeApp` | `ExtensionAPI(host)` 构造 | `cast(Any, ...)` 现状可保留 |
| `tests/test_diagnostics.py:25` `_build_app` | 真实 `YateApp`，无影响 | 观察 `DiagnosticsHost` 是否引入导入变化 |
| `tests/test_editor_core.py:17-18` | `TYPE_CHECKING` 导入 `YateApp` | Stage 4 清理 |

### C. 文档更新清单

- `yate/docs/extensions.en.md:175`、`yate/docs/extensions.zh.md:163`：`api.app` 类型说明（`YateApp` → 扩展宿主接口）。
- `yate/resources/manual.en.md:1088`、`yate/resources/manual.zh.md:989`：同步。
- `CHANGELOG.md` / `CHANGELOG.zh.md`：新增"架构重构：拆分并移除 AppProtocol"条目。
- `yate/app_features/__init__.py` 文档串（`:4` 提到 YateApp）与各模块 "Extracted from YateApp" 注释：Stage 4 更新表述。

### D. 后续可选深化（不在本计划主线上）

1. **`EditorSession`**（`yate/services/session.py`）：抽出 `docs/doc_index/search` 与会话操作，
   让 `YateApp` 只做组合根；`ExplorerHost` 的 `close_documents_under`/`retarget_document` 移入。
2. **`editor_view/__init__.py` 惰性化**：PEP 562 `__getattr__` 按需导出 widget，减少连带加载。
3. **`config.py` 解耦 `editor_view.theme`**（延迟导入或把 theme 移到独立包）：让 `config` 完全叶子化。
4. **`run_worker` 类型收敛**：`TaskSpawner` 原语替代各模块直接使用 Textual worker 类型。
5. **扩展 API 的 `api.app` 最终退场**：如未来允许破坏性变更，改为细分访问器（`api.buffer/doc/...`），删除万能门面。
