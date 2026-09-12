# yate 扩展（Extensions）

[English](extensions.en.md) · **中文**

yate 的扩展是任意一个暴露 `setup(api)` 函数的 `.py` 文件（可选提供
`teardown(api)`）。`setup` 在应用启动时被调用，通过传入的 `api` 对象
可以注册命令、动作、按键绑定、语言服务器，以及访问当前缓冲区、文档、
工作区等运行时对象。

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
2. **随包扩展** `yate/extensions/`（`python_lsp`、`csharp_highlight`，
   无论当前工作目录在哪都会自动加载；可用 yaterc 的 `disabled_extensions`
   按文件名主干禁用，见下文）；
3. 默认目录：工作目录下的 `./extensions/` 与 `~/.yate/extensions/`
   （启动时自动加载其中所有 `*.py`，下划线开头的文件跳过）；
4. 命令行：`--ext <文件>` 加载单个文件，`--ext-dir <目录>` 加载目录下
   所有 `*.py`（均可重复指定）。

加载顺序即上面的编号顺序；同一路径只执行一次，因此把修改版脚本放进
`~/.yate/extensions/`（第 3 步）可以覆盖随包同名扩展的注册。下划线开头
的文件与 `.example` 后缀的模板不会被加载。

### 禁用随包默认扩展（disabled_extensions）

在 yaterc 中按**文件名主干**（不含 `.py`）列出要跳过的随包扩展：

```python
disabled_extensions = ["python_lsp"]
disabled_extensions = ["python_lsp", "csharp_highlight"]
```

- 接受字符串或字符串列表，多个 rc 文件之间**累加**并去重；
- 只影响随包默认扩展——rc 路径、`./extensions/`、`~/.yate/extensions/`、
  命令行指定的脚本一律照常加载；
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
| `api.keymaps` | `dict[str, Keymap]` | 所有已加载键位（`vsc`/`vim`） |
| `api.app` | `YateApp` | 应用本体（高级用法） |

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
from yate.editor_view.highlight import LangSpec

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
| `api.highlight.LangSpec` | 语言规格数据类（也可直接 `from yate.editor_view.highlight import LangSpec`） |
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
| `keywords` | `frozenset()` | 关键字 |
| `builtins` | `frozenset()` | 内建函数/对象 |
| `constants` | `frozenset()` | 常量（`true`/`false`/`null` 等） |
| `types` | `frozenset()` | 内建类型/常见标准库类型 |
| `func_def_words` | `frozenset()` | 其后一个标识符按函数名着色（`def`、`fn`） |
| `type_def_words` | `frozenset()` | 其后一个标识符按类型名着色（`class`、`struct`、`interface`） |
| `macro_call` | `False` | 标识符紧跟 `!` 时按函数着色（Rust 宏） |

完整实例见包内随附的 `yate/extensions/csharp_highlight.py`
（C# 高亮：`cs`/`csx`，含关键字、上下文关键字、BCL 类型、`$`/`@` 字符串前缀等；
该扩展随包自动加载，无需放在工作目录内；不想加载时在 yaterc 中设置
`disabled_extensions = ["csharp_highlight"]`，也可用
`yate --ext csharp_highlight.py` 显式加载一份修改版）。

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
