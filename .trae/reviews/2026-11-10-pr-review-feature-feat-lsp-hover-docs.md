# 2026-11-10 pr-review：feature/feat-lsp-hover-docs

- 技能：[pr-review v1.0.0](../../skills/pr-review/SKILL.md)，模式 `review`（默认），`$ARGUMENTS` 未给 base ref
- 基线：`master` (`b982c06`)，`git merge-base HEAD master = b982c06`；范围 `git diff b982c06...HEAD`
- 规模：51 文件 / +5053−20（评审启动前），24 笔提交含 1 笔基线 merge；工作区在评审开始时干净
- 噪声过滤（skill Step 1）：无 `*.pyc`/lock/`*.spec`/binary/`.venv` 产物；`yate/editor.py` 三处纯折行收敛（`:279`/`:369`/`:658`）**skipped as noise**，仅在此声明一次
- 分支基线口径：skill 的 `main` 优先/fallback 表述按 `task-orchestration.md` §二.1 让位于本仓库唯一基线 `master`
- 门禁口径：skill Step 3 的 `pyright yate/ tests/ tools/` 与 `pytest tests/ -q` 按 `task-orchestration.md` §二.7 / CI 口径加强为 `pyright yate/ tests/ tools/ pack/` 与 `pytest -q -n auto`，并补架构、覆盖率、冒烟、diffcheck、changelog check

Overall: REQUEST_CHANGES — 1 个合并前门禁项待人工处置（非本 PR 代码缺陷）；本 PR 引入的 BLOCKER/MAJOR 已全部修复。

---

## 一、发现与处置

### `[BLOCKER]` `tools/changelog` CI 门禁在功能分支上红，master 上绿

- 位置：`tools/changelog/cli.py:180-205`（`generate(check=True)` 比较 released sections），非本 PR 改动文件
- Problem：
  - 本分支 `python -m tools.changelog check` → **exit 1**，`stale changelog files — run generate`，四份 CHANGELOG 的 `## [0.2.18] - 2026-11-09 — [compare](v0.2.17...v0.2.18)` 标题被判 drift；另打印 `unreleased ... lags 7 commit(s) (refreshed at release)`（该 lag 是允许的警告，不判红）。
  - 同一命令在 `master` 基线工作区 → **exit 0**，`released changelog sections are up to date`。
  - `git diff --name-only b982c06...HEAD` **不含任何 CHANGELOG 文件**；分支已 `git merge master` 同步 v0.2.18 发布段落，`yate/__init__.py` 为 `0.2.18`。
  - 因果定性：`check` 按当前分支 git history 重算 released segment，v0.2.18 发布之后分支存在 merge commit 与新增提交，重算结果与磁盘的已发布段落不一致；这是发布流程与功能分支的交互，不是 PR 代码缺陷。
- Fix（**人工决策，不在本 PR 改文件**）：
  - 合并到 `master` 后由发布流水线复跑 `python -m tools.changelog check`（master 当前已 exit 0）；
  - 或由人工在合并前明确豁免该分支级红门禁。
  - **不要**在本分支运行 `generate` 改写四份 CHANGELOG：那会把功能分支的提交写进 Unreleased 并改动已发布标题，而 master 侧生成器仍算回原标题，反而使 master 的 CI 变红。
- 按 skill「red hard gate = BLOCKER」登记；因证据表明非 PR diff 引入，整体结论取 `REQUEST_CHANGES` 而非 `BLOCKED`，合并决定权归人工评审者。

### `[MAJOR]` 1. 鼠标换位置未使在途 hover 请求过期 — **已修复**

- 位置：`yate/flows/hover_flows.py:74-98`（原），`_stale` 在 `:184-203`
- Problem：位置 A 的请求 W1 飞行中鼠标移到 B，`on_mouse_move` 只 `close()` 卡片并重排 0.35s timer，不推进 `_token`、不更新 `_target`；W1 在防抖窗口内返回时 `token == self._token` 且 `_target == A == pos`，被判不 stale，于旧锚点弹出旧文档（`exclusive=True` 的新 worker 尚未 spawn）。既有测试把 `HOVER_DEBOUNCE_S` patch 为 0 掩盖了该窗口。
- Fix：位置变化时立即 `self._token += 1`、`self._target = pos`，再按需 close + 重排 timer；新增 `test_mouse_move_to_new_position_drops_inflight_response`（gated future，防抖保持 0.35s 而非 0）断言 `popup.shows == []`。

```python
if self._target != pos:
    self._token += 1
    self._target = pos
if self._popup.is_open:
    self._popup.close()
```

### `[MAJOR]` 2. 空 `MarkedString` 生成空围栏卡片，破坏 AC5 — **已修复**

- 位置：`yate/editor_lsp/parsing.py:83-95`（原）
- Problem：`{"language": "python", "value": ""}` 返回 `` ```python\n\n``` ``，`parse_hover_contents` 的 `text.strip()` 非空 → 弹出只有空代码围栏的卡片，违反 issue「内容为空一律不显示任何东西」。审查员预分级 MINOR，主代理按 AC5 硬约束升级为 MAJOR。
- Fix：取到 `raw_value` 后先判 `not raw_value.strip()` → 返回 `""`；新增 `test_parse_hover_contents_with_empty_value_and_language_returns_empty_string`（6 组空白 × language 参数化）。

```python
if not isinstance(raw_value, str):
    ...
    return ""
if not raw_value.strip():
    log.debug("discarding hover part with empty value")
    return ""
```

### `[MINOR]` 本轮已修复（8 项）

| 位置 | 问题 | 修复 |
| --- | --- | --- |
| `yate/flows/hover_flows.py:139-144` | modal / 无 server 守卫直接 return，不推进 token，在途 worker 仍可能 show | 两个守卫改调幂等 `dismiss()` 后 return；新增 `test_guard_triggered_mid_request_drops_inflight_response` |
| `yate/editor_lsp/parsing.py:104-111` | 服务器可控 `language` 未校验即拼进 fenced block（换行可闭合围栏注入 Markdown） | 仅 `[A-Za-z0-9_+#.-]+` fullmatch 用于围栏标注，否则忽略 language 直接返回 value；补 2 条用例（合法 `python`/`c++`、恶意注入） |
| `yate/editor_components/hover_popup.py:108` | 「下方」分支 `y` 未 clamp，负 anchor 行时卡片落到编辑区上方 | `y = max(origin_y, below)`；新增负 anchor 用例 |
| `yate/editor_lsp/manager.py:672` | 新增 `params: dict[str, Any]` 缺 `python-coding-style.md` §3.3 理由注释 | 补 `# noqa: Any - LSP wire payload, untyped server data` |
| `yate/editor_lsp/manager.py:282` | `_ready_client_for` 未比对 `OpenDocState.client_key`，root/config 替换后可能对未在该 READY client 上 didOpen 的 URI 发请求 | 增加 `state = self._open.get(self._uri(doc))` 且 `state.client_key == key` 校验；新增不匹配返回 `""` 用例 |
| `.trae/rules/architecture-boundaries.md` §一/R9/R11 | 三处文本清单未列 `hover_flows.py` 与 `#hover-docs`（§三.8 第 6 项 / §七 要求同步） | 补入枚举与组件自持 id 先例，未改 §六 38 计数 |
| `.trae/documents/lsp-hover-docs-plans/` 10 份新建 Markdown | 含指向任务 worktree 的 `cd` 行（盘符绝对路径），违反 `doc-conventions.md` §五 | 删 `cd` 行、改可移植表述；目录内盘符 worktree 路径命中 0 |
| `FEATURES.md:197` / `FEATURES.zh.md:161` / `overview.md` §2 | 双语架构守卫计数仍为 36（应为 38）；plan i 文件清单缺 `harness.py`；`test_architecture.py` 实际有三次串行触碰 | 同步为 38、补登记、改为 three sequential edits 说明 |

### `[MINOR]` 登记待办（不阻塞，含历史遗留）

`_hover_part` 递归深度上限（自引用 list/超深嵌套可 `RecursionError`，manager 有 `except Exception` 兜底）；`kind="plaintext"` 仍走 Markdown 渲染（LSP 语义偏差）；`client.start_request` 写失败时 `_pending` 残留（基线既有模式，`client.py` 本轮未改）；`render_doc_lines` 一次 `show()` 两遍渲染且无缓存、超长响应未截断（低频路径）；`tests/test_lsp_hover.py` 既有 `Any` 缺理由注释；8 处 `wait_until(lambda: False, timeout=0.05)` 固定窗口负向断言；部分新增测试模块级常量缺 PEP 526 注解；`hover_popup.py:26` 类定义前空行；`scenarios/hover.py` 私有回调 `getattr/setattr` spy；`editor.py` 恰 800 行临界；存量 `vim_advanced.py` 并行时序风险（另案）。

---

## 二、六维度结论（skill Step 3）

| 维度 | 结论 | 要点 |
| --- | --- | --- |
| 功能与正确性 | PASS（2 MAJOR 已修） | 上两项；其余：UTF-16、超时降级、CancelledError 重抛、`_stale` 六条件、键盘/鼠标共用 worker、空结果零 UI 输出均有实证 |
| 安全 | PASS | 新增链路无 `shell=True`/`eval`/`exec`/`pickle`/`yaml.load`、无硬编码凭据、路径只由已打开 `doc.path` 构造；服务器可控 `language` 围栏注入已修；`plaintext` 渲染语义登记待办（不涉及代码执行） |
| 性能 | PASS | 无 O(n²)/循环内 I/O/整份 buffer 重复读；每键 `dismiss()` 重绘已由 `f637be9` 消除；`render_doc_lines` 双渲染为低频路径待办 |
| 可维护性 | PASS（风格类待办已登记） | docstring/注解/ASCII 注释/绝对导入/行宽 ≤100 均通过；无裸 `except`；两轮评审已消除公共协作者与静默诊断 |
| 架构边界 | PASS | R1-R15 逐条核对通过；`UI_FROZEN_FILES` 精确；规则文本清单已补；无新 `Protocol`/`TYPE_CHECKING`/相对导入/App handle；`SIZE_EXEMPT_FILES` 875 行豁免两处同步；架构 38 用例 |
| 硬门禁 | 1 项红（见 BLOCKER） | 其余全部 exit 0，见下表 |

## 三、门禁实测（主代理亲跑，修复轮之后）

| 命令 | exit | 结果 |
| --- | --- | --- |
| `pyright yate/ tests/ tools/ pack/` | 0 | `0 errors, 0 warnings, 0 informations` |
| `pytest tests/ -q -n auto` | 0 | 全点通过，无 FAILED |
| `pytest tests/test_architecture.py -q` | 0 | `38 passed` |
| `pytest tests/ --cov=yate --cov-branch --cov-fail-under=75 -n auto` | 0 | `Total coverage: 93.05%` ≥75 |
| `tools.smoke_test run --jobs 4` | 0 | `123/123 scenarios`、`1493/1493 checks`（`stress_rapid_toggles` 12/12） |
| `git diff --check` / `git diff --check master...HEAD` | 0 / 0 | 无空白错误 |
| `tools.changelog check`（本分支 / master） | **1** / 0 | 见 `[BLOCKER]`，非 PR diff 引入 |

`pytest -q` 本环境无汇总行，以退出码为准；覆盖率以 `--cov-report=` 抑制长表后取 `Required test coverage` 行。

## 四、范围与流程事实

- 三个只读分域审查员（`code-explorer`，功能/安全、性能/架构、可维护性/文档）并行下发，禁止跑测试/改文件；主代理对其每条发现逐条回读代码复核后定级，并据此升级 1 条 MAJOR、剔除无实证推测。
- 修复轮按 `subagent-workflow.md` 以 2 个 `plan-executor` 并行、独占文件零重叠下发；主代理独立复核落盘结果并亲跑全部门禁（不引用执行者自述数字）。
- 两轮修复共改 21 个文件（产品 4 + 测试 4 + 规则/计划/文档 13），全部按 `git-commit-message.md` 分笔提交；纯文档部分按 `misc-rules.md` §三 豁免测试。

## 五、Strengths

- `<f7>` 统一键的 `\x0b` 同码裁决有字节级实证，单一 `HOVER_DOC_KEY` 常量 + AST 与运行时双守卫真正防住「只改一侧」漂移。
- AC5 零 UI 输出用卡片态 / 正文 / 消息栏 / 状态栏四项快照交叉断言；AC6 用「调用即抛」的 `_block_spawns` 硬证不启动 server、不 `didOpen`/`didChange`。
- `request_hover` 与 `request_completion` 严格分离：只读 READY + `is_open` 状态，不复用会启动 server 的 `ensure_client`，也不刷 `didChange`。
- 前两轮评审已把两个真实 flake 修在根因上（每键隐藏卡片重绘、嵌套 pytest 与 pytest-cov/xdist 冲突），本轮又补上「防抖窗口内在途结果」与「空 MarkedString」两个边界。
- 规则、计划、评审记录三处同步（§六 38 / §三.7 豁免 / §10 真实数字与偏离 / #70–#72 索引），可追溯性强。

**人工决策项**：仅 `changelog check` 的分支级红门禁。AI 预评审不合并，合并决定归人工评审者。
