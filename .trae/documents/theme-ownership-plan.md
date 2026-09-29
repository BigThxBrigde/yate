# theme-ownership 重构方案（已拆分，本文件为指针）

> **本方案已于 2026-09-27 按 app-layering-plans 规格拆分为目录，唯一计划来源迁移至：**
>
> **[theme-ownership-refactoring-plans/overview.md](theme-ownership-refactoring-plans/overview.md)**
> （总纲：事实基线 / 问题陈述 / 方案比选 / Plan 索引 / 依赖面 / 风险 / 审计记录）
>
> | 分册 | 内容 |
> |---|---|
> | [theme-ownership-refactoring-theme-broadcast-plan-a.md](theme-ownership-refactoring-plans/theme-ownership-refactoring-theme-broadcast-plan-a.md) | 主题广播基建（theme.py 订阅/派发） |
> | [theme-ownership-refactoring-scrollbar-injection-plan-b.md](theme-ownership-refactoring-plans/theme-ownership-refactoring-scrollbar-injection-plan-b.md) | 滚动条 per-widget 注入（T1） |
> | [theme-ownership-refactoring-widget-theme-selfhold-plan-c.md](theme-ownership-refactoring-plans/theme-ownership-refactoring-widget-theme-selfhold-plan-c.md) | 七组件自持主题 + 删 apply_theme（T2） |
> | [theme-ownership-refactoring-architecture-guards-plan-d.md](theme-ownership-refactoring-plans/theme-ownership-refactoring-architecture-guards-plan-d.md) | 2 条架构守卫 |
> | [theme-ownership-refactoring-gate-docs-plan-e.md](theme-ownership-refactoring-plans/theme-ownership-refactoring-gate-docs-plan-e.md) | 门禁 / 基线归因 / 文档回填 |
>
> 状态：Plan A–E 全部完成（分支 `ref/theme-ownership`）。本文件不再维护。
