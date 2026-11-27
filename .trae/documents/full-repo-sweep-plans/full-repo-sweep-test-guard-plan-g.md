# B3 + R2：进程内体积守卫与规则文本同步（计划 g）

> **实施状态**：✅ 已实施 —— 2026-11-20（`e6723300`，覆盖率双口径 exit 0）

父计划：[../full-repo-sweep-plan.md](../full-repo-sweep-plan.md)。

## 输入

- `../../../tests/test_macro_wiring.py:95-125` 嵌套了 `subprocess.run([sys.executable, "-m", "pytest", ...])`，该代码仅在并行覆盖率下失败（`1 failed / 3961 passed`）。
- `../../rules/architecture-boundaries.md:331-337` 称 `keymaps/vim.py` 为 1595 行（实际 1679），`:389-396` 称 `editor_components/view.py` 为 824 行（实际 879），`:67` 称 37 个守卫（实际 45；`:508` 处的 §六 已是 45）。其余五个豁免文件也比上次记录的数字多 1。
- `../../../tests/test_architecture.py:377-385` 中的 `SIZE_EXEMPT_FILES` 有正确的 7 个键；`:919-941` 内联了体积检查循环；`:1828-1844` 仅检查 `editor.py` 的归属关系和集合大小。

## 独占文件

- `../../../tests/test_architecture.py`
- `../../../tests/test_macro_wiring.py`
- `../../rules/architecture-boundaries.md`

## 设计

1. 将 `test_source_files_within_size_threshold` 的函数体提取为 `test_architecture.py` 中的模块级函数 `size_exemption_violations() -> list[str]`；现有测试调用它并断言返回空列表。无行为变更。
2. 在 `test_architecture.py` 中添加 `SIZE_EXEMPT_LINE_COUNTS: dict[str, int]`，包含**最终实测**的七个键的 `splitlines()` 行数，取值时点为波次 1 和 2 均已落地之后（波次 3 刻意延后）。添加 `test_size_exemption_line_counts_match_rule`，解析新规则表（如下），并断言每个键/数对都与常量**以及**实际文件行数一致。
3. 在 `../../rules/architecture-boundaries.md` §三.7 中添加一个 7 行表格（标题例如 `Current measured line counts (2026-11-20)`），列为 `exempt file | lines`；更新 `vim.py`、`view.py` 以及五个 +1 文件中已过时的正文数字，并将 `:67` 的守卫数从 37 改为 45。保留历史沿革文字，但使其最新数字与表格一致。
4. 重写 `test_macro_wiring.py` 中的 `test_size_exemption_rule_and_guard_are_in_sync`：保留规则/常量的字符串断言，遍历全部七个键（断言每个键同时出现在常量块和规则表中），并将嵌套的 pytest 替换为通过 `importlib.util.spec_from_file_location` 加载的 `size_exemption_violations()` 进程内调用（tests 不是包）。断言返回列表为空。仅当文件中没有其他测试使用 `sys` / `subprocess` 时才移除这些现已未用的导入（`:183-191` 仍使用 `sys`/`subprocess` 做 pyright 检查——保留它们）。

## 测试

- `test_size_exemption_line_counts_match_rule`（新增，位于 `test_architecture.py`）：对 7 个键中的每一个，从规则表中解析反引号内的路径和整数；断言 `parsed == SIZE_EXEMPT_LINE_COUNTS[key] == len(file.read_text(encoding="utf-8").splitlines())`；断言解析出的键集合等于 `set(SIZE_EXEMPT_FILES)`。
- `test_size_exemption_rule_and_guard_are_in_sync`（重写）：断言 7 个键中的每一个都出现在规则表和守卫集合中；断言 `size_exemption_violations() == []`；不使用 subprocess pytest。
- 保持 `test_editor_size_exemption_is_registered`（`:1828-1844`）不变。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests/test_macro_wiring.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n 1
```

通过标准：两次覆盖率运行均 exit 0 且无测试失败；架构测试数量变为 46；规则表数字与 `splitlines()` 输出一致。

## 风险 / 回滚

风险：行数表在后续编辑中会过时；这正是预期的预警信号，波次 5 / 评审迭代必须重新测量。回滚：仅在进程内守卫无法可靠加载时才恢复 subprocess 测试和旧规则数字；记录证据。
