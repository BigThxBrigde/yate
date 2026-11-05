# W2 · 边框体系、栏头与整行高亮（chrome plan-b）

## 输入

- W1 已落地的 `IconPalette` / `themed_icon_palette` / `format_status_text` API。
- `.trae/documents/filemgr-theme-beautify-issue.md`；本目录 `overview.md`。
- 取证 F1-F8、F12。

## 独占文件清单（只改这两个）

- `yate/resources/file-manager-screen.tcss`
- `yate/editor_components/file_manager/screen.py`

## 设计

### 1. `file-manager-screen.tcss`（组件自持 `DEFAULT_CSS` 不变，id 冻结）

颜色**只用桥接令牌**，形状沿用 `tall` / `solid` / `round` 惯例，零 hex：

- `#file-manager`：保留 `width:90% height:80% border: tall $panel background: $surface`；
  增 `border-title-color: $primary; border-title-style: bold; border-title-align: left;`
  （标题由 Python 设为当前路径，对应预览图顶部框线路径）。
- `.fullscreen #file-manager`：只保留 `width/height:100%`；**删除 `border: none`**（全屏仍有框）。
- 新增 `#file-manager-head`（`Horizontal`，`height:1`、`background:$panel`、
  `border-bottom: solid $foreground 12%`），三个 `Static` 子项宽度 `1fr/2fr/2fr`
  （与三栏对齐）、`color:$primary`、`text-style:bold`、`padding:0 1`；
  前两项 `border-right: solid $foreground 12%`。
- `#file-manager-parent` / `#file-manager-list`：保留 `padding:0 1`，各加
  `border-right: solid $foreground 12%`；`#file-manager-preview` 删除原
  `border-left: tall $panel`（避免双线），保留 `padding:0 1`。
- 选中行：`FileManagerScreen #file-manager-list > ListItem.-highlight` 与
  `... #file-manager-list:focus > ListItem.-highlight` 两条规则，均设
  `background: $primary; color: $block-cursor-foreground; text-style: bold;`
  （`$primary`←`accent2`、`$block-cursor-*` 为 Textual 派生的对比色令牌，F5 实证；
  不新增桥变量、不写死 `on_accent`）。
- `#file-manager-input`：保留 `border:none`（单行输入不被焦点框遮挡）；
  `.active` 增 `border-top: solid $foreground 12%`。
- `#file-manager-status`：`background:$panel`、`border-top: solid $foreground 12%`。
- 保留 `Widget { scrollbar-size-vertical: 1 }`。

> 实现取舍（已在总纲 §四 备选 E 否决理由中登记）：`#file-manager-status` 仍为单个
> `Static`，三段间用主题 `fg_dim` 的 `│` 分隔，状态区**上边框是真正 CSS 边框**。

### 2. `screen.py`（组件自持，R13 / R15 不越线）

- `__init__` 增 `self._icon_palette: IconPalette = themed_icon_palette(theme.active())`
  与 `self._highlighted_index: int | None = None`。
- `compose()`：`Vertical#file-manager` 内先 `yield` 一个
  `Horizontal#file-manager-head`，含三个 `Static`
  （`id="file-manager-parent-head" / "file-manager-list-head" / "file-manager-preview-head"`，
  screen-local id，不改既有 id），再是原 `#file-manager-body` / `Input` / `Static#file-manager-status`。
- `_Row`：增 `@override def render(self) -> Text`——`self.content` 为 `Text` 时，
  若 `self.parent` 带 `-highlight` 类则返回 `Text(content.plain)`（剥离 span 显式色），
  否则原样返回；非 `Text` 时降级 `Text(str(content))`。docstring 写明与 CSS 变量的分工。
- `_apply_theme`：先刷新 `self._icon_palette`，再走既有 `_rebuild_rows` / `_refresh_status`；
  额外调用 `_refresh_headers()`（栏头与外框标题）。
- `_rebuild_rows`：`build_row_text(..., icon_palette=self._icon_palette)`。
- `_icon_text(name, is_dir, name_style)` 增 `palette: IconPalette` 形参并传给 `icon_color`；
  `_render_parent` / `_render_dir_preview` 调用点传 `self._icon_palette`。
- `_refresh_status`：改用 `format_status_text(...)`（传 `theme.active().fg/fg_dim` 与
  `status.size.width - 2`）；同时调 `_refresh_headers()`。
- 新增 `_refresh_headers()`：更新三个栏头文本（父目录名 / 当前目录名 / 光标条目名，
  盘符层用 `DRIVES`）与 `Vertical#file-manager.border_title`（完整 cwd 路径）；
  纯字符串 `update()`，颜色由 TCSS 令牌负责。
- `on_list_view_highlighted`：在既有 `_refresh_preview()` / `_refresh_status()` 之前
  调 `_refresh_highlight_rows(event.list_view.index)`。
- 新增 `_refresh_highlight_rows(new_index)`：以 `self._highlighted_index` 为旧值，
  对旧/新两行的 `_Row` 调 `refresh()`（F5：`watch_index` 先同步 `-highlight` 再发消息），
  再存新值；越界索引跳过。
- `_render_list`：`clear()` 后把 `self._highlighted_index` 置 `None`（行重建后索引失效）。
- 不新增可滚动容器（R15 无需新接线）、不改 `editor.py`、不改键位/功能、不改 widget id。

## 输出

- 三栏 + 外框 + 栏头 + 状态区都有主题令牌驱动的边框；全屏态有框。
- 选中行整行使用主题高亮色；图标/目录/状态/栏头全部随主题切换。
- `explorer` 图标色不变，`format_status` 语义不变。

## 可执行验收命令（工作目录 worktree）

```powershell
.venv\Scripts\python.exe -m pyright yate/editor_components/file_manager/screen.py
.venv\Scripts\python.exe -m pytest tests/test_file_manager.py -q
.venv\Scripts\python.exe -m tools.screenshots --only file-manager
git -C D:/Programming/yate-filemgr-theme-beautify diff --check
```

判据：pyright 零诊断；既有 `tests/test_file_manager.py` 全绿（尤其
`test_file_manager_fullscreen_css_class_switches_layout` 的 region 断言与
主题切换用例）；截图命令 exit 0 且能渲染（此时 SVG 先不提交，W3 统一生成基线）。

## 风险与偏离

- R1（总纲）：高亮行重绘时机由新增用例在 W3 验证；若类变化不触发 `_Row.refresh()`，
  在 `_restore_index` / `action_*` 的索引赋值点补 `call_after_refresh` 重绘，并回填偏离记录。
- R3：全屏 region 断言若因边框变化失败，先实测 region 语义，按「改断言不改需求」处理并记录。
- 回滚：两文件 `git checkout HEAD -- <file>`。
