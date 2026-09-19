# 日志系统实现方案：Python logging 落盘（YATE_TRACE）

> 基于 Python 自带 `logging` 框架为 yate 实现可调试的日志系统。
> 日志**默认关闭**，通过环境变量 `YATE_TRACE` / `YATE_TRACE_LEVEL`
> 或 yaterc 中的 `yate_trace` / `yate_trace_level` 控制，
> 启用后写入 `~/.yate/data/logs/` 下带时间戳的 `.log` 文件。

---

## 1. 背景与目标

### 1.1 现状

yate 目前只有**崩溃诊断**（`yate/crash.py` → `~/.yate/data/crash-*.err`），
覆盖 native crash 与未捕获异常，但**没有常规运行日志**：

- 未使用 `logging` 模块，模块内无 `log.debug/info/...` 埋点
- 运行期问题（LSP 启动失败、扩展加载异常、保存慢、补全失效等）
  只能靠 `--diag` 快照或用户复述，缺少时间线还原手段
- crash-*.err 只在进程死亡时保留，正常运行不留任何痕迹

### 1.2 目标

| 目标 | 说明 |
|------|------|
| **框架** | Python 标准库 `logging`，不引入第三方依赖 |
| **默认关闭** | 不设置开关时零文件、零输出、零开销（无 handler 即无 I/O） |
| **开关** | 环境变量 `YATE_TRACE` 或 yaterc 选项 `yate_trace` |
| **等级** | 环境变量 `YATE_TRACE_LEVEL` 或 yaterc 选项 `yate_trace_level`，与 `logging` 内置等级（DEBUG/INFO/WARNING/ERROR/CRITICAL）对齐 |
| **落盘位置** | `~/.yate/data/logs/yate-YYYYMMDD-HHMMSS.log` |
| **零侵入** | 日志初始化失败（目录不可写等）不影响编辑器启动（best-effort，与 `crash.py` 同哲学） |

### 1.3 非目标（后续可扩展方向）

- 日志轮转 / 数量上限清理
- 结构化（JSON）日志
- 终端 UI 内查看日志的命令（`:log` / OutputScreen）
- per-module 等级（如 `YATE_TRACE_LEVEL="yate.lsp=debug"`）

---

## 2. 方案设计

### 2.1 新增模块：`yate/tracing.py`

与 `crash.py`、`paths.py` 同级，属启动期基础设施，不依赖 TUI。

| 函数/变量 | 职责 |
|-----------|------|
| `LOGGER_NAME = "yate"` | 应用根 logger 名，所有子 logger（`yate.lsp` 等）向它传播 |
| `logs_dir()` | 返回并创建 `~/.yate/data/logs/` |
| `get_logger(name=None)` | 返回 `logging.getLogger("yate" 或 "yate.<name>")`，供各模块取 logger |
| `resolve_level(raw)` | 把 `"debug"`/`"INFO"`/`"WARNING"`…（大小写不敏感）解析为 `logging` 数值等级（10/20/30/40/50），非法返回 `None` |
| `env_trace()` | 读取 `YATE_TRACE`：返回 `True`/`False`/`None`（未设置或值不可识别） |
| `env_level()` | 读取 `YATE_TRACE_LEVEL`：返回等级名或 `None` |
| `install(config=None)` | 主入口：两阶段调用——无 config 时只看 env；传入 `YateConfig` 时按 §2.2 优先级合并，env 显式值不被 rc 覆盖；幂等 |
| `uninstall()` | 关闭并移除 handler（`--cleanup-defaults --include-data` 删 `data/` 前调用，Windows 打开的句柄会阻塞目录删除——同 `crash.uninstall()` 的理由） |
| `is_enabled()` | 当前是否启用（幂等判断、测试断言用） |

### 2.2 配置来源与优先级

三个来源，**优先级从高到低**（环境变量是会话级覆盖，语义同 CLI 标志覆盖 yaterc）：

```
环境变量 YATE_TRACE / YATE_TRACE_LEVEL
        │  未设置时 ↓
yaterc 选项 yate_trace / yate_trace_level（项目 rc 覆盖用户 rc，同现有 rc 合并规则）
        │  未设置时 ↓
默认：关闭；开启但未指定等级时为 DEBUG
```

**`YATE_TRACE` 取值**（大小写不敏感）：

| 值 | 语义 |
|----|------|
| `1` / `true` / `yes` / `on` | 开启 |
| `0` / `false` / `no` / `off` | 显式关闭（覆盖 yaterc 里的 `yate_trace = True`） |
| 未设置 / 空串 | 交给 yaterc 决定 |
| 其它非空值 | 视为未设置，向 stderr 打一条警告后回退 yaterc |

**`YATE_TRACE_LEVEL` / `yate_trace_level` 取值**：与 `logging` 内置等级名对齐
（大小写不敏感）：`DEBUG`(10) / `INFO`(20) / `WARNING`(30) / `ERROR`(40) / `CRITICAL`(50)。
非法值不崩溃：env 来源回退默认 DEBUG 并警告；yaterc 来源记入 `config.errors`
（启动时显示在消息行，与现有选项校验一致）。

### 2.3 文件布局

```
~/.yate/data/logs/yate-20260920-101530.log
```

- 命名：`yate-YYYYMMDD-HHMMSS.log`（与 `crash-YYYYMMDD-HHMMSS.err` 风格一致）
- **追加模式**打开（`mode="a"`）：同一秒内启动的第二个实例复用文件而非失败/覆盖
- 每次进程启动先写**会话头**（含 pid 区分同文件的多个会话）：

```
=== yate 0.2.4 session ===
time: 2026-09-20T10:15:30
pid: 12345
cwd: /home/user/project
argv: ['yate', 'main.py']
python: 3.11.5 on win32
trace level: DEBUG
------------------------
2026-09-20 10:15:30.123 INFO  yate.cli: startup: rc sources=[...]
```

- 记录格式：`%(asctime)s %(levelname)-7s %(name)s: %(message)s`

### 2.4 logger 树与默认关闭的实现

```python
_logger = logging.getLogger("yate")
_logger.addHandler(logging.NullHandler())
_logger.propagate = False
# ... 省略函数定义；模块末尾有 atexit.register(uninstall) 兜底 ...
```

- 默认（关闭）：`"yate"` logger 只有 `NullHandler`，任何 `log.debug(...)` 调用
  无 I/O、无输出，TUI 画面不受影响
- 开启：`install()` 在 `"yate"` logger 上附加 `FileHandler` 并**让根 logger 保持 DEBUG**，过滤完全在 handler 上执行（`handler.setLevel(level)`）——将来加第二个 handler（如 stderr）可各自设级而不影响根
- 子 logger（`yate.lsp`、`yate.editor_view.editor`…）通过 `get_logger(__name__)` 获取，
  自动传播到根 logger 的 handler（根 logger `propagate=False`，绝不漏到 root/stderr 污染 TUI）
- 关闭再开启 / 重复 `install()`：先移除已有非 Null handler 再附加，幂等

### 2.5 集成点：`yate/cli.py` 的 `main()`

采用**两阶段初始化**，兼顾"启动早期也可观测"与"yaterc 优先级"：

```python
def main(argv=None):
    from yate import crash
    crash.install()

    from yate import tracing
    tracing.install()          # 阶段 1：仅读环境变量（零配置、立即可用）

    parser = build_parser()
    args = parser.parse_args(argv)
    # ... 早期退出命令（--version 等）不变 ...

    # cleanup_defaults 分支（cli.py:200-218）：tracing.uninstall() 与 crash.uninstall()
    # 平级，都在 if args.include_data: 块内——只有用户明确要删 data/ 才关 handler
    if args.cleanup_defaults:
        if args.include_data:
            crash.uninstall()
            tracing.uninstall()    # 释放 logs/ 下的打开句柄，否则 Windows 阻塞删除
        # ... 其余 cleanup 流程不变 ...

    config = load_config(rc_paths)
    tracing.install(config=config)   # 阶段 2：合并 yaterc 值（env 已定的不覆盖）
```

- 阶段 1 让 `YATE_TRACE=1 yate file` 也能捕获 rc 解析、主题加载阶段的日志
- `install()` 的参数设计：`install(config: YateConfig | None = None)`；
  `config is None` 时只看 env；传入时按 2.2 的优先级合并，且**env 显式设置
  的项不被 rc 覆盖**（第二次调用只补全/调整，已由 env 决定的开关不翻转）
- `--cleanup-defaults --include-data` 路径：`tracing.uninstall()` 与
  `crash.uninstall()` 平级、同条件（`if args.include_data:`），因为 tracing
  只写 `logs/` 下内容；非 include-data 清理不动 handler（和 crash 同哲学）

### 2.6 配置系统变更：`yate/config.py`

1. **`_KNOWN_OPTIONS`**（config.py:48-51 的 tuple）增加两项，紧跟现有项之后：
   ```python
   _KNOWN_OPTIONS = (
       "keymap", "theme", "tab_width", "use_spaces",
       "shell", "terminal_height", "show_hidden",
       "yate_trace", "yate_trace_level",        # ← 新增
   )
   ```
2. **`YateConfig`** dataclass（config.py:77-110）在 `show_hidden` 字段之后、扩展路径字段之前插入：
   ```python
   #: 运行日志开关（默认关闭）。yaterc: yate_trace = True
   yate_trace: bool = False
   #: 运行日志等级，与 logging 内置等级名对齐（默认 DEBUG）。
   yate_trace_level: str = "DEBUG"
   ```
3. **`_extract_options()`**（config.py:306 起）在 `tab_width` 校验块之后按同样风格补两段：
   ```python
   yate_trace_val = options.get("yate_trace")
   if yate_trace_val is not None:
       if isinstance(yate_trace_val, bool):
           config.yate_trace = yate_trace_val
       else:
           config.errors.append(
               f"yate_trace must be True or False, got {yate_trace_val!r}"
           )

   yate_trace_level_val = options.get("yate_trace_level")
   if yate_trace_level_val is not None:
       if isinstance(yate_trace_level_val, str) and (
           yate_trace_level_val.strip().upper()
       ) in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
           config.yate_trace_level = yate_trace_level_val.strip().upper()
       else:
           config.errors.append(
               "yate_trace_level must be one of "
               "DEBUG/INFO/WARNING/ERROR/CRITICAL, "
               f"got {yate_trace_level_val!r}"
           )
   ```

### 2.7 初始日志埋点（首批）

不在本次全量铺开，只加**最有调试价值**的种子点，后续按需扩展：

| 模块 | 埋点内容 |
|------|----------|
| `cli.py` | 启动 argv、rc 来源列表、resolved 开关（keymap/theme/trace…） |
| `app.py` | 文档 open/close/save（路径 + 耗时）、退出 |
| `services/extensions.py` | 每个扩展的加载开始/成功/失败（异常栈 `log.exception`） |
| `editor_lsp/manager.py` | server 启动/退出、注册与自动启动决策 |
| `crash.py` | excepthook 触发时同步 `log.exception` 一份（日志与 .err 互为备份） |

统一取 logger 方式：`log = tracing.get_logger(__name__)`（得到 `yate.editor_lsp.manager` 等）。

### 2.8 文档与可观测性配套

- `yate/yaterc.example`：新增注释段示例（默认注释掉）：

```python
# Debug trace log (~/.yate/data/logs/). Off by default; env vars
# YATE_TRACE / YATE_TRACE_LEVEL override these per-session.
# yate_trace = True
# yate_trace_level = "DEBUG"      # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

- `yate/docs/yaterc.en.md` / `yaterc.zh.md`：补选项说明
- CHANGELOG：按项目惯例补条目（en/zh）

---

## 3. 技术要点

### 3.1 与 crash 诊断的关系与区别

| | `crash.py` | `tracing.py` |
|---|---|---|
| 触发 | 始终安装 | 默认关闭 |
| 内容 | 致命错误回溯 | 全运行期时间线 |
| 文件 | `~/.yate/data/crash-*.err`（健康退出即删） | `~/.yate/data/logs/yate-*.log`（保留） |
| 写入者 | faulthandler 直接写 fd / excepthook | `logging.FileHandler` |

两者互补：crash 覆盖"死得难看"，trace 覆盖"活着但不对"。
`logs/` 放在 `data/` 下与 crash 报告同居，`--cleanup-defaults --include-data`
可一并清理。

### 3.2 等级对齐细节

- 开关与等级**相互独立**：`YATE_TRACE=1` 而等级未设 → DEBUG；
  只设 `YATE_TRACE_LEVEL` 而开关未开 → 无操作（等级存而不用）
- 只在 `"yate"` 根 logger 上 `setLevel`；不给子 logger 单独设级，
  保证 `resolve_level` 语义唯一
- 使用 `logging.FileHandler`（非 StreamHandler 包文件对象），
  便于 `close()` 释放 Windows 句柄

### 3.3 健壮性设计

| 风险 | 应对措施 |
|------|----------|
| `logs/` 创建失败 / 文件不可写 | `try/except OSError` → 打印一条 stderr 警告，编辑器照常启动 |
| 重复 `install()` | 幂等：先移除旧 handler 再决定是否附加 |
| 阶段 2 意外翻转 env 已定的开关 | env 返回 `True/False` 时视为"已决定"，rc 值不覆盖；只有 `None` 才采纳 rc |
| Windows 句柄阻塞 `data/` 删除 | `uninstall()` 关闭 handler，cleanup 路径先调用 |
| 日志调用自身抛异常影响编辑 | `logging` 已吞 handler 异常（`raiseExceptions` 场景除外），埋点不放在热路径的关键断言处 |
| 同秒启动多实例文件名冲突 | 追加模式 + 会话头（含 pid） |

### 3.4 性能

默认关闭时 `log.debug(...)` 仅经历 logger 级别判断（`disabled` 快路径），
无格式化、无 I/O；开启后 `FileHandler` 为行内缓冲，编辑器交互路径上的
埋点控制在 INFO 及以下频次（不逐键 debug）。

---

## 4. 实施步骤

### 步骤 1：创建 `yate/tracing.py`

核心骨架：

```python
"""Runtime trace logging for yate (off by default).

Enabled via the YATE_TRACE / YATE_TRACE_LEVEL environment variables or
the yate_trace / yate_trace_level yaterc options; writes timestamped
files under ~/.yate/data/logs/. Best-effort like yate.crash: a broken
logs directory never blocks startup.
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from yate import __version__

LOGGER_NAME = "yate"
LOG_PREFIX = "yate-"
LOG_SUFFIX = ".log"
DEFAULT_LEVEL = "DEBUG"
_LEVEL_NAMES = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_ON_VALUES = {"1", "true", "yes", "on"}
_OFF_VALUES = {"0", "false", "no", "off"}

_logger = logging.getLogger(LOGGER_NAME)
_logger.addHandler(logging.NullHandler())   # 库最佳实践：默认安静
_logger.propagate = False                   # 绝不漏到 root/stderr 污染 TUI


def logs_dir() -> Path:
    """Return (creating if needed) ~/.yate/data/logs/.

    Reuses :func:`yate.crash.crash_data_dir` so tracing lives under the
    same root as crash reports (``--cleanup-defaults --include-data``
    removes both; user-setup creates ``data/``).
    """
    from yate import crash as _crash  # 只在第一次被调用时 import

    directory = _crash.crash_data_dir() / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_logger(suffix: Optional[str] = None) -> logging.Logger:
    """The shared 'yate' logger, or a child like 'yate.editor_lsp'."""
    if suffix:
        return logging.getLogger(f"{LOGGER_NAME}.{suffix.lstrip('.')}")
    return _logger


def resolve_level(raw: str) -> Optional[int]:
    """Map a level name (case-insensitive) to its logging value."""
    name = raw.strip().upper()
    if name in _LEVEL_NAMES:
        return getattr(logging, name)
    return None


def env_trace() -> Optional[bool]:
    value = os.environ.get("YATE_TRACE", "").strip().lower()
    if not value:
        return None
    if value in _ON_VALUES:
        return True
    if value in _OFF_VALUES:
        return False
    print(f"yate: ignoring unrecognized YATE_TRACE={value!r}", file=sys.stderr)
    return None


def env_level() -> Optional[str]:
    value = os.environ.get("YATE_TRACE_LEVEL", "").strip()
    if not value:
        return None
    if resolve_level(value) is None:
        print(
            f"yate: ignoring unrecognized YATE_TRACE_LEVEL={value!r}",
            file=sys.stderr,
        )
        return None
    return value.upper()


def is_enabled() -> bool:
    return any(
        not isinstance(h, logging.NullHandler) for h in _logger.handlers
    )


def install(config=None) -> bool:
    """(Re)configure tracing from env vars plus an optional YateConfig."""
    trace = env_trace()
    if trace is None and config is not None:
        trace = config.yate_trace
    level_name = env_level() or (
        config.yate_trace_level if config is not None else DEFAULT_LEVEL
    ) or DEFAULT_LEVEL
    level = resolve_level(level_name) or logging.DEBUG

    # 两阶段幂等：阶段 2（config 到位）时如果已有活跃 handler（阶段 1 已开启），
    # 只更新等级、不重建文件——避免阶段 1 和阶段 2 之间的早期日志被丢进 orphan 文件。
    existing = [h for h in _logger.handlers
                if not isinstance(h, logging.NullHandler)]
    if existing and trace:
        existing[0].setLevel(level)
        return True
    # 第一次 install 或之前已关闭：重建。
    for handler in existing:
        _logger.removeHandler(handler)
        handler.close()
    if not trace:
        return False
    try:
        path = logs_dir() / (
            f"{LOG_PREFIX}{datetime.now():%Y%m%d-%H%M%S}{LOG_SUFFIX}"
        )
        handler = logging.FileHandler(
            path, mode="a", encoding="utf-8", delay=False,  # 会话头需要立刻可见
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
        ))
        handler.setLevel(level)
        _logger.addHandler(handler)
        _logger.setLevel(logging.DEBUG)   # 过滤在 handler 上做
    except (OSError, ImportError) as exc:
        print(f"yate: trace log unavailable: {exc}", file=sys.stderr)
        return False

    # 会话头（与 §2.3 格式对齐）——先于任何业务日志，保证 crash 紧接发生时已落盘。
    _logger.info("=== yate %s trace session ===", __version__)
    _logger.info("time: %s", datetime.now().isoformat(timespec='seconds'))
    _logger.info("pid: %d", os.getpid())
    _logger.info("cwd: %s", os.getcwd())
    _logger.info("argv: %r", sys.argv)
    _logger.info("python: %s on %s", sys.version.split()[0], sys.platform)
    _logger.info("trace level: %s", logging.getLevelName(level))
    _logger.info("-" * 48)
    try:
        handler.flush()
    except Exception:
        pass
    return True


def uninstall() -> None:
    """Close and remove file handlers (pre-deletion of ~/.yate/data)."""
    for handler in [h for h in _logger.handlers
                    if not isinstance(h, logging.NullHandler)]:
        _logger.removeHandler(handler)
        handler.close()

# 模块级注册（必须在 uninstall 定义之后——前向引用会 NameError）。
# 默认关闭时卸载幂等（遍历空列表即返回）；cleanup 路径的显式 uninstall()
# 仍是主入口，atexit 只是兜底。
atexit.register(uninstall)
```

要点：

- 根 logger `setLevel(DEBUG)`，**过滤在 handler 上做**——将来加第二个
  handler（如 stderr）可各自设级而互不影响
- `delay=False`：必须立刻打开文件，因为启动后立即写**多行会话头**
  （`=== yate x.y.z trace session ===` / pid / cwd / argv / python
  版本 / 等级 / 分隔线）。写完主动 `handler.flush()`，保证 crash
  紧接发生时头已落盘（`delay=True` 下关闭文件前都不打开，做不到这点）
- **两阶段幂等（cli.py 调用两次）**：已有活跃 handler 时只更新
  `handler.setLevel(level)`，**不关闭、不重建、不重写会话头**——避免
  阶段 1 和阶段 2 之间的早期日志被丢进 orphan 文件；只有第一次 install
  或 handler 已被 uninstall 过时才重建
- **atexit 自动关闭**：模块末尾 `atexit.register(uninstall)`（必须在
  `uninstall` 定义之后——前向引用会 NameError）；默认关闭时 uninstall
  幂等（遍历空列表即返回）；cleanup 路径的显式 `uninstall()` 仍是主入口
- **except 覆盖 ImportError**：`logs_dir()` 里懒 import crash 模块，
  骨架的 try/except 捕获 `(OSError, ImportError)` 而不是只 OSError，
  保证任何 crash 模块故障都不阻断启动（best-effort 承诺）
- `logs_dir()` 内部复用 `yate.crash.crash_data_dir()`，保证 crash
  与 tracing 同居 `~/.yate/data/` 根目录（cleanup 统一删除）

### 步骤 2：修改 `yate/config.py`

按 2.6：`_KNOWN_OPTIONS` 两项、`YateConfig` 两字段、`_extract_options()`
两段校验（`yate_trace` 参照 `use_spaces`，`yate_trace_level` 参照 `keymap`
的枚举校验，大小写不敏感并规范化大写）。

### 步骤 3：修改 `yate/cli.py`

按 2.5：

- `crash.install()` 之后插入阶段 1 `tracing.install()`
- `load_config()` 之后插入阶段 2 `tracing.install(config)`
- `--cleanup-defaults --include-data` 分支的 `crash.uninstall()` 旁加
  `tracing.uninstall()`

### 步骤 4：首批埋点

按 2.7 在 5 个模块加 `tracing.get_logger(__name__)` 埋点
（每处 1–3 行，`log.exception` 用于扩展加载失败）。
`crash.py` 的 `_excepthook` 中追加 `tracing.get_logger().exception(...)`
（包裹在现有 `try/except` 内）。

### 步骤 5：文档与配套

按 2.8：`yaterc.example`、`docs/yaterc.*.md`、CHANGELOG 条目。

### 步骤 6：编写测试 `tests/test_tracing.py`

覆盖（配合现有 `tests/test_isolation.py` 的 HOME 隔离模式，monkeypatch
`Path.home` / env）：

- `resolve_level()`：五个等级名大小写混写正确映射数值；非法值返回 `None`
- `env_trace()`：`1/true/YES/on` → True；`0/false/OFF` → False；未设置/
  空串 → None；垃圾值 → None + stderr 警告（capsys）
- `install()` 关闭路径：默认无文件、`is_enabled()` 为 False、
  对 `get_logger("x").debug(...)` 无任何 stderr 输出（capsys）
- `install()` 开启路径：创建 `logs/` 与 `.log` 文件；写入的记录等级
  低于设定值被过滤、等于/高于被写入；文件名格式正确
- **会话头格式**（与 §2.3 对齐）：开启后立即读文件首行，断言
  `=== yate X.Y.Z trace session ===` 存在、`time:` / `pid:` / `cwd:` /
  `argv:` / `python:` / `trace level:` 各字段齐全
- **flush 后立即可读**：install 返回 True 后立刻 `open(path).read()`
  能看到会话头第一行（证明 flush 生效、不是等关闭才落盘）
- `install()` 幂等：连续两次调用只有一个文件 handler（无重复记录）
- `install(config=...)` 优先级：env=True + rc=False → 开；env=False +
  rc=True → 关；env 未设 + rc=True → 开；rc 非法等级已由 config 层拦截
- `uninstall()`：关闭后 `is_enabled()` 为 False，日志文件可删除
  （Windows 句柄释放）
- **atexit 兜底**：monkeypatch `atexit` 让它立即触发（而不是真等进程退出），
  断言 atexit 注册后 `is_enabled()` 变为 False（测试 `atexit.register(uninstall)`
  路径不依赖真实进程退出）
- `logs_dir()` 创建失败（monkeypatch `mkdir` 抛 `OSError`）→ install 返回 False、
  不抛异常、stderr 有一条警告（capsys）
- `logs_dir()` 依赖 crash.crash_data_dir：monkeypatch `crash.crash_data_dir`
  抛异常 → install 返回 False（tracing 不应该 import crash 模块级，应该懒 import）
- `tests/test_config.py` 增补：`yate_trace` / `yate_trace_level` 的
  合法/非法取值校验与错误消息；`yate_trace` 接受 `bool`、拒绝 `str`；
  `yate_trace_level` 接受大小写混写、拒绝非枚举字符串

---

## 5. 验证方案

### 5.1 单元测试

```powershell
python -m pytest tests/test_tracing.py tests/test_config.py tests/test_cli.py tests/test_crash.py -v
```

### 5.2 环境变量开启（手动）

```powershell
$env:YATE_TRACE = "1"; $env:YATE_TRACE_LEVEL = "DEBUG"
python -m yate README.md
# 退出后检查：
Get-Content "$HOME\.yate\data\logs\yate-*.log" -Tail 20
```

预期：文件含会话头与启动/打开文档记录。

### 5.3 yaterc 开启（手动）

```powershell
# 临时项目 rc：
Set-Content .\yaterc "yate_trace = True`nyate_trace_level = 'INFO'"
python -m yate .
```

预期：日志产生且等级为 INFO（DEBUG 记录被过滤）。

### 5.4 默认关闭验证

```powershell
Remove-Item Env:YATE_TRACE -ErrorAction SilentlyContinue
python -m yate .   # 正常编辑、退出
Test-Path "$HOME\.yate\data\logs"
```

预期：不产生任何新日志文件，TUI 无异常输出。

### 5.5 优先级验证

```powershell
Set-Content .\yaterc "yate_trace = True"
$env:YATE_TRACE = "0"
python -m yate .   # 预期：无日志（env 显式关闭压过 rc）
```

### 5.6 cleanup 路径（Windows 句柄）

```powershell
$env:YATE_TRACE = "1"
python -m yate --cleanup-defaults --include-data --force
```

预期：`data/`（含 `logs/`）删除成功，无 `PermissionError`。

---

## 6. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `yate/tracing.py` | 新增 | 日志核心模块（install/uninstall/get_logger/等级解析） |
| `yate/config.py` | 修改 | `_KNOWN_OPTIONS` + `YateConfig` 两字段 + 校验 |
| `yate/cli.py` | 修改 | 两阶段 `tracing.install()`；cleanup 路径 `tracing.uninstall()` |
| `yate/crash.py` | 修改 | excepthook 内同步写一条 `logger.exception` |
| `yate/app.py` | 修改 | 文档 open/close/save 埋点 |
| `yate/services/extensions.py` | 修改 | 扩展加载埋点 |
| `yate/editor_lsp/manager.py` | 修改 | server 生命周期埋点 |
| `yate/yaterc.example` | 修改 | 新增注释示例段 |
| `yate/docs/yaterc.en.md` / `yaterc.zh.md` | 修改 | 选项文档 |
| `tests/test_tracing.py` | 新增 | 单元测试 |
| `tests/test_config.py` | 修改 | 新选项校验测试 |
| `CHANGELOG.md` / `CHANGELOG.zh.md` | 修改 | 条目 |
| `.trae/documents/logs_impl_plan.md` | 新增 | 本文档 |

---

## 7. 后续可扩展方向

- **保留策略**：启动时清理旧日志，仅保留最近 N 个（如 20 个）文件
- **`:log` 命令 / OutputScreen 查看**：在 TUI 内尾部跟踪当前会话日志
- **per-module 等级**：`yate_trace_level = {"yate.lsp": "DEBUG"}` 或
  `YATE_TRACE_LEVEL="yate.lsp=debug,yate=info"`（logging 支持按 logger 设级）
- **轮转**：改用 `logging.handlers.RotatingFileHandler`（按大小）
- **崩溃联动提示**：下次启动检测到上一次 `crash-*.err` 时自动建议开启 trace
