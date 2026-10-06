# pack wiki 进度刷新 + Ctrl+C 治理：skill 审查记录（2026-10-06）

> **本文是只读事实文档**：只记录发现与核对结论（含实测证据），不含修复排期。
> 修复方案见
> [pack-wiki-progress-refresh-plan.md](../documents/pack-wiki-progress-refresh-plan.md)
> §6.8–§6.11；本轮 issues 的跟踪状态见
> [legacy-issues.md](legacy-issues.md)（销账依据落在本文与该方案）。

- **对象**：分支 `fix/pack-wiki-progress-refresh`（worktree `../yate-pack-wiki-progress`），
  issue **IKJPEK** 的两条用户反馈驱动的修复
- **触发**：
  1. issue 评论 [`note_51450440`](https://gitee.com/jermaine/yate/issues/IKJPEK#note_51450440)
     （2026-10-05 22:42:11 +08:00）：「每个batch的任务进度不会实时更新进度，只有0到100，
     需要实时刷新进度」；
  2. 用户报告（2026-10-06）：按 `Ctrl+C` 后 `KeyboardInterrupt` 堆栈刷屏。
- **审查方式**：`python-code-review` skill 六维度 + 三级严重度，配合变异测试与
  一次性探针；共 6 轮（第 1、2 轮主代理，第 3、4 轮只读评审子代理，第 5 轮主代理
  复审未提交改动，第 6 轮确认性复核）。
- **skill 缺口**：本轮创建过项目级 skill 的机器本地副本——此前
  `code-review-expert` 剧本要求的 `python-code-review` skill 在仓库与用户目录均不存在
  （第 1 轮评审实测加载失败）。该副本已删除，`.trae/skills/` 下的 skill
  **未作任何改动**（用户明确要求），现由 master 提供的跟踪版承担。

## 一、结论概览

| 轮次 | 结论 | 处置 |
|---|---|---|
| 第 1 轮（主代理） | 0 CRITICAL / 7 WARNING / 3 SUGGESTION | R-01…R-08 已修；R-09/R-10 接受为风险并附理由 |
| 第 2 轮（主代理） | 1 SUGGESTION + 1 权衡 | R-12 已修（死成员）；R-13 接受并文档化 |
| 第 3 轮（只读评审子代理） | 0 CRITICAL / 5 WARNING / 2 SUGGESTION | R-14…R-18 已修；R-19/R-20 文档修正 |
| 第 4 轮（只读评审子代理，确认性） | 0 CRITICAL / 1 WARNING / 6 SUGGESTION | R-21（四轮皆遗漏的结构性缺陷）已修并加 AST 守护；R-22…R-27 已修；**代码收敛** |
| 第 5 轮（主代理，复审未提交改动） | 0 CRITICAL / 2 WARNING / 2 SUGGESTION | R-28（取消信号归属）已修；R-29（stdin 竞态 + 未验证的 WIP）已修；R-30 已修；R-31 接受并补文档 |
| 第 6 轮（主代理，确认性复核） | 0 CRITICAL / 0 WARNING / 1 SUGGESTION | R-32 已修（README 契约补编码）；无新增 |

> R-11（分支落后 master）不是代码缺陷，是流程风险，只登记在
> [legacy-issues.md](legacy-issues.md)，故不出现在上方编号表中。
> 累计：0 CRITICAL / **15 WARNING** / **16 SUGGESTION**（R-09/R-10/R-13/R-31 为接受项）。
>
> **编号口径**：第 1–4 轮沿用 R-01…R-27；第 5 轮起接续为 R-28…R-31
> （未提交草稿里曾把页写入竞态标成 "R-31"，本记录统一为 R-29，见 §五之二）。

无 CRITICAL。第 3 轮对前两轮修复做了等价性复核：`_translation_state()` 重构与重构前
**逐分支等价**（无 en 页 / stale / fresh / adopted × `--translate-all` 开关 × 有无
`--translate-cmd` 全组合核对）。

## 二、第 1 轮发现（本轮修复自身引入的缺陷优先）

| # | 级别 | 位置 | 问题 | 证据 | 状态 |
|---|---|---|---|---|---|
| R-01 | `[WARNING]` | `tools/pack/wiki.py` `_ProgressBoard.page_done` | 总体行文案落后进度条一页：`_description()` 作为**实参**在 `update(advance=1)` 之前求值 | 探针逐页采样 `(completed, 文案)`：`delta=1` 恒成立，仅批末 `batch_finished()` 追平 | ✅ 已修 |
| R-02 | `[WARNING]` | `tests/test_pack_wiki_parallel.py` | 中断链路无用例：原用例让 `translate_via_cmd` 直接抛异常，未覆盖"子进程以 `0xC000013A` 退出 → 父进程识别 → CLI 130"这条真实链路 | 读码：用户报告走的正是该路径 | ✅ 已修 |
| R-03 | `[WARNING]` | `tools/pack/wiki.py` `store_manifest` | manifest 写失败报 `WIKI_PAGE_WRITE`（WIKI-0106），`WIKI_MANIFEST_WRITE`（WIKI-0105）为死码 | 继承自 PR !56 P1（未处置项） | ✅ 已修 |
| R-04 | `[WARNING]` | `tools/pack/wiki.py` `_read_source_bytes` | 通用 `OSError`（权限/磁盘）被报成"源文件消失"（WIKI-0102），`WIKI_SOURCE_UNREADABLE`（WIKI-0103）为死码 | 继承自 PR !56 P2 | ✅ 已修 |
| R-05 | `[WARNING]` | `tools/pack/wiki.py` `_translate_pending.finally` | 收尾竞态：主线程清空失败列表后，仍存活的 worker ①消息丢失 ②模式恢复后裸写 stderr 交错 | 继承自 PR !56 P3 | ✅ 已修（第 3 轮补齐第二半，见 R-16） |
| R-06 | `[WARNING]` | `tools/pack/wiki.py` `needs_translation` / `_prepare_pages` | 判定逻辑两处各写一遍，规则可能漂移；且该函数已无生产调用方 | 继承自 PR !56 P4 | ✅ 已修（判定统一；调用面问题见 R-14） |
| R-07 | `[WARNING]` | `tools/pack/wiki.py` `_translate_pending` | 空 `plans` → `min(resolve_jobs(...), 0)` → `ThreadPoolExecutor(max_workers=0)` 抛 `ValueError` | 变异验证：移除卫语句后用例以 `ValueError` 失败 | ✅ 已修 |
| R-08 | `[SUGGESTION]` | 同上 | 同一对象两个名字（`_ProgressBoard.progress` vs 局部 `display`） | 读码 | ✅ 已修 |
| R-09 | `[SUGGESTION]` | `_run_batch` | 进度回调异常复用翻译失败通道（理论上会误报为翻译失败并中止整轮） | 键来源已单一，仅 rich 缺陷可达 | ⏸ 接受：新增独立告警通道属过度防御 |
| R-10 | `[SUGGESTION]` | `_emit_mode` 全局 | 理论不可重入 | 修法需改 `translate_via_cmd` 公开签名 | ⏸ 接受：CLI 每次进程单 run，不可达 |

## 三、第 2 轮发现（审查自己的重构）

| # | 级别 | 位置 | 问题 | 证据 | 状态 |
|---|---|---|---|---|---|
| R-12 | `[SUGGESTION]` | `_PageState` / `_translation_state` | 新加的 `COPIED` 成员与 `has_en_source` 参数无任何调用方传 `True`（预览先短路、rebuild 已在 `en_bytes` 分支处理）→ 死路径，且让人误以为"复制"仍在判定器里处理 | 全仓搜索调用点 | ✅ 已修（删成员与参数） |
| R-13 | `[SUGGESTION]` | `_INTERRUPT_EXIT_CODES` | 把 `130` 也读作"被中断"：自定义 `--translate-cmd` 若用 130 表示普通失败，会被误判为整轮中止 | 语义分析 | ⏸ 接受并文档化（POSIX 惯例与 `tools.translate` 返回值一致） |

## 四、第 3 轮发现（独立只读评审）

| # | 级别 | 位置 | 问题 | 证据 | 状态 |
|---|---|---|---|---|---|
| R-14 | `[WARNING]` | `needs_translation` | 生产零调用方（仅 14 处测试引用），而重构又为其新增哨兵常量 `_PREVIEW_TRANSLATE_HOOK`；R-06 的关闭描述会让人误以为生产在用 | `git grep` 确认改动前即无生产调用方 | ✅ 已修（docstring 如实标注调用面 + 登记） |
| R-15 | `[WARNING]` | `_translate_pending.finally` 注释 | 注释称"绝不阻塞中断路径"被实测证伪：CPython 在解释器 teardown 阶段 join 池线程，自定义 hook 吞掉 SIGINT 时退出仍会延迟（实测 0.6s → 3.1s，单页 3s） | 探针：主线程 0.58s 抛出、teardown 3.07s | ✅ 已修（注释改为实测事实；真要立即退出需 daemon worker/`os._exit`，超出本轮范围，登记为遗留） |
| R-16 | `[WARNING]` | `_translate_pending.finally` 顺序 | R-05 只修了一半：`_emit_mode = "print"` 在 drain **之后**，drain 后到达的消息进队列却无人再取 → 永久滞留丢失；恢复后的消息仍裸写 stderr 交错 | 探针：drain 后注入 emit → `residue after run: 1` | ✅ 已修（先恢复串行策略再 drain；变异验证用例变红） |
| R-17 | `[WARNING]` | `tests/test_pack_wiki_errors.py` | 原 `test_a_late_worker_failure_is_not_dropped` 恒真：只断言队列 API（put/qsize/drain），与"晚到消息能否到终端"无关；换回 list 也通过 | 变异：换回容器后仍绿 | ✅ 已修（改为在真实 drain 之后注入上报，断言 stderr 可见 + 队列为空） |
| R-18 | `[WARNING]` | `README.md` / `README.zh.md` / 方案 §6.3 | "重定向时只有逐批的行输出"与实测不符：`Live.stop()` 会渲染一次最终帧，非 TTY 下 stderr 仍有 4 行完整进度条（排在逐批行之后） | 主代理复核探针（重定向到文件）确认：`translating 25/25 … 100%` + 3 个批行 | ✅ 已修（中英 README 与方案改为"不实时刷新，结束时打印一次最终进度条"） |
| R-19 | `[SUGGESTION]` | 方案 §6.2 / §6.8 | 门禁计数过期（记 67/89，实测已 77/93；标题却写"审核轮最终态"） | 实测 | ✅ 已修 |
| R-20 | `[SUGGESTION]` | 方案 §6.9 | 行号引用 `wiki.py:837` 指向 R-01 修复**前**的位置，已失效 | 读码 | ✅ 已修（改为按函数引用） |

## 五、第 4 轮（确认性审查）：代码收敛，剩一条四轮皆遗漏的 WARNING

第 3 轮的 5 WARNING + 2 SUGGESTION 修复**全部属实且被变异锁定**（子代理逐条
反证：R-01/R-03/R-04/R-16/R-17 回退即变红），未引入新缺陷。四场景探针
（正常 / 全失败 / 中途 interrupt / worker 抛异常）终态全部自洽：`FAILPAGE`
行数 == 去重行数（恰好一次）、队列残留 0、`_emit_mode` 末值 `print`。

| # | 级别 | 位置 | 问题 | 证据 | 状态 |
|---|---|---|---|---|---|
| R-21 | `[WARNING]` | `tools/pack/wiki.py` `_translate_pending` | **四轮皆遗漏**：`global _emit_mode; _emit_mode = "collect"` 与 `progress.start()`、`ThreadPoolExecutor(...)` 都在 `try:` **之前**，任一抛异常则 `finally` 永不执行 → 策略永久停在 `"collect"`，此后进程内**任何**翻译失败都被塞进无人读取的队列（静默报错） | 子代理探针：`Live.start()` 失败后 `emit_mode after: collect`、`later serial failure on stderr: False`、`stranded in collector: 1` | ✅ 已修（全部 fallible setup 移入 `try`，`pool` 判空；新增 **AST 结构性守护**——该缺陷无法从外部激活性测试） |
| R-22 | `[SUGGESTION]` | `_emit_translate_failure` / 排空处 | 同一条失败消息有两种渲染：collect 路径走 rich（有 ANSI 高亮），串行路径走裸 `print` | 探针对照输出两通道的 ANSI 差异 | ✅ 已修（`console.print(..., highlight=False)`） |
| R-23 | `[SUGGESTION]` | `tests/test_pack_wiki_errors.py` | 新用例的 `failing` 桩含永不触发的 `page03` 分支（该文件 fixture 只有 1 页），误导读者以为覆盖了混合成败 | 用例输出首行 `wiki: 1 page(s) to translate` | ✅ 已修（换成诚实的成功桩） |
| R-24 | `[SUGGESTION]` | `_COLLECTED_FAILURES` 生命周期 | 队列是模块级且从不在入口清空，drain 后的残留会被**下一次** `run()` 打印（归属错位） | 探针：`queue size before run2: 1`、`run2 printed run1 residue` | ✅ 已修（进入时先排空一次） |
| R-25 | `[SUGGESTION]` | `README.md` / `README.zh.md` | `--translate-all` 在**无** `--translate-cmd` 时为空操作，两份 README 均未说明，且无用例 | 探针确认代码有提示行且行为正确（文档/测试缺失） | ✅ 已修（中英各补半句 + 新增提示行用例） |
| R-26 | `[SUGGESTION]` | 三处文档 | `§6.11` 交叉引用悬空（方案当时只有 §6.10）；索引累计计数与逐轮汇总不符；R-11 在编号表中缺号 | `git grep "6\.11"` 三处命中均指向不存在的小节 | ✅ 已修（补 §6.11、计数校正为 13 WARNING / 13 SUGGESTION、概览表补 R-11 行） |
| R-27 | `[SUGGESTION]` | 登记口径 | R-10「接受为风险」的理由需补实测依据：不可重入与跨 run 串味（R-24）**仍未解决** | 第 4 轮探针 | ✅ 已修（登记补注） |

**收敛判断**：代码修复层面收敛（第 1 轮 7 → 第 4 轮 0 条新增 WARNING；第 4 轮
唯一的 R-21 是四轮皆遗漏的**结构性**缺陷，非回归）。

## 五之二、第 5 轮（主代理复审未提交改动）：草稿本身站不住

> 触发：上一会话在 R-15 的"退出延迟"上做了改动并**留在工作区未提交**，
> 本轮开工时 `git status` 只有 `tools/pack/wiki.py` 与
> `tests/test_pack_wiki_errors.py` 两处修改。本节是对**这份草稿**的复审。

| # | 级别 | 位置 | 问题 | 证据 | 状态 |
|---|---|---|---|---|---|
| R-28 | `[WARNING]` | `_run_translate` 的轮询判定 / `_translate_pending.finally` | 取消信号是**进程级全局**，且判定 AND 了 emit 策略：`_STOP_TRANSLATIONS.is_set() and _emit_mode == "collect"`。而阶段收尾顺序是 `stop.set()` → 全局置位 → `pool.shutdown` → `progress.stop()` → `_emit_mode = "print"` → drain；worker 只在轮询里看这个条件，**落在窗口外的轮询永远看不到信号**，子进程照跑整页（即 R-15 实测 0.6 s → 3.1 s 的成因）。同一全局对进程内任何直接调用可见：库代码或扩展在 run 期间调 `translate_via_cmd`，会被别人家的 stage 取消 | 读码（HEAD `f531fd0`）+ 收尾顺序逐行核对 | ✅ 已修：阶段经 `threading.local` 把信号**发布给拥有该翻译的 worker**（`_run_batch` 发布、收尾清除），判定不再看 emit 策略；无 stage 的直接调用天然不可取消 |
| R-29 | `[WARNING]` | 草稿整体 | 草稿从未被跑过，三处硬伤：①`_ProgressBoard(stop=stop)` 写在 `stop = threading.Event()` **之前** → `UnboundLocalError`；②两条新用例 monkeypatch 了**不存在**的 `wiki._active_stage_stop`（生产符号是 `_stage_local` / `_stage_stop_requested()`）；③大页用例断言 `result.startswith("# en ")`，子进程回显 `# en 0`（空页）同样通过 → 恒真 | 实测 `pytest tests/test_pack_wiki_errors.py` → **4 failed, 28 passed**；`pyright tools/pack/wiki.py` → 2 errors（`reportUnboundVariable` / `reportUnknownArgumentType`） | ✅ 已修：创建顺序倒过来；用例改用 `getattr` 发布 thread-local；大页用例改为回显**解码后内容的 sha256 + 长度** |
| R-30 | `[SUGGESTION]` | `_ProgressBoard` | 草稿给 board 加了 `stop` 字段，而 `_run_batch` 本来就收到同一个 Event——同一对象两处来源（R-08 同类） | 读码 | ✅ 已修（删字段，worker 直接发布自己收到的 `stop`） |
| R-31 | `[SUGGESTION]` | `translate_via_cmd` 协议 | stdin/stdout 的**编码契约**从未写明：父进程以 UTF-8 写出，hook 若按本地编码解码就得到乱码（探针：子进程 `sys.stdin.read()` 后 `.encode('utf-8')` → `UnicodeEncodeError: surrogates not allowed`）；中英 README 只写"stdin 进中文、stdout 出英文" | 探针实测 | ⏸ 接受并文档化（第 6 轮补 README） |

**stdin 管道归属（A/B 实测，纠正草稿的错误结论）**：`communicate()` 会在首次
无 input 调用时关掉 `Popen.stdin`（Windows `_stdin_write(None)`、POSIX
`_communicate`）——探针实测 `after first communicate -> closed: True`，即写侧线程
与主线程会共用一条管道。已修：writer 拿到管道后立刻 `proc.stdin = None`，所有权
唯一。**但这是加固而不是修复可观测的截断**：A/B 实测 3/3 次整页送达
（224 KB 页 → 233484 字节，含文本模式 CRLF 展开），因为
`io.BufferedWriter` 的锁把那次 `close()` 挡在整次写入之后。草稿注释里
"实测 224 KB 被截断、出现 surrogate" 是错的（surrogate 来自子进程按本地编码解码
UTF-8 的探针假象），已在代码注释与用例 docstring 中改正。

**判别力实测（变异测试）**：

| 变异 | 目标用例 | 结果 |
|---|---|---|
| M1：撤掉 `_run_batch` 的信号发布 | `test_a_torn_down_stage_kills_the_child_its_worker_is_waiting_for` | ✅ 变红（译者活过整轮，`_wait_for` 5 s 失败；该用例是这条链路上首次出现的端到端守护） |
| M2：判定换回"全局 + AND `collect`" | 同上 | ❌ **不变红**：本机收尾窗口约 100 ms 宽，worker 的 0.2 s 轮询仍可能落进窗口内。旧设计的暴露面只能靠现场测量（R-15）证明，无法在进程内确定性复现——这一点如实登记，不假装已锁定 |
| M3：撤掉 `proc.stdin = None` | 大页完整性用例 | ❌ 不变红（见上：A/B 3/3 送达）——该行按"加固"记账 |

## 五之三、第 6 轮（确认性复核）

| # | 级别 | 位置 | 问题 | 状态 |
|---|---|---|---|---|
| R-32 | `[SUGGESTION]` | `README.md` / `README.zh.md` | R-31 的文档落点：两份 README 的 `--translate-cmd` 说明补上编码（UTF-8），中英同步 | ✅ 已修 |

复核结论：0 CRITICAL / 0 WARNING。逐条确认 `_run_batch` 的 `finally` 会清掉
thread-local（池线程复用不串味）、`_feed_stdin` 只吞 `OSError`
（含 `BrokenPipeError`，子进程的真实退出码仍由 `communicate` 报出）、大页 /
流式 / 早退 / 不可启动 shell 四条真实子进程路径的 stderr 契约无 traceback 泄漏。
本轮未引入新缺陷。

## 六、门禁实测（各轮结束时的真实数字）

| 轮次 | 命令 | 结果 |
|---|---|---|
| 第 1 轮 | `pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` |
| 第 1 轮 | `pytest tests/` + `--cov=yate --cov-fail-under=75` | 全绿；覆盖率 91.26% |
| 第 3 轮 | `pytest tests/test_pack_wiki.py tests/test_pack_wiki_errors.py tests/test_pack_wiki_parallel.py tests/test_tools_translate.py` | **93 passed, 1 skipped**（`skipif win32` 的 `[/x]` 用例） |
| 第 3 轮 | `pyright yate/ tests/ tools/` | `0 errors` |
| 第 4 轮 | `pytest tests/ --cov=yate --cov-fail-under=75` | **1861 passed, 9 skipped**；覆盖率 **91.27%** |
| 第 4 轮 | `pytest tests/test_architecture.py` | **22 passed** |
| 第 4 轮 | `pytest`（wiki 四文件）`--cov=tools.pack.wiki --cov=tools.translate` | **96 passed, 1 skipped**；tools 侧 **94%** |
| 第 4 轮 | `pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` |
| 第 5/6 轮 | `pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` |
| 第 5/6 轮 | `pytest tests/ --cov=yate --cov-fail-under=75` | **1933 passed, 9 skipped** in 417.25s；覆盖率 **91.26%**（阈值 75%） |
| 第 5/6 轮 | `pytest tests/test_architecture.py` | **22 passed**（与 wiki 四文件同跑：**125 passed, 1 skipped**） |
| 第 5/6 轮 | `pytest`（wiki 四文件）`--cov=tools.pack.wiki --cov=tools.translate` | **103 passed, 1 skipped**；tools 侧 **94%**（`wiki.py` 96%） |

变异测试记录（每次回退修复 → 目标用例变红 → 还原）：R-01 单次 `update`、
R-03 不传 `code`、R-04 复用传入 `code`、R-07 去卫语句、R-16 恢复旧顺序、
R-17 容器语义、R-21 AST 守护（把 `_emit_mode = "collect"` 移回保护区外即变红）。
第 3 轮评审另做 8 组 in-process 变异（含复原 R-01、复原批粒度、清空
`_INTERRUPT_EXIT_CODES`），均按预期变红。第 5 轮的 M1–M3 见 §五之二，其中
**M2、M3 预期不变红**（收尾窗口太宽、管道锁挡住截断），已按"未锁定"如实记账。

## 七、遗留与限制

- **真实 TTY 目验缺位**：无人值守会话无法向控制台投递 SIGINT / 无法目验，
  页级推进与最终帧形态靠注入断言与探针背书。
- **中断后退出延迟**：R-15 已由第 5 轮定位并修完（信号归属改为 stage 拥有）。
  旧设计为何在本机难以确定性复现、管道交接为何只能记作"加固"，见 §五之二
  变异 M2 / M3 与 §七。
- **`_emit_mode` 全局**：R-09/R-10/R-27 —— 进度回调异常复用翻译失败通道
  （仅 rich 缺陷可达）、`run()` 理论不可重入、跨 run 串味（R-24 已修入口排空，
  但串味本身依赖"两次 run 共享同一全局"，CLI 单 run 不可达）。
- **分支落后 master**：已于第 5 轮 `merge master` 处置（见
  [legacy-issues.md](legacy-issues.md) 的 R-11 条目）。

## 八、核对结论

- 无 CRITICAL；第 1 轮唯一的"自己引入的缺陷"（R-01）已由探针定位并修复，
  修复后的行为由变异测试锁定；第 4 轮补上的 R-21 是**四轮皆遗漏**的结构性缺陷，
  现由 AST 结构性守护锁定。
- 第 3 轮确认：`_translation_state` 重构前后**行为等价**（全组合核对）；
  `page_done` 两步更新在 2 线程 × 6000 次压测下未观测到文案落后
  （`lag samples: 0`，终值与文案一致）。
- 第 4 轮确认：中断链路六个位置（主线程 / worker 子进程 / 批次提交前后 /
  写 en 页 / 写 manifest / `push_wiki` 的 git 子进程）**均无 traceback 泄漏**，
  且均能以 130 退出；唯一例外是 R-15 记录的退出延迟。`tools/translate/cli.py`
  的中断边界（stdin 读取期间、临时目录清理期间）亦干净返回 130 且不留临时目录。
- 第 5 轮确认：R-15 的退出延迟不是"注释写错"而是**判定接错了状态**——信号归属
  从进程级全局改为 stage 拥有，判定不再与 emit 策略耦合；这条链路上第一次有了
  端到端守护（stage 收尾 → worker 亲手 kill 自己的子进程，M1 变异变红）。
  同时纠正了草稿的两处错误结论：`_ProgressBoard` 并不需要 `stop` 字段（R-30），
  "大页被截断 / 出现 surrogate" 不成立（探针假象 + `io.BufferedWriter` 的锁）。
- 第 6 轮确认：真实子进程四条路径（大页 / 流式早答 / 早退 / shell 起不来）的
  stderr 契约均无 traceback 泄漏；`_run_batch` 收尾清掉 thread-local，池线程复用
  不串味；编码契约已写进中英 README（R-31 / R-32）。
- 架构与风格：无 R1–R13 违规、无新增 `Protocol`/`TYPE_CHECKING`/`Any`/
  `# type: ignore`/裸 `except:`；命名守卫不命中；`tools/` 的 `print`
  属既有约定（R12 只约束 `yate/`）。
- 已知配置摩擦（非本轮引入）：`pyproject.toml` 的 `addopts = "-q"` 与命令行
  `-q` 叠加会吞掉 pytest 汇总行，评审记录中的数字需用 `-o addopts=` 才能读出。

