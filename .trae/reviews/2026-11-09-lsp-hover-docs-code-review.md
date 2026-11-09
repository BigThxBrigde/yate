# 2026-11-09 IKTPC2 LSP hover docs 首轮评审

- 分支：`feature/feat-lsp-hover-docs`（worktree `yate-lsp-hover-docs`），parent `master` @ `8cadbc3`
- 范围：`master..HEAD`，15 笔提交 / 52 文件 / +4807−70；评审时工作区干净
- 评审者：`code-review-expert`（按 [code-review-expert.md](../agents/code-review-expert.md) 剧本，含强制自我批判）
- Skill：运行时 `Skill` 工具未注册 `python-code-review`，已通读 [SKILL.md](../skills/python-code-review/SKILL.md) 并按其 6 维度框架执行
- 结论：**REQUEST_CHANGES** — 1 BLOCKER / 3 MAJOR / 4 MINOR

## 一、发现清单（事实与核对结论）

| 级别 | 位置 | 发现 | 处置结果 |
| --- | --- | --- | --- |
| BLOCKER | [../../tools/smoke_test/scenarios/hover.py](../../tools/smoke_test/scenarios/hover.py):216,221 与 [../../tools/smoke_test/harness.py](../../tools/smoke_test/harness.py):94-106 | 两个新场景用 tag `("hover",)`，但 `TAGS` 未声明；`tests/test_smoke_harness.py` 两条登记守卫失败（`assert ['hover'] == []`），全量 `pytest tests/ -q -n auto` exit 1 | 已修：`TAGS` 加 `"hover"`（`harness.py:102`）；`-n 1` 复核同样失败证明是真实缺陷不是时序假设 |
| MAJOR | [../../yate/__init__.py](../../yate/__init__.py):15、四份 CHANGELOG | 切分支后 `master` 前进到 `b982c06`（v0.2.18 发布）；`merge-base` 仍为 `8cadbc3`，直接合并会把版本与已发布 CHANGELOG 回退到 0.2.17。本分支未改版本号，属**基址过期**而非作者误改 | 已修：`git merge master`（`17692a8`），15 笔功能提交未改写，版本保持 `0.2.18` |
| MAJOR | [../../yate/flows/hover_flows.py](../../yate/flows/hover_flows.py):49-54 | 四个构造注入协作者 `lsp`/`session`/`panes`/`popup` 暴露为公共属性，仅 `_spawn` 私有；`_stale()` 依赖这些状态不被外部改写，且模块注释声明封装意图 | 已修：统一私有化 `_lsp`/`_session`/`_panes`/`_popup`，11 处引用同步；构造参数名与公开方法签名不变 |
| MAJOR | 同上 `:131-134`、`:164-168`，[../../yate/editor_components/hover_popup.py](../../yate/editor_components/hover_popup.py):120-126 | `_schedule` 无 server 守卫只在卡片可见时 `close()`，`_worker` 空结果分支却无条件 `close()`；AC5「不闪」依赖 widget 侧幂等短路这一隐式契约 | 已修：`_worker` 空结果分支加 `if self._popup.is_open`；三个 silent 用例断言由 `closes == 1` 收紧为 `closes == 0`，保留 `shows == []`，另加「隐藏卡片空结果不重绘」用例；正向场景 `test_empty_result_clears_a_previously_visible_card` 的 `closes == 1` 不变 |
| MINOR | `tests/test_hover_flows.py:208,245,262` | silent 用例把「无条件 close」固化成期望值 | 已随上条收紧 |
| MINOR | `yate/editor_lsp/parsing.py:76-92` | `isinstance` 窄化后仍 `cast`，冗余 | 登记待办：删除可能引入 `reportUnknown*` 诊断，本轮不动 |
| MINOR | `hover_flows.py:135-143` | `_stale()` 快照四字段赋值块缺说明 | 已修：加英文 ASCII 注释 |
| MINOR | `tools/smoke_test/scenarios/hover.py:169-180` | 用 `getattr`/`setattr` 监视私有回调 | 登记待办：不得回退为文件级静默注释（wave-4 已删过 `reportPrivateUsage=false`） |

## 二、AC1-AC8 逐条核对（首轮结论）

- **AC1 PASS**：`request_hover` 发 `textDocument/hover`，`character` 经 `_to_utf16`；客户端只声明 `textDocument.hover.contentFormat` 与 `completion.documentationFormat`，不声明 server 侧 `hoverProvider`，裁决符合 LSP 3.17。
- **AC2 PASS**：`<ctrl-k>` 与 `<ctrl-shift-k>` 实测同为 `\x0b` 且 vsc 已绑 `delete_line`，改 `<f7>` 证据充分；单一 `HOVER_DOC_KEY`、两表引用、AST + 运行时双守卫、`keymap="both"`、`<ctrl+/>` 切换后同键均有覆盖。
- **AC3 PASS**：App 与 `MouseFlows` 两道门控；非拖拽 `MouseMove` 返回 `False` 不消费；单 timer 防抖；移开/编辑/Esc 清卡片。
- **AC4 PASS**：`Hover.contents` 四类形状 + hostile 输入；定位翻转、主题令牌、R13 自持、R15 两调用、R9 组件自持 id。
- **AC5 PASS（有风险）**：null/`{}`/空串/全空白/空数组/失败/超时/未启动/无 server/先有卡片后空全覆盖；集成侧四项快照（卡片态、正文、消息栏、状态栏）比仅比消息栏更强。风险即上表 MAJOR 的隐式契约。
- **AC6 PASS**：`_block_spawns` 硬证不启 server / 不 `didOpen` / 不刷 `didChange`；`_stale` 六条件；`can_focus=False`；`_handle_key` 的 `dismiss()` 不 return、不吞键（打字仍进 buffer）。
- **AC7 PASS**：六份双语文档同写 `F7`；`FEATURES.en.md` 从来不存在，用 `FEATURES.md` 的偏离成立。
- **AC8 PASS（除 BLOCKER）**：pyright 0、架构 38、覆盖率 93.06%、冒烟 123/123；新增代码无 `TYPE_CHECKING`/裸 `except`/相对导入/f-string 日志；15 笔提交信息全英文 conventional。

## 三、门禁实测（评审者本机实跑）

| 命令 | exit | 结果 |
| --- | --- | --- |
| `pyright yate/ tests/ tools/ pack/` | 0 | `0 errors, 0 warnings, 0 informations` |
| `pytest tests/ -q -n auto` | **1** | 2 failed（tag 守卫）；`-n 1` 复核同样失败 |
| `pytest tests/test_architecture.py -q` | 0 | `38 passed` |
| `pytest tests/ --cov=yate --cov-branch --cov-fail-under=75 -n auto` | 0（含失败标记） | `TOTAL 93%` / `93.06%`；以 pytest exit 1 为准 |
| `tools.smoke_test run --jobs 4` | 0 | `123/123 scenarios`、`1493/1493 checks`；`--jobs 1` ×2 亦全绿 |

## 四、架构裁决与 flake 复核

- `editor_lsp/manager.py` 875 行豁免**接受**：职责块共享 `_clients`/`_open`，迁出会破坏封装；规则 §三.7 与 `SIZE_EXEMPT_FILES` 两处已同步。
- `editor.py` 恰好 800 行：零余量脆弱性，登记 minor；评审建议还原三处折行会使文件涨到 807 行触发阈值守卫，故主代理裁定**显式接受**折行收敛。
- `UI_FROZEN_FILES` 对 `flows/hover_flows.py` 的登记与实际 import 逐条对应，无多登漏登；无新增向上依赖 / `Protocol` / App handle。
- `stress_rapid_toggles` flake 归因**成立**：每键 `dismiss()` 对隐藏卡片仍写 `Static.update("")` 与 `display`，多出重绘周期拖慢收敛；修复后三次 `--jobs 1` + 一次 `--jobs 4` 全 123/123。残留的「靠下游短路兜底」由本轮 MAJOR 收口。

## 五、强制自我批判（评审者记录摘要）

- 逐条反证：重读所引行号、实跑 pytest 两次与 `-n 1` 复核，BLOCKER 与 3 个 MAJOR 证据成立。
- 剔除 4 条误报：`_token` 在守卫前递增（实际在守卫之后）、`reportPrivateUsage=false` 违反 §4.2（该条不属禁止对象）、`FEATURES.en.md` 缺失（文件从不存在）、`_GUTTER` 魔法数字（既有先例且已注释）。
- 降级 2 条：公共属性 blocker→major（无现实外部调用方）；反射绕过 major→minor（`tools/` 侧有意 workaround 且有注释）。
- 漏报自查：正确性 / 边界 / 异常 / 并发 / 性能 / 类型与测试覆盖六维度反扫，`row` 越界与 `active_view is None` 两处防御分支因可达性不足未新增问题。

## 六、处置与后续

迭代修复见提交 `f0f1b85`、`6858ff1` 与基线合并 `17692a8`；复审结论见 [2026-11-09-lsp-hover-docs-iteration-verification.md](2026-11-09-lsp-hover-docs-iteration-verification.md)，主计划 [lsp-hover-docs-plan.md](../documents/lsp-hover-docs-plan.md) §10。
