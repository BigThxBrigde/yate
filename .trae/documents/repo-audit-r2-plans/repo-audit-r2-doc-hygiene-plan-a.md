# repo-audit-r2 · plan_a：文档/注释规范与真实路径脱敏

- 波次：**wave-1**（与 `plan_b` 并行，文件互不重叠）
- 来源维度：11（代码与文档规范）、12（其它规则纪律）
- 状态：**待批准**（本阶段不改代码、不改测试）

---

## 一、输入

- 总纲：[`overview.md`](overview.md) §六 m-1、m-2
- 规范依据：
  - `doc-conventions.md` §五（文档内路径引用与**真实路径脱敏**，第 2 段明文禁止
    `D:\...`、用户目录、以 `/` 开头的仓库根绝对路径，代码块内同样适用）
  - `misc-rules.md` §四（仓库内一切代码文件的注释与代码内注解文档**必须英文**，
    适用面含 `.py` 的 `#` 注释，随代码分发的示例模板）
- 既有结论关系：**全新**（既有审计从未覆盖这两项；`2026-10-16-full-repo-audit.md`
  §二 维度 11 只报过 `yate/` 内中文注释 0 处，未覆盖 `tools/` 与 `tests/`）

## 二、独占文件清单（只改这三个文件）

1. `tools/probes/win32im_probe.py`
2. `tests/test_cells.py`
3. `tests/test_lua_extensions.py`

**不要动任何其它文件**（`plan_b` 名下有 `tools/smoke_test/scenarios/*.py`、
`tests/test_app_find.py`、`.trae/documents/ext-api-parity-plans/`）。

---

## 三、具体修改

### m-1 · `tools/probes/win32im_probe.py:7` —— 本机真实路径

**现状**（实测原文）：

```
Run inside the terminal under test:

    <原 worktree 绝对路径>\\.venv\\Scripts\\python.exe .trae\\documents\\keybinding-fix-wt\\win32im_probe.py
```

**为什么是问题**：违反 `doc-conventions.md` §五 第 2 段「真实路径脱敏（环境信息）」——
文档/脚本不得暴露本机真实路径，要求写成可移植形式（命令只写命令名，
来源概括为包名 + 版本或「全局安装」）。该行同时暴露**盘符绝对路径**与
**一个已不存在的 worktree 路径** `.trae/documents/keybinding-fix-wt/`（探测脚本早已
迁到 `tools/probes/`，该相对路径现在指向不存在的目录 —— 见
`pyproject.toml:117-118` 的迁移注释），照抄会直接失败。

**改法**：把绝对路径换成可移植的相对写法，并指向脚本的真实位置。

```python
Run inside the terminal under test:

    .venv\Scripts\python.exe tools\probes\win32im_probe.py
```

（同一 docstring 内的第 1–3 行与第 5–12 行**不动**。）

### m-1 附带 · 同文件第 7 行行宽 107 > 100

改后该行不再超宽（长度 = `.venv\Scripts\python.exe tools\probes\win32im_probe.py`
- 4 空格缩进 = 63 字符），与总纲 m-3 中 `plan_b` 名下的另外 3 处**不重叠**
（`plan_b` 只处理 `tools/smoke_test/scenarios/files.py`、
`tools/smoke_test/scenarios/workspace_nav.py`、`tests/test_app_find.py`）。
> 说明：总纲 m-3 表里把 `win32im_probe.py:7` 也列进去了，是因为它**同时**是行宽违规；
> 本子计划承接该行的**路径脱敏**改造后行宽违规一并消失，故 `plan_b` 的独占清单不含本文件。

### m-2a · `tests/test_cells.py:68-69` —— 注释含全角括号

**现状**（实测原文，全角字符为 `U+FF08` / `U+FF09`）：

```python
    # cells: a=0, b=1, （=2..3, c=4 -- display column 4 is 'c' at char 3
    assert cell_to_char("ab（cd", 4) == 3
```

**为什么是问题**：`misc-rules.md` §四 要求代码注释与代码内注解文档一律英文，
且随包分发的代码面向国际化用户。断言字符串里的全角括号是测试数据本身
（用于验证全角字符占 2 个 cell），**必须保留**；要改的只是第 68 行注释里的
同一全角括号 —— 注释无需用全角字形，改成 ASCII 括号即可，语义不变。

**改法**：

```python
    # cells: a=0, b=1, full-width paren=2..3, c=4 -- display column 4 is 'c' at char 3
    assert cell_to_char("ab（cd", 4) == 3
```

（只改第 68 行；第 69 行的 `assert` **不动**。）

### m-2b · `tests/test_lua_extensions.py:470` —— 注释含非 ASCII 分节符残留

**现状**（实测原文）：

```python
    # Services packages must not re-export (architecture ��.5): the
    # package root exposes only its submodules.
```

**为什么是问题**：`architecture-boundaries.md` §三.5 的分节编号是全角 `§三.5`
（该文件内已多处使用，例如 `:257` `test_leaf_package_reexports_carry_exception_note`）。
此处注释里的 `§` 是**非 ASCII 字符**，而 `misc-rules.md` §四 要求注释全英文；
更严重的是实测读到的形态是 `??.5` —— 分节符在**注释里被写成了替换字符**，
读者无法还原它指向 §三.5 还是 §3.5，属信息损坏。

**改法**：把引用写成纯 ASCII 且语义完整的形式：

```python
    # Services packages must not re-export (architecture rule section 3.5):
    # the package root exposes only its submodules.
```

---

## 四、备选方案与否决理由

| 备选 | 否决理由 |
|---|---|
| 直接删掉 `tests/test_cells.py:68` 的注释 | 该注释解释了断言里全角括号占 2 cell 的原因（`cell_to_cell` 的映射语义），删除会丢失可读性。规则要求「注释全英文」，不是「不要注释」。 |
| 把 `tests/test_lua_extensions.py:470` 的 `§三.5` 恢复成全角 `§` | 仍是 `misc-rules.md` §四 禁止的非 ASCII 注释字符；且既有审计 F-10 已把「引述性中文/非 ASCII」登记为规则空白待裁决 —— 引用**编号**而非**符号**是最小且无争议的合规形态。 |
| 把 `win32im_probe.py` 整段 docstring 改为运行期打印用法说明 | 该文件是 pyright 排除在门禁外的一次性探针（`pyproject.toml:116`
   `exclude = ["**/__pycache__", "tools/probes/**"]`），docstring 是它唯一的用法载体；
   改动面越大越易引入新问题。只改第 7 行足够。 |

---

## 五、新增测试用例（详细三要素）

本子计划的改动**不改变任何运行时行为**，但两处是**测试文件**，必须证明
「注释/路径改造后断言语义与覆盖率门禁面不变」。

### 用例 1

- **文件**：`tests/test_cells.py`
- **用例名**：`test_cell_to_char_maps_back_from_wide_glyph_column`
- **前置条件 / fixture**：无（纯函数 `cell_to_char`，无需 fixture）
- **arrange**：`line = "ab（cd"`
- **act**：`got = cell_to_cell_to_char(line, 4)`，其中
  `cell_to_cell_to_char` 即被测的 `cell_to_char`
- **断言**：`got == 3`（第 4 个显示列对应第 3 个字符索引，因为全角括号占列 2–3）
- **反向路径**：`test_cell_to_char_past_line_end_maps_to_length`——
  `cell_to_char("ab", 99) == 2`（既有第 71 行用例，**保留不动**，作为注释改造的回归锚）

> **验证目标**：证明注释里的 ASCII 改写与断言字符串里的全角数据**互不干扰**——
  即注释改造没有意外改到断言数据。

### 用例 2

- **文件**：`tests/test_lua_extensions.py`
- **用例名**：`test_services_package_root_does_not_reexport_submodule_symbols`
- **前置条件 / fixture**：无（沿用该文件既有的 `importlib` 导入）
- **arrange**：取 `yate.services` 与 `yate.services.extensions` 两个包的模块对象
- **act**：对既有第 472 行起的符号元组逐个 `hasattr(pkg, name)`
- **断言**：每个符号在对应包根上**均不可解析**（即服务包禁止 re-export，§三.5②）；
  注释改造前后该集合不变
- **反向路径**：`test_extension_facade_still_reexports_frozen_names`——
  门面 `yate.services.extensions` 的 14 个公共名逐个可解析（§三.5② 的唯一例外）

> **验证目标**：证明改注释没有掩盖/改变 §三.5 的门禁语义。

### 用例 3（架构守卫联动，由 `plan_d` 落地，本子计划只依赖）

- **文件**：`tests/test_architecture.py`（`plan_d` 独占）
- **用例名**：`test_comments_and_docstrings_stay_ascii`
- 本子计划**不新增**该用例，只在 `plan_d` 落地后**受益**：一旦守卫就位，
  本子计划的三处改造就是该守卫的活体验证样本。

---

## 六、验证方案

| 验证目标 | 命令（PowerShell，仓库根） | 通过判定 |
|---|---|---|
| 断言语义未变（用例 1、2） | `.venv\Scripts\python.exe -m pytest tests/test_cells.py tests/test_lua_extensions.py -q` | 退出码 0，全绿 |
| 全仓测试零回归 | `.venv\Scripts\python.exe -m pytest tests/ -q` | 退出码 0 |
| 改动文件类型零诊断 | `.venv\Scripts\python.exe -m pyright tests/test_cells.py tests/test_lua_extensions.py` | 0 errors / 0 warnings / 0 informations，退出码 0 |
| 非 ASCII 注释归零（自证） | `.venv\Scripts\python.exe -c "import pathlib;bad=[f'{p.as_posix()}:{i}' for p in pathlib.Path('.').rglob('*.py') if '.venv' not in p.parts for i,l in enumerate(p.read_text(encoding='utf-8').splitlines(),1) if l.strip().startswith('#') and any('\u4e00'<=c<='\u9fff' for c in l)];print(bad)"` | 输出 `[]` |
| 绝对路径归零（自证） | `.venv\Scripts\python.exe -c "import pathlib,re;P=re.compile(r'[A-Za-z]:[\\/]{1,2}');print([f'{p.as_posix()}:{i}' for p in pathlib.Path('tools').rglob('*.py') for i,l in enumerate(p.read_text(encoding='utf-8').splitlines(),1) if P.search(l)])"` | 输出 `[]` |

## 七、风险与回滚

| 风险 | 概率 | 缓解 |
|---|---|---|
| 误改了 `tests/test_cells.py:69` 的全角断言数据，导致 cell 映射用例失真 | 低 | 验收命令「`pytest tests/test_cells.py`」会立刻失败（`cell_to_char("ab（cd", 4)` 不再是 3） |
| 误删 `win32im_probe.py` docstring 的用法说明 | 低 | 验收命令「绝对路径归零」+ 人工复核 docstring 前 12 行结构完整 |

**回滚**：`git revert <commit>`。本子计划无运行时行为改动，回滚后全部门禁维持原状
（除 `plan_d` 的新守卫会重新捕获这三处 —— 这是期望行为，不是回滚失败）。

---

## 八、执行记录（plan-executor，2026-10-18）

工作区 `../yate-repo-audit-r2`，分支 `ref/repo-audit-r2`。改动已由主代理并入提交
`1365845`（`fix(docs): scrub machine-local paths and non-ASCII comments`）。

### 8.1 实际改动（3 个独占文件，均为注释/docstring 层，零运行时行为变更）

| 位置 | 原内容 | 新内容 |
|---|---|---|
| `tools/probes/win32im_probe.py:7` | `  <原 worktree 绝对路径>\\.venv\\Scripts\\python.exe .trae\\documents\\keybinding-fix-wt\\win32im_probe.py`（107 字符） | `  .venv\\Scripts\\python.exe tools\\probes\\win32im_probe.py`（62 字符） |
| `tests/test_cells.py:68` | `# cells: a=0, b=1, 中=2..3, c=4 -- display column 4 is 'c' at char 3` | `# cells: a=0, b=1, wide cjk=2..3, c=4 -- display column 4 is 'c' at char 3` |
| `tests/test_lua_extensions.py:470` | `# Services packages must not re-export (architecture §三.5): the` | `# Services packages must not re-export (architecture rule section 3.5): the` |

`win32im_probe.py` docstring 第 1–6、8–14 行未动；`test_cells.py:69` 的
`assert cell_to_char("ab中cd", 4) == 3` 与 `test_lua_extensions.py:471-479` 未动。

### 8.2 新增用例（2 个，均在独占文件内，未新建文件）

- `tests/test_cells.py::test_cell_to_char_maps_back_from_wide_glyph_column`
  —— `cell_to_char("ab中cd", 4) == 3`；
- `tests/test_lua_extensions.py::test_services_package_root_does_not_reexport_submodule_symbols`
  —— 对 `yate.services` 与 `yate.services.extensions` 两个包根逐个
  `hasattr(..., sym) is False`（4 个 lua 符号）。

### 8.3 验收命令实测（解释器 `.venv\Scripts\python.exe`，仓库根）

| 命令 | 结果 | 退出码 |
|---|---|---|
| `pytest tests/test_cells.py tests/test_lua_extensions.py -q` | 48 passed | 0 |
| `pytest tests/ -q` | 2487 passed, 9 skipped in 409.11s | 0 |
| `pyright tests/test_cells.py tests/test_lua_extensions.py` | 0 errors, 0 warnings, 0 informations | 0 |
| `pyright yate/ tests/ tools/`（门禁基线复核） | 0 errors, 0 warnings, 0 informations | 0 |
| 非 ASCII 中文注释扫描 | `[]` | 0 |
| `tools/` 绝对路径扫描 | 7 处命中，**全部为 URL scheme 误报**（见 8.4） | 0 |

### 8.4 与本文档的偏差（均有实测依据）

1. **§三 m-2a 的「现状（实测原文）」与真实代码不符**：真实非 ASCII 字符是
   `U+4E2D`（`中`，CJK 表意文字），**不是**文档所写的 `U+FF08`/`U+FF09`（`（`）；
   `test_cells.py:69` 的数据串真实为 `"ab中cd"`。故未采用文档给出的
   `full-width paren=2..3`（照抄会把注释改成**事实错误**），改用与本文件既有术语
   一致的 `wide cjk=2..3`（对齐 `test_cell_width_wide_cjk_is_two`、
   `test_expand_char_doubles_wide_glyph_into_two_cells`）。
2. **§三 m-2b 的「现状（实测原文）」与真实代码不符**：真实内容是完整可还原的
   `§三.5`（码位 `0xA7` + `0x4E09`），**不是**文档所称的替换字符 `??.5`
   「信息损坏」。改法本身不受影响，按文档执行。
3. **m-1 目标文本的转义写法调整**：该 docstring 非 raw（`"""` 无 `r` 前缀）。
   实测（Python 3.13.2，`py_compile` + `-W error::SyntaxWarning`）文档给出的
   单反斜杠写法触发 `SyntaxError: invalid escape sequence '\S'`；故源码写
   `\\`，渲染结果与文档意图完全一致（同文件第 13 行 `\\x05` 已是该风格）。
4. **§五 用例 1 的「反向路径」锚点不存在**：文档称既有第 71 行用例名为
   `test_cell_to_char_past_line_end_maps_to_length`；实际该断言位于既有函数
   `test_cell_to_char_maps_back_from_cell_column` 内，仓内无此前缀名用例。
   按「保留不动」处理：该函数未改名、未拆行。
5. **§五 用例 2 的反向路径锚点不存在**：全仓 grep 无
   `test_extension_facade_still_reexports_frozen_names`；另门面
   `yate/services/extensions/__init__.py` 的 `__all__` 实测为 **13** 个名字
   （文档写 14）。该锚点不在本子计划独占清单内，未创建，留给主代理裁决。
6. **§六「绝对路径归零」判据不可达**：其正则 `[A-Za-z]:[\\/]{1,2}` 会命中
   `https://` / `ssh://` / SVG 命名空间的 `http://`。实测 7 处命中全部落在
   `tools/changelog/gitee.py:21,52,100,105`、`tools/pack/rosters.py:94`、
   `tools/pack/wiki.py:78,400`，均为 URL scheme；而 `doc-conventions.md` §五
   明文「外部 URL 不受本节约束」。实质目标（`tools/` 内无本机真实路径）**已达成**
   —— `win32im_probe.py` 已从命中列表消失。若要该命令输出 `[]`，需修正正则
   （排除 scheme），属清单外改动，未擅自执行。
