# 2026-10-17 tab 点击切换文档回归（用户报告）

- 报告：2026-10-17，用户原话"发现有回退，在全面支持鼠标点击事件后，点击tab是能切换文档的，
  现在无法切换"
- 处置：[`../documents/tab-click-regression-review-fixes-plan.md`](../documents/tab-click-regression-review-fixes-plan.md)
  （分支 `fix/tab-click-switch`，worktree `../yate-tab-click-switch`）
- 形态：**只读事实文档**（只记录发现与核对结论，不含修复排期）

## 一、症状与环境

- 症状：点击顶部标签行中的文档 tab，文档不切换（渲染帧停留在旧文档；tab 高亮不动）。
- 环境：Windows 真实终端（ConPTY + Windows Terminal），默认弦驱动（`key_protocol != "legacy"`）。
- 基线：master `050f16f`（回归在无头 pilot 下即可复现，与终端无关）。

## 二、取证（主代理亲测）

1. **组件与接线无缺陷**：`TabBar.on_mouse_down`（`chrome.py:147`）按 `_regions` 命中后回调
   `on_activate`；探针实测 `app.screen.get_widget_at(标签屏幕坐标)` 返回 `TabBar`；
   pilot 直点标签后 `session.index` 正确切换。
2. **渲染级复现（对照实验，三文档 alpha/bravo/charlie）**：点击 a.txt 标签后
   `session.index=1`、`panes.active_view` 的 buffer 已是 a.txt，**但
   `app.screen._compositor.render_strips()` 的帧仍显示 charlie**；改走键盘路径
   `cycle_tab(1)` 后帧正确显示 bravo ⇒ "模型切了、帧没刷"。
3. **路径差异（根因）**：键盘路径 `cycle_tab` 末尾有一组切换收尾
   （`session.reset_search()` + `completion.close()` + `_refresh_ui()`，见
   `yate/flows/document_flows.py`），而 **tab 点击走的 `activate_doc` 没有这组收尾**；
   `_open_document`（`:e` / explorer 打开）虽同样走 `activate_doc`，但其后的
   `_after_open()` 含 `_refresh_ui` 兜底 ⇒ **tab 点击是唯一缺收尾的切换路径**，
   与"只有点击 tab 坏"的症状完全吻合。
4. **排除项**（均实测非成因）：`support_mouse` 闸门（默认 True，仅 `:set` 可关）、
   `mouse_flows` 派发（仅作用于 EditorView）、PaneHost 分隔条拖拽（仅命中分隔条时 `stop()`）、
   `a01ef20` 的 `+N` 溢出重构（区域记账等价）、`e1181f8` 的 cell 宽度 memo（纯函数等价）、
   弦驱动 `record_key_override`（仅 ctrl/alt 截胡，鼠标 SGR 透传字符不受影响）。

## 二点五、提交考古：不存在"删掉刷新"的单笔提交，缺陷是潜伏缺陷 + 滚动掩蔽

用户追问"是哪次提交造成的"，考古结论（提交逐一核对 + 掩蔽机制实证）：

| 时点 | 提交 | 事实 |
|---|---|---|
| 2026-09-12 | `ecadd41`（引入窗格模型 Leaf/Split/ViewState） | `show_doc`/`apply_doc` 自始就**不含**显式刷新；重绘完全依赖 `apply_doc` 末尾 `view.scroll_to(...)` 的 watcher 副作用 |
| Textual 语义 | 版本钉子自初始提交未变 | `_scroll_to` 非动画分支只在**滚动位置实际变化**时触发 watcher → 刷新；位置相同则静默返回 |
| 2026-09-29 | `0cff320`（flows 抽取） | 原样搬运无收尾的 `activate_doc`（`0cff320^` 已核对，函数体无刷新） |
| 2026-10-08 | `84e27f9`（鼠标特性合入） | `activate_doc` 仍无收尾（当时函数体已核对）；逐路径打补丁自此开始：`cycle_tab` 有收尾、`_after_open` 有 `_refresh_ui` |
| 2026-10-16 | `bc690ba` | 新增的 reveal 路径（`reveal_match`）**单独**补了 `self.refresh_ui()` —— 同一缺口的又一个逐路径补丁，tab 点击仍未覆盖 |

**掩蔽机制实证**（修复摘除态，探针 `probe_scroll_mask.py`）：

- 新旧文档**滚动位置不同**（c.txt 滚到底后点击 a.txt）→ 帧正确显示 alpha —— 点击"看起来正常"
  （`scroll_to` 位置变化触发 watcher 刷新）；
- 新旧文档**滚动位置相同**（都在文件顶部）→ 帧保持 charlie —— 点击"没反应"。

因此：**不存在"某次提交删掉了刷新"**；缺陷自窗格模型引入（`ecadd41`）即潜伏，"能切/不能切"
取决于新旧文档滚动位置是否相同（长文件浏览时通常不同 → 掩蔽；新开短文件都在顶部 → 显形）。
修复将收尾收敛为所有切换路径共享的 `_after_activate()`，重绘不再依赖滚动副作用；
渲染级回归用例（等滚动位置场景）永久钉死该行为。

## 三、结论

- 定级：**MAJOR**（核心交互回归，模型与渲染不一致）。
- 根因：`activate_doc` 缺少 `cycle_tab` 的切换收尾，tab 点击路径切换模型后不调度重绘。
- 修复：收尾提炼为 `document_flows._after_activate()`，`activate_doc` 与 `cycle_tab` 共同复用；
  新增渲染级回归用例（`tests/test_app_textual.py::test_tab_click_switches_the_rendered_document`，
  负向演练：摘除收尾后用例失败，还原后通过）。
- 门禁终态（主代理亲跑）：`pyright yate/ tests/ tools/` 0/0/0（exit 0）；
  全量 `pytest tests/ -q --cov --cov-fail-under=75` **91.95%**（exit 0）。
