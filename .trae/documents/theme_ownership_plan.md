# theme-ownership 重构方案（已拆分，本文件为指针）

> **本方案已于 2026-09-27 按 app-layering-plans 规格拆分为目录，唯一计划来源迁移至：**
>
> **[theme-ownership-refactoring-plans/README.md](theme-ownership-refactoring-plans/README.md)**
> （总纲：事实基线 / 问题陈述 / 方案比选 / Plan 索引 / 依赖面 / 风险 / 审计记录）
>
> | 分册 | 内容 |
> |---|---|
> | [plan_A_theme_broadcast.md](theme-ownership-refactoring-plans/plan_A_theme_broadcast.md) | 主题广播基建（theme.py 订阅/派发） |
> | [plan_B_scrollbar_injection.md](theme-ownership-refactoring-plans/plan_B_scrollbar_injection.md) | 滚动条 per-widget 注入（T1） |
> | [plan_C_widget_theme_selfhold.md](theme-ownership-refactoring-plans/plan_C_widget_theme_selfhold.md) | 七组件自持主题 + 删 apply_theme（T2） |
> | [plan_D_architecture_guards.md](theme-ownership-refactoring-plans/plan_D_architecture_guards.md) | 2 条架构守卫 |
> | [plan_E_gate_docs.md](theme-ownership-refactoring-plans/plan_E_gate_docs.md) | 门禁 / 基线归因 / 文档回填 |
>
> 状态：Plan A–E 全部完成（分支 `ref/theme-ownership`）。本文件不再维护。
