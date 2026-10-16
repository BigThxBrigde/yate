# repo-structure-layering-audit-review-fixes —— 子计划总纲

- 主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md)
- 来源：[`../../reviews/2026-10-17-repo-structure-layering-audit.md`](../../reviews/2026-10-17-repo-structure-layering-audit.md)
- 分支 / worktree：`enh/full-repo-audit` / `../yate-full-repo-audit`
- 日期：2026-10-17
- 唯一规范来源：本总纲 + 各子计划 + 主计划 + [`../../rules/`](../../rules/) 全 8 个规则文档。
  子代理执行时**以各自子计划为唯一规范来源**，不得凭常识增删。

## 一、目标与非目标

**目标**（全部为口径/登记/文档一致性修复 + 新增 1 条守卫，不改产品行为）：

| 编号 | 修复项 | 子计划 |
|---|---|---|
| Fix-A | S-1：登记 `keymaps/base.py -> yate.session` 例外（保留既有层秩切分，见主计划 §四 方案 B 否决） | [plan-a](repo-structure-layering-audit-review-fixes-rules-plan-a.md) |
| Fix-B | S-2：登记 L2→L3 扩展门面例外（`editor_view/statusbar.py`） | plan-a |
| Fix-C2 | S-7：登记 `editor_view/theme.py` 门面再导出例外 | plan-a |
| Fix-C4 | S-8：登记 `dist_meta.py` 层级 + 守卫面 | plan-a（规则侧）/ plan-b（守卫面） |
| Fix-C3 | S-4：登记 `services/yxp.py` 归属（规则侧）/ 门户 docstring（代码侧） | plan-a（规则侧）/ plan-d（代码侧） |
| Fix-C1 | S-6：`tests/README.md` 失效路径与覆盖表口径 | plan-c |
| Fix-D | S-1/S-2 可执行化：层秩向上连线白名单守卫（32 个用例） | plan-b |
| Fix-D2 | S-11：wheel 资源清单取证（只读） | plan-e |

**非目标**（另案，本轮硬性排除）：S-3 `editor_view/` 子域化、S-5 `tools/pack` 改名、
S-9 `editor.py` 拆分、S-10 `tests/` 目录化、6 包导入环重构。

## 二、子计划索引与波次

| 波次 | 子计划 | 独占文件清单 | 执行者 |
|---|---|---|---|
| wave-1 | [plan-a rules](repo-structure-layering-audit-review-fixes-rules-plan-a.md) | `.trae/rules/architecture-boundaries.md` | plan-executor #1 |
| wave-1 | [plan-b guard](repo-structure-layering-audit-review-fixes-guard-plan-b.md) | `tests/test_architecture.py` | plan-executor #2 |
| wave-2 | [plan-c tests-readme](repo-structure-layering-audit-review-fixes-tests-readme-plan-c.md) | `tests/README.md` | plan-executor #3 |
| wave-2 | [plan-d services-init](repo-structure-layering-audit-review-fixes-services-init-plan-d.md) | `yate/services/__init__.py` | plan-executor #4 |
| wave-3 | [plan-e wheel-probe](repo-structure-layering-audit-review-fixes-wheel-probe-plan-e.md) | 无（只读取证） | 主代理 |
| wave-3 | 全量门禁 + 评审 + 回填 | 主计划 §七、审计记录 §四 | 主代理 |

波次纪律：同波文件互不重叠；上一波验收退出码全 0 才进下一波；波次不改排（变更须回填并附实测依据）。
计划见 [`../../../.trae/rules/task-orchestration.md`](../../rules/task-orchestration.md) §二。

## 三、跨子计划一致性契约（硬性）

1. **守卫白名单**（plan-b 落盘内容必须与 plan-a 登记语句一致，逐字如下）：

   ```
   keymaps/base.py -> yate.session
   editor_view/statusbar.py -> yate.services.extensions
   editor_view/statusbar.py -> yate.services.extensions.bridges
   ```

   实测依据（本总纲亲测，主代理复跑）：在"`keymaps/base|vim|vsc` = L0、`keymaps/__init__.py` 与
   `keymaps/registry.py` = L1、`extensions/` 不参与层秩"的表下，全仓向上连线**恰为上述 3 条**。
2. **规则用例计数**：plan-b 落地后 `pytest tests/test_architecture.py -q` 必须为 **32 passed**；
   plan-a 的 §六 计数与对照表按 32 回填。两处不一致 = 阻塞。
3. **口径**：`extensions/`（随包插件示例）在层秩守卫中**跳过**，其门面纪律由 R14 守卫覆盖
   （`test_extension_machinery_hides_behind_facade`）。

## 四、统一验收（wave-3，主代理亲跑）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/ -q --cov --cov-fail-under=75
```

本批含代码/测试改动（`yate/services/__init__.py`、`tests/test_architecture.py`、`tests/README.md`），
**不适用** [`misc-rules.md`](../../rules/misc-rules.md) §三 的纯文档豁免。

## 五、风险与回滚

| 风险 | 缓解 / 回滚 |
|---|---|
| 规则文本编辑破坏内部一致（§一/§二/§三.5/§六 四处互引） | plan-a 逐处锚点核对 + `keymaps` 残留语句 grep 归零；单笔 `git revert` |
| 守卫误报（层秩表与实际不符） | 白名单已按实测 3 条冻结；未列明模块按 L0 计并在失败信息指引登记；负向演练取证 |
| plan-a / plan-b 并行导致白名单与登记措辞不一致 | §三.1 逐字契约 + 主代理收口复核（两边逐字比对） |
| docstring 改动触发门禁 | 按 §四 跑全量，不走豁免 |
| 子代理零产出 | spawn 后同回合探活；判死改主代理亲自执行并如实标注 |

## 六、回填位

- 主计划 §七（门禁前后数字、步骤-提交对照、负向演练输出、wheel 结论、偏离记录）；
- 审计记录 §四 处置列（S-1/S-2/S-6/S-7/S-8 → 已修；S-4 → 规则+文档侧已修，代码结构侧登记）。
