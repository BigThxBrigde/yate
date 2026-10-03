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

import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

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
