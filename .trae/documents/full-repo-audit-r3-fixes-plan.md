# full-repo-audit-r3-fixes-plan

- 分支：`enh/repo-audit-r3`（worktree `../yate-repo-audit-r3`，沙箱 `.venv` 新建重建）
- 日期：2026-10-18
- 状态：无人值守执行（22:00–06:00 规则，方案批准按通过处理，本行即为批准登记）
- 唯一规范来源：[`../rules/`](../rules/) 下全部 8 个规则文档；评审事实
  [`../reviews/2026-10-18-full-repo-audit-r3.md`](../reviews/2026-10-18-full-repo-audit-r3.md)
- 关联主计划：[`full-repo-audit-plan.md`](full-repo-audit-plan.md)（本轮在新分支独立重跑）

## 一、目标与非目标

**目标**：关闭本轮全新 12 维度审计确证的 **3 个真实缺陷**——

- F1（维度1 MAJOR）：`session.py` `close_under` 活动标签静默切走；
- F2（维度2 HIGH）：项目级 `yaterc` 绕过 `is_trusted` 自动 `exec`；
- F3（维度4 MINOR）：`editor_lsp/client.py` 死常量 `ERR_REQUEST_CANCELLED`。

并补对应回归测试，使门禁终态可核实。

**非目标**：

- 不重铺前两轮已覆盖且代码未变的维度结论（架构/健壮性/命名等已在本轮子代理复核为合规）；
- 不顺手重构 `themes.py` 构造器重复、键映射名硬编码（维度4/6 MINOR，登记待办）；
- 不无 profiler 依据做性能优化（维度3 疑点）；
- 不触碰"登记不修"文档存量（下划线分词 / 本机路径暴露）；
- 闭环内只提交不推送（收尾是否推送以用户后续指令为准）。

## 二、修复项与独占文件清单

| 编号 | 文件:行 | 改动 | 独占文件 |
|---|---|---|---|
| F1 | `yate/session.py:181` `close_under` | 活动标签存活则按身份重算 `self.index`，被删则回退邻居 | `yate/session.py` |
| F1·测试 | `tests/test_session.py` | 新增 `test_close_under_keeps_the_active_tab_when_a_preceding_tab_is_closed` | `tests/test_session.py` |
| F2 | `yate/yaterc.py:99` `default_rc_paths` | 项目级 `yaterc` 仅当 `is_trusted(project.parent)` 加载（**2026-10-18 评审修订**：锚点由 `here`（启动目录）改为 rc 文件所属目录——`here` 锚点存在两个边界缺陷：信任库记录 repo 本身时，repo 的**父**目录里的 rc 会被放行（安全残留）；`yate sub/dir/file.py` 启动时子目录不在信任库（假阴性）。`is_trusted` 从模块级导入并新增 `notes` 出参，跳过时附用户可见提示） | `yate/yaterc.py` |
| F2·测试 | `tests/test_config.py` | 既有两测试加 `trust_workspace`；新增 `test_default_rc_paths_skips_untrusted_project_rc` | `tests/test_config.py` |
| F3 | `yate/editor_lsp/client.py:45` | 删除死常量 `ERR_REQUEST_CANCELLED` | `yate/editor_lsp/client.py` |

独占文件清单（互不重叠）：`yate/session.py`、`tests/test_session.py`、`yate/yaterc.py`、
`tests/test_config.py`、`yate/editor_lsp/client.py`。

## 三、验收命令（worktree 沙箱解释器）

每文件改动后：

```powershell
.venv\Scripts\python.exe -m pyright yate/session.py yate/yaterc.py yate/editor_lsp/client.py
.venv\Scripts\python.exe -m pytest tests/test_session.py tests/test_config.py -q
```

收尾全量门禁（主代理亲跑）：

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q --cov --cov-fail-under=75
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

判定：pyright 0/0/0、pytest exit 0、架构 32 passed、覆盖率 ≥75% 方过；任一红门禁回修。

## 四、风险与回滚

| 风险 | 缓解 / 回滚 |
|---|---|
| F1 改 `close_under` 影响删除流 | 保留并扩展既有 `close_under` 测试；新增回归测试锁定"活动标签保活"语义；`close_active` 未动 |
| F2 改变项目 `yaterc` 加载行为 | 仅影响"未信任目录 + 有项目 yaterc"的窄场景（与 `extensions/` 自动装载行为对齐，更安全）；用户级 `~/.yate/yaterc` 与显式 `-u` 不受影响；既有两测试已改为先 `trust_workspace` |
| F3 删常量引发引用缺失 | 全仓 grep 零引用（含测试），删后 pyright + 全量测试零回归 |
| 误修"登记不修"项 | 非目标显式排除；改动文件清单仅 5 个，无越界 |

## 五、步骤-提交对照（执行后回填）

| 步骤 | 提交 | 内容 |
|---|---|---|
| Step 1 | `176d40f` | `fix(session): keep active tab when a preceding tab is closed`（session.py + test_session.py） |
| Step 2 | `fbb9945` | `fix(security): gate auto-loaded project yaterc behind workspace trust`（yaterc.py + test_config.py） |
| Step 3 | `6bc750c` | `refactor(lsp): drop unused ERR_REQUEST_CANCELLED constant`（client.py） |
| Step 4 | `30eee0d` | `docs(reviews): add 2026-10-18 full-repo-audit-r3 record` |
| Step 5 | `12f458f` | `docs(plan): add full-repo-audit-r3 fixes plan` |

## 六、偏离记录

- 本轮按用户指令新建 worktree/分支（不复用 `yate-full-repo-audit`），主计划沿用既有
  `full-repo-audit-plan.md`，未另起方案文档（避免重复铺开）。
- 子代理复核确认前两轮"登记不修"项（主题构造器重复 / 键映射硬编码 / 文档分词与路径暴露）
  仍属受控风格，本轮不修。
- 闭环内推送：本计划不授权推送；若收尾需推送，须用户显式指令。
