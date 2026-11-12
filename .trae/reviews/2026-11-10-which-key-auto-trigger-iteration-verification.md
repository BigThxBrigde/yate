# 2026-11-10 IKU55P which-key 自动触发开关：第二轮复审（迭代验证）

- 评审者：`code-review-expert`（`.trae/agents/code-review-expert.md` + `.trae/skills/python-code-review/SKILL.md`），强制自我批判已执行；本轮零写入
- 范围：分支 `feature/enh-which-key-auto-trigger`，`master..HEAD`（基线 `18e96d2a`）/ 10 笔提交 / 工作树干净
- 结论：**APPROVE** — 0 BLOCKER / 0 MAJOR / 2 MINOR（非阻塞）
- 关联：首轮评审 [2026-11-10-which-key-auto-trigger-code-review.md](2026-11-10-which-key-auto-trigger-code-review.md)（REQUEST_CHANGES，1 MAJOR + 3 MINOR）、修复方案 [which-key-auto-trigger-review-fixes-plan.md](../documents/which-key-auto-trigger-review-fixes-plan.md)、主计划 [which-key-auto-trigger-plan.md](../documents/which-key-auto-trigger-plan.md)

## 一、七项强制核验逐条裁定（file:line 证据）

| # | 核验项 | 证据 | 判定 |
| --- | --- | --- | --- |
| 1 | M-1 闭环 | 主计划 §10（`:144-192`）与总纲 §7（`:80-111`）占位符清零（`placeholders: []`）；plan-a `:72-80`、plan-b `:66-73`、plan-c `:60-68`、plan-d `:85-96`、plan-e `:72-82` 均有执行回填；两处偏离（plan-d `:96`、plan-e `:82`）与「不重新设计」裁决（主计划 `:188`、总纲 `:101`）附实测依据；README #73 散文 `:209-216` / 表格 `:295` 与编号分歧 `:217-218` 齐全，#72 段 `:196-208` 完整，3 个链接目标实测可达 | PASS |
| 2 | m-1 闭环 | `yate/docs/which-key.en.md:37-46` / `which-key.zh.md:31-36` 改为五个分支，序列与 `yate/flows/whichkey_flows.py:108-124` 对应；触发时机语义（en `:24`）未变 | PASS |
| 3 | m-2 闭环 | `yate/flows/whichkey_flows.py:35-44` 拆分 master / auto 谓词语义；ASCII 实测 `non_ascii_lines: []`；`git diff dde0211b HEAD -- yate/flows/whichkey_flows.py` 仅注释增删 | PASS |
| 4 | m-3 闭环 | `tests/test_whichkey_flows.py:434` 与 `:525-531` 改为精确等值；**负向演练**：临时把 master-off 的 `toggle()` 改为 `self._panel.clear(); return` 后 3 条用例判红（`assert 2 == 1`），还原后 `-n 1` 30 passed；`_make_flows`（`:55-77`）完整 | PASS |
| 5 | 无回归 | 四行矩阵 `:404-434`、钉住态 `:477-496`、`ctrl+w` `:454-461` + `editor_compose.py:370`、`:set` `commands.py:124-138`、非 bool `yaterc_options.py:561-568`、vsc `:534-545`、默认 `config.py:183` 全部实测通过；双语对称差集空；CHANGELOG 生成物未出现在 `git diff --name-only`；10 条提交信息全英文规范；分支无 upstream（10 笔未推送）；架构 38 passed | PASS |
| 6 | 修复引入的新问题 | 2 项 MINOR，见 §三 | 登记 |

## 二、实测命令与退出码（评审者本轮亲跑，worktree 根）

| 命令 | 实测结果 | 退出码 |
| --- | --- | --- |
| `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/` | `0 errors, 0 warnings, 0 informations` | 0 |
| `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | 全 `[100%]`，无 F/E | 0 |
| `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | `38 passed` | 0 |
| `.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -n auto` | `TOTAL 19838 1085 6326 577 93%`，`Total coverage: 93.07%`，`3610 passed, 10 skipped in 193.14s` | 0 |
| `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` | `124/124 scenarios`，`1511/1511 checks (100%)`，`80.23s total` | 0 |
| `.venv\Scripts\python.exe -m tools.changelog check` | `released changelog sections are up to date`；4 份 `[Unreleased] lags 11 commit(s)`（生成器机制，CI 只校验 released） | 0 |
| `git diff --check master..HEAD` | 无空白问题 | 0 |

补充：`tests/test_whichkey_flows.py -q -n 1` → 30 passed（0）；`--scenario which_key_auto_off_manual_toggle --jobs 1` → 18/18 checks（0）；无并行 flake 需复核。覆盖率未覆盖行均为既有分支（`whichkey_flows.py` 97%：`194`、`200->199`；`config.py` 99%：`282`；`yaterc_options.py` 99%：`189->199`），本次新增代码行零未覆盖。

## 三、新发现（2 MINOR，非阻塞）

### [minor] N-1 双语文档同一段落重复两遍（F2 修复引入）

- 位置：`yate/docs/which-key.en.md:12-16` 与 `:33-35`；`yate/docs/which-key.zh.md:10-13` 与 `:28-29`
- 规则来源：`doc-conventions.md` §三 / §六；`python-coding-style.md` §6.1 可读性
- 事实：两处几乎同措辞说明 `which_key_auto = False` 只关自动弹出、F9 仍可用、钉住态不受前缀影响；导语段 `:12-16` 还提前引用「下文优先级列表」，形成叙述回环。零功能影响
- 处置结果（已发生）：主代理当轮删除 en `:12-16` / zh `:10-13` 前置重复段，保留 §1 概述内段落；双语同改，`which_key = False` 既有导语保留

### [minor] N-2 残留弱断言 `panel.clears > clears_before`

- 位置：`tests/test_whichkey_flows.py:566`
- 规则来源：`python-coding-style.md` §4.7；plan-d §六「用例恒真」风险项
- 事实：同函数 `:565` 已用 `len(panel.shown) == shown_count` 精确固定「无新增 show」，`:566` 的 `>` 非恒真（零次 clear 会失败），但无法区分清一次与错清多次。plan-d §三.9 原文即「clears 增加」，故不属 m-3 未闭环
- 处置结果（已发生）：主代理当轮收紧为 `assert panel.clears == clears_before + 1`；局部 pyright / pytest 退出码 0，双语关键词成对检查 `missing: []`

## 四、强制自我批判台账（摘要）

| # | 初版候选 | 最终状态 | 理由 |
| --- | --- | --- | --- |
| 1 | 双语段落重复 → minor | 保留 | 回读四处确认重复属实，且均在本分支新增块内 |
| 2 | `:566` 弱断言 → minor | 保留（降级说明） | 忠于 plan-d 原文「clears 增加」，不属 m-3 范围 |
| 3 | 索引表 #67–#72 缺表行 → minor | 删除 | master 侧同形态，属既有索引惯例 |
| 4 | 回填「滞后 8 commits」与现测 11 不符 → major | 删除 | 回填为时点事实（首轮 `d52dfd11`），篡改历史数字反而失真 |
| 5 | 「六道门禁」列 7 行 → minor | 删除 | 仓库既有术语，第 7 行 diffcheck 为附加项 |
| 6 | 编号分歧位置不当 → minor | 删除 | 紧接 #73 散文段且含合并动作项 |

漏报自查：正确性 / 边界 / 异常 / 并发 / 性能 / 类型 / 覆盖七维回扫完毕，除上述外无遗漏。

## 五、结论

**APPROVE — blocker = 0，major = 0。** 首轮 M-1 与 m-1 / m-2 / m-3 全部闭环且有可复现证据（负向演练 + 占位符扫描双重背书）；产品行为与 issue 四行矩阵、7 条验收标准逐条吻合；七道验证命令全 exit 0；未推送、未合并、工作树干净。两项新 MINOR 为非阻塞的文案冗余与断言强度加固，处置结果见 §三。修复后主代理另亲自执行全量收尾门禁，数字以其落盘回填为准。
