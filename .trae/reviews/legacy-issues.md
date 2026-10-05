# yate Code Review — 历史问题（早期登记，无日期）

## 历史问题

- [x] 输入时候，屏幕会闪烁，影响输入体验，加入放抖动机制。
- [x] yate 输入一个不存在的文件名，进程会卡住无任何输出，希望和vim一样，直接进入enew新建一个bug。

## 已知设计权衡与守卫局限（2026-10-01 登记）

来源：语义能力注入 PR 的 AI 审查（2026-10-01 00:18 第四轮，无阻断项、3 个改进建议）。
三条均为方案文档已登记的权衡或有意设计，当前不修复；触发条件出现时再评估。

- [ ] `spawn` 动词签名擦除：`Callable[..., Worker[object]]` 的 `...` 使调用处关键字
  参数（`group=` / `exclusive=` / `exit_on_error=`）失去静态拼写校验，目前靠冒烟
  测试兜底（6 个流程模块，如 `yate/document_flows.py`）。若 `run_worker` 调用形态
  扩张或需更强静态保障，再评估更具体的 Callable 签名（注意 R2 禁新增 Protocol）。
- [ ] AST 守卫 `_stringified_imprecise` 仅匹配顶层精确形态（`"App[Any]"` /
  `"App[object]"`），不捕获嵌套字符串化注解（如 `"list[App[Any]]"`）；当前仓库无
  此形态，扫描面已由方案声明（变量 / 参数 / 返回值三处顶层）。
- [ ] 守卫 `test_flow_modules_hold_no_app_handle` 为非递归扫描
  （`YATE.glob("*.py")`），仅覆盖 `yate/` 顶层——L3 流程模块均居顶层，L2
  （`editor_view/*`）的向上依赖由 R3 守卫覆盖；模块布局调整时须同步复核扫描范围
  与该测试 docstring。

## pack wiki 进度刷新与 Ctrl+C 治理：审查轮问题（2026-10-06 登记）

来源：`python-code-review` skill 对 `fix/pack-wiki-progress-refresh` 累计改动的审查
（issue IKJPEK 评论 `note_51450440` 驱动的修复 + 两轮审核处置 + 中断治理）。
方案与逐条处置见
[pack-wiki-progress-refresh-plan.md](../documents/pack-wiki-progress-refresh-plan.md) §6.7–§6.9。
编号 `R-*` 为本轮编号（与 PR !56 评审的 P1–P4 区分）。

### 待修（本轮已定位）

- [ ] **R-01 · `[WARNING]` 总体行文案落后进度条一页** —
  `tools/pack/wiki.py` `_ProgressBoard.page_done`：`_description()` 作为**参数**
  在 `update(overall, advance=1, ...)` 之前求值，读到的是推进前的计数。
  影响范围：wiki 翻译全程，总体行显示的页数恒比进度条少 1（探针实测
  `delta=1`，仅批末 `batch_finished()` 才纠正）；与 README「进度条与文案同源」的
  承诺不符，也与本轮修复目标（消灭"条与文案不一致"）自相矛盾。
- [ ] **R-02 · `[WARNING]` 中断链路的端到端无用例** —
  `tests/test_pack_wiki_parallel.py::test_console_interrupt_reaches_the_cli_as_exit_130`
  走的是 `translate_via_cmd` 直接抛 `KeyboardInterrupt`，未覆盖
  `_INTERRUPT_EXIT_CODES` → `_run_translate` → worker → 主线程 → CLI 130 这条
  **真实**链路（用户报告的正是这条）。影响范围：`wiki.py` 的中断码识别与
  `tools/translate` 返回 130 的接线无测试背书，接线被改坏不会有用例变红。
- [ ] **R-03 · `[WARNING]` manifest 写失败用错错误码**（原有缺陷，PR !56 P1） —
  `store_manifest()` 经 `_write_page_text()` 固定用 `WIKI_PAGE_WRITE`（WIKI-0106），
  `WIKI_MANIFEST_WRITE`（WIKI-0105）为死码。影响范围：manifest 写失败与普通页面
  写失败在输出中不可区分；排查 `.translation-manifest.json` 损坏时缺少定向码。
- [ ] **R-04 · `[WARNING]` 通用 `OSError` 被误报为"源文件消失"**（原有缺陷，
  PR !56 P2） — `_read_source_bytes()` 的通用 `OSError` 分支复用传入 `code`，
  默认 `WIKI_ZH_SOURCE_MISSING`（WIKI-0102）；权限不足、磁盘故障被误报，
  `WIKI_SOURCE_UNREADABLE`（WIKI-0103）为死码。影响范围：所有源文档读取失败场景
  的错误码语义。
- [ ] **R-05 · `[WARNING]` 中断时在途 worker 的失败行可能丢失**（原有缺陷，
  PR !56 P3） — `_translate_pending` 的 `finally` 先 `pool.shutdown(wait=False)`
  再清空 `_COLLECTED_FAILURES`；仍存活的 worker 可能①追加到已清空的列表导致丢失，
  ②在 `_emit_mode` 恢复后直接写 stderr，造成两次运行输出交错。影响范围：中断与
  并发收尾路径的可追溯性。
- [ ] **R-06 · `[WARNING]` `needs_translation` 成为死代码且判定重复**（原有缺陷，
  PR !56 P4） — `run()` 已不再调用它（仅测试引用），而 fresh/stale/missing/adopted
  的判定在它与 `_prepare_pages` 各写一遍，规则可能漂移。影响范围：维护面，
  `--translate-all` 的预告数与主循环判定的一致性。
- [ ] **R-07 · `[WARNING]` 空 `plans` 会抛 `ValueError`** — `_translate_pending([])`：
  `workers = min(resolve_jobs(jobs), 0)` → `ThreadPoolExecutor(max_workers=0)` 抛错。
  生产路径被 `run()` 的 `if plans:` 挡住，但函数自身无卫语句。影响范围：直接调用
  该函数（测试 / 未来复用）时崩溃。
- [ ] **R-08 · `[SUGGESTION]` 同一对象两个名字** — `_ProgressBoard` 字段叫 `progress`，
  `_translate_pending` 局部变量叫 `display`。影响范围：可读性（前者已随参数删除
  统一过一次）。

### 已接受为风险（附理由，不再复议）

- [ ] **R-09 · 进度回调异常复用翻译失败通道** — `_ProgressBoard` 的回调与翻译同处
  一个 `try`，若 rich 自身抛错会被记作 `outcome.error` 并中止整轮。键来源已单一
  （submit 遍历 `batch_tasks`），该路径只在 rich 缺陷时可达；为它新增独立告警通道
  属过度防御。**接受**，理由：复杂度收益为负。
- [ ] **R-10 · `_emit_mode` 全局使 `run()` 理论不可重入** — 修法需改
  `translate_via_cmd` 公开签名（测试与文档均依赖）。CLI 每次进程只跑一个 run，
  并发两个 run 不可达。**接受**，与 R-05 的丢失问题分开处理：R-05 修数据丢失，
  本条保留为文档化限制。

### 流程风险

- [ ] **R-11 · 修复分支落后 master** — `fix/pack-wiki-progress-refresh` 基于
  `d691bfb`，master 之后合入了 PR !57（smoke 测试，5000+ 行）。本分支改动集中在
  `tools/pack/wiki.py`、`tools/translate/cli.py`、三个测试文件与两份 README，与
  smoke 改动基本不重叠，但 **`.trae/reviews/README.md` 与 `README.md` 两边都改过**，
  合并顺序不当会产生冲突。状态：待用户决策（建议先合 PR !57，再 rebase 本分支）。
