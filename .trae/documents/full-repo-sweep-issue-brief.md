# 全仓库扫描修复：issue 简报

- 来源 issue：<https://gitee.com/jermaine/yate/issues/IKWXU4>（标题：`ENH - FULL-REPO SWEEP: LSP DIAGNOSTIC HOT PATH, ROBUSTNESS GUARDS, RULE-TEXT DRIFT AND DOC INDEX CLEANUP`，创建于 2026-11-20 22:08，标签 `docs` / `bug` / `enhancement` / `performance`）。
- Worktree：`yate-full-repo-sweep`；分支：`feature/fix-full-repo-sweep`；父级：本地 `master` 位于 `ebe8fee6`（已与 `origin/master` 同步；issue 文本使用的是较早的 `f7e34c34` 基线，因此所有行号都必须在本分支上重新核实）。
- 用户指令（2026-11-20，无人值守窗口）：不提问、不审批；严格按项目纪律执行；每完成一批即提交；迭代闭环直到不再有 issue 发现项。
- 来源评审记录（本地，在主 worktree 中未提交）为 `../reviews/2026-11-20-full-repo-review.md`；本 worktree 不得修改或提交它。

## issue 报告的基线门禁结果（不得在此作为证据复用）

| 门禁 | 报告的结果 |
|---|---|
| `pyright yate/ tests/ tools/ pack/` | exit 0 |
| `pytest tests/ -q -n auto` | exit 0 |
| `pytest tests/test_architecture.py -q` | 45 passed（规则文本仍写 44） |
| coverage `-n 1` | 3962 passed / 10 skipped，93.09% |
| coverage `-n auto` | 1 failed / 3961 passed，93.14%（见 B3） |
| `smoke_test run --jobs 4` | 124/124 场景，1511/1511 检查 |
| `tools.changelog check` | exit 0 |

## 待解决的发现项

### 重构建议

- **R1（建议，中等）**：`yate/services/extensions/bridges.py` 有 678 行，自述十个能力领域；`yate/services/extensions/api.py:33-47` 从它导入 13 个名字，门面又重新导出 5 个。拆分为 `bridges/` 子包（按领域划分为 3-4 个内部模块），并用 `__init__` 重新导出每一个现有名字。必须保持 R14（机制留在 `services/extensions/` 内）、冻结的 14 名字门面以及直接内部模块测试可用；主要风险是循环导入。
- **R2（应修复，低风险）**：规则文本漂移 —— `architecture-boundaries.md:331-337` 称 `keymaps/vim.py` 为 1595 行（报告 1678）、`:389-396` 称 `editor_components/view.py` 为 824（报告 878）、`:508` 称 45 个架构守卫（报告 45 而文本写 44）。`SIZE_EXEMPT_FILES` 的 7 个成员正确，但 `tests/test_macro_wiring.py:95-125` 只断言 `editor.py` 的数字。同步三处文本位置，将 7 个实测行数集中为一张规则表，并让守卫逐项比较。不改变行为，不新增豁免。
- **R3（建议，可选）**：`yate/diagnostics.py` 在第 25/82/131/268/298/355/399 行仅为报告签名从 `yate.editor` 导入 `Editor`；依赖图只画了 `ED -> DIAG`，且 `cli.py:31-33` 记录了 TUI 栈拖拽问题。建议修复：由 L4 的 `cli.py:507-524` 构造一个只读 `DiagnosticsInput` 数据类快照并传给 `format_report` / `print_report`，移除 diagnostics 到 editor 的导入；成本中等，`tests/test_diagnostics.py` 许多调用点需要一个构造器。
- **R4（建议，低）**：`services/workspace.py`（737 行）有一个自包含的 ignore 子系统（`_IgnorePattern`、`_parse_ignore`、`_load_root_ignores`、`_dir_ignores`、`_is_ignored`、mtime 缓存、`_DIR_IGNORE_CACHE_MAX`）。可用薄委托方式移至 `services/workspace_ignores.py`；仅提升可读性，不改变行为。

### 文档修复

- **D1（应修复）**：`.trae/documents/overview.md:14` 声称索引由 `tools/_gen_index.py` 从共享数据生成，但不存在这样的脚本；`:23-27` 声称 147 篇文档，而报告实测 566 个 markdown 文件 / 151 个状态块。九篇最近的 2026-11 计划（soft-wrap、toggle-comment、macro-record-replay-unified、pack-dist-zip、which-key-auto-trigger、filemgr-wrapup、lsp-hover-docs、readme-screenshots、extension-trust-hardening）没有索引条目。更正或删除生成器声明，增量添加 2026-10-05 之后带状态块的计划，刷新计数并记录核实日期。
- **D2（应修复）**：`.trae/documents/toggle-comment-plan.md:7` 暴露了本地 worktree 路径（违反 `doc-conventions.md` §五）。`.trae/documents/macro-record-replay-unified-plans/overview.md:3-4` 与 §五 矛盾，称仓库引用相对于仓库根目录。`toggle-comment-plan.md` 及其他近期计划缺少统一的 `> **实施状态**：...` 块；`which-key-auto-trigger-plan.md:7` 和 `soft-wrap-plans/overview.md:3` 使用临时状态文本。只添加标题行；不要重写正文。
- **D3（应修复）**：`tests/README.md:15-16` 仍称 134 个 `yate/` 模块中有 98 个、以及 150 个 `.py` 文件；报告实测 149 个非 `__init__` 模块 / 169 个 `.py` 文件。使用动态的“由 `test_architecture.py` 守卫”表述，或刷新计数并附上测量日期。
- **D4（需裁决）**：`.trae/reviews/README.md` 快速表格跳过 #59-#61 和 #67-#72（它们只出现在正文中）。这些缺口已有编号分歧说明（`README.md:181-183,308-318`）。确定一种口径：添加 9 行并附分歧说明，或在表头声明只列出 master 序号。注意：本分支不包含主 worktree 中未提交的 2026-11-20 索引行，因此不要在此引用它们。

### 性能

- **P1（MAJOR，最高优先级）**：`yate/editor_lsp/manager.py:793-808` 的 `diagnostic_at` 调用 `diagnostics_for(doc)`（在 `:784` 复制整张表）并扫描每条诊断，而 `:763-773` 已在每次发布时重建 `_diagnostics_by_row[uri][row]`（唯一写入在 `:733-734`），`:810-821` 的 `diagnostics_on_line` 以 O(1) 使用它。热路径：`yate/editor.py:447-453 refresh_ui -> :499-503 _refresh_lsp -> yate/flows/lsp_sync.py:95-101 update_echo -> diagnostic_at`。修复：查找 `by_row = self._diagnostics_by_row.get(uri, {}).get(row, ())`，并将原有的列重叠与严重度逻辑仅应用于这 k 条诊断；保留单行、多行和 `doc.path is None` 语义；添加一个在同一行有多条诊断的等价性测试以及一个大 D 用例。O(D) -> O(k_row)，空间 O(D) -> O(1)。
- **P2（MINOR）**：`yate/editor_core/diff.py:153-199` 的 `diff3_regions.classify` 为每个区域重新扫描 opcode/change（`:286` 的 `_side_span` 加上 `:161-169` 的四个 `any(...)`），O(k^2)。opcode 和 change 按基准行排序；使用两个单调游标实现 O(k)。k 通常很小且有防抖，故为 MINOR。
- **P3（可疑项，不可丢弃）**：`yate/editor_components/palette.py:272-302` 每次按键都全量重新打分 + 全量排序（在 `heapq` 之前需要候选规模分布）；`yate/editor_components/completion.py:273-286,452-457` 的逐行词集有版本缓存，但每次补全都重建并集（120 ms 防抖，`items[:64]` 截断）；`yate/editor_lsp/manager.py:769-773` 一条跨文件的诊断会扩展到每一行（需要真实发布负载采样）。若不修复，为每一项登记“needs profiler / needs real load”理由。评审还列出 5 处静默 `is_dir/stat` 的 `OSError` 兜底（`yate/flows/document_flows.py:52-55` 及同类）作为良性降级可疑项。

### 健壮性 / 测试基础设施

- **B1（MINOR）**：`yate/services/workspace.py:547-559` 的 `move_entry` 缺少 `copy_entry:519-545` 具有的自嵌套守卫（`target.resolve().relative_to(src.resolve())`）。从 `yate/editor_components/file_manager/screen.py:1007` 将父目录剪切到子目录中可能递归或失败。复用祖先检查，抛出 `OSError("cannot move ... into itself")`，添加一个包含模拟跨卷分支的回归用例。先写负向测试。
- **B2（MINOR）**：`yate/yaterc_options.py:186-195` 使用 `isdigit()`，它接受 `²`，而 `int("²")` 抛出裸 `ValueError`；这会冒泡到 `yate/yaterc.py:213-216` 并在 `:485-487` 中止 `_extract_options`，跳过 file_preview 和 large_file。改用 `isdecimal()` 加上局部 `try/except ValueError`，追加一条友好的 `config.errors` 消息；添加一个 `"²/8"` 用例，断言消息以及后续选项仍被提取。先写负向测试。
- **B3（MINOR，测试基础设施）**：`tests/test_macro_wiring.py:111-125` 嵌套了 `subprocess.run([sys.executable, "-m", "pytest", ...])`，它仅在并行覆盖率下失败（`1 failed / 3961 passed`），而单点和 `-n 1` 运行退出 0。替换为进程内守卫调用（导入并运行 `test_architecture.py::test_source_files_within_size_threshold` 的判定逻辑），或在保留子进程时显式清除 `COV_CORE_*` / `PYTEST_*` 环境变量。验收：coverage `-n auto` 与 `-n 1` 均 exit 0 且无失败测试。

## 验收标准（逐字意图）

1. P1 使用按行索引，并具备逐场景行为等价性（严重度优先级、多行范围、`doc.path is None`），另加一个大 D 单元测试。
2. B1 / B2 各有一个先红后绿的负向测试；单个 yaterc 错误不再跳过后续选项。
3. R2 的三个数字与现实一致；7 个豁免文件的行数逐项检查。
4. D1 / D2 / D3 的计数、路径、状态块和生成器声明与当前代码一致。
5. B3 的修复使 coverage `-n auto` 与 `-n 1` 一致（均 exit 0，零失败）。
6. 全量门禁 exit 0：pyright（包括 `pack/`）、pytest `-n auto`、架构测试、coverage >= 75%、smoke、`tools.changelog check`。
7. 每一个未修复的 P3 可疑项都有已登记的“needs profiler / needs real load”理由。

## 已排除 / 已关闭（不可重开）

`shell=True`、yaterc `exec`、主题文件 `exec`、扩展自动加载（trust 门控）；`.yxp` casefold 与符号链接、`take_dirty_range` 与 `dirty_range`、撤销 delta、窗格树身份（#47/#48/#49 已关闭）；进一步的 `view.py` mixin 拆分、`editor_dispatch.py` 通过 `TYPE_CHECKING` 的尾部导入、`tools/pack/wiki/__init__.py` 门面简化（§三.7 豁免、R6/冻结 Protocol、big-module-split-2 兼容面）。已撤回的评审候选：8 行“超过 100 字符”实际正好 100（合规），缺少 `caplog.propagate` 在当前 pytest 下是误报。四处 `type: ignore` / `pyright: ignore` 均有理由且在 §4.2 例外范围内。
