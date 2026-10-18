# 2026-10-18 pr-review · `ref/repo-audit-r2` 分支审查（PR 级 AI 预审）

- 审查对象：分支 `ref/repo-audit-r2`（worktree `../yate-repo-audit-r2`），base = master `9e84e97`
  （merge-base），变更 44 文件 / +3621 −51（含 `enh/full-repo-audit`、`enh/repo-audit-r3` 合并内容）
- 方法：`pr-review` 技能六维框架（功能正确性 / 安全 / 性能 / 可维护性 / 架构边界 / 硬门禁），
  主代理亲自逐文件读 diff 并独立重跑全部门禁
- 形态：**只读事实文档**（doc-conventions §二.1）——只记录发现与核对结论；修复动作归方案
  [`../documents/repo-audit-r2-review-fixes-plan.md`](../documents/repo-audit-r2-review-fixes-plan.md)

---

## 一、实测门禁（主代理亲跑，worktree 沙箱 `.venv`，Python 3.13.2）

| 门禁 | 命令 | 结果 |
|---|---|---|
| pyright strict | `python -m pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations`（exit 0） |
| pytest（无插桩） | `python -m pytest tests/ -q` | 全绿（exit 0） |
| 覆盖率 | `python -m pytest tests/ -q --cov=yate --cov-branch` | 92.00%，`fail_under=75` 通过 |
| 架构 + 门禁配置 | `python -m pytest tests/test_architecture.py tests/test_gate_config.py -q` | 40 passed（架构 35 + 门禁 5），与规则 §六「35 个用例」一致 |
| 冒烟 | `python -m tools.smoke_test run --skip-slow --json --report` | 107/107 场景、1304/1304 checks，exit 0（Windows 本机；`--skip-slow`） |

## 二、发现（1 MAJOR + 5 MINOR）

### F1 [MAJOR] `yate/app.py:262` — `poll_idle` 空屏幕栈竞态抛 `ScreenStackError`

覆盖率插桩（`--cov`）下全量运行 **3/3 次**各失败 1–2 例，失败用例分属三个**本分支未改动**的文件：

| 运行 | 失败用例 |
|---|---|
| 1 | `tests/test_app_render.py::test_doc_search_debounce_merges_rapid_typing` |
| 2 | `tests/test_app_manual.py::test_shell_command_runs_without_freezing_ui`、`tests/test_completion_popup.py::test_escape_dismissal_survives_a_pending_debounce` |
| 3 | `tests/test_app_find_replace.py::test_project_replace_end_to_end_open_edit_replace` |

第 3 次取到的根因（未被改动的代码抛错）：

```text
textual.app.ScreenStackError: No screens on stack
  yate/app.py:262 in poll_idle → if isinstance(self.screen, ScreensaverScreen):
```

即 1 秒 idle 轮询定时器在 app 屏幕栈已空（teardown 期）访问 `self.screen`。对照样本：
不带 `--cov` 全量 1/1 通过；失败用例单独/按文件重跑通过（`test_app_render.py` + `test_manual.py`
15 passed）；master 同条件带 `--cov` 对照 1 次通过（对照样本仅 1 次，归因存保留）。
影响面：`.github/workflows/test.yml` 的 test job 正是带 `--cov` 运行，本分支又新增 pilot 密集的
smoke job，整体 pilot 负载上升。

### F2 [MINOR] 局部 `--cov` 运行被 `fail_under=75` 判红，逃生口径只写在 pyproject 注释

实测 `pytest tests/test_app_render.py --cov=yate` → `ERROR: Coverage failure: total of 32 is less
than fail-under=75`（exit 1）。单点源目标达成，但「局部运行须加 `--cov-fail-under=0`」未进规则面。

### F3 [MINOR] `.workflow/test.yml:69` — 注释与新口径矛盾

命令已去掉 `--cov-fail-under=75`，该行注释仍写 `# --cov uses the [tool.coverage.*] config in
pyproject; fail-under stays identical`（文件头第 22 行已是正确口径，第 69 行漏改）。

### F4 [MINOR] `.github/workflows/test.yml:91` — 新增 smoke job 的 Linux 腿未经验证

job 在 `ubuntu-latest` / `windows-latest` 双腿跑 `python -m tools.smoke_test run --json --report`
（20 分钟预算）。命令形状与 Windows 腿已实测（107/107，90s，`--skip-slow`）；CI 跑的是完整
112 场景（含 `slow` 标记），Linux 腿（TERM / 字体 / 终端探测）本地无法复现，红灯即挡 PR。

### F5 [MINOR] 新增计划文档自身携带本机真实路径（doc-conventions §五）

`repo-audit-r2-architecture-plan-d.md:126,135,145,238,278`、
`repo-audit-r2-doc-hygiene-plan-a.md:40,202`、`repo-audit-r2-plans/overview.md:133`
出现 `d:\Programming\yate\...`、`d:\Programming\fake` 形态——正是本轮审计在 doc-conventions §五
立为「禁」的形态（部分为反例/证据引用，部分为演练命令），且源码面已上守卫、文档面没有。
与「存量 42 处随下次修改迁移」的既有裁定是两回事：这些是**新增**文件。

### F6 [MINOR] `.trae/reviews/README.md` — 三条 2026-10-18 评审记录未进索引

`2026-10-18-full-repo-audit.md` / `2026-10-18-full-repo-audit-r3.md` / `2026-10-18-repo-audit-r2.md`
未按 doc-conventions §二.1 登记进目录索引（表格最后一条为 2026-10-17）。

## 三、核对结论（无发现项）

- 信任门控锚点正确：`yate/yaterc.py:121` 以 rc 所属目录（`project.parent`）而非 cwd 判定，
  `is_trusted` 内部 `resolve()`，相对/短名/符号链拼写均归一；跳过原因经 `notes` 回传
  `cli.py:403` 合入 `config.errors` 并进启动告警；双语手册同步。
- 测试污染已根除：`tests/` 内全部 `trust_workspace` / `is_trusted` 调用点均已重定向
  `TRUST_FILE`（test_config / test_extensions / test_app_lsp / test_trust）。
- 静默吞异常补齐处（`editor_lsp/manager.py` didClose/didSave、`services/fonts.py`、
  `services/user_setup.py`）均为惰性 `%` 日志（R12 合规），并各配「反向路径不产生噪声」对照用例。
- `yate/session.py` close_under 焦点保持改动正确：`Document` 为普通类（恒等相等），
  `self.docs.index(active)` 按身份取回，无结构性相等的误配风险。
- `tests/test_gate_config.py` 的场景数下限 19 与实测一致（21 文件 − 2 包模块）。

## 四、结论

```text
Overall: REQUEST_CHANGES — 1 MAJOR（F1：覆盖率负载下的 pilot 时序抖动，合并前需确认）
```

是否合入由人类评审者决定；F1 建议合并前在同条件（带 `--cov` 全量）下再各跑一次分支与 master 定性。
