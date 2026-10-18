# 2026-10-18 全仓库多维度审核（续作增量轮）

- 分支：`enh/full-repo-audit`（worktree `../yate-full-repo-audit`）
- 范围：续作轮——复用既有 worktree 与其沙箱 `.venv`，无新代码 delta
- 形态：**只读事实文档** —— 只记录发现与核对结论，不含修复排期以外的代码改动
  （doc-conventions §二.1）；修复动作归方案
  [`../documents/full-repo-audit-continue-fixes-plan.md`](../documents/full-repo-audit-continue-fixes-plan.md)
- 交叉引用：主计划 [`full-repo-audit-plan.md`](../documents/full-repo-audit-plan.md)、
  前轮评审 [`2026-10-16-full-repo-audit.md`](../reviews/2026-10-16-full-repo-audit.md)、
  [`2026-10-17-full-repo-audit.md`](../reviews/2026-10-17-full-repo-audit.md)、
  [`2026-10-17-full-repo-audit-code-review.md`](../reviews/2026-10-17-full-repo-audit-code-review.md)

## 一、续作判定（为何是增量而非全量重审）

- `git diff $(git merge-base master HEAD) HEAD -- yate/ tools/` **为空**：本分支 HEAD
  （`970b598` Merge branch 'master' into enh/full-repo-audit）相对主干共同祖先的
  `yate/`、`tools/` 树与主干完全一致——前两轮审计的修复均已合入主干，本分支无未合入
  代码 delta。
- 结论：对 12 维度做"全量重铺"属纯冗余（主计划 §四 方案 C 已裁掉同类重复）；本轮按
  `full-repo-audit-plan.md` 的"增量复核 + 只认确证真问题修复"纪律，只做：
  1. 门禁终态复测（维度 10）；
  2. 静态守卫 + 安全面回归扫描（维度 9 / 2 / 5 增量）；
  3. 关闭前轮登记的**唯一真代码缺陷** F-7（维度 5 健壮性）；
  4. 核验前轮 code-review 发现 C-3 / C-6 是否已在库内落地（维度 11 / 9）；
  5. 显式登记前轮"登记不修"项，避免重复误修。

## 二、门禁复测（主代理亲跑，worktree 沙箱）

| 门禁 | 命令 | 结果 |
|---|---|---|
| pyright strict | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | **0 errors / 0 warnings / 0 informations**，exit 0 |
| 架构守卫 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | **32 passed**，exit 0 |
| 全量回归 | `.venv\Scripts\python.exe -m pytest tests/ -q`（重定向防探针超时） | exit 0（2480 passed / 9 skipped，与前轮一致） |
| 覆盖率 | `--cov --cov-fail-under=75` | **91.96% ≥ 75%**，exit 0（前轮 91.94%，持平微升） |

四道门禁全绿，无红门禁。

## 三、增量发现

### 维度 5 健壮性 — 关闭 F-7（前轮登记待办，本次修复）

前轮 `2026-10-16-full-repo-audit.md` 登记 F-7：`editor_lsp/manager.py:366-368,444-447`、
`services/user_setup.py:278-280`、`services/fonts.py:224-227` 共 4 处**实质静默吞异常**
（无 log 无反馈，字面违反 python-coding-style §4.5 第 3 条）。本轮确证并修复：

| 文件:行 | 原状 | 修复 |
|---|---|---|
| `yate/editor_lsp/manager.py:367` | `except (LspError, OSError): pass`（didClose 通知失败静默） | `log.debug("didClose notify failed for %s", uri)` |
| `yate/editor_lsp/manager.py:446` | `except (LspError, OSError): pass`（didSave 通知失败静默） | `log.debug("didSave notify failed for %s", state.uri)` |
| `yate/services/user_setup.py:279` | `except OSError: pass`（空基目录 rmdir 清理静默） | `log.debug("could not remove empty base dir %s", base)` |
| `yate/services/fonts.py:226` | `except OSError: pass`（重复字体 unlink 静默） | `log.debug("could not remove duplicate font %s", dup)` |

- `manager.py` / `fonts.py` 已有 `log = tracing.get_logger(__name__)`；
  `user_setup.py` 此前无 logger，本次补 `from yate.logs import tracing` +
  `log = tracing.get_logger(__name__)`（模块顶部，符合 R12 日志统一规范）。
- 级别选 `debug`：四处均为 fire-and-forget 通知 / best-effort 清理，记录即满足 §4.5
  "至少记录日志"，且不向常规运行引入噪声。
- 复测：改动文件 pyright 0/0/0；全量 pytest + 覆盖率 91.96% 全绿（见 §二）。

### 维度 9 架构 / 维度 11 文档 — 核验 C-3、C-6 已落地（非本次引入）

前轮 code-review（[`2026-10-17-full-repo-audit-code-review.md`](../reviews/2026-10-17-full-repo-audit-code-review.md)）
C-3 / C-6 经主代理本轮实测已在库内解决，无需重复修复：

- **C-3** `tests/README.md` 模块计数过期（原 "139"）：现文为
  "94 of the 124 `yate/` modules, counting `*.py` excluding `__init__.py`；
  `yate/` holds **140** `.py` files in total"——已同步为 140 并重述口径，实测
  `pathlib` 清点 `yate/` 恰 140 个 `.py`，一致。
- **C-6** §一 清单相对 `_LAYER_RANKS` 少 3 名：L4 行已列 `__main__.py`
  （"L4 外壳：app.py / cli.py / __main__.py（`python -m yate` 入口 shim…）"），
  L0 行已列 `yaterc.py` / `yaterc_options.py`（"…/ config / yaterc.py /
  yaterc_options.py /"），与守卫表口径对齐。

### 维度 9 / 2 / 5 回归扫描（增量，确认无新违规）

只读探针（worktree 沙箱解释器）：

| 探针 | 期望 | 实测 | 结论 |
|---|---|---|---|
| 相对导入 `from .` / `from ..`（yate+tools+tests） | 0 | **0** | 合规（守卫 `test_no_relative_imports` 之外再证） |
| `if TYPE_CHECKING:` 实际块（yate+tools） | 0 | **0**（仅 `tests/test_architecture.py:22` docstring 提及、`:460` 断言字符串，非真实块） | 合规 |
| 命名守卫 `*Feature/*Host/*Ops/*Delegate/*Controller/AppProtocol`（yate AST 标识符） | 0 | **0**（`editor.py:869` "Delegated" 为 docstring 散文，非标识符，误报排除） | 合规 |
| `shell=True`（yate+tools） | 存量 2，无新增 | `services/shell.py`、`tools/pack/wiki.py` 共 **2**，与前轮一致 | 无新增面 |
| `exec(` / `eval(`（yate+tools） | 存量（`yaterc.py` / `theme_files.py` / lua runtime，均带 `# noqa: S102` 注记） | 无新增 | 无新增面 |

## 四、延续"登记不修"项（前轮裁定，本轮不重复误修）

- **F-3** `keymaps/vim.py` count 无上界（`9999999999j` 型挂起）：前轮裁定"需用户超长键入
  触达、非外部不可信输入，登记不修"——本轮维持，不改产品源码。
- **F-10** `tools/probes/verify_matrix.ps1` 中文注释 / 引述性中文：规则空白待裁决，
  前轮"登记不修"——维持。
- **F-11** `2026-09-26-readonly-feature.md` 文件名命中 `*-feature` 后缀禁令：存量随下次
  修改迁移，前轮"登记不修"——维持（重命名会破坏既有引用）。
- **F-12** `documents/ext-api-parity-plans/` 下划线分词：存量随下次修改迁移，前轮"登记不修"
  ——维持。
- **P-1~P-5** 性能疑点：修复须先 profiler 实测（python-coding-style §6.3.1），前轮登记待办，
  本轮未做无实测支撑的优化。

## 五、结论

- 门禁四道全绿（pyright 0/0/0、架构 32 passed、pytest exit 0、覆盖率 91.96%）。
- 唯一确证真代码缺陷 F-7（4 处静默吞异常）已修复并复测通过。
- 前轮 code-review 遗留项 C-3 / C-6 经核验已在库内落地，未重复修复。
- 静态守卫 + 安全面回归扫描零新增违规。
- 其余 12 维度结论沿用前两轮审计记录（代码未变更，主计划 §四 增量纪律），不重铺。
