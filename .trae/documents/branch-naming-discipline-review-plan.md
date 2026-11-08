# 分支命名纪律偏差 — 状态回填与自我批判修复方案

> 来源记录（唯一需求来源）：[2026-11-08-branch-naming-discipline.md](../reviews/2026-11-08-branch-naming-discipline.md)（评审索引 #66，主代理自审）。
> 关联计划：[extension-trust-hardening-plan.md](extension-trust-hardening-plan.md) §九、
> [extension-trust-hardening-review-fixes-plan.md](extension-trust-hardening-review-fixes-plan.md)、
> [overview.md](extension-trust-hardening-plans/overview.md) §六。
> 本方案只处理**记录、状态文档、索引与记忆**，不改产品代码 / 测试 / 配置。

## 一、目标与非目标

**目标**：把自我批判记录（#66）落盘并双向互链；订正主计划 §九 的归因表述与
2 处本机绝对路径；把 #66 结论回填至主计划、`overview.md`、评审索引、
修复方案执行记录与机器记忆；按纯文档口径完成验收并如实汇报。

**非目标**：不改分支名（当前 `feature/enh-extension-trust-hardening` 已按
`task-orchestration.md` §二.1 合规，类型 `enh` 依据 issue 标题 `ENH -` 自行裁定）、
不改 parent、不 rebase / merge / push、不重开产品代码评审、不批量清扫存量
文档、不修改 `task-orchestration.md` 等权威规则正文。

## 二、裁决表

| # | 来源记录条目 | 裁决 | 落点 |
|---|---|---|---|
| 1 | T1–T4、D1–D4 事实与责任归属 | 落盘独立评审记录「自我批判 + 逐条核对结论」，不含修复排期 | `.trae/reviews/2026-11-08-branch-naming-discipline.md` |
| 2 | `doc-conventions.md` §二.2 互链要求 | 落盘独立修复方案（本文件），与本记录双向互链 | 本文件 §开头 + 记录 §0/§8 |
| 3 | §3.3 归因失衡 | 订正主计划 §九「根因」段：主责在主代理，交叉引用为诱因 | `extension-trust-hardening-plan.md` §九 |
| 4 | T8 本机绝对路径 | 把主计划 §九 的 2 处盘符路径脱敏为相对写法（§五） | `extension-trust-hardening-plan.md` §九 |
| 5 | T9 索引缺项 | 评审索引新增 #66 条目 + 散文增量段；同日记录以主题区分，不加 `-2` 后缀 | `.trae/reviews/README.md` |
| 6 | 状态更新 | 主计划 §六 wave-4 行、`overview.md` §六、修复方案 §八/§九、任务状态记忆与 `MEMORY.md` 索引同步 #66 与提交数 | 见 §三 |
| 7 | D4 无人值守约束 | 追加到 `feedback_branch_naming.md`：事后纠正不得写成合规执行、纪律项不得抛给用户确认 | 机器本地记忆（非仓库文件） |
| 8 | 门禁 | 纯文档变更按 `misc-rules.md` §三 豁免测试门禁；第三轮六道门禁结果仍有效，本轮只做文档校验 | 本文件 §四 |

## 三、状态回填清单（文件 → 改动）

| 文件 | 改动 |
|---|---|
| `.trae/documents/extension-trust-hardening-plan.md` | §六 wave-4 行备注追加「#66 自审 MAJOR（纪律类）已登记、已订正」；§九 根因段订正主责、两处路径脱敏、追加 #66 互链与结论 |
| `.trae/documents/extension-trust-hardening-plans/overview.md` | §六 wave-4 行追加 #66 与状态结论 |
| `.trae/documents/extension-trust-hardening-review-fixes-plan.md` | 新增 §十「纪律自审 #66 状态结论」，与 #66 记录互链 |
| `.trae/reviews/README.md` | 2026-11-08 增量散文段追加 #66；编号表追加 #66 行（不改动 #62–#65 既有行） |
| 记忆 `feedback_branch_naming.md` | 追加 D4 类约束与「归因不得外推给规则文档」 |
| 记忆 `project_iktf4y_extension_trust_status.md` | 提交数 / HEAD / #66 状态同步 |
| 记忆 `MEMORY.md` | 索引行同步提交数与 #66 |

## 四、验收命令与判据

本轮变更**全部为 `.trae/` 下 Markdown 与机器本地记忆**，按
`misc-rules.md` §三「纯文档变更的验证豁免」**不运行 pytest / pyright / 覆盖率 /
冒烟**；第三轮六道门禁（pyright 0 / 3469 passed·10 skipped / 架构 37 /
覆盖率 92.96% / 冒烟 121/121·1464 / changelog 0 / diffcheck 0）在本轮之前已由
主代理亲跑且代码未再改动，结论继续有效。豁免不免除规则加载、命名与相对路径引用、
提交信息格式及如实汇报。

```powershell
git diff --check
.venv\Scripts\python.exe -m tools.changelog check
.venv\Scripts\python.exe -c "import re; from pathlib import Path; bad=re.compile(r'[A-Z]:/Programming'); rec=Path('.trae/reviews/2026-11-08-branch-naming-discipline.md'); plan=Path('.trae/documents/branch-naming-discipline-review-plan.md'); idx=Path('.trae/reviews/README.md'); main=Path('.trae/documents/extension-trust-hardening-plan.md'); assert rec.is_file() and plan.is_file(); assert 'branch-naming-discipline-review-plan.md' in rec.read_text(encoding='utf-8'); assert '2026-11-08-branch-naming-discipline.md' in plan.read_text(encoding='utf-8'); assert '| 66 |' in idx.read_text(encoding='utf-8'); assert not any(bad.search(p.read_text(encoding='utf-8')) for p in (rec, plan, main)); print('links/index/path checks OK')"
```

- `git diff --check`：退出码 0；
- `tools.changelog check`：退出码 0（released sections up to date）；
- 互链 / 索引 / 路径脚本：打印 `links/index/path checks OK` 且退出码 0；
- 新增两份文档另跑 `tools.mdlint --auto-lang --check` 取证，命中项如实登记；
  `.trae/` 计划与记录存在同构的存量规则命中，本轮**不做专项清扫**，只要求
  新增内容不含本机绝对路径、互链为相对路径。

## 五、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 自我批判写成形式化套话或把责任推给规则文档 | 每条结论绑定提交号 / 命令输出 / 文件行号；§3.1 明确主责、§3.3 订正上一轮归因 | `git checkout -- <本方案涉及文件>` |
| 新增记录违反 `doc-conventions.md` §二 / §五 | 同日以主题区分命名、无本机路径、记录与方案互链为相对路径 | 同上 |
| 索引 #66 与既有编号冲突 | 落盘前实测最大编号为 #65 | 同上 |
| 纯文档豁免被误用为「跳过全部校验」 | 仍跑 diffcheck / changelog / 互链脚本，并保留第三轮门禁证据 | 不适用 |

## 六、执行记录（回填）

| 项 | 结果 | 提交 |
|---|---|---|
| #66 自审记录 + 本方案落盘 | 已落盘：`2026-11-08-branch-naming-discipline.md`（索引 #66、自审局限声明、T1–T9 时间线、D1–D4 四类失误、主责判定与归因订正、MAJOR（流程/纪律类）定级、逐条核对、防复发约束、遗留事实）；本方案按 `doc-conventions.md` 的评审互链要求与之双向互链 | 本笔 `docs(review)` 提交 |
| 主计划 / overview / 修复方案 / 索引状态回填 | 已回填：主计划 §六 wave-4 行 + §九（归因订正为主代理主责、2 处本机绝对路径脱敏为 `../yate-extension-trust-hardening`、追加 #66 结论与互链）；`overview.md` §六 wave-4 行；修复方案新增 §十；`README.md` 新增 #66 散文增量段与编号表行（落盘前实测最大编号 #65） | 同上 |
| 记忆同步 | 已同步 `feedback_branch_naming.md`（D4 类约束：事后纠正不得表述为合规执行、纪律项不得抛回用户确认、责任不得外推给规则文档）、`project_iktf4y_extension_trust_status.md`（提交数 / HEAD / #66 状态）、`MEMORY.md` 索引行 | 机器本地，不入 git |
| 验收命令退出码 | `git diff --check` 0（仅 LF/CRLF 提示，无错误）；`tools.changelog check` 0；互链 / 索引 / 路径脚本 0（`links/index/path checks OK`）；两份新文档 `tools.mdlint --auto-lang --check` 修前 10 条 / 修后 9 条，按设计退出码 1（见 §6.1） | 同上 |

### 6.1 mdlint 命中与处置（如实登记）

- **修前**：`10 violation(s) in 2 files`，结构为 9 × `YM002 fullwidth-punct` +
  1 × `MD018`（标题井号后缺空格）。
- **MD018 已当轮修复**：#66 记录 §7 的续行原以 `#64 / #65 为准。` 起始（两空格缩进），
  被解析为井号后缺空格的标题；改为 `评审索引 #64 / #65 为准。` 并保留缩进，
  复跑后该条归零。这是结构性命中，不属可登记的存量风格。
- **9 条 YM002 按 §四登记、不专项清扫**：命中位置为
  `2026-11-08-branch-naming-discipline.md:31:177`、`:35:28`、`:47:38`、
  `:108:100`、`:119:35`、`:121:42`、`:130:52` 与
  `branch-naming-discipline-review-plan.md:16:27`、`:25:30`。逐处取证上下文均
  为仓库既有章节引用写法 `§二.1` / `§二.2`（半角句点紧邻中文），不是本机路径、
  不是绝对路径引用、不是链接形态问题。
- **同构存量取证**：同命令对三份已提交的既有文档
  （`extension-trust-hardening-plan.md`、`extension-trust-hardening-review-fixes-plan.md`、
  `README.md`）得到 `24` 条 YM002 / `81 violation(s) in 3 files`，证明该命中类型
  在 `.trae/` 计划与索引中既已存在；本轮按 `doc-conventions.md` §五「存量文档随
  下次修改逐步迁移，不做专项清扫」处理，只保证新增内容无本机绝对路径、互链为相对路径。
- **验收脚本自指修正**：初版互链 / 路径脚本把被检字符串写成源码字面量，导致
  本方案自身命中「plan 中不得含该字符串」而失败；改为
  `bad = re.compile(r'[A-Z]:/Programming')` 并把主计划纳入检测面（见 §四命令块），
  重跑退出码 0。该修正只影响验收脚本，不改任何被检文档内容。
- **本节回填文本自纠**：执行记录表格与本节初稿曾额外引入 1 条 YM002（表格内
  裸写的章节号）与 2 条 MD038（代码跨度首尾空格），已在同轮改写消除；最终
  复跑稳定为 `9 violation(s) in 2 files`、退出码 1，与上文登记一致。
  故本轮新增内容**未新增 lint 命中类型**，仅保留与仓库既有写法同构的 YM002。
