# plan-c — UI 贡献点：状态栏段（wave-2，与 plan-b 并行）

父计划：[../extension-system-enhance-plan.md](../extension-system-enhance-plan.md)

## 目标

扩展经 `api.ui.add_status_segment(id, provider, align="right", priority=0)`
在状态栏贡献文本段；StatusBar（L2）自渲染；A13 回滚覆盖。

## 改动文件（独占清单）

| 文件 | 动作 |
|---|---|
| `yate/services/extension_bridges.py` | 新增 `StatusSegment` dataclass + `UiExtensionBridge`（注册表 + 排序快照） |
| `yate/services/extension_api.py` | `ExtensionAPI` 构造 `UiExtensionBridge` 并暴露 `ui` 属性；注册记入回滚 scope |
| `yate/editor_view/statusbar.py` | `refresh_status` 拉取并渲染扩展段（左右对齐分区、priority 降序、None/空隐藏） |
| `yate/editor.py` | `_build_widgets` 将 `ed.extension_api.ui` 注入 `StatusBar` |
| `tests/test_ui_contributions.py` | 新建 |

## 设计

```python
@dataclass(frozen=True)
class StatusSegment:
    id: str
    provider: Callable[[], str | None]
    align: str = "right"      # "left" | "right"
    priority: int = 0

class UiExtensionBridge:
    def add_status_segment(self, segment: StatusSegment) -> None  # 重复 id → ValueError
    def remove_status_segment(self, segment_id: str) -> None
    def segments(self, align: str) -> list[StatusSegment]         # (-priority, 注册序) 快照
```

- provider 返回 `None` 或空串 → 该段本轮隐藏（pull 模型，随
  `refresh_status` 节奏刷新，与 F7 既有刷新点一致）；
- provider 调用由 StatusBar 侧护栏包裹（复用 `_guarded_callback` 形态：
  单段异常显示占位 `!` 并 message，不影响其余段）——实现在 StatusBar 拉取
  处 try/except，避免桥依赖 message；
- 主题着色：扩展段沿用 StatusBar 既有段落样式与 `theme.active()` 变量
  （R13，组件自持；扩展不得直改样式）；
- 注入链：`Editor._build_models` 建 `ExtensionAPI`（wave-1 已带 events）→
  `_build_widgets` 把 `ed.extension_api.ui` 传入 `StatusBar(...)`——
 StatusBar 构造参数追加 `ui: UiExtensionBridge | None = None`（缺省 None
  = 无贡献段，兼容现有测试构造）。

## 步骤

1. `extension_bridges.py`：`StatusSegment` + `UiExtensionBridge`
   （docstring 说明 pull 模型与对齐/优先级语义）。
2. `extension_api.py`：构造并暴露 `ui`；`add/remove` 记入 A13 scope undo。
3. `statusbar.py`：构造参数 + `refresh_status` 渲染左右扩展段
   （左段缀于既有左侧内容后，右段缀于既有右侧内容前；实现按文件实际
   布局微调，偏离记录）。
4. `editor.py`：注入。
5. `tests/test_ui_contributions.py`：注册/去重/移除、排序快照、回滚、
   StatusBar 渲染（含 provider 异常占位与 None 隐藏）。

## 验收命令

```text
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_ui_contributions.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m tools.smoke_test run
```

## 新增测试清单

- `test_segment_registration_dedup_and_removal`
- `test_segments_snapshot_sorted_by_priority`
- `test_segment_registration_rolls_back`
- `test_statusbar_renders_extension_segments`
- `test_failing_provider_shows_placeholder_and_hides`
- `test_none_provider_hides_segment`

## 回滚

revert `statusbar.py` + `editor.py` 注入行；删除桥与测试文件。
