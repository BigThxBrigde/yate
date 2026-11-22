# 2026-11-20 全仓库多维扫描（只读）

- 基线：本地 `master` `f7e34c34`（落后 `origin/master` 14 提交；以本地工作树为准）。
- 方法：`multi-dim-review` 技能 13 维度，5 个只读分区审查员两波 fan-out
  （SA 正确性/健壮性/安全、SB 算法/性能、SC 架构/结构、SD 类型/风格/并发、
  SE 测试/文档），主代理逐条回读、机械取证、剔除已闭环/误报后亲跑门禁。
- 产物：可贴单的 issue 文本见 [../documents/full-repo-sweep-issue-brief.md](../documents/full-repo-sweep-issue-brief.md)。
- 本轮**不修改产品代码**；修复另按 `plan-before-execute.md` 立项。

Overall: REQUEST_CHANGES — 1 MAJOR（D4 热路径 O(D) 诊断扫描）+ 6 MINOR，
0 BLOCKER；4 条 Suspects、5 条 Suggestions；审查员另报 2 条候选经实测反证撤回。

## 一、维度总表

| 维度 | 结论 | 关键证据 / 代表反证 |
|---|---|---|
| D1 正确性 | 1 MINOR | `../../yate/services/workspace.py:547-559` `move_entry` 缺 `copy_entry:519-545` 的自嵌套守卫；undo delta / pane-tree identity / take-peek 契约均有守卫 |
| D2 健壮性 | 1 MINOR | `../../yate/yaterc_options.py:186-195` `isdigit()` 接受 `²` 后 `int()` 抛裸 `ValueError`，经 `yaterc.py:213-216` 中断后续选项提取 |
| D3 安全 | clean | 项目 rc / 工作区主题 / 扩展自动加载均有 trust gate；`.yxp` casefold + 符号链接防护在位；`shell=True` 是设计内完全权限接口 |
| D4 复杂度 | **1 MAJOR** + 1 MINOR | `../../yate/editor_lsp/manager.py:793-808` 弃用现成 per-row 索引做 O(D) 全表扫描；`../../yate/editor_core/diff.py:153-199` O(k²) 归并为 MINOR |
| D5 性能 | 3 SUSPECT | palette 全量 sort / completion 并集 / 跨行诊断索引膨胀；均为常数因子或需真实负载，按纪律保留不升级 |
| D6 架构边界 | clean（1 SUGGESTION） | `UPWARD_EDGES_FROZEN` 空集、R14 门面 14 名、R2 白名单 4 类、UI_FROZEN_FILES 与规则一致；`diagnostics.py` 同层反向边未画入依赖图 |
| D7 结构职责 | 2 MINOR / SUGGESTION | `bridges.py` 678 行十域；规则文本 3 处行数/守卫数漂移（`vim.py` 1678 vs 1595、`view.py` 878 vs 824、守卫 45 vs 44） |
| D8 类型纪律 | clean | `Optional[`/`Union[`/`TYPE_CHECKING`/相对导入 = 0；4 类 `type: ignore` 均带理由注释，命中 §4.2 例外 |
| D9 风格 | clean | "8 处行宽 >100"实测全部恰好 100（合规）；ASCII 注释守卫与非 ASCII 豁免账本一致；`print()` 仅在白名单 |
| D10 并发可观测 | 1 SUSPECT | 5 处 `is_dir/stat` 的 `OSError` 静默降级；属良性降级且已有用户反馈，显著性需实测，降级为 suspect |
| D11 测试 | 1 MINOR | `tests/test_macro_wiring.py:111-125` 嵌套 pytest 在覆盖率 `-n auto` 下失败（串行/单点均绿）；"caplog 缺 propagate"已撤回 |
| D12 文档 | 3 MINOR / 1 需裁决 | `overview.md` 生成器断言与计数失真、近期计划状态块/本机路径/相对路径冲突、`tests/README.md` 计数过期、reviews 索引编号缺口 |
| D13 门禁 | 全部 exit 0 | 并行覆盖率 1 failed 属测试基础设施 flake，`-n 1` 全绿；详见 §四 |

## 二、Findings

### [MAJOR] `../../yate/editor_lsp/manager.py:793-808` — `diagnostic_at` 弃用现成索引

Problem: `_index_diagnostics`（`763-773`）每次 publish 重建 `_diagnostics_by_row[uri][row]`，
`diagnostics_on_line`（`810-821`）已 O(1) 用它；但 `diagnostic_at` 仍走
`diagnostics_for(doc)`（`784` 复制整表）后逐条比较，位于 `refresh_ui → _refresh_lsp →
lsp_sync.update_echo`（`../../yate/editor.py:447-453,499-503`、
`../../yate/flows/lsp_sync.py:95-101`）热路径，D 可达数百上千条。
Fix: 用 `by_row = _diagnostics_by_row.get(uri, {}).get(row, ())`，仅对 k 条做原 col /
severity 判断；补多诊断同行的等值对照用例。O(D) → O(k_row)，临时空间 O(D) → O(1)。

### [MINOR] `../../yate/services/workspace.py:547-559` — `move_entry` 缺自嵌套守卫

Problem: `copy_entry:519-545` 有 `target.resolve().relative_to(src.resolve())` 守卫，
`move_entry` 只有 `target.exists()`；`../../yate/editor_components/file_manager/screen.py:1007`
的 cut→paste 可把目录粘进自身子树，跨卷 `shutil.move` 的 copy+delete 路径有递归风险。
Fix: 复用祖先判定抛 `OSError`，补 cut-parent-into-child 回归用例。

### [MINOR] `../../yate/yaterc_options.py:186-195` — Unicode 数字触发裸 `ValueError`

Problem: `str.isdigit()` 接受 `²`，`int('²')` 抛 `ValueError`；冒泡到
`../../yate/yaterc.py:213-216` 后错误文案失真，且 `_extract_options` 在 `485-487`
提前中断，跳过 file_preview / large_file。
Fix: 改 `isdecimal()` + 局部 `try/except ValueError` 追加友好错误，补 `"²/8"` 用例。

### [MINOR] `../../yate/editor_core/diff.py:153-199` — diff3 每 region 重扫 opcodes/changes

Problem: `_side_span`（`286`）与四个 `any(...)` 从头遍历，整体 O(k²)；有 debounce 与
cancel，非每击键，故不升 MAJOR。Fix: 单调双游标一次推进降 O(k)。

### [MINOR] `../../.trae/rules/architecture-boundaries.md:331-337,389-396,508` — 规则文本漂移

Problem: 实测 `vim.py` 1678（写 1595）、`view.py` 878（写 824）、架构守卫 45（写 44）；
`SIZE_EXEMPT_FILES` 成员正确，但 `test_macro_wiring.py:95-125` 只比对 `editor.py` 一个数。
Fix: 同步三处文本，并把 7 个豁免文件的行数集中成表逐项守卫。

### [MINOR] `../../tests/test_macro_wiring.py:111-125` — 嵌套 pytest 在并行覆盖率下失败

Problem: 覆盖率 `-n auto` 实测 `1 failed, 3961 passed, 10 skipped`；`-n 1` 全量与
单点均 exit 0。该用例 `subprocess.run([sys.executable, "-m", "pytest", ...])` 与
pytest-cov/xdist 环境继承冲突（2026-11-09 hover-docs 已记同类根因）。
Fix: 改进程内调用守卫（precedent：R15 进程内重构），或显式清理 `COV_CORE_*` / `PYTEST_*`。

## 三、Suspects

- `[SUSPECT] ../../yate/editor_components/palette.py:272-302` — 每击键全量评分 + 全量 sort；
  需测候选规模分布后才决定 top-k 是否用 `heapq`。
- `[SUSPECT] ../../yate/editor_components/completion.py:273-286,452-457` — 每行词集有版本缓存，
  并集每次重做；有 120ms debounce + `items[:64]` 截断，收益需 profiler。
- `[SUSPECT] ../../yate/editor_lsp/manager.py:769-773` — 一条跨全文件诊断按行展开会膨胀索引到
  O(文件行数)；需采样真实 publish 负载或压测。
- `[SUSPECT] ../../yate/flows/document_flows.py:52-55` 等 5 处 `is_dir/stat` 的 `OSError` 静默降级 —
  属良性降级且有用户反馈，是否需 `log.debug` 取决于显著性实测。

## 四、Suggestions / Deferred

- `[SUGGESTION] ../../yate/services/extensions/bridges.py:1-7` — 678 行十域子包化，保持门面
  14 名与内部再导出兼容；中等成本、无行为变化。
- `[SUGGESTION] ../../yate/diagnostics.py:25` — 用只读 `DiagnosticsInput` 快照解除同层反向边。
- `[SUGGESTION] ../../yate/services/workspace.py:116-311` — ignore 子系统独立成模块，低优先。
- `[SUGGESTION] ../../.trae/documents/overview.md:14,23-27` — 生成器脚本不存在却称"不会漂移"；
  147 篇（实测 566 个 md / 151 个状态块）与 9 个近期计划漏登；状态块与本机路径见
  `toggle-comment-plan.md:7`、`macro-record-replay-unified-plans/overview.md:3-4`、
  `tests/README.md:15-16`（98/134、150 → 实测 149/169）。
- `[DEFERRED] ../../.trae/reviews/README.md:381-389` — 速览表漏登 #59–#61 / #67–#72；
  存在编号分歧登记，需作者确认收录口径后决定补行或加表头说明。
- `[DEFERRED] 4 类 type/pyright ignore 站点` — 均带理由注释，命中 `python-coding-style.md` §4.2 例外。
- 已闭环/明确不修项复核：#47 性能审计、#48/#49 yxp 与信任门控、#57 算法项、#76 规则漂移、
  soft-wrap span 复用、take/peek 契约全部未见回归，按登记不重提。

## 五、审查员候选撤回（反证）

1. "8 处行宽 >100 字符"：主代理用 `splitlines()` 实测全部**恰好 100**，规则为 ≤100 → 合规，删除。
2. "caplog 缺 `propagate=True` 致恒真"：当前 pytest `_pytest.logging.catching_logs` 会向所有
   non-propagating logger 直接挂 handler；`tests/test_pack_wiki_lint.py` +
   `tests/test_theme_palettes.py` 定点跑 exit 0，正/负向断言均有效 → 删除。
3. "move_entry 与 shell/yaterc exec 同类风险"：仅前者保留，后两者有 trust gate 与显式权限语义。
4. "view.py 继续拆 mixin / editor_dispatch 尾部 import 改 `TYPE_CHECKING` / wiki 门面改惰性"：
   分别受 §三.7 豁免、R6 + 冻结 Protocol、big-module-split-2 兼容面约束 → 删除。

## 六、门禁实测（主代理亲跑）

| 命令 | 结果 / 退出码 |
|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors / exit 0 |
| `pytest tests/ -q -n auto` | exit 0 |
| `pytest tests/test_architecture.py -q` | 45 passed / exit 0 |
| `pytest tests/ --cov=yate --cov-branch -n auto` | 1 failed / 3961 passed / 10 skipped，93.14%（flake，见 §二） |
| `pytest tests/ --cov=yate --cov-branch -n 1` | 3962 passed / 10 skipped，93.09% / exit 0 |
| `python -m tools.smoke_test run --jobs 4` | 124/124 scenarios · 1511/1511 checks / exit 0 |
| `python -m tools.changelog check` | exit 0（unreleased 滞后 165 提交属生成器机制） |

## 七、Strengths

- 低复杂度选择已构建期化：buffer bisect 区间表、highlight dirty-range + 后台 worker、
  completion weakref 有界缓存、project_search budget 截断，绝大多数热路径无需 profiler 即可确认。
- 45 条架构守卫覆盖 R1–R15；`UPWARD_EDGES_FROZEN` 空集，冻结白名单与规则文本成员一致。
- 双语手册成对、CHANGELOG 生成器可校验、`tests/README.md` 以行为域组织测试的思路清晰（仅计数快照需刷新）。
