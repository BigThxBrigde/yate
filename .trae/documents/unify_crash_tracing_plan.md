# Plan: Unified Crash & Tracing Log Module — Independent Objects, Shared Functions

## Goal

Consolidate `yate/crash.py` and `yate/tracing.py` into a single logging module under `yate/services/`, exposing `crash` and `tracing` as independent singleton objects. The two services share nothing but a handful of module-level helper functions. No circular imports, no cross-references between the classes, no `TYPE_CHECKING` guard, no `YateConfig` reference.

## Hard Constraints (from the user's brief)

| # | Rule | How this plan satisfies it |
|---|------|-----------------------------|
| 1 | Unify logging — crash and tracing | Both live in `yate/services/log_services.py`; thin shells `yate/crash.py` and `yate/tracing.py` re-export from it |
| 2 | Add a logging module under `services/`, expose `crash` and `tracing` objects | `yate/services/log_services.py` exposes `crash = CrashService()` and `tracing = TracingService()` as module-level singletons |
| 3 | Crash and tracing functionality stays unchanged | `install()`, `uninstall()`, `get_logger()`, excepthook chain, faulthandler enable, atexit cleanup, lazy file open, header format — all preserved 1:1 |
| 4 | No circular dependencies | `log_services.py` imports only stdlib + `yate.__version__`; no import of `yate.config`, no import between `CrashService` and `TracingService` |
| 5 | Crash and tracing are independent — no references between them | The current `tracing.get_logger("crash").error(...)` call inside `_excepthook` is **deleted**. The two classes never reference each other |
| 6 | Common methods can be written as functions | Shared helpers (`warn`, `build_session_header`, `crash_data_dir`, `logs_dir`) are **module-level functions**, not `@staticmethod` and not an ABC. No `LogService` base class |
| 7 | Remove `YateConfig` reference entirely — pass `yate_trace` and `yate_trace_level` as two separate scalars | `install(yate_trace: Optional[bool], yate_trace_level: Optional[str])` — the level string is resolved to int inside `install()` via `resolve_level()`, not at the call site. cli.py passes `config.yate_trace` and `config.yate_trace_level` directly. |
| 8 | `tracing` exposes a `configure()` method matching `install()`'s signature | `configure(yate_trace, yate_trace_level)` is a thin alias for `install(...)`, used at the rc-stage re-config to make intent clear. |

---

## Current State (What We're Refactoring)

### `yate/tracing.py` (303 lines)

Module-level state and functions, plus one private class:

- Constants: `LOGGER_NAME`, `_DATA_DIRNAME`, `LOG_DIRNAME`, `LOG_PREFIX`, `LOG_SUFFIX`, `DEFAULT_LEVEL`, `LEVEL_NAMES`, `TRUE_VALUES`, `FALSE_VALUES`
- Module-level state: `_logger = logging.getLogger(LOGGER_NAME)` (with `NullHandler`)
- Pure functions: `logs_dir()`, `get_logger(name)`, `resolve_level(raw)`, `is_enabled()`, `current_log_path()`, `env_trace()`, `env_level()`
- Private helpers: `_file_handlers()`, `_warn(message)`, `_requested_level(config)`, `_session_header(level)`
- Private class: `_SessionFileHandler(logging.FileHandler)` — lazy-open + header-on-first-emit
- `install(config: Optional["YateConfig"] = None) -> bool` — two-phase install (env-only pass 1, env+rc pass 2)
- `uninstall() -> None`
- `TYPE_CHECKING` guard imports `YateConfig` for the `install()` signature only

### `yate/crash.py` (179 lines)

Module-level state and functions:

- Constants: `DATA_DIRNAME`, `ERR_PREFIX`, `ERR_SUFFIX`, `_HEADER_RULE`
- Module-level state: `_err_file`, `_err_path`, `_crashed`, `_original_excepthook`
- Pure functions: `crash_data_dir()`, `current_crash_file()`, `_err_file_path(directory, now)`, `_write_header(handle)`, `_excepthook(...)`, `_cleanup_on_exit()`, `uninstall()`, `install()`
- **Imports `tracing`** and calls `tracing.get_logger("crash").error(...)` inside `_excepthook` (lines 102–110) — this is the only crash → tracing coupling

### External Call Sites

| File | Uses |
|------|------|
| `yate/cli.py` | `crash.install()`, `crash.uninstall()`, `tracing.install()`, `tracing.configure(yate_trace=..., yate_trace_level=...)`, `tracing.uninstall()`, `tracing.get_logger("cli")` |
| `yate/config.py` | `tracing.LEVEL_NAMES`, `tracing.DEFAULT_LEVEL` (constants only) |
| `yate/diagnostics.py` | `crash.crash_data_dir()`, `crash.current_crash_file()` |
| `yate/app.py` | `tracing.get_logger(__name__)` |
| `yate/editor_lsp/manager.py` | `tracing.get_logger(__name__)` |
| `yate/services/extensions.py` | `tracing.get_logger(__name__)` |
| `yate/crash.py` | `tracing.get_logger("crash").error(...)` — **the call being deleted** |

### Test Usage of Private Names

- `tests/test_crash.py`: `crash._err_file`, `crash._err_path`, `crash._crashed`, `crash._original_excepthook`, `crash._cleanup_on_exit()`, `crash._err_file_path()`
- `tests/test_tracing.py`: `tracing._logger`, `tracing._file_handlers()`, `tracing._requested_level()`, plus `YateConfig(yate_trace=...)` passed to `install()`

---

## Target File Layout

```
yate/
├── services/
│   ├── __init__.py          ← MODIFY: add exports for crash, tracing, CrashService, TracingService
│   └── log_services.py      ← NEW: constants + functions + CrashService + TracingService + SessionFileHandler + singletons
├── crash.py                 ← MODIFY: thin shell re-exporting from services.log_services
├── tracing.py               ← MODIFY: thin shell re-exporting from services.log_services, ZERO TYPE_CHECKING
├── cli.py                   ← MODIFY: pass 2 calls install(yate_trace=..., yate_trace_level=...)
├── diagnostics.py           ← NO CHANGE (resolves via thin shell)
├── config.py                ← NO CHANGE (reads tracing.LEVEL_NAMES / tracing.DEFAULT_LEVEL via thin shell)
├── app.py                   ← NO CHANGE
├── editor_lsp/manager.py    ← NO CHANGE
└── services/extensions.py   ← NO CHANGE

tests/
├── test_crash.py            ← MODIFY: ._xxx → .xxx public names, drop tracing mirror assertion if any
└── test_tracing.py          ← MODIFY: drop YateConfig; install(yate_trace=..., yate_trace_level=str); rename privates
```

---

## Dependency Graph (After — Zero Coupling)

```
cli.py ──► yate.crash (thin shell) ──► yate.services.log_services ──► (stdlib + yate.__version__ only)
cli.py ──► yate.tracing (thin shell) ──► yate.services.log_services
config.py ──► yate.tracing (constants only)
diagnostics.py ──► yate.crash
app.py ──► yate.tracing
editor_lsp/manager.py ──► yate.tracing
services/extensions.py ──► yate.tracing

yate/services/log_services.py:
  ├── MODULE LEVEL — constants + pure functions (shared by both classes)
  │     LOGGER_NAME, LEVEL_NAMES, DEFAULT_LEVEL, TRUE_VALUES, FALSE_VALUES
  │     DATA_DIRNAME, LOG_DIRNAME, LOG_PREFIX, LOG_SUFFIX, ERR_PREFIX, ERR_SUFFIX
  │     warn(), build_session_header(), resolve_level(), env_trace(), env_level(),
  │     logs_dir(), crash_data_dir()
  │
  ├── SessionFileHandler          (public class — used by TracingService only)
  ├── CrashService                (no reference to TracingService — self-contained)
  ├── TracingService              (no reference to CrashService — self-contained)
  ├── crash = CrashService()      singleton
  └── tracing = TracingService()  singleton

  ⚠️  No ABC. No TYPE_CHECKING. No YateConfig. No import between CrashService and TracingService.
```

---

## Module-Level Constants & Pure Functions

These live at module scope in `log_services.py`. Call sites are unchanged: `tracing.LEVEL_NAMES` resolves via the thin shell's `from ... import LEVEL_NAMES`; `tracing.resolve_level(...)` resolves via the thin shell's `from ... import resolve_level`. Same for `crash.crash_data_dir()`.

```python
# ==============================================================
# Constants — consumed directly by config.py, cli.py, etc.
# ==============================================================

#: Root logger name; every yate logger is ``yate`` or a child of it.
LOGGER_NAME = "yate"

#: Accepted level names -- :mod:`logging`'s built-ins, in increasing order.
LEVEL_NAMES: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

#: Level used when tracing is enabled without an explicit level.
DEFAULT_LEVEL = "DEBUG"

#: Accepted spellings of ``YATE_TRACE`` (compared lower-cased).
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})

#: ``~/.yate/data`` parent and ``~/.yate/data/logs`` child.
DATA_DIRNAME = "data"
LOG_DIRNAME = "logs"

#: Filename stems/suffixes for the two services.
LOG_PREFIX = "yate-"
LOG_SUFFIX = ".log"
ERR_PREFIX = "crash-"
ERR_SUFFIX = ".err"


# ==============================================================
# Pure functions — no state, no class needed (constraint #6)
# ==============================================================

def warn(message: str) -> None:
    """Print ``yate: ...`` to stderr. Never raises."""
    print(f"yate: {message}", file=sys.stderr)


def build_session_header(
    *,
    service_name: str,
    extra_lines: Optional[dict[str, str]] = None,
) -> str:
    """Standard process-metadata header used by both crash and tracing.

    *service_name* appears in the title line as ``yate <version> <service_name>``.
    *extra_lines* (optional) is appended as ``key: value`` rows before the
    rule. Both crash and tracing pass their own extras (pid, trace level, …).
    """
    lines: list[str] = [
        f"yate {__version__} {service_name}",
        f"time: {datetime.now().isoformat(timespec='seconds')}",
        f"cwd: {os.getcwd()}",
        f"argv: {sys.argv!r}",
        f"python: {sys.version.split()[0]} on {sys.platform}",
    ]
    if extra_lines:
        for key, value in extra_lines.items():
            lines.append(f"{key}: {value}")
    lines.append("-" * 60)
    return "\n".join(lines) + "\n"


def resolve_level(raw: str) -> Optional[int]:
    """Map a level name to its :mod:`logging` value; ``None`` if unknown."""
    name = raw.strip().upper()
    if name not in LEVEL_NAMES:
        return None
    return int(getattr(logging, name))


def env_trace() -> Optional[bool]:
    """``YATE_TRACE`` decoded; ``None`` when unset (or unrecognizable)."""
    value = os.environ.get("YATE_TRACE", "").strip().lower()
    if not value:
        return None
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    warn(f"ignoring unrecognized YATE_TRACE={value!r}")
    return None


def env_level() -> Optional[str]:
    """``YATE_TRACE_LEVEL`` normalized to upper case; ``None`` if unset/invalid."""
    value = os.environ.get("YATE_TRACE_LEVEL", "").strip()
    if not value:
        return None
    if resolve_level(value) is None:
        warn(f"ignoring unrecognized YATE_TRACE_LEVEL={value!r}")
        return None
    return value.upper()


def logs_dir() -> Path:
    """Return (creating if needed) ``~/.yate/data/logs/``."""
    directory = Path.home() / ".yate" / DATA_DIRNAME / LOG_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def crash_data_dir() -> Path:
    """Return (creating if needed) ``~/.yate/data/``."""
    directory = Path.home() / ".yate" / DATA_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory
```

### Why these are functions, not class methods

Per constraint #6, shared pure logic stays at module level. `crash_data_dir()` and `logs_dir()` are pure directory resolvers; `resolve_level()` is a pure mapping; `env_trace()` / `env_level()` are pure env readers; `warn()` is a pure stderr printer; `build_session_header()` is a pure string builder. None of them need instance state, so none of them belong on a class.

The thin shells re-export them by name, so every existing call site (`tracing.resolve_level(...)`, `crash.crash_data_dir()`, `tracing.LEVEL_NAMES`) keeps working — Python attribute lookup on a module finds them.

---

## CrashService — Self-Contained, Zero Dependencies

```python
class CrashService:
    """Best-effort crash diagnostics for one yate process.

    Eagerly opens ``~/.yate/data/crash-*.err`` at install time, writes a
    metadata header, points :mod:`faulthandler` at the fd, and wraps
    ``sys.excepthook`` to append uncaught Python tracebacks. Atexit deletes
    a header-only report on healthy shutdown.

    Self-contained: does not import or reference :class:`TracingService`.
    """

    def __init__(self) -> None:
        self._err_file: Optional[TextIO] = None
        self._err_path: Optional[Path] = None
        self._crashed: bool = False
        self._original_excepthook = sys.excepthook

    # --- public read-only state (was module-level _underscore names) ---

    @property
    def err_file(self) -> Optional[TextIO]:
        """Open crash report handle, or None when not installed."""

    @property
    def err_path(self) -> Optional[Path]:
        """Path of the open crash report, or None."""

    @property
    def had_crash(self) -> bool:
        """True once an uncaught exception has been logged."""

    @property
    def original_excepthook(self) -> Callable[..., Any]:
        """The sys.excepthook that was installed before us (for chaining)."""

    # --- public lifecycle ---

    def install(self) -> None:
        """Enable on-disk crash diagnostics. Idempotent and best-effort.

        Preserves the exact behavior of yate/crash.py:install(): eager open,
        header write, faulthandler.enable(file=handle, all_threads=True),
        stderr fallback on OSError, atexit registration, sys.excepthook wrap.
        """

    def uninstall(self) -> None:
        """Release the open report and disable faulthandler. Idempotent."""

    def current_path(self) -> Optional[Path]:
        """Path of this process's in-progress crash report, or None."""

    def current_crash_file(self) -> Optional[Path]:
        """Alias for :meth:`current_path` (kept for diagnostics.py)."""

    def is_enabled(self) -> bool:
        """True while the report file is open."""

    # --- public helpers (used by tests; some mirror module-level fns) ---

    def build_err_path(
        self, directory: Path, now: Optional[datetime] = None
    ) -> Path:
        """Build ``crash-YYYYMMDD-HHMMSS.err`` inside *directory*."""

    def cleanup_on_exit(self) -> None:
        """Close + optionally delete the report. Public for atexit testing."""
```

### What changes vs the original `yate/crash.py`

| Item | Decision |
|------|----------|
| `tracing.get_logger("crash").error(...)` call inside `_excepthook` (lines 102–110) | **DELETED.** This is the only crash → tracing coupling; removing it satisfies constraint #5. The excepthook still writes the traceback to `.err` and chains to the original hook — the crash-specific behavior is unchanged. |
| Module-level `_err_file`, `_err_path`, `_crashed`, `_original_excepthook` | Move to instance attributes on `CrashService`. Exposed via `@property` for tests (public names). |
| Module-level `_err_file_path()`, `_cleanup_on_exit()`, `_excepthook()`, `_write_header()` | Become instance methods `build_err_path()`, `cleanup_on_exit()`, `_excepthook_impl()` (private — only the public-rename ones go public), and `_write_header()` stays private. |
| `_write_header(handle)` writing directly to the handle | Calls `build_session_header(service_name="crash report")` and writes the returned string. Same output bytes. |
| `crash_data_dir()` (module-level) | Stays **module-level** (constraint #6: common methods as functions). The class does not re-implement it; the thin shell re-exports the module-level function. |
| `install()` return type | Stays `None` (current behavior, constraint #3). |

### What stays exactly the same

- `faulthandler.enable(file=handle, all_threads=True)` on the open fd
- stderr fallback when the data directory is unwritable
- `sys.excepthook` wrap + chaining to the saved original
- `atexit.register(cleanup_on_exit)` for healthy-shutdown file deletion
- `_crashed` flag so a logged exception keeps the file
- Idempotent `install()` / `uninstall()`

---

## TracingService — Lazy, Opt-In, Zero Dependencies

```python
class TracingService:
    """Runtime trace log for one yate process. Off by default.

    Two-phase install in cli.py:
        tracing.install()                                          # pass 1: env
        ... load_config() ...
        tracing.configure(                                          # pass 2: merge rc
            yate_trace=config.yate_trace,
            yate_trace_level=config.yate_trace_level,
        )

    Self-contained: does not import or reference :class:`CrashService`.
    No ``YateConfig`` reference — the two yaterc fields are passed as
    separate scalars (a bool and a level-name string); ``install()``
    resolves the level string to an int internally via
    :func:`resolve_level`.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(LOGGER_NAME)
        self._logger.addHandler(logging.NullHandler())
        self._logger.propagate = False

    # --- public state ---

    @property
    def root_logger(self) -> logging.Logger:
        """The shared ``yate`` logger (was module-level _logger)."""

    # --- public lifecycle ---

    def install(
        self,
        yate_trace: Optional[bool] = None,
        yate_trace_level: Optional[str] = None,
    ) -> bool:
        """(Re)configure tracing and return whether it is on.

        Env vars (``YATE_TRACE`` / ``YATE_TRACE_LEVEL``) always win when
        present. *yate_trace* / *yate_trace_level* are yaterc fallbacks
        (``None`` = not set). A second call keeps the file opened by the
        first and only adjusts the level.

        Level resolution order (mirrors the original ``_requested_level``):
            1. ``YATE_TRACE_LEVEL`` env var (if set and valid)
            2. *yate_trace_level* parameter (yaterc value, a string)
            3. :data:`DEFAULT_LEVEL` (``"DEBUG"``)
        The chosen string is passed through :func:`resolve_level` to get
        the int level. A falsy result (``0`` = ``logging.NOTSET``) is
        preserved with an explicit ``None`` test, not ``or``.
        """

    def configure(
        self,
        yate_trace: Optional[bool] = None,
        yate_trace_level: Optional[str] = None,
    ) -> None:
        """Alias for :meth:`install` — semantic sugar for the rc-stage re-config.

        Same parameters, same behavior; the only difference is that callers
        at the rc-loaded stage (cli.py pass 2) use ``configure()`` to make
        the intent obvious, while the pre-config pass 1 uses ``install()``
        with no arguments.
        """

    def uninstall(self) -> None:
        """Detach and close file handlers (before deleting ~/.yate/data)."""

    def current_path(self) -> Optional[Path]:
        """Path of this session's log file, or None when tracing is off."""

    def current_log_path(self) -> Optional[Path]:
        """Alias for :meth:`current_path` (kept for external callers)."""

    def is_enabled(self) -> bool:
        """True while a log file handler is attached."""

    # --- logger tree (TracingService-only; crash has no logger) ---

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """The shared ``yate`` logger, or a child of it."""

    # --- public helpers (used by tests) ---

    def file_handlers(self) -> list[logging.FileHandler]:
        """Active FileHandler instances attached to root_logger."""
```

### What changes vs the original `yate/tracing.py`

| Item | Decision |
|------|----------|
| `TYPE_CHECKING` guard importing `YateConfig` | **DELETED.** `install()` takes `Optional[bool]` / `Optional[str]` scalars. No `YateConfig` reference anywhere. |
| `install(config: Optional[YateConfig]) -> bool` | Becomes `install(yate_trace=None, yate_trace_level=None) -> bool`. The body merges the old `_requested_level(config)` logic inline: env wins; else `yate_trace_level` parameter (a string); else `DEFAULT_LEVEL`. The chosen string is resolved to an int inside `install()` via `resolve_level()`. |
| New `configure()` method | **ADDED.** Thin alias: `def configure(self, yate_trace=None, yate_trace_level=None) -> None: self.install(yate_trace=yate_trace, yate_trace_level=yate_trace_level)`. Used at cli.py pass 2 for intent clarity. |
| Module-level `_logger = logging.getLogger(LOGGER_NAME)` | Moves to `TracingService.__init__`. Exposed via `root_logger` property. |
| Module-level `_file_handlers()`, `_warn()`, `_session_header()`, `_requested_level()` | `_file_handlers()` becomes the public `file_handlers()` method. `_warn()` becomes a call to the module-level `warn()` function. `_session_header(level)` becomes a call to `build_session_header(service_name="trace session", extra_lines={"pid": ..., "trace level": ...})`. `_requested_level()` is inlined into `install()` (logic is small). |
| Module-level `_SessionFileHandler` | Becomes public `SessionFileHandler` (used by tests and by TracingService). Logic unchanged: `delay=True`, header-on-first-emit, `handleError` on OSError. |
| Module-level `logs_dir()`, `resolve_level()`, `env_trace()`, `env_level()`, `get_logger(name)` | `logs_dir`, `resolve_level`, `env_trace`, `env_level` stay **module-level** (constraint #6). `get_logger` becomes an instance method (it needs `self._logger`). The thin shell re-exports the module-level functions; callers doing `tracing.resolve_level(...)` work via the shell. |

### What stays exactly the same

- `NullHandler` attached at construction so library calls never leak to the root logger
- `propagate = False` on the `yate` logger
- Lazy file open (`delay=True`) — `YATE_TRACE=1 yate --version` leaves no empty file
- Header-on-first-emit via the `SessionFileHandler.emit` override
- Two-phase install idempotency (second call keeps file, adjusts level)
- Env-var precedence over yaterc
- `DEFAULT_LEVEL = "DEBUG"` when no level is specified
- `OSError` on directory creation → warn to stderr and return False (editor still starts)

---

## Private → Public Rename Mapping

| Was private (module-level `_xxx`) | Becomes public (on the class) | Accessed by |
|----------------------------------|-------------------------------|-------------|
| `crash._err_file` | `crash.err_file` (`@property`) | `tests/test_crash.py` (×8) |
| `crash._err_path` | `crash.err_path` (`@property`) | `tests/test_crash.py` (×2) |
| `crash._crashed` | `crash.had_crash` (`@property`) | `tests/test_crash.py` (×1) |
| `crash._original_excepthook` | `crash.original_excepthook` (`@property`) | `tests/test_crash.py` (×5) |
| `crash._cleanup_on_exit()` | `crash.cleanup_on_exit()` (method) | `tests/test_crash.py` (×2) |
| `crash._err_file_path()` | `crash.build_err_path()` (method) | `tests/test_crash.py` (×2) |
| `tracing._logger` | `tracing.root_logger` (`@property`) | `tests/test_tracing.py` (×1) |
| `tracing._file_handlers()` | `tracing.file_handlers()` (method) | `tests/test_tracing.py` (×2) |
| `tracing._SessionFileHandler` | `SessionFileHandler` (public class) | `tests/test_tracing.py` |
| `tracing._requested_level()` | **REMOVED** — inlined into `install()` | `tests/test_tracing.py` (×1) — see note below |

**Note on `_requested_level()`**: it existed only to resolve env + config priority. After the refactor, `install()` does this inline (env wins; else `yate_trace_level` param; else `DEFAULT_LEVEL`). The test `test_requested_level_keeps_a_falsy_resolution` exercises the corner case where `resolve_level` returns `0` (`logging.NOTSET`) — a scenario no real yaterc config produces. **Delete the test**; it's low-value and its setup (`monkeypatch.setattr(tracing, "resolve_level", _zero_level)`) breaks once `resolve_level` is a re-exported module function.

---

## Thin Shell Files

### `yate/crash.py` — re-export from `services.log_services`

```python
"""Thin shell. Re-exports the crash singleton and module-level helpers
from :mod:`yate.services.log_services`. See that module for the real
implementation.
"""
from __future__ import annotations

from yate.services.log_services import (
    DATA_DIRNAME,
    ERR_PREFIX,
    ERR_SUFFIX,
    CrashService,
    crash,
    crash_data_dir,
)

__all__ = [
    "crash",
    "CrashService",
    "DATA_DIRNAME",
    "ERR_PREFIX",
    "ERR_SUFFIX",
    "crash_data_dir",
]
```

### `yate/tracing.py` — re-export from `services.log_services`, ZERO `TYPE_CHECKING`

```python
"""Thin shell. Re-exports the tracing singleton and module-level helpers
from :mod:`yate.services.log_services`. See that module for the real
implementation.
"""
from __future__ import annotations

from yate.services.log_services import (
    DEFAULT_LEVEL,
    FALSE_VALUES,
    LEVEL_NAMES,
    LOGGER_NAME,
    LOG_DIRNAME,
    LOG_PREFIX,
    LOG_SUFFIX,
    SessionFileHandler,
    TRUE_VALUES,
    TracingService,
    env_level,
    env_trace,
    logs_dir,
    resolve_level,
    tracing,
)

__all__ = [
    "tracing",
    "TracingService",
    "SessionFileHandler",
    "LOGGER_NAME",
    "LEVEL_NAMES",
    "DEFAULT_LEVEL",
    "TRUE_VALUES",
    "FALSE_VALUES",
    "LOG_DIRNAME",
    "LOG_PREFIX",
    "LOG_SUFFIX",
    "logs_dir",
    "resolve_level",
    "env_trace",
    "env_level",
]
```

### Why this works without code changes elsewhere

- `from yate import crash, tracing` — unchanged: returns the thin-shell modules
- `crash.install()`, `crash.uninstall()` — resolves to the `crash` singleton's methods
- `tracing.install()`, `tracing.install(yate_trace=..., yate_trace_level=...)`, `tracing.configure(yate_trace=..., yate_trace_level=...)` — singleton methods
- `tracing.get_logger(__name__)` — singleton method
- `tracing.LEVEL_NAMES`, `tracing.DEFAULT_LEVEL` — module-level constants re-exported by the shell
- `tracing.resolve_level(...)`, `tracing.env_trace()`, `tracing.env_level()` — module-level functions re-exported
- `crash.crash_data_dir()` — module-level function re-exported
- `crash.current_crash_file()`, `tracing.current_log_path()` — singleton methods (kept as aliases)

Zero `TYPE_CHECKING` in either shell — they're pure re-exports.

---

## Call Site Changes

### `yate/cli.py` — pass 2 signature

```python
# Pass 1: unchanged
crash.install()
tracing.install()

# Pass 2: OLD tracing.install(config) → NEW explicit scalars (level is a
# string; install() resolves it to an int internally).
tracing.configure(
    yate_trace=config.yate_trace,
    yate_trace_level=config.yate_trace_level,
)
```

No `resolve_level` call at the cli.py site — `install()` does it internally. cli.py does not need to import `resolve_level`.

### `yate/diagnostics.py` — 0 change ✅

Calls `crash.crash_data_dir()` (module-level function re-exported by the shell) and `crash.current_crash_file()` (singleton method). Both resolve.

### `yate/config.py` — 0 change ✅

Reads `tracing.LEVEL_NAMES` and `tracing.DEFAULT_LEVEL` (module-level constants re-exported by the shell).

### `yate/app.py`, `yate/editor_lsp/manager.py`, `yate/services/extensions.py` — 0 change ✅

All call `tracing.get_logger(__name__)` — singleton method on `TracingService`.

---

## Task Breakdown

### Task 1: Create `yate/services/log_services.py` — Core Implementation
- **Priority**: P0
- **Scope**:
  1. Module docstring + `from __future__ import annotations`
  2. Stdlib imports only: `atexit`, `faulthandler`, `logging`, `os`, `sys`, `traceback`, `datetime`, `pathlib.Path`, `types.TracebackType`, `typing.{Optional, TextIO, IO, Callable, Any}`
  3. `from yate import __version__` — the only project-internal import
  4. Module-level constants (see section above)
  5. Module-level pure functions: `warn`, `build_session_header`, `resolve_level`, `env_trace`, `env_level`, `logs_dir`, `crash_data_dir`
  6. `SessionFileHandler` class — move verbatim from `yate/tracing.py`, rename `_SessionFileHandler` → `SessionFileHandler`, replace the `_session_header(level)` call inside `emit()` with a `build_session_header(...)` call (or keep a private `_session_header(level)` helper that wraps it — either works; the bytes must be identical)
  7. `CrashService` class — instance state via `@property`, `install()`, `uninstall()`, `current_path()`/`current_crash_file()`, `is_enabled()`, `build_err_path()`, `cleanup_on_exit()`. Private `_excepthook_impl()` (was `_excepthook`) and `_write_header()` (or call `build_session_header` directly). **No `tracing.get_logger("crash").error(...)` call anywhere.**
  8. `TracingService` class — `__init__` builds `_logger` with `NullHandler`, `install(yate_trace, yate_trace_level)` (level is a string, resolved internally via `resolve_level()`), `configure(yate_trace, yate_trace_level)` (alias for `install()`), `uninstall()`, `current_path()`/`current_log_path()`, `is_enabled()`, `get_logger(name)`, `file_handlers()`. Inline the `_requested_level` logic into `install()`.
  9. Module-level singletons: `crash = CrashService()` and `tracing = TracingService()`. **No injection line.** The two are independent.
- **Verification**:
  - `pyright yate/services/log_services.py` → zero diagnostics (strict mode)
  - `grep -n "TYPE_CHECKING" yate/services/log_services.py` → no matches
  - `grep -n "YateConfig" yate/services/log_services.py` → no matches
  - `grep -n "TracingService" yate/services/log_services.py` inside the `class CrashService` body → no matches (and vice versa)

### Task 2: Thin Shells `yate/crash.py` and `yate/tracing.py`
- **Priority**: P0
- **Scope**: Replace the current 179-line and 303-line implementations with the thin shells shown above. Preserve the module docstring (shortened to point at `log_services`).
- **Verification**:
  - `from yate import crash, tracing` works
  - `tracing.LEVEL_NAMES`, `tracing.DEFAULT_LEVEL`, `tracing.resolve_level("DEBUG")`, `tracing.env_trace()`, `tracing.logs_dir()`, `crash.crash_data_dir()` all resolve
  - `grep -n "TYPE_CHECKING" yate/tracing.py yate/crash.py` → no matches

### Task 3: Update `yate/cli.py` — Pass 2 Signature
- **Priority**: P0
- **Scope**: Change `tracing.install(config)` (line 257) to `tracing.configure(yate_trace=config.yate_trace, yate_trace_level=config.yate_trace_level)`. No `resolve_level` import needed at the call site — `install()` does it internally.
- **Verification**: `pyright yate/cli.py` → zero diagnostics

### Task 4: Rewrite `tests/test_crash.py` — Public Names
- **Priority**: P0
- **Scope**:
  1. Search-and-replace within the file:
     - `crash._err_file` → `crash.err_file`
     - `crash._err_path` → `crash.err_path`
     - `crash._crashed` → `crash.had_crash`
     - `crash._original_excepthook` → `crash.original_excepthook`
     - `crash._cleanup_on_exit` → `crash.cleanup_on_exit`
     - `crash._err_file_path` → `crash.build_err_path`
  2. Update the `_reset_crash_module()` fixture: it currently mutates module-level `_err_file = None` etc. After refactor, the state is on the `crash` singleton. Reset via `crash._err_file = None` (instance attribute, still settable from tests because `# pyright: reportPrivateUsage=false` is at the top of the file) — or expose a `crash._reset()` helper for tests. Recommended: keep the `reportPrivateUsage=false` pragma and assign directly to the instance attributes — the public properties still read them.
  3. No `tracing` import needed anymore in `tests/test_crash.py` (the mirror call is gone; no test asserted it).
- **Verification**: `pytest tests/test_crash.py -q` → all tests pass

### Task 5: Rewrite `tests/test_tracing.py` — Remove `YateConfig`, Public Names
- **Priority**: P0
- **Scope**:
  1. Delete `from yate.config import YateConfig`
  2. Replace every `tracing.install(YateConfig(yate_trace=..., yate_trace_level=...))` with the new signature (level stays as a string):
     - `YateConfig(yate_trace=True)` → `tracing.install(yate_trace=True)`
     - `YateConfig(yate_trace=False)` → `tracing.install(yate_trace=False)`
     - `YateConfig(yate_trace=True, yate_trace_level="ERROR")` → `tracing.install(yate_trace=True, yate_trace_level="ERROR")`
     - Same pattern for `"WARNING"`, `"DEBUG"`, `"INFO"` — all pass as strings, no `logging.ERROR` int conversion at the test site
  3. Delete `test_requested_level_keeps_a_falsy_resolution` (the `_requested_level` helper is gone; the test exercises a corner case no real config produces)
  4. `tracing._logger` → `tracing.root_logger`
  5. `tracing._file_handlers()` → `tracing.file_handlers()`
  6. `tracing.get_logger() is tracing._logger` → `tracing.get_logger() is tracing.root_logger`
- **Verification**: `pytest tests/test_tracing.py -q` → all tests pass

### Task 6: Update `yate/services/__init__.py`
- **Priority**: P2
- **Scope**: Add exports for the two singletons and the two classes:
  ```python
  from yate.services.log_services import CrashService, TracingService, crash, tracing
  ```
  Append `crash`, `tracing`, `CrashService`, `TracingService` to `__all__`.
- **Verification**: `from yate.services import crash, tracing, CrashService, TracingService` works

---

## Verification Matrix

| # | Step | Command | Expected |
|---|------|---------|----------|
| 1 | No `TYPE_CHECKING` in new code | `grep -n "TYPE_CHECKING" yate/services/log_services.py yate/crash.py yate/tracing.py` | 0 matches |
| 2 | No `YateConfig` reference in services | `grep -n "YateConfig" yate/services/log_services.py yate/crash.py yate/tracing.py yate/cli.py` | 0 matches |
| 3 | No cross-reference between classes | `grep -n "CrashService" yate/services/log_services.py` inside `class TracingService` body (and vice versa) | 0 matches in either class body |
| 4 | No `yate.config` import in services | `grep -n "from yate.config" yate/services/log_services.py` | 0 matches |
| 5 | Strict pyright | `pyright yate/` | Zero diagnostics |
| 6 | Crash tests | `pytest tests/test_crash.py -q` | All pass |
| 7 | Tracing tests | `pytest tests/test_tracing.py -q` | All pass |
| 8 | Full test suite | `pytest tests/ -q` | All pass |
| 9 | Smoke: `--version` with env trace | `YATE_TRACE=1 yate --version` | Instant exit, no log file (lazy open) |
| 10 | Smoke: normal startup | `YATE_TRACE=1 yate` → quit | `.log` file under `~/.yate/data/logs/` |
| 11 | Smoke: crash file on uncaught exception | trigger an uncaught exception in a test run | `.err` file under `~/.yate/data/` is kept |
| 12 | Smoke: cleanup | `yate --cleanup-defaults --include-data` | `data/` fully removed |
| 13 | Smoke: crash no longer mirrors to trace log | `grep "uncaught" ~/.yate/data/logs/*.log` after a crash | 0 matches (the mirror call is gone) |
| 14 | Smoke: `configure()` works | `YATE_TRACE=1 yate` (cli pass 2 calls `configure`) | Log file created with correct level |

---

## Practical Suggestions for Optimizing Task Execution

1. **Build bottom-up**: module-level constants → module-level functions → `SessionFileHandler` → `CrashService` → `TracingService` → singletons → thin shells → cli.py → tests. Each layer imports cleanly from the one above, so a partial implementation still produces a working import chain and surfaces errors early.

2. **Copy `SessionFileHandler` verbatim** from `yate/tracing.py` (lines 144–201). Its `delay=True` + header-on-first-emit logic is subtle; do not refactor it. The only rename is `_SessionFileHandler` → `SessionFileHandler`. The `_session_header(level)` call inside `emit()` can stay as a private helper, or be replaced with a `build_session_header(...)` call — either way the bytes written to the file must be identical. Easiest: keep a private `_session_header(level)` method on `TracingService` and have `SessionFileHandler.emit()` call it via a closure or a module-level function reference passed in at construction. Or simplest: keep `_session_header` as a module-level private function and call it from `SessionFileHandler` directly — this is fine because `SessionFileHandler` lives in the same module.

3. **Do the tests LAST** (tasks 4 and 5). The mechanical rename is tedious but low-risk. A global find-and-replace within each test file handles 90% of the work. Run them only after pyright is clean and the smoke tests pass.

4. **Don't forget the two aliases**: `current_crash_file()` on `CrashService` (used by `yate/diagnostics.py`) and `current_log_path()` on `TracingService`. Without these, external call sites break.

5. **For the crash → tracing mirror removal**: the current `tracing.get_logger("crash").error(...)` call in `yate/crash.py` (line 106) is best-effort and silently skipped when tracing is off (the default). No test asserts it. Removing it is safe — but note it in the commit message so anyone reviewing a future crash log isn't surprised that uncaught exceptions no longer appear in the trace log.

6. **Validate `install()`'s env priority logic carefully**. The original `yate/tracing.py:install()` did:
   ```
   trace = env_trace() or config.yate_trace
   level = _requested_level(config)  # env_level() or config.yate_trace_level or DEFAULT_LEVEL
   ```
   The refactored version must replicate:
   ```
   trace = env_trace()                 # if None, use yate_trace param
   level_name = env_level()           # if None, use yate_trace_level param (a string)
                                      # if None, DEFAULT_LEVEL
   level = resolve_level(level_name)  # int; explicit None test, not `or`, to keep NOTSET
   ```
   Since `yate_trace_level` is a string (not pre-resolved int), `install()` calls `resolve_level()` internally. This matches the original `_requested_level` behavior — the level string resolution happens inside the service, not at the call site.

7. **For `crash._original_excepthook` reset in tests**: the current fixture saves and restores this value. After refactor, it's an instance attribute on the `crash` singleton. The fixture must save `crash.original_excepthook` (the property) and restore it by assigning to `crash._original_excepthook` (the backing attribute) — properties can't be assigned to. Keep the `# pyright: reportPrivateUsage=false` pragma at the top of the test file.

8. **Run pyright after each task, not just at the end**. Strict mode catches missing re-exports, signature mismatches, and forgotten aliases immediately. A 30-second pyright run after each task saves a 30-minute debugging session later.

9. **`configure()` is a one-liner alias** — don't add extra logic. Its only purpose is call-site readability: `tracing.configure(yate_trace=..., yate_trace_level=...)` at cli pass 2 makes the rc-stage re-config intent obvious, vs. `tracing.install(...)` which reads as "initial install." The implementation is literally `return self.install(...)` (or `self.install(...); return None` to match the `-> None` signature).

---

## Potential Risks & Mitigation Strategies

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Forgetting a module-level re-export in a thin shell → `tracing.LEVEL_NAMES` or `crash.crash_data_dir()` breaks at a distant call site | Low | High | Before writing the thin shells, grep for every `crash.XXX` and `tracing.XXX` usage across `yate/` and `tests/`. Build the `__all__` list from that grep, not from memory. |
| `SessionFileHandler` lazy-open / header behavior breaks because the move wasn't byte-for-byte | Medium | High | Copy the class verbatim. Do not refactor. Run `YATE_TRACE=1 yate --version` (expect no file) then `YATE_TRACE=1 yate` → quit (expect a file with the header). Both smoke tests must pass before moving on. |
| Forgetting the `current_crash_file` or `current_log_path` alias → diagnostics.py or external callers break | Low | Medium | Add a dedicated grep for `current_crash_file` and `current_log_path` across the codebase. Each must resolve to a method on the singleton. |
| Test monkeypatch of `tracing.resolve_level` stops working because the function is now a re-export from a different module | Medium | Medium | When the test does `monkeypatch.setattr(tracing, "resolve_level", fn)`, it patches the thin shell module's attribute. But `install()` in `log_services.py` looks up `resolve_level` from its own module globals (NOT from `yate.tracing`). So monkeypatching the thin shell does NOT affect `install()`. **Mitigation**: tests that need to influence `install()`'s level resolution must monkeypatch `yate.services.log_services.resolve_level` instead. The only test that did this (`test_requested_level_keeps_a_falsy_resolution`) is being deleted anyway — but if future tests need this pattern, document the correct monkeypatch target. |
| `crash.install()` return type changes from `None` to `bool` by accident (because `TracingService.install()` returns `bool`) | Low | Low | Explicitly annotate `def install(self) -> None` on `CrashService`. pyright catches the divergence. |
| The `_reset_crash_module()` test fixture breaks because module-level state is now instance state on a singleton | Medium | Medium | Rewrite the fixture to mutate `crash._err_file`, `crash._err_path`, `crash._crashed`, `crash._original_excepthook` directly (instance attributes). Keep `# pyright: reportPrivateUsage=false` at the top of the test file. The singleton's `@property` readers still work. |
| `yate.config` still imports `yate.tracing` at module load time → circular import through the thin shell | Low | High | The thin shell `yate/tracing.py` imports only from `yate.services.log_services`, which imports only stdlib + `yate.__version__`. No cycle. Verify with `python -c "import yate.config"` after the refactor. |
| Crash excepthook loses functionality because the mirror call was deleted | Low | Low | The mirror was best-effort bonus, silently skipped when tracing is off (the default). No test covered it. If anyone wants it back, the extension direction below shows how to add it at the cli.py layer without re-coupling the services. |
| `yate_trace_level` string is invalid (not in `LEVEL_NAMES`) and `resolve_level` returns `None` inside `install()` | Low | Low | Replicate the original `_requested_level` explicit `None` test: `level = resolve_level(name); if level is None: level = logging.DEBUG`. A bad yaterc value falls back to DEBUG rather than crashing. The original `tracing.py:289` already does this — preserve it verbatim. |
| Callers use `tracing.configure()` but expect a `bool` return (like `install()`) | Low | Low | Annotate `configure() -> None` explicitly. Document in its docstring that it's an alias for `install()` but returns `None` for call-site simplicity (cli.py pass 2 doesn't check the return value). |

---

## Feasible Extension Directions

1. **Re-add the crash → tracing mirror at the cli.py layer**. After both services are installed, register an `atexit` callback (or a custom `sys.excepthook` wrapper) that checks `crash.had_crash` and, if `tracing.is_enabled()`, writes the last exception into the trace log via `tracing.get_logger("crash").error(...)`. This restores the deleted feature **without** re-introducing a `crash → tracing` import: the coordination lives at the caller (cli.py), where both singletons are already in scope.

2. **Replace the `@property`-backed state with `@dataclass`**. `CrashService` and `TracingService` are natural dataclasses — their state is small and their methods are mostly side effects on that state. A future refactor could make them `@dataclass(slots=True)` for clearer state declaration and smaller memory footprint. Not done now because it would touch every test that mutates private attributes.

3. **Add a `LogService` Protocol** (not ABC) once `yate/interfaces.py` adopts the same pattern. A `Protocol` would let type-checkers enforce that both classes have `install()`, `uninstall()`, `current_path()`, `is_enabled()` without the runtime overhead of an ABC and without forcing inheritance. Not done now because nothing in the codebase treats crash and tracing polymorphically — the interface would be documentation only.

4. **Add structured JSONL output to `SessionFileHandler`**. Since it's now a public class, external code can subclass it for different log formats (JSON lines, structured fields, etc.). The lazy-open + header-on-first-emit pattern is reusable.

5. **Move `SessionFileHandler` into its own module** (`yate/services/_session_handler.py`) if tracing grows more handler types (rotation, compression, remote sink). Currently it's ~80 lines and fine where it is.

6. **Add a `LogServiceRegistry`** at the cli.py layer that holds both singletons and provides coordinated lifecycle (`install_all()`, `uninstall_all()`). This is the natural place to put the cross-service coordination logic (like the deleted mirror call) without coupling the services themselves.

7. **Expose `crash.had_crash` and `tracing.is_enabled()` through `yate.diagnostics`** so the `--diag` report can show "last run crashed" / "tracing is on this session" without callers needing to know the service shapes.

8. **Promote `configure()` to a full state-merge method** that accepts additional yaterc-derived parameters (e.g., a future `yate_trace_format` for JSON vs. plain text). Currently it's a one-liner alias; if tracing grows more knobs, `configure()` becomes the natural extension point while `install()` stays focused on env+rc trace/level.
