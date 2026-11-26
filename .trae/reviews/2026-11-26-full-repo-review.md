# 2026-11-26 全仓库多维度评审（只读）

- 基线：本地 `master` `b97a695c`（= `origin/master`，`v0.2.18-268`）；距上一轮全仓基线
  `f7e34c34`（[2026-11-20](2026-11-20-full-repo-review.md)）73 提交 / 120 文件 / +11274 −1143。
- 方法：`multi-dim-review` 技能 13 维度、audit scope。12 个只读分区审查员分四波 fan-out
  （每波 3 个并行），主代理逐条回读 `文件:行号`、跑只读探针、剔除已登记项与误报后
  亲跑门禁。分区、波次与任务书见 [full-repo-review-plan.md](../documents/full-repo-review-plan.md)。
- 本轮**不修改产品代码**；修复另按 `plan-before-execute.md` 立项，批准前零代码改动。
- 定级口径：D4 复杂度类由构造直接定级（热路径或大输入即 MAJOR），实测数字只用于校准影响面；
  MINOR 分「影响面窄的边界缺陷」与「测试 / 文档漂移」两类，逐条写明触发条件。
  探针脚本与输出不入库，本文只引用实测数字。

Overall: REQUEST_CHANGES — 6 MAJOR + 27 MINOR，0 BLOCKER；7 条 Suspects、20 条 Suggestions；
审查员另报 24 条候选经回读或实测反证撤回。

## 一、维度总表

| 维度 | 结论 | 关键证据 / 代表反证 |
|---|---|---|
| D1 正确性 | **2 MAJOR** + 3 MINOR | vim count 无上限循环（`../../yate/keymaps/vim.py:1000,1007,1014`）；分派无异常边界（`../../yate/editor.py:806`）；分数分母裸 `ValueError`、`workspace/configuration` 非等长、signature 高亮错位 |
| D2 健壮性 | **1 MAJOR** + 13 MINOR | 发布回滚只对 `RuntimeError` 生效（`../../tools/release/cli.py:436`）；zip 回滚失败后备份仍被删、探针假 PASS、子进程无 timeout、不变量只扫末位 App 等工具链边界 |
| D3 安全 | clean | 项目 rc / 工作区主题 / 扩展自动加载三处信任门控在位；yxp 成员名校验（反斜杠、绝对路径、`..`、保留目录）未回归 |
| D4 复杂度 | **2 MAJOR** + 2 MINOR（另与 D1 共计 vim count 一条） | `buffer_completions` 每请求全文档并集（10 万行 165 ms）；`diff_words` 字符级 O(n·m) 占 UI 线程；诊断行索引按 span 展开、toggle 注释三遍全表拷贝为 MINOR |
| D5 性能（常数因子） | 6 SUSPECT | palette 全量 sort、which-key 每键刷新、终端 20 ms 轮询、日志无保留策略等按纪律保留，不升级 |
| D6 架构边界 | clean | 架构守卫 47 项全绿；`UPWARD_EDGES_FROZEN` 仍为空集，无新增反向边 |
| D7 结构职责 | 1 SUGGESTION | 5 个 >180 行的函数维持观察（`vim.py:847` 291 行最大） |
| D8 类型纪律 | clean | pyright strict 四路径 0 诊断 |
| D9 风格 | 1 MINOR | `tests/` 行宽超限 4 处 |
| D10 并发可观测 | 2 MINOR + 1 SUSPECT | LSP 请求 / didChange 失败、服务器 stderr、信任存储读取均无日志；`dispatch_change` 锁表误摘竞态 |
| D11 测试 | **1 MAJOR** + 3 MINOR | `support_mouse` 闸门顺序守卫恒真（负向演练仍 True）；并行下可能空过的配对用例、起不来即 skip、错误分支零覆盖 |
| D12 文档 | 3 MINOR | 冒烟 tag 列表漏 2 项；`logs.py` docstring 与实现不符；`editor_view` 旧名 14 处、pyright 门禁漏 `pack/` 5 处、基线分支写作 `main` 3 处等 |
| D13 门禁 | 全部 exit 0 | 详见 §八 |

## 二、Findings

### MAJOR

#### [MAJOR] `../../tests/test_architecture.py:1436-1440` — `support_mouse` 闸门顺序守卫恒真

Problem: 守卫取 `source.index("support_mouse")` 的**首个**命中，与
`await super().on_event(event)` 的位置比先后。`../../yate/app.py` 里该标识符首现在
`on_event` docstring 的第 260 行，真实闸门在 `:268-271`、转发在 `:272`。负向演练（内存中
改写源码后求值守卫表达式）：删除 `268-271` 四行 → 仍为 True；把闸门整体移到转发之后 →
仍为 True。守卫对它要防的回归（鼠标闸门被删或后移）没有检出力；当前产品行为本身正确。
Fix: 按代码行定位闸门（取 `on_event` 函数体比较两条语句的行号），并补一条「闸门后移即判红」
的负向用例。

#### [MAJOR] `../../yate/editor_components/completion.py:273-286,448-514` — `buffer_completions` 每次请求重做全文档词集并集

Problem: `_words_from_buffer` 每次请求逐行 `words |= row_words`，把整份 buffer 的行词集
重新并一遍（行词集本身按 `content_version` 增量缓存），对其它打开的 buffer 重复同一过程；
随后对全部候选过滤、`sorted` 全排序、为每个命中构造 `Completion`，最后才 `items[:64]`
（`:514`）。单次请求成本与文档行数和词数成正比，运行在 UI 线程。实测（探针，每行约 10 个词的
合成文档，热缓存）：2 万行 ≈ 32 ms、10 万行 ≈ 165 ms，随行数线性。有 debounce 故不是每击键，
但每次补全刷新都要付全文档代价。
Fix: 按 buffer 维护随 `content_version` 增量更新的聚合词集（或缓存 `_RowWords` 的并集，
版本不一致时只并入脏区行）；top-k 改 `heapq.nsmallest` 或提前截断。

#### [MAJOR] `../../yate/editor_core/diff.py:114-130` — `diff_words` 字符级 O(n·m)，在 UI 线程按行对调用且只限行数

Problem: `diff_words` 对整行做 `difflib.SequenceMatcher(None, a, b, autojunk=False)`；
`../../yate/editor_components/diff/screen.py:282-290` 在重算时对每个 replace hunk 的每对行
各调用一次。唯一的规模闸 `MAX_DIFF_LINES = 20000`（`screen.py:54`、
`../../yate/flows/overlay_flows.py:168`）只限行数、不限行长。实测：JSON 数组行
1000 / 2000 / 4000 字符 → 0.044 / 0.254 / 0.907 s（超线性），空白密集行 3001 字符 1.12 s；
prose 与 minified 2000 字符仅 0.06–0.08 s。含长行的生成文件 / 数据文件打开 diff 视图时，
每个替换行对可冻结 UI 近一秒。
Fix: 给行长设上限（超限退回整行高亮），或先按 token 切分再做词级 `SequenceMatcher`，
把 n·m 从字符数降到 token 数。

#### [MAJOR] `../../yate/keymaps/vim.py:616,880,991,1000,1007,1014,1506` — count 无上限，重复型命令在 UI 线程按 `range(count)` 循环

Problem: 数字键无上限地累加进 `count_str`（`:616`、`:880`），`x` / `p` / `P`
（`:1000` / `:1007` / `:1014`）、重复查找（`:991`）和各类 motion（`:1506`）都按
`for _ in range(count)` 逐次调用 buffer API：`x` 到行尾后空转、`p` 真的粘贴 N 次，均不按
边界截断。按住数字键自动重复出十余位再按操作符，即得到 10^10 量级的 UI 线程循环，不可中断，
只能杀进程；vim 对超大 count 按缓冲区边界即时返回。附带：数字串超过 4300 位时 `int()` 抛
`ValueError`（解释器上限，仅理论触发面）。
Fix: count 取上限，并对可按边界截断的操作（`x` 到行尾、motion 到文件边界）直接算终点；
补「`999999999999x` 即时返回」用例。

#### [MAJOR] `../../tools/release/cli.py:303-329,436` — 发布回滚只对 `RuntimeError` 生效

Problem: 发布流水线先 bump 并提交版本文件，再生成并提交 changelog，然后才是只读门禁、
版本测试、打 tag、推送。外层只 `except RuntimeError` 触发回滚（`:332-363`）。changelog 写盘
抛 `OSError`、`subprocess.run` 起不来、操作者 Ctrl+C（`KeyboardInterrupt`）都不是
`RuntimeError`：带着已 bump 并提交的版本文件直接穿出，回滚不执行——而回滚是该工具的核心承诺。
Fix: `except (RuntimeError, OSError, KeyboardInterrupt)` 统一进入回滚后原样 `raise`；
补「changelog 写盘失败触发回滚」用例。

#### [MAJOR·设计裁决项] `../../yate/editor.py:806`、`../../yate/registries.py:83`、`../../yate/keymaps/base.py:196-197` — 命令 / 动作 / 键位分派无异常边界

Problem: 三处分派点都直接调用处理器（`entry.func(args)`、`action.func(ctx)`、`action(ctx)`，
最后者是扩展经 `add_binding` 注册的直调可调用对象）。全仓没有 `App._handle_exception` 覆盖
或等价兜底（`app.py` 只有 `:114`、`:126` 两处启动期 `except`），也没有 autosave / 崩溃后
恢复机制。用本仓库锁定的 Textual 做最小探针：动作处理器抛 `RuntimeError` 后异常穿出
`run_test()`，应用以 Traceback 终止。即任一处理器（含第三方扩展注册的处理器）的未预期异常
都会结束整个编辑器会话，未保存内容随之丢失。
Fix（需产品裁决是否采纳）: 在三处分派点加统一边界——`log.exception` + 面向用户的错误消息
（不违背「不静默」）；或显式裁决「处理器异常即崩溃」并把该决定写入 architecture-boundaries。

### MINOR — 影响面窄的边界缺陷

#### [MINOR] `../../yate/yaterc_options.py:190-201` — 分母 `int()` 在 `try` 之外（#77 同类修复的残留）

Problem: `denominator.strip().lstrip("-").isdecimal()` 放行 `"--5"`，而
`bottom = int(denominator)`（`:193`）在 `:195` 的 `try` 之外。端到端实测：
`screen_saver = {"dist_lower_bound": "1/--5"}` → `config.errors` 只有一条
`"ValueError: invalid literal for int() with base 10: '--5'"`（对照：`"--5/8"`、`"abc"`
都得到带选项名与示例的提示）；异常冒到 `../../yate/yaterc.py:213-216` 中断
`_extract_options`，其后的 `_extract_file_preview` / `_extract_large_file` 被静默跳过。
[2026-11-20](2026-11-20-full-repo-review.md) D2 条目描述的正是这一后果，当时只修了分子分支。
Fix: 把 `int(denominator)` 移入同一个 `try`；补 `"1/--5"` 用例断言文案与后续选项仍被提取。

#### [MINOR] LSP / 服务层失败无日志群（D10）

- `../../yate/editor_lsp/manager.py:666`：`request_completion` 对 `LspError` / `OSError`
  直接 `return []`；`../../yate/editor_lsp/sync.py:148-149`：didChange 失败直接 `return`。
  请求超时或连接失败后补全与增量同步静默降级，`client.py` 只有读循环意外崩溃有日志
  （`:504`），`LspError` / 连接断开路径（`:499-500`）只让 future 失败、不留记录。
- `../../yate/editor_lsp/client.py:296`：服务器进程 `stderr=DEVNULL`，启动失败的原因
  （缺 node、模块不存在等）无处可查。
- `../../yate/services/trust.py:92-93`：读信任存储遇 `OSError` 静默返回空集——失败关闭，
  但用户不知道为何 `:trust` 过的工作区又不再受信。
- `../../yate/services/extensions/api.py:130-133`：Lua 表 `__len` 抛错静默降级为 `[]`，
  扩展作者得不到反馈。

Fix: 各加一条 `log.warning`（带 uri / 选项名 / 路径）；服务器 stderr 改接 trace 日志。

#### [MINOR] `../../yate/editor_lsp/client.py:563-564` — `workspace/configuration` 响应长度不随请求

Problem: 处理器不读 `params.items`，恒回 `[settings]`；LSP 规定响应数组长度必须与请求项数
一致。一次请求多项的服务器会拿到错位或缺失的配置。
Fix: 按 `params.items` 逐项回填，补多项请求用例。

#### [MINOR] `../../yate/editor_lsp/sync.py:95-105` — 持锁者在文档重开时把仍在被引用的锁从锁表摘除

Problem: `dispatch_change` 末尾 `if open_docs.get(uri) is not state: change_locks.pop(uri)`。
didChange 在途期间该文档被关闭又重开时，已拿到同一把锁、正在排队的工作协程不受影响；但此后
新到的协程 `change_locks.get(uri)` 得 `None`，会新建另一把锁，与前者并发发送同一 uri 的
didChange，`state.version` 可能被分配两次。窗口极窄（需在单次 notify 的 await 内完成关闭、
重开并再有两次编辑），但属 review R3 N5 引入的逻辑洞。
Fix: 仅在锁空闲且无等待者时摘除，或把锁对象挂到 `OpenDocState` 上随其生命周期走。

#### [MINOR] `../../yate/editor_lsp/navigation.py:540-544` — signature help 高亮的是首个同名子串而非 `start:end`

Problem: `marker = label[start:end]` 之后
`return label.replace(marker, f"**{marker}**", 1)`，替换的是 `marker` 在整串中的**首次**
出现。参数名或标点在 label 更靠前处已出现时加粗落错位置（如 `f(a, a)` 高亮第二个 `a`）。
Fix: `label[:start] + f"**{marker}**" + label[end:]`。

#### [MINOR] `../../yate/editor_lsp/manager.py:80,1096-1102` — 诊断行索引按 span 逐行展开，上限 1000 行 / 条

Problem: span < `_ROW_INDEX_SPAN_MAX`（1000）的诊断被 append 到区间内每一行，发布成本
O(Σ span)；k 条近千行的诊断即约 10^6 个条目，整文件级诊断每条展开成文件行数条。标准替代是
按 start / end 排序后 bisect 的区间索引：发布 O(k log k)，查询 O(log k + m)，m 为命中数。
Fix: 区间索引替换逐行展开；或在规则里登记该上界的取舍。

#### [MINOR] `../../yate/editor_components/manual.py:552-559` — resize 重渲染去抖不合并

Problem: `_schedule_rerender` 每次 resize 都新起一个 timer，不保存也不取消上一个；同文件的
`_schedule_search`（`:674-679`）是先取消旧 timer 的写法。拖动窗口期间每个 resize 事件各排
一次全文重渲染，docstring 所称「resize 稳定后渲染一次」并未兑现。
Fix: 保存 timer 句柄并在重排前取消，与 `_schedule_search` 对齐。

#### [MINOR] `../../yate/logs.py:364-375` — `install()` 失败路径不告警，与模块 docstring 冲突

Problem: 模块 docstring `:39-40` 承诺「不可写目录会在 stderr 打印一条 warning 且编辑器照常
启动」；实现里 `except (OSError, ValueError)` 只关句柄、把 faulthandler 切到 stderr 后
`return`，没有任何输出，崩溃报告被静默禁用。
Fix: 失败分支补一条 stderr warning，或修正 docstring。

#### [MINOR] `../../yate/actions.py:90-98`、`../../yate/editor_core/commenting.py:77` — toggle 注释每次三遍全表拷贝 / 比较

Problem: `before = list(buf.lines)` 全量拷贝，`comment_range` 内 `result = list(lines)` 再拷贝
一次，最后 `after == before` 整表比较；而判定与改写只依赖选区行。成本与文档行数成正比。
非每击键路径，故为 MINOR。
Fix: 只拷贝、比较选区行。

#### [MINOR] `../../tools/lint_lua.py:57,66-69` — Lua lint 一处误报、一处漏报

Problem: banned-call 用 `\bprint\s*\(` 直接扫源码，字符串字面量里的 `print(` 也命中（实测
`local msg = "call print(1) here"` 报 `banned-call`）；global-leak 用
`^([A-Za-z_]\w*)\s*=` 只匹配顶格赋值，缩进块内的全局泄漏漏检（实测
`if true then⏎  leak = 1⏎end` 零 issue，顶格同句命中）。
Fix: 扫描前屏蔽字符串字面量；行首放宽到缩进并排除已 `local` 的名字。

#### [MINOR] `../../tools/changelog/render.py:124-133` — `split_sections` 对重复 heading 静默取后者

Problem: `sections[heading] = ...` 直接覆盖。实测磁盘文档含两个 `## [1.0.0]`（前者被手改）时，
`released_sections_diff` 对完好的生成稿返回 `[]`，`check` 放行一份已漂移的文件。
Fix: 重复 heading 直接报错，或全部保留后逐段比对。

#### [MINOR] `../../tools/smoke_test/harness.py:112-119,591-615` — `--seed` 不传入 spawn 出来的工作进程

Problem: `set_seed` 只改父进程的模块级 `_seed`；`run_shard` 没有 seed 形参，
`ProcessPoolExecutor`（spawn）里的工作进程一律用默认值 1337。`run --jobs 4 --seed N` 时 fuzz
场景实际按 1337 跑，报告头（`cli.py:237`）却打印请求的 seed，复现指引失真。默认 `--jobs 1`
不受影响。
Fix: `run_shard` 增 `seed` 形参并在函数体首行 `set_seed(seed)`。

#### [MINOR] `../../tools/smoke_test/harness.py:395-397,510` — 不变量扫描只覆盖场景创建的最后一个 App

Problem: `current_app()` 返回 `_apps[-1]`，`_run_one` 只对它跑 `invariant_checks`；一个场景内
`new_app` / `track` 过多个 App 时，先前 App 的残留（未关弹层、未取消 worker 等）不在扫描
范围。主题漂移因为是进程全局量仍会被末位 App 捕获，其余不变量不受此惠。
Fix: 对 `_apps` 全体逐个跑不变量。

#### [MINOR] `../../tools/pack/zip_dist.py:259-260,266-275` — 回滚失败静默，且 `finally` 仍删掉旧包备份

Problem: `:259-260` 的 `except OSError: pass` 把回滚失败吞掉，`backup` 未置空，随后 `finally`
（`:266-269`）照样把它 `unlink`。双故障路径下旧包备份消失，归档位置留着新包而 sums 未更新，
用户只看到 sums 写入失败。`:270-271`、`:274-275` 两处清理也是无输出的 `pass`。
Fix: 回滚失败时向 stderr 说明备份仍在并跳过删除；清理失败打一行提示。

#### [MINOR] `../../tools/translate/cli.py:191-194` — 临时文件写入不在 `try` 内

Problem: `temp_path.write_text(...)` 在任何 `except OSError` 之外，失败会以裸 Traceback 穿出
`main()`（那里只处理 `KeyboardInterrupt`），违背模块对「失败一律带 `wiki-translate:` 前缀
报错」的承诺。
Fix: 并入下方的 `except OSError`。

#### [MINOR] `../../tools/pack/icon.py:73` — 已跟踪文件 `pack/yate.ico` 被原地覆盖

Problem: `square(image).save(target, ...)` 直接写目标，中途失败会留下截断的图标文件；同包
`zip_dist.py` 已普遍采用临时文件 + `os.replace`。
Fix: 写临时文件后 `os.replace`。

#### [MINOR] `../../tools/mdlint/fences.py:25` — 围栏正则接受任意缩进

Problem: 围栏正则以 `^[ \t]*` 起头，把缩进 ≥4 空格的行也当作围栏起点，而 CommonMark 规定
那是缩进代码块。文档用缩进代码块展示围栏示例时，跟踪器从此处错位，后续规则漏检。
Fix: 缩进限制为 ≤3 空格。

#### [MINOR] `../../tools/pack/wiki/publish.py:310-316` — 用英文输出文本判断「无变更」

Problem: `run_git` 不固定 locale，非英文环境下 git 输出被本地化，`"nothing to commit"` 匹配
不到，干净工作区会被报成 commit 失败。
Fix: 改用 `git status --porcelain` 或退出码判定。

#### [MINOR] `../../tools/probes/pb6_real_input_harness.py:193-204,352` — 查询失败被当成「进程已退出」

Problem: `marker_process_count()` 把空 stdout 记作 0 且不检查 `returncode`；PowerShell / CIM
查询失败时 `:352` 得 `app_exited = True`，"app exited on ctrl+q" 假 PASS。
Fix: `returncode != 0` 或 stdout 为空时返回 `-1`。

#### [MINOR] `../../tools/probes/win32im_probe.py:63` — 交互探针在模块顶层调用 `main()`

Problem: 没有 `__main__` 守卫，任何误 import（IDE 索引、`python -c` 补全）都会进入无限循环
并改写当前终端的输入模式。
Fix: 加 `if __name__ == "__main__":` 守卫。

#### [MINOR] `../../tools/screenshots/driver.py:202-206` — 子进程调用无 `timeout`，且在 `wait_for` 之外

Problem: `subprocess.run([sys.executable, "-m", "fontTools.subset", ...])` 没有 `timeout=`；
`../../tools/screenshots/__main__.py:114-115` 是在 `asyncio.wait_for` 块结束后才调用
`scrub_svg` / `embed_icon_font`，字体子进程一旦挂起，截图工具无限期卡住。
Fix: 加 `timeout=` 并纳入 `wait_for`。

### MINOR — 测试与文档

#### [MINOR] `../../tests/test_theme_reset_fixture.py:17-25` — 钉住用例在并行下可能空过

Problem: 文件内两个用例的配对依赖同一 worker 顺序执行（docstring 自述「separate workers both
pass trivially」）；门禁用 `-n auto`，xdist 默认 `--dist load` 不保证同 worker。
Fix: 合并为单个用例，或直接调用夹具函数验证复位。

#### [MINOR] `../../tests/test_lsp_real_server.py:30-33,130-134,264` — 服务器「起不来」与「未安装」同为 skip

Problem: `pyright-langserver` 不在 PATH 时收集期 skip 合理；但二进制存在、启动超时或握手
失败时也 `pytest.skip`，握手回归在装有该二进制的机器上不会判红。
Fix: 仅「未安装」skip，启动失败改 fail。

#### [MINOR] 测试覆盖缺口（D11，全量 `pytest --cov` 实测）

- `../../yate/editor_components/explorer.py` 81%：`submit_create` / `submit_rename` /
  `submit_delete` 的错误分支（`:482,485-493,505,508-516,526,532-534`，非法名 / 已存在 /
  `OSError`）无单测；成功路径由单测与冒烟 `tools/smoke_test/scenarios/explorer.py:88-139` 覆盖。
- `../../yate/keyproto/driver_windows.py` 26%：`run()` 主循环（`:122-246`）与
  `start_application_mode`（`:272-301`）无自动化覆盖，只有
  `tests/test_keyproto.py:374-377` 的源码文本钉；真机行为依赖人工 harness（已登记 #10）。

Fix: 错误分支各补一条消息断言用例；`run()` 的帧分发抽出纯函数后单测。

#### [MINOR] `tests/` 行宽超限 4 处

`../../tests/conftest.py:160`（122 字符）、`test_architecture.py:355`（101）、
`test_lua_lint.py:141`（107）、`test_pack_zip.py:253`（101）；规则上限 100。
Fix: 折行。

#### [MINOR] `../../tools/smoke_test/testsuite.py:30-31` — 文档 tag 列表漏项

Problem: 相对 `tools/smoke_test/harness.py:94-108` 的 `TAGS`，模块 docstring 漏列 `hover` 与
`lsp-navigation`。Fix: 同步。

#### [MINOR] 规则 / 技能 / agent 文档漂移群（D12）

- `editor_view` 旧包名 14 处 / 5 文件：`../skills/multi-dim-review/SKILL.md:116,140,141,148,164,381`、
  `../skills/pr-review/SKILL.md:84`、`../skills/textual-pilot-smoke/SKILL.md:25`、
  `../agents/code-review-expert.md:57`、`../rules/python-coding-style.md:37,59,70,76,77`。
- pyright 门禁命令漏 `pack/` 5 处：`../skills/multi-dim-review/SKILL.md:287`、
  `../skills/pr-review/SKILL.md:97`、`../skills/textual-pilot-smoke/SKILL.md:174`、
  `../agents/code-review-expert.md:74`、`../rules/architecture-boundaries.md:530`。
- 基线分支写作 `main` 3 处：`../skills/multi-dim-review/SKILL.md:252`、
  `../skills/pr-review/SKILL.md:25-26`（本项目为 `master`）。
- 架构规则范围仍写 R1–R13：`../agents/code-review-expert.md:57`、`coder.md:16`、
  `plan-architect-designer.md:32,46`（现为 R1–R15）。
- `../../yate/docs/lsp` 双语标题数 en=25 / zh=24。
- 技能 D9 写「ASCII only」，而守卫与规则文本的范围是「CJK + 全角标点 + § / °」。全仓扫描
  注释 / docstring 内非 ASCII 码点共 85 种 / 184 处：真实落在注释或 docstring 的 CJK 与 `§`
  恰 6 处（等于 `NON_ASCII_COMMENT_EXEMPT` 冻结集），其余约 120 处是 em dash（28）、
  箭头（20）、省略号（11）、图标与制表字形等，都在守卫范围之外。

Fix: 同步措辞；D9 与守卫范围二选一对齐。

## 三、Suspects

- `[SUSPECT] ../../tools/pack/wiki/lint.py:100` — `@functools.cache` 且单文档 lint 无独立
  时间预算；是否需要按真实文档规模设预算，与 #31 R-09 / R-10 / R-13 的登记相邻，未实测。
- `[SUSPECT] ../../yate/logs.py:220-285` — trace 日志每次会话落一个新文件
  （`yate-YYYYMMDD-HHMMSS.log`），全仓无保留 / 轮转策略；是否成问题取决于长期使用后的目录
  体积，未实测。
- `[SUSPECT] ../../yate/editor_components/palette.py:283-298` — `refilter` 每键全量评分 +
  全排序后截断；#41 已登记相邻项，是否改 top-k 需候选规模分布数据。
- `[SUSPECT] ../../yate/flows/whichkey_flows.py:95-124`（审查员线索，未逐行回读）—
  `refresh` 每键一次且含 `_sheet_entries` 全表。
- `[SUSPECT] ../../yate/editor_components/commandline.py:128-180,214-228`（审查员线索，未逐行
  回读）— 补全候选与历史列表无上界。
- `[SUSPECT] ../../yate/editor_components/terminal.py:251-258`（审查员线索，未逐行回读）—
  `_wait_for_size` 以 20 ms 真实睡眠轮询，超时静默回落 80x24。
- `[SUSPECT] ../../yate/editor_syntax/ts_backend/languages.py:58` —
  `except (ValueError, IndexError): return None`（语言解析失败静默）；审查员把文件误记为
  `editor_lsp/languages.py`，本条未逐行回读，保留线索。

## 四、Suggestions / Deferred

- `[SUGGESTION]` 冒烟场景中 26 处裸 `assert`（11 个文件）在 `python -O` 下被剥离；改 `Check`
  或显式 `raise`（先例 #23）。
- `[SUGGESTION]` 产品代码 12 处裸 `assert`（`editor_core/buffer.py` ×6、`editor_components/panes.py`
  ×2、`editor_lsp/manager.py`   ×2、`editor_lsp/diff.py`、`editor_syntax/regex_backend.py`）同属 #23 类，
  维持登记。
- `[SUGGESTION]` `tests/test_macro_wiring.py:187-195` 嵌套 pyright 子进程（依赖 PATH 上的
  node）；先例 #71 已把同类嵌套 pytest 改为进程内守卫，可考虑移到独立门禁步骤。
  `tests/test_architecture.py:988-990` 的规则表锚点含日期字面量，改规则日期时需同步。
- `[SUGGESTION]` `tests/test_architecture.py:1200,1218-1226` 两处样式守卫是文本匹配
  （`.styles.background =` 单空格等），别名或双空格写法可绕过；作为误改回归钉足够，要防绕过
  需 AST。
- `[SUGGESTION]` `tests/test_lsp_navigation.py:394` 以 `_uri()` 自身作 oracle 的镜像断言；
  换成字面量期望值更强。
- `[SUGGESTION]` `tools/screenshots/__main__.py:143-158` gallery 以 `exists()` 取图：场景失败时
  其 SVG（或上次运行的旧图）仍进画廊；与 #55 的子集渲染语义绑定，失败分支可改为跳过。
- `[SUGGESTION]` `tools/screenshots/driver.py:104-124` `scrub_text` 不覆盖主机名 / 时区 /
  裸盘符路径；已提交截图在 #55 第二轮全量扫描归零，属加固项。
- `[SUGGESTION]` `tools/screenshots/cli_reports.py:75` `subprocess.run` 后不检查 `returncode`；
  `tools/screenshots/scenarios.py:466-467` which-key 帧前固定 `pause(1.5)`（截图工具，非断言）。
- `[SUGGESTION]` `tools/changelog/classify.py`：非 git 默认格式的 `revert: feat(x): y` 被归入
  Other 且摘要只剩内层标题；`tools/changelog/gitee.py:139-147` 降级时打印一条提示更稳妥。
- `[SUGGESTION]` `tools/lint_lua.py:184-188`：CRLF 文件每行另报一条 trailing-space（`\r` 被
  `rstrip` 命中），输出噪声。
- `[SUGGESTION]` `tools/mdlint/cli.py:270`：`dict.fromkeys` 去重前未 `resolve()`；
  `tools/pack/wiki/publish.py:144-150` 与 `:151-156` 对 manifest「损坏」与「不可读」的处置口径
  相反（前者报告后重置，后者中止），可统一。
- `[SUGGESTION]` `tools/probes/pb6_real_input_harness.py:258-259`：`mkdtemp` 目录不清理；
  `tools/pack/rosters.py:100`：`rosters.svg` 非原子写；`tools/pack/wiki/sources.py:211`：错误
  只报 basename。
- `[SUGGESTION]` `tools/pack/wiki/translate.py:303,660` 与 `tools/mdlint/batch.py:151,248` 的
  `except BaseException:` 未带理由注记。
- `[SUGGESTION]` `yate/keymaps/vsc.py:153-155` 分组字面量 `"NAV"` 改命名常量；
  `yate/yaterc_options.py:307-311` 成对校验文案在「一者非法」时误导；`yate/config.py:322-326`
  使 `shell = ""` 无法表达。
- `[SUGGESTION]` `yate/editor_components/marks_palette.py:174-180` `action_jump` 用 try/finally
  保证 `dismiss`；`file_manager/model.py:173` `count_children` 的 `-1` 哨兵加日志。
- `[SUGGESTION]` `yate/commands.py:480-502` `:theme` / `:filetype` 未走 `_strip_quotes`
  （同类先例见 #52）。
- `[SUGGESTION]` `yate/editor_components/completion.py:42,255-270` 与
  `yate/flows/completion_flows.py:38-46` 对「标识符前缀」各有一份定义（后者 docstring 称其为
  唯一定义）；抽到一处复用，或修正 docstring 说明分工。
- `[SUGGESTION]` `yate/editor_lsp/manager.py:1042-1062`：`window/showMessage` 等通知已确认
  但未上屏（注释自述 not surfaced yet）。
- `[SUGGESTION]` 5 个 >180 行的函数维持观察：`yate/keymaps/vim.py:847`（291）、`:583`（200）、
  `yate/cli.py:349`（233）、`yate/editor_components/view.py:527`（196）、
  `yate/editor_compose.py:230`（185）。
- `[SUGGESTION]` `yate/yaterc.py:110-112` docstring 称两份 rc 都 `resolve()`，项目 rc 实际
  以未解析路径入表（`:121-129`）；`is_trusted` 内部会解析，故只影响去重口径。
- `[DEFERRED]` 修复范围与排期：待用户批准后另出 `full-repo-review-fixes-plan.md`。

## 五、已登记项现状复核

- **#33 O-1 / O-2**：`tools/pack/wiki/translate.py:211-231` 的 `_terminate` 仍只对直接子进程
  `proc.kill()`（`shell=True` 下即 shell），孙进程不在终止范围。与登记一致，维持另案；
  本轮审查员的同址候选并入账，不重提。
- **#77（11-20）**：`diagnostic_at` 已改用行索引（`yate/editor_lsp/manager.py:1126-1163`），
  未见回归；**yaterc 分数条目有残留**（分母分支，见 MINOR 首条）。
- **#23**：产品代码裸 `assert` 12 处仍在，未出现 `-O` 运行面。
- **#68 m-1 / #71**：冒烟并行负载敏感与嵌套子进程先例仍在；本轮
  `tools/smoke_test/scenarios/file_manager.py:113-118` 的 10 轮退出等待属同类且后随
  `return_code_zero` 检查，不重提。
- **#55 / #56**：画廊按 `exists()` 取子集的设计未见回归。
- **#41**：`palette.refilter` 现状不变（见 Suspects）。
- **#11 / #14 / #31 R-09·R-10·R-13**：明确不修项，未发现需要重开的新证据。

## 六、豁免账本（被登记集合吸收，不计 finding）

- `yate/editor_syntax/regex_backend.py:105` `@lru_cache(maxsize=None)`：键为模式串的编译缓存，
  与 #41 M1 同类（信息级）。
- `SIZE_EXEMPT_FILES` 7 文件：`len(...) == 7` 被冻结，规则表行数另有守卫；其余登记豁免集合
  的命中项按定级规则视为合规。
- `yate/editor_components/modals.py:89` 帮助页里的 em dash 属展示字符串，不在注释守卫范围。
- 工作区主题信任门以 resolved cwd 解析工作区根：arch-sec-audit 已定口径，未见回归。
- `yate/services/trust.py:114-131` 拒绝含符号链接分量的工作区根（S39）：设计在位。
- `yate/editor_sprites/**`、`yate/editor_syntax/langdefs.py` 的纯数据表：数据契约 clean。

## 七、审查员候选撤回（反证）

1. 「`_abort_with_rollback` 的 `version` 是死参」：`tools/release/cli.py:355,361` 的回滚指令与
   提示都用 `v{version}` → 删除。
2. 「zip 符号链接硬编码 `0o777` 把 `0o644` 的链接变成 `0o777`」（`zip_dist.py:137`）：POSIX
   符号链接自身的模式位本就无意义（Linux 恒为 `lrwxrwxrwx`），按目标文件模式写才是错的 →
   删除。
3. 「zip 成员无 casefold 去重」（`zip_dist.py:176`）：所引证据行是校验和比对，与论点无关 →
   不计。
4. 「`_force_utf8_pipes` 漏 stderr 会抛 `UnicodeEncodeError`」（`tools/translate/cli.py:154-162`）：
   `sys.stderr` 默认 `backslashreplace`，不会抛 → 不计。
5. 「bundle 日期取当天致跨天 `check` 误判」：把 bundle 头部日期改成 `1999-01-01` 后
   `released_sections_diff` 返回 `[]`、`unreleased_lag` 为 0；`split_sections` docstring
   （`tools/changelog/render.py:116-117`）明示首个二级标题之前的文件头不参与比对 → 删除。
6. 「`gitee.pushed_flags` 首个网络错误即停」：docstring 明确记录该降级设计 → 降 SUGGESTION。
7. 「revert 提交被误归类」：git 默认格式 `Revert "feat(x): add y"` 实测归 Other 且摘要完整
   保留 → 降 SUGGESTION。
8. 「`mdlint/lint.py` 导入期改第三方 logger」（`:25-26`）：`:20-24` 注释登记了理由，模块每进程
   只导入一次 → 删除。
9. 「`win32im_probe` 无总超时」：交互式探针按设计由操作者退出 → 删除。
10. 「冒烟 `file_manager.py:113-118` 的 10 轮等待 + `suppress(Exception)` 可致假通过」：
    `Check("q_exits_app", …, exited)` 如实记录，紧随的 `Check("return_code_zero", …)`
    （`:120`）兜住崩溃退出 → 删除。
11. 「`report.py:371` 零检查报 100%」：仅当整轮检查总数为 0 时可达（现为 1554）→ 删除。
12. 「yxp manifest casefold 去重不归一化点段」（`manifest.py:279-289`）：
    `PurePosixPath(...).parts` 已折叠 `.` 与空段（实测），`..` 在 `_check_member_name`
    （`:231-235`）被拒 → 删除。
13. 「`trust.py:17-18` 与 `:69-73` 文档与实现冲突」：前者说的是**存储文件**是不是符号链接
    （由 `:84` / `:122` 的 `store.is_symlink()` 判定，父目录不受影响），
    `_has_symlink_component` 只用于**被信任的工作区根**（`:125`），与 `:114-119` 一致 → 删除。
14. 「信任存储读入不展开 `~`」（`trust.py:98`）：契约是每行一个已解析的绝对路径
    （`:79-81`）→ 删除。
15. 「`palette._index_files` 吞 `OSError` 无日志」：`yate/editor_components/palette.py:260-262`
    有 `log.warning`；`:201-203` 的 `except ValueError` 是仓库外文件的显示名回退 → 删除。
16. 「explorer 建改删失败路径无反馈」：`yate/editor_components/explorer.py:485-532` 各分支均有
    `self.prompt.write(..., kind="error")` → 删除（覆盖缺口另见 MINOR）。
17. 「`driver_windows.py:274` 启用应用模式后异常不恢复终端」：锁定的 Textual 在 shutdown
    序列里统一调用 `driver.stop_application_mode()`，覆写实现写完复位序列后转交基类 → 删除。
18. 「架构守卫豁免集合可被悄悄扩充」（`tests/test_architecture.py:955-960`）：`:1969` 冻结
    `len(SIZE_EXEMPT_FILES) == 7`，规则表另有守卫，任何扩充都在 diff 中可见 → 删除。
19. 「explorer 新建 / 重命名零覆盖」：成功路径由单测与冒烟 `explorer.py:88-139` 覆盖，全量
    实测 81%，缺口仅错误分支 → 改记 MINOR。
20. 「`conftest.py:41` 导入期写环境变量」：`:37-40` 注释登记了「进程级、只在 conftest 导入时
    设一次」的设计 → 删除。
21. 「`panes.py:267` 行宽 103」：实测 93；产品与工具代码（不含冒烟场景）无 >100 行 → 删除。
22. 「冒烟 `hover.py` 的 `rows` 可能未赋值」：`rows` 在恒执行的 phase 1 末尾赋值
    （`tools/smoke_test/scenarios/hover.py:153`）→ 删除。
23. 「`delete_lines` 不递增 `content_version`」：`yate/editor_core/buffer.py:435-455` 的
    `_record` 在权重非零时递增 → 删除。
24. 「`_render_parent` 绕过 `_dir_cache`」：`explorer.py` 中检索不到这两个符号，无法核对 →
    删除。

另：wave-1 审查员所报七处纯窄化 `assert`、registries 回滚、Document identity、`~` 展开、
`is_open`、`open_async` TOCTOU、组装顺序等候选，回读后均被调用方保证或登记集合吸收。

## 八、门禁实测（主代理亲跑，2026-11-26 06:40–07:10，基线 `b97a695c`）

| 命令 | 结果 | 退出码 |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors | 0 |
| `pytest tests/ -q -n auto` | 4062 收集 · 0 failed · 10 skipped | 0 |
| `pytest tests/test_architecture.py -q` | 47 passed | 0 |
| `pytest tests/ --cov=yate --cov-branch -n auto` | 覆盖率 92.76%（4052 passed · 10 skipped），阈值 75 | 0 |
| `tools.smoke_test run --jobs 4` | 128/128 场景 · 1554/1554 检查（93.87 s） | 0 |
| `tools.changelog check` | released 段一致 | 0 |

复核期另跑一次全量 `pytest --cov`（仅统计 explorer / driver_windows / completion 三模块，
全新 basetemp）exit 0，数字见「测试覆盖缺口」条。首次尝试在 100% 跑完后被本机 safe-delete
钩子在收尾清理阶段杀掉（环境伪影，非测试失败），换全新 basetemp 后通过。

## 九、未覆盖清单（如实）

- 12 个分区审查员各自的「未通读文件清单」未并入本记录。冒烟框架的 28 个场景文件只抽审
  约 45%，其余 13 个仅由主代理做机械统计（裸 `assert` / 睡眠 / `except Exception` 计数）。
- `tests/` 按计划只做模式扫描 + 重点抽审（`conftest.py`、`test_architecture.py` 与
  `test_theme_reset_fixture.py`、`test_lsp_real_server.py`、`test_keyproto.py` 等）；其余测试
  文件未逐行审。
- 主代理对全部 MAJOR 候选与 wave-2/3/4 的 MINOR 候选所在位置做了定点回读与探针；
  wave-1/2 的其余约 25 条 MINOR / SUSPECT 级审查员线索未逐条回读，已在上文标注。
- 未做真实 GUI 验证、性能 profiler 实测、Linux / macOS 平台行为验证。
- 子代理产出：规划角色两次 spawn 均模型未注册，方案由主代理代笔；首个 P-B1 审查员因通读
  长文档被上下文压缩零交付，改用最小读取清单后重试交付。

## 十、Strengths

- 增量最重的 LSP 增量同步 / 诊断发布路径设计扎实：`dispatch_change` 在锁内分配版本号、
  notify 成功后才推进状态；诊断行索引对超长 span 有 overflow 兜底。
- 三处信任门控与 yxp 成员名校验在位，未见回归。
- 构建 / 发布工具普遍有临时文件 + `os.replace`、锁文件、备份回滚的纪律；M5 与 zip 回滚那条
  是该纪律的例外而非普遍现象。
- 机械体检干净：产品与工具代码无 >100 字符行、无裸 `except:`、无可变默认参数；pyright
  strict 四路径 0 诊断。
- 12 个分区中 5 个（P-B2 / P-D / P-E / P-G2 / P-G3）以及主代理自审的规则 / 技能 / agent 区
  没有 MAJOR 级发现。
