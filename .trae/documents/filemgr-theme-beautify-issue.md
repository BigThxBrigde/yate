# File manager 视觉美化 issue 素材（【领会】整理稿）

本文件是 `task-orchestration.md` §二.1 的「issue 文本读取整理」产物：只整理需求原文、
约束与既有上下文事实，**不做任务分析、不产出方案**（任务分析与方案由【方案】环节承担）。
唯一规范来源：本文件 + `.trae/rules/` 8 份必读规则。

## 一、执行环境（用户指令）

- 用户指令：「进入无人值守，所有问题无须过问。根据此 issue 文本，执行新任务，
  model 始终使用 hy4，其他严格按照纪律执行」。
- 因此：方案批准、步骤确认、权限申请一律按通过处理；子代理 spawn 显式给
  `bypassPermissions`；**不向用户发起任何询问**。
- 模型分配：用户显式覆盖 `task-orchestration.md` §一.3 表格，要求所有子代理
  一律 hy4。运行时若报模型未注册，按 §一.3.5 / §三 兜底，并如实标注。
- 主仓 HEAD `75bccfa`（master，干净）；本任务 worktree 分支
  `enh/filemgr-theme-beautify`；任务名 `filemgr-theme-beautify`。

## 二、需求原文（上一轮产出的 issue 文本）

### 标题

File manager 视觉美化：按预览图重做边框与选中高亮，配色全面对齐主题

### 预览图

用户提供附件 `image.c2fff4c61f.png`（外部附件，未入库），即本 issue 的预览图：
lf / ranger 风格三栏（父目录 · 当前目录 · 预览），顶部选中行整行反色，
底部三段状态栏，列间细分隔线。**只借鉴版式与信息密度，不借鉴图中蓝/绿固定色值。**

目标线框（所有色位取自主题令牌）：

```text
┌─ ~/project ───────────────────────────────────────────────────┐ ← 外框 tall $panel
│ PARENT          │ CURRENT            │ PREVIEW              │ ← 栏头 $surface / $primary
├─────────────────┼────────────────────┼──────────────────────┤ ← 栏间 solid $border
│ bin/            │  src/              │  # brightness        │
│ docs/           │  main.py  *        │  # colorpicker       │
│ ...             │ █ selected.c █     │  # quicksettings     │ ← 选中整行 accent/on_accent
│                 │  README.md         │  # lockscreen        │
├─────────────────┴────────────────────┴──────────────────────┤ ← 状态区上边框
│ -rw-r--r-- 1 u g 5.9K ... · 3/8 · name asc │ 5.9K sum · All │ ← 三段状态栏
└──────────────────────────────────────────────────────────────┘
```

### 一、背景与现状（取证于主仓 HEAD）

| 现状 | 证据 |
| --- | --- |
| 三栏 `1fr : 2fr : 2fr`（父目录 / 当前目录 / 预览），外框浮层 90%×80% | `yate/resources/file-manager-screen.tcss:7-33`、`yate/editor_components/file_manager/screen.py:201-213` |
| 边框只有两处：`#file-manager` 的 `border: tall $panel` 与右栏 `border-left: tall $panel`；左/中栏之间无分隔线 | `yate/resources/file-manager-screen.tcss:10,31` |
| 全屏形态 `border: none`，输入行亦 `border: none`，整屏几乎看不到框 | `yate/resources/file-manager-screen.tcss:13-17,34-39` |
| 无顶部栏头 / 路径条；`compose()` 仅三栏 + `Input` + `Static` | `yate/editor_components/file_manager/screen.py:201-213` |
| 选中行依赖 Textual `ListView` 内置高亮，未定制 `ListItem` / `--highlight`；无「当前栏」视觉态 | `yate/editor_components/file_manager/screen.py:410-420`；全仓 `*.tcss` 无 `ListItem` 声明 |
| 状态栏为单行 `mode nlink owner group size mtime · n/total · sort [· filter · marked]`，前景写死为 `theme.active().fg` | `yate/editor_components/file_manager/model.py:205-249`、`yate/editor_components/file_manager/screen.py:548-564` |
| 图标色是固定 Seti hex（`SETI_COLORS`），注释明确「intentionally do NOT follow the active yate theme」 | `yate/editor_components/icons.py:99-114,170-179` |
| 主题自持链路已达标：`apply_slim_scrollbars` + `apply_scrollbar_theme` + `theme.attach(self, self._apply_theme)` | `yate/editor_components/file_manager/screen.py:238-258` |

### 二、目标（What）

1. **边框体系（硬性要求：必须有边框）**
   - 外框、三栏两两之间的分隔线、状态区/输入区与内容区之间的横向分隔线都要可见；
   - 浮层形态与全屏形态都要有边框（去掉 `.fullscreen #file-manager { border: none }`，
     全屏下至少保证栏间分隔 + 内框可见）；
   - 边框形状沿用仓库惯例 `tall` / `round` / `solid`（参考 `which-key.tcss:15-19` 的
     `round` + `border-title-*`、`diff-view.tcss:29-31` 的 `solid $border`、
     `explorer-tree.tcss:4-5` 的 `border-right: tall $foreground 12%`）；
   - 每栏增加主题色栏头（父目录路径 / 当前目录 / 预览标题），用 `border-title-*`
     或独立 `Static` 实现，风格与预览图一致。
2. **向预览图靠拢的版式**
   - 当前选中行整行反色高亮（对应预览图顶部绿条），配色用 `accent` + `on_accent`
     或 `$primary` / `$surface`，不得照抄绿色；
   - 底部状态栏改为左/中/右三段式（属性信息 · 位置/时间 · 统计与筛选），
     段间用边框或 `$foreground 15%` 分隔；
   - 保持三栏 1:2:2 比例与现有信息密度，不新增第四栏。
3. **配色全面对齐主题（硬性要求）**
   - file manager 可见的所有颜色（边框、栏头、选中行、目录/文件名、图标、状态栏、
     预览降级文案）全部来自 `Theme` / Textual 设计令牌，禁止硬编码 hex、
     禁止照抄预览图配色；
   - 文件图标色需改由主题派生（如按扩展名映射到 `accent` / `accent2` / `green` /
     `yellow` / `red` / `orange` / `fg_dim`）。`icons.py` 的 Seti 固定色是全局共享，
     改造应局限在 file manager 侧（可注入色彩解析器），不得改变 explorer 的既有图标外观；
   - 切换主题（含运行时 `:theme` 与自定义主题）后，边框、栏头、高亮、图标色即时跟随；
     TCSS 令牌由桥自动重生成，Rich `Text` / 内联 `styles.*` 必须放进
     `theme.attach` 回调重刷。

### 三、约束与风险（架构红线）

- 可用令牌（`to_textual_theme`，`yate/editor_components/theme/themes.py:566-599`）：
  `$primary`←`accent2`、`$secondary`←`accent`、`$accent`←`orange`、
  `$warning`←`yellow`、`$error`←`red`、`$success`←`green`、
  `$foreground`/`$text`←`fg`、`$foreground-muted`←`fg_dim`、
  `$text-muted`←`fg_muted`、`$background`←`bg`、`$surface`←`surface`、
  `$panel`←`panel`；另有 Textual 派生 `$border` / `$boost` 及
  `$foreground 12%/15%/25%` tint 写法。自定义主题
  （`replace(THEMES[...])` 或 `*.py` 主题文件）同样覆盖这些令牌。
- 坑：`Theme.border` ≠ CSS `$border`。桥不映射 `border` 字段；`t.border` 只用于
  滚动条 thumb 与 diff 内联空白。想让边框随主题变，应改 `panel` / `fg` /
  `accent` / `accent2`，不要指望改 `Theme.border`。
- R13：主题着色归 L2 组件自持，`editor.py` 不得出现 `apply_theme` /
  `.styles.background =` 等代劳写法
  （`tests/test_architecture.py::test_editor_does_not_paint_widget_styles`）。
- R15：新增可滚动容器必须成对调用 `apply_slim_scrollbars`（挂载）与
  `apply_scrollbar_theme`（主题回调），守卫
  `test_scrollable_widgets_apply_theme_scrollbar_pair`；禁止类级
  `ScrollBar.renderer` patch。
- R9：widget id 冻结，`file-manager-screen.tcss` 头注释声明 id 归本组件所有；
  改 id 需同步评审（无自动守卫，人工确认）。
- 样式仍走组件自持的 `DEFAULT_CSS = load_tcss("file-manager-screen.tcss")`
  （`yate/paths.py:71-78`），不往 `app.tcss` 塞组件选择器。
- 不改 `Theme` 数据结构与桥映射；若确需新增字段，必须同步
  `yate/editor_components/theme/themes.py` 与 `tests/test_theme_palettes.py`
  的逐字段断言。
- 纯视觉改动：不改键位、导航、文件操作、预览加载与状态栏数据语义；不新增依赖。

### 四、验收标准

1. 视觉对比（主要验收）：改动前后各产出一次
   `.venv\Scripts\python.exe -m tools.screenshots --only file-manager`
   （基线 `screenshots/file-manager.svg`，100×30 确定性 SVG）；至少覆盖默认主题 +
   另一套内置主题 + 一套自定义 `replace(THEMES[...])` 主题，以及浮层 + 全屏两种形态，
   逐项确认：三栏边框可见、栏头存在、选中行整行高亮、状态栏分段、
   切换主题后无残留固定色（尤其图标）。
2. 新增用例（`tests/test_file_manager.py` 等）：主题切换后边框/栏头/选中行/图标色
   取自新主题的 `Theme` 字段；全屏态与输入行激活态仍存在边框；自定义主题覆盖
   `panel` / `accent` / `fg` 后 file manager 视觉随之变化，且 explorer 图标色不变。
3. 回归：
   `.venv\Scripts\python.exe -m pytest tests/test_file_manager.py tests/test_file_manager_model.py tests/test_theme_palettes.py -q`
   及 `python -m tools.smoke_test compare --scenario file_manager_startup_navigation`
   （checks 不漂移；注意 `compare` 默认丢弃 `svg_rows`，纯视觉改动不会被 checks 捕获，
   故第 1 条不可省）。
4. 全量门禁（与 CI 同口径）：pyright 零诊断、`pytest tests/ -q -n auto` 全绿、
   `pytest tests/test_architecture.py -q` 37 用例、`--cov=yate --cov-branch -n auto`
   覆盖率、`tools.smoke_test run --jobs 4`；若涉双语手册或 README 截图说明，同步更新。

### 五、非目标

- 不改三栏比例、不新增第四栏、不改 1:2:2 布局语义；
- 不改键位表、导航/标记/复制粘贴/盘符层、预览 worker 与缓存；
- 不改 explorer / 其它组件的图标色与边框；
- 不引入硬编码主题色板、不引入新依赖、不改 `Theme` 字段；
- 不做「中栏万级条目增量刷新」等既有遗留项（另案）。

### 六、预估涉及文件

| 文件 | 改动 |
| --- | --- |
| `yate/resources/file-manager-screen.tcss` | 边框体系、栏头、选中行高亮、状态栏分段、全屏态边框 |
| `yate/editor_components/file_manager/screen.py` | 栏头 widget / 路径文本、`_apply_theme` 重刷新增 Rich 样式、图标色注入 |
| `yate/editor_components/file_manager/model.py` | 行文本/状态栏分段渲染（若采用主题 Rich span） |
| `yate/editor_components/icons.py` | 仅新增可注入的主题派生色接口，保持默认 Seti 行为不变 |
| `tests/test_file_manager*.py`、`screenshots/file-manager.svg` | 新增用例与截图基线 |
| `yate/docs/` / `yate/resources/manual.*.md` | 若用户可见文案或截图说明变化，双语同步 |

## 三、只读情报（【领会】阶段已核实的既有上下文）

- 主题系统：`yate/editor_components/theme/{__init__,themes,files}.py`；`Theme` 为
  frozen dataclass，34 个颜色字段（背景 5 / 叠加 4 / 前景 4 / 强调 6 / 模式 4 /
  语法 11）；`to_textual_theme` 桥映射 12 个字段，`fg_bright` 与 `border` 未进桥。
- 边框惯例：`palette-screen.tcss:10-12` `tall $foreground 15%`、
  `explorer-tree.tcss:4-5` `tall $foreground 12%`、`pane-host.tcss:17-20`
  `tall $foreground 25%`、`diff-view.tcss:29-31` `solid $border`、
  `which-key.tcss:15-19` `round $secondary` + `border-title-*`；
  全仓无 `heavy` / `double`，无写死 hex 的边框。
- 截图机制：`tools/screenshots/scenarios.py:402-426` 的 `_file_manager` 场景，
  CLI `python -m tools.screenshots --only file-manager`；
  `screenshots/README.md:167-173` 记录 file-manager SVG 条目；
  冒烟基线 `tools/smoke_test/smoke_baselines/file_manager_startup_navigation.json`。
- 既有计划/评审未登记「视觉美化 / 边框 / 主题对齐」待办：
  `.trae/documents/file-manager-plans/overview.md:181-183` 的四项遗留均为性能/回调/
  harness/SVG 基线；`.trae/reviews/2026-11-02-filemgr-wrapup.md` 终审零发现。
- 环境事实（本轮实测）：主仓 `git status --short` 为空；`git worktree list` 另有
  `yate-multi-dim-review-r2`；Windows PowerShell；本机 CodeBuddy safe-delete 钩子
  在单轮删除 >9999 文件时会杀 pytest（本轮每道门禁须拆到独立工具调用轮次）；
  `pytest -q` 无汇总行，以 exit code 为权威信号。
