# Plan: Unified Crash & Tracing Services — Zero Cycle, Zero TYPE_CHECKING, Public API

## Hard Constraints

| # | Rule | Rationale |
|---|------|-----------|
| 1 | **Zero coupling between CrashService and TracingService** | They are two independent services. No injection, no logger_provider, no cross-reference. Crash writes .err, Tracing writes .log. Period. |
| 2 | **Zero `TYPE_CHECKING`** in log_services.py | No forward references needed — `install()` accepts `bool/int` scalars, not `YateConfig` |
| 3 | **No private-attribute cheating** in tests | Every symbol accessed as `._xxx` becomes genuine public API (underscore removed) |
| 4 | **Constants and pure functions live at module level** | Not class `@staticmethod`. Classes only hold state + instance methods. Keeps the call site identical to before (`tracing.LEVEL_NAMES`, `tracing.resolve_level(...)`). |

**Explicitly excluded**: `yate/interfaces.py` uses `TYPE_CHECKING` as the official Protocol pattern recommended by pyright — separate architectural choice, not in scope. Same for `tests/test_editor_core.py`.

---

## Two Design Decisions Explained

### Why remove the crash → tracing call entirely?

Original `crash.py` line 102-110 did this in `_excepthook`:

```python
# Mirror into the trace log when it is on... best-effort
try:
    tracing.get_logger("crash").error(...)
except Exception:
    pass
```

This was a **nice-to-have bonus**, not crash's core job. It mirrors uncaught Python exceptions from the `.err` report into the `.log` timeline. But:
- It creates a **hard import** from crash → tracing, which is the only reason we were inventing `logger_provider` injection
- It's **silently skipped** when tracing is off anyway (which is the default)
- It's **not crash's responsibility** — if two services need to coordinate, the coordination belongs at the caller (cli.py), not inside one service

**Decision**: Delete this call. CrashService is self-contained. If future coordination is needed between services, add it at the cli.py layer, not inside CrashService.

### Why no @staticmethod?

Previous plan put `resolve_level`, `env_trace`, `env_level`, `logs_dir`, `warn`, `build_session_header` as `@staticmethod` on the classes. This is a Java-ism. Python modules *are* namespaces for functions and constants. There's no reason to stuff stateless pure functions into a class when:

- `config.py` already does `tracing.LEVEL_NAMES` — that's a **module-level** constant lookup
- Tests already do `tracing.resolve_level(...)` — that's a **module-level** function call
- Moving them into the class as `@staticmethod` buys nothing, just adds indirection

**Decision**: All constants and pure functions stay at module level. Classes only hold state (`self._err_file`, `self.root_logger`, etc.) and instance methods that need that state.

---

## Dependency Graph (After — No Coupling At All)

```
cli.py ──► services/log_services.py ──► (stdlib only: logging, faulthandler, os, sys, pathlib, atexit, ...)
diagnostics.py ──► services/log_services.py
config.py ──► services/log_services.py  (only reads LEVEL_NAMES / DEFAULT_LEVEL constants)
extensions.py ──► services/log_services.py
app.py ──► services/log_services.py

services/log_services.py:
  ├── MODULE LEVEL: constants + pure functions + shared helpers
  │     LOGGER_NAME, LEVEL_NAMES, DEFAULT_LEVEL, TRUE_VALUES, FALSE_VALUES
  │     LOG_DIRNAME, LOG_PREFIX, LOG_SUFFIX
  │     DATA_DIRNAME, ERR_PREFIX, ERR_SUFFIX
  │     warn(), build_session_header(), resolve_level(), env_trace(), env_level(), logs_dir()
  │
  ├── LogService ABC        (no deps)
  ├── CrashService          (no deps on anything — self-contained)
  ├── TracingService        (no deps on CrashService — self-contained)
  ├── SessionFileHandler    (public class, no deps)
  ├── crash = CrashService()     singleton
  └── tracing = TracingService() singleton

  ⚠️  No import between CrashService and TracingService. Period.
```

---

## Target File Layout

```
yate/
├── services/
│   ├── __init__.py          ← MODIFY: export crash, tracing, LogService, CrashService, TracingService
│   └── log_services.py      ← NEW: everything lives here
├── crash.py                 ← MODIFY: thin shell
├── tracing.py               ← MODIFY: thin shell, NO TYPE_CHECKING
├── cli.py                   ← MODIFY: 1-line change in pass 2
├── diagnostics.py           ← NO CHANGE ✅
└── config.py                ← NO CHANGE ✅

tests/
├── test_crash.py            ← MODIFY: ._xxx → .xxx, + remove tracing import + its exception-mirror test
└── test_tracing.py          ← MODIFY: remove YateConfig; install(yate_trace, yate_level=int); rename privates
```

---

## Module-Level Constants & Pure Functions (Not In Classes)

```python
# ==============================================================
# Constants — consumed directly by config.py, cli.py, etc.
# ==============================================================

#: Root logger name; every yate logger is ``yate`` or a child of it.
LOGGER_NAME = "yate"

#: Accepted level names — :mod:`logging`'s built-ins, in increasing order.
LEVEL_NAMES: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

#: Level used when tracing is enabled without an explicit level.
DEFAULT_LEVEL = "DEBUG"

#: Accepted spellings of ``YATE_TRACE`` (compared lower-cased).
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})

#: ``~/.yate/data/logs`` — mirrors crash's ``~/.yate/data`` parent.
DATA_DIRNAME = "data"
LOG_DIRNAME = "logs"
LOG_PREFIX = "yate-"
LOG_SUFFIX = ".log"
ERR_PREFIX = "crash-"
ERR_SUFFIX = ".err"

# ==============================================================
# Pure functions — no state, no class needed
# ==============================================================

def warn(message: str) -> None:
    """Print ``yate: ...`` to stderr. Never raises."""
    print(f"yate: {message}", file=sys.stderr)


def build_session_header(
    *,
    service_name: str,
    version: str,
    extra_lines: Optional[dict[str, str]] = None,
) -> str:
    """Standard process-metadata header. Used by both crash and tracing."""
    header = [
        f"=== yate {version} {service_name} session ===",
        f"time: {datetime.now().isoformat(timespec='seconds')}",
        f"pid: {os.getpid()}",
        f"cwd: {os.getcwd()}",
        f"argv: {sys.argv!r}",
        f"python: {sys.version.split()[0]} on {sys.platform}",
    ]
    if extra_lines:
        header.extend(f"{k}: {v}" for k, v in extra_lines.items())
    header.append("-" * 60)
    return "\n".join(header) + "\n"


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

Call site for every one of these is identical to the original:
- `tracing.LEVEL_NAMES` → reads module-level constant ✅
- `tracing.resolve_level("DEBUG")` → calls module-level function ✅
- `crash.crash_data_dir()` → calls module-level function ✅
- `tracing.logs_dir()` → calls module-level function ✅

---

## LogService Abstract Base

```python
class LogService(ABC):
    """Shared contract for on-disk diagnostics services."""

    @abstractmethod
    def install(self, **kwargs: Any) -> Optional[bool]:
        """Enable the service. Returns True/False (tracing) or None (crash)."""

    @abstractmethod
    def uninstall(self) -> None:
        """Detach handlers and close open file handles. Idempotent."""

    @abstractmethod
    def current_path(self) -> Optional[Path]:
        """Path of this session's on-disk report / log, or None."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """True while the service is actively installed."""
```

**Note**: Previous plan had `get_logger()` on the base too. CrashService doesn't *really* need a `get_logger()` — it was only there for the deleted exception-mirroring feature. Keeping it on the base forces CrashService to implement a stub. Instead, `get_logger()` lives **only** on TracingService (it's the *only* service with a stdlib `logging.Logger` tree). CrashService exposes `err_file` and writes directly to it.

---

## CrashService — Self-Contained, Zero Dependencies

```python
class CrashService(LogService):
    """Eager-opened crash diagnostics. Permanent for the process lifetime.

    Uses faulthandler for native crashes and wraps sys.excepthook for
    uncaught Python exceptions. Atexit deletes header-only reports on
    healthy shutdown. Completely self-contained — does not import or
    reference TracingService.
    """

    # --- public state properties (was module-level _underscore names) ---

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

    # --- public lifecycle (implements LogService) ------------------------

    def install(self) -> None: ...
    def uninstall(self) -> None: ...
    def current_path(self) -> Optional[Path]: ...
    def current_crash_file(self) -> Optional[Path]: ...  # alias for diagnostics.py
    def is_enabled(self) -> bool: ...                     # `self.err_file is not None`

    # --- public helpers (module-level crash_data_dir above is mirrored here)

    def build_err_path(self, directory: Path, now: Optional[datetime] = None) -> Path:
        """Build ``crash-YYYYMMDD-HHMMSS.err`` inside *directory*."""

    def cleanup_on_exit(self) -> None:
        """Close + optionally delete the report. Public for atexit testing."""
```

**What was deleted**: `get_logger()`, `logger_provider`, and the entire `tracing.get_logger("crash").error(...)` call inside `_excepthook`. CrashService now writes .err files and nothing else.

**What stayed exactly the same**: faulthandler enable/disable, excepthook original hook chaining, atexit cleanup, header-only file deletion on healthy exit — all crash-specific logic preserved.

---

## TracingService — Lazy, Opt-In, Zero Dependencies

```python
class TracingService(LogService):
    """Lazy-opened runtime trace log. Controlled by env vars + yaterc.

    Two-phase install in cli.py:
        tracing.install()                                          # pass 1: env only
        ... load_config() ...
        tracing.install(                                           # pass 2: merge rc
            yate_trace=config.yate_trace,
            yate_level=resolve_level(config.yate_trace_level),
        )
    Or equivalently:
        tracing.configure(yate_trace=..., yate_level=...)
    """

    # --- public root logger ---------------------------------------------
    root_logger: logging.Logger              # was _logger — now public

    # --- public lifecycle (implements LogService) -----------------------

    def install(
        self,
        yate_trace: Optional[bool] = None,
        yate_level: Optional[int] = None,
    ) -> bool:
        """(Re)configure tracing. Returns whether enabled.

        Env vars (YATE_TRACE / YATE_TRACE_LEVEL) always win when present.
        The two parameters are yaterc fallbacks (None = not set).
        Second call keeps existing file handle, only adjusts level.
        """

    def configure(
        self,
        yate_trace: Optional[bool] = None,
        yate_level: Optional[int] = None,
    ) -> None:
        """Alias for install(...) — semantic sugar for rc-stage re-config."""
        self.install(yate_trace=yate_trace, yate_level=yate_level)

    def uninstall(self) -> None: ...
    def current_path(self) -> Optional[Path]: ...       # LogService abstract
    def current_log_path(self) -> Optional[Path]: ...   # alias
    def is_enabled(self) -> bool: ...

    # TracingService is the only LogService that exposes get_logger
    def get_logger(self, name: Optional[str] = None) -> logging.Logger: ...

    # --- public query & internals ---------------------------------------

    def file_handlers(self) -> list[logging.FileHandler]:
        """Active FileHandler instances attached to root_logger."""
```

**Design notes — zero TYPE_CHECKING, zero cycle, zero statics**:
- Constants (`LEVEL_NAMES`, `DEFAULT_LEVEL`, etc.) are **module-level**, not class attributes. `tracing.LEVEL_NAMES` reads from the module-level dict directly.
- Pure functions (`resolve_level`, `env_trace`, `env_level`, `logs_dir`) are **module-level**, not `@staticmethod`. Tests monkeypatch `tracing.resolve_level` which is a direct reference to the module-level function — works exactly as before.
- `install()` accepts `Optional[bool]` / `Optional[int]`, never `YateConfig` → no forward ref.
- No import of `yate.config` anywhere in log_services.py.
- `TracingService` does not import `CrashService`; no cross-reference exists at all.

---

## Private → Public Rename Mapping

Every symbol accessed as `._xxx` in tests becomes `.xxx`:

| Was private | Becomes public | Where accessed | Type |
|------------|----------------|----------------|------|
| `crash._err_file` | `crash.err_file` | test_crash.py (×8) | `@property` → `Optional[TextIO]` |
| `crash._err_path` | `crash.err_path` | test_crash.py (×2) | `@property` → `Optional[Path]` |
| `crash._crashed` | `crash.had_crash` | test_crash.py (×1) | `@property` → `bool` |
| `crash._original_excepthook` | `crash.original_excepthook` | test_crash.py (×5) | `@property` → `Callable` |
| `crash._cleanup_on_exit()` | `crash.cleanup_on_exit()` | test_crash.py (×2) | public method |
| `crash._err_file_path()` | `crash.build_err_path()` | test_crash.py (×2) | public method |
| `tracing._logger` | `tracing.root_logger` | test_tracing.py (×1) | public instance attr |
| `tracing._file_handlers()` | `tracing.file_handlers()` | test_tracing.py (×2) | public method |
| `tracing._SessionFileHandler` | `tracing.SessionFileHandler` | test_tracing.py | public class |
| `tracing._requested_level()` | **REMOVED** — merged into `install()` | test_tracing.py (×1) | see note below |

**Note on `_requested_level()`**: Exists only to resolve env + config priority. After refactor, `install()` does this inline. The test `test_requested_level_keeps_a_falsy_resolution` is low-value (level=0 NOTSET isn't a real yaterc use case) — delete it.

---

## Thin Shell Files

### `yate/crash.py` — thin shell, re-exports module-level + singleton

```python
"""Thin shell. Re-exports singleton and module-level functions from log_services."""
from yate.services.log_services import (
    DATA_DIRNAME,
    ERR_PREFIX,
    ERR_SUFFIX,
    CrashService,
    build_err_path,
    crash,
    crash_data_dir,
    cleanup_on_exit,
)

__all__ = [
    "crash", "CrashService",
    "DATA_DIRNAME", "ERR_PREFIX", "ERR_SUFFIX",
    "crash_data_dir", "build_err_path", "cleanup_on_exit",
]
```

### `yate/tracing.py` — thin shell, NO TYPE_CHECKING

```python
"""Thin shell. Re-exports singleton and module-level constants/functions from log_services."""
from yate.services.log_services import (
    FALSE_VALUES,
    LEVEL_NAMES,
    LOGGER_NAME,
    LOG_DIRNAME,
    LOG_PREFIX,
    LOG_SUFFIX,
    TRUE_VALUES,
    TracingService,
    DEFAULT_LEVEL,
    SessionFileHandler,
    env_level,
    env_trace,
    install,
    logs_dir,
    resolve_level,
    tracing,
    uninstall,
)

__all__ = [
    "tracing", "TracingService",
    "LOGGER_NAME", "LEVEL_NAMES", "DEFAULT_LEVEL",
    "TRUE_VALUES", "FALSE_VALUES",
    "LOG_DIRNAME", "LOG_PREFIX", "LOG_SUFFIX",
    "SessionFileHandler",
    "logs_dir", "resolve_level", "env_trace", "env_level",
    "install", "uninstall",
]
```

**Key**: These are **module-level re-exports**, not class attributes. `config.py` does `tracing.LEVEL_NAMES` — with a thin shell, Python finds it as a module-level attribute lookup. Tests monkeypatch `tracing.resolve_level` — same. Everything works exactly as before.

**Zero `TYPE_CHECKING`** — this file has literally nothing to type-check.

---

## Call Site Changes

### `yate/cli.py` — 1-line change in pass 2

```python
# Pass 1: unchanged
crash.install()
tracing.install()

# Pass 2: OLD tracing.install(config) → NEW explicit scalars
tracing.install(
    yate_trace=config.yate_trace,
    yate_level=resolve_level(config.yate_trace_level),
)
```

### `yate/diagnostics.py` — 0 change ✅
Calls `crash.crash_data_dir()` and `crash.current_crash_file()`. The former is a module-level re-export from the thin shell; the latter is an alias method on the crash singleton. Both resolve.

### All other files — 0 changes ✅
`from yate import crash, tracing` returns the thin-shell module objects which re-export everything. `crash.install()`, `tracing.get_logger(__name__)`, `crash.crash_data_dir()`, `tracing.LEVEL_NAMES`, `tracing.resolve_level(...)`, `tracing.install()` all resolve via normal Python attribute lookup.

---

## What Was Removed from test_crash.py

The deleted crash → tracing call means one feature test disappears. Grep shows test_crash.py doesn't currently test the exception-mirror behavior explicitly — it only tests that `_excepthook` appends to .err and chains to the original hook. That test stays. The tracing mirror call was best-effort bonus with no dedicated test coverage.

---

## Task Breakdown

### Task 1: Create `yate/services/log_services.py` — Core Implementation
- **Priority**: P0
- **Estimated effort**: 90 min
- **Scope**:
  1. Module-level constants + pure functions (see section above)
  2. `SessionFileHandler` — move verbatim from tracing.py, now public
  3. `LogService` ABC — 4 abstract methods (install, uninstall, current_path, is_enabled). No statics; `get_logger` is TracingService-only.
  4. `CrashService` — state as public `@property` + instance methods. **No `logger_provider`**. `_excepthook_impl` writes .err + chains to original hook. No tracing call.
  5. `TracingService` — `root_logger` public attr + all instance methods. No statics.
  6. Instantiate singletons:
     ```python
     crash = CrashService()
     tracing = TracingService()
     ```
     **No injection line needed.** Services are independent.
- **Verification**: `pyright yate/services/log_services.py` strict → zero diagnostics

### Task 2: Thin Shells `yate/crash.py` and `yate/tracing.py`
- **Priority**: P0
- **Estimated effort**: 20 min
- **Scope**: See section above. Re-export module-level symbols as well as singletons. **Zero TYPE_CHECKING**.
- **Verification**: `from yate import crash, tracing` works; `tracing.LEVEL_NAMES`, `crash.crash_data_dir()`, `tracing.resolve_level(...)` all resolve

### Task 3: Update `yate/cli.py` — Pass 2 Signature
- **Priority**: P0
- **Estimated effort**: 5 min
- **Scope**: `tracing.install(config)` → `tracing.install(yate_trace=config.yate_trace, yate_level=resolve_level(config.yate_trace_level))`
- **Verification**: pyright strict zero diagnostics

### Task 4: Rewrite `tests/test_crash.py` — Public Names
- **Priority**: P0
- **Estimated effort**: 25 min
- **Scope**: Search-and-replace all `._xxx` → `.xxx`:
  | `crash._err_file` | → | `crash.err_file` |
  | `crash._err_path` | → | `crash.err_path` |
  | `crash._crashed` | → | `crash.had_crash` |
  | `crash._original_excepthook` | → | `crash.original_excepthook` |
  | `crash._cleanup_on_exit` | → | `crash.cleanup_on_exit` |
  | `crash._err_file_path` | → | `crash.build_err_path` |
  - Update `_reset_crash_module()` fixture to use public names
- **Verification**: `pytest tests/test_crash.py -q` — all tests pass

### Task 5: Rewrite `tests/test_tracing.py` — Remove YateConfig, Public Names
- **Priority**: P0
- **Estimated effort**: 40 min
- **Scope**:
  1. Delete `from yate.config import YateConfig`
  2. Replace all `tracing.install(YateConfig(...))` with explicit params:
     - `YateConfig(yate_trace=True)` → `tracing.install(yate_trace=True)`
     - `YateConfig(yate_trace=False)` → `tracing.install(yate_trace=False)`
     - `YateConfig(yate_trace=True, yate_trace_level="ERROR")` → `tracing.install(yate_trace=True, yate_level=logging.ERROR)`
     - Same pattern for WARNING(30), DEBUG(10)
  3. Delete `test_requested_level_keeps_a_falsy_resolution` test (or rewrite; recommended: delete)
  4. `tracing._logger` → `tracing.root_logger`
  5. `tracing._file_handlers()` → `tracing.file_handlers()`
- **Verification**: `pytest tests/test_tracing.py -q` — all tests pass

### Task 6: Update `yate/services/__init__.py`
- **Priority**: P2
- **Estimated effort**: 10 min
- **Scope**: Add exports:
  ```python
  from yate.services.log_services import LogService, CrashService, TracingService
  from yate.services.log_services import crash, tracing
  ```
  Append to `__all__`.
- **Verification**: `from yate.services import crash, tracing, LogService` works

---

## Verification Matrix

| # | Step | Command | Expected |
|---|------|---------|----------|
| 1 | No TYPE_CHECKING in new code | `grep -n "TYPE_CHECKING" yate/services/log_services.py` | 0 matches |
| 2 | No TYPE_CHECKING in tracing.py | `grep -n "TYPE_CHECKING" yate/tracing.py` | 0 matches |
| 3 | No import between services | `grep -n "CrashService\|TracingService" yate/services/log_services.py` — each class body references only self/module-level symbols, never the other class name | Zero cross-reference inside class bodies |
| 4 | Strict pyright | `pyright yate/` | Zero diagnostics |
| 5 | Crash tests | `pytest tests/test_crash.py -q` | All pass |
| 6 | Tracing tests | `pytest tests/test_tracing.py -q` | All pass |
| 7 | Full test suite | `pytest tests/ -q` | All pass |
| 8 | Smoke: --version with env trace | `YATE_TRACE=1 yate --version` | Instant exit, no log file (lazy open) |
| 9 | Smoke: normal startup | `YATE_TRACE=1 yate` → quit | `.log` file under `~/.yate/data/logs/` |
| 10 | Smoke: cleanup | `yate --cleanup-defaults --include-data` | `data/` fully removed |

---

## Practical Suggestions

1. **Implement module-level stuff first**, then CrashService, then TracingService, then thin shells, then tests. This way you always have a partially-working import chain — and any errors are isolated to the last thing you touched.

2. **Test files (tasks 4 and 5)** are tedious because of mechanical rename. Do them **LAST** (after everything compiles). A global find-and-replace within each file handles 90%.

3. **Don't forget the two aliases**: `current_crash_file()` on CrashService (used by diagnostics.py) and `current_log_path()` on TracingService. Without these, diagnostics.py and external call sites break.

4. **Double-check `install()`'s env-var priority logic**. The original tracing.py had:
   ```
   env_trace() → if None, use config.yate_trace
   env_level() → if None, use config.yate_trace_level → resolve
   ```
   The refactored install() must replicate:
   ```
   env_trace() → if None, use yate_trace param
   env_level() → if None, use yate_level param directly (it's already int)
   ```
   Since `yate_level` is already resolved (cli.py calls `resolve_level` before passing it), the install logic is actually **simpler** than the original.

---

## Potential Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Forgetting a module-level re-export → `tracing.LEVEL_NAMES` or `crash.crash_data_dir()` breaks | Low | High | Before writing thin shells, grep for all `crash.XXX` / `tracing.XXX` usages across yate/ and tests/ |
| `SessionFileHandler` not moved verbatim → lazy-open / header behavior breaks | Medium | High | Copy-paste without refactoring. Subtle `delay=True` + custom header logic. Test `YATE_TRACE=1 yate --version` (no file) then normal run (file with header) |
| Forgetting the two aliases → diagnostics.py crashes | Low | Medium | Add a dedicated grep for `current_crash_file` and `current_log_path` usages |
| Test monkeypatch of `tracing.resolve_level` doesn't work because it's now a module-level function on a different module | Low | Medium | Thin shell does `from yate.services.log_services import resolve_level`. When test does `monkeypatch.setattr(tracing, "resolve_level", fn)`, it patches the thin shell module attribute which *is* the same object as the module-level function in log_services.py (Python import binds the same reference). It works — but verify with the existing `test_env_trace_off_values` test that monkeypatches tracing.resolve_level. |

---

## What We Deleted On Purpose

| Item | Reason |
|------|--------|
| `crash → tracing` exception mirror call | Not crash's job. Two services are independent. If future coordination needed, do it at cli.py layer. |
| `logger_provider` injection pattern | Was only there to break the deleted call. Not needed anymore. |
| LogService's `get_logger` abstract | CrashService doesn't need a logger tree; only TracingService does. Keep it concrete on TracingService only. |
| All `@staticmethod` | Pure functions belong at module level. Classes hold state + instance methods. |
| Class-level constants (`LEVEL_NAMES: ClassVar[...] = ...`) | Module-level constants are simpler and match how config.py already reads them. |
| `_requested_level()` | Logic merged inline into `install()`. Test deleted (low-value scenario). |

---

## Feasible Extension Directions

1. **Re-add crash→tracing mirror at the cli.py layer**: After both services are installed, register an atexit callback that checks `crash.had_crash` and writes the last exception into the tracing log if tracing is enabled. This keeps services independent while restoring the feature.

2. **Replace `ABC` with `Protocol`** (after interfaces.py is also converted). Protocol avoids runtime overhead and is more idiomatic for interfaces with no shared implementation.

3. **Add structured JSONL output option** to SessionFileHandler. Since it's now a public class, external code can subclass it for different log formats.

4. **Move `SessionFileHandler` into its own module** (`yate/services/_session_handler.py`) if tracing grows more handler types. Currently it's ~80 lines, fine where it is.
