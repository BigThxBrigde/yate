# 选项定义统一 进度记录（2026-11-16）

> worktree `yate-option-spec-unify`，分支 `feature/ref-option-spec-unify`，parent `master`（9c304548）。
> 唯一规范来源：[总纲](overview.md) + 三个子计划；本文件只记状态，不承载设计。

## 步骤状态

| 步骤 | 状态 | 产物 / 提交 |
|---|---|---|
| 【领会】 | 完成 | 三文件消费端取证、issue 素材整理（master 主工作区阅读，未单独落盘） |
| 【方案】 | 完成 | issue 文本 + 总纲 + 3 子计划（提交 `ef1c7e7b`；5 文件 808 行）。规划角色两次 spawn 因 `qwen-3.8-plus` 未注册失败，主代理兜底，已登记 |
| 【批准】 | 完成 | 用户 2026-11-16 显式指令「进入无人值守，所有问题和操作都无须过问，更新任务状态，继续执行」，按通过处理 |
| wave-1（plan-a） | 完成 | `09efd402`：config.py 统一表 + 13 测试；555 行 < 800；pyright 0、27 passed |
| wave-2（plan-b） | 完成 | `5c8d1aa4`：_extract_options 遍历表；627 行 < 800；35 passed |
| wave-3（plan-c） | 完成 | `b5ffd885`：补全候选 + 架构守卫 42 条 + 规则计数同步；91 passed；N1/N2 演练均 exit 1 后还原 |
| 【审核】 | 完成 | code-review-expert 交付 REQUEST CHANGES（5 MAJOR）；`04432f95` 全部闭合，复审 APPROVE |
| 【收尾】 | 完成 | 六道门禁全绿（见下）；只提交不推送，分支共 8 笔提交 |

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

- wave-1：pyright 0 / 27 passed / 架构 41 → 555 行；N/A 演练见 plan-a
- wave-2：pyright 0 / 35 passed；_extract_options 742→627 行；dict extractors 仍在尾部调用
- wave-3：pyright 0 / 91 passed / 架构 42 passed；N1（keymap 硬编码候选）与 N2（tab_width 内联校验）负向演练均令守卫 exit 1，还原后 exit 0
- 审核：code-review-expert 交付；5 MAJOR / 5 MINOR 全部闭合于 04432f95；复审 APPROVE；评审记录 `.trae/reviews/2026-11-16-option-spec-unify.md`
- 收尾门禁（2026-11-16 主代理亲跑，六项全绿）：\n  1. pyright yate/ tests/ tools/ pack/ -> 0 errors / 0 warnings\n  2. pytest tests/ -q -n 1 -> exit 0\n  3. pytest tests/test_architecture.py -q -n 1 -> 42 passed, exit 0\n  4. pytest tests/ --cov=yate --cov-branch -q -n 1 --cov-fail-under=75 -> 93.02%, exit 0（首轮 test_palette_down_cursor_moves 一过性失败，单独复跑通过；二轮全绿）\n  5. python -m tools.smoke_test run --jobs 4 -> 124/124 scenarios, 1511/1511 checks, exit 0\n  6. python -m tools.changelog check -> exit 0\n  - 备注：并行 -n auto 全量首轮 exit 1 由本机 safe-delete 钩子收尾清理锁超时所致（非测试失败，见记忆）；串行 -n 1 为权威口径，exit 0。
