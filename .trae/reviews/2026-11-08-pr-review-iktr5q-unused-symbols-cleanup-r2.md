# 评审记录（第二轮复验）：2026-11-08 · IKTR5Q 无用符号清理（unused-symbols-cleanup r2）

- 角色：`code-review-expert` 第二轮复验；模型 DeepSeek-V4.1-Flash（`task-orchestration.md` §一.3 CodeBuddy 插件表）。
- 复验对象：首轮评审记录 `2026-11-08-pr-review-iktr5q-unused-symbols-cleanup.md` 的 §九（迭代波 F1）、§十（收尾门禁）、§十一（迭代后状态）；偏离登记 `unused-symbols-cleanup-plans/overview.md` §七 D12-D15。
- 已加载：`.trae/agents/code-review-expert.md` 剧本全文、`.trae/skills/python-code-review/SKILL.md`（以 `.trae/skills/` 为唯一权威来源；Skill 工具按名调用返回 not found，按剧本回退条款直接读该 skill 文件执行，不阻塞评审）、`.trae/rules/` 下 8 份规则全文。
- 纪律：本记录是本次复验唯一写入的文件；未改产品源码 / 测试 / 规则 / 方案文档 / 首轮评审记录，未执行 git add / commit / push。已执行强制自我批判（§五）。

## 一、复验范围

| 项 | 值 |
| --- | --- |
| worktree | `yate-unused-symbols-cleanup`（分支 `feature/enh-unused-symbols-cleanup`） |
| 复验区间 | `4b38989..179fdf6`（`git --no-pager diff 4b38989..179fdf6`） |
| 迭代提交 | `179fdf6 test(callbacks): poll for async dispatch in review iteration F1`（1 笔） |
| 改动规模 | 4 文件 / +352 / -9（`git --no-pager diff --numstat` 实测） |
| 其中测试 | `tests/test_app_find_replace.py`（+11/-4）、`tests/test_zero_arg_callbacks.py`（+9/-5） |
| 其中文档 | `unused-symbols-cleanup-plans/overview.md`（+4/-0，D12-D15）、`2026-11-08-pr-review-iktr5q-unused-symbols-cleanup.md`（+328/-0，§九-§十一） |
| 产品代码改动 | 0：`git --no-pager diff --stat 4b38989..179fdf6 -- yate/ tools/ pack/ pyproject.toml .trae/rules/ tests/test_architecture.py` 输出为空 |
| 分支状态 | `## feature/enh-unused-symbols-cleanup...origin/feature/enh-unused-symbols-cleanup [ahead 4]`，只提交未推送 |

## 二、门禁实测表（全部本次亲自实测，不引用他人数字）

| # | 命令 | 退出码 | 实测数字 | 判定 |
| --- | --- | --- | --- | --- |
| 1 | `python -m pyright yate/ tests/ tools/ pack/` | 0 | `0 errors, 0 warnings, 0 informations` | PASS |
| 2 | `python -m pytest tests/ -q -n auto` | 0 | `-q` 无汇总行，按退出码判定（全量 3483 收集 = 3473 passed + 10 skipped，见 #12） | PASS |
| 3 | `python -m pytest tests/test_architecture.py -q` | 0 | 37 passed（`-v` 汇总行 `37 passed in 16.64s`） | PASS |
| 4 | `python -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75`（后台进程 + 退出码落盘） | 0 | `Required test coverage of 75% reached. Total coverage: 92.94%`；`TOTAL 19552 stmts / 1092 miss / 6246 branch / 571 BrPart / 93%`；`3473 passed, 10 skipped in 159.68s` | PASS |
| 5 | `python -m tools.smoke_test run --jobs 4`（首跑） | 1 | `1463/1464 checks`、`120/121 scenarios passed`、85.55s；唯一失败 `stress_rapid_toggles` 的 `toggles_back`（expected False / actual True） | 见 §四 m-1 |
| 5b | 同 #5 重跑（第 2 次，`--jobs 4`） | 1 | 同一 check 再失败：`stress_rapid_toggles` `11/12`、`1463/1464`、84.60s | 见 §四 m-1 |
| 5c | `python -m tools.smoke_test run --jobs 1`（串行复核） | 0 | `121/121 scenarios passed`、`1464/1464 checks (100%)`、72.47s | 负载相关 |
| 5d | 同 #5 再跑（第 3 次，`--jobs 4`） | 0 | `121/121 scenarios passed`、`1464/1464 checks (100%)`、79.40s | 通过 |
| 6 | `python -m tools.changelog check` | 0 | `released changelog sections are up to date`；`stats: 21 segment(s), 20 version(s), 1714 entry/entries`；4 份 unreleased changelog `lags 7 commit(s) (refreshed at release)`（unreleased 滞后为设计内提示，非失败） | PASS |
| 7 | `git --no-pager diff --check` | 0 | 无输出 | PASS |
| 8 | 定向重复：`pytest tests/test_zero_arg_callbacks.py tests/test_app_find_replace.py -n 4` × 3 轮（每轮独立工具调用轮次） | 0/0/0 | `40 passed in 9.25s` / `40 passed in 13.82s` / `40 passed in 9.04s` | PASS |
| 9 | 全量负载复跑 `pytest tests/ -q -n auto` × 3 次（本次累计 4 次全量） | 0/0/0/0 | 均无 FAILED。第 3 次附 1 条 `PytestUnraisableExceptionWarning`（Textual `Worker._run` 的 `active_message_pump` ContextVar 跨 Context 复原告警，出现在 `tests/test_app_textual.py::test_line_resync_updates_string_boundary_on_edit` 收尾期），非 FAILED、退出码 0；该用例与本次删除项无关，属 master 基线既有行为 | PASS |
| 10 | 登记表/删除清单对账（正则计行） | - | 登记表 1243 行；删除清单编号行 12 行；1243 + 12 = 1255 闭合 | PASS |
| 11 | `git --no-pager diff --stat 4b38989..179fdf6 -- yate/ tools/ pack/ pyproject.toml .trae/rules/ tests/test_architecture.py` | 0 | 空输出（产品代码、工具、规则、架构守卫、门禁配置零改动） | PASS |
| 12 | 用例总数对账 `pytest tests/ --co -q`（逐文件累加） | 0 | 147 文件 / 3483 收集 ≡ 3473 passed + 10 skipped（与 #4 逐字一致） | PASS |
| 13 | 新增行违禁模式扫描（`+` 行正则：`type: ignore` / `pyright: ignore` / `noqa` / `TYPE_CHECKING` / `Any` / `sleep` / 非 ASCII） | - | 全部 0 命中 | PASS |

### 2.1 与首轮 §十 数字的对账

| 门禁 | 首轮 §十 记录 | 本次实测 | 一致性 |
| --- | --- | --- | --- |
| pyright | 0 / `0 errors, 0 warnings, 0 informations` | 同 | 一致 |
| `pytest tests/ -q -n auto` | exit 0（无汇总行） | exit 0（无汇总行） | 一致 |
| 架构测试 | 37 passed | 37 passed | 一致 |
| 覆盖率 | `92.96%`、`3473 passed, 10 skipped in 163.61s` | `92.94%`、`3473 passed, 10 skipped in 159.68s` | 用例数与跳过数逐字一致；总分差 0.02 个百分点，`TOTAL` 分母（19552 语句 / 6246 分支）未变，属并行 worker 分片下的正常抖动 |
| 冒烟 | `121/121`、`1464/1464`、exit 0 | 4 次：fail、fail、`--jobs 1` 通过、`--jobs 4` 通过 | 不完全一致：本次 `--jobs 4` 下 2 次命中 `stress_rapid_toggles`，首轮 §十 未登记该现象。定性见 §四 m-1 |
| changelog | exit 0 | exit 0 | 一致 |
| `git diff --check` | exit 0、无输出 | 同 | 一致 |

### 2.2 覆盖率与本次改动的测试覆盖

F1 只改 2 个测试文件与 2 份文档，产品代码零改动，故不存在「新增 / 修改的生产代码缺测试」问题；总覆盖率 92.94% >= 75（`pyproject.toml:166 fail_under = 75`，`show_missing = true` 使未覆盖行随报告输出）。新增 / 修改的两个测试文件本身在 #2、#4、#8、#9 中共运行 8 次（4 次全量 + 3 次定向 + 1 次覆盖率），零失败。

## 三、逐条复核结论（对应任务书 6 个必查项）

### 3.1 复核项 1：M-1（MAJOR）是否销账 —— 已销账

逐条对照任务书三个子问：

| 子问 | 实测证据（`tests/test_zero_arg_callbacks.py`，F1 后终态行号） | 判定 |
| --- | --- | --- |
| 断言是否移回 `async with app.run_test()` 上下文内 | `:71` `async with app.run_test() as pilot:` 起；`:73-75` `widget = app.query_one(ResizeWidget)` / `baseline: int = widget.resize_calls` / `await pilot.resize_terminal(120, 40)`；`:78-80` `assert await wait_until(pilot, lambda: widget.resize_calls > baseline)` 位于 `:71` 的 `with` 块内（缩进 12 空格），`with` 块在 `:82` 才结束 | 已移回 |
| 是否改用 `wait_until` 轮询 | `:78-80` 为 `assert await wait_until(pilot, lambda: widget.resize_calls > baseline)`（`timeout` 走 `conftest.py:313` 默认 5.0、`step=0.01`）；`git diff` 显示 `- await pilot.pause()` 与 `-assert widget.resize_calls > baseline`（旧裸断言在 with 块外）已被删除 | 已改 |
| `wait_until` 是否从 conftest 正确导入 | `:19` `from conftest import wait_until`（模块顶层，独立分组）；实现见 `tests/conftest.py:311-331`；同文件 `tests/test_app_find_replace.py:28` 亦以 `from conftest import ... wait_until` 同形态导入，`grep` 实测 40 个测试文件同写法，非新引入模式 | 正确 |
| 是否仍有单一帧裸断言 | 残留扫描：`:53-82` 用例体内除 `:78` 的 `wait_until` 断言外，无其他断言；`:48` 的 `assert app.watch_calls == [...]`、`:98-99` 的 `assert after == ...` 属另两个用例，均为「赋值 + `pilot.pause()` 后读状态」形态（非 resize 派发时序） | 无残留 |
| 是否仍有真实睡眠 | 文件内无 `asyncio.sleep` / `time.sleep`（正则扫描 `sleep` 在 F1 新增行 0 命中；整文件回读亦无） | 无睡眠 |

补充实证：M-1 原症状为「全量并行首跑 `assert 1 > 1`」。本次在 4 次全量 `-n auto`（#2、#9×3）与 3 轮定向 `-n 4`（#8）中，该用例共运行 7 次全部通过，未再出现裸断言失败。修复方向与 `python-coding-style.md` §4.7「禁止依赖真实睡眠时长做断言……或用 wait_until 轮询谓词」及首轮 §四 M-1 的修复建议逐字同构。

### 3.2 复核项 2：m-1（MINOR）函数体内局部 import —— 已销账

| 子问 | 实测证据 | 判定 |
| --- | --- | --- |
| `Color` / `yate_theme` 是否提到模块顶层 | `:15` `from textual.color import Color`、`:22` `from yate.editor_components import theme as yate_theme`；原函数体内的两行（`git diff` 的 `-    from textual.color import Color` / `-    from yate.editor_components import theme as yate_theme`）已删除 | 已提升 |
| 是否按 `python-coding-style.md` §1.3 分组 | 分组实测：标准库 `:11-12`（`asyncio` / `typing`）→ 空行 → 第三方 `:14-17`（`textual.app` / `textual.color` / `textual.reactive` / `textual.widgets`）→ 空行 → `:19` `from conftest import wait_until` → 空行 → 项目内部 `:21-22`（`yate.app` / `yate.editor_components.theme`）；每组内字母序成立（`textual.app` < `textual.color` < `textual.reactive` < `textual.widgets`；`yate.app` < `yate.editor_components`） | 合规 |
| 是否存在残留函数体内局部 import | 全文件回读（106 行）扫描：仅 `:11-22` 一处导入块，三个用例的函数体内（`:25-50`、`:53-82`、`:85-105`）无任何 `import` 语句 | 无残留 |

关于 `from conftest import wait_until` 单独成组是否偏离 §1.3 的三分组：`conftest` 既非标准库也非 `yate` 内部包，而是 pytest 的测试辅助（与第三方测试设施同层）。首轮 m-1 建议的「标准库 / 第三方 / 项目内部」三分组未覆盖 `tests/conftest` 这一层；F1 单独成组并保持字母序，属对既有 40 个测试文件同一写法的自然延续，不构成新违规（定性见 §五 5.2 的降级记录）。

### 3.3 复核项 3：`tests/test_app_find_replace.py:541-560` 的 `nonlocal seen_report` 闩锁 —— 修复有效，语义未放宽，但补偿性存在一处未闭环（见 §四 m-2）

| 子问 | 实测证据 | 判定 |
| --- | --- | --- |
| 是否真的在轮询期间捕获瞬态消息 | `:547` `seen_report = False`；`:549-552` `def _landed() -> bool:` 内 `nonlocal seen_report` + `if "replaced 3" in message_text(app): seen_report = True`；`:562` `assert await wait_until(pilot, _landed, timeout=15.0)`。`wait_until`（`conftest.py:324-331`）每 10ms 调一次谓词并 `await pilot.pause(step)`，即**每次轮询都重新读消息行**，把瞬态命中累积到闭包变量，不再依赖最后一帧 | 有效 |
| 是否仍要求两个文件写入落地 | `:554-558` 返回 `seen_report and two.read_text(encoding="utf-8") == "dog two\\n" and three.read_text(...) == "three dog\\n"`——三个条件为 `and` 合取；`:567-568` 退出后再次断言两文件内容，`:570-574` 断言打开文件内存态 `"x dog y\\n"`、`modified is True`、磁盘仍 `"x needle y\\n"` | 要求未放宽 |
| 是否引入吞异常 | `:559-560` 为 `except OSError: return False`，与 `git diff` 的旧实现（`-` 侧同一 `except OSError: return False`）**完全一致**，属既有语义（Windows `os.replace` 竞态读 PermissionError 视为「尚未落地」）；新增行未新增任何 `except` | 未引入 |
| 是否放宽断言 | 旧形态为「`wait_until` 落地 + 单帧断言消息」；新形态把消息检查并入同一谓词并累计，等价强度更高（不再要求消息与落地同帧）；无断言被删除（`git diff` 中被删的只有 `-            # the replaced total surfaces while the overlay is still open` 与 `-            assert "replaced 3" in message_text(app)` 两行，功能已并入 `_landed`） | 等价 / 更强 |

强度上的唯一妥协（`python-coding-style.md` §6.1「Errors should never pass silently」在测试侧的推论）：把消息检查并入落地谓词后，谓词更早被满足，`wait_until` 返回后不再校验消息仍在屏上。这本身正确（瞬态消息本就不可靠），但**测试名 / docstring 仍宣称「with the replaced total on the message line」**（`:510-511`），而能证明该文案的只剩轮询期间的一瞬。对比同文件 `:734` 与 `:796` 的两处同类断言仍依赖 `wait_until(pilot, lambda: "replaced N" in message_text(app))` 的**终态**读法，本处属更弱的口径。见 §四 m-2（MINOR，不阻塞）。

### 3.4 复核项 4：改动范围与越界检查 —— 全部通过

| 检查项 | 实测 | 判定 |
| --- | --- | --- |
| 是否只触及 2 个测试文件 + 文档 | `git --no-pager diff --name-only 4b38989..179fdf6` 输出恰好 4 条：`unused-symbols-cleanup-plans/overview.md`、`2026-11-08-pr-review-iktr5q-unused-symbols-cleanup.md`、`tests/test_app_find_replace.py`、`tests/test_zero_arg_callbacks.py` | 成立 |
| 产品代码是否零改动 | `git --no-pager diff --stat 4b38989..179fdf6 -- yate/ tools/ pack/ pyproject.toml .trae/rules/ tests/test_architecture.py` **空输出** | 零改动 |
| 越界逻辑改动 | 两个测试文件的 2 个 hunk 已逐行通读：`test_zero_arg_callbacks.py` 仅导入位置 + 一处断言形态；`test_app_find_replace.py` 仅 `:547-562` 的谓词重构。无被测行为改动、无产品断言对象改动 | 无越界 |
| 豁免注释 | 新增行 `type: ignore` / `pyright: ignore` / `noqa` 命中 0；未向 `NON_ASCII_COMMENT_EXEMPT` / `SIZE_EXEMPT_FILES` 等守卫名单追加任何条目（`tests/test_architecture.py` 零 diff，架构测试 37 passed） | 0 |
| `Any` / `TYPE_CHECKING` | 新增行 `\\bAny\\b` / `TYPE_CHECKING` 命中 0 | 0 |
| 非 ASCII 注释 | 新增行非 ASCII 命中 0（两处新增注释 `:76-77` 与 `:544-546` 均为英文 ASCII）；`test_comments_and_docstrings_stay_ascii` 在 37 守卫内通过 | 0 |
| 空白 / 行宽 | `git --no-pager diff --check` 退出码 0、无输出；新增行均 < 100 字符 | PASS |

### 3.5 复核项 5：首轮 §十 七道门禁数字与对账闭合 —— 见 §二、§2.1，一处需补登（冒烟）

- 七道门禁数字：6 项与本次一致（pyright / 全量 pytest / 架构 / changelog / `git diff --check` 及覆盖率用例数），覆盖率总分 92.96 -> 92.94 属抖动，**冒烟一项不一致**（首轮只记 exit 0，本次 4 次中 2 次 exit 1）。定性见 §四 m-1（登记为 MINOR：与被审 F1 改动无关，属 master 基线既有负载敏感场景）。
- 对账 1243 + 12 = 1255 **仍闭合**：本次以正则 `^\\| .[^|]*:[0-9]+.` 重算 `unused-symbols-cleanup-keep-register.md` 得 **1243** 行；`unused-symbols-cleanup-delete-list.md` 编号行 **12** 行；且这两份文件**不在** `4b38989..179fdf6` 的 diff 内（见 §3.4 文件清单），F1 未改动登记表与删除清单。

### 3.6 复核项 6：提交信息与「只提交未推送」、临时探针入库情况

| 检查项 | 实测 | 判定 |
| --- | --- | --- |
| 提交信息格式 | `git log -1 --format=%B 179fdf6` 原始字节：`test(callbacks): poll for async dispatch in review iteration F1` + 空行 + `Fix the MAJOR parallel assertion with wait_until, hoist local imports to module scope, and latch the transient replace-report message. Archive the review record and backfill deviations D12-D15.` + 空行；非 ASCII 字符集为空 `[]`（主题与消息体全英文） | 格式与英文要求满足 |
| `type` 取值 | `git-commit-message.md` §5 列举 `feat` / `fix` / `refactor` / `docs` / `chore`，未含 `test`。实测近 400 笔提交 type 分布：`docs 164 / fix 73 / refactor 29 / test 28 / chore 27 / feat 25 / ci 4 / perf 2` —— `test(` 是仓库存量惯例（28 笔），且本次改动**确为测试改动**。按 §6「`type` 可选值」为允许集表述、非封闭枚举，加之仓库一致性优先（`python-coding-style.md` §6.3「可读性 > 风格一致性」反向推论：不为字面一致牺牲语义准确），判**不构成违规**，仅登记提示（§五 5.2 降级记录） | 合规（附提示） |
| `scope` | `callbacks`（本次两处改动均在 0 参数回调 / 回调时序测试域） | 合规 |
| `subject` | 祈使句、无末句号、< 72 字符 | 合规 |
| 是否只提交未推送 | `git status --short --branch` -> `## feature/enh-unused-symbols-cleanup...origin/feature/enh-unused-symbols-cleanup [ahead 4]`；`git log --oneline origin/feature/... -3` 顶端仍为 `1e094db` | 未推送 |
| 临时探针是否入库 | `git status --short` 的 `??` 项：`_ast_candidates.md`、`_ast_facts.md`、`_ast_probe_calls.json`、`_ast_probe_output.json`、`_ast_verdicts.json`、`cov_exit.txt`、`cov_exit2.txt` —— 全部 untracked，未入库；`git ls-tree` 视角下 F1 的 4 个文件不含任何探针。按任务书要求，评审时忽略其存在，不擅删 | 未入库 |

## 四、Issue 清单（按严重度排序）

**统计：BLOCKER 0 / MAJOR 0 / MINOR 2**（首轮 M-1、m-1 均销账；本次新发现 2 条 MINOR，均不阻塞合并）。

两条新 MINOR 的共同定性：**均非 F1 引入的缺陷**，而是「上一轮记录未登记 / 修复口径可再收紧」的事实。按 `task-orchestration.md` §二.6（仅 minor -> 登记待办）不构成返工理由。

### [MINOR] m-1 冒烟 `stress_rapid_toggles::toggles_back` 在 `--jobs 4` 下负载敏感（2/4 次失败），首轮 §十 未登记

**位置**：`tools/smoke_test/scenarios/stress.py:154-157`（断言 `:157` `checks.append(Check("toggles_back", before, app.editor.explorer_visible))`）；首轮记录 `.trae/reviews/2026-11-08-pr-review-iktr5q-unused-symbols-cleanup.md:311`

**问题**：本轮 4 次冒烟中，`--jobs 4` 两次出现同一 check 失败（`expected False / actual True`），`--jobs 1` 通过、第 3 次 `--jobs 4` 通过。即典型负载敏感。首轮 §十 只记「`121/121`、`exit 0`」，未登记该现象，导致 §十 与本轮实测不完全一致。

**归属证据（非 F1 引入）**：`git --no-pager log --oneline -3 -- tools/smoke_test/scenarios/stress.py` 顶端两笔为 `81f8486 refactor(smoke): use named settling constant and nonlocal streak` 与 `c9f5589 fix(smoke): settle explorer toggle convergence under key storms`；`git merge-base --is-ancestor 81f8486 fb3c398` 返回成功，即两者**已在本任务 master 基线内**；F1 的 4 文件清单不含 `tools/`。

**为何只记 MINOR**：该场景已内置 `wait_until` + `_SETTLED_POLLS` 连续收敛闩锁（`stress.py:138-156`），属已知负载敏感点且已有缓解；失败不落在 `pytest` 合并硬门槛上（冒烟是端到端补充门禁），且串行口径 100% 通过。

**建议**（不属本轮返工）：把 `toggles_back` 的取值改为「闩锁时刻的稳定值」而非 `wait_until` 返回后的即时读取（与 `:124` `sidebar_matches_flag` 的读法一致），或把 `_SETTLED_POLLS` 再抬一档；同时在后续评审记录中按 `task-orchestration.md` §二.7「并行下出现时序 flake 必须用 -n 1 复核并修用例」把该 flake 常态登记，避免每次复验都被当作新发现。

### [MINOR] m-2 `test_project_replace_end_to_end_open_edit_replace` 的「消息行」断言强度降至瞬态，docstring 与实测口径不再一致

**位置**：`tests/test_app_find_replace.py:547-562`（谓词）、`:510-511`（docstring 宣称），对照同文件 `:734`、`:796`

**问题**：F1 把 `assert "replaced 3" in message_text(app)`（旧 `:555`）并入 `_landed` 谓词并闩锁。谓词一旦满足即返回，此后不再校验消息内容——而 `"replaced 3 occurrence(s) in 3 file(s)"` 由 `yate/editor_components/find_replace.py:558` 写入后，会被 `yate/editor_components/commandline.py:400-403` 的 `idle()`（`_show_message` 覆写 `self._message`）覆盖。于是「消息行显示 replaced 3」只在轮询的某一瞬成立，docstring `:510-511`「with the replaced total on the message line」描述的终态语义已不再被断言保证。

**为何只记 MINOR**：
1. 三条件为 `and` 合取、退出后仍二次校验两文件落地（`:567-568`）与内存态 / 磁盘态（`:570-574`），**没有任何断言被删除或放宽**；核心断言强度未降。
2. 消息文案本身另有终态覆盖：`tests/test_app_find.py:846`（`assert "replaced 3" in message_text(app)`）、`:890`、`tests/test_app_find_replace.py:734`、`:796`。
3. 该形态是消除 flake 的必要折衷——原断言在负载下必现失败（首轮 §十 已记录实测 `assert replaced 3 in [#6c7086] Ready. Press F1 for help.[/]`）。保留单帧终态断言等于保留 flake。

**建议**（不阻塞）：把 docstring `:510-511` 改成「…with the replaced total observed on the message line while the replace lands」，使文档口径与实测口径一致；或把 `two` / `three` 的消息断言移到用 `wait_until(pilot, lambda: "replaced 3" in message_text(app))` 的并行用例（已存在 `:796`）里保持终态覆盖。

### 已撤销的初判（误报剔除，保留痕迹以便追溯）

| 初判 | 反证依据 | 处置 |
| --- | --- | --- |
| 「`from conftest import wait_until` 单独成组违反 §1.3 三分组，m-1 未真正销账」 | 回读 §1.3 原文：分组为「标准库 / 第三方 / 项目内部」，`tests/conftest.py` 不属任一组；仓库 40 个测试文件同写法（`grep -c` 实测），F1 只是延续既有形态而非新违规；且首轮 m-1 的修复建议原文就要求「提到模块头（第三方组 / 项目组）」，`conftest` 组并不在建议范围内 | **删除** |
| 「`test()` 不在 `git-commit-message.md` §5 允许集，提交信息违规」 | §5 表述为「`type` 可选值：…」的列举而非封闭枚举；实测近 400 笔提交 `test` 出现 28 次，属仓库既有惯例；改动内容确为测试 | **降级**为提示（§五 5.2） |
| 「覆盖率 92.94 < 首轮 92.96，属覆盖率下降」 | `TOTAL` 分母未变（19552 语句 / 6246 分支），差值 0.02 个百分点对应 1 条 missing 语句的并行分片抖动；F1 产品代码零 diff，新增 / 修改代码全为测试，按 `python-coding-style.md` §4.7 / §五 不构成覆盖率下降 | **删除** |
| 「`--jobs 4` 冒烟失败是本任务引入的回归，应记 MAJOR」 | `stress.py` 的 `81f8486` / `c9f5589` 均已在 master 基线内（`merge-base --is-ancestor` 验证），F1 未触 `tools/`；`--jobs 1` 100% 通过 | **降级**为 MINOR（§5.2） |
| 「`stress_rapid_toggles` 失败必须要求本任务修用例（§二.7）」 | §二.7 的「修用例」针对**本任务门禁出现 flake**的情形；该场景的 flake 与其修法（`c9f5589`）均为 master 基线既有产物，本任务改动与之无因果关系，要求本任务修属超范围加码 | **降级**为 MINOR + 建议项 |

## 五、强制自我批判记录

按 `.trae/agents/code-review-expert.md` 剧本，初版清单完成后逐条反证，结论登记如下。

### 5.1 逐条反证的实证依据

| 条目 | 是否回到代码实证 | 实证方式 | 是否存在推翻性上下文 |
| --- | --- | --- | --- |
| M-1 销账 | 是 | 重读 `tests/test_zero_arg_callbacks.py` 全文 106 行（行号 `:71` / `:78-80` / `:19`）；重读 `conftest.py:311-331` 实现；`git diff` 确认旧裸断言在 `with` 外被删 | 无（7 次运行全过） |
| m-1 销账 | 是 | 重读 `:11-22` 导入块逐行确认分组与字母序；全文件扫描无函数体内 import | 无 |
| 复核项 3（replace 闩锁） | 是 | 重读 `tests/test_app_find_replace.py:509-576` 全用例；重读 `find_replace.py:535-560`、`commandline.py:364-415`（`write` / `_show_message` / `idle` 覆写链）、`editor.py:420-430`（`message()` 走 `prompt_bar.write`）、`overlay_flows.py:76` 与 `editor_compose.py:245`（同一 `ed.message` 注入点） | **有**：确认消息确被 `idle()` 覆盖 -> 支撑 m-2 的「瞬态」定性；同时确认三条件仍为合取 -> 推翻「放宽断言」初判 |
| m-1（冒烟 flake） | 是 | 4 次实跑 + `stress.py:115-160` 回读 + `git log` / `merge-base --is-ancestor` 归属验证 | **有**：`--jobs 1` 通过、第 3 次 `--jobs 4` 通过、修复提交在 master 基线 -> 不记 MAJOR 回归 |
| m-2（消息断言强度） | 是 | 重读 `:510-511` docstring、同文件 `:734` / `:796` 的终态读法、`test_app_find.py:846` 的重复覆盖 | **有**：消息文案另有 3 处终态覆盖 -> 不记 MAJOR |

### 5.2 降级记录

| 初判 | 最终 | 理由 |
| --- | --- | --- |
| 提交 `test(` 不在 `git-commit-message.md` §5 允许集 -> MINOR 违规 | 降为**提示**（不计入统计） | §5 为列举而非封闭枚举；仓库近 400 笔提交 `test` 28 次，属既有惯例；改动性质确为测试 |
| `--jobs 4` 冒烟失败 -> MAJOR（门禁非确定性失败） | 降为 **MINOR** | 归属验证显示场景与修法均在 master 基线；`--jobs 1` 100% 通过；不在 `pytest` 合并硬门槛上 |
| 消息断言强度下降 -> MAJOR（断言放宽） | 降为 **MINOR** | 实证显示无断言删除、三条件合取、退出后二次校验落地；且文案另有 3 处终态覆盖 |

### 5.3 漏报自查（六维度反向扫描）

| 维度 | 复查结论 |
| --- | --- |
| 正确性 | F1 两个测试 hunk 的断言语义逐条核对：M-1 的谓词 `resize_calls > baseline` 与原断言同式，只把「单帧读」换成「轮询读」；replace 用例三条件合取 + 退出后二次校验，无弱化。`nonlocal seen_report` 是 Python 3 闭包写入的标准写法，无作用域陷阱。**无新增发现** |
| 边界条件 | `wait_until` 超时语义（`conftest.py:331` `return predicate()`）保证超时后仍做最后一次判定，故 `assert await wait_until(...)` 在真超时时会失败而非误过（不会把超时当成功）。M-1 用例 `timeout` 取默认 5.0，在 `--jobs 4` / `-n auto` 下 7 次运行均远未逼近。replace 用例 `timeout=15.0` 保留。**无新增发现** |
| 异常处理 | F1 新增行无 `except`（`except OSError: return False` 为既有行，`git diff` 显示未改动）；无吞异常、无裸 `except:`。**无新增发现** |
| 并发安全 | 仅测试文件改动，无共享状态；`seen_report` / `streak` 类闭包变量均为单用例单任务内使用，`wait_until` 在同一事件循环内串行调用谓词，无竞态。**无新增发现** |
| 性能 | `wait_until` 轮询 `step=0.01`，M-1 用例典型 1-2 次即满足（`-n 4` 下 40 用例 9-14s，与首轮同量级）；全量 `-n auto` 4 次耗时 0.4-1.1 倍波动，无退化迹象。**无新增发现** |
| 类型与测试覆盖 | pyright `0/0/0`；`from conftest import wait_until` 在 pyright strict 下无诊断（`conftest.py:311` 带 `# noqa: Any` 说明理由）；全量 3483 收集 = 3473 passed + 10 skipped；37 架构守卫通过；覆盖率 92.94 >= 75。**无新增发现** |
| 架构边界 R1-R15 | `architecture-boundaries.md`、`test_architecture.py` 零 diff；F1 未新增任何 import 连线（`conftest` 属 tests 域，不在 `yate/` 依赖图内；`textual.color` / `yate.editor_components.theme` 为既有导入的位置移动）。**无新增发现** |
| 文档纪律 | `overview.md` 与首轮记录的 F1 新增段做绝对路径扫描：`overview.md` 0 命中；首轮记录 2 处命中均为记录自身的正则字面量（`[A-Za-z]:\\\\`、`/home/`、`/Users/`），未暴露本机真实路径，不属 `doc-conventions.md` §五 违规。D12-D15 四条偏离登记内容与实测一致（D15 的 safe-delete 钩子事实本轮亦复现：覆盖率门禁因此改为后台 + 落盘退出码，与 D15 处置一致）。**无新增发现** |

### 5.4 结论登记汇总

| 状态 | 条目 |
| --- | --- |
| 确认保留 | m-1（冒烟 `stress_rapid_toggles` 负载敏感 + 首轮 §十 漏登）、m-2（replace 用例消息断言强度降至瞬态、docstring 口径失配） |
| 降级 | `test(` type 前缀提示（不计统计）、冒烟 flake MAJOR->MINOR、消息断言 MAJOR->MINOR（理由见 §5.2） |
| 删除 | 「`from conftest` 单独成组违反 §1.3」、「覆盖率 92.96->92.94 属下降」、「冒烟失败是本任务引入的回归」、「要求本任务修 master 基线既有 flake」（理由见 §四 已撤销初判表） |
| 销账确认 | 首轮 M-1（MAJOR）、首轮 m-1（MINOR）——均经代码实证 + 多次实跑确认修复 |

## 六、最终裁决

**APPROVE**

理由：

1. 首轮 1 MAJOR（M-1）与 1 MINOR（m-1）**均已修复并实证销账**（§3.1 / §3.2），符合 `task-orchestration.md` §二.6「迭代上不封顶，直至无 blocker / major」。
2. 本次复验**0 BLOCKER / 0 MAJOR**；2 条 MINOR 均非 F1 引入、均不落在合并硬门槛上，按 §二.6「仅 minor -> 登记待办」不阻塞合并。
3. 合并硬门槛实测全部通过：pyright 0 诊断、`pytest tests/ -q -n auto` 4 次全绿、架构 37 passed、覆盖率 92.94 >= 75、`git diff --check` 干净、changelog 一致。
4. 改动范围收敛：只触及 2 个测试文件 + 2 份文档，产品代码 / 规则 / 架构守卫 / 门禁配置零 diff；无豁免注释、无 `Any` / `TYPE_CHECKING`、无非 ASCII 注释。
5. 对账 1243 + 12 = 1255 仍闭合；提交信息合规且只提交未推送；临时探针未入库。

## 七、未解决项

1. **m-1（MINOR，不阻塞）**：`tools/smoke_test/scenarios/stress.py:157` 的 `toggles_back` 在 `--jobs 4` 下负载敏感（本轮 4 次中 2 次失败，`--jobs 1` 通过）。场景与既有修法 `c9f5589` / `81f8486` 均属 master 基线，非本任务引入；建议后续单独立项收紧取值口径。
2. **m-2（MINOR，不阻塞）**：`tests/test_app_find_replace.py:510-511` docstring 宣称「with the replaced total on the message line」，而实际断言已降为轮询期间瞬态捕获；建议改写 docstring 口径。
3. **首轮 §十 记载需补正**：「`tools.smoke_test run --jobs 4` exit 0」未反映本轮实测的 2/4 负载敏感失败。本次以只读方式登记，未修改首轮记录（任务书禁止）。
4. **flake 复现率样本有限**：冒烟失败 2/4（`--jobs 4`）、全量 pytest 0/4、定向 0/3。样本量不足以给出概率估计，建议后续 CI 侧累积统计。
5. **`test()` 提交前缀提示**：`git-commit-message.md` §5 是否应把 `test` 补入允许集，属规则层决定，不在本次评审范围内。

## 八、实测命令回执（可复核）

```text
pyright yate/ tests/ tools/ pack/                 -> exit 0,  0 errors 0 warnings 0 informations
pytest tests/ -q -n auto                          -> exit 0  (no summary line under -q)
pytest tests/test_architecture.py -q               -> exit 0,  37 passed
pytest tests/test_architecture.py -v              -> exit 0,  37 passed in 16.64s
pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75
                                                  -> exit 0,  92.94%  (3473 passed, 10 skipped in 159.68s)
tools.smoke_test run --jobs 4                     -> exit 1,  120/121 scenarios, 1463/1464 checks (85.55s)
tools.smoke_test run --jobs 4   (rerun)           -> exit 1,  120/121 scenarios, 1463/1464 checks (84.60s)
tools.smoke_test run --jobs 1                     -> exit 0,  121/121 scenarios, 1464/1464 checks (72.47s)
tools.smoke_test run --jobs 4   (3rd)             -> exit 0,  121/121 scenarios, 1464/1464 checks (79.40s)
tools.changelog check                             -> exit 0,  released sections up to date
git --no-pager diff --check                       -> exit 0,  (no output)
pytest tests/test_zero_arg_callbacks.py tests/test_app_find_replace.py -n 4  (x3)
                                                  -> exit 0 / 0 / 0,  40 passed each
pytest tests/ -q -n auto   (rerun x3)             -> exit 0 / 0 / 0
pytest tests/ --co -q                             -> exit 0,  147 files / 3483 collected
```

> 本记录只记录发现与核对结论，修复排期遵循 `doc-conventions.md` §2.2（评审记录与修复方案互相链接、各自独立）。首轮记录 `2026-11-08-pr-review-iktr5q-unused-symbols-cleanup.md` 保持只读，未作任何修改。
