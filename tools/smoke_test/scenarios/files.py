"""File, tab, save and quit scenarios (tag: ``files``)."""

from __future__ import annotations

from pathlib import Path

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import message_text, run_command, type_path, type_text, wait_until

__all__ = ["SCENARIOS"]


async def _open_path_prompt(tmp: Path) -> ScenarioResult:
    """ctrl+o opens a file by path (the open runs in a worker)."""
    other = tmp / "other.txt"
    other.write_text("second file\n", encoding="utf-8")
    app = new_app(target=tmp / "main.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+o")
        await pilot.pause()
        checks.append(Check("open_mode", "open",
                            app.prompt_bar.active_mode if app.prompt_bar else None))
        await type_path(pilot, other)
        await pilot.press("enter")
        await wait_until(pilot, lambda: app.doc.name == "other.txt")
        checks.append(Check("doc.name", "other.txt", app.doc.name))
        # Compare the name, not the absolute path: the scenario runs in a
        # fresh temp dir every time and baselines must stay machine-stable.
        doc_path = app.doc.path
        checks.append(Check("doc.path_name", other.name,
                            doc_path.name if doc_path else None))
        checks.append(Check("content", "second file", app.buffer.lines[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("open_path_prompt", checks, rows)


async def _save_as_flow(tmp: Path) -> ScenarioResult:
    """ctrl+s on an unnamed buffer prompts for a path (save-as)."""
    target = tmp / "other.txt"
    app = new_app()
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()
        checks.append(Check("unnamed", None, app.doc.path))
        await type_text(pilot, "hello")
        await pilot.press("ctrl+s")
        await pilot.pause()
        checks.append(Check("save_mode", "save",
                            app.prompt_bar.active_mode if app.prompt_bar else None))
        await type_path(pilot, target)
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("file_exists", True, target.exists()))
        checks.append(Check("file_content", "hello", target.read_text(encoding="utf-8")))
        checks.append(Check("doc.name", "other.txt", app.doc.name))
        checks.append(Check("saved_flag", False, app.doc.modified))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("save_as_flow", checks, rows)


async def _new_buffer_close_tab(tmp: Path) -> ScenarioResult:
    """ctrl+n adds a tab, ctrl+w closes it again."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("one_doc", 1, len(app.docs)))
        await pilot.press("ctrl+n")
        await pilot.pause()
        checks.append(Check("two_docs", 2, len(app.docs)))
        checks.append(Check("active_is_new", 1, app.doc_index))
        await pilot.press("ctrl+w")
        await pilot.pause()
        checks.append(Check("back_to_one", 1, len(app.docs)))
        checks.append(Check("doc_index", 0, app.doc_index))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("new_buffer_close_tab", checks, rows)


async def _tab_cycle(tmp: Path) -> ScenarioResult:
    """ctrl+pagedown / ctrl+pageup cycle the open tabs."""
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp / "b.txt").write_text("b\n", encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Setup only: the second tab is opened through the app API so the
        # scenario stays about tab cycling (typing the absolute path is
        # covered by open_path_prompt and costs ~70ms per character).
        app.open_path(tmp / "b.txt")
        await wait_until(pilot, lambda: app.doc.name == "b.txt")
        checks.append(Check("opened_b", "b.txt", app.doc.name))
        await pilot.press("ctrl+pagedown")
        await pilot.pause()
        checks.append(Check("next_tab", "a.txt", app.doc.name))
        await pilot.press("ctrl+pageup")
        await pilot.pause()
        checks.append(Check("prev_tab", "b.txt", app.doc.name))
        await run_command(pilot, "bn")
        checks.append(Check("colon_bn", "a.txt", app.doc.name))
        await run_command(pilot, "bp")
        checks.append(Check("colon_bp", "b.txt", app.doc.name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("tab_cycle", checks, rows)


async def _welcome_screen(tmp: Path) -> ScenarioResult:
    """Starting without a target shows the welcome page on a scratch buffer."""
    app = new_app()
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("welcome_visible", True, app.welcome_visible))
        checks.append(Check("no_path", None, app.doc.path))
        checks.append(Check("doc_name", "[no name]", app.doc.name))
        checks.append(Check("empty_buffer", "", app.buffer.get_text()))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("welcome_screen", checks, rows)


async def _quit_guard_wq(tmp: Path) -> ScenarioResult:
    """:q is blocked on a dirty buffer; :wq saves and quits."""
    target = tmp / "quit.txt"
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_text(pilot, "hello")
        await run_command(pilot, "q")
        checks.append(Check("still_running", None, app.return_code))
        checks.append(Check("no_modal", 1, len(app.screen_stack)))
        checks.append(Check("warned", True, "unsaved changes" in message_text(app)))
        await run_command(pilot, "wq")
        checks.append(Check("doc_saved", False, app.doc.modified))
    checks.append(Check("file_content", "hello", target.read_text(encoding="utf-8")))
    checks.append(Check("exited", 0, app.return_code))
    return ScenarioResult("quit_guard_wq", checks)


async def _quit_force_discards(tmp: Path) -> ScenarioResult:
    """:q! leaves the buffer unsaved and quits anyway."""
    target = tmp / "force.txt"
    target.write_text("original", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_text(pilot, "changed")
        checks.append(Check("dirty", True, app.doc.modified))
        await run_command(pilot, "q")
        checks.append(Check("still_running", None, app.return_code))
        await run_command(pilot, "q!")
    checks.append(Check("disk_untouched", "original", target.read_text(encoding="utf-8")))
    checks.append(Check("exited", 0, app.return_code))
    return ScenarioResult("quit_force_discards", checks)


async def _filetype_override(tmp: Path) -> ScenarioResult:
    """:set filetype= overrides the detected type; ``auto`` restores it."""
    target = tmp / "code.py"
    target.write_text("x = 1\n", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("detected", "py", app.doc.filetype))
        checks.append(Check("no_override", None, app.doc.filetype_override))
        await run_command(pilot, "set filetype=md")
        checks.append(Check("overridden", "md", app.doc.filetype))
        checks.append(Check("override_flag", "md", app.doc.filetype_override))
        await run_command(pilot, "set filetype=auto")
        checks.append(Check("restored", "py", app.doc.filetype))
        checks.append(Check("override_cleared", None, app.doc.filetype_override))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("filetype_override", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("open_path_prompt", _open_path_prompt, ("files",)),
    Scenario("save_as_flow", _save_as_flow, ("files",)),
    Scenario("new_buffer_close_tab", _new_buffer_close_tab, ("files",)),
    Scenario("tab_cycle", _tab_cycle, ("files",)),
    Scenario("welcome_screen", _welcome_screen, ("files",)),
    Scenario("quit_guard_wq", _quit_guard_wq, ("files",)),
    Scenario("quit_force_discards", _quit_force_discards, ("files",)),
    Scenario("filetype_override", _filetype_override, ("files",)),
]
