# 2026-11-06 未命名 buffer 的 LSP attach 评审第一轮

- 分支：`fix/enew-args-lsp-attach` · 范围 `8e60598..383affe`（6 笔提交，issue 说明 + 计划 + 波次 1/2 产物）。
- 评审者：`code-review-expert`（`.trae/agents/code-review-expert.md`），来自 `.trae/skills/` 的 `python-code-review` skill，已强制应用自我批评。
- 范围：`yate/commands.py`、`yate/editor_lsp/manager.py`、`yate/flows/document_flows.py`、`tests/test_cmd_enew.py`、`tests/test_lsp.py`、`tests/test_document_flows_saveas.py`、四个双语手册文件、冒烟场景及一处基线。
- 规范来源：[`../documents/enew-args-lsp-attach-issue-notes.md`](../documents/enew-args-lsp-attach-issue-notes.md)、[`../documents/enew-args-lsp-attach-plan.md`](../documents/enew-args-lsp-attach-plan.md)、[`../documents/enew-args-lsp-attach-plans/overview.md`](../documents/enew-args-lsp-attach-plans/overview.md) 及子计划 a–d。
- 结论：**需要整改 — 0 个阻塞项 / 2 个严重 / 4 个次要**。本文为只读事实文档；整改记录在计划中，不在此处安排。

## 1. 实际执行的门禁命令（评审者，退出码）

| 命令 | 结果 | 退出码 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 errors, 0 warnings, 0 informations | 0 |
| `python -m pytest tests/ -q -n auto` | 全绿 | 0 |
| `python -m pytest tests/test_architecture.py -q` | 37 passed | 0 |
| `python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -n auto` | 3413 passed, 10 skipped; TOTAL 92.86% (19416 stmts / 1100 miss / 6202 branch / 572 brpart); manager.py 90%, document_flows.py 94%, commands.py 91% | 0 |
| `python -m tools.smoke_test run --jobs 4` | 121/121 scenarios, 1464/1464 checks, 76.95s | 0 |
| `-n 1` 复查（test_lsp + test_document_flows_saveas + test_cmd_enew） | 全绿，与 `-n auto` 一致 | 0 |

新增代码（`yate/editor_lsp/manager.py`）中未覆盖的行：`364`、`387-388`、`445`。行数：manager.py 783、commands.py 617、document_flows.py 533 —— 均低于 §三.7 的 800 行守卫。

## 2. 发现项

### [major] 1 — 重定向到另一个标签页拥有的 URI

`yate/editor_lsp/manager.py:449-451` 结合 `:366`（`uri in self._open` 提前返回）与 `:450`（`_close_uri`）。已用真实 `Document` 对象与假客户端复现：文档 A（`x.py`）另存为 `y.py`，而标签页 B 已持有 `y.py`，此时 `_open[y.py]` 归 B 所有且 A 没有 didOpen；若先关闭 B 的 URI，服务端会看到一个 didClose 且之后没有 didOpen。可达性也已复现：`EditorSession.is_open` 阻止重复 `:e` 打开，但不阻止 `:saveas` 后两个标签页共享同一路径。建议方向：比较 `state.doc` 身份，在重新打开前关闭前任所有者的 URI 条目。

### [major] 2 — 路径拼写与 URI 等价性

`yate/editor_lsp/manager.py:446` 按词法比较 `Path(previous_path) == doc.path`，而 `protocol.path_to_uri` 会解析路径。已用 `sub/../a.py` 与 `a.py` 复现：`Path` 相等性为 False 但 URI 相等，因此重定向发送了不必要的 `didClose` + `didOpen` 并丢弃服务端诊断 —— 正是计划 §3 C4 所否决的行为。`_drop_uri_cache`（`:190-194`）还可能留下两个值相同的键。建议方向：比较 URI（或丢弃过期拼写的缓存键）；在保存路径中拒绝符号链接解析的 `resolve()` 是计划的设计决策，不属于本评审。

### [minor] 3 — 关闭操作落在进行中的打开操作内

`manager.py:371-403`：`_opening` 阻止重复 didOpen，但在 `await ensure_client` 期间完成的 `on_document_closed` 之后，打开方仍可能写入幽灵 `_open` 条目并发送 didOpen。已复现；因窗口很窄、无数据丢失，且属于计划 b 设计的边界而非回归，故从严重降级为次要。

### [minor] 4 — 三行新增代码未覆盖

`manager.py:364`（无路径时显示）、`:387-388`（didOpen 通知失败）、`:445`（无路径重定向）没有测试。全量套件覆盖率仍满足 75 阈值。

### [minor] 5 — 行数余量

`manager.py` 已有 783/800 行；后续任何新增 method 都会触发 `test_source_files_within_size_threshold`，除非拆分该文件或将其豁免。

### [minor] 6 — 缺少多参数 `:enew` 用例

`tests/test_cmd_enew.py:83-100` 覆盖了文件名和带引号的文件名，但未覆盖 `:enew a.py b.py`。守卫本身正确（`CommandFunc` 接受一个 `args: str`），只是缺少一个回归用例。

## 3. 自我批评登记

| # | 初始结论 | 结果 |
|---|---|---|
| 1 | major | 确认（重读代码行，双向运行时验证） |
| 2 | major | 确认（重读代码行，Path 与 URI 对比验证） |
| 3 | 初稿 major | 降为次要（await 窗口很窄、无崩溃/数据丢失、计划 b 设计边界） |
| 4 | minor | 确认（针对性重跑覆盖率） |
| 5 | minor | 确认（实测 783 行） |
| 6 | minor | 确认（已检查签名） |

作为误报删除："`_close_uri` 改变了语句顺序/日志文本"（与基线版本逐字节比对）、"`_opening` 在 cancel/shutdown 后泄漏"（实测集合为空）、"`_refresh_ui()` 有副作用"（注入可调用对象、卸载后无操作、与 `save_document` 尾部相同）、"`doc_shown_later` 与重定向竞态导致重复 didOpen"（实测只有一个 didOpen）、"新测试中缺少 `@override` / NameError"（pyright 0，测试全绿）、"手册不同步"（四种关键字符串在两种语言中均存在）、"`states()`/`configs()` 语义改变"（未改变）。

评审者记录了一处工作区纪律偏差：评审期间创建了三个临时抓取文件（`cov.txt`、`old_mgr.txt`、`smoke.txt`），并在最终的 `git status --short`（为空）之前删除。评审者未修改任何产品、测试、文档、计划或基线文件。

## 4. 计划符合性检查

所有波次 1/2 的实现与各自子计划逐字一致：`:enew` 警告文本与注册描述、`state_for_doc` 路径门控、`_close_uri` 抽取、`on_document_retargeted` 签名/分支、`previous_path` 捕获与 spawn 位置、`_refresh_ui()` 尾部、双语手册配对、单项冒烟检查且恰好一处基线改动。计划 c 的测试 #4 `cast(Any, fx.flows)._submit_save_as(...)` 偏差已验证，并由 pyright strict 证明合理；计划 d 中推迟的完整 `run --jobs 4` 已由本评审执行（121/121）。六笔提交均使用 `type(scope): subject` 格式。两个严重项是**计划设计缺口**（URI 同一性 / URI 所有权未定义），而非实现偏差；它们已作为 [`../documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-review-plan-e.md`](../documents/enew-args-lsp-attach-plans/enew-args-lsp-attach-review-plan-e.md) 反馈回第 2 步。
