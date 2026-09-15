# `--version` 与 `--diag` 诊断命令实施计划

> 为 yate 增加两个不启动 TUI 的命令行出口：
> - `yate --version`：输出版本基本信息（yate / Python / 操作系统）
> - `yate --diag`：输出完整配置与环境诊断，便于上报问题时一键收集信息
>
> 所有信息均来自仓库现有模块的真实接口，不重复实现探测逻辑。

---

## 1. 现状（基于代码事实）

### 1.1 `--version` 现状

[yate/cli.py](yate/cli.py#L95) 第 95 行：

```python
parser.add_argument("--version", action="version", version=f"yate {__version__}")
```

仅输出一行 `yate 0.1.0`，信息过少。

### 1.2 可复用的现有接口（不新造轮子）

| 诊断信息 | 现有来源 |
|----------|----------|
| yate 版本 | `yate.__version__`；`pyproject.toml` 声明 `requires-python >= 3.10`，依赖 `textual>=8.0` |
| 包根目录 / 冻结模式 | [paths.py](yate/paths.py)：`package_root()`、`bundled_extensions_dir()`，`sys.frozen` / `sys._MEIPASS` |
| Python / OS | 标准库 `sys`、`platform`、`importlib.metadata` |
| 终端类型 | [fonts.py](yate/services/fonts.py#L126)：`detect_terminal()`（识别 windows_terminal / vscode / iterm2 / apple_terminal / conhost） |
| 字体 | [fonts.py](yate/services/fonts.py#L141)：`font_status()` → `has_nerd_font` / `installed_fonts` / `terminal` / `detail` |
| 集成终端 shell | [shells.py](yate/editor_term/shells.py#L21)：`resolve_shell(config.shell)` → 实际 `[executable, ...args]` |
| `:!` 命令 shell | [shell.py](yate/services/shell.py#L53)：`shell_name()` |
| yaterc 位置 | [config.py](yate/config.py#L115)：`user_config_path()`、`find_project_config()`、`default_rc_paths()`；加载结果在 `config.sources` / `config.errors` |
| 全部配置项 | `YateConfig` dataclass：keymap / theme / tab_width / use_spaces / shell / terminal_height / show_hidden / extension_paths / disabled_extensions / theme_dirs / language_servers / sources / errors |
| 主题 | `editor_view.theme.available()`（内置 + rc/theme-dir 注册） |
| tree-sitter 后端 | [ts_backend/__init__.py](yate/editor_syntax/ts_backend/__init__.py)：`ts_available()`；regex 后端 `available_filetypes()` |
| 扩展 | [extensions.py](yate/services/extensions.py#L300)：`ExtensionLoader.loaded`（`LoadedExtension.name/path/error`） |
| LSP 服务器 | [manager.py](yate/editor_lsp/manager.py)：`config_names()`、`states()`；`ServerConfig`（name/command/args/filetypes/language_ids/root_markers/env） |
| 崩溃报告 | `~/.yate/data/crash-*.err`（上一阶段 crash 功能落盘目录） |

### 1.3 关键约束

- 扩展只在 `YateApp.on_mount()` 里通过 `_load_extensions()` / `_register_configured_servers()` 加载；构造 `YateApp`（测试里已有无头用法）不会加载扩展，`--diag` 需显式触发。
- `LspManager._configs` 是私有属性，pyright strict 下不能跨模块读取，需补一个公开只读访问器。
- `ServerConfig.env` 可能含 token/密钥，输出时**值必须脱敏**（只显示键名）。

---

## 2. 方案设计

### 2.1 `--version` 输出（简洁，不加载任何配置）

```
yate 0.1.0
Python 3.11.5 (CPython)
Windows-11-10.0.22631-SP0
```

- 改为 `store_true`，在 `parse_args()` 之后**最早**处理（早于 `--install-font`、配置加载），打印后 `return 0`
- 输出到 stdout，退出码 0，行为与惯例一致

### 2.2 `--diag` 输出（纯文本分节，适合粘贴到 issue）

```
yate 0.1.0 — diagnostics
========================================

[system]
  platform     : Windows-11-10.0.22631-SP0
  machine      : AMD64
  python       : 3.11.5 (CPython)
  executable   : C:\...\python.exe
  prefix       : C:\...
  frozen       : no

[terminal]
  detected     : windows_terminal
  isatty       : yes (stdout)
  TERM                = xterm-256color
  COLORTERM           = truecolor
  TERM_PROGRAM        = Windows Terminal
  TERM_PROGRAM_VERSION= 1.21
  WT_SESSION          = <set>

[shell]
  integrated   : C:\Program Files\PowerShell\7\pwsh.exe -NoLogo
  :! default   : cmd.exe

[paths]
  package root        : d:\Programming\yate\yate
  bundled extensions  : d:\Programming\yate\yate\extensions
  user dir (~/.yate)  : C:\Users\xxx\.yate
  crash data dir      : C:\Users\xxx\.yate\data (2 个 .err 文件)

[yaterc]
  user rc      : C:\Users\xxx\.yate\yaterc (存在)
  project rc   : 未找到
  实际加载顺序 :
    - C:\Users\xxx\.yate\yaterc
  加载错误     : 无

[config]
  keymap           = vsc
  theme            = mocha
  tab_width        = 4
  use_spaces       = True
  shell            = (默认)
  terminal_height  = 12
  show_hidden      = False
  disabled_extensions = []
  extension_paths  = []
  theme_dirs       = []

[themes]
  可用主题 : frappe, latte, macchiato, mocha, my-custom

[syntax]
  tree-sitter : 可用 (tree-sitter 0.25.x; grammars: python, bash)
  regex 语言  : bash, c, cpp, csharp, css, go, ...

[extensions]
  候选目录 :
    bundled : d:\...\yate\extensions (2 个脚本)
    user    : C:\Users\xxx\.yate\extensions (不存在)
    project : d:\Programming\yate\extensions (不存在)
  已加载 :
    [ok]    python_lsp        d:\...\extensions\python_lsp.py
    [ok]    csharp_highlight  d:\...\extensions\csharp_highlight.py
    [error] broken_ext        d:\...\broken_ext.py
            ImportError: No module named 'xxx'

[lsp]
  python-lsp-server
    command      : pylsp
    args         : []
    filetypes    : py
    language_ids : {py: python}
    root markers : .git, pyproject.toml, setup.py
    state        : configured
    env keys     : (无)

[fonts]
  nerd font : 是
  已安装    : JetBrainsMono NFM (TrueType)
  terminal  : windows_terminal

[packages]
  textual                : 8.0.0
  tree-sitter            : 0.25.12
  tree-sitter-python     : 0.23.6
  tree-sitter-bash       : 0.23.9
```

设计要点：

- **纯文本、固定节顺序**：重定向到文件 / 粘贴 issue 不丢格式，不依赖 Rich
- **每节独立 best-effort**：单节探测异常不影响其他节输出（异常时打印 `<探测失败: ...>`）
- **零副作用**：不启动 LSP 进程（服务器是懒启动）、不改终端、不装字体
- **脱敏**：LSP `env` 只列键名；不回显 yaterc 源码（它是可执行 Python），只列解析后的配置值

---

## 3. 实施步骤

### 步骤 1：新增 `yate/diagnostics.py`

精确命名（非 *_ops/helpers），职责单一：收集并格式化诊断信息。

```python
"""One-shot environment/configuration diagnostics for `yate --diag`."""

def version_lines() -> str:
    """yate/Python/platform 基本信息（--version 使用）。"""

def format_report(app: "YateApp") -> str:
    """收集全部诊断节并返回纯文本报告。"""
```

内部按节组织私有函数：`_section_system / _terminal / _shell / _paths /
_yaterc / _config / _themes / _syntax / _extensions / _lsp / _fonts /
_packages`，每个返回 `list[str]`，由 `format_report` 统一拼装；
每个 section builder 外层包 `try/except`，失败降级为一行提示。

补充细节：

- 包版本：`importlib.metadata.version("textual")`，`PackageNotFoundError` 时显示 `未安装`
- tree-sitter：`ts_available()` 为 True 时再查 `tree-sitter / tree-sitter-python / tree-sitter-bash` 版本
- crash data 目录：存在时统计 `crash-*.err` 文件数量并列最近 5 个文件名
- 扩展节：候选目录来自与 `app._load_extensions()` 相同的路径集合
  （`config.extension_paths`、`bundled_extensions_dir()`、`ext_dirs`、
  `cwd/extensions`、`~/.yate/extensions`、`ext_files`），加载结果读
  `app.extension_loader.loaded`（含 `error` 字段）
- LSP 节：通过步骤 3 新增的 `app.lsp.configs()` 读取配置，
  `states()` 读状态；`env` 仅输出 `sorted(env.keys())`

### 步骤 2：`yate/app.py` —— 抽出公开的启动加载方法

`on_mount()` 中的两行：

```python
self._load_extensions()
self._register_configured_servers()
```

提取为公开方法（消除 `--diag` 路径调用私有方法的问题）：

```python
def load_startup_services(self) -> None:
    """加载扩展并注册 yaterc 声明的 LSP（无头安全：不依赖任何 widget）。"""
    self._load_extensions()
    self._register_configured_servers()
```

`on_mount()` 改为调用该方法；`--diag` 同样调用它。两者逻辑零差异，
保证"诊断所见 = 实际启动所加载"。

### 步骤 3：`yate/editor_lsp/manager.py` —— 增加只读访问器

```python
def configs(self) -> list[ServerConfig]:
    """已注册的服务器配置（只读视图，供诊断/状态栏使用）。"""
    return list(self._configs)
```

### 步骤 4：`yate/cli.py` —— 参数与分支

1. `--version` 由 argparse action 改为 `store_true`
2. 新增 `--diag`（`store_true`，help 中英文沿用现有风格）
3. `main()` 流程调整：

```python
crash.install()
args = parse_args()

if args.version:
    print(diagnostics.version_lines())
    return 0

if args.install_font:
    ...  # 现有逻辑不动

# 现有配置/主题加载
...

if args.diag:
    app = YateApp(...)          # 与正常启动同一构造路径
    app.load_startup_services() # 扩展/LSP 注册（无头安全）
    print(diagnostics.format_report(app))
    return 0

app = YateApp(...)
app.run()
```

注意：当前 cli 里 app 构造在最后；`--diag` 分支需要在其之前构造一次，
正常分支保持单次构造（用 `if args.diag: ... return` 提前返回，不重复构造）。

### 步骤 5：测试

扩展现有 [tests/test_cli.py](tests/test_cli.py)（沿用 `_FakeApp` + patch 风格）：

- `--version`：输出含 `yate 0.1.0`、`Python`、平台串；退出码 0；
  断言未构造 `YateApp`、未读配置
- `--diag`：patch `yate.app.YateApp` 与
  `yate.diagnostics.format_report`，断言打印报告、退出码 0、`run()` 未调用
- `-u NONE --diag`：报告中 yaterc 节显示未加载任何 rc

新增 `tests/test_diagnostics.py`（无头真实 `YateApp`，参照
test_cli.py 中直接构造 `YateApp(theme_name=...)` 的做法）：

- `version_lines()` 含三个基本信息
- `format_report()` 包含全部 12 个节标题
- 用临时 yaterc（`tab_width = 2` 等）构造 app，报告中出现解析后的值
- 临时扩展脚本（写一个无 `setup` 的坏文件，经 `--ext` 等价路径传入），
  调 `load_startup_services()` 后报告出现 `[error]` 与错误原因
- LSP env 脱敏：注册一个带 `env={"API_TOKEN": "secret123"}` 的服务器，
  断言输出含 `API_TOKEN` 且**不含** `secret123`
- 某节内部抛异常时报告仍完整生成（best-effort 降级）

---

## 4. 验证方案

```powershell
# 单元测试
python -m pytest tests/test_cli.py tests/test_diagnostics.py -v
python -m pytest tests/ -v   # 全量回归（app/manager 有小改动）

# 手动验证
yate --version
yate --diag
yate --diag -u NONE
yate --diag > diag.txt       # 重定向到文件，便于随 issue 上传
```

预期：

- `--version` 三行基本信息，退出码 0
- `--diag` 12 个节齐全；无 yaterc 时显示"未找到/未加载"；
  扩展错误可见；LSP env 值不可见；不进入 TUI

---

## 5. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `yate/diagnostics.py` | 新增 | 版本信息与 `--diag` 报告收集/格式化 |
| `yate/cli.py` | 修改 | `--version` 改造、新增 `--diag` 及分支 |
| `yate/app.py` | 修改 | 抽出 `load_startup_services()` 公开方法 |
| `yate/editor_lsp/manager.py` | 修改 | 新增 `configs()` 只读访问器 |
| `tests/test_cli.py` | 修改 | `--version` / `--diag` CLI 层用例 |
| `tests/test_diagnostics.py` | 新增 | 报告内容、脱敏、best-effort 用例 |
| `.trae/documents/diag_command_plan.md` | 新增 | 本文档 |

---

## 6. 后续可扩展方向

- `--diag --check`：对常见问题（字体缺失、LSP 命令不在 PATH、终端不支持 truecolor）
  给出 `[!]` 警告与修复命令（如 `yate --install-font`）
- `yate :diag` 应用内命令：在 OutputScreen 中展示同一报告（复用 `format_report`）
- 报告脱敏清单可配置化（默认覆盖 token/key/secret/password 命名的 env 键）
