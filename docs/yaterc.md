# yaterc 配置指南

yate 使用 Python 语法的配置文件 **yaterc**（类似 vim 的 `vimrc` / neovim 的 `init.vim`）：
选项就是普通的模块级变量，配置文件里可以写任意 Python 代码。

一份最小配置：

```python
keymap = "vim"
theme = "latte"
tab_width = 2
use_spaces = False
```

可直接参考仓库根目录的 [yaterc.example](../yaterc.example)（复制为 `~/.yate/yaterc`
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

加载行为的几个细节（实现见 [yate/config.py](../yate/config.py)）：

- 多个文件在**同一个命名空间**内依次执行，因此项目级配置能看到（并覆盖）
  用户级配置里已设置的变量。
- 配置文件里被识别的选项只有下表七个；**未识别的变量会被静默忽略**，
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
| `shell` | `str` | 平台默认 | 非空字符串 | 集成终端（`Ctrl+`` 打开）启动的 Shell，可带参数（如 `"pwsh -NoLogo"`）；默认 Windows 为 `pwsh`→Windows PowerShell→`cmd.exe`，POSIX 为 `$SHELL`→`bash`→`/bin/sh` |
| `terminal_height` | `int` | `12` | `3`–`40` 的整数（布尔/浮点/字符串被拒绝） | 集成终端面板高度（行数） |

非法取值不会中断加载：对应选项保持默认，错误信息出现在启动消息栏。

选项的作用范围：

- `keymap` / `theme` 在启动时生效；`theme` 是进程级全局状态（同 vim 的
  colorscheme）。
- `tab_width` / `use_spaces` 会传播到**所有新建和打开的 buffer**
  （见 [yate/app.py](../yate/app.py) 中 `_make_buffer` / `_apply_buffer_options`）。
- `shell` 在启动终端 Shell 时读取（会话内 `:set shell=…` 后需重启 Shell 生效）；
  `terminal_height` 同时支持会话内 `:set terminal_height=<n>` 立即调整。

## 内置主题

四个内置主题均为 [Catppuccin](https://catppuccin.com/) 风味：

| 名称 | 风味 | 明暗 |
|---|---|---|
| `mocha` | Catppuccin Mocha | 深色（默认） |
| `macchiato` | Catppuccin Macchiato | 深色 |
| `frappe` | Catppuccin Frappé | 深色 |
| `latte` | Catppuccin Latte | 浅色 |

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

`Theme` 的字段（定义见 [yate/editor_view/theme.py](../yate/editor_view/theme.py)）按用途分组：

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

## 扩展路径（extensions）

`extensions` 选项声明要加载的自定义扩展脚本（扩展 API 见
[yate/services/extensions.py](../yate/services/extensions.py)）。每个
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

除 rc 声明外，扩展仍从默认目录 `./extensions/` 和 `~/.yate/extensions/`
自动加载，也可用命令行 `--ext <文件>` / `--ext-dir <目录>` 追加。

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
