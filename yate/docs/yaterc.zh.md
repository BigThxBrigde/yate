# yaterc 配置指南

[English](yaterc.en.md) · **中文**

yate 使用 Python 语法的配置文件 **yaterc**（类似 vim 的 `vimrc` / neovim 的 `init.vim`）：
选项就是普通的模块级变量，配置文件里可以写任意 Python 代码。

一份最小配置：

```python
keymap = "vim"
theme = "latte"
tab_width = 2
use_spaces = False
```

可直接参考包内随附的 [yaterc.example](../yaterc.example)（复制为 `~/.yate/yaterc`
或项目内的 `yaterc` 即可生效）。

## 配置文件位置与加载顺序

启动时 yate 按以下顺序加载配置，**后加载的文件覆盖先加载的同名选项**（与
vim 的 `~/.vimrc` → `./.vimrc` 规则一致）：

| 顺序 | 来源 | 路径 | 说明 |
|---|---|---|---|
| 1 | 用户级 | `~/.yate/yaterc` | 全局个人配置，不存在则跳过 |
| 2 | 项目级 | 从当前目录（或启动时打开的文件所在目录）**逐级向上**查找名为 `yaterc` 的文件 | 最近一级生效；适合随项目提交到版本库 |
| 3 | 命令行指定 | `yate -u <文件>` | **替换**上面两个来源，只加载该文件 |

特例：`yate -u NONE` 完全跳过配置加载（vim 同款语义）。

加载行为的几个细节（实现见 [yate/config.py](../config.py)）：

- 多个文件在**同一个命名空间**内依次执行，因此项目级配置能看到（并覆盖）
  用户级配置里已设置的变量。
- 配置文件里被识别的选项只有下表九个；**未识别的变量会被静默忽略**，
  但你可以在里面定义任意辅助变量/函数供后续使用。
- 任何文件读取失败、语法错误、运行时异常都**不会导致编辑器崩溃**：
  出错的文件被跳过，问题以 `yaterc: ...` 前缀显示在启动时的消息栏，
  其余文件继续加载。

## 选项参考

| 选项 | 类型 | 默认值 | 合法值 | 说明 |
|---|---|---|---|---|
| `keymap` | `str` | `"vsc"` | `"vsc"` / `"vim"` | 按键映射。非法值回退默认并报错 |
| `theme` | `str` | `"mocha"` | 内置主题名或自定义主题名 | 配色方案，见下文 |
| `tab_width` | `int` | `4` | `1`–`16` 的整数 | Tab 键插入的空格数，也是 Tab 的显示宽度；`True`/`False` 等非整数被拒绝 |
| `use_spaces` | `bool` | `True` | `True` / `False` | `True` 时 Tab 插入空格；`False` 时插入真实制表符 |
| `extensions` | `str` 或 `list[str]` | 无 | 存在的文件/目录路径 | 额外扩展脚本路径，见[下文](#扩展路径extensions)；多个 rc 文件**累加**而非覆盖 |
| `disabled_extensions` | `str` 或 `list[str]` | 无 | 非空扩展名字符串 | 按文件名主干禁用随包默认扩展（如 `["python_lsp"]`），见[下文](#扩展路径extensions)；多个 rc 文件**累加**去重 |
| `theme_dirs` | `str` 或 `list[str]` | 无 | 存在的文件/目录路径 | 客制化主题目录（或单个 `*.py` 主题文件），见[下文](#客制化主题目录theme_dirs)；多个 rc 文件**累加**而非覆盖 |
| `shell` | `str` | 平台默认 | 非空字符串 | 集成终端（`` Ctrl+` `` 打开）启动的 Shell，可带参数（如 `"pwsh -NoLogo"`）；默认 Windows 为 `pwsh`→Windows PowerShell→`cmd.exe`，POSIX 为 `$SHELL`→`bash`→`/bin/sh` |
| `terminal_height` | `int` | `12` | `3`–`40` 的整数（布尔/浮点/字符串被拒绝） | 集成终端面板高度（行数） |
| `language_servers` | `list[dict]` | 无 | 见[下文](#声明式语言服务器language_servers) | 声明式注册 LSP 语言服务器；打开匹配文件时自动激活，无需写扩展 |

非法取值不会中断加载：对应选项保持默认，错误信息出现在启动消息栏。

选项的作用范围：

- `keymap` / `theme` 在启动时生效；`theme` 是进程级全局状态（同 vim 的
  colorscheme）。
- `tab_width` / `use_spaces` 会传播到**所有新建和打开的 buffer**
  （见 [yate/app.py](../app.py) 中 `_make_buffer` / `_apply_buffer_options`）。
- `shell` 在启动终端 Shell 时读取（会话内 `:set shell=…` 后需重启 Shell 生效）；
  `terminal_height` 同时支持会话内 `:set terminal_height=<n>` 立即调整。

## 内置主题

八套内置主题（四套 Catppuccin 风味 + One / Gruvbox）：

| 名称 | 主题 | 明暗 |
|---|---|---|
| `mocha` | Catppuccin Mocha | 深色（默认） |
| `macchiato` | Catppuccin Macchiato | 深色 |
| `frappe` | Catppuccin Frappé | 深色 |
| `latte` | Catppuccin Latte | 浅色 |
| `onedark` | One Dark | 深色 |
| `onelight` | One Light | 浅色 |
| `gruvbox-dark` | Gruvbox Dark | 深色 |
| `gruvbox-light` | Gruvbox Light | 浅色 |

另有 Dracula 与 Ayu 官方主题模板随包附带，拷贝为 `*.py` 即可启用，
见[主题指南](themes.zh.md)。

## 自定义主题

yaterc 的命名空间中注入了 `register_theme()` 函数，用于注册自定义
`Theme`。最省事的做法是用 `dataclasses.replace` 复制一个内置主题再
覆盖少量颜色：

```python
from dataclasses import replace
from yate.editor_view.theme import THEMES, register_theme

register_theme(replace(
    THEMES["mocha"],
    name="my-mocha",        # 必须唯一，作为 theme 选项引用
    label="My Mocha",
    accent="#89b4fa",      # 主色：状态栏底色、活动 tab、选中项
    accent2="#cba6f7",     # 次色：mauve/紫
))

theme = "my-mocha"
```

`Theme` 的字段（定义见 [yate/editor_view/theme.py](../editor_view/theme.py)）按用途分组：

- **背景**：`bg`（编辑区）、`panel`（tab 栏/侧栏/状态栏）、`surface`
  （当前行/输入框）、`gutter_bg`（行号槽）、`border`（分隔线）
- **叠加层**：`selection_bg`（选区）、`match_bg` / `match_active_bg`
  （搜索匹配/当前匹配）、`on_accent`（绘制在 accent 色块上的文字色）
- **前景**：`fg`、`fg_dim`（注释/弱化）、`fg_muted`、`fg_bright`（强调）
- **强调色**：`accent`、`accent2`、`green`、`yellow`、`red`、`orange`
- **模式色块**：`mode_normal_bg`、`mode_insert_bg`、`mode_visual_bg`、
  `mode_command_bg`
- **语法色板**：`syn_keyword`、`syn_string`、`syn_number`、`syn_comment`、
  `syn_function`、`syn_type`、`syn_constant`、`syn_builtin`、`syn_decorator`、
  `syn_operator`、`syn_property`

注意：`name` 与内置主题重名会覆盖内置主题。

## 客制化主题目录（theme_dirs）

少量改色可以直接在 yaterc 中调用 `register_theme()`（见上节）；要维护
可复用的主题库时，用 `theme_dirs` 指定目录，yate 启动时加载其中所有
`*.py` 主题文件（下划线开头的跳过），也支持直接给单个 `*.py` 文件：

```python
theme_dirs = "~/.yate/themes"          # 单个目录，字符串即可
theme_dirs = [
    "~/.yate/themes",                  # ~ 自动展开
    "./team-themes",                   # 相对路径：相对本 yaterc 所在目录
    "./extras/solarized.py",           # 单个主题文件
]
theme = "my-mocha"                     # 选用这些文件注册的主题
```

主题文件是普通 Python，作用域内已注入 `Theme` 与 `register_theme()`，也可
正常 `import`。文件示例（`~/.yate/themes/my_mocha.py`）：

```python
from dataclasses import replace
from yate.editor_view.theme import THEMES

register_theme(replace(THEMES["mocha"], name="my-mocha", accent="#89b4fa"))
```

路径规则与加载行为：

- `~` 会展开为用户主目录；**相对路径相对声明它的 yaterc 文件所在目录**解析。
- 用户级和项目级 yaterc 中的 `theme_dirs` **累加**；同一路径重复声明去重。
- 路径不存在、类型错误会作为配置错误显示在启动消息栏；单个主题文件出错
  不影响其余文件加载。
- 同一文件即使被多个来源命中也只执行一次（按解析后的绝对路径去重）。

除 rc 声明外，`./themes/` 和 `~/.yate/themes/` 会被自动扫描，也可用命令行
`--theme-dir <目录或文件>`（可重复）追加；`~` 会展开（PowerShell/cmd 下也
生效）。同名主题的加载优先级（后者覆盖前者）：
内置主题 < 默认目录 < yaterc `theme_dirs`（先用户 rc、后项目 rc）
< 命令行 `--theme-dir`。注册成功后即可用 `:theme <名称>` 切换，也可在启动时
用 `--theme <名称>` 直接选用（覆盖 yaterc 中的 `theme`）。

## 扩展路径（extensions）

`extensions` 选项声明要加载的自定义扩展脚本（扩展 API 见
[yate/services/extensions.py](../services/extensions.py)）。每个
扩展就是一个暴露 `setup(api)` 函数的 `.py` 文件，通过 `api` 注册动作、
按键绑定和 `:` 命令：

```python
def setup(api):
    @api.command("hello", "greet from an extension")
    def hello(args):
        api.message("hello from my extension!")
```

`extensions` 接受一个路径字符串或路径列表，每一项可以是：

- **目录**：加载该目录下所有 `*.py`（下划线开头的文件跳过）；
- **`.py` 文件**：只加载该文件。

```python
extensions = "~/.yate/myext.py"          # 单个文件
extensions = [
    "~/.yate/extensions",                # 目录：加载其中所有 .py
    "./tools/yate_exts",                 # 相对路径：相对本 yaterc 所在目录
    "/opt/yate/extra.py",                # 绝对路径
]
```

路径规则与加载行为：

- `~` 会展开为用户主目录；**相对路径相对声明它的 yaterc 文件所在目录**
  解析（因此项目级 yaterc 里的相对路径随项目移动仍然有效）。
- 用户级和项目级 yaterc 中的 `extensions` **累加**（与标量选项的"后者
  覆盖"语义不同）；同一路径在多个文件中重复声明只加载一次。
- 路径不存在、类型错误（非字符串/非列表）会作为配置错误显示在启动消息栏，
  不影响其余选项。
- 同一脚本即使同时被 rc 路径、默认目录和命令行参数命中，也只会加载一次
  （按解析后的绝对路径去重），避免命令/绑定重复注册。

除 rc 声明外，yate 会先自动加载**包内随附扩展** `yate/extensions/`
（目前为 `python_lsp`、`csharp_highlight`，无论工作目录在哪都生效），
再扫描默认目录 `./extensions/` 和 `~/.yate/extensions/`，也可用命令行
`--ext <文件>` / `--ext-dir <目录>` 追加。要跳过某个随包默认扩展，用
`disabled_extensions` 列出其文件名主干（不含 `.py`）：

```python
disabled_extensions = ["python_lsp"]
disabled_extensions = ["python_lsp", "csharp_highlight"]
```

该选项接受字符串或字符串列表（空白自动去除），多个 rc 文件之间累加并
去重；它只影响随包扩展，用户/项目/命令行脚本不受影响。非法取值作为
配置错误显示在启动消息栏。完整的加载顺序与扩展 API 见
[extensions.zh.md](extensions.zh.md)。

## 声明式语言服务器（language_servers）

`language_servers` 用纯数据列表声明 LSP 语言服务器，免去编写扩展。
配置后打开扩展名匹配的文件时**自动激活**（首次匹配惰性启动，每个
服务器 × 项目根一个进程），字段与扩展 API
`api.lsp.register_server(...)` 一致：

```python
language_servers = [
    {
        "name": "rust-analyzer",                  # 必填：状态栏显示名
        "command": "rust-analyzer",               # 必填：可执行文件（非空）
        "args": [],                                # 可选：命令行参数，默认 []
        "filetypes": ["rs"],                      # 必填：不带点的扩展名（".rs" 亦可）
        "language_ids": {"rs": "rust"},           # 可选：filetype -> LSP languageId
        "root_markers": ["Cargo.toml", ".git"],   # 可选：缺省用内置根标记
        "env": {"RUST_LOG": "info"},              # 可选：额外环境变量
        "initialization_options": None,           # 可选：initializeOptions
        "settings": None,                         # 可选：服务器配置
    },
    {
        "name": "typescript",
        "command": "typescript-language-server",
        "args": ["--stdio"],
        "filetypes": ["ts", "tsx", "js", "jsx"],
        "language_ids": {"ts": "typescript", "tsx": "typescriptreact",
                         "js": "javascript", "jsx": "javascriptreact"},
        "root_markers": ["package.json", "tsconfig.json", ".git"],
    },
]
```

校验与加载语义：

- `name` / `command` / `filetypes` 必填；`command` 必须是非空字符串，
  `filetypes` 必须是非空字符串列表（`args` / `root_markers` 等同理）。
  列表字段也接受元组；`name` / `command` 两端空白自动去除；扩展名前导点
  自动剥离（`".rs"` → `"rs"`，但 `"."` / `".."` 这类值报错）；
  `language_ids` / `env` 必须是字符串到字符串的映射；未识别的多余键忽略。
  非法条目被跳过并在启动消息栏报错，同一列表中的其余条目仍然生效。
- 与标量选项一致，后加载的 yaterc **整体替换**该列表（不累加）。
- 选项在扩展加载**之后**注册：同名条目替换扩展注册（包括内置 Python
  服务器），可用 `"name": "python"` 自定义 Python 服务器命令。
- 仅配置不会启动进程；未命名 buffer 与不匹配的文件不受影响。

> 主流语言的安装命令与完整食谱见 [lsp.zh.md](lsp.zh.md)
> （[English](lsp.en.md)）。

## 命令行交互

- `yate -u <文件>`：只加载指定配置文件。
- `yate -u NONE`：不加载任何配置。
- `yate --keymap vim`：命令行显式指定的 keymap **优先级高于 yaterc**
  （`--keymap normal` 是 `vsc` 的兼容别名）；不传 `--keymap` 时使用
  yaterc 的值。

## 会话内临时更改

以下 `:` 命令只影响当前会话，不会写回 yaterc 文件：

- `:set keymap=vsc|vim`、`:vim`、`:vsc`（`:normal` 为 `:vsc` 别名）
- `:theme <名称>` / `:colorscheme <名称>`（不带参数列出可用主题）
- `:set shell=<命令>`（下次启动终端 Shell 时生效）、`:set terminal_height=<3-40>`
  （立即调整终端面板高度）

要永久生效，请把对应选项写进 yaterc。
