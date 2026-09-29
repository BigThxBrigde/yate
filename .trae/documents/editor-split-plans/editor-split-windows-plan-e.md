# plan-e：抽取 WindowFlows（window_flows.py）

> 前置：plan-b（命名统一）、plan-c（删薄委托）、plan-d（DocumentFlows）已合入；
> 行号基于 HEAD `07004a0`（与 c04d202 合并后 editor.py 未变，grep 已复核）。

## 一、职责与迁移清单

`window_flows.py::WindowFlows` 承接 editor.py 的窗格/窗口命令簇与 vim `ctrl+w` 弦状态机。

迁移成员（9 方法 + 1 property + 1 模块常量）：

| 成员 | editor.py 行号 | 依赖取证 |
|---|---|---|
| `split_with_path` | :864 | `session.doc`（:874 相对路径基准）、`open_path`（:882 → plan-d 后 `document_flows.open_path`）、`app.run_worker` |
| `_split_pane` | :889 | `app.run_worker` |
| `_split_pane_worker` | :895 | `panes.split_active`、`open_path_async`（:900 → `document_flows`）、`after_pane_focus`（:903） |
| `only_pane` | :905 | `panes.only_active` |
| `close_pane` | :914 | `panes.leaf_count`、`message`、`panes.close_active` |
| `resize_pane` | :924 | `panes.resize` / `panes.equalize`、`message` |
| `window_pending`（property） | :940 | `_window_pending` 状态 |
| `try_window_prefix` | :945 | `has_modal_screen`（:952）、`prompt_bar.active_mode`（:954）、`keymaps` + `VimKeymap`/`VimMode`（:962-964）、`message` |
| `_window_command` | :973 | `app.focused`、`explorer_tree`（:976-980）、`panes.cycle_focus`/`focus_direction`、`focus_editor`/`focus_explorer` |
| `_WINDOW_KEYS`（常量） | :74-79 | 纯数据 |

状态归属：`_window_pending`（editor.py:300 初始化）移入 `WindowFlows.__init__`。

`has_modal_screen`（editor.py:403-405）**留在 Editor**（读 `app.screen_stack`，`handle_key` :721 也用），以 `Callable[[], bool]` 注入。

## 二、构造签名与装配

```python
WindowFlows(
    ed.app, ed.session, ed.panes, ed.keymaps, ed.document_flows,
    ed.explorer_tree, ed.prompt_bar, ed.message,
    has_modal_screen=ed.has_modal_screen,
    focus_editor=ed.focus_editor,
    focus_explorer=ed.focus_explorer,
    after_pane_focus=ed.after_pane_focus,
)
```

- 装配点：`_build_pane_stack` 尾部（document_flows 之后）；全部依赖此时就绪。
- R8：`document_flows` 以具体对象注入（split_with_path 两个调用 :882/:900），不设回调。

### ExplorerTree `window_prefix` 晚挂（本波唯一 L2 触点）

构造顺序矛盾：`_build_widgets`（:144-152）先建 explorer 并注入
`window_prefix=ed.try_window_prefix`（:150），而 WindowFlows 依赖 panes（后建）。

方案（采纳，零 lambda 直绑）：

1. `editor_view/explorer.py:114` 参数改为
   `window_prefix: Callable[[Key], bool] | None = None`；:369 调用点加 None 守卫：
   `if self.window_prefix is not None and self.window_prefix(event):`
2. editor.py:150 删实参；`_build_pane_stack` 建 window_flows 后直绑：
   `ed.explorer_tree.window_prefix = ed.window_flows.try_window_prefix`。
3. 安全性：`__init__` 全同步（`_build_widgets` → `_build_pane_stack` 之间无 await），
   无 Key 事件可到达；首个事件循环心跳在 `on_mount` 之后。

否决备选：转发 lambda `window_prefix=lambda e: ed.window_flows.try_window_prefix(e)`
——与本轮删除的薄委托同质，且把"何时可用"藏进闭包；晚挂把装配事实显式化。

### 文档修正

`try_window_prefix` docstring（:948-950）称 "Called from the editor view"——grep 实证
全仓仅两处调用：ExplorerTree 回调（explorer.py:369）与 `handle_key`（:773），
EditorView 从不调用；迁移时顺带修正表述。

## 三、调用方改直调（grep 驱动，断言语义不变）

| 位置 | 改动 |
|---|---|
| editor.py:773（handle_key） | `self.try_window_prefix(event)` → `self.window_flows.try_window_prefix(event)` |
| editor.py:74-79 / :300 | `_WINDOW_KEYS`、`self._window_pending = False` 删除（随迁） |
| editor.py imports | 删 `Axis`（:67，仅 :864/:889/:895 使用）；`VimMode` 从 :50 删（`VimKeymap` 保留，:110 构造仍用）；`Key`/`event_to_raw` 保留（:709/:806） |
| yate/commands.py:76/79/82/85 | `editor.split_with_path(...)` / `editor.only_pane()` / `editor.close_pane()` → `editor.window_flows.*`（:sp/:vs/:only/ctrl+w q） |
| tests/test_app_textual.py:2055/2058/2083/2088/2105 | `app.editor.window_pending` → `app.editor.window_flows.window_pending` |
| tools/smoke_test/scenarios/panes.py:72/75 | 同上跟随 |

## 四、规则同步（总纲 §六矩阵）

- `architecture-boundaries.md` §一 L3 流程模块枚举补 `window_flows.py`（plan-b 已把既有流程模块补全为连字符全名）。
- `tests/test_architecture.py` `UI_FROZEN_FILES` 增条目（window_flows 真实 import editor_view 的 panes/explorer/commandline）：

```python
"window_flows.py": {
    "yate.editor_view",
    "yate.editor_view.commandline",
    "yate.editor_view.explorer",
    "yate.editor_view.panes",
},
```

## 五、验收命令（全部退出码 0；探针退出码 1 = 通过）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
# 探针：目标成员已离开 editor.py（退出码 1 = 无命中）
Select-String -Path yate/editor.py -Pattern "def split_with_path|def try_window_prefix|_WINDOW_KEYS" ; echo "exit=$LASTEXITCODE"
# 冒烟：textual-pilot-smoke 窗格场景（ctrl+w h/j/k/l、:sp/:vs/:only、explorer 焦点往返）
```

## 六、提交

`refactor(editor): extract window pane flows`

## 七、风险与回滚

- 晚挂窗口期（构造期）无按键可达——同步构造保证；极端情形（未来有人在两工厂之间
  yield）守卫使 ctrl+w 弦静默不触发，属可接受降级，且 `window_prefix` 为 None 的
  explorer 行为与"未开 vim keymap"一致。
- 桩/测试若在 window_flows 装配前访问 `editor.window_flows` 将 AttributeError——
  现有测试全部经 pilot 全流程构造，无半构造访问（grep 已核）。
- 回滚：单提交 `git revert`。
