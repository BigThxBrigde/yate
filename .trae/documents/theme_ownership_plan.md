# theme-ownership 重构方案（已拆分，本文件为指针）

> **本方案已于 2026-09-27 按 app-layering-plans 规格拆分为目录，唯一计划来源迁移至：**
>
> **[theme-ownership-refactoring-plans/overview.md](theme-ownership-refactoring-plans/overview.md)**
> （总纲：事实基线 / 问题陈述 / 方案比选 / Plan 索引 / 依赖面 / 风险 / 审计记录）
>
> | 分册 | 内容 |
> |---|---|
> | [theme_ownership_refactoring_theme_broadcast_plan_a.md](theme-ownership-refactoring-plans/theme_ownership_refactoring_theme_broadcast_plan_a.md) | 主题广播基建（theme.py 订阅/派发） |
> | [theme_ownership_refactoring_scrollbar_injection_plan_b.md](theme-ownership-refactoring-plans/theme_ownership_refactoring_scrollbar_injection_plan_b.md) | 滚动条 per-widget 注入（T1） |
> | [theme_ownership_refactoring_widget_theme_selfhold_plan_c.md](theme-ownership-refactoring-plans/theme_ownership_refactoring_widget_theme_selfhold_plan_c.md) | 七组件自持主题 + 删 apply_theme（T2） |
> | [theme_ownership_refactoring_architecture_guards_plan_d.md](theme-ownership-refactoring-plans/theme_ownership_refactoring_architecture_guards_plan_d.md) | 2 条架构守卫 |
> | [theme_ownership_refactoring_gate_docs_plan_e.md](theme-ownership-refactoring-plans/theme_ownership_refactoring_gate_docs_plan_e.md) | 门禁 / 基线归因 / 文档回填 |
>
> 状态：Plan A–E 全部完成（分支 `ref/theme-ownership`）。本文件不再维护。
