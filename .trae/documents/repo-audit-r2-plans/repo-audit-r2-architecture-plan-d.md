# repo-audit-r2 · plan_d：架构守卫缺口收口（新增 3 条用例 + 规则同步）

- 波次：**wave-2**（与 `plan_c` 并行，文件互不重叠）
- 来源维度：9（架构边界规则 R1–R14 与 §六 32 守卫用例）
- 触发条款：**R12**（日志统一 tracing）、`architecture-boundaries.md` §六（防回归）、
  `doc-conventions.md` §五、`misc-rules.md` §四
- 状态：**待批准**（本阶段不改代码、不改测试）

---

## 一、输入

- 总纲：[`overview.md`](overview.md) §六 A-1 / A-2 / A-3
- 现状依据（主代理亲跑实测）：
  - `tests/test_architecture.py` §六 对照表（`:446-481`）逐条核对：**32 个用例**，
    无一条覆盖「`print()` 调试」「注释/docstring 非 ASCII」「文档真实路径」
  - A-2 的缺口是**实测证明**的：`tests/test_cells.py:68` 与
    `tests/test_lua_extensions.py:470` 两处非 ASCII 注释**通过了全部现有门禁**
    （pyright strict 零诊断、pytest 全绿、32 架构用例全绿）——
    即「缺口真实存在」而非「推测存在」
  - A-3 同理：`tools/probes/win32im_probe.py:7` 的本机真实路径同样通过全部门禁
- 前置条件：wave-1（`plan_a` ∥ `plan_b`）验收通过
  （**注**：`plan_a` 已消除上述两处负样本，本子计划落地后它们成为守卫的活体正样本；
  `plan_a`/`plan_b` 与本子计划**不改同一文件**，守卫与样本互不干扰）

## 二、独占文件清单（只改这 2 个文件）

1. `tests/test_architecture.py`（新增 3 个用例）
2. `.trae/rules/architecture-boundaries.md`（§六 补 3 条守卫登记 + 32 → 35 用例计数同步）

> **约束**：守卫测试**不得**用豁免注释绕过（`architecture-boundaries.md` §六 末行）。
> 三条新用例的扫描面必须**排除**它们正当的存量形态（见各条「豁免面」节），
> 否则会把既有合规代码判为违规。

---

## 三、具体修改

### A-1 · 新增守卫 `test_no_debug_prints_in_library_modules`

**为什么是问题**：`python-coding-style.md` §4.6 明文「使用 `logging` 模块（见
`yate/logs.py` 的 `tracing` 服务），**禁止 `print()` 用于调试**」；§五 快速检查清单
也把日志纪律列为硬项。实测 `yate/` 内 `print` 调用共 14 处，**全部正当**：

| 位置 | 性质 | 判定 |
|---|---|---|
| `yate/cli.py`（12 处：`:266,:272,:274,:277,:308,:319,:329,:331,:350,:370,:372` 等） | CLI 面向用户的 stdout 输出 | 正当豁免 |
| `yate/diagnostics.py:125` | `print_report()` 的唯一职责就是打印报告 | 正当豁免 |
| `yate/logs.py:104` | `warn()` 的唯一职责就是向 stderr 打 `yate: <msg>` | 正当豁免 |

无一条守卫防止后人在 L0/L1/L2 里塞 `print("debug ...")` 调试残留 —— 实测
`tools/` 下有 60+ 处 `print`（CLI 输出），一旦守卫面写宽就会误伤。

**改法**：在 `tests/test_architecture.py` 中新增用例，扫描面与豁免面**精确到文件+函数**：

```python
def test_no_debug_prints_in_library_modules() -> None:
    """``print()`` is banned outside the modules whose job is CLI output.

    ``python-coding-style.md`` 4.6 requires every runtime log line to go
    through :mod:`yate.logs`' tracing service, so a stray ``print()`` in a
    library module would bypass both the ``YATE_TRACE`` switch and the
    devtools bridge (R12) and corrupt the TUI.  Three modules legitimately
    own stdout/stderr output -- the CLI front door and the two reporting
    helpers -- and they are exempted by module path plus function name so a
    new ``print()`` anywhere else, including inside those files, still fails.
    """
```

**扫描面**：`yate/` 全部 `.py` 的 AST `ast.Call`，`func` 为 `ast.Name(id="print")`。

**豁免面**（白名单，必须逐名登记，不得按目录粗放）：

| 模块 | 允许的宿主 | 依据 |
|---|---|---|
| `cli.py` | `main` 及其直接调用的私有助手（`_manage_extensions`、`_validate_diff_args`） | CLI 的 stdout 是产品输出（`cli.py:350` setup 报告、`:372` cleanup 报告） |
| `diagnostics.py` | `print_report` | 函数 docstring 自述职责（`diagnostics.py:120-121`） |
| `logs.py` | `warn` | 函数 docstring 自述职责（`logs.py:95-101`） |

**断言**：
1. 遍历每个 `.py`，每个 `print()` 调用的 `lineno` 对应的 `(模块, 宿主函数名)` 必须在豁免表内；
2. 违反时报出 `文件:行号` 与宿主函数名；
3. **反向演练**（执行者必须实测）：临时在 `yate/editor_core/words.py` 插入一行
   `print("x")` → 本用例**必须失败**；随即还原。

> **负向演练是硬要求**：`subagent-workflow.md` §三.2 与 `architecture-boundaries.md`
> §六「负向演练过」的传统一致 —— 未演练的守卫不算落地。

### A-2 · 新增守卫 `test_comments_and_docstrings_stay_ascii`

**为什么是问题**：`misc-rules.md` §四 明文「仓库内一切代码文件的注释与代码内注解
文档必须使用英文」，理由是「代码（含随包模板）面向国际化用户分发」。
实测 `tests/test_cells.py:68`（全角括号）与 `tests/test_lua_extensions.py:470`
（分节符残留）**通过了全部门禁**。

**改法**：新增用例，用 `tokenize` 逐 token 取 `COMMENT` 与 `STRING`（docstring 段），
拒绝 CJK 与全角标点。

**扫描面**：`yate/` + `tools/` + `tests/` 全部 `.py`。

**豁免面**（必须逐条实测确认，执行者在本步把实测结果回填本节）：
1. **测试断言数据**里的非 ASCII 字符（`tests/test_cells.py:69` 的 `cell_to_char("ab（cd", 4)`）
   —— 它是**被测数据**，不是注释/docstring；扫描器只看 `COMMENT` token 与
   `STRING` token 的**首行 docstring**（即 `ast.get_docstring` 路径），不看其它字符串字面量；
2. **docstring 内引述规则编号**的写法：若某 docstring 需要指 `§三.5`，应写
   `section 3.5`（`plan_a` 已按此收口 `tests/test_lua_extensions.py:470`）；
   本守卫不为此开豁免。

**断言**：
1. 每个 `COMMENT` token 的文本与每个模块/类/函数的 docstring 首行文本中，
   不得出现 `U+0080–U+FFFF` 的**标点/符号**类字符（CJK 统一表意文字、全角标点、
   分节符 `§`）；
2. 违规时报出 `文件:行号` 与 offending 字符的 `U+XXXX`；
3. **反向演练**：在 `yate/logs.py` 某注释里插入一个汉字 → 必须失败；随即还原。

> **实现注意**：用 `str.isascii()` 是**过宽**的实现 —— 会误伤 `editor_sprites/chars/*.py`
> 的像素数据（`megaman.py` 等全是 ASCII，安全）与 `yate/docs/` 侧的说明。
> 实现应精确为「拒绝 CJK 统一表意文字（`U+4E00–U+9FFF`）与全角标点（`U+FF00–U+FFEF`）
> 与 `§`(U+00A7) / `°`(U+00B0) 之类排版符号」，**允许** ASCII 与其它拉丁/希腊字母。

### A-3 · 新增守卫 `test_repository_documents_contain_no_real_machine_paths`

**为什么是问题**：`doc-conventions.md` §五 第 2 段「真实路径脱敏（环境信息）」明文
禁止盘符路径、用户目录、仓库根绝对路径，且「**对命令示例代码块同样适用**」。
实测 `tools/probes/win32im_probe.py:7` 的
`d:\\Programming\\yate\\.venv\\Scripts\\python.exe` 通过了全部门禁。

**改法**：新增用例，扫 `.trae/**/*.md` + `yate/docs/**/*.md` + `README*.md`
+ `CHANGELOG*.md` + `tools/**/*.py` 的 docstring 与注释。

**模式与豁免面**：

| 模式 | 命中示例 | 处置 |
|---|---|---|
| `[A-Za-z]:[\\/]{1,2}` 盘符绝对路径 | `d:\Programming\yate\...` | **禁**（除非写成 `C:\Users\<user>\` 这类占位符形态） |
| `/home/<user>/` `/Users/<user>/` | — | **禁** |
| `https://…` `http://…` | 全仓数百处 | **不匹配**（`doc-conventions.md` §五 第 3 段明文豁免外部 URL）——实现必须用负向断言确保 URL 不被命中 |
| `C:\Users\xxx\` `C:\...` `D:\tmp\...` 占位符 | `diag-command-plan.md:99-156` 大量使用 | **豁免**（`2026-10-05-doc-review-sweep` 已确立的占位符口径：至少含 `xxx` / `...` / `<user>` 之一） |

**断言**：
1. 对每个被扫文件的每一行，若命中盘符/家目录模式，则该行必须同时含
   占位符标记（`xxx` / `...` / `<user>` / `<checkout>`）；否则报 `文件:行号`；
2. **负向断言**：`https://` 开头的行**不得**被判违规（否则守卫自身误报）；
3. **反向演练**：在 `.trae/rules/misc-rules.md` 某行插入
   `cd d:\Programming\fake` → 必须失败；随即还原。

### A-4 · 规则文本同步（`.trae/rules/architecture-boundaries.md`）

**为什么必须同步**：`architecture-boundaries.md` §六 是 32 用例的**权威对照表**
（`:446-481`），并声明「`tests/test_architecture.py` 已落地 **32 个用例**」。
新增 3 条守卫后若不同步，规则文本与守卫面立即漂移 —— 这正是 C-6（`2026-10-17` 审计
MAJOR）的成因形态，不得重犯。

**改法**（三处）：

1. `:368-369` 的计数句：`已落地 **32 个用例**（2026-10-17 实测复核：... → `32 passed`；`
   → 改为 `已落地 **35 个用例**（2026-10-18 新增三条非 ASCII / print / 真实路径守卫；`
   `此前 2026-10-17 实测复核：... → `32 passed`；`
2. §六 守卫条目列表末尾追加三条（格式与既有条目一致，含守卫项标签）：

```markdown
- **代码注释与 docstring 的 ASCII 纪律**（`misc-rules.md` §四，2026-10-18 新增）：
  `test_comments_and_docstrings_stay_ascii` 扫描 ``yate/`` + ``tools/`` + ``tests/``
  的 ``COMMENT`` token 与 docstring 首行，拒绝 CJK 统一表意文字、全角标点与排版符号；
  被测数据里的非 ASCII 字符串字面量不拦截（它们是断言输入，不是注释）；
- **库模块禁 ``print()``**（`python-coding-style.md` §4.6，2026-10-18 新增）：
  `test_no_debug_prints_in_library_modules` 对 ``yate/`` 做 AST 扫描，仅豁免
  ``cli.py`` 的 CLI 输出路径与 ``diagnostics.py::print_report`` /
  ``logs.py::warn`` 两个自述职责的报告函数；``tools/`` 全部 CLI 包不在扫描面
  （它们的 ``print`` 就是产品输出）；
- **文档真实路径脱敏**（`doc-conventions.md` §五 第 2 段，2026-10-18 新增）：
  `test_repository_documents_contain_no_real_machine_paths` 扫 ``.trae/**/*.md`` /
  ``yate/docs/**/*.md`` / 根级 README 与 CHANGELOG / ``tools/`` 的注释与 docstring，
  拒绝盘符与家目录绝对路径，豁免 ``C:\Users\xxx\`` 这类占位符形态，并显式不匹配
  外部 URL（§五 第 3 段）。
```

3. `:446-481` 的「32 个用例逐条对照」表末尾追加三行（`| 33 |` / `| 34 |` / `| 35 |`），
   并把表头 `**32 个用例逐条对照**（2026-10-17 实测 `32 passed`）` 改为
   `**35 个用例逐条对照**（2026-10-18 实测 `35 passed`；2026-10-17 为 `32 passed`）`。

---

## 四、备选方案与否决理由

| 备选 | 否决理由 |
|---|---|
| A-1 按「扫描 `yate/` 全部 `print`」而不开豁免 | 实测 `yate/` 内 14 处 `print` **全部正当**（CLI 输出 / 两个自述职责的报告函数）。不开豁免会让守卫在落地第一刻就红，执行者要么写豁免要么删 CLI 的输出 —— 后者是行为退化。 |
| A-1 把 `tools/` 也纳入扫描面 | `tools/` 8 个子包全是构建/发布 CLI，`print` 就是产品输出（实测 60+ 处）。纳入即恒红，等于没有守卫。 |
| A-2 用 `str.isascii()` 一刀切 | 会误伤**合法**的非 ASCII 注释需求（如引用第三方文档标题的拉丁重音）与 `tools/probes/` 的证据附件注释；且会与 `doc-conventions.md` §三（用户文档可双语）混淆边界。精确模式（拒绝 CJK/全角/排版符号）才是 §四 的语义。 |
| A-2 只扫 `yate/`，不扫 `tests/` | 本轮两处负样本**都在 `tests/`**（`test_cells.py:68`、`test_lua_extensions.py:470`）。只扫 `yate/` 等于没补这个缺口。 |
| A-3 只扫 `.trae/**/*.md` | `misc-rules.md` §四 的适用面含「一切代码文件」，而实测负样本
   `tools/probes/win32im_probe.py:7` **在 `tools/`**。只扫文档等于没补这个缺口。 |
| A-3 顺带把存量占位符形态（`C:\Users\xxx\`）也判违规 | `2026-10-05-doc-review-sweep` 已确立占位符是**合规**的脱敏写法
   （`.trae/documents/doc-review-sweep-plan.md:170` 明文列举 `C:\Users\xxx` /
   `C:\...` / `C:\my` / `D:\tmp\...` 为正确示例）。把它们判违规会造成大面积无意义返工。 |
| 合并三条为一条守卫用例 | 三条守的是**三条不同规则**（§4.6 日志 / misc §四 注释 / doc-conventions §五 路径）。合并后任一子项失败都难以定位，且违反「一条用例守一条可回归契约」的既有形态（§六 32 条逐条对应）。 |

---

## 五、新增测试用例（详细三要素）

三条新用例本身就是「用例」，此处按守卫测试规范写全三要素。
**实施顺序**：A-2 → A-3 → A-1（先落两条纯文档/注释守卫，最后落 AST 扫描守卫，
因为 AST 扫描的实现复杂度最高，放最后有 `plan_a`/`plan_b` 的改造做活体验证样本）。

### 用例 33

- **文件**：`tests/test_architecture.py`
- **用例名**：`test_comments_and_docstrings_stay_ascii`
- **前置条件 / fixture**：无（纯文件扫描，不 import 被测模块 —— 与既有
  `test_no_relative_imports` / `test_callable_aliases_use_type_statements` 同形态）
- **arrange**：枚举 `yate/` + `tools/` + `tests/` 全部 `.py`；对每个文件
  用 `tokenize.generate_tokens` 取 `COMMENT` token；对每个模块/类/函数用
  `ast` 取 docstring 首行
- **act**：对每段文本运行 `_BANNED_COMMENT_CHARS` 判定
- **断言**：
  1. 无任何命中；有命中则失败信息含 `文件:行号` 与字符 `U+XXXX`；
  2. **反向演练**：`yate/logs.py` 注释插入一个汉字后本用例必须失败；
  3. **正向存样**：`tests/test_cells.py:69` 的 `cell_to_char("ab（cd", 4)` **不得**触发
     （字符串字面量不是注释也不是 docstring）

### 用例 34

- **文件**：`tests/test_architecture.py`
- **用例名**：`test_repository_documents_contain_no_real_machine_paths`
- **前置条件 / fixture**：无
- **arrange**：枚举 `.trae/**/*.md`、`yate/docs/**/*.md`、
  `README.md` / `README.zh.md` / `CHANGELOG.md` / `CHANGELOG.zh.md`；
  另枚举 `tools/**/*.py` 的 `COMMENT` token 与 docstring 首行
- **act**：对每行跑 `_REAL_PATH_RE`（盘符 + `/home/<u>/` + `/Users/<u>/`）；
  命中后再检查该行是否含占位符标记（`xxx` / `...` / `<user>` / `<checkout>`）
- **断言**：
  1. 「命中且无占位符标记」的行数为 0；失败信息含 `文件:行号` 与原文行；
  2. **负向断言**：对 `https://` 与 `http://` 出现的行数 **必须 > 0**（证明过滤器
     没有把外部 URL 误判 —— `doc-conventions.md` §五 第 3 段）；若为 0 说明正则
     写宽了，需修正；
  3. **反向演练**：在 `.trae/rules/misc-rules.md` 插入 `cd d:\Programming\fake`
     后本用例必须失败

### 用例 35

- **文件**：`tests/test_architecture.py`
- **用例名**：`test_no_debug_prints_in_library_modules`
- **前置条件 / fixture**：无（AST 扫描，不 import）
- **arrange**：枚举 `yate/` 全部 `.py`；用 `ast.parse` 找
  `ast.Call(func=ast.Name(id="print"))`；对每个命中求其宿主函数名
  （向上找最近的 `FunctionDef` / `AsyncFunctionDef`，模块顶层则记为 `<module>`）
- **act**：断言每个 `(模块相对路径, 宿主函数名)` 落在 `PRINT_EXEMPT_SITES` 白名单内
- **断言**：
  1. 违规数为 0；失败信息含 `文件:行号` 与宿主函数名；
  2. **正向存样**：`cli.py` / `diagnostics.py` / `logs.py` 的既有 14 处
     `print` 全部在白名单内（守卫落地即证明豁免面完整）；
  3. **反向演练**：在 `yate/editor_core/words.py` 顶层插入 `print("x")` →
     本用例必须失败（宿主记为 `<module>`，不在白名单）

---

## 六、验证方案

| 验证目标 | 命令（PowerShell，仓库根） | 通过判定 |
|---|---|---|
| 三条新守卫生效且不误伤 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 退出码 0，**35 passed** |
| 计数同步正确（规则 vs 守卫） | `.venv\Scripts\python.exe -c "import re,pathlib;t=pathlib.Path('.trae/rules/architecture-boundaries.md').read_text(encoding='utf-8');print(len(re.findall(r'^\| \d+ \| ',t,re.M)))"` | 输出 `35` |
| 规则文本引用完整性 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k "ascii or real_machine or debug_prints"` | 退出码 0，3 passed |
| 改动文件类型零诊断 | `.venv\Scripts\python.exe -m pyright tests/test_architecture.py` | 0/0/0，退出码 0 |
| 全仓零回归 | `.venv\Scripts\python.exe -m pytest tests/ -q` | 退出码 0 |
| **负向演练已执行**（三条各一次） | 手工步骤见 §七 | 三次演练均观察到手写用例失败并已还原 |

## 七、手工验证（负向演练，不可自动化）

三条守卫各做一次负向演练，**每次演练必须在报告里记录「插入内容 → 用例名 → 失败输出 → 还原确认」四要素**：

1. **A-2 演练**：在 `yate/logs.py` 某 `#` 注释末尾追加一个汉字 →
   `pytest tests/test_architecture.py -q -k ascii` 必须失败且报错点名该行 →
   `git checkout -- yate/logs.py` 还原 → 复跑必须通过；
2. **A-3 演练**：在 `.trae/rules/misc-rules.md` 末尾追加一行
   ``  cd d:\Programming\fake`` →
   `pytest tests/test_architecture.py -q -k real_machine` 必须失败 →
   还原 → 复跑通过；
3. **A-1 演练**：在 `yate/editor_core/words.py` 末尾追加 `print("probe")` →
   `pytest tests/test_architecture.py -q -k debug_prints` 必须失败 →
   还原 → 复跑通过。

> **纪律**：任何一次演练未做或未记录，该守卫按「未落地」处理，
> 不得在收尾报告里声称守卫已生效（`subagent-workflow.md` §三.2「只认落盘结果」）。

## 八、风险与回滚

| 风险 | 概率 | 缓解 |
|---|---|---|
| A-1 豁免面写窄，`cli.py` 里新加的 `_validate_diff_args` 打 `print` 时误红 | 中 | 豁免表按「模块 + 宿主函数名」登记，并在规则文本里写明新增 CLI 助手须登记 —— 把维护成本显式化而非放宽到目录级 |
| A-2 误伤 `tools/probes/` 的证据附件注释（含引述性中文，既有 F-10 口径） | 中 | 执行者须在 Phase 1 实测全仓命中清单，把 `tools/probes/` 的既有命中**逐条**在守卫里豁免并在规则文本登记理由；若实测命中过多，执行者须在报告里提出「缩小扫描面到 `yate/` + `tests/`」的偏离并附实测依据 |
| A-3 误伤存量占位符（`C:\Users\xxx\`）造成大面积返工 | 中 | 占位符白名单已在 §三 逐条列出；验收命令「`pytest tests/test_architecture.py -q -k real_machine`」在落地前必须先跑一次**只读预演**（临时改扫描范围不影响仓库）确认存量命中为 0 |
| 规则文本 32 → 35 的三处计数不同步 | 中 | §五「计数同步正确」命令直接断言对照表行数为 35；`overview.md` §五 维度 9 也需在执行后回填实测 `35 passed` |
| 三条守卫与 `plan_c` 的改造互相掩盖 | 低 | 两者独占文件无交集（`plan_c` 改 `yate/` 业务模块，`plan_d` 只改守卫与规则）；且 `plan_c` 的 M-2 正是 A-2 之外的另一类问题（静默吞异常），由 `plan_c` 自己的验收命令覆盖 |

**回滚**：`git revert <commit>`（守卫与规则文本同一 commit，回滚后回到 32 用例、
计数与对照表同步复原，无残留）。若只回滚守卫而留规则文本，会重现 C-6 类漂移 ——
**必须同 commit**。
