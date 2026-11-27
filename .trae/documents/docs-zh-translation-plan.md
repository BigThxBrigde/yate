# 英文计划/评审文档中文化方案

## 一、目标与非目标

**目标**：把 `.trae/documents/` 与 `.trae/reviews/` 下以英文叙述为主的 Markdown 文档就地翻译为简体中文，保留全部技术事实与可机读结构，使这两个目录的文档语言与仓库其余 647 篇中文文档一致。

**非目标**：

- 不翻译 `yate/docs/*.en.md`（面向用户的英文手册，须保持英文）、源码注释/docstring（`misc-rules.md` §四强制英文）、代码内的英文标识符与字符串。
- 不改变任何 `.py` / `.toml` / 配置 / 脚本 / 数据文件，不改变可执行行为。
- 不修改文档文件名（`.trae` 的命名由 `doc-conventions.md` §一/§二固定）。
- 不补写、删减或重排技术内容；不修正原文中记录的历史结论（即使已过时）。

## 二、调研事实（只读探针，路径相对 worktree 根）

1. 两目录共 726 个 `.md`：`.trae/documents/` 597、`.trae/reviews/` 129。
2. 中文字符计数 `< 100` 的英文/英文主导文档共 **79 篇**（documents 70、reviews 9），合计 **635,991 字节**，单篇最大 27,519 字节；其中 29 篇完全无中文字符，43 篇含 1–29 个中文字符（多为原文引用的 issue 标题等），7 篇含 30–97 个中文字符。
3. 其余 647 篇中文字符数 ≥ 100，已是中文文档，不纳入本次范围。
4. 现有 `.trae/agents/translator.md` 的默认方向为「中文→英文」；本任务以任务书显式声明「英文→中文」覆盖该默认方向，其余纪律（独占文件、结构保真、非空校验、只报可验证事实）全部沿用。
5. 当前分支 `feature/docs-zh-translation`，parent `master@ac47f7d1`（与 `origin/master` 一致）；主仓未改动。

## 三、方案选型

| 方案 | 结论 | 理由 |
|---|---|---|
| **就地翻译**（选定） | 采用 | `.trae` 的计划/评审文件名由 `doc-conventions.md` 固定，无 `.zh.md` 双语惯例；原文可由 git 历史完整恢复；相对链接目标无需改动。 |
| 新增 `*.zh.md` 副本 | 否决 | 与 §一/§二命名规范冲突，凭空增加 79 个文件；两个目录没有双语索引机制，副本会与原文长期漂移。 |
| 另建译文化镜像目录 | 否决 | 目录内大量 `../xxx.md` 相对链接会失效，且产生并行事实源。 |
| 脚本式机器直译 | 否决 | 无质量保障，且会破坏代码块、表格、行内代码与链接；仅允许脚本做**校验**，不做翻译。 |

## 四、翻译保真契约（所有执行者必须遵守）

1. Markdown 结构逐篇不变：标题层级、列表符号与缩进、表格列数/分隔行、引用块、代码块语言标记、水平分隔线、空行分段。
2. **不译**：代码块内容、行内代码（反引号内）、命令、路径、文件名、模块名/函数/类/常量/键名/快捷键字面量、提交哈希、issue 编号、URL 与 Markdown 链接目标、日期、数字、代码片段中的英文注释。
3. **译**：叙述性英文（标题、正文、表格表头与说明单元格、列表说明、引用中的说明文字、Mermaid 节点显示文字）。Mermaid 图边标签中的规则名/标识符保持原样，其余说明文字可译。
4. 原文中已有的中文（issue 标题、引述、产品文案）原样保留，不回译、不改写。
5. 术语统一：plan→计划、review→评审、wave→波次、guard→守卫、acceptance command→验收命令、worktree→worktree、sub-plan→子计划、finding→发现项、blocker→阻塞项、major/minor→严重/次要（保留原文级别词可写 `MAJOR`/`MINOR`）、facade→门面、smoke→冒烟；拿不准时保留英文术语并在首次出现处加中文解释。
6. UTF-8 无 BOM 写盘；不改动文件权限；不触碰范围外文件。

## 五、执行分批与独占文件清单

按主题分组，**每个执行者独占自己的文件**；每波最多 3 个执行者并行，波间串行。全部使用 `.trae/agents/translator.md` 定义（任务书覆盖翻译方向），团队模式 `acceptEdits`。

| 波 | 执行者 | 独占文件（相对 worktree 根） |
|---|---|---|
| 1 | T01 | `.trae/documents/big-module-split-2-plans/` 下 5 篇（editor-plan-a/b、wiki-plan-a、yxp-plan-a、overview） |
| 1 | T02 | `.trae/documents/enew-args-lsp-attach-plan.md`、`enew-args-lsp-attach-naming-plan.md` |
| 1 | T03 | `.trae/documents/enew-args-lsp-attach-plans/` 下 5 篇（guard-plan-a、review-plan-e、saveas-plan-c、state-plan-b、overview） |
| 2 | T04 | `.trae/documents/full-repo-sweep-plan.md`、`full-repo-sweep-issue-brief.md`、`full-repo-sweep-review-fixes-plan.md` |
| 2 | T05 | `.trae/documents/full-repo-sweep-plans/` 下 6 篇（lsp-diagnostics-plan-a、robustness-plan-b、yaterc-plan-c、diff3-plan-d、tests-readme-plan-e、review-index-plan-f） |
| 2 | T06 | `.trae/documents/full-repo-sweep-plans/` 下 6 篇（test-guard-plan-g、doc-index-plan-h、doc-status-plan-i、bridges-plan-j、diagnostics-plan-k、workspace-plan-l、`overview.md`） |
| 3 | T07 | `.trae/documents/iktbxc-plan.md`、`iktbxc-issue-notes.md`、`iktbxc-reference-inventory.md`、`iktbxc-plans/` 下 5 篇（cmdline-relocation-plan-c、key-codec-plan-a、view-plan-b、overview 等，以实际清单为准） |
| 3 | T08 | `.trae/documents/lsp-hover-docs-plan.md`、`lsp-hover-docs-plans/overview.md`、`lsp-hover-docs-plans/` 下 3 篇（capabilities-plan-b、keymap-plan-c、parsing-plan-a） |
| 3 | T09 | `.trae/documents/lsp-hover-docs-plans/` 下剩余 6 篇（manager-plan-d、popup-plan-e、docs-plan-f、flows-plan-g、integration-plan-h、smoke-plan-i） |
| 4 | T10 | `.trae/documents/lsp-navigation-plan.md`、`lsp-navigation-issue-brief.md`、`lsp-navigation-review-fixes-plan.md`、`lsp-navigation-plans/` 下 6 篇（a–e + overview） |
| 4 | T11 | `.trae/documents/completion-staleness-check-plan.md`、`naming-hygiene-pr-review-plan.md`、`ec-structure-reorg-plans/wave-2-executor-notes.md` |
| 4 | T12 | `.trae/documents/soft-wrap-plans/` 下 7 篇（core-plan-a、view-plan-b、config-plan-c、keys-plan-d、robustness-plan-e、docs-plan-f、overview） |
| 5 | T13 | `.trae/documents/toggle-comment-plan.md`、`toggle-comment-plans/` 下 5 篇（overview、plan-a/b/c/d） |
| 5 | T14 | `.trae/reviews/` 下 9 篇：2026-11-06-*（2 篇）、2026-11-08-*（2 篇）、2026-11-16-*、2026-11-20-*、2026-11-21-*、2026-11-22-*、2026-11-23-* |

每波执行者名单、文件数、字节数在任务书中逐项列全，任务书是执行者的唯一规范来源；上表与第七节清单冲突时以任务书列出的实际路径为准（任务书从第七节清单生成）。

```mermaid
flowchart LR
    S["79 篇英文文档清单"] --> W1["波 1：3 名执行者"]
    W1 --> W2["波 2：3 名执行者"]
    W2 --> W3["波 3：3 名执行者"]
    W3 --> W4["波 4：3 名执行者"]
    W4 --> W5["波 5：2 名执行者"]
    W5 --> V["主代理校验：结构/术语/覆盖率"]
    V --> G["门禁豁免确认 + 提交"]
```

## 六、验收与风险

**验收命令**（在 worktree 根执行，解释器用 `.venv\Scripts\python.exe` 或系统 `python`）：

1. 覆盖率：`python -c "...扫描两目录，中文字符<100 的 .md 数量必须为 0..."`（方案落盘文档自身是中文，不计入）。
2. 结构保真：`python -c "...对每篇 git show HEAD:<path> 与工作副本比较：标题行数、代码围栏数、围栏内文本逐字一致、行内代码序列一致、链接目标序列一致..."`（逐项 diff；任何不等即失败）。
3. 非空与编码：79 个目标文件均存在、字节数 > 0、UTF-8 可解码且无 BOM。
4. 范围：`git status --short` 只出现第七节列出的 79 个文件（加方案文档本身）；无源码/配置/脚本改动。
5. 因属于**纯文档变更**（`misc-rules.md` §三），豁免 pyright / pytest / 架构 / 覆盖率 / 冒烟门禁；如出现任何非文档改动则豁免失效，按常规流程跑全量门禁。

**风险与回滚**：

- 子代理零产出 / 提前判死 → 按 `subagent-workflow.md` §五：探活、查落盘结果、最多一次变更配置重试，否则主代理亲自翻译该批。
- 翻译破坏代码块或链接 → 第 2 条校验拦截，逐篇修复；无法修复则 `git restore -- <path>` 回退单篇。
- 术语不一致 → 主代理在第二/三步抽查并统一。
- 整体回滚：`git restore -- .trae/documents .trae/reviews`（仅在未提交前），已提交则 revert。

## 七、79 篇目标文件清单（路径 | 原始字节 | 原中文字符数）

```text
.trae/documents/big-module-split-2-plans/big-module-split-2-editor-plan-a.md | 13021 | 0
.trae/documents/big-module-split-2-plans/big-module-split-2-editor-plan-b.md | 13300 | 0
.trae/documents/big-module-split-2-plans/big-module-split-2-wiki-plan-a.md | 15141 | 0
.trae/documents/big-module-split-2-plans/big-module-split-2-yxp-plan-a.md | 14598 | 0
.trae/documents/big-module-split-2-plans/overview.md | 8972 | 4
.trae/documents/completion-staleness-check-plan.md | 15616 | 97
.trae/documents/ec-structure-reorg-plans/wave-2-executor-notes.md | 3914 | 0
.trae/documents/enew-args-lsp-attach-naming-plan.md | 27519 | 76
.trae/documents/enew-args-lsp-attach-plan.md | 26090 | 50
.trae/documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-guard-plan-a.md | 6965 | 3
.trae/documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-review-plan-e.md | 13595 | 4
.trae/documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-saveas-plan-c.md | 10598 | 2
.trae/documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-state-plan-b.md | 14120 | 2
.trae/documents/enew-args-lsp-attach-plans/overview.md | 7703 | 2
.trae/documents/full-repo-sweep-issue-brief.md | 10271 | 9
.trae/documents/full-repo-sweep-plan.md | 20091 | 43
.trae/documents/full-repo-sweep-plans/full-repo-sweep-bridges-plan-j.md | 3994 | 14
.trae/documents/full-repo-sweep-plans/full-repo-sweep-diagnostics-plan-k.md | 3838 | 8
.trae/documents/full-repo-sweep-plans/full-repo-sweep-diff3-plan-d.md | 3526 | 13
.trae/documents/full-repo-sweep-plans/full-repo-sweep-doc-index-plan-h.md | 2456 | 28
.trae/documents/full-repo-sweep-plans/full-repo-sweep-doc-status-plan-i.md | 2391 | 35
.trae/documents/full-repo-sweep-plans/full-repo-sweep-lsp-diagnostics-plan-a.md | 3426 | 12
.trae/documents/full-repo-sweep-plans/full-repo-sweep-review-index-plan-f.md | 1632 | 15
.trae/documents/full-repo-sweep-plans/full-repo-sweep-robustness-plan-b.md | 2758 | 16
.trae/documents/full-repo-sweep-plans/full-repo-sweep-test-guard-plan-g.md | 4055 | 15
.trae/documents/full-repo-sweep-plans/full-repo-sweep-tests-readme-plan-e.md | 1579 | 16
.trae/documents/full-repo-sweep-plans/full-repo-sweep-workspace-plan-l.md | 3501 | 13
.trae/documents/full-repo-sweep-plans/full-repo-sweep-yaterc-plan-c.md | 2829 | 15
.trae/documents/full-repo-sweep-plans/overview.md | 4573 | 16
.trae/documents/full-repo-sweep-review-fixes-plan.md | 2371 | 7
.trae/documents/iktbxc-issue-notes.md | 9162 | 31
.trae/documents/iktbxc-plan.md | 20737 | 21
.trae/documents/iktbxc-plans/iktbxc-cmdline-relocation-plan-c.md | 8533 | 6
.trae/documents/iktbxc-plans/iktbxc-key-codec-plan-a.md | 6973 | 1
.trae/documents/iktbxc-plans/iktbxc-view-plan-b.md | 8365 | 0
.trae/documents/iktbxc-plans/overview.md | 8716 | 7
.trae/documents/iktbxc-reference-inventory.md | 9784 | 1
.trae/documents/lsp-hover-docs-plan.md | 24314 | 18
.trae/documents/lsp-hover-docs-plans/lsp-hover-docs-capabilities-plan-b.md | 4333 | 0
.trae/documents/lsp-hover-docs-plans/lsp-hover-docs-docs-plan-f.md | 5862 | 18
.trae/documents/lsp-hover-docs-plans/lsp-hover-docs-flows-plan-g.md | 9716 | 1
.trae/documents/lsp-hover-docs-plans/lsp-hover-docs-integration-plan-h.md | 11414 | 16
.trae/documents/lsp-hover-docs-plans/lsp-hover-docs-keymap-plan-c.md | 6176 | 0
.trae/documents/lsp-hover-docs-plans/lsp-hover-docs-manager-plan-d.md | 6956 | 2
.trae/documents/lsp-hover-docs-plans/lsp-hover-docs-parsing-plan-a.md | 5510 | 0
.trae/documents/lsp-hover-docs-plans/lsp-hover-docs-popup-plan-e.md | 7190 | 0
.trae/documents/lsp-hover-docs-plans/lsp-hover-docs-smoke-plan-i.md | 5342 | 0
.trae/documents/lsp-hover-docs-plans/overview.md | 10059 | 5
.trae/documents/lsp-navigation-issue-brief.md | 4437 | 11
.trae/documents/lsp-navigation-plan.md | 7621 | 1
.trae/documents/lsp-navigation-plans/lsp-navigation-chooser-plan-c.md | 3762 | 0
.trae/documents/lsp-navigation-plans/lsp-navigation-flow-plan-d.md | 8624 | 0
.trae/documents/lsp-navigation-plans/lsp-navigation-guards-docs-plan-e.md | 6156 | 3
.trae/documents/lsp-navigation-plans/lsp-navigation-keys-plan-b.md | 6137 | 0
.trae/documents/lsp-navigation-plans/lsp-navigation-request-layer-plan-a.md | 7324 | 0
.trae/documents/lsp-navigation-plans/overview.md | 3239 | 0
.trae/documents/lsp-navigation-review-fixes-plan.md | 4599 | 0
.trae/documents/naming-hygiene-pr-review-plan.md | 10480 | 73
.trae/documents/soft-wrap-plans/soft-wrap-config-plan-c.md | 5716 | 0
.trae/documents/soft-wrap-plans/soft-wrap-core-plan-a.md | 5241 | 0
.trae/documents/soft-wrap-plans/soft-wrap-docs-plan-f.md | 3856 | 16
.trae/documents/soft-wrap-plans/soft-wrap-keys-plan-d.md | 6949 | 1
.trae/documents/soft-wrap-plans/soft-wrap-robustness-plan-e.md | 5336 | 0
.trae/documents/soft-wrap-plans/soft-wrap-view-plan-b.md | 7214 | 0
.trae/documents/toggle-comment-plan.md | 16734 | 11
.trae/documents/toggle-comment-plans/overview.md | 1375 | 0
.trae/documents/toggle-comment-plans/plan-a.md | 1505 | 0
.trae/documents/toggle-comment-plans/plan-b.md | 2229 | 0
.trae/documents/toggle-comment-plans/plan-c.md | 1464 | 0
.trae/documents/toggle-comment-plans/plan-d.md | 1675 | 0
.trae/reviews/2026-11-06-enew-args-lsp-attach-iteration-review.md | 6306 | 2
.trae/reviews/2026-11-06-enew-args-lsp-attach-review.md | 6909 | 1
.trae/reviews/2026-11-08-extension-trust-hardening-r2-lua.md | 15427 | 0
.trae/reviews/2026-11-08-extension-trust-hardening.md | 23388 | 11
.trae/reviews/2026-11-16-marks-jumplist.md | 7156 | 0
.trae/reviews/2026-11-20-full-repo-sweep-fixes.md | 3974 | 1
.trae/reviews/2026-11-21-full-repo-sweep-independent-review.md | 3511 | 2
.trae/reviews/2026-11-22-lsp-navigation.md | 4873 | 0
.trae/reviews/2026-11-23-pr-review-enh-lsp-navigation.md | 9189 | 4
```

## 八、偏离记录

- `task-orchestration.md` §二.1 要求新建 worktree 后重建 `.venv`；本任务为纯文档变更、不运行任何 Python 测试或 pyright，故不重建沙箱（避免无意义安装与磁盘占用）。若后续出现非文档改动，即刻补建沙箱并跑全量门禁。
- `translator.md` 定义默认方向为「中文→英文」；本任务在任务书中显式覆盖方向，其余纪律不变。

## 九、执行回填（实测）

- 执行结构：5 波、14 名 translator 执行者（3+3+3+3+2），全部落盘；T07 曾漏 `iktbxc-plans/overview.md`，经探活核查后补译并完成校验。
- 校验结果：`python <TEMP>\yate_docs_verify.py` → `targets=79 failures=0`（非 Mermaid 代码块逐字一致、代码围栏数/标题数/表格行数/链接目标/反引号数一致、每篇中文字符 ≥30、UTF-8 无 BOM）。
- 覆盖率：两目录 727 个 Markdown（含本方案文档），中文字符 <100 的文件数 = **0**。
- 改动范围：`git status --short` = 79 篇译文（M）+ 本方案文档（??），无源码/配置/脚本改动；`git diff --stat` = 79 files changed, 5004 insertions(+), 6907 deletions(-)。
- 质量修复：主代理在波 1/3/4/5 校验中修正 10 处译文对行内代码/反引号的误改写（如 `asyncio.sleep(0)`、`await`、`scroll_col`、`dict`、`list()`、`except` 等），修复后全量复验 0 失败。
- 门禁：纯文档变更，按 `misc-rules.md` §三豁免 pyright / pytest / 架构 / 覆盖率 / 冒烟；未执行任何测试命令。
