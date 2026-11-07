# 合并前 PR 预评审 — `fix/enew-args-lsp-attach`

- **日期**：2026-11-07
- **模式**：`review`（[pr-review SKILL](../skills/pr-review/SKILL.md) Step 2 默认：六维度 + Verdict + Action plan）
- **分支 / HEAD**：`fix/enew-args-lsp-attach`；审查员启动时 HEAD `629350a`，迭代设计
  `5bf3eb8`，修复波 `623422e`，收尾回填为最后一笔文档提交（无 push）。
- **范围**：`master...HEAD` **三点差异**，`merge-base` = `8e60598`；审查员启动时 HEAD
  `629350a`（含本轮方案文档共 18 提交），PR 主体 17 提交 / 24 文件 / +3111−44。
  master tip `3e92532` 独有 1 笔文档提交，与 PR 改动文件**零重叠**，
  `git merge-tree 8e60598 master HEAD` exit 0 无冲突面。
- **审查员**：3 名只读 `code-review-expert`（[剧本](../agents/code-review-expert.md)）一波并行：
  P1 功能正确性 / 边界 / 并发、P2 架构 / 安全 / 性能、P3 可维护性 / 文档 / 流程纪律。
  全员零写盘、零全量门禁；门禁由主代理在独立轮次亲跑。
- **规范来源**：[pr-review 方案](../documents/enew-args-lsp-attach-pr-review-plan.md)（唯一规范来源）、
  [主计划](../documents/enew-args-lsp-attach-plan.md)、
  [命名迁移方案](../documents/enew-args-lsp-attach-naming-plan.md)、
  [#59 首轮评审](2026-11-06-enew-args-lsp-attach-review.md)、
  [#60 迭代复审](2026-11-06-enew-args-lsp-attach-iteration-review.md)、
  `.trae/rules/` 八份规则。
- **噪声过滤**（skill Step 1，一次性声明）：三点 diff 内无 `.pyc` / lock / 二进制 /
  `.venv` / 生成物；`smoke_baselines/command_alias_roundup.json` 是**行为基线**
  （含新增 `enew_rejects_args`），不是噪声；无纯重排 / 纯格式 hunk。

## Verdict

- **基线**：`REQUEST_CHANGES — 0 BLOCKER / 1 MAJOR / 4 MINOR`（主代理逐条回读复核后）。
  审查员原始上报合计 0 BLOCKER / 2 MAJOR / 9 MINOR；复核后 1 MAJOR 降级、
  2 MINOR 删除、3 MINOR 降级或登记。
- **修复后**：`APPROVE — 0 BLOCKER / 0 MAJOR`。1 MAJOR + 2 MINOR 已闭环，
  其余按理由登记为 Deferred（见「遗留项」）。
- 产品代码 `yate/**` 零改动；修复仅涉及文档措辞与测试替身重命名。

## Findings（复核后基线）

| # | 级别 | 位置 | 发现 | 处置 |
|---|---|---|---|---|
| 1 | MAJOR | `.trae/documents/enew-args-lsp-attach-naming-plan.md:50-51` | §1 非目标断言「12 条既有 subject 不含 issue 编号名」与事实相反：`git log --format=%s 8e60598..9c90c8d` 实测 12 条中 **6 条含 `IKSFS7`**（`7011ff2` / `68a1ada` / `2c6989b` / `20e6b9c` / `6ec91ec` / `0619086`）。文档自述执行如实汇报规范，属不实陈述 | **已修**：§1 改为列明 6 个哈希的已知接受偏离；§4 追加偏离 #9；不改写历史（`623422e`） |
| 2 | MINOR | `tests/test_cmd_enew.py`（9 处） | `_Enrew*` 测试替身拼写与 `enew` 词根不符 | **已修** → `_Enew*`（`623422e`）；局部 pytest 6 passed / pyright 0 |
| 3 | MINOR | `.trae/documents/enew-args-lsp-attach-naming-plan.md:20`、`:275` | `§二.5` 引用在 `.trae/rules/` 零命中，易被误读为规则引用错误 | **已修**：补明来源为 always-applied workspace loader §二.5（无人值守 bypass），非 git 跟踪规则 |
| 4 | MINOR | `.trae/documents/enew-args-lsp-attach-naming-plan.md:99-102` | portable-wording 承诺范围未限定，与方案自身保留 worktree 目标路径形成自我矛盾 | **已修**：承诺限定到主计划 §0 的单一证据行，并链接 pr-review 迭代设计 |
| 5 | MINOR | `tools/smoke_test/scenarios/aliases.py` | `enew_rejects_args` 只断言 buffer 数不变，未在 e2e 层断言 usage 警告文本 | **Deferred**：`tests/test_cmd_enew.py` 已精确断言警告全文；新增 check 需重生成 baseline，属已知风险面，无行为收益 |

## 主代理复核删除 / 降级（引反证）

| 来源 | 初判 | 复核 | 反证 |
|---|---|---|---|
| P3 | MAJOR：命名迁移方案 11 行盘符路径违反 `doc-conventions.md` §五 | **降级 Deferred，不翻案** | 命名迁移 round-1/2/3 三轮一致性评审已就同一事实裁定不成立：这些是迁移的**目标产物路径**与实测输出证据，§五 约束的是仓库内文件引用与环境信息；§6 命令块改占位符会失去可执行性（`plan-before-execute.md` §二.2）；§五 末条存量迁移。其「自我矛盾」子点已作为 finding #4 采纳 |
| P1 | MINOR：等价路径 save-as 后 `_uri_cache` 被销毁、每次按键重算 `resolve()` | **删除（误报）** | `yate/editor_lsp/manager.py:454` 的 `_uri(doc)` 在 `:458` 的 `pop` **之前**已按新 spelling 建键；`tests/test_lsp.py:2485-2493` 断言去重后 `values.count(uri) == 1` 且旧键不在缓存 → 缓存命中 |
| P1 | MINOR：`previous_path` 捕获时机无负向演练 | **删除（误报）** | `tests/test_document_flows_saveas.py:180-181` 同时断言 `work.args == (doc, source)` 与 `doc.path == renamed`；实现若把捕获移到 `doc.save()` 之后会拿到 `renamed`，用例即红 |
| P1 | MINOR：same-URI 且从未 shown 路径无测试 | **Deferred** | 与 #60 minor#2 同源，主计划 §6 residual backlog 已在位；补测试会固化待修行为 |
| P2 | MAJOR 候选：`on_document_retargeted` 无 try/except + `exit_on_error=False` 吞异常 | **不成立** | 重试轮以 `path_to_uri` 的四类异常输入（NUL / 孤立代理码位 / 3000 字符 / UNC）实测全部不抛错；`on_document_shown` 同类路径风险不高于改动前 |
| P2 | MINOR：`_uri_cache` 单条旧键延迟清理 / 同 client didClose+didOpen 空转 | **Deferred ×2** | 前者有测试背书且 `_drop_uri_cache` 按 URI 值清理、非无界增长；后者是 plan-e §7 已登记的「旧 URI 让位 / close wins」显式取舍 |

## 审查员交付与存活统计

| 审查员 | 首轮 | 处置 | 结论 |
|---|---|---|---|
| P1 | 有效报告（APPROVE / 3 MINOR） | 直接采纳 | 功能正确性、边界、并发门控零 BLOCKER / MAJOR |
| P2 | **零产出**：交付物为上下文压缩摘要（`<analysis><summary>`），无 Verdict / Findings / 自我批判 | 按 `subagent-workflow.md` §五.4 变更任务粒度（5 个判定、30 次工具上限、输出格式硬约束）重试 **一次** | 重试交付有效报告：APPROVE / 2 MINOR / 0 BLOCKER / 0 MAJOR |
| P3 | 有效报告（REQUEST_CHANGES / 2 MAJOR / 3 MINOR） | 直接采纳 | 1 MAJOR 保留、1 MAJOR 降级、3 MINOR 中 2 修 1 登记 |

最终 **3/3 有效交付**；首轮零产出 1 名已如实登记。取证期未跟踪临时文件复核为 0
（`git status --porcelain -uall` 空）。

## Strengths

- LSP 生命周期改动具备 URI 级身份比较、owner 冲突让位、`_opening` 并发门控与
  close-beats-open 竞态处理，4/4 负向演练在旧实现全红（#59/#60 已闭环）。
- `manager.py` 797 行（< 800 守卫，仅 3 行余量）；三点 diff 内零新增 `Protocol` /
  `TYPE_CHECKING` / `Any` / `# type: ignore` / 禁用命名 / `self.log` / 向上 import /
  App 句柄，R1–R15 零违规。
- 中英双语手册与 LSP docs 成对同步；smoke baseline 只变更
  `command_alias_roundup.json` 一处。
- 全部提交的 subject/body 全英文且符合 `type(scope): subject`；无 amend / rebase /
  force / push。
- 命名迁移 10 份文档 git 识别 10 rename（86%–96%），流程文档如实记载 3 轮一致性
  评审与 9 条偏离。

## 六道硬门禁（主代理亲跑，独立轮次）

| # | 命令 | 实测 | 退出码 |
|---|---|---|---|
| 1 | `pyright yate/ tests/ tools/ pack/` | `0 errors, 0 warnings, 0 informations`（四路径，含 `pack/`） | 0 |
| 2 | `pytest tests/ -q -n auto` | exit 0；`-q` 无汇总行按退出码；`--junitxml` 取回 `tests=3432 failures=0 errors=0 skipped=10` | 0 |
| 3 | `pytest tests/test_architecture.py -q` | 37 passed | 0 |
| 4 | `pytest tests/ --cov=yate --cov-branch -n auto` | `3422 passed, 10 skipped in 147.12s`；`TOTAL 19425/1093/6206/570 = 93%`，`Required test coverage of 75.0% reached. Total coverage: 92.90%`（阈值单源 `[tool.coverage.report] fail_under = 75`） | 0 |
| 5 | `tools.smoke_test run --jobs 4` | `121/121 scenarios passed`、`1464/1464 checks (100%)`、79.05s | 0 |
| 6 | `tools.changelog check` | `released changelog sections are up to date`；unreleased 滞后为发布期刷新（与既有门禁口径一致） | 0 |
| + | `git diff --check master...HEAD` | 无空白错误 / 冲突标记 | 0 |

混合变更（含产品代码）**不适用** `misc-rules.md` §三 纯文档豁免，故全量门禁均已实跑；
修复波另跑 `pytest tests/test_cmd_enew.py -q`（6 passed）与 pyright 四路径（0）。

## 修复后复核

- MAJOR #1：命名迁移方案中 `contain no issue-number name` 出现次数 0；§1 列明 6 个
  哈希、§4 偏离 #9 在位；`git log --format=%s` 仍为 6 条含 `IKSFS7`（历史未改写，
  如实接受）。
- MINOR #2：`_Enrew` 0 处、`_Enew` 15 处；局部 pytest 6 passed / pyright 0。
- MINOR #3/#4：两处 `§二.5` 均带来源说明；新增相对链接目标存在。
- 六道门禁全 exit 0；`git status --short` 空；无上游、未推送。
- `0 BLOCKER / 0 MAJOR` → 修复后 **APPROVE**。

## 遗留项（Deferred，按规则登记，不修）

| 项 | 理由 |
|---|---|
| 冒烟未断言 `enew` usage 警告文本 | 单测已精确断言；基线重生成风险无行为收益 |
| same-URI 且从未 shown 时静默不 attach | #60 minor#2，主计划 §6 residual backlog；常规 UI 由 `_refresh_ui()` 兜底 |
| `_uri_cache` 单条旧键延迟清理 | 有测试背书，`_drop_uri_cache` 按 URI 值清理，非无界增长 |
| 同 client didClose+didOpen 空转 | plan-e §7 已登记的显式设计取舍 |
| 命名迁移方案内 worktree 目标路径 | 命名迁移 round-1/2/3 三轮一致性评审在案裁决；§6 命令块须可执行 |
| 6 条 commit subject 含 `IKSFS7` | 不可改写历史；已转为 §4 偏离 #9 如实登记 |

> 改法 / 验收 / 回滚见 [pr-review 方案文档](../documents/enew-args-lsp-attach-pr-review-plan.md) §6；
> 本记录按 `doc-conventions.md` §二.1 仅登记事实与核对结论。
