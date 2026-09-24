# SP6 — editor 调度与组件（N10 N19 N22 N24 N26）

> 波次二 · 规模 M · [P2 原文](../P2_nice_to_have_plan.md)为唯一规范来源。

## 独占文件清单

**产品（任务书逐文件显式授权）：**
- `yate/editor.py`（N10 N26；N24 若 prompt 流引用 `on_cancel` 属性名，一并更新）
- `yate/editor_view/terminal.py`（N19）
- `yate/editor_view/palette.py`（N22）
- `yate/editor_view/commandline.py`（N24）

**测试：** `tests/test_app_textual.py`（仅新增用例）

**不许动**：`tools/smoke_test/scenarios/`（如 N19 需冒烟场景，先上报主代理单独授权指定文件）、
其它任何文件。**架构红线**：N10 不引入跨层新依赖；R10（一次按键只派发一次）与「未识别键
fall-through」自检清单适用于 N19 的按键放行改动。

## 第 0 步：现状复核

逐条核对 P2 原文锚点（N10: 单 tab 时 `cycle_tab` 仅提示；N19: `TerminalView.on_key` 吞键仅留
toggle；N22: palette `score += 0` 死语句；N24: `PromptBar.on_cancel` 实例属性落入 `on_*`
反射命名空间；N26: `handle_key` docstring「every check is pure」不实）。P1 多波次刚改过
editor.py 与 editor_view（S12–S17、S30、S37、S40），以当前代码为基准。

## 条目执行

### N10 — 单 tab `cycle_tab` 静默 no-op

1. **输入**：P2 原文 N10 行（单 tab 时 no-op 且不提示；倾向静默）。
2. **步骤**：`cycle_tab` 入口判 `len(tabs) <= 1` 直接 return；不改其它路径。
3. **验收**：新增 pilot 用例——单 tab 下连续执行 cycle 命令断言无消息行输出、无异常；
   多 tab 循环行为不变（既有用例全绿）。

### N19 — 终端面板获焦时 `ctrl+1` 回焦编辑器

1. **输入**：P2 原文 N19 行（`TOGGLE_KEYS` 之外放行 `ctrl+1`（`focus_editor`）；`Esc` 不放行，需先确认 shell 依赖——本轮不动 Esc）。
2. **步骤**：读 `TerminalView.on_key` 现状（P1 波次二改过本文件：S16 死分支、S32 spawn 复活）；
   在按键白名单加 `ctrl+1` → 调用既有 `focus_editor` 回调；其余键维持转发 shell。
3. **输出**：终端获焦时 `ctrl+1` 把焦点交回编辑区，toggle 键行为不变。
4. **验收**：pilot 用例——进入终端获焦 → 按 `ctrl+1` → 断言焦点回到编辑区且 shell 输入流
   未收到该键；**R10 自检**：放行的键不产生二次派发。
5. **注意**：`ctrl+1` 与 kitty CSI-u（N8，决策门 G1）同域——若 G1 已拍板改绑，此处按拍板后
   的键名实现；未拍板则按 `ctrl+1` 现状实现并在报告注明关联。

### N22 — palette 死语句删除

1. **输入**：P2 原文 N22 行（`score += 0  # consecutive: best`）。
2. **验收**：删除；palette 既有用例全绿。

### N24 — `PromptBar.on_cancel` 改名 `cancel_hook`

1. **输入**：P2 原文 N24 行（实例属性改名，消除 Textual `on_*` 反射命名空间隐患）。
2. **步骤**：commandline.py 定义处 + editor.py（或其它）赋值使用点全部改名；
   grep 全仓 `on_cancel` 确认无漏网（测试替身如有同步更新——**仅限 SP6 独占文件内**）。
3. **验收**：pyright 0 诊断；prompt 既有用例全绿；全仓 grep `on_cancel` 残留 0 处（报告附结果）。

### N26 — `handle_key` docstring 修正

1. **输入**：P2 原文 N26 行（修正「every check is pure」：`try_window_prefix` 变更
   `_window_pending`、popup 分支执行 `accept_completion`）。
2. **验收**：纯 docstring；表述与当前代码行为一致（对照现实现写）。

## 收尾清单

- [ ] `.venv\Scripts\python.exe -m pyright yate/editor.py yate/editor_view/terminal.py yate/editor_view/palette.py yate/editor_view/commandline.py tests/test_app_textual.py` → 0 诊断
- [ ] `.venv\Scripts\python.exe -m pytest tests/test_app_textual.py -q` → exit 0
- [ ] 报告：改动清单 + 实跑命令与结果 + `on_cancel` 全仓 grep 结果 + N19 与 G1 的关联说明 + 校准记录

## 校准记录

（实施时回填）
