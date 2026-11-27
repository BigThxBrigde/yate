# 2026-11-22 LSP 导航评审（IKX5EP）

范围：worktree `<repo-parent>/yate-lsp-navigation`，分支 `feature/enh-lsp-navigation`，基线 `master c6d6e89a`；评审时 33 个文件 / +4375 -19；修复后终态 38 个文件 / +5011 -21（统计于 2026-11-23 在 `9b6f6471` 重新实测）。
评审者：code-review-expert（DeepSeek-V4.1-Flash）。本环境中 `python-code-review` skill 不可用；该 agent 按其指令允许回退到角色文件检查清单。

## 评审者报告的门禁结果

| 门禁 | 结果 | 退出码 |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 4 个错误，全部位于 `tools/smoke_test/scenarios/lsp_navigation.py:191,193`（`pilot: object`） | 1 |
| `pytest tests/ -q -n auto` | 2 failed（`test_action_table.py`、`test_vim_keymap.py`）；`-n 1` 同样 -> 真实回归 | 非零 |
| `pytest tests/test_architecture.py -q` | 47 passed | 0 |
| coverage（`--cov-fail-under=75`、`-n auto`） | 总计 92.48%；同样 2 个测试失败 | 非零 |
| `tools.smoke_test run --jobs 4` | 128/128 场景，1554/1554 检查 | 0 |

真实的 `pyright-langserver` 双文件测试已运行（未跳过）；新模块的覆盖率：`editor_lsp/navigation.py` 72%、`flows/lsp_navigation_flows.py` 73%，五个新增 manager 请求方法实际为 0%。

## 发现项（此处保留评审者的严重程度标签）

- B1（评审者 blocker）：声称 `:check-keys` 把新增的 vim `gd`/`gr` 帮助行报告为保留键，且冲突数从 8 增至 10。
- B2（评审者 blocker）：vim `K` 行的注释称仅用于帮助，但该行实际会分发；架构守卫未断言 F7+K 共存。
- M1（major）：`pilot: object` 未通过 pyright；应改用 `Any` 并附上仓库规定的原因注释。
- M2（major）：`test_action_table.py` 缺少 `lsp_navigation` 命名空间/hooks；`test_vim_keymap.py` 的 chord-hint 期望缺少 `gd`/`gr`。
- M3（major）：四处文档宣传了不存在的 `:lsp outline` 命令。
- M4（major）：五个新增 manager 请求方法没有直接测试；跨文件重命名的列转换未测试。
- M5（major）：重命名会为未打开的目标新建 buffer；回滚恢复了文本但留下新开的标签页；成功消息遗漏了 "unsaved"。
- M6（major）：`LspFeatureUnavailable` 混淆了"无就绪 server"与"server 缺少能力"。
- m1-m13（minor）：符号范围、跨文件钳制、取消错误掩盖、异常日志稀疏、execute_command 静默、documentChanges 优先级、chooser 选择异常、重命名提示前缀、失效的超时分支、stub-key 的 R10 测试、冒烟中 K/F7 仅在 vim 下、规则自述、过时的真实 server 注释。

## 主代理对 B1 的事实核查（驳回）

在 worktree 中直接探测：

```text
find_key_conflicts(VimKeymap(), RESERVED_KEYS) -> 8 conflicts
format_conflicts("vim", ...) -> 8 reserved rows (<alt-c>, <ctrl-b>, ...)
"gd" in RESERVED_KEYS -> False; "gr" in RESERVED_KEYS -> False
```

`gd`/`gr` 既无冲突计数回归，也未被归为保留键；B1 有证据驳回。其余 B2/M1-M6 被接受；次要项 m3/m7/m8/m9/m13 并入修复轮次，其余登记为修复计划中的后续事项。

评审时评审者的结论：REQUEST_CHANGES。修复后主代理必须亲自重跑所有门禁。

## 修复后门禁重跑（主代理，2026-11-22）

修复波次 F1/F2 提交为 `0d787642` 与 `761a365e`。B1 经直接探测驳回；其它所有被接受的阻塞项/严重项均已修复（B2 的注释与双绑定守卫、M1 的 pilot 类型、M2 的两张测试表、M3 的四处文档、M4 的五个 manager 方法及其直接测试，含 documentChanges/UTF-16、M5 的重命名消息披露与回滚测试、M6 的无就绪 server 与不支持之区分）。成本低的次要项 m3/m7/m8/m9/m13 也一并修复；m1/m4/m5/m6/m10/m11/m12 仍登记为后续事项（非阻塞）。

修复后由主代理实测：

| 门禁 | 结果 | 退出码 |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings, 0 informations | 0 |
| `pytest tests/ -q -n auto`（门禁运行） | 全部测试全绿 | 0 |
| `pytest tests/test_architecture.py -q` | 47 passed | 0 |
| coverage `-n auto` | 4029 passed，10 skipped；总计 92.80%（阈值 75%） | 0 |
| `smoke --jobs 4` | 128/128 场景，1554/1554 检查 | 0 |
| `tools.changelog check` | 仅分支级 "unreleased lags 193 commits"；已发布各节为最新 | 0 |

随后一次临时的 `pytest -n auto` 重复运行返回退出码 1，但所有测试均为 100% 且无 `F` 标记；日志显示在 pytest 临时清理期间出现 `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] count=10000`。这是有记录的环境钩子伪影（非测试失败）；门禁运行与覆盖率运行均完全全绿。

两处均钉定的最终行数：`keymaps/vim.py` 1705、`editor_lsp/manager.py` 1189、`editor.py` 848。
