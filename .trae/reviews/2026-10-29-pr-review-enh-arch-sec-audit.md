# pr-review · `enh/arch-sec-audit` 分支审查（合并前预评审）

> 来源方案：[arch-sec-audit-plans/overview.md](../documents/arch-sec-audit-plans/overview.md)
> （总纲 + plan-a~e，wave-3 评审记录见
> [2026-10-29-arch-sec-audit.md](2026-10-29-arch-sec-audit.md)）。
> 本轮为分支级 `pr-review`（review 模式，六维度 + 硬门禁），评审时点 HEAD `5beb95a`
> （19 笔，base master `98963be`），`git diff --stat master...HEAD` = **35 files，
> +1367 −64**。处置结果见文末「处置结果」节（主代理收尾回填）。

- 评审者：`code-review-expert`（DeepSeek-V4.1-Flash，只读，未改任何文件，临时探针已自清）。
- 规范来源：`.trae/skills/pr-review/SKILL.md`；自检清单对照
  `../../rules/architecture-boundaries.md` §五/§六 与 `../../rules/python-coding-style.md` §五。
- wave-3 已登记待办（F4/F5/F6/F7、uninstall OSError 存量、yxp.py:398-399、
  .gitignore 残留、Lua 机件加固）按反馈回路纪律未重复上报；F6 仅补充新证据。

## 门禁实测（评审者，评审时点 5beb95a）

| 门禁 | 命令 | 结果 | 退出码 |
|---|---|---|---|
| pyright | `pyright yate/ tests/ tools/ pack/` | 0 errors / 0 warnings / 0 informations | 0 |
| pytest 全量 | `pytest tests/ -q -n auto`（`-o addopts=` 取汇总） | 3171 passed, 10 skipped | 0 |
| 架构 | `pytest tests/test_architecture.py -q` | 37 passed | 0 |
| 覆盖率 | `pytest tests/ --cov=yate --cov-branch --cov-fail-under=75 -n auto` | 92.30%，3171 passed / 10 skipped | 0 |
| 冒烟 | `python -m tools.smoke_test run --jobs 4` | 117/117 scenarios, 1407/1407 checks | 0 |

环境注记：评审会话 shell 实落 cmd（非 PowerShell）；覆盖率曾出现一次 xdist
`INTERNALERROR: KeyError: <WorkerController gw0>`（负载下记账抖动，`-o addopts=`
重跑干净消解）；覆盖率 92.30%（评审时点）与 92.22%（收尾时点）为逐次运行波动，
均在 75 门槛与既定解释口径内。

## 结论清单

**Overall: REQUEST_CHANGES**（0 BLOCKER / 2 MAJOR / 7 MINOR，无阻断项）

### MAJOR

- **[MAJOR] `yate/resources/manual.en.md:982-989` / `manual.zh.md:897-902` —
  应用内 `:help` 手册未同步主题信任门控**：站外指南 `themes.{en,zh}.md` 已声明
  `./themes` 仅受信任工作区加载（且自述与 `:help` 手册互为权威副本），但手册仍写
  "无条件自动扫描"、优先级列表仍无条件并列——用户从 `:help` 读到错误信任模型，
  正是 S1/S7 要消除的面。属 plan-a 计划范围漏项（`manual.*.md` 不在独占清单）。
- **[MAJOR] `yate/services/yxp.py:264` + `:466-475`/`:588`/`:662` — 大小写变体
  成员在大小写不敏感文件系统上互相覆盖**：`_parse_manifest` 仅去重大小写精确
  重复；`a.py` 与 `A.py` 并存时 install 记录两文件、磁盘只落一个，uninstall 报
  record 与磁盘不一致，升级路径还会误报 "belong to another package"（同包自我
  冲突）。破坏 record↔disk 一致不变量（评审者本机 install 探针实证），不构成提权。

### MINOR

- **[MINOR] `theme_files.py:93-95`/`:57-81` — 门控判定用 resolved cwd、加载与
  提示文案用未 resolved 拼写**：与 `loader.py:292-296` "判定与加载同一 resolved
  拼写"不变式相悖；实测无信任绕过（符号链接 cwd 探针），纯拼写/文案面。
- **[MINOR] `theme_files.py:76-79` — `./themes` 无 `*.py` 时也提示去 `:trust`**：
  噪声提示；与 loader 既有"只看目录存在性"语义一致的取舍（评审自评可选）。
- **[MINOR] `yxp.py:525-530`/`:549-555` — 回滚/恢复的 symlink 跳过分支无直接用例**
  （覆盖率 Missing 526-530 / 550-555），"回滚绝不因自身保护逻辑抛错"承诺缺守卫。
- **[MINOR] `user_setup.py:88` — `default_base_dir()` 仍自拼 `~/.yate`（F6 同族）**：
  不重复上报，补新证据——`yxp.default_extensions_dir()`（yxp.py:77-79）经其求值，
  与 `paths.yate_home()` 是两条求值路径，未来 `YATE_HOME_DIRNAME` 变更即分叉。
- **[MINOR] `logs.py:195-197`/`:205-207` — `mkdir` 未传 `mode=0o700`**：创建瞬间
  存在按 umask 建目录的极短窗口（随后立即 chmod 兜底）；F4 已登记，仅作记录。
- **[MINOR] `overview.md:15` 基线记"约 13 skipped"（实测 10）与提交计数随每笔
  提交失准（文档一致性）**。
- **[MINOR] 风格类合并**：`cli.py:413` 单行 93 字符与相邻多行调用排版不一（未超
  100）；新增测试 docstring 两行摘要（与仓库多数测试一致，可接受）。

### 自我批判（主动排除的疑点，摘录）

`theme_files` 引 `services.trust` 非 L2→L3 向上（`services/*` 在 L0 叶子清单，
守卫 37 passed 证实）；符号链接 cwd 无信任绕过（运行时探针：判定侧 resolve 使
`is_trusted(cwd.resolve())` 为真，主题正常加载）；`TRUST_FILE` 改 `yate_home()`
不破坏测试 patch（调用时求值 + conftest autouse isolated_home）；`cli.py` 零新增
导入（diff 仅调用行）；`logs.py` 导入 `yate.paths` 未破坏 stdlib-only 自述
（docstring 已同步）；CI `permissions: contents: read` 不影响既有 job（无写权限
动作）；CI 双语手册小节号/交叉引用两两对得上。

### Strengths（摘录）

yxp 符号链接加固端到端六面覆盖（写/删/回滚/恢复/卸载/records）；两阶段 stale
清理正确闭合 N1；信任门控下沉 `theme_files` 且 cli 零新增导入；`yate_home()` 九处
单源干净（paths.py 覆盖率 100%）；新增 10 条 yxp 用例四重断言 + 建链不可用降级；
规则与豁免两处同步登记；CI 最小权限与 0700 属低成本纵深防御。

## 处置结果（主代理收尾回填，2026-10-29）

- **[MAJOR] 手册同步 → 已修**（`eebc5f8`）：`manual.en.md` / `manual.zh.md` 扫描
  位置与优先级列表第 2 项改注 "**trusted** workspaces only / 仅受信任工作区"
  （`:trust` 后重启，指向主题指南第 7 节）；双语同构；`test_manual.py` +
  `test_app_manual.py`（27 passed）与 `test_smoke_cli.py`（22 passed）验证。
- **[MAJOR] yxp 大小写冲突 → 已修**（`181f179`）：`_parse_manifest` 保留精确重复
  快速路径，新增逐段 `casefold` 键去重（`PurePosixPath(entry).parts`，覆盖
  `sub/x.py` vs `SUB/X.py`），命中抛 `YxpError`（"case-colliding entries"）。
- **[MINOR] 回滚/恢复跳过分支 → 已补直接用例**（`181f179`）：
  `test_rollback_skips_symlinked_member` /
  `test_restore_stale_files_skips_symlinked_member`（外部文件未动 + WARNING 告警
  双断言；负向演练先红后绿自证有效）。
- **[MINOR] 主题路径拼写 → 已修**（`6f58ee2`）：`default_theme_dirs` 先
  `cwd = Path.cwd().resolve()`，判定/加载/文案三处统一复用；提示措辞一字未动；
  行为等价（判定集合不变，仅路径形态转 resolved）。
- **[MINOR] 总纲口径 → 已修**（`2ed0cbc`）：基线 skip 数改实测 10；提交计数改
  动态口径（以 `git rev-list --count master..HEAD` 为准）。
- **登记不修（随下次修改逐步处置）**：空 `./themes` 目录噪声提示（与 loader 既有
  语义一致，改则两处同步）；F6 维持登记（新证据 `yxp.py:77-79` 求值路径耦合记入
  待办上下文）；`logs.py` mkdir `mode=0o700` 创建窗口（并入 F4 处置时一并收紧）；
  `cli.py:413` 排版统一（未超 100，纯读感）。
- **迭代修复后主代理收尾门禁（HEAD `2ed0cbc`，并行口径，逐项实测退出码 0）**：
  pyright 0 诊断；pytest 全量 **3173 passed / 10 skipped**（含 2 条新用例）；架构
  **37 passed**；覆盖率 **92.22%**（fail_under=75 通过）；冒烟 **117/117
  scenarios、1407/1407 checks**；`tools.changelog check` exit 0。
- 主代理独立复核记录：pyright（4 个改动文件）0 诊断；定向
  `pytest tests/test_yxp.py tests/test_theme_trust.py tests/test_manual.py
  tests/test_app_manual.py tests/test_paths.py -q -rs` = 81 passed / 1 skipped
  （skip = POSIX 权限位，本机预期）。
- 本轮登记后评审索引同步：`.trae/reviews/README.md` §一 #49 + §二行（同笔
  `docs(review)` 提交）。
