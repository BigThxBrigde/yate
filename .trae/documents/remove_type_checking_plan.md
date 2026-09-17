# 移除 TYPE_CHECKING 循环依赖重构计划 (v2)

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

| # | 文件 | TYPE_CHECKING 导入 | __future__ annotations | 运行时使用？ |
|---|------|-------------------|----------------------|------------|
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
- TYPE_CHECKING 导入**仅用于类型注解**（无 isinstance、无运行时引用）
- 问题**纯粹在类型层面**，运行时已安全

### 1.3 editor_view 内部循环（已部分处理）

```
panes.py ←TYPE_CHECKING→ EditorView (editor.py)
editor.py ←TYPE_CHECKING→ Leaf (panes.py)
```

- `panes.py` 已用**字符串注解** `"EditorView"` + **函数体内延迟导入**（`PaneHost._build()` 内 `from yate.editor_view.editor import EditorView`）
- `editor.py` 中 `Leaf` 用于返回类型注解 `def leaf(self) -> Leaf:`，运行时**不直接依赖** panes 模块（通过 `self.yate.panes` 获取）
- **这两个 TYPE_CHECKING 块可以一并移除**（配合 `from __future__ import annotations`）

---

## 2. 解决方案

### 2.1 核心策略：Protocol 依赖反转

创建 `yate/interfaces.py`，用 `typing.Protocol` 定义接口。所有下层模块将 `YateApp` 注解替换为 `AppProtocol`。

```
重构后依赖方向（无循环）:

yate.interfaces (纯抽象层，仅依赖 editor_core + editor_lsp + editor_syntax)
    ↑ 被引用
    ├── yate.keymaps.*         ← AppProtocol
    ├── yate.services.extensions ← AppProtocol
    ├── yate.editor_view.*      ← AppProtocol
    ├── yate.app_features.*     ← AppProtocol
    └── yate.diagnostics        ← AppProtocol

yate.app (具体实现，依赖所有下层模块)
    └── YateApp 自动满足 AppProtocol (结构化子类型)
```

### 2.2 为什么 Protocol 方案最优

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Protocol 依赖反转** | 符合依赖倒置原则；不影响运行时；IDE/pyright 完美支持 | AppProtocol 枚举成员需要完整审计 |
| 直接运行时导入 | 简单 | 破坏加载顺序，yate.app 还没初始化完下层模块就尝试导入 → ImportError |
| 函数体内延迟导入 | 绕过循环 | 类型注解需要额外处理（不能用在函数签名上）；类型检查器支持差 |

### 2.3 editor_view 内部循环处理

editor_view 包内部的循环已正确处理（字符串注解 + 函数体内延迟导入）。移除 TYPE_CHECKING 后，配合 `from __future__ import annotations`，所有类型引用变为字符串，pyright 可以通过以下方式解析：
- 同包内的简单名称（`Leaf`、`EditorView`）→ pyright 会在包内查找
- 函数体内的运行时导入（已存在）→ 保证实际运行时可用

---

## 3. 详细实施步骤

### 步骤 1：创建 `yate/interfaces.py`

**文件**：`yate/interfaces.py`（新建）

**设计原则**：
- 零依赖 `yate.app` 或任何导入 `yate.app` 的模块
- 只导入底层包：`typing`、`pathlib`、`yate.editor_core.*`、`yate.editor_lsp.*`、`yate.editor_syntax.*`
- 对 Textual 继承的方法（`run_worker`、`screen_stack`、`_push_overlay`）用 `Any` 或最小 Protocol
- 对私有属性（`_terminal_visible`、`_explorer_target`）如果下层模块确实访问了，也纳入 Protocol

**AppProtocol 成员清单**（精确审计结果）：

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

**interfaces.py 导入声明**（顶层）：
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
- 如果某个类型确实需要，可以在 interfaces.py 内部延迟导入（函数体内）或用 TYPE_CHECKING 只对 interfaces.py 自身使用

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

**需要改注解**：
- 所有 `"YateApp"` → `AppProtocol`

### 步骤 5：修改 `yate/editor_view/*.py`（9 个文件）

每个文件的修改模式相同：

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
|------|-------------------|---------|
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
|------|---------|
| `app_features/commands.py` | `"YateApp"` → `AppProtocol` |
| `app_features/completion.py` | `"YateApp"` → `AppProtocol` |
| `app_features/docs.py` | `"YateApp"` → `AppProtocol` |
| `app_features/explorer.py` | `"YateApp"` → `AppProtocol` |
| `app_features/terminal.py` | `"YateApp"` → `AppProtocol` |

### 步骤 7：修改 `yate/diagnostics.py`

移除 TYPE_CHECKING 块，导入 AppProtocol，将 `"YateApp"` 改为 `AppProtocol`。

### 步骤 8：修改 `yate/extensions/python_lsp.py`

移除 TYPE_CHECKING 的 `ExtensionAPI` 导入，改为直接运行时导入：
```python
from yate.services.extensions import ExtensionAPI
```
（此时 services.extensions 已经完成修改，不再有循环）

### 步骤 9：可选 — 让 YateApp 显式继承 AppProtocol

```python
# yate/app.py
from yate.interfaces import AppProtocol

class YateApp(App[None], AppProtocol):
    ...
```

这不是必须的（Protocol 是结构化子类型），但显式继承可以：
- 让 IDE 在 YateApp 类定义时就检查是否满足 Protocol
- 为 Protocol 成员提供更好的 "Go to Definition" 体验

---

## 4. 验证方案

### 4.1 导入验证（修改后立即执行）

```bash
# 确保没有 ImportError
python -c "from yate.interfaces import AppProtocol; print('interfaces OK')"
python -c "from yate.keymaps.base import ActionContext, Keymap; print('keymaps OK')"
python -c "from yate.services.extensions import ExtensionAPI; print('extensions OK')"
python -c "from yate.editor_view.editor import EditorView; print('editor OK')"
python -c "from yate.app import YateApp; print('YateApp OK')"
```

### 4.2 类型检查（pyright strict）

```bash
python -m pyright yate/  # 项目配置了 strict 模式
```

预期：零新增诊断（某些 Protocol 成员可能需要补充精化）。

### 4.3 运行测试

```bash
python -m pytest tests/ -v --tb=short
```

### 4.4 启动 smoke test

```bash
python -m yate --help  # CLI 正常
```

---

## 5. 风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| AppProtocol 遗漏成员，pyright 报错 | 中 | 低 | Protocol 是渐进式的，漏一个补一个即可；不影响运行时 |
| Protocol 成员类型过于宽泛（用了 Any） | 低 | 低 | 可以后续迭代精化类型；当前目标是移除 TYPE_CHECKING |
| editor_view 内部循环的字符串注解 pyright 无法解析 | 低 | 中 | pyright 对同包前向引用处理良好；可保留极小范围的 TYPE_CHECKING 仅用于 editor_view 内部类型 |
| 修改后某个文件导入时先于 YateApp 初始化 | 极低 | 高 | 逐步修改 + 每步导入验证；Protocol 不依赖 YateApp，所以下层模块不会触发循环 |

---

## 6. 实施顺序（依赖顺序，自底向上）

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

---

## 7. 成功标准

- ✅ 所有 19 个 TYPE_CHECKING 块被移除或减少到 editor_view 内部类型（不涉及 yate.app）
- ✅ 无运行时 ImportError
- ✅ pyright strict 模式零新增错误
- ✅ 全部现有测试通过
- ✅ CLI 可正常启动
