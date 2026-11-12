# 2026-11-12 全仓库多维度评审（multi-dim-review 第三轮）

- 分支：`feature/fix-repo-audit`（worktree 为本任务沙箱，路径已按
  `doc-conventions.md` §五 脱敏，不在此暴露；沙箱 `.venv` 新建重建）
- 基线：`master` `7665814a`（与 `origin/master` 同步，工作树干净）
- 范围：按用户指令对**全仓库**（yate/ 约 4.4 万行 + tests/ + tools/ + pack/）
  按 `multi-dim-review` 技能 13 维度做一轮全新只读审计；发现确证后走方案
  工作流修复（见 §四，修复动作归
  [`../documents/multi-dim-review-r3-fixes-plan.md`](../documents/multi-dim-review-r3-fixes-plan.md)）
- 形态：**只读事实文档**（doc-conventions §二.1），只记录发现与核对结论
- 交叉引用：前两轮同技能轮
  [`2026-11-05-multi-dim-review-r2.md`](2026-11-05-multi-dim-review-r2.md)、
  全仓库审计系列
  [`2026-10-18-full-repo-audit-r3.md`](2026-10-18-full-repo-audit-r3.md)
- 无人值守：用户指令「全程无人值守，无须过问」——【批准】步骤由用户预先授权，
  登记于修复计划文档头

## 一、门禁基线（主代理亲跑，worktree 沙箱，修复前）

| 门禁 | 命令 | 结果 |
|---|---|---|
| pyright strict | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | **0 errors**，exit 0 |
| pyright（pack 面） | `.venv\Scripts\python.exe -m pyright pack/` | **0 errors**，exit 0 |
| 架构守卫 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | **38 passed**，exit 0 |
| 全量回归 | `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | exit 0（计数收尾复测） |
| 覆盖率 | `--cov=yate --cov-branch -n auto` | **92.96% ≥ 75%**，exit 0 |
| 冒烟 | `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` | **123/123 scenarios，1493/1493 checks**，exit 0 |
| changelog | `.venv\Scripts\python.exe -m tools.changelog check` | exit 0（lag 为发布期刷新语义，非缺陷） |

七道门禁全绿；本轮发现不改变「基线可发布」判定，MAJOR/MINOR 见 §三。

修复闭环后收尾复测（主代理亲跑，2026-11-12，全部改动落盘后）：

| 门禁 | 命令 | 结果 |
|---|---|---|
| pyright strict | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | **0 errors**，exit 0 |
| pyright（pack 面） | `.venv\Scripts\python.exe -m pyright pack/` | **0 errors**，exit 0 |
| 架构守卫 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | **38 passed**，exit 0 |
| 全量回归 | `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | exit 0；junit 计数 **3647 tests / 0 failures / 0 errors / 10 skipped** |
| 覆盖率 | `--cov=yate --cov-branch --cov-fail-under=75 -n auto` | **92.98% ≥ 75%**，exit 0 |
| 冒烟 | `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` | **123/123 scenarios**，exit 0 |
| changelog | `.venv\Scripts\python.exe -m tools.changelog check` | exit 0 |

## 二、审计执行方式

5 个只读评审员两波 fan-out（批内 ≤3，符合 subagent-workflow 上限），各维度分工
沿用技能 Step 6 先例形态：SA（D1 正确性 + D2 健壮性）、SB（D3 安全 + D4 算法复杂度 +
D5 性能）、SC（D6 架构边界 + D7 结构职责）、SD（D8 类型纪律 + D9 风格 + D10 并发可观测）、
SE（D11 测试 + D12 文档双语提交卫生）。评审员只输出 `文件:行号 → 证据 → 候选 → 自判`，
不改文件、不跑门禁。**主代理逐条回读复核**（§三全部 keep 项经主代理现场重读取证），
门禁全部由主代理亲跑（§一）。

## 三、逐维度结论

| 维度 | 结论 | 关键发现（主代理复核后） |
|---|---|---|
| D1 正确性 | 全合规（1 处契约不一致） | 窗格树关闭不变量、undo/redo delta、`take_dirty_range`/`dirty_range` 契约逐项推演无缺陷；`buffer.commit()` 标脏缺结构扩排（m4） |
| D2 健壮性 | 全合规 | 裸 `except:` 0；`except Exception` 48 处全部带 `# noqa: BLE001` 理由；`except X: pass` 17 处逐一甄别为 EAFP/拆除/探测语义；`run_worker` 20+ 调用点全部传 coroutine function/partial，零 eager 协程 |
| D3 安全 | 2 MINOR（.yxp 恶意包面） | 四处信任闸门（项目 rc / extensions 自动装载 / workspace 主题 / trust store）全部核实完备，F2 先例修复在位；`shell=True` 判定为用户显式发起的合法面（终端应用固有）；yxp 两处封顶缺口（m2/m3） |
| D4 算法复杂度 | 1 MAJOR + 1 MINOR | `project_search` 全量物化后再截断（M1）；`replace_current` 同 pattern 双编译（m1）；buffer bisect 区间表基准无回归；无界缓存全仓 0（均有界/键集有限） |
| D5 性能 | 0 缺陷，2 疑点 | 每键渲染路径 grep 取证干净（per-key snapshot/get_text 两条已由 perf-audit dirty-range 契约吸收，不重复报）；疑点见 §五 |
| D6 架构边界 | 全合规 | R9 id↔tcss 双向比对无漂移；R10 无吞键；R13 盲区（compose/dispatch/flows）零 `.styles.` 直改；R15 盲区零漏接线；`UPWARD_EDGES_FROZEN`/`SCROLLBAR_EXEMPT`/`HOME_PATH_EXEMPT` 空集实测成立 |
| D7 结构职责 | 2 MINOR（规则文本漂移） | `SIZE_EXEMPT_FILES` 登记行数 4 处漂移（m13）；`services/yxp` 门面例外未回写 §三.5②（m14）；>800 行文件恰 5 豁免 + `editor.py` 800 贴线，无漏网；包 `__init__` 惰性除登记例外全合规 |
| D8 类型纪律 | 1 MINOR（注释形态） | `Optional/Union/TypeAlias` 全仓 0；抑制站点 19 处全部带规则码，唯 `regression.py:268` 缺理由注释（m7）；守卫 #26 盲区（裸 Callable 别名）0 命中 |
| D9 风格 | 1 MINOR | 全仓 AST 逐行复测 >100 字符仅 1 处（m6），>120 零；日志 f-string/`print` 别名/CJK 注释盲区变体全 0；`manual.py` 两处 CJK 字符串为双语回退文案（#34 设计内放行） |
| D10 并发可观测 | 1 MINOR | 线程→loop 交接（pty `_post`/`call_soon_threadsafe`）教科书级；8 处防抖全部命名常量 + cancel-first；didOpen 失败静默 return 无日志（m5，兄弟路径 didClose/didSave 均有 `log.debug`）；tests 主题/HOME/cwd 隔离全闭环 |
| D11 测试 | 5 MINOR | 固定 sleep 断言 3 处（m8/m9/m10）、死 delay 旋钮（m11）、恒真负向断言（m12）；守卫 #38 无负向演练登记（m15 同波处置）；近 30 提交 16 个新模块 16/16 有专属测试，零盲区 |
| D12 文档双语 | 2 MINOR（登记类） | 近 60 提交双语成对全达标（唯一单侧为合法 reflow）；changelog 无手改证据；提交信息 60 条全合规（`!NNN` 前缀为平台产物）；`.trae` 近 14 天文档单行盘符路径 10 处（m15）；§三.7/§三.5② 规则文本漂移（m13/m14） |
| D13 硬门禁 | 全绿 | §一七道门禁 exit 0 |

## 四、确证发现清单（严重级，主代理逐条回读取证）

```
[MAJOR] M1 yate/editor_core/project_search.py:161 — 全量物化后再截断
Problem: `_search_one_file` 调 `search_lines(lines, pattern)[:budget]`，而
`search_lines`（:196-212）把整文件全部匹配物化为 frozen dataclass 列表后才被
调用方截断到全局 budget（2000）。2MB 单行高频模式可先造百万级对象再丢弃；
`max_file_bytes` 封顶输入不封顶中间量。D4 构造判定，大输入路径。
Fix: `search_lines` 增加可选 `limit` 参数（默认 None 保持公共契约），命中数达到
limit 即 break；`_search_one_file` 传 `budget`。

[MINOR] m1 yate/editor_core/search.py:123,130 — replace_current 双编译
Problem: `use_regex` 分支 :123 与 :130 各调一次 `self._compile(self.query)`，
同参数重算。
Fix: 函数顶部编译一次并复用。

[MINOR] m2 yate/services/yxp/manifest.py:205-217 — JSON 成员读取无界
Problem: `_load_json_member` 用 `zf.read(member)` 全量解压入内存后才校验，
撒谎头部 + 高压缩比 manifest/checksum 成员可造成单次内存尖峰。
Fix: 改走 `_read_member` 有界流式读取（真实字节封顶 32MB，不信任 ZipInfo.file_size）。

[MINOR] m3 yate/services/yxp — 真实字节累计封顶缺失
Problem: manifest.py:180-183 的 `total_size` 按可伪造的 `ZipInfo.file_size` 头部
校验 MAX_PAYLOAD_BYTES；成员数无界，恶意包可在 install 提取时写出 N×32MB
（磁盘/CPU 放大）。需用户显式安装恶意包，故 MINOR。
Fix: `_verify_digests` 与 `install._extract_payload` 各自按真实字节累计封顶
MAX_PAYLOAD_BYTES；头部预检保留为快速拒绝路径。

[MINOR] m4 yate/editor_core/buffer.py:579-583 — commit() 标脏缺结构扩排
Problem: `commit()` 经 `_record`→`_note_dirty(top, top+max(len(old),len(new))-1)`，
行数变化时不扩排到末行；`_apply_deltas`（:612-615）对 `len(old)!=len(new)` 显式
扩排。两条 delta 记录原语标脏规则不一致。现行唯一调用方（search.replace_all）
保证行数不变，故为契约漂移而非现行缺陷。
Fix: `commit()` 对结构增删行补与 `_apply_deltas` 同型的一行扩排。

[MINOR] m5 yate/editor_lsp/manager.py:422-423 — didOpen 失败零日志
Problem: `except (LspError, OSError): return` 静默丢弃，跨层调用失败无 log record
（D10）；兄弟路径 didClose(:465)/didSave(:569) 均有 `log.debug`。
Fix: 补 `log.debug("didOpen failed for %s: %s", uri, exc)`。

[MINOR] m6 tools/lint_lua.py:178 — 行宽 105 > 100
Problem: 全仓（yate/+tools/）AST 逐行复测唯一超限行。
Fix: 参数分行悬挂。

[MINOR] m7 tools/smoke_test/scenarios/regression.py:268 — 抑制缺理由注释
Problem: `# pyright: ignore[reportUnknownMemberType]` 无理由注释；同文件 :301-304
对同一调用已写明理由。
Fix: 补一行理由注释（指向 Textual bare Worker generic）。

[MINOR] m8 tests/test_lsp.py:797 — 固定 sleep 断言
Problem: monkeypatch CHANGE_DEBOUNCE_S=0.01 后 `sleep(0.1)` 再断言 didChange 合成，
xdist 高负载下可假失败；同文件 :1299 已有轮询范本。
Fix: 改 `wait_until` 轮询 `client.sent` 中 didChange 出现。

[MINOR] m9 tests/test_lsp.py:1122 — 固定 sleep 等待 STARTING
Problem: `sleep(0.1)` 后断言 `fake.state is ServerState.STARTING`。
Fix: 轮询状态转换。

[MINOR] m10 tests/test_pty_proc.py:605 — 弃用自家 _wait_for 且丢弃输出
Problem: 同文件 :599/:787 均 `_wait_for(lambda: b"pty-ready" in ...)`，此处固定
`sleep(0.2)`，且 start 回调 `lambda _data: None` 丢弃了轮询所需的数据。
Fix: 回调收集数据 + `_wait_for` 等首个输出。

[MINOR] m11 tests/test_hover_integration.py:56,88-89 — 死 delay 旋钮
Problem: `self.delay` 初始化 0.0 后全文件从未赋值，:88-89 分支永不执行。
Fix: 删除该旋钮（三处）。

[MINOR] m12 tests/test_tracing.py:354-356 — 恒真负向断言
Problem: `caplog.at_level(logging.WARNING)` 把 handler 级别抬到 WARNING，DEBUG 记录
无论 logger 级别是否泄漏都被过滤，断言对其守护的 m-28 级别泄漏回归不可失败。
Fix: 直接断言 `logging.getLogger("yate").level == logging.NOTSET`
（logs.py:601/632 install 保存/uninstall 恢复 `_previous_level`）。

[MINOR] m13 .trae/rules/architecture-boundaries.md §三.7 — 登记行数漂移 4 处
Problem: 守卫 #28 只查成员资格不查行数；实测 splitlines：
`keymaps/vim.py` 1534（登记 1531，+3）、`editor_core/buffer.py` 1559（登记 1565，−6）、
`editor_lsp/manager.py` 879（登记 875，+4）、`file_manager/screen.py` 1017（登记 1018，−1）。
规则明文「修改文件时须同步更新行数」。
Fix: §三.7 四处数字修订并注记本轮复测日期。

[MINOR] m14 .trae/rules/architecture-boundaries.md §三.5② — yxp 门面例外漏登
Problem: `services/yxp/__init__.py:9-17` docstring 自称登记例外（R14 先例），
但 §三.5②「唯一例外」清单只列 theme 门面与 extensions 门面两项；
big-module-split-2 子包化时未回写规则。守卫 #25 只扫纯 L0 叶包，services 包根无守卫面。
Fix: §三.5② 例外清单补登 `services/yxp/__init__.py`。

[MINOR] m15 .trae 文档单行盘符路径 10 处（近 14 天修改已触发迁移义务）
Problem: doc-conventions §五 禁绝对路径/要求环境脱敏；以下单行提及均在近 14 天
被修改的文档中：`pr-review-fixes-plans/{prfix-ws,fix-cli,fix-fm}.md:3`、
`pr-review-deferred-fixes-plans/{fix-preview,fix-editor,fix-navtest}.md:3`、
`file-manager-plans/overview.md:165`、`ci-pilot-startup-stall-plan.md:134`、
`arch-sec-audit-plans/overview.md:3`、`reviews/2026-11-10-pr-review-feature-feat-lsp-hover-docs.md:69`。
Fix: 逐行改为可移植表述（`<worktree>` 占位）。多行执行记录簇见 §六登记不修。
```

另：守卫 #38（`test_hover_key_is_shared_and_identical`）无负向演练登记——
2026-11 后新增守卫的仓库惯例（R12/能力注入/回调别名）均明文登记演练，本轮补
一次单侧改键漂移演练并在规则 §六 登记（随 m13/m14 同波处置）。

## 五、Suspects（依赖未验证假设，不判级不修复）

```
[SUSPECT] yate/editor_lsp/client.py:311-314 — _stopping 分支缺 SIGKILL 升级
Claim: terminate 后 wait_for(3.0) 超时仅 pass，无 SIGKILL 升级；server 拒死时
可能残留持 cwd 的孤儿子进程。
Uncertainty: 触发窗口为 stop 与 connect 竞态且 server 无视 SIGTERM；:301-306
注释表明作者已知该场景并做了尽力处理。需构造拒死 server 的复现才能定性。

[SUSPECT] yate/editor_term/pty_proc.py:622-634 — ConPTY 句柄复用残余窗口
Claim: 快照 `_out_read` 后锁外 ReadFile，句柄理论上可在读期间被 close 并复用。
Uncertainty: 作者注释 :623-626 已显式登记该残余窗口并论证取锁不可行
（ReadFile 阻塞会死锁 close），属已知接受风险。

[SUSPECT] yate/editor_core/diff.py:95 — difflib 最坏 O(n²)
Claim: 大文件 diff 可卡顿。Uncertainty: SequenceMatcher 固有复杂度 +
autojunk=False 为正确性选择且被守卫钉死；需 profiler 实测大文件再议分块/超时。

[SUSPECT] yate/editor_core/project_search.py:146-148 — 整文件读
Claim: 可流式处整文件加载。Uncertainty: max_file_bytes 已封顶内存，收益需实测。

[SUSPECT] .trae/rules/python-coding-style.md §3.3 — Any 理由形态系统性偏差
Claim: 规则字面要求逐处行内理由，仓库实践为节级/叙述性理由
（283 处 Any vs 37 处行内标记，抽样使用场景全部合法）。
Uncertainty: 修订规则措辞或补守卫属规则层决策，非本轮擅改。

[SUSPECT] tests/test_architecture.py:555-567 — 手工 handler 簿记
Claim: finally 无条件 addHandler(caplog.handler) 与 pytest logging 插件 teardown
交错可致计数漂移。Uncertainty: 主路径成对性已覆盖，未复现。

[SUSPECT] tests/test_lsp.py:370 — sleep(1.0) 与 initialize 超时常量隐式耦合
Claim: 桩侧 1.0 须大于客户端超时才成立。Uncertainty: 当前常量关系成立，值得注释钉死。

[SUSPECT] tests/test_pack_wiki_parallel.py:385 — 墙钟计时断言
Claim: -n auto 下依赖调度余量。Uncertainty: 15 倍页预算余量充足，并发测试本质需要真实计时。
```

## 六、Suggestions（确证但仅建议，不影响判定）与登记不修

- `tests/` 六处 docstring 仍写「pytest's caplog can't see child-logger records」
  （test_diagnostics:524、test_extension_api:45、test_extensions:33、test_fonts:819、
  test_lsp:1423、test_syntax_engine:186）——pytest 9 的 `catching_logs` 已自动挂载
  非传播 logger，文案陈旧；随下次修改顺手更新。
- `yate/editor_components/explorer.py:348` `on_key` AST 嵌套深度 11——键位 if/elif
  链天然深，同类 `keymaps/vim.py:1325`（深度 12）为 SIZE_EXEMPT 单一键映射域先例，
  观察项不立项。
- §三.8 第 2 步「类型注解 + `None` 初值」与实现形态（纯注解，pyright strict 要求）
  措辞不符——规则文本修订建议，实质合规（13/13 流程模块经 #23 守卫全绿）。
- `#37` 演练登记位置漂移：演练记录在 `.trae` 文档面而非 test_architecture.py 注释，
  与 R12/能力注入条目「负向演练通过」写法不一致；本轮 #38 演练按文档面登记。
- `!135`/`!134` 合并提交 `!NNN ` 前缀为 Gitee 平台产物，非作者书写。
- yate/ 产品代码 19 处类型抑制站点无任何守卫登记面（新增抑制不会被拦截）——
  建议后续评估「抑制站点清单守卫」，本轮仅建台账（见 §八）。
- **登记不修（存量文档盘符路径簇）**：`arg-completion-plan.md`（47 处）、
  `enew-args-lsp-attach-naming-plan.md`（14 处）、`ec-structure-reorg-plans/` 三份
  子计划（32 处）、`test-speedup-plans/` 两份（10 处）——均为执行记录多行路径簇，
  整文件迁移即 doc-conventions §五 明文禁止的「专项清扫」，按「随下次修改逐步迁移」
  处理；全 `.trae` 存量命中 265 处/88 文件（本轮 grep 口径，其中近 14 天窗口约 113 处/20 文件，
  单行型 10 处已由 m15 处置）。

## 七、登记/延期事项复核（Step 6.4，一行一项）

| 项 | 现状 | 结论 |
|---|---|---|
| arch-sec-audit F4（logs chmod 只落叶子目录） | 代码未再触碰 | 不变，仍登记待办 |
| arch-sec-audit F5（无校验告警早于所有权校验） | 同上 | 不变 |
| arch-sec-audit F6（user_setup.default_base_dir 自拼 join） | 同上 | 不变 |
| arch-sec-audit F7（主题门控表述不一致） | 同上 | 不变 |
| yxp uninstall 中途 OSError 非原子 / yxp.py:398 缺口 | 存量语义 | 不变 |
| #74 的 7 MINOR（pack-dist-zip） | #75 轮（2026-11-11）16 条去重 issue 全闭环 | 已销账 |
| #60 minor#2（同 URI 从未 shown 静默不 attach） | 主计划 §6 residual backlog | 不变 |
| #64（ShellResult.command 标签歧义） | 登记项 | 不变 |
| #65 登记 2 MINOR | 登记项 | 不变 |
| #68 m-1（stress.py:157 toggles_back 负载敏感） | 本轮冒烟 --jobs 4 全绿未复现 | 不变，继续观察 |
| #69（179fdf6 test 前缀 / buffer language 前瞻缝） | 规则层决定/观察项 | 不变 |
| r3 perf 疑点（per-key snapshot / get_text join） | perf-audit dirty-range 契约已落地吸收 | 已闭环，不重复报 |
| themes.py 构造器重复 / 键映射名硬编码 | 登记待办 | 不变 |
| 文档下划线分词 / 存量盘符路径 | §五 随下次修改迁移 | 不变（本轮仅处置已触发单行 10 处，见 m15） |

## 八、豁免台账（本轮核对无滥用）

- `SIZE_EXEMPT_FILES` 5 文件成员资格合规（行数漂移另见 m13）；
- `UI_FROZEN_FILES` 12 键与实测导入面逐键一致（extension_flows/chunked_flows 确不导入）；
- `NON_ASCII_COMMENT_EXEMPT` 6 处引述型、`PRINT_EXEMPT_SITES` 4 处、R2 Protocol 白名单 4 类：
  无新增命中；
- `SCROLLBAR_EXEMPT` / `HOME_PATH_EXEMPT` / `UPWARD_EDGES_FROZEN` 空集实测成立；
- 类型抑制站点台账（无守卫面，本轮建立）：yate/ 产品代码 17 处 + tools/smoke_test 3 处，
  全部带规则码，仅 m7 缺理由注释；
- D3 判定为固有合法面：`shell=True`（shell.py/shell_flows.py/translate.py，用户/CLI 显式发起）、
  pty argv（noqa S603 理由属实）、lua lupa eval（固定模板 + 信任闸门）。

## 九、Strengths

- 信任模型执法完整：四处闸门（项目 rc、extensions 自动装载、workspace 主题、trust store
  fail-closed + resolve 折叠符号链接）逐一取证在位，F2 先例无回归；
- 异常处理纪律罕见地整齐：0 裸 except、48 处 `except Exception` 全部带理由、17 处
  `except-pass` 全部可证伪为 EAFP/拆除/探测语义；
- 协程启动纪律（RuntimeWarning=error 硬雷区）20+ 调用点零违规，5 处带防回归注释；
- 架构守卫与实况高度一致：R9/R10/R13/R15 四项守卫盲区专项实测全部干净，
  本轮发现集中于规则文本同步漂移而非边界实质破坏；
- 测试基建成熟：autouse 主题/HOME 隔离、13 处 cwd 全 monkeypatch、wait_until 范本在案，
  近 30 提交 16 新模块 16/16 有专属测试；
- 双语与 changelog 纪律：近 60 提交文档面 20 个提交除 1 个合法 reflow 外全部成对，
  零手改证据；缓存全部有界（LRU 32 / 256 整体重置 / lru_cache 显式上限）。

## 十、结论

Overall: **REQUEST_CHANGES**（1 MAJOR / 15 MINOR 确证，8 Suspects，6 Suggestions）。
七道门禁基线全绿；MAJOR 与全部 MINOR 经
[`../documents/multi-dim-review-r3-fixes-plan.md`](../documents/multi-dim-review-r3-fixes-plan.md)
当轮闭环，修复后复测门禁全绿并回填 §一（先例：#57 基线→当轮修复→收尾全绿）。

## 十一、本轮修复事实（收尾回填）

按修复计划三波执行，分支 `feature/fix-repo-audit` 共 15 笔提交（评审/计划 2 笔 +
Wave-A 5 笔 + Wave-B 6 笔 + Wave-C 2 笔），只提交未推送：

| 提交 | 项 | 内容 |
|---|---|---|
| `8542c5e0` | M1 | `search_lines` 可选 `limit` 早停，`_search_one_file` 传 budget；2 条回归用例（早停可观测 + 默认契约不变） |
| `81986cde` | m1 | `replace_current` 单次编译复用 |
| `685e6cc2` | m2/m3 | `_load_json_member` 改走 `_read_member`；`_verify_digests` 与 `_extract_payload` 按真实字节累计封顶 `MAX_PAYLOAD_BYTES`（头部预检保留为快速拒绝）；2 条 lying-stream 用例证明写入前拦截 |
| `4ed78531` | m4 | `commit()` 结构 delta 补末行扩排，与 `_apply_deltas` 对齐同一脏标记契约 |
| `15429736` | m5 | didOpen 失败补 `log.debug`（与 didClose/didSave 同型） |
| `1e24136b` | m6 | lint_lua 超宽行折行 |
| `b4a45671` | m7 | wait_for_complete 抑制补理由注释 |
| `2c500e6c` | m8/m9 | 固定 sleep 改因果轮询（didChange 到达；`fake.started`——state 自 `__init__` 即 STARTING 不能作同步点，且 `started` 在 client 注册之后置位，reaper 可回收） |
| `537b7c30` | m10 | terminate 场景收集输出 + `_wait_for` ready 标记（含 `_no_inherited_std_handles` 护栏，与同文件范本一致） |
| `ec154422` | m11 | 删除从未赋值的 `delay` 死旋钮 |
| `88ed96ad` | m12 | 恒真 caplog 断言改为钉死 NOTSET→DEBUG→NOTSET 真实 logger 级别 |
| `d18a8d69` | m13/m14/#38 | 规则 §三.7 三处行数复测同步（vim 1534、screen 1017、manager 883；buffer 经 m4 后恰回到登记值 1565 无需修订）；§三.5② 补登 yxp 门面例外；§六 #38 登记负向演练（单侧 `parse_key("<f7>")` → 守卫失败 AssertionError: vim.py → 还原通过） |
| `851f01a1` | m15 | 10 处单行盘符 worktree 路径改 `../yate-*` 相对表述，grep 复核命中 0 |

计划偏离登记（`plan-before-execute.md` §二.4 要求显式列出）：

1. **验收命令文件名修正**：计划 Wave-A 验收列出的 `test_search.py` / `test_buffer.py` /
   `test_yxp_manifest.py` / `test_yxp_install.py` 不存在——实测布局为
   `test_project_search.py`（含 SearchEngine 用例）、`test_editor_core.py`（含 buffer
   用例）、`test_yxp.py` + `test_yxp_subpackage.py` + `test_tools_yxp.py`（Glob 取证），
   按实际文件执行，覆盖面不变；
2. **m2/m3 合并一笔提交**：两项同改 `manifest.py`，无法按文件分笔（计划「逐条独立提交」
   的例外），提交信息同时引用 m2/m3；
3. **m9 轮询信号改选**：第一版按计划轮询 `state is STARTING` 复测失败（该值
   `__init__` 即成立，非同步点），依 manager 注册顺序取证改轮询 `fake.started`；
4. **m10 补 std-handles 护栏**：第一版复测失败（缺护栏时 ready 标记不达），按同文件
   resize 场景先例补齐。

时序敏感目标文件（test_lsp.py / test_pty_proc.py）按计划风险条款连跑 3 次全绿。
