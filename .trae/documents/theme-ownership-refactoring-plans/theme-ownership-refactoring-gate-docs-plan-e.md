# Plan E — 门禁、冒烟基线与文档回填

> 状态：✅ **已完成**（2026-09-27）· 前置：[Plan A](theme_ownership_refactoring_theme_broadcast_plan_a.md)–[Plan D](theme_ownership_refactoring_architecture_guards_plan_d.md) 全部完成
> 独占文件：`tools/smoke_test/smoke_baselines/*.json`（2 个）、`.trae/issues/review_ui_refine_20260927.md`、
> `.trae/documents/theme_ownership_plan.md`
> 门禁：总纲 §1.2 全表（pyright 0 / pytest 绿 / run + compare 均 exit 0）

---

## E.1 门禁执行

| 门禁 | 实测结果 |
|---|---|
| `pyright yate/ tests/ tools/` | **0 errors, 0 warnings, 0 informations** |
| `pytest tests/ -q` | 全量绿（仅平台性 skip） |
| `pytest tests/test_architecture.py -q` | 20 passed |
| `tools.smoke_test run --skip-slow` | 882/882 checks、84/84 scenarios、exit 0 |
| `tools.smoke_test compare --skip-slow` | 首跑 exit 1（2 处 DRIFT，见 §E.4）→ 归因 + 重拍后 **exit 0** |

## E.2 review 文档回填

[review_ui_refine_20260927.md](../../review/2026-09-27-ui-refine.md) 同步三处：

- §四 标题"待重构"→"已治理"，T1/T2 各追加"✅ 治理结果"段（指向本目录各 Plan）；
- §五 整改项划线标注完成；
- 两条张力的状态从"已评估"变为"已治理 + 守卫固化"。

## E.3 计划文档迁移

原单文件方案 `theme_ownership_plan.md` 的内容按 app-layering-plans 规格拆分为本目录
（README 总纲 + Plan A–E 分册）；原文件改为**指针 stub**，避免双份真相。

## E.4 冒烟基线漂移：发现 → 归因 → 闭合

### 发现

`compare` 首跑 exit 1（checks 本身 882/882 全过，漂移在**基线比对层**）：

| 场景 | 漂移内容 |
|---|---|
| `set_options_matrix` | 基线缺 3 个新 check（`readonly` / `readonly_kept` / `readonly_off`）——master 合并新增的检查项，基线未重拍 |
| `stress_key_fuzz` | 保存内容差一处字符置换（`3b3d2c` vs `3b32dc`），fuzz 序列输出变化 |

### 归因（反证法）

在**重构前**的父分支 `enh/ui-refine`（worktree `D:/Programming/yate-ui-refine-wt`）跑同一场景：

- 两处漂移**逐一复现**，且 fuzz 序列逐字符一致 → 漂移继承自 master 合并
  （keyproto 行为变化 + readonly 场景扩展），**非本次重构引入**。

### 闭合

```powershell
python -m tools.smoke_test snapshot --scenario set_options_matrix --scenario stress_key_fuzz
python -m tools.smoke_test compare --skip-slow   # exit 0，882/882
```

### 流程教训（已固化）

风险表明确要求"S3 后跑 compare 记录视觉漂移"，执行时只跑了 `run`——**漏跑被总纲 §10
审计第 6 项捕获**。教训连同"先方案后执行"一起固化为
[`plan-before-execute.md`](../../rules/plan-before-execute.md)（收尾步骤强制 compare）。

## E.5 提交划分

| 提交 | 内容 |
|---|---|
| `046fcff` | Plan A/B/C 产品代码 |
| `1b49208` | Plan D 守卫 |
| `47567db` | review 回填 |
| `766b266` | 子计划拆分（本目录）+ 2 处基线重拍 |

**未推送**（用户指示）；分支 `ref/theme-ownership`，基线 `enh/ui-refine`。
