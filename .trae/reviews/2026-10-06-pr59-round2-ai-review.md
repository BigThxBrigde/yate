# Gitee PR !59 AI 队友评审记录（第二轮，pack wiki 进度刷新，2026-10-06）

> **本文是只读事实文档**：只记录发现与核对结论，不含修复排期。
>
> - **本文是第二轮**：同一 PR 的第一轮（note 51456136，⛔ 1 阻断 + 3 改进）记录见
>   [2026-10-06-pr59-pack-wiki-refresh-ai-review.md](2026-10-06-pr59-pack-wiki-refresh-ai-review.md)，
>   其整改方案见
>   [pr59-pack-wiki-refresh-review-fixes-plan.md](../documents/pr59-pack-wiki-refresh-review-fixes-plan.md)。
>   第一轮 3 项改进已修（`6f036cd` + `23f536a`）、阻断项经实测判为误报，**本轮评审未再提出该阻断**。
> - **本轮按用户指令只登记、不修复**：三项发现均为 ⚠️ 改进、0 阻断，按指令未产出整改方案
>   文档（`doc-conventions.md` §二.2 的"评审发现需要修复时"不适用），处置排期另案。
> - 同分支前序（skill 六维度六轮）记录见
>   [2026-10-06-pack-wiki-progress-skill-review.md](2026-10-06-pack-wiki-progress-skill-review.md)。

- **对象**：[Gitee PR !59](https://gitee.com/jermaine/yate/pulls/59)
  （`master` → `fix/pack-wiki-progress-refresh`，issue **IKJPEK**），评论
  [`note_51457690`](https://gitee.com/jermaine/yate/pulls/59#note_51457690_conversation_191441088)
  conversation 191441088（作者 `PR观察者` / `pull_review_bot_2f642dd39f557e6f`，
  2026-10-06 19:10:43 +08:00，末次更新 19:17:42，正文 2886 字符）。
- **取回方式**：Gitee API `repos/jermaine/yate/pulls/59/comments`（页面本身不展开评论正文，
  抓取页面只能拿到概要；与第一轮、PR !57 轮同一做法）。评论为 `pr_comment`，未给行号，
  位置信息取自其代码片段本身。
- **触发**：用户在 PR !59 下发 `@pull_review_bot /review`（`note_51457689`，19:10:41）。

## 一、评审自评结论（原样登记）

| 评审规则 | 结论 | 完成时间 |
|---|---|---|
| 功能性与逻辑 | ⚠️ 待优化 | 2026-10-06 19:17:42 |
| 安全性 | ✅ 通过 | 2026-10-06 19:17:42 |
| 性能 | ✅ 通过 | 2026-10-06 19:17:42 |
| 可维护性 | ⚠️ 待优化 | 2026-10-06 19:17:42 |

AI 队友结论：**⚠️ 0 个阻断项 + 3 个改进建议，可优化后合并**，风险等级 `low`。其风险面
表述为"三项均属中等优先级，不影响正确性"，并给出正面评价：改动解决了 issue 的两个核心问题
（进度条逐页实时刷新、Ctrl+C 治理），附带修掉多项存量缺陷，"整体 PR 代码质量高，测试覆盖
充分，已知限制均有明确登记和接受"。

评审自评与本仓实测的一致性：第一轮三项改进（`_terminate` 有界等待、入口排空
`highlight=False`、`feeder.join` 注释）在最新 HEAD `a1ac803` 上均已落地，**本轮未再出现**，
即机器人对第一轮的整改无异议。

## 二、三项发现与本仓库核对结论

| # | 级别 | 位置 | 评审所述问题 | 本仓库核对 | 处置 |
|---|---|---|---|---|---|
| M1 | ⚠️ 改进（功能性） | `tools/pack/wiki.py` `_run_translate` | stage stop 触发的 `KeyboardInterrupt` 走 `except BaseException: _terminate(proc); raise`，`_terminate` 返回的抗杀注记被丢弃；超时路径却会把它拼进失败消息 | ✅ **属实**（§三.1）；但评审给出的两条修法各有约束，其一与已登记的 R-05 语义冲突 | 👀 登记待处置（修法需另案裁决，§三.1） |
| M2 | ⚠️ 改进（可维护性） | `tests/test_pack_wiki_errors.py` | 两条 AST 结构性守护钉死标识符（`_emit_mode` / `"collect"` / `start` / `_drain_collected_failures`），等价重构会误报 | ✅ **属实**（§三.2）；"加注释" 部分已由现有 docstring 覆盖，缺的是"重构须同步"告警；"改行为测试" 与该用例自身给出的论证相左 | 👀 登记待处置 |
| M3 | ⚠️ 改进（可维护性） | `tests/test_pack_wiki_errors.py`、`tests/test_pack_wiki_parallel.py` | `import io` 与 `from io import StringIO` 并存，风格不一致 | ✅ **属实，且为全仓孤例**（§三.3） | 👀 登记待处置（纯风格，零行为影响） |

结论：**0 阻断 / 3 改进，登记待处置**。三项均无功能性缺陷，不影响合并。

## 三、逐条取证

### 3.1 M1：抗杀注记在 `KeyboardInterrupt` 路径被丢弃（属实，但修法有约束）

**现象核对（`tools/pack/wiki.py`）**

- 超时路径把注记交给用户看：`wiki.py:665-667`
  `except subprocess.TimeoutExpired:` → `leftover = _terminate(proc)` →
  `detail = f" ({leftover})"`，并拼进 `error[WIKI_TRANSLATE_TIMEOUT]` 消息。
- 中断路径直接丢弃：`wiki.py:672-674`
  `except BaseException:` → `_terminate(proc)`（**返回值未赋值**）→ `raise`。

即两条路径对同一个 `_terminate` 返回值的处理确实不一致，评审所述现象属实。

**为什么不能照评审建议直接改**

评审给出两条修法，逐条核对后均有约束：

1. **"把返回值附加到异常信息"**：该分支的语义是 `raise`（重新抛出，通常是
   `KeyboardInterrupt`）。改写异常消息会替换掉中断异常的原始类型/消息，而中断路径的
   首要职责是把控制权交回取消通道（`KeyboardInterrupt` 必须原样传播），不是携带诊断。
2. **"通过 `_emit_translate_failure` 记录一行提示（应走队列）"**：与已登记的 **R-05**
   语义冲突。R-05 的第二轮修复（`test_a_failure_reported_after_the_drain_still_reaches_the_terminal`，
   `tests/test_pack_wiki_errors.py:869`）确立的不变式是：**主线程排空队列并把策略恢复为
   serial 之后才到达的 worker 消息必须直接打印**——因为此时已无人读队列。若在中断路径
   按评审建议"应走队列"入队，而 `_emit_mode` 仍是 `collect`、主线程又已 drain 完毕，
   就恰好复现 R-05 修复前"消息滞留丢失"的缺陷形态。评审自身也在这条建议里提示了
   "需注意此时 `_emit_mode` 可能仍为 collect"，即承认通道存在竞态，但未给出解法。
3. 还有一条通道约束：第一轮整改已把"kill 未生效"从 **worker 直写 stderr** 改为
   **返回注记由调用方并入消息**，原因正是 worker 直写会插进 rich 的活动重绘区
   （既有不变式：并行阶段只有主线程打印，见第一轮记录 §4.3 第 2 点）。因此在
   `except BaseException` 里新增任何 worker 侧输出，都会与那条已付过代价的决策冲突。

**登记的处置口径**：现象属实；评审的第二备选（"至少在 docstring 中显式说明此路径有意
省略诊断"）是当前唯一无副作用的落点。任何把注记送出该路径的方案都必须先解决
"消息通道在收尾窗口内不可用"这一前提，属另案裁决，本轮按指令只登记。

### 3.2 M2：两条 AST 守护对重构敏感（属实）

**守护钉住的具体标识符**（`tests/test_pack_wiki_errors.py`）：

| 守护 | 钉住的东西 | 位置 |
|---|---|---|
| `test_the_collect_policy_is_installed_inside_the_protected_region` | 函数名 `_translate_pending` | `:796` |
| 同上 | 目标变量名 `_emit_mode` | `:809` |
| 同上 | 字面量 `"collect"` | `:813` |
| 同上 | 方法属性 `start` | `:820` |
| `test_every_drained_failure_is_rendered_the_same_way` | 函数名 `_drain_collected_failures`、**出现次数恰为 2** | `:848`、`:850` |
| 同上 | 方法属性 `print` + 关键字集合须含 `{"markup", "highlight"}` | `:858`、`:863` |

评审所述"任何等价重构都会误报"由此可验证为真：把 collect 策略收进 context manager、
重命名 `_emit_mode`、或把 display 启动包进工厂方法，都会让守护在行为完全正确时变红。

**对两条建议的核对**

- **"加显著注释标明重构须同步"**：两条用例的 docstring 已记录来源与理由
  （`:781-789` 引 review R-21、`:831-838` 引 review I2/R-22），但确实**没有**一句
  "若重构改变上述标识符须同步更新本守护"的告警。建议中的这部分尚未覆盖。
- **"优先用行为测试替代 AST 检查"**：与该用例自身写下的论证相左——`R-21` 是**结构性**
  缺陷（collect 策略装在 `try` 外，setup 异常后无人读队列），行为测试无法在结构已正确时
  诱发它。评审自己承认"AST 守护有其存在理由"，只是要求"维护成本意识"。
  另需如实指出：与之配套的行为用例
  `test_a_failing_pool_setup_does_not_strand_the_collect_policy`（`:749`）虽走行为路径，
  断言仍经 `getattr(wiki, "_emit_mode")` / `wiki._COLLECTED_FAILURES` **按名字取属性**，
  重命名同样会让它变红——即"名称耦合"在本仓是成片存在的，不只这两条 AST 守护。

### 3.3 M3：`io` 导入双形态并存（属实，且为全仓孤例）

- `tests/test_pack_wiki_errors.py`：`:19` `import io`、`:26` `from io import StringIO`；
  用法 `io.StringIO()`（`:291`）与裸 `StringIO()`（`:727`）并存。
- `tests/test_pack_wiki_parallel.py`：`:19` `import io`、`:27` `from io import StringIO`；
  `io.StringIO()`（`:417`、`:630`）与裸 `StringIO()`（`:539` 注解、`:711`、`:768`、
  `:813`、`:885`）并存。

**全仓基线（`tests/*.py` 逐文件扫描，两种形态各计一次）**

| 形态 | 文件 |
|---|---|
| 仅 `import io` | `test_crash.py`、`test_diagnostics.py`、`test_tools_translate.py`、`test_user_setup.py` |
| 仅 `from io import StringIO` | `test_smoke_tool.py` |
| **两种并存** | **仅本 PR 的 `test_pack_wiki_errors.py` 与 `test_pack_wiki_parallel.py`** |

`tools/` 侧无一处使用 `StringIO`。即评审的定性成立，且比它说的更窄：全仓两种形态**并存**
的情况只有这两个文件，其余各取一种。

**分级说明**：`python-coding-style.md` §1.3 只约束导入**分组**（标准库 → 第三方 → 项目内），
两种写法同属标准库组，故**不构成分组违规**；这是模块内重复导入同一符号的冗余，属 Nit 级
可维护性项，零行为影响。

## 四、状态

| 编号 | 摘要 | 分类 | 状态 |
|---|---|---|---|
| M1 | `KeyboardInterrupt` 路径丢弃 `_terminate` 的抗杀注记（超时路径有、此路径无） | 改进（功能性） | 👀 登记待处置（2026-10-06；现象属实，但评审两条修法分别与 `raise` 语义、R-05 队列语义冲突，安全落点为 docstring 声明，详见 §3.1） |
| M2 | 两条 AST 结构性守护钉死标识符，等价重构会误报 | 改进（可维护性） | 👀 登记待处置（2026-10-06；"加注释" 部分已被现有 docstring 部分覆盖，缺"重构须同步"告警；"改行为测试" 与用例自身论证相左） |
| M3 | 两个测试文件 `import io` 与 `from io import StringIO` 并存 | 改进（可维护性） | 👀 登记待处置（2026-10-06；全仓仅此两处并存，Nit 级，零行为影响） |

## 五、轮次小结

| 轮次 | 结论 | 阻断 / 改进 | 处置 |
|---|---|---|---|
| 第一轮（16:04:19，note 51456136） | ⛔ 未通过 | 1 阻断 / 3 改进 | ✅ 3 改进已修（`6f036cd` / `23f536a`）；阻断经实测判为误报，改以慢速真实子进程用例锁定行为 |
| 第二轮（19:10:43，note 51457690） | ⚠️ 无阻断，可优化后合并 | 0 阻断 / 3 改进 | 👀 3 项登记待处置（本轮按用户指令只登记不修） |

第二轮未再提出第一轮的阻断项，也未对第一轮的三项修复提出异议——**PR !59 的功能性子集已
连续两轮无阻断**。

## 六、遗留与限制（本轮新增）

- **M1 的前提未解**：要在中断路径送出抗杀注记，必须先解决"收尾窗口内 worker 无可用消息
  通道"（R-05 语义）。这不是单点改动，属另案裁决。
- **M2 的耦合面大于评审所述**：名称耦合不只在两条 AST 守护，配套的行为用例也按名字取
  属性；若按建议做"单一来源"重构，需评估的是整个 `tests/test_pack_wiki_*.py` 面。
- **取证范围声明**：本轮核对全部为静态只读取证（`tools/pack/wiki.py`、
  `tests/test_pack_wiki_errors.py`、`tests/test_pack_wiki_parallel.py`、全仓 `tests/*.py`
  导入形态扫描）；**未运行任何测试、未做真 TTY 目验、未复现抗杀场景**（本轮按用户指令
  只登记，不做其他操作）。M1 的两条修法评估基于代码语义推演，未经实测。
- 第一轮登记的存量限制（`shell=True` 杀不到孙进程、daemon 写线程与 `ResourceWarning`、
  rich 折行导致两条渲染通道并非完全一致，见
  [第一轮记录](2026-10-06-pr59-pack-wiki-refresh-ai-review.md) §五 O-1…O-3）本轮未复审，
  状态不变。
