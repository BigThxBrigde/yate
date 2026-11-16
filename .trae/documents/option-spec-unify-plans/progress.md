# 选项定义统一 进度记录（2026-11-16）

> worktree `yate-option-spec-unify`，分支 `feature/ref-option-spec-unify`，parent `master`（9c304548）。
> 唯一规范来源：[总纲](overview.md) + 三个子计划；本文件只记状态，不承载设计。

## 步骤状态

| 步骤 | 状态 | 产物 / 提交 |
|---|---|---|
| 【领会】 | 完成 | 三文件消费端取证、issue 素材整理（master 主工作区阅读，未单独落盘） |
| 【方案】 | 完成 | issue 文本 + 总纲 + 3 子计划（提交 `ef1c7e7b`；5 文件 808 行）。规划角色两次 spawn 因 `qwen-3.8-plus` 未注册失败，主代理兜底，已登记 |
| 【批准】 | 完成 | 用户 2026-11-16 显式指令「进入无人值守，所有问题和操作都无须过问，更新任务状态，继续执行」，按通过处理 |
| wave-1（plan-a） | 进行中 | 待落盘：`config.py` + `tests/test_option_specs.py` |
| wave-2（plan-b） | 待办 | 依赖 wave-1 验收通过；`yaterc_options.py` + `tests/test_yaterc_options.py` |
| wave-3（plan-c） | 待办 | 依赖 wave-2；`commands.py` + `tests/test_set_options.py` + `tests/test_architecture.py` |
| 【审核】 | 待办 | code-review-expert 评审（失败则主代理自查替代并登记） |
| 【收尾】 | 待办 | 主代理亲跑全量门禁 + 回填 + 提交，只提交不推送 |

## 执行纪律登记

- 无人值守：全部审批按通过处理（`bypassPermissions`），不向用户发起询问。
- 子代理模型：2026-11-16 00:00 起临时统一 Hy4 失效，恢复 `task-orchestration.md` §一.3 按来源分配；主代理来自 CodeBuddy 插件 → plan-executor `GLM-5.3-Flash`、code-review-expert `DeepSeek-V4.1-Flash`。本机 `code-review-expert` 的 `DeepSeek-V4.1-Flash` 定义可用但不保证交付，按记忆判死窗口（≥30 分钟、只认落盘）执行。
- 每波单独提交、只提交不推送；波次间串行，上一波验收退出码 0 才进下一波。
- 纯文档变更按 `misc-rules.md` §三豁免门禁；产品代码变更须按波次跑计划内验收命令。

## 关键事实（供续作，避免凭记忆重建）

- 现状行数：`config.py` 378，`yaterc_options.py` 742，`commands.py` 约 612；800 行阈值须逐波实测。
- `KNOWN_OPTIONS` 派生顺序会变（内部 dict 构建，用户不可见），总纲 D3 与 plan-a §2.3 已如实登记；usage 文案由顺序一致的 `SET_OPTION_SPECS` 决定。
- `shell` 的空串差异、`readonly` 的 `true|false` vs 其余 bool 的 `on|off` 差异须保持不变（总纲 D7、plan-c §2.1）。
- `plan-b` 依赖 plan-a 的 `OptionSpec.invalid_message_fmt`（已补齐到 plan-a §2.2）。
- wave-1 的 `setattr` 风险与 fallback 见 plan-a §五 / plan-b §2.2；pyright 有异议才启用 fallback，并回填实测依据。

## 执行回填（逐波追加）

- wave-1：（待执行）
- wave-2：（待执行）
- wave-3：（待执行）
- 审核：（待执行）
- 收尾门禁：（待执行）
