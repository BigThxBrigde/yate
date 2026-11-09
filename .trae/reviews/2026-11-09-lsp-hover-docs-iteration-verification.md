# 2026-11-09 IKTPC2 LSP hover docs 迭代复审

- 分支：`feature/feat-lsp-hover-docs`；范围：首轮 `REQUEST_CHANGES` 之后的全部分支改动
- 评审者：`code-review-expert`（只读，工作区复查干净）
- 结论：**APPROVE** — **0 BLOCKER / 0 MAJOR**；2 条新增 MINOR + 3 条存量待办，均不阻塞
- 首轮记录：[2026-11-09-lsp-hover-docs-code-review.md](2026-11-09-lsp-hover-docs-code-review.md)

## 一、7 项核验逐一结论

| # | 核验项 | 结论 | 关键证据 |
| --- | --- | --- | --- |
| 1 | BLOCKER：hover tag 登记 | **PASS** | `tools/smoke_test/harness.py:102` 有 `"hover"`；两场景 `:216`/`:221` 仍为 `("hover",)`；两条登记守卫实跑 exit 0；全量 pytest exit 0 |
| 2 | MAJOR：基线过期 / 版本回退 | **PASS** | `git rev-parse master` 与 `merge-base master HEAD` 同为 `b982c06`；`yate/__init__.py:15` 为 `0.2.18`；四份 CHANGELOG 的 0.2.18 已发布段落完整且未被本分支改动；15 笔功能提交哈希未改写（`master..HEAD` 非合并提交 17 笔 = 15 功能 + 2 修复） |
| 3 | MAJOR：`HoverFlows` 公共属性 | **PASS** | `hover_flows.py:50-53` 为 `_lsp`/`_session`/`_panes`/`_popup`；全模块 `self.lsp`/`self.session`/`self.panes`/`self.popup` 零命中；构造参数名与公开方法签名、`editor_compose.py:237-244` 接线不变 |
| 4 | MAJOR：空结果 close 对称 + 配套 minor | **PASS** | `hover_flows.py:165-168` 已用 `if self._popup.is_open` 包裹；三个 silent 用例断言 `closes == 0` 且保留 `shows == []`，改用 `lsp.calls == 1` 作确定性同步点；正向场景仍断言 `closes == 1`；新增 `test_empty_result_with_hidden_card_does_not_repaint`；快照注释在 `:139` |
| 5 | 新修复：R15 守卫去嵌套子进程 | **PASS** | `tests/test_hover_popup.py:280-299` 删除 `subprocess`/`sys`，改 `importlib.util` 进程内加载并调用真实守卫 `test_scrollable_widgets_apply_theme_scrollbar_pair()`（该守卫动态扫描新组件）；`getattr` + `cast(Callable[[], None], ...)`，无 `Any`/`type: ignore`/相对导入；pyright 0；覆盖率运行不再失败 |
| 6 | 回归面 | **PASS** | `dismiss()` 双层不重绘；AC5 静默与 AC6 六条件过期丢弃保持；`_handle_key` 不吞键（打字仍进 buffer）；`UI_FROZEN_FILES` 白名单与 import 精确对应；无新 `Protocol`/`TYPE_CHECKING`/App handle/新增非 ASCII 注释 |
| 7 | 未修 minor 待办 | **PASS（仍存在，未被静默豁免）** | `parsing.py:84,89,97` 冗余 cast；`scenarios/hover.py:170,172,180` 私有回调 spy；`editor.py` `splitlines()` = 800 临界；均未偷偷改成豁免 |

## 二、门禁实测（复审者本机实跑，不引用他人数字）

| # | 命令 | exit | 结果 |
| --- | --- | --- | --- |
| 1 | `pyright yate/ tests/ tools/ pack/` | 0 | `0 errors, 0 warnings, 0 informations` |
| 2 | `pytest tests/ -q -n auto` | 0 | 全绿，两次运行一致 |
| 3 | `pytest tests/test_architecture.py -q` | 0 | `38 passed` |
| 4 | `pytest tests/ --cov=yate --cov-branch --cov-fail-under=75 -n auto` | 0 | `TOTAL 19814 stmts / 1090 miss / 6318 branch / 581 partial / 93%`；`Total coverage: 93.03%` |
| 5 | `tools.smoke_test run --jobs 4` | 首轮 1 / 复跑 0 | 首轮 `122/123`、`1492/1493`；复跑 `123/123`、`1493/1493`，hover 组 `2/2`、`29/29` 两次均 PASS |

## 三、新增 MINOR 与存量风险（均不阻塞）

1. `yate/editor_components/hover_popup.py:26` 类定义前仅 1 空行（PEP 8 要求 2 行）；仓库无 ruff/flake8，pyright/pytest/冒烟均不拦。
2. `yate/editor.py:279/369/658` 三处与 hover 无关的反向折行（76/78/99 列，均 ≤100 未越界），属噪声 diff；还原会使文件涨到 807 行触发 A11 阈值守卫，主代理裁定显式接受并登记。
3. 三项首轮遗留待办见核验 7，按剧本 minor 可登记待办。

### 冒烟首轮失败定性（非本分支缺陷，登记而非记成偶发）

- 首轮 `--jobs 4`：`vim_registers_text_objects` 的 `ciw_back_to_normal` 期望 `NORMAL` 实得 `INSERT`，整体 `122/123`、`1492/1493`、exit 1，单轮耗时 279.48s。
- 复核：`--jobs 1 --tag edit` 该场景 `PASS 38/38`；第二次 `--jobs 4` 全绿 `123/123`、`1493/1493`、exit 0（83.12s）。
- 因果证据：该场景文件 `tools/smoke_test/scenarios/vim_advanced.py` 未被本分支触碰（最近三笔提交均早于本分支）；失败点是 `escape` 后单次 `pilot.pause()` 立即读 `mode_label()` 的存量并行时序假设。
- 结论：按「不得把 flake 记成偶发」登记为**存量用例的并行时序风险**，建议另案补 `wait_until` 轮询；与本分支无因果，不作阻塞项。主代理另在本分支多次 `--jobs 4` 复跑均 123/123。

## 四、强制自我批判摘要

- 逐条反证：重读 `harness.py:94-107`、`hover_flows.py:50-53 / 165-168`、`6858ff1` diff；`findstr` 反证无遗漏公共属性引用；`merge-base` 与版本/CHANGELOG 交叉核对。
- 降级：「反向折行」初判 major（行宽）→ 逐行实测 ≤100 后降 minor；「冒烟首轮红」初判 blocker → `--jobs 1` 与复跑双证 + 文件未被改动，降为非阻塞存量风险。
- 误报剔除：`self.parent is not None` 双保险（无 App 几何测试的必要护栏）、`except Exception: # noqa: BLE001`（AC5 明确要求静默降级且有测试背书）。
- 漏报自查：正确性 / 边界 / 异常 / 并发 / 性能 / 类型与测试覆盖六维度反扫，仅补报 1 条 PEP 8 空行 minor。

## 五、最终结论

**APPROVE**。首轮 1 BLOCKER + 3 MAJOR 全部逐条实证修复；五项硬门槛全达标（pyright 0 / 全量 pytest exit 0 / 架构 38 / 覆盖率 93.03% ≥ 75 / 冒烟 123/123·1493 checks）。修复质量优于原实现：silent 用例改用 `lsp.calls` 同步点、R15 守卫改进程内调用且保留动态扫描语义、`_worker`/`_schedule` 守卫对称。

主计划与真实数字回填见 [lsp-hover-docs-plan.md](../documents/lsp-hover-docs-plan.md) §10。
