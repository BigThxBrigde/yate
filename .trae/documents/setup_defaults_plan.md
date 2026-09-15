# `--setup-defaults` / `--cleanup-defaults` 用户配置初始化与清理计划

> 新增两个 CLI 子功能（均为"执行后退出"，不启动 TUI）：
>
> - `yate --setup-defaults`：创建 `~/.yate/`，发放默认 `yaterc`，并把
>   随包的主题、扩展示例以 **`.example` 原后缀**拷贝到
>   `~/.yate/themes/`、`~/.yate/extensions/`——保持 `.example` 即不会被
>   自动扫描加载，用户改名 `*.py` 后才激活；
> - `yate --cleanup-defaults`：删除 `~/.yate/` 下的配置内容
>   （yaterc、themes、extensions），默认保留 `data/` 崩溃日志。

---

## 1. 现状（基于代码事实）

| 事实 | 证据 |
|------|------|
| 用户配置根目录 | `~/.yate/`，[config.py:115-117](yate/config.py#L115-L117) `user_config_path()` = `~/.yate/yaterc` |
| 默认 yaterc 加载 | [config.py:136](yate/config.py#L136) `default_rc_paths()`：用户 rc 存在才加载；缺失不是错误 |
| 主题默认扫描目录 | [cli.py:175-178](yate/cli.py#L175-L178)：`./themes`、`~/.yate/themes`；目录扫描只 glob `*.py`，`.example` 天然不加载 |
| 扩展默认扫描目录 | [app.py:1805-1811](yate/app.py#L1805-L1811)：`./extensions`、`~/.yate/extensions`，只加载 `*.py` |
| 随包 yaterc 模板 | `yate/yaterc.example`（包根；含生效默认值 keymap/theme + 大量注释教学，适合作为初始 rc） |
| 随包主题模板（已存在） | `yate/resources/theme_examples/dracula_theme.example`、`ayu_theme.example` |
| 随包扩展示例 | `yate/extensions/example_ext.py.example`、`yatesh_syntax.py.example`（同目录还有真实内置扩展 `*.py`，**绝不能拷**） |
| 包资源统一入口 | [paths.py](yate/paths.py) `package_root()`（支持 PyInstaller frozen）、`bundled_extensions_dir()` |
| `~/.yate/data/` 是运行时数据 | [crash.py:53-54](yate/crash.py#L53-L54)：崩溃日志 `crash-*.err`，健康退出自动清理；属诊断证据而非配置 |
| CLI 既有"执行后退出"范式 | `--install-font`、`--version`、`--changelog`、`--diag`（[cli.py](yate/cli.py)），早返回、不构造 YateApp |
| 备份惯例 | [fonts.py:379](yate/services/fonts.py#L379) 写配置前留 `*.yate-bak` |
| 服务层归属 | 一次性用户环境操作在 `yate/services/`（fonts.py 同构） |
| `--diag` 已展示 user dir / extensions 路径 | diagnostics.py 231/366 行；setup 后诊断自然反映，无需改诊断代码 |

---

## 2. 口径冻结

1. **选项命名**：`--setup-defaults`、`--cleanup-defaults`，二者互斥
   （argparse mutually exclusive group；同传报错退出码 2）。
2. **setup 产物布局**：

   ```text
   ~/.yate/
     yaterc                              # 包内 yaterc.example 的副本
     themes/
       dracula_theme.example             # 保持 .example，不加载
       ayu_theme.example
     extensions/
       example_ext.py.example
       yatesh_syntax.py.example
     data/                               # setup 不创建、不触碰
   ```

   激活方式：改名为 `*.py`（主题进 `~/.yate/themes/`，扩展进
   `~/.yate/extensions/`），下次启动由**现有**默认扫描自动加载——
   不新增任何加载逻辑。
3. **覆盖策略（setup 幂等，可随时重跑/随版本升级重跑）**：
   - `yaterc`：已存在则**跳过**并提示（用户配置永不静默覆盖）；
     加 `--force` 时才覆盖，覆盖前把旧文件备份为
     `yaterc.yate-bak`（沿用 fonts 的 `.yate-bak` 惯例，已存在备份不
     再覆盖，保留最早版本）；
   - 四个 `*.example` 模板：视为 yate 托管文件，**始终刷新覆盖**
     （升级 yate 后重跑 setup 可更新模板；用户定制应改名 `*.py` 后
     再改，`.example` 不是定制入口，这一点写入文件头注释与文档）；
   - 目录：缺则建，存在不动。
4. **cleanup 删除范围**：
   - 默认删除 `yaterc`、`themes/`、`extensions/`（含用户改名为 `*.py`
     的全部内容——这是"清除配置"的语义）；
   - **保留 `data/`**（崩溃诊断日志不是配置）；加 `--include-data`
     才连同 `data/` 删除；
   - 其他非 yate 创建的文件/目录（未来扩展或用户自建）：默认**不动**，
     仅在输出中列为 "unknown, preserved"；
   - 若 `~/.yate/` 清理后为空目录则一并删除；非空则保留。
5. **危险操作确认**：cleanup 在 stdin 为 TTY 时提示
   `proceed? [y/N]`，非 y 即取消（退出码 0，打印 cancelled）；
   stdin 非 TTY（脚本/CI）时无 `--force` 则拒绝执行（退出码 2）；
   `--force` 跳过确认。setup 不需要确认（只写/刷新，不删除）。
6. **无网络、零新依赖**；仅标准库 `shutil` / `pathlib` / `sys` /
   `dataclasses`。
7. **可测性**：服务层函数接收显式 `base_dir` 参数（默认
   `Path.home()/".yate"`），测试用 TemporaryDirectory，不 monkeypatch
   `Path.home`（也避免与 `crash.install()` 的真实 home 写入互相干扰）。

---

## 3. 模块设计：`yate/services/user_setup.py`

命名语义：用户目录的一次性初始化/清理（不叫 bootstrap/ops 等泛名）。

### 3.1 数据结构

```python
@dataclass(frozen=True)
class SetupReport:
    base_dir: Path
    created_dirs: list[str]      # 相对路径，如 "themes"
    installed_rc: bool           # 本次是否写入 yaterc
    rc_skipped: bool             # 已存在且未 --force
    rc_backup: Path | None       # --force 覆盖时的备份路径
    refreshed_templates: list[str]
    skipped_templates: list[str] # 源缺失（安装不完整）时

@dataclass(frozen=True)
class CleanupReport:
    base_dir: Path
    removed_files: list[str]
    removed_dirs: list[str]
    preserved: list[str]         # data/、未知条目
    base_removed: bool           # ~/.yate 空目录是否已删
    cancelled: bool = False
```

### 3.2 模板清单（单一事实源）

```python
# (包内源（相对 package_root()）, 目标相对 ~/.yate 的路径)
_TEMPLATE_MAP = (
    ("resources/theme_examples/dracula_theme.example", "themes/dracula_theme.example"),
    ("resources/theme_examples/ayu_theme.example",     "themes/ayu_theme.example"),
)
# 扩展示例从 bundled_extensions_dir() 动态 glob("*.py.example")，
# 避免硬编码文件名、且天然只拿 .example（同目录真实内置 .py 永不入选）。
```

`yaterc` 固定来自 `package_root() / "yaterc.example"`。
所有源读取走 [paths.py](yate/paths.py)，
PyInstaller onefile/onedir 自动正确。

### 3.3 函数

```python
def setup_defaults(*, force: bool = False,
                   base_dir: Path | None = None) -> SetupReport: ...

def cleanup_defaults(*, force: bool = False, include_data: bool = False,
                     base_dir: Path | None = None,
                     stdin=None, stdout=None) -> CleanupReport: ...
```

- 所有写盘操作捕获 `OSError`：单文件失败记录到 report 的 errors 列表
  （数据类加 `errors: list[str]`），其余继续；最终 CLI 据 errors 决定
  退出码（setup 有错误 → 1）；
- 文件拷贝用 `shutil.copyfile`（不复制权限位，模板是只读文本；
  yaterc 拷贝后保持普通文件权限）；
- cleanup 用 `unlink()` / `shutil.rmtree()`；删除前列好清单，确认后
  一次性执行，不在确认前删任何东西；
- 确认提示文本明确列出将删条目、保留条目与 `--include-data` 含义。

### 3.4 CLI 接线（cli.py）

argparse 增加互斥组与选项：

```python
group = parser.add_mutually_exclusive_group()
group.add_argument("--setup-defaults", action="store_true",
                   help="create ~/.yate with a default yaterc and bundled "
                        "theme/extension *.example templates, then exit")
group.add_argument("--cleanup-defaults", action="store_true",
                   help="remove ~/.yate configuration (yaterc, themes, "
                        "extensions; data/ kept unless --include-data), then exit")
parser.add_argument("--force", action="store_true",
                    help="with --setup-defaults: overwrite an existing yaterc "
                         "(backup kept); with --cleanup-defaults: skip the "
                         "interactive confirmation")
parser.add_argument("--include-data", action="store_true",
                    help="with --cleanup-defaults: also delete ~/.yate/data")
```

`main()` 中放在 `--install-font` 同层（配置解析之前、TUI import 之前），
打印人类可读报告后退出：

- setup 成功 0（rc 因已存在被跳过仍为 0，输出里注明）；有 IO 错误 1；
- cleanup：取消 0；非 TTY 无 --force 2；完成 0；IO 错误 1；
- `--include-data` 与 setup 同传时忽略（help 文本已限定语义），或在
  argparse 层不做强制，代码内仅 cleanup 读取。

`crash.install()` 仍在最前运行：它会创建 `~/.yate/data/`，因此 cleanup
后 data 目录被重新创建属预期行为——cleanup 逻辑上保留/删除的是执行前
状态，报告中说明 "data/ is recreated on the next launch"。

### 3.5 输出示例

```text
$ yate --setup-defaults
yate user directory: C:\Users\i77\.yate
  created  themes/
  created  extensions/
  installed yaterc  (from yaterc.example)
  refreshed themes/dracula_theme.example
  refreshed themes/ayu_theme.example
  refreshed extensions/example_ext.py.example
  refreshed extensions/yatesh_syntax.py.example

edit yaterc to customize; rename a *.example to *.py to activate it.

$ yate --setup-defaults        # 第二次
  yaterc already exists (skipped; use --force to replace, backup kept)
  refreshed themes/dracula_theme.example
  ...

$ yate --cleanup-defaults
about to remove configuration under C:\Users\i77\.yate:
  yaterc
  themes/        (4 files)
  extensions/    (2 files)
preserved: data/ (crash logs; --include-data to remove)
proceed? [y/N]: y
removed. data/ is recreated automatically on the next launch.
```

---

## 4. 实施步骤

1. 新建 `yate/services/user_setup.py`：数据类、模板清单、
   setup/cleanup 函数（含确认逻辑与错误收集）。
2. cli.py：互斥组 + `--force` / `--include-data` + 两个早返回分支、
   epilog 示例。
3. 新增 `tests/test_user_setup.py`；扩展 `tests/test_cli.py`
   （第 5 节）。
4. 全量 pytest + pyright strict。
5. 文档同步（第 6 节）。
6. 手动验证（PowerShell + 临时 `HOME`/`USERPROFILE` 或直接当前用户
   小心中 cleanup 确认；建议用 `--yaterc` 无关的隔离环境变量方式——
   服务层测试已覆盖真实 IO，手动只验 CLI 表面）。

---

## 5. 测试方案（`tests/test_user_setup.py` + cli 用例）

服务层（全部用 `tmp_path` 作 `base_dir`，模板源用真实包资源）：

**setup**：

- 空目录执行后：`yaterc` 内容与包内 `yaterc.example` 字节一致；
  `themes/`、`extensions/` 下 4 个 `.example` 存在；无 `*.py` 被拷入
  extensions（断言 python_lsp/csharp_highlight 未出现）；无 `data/`；
- 幂等：二次执行不报错；`yaterc` 标记 skipped；模板内容刷新
  （篡改模板文件后重跑恢复为包内版本）；
- `--force`：自定义 yaterc 被覆盖，旧内容出现在 `yaterc.yate-bak`；
  再次 force 不覆盖已有备份；
- 源缺失：模拟某模板源不存在（monkeypatch 模板清单）→ report.errors
  非空、其余文件照常写入；
- 目标目录不可写（权限错误在 Windows 难造：用一个已存在的**文件**
  占用 `themes` 路径触发 OSError）→ 收集错误不抛异常。

**cleanup**：

- 预置 yaterc + themes/*.example + 一个用户改名的 themes/dracula.py +
  extensions/* + data/crash-x.err：默认清理后前三者全删、
  `data/crash-x.err` 保留；
- `include_data=True`：data 一并删除；`~/.yate` 变空则基目录删除，
  `base_removed=True`；
- 未知条目保留：手工建 `~/.yate/notes.txt`，cleanup 后仍在，出现在
  preserved，基目录不删；
- 确认逻辑：传入假 stdin（StringIO）：`"y\n"` 执行、`"n\n"`/`""`
  cancelled=True 且文件仍在；非 TTY 无 force → 抛/返回拒绝，CLI 层
  退出码 2（服务层用一个明确异常 `ConfirmationRequiredError`，CLI
  捕获转退出码 2）；
- 不存在的 `~/.yate`：cleanup 返回空报告，不报错（退出 0）。

**CLI**（test_cli.py，patch `user_setup.setup_defaults` 等函数避免动
真实 home）：

- `main(["--setup-defaults"])` 返回 0、函数被调、YateApp 未构造；
- `--setup-defaults --cleanup-defaults` → SystemExit 码 2；
- `--cleanup-defaults --force` 透传 `force=True`；
- `--include-data` 透传；
- help 文本含两个新选项。

```powershell
python -m pytest tests/test_user_setup.py tests/test_cli.py -v
python -m pytest tests/ -v
```

---

## 6. 文档更新

| 文件 | 内容 |
|------|------|
| `yate/resources/manual.zh.md` / `manual.en.md` | 配置章节开头加"快速初始化"：`yate --setup-defaults` 一键创建目录/模板、改名激活机制、`--cleanup-defaults` 与 data 保留口径 |
| `yate/yaterc.example` | 头部注释补一行：可用 `yate --setup-defaults` 自动安装本文件 |
| `yate/docs/themes.zh.md` / `themes.en.md` | "方式 E：模板安装"的手工拷贝命令前加快捷方式 `yate --setup-defaults`（手工命令保留，说明其等价） |
| `yate/docs/yaterc.zh.md` / `yaterc.en.md` | 配置文件位置章节补 setup/cleanup |
| `README.md` / `README.zh.md` | 快速开始增加初始化命令一行 |
| `yate/cli.py` epilog | 加 `yate --setup-defaults` / `--cleanup-defaults` 示例 |
| `.trae/documents/setup_defaults_plan.md` | 本文档 |

模板文件自身（dracula/ayu `.example`、extensions `*.example`）头部注释
补一句"由 `yate --setup-defaults` 安装；重命名为 .py 激活；本文件会在
升级重跑 setup 时被刷新覆盖，请勿在此文件中定制"。

---

## 7. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `yate/services/user_setup.py` | 新增 | setup/cleanup 服务层、模板清单、报告数据类、确认异常 |
| `yate/cli.py` | 修改 | 互斥选项、`--force`/`--include-data`、早返回分支、epilog |
| `tests/test_user_setup.py` | 新增 | 服务层全部场景 |
| `tests/test_cli.py` | 修改 | 参数互斥/透传/退出码 |
| `yate/resources/theme_examples/*.example` | 修改 | 头部补安装/刷新说明注释 |
| `yate/extensions/example_ext.py.example`、`yatesh_syntax.py.example` | 修改 | 同上 |
| `yate/yaterc.example` | 修改 | 头部补 setup 提示 |
| `manual.zh/en.md`、`themes.zh/en.md`、`yaterc.zh/en.md`、`README(.zh).md` | 修改 | 文档同步 |
| `.trae/documents/setup_defaults_plan.md` | 新增 | 本文档 |

**不改动**：主题/扩展/yaterc 的任何加载逻辑（cli.py 现有默认扫描、
config.py、app.py 扩展加载）、paths.py、PyInstaller spec、`~/.yate/data`
写入逻辑。

---

## 8. 后续可扩展方向

- `--setup-defaults --theme dracula`：setup 后直接把某模板改名激活并
  写入 yaterc（本计划不做，保持"改名即激活"的简单心智）；
- cleanup 支持 dry-run（只打印将删内容）；
- `yate --install-theme <name>` 单模板安装（与主题计划第 10 节呼应）；
- setup 报告写入 `~/.yate/data/setup.log` 便于排查安装问题。
