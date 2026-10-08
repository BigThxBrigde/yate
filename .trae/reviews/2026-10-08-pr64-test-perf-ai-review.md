# Gitee PR !64 AI 队友评审（test-perf）— 2026-10-08

> 来源：[PR !64 评论 note 51468217](https://gitee.com/jermaine/yate/pulls/64#note_51468217_conversation_191486229)
> （AI 队友"PR观察者"，响应 `jermaine` 的 `/review` 指令，2026-10-08 06:20 触发 / 06:27 更新，
> 正文经 Gitee API 取回，页面不展开评论；PR !64 即 worktree 分支 `enh/test-perf`，
> 关联 issue IKJVL6「单元测试的性能和执行速度问题」）。
> 评审对象：test-perf 三提交（`perf(tests)` 最慢用例 144s→4s / `fix(shell)` 超时杀进程树 /
> `docs(plan)` 计划与实测回填）。

## 一、评审结论（机器人自评）

**⛔ 未通过：发现 1 个阻断项、2 个改进项。风险等级 medium。**

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ❌ 未通过 |
| 安全性 | ✅ 通过 |
| 性能 | ✅ 通过 |
| 可维护性 | ⚠️ 待优化（2 项，见下） |

## 二、阻断项与改进项处置

| # | 级别 | 问题 | 机器人建议 | 处置 |
|---|---|---|---|---|
| B1 | ⛔ 阻断 | `yate/services/shell.py` 超时兜底的第二次 `proc.communicate()` 未传 timeout：若 `_kill_tree` 未能终止持有管道的进程（Windows taskkill 竞态、POSIX 孙进程脱离 pgid），调用将无限阻塞 | 改 `communicate(timeout=5.0)` + 二次超时降级 `proc.kill()` | ✅ **已修**（`6578714`）：两段收尾排水均有界（5s），二次超时降级杀 shell 根并再给一段有界收尸，仍超时则 `log.error` 取证后按固定文案返回 124（排出的输出本就丢弃）。新增钉桩用例 `test_run_shell_bounds_the_drain_when_the_tree_survives_the_kill`（stub `Popen` + no-op `_kill_tree`，无界排水会被 stub 断言击穿）；负向演练通过（临时还原无界写法用例变红） |
| M1 | ⚠️ 改进 | `tests/test_app_manual.py::test_manual_command_selects_language` fixture 用固定 `return_value`，丢失语言路由守卫语义（`:manual zh` 是否真把 zh 传给了 loader 不可观察） | 改用 `side_effect` 捕获 `(kind, lang)` 并断言 | ✅ **已修**（`c733fcb`）：stub 记录参数后仍返回 `MANUAL_DOC_FIXTURE`（保留渲染提速收益），断言 `calls == [("manual", expected_lang)]`。对建议的一处细化：`bogus→en` 归一化在真实 `load_doc_markdown` 内部（`manual.py:65-67`），本用例 mock 了它，故断言**命令原样透传语言参数**；在测试里复刻归一化再断言 en 是恒真断言温床（#31 轮 R-17 先例），不采纳 |
| M2 | ⚠️ 改进 | `tests/test_workspace_filter.py` 的 1500 级链 walk 用例全局 monkeypatch `pathlib.Path.stat` / `Path.read_text`，侵入面过大 | 收窄到 `ws._dir_ignores` 等更具体的 seam | ✅ **已修**（`c733fcb`）：改为 `monkeypatch.setattr(Workspace, "_dir_ignores", stub)` 直接返回空表——与原 stub 经 `OSError` 分支产生的"每目录无 ignore 文件"语义等价，但不再触碰 `pathlib` 全局；删除 `raise_long_path_error` 与 `import os` |

## 三、门禁（主代理亲自跑，worktree 内 `.venv`）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 | `0 errors, 0 warnings, 0 informations` |
| `python -m pytest tests/ -q` | 0 | **1998 passed / 9 skipped**（基线 1997 + 本轮 1 个钉桩用例） |
| `python -m pytest tests/test_architecture.py -q` | 0 | **25 passed** |
| `python -m pytest tests/ --cov=yate --cov-branch --cov-fail-under=75` | 0 | 覆盖率 **91.35%**（≥75%） |

**性能核对**（针对"fix 是否拖慢全量"的疑问）：fix 只改超时异常路径，
`communicate(timeout=5.0)` 在树已死时立即返回（5s 是上限而非等待）。
A/B 实测（`git stash` 前后各跑 `tests/test_shell.py --durations`）：
杀树用例基线 2.35s / 有 fix 1.08s，超时用例两侧均 0.34s——零回退，
差异在基线方差内。用户实测 run1（无改动）141.28s ≈ 计划记录的 143.9s 基线；
run2 187.09s 系门禁并发（全量 pyright + 两轮 pytest 同窗运行）所致墙钟膨胀，
非代码回归。

## 四、关联

- 实施方案与批准记录：[pr64-test-perf-review-fixes-plan.md](../documents/pr64-test-perf-review-fixes-plan.md)。
- 被评审分支的实施计划：[test-perf-plan.md](../documents/test-perf-plan.md)（issue IKJVL6）。
- 评审建议的修法先例：#31 轮 R-17（恒真断言教训）→ 本轮 M1 处置依据。

## 五、第二轮评审登记（note 51468439，conversation 191486965）

> 来源：[PR !64 评论 note 51468439](https://gitee.com/jermaine/yate/pulls/64#note_51468439_conversation_191486965)
> （AI 队友"PR观察者"，响应 `jermaine` 的第二次 `/review` 指令（note 51468438，
> 2026-10-08 07:33:38），评论创建 07:33:39 / 更新 07:38:38，
> 正文经 Gitee API 取回，页面不展开评论）。
> 评审对象：第一轮处置后的分支全量（含修复提交 `6578714` / `c733fcb`）。
> **按用户指令（2026-10-08）：同一 PR 的各轮评审登记并入本文档，不再新建文件。**

**结论：⚠️ 无阻断项，可优化后合并。风险等级 low。**
未再提出第一轮的阻断项，也未对第一轮两项修复提出异议；
第一轮结论由「⛔ 未通过（风险 medium）」收敛为「⚠️ 可优化后合并（风险 low）」。

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ✅ 通过 |
| 安全性 | ✅ 通过 |
| 性能 | ✅ 通过 |
| 可维护性 | ⚠️ 待优化（3 项，见下） |

| # | 级别 | 问题 | 机器人建议 | 处置 |
|---|---|---|---|---|
| M1' | ⚠️ 改进 | `yate/services/shell.py` 超时后的排水 timeout 魔法数字 `5.0` 缺乏集中管理 | 定义模块级私有常量 `_DRAIN_TIMEOUT_S = 5.0` 并统一引用 | 👀 **登记未处置**（2026-10-08 用户指令只登记不修）。主代理核实：全文件 grep 实测字面量为 **2 处**（`shell.py:96`、`shell.py:103`，即两段有界排水），评审正文称"出现三次"与实测不符（第三处疑为统计口径偏差，如实校准）；两处语义一致且仅此文件使用，Nit 级 |
| M2' | ⚠️ 改进 | `tests/test_shell.py::_pid_alive` 硬编码 Windows API 常量 `0x1000`，可读性稍差 | 命名为 `PROCESS_QUERY_LIMITED_INFORMATION = 0x1000` | 👀 **登记未处置**（同上）。核实属实（`test_shell.py:77`，全仓孤例）；Nit 级可读性 |
| M3' | ⚠️ 改进 | `tests/test_app_manual.py` 的 `await pilot.pause(0.15)` 与实现内部 `_SEARCH_DEBOUNCE_S`（0.12s）紧耦合，实现调大防抖时用例会脆断 | 显式设置更大的 debounce 值或用 `wait_until` 等待状态变化 | 👀 **登记未处置**（同上）。核实：`pilot.pause(0.15)` 实际 **5 处**（`test_app_manual.py:295/429/438/469/522`，评审举 1 处）；当前 0.15 > 0.12 余量成立不脆断，建议属可选加固非现症 |

风险自评：low——全量测试 265.7s → 约 144s（-45%），shell 超时进程泄漏与无限阻塞已修，
改动经充分测试与负向演练。3 项均为可维护性 / Nit 级，**只登记、不修复**；
纯文档变更，按 `misc-rules.md` §三 豁免测试与门禁。
同类先例：#34（PR !59 第二轮评审，同样按用户指令只登记不修）。
