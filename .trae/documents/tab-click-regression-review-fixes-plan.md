# tab-click-regression-review-fixes-plan

- 来源：[`../reviews/2026-10-17-tab-click-regression.md`](../reviews/2026-10-17-tab-click-regression.md)
  （2026-10-17 用户报告的回归：全面支持鼠标点击事件后，点击 tab 无法切换文档）
- 分支 / worktree：`fix/tab-click-switch` / `../yate-tab-click-switch`（自 master `050f16f` 新建，
  沙箱 `.venv` 已重建并自证指向本 worktree）
- 日期：2026-10-17
- 状态：**已批准执行**（用户指令"新建分支和worktree，登记并修复"）
- 唯一规范来源：本计划 + [`../reviews/2026-10-17-tab-click-regression.md`](../reviews/2026-10-17-tab-click-regression.md)
  - [`../rules/`](../rules/) 全 8 个规则文档（起草前已逐个精读）

## 一、目标与非目标

**目标**：让**每一条**文档切换路径（tab 点击 / `:bn` / `gt` / reveal 跳转）都完成同一套切换收尾
（清旧文档搜索高亮、关补全弹窗、刷新 UI），修复"tab 点击后渲染帧不跟随"的回归；并补一个
pilot 渲染级回归用例。

**非目标**：不动 TabBar 命中测试与渲染实现（`chrome.py` 实测无缺陷）；不动鼠标事件管线
（`support_mouse` 闸门 / `mouse_flows` / PaneHost 分隔条拖拽实测无缺陷）；不新增架构规则。

## 二、调研取证（计划制定者亲测，2026-10-17）

| 取证点 | 实测 | 结论 |
|---|---|---|
| 组件命中测试 | `TabBar.on_mouse_down`（`chrome.py:147`）按 `_regions` 命中并回调 `on_activate`；探针实测 `app.screen.get_widget_at(标签屏幕坐标)` 返回 `TabBar` | 组件与接线无缺陷 |
| `TabBar` 接线 | `editor.py:184` `TabBar(ed.session, ed.document_flows.activate_doc, id="tabbar")` | 点击走 `activate_doc` |
| 鼠标管线 | `app.py:241` 闸门仅当 `support_mouse=False` 丢弃（默认 True，`config.py:153`）；`mouse_flows.handle_view_mouse` 仅作用于 EditorView；`panes.py:639` 分隔条拖拽仅在命中分隔条时 `stop()` | 非成因 |
| 无头复现（对照） | pilot 三文档（alpha/bravo/charlie）：点击 a.txt 标签后 `session.index=1`、活动视图 buffer 已是 a.txt，**但 `render_strips()` 帧仍显示 charlie**；`cycle_tab(1)` 后帧正确变为 bravo | **回归复现**：模型切了、帧没刷 |
| 路径差异 | `cycle_tab` 末尾 `reset_search() + completion.close() + _refresh_ui()`；`activate_doc` 无此收尾；`_open_document` 虽也走 `activate_doc`，但其后有 `_after_open()`（内含 `_refresh_ui`）兜底 | **唯一缺收尾的切换路径 = tab 点击** |
| 修复验证 | `activate_doc` 补 `_after_activate()` 后复跑探针：点击后帧显示 alpha、cycle 后显示 bravo；新增回归用例修复态通过、摘除收尾的负向演练 `1 failed` 后还原 | 修复有效且用例有牙齿 |

## 三、备选方案与否决理由

- **方案 A（采纳）**：把切换收尾提炼为 `document_flows._after_activate()`，`activate_doc` 与
  `cycle_tab` 共同复用。理由：所有切换路径行为一致；flow 层是"切换文档"职责的唯一归属；
  改动最小（1 个新私有方法 + 2 处调用）。
- **方案 B（否决）**：只在 `TabBar` 接线处包一层刷新（`editor.py:184` 换成带收尾的 lambda）。
  否决理由：reveal 跳转（`editor.py:779`）与未来其它切换入口会再次漂移；把收尾藏进接线违背
  "flow 拥有切换职责"的归属。
- **方案 C（否决）**：改 `panes.apply_doc` 补刷新。否决理由：`apply_doc` 是窗格状态操作；
  搜索高亮清理与补全关闭是文档切换的 flow 职责；且 `panes.py` 自鼠标特性合入（84e27f9）以来
  零改动，在此动手扩大验证面。

## 四、分步实施与执行记录（已执行）

| 步骤 | 内容 | 结果 |
|---|---|---|
| Step 1 | `document_flows.activate_doc` 末尾补 `_after_activate()`（`reset_search` + `completion.close` + `_refresh_ui`），`cycle_tab` 改为复用共享收尾 | 完成 |
| Step 2 | 回归用例 `tests/test_app_textual.py::test_tab_click_switches_the_rendered_document`（渲染帧断言：`render_strips()` + `wait_until`，覆盖点击与键盘两条路径） | 完成 |
| Step 3 | 负向演练：临时摘除 `activate_doc` 的收尾调用 → 新用例 `1 failed`（exit 1）→ 还原后通过 | 完成 |
| Step 4 | 全量门禁（见 §五） | 全绿 |

## 五、验收命令与门禁实测（主代理亲跑）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_app_textual.py -q -k "tab_click"
.venv\Scripts\python.exe -m pytest tests/ -q --cov --cov-fail-under=75
```

| 门禁 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations，exit 0 |
| 新回归用例 | 修复态 passed；负向演练 FAILED（exit 1）后还原 |
| `pytest tests/ -q --cov --cov-fail-under=75` | 全量通过，覆盖率 **91.95%**，exit 0 |

说明：聚焦轮曾出现 `test_syntax_highlight_and_theme_switch` 单次失败，按
`subagent-workflow.md` §三.3 重跑两次均通过，判定为 timing 偶发，未改任何断言。

## 六、风险与回滚

| 风险 | 缓解 / 回滚 |
|---|---|
| `_open_document` 路径出现重复收尾（`activate_doc` 尾 + `_after_open` 内的同名调用） | 两组调用均幂等（reset/close/refresh），全量测试绿；如需精简另行立项 |
| 切换时补全弹窗被关影响依赖弹窗的场景 | 与 `cycle_tab` 既有行为一致（键盘路径一直如此） |
| 回滚 | `git revert <本步提交 sha>`；负向演练的临时改动未入库 |
