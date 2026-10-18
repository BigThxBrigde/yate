# which-key 子计划 d：L3 流程模块（WhichKeyFlows）

wave-2（串行，依赖 wave-1 的 plan-a `pending_prefix()`、plan-b
`find_key_conflicts`、plan-c `WhichKeyPanel` 全部验收通过）。自包含任务书。

## 输入（调研事实）

- vim 挂起态读取：plan-a 交付的 `Keymap.pending_prefix()`（vim 覆写、vsc 恒空）；
  ctrl+w 挂起态：[window_flows.py](../../../yate/flows/window_flows.py)
  `window_pending` 属性（:155-158）与 `_WINDOW_KEYS`（:32-37），第二键文案在
  :183-186。
- 绑定表候选计算的数据形态：`KeyBinding.key` 是 vim 式 spec 字符串
  （`"dd"` / `"d{motion}"` / `"f{char}"` / `'"(a-z}'` / raw 字节）；
  raw 键的人读形经 `keymaps.keys.key_name`（如 `\x04` → `<ctrl-d>`）。
- 流程模块接入清单（§三.8 六步，本计划走第 1 步命名；第 2-5 步 editor 侧
  接线归 plan-e）与命名纪律：`*Flows`；共享回调词汇 `MessageFn` /
  `StateQuery` 在 [flows/__init__.py](../../../yate/flows/__init__.py)。
- 描述回退策略范本：HelpScreen 缺描述时回退 `str(binding.action)`
  （[modals.py:77](../../../yate/editor_view/modals.py)）。
- 冲突报告数据源：plan-b 的 `find_key_conflicts` / `format_conflicts` 与
  plan-a 的 `VimKeymap.RESERVED_KEYS`。
- 面板推送接口：plan-c 的 `WhichKeyPanel.show_entries(header, entries)` /
  `clear()` 与 `ChordEntry`。
- 架构守卫事实：R11 要求 flows 新增 `editor_view` 导入前先登记
  `UI_FROZEN_FILES`；该登记文件 `tests/test_architecture.py` 为 plan-e 独占
  （wave-3），故本计划验收**不跑** R11 耦合用例（见验收节说明）。

## 目标

新建 L3 流程模块 `WhichKeyFlows`（预计 ~190 行）：把「活动 keymap 的绑定表 +
挂起 chord 态」翻译成面板条目并驱动面板 —— 候选集计算 + 面板驱动 +
toggle 钉住态 + 冲突报告出口；不含渲染、不持 App 句柄。

## 非目标

- 不改 `Editor`（组装 / 刷新钩子归 plan-e）、不登记内置表与架构白名单
  （归 plan-e）；
- 不做渲染（归 plan-c 组件）；不做 yaterc 配置项；
- 不在 vsc 模式做前缀自动弹出（vsc 无前缀态，只有钉住模式，见主计划）。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `yate/flows/whichkey_flows.py` | 新建 |
| `tests/test_whichkey_flows.py` | 新建 |

## 具体修改

### [whichkey_flows.py](../../../yate/flows/whichkey_flows.py) — 新建

依赖（全部向下）：`yate.flows`（MessageFn/StateQuery）、
`yate.keymaps.conflicts`、`yate.keymaps.registry.KeymapSet`、
`yate.keymaps.keys.key_name`、`yate.editor_view.whichkey`（R11 冻结登记，
随 plan-e 落地）、stdlib `tracing`。

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
   `category` 分组全量渲染（描述缺失时回退 `str(binding.action)`，
   与 HelpScreen [modals.py:77](../../../yate/editor_view/modals.py) 同策略）。
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

`toggle()`：翻转 `self._pinned` 布尔并立即 `refresh()`。

`conflicts_report()`：`find_key_conflicts(self.keymaps.active,
reserved=RESERVED_KEYS if self.keymaps.name == "vim" else frozenset())` →
`format_conflicts(self.keymaps.name, conflicts)`。

pyright strict 全签名注解；模块级 `log = tracing.get_logger(__name__)`（R12）；
**不持有 App 句柄**（守卫 `test_flow_modules_hold_no_app_handle`）。

## 新增测试

### tests/test_whichkey_flows.py（新建；沿用 test_vim_keymap.py 的
ActionContext/KeyUi 替身手法构造 keymaps，替身面板记录 show_entries/clear 调用）

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

## 验收命令（worktree venv）

```text
.venv\Scripts\python.exe -m pytest tests/test_whichkey_flows.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pyright yate/flows/whichkey_flows.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q --cov-fail-under=0 -k "not test_collaborators_keep_widget_coupling_frozen"
```

通过判定：三条命令退出码 0。**已知时序**：本模块 import
`yate.editor_view.whichkey`，而 R11 白名单键随 plan-e（wave-3）登记于
`tests/test_architecture.py`（wave-1 已确认 `test_architecture.py` 非本计划
独占，故用 `-k` 排除该耦合用例），故 plan-d 验收面不含它；plan-e 登记后
以**全量**架构测试（无 `-k`）复绿并含负向演练。

## 风险与回滚

- R11 白名单时序窗口（本计划合入后至 plan-e 之前，架构测试全量跑会红）：
  已在验收节显式声明，波次纪律保证 wave-3 紧随执行；若中断需回滚本文件
  以恢复门禁绿。
- `refresh()` 每键调用 `_candidates` 扫绑定表：表 ~60 条 O(n)，
  无需缓存（不做预优化）；若实测热路径劣化再议（记录于回填）。
- 判定序错位（如 pinned 未优先）：`test_refresh_prefers_pinned_sheet_over_pending`
  钉住顺序语义。
- 回滚：删除 `whichkey_flows.py` 即整体下线（plan-e 接线前无消费者），
  无迁移状态。
