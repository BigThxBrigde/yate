# full-repo-audit-continue-fixes-plan

- 分支：`enh/full-repo-audit`（worktree `../yate-full-repo-audit`，沙箱 `.venv` 复用）
- 日期：2026-10-18
- 状态：无人值守执行（22:00–06:00 规则，方案批准按通过处理，本行即为批准登记）
- 唯一规范来源：[`../rules/`](../rules/) 下全部 8 个规则文档；评审事实
  [`../reviews/2026-10-18-full-repo-audit.md`](../reviews/2026-10-18-full-repo-audit.md)
- 关联主计划：[`full-repo-audit-plan.md`](full-repo-audit-plan.md)（续作，非新开维度铺开）

## 一、目标与非目标

**目标**：关闭前轮审计登记的唯一真代码缺陷 **F-7**（4 处实质静默吞异常，违反
python-coding-style §4.5 第 3 条），并复测四道门禁，使续作轮门禁终态可核实。

**非目标**：

- 不做全量 12 维度重审——`git diff merge-base..HEAD -- yate/ tools/` 为空，前两轮审计
  修复已合入主干，代码未变更（见评审记录 §一）；
- 不触碰前轮"登记不修"项（F-3 / F-10 / F-11 / F-12 / P-1~P-5）；
- 不新增架构规则，不顺手重构；
- 闭环内只提交不推送（收尾是否推送以用户后续指令为准）。

## 二、修复项（唯一一项，独占文件清单）

| 编号 | 文件:行 | 改动 |
|---|---|---|
| F-7a | `yate/editor_lsp/manager.py:367` | `except (LspError, OSError): pass` → `log.debug("didClose notify failed for %s", uri)` |
| F-7b | `yate/editor_lsp/manager.py:446` | `except (LspError, OSError): pass` → `log.debug("didSave notify failed for %s", state.uri)` |
| F-7c | `yate/services/user_setup.py:279` | `except OSError: pass` → `log.debug("could not remove empty base dir %s", base)`；模块顶部补 `from yate.logs import tracing` + `log = tracing.get_logger(__name__)` |
| F-7d | `yate/services/fonts.py:226` | `except OSError: pass` → `log.debug("could not remove duplicate font %s", dup)` |

独占文件清单（4 文件，互不重叠，单笔提交）：

- `yate/editor_lsp/manager.py`
- `yate/services/user_setup.py`
- `yate/services/fonts.py`

## 三、验收命令（worktree 沙箱解释器）

每文件改动后：

```powershell
.venv\Scripts\python.exe -m pyright yate/editor_lsp/manager.py yate/services/user_setup.py yate/services/fonts.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

收尾全量门禁（主代理亲跑）：

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q --cov --cov-fail-under=75
```

判定：pyright 0/0/0、架构 32 passed、pytest exit 0、覆盖率 ≥75% 方过；任一红门禁回修。

## 四、风险与回滚

| 风险 | 缓解 / 回滚 |
|---|---|
| 新增 `log.debug` 改变行为 | 仅新增日志行，不改变控制流；四处均为 fire-and-forget / best-effort 路径，零行为影响 |
| `user_setup.py` 新增 logger 引入导入循环 | `yate.logs` 为 stdlib-only 导入面（R12），不依赖 `services`，无循环风险；pyright + 全量 pytest 实测零回归 |
| 误修"登记不修"项 | 本计划非目标显式排除 F-3/F-10/F-11/F-12/P-1~P-5，改动文件清单仅 3 个，无越界 |

## 五、步骤-提交对照（执行后回填）

| 步骤 | 提交 | 内容 |
|---|---|---|
| Step 1 | `ffc15cf` | `fix(robustness): log swallowed notification/cleanup exceptions (F-7)` —— 3 文件 |
| Step 2 | `42524b8` | `docs(reviews): add 2026-10-18 continuation audit record` |
| Step 3 | `9e2b324` | `docs(plan): add full-repo-audit continue fixes plan` |

## 六、偏离记录

- 本轮未做全量重审：依据 `git diff merge-base..HEAD -- yate/ tools/` 为空（评审记录 §一），
  与前轮主计划 §四 增量纪律一致，不重复铺开。
- 闭环内推送：本计划不授权推送；若收尾需推送，须用户显式指令（区别于前轮 Step 9 的
  统一推送授权）。
