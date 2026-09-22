# yate：yaterc 配置系统 + 严格 pyright 类型检查 + VSCode 风格改版 + keymap 更名 vsc

> **实施状态（2026-09-22 核对）：✅ 已实现。**
>
> - **yaterc**：`yate/config.py` 已落地用户级 + 项目级叠加、`-u/--rc`（含
>   `NONE`）、`yate.map/unmap/alias_command`、未知选项 warning。
> - **keymap 更名**：`yate/keymaps/vsc.py` 为现行模块（`keymaps/normal.py`
>   已不存在），`normal` 保留为静默别名。
> - **UI**：VSCode 风格侧栏/面包屑/扁平状态栏、命令面板与快速打开
>   （`yate/editor_view/palette.py`）、欢迎页均已落地。
> - **pyright**：`pyproject.toml` 为 `typeCheckingMode = "strict"`、
>   `include = ["yate", "tools", "tests"]`（比本文档 §4 的 basic/override 方案
>   更严格），当前 0 诊断。
> - **过时内容**：§3 描述的"单一 VSCode Dark Modern 主题常量"已被后续主题系统
>   取代（8 套内置 + 模板 + Textual 主题桥，见 `themes_expansion_plan.md` /
>   `overlay_theme_consistency_plan.md`）。

## 与当前实现的差异（回写，2026-09-22）

- **§4 pyright**：已由"basic + 目录级 `overrides`"升级为全局
  `typeCheckingMode = "strict"`、`include = ["yate", "tools", "tests"]`，
  目标零诊断；不再有 `[tool.pyright.basic]` 段与目录 override。
- **§3 的 VSCode Dark Modern 常量**已被主题系统取代：
  `yate/editor_view/theme.py` 现有 8 套内置主题（Catppuccin 4 + One/Gruvbox 4）
  与 `resources/theme_examples/*.example` 模板，并桥接为 `yate-<name>` Textual
  主题（`textual_theme_name` / `to_textual_theme` / `validate_theme`），
  所有覆盖屏跟随当前主题（见 `themes_expansion_plan.md` /
  `overlay_theme_consistency_plan.md`）。
- **§2 重命名**：`yate/keymaps/vsc.py` 存在，`keymaps/normal.py` 不存在；
  `render_tabbar` 现为 `build_tabbar(width)`（配套 `TabBar` 点击命中，
  见 `scrollbar_tab_click_plan.md`）。
- **§5 / §6 测试**：已迁移 pytest，`tests/conftest.py::isolated_home` 提供全局
  隔离；正文中的 `unittest` 相关描述与 `tests/test_editor_core.py` 的旧断言
  已过时。
- **§1 yaterc**：`yate/config.py` + `yaterc.example` 已实现用户级/项目级叠加与
  `-u/--rc`（含 `NONE`）；后续新增选项见 `yate/docs/yaterc.*.md`。

## 背景

用户要求：① 所有代码严格遵守 pyright 类型检查；② 所有设置集中到名为 `yaterc` 的 Python 配置文件（优先级类似 vimrc/init.vim，所有选项可配，例如 keymap）；③ `normal` keymap 更名 `vsc`；④ TUI 现代化、布局参考 VSCode。

已确认决策：yaterc 采用**用户级+项目级叠加**加载；UI 做**全套 VSCode 风格**（含命令面板/快速打开/欢迎页）；pyright **strict 模式 + 少量类型豁免**；提供 `yaterc.example`。

架构约束不变：`editor_core`/`keymaps`/`services` 为 UI 无关层，只做必要小改；`editor_view` 为 UI 层。venv 执行统一 `.\.venv\Scripts\python.exe`，跑测试前置 `$env:PYTHONDONTWRITEBYTECODE=1`（沙箱产物告警可忽略）。

---

## 1. yaterc 配置系统（新建 `yate/config.py`）

**Settings**（dataclass，字段=现硬编码默认）：`keymap="vsc"`、`tab_width=4`、`use_spaces=True`、`explorer_width=34`。

**加载 `load_config(rc_file: Path | str | None) -> ConfigResult`**（`ConfigResult` 含 `settings`、`ops`、`warnings: list[str]`）：
- `rc_file` 显式给定 → 只加载该文件（vim `-u` 语义；值为 `"NONE"` → 完全跳过）。
- 否则：先执行 `~/.yate/yaterc`（用户级），再执行 `./yaterc`（项目级叠加覆盖）；不存在则静默跳过。
- 每个 rc 在独立命名空间 `exec(compile(src, path, "exec"))`：预置 `yate = _ConfigAPI(ops)` 和各已知选项名的哨兵 `_UNSET`。执行后：值变化 → 写入 settings；出现未知全局名（非 `_` 前缀、非 `yate`、非模块/可调用）→ warning；整个 exec try/except → 异常转 warning（`yaterc: {name}: {exc}`），绝不崩溃启动。

**`_ConfigAPI`**（rc 文件内可见名 `yate`）：
- `map(key_spec, action, keymap="vsc", description="")` — action 为 action 名或 `Callable[[ActionContext], None]`，只记录 op。
- `unmap(key_spec, keymap=None)` — None 表示全部 keymap。
- `alias_command(name, target)` — `:` 命令别名。

**YateApp 集成**（`yate/app.py`）：
1. `__init__` 最前调 `load_config(rc_file)`（新增参数 `rc_file=None`，放 `keymap` 之前）；`keymap` 参数改为 `Optional[str]`：`None` 用 `settings.keymap`，显式 CLI 值覆盖 config。
2. 构建 `self.keymaps = {"vsc": VscKeymap(), "vim": VimKeymap()}` 后应用 ops：map→`km.add_binding(..., category="user")`，unmap→从 `bindings/_index` 移除，alias 在 `_register_commands()` 之后应用。顺序（vim 语义）：yaterc 绑定 → 扩展（on_mount 加载，可覆盖用户绑定）。
3. `_config_warnings` 并入现有 `_ext_messages` 启动提示。
4. `tab_width/use_spaces` 传播：私有助手 `_apply_buffer_settings(buf)`（给 `buf.tab_width/use_spaces` 赋值，运行时属性读取所以事后赋值有效），在 `_open_document_path`（L179 `Document.open` 后）与 `new_buffer`（L205）调用。`document.py` 默认 `TextBuffer()`（测试路径）不改。

**CLI**（`yate/cli.py`）：新增 `-u FILE` / `--rc FILE`（`NONE` 支持）；`--keymap` 的 `"normal"` 在 `main()` 归一为 `"vsc"`。

**`yate/keymaps/vim.py` L104**：`_extension_binding` 的 `category == "extension"` 放宽为 `in ("extension", "user")`，否则 yaterc map 到 vim 的键在 NORMAL 模式不生效。

**仓库根**新建 `yaterc.example`：注释齐全的选项+`yate.map` 示例。

## 2. normal → vsc 重命名

- `yate/keymaps/normal.py` → 重命名 **`yate/keymaps/vsc.py`**；`NormalKeymap`→`VscKeymap`；`name="vsc"`；`label="VS Code"`。
- `yate/app.py`：L31 import；L99 参数默认 `"vsc"`；L113-114 dict 与 fallback；L273 错误提示 `(vsc|vim)`；L280 `toggle_keymap` 判断；L299 `mode_label()` 非分支返回 `("VSC", MODE_NORMAL_BG)`；L541/549 `:set` 用法文案；L551 `:normal` 保留为 alias→`set_keymap("vsc")`，另注册 `:vsc`；L650-654 idle 文案。
- `yate/actions.py` L190 描述文案。
- `yate/services/extensions.py`：L23 docstring 示例、L79 默认 `keymap="vsc"`、L89 `"both"→["vsc","vim"]`，legacy `"normal"` 静默映射为 `"vsc"`。
- `yate/cli.py` L37-38：choices `["vsc","vim"]`、default `"vsc"`。
- `yate/editor_view/modals.py` L59 帮助文案；`yate/keymaps/__init__.py`、`yate/__init__.py` docstring；`extensions/example_ext.py` 注释。
- tests：`test_editor_core.py` L14/204-218；`test_app_textual.py` 补默认断言。
- vsc 键绑新增 `_k(":", "command_prompt", "Ex command prompt", FILE)`（当前 `:` 在 vsc 下是插入字符，与文档承诺不符）。

## 3. VSCode Dark Modern UI

**theme.py**（保常量名，改值；新增 `SIDEBAR_BG #181818`、`TAB_ACTIVE_BG #1F1F1F`、`TAB_INACTIVE_BG #181818`、`BORDER #2B2B2B`、`STATUSBAR_BG #181818`、`BREADCRUMB_FG`）：`BG #1F1F1F`、`LINE_BG #282828`、`ACCENT #0078D4`、`ACCENT2 #4FC1FF`、`SELECTION_BG #264F78`、`MATCH_BG #623315`、`MATCH_ACTIVE_BG #9E6A03`、`GRAY_DIM #8B8B8B`、`GRAY #9D9D9D`、`GRAY_LIGHT #CCCCCC`、`RED #F14C4C`、`GREEN #89D185`、`YELLOW #CCA700`、`ORANGE`、`MODE_*_BG` 取 VSCode 徽章色。

**app.py 布局**（compose L626 / CSS L72）：
- `#body` → `Vertical#sidebar`（宽从 CSS 常量改为 on_mount 按 `settings.explorer_width` 设 `styles.width`）[ `Static#explorer-header`（h1，"EXPLORER"）+ `ExplorerTree#explorer`（1fr，去 border-right 换 `BORDER` 色）] + `Vertical#editor-col`[ `Static#breadcrumbs`（h1）+ `EditorView` ]。
- 头部用 Vertical 包裹方案：不动 Tree 的 focus/keys。`on_mount` 增查 header/breadcrumbs/sidebar；`_sync_explorer_visibility()`（L561）改为作用于整个 `#sidebar`；`#explorer` 原 CSS 宽度移到 `#sidebar`。
- `render_tabbar()`（L597）重写：每 tab ` {name} {icons.TIMES} `，modified 用 `●`（ORANGE）替代 ✕；active：`bold GRAY_LIGHT on TAB_ACTIVE_BG`，inactive：`GRAY_DIM on TAB_INACTIVE_BG`（1 行内无法画下划线，用前景亮色替代）。
- 新增 `update_breadcrumbs()`：`doc.path` 相对 `workspace.root` 的目录链用 `›` 连接，无 root 只显文件名；在 `ui_refresh()`（L328）随 tabbar 一起刷新。

**statusbar.py**：去 powerline 三角，扁平化重写：左 ` {mode} ` 黑字彩底 chip（vsc 显 "VSC"）+ ` PENCIL name `（#2B2B2B 底）+ modified DOT + `Ln X, Col Y`；右 `spaces:{tab_width}  {encoding}  {filetype}  {PLUG} n`。

**命令面板/快速打开**（新建 `yate/editor_view/palette.py`）：
- `PaletteScreen(ModalScreen)`：`Input#palette-input` + `OptionList#palette-list`（OptionList 自带键盘导航/高亮，8.2.8 内建）；构造参数 `mode: "commands" | "files"`。`on_input_changed` 子序列模糊过滤；Enter：命令→`app.run_command(name)`、文件→`app.open_path(path)` 后 dismiss；BINDINGS 仅 `escape`/`ctrl+c`（不继承 `_OverlayScreen` 的 q，避免劫持 Input）；Input on_mount 后 focus，上/下键转发 OptionList（退化方案：只支持过滤+Enter 选首项）。
- `yate/services/workspace.py` 新增 `walk_files(limit=2000)`：递归 iterdir，跳过 `IGNORED_NAMES` + `is_text_file` 过滤，返回相对 root 的 Path 列表。
- `actions.py`：`command_palette`（现 L184 误指向 `command_prompt`）改为打开面板；新增 `quick_open`。

**按键路由**（`yate/editor_view/keys.py`）：raw 串完全由 keys.py 生成，用合成 raw 最干净：
- `"ctrl+shift+p"` → `"\x1b\x10"`（= alt+ctrl+p 序列；yate 绑定宇宙内无冲突），`KEY_ALIASES["\x1b\x10"]="ctrl-shift-p"`（帮助正确显示）。
- `"ctrl+underscore"` 与 `"ctrl+slash"`（Textual 键名，实装时用 pilot 验证其一）→ `"\x1f"`，`KEY_ALIASES["\x1f"]="ctrl-slash"`。
- vsc 键绑：`<ctrl-p>` → `quick_open`；新增 `_raw("\x1b\x10", "command_palette", ...)`、`_raw("\x1f", "toggle_keymap", ...)`（落地帮助文案承诺的 ctrl+/ 切换）；`_k(":", ...)`。
- 顺带修 app.py L359 陈旧调用：`textual_key_to_raw(event.key)` → `event_to_raw(event.key, event.character)`（否则 app 级 fallback 收不到合成键/标点键）。

**欢迎页**（`yate/editor_view/editor.py`）：`render_line` 在「`doc.path is None` 且 buffer 为空」时前 6 行画居中暗色文案（版本、F1 help、ctrl+p quick open、: 命令），其余空白；`_update_virtual_size`（L51）在欢迎态抬高为 `max(1, line_count, 6)`，否则 virtual 高度 1 只渲染第 1 行。

## 4. pyright（strict 模式 + 少量类型豁免）

`pyproject.toml`：
```toml
[project.optional-dependencies]
dev = ["pyright>=1.1", "pylance>=1.1"]

[tool.pyright]
pythonVersion = "3.13"
typeCheckingMode = "basic"
include = ["yate", "tests"]
exclude = [".venv"]

    [tool.pyright.overrides]
    # UI 无关核心层：strict
    yate/keymaps = [
      { typeCheckingMode = "strict" },
    ]
    yate/editor_core = [
      { typeCheckingMode = "strict" },
    ]
    yate/services = [
      { typeCheckingMode = "strict" },
    ]
    # UI 层：basic（Textual 类型桩偶尔不完整）
    yate/editor_view = [
      { typeCheckingMode = "basic" },
    ]
    tests = [
      { typeCheckingMode = "basic" },
    ]

[tool.pyright.basic]
reportMissingTypeStubs = false
reportUnknownVariableType = false
reportUnknownMemberType = false
reportUnknownArgumentType = false
reportUnknownParameterType = false
```
行内豁免（带理由注释）：`cli.py` 懒加载用 `# pyright: ignore[reportMissingImports]`；`vim.py` 访问私有属性（如 `buf.anchor`）用 `# pyright: ignore[reportAttributeAccessIssue]`；扩展隔离执行路径上 `# pyright: ignore[reportMissingTypeStubs]`。
逐文件清类型问题（以实际输出为准迭代）：`reportUnusedVariable`（lambda 参数改 `_args` 或具名函数）、`reportMissingReturnStatement`、`reportPossiblyUnboundVariable`、`reportOptionalMemberAccess`、`reportArgumentType` 等。目标：`pyright yate tests` 0 errors / 0 warnings。

## 5. 测试

- 新增 `tests/test_config.py`：选项设置、`yate.map` 生效、未知选项 warning、语法错误 warning、用户级+项目级叠加、`-u` 指定与 `NONE`。
- `test_editor_core.py`：`NormalKeymap`→`VscKeymap`；vsc 键绑含 `:`/`\x1f`/`\x1b\x10`。
- `test_app_textual.py`：默认 `keymap_name=="vsc"`；`pilot.press("ctrl+shift+p")` 面板打开+过滤；ctrl+p 快速打开（TemporaryDirectory 造文件验 `walk_files`）；`:normal` 别名；`render_tabbar` 含 ✕/文件名；breadcrumbs 含文件名；statusbar/welcome 渲染 smoke。
- 运行：`$env:PYTHONDONTWRITEBYTECODE=1; .\.venv\Scripts\python.exe -m pytest tests -v`

## 6. 实施顺序（每步保持测试绿）

1. **重命名 vsc**：机械改动 + 测试 + `:normal` alias + `:`/toggle 绑定落地。
2. **pyright 接入**：装 pyright+pylance、写配置、清全库类型问题（顺带修 app.py L359）。
3. **config.py + CLI `-u` + TextBuffer 传播 + test_config.py**。
4. **纯渲染改版**：theme 调色 → statusbar 平化 → render_tabbar → 侧栏头部 → breadcrumbs。
5. **交互**：`walk_files` → palette.py → keys.py 合成键 → ctrl+p/ctrl+shift+p 重绑 → welcome 渲染 + pilot 测试。
6. **收尾**：`yaterc.example`、pyright 0 errors 复验、全量测试、`yate --version` 双入口、真实 TUI 启动冒烟。

## 风险

- **OptionList + ModalScreen 焦点/上下键转发**：退化方案为「输入过滤 + Enter 执行首项」。
- **ctrl+shift+p 实终端差异**：Windows Terminal 可正常发送；若终端吞键，`:` 命令与面板内注册的 `:commands` 列表仍可用。
- **ctrl+/ 各终端发送差异**：以 Textual 键名映射为准，pilot 验证；失败则改绑其他键。
- **welcome 与 virtual_size**：不抬高高度则只渲染 1 行（已纳入方案）。
- **keymap 改名对外影响**：以「`normal` 静默别名→vsc」兜底旧配置/旧扩展脚本。
