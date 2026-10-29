# arch-sec-audit 总纲（全仓库架构 / 项目结构 / 安全性审查与迭代修复）

- 日期：2026-10-29；分支 `enh/arch-sec-audit`；worktree `D:\Programming\yate-arch-sec-audit`（基于 master 98963be）。
- 流程：task-orchestration 闭环。批准环节按无人值守规则（工作区规则 §二.5 + 用户显式指令
  「进入无人值守，无须过问」）视为通过；方案落盘后直接进入执行。
- 子代理模型（task-orchestration §一.3，CodeBuddy 来源）：plan-executor=GLM-5.3-Flash、
  code-review-expert=DeepSeek-V4.1-Flash。plan-architect-designer 的 frontmatter 模型
  `qwen-3.7-plus` 为运行时既证未注册（2026-10-27 两次实测 spawn 必败且任务书指定无效），
  按 §一.3.5 + §三 兜底：**主代理亲自产出本方案**（标注：该角色子代理零产出）。

## 基线（改动前实测，本 worktree 沙箱）

| 门禁 | 命令 | 结果 |
|---|---|---|
| pytest | `pytest tests/ -q -n auto` | exit 0（约 13 skipped，无失败） |
| pyright | `pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings, 0 informations |
| 架构 | `pytest tests/test_architecture.py -q` | 37 passed |
| 覆盖率 | `pytest tests/ --cov=yate --cov-branch -n auto` | exit 0，**92.31%**（fail_under=75） |
| 冒烟 | `python -m tools.smoke_test run --jobs 4` | 117/117 scenarios，1407/1407 checks |

## 目标

1. **安全性**：修复审计发现的高危项（工作区主题目录无信任门控执行任意 Python）、
   yxp 解包穿符号链接写入、CI 最小权限、数据目录权限、无校验包静默安装；
   将扩展/Lua 的实际信任边界落成文档（en/zh 同步）。
2. **架构/结构**：裁决并登记 `services/extensions/__init__.py` 门面与 §三.5 的措辞冲突；
   收敛 `~/.yate` 路径 9 处散布拼接为 `yate.paths.yate_home()` 单一来源；
   补齐 README 对 games/which-key 手册的锚点、tests/README 统计漂移。

## 非目标（登记，不实施）

- **Lua 运行时沙箱机件**（删减 `os/io/package`、`attribute_filter`）：随包游戏
  （nethack/pacman/snake/tetris + lib/engine_*）跑在同一运行时上，行为回归风险高；
  本轮以文档声明信任边界（plan-b），机件加固另行立项。
- **ruff 等风格 linter 引入**：全仓风格清洗属大范围 churn，另行立项。
- **.gitattributes 增补 .py/.md eol 规则**：会触发全仓行尾归一化 churn，不动。
- **pyproject dev/ts 语法包清单去重**：已有 `test_dependency_groups.py` 守护，收益低。
- **780 行以下模块预防性拆分**（emulator.py 780、ts_backend/backend.py 755、manual.py 742、
  yxp.py 746、pty_proc.py 745、manager.py 740、yaterc_options.py 728、smoke harness 721）：
  均未触发 800 行阈值，仅登记观察，不拆。
- **CI smoke Linux 腿、覆盖率阈值上调（92% 实测 vs 75% 门槛）**：跨平台基线未固化，不动。
- **SECURITY.md**：缺可确认的私密上报通道，本轮不创建；信任模型写入既有手册。

## 发现与处置映射

安全（证据行号以取证扫描为准）：

| # | 级别 | 发现 | 处置 |
|---|---|---|---|
| S1 | 高 | `yate/cli.py:413-415` 无条件 exec 工作区 `./themes/*.py`（`theme_files.py:69-76`），绕过 `./extensions`/项目 yaterc 已有的 workspace trust 门控，违背 `trust.py:3-9` 威胁模型 | plan-a |
| S2 | 高 | Lua 运行时无沙箱且超文档化模型（`lua/runtime.py:111-130`；`api.py:251-254`） | plan-b（文档声明边界）；机件加固列非目标 |
| S3 | 中低 | `.github/workflows/test.yml` 缺 `permissions:` 块 | plan-c |
| S4 | 低 | `yxp.py:434-438` 解包穿预置符号链接写出目标目录 | plan-e |
| S5 | 低 | `logs.py:190,197` 数据目录创建无 0700（对比 `trust.py:103-111`） | plan-d |
| S6 | 低 | `yxp.py` 无 checksum 成员的包静默安装 | plan-e（告警日志） |
| S7 | 中 | 无单一威胁模型文档；扩展文档未声明沙箱/信任边界 | plan-b（扩展文档）+ plan-a（主题文档） |

结构：

| # | 发现 | 处置 |
|---|---|---|
| A1 | `services/extensions/__init__.py`（service 包）纯重导出门面缺 §三.5 异常声明措辞 | plan-b（docstring + 规则登记） |
| A2 | `~/.yate` 路径手工拼接 9 处（cli.py:414、diagnostics.py:230,363、yaterc.py:84、trust.py:35、loader.py:310、data_store.py:31、logs.py:190,197） | plan-d |
| A3 | games.*/which-key.* 手册无 README 锚点；tests/README.md:16 统计漂移（140 vs 实测 148） | plan-c |
| A4 | .gitignore 含 cookiecutter 模板残留段 | 登记，本轮不动（纯卫生项，避免与安全修复混提交） |
| A5 | conftest 触碰 Textual/theme 私有内部 | 登记，升级时再处理 |
| A6 | pyright Linux 平台 lint 未做（test.yml:188 TODO） | 登记，非目标 |

## 子计划索引与执行波次

| 子计划 | 主题 | 独占文件（产品/文档/测试） | 波次 |
|---|---|---|---|
| plan-a | S1 主题信任门控 + 主题手册信任段落 | yate/editor_view/theme_files.py、yate/editor_view/theme.py、yate/cli.py（仅调用行）、yate/docs/themes.{en,zh}.md、tests/test_theme_trust.py | wave-1 |
| plan-b | S7/A1 扩展信任边界文档 + 门面 §三.5 注记 + 规则登记 | yate/docs/extensions.{en,zh}.md、yate/services/extensions/__init__.py、.trae/rules/architecture-boundaries.md | wave-1 |
| plan-c | S3 CI 最小权限 + A3 文档锚点与统计 | .github/workflows/test.yml、README.md、README.zh.md、yate/docs/README.md、tests/README.md | wave-1 |
| plan-d | A2 yate_home 收敛 + S5 数据目录 0700 | yate/paths.py、yate/yaterc.py、yate/services/trust.py、yate/services/data_store.py、yate/services/extensions/loader.py、yate/logs.py、yate/diagnostics.py、yate/editor_view/theme_files.py（仅 home themes 一行）、yate/services/user_setup.py（v3）、tests/test_paths.py | wave-2 |
| plan-e | S4 yxp 符号链接拒写 + S6 无校验告警 | yate/services/yxp.py、tests/test_yxp.py | wave-2 |

```mermaid
flowchart LR
    W1["wave-1: plan-a ∥ plan-b ∥ plan-c"] --> W2["wave-2: plan-d ∥ plan-e"]
    W2 --> RV["wave-3: code-review-expert 评审"]
    RV --> IT["迭代修复（blocker/major 归零）"]
    IT --> GATE["主代理全量门禁 + 回填 + 提交"]
```

- wave-1 三个子计划文件互不重叠，可并行（2~3 个一批纪律，3 个一批下发）。
- ~~`yate/cli.py` 由 plan-a（wave-1）与 plan-d（wave-2）先后触碰~~（plan-a v2 后
  plan-d 对 cli.py 的触点取消，改触 `editor_view/theme_files.py` 一行，见 plan-d 修订注）。
- **执行偏差记录（2026-10-29）**：wave-2（plan-d/e）在 plan-c 验收关闭前提前派发。
  实测依据：plan-a/b 已独立复核通过（exit 0）并提交；plan-c 名下在改文件
  （.github/workflows/test.yml、README*、yate/docs/README.md、tests/README.md）与
  plan-d/e 独占清单零重叠，无文件冲突；plan-c 的验收由主代理在其交付时独立重跑，
  不受 wave-2 并行影响。
- 每个子计划验收通过（验收命令 exit 0）后，由主代理按子计划单独提交一笔。

## 风险与回滚

- 风险 1：cli.py 启动路径改动导致主题加载回归——plan-a 提取可测助手 + 4 条用例；
  冒烟含主题场景，wave-3 评审兜底。回滚：revert 对应提交。
- 风险 2：yxp 行为收紧使既有安装流失败——plan-e 仅在"目标是符号链接"这一
  非常规前置态拒绝，常规重装路径有正向用例守护。回滚：revert。
- 风险 3：paths 收敛触碰 8 个文件——机械替换 + 全量门禁；pyright strict 兜底。回滚：revert。

## 执行记录（回填区）

- [待回填] wave-1 / wave-2 / 评审 / 门禁结果与偏离记录。
