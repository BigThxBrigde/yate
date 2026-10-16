# repo-structure-audit-plan

- Issue：[Gitee IKMCZW](https://gitee.com/jermaine/yate/issues/IKMCZW)（ENHANCE - 大模块、项目结构以及层次的审核，文档更新）
- 分支：`enh/repo-structure-audit`（worktree `../yate-repo-structure-audit`，沙箱已自证指向本 worktree）
- 日期：2026-10-16
- 状态：无人值守执行（22:00–06:00 规则，方案批准按通过处理，本行即为批准登记）

## 一、目标与非目标

**目标**（对应 issue 四项任务）：

1. 全仓扫描大模块（≥600 行清单、>800 阈值核对豁免名单），给出拆分/豁免结论；
2. 模块与包结构核对（命名守卫、相对导入、错位模块、`__init__` 惰性约定）；
3. 分层边界核对（R1–R14 违规信号 grep + 架构测试全绿）；
4. 依据实测更新与实现有出入的文档。

**非目标**：

- 不做 editor.py 等大文件的拆分（见 §四登记待办；拆分属 big-module-split 另行立项）；
- 不改任何产品行为代码（`yate/`、`tools/` 生产逻辑零改动）；
- 不新增架构规则，只同步既有规则文档与实现的偏差。

## 二、调研取证（主代理亲测，含子代理交叉取证）

基线门禁（worktree 沙箱实测）：

| 门禁 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations，exit 0 |
| `pytest tests/ -q` | 全绿，exit 0 |

实测取证清单（守卫口径 `splitlines()`）：

| 取证点 | 实测 | 文档登记 | 结论 |
|---|---|---|---|
| `yate/editor.py` 行数 | 1024 | 983（§三.7） | **漂移 +41，需同步** |
| `yate/keymaps/vim.py` 行数 | 1184 | 1178 | **漂移 +6，需同步** |
| `yate/editor_core/buffer.py` 行数 | 1069 | 1062 | **漂移 +7，需同步** |
| `tools/pack/wiki.py` 行数 | 1495 | 1487 | **漂移 +8，需同步** |
| `yate/editor_syntax/langdefs.py` 行数 | 813 | 813 | 一致 |
| `yate/logs.py` 行数（负面清单） | 690 | 686 | **漂移 +4，需同步** |
| `yate/flows/` 实际模块数 | 10 个（含 `mouse_flows.py`、`extension_flows.py`） | R11 枚举只列 8 个 | **枚举缺 2，需补** |
| `UI_FROZEN_FILES` 键数（../../tests/test_architecture.py:148） | 9 键 | 守卫 docstring 只提 2 个 flows 文件；块注释 L147 引用 "(R4)" 应为 R11 | **注释失准，需修** |
| 架构测试用例数 | 31 | 31（§六） | 一致 |
| 扩展门面 `__all__` | 14 名 | 14 名 | 一致 |
| README 语言数 | 30（`_LANGUAGES` 按语言对象去重） | 30 | 一致 |
| README tree-sitter 数 | 25（`BUILTIN_PACKS`） | 25 | 一致 |
| README 主题数 | 8（`THEMES`） | 8 | 一致 |
| README 屏保角色数 | 27（`character_names()` 运行时） | 27 | 一致 |
| 违规信号（`import yate.app` 出界 / `TYPE_CHECKING` / `Optional[` / `self.log` / 类级 `ScrollBar.renderer` / `X = Callable[` / 相对导入） | 全部 0（yate/+tools/） | — | 一致 |
| >800 行未登记豁免的文件 | 0 个 | — | 一致 |

结构结论：无错位模块、无命名违规、包结构合规；`yate/services/yxp.py`（705 行）逼近阈值，仅登记观察。

## 三、备选方案与否决理由

- **方案 A（采纳）**：纯文档同步——修规则文档漂移 + 守卫注释失准 + 评审记录落盘 + 登记拆分待办。理由：issue 的交付物是"审核 + 更新有出入的文档"；实测代码侧全部合规，唯一失守的是文档与注释。
- **方案 B（否决）**：顺势拆分 `editor.py`（1024 行、多职责块）。否决理由：拆分会触碰 big-module-split 已钉死的构造工厂与 patch 语义，风险高、零行为收益，且规则允许多职责拆分"另行立项"；无人值守时段不宜启动高危重构。
- **方案 C（否决）**：把 `flows/extension_flows.py` 预登进 `UI_FROZEN_FILES`。否决理由：该白名单语义是"允许 import `editor_view` 的冻结耦合文件"，`extension_flows.py` 实测不 import `editor_view`（extension_flows.py:20-27），预登记反而稀释白名单语义；扫描面本身已覆盖 flows/ 全目录。

## 四、分步实施计划

```mermaid
flowchart LR
    A[计划落盘] --> B[Step1 规则文档同步]
    B --> C[Step2 守卫注释修正]
    C --> D[Step3 评审记录落盘]
    D --> E[Step4 全量门禁]
    E --> F[Step5 pr-review 迭代]
    F -->|有 BLOCKER/MAJOR| B
    F -->|无| G[回填+提交]
```

### Step 1 — 规则文档同步（输入：§二实测表）

- 改动文件：`../rules/architecture-boundaries.md`
- 内容：§三.7 五处行数同步（editor.py / vim.py / buffer.py / wiki.py / logs.py 负面清单），editor.py 条目追加 2026-10-16 复核注记；§一 R11 flows 枚举补 `mouse_flows.py`、`extension_flows.py`（与 §一 L3 依赖图对齐）
- 输出：文档与实测一致
- 验收命令：`python -m pytest tests/ -q`（规则文档不影响测试，防手滑）+ 人工核对引用行号

### Step 2 — 守卫注释修正（输入：§二取证）

- 改动文件：`../../tests/test_architecture.py`（仅注释/docstring，零行为）
- 内容：`UI_FROZEN_FILES` 块注释 L147 "(R4)" 改为 R11；`test_collaborators_keep_widget_coupling_frozen` docstring 概括 9 键扫描面
- 验收命令：`python -m pytest tests/test_architecture.py -q`

### Step 3 — 评审记录落盘（输入：§二全部取证）

- 新建文件：`../reviews/2026-10-16-repo-structure-audit.md`（命名合规：日期前缀 + 连字符分词）
- 内容：四项审核的发现与核对结论（只读事实文档），与计划文档互相链接；登记拆分待办：editor.py 为下一个 big-module-split 候选（1024 行、多职责块、豁免登记持续过期）、`services/yxp.py` 705 行逼近阈值
- 验收命令：纯文档，按 `../rules/misc-rules.md` §三核对（与 Step2 混合则跑全量门禁）

### Step 4 — 全量门禁（混合变更，不豁免）

- 验收命令（主代理亲自跑，退出码全 0 才过）：
  - `python -m pyright yate/ tests/ tools/`
  - `python -m pytest tests/ -q`
  - `python -m pytest tests/ -q --cov --cov-fail-under=75`
  - `python -m pytest tests/test_architecture.py -q`

### Step 5 — pr-review 技能审核迭代

- 对分支全部改动（`git diff master...HEAD`）按 `pr-review` 技能跑 review 模式；存在 BLOCKER/MAJOR 回 Step 1 修复迭代，直至无 issue 产出

### Step 6 — 回填与提交

- 本文档回填真实结果与偏离记录；按 `../rules/git-commit-message.md` 分步提交（docs(plan) → docs(rules) → docs(architecture) → docs(reviews)），只提交不推送

## 五、风险清单与回滚路径

| 风险 | 缓解 / 回滚 |
|---|---|
| 规则文档行数再次过期 | 本次一并把"实测日期"写进条目，复核有据可查 |
| 注释改动误触架构测试文本断言 | Step 2 只动 docstring/注释，不动断言逻辑；架构测试单独跑 |
| 纯文档提交遗漏分步 | 每步完成即单独 commit，git log 可逐笔回溯 |
| 回滚 | 全部改动为文档与注释，`git revert` 对应单笔提交即可，无数据/行为风险 |

## 六、执行记录回填（2026-10-16）

### 门禁实测（终态，主代理亲跑）

| 门禁 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations，exit 0 |
| `pytest tests/ -q --cov --cov-fail-under=75` | 全绿，exit 0；覆盖率 **91.92%**（≥75 达标） |
| `pytest tests/test_architecture.py -q` | 31 passed，exit 0 |

### 步骤执行与提交对照

| 步骤 | 提交 | 结果 |
|---|---|---|
| 计划落盘 | `06d224d` docs(plan) | 完成 |
| Step 1 规则同步 | `2f28377` docs(rules) | 五处行数 + R11 枚举修正 |
| Step 2 守卫注释 | `e7cb99c` docs(architecture) | R4→R11、docstring 9 键概括 |
| Step 3 评审记录 | `1da8a2b` docs(reviews) | `../reviews/2026-10-16-repo-structure-audit.md` |
| Step 4 门禁 | （首轮） | 通过（一次 timing 偶发重跑确认，见偏离 2） |
| Step 5 pr-review | `ef04d96` docs(plan) | 两轮迭代，第二轮零发现 |
| Step 6 回填 | 本提交 | 本节 |

### 偏离记录（实测依据）

1. **外来合并提交 `bd91dc3`**：`enh/repo-structure-audit` 分支上出现一笔非本会话创建的
   `Merge branch 'master'`（作者 i77，2026-10-16 22:41），合入 master 的
   `d34ee32`（`.codebuddy/rules/yate-rules.md` +21 行）。与本任务无关、不动本分支产物，
   予以保留；`git diff master...HEAD` 经此合并后仍只含本任务 4 个文件。
2. **`test_run_shell_timeout_kills_the_grandchild_process` 首轮全量失败**：单跑通过、
   全量重跑全绿——timing 类偶发（本分支零行为代码改动，不可能由本任务引入），按
   `../rules/subagent-workflow.md` §三.3 纪律重跑确认后下结论。
3. **pr-review 第一轮发现 1 处 [MINOR]**：计划/评审文档内仓库文件引用用了仓库根路径，
   违反 `../rules/doc-conventions.md` §五；已改为文档自身相对路径（提交 `ef04d96`）。
   第二轮复审（功能/安全/性能/可维护性/架构/门禁六维 + 全文引用扫描）零新发现，
   裁定 `APPROVE`，迭代闭环。

### 待办登记（后续 issue / 另行立项）

- `yate/editor.py`（1024 行、多职责块）为下一个 big-module-split 候选；
- 观察项：`yate/services/yxp.py`（705 行）、`yate/editor_view/panes.py`（694 行）逼近 800 阈值。
