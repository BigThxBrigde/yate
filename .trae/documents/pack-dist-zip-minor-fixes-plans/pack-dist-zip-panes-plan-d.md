# 子计划 d：存量焦点竞态 F16（wave-2，主代理亲改产品源码）

> 路径基准同总纲。唯一规范来源：本文件 +
> `../pack-dist-zip-minor-fixes-plan.md` §2/§3 +
> `../pack-dist-zip-minor-fixes-issue.md` F16 +
> 评审记录 `.trae/reviews/2026-11-10-pack-dist-zip.md` §7.4 N1。
> `subagent-workflow.md` §一.3 禁止子代理修改 `yate/` 产品源码，故本波由
> 主代理亲自执行，不派子代理。

## 1. 输入

- 根因取证：`yate/editor_components/view.py:175-177` 的 `on_focus()` 只管
  `self.panes.notify_focus(self.leaf_id)`；`yate/editor_components/panes.py:214-220`
  的 `notify_focus` 调 `leaf_by_id`（`:135-140` 对 `find_leaf` 返回 None 做
  硬断言）。关闭 pane 后迟到的 focus 事件命中已销毁 leaf → 断言崩溃。
- 复现实测（评审 N1）：`pytest tests/test_app_panes.py -q -n 1` 连续 4 次
  得 0,1,0,0；单独跑该用例 6/6 全过；属确定性焦点竞态，不得记「偶发」。
- 现有用例：`tests/test_app_panes.py:127-148`
  `test_close_command_closes_active_pane`（close 后只 `wait_until(leaf_count==1)`
  就发 `cl`，:146 断言 `app.is_running`）。

## 2. 独占文件清单

只改 `yate/editor_components/panes.py`、`tests/test_app_panes.py`。
其余文件（含 wave-1 的 `tools/`、`tests/test_pack_*`、`pack/`、`README`）一律
不触碰。

## 3. 具体修改（产品侧 + 测试侧 + 守卫用例）

1. **产品侧**（`panes.py:214-220`）：`notify_focus` 在 `is_mounted()` 之后把
   ```python
   leaf = self.leaf_by_id(leaf_id)
   ```
   改为
   ```python
   leaf = find_leaf(self.root, leaf_id)
   if leaf is None:
       # A late focus event can arrive after its pane was closed.
       return
   ```
   - `leaf_by_id` 与其硬断言**保持原样**（active-view 等调用点依赖
     live-view 不变式）；
   - 注释与现有 docstring 全英文 ASCII；不改其它方法、不新增 import
     （`find_leaf` 已在文件内可用，见 `:133`）。
2. **测试侧**（`test_close_command_closes_active_pane:140-144`）：
   `assert await wait_until(pilot, lambda: panes.leaf_count == 1)` 之后、
   发 `cl` 之前补一次 `await pilot.pause()`，让关闭后的迟到 focus 事件先
   派发完。其余断言（含 `app.is_running`）不动。
3. **守卫用例**（新增，名称 `test_notify_focus_when_leaf_was_closed_returns_silently`）：
   - arrange：`pane_root` fixture + `YateApp` + `run_test`，`sp` 后
     `wait_until(leaf_count == 2)`，用本文件既有 `pane_leaves(panes.root)`
     / `EditorView` API 记录两个 leaf id（先读现有用例确认取 id 的形态）；
   - act：`close` → `wait_until(leaf_count == 1)` → `await pilot.pause()` →
     对每个已销毁 leaf id 调 `panes.notify_focus(stale_id)`（若取 id 的 API
     不稳，退化为对确定不存在的 id 调 `notify_focus`，并在报告说明）；
   - assert：不抛异常、`app.is_running` 为真、活动 pane 未被切换。
   用例名与三要素齐全；注释英文 ASCII；不改其它用例。

## 4. 验收命令（逐条记录退出码）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_app_panes.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_app_panes.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_app_panes.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/test_app_panes.py -q -n 1
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
```
判据：前 4 次**全部** exit 0（不得用「重跑即过」结案）；pyright 0 诊断；
架构 37 用例全绿；全量 pytest 0。若任一失败，按
`python-coding-style.md` §4.7 修用例/实现，不记「偶发」。

## 5. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 宽松判空掩盖真实状态错误 | 只改 `notify_focus`（事件入口），`leaf_by_id` 保持 strict；守卫用例覆盖 | `git revert` panes 改动 |
| `find_leaf` 未在本文件导入 | 先读 `:1-40` 确认（`:133` 显示已可用），pyright 兜底 | 补正确 import（绝对导入） |
| `await pilot.pause()` 改变其它断言时序 | 只加一次，全量用例实测 4 次 | 移除 pause |
| 改动 `yate/` 触发架构守卫（UI_FREE / ASCII / 行宽） | 3 行改动 + 英文注释；架构 37 实测 | 按诊断修正 |

回滚：`git revert` 本波提交；wave-1 三份提交独立，不受影响。
