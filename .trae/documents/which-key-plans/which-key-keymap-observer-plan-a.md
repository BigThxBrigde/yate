# which-key 子计划 a：L1 键位观测（pending_prefix + RESERVED_KEYS + F9 绑定）

wave-1（与 plan-b、plan-c 并行，文件互不重叠）。自包含任务书：输入、独占文件、
具体修改、测试、验收、风险。

## 输入（调研事实）

- [keymaps/base.py](../../../yate/keymaps/base.py) 的 `Keymap`（:89-105）持有
  `bindings` 列表与 `_index`（raw key → `KeyBinding`），`handle_key`（:174-179）
  单键分发；vsc 为无状态单键，无挂起态。
- [keymaps/vim.py](../../../yate/keymaps/vim.py) 的挂起 chord 全部是实例字段
  （:96-111）：`mode` / `op` / `prefix` / `count_str` / `pending_register`
  / `op_count` / `op_register`；`_clear_pending`（:249-254）统一清空。
  键入顺序约定：`"`register → count → operator → prefix（如 `"a2df`）。
- [keymaps/vim.py](../../../yate/keymaps/vim.py) 在绑定表查找之前硬编码消费的键
  （对这些键的绑定永远不会生效）：`\x1b`（:459）、`\x1bc`（:464）、`\x07`（:469）、
  `\x04` / `\x15` / `\x06` / `\x02`（:598-617）、`\x12`（:588）；数字 `1`-`9`
  恒被 count 吞掉（:484-489），`0` 仅在 count 非空时被吞。`<f1>`-`<f12>`
  经 `_FUNCTION_KEYS` 分支仍走 `lookup`（:218-227），不算被抢占。
  —— 本常量由 plan-b 的冲突扫描消费（`reserved` 参数），登记在本计划（同文件独占）。
- [keymaps/vsc.py](../../../yate/keymaps/vsc.py) 绑定表为 `_k` / `_raw` 工厂
  （:21-27），`<f1>`-`<f5>`、`<f8>` 已占用，`<f6>`/`<f7>`/`<f9>`-`<f12>` 空闲。
- [keymaps/registry.py](../../../yate/keymaps/registry.py) `KeymapSet.active`
  是唯一分发者（:55-58）。

## 目标

1. `Keymap` 增加只读观测钩子 `pending_prefix()`，vsc 继承基类恒空串，
   vim 覆写返回当前挂起 chord 的人读序列 —— which-key 实时更新的数据源
   （wave-2 的 plan-d 流程模块消费）。
2. vim 模块导出 `RESERVED_KEYS`（绑定表查找前被硬编码消费的 raw 键集合），
   作为 plan-b 冲突扫描的抢占事实来源。
3. 两种 keymap 各登记 `<f9>` → `toggle_whichkey` 动作名绑定（动作本体在
   plan-e 注册，L1 只持名字串，无新依赖边）。

## 非目标

- 不在 L1 做任何 UI / 回调通知（R4；面板经 L3 轮询读取，见主计划备选 D 否决）。
- 不做冲突扫描模块 `conflicts.py`（归 plan-b，文件互斥）。
- 不检测「绑定指向未注册 action」（vim 绑定表大量使用带空格的伪动作名，
  静态判定必然误报，见主计划非目标）。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `yate/keymaps/base.py` | 修改 |
| `yate/keymaps/vim.py` | 修改 |
| `yate/keymaps/vsc.py` | 修改 |
| `tests/test_vim_keymap.py` | 追加 |
| `tests/test_vsc_keymap.py` | 追加 |

## 具体修改

### 1. [base.py](../../../yate/keymaps/base.py) — `Keymap` 尾部（:204 后）新增

```python
def pending_prefix(self) -> str:
    """The chord typed so far in human form (empty when nothing pends).

    Which-key surfaces read this after every dispatch to decide whether
    the pending-chord panel is visible.  The modeless base keymap never
    holds chord state, so it answers empty; stateful subclasses override.
    """
    return ""
```

### 2. [vim.py](../../../yate/keymaps/vim.py) — 三处

2a. 模块级常量区（`_FUNCTION_KEYS` 定义 :71 附近）导出：

```python
#: Raw keys consumed by _handle_normal before the binding table is
#: consulted, so a table entry on any of them would never dispatch.
#: ``0`` is only swallowed mid-count and stays bindable.
RESERVED_KEYS: frozenset[str] = frozenset(
    {"\x1b", "\x1bc", "\x07", "\x04", "\x15", "\x06", "\x02", "\x12",
     "1", "2", "3", "4", "5", "6", "7", "8", "9"}
)
```

2b. `VimKeymap` 内（`_clear_pending` :249 之后）覆写观测钩子：

```python
@override
def pending_prefix(self) -> str:
    """The vim chord typed so far, in binding-spec order (empty if none).

    Follows the typing order the dispatch accepts: register, count,
    operator, prefix (``"a2df``).  INSERT / VISUAL never hold chord state.
    """
    if self.mode is not VimMode.NORMAL:
        return ""
    parts: list[str] = []
    if self.pending_register == "":
        parts.append('"')
    if self.count_str:
        parts.append(self.count_str)
    if self.op is not None:
        parts.append(self.op)
    if self.prefix is not None:
        parts.append(self.prefix)
    return "".join(parts)
```

2c. `build_bindings` 表尾（`toggle_keymap` 条目 :198 旁）新增：

```python
KeyBinding(parse_key("<f9>"), "toggle_whichkey",
           "Toggle the which-key panel", HLP),
```

### 3. [vsc.py](../../../yate/keymaps/vsc.py) — `build_bindings` 表尾（:119 旁）新增

```python
_k("<f9>", "toggle_whichkey", "Toggle the which-key panel", VIEW),
```

## 新增测试

### tests/test_vim_keymap.py 追加

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_pending_prefix_empty_when_idle` | `VimKeymap()`，`ActionContext` + `KeyUi`（沿用本文件既有 fixture） | 初始调 `pending_prefix()` | 返回 `""` |
| `test_pending_prefix_tracks_operator_then_prefix` | 同上 | 依次 `handle_key(ctx, "2")`、`"d"`、`"f"` | 依次断言 `"2"`、`"2d"`、`"2df"` |
| `test_pending_prefix_tracks_register_wait` | 同上 | `handle_key(ctx, '"')` 后 | 返回 `'"'`；再喂 `"a"` 后回到 `""` |
| `test_pending_prefix_empty_in_insert_mode` | 进入 insert（`handle_key(ctx, "i")`） | `pending_prefix()` | `""` |
| `test_f9_binding_toggles_whichkey_action` | 同上 | `handle_key(ctx, parse_key("<f9>"))` | 经 `KeyUi.execute_action` 记录收到 `"toggle_whichkey"`（用测试替身 runner 断言调用参数），返回 `True` |
| `test_reserved_keys_match_hardcoded_consumers` | `VimKeymap()` 已 import `RESERVED_KEYS` | 断言常量集合内容 | 恰含 `\x1b` / `\x04` 与 `1`-`9`，不含 `"0"`、不含 `<f1>` |

### tests/test_vsc_keymap.py 追加

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_f9_binding_dispatches_toggle_action` | `VscKeymap()` + 替身 runner | `handle_key(ctx, parse_key("<f9>"))` | runner 收到 `"toggle_whichkey"`，返回 `True` |
| `test_pending_prefix_always_empty` | 任意按键前后 | `pending_prefix()` | 恒 `""`（基类继承，vsc 不覆写） |

## 验收命令（worktree venv）

```text
.venv\Scripts\python.exe -m pytest tests/test_vim_keymap.py tests/test_vsc_keymap.py tests/test_keymap_set.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pyright yate/keymaps/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q --cov-fail-under=0
```

通过判定：三条命令退出码 0；架构测试确认 L1 零 UI 导入（R4 守卫
`test_keymaps_services_and_models_stay_ui_free` 仍绿）。

## 风险与回滚

- `pending_prefix()` 漏统计未来新增 chord 形态：测试逐形态钉住；新增 chord 时
  同步覆写（已写入方法 docstring 契约）。
- `RESERVED_KEYS` 收录过宽误报（`0` 未收录、`<f*>` 未收录均有行号依据）：
  常量内容用例 `test_reserved_keys_match_hardcoded_consumers` 钉住，
  plan-b 的 `test_clean_table_reports_nothing` 反向验证不误伤。
- `<f9>` 与既有绑定冲突：vsc 表 `<f9>`-`<f12>` 空闲（输入事实），vim 走
  `_FUNCTION_KEYS` lookup 分支，均实测有据。
- 回滚：本子计划全部改动可按文件独立 `git checkout -- yate/keymaps/ tests/`
  还原，无迁移状态。
