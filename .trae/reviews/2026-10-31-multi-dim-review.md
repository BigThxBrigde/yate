# 全仓库多维度评审记录（multi-dim-review）

> skill：`.trae/skills/multi-dim-review`（13 维度全量审计路由）。本记录为只读事实文档：
> 只记发现与结论，不含修复排期（doc-conventions.md §二.1）。

**总裁定：APPROVE（0 BLOCKER / 0 MAJOR / 3 MINOR）**——三条 MINOR 均为登记级
（健壮性观察 / 测试时序卫生 / 文档漂移），无合并阻断项。

- 评审对象：master `0ae1a64`（工作树 clean，与 origin/master 同步），覆盖 `yate/` +
  `tools/` + `tests/` 全量。
- 评审方式：fan-out 5 名只读审查员（SA 正确性+健壮性 / SB 安全+算法+性能 /
  SC 架构+结构+职责 / SD 类型+风格+运行时可观测 / SE 测试+文档），两波派发
  （≤3 并发）；主代理对全部线索逐条回读当前文件复核（证据纪律 Step 4），
  硬门禁由主代理亲跑（Step 7）。
- 豁免集对照：`SIZE_EXEMPT_FILES` / `UI_FROZEN_FILES` / `NON_ASCII_COMMENT_EXEMPT` /
  `PRINT_EXEMPT_SITES` / R2 Protocol 白名单 / 命名白名单 / `SCROLLBAR_EXEMPT` ——
  本轮零新增命中。
- 登记项不重提（既往轮次已定案，未发现推翻性新证据）：arch-sec-audit F4–F7、
  uninstall 中途 OSError 存量语义、yxp.py:398-399 分支缺口、yxp.py 尺寸豁免、
  cli.py:413 排版、空目录噪声提示、logs mkdir mode 窗口、`.trae/` 文档面本机路径
  存量（42 处 / 21 文件，按「随下次修改迁移」待办）。

## 门禁实测（本机 Windows，master worktree，`.venv` Python 3.13.2）

| 门禁 | 命令 | 结果 | 退出码 |
|---|---|---|---|
| pyright | `python -m pyright yate/ tests/ tools/` | 0 errors, 0 warnings, 0 informations | 0 |
| changelog | `python -m tools.changelog check` | released 段最新；Unreleased 滞后 36 笔（设计容忍） | 0 |
| 架构 | `pytest tests/test_architecture.py -q` | 37 passed in 12.18s | 0 |
| pytest 全量·首跑 | `pytest tests/ -q -n auto` | 1 failed（lua lint，见「环境事故」定性） | 1 |
| pytest 全量·复跑 | `pytest tests/ -q -n auto` | 全绿（`-q` 口径未打印汇总行，以退出码为准） | 0 |
| 覆盖率 | `pytest tests/ --cov=yate --cov-branch -n auto` | TOTAL 18307 stmts，92.25%（Required 75 reached） | 0 |
| 冒烟 | `python -m tools.smoke_test run --jobs 4` | 117/117 scenarios passed，84.09s | 0 |

## 环境事故与定性（非代码缺陷，已现场恢复）

**现象**：pytest 全量首跑唯一失败
`tests/test_lua_lint.py::test_bundled_lua_files_pass_the_linter`，4521 条 issue，
首条 `Issue(path=...extensions/_yate.d.lua, line=1, rule='crlf', message='file contains
CR characters')`；`-n 1` 复跑同败（非并行负载假象）。

**根因链**（逐条实证）：

1. commit `99f8158`（2026-10-22）为 `*.lua` 加 `.gitattributes` `text` + `eol=lf`；
2. 本 master worktree 的 10 个 `.lua` 文件落盘早于该提交（旧检出在
   `core.autocrlf=true` 下产生 CRLF 磁盘态），属性生效后 git 状态判定仍为
   clean（clean filter 把 CRLF 归一为 LF 后与 LF blob 相等），**陈旧状态对 git 不可见**；
3. linter 按磁盘字节判定（release 打包原样携带 `yate/extensions/` 数据，磁盘 CRLF
   会随 wheel / PyInstaller 发布），**linter 守卫行为正确**；
4. CI（ubuntu）跑同测试不红的原因推断：lupa 为可选依赖，CI 未装则该用例 skip
   （`requires_lupa`），CRLF blob 风险从未在 Linux 腿暴露。

**处置**：主代理以 Python 字节级替换（`\r\n` → `\n`）就地规范 10 个文件（未触碰
git 指令）；复跑 `test_lua_lint.py` 11 passed。恢复后 `git status --short` 对这 10 个
文件显示幻影 ` M`（`git diff` 为空、内容与 HEAD 一致；`eol` 属性 + stat 缓存的
表面现象），无内容差异、无可提交物。

**启示（供后续立项，非本记录排期）**：a) linter 对 `eol=lf` 属性文件可给出
「worktree 陈旧检出，建议重新规范化」的定向提示，避免 4521 条噪声断言；
b) `requires_lupa` skip 使该真实合并门在 CI 形同虚设，可评估安装 lupa 的 CI 腿。

## 结论清单（主代理复核后终版）

[minor] yate/editor_term/pty_proc.py:112-116,125-128,135-138,149-153 — PTY 四处
`except OSError: pass` 零可观测性
Problem：`write` / `resize` / `terminate` / `_finished` 的 docstring 均自述
best-effort 契约（"never raises on a dead PTY"），意图明确、非误吞；但四个分支
全部无日志，PTY 死亡与安静无任何 tracing 区分，违背 R12 跨层调用可观测精神
（D2）。`write` 在每次击键路径上，逐次打日志会刷屏——需一次性状态转换日志
（首次失败置标志打一条 debug）。
Fix（建议，不落盘）：死亡首次检出时 `log.debug("pty write failed (child dead): %d", code)`
一次。

[minor] tests/test_app_find.py:1151 — 实时搜索用例依赖真实睡眠 `await asyncio.sleep(0.3)`
Problem：与刚修复的 3 处防抖 flake（`test_live_search_debounces_rapid_typing` 族，
冻结窗口 + 轮询）同族：按下 "needle" 后睡 0.3s 等防抖窗口，属 §4.7 禁止的
"睡够就行" 假设，并行负载下可 flake。同文件 1138 用例清空路径无睡眠，仅此一处。
Fix（建议，不落盘）：冻结 `prompt_flows` 的 live-search 窗口常量为远大于测试
生命期 + `wait_until` 轮询 `search.query`。

[minor] 豁免文件行数漂移（规则文本 vs 实测，D7 文档漂移）
Problem：`yate/editor_core/buffer.py` 1565（规则登记 1565，一致）、
`yate/keymaps/vim.py` 1528（一致）、`yate/editor.py` 1239（登记 1238，+1）、
`yate/services/yxp.py` 841（登记 830，+11）、`yate/editor_syntax/langdefs.py` 841
（登记 813，+28）。均仍在豁免名单内、零违规，但 §三.7 要求"修改文件时须同步
更新行数"，三处登记数字已过时。
Fix（建议，不落盘）：下次触碰相应文件时同步规则文本与 `SIZE_EXEMPT_FILES` 注释。

**观察（不计 finding）**：`tools.changelog check` 报 released 段 595 条 + Unreleased
41 条缺 zh（生成物 `[缺中文]` 标记），门禁按设计 exit 0；双语手册配对
（extensions / themes / yaterc / games / which-key / lsp 的 en+zh）完整成对。

## 逐维度结论

| 维度 | 结论 | 依据（抽样） |
|---|---|---|
| D1 正确性 | clean | `take_dirty_range`（消费）vs `dirty_range`（窥视）分工有意且正确（completion.py:326-345 用 peek，highlighting.py:280 用 consume）；buffer 契约 docstring 齐备；pyright 0 + 全量测试绿 |
| D2 健壮性 | 1 MINOR | pty_proc 四处静默 pass（见结论清单）；logs.py:371-374 faulthandler fallback 带 `# noqa: BLE001` + 理由，合规；editor.py:661-674 teardown 有日志，正面样例 |
| D3 安全 | clean | 项目 rc 经 `is_trusted(project.parent)` 门控（yaterc.py:128-135，debug 日志 + 用户提示）；`./extensions` 自动加载经 `is_trusted(cwd)`（extensions/loader.py）；yxp 成员名校验 / casefold 去重 / symlink 卫语句在位（yxp.py:214-229）；`shell=True` 为文档化的用户显式行为（shell.py / shell_flows.py，无混合来源字符串拼接） |
| D4 算法与复杂度 | clean | buffer.py loaded-interval 表 `bisect` O(log k)（279-343）实证；perf-audit #47（2026-10-26，PR !104）已清每击键 O(文档) 类，未发现新的复杂度类回退 |
| D5 性能 | clean（0 缺陷 0 疑点） | #47 修复波后无新证据；terminal.py:252-260 启动期有界轮询属合理模式 |
| D6 架构边界 | clean | 37 守卫用例全绿；`self.log` / `.app.log` 零命中（仅注释）；相对导入零命中；`# pyright: ignore` 5 处全在 themes.py 且带理由注释（用户主题运行时校验，510-513）、`# type: ignore` 7 处全在 pty_proc.py POSIX/ctypes 平台分支；print() 仅登记豁免面 |
| D7 结构与职责 | 1 MINOR（行数漂移） | 越线文件均在 `SIZE_EXEMPT_FILES`；包 `__init__` 惰性与门面例外合规（守卫 #24/#25/#31/#32） |
| D8 类型纪律 | clean | `Optional[` / `Union[` / `TYPE_CHECKING` / `App[Any]` / `Screen[Any]` 在 yate/ 全零（changelog 资源里的历史字样非代码）；pyright strict 0 |
| D9 风格惯用 | clean | 日志 f-string 零命中（惰性 % 全覆盖）；ASCII 注释守卫全绿；print 仅 `PRINT_EXEMPT_SITES` |
| D10 并发与可观测 | clean | PTY 读线程经 `_post` 投递事件循环（pty_proc.py:140-147）；caplog 用例统一走 `_open_debug_log` 助手并显式 `propagate=True`（test_lsp.py:1418-1429、test_fonts.py:819-825，docstring 自述原因）；support_mouse 闸门守卫在位 |
| D11 测试 | 1 MINOR + 环境事故 | test_app_find.py:1151（见结论清单）；防抖修复模式（冻结窗口 + wait_until）在 test_app_render.py:248-351 在位；主题切换测试 finally 恢复 mocha（test_app_manual.py:75-127） |
| D12 文档与提交卫生 | clean | 双语对完整；近期提交均 `type(scope): subject` 英文（0ae1a64 docs(skills) 等）；CHANGELOG 为生成物未被手改 |
| D13 硬门禁 | 全绿 | pyright 0 + changelog 0 + 架构 37 passed + 全量 exit 0 + 覆盖率 92.25% + 冒烟 117/117，全 exit 0（首跑 lua lint 红灯为环境陈旧态，恢复后全绿） |

## 已核查并排除（误报删除项）

- themes.py 5 处 `# pyright: ignore[reportUnnecessaryIsInstance]`：合法——用户自写
  主题是运行时数据，isinstance 校验有意为之，理由注释在位（510-513）。
- pty_proc.py 7 处 `# type: ignore`：POSIX-only 平台导入（fcntl/pty/termios…）与
  ctypes WinDLL，Windows 静态检查的标准处理，非类型逃逸。
- logs.py:371-374 裸 `except Exception: pass`：带 `# noqa: BLE001` 与 best-effort
  自述，合规。
- yaterc.py:195 `exec`：`# noqa: S102 - intentional rc execution` + 项目 rc 信任门控
  在位（yaterc.py:124-135），非 RCE 缺口。
- test_lsp.py:370 `asyncio.sleep(1.0)`：假 LSP 服务器制造静默以触发客户端超时，
  非时序断言，余量充足。
- editor.py:692 `Screen[object]` 注释：`current_screen()` 实际返回 `Screen[None]`
  并显式收窄，守卫 #22 认可的精确形态。
- cli.py / diagnostics.py / logs.py 的 `print`：全部落在 `PRINT_EXEMPT_SITES`；
  emulator.py `_print` 为方法名非内建。

## 优点

- 架构执法面（37 守卫）+ pyright strict 0 + 覆盖率 92%+ + 冒烟 117 场景的门禁
  组合在真实环境中持续有效：本轮唯一红灯正是 lua lint 守卫抓住了 git 看不见的
  worktree 陈旧状态——守卫比版本控制本身更严格，正是它的价值。
- 信任门控（rc / extensions / 主题三入口）与 .yxp 加固在连续两轮安全审计后保持
  完整，无新绕过面。
- 测试时序卫生的修复模式（冻结窗口 + 轮询）已成体系，caplog 助手 docstring
  把"为什么 propagate=True"写进代码。
