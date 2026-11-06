# W1 · 主题派生图标色与状态栏分段（palette plan-a）

## 输入

- `.trae/documents/filemgr-theme-beautify-issue.md`（需求原文 + 取证）
- 本目录 `overview.md`（总纲，波次与独占文件矩阵）
- 现状：`yate/editor_components/icons.py::icon_color` 固定 Seti hex；
  `yate/editor_components/file_manager/model.py::build_row_text` 只传 `accent`；
  `format_status` 有精确字符串断言（`tests/test_file_manager_model.py:163-206`）。

## 独占文件清单（只改这三个）

- `yate/editor_components/icons.py`
- `yate/editor_components/file_manager/model.py`
- `tests/test_file_manager_model.py`

## 设计（严格按 `python-coding-style.md`，pep695 `type` 语句、完整注解、英文注释/docstring）

### 1. `icons.py`

- 新增 `type IconPalette = dict[str, str]`（模块级 `#:` 注释说明键集合与 `SETI_COLORS` 一致）。
- `icon_color(name, is_dir, dir_color, palette: IconPalette | None = None) -> str`：
  - `is_dir` 仍返回 `dir_color`；
  - `palette is None` 时保持原行为（`SETI_COLORS[key]` / `ICON_COLOR_FALLBACK`），**explorer 零影响**；
  - `palette` 提供时按同一 key 查 `palette`，缺省回落 `palette["grey"]`；
  - docstring 写明「默认路径保留 Seti 固定色，注入路径供主题自持组件使用」。
- 不新增任何 yate import，不新增依赖。

### 2. `model.py`

- 新增 import：`IconPalette`（自 `yate/editor_components.icons`）、`Theme`（自 `yate/editor_components.theme.themes`）。
  同层 L2 → L2，不产生向上连线；`model.py` 仍是纯数据层（颜色经参数传入）。
- `themed_icon_palette(t: Theme) -> IconPalette`：把 8 个 Seti key 映射到 `Theme` 字段
  `blue→accent`、`green→green`、`yellow→yellow`、`orange→orange`、
  `purple→accent2`、`red→red`、`pink→accent2`、`grey→fg_dim`；返回新 dict。
- `build_row_text(..., *, icon_palette: IconPalette | None = None)`：把 palette 传给
  `icon_color`；不传时行为与 HEAD 完全一致（既有调用零改动）。
- 抽出 `_status_parts(...) -> list[str]`（原 `format_status` 的 parts 构造，逐字保持），
  `format_status` 改为 `_SEP.join(_status_parts(...))`，**输出字符串必须与 HEAD 逐字一致**。
- 新增 `format_status_text(stat, index, total, sort_key, descending, filter_active,
  marked_count, *, fg: str, fg_dim: str, width: int) -> Text`：
  - 左段 `parts[0]`（属性），中段 `_SEP.join(parts[1:3])`（位置 + 排序），
    右段 `_SEP.join(parts[3:])` 或 `f"{total} entries"`（统计与筛选）；
  - 段间分隔符 ` \u2502 ` 用 `fg_dim` 着色，段文本用 `fg`；
  - 按 `width` 在中段与右段之间补空格把右段推到右侧（`max(0, width - used)`），
    `width <= 0` 时退化为无补白；
  - 不写死任何色值，不 import `theme`（颜色全部由参数传入）。

### 3. `tests/test_file_manager_model.py`

- `test_icon_color_default_keeps_seti_palette`：不传 palette 时文件图标色仍为 `SETI_COLORS` 值。
- `test_icon_color_uses_injected_palette`：注入 palette 后按扩展名取主题色，未知扩展回落 grey。
- `test_themed_icon_palette_tracks_theme_fields`：自定义 `replace(THEMES["mocha"], accent=..., fg_dim=...)`
  后对应键变化。
- `test_format_status_unchanged_after_refactor`：原有用例保持不动（回归守卫）。
- `test_format_status_text_has_three_themed_segments`：断言三段文本、`fg_dim` 分隔符 span、补白不吞关键字串。

## 输出

- `icon_color` 具备可选注入式调色板，`explorer` 行为不变。
- `themed_icon_palette` 与 `format_status_text` 为 W2 提供稳定 API。
- 模型层新用例全绿。

## 可执行验收命令（工作目录 worktree）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_file_manager_model.py -q
.venv\Scripts\python.exe -m pyright yate/editor_components/icons.py yate/editor_components/file_manager/model.py
git diff --check
```

判据：pytest exit code 0（本机 `-q` 无汇总行）；pyright 零诊断；`format_status` 字符串逐字不变。

## 风险与偏离

- 偏离：`model.py` 新增对 `theme.themes.Theme` 的类型依赖（同层、纯类型用途）。若 pyright 报
  向上连线守卫（不太可能，二者同为 L2），改为把 palette 构造移到 `screen.py`，并在此显式记录。
- 回滚：三文件 `git checkout HEAD -- <file>`。
