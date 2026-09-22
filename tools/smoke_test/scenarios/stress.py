"""Randomized and volume stress scenarios (tag: ``stress``).

The fuzz scenario is seeded (``--seed`` / :func:`rng_for`), so a failure is
reproducible: re-run with the same seed to get the same keystrokes.
"""

from __future__ import annotations

from pathlib import Path

from ..harness import (
    Check,
    Scenario,
    ScenarioResult,
    new_app,
    rng_for,
    snapshot_svg,
)
from ._base import run_command, type_text, wait_until
from yate.editor_view import theme

__all__ = ["SCENARIOS"]

#: Keys a fuzz run may press: plain text plus harmless cursor motions.
_FUZZ_KEYS = (
    "a b c d e space 1 2 3 x y z".split()
    + ["enter", "backspace", "left", "right", "up", "down", "home", "end"]
)


async def _stress_key_fuzz(tmp: Path) -> ScenarioResult:
    """200 seeded random keystrokes must never break the editor."""
    target = tmp / "fuzz.txt"
    target.write_text("seed\n", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    rng = rng_for("stress_key_fuzz")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        for _ in range(200):
            await pilot.press(rng.choice(_FUZZ_KEYS))
        await pilot.pause()
        buf = app.editor.session.buffer
        checks.append(Check("no_crash", None, app.return_code))
        checks.append(Check("no_modal", 1, len(app.screen_stack)))
        checks.append(Check("cursor_row", True, 0 <= buf.row < buf.line_count))
        checks.append(Check("cursor_col", True,
                            0 <= buf.col <= len(buf.lines[buf.row])))
        checks.append(Check("not_empty", True, buf.line_count >= 1))
        # the buffer must still be saveable after all that abuse
        await pilot.press("ctrl+s")
        await wait_until(pilot, lambda: not app.editor.session.doc.modified)
        checks.append(Check("saved", buf.get_text(),
                            target.read_text(encoding="utf-8")))
        checks.append(Check("clean", False, app.editor.session.doc.modified))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("stress_key_fuzz", checks, rows)


async def _stress_many_tabs(tmp: Path) -> ScenarioResult:
    """Open 20 tabs, then close them one by one."""
    paths: list[Path] = []
    for i in range(20):
        path = tmp / f"f{i}.txt"
        path.write_text(f"file {i}\n", encoding="utf-8")
        paths.append(path)
    app = new_app(target=paths[0])
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        for path in paths[1:]:
            app.editor.open_path(path)
        await pilot.pause()
        checks.append(Check("twenty_tabs", 20, len(app.editor.session.docs)))
        for _ in range(19):
            await pilot.press("ctrl+w")
        await pilot.pause()
        checks.append(Check("one_left", 1, len(app.editor.session.docs)))
        checks.append(Check("doc_index", 0, app.editor.session.index))
        checks.append(Check("buffer_readable", True,
                            app.editor.session.buffer.line_count >= 1))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("stress_many_tabs", checks, rows)


async def _stress_rapid_toggles(tmp: Path) -> ScenarioResult:
    """Rapid theme / keymap / explorer toggles always land on a state."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        start_theme = app.theme
        start_keymap = app.editor.keymaps.name
        for _ in range(5):
            await run_command(pilot, "theme latte")
            await run_command(pilot, "theme mocha")
        checks.append(Check("theme_back", "mocha", theme.active().name))
        checks.append(Check("textual_theme_back", start_theme, str(app.theme)))
        for _ in range(10):
            await pilot.press("ctrl+/")
        await pilot.pause()
        checks.append(Check("keymap_back", start_keymap, app.editor.keymaps.name))
        # Rapid toggling must never wedge the sidebar: after the storm the
        # editor takes focus back and one ctrl+b still flips the state.
        for _ in range(10):
            await pilot.press("ctrl+b")
        await pilot.pause()
        checks.append(Check("sidebar_matches_flag", app.editor.explorer_visible,
                            app.editor.sidebar.display
                            if app.editor.sidebar else None))
        await pilot.press("ctrl+1")
        await pilot.pause()
        before = app.editor.explorer_visible
        await pilot.press("ctrl+b")
        await pilot.pause()
        checks.append(Check("toggles", not before, app.editor.explorer_visible))
        await pilot.press("ctrl+b")
        await pilot.pause()
        checks.append(Check("toggles_back", before, app.editor.explorer_visible))
        checks.append(Check("still_no_crash", None, app.return_code))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("stress_rapid_toggles", checks, rows)


async def _stress_reopen_same_file(tmp: Path) -> ScenarioResult:
    """Closing a modified tab and reopening the file reads from disk."""
    target = tmp / "one.txt"
    target.write_text("one", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_text(pilot, " changed")
        checks.append(Check("dirty", True, app.editor.session.doc.modified))
        await pilot.press("ctrl+w")
        await pilot.pause()
        checks.append(Check("closed", 1, len(app.editor.session.docs)))
        checks.append(Check("scratch", None, app.editor.session.doc.path))
        app.editor.open_path(target)
        await pilot.pause()
        checks.append(Check("reopened", "one.txt", app.editor.session.doc.name))
        checks.append(Check("disk_version", "one",
                            app.editor.session.buffer.lines[0]))
        checks.append(Check("clean", False, app.editor.session.doc.modified))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("stress_reopen_same_file", checks, rows)


async def _stress_large_file(tmp: Path) -> ScenarioResult:
    """5000 lines: jump to the end, edit, save."""
    target = tmp / "huge.txt"
    target.write_text("\n".join(f"line {i}" for i in range(5000)), encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("line_count", 5000, app.editor.session.buffer.line_count))
        await pilot.press("ctrl+end")
        await pilot.pause()
        checks.append(Check("at_end", 4999, app.editor.session.buffer.cursor[0]))
        await type_text(pilot, "!")
        await pilot.press("ctrl+s")
        await pilot.pause()
        checks.append(Check("clean", False, app.editor.session.doc.modified))
        on_disk = target.read_text(encoding="utf-8").split("\n")
        checks.append(Check("disk_lines", 5000, len(on_disk)))
        checks.append(Check("disk_last", True, on_disk[-1].endswith("!")))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("stress_large_file", checks, rows)


async def _stress_long_line(tmp: Path) -> ScenarioResult:
    """A 10k character line: cursor motion stays cheap and correct."""
    target = tmp / "long.txt"
    target.write_text("x" * 10000, encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("line_length", 10000,
                            len(app.editor.session.buffer.lines[0])))
        for _ in range(5):
            await pilot.press("right")
        await pilot.pause()
        checks.append(Check("cursor", (0, 5), app.editor.session.buffer.cursor))
        await pilot.press("ctrl+end")
        await pilot.pause()
        checks.append(Check("doc_end", (0, 10000),
                            app.editor.session.buffer.cursor))
        checks.append(Check("no_crash", None, app.return_code))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("stress_long_line", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("stress_key_fuzz", _stress_key_fuzz, ("stress",)),
    Scenario("stress_many_tabs", _stress_many_tabs, ("stress",)),
    Scenario("stress_rapid_toggles", _stress_rapid_toggles, ("stress",)),
    Scenario("stress_reopen_same_file", _stress_reopen_same_file, ("stress",)),
    Scenario("stress_large_file", _stress_large_file, ("stress",), slow=True),
    Scenario("stress_long_line", _stress_long_line, ("stress",), slow=True),
]
