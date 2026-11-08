# wave-1 / plan-c：view / terminal / manual / find_replace 的 0 参数回调

> 总纲 [`overview.md`](overview.md)；删除清单
> [`../unused-symbols-cleanup-delete-list.md`](../unused-symbols-cleanup-delete-list.md) #5-9。
> 所属波次 `wave-1: plan_a ∥ plan_b ∥ plan_c`，文件与 plan-a / plan-b 互不重叠。

## 输入

- 运行时探针实测：`textual/_callback.py:45-56` 裁剪实参、`invoke_watcher` 支持
  0 参数；`pilot.resize_terminal` 后 0 参数 `on_resize` 被调用（plan-a 证据用例 2）。
- AST 事实：5 个形参在函数体内均无 `Load` 引用；仓内 0 处直接调用。

## 独占文件清单（只改这些文件）

- `yate/editor_components/view.py`
- `yate/editor_components/terminal.py`
- `yate/editor_components/manual.py`
- `yate/editor_components/find_replace.py`

**不得**触碰 `yate/editor_components/manual.py:265 get_content_height`（`@override`
覆写，登记表已登记保留）。

## 具体修改

| 文件:行号 | 原代码 | 新代码 |
| --- | --- | --- |
| `yate/editor_components/find_replace.py:197` | `def on_resize(self, event: Resize) -> None:` | `def on_resize(self) -> None:` |
| `yate/editor_components/manual.py:442` | `def on_resize(self, event: events.Resize) -> None:` | `def on_resize(self) -> None:` |
| `yate/editor_components/terminal.py:266` | `def on_resize(self, _event: Resize) -> None:` | `def on_resize(self) -> None:` |
| `yate/editor_components/view.py:177` | `def on_focus(self, _event: Focus) -> None:` | `def on_focus(self) -> None:` |
| `yate/editor_components/view.py:239` | `def on_resize(self, _event: Resize) -> None:` | `def on_resize(self) -> None:` |

- 五个方法体 **一行不改**（`_sync_footer()` / `_schedule_rerender()` /
  emulator+PTY resize / `panes.notify_focus` / `_update_virtual_size()`）。
- `on_key(self, event: Key)`（`view.py:240`）**不在本子计划范围**：`event` 被函数体
  读取，保留。
- **连带复核**：逐文件检查 `Resize` / `Focus` / `events` 导入是否还有其它引用，
  无引用则删除（pyright strict `reportUnusedImport` 硬门槛）；`manual.py` 若仍用
  `events.Resize` 于别处则保留 `from textual import events`。
- 调用点：主要由 Textual 事件分派；**wave-1 实测校正**：`tests/test_terminal.py:552`
  直接调用 `TerminalView.on_resize(Resize(Size(80, 24), Size(80, 24)))`，改签名后
  由主代理同步为 `view.on_resize()` 并删该用例两行未使用局部导入（见总纲 §七 D7）。
  其余四个方法无直接调用；无关键字实参需同步。

## 测试用例与验证方案

不新增用例（plan-a 用例 2 覆盖 0 参数 `on_resize` 的框架分派契约），以既有回归
作为行为一致证据：

- `tests/test_terminal.py`：终端 resize / 焦点路径。
- `tests/test_app_manual.py`：手册屏 resize 后重排。
- `tests/test_app_find_replace.py`：查找替换屏 footer 提示随视口变化。
- `tests/test_app_render.py` / `tests/test_app_textual.py`：编辑视图 focus / resize。

## 可执行验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_terminal.py tests/test_app_manual.py tests/test_app_find_replace.py tests/test_app_textual.py -q --cov-fail-under=0
git diff --check
```

通过判定：pyright 零诊断、pytest 退出码 0、`git diff` 只含五处签名与必要的
未使用导入删除。

## 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| `Focus` / `Resize` 导入被误删 | pyright 全仓零诊断 + 逐文件回读 | 恢复导入或 `git revert` |
| focus 路径 0 参数后不触发 | `panes.notify_focus` 由视图 focus 事件分派；既有 focus 用例回归 | `git revert` 本波提交 |
