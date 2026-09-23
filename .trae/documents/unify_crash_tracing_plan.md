# 崩溃与追踪日志统一方案 —— 已实现设计

> **状态：已实现。** 本文档按当前代码回写：实现集中在单模块 **`yate/logs.py`**，
> 调用方直接导入两个单例。中途曾出现过的两个薄壳（`yate/crash.py` / `yate/tracing.py`）
> 已在最终版**删除**，历史见文末「与初稿的差异」。
>
> 姊妹文档：`crash_diagnostic_plan.md`（崩溃诊断 `crash-*.err`）、
> `logs_impl_plan.md`（运行日志 `YATE_TRACE`）。
>
> **2026-09-22 复核确认**：本方案仍与代码一致——`yate/logs.py` 是唯一实现，
> 暴露 `crash` / `tracing` 两个单例；`yate/crash.py`、`yate/tracing.py` 不存在；
> `yate/logs.py` 仍保持叶子（只依赖标准库 + `yate.__version__`）；
> `tests/test_crash.py` / `tests/test_tracing.py` 单例直连，`tests/test_cli.py`
> 的 patch 目标为 `yate.logs.crash.*`。

## 目标

把原先的 `yate/crash.py` 与 `yate/tracing.py` 合并为单一日志模块
**`yate/logs.py`**，暴露 `crash` 与 `tracing` 两个**互不引用的单例对象**，
调用方直接：

```python
from yate.logs import crash, tracing

crash.install()                            # ~/.yate/data/crash-*.err
tracing.install(yate_trace=True)           # ~/.yate/data/logs/yate-*.log
log = tracing.get_logger(__name__)
```

两个服务除了少量模块级辅助函数之外不共享任何东西：无循环导入、两个类之间无互相引用、
无 `TYPE_CHECKING` 守卫、无 `YateConfig` 引用。

## 调用方式（唯一一条规则）

| 需要什么 | 怎么拿 |
|----------|--------|
| **服务对象**（生命周期 + 状态） | `from yate.logs import crash, tracing` → `crash.install()`、`tracing.get_logger(...)`、`crash.err_file`、`tracing.root_logger` |
| **模块级常量** | `from yate.logs import LEVEL_NAMES, DEFAULT_LEVEL`（`LOGGER_NAME`、`TRUE_VALUES`、`LOG_PREFIX` 等同理） |
| **模块级纯函数** | `from yate.logs import resolve_level, env_trace, env_level, logs_dir, crash_data_dir` |

去掉薄壳后唯一需要适应的语法变化：**常量与纯函数不是单例的成员**，
`tracing.LEVEL_NAMES` / `crash.crash_data_dir()` 这类写法不再成立，改成按名导入：

```python
from yate.logs import LEVEL_NAMES, crash, crash_data_dir

crash_dir = crash_data_dir()
if config.yate_trace_level not in LEVEL_NAMES: ...
```

对象方法（`install` / `uninstall` / `configure` / `get_logger` / `build_err_path` /
`cleanup_on_exit` / `current_crash_file` / `file_handlers` …）与之前完全一样，
`from yate.logs import crash, tracing` 之后即可直接调用。

## 硬约束 —— 全部满足

| # | 约束 | 实现如何满足 |
|---|------|--------------|
| 1 | 统一日志 —— 崩溃与追踪 | 两者都在 `yate/logs.py`，没有任何中间模块 |
| 2 | 新增日志模块并暴露 `crash` / `tracing` 对象 | `yate/logs.py` 末尾 `crash = CrashService()` / `tracing = TracingService()`；一个对象只有一个地址 |
| 3 | 崩溃与追踪功能保持不变 | `install()`、`uninstall()`、`get_logger()`、excepthook 链、`faulthandler` 启用、atexit 清理、日志文件懒创建，**以及两种头部格式**均 1:1 保留（逐字节比对，见 §验证结果） |
| 4 | 无循环依赖 | `yate/logs.py` 只依赖标准库 + `yate.__version__`（叶子模块），位于顶层包目录；见 §为什么模块必须保持叶子 |
| 5 | 崩溃与追踪互相独立 | excepthook 里旧的 `tracing.get_logger("crash").error(...)` 调用**已删除**；两个类除 docstring 外互不提及 |
| 6 | 公共逻辑写成函数 | `warn`、`build_session_header`、`resolve_level`、`env_trace`、`env_level`、`logs_dir`、`crash_data_dir` 均为模块级函数；无 ABC、无基类、无 `@staticmethod` |
| 7 | 彻底去掉 `YateConfig` —— 传两个标量 | `install(yate_trace: Optional[bool], yate_trace_level: Optional[str])`；等级字符串在 `install()` 内部解析为 int。`cli.py` 直接传 `config.yate_trace` / `config.yate_trace_level` |
| 8 | `tracing` 提供与 `install()` 同签名的 `configure()` | `configure(yate_trace=None, yate_trace_level=None) -> None` —— 一行别名，用于 rc 阶段的重新配置 |
| 9 | *（推导）* 调用点只认一个来源 | 全部改为 `from yate.logs import ...`；不再存在"壳 / 实现模块"两套路径 |
| 10 | *（推导）* 两种头部保持逐字节一致 | `build_session_header(*, title, extra_lines, footer_lines)` 能精确复现两种历史布局 |

## 为什么模块必须保持叶子

初稿把实现放在 `yate/services/log_services.py`，并且让薄壳去导入它。这形成了导入环，
因为**导入任何子模块都会先初始化它的父包**：

```
import yate.tracing                                  # 薄壳开始执行
└─ from yate.services.log_services import …
   └─ 先初始化父包 yate.services
      └─ yate/services/__init__.py: from yate.services.extensions import …
         └─ yate/services/extensions.py: 导入 yate.editor_lsp.client
            └─ yate/editor_lsp/__init__.py: from yate.editor_lsp.manager import …
               └─ manager.py: from yate import tracing   ← 薄壳仍在执行中
                  log = tracing.get_logger(__name__)     ← AttributeError
```

实测报错（重构过程中真实出现，也做过刻意的复现）：

```
AttributeError: partially initialized module 'yate.tracing' from '...\yate\tracing.py'
has no attribute 'get_logger' (most likely due to a circular import)
```

最终解法有两条，实施时都做了：

1. **模块放顶层并保持叶子**：`yate/logs.py` 只依赖标准库 + `yate.__version__`。
   于是它可以在任何时刻被任何模块导入，包括正在初始化中的包内部。
2. **彻底不做中间层**：薄壳（它才是那个"被导入到一半"的模块）已删除，
   调用方直接引用单例，环从结构上消失。

以下模块各自作为**首个导入**在新解释器里验证通过：
`yate.logs`、`yate.config`、`yate.cli`、`yate.app`、`yate.services.extensions`、
`yate.diagnostics` —— 全部干净。

## 最终文件布局

```
yate/
├── logs.py                  ← 新增（576 行）实现：常量、纯函数、
│                                    _SessionFileHandler、CrashService、
│                                    TracingService、两个单例
├── cli.py                   ← from yate.logs import crash, tracing
│                               （第二阶段改为 tracing.configure(...)）
├── config.py                ← from yate.logs import DEFAULT_LEVEL, LEVEL_NAMES
├── app.py                   ← from yate.logs import tracing（tracing.get_logger）
├── diagnostics.py           ← from yate.logs import crash, crash_data_dir
├── editor_lsp/manager.py    ← from yate.logs import tracing
└── services/
    ├── __init__.py          ← 无改动
    └── extensions.py        ← from yate.logs import tracing

tests/
├── test_crash.py            ← 改动（199 行）单例直连；patch 打 yate.logs 的模块全局
├── test_tracing.py          ← 改动（278 行）单例直连；常量/函数按名导入
└── test_cli.py              ← 改动（443 行）patch 目标改为 "yate.logs.crash.install" 等
```

## 依赖关系（最终）

```
cli.py ─────────────────────┐
config.py ──────────────────┤
app.py ─────────────────────┤
diagnostics.py ─────────────┼──► yate.logs ──►（仅标准库 + yate.__version__）
editor_lsp/manager.py ──────┤
services/extensions.py ─────┘

yate/logs.py:
  ├── 模块级 —— 常量 + 纯函数（两个类共享）
  │     LOGGER_NAME, LEVEL_NAMES, DEFAULT_LEVEL, TRUE_VALUES, FALSE_VALUES
  │     DATA_DIRNAME, LOG_DIRNAME, LOG_PREFIX, LOG_SUFFIX, ERR_PREFIX, ERR_SUFFIX
  │     warn(), build_session_header(), resolve_level(), env_trace(), env_level(),
  │     logs_dir(), crash_data_dir()
  ├── _SessionFileHandler         （模块私有 —— 仅 TracingService 使用）
  ├── CrashService                （自包含，不引用 TracingService）
  ├── TracingService              （自包含，不引用 CrashService）
  ├── crash = CrashService()      单例
  └── tracing = TracingService()  单例

⚠️  无 ABC。无 TYPE_CHECKING。无 YateConfig。两个类之间无任何导入。
```

## 模块级常量与纯函数

```python
LOGGER_NAME = "yate"
LEVEL_NAMES: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
DEFAULT_LEVEL = "DEBUG"
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})
DATA_DIRNAME = "data"
LOG_DIRNAME = "logs"
LOG_PREFIX = "yate-";  LOG_SUFFIX = ".log"
ERR_PREFIX = "crash-"; ERR_SUFFIX = ".err"


def warn(message: str) -> None:
    """向 stderr 打印 ``yate: <message>``。永不抛异常。"""
    print(f"yate: {message}", file=sys.stderr)


def build_session_header(
    *,
    title: str,
    extra_lines: Optional[Mapping[str, str]] = None,
    footer_lines: Optional[Mapping[str, str]] = None,
) -> str:
    """崩溃报告与追踪日志共用的进程元数据头部。

    布局::

        <title>
        time: ...
        [extra_lines]        # 追踪日志把 pid 放这里（运行标识，紧邻时间）
        cwd: ...
        argv: [...]
        python: ... on ...
        [footer_lines]       # 追踪日志把 trace level 放这里（会话设置）
        ------------------------------------------------------------
    """


def resolve_level(raw: str) -> Optional[int]: ...      # "debug" -> 10，"no" -> None
def env_trace() -> Optional[bool]: ...                 # 解析 YATE_TRACE
def env_level() -> Optional[str]: ...                  # 归一化 YATE_TRACE_LEVEL
def logs_dir() -> Path: ...                            # ~/.yate/data/logs/（自动创建）
def crash_data_dir() -> Path: ...                      # ~/.yate/data/（自动创建）
def _trace_header(level: int) -> str: ...              # 组装头部，供文件 handler 使用
```

外部使用者（与"是否有调用点"对应）：

| 名字 | 模块外调用点 |
|------|--------------|
| `LEVEL_NAMES` / `DEFAULT_LEVEL` | `yate/config.py`（yaterc 等级校验、字段默认值） |
| `crash_data_dir` | `yate/diagnostics.py`、`tests/test_crash.py`（也是 patch 目标） |
| `logs_dir` | `tests/test_tracing.py`（patch 目标） |
| `resolve_level` / `env_trace` / `env_level` | `tests/test_tracing.py` |
| 其余常量 / `warn` / `build_session_header` / `_trace_header` | 仅模块内使用（保留公开是因为它们是本模块的词汇表与共享构造器） |

### 为什么签名是 `title` + `extra_lines` + `footer_lines`

初稿提议 `build_session_header(service_name=..., extra_lines=...)` 加固定正文顺序。
那个形状**无法**复现追踪日志的头部：它带装饰性标题
（`=== yate <version> trace session ===`），并且 `pid` 在**时间戳之后**、
`trace level` 在**环境信息之后** —— 这三点都被 `tests/test_tracing.py` 断言
（`"trace session ==="`、`"trace level: DEBUG"`、`"pid:"`）。把标题作为 `title` 传入、
给两组附加行显式位置，既保留唯一的共享构造函数，也保留历史字节：

* 崩溃 → `build_session_header(title=f"yate {__version__} crash report")`
* 追踪 → `build_session_header(title=f"=== yate {__version__} trace session ===",`
  `extra_lines={"pid": str(os.getpid())},`
  `footer_lines={"trace level": logging.getLevelName(level)})`

## _SessionFileHandler（模块私有）

从旧的 `yate/tracing.py` **原样迁移**，仅把头部调用改走 `_trace_header()`。
名字带下划线：它是 `TracingService.install()` 的内部机件（全库仅两处引用：
定义 + 实例化），换掉它不需要任何外部知会。

* `delay=True` —— 文件在**第一条真正写出的记录**时才创建，所以
  `YATE_TRACE=1 yate --version` 不会在 `~/.yate/data/logs` 留下空壳文件；
* 头部在首次 emit 时直接写入流（不走 logger），无论配置的等级是什么都会出现；
* `OSError` → `handleError()`（日志绝不能把编辑器搞崩）；
* `close()` 会重置 `self._stream`，后续记录会重新打开文件，而不是写进一个已关闭的句柄；
* 懒打开用我们自己的 `_stream` 跟踪，而不是判断 `self.stream is None`（stdlib 的
  `stream` 属性在首次 emit 前根本不存在，各版本 stub 对它是否可空说法不一）。

## CrashService —— 自包含、零依赖

```python
class CrashService:
    def __init__(self) -> None:
        self._err_file: Optional[TextIO] = None
        self._err_path: Optional[Path] = None
        self._crashed: bool = False
        self._original_excepthook: Callable[..., Any] = sys.excepthook

    # 公开只读状态
    @property
    def err_file(self) -> Optional[TextIO]: ...           # 原模块级 _err_file
    @property
    def err_path(self) -> Optional[Path]: ...             # 原模块级 _err_path
    @property
    def had_crash(self) -> bool: ...                      # 原模块级 _crashed
    @property
    def original_excepthook(self) -> Callable[..., Any]: ...

    # 生命周期
    def install(self) -> None: ...                        # 幂等、best-effort
    def uninstall(self) -> None: ...                      # faulthandler.disable() + 清理
    def cleanup_on_exit(self) -> None: ...                # 原 _cleanup_on_exit

    # 辅助
    def build_err_path(self, directory: Path, now: Optional[datetime] = None) -> Path: ...
    def current_path(self) -> Optional[Path]: ...
    def current_crash_file(self) -> Optional[Path]: ...   # 别名，diagnostics.py 在用
    def is_enabled(self) -> bool: ...

    # 私有
    def _write_header(self, handle: TextIO) -> None: ...
    def _excepthook(self, exc_type, exc_value, exc_tb) -> None: ...
```

相对原 `yate/crash.py` 的变化：

| 项 | 处置 |
|----|------|
| excepthook 里的 `tracing.get_logger("crash").error(...)` | **已删除**（硬约束 #5）。excepthook 仍把回溯写进 `.err` 并链回原 hook |
| 模块级 `_err_file` / `_err_path` / `_crashed` / `_original_excepthook` | 变成单例的实例属性，通过 `@property` 暴露为**只读**公开状态 |
| `_err_file_path()` / `_cleanup_on_exit()` / `_excepthook()` | 变成实例方法 `build_err_path()` / `cleanup_on_exit()` / `_excepthook()` |
| `_write_header(handle)` | 改为写 `build_session_header(title=…crash report)`，字节一致 |
| `crash_data_dir()` | 保持**模块级**函数（硬约束 #6），按名导入使用 |
| `install()` 返回类型 | 保持 `None`（硬约束 #3） |

逐位保留的行为：急切打开 + 写头 + flush、
`faulthandler.enable(file=handle, all_threads=True)`、`OSError`/`ValueError` 时回退
stderr、包装 `sys.excepthook` 并链回原 hook、注册 `atexit`、`_crashed` 决定保留文件、
`install()`/`uninstall()` 幂等、健康退出时删除只含头部的报告。

## TracingService —— 懒初始化、默认关闭、零依赖

```python
class TracingService:
    def __init__(self) -> None:
        self._logger = logging.getLogger(LOGGER_NAME)
        self._logger.addHandler(logging.NullHandler())
        self._logger.propagate = False

    @property
    def root_logger(self) -> logging.Logger: ...          # 原模块级 _logger

    def install(self, yate_trace: Optional[bool] = None,
                yate_trace_level: Optional[str] = None) -> bool: ...
    def configure(self, yate_trace: Optional[bool] = None,
                  yate_trace_level: Optional[str] = None) -> None: ...   # 别名
    def uninstall(self) -> None: ...
    def current_path(self) -> Optional[Path]: ...
    def current_log_path(self) -> Optional[Path]: ...      # 别名
    def is_enabled(self) -> bool: ...
    def file_handlers(self) -> list[logging.FileHandler]: ...   # 原 _file_handlers()
    def get_logger(self, name: Optional[str] = None) -> logging.Logger: ...
```

`install()` 内联完成等级解析（旧的 `_requested_level()` 已删除）：

```
YATE_TRACE_LEVEL  →  yate_trace_level 参数  →  DEFAULT_LEVEL
level = resolve_level(name)
level = resolved if resolved is not None else logging.DEBUG   # 显式 None 判断，不用 `or`，
                                                              # 以便 NOTSET(0) 能保留
```

`cli.py` 里的两阶段安装：第一阶段 `tracing.install()`（只看环境变量），第二阶段
`tracing.configure(yate_trace=config.yate_trace, yate_trace_level=config.yate_trace_level)`。
第二次调用会保留第一次打开的文件、只调整等级，因此两阶段不会产生两个文件或两个头部。

保留的行为：构造时挂 `NullHandler`、`propagate = False`、文件懒创建、首条记录写头部、
两阶段幂等、环境变量优先于 yaterc、无等级时 `DEFAULT_LEVEL = "DEBUG"`、目录创建
`OSError` → 一条 stderr 警告 + 返回 `False`（编辑器照常启动）。

## 私有 → 公开 重命名对照

| 原私有 | 现公开 | 使用方 |
|--------|--------|--------|
| `crash._err_file` | `crash.err_file`（只读 property） | 测试读取；重置走底层属性（见 §测试变更） |
| `crash._err_path` | `crash.err_path`（只读 property） | 暂无调用点（读取走 `current_crash_file()`） |
| `crash._crashed` | `crash.had_crash`（只读 property） | 暂无调用点（真正起作用的是崩溃时保留报告） |
| `crash._original_excepthook` | `crash.original_excepthook`（只读 property） | 测试读取；注入假 hook 走底层属性 |
| `crash._cleanup_on_exit()` | `crash.cleanup_on_exit()` | `tests/test_crash.py` |
| `crash._err_file_path()` | `crash.build_err_path()` | `tests/test_crash.py` |
| `tracing._logger` | `tracing.root_logger`（只读 property） | `tests/test_tracing.py` |
| `tracing._file_handlers()` | `tracing.file_handlers()` | `tests/test_tracing.py` |
| `tracing._SessionFileHandler` | `_SessionFileHandler`（仍是模块私有） | 无外部使用；`TracingService.install()` 内部机件 |
| `tracing._requested_level()` | **已删除** —— 逻辑内联进 `install()` | 对应测试已删除（patch `resolve_level` 也影响不到 `install()`，因为它是模块全局） |

## 调用点变更

| 文件 | 变更 |
|------|------|
| `yate/cli.py` | `from yate.logs import crash, tracing`（两处：`main()` 顶部与 `--include-data` 分支）；第二阶段 `tracing.install(config)` → `tracing.configure(yate_trace=config.yate_trace, yate_trace_level=config.yate_trace_level)` |
| `yate/config.py` | `from yate.logs import DEFAULT_LEVEL, LEVEL_NAMES`；`_VALID_TRACE_LEVELS = LEVEL_NAMES`、`yate_trace_level: str = DEFAULT_LEVEL` |
| `yate/app.py`、`yate/editor_lsp/manager.py`、`yate/services/extensions.py` | `from yate.logs import tracing`（`tracing.get_logger(__name__)` 不变） |
| `yate/diagnostics.py` | `from yate.logs import crash, crash_data_dir`；`crash.crash_data_dir()` → `crash_data_dir()`，`crash.current_crash_file()` 不变 |
| `yate/services/__init__.py` | **无改动**（不再从服务包再导出单例） |
| `tests/test_cli.py` | patch 目标：`"yate.crash.install"` / `"yate.crash.uninstall"` → `"yate.logs.crash.install"` / `"yate.logs.crash.uninstall"`（8 处） |

## 测试变更

`tests/test_crash.py`：

* **单例直连**：`from yate.logs import crash`；`crash.install()` /
  `crash.uninstall()` / `crash.current_crash_file()` / `crash.build_err_path(...)` /
  `crash.cleanup_on_exit()` 全是对象方法（与生产同一条路径）；
* 模块级函数 `crash_data_dir()` 按名/经模块使用（`logs.crash_data_dir()`），
  因为它同时是 monkeypatch 的目标；
* `_reset_crash_state()` 重置**底层属性**（`crash._err_file` / `_err_path` /
  `_crashed`）——状态是只读 property，没有 setter；文件顶部保留
  `# pyright: reportPrivateUsage=false`，与 fixture 恢复
  `crash._original_excepthook`、`sys.excepthook` 的做法一致；
* 降级环境用例 patch **`yate.logs.crash_data_dir`**（`install()` 从 `yate.logs`
  自己的模块全局解析它，patch 服务对象不会生效）。

`tests/test_tracing.py`：

* **单例直连**：`from yate.logs import tracing`，加按名导入的
  `env_level, env_trace, resolve_level`（它们是模块函数，不是对象成员）；
* 删掉 `from yate.config import YateConfig`；所有调用改为
  `install(yate_trace=..., yate_trace_level="ERROR"|"WARNING"|"DEBUG")` —— 等级名
  保持字符串，测试点不再出现 `logging.ERROR` 这类 int；
* 删除 `_zero_level` 与 `test_requested_level_keeps_a_falsy_resolution`；
* `tracing.root_logger` / `tracing.file_handlers()` 直接读单例（无需再经 `logs.tracing`）；
* **新增** `test_configure_is_a_thin_alias_of_install`（否则第二阶段的路径没有单测覆盖）；
* 不可写日志目录的用例 patch **`yate.logs.logs_dir`**。

## 验证结果（实测）

| # | 验证项 | 命令 / 方式 | 结果 |
|---|--------|-------------|------|
| 1 | 无 `TYPE_CHECKING` / `YateConfig` / `from yate.config`（`logs.py` 与 `cli.py`） | `grep` | 0 命中 |
| 2 | 两个类之间无互相引用 | 在 `yate/logs.py` 中 grep `tracing.` / `crash.` | 只有 docstring 里的用法示例 |
| 3 | 严格类型检查 | `pyright`（1.1.414，`typeCheckingMode = "strict"`，含 `yate`、`tools`、`tests`） | **0 errors, 0 warnings** |
| 4 | 全量测试 | `python -m pytest tests/` | **612 passed in 137.77s** |
| 5 | 头部字节 | 将 `build_session_header(...)` / `_trace_header(...)` 与历史格式串比对 | 两者均**逐字节一致** |
| 6 | 导入顺序 | 分别以 `import yate.logs` / `yate.config` / `yate.cli` / `yate.app` / `yate.services.extensions` / `yate.diagnostics` 作为首个导入 | 全部干净，无环 |
| 7 | `YATE_TRACE=1 yate --version` | 沙箱 HOME | 立即退出、**不生成日志文件**（懒创建），也不残留 `.err` |
| 8 | `YATE_TRACE=1 yate --diag` | 沙箱 HOME | 生成带精确头部 + `trace level: DEBUG` 的 `.log`；验证第二阶段 `configure` |
| 9 | 未捕获异常 | `crash.install(); tracing.install(yate_trace=True); raise RuntimeError` | `.err` 保留（头部 + `=== uncaught Python exception ===`）；追踪日志中 `uncaught` **0 行**（镜像已移除） |
| 10 | `yate --cleanup-defaults --include-data` | 沙箱 HOME | `data/` 被完整删除，无残留 |
| 11 | 旧路径残留 | `grep -r "yate.crash\|yate.tracing\|crash.py\|tracing.py"`（代码/文档） | 0 命中（`yate/crash.py`、`yate/tracing.py` 已删除） |

## 后续开发陷阱

| 陷阱 | 为什么咬人 | 正确做法 |
|------|------------|----------|
| 给 `yate/logs.py` 添加项目内依赖（`config`、`services`…） | 它是叶子模块，所以任何模块都能在任何时刻导入它；一旦它反向依赖上层，启动期就会重新出现循环导入 | 保持只依赖标准库 + `yate.__version__` |
| 企图通过单例访问模块级名字（`tracing.LEVEL_NAMES`、`crash.crash_data_dir()`） | 常量与纯函数不在类上，`AttributeError` | 按名导入：`from yate.logs import LEVEL_NAMES, crash_data_dir` |
| 在服务对象上 monkeypatch 模块函数（`monkeypatch.setattr(crash, "crash_data_dir", …)`） | 模块函数不是对象成员；且 `install()` 从 `yate.logs` 的**模块全局**解析它们 | 用 `logs` 模块对象（或字符串 `"yate.logs.crash_data_dir"`）patch |
| 在测试 `cli.py` 时 patch 错位置 | `cli.py` 在 `main()` 内 `from yate.logs import crash`，之后调用的是**对象方法**；打在 `yate.logs.crash.install` 才生效 | `patch("yate.logs.crash.install")` / `patch("yate.logs.crash.uninstall")` |
| 直接改只读状态（`crash.err_file = None`） | property 没有 setter | 测试里改底层属性（配 `reportPrivateUsage` 豁免），或走 `cleanup_on_exit()` 这样的公开方法 |
| 忘记 `_SessionFileHandler` 是私有的 | 名字带下划线，属于实现细节；对外没有契约 | 需要别的格式时再单独设计（子类化或参数化），不要当公开 API |
| 在 `.err` 头 / `.log` 头里手写字段 | 两个头部都由 `build_session_header()` 生成，手写会让格式漂移 | 通过 `title` / `extra_lines` / `footer_lines` 传参 |

## 与初稿的差异

1. **模块位置与名字**：`yate/services/log_services.py` → **`yate/logs.py`**（顶层）。
   初稿把实现放在 `yate/services/` 下并让薄壳导入它，触发了上文的导入环；
   移到顶层（叶子模块）后环从结构上消失。
2. **`build_session_header` 签名**：`service_name` + 固定行序 →
   `title` + `extra_lines` + `footer_lines`，以保证追踪日志的标题装饰与行序逐字节不变。
3. **薄壳：引入 → 收缩 → 删除**。中间版本曾用 `yate/crash.py` / `yate/tracing.py`
   再导出"有调用点的名字"（方法以绑定方法形式再导出，因为调用点是**模块属性查找**，
   且 `patch("yate.crash.install")` 依赖它）。但由此产生两套路径（`logs.crash.x` 与
   `crash.x`），容易混淆；最终决定**删除薄壳**，统一为
   `from yate.logs import crash, tracing`。代价：`from yate import crash/tracing` 这类
   旧写法不再可用（仓库内所有调用点已同步；外部扩展若依赖它需改一行导入）。
4. **`SessionFileHandler` 反复一次**：原名 `_SessionFileHandler`（私有）→ 重构时
   提升为公开（准备给薄壳/测试用，但始终没有调用点）→ 薄壳删除后**改回私有**。
5. **放弃 `yate/services/__init__.py` 的再导出**：全库 0 调用点，且单例不在服务包下。
6. **测试**：patch 目标从 `yate.crash.*` 改为 `yate.logs.crash.*`；`test_crash.py`
   改为单例直连；新增 `test_configure_is_a_thin_alias_of_install`；按计划删除
   `test_requested_level_keeps_a_falsy_resolution`。
7. **`YateConfig` 彻底移除**：`install()` 收两个标量（`yate_trace` / `yate_trace_level`），
   等级字符串在服务内部经 `resolve_level()` 解析（显式 `None` 判断，保留 `NOTSET(0)`）。

## 可扩展方向

1. **在 `cli.py` 层重新加回 crash → tracing 镜像**：两个服务都安装完后，注册一个
   atexit 回调（或包装 `sys.excepthook`），检查 `crash.had_crash`，若
   `tracing.is_enabled()` 则用 `tracing.get_logger("crash").error(...)` 记录最后一次异常。
   协调逻辑放在调用方，不会重新引入 `crash → tracing` 导入。
2. **两个服务改用 `@dataclass(slots=True)`**：状态声明会更清晰；现在没做，是因为
   测试仍直接重置底层属性（这一步要先设计出公开的重置入口）。
3. **抽出 `LogService` `Protocol`**（不是 ABC）：如果哪天需要多态地
   对待二者。目前没有任何地方这么做。（注：`yate/interfaces.py` 已在
   2026-09-22 的分层重构中删除，当前架构不使用 `Protocol`。）
4. **日志轮转 / 清理**：`~/.yate/data/` 下 `.err` 与 `.log` 的数量上限（文件名前缀
   常量已经集中在 `logs.py`，便于按 glob 清理）。
5. **在 `cli.py` 层加 `LogServiceRegistry`**：持有两个单例并提供
   `install_all()` / `uninstall_all()` —— 跨服务协调（见第 1 条）的天然归属。
6. **把 `crash.had_crash` / `tracing.is_enabled()` 接入 `yate.diagnostics`**：让 `--diag`
   能报告"上次运行崩溃过" / "本次会话开着追踪"。
7. **把 `configure()` 长成完整的状态合并方法**：若追踪未来增加更多 yaterc 开关
   （例如 `yate_trace_format`），`configure()` 是自然的扩展点，而 `install()` 继续专注于
   环境变量 + rc 的 trace/level。
