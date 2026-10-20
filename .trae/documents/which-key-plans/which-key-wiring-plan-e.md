# which-key 子计划 e：L3 接线与内置表（Editor 组装 + actions/commands + 守卫登记）

wave-3（串行，依赖 wave-2 的 plan-d `WhichKeyFlows` 验收通过；
plan-a / plan-c 产物亦须在位）。自包含任务书。
**跨架构边界子计划**：触发 R9 / R11 / R5 / R7 / §三.8，见文末条款对照。

## 输入（调研事实）

- 每次按键的刷新通道：[editor.py](../../../yate/editor.py)
  `handle_raw_key`（:698-711）分发后必调 `refresh_ui()`（:561-567）→
  `_refresh_chrome`（:578-582）；但 `handle_key`（:592-696）里
  `try_window_prefix` 命中分支（:656-657）直接 `return True` 不刷新。
- L2 组件挂载：`#bottom` Vertical 组合点 [editor.py](../../../yate/editor.py)
  :466-470；属性声明区 :336-370；`_build_widgets` 内 status_bar 构造 :156-159；
  `_build_pane_stack` 尾部 `ed.explorer_tree.window_prefix = ...`（:313 附近，
  window_flows 已存在）。
- 内置表落点：[actions.py](../../../yate/actions.py) `populate`（:26，
  help 在 :226）、[commands.py](../../../yate/commands.py)
  `register_commands`（:156，`list-extensions` 报告模式在 :457）。
- 报告输出通道：[overlay_flows.py](../../../yate/flows/overlay_flows.py)
  `show_output(title, text)`（:108-111）→ `OutputScreen`（[modals.py:102](../../../yate/editor_view/modals.py)）。
- 架构守卫登记面：[test_architecture.py](../../../tests/test_architecture.py)
  `UI_FROZEN_FILES`（:196-252），测试断言 flows 键计数的注释在 :799-803
  （登记后须同步数字）。
- §三.8 接入清单第 2-5 步（类属性 / 工厂构造 / 组装顺序注释 / R11 登记）
  全在本计划的 `editor.py` 与 `test_architecture.py` 面内；第 1 步命名与
  模块本体已随 plan-d 落地，第 6 步规则清单同步归 plan-f。

## 目标

1. `Editor` 组装面板与流程：属性声明、`_build_widgets` 构造面板（id=
   `which-key`，R9）、`_build_pane_stack` 构造 `WhichKeyFlows`、compose 进
   `#bottom`、每键刷新 + ctrl+w 分支补刷新（§三.8 步 2-4）。
2. 内置表登记 `toggle_whichkey` action 与 `:check-keys` 命令（R5/R7）。
3. 架构守卫登记 `flows/whichkey_flows.py` 的 editor_view 冻结耦合（R11，
   §三.8 步 5），含负向演练。
4. 全量门禁复绿（pyright + 全量 pytest + 35 项架构守卫无 `-k`）与手工冒烟。

## 非目标

- 不改 `EditorView` / `statusbar.py`（面板独立于状态栏，R14 例外面不再扩大）；
- 不改 `flows/whichkey_flows.py`（plan-d 独占）与面板组件（plan-c 独占）；
- 不新增 Protocol / 共享 context 类型；不做 yaterc 配置项；
- 不写规则文本 / 手册（归 plan-f）。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `yate/editor.py` | 修改（导入 / 属性 / 两处构造 / 组合 / 两处刷新，共约 7 小处） |
| `yate/actions.py` | 修改（+1 注册） |
| `yate/commands.py` | 修改（+1 注册） |
| `tests/test_architecture.py` | 修改（白名单 +1 键、注释计数同步） |

## 具体修改

### 1. [editor.py](../../../yate/editor.py) — 七小处

1a. 导入区（:47 flows 组）：`from yate.flows.whichkey_flows import WhichKeyFlows`；
`from yate.editor_view.whichkey import WhichKeyPanel`。

1b. 属性声明区（:355 附近，status_bar 之后）：
`which_key_panel: WhichKeyPanel`、`whichkey: WhichKeyFlows`。

1c. `_build_widgets`（:156-159 status_bar 构造之后）：
`ed.which_key_panel = WhichKeyPanel(id="which-key")`（R9：id 由 Editor 传）。

1d. `_build_pane_stack` 尾部（:313 `ed.explorer_tree.window_prefix = ...`
之后，window_flows 已存在）：

```python
ed.whichkey = WhichKeyFlows(
    keymaps=ed.keymaps,
    window_pending=lambda: ed.window_flows.window_pending,
    panel=ed.which_key_panel,
    message=ed.message,
)
```

1e. `Editor.__init__` 组装顺序注释（§三.8 步 4，按现有注释格式追加一行，
注明 whichkey 依赖 keymaps / window_flows / which_key_panel 已就绪）。

1f. 组合（:466-470）：`#bottom` 内首个 yield `self.which_key_panel`
（statusbar 之上、prompt 之上）。

1g. 两处刷新钩子：

- `_refresh_chrome`（:578-582）追加 `self.whichkey.refresh()`；
- `handle_key` 的 ctrl+w 命中分支（:656-657）改为
  `if self.window_flows.try_window_prefix(event):`
  &nbsp;&nbsp;`self.whichkey.refresh()` / `return True`（缩进按现有风格）。

### 2. [actions.py](../../../yate/actions.py) — `populate` 内 help 注册（:226）旁

```python
reg("toggle_whichkey", lambda ctx: editor.whichkey.toggle(),
    "Toggle the which-key panel")
```

### 3. [commands.py](../../../yate/commands.py) — `register_commands` 内
（`list-extensions` :457 附近同区）

```python
def _check_keys(args: str) -> None:
    editor.overlays.show_output("key conflicts", editor.whichkey.conflicts_report())

reg("check-keys", _check_keys, "report key binding conflicts")
```

### 4. [test_architecture.py](../../../tests/test_architecture.py) — 两处

- `UI_FROZEN_FILES`（:196-252）追加：
  `"flows/whichkey_flows.py": {"yate.editor_view", "yate.editor_view.whichkey"}`；
- :799-803 断言注释里的 flows 键计数「nine」改「ten」（并核对该用例是否
  内嵌数量断言，若有同步为实际键数）。

## 验收命令（worktree venv）

```text
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pyright yate/ tests/
.venv\Scripts\python.exe -m pytest tests/ -q --cov-fail-under=0
```

通过判定：三条命令退出码 0（pyright strict 零诊断；35 项架构守卫全绿、
无 `-k` 排除，`test_collaborators_keep_widget_coupling_frozen` 带新白名单键）。
守卫负向演练（执行者做）：临时删白名单键 → 架构测试红 → 还原后绿。

手工冒烟（UI，不可自动化）：`.venv\Scripts\python.exe -m yate` 打开文本 →
vim 键位下按 `d`：面板出现在状态栏上方并列出 `dd` / `d{motion}`；
`esc` 后消失；`<f9>` 钉住全表、再按消失；vsc 下按 `<ctrl+w>`（vim only，
vsc 应无自动弹出）、`<f9>` 钉住分组全表；`:check-keys` 弹出报告浮层。

## 架构条款对照

| 条款 | 触碰 | 处置 / 守卫 |
|---|---|---|
| R9 | 新 widget id `#which-key` | `Editor` 传 id；样式组件自持（`#statusbar` 先例，tcss 由 plan-c 交付）；外壳 `app.tcss` 无需改动；规则 R9 清单回写随 plan-f |
| R11 | flows 新增 editor_view 导入 | `UI_FROZEN_FILES` 本计划登记；守卫 `test_collaborators_keep_widget_coupling_frozen`（含负向演练） |
| R5/R7 | action / command 走内置表 | `actions.py` / `commands.py` 各 +1 注册，外壳装载路径不变；守卫 `test_editor_does_not_import_action_tables` / `test_shell_loads_the_builtin_tables` |
| §三.8 | 流程模块接入 | 步 2-4（类属性 / 工厂 / 顺序注释）+ 步 5（白名单）在本计划；守卫 `test_flow_modules_hold_no_app_handle` / 命名守卫 |

## 风险与回滚

- R11 白名单漏登记 / 注释计数不同步 → 验收命令 1 直接拦截。
- ctrl+w 分支补刷新可能重复刷新（raw 路径已刷）：幂等渲染，无正确性风险；
  既有 `handle_key` 相关回归用例随全量 pytest 覆盖。
- `<f9>` 个别终端不可达：action 名与 `:check-keys` 命令是双通道冗余；
  手册（plan-f）注明。
- 回滚：`editor.py` 七小处逐条还原（导入 1 / 属性 1 / 构造 2 / 顺序注释 1 /
  组合 1 / 刷新 2）+ 两表各删一段 + 白名单键删除；`git checkout --
  yate/editor.py yate/actions.py yate/commands.py tests/test_architecture.py`
  即退回 wave-2 状态（`whichkey_flows.py` 成为无消费者死代码，可保留或
  随波回滚）。
