# Hex View - Plan C: :hex 命令 + --hex CLI + 流程接入

## 目标

1. 在 `OverlayFlows` 中新增 `open_hex_view` / `toggle_hex_view` 方法；
2. 在 `DocumentFlows` 中通过回调注入将二进制文件打开改走 hex view；
3. 注册 `:hex` 命令（L3 `commands.py`）；
4. 添加 `--hex <file>` CLI 选项（L4 `cli.py` + `app.py`）。

## 非目标

- 修改 `is_text_file` 语义（plan-a 已完成）；
- 修改 HexView widget（plan-b 已完成）。

## 输入

- `yate/flows/overlay_flows.py:39-81`（OverlayFlows 构造器，已持有 push/pop/current_screen）；
- `yate/flows/document_flows.py:54-84`（DocumentFlows 构造器，无 push/pop 能力）；
- `yate/editor.py:188-202`（DocumentFlows 构造）+ `:258-278`（OverlayFlows 构造）+ `:223-234`（`_build_pane_stack`）；
- `yate/commands.py:367-368`（`:help` 命令先例：`editor.overlays.show_help()`）；
- `yate/cli.py:235-247`（`_validate_diff_args` 先例）；
- `yate/app.py:171`（`self._diff_files` 先例）+ `:208-214`（`call_after_refresh` 先例）。

## 独占文件清单

- `yate/flows/overlay_flows.py`（修改：新增 `open_hex_view` + `toggle_hex_view`）；
- `yate/flows/document_flows.py`（修改：构造器新增 `open_hex_view` 回调参数，二进制分支改调回调）；
- `yate/editor.py`（修改：DocumentFlows 构造注入回调 + Editor 持有延迟 flush 逻辑）；
- `yate/commands.py`（修改：注册 `:hex` 命令）；
- `yate/cli.py`（修改：添加 `--hex` 选项 + 校验）；
- `yate/app.py`（修改：`YateApp.__init__` 存 `self._hex_file` + `on_mount` 调 `call_after_refresh`）；
- `tests/test_overlay_flows_hex.py`（新增：OverlayFlows hex view 测试）。

## 具体修改

### 1. 修改 `yate/flows/overlay_flows.py`

**新增导入**：
```python
from yate.editor_view.hexview import HexScreen, MAX_HEX_VIEW_SIZE
```

**R11 登记**：在 `tests/test_architecture.py:234-243` 的 `UI_FROZEN_FILES["flows/overlay_flows.py"]` 集合中追加 `"yate.editor_view.hexview"`。

**新增 `open_hex_view` 方法**：
```python
def open_hex_view(self, path: Path) -> None:
    """Open a file in the hex view (read-only).

    If a HexScreen is already the top screen, pop it (toggle-off semantics).
    """
    if isinstance(self._current_screen(), HexScreen):
        self._pop_screen()
        return
    try:
        data = path.read_bytes()
    except OSError as exc:
        self._message(f"cannot read {path.name}: {exc}", "warn")
        return
    if len(data) > MAX_HEX_VIEW_SIZE:
        self._message(
            f"file too large for hex view: {path.name} "
            f"(> {MAX_HEX_VIEW_SIZE} bytes)",
            "warn",
        )
        return
    if self._mounted():
        self.push(HexScreen(path, data))
```

> `MessageFn = Callable[[str, str], None]`（`yate/flows/__init__.py:28`）：所有
> `_message` 调用必须带第二个 severity 实参（`"warn"` / `"info"`）。

**新增 `toggle_hex_view` 方法**（供 `:hex` 命令调用）：
```python
def toggle_hex_view(self) -> None:
    """Toggle between text view and hex view for the active document."""
    if isinstance(self._current_screen(), HexScreen):
        self._pop_screen()
        return
    doc = self.session.doc
    # session.doc is a non-optional property (session.py:63, raises on empty
    # docs) -- the only guard needed is the unsaved-buffer one.
    if doc.resolved_path is None:
        self._message("cannot hex view an unsaved buffer", "warn")
        return
    self.open_hex_view(doc.resolved_path)
```

### 2. 修改 `yate/flows/document_flows.py`

**构造器新增参数**（`document_flows.py:54-84`）：
```python
def __init__(
    self,
    spawn: SpawnFn,
    session: EditorSession,
    workspace: Workspace,
    lsp: LspManager,
    explorer_tree: ExplorerTree,
    prompt_bar: PromptBar,
    events: EventHub,
    message: MessageFn,
    report: MessageFn,
    refresh_ui: Callable[[], None],
    mounted: StateQuery,
    reveal_explorer: Callable[[], None],
    startup_readonly: bool,
    open_hex_view: Callable[[Path], None] | None = None,  # NEW
) -> None:
    ...
    self._open_hex_view = open_hex_view
```

**修改 `_open_document` 二进制分支**（`document_flows.py:182-185`）：

当前逻辑：
```python
if doc is None:
    self._report(f"not a text file: {path.name}", "warn")
    log.info("open skipped (binary): %s", path)
    return None
```

新逻辑：
```python
if doc is None:
    if self._open_hex_view is not None:
        self._open_hex_view(path)
    else:
        self._report(f"not a text file: {path.name}", "warn")
    log.info("open skipped (binary): %s", path)
    return None
```

**修改 `_open_document_async` 二进制分支**（`document_flows.py:206-208`）：

同理，二进制分支改调 `self._open_hex_view(path)`。

### 3. 修改 `yate/editor.py`

**DocumentFlows 构造注入回调**（`editor.py:188-202`）：

当前构造（`editor.py:188-202`）不传 `open_hex_view`。修订：
```python
ed.document_flows = DocumentFlows(
    spawn=ed.app.run_worker,
    session=ed.session,
    workspace=ed.workspace,
    lsp=ed.lsp,
    explorer_tree=ed.explorer_tree,
    prompt_bar=ed.prompt_bar,
    events=ed.events,
    message=ed.message,
    report=ed.report,
    refresh_ui=ed.refresh_ui,
    mounted=lambda: ed.mounted,
    reveal_explorer=ed.reveal_explorer,
    startup_readonly=ed.startup_readonly,
    open_hex_view=None,  # Bound late in _build_pane_stack (overlays not yet built)
)
```

**`_build_pane_stack` 阶段绑定回调**（`editor.py:223-278`）：

在 OverlayFlows 构造完成后（`editor.py:278` 之后），绑定回调：
```python
ed.document_flows.bind_hex_opener(ed.overlays.open_hex_view)
```

**说明**：DocumentFlows 构造早于 OverlayFlows（`editor.py:188` vs `editor.py:258`），
且启动目标在 Editor 构建期打开（`editor.py:432` 调 `_open_startup_target`，早于
`_build_pane_stack` 与挂载）。若启动目标是二进制文件，`_open_document` 调用时
`self._open_hex_view` 仍为 `None`，走 fallback 暂存 pending；挂载后 flush。

**修订方案（主代理定稿）**：pending 状态归 **DocumentFlows** 所有（fallback 发生在
它的 `_open_document` 里），Editor 只负责挂载后的 flush：

**DocumentFlows 新增**：
```python
# __init__:
self._pending_hex_path: Path | None = None

def bind_hex_opener(self, opener: Callable[[Path], None]) -> None:
    """Bind the overlay-flow hex opener (overlays are built later)."""
    self._open_hex_view = opener

def take_pending_hex(self) -> Path | None:
    """Return and clear the deferred binary startup target (post-mount)."""
    pending = self._pending_hex_path
    self._pending_hex_path = None
    return pending
```

**`_open_document` 二进制分支（fallback 定稿）**：
```python
if doc is None:
    if self._open_hex_view is not None:
        self._open_hex_view(path)
    else:
        # Overlays not yet built (startup target): defer to post-mount flush.
        self._pending_hex_path = path
    log.info("open skipped (binary): %s", path)
    return None
```
（`_open_document_async` 二进制分支同理。）

**Editor.on_mount 末尾 flush**（app.on_mount 在 app.py:207 `await self.editor.on_mount()`
之后才处理 `--diff`；pending flush 同样放 Editor.on_mount 尾部，走
`call_after_refresh` 安全层）：
```python
# Editor.on_mount tail:
pending = self.document_flows.take_pending_hex()
if pending is not None:
    self.app.call_after_refresh(self.overlays.open_hex_view, pending)
```
（Editor 是 L3 唯一 App 句柄持有者，`call_after_refresh` 动词合法；pending 取用
走 `take_pending_hex` 方法，不跨对象摸私有属性。）
**不要**在 `_build_pane_stack` 末尾 flush（彼时尚未挂载，push 会被
`_mounted()` 守卫静默丢弃）。

### 4. 修改 `yate/commands.py`

**在 `register_commands` 中新增**（仿 `:help` 先例，`commands.py:367-368`）：
```python
def _hex(args: str) -> None:
    editor.overlays.toggle_hex_view()

reg("hex", _hex, "toggle hex view for the current file")
```

### 5. 修改 `yate/cli.py`

**在 `build_parser` 中新增**：
```python
parser.add_argument(
    "--hex",
    dest="hex_file",
    metavar="FILE",
    help="open a file in hex view (read-only hex dump)",
)
```

**新增校验函数**（仿 `_validate_diff_args`，`cli.py:235-247`）：
```python
def _validate_hex_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.hex_file:
        if args.path:
            parser.error("--hex cannot be combined with a startup path argument")
        if args.diff_files:
            parser.error("--hex cannot be combined with --diff")
```

**在 `main` 中传递**：
```python
app = YateApp(
    target=target,
    keymap=keymap,
    theme_name=args.theme,
    config=config,
    readonly=args.readonly,
    ext_files=args.ext_files,
    ext_dirs=args.ext_dirs,
    diff_files=[Path(p) for p in args.diff_files] if args.diff_files else None,
    hex_file=Path(args.hex_file) if args.hex_file else None,
)
```

### 6. 修改 `yate/app.py`

**`YateApp.__init__` 新增参数**（仿 `diff_files`，`app.py:156-171`）：
```python
def __init__(
    self,
    target: str | Path | None = None,
    *,
    keymap: str | None = None,
    theme_name: str | None = None,
    config: YateConfig | None = None,
    readonly: bool = False,
    ext_files: list[str | Path] | None = None,
    ext_dirs: list[str | Path] | None = None,
    diff_files: list[Path] | None = None,
    hex_file: Path | None = None,  # NEW
) -> None:
    ...
    self._hex_file = hex_file
```

**`on_mount` 中调 `call_after_refresh`**（仿 `diff_files`，`app.py:208-214`）：
```python
if self._hex_file:
    self.call_after_refresh(
        self.editor.overlays.open_hex_view, self._hex_file
    )
```

### 7. 新增 `tests/test_overlay_flows_hex.py`

**测试用例**：

| 用例名 | 验证行为 |
|---|---|
| `test_open_hex_view_pushes_hex_screen` | 给定二进制文件 → 推送 HexScreen |
| `test_open_hex_view_pops_when_already_hex_screen` | HexScreen 激活时 → 弹出 screen |
| `test_open_hex_view_rejects_oversize_file` | >100MB 文件 → 报错，不推送 HexScreen |
| `test_toggle_hex_view_opens_for_text` | 文本文件执行 `:hex` → 推送 HexScreen |
| `test_toggle_hex_view_closes_when_active` | HexScreen 激活时执行 `:hex` → 弹出 screen |
| `test_toggle_hex_view_unsaved_buffer_warns` | 未保存 buffer 执行 `:hex` → 警告 |

**测试文件独占**：`tests/test_overlay_flows_hex.py`。

## 输出

- 二进制文件自动打开 hex view（通过回调注入）；
- `:hex` 命令可切换文本/hex 视图；
- `--hex <file>` CLI 选项可直接启动 hex view；
- 测试覆盖正反路径。

## 验收命令

```powershell
cd D:\Programming\yate-hex-view
.venv\Scripts\python.exe -m pytest tests/test_overlay_flows_hex.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/flows/overlay_flows.py yate/flows/document_flows.py yate/editor.py yate/commands.py yate/cli.py yate/app.py tests/test_overlay_flows_hex.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

通过判定标准：
- pytest 退出码 0，所有用例通过；
- pyright 零诊断；
- 架构测试无新增违规（R11 登记生效）。

## 风险清单

| 风险 | 缓解 |
|---|---|
| `--hex` 与 `--diff` / `path` 冲突 | `_validate_hex_args` 提前拦截 |
| `:hex` 在未保存 buffer 上崩溃 | `toggle_hex_view` 检查 `doc.resolved_path is None` |
| R11 登记遗漏 | `UI_FROZEN_FILES` 同步更新 |
| DocumentFlows 构造早于 OverlayFlows | Editor 持有 `_pending_hex_path`，`_build_pane_stack` 末尾 flush |

## 回滚路径

恢复 `overlay_flows.py` / `document_flows.py` / `editor.py` / `commands.py` / `cli.py` / `app.py` 的原始版本即可回滚。

## 触碰架构边界

- **R11**：`flows/overlay_flows.py` 新增 `yate.editor_view.hexview` 导入，须登记 `UI_FROZEN_FILES`；
- **R5**：`commands.py` import `yate.editor`（已存在），反向禁止（已遵守）；
- **R7**：`YateApp.__init__` 装载内置表（已存在），本波次不触碰；
- **R3**：`editor_view/hexview.py` 不得 import `yate.editor` / `yate.app`（plan-b 已遵守）。

## 【执行】【审核】迭代记录段

- 2026-10-24 主代理复核修订：open_hex_view 移至 OverlayFlows（DocumentFlows 无 push/pop 能力）；
  DocumentFlows 改走回调注入（`open_hex_view: Callable[[Path], None] | None`）；
  CLI 接线照 `--diff` 先例（`YateApp.__init__` 存 `self._hex_file`，`on_mount` 用 `call_after_refresh`）；
  `:hex` 命令照 `:help` 先例（`editor.overlays.toggle_hex_view()`）；
  R11 登记修正为全点分模块名（`"yate.editor_view.hexview"`）。
- 2026-10-24 主代理二轮定稿：pending 状态归 DocumentFlows（`take_pending_hex` /
  `bind_hex_opener` 方法化，不跨对象摸私有属性），flush 点定在 Editor.on_mount 尾部
  （`_build_pane_stack` 末尾 flush 会被 `_mounted()` 守卫静默丢弃）；
  `session.doc` 判空语义修正（非可选属性，仅判 `resolved_path is None`）；
  `_message` 全部补 severity 实参（`MessageFn = Callable[[str, str], None]`）。
