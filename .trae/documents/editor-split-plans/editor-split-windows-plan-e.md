# plan-e：抽取 WindowFlows（window_flows.py）

> 前置：plan-b（命名统一）、plan-c（删薄委托）、plan-d（DocumentFlows）已合入；
> 行号锚点：wave-2 后 editor.py 1196 行，2026-09-29 实测 grep 复核并更新
> （成员集与依赖取证不变，仅行号偏移）。

## 一、职责与迁移清单

`window_flows.py::WindowFlows` 承接 editor.py 的窗格/窗口命令簇与 vim `ctrl+w` 弦状态机。

迁移成员（9 方法 + 1 property + 1 模块常量）：

| 成员 | editor.py 行号 | 依赖取证 |
|---|---|---|
| `split_with_path` | :880 | `session.doc`（相对路径基准）、`open_path`（plan-d 后 `document_flows.open_path`）、`app.run_worker` |
| `_split_pane` | :905 | `app.run_worker` |
| `_split_pane_worker` | :911 | `panes.split_active`、`open_path_async`（→ `document_flows`）、`after_pane_focus` |
| `only_pane` | :921 | `panes.only_active` |
| `close_pane` | :930 | `panes.leaf_count`、`message`、`panes.close_active` |
| `resize_pane` | :940 | `panes.resize` / `panes.equalize`、`message` |
| `window_pending`（property） | :957 | `_window_pending` 状态 |
| `try_window_prefix` | :961 | `has_modal_screen`、`prompt_bar.active_mode`、`keymaps` + `VimKeymap`/`VimMode`、`message` |
| `_window_command` | :989 | `app.focused`、`explorer_tree`、`panes.cycle_focus`/`focus_direction`、`focus_editor`/`focus_explorer` |
| `_WINDOW_KEYS`（常量） | :70-79 | 纯数据 |

状态归属：`_window_pending`（editor.py:311 初始化）移入 `WindowFlows.__init__`。

`has_modal_screen`（editor.py:419-421）**留在 Editor**（读 `app.screen_stack`，`handle_key` 也用），以 `Callable[[], bool]` 注入。

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
- R8：`document_flows` 以具体对象注入（split_with_path 两个调用 :898/:916），不设回调。

### ExplorerTree `window_prefix` 晚挂（本波唯一 L2 触点）

构造顺序矛盾：`_build_widgets`（:117 起）先建 explorer 并注入
`window_prefix=ed.try_window_prefix`（:143），而 WindowFlows 依赖 panes（后建）。

方案（采纳，零 lambda 直绑）：

1. `editor_view/explorer.py:114` 参数改为
   `window_prefix: Callable[[Key], bool] | None = None`；:369 调用点加 None 守卫：
   `if self.window_prefix is not None and self.window_prefix(event):`
2. editor.py:143 删实参；`_build_pane_stack` 建 window_flows 后直绑：
   `ed.explorer_tree.window_prefix = ed.window_flows.try_window_prefix`。
3. 安全性：`__init__` 全同步（`_build_widgets` → `_build_pane_stack` 之间无 await），
   无 Key 事件可到达；首个事件循环心跳在 `on_mount` 之后。

否决备选：转发 lambda `window_prefix=lambda e: ed.window_flows.try_window_prefix(e)`
——与本轮删除的薄委托同质，且把"何时可用"藏进闭包；晚挂把装配事实显式化。

### 文档修正

`try_window_prefix` docstring（def :961 起）称 "Called from the editor view"——grep 实证
全仓仅两处调用：ExplorerTree 回调（explorer.py:369）与 `handle_key`（:789），
EditorView 从不调用；迁移时顺带修正表述。

## 三、调用方改直调（grep 驱动，断言语义不变）

| 位置 | 改动 |
|---|---|
| editor.py:789（handle_key） | `self.try_window_prefix(event)` → `self.window_flows.try_window_prefix(event)` |
| editor.py:70-79 / :311 | `_WINDOW_KEYS`、`self._window_pending = False` 删除（随迁） |
| editor.py imports | 删 `Axis`（:63，仅 split 簇使用）；`VimMode` 从 :47 删（`VimKeymap` 保留，:106 构造仍用）；`Key`（:27）/`event_to_raw`（:48）保留（键路由仍用） |
| yate/commands.py:76/79/82/85 | `editor.split_with_path(...)` / `editor.only_pane()` / `editor.close_pane()` → `editor.window_flows.*`（:sp/:vs/:only/ctrl+w q） |
| tests/test_app_textual.py（window_pending 相关） | `app.editor.window_pending` → `app.editor.window_flows.window_pending` |
| tools/smoke_test/scenarios/panes.py | 同上跟随 |

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

## 八、执行记录（wave-4 实测回填，2026-09-29）

**结果：全部门禁绿，已按 §六 提交。**

| 门禁 | 命令 | 实测结果 |
|---|---|---|
| pyright strict | `python -m pyright yate/ tests/ tools/` | **0 errors**（首跑 1 error：`window_flows.py:176` ctrl+w 提示串单参调用与 `Callable[[str, str], None]` 不符 → 补 `"info"` kind，复跑 0） |
| pytest 全量 | `python -m pytest tests/ -q --cov=yate --cov-fail-under=75` | 全绿，**覆盖率 90.70%**；`window_flows.py` 覆盖 89% |
| 架构守护 | `python -m pytest tests/test_architecture.py -q` | **20 passed** |
| 冒烟 | `python -m tools.smoke_test run` | **932/932 checks，89/89 scenarios，exit 0**（86.5s） |
| 探针 | `Select-String -Path yate/editor.py -Pattern "def split_with_path|def try_window_prefix|_WINDOW_KEYS"` | 无命中（成员已离开 editor.py） |

**editor.py 行数**：1089 → **958**（净 -131；numstat +28/-159：迁出窗格簇 9 方法 + property +
`_WINDOW_KEYS` 8 行 + `_window_pending` 初始化共 159 行，新增 WindowFlows 装配 19 行与
import/注解等 28 行）。
（口径勘误：此前摘要记录的"989"系 PowerShell `Measure-Object -Line` 非空行口径的误值；
本记录统一以 Python `splitlines()` 总行数为准，wave-3 收官真实值为 1089。）

**偏离与实施要点**（相对 §二/§三 计划文本）：

1. **装配点**：按 §二 定案在 `_build_pane_stack` 尾（`attach_pane_stack` 之后）构造
   `WindowFlows` 并 `ed.explorer_tree.window_prefix = ed.window_flows.try_window_prefix`
   —— 与 plan-d 的二段注入同构（explorer 构造于 `_build_widgets`，晚于装配点不可能，早于
   pane stack 是必然，故晚挂）。
2. **explorer.py 晚挂窗口守卫**：`window_prefix` 参数改 `Callable[[Key], bool] | None = None`，
   `on_key` 调用点加 `is not None` 守卫（与 wave-3 `open_path` 同模式）。
3. **try_window_prefix docstring 修正**：原文写"Called from the editor view"，实际两个调用方是
   `ExplorerTree.on_key`（keymap 派发前，vim keymap 会吞未映射键）与 `Editor.handle_key`；
   window_flows.py 中已按事实改写。
4. **`_message` 单参调用补 kind**：ctrl+w 提示串调用补第二参数 `"info"`（pyright 报错驱动，
   与 wave-3 约定一致）。
5. **handle_key docstring**：`try_window_prefix` 交叉引用改为
   `window_flows.try_window_prefix`（原 `:meth:` 指向已删除的编辑器方法）。
6. **调用方改写清单**（grep 全仓驱动，无漏网）：`commands.py` 4 处 →
   `editor.window_flows.*`；smoke `panes.py` 2 处与 `test_app_textual.py` 5 处
   `app.editor.window_pending` → `app.editor.window_flows.window_pending`；
   `test_architecture.py` `UI_FROZEN_FILES` 增 `window_flows.py`
   （commandline/explorer/panes，与 document_flows 同组面）；规则文本 §一 L3 枚举与 R11 同步。
