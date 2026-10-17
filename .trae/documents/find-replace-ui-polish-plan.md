# find-replace-ui-polish（ctrl+h 弹窗美化 + 滚动条对齐 explorer）方案

## 一、目标与非目标

**目标**

1. `ctrl+h` 项目内查找替换弹窗（`FindReplaceScreen`）视觉向既有弹窗看齐：
   与 `PaletteScreen` / `MarkdownDocScreen` / `_OverlayScreen` 同一套边框与底色语言
   （`border: tall $primary` + `$surface`），不再是一条贴顶的整宽色带。
2. 结果区滚动条与 explorer **同源**：
   - 渲染器同源 —— `editor_view.scrollbars.apply_slim_scrollbars`（`▐` 细滑块）；
   - 调色同源 —— `editor_view.scrollbars.apply_scrollbar_theme`（轨道透明、
     滑块 `theme.border`、hover `fg_dim`、拖动 `accent`）；
   - 厚度同源 —— `app.tcss` 的全局 `Widget { scrollbar-size-vertical: 1 }` 已生效，
     本次不新增覆盖。
3. 结果区可读性微调：文件组头带文件图标（沿用 `editor_view.icons` Seti 配色）、
   组间留白、计数弱化；底部补一行键位提示（既有 `enter/r/a/alt+c/w/r` 全部已有，
   仅补可发现性），对齐 `MarkdownDocScreen` 的 footer 惯例。

**非目标**

- 不改搜索 / 替换语义、worker、去抖、光标模型（`_flat` / `_cursor` / `_render_results` 的数据口径不变）。
- 不动 L3 接线（`flows/overlay_flows.py`）、不动键位表、不改 id 契约（R9 未提及屏幕本地 id）。
- 不引入新 Protocol / 新 L3 类型层；不做架构边界变更。
- 不新增文档：手册 `resources/manual.{en,zh}.md` §7.1 描述的是行为与键位，
  本次仅补"键位提示行"，行为与键位均未变，双语手册无需改动。

## 二、调研事实（文件:行号）

| 事实 | 证据 |
|---|---|
| 弹窗当前只挂主题广播用于重绘选项 chip 与结果行，未接管滚动条 | `yate/editor_view/find_replace.py:144-160` |
| 结果区是普通 `VerticalScroll`，未注入渲染器 / 未上色调 | `yate/editor_view/find_replace.py:138-142` |
| 弹窗样式：整宽 `width: 100%`、无边框、只有底色 | `yate/resources/find-replace-screen.tcss:7-13` |
| Input 被压成 `border: none` + `padding: 0`，字段无可见轮廓 | `yate/resources/find-replace-screen.tcss:17-23` |
| explorer 的滚动条由组件自持：`apply_slim_scrollbars` + `apply_scrollbar_theme` + `theme.attach` | `yate/editor_view/explorer.py:243-249`、`279` |
| 同一模式已在 palette / manual / diff / editor view 复用（可照抄的先例） | `yate/editor_view/palette.py:121-138`、`yate/editor_view/manual.py:154-172` |
| `VerticalScroll` 的 MRO 无 `on_mount` 可链（manual 的 `DocScroll` 已注明） | `yate/editor_view/manual.py:157-164` |
| 滚动条主题调色语义（轨道透明 / 滑块 border / hover fg_dim / 拖动 accent） | `yate/editor_view/scrollbars.py:114-131` |
| 文件图标与 Seti 配色现成可用 | `yate/editor_view/icons.py:92-96`、`170-179` |
| 全局滚动条厚度已统一为 1 | `yate/resources/app.tcss:43-48` |
| Input 默认 `height: 3` + `border: tall`，`border: none` 后仍是 3 行高但无轮廓 | Textual 8.2.8 `Input.DEFAULT_CSS` 实测 |

## 三、备选方案与否决理由

| 方案 | 结论 |
|---|---|
| A. 只在 tcss 里改配色，不动滚动条 | **否决**：Textual 的 `scrollbar-color` 变量来自 Textual 主题（`$scrollbar`），与 yate 主题的 `theme.border` 不同源；且默认渲染器仍是整格反白滑块，与 explorer 的 `▐` 细滑块不一致——正是用户点名要对齐的部分。 |
| B. 类级 `ScrollBar.renderer = SlimScrollBarRender` 进程级 patch | **否决**：违反 R13 与架构测试 `test_no_class_level_scrollbar_renderer_patch`（T1）。 |
| C. 在 `FindReplaceScreen.on_mount` 里 `query_one` 结果区再注入 | **否决**：屏幕的 `on_mount` 与子组件挂载时序耦合（child 尚未 ready 时会抛 NoMatches）；且会把「滚动条归组件自持」的 R13 职责上提到屏幕层。 |
| D. 仿 `manual.DocScroll`：结果区做成 `VerticalScroll` 子类，自持滚动条与主题 | **采纳**：与 palette / manual / diff 完全同构的既有先例，零新概念，R13 归位。 |
| E. 弹窗宽度沿用 `width: 100%` 贴顶 | **否决**：与 palette（70%/max 90）、manual（90%/90%）、overlay（90%/85%）三个弹窗的视觉语言冲突；改为居中定宽 + `border: tall $primary`。 |
| F. 结果行整行高亮（背景色块） | **否决**：单 `Text` 渲染里整行背景需要按行拼接样式并自行算宽，且与 explorer 的 `$foreground 6%` 光标语义不完全等价；现保留 `>` 标记 + 匹配片段 `match_bg`，只做组头与间距美化。 |

## 四、分步实施计划

### 步骤 1：结果区滚动条同源化（组件自持）

- 文件：`yate/editor_view/find_replace.py`
- 改动：新增 `class _ResultsScroll(VerticalScroll)`（照 `manual.DocScroll`）：
  `on_mount` → `apply_slim_scrollbars(self)` + `_apply_theme()` + `theme.attach(self, self._apply_theme)`；
  `on_unmount` → `theme.detach(self)`；`_apply_theme` → `apply_scrollbar_theme(self)`。
  `compose()` 里 `VerticalScroll(id="fr-results-scroll")` 换成 `_ResultsScroll(...)`（id 不变）。
- 输出：滚动条渲染器与调色和 explorer 完全同源。
- 验收：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_app_find_replace.py -q
  ```
  探针（发现式，不落盘）：push 屏幕后断言
  `scroller.vertical_scrollbar.renderer is SlimScrollBarRender` 且
  `scroller.styles.scrollbar_color.hex == theme.active().border`。

### 步骤 2：弹窗布局与输入行轮廓

- 文件：`yate/resources/find-replace-screen.tcss`
- 改动：
  - `#find-replace`：`width: 90%` / `max-width: 120` / `margin-top: 2` /
    `max-height: 90%` / `border: tall $primary` / `padding: 0 1`（与 palette 同语言）。
  - `#fr-inputs`：`height: 4`，`border-bottom: solid $foreground 12%`（1 行分隔线，
    色值与 explorer 右边框同源）。
  - `#fr-find` / `#fr-replace`：`height: 3`、`border: tall $foreground 15%`、
    `padding: 0 1`；`:focus` → `border: tall $primary`。
  - `#fr-options`：`height: 3`、`content-align: center middle`、`padding-left: 1`。
- 输出：弹窗居中定宽带边框，两个输入框有可见字段轮廓，聚焦态用主色。
- 验收：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_app_find_replace.py -q
  ```
  几何探针：100x30 视口下 `#find-replace` 的 `region.width < 100`、
  `#fr-find.region.height == 3`、面板右缘不越界。

### 步骤 3：结果行视觉（组头 + 计数）

- 文件：`yate/editor_view/find_replace.py`（仅 `_render_results`）
- 改动：组头 `icon_for_path(path.name, False)` + 图标色（`icon_color`，目录色取
  `theme.accent`）+ 路径；计数改为 `· N` 弱化在 `fg_dim`；非首个文件组前空一行。
- 输出：结果区按文件分组更易扫读，与 explorer 的文件图标语言一致。
- 验收：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_app_find_replace.py -q
  .venv\Scripts\python.exe -m pyright yate/editor_view/find_replace.py tests/test_app_find_replace.py
  ```
  既有断言（`"alpha.txt" in plain`、`"1: "`、`"> 3: "`）必须仍成立。

### 步骤 4：页脚键位提示

- 文件：`yate/editor_view/find_replace.py`（compose 增加 `Static(id="fr-footer")` 常量文案）、
  `yate/resources/find-replace-screen.tcss`（`#fr-footer { height: 1; margin-top: 1; color: $text-muted; text-align: center; }`）
- 输出：底部一行 `enter jump · r replace file · a replace all · alt+c case · alt+w word · alt+r regex · esc close`。
- 验收：pytest 全量 + pilot 文本 dump 中能看到该行，且面板总高不超过视口。

### 步骤 5：门禁与回填

- 新增 1 条用例（`tests/test_app_find_replace.py`）：
  `test_results_scroll_aligns_with_explorer_scrollbar` —— 渲染器类型 + 调色同源断言。
- 全量门禁（主代理亲自跑）：
  ```powershell
  .venv\Scripts\python.exe -m pyright yate/ tests/ tools/
  .venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
  .venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-fail-under=75
  ```
- 回填本文件的实测前后数字与偏离记录，按 `git-commit-message.md` 提交
  （`feat(editor_view): polish the project find & replace overlay`），只提交不推送。

## 五、风险与回滚

| 风险 | 应对 |
|---|---|
| `height: auto` 面板 + `height: 1fr` 滚动区在 `max-height: 90%` 下的高度结算变化，可能影响 `test_results_pane_scrolls_to_keep_cursor_visible` | 步骤 2 后用 45 条命中的几何探针实测 `scroll_offset.y > 0` 与面板不越界；异常则回退为 `max-height: 100%` |
| 组头加图标后，既有 `_results_plain` 子串断言误伤 | 断言只依赖 `alpha.txt` / `1: ` / `> 3: ` 子串，图标是前缀，不影响；全量跑一遍确认 |
| 主题切换时滚动条不重绘 | 步骤 1 已 attch `theme.attach`，用切主题探针验证 `scrollbar_color` 随 `theme.border` 变化 |
| 回滚路径 | `git checkout -- yate/editor_view/find_replace.py yate/resources/find-replace-screen.tcss tests/test_app_find_replace.py` 单点回退，无数据/接口迁移 |

## 六、架构自检

- R3：`editor_view/*` 不 import `yate.editor` / `yate.app` —— 本次只 import
  `yate.editor_view.{icons,scrollbars,theme}`，同层内引用。
- R13：滚动条 per-widget 注入（`apply_slim_scrollbars`），无类级 patch；主题上色由组件自持。
- R9：新增 id（`fr-footer`）为屏幕本地，外壳 `app.tcss` 未引用，无需同步。
- R2 / R6 / §三.6：不新增 Protocol / TYPE_CHECKING / 类，只加一个 `VerticalScroll` 子类
  （与 `manual.DocScroll` 同构的渲染容器，属 UI 组件，非"能不能用函数"的范围）。

## 七、执行记录

执行日期：2026-10-17。分支 `feat/find-replace-ui-polish`（worktree
`../yate-find-replace-ui-polish`，沙箱自证 `import yate` 指向该 worktree）。
实施最初在 master 工作树完成，用户随后要求整体迁入新分支 worktree，
master 已复位回 origin/master（本地 docs 提交随本分支保留）。

### 实测前后数字

| 项 | 前（master 工作树） | 后 |
|---|---|---|
| 结果区滚动条渲染器 | `ScrollBarRender`（整格反白） | `SlimScrollBarRender`（`▐` 细滑块，与 explorer 同类） |
| 滚动条滑块色 | `#594A74`（Textual 由应用主题推导） | `#45475A` = `theme.active().border`（同一 `apply_scrollbar_theme`） |
| 弹窗 region（104x30） | `Region(0,0,104,30)` 占满整屏 | `Region(5,2,93,25)` 定宽居中 + 边框 |
| 非光标行命中片段 | 前景落到终端默认色，亮黄底上不可读 | `on_accent if dark else fg`，可读 |
| 结果区滚动锚定 | 每次重绘把光标行顶到第一行（组头被挤掉） | 仅光标行离开可视窗口才滚动 |

门禁（worktree 沙箱内主代理亲测）：
`pyright yate/ tests/ tools/` → 0 errors（退出码 0）；
`pytest tests/ -q --cov=yate --cov-fail-under=75` → 2489 collected 全绿、
覆盖率 91.94%（退出码 0）；`pytest tests/test_architecture.py -q` → 31 passed；
`tools.smoke_test run` → 110/112 scenarios、1347/1354 checks。

几何探针（13 个视口：104x30 … 50x16）：面板始终 `bottom <= 视口高`、
结果区恒 `>= 2` 行、新搜索 `offset == 0`（组头可见）、页脚在 `< 20` 行视口
隐藏（`FOOTER_MIN_HEIGHT`）、窄终端下自动增高不截断。

### 偏离计划项（均附实测依据）

1. 步骤 3 扩为"结果区可读性"：出预览图时发现非光标行命中不可读（前景落到
   终端默认色）、片段保留原缩进行首参差、每次重绘把光标行顶到第一行挤掉组头，
   一并修复（前景分支、`lead` 去公共缩进、`_ensure_cursor_visible` 条件滚动）。
2. 命中前景取 `t.on_accent if t.dark else t.fg`：实测 WCAG vs `match_bg`
   ——深色 8.10-14.76（on_accent），浅色 latte 3.05 / onelight 3.55 /
   gruvbox-light 3.07（fg）。gruvbox-light 是例外（on_accent 3.33 更优），
   该主题无候选达 4.5（match_bg 为中亮度琥珀色），重新调色登记为主题层待办。
3. Textual 8.2.8 不支持 `@media`（tokenizer 报
   `Expected selector or end of file`）：短视口隐藏页脚改为组件自持的
   `FOOTER_MIN_HEIGHT = 20` + `on_resize -> _sync_footer`（R13 归位，
   不触碰外壳 CSS）。
4. `_ensure_cursor_visible` 上滚目标为光标行本身而非 `cursor_line - 1`：
   后者在"组内第一条命中"上目标等于自身，后续渲染判定已可见而不再回滚，
   组头永久差一行（实测 offset 停在 1）；改为标准列表行为（上滚时光标行
   齐上缘），新增跨组上滚用例守护。

### 评审迭代

- 第一轮（code-review-expert）：REQUEST_CHANGES —— 3 个 `[WARNING]`
  （页脚窄终端被换行截断 / 视口 ≤16 行结果区塌到 1 行且组头不可见 /
  浅色主题命中对比度不足）+ 3 个 `[SUGGESTION]`（重复 `asyncio.run` /
  上滚分支无覆盖 / 光标行行号无视觉差异），逐项修复。
- 复评：可合并。N1（注释与实测不符：gruvbox-light 上 fg 反而更差）已修正
  注释；N2（首帧不滚动的收敛前提）已写入注释；N3（上滚用例扩为跨组）与
  N4（页脚可见性用例）已补。
- 登记待办（不在本轮范围）：浅色主题 `match_bg` 亮度重调（使命中前景达
  WCAG AA）；`editor.py:615` 与本模块的前景选型统一到 `Theme` 派生槽位。

### 已知环境噪音（非本次引入）

- 全量跑时 `test_shell.py::test_run_shell_timeout_kills_the_grandchild_process`
  偶发失败（进程收割时序），单测与复跑均通过——按 subagent-workflow §三.3
  先复跑确认，不改断言。
- 冒烟失败集（`replace_single_all` / `replace_all_clamp`，共 7 checks）在
  master 基线上以 `git stash` 对照复现完全相同，属存量失败：走 F4 缓冲区
  替换循环（`prompt_flows`），不经过 `FindReplaceScreen`。
