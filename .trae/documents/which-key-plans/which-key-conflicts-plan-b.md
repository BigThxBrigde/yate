# which-key 子计划 b：L1 冲突扫描（keymaps/conflicts.py）

wave-1（与 plan-a、plan-c 并行，文件互不重叠）。自包含任务书：输入、独占文件、
具体修改、测试、验收、风险。

## 输入（调研事实）

- [keymaps/base.py](../../../yate/keymaps/base.py) 的 `Keymap`：`bindings`
  列表（表序即注册序）与 `_index`（raw key → `KeyBinding`，后者居后者遮蔽）；
  `add_binding` 原位替换（同 raw 只留一条，正常注册不产生重复）。
- 被 vim 硬编码分支抢占的 raw 键（扫描的 `reserved` 事实来源，常量本体登记在
  plan-a 的 `vim.py`，本计划只以 `reserved: frozenset[str]` 参数消费，
  不 import `vim.RESERVED_KEYS`）：`\x1b`、`\x1bc`、`\x07`、`\x04`、`\x15`、
  `\x06`、`\x02`、`\x12` 与 `1`-`9`（行号见 plan-a 输入节）。
- raw 键的人读形经 [keymaps/keys.py](../../../yate/keymaps/keys.py) 的
  `key_name`（如 `\x1b` → `<esc>`、`\x04` → `<ctrl-d>`）。
- 报告消费方：L3 `:check-keys` 命令（plan-e 接线），形态参考
  [diagnostics.py](../../../yate/diagnostics.py) 的 `format_report` 文本报告
  （纯函数、零 UI）。
- 约束：R4 —— `keymaps/*` 不得 import `editor_view`；本模块纯逻辑天然满足。

## 目标

新增纯逻辑模块 `yate/keymaps/conflicts.py`（预计 ~110 行）：对一个 `Keymap`
的绑定表做两类冲突扫描（duplicate / reserved）与报告格式化；L1 零 UI 导入。
wave-2 的 plan-d 将以 `find_key_conflicts` + `format_conflicts` 组装
`:check-keys` 报告体。

## 非目标

- 不 import `yate.keymaps.vim`（`reserved` 由调用方按 keymap 名注入，
  保持模块与具体 keymap 解耦，也保证 wave-1 内与 plan-a 并行可跑）。
- 不检测「绑定指向未注册 action」（见主计划非目标）。
- 不做观测钩子 / F9 绑定（归 plan-a）、不做报告出口接线（归 plan-d / plan-e）。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `yate/keymaps/conflicts.py` | 新建 |
| `tests/test_keymaps_conflicts.py` | 新建 |

## 具体修改

### [conflicts.py](../../../yate/keymaps/conflicts.py) — 新建

单一职责：扫描一个 `Keymap` 的绑定表并格式化报告；只 import
`yate.keymaps.base`（同包绝对导入，`test_no_relative_imports`）、
`yate.keymaps.keys.key_name` 与 stdlib `collections.Counter`。
签名与语义为准，docstring 按 python-coding-style §二写全：

```python
@dataclass(frozen=True)
class KeyConflict:
    """One detected keymap conflict and the bindings that collide."""
    raw: str                     # the colliding raw key
    reason: Literal["duplicate", "reserved"]
    bindings: tuple[KeyBinding, ...]   # every table entry involved

def find_key_conflicts(
    keymap: Keymap, reserved: frozenset[str] = frozenset(),
) -> list[KeyConflict]:
    """Scan *keymap*'s binding table; sorted by ``key_name(raw)``.

    ``duplicate``: the same raw key appears twice in ``bindings`` -- the
    later entry shadows the earlier one in ``_index``.  ``reserved``: the
    raw key is consumed before the table is consulted (e.g. vim's
    RESERVED_KEYS), so the binding can never dispatch.  Bindings
    registered through ``add_binding`` replace in place and are reported
    only if the table still holds a stale twin.
    """

def format_conflicts(
    keymap_name: str, conflicts: list[KeyConflict],
) -> str:
    """The ``:check-keys`` report body (human text, no UI imports)."""
```

判定与格式细则：

- `duplicate` 判定用 `Counter(b.key for b in keymap.bindings)`；
  `reserved` 判定 `b.key in reserved`；同一 raw 同时命中两类时输出两条冲突；
- 排序按 `key_name(raw)` 升序（同 raw 的 duplicate 条目排在 reserved 前）；
- 报告行格式：`<key>  <reason>  action1 -> action2`，附头部
  `keymap: <name> -- N conflict(s)`；无冲突时输出
  `keymap: <name> -- no conflicts`。

## 新增测试

### tests/test_keymaps_conflicts.py（新建，纯逻辑、无 Textual；reserved 集合
一律用字面量构造，不 import `vim.RESERVED_KEYS`——保证 wave-1 内与 plan-a
并行时本测试独立可绿）

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_duplicate_raw_key_is_reported` | 手工构造 `Keymap` 子类，`build_bindings` 返回两条同 raw `KeyBinding("x", "a1", ...)`、`KeyBinding("x", "a2", ...)` | `find_key_conflicts(km)` | 恰 1 条冲突，`reason == "duplicate"`，`bindings` 两条皆在且按表序 |
| `test_reserved_key_binding_is_reported` | 上述构造表，另追加 `KeyBinding("1", "x")` | `find_key_conflicts(km, reserved=frozenset({"1"}))` | 含 raw `"1"` 的 `reserved` 冲突，其 `bindings` 含该表项 |
| `test_clean_table_reports_nothing` | `VscKeymap()`（表内无重复、不传 reserved） | `find_key_conflicts(vsc)` | 返回 `[]` |
| `test_conflicts_sorted_by_key_label` | 构造 raw `"\x1b"` 与 `"zz"` 两条 reserved 冲突 | `find_key_conflicts` | 首条 label `<esc>` 在 `z` 之前 |
| `test_format_conflicts_lists_actions` | 上文 duplicate 冲突 | `format_conflicts("vim", conflicts)` | 文本含 `keymap: vim`、`x`、`a1`、`a2`；空表输入含 `no conflicts` |

## 验收命令（worktree venv）

```text
.venv\Scripts\python.exe -m pytest tests/test_keymaps_conflicts.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pyright yate/keymaps/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q --cov-fail-under=0
```

通过判定：三条命令退出码 0；`test_clean_table_reports_nothing` 证明对现役
`VscKeymap` 表零误报；架构测试确认 R4（`keymaps/` UI-free）仍绿。

## 风险与回滚

- `reserved` 参数化导致调用方漏传（vim 漏传 → 漏报 reserved 类）：
  集成判定收在 plan-d 的 `test_conflicts_report_uses_reserved_keys_only_for_vim`
  （wave-2，依赖 plan-a 常量落地后）。
- `duplicate` 误报 `add_binding` 的正常替换：`add_binding` 原位替换不留双胞，
  测试 `test_clean_table_reports_nothing` 反向验证。
- 回滚：删除 `conflicts.py` 即整体下线（plan-d 未接线前无任何消费者），
  无迁移状态。
