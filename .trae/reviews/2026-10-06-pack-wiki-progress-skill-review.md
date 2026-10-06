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
  一次性探针；共 3 轮（第 1、2 轮主代理，第 3 轮只读评审子代理）。
- **skill 缺口**：本轮创建了项目级 skill（机器本地，不入库）——此前
  `code-review-expert` 剧本要求的 `python-code-review` skill 在仓库与用户目录均不存在
  （第 1 轮评审实测加载失败）。

## 一、结论概览

| 轮次 | 结论 | 处置 |
|---|---|---|
| 第 1 轮（主代理） | 0 CRITICAL / 7 WARNING / 3 SUGGESTION | R-01…R-08 已修；R-09/R-10 接受为风险并附理由 |
| 第 2 轮（主代理） | 1 SUGGESTION + 1 权衡 | R-12 已修（死成员）；R-13 接受并文档化 |
| 第 3 轮（只读评审子代理） | 0 CRITICAL / 5 WARNING / 2 SUGGESTION | R-14…R-18 已修；R-19/R-20 文档修正 |
| 第 4 轮（只读评审子代理，确认性） | 0 CRITICAL / 1 WARNING / 6 SUGGESTION | R-21（四轮皆遗漏的结构性缺陷）已修并加 AST 守护；R-22…R-27 已修；**代码收敛** |

> R-11（分支落后 master）不是代码缺陷，是流程风险，只登记在
> [legacy-issues.md](legacy-issues.md)，故不出现在上方编号表中。
> 累计：0 CRITICAL / **13 WARNING** / **13 SUGGESTION**（R-09/R-10/R-13 为接受项）。

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

变异测试记录（每次回退修复 → 目标用例变红 → 还原）：R-01 单次 `update`、
R-03 不传 `code`、R-04 复用传入 `code`、R-07 去卫语句、R-16 恢复旧顺序、
R-17 容器语义、R-21 AST 守护（把 `_emit_mode = "collect"` 移回保护区外即变红）。
第 3 轮评审另做 8 组 in-process 变异（含复原 R-01、复原批粒度、清空
`_INTERRUPT_EXIT_CODES`），均按预期变红。

## 七、遗留与限制

- **真实 TTY 目验缺位**：无人值守会话无法向控制台投递 SIGINT / 无法目验，
  页级推进与最终帧形态靠注入断言与探针背书。
- **中断后退出延迟**：见 R-15（仅在自定义 hook 吞掉中断时可达）。
- **`_emit_mode` 全局**：R-09/R-10/R-27 —— 进度回调异常复用翻译失败通道
  （仅 rich 缺陷可达）、`run()` 理论不可重入、跨 run 串味（R-24 已修入口排空，
  但串味本身依赖"两次 run 共享同一全局"，CLI 单 run 不可达）。
- **分支落后 master**：修复分支基于 `d691bfb`，master 之后合入 PR !57（smoke 测试），
  `.trae/reviews/README.md` 与 `README.md` 两边都改过，合并顺序需注意
  （见 [legacy-issues.md](legacy-issues.md) 的流程风险条目）。

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
- 架构与风格：无 R1–R13 违规、无新增 `Protocol`/`TYPE_CHECKING`/`Any`/
  `# type: ignore`/裸 `except:`；命名守卫不命中；`tools/` 的 `print`
  属既有约定（R12 只约束 `yate/`）。
- 已知配置摩擦（非本轮引入）：`pyproject.toml` 的 `addopts = "-q"` 与命令行
  `-q` 叠加会吞掉 pytest 汇总行，评审记录中的数字需用 `-o addopts=` 才能读出。

