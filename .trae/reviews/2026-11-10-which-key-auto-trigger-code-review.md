# 2026-11-10 IKU55P which-key 自动触发开关：首轮代码评审

- 评审者：`code-review-expert`（`.trae/agents/code-review-expert.md` + `.trae/skills/python-code-review/SKILL.md`），自我批判已执行
- 范围：分支 `feature/enh-which-key-auto-trigger`，`master..HEAD`（基线 `18e96d2a`）/ 7 笔提交 / 工作树干净
- 结论：**REQUEST_CHANGES** — 0 BLOCKER / 1 MAJOR / 3 MINOR
- 规范来源：`.trae/rules/task-orchestration.md`、`plan-before-execute.md`、`architecture-boundaries.md`、`python-coding-style.md`、`doc-conventions.md`、`misc-rules.md`、`git-commit-message.md`
- 关联修复方案（互链）：[which-key-auto-trigger-review-fixes-plan.md](../documents/which-key-auto-trigger-review-fixes-plan.md)

## 一、实测命令与退出码（评审者亲跑，worktree 根）

| 命令 | 实测结果 | 退出码 |
| --- | --- | --- |
| `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/` | `0 errors, 0 warnings, 0 informations` | 0 |
| `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | 全绿，无 F/E | 0 |
| `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | `38 passed` | 0 |
| `.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -n auto` | `TOTAL 19838 1091 6326 582 93%`，`Total coverage: 93.03%` ≥ 75 | 0 |
| `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` | `124/124 scenarios`，`1511/1511 checks (100%)` | 0 |
| `.venv\Scripts\python.exe -m tools.changelog check` | `released changelog sections are up to date`；`[Unreleased]` 4 份滞后 8 commits（生成器机制，CI 只校验 released） | 0 |
| `git diff --check master..HEAD` | 无空白问题 | 0 |

补充实测：双语关键词成对检查 `missing: []`（0）；新场景 `--scenario which_key_auto_off_manual_toggle --jobs 1 --svg` → 18/18 PASS（0）；无并行 flake 需 `-n 1` / `--jobs 1` 复核。

覆盖率明细：`whichkey_flows.py` 97%（未覆盖 190、196→195 为既有候选/全表分支）、`yaterc_options.py` 99%、`config.py` 99%（未覆盖 282 既有 `_parse_shell`）；本次新增行均有覆盖。

## 二、发现清单（严重度排序）

### [major] M-1 计划文档回填区与偏离记录为空

- 位置：`.trae/documents/which-key-auto-trigger-plan.md:144-146`（§十占位符）、`.trae/documents/which-key-auto-trigger-plans/overview.md:80-82`（§七占位符）、plan-a..e 均无偏离与实测记录
- 规则来源：`task-orchestration.md` §二.7（回填真实前后数字、偏离记录）与 §三（每步输入 / 产出 / 审核结论 / 迭代轮次必须回填方案文档）；`plan-before-execute.md` §二.5
- 事实：wave-1..3 两处已登记的偏离（plan-d 用例 9 断言形态、plan-e `snapshot_svg` 位置）只存在于执行者报告与本实现中，未落到唯一规范来源；主计划与总纲回填区仍是「收尾时填写」占位符；六份子计划无实测数字
- 影响：闭环事实链不可追溯，违反流程硬性要求；产品行为本身无缺陷

### [minor] m-1 双语 which-key 文档分支计数未随新增闸门更新

- 位置：`yate/docs/which-key.en.md:37-38`（`four mutually exclusive branches`）、`yate/docs/which-key.zh.md:31`（`四个分支互斥`）
- 规则来源：`doc-conventions.md` §三（双语同步）、§六（表述准确性）
- 事实：`yate/flows/whichkey_flows.py:104-120` 现有总开关短路 → pinned → auto 闸门 → `ctrl+w` → pending → 末位 clear 的判定序列；文档仍枚举四项且未含 auto 闸门，虽同段后文补充了闸门说明，计数与结构仍失准

### [minor] m-2 `EnabledPredicate` 类型注释对新 auto 谓词描述错误

- 位置：`yate/flows/whichkey_flows.py:35-41`（问题句在 :39-40）
- 规则来源：`python-coding-style.md` §2.5 / §6.1
- 事实：`:35-36` 已声明该类型别名同时服务两个开关，`:39-40` 仍写「Returning `False` hides the panel and turns F9 into a no-op」；该语义只对 `which_key` 成立。实测 `which_key_auto_enabled=False` 时 `toggle()` 仍能正常钉住 / 解除，pinned 保留来自 `refresh()` 分支顺序

### [minor] m-3 矩阵用例与 master-off 用例存在恒真断言

- 位置：`tests/test_whichkey_flows.py:434`（`assert panel.clears >= clears_before`）、`:528`（`assert panel.clears >= 1`）
- 规则来源：`python-coding-style.md` §4.7、`task-orchestration.md` §二.6、plan-d §六「用例恒真」风险项
- 事实：实测 `which_key=False` 时 `toggle()` 的 `clears` 增量为 0，而 `refresh()` 已使 `clears` 增加 1；两条 `>=` 在任何实现下均成立，即使 `toggle()` 错误地清空面板也不会判红。当前「F9 no-op」契约仅由 `panel.shown == []` 部分覆盖

## 三、强制自我批判台账（评审者输出）

| # | 初版等级 | 最终状态 | 理由 |
| --- | --- | --- | --- |
| 1 | major | 删除 | plan-d 用例 9 原断言 `shown == []` 客观不可达（`_PanelRecorder.shown` 为 append-only 历史）；替代的 4 项断言能钉住契约，偏离合理 |
| 2 | major | 删除 | plan-e `snapshot_svg` 移入 `async with` 与全仓 25 个场景惯例一致；`--svg` 单跑 18/18 通过，非掩盖 ScreenStackError |
| 3 | major | 降级 minor | 双语计数失准属实，但无可执行行为影响 |
| 4 | major | 降级 minor | 注释语义冲突属实、位于本分支改动块内，但无运行时影响 |
| 5 | major | 降级 minor | 矩阵 else 分支仍有 `shown == []` 覆盖，非完全恒真，但应收紧 |
| 6 | major | 降级并合并入 5 | 与 5 同类断言松弛 |
| 7 | major | 保留 | 实证回填区为空、子计划零偏离记录，违反闭环硬性要求 |

漏报自查：正确性 / 边界 / 异常 / 并发 / 性能 / 类型 / 测试覆盖七维均已回扫，除上述外无新增发现。

## 四、通过的核验项（无问题）

- 四行行为矩阵逐行吻合：默认态前缀弹 `d` 候选 + F9 出 `vim` 全表；`auto=False` 前缀不弹（`clears==1`）而 F9 仍可钉住；`which_key=False` 两行全隐藏且 F9 no-op，重新启用恢复 pinned。
- 钉住态不被清除 / 覆盖：`auto=False` + pinned + 前缀 `d` + `ctrl+w` 挂起时 `shown[-1][0]` 恒为 `vim`、`clears` 不增；auto 重开仍保持 pinned。
- `ctrl+w` 链：`editor_compose.py:375` 的 `on_chord_change = whichkey.refresh` 与每键 `refresh_ui` 共用 `refresh()` 内的 auto 闸门（`whichkey_flows.py:110-112`）。
- `:set` 即时生效：`commands.py:124-137` 只写 config + `refresh_ui()`，不无条件 `clear()`；往返与非法值实测 0 clear / 非法 0 refresh。
- 非 bool rc 值：`which_key_auto = 1` → 字段保持 `True` 且 `errors` 含 `which_key_auto must be True or False, got 1`；`None` 保留默认；与 `which_key` 同构。
- 总开关优先、vsc 不自动弹出、默认值 `True` 兼容、重新启用恢复钉住状态，均有对应用例。
- 双语文档同步：8 份文档 + `yaterc.example` 关键词检查通过；`which_key=False` 既有表述未被改写，仅补优先级。
- README 核对结论：无 which-key 开关条目，不虚构条目成立。
- CHANGELOG 四份生成物未在 `git diff --name-only master..HEAD` 中；`check` 退出码 0，仅 `[Unreleased]` 滞后（生成器机制，非缺陷）。
- 提交纪律：7 条全英文 `type(scope): subject`，无 push、无合并。
- 架构：新增 import 仅 `pytest` 与既有 L0 `yate.config`；无新连线 / `Protocol` / `TYPE_CHECKING` / `Any` / 相对导入；38 条架构守卫全绿；新增代码段 ASCII 合规。

## 五、结论

**REQUEST_CHANGES**：无 blocker；M-1 为闭环流程硬性要求，须补齐回填与偏离记录后再复审；3 项 minor 建议同轮修复。产品代码行为与 issue 四行矩阵、7 条验收标准逐条吻合，首轮全量门禁已全绿。
