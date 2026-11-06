# 2026-11-06 合并前 PR 预评审：`enh/multi-dim-review-r2`

- **Date**：2026-11-06
- **Scope**：`master 75bccfa` → `enh/multi-dim-review-r2 @ b80505a`（`git merge-base` 与 master
  tip 相同，无分叉、无冲突面）；6 提交 / 20 文件 / +735−56；工作区 clean、未推送。
  评审对象是 `master...HEAD` 的**全部改动**，不评审 diff 外的 skill / 规则源 / CI 配置。
- **Sources**：[pr-review SKILL](../skills/pr-review/SKILL.md)、
  [本轮主计划](../documents/multi-dim-review-r2-pr-review-plan.md)、
  [上一轮只读事实记录](2026-11-05-multi-dim-review-r2.md)、
  [修复方案](../documents/multi-dim-review-r2-fixes-plan.md)、[评审索引](README.md)、
  被评审分支内 `.trae/rules/` 八份规则；3 名只读审查员（P1/P2/P3）并行报告 +
  主代理机械取证与逐条回读复核。
- **Noise filter**（skill Step 1，一次性声明）：diff 内无 `.pyc` / lock / 二进制 / `.venv` /
  生成物；无纯重排、纯格式 hunk，故不逐条枚举跳过项。
- **流程事实**：无人值守，方案批准与权限按总纲 §二.5 豁免，全程未向用户询问；
  `plan-architect-designer` 依记忆（frontmatter `qwen-3.7-plus` 未注册且任务书指定模型
  无效）不再重复 spawn，由主代理按 §三兜底产出主计划，**如实标注该环节子代理零产出**；
  3 名只读审查员一波 3 个（≤6）全部交付、零写盘、零门禁。

## Verdict

**基线态：REQUEST_CHANGES** —— 0 BLOCKER / **1 MAJOR** / **12 MINOR**。
**修复后：APPROVE** —— MAJOR 归零，MINOR 全部销账或按理由登记，六道硬门禁全 exit 0。
本记录是 AI 预评审的只读事实记录，不含人工批准；人工决策由 PR 审阅者作出。

## Findings

### [BLOCKER]

无。硬门禁无红灯；`pack/` 漏扫是本地命令口径缺口而非红灯（见 MAJOR-1 的复核说明）。

### [MAJOR]（1）

1. **本地 pyright 门禁口径漏 `pack/`，与规则 §二.7 / `pyproject.toml` 不一致**
   证据：[主计划 Step 5](../documents/multi-dim-review-r2-plan.md) 与
   [上一轮记录第九节](2026-11-05-multi-dim-review-r2.md) 的 pyright 命令均为
   `-m pyright yate/ tests/ tools/`；`task-orchestration.md` §二.7 要求
   `pyright yate/ tests/ tools/ pack/`；`pyproject.toml` 的 `[tool.pyright] include`
   含 `"pack"`，且 `pack/_common.py` 实存。主代理按四路径补跑实测
   `0 errors, 0 warnings, 0 informations`。
   复核说明：CI 用 bare `pyright --pythonplatform Windows`，受 `include` 管辖未漏扫；
   本 PR 未改 `pack/`。因此该 MAJOR 是**流程/记录口径缺口**，不掩盖本 PR 的产品代码缺陷，
   但按「收尾门禁必须按规则口径亲跑」的纪律必须闭环。
   闭环：本轮按四路径补跑（见硬门禁表）；主计划 Step 5 命令订正为四路径；
   上一轮记录第九节追加订正脚注；`pr-review` / `multi-dim-review` 两个 skill 的三路径
   写法属 diff 外存量规则源，按「只评审 diff」另案登记，不在本 PR 修改。

### [MINOR]（12，含 3 条经复核降级/登记不修）

| # | 位置 | 摘要 | 处置 |
|---|---|---|---|
| m-01 | `multi-dim-review-r2-fixes-plan.md:34` | 行尾单个空格（`git diff --check master...HEAD` 命中） | 删空格，提交后复查 exit 0 |
| m-02 | `yate/services/extensions/loader.py:54-56`（P1/P2 同源） | `LoadedExtension` docstring 仍称「de-duplication lookup stays a set query」，而收尾复核已删 `_resolved` | 改为 direct index 口径 |
| m-03 | `multi-dim-review-r2-fixes-plan.md:74,148` + 上一轮记录第十节（P1） | F6e 仍描述 `_resolved` 双集合写入；记录「四项全部闭环」未同步注释/方案残留 | 方案两行订正 + 记录追加订正说明 |
| m-04 | `yate/editor_components/terminal.py:182-186`（P1） | `log.debug` 在 tracing 默认关闭时不可见且不记堆栈；注释声称 `CancelledError` 被捕获（实际未捕获，由 `finally` 覆盖） | 补 `exc_info=True` + 注释订正；**不提升级别**（见复核删除/降级） |
| m-05 | `yate/services/workspace.py:571-585`（P1） | `final=False` 无条件，短文件（<2048 字节）末尾不完整 UTF-8 序列被缓冲放行，与 docstring「仅容忍 2048 边界截断」不符 | 改 `final=len(chunk) < 2048` + 新增 `test_is_text_file_rejects_truncated_tail_in_short_file`（先红后绿） |
| m-06 | `multi-dim-review-r2-fixes-plan.md:147` + 上一轮记录（P1） | 风险行称新增用例「覆盖空集」，但空集由 `next()` 提前返回、未触达 `_nearest_index`；用例是等价性守卫而非差异化验证 | 措辞订正；**否决**「直接调私有方法补空集」的改法（见复核删除/降级） |
| m-07 | `tools/pack/wiki/report.py:116-123`（P2） | 新增分桶循环形成 4 层嵌套（`python-coding-style.md` §五 嵌套 ≤3） | **降级 Deferred**：同分支存量 `:134` 已有 4 层；复杂度类下降是主要目标，抽函数扩大 diff 且无行为收益 |
| m-08 | `2026-11-05-multi-dim-review-r2.md:233`（P3） | 第十节称「最终态（全部主代理亲跑）」，但 `b80505a` 是纯文档改动、门禁在其之前跑，未标注豁免依据 | 追加 `misc-rules.md` §三 纯文档豁免注记 |
| m-09 | 提交链 `f2b5440..b80505a` + 主计划 §九（P3） | 实际顺序「修复方案 → 评审记录」与计划 Step 6/7 相反；`084c74a` 的修复方案链接指向当时尚未落盘的评审记录（中间态文档互链断链，最终态闭合） | 主计划 §九 显式登记偏离；逐笔 `git diff-tree` 复核无夹带；**不重排提交**（见复核删除/降级） |
| m-10 | `2026-11-05-multi-dim-review-r2.md:186`（P3） | 豁免账本写「D1/D2 的 3 条 MAJOR/MINOR」，按 13 维度表应为 5 条（2 MAJOR + 3 MINOR） | 订正为 5 条并注明订正来源 |
| m-11 | `multi-dim-review-r2-plan.md:205-206` + `multi-dim-review-r2-fixes-plan.md:102-104`（P2/P3） | 一处写 `--cov-fail-under=75`（实际命令未带该参数），另一处把阈值单源误引为 `misc-rules.md` §三 | 统一为「阈值 75 单源于 `pyproject.toml` 的 `[tool.coverage.report] fail_under`，`task-orchestration.md` §二.7 约束」 |
| m-12 | 三份新增文档内 `.trae/...` 行内代码路径（P3，约 20 处） | 按 `doc-conventions.md` §五 应为以引用文档自身位置为基准的相对路径 | **降级 Deferred**：§五 末条「存量随下次修改逐步迁移，不做专项清扫」；Markdown 链接已全部相对，批量替换属专项清扫且扩大 diff 无行为收益；命中清单已在本轮取证 |

### [SUGGESTION]（代表性，登记不修）

- `tools/mdlint/cli.py` 两处 `# noqa: BLE001 - backend/plugin startup failure` 理由可更贴切
  （运行时后端 / 本地 lint 后端）；`terminal.py` 两分支日志文案完全相同，可区分 PTY/OSError。
- `SearchEngine.matches` 的有序不变量此前未文档化 —— 本轮已顺手补一行注释
  （`yate/editor_core/search.py:38`），`replace_current` 原地重排的保序用例仍建议下轮补。
- `test_nearest_index_bisect_boundaries` 补一行英文 docstring —— 本轮已顺手补。
- 「先红后绿」措辞：F1 旧实现会因 `b"\x00" not in chunk` 恰好通过其中一条负向用例，
  不是所有新增用例都构成差异化验证；等价性守卫同样有价值，措辞宜区分。
- `%TEMP%\pytest-of-*` 的用户目录字面量在记录中宜用通配符 —— 上一轮已脱敏，本轮沿用。
- 主计划 §九 可补逐笔 tree 互链复核行；`pr-review` / `multi-dim-review` skill 的 pyright
  三路径与 `task-orchestration.md` §二.7 四路径不一致，建议另案统一（diff 外，本 PR 不动）。

## 主代理复核删除 / 降级（引反证）

- **删除 P1 MINOR-5 的改法建议**（「测试文件已有 `reportPrivateUsage` 豁免，可直接调
  `_nearest_index` 补空集用例」）：回读 `tests/test_editor_core.py` 文件头确认无
  `# pyright: reportPrivateUsage=false`；上一轮实测 pyright 对 7 处私有方法调用报该诊断，
  故该改法会引入红灯。只采纳其「措辞不实」部分。
- **降级 P1 MINOR-3 的「提升日志级别」**：`yate/logs.py` 的 tracing 是 opt-in 全仓设计
  （debug 默认不可见是既定契约，非本 PR 缺陷）；`python-coding-style.md` §4.5 只要求
  「except 块内至少记录日志或向用户反馈」，`log.debug` 已满足；改为 warning 会在正常
  退出路径引入 stderr 噪声。仅采纳 `exc_info=True` 与注释订正。
- **降级 P3 MINOR-6 / P2 M2 为 Deferred**：理由见 findings 表 m-12 / m-07。
- **否决「重排 6 笔提交」**：分支未推送但交互式 rebase 属破坏性历史改写；断链仅为
  文档互链且最终态闭合、无构建影响；按 git 安全协议优先落盘登记偏离。

## Strengths

- 范围干净：`merge-base` = master tip，无分叉无冲突面；6 笔 subject/body 全英文、
  `type(scope): subject` 合规；逐笔 `git diff-tree` 复核无夹带探针/生成物/二进制。
- 原 2 MAJOR 修复语义成立：`is_text_file` 用增量解码器区分「窗口边界截断」与
  「非法字节」，两条负向用例可先红后绿；`terminal.shutdown` 不再静默吞异常。
- 五处低复杂度替代（`set` 成员测试、`seen` 累加、group 分桶、`bisect_left`、dict 索引）
  均保持顺序/类型/返回值语义，`_by_resolved` 在两处 append 同步维护。
- 架构边界零违规：R1–R15 自检清单、`UI_FROZEN_FILES` / `SIZE_EXEMPT_FILES` 同步登记、
  flows→`yate.logs` 为合法向下依赖、无新增向上连线 / `Protocol` / `Any` / `type: ignore`。
- 交付物自洽：13 维度结论、Suspects / Deferred / 豁免账本 / 既往登记项复核清单齐备，
  无静默丢弃；评审记录、修复方案、主计划、README #57 索引互链闭合。
- 硬门禁六项全绿（下表），覆盖率 92.82% 远高于 75 阈值。

## 硬门禁实测（主代理亲跑，全部独立轮次）

| 门禁 | 命令 | 退出码 | 实测输出要点 |
|---|---|---|---|
| pyright | `-m pyright yate/ tests/ tools/ pack/` | **0** | `0 errors, 0 warnings, 0 informations` |
| pytest | `-m pytest tests/ -q -n auto` | **0** | `[100%]`，`-q` 无汇总行，以 exit code 为准 |
| 架构 | `-m pytest tests/test_architecture.py -q` | **0** | 37/37 守卫 |
| 覆盖率 | `-m pytest tests/ --cov=yate --cov-branch -n auto` | **0** | `3395 passed, 10 skipped in 169.59s`；`Required test coverage of 75.0% reached. Total coverage: 92.82%` |
| 冒烟 | `-m tools.smoke_test run --jobs 4` | **0** | `121/121 scenarios passed`、`1463/1463 checks (100%)`、84.16s |
| changelog | `-m tools.changelog check` | **0** | released 段 up to date（released/unreleased 中文缺失为生成物语义，exit 0） |

环境处置：门禁前探测到 `%TEMP%` 下 8 个轮换 `garbage-*` 目录 / 121158 条目，
以原生 `rmdir /s /q` 清理；六道门禁拆到独立工具调用轮次，长门禁用后台执行器 +
JSON 结果落盘规避工具空闲超时；未使用仓库内 `--basetemp`。本轮无 safe-delete 拦截。

## 修复后复核

| 项 | 结果 |
|---|---|
| 修复项 | 1 MAJOR（按 §二.7 四路径补跑 pyright + 主计划/上一轮记录口径订正）；12 MINOR 中 9 条当轮销账（代码 5 文件 + 测试 2 文件 + 文档 3 文件），3 条按理由登记（m-07 / m-12 降级 Deferred，m-09 显式登记偏离且不重排提交）。 |
| 新增/改动 | `yate/services/workspace.py`（短文件 EOF 用 `final=True` + docstring）、`yate/services/extensions/loader.py`（docstring）、`yate/editor_components/terminal.py`（`exc_info=True` + 注释）、`yate/editor_core/search.py`（有序不变量注释）、`tests/test_workspace_filter.py`（+1 负向用例）、`tests/test_editor_core.py`（+1 行 docstring）、三份既有文档订正；另新建本轮主计划、本记录、README 索引行。 |
| 六道门禁 | 全 exit 0（见上表）；`git diff --check master...HEAD` 在提交后复核为 0。 |
| 复核裁定 | **APPROVE**：0 BLOCKER / 0 MAJOR；MINOR 全部销账或登记，六道门禁全绿。 |

> 本记录为只读事实文档，不含修复排期；改法、验收命令与回滚见
> [本轮主计划](../documents/multi-dim-review-r2-pr-review-plan.md)。
