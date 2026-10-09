# closure-sweep-structure-plan-b（任务 3：模块结构清晰度审查）

来源：用户指令「检查各个模块内结构是否合理清晰」。
前置参照：[2026-10-07 仓库架构全量评审](../../reviews/2026-10-07-repo-architecture-audit.md)
（A1–A20 已于 `ref/repo-audit-fixes` 处置，本计划只核增量）。

## 一、审计结论（实测证据）

1. **架构守护**：`python -m pytest tests/test_architecture.py -q` → 28 passed（含 R1–R13、
   体量阈值、包根惰性、命名守卫、能力注入、回调别名、support_mouse 闸门）。
2. **分层无回归**：pyright strict 0 诊断 + R1–R13 守卫全绿，2026-10-07 审计后的
   修复未出现结构性回退。
3. **新发现 S1——体量豁免名单行数过期**（A11 §三.7 要求名单与规则文本同步维护）：
   - `keymaps/vim.py` 实测 1021 行（规则文本记 1117）；
   - `editor.py` 实测 851 行（规则文本记 933）；
   - `editor_core/buffer.py` 实测已低于 800 行阈值（拆词运动后），**仍在
     `SIZE_EXEMPT_FILES` 与规则文本名单内**，应出名单。
4. **新发现 S2——体量守卫盲区**：`test_source_files_within_size_threshold` 只扫
   `yate/`；`tools/pack/wiki.py` 实测 **1304 行** 超阈值且无任何守卫面。
   单一职责（pack wiki 站点生成 + 翻译 + 进度，2026-10-06 三轮评审均在同一文件收敛），
   按评审 A11 判据可登记豁免，但守卫必须先覆盖到 tools/ 才有"登记"可言。
5. **新发现 S3——`closes_block` 未接线**（与 reviews #25 G9-3 同源）：判为
   已标记实验性接缝（docstring 已声明"本版未接线"），维持现状，闭环登记不改码。

## 二、实施步骤

### S1 豁免名单同步（含规则文本）

- 改动文件：`tests/test_architecture.py`（`SIZE_EXEMPT_FILES` 移除
  `editor_core/buffer.py` 并更新注释）、`.trae/rules/architecture-boundaries.md`
  （§三.7：buffer.py 移出名单；vim.py / editor.py 行数更新为 1021 / 851）。
- 验收：`python -m pytest tests/test_architecture.py -q` 全绿
  （buffer.py 低于阈值，移出后仍通过）。

### S2 体量守卫扩展到 tools/

- 改动文件：`tests/test_architecture.py`（`_python_files` / 守卫用例把
  `tools/` 纳入扫描，键为相对仓库根 posix 路径；`SIZE_EXEMPT_FILES` 增加
  `tools/pack/wiki.py`，注释附单一职责理由与行数）。
- 同步：`.trae/rules/architecture-boundaries.md` §三.7 补 tools/ 纳入守卫与
  wiki.py 豁免登记。
- `tests/` 不纳入（测试文件体量不设限，与现状口径一致）。
- 验收：`python -m pytest tests/test_architecture.py -q` 全绿；
  负向演练——临时把 wiki.py 从豁免移除应失败（演练后还原）。

### S3 closes_block 闭环登记

- 不改码。在 `closure-sweep-reviews-plan-c.md` 的闭环登记表记录裁决
  （实验性接缝已标记，移除属产品决策）。

## 三、备选与否决

| 备选 | 否决理由 |
|---|---|
| 拆分 `tools/pack/wiki.py`（1304 行） | 近三轮评审（#29/#31/#33）均在该文件收敛且行为正确；拆分是纯结构工程，混入本轮修复轮会放大回归面——登记豁免并保留未来拆分选项 |
| 守卫扩展到 tests/ | 测试体量与可读性取舍不同，规则从未约束；扩面只会制造噪音 |
| 强制接线或删除 closes_block | 接线是 issue IKJMQ2 明确的"V1 可选"非目标；删除丢失已验证契约，维持已标记现状 |

## 四、风险与回滚

守卫扩面可能暴露未知超阈值 tools 文件：实施前先全量扫描 tools/ 实测
（已知仅 wiki.py 超阈），如另有新 offender 按同判据逐个裁决并登记。
回滚：revert 单提交。

## 五、执行结果回填（2026-10-09）

- **S1 修正**：豁免名单行数经守卫口径（`splitlines()`）复测为 vim.py 1117 /
  editor.py 933 / buffer.py 820——原名单行数**本就正确**，§一.3 的"行数过期"
  系初扫 `Measure-Object -Line`（不计空行）口径失真的误报，撤销；buffer.py
  维持豁免。规则文本仅补口径修正注记。
- **S2 已落地**：体量守卫扩展到 `tools/`（wiki.py 1487 行登记豁免，注释附
  单一职责理由）；负向演练：移除豁免后守卫捕获 `('tools/pack/wiki.py', 1487)`，
  恢复后全绿；`tests/` 按计划不纳入。
- **S3**：维持现状，已在 plan-c §三登记。
- 提交：`7781cf7`（测试 + 规则同步单笔）。偏离：无。
