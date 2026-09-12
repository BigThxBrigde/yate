# yate

**yate** — *yet another terminal editor*，基于 [Textual](https://www.textualize.io/)
构建的现代终端文本编辑器。分层架构：`editor_core` 为纯编辑逻辑（与 UI 解耦，
可无头测试），`editor_view` 为 Textual 界面。

## 📖 用户手册 / Manual

完整使用说明（中英双语），会话内也可按 `F8` 或输入 `:manual` 打开：

| 语言 | 文件 |
|---|---|
| 中文 | [yate/resources/manual.zh.md](yate/resources/manual.zh.md) |
| English | [yate/resources/manual.en.md](yate/resources/manual.en.md) |

## 特性

- **VS Code 风格布局**：活动标签栏、EXPLORER 文件树侧栏、面包屑路径栏、扁平化状态栏
- **两套内置键位**：`vsc`（VS Code 风格、无模式，默认）与 `vim`（NORMAL/INSERT/VISUAL
  模式 + `:` ex 命令行）
- **语法高亮**：内置高亮引擎，按文件类型着色关键字/字符串/数字/注释/函数等
- **四套 Catppuccin 主题**：`mocha`（默认深色）、`macchiato`、`frappe`、`latte`（浅色），
  支持 yaterc 注册自定义主题，也可用 `theme_dirs` / `--theme-dir`
  从主题目录批量加载客制化主题
- **Nerd Font 图标**：文件树与文件类型图标（`yate --install-font` 可安装随包字体）
- **模糊查找**：`Ctrl+P` 快速打开文件（fzf 式子序列匹配、命中字符高亮），
  `Alt+Shift+P` 命令面板
- **欢迎页**：空 buffer 启动时显示版本、键位提示
- **搜索**：`Ctrl+F` 文件内查找
- **集成终端**：`` Ctrl+` `` 切换底部终端面板（VS Code 风格布局），经 PTY 运行真实
  Shell（Windows ConPTY / POSIX pty）；`:term` / `:termclose`、Shell 可在 yaterc
  的 `shell` 选项配置，面板高度用 `terminal_height`（默认 12 行）
- **yaterc 配置**：Python 语法配置文件（vimrc 风格），支持用户级/项目级/`-u` 三级加载
- **Python 扩展**：任意 `.py` 脚本通过 `setup(api)` 注册命令、按键绑定和动作
- **LSP 支持**：内置零依赖 LSP 客户端（`editor_lsp`），提供自动补全弹窗与诊断
  （下划线/装订槽标记/状态栏计数/`:diagnostics`）；语言服务器通过扩展注册，
  仓库内置 Python 服务器扩展（pyright / python-lsp-server 自动发现）

## 环境要求

- Python ≥ 3.10
- 依赖：[textual](https://pypi.org/project/textual/) ≥ 8.0

## 安装

```powershell
git clone <this repo>
cd yate
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e .
```

安装后提供两个等价入口：

```powershell
yate                  # 控制台脚本
python -m yate        # 模块方式
```

## 使用

```powershell
yate                        # 打开空 buffer（显示欢迎页）
yate README.md              # 编辑文件
yate ./src                  # 打开目录，文件树浏览
yate --keymap vim .         # 以 vim 键位启动
yate -u ~/.yate/yaterc      # 使用指定配置文件
yate -u NONE                # 不加载任何 yaterc
yate --ext mytool.py        # 加载扩展脚本（可重复）
yate --ext-dir ./exts       # 加载目录下所有扩展（可重复）
yate --theme-dir ./themes   # 加载客制化主题目录（也接受单个 .py，可重复）
yate --theme my-mocha       # 以指定主题启动（覆盖 yaterc）
yate --install-font         # 安装随包 Nerd Font 后退出
```

### 常用键位（vsc 键位）

| 按键 | 功能 |
|---|---|
| `Ctrl+P` | 模糊快速打开文件 |
| `Alt+Shift+P` | 命令面板（检索并执行全部 `:` 命令与命名动作；vsc 模式下 `:` 是普通字符） |
| `F5` | 打开命令行（ex 命令，`Esc` 退出） |
| `Ctrl+Q` | 退出（有未保存修改时拦截） |
| `Ctrl+S` | 保存 |
| `Ctrl+F` | 文件内查找 |
| `Ctrl+G` | 跳转到行（命令行直接输 `:42` 等效，`:+5` 相对跳转） |
| `Ctrl+B` | 显示/隐藏文件树（命令面板 `explorer` 同效） |
| `` Ctrl+` `` | 显示/隐藏底部集成终端（命令面板 `term` / `termclose`） |
| `Ctrl+E` / `Ctrl+Shift+E` | 聚焦文件树（后者同 VS Code） |
| `Ctrl+1` | 聚焦编辑器（同 VS Code） |
| `Ctrl+Space` | 触发 LSP 自动补全（输入时也会自动弹出，`Tab`/`Enter` 接受） |
| `F1` | 帮助 / 全部键位 |

文件树内（聚焦后）：`j`/`k` 移动，`l`/`h` 展开/折叠，`Enter` 打开文件，
`a` 新建文件，`A` 新建文件夹，`r` 重命名，`d`/`Del` 删除（输入 `y` 确认），
`Esc` 回编辑器。改名/删除会同步已打开的标签页。

vim 键位下：`i` 进入插入、`Esc` 回 NORMAL，`:` 打开命令行；
`Ctrl+W` 后接 `h`/`l` 切到文件树/编辑器（`Ctrl+W Ctrl+W` 来回切换）；
完整绑定见 F1 帮助。

## 配置（yaterc）

配置文件是普通 Python：选项即模块级变量。启动时依次加载
`~/.yate/yaterc`（用户级）和当前目录逐级向上的 `yaterc`（项目级，后者覆盖同名选项）。

```python
keymap = "vim"            # "vsc"（默认）/ "vim"
theme = "mocha"           # mocha | macchiato | frappe | latte | 自定义主题
tab_width = 4
use_spaces = True
shell = "pwsh -NoLogo"    # 集成终端 Shell（默认 pwsh/PowerShell/cmd 或 $SHELL/bash）
terminal_height = 12      # 终端面板高度，3–40 行
theme_dirs = ["~/.yate/themes"]  # 客制化主题目录（默认也扫描 ./themes）
extensions = [            # 额外扩展路径（目录或 .py 文件，跨 yaterc 累加去重）
    "~/.yate/extensions",
    "./tools/my_ext.py",
]
language_servers = [      # 声明式 LSP：打开匹配语言文件时自动激活，无需写扩展
    {"name": "rust-analyzer", "command": "rust-analyzer",
     "filetypes": ["rs"], "language_ids": {"rs": "rust"},
     "root_markers": ["Cargo.toml", ".git"]},
]
```

完整说明（含自定义主题、路径解析规则、错误行为）见
[docs/yaterc.md](docs/yaterc.md)；可直接复制 [yaterc.example](yaterc.example)
作为起点。`yaterc.example` 随测试保证可加载。

## 扩展

扩展是任何暴露 `setup(api)` 的 `.py` 文件：

```python
def setup(api):
    @api.command("hello", "greet from an extension")
    def hello(args):
        api.message("hello!")

    api.bind_key("<alt-h>", lambda ctx: hello(""), keymap="both")
```

加载方式（三选一或组合）：

- 放入 `./extensions/` 或 `~/.yate/extensions/`（启动自动加载）
- yaterc 中 `extensions = [...]` 声明路径
- 命令行 `--ext 文件.py` / `--ext-dir 目录`

`api` 可注册命令（`command` / `register_command`）、按键绑定（`bind_key`，
支持 `vsc` / `vim` / `both`）、命名动作（`register_action`），并可访问
`api.buffer` / `api.doc` / `api.workspace`、`api.shell()` / `api.open_path()` /
`api.save()` / `api.message()`。完整示例见 [extensions/example_ext.py](extensions/example_ext.py)
（`:upper` / `:lower` / `:words` / `:sh` 命令 + `Alt+U` 绑定）。

### LSP 语言服务器

语言服务器按扩展名匹配、首次打开匹配文件时惰性启动，提供自动补全 + 诊断。
配置方式两种：

- **yaterc 声明式（推荐）**：`language_servers = [...]` 字典列表，配置后
  打开匹配文件自动激活，无需写扩展（见上方示例与 [docs/lsp.md](docs/lsp.md)）。
- **扩展**：`api.lsp.register_server(...)` 编程式注册。

仓库内置 [extensions/python_lsp.py](extensions/python_lsp.py)，
打开 `.py` 文件时自动连接 Python 语言服务器，需自行安装其一：

```powershell
pip install python-lsp-server     # pylsp
npm install -g pyright            # 或 pyright-langserver
```

也可用环境变量 `YATE_PYTHON_LSP` 指定命令行（设为 `off` 可禁用）。
详细 API 与行为见用户手册第 16 节
（[中](yate/resources/manual.zh.md) / [En](yate/resources/manual.en.md)，
会话内 `:manual` 或 `F8`）。

## 项目结构

```
yate/
  editor_core/    # 纯编辑逻辑：buffer、文档模型、搜索引擎（无 Textual 依赖）
  editor_term/    # PTY 后端（ConPTY/POSIX pty）、VT100 仿真、Shell 解析
  editor_lsp/     # UI 无关的 LSP 客户端：JSON-RPC、进程管理、补全/诊断状态
  editor_view/    # Textual 界面：编辑器、文件树、状态栏、命令面板、终端、高亮、主题
  keymaps/        # vsc / vim 键位定义与动作分发
  services/       # workspace 遍历、shell、扩展加载、字体安装
  config.py       # yaterc 配置系统
  app.py          # YateApp：界面组装、命令注册、生命周期
  cli.py          # 命令行入口
extensions/       # 随仓库提供的扩展（example_ext 示例、python_lsp 内置 LSP）
tests/            # 单元测试 + Textual pilot 端到端测试
docs/             # yaterc 配置、扩展、主题、LSP 配置文档
  yaterc.md       # 配置系统完整文档
  extensions.md   # 扩展 API 参考
  themes.md       # 主题客制化
  lsp.md          # 主流语言 LSP 配置食谱
yate/resources/   # 资源：manual.zh.md / manual.en.md 双语用户手册、随包字体
```

## 开发

```powershell
# 运行全部测试（224 个，含 Textual pilot 端到端测试）
python -m unittest discover -s tests

# 类型检查：pyright strict，要求 0 诊断
python -m pyright
```

## 许可

MIT
