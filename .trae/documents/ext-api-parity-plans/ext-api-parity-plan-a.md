# plan_a — Python API 面扩展（wave-1）

## 目标

NEXT STEPS 点 1 + 点 2 的 Python 侧：theme / clipboard / docs / actions 四个桥、`api.ui.add_segment` 工厂、`api.events.EditorEvent` 再导出、`bind_action` / `unbind_key` 重绑原语。

## 专属文件清单（独占，不得触碰其他文件）

- `yate/services/extension_bridges.py`
- `yate/services/extension_api.py`
- `yate/editor.py`
- `tests/test_extension_bridges.py`
- `tests/test_extension_api.py`

## 精确改动

### 1. yate/services/extension_bridges.py

1. `EventExtensionBridge` 增加类属性再导出（先例：`HighlightExtensionBridge.LangSpec`，L129）：
   ```python
   #: Re-exported so extensions subscribe without importing yate internals.
   EditorEvent = EditorEvent
   ```
2. 新增 `ThemeExtensionBridge`（不 import yate.editor_view，仅持回调——R4）：
   ```python
   class ThemeExtensionBridge:
       """``api.theme`` -- switch/read the color theme from an extension."""
       def __init__(self, set_theme: Callable[[str], None], active_name: Callable[[], str]) -> None: ...
       def set(self, name: str) -> None:  # 转发 set_theme 回调；未知主题的异常原样上抛（setup 期由 loader 记录、回调期由 guard 兜底）
       def active(self) -> str: ...       # 返回当前主题名
   ```
3. 新增 `ClipboardExtensionBridge`（直接 import `yate.services.clipboard` 的模块级函数，同层 L3 合法）：
   ```python
   def set(self, text: str) -> bool:   # copy_text(text)
   def get(self) -> str | None:        # paste_text()
   ```
4. 新增 `DocsExtensionBridge`（只读包装 `EditorSession`；禁止暴露 session.open/activate/close_active 等会绕过 UI flows 的可变成员）：
   ```python
   def __init__(self, session: EditorSession) -> None: ...
   def all(self) -> list[Document]:    # list(self._session.docs) 新列表
   def is_open(self, path: str | Path) -> bool:  # self._session.is_open(Path(path)) is not None
   ```
5. 新增 `ActionExtensionBridge`：
   ```python
   def __init__(self, registry: ActionRegistry, run_action: Callable[[str], bool]) -> None: ...
   def run(self, name: str) -> bool:   # 经 run_action（即 KeyUi.execute_action，走编辑器统一派发）
   def names(self) -> list[str]:       # registry.names()
   def has(self, name: str) -> bool:   # registry.get(name) is not None
   ```
6. `UiExtensionBridge` 增加工厂（Lua 无法构造 frozen dataclass，此工厂是点 3 对齐的使能件；`add_status_segment` 保留为既有公共 API）：
   ```python
   def add_segment(self, id: str, provider: Callable[[], str | None],
                   align: SegmentAlign = "right", priority: int = 0) -> None:
       self.add_status_segment(StatusSegment(id=id, provider=provider, align=align, priority=priority))
   ```

### 2. yate/services/extension_api.py

1. `ExtensionContext` 增加三个回调字段（docstring 注明由 editor 注入、惰性解析，与 message/run_shell 同型）：
   ```python
   #: ``run_action(name)`` -- run a named action through the editor's key UI
   #: dispatch; the bool result says whether the action was known.
   run_action: Callable[[str], bool]
   #: ``set_theme(name)`` -- switch the color theme (R13: L3 只触发，不自改样式).
   set_theme: Callable[[str], None]
   #: ``active_theme_name()`` -- the active theme's name.
   active_theme_name: Callable[[], str]
   ```
2. `ExtensionAPI.__init__` 构建四个新桥；新增 properties：`theme` / `clipboard` / `docs` / `actions`（docstring 一行说明，风格对齐现有 accessors）。
3. 新增 `bind_action`（结构镜像 `bind_key` 的 `_do` 内嵌与 A13 快照）：
   ```python
   def bind_action(self, key_spec: str, action_name: str, keymap: str = "vsc",
                   description: str = "", category: str = "extension") -> None:
   ```
   - keymap 解析复用 bind_key 语义：`"both"` → ["vsc","vim"]；`"normal"` 别名 → ["vsc"]；未知 keymap 名 → `log.warning` 列出可用名并跳过（先例 bind_key S34）。
   - 校验 `self._ctx.actions.get(action_name)`：未知 action → `log.warning("bind_action: unknown action %r (available: %s)")` 且不绑定（镜像未知 keymap 的响亮失败；文档注明“先注册后绑定”）。
   - A13：`previous = km.lookup(raw)` 记录 undo thunk（恢复 previous 或 remove_binding），与 bind_key L272-285 同构。
   - 绑定本体：`km.add_binding(key_spec, action_name, description or f"action {action_name}", category)`（add_binding 的 action 参数原生接受 str，见 keymaps/base.py:273）。
   - 无装饰器形态（返回 None）。
4. 新增 `unbind_key`：
   ```python
   def unbind_key(self, key_spec: str, keymap: str = "vsc") -> bool:
   ```
   - 同一 keymap 解析；`raw = km.normalize_key(key_spec)`；有 A13 scope 时记录恢复 thunk（previous = km.lookup(raw)）。
   - `removed = km.remove_binding(raw)`；任一目标移除成功即返回 True；未知 keymap → warning + False。
5. 更新模块 docstring 提及四桥与重绑原语（一两句即可）。

### 3. yate/editor.py（仅 `extension_context()` 一处装配）

- `editor.py:402-417` 的 `ExtensionContext(...)` 增加三个实参（惰性 lambda，与 open_path/save 同型）：
  ```python
  run_action=lambda name: self.key_ui.execute_action(name),
  set_theme=lambda name: set_theme(name),
  active_theme_name=lambda: theme.active().name,
  ```
  - import 来源：editor.py 已有 theme 相关装配（THEME_CHANGED 发射），复用其现有 import（`yate.editor_view.theme` 的 `set_theme` / `active`；若为 `from yate.editor_view import theme` 风格则用 `theme.set_theme(...)`）。
  - 不得改动 editor.py 其他区域。

### 4. tests/test_extension_bridges.py（新增用例）

- ThemeBridge：set 转发回调参数；active 返回注入值。
- ClipboardBridge：monkeypatch `yate.services.clipboard.copy_text/paste_text`（session-scoped 模块函数，用 pytest monkeypatch），断言 get/set 转发与返回值。
- DocsBridge：构造假 session（`SimpleNamespace(docs=[...])` 或最小 stub 类），all() 返回新列表（改返回列表不影响 session.docs）、is_open 命中/未命中。
- ActionsBridge：run 经注入回调、names/has 来自真 ActionRegistry（注册临时 action，测试内清理）。
- UiBridge.add_segment：注册后 `segments("right")` 可见且 priority 排序生效；duplicate id 抛 ValueError；A13 scope 下回滚消失。

### 5. tests/test_extension_api.py（新增用例）

- `api.events.EditorEvent is EditorEvent`。
- 四个新 properties 返回对应桥实例。
- bind_action：
  - 绑定后 `km.lookup(raw)` 的 `.action == action_name`（vsc/vim/both 三分支各一例；vim 分支断言 vsc 未动）。
  - 未知 action：无绑定产生 + caplog 有 warning。
  - 未知 keymap：无绑定 + warning。
  - 覆盖重绑：先 bind_key 再 bind_action 同键，lookup 得到 action 名。
  - rollback scope 内 bind_action 后 rollback 恢复 previous（先用内建绑定占位再回滚还原）。
- unbind_key：移除已绑定键返回 True 且 lookup 为 None；未绑定键返回 False；"both" 两图均移除；rollback 恢复原绑定。
- api.actions.run 未知名返回 False、已知名返回 True（注入记录回调）。

## 硬规则自检

- R4：extension_bridges 不 import yate.editor_view（theme 走回调）。
- R6：0 新增 Any / TYPE_CHECKING / ignore。
- R13：theme 只经 set_theme 触发（内部 subscribe 1:N 广播），桥不自改 widget styles。
- A13：所有注册路径记录 undo thunk。
- 命名：桥类名 `*ExtensionBridge`，与既有五桥一致。

## 验收命令

```
python -m pyright yate/services/extension_bridges.py yate/services/extension_api.py yate/editor.py
python -m pytest tests/test_extension_bridges.py tests/test_extension_api.py -q
```

两者 exit 0。全量门禁由主控在 wave-3 统一执行。

## 回滚

单提交 `feat(extensions): widen the python api surface`；revert 即可，无数据迁移。
