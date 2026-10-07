# Gitee PR !61 AI 队友评审（repo-audit-fixes）— 2026-10-07

> 来源：[PR !61 评论 note 51464779](https://gitee.com/jermaine/yate/pulls/61#note_51464779_conversation_191468771)
> （AI 队友"PR观察者"，响应 `jermaine` 的 `/review` 指令，2026-10-07 16:56 触发 / 17:07 完成，
> 正文经 Gitee API 取回；PR !61 即本 worktree 分支 `ref/repo-audit-fixes` 的评审修复轮）。
> 评审对象：PR 全量 94 文件（架构规则同步 + 审计修复），含可执行逻辑改动的核心文件：
> `yate/config.py`、`yate/yaterc.py`、`yate/commands.py`、`yate/services/extensions.py`、
> `yate/registries.py`、`yate/keymaps/base.py`、`yate/keyproto/*`、`tools/changelog/cli.py`、
> 两条 CI workflow。

## 一、评审结论（机器人自评）

**⚠️ 无阻断项，1 改进建议，可优化后合并。风险等级 low。**

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ✅ 通过（`SET_OPTION_SPECS` 与 `SET_APPLY` 键对应、`parse_bool` 依赖、changelog `released_shas` 命名空间、扩展回滚逆序撤销语义均核验一致，功能等价无缺陷） |
| 安全性 | ✅ 通过（无 SQL/XSS/命令注入/敏感信息新增风险；yaterc 以 Python 执行属既有设计） |
| 性能 | ✅ 通过（无循环嵌套/冗余查询；CI 改善成本可控） |
| 可维护性 | ⚠️ 待优化（1 项，见下） |

正面认定：表驱动、私有 API 网关、模块拆分、测试覆盖增强使可维护性整体提升明显。

## 二、改进项与处置

| # | 问题 | 证据 | 机器人建议 | 处置 |
|---|---|---|---|---|
| M1 | `SET_APPLY[spec.name]` 直接索引缺运行时兜底：不变量"SPEC 有则 APPLY 必有"仅靠 `tests/test_set_options.py` 守护，将来新增 option 忘补 apply 时 `:set` 会抛裸 `KeyError` 崩溃而非优雅提示 | `yate/commands.py` `_set` 分发处 | 方案一：import 期断言不变量；方案二：改 `SET_APPLY.get()` + `log.error` + warn 消息 | ✅ **已修（方案二）**：分发处改 `.get()`，缺失时 `log.error("set missing apply handler for %r")` 并在消息行报 `internal error: no handler for <name>`（warn）；不变量守护保持由 `test_set_option_specs_cover_all_dispatched_options` 承担。**未采纳方案一**（import 期断言）：`assert` 在 `-O` 下被剥离（速览 #23 同类先例），改用模块级显式 fail-fast 则把"测试可拦截的表不一致"升级为"整个应用无法启动"，收益为负；运行时兜底 + 每轮 CI 必跑的键集守卫已覆盖"测试漏跑 + 人忘补"的组合场景。新增回归用例 `test_set_dispatch_survives_a_missing_apply`（经公开分发面 `register_commands` 删一个 handler，断言 warn 消息而非崩溃） |

## 三、门禁

`.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` → 0 errors；
`.venv\Scripts\python.exe -m pytest tests/test_set_options.py -q` → 全绿（含新用例）；
提交见该文档处置列，登记于 [README.md](README.md) 速览 #36。
