# plan-a — 事件订阅系统（wave-1）

父计划：[../extension-system-enhance-plan.md](../extension-system-enhance-plan.md)

## 目标

扩展经 `api.events.subscribe(EditorEvent.X, cb)` 订阅编辑器事件；退订函数返回值；
setup 期间的订阅进 A13 回滚 scope；七个发射点接进 L3 流程与 Editor。

## 改动文件（独占清单）

| 文件 | 动作 |
|---|---|
| `yate/services/events.py` | 新建：`EditorEvent` 枚举、事件载荷 dataclass、`EventHub` |
| `yate/services/extension_api.py` | `EventExtensionBridge` + `ExtensionAPI.events` 属性；构造参数加 `events: EventHub`；subscribe 记入回滚 scope |
| `yate/editor.py` | `_build_models` 构造 `EventHub` 并传入 `ExtensionAPI`；发射：`select_keymap`/`set_theme`/`on_closed` 转发 lambda；`extension_context` 不变 |
| `yate/flows/document_flows.py` | 构造参数加 `events: EventHub`；发射 DOCUMENT_SAVED / DOCUMENT_OPENED / DOCUMENT_ACTIVATED |
| `yate/flows/lsp_sync.py` | 构造参数加 `events: EventHub`；`on_event("diagnostics")` 分支发射 DIAGNOSTICS_UPDATED |
| `tests/test_events.py` | 新建：hub 单元 + 桥 + 回滚 + 发射点集成 |

## 设计

```python
class EditorEvent(Enum):
    DOCUMENT_SAVED / DOCUMENT_OPENED / DOCUMENT_CLOSED /
    DOCUMENT_ACTIVATED / DIAGNOSTICS_UPDATED / KEYMAP_CHANGED / THEME_CHANGED
```

- 载荷：`@dataclass(frozen=True)`，每事件一类（`DocumentSaved(doc)`、
  `DocumentClosed(docs: list[Document])`、`KeymapChanged(name)`、
  `ThemeChanged(name)`、`DiagnosticsUpdated(doc)`）。
- `EventHub(message: Callable[[str], None] | None)`：
  - `subscribe(event, callback) -> Callable[[], None]`（重复订阅不去重，
    退订函数按调用次幂生效）；
  - `emit(event, payload)`：同线程同步、按订阅顺序逐个调用；单回调异常
    被捕获 → log.exception + message（护栏），后续回调继续；
  - `listener_count(event) -> int`（诊断/测试用）。
- 回调类型：`type EventCallback = Callable[..., object]`（PEP 695 语句；
  用户代码边界，形状开放，沿 `AnyCallback` 先例注明理由）。
- `EventExtensionBridge(hub)`：`subscribe` 先记 undo（调退订函数）再挂接；
  归 `ExtensionAPI.events`。
- 发射点（全部低频，不在按键热路径）：
  1. `document_flows.save_document` 成功后 → DOCUMENT_SAVED；
  2. `_open_document` 成功激活后 → DOCUMENT_OPENED；
  3. `activate_doc` 末尾 → DOCUMENT_ACTIVATED；
  4. `EditorSession on_closed` 转发 lambda（editor.py:83）→ DOCUMENT_CLOSED；
  5. `lsp_sync.on_event` `event == "diagnostics"` → DIAGNOSTICS_UPDATED；
  6. `Editor.select_keymap` 成功后 → KEYMAP_CHANGED；
  7. `Editor.set_theme` 成功后 → THEME_CHANGED。

## 步骤

1. 新建 `services/events.py`（枚举/载荷/EventHub，模块 docstring 写明
   "实例由 Editor 持有，非全局总线；事件身份为枚举成员，非字符串"）。
2. `extension_api.py`：加桥与属性；`ExtensionAPI.__init__(ctx, events)`；
   subscribe 进 scope。
3. `editor.py`：`_build_models` 构造 hub（`message=ed.message` 注入）→
   传入 ExtensionAPI 与 DocumentFlows/LspSync 构造；三处发射。
4. `document_flows.py` / `lsp_sync.py`：构造注入 + 发射。
5. `tests/test_events.py`：hub 行为（订阅/退订/顺序/护栏/异常隔离）、
   桥与 A13 回滚（setup 失败撤销订阅）、发射点集成（沿用
   tests/test_app_textual.py 的 Editor 构造模式，自包含新文件）。
6. 架构自检：无 Protocol/TYPE_CHECKING/Any 掩盖；log 惰性 %；命名无禁用后缀。

## 验收命令

```text
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_events.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 新增测试清单

- `test_hub_subscribes_and_unsubscribes`
- `test_hub_emits_in_insertion_order`
- `test_hub_guards_failing_listener`（后续监听继续、message 收到错误）
- `test_bridge_subscription_rolls_back_on_setup_failure`
- `test_document_saved_event_fires`（Editor 集成，保存后触发）
- `test_keymap_and_theme_events_fire`

## 回滚

单文件 revert：删除 `services/events.py` + revert 其余四个文件的引入即可，
事件无持久化副作用。
