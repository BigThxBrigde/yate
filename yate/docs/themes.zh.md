# yate 主题（Themes）

[English](themes.en.md) · **中文**

yate 的颜色主题由两部分组成：**界面配色**（背景、状态栏、选中、边框等）
和**语法高亮色板**。两者都封装在 `Theme` 数据类中。

内置四套主题均为 [Catppuccin](https://catppuccin.com/) 风味：
`mocha`（默认，深色）、`macchiato`、`frappe`、`latte`（浅色）。

本文件是主题定制的完整参考；手册第 10.3 / 11 节是简介。

---

## 1. 选择主题

| 方式 | 操作 |
|---|---|
| 命令 | `:theme latte`、`:colorscheme latte`（不带参数列出全部已注册主题） |
| 选项 | `:set theme=latte` |
| 配置 | yaterc 中 `theme = "latte"` |
| 启动参数 | `yate --theme latte`（覆盖 yaterc 的 `theme`） |

切换只影响当前会话；要永久生效请写入 yaterc。未知主题名会报错并列出
可用主题。

---

## 2. 客制化主题的四种方式

### 方式 A：在 yaterc 中内联注册

yaterc 的执行命名空间里注入了 `Theme` 与 `register_theme()`，少量改色
可以直接写：

```python
from dataclasses import replace
from yate.editor_view.theme import THEMES

register_theme(replace(
    THEMES["mocha"],
    name="my-mocha",
    label="My Mocha",
    accent="#89b4fa",
    accent2="#cba6f7",
))
theme = "my-mocha"
```

### 方式 B：`theme_dirs` 指定主题目录/文件

在 yaterc 中声明一个或多个路径，启动时自动加载其中所有 `*.py`：

```python
theme_dirs = "~/.yate/themes"           # 单个目录
theme_dirs = [
    "~/.yate/themes",                   # 自动展开 ~
    "./team-themes",                    # 相对路径：相对本 yaterc 所在目录
    "./extras/solarized.py",            # 也可以是单个主题文件
]
```

主题文件就是普通 Python，作用域内已注入 `Theme` 与 `register_theme()`，
也可以正常 `import`。

### 方式 C：默认目录（无需配置）

不做任何配置时，yate 会自动扫描：

- 工作目录下的 `./themes/`
- `~/.yate/themes/`

把 `*.py` 主题文件丢进去即可（下划线开头的文件会被跳过）。

### 方式 D：命令行 `--theme-dir`

临时指定，可重复：

```bash
yate --theme-dir ~/my-themes --theme-dir ./extras/solarized.py
```

`--theme-dir` 既接受目录，也接受单个 `*.py` 文件。

---

## 3. 同名覆盖与加载优先级

同名主题被多次注册时，**后加载者覆盖先加载者**。优先级从低到高：

1. 内置主题（`mocha` / `macchiato` / `frappe` / `latte`）
2. 默认目录 `./themes`、`~/.yate/themes`
3. yaterc 中的 `theme_dirs`（先用户 rc、后项目 rc）
4. 命令行 `--theme-dir`

因此可以用一个项目级 yaterc 的 `theme_dirs` 覆盖用户级主题，或用
`--theme-dir` 在单次启动中临时覆盖全部。

主题文件出错不会中断启动：错误以 `<路径>: <问题>` 的形式显示在启动
消息栏，其余文件照常加载。

---

## 4. 如何写一个主题文件

最简单的做法是复制内置主题再覆盖少量颜色：

```python
# ~/.yate/themes/my_mocha.py
from dataclasses import replace
from yate.editor_view.theme import THEMES

register_theme(replace(
    THEMES["mocha"],
    name="my-mocha",        # 必须唯一；与内置重名会覆盖内置
    label="My Mocha",
    accent="#89b4fa",       # 主色：状态栏底色、活动 tab、选中项
    accent2="#cba6f7",      # 次色
))
```

也可以从零构造一个 `Theme`（所有字段必填，`extra` 除外）：

```python
register_theme(Theme(
    name="solarized-dark",
    label="Solarized Dark",
    dark=True,
    bg="#002b36", panel="#073642", surface="#073642",
    gutter_bg="#002b36", border="#586e75",
    selection_bg="#073642", match_bg="#b58900", match_active_bg="#cb4b16",
    on_accent="#002b36",
    fg="#839496", fg_dim="#586e75", fg_muted="#657b83", fg_bright="#93a1a1",
    accent="#268bd2", accent2="#6c71c4",
    green="#859900", yellow="#b58900", red="#dc322f", orange="#cb4b16",
    mode_normal_bg="#268bd2", mode_insert_bg="#859900",
    mode_visual_bg="#6c71c4", mode_command_bg="#cb4b16",
    syn_keyword="#859900", syn_string="#2aa198", syn_number="#d33682",
    syn_comment="#586e75", syn_function="#268bd2", syn_type="#b58900",
    syn_constant="#cb4b16", syn_builtin="#dc322f", syn_decorator="#d33682",
    syn_operator="#93a1a1", syn_property="#6c71c4",
))
```

---

## 5. `Theme` 字段参考

所有颜色值为 `#RRGGBB` 十六进制字符串。

### 背景（backgrounds）

| 字段 | 用途 |
|---|---|
| `bg` | 编辑区背景 |
| `panel` | 标签栏 / 侧栏 / 状态栏背景 |
| `surface` | 当前行高亮 / 输入框背景 |
| `gutter_bg` | 行号装订槽背景 |
| `border` | 细微分隔线 |

### 叠加层（overlays）

| 字段 | 用途 |
|---|---|
| `selection_bg` | 选区背景 |
| `match_bg` | 搜索匹配项背景 |
| `match_active_bg` | 当前搜索匹配项背景 |
| `on_accent` | 画在强调色块（如匹配高亮）之上的文字颜色 |

### 前景（foregrounds）

| 字段 | 用途 |
|---|---|
| `fg` | 正文前景 |
| `fg_dim` | 注释等弱化文本 |
| `fg_muted` | 次要文本 |
| `fg_bright` | 强调文本 |

### 强调色（accents）

| 字段 | 用途 |
|---|---|
| `accent` | 主色（蓝）：状态栏底色、活动 tab、选中项 |
| `accent2` | 次色（紫） |
| `green` / `yellow` / `red` / `orange` | 状态色（成功/警告/错误等） |

### 模式色块（status bar mode chips）

| 字段 | 用途 |
|---|---|
| `mode_normal_bg` | 普通模式 |
| `mode_insert_bg` | 插入模式 |
| `mode_visual_bg` | 可视模式 |
| `mode_command_bg` | 命令模式 |

### 语法色板（syntax palette）

对应 `highlight.py` 产出的 token 种类：

| 字段 | token 种类 |
|---|---|
| `syn_keyword` | 关键字、标题 |
| `syn_string` | 字符串 |
| `syn_number` | 数字 |
| `syn_comment` | 注释（渲染为斜体） |
| `syn_function` | 函数名、链接 |
| `syn_type` | 类型 |
| `syn_constant` | 常量 |
| `syn_builtin` | 内建 |
| `syn_decorator` | 装饰器 |
| `syn_operator` | 运算符 |
| `syn_property` | 属性 |

### 元信息

| 字段 | 说明 |
|---|---|
| `name` | 唯一名称，用于 `:theme <name>` 切换 |
| `label` | 显示名 |
| `dark` | 是否深色主题 |
| `extra` | 自由元数据字典，保留给用户主题使用 |

---

## 6. 查看已注册主题

- 运行时：`:theme` 不带参数，在消息栏列出所有已注册主题名。
- 命令面板：搜索 `theme` 可找到 `:theme` 命令并按 `Tab` 补全主题名。
