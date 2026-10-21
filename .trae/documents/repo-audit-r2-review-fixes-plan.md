# repo-audit-r2 review fixes plan（pr-review 发现登记与修复）

- 任务：登记 `ref/repo-audit-r2` 分支 pr-review（2026-10-18）发现的问题并修复
- 来源评审记录：[`../reviews/2026-10-18-pr-review-ref-repo-audit-r2.md`](../reviews/2026-10-18-pr-review-ref-repo-audit-r2.md)（本任务 P1 产出，与本文档互链）
- 工作区：续作复用 worktree `../yate-repo-audit-r2`（分支 `ref/repo-audit-r2`，沙箱 `.venv` 已自证指向本 worktree），不新建
- 分流判据：改动 ≥3 文件 → 走闭环（task-orchestration §一.2）

## 一、目标与非目标

**目标**

1. 把 pr-review 的 1 MAJOR + 5 MINOR 全部登记为只读评审记录（R0）；
2. 修复其中可在本地闭环验证的 5 项（F1–F5）+ 补登记索引（F6）。

**非目标**

- 不在本轮验证 GitHub Actions 的 Linux 腿（无远端触发权限）；F4 以临时降级 + 待办登记；
- 不清扫 `.trae/` 存量文档的 42 处历史路径（既有裁定：随下次修改迁移）；
- 不改 `ref/repo-audit-r2` 已评审的其它行为（trust 门控 / close_under / LSP 等）。

## 二、发现清单（编号与评审记录一致）

| 编号 | 级别 | 位置 | 问题 |
|---|---|---|---|
| F1 | MAJOR | `yate/app.py:262` | `poll_idle` 在空屏幕栈（teardown 竞态）访问 `self.screen` 抛 `ScreenStackError`；覆盖率插桩下 3/3 次全量运行各失败 1–2 例（失败点均为未改动文件的 pilot 时序用例），不带 `--cov` 全量通过 |
| F2 | MINOR | `.trae/rules/task-orchestration.md` §二.7 | `fail_under=75` 单点源后，局部 `--cov` 运行必须 `--cov-fail-under=0`，该口径只写在 pyproject 注释里 |
| F3 | MINOR | `.workflow/test.yml:69` | 注释仍写 `fail-under stays identical`，与新口径矛盾 |
| F4 | MINOR | `.github/workflows/test.yml:91` | 新增 smoke job 的 `ubuntu-latest` 腿从未验证，红灯即挡合并 |
| F5 | MINOR | 3 个新增计划文档 | 自身携带本机真实路径 `d:\Programming\yate\...`（违反 doc-conventions §五） |
| F6 | MINOR | `.trae/reviews/README.md` | 3 条 2026-10-18 评审记录未进索引 |

## 三、备选方案与否决理由

**F4（smoke job Linux 腿）**

- 方案 A（否决）：维持双腿硬门槛。—— 首次 CI 运行即可能红，且本地无法复现 Linux 腿，等于把验证成本推迟到「挡住合并」之后。
- 方案 B（采纳）：`ubuntu-latest` 腿加 `continue-on-error`，注释注明「临时，首轮 CI 全绿后移除」，并把「移除降级」登记为待办（本计划 §五）。
- 方案 C（否决）：直接砍掉 Linux 腿。—— 双平台覆盖是 smoke job 的立项目标之一，砍腿不可逆。

**F1（回归测试形态）**

- 方案 A（采纳）：headless 直构 `YateApp()`（不 `run_test`）调用 `poll_idle()`——已实测未挂载实例 `_screen_stack == []`、`_idle` 就绪、`interval=120`，今日直接抛错，负向演练面天然存在；再补一条 run_test 活体路径（`due` 恒真 → `execute_action("toggle_screensaver")` 恰好一次）证明守卫未破坏正常调度。
- 方案 B（否决）：在 run_test 内清空 `_screen_stack` 模拟竞态。—— 干扰 Textual 消息泵，脆弱且与真实竞态形态不符。

## 四、分步实施计划（波次间串行，波内文件独占）

### P0 【方案】（本文档）

- 输入：评审发现（上表）+ 已验证事实（`app.py:247-265`、未挂载空栈探针、`execute_action(name: str) -> bool`）
- 产出：本文档 → **待用户批准**

### P1 【登记】主代理亲自：评审记录 + README 索引

- 独占文件：`.trae/reviews/2026-10-18-pr-review-ref-repo-audit-r2.md`（新建）、`.trae/reviews/README.md`
- 输出：只读事实文档（1 MAJOR + 5 MINOR，含实测门禁数字与 3 次运行失败表），与本文档互链；README 表格追加 4 行（3 条既有 2026-10-18 记录 + 本条）
- 验收：`Select-String -Path .trae/reviews/README.md -Pattern '2026-10-18'` 命中 ≥4；两文档互链有效

### P2 【执行·波 1】子代理 A：poll_idle 守卫 + 回归测试

- 独占文件：`yate/app.py`、`tests/test_app_idle.py`（新建）
- 改动：
  - `poll_idle` 在 `self._idle`/interval 检查之后、`self.screen` 访问之前加卫语句：

    ```python
    if not self.screen_stack:
        # Teardown race: the 1 s poll timer can fire after the last
        # screen is popped; there is nothing to inspect then.
        return
    ```

    （docstring 追加一句说明该竞态与覆盖率插桩下的实测失败形态）
  - 新建 `tests/test_app_idle.py`（全英文注释，文件头 `# pyright: reportPrivateUsage=false`，遵守 `from __future__ import annotations`）：
    1. `test_poll_idle_survives_an_empty_screen_stack`：`YateApp()` 直构（不 run_test），`app._idle` 保持默认，直接 `app.poll_idle()` 不抛；先 `assert app._screen_stack == []` 锁定前提，防 Textual 升级后守卫面失真；
    2. `test_poll_idle_still_toggles_when_due`：`run_test` 挂载后 monkeypatch `app._idle` 为 `due()` 恒真的替身、`app.editor.execute_action` 为记录器，调用 `app.poll_idle()` 断言恰好一次 `"toggle_screensaver"`。
- 验收命令：
  - `.venv\Scripts\python.exe -m pyright yate/app.py tests/test_app_idle.py` → 0 诊断
  - `.venv\Scripts\python.exe -m pytest tests/test_app_idle.py -q` → 2 passed
  - 负向演练：临时还原卫语句 → 用例 1 必须红（`ScreenStackError`）→ 还原
  - `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k "ascii or comments"` → 新文件注释全 ASCII

### P3 【执行·波 1】子代理 B：CI 注释与降级 + 文档脱敏

- 独占文件：`.github/workflows/test.yml`、`.workflow/test.yml`、
  `.trae/rules/task-orchestration.md`、
  `.trae/documents/repo-audit-r2-plans/repo-audit-r2-architecture-plan-d.md`、
  `.trae/documents/repo-audit-r2-plans/repo-audit-r2-doc-hygiene-plan-a.md`、
  `.trae/documents/repo-audit-r2-plans/overview.md`
- 改动（逐处 old→new 以本计划为准，不凭常识猜）：
  1. `.github/workflows/test.yml` smoke job matrix：为 `ubuntu-latest` 腿加
     `continue-on-error: ${{ matrix.os == 'ubuntu-latest' }}`，注释注明「provisional: the Linux leg
     has never run; drop this once one CI round is green on both legs」；
  2. `.workflow/test.yml:69` 注释改为 `# --cov uses the [tool.coverage.*] config in pyproject; the threshold lives in [tool.coverage.report] fail_under`；
  3. `.trae/rules/task-orchestration.md` §二.7 门禁句追加半句：局部（单文件/目录）覆盖率运行须加 `--cov-fail-under=0`，否则被 `[tool.coverage.report] fail_under` 判红；
  4. `repo-audit-r2-architecture-plan-d.md`：`:126` 引文改 `<原 worktree 绝对路径>\.venv\Scripts\python.exe`；`:135` 示例改 `<worktree>\yate\...`；`:145` / `:238` / `:278` 的演练命令 `cd d:\Programming\fake` 改 `cd ../<sibling-worktree>-fake`（仓库相对形态，不指向任何本机盘符）；
  5. `repo-audit-r2-doc-hygiene-plan-a.md`：`:40` 引文块与 `:202` 表格「原内容」列同样脱敏为 `<原 worktree 绝对路径>\.venv\...`（保留「107 字符 / 62 字符」的量化结论不变）；
  6. `overview.md:133`：m-1 行的命中示例改为「本机解释器绝对路径（已脱敏）」，不再复写路径本体。
- 验收命令：
  - `Select-String -Path <6 文件> -Pattern '(?-i)[A-Za-z]:[\\/]+Programming'` → 零命中
  - `.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/test_gate_config.py -q` → 40 passed（`test_ci_workflow_runs_the_ui_smoke_suite` 仍绿，证明 smoke 调用未被注释改坏；`test_coverage_threshold_is_not_hardcoded_on_the_ci_command_line` 仍绿）

### P4 【审核】主代理收口

- 主代理重跑全部子代理名下验收命令（只认落盘结果 + 独立复核）；
- 全量门禁：`.venv\Scripts\python.exe -m pyright yate/ tests/ tools/`；`.venv\Scripts\python.exe -m pytest tests/ -q`；`.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-branch`（≥75）
- 冒烟：`.venv\Scripts\python.exe -m tools.smoke_test run --skip-slow --quiet` → exit 0
- 本文档回填真实数字与偏离记录

### P5 【收尾】提交（只提交不推送，信息按 git-commit-message.md）

| # | scope | 内容 |
|---|---|---|
| 1 | `docs(reviews)` | 评审记录 + README 索引 4 行 |
| 2 | `fix(app)` | poll_idle 空栈守卫 + `tests/test_app_idle.py` |
| 3 | `chore(ci)` | smoke ubuntu 腿临时降级 + Gitee 注释同步 |
| 4 | `docs(rules)` | task-orchestration 局部覆盖率 opt-out 口径 |
| 5 | `docs(audit)` | 3 个计划文档本机路径脱敏 |

## 五、风险清单与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `screen_stack` 属性语义随 Textual 升级变化，守卫失效 | 用例 1 显式 `assert app._screen_stack == []` 锁前提，升级时先红在此 | 还原 `app.py` 单处卫语句 |
| `continue-on-error` 掩盖 Linux 真实回归 | 注释写明临时性与移除条件；P1 评审记录登记待办 | 删 1 行即恢复硬门槛 |
| 文档脱敏破坏「证据可追溯」 | 量化结论（字符数、行号）保留，仅路径本体改占位符 | git revert 对应提交 |
| 新测试与 pilot 用例并发互相干扰（subagent-workflow §三.3） | 用例 1 为纯同步无 pilot；用例 2 单独 run_test，若全量运行偶发先重跑确认再下结论 | 删除测试文件 |

## 六、待办登记（不在本轮）

1. smoke job 双腿首轮 CI 全绿后移除 ubuntu 腿 `continue-on-error`（F4 跟进）；
2. `.trae/` 存量文档 42 处历史路径随下次修改迁移（既有裁定，不变）。

## 七、执行记录回填（2026-10-18，主代理）

**波次与产出**：P1 主代理亲自（评审记录 + README 索引 4 行）；P2 子代理 `wave-code`、
P3 子代理 `wave-docs` 并行（`acceptEdits`，文件独占无交集，两成员均正常回报、零卡死）；
P4 主代理独立复核 + 全量门禁；P5 分 5 笔提交。

**验收复核（主代理重跑，不引用成员自述数字）**

| 项 | 命令 | 实测 |
|---|---|---|
| P2 pyright | `python -m pyright yate/app.py tests/test_app_idle.py` | `0 errors, 0 warnings, 0 informations`，exit 0 |
| P2 用例 | `python -m pytest tests/test_app_idle.py -q` | 2 passed，exit 0（负向演练由成员实测：移除卫语句 → 用例 1 红 `ScreenStackError`，还原后复绿） |
| P3 路径扫描 | `Select-String … '(?-i)[A-Za-z]:[\\/]+Programming'`（6 文件） | 零命中 |
| P3 架构+门禁 | `pytest tests/test_architecture.py tests/test_gate_config.py -q` | 40 passed，exit 0 |
| 全量 pyright | `python -m pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations`，exit 0 |
| 全量 pytest（无插桩） | `python -m pytest tests/ -q` | 全绿（35 行进度点至 100%），exit 0 |
| 覆盖率 | `python -m pytest tests/ -q --cov=yate --cov-branch` | **exit 0，92.01%，0 失败** |
| 冒烟 | `python -m tools.smoke_test run --skip-slow --quiet` | 107/107 场景、1304/1304 checks，exit 0 |

**F1 修复定性**：修复前覆盖率插桩下全量 3/3 次运行各失败 1–2 例（详见评审记录 §二 F1）；
修复后同条件全量 1/1 通过、0 失败。根因与守卫的因果关系在本地可观测面内成立
（CI 仍需一轮观察，见待办 1）。

**偏离记录（均非设计性偏离）**

1. P2 成员初版用 lambda 记录器触发 pyright `reportUnknown*` 3 例，改为带 `name: str` 注解的
   具名函数后归零（pyright strict 要求，符合 python-coding-style）；
2. P3 成员在验收命令中去掉命令行 `-q`（pyproject `addopts = "-q"` 叠加成 `-qq` 会隐藏汇总行），
   40 个进度点 + 退出码 0 先行确认，去掉后拿到 `40 passed` 汇总行，结果一致；
3. 覆盖率总比 92.00% → 92.01%（新增 `tests/test_app_idle.py` 不计语句，波动来自行号漂移）。
