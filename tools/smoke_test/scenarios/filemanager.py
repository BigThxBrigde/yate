"""File manager screen scenarios (tags: ``files``, ``view``).

Covers the ``--file-manager`` startup form end to end (the only surface
the m6 review found unguarded): the app boots straight into the
fullscreen :class:`~yate.editor_view.filemgr.FileManagerScreen`, whose
mount wiring is deferred via ``call_after_refresh`` (B1 race), so every
post-startup assertion is awaited through :func:`wait_until`.  The
scenario then drives ``j`` / ``k`` / ``l`` navigation into a
subdirectory and closes with ``q`` -- the injected exit verb quits the
whole app (rc 0), which the closing checks pin down.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from tools.smoke_test import harness
from tools.smoke_test.harness import Check, Scenario, ScenarioResult, snapshot_svg
from tools.smoke_test.scenarios._base import wait_until
from yate.app import YateApp
from yate.editor_view.filemgr import FileManagerScreen

__all__ = ["SCENARIOS"]


def _fm_screen(app: Any) -> FileManagerScreen | None:
    """The top screen when it is a :class:`FileManagerScreen`, else ``None``."""
    screen = getattr(app, "screen", None)
    return screen if isinstance(screen, FileManagerScreen) else None


def _panes_visible(screen: FileManagerScreen) -> bool:
    """Whether the three panes are attached and displayed (post-B1 wiring)."""
    try:
        parent = screen.query_one("#filemgr-parent")
        body = screen.query_one("#filemgr-list")
        preview = screen.query_one("#filemgr-preview")
    except Exception:  # noqa: BLE001 - panes not mounted yet is a False, not a crash
        return False
    return all(node.is_attached and node.display for node in (parent, body, preview))


async def _filemanager_startup_navigation(tmp: Path) -> ScenarioResult:
    """``--file-manager`` startup: fullscreen screen, three panes, j/l, q."""
    (tmp / "a.txt").write_text("alpha\n", encoding="utf-8")
    sub = tmp / "sub"
    sub.mkdir()
    (sub / "inner.txt").write_text("inner\n", encoding="utf-8")
    # cli.py --file-manager startup form (target stays None, the dir is the
    # --file-manager argument); registered for the invariant sweep exactly
    # like harness.new_app does (the factory has no filemanager_dir knob).
    app = YateApp(filemanager_dir=tmp)
    harness._apps.append(app)
    checks: list[Check] = []
    rows: dict[int, str] = {}
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        # The startup push rides app.on_mount's call_after_refresh (B1), so
        # the screen may not be up after the first pause.
        checks.append(Check(
            "fullscreen_screen_pushed", True,
            await wait_until(pilot, lambda: _fm_screen(app) is not None),
        ))
        screen = _fm_screen(app)
        assert screen is not None
        checks.append(Check(
            "fullscreen_class", True, screen.has_class("fullscreen")))
        checks.append(Check(
            "three_panes_visible", True,
            await wait_until(pilot, lambda: _panes_visible(screen)),
        ))
        # The listing is built in _wire_mount, also deferred (B1).
        checks.append(Check(
            "listing_ready", True,
            await wait_until(pilot, lambda: screen._cursor_path() is not None),
        ))
        # Dirs-first sort: the cursor starts on sub/, j steps onto a.txt.
        checks.append(Check("cursor_starts_on_dir", sub, screen._cursor_path()))
        await pilot.press("j")
        await pilot.pause()
        checks.append(Check(
            "j_steps_to_file", tmp / "a.txt", screen._cursor_path()))
        await pilot.press("k")
        await pilot.pause()
        checks.append(Check("k_back_to_dir", sub, screen._cursor_path()))
        # l on a directory navigates into it (listing swaps to its content).
        await pilot.press("l")
        checks.append(Check(
            "l_enters_subdir", True,
            await wait_until(pilot, lambda: screen._cwd == sub),
        ))
        checks.append(Check(
            "subdir_listed", ["inner.txt"],
            [e.path.name for e in screen._entries],
        ))
        rows = snapshot_svg(app, tmp)
        checks.append(Check(
            "svg_shows_entry", True,
            any("inner.txt" in text for text in rows.values()),
        ))
        # q closes through the injected exit verb: the fullscreen form quits
        # the app (bound by app.on_mount before the screen was pushed).
        await pilot.press("q")
        exited = False
        for _ in range(10):
            with contextlib.suppress(Exception):
                await pilot.pause()
            if not app.is_running:
                exited = True
                break
        checks.append(Check("q_exits_app", True, exited))
        checks.append(Check("return_code_zero", 0, app.return_code))
    return ScenarioResult("filemanager_startup_navigation", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario(
        "filemanager_startup_navigation",
        _filemanager_startup_navigation,
        ("files", "view"),
    ),
]
