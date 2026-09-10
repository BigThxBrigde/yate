# yate

**yate** — *yet another terminal editor*，基于 [Textual](https://www.textualize.io/)
构建的现代终端文本编辑器。分层架构：`editor_core` 为纯编辑逻辑（与 UI 解耦，
可无头测试），`editor_view` 为 Textual 界面。

## 特性

- **VS Code 风格布局**：活动标签栏、EXPLORER 文件树侧栏、面包屑路径栏、扁平化状态栏
- **两套内置键位**：`vsc`（VS Code 风格、无模式，默认）与 `vim`（NORMAL/INSERT/VISUAL
  模式 + `:` ex 命令行）
- **语法高亮**：内置高亮引擎，按文件类型着色关键字/字符串/数字/注释/函数等
- **四套 Catppuccin 主题**：`mocha`（默认深色）、`macchiato`、`frappe`、`latte`（浅色），
  支持 yaterc 注册自定义主题
- **Nerd Font 图标**：文件树与文件类型图标（`yate --install-font` 可安装随包字体）
- **模糊查找**：`Ctrl+P` 快速打开文件（fzf 式子序列匹配、命中字符高亮），
  `Alt+Shift+P` 命令面板
- **欢迎页**：空 buffer 启动时显示版本、键位提示
- **搜索**：`Ctrl+F` 文件内查找
- **yaterc 配置**：Python 语法配置文件（vimrc 风格），支持用户级/项目级/`-u` 三级加载
- **Python 扩展**：任意 `.py` 脚本通过 `setup(api)` 注册命令、按键绑定和动作

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
yate --install-font         # 安装随包 Nerd Font 后退出
```

### 常用键位（vsc 键位）

| 按键 | 功能 |
|---|---|
| `Ctrl+P` | 模糊快速打开文件 |
| `Alt+Shift+P` | 命令面板（执行任意 `:` 命令） |
| `:` | ex 命令行（`:w` 保存、`:q` 退出、`:theme latte` 切主题…） |
| `Ctrl+S` | 保存 |
| `Ctrl+F` | 文件内查找 |
| `Ctrl+E` | 聚焦文件树（`j`/`k` 移动，`l` 打开，`Esc` 返回） |
| `F1` | 帮助 / 全部键位 |

vim 键位下：`i` 进入插入、`Esc` 回 NORMAL，`:` 打开命令行；完整绑定见 F1 帮助。

## 配置（yaterc）

配置文件是普通 Python：选项即模块级变量。启动时依次加载
`~/.yate/yaterc`（用户级）和当前目录逐级向上的 `yaterc`（项目级，后者覆盖同名选项）。

```python
keymap = "vim"            # "vsc"（默认）/ "vim"
theme = "mocha"           # mocha | macchiato | frappe | latte | 自定义主题
tab_width = 4
use_spaces = True
extensions = [            # 额外扩展路径（目录或 .py 文件，跨 yaterc 累加去重）
    "~/.yate/extensions",
    "./tools/my_ext.py",
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

## 项目结构

```
yate/
  editor_core/    # 纯编辑逻辑：buffer、文档模型、搜索引擎（无 Textual 依赖）
  editor_view/    # Textual 界面：编辑器、文件树、状态栏、命令面板、高亮、主题
  keymaps/        # vsc / vim 键位定义与动作分发
  services/       # workspace 遍历、shell、扩展加载、字体安装
  config.py       # yaterc 配置系统
  app.py          # YateApp：界面组装、命令注册、生命周期
  cli.py          # 命令行入口
extensions/       # 随仓库提供的示例扩展
tests/            # 单元测试 + Textual pilot 端到端测试
docs/yaterc.md    # 配置系统完整文档
```

## 开发

```powershell
# 运行全部测试（96 个，含 Textual pilot 端到端测试）
python -m unittest discover -s tests

# 类型检查：pyright strict，要求 0 诊断
python -m pyright
```

## 许可

MIT
