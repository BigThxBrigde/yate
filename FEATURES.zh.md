# yate 特性与功能总览

[English](FEATURES.md) · **中文**

*yate — yet another terminal editor*，基于 [Textual](https://www.textualize.io/)
构建的现代终端文本编辑器（Python ≥ 3.12）。本文是当前版本全部用户可见特性与
功能的完整清单；快速上手见 [README.zh.md](README.zh.md)，完整使用说明见
[用户手册](yate/resources/manual.zh.md)（会话内 `F8` / `:manual`）。

## 1. 编辑核心

- 多 buffer 标签页编辑；文档会话与 UI 解耦（`editor_core` 纯逻辑，可无头测试）
- 撤销/重做、剪切/复制/粘贴（同步系统剪贴板与内部寄存器）
- 多光标编辑（`add_cursor_below`、`Alt+C`），多光标感知的行操作
- 自动缩进换行、Tab/缩进/反缩进、删词/删行/合并行、行上下移
- 可配 `tab_width`(1–16)、`use_spaces`；只读模式（拒绝编辑与保存）
- vim 风格命名寄存器 `"a-z`（未命名寄存器镜像系统剪贴板）
- count 乘法（如 `2d3w`）、`f/F/t/T` + `;`/`,` 重复查找

## 2. 界面与布局

- VS Code 风格布局：活动标签栏、EXPLORER 文件树侧栏、面包屑路径栏、扁平状态栏、欢迎页
- 状态栏 + 命令行/消息栏；扩展可注入自定义状态栏段与模态字符画布（`api.ui`）
- which-key 面板：和弦挂起时实时显示下一键候选、`F9` 钉住全键位分类表（`which_key` 可关）
- Nerd Font 文件类型图标（`--install-font` / `:font` 自动安装并配置 Windows Terminal）
- 瘦滚动条注入、每组件自持主题着色

## 3. 两套内置键位

- **vsc**（默认，无模式）：VS Code 式编辑/选择/剪贴板快捷键，`:` 是普通字符、`F5` 开命令行
- **vim**（有模式）：NORMAL/INSERT/VISUAL/VISUAL-LINE；motion（`hjkl w b e 0 $ gg G f t`）、
  操作符 `d/y/c`、text-object（`iw aw i( i" it`…）、`r` 替换、`x`、`p/P`、`u/Ctrl+R`、`J`、
  缩进操作符 `>/<`
- `Ctrl+/` 运行中一键切换；vim 下 `Ctrl+W` 窗格和弦（14 键）+ 和弦实时提示；
  vim 保留键机制（不可被扩展覆盖）
- `:check-keys` 键位绑定冲突报告

## 4. 查找与替换

- 文件内查找 `Ctrl+F`（实时高亮、`[序号/总数]`）、`F3`/`Enter` 下一个
- 两步式全部替换 `F4`（计入单条撤销）
- 项目内查找替换 `Ctrl+H` / `:project-replace`

## 5. 文件与工作区

- 文件树浏览（`Ctrl+B` 开关）：`j/k/l/h` 导航、新建文件/文件夹、重命名、删除（`y` 确认），
  同步已开标签
- 模糊快速打开 `Ctrl+P`（fzf 式子序列匹配 + 实时文件预览窗格，`file_preview` 可配）
- 命令面板 `Alt+Shift+P`（全部 `:` 命令与命名动作）
- 工作区信任机制：`:trust` 后才自动加载项目内 `./extensions` 与项目级 yaterc
- `show_hidden` 显示隐藏文件

## 6. 窗格与标签

- 窗格分割：`:split`/`:vsplit`（可带路径）、`:only`、`:close`；每窗格光标/选区/滚动独立
- vim `Ctrl+W` 和弦：分割/关闭/最大化/四向移动/调大小/等分/循环焦点
- 标签：`Ctrl+PageUp/Down`、`:bn`/`:bp`/`:bd`

## 7. 命令行（ex 命令）

- 全集：`:w` `:q` `:q!` `:wq` `:saveas` `:e` `:enew` `:welcome` `:files` `:palette`
  `:set` `:filetype` `:theme` `:vim/:vsc` `:help` `:manual` `:changelog` `:explorer`
  `:term/:termclose` `:diagnostics` `:font` `:diff` `:trust` `:project-replace`
  `:check-keys` `:game` 及扩展注册命令
- `:!命令`（`F2`）后台线程执行 shell，输出到可滚动浮层并标注退出码
- `:set` 运行时可设：`keymap`/`theme`/`shell`/`terminal_height`/`filetype`/`show_hidden`/
  `readonly`/`support_mouse`/`which_key`

## 8. 配置系统（yaterc）

- Python 语法配置文件（vimrc 风格），用户级 → 项目级逐级向上加载，`-u FILE` 指定、
  `-u NONE` 跳过
- 全部选项：`keymap` `theme` `tab_width` `use_spaces` `shell` `terminal_height`(3–40)
  `show_hidden` `support_mouse` `which_key` `key_protocol` `extensions`
  `disabled_extensions` `theme_dirs` `yate_trace`/`yate_trace_level`（运行日志）
  + 字典 `screen_saver`（enable/interval/switch/距离区间/角色白名单）、
  `file_preview`（enable/position/size/max_lines/max_size）、
  `language_servers`（name/command/filetypes/args/language_ids/initialization_options/
  settings/env/root_markers）
- `register_theme()` 内联注册自定义主题；`--setup-defaults`/`--cleanup-defaults`
  （`--force`/`--include-data`）管理 `~/.yate`

## 9. 主题

- 内置 8 套：Catppuccin `mocha`(默认)/`macchiato`/`frappe`/`latte`、One Dark/Light、
  Gruvbox dark/light
- 随包模板 Dracula 与 Ayu（dark/mirage/light）拷贝即用
- 5 种客制化途径：yaterc 内联 / `theme_dirs` / 默认目录 / `--theme-dir` / 模板拷贝

## 10. 语法高亮

- 双后端共享语言注册表：regex 后端开箱 30 种语言（C#/Rust/Go/HTML/CSS/YAML/SQL/Lua/
  Perl/PHP/Ruby/PowerShell/Zig…）、60+ 扩展键
- 可选 tree-sitter 后端（`pip install -e ".[ts]"`）：25 种语言切到真实语法树解析
- `:filetype` 查看/强制/`auto` 重检测；扩展可注册自定义词法语言（`api.highlight`）
  与 tree-sitter 语法包（`api.syntax`）

## 11. LSP 语言服务器

- 内置零依赖 LSP 客户端（stdio JSON-RPC、按服务器×项目根惰性启动、全文同步 0.25s 去抖）
- 自动补全弹窗（触发字符 + `Ctrl+Space`，无服务器时回退 buffer 单词/路径）
- 诊断：下划线/装订槽 ✖▲/状态栏计数/`:diagnostics`
- 两种注册：yaterc `language_servers` 声明式；扩展 `api.lsp.register_server`
- 随包 Python LSP 扩展自动发现 pyright / python-lsp-server（`YATE_PYTHON_LSP` 可指定或 `off`）

## 12. 终端与 Shell

- 集成终端：`` Ctrl+` `` / `:term` / `:termclose`，PTY 运行真实 Shell
  （Windows ConPTY / POSIX pty），高度 `terminal_height`
- `shell` 选项可配任意 Shell 命令行

## 13. Diff 视图

- CLI `--diff F1 F2`（两路）、`--diff F1 F2 F3`（三路 base/local/remote）、
  `--2way`/`--3way` 强制
- 会话内 `:diff [--3way] F1 F2 [F3]`

## 14. 扩展系统

- **Python 扩展**：任意 `setup(api)` 脚本；加载途径：随包 `yate/extensions/`、
  `./extensions/` 与 `~/.yate/extensions/` 自动加载、yaterc `extensions`、`--ext`/`--ext-dir`
- **Lua 扩展**（`pip install -e ".[lua]"`）：`setup/teardown` + `require("yate")`
- **`.yxp` 扩展包**：安装/卸载/列表（CLI 与 `:` 命令均支持）
- API 面：`command`/`register_command`、`bind_key`/`bind_action`/`unbind_key`（vsc/vim/both）、
  `register_action`、`message`/`shell`/`open_path`/`save`、`buffer`/`doc`/`workspace`/
  `keymaps`/`lsp`/`highlight`/`syntax`/`sprites`/`ui`/`events`/`theme`/`clipboard`/`docs`/
  `actions`/`data`（`~/.yate/data` 持久化）
- setup 失败自动快照-恢复回滚全部注册
- 随包扩展：`python_lsp.py`（内置 LSP）+ `games.lua`（游戏包）+ 多个 `.py.example` 模板

## 15. 娱乐子系统

- **屏保**：空闲自动进入/`Alt+Shift+S` 手动开关，27 只原创致敬像素角色，
  扩展可注册角色（`api.sprites`）
- **Lua 游戏包**：`:game snake|pacman|nethack|tetris`，统一暂停/重开/退出，
  NetHack 每回合自动存档（`~/.yate/data/games/` 存档）

## 16. 帮助与文档

- `F1` 键位帮助、`F8`/`:manual` 中英双语用户手册（会话内直接看）
- `:changelog [en|zh]` 浏览变更日志；双语 README 与
  [yate/docs/](yate/docs/)（yaterc/扩展/LSP/主题/which-key/games 六篇 × en/zh）
- `YATE_TRACE` 运行日志与崩溃报告（`~/.yate/data/`）

## 17. CLI 完整选项

`path`、`--readonly`、`--keymap vsc|vim|normal`、`-u/--yaterc`、`--ext`、`--ext-dir`、
`--theme-dir`、`--theme`、`--install-font`、`--install-extension`、`--uninstall-extension`、
`--list-extensions`、`--setup-defaults`、`--cleanup-defaults`、`--force`、`--include-data`、
`--version`、`--changelog`、`--diag`（环境诊断报告）、`--diff`、`--2way`、`--3way`

## 18. 分发与打包

- wheel 安装 + PyInstaller 独立可执行（Windows `pack.ps1`/`pack.bat`、Linux `pack.sh`，
  单目录/单文件两种形态，内置 tree-sitter 与 Lua 桥）
- 维护工具链：`tools.smoke_test`（端到端冒烟 + 基线对比）、`tools.changelog`/`tools.release`
  （自动 changelog 与发布）、`tools.pack wiki`（双语 Wiki 生成）+ 36 条架构守卫测试

## 附：README 未重点提及的功能

`.yxp` 扩展包管理、Lua 扩展与四款游戏、which-key 面板、多光标 `Alt+C`、
项目查找替换 `Ctrl+H`、`:check-keys`/`:trust`/`:font`、vim 命名寄存器、
扩展高级 API（`syntax`/`sprites`/`ui` 画布/`events`/`data`/`clipboard`），以及 yaterc 的
`key_protocol`/`show_hidden`/`support_mouse`/`which_key`/`yate_trace` 等选项。
