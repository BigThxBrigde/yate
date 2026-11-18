# 合并前独立评审：ConPTY 短命子进程输出竞态修复（pty-win312-stream）

- 日期：2026-11-19
- 评审人：code-review-expert（reviewer）
- 性质：合并前只读独立评审；**未修改**任何产品源码 / 测试 / 规则 / 方案文档，**未** `git commit` / `git push`
- 对象：worktree `yate-pty-win312-stream`，分支 `feature/fix-pty-win312-stream`，base `master 015deee5`
- 范围（`git status --short`）：`M yate/editor_term/pty_proc.py`、`M tests/test_pty_proc.py`、`?? .trae/documents/pty-win312-stream-plan.md`；`git diff --stat`：产品 `+29/-8`（净 +21）、测试 `+87`
- 口径：本机 `pytest -q` stdout 无汇总行，一律以 `$LASTEXITCODE` 为权威信号（team-lead 任务书要求）
- 路径记法：本文所有路径均为**相对仓库根的相对路径**，不含盘符 / 用户目录 / 以 `/` 开头的仓库根绝对路径（`doc-conventions.md` §五）；文件名符合 §二.1 `YYYY-MM-DD-<topic>.md` 命名

## 规范来源与 skill 加载

评审前已逐个读取 `.trae/rules/` 下 8 个必读规则（`task-orchestration.md`、`plan-before-execute.md`、`subagent-workflow.md`、`architecture-boundaries.md`、`python-coding-style.md`、`doc-conventions.md`、`git-commit-message.md`、`misc-rules.md`）全文，并按 `.trae/agents/code-review-expert.md` 剧本执行。

> **skill 加载说明**：按规则总纲 §一.3「Skill 唯一权威来源是 `.trae/skills/`」，从 `.trae/skills/python-code-review/SKILL.md` 直接读取并加载其 6 维度框架（Correctness / Security / Performance / Pythonic Style / Maintainability / Error Handling）+ 输出格式；该 skill 未注册进 `use_skill` 工具的 `available_skills` 清单，故以读取 `SKILL.md` 落地，**加载成功、未回退**。严重等级沿用 `code-review-expert.md` 的旧三级 `blocker / major / minor`（报告标题用大写 Blocker / MAJOR / MINOR 呈现，与既有评审记录一致）。

## 结论

**APPROVE**（0 BLOCKER / 0 MAJOR / 1 MINOR）。

- 修复**真正消除**了竞态：`_watch_exit` 不再由 watcher 线程提前置位 `_closing`，`read_loop` 改为 `while True` 无条件执行首次 `ReadFile`，短命 ConPTY 子进程已渲染输出必达 `on_output`；`mark_closing()` 后移到 reader drain 完成、`process_finished` 之前，退出码链路不变。
- 唯一 MINOR 为 `is_closing` 公共属性 docstring 与修复后置位时机不一致（`pty_proc.py:219`），无功能影响、不阻塞合并，建议合入前顺手修订或登记待办。
- 门禁五项由本 reviewer **独立重跑**、全部 exit 0（数字见下表），不引用执行者自述数字。
- **未解决项**：本机仅 Python 3.13.2、无 3.12 解释器，CI Windows py3.12.10 的 `1 failed` 无法在本机精确复现，须在 CI / 3.12 runner 复核（详见「未解决项」）。

## 门禁实测（本 reviewer 独立重跑，逐项记录命令 / exit code / 关键输出）

| # | 命令（相对仓库根） | 实测关键输出 | exit |
|---|---|---|---|
| 1 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/` | `0 errors, 0 warnings, 0 informations` | **0** |
| 2 | `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | 点阵推进至 `[100%]`，全程无 `F` / `E`；`FULL_EXIT=0` | **0** |
| 3 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 43 个进度字符全为 `.`，`[100%]`；`--collect-only -q` 复核 `tests/test_architecture.py: 43` | **0** |
| 4 | `.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto` | `3880 passed, 10 skipped in 149.59s`；`TOTAL 20470 1112 6480 587 93%`；`Required test coverage of 75.0% reached. Total coverage: 93.11%`；`yate\editor_term\pty_proc.py 429 81 92 3 81% Missing 95->97, 248-372, 377->425` | **0** |
| 5 | `.venv\Scripts\python.exe -m pytest tests/test_pty_proc.py -q -n 1` | `...............................................sss [100%]`；`PTY_N1_EXIT=0` | **0** |
| 6 | 三条 N 用例 `-k` 定向、`-n 1` 与 `-n auto` | 两次均 `... [100%]`（真实执行，非 `sss`）；`N_N1_EXIT=0`、`N_AUTO_EXIT=0` | **0** / **0** |
| 7 | 静态只读探针（`python -c`） | `pty_proc.py LINES 781`、`test_pty_proc.py LINES 1187`；两文件 `WIDTH>100 []`、`NONASCII []` | **0** |
| 8 | 环境自证（`python -c`） | `3.13.2` / `os.name == "nt"` / `yate.__file__` 指向本 worktree（沙箱生效，符合 `task-orchestration.md` §二.1） | **0** |

补充：

- **覆盖率口径**：命令未显式带 `--cov-report=term-missing --cov-fail-under=75`，但 `pyproject.toml` 的 `[tool.coverage.report]` 已设 `show_missing = true` 与 `fail_under = 75`（单一来源，注释明确「a bare `--cov` reproduces the CI gate」），故输出自带 term-missing 报告与 `Required test coverage of 75.0% reached`。全仓 **93.11% ≥ 75**，达标。
- **未覆盖行性质**：`pty_proc.py` 81%，Missing `248-372` 为 POSIX `_UnixPty` 整段（本机 `os.name == "nt"`，平台互斥块）、`377->425` 为 `if os.name == "nt"` 分支跳转、`95->97` 为 spawn 失败时 future 已结算分支——均属既有 / 平台互斥（`pyproject.toml` §[tool.coverage.report] 注释已说明两平台腿覆盖互斥块）。**本次新增行 `pty_proc.py:633`（`while True`）与 `:661`（`mark_closing()`）均不在 Missing 列 → 新增代码有对应测试覆盖**，覆盖率未明显下降。
- **并行 flake**：`-n auto` 全量首轮即 exit 0，未触发 `reference_safe_delete_pytemp.md` 记载的收尾杀进程，故无需对全量做 `-n 1` 复核；`tests/test_pty_proc.py` 已按 team-lead 要求单独跑 `-n 1`，与 `-n auto` 结果一致（三条 N 用例两口径均绿）。
- **冒烟 `tools.smoke_test` 未跑（如实说明）**：本次改动仅在 L0 叶子 `yate/editor_term/pty_proc.py`（PTY 进程管理），不触碰 UI / 交互 / 渲染 / 按键路径；按 `python-code-review` skill 与剧本「涉及 UI/交互/渲染/按键路径的改动必跑」判据不属此类，且 team-lead 门禁清单未列该项，故未跑。

## 问题清单（按严重程度排序，已通过强制自我批判）

> BLOCKER 档：**无**。MAJOR 档：**无**。以下仅 1 条 MINOR。

### [MINOR] MINOR-1：`is_closing` docstring 与修复后的置位时机不一致

- **位置**：`yate/editor_term/pty_proc.py:219`
- **证据**：`pty_proc.py:219` 仍写 ``"""True once termination started or the child already died."""``；而修复后 `_watch_exit`（`pty_proc.py:664-681`）已删除 `self._owner.mark_closing()`（`git diff` 实证删除行），`_closing` 的置位者只剩 `start()` 失败分支（`:94`）、`terminate()`（`:135`）与 reader 末尾 `mark_closing()`（`:661`）。即**子进程自然死亡后、reader drain 完成前存在一个 `is_closing is False` 的窗口**；并且 `mark_closing` 的新 docstring（`:223-229`）已明确「after the reader has drained its output」，与 `is_closing` 的旧 docstring 形成模块内部表述不一致。
- **问题描述**：属性 docstring 暗示「子进程一死即为 True」，修复后实际需叠加「reader 已 drain 完」。属公共 API 契约描述准确性 / 可维护性缺口（后来者可能据此误用 `is_closing` 判断子进程存活）。
- **影响面（已核实，故非 major）**：全仓 `search_content` 实证 `is_closing` 在 `yate/` 生产代码中**仅 `pty_proc.py` 自身**（`write()` `:111` / `terminate()` `:133` / 注释 `:618`、`:639`）引用，**无任何外部消费者**；生产侧 `yate/editor_components/terminal.py:120-123` 的 `started` 用 `self.dead`、`refresh_header`（`:600`）用 `self.view.dead`、`shutdown()`（`:173-187`）用 `terminate()` + `wait_closed()` + `detach()`，均不依赖 `is_closing`。故无功能影响。
- **修复建议**：把 `:219` 改为例如 ``"""True once termination started or the reader has finished draining."""``，或「True once termination started or the child's output has been fully drained.」，与 `:223-229` 的新语义对齐；无需改逻辑、无需补测试。

## 重点核查结论（team-lead 指定 7 项）

1. **修复是否真正消除竞态 → 是**。基线形态经 `git show HEAD:yate/editor_term/pty_proc.py` 重新读取实证为 `while not self._owner.is_closing:` + `_watch_exit` 内 `self._owner.mark_closing()`（紧接 `# Give the reader a moment to flush the final repaint.` 之前）；`git diff` 显示两者分别被改为 `while True:` 与删除置位。修复后首次 `ReadFile`（`:645`）无条件执行，watcher 只 `wait(0.2)` + `_close_pty()`（`:679-681`），根因（watcher 抢先置位短路首次读）被切断。
2. **`while True` 是否会挂死 / 关 HPC 打断 `ReadFile` 是否可靠 → 可靠，不构成挂死**。`read_loop` 退出仅靠 `out_read is None`（`:643-644`）或 `not ok or count == 0`（`:655-656`），打断机制是 watcher `_close_pty()` 关闭 HPC 令 ConHost 释放输出管道写端、管道排空后 `ReadFile` 返回 0 / 失败。该机制**修复前后为同一机制**（基线 `_watch_exit` 末尾同样 `_close_pty()`，`terminate()` `:742-752` 亦依赖它）；独立实测背书：全量 `-n auto` 3880 passed（含 3 个长驻子进程用例 `tests/test_pty_proc.py:542` / `:569` / `:593` 与新增 N2 立即退出用例）全部通过 `wait_closed()` 结算，`test_pty_proc.py -n 1` 全绿。`watcher.join(timeout=3)`（`:660`）有界，不挂死。方案 §9 R1 已显式登记该风险并给出 `REAL_PTY_TIMEOUT` 兜底，属「已识别且实测背书的设计权衡」，非未识别缺陷（见自我批判 F-D）。
3. **`is_closing` 语义后移是否破坏 `write()` / `terminate()` / `wait_closed()` 契约 → 不破坏**。
   - `write()`（`:109-117`）：子进程退出到 drain 完成的窗口内 `_closing` 仍为 `False`，会尝试 `_impl.write`；`_ConPty.write`（`:719-730`）对失效句柄的 `WriteFile` 返回 FALSE（ctypes 不抛 `OSError`），等价于 no-op，不抛到 UI；`test_real_pty_write_after_exit_is_a_noop`（`tests/test_pty_proc.py:633`）覆盖。
   - `terminate()`（`:131-139`）：`if self._closing: return` 幂等仍在；窗口内若被调用会走完整路径，但 `_close_pty()`（`:683-687`）幂等（`_hpc is not None` 保护）、`TerminateProcess` 对已退出进程无害，持 RLock 与 watcher 串行，无死锁。
   - `wait_closed()`（`:103-107`）：仍由 `process_finished → _finished → future.set_result(code)`（`:174-185`）结算；`mark_closing()`（`:661`）在 `process_finished`（`:662`）之前且 `_finished` 内的 `close()` 不依赖 `_closing`，结算路径不变；`mark_closing()` 先于 future 结算，故 `wait_closed()` 返回时 `is_closing` 已为 True，UI 侧后续 `write()` 正确 no-op。
4. **POSIX 侧是否受影响 → 代码未改，不受影响**。`_UnixPty.read_loop`（`pty_proc.py:301-328`）是既有 `while True` + master-fd `os.read` EOF + `proc.wait()`，不读 `is_closing`、不调 `mark_closing()`；`git diff` 未触碰该分支。附带说明（不作 finding）：POSIX 侧子进程自然退出后 `is_closing` 永不为 True（仅 `terminate()` / spawn 失败置位），与方案 §2 G2「子进程已死 → is_closing True」的字面描述不符，但这是**既有不对称**（修复前也只有 `_ConPty` 的 watcher 置位）、方案非目标明确「不改 POSIX `_UnixPty`」，且 `is_closing` 无生产消费者（见 MINOR-1 影响面），无生产影响。
5. **三条回归用例能否拦截回归 / 负向演练证据是否可信 → 能，证据可信**。
   - 三条用例本机（`nt`）在 `-n 1` 与 `-n auto` 均真实执行（`...` 而非 `sss`，见门禁 #6），skipif 守卫生效。
   - 逐条以「基线产品代码（`git show HEAD` 实证）+ 修复版测试」静态推演，三条**修复前必红**：N1（`tests/test_pty_proc.py:1041-1061`）基线 watcher 调 `mark_closing()` → `marked == [True]` 令 `assert marked == []` 失败；N2（`:1064-1096`）包装器先 `proc.mark_closing()`，基线 `while not is_closing` 循环体零执行 → `got is False` 令 `assert got is True` 失败；N3（`:1099-1125`）`_proc_info=None` 无 watcher、基线 reader 末尾无 `mark_closing()` → `events == ["finished"]` 令 `assert events == ["mark","finished"]` 失败。执行者方案 §12.2 自述 `FFF` → 恢复 `...` 与该推演一致。
   - 三条设计确定性：N1/N3 为纯同步 fake（`_FakeKernel32` / `SimpleNamespace` / monkeypatch），N2 用 `_wait_for` 轮询谓词 + `asyncio.wait_for(..., REAL_PTY_TIMEOUT)`，不依赖固定 sleep 时长（`python-coding-style.md` §4.7）；D2 已把带参数 lambda 改为带完整注解的嵌套 `def`（`:1114-1118`），断言未放宽。
   - **诚实边界**：任务书禁止修改任何代码 / 测试，故本 reviewer **未亲自重跑「文字级回退 → 红 → 恢复 → 绿」**；上述「修复前必红」结论基于 `git diff` / `git show HEAD` 实证的基线代码形态逐条静态推演，非亲跑（见「未解决项」U4）。
6. **docstring / ASCII / 行宽 / 类型注解 → 全部合规**。三处更新 docstring 与三条用例 docstring 均为散文式英文（`python-coding-style.md` §二、`misc-rules.md` §四）；静态实测两文件 `NONASCII []`、`WIDTH>100 []`（门禁 #7）；三条用例 `-> None` / `monkeypatch: pytest.MonkeyPatch` / 嵌套 def 参数注解齐全，pyright strict 实测 0 诊断（门禁 #1）；`from __future__ import annotations` 保持文件首；无新增 `Any` / `# type: ignore` / `TYPE_CHECKING` / 相对导入。
7. **文件体量是否仍 < 800 → 是**。实测 `pty_proc.py` **781 行**（splitlines 口径，`architecture-boundaries.md` §三.7），`< 800`，`SIZE_EXEMPT_FILES` 无需登记、架构守卫 #28 仍绿（门禁 #3）；`tests/test_pty_proc.py` 1187 行，`tests/` 不设限。

## 方案文档 §12.3 D1-D4 偏离记录核查

| 偏离 | 核查结论 | 依据 |
|---|---|---|
| D1（N2 补 `skipif(os.name != "nt")`） | 合理 | 只读取证 `_UnixPty.read_loop`（`:301-328`）为 `while True` + EOF、不读 `is_closing`，回退 Step 1 在 POSIX leg 不会令 N2 变红；不加守卫则该用例在 POSIX 是「常绿、负向演练无效」，稀释守卫语义；三条守卫一致 |
| D2（N3 带参 lambda → 带注解嵌套 def） | 合理、非「改断言凑绿」 | 当前 `:1114-1118` 实测为 `def _record_emit(_d: bytes)` / `def _record_finished(_c: int | None)`，与既有 `_fake_writefile` 风格一致；pyright 由 3 errors 转 0 errors（门禁 #1 背书），断言 `:1124-1125` 不变 |
| D3（架构 43 例 vs 方案写 42） | 与实测一致，属基线差异、如实上报 | 独立实测 `tests/test_architecture.py: 43`、`--collect-only -q` 亦为 43，exit 0（门禁 #3）；未改 `tests/test_architecture.py` |
| D4（760 → 781 行，`+29/-8`） | 与实测一致 | 独立实测 781 行（门禁 #7），`git diff --stat` 产品 37 行变动 = `+29/-8`（净 +21，760+21=781）；增量来自 §5 要求的 docstring 与注释扩充，非计划外设计改动；`781 < 800`，`SIZE_EXEMPT_FILES` 无需登记 |

四条偏离均显式列出、附实测依据，符合 `plan-before-execute.md` §二.4「偏离方案必须显式列出并给出实测依据，不得静默改设计」。

## 规则合规核对

- **方案先行**（`plan-before-execute.md` §一）：改动虽仅 1 个产品文件，但命中第 4 判据「需先调研代码才能确定做法」（根因调研），属非平凡任务；已有 `.trae/documents/pty-win312-stream-plan.md`，含目标 / 非目标、备选方案否决（A1/A2/A3/B/C/D/E）、分步实施、Mermaid 时序图、风险与回滚、验收命令，合规。
- **架构边界**（`architecture-boundaries.md`）：改动仅在 L0 叶子 `editor_term/pty_proc.py` 内部，零新增 import 连线、不跨层、不新增模块 / 协议 / EventBus / `TYPE_CHECKING` / `Any`；`mark_closing()` 调用者从 `_ConPty._watch_exit`（watcher 线程）迁到 `_ConPty.read_loop`（reader 线程），仍是具体对象方法调用（R8 / §四 1:1）。42+1=43 条守卫全绿，**无需新增守卫用例**。
- **Python 风格**（`python-coding-style.md` §五快速清单）：逐项核对通过（见重点核查结论 §6）；覆盖率 / 并行口径见门禁表。
- **日志**（R12）：未新增日志，既有 `log = tracing.get_logger(__name__)` 与惰性 `%` 保持。
- **doc-conventions.md**：评审记录命名 / 相对路径引用合规（见文件头）。
- **git-commit-message.md / subagent-workflow.md**：本任务无提交、无子代理产出，N/A。

## 未解决项

| # | 未解决项 | 原因 / 建议 |
|---|---|---|
| **U1（重点）** | **无法在本机用 Python 3.12.10 精确复现 CI 的 `1 failed`，也无法本机实测「修复后 CI 原命令 `1 failed → 0 failed`」** | 本机仅 `3.13.2`（环境自证门禁 #8），方案 P3 `install_binary` 失败（缓存误取 3.14.3 + 本机缺 `tar`）、P4 证实无 `py` / 任何 3.12 解释器。根因与 Python 版本无关（方案 §1.3/§1.4 的 3.13 确定性负向演练已复现），修复为纯线程时序逻辑修正，理论对 3.12 同样有效；但合并前仍须在 CI / 3.12 runner 按方案 §7.2 / §7.3 实测复核，**不得**把「本机 3.13 绿」等同于「CI 3.12 绿」 |
| U2 | CI 汇总「其余 3 个真实 PTY 用例全绿」为基于 `3876 passed` 的推断，非逐例实测 | 本 worktree 无法复现 3.12 CI 全量；方案 §11 U3 已标注，若 §7.2 实测与推断不符按 §7.4 兜底，不得改断言 / skip |
| U3 | 真实 TUI 手工验证（方案 §6 末「启动即退出命令」网格显示）未做 | CI 无法自动化，需人工在集成终端操作并回填 OS / Python 版本 |
| U4 | 负向演练「先红后绿」本 reviewer 未亲自重跑文字级回退 | 任务书禁止修改任何代码 / 测试；独立结论基于 `git diff` / `git show HEAD` 实证基线形态 + 三条用例逐条静态推演（修复前必红），与执行者 §12.2 自述 `FFF → ...` 一致；建议合并前由主代理在允许改文件的语境下补一次权威复跑 |
| U5 | 冒烟 `tools.smoke_test` 未跑 | 见「门禁实测」补充：本次非 UI / 交互 / 渲染 / 按键路径改动，且 team-lead 清单未列 |

## 强制自我批判登记（输出报告前的硬性环节）

**初版候选清单**：F-A（MINOR，`is_closing` docstring 与实现不一致）、F-B（拟 MAJOR，`mark_closing` / `process_finished` 位于 `try/finally` 之外，循环体异常会跳过、令 `wait_closed()` 挂死）、F-C（拟 MINOR，POSIX 自然退出不置 `is_closing`、与方案 G2 不符）、F-D（拟 MAJOR，`while True` 移除 `is_closing` 兜底退出、若 `_close_pty()` 失效则永久阻塞）。

**逐条反证结论**：

| # | 状态 | 理由 |
|---|---|---|
| F-A | **确认保留**（MINOR，未降级） | 重读 `:219` docstring、`:661` `mark_closing()`、`:664-681` `_watch_exit` 与 `git diff` 删除行，证据真实；`is_closing` 无生产消费者，故非 major；无功能影响，故非 blocker |
| F-B | **删除** | `git diff` 上下文证明修复前 `process_finished(code)` 同样在 `try/finally` 之外 → 既有结构、非本次引入；循环体内 `k["ReadFile"]` 为 ctypes BOOL 返回（不抛）、`emit_output → _post` 有 `is_closed()` 与 `try/except RuntimeError` 保护，异常路径无实证触发条件。按「宁可漏报存疑项，不留无实证断言」剔除 |
| F-C | **删除** | `_UnixPty` 代码未改（既有不对称）、`is_closing` 无生产消费者、方案非目标明确不改 POSIX → 非本次改动范围、无生产影响；结论转入「重点核查结论 §4」作说明 |
| F-D | **删除** | 打断机制修复前后同一（基线 watcher 与 `terminate()` 均依赖 `_close_pty()`），方案 §9 R1 已登记风险；独立实测全量 `-n auto` / `test_pty_proc.py -n 1` / 三条 N 用例全绿，`wait_closed()` 均结算 → 属已识别且实测背书的设计权衡；结论转入「重点核查结论 §2」作专项核查 |

**降级条目**：无（F-A 保持 MINOR，无夸大 minor→major、无漏判 major→blocker）。

**漏报自查**：反向扫正确性（竞态切断、`spawn` 失败 / `detach` / `terminate` / 双次 `process_finished` 路径逐条走查）、边界条件（`info is None` + `out_read None` 由 N3 覆盖；`out_read` 有效但无 watcher 的组合修复前同样会阻塞且非生产组合；`watcher.join(3)` / `_exit_code_or_failed` 5000ms 均有界）、异常处理（`start()` `except BaseException` re-raise 且结算 future、`_safe_call` 包 callback）、并发安全（`_closing` 跨线程布尔赋值在 GIL 下原子且幂等，写者由 watcher+UI 减为 reader+UI、竞态面缩小；`_handle_lock` RLock 保护句柄且 `_close_pty()` 幂等）、性能（循环结构与修复前同量级，无 N+1 / 循环内字符串拼接）、类型与测试覆盖（pyright 0、ASCII / 行宽 0 违规、781 < 800、覆盖率 93.11% ≥ 75 且新增行有覆盖、架构 43 全绿、负向演练静态推演）——**无明显遗漏**。

**最终报告** = 上述自我批判后清单（1 MINOR）+ 实测命令结果与退出码（门禁表 8 行）。

## Strengths

- 根因定位准确且有确定性负向演练支撑（`reads=0 / chunks=0 / code=0` 与 CI `assert False` 形态吻合），没有把负载下的竞态误记为「偶发、重跑即过」，也没有放宽断言 / 加固定 sleep / skip 3.12 来掩盖产品缺陷。
- 修复面极小（单产品文件 3 处内聚改动、零新增依赖 / 模块 / 协议），`is_closing` 的写者由 watcher+UI 收敛为 reader+UI，竞态面实际缩小；`mark_closing()` 与 `process_finished()` 的顺序由 N3 契约守卫钉住。
- 三条回归用例分层合理（watcher 行为 / 端到端立即退出 / reader 末尾契约），D1 的 skipif 补齐避免了 POSIX leg 的「常绿无效守卫」，D2 为 pyright strict 零诊断改形态而不改断言；方案 §12.3 的 D1-D4 偏离均附实测依据、如实上报 43 例与 781 行差异。
