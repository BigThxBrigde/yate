# 子计划 a：L0 共享键位常量（wave-1）

> 唯一规范来源：`overview.md` §1.1 + 主计划 `../macro-record-replay-unified-plan.md`
> §5.2；本文件自包含。先读 `.trae/agents/plan-executor.md` 按剧本执行。
> 状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F1/F2（L0 `keys.py` 先例 `HOVER_DOC_KEY`）、F3/F4/F18（键位占用）。
- 上游依赖：**无**（wave-1 最先独立开工）。
- 输出：3 个共享键位常量 + 1 个控制键 raw 集合；L0 单测；既有键位零回归。

## 1. 独占文件清单（只改这些）

- `yate/keymaps/keys.py`
- `tests/test_macro_constants.py`（新增）

> 不改 `yate/keymaps/vim.py` / `vsc.py`、`tests/test_architecture.py`、
> 任何其它文件；`base.py` 由 plan-d（wave-2）独占修改（新增
> `Keymap.take_pending_count()`），本计划仍不触碰。产品源码 `yate/**` 归属依据
> 见 `overview.md` §2。

## 2. 具体修改（文件:行号）

### 2.1 `yate/keymaps/keys.py`

- 在 `HOVER_DOC_KEY: str = "<f7>"`（**第 60 行**）之下，新增 3 个模块级常量，
  各带 `#:` 注释（对齐 `HOVER_DOC_KEY` 第 57-59 行风格，注释 ASCII）：

```python
#: Shared key for toggling macro recording in both built-in keymaps (AC3).
MACRO_RECORD_KEY: str = "<f10>"
#: Shared key for playing a recorded macro in both built-in keymaps (AC3).
MACRO_PLAY_KEY: str = "<f11>"
#: Shared key for repeating the last macro replay in both keymaps (AC3).
MACRO_REPLAY_LAST_KEY: str = "<f12>"
```

- 在 `parse_key` 定义**之后**（`return base`，**第 157 行**之后、`key_name` 第 160 行
  之前）新增 `MACRO_CONTROL_KEYS`。**位置理由**：模块级常量在导入时按源码顺序求值，
  `parse_key` 到第 98 行才定义，若把该集合放到第 60 行附近会 `NameError`；放在
  `parse_key` 之后既满足契约 `frozenset(parse_key(k) ...)` 又无循环。

```python
#: Raw forms of the three macro control keys; dispatch uses this set to keep
#: the control keys themselves out of a recorded sequence and to reject a
#: replay-triggering key while a replay is in flight (AC4).
MACRO_CONTROL_KEYS: frozenset[str] = frozenset(
    parse_key(key)
    for key in (MACRO_RECORD_KEY, MACRO_PLAY_KEY, MACRO_REPLAY_LAST_KEY)
)
```

- **不改**：`SPECIAL_KEYS`（第 25-55 行）、`KEY_ALIASES`（第 63-88 行）、
  `_KEY_ALIASES_INV`、`parse_key`（第 98-157 行）、`key_name`（第 160-209 行）、
  `HOVER_DOC_KEY`（第 60 行）、模块 docstring 的分层声明。
- 依赖边：无新增 import（本模块只 `import re`）；L0 零上层依赖不变。

### 2.2 `tests/test_macro_constants.py`（新增）

文件头 `from __future__ import annotations`；`from yate.keymaps.keys import ...` 绝对
导入；测试函数命名 `test_<behavior>_<condition>_<expected>`；用例见 §3。

## 3. 详细测试用例（`tests/test_macro_constants.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_macro_keys_have_expected_specs_and_no_conflict` | 无（纯常量模块） | 读取 3 个常量并 `parse_key` | `MACRO_RECORD_KEY == "<f10>"`、`MACRO_PLAY_KEY == "<f11>"`、`MACRO_REPLAY_LAST_KEY == "<f12>"`；`parse_key` 分别 `== "\x1b[21~"` / `"\x1b[23~"` / `"\x1b[24~"`；三者与 `parse_key(HOVER_DOC_KEY) == "\x1b[18~"`、`SPECIAL_KEYS["f9"] == "\x1b[20~"`、`SPECIAL_KEYS["f8"] == "\x1b[19~"`、`SPECIAL_KEYS["f6"] == "\x1b[17~"` 两两不等（长度 7 的集合去重后 `len == 7`） |
| `test_macro_control_keys_match_parse_key` | 无 | 读 `MACRO_CONTROL_KEYS` | `MACRO_CONTROL_KEYS == frozenset({parse_key(MACRO_RECORD_KEY), parse_key(MACRO_PLAY_KEY), parse_key(MACRO_REPLAY_LAST_KEY)})` 且 `len(MACRO_CONTROL_KEYS) == 3`，集合元素类型全为 `str` |
| `test_hover_doc_key_unchanged_after_macro_constants` | 无 | 读 `HOVER_DOC_KEY` | `HOVER_DOC_KEY == "<f7>"` 且 `parse_key(HOVER_DOC_KEY) == "\x1b[18~"`（既有 hover 键零回归） |
| `test_parse_key_unknown_macro_spec_raises_value_error`（异常流） | 无 | `pytest.raises(ValueError)` 调 `parse_key("<f13>")` | 抛出 `ValueError`，消息含 `"unknown key name in spec"`（既有 `parse_key` 第 116 行行为回归） |
| `test_macro_constants_are_upper_case_module_level`（边界） | 无 | `ast.parse` 读 `yate/keymaps/keys.py`，收集模块级 `Assign` / `AnnAssign` 目标名 | 4 个新名字均在模块级赋值节点中，且 `MACRO_CONTROL_KEYS` 的赋值节点行号 **大于** `parse_key` 的 `FunctionDef` 行号（防求值顺序回归） |

## 4. 验证方案

- **验证目标**：证明 L0 共享常量是宏键位的唯一真源、`parse_key` 规范化无回归、
  既有 f6/f7/f8/f9 占用未被改写（主计划 §5.2 裁定），且求值顺序不产生 `NameError`。
- **需一并回归的既有测试**：`tests/test_architecture.py`（现有
  `test_hover_key_is_shared_and_identical` 与 R4 / 层秩守卫）；`tests/test_keymaps.py`
  或 `pytest tests/ -k "parse_key or key_codec" -q`（若存在，执行者按实际文件名取）。
- **通过判定标准**：pyright 退出码 0 零诊断；pytest 退出码 0、断言全绿；架构守卫
  无违规。
- **无法自动化部分**：终端实键（f10/f11/f12 是否被终端吞）留待 wave-5 冒烟与
  人工验证，本子计划不臆测。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pyright yate/keymaps/keys.py
.venv\Scripts\python.exe -m pytest tests/test_macro_constants.py tests/test_architecture.py -q
```

## 6. 架构边界与守卫

- 触碰层级：仅 L0（`keymaps/keys.py`，`_LAYER_RANKS` 第 159 行登记为 0）。
- R 条款：R4（L0 UI-free，无新 import）、`UPWARD_EDGES_FROZEN` 保持空集。
- 守卫用例：`tests/test_architecture.py::test_no_unregistered_upward_imports`、
  `test_hover_key_is_shared_and_identical`（**只跑不改**；新增守卫归 plan-d）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `MACRO_CONTROL_KEYS` 放在 `parse_key` 之前导致导入 `NameError` | §2.1 明确放在第 157 行之后；单测 `test_macro_constants_are_upper_case_module_level` 断言行号顺序 | `git checkout -- yate/keymaps/keys.py tests/test_macro_constants.py` |
| 误改 `SPECIAL_KEYS` / `HOVER_DOC_KEY` 造成既有键位漂移 | §2.1 列明不改清单 + 回归用例 + 跑既有 hover 守卫 | 同上 |
| 常量值选到已占用键（f6 冒烟 / f7 hover / f9 which-key） | 主计划 §5.2 占用矩阵 + 本计划首个用例断言七键互异 | 同上 |

回滚后须在该波次记录回填偏离与实测依据，未 commit 前直接还原工作区即可。
