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

import json
import os
import time
import zipfile
from collections.abc import Awaitable, Callable, Iterator
from hashlib import sha256
from pathlib import Path
from typing import Any

import pyperclip
import pytest

# The bundled yate/extensions/ directory is auto-loaded with every YateApp;
# make sure the Python LSP extension never probes PATH or spawns a real server
# while the test suite runs -- process-wide, set once here at conftest import
# time (individual tests may still override via monkeypatch.setenv/delenv).
os.environ["YATE_PYTHON_LSP"] = "off"

from yate.app import YateApp
from yate.config import YateConfig
from yate.editor_core import Document
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


async def wait_until(  # noqa: Any - Textual pilot probe; no stubs
    pilot: Any, predicate: Callable[[], bool],
    timeout: float = 5.0, step: float = 0.05,
) -> bool:
    """Pause until *predicate* holds; False on timeout (for worker tests)."""
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
