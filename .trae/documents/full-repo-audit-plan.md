# full-repo-audit-plan

- Issue：[Gitee IKMD0E](https://gitee.com/jermaine/yate/issues/IKMD0E)（ENH - 全仓库多维度审核，创建于 2026-10-16 21:52）
- 分支：`enh/full-repo-audit`（worktree `../yate-full-repo-audit`，沙箱 `.venv` 已自证指向本 worktree）
- 日期：2026-10-16
- 状态：无人值守执行（22:00–06:00 规则，方案批准按通过处理，本行即为批准登记）
- 唯一规范来源：[`../rules/`](../rules/) 下全部 8 个规则文档（本计划起草前已逐个精读）；格式范本 [`repo-structure-audit-plan.md`](repo-structure-audit-plan.md)（同构审核，已执行完毕）

## 一、目标与非目标

**目标**（对齐 issue 12 个维度，逐维给出审计方法与判定依据，见 §三矩阵）：

1. **功能正确性**（维度 1）：对内核热路径（buffer / emulator / keymaps / flows）做边界抽查，发现项必须可复现（测试或手工步骤）；
2. **安全性**（维度 2）：盘点 `subprocess` / `shell=True` / `exec` / 密钥 / 路径拼接等攻击面，核对输入源与沙箱边界；
3. **性能**（维度 3）：以 profiler 实测为前提的疑点核查（不做预优化，见 python-coding-style §6.3.1）；
4. **可维护性**（维度 4）：python-coding-style §五清单的机械核对（docstring / 魔法数 / 嵌套 / 重复逻辑）；
5. **健壮性**（维度 5）：异常处理面扫描（裸 `except`、静默吞异常、缺 BLE001 注记）；
6. **可扩展性**（维度 6）：扩展 API 门面、注册表/回调接入点（architecture-boundaries §三.8 接入清单）与插件手册的一致性；
7. **项目结构合理性**（维度 7）：交叉引用 IKMCZW 结论 + 增量复核（不重复铺开）；
8. **模块职责单一性**（维度 8）：交叉引用 IKMCZW 结论 + 增量复核（不重复铺开）；
9. **架构边界规则**（维度 9）：R1–R14 违规信号 + 架构测试全绿；
10. **门禁规则**（维度 10）：四道门禁（pyright / pytest / 架构测试 / 覆盖率 ≥75%）实测；
11. **代码文档规范**（维度 11）：doc-conventions（命名 / 相对路径 / 双语同步）+ misc-rules §四（代码注释英文）；
12. **其他规则纪律性**（维度 12）：git-commit-message、misc-rules（here-string / 探针脚本）、豁免名单两处同步等散点纪律。

交付物形态（硬性）：

- 审核发现落盘 [`../reviews/2026-10-16-full-repo-audit.md`](../reviews/2026-10-16-full-repo-audit.md)——**只读事实文档**（doc-conventions §二.1：只记录发现与核对结论，不放修复排期）；
- 需要修复的问题按 doc-conventions §二.2 以 `<task>-plan.md` 形态立项，task 含 `review` 词根（合规格式如 `full-repo-audit-review-fixes-plan.md`），评审记录与修复方案互相链接；
- 产品源码（`yate/`、`tools/`）的修改**仅限"审核确证的真问题修复"**，禁止顺手重构；文档漂移（规则文档与实现不符）按仓库惯例属于可修复项。

**非目标**：

- 不做 `editor.py` 等大文件拆分（IKMCZW 已登记为下一个 big-module-split 候选，另行立项）；
- 不新增架构规则，只同步既有规则文档与实现的偏差；
- 维度 7/8 不重复 IKMCZW 已审完的铺开式核对，只做交叉引用 + 增量复核；
- 不做无 profiler 实测支撑的性能"优化"；
- 不在闭环流程内推送（推送仅在收尾按本任务指令统一执行一次）。

## 二、调研取证（计划制定者亲测，2026-10-16，worktree `enh/full-repo-audit` @ `b36f9b3`）

### 2.1 基线门禁

| 探针 | 结果 | 来源 |
|---|---|---|
| `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations，exit 0 | **本计划亲测** |
| `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 31 passed，exit 0 | **本计划亲测** |
| `.venv\Scripts\python.exe -m pytest tests/ -q` | 探针时限内跑至 14%（100% 通过无失败点）后超时；全量基线引分支既有执行记录（HEAD 即该任务回填提交）：全绿 exit 0，`--cov --cov-fail-under=75` 实测 **91.92%** | 探针 + [repo-structure-audit-plan.md §六](repo-structure-audit-plan.md) |
| `git status --porcelain` | 工作区干净 | **本计划亲测** |
| `git log --format=%s -40` | 40 条全部 `type(scope): subject` 英文 conventional 形态（`!85`/`!84` 前缀为 Gitee 推送引用标记，非提交信息本体） | **本计划亲测** |

### 2.2 代码面取证

| 取证点 | 实测 | 依据条款 | 结论 |
|---|---|---|---|
| `yate/` 模块数 / 行数 | 139 个 `.py` / 33,170 行（守卫口径 `splitlines()`） | — | 审计范围基准 |
| `tools/` 模块数 / 行数 | 60 个 `.py` / 11,875 行 | — | 审计范围基准 |
| `tests/` 模块数 / 行数 | 99 个 `.py` / 44,996 行（测试不设体量阈值，architecture-boundaries §三.7） | §三.7 | 合规 |
| `yate/` + `tools/` >800 行文件 | `editor.py` 1024、`buffer.py` 1069、`langdefs.py` 813、`vim.py` 1184、`tools/pack/wiki.py` 1495——与规则 §三.7 豁免名单登记数**逐项一致，零漂移** | §三.7 | 一致（IKMCZW 同步后） |
| 裸 `except:`（无类型） | 0 处（yate/ + tools/ + tests/） | python-coding-style §4.5 | 合规 |
| `import subprocess` 面 | `services/shell.py:43,72`、`services/fonts.py:113,281`、`editor_term/pty_proc.py:255`（自带 `# noqa: S603 - argv from config/user` 注记）、`editor.py:421`（回调转发） | pr-review §3.2 | 待执行期核对输入源 |
| `shell=True` | `services/shell.py:74`、`tools/pack/wiki.py:629` | pr-review §3.2 | **疑点**：待执行期确证用户可控字符串是否可达命令行 |
| `exec()` / `eval()` | `yaterc.py:170`、`editor_view/theme_files.py:70`（均带 `# noqa: S102 - intentional ...` 注记）；`services/extensions/lua/runtime.py:67,131,143-146`（扩展沙箱 API 面） | pr-review §3.2 | **疑点**：待执行期核对 namespace 沙箱边界 |
| 硬编码密钥（password/secret/api_key/token 赋值字面量） | 0 处 | pr-review §3.2 | 合规 |
| `# type: ignore` / `# pyright: ignore` | yate/ 共 13 处：`editor_view/themes.py:483,485,490,511`（reportUnnecessaryIsInstance ×4）、`editor_term/pty_proc.py:228-232,430,577`（平台导入 + ctypes ×7）、`editor_syntax/engine.py:83`（no-any-return ×1）、`tools/smoke_test/harness.py:56` ×1；tests/ 若干 | python-coding-style §4.2 | **疑点**：§4.2 要求极特殊场景需评审批准并附理由——待执行期逐处核对注记理由完备性 |
| 双语手册配对（`yate/docs/`） | extensions / lsp / themes / yaterc 共 4 对 `.en.md`/`.zh.md` + `README.md`，**全部成对** | doc-conventions §三 | 合规 |
| `.trae/` 文档内绝对路径 | 32 处命中，全部位于存量文档（历史审核记录 / 旧计划） | doc-conventions §五（"存量随下次修改逐步迁移，不做专项清扫"） | 存量豁免；本次新增文档不得新增 |
| 提交规范纪律 | 最近 40 条全 conventional（见 2.1） | git-commit-message | 合规 |
| 架构守卫面 | `tests/test_architecture.py` 31 用例全绿（亲测）；R6 `TYPE_CHECKING`、相对导入、命名守卫等静态项由守卫保证 | architecture-boundaries §六 | 合规 |

### 2.3 既有审核背景（避免重复劳动）

- **维度 7（项目结构）/ 维度 8（职责单一）**：IKMCZW 刚审完，结论见 [`../reviews/2026-10-16-repo-structure-audit.md`](../reviews/2026-10-16-repo-structure-audit.md)——结构无错位、命名无违规、>800 行豁免无遗漏、豁免行数已同步。本轮仅做增量复核（行数漂移与新增文件）。
- 其他可交叉引用的近期评审：`../reviews/2026-10-12-full-review.md`（全量 review）、`../reviews/2026-10-12-perf-profiling.md`（性能）、`../reviews/2026-10-16-find-replace.md`（find-replace 多轮）、`../reviews/2026-10-13-extension-system-enhance.md`（扩展系统）——发现项凡与既有评审重复的，引用不重报。
- `.trae/reviews/legacy-issues.md` 为历史遗留汇总，审计发现不得与其重复登记。

## 三、维度 × 方法矩阵（12 维度审计设计）

| # | 维度 | 审计对象与取证方法 | 判定依据（规则条款） | 交叉引用 |
|---|---|---|---|---|
| 1 | 功能正确性 | 内核热路径（`editor_core/buffer.py`、`editor_term/emulator.py`、`keymaps/vim.py`、`flows/*`）边界抽查：空输入 / `None` / 零 / 超大值 / 可变默认参数；发现须配复现步骤 | pr-review SKILL §3.1 | 2026-10-12-full-review |
| 2 | 安全性 | §2.2 疑点逐一确证：`shell=True` 输入源（shell.py:74 / wiki.py:629）、`exec` namespace（yaterc.py:170 / theme_files.py:70）、lua runtime 沙箱、`tools/yxp` 解包路径穿越（已有 fix 复核回归） | pr-review SKILL §3.2 | ext-enh-review 系列 |
| 3 | 性能 | O(n²) 循环 / 循环内 I/O / 重复计算 / 字符串拼接——**仅登记疑点**，修复须先 profiler 实测 | pr-review SKILL §3.3；python-coding-style §6.3.1 | 2026-10-12-perf-profiling |
| 4 | 可维护性 | python-coding-style §五清单机械核对：公共符号 docstring、类型注解完整（pyright 已 0）、魔法数、嵌套 >3、重复逻辑、`from __future__` 位置 | python-coding-style §一/§二/§五 | 2026-10-03-python-code-review |
| 5 | 健壮性 | `except` 面全量扫描：裸 except（已 0）、`except Exception` 缺 BLE001 注记、except 块静默（无 log 无反馈）、资源泄漏（无 with 的 open / Popen） | python-coding-style §4.5 | — |
| 6 | 可扩展性 | 扩展门面 14 名冻结（守卫 #31）、注册表 / 回调 / `*Flows` 接入清单（§三.8 六步）、双语插件手册引用的导入路径与实现逐名核对 | architecture-boundaries §三.8、§四 | extension-system-enhance |
| 7 | 项目结构合理性 | 增量复核：包结构 / `__init__` 惰性（§三.5 三层表述）/ 近空模块 / 新增文件错位 | architecture-boundaries §三.5、§三.7 | **IKMCZW（2026-10-16）** |
| 8 | 模块职责单一性 | 增量复核：豁免名单行数漂移 + 单一职责论证复核 + 逼近阈值观察项（`services/yxp.py` 705、`editor_view/panes.py` 694） | architecture-boundaries §三.7 | **IKMCZW（2026-10-16）** |
| 9 | 架构边界规则 | R1–R14 信号 grep（R1/R2/R3/R4/R5/R6/R10/R11/R12/R14）+ 架构测试 31 用例全绿（已亲测） | architecture-boundaries §一/§六 | 2026-10-07-repo-architecture-audit |
| 10 | 门禁规则 | 四道门禁终态实测：pyright（亲测 0/0/0）+ pytest 全量 + 架构测试（亲测 31）+ `--cov-fail-under=75`（分支记录 91.92%） | pr-review SKILL §3.6；misc-rules §三 | — |
| 11 | 代码文档规范 | `.trae/` 新增文档相对路径（§五）、文档命名（§一/§二）、双语手册同步（§三，已亲测 4 对齐）、代码注释英文（misc-rules §四）、`#:` 常量注释（python-coding-style §2.5） | doc-conventions；misc-rules §四 | 2026-10-05-doc-review-sweep |
| 12 | 规则纪律性 | git-commit-message（已亲测合规）、misc-rules §一/§二（PowerShell here-string / 验证用 Python 脚本）、§三门禁豁免判定、SIZE_EXEMPT_FILES 与 §三.7 两处同步（已亲测一致）、`# type: ignore` 逐处批准理由完备性 | misc-rules；git-commit-message；python-coding-style §4.2 | — |

> 发现分级沿用 pr-review SKILL：`[BLOCKER]`（安全 / 架构违规 / 红门禁）/ `[MAJOR]`（边界 bug / 显著性能 / 吞异常）/ `[MINOR]`（风格可读性，登记不阻塞）。确证的真问题（BLOCKER/MAJOR）修复；MINOR 登记待办。

## 四、备选方案与否决理由

- **方案 A（采纳）**：取证为主的三波执行——wave-1 并行分域取证（只读探针），wave-2 主代理汇总落盘评审记录 + 真问题分类，wave-3 确证修复 + 门禁 + pr-review 迭代。理由：issue 的交付物是"多维度审核"，审核以取证为主；修复范围未知，先落盘事实再按 doc-conventions §二.2 立项，避免无依据乱改。
- **方案 B（否决）**：审核与修复一体推进（边审边修）。否决理由：无人值守时段无人工裁决，"疑似问题"未经确证就改产品源码风险高；违反本任务"仅限确证真问题修复、禁止顺手重构"的硬约束；评审记录是只读事实文档，混入修复动作会破坏 doc-conventions §二.1 的形态约定。
- **方案 C（否决）**：把 12 个维度全部铺开重审。否决理由：维度 7/8 于 IKMCZW（同日）刚审完且实测零漂移，重复铺开是纯浪费；按本任务约束改为交叉引用 + 增量复核。
- **方案 D（否决）**：拆子计划目录 `.trae/documents/full-repo-audit-plans/`。否决理由：本任务指派落盘路径为单一计划文档（独占文件清单硬约束）；修复阶段产物按 doc-conventions §二.2 以 `<task>-review-fixes-plan.md` 形态落在 documents 根（有存量合规先例 `repo-audit-fixes-plan.md`），不建子计划目录。

## 五、分步实施计划

### 5.0 执行流程图

```mermaid
flowchart LR
    A[计划落盘+提交] --> B
    subgraph B[wave-1 并行取证 2~3 一批]
        B1[Step1 正确性+健壮性]
        B2[Step2 安全+性能]
        B3[Step3 可维护+扩展+文档规范]
    end
    B --> C[Step4 结构/职责/边界增量复核 主代理]
    C --> D[Step5 汇总落盘评审记录+真问题分类]
    D -->|需修复| E[Step6 修复执行 单独提交]
    D -->|零真问题| G
    E --> G[Step7 全量门禁 主代理亲跑]
    G --> H[Step8 pr-review 迭代]
    H -->|BLOCKER/MAJOR| E
    H -->|无| I[Step9 回填+分步提交+统一推送]
```

### 5.1 子代理任务书要点（wave-1 通用，依据 subagent-workflow §二）

- **唯一规范来源**：本计划文档 + `../rules/` 全部 8 文件，声明"以它为准，不要凭常识猜"；
- **权限模式**：显式 `bypassPermissions`（subagent-workflow §五.1）；**批大小 2~3，硬上限 6**；spawn 后同回合探活，判死即主代理兜底执行；
- **报告格式**：改动清单 + 实际执行的命令与结果（含退出码）+ 未解决项与原因；
- **只认落盘结果**：成员声称的发现，主代理须独立复核（重跑 grep / 探针 / 测试）后方可写入评审记录；
- **模型调度**：按 subagent-workflow §六按时段表指定，不逐条复写。

### 5.2 步骤与波次表

| 波次 | 步骤 | 执行者 | 独占文件清单 |
|---|---|---|---|
| wave-1 | Step 1 ∥ Step 2 ∥ Step 3 | 子代理 ×3（只读取证，可 2+1 分批） | 各自仅产出报告（无写盘），发现以"文件:行号 → 证据 → 复现命令"清单回报，主代理复核后落盘 |
| wave-2 | Step 4 → Step 5 | 主代理 | `../reviews/2026-10-16-full-repo-audit.md`（新建） |
| wave-3 | Step 6 → Step 7 → Step 8 | 主代理（修复面大时派 plan-executor 子代理，独占文件清单按修复项划分） | 按修复项临时划定；禁止跨项 |
| wave-4 | Step 9 | 主代理 | 本计划文档回填段 |

波次纪律：同一波内文件互不重叠可并行；上一波全部验收通过（退出码 0）才进下一波；波次一经批准不临时重排，确需调整须回填本节并附实测依据。

---

### Step 0 — 计划落盘（已完成，本提交）

- 输入：§二取证 + §三矩阵设计；
- 改动文件：`.trae/documents/full-repo-audit-plan.md`（新建，本文件）；
- 输出：可评审、可执行的多维审核计划；
- 验收：无人值守规则下本行即批准登记；提交信息 `docs(plan): add full-repo-audit plan for Gitee IKMD0E`。

### Step 1 —（wave-1）功能正确性 + 健壮性取证（维度 1、5）

- 输入：§三矩阵行 1、5；`../reviews/2026-10-12-full-review.md` 防重复清单；
- 探针命令（只读）：
  - `.venv\Scripts\python.exe -m pytest tests/ -q --tb=no`（全量回归基线，输出重定向文件防探针超时）
  - grep：`except Exception`（核对 BLE001 注记）、`except\s*(Exception)?\s*:\s*pass`（静默吞）、`open\(` 无 `with` 邻接、可变默认参数 `def\s+\w+\([^)]*=\s*(\[\]|\{\})`
- 输出：发现清单（文件:行号 → 证据 → 复现命令/测试 → 分级）；
- 验收：每个 BLOCKER/MAJOR 发现须附可复现证据（失败测试或最小复现脚本运行输出）；复核命令退出码如实记录。

### Step 2 —（wave-1）安全性 + 性能取证（维度 2、3）

- 输入：§二.2 疑点清单（shell=True ×2、exec ×2、lua runtime、yxp 解包）；
- 探针命令（只读）：
  - 精读 `yate/services/shell.py:43-90`、`tools/pack/wiki.py:600-650`：核对命令字符串构造中用户可控片段的来源与转义；
  - 精读 `yate/yaterc.py:150-180`、`yate/editor_view/theme_files.py:30-80`：namespace 构造（是否限制 `__builtins__`、路径来源是否用户配置目录）；
  - grep：`requests|urlopen|http`（tools 外联面）、`shutil.rmtree|unlink|rename`（危险文件操作输入源）；
  - 性能：仅登记疑点（O(n²) / 循环内 I/O / 重复计算），不跑优化；
- 输出：安全面确证结论（每处疑点：可达 / 不可达 + 依据）+ 性能疑点登记；
- 验收：安全结论必须以"输入源 → 传播路径 → 汇点"链路描述，不得凭名字猜。

### Step 3 —（wave-1）可维护性 + 可扩展性 + 文档规范取证（维度 4、6、11）

- 输入：§三矩阵行 4、6、11；
- 探针命令（只读）：
  - grep：公共函数缺 docstring（`^def [a-z]` 后 3 行无 `"""`，抽查法）、`Optional\[|Union\[|Dict\[|List\[`（遗留写法回潮）、`from .`（相对导入，守卫外 tests/tools 面）、中文注释（misc-rules §四：`# [\u4e00-\u9fa5]` 扫 `yate/ tools/`）；
  - 核对 `yate/docs/extensions.en.md` / `extensions.zh.md` 引用的 API 名与 `services/extensions/__init__.py` 14 名逐一对齐（双语 diff）；
- 输出：发现清单（同 Step 1 格式）；
- 验收：每条发现标注对应规则条款编号；MINOR 级仅登记不立项。

### Step 4 —（wave-2）结构 / 职责 / 架构边界增量复核（维度 7、8、9，主代理）

- 输入：`../reviews/2026-10-16-repo-structure-audit.md` 全文 + §二.2 实测；
- 探针命令（只读）：
  - `git diff master...HEAD --stat`（本分支零代码改动，防混入）；
  - 行数漂移复测（`splitlines()` 口径，对豁免名单 5 文件）；
  - `pytest tests/test_architecture.py -q`（已亲测 31 passed）；
- 输出：增量复核结论（预期：零漂移、零新增违规；若有漂移按文档漂移可修复项处理）；
- 验收：不重复 IKMCZW 已审结论，仅引用 + 增量。

### Step 5 —（wave-2）汇总落盘评审记录 + 真问题分类（主代理）

- 输入：Step 1–4 全部复核后的发现；
- 改动文件：新建 `../reviews/2026-10-16-full-repo-audit.md`（只读事实文档：基线门禁表 + 12 维度逐维发现与核对结论 + 与既有评审的交叉引用），并在本计划文档间互相链接；若 reviews 索引 `../reviews/README.md` 需登记条目则一并补；
- 输出：确证真问题清单（BLOCKER/MAJOR，各附修复建议）→ 修复面小则进入 Step 6，修复面大（预计 ≥3 文件或多方案）则按 doc-conventions §二.2 立项 `full-repo-audit-review-fixes-plan.md`（评审记录 → 修复方案互链）；
- 验收：文档命名合规（日期前缀 + 连字符分词）、仓库内引用全部相对路径（doc-conventions §五）、纯文档变更按 misc-rules §三豁免测试（混合变更则跑全量门禁）。

### Step 6 —（wave-3）确证真问题修复

- 输入：Step 5 的真问题清单（仅限审核确证的 BLOCKER/MAJOR + 文档漂移，禁止顺手重构）；
- 改动文件：按修复项划定独占清单（执行期在 Step 5 产出中明确到 文件:行号；预期形态参考：`# pyright: ignore` 注记理由补全属注释级、`shell=True` 疑点若确证则属 `services/shell.py` 局部改动）；涉及架构边界时同步 `tests/test_architecture.py` 守卫用例（新增守卫须附负向演练：回填违规确认拦截后还原）；
- 输出：每个修复项单独 commit（`git-commit-message.md` 规范，如 `fix(security): ...` / `docs(rules): ...`），只提交不推送；
- 验收命令：每个修复项跑其影响面测试 + `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q`；
- 回滚：单项 `git revert <commit>`。

### Step 7 —（wave-3）全量门禁（主代理亲自跑，退出码全 0 才过）

- 验收命令（worktree 沙箱解释器）：
  - `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/`
  - `.venv\Scripts\python.exe -m pytest tests/ -q`（长跑：输出重定向，防探针超时误判）
  - `.venv\Scripts\python.exe -m pytest tests/ -q --cov --cov-fail-under=75`
  - `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q`
- 判定：任一红门禁 = BLOCKER，回 Step 6；timing 类偶发失败按 subagent-workflow §三.3 重跑确认后再下结论，不许直接改断言。

### Step 8 —（wave-3）pr-review 技能审核迭代

- 输入：`git diff master...HEAD` 全部改动；
- 方法：按 `../skills/pr-review/SKILL.md` 的 `review` 模式（六维 + 四道门禁，真实退出码）；
- 判定：存在 BLOCKER/MAJOR → 回 Step 6 修复迭代；仅 MINOR → 登记待办；迭代上不封顶，直至 `Overall: APPROVE`。

### Step 9 —（wave-4）回填与提交、统一推送

- 输入：全部门禁实测数字、偏离记录、pr-review 结论；
- 改动文件：本计划文档 §六回填（真实前后数字、步骤-提交对照、偏离记录与实测依据）；
- 提交纪律：每步产物单独 commit（`docs(reviews)` / `fix(...)` / `docs(plan)` 分笔，PowerShell 多行提交信息用 here-string，misc-rules §一）；
- **推送**：全部步骤完成且 pr-review 无 BLOCKER/MAJOR 后，按本任务指令**统一执行一次 `git push`**（本条为本任务对 task-orchestration §二"闭环内禁 push"的显式授权偏离，登记入 §六偏离记录）。

## 六、风险清单与回滚路径

| 风险 | 缓解 / 回滚 |
|---|---|
| 安全疑点误报导致误改产品代码 | Step 2 强制"输入源 → 传播 → 汇点"链路证据；不可达即登记为"核对通过"，不改代码 |
| 修复引入回归 | 修复仅限确证真问题 + 每项单独 commit + 影响面测试 + 全量门禁兜底；回滚 `git revert` 单笔 |
| 全量 pytest 长跑触发探针超时 | Step 7 明确输出重定向长跑；已亲测 14% 内零失败点，超时非质量信号 |
| 子代理并发 pytest 互相干扰（timing 偶发） | subagent-workflow §三.3：重跑确认后再下结论；取证类子代理不并发跑同一测试文件 |
| pr-review 迭代不收敛 | 迭代上不封顶但每轮发现须降级收敛；MINOR 登记 `legacy-issues.md` 或待办，不阻塞收尾 |
| 维度 7/8 与 IKMCZW 结论重复冲突 | 交叉引用为唯一事实源；仅当增量复核发现新漂移才登记，并注明"增量于 IKMCZW" |
| 文档漂移修复范围失控（顺手大扫除） | 文档修复仅限"规则文档与实现不符"的实测漂移项；存量绝对路径（32 处，§2.2）按 §五"随下次修改迁移"豁免，不做专项清扫 |
| 推送偏离闭环纪律 | 仅在 Step 9 末统一一次，且以本任务指令为授权依据，登记偏离记录 |

## 七、执行记录回填（2026-10-16 终态）

### 门禁实测（主代理亲跑，worktree 沙箱）

| 门禁 | 基线（§2.1） | 终态 |
|---|---|---|
| `pyright yate/ tests/ tools/` | 0/0/0，exit 0 | **0/0/0，exit 0** |
| `pytest tests/ -q` | 全绿（分支记录） | **全绿，exit 0** |
| `pytest tests/test_architecture.py -q` | 31 passed | **31 passed，exit 0** |
| `pytest tests/ -q --cov --cov-fail-under=75` | 91.92%（分支记录） | **91.98% ≥ 75%，exit 0** |

### 步骤-提交对照

| 步骤 | 提交 | 内容 |
|---|---|---|
| Step 0 | `852b08b` | 本计划落盘 |
| Step 5 | `fa88bd6` | 评审记录落盘（12 维度：3 MAJOR / 11 MINOR 登记 / 1 误报驳回） |
| Step 5 | `dff0644` | 修复方案立项（full-repo-audit-review-fixes-plan.md） |
| Step 6 Fix-A+B | `5601a7b` | emulator EL 钳制 + S/T count 钳制 + 4 个守卫用例（81 passed） |
| Step 6 Fix-C | `7bc9c4c` | 项目 rc 与 cwd/themes 信任门控 + 测试 + 双语文档（**已于 2026-10-17 整体撤销**，见偏离记录 6） |
| Step 6 Fix-D | `243afef` | 注释/文档级合规 4 处（F-5/F-6/F-8/F-9） |
| Step 7 | — | 全量门禁四道全绿（见上表） |
| Step 8 | — | pr-review（review 模式，六维 + 四道门禁真实退出码）：**Overall: APPROVE**，无 BLOCKER/MAJOR；MINOR 2 条仅登记（`is_trusted` 启动期两次读 store 开销可忽略；新增双语小节行数不对称、内容已对齐） |
| Step 9 | 本提交 + 统一推送 | 回填与推送（推送为总任务指令显式授权，见偏离记录 4） |

### 偏离记录（均附实测依据）

1. **Fix-A 与 Fix-B 合并为一笔提交**（计划原定每 Fix 一笔）：两者改动落在同一对文件
   （emulator.py + test_terminal_emulator.py）的相邻区域，无人值守下按 hunk 拆分提交
   风险大于收益；提交体中分别点名 F-1/F-2，回滚粒度损失可接受。
2. **Fix-C 门控函数命名 `gate_project_rc`（公开，无下划线）**：任务书建议名
   `_gate_project_rc` 被 pyright strict 的 reportPrivateUsage（tests 导入私有名）判 1 error
   （§4.2 禁 ignore 豁免）；更名后 0 诊断，语义与签名不变（执行器实测）。
3. **wave-1 取证子代理无 shell 执行能力**：三条探针命令（全量 pytest / pyright / 复现脚本）
   由主代理独立补测（A-1 IndexError 复现、A-2 挂死复现、基线门禁全绿），
   符合"只认落盘结果、主代理复核"纪律。
4. **闭环内推送**：task-orchestration §二 规定闭环内只提交不推送；本任务用户指令第 8 条
   显式要求"所有任务完成后，推送"，按指令在 Step 9 末统一执行一次 `git push`。
5. **子代理报告误报驳回 1 条**：F-8 中"architecture-boundaries.md:10 引用数量漂移"经主代理
   复核为误报（该行引用 app-layering-refactoring-plans/ 实存 plan_a–g 且合规），
   已记入评审记录 §三。
6. **Fix-C 撤销（2026-10-17 用户裁决）**：拥有者裁定 trust 职责域仅限 extensions，
   项目 yaterc 属 vimrc 式 deliberate design，不做工作区信任门控（cwd/themes 同）；
   `7bc9c4c` 已 revert（`2cb30cc`，含测试与双语文档），F-4 在评审记录 §三改登
   "用户裁决不修"。撤销后复测：pyright 0/0/0、全量 pytest exit 0、架构 31 passed。
   另：Fix-C 落地期间曾按用户指示尝试将门控函数迁往 yaterc.py / 调整调用宿主，
   均未提交即作废；同名函数 `gate_project_rc` / `gate_cwd_themes` 命名与调用宿主
   讨论随撤销一并失效，trust.py 恢复原状（extensions-only）。

### 登记待办（MINOR，不阻塞收尾）

F-3（vim count 无上界）、F-7（4 处静默吞异常）、P-1~P-5（性能疑点，修复须先 profiler）、
F-10（verify_matrix.ps1 中文注释 / 引述性中文规则空白）、F-11（`*-feature` 存量命名）、
F-12（ext-api-parity-plans 下划线分词存量）、lua runtime lupa 收口观察项、
pb6 探针 Popen 兜底——明细见
[`../reviews/2026-10-16-full-repo-audit.md`](../reviews/2026-10-16-full-repo-audit.md) §二/§三。
