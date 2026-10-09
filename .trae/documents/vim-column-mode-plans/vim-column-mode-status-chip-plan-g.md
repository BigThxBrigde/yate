# vim-column-mode 子计划 g：状态栏 V-COLUMN chip 与冒烟场景（wave-3）

> 输入：plan-c 的 `VimMode.VISUAL_BLOCK`（statusbar 直接 import `VimMode`）。
> 依赖：plan-c 已合入；本计划是 wave-3 唯一子计划，收尾后跑总门禁。

## 一、目标

1. 状态栏模式 chip 显示 vim 列模式：`V-COLUMN`（沿用 NORMAL/INSERT/VISUAL/
   V-LINE 的大写 chip 惯例；issue 原文 `v-column` 按既有 chip 风格转大写——
   `V-LINE` 是同类先例，见 `yate/editor_view/statusbar.py:49`）；
2. 冒烟场景扩展：vim 键位列模式端到端（`tools/smoke_test`）。

## 二、非目标

- 不改 `Editor.mode_label`（`yate/editor.py:785-791`）——它委托 `mode_chip`
  纯函数，自动跟随；
- 不新增主题色：复用 `t.mode_visual_bg`（列模式是 visual 家族形态）。

## 三、独占文件清单

- `yate/editor_view/statusbar.py`
- `tests/test_mode_chip.py`（**新建**）
- `tools/smoke_test/scenarios/vim_advanced.py`（追加场景）

## 四、具体修改

### 1. `yate/editor_view/statusbar.py` — `mode_chip` 映射（:45-51）

```python
            mapping = {
                VimMode.NORMAL: ("NORMAL", t.mode_normal_bg),
                VimMode.INSERT: ("INSERT", t.mode_insert_bg),
                VimMode.VISUAL: ("VISUAL", t.mode_visual_bg),
                VimMode.VISUAL_LINE: ("V-LINE", t.mode_visual_bg),
                VimMode.VISUAL_BLOCK: ("V-COLUMN", t.mode_visual_bg),
            }
```

`VimMode` 已在模块顶部 import（:22），无新依赖边（L2 → L0 keymaps 既有）。

### 2. `tools/smoke_test/scenarios/vim_advanced.py` — 新场景

沿用文件内 `_vim_state` / `run_command` / `Check` 夹具，新增
`_vim_column_mode_ops(tmp)` 场景（注册进该文件的场景表，分组沿用
`("edit",)`/`("view",)` 现有归类取其一）：

- `run_command(pilot, "vim")` → chip `NORMAL`；
- `pilot.press("ctrl+v")` → chip `V-COLUMN`、`VimMode.VISUAL_BLOCK`、
  anchor == cursor；
- `pilot.press("l", "j")` → `buffer.block_region() == (0, 0, 1, 1)`；
- `pilot.press("y")` → chip 回 `NORMAL`、register 为块文本、
  `register_block is True`；
- `pilot.press("j")` + `pilot.press("p")` → 矩形回贴；
- 收尾 `run_command(pilot, "vsc")` → chip `VSC`。

注意 `pilot.press` 的 chord 拼写：Textual 名 `ctrl+v` 经
`event_to_raw` 收敛为 `\x16`（`yate/keyproto/legacy.py:127-133`），与
`tools/smoke_test/scenarios/edit.py:356` 的 `ctrl+u` 用法同源。

## 五、新增测试（tests/test_mode_chip.py 新建）

`mode_chip` 是纯函数但 `PromptBar` 是 widget——用 app-pilot 集成测试走
`Editor.mode_label()`（冒烟同构、pyright 严格下无需造 PromptBar 替身）：

| 用例名 | 前置与操作 | 断言 |
|---|---|---|
| `test_mode_chip_shows_v_column_in_visual_block` | app-pilot，`run_command "vim"`，`pilot.press("ctrl+v")` | `app.editor.mode_label() == ("V-COLUMN", <mode_visual_bg>)`（色值经 `theme.active()` 对比） |
| `test_mode_chip_back_to_normal_after_block_exit` | 同上后 `pilot.press("escape")` | `mode_label()[0] == "NORMAL"` |
| `test_mode_chip_vsc_falls_back_to_vsc_label` | vsc 键位下按 `ctrl+v`（粘贴语义，无模式变化） | `mode_label()[0] == "VSC"`（`Ctrl+V` 不误触发 chip） |
| `test_mode_chip_v_line_unchanged` | vim 键位按 `V` | `mode_label()[0] == "V-LINE"`（既有 chip 回归钉） |

## 六、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_mode_chip.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/editor_view/statusbar.py tests/test_mode_chip.py tools/smoke_test/scenarios/vim_advanced.py
.venv\Scripts\python.exe -m pytest tests/ -q
```

冒烟（手工/可选执行，依赖交互终端）：

```powershell
.venv\Scripts\python.exe -m tools.smoke_test --list
.venv\Scripts\python.exe -m tools.smoke_test vim_column_mode_ops
```

（入口模块名以 `tools/smoke_test/__main__.py` 实际为准；若冒烟入口不接受单
场景参数，则跑全量冒烟并核对新场景 Check 全绿。）

通过判定：pytest 全绿退出码 0；总门禁三条命令（overview §八）退出码 0。

## 七、风险与回滚

- 风险：本计划合入前（wave-2 期间）`VISUAL_BLOCK` 落到 `mapping.get` 默认值
  显示 `NORMAL` chip——中间态可接受（功能可用、标识暂缺），波次表已注明；
  冒烟场景属 tools 代码，受 `test_architecture.py` 体量守卫管辖（新增行数
  远低于阈值）。
- 回滚：独立 commit（`feat(statusbar): v-column chip for vim block mode`），
  单提交 revert；statusbar 与冒烟文件无其它计划触碰。

## 八、收尾（本计划承载 wave-3 收尾职责）

1. 跑 overview §八总门禁三条命令，退出码 0；
2. 回填 overview §五波次表实测结论（如有偏离记录实测依据）；
3. 按 `git-commit-message.md` 分别提交（docs / feat 分 commit）。
