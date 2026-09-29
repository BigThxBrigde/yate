# yate Code Review — 日志/devtools 桥接评审（PR #28 Gitee AI 审查）— 2026-09-27

## 日志/devtools 桥接评审（fix/logging-tracing-wt）— 2026-09-27

> **范围**：PR #28 `refactor(logging): mount the devtools bridge on the app lifecycle`
> （`fix/logging-tracing-wt` → `master`），关联本文件上方同日评审轮。本次登记
> **Gitee AI 队友审查**（[原始评论](https://gitee.com/jermaine/yate/pulls/28#note_51377137_conversation_190973698)，
> 审查时间 2026-09-27 10:30）：结论 ⚠️ **无阻断项，3 个改进建议，可优化后合并**；风险等级
> **low**。四维度判定：功能性与逻辑 ⚠️ 待优化；安全性 ✅ 通过；性能 ⚠️ 待优化；
> 可维护性 ⚠️ 待优化。AI 核查确认核心桥接生命周期管理（按身份摘除、重挂载防泄漏）、
> tracing 闸门语义、`driver_windows.py` 违规清除均正确，无功能性回归风险。
> 处置：3 项建议全部采纳修复（commit `c13f407`），逐项核实如下。

- [x] **文档用例计数与实际不符（功能性与逻辑）** —
  [architecture-boundaries.md §六](../rules/architecture-boundaries.md) 声称 16 个用例，
  `tests/test_architecture.py` 实有 18 个 `test_` 函数（master 原 14 + 本 PR 新 4）——计数
  过时会误导维护者对守卫覆盖面的判断。
  *✅ 已修复（2026-09-27，`c13f407`）——§六 计数改为 18（实测 `pytest tests/test_architecture.py`
  → 18 passed 与 grep `^def test_` = 18 双重核实）。*

- [x] **UI-free 守卫显式 targets 缺存在性校验（可维护性）** —
  [test_architecture.py](../../tests/test_architecture.py)
  `test_ui_free_layers_do_not_import_textual_app` 显式拼接的 targets（含 `logs.py`）若将来
  文件被重命名/删除，`_module_imports` 会抛裸 `FileNotFoundError`，报错不指向"守卫清单
  过期"这一真实原因。
  *✅ 已修复（2026-09-27，`c13f407`）——解析前补
  `assert path.exists(), f"stale UI-free guard target: {path}"`，失败信息直指过期目标。*

- [x] **守卫对同一批文件重复 `ast.parse`（性能）** —
  [test_architecture.py](../../tests/test_architecture.py)
  `_module_imports` 与 `_devtools_log_accesses` 各自独立 parse，全仓扫描与 L0 扫描反复
  解析重叠文件，随仓库增长开销线性放大。
  *✅ 已修复（2026-09-27，`c13f407`）——抽出 `_parsed_tree(path)`，以 `(path, mtime)` 为键
  的模块级 dict 缓存 parse tree（AI 原建议即此方案；中途误用 `ast.parse(cache=True)`——
  该参数不存在——已被守卫运行时抓出并改正）。*

> **登记说明**：本节登记时未发现 AI 意见与事实不符的误报项；3 项建议均属低成本改进。
> 用例计数错误根因：`036bd2a` 新增守卫后未同步 §六 的 16 这个数字（该数字自 PR #25
> 登记起沿用），已在过程上注意——改守卫数量时必须同步规则文档计数。
