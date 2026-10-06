# PR !59 评审修复计划（pack wiki 进度刷新分支）

> **来源记录**（`doc-conventions.md` §二.2 要求记录 ↔ 方案互链）：
> [2026-10-06-pr59-pack-wiki-refresh-ai-review.md](../reviews/2026-10-06-pr59-pack-wiki-refresh-ai-review.md)
> —— 本轮 1 阻断 + 3 改进的原文摘要、取证与逐条裁决登记在该记录中。
>
> 分支：`fix/pack-wiki-progress-refresh`（worktree：仓库同级目录 `../yate-pack-wiki-progress`，
> 复用既有 worktree 与其 `.venv`，未新建）
> PR：[!59](https://gitee.com/jermaine/yate/pulls/59)，评论
> [`note_51456136`](https://gitee.com/jermaine/yate/pulls/59#note_51456136_conversation_191435254)
> Issue：<https://gitee.com/jermaine/yate/issues/IKJPEK>
> 状态：**已实施并门禁通过（待回填真实数字）**
>
> 批准方式：用户于 2026-10-06 明确要求「无人值守、bypass 所有权限」，按
> `.trae/rules/yate-rules.md` §二 第 5 条，方案批准与步骤确认一律按通过处理。

## 一、目标与非目标

**目标**

1. 处置 PR !59 评审的 3 个改进项（可维护性），每项配可执行的守护；
2. 对 1 个阻断项给出**可复现的裁决**（修 / 不修 + 依据），并把评审同时提出的
   测试缺口补上；
3. 门禁（pyright + 全量 pytest + 架构测试 + 覆盖率 ≥ 75）由主代理亲自跑通。

**非目标**

- 不改并行度、`BATCH_SIZE`、`--jobs` 语义与页面收集/写盘逻辑；
- 不动 `README` / 中英手册（本轮无契约变化；I3 只改代码注释）；
- 不合并不推送（`task-orchestration.md` §二：闭环内禁止 `git push`）。

## 二、发现 → 处置（逐条裁决）

| # | 级别 | 位置 | 评审所述问题 | 裁决 | 改动 |
|---|---|---|---|---|---|
| B1 | ⛔ | `_run_translate` 轮询 | 反复 `communicate(timeout=)` 导致第二次起不再读管道，输出变 `(None, None)`，成功翻译被误报失败 | ❌ **不改实现（误报）**：CPython 3.13.2 `communicate` 无该短路分支；慢速子进程探针（1 s + 200 KB 输出 + 4 次超时）输出完整 | ✅ **采纳其测试建议**：新增慢速真实子进程用例，把"跨多个轮询间隔的输出必须一字不差"钉住 |
| I1 | ⚠️ | `_terminate` | `proc.wait()` 无超时，子进程不可中断时 worker 悬挂 | ✅ 修 | 新增 `_TERMINATE_WAIT_S = 5.0`，`wait(timeout=...)` + `TimeoutExpired` 告警；`_FakeProc.wait` 补 `timeout` 形参；新增抗 kill 用例 |
| I2 | ⚠️ | `_translate_pending` 入口排空 | `console.print(message, markup=False)` 漏 `highlight=False`，与 `finally` 处渲染不一致 | ✅ 修 | 补 `highlight=False`；新增 AST 守护，要求两处 drain 的 `console.print` 都带该参数 |
| I3 | ⚠️ | `_run_translate.finally` | 注释承诺 "Never let the writer outlive the call"，`join(timeout=…)` 超时后静默放弃 | ✅ 修（只改注释） | 注释改为如实描述"最多等一个轮询间隔，之后交给 daemon 线程自行退出"，并说明管道已交接、线程不会再触碰进程对象 |

## 三、备选方案与否决理由

| 方案 | 结论 | 理由 |
|---|---|---|
| **A. 保持轮询实现 + 补慢速钉桩用例**（B1 选定） | ✅ 采纳 | 取证显示现实现正确；改动面最小，且把"解释器若真的短路返回"变成可被套件捕获的变化 |
| B. 按评审建议把 `communicate()` 移入独立读线程、主线程 `join(timeout)` 轮询 | ❌ 否决 | 多一个线程与一层结果转发；`_stage_stop_requested()` / 超时预算的判定逻辑要重写，而被"修复"的缺陷并不存在；且现有用例（stage 收尾 kill 自己的子进程）已覆盖这条链路的可达行为 |
| C. B1 照单全收改实现，同时保留轮询 | ❌ 否决 | 同 B；无缺陷的"修复"会让已验证的取消语义重新承风险 |
| I1 备选：把 `_terminate` 整体挪到 daemon 线程（对齐 `pty_proc`） | ❌ 否决 | `wait` 已可 kill 后的有界等待；再引入线程会让"子进程已回收"变成不确定状态，且本模块明确以"只有主/worker 线程做终止"为前提 |

## 四、分步实施与验收命令

| 步 | 改动文件 | 输出 | 验收命令（worktree 内执行，解释器 `.venv\Scripts\python.exe`） |
|---|---|---|---|
| 1 | `tools/pack/wiki.py`（`_terminate` / 入口 drain / `feeder.join` 注释）、`tests/test_pack_wiki_errors.py`（3 处） | 三项改进落地 + 守护 | `.venv\Scripts\python.exe -m pytest tests/test_pack_wiki_errors.py tests/test_pack_wiki_parallel.py tests/test_pack_wiki.py -o addopts= -q` |
| 2 | 同上（无新增改动，仅复核） | — | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` |
| 3 | 全量门禁 + 架构测试 + 覆盖率 | 真实数字回填 §五 | `.venv\Scripts\python.exe -m pytest tests/ -o addopts= -q --cov=yate --cov-fail-under=75`；`.venv\Scripts\python.exe -m pytest tests/test_architecture.py -o addopts= -q` |

## 五、执行与门禁记录（收尾回填）

- 待回填：提交号、pytest 通过数、pyright 退出码、覆盖率、架构用例数。
- 偏离记录：待回填。

## 六、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `_terminate` 超时后子进程未被回收（极小概率） | 告警行让用户知情；`TRANSLATE_TIMEOUT_S` 路径本就已在报错 | 还原 `proc.wait()` 一行 |
| 慢速钉桩用例依赖真实子进程，CI 上偶发慢 | 子进程只 `sleep` 0.6 s，断言不含耗时上界；失败即说明管道行为变化 | 删除该用例（保留记录） |
| I1 改动波及既有 fake 桩（`wait()` 签名） | `_FakeProc.wait` 加默认值形参，向后兼容 | 还原签名 |

## 七、与后续工作的衔接

- 本分支的 reviews 索引编号与 master 存在一条分歧（本分支 #31 为 skill 审查轮，
  master 无此行），已在 [README.md](../reviews/README.md) §一 登记；合并回 master
  时按日期重排编号。
- B1 如被机器人复议，回复材料：评审记录 §三（stdlib 源码引用 + 探针输出）。