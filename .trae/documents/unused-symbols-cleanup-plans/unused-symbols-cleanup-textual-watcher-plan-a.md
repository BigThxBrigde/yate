# wave-1 / plan-a：0 参数 watcher 首样例 + 运行时证据

> 总纲 [`overview.md`](overview.md)；删除清单
> [`../unused-symbols-cleanup-delete-list.md`](../unused-symbols-cleanup-delete-list.md) #1。
> 所属波次 `wave-1: plan_a ∥ plan_b ∥ plan_c`，与另两个子计划文件互不重叠。

## 输入

- issue §二.3：以 `yate/app.py:186` 为首个样例改为无参 watcher，并补运行时/pilot
  证据证明主题变更仍触发重绘。
- 已实测的运行时探针（临时脚本 `_callback_probe.py`，不入库）：
  `count_parameters(bound 0-arg on_resize) == 0`；`invoke(w.on_resize, object())`
  → 回调执行 1 次；0 参数 reactive watcher 在构造 + 赋值时共触发 2 次；
  `pilot.resize_terminal(120, 40)` 后 0 参数 `on_resize` 计数由 1 → 2。
- Textual 8.2.8 源码：`textual/reactive.py:106-116` 的 `invoke_watcher` 显式支持
  0/1/2 三种形参数；`textual/_callback.py:45-56` 的 `_invoke` 用
  `callback(*params[:parameter_count])` 裁剪实参。

## 独占文件清单（只改这些文件）

- `yate/app.py`
- `tests/test_zero_arg_callbacks.py`（新增）

## 具体修改

| 文件:行号 | 原代码 | 新代码 |
| --- | --- | --- |
| `yate/app.py:186` | `def watch_theme(self, _theme: str) -> None:` | `def watch_theme(self) -> None:` |

- 方法体（`if self.screen_stack: self.screen.styles.background = theme.active().bg`）
  **一行不改**；docstring 未引用 `_theme`，无需同步。
- 调用点：仓内 0 处直接调用，由 Textual reactive 框架分派，无同步实参。
- 检查 `yate/app.py` 是否因该改动产生未使用导入；`str` 是内建类型，无导入。

## 新增测试（`tests/test_zero_arg_callbacks.py`）

模块 docstring 说明用途；`from __future__ import annotations` 首行；全部公共函数
带完整注解与散文式 docstring（英文 ASCII）；`App[None]` 精确标注。

### 用例 1 `test_zero_arg_watcher_fires_on_reactive_change`

- **验证目标**：证明 0 参数 `watch_*` 仍被 `invoke_watcher` 分派（构造与赋值两次）。
- **前置**：定义最小 `App[None]` 子类，`marker = reactive("before")`，
  `__init__` 建 `self.watch_calls: list[str] = []`，`compose()` yield 一个 `Static`，
  `watch_marker(self) -> None` 向列表追加 `"fired"`。
- **操作**：`asyncio.run(scenario())`，`scenario` 内 `async with app.run_test() as pilot:`
  先 `await pilot.pause()`，再 `app.marker = "after"`，再 `await pilot.pause()`。
- **断言**：`app.watch_calls == ["fired", "fired"]`（构造初值 + 赋值各一次）。

### 用例 2 `test_zero_arg_resize_handler_is_invoked_by_framework`

- **验证目标**：证明 0 参数 `on_resize` 在真实框架分派下被调用，且多余事件实参被裁剪。
- **前置**：定义 `Static` 子类，`__init__` 建 `self.resize_calls = 0`，
  `on_resize(self) -> None` 自增计数；最小 App `compose()` yield 该 widget。
- **操作**：`async with app.run_test() as pilot:` 先 `await pilot.pause()` 记录基线，
  再 `await pilot.resize_terminal(120, 40)` 与 `await pilot.pause()`。
- **断言**：结束时 `widget.resize_calls > 基线`，且过程中无 `TypeError`。

### 用例 3 `test_yate_app_watch_theme_repaints_on_theme_change`

- **验证目标**：证明改签名后真实 `YateApp` 主题切换仍触发屏幕背景重绘。
- **前置**：`from textual.color import Color`；`from yate.app import YateApp`；
  `from yate.editor_components import theme as yate_theme`；`app = YateApp()`。
  参考 `tests/test_app_manual.py:75` 的构造与 `try/finally` 恢复主题写法。
- **操作**：`async with app.run_test(size=(100, 30)) as pilot:` → `await pilot.pause()`；
  `app.editor.run_command("set theme=latte")` → `await pilot.pause()` 两次；
  读取 `app.screen.styles.background`。
- **断言**：`app.screen.styles.background == Color.parse(yate_theme.active().bg)`，
  且与切换前记录的背景值不同；`finally: yate_theme.set_theme("mocha")` 恢复默认，
  防止主题状态泄漏到后续测试。

## 验证方案与可执行验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_zero_arg_callbacks.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pytest tests/test_app_manual.py tests/test_app_render.py -q --cov-fail-under=0
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
git diff --check
```

通过判定：三条 pytest 退出码 0、pyright 零诊断、`git diff --check` 退出码 0。
用例 3 的 `wait_until` 轮询（若 `set theme` 为异步生效）按
`python-coding-style.md` §4.7 用轮询谓词，禁止依赖固定睡眠时长。

## 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 0 参数 watcher 不被分派 | 用例 1 / 3 直接拦截；已先跑运行时探针取证 | `git revert` 本波提交 |
| 主题状态泄漏导致后续用例串味 | `finally` 恢复 `mocha`，与既有主题测试同口径 | 同上 |
| 并行负载下时序 flake | 用 `wait_until` 轮询；必要时 `-n 1` 复核并按 §4.7 修用例 | 修用例，不记「偶发」 |
