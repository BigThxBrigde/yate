# IKTRDV / pack-dist-zip 任务进度状态（落盘事实，失败续作唯一依据）

本文件是无人值守任务的进度记录：任何步骤失败/中断，先更新本文件（已完成步骤、
关键结论、下一步动作、失败与重试记录）再继续，禁止凭记忆重建事实。
任务名 `pack-dist-zip`；issue 素材见 `pack-dist-zip-issue.md`；主计划见
`pack-dist-zip-plan.md`；子计划总纲见 `pack-dist-zip-plans/overview.md`。

## 环境与基线（【领会】实测）

- 主仓 `master` HEAD `b982c06`，`origin/master` 同为 `b982c06`，工作树干净。
- 分支 `feature/feat-pack-dist-zip`（parent `master`，语义化命名，符合
  `task-orchestration.md` §二.1 / `doc-conventions.md` §七）；worktree 目录名
  `yate-pack-dist-zip`（仓库同级），`git worktree list` 已登记。
- worktree 内独立 `.venv` 已重建（`pip install -e ".[dev]"`），
  `.venv\Scripts\python.exe -c "import yate; print(yate.__file__)"` 实测指向
  该 worktree 的 `yate/__init__.py`。
- `.trae/rules/` 8 份必读规则已全文加载；子代理定义以
  `.trae/agents/` 为准；模型按 `task-orchestration.md` §一.3 主代理来源表格。
- 用户指令：无人值守、不询问、失败先更新状态再续作、严格按纪律。
- 【领会】产物已单独提交 `a204f14 docs(plan): collect IKTRDV issue material and task progress record`。

## 步骤状态

| # | 步骤 | 状态 | 产物 / 实测 |
| --- | --- | --- | --- |
| 1 | 【领会】环境与情报准备 | 完成 | `pack-dist-zip-issue.md` + 本文件；venv 自证通过；提交 `a204f14` |
| 2 | 【方案】调研取证并落盘方案 | 完成（主代理兜底，子代理零产出） | `pack-dist-zip-plan.md` + `pack-dist-zip-plans/overview.md` + 7 个子计划 a-g，含目标/非目标、5 个备选与否决理由、波次表、每步验收命令、风险与回滚、Mermaid 图 |
| 3 | 【批准】无人值守按通过处理 | 完成 | 本文件「批准结论」章节；单独提交一笔 |
| 4 | 【执行】按波次实施 | 完成 | wave-1 `78354c9` / wave-2 `0d239f1` / wave-3 `a6b5bed` / wave-4 三次真实构建全部 exit 0，实测见「波次执行实测」 |
| 5 | 【审核】code-review-expert 评审 + 迭代 | 完成（两轮，major 归零） | 第一轮 0 blocker / 3 major / 7 minor → 修复 `4f11dd1d` → 第二轮 0 blocker / 0 major / 5 minor；记录 `.trae/reviews/2026-11-10-pack-dist-zip.md` 含两轮章节 |
| 6 | 【收尾】主代理全量门禁 + 回填 + 逐步提交 | 完成 | 六项门禁 `GATE_RCS [0,0,0,0,0,0]`；索引 #70 登记；本文件与主计划/总纲回填 |

## 批准结论（【批准】）

- 用户无人值守指令「所有问题无须过问」→ `plan-before-execute.md` §二.3 /
  `task-orchestration.md` §二.3 的「用户批准」按通过处理，不向用户发起询问；
  本条记录的是**豁免询问**，不以「自我判定方案显然可行」冒充用户答复。
- 批准范围：`pack-dist-zip-plan.md` 全文 +
  `pack-dist-zip-plans/overview.md` 的 4 个波次与 7 个子计划；执行中任何
  阈值 / 范围 / 选型偏离须当轮回填 `overview.md` §六并附实测依据。
- 生效时点：本笔提交之后进入【执行】wave-1。

## 关键结论

- 本任务为「新任务」关键字触发的非平凡任务，`task-orchestration.md` §二闭环是
  唯一执行路径；预计改动 ≥3 文件，已按剧本拆子计划并定制 4 个波次。
- 方案选型：共享 Python 助手 `tools/pack/zip_dist.py`（stdlib zipfile，
  `external_attr` 显式写 Unix mode、临时文件 + `os.replace` 原子替换、
  `SHA256SUMS.txt` 同名条目 upsert），三脚本在冒烟成功后统一以
  `-m tools.pack.zip_dist` 调用；否决 `Compress-Archive` 分叉（2GB 上限、
  跨平台分叉）、系统 `zip` 依赖、`tools.pack` 新子命令、双向开关。
- 范围裁定：本轮同步 README + 应用内双语手册（manual.en/zh.md 已明文描述
  `--dist` 现状，不改即文档谎言）；不动 PyInstaller spec、CI、release 工具。
- 偏离登记：本机 Windows，Linux 真实构建不纳入（由助手 `posix=True` 单测 +
  sh 静态守卫 + `python -m zipfile -t` 等价覆盖）；Windows 真实构建在 wave-4，
  失败按 `pack-dist-zip-e2e-plan-g.md` §5 降级并如实记录。
- 收尾门禁五项（pyright / pytest -n auto / 架构 37 用例 / 覆盖率
  `--cov-fail-under=75` / 冒烟 `--jobs 4`）由主代理亲自跑，记录退出码；
  改 README 追加 `python -m tools.changelog check`。

## 失败与重试记录

- 【方案】`plan-architect-designer` 首次 spawn 返回
  `Model "qwen-3.7-plus" not found`（角色 frontmatter 模型在 CodeBuddy 插件
  运行时未注册）。按 §一.3.5 未改定义文件，改在任务书中指定表格模型
  `Hy4 preview` 并变更配置（`max_turns` 60）重试一次，仍返回同一错误，
  零落盘产物。按 §三 判定子代理零产出，由主代理亲自按剧本调研 + 落盘全部
  方案文档；已在 `pack-dist-zip-plans/overview.md` §六登记偏离。
- 【执行】wave-2 主代理复核时，一条包含 `where.exe` / `cmd /c` / Git Bash 可执行文件绝对路径引用 的
  长串验收命令整体报「系统找不到指定的路径」(exit 1)，随后同样形态的诊断命令因
  「Awaiting user approval timed out」被取消。按用户「失败重新更新状态继续执行」
  要求，本条先落盘，再改用短命令逐条执行（PowerShell 内置 `Get-Command` /
  `Test-Path` 定位解释器、每条命令单独记录退出码），不重复原失败形态。
- 复核发现 wave-2 bat 执行者把既有头注释示例 `--onefile --dist release` 改写为
  `--dist release`（计划外改动，plan-e §3 只要求追加），主代理将恢复原行并保留
  新增说明，登记为执行偏离。
- 【执行】wave-4 构建 1 首次尝试 `& .\pack\pack.ps1 -SkipChangelog --dist release`
  报 `A positional parameter cannot be found that accepts argument 'release'`
  （`--dist` 形态在当前 PowerShell 会话直接调用时未绑定为 `-Dist`），未产生
  构建产物。按用户要求先落盘，再用 `-Dist` / `-Help` 探针定位绑定差异；bat
  路径因 `--dist` → `-Dist` 显式映射不受影响，E2E 将优先用 bat 覆盖 `--dist`。
- 其它步骤暂无失败。

## 波次执行实测

- wave-1（提交 `78354c9`）：`plan-executor` 落盘共享助手与 12 个单测；主代理
  独立复核 `pytest tests/test_pack_zip.py -q` = 12 passed、`pyright` = 0、
  架构 37 passed、`test_pack_spec.py` 24 passed，四条 exit 0。
- wave-2（本笔提交）：三个 `plan-executor` 并行落盘 ps1 / sh / bat；主代理复核
  `git diff` 三文件 +21/+16/+5 行，全部只改独占文件；ps1 `-Help` 与
  `-NoZip -Help` exit 0 且输出含 `-NoZip` / `--no-zip` / `by default`；
  bat `--help` 与 `--no-zip --help` exit 0；`bash pack/pack.sh -h` exit 0 且
  含新开关与默认说明；`bash pack/pack.sh --zip` exit 2 且 stderr 含
  `unknown argument: --zip`；`pytest tests/test_pack_spec.py -q` = 24 passed；
  全量 `pyright yate/ tests/ tools/ pack/` = 0 errors。
- 偏离：bat 执行者曾把既有 `--onefile --dist release` 示例改写为
  `--dist release`（计划外），主代理已恢复原行并保留新增说明；主代理 shell 下
  `powershell -File ...` 触发审批超时、`cmd /c "..."` 引号写法报路径错误，
  改用当前会话直接调用脚本 / 正确引号后全部通过，详见「失败与重试记录」。

- wave-3（本笔提交）：两个 `plan-executor` 并行落盘 8 条静态守卫
  （`tests/test_pack_spec.py` +248 行）与四份双语文档（+65 行）。守卫实现两处
  与真实脚本形态对齐、未削弱覆盖：用例 5 用锚定整行的 `^\s+\*\)\s*$` 定位
  catch-all 分支（裸 `index("*)")` 会先命中 `--dist=*)`）；用例 8 把「无第三方
  依赖」落实为显式 stdlib 根模块白名单断言。主代理复核
  `pytest tests/test_pack_spec.py tests/test_pack_zip.py -q` = 44 passed、
  架构 37 passed、全量 pyright 0 errors、`tools.changelog check` exit 0
  （既有 unreleased lag / missing zh 提示属存量状态，不影响退出码）；
  四份文档 diff 双语逐项对齐、无本机绝对路径、保留 `build,ts,lua` 字样。
  负向演练留待 wave-4 执行（实测结果见下文），本处不重复陈述。

- wave-4（本笔提交）：主代理真实 Windows PyInstaller 构建三次，全部 exit 0：
  ① `pack.bat --skip-changelog --dist release`（one-folder）→
  `Collected -> .../yate-0.2.18-windows-x64 (69.3 MB)` +
  `ZIP -> ...zip (22.4 MB)` + SHA256 输出；
  ② `pack.ps1 -SkipChangelog -OneFile -Dist release`（onefile）→
  同名 zip 被覆盖（hash `01f9ab9a…` → `a87e74ca…`），校验文件仍单行；
  ③ `pack.ps1 -SkipChangelog -NoZip -Dist release` →
  `Collected ->` 与 `ZIP skipped (-NoZip)`，zip 字节与校验文件逐字节不变、
  stage 保留且内部 `SHA256SUMS.txt` 随本次构建更新。
  校验：一次性 Python 探针比对 zip 364 个文件与 stage 逐字节相等、顶层
  `<stage>/` 保留、无 `smoke-out.txt` / `.tmp`；`python -m zipfile -t` =
  `Done testing`；`Expand-Archive` 解压成功且 `SHA256SUMS.txt` 存在；
  `Get-FileHash` 与校验条目一致；解压后 `yate.exe --version` = 0.2.18
  （exit 0）。负向演练：临时把 sh 的 `2,21p` 改回 `2,19p`，
  `test_help_text_when_scripts_scanned_covers_new_switch` 变红（RC 1），
  字节级还原成功。一次性探针与 TEMP 解压目录均已清理。
- 偏离（详见 `pack-dist-zip-plans/overview.md` §六）：dist 目录用已被
  `.gitignore` 忽略的 `release` 替代计划里的 `release-e2e`；ps1 直接调用
  `--dist release` 在 PowerShell 命令模式是参数终止符形态、绑定失败
  （既有行为，非本任务引入），改由 bat 显式映射与 `-Dist` 形态覆盖；
  Linux 真实构建不纳入（主计划 §7 已登记等价覆盖）。

## 评审第一轮结论与迭代

- 第一轮 `code-review-expert` 实测六项门禁全 0（pyright 0 / pytest -n auto /
  架构 37 / 覆盖率 93% / 冒烟 1464/1464 / changelog check 0），
  结论 blocker 0 / **major 3** / minor 7；评审记录已落盘并双向互链。
- major：M1（README 双语 ps1 示例 `--dist` 在 PowerShell 命令模式不可执行）、
  M2（ps1 `.EXAMPLE` 同样不可执行）、M3（`_checksum_text` 的 ascii 解码遇
  非 ASCII 校验行硬失败）。主代理已独立复核：`-dist` 绑定成功、
  `--dist` 失败、非 ASCII 行抛 `UnicodeDecodeError`。
- 按 §二.6 回到步骤 2 产出 `pack-dist-zip-review-fixes-plan.md`；裁定
  文档纠偏为 `-Dist` 形态（否决改 ps1 参数面）、M3 改字节级 upsert；
  顺带闭环 m2/m3/m4/m5/m6，m1/m7 与存量 flake 登记待办。

- 迭代修复（提交 `4f11dd1d`）：R1-a / R1-b 两个 `plan-executor` 并行落盘
  8 个文件；主代理复核 46 passed / pyright 0 / 架构 37 / 非 ASCII 探针
  保留字节 exit 0 / `-NoZip -Dist release -Help` exit 0 / changelog check 0。
  方案 §8、总纲 §六（新增退出码列）、进度文档均已回填。

## 收尾实测（2026-11-10）

- 第二轮评审：blocker 0 / major 0 / minor 5（评审记录 §七），迭代终点达成。
- 主代理全量门禁（并行口径）：pyright 0（0 errors）；`pytest -n auto` exit 0；
  架构 37；覆盖率 `--cov-fail-under=75` 实测 92.96%（3495 passed /
  10 skipped）；冒烟 121/121 scenarios、1464/1464 checks；changelog check 0。
  `GATE_RCS [0,0,0,0,0,0]`、`ALL_ZERO True`。
- 评审索引已登记 #70；主计划 §9、总纲 §六、修复方案 §8、评审记录两轮章节
  均已回填；一次性门禁/探针脚本已删除。
- 遗留 minor 待办（不阻塞）：m1 / m7、第二轮 N1 存量 `test_app_panes`
  确定性竞态（另案，不记「偶发」）、N2 / N3 / N4 / N5；详见主计划 §9。
- E2E 产物 `release/` / `dist/` / `build/` 为 `.gitignore` 忽略项，按 git
  安全协议保留未删；未推送、未合流、工作树干净。

## 下一步动作

无（合并前 pr-review 已完成，结论 APPROVE）；推送 / 合入 master 仍须用户显式要求。

## 合并前 pr-review 轮（2026-11-10，完成）

- 范围 `master...HEAD`（25 文件 +2846/−8），merge-base `b982c06`；master 已推进
  到 `18e96d2a`（合入 IKTPC2 LSP hover docs + `chore(changelog)`），架构守卫
  37→38。
- 失败与续作（用户无人值守「失败先更新状态继续执行」）：3 名只读审查员并行，
  分域 A 交付「1 MAJOR（`--stage .` / `..` 产生 `/` / `../` arcname 与越界
  rglob）+ 5 MINOR」；分域 B / C 均 `code=10003 aborted` 零产出，按
  `subagent-workflow.md` §五.4 不原样重试，主代理亲自按 skill 六维度兜底并
  如实标注。首条 `$(...)` bash 语法在 PowerShell 失效、merge-tree 探针 GBK
  解码失败，均已改用三点语法 / `errors="replace"` 后重跑成功。
- 已取证：评审索引本分支登记 #70 与 master #70/#71/#72 重复；
  `git merge-tree` 唯一冲突块在 `.trae/reviews/README.md`；`manual.en/zh`
  双方 hunk 不重叠可自动合并；`tools.changelog check` 分支侧 exit 0。
- 七道门禁首轮：pyright 0 / pytest `-n auto` 0 / 架构 37 / 覆盖率 **RC=1**
  （`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] count=18852 threshold=9999`，
  本机 %TEMP% 积压触发 safe-delete 钩子杀 pytest 收尾清理，属环境钩子而非产品
  缺陷）/ 冒烟 121/121·1464 / changelog 0 / diffcheck 0。
- 修复波 `6f842d34`：P1-a 净化 stage 名 / 越界与 symlink 收口 + 3 个回归
  用例；P1-b 评审索引顺延 #73 并移出冲突 hunk；提交态 `git merge-tree`
  实测 `CONFLICT_MARKERS 0`、`IDX_70 0` / `IDX_73 1`。覆盖率首轮红经
  `-n 1` 复核为 safe-delete 环境钩子（`count=18852 > 9999`），非产品缺陷。
- 修复后七道门禁 `GATE_RCS [0,0,0,0,0,0,0]`：pyright 0 / pytest `-n auto` 0 /
  架构 37 / 覆盖率 92.95%·3498 passed·10 skipped / 冒烟 121/121·1464 /
  changelog 0 / diffcheck 0。
- 评审记录 `.trae/reviews/2026-11-10-pr-review-feature-feat-pack-dist-zip.md`
  给出 **APPROVE**（0 BLOCKER / 0 MAJOR / 7 MINOR 待办），索引 #74 已登记；
  合并时需在合并树上重跑门禁（master 架构守卫 38）并确认 changelog。
- 复核口径订正（无人值守「失败先落盘状态继续执行」）：追加索引 #74 段后
  裸冲突标记计数从 0 变 1，经精确判据复核为**探针误报**——新评审记录正文
  引用了冲突起始标记文本，被裸计数误计；真实冲突块（起始 `.our` / 结束
  `.their` 标记）实测均为 0，`CHANGED_IN_BOTH 3` 但无冲突块，合并阻碍仍归零。
  同期新评审记录残留 1 处本机工具路径已按 §五 脱敏。口径说明已写入评审
  记录 §二与修复方案 §7。
- 最终提交态复核：精确冲突块 0 / 索引 #73、#74 各 1 次 / diffcheck 0 /
  工作树干净。
- 下一步：无（本轮闭环，APPROVE）；推送 / 合入 master 由用户显式要求后进行。

## 全量 minor 修复轮（2026-11-11，进行中）

- 用户指令：「更新记忆，fix 所有的isuee」；无人值守上下文延续，不询问、审批
  按通过处理、失败先落盘状态再续作。
- 起点实测：分支 `feature/feat-pack-dist-zip` HEAD `a8db1324`（16 笔提交），
  master `18e96d2a`，merge-base `b982c06`，工作树干净，`.trae/rules/` 未被
  本分支改动；8 份必读规则本会话已全文加载。
- issue 素材已落盘 `pack-dist-zip-minor-fixes-issue.md`：去重 **16 条**
  （PR §四 7 条 + §九 2 条、R2 的 N1–N5、R1 的 m1/m7、合并时流程项 2 条），
  逐条给来源、位置、修复路径与可实测判据。
- 【方案】已落盘：`pack-dist-zip-minor-fixes-plan.md` +
  `pack-dist-zip-minor-fixes-plans/overview.md` + 5 个子计划 a–e，含 16 条
  裁定、备选否决、Mermaid、波次表、逐波验收命令与风险回滚。
  `plan-architect-designer` 未派发（模型 `qwen-3.7-plus` 在本运行时未注册，
  前轮已两次失败），按 §三 主代理亲自按剧本产出，如实标注「子代理零产出」。
- 【批准】无人值守按通过处理（用户「所有问题无须过问」）：豁免询问与审批，
  不冒充用户答复；批准范围为主计划 + 总纲的 4 个 wave 与 5 个子计划，
  执行中偏离须当轮回填 `overview.md` §六并附实测依据。
- wave-1 复核（主代理）：三个子代理均有落盘产出，8 个文件 +255/−37；
  前 5 条验收命令 RC=0（`test_pack_zip.py` + `test_pack_spec.py` 合计
  58 passed、pyright 0、架构 37、diffcheck 0、changelog 0）。验证脚本在
  打印 bat 中文帮助输出时因 GBK 编码崩溃（脚本自身问题、非产品失败），
  第 7 条 sh `-h` 未跑到 → 修脚本打印编码后重跑。
- 复核发现 2 个新缺陷（须当轮修，不得静默带入 wave-2）：
  ① `tests/test_pack_zip.py:355` 使用 `# type: ignore[arg-type]`
  （违反 python-coding-style「不得用 type ignore 掩盖问题」）→ 改正确签名；
  ② F6 事务在「旧 zip 移到备份后、新 zip 首次 `os.replace` 失败」时会丢
  旧 zip（异常只覆盖第二次 replace）→ 改复制式备份 + 整个 swap 块异常回滚。
- 复核失败与续作（无人值守「失败先落盘状态继续执行」）：修好验证脚本后
  七条命令跑完，`WAVE1_RCS [1,0,0,0,0,0,0]` —— 唯一红项是
  `test_zip_helper_when_scanned_keeps_atomic_replace_and_unix_mode:948`
  （静态守卫的 stdlib import 根白名单未含新增的 `shutil`），pyright 0 /
  架构 37 / diffcheck 0 / changelog 0 / bat `--help` 0 / sh `-h` 0 均绿。
  下一步把 `shutil` 补入白名单（stdlib、无第三方依赖）并重跑，不得删断言。
- wave-1 复核最终实测：`WAVE1_RCS [0,0,0,0,0,0,0]`（59 passed / pyright 0 /
  架构 37 / diffcheck 0 / changelog 0 / bat `--help` 0 / sh `-h` 0）；
  负向演练 `NEGATIVE_RCS {'help_stale_range': 1, 'bat_no_notice': 1}`、
  `RESTORED True`、`GUARDS_CATCH True`（补做 plan-b 未执行的推荐项）。
- **并发会话事实登记**：核对 `git status` 时发现同 worktree 另有并行会话提交
  `1472c10b fix(pack): harden zip helper and pin archive order in fix-all wave 1`
  与 `f9a0cd4d fix(panes): tolerate late focus events for closed leaves`，
  HEAD 已推进到 `f9a0cd4d`；README 双语 / bat / sh / 偏离表 F10 等 wave-1
  产物与 F16 已落盘提交。主代理本轮的复核修正（F6 复制式备份 + 全 swap
  回滚、去 `# type: ignore`、白名单补 `shutil`、F12 守卫、负向演练脚本、
  偏离登记）仍以未提交增量形式在工作树，按「只认落盘结果」以当前 HEAD
  为事实基线继续，不重复报已提交产物、不覆盖并行会话的提交。
- wave-2 实测：`WAVE2_RCS [0,0,0,0,0,0,0]`（F16 四次
  `pytest tests/test_app_panes.py -q -n 1` 连续全 0、pyright 0、架构 37、
  全量 pytest `-n auto` 0）；本轮复核修正已提交 `44bd6c0e`。
- **wave-3 前置记录（git 安全协议）**：即将创建隔离临时 worktree
  `../yate-pack-dist-zip-merge-check`（detached HEAD，仓库同级）并在其中
  `git merge --no-edit master` 做合并模拟；不推送、不合流、不改主分支。
  验证完成后将 `git worktree remove` 删除该 worktree 及其合并提交，
  收尾汇报显式列出该删除动作；主 worktree 的 `git status --short` 须为空。
- wave-3 合并模拟实测（临时 worktree `../yate-pack-dist-zip-merge-check`，
  合并提交 `b8dddf0d`，0 冲突）：`MERGE_TREE_RCS [0,0,1,2]` ——
  架构守卫 **38 passed** ✓、合并树全量 `pytest -n 1` ✓（F14 实测达标）、
  `tools.changelog check` **RC=1**（合并树红门禁，需诊断根因）、
  `git diff --check master...HEAD` **RC=2**（本轮子计划文档尾随空白，
  `pack-dist-zip-guards-scripts-plan-b.md:32`）。按无人值守要求先落盘，
  下一步取完整错误输出：diffcheck 尾随空白必须在本分支修掉；changelog
  红项按历史 IKTPC2 pr-review 同类项诊断，若属发布流程交互则如实登记为
  合并时人工处置、不擅自改 CHANGELOG。
- wave-3 最终实测（临时 worktree 基于 `decdd769` 重建合并树，0 冲突）：
  `MERGE_TREE_RCS [0,0,1,0]`——架构 **38 passed** ✓、合并树全量
  `pytest -q -n 1` ✓、diffcheck **0** ✓（尾随空格修复生效）；
  仅 `tools.changelog check` RC=1。
- F15 根因与处置路径（已实测）：master 侧同命令 RC=0（
  "released changelog sections are up to date"），合并树报
  "stale changelog files → run generate"，是合并提交重算 v0.2.18
  已发布段的发布流程交互（历史 IKTPC2 pr-review 同类项），非本分支
  代码缺陷、PR diff 不含 CHANGELOG。在隔离合并树运行
  `python -m tools.changelog generate`（RC=0，写 4 个 changelog）后
  `check` **转绿 RC=0**。按非目标不改本分支 CHANGELOG，登记为合并时
  人工处置项并给出已验证命令；不冒充已修复、不记「偶发」。
- 清理（git 安全协议）：按前置记录用 `git worktree remove --force`
  删除临时 worktree 与其合并提交及 generate 产生的未提交改动，
  `git worktree list` 复核；一次性验证脚本 4 个已删除。
- 【审核】第一轮 `code-review-expert` 已落盘
  `.trae/reviews/2026-11-11-fix-all-minor-review.md`（196 行）：
  blocker 0 / **major 1** / minor 6；八项门禁全绿（pyright 0、
  pytest 3519 tests、架构 37、覆盖率 93.02%、冒烟 121/121·1464、
  changelog 0、diffcheck 0、`test_app_panes -n 1` 四连 0）；16 条中
  14 条已闭环、F5 未闭环、F15 判定为合并时人工处置（处置路径充分）。
  M1：锁创建后 `try` 起点过晚，空 stage / `_stage_files` 越界拒绝 /
  `mkstemp` 失败三条路径残留 `.lock`，`O_EXCL` 使重试永久失败；
  评审实测复现并判为本轮 F5 引入的回归。minor 6 条（m1 回滚二次失败、
  m2 F12 守卫顺序、m3 symlink 用例为 monkeypatch、m4 F16 守卫
  `stale_ids` 未断言非空、m5 跨 stage 并发、m6 陈旧锁无自愈）。
- 按 §二.6「存在 major → 回到步骤 2 重新设计」：本轮进入迭代轮，
  产出修复方案 → 无人值守批准 → 修 M1（调 `try` 起点 + 补 3 条
  「失败后无锁残留」断言）与评审建议同批的 m2 / m4 → 复评至
  0 blocker / 0 major →【收尾】全量门禁 + 回填 + 记忆更新。
- 【迭代·方案】已落盘 `pack-dist-zip-minor-fixes-review-iteration-plan.md`：
  裁定 A（锁创建成功后立即进入大 `try`，三个临时 Path 改可选并判空清理），
  否决 B（校验移到锁外，`mkstemp` 仍漏）/ C（多一个易错标志位 + 误转异常）；
  R1 修 M1 + m2/m4 + 3 条「失败后无锁残留」用例，m1/m3/m5/m6 登记待办；
  评审记录已双向互链。
- 【迭代·批准】无人值守按通过处理，豁免询问与审批，不冒充用户答复；
  范围为本方案 R1/R2，执行中偏离须回填 `overview.md` §六。
- 下一步：执行 R1 修复 → 局部验收 → 第二轮 `code-review-expert` 复核 →
  【收尾】全量门禁 + 回填 + 提交 + 记忆更新。

## 续作会话独立复核（2026-11-10，完成）

- 另一无人值守会话在闭环后重新派 2 名只读分域审查员（均交付完整报告），
  主代理逐条回读定级；新证据补记在评审记录 §九。
- 独立探针：`Path(".")` / `Path("..")` / `<stage>/..` 三种畸形 stage 名均抛
  `ZipDistError` 且无 zip / tmp 产物；真实 symlink 指向 stage 外文件不进入
  归档；正常归档顶层前缀与无临时残留均复验通过。
- 本会话亲跑八项门禁 `GATE_RCS [0,0,0,0,0,0,0,0]`（覆盖率 92.95%·
  3498 passed·10 skipped / 架构 37 / 冒烟 121/121·1464 / changelog 0 /
  diffcheck 双 0）；覆盖率 `-n auto` 本轮直接为 0，前轮 safe-delete 钩子
  拦截未复现，两轮事实并列登记、不互相覆盖。
- 新登记 minor 2 条（两次 replace 间失败、dist-root 落在 stage 内），按
  skill Step 5 撤回前轮已删除的重复 stat 误报 1 条；APPROVE 维持，
  minor 待办 7 → 9。
- 提交态复核：工作树干净；merge-tree 精确冲突块 0；未推送、未合流。
- 下一步：无（闭环完成，待用户显式要求推送 / 合入）。
