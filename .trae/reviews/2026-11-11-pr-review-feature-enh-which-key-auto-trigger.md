# 2026-11-11 合并前 pr-review：feature/enh-which-key-auto-trigger

- 模式：`.trae/skills/pr-review/SKILL.md` `review`（默认，无 base ref → 以 `master` merge-base 为基线）
- 范围：`git diff master...HEAD`，merge-base `18e96d2a`（= `origin/master`）；13 笔提交 / 30 文件 `+1529 −34`；HEAD `79dffdbd`
- 远端状态：`origin/feature/enh-which-key-auto-trigger` 与 HEAD 一致（13 笔已推送）；本地在本次评审产物提交前工作树干净
- 方法：3 名只读分域审查员并行（A 功能/安全/性能、B 架构/可维护性/纪律、C 测试/双语文档/记录/合并就绪）+ 主代理逐条回读复核 + 主代理亲跑全部硬门禁
- 噪声过滤（skill Step 1）：diff 中无 `*.pyc` / lock / `*.spec` / 二进制 / 纯重排版 hunk，无需跳过
- 结论：**`Overall: APPROVE`** — 0 BLOCKER / 0 MAJOR / 5 MINOR 报告（其中 1 项经主代理字符级复核撤回为误报，4 项当轮修复；AI 预评审，合并决定仍归人工）

## 一、审查员存活与产出（如实登记）

| 域 | 结果 |
| --- | --- |
| A | 交付完整报告（落盘于工具结果缓存）：`Overall: APPROVE`，0/0/0，六项 Strengths，三维度均附 `file:line` 证据 |
| B | 首次同步返回在输出最终报告前被截断（仅交付自我批判台账）；按 `subagent-workflow.md` §五.4 变更任务粒度（限制轮次、要求 ≤2000 字完整报告）重试一次后交付完整报告：`Overall: APPROVE`，0/0/1。重试时按角色剧本尝试 `Skill(python-code-review)` 返回 not found，已按角色文件回退分支使用 6 维度 + 三级严重度 + Step 4 格式，未阻塞评审 |
| C | 交付完整报告（落盘于工具结果缓存）：4 MINOR，含逐域核对表、自我批判降级说明与 Strengths |

三域报告的全部发现均由主代理重读 `文件:行号` 独立复核后才纳入本记录；主代理未直接采信自述结论。

## 二、硬门禁实测（主代理亲跑，worktree 根，退出码权威）

| 命令 | 实测结果 | 退出码 |
| --- | --- | --- |
| `pyright yate/ tests/ tools/ pack/` | `0 errors, 0 warnings, 0 informations` | 0 |
| `pytest tests/ -q -n auto` | 全 `[100%]`，无 F/E | 0 |
| `pytest tests/test_architecture.py -q` | 38 点全绿 | 0 |
| `pytest tests/ --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -n auto` | `TOTAL 19838 1099 6326 577 93%`；`Total coverage: 92.99%`；`3610 passed, 10 skipped in 163.73s` | 0 |
| `tools.smoke_test run --jobs 4` | `124/124 scenarios` / `1511/1511 checks (100%)`，`90.28s` | 0 |
| `tools.changelog check` | `released changelog sections are up to date`；4 份 `[Unreleased] lags 14 commit(s)`（生成器机制，CI 只校验 released） | 0 |
| `git diff --check master...HEAD` / `git diff --check` | 无空白问题 | 0 / 0 |

覆盖率时点：闭环终轮 92.96% → 本次 pr-review 92.99%，并行覆盖率正常波动，均 ≥75 门槛；`[Unreleased]` 滞后 14 笔属生成器设计（历史裁决见 `which-key-auto-trigger-plan.md` §七）。

## 三、发现清单（按严重度）

### [MINOR] `yate/flows/whichkey_flows.py:9` — 模块 docstring 的 `refresh()` 分支枚举漏了 auto 闸门（B 域）

- Problem：`:8-10` 仍按「pinned / `ctrl+w` / pending / hidden」枚举，未含本次新增的 auto 闸门；`:12-14` 下一句虽补述闸门位置、`refresh()` docstring `:100-106` 也已完整，但唯一的结构化枚举不完整，与双语 which-key 文档的「五个互斥分支」口径不齐。属首轮 m-1 同类问题的单点遗漏，无运行影响。
- 依据：`python-coding-style.md` §二 docstring 规范；`doc-conventions.md` §六表述准确性。主代理回读 `:1-16` 与 `:100-106` 确认。
- Fix：在 `:9-10` 枚举中插入 `the auto-trigger gate`，保持 ASCII 与 RST 引用格式。

### [MINOR] `tests/test_whichkey_flows.py:407` — 矩阵用例 master-off 两行缺少 `panel.last` 断言（C 域）

- Problem：`:431-434` 的 else 分支断言 `shown_before == []` / `panel.shown == []` / `panel.clears == clears_before`，已非恒真（错误清面板会令 `clears` 变 2 而判红），且 `test_master_switch_off_wins_over_auto_disabled:525-531` 有精确定值覆盖；但矩阵用例自身未断言 `panel.last == "clear"`，两处用例强度不对称，docstring `:408-409` 的 no-op 语义可读性弱。
- 依据：`python-coding-style.md` §4.7。审查员初版拟报 MAJOR，回读后因已有专门用例 + 非恒真而降级 MINOR。
- Fix：else 分支补 `assert panel.last == "clear"` 及一行 ASCII 注释。

### [WITHDRAWN] `yate/docs/yaterc.en.md:82` / `yate/docs/yaterc.zh.md:74` — 「`which_key=False` 裸写」为误报（C 域原报 MINOR）

- 撤回原因（pr-review skill Step 5）：P1 执行时准备加反引号前发现目标状态已存在；主代理独立以 `chr(96)` 构造反引号做字符级复核，实测 `backticked: ['yate/docs/yaterc.en.md', 'yate/docs/yaterc.zh.md']`、`bare_hits: []`，`git status` 中两文件零改动。两行在 HEAD 原本就是反引号包裹的 `which_key=False`，审查员与主代理初次回读均误判。
- 处置：该发现撤回，双语文档零改动，不计入合并前待办；本会话内不再重提，除非出现新证据。
- 依据：主代理复核命令退出码 0 + `git diff` 为空；`pr-review` skill Step 5（反馈环与误报学习）。

### [MINOR] `.trae/reviews/README.md:217` — #74 索引「10 笔提交」未标注为复审时点快照（C 域）

- Problem：散文段 `:217-218` 与表格行 `:305` 写「10 笔提交」，而分支终态为 13 笔（收尾 3 笔见主计划 §12.3）；#73 行「7 笔提交」同理。数字是各自评审时点事实、不失真，但索引未标注时点，读者按终态复核会见到 13 ≠ 10 / 7。
- 依据：`doc-conventions.md` §二 2.1（评审记录可复核）、`task-orchestration.md` §三（真实数字）。审查员初版拟报 MAJOR 后降级：篡改时点数字反而失真。
- Fix：不改数字，仅在散文段与表格行标注「复审时点 N 笔（分支终态 13 笔）」。

### [MINOR] `.trae/reviews/README.md:214` — #73 散文段状态标记与表格终态构成双状态源（C 域）

- Problem：散文段 `:214` 写「复审前状态 🔧 进行中」，表格行 `:304` 已为「✅ 已闭环」；虽前者是过程叙述，同一评审在同一文件出现两个标记，读者易误读为仍未闭环。
- 依据：`doc-conventions.md` §二 2.1（状态单一来源）。主代理回读两处确认。
- Fix：散文段末句改为指向 #74 终态，消除过期标记。

## 四、逐条回读后的核对结论（无发现维度）

- A 域：四行矩阵、钉住态保留、`ctrl+w` 双链门控、`:set` 即时生效、非 bool rc 记错且状态不变、vsc、默认 `True`、总开关优先逐项实证通过；安全（无 secrets / 注入 / eval / 路径穿越）、性能（新增仅一次 O(1) 谓词求值，无循环 I/O / O(n²)）均无发现。
- B 域：R1-R15 无新 import 连线 / App 句柄 / UI 层越界；无新 `Protocol` / `TYPE_CHECKING` / `Any` / `# type: ignore` / 相对导入 / 禁用命名；ASCII、注解、行宽、tracing 合规；13 条提交信息全英文规范；生成式 CHANGELOG 四份未手改；无需新增架构守卫（无新连线，`SET_OPTION_SPECS` ↔ `SET_APPLY` 一致性已有守卫）。
- C 域：15 条新增测试项与 1 个新冒烟场景（18 checks）真断言、既有两场景零改动、无真实睡眠；双语 8 份文档 + 示例配置成对、`which_key=False` 既有陈述未改、触发时机描述未变；计划/评审文档命名、相对链接、回填区、#73/#74 编号分歧登记合规；无未提交改动、无与 `master` 的合并冲突迹象。
- 已知裁决未被新证据推翻：CHANGELOG 生成物不手改；README 无 which-key 开关条目；覆盖率为时点快照；「不重新设计」迭代偏离已登记；`[Unreleased]` 滞后为生成器设计。

## 五、Strengths（skill Step 4）

1. 自动闸门置于 `refresh()` 的 pinned 分支之后，使「钉住优先于自动开关」成为结构保证；`toggle()` 完全不参与 auto 判定，两条自动通路（每键 `refresh_ui` 与 `on_chord_change`）共用单一决策点。
2. `which_key_auto_enabled` 为构造必填谓词、无默认值，漏接线在构造期立即暴露；`_apply_which_key_auto` 刻意不调 `clear()`，并由 `clears == 0` 断言固定「关自动弹窗不得抹掉钉住页」。
3. rc 校验与既有布尔选项逐字同构，坏值只进 `config.errors`、零迁移、零行为回归。
4. 测试矩阵参数化四行 + 负向演练（改错实现后 3 条判红）证明断言非恒真；偏离记录（append-only 记录器、`ScreenStackError`）附实测依据而非粉饰。
5. 双语五分支叙述与 `refresh()` 实现逐分支对账，评审记录 / 修复方案 / 计划 / 索引双向互链，闭环事实链可追溯。

## 六、结论与关联

`Overall: APPROVE`：无 BLOCKER / MAJOR；报告 5 项 MINOR 中 1 项经主代理字符级复核撤回（见 §三第 3 条，双语文档零改动），其余 4 项为文档表述、断言强度与索引时点标注类，不阻塞合并并按本仓库严格纪律当轮修复；修复后主代理复跑全量门禁，实测数字见修复方案 §五。关联修复方案：[which-key-auto-trigger-pr-review-plan.md](../documents/which-key-auto-trigger-pr-review-plan.md)。合并决定归人工；本评审不执行合并、不执行推送。
