# 移除 TYPE_CHECKING 循环依赖重构（合并文档）

> 本文件由以下 4 份历史文档合并整理而成（原文件已删除）：
>
> | 原文档 | 内容 | 时间 |
> | --- | --- | --- |
> | `remove_type_checking_plan.md` | 重构主计划 v2（Protocol 依赖反转） | 2026-09-18 |
> | `remove_type_checking_review_v2.md` | PR 评审 v2 | 2026-09-18 14:48 |
> | `remove_type_checking_review_v3.md` | PR 评审 v3 | 2026-09-18 19:51 |
> | `remove_type_checking_v3_plan.md` | v3 精化计划（消除 `Any`） | 2026-09-22 |
>
> ---
>
> **状态：历史方案，已被后续重构取代（2026-09-22）。**
>
> 本方案的直接目标（移除 `TYPE_CHECKING`）已达成，但中间产物
> `yate/interfaces.py`（`AppProtocol`）与 `app_features/*` 已在紧随其后的
> 「分层重构」中**整体删除**。当前架构不使用任何 `Protocol`：共享状态改为
> **具体对象**（`EditorSession` / `KeymapSet` / `ActionRegistry` /
> `CommandRegistry`），操作逻辑上移到 `yate/editor.py`（`Editor`）。
>
> **当前权威架构定义请以 [app-layering-refactoring-plans/README.md](app-layering-refactoring-plans/README.md)
> 与 [`.trae/rules/architecture-boundaries.md`](../rules/architecture-boundaries.md) 为准**；
> 本文档保留作为架构决策记录（ADR），正文描述的是**历史实现**，请勿与当前代码对照。

**阅读导航**

- §1 问题分析｜§2 解决方案｜§3 实施步骤 —— 来自原主计划 v2
- §4 消除 `Any` 的精化计划 —— 来自原 v3 精化计划
- §5 两轮 PR 评审记录与最终处置 —— 来自原 v2 / v3 评审
- §6 验证方案｜§7 风险分析｜§8 后续演进方向

---

## 1. 问题分析

### 1.1 循环依赖地图

```
yate.app (组合根)
├── from yate.keymaps.base   import Keymap, ActionContext
├── from yate.keymaps.vim    import VimKeymap, VimMode
├── from yate.services.extensions import ExtensionAPI, ExtensionLoader
├── from yate.editor_view.editor   import EditorView
├── from yate.editor_view.panes    import Leaf, PaneManager
├── from yate.editor_view.*        import 8 个 Widget
├── from yate.app_features.*       import 5 个功能模块
└── from yate.diagnostics          import (仅函数签名引用)

所有 ← 方向通过 `if TYPE_CHECKING:` 反向导入 YateApp
```

### 1.2 完整 TYPE_CHECKING 文件清单

| # | 文件 | TYPE_CHECKING 导入 | `__future__ annotations` | 运行时使用？ |
| --- | --- | --- | --- | --- |
| 1 | `keymaps/base.py` | `YateApp` | ✅ | ❌ 仅注解 `ActionContext.__init__(app: "YateApp")` |
| 2 | `keymaps/vim.py` | `YateApp`, `TextBuffer` | ✅ | ❌ 仅注解 `_enter_insert(app: YateApp)` |
| 3 | `services/extensions.py` | `YateApp`, `Keymap` | ✅ | ❌ 仅注解 `ExtensionAPI.__init__(app: "YateApp")` |
| 4 | `editor_view/editor.py` | `YateApp`, `Document`, `Leaf` | ✅ | ❌ 仅注解 `EditorView.__init__(app: YateApp)` + `leaf(self) -> Leaf` |
| 5 | `editor_view/panes.py` | `YateApp`, `EditorView` | ✅ | ❌ 仅注解 `PaneManager.__init__(app: "YateApp")` + `"EditorView"` 字符串注解 |
| 6 | `editor_view/explorer.py` | `YateApp` | ✅ | ❌ 仅注解 `__init__(self, yate: YateApp, ...)` |
| 7 | `editor_view/palette.py` | `YateApp` | ✅ | ❌ 仅注解 |
| 8 | `editor_view/commandline.py` | `YateApp` | ✅ | ❌ 仅注解 |
| 9 | `editor_view/statusbar.py` | `YateApp` | ✅ | ❌ 仅注解 |
| 10 | `editor_view/modals.py` | `YateApp` | ✅ | ❌ 仅注解 |
| 11 | `editor_view/completion.py` | `YateApp`, `TextBuffer` | ✅ | ❌ 仅注解 |
| 12 | `editor_view/terminal.py` | `YateApp` | ✅ | ❌ 仅注解 |
| 13 | `app_features/commands.py` | `YateApp` | ✅ | ❌ 仅注解 `register_commands(app: "YateApp")` |
| 14 | `app_features/completion.py` | `YateApp` | ✅ | ❌ 仅注解 `CompletionController.__init__(app: "YateApp")` |
| 15 | `app_features/docs.py` | `YateApp` | ✅ | ❌ 仅注解 |
| 16 | `app_features/explorer.py` | `YateApp` | ✅ | ❌ 仅注解 |
| 17 | `app_features/terminal.py` | `YateApp` | ✅ | ❌ 仅注解 |
| 18 | `diagnostics.py` | `YateApp` | ✅ | ❌ 仅注解 |
| 19 | `extensions/python_lsp.py` | `ExtensionAPI` | ✅ | ❌ 仅注解 |

**关键结论**：

- 全部 **19 个文件** 已有 `from __future__ import annotations`
- TYPE_CHECKING 导入**仅用于类型注解**（无 `isinstance`、无运行时引用）
- 问题**纯粹在类型层面**，运行时已安全

### 1.3 `editor_view` 内部循环（已部分处理）

```
panes.py ←TYPE_CHECKING→ EditorView (editor.py)
editor.py ←TYPE_CHECKING→ Leaf (panes.py)
```

- `panes.py` 已用**字符串注解** `"EditorView"` + **函数体内延迟导入**（`PaneHost._build()` 内 `from yate.editor_view.editor import EditorView`）
- `editor.py` 中 `Leaf` 用于返回类型注解 `def leaf(self) -> Leaf:`，运行时**不直接依赖** panes 模块（通过 `self.yate.panes` 获取）
- **这两个 TYPE_CHECKING 块可以一并移除**（配合 `from __future__ import annotations`）

---

## 2. 解决方案：Protocol 依赖反转

创建 `yate/interfaces.py`，用 `typing.Protocol` 定义接口。所有下层模块将 `YateApp` 注解替换为 `AppProtocol`。

```
重构后依赖方向（无循环）:

yate.interfaces (纯抽象层，仅依赖 editor_core + editor_lsp + editor_syntax)
    ↑ 被引用
    ├── yate.keymaps.*            ← AppProtocol
    ├── yate.services.extensions  ← AppProtocol
    ├── yate.editor_view.*        ← AppProtocol
    ├── yate.app_features.*       ← AppProtocol
    └── yate.diagnostics          ← AppProtocol

yate.app (具体实现，依赖所有下层模块)
    └── YateApp 自动满足 AppProtocol (结构化子类型)
```

### 2.1 为什么 Protocol 方案最优

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| **Protocol 依赖反转** | 符合依赖倒置原则；不影响运行时；IDE/pyright 完美支持 | `AppProtocol` 枚举成员需要完整审计 |
| 直接运行时导入 | 简单 | 破坏加载顺序，`yate.app` 还没初始化完下层模块就尝试导入 → `ImportError` |
| 函数体内延迟导入 | 绕过循环 | 类型注解需要额外处理（不能用在函数签名上）；类型检查器支持差 |

### 2.2 `editor_view` 内部循环处理

`editor_view` 包内部的循环已正确处理（字符串注解 + 函数体内延迟导入）。移除 TYPE_CHECKING 后，配合 `from __future__ import annotations`，所有类型引用变为字符串，pyright 可以通过以下方式解析：

- 同包内的简单名称（`Leaf`、`EditorView`）→ pyright 会在包内查找
- 函数体内的运行时导入（已存在）→ 保证实际运行时可用

### 2.3 `AppProtocol` 成员清单（精确审计结果）

```python
class AppProtocol(Protocol):
    # === 来自 editor_core ===
    buffer: TextBuffer              # keymaps/base, services/extensions, editor/editor
    doc: Document                   # 几乎所有模块
    docs: list[Document]            # app_features/explorer, app_features/completion, editor/panes
    doc_index: int                  # editor/panes, app_features/explorer

    # === 来自 config ===
    config: YateConfig              # app_features/terminal, diagnostics

    # === 来自 services ===
    workspace: Workspace            # services/extensions, editor/explorer, app_features/completion
    keymaps: dict[str, Keymap]      # services/extensions, app_features/completion
    keymap_name: str                # editor/editor
    lsp: LspManager                 # services/extensions, editor/editor, diagnostics
    search: SearchEngine            # editor/editor, app_features/explorer
    actions: ActionRegistry         # services/extensions
    commands: CommandRegistry       # services/extensions
    extension_loader: ExtensionLoader  # diagnostics
    completion_popup: Optional[CompletionPopup]  # editor/editor, app_features/completion

    # === 来自 app_features ===
    mounted: bool                   # panes, app_features/completion, app_features/docs
    welcome_visible: bool           # editor/editor

    # === 来自 editor_view Widget 指针 ===
    panes: Optional[PaneManager]    # editor/editor
    prompt_bar: Optional[PromptBar] # commandline, app_features/explorer
    editor_view: Optional[EditorView]  # app_features/completion
    explorer_tree: Optional[ExplorerTree]  # app_features/explorer
    terminal_panel: Optional[TerminalPanel]  # app_features/terminal

    # === 私有/内部属性（app_features 访问）===
    _terminal_visible: bool
    _terminal_starting: bool
    _terminal_factory: Optional[Callable[..., Any]]
    _explorer_target: Optional[Path]
    _explorer_is_dir: bool
    ext_dirs: list[Path]            # diagnostics
    ext_files: list[Path]           # diagnostics

    # === 来自 Textual App 继承 ===
    screen_stack: list[Any]         # editor/editor, app_features/completion
    screen: Any                     # app_features/docs

    # === 方法 ===
    def execute_action(self, name: str) -> None: ...
    def insert_char(self, ch: str) -> None: ...
    def page(self, direction: int, half: bool = False) -> None: ...
    def handle_raw_key(self, raw: str) -> bool: ...
    def try_window_prefix(self, event: Any) -> bool: ...
    def toggle_terminal(self) -> None: ...
    def open_terminal(self) -> None: ...
    def message(self, text: str, kind: str = "info") -> None: ...
    def focus_editor(self) -> None: ...
    def focus_explorer(self) -> None: ...
    def open_path(self, path: Path) -> None: ...
    def open_path_later(self, path: Path) -> None: ...
    def save_document(self) -> None: ...
    def run_command(self, name: str) -> None: ...
    def ui_refresh(self) -> None: ...
    def after_pane_focus(self) -> None: ...
    def request_completion(self, manual: bool = False) -> None: ...
    def accept_completion(self) -> None: ...
    def run_worker(self, coro: Any, **kwargs: Any) -> Any: ...
    def prompt_completions(self, text: str, mode: str) -> list[str]: ...
    def on_prompt_cancel(self) -> None: ...

    # === app_features/explorer 调用 ===
    def explorer_new_file_prompt(self, dir: Optional[Path]) -> None: ...
    def explorer_new_dir_prompt(self, dir: Optional[Path]) -> None: ...
    def explorer_rename_prompt(self, path: Optional[Path]) -> None: ...
    def explorer_delete_prompt(self, path: Optional[Path]) -> None: ...
    def new_buffer(self, show: bool = True) -> None: ...
    def _open_document_path(self, path: Path, *, target_leaf: Optional[Any] = None) -> Optional[Document]: ...

    # === app_features/docs 调用 ===
    def _push_overlay(self, screen: Any) -> None: ...

    # === services/extensions 调用 ===
    def run_shell_command(self, command: str, show_output: bool = True) -> Any: ...
```

**`interfaces.py` 导入声明**（顶层）：

```python
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, Union

# 只导入不会导致循环的底层模块
from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
from yate.editor_core.search import SearchEngine
from yate.editor_lsp import LspManager
```

**重要说明**：

- `Keymap`、`Workspace`、`YateConfig`、`PaneManager` 等类型**不要直接导入**（可能引发循环），用 `Any` 或在 Protocol 方法签名中用字符串前向引用
- 如果某个类型确实需要，可以在 `interfaces.py` 内部延迟导入（函数体内）或用 TYPE_CHECKING 只对 `interfaces.py` 自身使用
- 第一版因上述顾虑大量使用 `Any`（见 §4）

---

## 3. 实施步骤（依赖顺序，自底向上）

```
Step 1: interfaces.py         ← 无依赖，最先创建
   ↓
Step 2: keymaps/*             ← 最底层业务逻辑
   ↓
Step 3: services/extensions   ← 依赖 keymaps
   ↓
Step 4: editor_view/*         ← 依赖 keymaps + services
   ↓
Step 5: app_features/*        ← 已抽离但仍引用 YateApp
   ↓
Step 6: diagnostics.py
   ↓
Step 7: extensions/python_lsp
   ↓
Step 8: yate/app.py (可选显式继承)
```

每完成一步，运行 `python -c "import yate.app"` 验证导入链正常。

### 步骤 1：创建 `yate/interfaces.py`

**文件**：`yate/interfaces.py`（新建）

**设计原则**：

- 零依赖 `yate.app` 或任何导入 `yate.app` 的模块
- 只导入底层包：`typing`、`pathlib`、`yate.editor_core.*`、`yate.editor_lsp.*`、`yate.editor_syntax.*`
- 对 Textual 继承的方法（`run_worker`、`screen_stack`、`_push_overlay`）用 `Any` 或最小 Protocol
- 对私有属性（`_terminal_visible`、`_explorer_target`）如果下层模块确实访问了，也纳入 Protocol

成员清单见 §2.3。

### 步骤 2：修改 `yate/keymaps/base.py`

**当前 TYPE_CHECKING 块**：

```python
from typing import TYPE_CHECKING, Callable, Optional, Union

if TYPE_CHECKING:
    from yate.app import YateApp
```

**修改为**：

```python
from typing import Callable, Optional, Union
from yate.interfaces import AppProtocol
```

**需要改注解的位置**：

- `ActionContext.__init__(self, app: "YateApp")` → `ActionContext.__init__(self, app: AppProtocol)`

### 步骤 3：修改 `yate/keymaps/vim.py`

**当前 TYPE_CHECKING 块**：

```python
if TYPE_CHECKING:
    from yate.app import YateApp
    from yate.editor_core.buffer import TextBuffer
```

**修改为**：

```python
from yate.interfaces import AppProtocol
# TextBuffer 已经直接从 yate.editor_core.buffer 导入（非循环依赖）
```

**需要改注解**：

- `_enter_insert(self, app: YateApp)` → `_enter_insert(self, app: AppProtocol)`

### 步骤 4：修改 `yate/services/extensions.py`

**当前 TYPE_CHECKING 块**：

```python
if TYPE_CHECKING:
    from yate.app import YateApp
    from yate.keymaps.base import Keymap
```

**修改为**：

```python
from yate.interfaces import AppProtocol
from yate.keymaps.base import Keymap  # 直接运行时导入（keymaps.base 不再循环）
```

**需要改注解**：所有 `"YateApp"` → `AppProtocol`

### 步骤 5：修改 `yate/editor_view/*.py`（9 个文件）

**通用模板**：

```python
# 之前
from typing import TYPE_CHECKING, ...
if TYPE_CHECKING:
    from yate.app import YateApp
    from ... # 其他

# 之后
from typing import ...  # 移除 TYPE_CHECKING
from yate.interfaces import AppProtocol
```

**各文件具体修改**：

| 文件 | TYPE_CHECKING 导入 | 修改注解 |
| --- | --- | --- |
| `editor_view/editor.py` | `YateApp`, `Document`, `Leaf` | `YateApp`→`AppProtocol`；`Document` 直接导入；`Leaf` 保留字符串（`from __future__ import annotations`） |
| `editor_view/panes.py` | `YateApp`, `EditorView` | `YateApp`→`AppProtocol`；`EditorView` 保持字符串注解（函数体内延迟导入已处理） |
| `editor_view/explorer.py` | `YateApp` | → `AppProtocol` |
| `editor_view/palette.py` | `YateApp` | → `AppProtocol` |
| `editor_view/commandline.py` | `YateApp` | → `AppProtocol` |
| `editor_view/statusbar.py` | `YateApp` | → `AppProtocol` |
| `editor_view/modals.py` | `YateApp` | → `AppProtocol` |
| `editor_view/completion.py` | `YateApp`, `TextBuffer` | `YateApp`→`AppProtocol`；`TextBuffer` 直接导入 |
| `editor_view/terminal.py` | `YateApp` | → `AppProtocol` |

### 步骤 6：修改 `yate/app_features/*.py`（5 个文件）

| 文件 | 修改注解 |
| --- | --- |
| `app_features/commands.py` | `"YateApp"` → `AppProtocol` |
| `app_features/completion.py` | `"YateApp"` → `AppProtocol` |
| `app_features/docs.py` | `"YateApp"` → `AppProtocol` |
| `app_features/explorer.py` | `"YateApp"` → `AppProtocol` |
| `app_features/terminal.py` | `"YateApp"` → `AppProtocol` |

### 步骤 7：修改 `yate/diagnostics.py`

移除 TYPE_CHECKING 块，导入 `AppProtocol`，将 `"YateApp"` 改为 `AppProtocol`。

### 步骤 8：修改 `yate/extensions/python_lsp.py`

移除 TYPE_CHECKING 的 `ExtensionAPI` 导入，改为直接运行时导入（`services.extensions` 此时已完成修改，不再循环）：

```python
from yate.services.extensions import ExtensionAPI
```

### 步骤 9：可选 — 让 `YateApp` 显式继承 `AppProtocol`

```python
# yate/app.py
from yate.interfaces import AppProtocol

class YateApp(App[None], AppProtocol):
    ...
```

这不是必须的（Protocol 是结构化子类型），但显式继承可以：

- 让 IDE 在 `YateApp` 类定义时就检查是否满足 Protocol
- 为 Protocol 成员提供更好的 "Go to Definition" 体验

---

## 4. 精化计划 v3：消除 `interfaces.py` 中的 `Any`

> 来源：`remove_type_checking_v3_plan.md`。
> 前置：`b4a354f` 引入 `AppProtocol` 后，为了让 `interfaces.py` 保持叶子层，许多成员被写成
> `Any` + 注释真名（如 `workspace: Any  # Workspace`）。本节把能安全替换的换成具体类型，
> 不能的直接导入的换成精确前向引用。

### 4.1 完整 `Any` 审计清单

| # | 位置 | 当前类型 | 目标类型 | 安全性 |
| --- | --- | --- | --- | --- |
| 1 | `workspace` | `Any` | `Workspace` | ✅ direct |
| 2 | `keymaps: dict[str, ...]` | `Any` | `Keymap` | ⚠️ forward |
| 3 | `actions` | `Any` | `ActionRegistry` | ⚠️ forward |
| 4 | `commands` | `Any` | `CommandRegistry` | ⚠️ forward |
| 5 | `extension_loader` | `Any` | `ExtensionLoader` | ⚠️ forward |
| 6 | `active_keymap` (property) | `Any` | `Keymap` | ⚠️ forward |
| 7 | `config` | `Any` | `YateConfig` | ✅ direct |
| 8 | `completion_popup` | `Optional[Any]` | `Optional[CompletionPopup]` | ⚠️ forward |
| 9 | `prompt_bar` | `Optional[Any]` | `Optional[PromptBar]` | ⚠️ forward |
| 10 | `panes` | `Optional[Any]` | `Optional[PaneManager]` | ⚠️ forward |
| 11 | `editor_view` | `Optional[Any]` | `Optional[EditorView]` | ⚠️ forward |
| 12 | `explorer_tree` | `Optional[Any]` | `Optional[ExplorerTree]` | ⚠️ forward |
| 13 | `terminal_panel` | `Optional[Any]` | `Optional[TerminalPanel]` | ⚠️ forward |
| 14 | `screen_stack` (property) | `list[Any]` | **保持 `list[Any]`** | Textual |
| 15 | `screen` (property) | `Any` | **保持 `Any`** | Textual |
| 16 | `_terminal_factory` | `Optional[Callable[..., Any]]` | **保持** | callback |
| 17 | `_open_document_path(..., target_leaf)` | `Optional[Any]` | `Optional[Leaf]` | ✅ direct |
| 18 | `try_window_prefix(event)` | `Any` | **保持 `Any`** | Textual |
| 19 | `run_worker(work, ...) -> Any` | `Any` | **保持 `Any`** | Textual |
| 20 | `_push_overlay(screen)` | `Any` | **保持 `Any`** | Textual |
| 21 | `_split_with_path(axis, ...)` | `Any` | `Axis` | ✅ direct |
| 22 | `run_shell_command(...) -> Any` | `Any` | `ShellResult` | ✅ direct |

**小结**：**5** 处可安全直接替换；**9** 处需前向引用；**8** 处有意保留 `Any`（Textual 内部或不透明回调）。

### 4.2 为什么某些导入不安全

```
interfaces.py  ←──  keymaps/base.py  (imports AppProtocol)
     ↑                                        ↑
     └──── would cause cycle if we import ────┘
              Keymap at runtime
```

`editor_view` / `app_features` / `services` 层的每个模块现在都为类型注解导入 `AppProtocol`。
如果 `interfaces.py` 在**运行时**反向导入它们，Python 会在任一模块完成初始化前撞上导入循环。
解决办法是 `TYPE_CHECKING`：静态分析器看得到导入，运行时解释器跳过；配合
`from __future__ import annotations`（注解字符串化），前向引用在运行时安全，同时对 pyright 精确。

**这与旧的 TYPE_CHECKING 模式有本质区别**：旧模式是*下游*模块反向导入*组合根*
（`yate.app.YateApp`），方向违背依赖结构；此处 `interfaces.py` 只用 `TYPE_CHECKING`
命名实现了该 Protocol 的**具体类**，运行时不导入任何依赖自己的东西 —— 这是对
`TYPE_CHECKING` 的正当使用，不是修补坏架构的权宜之计。

### 4.3 安全 / 不安全导入验证

**可直接导入（零内部依赖）**：

| 目标 | 模块 | 内部导入 | 循环风险 |
| --- | --- | --- | --- |
| `Workspace` | `yate.services.workspace` | `fnmatch, dataclasses, pathlib, typing` | None |
| `ShellResult` | `yate.services.shell` | `subprocess, sys, dataclasses, pathlib, typing` | None |
| `YateConfig` | `yate.config` | `dataclasses, pathlib, typing, yate.editor_view.theme` | theme 仅导入 `editor_syntax.tokens` → None |
| `Axis` | `yate.editor_view.pane_types` | `dataclasses, typing, yate.editor_core.*` | None |
| `Leaf` | `yate.editor_view.pane_types` | 同上 | None |

**仅可前向引用（运行时会成环）**：

| 目标 | 模块 | 反向导入 | 成环原因 |
| --- | --- | --- | --- |
| `Keymap` | `yate.keymaps.base` | `from yate.interfaces import AppProtocol` | direct |
| `ActionRegistry` | `yate.actions` | 导入 `keymaps.base.ActionContext` → keymaps.base 导入 interfaces | indirect |
| `CommandRegistry` | `yate.app_features.commands` | `from yate.interfaces import AppProtocol` | direct |
| `ExtensionLoader` | `yate.services.extensions` | `from yate.interfaces import AppProtocol` | direct |
| `CompletionPopup` | `yate.editor_view.completion` | `from yate.interfaces import AppProtocol` | direct |
| `PromptBar` | `yate.editor_view.commandline` | `from yate.interfaces import AppProtocol` | direct |
| `EditorView` | `yate.editor_view.editor` | `from yate.interfaces import AppProtocol` | direct |
| `ExplorerTree` | `yate.editor_view.explorer` | `from yate.interfaces import AppProtocol` | direct |
| `PaneManager` | `yate.editor_view.panes` | 导入 `editor` → editor 导入 interfaces | indirect |
| `TerminalPanel` | `yate.editor_view.terminal` | `from yate.interfaces import AppProtocol` | direct |

### 4.4 实施步骤

**Step 1 — 在 `interfaces.py` 加直接安全导入**

```python
# New top-level imports (no cycle risk)
from yate.config import YateConfig
from yate.editor_view.pane_types import Axis, Leaf
from yate.services.shell import ShellResult
from yate.services.workspace import Workspace
```

更新成员：

```python
workspace: Workspace
config: YateConfig
_split_with_path(self, axis: Axis, args: str) -> None: ...
_open_document_path(
    self, path: Path, *, target_leaf: Optional[Leaf] = None
) -> Optional[Document]: ...
run_shell_command(
    self, command: str, show_output: bool = True
) -> ShellResult: ...
```

**Step 2 — 加 TYPE_CHECKING 块做前向引用**

```python
from typing import Any, Callable, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from yate.actions import ActionRegistry
    from yate.app_features.commands import CommandRegistry
    from yate.editor_view.commandline import PromptBar
    from yate.editor_view.completion import CompletionPopup
    from yate.editor_view.editor import EditorView
    from yate.editor_view.explorer import ExplorerTree
    from yate.editor_view.panes import PaneManager
    from yate.editor_view.terminal import TerminalPanel
    from yate.keymaps.base import Keymap
    from yate.services.extensions import ExtensionLoader
```

更新成员（借助 `from __future__ import annotations` 自动字符串化）：

```python
keymaps: dict[str, Keymap]
actions: ActionRegistry
commands: CommandRegistry
extension_loader: ExtensionLoader

@property
def active_keymap(self) -> Keymap: ...

completion_popup: Optional[CompletionPopup]
prompt_bar: Optional[PromptBar]
panes: Optional[PaneManager]
editor_view: Optional[EditorView]
explorer_tree: Optional[ExplorerTree]
terminal_panel: Optional[TerminalPanel]
```

**Step 3 — 删除冗余注释**：替换后 `# yate.services.workspace.Workspace` 之类注释应移除。

**Step 4 — 更新模块 docstring**，改为反映"两类策略"：

```python
"""...

This module uses two strategies for type precision:

1. **Direct top-level imports** for types that live in truly leaf-level
   packages (``Workspace``, ``YateConfig``, ``Axis``, ``Leaf``,
   ``ShellResult``).  These create no cycle.

2. **TYPE_CHECKING + string forward refs** for types whose module imports
   ``AppProtocol`` back (``Keymap``, ``ActionRegistry``, ``CommandRegistry``,
   all editor_view widgets).  The imports are resolved at static-analysis
   time only, so no runtime cycle occurs.

Textual framework internals (``screen``, ``run_worker``, ``_push_overlay``)
remain ``Any`` because their concrete types are defined in the third-party
library and are out of this project's control.
"""
```

**Step 5 — 验证**

```bash
python -c "from yate.interfaces import AppProtocol; print('interfaces OK')"
python -c "from yate.app import YateApp; print('YateApp OK')"
python -m pyright yate/ tests/    # expect 0 errors, 0 warnings
python -m pytest tests/ -q        # expect all pass
python -m yate --help             # expect normal CLI
```

### 4.5 附带修复：`completion.py::accept()` 行范围判定

```python
# Before (semantically obscure — "row != r0 or row != r1" means
# "row is not simultaneously equal to both", which is always true when
# r0 != r1)
if row != r0 or row != r1:
    return

# After (semantically clear — "cursor left the completion row range")
if row < r0 or row > r1:
    return
```

当前补全项均为单行（`r0 == r1`），两种写法实践效果相同；新写法语义无歧义，且正确处理
假想的多行场景。**该项与 §5.1 评审 v2 的阻断项为同一处缺陷**，此处重复出现是因为它同时被
纳入了 v3 精化计划。

### 4.6 执行注意事项

1. **不要给 `AppProtocol` 加 `@runtime_checkable`**：会强制运行时逐一求值成员，把
   TYPE_CHECKING 导入拉进来，重新触发我们刚避开的循环。pyright 的结构化子类型检查无需运行时支持。
2. **保留 `interfaces.py` 顶部的 `from __future__ import annotations`**：这是字符串前向引用
   工作的前提，删除会立刻 `ImportError`。
3. **增量验证 TYPE_CHECKING 导入块**：每加一批就跑
   `python -c "from yate.app import YateApp"` 尽早发现成环。部分模块（如 `PaneManager`）
   是经 `EditorView` 间接到达的，环不明显。
4. **一个逻辑步骤一个提交**：Step 1-2 与 Step 5（completion 修复）互相独立，分开有助于 `git bisect`。

---

## 5. 两轮 PR 评审记录

### 5.1 评审 v2（2026-09-18 14:48）

| 评审规则 | 评审内容 | 结论 | 完成时间 |
| --- | --- | --- | --- |
| 功能性与逻辑 | 代码是否按预期执行？有无逻辑错误或未处理的边缘情况？ | ❌ 未通过 | 2026-09-18 14:48:25 |
| 安全性 | 是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？ | ✅ 通过 | 2026-09-18 14:48:25 |
| 性能 | 是否有明显的性能瓶颈（如循环嵌套过深、冗余查询、内存泄漏）？ | ✅ 通过 | 2026-09-18 14:48:25 |
| 可维护性 | 代码是否清晰易读？注释是否充分？命名是否合理？ | ⚠️ 待优化 | 2026-09-18 14:48:25 |

**结论**：⛔ 1 个阻断项，3 个改进项。**风险等级**：medium。

本 PR 涉及 23 个文件的大规模重构，主要目标是移除所有 `TYPE_CHECKING` 块，引入
`yate/interfaces.py` 中的 `AppProtocol` 作为依赖倒置层，同时提取
`yate/editor_view/pane_types.py` 作为纯数据模型以打破循环依赖。

- **新增文件**：`yate/interfaces.py`（`AppProtocol` 抽象层）、`yate/editor_view/pane_types.py`（面板树数据结构）
- **核心模式变更**：几乎所有文件的函数签名从 `app: "YateApp"` 变为 `app: AppProtocol`
- **Import 变化**：约 18 个文件移除 `from typing import TYPE_CHECKING` 及 `if TYPE_CHECKING:` 块
- **类型注解简化**：已有 PEP 563，注解运行时延迟求值为字符串，不再需要 `TYPE_CHECKING` 避免循环导入
- **功能增强**：`app_features/completion.py` 重写，引入更完善的补全陈旧性检测

#### 🚫 阻断项：`accept()` 跨行条件导致多行补全被错误拒绝

位置：`yate/app_features/completion.py`（功能性 / 逻辑）

```python
def accept(self) -> None:
    ...
    if item.has_range():
        r0 = item.range_start_row or 0
        c0 = item.range_start_col or 0
        r1 = item.range_end_row or 0
        c1 = item.range_end_col or 0
        # Cursor left the row(s) the completion was for — discard.
        if row != r0 or row != r1:    # ← 问题行
            return
```

`r0 != r1` 时 `row` 不可能同时等于 `r0` 与 `r1`，该条件恒为真，所有跨行补全被无条件拒绝。

**修正建议**（等价于 §4.5）：

```python
if row < r0 or row > r1:      # 或 if not (r0 <= row <= r1):
    return
```

#### ⚠️ 改进项

1. **`AppProtocol` 中过多 `Any` 削弱类型安全**（可维护性）：大量字段用 `Any` 而非真实类型注解。
   建议在不会引发运行时导入冲突时改用字符串前向引用，如
   `workspace: 'Workspace'`、`keymaps: dict[str, 'Keymap']`、`config: 'YateConfig'`、
   `actions: 'ActionRegistry'`、`commands: 'CommandRegistry'`、`extension_loader: 'ExtensionLoader'`、
   `screen_stack: list['Screen']`、`screen: 'Screen'`，返回值用 `object`。
   → 本项直接催生了 §4 的 v3 精化计划。

2. **`Leaf.states` 的 `default_factory` 可简化**（可维护性）：

   ```python
   # 现状（正确但啰嗦）
   states: dict[int, ViewState] = field(default_factory=lambda: dict[int, ViewState]())
   # 建议（行为等价，更 Pythonic）
   states: dict[int, ViewState] = field(default_factory=dict)
   ```

3. **`remove_node` 原地修改可能导致副作用**（可维护性）：函数原地修改 `node.children` / `node.sizes`
   却又返回新 `Node`，语义不一致；若其他代码持有同一 `Split` 实例引用会被意外影响。
   建议：若要返回新树则先拷贝 `node` 再改，或在 docstring 中明确"原地修改"语义。

### 5.2 评审 v3（2026-09-18 19:51）

| 评审规则 | 评审内容 | 结论 | 完成时间 |
| --- | --- | --- | --- |
| 功能性与逻辑 | 代码是否按预期执行？有无逻辑错误或未处理的边缘情况？ | ❌ 未通过 | 2026-09-18 19:51:25 |
| 安全性 | 是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？ | ✅ 通过 | 2026-09-18 19:51:25 |
| 性能 | 是否有明显的性能瓶颈（如循环嵌套过深、冗余查询、内存泄漏）？ | ⚠️ 待优化 | 2026-09-18 19:51:25 |
| 可维护性 | 代码是否清晰易读？注释是否充分？命名是否合理？ | ⚠️ 待优化 | 2026-09-18 19:51:25 |

**结论**：⛔ 2 个阻断项，2 个改进项。**风险等级**：medium。

改动概要：新增 `interfaces.py` 定义 `AppProtocol` 实现依赖倒置；创建 `pane_types.py`
作为纯数据模型层解耦 editor 与 panes；将 `CompletionController` 逻辑提取至独立文件；
移除多个文件的 `TYPE_CHECKING` 条件导入并统一使用新接口；优化 vim 模式下的补全触发逻辑。

#### 🚫 阻断项

1. **`_vim_insert_mode` 中直接访问字典键可能 `KeyError`**（功能性 / 逻辑）: `yate/app_features/completion.py`

   ```python
   # 现状：键不存在（如异常状态转换期间）即崩溃
   vim = self._app.keymaps["vim"]

   # 建议：安全访问 + 合理默认值
   vim = self._app.keymaps.get("vim")
   if vim is None:
       return True   # 安全默认值
   ```

2. **`reconcile` 用 `id()` 作状态键不稳定**（功能性 / 逻辑）: `yate/editor_view/panes.py`

   ```python
   # 现状：Document 被重建（重新打开文件）时键失效
   state = leaf.states.get(id(leaf.doc))

   # 建议：用稳定标识符
   state = leaf.states.get(leaf.doc.path)
   ```

#### ⚠️ 改进项

1. **`reconcile` 全量重建 widget 树影响性能**（性能）: `yate/editor_view/panes.py`

   ```python
   for child in list(self.children):
       await child.remove()
   await self.mount(self._build(self.manager.root))
   ```

   建议引入差异比较机制，仅更新变化节点、复用未变动的 `EditorView` 实例。

2. **`panes.py` 重新导出 `pane_types` 内容缺乏弃用指引**（可维护性）: `__all__` 里
   列出 `Axis`、`Leaf`、`Node` 等却无提示。建议加注释指明应从
   `yate.editor_view.pane_types` 导入，并规划未来移除这些导出。

### 5.3 最终处置（2026-09-23 复核）：所有项均已闭环，但方案本身被取代

> 复核结论：历史评审记录；阻断项均已修复，评审对象已被后续重构取代。
> `yate/interfaces.py` 与 `AppProtocol` 在「分层重构」中**整体删除**，`app_features/*`
> 目录也已删除；当前架构使用具体对象与 `yate/editor.py`（`Editor`），不再依赖任何 `Protocol`。

| 来源 | 问题 | 最终处置 |
| --- | --- | --- |
| 评审 v2 阻断 | `accept()` 跨行条件 `row != r0 or row != r1` | ✅ 已修复：改按行范围判定，并叠加列 / 前缀守卫（见 `completion_staleness_check_plan.md`） |
| 评审 v2 改进 1 | `AppProtocol` 过多 `Any` | ⛔ 不适用：`AppProtocol` 已删除 |
| 评审 v2 改进 2 | `Leaf.states` 的 `default_factory` | ✅ 演进：现为 `dict[int, ViewState]`，键由 `id(doc)` 改为稳定的 `Document.uid`（见 `yate/editor_view/pane_types.py`） |
| 评审 v2 改进 3 | `remove_node` 原地修改 | ✅ 保留设计：`pane_types.py` 维持模型"就地重建"策略，详见文件内注释与 `split_panes_plan.md` |
| 评审 v3 阻断 1 | `_vim_insert_mode` 直接取 `keymaps["vim"]` 可能 `KeyError` | ✅ 已修复：改安全访问（原 `app_features/completion.py` 已删除，逻辑迁至 `yate/completion.py`） |
| 评审 v3 阻断 2 | `reconcile` 用 `id()` 作状态键 | ✅ 已修复：改用 `Document.uid`（稳定自增 id），`Leaf.states: dict[int, ViewState]`，注释说明用于规避文档重建导致的键失效 |
| 评审 v3 改进 1 | `reconcile` 全量重建 widget 树 | ℹ️ 有意设计：`PaneHost` 明确"整树重建 + EditorView 廉价可抛弃、状态全部外置模型"，见 `split_panes_plan.md` |
| 评审 v3 改进 2 | `panes.py` 再导出缺少说明 | ✅ 已收敛：纯数据模型抽到 `pane_types.py`，`panes.py` 作为 UI 侧入口 |

---

## 6. 验证方案

**6.1 导入验证（修改后立即执行）**

```bash
python -c "from yate.interfaces import AppProtocol; print('interfaces OK')"
python -c "from yate.keymaps.base import ActionContext, Keymap; print('keymaps OK')"
python -c "from yate.services.extensions import ExtensionAPI; print('extensions OK')"
python -c "from yate.editor_view.editor import EditorView; print('editor OK')"
python -c "from yate.app import YateApp; print('YateApp OK')"
```

**6.2 类型检查（pyright strict）**

```bash
python -m pyright yate/  # 项目配置了 strict 模式
```

预期：零新增诊断（某些 `AppProtocol` 成员可能需要补充精化，见 §4）。

**6.3 运行测试**

```bash
python -m pytest tests/ -v --tb=short
```

**6.4 启动 smoke test**

```bash
python -m yate --help  # CLI 正常
```

### 成功标准

- ✅ 所有 19 个 TYPE_CHECKING 块被移除，或减少到 `editor_view` 内部类型（不涉及 `yate.app`）
- ✅ 无运行时 `ImportError`
- ✅ pyright strict 模式零新增错误
- ✅ 全部现有测试通过
- ✅ CLI 可正常启动

---

## 7. 风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| `AppProtocol` 遗漏成员，pyright 报错 | 中 | 低 | Protocol 是渐进式的，漏一个补一个即可；不影响运行时 |
| Protocol 成员类型过于宽泛（用了 `Any`） | 低 | 低 | 可后续迭代精化类型；当前目标是移除 TYPE_CHECKING（→ §4 已解决） |
| `editor_view` 内部循环的字符串注解 pyright 无法解析 | 低 | 中 | pyright 对同包前向引用处理良好；可保留极小范围 TYPE_CHECKING 仅用于 `editor_view` 内部类型 |
| 修改后某个文件导入时先于 `YateApp` 初始化 | 极低 | 高 | 逐步修改 + 每步导入验证；Protocol 不依赖 `YateApp`，下层模块不会触发循环 |
| （§4 追加）某个 TYPE_CHECKING 导入实际在运行时成环（遗漏传递依赖） | 中 | 高 | 每加一批导入就跑 `python -c "from yate.app import YateApp"`；pyright 不检测运行时循环 |
| （§4 追加）pyright strict 对原 `Any` 成员报 `reportUnknownVariableType` | 低 | 低 | `Any` 会抑制该规则；具体类型同样可推断。若仍报错，加显式 property 注解 |
| （§4 追加）TYPE_CHECKING 块膨胀难维护 | 低 | 低 | 按包分组 + 分区注释（`# editor_view widgets`、`# services`）；当前 10 条可控 |
| （§4 追加）`Axis` / `Leaf` 从 `pane_types.py` 导入与别处同名冲突 | 极低 | 低 | 仓库中无同名 `Axis`；定稿前再 grep 一次 |
| （§4 追加）`completion.py` 行范围改动影响未文档化的多行补全场景 | 极低 | 低 | 当前 LSP/前缀补全不产生多行区间；新写法严格更正确 |

---

## 8. 后续演进方向（原 v3 计划 §8，均未实施）

1. **生成 `yate.interfaces` 类型别名再导出模块**：新建 `yate/interfaces/__init__.py`，
   一并导出 `AppProtocol` 与现在可安全导入的具体类型（`Workspace`、`YateConfig`、`Axis`、
   `Leaf`、`ShellResult`），为下游提供统一导入面。

2. **自动检查 `interfaces.py` 残留 `Any`**：pyright strict 的 `reportUnknownType` 不会标记
   Protocol 定义内的 `Any`；可用 CI 脚本 grep `: Any` 并与白名单（Textual 内部类型 + 不透明回调）比对。

3. **为 Textual 集成面提供 `_TextualProtocol`**：保留为 `Any` 的 8 个成员全是 Textual 类型
   （`screen`、`run_worker`、`_push_overlay`、`try_window_prefix(event)` 等），可用一个小 Protocol
   描述 YateApp 依赖的 Textual API 子集；在 Textual 频繁破坏兼容性时收益明显。

4. **把 `Keymap` / `ActionRegistry` / `CommandRegistry` 拆出叶子级 stub 模块**：当前这些类自身
   导入 `AppProtocol` 才造成环；若各自拆出最小 stub 而实现留在别处，`interfaces.py` 就能直接导入、
   无需 TYPE_CHECKING。改动较大，但长期架构更干净。

5. **仅对 Textual 相关导入放宽 `reportMissingTypeStubs=false`**：待 Textual 类型桩完善后再重审那 8 处 `Any`。

> 上述方向均基于"继续使用 Protocol"的前提。**实际演进路径是另一条**：整体的
> `interfaces.py` / `app_features/*` 被删除，改为具体对象 + `Editor` 上移 —— 详见
> [app-layering-refactoring-plans/README.md](app-layering-refactoring-plans/README.md)。
