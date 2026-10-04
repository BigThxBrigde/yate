# input-assist 评审修复方案（python-code-review skill，2026-10-04）

- **来源**：`.trae/skills/python-code-review` skill 对 issue IKJMQ2 产物的审核（0 CRITICAL / 2 WARNING / 6 SUGGESTION）
- **分支 / worktree**：`enh/input-assist` @ `../yate-input-assist`
- **状态**：用户已批准修复（"fix 这些 issues"）

## 一、处置总表

| # | 维度 | 问题 | 处置 |
|---|---|---|---|
| F1 | 文档准确性 | 手册 3.5 节写"空行回车 → 保持**上一行**缩进"，实现是保持**当前行**缩进（实测 `"    x\n"` 光标在无缩进空行 → 回车得 `'    x\n\n'`） | **修文档**（zh/en 成对），不改行为 |
| F2 | 可维护性 | `buffer.py` 包裹选区分支手工复刻 `replace_range`（差异仅 `kind="char"`），无注释说明，将来被"简化"会静默改变撤销合并语义 | **修**：补注释 |
| F3 | 一致性 | `buffer.py` 包裹分支直接写 `self.cursor` / `self.anchor` 绕过 `set_cursor`，与本轮 `_shift_row` 采纳的 m5 结论相反 | **修**：改走 `set_cursor` |
| F4 | 一致性 | 只读护栏风格不一致：`type_char` 先显式 `_ensure_writable()` 又委托 `insert_text`（双重检查），`insert_newline` 则完全依赖被调方 | **修**：`type_char` 保留显式守卫并补注释（它还要拦住"跳过"这条非变更路径），`insert_newline` 补显式守卫 |
| F5 | 性能 / 可读性 | `insert_newline` 对同一行做 3 次扫描（`lstrip` / `strip` / `rstrip`） | **修**：一次 `strip()` 派生缩进与空行判断 |
| F6 | Pythonic | `vim.py:367` 与 `vim.py:488` 各写 `if key == ">" or key == "<"`，字面量在 `build_bindings` 再重复 | **修**：模块级 `_SHIFT_KEYS` + `in` 成员测试 |
| F7 | 用户体验 | `don` + `'` → `don''`，再输入 `t` 得 `don't'`（多一个孤立右引号） | **不改代码**：issue 明确"字符串/注释内也生效、不做词法状态屏蔽"，改动即违背 issue；手册 zh/en 已补引号说明；VS Code 同款行为。作为已知限制登记 |
| F8 | 产品行为 | `delete_forward` 未做成对删除（`(|)` 按 Delete 只删右符号），与 Backspace 不对称 | **不改**：issue 只规定 Backspace；擅自给 Delete 加对称属未被请求的行为变更，仅登记为留白 |
| F9 | 文档 | `_shift_row` docstring 约 30 行，含设计权衡 | **不改**：house 风格鼓励散文式 docstring；权衡已记录在 `input-assist-plan.md` §七 D5/D7。仅记一次，不逐条挑风格 |

## 二、修复明细

### F1（文档，`yate/resources/manual.zh.md` + `manual.en.md`）

3.5 节「回车自动缩进」的空行条目：

- zh：`空行回车 → 保持上一行缩进，不再增加` → `空行回车 → 保持当前行自己的缩进，不再增加`
- en：`an empty line keeps the previous line's indent without adding a level` → `an empty line keeps its own indent without adding a level`

两语言必须成对修改；只改这一处，不动同节其它条目。

### F2–F5（`yate/editor_core/buffer.py`，单文件）

1. 包裹选区分支（`type_char` 内）：补注释说明**为何不调用 `replace_range`**——它硬编码 `kind="step"`，而包裹必须保持 `"char"` 才能与相邻输入合并撤销（issue G8）。
2. 同分支把 `self.cursor = (r1, c1)` / `self.anchor = None` 改为 `set_cursor((r1, c1))`（`select=False` 分支本就清 anchor），与 `_shift_row` 同口径。
3. `type_char` 的 `_ensure_writable()` 保留并补一行注释：它同时拦住"右符号跳过"这条**不做变更**的路径，只靠 `insert_text` 拦不住。
4. `insert_newline` 开头补 `self._ensure_writable()`，与其余公开 mutator 一致。
5. `insert_newline` 收敛扫描次数：

```python
stripped = line.strip()
indent = line[: len(line) - len(line.lstrip(" \t"))]
rules = rules_for(language)
if stripped and opens_block(rules, stripped):
    indent += indent_unit(self.tab_width, self.use_spaces)
```

> **本方案原稿的 `indent` 写法有 bug，已由执行成员纠正（2026-10-04）**：原稿写
> `line[: len(line) - len(stripped)]`，只在行尾无空白时等于前导缩进；`strip()` 吃两端，
> 尾随空白会让切片越界啃进正文——实测 `"if x:  "` 原稿实现得到 `'\nif    if x:  '`
> （缩进变成 `"if"`），与本节"不得改变 `insert_newline` 的缩进结果"直接冲突。
> 现行为 **2 次扫描**（`strip` + `lstrip(" \t")`），这是 Python 里同时得到左剥离与
> 全剥离的正确性下限；第 3 次（`opens_block` 内部的 `rstrip`）因传入的已是 stripped
> 串而实际遍历 0 字符，相对改前仍是净减少。`stripped` 非空即非空行（替代 `is_blank`）；
> `opens_block` 传已 strip 的串与原语义等价。
> 连带后果：`leading_indent` / `is_blank` 在 `buffer.py` 中不再有调用点，pyright strict
> 的 `reportUnusedImport` 使其必须从 import 表移除；复核确认二者**全仓零调用方**，
> 已一并从 `indentation.py` 删除（避免留死代码），并新增一条测试补上"行尾空白 + 自动
> 缩进"这一原本无任何用例覆盖的缺口。

**不得**改变以下既有行为：`type_char` 的 5 条分支顺序、撤销 kind、`insert_newline` 的缩进结果、空行回落、`insert_tab` 语义。

### F6（`yate/keymaps/vim.py`，单文件）

- 在既有模块级键常量区（`_MOTION_CODES` / `_ARROW` 附近）新增 `_SHIFT_KEYS: frozenset[str] = frozenset({">", "<"})`，带 `#:` 注释说明用途；
- `_handle_visual:367` 与 `_handle_normal:488` 两处判断改为 `if key in _SHIFT_KEYS:`；
- `build_bindings` 的两条帮助条目**照旧**写字面量（帮助表要展示真实按键，不改为常量）。

## 三、验收命令（worktree 内，`.venv\Scripts\python.exe`）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_input_assist.py tests/test_editor_core.py tests/test_vim_keymap.py tests/test_vsc_keymap.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-report=term-missing --cov-fail-under=75
```

> `pyproject.toml` 的 `addopts` 已含 `-q`，命令行**不要**再叠 `-q`，否则变`-qq` 吞掉统计行。
> **更正（2026-10-04）**：本方案原稿第 4 条写的是
> `pytest tests/test_architecture.py --cov=yate --cov-fail-under=75`——**这条命令本身是错的**，
> 只跑 22 条架构测试不可能达到 75% 覆盖率（实测 total 25%，exit 1）。覆盖率必须由**全量**
> `pytest tests/ --cov=yate --cov-fail-under=75` 产出。

基线（修复前）：`pyright` 0 诊断；`test_input_assist.py` 58 passed；全量 `1739 passed / 7 skipped`；架构 `22 passed`；覆盖率 `91.32%`。修复后数字不得低于此基线（用例数可增不可减）。

## 四、执行记录（2026-10-04，主代理回填）

### 4.1 门禁实测（主代理亲自跑，退出码均 0）

| 命令 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` |
| `pytest tests/test_input_assist.py tests/test_editor_core.py tests/test_vim_keymap.py tests/test_vsc_keymap.py` | `302 passed, 1 skipped` |
| `pytest tests/test_architecture.py` | `22 passed` |
| `pytest tests/ --cov=yate --cov-report=term-missing --cov-fail-under=75` | `1740 passed, 7 skipped`，覆盖率 **91.35%** |

对比基线（修复前 `1739 / 7`、91.32%）：用例 **+1**（本方案补的尾随空白用例），
覆盖率 **+0.03**（删除死代码后 `indentation.py` 回到 **100%**：`buffer.py` 99%、
`vim.py` 98%）。

### 4.2 各项处置结果

| # | 结果 |
|---|---|
| F1 | 已改：`manual.zh.md:189` → "保持当前行自己的缩进"；`manual.en.md:203` → "keeps its own indent"（主代理 `git diff -U0` 复核：zh/en 各恰好 1 行，旧表述清零） |
| F2 | 已加注释（`type_char` 包裹分支，说明 `replace_range` 的 `kind="step"` 与包裹所需的 `"char"` 冲突） |
| F3 | 已改走 `set_cursor((r1, c1))`（跨行选区与反向选区实测光标仍停在右符号之前） |
| F4 | `type_char` 守卫保留并加注释（它还要拦住"右符号跳过"这条非变更路径）；`insert_newline` 补 `self._ensure_writable()`，五条只读用例全绿 |
| F5 | 已改（2 次扫描版，见 §二 更正框）；连带删除 `indentation.py` 中零调用的 `leading_indent` / `is_blank` |
| F6 | 已改：`vim.py:74` 新增 `_SHIFT_KEYS`，`_handle_visual:370` 与 `_handle_normal:491` 改用 `in`；`build_bindings` 帮助条目按方案照旧保留字面量 |
| F7 / F8 / F9 | 按 §一 处置表**不改**，理由已登记（issue 授权的引号自动闭合、未被请求的 Delete 对称行为、house 风格的长 docstring） |

### 4.3 与方案的偏离

| # | 偏离 | 依据 |
|---|---|---|
| P1 | **§二 F5 的 `indent` 切片写法有 bug**，执行成员按"行为不得改变"纠正为 `line[: len(line) - len(line.lstrip(" \t"))]` | 原稿写法在行尾有空白时切片越界：实测 `"if x:  "` → `'\nif    if x:  '`（缩进变成 `"if"`），与 §二第 5 条"不得改变缩进结果"自相矛盾 |
| P2 | 连带**删除** `indentation.py` 的 `leading_indent` / `is_blank` | 原方案要求"不许删"（当时假定仍有调用方）；复核 `grep` 确认二者**全仓零调用方**，pyright strict的 `reportUnusedImport` 也迫使从 import 表移除，留着即死代码 |
| P3 | **新增一条测试** `test_enter_after_a_python_colon_with_trailing_blanks_keeps_the_indent_intact` | 复核发现全量 1739 条用例**无任何一条覆盖"行尾空白 + 自动缩进"**，这正是 P1 那个 bug 能一路绿灯的原因 |
| P4 | §三第 4 条验收命令纠正为全量 | 原稿 `pytest tests/test_architecture.py --cov=yate --cov-fail-under=75` 只跑 22 条用例，实测 total 25%、exit 1，不可能达到 75% |

### 4.4 提交

`fix(editor-core)` / `fix(keymaps)` / `test(input-assist)` / `docs(input-assist)` ×2，共 5 笔（只提交、不推送）。