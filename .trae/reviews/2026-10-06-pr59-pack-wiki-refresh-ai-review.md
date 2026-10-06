# Gitee PR !59 AI 队友评审记录（pack wiki 进度刷新，2026-10-06）

> **本文是只读事实文档**：只记录发现与核对结论（含实测证据），不含修复排期。
> 修复方案见
> [pr59-pack-wiki-refresh-review-fixes-plan.md](../documents/pr59-pack-wiki-refresh-review-fixes-plan.md)；
> 同分支前序（skill 六维度六轮）记录见
> [2026-10-06-pack-wiki-progress-skill-review.md](2026-10-06-pack-wiki-progress-skill-review.md)。

- **对象**：[Gitee PR !59](https://gitee.com/jermaine/yate/pulls/59)
  （`master` → `fix/pack-wiki-progress-refresh`，issue **IKJPEK**，30 文件），
  评论 [`note_51456136`](https://gitee.com/jermaine/yate/pulls/59#note_51456136_conversation_191435254)
  conversation 191435254（作者 `PR观察者` / `pull_review_bot_...`，2026-10-06 16:04:19 +08:00，
  末次更新 16:17:27）。
- **取回方式**：Gitee API `repos/jermaine/yate/pulls/59/comments`（页面本身不展开评论正文，
  抓取页面只能拿到概要；与 PR !57 轮同一做法）。评论为 `pr_comment`，未给行号，
  位置信息取自其代码片段本身。
- **触发**：用户在 PR !59 下发 `@pull_review_bot /review`（`note_51456134`）。

## 一、评审自评结论（原样登记）

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ❌ 未通过 |
| 安全性 | ✅ 通过 |
| 性能 | ✅ 通过 |
| 可维护性 | ⚠️ 待优化 |

AI 队友结论：**⛔ 1 个阻断项 + 3 个改进项**，风险等级 `high`，理由是"并行翻译真实场景下
单页耗时远超 0.2 s，输出会被误判为丢失"。

## 二、本轮四项发现与本仓库核对结论

| # | 级别 | 位置 | 评审所述问题 | 本仓库核对 | 处置 |
|---|---|---|---|---|---|
| B1 | ⛔ 阻断 | `tools/pack/wiki.py` `_run_translate` 轮询 | 轮询反复调用 `proc.communicate(timeout=...)`，首次超时后 `_communication_started` 已置位，后续调用走"只等待、不读管道"分支，`output` 变 `(None, None)`，成功翻译被误报 `error[WIKI-0201]` | ❌ **误报**：机制描述与 CPython 实现不符，且在真实子进程上无法复现（§三 取证） | 不改轮询实现；**采纳其测试建议**，新增慢速真实子进程用例把该行为钉住（§四） |
| I1 | ⚠️ 改进 | `_terminate` | `proc.wait()` 无超时兜底，子进程不可中断时 worker 永久悬挂，抵消退出延迟治理的收益 | ✅ 属实：与仓库既有约定不一致（`yate/editor_term/pty_proc.py` 对 `wait` 加了超时） | ✅ 已修（新增 `_TERMINATE_WAIT_S` + 超时告警 + 用例） |
| I2 | ⚠️ 改进 | `_translate_pending` 入口排空 | 入口处 `console.print(message, markup=False)` 漏 `highlight=False`，与 `finally` 处渲染不一致（R-22 的不变量在第二处被打破） | ✅ 属实：`wiki.py` 两处 drain，一处带 `highlight=False`、一处不带 | ✅ 已修（一处补齐 + AST 结构性守护） |
| I3 | ⚠️ 改进 | `_run_translate.finally` | 注释声称 "Never let the writer outlive the call"，但 `feeder.join(timeout=_STOP_POLL_S)` 超时后静默放弃，注释与行为不符，最坏每页多 0.2 s | ✅ 属实（注释确实承诺了做不到的事） | ✅ 已修（注释改为如实描述；不额外改管道所有权，避免与 R-29 的交接语义冲突） |

结论：**0 阻断（1 项误报）/ 3 改进已修**。

## 三、B1 的取证（评审结论不成立）

### 3.1 评审所述机制与 CPython 实现不符

评审称"后续再次调用会走 `_try_wait` 分支，直接返回 `(None, None)` 而不再读取管道"。
实测本仓库解释器（`python --version` → `CPython 3.13.2`，`requires-python = ">=3.12"`）
的 `subprocess.Popen.communicate` 源码中**不存在**该分支：超时只是让
`finally: self._communication_started = True` 提前生效，读取线程与
`_stdout_buffer` / `_stderr_buffer` 全部保留；下一次带 timeout 的调用重新进入
`_communicate`，**再次 join 读取线程并从缓冲区取值**（Windows 实现：
`_readerthread` 首次启动后不再重建 → `join(remaining)` → `_stdout_buffer.getvalue()`）。

### 3.2 真实子进程复现尝试：输出完整

一次性探针 `_probe_comm.py`（已删除）完全复刻评审描述的场景——子进程
**睡 1.0 s**（远超 `_STOP_POLL_S = 0.2`）后才回 200 KB 答案，父进程先喂 100 KB
stdin 再以 0.2 s 超时轮询：

```text
timeout #1 … timeout #4            （4 次轮询超时，_communication_started=True）
poll timeouts: 4
stdout len: 200006   repr head: '# en\nxxxxx'
stderr: ''      returncode: 0
verdict: OK, output intact
```

即：慢速 + 大输出 + 多次超时，`stdout` **一字不差**。探针同时证明 stdin 侧
（writer 线程交接）没有截断。

### 3.3 采纳的部分

评审对**测试**的批评成立：既有真实子进程用例要么即时返回、要么只有一页，未覆盖
"单页耗时远超轮询间隔且有输出"。该缺口由新增用例补上（`tests/test_pack_wiki_errors.py`，
见 §四），这样即便将来某个解释器版本真的改成短路返回，套件会立刻变红。

### 3.4 取证范围声明（如实登记）

- 3.13.2 已本地实测（上表）；**CPython 3.12 的 `subprocess.py` 原文未取到**
  （两次 `web_fetch` 均 10 s 超时），故 3.12 未单独取证——但本仓库门禁与 CI 实际
  解释器为 3.13.2，结论对本仓库生效。
- 未在真实 TTY 下目验（本会话无人值守），但本条不涉及终端渲染。

## 四、改动与门禁实测

### 4.1 改动

| 项 | 内容 |
|---|---|
| 代码 | `tools/pack/wiki.py`：`_terminate` 改为**返回**"kill 未生效"的注记（不再由 worker 直接写终端），等待带预算 `_TERMINATE_WAIT_S`；超时失败消息内联该注记；入口排空补 `highlight=False`；`feeder.join` 注释改为如实描述 |
| 测试 | `tests/test_pack_wiki_errors.py`：慢速大输出真实子进程用例（B1 钉桩）、抗 kill 用例（I1）、两处 drain 渲染参数一致性 AST 守护（I2）；`tests/test_pack_wiki_parallel.py`：两个进程桩接受并记录 `wait` 预算，torn-down-stage 用例断言预算被使用 |
| 提交 | `6f036cd`（首版修复）→ `23f536a`（评审后修正，见 §4.3） |

### 4.2 门禁（worktree 内实测，解释器 `.venv\Scripts\python.exe`）

| 命令 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | **0 errors, 0 warnings, 0 informations** |
| `pytest tests/ -o addopts= -q --cov=yate --cov-fail-under=75` | **1950 passed, 9 skipped** in 456 s；覆盖率 **91.25%**（阈值 75%） |
| `pytest tests/test_architecture.py -o addopts= -q` | **22 passed** |
| `pytest`（wiki 四文件） | **106 passed, 1 skipped**（`skipif win32` 的 `[/x]` 用例） |

变异测试（回退修复 → 目标守护变红 → 还原）：

| 变异 | 目标用例 | 结果 |
|---|---|---|
| M1：`proc.wait()` 去掉 timeout 预算 | `test_a_child_that_ignores_the_kill_is_announced_not_waited_on` + `test_a_torn_down_stage_kills_the_child_its_worker_is_waiting_for` | ✅ 两条同时变红 |
| M2：入口排空去掉 `highlight=False` | `test_every_drained_failure_is_rendered_the_same_way` | ✅ 变红（报出缺失的关键字参数） |

### 4.3 首版修复被自查打回（记录留痕）

首版（`6f036cd`）把"kill 未生效"直接 `print` 到 stderr，并由独立评审轮发现三处问题，
已在 `23f536a` 修掉：

1. **静默回归（最严重）**：`tests/test_pack_wiki_parallel.py` 的两个进程桩仍是
   `wait(self)`，worker 收尾因此抛 `TypeError` 而非 `KeyboardInterrupt`；主线程此时
   已离开线程池，异常被吞，**全量套件照样全绿**——即首版门禁的"绿"是假的。已给桩补
   预算形参并在 torn-down-stage 用例中断言预算被使用（该路径此前无任何观察者）。
2. **契约违反**：worker 直写 stderr 会插进 rich 的活动重绘区（既有不变式：并行阶段
   只有主线程打印）。改为 `_terminate` 返回注记，由调用方并入该页失败消息。
3. **注释仍不 truthfully**：I3 的注释改写里"detached 后不再触达子进程"是错的——
   那条流就是子进程的 stdin。已改为如实描述（daemon 线程仍持有自己的句柄）。

> 教训留档：**"桩未同步 + 异常被池吞"能骗过全量套件**，因此跨文件改签名时必须同步
> 搜索全部桩，并给"主线程已离开"的路径补显式断言。

## 五、遗留与限制

- **3.12 未取证**：见 §3.4；若后续需要，可在有网环境下补一次源码比对。
- **真实 TTY 目验缺位**：沿用前序记录的限制，无人值守会话无法投递 SIGINT 目验。
- B1 按"误报 + 补测试"记账，**不作为已修缺陷**；若 PR 机器人复议，引用 §3.1/§3.2
  的实测数据回复。
- **O-1（本轮评审轮新发现，存量问题，超出本轮范围）**：`--translate-cmd` 走
  `shell=True`，`kill()` 杀的是 shell 本身，POSIX 下真正的翻译器是孙进程，会成为
  孤儿继续持有 stdin（父进程退出后写入即 BrokenPipe 而已，但子进程确实活过
  `_terminate` 的回收窗口）。要真正解决需要进程组（`start_new_session=True` /
  `os.killpg`）或 Windows Job Object，属选型变更，另案登记。
- **O-2（存量）**：抗 kill 场景下 `_feed_stdin` 的 daemon 线程可能仍阻塞在
  `stream.write`，最多每页泄漏一个线程与一个句柄，随进程退出而消亡；同理超时未被
  回收的子进程会让 `Popen.__del__` 报 `ResourceWarning`（`pyproject.toml` 只把
  `RuntimeWarning` 设为 error，故不炸）。
- **O-3（存量，非本轮引入）**：`_emit_translate_failure` 的 docstring 声称
  "两条路径输出同样的纯文本"，但 rich 路线会按 `Console.width` 折行，长失败消息
  （会内嵌子进程 stderr 全文）在两条路线上的终端形态并不完全一致；本轮的 AST 守护
  只保证 rich-vs-rich 一致。