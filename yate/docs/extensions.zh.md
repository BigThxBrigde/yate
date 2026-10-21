# yate 扩展（Extensions）

[English](extensions.en.md) · **中文**

yate 的扩展是任意一个暴露 `setup(api)` 函数的 `.py` 文件（可选提供
`teardown(api)`）。`setup` 在应用启动时被调用，通过传入的 `api` 对象
可以注册命令、动作、按键绑定、语言服务器，以及访问当前缓冲区、文档、
工作区等运行时对象。Lua 同样受支持：`.lua` 脚本可以是模块表、显式
`setup(api)` 或顶层脚本（见第 6 节），前提是安装了可选的 `lupa` 桥
（`pip install yate[lua]`）。

本文件是扩展编写的完整参考；手册第 10.4 / 15 节是简介。

---

## 1. 扩展长什么样

最小扩展：

```python
# ~/.yate/extensions/hello.py
def setup(api):
    @api.command("hello", "greet from my extension")
    def hello(args):
        api.message(f"hello, {args or 'world'}!")

    api.bind_key("<alt-h>", lambda ctx: hello(""), keymap="both")
```

加载后即可用 `:hello you` 或 `Alt+H` 触发。

包内 `yate/extensions/example_ext.py.example` 提供了 `:upper`、`:lower`、
`:words`、`:sh` 命令和 `Alt+U` 绑定，去掉 `.example` 后缀复制到扩展目录
即可作为模板使用。

---

## 2. 加载方式与优先级

扩展可以从以下来源加载，**按解析后的绝对路径去重**（同一个脚本被多个
来源命中也只会执行一次）：

1. yaterc 中的 `extensions` 选项（用户级先于项目级，**累加**而非覆盖）；
2. **随包扩展** `yate/extensions/`（目前为 `python_lsp`——Python 语言服务器，
   外加游戏包：`games`（`:game` 派发器）与 `snake` / `pacman` /
   `nethack` / `tetris`；它们共同 `require` 的共享模块
   `lib/game_engine.lua` 放在 `yate/extensions/lib/`，装载器不会把它当扩展；
   无论当前工作目录在哪都会自动
   加载；可用 yaterc 的 `disabled_extensions`
   按文件名主干禁用，见下文）。目录内还提供模板（`*.py.example`，不会被
   自动加载）：`example_ext.py.example`、tree-sitter grammar 模板
   `yatesh_syntax.py.example`，以及语法高亮模板 `batch_syntax.py.example`、
   `ini_syntax.py.example`、`fsharp_syntax.py.example`、
   `git_syntax.py.example`、`diff_syntax.py.example`，以及 Lua 模板
   `lua.example`；
3. 默认目录：工作目录下的 `./extensions/` 与 `~/.yate/extensions/`
   （启动时自动加载其中所有 `*.py` 与 `*.lua`，下划线开头的文件跳过）。
   项目目录
   只在**受信任工作区**中自动加载——见下文「工作区信任（:trust）」；
   用户目录始终加载；
4. 命令行：`--ext <文件>` 加载单个文件，`--ext-dir <目录>` 加载目录下
   所有 `*.py`/`*.lua`（均可重复指定）。

加载顺序基本即上面的编号顺序，只有 `--ext-dir` 例外：这些目录**先于**两个
默认目录加载，因此实际顺序是第 1 步 → 第 2 步 → `--ext-dir` → 第 3 步
→ `--ext <文件>`。同一路径只执行一次，因此把修改版脚本放进
`~/.yate/extensions/`（第 3 步）可以覆盖随包同名扩展的注册。下划线开头的
文件与 `.example` 后缀的模板不会被加载。

### 工作区信任（:trust）

打开一个仓库绝不应当执行该仓库自带的代码，因此项目目录 `./extensions/`
只在用户**显式信任**的工作区中自动加载。启动时若在工作区中发现该目录但
尚未信任，yate 会跳过它并在消息栏提示
`extensions: skipped untrusted <路径> (run :trust to load them)`。运行

```
:trust
```

即可信任当前工作区并立即加载其 `./extensions/`。路径中含符号链接成员的
工作区会被**拒绝**：信任库保存的是解析后的根路径，因此符号链接指向的
cwd 无法按原样信任；yate 会提示
`refused to trust <路径>: it contains a symlink component`，此时请改为
信任解析后的目录。受信任的工作区逐行记录
在 `~/.yate/trusted_workspaces`（每行一个绝对路径）；删除对应行即可取消
信任。rc 声明路径、`--ext` / `--ext-dir` 与 `~/.yate/extensions/` 属于
用户主动行为，始终加载。

### 禁用随包默认扩展（disabled_extensions）

在 yaterc 中按**文件名主干**（不含脚本后缀）列出要跳过的随包扩展：

```python
disabled_extensions = ["python_lsp"]
```

- 接受字符串或字符串列表，多个 rc 文件之间**累加**并去重；
- 只影响随包默认扩展——rc 路径、受信任工作区中的 `./extensions/`、
  `~/.yate/extensions/`、命令行指定的脚本一律照常加载；
- 非法值（非字符串列表、空字符串）作为配置错误显示在启动消息栏。

yaterc 中声明：

```python
extensions = "~/.yate/myext.py"          # 单个文件
extensions = [
    "~/.yate/extensions",                # 目录：加载其中所有 .py
    "./tools/yate_exts",                 # 相对路径：相对本 yaterc 所在目录
    "/opt/yate/extra.py",                # 绝对路径
]
```

`~` 自动展开；相对路径相对于**声明它的 yaterc 文件所在目录**解析，因此
项目级配置可以随项目移动。路径不存在或类型错误作为配置错误显示在消息栏，
不影响其余选项。

---

## 3. `setup(api)` 与 `teardown(api)`

| 钩子 | 时机 |
|---|---|
| `setup(api)` | 扩展加载时调用一次。扩展**必须**提供此函数，否则会报 `has no setup(api) function`。 |
| `teardown(api)` | 可选。应用退出时调用，用于释放扩展自己持有的资源（如启动的子进程、定时器）。 |

两个函数都接收同一个 `ExtensionAPI` 实例。扩展中的任何异常都不会导致
编辑器崩溃：错误以 `extension <名字>: <异常>` 的形式显示在消息栏。

如果 `setup` 执行到一半抛出异常，抛出前注册的一切——动作、命令、按键
绑定、语言服务器、事件订阅、状态栏段、屏保精灵——都会被**自动回滚**
（回滚 scope）：失败的 setup 不会留下半注册的能力，其 `teardown` 也
不会被执行。

---

## 4. API 参考

### 4.1 注册 `:` 命令

```python
@api.command("name", "description shown in :help / palette")
def cmd(args: str) -> None:
    ...

# 或者命令式
api.register_command("name", func, "description")
```

命令函数接收命令名之后的原始参数字符串（可能为空串）。例如执行
`:upper foo bar`，`args` 为 `"foo bar"`。

命令会出现在命令面板（`Alt+Shift+P`）和 `:help` 列表中，并支持 `Tab`
补全命令名。

### 4.2 注册命名动作（Action）

```python
api.register_action("my_action", func, "description")
```

动作可通过 `api.bind_key` 或键位表绑定，也可以在命令面板中按动作名
检索执行。`func` 的签名与键位回调一致（接收 `ActionContext` 或无参）。

### 4.3 绑定按键

```python
api.bind_key(key_spec, callback, *, keymap="vsc",
             description="extension binding", category="extension")
```

- `keymap`：`"vsc"`、`"vim"` 或 `"both"`（`"normal"` 是 `"vsc"` 的
  别名）。
- 可作装饰器使用：省略 `callback` 时返回装饰器。
- `callback` 接收一个 `ActionContext`（可忽略参数）。

**键记法**（与键位表一致）：

- 控制键：`<ctrl-x>`、`<alt-x>`、`<shift-x>`、`<alt-shift-p>`
- 特殊键：`<f1>`…`<f12>`、`<enter>`、`<esc>`、`<tab>`、`<backspace>`、
  `<up>`、`<down>`、`<left>`、`<right>`、`<home>`、`<end>`、
  `<pageup>`、`<pagedown>`、`<delete>`、`<space>`
- 普通字符直接写：`"a"`、`"1"`、`":"`、`"/"`

示例：

```python
@api.bind_key("<ctrl-shift-u>", keymap="both", description="uppercase")
def _upper(ctx):
    api.buffer.insert_text((api.buffer.selected_text() or "").upper())
```

### 4.4 访问运行时对象

| 属性 | 类型 | 说明 |
|---|---|---|
| `api.buffer` | `TextBuffer` | 当前活动缓冲区 |
| `api.doc` | `Document` | 当前活动文档（含路径、保存等） |
| `api.workspace` | `Workspace` | 文件树工作区 |
| `api.keymaps` | `KeymapSet` | 所有已加载键位（`vsc`/`vim`）；用 `api.keymaps.get(名字)` 取单个 |
| `api.app` | `ExtensionContext` | 扩展可驱动的具体服务（高级用法） |

**`api.app`（`ExtensionContext`）字段**（高级用法；优先使用上面的窄接口）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `session` | `EditorSession` | 打开的文档会话（`session.doc` / `session.buffer`） |
| `workspace` | `Workspace` | 文件树工作区 |
| `lsp` | `LspManager` | 语言服务器管理器（窄接口见 `api.lsp`） |
| `keymaps` | `KeymapSet` | 所有已加载键位（`vsc`/`vim`） |
| `actions` | `ActionRegistry` | 命名动作注册表 |
| `commands` | `CommandRegistry` | `:` 命令注册表 |
| `message(text)` | 可调用 | 在消息栏显示提示 |
| `run_shell(command, show_output)` | 可调用 | 同步执行 shell 命令，返回 `ShellResult` 或 `None` |
| `open_path(path)` | 可调用 | 在编辑器中打开文件/目录 |
| `save()` | 可调用 | 保存当前文档 |

**`api.buffer`（TextBuffer）常用方法**：

| 方法 | 作用 |
|---|---|
| `row` / `col` | 光标行列（0-based） |
| `lines` | 行列表（可直接赋值改单行，改后需 `mark_content_changed()`） |
| `get_text()` / `set_text(t)` | 获取/设置全文 |
| `insert_text(text)` | 在光标处插入文本 |
| `replace_range(start, end, text)` | 替换范围 |
| `has_selection()` / `selected_text()` | 选区判断与取文本 |
| `select_all()` / `clear_selection()` | 选区操作 |
| `undo()` / `redo()` | 撤销重做 |
| `move_left/right/up/down(select=False, word=False)` | 光标移动 |
| `move_line_start/end()` / `move_doc_start/end()` | 跳转 |
| `mark_content_changed()` | 直接改 `lines` 后调用，刷新高亮/缓存 |

缓冲区只读时（`buf.read_only` 为 `True`，由 `--readonly` 或 `:set readonly=true`
设置），所有变更方法都会抛出 `yate.editor_core.BufferReadOnlyError`；扩展若需
容忍只读文档，请用 `try`/`except` 包裹编辑操作。直接对 `lines` 赋值不经过护栏
（不会抛异常），但改动依然计入编辑——请先检查 `buf.read_only`。`doc.save()`
同样遵守该标志：只读缓冲区上会抛出 `BufferReadOnlyError`，确需持久化请先解除
标志（`buf.read_only = False`）——交互式 `:saveas` 命令正是这样做的。

**`api.doc`（Document）常用属性/方法**：

| 成员 | 说明 |
|---|---|
| `doc.path` | `Path` 或 `None` |
| `doc.filetype` | 不带点的扩展名（如 `py`、`rs`） |
| `doc.name` / `doc.display_path` | 显示用名称/路径 |
| `doc.modified` | 是否有未保存修改 |
| `doc.save(path=None)` | 保存（可另存为） |

### 4.5 服务方法

| 方法 | 作用 |
|---|---|
| `api.message(text)` | 在消息栏显示一条提示 |
| `api.shell(command)` | 静默执行 shell 命令，返回 `ShellResult`（含 `output`、`returncode`），不弹输出浮层 |
| `api.open_path(path)` | 在新标签打开文件 |
| `api.save()` | 保存当前文档 |

### 4.6 语言服务器（LSP）

详见 [lsp.zh.md](./lsp.zh.md)（[English](./lsp.en.md)）。核心 API：

```python
api.lsp.register_server(
    name="rust-analyzer",
    command="rust-analyzer",            # "" 表示已知缺失，惰性失败
    args=[],
    filetypes=["rs"],                   # 不带点的扩展名
    language_ids={"rs": "rust"},        # textDocument 的 languageId
    root_markers=["Cargo.toml", ".git"],
    initialization_options=None,
    settings=None,
    env=None,
)
api.lsp.statuses()        # {"rust-analyzer": "ready" | "starting" | "failed" | ...}
api.lsp.has_state(name, "ready")
```

用同名重复注册会替换旧配置，并丢弃其缓存进程与诊断。

### 4.7 语法高亮（自定义语言）

通过 `api.highlight` 可以注册新语言的语法高亮，或**覆盖内置语言**（同名扩展名
再次注册即替换）。高亮引擎是声明式的：只需提供注释标记与若干单词集合，
字符串、数字、注释、多行状态由引擎统一处理。

```python
from yate.editor_syntax import LangSpec

def setup(api):
    spec = LangSpec(
        name="mylang",
        line_comment="#",
        block_comment=("/*", "*/"),
        keywords=frozenset({"if", "else", "return"}),
        types=frozenset({"int", "str"}),
        constants=frozenset({"true", "false", "null"}),
        builtins=frozenset({"print"}),
        type_def_words=frozenset({"class"}),   # 其后一个标识符按"类型名"着色
        func_def_words=frozenset({"fn"}),      # 其后一个标识符按"函数名"着色
    )
    api.highlight.register(spec, "ml", "mylang")   # .ml / .mylang 文件
```

注册后立即生效：`.ml` 文件自动高亮，也可在会话内 `:set filetype=ml` 或
`:set filetype=mylang`（扩展名与语言名都能解析），命令行 `Tab` 补全与状态栏
类型同步。`type_def_words` / `func_def_words` 中的词即使不放进 `keywords`
也会按关键字着色。

**API**：

| 方法/属性 | 作用 |
|---|---|
| `api.highlight.register(spec, *extensions)` | 注册/覆盖一个语言；扩展名不带点（带点也容忍） |
| `api.highlight.LangSpec` | 语言规格数据类（也可直接 `from yate.editor_syntax import LangSpec`） |
| `api.highlight.spec(**kwargs)` | 用关键字参数构造 `LangSpec` |
| `api.highlight.available()` | 当前可用于 `:set filetype` 的全部扩展名与语言名 |

**`LangSpec` 字段**：

| 字段 | 默认 | 说明 |
|---|---|---|
| `name` | （必填） | 语言名，同时作为 `:set filetype=<name>` 的候选 |
| `mode` | `"code"` | `"code"` / `"json"` / `"markdown"` / `"config"`，选择分词器 |
| `line_comment` | `None` | 行注释前缀，如 `"#"`、`"//"` |
| `block_comment` | `None` | 块注释首尾标记，如 `("/*", "*/")`（跨行） |
| `triple_strings` | `False` | 是否支持 Python 式 `'''`/`"""` 跨行字符串 |
| `string_prefixes` | `""` | 允许紧贴引号前的前缀字符（1–2 个），如 C# 的 `"@$"` |
| `sigils` | `False` | 是否高亮 `$var`/`${var}` 形式（shell） |
| `at_sigil` | `False` | `@name` 视为变量 sigil 而非装饰器（perl/ruby/PowerShell） |
| `paren_vars` | `False` | 是否高亮 `$(VAR)` 展开（make） |
| `hyphenated_idents` | `False` | `font-size` 按单个标识符扫描（CSS 属性名） |
| `keywords` | `frozenset()` | 关键字 |
| `builtins` | `frozenset()` | 内建函数/对象 |
| `constants` | `frozenset()` | 常量（`true`/`false`/`null` 等） |
| `types` | `frozenset()` | 内建类型/常见标准库类型 |
| `func_def_words` | `frozenset()` | 其后一个标识符按函数名着色（`def`、`fn`） |
| `type_def_words` | `frozenset()` | 其后一个标识符按类型名着色（`class`、`struct`、`interface`） |
| `macro_call` | `False` | 标识符紧跟 `!` 时按函数着色（Rust 宏） |

**内置语言**：yate 已识别的语言无需扩展。regex 后端为 Python、C、C++、
Java、Rust、Go、JavaScript、TypeScript、Shell、JSON、Markdown、TOML、
INI、YAML、C#、HTML、CSS、PowerShell、Lua、Make、XML、XAML、Perl、PHP、
Ruby、SQL、Zig、JSONC、SCSS、LESS 提供单词表高亮（共 30 种）；安装可选
tree-sitter 后端
（`pip install yate[ts]`）后，其中 25 种改由真实语法树解析驱动——除
JSONC、INI、Perl、SCSS、LESS 外的全部内置语言。SCSS 与 LESS 复用 CSS
单词表并留在
regex 后端——PyPI 没有对应的 tree-sitter 语法包，而用 CSS 语法解析它们会
把 `$var` / `@mixin` / `//` 解析成错误节点。

完整实例见模板 `yate/extensions/batch_syntax.py.example`（Windows batch
的声明式高亮：`rem` 注释加关键字单词表——`%VAR%` 展开与 `:label` 目标没有
单词表后端可表达的词法形式）；`ini_syntax.py.example`、
`git_syntax.py.example`、`diff_syntax.py.example` 分别演示 config 模式的
INI/Git 文件与 diff 文件，`fsharp_syntax.py.example` 演示 tree-sitter 通道。
去掉 `.example` 后缀复制到扩展目录即可，下次启动自动注册——扩展对同一扩展名的
注册会替换内置规格。

### 4.8 基于 tree-sitter 的语法高亮（自定义语法）

`api.syntax.register_tree_sitter` 为某个语言绑定真正的 tree-sitter 语法
（grammar）与 `highlights.scm` 查询——基于语法树的高亮，适合单词表
无法覆盖的自定义语言（例如你自己实现的 shell）。需要可选依赖
`pip install yate[ts]`。

```python
from pathlib import Path

def setup(api):
    here = Path(__file__).resolve().parent
    api.syntax.register_tree_sitter(
        name="yatesh",
        grammar=str(here / "yatesh.so"),   # 编译好的 grammar（见下），或
                                           # pip 包名 "tree_sitter_yatesh"
        extensions=["ysh", "yatesh"],      # 选择该语言的文件扩展名
        query=str(here / "highlights.scm"),  # 查询文件路径或查询源码字符串
        capture_map={"operator.special": "operator"},  # 可选的映射覆盖
    )
```

注册后 `*.ysh` / `*.yatesh` 文件自动高亮，`:set filetype=ysh` 立即可用
（支持 Tab 补全）。注册是全有或全无：扩展名只在 grammar 与 query 都加载成功
后才登记，缺 `tree_sitter`、缺语法包或 query 非法都会一条都不注册并报错。需要
回退的话，另用 `api.highlight.register` 为同一批扩展名注册 `LangSpec`。

grammar 库的构建方式：`npm install -g tree-sitter-cli`，在你的 grammar
仓库中运行 `tree-sitter generate` 后编译（POSIX：
`cc -shared -fPIC -I src src/parser.c src/scanner.c -o yatesh.so`；
MSVC：`cl /LD /Isrc src\parser.c src\scanner.c /Fe:yatesh.dll`）。
C 入口函数必须命名为 `tree_sitter_<name>`。查询使用 tree-sitter 的
capture 名（`@keyword`、`@comment`、`@function.call` 等），由默认映射表
（`yate/editor_syntax/ts_backend/languages.py`）转换成 yate 的 token
种类；`capture_map` 可增改单个映射。

完整模板见包内随附的 `yate/extensions/yatesh_syntax.py.example`；
`fsharp_syntax.py.example` 演示了直接绑定 pip 语法包
（`tree-sitter-fsharp`）而非编译好的 `.so`/`.dll`。
注意：同一扩展名上，`api.highlight.register`（4.7 节）的注册始终优先于
tree-sitter。

### 4.9 屏保精灵（`api.sprites`）

`api.sprites.register` 为空闲屏保（`Alt+Shift+S`）注册自定义角色：
它与 27 个内置精灵一起混入游行队、参与播放列表洗牌，也可以写进
yaterc 的 `screen_saver.characters` 白名单。

**帧格式** —— 一个角色由若干帧加一个调色板组成。每帧是等长的字符串
序列，每行对应一个像素行；行内每个字符要么是调色板键（一个着色
像素），要么是 `.`（透明）。调色板把每个键字符映射为 `"#rrggbb"`
颜色字符串：

```python
FRAMES = (
    (   # 第 1 帧：睁眼
        "..GG..",
        ".GGGG.",
        "GGWWGG",
        ".GGGG.",
        "..GG..",
    ),
    (   # 第 2 帧：红眼
        "..GG..",
        ".GGGG.",
        "GGRRGG",
        ".GGGG.",
        "..GG..",
    ),
)
PALETTE = {"G": "#00aa00", "W": "#ffffff", "R": "#cc0000"}

def setup(api):
    api.sprites.register("blob", FRAMES, PALETTE)
```

**渲染规则** —— 屏保用 Unicode 半块字符把两个像素行画进一个终端
文本行：上像素成为 `▀` 的前景色，下像素成为其背景色（同色 → 实心
`█`，只有下像素 → `▄`，都没有 → 空格）。因此 *n* 个像素行占
`ceil(n / 2)` 个文本行，*w* 个像素列占 *w* 个文本列（1 像素 = 1
字符格）。请把精灵控制在 24 行终端能容纳的尺寸（约至多 40 像素
行），避免游行画面被裁切。

**约束** —— 注册时校验，规则与内置名册导入期校验完全一致：

- 至少 2 帧；
- 所有帧同宽同高（不允许参差帧）；
- 每个非 `.` 像素都有调色板条目。

违规抛出 `ValueError`，加载器会在启动消息栏报告
`extension <名字>: ValueError ...`，该角色不会被注册。重名同样被
拒绝——包括内置名，扩展永远不能替换内置角色。

**API**：

| 方法 | 作用 |
|---|---|
| `api.sprites.register(name, frames, palette)` | 注册角色；重名或数据非法时抛 `ValueError` |
| `api.sprites.unregister(name)` | 移除本扩展注册的角色（内置名不可删；未知名抛 `KeyError`） |
| `api.sprites.names()` | 当前全部角色名（内置 + 扩展），可用作注册自检 |

**完整示例（含 teardown）**：

```python
# ~/.yate/extensions/blob.py
FRAMES = (...)   # 同上
PALETTE = {"G": "#00aa00", "W": "#ffffff", "R": "#cc0000"}

def setup(api):
    api.sprites.register("blob", FRAMES, PALETTE)
    assert "blob" in api.sprites.names()  # 注册自检

def teardown(api):
    api.sprites.unregister("blob")  # 热重载不残留幽灵名字
```

**白名单时序** —— yaterc 的 `screen_saver.characters` 白名单在启动期
校验，此刻只知道内置名册；扩展角色在扩展加载期才注册，因此白名单
引用扩展角色会先收到一条无害的启动警告
（`unknown screensaver character: 'blob'`）。该警告不影响功能：屏保
每次开启时都会按实时注册表重新过滤白名单，扩展加载完成后角色即
生效。可以接受这条已知噪音，也可以不设白名单（空 = 全部角色，
含扩展角色）。

### 4.10 编辑器事件（`api.events`）

`api.events.subscribe` 订阅编辑器生命周期事件。事件标识是
`EditorEvent` 枚举成员，已再导出为 `api.events.EditorEvent`，扩展无需
导入 yate 内部模块——绝不接受字符串——每个载荷都是冻结的 dataclass：

```python
def setup(api):
    def on_theme(payload):
        api.message(f"theme switched to {payload.name}")

    unsubscribe = api.events.subscribe(
        api.events.EditorEvent.THEME_CHANGED, on_theme)
    # 调用 unsubscribe() 即可退订
```

| 事件 | 载荷 | 触发时机 |
|---|---|---|
| `EditorEvent.DOCUMENT_SAVED` | `DocumentSaved(doc)` | 文档写入磁盘（`:w`、`:saveas`、`api.save()`） |
| `EditorEvent.DOCUMENT_OPENED` | `DocumentOpened(doc)` | 打开了会话中尚未打开的文件 |
| `EditorEvent.DOCUMENT_CLOSED` | `DocumentClosed(docs)` | 一个或多个文档离开会话（`:bd`、关闭最后一个标签） |
| `EditorEvent.DOCUMENT_ACTIVATED` | `DocumentActivated(doc)` | 某文档成为活动文档（打开、`:bn`/`:bp`、点击标签） |
| `EditorEvent.DIAGNOSTICS_UPDATED` | `DiagnosticsUpdated(doc)` | 语言服务器发布了诊断；载荷即诊断实际归属的文档 |
| `EditorEvent.KEYMAP_CHANGED` | `KeymapChanged(name)` | 活动键位表切换（`vsc` / `vim`） |
| `EditorEvent.THEME_CHANGED` | `ThemeChanged(name)` | 配色主题切换（`:theme`） |

派发契约：

- **同步、同线程、按订阅顺序**——监听器看到的是派发时刻的状态；
  不要在监听器里阻塞。
- **监听器彼此隔离**——抛异常的监听器会被记录（trace 日志）并上报
  消息栏；其余监听器照常运行，触发派发的编辑器操作也继续。
- `subscribe` 返回**退订函数**；重复订阅各自独立登记（VS Code
  disposables 语义），退订两次是安全的空操作。
- `setup` 期间的订阅受回滚 scope 保护：失败的 setup 会把订阅一并撤销。
- **`DOCUMENT_OPENED` 先于 `DOCUMENT_ACTIVATED`**——新打开的文档先发
  `DOCUMENT_OPENED`，成为活动文档后再发 `DOCUMENT_ACTIVATED`；复用
  会话中已打开的文档只发激活事件。

事件只挂在低频点上（保存 / 打开 / 关闭 / 激活 / 诊断 / 键位 / 主题）
——刻意不提供逐按键事件。

### 4.11 状态栏段与画布（`api.ui`）

`api.ui.add_segment` 向状态栏贡献一个文本段。状态栏是**拉取式**
注册表：每次刷新时逐个调用已注册的 provider 一次，并用状态栏自己的
样式绘制返回的字符串——扩展只贡献文本，不贡献 widget 或颜色。

保持 provider **轻量**：状态栏在每次光标移动与模式切换后都会刷新，
若 provider 扫描整个缓冲区就会随之反复执行。优先返回短字符串与廉价
查询；较重的聚合统计更适合放进事件监听器（如 `DOCUMENT_OPENED` /
`DOCUMENT_SAVED`）里算好，刷新时只取现成结果。

```python
def setup(api):
    api.ui.add_segment(
        "wordcount",
        lambda: f"{len(api.buffer.get_text().split())}w",
        align="right",   # "left" 或 "right"（默认 "right"）
        priority=0,      # 越大在同侧越靠前
    )
    # 等价的显式写法——自己构造冻结的 StatusSegment：
    #   from yate.services.extensions import StatusSegment
    #   api.ui.add_status_segment(StatusSegment(
    #       "wordcount", provider, align="right", priority=0))
```

规则：

- provider 返回 `None` 或空串时，该段本轮隐藏——可用它做条件显示。
- provider 抛异常时降级为 `!` 占位符（记录日志，绝不致命）；一个坏掉
  的扩展拖不垮其余状态栏。
- 重复 id 抛 `ValueError`；`api.ui.remove_status_segment(id)` 移除
  一个段（未知名抛 `KeyError`）。
- 注册参与回滚 scope：失败的 setup 会把段一并撤销。

**`api.ui.open_canvas(cols, rows, on_key, on_tick, on_close)`** 打开一个
可由脚本绘制的全屏模态画布——随包俄罗斯方块（`:game tetris`）正是用它
实现的。返回一个**句柄**，带三个方法：

| 方法 | 作用 |
|---|---|
| `handle.draw(grid, palette)` | 重绘画布：*grid* 是换行拼接的单个字符串（每行一个字符串），*palette* 把单元格字符映射到 `"#rrggbb"` 颜色；空格与未登记字符用默认色；超出网格的行/列被裁剪 |
| `handle.set_status(text)` | 替换网格下方的状态行 |
| `handle.close()` | 关闭画布（幂等） |

三个回调：*on_key* 收到 Textual 键名（`left`、`space`、……）——画布是模态
屏，按键不会再到达下层编辑器；`escape` 是画布自带的退出键，不会进
*on_key*；*on_tick* 按画布自有时钟触发（每秒 15 tick——靠累计 tick 放慢
游戏重力）；*on_close* 在屏幕关闭后触发一次。

```python
def setup(api):
    handle = None

    def on_key(key):            # "left" / "right" / "space" / ...
        ...                     # 更新游戏状态；下一个 tick 再绘制
    def on_tick():
        if handle:
            handle.draw("##  \n    \n", {"#": "#e57373"})
            handle.set_status("score 0")
    def on_close():
        pass

    handle = api.ui.open_canvas(10, 20, on_key, on_tick, on_close)
```

规则：

- `cols` / `rows` 是网格尺寸；屏幕居中显示网格，终端更小时裁剪。
- 句柄随画布消亡：屏幕关闭后的调用一律忽略，tick 与关闭竞态无害。
- 宿主没有 UI（headless 构造）时打开会抛 `RuntimeError`。
- 回调抛异常会被上报且画布继续运行；`escape` 始终可用。

### 4.12 运行动作与重绑按键（`api.actions` / `bind_action` / `unbind_key`）

`api.actions` 按名字运行动作、查询动作注册表。`run` 走编辑器的统一
按键派发路径，扩展触发的动作与按键触发完全一致：

| 方法 | 作用 |
|---|---|
| `api.actions.run(name)` | 运行动作 *name*；名字未知时返回 `False` |
| `api.actions.names()` | 全部已注册动作名 |
| `api.actions.has(name)` | *name* 已注册时为 `True` |

```python
if api.actions.has("delete_line"):
    api.actions.run("delete_line")   # 与按键触发同一条派发路径
```

`api.bind_action(key_spec, action_name, keymap="vsc")` 把按键绑定到
**具名动作**——内置的或自己注册的都可以，扩展借此重排内置键位：

```python
def setup(api):
    # 把 <ctrl-shift-d> 重绑到内置的 delete_line 动作，两张键位表同时生效
    # （"both" = "vsc" + "vim"；"normal" 是 "vsc" 的别名）。
    api.bind_action("<ctrl-shift-d>", "delete_line", keymap="both")

    # 自己的动作：先注册后绑定——bind_action 按名字引用动作。
    api.register_action("ext.duplicate",
                        lambda ctx: ctx.buffer.duplicate_line(),
                        "duplicate the current line")
    api.bind_action("<ctrl-shift-alt-d>", "ext.duplicate")
```

- 可选的 `description` / `category` 与 `api.bind_key` 一致；没有装饰器
  形式——动作按名字引用，不作为参数传入。
- **先注册后绑定**：未知的 *action_name* 不会绑定任何东西，只记录一条
  警告（列出已注册动作名）；未知的 *keymap* 名同样处理。写错名字不会
  静默占用按键。
- 回滚（第 3 节）：setup 失败时，`bind_action` 触碰过的每个键都会恢复
  原绑定。

`api.unbind_key(key_spec, keymap="vsc")` 解除绑定（`keymap="both"` 两张
键位表一起解）。只要有键位表实际移除了绑定就返回 `True`；键本来就未
绑定或键位表名未知时返回 `False`：

```python
removed = api.unbind_key("<ctrl-shift-alt-d>")
api.unbind_key("<ctrl-shift-d>", keymap="both")
```

### 4.13 主题、剪贴板与打开的文档（`api.theme` / `api.clipboard` / `api.docs`）

**`api.theme`** 切换与读取配色主题：

```python
api.theme.set("gruvbox-dark")   # 名字未知时抛 KeyError
current = api.theme.active()    # 当前主题名（只读）
```

**`api.clipboard`** 读写系统剪贴板；没有可用后端时两个调用都优雅降级
（`False` / `None`），扩展代码不会见到平台异常：

```python
api.clipboard.set("copied!")    # 不可用时返回 False
text = api.clipboard.get()      # str（空剪贴板为 ""），不可用时为 None
```

**`api.docs`** 是会话中已打开文档的只读视图：

| 方法 | 作用 |
|---|---|
| `api.docs.all()` | 全部打开的文档——返回新列表，元素为 `Document`（成员见 4.4 节） |
| `api.docs.is_open(path)` | 显示 *path* 的文档已在会话中打开时为 `True` |

```python
for doc in api.docs.all():
    api.message(f"{doc.name}: {'modified' if doc.modified else 'saved'}")
if not api.docs.is_open("notes.md"):
    api.open_path("notes.md")   # 变更类操作走常规流程
```

刻意收窄：这里没有打开/激活/关闭——文档生命周期走编辑器的 UI 流程
（`api.open_path`、`api.save`、`:` 命令），不开旁门。

### 4.14 让 Lua 脚本通过 IDE 静态检查（`_yate.d.lua` + `.luarc.json`）

Lua 扩展脚本就是普通的 Lua 文件，编辑器既不认识全局 `yate` 表，也不
认识 `setup(api)` 的 `api` 参数——开箱即用时两者都会被标成未知名。
为此 yate 随包提供两份 lint 基建：

- `yate/extensions/_yate.d.lua` —— `---@meta` 声明文件：逐个声明
  `_yate.lua` 的全部导出函数，签名与注解（`---@param` / `---@return`）
  完全一致（不含逻辑；`_` 前缀使它不被自动加载扫描命中）；
- `.luarc.json`（仓库根）——yate 自有 Lua 文件所用的
  lua-language-server 配置；其中 `workspace.library` 的写法就是下文
  配方 (a) 的那个开关。

推荐的编辑器环境是 VS Code 加 **"Lua"** 插件（lua-language-server）。
两种配方让你的脚本获得干净的检查结果：

**(a) 把 workspace library 指向 yate 安装目录**——继续使用随包的那份
声明文件，按路径引用其所在目录：

```json
{
  "workspace.library": ["<yate>/yate/extensions"]
}
```

`<yate>` 是安装好的 `yate` 包目录——wheel 安装即
`.../site-packages/yate/extensions`；frozen 二进制或可编辑安装的同一
目录在别的位置（指到含 `_yate.lua` / `_yate.d.lua` 的那个目录即可）。

**(b) 把声明文件复制进项目**——自包含，重装与升级 yate 都不受影响：

把 `yate/extensions/_yate.d.lua` 复制进项目（惯例放在 `.vscode/`），
并配置声明文件覆盖不到的那一个全局名：

```json
{
  "diagnostics.globals": ["api"]
}
```

任选其一，`yate.*` 即获得签名补全，针对它的 unknown-global 诊断消失；
`api` 条目覆盖 `setup(api)` 的形参——它只在运行期存在。

### 4.15 持久化数据（`api.data`）

`api.data` 读写 `~/.yate/data` 下的 UTF-8 小文档，是扩展**唯一**的文件通道：
名字相对该目录（绝对路径、盘符或含 `..` 会抛 `ValueError`，桥把失败统一报成
`None` / `False`，不会把编辑器打崩），写入是原子的——先写同目录临时文件再改名，
中途崩溃只会留下旧版本。

| 方法 | 返回 |
|---|---|
| `api.data.read(name)` | 文档文本；不存在时 `None` |
| `api.data.write(name, text)` | 成功 `True`；名字非法或 I/O 失败 `False` |
| `api.data.remove(name)` | 确实删掉了文件为 `True` |
| `api.data.list(prefix)` | 子目录下的文件名（升序，目录不存在为 `[]`） |

```python
import json

def setup(api):
    raw = api.data.read("games/snake.json")
    best = json.loads(raw)["high_scores"][0]["score"] if raw else 0
    api.data.write(
        "games/snake.json",
        json.dumps({"version": 1, "high_scores": [{"score": best + 1}]}),
    )
```

随包游戏在 `games/` 下每游戏一个 JSON 文档，字段见
[games.zh.md](games.zh.md)。Lua 侧包装为 `yate.data.read` / `.write` /
`.remove` / `.list`（见第 6 节函数表）。

---

## 5. 完整示例：单词计数 + 选区大写

```python
from yate.services.shell import ShellResult

def setup(api):
    @api.command("words", "count words in the document")
    def words(_args):
        api.message(f"word count: {len(api.buffer.get_text().split())}")

    @api.command("upper", "uppercase the selection (or current line)")
    def upper(_args):
        buf = api.buffer
        if buf.has_selection():
            buf.insert_text((buf.selected_text() or "").upper())
        else:
            row = buf.row
            buf.lines[row] = buf.lines[row].upper()
            buf.mark_content_changed()  # 直接改 lines 后必须刷新
        api.message("uppercased!")

    api.bind_key("<alt-u>", lambda ctx: upper(""), keymap="both",
                 description="uppercase selection/line (extension)")
```

---

## 6. Lua 扩展

`.lua` 扩展脚本与 Python 脚本走同一条加载管线（发现、排序、
`disabled_extensions`、去重、工作区信任、回滚 scope 与 teardown），
前提是安装了可选的桥接包：

```
pip install yate[lua]
```

未安装时，加载 `.lua` 扩展只会记录一条可操作的错误提示
`lua extensions require the lupa package; install with: pip install yate[lua]`，
其余一切照常工作。

### Lua 扩展的形态

三种写法，加载时按优先级取第一个命中的：**模块表 > 全局 `setup` >
顶层**：

- **模块表风格（推荐）**：Lua 生态的标准库形态——构建一张模块表并
  `return` 返回，yate 调用其 `setup(api)` / `teardown(api)` 字段。契约
  显式、不占全局名，适合正式维护的扩展。注意：**返回了表却没有可调用
  的 `setup` 字段会直接报错**——返回表即表达了模块意图，缺入口多半是
  拼写错误，静默放行只会留下"加载成功却什么都没注册"的困惑；
- **显式风格**：定义全局 `function setup(api)`——yate 会在顶层代码运行
  之后，用同一个 `api` 对象调用它一次，与 Python 的 `setup(api)` 逐行
  对应，适合从 Python 扩展迁移或对照手册学习；
- **顶层风格**（Lua 脚本惯例，向后兼容）：chunk 的**顶层代码就是
  setup**——没有 `setup(api)` 函数，适合十几行的快速脚本。

三种风格下，卸载钩子同理按优先级取 `mod.teardown(api)`（模块表风格）
或全局 `teardown(api)`（其余两种风格）。

模块表风格示例（推荐）：

```lua
-- ~/.yate/extensions/hello.lua
local mod = {}

function mod.setup(api)
  api.register_command("lua-hello", function(args)
    api.message("hello from lua! args: " .. (args or ""))
  end, "greet from a lua extension")

  api.bind_key("<alt-h>", function(ctx)
    api.message("Alt+H pressed")
  end, "both")                   -- 位置参数（Lua 没有 kwargs）
end

function mod.teardown(api)
  -- 退出时的可选清理（释放本扩展持有的资源）
end

return mod
```

顶层风格示例（快速脚本）：

```lua
-- ~/.yate/extensions/hello.lua
local yate = require("yate")   -- 或直接使用全局 `yate`

yate.register_command("lua-hello", function(args)
  yate.message("hello from lua! args: " .. (args or ""))
end, "greet from a lua extension")

yate.bind_key("<alt-h>", function(ctx)
  yate.message("Alt+H pressed")
end, "both")                   -- 位置参数（Lua 没有 kwargs）

-- 退出时的可选清理：
-- teardown = function(api) ... end
```

错误不会导致编辑器崩溃：失败的 chunk 以
`extension <名字>: LuaError: ...` 的形式上报，且它已经做出的全部注册
会被自动回滚。模块表风格下返回了缺 `setup` 字段的表，则以
`extension <名字>: RuntimeError: extension module table has no setup(api) function ...`
上报。命令/按键/动作回调在运行期抛出的错误同样会被捕获并按
相同形式上报到消息栏，回调失败绝不会拖垮编辑器。

### `yate` API 库

内置库 `yate/extensions/_yate.lua` 被注入每个扩展的运行时：
`require("yate")` 与全局 `yate` 是同一张模块表（下划线前缀使库本身
不会被自动加载扫描命中）。

| 函数 | 用途 |
|---|---|
| `yate.message(text)` | 在消息栏显示提示 |
| `yate.register_command(name, fn, desc?)` | 注册 `:` 命令；`fn` 接收原始参数字符串 |
| `yate.register_action(name, fn, desc?)` | 注册命名动作 |
| `yate.bind_key(spec, fn, keymap?)` | 绑定按键（`"vsc"` / `"vim"` / `"both"`；默认 `"vsc"`） |
| `yate.bind_action(spec, action, keymap?)` | 把按键绑定到**已注册**动作（内置或自己的均可；先注册后绑定，见 4.12 节） |
| `yate.unbind_key(spec, keymap?)` | 解除按键绑定；有移除时返回 `true` |
| `yate.events.subscribe(name, fn)` | 订阅编辑器事件；`name` 为小写事件名（`"document_saved"` … `"theme_changed"`，见 4.10 节） |
| `yate.ui.add_segment(id, provider, align?, priority?)` | 贡献一个状态栏段（见 4.11 节） |
| `yate.ui.remove_segment(id)` | 移除此前贡献的状态栏段（见 4.11 节） |
| `yate.ui.open_canvas(cols, rows, on_key, on_tick, on_close)` | 打开全屏模态画布；返回绘制句柄（见 4.11 节） |
| `yate.theme.set(name)` / `yate.theme.active()` | 切换/读取配色主题（见 4.13 节） |
| `yate.clipboard.set(text)` / `yate.clipboard.get()` | 系统剪贴板（见 4.13 节） |
| `yate.docs.all()` / `yate.docs.is_open(path)` | 打开文档的只读视图（见 4.13 节） |
| `yate.data.read(name)` / `.write(name, text)` / `.remove(name)` / `.list(prefix)` | `~/.yate/data` 下的文档（见 4.15 节） |
| `yate.actions.run(name)` / `.names()` / `.has(name)` | 运行/列出/探测已注册动作（见 4.12 节） |
| `yate.keymaps` | 已加载键位集合（`api.keymaps` 原样透传） |
| `yate.shell(cmd)` | 静默执行 shell 命令；返回 `ShellResult` 对象（读 `.output` / `.returncode`） |
| `yate.open_path(path)` | 在编辑器中打开文件/目录 |
| `yate.save()` | 保存当前文档 |
| `yate.buffer()` / `yate.doc()` / `yate.workspace()` | 运行时对象（成员见 4.4 节） |
| `yate.api` / `yate.highlight` / `yate.sprites` / `yate.lsp` / `yate.syntax` | 原始 Python 桥（高级用法） |

上表每个包装都与 Python API 的成员一一对应——同名、同语义、按位置
传参（Lua 没有关键字参数），省略的可选参数回落到 Python 默认值；
共同行为见 4.10 / 4.11 / 4.12 / 4.13 节。

与 Python 枚举不同，`yate.events.subscribe` 接收上表列出的小写事件名；
载荷仍是同一个冻结 dataclass（用点号读字段）。超出本表的能力仍可经
`yate.api` 触达原始 Python 桥。

### 共享 Lua 模块（`extensions/lib/`）

多个 Lua 脚本都要用的代码只有一个落点：`yate/extensions/lib/` 下的 `.lua` 文件，
用 `require("<文件名主干>")` 取用。装载器会在脚本运行前把每个 `lib/*.lua` 编译进
运行时的 `package.preload`，因此：

- `lib/` 里的文件**不会**被当成扩展自动加载（装载器只扫目录顶层）；
- 共享模块**不得**定义 `setup` / `teardown`——它是库，不是脚本；
- 每个运行时编译自己的一份副本，两个脚本 require 同一个模块也互相看不见状态；
- 新增模块不需要改 Python：下次启动自动生效。

```lua
local engine = require("game_engine")   -- yate/extensions/lib/game_engine.lua

local game = {}
function game.setup(_api)
  engine.register("mygame", start)       -- 由该共享模块提供
end
return game
```

随包游戏包正是一例，也示范了按体量拆分：`lib/game_engine.lua`（文档存储、高分榜、
派发、画布会话）、`lib/engine_json.lua`（编解码）、`lib/engine_layout.lua`
（字形词表与边框排版）三个模块各司其职，`game_engine` 再导出另两个，
所以游戏仍只需 require 一个名字；`games.lua` 与每个游戏文件只带自己的规则。
引擎 API 表与一个完整的最小游戏见 [games.zh.md](games.zh.md)。

### Lua 的编辑器补全（`---@` 注解）

`_yate.lua` 中每个导出函数都带有 EmmyLua 注解（`---@param` /
`---@return`）：运行 lua-language-server 的编辑器开箱即可获得
`require("yate")` 的签名补全。注解就是「开放 pyi」的 Lua 等价物；随包
同时分发镜像的 `---@meta` 声明文件 `_yate.d.lua`，供你自己的项目对
同一 API 面做静态检查（见 4.14 节）。

### lupa 语义注意

- 每个 `.lua` 扩展都有**独立的 Lua 运行时**；脚本之间看不到彼此的全局变量。
- Python 对象从 Lua 侧用点号调用（`yate.api.buffer.get_text()`），
  其**索引从 0 开始**：第一行缓冲区文本是 `yate.buffer().lines[0]`。
- Lua 的长度操作符 `#` 不能用于 Python 对象；取 Python 列表长度请用桥
  提供的 `python.builtins.len(list)`。
- Lua 无法向 Python 传关键字参数——库函数全部按位置传参，省略的可选
  参数回落到 Python 默认值。这也是 `bind_key` 额外接受位置形式的
  `keymap` / `description` / `category` 的原因（Python 调用方不受影响）。
- Python 字符串与 Lua 字符串双向无损转换。

### 安装示例

`yate --setup-defaults` 会把 `lua.example` 放入 `~/.yate/extensions/`；
重命名它（如改为 `hello.lua`）即可激活，或直接阅读——它是一份带完整
注释的入门教程。

---

## 7. 扩展包（`.yxp`）

扩展包把多个文件打包成一个压缩档，便于分发与安装。`.yxp`
（Yate eXtension Package）本质是 zip 包，内含载荷文件与两个保留成员：

- `manifest` —— JSON 元数据：`name`（必填，须匹配 `^[A-Za-z0-9._-]+$`）、
  `version` / `description` / `author`（可选），以及列出全部载荷成员的
  `files` 清单。
- `checksum` —— JSON，把每个载荷成员映射到其小写 SHA-256 十六进制
  摘要。格式上允许缺省，但官方打包工具总是写入；存在时 yate 会在解压
  前校验文件清单与每个摘要。

### 安装、卸载、列表

```text
yate --install-extension hello_yxp.yxp          # 校验 + 解压 + 记录
yate --uninstall-extension hello_yxp            # 移除已记录的文件
yate --list-extensions                          # 显示已安装的包
```

这三个选项都是 side 命令（打印报告后退出；install/uninstall 可重复；
失败退出码 1）。编辑器内也可用同样的操作：

```text
:install-extension hello_yxp.yxp
:uninstall-extension hello_yxp
:list-extensions            " 报告显示在输出浮层里
```

### 安装过程做了什么

- 载荷**平铺**解压到 `~/.yate/extensions/` —— 正是启动加载器扫描的
  目录，因此顶层 `*.py` / `*.lua` 成员在下次启动时生效（安装后需重启
  yate）。
- 归属记录写入 `~/.yate/extensions/_manifests/<name>.json`。
- 目标文件已存在但不属于同名包时拒绝安装——你手工放置的文件绝不会被
  覆盖。
- 同名重装即原位升级：覆盖自家文件，并删除新版本中已不存在的过时
  文件。
- 卸载严格按记录删文件（缺失容忍并上报），随后删除记录。

### 用 `tools/yxp` 打包

仓库自带打包工具（开发工具，不随 wheel 分发）：

```bash
python -m tools.yxp --create my_ext                     # 脚手架 ./my_ext/
python -m tools.yxp --pack tools/yxp/example/hello_yxp  # -> hello_yxp.yxp
python -m tools.yxp --verify hello_yxp.yxp
```

`--create NAME` 生成源目录脚手架：一个 `manifest` 元数据文件加一个
`<name>.py` 起步扩展（注册一个问候命令）——填好元数据后按需扩充载荷。
`--pack DIR` 接收一个源目录，目录里须有 `manifest` 元数据文件（JSON，含
`name` / `version` / `description` / `author` —— 不写 `files` 字段，由
打包器计算）。它会写入打包后的 manifest、`checksum` 成员与全部载荷
文件，并跳过 `__pycache__`、`.git` 与 `*.pyc`。内置示例
（`tools/yxp/example/hello_yxp/`）注册 `:hello-yxp` 问候命令——构建、
安装、重启 yate 后运行 `:hello-yxp` 即可体验。

### 安全须知

- 校验仅保证完整性（SHA-256）：能发现损坏或被篡改的包，但不是签名——
  只安装你信任的包。
- 不安全的成员名（绝对路径、`..` 段、反斜杠、保留目录 `_manifests/`）
  在写盘前一律拒绝。
- 没有 `checksum` 成员的包按未校验安装；可先用
  `python -m tools.yxp --verify FILE.yxp` 检查。
