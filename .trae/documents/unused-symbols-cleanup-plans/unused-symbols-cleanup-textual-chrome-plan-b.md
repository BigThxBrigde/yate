# wave-1 / plan-b：chrome / diff 的 0 参数 resize 回调

> 总纲 [`overview.md`](overview.md)；删除清单
> [`../unused-symbols-cleanup-delete-list.md`](../unused-symbols-cleanup-delete-list.md) #2-4。
> 所属波次 `wave-1: plan_a ∥ plan_b ∥ plan_c`，文件与 plan-a / plan-c 互不重叠。

## 输入

- 运行时探针实测：`textual/_callback.py:45-56` 按 `count_parameters` 裁剪实参，
  0 参数 `on_resize` 在 `pilot.resize_terminal` 后仍被调用（见 plan-a 证据用例 2）。
- AST 事实：3 个形参在函数体内均无 `Load` 引用；仓内 0 处直接调用。

## 独占文件清单（只改这些文件）

- `yate/editor_components/chrome.py`
- `yate/editor_components/diff/pane.py`

**不得**触碰 `yate/editor_components/diff/pane.py:106` 的 `_vim_inert(pane)`——它是
keymap 表固定签名回调，已在登记表登记保留。

## 具体修改

| 文件:行号 | 原代码 | 新代码 |
| --- | --- | --- |
| `yate/editor_components/chrome.py:163` | `def on_resize(self, _event: Resize) -> None:` | `def on_resize(self) -> None:` |
| `yate/editor_components/chrome.py:313` | `def on_resize(self, _event: Resize) -> None:` | `def on_resize(self) -> None:` |
| `yate/editor_components/diff/pane.py:282` | `def on_resize(self, _event: Resize) -> None:` | `def on_resize(self) -> None:` |

- 三个方法体（`refresh_tabs()` / `refresh_crumbs()` / `_update_virtual_size()`）
  **一行不改**；docstring 未引用事件参数，无需同步。
- **连带复核**：逐文件检查 `Resize` 类型导入（通常来自 `textual.events` 的
  `from textual.events import Resize` 或 `from textual import events` 写法），
  若该文件已无其它 `Resize` 引用则删除该导入——pyright strict
  `reportUnusedImport` 是硬门槛。若同文件其它方法仍使用 `Resize`，保留导入。
- 调用点：主要由 Textual 事件分派；**wave-1 实测校正**：`tests/test_terminal.py:552`
  有一处 `view.on_resize(Resize(...))` 直接调用（属 `TerminalView`，由 plan-c 与
  主代理同步为 `view.on_resize()`），本子计划的两个 `chrome.py` / `diff/pane.py`
  方法无直接调用；无关键字实参需同步。

## 测试用例与验证方案

不新增用例（plan-a 的用例 2 已覆盖 0 参数 `on_resize` 的框架分派契约），
本子计划以既有渲染 / 布局回归为行为一致证据：

- `tests/test_app_render.py`：页签栏与面包屑渲染、主题切换后重绘。
- `tests/test_diff.py` / `tests/test_diff_pane.py`（以仓库实际文件名为准）：
  diff 面板虚拟尺寸与 resize 路径。
- `tests/test_terminal.py:552` 附近：resize 事件派发路径（若该用例直接调用
  `on_resize(event)`，须核对是否因签名变化受影响；AST 调用点清单显示它是
  另一个对象的方法调用，不改）。

## 可执行验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_app_render.py tests/test_terminal.py -q --cov-fail-under=0
git diff --check
```

通过判定：pyright 零诊断、pytest 退出码 0、`git diff` 只含三处签名与必要的
未使用导入删除。

## 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 删除 `Resize` 导入后其它函数仍隐式引用 | pyright 全仓零诊断拦截 | 恢复导入或 `git revert` 本波提交 |
| resize 事件对象被裁剪后方法体异常 | 方法体不读事件参数；既有渲染用例回归 | `git revert` |
