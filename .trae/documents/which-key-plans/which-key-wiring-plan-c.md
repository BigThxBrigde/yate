# which-key 子计划 c：L3 接线（WhichKeyFlows + Editor 组装 + 内置表 + 守卫登记）

wave-2（串行，依赖 wave-1 的 plan-a / plan-b 全部验收通过）。自包含任务书。
**跨架构边界子计划**：触发 R9 / R11 / R5 / R7 / §三.8，见文末条款对照。

## 输入（调研事实）

- 每次按键的刷新通道：[editor.py](../../../yate/editor.py)
  `handle_raw_key`（:698-711）分发后必调 `refresh_ui()`（:561-567）→
  `_refresh_chrome`（:578-582）；但 `handle_key`（:592-696）里
  `try_window_prefix` 命中分支（:656-657）直接 `return True` 不刷新。
- vim 挂起态读取：plan-a 交付的 `Keymap.pending_prefix()`；
  ctrl+w 挂起态：[window_flows.py](../../../yate/flows/window_flows.py)
  `window_pending` 属性（:155-158）与 `_WINDOW_KEYS`（:32-37）。
- 绑定表候选计算的数据形态：`KeyBinding.key` 是 vim 式 spec 字符串
  （`"dd"` / `"d{motion}"` / `"f{char}"` / `'"(a-z}'` / raw 字节）；
  raw 键的人读形经 `keymaps.keys.key_name`（如 `\x04` → `<ctrl-d>`）。
- 流程模块接入清单（§三.8 六步）与命名纪律：`*Flows`；共享回调词汇
  `MessageFn` / `StateQuery` 在 [flows/__init__.py](../../../yate/flows/__init__.py)。
- 内置表落点：[actions.py](../../../yate/actions.py) `populate`（:26，
  help 在 :226）、[commands.py](../../../yate/commands.py)
  `register_commands`（:156，`list-extensions` 报告模式在 :457）。
- 报告输出通道：[overlay_flows.py](../../../yate/flows/overlay_flows.py)
  `show_output(title, text)`（:108-111）→ `OutputScreen`（[modals.py:102](../../../yate/editor_view/modals.py)）。
- L2 组件挂载：`#bottom` Vertical 组合点 [editor.py](../../../yate/editor.py)
  :466-470；属性声明区 :336-370；`_build_widgets` 内 status_bar 构造 :156-159。
- 架构守卫登记面：[test_architecture.py](../../../tests/test_architecture.py)
  `UI_FROZEN_FILES`（:196-252），测试断言「九个 flows 键」的注释在 :799-803
  （登记后须同步数字）。

## 目标

1. 新建 L3 流程模块 `WhichKeyFlows`：候选集计算 + 面板驱动 + toggle 钉住态
   + 冲突报告出口（§三.8 全六步落地）。
2. `Editor` 组装面板与流程：compose 进 `#bottom`、id=`#which-key`（R9）、
   每键刷新、ctrl+w 分支补刷新。
3. 内置表登记 `toggle_whichkey` action 与 `:check-keys` 命令（R5/R7）。
4. 架构守卫登记 `flows/whichkey_flows.py` 的 editor_view 冻结耦合（R11）。

## 非目标

- 不改 `EditorView` / `statusbar.py`（面板独立于状态栏，R14 例外面不再扩大）；
- 不新增 Protocol / 共享 context 类型；不做 yaterc 配置项；
- 不在 vsc 模式做前缀自动弹出（vsc 无前缀态，只有钉住模式，见主计划）。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `yate/flows/whichkey_flows.py` | 新建（预计 ~190 行） |
| `yate/editor.py` | 修改（5 处小改） |
| `yate/actions.py` | 修改（+1 注册） |
| `yate/commands.py` | 修改（+1 注册） |
| `tests/test_architecture.py` | 修改（白名单 +1 键、注释计数同步） |
| `tests/test_whichkey_flows.py` | 新建 |

## 具体修改

### 1. [whichkey_flows.py](../../../yate/flows/whichkey_flows.py) — 新建

单一职责：把「活动 keymap 的绑定表 + 挂起 chord 态」翻译成面板条目并驱动面板；
不含渲染。依赖（全部向下）：`yate.flows`（MessageFn/StateQuery）、
`yate.keymaps.conflicts`、`yate.keymaps.registry.KeymapSet`、
`yate.keymaps.keys.key_name`、`yate.editor_view.whichkey`（R11 冻结登记）。

```python
type PendingQuery = StateQuery          # window_flows.window_pending 的只读探针

class WhichKeyFlows:
    """Drives the which-key panel from the active keymap's state."""

    def __init__(
        self,
        keymaps: KeymapSet,
        window_pending: StateQuery,
        panel: WhichKeyPanel,
        message: MessageFn,
    ) -> None: ...

    def refresh(self) -> None:
        """Recompute panel visibility after one dispatch (called per key)."""

    def toggle(self) -> None:
        """Pin / unpin the full keymap sheet (the <f9> / action entry)."""

    def conflicts_report(self) -> str:
        """The :check-keys report body for the active keymap."""
```

`refresh()` 判定序（互斥，先命中先显示）：

1. `self._pinned` → 整表钉住模式：`_sheet_entries()` 按绑定表
   `category` 分组全量渲染（描述缺失时回退 `str(binding.action)`，与
   HelpScreen [modals.py:77](../../../yate/editor_view/modals.py) 同策略）。
2. `self._window_pending()` → ctrl+w chord：渲染模块级常量
   `WINDOW_CHORDS: tuple[ChordEntry, ...]`（h/j/k/l/s/v/q/o/ctrl+w/+/-/</>/=
   十四条，文案与 [window_flows.py:183-186](../../../yate/flows/window_flows.py)
   的提示串一致），header = `ctrl+w`。
3. `pending := self.keymaps.active.pending_prefix()` 非空 → 候选模式：
   `_candidates(pending)`，header = pending。
4. 其余 → `panel.clear()`。

`_candidates(pending: str) -> list[ChordEntry]` 匹配规则（写入 docstring）：

- spec 是 raw 字节（非可打印首字符）→ 展开为单步 `key_name(raw)`；
- spec 首字符可打印 → 取首字符为第一步；
- 条目入选当且仅当 `pending` 是该 spec 的**字面前缀**且 spec 严格长于
  pending（`spec.startswith(pending) and len(spec) > len(pending)`）——
  占位符 `{...}` 只出现在首字符之后，字面前缀判定安全；
- 同 key 去重（保留先出现者），空结果时条目列表为空（面板仅显 header）。

`conflicts_report()`：`find_key_conflicts(self.keymaps.active,
reserved=RESERVED_KEYS if self.keymaps.name == "vim" else frozenset())` →
`format_conflicts(self.keymaps.name, conflicts)`。

pyright strict 全签名注解；模块级 `log = tracing.get_logger(__name__)`；
**不持有 App 句柄**（守卫 `test_flow_modules_hold_no_app_handle`）。

### 2. [editor.py](../../../yate/editor.py) — 五处

2a. 导入区（:47 flows 组）：`from yate.flows.whichkey_flows import WhichKeyFlows`；
`from yate.editor_view.whichkey import WhichKeyPanel`。

2b. 属性声明区（:355 附近，status_bar 之后）：
`which_key_panel: WhichKeyPanel`、`whichkey: WhichKeyFlows`。

2c. `_build_widgets`（:156-159 status_bar 构造之后）：
`ed.which_key_panel = WhichKeyPanel(id="which-key")`。

2d. `_build_pane_stack` 尾部（:313 `ed.explorer_tree.window_prefix = ...`
之后，window_flows 已存在）：

```python
ed.whichkey = WhichKeyFlows(
    keymaps=ed.keymaps,
    window_pending=lambda: ed.window_flows.window_pending,
    panel=ed.which_key_panel,
    message=ed.message,
)
```

2e. 组合（:466-470）：`#bottom` 内首个 yield `self.which_key_panel`
（statusbar 之上、prompt 之上）。
另两处刷新钩子：

- `_refresh_chrome`（:578-582）追加 `self.whichkey.refresh()`；
- `handle_key` 的 ctrl+w 命中分支（:656-657）改为
  `if self.window_flows.try_window_prefix(event):`
  &nbsp;&nbsp;`self.whichkey.refresh()` / `return True`（缩进按现有风格）。

### 3. [actions.py](../../../yate/actions.py) — `populate` 内 help 注册（:226）旁

```python
reg("toggle_whichkey", lambda ctx: editor.whichkey.toggle(),
    "Toggle the which-key panel")
```

### 4. [commands.py](../../../yate/commands.py) — `register_commands` 内
（`list-extensions` :457 附近同区）

```python
def _check_keys(args: str) -> None:
    editor.overlays.show_output("key conflicts", editor.whichkey.conflicts_report())

reg("check-keys", _check_keys, "report key binding conflicts")
```

### 5. [test_architecture.py](../../../tests/test_architecture.py) — 两处

- `UI_FROZEN_FILES`（:196-252）追加：
  `"flows/whichkey_flows.py": {"yate.editor_view", "yate.editor_view.whichkey"}`；
- :799-803 断言注释里的 flows 键计数「nine」改「ten」（并核对该用例是否
  内嵌数量断言，若有同步为实际键数）。

## 新增测试

### tests/test_whichkey_flows.py（新建；沿用 test_vim_keymap.py 的
ActionContext/KeyUi 替身手法构造 keymaps）

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_refresh_shows_candidates_while_vim_chord_pending` | `VimKeymap` 收到 `"d"` 后的 `KeymapSet` | `flows.refresh()` | 面板收到 `show_entries("d", ...)`，条目含 `dd` 与 `d{motion}` 两 key 标签 |
| `test_refresh_clears_panel_when_idle` | 无挂起态 | `refresh()` | 面板 `clear` 被调用（替身面板记录调用） |
| `test_refresh_shows_window_chords_while_ctrlw_pending` | `window_pending` 替身返回 `True` | `refresh()` | 条目 key 集合含 `q`、`s`、`v`、`ctrl+w`，header 为 `ctrl+w` |
| `test_candidates_exclude_completed_and_unrelated_specs` | pending `"d"` | `_candidates("d")` | 含 `dd` / `d{motion}`；不含 `"doc start"`（spec `G`）、不含 `y{motion}` |
| `test_refresh_prefers_pinned_sheet_over_pending` | pinned=True 且 pending `"d"` | `refresh()` | 渲染为分组全量表（含 category 头），非候选模式 |
| `test_toggle_flips_pin_and_clears_on_unpin` | 初始未钉 | `toggle()` 后 `refresh()`；再 `toggle()` 后 `refresh()` | 第一次显示整表，第二次 `clear` 被调用 |
| `test_vsc_never_autoshows_without_pin` | `KeymapSet` 活动为 vsc、未钉 | 逐键喂 `d`、`"`、`2` 后 `refresh()` | 面板始终收到 `clear`（vsc 无挂起态） |
| `test_conflicts_report_uses_reserved_keys_only_for_vim` | 构造含 raw `"1"` 绑定的 vsc / vim 两个 set | 分别调 `conflicts_report()` | vsc 报告 `no conflicts`；vim 报告含 `reserved` |
| `test_flow_holds_no_app_handle` | 源码静态 | AST 断言模块无 `self.app` 属性链 | 断言通过（与守卫 22 同语义的本模块回归） |

### tests/test_architecture.py 守卫用例（落在既有用例内，无新用例名）

- `test_collaborators_keep_widget_coupling_frozen`：新键登记后正向通过、
  未登记导入会被拦截（负向演练由执行者临时删白名单确认后还原）。

## 验收命令

```text
.venv\Scripts\python.exe -m pytest tests/test_whichkey_flows.py tests/test_whichkey_panel.py tests/test_keymaps_conflicts.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pyright yate/ tests/
.venv\Scripts\python.exe -m pytest tests/ -q --cov-fail-under=0
```

通过判定：全部退出码 0（pyright strict 零诊断；35 项架构守卫全绿，
`test_collaborators_keep_widget_coupling_frozen` 带新白名单键）。
手工冒烟（UI，不可自动化）：`.venv\Scripts\python.exe -m yate` 打开文本 →
vim 键位下按 `d`：面板出现在状态栏上方并列出 `dd` / `d{motion}`；
`esc` 后消失；`<f9>` 钉住全表、再按消失；vsc 下按 `<ctrl+w>`（vim only，
vsc 应无自动弹出）、`<f9>` 钉住分组全表；`:check-keys` 弹出报告浮层。

## 风险与回滚

- `_refresh_chrome` 每键调用 `_candidates` 扫绑定表：表 ~60 条 O(n)，
  无需缓存（不做预优化）；若实测热路径劣化再议（记录于回填）。
- ctrl+w 分支补刷新可能重复刷新（raw 路径已刷）：幂等渲染，无正确性风险。
- `<f9>` 在个别终端不可达：action 名与 `:check-keys` 命令是双通道冗余；
  文档（plan-d）注明。
- R11 白名单漏登记 → 架构测试红，验收命令 2 拦截。
- 回滚：`whichkey_flows.py` 删除 + editor.py 五处逐条还原（compose 一处 /
  build 两处 / chrome 一处 / handle_key 一处）+ 两表各删一段 + 白名单键删除；
  面板组件保留不影响运行（无 import 即死代码，最终一并删除）。
