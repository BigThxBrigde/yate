# 子计划 f —— keymaps 层秩干净切分（Fix-F，S-1）

- 总纲：[`overview.md`](overview.md)｜主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md) §四 方案 D
- 波次：wave-1｜独占文件：`yate/keymaps/keys.py`（新建）、`yate/keymaps/base.py`、`yate/keyproto/legacy.py`
- 前置依赖：无（plan-b 守卫依赖本步先落地，见总纲 §二）

## 一、目标（分层切分清楚，且不违反规则）

`yate/keymaps/base.py` 现把**键位记法**（纯逻辑，L0）与**动作族**（`ActionContext` 持有
`EditorSession`，L1）混在同一文件，导致 L0 模块 `yate/keyproto/legacy.py` 与规则 §一 的 L0 定义冲突。

切分方案：

| 文件 | 层秩 | 内容 |
|---|---|---|
| `yate/keymaps/keys.py`（**新建**） | **L0** | 键位记法：`SPECIAL_KEYS` / `KEY_ALIASES` / `_KEY_ALIASES_INV` / `parse_key` / `key_name` |
| `yate/keymaps/base.py`（收敛） | **L1** | `Keymap` / `KeyBinding` / `KeyUi` / `ActionContext` / `ActionFunc` / `ActionRunner`，并为历史导入面**再导出**记法符号（向下再导出，合规） |
| `yate/keyproto/legacy.py` | L0 | 改从 `yate.keymaps.keys` 取 `SPECIAL_KEYS`（唯一必须改的跨模块引用） |

切分后：`keymaps/` 内每个文件层秩唯一，`keyproto/legacy.py → keys.py` 属同层；全仓 L0→L1 连线归零。

## 二、逐处改动

### 改动 1 —— 新建 `yate/keymaps/keys.py`

- 结构（顺序固定）：

```python
"""Key notation for keymaps (L0 leaf, no upward dependencies).

``KEY_ALIASES`` / ``SPECIAL_KEYS`` plus the two codecs :func:`parse_key` and
:func:`key_name` are the whole of this module: pure string logic that any
layer may import, including the L0 key codecs in :mod:`yate.keyproto`.
``keymaps/base.py`` (L1) re-exports them for the historical import surface;
**L0 code must import them from here** -- the layer guard in
``tests/test_architecture.py`` rejects an L0 module reaching into ``base``.
"""

from __future__ import annotations

import re
```

- 随后**整段搬入** `yate/keymaps/base.py` 现第 19–189 行的记法块（逐字搬运，**不得改动任何实现、
  注释文字、常量顺序或空行数量**）：
  - 第 19–27 行的 `# --- Key notation ---` 说明横幅；
  - `SPECIAL_KEYS`、`KEY_ALIASES`、`_KEY_ALIASES_INV`；
  - `def parse_key(...)`、`def key_name(...)` 及其 `#:` 注释。
  - 判定边界：记法块 = 自 `# ----------` 横幅起，至 `type ActionFunc` 之前的**全部内容**。
- 搬运后 `keys.py` 的 import 只允许 `re`（`from __future__ import annotations` 之外）。若发现记法块
  内引用了 `TextBuffer` / `Document` / `EditorSession` 等上层名字，**停止并回报**（不得自行加 import）。

### 改动 2 —— `yate/keymaps/base.py` 收敛为 L1

1. 模块 docstring 首行由
   `"""Keymap infrastructure: key notation, bindings and dispatch context.`
   改为
   `"""Keymap infrastructure: bindings and dispatch context (L1).`
   并在 docstring 末尾（`"""` 之前）补一段（英文）：

   ```
   Key *notation* moved to the L0 leaf :mod:`yate.keymaps.keys` in the
   2026-10-17 layer split; the four notation names are re-exported below so
   the historical import surface keeps working.  L0 code (``keyproto/*``)
   must import them from :mod:`yate.keymaps.keys` directly.
   ```

2. 删除改动 1 已搬走的记法块（含横幅注释）。
3. import 区调整：
   - 删除 `import re`（记法移走后本文件不再使用 `re`；已实测 `re.` 仅出现在 `key_name` 内）；
   - 新增 `from yate.keymaps.keys import KEY_ALIASES, SPECIAL_KEYS, key_name, parse_key`
     （按字母序放在 `from yate.editor_core...` 与 `from yate.session...` 之间的项目内导入组内，
     保持既有分组顺序：本条置于 `yate.editor_core` 之后、`yate.session` 之前）。
   - **保留** `from yate.editor_core.buffer import TextBuffer` / `document.Document` /
     `from yate.session import EditorSession`（动作族仍需要）。
   - 若本文件正在使用的记法符号（例如 `Keymap` 内部调用 `parse_key`）在删块后仍被引用，靠上条
     import 即可解析；**不得**新增其它 import。
4. 若文件定义了 `__all__`：把 `SPECIAL_KEYS` / `KEY_ALIASES` / `parse_key` / `key_name` 保留在
   其中（再导出面不变）；若没有 `__all__`，不新增。

### 改动 3 —— `yate/keyproto/legacy.py` 改指向

```python
from yate.keymaps.base import SPECIAL_KEYS
```

→

```python
from yate.keymaps.keys import SPECIAL_KEYS
```

（该文件其余内容一律不动；这是切分后 L0 侧唯一需要改的引用。）

### 改动 4 —— 不改动项（明确清单，避免顺手重构）

- `yate/keymaps/__init__.py`、`vim.py`、`vsc.py`、`registry.py` **不改**（经 `base.py` 再导出解析）；
- `yate/actions.py`、`registries.py`、`editor.py`、`flows/*`、`editor_view/*`、
  `services/extensions/api.py` **不改**（取的是动作族符号）；
- `tests/**` **不改**（`test_editor_core.py:29` / `test_extensions.py:14` / `test_input_assist.py:30`
  等经 `base.py` 再导出解析；若全量测试因改指向失败，停下来回报，不得私改测试）。

## 三、验收命令（必须实际执行并如实报告输出与退出码）

```powershell
# 在 worktree 根目录（本仓库的 `../yate-full-repo-audit`）下执行
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/          # 期望 0 errors, 0 warnings, 0 informations
.venv\Scripts\python.exe -m pytest tests/ -q -k "key or keymap or keyproto or extensions or input_assist or editor_core or app_"
.venv\Scripts\python.exe -c "import yate.keymaps.keys as k; print(k.parse_key('<ctrl-s>'), k.key_name('\x13'))"
.venv\Scripts\python.exe -c "from yate.keymaps.base import SPECIAL_KEYS, parse_key; print(len(SPECIAL_KEYS), parse_key('<esc>'))"
Select-String -Path yate\keyproto\legacy.py -Pattern 'keymaps\.keys'
Select-String -Path yate\keymaps\base.py -Pattern '^import re|SPECIAL_KEYS: dict'
```

- 期望：pyright 0/0/0；`keys.parse_key('<ctrl-s>')` → `\x13`、`key_name('\x13')` → `<ctrl-s>`；
  `base` 再导出可用；`legacy.py` 命中 `keymaps.keys`；`base.py` 不再含 `import re` 与 `SPECIAL_KEYS` 定义。

## 四、风险与回滚

| 风险 | 缓解 / 回滚 |
|---|---|
| 搬运时改动了逻辑或注释 | 逐字搬运 + 验收命令对照（`parse_key`/`key_name` 行为断言） |
| 记法块内隐藏上层引用 | 发现即停止回报，不得自行加 import |
| `base.py` 删除块后漏引用 | pyright strict 会直接报未定义名；0/0/0 是硬门槛 |
| 测试因改指向失败 | 停止回报（不得改 tests/）；回滚 `git revert <本步提交 sha>` |
