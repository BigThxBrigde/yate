# 2026-11-06 未命名 buffer 的 LSP attach 评审第二轮（迭代后）

- 分支：`fix/enew-args-lsp-attach` · 主要范围 `383affe..HEAD`（3 笔计划/评审提交 + 波次 3 代码 `28a5fdf`），另有全范围复查 `8e60598..HEAD`。
- 评审者：`code-review-expert`（`.trae/agents/code-review-expert.md`），来自 `.trae/skills/` 的 `python-code-review` skill，已强制应用自我批评。
- 结论：**看起来良好 — 0 个阻塞项 / 0 个严重 / 2 个次要**。第一轮的 2 个严重项已闭合；第一轮的 4 个次要项全部处置完毕。可进入第 7 步。
- 本文为只读事实文档；整改记录在计划中，不在此处安排。

## 1. 第一轮严重项闭合（经探针验证）

| 严重项 | 闭合证据 |
|---|---|
| #1 另存到另一个标签页拥有的 URI | `manager.py:462-464` 所有者分支 + `:465` `on_document_shown`；实测通知序列 `didOpen, didOpen, didClose, didClose, didOpen`、`_open[y.py].doc is a`，新所有者的 didOpen 携带 `text == "a\n"`；在 `383affe` 上的负向演练：`AssertionError: assert new_uri in closes` |
| #2 路径拼写与 URI 等价性 | `manager.py:454-460` 比较 `protocol.path_to_uri`，丢弃过期的缓存键；同路径另存只发送 `didOpen, didSave`，无 didClose 往返，缓存只有 1 个键；在 `383affe` 上的负向演练：`AssertionError: assert ['textDocument/didClose'] == []` |

对 `_uri_cache.pop(previous_path)` 是否误删做了探针验证：`_uri(doc)` 先运行并重写该键，因此无后果。4/4 波次 3 负向演练（包括两处 `_opening` 复查用例）在旧实现上失败、在 `28a5fdf` 上通过。

## 2. 发现项（本轮）

### [minor] 1 — 计划 e §6 执行记录仍为占位符

`.trae/documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-review-plan-e.md:187-200` 的 8 行全部为 `pending`，而计划 e §4.1/§5 要求记录负向演练与实测结果。依据规则：`plan-before-execute.md`（可验证的验收记录）。**处理**：在第 7 步解决 —— 主代理用实测命令、退出码与偏差回填了计划 e §6（以及其它每个子计划的执行记录）；见 [`../documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-review-plan-e.md`](../documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-review-plan-e.md) §6。

### [minor] 2 — 从未显示过的文档同 URI 重定向不发生 attach

`yate/editor_lsp/manager.py:455-460`：当 `previous_uri == new_uri` 时，若该 URI 从未进入 `_open`，`notify_saved(doc)` 会静默返回（实测 `_open == []`、`is_open == False`、`_clients == 0`）。正常 UI 流程已覆盖，因为 `_submit_save_as` 以 `_refresh_ui()` → `doc_shown_later()` → didOpen 结束，故降为次要。评审者建议当 `new_uri not in self._open` 时回退到 `on_document_shown(doc)`，或记录调用方前置条件。**处置**：已登记为主计划 §6 的遗留待办，本 issue 不修复（规则 §二.6：仅次要项 → 待办）。注意 `manager.py` 已有 797 行；修复还须遵守 §三.7 的 800 行守卫。

## 3. 自我批评登记

确认：A（计划 e §6 回填）、B（同 URI 从未显示时 attach）。作为误报/非问题删除：C（`_uri_cache.pop` 误删 —— 探针证明无害）、D（`previous_uri` 未缓存 —— 每次用户操作只另存一次，非热路径）、E（`shutdown_all` 泄漏 `_opening` —— `finally` 已清除，实测为空）、G（非英文测试注释 —— 架构守卫 37 通过）、H（重复 didClose —— 同 URI 分支提前返回）、I（测试改写既有用例 —— numstat 显示纯新增：`test_lsp.py` +267/−0、`test_cmd_enew.py` +10/−0）。将 F（两个标签页共享一个 URI 时，仍可能依据另一标签页的状态发送 didChange）降级为主计划 §6 已登记的遗留待办，因为修复前的行为是"完全不 attach"，而该修复是净改善。

六维泄漏检查：正确性（所有者 / 等价 URI / 同路径 / 并发不同 URI 路径均已探测）、边界（`path is None`、`previous_path is None`、`owner.doc is doc`、通知失败）、异常处理（尽力而为的 didOpen/didClose/didSave 配合惰性 `%` 日志）、并发（`_opening` 两处复查 + `finally`）、性能（O(1) 字典查找，无热路径回退）、类型/覆盖率（pyright 0，manager.py 92%）。

## 4. 实际执行的门禁命令（评审者，退出码）

| 命令 | 结果 | 退出码 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` | 0 |
| `python -m pytest tests/ -q -n auto` | `3422 passed, 10 skipped in 76.56s` | 0 |
| `python -m pytest tests/test_architecture.py -q` | `37 passed` | 0 |
| `python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -n auto` | `3422 passed, 10 skipped`；`TOTAL 19425 1081 6206 572 93%`；`Total coverage: 92.97%`（≥75） | 0 |
| `python -m tools.smoke_test run --jobs 4` | `1464/1464 checks`、`121/121 scenarios passed`，76.08s | 0 |
| 行数 `manager.py` | `797`（`< 800`，无 `SIZE_EXEMPT_FILES` 登记） | 0 |
| `-n 1` 复查（聚焦集） | `83 passed`，与 `-n auto` 一致 | 0 |
| `tests/test_app_lsp.py` | `14 passed` | 0 |

`manager.py` 中未覆盖的行不再包含第一轮的 `:364`、`:387-388`、`:445`，也不包含波次 3 的第二处 `_opening` 复查。负向演练在系统临时目录中 `383affe` 的隔离克隆里运行，之后已清理；主 worktree 保持未改动。

## 5. 计划符合性检查

计划 e 的五项裁决全部符合：URI 同一性、URI 所有权、关闭先于打开、未新增模块/公开 method/`<800` 行、无 `resolve()`/`normpath` 出现在 `DocumentFlows` 中。独占文件约束成立（仅 `manager.py`、`tests/test_lsp.py`、`tests/test_cmd_enew.py` 加计划/评审文档有改动）；本波次未触碰手册、冒烟文件及其它产品源码。提交信息均遵循 `type(scope): subject`。唯一一处计划偏差是上面的次要项 1（回填），现已解决。主代理第 7 步门禁复测覆盖率为 `92.86%`（而此处为 `92.97%`）；两者均超过 75% 阈值，差异是正常的并行覆盖率波动，已记录在主计划 §7。
