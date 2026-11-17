# PR Review — `feature/feat-soft-wrap`（合并前）

> 评审日期：2026-11-17（无人值守）｜模式：`review`（只读 + 门禁实测）
> 对象：`feature/feat-soft-wrap` 相对 `master`，18 笔提交（`11c9f97b..f9406d26`），
> 42 文件 +2787/−50；issue IKVRXT「软换行」。
> base 分支 `master`（HEAD 与 origin 同步），无噪音文件（无 lock/pyc/二进制）。
> 本文为只读事实记录；发现与建议见 §五，修复版本以 commit 为准。

## 〇、评审执行方式（偏离登记）

- 按 `pr-review` skill 派 2 名分维度只读评审员（`pr-func`：功能/健壮性/可维护性；
  `pr-perf`：性能/安全/架构/门禁），团队模式 `bypassPermissions`，任务书自包含六维度与
  唯一规范来源。
- `pr-func`：探活累计 30 分钟零回信零产物 → 按 `subagent-workflow.md` §五.3 判死零产出。
- `pr-perf`：观察到其覆盖率进程（`--basetemp=yate-cov-0aecbd37`）真实运行 20+ 分钟后退出，
  曾撤回判死要求交付；进程结束后多次索取报告仍零回信 → 按零产出登记。
- 按 `task-orchestration.md` §三 由**主代理亲自按 pr-review 剧本兜底**：独立跑完全部 6 项
  硬门禁 + 六维度读码自审。本报告所有数字与发现均来自主代理实测，不采信任何子代理自述。
- 这是流程偏离（两名评审员零交付 → 主代理兜底），如实登记。

## 一、Overall

**APPROVE** — 0 blocker、0 major、3 minor（均为文档/流程口径，非阻断）。合并前门禁全绿，
上一轮自审的 3 个 MAJOR 修复经本次复查全部保留、无回归，identity 快路径在 wrap-off 的
全部 span 消费点均安全。建议按 §五 minor 建议酌情处理后即可合流。

## 二、门禁实测（主代理独立执行，exit code 权威）

| 门禁 | 结果 | exit |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings | 0 |
| `pytest tests/ -q -n auto` | 全绿（10 skipped，无 failed；独立轮次重跑确认） | 0 |
| `pytest tests/test_architecture.py -q` | 42 passed | 0 |
| `pytest tests/ --cov=yate --cov-branch -n auto` | TOTAL 92.90%（阈值 75%），3822 passed / 10 skipped | 0 |
| `tools.smoke_test run --jobs 4` | 124/124 场景、1511/1511 checks，83s | 0 |
| `git diff --check master...HEAD` | 无输出 | 0 |
| `python -m tools.changelog check`（附加） | released sections up to date；unreleased zh 滞后为存量提示 | 0 |

**环境伪影说明（非代码失败）**：首轮并发跑门禁时，pytest 输出曾出现
`[safe-delete][SAFE_DELETE_BULK_GUARD_ERROR] state lock timeout`（本机清理 `%TEMP%` 积压被钩子拦截），
smoke 曾出现 1510/1511 checks、273s（多 agent 并发跑 Textual pilot 干扰）。按
`python-coding-style.md` §4.7 / `subagent-workflow.md` §三.3，两者均在**无并发串行重跑**后全绿
（smoke 83s、pytest exit 0），确认非产品缺陷，未改任何断言。

## 三、六维度结论

### 维度 1 功能正确性与健壮性 — PASS

- **AC1**（显示层折行、零改 buffer/undo/文件）：render 路径全程只读 `buf.lines`；`WrapLayout`
  为纯计算，无 buffer Mutation。
- **AC2**（单元格宽度/tab/宽字符）：`_wrap_line` 复用 `cell_offsets`/`expand_char`，宽字符与
  超界 tab 整体推到下一显示行、孤立超宽字符独占一行，不拆半字。
- **AC3**（wrap-off 零回归）：`render_line`/`buffer_pos_from_mouse`/`reveal_cursor`/`move_display_line`
  的 wrap-off 分支全部绕开 `_wrap`，走原 `scroll_col`/逻辑行路径；`test_app_render.py` 无回归。
- **AC4**（vim gj/gk）：g 前缀分支只认 j/k，`gg`/数字计数/未知 follower 丢弃不变；count 取
  `self._typed_count() or 1`；normal 传 `select=False`、visual 传 `select=True`。
- **AC5**（alt+z 两套 keymap）：`SOFT_WRAP_KEY` 共享常量 + 架构漂移守卫；`\x1bz` 不在保留键。
- **AC6**（折行态正确性）：gutter 续行留空、诊断 mark 每行显示、语法/styles 按 logical_y。
- **AC7**（chunked）：`render_line`/`buffer_pos_from_mouse` 的 `_ensure_row` 均传映射后的
  `span.logical_row`；content_version bump 后二次 `_sync_wrap` 重映射；区间表/占位/locked 保持。
- **AC8**（性能）：见维度 3。
- **AC9**（双语）：12 份 en/zh 同轮同步，`git diff --check` 0。

**3 个已知修复复查**（本次 PR 的重点回归面）：
1. `0e25ca48`（缓存键加 doc identity）：`update` key 第 4 项为 `identity`，`view._sync_wrap`
   传 `self.doc`；切未编辑文档不再复用旧折行表。→ **保留，无回归**。
2. `003432e6`（KeyUi.move_display_line 加 `select`）：`base.py` type 别名三参数、`editor`/`view`
   转发、`vim.py` visual 传 True/normal 传 False；回归断言 `(1,1,True)` 在。→ **保留，无回归**。
3. `ed74926f`（wrap-off O(1) identity 快路径）：`update` 在 `not enabled` 时只记行数、零行扫描
   （`wrap_layout.py:141-148`）；查询方法 identity 分支（157-214）。**关键风险点 `cell_end=0`
   哨兵已逐点核对全部 span 消费点**：`render_line` 文本窗口 wrap-off 走 `else`（view.py:629-631）
   用 `scroll_col`、不读 `span.cell_start/end`；`span.continuation` 恒 0（行号正常）；
   `buffer_pos_from_mouse`/`reveal_cursor`/`move_display_line` 的 wrap-off 分支全部绕开 `_wrap`。
   → **保留，无回归，哨兵安全**。

### 维度 2 安全 — PASS（无安全面改动）

本 diff 为渲染/键位/配置/文档，无新文件 I/O、无反序列化、无网络、无 shell 注入面、无硬编码
密钥。无 BLocker 级架构违规（见维度 5）。

### 维度 3 性能 — PASS

- identity 快路径（默认态）零行扫描，2 万行文档 spy `cell_offsets` 零调用（回归测试实证）。
- 缓存 key 为 4 元组 O(1) 比较；稳定帧零重建（E 波次 50k 行/100k 字符长行测试背书）。
- wrap-on 重建只在 key 变化时一次性 O(逻辑行)；可见行 `display_to_logical` O(1) 索引；
  `logical_to_display` 单行内线性扫 span（每行折行数有界）。
- 无路径因折行把 chunked 大文件全文拉入内存；每次击键不再做 O(文档) 恒等重建。

### 维度 4 可维护性 — PASS（2 minor，见 §五）

- 类型注解完整、docstring 为英文散文、ASCII 注释、绝对导入、无新增 Any/type:ignore/Protocol。
- 测试覆盖充分（新增模块/键位/配置/渲染/chunked 均有对应用例）。
- minor：规则 `architecture-boundaries.md` §三.7 把 editor.py 精确行数（840）写死在文本里，
  `test_size_exemption_rule_and_guard_are_in_sync` 逐字断言，属脆弱设计（本次开发期两次转红）。

### 维度 5 架构边界 — PASS（BLOCKER by definition：无命中）

- 依赖方向：`keymaps`（L1）不 import 视图（L2），经 `KeyUi.move_display_line` 回调注入；
  `wrap_layout` 为 L2 纯计算模块，无 widget 基类（R15 不触发）。
- 无新增 `Protocol`/`TYPE_CHECKING`/`Any`/`type:ignore`；命名守卫、ASCII 注释、绝对导入合规。
- `view.py`(816)/`editor.py`(840) 体量豁免：规则文本 + `SIZE_EXEMPT_FILES` 两处同步（集合 7），
  `test_architecture.py` 42 passed 含该守卫。

### 维度 6 硬门禁 — PASS

见 §二表，6 项全 exit 0（附加 changelog check 0）。

## 四、强制自我批判（已执行）

- 初版关注点逐条回代码实证：identity 哨兵风险点重读 view.py 三处消费分支（525-631 / 295-324 /
  385-452），确认 wrap-off 全绕开 span cell 字段——剔除该误报。
- 门禁两处红（safe-delete / smoke 1 check）经串行重跑转绿——剔除为环境伪报、未改断言。
- 反向扫漏报：复查 diff 无新 I/O/反序列化/注入面；复查 3 个修复的下游调用点无遗漏。
- 结论状态：0 blocker / 0 major / 3 minor，APPROVE。

## 五、发现与分档行动建议

### MINOR-1（文档口径）CHANGELOG Unreleased 条目暂无 commit 哈希链接

- 位置：`CHANGELOG.md` / `CHANGELOG.zh.md` Unreleased 顶部软换行条目。
- 建议：合流后由 `tools.changelog` 重生成补齐链接；不阻断本 PR。

### MINOR-2（流程口径）评审子代理零产出，主代理兜底

- 位置：见 §〇。两名评审员均零交付，本报告为主代理兜底自审。
- 建议：后续 pr-review 可优先用运行时验证有效的模型（如 Hy4）派发，或直接在主代理执行以
  省去 30 分钟判死窗口；不阻断本 PR。

### MINOR-3（测试设计脆弱性）精确行数守卫

- 位置：`architecture-boundaries.md` §三.7 + `tests/test_macro_wiring.py::test_size_exemption_rule_and_guard_are_in_sync`。
- 问题：把 editor.py 精确行数写死在规则文本并逐字断言，editor.py 每次增长都要改两处（本次开发期
  两次转红：807→837→840）。
- 建议：后续另案把守卫改为「实测行数 ≤ 规则登记值或登记值随实测自动回填」，避免机械同步；
  不阻断本 PR（当前已同步为 840、守卫绿）。

## 六、结论

`Overall: APPROVE`。合并前门禁全绿、0 blocker/0 major，上一轮 3 个 MAJOR 修复经复查全部保留
且 identity 快路径无回归。分支未推送、未合入 `master`；建议按 §五 3 条 minor 酌情处理后合流。
