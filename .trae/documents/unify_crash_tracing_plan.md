# 崩溃与追踪日志统一方案 —— 已实现设计

> **状态：已实现。** 本文档在执行完成后按当前代码回写；与初稿的差异集中在文末
> 「与初稿的差异」一节，而不是散落在正文里。
>
> 姊妹文档：`crash_diagnostic_plan.md`（崩溃诊断 `crash-*.err`）、
> `logs_impl_plan.md`（运行日志 `YATE_TRACE`）。

## 目标

把原先的 `yate/crash.py` 与 `yate/tracing.py` 合并为单一日志模块
**`yate/logs.py`**，对外暴露 `crash` 与 `tracing` 两个**互不引用的单例对象**。
两个服务除了少量模块级辅助函数之外不共享任何东西：无循环导入、两个类之间无互相
引用、无 `TYPE_CHECKING` 守卫、无 `YateConfig` 引用。

## 硬约束 —— 全部满足

| # | 约束 | 实现如何满足 |
|---|------|--------------|
| 1 | 统一日志 —— 崩溃与追踪 | 两者都在 `yate/logs.py`；薄壳 `yate/crash.py` / `yate/tracing.py` 从它再导出 |
| 2 | 新增日志模块并暴露 `crash` / `tracing` 对象 | `yate/logs.py` 末尾 `crash = CrashService()` / `tracing = TracingService()`，**一个对象只有一个地址**；壳只承载**旧**导入路径，不再导出对象 |
| 3 | 崩溃与追踪功能保持不变 | `install()`、`uninstall()`、`get_logger()`、excepthook 链、`faulthandler` 启用、atexit 清理、日志文件懒创建，**以及两种头部格式**均 1:1 保留（逐字节比对，见 §验证结果） |
| 4 | 无循环依赖 | `yate/logs.py` 只依赖标准库 + `yate.__version__`，且位于所有"导入薄壳的包"**之外** —— 见 §为什么放在顶层 |
| 5 | 崩溃与追踪互相独立 | excepthook 里旧的 `tracing.get_logger("crash").error(...)` 调用**已删除**；两个类除 docstring 外互不提及 |
| 6 | 公共逻辑写成函数 | `warn`、`build_session_header`、`resolve_level`、`env_trace`、`env_level`、`logs_dir`、`crash_data_dir` 均为模块级函数；无 ABC、无基类、无 `@staticmethod` |
| 7 | 彻底去掉 `YateConfig` —— 传两个标量 | `install(yate_trace: Optional[bool], yate_trace_level: Optional[str])`；等级字符串在 `install()` 内部解析为 int。`cli.py` 直接传 `config.yate_trace` / `config.yate_trace_level` |
| 8 | `tracing` 提供与 `install()` 同签名的 `configure()` | `configure(yate_trace=None, yate_trace_level=None) -> None` —— 一行别名，用于 rc 阶段的重新配置 |
| 9 | *（推导）* 调用点靠**模块属性查找**继续工作 | 薄壳把单例的**方法**以绑定方法形式再导出 —— 只导出有调用点的，绝不"以防万一"；见 §薄壳 |
| 10 | *（推导）* 两种头部保持逐字节一致 | `build_session_header(*, title, extra_lines, footer_lines)` 能精确复现两种历史布局 |

## 为什么 `yate/logs.py` 放在顶层（而不是 `yate/services/log_services.py`）

初稿把模块放在 `yate/services/` 下。这会形成导入环，因为**导入任何子模块都会先初始化
它的父包**：

```
import yate.tracing                                  # 薄壳开始执行
└─ from yate.logs import …            #（初稿：from yate.services.log_services import …）
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

由此推出三条规则，最终布局全部遵守：

1. 实现模块必须是**叶子**：只依赖标准库 + `yate.__version__`。它导入的任何东西都可能
   绕回来、重新进入尚未构造完成的薄壳。
2. 它**不能**待在"`__init__`（传递地）在模块级导入薄壳"的包里。
   `yate.services.__init__` 导入 `yate.services.extensions`，后者又能到达
   `yate.editor_lsp.manager` —— 所以 `yate.services/` 下正是最不该待的地方。
3. 于是包内的消费者（`services/extensions.py`、`editor_lsp/manager.py`）保持原本统一的
   `from yate import tracing`，任何地方都不需要特例注释或备用导入路径。

以下模块各自作为**首个导入**在新解释器里验证通过：
`yate.tracing`、`yate.crash`、`yate.logs`、`yate.config`、`yate.app`、
`yate.services.extensions` —— 全部干净。

## 最终文件布局

```
yate/
├── logs.py                  ← 新增（569 行）实现：常量、纯函数、
│                                    SessionFileHandler、CrashService、
│                                    TracingService、两个单例
├── crash.py                 ← 薄壳（36 行）再导出 yate.logs
├── tracing.py               ← 薄壳（53 行）再导出 yate.logs
├── cli.py                   ← 第二阶段改为 tracing.configure(...)
├── diagnostics.py           ← 无改动（crash.crash_data_dir / current_crash_file）
├── config.py                ← 无改动（tracing.LEVEL_NAMES / DEFAULT_LEVEL）
├── app.py                   ← 无改动（tracing.get_logger）
├── editor_lsp/manager.py    ← 无改动（tracing.get_logger）
└── services/
    ├── __init__.py          ← 无改动
    └── extensions.py        ← 无改动（tracing.get_logger）

tests/
├── test_crash.py            ← 改动（194 行）单例状态、公开名
├── test_tracing.py          ← 改动（280 行）去掉 YateConfig、公开名
└── test_cli.py              ← 无改动（patch("yate.crash.install") 仍可解析）
```

## 依赖关系（重构后）

```
cli.py ──► yate.crash（薄壳） ──┐
cli.py ──► yate.tracing（薄壳）─┼──► yate.logs ──►（仅标准库 + yate.__version__）
config.py ──► yate.tracing ─────┤
app.py ──► yate.tracing ────────┤
editor_lsp/manager.py ──────────┤
services/extensions.py ─────────┘
diagnostics.py ──► yate.crash

yate/logs.py:
  ├── 模块级 —— 常量 + 纯函数（两个类共享）
  │     LOGGER_NAME, LEVEL_NAMES, DEFAULT_LEVEL, TRUE_VALUES, FALSE_VALUES
  │     DATA_DIRNAME, LOG_DIRNAME, LOG_PREFIX, LOG_SUFFIX, ERR_PREFIX, ERR_SUFFIX
  │     warn(), build_session_header(), resolve_level(), env_trace(), env_level(),
  │     logs_dir(), crash_data_dir()
  ├── SessionFileHandler          （公开类 —— 仅 TracingService 使用）
  ├── CrashService                （自包含，不引用 TracingService）
  ├── TracingService              （自包含，不引用 CrashService）
  ├── crash = CrashService()      单例
  └── tracing = TracingService()  单例

⚠️  无 ABC。无 TYPE_CHECKING。无 YateConfig。两个类之间无任何导入。
```

## 模块级常量与纯函数

调用点不变，因为薄壳再导出了这些名字：`tracing.LEVEL_NAMES`、
`tracing.resolve_level(...)`、`crash.crash_data_dir()`。

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

## SessionFileHandler（公开）

从 `yate/tracing.py` **原样迁移**，仅改名（`_SessionFileHandler` →
`SessionFileHandler`），头部调用改走 `_trace_header()`：

* `delay=True` —— 文件在**第一条真正写出的记录**时才创建，所以
  `YATE_TRACE=1 yate --version` 不会在 `~/.yate/data/logs` 留下空壳文件；
* 头部在首次 emit 时直接写入流（不走 logger），无论配置的等级是什么都会出现；
* `OSError` → `handleError()`（日志绝不能把编辑器搞崩）；
* `close()` 会重置 `self._stream`，后续记录会重新打开文件，而不是写进一个已关闭的句柄；
* 懒打开用我们自己的 `_stream` 跟踪，而不是判断 `self.stream is None`。

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
| 模块级 `_err_file` / `_err_path` / `_crashed` / `_original_excepthook` | 变成单例的实例属性，通过 `@property` 暴露为公开名 |
| `_err_file_path()` / `_cleanup_on_exit()` / `_excepthook()` | 变成实例方法 `build_err_path()` / `cleanup_on_exit()` / `_excepthook()` |
| `_write_header(handle)` | 改为写 `build_session_header(title=…crash report)`，字节一致 |
| `crash_data_dir()` | 保持**模块级**函数（硬约束 #6）；薄壳再导出 |
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

## 薄壳

`yate/crash.py`（36 行）与 `yate/tracing.py`（53 行）是纯再导出。它们不引入任何新东西：
壳里每个名字都只在 `yate/logs.py` 实现一次。

**壳里放什么的规则** —— 只有当"壳之外有人查这个名字"时才保留；"有人"是**统计出来的**：
对 `yate/`、`tests/`、`tools/` 逐个名字统计 `crash.<name>` / `tracing.<name>` 的引用
（区分生产代码与测试），而不是凭印象：

1. **有调用点的名字** —— `LEVEL_NAMES` / `DEFAULT_LEVEL`（`config.py`）、
   `crash_data_dir` / `current_crash_file`（`diagnostics.py`），以及
   `resolve_level` / `env_trace` / `env_level` / `is_enabled` / `current_log_path`
   （测试作为旧公开辅助函数的"外部调用方"在用）。
2. **调用点做模块属性查找的单例方法** —— `install` / `uninstall`（`cli.py`）、
   `configure`（`cli.py` 第二阶段）、`get_logger`（`app.py`、`manager.py`、
   `extensions.py`），以及 `current_crash_file`（`diagnostics.py`）。

**零调用的名字一律删除**，即使旧模块公开过它们：`LOGGER_NAME`、`TRUE_VALUES`、
`FALSE_VALUES`、`LOG_DIRNAME`、`LOG_PREFIX`、`LOG_SUFFIX`、`logs_dir`（追踪）
与 `DATA_DIRNAME`、`ERR_PREFIX`、`ERR_SUFFIX`（崩溃）。它们是文件名 / 环境变量的
词汇表（实现细节），在 `yate.logs` 里仍然公开。**壳不是博物馆**：没人查的名字
只是一个白占地方的第二个地址。

**服务对象刻意不再导出**：旧模块没有 `crash` / `tracing` 对象，
`yate.tracing.tracing` 只会是 `yate.logs.tracing` 的多余别名。单例只以私有别名
导入（`from yate.logs import tracing as _service`），用途仅仅是搭出下面的绑定。

```python
# yate/tracing.py —— 方法绑定（crash.py 同构，绑定 install / uninstall / current_crash_file）
install = _service.install
configure = _service.configure
uninstall = _service.uninstall
get_logger = _service.get_logger
is_enabled = _service.is_enabled
current_log_path = _service.current_log_path
```

为什么必须有这些绑定：`from yate import tracing` 绑定的是**模块**，而调用点写的是
`tracing.install()` / `tracing.get_logger(__name__)` —— 属于**模块属性查找**，
不是单例方法查找。没有这些绑定，所有既有调用点都会断。同样因为 `cli.py` 也是查模块
属性，这些绑定才让 `tests/test_cli.py` 里的 `patch("yate.crash.install")` /
`patch("yate.crash.uninstall")` 继续生效。

**重构*新增*的东西一律不进壳** —— `CrashService`、`TracingService`、
`SessionFileHandler`、`current_path()`、`file_handlers()`、`build_err_path()`、
`cleanup_on_exit()`。它们在 `yate.logs` 里就是公开的；壳的职责是*旧*导入路径，
而不是给新 API 开第二个地址。旧但无人使用的名字同理：`logs_dir()`、`LOGGER_NAME`、
`TRUE_VALUES` / `FALSE_VALUES`、`LOG_*` / `ERR_*` / `DATA_DIRNAME` 这些文件名常量
—— 都还在 `yate.logs` 里公开，只是没有任何一个由壳承载。

property 无法这样再导出（模块属性在导入时就被冻结成一个值），所以可变状态、以及壳
刻意不镜像的东西，都从实现模块取：

```python
from yate import crash                        # 模块：常量 + 辅助函数 + 方法
from yate.logs import crash as crash_service  # 单例：err_file、had_crash、…
from yate import logs                         # logs.tracing.file_handlers()
```

## 私有 → 公开 重命名对照

| 原私有 | 现公开 | 使用方 |
|--------|--------|--------|
| `crash._err_file` | `crash.err_file`（property） | `tests/test_crash.py` |
| `crash._err_path` | `crash.err_path`（property） | 公开只读状态；暂无调用点（测试直接重置 `_err_path`，读取走 `current_crash_file()`） |
| `crash._crashed` | `crash.had_crash`（property） | 公开只读状态；暂无调用点（真正起作用的是那个标志本身：崩溃时保留报告） |
| `crash._original_excepthook` | `crash.original_excepthook`（property） | `tests/test_crash.py` |
| `crash._cleanup_on_exit()` | `crash.cleanup_on_exit()` | `tests/test_crash.py` |
| `crash._err_file_path()` | `crash.build_err_path()` | `tests/test_crash.py` |
| `tracing._logger` | `tracing.root_logger`（property） | `tests/test_tracing.py`，经 `logs.tracing.root_logger`（property 无法再导出） |
| `tracing._file_handlers()` | `tracing.file_handlers()` | `tests/test_tracing.py`，经 `logs.tracing.file_handlers()` —— 壳不镜像它 |
| `tracing._SessionFileHandler` | `SessionFileHandler`（公开类） | 暂无调用点 —— 只在 `yate.logs` 公开；壳刻意不再导出 |
| `tracing._requested_level()` | **已删除** —— 逻辑内联进 `install()` | 对应测试已删除（从壳上 monkeypatch `resolve_level` 本来也影响不到 `install()`） |

## 调用点变更

| 文件 | 变更 |
|------|------|
| `yate/cli.py` | 第二阶段：`tracing.install(config)` → `tracing.configure(yate_trace=config.yate_trace, yate_trace_level=config.yate_trace_level)`；调用点不需要导入 `resolve_level` |
| `yate/diagnostics.py` | **无改动** —— `crash.crash_data_dir()`（壳函数）+ `crash.current_crash_file()`（壳上的绑定方法） |
| `yate/config.py` | **无改动** —— `tracing.LEVEL_NAMES` / `tracing.DEFAULT_LEVEL` 壳常量 |
| `yate/app.py`、`yate/editor_lsp/manager.py`、`yate/services/extensions.py` | **无改动** —— `tracing.get_logger(__name__)` 壳上的绑定方法 |
| `yate/services/__init__.py` | **无改动** —— 单例已不住在 `services/` 下；它们可从 `yate.logs.crash` / `yate.logs.tracing`（或壳）拿到 |
| `tests/test_cli.py` | **无改动** —— `patch("yate.crash.install")` / `patch("yate.crash.uninstall")` 仍然打在 `cli.py` 读取的模块属性上 |

## 测试变更

`tests/test_crash.py`：

* 生命周期与可变状态走单例（`from yate.logs import crash as crash_service`）；
  模块级辅助函数 `crash_data_dir()` 与 patch 目标走壳（`from yate import crash`）；
* `_reset_crash_module()` → `_reset_crash_state()`，重置单例的底层属性
  （`_err_file`、`_err_path`、`_crashed`）；
* fixture 通过属性赋值恢复 `crash_service._original_excepthook`（property 不可赋值）；
* 降级环境用例 patch 的是 **`yate.logs`** —— `install()` 从自身模块全局解析
  `crash_data_dir`，patch 薄壳不会生效（与初稿为 `resolve_level` 标记的是同一类陷阱）。

`tests/test_tracing.py`：

* 删掉 `from yate.config import YateConfig`；所有调用改为
  `install(yate_trace=..., yate_trace_level="ERROR"|"WARNING"|"DEBUG")` —— 等级名
  保持字符串，测试点不再出现 `logging.ERROR` 这类 int；
* 删除 `_zero_level` 与 `test_requested_level_keeps_a_falsy_resolution`；
* 壳不镜像的状态从实现模块取：`_logger` → `logs.tracing.root_logger`、
  `_file_handlers()` → `logs.tracing.file_handlers()`；
* **新增** `test_configure_is_a_thin_alias_of_install`（否则第二阶段的路径没有单测覆盖）；
* 不可写日志目录的用例 patch **`yate.logs.logs_dir`**。

## 验证结果（实测）

| # | 验证项 | 命令 / 方式 | 结果 |
|---|--------|-------------|------|
| 1 | 新模块、壳、`cli.py` 中无 `TYPE_CHECKING` / `YateConfig` / `from yate.config` | `grep` | 0 命中 |
| 2 | 两个类之间无互相引用 | 在 `yate/logs.py` 中 grep `tracing.` / `crash.` | 只有 docstring 里的用法示例 |
| 3 | 严格类型检查 | `pyright`（1.1.414，`typeCheckingMode = "strict"`，含 `yate`、`tools`、`tests`） | **0 errors, 0 warnings** |
| 4 | 全量测试 | `python -m pytest tests/` | **612 passed in 141.34s** |
| 5 | 头部字节 | 将 `build_session_header(...)` / `_trace_header(...)` 与历史格式串比对 | 两者均**逐字节一致** |
| 6 | 导入顺序 | 分别以 `import yate.tracing` / `yate.crash` / `yate.logs` / `yate.config` / `yate.app` / `yate.services.extensions` 作为首个导入 | 全部干净，无环 |
| 7 | `YATE_TRACE=1 yate --version` | 沙箱 HOME | 立即退出、**不生成日志文件**（懒创建），也不残留 `.err` |
| 8 | `YATE_TRACE=1 yate --diag` | 沙箱 HOME | 生成带精确头部 + `trace level: DEBUG` 的 `.log`；验证第二阶段 `configure` |
| 9 | 未捕获异常 | `crash.install(); tracing.install(yate_trace=True); raise RuntimeError` | `.err` 保留（头部 + `=== uncaught Python exception ===`）；追踪日志中 `uncaught` **0 行**（镜像已移除） |
| 10 | `yate --cleanup-defaults --include-data` | 沙箱 HOME | `data/` 被完整删除，无残留 |
| 11 | 残留引用 | `grep -r log_services` | 0 命中 |
| 12 | 壳的对外面 | 对 `yate/`、`tests/`、`tools/` 中每个 `crash.<name>` / `tracing.<name>` 引用与壳的 `__all__` 逐名比对 | 保留 = 有调用点的名字（追踪 11 个 / 崩溃 4 个）；因 **0 调用点** 删除：`SessionFileHandler`、`TracingService`、`CrashService`、`current_path()`、`file_handlers()`、`build_err_path()`、`cleanup_on_exit()`、`crash` / `tracing` **对象名**，以及 10 个文件名 / 环境变量常量 |

## 后续开发陷阱

| 陷阱 | 为什么咬人 | 正确做法 |
|------|------------|----------|
| 把 `yate/logs.py` 移回某个包内 | 导入任何子模块都会先初始化父包 `__init__`；`yate.services.__init__` 能到达 `editor_lsp.manager`，而后者在模块级需要薄壳 → 半成品模块 `AttributeError` | 保持在顶层，且只依赖标准库 |
| 在壳上 monkeypatch 辅助函数（`monkeypatch.setattr(tracing, "logs_dir", …)`） | `install()` 从**自身模块全局**解析 `logs_dir` / `crash_data_dir` / `resolve_level`，不看壳 | patch `yate.logs` |
| 通过壳取 property（`crash.err_file`） | property 无法再导出；写成模块属性会把值冻结在导入那一刻 | 用单例：`from yate.logs import crash` |
| 在测试 `cli.py` 时直接 patch 单例（`patch.object(crash, "install")`） | `cli.py` 调用的是**模块**属性（薄壳在导入时就绑好了），实例上的 patch 对它不可见 | 继续 patch `yate.crash.install` |
| 给"`yate.services.__init__` 会导入的模块"加 `from yate import logs` | 今天没问题（`logs` 是叶子），但一旦它长出标准库之外的依赖就可能重新引入导入环 | 保持它零依赖 |
| 以为 `crash.install()` 与 `crash.crash.install()` 是同一个对象 | 绑定方法在每次属性访问时新建；只有 `.__func__` / `.__self__` 相等 | 比较行为，不要比较身份 |
| 往壳里塞"以防万一"的名字 | 每个多余的名字都是同一 API 的第二个地址，而且没有调用点 —— 这正是 `SessionFileHandler` / `TracingService` / `CrashService` 被移出壳的原因 | 先 grep，确有用到再加 |

## 与初稿的差异

1. **模块位置与名字**：`yate/services/log_services.py` → **`yate/logs.py`**（顶层），
   用于打断上文的导入环。设计本身没有因此改变，但因为环而被迫加的两处包内绕行
   （`extensions.py` / `manager.py` 从实现模块导入）已经消失 —— 两个文件都回到
   `from yate import tracing`。
2. **`build_session_header` 签名**：`service_name` + 固定行序 →
   `title` + `extra_lines` + `footer_lines`，以保证追踪日志的标题装饰与行序逐字节不变。
3. **薄壳再导出绑定方法**（硬约束 #9）：初稿假设 `crash.install()` 会解析到单例的方法；
   实际那是*模块*属性查找，所以壳必须承载这些方法。附带好处：
   `tests/test_cli.py` 里的 `patch("yate.crash.*")` 继续生效，该文件一行都不用改。
4. **测试**：patch 目标改为 `yate.logs`；新增
   `test_configure_is_a_thin_alias_of_install`；按计划删除
   `test_requested_level_keeps_a_falsy_resolution`。
5. **放弃 Task 6 并多次收缩壳**：初稿还要求 `yate/services/__init__.py` 再导出单例、
   要求壳承载 `CrashService` / `TracingService` / `SessionFileHandler`。全库 grep 显示它们
   **0 调用点**，而且模块已不在 `services/` 下，包级再导出更没道理；
   `yate/services/__init__.py` 已还原为原始内容。之后壳又按同一条 grep 规则收缩了两轮：
   先是新成员与对象别名（`SessionFileHandler`、`TracingService` / `CrashService`、
   `current_path()`、`file_handlers()`、`build_err_path()`、`cleanup_on_exit()`、
   `yate.tracing.tracing` / `yate.crash.crash` —— 这轮还把 `tests/test_crash.py` 的
   `from yate.crash import crash` 换成了 `from yate.logs import crash`），
   接着是**全库零调用**的 10 个名字：文件名 / 环境变量词汇表（`LOGGER_NAME`、
   `TRUE_VALUES`、`FALSE_VALUES`、`LOG_DIRNAME`、`LOG_PREFIX`、`LOG_SUFFIX`、
   `logs_dir`、`DATA_DIRNAME`、`ERR_PREFIX`、`ERR_SUFFIX`）。最终剩下的恰好是
   "有人查的名字"（见 §薄壳）；其余一切只有一个地址：`yate.logs`。

## 可扩展方向

1. **在 `cli.py` 层重新加回 crash → tracing 镜像**：两个服务都安装完后，注册一个
   atexit 回调（或包装 `sys.excepthook`），检查 `crash.had_crash`，若
   `tracing.is_enabled()` 则用 `tracing.get_logger("crash").error(...)` 记录最后一次异常。
   协调逻辑放在调用方，不会重新引入 `crash → tracing` 导入。
2. **两个服务改用 `@dataclass(slots=True)`**：等测试不再直接赋值底层属性之后。
   状态声明会更清晰；现在不做是因为每个重置 `crash_service._err_file` 的测试都要改。
3. **抽出 `LogService` `Protocol`**（不是 ABC）：如果哪天 `yate/interfaces.py` 需要多态地
   对待二者。目前没有任何地方这么做。
4. **`SessionFileHandler` 的子类**：面向其他格式（JSONL、轮转、远端 sink）—— 类公开后，
   "懒打开 + 首条记录写头部"的模式可复用。
5. **在 `cli.py` 层加 `LogServiceRegistry`**：持有两个单例并提供
   `install_all()` / `uninstall_all()` —— 跨服务协调（见第 1 条）的天然归属，且不耦合服务本身。
6. **把 `crash.had_crash` / `tracing.is_enabled()` 接入 `yate.diagnostics`**：让 `--diag`
   能报告"上次运行崩溃过" / "本次会话开着追踪"。
7. **把 `configure()` 长成完整的状态合并方法**：若追踪未来增加更多 yaterc 开关
   （例如 `yate_trace_format`），`configure()` 是自然的扩展点，而 `install()` 继续专注于
   环境变量 + rc 的 trace/level。
