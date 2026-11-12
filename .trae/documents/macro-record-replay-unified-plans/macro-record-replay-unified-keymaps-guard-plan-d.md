# 子计划 d：双 keymap 统一登记 + 架构守卫（wave-2）

> 唯一规范来源：`overview.md` §1.1 / §1.2 / §1.10 + 主计划
> `../macro-record-replay-unified-plan.md` §5.2 / §7（AC3）；本文件自包含。
> 状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F1/F3/F4/F17（双表结构、`HOVER_DOC_KEY` 先例、守卫模板
  `test_hover_key_is_shared_and_identical`）、F18（f6 冒烟占用）。
- 上游依赖：**wave-1 全部验收通过**（尤其 plan-a 的 3 个共享常量已落盘）。
- 输出：vim / vsc 两套 `build_bindings()` 各登记 3 行共享常量引用（零字面量）；
  `base.py` 新增 `Keymap.take_pending_count()`（缺省 1）、`VimKeymap` 覆写委托
  `_take_count()`、`VscKeymap` 继承缺省恒 1（按键入口 count 前缀的 L1 原语）；
  `tests/test_architecture.py` 新增 3 条守卫 + `SIZE_EXEMPT_FILES` 登记；负向演练记录。

## 1. 独占文件清单（只改这些）

- `yate/keymaps/vim.py`
- `yate/keymaps/vsc.py`
- `yate/keymaps/base.py`（**本计划独占**：新增 `Keymap.take_pending_count()`；与双表同子计划、同波）
- `tests/test_architecture.py`（**全局独占**：所有新增守卫与豁免登记都在本计划）

> **不动** `yate/keymaps/keys.py`（plan-a）、`yate/editor.py`（plan-f）、其它子计划
> 文件。`base.py` 由本计划（plan-d / wave-2）独占修改，`overview.md` §2 归属表与
> §4 文件互斥矩阵已补登（波内不冲突）。产品源码归属依据见 `overview.md` §2。
> `tests/test_architecture.py` 其余子计划**只跑不改**。

## 2. 具体修改（文件:行号）

### 2.1 导入形态裁定（重要）

`HOVER_DOC_KEY` 的历史路径是 `base.py` 第 22 行 re-export 后由双表从
`yate.keymaps.base` 导入（F1/F6）。**常量的导入路径本计划不改**：`vsc.py` 与 `vim.py`
各自新增一行 `from yate.keymaps.keys import MACRO_PLAY_KEY, MACRO_RECORD_KEY,
MACRO_REPLAY_LAST_KEY`，直接引用 L0 真源（L1 → L0 向下，合法；F1 明确「L0 代码
必须 import them from here」不禁止 L1 直引）。理由：issue 只要求「常量定义在
`keys.py`、双表只引用常量、禁止字面量」，不要求经 `base.py` 再导出。
**但 `base.py` 本计划要改** —— 不是为 re-export 常量，而是为新增 L1 公共方法
`Keymap.take_pending_count()`（§2.5，按键入口 count 前缀原语）；`VimKeymap` 覆写
（§2.6）、`VscKeymap` 继承缺省（§2.2）。`base.py` 与双表同属 plan-d、同波，波内
无冲突（`overview.md` §2 / §4 已补登）。该裁定须在报告中登记依据。

### 2.2 `yate/keymaps/vsc.py`

- 现有 import 块（**第 7-12 行** `from yate.keymaps.base import (...)`）之后追加
  `from yate.keymaps.keys import MACRO_PLAY_KEY, MACRO_RECORD_KEY, MACRO_REPLAY_LAST_KEY`
  （按 `python-coding-style.md` §1.3 分组：均为项目内部导入，字母序排在该组）。
- `build_bindings()`（**第 41-128 行**）的 `return [...]`，在
  `_k(HOVER_DOC_KEY, "show_hover_docs", ...)`（**第 127 行**）之后、`]`（第 128 行）
  之前追加 3 行，**只引用常量名**：

```python
            _k(MACRO_RECORD_KEY, "macro_record", "Toggle macro recording", VIEW),
            _k(MACRO_PLAY_KEY, "macro_play", "Play a recorded macro", VIEW),
            _k(MACRO_REPLAY_LAST_KEY, "macro_replay_last", "Repeat last replay", VIEW),
```

  `_k` 内部即 `parse_key(spec)`（第 26-27 行），故 raw 与共享常量一致。

- **不覆写** `take_pending_count()`：`VscKeymap`（第 34 行）继承
  `Keymap.take_pending_count()`（§2.5）→ 恒返回 1（vsc 无 `count_str` 状态机，
  登记为 N5）。本计划不在 `vsc.py` 加任何 count 相关方法 / import。

### 2.3 `yate/keymaps/vim.py`

- 现有 import 块（**第 33-41 行**）之后追加同样的 `from yate.keymaps.keys import ...`。
- `build_bindings()`（**第 146-239 行**）在
  `KeyBinding(parse_key(HOVER_DOC_KEY), "show_hover_docs", ...)`（**第 234-235 行**）
  之后追加 3 行（vim 侧先例用 `parse_key(...)` 包 spec）：

```python
            KeyBinding(parse_key(MACRO_RECORD_KEY), "macro_record",
                       "Toggle macro recording", CMD),
            KeyBinding(parse_key(MACRO_PLAY_KEY), "macro_play",
                       "Play a recorded macro", CMD),
            KeyBinding(parse_key(MACRO_REPLAY_LAST_KEY), "macro_replay_last",
                       "Repeat last replay", CMD),
```

- **不动** `handle_key`（第 241-269 行）、`_FUNCTION_KEYS`（第 81 行）、
  `RESERVED_KEYS`（第 92-95 行）、`chord_hints()`（第 330 行起）、`pending_prefix()`。
  `_FUNCTION_KEYS` 已含 f10/f11/f12 的 raw，`handle_key` 第 255-264 行会
  `_clear_pending()` 后 `lookup(key)` + `dispatch` —— 因本计划已登记 binding，
  `lookup` 必然命中三个动作（**须在验收中实测确认**，见 §4）。另见 §2.6：本计划在
  `VimKeymap` 新增 `take_pending_count()` 覆写（委托既有 `_take_count()`），
  **不改 `handle_key` / `_clear_pending` 等状态机主体**。
- `vim.py` 当前 1534 行（F4），已在 `SIZE_EXEMPT_FILES` 名单（单一键映射域），
  新增 4 行（1 import + 3 binding）后**维持既有豁免**，不新增豁免条目。

### 2.4 `tests/test_architecture.py`

1. 在 `SIZE_EXEMPT_FILES`（**第 369-375 行**）集合中追加 `"editor.py"`，并在
   第 358-368 行注释区补一句 ASCII 说明「macro wiring adds the `MacroFlows`
   class attribute / factory to `editor.py`, pushing it past 800 lines; single-duty
   thin delegate, registered per section 3.7」。F17 证明：登记一个当时尚未越线的
   文件不会使 `test_source_files_within_size_threshold` 误报（第 926-930 行只在
   `lines > 800` 且未登记时报错），故可在本波提前登记，wave-3 才真正越线。
2. 新增 `test_macro_keys_are_shared_and_identical()`（**复制第 1611-1646 行
   `test_hover_key_is_shared_and_identical` 结构并泛化**）：
   - 对 `("vsc.py", "vim.py")` × `(MACRO_RECORD_KEY, MACRO_PLAY_KEY,
     MACRO_REPLAY_LAST_KEY)` 逐个：`ast.parse` 文件、取 `build_bindings`
     `FunctionDef`、收集 `ast.Name.id` 断言 3 个常量名**都在**；收集
     `ast.Constant` 的 str 字面量断言 `"<f10>"` / `"<f11>"` / `"<f12>"`
     **都不在**（负向：任一侧硬编码字面量必须失败）。
   - 运行时：`VscKeymap().lookup(parse_key(CONST))` 与
     `VimKeymap().lookup(parse_key(CONST))` 都非 `None`，且 `.action` 都等于
     同一动作名（`macro_record` / `macro_play` / `macro_replay_last`）。
3. 新增 `test_editor_size_exemption_is_registered()`：**仅**断言
   `"editor.py" in SIZE_EXEMPT_FILES`（守卫集合侧）。规则文本
   `.trae/rules/architecture-boundaries.md` §三.7 名单由 wave-3 plan-f 同步，
   两处一致性由 plan-f 的 `tests/test_macro_wiring.py` 断言——本用例若在此处
   读规则文本会因 wave-2 尚未改文本而红测，故**不读**，避免波间红测；
   本计划不改规则文本。
4. 新增 `test_macro_take_pending_count_is_defined_on_both_keymaps_and_vsc_is_one()`
   （轻量守卫，**本计划裁决新增、已登记于 `overview.md` §1.10 与主计划 §7**）：
   AST 断言 `base.py` 的 `Keymap` 类体与 `vim.py` 的 `VimKeymap` 类体**都含**
   `take_pending_count` 方法定义（基类 + 覆写两侧均有定义），且 `vsc.py` 的
   `VscKeymap` 类体**不含**该方法定义（继承缺省）；运行时断言
   `VscKeymap().take_pending_count() == 1`（vsc 恒 1）、
   `Keymap().take_pending_count() == 1`（基类缺省）、`VimKeymap()` 构造后
   `take_pending_count()` 可调用且返回 `int`。不读规则文本、不改既有守卫。

### 2.5 `yate/keymaps/base.py`（新增 `Keymap.take_pending_count()`，本计划独占）

- 在 `class Keymap:`（**第 90 行**）的方法区（`handle_key` 第 196 行附近或
  `pending_prefix()` 第 228 行起）新增一个公共方法，**不改任何既有方法体**：

```python
    def take_pending_count(self) -> int:
        """Return the pending count for a macro key, or ``1`` if none.

        Table-driven keymaps hold no count state machine, so the default is
        always ``1`` (N defaults to one). Stateful keymaps (vim) override this
        and must be called before ``handle_key`` clears pending state.
        """
        return 1
```

  - 签名逐字按 `overview.md` §1.8 硬契约；散文式 docstring、ASCII；不新增
    `Protocol` / `Any` / `TYPE_CHECKING` / `# type: ignore`（R2 / R6 / §五）；
    `base.py` 已有既有的 `from __future__ import annotations`，不新增任何 import，
    不改变 `KeyUi` / `ActionContext` / `lookup` / `dispatch` 等既有符号。
  - docstring 明示「必须在 `handle_key` 之前调用」的理由：dispatch（plan-g）依赖
    此约定在 vim `_FUNCTION_KEYS` 分支 `_clear_pending()` 之前捕获 count（F23）。

### 2.6 `yate/keymaps/vim.py`（`VimKeymap` 覆写委托，本计划独占）

- 在 `VimKeymap` 的 `# ---- counts` 区（`_take_count()` 定义，**第 1254-1266 行**）
  之后，新增覆写（**不改** `handle_key` / `_clear_pending` / `_take_count` 等既有主体）：

```python
    def take_pending_count(self) -> int:
        """Consume the typed count before ``handle_key`` clears it (vim)."""
        return self._take_count()
```

  - 委托既有私有原语 `_take_count()`（第 1260-1263 行，读并清空 `count_str`，无
    数字前缀返回 1）；不复制其逻辑、不改状态机主体、不新增 import。
  - `VscKeymap` **不覆写**（§2.2）：继承 `Keymap.take_pending_count()` → 恒 1
    （vsc 无 `count_str` 状态机，登记为 N5）。
  - 时序：`editor_dispatch.py::_handle_raw_key`（plan-g）在 `handle_key` 之前调
    `ed.keymaps.active.take_pending_count()`；vim 的 `handle_key` 第 255-264 行随后
    `_clear_pending()` 再清一次已空的 `count_str`，不影响已捕获值（wave-3 实测）。

## 3. 详细测试用例（`tests/test_architecture.py` 内新增）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_macro_keys_are_shared_and_identical` | 无（AST 读文件 + 运行时构造两套 keymap） | 解析 `vsc.py` / `vim.py` 的 `build_bindings`；构造 `VscKeymap()` / `VimKeymap()` 并 `lookup(parse_key(常量))` | 两文件 AST 均含 3 个常量 `ast.Name`，均不含 4 个字符串字面量 `<f10> <f11> <f12>`（外加 `<f7>` 沿用既有）；`VscKeymap().lookup(parse_key(MACRO_RECORD_KEY)).action == "macro_record"`，`VimKeymap()` 同；三个常量逐一断言两侧同 action 名 |
| `test_editor_size_exemption_is_registered` | 无 | 读 `SIZE_EXEMPT_FILES` | `"editor.py" in SIZE_EXEMPT_FILES` 为 `True`；集合仍含既有 5 项（`keymaps/vim.py` 等），`len(SIZE_EXEMPT_FILES) == 6` |
| `test_macro_keys_are_shared_and_identical`（**负向演练**，手工执行，不改文件落盘） | 执行者临时把 `vsc.py` 的 `_k(MACRO_RECORD_KEY, ...)` 改成 `_k("<f10>", ...)` | 跑 `pytest tests/test_architecture.py -k macro_keys -q` | 退出码**非 0**，`assert "<f10>" not in literals` 失败；随后**还原** `vsc.py`，重跑退出码 0。演练过程与两条输出写入报告 |
| `test_macro_take_pending_count_is_defined_on_both_keymaps_and_vsc_is_one` | 无（AST 读 `base.py` / `vim.py` / `vsc.py` + 运行时构造三套 keymap） | `ast.parse` 取 `Keymap` / `VimKeymap` / `VscKeymap` 类体方法名；构造 `Keymap()` / `VimKeymap()` / `VscKeymap()` 调 `take_pending_count()` | `Keymap` 与 `VimKeymap` 类体都含 `take_pending_count` 定义、`VscKeymap` 类体不含（继承缺省）；`Keymap().take_pending_count() == 1`、`VscKeymap().take_pending_count() == 1`；`VimKeymap().take_pending_count()` 返回 `int` 且无异常（缺省 1） |

补充回归用例（既有，只跑）：`test_hover_key_is_shared_and_identical`（确保
`HOVER_DOC_KEY` 未因新增 import 漂移）、`test_no_unregistered_upward_imports`
（新 import 为 L1→L0 向下）。`tests/test_macro_constants.py`（plan-a 产物）一并回归。

## 4. 验证方案

- **验证目标**：证明 AC3「同一键弦、同一动作名、来自 `keys.py` 共享常量、含负向
  拦截」；证明 `take_pending_count()` 在 L1 基类 + `VimKeymap` 覆写两侧均有定义、
  `VscKeymap` 继承缺省恒 1（按键 count 前缀原语，AC2）；证明 §三.7 豁免集合已为
  wave-3 的 `editor.py` 越线做好准备。
- **需一并回归的既有测试**：`tests/test_architecture.py` 全量（含既有 38 条 +
  本计划 2 条）、`tests/test_macro_constants.py`、`pytest tests/ -k "keymap or keys" -q`。
- **通过判定标准**：pyright 退出码 0 零诊断；pytest 退出码 0、断言全绿；架构守卫
  无违规；负向演练按预期拦截并还原。
- **实测项（不可凭假设）**：`VimKeymap().handle_key(ActionContext(...), parse_key("<f10>"))`
  必须返回 `True` 且 dispatch 到 `macro_record`（验证 F4 的 `_FUNCTION_KEYS`
  吞键分支确实因新 binding 命中）；若未命中，须停下来上报，不得在 `vim.py` 加
  特例分支（偏离须回填方案）。
- **无法自动化部分**：真实终端 f10/f11/f12 是否被吞留待 wave-5 冒烟 / 人工验证。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pyright yate/keymaps/vim.py yate/keymaps/vsc.py yate/keymaps/base.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/test_macro_constants.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -k "keymap or keys"
```

（负向演练为手工临时改动 + 上述 `-k macro_keys` 命令，执行后必须还原。）

## 6. 架构边界与守卫

- 触碰层级：L1（`keymaps/vim.py` / `vsc.py`，`_LAYER_RANKS` 第 160 行
  `("keymaps/", 1)`）、守卫文件 `tests/test_architecture.py`（不在扫描面）。
- R 条款：R4（keymaps 保持 UI-free，新 import 为 `yate.keymaps.keys` L0）、
  R2 / R6 / §五（`base.py` 新增的是普通公共方法，不新增 `Protocol` / `Any` /
  `TYPE_CHECKING` / 别名模块）、R11（不涉及 flows 的 `editor_components` 导入）、
  §三.7（体量豁免两处同步中的守卫集合侧）、§六 #38 先例泛化。
- 守卫用例：`test_macro_keys_are_shared_and_identical`（**本计划新增**）、
  `test_editor_size_exemption_is_registered`（**本计划新增**）、
  `test_macro_take_pending_count_is_defined_on_both_keymaps_and_vsc_is_one`
  （**本计划新增，已登记**）、
  `test_source_files_within_size_threshold`（既有，回归）、
  `test_hover_key_is_shared_and_identical`（既有，回归）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 两侧只改一侧 / 硬编码字面量导致 AC3 漂移 | 守卫 AST + 运行时双断言 + 负向演练 | `git checkout -- yate/keymaps/vim.py yate/keymaps/vsc.py tests/test_architecture.py` |
| `vim.py::_FUNCTION_KEYS` 吞掉未登记 f 键 | §2.3 登记 binding + §4 实测 dispatch 命中 | 同上；仍不命中须上报而非私自改状态机 |
| `base.py` 改动超出「只加一个方法」范围，波及 `KeyUi` / `lookup` 等既有符号 | §2.5 明确只加 `take_pending_count()`、不改既有方法体、不新增 import；pyright + 既有回归用例 | `git checkout -- yate/keymaps/vim.py yate/keymaps/vsc.py yate/keymaps/base.py tests/test_architecture.py` |
| `VimKeymap.take_pending_count()` 未委托 `_take_count()` 而自造逻辑 / 误改 `handle_key` 主体 | §2.6 明确委托既有原语、不改状态机；守卫 AST 断言覆写存在 + wave-3 实测捕获时序 | 同上 |
| `SIZE_EXEMPT_FILES` 提前登记被误判为「越线」 | F17 第 926-930 行证明只在越线且未登记时报错；单测断言集合长度 6 | 同上 |
| 负向演练临时改动未还原 | 报告须附还原后重跑退出码 0 的证据 | `git checkout -- yate/keymaps/vsc.py` |
