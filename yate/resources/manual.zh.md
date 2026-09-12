# yate 用户手册

**yate** — *yet another terminal editor*，一个基于
[Textual](https://www.textualize.io/) 构建的现代终端文本编辑器。
版本 **0.1.0**（本手册随程序打包，按 `F8` 或输入 `:manual` 可随时打开）。

yate 采用分层架构：`editor_core` 是与界面完全解耦的纯编辑逻辑
（缓冲区、文档模型、搜索引擎），`editor_view` 是 Textual 界面，
`keymaps` 提供可插拔键位，`services` 负责工作区、Shell、扩展与字体。

---

## 目录

1. 系统要求与安装
2. 启动与命令行参数
3. 界面导览
4. 快速上手
5. 键位总览（vsc 键位 / vim 键位）
6. 文件浏览器（EXPLORER）
7. 搜索与替换
8. 命令行（ex 命令）
9. 命令面板与快速打开
10. 配置文件 yaterc
11. 主题
12. 字体与 Nerd Font 图标
13. 集成终端
14. Shell 集成
15. Python 扩展
16. 语言服务器（LSP）
17. 常见问题（FAQ）
18. 键位速查表

---

## 1. 系统要求与安装

| 项目 | 要求 |
|---|---|
| Python | ≥ 3.10 |
| 核心依赖 | textual ≥ 8.0 |
| 终端 | 任何支持 ANSI 转义序列的现代终端（推荐 Windows Terminal） |
| 字体 | 建议安装 Nerd Font 以显示文件图标（见第 12 节） |

从源码安装（Windows PowerShell 示例）：

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
python -m yate        # 模块方式运行
```

查看版本：`yate --version`。

## 2. 启动与命令行参数

```
yate [路径] [选项]
```

| 参数 | 说明 |
|---|---|
| `路径`（可选） | 要打开的文件或目录。目录会在文件树中浏览；不存在的路径按"尚未创建的新文件"处理 |
| `--keymap {vsc,vim,normal}` | 指定启动键位；`normal` 是 `vsc` 的兼容别名。**优先级高于 yaterc** |
| `-u FILE` / `--yaterc FILE` | 只加载指定配置文件（vim 风格 `-u`）；`-u NONE` 完全跳过配置加载 |
| `--ext FILE` | 加载一个 Python 扩展脚本（可重复） |
| `--ext-dir DIR` | 加载目录下所有 `*.py` 扩展（可重复） |
| `--theme-dir DIR` | 从目录加载客制化 `*.py` 配色主题（可重复，也接受单个 `*.py` 文件；默认扫描 `./themes` 与 `~/.yate/themes`），见 10.3 节 |
| `--theme NAME` | 启动时选用的主题名（内置或已注册的客制化主题），覆盖 yaterc 中的 `theme` |
| `--install-font` | 为当前用户安装随包 Nerd Font（必要时配置 Windows Terminal），完成后退出，不进入界面 |
| `--version` | 显示版本号 |
| `--help` | 显示帮助 |

启动示例：

```powershell
yate                        # 打开空 buffer（显示欢迎页）
yate README.md              # 编辑文件
yate ./src                  # 打开目录，文件树浏览
yate --keymap vim .         # 以 vim 键位启动
yate -u ~/.yate/yaterc      # 使用指定配置文件
yate -u NONE                # 不加载任何 yaterc
yate --ext mytool.py        # 加载扩展脚本（可重复）
yate --ext-dir ./exts       # 加载目录下所有扩展（可重复）
yate --theme-dir ./themes   # 从目录加载客制化配色主题
yate --theme my-mocha       # 直接选用（客制化）主题启动
yate --install-font         # 安装随包 Nerd Font 后退出
```

## 3. 界面导览

yate 的布局模仿 VS Code，自上而下分为几个区域：

```
┌────────────┬──────────────────────────────────┐
│  EXPLORER  │  标签栏（tab bar）                │
│  文件树     │  面包屑路径栏（breadcrumbs）       │
│  侧栏       │  编辑区（editor）                 │
├────────────┴──────────────────────────────────┤
│  状态栏（status bar）                          │
│  命令行 / 消息栏（command line / message）      │
└───────────────────────────────────────────────┘
```

### 3.1 EXPLORER 文件树侧栏

- 顶部标题为 `EXPLORER`，宽度约 34 个字符列。
- 显示打开目录的树状结构；目录排在文件之前、各自按名称排序。
- 每个条目带 Nerd Font 图标（目录、按扩展名区分的文件类型图标）。
- 目录按需懒加载：首次展开时才读取子目录。
- 未打开任何目录时显示 `no folder open`，此时可用 `:e <路径>` 打开。
- 键盘操作详见第 6 节。

### 3.2 标签栏

- 每个打开的文档一个标签：` <图标> 文件名`；活动标签使用编辑区底色，
  非活动标签使用面板底色。
- 文件被修改后，标签上出现橙色 `●` 标记。
- 名称过长时按显示宽度截断。

### 3.3 面包屑路径栏

- 显示当前文档相对工作区根目录的完整路径：`图标 目录 › 子目录 › 文件名`。
- 文件名始终加粗显示；空间不足时从左侧截断并显示 `…`（文件名永远可见）。
- 未命名 buffer 不显示面包屑（标签栏已显示 `[no name]`）。

### 3.4 编辑区

- 左侧行号槽；当前行的行号加粗并使用主题强调色。
- 当前行整行高亮（surface 底色）。
- 方块光标；行尾时光标显示在行末补位上。
- 内置语法高亮引擎按文件类型着色（支持的语言清单见第 17 节 FAQ：
  Python、C/C++、Java、Rust、Go、JavaScript/TypeScript、Shell、JSON、
  Markdown、TOML、INI、YAML）。
- 选区、搜索匹配（当前匹配使用更醒目的颜色）均以主题色叠加渲染。
- 空的未命名 buffer 显示欢迎页：YATE 字符画、版本号与常用键位提示。
  欢迎页只在启动时出现一次：开始输入、或用 `:enew`（及"新建空缓冲区"
  动作）新建 buffer 后即关闭，且不会再因切换标签而重新出现；如需再次查看，
  执行 `:welcome`（在空的未命名 buffer 上显示）。

### 3.5 状态栏

左侧模式色块 + 文件信息，右侧位置与元信息：

- **模式色块**：vsc 键位显示 `VSC`；vim 键位显示 `NORMAL` / `INSERT` /
  `VISUAL` / `V-LINE`；命令行处于不同输入状态时显示 `COMMAND` / `SEARCH` /
  `SHELL`。
- 文件名（带铅笔图标），未保存时后跟 `●`。
- 右侧：`Ln 行, Col 列`、总行数、文件类型（扩展名）、编码；
  末尾是提示图标区：已加载扩展数、`:!`（Shell 命令）、`F1`（帮助）。

### 3.6 命令行 / 消息栏

最底部一行，平时显示消息（vsc 模式启动时为
`yate 0.1.0 — F1 help, Ctrl+P quick open, Alt+Shift+P command palette`；
vim 模式为 `-- NORMAL -- (F1 help, : commands)`），
激活输入时按模式显示不同前缀：

| 模式 | 前缀 | 触发方式 |
|---|---|---|
| 命令 | `:` | vim NORMAL 模式 `:`；vsc 模式 `F5`（或命令面板） |
| 向下查找 | 放大镜图标 | `Ctrl+F`（vsc）、`/`（vim） |
| 向上查找 | `?` | `?`（vim） |
| 替换（第一步） | `Replace:` | `F4` |
| 替换（第二步） | `With:` | 输入查找文本后自动进入 |
| Shell | 终端图标 | `F2`、`:!命令` |
| 打开文件 | `Open: ` | `Ctrl+O`、`:e`（无参数时） |
| 另存为 | `Save as: ` | 对未命名 buffer 执行保存 |
| 新建文件 | `New file: ` | 文件树内 `a` |
| 新建文件夹 | `New folder: ` | 文件树内 `A` |
| 重命名 | `Rename: ` | 文件树内 `r` |
| 删除确认 | `Delete? ` | 文件树内 `d` 或 `Del` |

输入行支持历史记录：`↑` / `↓` 翻阅历史，`Esc` 或 `Ctrl+C` 取消。
查找模式输入时即实时高亮全部匹配。

### 3.7 命令面板

- `Alt+Shift+P` 打开**命令面板**：列出全部 `:` 命令（齿轮图标）与命名动作
  （键盘图标），可按全称模糊检索（命令的描述文本也参与匹配），回车执行。
- `Ctrl+P` 打开**快速打开**（文件面板）：模糊搜索工作区内文件，回车打开。
- 两者共用同一组件，见第 9 节。

### 3.8 集成终端

- 底部面板（编辑区与状态栏之间）内嵌经伪终端连接的真实 Shell；
  `` Ctrl+` `` 切换面板并聚焦终端。
- 隐藏时 Shell 保持运行；Shell 退出后按任意键重启；可通过 `shell` /
  `terminal_height` 配置，见第 13 节。

## 4. 快速上手

1. **打开文件**：启动参数传入路径、`Ctrl+P` 模糊打开、`Ctrl+O` / `:e`
   按路径打开；打开目录则进入文件树浏览。
2. **编辑**：直接输入即可（vsc 键位无模式）。回车自动缩进；
   `Tab` 按 yaterc 配置插入空格或制表符。
3. **保存**：`Ctrl+S` 或 `:w`。未命名 buffer 会弹出 `Save as: ` 输入行；
   保存后工作区根目录随之切换到文件所在目录。
4. **切换标签**：`Ctrl+PageUp` / `Ctrl+PageDown`，或 `:bn` / `:bp`。
5. **退出**：`Ctrl+Q` 或 `:q`。有未保存修改时会提示
   `unsaved changes — :q! to quit anyway`；`Ctrl+S` 保存后再退出，
   或 `:q!` / `:wq` 强制处理。
6. **获取帮助**：`F1` 键位参考（按当前键位分组 + 全部 `:` 命令）；
   `F8` 或 `:manual` 打开本手册（`Esc` / `q` 关闭，`PgUp`/`PgDn` 或滚轮滚动；
   `/` 或 `Ctrl+F` 检索手册内容，`Enter` / `Shift+Enter` 在匹配项间跳转，
   关闭检索栏后 `n` / `N` 可继续上一项/下一项匹配）。
7. **终端**：按 `` Ctrl+` `` 打开底部集成 Shell（`:term` / `:termclose` 同效）；
   面板隐藏期间 Shell 持续运行。

> 注意：剪贴板操作（剪切/复制/粘贴）使用 yate **内部寄存器**，
> 不读写系统剪贴板（详见 5.1 节）。

## 5. 键位总览

yate 内置两套键位：

- **`vsc`**（默认）：VS Code 风格、无模式。
- **`vim`**：NORMAL / INSERT / VISUAL / VISUAL-LINE 模式 + `:` ex 命令行。

切换方式（任选其一）：

| 方式 | 操作 |
|---|---|
| 会话内切换 | `Ctrl+/`（部分终端发送 `Ctrl+_`）在两套键位间切换 |
| 命令 | `:set keymap=vsc` / `:set keymap=vim`；快捷别名 `:vsc`、`:vim`、`:normal`（`:normal` 是 `:vsc` 的别名） |
| 配置 | yaterc 中 `keymap = "vsc"` 或 `"vim"` |
| 命令行 | `yate --keymap vim`（优先级高于 yaterc） |

`F1` 帮助浮层始终显示**当前键位**的完整绑定，按类别分组，并列出全部 `:` 命令。

### 5.1 vsc 键位（默认，无模式）

**编辑（Editing）**

| 按键 | 功能 |
|---|---|
| `Enter` | 插入换行（自动缩进） |
| `Tab` | 缩进 / 插入制表符（受 `use_spaces` 影响） |
| `Backspace` | 删除光标前字符 |
| `Delete` | 删除光标后字符 |
| `Alt+Backspace` | 删除光标前一个词 |
| `Alt+D` | 删除光标后一个词 |
| `Ctrl+D` | 复制当前行 / 选区 |
| `Ctrl+Shift+K` | 删除当前行 |
| `Alt+↑` / `Alt+↓` | 上移 / 下移当前行 |
| `Ctrl+]` | 增加缩进（行 / 选区） |
| `Shift+Tab` | 减少缩进（行 / 选区） |
| `Ctrl+J` | 合并行 |

**导航（Navigation）**

| 按键 | 功能 |
|---|---|
| `←` `→` `↑` `↓` | 光标移动 |
| `Ctrl+←` / `Ctrl+→` | 按词移动 |
| `Home` | 行首（在列 0 与首个非空白字符之间切换） |
| `End` | 行尾 |
| `Ctrl+Home` / `Ctrl+End` | 文档开头 / 文档结尾 |
| `PageUp` / `PageDown` | 翻页 |

**选择（Selection）**

| 按键 | 功能 |
|---|---|
| `Shift+←` `Shift+→` `Shift+↑` `Shift+↓` | 方向选择 |
| `Ctrl+Shift+←` / `Ctrl+Shift+→` | 按词选择 |
| `Shift+Home` / `Shift+End` | 选择到行首 / 行尾 |
| `Ctrl+A` | 全选 |
| `Esc` | 清除选区 |

**历史与剪贴板（History / Clipboard）**

| 按键 | 功能 |
|---|---|
| `Ctrl+Z` | 撤销（连续输入会合并为一步） |
| `Ctrl+Y` | 重做 |
| `Ctrl+X` | 剪切选区 / 当前行到内部寄存器 |
| `Ctrl+C` | 复制选区 / 当前行到内部寄存器 |
| `Ctrl+V` | 从内部寄存器粘贴 |

> 剪贴板说明：复制/剪切/粘贴使用编辑器内部的 yank/clipboard 寄存器，
> 不与操作系统剪贴板交换数据。

**文件（File）**

| 按键 | 功能 |
|---|---|
| `Ctrl+S` | 保存文件 |
| `Ctrl+O` | 按路径打开文件（`Open: ` 输入行） |
| `Ctrl+N` | 新建空 buffer |
| `Ctrl+W` | 关闭当前标签 |
| `Ctrl+Q` | 退出 yate（有未保存修改时会拦截） |

> vsc 模式下 **`:` 不是快捷键**——它和普通字符一样会输入到 buffer 中。
> vsc 模式要执行 ex 命令，可按 `F5` 打开命令行（输入 `:w` `:q` 等，无需先输
> 入冒号），或用 `Alt+Shift+P` 打开命令面板（见 3.7 节）。

**搜索（Search）**

| 按键 | 功能 |
|---|---|
| `Ctrl+F` | 文件内查找（实时高亮，`Enter` 跳转） |
| `F3` | 下一个匹配 |
| `F4` | 查找并替换（两步输入，全部替换） |

**视图与工具（View / Tools）**

| 按键 | 功能 |
|---|---|
| `Ctrl+P` | 快速打开文件（模糊匹配） |
| `Alt+Shift+P` | 命令面板（执行任意 `:` 命令） |
| `F5` | 命令行（ex 命令：`:w` `:q` `:e` 等，`Esc` 退出） |
| `Ctrl+/` | 切换 vsc / vim 键位 |
| `Ctrl+E` / `Ctrl+Shift+E` | 聚焦文件树（`Ctrl+Shift+E` 同 VS Code） |
| `Ctrl+1` | 聚焦编辑器（同 VS Code） |
| `Ctrl+B` | 显示 / 隐藏文件树（`:explorer` 同效） |
| `` Ctrl+` `` | 显示 / 隐藏集成终端（见第 13 节） |
| `F2` | 运行 Shell 命令 |

**标签（Tabs）**

| 按键 | 功能 |
|---|---|
| `Ctrl+PageUp` | 上一个标签 |
| `Ctrl+PageDown` | 下一个标签 |

**帮助（Help）**

| 按键 | 功能 |
|---|---|
| `F1` | 键位参考（帮助浮层） |
| `F8` | 打开用户手册（本手册，只读渲染；手册内 `/` 或 `Ctrl+F` 可检索） |

### 5.2 vim 键位（有模式）

状态栏左下角实时显示当前模式。数字键（`1`–`9`）作为计数前缀，
可叠加在多数移动与操作符之前，如 `3j`、`2dd`、`5w`。

**移动（Vim: motion）**

| 按键 | 功能 |
|---|---|
| `h` `l` `j` `k` | 左 / 右 / 下 / 上 |
| `w` / `b` / `e` | 下一词首 / 上一词首 / 词尾 |
| `0` | 行首（列 0） |
| `$` | 行尾 |
| `gg` | 文档开头；`gg` 前加数字跳转到指定行（如 `5gg`） |
| `G` | 文档结尾；前加数字同样跳转到指定行 |
| `Ctrl+D` / `Ctrl+U` | 下移 / 上移半页 |
| `Ctrl+F` / `Ctrl+B` | 下翻 / 上翻一页 |

**进入插入模式（Vim: insert）**

| 按键 | 功能 |
|---|---|
| `i` | 在光标前插入 |
| `a` | 在光标后插入 |
| `I` | 在行首插入 |
| `A` | 在行尾插入 |
| `o` | 在下方新建一行并插入 |
| `O` | 在上方新建一行并插入 |
| `Esc` | 回到 NORMAL 模式（光标左移一格，与 vim 一致） |

**编辑（Vim: edit）**

| 按键 | 功能 |
|---|---|
| `x` | 删除光标处字符（支持计数） |
| `dd` | 删除（剪切）当前行 |
| `yy` | 复制当前行 |
| `d{motion}` | 删除到 motion 处（如 `dw`、`d$`、`dj`） |
| `y{motion}` | 复制到 motion 处 |
| `p` / `P` | 粘贴到下方 / 上方 |
| `u` | 撤销 |
| `Ctrl+R` | 重做 |
| `J` | 合并下一行 |
| `v` | 字符可视模式（`-- VISUAL --`） |
| `V` | 行可视模式（`-- VISUAL LINE --`） |

**命令（Vim: command）**

| 按键 | 功能 |
|---|---|
| `/` | 向下查找 |
| `?` | 向上查找 |
| `n` / `N` | 下一个 / 上一个匹配 |
| `:` | ex 命令行（`:w` `:q` `:e` `:!` 等） |

**窗口切换**

| 按键 | 功能 |
|---|---|
| `Ctrl+W` `h` | 聚焦文件树（左窗格） |
| `Ctrl+W` `l` | 聚焦编辑器（右窗格） |
| `Ctrl+W` `Ctrl+W` | 在文件树与编辑器间来回切换 |

**INSERT 模式下**：`Esc` 回 NORMAL；`Ctrl+W` 删除前一个词；
`Ctrl+U` 删除到行首；`Backspace` / `Delete` / `Enter` / `Tab` 与方向键按常规定位。
**VISUAL 模式下**：`v` / `V` 切换或退出；`y` 复制选区；`d` / `x` 删除选区；
`:` `/` `?` 先退出可视模式再打开对应输入行；移动键延伸选区。
NORMAL 模式下未映射的按键会被吞掉，不会插入文本。

vim 键位下 `Ctrl+F` 是翻页而非查找；`Ctrl+P` 快速打开、`Alt+Shift+P`
命令面板、`` Ctrl+` `` 集成终端、`F1` 帮助、`F8` 手册仍然可用。

## 6. 文件浏览器（EXPLORER）

### 6.1 打开与聚焦

| 按键 | 功能 |
|---|---|
| `Ctrl+B` | 显示 / 隐藏文件树（未打开目录时侧栏自动隐藏） |
| `Ctrl+E` / `Ctrl+Shift+E` | 聚焦文件树（未打开目录时提示 `no folder is open — use :e <path>`，若已隐藏会先显示） |
| `Ctrl+1` | 聚焦编辑器 |
| `Esc`（在文件树内） | 焦点返回编辑器 |

用 `:e <目录>`、`Ctrl+O` 输入目录路径或启动参数传目录即可打开工作区。

### 6.2 树内键盘操作

聚焦文件树后：

| 按键 | 功能 |
|---|---|
| `j` / `k` | 光标下移 / 上移 |
| `l` / `Enter` | 展开 / 折叠目录；文件则在编辑器中打开并回到编辑器 |
| `h` | 折叠当前目录；已折叠或光标在文件上时跳到父节点 |
| `a` | 新建文件 |
| `A` | 新建文件夹 |
| `r` | 重命名 |
| `d` / `Delete` | 删除（输入 `y` 或 `yes` 确认，其他输入取消） |
| `Esc` | 回编辑器 |

其他行为：

- **新建**：在光标所在目录（光标在文件上时为其同级目录）内创建。
  输入行占位符显示目标目录。新建**文件**会立即在编辑器中打开（VS Code 行为）；
  新建**文件夹**保持文件树焦点。文件名不允许为空、`.`、`..`，
  也不允许包含 `/` `\` `:`；重名会报错。
- **重命名**：输入行预填当前名称；已打开的对应标签会同步指向新路径。
- **删除**：删除目录会递归删除整棵子树；位于其下方的已打开标签会被关闭
  （提示关闭了多少个标签）。删除全部标签后回到空 buffer。
- 文件树内输入普通可打印字符会被吞掉，不会泄漏到编辑器。
- 目录 `.git`、`.hg`、`.svn`、`__pycache__`、`.venv`、`venv`、
  `node_modules`、`.mypy_cache`、`.pytest_cache`、`.ruff_cache`、
  `.idea`、`.vscode` 不会显示在树中，快速打开也不会索引它们。
- 刷新树（如外部改动、主题切换、保存文件）时，各目录的展开状态会保留。

## 7. 搜索与替换

- **查找**：`Ctrl+F`（vsc）或 `/`（vim，向下）、`?`（vim，向上）。
  输入即实时高亮全部匹配；`Enter` 跳到当前方向的下一个匹配并显示
  `[序号/总数]`；`F3`（vsc）或 `n` / `N`（vim）继续跳转。
  匹配从光标位置就近开始，到文件末尾后回绕。
- **取消**：`Esc` 或 `Ctrl+C` 关闭查找输入行并清除高亮。
- **替换**：`F4` 分两步：先输入查找文本（`Replace:`），再输入替换文本
  （`With:`）。确认后**一次性替换全部匹配**，并作为单条撤销记录
  （一次 `Ctrl+Z` / `u` 即可整体撤销）。结果消息显示替换次数。
- 默认**不区分大小写**；查找为普通文本匹配（非正则）。
- 无匹配时消息栏提示 `no matches for '…'`；
  没有活动搜索时按 `F3` 提示先按 `/` 或 `Ctrl+F` 发起搜索。

## 8. 命令行（ex 命令）

vim NORMAL 模式按 `:` 进入命令行。vsc 模式下 `:` 是可编辑的普通字符，
可按 `F5` 打开命令行（或用命令面板 `Alt+Shift+P`）执行同样的命令。命令后
可跟参数，以空格分隔。`Esc` / `Ctrl+C` 取消，`↑` / `↓` 翻阅历史。未知命令提示
`not an editor command: … (try :help)`。

**Tab 补全。** 按 `Tab` 以 bash 风格补全已输入的文本：先补全命令名；
命令名后接空格时，`Tab` 补全参数——`:e`/`:edit` 补文件路径，
`:theme`/`:colorscheme` 补主题名，`:set` 补选项键与值，
`:filetype`/`:ft`/`:language` 与 `:set filetype=` 补语法类型名（含
`auto`），`:manual` 补 `en`/`zh`。第一次 `Tab` 展开为所有匹配项的最长
公共前缀（唯一匹配直接插入）；连续按 `Tab` 在所有匹配项间轮询。

**文件操作**

| 命令 | 别名 | 说明 |
|---|---|---|
| `:w` | `:write` | 保存当前文件 |
| `:q` | `:quit` | 退出 yate（有未保存修改时拦截） |
| `:q!` | — | 丢弃修改并强制退出 |
| `:wq` | — | 保存并退出 |
| `:e [路径]` | `:edit` | 打开文件或目录；无参数时弹出 `Open: ` 输入行 |
| `:enew` | — | 新建空 buffer（同时关闭欢迎页，本会话不再自动出现） |
| `:welcome` | — | 重新开启欢迎页（在空的未命名 buffer 上显示） |
| `:bn` | `:bnext` | 下一个 buffer / 标签 |
| `:bp` | `:bprev` | 上一个 buffer / 标签 |
| `:bd` | — | 关闭当前 buffer / 标签 |

**界面与工具**

| 命令 | 说明 |
|---|---|
| `:files` | 快速打开文件面板（同 `Ctrl+P`） |
| `:palette` | 命令面板（同 `Alt+Shift+P`） |
| `:manual` | 打开用户手册（本手册） |
| `:help` | 键位参考浮层（同 `F1`） |
| `:explorer` | 显示 / 隐藏文件树（同 `Ctrl+B`） |
| `:term` | 显示 / 聚焦集成终端（别名 `:terminal`，见第 13 节） |
| `:termclose` | 隐藏集成终端（Shell 进程保持运行） |
| `:font` | 检测并（必要时）安装随包 Nerd Font，配置 Windows Terminal |

**选项与外观（只影响当前会话，不写回 yaterc）**

| 命令 | 说明 |
|---|---|
| `:set keymap=vsc` 或 `:set keymap=vim` | 切换键位 |
| `:set theme=<名称>` | 切换主题 |
| `:vsc` | 切换到 vsc 键位 |
| `:vim` | 切换到 vim 键位 |
| `:normal` | `:vsc` 的别名 |
| `:theme [名称]` | 切换主题；不带参数时显示当前主题及全部可用主题 |
| `:colorscheme [名称]` | `:theme` 的别名 |
| `:set shell=<命令>` | 设置集成终端的 Shell（下次启动 Shell 时生效） |
| `:set terminal_height=<n>` | 终端面板高度（行数，`3`–`40`），立即生效 |
| `:set filetype=<类型>` | 手动指定当前缓冲区的语法类型（别名 `ft` / `language` / `lang`），见第 17 节 FAQ |
| `:filetype [类型]` | 同上；不带参数时显示当前类型及全部可用类型（别名 `:ft`、`:language`） |

**Shell**

| 命令 | 说明 |
|---|---|
| `:!命令` | 运行 Shell 命令（如 `:!git status`），详见第 14 节 |

## 9. 命令面板与快速打开

两个浮层共用一个组件，均为模糊匹配（fzf 式子序列打分：
查询字符须按顺序出现，词首/路径边界命中得分更高，命中字符高亮显示）。

- **快速打开**（`Ctrl+P` 或 `:files`）：列出工作区（或未打开目录时的当前
  工作目录）下的全部文件（上限 5000 个，忽略目录已剪除），回车打开并聚焦
  编辑器。
- **命令面板**（`Alt+Shift+P` 或 `:palette`）：列出全部 `:` 命令（齿轮图标）
  与全部命名动作（键盘图标，含内建动作与扩展注册的动作），每项显示全称，
  可按全称模糊检索；命令模式下命令的描述文本也参与匹配（描述命中排在名称
  命中之后），回车执行。查询中的空格会被忽略（输入 `ctrlp` 能匹配
  `ctrl p`）。

浮层内按键：

| 按键 | 功能 |
|---|---|
| `↑` / `↓`（或 `Ctrl+P` / `Ctrl+N`） | 移动高亮行 |
| `Tab` / `Shift+Tab` | 向下 / 向上轮询高亮项；**仅剩唯一匹配时按 `Tab` 直接执行/打开**（bash 风格） |
| `Enter` | 打开选中文件 / 执行选中命令或动作 |
| `Esc` / `Ctrl+C` | 关闭浮层 |

最多同时显示 12 行结果；无匹配时显示 `no matches`。

> 为什么是 `Alt+Shift+P` 而不是 `Ctrl+Shift+P`？
> Windows Terminal 保留了 `Ctrl+Shift+P` 作为自己的命令面板，
> `Alt+Shift+P` 在常见终端中都未被占用，故选其为默认。

## 10. 配置文件 yaterc

yate 使用 **Python 语法的配置文件 yaterc**（类似 vim 的 `vimrc`）：
选项就是普通的模块级变量，文件里可以写任意 Python 代码。

### 10.1 位置与加载顺序

启动时按以下顺序加载，**后加载者覆盖先加载的同名选项**：

| 顺序 | 来源 | 路径 | 说明 |
|---|---|---|---|
| 1 | 用户级 | `~/.yate/yaterc` | 全局个人配置；不存在则跳过 |
| 2 | 项目级 | 从当前目录（或启动时打开文件所在目录）**逐级向上**查找 `yaterc` | 最近一级生效；适合随项目提交 |
| 3 | 命令行 | `yate -u <文件>` | **替换**前两者，只加载该文件 |

特例：`yate -u NONE` 完全跳过配置加载。

行为细节：

- 多个文件在**同一个命名空间**内依次执行，项目级配置能看到并覆盖用户级变量。
- 未被识别的变量会被**静默忽略**，可用于定义辅助函数/常量。
- 读取失败、语法错误、运行时异常都**不会导致编辑器崩溃**：出错的文件被跳过，
  问题以 `yaterc: ...` 前缀显示在启动消息栏，其余文件继续加载。
- 非法取值同样不中断加载：对应选项保持默认，错误信息出现在消息栏。

### 10.2 选项参考

| 选项 | 类型 | 默认值 | 合法值 | 说明 |
|---|---|---|---|---|
| `keymap` | `str` | `"vsc"` | `"vsc"` / `"vim"` | 按键映射；非法值回退默认并报错 |
| `theme` | `str` | `"mocha"` | 已注册主题名 | 配色方案，见第 11 节；未知主题在启动消息栏报警 |
| `tab_width` | `int` | `4` | 1–16 的整数（`True`/`False` 等布尔值会被拒绝） | Tab 键插入的空格数，也是 Tab 的显示宽度 |
| `use_spaces` | `bool` | `True` | `True` / `False` | `True` 时 Tab 插入空格，`False` 时插入真实制表符 |
| `extensions` | `str` 或 `list[str]` | 无 | 存在的文件/目录路径 | 额外扩展脚本路径，见 10.4 节 |
| `theme_dirs` | `str` 或 `list[str]` | 无 | 存在的文件/目录路径 | 存放客制化配色主题的目录（或单个 `*.py` 文件），见 10.3 节 |
| `shell` | `str` | 平台默认（见第 13 节） | 非空字符串 | 集成终端使用的 Shell，可带参数（如 `"pwsh -NoLogo"`）；若值是已存在的文件路径，含空格也可直接使用 |
| `terminal_height` | `int` | `12` | 3–40 的整数（布尔/浮点被拒绝） | 集成终端面板高度（行数） |

- `keymap` / `theme` 在启动时生效；`theme` 是进程级全局状态（同 vim 的
  colorscheme）。
- `tab_width` / `use_spaces` 会传播到**所有新建和打开的 buffer**。
- `shell` 在启动终端 Shell 时读取（修改后需重启 Shell 生效）；
  `terminal_height` 也可用 `:set terminal_height=<n>` 立即调整。

最小示例（可直接复制仓库根目录的 `yaterc.example` 作起点）：

```python
keymap = "vim"
theme = "latte"
tab_width = 2
use_spaces = False
```

### 10.3 客制化主题目录（theme_dirs）

yaterc 命名空间中注入了 `register_theme()` 函数，少量改色可以直接写在
yaterc 文件里。若要维护可复用的主题库，可通过 `theme_dirs` 指定一个或多个
目录：启动时会加载其中所有 `*.py` 文件（下划线开头的跳过），也可以直接给
单个 `*.py` 主题文件：

```python
theme_dirs = "~/.yate/themes"           # 单个目录，字符串即可
theme_dirs = [
    "~/.yate/themes",                   # 自动展开 ~
    "./team-themes",                    # 相对路径：相对于本 yaterc 所在目录
    "./extras/solarized.py",            # 单个主题文件
]
theme = "my-mocha"                      # 从这些文件注册的主题中选用
```

主题文件就是普通 Python，作用域内已注入 `Theme` 与 `register_theme()`，也可
正常使用 `import`。最简单的做法是用 `dataclasses.replace` 复制内置主题再
覆盖少量颜色：

```python
# ~/.yate/themes/my_mocha.py
from dataclasses import replace
from yate.editor_view.theme import THEMES

register_theme(replace(
    THEMES["mocha"],
    name="my-mocha",        # 必须唯一；与内置主题重名会覆盖内置主题
    label="My Mocha",
    accent="#89b4fa",       # 主色：状态栏底色、活动 tab、选中项
    accent2="#cba6f7",      # 次色
))
```

不做任何配置也有默认扫描位置：工作目录下的 `./themes` 和 `~/.yate/themes`；
临时目录可用命令行 `--theme-dir DIR`（可重复）指定。同名主题被多次注册时，
后加载者覆盖先加载者，优先级从低到高为：

1. 内置主题（最低）
2. `./themes`、`~/.yate/themes`
3. yaterc 中的 `theme_dirs`（先用户 rc、后项目 rc）
4. 命令行 `--theme-dir`（最高）

主题文件出错不会中断启动：错误会显示在启动消息栏，其余文件照常加载。注册后
的客制化主题与内置主题用法一致：yaterc 中 `theme = "my-mocha"`、运行时
`:theme my-mocha`，或用无参数 `:theme` 列出所有已注册主题名。

`Theme` 字段按用途分组：背景（`bg`/`panel`/`surface`/`gutter_bg`/`border`）、
叠加层（`selection_bg`/`match_bg`/`match_active_bg`/`on_accent`）、
前景（`fg`/`fg_dim`/`fg_muted`/`fg_bright`）、强调色
（`accent`/`accent2`/`green`/`yellow`/`red`/`orange`）、
模式色块（`mode_normal_bg`/`mode_insert_bg`/`mode_visual_bg`/`mode_command_bg`）、
语法色板（`syn_keyword`/`syn_string`/`syn_number`/`syn_comment`/
`syn_function`/`syn_type`/`syn_constant`/`syn_builtin`/`syn_decorator`/
`syn_operator`/`syn_property`）。

> 完整的 `Theme` 字段说明、从零构造主题的示例以及加载优先级，见
> [`docs/themes.md`](../../docs/themes.md)。

### 10.4 扩展路径（extensions）

`extensions` 接受一个路径字符串或路径列表，每项可以是：

- **目录**：加载其中所有 `*.py`（下划线开头的文件跳过）；
- **`.py` 文件**：只加载该文件。

```python
extensions = "~/.yate/myext.py"          # 单个文件
extensions = [
    "~/.yate/extensions",                # 目录：加载其中所有 .py
    "./tools/yate_exts",                 # 相对路径：相对本 yaterc 所在目录
    "/opt/yate/extra.py",                # 绝对路径
]
```

规则：

- `~` 展开为用户主目录；**相对路径相对声明它的 yaterc 文件所在目录**解析，
  项目级配置随项目移动仍然有效。
- 用户级与项目级 yaterc 的 `extensions` **累加**（与标量选项"后者覆盖"不同）；
  同一路径重复声明只加载一次。
- 路径不存在或类型错误作为配置错误显示在消息栏，不影响其余选项。
- 即使同一脚本同时被 rc、默认目录和命令行参数命中，也只会加载一次
  （按解析后的绝对路径去重）。

除 rc 声明外，扩展还会从默认目录 `./extensions/`、`~/.yate/extensions/`
自动加载，也可用 `--ext <文件>` / `--ext-dir <目录>` 追加（详见第 15 节）。

## 11. 主题

四套内置主题均为 [Catppuccin](https://catppuccin.com/) 风味：

| 名称 | 主题 | 明暗 |
|---|---|---|
| `mocha` | Catppuccin Mocha | 深色（默认） |
| `macchiato` | Catppuccin Macchiato | 深色 |
| `frappe` | Catppuccin Frappé | 深色 |
| `latte` | Catppuccin Latte | 浅色 |

切换方式：

| 方式 | 操作 |
|---|---|
| 命令 | `:theme latte`、`:colorscheme latte`（不带参数列出全部可用主题） |
| 选项 | `:set theme=latte` |
| 配置 | yaterc 中 `theme = "latte"` |
| 启动参数 | `yate --theme latte`（覆盖 yaterc 的 `theme`） |
| 自定义 | yaterc 中 `register_theme(...)` 内联注册，或将 `*.py` 主题文件放入 `theme_dirs` / `--theme-dir`，再按名切换（见 10.3 节） |

切换只影响当前会话；要永久生效请写入 yaterc。未知主题名会报错并列出可用主题。

## 12. 字体与 Nerd Font 图标

yate 的文件树、标签栏、状态栏使用 **Nerd Font** 私有区码点绘制图标
（目录、按扩展名的文件类型图标、状态栏提示图标等）。终端模拟器决定使用
什么字体，程序无法自行选择，因此 yate 提供完整的字体兜底链：

1. **检测**：Windows 上扫描注册表字体项（HKLM 与 HKCU，含 Nerd 字样且
   文件可加载）；macOS / Linux 通过 `fc-list` 检测。
2. **按需安装**：未检测到 Nerd Font 时安装随包字体。
3. **终端配置**：检测到 Windows Terminal 时自动写入字体设置。

### 12.1 `yate --install-font`（或会话内 `:font`）

两种入口行为一致（`:font` 在编辑器内执行，`--install-font` 执行后退出）：

- **Windows（无需管理员权限，仅当前用户）**
  - 字体文件复制到 `%LOCALAPPDATA%\Microsoft\Windows\Fonts\`；
  - 在 `HKCU\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts` 写入注册表项。
    每个注册表值保存 TTF 的**完整路径**（裸文件名会被 Windows 静默忽略，
    导致图标显示为替代字形——这是旧版安装方式出错的常见原因）；
  - 清理同族的过期注册表项与 `_0.ttf` 之类的重复副本；
  - 广播 `WM_FONTCHANGE` 通知运行中的应用。
- **macOS / Linux**
  - 字体复制到 `~/.local/share/fonts/yate/`，随后运行 `fc-cache -f` 刷新缓存。
- **Windows Terminal 自动配置**
  - 定位
    `%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal*_8wekyb3d8bbwe\LocalState\settings.json`；
  - 把 `profiles.defaults` 的 `font.face` 设为 `JetBrainsMono NFM`（强制）；
  - 对**显式设置了 `font.face` 覆盖**的 profile（如 Cascadia Mono）一并改写，
    避免其覆盖默认值导致图标失效；未显式设置字体的 profile 继承默认值，不动；
  - 写入前在设置文件旁保留 `settings.json.yate-bak` 备份；
  - 幂等：已是目标字体则提示"already uses"。

随包字体为 **JetBrains Mono Nerd Font Mono**（OFL 许可，见
`yate/resources/fonts/OFL.txt`），GDI 家族名为 `JetBrainsMono NFM`。
安装完成后**重启终端**若图标仍未显示。

### 12.2 手动安装

1. 从 [nerdfonts.com](https://www.nerdfonts.com/) 下载任意 Nerd Font
   （或直接使用 yate 随包的 JetBrains Mono Nerd Font Mono TTF）。
2. 安装到系统或用户字体目录（Windows 可右键"为当前用户安装"）。
3. 在终端设置中把字体设为该 Nerd Font，重启终端。

验证：`yate --install-font` 会先打印检测结果
（`Nerd Font already available: ...` 或
`no Nerd Font detected -- run 'yate --install-font' or ':font'`）。

## 13. 集成终端

yate 在底部面板中内嵌了一个真实 Shell（VS Code 风格布局），通过伪终端连接，
因此 vim、htop、python REPL 等全屏 TUI 程序都能直接运行。Windows 后端为
ConPTY（Windows 10 1809+），macOS / Linux 使用 POSIX `pty` 设备。

**打开 / 隐藏**

- `` Ctrl+` `` 切换面板（反引号，Tab 上方的键）。打开时焦点进入终端，隐藏时焦点
  回到编辑器。
- 隐藏**不会**结束 Shell：进程持续运行（与 VS Code 一致），再次切换回到的是
  同一会话。
- `:term`（别名 `:terminal`）显示并聚焦面板；`:termclose` 隐藏面板。

**终端操作**

- 所有按键（包括控制键与粘贴文本，支持 bracketed paste）都原样转发给 Shell；
  唯独 `` Ctrl+` `` 仍由 yate 拦截，用于键盘隐藏面板。
- `Shift+PageUp` / `Shift+PageDown` 或鼠标滚轮可回看历史，回滚缓冲保留最近
  5000 行。
- 面板标题栏显示 Shell 名、程序通过 OSC 转义序列上报的标题，以及状态：
  `starting` / `running` / `exited`。
- Shell 退出后，最后一行显示
  `[shell exited (exit code N); any key restarts]`，按任意键即启动新 Shell。
- 面板随窗口自动调整大小，并向 Shell 发送窗口尺寸变化（SIGWINCH /
  ResizePseudoConsole）。

**默认 Shell 与配置**

未配置时，yate 按以下顺序选择：

- Windows：`PATH` 中有 `pwsh` 则用它；否则用 Windows PowerShell
  （`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`，附加
  `-NoLogo`）；再否则用 `%COMSPEC%` / `cmd.exe`。
- macOS / Linux：`$SHELL`，否则 `bash`，再否则 `/bin/sh`。

在 yaterc 中设置 `shell` 可覆盖（见 10.2）：

```python
shell = "pwsh -NoLogo"
```

值按命令行形式拆分；Windows 上若值本身是已存在的文件路径则原样使用，因此
带空格的引号路径也可用（如 `shell = r"C:\Program Files\PowerShell\7\pwsh.exe"`）。
修改 `shell` 后在**下次启动 Shell** 时生效（等当前 Shell 退出后重新打开面板，
或重启 yate）。

面板高度默认 12 行；`terminal_height` 合法范围为 `3`–`40`，会话中可用
`:set terminal_height=<n>` 立即调整。

## 14. Shell 集成

- **入口**：`F2` 打开 Shell 输入行，或直接在命令行输入 `:!命令`
  （如 `:!git status`、`:!ls -la`）。
- **工作目录**：优先使用打开的工作区根目录；否则为当前文档所在目录；
  再否则为进程启动目录。输出浮层顶部会显示实际 cwd 与所用 Shell。
- **Shell 选择**：Windows 使用 `cmd.exe`，macOS / Linux 使用 `/bin/sh`
  （等价于 `subprocess.run(shell=True)`）。
- **非阻塞**：命令在后台 worker 线程中执行，编辑器始终可响应（命令运行时
  仍可按 F1 查看帮助）；消息行显示 `running: …`，命令结束后自动弹出输出浮层。
- **输出**：命令在可滚动浮层中显示，标题为 `$ 命令`，并标注退出码
  （0 显示绿色对勾，非零显示红色叉）；stdout 与 stderr 一并显示。
  超时 60 秒，返回码 124。
- `Esc` / `q` / `Ctrl+C` 关闭输出浮层。
- 扩展可通过 `api.shell(命令)` 静默执行命令（不弹输出浮层）。

## 15. Python 扩展

扩展是任何暴露 `setup(api)` 的 `.py` 文件（可选 `teardown(api)`）：

```python
def setup(api):
    @api.command("hello", "greet from an extension")
    def hello(args):
        api.message("hello!")

    api.bind_key("<alt-h>", lambda ctx: hello(""), keymap="both")
```

`api` 提供的能力：

| 类别 | API |
|---|---|
| 注册 | `command(name, description)` 装饰器 / `register_command(name, func, description)` 注册 `:` 命令；`bind_key(key_spec, callback, keymap=...)` 绑定按键（`"vsc"` / `"vim"` / `"both"`，`normal` 是 `vsc` 的别名）；`register_action(name, func, description)` 注册命名动作 |
| 访问 | `api.buffer`、`api.doc`、`api.workspace`、`api.keymaps`、`api.app` |
| 服务 | `api.message(text)`、`api.shell(command)`、`api.open_path(path)`、`api.save()` |
| 语言服务器 | `api.lsp.register_server(...)`（见第 16 节）；`api.lsp.statuses()` 返回 `{名字: 状态}` |
| 语法高亮 | `api.highlight.register(spec, *扩展名)` 注册/覆盖自定义语言的声明式高亮（`LangSpec`），注册后可用于 `:set filetype=` |

按键描述使用 yate 的键记法：`<ctrl-x>`、`<alt-x>`、`<shift-x>`、
`<f1>`…`<f12>`、`<enter>`、`<esc>`、`<tab>`、`<backspace>`、
`<up>`、`<down>`、`<left>`、`<right>`、`<home>`、`<end>`、
`<pageup>`、`<pagedown>`、`<delete>`、`<space>`；普通字符直接写
`"a"`、`"1"`、`":"`、`"/"`。修饰键用 `-` 连接，如 `<alt-shift-p>`、`<ctrl-]>`。

加载来源（可组合，按解析后的绝对路径去重）：

1. yaterc 的 `extensions` 选项（用户级先于项目级）；
2. 默认目录 `./extensions/` 与 `~/.yate/extensions/`（启动自动加载）；
3. 命令行 `--ext <文件>` / `--ext-dir <目录>`。

扩展中的异常不会导致编辑器崩溃，错误以 `extension <名字>: ...` 显示在消息栏。
仓库自带示例 `extensions/example_ext.py`（提供 `:upper` / `:lower` /
`:words` / `:sh` 命令与 `Alt+U` 绑定），可作模板；
`extensions/csharp_highlight.py` 则演示了如何用 `api.highlight.register`
为 C#（`.cs`/`.csx`）添加语法高亮。

> 扩展 API 完整参考（命令、动作、按键绑定、buffer/doc/workspace 访问、
> LSP 注册、自定义语法高亮与 `LangSpec` 字段）见
> [`docs/extensions.md`](../../docs/extensions.md)。

## 16. 语言服务器（LSP）

yate 内置了一个精简的
[LSP](https://microsoft.github.io/language-server-protocol/)
客户端（无额外依赖）：通过 stdio 启动语言服务器进程，自行实现 JSON-RPC，
提供：

* **自动补全**——输入标识符时自动弹出（在服务器触发字符之后，如 Python
  的 `.`），也可随时按 `Ctrl+Space` 手动请求（无语言服务器时同样可用）。
  `↑` / `↓` 选择，`Tab` 或 `Enter` 接受，`Esc` 关闭。当当前文件没有可用的
  语言服务器时，补全回退为内建 **buffer 补全**：从所有已打开的缓冲区中
  收集已输入过的单词（当输入前缀包含 `/`、`\` 或 `~` 时还会补全文件系统
  路径），无需任何外部进程。
* **诊断**——错误与警告在编辑区内以下划线标出，装订槽显示 `✖`（错误）/
  `▲`（警告）并给行号着色；光标所在行的诊断会回显在消息栏，状态栏实时
  显示计数。`:diagnostics` 在输出屏中列出当前文件的全部诊断。

文档采用全文同步：打开时、保存时，以及输入停顿短暂去抖后发送整个缓冲区。
服务器在首次打开匹配文件时惰性启动，每个（服务器 × 项目根目录）一个进程。
状态栏在就绪时显示服务器名，启动中显示 `LSP…`，启动失败显示 `LSP ✖`。

### 16.1 Python（内置扩展）

`extensions/python_lsp.py` 会自动加载，为 `.py` / `.pyi` 文件注册 Python
语言服务器。具体实现需自行安装（二者均不随 yate 分发）：

```powershell
pip install python-lsp-server     # 提供 pylsp
# 或
npm install -g pyright            # 提供 pyright-langserver
pip install pyright               # 另一种方式，同样会安装该可执行文件
```

服务器发现顺序：

1. 环境变量 `YATE_PYTHON_LSP`：完整命令行，支持 shell 风格引号，例如
   `set YATE_PYTHON_LSP=C:\tools\pyright-langserver.cmd --stdio`。
   设为 `0`、`off`、`false`、`none` 或 `no` 时彻底禁用 Python 服务器
   （保留注册，但绝不启动进程）。
2. `PATH` 上的 `pyright-langserver`（自动附加 `--stdio`）。
3. `PATH` 上的 `pylsp`。

三者都没有时不会启动任何进程，也不弹错误；直到打开 Python 文件，状态栏
才会显示 `LSP ✖`。

### 16.2 在扩展中注册语言服务器

```python
def setup(api):
    api.lsp.register_server(
        "rust-analyzer",                       # 服务器名（显示在状态栏）
        command="rust-analyzer",               # "" 表示已知缺失，惰性失败
        args=[],
        filetypes=["rs"],                      # 不带点的扩展名
        language_ids={"rs": "rust"},           # textDocument 的 languageId
        root_markers=["Cargo.toml", ".git"],   # 项目根探测文件
        initialization_options=None,           # 原始 initializeOptions
        settings=None,                         # 随 didChangeConfiguration 发送
        env=None,                              # 额外环境变量
    )
```

`api.lsp.statuses()` 返回 `{名字: "ready"|"starting"|"failed"|...}`。
用同名重复注册会替换旧配置，并丢弃其缓存进程与诊断。

> 主流语言（Rust、TypeScript、Go、C/C++、Bash、JSON、HTML/CSS、Lua 等）
> 的安装命令与 `register_server` 食谱，见
> [`docs/lsp.md`](../../docs/lsp.md)。

## 17. 常见问题（FAQ）

**图标显示为方块、菱形或问号？**
终端没有使用 Nerd Font。运行 `yate --install-font`（或会话内 `:font`），
按第 12 节操作后**重启终端**。若用 Windows Terminal 且个别 profile 显式
设置了其他 `font.face`，`--install-font` 会一并改写。

**`Ctrl+Shift+P` 没有打开 yate 的命令面板？**
Windows Terminal 保留了该组合键。yate 的命令面板默认是 `Alt+Shift+P`。

**某个快捷键没反应或被终端"吃掉"了？**
终端模拟器会拦截部分组合键（如 `Ctrl+Shift+P`、部分终端的 `Ctrl+/`）。
可在终端设置中解除占用，或改用等价命令（`:explorer`、`:palette`、
`:set keymap=...` 等）。

**配置文件写错了会怎样？**
不会崩溃。出错的 yaterc 被跳过，错误以 `yaterc: ...` 显示在启动消息栏；
非法选项值保持默认。可用 `yate -u NONE` 验证是否为配置问题。

**退出时提示 unsaved changes？**
yate 会拦截带未保存修改的退出。`:w` 保存后 `:q`，或 `:q!` 放弃修改、
`:wq` 保存并退出。

**支持哪些语言的语法高亮？**
内置高亮引擎按扩展名识别：Python（`py`/`pyi`/`pyw`）、C（`c`/`h`）、
C++（`cpp`/`cc`/`cxx`/`c++`/`hpp`/`hxx`/`h++`/`hh`/`ino`）、Java（`java`）、
Rust（`rs`）、Go（`go`）、JavaScript（`js`/`mjs`/`cjs`/`jsx`）、
TypeScript（`ts`/`tsx`/`mts`/`cts`）、Shell（`sh`/`bash`/`zsh`/`fish`）、
JSON（`json`/`jsonc`）、Markdown（`md`/`markdown`/`mdx`）、TOML（`toml`）、
INI（`ini`/`cfg`/`conf`/`properties`）、YAML（`yaml`/`yml`）。
其他类型按纯文本渲染。

**如何增加新语言（或覆盖某种语言）的语法高亮？**
通过扩展的 `api.highlight.register(spec, *扩展名)` 注册一个声明式的
`LangSpec`（注释标记、关键字、类型、常量等单词集合；字符串、数字、多行
状态由引擎处理），注册后即可自动高亮并用于 `:set filetype=`。仓库自带
`extensions/csharp_highlight.py` 为 C#（`cs`/`csx`）提供高亮，在仓库目录内
启动时自动加载，也可用 `yate --ext csharp_highlight.py` 显式加载；完整字段
说明见 [`docs/extensions.md`](../../docs/extensions.md) 的 4.7 节。

**如何手动指定语法类型（类似 VS Code 的 Change Language Mode / vim 的 `:set filetype`）？**
默认按文件扩展名识别；对无后缀文件、识别错误或临时缓冲区，可以手动覆盖，
且只影响当前缓冲区：

```
:set filetype=python   # 语言名或扩展名均可（python / .py / py 等价）
:set ft=rs             # vim 风格缩写；language/lang 是同义键
:filetype json         # 等价的独立命令（别名 :ft / :language）
:filetype              # 不带参数：显示当前类型与全部可用类型
:set filetype=auto     # 清除覆盖，恢复按路径扩展名自动识别
```

切换后语法高亮、状态栏右侧的类型标识立即更新；若该类型注册了语言服务器
（第 16 节），文档也会重新绑定到对应服务器。命令行中按 `Tab` 可轮询补全
类型名（`:set filetype=py<Tab>`、`:filetype r<Tab>`）。未知类型会被接受
（可能供 LSP 使用），但没有内建高亮，消息栏会给出提示。

**打开某些文件提示 not a text file？**
yate 按扩展名白名单判断可编辑文本（常见的代码/文本后缀，以及
`Dockerfile`、`Makefile`、`README`、`License` 等无后缀名单）；无后缀文件
会嗅探前 2048 字节是否为合法 UTF-8 且不含 NUL 字节。

**文件编码如何处理？**
打开时依次尝试 UTF-8 → 系统首选编码 → cp1252 嗅探；换行统一按 LF 处理，
保存时同样写 LF（Windows 的 CRLF 文件保存后保持一致的 LF）。
状态栏右侧显示当前文件类型与编码。

**中文/emoji 对齐正常吗？**
渲染按终端单元格宽度计算：宽字符（CJK、全角、多数 emoji）占 2 列、
组合字符占 0 列，制表符按 `tab_width` 展开对齐。

**忘了某个键位/命令？**
`F1` 打开当前键位的完整参考并列出全部 `:` 命令；`F8` / `:manual` 打开本手册。

## 18. 键位速查表

vsc 键位（默认）：

| 按键 | 功能 | 按键 | 功能 |
|---|---|---|---|
| `Ctrl+S` | 保存 | `Ctrl+P` | 快速打开文件 |
| `Ctrl+O` | 打开文件 | `Alt+Shift+P` | 命令面板 |
| `Ctrl+N` | 新建 buffer | `Ctrl+1` | 聚焦编辑器 |
| `Ctrl+W` | 关闭标签 | `Ctrl+F` | 查找 |
| `Ctrl+Q` | 退出 | `F3` | 下一个匹配 |
| `Ctrl+Z` / `Ctrl+Y` | 撤销 / 重做 | `F4` | 查找替换 |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | 剪切 / 复制 / 粘贴 | `Ctrl+B` | 显隐文件树 |
| `Ctrl+A` | 全选 | `Ctrl+E` | 聚焦文件树 |
| `Ctrl+D` | 复制行/选区 | `F2` / `F5` | Shell 命令 / 命令行 |
| `Ctrl+Shift+K` | 删除行 | `Ctrl+/` | 切换键位 |
| `Alt+↑` / `Alt+↓` | 移动行 | `Ctrl+PageUp`/`PageDown` | 切换标签 |
| `Ctrl+]` / `Shift+Tab` | 缩进 / 反缩进 | `F1` | 键位帮助 |
| `Ctrl+J` | 合并行 | `F8` | 用户手册 |
| `Ctrl+Space` | 触发自动补全 | 面板 `diagnostics` | 列出 LSP 诊断 |
| `` Ctrl+` `` | 切换集成终端 | `Shift+PageUp/PageDown` | 终端回滚 |

文件树内：`j`/`k` 移动 · `l`/`Enter` 打开/展开 · `h` 折叠 ·
`a` 新建文件 · `A` 新建文件夹 · `r` 重命名 · `d`/`Del` 删除（`y` 确认） ·
`Esc` 回编辑器。

vim 键位：

| 按键 | 功能 | 按键 | 功能 |
|---|---|---|---|
| `h j k l` | 移动 | `i a I A o O` | 进入插入模式 |
| `w b e` | 词移动 | `Esc` | 回 NORMAL |
| `0` / `$` | 行首 / 行尾 | `x` | 删除字符 |
| `gg` / `G` | 文档首 / 尾（可加行号） | `dd` / `yy` | 删行 / 复制行 |
| `Ctrl+D` / `Ctrl+U` | 半页下 / 上 | `d{motion}` / `y{motion}` | 删除 / 复制到 motion |
| `Ctrl+F` / `Ctrl+B` | 翻页下 / 上 | `p` / `P` | 粘贴下 / 上 |
| `v` / `V` | 可视 / 行可视 | `u` / `Ctrl+R` | 撤销 / 重做 |
| `/` / `?` | 向下 / 向上查找 | `J` | 合并行 |
| `n` / `N` | 下 / 上一个匹配 | 数字前缀 | 计数（如 `3j`、`2dd`） |
| `:` | ex 命令行 | `Ctrl+W` / `Ctrl+U`（插入模式） | 删词 / 删到行首 |
| `` Ctrl+` `` | 切换集成终端 | `Shift+PageUp/PageDown` | 终端回滚 |

命令行速查：`:w` `:q` `:q!` `:wq` `:e` `:enew` `:welcome` `:bn` `:bp` `:bd`
`:files` `:palette` `:manual` `:help` `:explorer` `:font` `:term` `:termclose`
`:set keymap=…` `:set theme=…` `:set shell=…` `:set terminal_height=…` `:set filetype=…` `:filetype …` `:vsc` `:vim` `:theme` `:colorscheme` `:!命令`

---

*yate 0.1.0 — MIT License — built with Textual*
