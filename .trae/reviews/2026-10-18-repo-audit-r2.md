# 2026-10-18 repo-audit-r2 · plan_d 执行记录（架构守卫缺口收口）

- 来源方案：[`../documents/repo-audit-r2-plans/repo-audit-r2-architecture-plan-d.md`](../documents/repo-audit-r2-plans/repo-audit-r2-architecture-plan-d.md)（总纲 [`overview.md`](../documents/repo-audit-r2-plans/overview.md)）
- 波次：wave-2（与 `plan_c` 并行，独占文件无交集）
- 落地范围：`tests/test_architecture.py` 新增 **2** 条守卫 + `.trae/rules/architecture-boundaries.md` §六 同步
  （计划为 3 条，见 §四 A-3 未落地项）

---

## 一、守卫清单（新增 2 条，用例 33 / 34）

| # | 用例 | 守的规则 | 扫描面 | 豁免面 |
|---|---|---|---|---|
| 33 | `test_comments_and_docstrings_stay_ascii` | `misc-rules.md` §四「注释与代码内注解文档一律英文」 | `yate/` + `tools/` + `tests/` 全部 `.py` 的 `COMMENT` token 与模块/类/函数 docstring | `NON_ASCII_COMMENT_EXEMPT`：实测 6 处**引述型**存量命中，逐条登记（见 §二）；字符串字面量不在拦截面 |
| 34 | `test_no_debug_prints_in_library_modules` | `python-coding-style.md` §4.6「禁止 `print()` 用于调试」 | `yate/` 全部 `.py` 的 `ast.Call(func=ast.Name(id="print"))`，按「模块 + 最近宿主函数名」判定 | `PRINT_EXEMPT_SITES`：`cli.py::main` / `cli.py::_manage_extensions` / `diagnostics.py::print_report` / `logs.py::warn`；`tools/` 不在扫描面 |

拒绝字符集 `BANNED_COMMENT_RANGES`：`§`(U+00A7)、`°`(U+00B0)、CJK 标点(U+3000–U+303F)、
CJK 统一表意文字(U+4E00–U+9FFF)、全角/半角(U+FF00–U+FFEF)。ASCII 与其它拉丁/希腊字母放行
（不用 `str.isascii()` 一刀切，避免误伤引述性重音字母）。

## 二、活体负样本（守卫零误伤的证据）

用例 33 的 6 处豁免**全部是活体负样本**——它们今天就在扫描面里，若豁免表写窄或键写错，
用例会立刻红。逐条实测来源与豁免理由：

| 位置 | 字符 | 性质（豁免理由） |
|---|---|---|
| `tests/test_pack_spec.py:226` `::_returned_call` | U+00A7 | docstring 引述它自己执行的规则编号 `§4.5` |
| `tests/test_pack_spec.py:594` `::test_contents_dirname_…runtime_dir` | U+00A7 | 同上（引述外部行为 + 规则） |
| `tools/changelog/__init__.py::<module>` | U+7F3A | docstring 记录它**产出**的 zh 标记 `[缺中文]`——是产品字符串，不是中文行文 |
| `tools/changelog/segments.py::<module>` | U+00A7 | docstring 引述冻结的 changelog 计划章节 `§2` |
| `tools/probes/pb6_real_input_harness.py::ensure_english_layout` | U+5143 | docstring 引述实测证据（`x` → 组合出的 `先` 键），属 F-10 证据附件口径 |
| `yate/editor_sprites/characters.py:62`（模块层 `#:` 注释） | U+00A7 | 注册表注释引述计划章节 `§4.4` |

用例 34 的 4 个豁免宿主共 **12 处**存量 `print()`（`cli.py` 7 处 + `_manage_extensions` 5 处、
`diagnostics.py::print_report` 1 处、`logs.py::warn` 1 处），实测与方案 §三 A-1 的表格**逐条吻合**。
按「模块 + 宿主函数名」双重登记的后果：`cli.py` 里新增一个打 `print` 的助手函数仍会失败
（方案 §八 风险行「豁免面写窄」的缓解措施已落地）。

方案 §三 A-2 曾预设的活体负样本 `tests/test_cells.py:69` 的 `cell_to_char("ab（cd", 4)`
**仍然在扫描面里**（实测确认：`:69` 与 `:76` 的全角 `（` 都在**字符串字面量**内，
wave-1 的 `plan_a` 只改写了同段的**注释**）。它正是「非 ASCII 字符串字面量不得被拦截」
这条放行口径的活体证据：本次落地后该用例通过，即证明守卫把字符串字面量判为被测数据
而非注释。若有人日后把扫描面误扩到 `ast.Constant`，这两行会立刻把守卫打红。

## 三、负向演练记录（四要素，方案 §七硬要求）

| 演练 | 插入内容 | 用例 | 观察到的失败输出 | 还原确认 |
|---|---|---|---|---|
| A-2（注释分支） | `yate/logs.py` 末尾追加 `# probe` + U+8BD5 U+63A2 | `test_comments_and_docstrings_stay_ascii` | `AssertionError: ["yate/logs.py:692 comment ['U+8BD5', 'U+63A2']"]`，退出码 1 | `git checkout -- yate/logs.py` → 复跑退出码 0，`git status` 无该文件 |
| A-2（docstring 分支） | `yate/editor_core/words.py:1` 模块 docstring 首行插入 `probe 汉字.` | 同上 | `AssertionError: ["yate/editor_core/words.py:1 docstring <module> ['U+6C49', 'U+5B57']"]`，退出码 1 | `git checkout -- yate/editor_core/words.py` → 复跑退出码 0 |
| A-1 | `yate/editor_core/words.py` 末尾追加顶层 `print("probe")` | `test_no_debug_prints_in_library_modules` | `AssertionError: [… 'editor_core/words.py:84 print() in <module>()']`，退出码 1 | `git checkout -- yate/editor_core/words.py` → 复跑退出码 0，`git status` 无该文件 |

A-2 的 docstring 分支演练是**方案未列**的补充：`_docstring_site()` 辅助函数在 pyright 修正后
新增了一条取行号路径，只演练注释分支不足以证明该路径可拦截，故补做。

## 四、A-3 未落地（偏离方案，实测依据）

方案 §三 A-3 要求新增「文档真实路径脱敏」守卫，并在 §八 规定「落地前必须先跑一次只读预演
确认存量命中为 0」。**只读预演实测存量命中 42 处 / 21 个文件，与该前提冲突**：

- `.trae/documents/` 15 个文件：`dist-copy-plan.md`(10)、`pr60-ctrlp-preview-review-fixes-plan.md`(4)、
  `repo-audit-r2-architecture-plan-d.md`(5)、`doc-review-sweep-plan.md`(3)、
  `dap-support-plan.md`(2)、`multi-cursor-plans/overview.md`(2)、`path-space-handling-plan.md`(2)，
  以及 `diag-command-plan.md` / `editor-syntax-langdefs-plan.md` / `logs-impl-plan.md` /
  `lua-extensions-plan.md` / `pack-wiki-review-fixes-plan.md` /
  `repo-audit-r2-doc-hygiene-plan-a.md` / `split-module-tests-plans/overview.md` 各 1；
- `.trae/reviews/` 4 条：`2026-10-03-python-code-review.md`、`2026-10-05-doc-review-sweep.md`、
  `2026-10-07-pr60-ctrlp-preview-ai-review.md`、`2026-10-07-pr60-round2-ai-review.md` 各 1；
- `yate/docs/lsp.en.md` / `yate/docs/lsp.zh.md` 各 1（`C:\tools\pyright-langserver.cmd`）。

命中内容分两类：历史文档里的**真实 worktree 路径**（`D:\Programming\yate-*`）与**占位符形态**
（`C:\Python311`、`D:\tmp\yate-releases`、`/home/user/project`）。方案 §三 的豁免面要求占位符行
必须含 `xxx` / `...` / `<user>` 标记，这些行**均不含**，因此豁免面覆盖不到。

**处置**：按 plan-executor 纪律「遇到计划未覆盖的情况时停下上报」，本子计划**未落地** A-3，
也**未**以放宽扫描面或加豁免名单的方式凑绿。清理这 42 处需改动 21 个历史文档，
全部在本子计划独占文件清单之外，须由主代理决定：清扫存量、还是另案收窄扫描面。
`architecture-boundaries.md` §六 已把该缺口显式登记为「未落地项」，避免规则文本与守卫面漂移。

## 五、实测门禁（退出码均为 0）

| 验证目标 | 命令 | 结果 |
|---|---|---|
| 架构用例全绿 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 34 passed，退出码 0（基线 32） |
| 新守卫定向 | `… -m pytest tests/test_architecture.py -q -k "ascii or debug_prints"` | 2 passed，退出码 0 |
| 计数同步（规则 vs 守卫） | `… -c "import re,pathlib;…len(re.findall(r'^\| \d+ \| ',t,re.M))"` | 输出 `34` |
| 改动文件类型零诊断 | `.venv\Scripts\python.exe -m pyright tests/test_architecture.py` | `0 errors, 0 warnings, 0 informations`，退出码 0 |

全仓 `pytest tests/ -q` 由主代理在 wave 汇总时统一执行（本子计划不并发跑，避免与 Textual
pilot 互相干扰）。

## 六、规则文本同步位置

`.trae/rules/architecture-boundaries.md`：

- `:56`「§六 32 个架构守卫用例」→ `34 个`；
- `:368-370` 计数句 → `已落地 **34 个用例**`（保留 2026-10-17 的 `32 passed` 作为历史锚点）；
- §六 守卫条目列表末尾追加 2 条（非 ASCII 注释纪律 / 库模块禁 `print()`）+ 1 段「未落地项」说明；
- `:470` 对照表标题 → `**34 个用例逐条对照**（2026-10-18 实测 34 passed；2026-10-17 为 32 passed）`；
- 对照表追加 `| 33 |` / `| 34 |` 两行。
## 终局收口（2026-10-18，主代理）

### 合并
- `enh/repo-audit-r3` → `ref/repo-audit-r2`：干净合并（yaterc trust 门控 /
  active tab / LSP 常量清理 + r3 文档）。
- `enh/full-repo-audit` → `ref/repo-audit-r2`：3 个文件冲突（该分支对同一批
  静默吞异常的修复形态更弱——无异常详情、cleanup 路径 log 到不打印的通道），
  全部按本分支已评审版本解决；其评审记录与修复方案文档随合并入库。

### 评审处置（code-review-expert，两 skill 不可用按剧本单轨回退）
- [CRITICAL]：无。
- [WARNING] W1（测试污染真实信任库）/ W2（信任锚点应为 rc 所属目录）/
  W3（跳过无用户可见提示 + 手册未同步）/ W4（新用例时序敏感）：全部已修
  （commit `0c44e55`）。
- [SUGGESTION] S1-S6：S1/S2/S4/S5/S6 已修；S3 以扩展 ASCII 守卫到
  `*.py.example` 模板落地。

### 终局门禁（主代理亲跑，全部退出码 0）
| 门禁 | 结果 |
|---|---|
| pyright strict | 0 errors / 0 warnings / 0 informations |
| pytest 全量 + 架构守卫 | 2508 passed / 9 skipped（含 test_architecture 35 passed） |
| 覆盖率（fail_under=75，pyproject 单点源） | 91.99% |
| 冒烟 tools.smoke_test | 112/112 场景、1354/1354 checks |

### 遗留
- 文档面真实路径存量（42 处 / 21 个文件）按 doc-conventions §五「随下次修改
  迁移、不专项清扫」登记为待办（守卫只覆盖源码面）。
- 评审期间发现开发者真实信任库已被既有测试污染（18 条 pytest 临时目录条目），
  属本机环境数据，须手工清理（不在仓库范围内）。
