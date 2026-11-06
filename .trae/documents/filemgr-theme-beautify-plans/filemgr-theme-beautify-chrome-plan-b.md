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
git diff --check
```

判据：pyright 零诊断；既有 `tests/test_file_manager.py` 全绿（尤其
`test_file_manager_fullscreen_css_class_switches_layout` 的 region 断言与
主题切换用例）；截图命令 exit 0 且能渲染（此时 SVG 先不提交，W3 统一生成基线）。

## 风险与偏离

- R1（总纲）：高亮行重绘时机由新增用例在 W3 验证；若类变化不触发 `_Row.refresh()`，
  在 `_restore_index` / `action_*` 的索引赋值点补 `call_after_refresh` 重绘，并回填偏离记录。
- R3：全屏 region 断言若因边框变化失败，先实测 region 语义，按「改断言不改需求」处理并记录。
- 回滚：两文件 `git checkout HEAD -- <file>`。

## 实现偏离（W3 修复波，已回填总纲 §八.2）

初版把 `border-bottom` / `border-top` 放在高 1 的 `#file-manager-head` /
`#file-manager-status` 上；探针 + SVG 实证这两个容器被自身边框吃掉唯一的内容行，
栏头与状态栏文字完全不可见。改为由 `height: 1fr` 的 `#file-manager-body` 承载
`border-top` / `border-bottom`，栏头与状态栏不再自带纵向边框。评审 M3 后
`#file-manager-input.active` 另补 `height: 2 + border-top`，避免同一问题复发。
W3 用例的边框断言随之改到 body，并新增 SVG 栏头可见性守卫。

## 后续视觉修订（2026-11-06 用户反馈）

按实机截图：删除 `#file-manager` 的 `border: tall $panel` 与三条 `border-title-*`
（最外层黑框与顶部路径行一并去掉），`screen.py` 不再设置 `border_title`；
`#file-manager-head` / `#file-manager-status` 背景由 `$panel` 改为 `$surface`
（`mocha` 下 `#181825` → `#313244`）。浮层 / 全屏两形态均不设外框，但仍保留三栏
竖向 `solid` 分隔与 `#file-manager-body` 的上下横向规则。用例改为断言
`frame.border_title` 为空、外框非 `tall`、页头页脚背景与容器同色、SVG 无
`▔` / `▁`；自定义主题用例改断言背景跟随 `custom.surface`。

## 第二次视觉修订（2026-11-06 用户反馈第二波）

页眉 / 页脚的单行文字贴着条带上沿（用户反馈「垂直往下掉不居中」）。Textual 8.2.8
的 1 行盒 `vertical_excess_space=0`，`content-align: ... middle` 是 no-op；探针实测
`height: 2 + middle` 文字仍落第 1 行，`height: 3 + middle` 才落在第 2 行。本波把
`#file-manager-head`、`#file-manager-head > Static` 与 `#file-manager-status` 统一改为
`height: 3` + `content-align: left middle`（水平仍左对齐），文字落在条带正中、上下各
1 行留白；配色不动，仍全走主题令牌。代价：浮层 80% 高度下内容区少 4 行。

验收：`tests/test_file_manager.py` 新增
`test_file_manager_header_and_footer_are_vertically_centered`（styles + SVG 上下空白行
断言），`screenshots/file-manager.svg` 重生成；几何实测与另一缺陷（命令面板重复，
不属本子计划范围）见本目录 `overview.md` §八 偏离 11。
