Overall: APPROVE（AI 预评审，合入决定仍由人类作出；0 BLOCKER / 0 MAJOR，MAJOR 当轮修复并复验，仅 minor 待办）

# IKTRDV 合并前 PR 级预评审记录

> 模式：`pr-review` skill `review`（默认），范围 `git diff master...HEAD`。
> 基线：merge-base `b982c06`；评审时 `master` 已推进到 `18e96d2a`（合入 IKTPC2
> LSP hover docs + `chore(changelog)`，架构守卫 37→38）。
> 分支：`feature/feat-pack-dist-zip`，11 笔提交（`a204f145`..`24311713`）+
> 修复波 `6f842d34`，未推送、未合流。
> 修复方案双向互链：[pack-dist-zip-pr-review-fixes-plan.md](../documents/pack-dist-zip-pr-review-fixes-plan.md)；
> 前两轮分支评审：[2026-11-10-pack-dist-zip.md](2026-11-10-pack-dist-zip.md)。

## 一、范围与噪声过滤（skill Step 1）

- `git diff --stat master...HEAD`：25 文件、+2846 / −8（含修复波后 +3057 / −36）。
  代码面：`tools/pack/zip_dist.py`（新、220 行）、`tools/pack/__init__.py`、
  `pack/pack.ps1` / `pack.sh` / `pack.bat`、`tests/test_pack_zip.py`（新、232 行）、
  `tests/test_pack_spec.py`（+249）；文档面：12 份 `.trae/documents/pack-dist-zip*`
  计划/素材/进度、1 份评审记录 + 索引、README/README.zh、manual.en/zh。
- 噪声过滤：`*.spec`、二进制资产、`*.pyc` / 锁文件、`.venv/`、纯格式化 hunk
  一律跳过并在此说明一次；本分支未改动 PyInstaller spec，无此类噪声。
- 基线漂移（PR 级重点）：master 侧新增 `tests/test_architecture.py` 的 hover key
  guard（37→38）、评审索引 #70–#72、`manual.en/zh` 的 F7 hover 章节、
  CHANGELOG 与 FEATURES 更新；本分支基于 `b982c06`，两者 merge-base 未变。

## 二、执行方式与子代理状态（如实登记）

- 3 名只读分域审查员并行下发（`subagent-workflow.md` §五、批大小 3）：
  **分域 A**（功能正确性 / 安全 / 边界）交付 1 MAJOR + 5 MINOR；
  **分域 B**（性能 / 可维护性 / 架构）与 **分域 C**（基线漂移 / 文档 / 提交规范）
  均 `Subagent execution failed (code=10003): aborted`、零落盘产物。按
  §五.4 不原样重试、不"救活"式重建，由主代理亲自按 skill 六维度兜底并逐条
  回读复核分域 A 的发现（本记录 §三、§四）。
- 只读探针的失败与修正（无人值守「失败先落盘状态再续作」）：
  ① `$(git merge-base ...)` 是 bash 语法、在 PowerShell 失效 → 改用三点语法
  `git diff master...HEAD`；
  ② `git merge-tree --write-tree` 在旧版 Git 不支持 → 传统三参数 `merge-tree`；
  ③ merge-tree 输出含非 GBK 字节致 `UnicodeDecodeError` →
  `decode("utf-8", errors="replace")`；
  ④ P1-b 的提交态探针看不到未提交工作区改动 → 临时 `GIT_INDEX_FILE` +
  `write-tree` 的 tree 级探测，主代理在提交 `6f842d34` 后用提交态
  `merge-tree` 独立复核（§五）；
  ⑤ 收尾复核的裸冲突起始标记计数一度报 1，实为本记录正文引用该标记文本
  造成误计；改用精确冲突块标记（起始 `.our` / 结束 `.their`）计数复核得 0，
  非真实冲突回归。本记录所有 `CONFLICT_MARKERS` 均指精确冲突块计数。
- 修复波两子计划 P1-a / P1-b 由 `plan-executor` 并行执行、文件不重叠；
  主代理独立重跑其验收命令（49 passed / pyright 0 / 架构 37）。

## 三、六维度结论（review 模式）

| 维度 | 结论 | 证据 |
| --- | --- | --- |
| 1 功能正确性 | MAJOR 1 条（已修）+ MINOR 2 条 | `--stage .` / `..` 使 arcname 变 `/` / `../` 且 `rglob` 越界；修复见 §四 M1。upsert 精确匹配、原子替换、CLI 0/1/2、三脚本失败传播、`--no-zip` 跳过语义逐项回读无新增发现 |
| 2 安全 | MAJOR 1 条（即 M1）+ MINOR 1 条（symlink） | 无 `subprocess` / `shell=True` / `Invoke-Expression` / 硬编码密钥 / `pickle` / `eval`；ps1/sh/bat 均为参数数组或重引号形态；`mkstemp` 为 `O_EXCL` 随机名；路径遍历与 symlink 随 M1 收口 |
| 3 性能 | 无发现 | `sorted(rglob)` 为 O(n log n) 且是确定性条目顺序所需，无更低标准替代；`_digest` 1 MiB 流式；`ZIP_DEFLATED`；无循环内外部 I/O / N+1 / 字符串累加；`read_bytes` 最大单文件为实测产物约 22 MB，可接受 |
| 4 可维护性 | 无发现 | pyright strict 0 诊断背书完整注解；公共符号 docstring 齐全；常量带 `#:` 注释；嵌套 ≤3；实测新增/修改 `.py` 行宽 >100 计数为 0；注释与 docstring 全英文 ASCII（架构守卫）；`zip_dist.py` 220 行远低于 800 阈值；`tools/pack/__init__.py` 只改 docstring、包根仍惰性 |
| 5 架构边界 | 无发现 | 新模块在 `tools/`（构建期工具，不进 wheel），R1–R15 未触碰；架构守卫 37 全绿 + pyright strict 0 → 无新 `Protocol` / `TYPE_CHECKING` / `Any` / 相对导入 / `# type: ignore`；无 widget id / 主题 / R12 devtools 改动；`print()` 只在 CLI `main()` |
| 6 硬门禁 | 7/7 全绿（修复后） | 见 §六；skill 要求的 `pyright yate/ tests/ tools/` 与 `pytest tests/ -q` 由仓库更严口径（含 `pack/`、`-n auto`）覆盖 |

主代理兜底的 C 域专项（分域 C 零产出，亲自复核）：
- 双语文档：README/README.zh、manual.en/zh 新增段落逐项对齐；`build,ts,lua`
  守卫 8 个参数化用例全绿；`-Dist` / `--dist` / `--no-zip` 用法与实现一致。
- 文档规范：新增计划/子计划命名符合 `doc-conventions.md` §一，评审记录
  `YYYY-MM-DD-<topic>.md`，记录↔方案双向互链；本轮新增/修改文档内本机
  绝对路径命中 2 处（Git Bash 可执行文件绝对路径形态与 worktree 盘符路径），已按
  §五「随下次修改逐步迁移」脱敏；存量文档命中按规则不做专项清扫。
- 提交规范：11 笔提交均全英文 `type(scope): subject`，`type` 在允许集，逐步
  单独提交；`git diff --check master...HEAD` exit 0。
- 合并阻碍：见 §五。

## 四、发现与处置（skill Step 4 分级格式）

### [MAJOR] `tools/pack/zip_dist.py:67`（修复前） — `--stage` 畸形名导致 zip slip 与越界遍历（已修）

Problem：`archive_stage` 仅校验 `stage.is_dir()`，arcname 直接由 `stage.name`
拼出、顶层目录又从 `entries[0][1].split("/", 1)[0]` 反推。`Path(".").name`
为 `""`、`<dir>/..` 的 `.name` 为 `".."`，二者 `is_dir()` 均为真：传 `--stage .`
会 `rglob` 整个仓库根（含 `.git/` / `.venv/`）并写出 `/...` 绝对 arcname；
传 `<dir>/..` 写出 `../...`。首轮分支评审曾以「脚本侧 stage 名固定」判该面
不成立，遗漏了公开的 `python -m tools.pack.zip_dist` CLI 入口。另
`is_file()` / `read_bytes()` 跟随符号链接，可把 stage 外文件内容写入归档。
Fix（提交 `6f842d34`）：入口拒绝空 / `.` / `..` 名并 `root = stage.resolve()`、
`stage_name = root.name` 显式贯穿产物名 / mkstemp prefix / arcname；
`_stage_files(root, stage_name)` 跳过 symlink 并断言
`path.resolve().is_relative_to(root)`；`_write_archive` 接收显式
`stage_name`，删除反推。新增 3 个回归用例（`.`、`..`、顶层前缀），
局部验收 49 passed / pyright 0 / 架构 37，修复后七道门禁全绿。

### [MAJOR] `.trae/reviews/README.md:178`（修复前） — 评审索引编号重复 + 唯一合并冲突块（已修）

Problem：master 已用 #70（IKTPC2 首轮）/ #71（复审）/ #72（合并前 pr-review），
本分支在同一文件登记「2026-11-10 IKTRDV 增量：新增 #70」，编号重复；且双方
都在 `#69 增量段`之后插入，`git merge-tree` 出现唯一冲突块（起始标记 `.our` / 结束标记 `.their`），合并
会失败并把错误编号带进主干。
Fix（提交 `6f842d34`）：编号顺延为 #73，整段移到 `#67 增量段`之前的散文区、
与 master hunk 错开；提交态 `git merge-tree` 实测 `CONFLICT_MARKERS 0`、
`IDX_70 0` / `IDX_73 1` / `IKTRDV_SEGMENTS 1`。本次 pr-review 记录另登记 #74。

### [MINOR] 登记待办（不阻塞合入）

| # | 位置 | 摘要 |
| --- | --- | --- |
| 1 | `tools/pack/zip_dist.py:158` | 非 ASCII stage 名时 `encode("ascii")` 抛错且 upsert 同名判断用 `errors="replace"` 解码永不匹配；可改字节级 `os.fsencode` 比较，或入口显式拒绝非 ASCII 名 |
| 2 | `tests/test_pack_spec.py:746` | 归档分支守卫未钉死「冒烟之后 / `--dist` 块之内」的相对顺序与块边界；可加 `index("Remove-Item $smokeOut") < index("tools.pack.zip_dist")` 等断言 |
| 3 | `tools/pack/zip_dist.py:68` | symlink 当前采用「跳过」策略，未写 `S_IFLNK` 条目；若 Linux 产物含合法链接，zip 与 stage 目录树不完全一致，需产品决策 |
| 4 | `tools/pack/zip_dist.py:184` | `mkstemp` 创建 0600 临时文件后直接 `os.replace`，POSIX 上交付 zip / 校验文件为仅属主可读写（Windows 无此差异）；可在 replace 前 `chmod 0o644` 并补单测 |
| 5 | `tools/pack/zip_dist.py:196` | 无锁 read-modify-write，两进程并发归档同一 dist 根时可能「zip 是 B、校验写的是 digest_A」；可在文档声明不支持并行，或加文件锁 / 旁置校验文件 |
| 6 | 合并时 | 分支文档「架构 37」是 merge-base 时点事实，合并到 `18e96d2a` 后架构守卫为 38，六/七道门禁须在合并树上重跑 |
| 7 | 合并时 | `tools.changelog check` 分支侧与 master 侧均 exit 0、PR diff 不含 CHANGELOG，未复现 IKTPC2 的分支级红门禁；按历史惯例仍列为合并时人工确认项 |

前两轮已登记的 N1（存量 `test_app_panes` 确定性竞态，不得记「偶发」）、N2–N5、
m1 / m7 继续有效，本记录不重复计条。

## 五、合并阻碍裁定（PR 级）

| 项 | 独立结论 | 依据 |
| --- | --- | --- |
| 索引编号重复 + 文本冲突 | **需修复 → 已修** | 提交态 `git merge-tree`：`CONFLICT_MARKERS 0`、`CHANGED_IN_BOTH 3`（无冲突标记）、编号 #73 唯一 |
| `manual.en/zh` 双方改动 | **可接受** | master 改 F7 hover 章节（约 511/587/1367/1617 行），分支改 §19 Build & Release（约 1650/1474 行），hunk 不重叠，可自动合并 |
| 架构守卫 37→38 | **合并时重跑** | `git show master:tests/test_architecture.py` 实测 38 个 `def test_`，规则与守卫清单已由 master 同步；分支时点数字保留不改 |
| changelog 分支级红门禁 | **合并时人工确认** | 分支侧本轮 7 道门禁 `changelog 0`；master 侧历史 pr-review 记录同名命令 exit 0；PR diff 不含 CHANGELOG |
| `--dist` 在 PowerShell 命令模式 | **可接受** | 双连字符终止符形态属既有行为，非本分支引入；文档已纠偏为 `-Dist`，bat 显式映射保留 `--dist`；Windows 三次真实构建验证 |
| Linux 真实构建不纳入 | **可接受** | issue 验收 4 明文允许；posix mode 单测 + sh 静态守卫 + `python -m zipfile -t` 等价覆盖，偏离如实登记、未声称跑过 |

## 六、硬门禁实测（skill Step 3 / 仓库总纲口径）

修复前首轮（`_pr_gate.py`）：pyright 0 / pytest `-n auto` 0 / 架构 37 /
覆盖率 **RC=1** / 冒烟 121/121·1464 / changelog 0 / diffcheck 0。
覆盖率红项尾部为
`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":18852,"threshold":9999,...}`：
本机 %TEMP% 积压触发 safe-delete 钩子拦截 pytest 收尾清理，属环境钩子。
按 `python-coding-style.md` §4.7 以 `-n 1` 复核：RC=0，3495 passed /
10 skipped，TOTAL 92.94%（≥75），判定非产品缺陷、非用例 flake，未改断言、
未记「偶发」。

修复后（`6f842d34` 之后重跑同一脚本）：

| 命令 | 退出码 | 关键数字 |
| --- | --- | --- |
| `pyright yate/ tests/ tools/ pack/` | 0 | 0 errors, 0 warnings |
| `pytest tests/ -q -n auto` | 0 | 100% 完成、无 FAILED/ERROR |
| `pytest tests/test_architecture.py -q` | 0 | 37 passed |
| `pytest tests/ --cov=yate --cov-branch -n auto` | 0 | 3498 passed / 10 skipped，TOTAL 92.95%，Required 75 reached |
| `tools.smoke_test run --jobs 4` | 0 | 121/121 scenarios、1464/1464 checks |
| `tools.changelog check` | 0 | released sections up to date；unreleased lag 为存量 |
| `git diff --check master...HEAD` | 0 | 无空白错误 |

`GATE_RCS [0, 0, 0, 0, 0, 0, 0]`、`ALL_ZERO True`。

## 七、结论与合并前动作

- **Verdict：APPROVE**（0 BLOCKER / 0 MAJOR / 7 MINOR 登记待办）。两条 MAJOR
  已在修复波 `6f842d34` 当轮修复并经主代理独立复核；合并冲突与编号重复归零。
- 合并前（由人类/合并者执行）：在合并树上重跑七道门禁（架构 38）、确认
  `tools.changelog check`、按日期统一重排评审索引编号（本分支 #73/#74 与
  master #70–#72 并存时）；本记录不自动合并、不推送。
- 未推送、未合流、工作树干净；评审索引登记 #74。

## 八、Strengths

- 共享 Python 助手让 Windows / Linux 的 zip 命名、顶层目录、Unix mode、
  原子替换、校验条目 upsert 只有一份实现，静态守卫钉死三脚本开关与帮助区间。
- 三次真实 Windows PyInstaller 构建（默认 / onefile 覆盖 / `-NoZip`）+
  `Expand-Archive` 目录树逐字节比对 + `Get-FileHash` 与 `--version` 冒烟，
  并有负向演练证明 help 区间守卫真能拦截漂移。
- 两轮分支评审把 3 条 major 归零，本轮 PR 级评审主动发现并消除合并阻碍
  （编号重复 + 冲突块），而非留给合并者；子代理零产出如实登记、主代理
  按 skill 六维度兜底并逐条回读复核。
- 新增代码 pyright strict 0 诊断、行宽 100 全合规、覆盖率 92.95%，
  修复波新增 3 个针对性回归用例（`.` / `..` / 顶层前缀）。

## 九、续作会话独立复核补记（2026-11-10，主代理亲跑）

本节记录另一无人值守会话在闭环后的独立复核；不改动 §七 的 APPROVE 结论，
只补登记新证据与两条 minor，供合并者查阅。

- 范围与基线不变：`master...HEAD`，merge-base `b982c06`；复核时 HEAD 为
  `91c493fa`（在 §七 结论之上另有 2 笔文档回填提交，未改产品代码）。
- 分域审查重新下发 2 名只读 `code-explorer`（功能/安全、架构/文档/合并准备），
  两名均交付完整报告——与 §二 记载的「分域 B/C 零产出」不是同一批次，
  如实并列登记，不覆盖前次事实。主代理对每条发现逐条回读代码定级：
  - 两条最重发现（`--stage` 畸形名造成 zip slip / 越界 rglob、symlink 跟随
    把 stage 外内容打进包）经独立探针复验**已被 `6f842d34` 收口**：
    `Path(".")` / `Path("..")` / `<stage>/..` 三种输入均抛
    `ZipDistError("invalid stage directory name")` 且不产生任何 zip / tmp；
    真实 symlink 指向 stage 外文件时归档 `namelist()` 仅含正常条目，不含
    链接目标；正常归档顶层前缀为 `<resolved stage name>/`，无条目以 `/`
    开头或含 `..`，临时文件无残留。
  - 评审索引撞号与本机绝对路径泄漏两条经复验已闭环：提交态 `merge-tree`
    精确冲突块计数 0（3 处双方改动均可自动合并）、#73 / #74
    各登记一次、新增/修改文档盘符路径命中 0。
- 本会话主代理亲跑八项门禁（非引用前轮数字）：`GATE_RCS
  [0, 0, 0, 0, 0, 0, 0, 0]` / `ALL_ZERO True`——
  pyright `0 errors, 0 warnings, 0 informations`；`pytest tests/ -q -n auto`
  100% 完成、无 FAILED/ERROR；架构 37 passed；覆盖率
  `3498 passed, 10 skipped` / `TOTAL 19552 语句 · 93%（92.95%）`，
  `Required test coverage of 75.0% reached`；冒烟 `121/121 scenarios`、
  `1464/1464 checks`；changelog `released changelog sections are up to date`
  （unreleased lag 14 属存量）；`git diff --check` 与
  `git diff --check master...HEAD` 均 0。覆盖率本轮 `-n auto` 直接为 0，
  未复现 §六 的 safe-delete 钩子拦截，如实记录两轮差异、不改判前轮事实。
- 新增 minor 2 条（登记待办，不阻塞合入；均为畸形 CLI 输入或异常注入才
  触发的边缘面，正常构建脚本路径不经过）：

  | # | 位置 | 摘要 |
  | --- | --- | --- |
  | 8 | `tools/pack/zip_dist.py:196-197` | 两次 `os.replace` 之间失败会留下「新 zip + 旧 SHA256SUMS.txt」；可保留旧 zip 备份并回滚，或收窄 docstring 的 never touches 措辞后另案事务化并补 monkeypatch 用例 |
  | 9 | `tools/pack/zip_dist.py:178-179` | `--dist-root` 落在 stage 内时，重跑会把上一次的 zip 当普通文件再打进新包；可在入口拒绝 `dist_root.resolve().is_relative_to(root)` 并补参数化用例 |

- 按 skill Step 5 撤回重复发现 1 条：分域审查重提「`_write_archive` 每文件
  重复 `stat` + 整文件 `read_bytes()`」，前两轮分支评审已按
  `python-coding-style.md` §6.1「无实测依据的预优化不做」删除同一误报；
  本会话无新的 profiler 证据，不重提、不计入清单。
- 结论：**APPROVE 维持**（0 BLOCKER / 0 MAJOR；minor 待办由 7 条增至 9 条）。
  仍不自动合并、不推送，合并决定归人类评审者；合并树上须重跑门禁
  （master 架构守卫 38）并按日期统一重排评审索引编号。
