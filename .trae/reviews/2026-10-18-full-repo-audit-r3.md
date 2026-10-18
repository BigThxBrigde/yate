# 2026-10-18 全仓库多维度审核（第三轮，新 worktree 重跑）

- 分支：`enh/repo-audit-r3`（worktree `../yate-repo-audit-r3`，沙箱 `.venv` 新建重建）
- 范围：按用户指令**新建 worktree 与分支**、不复用 `yate-full-repo-audit` / 其分支，
  对全仓库 **12 个维度**做一轮**全新**只读审计 + 确证缺陷修复
- 形态：**只读事实文档**（doc-conventions §二.1）；修复动作归方案
  [`../documents/full-repo-audit-r3-fixes-plan.md`](../documents/full-repo-audit-r3-fixes-plan.md)
- 交叉引用：前两轮审计
  [`../reviews/2026-10-16-full-repo-audit.md`](../reviews/2026-10-16-full-repo-audit.md)、
  [`../reviews/2026-10-17-full-repo-audit.md`](../reviews/2026-10-17-full-repo-audit.md)、
  [`../reviews/2026-10-17-full-repo-audit-code-review.md`](../reviews/2026-10-17-full-repo-audit-code-review.md)；
  本轮沿用主计划 [`../documents/full-repo-audit-plan.md`](../documents/full-repo-audit-plan.md)
  为 governing plan，在新分支独立重跑。

## 一、门禁复测（主代理亲跑，新 worktree 沙箱）

| 门禁 | 命令 | 结果 |
|---|---|---|
| pyright strict | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | **0 errors / 0 warnings / 0 informations**，exit 0 |
| 架构守卫 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | **32 passed**，exit 0 |
| 全量回归 | `.venv\Scripts\python.exe -m pytest tests/ -q`（重定向防探针超时） | exit 0（2480 passed / 9 skipped，与前轮一致） |
| 覆盖率 | `--cov --cov-fail-under=75` | **91.95% ≥ 75%**，exit 0（前轮 91.94%） |

四道门禁全绿；新分支相对主干仅新增本轮 3 处修复 + 测试，无回归。

## 二、审计执行方式

5 个只读 `code-explorer` 子代理并行覆盖 12 维度（批内 ≤5，符合
subagent-workflow 上限 6），各子代理只输出 `文件:行号 → 证据 → 结论`，不改文件。
维度分工：SA（功能正确性 + 健壮性）、SB（安全性 + 性能）、SC（可维护性 + 可扩展性）、
SD（项目结构 + 职责单一 + 架构边界）、SE（门禁 + 文档规范 + 纪律）。

## 三、逐维度结论（摘要）

| 维度 | 结论 | 关键发现 |
|---|---|---|
| 1 功能正确性 | **1 个 MAJOR** | `session.py:181-197` `close_under` 删除"活动文档前方"的标签后，活动标签被数值 clamp 静默切走（已修复 F1） |
| 2 安全性 | **1 个 HIGH（已修复 F2）** | 项目级 `yaterc` 启动时自动 `exec` 却绕过 `is_trusted` 门控，与 `extensions/` 受信任保护的对称被打破（RCE 级风险） |
| 3 性能 | 0 缺陷，2 疑点（需 profiler） | `buffer._snapshot` 每键全量行拷贝、`get_text` 全量 join；按 §6.3.1 不无依据优化 |
| 4 可维护性 | 多项 MINOR/NIT | 死常量 `ERR_REQUEST_CANCELLED`（已修复 F3）；`themes.py` 三套 `Theme(...)` 构造器 ~34 参数近字重复；个别安全上限未收口为命名常量 |
| 5 健壮性 | 全合规 | 零裸 `except`；42 处 `except Exception` 全部带 `BLE001`；无静默吞咽（`logs.py` 崩溃处理器内 `pass` 为刻意设计） |
| 6 可扩展性 | MINOR | 键映射名 `"vsc"/"vim"` 在 `config`/`editor`/`api`/`cli`/`commands` 多处硬编码，新增键映射需改 ≥5 处（建议收敛到 `VALID_KEYMAPS` 单一来源 + `KeymapSet.names()`） |
| 7 项目结构 | 健康 | `_LAYER_RANKS` 固化 L0–L4；无循环依赖（唯一向上边 statusbar→extensions 已冻结） |
| 8 模块职责 | 已知豁免项 | 5 个 `SIZE_EXEMPT_FILES` 与 §三.7 名单一致；`editor.py`(~1024) 为已知 god-module 候选、已登记下一 big-module-split 目标 |
| 9 架构边界 | 全合规 | 9 类守卫在代码内 **0 违规**：`TYPE_CHECKING`/相对导入/命名守卫/`App[Any]`/`self.app`/类级 `ScrollBar.renderer`/devtools 通道/`Protocol`/向上连线均达标；32 用例与 §六 守卫项一一对应 |
| 10 门禁规则 | 健康 | `typeCheckingMode=strict`、pytest+cov 75、changelog 门禁、`test_architecture.py` 守卫在 GitHub/Gitee 双 CI 均落地 |
| 11 文档规范 | 存量待迁移 | `ext-api-parity-plans/plan_a~d.md` 下划线分词违反 §一/§六（前轮 F-12 登记不修）；多份计划/评审文档残留真实本机路径 `D:/Programming/yate-*`（前轮 F-10 登记不修）；双语成对 / 日期前缀 / 相对路径引用均合规 |
| 12 纪律 | 主体合规 | 代码注释/docstring 全英文（仅 2 处中文为 zh 用户手册回退文案，属 misc-rules §四例外）；300/300 `.py` 含 `from __future__ import annotations`；提交信息规范因快照无 `.git` 未能核查 |

## 四、本轮确证修复（F1 / F2 / F3）

| 编号 | 维度 | 文件:行 | 修复 |
|---|---|---|---|
| F1 | 1 功能正确性（MAJOR） | `yate/session.py:181` `close_under` | 用"活动文档身份"重算 `self.index`：活动标签存活时 `self.docs.index(active)`，被删时回退邻居（与 `close_active` 一致）；并补回归测试 `test_close_under_keeps_the_active_tab_when_a_preceding_tab_is_closed` |
| F2 | 2 安全性（HIGH） | `yate/yaterc.py:99` `default_rc_paths` | 自动发现的项目级 `yaterc` 仅在 `is_trusted(here)` 时加载，与 `extensions/` 自动装载走同一信任门控；用户级 `~/.yate/yaterc` 与显式 `-u` 不受影响；补 `test_default_rc_paths_skips_untrusted_project_rc` 并让既有两测试先 `trust_workspace` |
| F3 | 4 可维护性（MINOR） | `yate/editor_lsp/client.py:45` | 删除全仓零引用的死常量 `ERR_REQUEST_CANCELLED` |

修复复测：改动文件 pyright 0/0/0；`test_session.py` / `test_config.py` 全绿；全量 pytest + 覆盖率 91.95% 全绿（见 §一）。

## 五、延续"登记不修"项（前轮裁定 + 本轮复核，不重复误修）

- `themes.py` 主题构造器重复（MINOR）：属"非受控重复"，重构有主题正确性风险，登记待办。
- 键映射名硬编码（MINOR）：扩展性成本，登记待办（建议方案已在 §三维度6 给出）。
- 性能疑点（§三维度3）：须先 profiler 实测，不无依据优化。
- 文档下划线分词 / 真实路径暴露（F-11/F-10）：存量随下次修改迁移，登记不修。
- `editor.py` god-module（维度8）：已登记为下一 big-module-split 目标。

## 六、结论

- 门禁四道全绿（pyright 0/0/0、架构 32 passed、pytest exit 0、覆盖率 91.95%）。
- 全新 12 维度审计共确证 **1 MAJOR + 1 HIGH 真实缺陷 + 1 MINOR 死常量**，全部已修复并补测试；
  其余为存量受控风格 / 需 profiler / 登记不修项。
- 架构边界、健壮性异常纪律、文档命名、future-import 纪律等**整体合规**，未发现新违规。
- 本轮为独立重跑，未触碰前两轮分支；改动仅落于新分支 `enh/repo-audit-r3`。

## 七、增记（2026-10-18，repo-audit-r2 评审回改）

- F2 的信任锚点由 `is_trusted(here)`（启动目录）修订为 `is_trusted(project.parent)`
  （rc 文件所属目录）：`here` 锚点存在「父目录残留放行」与「子目录启动假阴性」
  两个边界缺陷，且与扩展门控「锚定 cwd」的注释自述不符。同步修订见
  `full-repo-audit-r3-fixes-plan.md` F2 行；跳过时的用户可见提示随
  `default_rc_paths(notes=...)` 出参上浮到启动消息面（W3），双语手册
  `yaterc.{en,zh}.md` 加载顺序表已同步。
