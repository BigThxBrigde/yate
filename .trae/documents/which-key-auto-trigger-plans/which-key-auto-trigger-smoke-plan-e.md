# wave-3 / plan-e：目标态 Textual pilot 冒烟场景

- 总纲：[overview.md](overview.md)；主计划：[../which-key-auto-trigger-plan.md](../which-key-auto-trigger-plan.md)
- 依赖：wave-2 `plan-c`（门控与注入已落地）；wave-1 `plan-a`（`YateConfig(which_key_auto=False)` 可构造）
- 同波并行：`plan-d`（`tests/**` 单测），文件互不重叠

## 一、输入

- issue §三第 1 / 2 / 3 / 7 条验收（前缀不弹、F9 仍可用、解除后不弹、既有场景零回归、vsc 不变）。
- 现状：`tools/smoke_test/scenarios/whichkey.py:1-79`（两场景 + `SCENARIOS` 注册）；`tools/smoke_test/harness.py:362-381` `new_app(config=...)`；`tools/smoke_test/scenarios/_base.py:55-66` `run_command`；`tools/smoke_test/scenarios/__init__.py:36,66` 已展开本模块 `SCENARIOS`（新增条目自动纳入，无需改该文件）。
- CLI 实测：`python -m tools.smoke_test run --scenario NAME --jobs N` 可用；默认不比对 SVG baseline（`--with-svg` 才比较）。

## 二、独占文件清单（只改这一个文件）

1. `tools/smoke_test/scenarios/whichkey.py`

禁止改动 `tools/smoke_test/scenarios/__init__.py`、baseline JSON、`harness.py`、任何产品源码或文档。

## 三、具体修改

1. 模块 docstring（`:1-14`）从「Two scenarios」改为三个场景，补一句新场景验证 `which_key_auto=False`：自动弹出关闭但 `<f9>` 钉住仍工作；注释 / docstring 全 ASCII。
2. 新增顶层绝对导入 `from yate.config import YateConfig`（放在既有项目内导入组，按字母序；禁相对导入）。
3. 新增 `async def _which_key_auto_off_manual_toggle(tmp: Path) -> ScenarioResult:`：
   - arrange：`app = new_app(target=tmp / "scratch.txt", config=YateConfig(which_key_auto=False))`；`async with app.run_test(size=(100, 30)) as pilot:`；`await pilot.pause()`；`await run_command(pilot, "vim")`；`panel = app.editor.which_key_panel`；`checks: list[Check] = []`。
   - act / assert（逐条 `Check(label, expected, actual)`）：
     1. `Check("in_vim", "vim", app.editor.keymaps.name)`。
     2. `Check("starts_hidden", False, panel.display)`。
     3. `await pilot.press("d")` + `await pilot.pause()` → `Check("prefix_pending", "d", app.editor.keymaps.active.pending_prefix())`、`Check("auto_hidden_on_prefix", False, panel.display)`。
     4. `await pilot.press("escape")` + `pause`（清理 / 继续，不对其效果下断言）。
     5. `await pilot.press("ctrl+w")` + `pause` → `Check("chord_pending", True, app.editor.window_flows.window_pending)`、`Check("auto_hidden_on_chord", False, panel.display)`。
     6. `await pilot.press("escape")` + `pause`；`Check("chord_cancelled", False, app.editor.window_flows.window_pending)`（沿用既有场景的取消语义）。
     7. `await pilot.press("f9")` + `pause` → `Check("manual_pinned_visible", True, panel.display)`、`Check("manual_pinned_title", "vim", panel.border_title)`。
     8. `await pilot.press("g")` + `pause` → `Check("pinned_not_overwritten", True, panel.display)`、`Check("pinned_title_still_vim", "vim", panel.border_title)`（钉住态不被前缀覆盖）。
     9. `await pilot.press("f9")` + `pause` → `Check("manual_unpinned_hidden", False, panel.display)`。
     10. `await pilot.press("g")` + `pause` → `Check("no_auto_after_unpin", False, panel.display)`（隐藏后再敲前缀不重新弹出）。
   - `rows = snapshot_svg(app, tmp)`；`return ScenarioResult("which_key_auto_off_manual_toggle", checks, rows)`。**不新增 baseline 文件**：默认 `run` 不比对 SVG，且 `run` 在 `options.svg=False` 时会清空 rows；若收尾 `--with-svg` 门禁要求 baseline，由主代理显式生成并回填偏离。
4. `SCENARIOS`（`:76-79`）追加 `Scenario("which_key_auto_off_manual_toggle", _which_key_auto_off_manual_toggle, ("view",))`；既有两条场景**一行不改**。

## 四、验证方案与可执行验收命令

- 验证目标：真实 Textual App 中「auto off + 总开关默认 on」下，vim 挂起前缀 / `ctrl+w` 和弦都不推面板、组合键本身仍完成；F9 钉住 / 解除可用；解除后不自动弹出；既有 `which_key_toggle` / `which_key_ctrl_w_chord` 零回归。
- 命令（worktree cwd，PowerShell）：

```powershell
.venv\Scripts\python.exe -m pyright tools/smoke_test/scenarios/whichkey.py
.venv\Scripts\python.exe -m tools.smoke_test run --scenario which_key_toggle --scenario which_key_ctrl_w_chord --scenario which_key_auto_off_manual_toggle --jobs 1
git diff --check
```

- 通过判定：三条退出码 0，三个场景 checks 全绿。出现偶发失败先 `--jobs 1` 重跑确认（本命令已是串行），仍失败则查断言依赖的状态契约，不得直接放宽断言（既有 flake 教训）。
- 主代理收尾另跑 `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` 全量（含新场景）。

## 五、输出

- 第三个 which-key 冒烟场景注册成功，`("view",)` tag 与既有两条一致；`tools/smoke_test/scenarios/__init__.py` 无需改动。
- 既有两场景断言与 SVG rows 处理保持原样，零回归。

## 六、风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| `YateConfig(which_key_auto=False)` 被 `YateApp` 覆盖 | `new_app(config=...)` 已把 config 传入 `YateApp`（harness `:376-379`）；场景首条断言 `in_vim` 之外再以面板行为反证 | 回退场景，检查 config 传递链 |
| `escape` 清前缀 / 清和弦语义与假设不符 | 不对 `escape` 后的前缀下断言；`chord_cancelled` 沿用既有场景已验证的语义 | 删除该条 Check 并回填理由 |
| 钉住期间按 `g` 触发其它动作影响面板 | 断言只看 `panel.display` / `border_title`；pinned 分支优先由 `plan-c` 保证 | 调整按键序列 |
| SVG baseline 漂移 | 不新增 baseline；默认 run 不比对 SVG | 回退 `snapshot_svg` 调用或由主代理生成基线（需回填） |
| 与 `plan-d` 并发跑 Textual pilot 干扰 | 本波唯一跑 pilot 的成员，`--jobs 1`；`plan-d` 全是 headless 纯状态用例 | 串行重跑确认 |

## 七、报告格式

新增场景与 checks 数量、三条命令实测退出码、既有两场景结果、SVG baseline 处理说明、未解决项。偏离须显式列出并给依据。
