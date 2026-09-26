# Plan SP2 — 架构守卫 + 规则与账目文档回填

> 状态：⏳ **待实施** · 前置：[Plan SP1](plan_SP1_decouple.md) ✅ · 后置：[Plan SP3](plan_SP3_gate_commit.md)
> 工作量：M · 步骤：S2.1 → S2.2 → S2.3 串行；S2.4 / S2.5 / S2.6 纯文档互不依赖，可并行
> 决策依据（注入回调 vs 下沉）：[README §2](README.md#2-方案比选与决策)。

---

## 1. 步骤表

| 步 | 动作 | 输入 | 输出 | 验收 |
|---|---|---|---|---|
| S2.1 | test_architecture.py `UI_FREE_FILES` 增 `"config.py"`（注释注明 N30 来源） | SP1 完成 | 守卫生效 | `pytest tests/test_architecture.py -q` → **13 passed**（扩员不新增用例，仅扩大既有 R4 用例覆盖面） |
| S2.2 | **负向验证**：临时在 config.py 加回惰性 `from yate.editor_view import theme` → `test_keymaps_services_and_models_stay_ui_free` 必须红 → 还原 | S2.1 | 守卫有效性证据 | 变红输出留档「执行记录」；还原后 13 passed |
| S2.3 | architecture-boundaries.md：R4 文件清单加 `config.py`；§四「跨模块交互」表补「L0 需要 UI 能力 → 构造参数注入 Callable（N30 模式：`load_config(register_theme=..., load_theme_paths=...)`）」行；§六说明用例计数维持 13 及理由 | S2.2 | 规则文档更新 | 规则与代码实际一致 |
| S2.4 | app-layering-refactoring-plans/README.md 增补决策记录段（注入回调而非下沉，引 [README §2.2](README.md#22-方案-b-的否决理由关键证据) 否决依据） | README §2 | README 记录段 | 交叉引用可达 |
| S2.5 | code-review-fix-plans/P2_nice_to_have_plan.md：N30 行 ⏸ → ✅ + 状态段补记并链接本目录 | S2.3 | 账目更新 | 链接可达、与规则一致 |
| S2.6 | .trae/issues/review.md：N30 条目回填 ✅ + 实测证据 | S2.5 | review.md 更新 | 与 P2 账一致 |

> 交叉引用关系：规则（S2.3）是其余三处文档的锚，先做；S2.4/S2.5/S2.6 并行后由主代理统一复核一致性。

## 2. 独占文件域

| 文件 | 性质 |
|---|---|
| `tests/test_architecture.py` | 代码（守卫扩员），仅本 Plan 触碰 |
| `.trae/rules/architecture-boundaries.md` | 规则文档 |
| `.trae/documents/app-layering-refactoring-plans/README.md` | 前序重构总纲（追加记录段） |
| `.trae/documents/code-review-fix-plans/P2_nice_to_have_plan.md` | P2 账目 |
| `.trae/issues/review.md` | issue 账目 |

---

## 执行记录（回填区，执行时填写）

- S2.1：（日期、diff 行号、13 passed 实测）
- S2.2 负向验证：变红输出摘要（用例名 + assert 位置）→ 还原后 ___ passed
- S2.3：R4 清单 / 交互表 / §六 三处改动行号
- S2.4 / S2.5 / S2.6：各文档改动概要 + 实测数字引用（来自 SP1/SP3 门禁）
- 四处文档一致性复核结论：
