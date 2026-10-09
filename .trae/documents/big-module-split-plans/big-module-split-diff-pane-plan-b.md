# 波次 b：diffview → diff_pane（issue IKK5F7）

## 目标

`yate/editor_view/diffview.py`（1035 行）拆为：

- 新增 `yate/editor_view/diff_pane.py`（~490 行）：
  - 纯数据/纯计算：`PaneDiffState`（原 79–94）、`_BADGES`（203–209）、
    `_TINTS`（211–218）、`_line_background`（221–230）、`_in_spans`（507–509）；
  - 编辑键表区（97–195）：`_undo`、`_vim_arm_dd`、`_vim_insert_at`、
    `_vim_append_at`、`_vim_open_below`、`_vim_word_end`、`_vim_inert`、
    `_VSC_EDIT_KEYS`、`_VIM_EDIT_KEYS`、`_VIM_INSERT_KEYS`；
  - widget：`DiffPane` 全类（233–504，含 `PaneChanged` 消息、主题订阅、
    `render_line`、编辑键分流、`_reveal_cursor`）。
- `diffview.py` 瘦身（~600 行）：docstring 改 screen 视角；保留
  `MAX_DIFF_LINES`（65–70，overlay_flows 依赖）、`RECOMPUTE_DEBOUNCE_SECONDS`
  （72–76）、`_2WAY_ROLES`/`_3WAY_ROLES`（516–517）、`DiffScreen` 全类
  （520–1035，文件共 1035 行）。

## import 方向（无环）

`diffview.py → from .diff_pane import DiffPane, PaneDiffState`（单向）。
`diff_pane.py` 依赖 textual/rich + `yate.editor_core.{buffer,document,
textobjects}` + 同包 `.theme` / `.scrollbars`；不 import `yate.editor` /
`yate.app`（R3 ✓）；不再需要 `asyncio`、`yate.editor_core.diff`、
`yate.keymaps`（仅 screen 用）。

## 外部 import 面同步（DiffPane 4 处）

`tests/test_diffview.py`、`tests/test_diff_integration.py`、
`tests/test_command_path_args.py`、`tools/smoke_test/scenarios/diffview.py`
改从 `yate.editor_view.diff_pane` import `DiffPane`（`DiffScreen`/
`MAX_DIFF_LINES` 路径不变）。核查 `tests/test_architecture.py:168` 模块清单
与 `yate/resources/diff-view.tcss:2` 注释。

## 架构守卫

无新增 `editor_view` 导入面（同包内部切分），`UI_FROZEN_FILES` 不动；
`flows/overlay_flows.py` 的既有冻结条目 `yate.editor_view.diffview`
（`tests/test_architecture.py:165–173`，overlay_flows 只取 `DiffScreen` /
`MAX_DIFF_LINES`，二者留在 diffview.py）已核实无需改动。

## 规则侧同步

- 行数守卫豁免集合（`tests/test_architecture.py`）移除
  `editor_view/diffview.py`；
- `.trae/rules/architecture-boundaries.md` §三.7 豁免名单同步移除
  `editor_view/diffview.py` 条目。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/editor_view/
.venv\Scripts\python.exe -m pytest tests/test_diffview.py tests/test_diff_integration.py tests/test_command_path_args.py tests/test_architecture.py -q
```

## 预估

`diff_pane.py` ~490；`diffview.py` ~600。
