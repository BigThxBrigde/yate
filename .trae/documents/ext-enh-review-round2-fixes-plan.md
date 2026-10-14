# ext-enh-review-round2-fixes-plan.md — 扩展系统增强分支第二轮评审修复方案

> 来源评审记录：[../reviews/2026-10-14-extension-system-enhance.md](../reviews/2026-10-14-extension-system-enhance.md)
> 分支：`enh/extension-system-enhance`（worktree `yate-extension-system-enhance`，HEAD `51ba7a3`）
> 日期：2026-10-14
> 前轮方案：[ext-enh-review-fixes-plan.md](ext-enh-review-fixes-plan.md)（2026-10-13，已闭环）

## 一、目标与非目标

**目标**：修复 2026-10-14 Qwen Code 评审的 2 条 Suggestion + 1 条 Nice to have：

1. `events.py` `report_failure` 回调未防御自身抛异常（emit 的 `except`
   处理器内调用 `_report_failure`，回调抛异常会逃逸并中断剩余监听器）；
2. Lua `yate.ui` 有 `add_segment` 缺 `remove_segment`（teardown 无法经
   同一抽象层清理状态栏段，重载时 bridge 抛重复 id `ValueError`）；
3. `tests/test_architecture.py` docstring "13-name facade" 与实际 14 名不符。

**非目标**：不改 `EventHub` 派发语义与 `UiExtensionBridge` 行为；不改
Python bridge 方法名（`remove_status_segment` 保持不动）；不做 Lua 面之外
的 API 扩展。

## 二、备选方案与否决理由

- **方案 A（采纳）**：按评审建议的最小 diff 逐条修复，全部在既有设计内
  （监听器隔离 + `remove_status_segment` 的 A13 回滚已存在，Lua 包装层补齐
  缺口）。理由：评审结论无 blocker/major；零架构收益的改动不做。
- **方案 B（否决）**：在 `EventHub` 内把 `report_failure` 也纳入通用
  "回调隔离"辅助并复用到监听器与 reporter 两处。理由：两处调用形态不同
  （一个带 payload、一个带文本），抽公共辅助属过度设计。
- **方案 C（否决）**：Lua 端不做 `remove_segment`，仅文档说明降级用
  `api.ui.remove_status_segment`。理由：破坏 `yate.*` 封装一致性（评审
  Fix constraint 的原始诉求），且 `LUA_SURFACE` 漂移守卫正是为补齐此缺口
  而设。

## 三、分步实施计划

### Step 1：`report_failure` 自防御（评审 2.1）

- 输入：评审记录 §2.1
- 改动文件：`yate/services/events.py`
- 做法：`emit` 的 `except Exception` 处理器内，`_report_failure` 调用包
  `try/except Exception`，异常改走 `log.exception`（R12 tracing、惰性 `%`）。
- 输出：reporter 抛异常不再逃逸 `emit`，后续监听器照常执行。
- 验收命令：`.venv\Scripts\python.exe -m pytest tests/test_events.py -q`

### Step 2：Lua `yate.ui.remove_segment`（评审 2.2）

- 输入：评审记录 §2.2（Fix constraint：Python bridge 方法名为
  `remove_status_segment`，`bridges.py:437`）
- 改动文件：
  - `yate/extensions/_yate.lua`：新增 `yate.ui.remove_segment(id)` 薄封装
    + 头部导出清单补一行；
  - `yate/extensions/_yate.d.lua`：镜像声明（`test_lua_defs.py` 锁步）；
  - `tests/test_lua_defs.py`：`LUA_SURFACE` 增 `ui.remove_segment`；
  - `yate/docs/extensions.en.md` / `extensions.zh.md`：Lua 库函数表各增一行
    （双语同步硬约束）；
  - `yate/extensions/lua.example`：头部函数清单注释同步。
- 验收命令：`.venv\Scripts\python.exe -m pytest tests/test_lua_defs.py tests/test_lua_extensions.py -q`

### Step 3：Fix witness 测试

- 改动文件：`tests/test_events.py`、`tests/test_lua_extensions.py`
- 做法：
  - `test_events.py`：两个健康监听器夹一个失败监听器，`report_failure`
    也抛异常，断言两个健康监听器都执行（评审建议的 witness 形态）；
  - `test_lua_extensions.py`：Lua 模块表脚本 setup 加段、teardown 经
    `yate.ui.remove_segment` 移除；teardown_all 后重新加载同内容副本
    （不同文件名），断言无重复 id `ValueError`（重载成功）。
- 验收命令：同 Step 1 / Step 2。

### Step 4：docstring "13-name" → "14-name"（评审 2.3）

- 改动文件：`tests/test_architecture.py`
- 验收命令：`.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q`

### Step 5：收尾门禁与回填（主代理亲跑）

1. `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/`（0 诊断）
2. `.venv\Scripts\python.exe -m pytest tests/ -q`（全绿）
3. `.venv\Scripts\python.exe -m pytest tests --cov=yate --cov-branch --cov-report=term --cov-fail-under=75`
4. `.venv\Scripts\python.exe -m tools.smoke_test run`
5. 迭代审核：对修复 diff 复跑评审（code-review-expert），有新发现回到
   §三处置，直至无 blocker/major；回填本方案 §五执行记录后提交。

## 四、风险清单与回滚

- 风险：`_yate.lua` 与 `_yate.d.lua` 漂移 → 由 `test_lua_defs.py` 两条
  锁步用例守卫，改动后必跑；
- 风险：`except Exception` 双层嵌套吞掉真实缺陷 → reporter 失败仍走
  `log.exception` 留痕（tracing 文件可查），与监听器隔离同等语义；
- 回滚：各步独立最小 diff，`git revert` 单笔即可回退。

## 五、执行记录（回填）

- 日期：2026-10-14；执行者：主代理（code-review-expert 子代理 spawn 返回
  空结果零产出，按 `subagent-workflow.md` §五 判死规则不重试，改由主代理
  亲自复审——兜底路径，如实登记）。
- Step 1–4 全部按方案落地，无偏离。改动 10 文件 +99/-8：
  `yate/services/events.py`、`yate/extensions/_yate.lua` / `_yate.d.lua` /
  `lua.example`、`yate/docs/extensions.en.md` / `extensions.zh.md`、
  `tests/test_events.py` / `test_lua_defs.py` / `test_lua_extensions.py` /
  `test_architecture.py`。
- 门禁实测（worktree `.venv`，沙箱自证指向本 worktree）：
  - `pyright yate/ tests/ tools/` → 0 errors, 0 warnings（exit 0）；
  - `pytest tests/ -q` → 全绿（exit 0；含新增 2 条 witness 用例）；
  - `pytest tests --cov=yate --cov-branch --cov-fail-under=75` →
    **91.94%**（exit 0）。首跑曾现 2 个 timing 类偶发失败
    （`test_vsplit_with_file_and_only` / `test_devtools_bridge_follows_app_lifecycle`），
    单跑复测通过、整轮复跑 exit 0——与 `subagent-workflow.md` §三.3 已知
    Textual pilot 偶发一致，未改断言；
  - `tools.smoke_test run` → 112/112 场景通过（exit 0）。
- 迭代审核：主代理按 diff 自查 + 定向测试复跑，三条修复与评审建议一致，
  无新增发现；结论 **Approve**（无 blocker / major）。
