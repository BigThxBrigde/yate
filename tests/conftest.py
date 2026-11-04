"""Global test isolation plus the shared pilot/construct helpers.

Isolation (autouse fixture): no test may touch the real user ~/.yate.
A single autouse fixture (function-scoped) redirects home for every test:

- ``Path.home()`` is patched to a per-test temp directory (config.py, crash.py,
  app.py, cli.py, user_setup.py, diagnostics.py, fonts.py all call it).
- ``USERPROFILE`` (Windows ntpath) and ``HOME`` (POSIX posixpath) are set so
  ``expanduser("~")`` string paths resolve to the same temp dir.

The temp home is empty, so ``~/.yate/yaterc``, themes and extensions never
exist during tests: user extensions are not executed, user config/themes are
not read. Tests that need "user config present" write it explicitly under the
returned directory.

The module-level helpers below are the single shared copies of the polling /
renderable / context-construction boilerplate that used to be duplicated
across the pilot-driven test modules.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import zipfile
from collections.abc import Awaitable, Callable, Iterator
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pyperclip
import pytest
from textual.pilot import Pilot, WaitForScreenTimeout

# The bundled yate/extensions/ directory is auto-loaded with every YateApp;
# make sure the Python LSP extension never probes PATH or spawns a real server
# while the test suite runs -- process-wide, set once here at conftest import
# time (individual tests may still override via monkeypatch.setenv/delenv).
os.environ["YATE_PYTHON_LSP"] = "off"

from yate.app import YateApp
from yate.config import YateConfig
from yate.editor_core import Document
from yate.editor_components import theme
from yate.keymaps.base import ActionContext, KeyUi
from yate.session import EditorSession


def _speed_up_pilot() -> None:
    """Cut Textual's fixed per-keystroke sleep from 20ms to 1ms.

    ``textual._wait.wait_for_idle`` always performs one
    ``asyncio.sleep(SLEEP_GRANULARITY)`` per call, and both
    ``Pilot._press_keys`` and every ``pilot.pause()`` go through it, so the
    default 0.02 turns into 15-31ms of pure sleeping per keystroke on
    Windows.  The pilot still drains the message queue afterwards, it just
    polls faster -- the smoke harness has lowered the same constant since it
    was written (``tools/smoke_test/harness.py``), and the full suite measured
    308s -> 264s (2026-10-20) with no behavioural change.

    Only the module constant is read here: ``wait_for_idle``'s ``min_sleep``
    default argument was bound to 0.02 at import time and keeps that value --
    the sleep inside the function body is what reads the constant, which is
    exactly why the assignment below takes effect.

    Tests that must wait for a worker poll explicitly (``wait_until`` below)
    rather than relying on any sleep duration, so no wait contract depends on
    this constant.
    """
    try:
        # Private on purpose upstream: the constant has no public accessor.
        from textual import _wait  # pyright: ignore[reportPrivateUsage]
    except ImportError:  # pragma: no cover - every Textual ships this module
        return
    _wait.SLEEP_GRANULARITY = 0.001


_speed_up_pilot()


#: Pristine ``Pilot._wait_for_screen`` implementation, captured before the
#: diagnostic wrapper below is installed.  The wrapper tests re-point this
#: with monkeypatch to drive the timeout and passthrough paths directly.
#: Any-typed on purpose: Textual pilot internals, no stubs (see wait_until).
_original_wait_for_screen: Any = cast(
    Any, Pilot._wait_for_screen  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType]
)


#: Cap for one rendered queue entry inside a pump summary line: the probe
#: dumps up to three entries per unresponsive pump and none of them may
#: flood the failure block.
_SUMMARY_REPR_LIMIT = 120


def _truncate(text: str, limit: int = _SUMMARY_REPR_LIMIT) -> str:
    """Clip *text* so one queued message cannot flood the failure output."""
    return text if len(text) <= limit else text[:limit] + "..."


def _describe_pump(pump: Any) -> str:  # noqa: Any - Textual pump probe; no stubs
    """One-line state snapshot of *pump* for the ``WaitForScreenTimeout`` message.

    Message pumps expose the interesting state privately (``_task`` /
    ``_closing`` / ``_message_queue``), so every access goes through
    ``getattr`` with a fallback: a missing attribute degrades to ``None``
    instead of breaking the failure path this probe runs on.
    """
    task = getattr(pump, "_task", None)
    if task is None:
        task_state = "task=none"
    elif task.done():
        task_state = "task=done"
    else:
        task_state = "task=pending"
    queue = getattr(pump, "_message_queue", None)
    qsize = queue.qsize() if queue is not None else -1
    peeked = [
        _truncate(repr(message))
        for message in list(getattr(queue, "_queue", ()))[:3]
    ]
    peek = f" queue={peeked}" if peeked else ""
    return (
        f"{type(pump).__name__}#{getattr(pump, 'id', None)}: {task_state}"
        f" closing={getattr(pump, '_closing', None)}"
        f" closed={getattr(pump, '_closed', None)}"
        f" attached={getattr(pump, 'is_attached', None)}"
        f" qsize={qsize}{peek}"
    )


def _format_pump_summary(
    unresponsive: list[Any], watched: int, budget: float
) -> str:
    """Render the probe outcome for the ``WaitForScreenTimeout`` message.

    *unresponsive* holds the pumps that did not process a probe callback
    within the *budget* seconds out of *watched* armed pumps; an empty
    list means every pump caught up after the original timeout -- a
    transient stall, not a pump that stayed dead.  The budget travels
    with the summary so a CI red can tell a stall that cleared inside the
    probe window apart from one that outlasted it (the observed CI
    windows ran >= 90s, far past this probe's cap).
    """
    if not unresponsive:
        return (
            f"(probe: all {watched} watched pumps answered within {budget:g}s"
            " of the timeout - transient stall, no pump stayed unresponsive)"
        )
    lines = [
        f"(probe: {len(unresponsive)}/{watched} pumps did not answer"
        f" within {budget:g}s budget)"
    ]
    lines.extend(f"  {_describe_pump(pump)}" for pump in unresponsive)
    return "\n".join(lines)


async def _probe_unresponsive_pumps(pilot: Any, timeout: float = 2.0) -> str:  # noqa: Any - Textual pilot probe; no stubs
    """Re-arm a callback on every pump of the current screen subtree.

    The probe arms one ``call_later`` callback per pump (the same protocol
    the original ``_wait_for_screen`` uses), waits up to *timeout* seconds
    and returns the formatted summary of the pumps that never answered.
    It runs only on the timeout path of ``_probed_wait_for_screen`` and is
    hard-capped, so it cannot stretch a frozen run: every leftover probe
    task is cancelled and awaited before returning.
    """
    try:
        screen = pilot.app.screen
    except Exception:  # noqa: BLE001 - any failure must degrade to a note here
        return "(probe: no current screen - pump states unavailable)"
    try:
        # Any-typed on purpose: Textual pump internals, no stubs (see wait_until).
        pumps: list[Any] = [pilot.app, *screen.walk_children(with_self=True)]
    except Exception:  # noqa: BLE001 - a walk failure must not replace the timeout
        return "(probe: subtree walk failed - pump states unavailable)"
    armed: dict[asyncio.Task[bool], Any] = {}
    for pump in pumps:
        event = asyncio.Event()
        if pump.call_later(event.set):
            armed[asyncio.create_task(event.wait())] = pump
    if not armed:
        return "(probe: no pump accepted a probe callback - subtree closed)"
    done, pending = await asyncio.wait(set(armed), timeout=timeout)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    unresponsive = [pump for task, pump in armed.items() if task not in done]
    return _format_pump_summary(unresponsive, watched=len(armed), budget=timeout)


async def _probed_wait_for_screen(
    self: Any, timeout: float = 30.0  # noqa: Any - Textual pilot probe; no stubs
) -> bool:
    """Drop-in replacement for ``Pilot._wait_for_screen`` (Textual 8.2.8).

    Delegates to the original implementation and returns its verdict
    untouched.  Only when the original raises ``WaitForScreenTimeout`` does
    the pump probe run, and its summary travels with the re-raised error:
    the same exception object and traceback come out, with the probe
    summary appended to the message, so a CI failure block becomes
    self-diagnosing without any behaviour change on green runs.
    """
    try:
        return await _original_wait_for_screen(self, timeout)
    except WaitForScreenTimeout as error:
        try:
            summary = await _probe_unresponsive_pumps(self)
        except Exception:  # noqa: BLE001 - the probe must never mask the timeout
            summary = "(probe: the probe itself failed - original timeout preserved)"
        detail = str(error.args[0]) if error.args else "timed out"
        error.args = (f"{detail}\n{summary}",)
        raise


def _install_wait_for_screen_diagnostics() -> None:
    """Swap :meth:`textual.pilot.Pilot._wait_for_screen` for the probe wrapper.

    Idempotent on purpose: a repeated install (conftest re-import in the
    same process) must not wrap the wrapper, or the saved original would
    chain into unbounded recursion.
    """
    current: Any = cast(
        Any, Pilot._wait_for_screen  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType]
    )
    if current is not _original_wait_for_screen:
        return  # already installed: a double import must not wrap the wrapper
    # upstream keeps the attribute private; same rationale as the capture above
    Pilot._wait_for_screen = _probed_wait_for_screen  # pyright: ignore[reportPrivateUsage]


_install_wait_for_screen_diagnostics()


@pytest.fixture(autouse=True)
def isolated_home(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Point home (Path.home + USERPROFILE/HOME) at a per-test temp dir.

    The home directory lives *outside* ``tmp_path`` (created via
    ``tmp_path_factory``): tests legitimately use ``tmp_path`` as a workspace
    root and assert on its contents, so it must stay unpolluted.
    """
    home = tmp_path_factory.mktemp("isolated_home")

    def _fake_home(cls: type[Path]) -> Path:
        return home

    monkeypatch.setattr(Path, "home", classmethod(_fake_home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture(autouse=True)
def isolated_os_clipboard(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Keep the OS clipboard out of the suite when tests run in parallel.

    ``pyperclip`` is the single clipboard backend (``yate/services/clipboard.py``)
    and the OS clipboard is shared by every worker process, so one test's yank
    becomes the next worker's paste: under ``-n auto``
    ``test_vim_keymap::test_yf_yanks_through_the_found_char`` read another
    worker's ``"hi"``.  Under xdist the backend is replaced by a per-process
    store; a serial run keeps the real one, so the clipboard round-trip tests
    still exercise the actual pyperclip calls.
    """
    if not hasattr(request.config, "workerinput"):
        yield
        return
    store: dict[str, str] = {"text": ""}

    def _copy(text: str) -> None:
        store["text"] = text

    def _paste() -> str:
        return store["text"]

    monkeypatch.setattr(pyperclip, "copy", _copy)
    monkeypatch.setattr(pyperclip, "paste", _paste)
    yield


@pytest.fixture(autouse=True)
def reset_theme_state() -> Iterator[None]:
    """Reset the process-global theme state after every test.

    The active theme is intentionally global (like vim's colorscheme), so a
    test switching themes leaks into every later test of the same xdist
    worker whenever its manual restore line is skipped -- a failed
    assertion before the restore leaks too (observed as flaky
    ``theme.active().dark`` failures in worker-parallel runs).  Teardown
    clears the subscriber list first (a leaked widget must not observe the
    reset) and then restores the built-in default without broadcasting.

    The theme *registry* (``THEMES``) is intentionally left untouched:
    ``tests/test_cli.py`` registers a custom theme at module import time and
    later tests assert its presence.
    """
    yield
    theme._listeners.clear()  # pyright: ignore[reportPrivateUsage]
    theme._active = theme.THEMES[theme.DEFAULT_THEME]  # pyright: ignore[reportPrivateUsage]


async def wait_until(  # noqa: Any - Textual pilot probe; no stubs
    pilot: Any, predicate: Callable[[], bool],
    timeout: float = 5.0, step: float = 0.01,
) -> bool:
    """Pause until *predicate* holds; False on timeout (for worker tests).

    ``step`` is the poll interval fed to ``pilot.pause``.  It stays small
    (10ms): the suite has 300+ call sites and every call pays at least one
    pause, so a coarse step is pure added latency -- the 2026-11-03 timing
    pass measured the pilot-driven files (file manager, app find/replace)
    losing seconds per file to it.  Predicates are cheap list/len checks,
    so tighter polling costs nothing.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # pilot.pause lets background workers/to_thread callbacks progress
        result: Awaitable[None] = pilot.pause(step)
        await result
        if predicate():
            return True
    return predicate()


def plain_text(content: Any) -> str:
    """Plain text of a widget renderable (rich Text, str, or other)."""
    plain = getattr(content, "plain", None)
    return plain if isinstance(plain, str) else str(content)


def message_text(app: YateApp) -> str:
    """The prompt bar's message-line text (command feedback / refusals)."""
    prompt_bar = app.editor.prompt_bar
    assert prompt_bar is not None
    return plain_text(prompt_bar.message.content)


def make_key_ui(
    execute: Callable[[str], bool] = lambda _name: True,
    on_message: Callable[[str], None] = lambda _text: None,
) -> KeyUi:
    """An inert :class:`KeyUi`: execute reports success, messages drop.

    *execute* / *on_message* let a test record what a keymap or an action
    asks the UI to do while the remaining callbacks stay inert no-ops.
    """
    return KeyUi(
        execute_action=execute,
        message=on_message,
        command_prompt=lambda: None,
        find_prompt=lambda _forward: None,
        goto_prompt=lambda: None,
        toggle_keymap=lambda: None,
    )


def make_action_context(text: str = "", ui: KeyUi | None = None) -> ActionContext:
    """A real :class:`ActionContext` whose active buffer holds *text*.

    The session starts with one unnamed buffer whose document is replaced by
    one over a fresh buffer seeded with *text* (the construction the
    action-table tests have always used).  *ui* defaults to the inert
    callbacks of :func:`make_key_ui`.
    """
    session = EditorSession(YateConfig())
    session.new_buffer()
    session.docs[session.index] = Document(None, session.make_buffer(text))
    return ActionContext(session, ui if ui is not None else make_key_ui())


def make_yxp(
    path: Path,
    files: dict[str, bytes],
    manifest: object | None = None,
    checksum: str | dict[str, str] | None = "auto",
    extra_members: dict[str, bytes | str] | None = None,
) -> Path:
    """Write a ``.yxp`` archive for the extension-package tests.

    *manifest* replaces the generated manifest verbatim (for malformed
    packages); *checksum* is ``"auto"`` (sha256 of *files*), ``None`` (omit
    the member) or an explicit dict; *extra_members* adds raw members.
    """
    if manifest is None:
        manifest = {
            "name": "hello",
            "version": "1.0.0",
            "description": "greets",
            "author": "tester",
            "files": sorted(files),
        }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest", json.dumps(manifest))
        if checksum == "auto":
            checksum = {
                name: sha256(data).hexdigest() for name, data in files.items()
            }
        if isinstance(checksum, dict):
            zf.writestr("checksum", json.dumps(checksum))
        for name, data in files.items():
            zf.writestr(name, data)
        for name, data in (extra_members or {}).items():
            zf.writestr(name, data)
    return path
