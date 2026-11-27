# R4：提取 workspace ignore 子系统（计划 l）

> **实施状态**：✅ 已实施 —— 2026-11-20（`dd61c63f`，ignore 子系统 L0 迁移）

父计划：[../full-repo-sweep-plan.md](../full-repo-sweep-plan.md)。

## 输入

`../../../yate/services/workspace.py:19,35,39` 的常量、`:117` 的 `_IgnorePattern`、`:139-146,183-195` 的状态、`:179-197` 的 `_load_root_ignores`、`:199-236` 的 `_parse_ignore`、`:238-265` 的 `_dir_ignores`、`:267-311` 的 `_is_ignored`、`:643` 的 `_anchored_match` 构成一个自包含子系统。消费方为 `list_dir :315-342`、`walk_files :344+`、`../../../tests/test_workspace_filter.py` 以及 `../../../yate/editor_components/explorer.py:23`（导入 `IGNORED_NAMES`）。没有闭包；状态存放在 `self` 加上模块常量中。

## 独占文件

- `../../../yate/services/workspace.py`
- 新文件 `../../../yate/services/workspace_ignores.py`
- 新测试 `../../../tests/test_workspace_ignores_module.py`

## 设计

1. 新建 L0 模块 `workspace_ignores.py`，拥有 `IGNORED_NAMES`、`IGNORE_FILENAMES`、`_DIR_IGNORE_CACHE_MAX`、`_IgnorePattern`、`_parse_ignore`、`_anchored_match`，以及一个 `IgnoreIndex` 类，持有 `root_ignores`、`root_has_anchored` 和以 mtime 为键的 `dir_ignore_cache`。`IgnoreIndex` 暴露 `set_root(root)`、`ignored(path, is_dir, dir_ignores=None)` 和 `dir_ignores(directory)`，算法与缓存淘汰阈值保持不变。
2. `Workspace` 保留轻量的委托私有方法，名称/签名不变（`_load_root_ignores`、`_parse_ignore`、`_dir_ignores`、`_is_ignored`），由 `self._ignore_index` 支撑；`IGNORED_NAMES` 仍从 `workspace.py` 再导出，使 `explorer.py:23` 和现有测试继续工作。再导出的说明写在新模块的 docstring 中（依据 `../../rules/architecture-boundaries.md` §三.5，L0 叶子包允许带说明的有限再导出）。
3. 无行为变更：后匹配优先、否定、锚定规则、注释/空行跳过、mtime 缓存同一性以及在 `_DIR_IGNORE_CACHE_MAX` 处清空整个缓存，都必须保持一致。不得新增 `editor_components` 导入（R4 守卫）。
4. 两个文件都必须保持在 800 `splitlines()` 以内；无需也不得新增豁免。

## 测试

- 现有 `../../../tests/test_workspace_filter.py` 的所有用例必须原样通过（`test_comments_and_blank_lines_skipped`、`test_negation`、`test_last_match_wins`、`test_anchored_rules_are_skipped_outside_the_root`、`test_set_root_reloads_ignores`、`test_load_root_ignores_without_a_root`）。
- `test_ignore_subsystem_lives_in_dedicated_module`（新测试文件 `../../../tests/test_workspace_ignores_module.py`——执行时加入独占文件）：断言 `_IgnorePattern`、`_parse_ignore`、`_anchored_match` 是在 `workspace_ignores.py` 中定义的（而非仅仅导入）；断言 `Workspace._is_ignored` 的源码是轻量委托（≤ 5 行源码）；断言 `from yate.services.workspace import IGNORED_NAMES` 仍可解析。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests/test_workspace_filter.py tests/test_workspace_file_manager.py tests/test_workspace_ignores_module.py -q
.venv\Scripts\python.exe -m pyright yate/services/workspace.py yate/services/workspace_ignores.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 风险 / 回滚

风险：缓存同一性的改变会在文件编辑后改变 ignore 结果。回滚：恢复 `workspace.py` 中的内联方法和常量并删除新模块；没有其他文件直接依赖新模块。
