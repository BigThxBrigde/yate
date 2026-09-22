# Plan A — 叶子模型：会话 / 注册表 / 键映射

> 状态：✅ **已完成**（工作区）· 前置：无 · 后置：[Plan B](plan_B_widget_selfhold.md)
> 产出：`yate/session.py`、`yate/registries.py`、`yate/keymaps/registry.py`、`KeyUi`（改造）
> 门禁：`python -c "import yate.session, yate.registries"` 无错；`python -m pyright yate/` 0 诊断

---

## A.1 背景（重构前）

1. 文档模型（`docs` / `doc` / `buffer` / `doc_index` / `search` / `welcome_visible`）直接挂在 `YateApp` 上；
   每个下层消费者（keymap、widget、extension、diagnostics）为了拿到它都要在**自己的模块**里定义窄 Protocol，
   再由 `YateApp` 结构性满足 —— 协议数量随消费者线性增长。
2. 键映射集合以 `dict[str, Keymap]` + `keymap_name: str` 两个裸值在层间传参，切换/查询逻辑散落各处。
3. 动作/命令注册表与"表内容"耦合，注册表被放在高层，导致下层无法持有同一对象。

## A.2 交付物

| 文件 | 形态 | 内容 |
|---|---|---|
| `yate/session.py` | `class EditorSession`（+ `ClosedHook` 类型别名） | `docs: list[Document]`、`index`、`search: SearchEngine`、`welcome_visible`；只读属性 `doc` / `buffer`；方法 `make_buffer` / `apply_buffer_options` / `is_open` / `activate` / `open` / `open_async` / `new_buffer` / `reset_search` / `cycle` / `close_active` / `close_under` / `retarget` |
| `yate/registries.py` | `Action`（dataclass）、`ActionRegistry`、`CommandRegistry`、`CommandFunc` | 纯容器：`register` / `get` / `names` / `describe`（`ActionRegistry.execute(name, ctx)`） |
| `yate/keymaps/registry.py` | `class KeymapSet` | `get` / `__getitem__` / `__iter__` / `names` / `name` / `active` / `select` / `toggle` |
| `yate/keymaps/base.py` | `KeyUi`、`ActionContext` | `KeyUi` 为**具体记录**（回调集合），`ActionContext(session, ui)` 通过属性暴露 `buffer` / `doc` |

## A.3 设计要点（为什么这样切）

1. **一个具体对象胜过 N 个协议**：`EditorSession` 无 UI、无 Textual、无 LSP，所有层共享**同一个实例**，
   于是 `DocHost` / `UiHost` / `ExplorerOps` 一类的"每消费者一协议"全部消失。
2. **副作用留给调用方**：session 只报告"哪些文档被关闭"（`on_closed` 回调，由 `Editor` 注入
   `_lsp_documents_closed`），自己不做 LSP 通知、不重绘。
3. **注册表下沉为叶子**：`registries.py` 只依赖 `keymaps.base`，任何层都能持有同一 `ActionRegistry` /
   `CommandRegistry`；**表内容**留在 `actions.py` / `commands.py`（Plan C）。
4. **`KeymapSet` 取代裸 dict + name**：`select()` / `toggle()` 成为模型自身行为，避免各层各写一份切换逻辑。
5. **能用函数/记录实现的就不造类**：`KeyUi` 是 dataclass 式记录而非协议；`ClosedHook` 是函数别名而非回调协议。

## A.4 旧 → 新 对照

| 旧（`YateApp` 上） | 新 |
|---|---|
| `app.docs` / `app.doc_index` / `app.doc` / `app.buffer` | `session.docs` / `session.index` / `session.doc` / `session.buffer` |
| `app.search` | `session.search` |
| `app.welcome_visible` | `session.welcome_visible` |
| `app.close_documents_under(path)` | `session.close_under(path)` |
| 关闭文档后手工通知 LSP | `EditorSession(on_closed=...)` 回调 |
| `app.keymaps`（dict）+ `app.keymap_name` | `KeymapSet`：`.get(name)` / `.name` / `.active` / `.select()` / `.toggle()` |
| 每消费者一个窄 Protocol | `EditorSession` + `KeyUi` + `ActionContext`（具体对象） |

## A.5 验收证据

- `yate/session.py` 仅 import `config` / `editor_core` / `services.workspace`（无 `textual`、无 `editor_lsp`、
  无 `editor_view`）。
- `yate/registries.py` 仅 import `keymaps.base`。
- 构造点唯一：`yate/editor.py:106` `EditorSession(config, on_closed=self._lsp_documents_closed)`；
  `yate/editor.py:119` `KeymapSet(...)`。（旧测试里的 `ActionContext(cast(Any, app))` 属于 Plan E 迁移范围。）
- `python -m pyright yate/` → 0 诊断。
