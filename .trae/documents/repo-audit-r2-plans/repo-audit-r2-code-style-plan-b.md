# repo-audit-r2 · plan_b：行宽、可维护性残留与命名纪律

- 波次：**wave-1**（与 `plan_a` 并行，文件互不重叠）
- 来源维度：4（可维护性）、11（代码与文档规范）、12（其它规则纪律）
- 状态：**待批准**（本阶段不改代码、不改测试）

---

## 一、输入

- 总纲：[`overview.md`](overview.md) §五 维度 4/11/12、§六 m-3、m-4
- 规范依据：
  - `python-coding-style.md` §1.1（行宽上限 **100 字符**；超长时函数签名/调用将参数分行
    4 空格悬挂）
  - `python-coding-style.md` §2.2（模块 docstring 首行紧接 `"""`，单行 docstring 闭合与开头同行）
  - `doc-conventions.md` §一（子计划文件命名 `<task>-<subtask>-plan-<a|b|c...>.md`；
    「**禁止下划线分词**（存量反例已随分支改名）；目录名统一连字符」）
- 既有结论关系：m-4 是 **F-12 的残留**（`2026-10-16-full-repo-audit.md` §二 维度 12）；
  m-3 是**全新**（既有审计未做行宽扫描）

## 二、独占文件清单（只改这 5 个路径）

1. `tools/smoke_test/scenarios/files.py`
2. `tools/smoke_test/scenarios/workspace_nav.py`
3. `tests/test_app_find.py`
4. `.trae/documents/ext-api-parity-plans/plan_a.md`（改名）
5. `.trae/documents/ext-api-parity-plans/plan_b.md`（改名）
6. `.trae/documents/ext-api-parity-plans/plan_c.md`（改名）
7. `.trae/documents/ext-api-parity-plans/plan_d.md`（改名）

> 第 4–7 项是 `git mv` 改名（不改内容），列在独占清单内是因为改名会改写 git 索引条目。
> **`tools/probes/win32im_probe.py` 的第 7 行不在本清单** —— 它的行宽违规由 `plan_a`
> 的路径脱敏改造一并消除（见总纲 m-3 说明）。

---

## 三、具体修改

### m-3a · `tools/smoke_test/scenarios/files.py:12`（实测 104 字符）

**现状**：

```python
from tools.smoke_test.scenarios._base import message_text, run_command, type_path, type_text, wait_until
```

**为什么是问题**：超 `python-coding-style.md` §1.1 的 100 字符上限。修法按该条
「函数签名/调用：将参数分行对齐首参数或 4 空格悬挂」的同构形态（导入列表同理）：

**改法**：

```python
from tools.smoke_test.scenarios._base import (
    message_text,
    run_command,
    type_path,
    type_text,
    wait_until,
)
```

（尾部逗号保留 —— §1.1 要求列表/元组尾逗号保留。）

### m-3b · `tools/smoke_test/scenarios/workspace_nav.py:30`（实测 106 字符）

**现状**：

```python
from tools.smoke_test.scenarios._base import cursor_path, message_text, run_command, type_text, wait_until
```

**改法**（同上形态）：

```python
from tools.smoke_test.scenarios._base import (
    cursor_path,
    message_text,
    run_command,
    type_text,
    wait_until,
)
```

### m-3c · `tests/test_app_find.py:1`（实测 112 字符）

**现状**（模块 docstring 首行）：

```python
"""Prompt bar, command line, goto and completion headless Textual UI tests (run via pilot, no real terminal)."""
```

**为什么是问题**：模块 docstring 首行超宽。`python-coding-style.md` §2.2 允许多行
docstring（第一行摘要 + 空行 + 详细描述，闭合 `"""` 独占一行）；该文件第 3 行起已有
续写内容，把首行按 `§2.2` 的规范多行形态折行即可，不改语义。

**改法**：

```python
"""Prompt bar, command line, goto and completion headless Textual UI tests.

Run via pilot, no real terminal.
"""
```

### m-4 · `.trae/documents/ext-api-parity-plans/` 四个下划线分词文件名

**现状**（`dir /b` 实测）：

```
overview.md
plan_a.md
plan_b.md
plan_c.md
plan_d.md
```

**为什么是问题**：违反 `doc-conventions.md` §一 —— 子计划文件必须命名为
`<task>-<subtask>-plan-<a|b|c...>.md`（「**禁止下划线分词**」条目把
`vim_keymap_review_plan.md` 列为反例，并说明该反例已随分支改名为
`vim-keymap-review-plan.md`）。现存 4 个下划线文件是同一形态的存量残留
（`2026-10-16-full-repo-audit.md` §二 维度 12 F-12 登记为「存量随下次修改迁移」）。
本次正处于「下次修改」，故按规范收口。

**改法**：`git mv` 到连字符形态（`task` 段 = 目录名 `ext-api-parity`）：

| 改前 | 改后 |
|---|---|
| `ext-api-parity-plans/plan_a.md` | `ext-api-parity-plans/ext-api-parity-plan-a.md` |
| `ext-api-parity-plans/plan_b.md` | `ext-api-parity-plans/ext-api-parity-plan-b.md` |
| `ext-api-parity-plans/plan_c.md` | `ext-api-parity-plans/ext-api-parity-plan-c.md` |
| `ext-api-parity-plans/plan_d.md` | `ext-api-parity-plans/ext-api-parity-plan-d.md` |

`overview.md` **不改名**（§一 明文「子计划目录总纲 `overview.md`」，是唯一合规的固定名）。

### m-4 连带面核对（必做，否则改名会留下断链）

改名后必须同步所有指向这四个文件的引用。**核对方法**（只读，Phase 1 必跑）：

```powershell
.venv\Scripts\python.exe -c "import pathlib;print([f'{p.as_posix()}:{i}:{l.strip()}' for p in pathlib.Path('.').rglob('*.md') if '.venv' not in p.parts for i,l in enumerate(p.read_text(encoding='utf-8',errors='replace').splitlines(),1) if 'ext-api-parity-plans/plan_' in l])"
```

**处置规则**（Phase 2 按实测结果逐条执行）：

- 命中项**只允许**改链接目标文件名，**不得**改动链接所在文档的任何其它内容；
- 引用一律写成**相对路径**（`doc-conventions.md` §五 第 1 条），若某处写成了绝对路径或
  仓库根绝对路径，**顺手按 §五 修正为相对路径**并在报告里注明；
- 本次 `p3.py` 探针已确认 `.trae/documents/` 内**无** `ext-api-parity-plans/plan_` 的
  命中记录被截断，故 Phase 1 输出的每一行都必须逐条处理，不得抽样。

---

## 四、备选方案与否决理由

| 备选 | 否决理由 |
|---|---|
| m-3 三处用 `# noqa: E501` 之类豁免 | `python-coding-style.md` §6.1 明确映射 PEP 20「Special cases aren't special enough to break the rules」，且 §五 快速检查清单把「行宽 ≤ 100」列为硬项；豁免注释属规则明文禁止的绕过形态（`plan-before-execute.md` §三「禁止出现模糊步骤」，架构规则 §六末行「不得用豁免注释绕过」的同类精神）。 |
| m-3c 保留单行 docstring、只把超宽部分挪到第二行（不空行） | 违反 `python-coding-style.md` §2.2「多行 docstring：第一行摘要 + **空行** + 详细描述」；会产出与全仓不一致的 docstring 形态（§6.3 第 2 条「可读性 > 风格一致性」不能用来违反 §2.2 的显式结构要求）。 |
| m-4 只改名 `plan_a.md` 一个，其余保留 | 规范是目录级的：`doc-conventions.md` §一 的命名表对子计划文件是统一形态要求，只改一个会让目录内形态分裂，比不改更糟。 |
| m-4 连带把 `overview.md` 也改成 `ext-api-parity-overview.md` | `doc-conventions.md` §一 硬性要求「子计划目录总纲 `overview.md`（**不用** README.md）」；改名反而违规。 |

---

## 五、新增测试用例（详细三要素）

### m-3 门禁自证（不入库为测试，作为验收断言执行）

行宽属风格门禁，项目当前**没有**行宽守卫（`tests/test_architecture.py` 32 用例无对应项）。
本子计划**不新增**行宽守卫用例 —— 该缺口由 `plan_d` 决策是否补（`plan_d` 已登记
A-1~A-3 三条守卫缺口，行宽不在其列，因为 §1.1 已有 `.editorconfig` 侧约束）。
本轮以**一次性探针**自证：

- **验证目标**：m-3 三处改造后 `tools/` + `tests/` 全仓 >100 字符行归零
- **命令**：`.venv\Scripts\python.exe -c "import pathlib;print([f'{p.as_posix()}:{i}' for b in ('yate','tools','tests') for p in pathlib.Path(b).rglob('*.py') for i,l in enumerate(p.read_text(encoding='utf-8').splitlines(),1) if len(l)>100])"`
- **通过判定**：输出 `[]`

### m-3b 导入形态的行为回归

- **文件**：`tests/test_smoke_tool.py`（既有，**不新增文件**）
- **用例名**：`test_smoke_scenarios_import_and_register`（既有覆盖 `tools.smoke_test.scenarios`
  的发现与注册面；折行是纯语法等价改造，该用例是它的回归锚）
- **前置条件 / fixture**：无
- **arrange**：`importlib` 导入 `tools.smoke_test.scenarios.files` 与
  `tools.smoke_test.scenarios.workspace_nav`
- **act**：读取两模块的 `SCENARIOS`
- **断言**：两模块的 `SCENARIOS` 均为**非空列表**，且每个元素是 `Scenario` 实例
  （证明 `from ... import (...)` 折行后 5 个名字全部正确绑定 —— 若漏掉一个名字，
  模块体在首次访问该名字时抛 `NameError`，本用例即失败）

> **验证目标**：折行改造没有漏绑 `_base` 的任一符号。

### m-3c docstring 折行的行为回归

- **文件**：`tests/test_app_find.py`（**既有**，不新增用例）
- **用例名**：该文件既有的 `test_prompt_*` / `test_completion_*` 全部用例
- **验证目标**：模块 docstring 首行折行不影响任何收集/夹具行为
- **命令**：`.venv\Scripts\python.exe -m pytest tests/test_app_find.py -q`
- **通过判定**：退出码 0，用例数与改造前**完全一致**（不得增删用例）

### m-4 改名的链接完整性回归

- **验证目标**：`ext-api-parity-plans/` 四个新文件名被仓库内全部引用点正确指向，无断链
- **命令**（改名前后各跑一次，结果必须为空）：

```powershell
.venv\Scripts\python.exe -c "import pathlib;print([f'{p.as_posix()}:{i}:{l.strip()}' for p in pathlib.Path('.').rglob('*.md') if '.venv' not in p.parts for i,l in enumerate(p.read_text(encoding='utf-8',errors='replace').splitlines(),1) if 'ext-api-parity-plans/plan_' in l])"
```

- **通过判定**：退出码 0 且输出 `[]`（改名前应命中若干行并被逐条修完，改名后归零）

---

## 六、验证方案

| 验证目标 | 命令（PowerShell，仓库根） | 通过判定 |
|---|---|---|
| 折行导入未漏绑符号 | `.venv\Scripts\python.exe -m pytest tests/test_smoke_tool.py -q` | 退出码 0 |
| docstring 折行零回归 | `.venv\Scripts\python.exe -m pytest tests/test_app_find.py -q` | 退出码 0，用例数不变 |
| 全仓测试零回归 | `.venv\Scripts\python.exe -m pytest tests/ -q` | 退出码 0 |
| 改动文件类型零诊断 | `.venv\Scripts\python.exe -m pyright tools/smoke_test/ tests/test_app_find.py` | 0/0/0，退出码 0 |
| 行宽归零（自证） | 见 §五 m-3 命令 | 输出 `[]` |
| 改名无断链 | 见 §五 m-4 命令 | 输出 `[]` |
| 命名合规（自证） | `.venv\Scripts\python.exe -c "import pathlib,re;print([p.as_posix() for p in pathlib.Path('.trae/documents').rglob('*.md') if '_' in p.name and p.name!='legacy-issues.md'])"` | 输出 `[]`（`legacy-issues.md` 是 `doc-conventions.md` §二.1 明文保留的存量名，登记豁免） |

## 七、风险与回滚

| 风险 | 概率 | 缓解 |
|---|---|---|
| 折行时漏掉 `_base` 的某个符号 | 中 | §五 m-3b 的 `test_smoke_tool.py` 回归锚 + Phase 2 的「跑一遍测试再改」纪律 |
| 改名漏改引用点，留下断链文档 | 中 | §三 m-4 的 Phase 1 强制核对命令 + 改名前后各跑一次对比 |
| 改名被下游 `.trae/reviews/README.md` 之类索引引用而未被发现 | 低 | Phase 1 命令扫的是**全仓** `.md`（不限 `.trae/`），覆盖 README 索引 |
| 行宽改造误伤 `editor_sprites/chars/*.py` 的像素数据 | 零 | 探针实测这些文件无 >100 行（`megaman.py` 的长行是像素串但长度 <100）；§五 行宽命令覆盖 `yate/`，一旦误改即失败 |

**回滚**：`git revert <commit>`（m-3 部分纯格式，回滚零风险）；
m-4 的 `git mv` 回滚同样是 `git revert`，git 会还原文件名与索引条目，
但**已改的引用点会随之回退**（同一 commit 内），无需额外动作。
