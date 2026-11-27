# IKTBXC 命名卫生计划

状态：**approved** —— 无人值守会话（用户指令 2026-11-07：不提问、不审批）。依据工作区规则 §二.5，审批视为已授予，但规则加载与收尾门禁仍为强制。基线：`master@3e92532`；worktree `yate-naming-hygiene`；分支 `ref/naming-hygiene`；独立 `.venv` 经 `.venv/Scripts/python.exe -c "import yate; print(yate.__file__)"` 验证解析到本 worktree 内（2026-11-07 重命名；见 §9.7）。

## 1. 输入（唯一事实来源）

- [iktbxc-issue-notes.md](iktbxc-issue-notes.md) —— 逐字 issue 素材。
- [iktbxc-reference-inventory.md](iktbxc-reference-inventory.md) —— 三处旧路径面、守卫常量，以及 issue 主张与仓库事实之间差异的 file:line 只读清单。
- 规则：[architecture-boundaries.md](../rules/architecture-boundaries.md)、[python-coding-style.md](../rules/python-coding-style.md)、[subagent-workflow.md](../rules/subagent-workflow.md)、[doc-conventions.md](../rules/doc-conventions.md)、[task-orchestration.md](../rules/task-orchestration.md)。
- 子计划索引：[iktbxc-plans/overview.md](iktbxc-plans/overview.md)。

## 2. 目标与非目标

目标：消除名称/角色不匹配，把纯补全函数移出 L3 flows 层，并让同一概念保持命名一致。

硬性非目标（issue §五，不扩大范围）：

- 零运行时行为变更、零新增依赖方向；diff 仅为 `git mv` + import 行 / 路径字符串 / docstring / 规则文档 / 测试名；
- 不重命名类（`EditorView`、`PaneRegistry`、`PaletteScreen`、`LspSync`）；
- 不改变插件公共 API，不改变面向用户的目录约定；
- 不回改 `CHANGELOG*`、`tools/changelog/zh_overrides.json`、`.trae/documents/**` 历史计划或 `.trae/reviews/**` 只读记录；
- 不借机拆分文件，不修改 `SIZE_EXEMPT_FILES`；
- P2 项（editor_sprites characters/chars、palette 一词三义）不在本 issue 的门禁批次内；
- 明确禁止 `editor_view.py` 作为新的 L2 模块名（它是 2026-11-02 退役的旧包名）。

## 3. 备选方案与否决理由

| # | 方案 | 决定 / 理由 |
|---|---|---|
| A1 | 保留 `keyproto/legacy.py`，只修改 docstring | 否决：issue P0-1 要求模块名与角色匹配；`legacy` 一词被读作"待删除"，而这是唯一活跃的编解码器。 |
| A2 | `git mv` 到 `yate/keyproto/key_codec.py`，重写第一行 docstring | **选定**：1 个文件 + 9 处活跃引用 + 1 行规则 + 3 行 wiki；名称表明角色。 |
| B1 | 把 L2 模块重命名为 `editor_view.py` / `text_view.py` | `editor_view.py` 被 issue 否决（旧包名回归）；`text_view.py` 因更长却未增加信息而被否决——类是 `EditorView`，所以 `view.py` 是最短且无歧义的名称。 |
| B2 | `git mv` 到 `yate/editor_components/view.py` | **选定**：消除 L2/L3 的 `editor.py` 重名，与 `EditorView` 对齐，该包中无现存 `view.py`（经目录列举验证）。 |
| C1 | 保留 `yate/flows/cmdline_completions.py`，只修文档 | 否决：P1-3 明确要求层级迁移；该模块不持有状态、不 import UI、不做流程编排（接线位于 `editor_compose.py:127-137`，向 `PromptBar` 注入一个 `partial`）。 |
| C2 | `yate/services/cmdline_completions.py` 且不注册 rank | 经实测否决：`cmdline_completions.py:12-14` import 了 `yate.registries` 和 `yate.session`（rank 1）以及 `yate.services.workspace`（rank 0）。`_layer_rank()` 对未注册路径默认取 0，且 `UPWARD_EDGES_FROZEN` 为空，因此 `test_no_unregistered_upward_imports` 会报告两条未注册的向上边。 |
| C3 | `yate/services/cmdline_completions.py` + `_LAYER_RANKS` rank 1 | 否决：把一个 L1 单文件放进 L0 的 `services/*` 叶子包，扩大了 issue 列为"明确不改"的那处 L0/L3 历史妥协；同时与 R4 中无 UI 包的措辞冲突。 |
| C4 | `yate/cmdline_completions.py` + `_LAYER_RANKS` 条目 `("cmdline_completions.py", 1)` | **选定**：issue 两个建议目标之一；像 `config.py` / `diagnostics.py` 那样的根级单文件；rank 1 匹配其两处 L1 import，因此所有既有边保持向下或同层；无向上边、无新增包例外。`README.md:272` 与 `README.zh.md:290` 都已在根 `yate/` 树中列出裸文件名，因此文档无需编辑即准确。 |
| C5 | 通过注入 callable 而非 `CommandRegistry` / `EditorSession` 来去掉 L1 import | 否决：改变签名与运行时接线，违反零行为变更的非目标。 |
| C6 | 在 `UPWARD_EDGES_FROZEN` 中登记两条边而非 rank 条目 | 否决：规则文本与守卫都声明例外集为空（自 2026-10-20 起零向上边）；重新开放它与"零依赖方向变更"矛盾。 |

需记录的偏离：issue §一.3 建议将 `services/` **L0 叶子**作为首选。选定的 C4 是其第二个建议目标，并带有显式的 L1 rank 注册。证据：`tests/test_architecture.py:520-525`（`_layer_rank` 默认取 0）、`:765-793`（守卫）、`:165`（空例外集），以及 `yate/flows/cmdline_completions.py:12-14`（三处 import）。该 rank 条目由 wave-3 的负向演练验证。

## 4. 架构影响

- R2 / `ALLOWED_PROTOCOLS`：`PaneRegistry` 白名单键基于路径（`tests/test_architecture.py:130`），因此 wave 2 必须把键从 `editor_components/editor.py` 移到 `editor_components/view.py`，否则 `test_no_new_protocols` 变红。
- R11 / `UI_FROZEN_FILES`：`tests/test_architecture.py:213` 与 `:225` 的两个允许集值是旧模块字符串；wave 2 必须把它们改为 `yate.editor_components.view`，否则 `test_collaborators_keep_widget_coupling_frozen` 变红。
- 层级 rank：`_LAYER_RANKS`（`:141-158`）基于前缀；wave 3 新增一个 L1 条目。`test_no_unregistered_upward_imports`、`test_flow_modules_hold_no_app_handle`（`:1306-1320`，已扫描顶层 `yate/*.py`）与 `test_no_relative_imports` 自动覆盖迁移后的根模块。
- R4（无 UI 的包/文件）：无变化；新根模块不 import `editor_components`。
- 命名守卫（`test_no_banned_identifier_names:869-878`）：扫描整棵树；wave 1 的负向演练证明新路径仍在覆盖范围内。
- 规则文本 wave-3 同步点：`architecture-boundaries.md` §一 L3 清单（`:25`）、L1 清单（`:31-37`）、R11 枚举（`:133`、`:139-142`）、§二 职责表（`:268`）、§三.6 纯计算清单（`:297`）、§六 R11 守卫清单（`:457`）；外加 `tests/test_architecture.py:25` docstring。
- 不新增 `Protocol`、`TYPE_CHECKING`、`Any`、`# type: ignore`、日志改动、主题改动、可滚动 widget 或新 widget id。

## 5. 波次

三个严格串行的波次（见 [overview.md](iktbxc-plans/overview.md)）：wave-1 [plan-a](iktbxc-plans/iktbxc-key-codec-plan-a.md)、wave-2 [plan-b](iktbxc-plans/iktbxc-view-plan-b.md)、wave-3 [plan-c](iktbxc-plans/iktbxc-cmdline-relocation-plan-c.md)。它们都涉及 `tests/test_architecture.py` 与 `.trae/rules/architecture-boundaries.md`，因此不能并行；每个波次以一次独立提交收尾，保留 `git mv` 重命名跟踪。

## 6. 验收

每波命令见各子计划。收尾门禁（仅主代理）：

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
.venv\Scripts\python.exe -m yate --help
```

残余 grep（预期 0 命中），范围 `yate/ tests/ tools/ pack/ pyproject.toml .trae/rules/ .trae/wikis/ README.md README.zh.md`：

```powershell
git grep -n -E "keyproto\.legacy|editor_components\.editor|flows\.cmdline_completions" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
git grep -n -E "keyproto/legacy|editor_components/editor|flows/cmdline_completions" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
```

豁免：`.trae/documents/**`（历史计划 + 本任务的 notes/plan）、`.trae/reviews/**`（只读事实记录）、`CHANGELOG*`、`tools/changelog/zh_overrides.json`。两个 README 文件在根树中只含裸文件名 `cmdline_completions.py`，迁移后即准确，因此不触发双语同步。

负向演练（每个改动的扫描路径守卫各一次，外加一次）：

1. wave-1 命名守卫：临时向新编解码器模块添加 `class RenameProbeController` → `test_no_banned_identifier_names` 必须失败 → 还原 → 转绿。
2. wave-2 R2 路径守卫：临时恢复旧的 `ALLOWED_PROTOCOLS` 键 → `test_no_new_protocols` 必须失败 → 还原 → 转绿。
3. wave-2 R11 冻结面：临时恢复一个旧的允许集值 → `test_collaborators_keep_widget_coupling_frozen` 必须失败 → 还原 → 转绿。
4. wave-3 层级 rank：临时移除新的 `_LAYER_RANKS` 条目 → `test_no_unregistered_upward_imports` 必须因两条向上边而失败 → 还原 → 转绿。

每次演练：每次编辑后核对磁盘上的文件内容，重跑前清理所涉包/测试目录的 `__pycache__`（既往会话中观察到 pyc 时序伪影），并以该文件的 `git status --short` 干净收尾。

## 7. 风险与回滚

| 风险 | 缓解措施 |
|---|---|
| 遗漏路径字符串 / docstring | 两次残余 grep + `git grep` 人工分诊（不做盲目全局替换）+ pyright + 全量 pytest |
| 路径改动后守卫变聋 | 四次负向演练，配还原并转绿 |
| `git mv` 重命名跟踪丢失 | 严格 `git mv`，每次提交后 `git log --follow -- <new path>` 抽查 |
| 插件 / 冒烟场景 import 旧路径 | 121 场景冒烟 + `python -m yate --help` |
| 规则/代码漂移 | `architecture-boundaries.md`、`tests/test_architecture.py`、`.trae/wikis/yate-architecture.md` 与根文档在代码同一波同步 |

回滚：三个独立提交，逐提交 `git revert`；worktree 沙箱隔离主仓。

## 8. 执行契约与偏离

- 无人值守：审批 bypass，子代理带 `bypassPermissions` spawn；收尾门禁不豁免。
- `subagent-workflow.md` §一.3 禁止子代理编辑产品源码（`yate/`）。三个波次全部由主代理在 `plan-executor` 脚本下执行，以本计划为唯一规范。评审步骤委托给 `code-review-expert`（bypassPermissions，按既往反馈在判死前给足完整窗口）。
- `plan-architect-designer` 被 spawn 两次（均带 `bypassPermissions`，按 `task-orchestration.md` §一.3 用模型 `Hy4 preview`）且两次失败，报 `Model "qwen-3.7-plus" not found`（定义文件的静态模型在本运行时未注册）。依据 `task-orchestration.md` §一.3.5 / §三，主代理亲自产出本计划——**规划角色子代理零产出**，此处作为事实记录。
- issue 主张差异（实测，见 inventory §G）：`:213/:225` 是允许集值而非键；P0-2 有 36 行而非 22 行且 `editor_compose.py` 无此引用；P0-1 的"9 处活跃引用"不含 109 行 `.trae`；`yate/docs` 0 命中；不存在 `FLOWS` 常量，也不存在 `test_banned_identifier_names`。执行依据实测清单，而非过时主张。
- 无新增行为测试：本任务不改变运行时行为；守卫覆盖由四次负向演练加完整 37 例架构套件证明。

## 9. 收尾回填（2026-11-07，主代理）

### 9.1 各波验收（真实结果）

| 波次 | pyright | 架构 | 聚焦 | 全量 pytest | 冒烟 | 残余 grep | 提交 |
|---|---|---|---|---|---|---|---|
| 1 | 0 errors | 37 点 / 退出 0 | 80 测试 / 退出 0 | 退出 0 | n/a | 0 命中（退出 1） | `3e615a9`（重命名 93%） |
| 2 | 0 errors | 37 点 / 退出 0 | 74 测试 / 退出 0 | 退出 0 | 121/121 · 1463/1463 / 退出 0 | 0 命中（退出 1） | `55aee7e`（重命名 100%） |
| 3 | 0 errors | 37 点 / 退出 0 | 4 文件 / 退出 0 | 退出 0 | 121/121 · 1463/1463 / 退出 0 | 0 命中（退出 1） | `f3299a1`（重命名 100%） |

负向演练：drill-1 命名守卫 红 退出 1 → 绿 退出 0；drill-2a `ALLOWED_PROTOCOLS` 红 1 → 绿 0；drill-2b `UI_FROZEN_FILES` 红 1 → 绿 0；drill-3 rank 红 1（观察到两条 `-> yate.registries` / `-> yate.session` 边）→ 绿 0。每次演练均核对磁盘还原 + `__pycache__` 清理。

两处执行异常，均已记录：

- wave-1 基线命令被 shell 包装器执行了两次；第二趟看到重命名后的中间状态（pytest 退出 4，`git mv` "bad source"）。变更前基线在干净的主仓重新实测：37 passed，退出 0。未影响任何产品改动。
- wave-3 applier 在第 17/22 次编辑处停止，因为 §二 表格短语用了行内反引号；前 16 次编辑已落盘。一个续接 applier 用同样的逐编辑唯一性断言应用了剩余 6 处；随后两种路径形式均 grep 干净。

### 9.2 评审与迭代

`code-review-expert`（`bypassPermissions`，DeepSeek-V4.1-Flash）在 [2026-11-07-iktbxc-naming-refactor.md](../reviews/2026-11-07-iktbxc-naming-refactor.md) 交付了 **0 阻塞项 / 1 严重 / 3 次要**（评审者无写工具；主代理逐字持久化记录并登记索引 #59，2026-11-07 pr-review 重编号为 #62）。M1（7 个一次性脚本）已移除，m2/m3 规则文本已澄清，m1 登记为延期；冒烟时序 flake 依据 `task-orchestration.md` §二.7 修复。迭代复验：pyright 0、架构 37、`--repeat 5 --jobs 4` 压力 12/12、全量冒烟 121/121 · 1463/1463。

### 9.3 偏离（附证据）

1. `cmdline_completions` 落在根级 L1（issue 第二建议目标），在 `_LAYER_RANKS` 中带 `("cmdline_completions.py", 1)`，而非 `services/` L0 —— drill-3 证明该 rank 条目承载关键（§3/C4）。
2. `tools/smoke_test/scenarios/stress.py` 收敛修复超出 issue §五 的 diff 范围，但 §二.7 要求在 `-n 1` / `--jobs 1` 复核后修复时序 flake；孤立在提交 `c9f5589` 中，从未混入三个实现提交（见 [iktbxc-review-fixes-plan.md](iktbxc-review-fixes-plan.md) §四）。
3. `plan-architect-designer` spawn 两次，均因模型未注册失败；主代理产出计划（§8，规划角色子代理零产出）。
4. 三个波次全部由主代理执行：`subagent-workflow.md` §一.3 禁止子代理编辑 `yate/`。
5. 无人值守 §二.5 记录：7 个未跟踪的一次性工具在删除清单落盘后删除（review fixes plan §三）：`.iktbxc_wave1.py`、`.iktbxc_wave2.py`、`.iktbxc_wave3.py`、`.iktbxc_wave3b.py`、`.iktbxc_drill1.py`、`.iktbxc_drill2.py`、`.iktbxc_drill3.py`。最终 `git status --short` 为空。

### 9.4 收尾门禁（主代理，除注明外均退出码 0）

| 命令 | 真实结果 |
|---|---|
| `pyright yate/ tests/ tools/ pack/` | `0 errors, 0 warnings, 0 informations`，退出 0 |
| `pytest tests/ -q -n auto` | 退出 0 |
| `pytest tests/test_architecture.py -q` | 37 点，退出 0 |
| `pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75` | `TOTAL 19392 / 1100 miss / 6190 branch / 573 partial = 93%`；`Required test coverage of 75% reached. Total coverage: 92.84%`；`3395 passed, 10 skipped in 165.91s`，退出 0 |
| `tools.smoke_test run --jobs 4` | `1463/1463 checks (100%)`，`121/121 scenarios passed 78.38s`，退出 0 |
| `python -m yate --help` | 退出 0 |
| 合并的残余 grep（点号形式 + 斜杠形式） | 0 命中，退出 1（预期为绿） |

### 9.5 最终提交（9 笔实现/评审提交 + 1 笔回填，无 `git push`）

`efd4551` issue notes → `6539b90` 参考清单 → `e7c2d67` 计划 + 子计划 → `3e615a9` wave-1 → `55aee7e` wave-2 → `f3299a1` wave-3 → `506b38c` 评审归档 → `adca72b` 评审修复计划 + 规则澄清 → `c9f5589` 冒烟 flake 修复。本次回填是收尾文档提交。

### 9.6 延期 / 范围外登记

- m1：三个提交正文为空；wave-1 的 docstring 改写记录在此处，而非重写历史。未来同类提交应加一行正文。
- 评审观察：R11 docstring/守卫枚举与 `UI_FROZEN_FILES` 10 键漂移（既有）；`key_codec.py` 首行仍含 "legacy" 一词（按 §一 P0-1 语义正确）；未对 2026-11-02 包级重命名做完整 `--follow` 考古。
- P2-4（editor_sprites characters/chars）与 P2-5（palette 一词三义）按 issue 仍为独立评审主题。

### 9.7 分支 / worktree 重命名（2026-11-07 后续）

用户更正：issue id 不得用作分支名；分支需要有意义的名称。原 issue-id 分支通过 `git branch -m` 重命名为 `ref/naming-hygiene`，worktree 目录改为 `yate-naming-hygiene`。

`git worktree move` 在 Windows 上两次失败，报 `Permission denied`（旧目录被另一进程占用；孤儿 pytest worker PID 14680 被终止但未释放句柄）。依据无人值守 §二.5，旧未跟踪 worktree 的移除在执行前已记入记忆，随后 `git worktree remove --force` 加 `git worktree add ... ref/naming-hygiene` 在 `80ad791` 重建 worktree。全部 10 笔提交都在分支上；被忽略的 `.venv` 从头重建。已验证：注册表键 `yate-naming-hygiene`，无 issue-id 分支残留，旧目录不存在，venv 含 0 个旧路径字符串，`yate.__file__` 解析到新 worktree 内，`git status --short` 为空。

旧名称的 9 处仓内引用均在本提交同步（issue notes、主计划、参考清单、评审记录元数据、评审索引）；评审结论与实测数字未变。旧名称的全仓 grep（含 `.trae/documents` 与 `.trae/reviews`）现为 0 命中。

主代理在新 worktree 重跑收尾门禁（均退出 0）：pyright `0 errors, 0 warnings`；`pytest -q -n auto` 0；架构 37 点 0；覆盖率 `TOTAL 19392/1101/6190/574 = 93%`、`Total coverage: 92.83%`、`3395 passed, 10 skipped`，0；冒烟 `1463/1463 checks`、`121/121 scenarios`，0；`python -m yate --help` 0；源面残余 grep 0 命中（退出 1）；旧名称 grep 0 命中（退出 1）；`git status --short` 为空。分支现含 12 笔提交（10 笔原始 + `f0f0997` 名称同步 + 本次回填）。无 push。

### 9.8 合并就绪 PR 评审（2026-11-07，已关闭）

`pr-review` skill，`review` 模式：3 名只读评审者（A 功能/架构、B 文档/合并面、C 安全/性能/门禁范围）加主代理裁决与亲自跑门禁。基线判定 A `APPROVE` / B `BLOCKED` / C `REQUEST_CHANGES`；裁决为 **0 阻塞项 / 3 严重 / 9 次要**：索引 #59 与 master #59-#61 冲突并存在真实三方合并冲突，新文档中三处盘符路径，以及一处被扭曲的首轮评审范围/结论。3 个严重项全部关闭；6 个次要项修复，3 个延期（分支命名漂移、`iktbxc-*` 文档词干、丢弃的 `wait_until` 返回值）。最终判定 **APPROVE**。报告：[2026-11-07-pr-review-naming-hygiene.md](../reviews/2026-11-07-pr-review-naming-hygiene.md)；迭代计划：[naming-hygiene-pr-review-plan.md](naming-hygiene-pr-review-plan.md)。

修复后主代理门禁（均退出 0）：pyright `0 errors, 0 warnings`；`pytest tests/ -q -n auto` 0；架构 `37 dots` 0；覆盖率 `92.88%`（`3395 passed, 10 skipped`，达到 `--cov-fail-under=75`）；冒烟 `121/121 scenarios · 1463/1463 checks`（95.16s）0；changelog check 0；`python -m yate --help` 0；`git diff --check` 0；源面残余 grep 0 命中（退出 1）；盘符扫描 0 命中；旧分支/worktree 名称 grep 0 命中（退出 1）；`git merge-tree 3e92532 master HEAD` 0 冲突标记；`git status --short` 为空。评审索引：首轮评审 #62，pr-review #63。无 push。
