# Gitee PR #57 AI 队友评审 — 冒烟扩充 — 2026-10-05

> 来源：[PR !57 `docs(smoke): backfill the expansion results and the scenario traps`](https://gitee.com/jermaine/yate/pulls/57#note_51450178_conversation_191412657)
>
> - **第一轮**：note 51450178 / conversation 191412657，2026-10-05 21:46:56
>   —— ⛔ 1 阻断 + 2 改进（见 §二、§三），**已全部销账**。
> - **第二轮**：note 51450575 / conversation 191414938，2026-10-05 23:14:55
>   —— ⚠️ 0 阻断 + 1 改进（见 §六），**登记待处置**。
>
> 评审者：`pull_review_bot_2f642dd39f557e6f`「PR观察者」。原始评论另经
> `https://gitee.com/api/v5/repos/jermaine/yate/pulls/57/comments` 取回核对
> （页面本身不展开评论正文，只有 API 能拿到全文）。两轮均由用户以
> `@pull_review_bot_… /review` 触发。
>
> 整改方案：[smoke-review-fixes-plan.md](../documents/smoke-review-fixes-plan.md)。
>
> 本文件是**只读事实文档**：只记录发现与核对结论，不放修复排期。

## 一、四维度评审结论（原表照录）

| 评审规则 | 评审内容 | 评审结论 | 完成时间 |
|---|---|---|---|
| 功能性与逻辑 | 代码是否按预期执行？有无逻辑错误或未处理的边缘情况？ | ❌ 未通过 | 2026-10-05 21:46:56 |
| 安全性 | 是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？ | ✅ 通过 | 2026-10-05 21:46:56 |
| 性能 | 是否有明显的性能瓶颈？ | ✅ 通过 | 2026-10-05 21:46:56 |
| 可维护性 | 代码是否清晰易读？注释是否充分？命名是否合理？ | ⚠️ 待优化 | 2026-10-05 21:46:56 |

评审者总评：⛔ 发现 1 个阻断项，2 个改进项，风险等级 medium，影响**正确性**与
**可维护性**；架构设计与隔离策略良好，风险可控。

## 二、阻断项（1）

### B1 `screensaver.py` 中 `rows` 变量被覆盖导致快照丢失

- 分类：功能性与逻辑
- 位置：`tools/smoke_test/scenarios/screensaver.py::_screensaver_disabled_message`
- 评审者判断：第一个 app 的 SVG 快照赋给 `rows` 后，在第二个 app 的运行块中被
  再次赋值覆盖，最终 `ScenarioResult` 只含第二个 app 的快照，第一个 app 的数据
  静默丢失；「若是有意为之应加注释，否则是逻辑缺陷」。

**核对结论：属实。** 原文两行（评审时点）：

- `screensaver.py:149` `rows = snapshot_svg(app, tmp)`（app 1）
- `screensaver.py:169` `rows = snapshot_svg(bad, tmp)`（app 2，随后返回）

第 149 行是**死存储**：既进了 `shot.svg` 又被下一行整体覆盖，磁盘上的 SVG 同样
只剩 app 2 的画面。附带一个同源问题：`harness._run_one` 的不变量扫描只作用于
**最后一个** `new_app`（`harness.py:445` 取 `current_app()`），所以 app 1 实际
**从未被不变量覆盖**。

本仓的补充事实（评审未提）：`snapshot_svg` 固定写同一个 `shot.svg` 路径，所以
"保留两个 app 的快照"在当前实现下**不可回收**——app 1 的行已在 app 2 截图时物理
丢失。评审者给的第二条建议（合并 `svg_rows`）因此不可行：两个屏幕的行按 y 坐标
混在一个 dict 里，既无法区分也毫无视觉意义。

### 处置

拆成两个场景，各自带一个 app：`screensaver_disabled_message`（`enable=False`）与
新增的 `screensaver_bad_roster_message`（角色表全非法）。死存储随之消失，app 1
也重新进入不变量扫描范围。否决的替代路线见方案文档 §三。

## 三、改进项（2）

### M1 `guards.py` 硬编码主题候选数量

- 分类：可维护性
- 位置：`tools/smoke_test/scenarios/guards.py::_prompt_tab_completion`
- 评审者判断：`Check("theme_candidates", 8, ...)` 把断言钉死在与产品配置强耦合的
  固定值上，主题增删即失败，产生与补全逻辑无关的噪音；建议改为从注册表动态取。

**核对结论：属实。** 评审者给出的替换代码用了 `theme.names()`，**该函数不存在**；
本仓真实 API 是 `theme.available()`（`yate/editor_view/theme.py:475`，返回
`sorted(THEMES)`），当前 `len(theme.THEMES) == 8`，故 `8` 这个字面量确实只是
清单快照。

**本仓扩大认定**：同一场景里另有两处同源耦合，评审未点名，属同一缺陷类：

- `Check("first_value", "set theme=frappe", ...)` —— `frappe` 是
  `sorted(THEMES)[0]`，新增一个排序更靠前的主题即失败；
- `Check("theme_applied", "frappe", ...)` —— 上一条的派生断言。

三处一起改成从 `theme.available()` 派生，断言对象回到"补全行为"而非"清单内容"。

### 处置

三处断言改为由 `theme.available()` 派生（见方案 §五 步骤 2）。

### M2 `workspace_nav.py` 循环上限 `12` 是魔法数字

- 分类：可维护性
- 位置：`tools/smoke_test/scenarios/workspace_nav.py::_pane_resize_chords`
- 评审者判断：`for _ in range(12)` 缺乏解释，与窗格最小尺寸比例、resize 步长的
  关系不明确；步长或最小比例一旦调整就可能触发不到告警，产生**假阴性**；建议
  提取为带注释的命名常量并说明计算依据。

**核对结论：属实，且假阴性风险已可量化。** 产品常量为
`MIN_FRACTION = 0.12`、`RESIZE_STEP = 0.08`（`yate/session.py`），从均分
`0.5` 收到下限需要 `ceil((0.5 - 0.12) / 0.08) = 5` 次；`12` 是它的近两倍多余量。
多余量本身不产生假阴性（只会多重按几次、按到下限后告警文本不变即 break），
但它把"够不够"的判据藏进了字面量里。

### 处置

改为由 `MIN_FRACTION` / `RESIZE_STEP` **推导**的命名常量并注明推导式
（见方案 §五 步骤 3）。

## 四、评审未覆盖但本轮核到的事实

- 评审称"26 项检查"、PR 列表 5 个提交，均为评审时点快照；评审窗口内本地又推进到
  9 个提交（`2ba17c5`…`5b93a4c`），`origin/enh/smoke-test-scenarios` 与本地同步
  （`git rev-list --count origin/..HEAD` = 0）。B1 / M1 / M2 三项在最新 HEAD 上
  仍全部成立，逐条按最新代码行号复核过。
- 评审的正面评价（架构设计与隔离策略良好）与本仓实测一致：真 shell / 真 PTY 场景
  标 `slow` 交给 `--skip-slow`，终端交互走 `_FakePty` 注入 `view_factory`。

## 五、状态

| 编号 | 摘要 | 分类 | 状态 |
|---|---|---|---|
| B1 | `screensaver.py` 两 app 共用 `rows`，第一个 app 快照死存储且逃过不变量扫描 | 阻断 | ✅ 已修（`c7099d0`：拆为 `screensaver_disabled_message` + `screensaver_bad_roster_message`，各一个 app、各一次 `snapshot_svg`） |
| M1 | `guards.py` 主题候选数量（及两处派生主题名）硬编码 | 改进 | ✅ 已修（`77475d8`：三处期望值改由 `theme.available()` 派生；`theme.names()` 不存在，评审建议的 API 已替换） |
| M2 | `workspace_nav.py` 循环上限 `12` 为魔法数字 | 改进 | ✅ 已修（`6a95fd8`：改为 `ceil((0.5 - MIN_FRACTION) / RESIZE_STEP) + 2`，实测 7；第 6 次按键才触发告警，余量 2 次是刻意的） |

### 销账实测（2026-10-05，HEAD `f9da8d1`）

| 门禁 | 结果 |
|---|---|
| 受影响 5 场景 | 77/77 checks，5/5 场景 PASS，exit 0（成员各自三轮一致，主代理再复核一轮） |
| 全量冒烟 | **104/104 场景、1252/1252 checks**，exit 0 |
| 覆盖率 | `commands 45/45`、`actions 66/66`（均为 100%，拆分未影响） |
| 基线 | 新增 `screensaver_bad_roster_message.json`；`screensaver_disabled_message.json` 减 3 条检查；`prompt_tab_completion.json` 与 `pane_resize_chords.json` **零 diff**（方案 §五 步骤 4 的对账要求达成） |
| `compare` | 全 MATCH，exit 0 |
| pyright strict | `yate/ tests/ tools/` 0 errors |
| pytest | 1875 passed / 8 skipped，exit 0；覆盖率 **91.27%**（门禁 75%） |
| 架构测试 | 22 passed，exit 0 |

> 耗时口径说明：同一份代码在两次全量运行中分别耗时 153s 与 94s、`pytest` 分别为
> 497s 与 264s，波动来自本机负载（整改期间三个子代理并行占用 CPU）。**场景数与
> 检查数是可靠口径，耗时只作参考**，本条不据此判断性能回归。

整改方案与逐处落点：[smoke-review-fixes-plan.md](../documents/smoke-review-fixes-plan.md)。

## 六、第二轮评审（note 51450575，2026-10-05 23:14:55）

触发：用户在 23:10:35 以 `@pull_review_bot_… /review` 再次唤起。评审时点为本轮
整改合入之后（`99ee498` 合并 master、场景数 104）。

### 6.1 四维度评审结论（原表照录）

| 评审规则 | 评审内容 | 评审结论 | 完成时间 |
|---|---|---|---|
| 功能性与逻辑 | 代码是否按预期执行？有无逻辑错误或未处理的边缘情况？ | ✅ 通过 | 2026-10-05 23:14:55 |
| 安全性 | 是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？ | ✅ 通过 | 2026-10-05 23:14:55 |
| 性能 | 是否有明显的性能瓶颈？ | ✅ 通过 | 2026-10-05 23:14:55 |
| 可维护性 | 代码是否清晰易读？注释是否充分？命名是否合理？ | ⚠️ 待优化 | 2026-10-05 23:14:55 |

总评：⚠️ **无阻断项，1 个改进建议，可优化后合并**；风险等级 **low**。评审者对
改动面的归纳：新增 5 个场景模块（场景 89 → 104）、命令与动作覆盖补到
`45/45` 与 `66/66`、新增 3 个 harness 单测文件、上一轮三项已修、基线与文档同步。

### 6.2 改进项 M3：CLI 测试的全局状态隔离与 harness 单测不对称

- 分类：可维护性
- 位置：`tests/test_smoke_cli.py`（关联 `tests/test_smoke_harness.py`）
- 评审者判断：`test_smoke_harness.py` 用 autouse fixture 保护全局状态，而
  `test_smoke_cli.py` 调用 `main()` 真跑场景时没有同等保护；若场景改动全局随机
  种子或主题，会污染后续测试，造成顺序相关或偶发失败。建议补上同样的恢复
  fixture，或确认被调场景绝无全局副作用。

**核对结论：不对称属实，但性质是"潜在"而非"现症"，且评审对 fixture 的描述有误。**

逐条核实（只读取证）：

1. **不对称确实存在**：`tests/test_smoke_cli.py` 全文**没有任何 fixture**（连
   非 autouse 的也没有），而它有三处调用 `main()`。其中两处（`:167` 的 tag 与
   场景名不匹配、`:177` 的基线目录不存在）都在 `cmd_run` / `cmd_compare` 的
   `return 2` 早退分支里，**根本不会执行场景**；真正跑场景的只有 `:184` 一处
   （`main(["run", "--scenario", "keymap_toggle", "--quiet", "--no-color"])`）。
2. **评审对 fixture 的描述不准确**：`test_smoke_harness.py` 只有**一个** autouse
   fixture——`restore_fuzz_seed`（`:52`）；`restore_theme`（`:61`）**不是**
   autouse，而是被两个用例按需显式请求的参数化 fixture
   （`test_note_registries_*`，`:136` / `:148`）。评审把两者都称作 autouse。
3. **当前没有被污染的证据**：唯一真跑的场景是 `keymap_toggle`（core.py），它
   两次切换键位后回到 `vsc`（自复原）；CLI 未传 `--seed`，而 `cmd_run` 仅在
   `args.seed is not None` 时才调 `set_seed`，全局种子不变；主题则由 harness 的
   `invariant:theme_restored` 校验、并由 `_run_one` 收尾强制复原
   （`harness.py:445-453`）。三条路径都不依赖测试侧的 fixture 兜底。
4. **风险是潜在的**：若日后该模块新增一个会切主题或调 `set_seed` 的场景，隔离
   缺失就会变成真实的顺序依赖；本轮不修等于把这条约束只留在口头。

**处置：登记待处置，本轮按用户指令只登记不改。** 若后续修，评审自己给出的两条
路径里，**从另一个测试模块 import fixture**（`from tests.test_smoke_harness
import restore_fuzz_seed, restore_theme`）有测试模块耦合与重复收集风险
（评审也已自行标注）；更稳妥的是把两个恢复 fixture 提到 `tests/conftest.py`
或专用测试辅助模块，由两者共用。

### 6.3 评审自身的三处数字／描述偏差（照实记录）

| 评审表述 | 实测 |
|---|---|
| "使用了 autouse 的 `restore_fuzz_seed` 和 `restore_theme` Fixture" | 只有 `restore_fuzz_seed` 是 autouse；`restore_theme` 是按需 fixture（见 6.2 第 2 点） |
| "14 个新场景的 JSON 基线文件" | 相对 master 实测 **15 个**基线文件，且**全部为新增（`A`）、无修改**（`git diff --name-status master...HEAD` 计数） |
| 场景总数 89 → 104 | ✅ 与实测一致（+15：扩充 14 + 拆屏保场景净增 1） |

### 6.4 状态

| 编号 | 摘要 | 分类 | 状态 |
|---|---|---|---|
| M3 | `tests/test_smoke_cli.py` 缺全局状态隔离，与 `test_smoke_harness.py` 不对称 | 改进 | 👀 登记待处置（2026-10-05；潜在风险非现症，0 阻断，可合并） |

### 6.5 轮次小结

| 轮次 | 结论 | 阻断 / 改进 | 处置 |
|---|---|---|---|
| 第一轮（21:46:56） | ⛔ 未通过 | 1 阻断 / 2 改进 | ✅ 已全修（`c7099d0` / `77475d8` / `6a95fd8`） |
| 第二轮（23:14:55） | ⚠️ 无阻断，可优化后合并 | 0 阻断 / 1 改进 | 👀 登记待处置（M3，见 §6.2 的稳妥修法建议） |
