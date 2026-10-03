"""End-to-end integration tests for the diff tool entry points (plan-c).

Pilot-driven (headless Textual): the real :class:`~yate.app.YateApp` shell
opens the diff screen through the two plan-c entry points -- the ``:diff``
ex command (:meth:`OverlayFlows.open_diff`) and the CLI ``--diff`` boot flag
-- and the tests verify opening, refusal messages, the close-then-key
handoff (F4 + R10) and the copy + save round trip on real temp files.
"""

# tests legitimately poke at screen internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

# The bundled yate/extensions/ directory is auto-loaded with every YateApp;
# make sure the Python LSP extension never probes PATH or spawns a real server
# while the UI test suite runs.
os.environ["YATE_PYTHON_LSP"] = "off"

from yate.app import YateApp
from yate.editor_view.diffview import MAX_DIFF_LINES, DiffPane, DiffScreen


def _write(tmp_path: Path, name: str, text: str) -> Path:
    """Persist *text* to a temp file and return its path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _plain(content: Any) -> str:
    """Plain text of a widget renderable (rich Text, str, or other)."""
    plain = getattr(content, "plain", None)
    return plain if isinstance(plain, str) else str(content)


def _message_text(app: YateApp) -> str:
    """The prompt bar's message-line text (refusals from open_diff)."""
    prompt_bar = app.editor.prompt_bar
    assert prompt_bar is not None
    return _plain(prompt_bar.message.content)


def test_command_diff_opens_two_way_screen(tmp_path: Path) -> None:
    """``:diff a b`` pushes the diff screen with two panes."""

    async def scenario() -> None:
        f1 = _write(tmp_path, "left.txt", "one\ntwo\nthree")
        f2 = _write(tmp_path, "right.txt", "one\nTWO\nthree")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f"diff {f1} {f2}")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            assert len(screen.query(DiffPane)) == 2

    asyncio.run(scenario())


def test_command_diff_quoted_paths_in_spaced_dir_open_two_panes(
    tmp_path: Path,
) -> None:
    """Quoted paths inside a directory with spaces open the two-pane screen."""

    async def scenario() -> None:
        spaced = tmp_path / "my dir"
        spaced.mkdir()
        f1 = spaced / "left one.txt"
        f1.write_text("one\ntwo\nthree", encoding="utf-8")
        f2 = spaced / "right two.txt"
        f2.write_text("one\nTWO\nthree", encoding="utf-8")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f'diff "{f1}" "{f2}"')
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            assert len(screen.query(DiffPane)) == 2

    asyncio.run(scenario())


def test_command_diff_three_files_open_three_panes(tmp_path: Path) -> None:
    """Three files open the 3way screen and classify the conflict."""

    async def scenario() -> None:
        base = _write(tmp_path, "base.txt", "a\nb\nc")
        local = _write(tmp_path, "local.txt", "a\nB\nc")
        remote = _write(tmp_path, "remote.txt", "a\nC\nc")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f"diff {base} {local} {remote}")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiffScreen)
            assert len(screen.query(DiffPane)) == 3
            assert any(region.kind == "conflict" for region in screen._regions)

    asyncio.run(scenario())


def test_command_diff_bad_arg_count_stays_on_base(tmp_path: Path) -> None:
    """A wrong file count reports usage on the message line, no screen."""

    async def scenario() -> None:
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command("diff onlyone")
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert "usage" in _message_text(app)

    asyncio.run(scenario())


def test_command_diff_missing_file_reports_and_stays(tmp_path: Path) -> None:
    """A missing path is refused with a message; the base screen stays."""

    async def scenario() -> None:
        f1 = _write(tmp_path, "left.txt", "one")
        nope = tmp_path / "missing.txt"
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f"diff {f1} {nope}")
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert "no such file" in _message_text(app)

    asyncio.run(scenario())


def test_command_diff_directory_with_text_suffix_reports_and_stays(
    tmp_path: Path,
) -> None:
    """A directory named like a text file is refused; no crash, no screen.

    ``Workspace.is_text_file`` trusts TEXT_SUFFIXES before any content
    sniffing, so the entry point must check ``is_file()`` first --
    ``Document.open`` would otherwise raise ``IsADirectoryError`` straight
    into the crash path (command actions have no try/except).
    """

    async def scenario() -> None:
        fake = tmp_path / "fake.txt"
        fake.mkdir()
        f2 = _write(tmp_path, "right.txt", "one")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f"diff {fake} {f2}")
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert "no such file" in _message_text(app)

    asyncio.run(scenario())


def test_command_diff_oversized_file_reports_and_stays(tmp_path: Path) -> None:
    """A file beyond MAX_DIFF_LINES is refused; the base screen stays.

    The refusal branch lives in :meth:`OverlayFlows.open_diff` (its message
    names the file); this locks the real entry path after the unused
    ``check_sizes`` helper was removed.
    """

    async def scenario() -> None:
        big = _write(tmp_path, "big.txt", "x\n" * (MAX_DIFF_LINES + 1))
        f2 = _write(tmp_path, "right.txt", "one")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f"diff {big} {f2}")
            await pilot.pause()
            assert len(app.screen_stack) == 1
            assert "too large" in _message_text(app)

    asyncio.run(scenario())


def test_cli_boot_diff_flag_opens_screen_after_mount(tmp_path: Path) -> None:
    """``YateApp(diff_files=...)`` pushes the diff screen after mount."""

    async def scenario() -> None:
        f1 = _write(tmp_path, "left.txt", "one\ntwo")
        f2 = _write(tmp_path, "right.txt", "one\nTWO")
        app = YateApp(diff_files=[f1, f2])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, DiffScreen)

    asyncio.run(scenario())


def test_diff_close_returns_keys_to_editor(tmp_path: Path) -> None:
    """After the modal closes the next key lands in the main buffer (R10).

    Two escapes close the (unmodified) diff screen; the following ``x`` must
    reach the editor's buffer -- nothing may stay swallowed by the closed
    modal and nothing may dispatch twice.
    """

    async def scenario() -> None:
        f1 = _write(tmp_path, "left.txt", "one\ntwo")
        f2 = _write(tmp_path, "right.txt", "one\nTWO")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f"diff {f1} {f2}")
            await pilot.pause()
            assert isinstance(app.screen, DiffScreen)
            await pilot.press("escape")  # first press: warn only
            assert isinstance(app.screen, DiffScreen)
            await pilot.press("escape")  # second press: close
            await pilot.pause()
            assert len(app.screen_stack) == 1
            await pilot.press("x")  # must reach the main buffer
            buffer = app.editor.session.buffer
            assert "x" in buffer.lines[buffer.row]

    asyncio.run(scenario())


def test_copy_persisted_via_command_flow(tmp_path: Path) -> None:
    """Copy a hunk via keys and persist the target side to disk.

    The key sequence is the one locked by the plan-b screen tests: select
    the hunk (alt+down), copy left->right (alt+right), focus the modified
    target side (tab), save (ctrl+s).
    """

    async def scenario() -> None:
        f1 = _write(tmp_path, "left.txt", "one\ntwo\nthree")
        f2 = _write(tmp_path, "right.txt", "one\nTWO\nthree")
        app = YateApp(target=tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.editor.run_command(f"diff {f1} {f2}")
            await pilot.pause()
            assert isinstance(app.screen, DiffScreen)
            await pilot.press("alt+down")  # select the only hunk
            await pilot.press("alt+right")  # copy left -> right
            await pilot.press("tab")  # focus the modified (right) side
            await pilot.press("ctrl+s")  # save it
            await pilot.pause()
            assert f2.read_text(encoding="utf-8") == "one\ntwo\nthree"

    asyncio.run(scenario())
