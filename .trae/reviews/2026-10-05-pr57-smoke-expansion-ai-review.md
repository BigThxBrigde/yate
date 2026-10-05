# Gitee PR #57 AI 队友评审 — 冒烟扩充 — 2026-10-05

> 来源：[PR !57 `docs(smoke): backfill the expansion results and the scenario traps`](https://gitee.com/jermaine/yate/pulls/57#note_51450178_conversation_191412657)
> note 51450178 / conversation 191412657（评审者：`pull_review_bot_2f642dd39f557e6f`
> 「PR观察者」，2026-10-05 21:46:56）。原始评论另经
> `https://gitee.com/api/v5/repos/jermaine/yate/pulls/57/comments` 取回核对
> （页面本身不展开评论正文，只有 API 能拿到全文）。
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
