---
alwaysApply: true
scene: git_message
---

1. 使用conversation模板, 生成提交信息。
2. 信息格式为：`type(scope): subject`
3. `type` 为提交类型，`scope` 为影响范围，`subject` 为提交主题。
4.  `type` 可选值：`feat`（新功能）、`fix`（修复）、`refactor`（重构）、`docs`（文档）、`chore`（构建工具、辅助工具等）。
5. `scope` 可选，用于指定影响的模块或组件。
6. `subject` 为提交主题，应简洁明了，描述提交的内容。
7. 提交信息应符合git commit规范，使用英文。

