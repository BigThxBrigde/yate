# W3 · 用例、截图基线与文档同步（verify plan-c）

## 输入

- W1 + W2 全部落地；总纲 `overview.md`；`tests/test_file_manager.py` 既有 helper
  （`_status_text` / `_list` / `_Host` / `_screen` / `wait_until`）。
- `tools/screenshots/scenarios.py:402-426` 的确定性 SVG 场景；
  `screenshots/README.md:167-173` 双语条目；
  `.trae/rules/architecture-boundaries.md:311-323` 的豁免行数登记。

## 独占文件清单（只改这四个）

- `tests/test_file_manager.py`
- `screenshots/file-manager.svg`
- `screenshots/README.md`
- `.trae/rules/architecture-boundaries.md`

> `tests/test_file_manager_model.py` 属于 W1 独占，W3 不得改。

## 设计

### 1. `tests/test_file_manager.py` 新增用例（沿用既有 pilot helper，禁真实 sleep）

1. `test_file_manager_headers_and_theme_driven_borders`：
   - 三个栏头 `Static` 存在且文本非空；`#file-manager.border_title` 为当前目录路径；
   - `#file-manager-parent` / `#file-manager-list` 的 `styles.border_right` 非空、
     `#file-manager-status` 的 `styles.border_top` 非空；
   - `ListItem.-highlight` 的 `styles.background == Color.parse(theme.active().accent2)`
     （`$primary` 桥映射，F6），栏头 `styles.color` 同色；
   - 断言 TCSS 资源里不含 `#`/`rgb(` 等硬编码色（文本读取 `load_tcss` 资源内容）。
2. `test_file_manager_fullscreen_keeps_outer_border`：
   `fullscreen=True` 时 `#file-manager` 的 `styles.border` 仍非空，且 region 断言沿用既有用例口径。
3. `test_file_manager_highlight_row_drops_span_colors`：
   `pilot.press("j")` 后用 `wait_until` 等 `list_view.index == 1`，
   断言旧行 `_Row.render()` 有 span、新行 `-highlight` 类成立且 `_Row.render().spans == []`；
   再按 `k` 回去断言旧行恢复 span（覆盖总纲 R1）。
4. `test_file_manager_icon_colors_follow_theme_but_explorer_does_not`：
   `theme.set_theme(...)` 前后 `screen._icon_palette["blue"]` 等于 `theme.active().accent`、
   行内图标 span 随之变化；同时 `icon_color("a.py", False, "x") == SETI_COLORS["blue"]`
   （explorer 默认路径零影响）；`finally` 恢复原主题。
5. `test_file_manager_custom_theme_repaints_chrome`：
   `replace(THEMES["mocha"], panel=..., accent2=..., fg=...)` 注册自定义主题并切换，
   断言边框背景 / 高亮背景 / 栏头色 / 状态栏分段色取自新主题；`finally` 恢复。

> 已有 `test_file_manager_theme_switch_rebuilds_row_colors`（约 `:480-505`）保持不动；
> 新增用例不得改动既有 helper 与断言。

### 2. `screenshots/file-manager.svg`

- 用 `.venv\Scripts\python.exe -m tools.screenshots --only file-manager` 重新生成；
- 人工核对（读取 SVG 文本）确认：外框、栏间分隔、栏头、高亮行、状态栏分段元素存在，
  颜色串来自主题色板而非预览图蓝/绿；机器路径仍被 `scrub_svg` 脱敏。

### 3. `screenshots/README.md`

- file-manager 条目 EN/ZH 两行同步补充「themed borders / column headers / highlighted row」，
  双语成对更新（`doc-conventions.md` §三 精神）。

### 4. `.trae/rules/architecture-boundaries.md`

- 实测 `screen.py` 的 `splitlines()` 行数，把 §三.7 豁免条目中登记的 963 行更新为真实值，
  并追加一行本波说明（`SIZE_EXEMPT_FILES` 集合本身不变，两处同步口径保持不变）。

### 5. 手册

- `yate/resources/manual.{en,zh}.md` 与 `yate/docs/` 只描述命令与行为（取证：仅三处提及
  `:file-manager` / `Alt+Shift+F`），本次不改行为与键位 → **不改手册**，在总纲回填记录说明。

## 输出

- 新增 5 条 pilot / 契约用例；SVG 基线反映新外观；文档与规则行数登记同步。

## 可执行验收命令（工作目录 worktree）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_file_manager.py tests/test_file_manager_model.py tests/test_theme_palettes.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m tools.screenshots --only file-manager
.venv\Scripts\python.exe -m tools.smoke_test compare --scenario file_manager_startup_navigation
git diff --check
```

判据：pytest exit 0（`tests/test_architecture.py` 由 W4 全量门禁跑）；
pyright 零诊断；截图 exit 0；`compare` 的 checks 不漂移（`svg_rows` 默认丢弃，
纯视觉改动靠 SVG 人工核对，符合 F11）。

## 风险与偏离

- 若 `styles.border_right` 在无边框时不是 `None`（Textual 默认返回空元组），改为断言
  `tuple(...)` 非空或读 TCSS 文本；实测后回填。
- 若自定义主题注册触发全局状态污染，用例须在 `finally` 里 `register_theme` 恢复原主题
  并 `theme.set_theme(original)`。
- 回滚：四文件 `git checkout HEAD -- <file>`（SVG 为二进制式大文本，同样可回滚）。

## 实现偏离（已回填总纲 §八.3 / §八.5）

1. `screenshots/README.md` 是 `tools/screenshots/gallery.py` 从 `scenarios.py` 的
   `desc_en` / `desc_zh` 生成的产物，直接改会被重生成覆盖；双语说明改到唯一来源
   `tools/screenshots/scenarios.py`，并用 `render_gallery` 重生成 README。
2. 状态区上边框断言从 `status.styles.border_top` 改到 `#file-manager-body` 的
   `border_top` / `border_bottom`（W2 布局修复，正向偏离）。
3. 评审迭代波补齐：按 `k` 回退后 span 恢复、输入行激活态边框与 SVG 可见性、
   `_Row` 非 Text 回退、`_refresh_highlight_rows` 越界分支、状态栏窄宽截断、
   恢复被误删的目录组排序断言。
