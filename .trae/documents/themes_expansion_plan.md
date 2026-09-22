# 主题扩展计划：One / Gruvbox 内置 + Dracula / Ayu 主题模板

> **实施状态（2026-09-22 核对）：✅ 已实现（§5 版本号部分已过时）。**
>
> - 内置已由 4 套扩为 **8 套**：Catppuccin 4 + `onedark` / `onelight` /
>   `gruvbox-dark` / `gruvbox-light`（`yate/editor_view/theme.py`，工厂
>   `_catppuccin` / `_one_family` / `_gruvbox`）。
> - 模板已随包：`yate/resources/theme_examples/dracula_theme.example`、
>   `ayu_theme.example`（不自动加载，改名 `*.py` 后由默认目录扫描注册）；
>   `tests/test_theme_palettes.py` 覆盖内置色值与模板 exec 校验。
> - **§5 的版本号 0.1.1（双写）已过时**：`pyproject.toml` 已改
>   `dynamic = ["version"]`，版本唯一来源是 `yate/__init__.py`（当前 **0.2.4**），
>   发布不再双写。
> - 后续演进：主题已进一步接入 Textual 主题桥，使所有覆盖屏跟随当前 yate 主题
>   （见 `overlay_theme_consistency_plan.md`）。

## 与当前实现的差异（回写，2026-09-22）

- **§1「现状」是实施前快照**：当前内置主题为 **8 套**（`mocha` / `frappe` /
  `macchiato` / `latte` / `onedark` / `onelight` / `gruvbox-dark` /
  `gruvbox-light`），另有 `yate/resources/theme_examples/dracula_theme.example`
  与 `ayu_theme.example` 两份模板。
- **§5 版本号已作废**：`pyproject.toml` 现为 `dynamic = ["version"]`
  （hatchling regex 读 `yate/__init__.py`），**不再双写**；当前版本 **0.2.4**。
  发布只改 `yate/__init__.py`（见 `changelog_plan.md` / `release_tool_plan.md`）。
- **§4.2 打包**：模板已由 hatchling 自动入 wheel —— `pyproject.toml` 的 wheel
  注释明确列出 `resources/theme_examples/*.example`。
- **§4.1 模板安装**：手动拷贝仍有效，但更推荐 `yate --setup-defaults`
  一键安装（见 `setup_defaults_plan.md`）。
- **主题进一步接入 Textual 主题桥**：`theme.py` 新增 `TEXTUAL_THEME_PREFIX` /
  `textual_theme_name` / `validate_theme` / `to_textual_theme`，
  `register_theme` 会拒绝非法颜色（见 `overlay_theme_consistency_plan.md`）。

> 主题分两类交付：
>
> - **内置**（`editor_view/theme.py` 的 `THEMES`，随 import 注册）：
>   `onedark`、`onelight`、`gruvbox-dark`、`gruvbox-light`；
> - **主题模板**（随包发布的 `*.theme.example`）：
>   `dracula_theme.example`（Dracula）与 `ayu_theme.example`
>   （ayu-dark / ayu-mirage / ayu-light）。模板**不自动注册**；
>   用户拷贝到 `~/.yate/themes/` 并改名为 `*.py` 后，yate 现有的默认
>   主题目录扫描会自动加载注册——无需任何新增加载逻辑。
>
> 同时版本号 `0.1.0 → 0.1.1`。默认主题仍为 `mocha`，本计划不改默认值。

---

## 1. 现状（基于代码事实）

| 事实 | 证据 |
|------|------|
| 主题 = chrome 配色 + 语法色板的 frozen dataclass | [theme.py:29](yate/editor_view/theme.py#L29) `Theme`（33 个颜色字段 + `extra`） |
| 内置 4 套 Catppuccin，mocha 默认 | [theme.py:202-209](yate/editor_view/theme.py#L202-L209) `THEMES` / `DEFAULT_THEME` |
| 内置构造范式 | `_catppuccin(name, label, dark, palette_dict)` 工厂 + 原始色板 dict |
| 外部主题加载机制已完备 | `load_theme_file()` exec 单个文件；`load_theme_paths()` 对目录只 glob **`*.py`**（下划线开头跳过）；命名空间注入 `Theme`/`register_theme()`；文件出错只记录不崩溃 |
| 默认扫描目录（无需配置） | [cli.py:175-178](yate/cli.py#L175-L178)：`./themes`、`~/.yate/themes` |
| 加载优先级（本计划不变） | 内置 < 默认目录 < yaterc `theme_dirs` < `--theme-dir` |
| yaterc 命名空间同样注入 register_theme | [config.py:163](yate/config.py#L163) |
| 随包非代码资源的既定位置 | `yate/resources/`（manual md、font config）；两个 PyInstaller spec 整目录打包 resources，wheel 自动包含 |
| 无独立主题测试文件 | 主题断言散在 test_config.py / test_cli.py |
| 版本双写 | `yate/__init__.py` 与 `pyproject.toml` 均为 `0.1.0` |

---

## 2. 决策点（如不认可请在审阅时指出）

1. **Gruvbox 出 dark + light 两套**（`gruvbox-dark` / `gruvbox-light`），
   与 One Dark/Light 成对；只做暗色可直接删一套。
2. **Dracula/Ayu 不进内置注册表，也不增加任何加载代码**。它们以
   `*.theme.example` 模板形式放在 `yate/resources/theme_examples/`，
   随 wheel / PyInstaller 发布；用户拷贝改名为 `*.py` 后由现有默认目录
   扫描自动加载。这保证：① 不拷贝就零副作用、不出现在 `:theme` 列表；
   ② 模板即官方教学范例，演示"纯公开 API 自定义主题"。
3. **模板文件两个**：`dracula_theme.example`（注册 1 套）、
   `ayu_theme.example`（一个文件注册 3 套，演示单文件多注册）。
4. Ayu 系列 = `ayu-dark` / `ayu-mirage` / `ayu-light`；Dracula 只出
   经典色，Soft 等变体留后续。
5. 默认主题不变（`mocha`）。

---

## 3. 内置主题设计（theme.py）

### 3.1 构造方式

沿用"原始色板 dict + 家族工厂"范式，每家一个工厂函数，保留上游色名、
注释附调色板出处：

```python
def _one_family(name, label, dark, p)   # onedark / onelight 共用语义槽位
def _gruvbox(name, label, dark, p)      # gruvbox dark/light 共用语义槽位
```

色板 dict 只放上游原色，工厂映射到 `Theme` 的 33 个字段；mode chip、
match、on_accent 等无上游对应的槽位按家族语义推导，规则写入 docstring。

### 3.2 色板（实现时以上游链接为准做最终核对）

**One Dark**（Atom One Dark）：bg `#282c34`、panel `#21252b`、surface
`#2c313a`、border `#3a3f4b`、selection `#3e4451`、fg `#abb2bf`、
fg_dim `#5c6370`、fg_muted `#636d83`、fg_bright `#c8ccd4`、accent
`#61afef`、accent2 `#c678dd`、green `#98c379`、yellow `#e5c07b`、red
`#e06c75`、orange `#d19a66`、cyan `#56b6c2`、on_accent `#282c34`。

语法映射：keyword `#c678dd`、string `#98c379`、number `#d19a66`、
comment `#5c6370`（斜体由 `syntax_style` 统一处理）、function
`#61afef`、type `#e5c07b`、constant `#d19a66`、builtin `#e06c75`、
decorator/operator `#56b6c2`、property `#e06c75`。
mode chips：normal blue / insert green / visual purple / command orange。

**One Light**（Atom One Light）：bg `#fafafa`、panel/surface `#f0f0f1`、
border `#d4d4d4`、selection `#e5e5e6`、fg `#383a42`、fg_dim `#a0a1a7`、
fg_muted `#696c77`、fg_bright `#23252b`、accent `#4078f2`、accent2
`#a626a4`、green `#50a14f`、yellow `#c18401`、red `#e45649`、orange
`#986801`、cyan `#0184bc`、on_accent `#ffffff`；语法槽位与暗色对称。

**Gruvbox Dark Medium / Light Medium**
（<https://github.com/morhetz/gruvbox#palette>）：

| 角色 | dark | light |
|---|---|---|
| bg | `#282828` | `#fbf1c7` |
| panel / surface | `#3c3836` | `#ebdbb2` |
| border / selection | `#504945` | `#d5c4a1` |
| fg | `#ebdbb2` | `#3c3836` |
| fg_dim（注释灰） | `#928374` | `#7c6f64` |
| fg_muted | `#a89984` | `#665c54` |
| fg_bright | `#fbf1c7` | `#282828` |
| blue | `#83a598` | `#076678` |
| purple | `#d3869b` | `#8f3f71` |
| green / aqua | `#b8bb26` / `#8ec07c` | `#79740e` / `#427b58` |
| yellow | `#fabd2f` | `#b57614` |
| red / orange | `#fb4934` / `#fe8019` | `#9d0006` / `#af3a03` |
| on_accent | `#282828` | `#fbf1c7` |

语法映射：keyword red、string green、number purple、function green、
type yellow、constant orange、builtin orange、decorator/property aqua、
operator orange；mode chips = blue/green/purple/orange。

### 3.3 注册与文档串

```python
THEMES: dict[str, Theme] = {
    # 既有 Catppuccin 四套 ...
    "onedark": ...,
    "onelight": ...,
    "gruvbox-dark": ...,
    "gruvbox-light": ...,
}
```

label：`One Dark` / `One Light` / `Gruvbox Dark` / `Gruvbox Light`；
更新模块 docstring（不再只描述 Catppuccin）。

---

## 4. 主题模板：`yate/resources/theme_examples/`

### 4.1 文件与加载原理

```
yate/resources/theme_examples/
  dracula_theme.example     # register_theme(Theme(...))  → dracula
  ayu_theme.example         # register_theme(...) × 3     → ayu-dark/mirage/light
```

- 文件内容是**普通 Python 主题文件**，与用户放到 `~/.yate/themes/` 的
  文件完全同构；只依赖加载器注入的 `Theme` / `register_theme()`
  （参考 [themes.zh.md](yate/docs/themes.zh.md#L63)
  已说明的约定），不 import 任何 yate 内部模块；
- `.example` 后缀使目录扫描的 `glob("*.py")` **天然忽略**它们：放在
  resources 里永不自动注册、不出现在 `:theme` 列表，也不影响 `--diag`；
- 用户使用方式（拷贝并改名，此后全自动）：

```powershell
# Windows (PowerShell)
New-Item -ItemType Directory -Force "$HOME\.yate\themes" | Out-Null
Copy-Item <yate资源目录>\theme_examples\dracula_theme.example `
          "$HOME\.yate\themes\dracula.py"
Copy-Item <yate资源目录>\theme_examples\ayu_theme.example `
          "$HOME\.yate\themes\ayu.py"
yate
:theme dracula
```

```bash
# Linux / macOS
mkdir -p ~/.yate/themes
cp <yate资源目录>/theme_examples/dracula_theme.example ~/.yate/themes/dracula.py
cp <yate资源目录>/theme_examples/ayu_theme.example     ~/.yate/themes/ayu.py
```

下次启动时 [cli.py:175](yate/cli.py#L175) 的
默认目录扫描自动加载；想卸载只需删除该 `*.py`。模板顶部注释写明安装
位置与改名要求。

> 资源目录定位：源码/Wheel 安装为
> `<site-packages>/yate/resources/theme_examples/`；PyInstaller
> onedir 为 `<安装目录>/yate/resources/theme_examples/`，onefile 在
> 解包临时目录内。手册给出 `yate --diag` 的 paths 节可查 resources
> 位置（diag 已有 resources 路径行）。

### 4.2 打包

- 两个 PyInstaller spec 已整目录打包 `yate/resources`，**spec 零改动**；
- wheel 由 hatchling 自动收包内非代码文件（需在验证步骤实际构建确认
  `.example` 后缀也被收入，若被过滤则在 pyproject 加
  `artifacts`/force-include 配置）；
- 不新增任何 Python 模块、不改 cli.py / config.py / 加载优先级。

### 4.3 Dracula 色板（dracula_theme.example）

bg `#282a36`、panel `#21222c`、surface `#44475a`、border/selection
`#44475a`、fg `#f8f8f2`、fg_dim `#6272a4`、fg_muted `#7b88a8`、
fg_bright `#ffffff`、accent cyan `#8be9fd`、accent2 purple `#bd93f9`、
green `#50fa7b`、yellow `#f1fa8c`、red `#ff5555`、orange `#ffb86c`、
pink `#ff79c6`、on_accent `#282a36`。
语法：keyword/operator/decorator pink、string yellow、number/constant
purple、comment `#6272a4`、function green、type/property cyan、builtin
red。

### 4.4 Ayu 色板（ayu_theme.example，注册 3 套）

| 角色 | ayu-dark | ayu-mirage | ayu-light |
|---|---|---|---|
| bg | `#0f1419` | `#1f2430` | `#fafafa` |
| panel | `#0b0e13` | `#191e2a` | `#f3f4f5` |
| surface | `#1a1f29` | `#232834` | `#f0f0f0`（核对上游） |
| fg | `#bfbdb6` | `#cbccc6` | `#5c6166` |
| fg_dim | `#626a73` | `#5c6773` | `#a0a4ab` |
| blue | `#59c2ff` | `#73d0ff` | `#399ee6` |
| purple | `#dfbfff` | `#d4bfff` | `#a37acc` |
| green/teal | `#95e6cb` | `#7fd962` | `#86b300`/`#4cbf99` |
| yellow | `#ffb454` | `#ffcc66` | `#ff9940` |
| red/orange | `#ff3333`/`#ff8f40` | `#f28779`/`#ffad66` | `#f07178`/`#fa8d3e` |

实现要求：以 [ayu-colors](https://github.com/ayu-theme/ayu-colors)
当前色值逐槽核对，上表确定语义映射方向、不以记忆值为准；三套主题语法
槽位映射一致、只换色值；`dark` 标志 dark/mirage 为 True、light 为 False。

### 4.5 模板文件示例骨架

```python
# Dracula theme for yate -- copy this file to:
#   ~/.yate/themes/dracula.py                  (Linux/macOS)
#   %USERPROFILE%\.yate\themes\dracula.py      (Windows)
# 拷贝后必须是 .py 后缀才会被默认目录扫描自动加载
# Palette: https://draculatheme.com/contribute#color-palette

register_theme(Theme(
    name="dracula",
    label="Dracula",
    dark=True,
    bg="#282a36",
    # ... 33 个字段完整填写
))
```

---

## 5. 版本号 0.1.1

| 文件 | 改动 |
|------|------|
| [yate/__init__.py](yate/__init__.py#L11) | `__version__ = "0.1.1"` |
| [pyproject.toml](pyproject.toml#L7) | `version = "0.1.1"` |

两处都改（dynamic-version 改造尚未落地）。验证 `yate --version`。

---

## 6. 文档更新

| 文件 | 内容 |
|------|------|
| `yate/docs/themes.zh.md` / `themes.en.md` | 开头改为"内置 8 套（Catppuccin 4 + One/Gruvbox 4）+ 官方主题模板（Dracula/Ayu）"；第 2 节增加"方式 E：从随包模板安装"，给出拷贝/改名命令与"`.example` 不加载、`.py` 才加载"的说明；第 4 节引用模板源码作为完整自定义范例 |
| `yate/resources/manual.zh.md` / `manual.en.md` | 10.3 / 11 节主题清单同步，补模板安装步骤 |
| `README.md` / `README.zh.md` | 主题描述行更新为 8 套内置 + 模板扩展 |
| `yate/yaterc.example` | 注释中的主题名列举补全 |
| `yate/editor_view/theme.py` | 模块 docstring 更新 |
| `.trae/documents/themes_expansion_plan.md` | 本文档 |

`--diag` 无需改动：内置 8 套始终出现在 themes 节；模板只有用户拷贝后
才出现，诊断所见即实际加载。

---

## 7. 实施步骤

1. 版本号两处改 0.1.1。
2. theme.py：One/Gruvbox 色板 dict + 两个工厂，注册 4 套内置主题，
   更新 docstring。
3. 新建 `yate/resources/theme_examples/dracula_theme.example`、
   `ayu_theme.example`（含安装注释、完整 33 字段；Ayu 色值核对上游）。
4. 新增测试（第 8 节），全量 pytest + pyright strict。
5. 双语文档、手册、README、yaterc.example 同步。
6. 手动 TUI 核对：内置 8 套逐一 `:theme <name>`；拷贝模板为 `.py` 后
   dracula/ayu 4 套出现在列表并可切换；删除文件后消失。
7. 打包核对：构建 wheel 与 onedir/onefile，确认 `.example` 在包内；
   从包内路径拷贝模板到 `~/.yate/themes` 后能自动加载。

---

## 8. 测试方案（新增 `tests/test_theme_palettes.py`）

**内置主题**：

- 遍历内置 8 套：所有 `Theme` 字段非空、颜色匹配
  `^#[0-9a-f]{6}$`、`name` 等于注册表键、`dark` 为 bool；
- 每套对全部 `SYNTAX_KINDS` 调 `syntax_color()`/`syntax_style("comment")`
  返回合法颜色且注释为斜体；
- `set_theme("onedark")` 生效；未知主题 KeyError 消息含全部 8 个内置名；
  测试末尾恢复 `mocha`（沿用 test_config.py 全局态恢复纪律）。

**主题模板**（直接从 resources 读取，不复制进任何加载目录）：

- 两个 `.example` 文件存在、是 UTF-8 文本、包含 `register_theme(Theme(`；
- 用与 `load_theme_file` 相同的注入命名空间 `exec` 模板源码（在测试用
  注册表里收集，或直接用真实 `register_theme` 并在 tearDown 清理键），
  断言注册出 `dracula` 与 `ayu-dark/mirage/light`，且每套通过同样的
  色值格式/字段完整性校验；
- **惰性验证**：`load_theme_paths` 直接扫模板所在目录时不注册任何东西
  （glob `*.py` 不匹配 `.example`）；
- **端到端**：TemporaryDirectory 中把模板**复制为 `*.py`**，
  `load_theme_paths([dir], errors)` 后 4 套主题注册成功、errors 为空；
  复制为非 `.py` 后缀则不注册；
- **隔离纪律**：模板源码不出现 `from yate` / `import yate`（只靠注入
  名称），保证与用户主题文件环境完全一致。

**版本**：`yate.__version__ == "0.1.1"` 且 pyproject.toml 含
`version = "0.1.1"`。

```powershell
python -m pytest tests/test_theme_palettes.py tests/test_config.py tests/test_cli.py -v
python -m pytest tests/ -v
```

---

## 9. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `yate/editor_view/theme.py` | 修改 | One/Gruvbox 色板与工厂、注册 4 主题、docstring |
| `yate/resources/theme_examples/dracula_theme.example` | 新增 | Dracula 模板（含安装注释），拷贝为 `.py` 后自动加载 |
| `yate/resources/theme_examples/ayu_theme.example` | 新增 | ayu-dark/mirage/light 三主题模板 |
| `yate/__init__.py` | 修改 | 版本 0.1.1 |
| `pyproject.toml` | 修改 | 版本 0.1.1（若 wheel 漏收 `.example`，在此补 force-include） |
| `tests/test_theme_palettes.py` | 新增 | 内置色板、模板 exec 校验、惰性/端到端加载、版本测试 |
| `yate/docs/themes.zh.md`、`themes.en.md` | 修改 | 8 内置 + 模板安装方式 E |
| `yate/resources/manual.zh.md`、`manual.en.md` | 修改 | 主题清单与模板安装步骤 |
| `README.md`、`README.zh.md`、`yate/yaterc.example` | 修改 | 主题措辞/名单 |
| `.trae/documents/themes_expansion_plan.md` | 修改 | 本文档（改为模板方案） |

明确**不新增/不修改**：任何主题加载器代码（cli.py、config.py、
theme.py 的 load_* 部分）、PyInstaller spec、Python 包结构。

---

## 10. 后续可扩展方向

- 增加 `solarized_theme.example`、Dracula Soft 等更多模板；
- `yate --install-theme <name>` 一键把随包模板复制到 `~/.yate/themes`
  （属新 CLI 功能，本计划不做）；
- 主题预览命令 `:theme-preview`（示例代码渲染各主题快照）；
- 模板与内置成熟后可互相平移（内置 ↔ 模板只改交付位置）。
