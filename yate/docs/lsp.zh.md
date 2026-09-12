# yate 语言服务器（LSP）配置

[English](lsp.en.md) · **中文**

yate 内置一个精简的 [LSP](https://microsoft.github.io/language-server-protocol/)
客户端（无额外依赖）：通过 stdio 启动语言服务器进程，自行实现 JSON-RPC，
提供**自动补全**与**诊断**。语言服务器本身需要用户自行安装；yate 不随包
分发任何语言服务器。

客户端能力：

- **自动补全**：输入标识符时自动弹出（在服务器声明的触发字符之后，如
  Python 的 `.`），也可随时 `Ctrl+Space` 手动请求。`↑`/`↓` 选择，`Tab`
  或 `Enter` 接受，`Esc` 关闭。
- **诊断**：错误/警告在编辑区以下划线标出，装订槽显示 `✖`/`▲` 并给行号
  着色；光标所在行的诊断回显在消息栏，状态栏显示计数。`:diagnostics`
  列出当前文件全部诊断。
- **buffer 补全回退**：当前文件没有可用语言服务器时，补全回退为从所有已
  打开缓冲区收集单词（前缀含 `/` 或 `~` 时还会补全文件路径）。

文档采用全文同步：打开时、保存时、输入停顿去抖（0.25s）后发送整个缓冲区。
服务器在首次打开匹配文件时**惰性启动**，每个（服务器 × 项目根目录）一个
进程。状态栏显示服务器状态：就绪显示服务器名，启动中 `LSP…`，失败 `LSP ✖`。

本文件是主流语言服务器的配置食谱；手册第 16 节是简介。

---

## 1. 如何注册语言服务器

语言服务器通过**扩展**注册。在任意扩展的 `setup(api)` 中调用：

```python
api.lsp.register_server(
    name="rust-analyzer",                       # 状态栏显示名
    command="rust-analyzer",                    # 可执行文件；"" 表示已知缺失，惰性失败
    args=[],                                    # 命令行参数
    filetypes=["rs"],                           # 不带点的扩展名列表
    language_ids={"rs": "rust"},                # filetype -> LSP languageId（缺省用 filetype 本身）
    root_markers=["Cargo.toml", ".git"],        # 项目根探测文件
    initialization_options=None,                # 原始 initializeOptions
    settings=None,                              # 随 didChangeConfiguration 发送
    env=None,                                   # 额外环境变量
)
```

把注册代码放入 `~/.yate/extensions/lsp.py`（或 yaterc `extensions` 指向的
任意 `.py`），下次启动即生效。用同名重复注册会替换旧配置并丢弃其缓存
进程与诊断。

可用 `api.lsp.statuses()` 查看 `{名字: 状态}`，`api.lsp.has_state(name, "ready")`
判断某服务器是否就绪。

**项目根目录**：优先使用打开的工作区根目录；否则从文档目录向上查找
`root_markers` 中第一个存在的文件；找不到则用文档所在目录。

### 1.1 更简单的方式：写在 yaterc 里（自动激活）

不想写扩展时，可直接在 yaterc（`~/.yate/yaterc` 或项目根的 `yaterc`）
用 `language_servers` 选项声明。它是一个字典列表，字段与上面
`register_server` 的参数同名；配置后**无需任何手动命令**，打开扩展名
匹配的文件时自动启动服务器：

```python
language_servers = [
    {
        "name": "rust-analyzer",
        "command": "rust-analyzer",
        "filetypes": ["rs"],                 # 不带点；".rs" 也接受
        "language_ids": {"rs": "rust"},
        "root_markers": ["Cargo.toml", ".git"],
        # "args": [], "env": {...},
        # "initialization_options": {...}, "settings": {...},
    },
]
```

- `name` / `command` / `filetypes` 必填，`command` 必须非空；非法条目
  跳过并在启动消息栏报错，其余条目照常注册。
- 选项在扩展加载**之后**注册，同名条目会替换扩展注册——包括内置 Python
  服务器（用 `"name": "python"` 即可自定义其命令）。
- 仅配置不会启动进程：未命名 buffer 或不匹配的文件完全不受影响；后加载
  的 yaterc 整体替换该列表。

下文各语言食谱中的 `api.lsp.register_server(...)` 调用都可以等价改写为
这样一个字典。

---

## 2. Python（内置）

`yate/extensions/python_lsp.py` 随 yate 分发并在启动时自动加载（无论
工作目录在哪），为 `.py` / `.pyi` 注册 Python 语言服务器。不想加载它时，
在 yaterc 中设置 `disabled_extensions = ["python_lsp"]`（此时也可用
yaterc 的 `language_servers` 自行声明 `"name": "python"`）。服务器需
自行安装：

```powershell
pip install python-lsp-server     # 提供 pylsp
# 或
npm install -g pyright            # 提供 pyright-langserver
pip install pyright               # 另一种方式
```

服务器发现顺序：

1. 环境变量 `YATE_PYTHON_LSP`：完整命令行，支持 shell 风格引号，例如
   `set YATE_PYTHON_LSP=C:\tools\pyright-langserver.cmd --stdio`。
   设为 `0`/`off`/`false`/`none`/`no` 可彻底禁用（保留注册但不启动）。
2. `PATH` 上的 `pyright-langserver`（自动附加 `--stdio`）。
3. `PATH` 上的 `pylsp`。

三者都没有时不会启动进程也不弹错；打开 Python 文件时状态栏显示 `LSP ✖`。

---

## 3. Rust

安装：

```bash
rustup component add rust-analyzer
# 或从 https://github.com/rust-lang/rust-analyzer/releases 下载
```

注册：

```python
api.lsp.register_server(
    name="rust-analyzer",
    command="rust-analyzer",
    filetypes=["rs"],
    language_ids={"rs": "rust"},
    root_markers=["Cargo.toml", ".git"],
)
```

---

## 4. TypeScript / JavaScript

安装：

```bash
npm install -g typescript typescript-language-server
```

注册：

```python
api.lsp.register_server(
    name="typescript",
    command="typescript-language-server",
    args=["--stdio"],
    filetypes=["ts", "tsx", "js", "jsx", "mjs", "cjs"],
    language_ids={
        "ts": "typescript",
        "tsx": "typescriptreact",
        "js": "javascript",
        "jsx": "javascriptreact",
        "mjs": "javascript",
        "cjs": "javascript",
    },
    root_markers=["package.json", "tsconfig.json", ".git"],
)
```

---

## 5. Go

安装：

```bash
go install golang.org/x/tools/gopls@latest
```

注册：

```python
api.lsp.register_server(
    name="gopls",
    command="gopls",
    args=["serve"],
    filetypes=["go"],
    language_ids={"go": "go"},
    root_markers=["go.mod", ".git"],
)
```

---

## 6. C / C++

安装：

```bash
# 系统包管理器或从 https://github.com/clangd/clangd/releases 下载
# Debian/Ubuntu: sudo apt install clangd
# macOS: brew install llvm
```

注册：

```python
api.lsp.register_server(
    name="clangd",
    command="clangd",
    args=["--background-index"],
    filetypes=["c", "cc", "cpp", "cxx", "h", "hh", "hpp", "hxx"],
    language_ids={
        "c": "c", "cc": "c",
        "cpp": "cpp", "cxx": "cpp",
        "h": "c", "hh": "c",
        "hpp": "cpp", "hxx": "cpp",
    },
    root_markers=["compile_commands.json", "compile_flags.txt", ".git"],
)
```

---

## 7. Bash / Shell

安装：

```bash
npm install -g bash-language-server
```

注册：

```python
api.lsp.register_server(
    name="bash-language-server",
    command="bash-language-server",
    args=["start"],
    filetypes=["sh", "bash", "zsh"],
    language_ids={"sh": "shellscript", "bash": "shellscript", "zsh": "shellscript"},
    root_markers=[".git"],
)
```

---

## 8. JSON

安装：

```bash
npm install -g vscode-langservers-extracted
# 提供 vscode-json-languageserver（以及 html/css/eslint）
```

注册：

```python
api.lsp.register_server(
    name="json",
    command="vscode-json-language-server",
    args=["--stdio"],
    filetypes=["json", "jsonc"],
    language_ids={"json": "json", "jsonc": "json"},
    root_markers=["package.json", ".git"],
)
```

---

## 9. HTML / CSS

`vscode-langservers-extracted` 同时提供 HTML 与 CSS 服务器：

```python
api.lsp.register_server(
    name="html",
    command="vscode-html-language-server",
    args=["--stdio"],
    filetypes=["html", "htm"],
    language_ids={"html": "html", "htm": "html"},
    root_markers=["package.json", ".git"],
)

api.lsp.register_server(
    name="css",
    command="vscode-css-language-server",
    args=["--stdio"],
    filetypes=["css", "scss", "less"],
    language_ids={"css": "css", "scss": "scss", "less": "less"},
    root_markers=["package.json", ".git"],
)
```

---

## 10. Lua

安装：

```bash
# 从 https://github.com/LuaLS/lua-language-server/releases 下载
# 或：brew install lua-language-server
```

注册：

```python
api.lsp.register_server(
    name="lua-language-server",
    command="lua-language-server",
    filetypes=["lua"],
    language_ids={"lua": "lua"},
    root_markers=[".luarc.json", ".git"],
)
```

---

## 11. 一键脚本示例

把以下内容保存为 `~/.yate/extensions/lsp.py`，按需注释掉不需要的语言：

```python
import shutil


def _has(cmd):
    return shutil.which(cmd) is not None


def setup(api):
    if _has("rust-analyzer"):
        api.lsp.register_server("rust-analyzer", command="rust-analyzer",
                                filetypes=["rs"], language_ids={"rs": "rust"},
                                root_markers=["Cargo.toml", ".git"])

    if _has("typescript-language-server"):
        api.lsp.register_server(
            "typescript", command="typescript-language-server",
            args=["--stdio"],
            filetypes=["ts", "tsx", "js", "jsx"],
            language_ids={"ts": "typescript", "tsx": "typescriptreact",
                          "js": "javascript", "jsx": "javascriptreact"},
            root_markers=["package.json", "tsconfig.json", ".git"],
        )

    if _has("gopls"):
        api.lsp.register_server("gopls", command="gopls", args=["serve"],
                                filetypes=["go"], language_ids={"go": "go"},
                                root_markers=["go.mod", ".git"])

    if _has("clangd"):
        api.lsp.register_server("clangd", command="clangd",
                                args=["--background-index"],
                                filetypes=["c", "cc", "cpp", "h", "hpp"],
                                language_ids={"c": "c", "cc": "c",
                                              "cpp": "cpp", "h": "c", "hpp": "cpp"},
                                root_markers=["compile_commands.json", ".git"])

    if _has("bash-language-server"):
        api.lsp.register_server("bash-language-server",
                                command="bash-language-server", args=["start"],
                                filetypes=["sh", "bash"],
                                language_ids={"sh": "shellscript",
                                              "bash": "shellscript"},
                                root_markers=[".git"])
```

用 `shutil.which` 探测可执行文件，找不到就不注册，避免状态栏出现
`LSP ✖`。如果希望"已知缺失但仍注册"（让状态栏明确提示），把 `command`
设为 `""` 即可。

> 不想写扩展脚本的话，上述服务器也可以直接用 yaterc 的
> `language_servers` 列表声明（见 1.1 节）：把每个
> `api.lsp.register_server(...)` 调用改写成一个同名字典即可，打开匹配
> 文件时自动激活。

---

## 12. 排查

- **状态栏显示 `LSP ✖`**：该文件类型注册了服务器但启动失败。常见原因：
  可执行文件不在 `PATH`、命令参数错误、初始化超时（默认 20 秒）。
- **无任何 LSP 字样**：该文件类型没有注册任何服务器，补全回退为 buffer
  补全。按上述食谱注册即可。
- **补全不弹出**：确认服务器已 `ready`；部分服务器需要在项目根目录有
  配置文件（如 `tsconfig.json`、`pyproject.toml`）才提供完整能力。
- **想禁用某语言**：在注册前用 `shutil.which` 判断，或直接不注册该语言。
