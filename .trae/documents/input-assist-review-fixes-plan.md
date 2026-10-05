# input-assist 评审修复方案（python-code-review skill，2026-10-04）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
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

---

## 五、第二轮：Gitee PR !54 AI 队友评审（2026-10-05）

- **来源**：Gitee PR !54 评论
  [`note_51443873`](https://gitee.com/jermaine/yate/pulls/54#note_51443873_conversation_191386654)
  （conversation `191386654`，「PR观察者」）。落盘记录见
  [`../reviews/2026-10-05-pr54-input-assist-ai-review.md`](../reviews/2026-10-05-pr54-input-assist-ai-review.md)。
- **结论**：⛔ 未通过——1 阻断 / 2 改进，风险自评 low。
- **状态**：已修复（2026-10-05）。

### 5.1 处置总表

| # | 维度 | 问题 | 处置 |
|---|---|---|---|
| B1 | 功能性与逻辑 | `_shift_row` 的 `row` 在循环外只取一次，`3>` = 当前行缩进 3 级，与 vim 的"向下 3 行各 1 级"不一致 | **改代码对齐 vim**（§5.2 路线 A），非改文案 |
| M1 | 可维护性 | `delete_backward` 成对删除分支裸赋 `self.cursor`，绕过 `set_cursor` 的 `_goal_col` 复位 | **改**：`self.set_cursor((r, c - 1))` |
| M2 | 性能 | G9 基准取 1000 次按键均值而非单次上限 | **不改**：评审者自评无需改动（阈值余量约 500 倍），仅登记 |

### 5.2 B1 选型：为什么对齐 vim 而非改文案

评审给了两条互斥路线，裁决如下。

| | 路线 A：对齐 vim（`3>` 向下 3 行各 1 级） | 路线 B：保留"当前行 ×N 级"，改文案 |
|---|---|---|
| 产品定位 | 符合 `enh/vim-keymap` 一贯的"保真复刻 vim"验收口径 | 功能差异仍在，只是说清楚了 |
| 与既有文案的关系 | `vim.py:151-152` 的 `Indent [count] lines` / `Outdent [count] lines` **转为正确**（现文案即 vim 口径） | 必须把 `lines` 改成"当前行重复 N 次" |
| 副作用 | 撤销步从 count 次降为 **1 次**（一次跨行选区 + 一次 commit） | 无 |
| issue 授权 | G6 原文只写"增/减一级"，未排除多行；§3.3 只写"支持 `3>` 计数"，从未规定计数作用于行还是级；D5 的"`3>` = 3 级"是**实施记录**而非方案决策 | 同左，不越界 |
| 代价 | 需改 3 条 pin 旧语义的用例 + 手册 3 处措辞（中英各 3） | 需改手册 3 处措辞 + 2 条帮助文案 |

裁决：**路线 A**。决定性证据是帮助文案本身写着 `lines`——文案侧站的才是 vim 惯例，
偏差在实现侧；路线 B 等于让实现迁就一段本来就与自身矛盾的文字。

**新语义定义**（本节即唯一规范来源）：

- NORMAL 模式 `count>` / `count<`：对**光标行及其下方共 `count` 行**（不足则截断到
  文件末尾，不报错）各增/减**一个**缩进单位；
- 行数不足时按实际行数截断，与 vim 一致（vim 的 `3>` 在只剩 2 行时同样只作用 2 行）；
- 空行不再有"每 count 一个单位"的特殊语义：多行选区覆盖时按普通行处理；仅当整个
  作用范围退化为**单个空行**（选区 anchor == cursor，`selection()` 返回 `None`）时，
  才落回 `indent_selection()` 的 `insert_tab()` 分支，即列 0 处一个单位；
- 结束后光标落在**光标行**的首个非空白列，选区清空（均不变）；
- 撤销：整个 `count` 行的缩进是**一个** `"step"`（`indent_selection` / `outdent_selection`
  内部各 commit 一次）。

### 5.3 改动清单

| 文件 | 改动 |
|---|---|
| `yate/keymaps/vim.py` | `_shift_row` 重写：选区从 `(row, 0)` 延伸到 `(row + count - 1, 行尾)`，clamp 到末行；`indent_selection` / `outdent_selection` 各调用一次；docstring 改写为行数语义并说明末行截断；帮助文案**不动**（已与新语义一致） |
| `yate/editor_core/buffer.py` | `delete_backward` 成对删除分支 `self.cursor = (r, c - 1)` → `self.set_cursor((r, c - 1))`，与 F3 口径统一 |
| `tests/test_input_assist.py` | 3 条 pin 旧语义的用例改写（详见 §5.4）+ 补末行截断与撤销步用例 |
| `yate/resources/manual.zh.md` / `manual.en.md` | 3 处措辞明确"计数作用于行数"：3.5 节缩进键表、5.2 节按键表、命令速查表（中英成对，共 6 处） |

### 5.4 受语义变更影响的用例（改写，非删除）

| 用例 | 旧断言 | 新语义下的期望 |
|---|---|---|
| `test_vim_normal_mode_count_indents_the_current_line`（`:503`） | 单行 `3>` → 12 空格 | 改为多行：`a\nb\nc\nd` 光标在 row 0，`3>` → 前 3 行各 +1 级，第 4 行不动 |
| `test_vim_normal_mode_outdent_stops_at_column_zero`（`:512`） | 单行 8 空格 `3<` → `abc`（0） | 改为多行 4 行各 8 空格，`3<` → 前 3 行各留 4 空格、第 4 行不动；"不低于 0" 由新增单行 4 空格 `3<` → `""` 的用例 pin |
| `test_vim_normal_mode_indent_on_an_empty_row_adds_one_unit_per_count`（`:551`） | 空行 `3>` → 12 空格 | 改为：空行作为首行且下方有 2 行时，`3>` 三行各 +1 级（含空行变 4 空格）；"单个空行落回 `insert_tab`"的语义由新用例 pin（单行 buffer 的空行 `3>` → 1 个单位） |

### 5.5 验收命令（worktree 内，`.venv\Scripts\python.exe`）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_input_assist.py tests/test_editor_core.py tests/test_vim_keymap.py tests/test_vsc_keymap.py tests/test_action_table.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-report=term-missing --cov-fail-under=75
```

> 承接 §三 提示：`addopts` 已含 `-q`，命令行**不要**再叠 `-q`；覆盖率必须由**全量**
> `pytest tests/` 产出，只跑 22 条架构测试达不到 75%。

基线（第一轮修复后）：`pyright` 0 诊断；`test_input_assist.py` 59 条；全量
`1740 passed / 7 skipped`；架构 `22 passed`；覆盖率 `91.35%`。本轮修复后用例数只增不减，
覆盖率不得低于基线。

### 5.6 执行记录（2026-10-05，主代理回填）

**5.6.1 门禁实测**（主代理亲自在 worktree 沙箱跑，退出码均 0）

| 命令 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` |
| `pytest tests/test_architecture.py` | `22 passed` |
| `pytest tests/test_input_assist.py` | **`63 passed`**（基线 59，+4） |
| `pytest tests/ --cov=yate --cov-report=term --cov-fail-under=75` | **`1788 passed, 30 skipped`**，覆盖率 **91.27%** |

对比第一轮基线（`1740 / 7`、91.35%）：全量用例 **+48**（含 master 经 `5c40f99` 带入的
syntax 用例，非本轮新增），`test_input_assist.py` **+4**，覆盖率 91.35% → 91.27%
（−0.08，属新增分支路径的正常波动，仍远高于 75% 门槛）。

**5.6.2 逐项处置结果**

| # | 结果 |
|---|---|
| B1 | **已改**（`5c41d69`）：`_shift_row` 选区由光标行延伸至 `row + count - 1`（clamp 到末行），`indent_selection` / `outdent_selection` 各调一次。主代理用探针实测 8 个边界场景全部符合 vim 语义：`3>` 于 4 行 → 前 3 行各 +1 级、光标 `(0, 4)`；于 2 行 → 2 行全缩进（静默截断）；`3<` 于 4×8 空格 → 前 3 行各留 4 空格；`3<` 于 4 空格 → 落到 0 不为负；空行作首行且下方有行 → 按普通行加缩进；孤立空行 → `insert_tab` 一个单位。帮助文案 `Indent [count] lines` 由此**转为正确**，未改一字 |
| M1 | **已改**（`5c41d69`）：`self.cursor = (r, c - 1)` → `self.set_cursor((r, c - 1))`。探针实测行为等价（`a()b` + BS → `a()` 光标 `(0, 3)`，`()` + BS → `x` 未越界，undo 复原） |
| M2 | **不改**：按评审者自评登记（阈值余量约 500 倍） |
| 用例 | **已改**（`ca6d204`）：3 条改写 + 4 条新增（末行截断 / 撤销单步 / 不低于 0 / 孤立空行），共 59 → 63 |
| 手册 | **已改**（`ca6d204`）：中英成对 3 处（3.5 节缩进键表、5.2 节按键表、命令速查表）+ 3.5 节正文明示"计数按行数向下生效、行数不足只作用到文件末尾"；VISUAL 表述未动 |

**5.6.3 与方案的偏离**

| # | 偏离 | 依据 |
|---|---|---|
| P5 | **实现追加了一次"光标行回走"**（§5.2 的语义定义里没写这一步） | 主代理探针实测发现：只选一次区时 `indent_selection` 把光标留在**末行**（`3>` 于 4 行 → `cursor=(2, 4)`），与 vim 落在起始行首个非空白列不符。补 `buf.set_cursor((row, 0))` 后再 `move_line_start(toggle=False)`，复跑探针 8 场景全绿（`cursor=(0, 4)`）。这是 §5.2"光标落在光标行"这一既定语义的实现补齐，不是新增语义 |
| P6 | **worktree 沙箱补装 `tree-sitter-css`** | 全量首跑 1 条失败 `test_ts_backend.py::test_scss_and_less_do_not_borrow_the_css_grammar`，实测 `find_spec('tree_sitter_css') is None` 而 `pyproject.toml:40,75`（`ts` 与 `dev` extras）均已声明该依赖——该用例由 master 经 `5c40f99` 带入，沙箱未装齐所致，与本轮改动无关。`pip install "tree-sitter-css>=0.25"` 后复跑全绿。仅动沙箱环境，无代码或依赖声明变更 |
| P7 | **VISUAL 模式的 count 差异未修** | 评审明确将影响范围限定为 NORMAL（"单次按键和 VISUAL 模式均不受影响"）；手册 3.5 / 5.2 两表已按 NORMAL / VISUAL 分行写明忽略计数前缀，测试亦 pin。改动属评审范围外的产品行为变更，登记为遗留项（见评审记录 §六 G9-1） |

**5.6.4 子代理分工与产出**（只认落盘结果，主代理已逐条 `git diff` 复核 + 重跑）

| 成员 | 名下文件 | 产出 |
|---|---|---|
| `tests-writer`（`acceptEdits`） | `tests/test_input_assist.py` | 63 passed，主代理复核通过 |
| `docs-writer`（`acceptEdits`） | `yate/resources/manual.zh.md` / `manual.en.md` | 中英成对 3 处 + 正文，主代理复核通过 |
| 主代理 | `yate/keymaps/vim.py`、`yate/editor_core/buffer.py`、两份 `.trae/` 文档 | 产品源码按规则不由子代理改动 |

**5.6.5 提交**（只提交、不推送）

`4b81e54` 评审记录 → `d1d1a41` 方案 → `5c41d69` 源码修复 → `ca6d204` 用例与手册，
共 4 笔。
