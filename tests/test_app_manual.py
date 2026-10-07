"""Manual / markdown doc headless Textual UI tests (run via pilot, no real terminal)."""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch
import pytest
from textual.widget import Widget
from yate.app import YateApp
from yate.editor_view.manual import MarkdownDocScreen
from conftest import wait_until
from manual_doc_fixture import MANUAL_DOC_FIXTURE

# ------------------------------------------------------ manual / markdown doc


def test_f8_opens_manual_and_esc_closes() -> None:
    from textual.widgets import Markdown, Static

    async def scenario() -> None:
        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_doc_markdown",
            return_value=MANUAL_DOC_FIXTURE,
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("f8")
                await pilot.pause()
                assert isinstance(app.screen, MarkdownDocScreen)
                md = app.screen.query_one("#doc-md", Markdown)
                loading = app.screen.query_one("#doc-loading", Static)
                # the markdown worker reads/parses off the loop; poll until the
                # load completes before asserting content -- a loaded CI box can
                # still be mid-read after the first pause (asserting the source
                # immediately once raced as '' != manual there)
                assert await wait_until(
                    pilot, lambda: not loading.display, timeout=15.0
                )
                # F8 loads the injected fixture document
                assert md.source == MANUAL_DOC_FIXTURE
                # the viewer follows the active yate theme via the bridge -- no
                # per-screen theme switch happens
                assert app.theme == "yate-mocha"
                # f8 again must not stack a second viewer
                await pilot.press("f8")
                await pilot.pause()
                assert len(app.screen_stack) == 2
                await pilot.press("escape")
                await pilot.pause()
                assert not isinstance(app.screen, MarkdownDocScreen)
                # ... and the theme is still yate-mocha afterwards (no restore)
                assert app.theme == "yate-mocha"

    asyncio.run(scenario())


def test_startup_selects_yate_bridge_theme() -> None:
    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # startup defaults to the mocha yate theme -> yate-mocha bridge
            assert app.theme == "yate-mocha"
            assert app.get_theme("yate-mocha") is not None

    asyncio.run(scenario())


def test_set_theme_switches_textual_theme_and_overlay_border() -> None:
    async def scenario() -> None:
        from textual.color import Color

        from yate.editor_view import theme as yate_theme

        app = YateApp()
        try:
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                # switch to latte -> app.theme becomes yate-latte, the
                # overlay border token ($primary) resolves to latte's
                # accent2 (mauve)
                app.editor.run_command("set theme=latte")
                await pilot.pause()
                await pilot.pause()
                assert app.theme == "yate-latte"
                # open the help overlay and inspect its border color -- it
                # must follow the latte palette, not the textual-dark blue.
                # The border shorthand returns an Edges NamedTuple of
                # (type, Color) per side.
                await pilot.press("f1")
                await pilot.pause()
                overlay = app.screen.query_one("#overlay")
                border_color = overlay.styles.border.top[1]
                expected = Color.parse(yate_theme.THEMES["latte"].accent2)
                assert border_color.hex == expected.hex
                await pilot.press("escape")
                await pilot.pause()

                # one non-Mocha dark theme proves the textual-dark blue is
                # gone
                app.editor.run_command("set theme=onedark")
                await pilot.pause()
                await pilot.pause()
                assert app.theme == "yate-onedark"
                await pilot.press("f1")
                await pilot.pause()
                overlay = app.screen.query_one("#overlay")
                border_color = overlay.styles.border.top[1]
                expected = Color.parse(yate_theme.THEMES["onedark"].accent2)
                assert border_color.hex == expected.hex
        finally:
            # restore the default theme even on failure: a leaked latte /
            # onedark would cascade into every later theme-sensitive test
            yate_theme.set_theme("mocha")

    asyncio.run(scenario())


def test_startup_falls_back_to_mocha_when_selected_theme_bridge_fails() -> None:
    """A yate theme with an unusable bridge must not crash startup."""
    from dataclasses import fields as dc_fields

    from yate.editor_view.theme import THEMES, Theme, set_theme

    async def scenario() -> None:
        base = THEMES["mocha"]
        d = {f.name: getattr(base, f.name) for f in dc_fields(base)}
        d["name"] = "broken-bridge"
        d["bg"] = "#gggggg"  # invalid -> to_textual_theme raises
        # d re-uses Theme's real field names; pyright only sees dict[str, object].
        broken = Theme(**d)  # type: ignore[arg-type]
        THEMES["broken-bridge"] = broken
        try:
            app = YateApp(theme_name="broken-bridge")
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                # bridge failed for 'broken-bridge'; startup fell back to mocha
                assert app.theme == "yate-mocha"
                assert any("broken-bridge" in e for e in app.editor.config.errors)
        finally:
            THEMES.pop("broken-bridge", None)
            set_theme("mocha")

    asyncio.run(scenario())


def test_valid_custom_yate_theme_gets_working_bridge() -> None:
    from dataclasses import fields as dc_fields

    from textual.color import Color

    from yate.editor_view.theme import THEMES, Theme, set_theme

    async def scenario() -> None:
        base = THEMES["mocha"]
        d = {f.name: getattr(base, f.name) for f in dc_fields(base)}
        d["name"] = "custom-ok"
        d["accent2"] = "#ff00ff"  # distinct so the bridge border is testable
        # d re-uses Theme's real field names; pyright only sees dict[str, object].
        custom = Theme(**d)  # type: ignore[arg-type]
        THEMES["custom-ok"] = custom
        try:
            app = YateApp(theme_name="custom-ok")
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                assert app.theme == "yate-custom-ok"
                assert app.get_theme("yate-custom-ok") is not None
                # the overlay border follows the custom theme's accent2
                await pilot.press("f1")
                await pilot.pause()
                overlay = app.screen.query_one("#overlay")
                border_color = overlay.styles.border.top[1]
                assert border_color.hex == Color.parse("#ff00ff").hex
        finally:
            THEMES.pop("custom-ok", None)
            set_theme("mocha")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "cmd_arg,lang",
    [("zh", "zh"), ("en", "en"), ("bogus", "en")],
    ids=["zh", "en", "bogus"],
)
def test_manual_command_selects_language(cmd_arg: str, lang: str) -> None:
    async def scenario() -> None:
        from textual.widgets import Markdown, Static

        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_doc_markdown",
            return_value=MANUAL_DOC_FIXTURE,
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                app.editor.run_command(f"manual {cmd_arg}".strip())
                await pilot.pause()
                assert isinstance(app.screen, MarkdownDocScreen)
                loading = app.screen.query_one("#doc-loading", Static)
                # the document loads in a background worker; a loaded CI box can
                # still be mid-read after the first pause (pipeline #82 raced
                # '' != manual there) -- poll until the load lands first
                assert await wait_until(
                    pilot, lambda: not loading.display, timeout=15.0
                )
                md = app.screen.query_one("#doc-md", Markdown)
                assert md.source == MANUAL_DOC_FIXTURE

    asyncio.run(scenario())


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_both_language_files_bundled(lang: str) -> None:
    from yate.editor_view.manual import load_manual_markdown

    text = load_manual_markdown(lang)
    assert len(text) > 1000
    assert text.lstrip().startswith("# yate")


def test_manual_search_filters_and_cycles_matches() -> None:
    from textual.containers import Horizontal
    from textual.widgets import Input, Markdown, Static
    from yate.editor_view.manual import _widget_plain_text

    async def scenario() -> None:
        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_doc_markdown",
            return_value=MANUAL_DOC_FIXTURE,
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("f8")
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, MarkdownDocScreen)
                bar = screen.query_one("#doc-search-bar", Horizontal)
                field = screen.query_one("#doc-search-input", Input)
                status = screen.query_one("#doc-search-status", Static)
                md = screen.query_one("#doc-md", Markdown)
                # same worker-race guard as test_manual_command_selects_language:
                # searching an unloaded document would race 0 hits
                loading = screen.query_one("#doc-loading", Static)
                assert await wait_until(
                    pilot, lambda: not loading.display, timeout=15.0
                )

                def footer_text() -> str:
                    return _widget_plain_text(
                        screen.query_one("#doc-footer", Static)
                    )

                assert not bar.display
                # bar hidden: footer advertises n/N to repeat a search
                assert "n/N" in footer_text()
                # ctrl+f reveals the search bar and focuses it
                await pilot.press("ctrl+f")
                await pilot.pause()
                assert bar.display
                assert screen.focused is field
                # bar open: footer must advertise Enter / Shift+Enter (typing
                # n/N there are search characters, not navigation)
                search_footer = footer_text()
                assert "enter" in search_footer.lower()
                assert "shift+enter" in search_footer.lower()
                assert "repeat last match" not in search_footer
                # typing live-marks every block containing the query; the
                # trailing pause spans the 0.12s debounce window, which the
                # tiny fixture no longer covers as a side effect of slow
                # big-document processing
                await pilot.press("y", "a", "t", "e")
                await pilot.pause(0.15)
                private = cast(Any, screen)
                assert len(private._hits) >= 2
                assert private._hit_index == 0
                assert len(list(md.query(".doc-hit-current"))) == 1
                assert len(list(md.query(".doc-hit"))) >= 1
                assert "1/" in str(status.content)
                # enter advances to the next match, shift+enter goes back
                await pilot.press("enter")
                await pilot.pause()
                assert private._hit_index == 1
                assert "2/" in str(status.content)
                await pilot.press("shift+enter")
                await pilot.pause()
                assert private._hit_index == 0
                # escape while typing closes only the bar (manual stays open)…
                await pilot.press("escape")
                await pilot.pause()
                assert not bar.display
                assert isinstance(app.screen, MarkdownDocScreen)
                # footer switches back to the browse hints (n/N repeat)
                assert "n/N" in footer_text()
                assert "repeat last match" in footer_text()
                # …and n/N repeat the last search with highlights still present
                await pilot.press("n")
                await pilot.pause()
                assert private._hit_index == 1
                await pilot.press("N")
                await pilot.pause()
                assert private._hit_index == 0
                # escape with the bar closed dismisses the manual itself
                await pilot.press("escape")
                await pilot.pause()
                assert not isinstance(app.screen, MarkdownDocScreen)

    asyncio.run(scenario())


def test_manual_search_step_lands_on_exact_rendered_row() -> None:
    """Regression: n/N stepped the counter but did not scroll when
    several matches lived in one wrapped widget (scroll was widget
    level); table cells were not searchable at all."""
    from textual.containers import VerticalScroll

    async def scenario() -> None:
        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_doc_markdown",
            return_value=MANUAL_DOC_FIXTURE,
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("f8")
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, MarkdownDocScreen)
                md = screen.query_one("Markdown")
                # layout readiness, not just child count: _run_search scans
                # widget.region.height, which is 0 for every widget until the
                # refresh cycle lays the screen out (flaky under full-suite
                # load, where that cycle lands after the search below)
                await wait_until(
                    pilot,
                    lambda: len(list(md.walk_children())) > 20
                    and any(w.region.height > 0 for w in md.walk_children(Widget)),
                )
                private = cast(Any, screen)
                scroll = screen.query_one("#doc-scroll", VerticalScroll)

                # table cell content is now searched too
                private._run_search("item")
                assert private._hits
                widget_types = {type(w).__name__ for w, _r, _c, _l in private._hits}
                assert "MarkdownTableCellContents" in widget_types

                # matches inside one wrapped widget must land on distinct rows:
                # measure each target from the same baseline (top), so the row
                # offset is the only thing that differs
                private._run_search("ctrl")
                assert len(private._hits) > 10
                moved = 0
                for i in range(1, len(private._hits)):
                    w0, r0, _c0, _l0 = private._hits[i - 1]
                    w1, r1, _c1, _l1 = private._hits[i]
                    if w0 is w1 and r0 != r1:
                        scroll.scroll_to(y=0, animate=False, immediate=True)
                        private._hit_index = i - 1
                        private._goto_current_hit()
                        y0 = float(scroll.scroll_target_y)
                        scroll.scroll_to(y=0, animate=False, immediate=True)
                        private._hit_index = i
                        private._goto_current_hit()
                        y1 = float(scroll.scroll_target_y)
                        if y0 == y1 == float(scroll.max_scroll_y):
                            continue  # bottom clamp: both rows already visible
                        assert y0 != y1, (
                            f"same-widget rows {r0}/{r1} share a scroll target"
                        )
                        assert abs((y1 - y0) - (r1 - r0)) <= 1
                        moved += 1
                assert moved > 0

    asyncio.run(scenario())


def test_manual_search_no_matches_then_slash_reopens() -> None:
    from textual.containers import Horizontal
    from textual.widgets import Input, Markdown, Static

    async def scenario() -> None:
        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_doc_markdown",
            return_value=MANUAL_DOC_FIXTURE,
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("f8")
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, MarkdownDocScreen)
                # "/" (textual key name "slash") also opens the search bar
                await pilot.press("slash")
                await pilot.pause()
                bar = screen.query_one("#doc-search-bar", Horizontal)
                field = screen.query_one("#doc-search-input", Input)
                status = screen.query_one("#doc-search-status", Static)
                md = screen.query_one("#doc-md", Markdown)
                assert bar.display
                assert screen.focused is field
                # a query present nowhere reports "no matches" and tints
                # nothing (the pause spans the debounce window -- see the
                # filters test)
                await pilot.press("z", "q", "z", "q", "w", "x")
                await pilot.pause(0.15)
                private = cast(Any, screen)
                assert private._hits == []
                assert private._hit_index == -1
                assert len(list(md.query(".doc-hit"))) == 0
                assert "no matches" in str(status.content)
                # clearing the query removes the error state (debounced
                # flush needs the same window as above)
                await pilot.press(*(("backspace",) * 10))
                await pilot.pause(0.15)
                assert field.value == ""
                assert private._hits == []
                assert "type to search" in str(status.content)
                assert isinstance(app.screen, MarkdownDocScreen)

    asyncio.run(scenario())


# ----------------------------------------------------- async background workers


def test_manual_paints_before_content_loads() -> None:
    from textual.widgets import Markdown, Static

    gate = threading.Event()

    def slow_load(kind: str, lang: str = "en") -> str:
        gate.wait(timeout=10.0)
        return MANUAL_DOC_FIXTURE

    async def scenario() -> None:
        app = YateApp()
        with patch(
            "yate.editor_view.manual.load_doc_markdown", side_effect=slow_load
        ):
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.press("f8")
                # while the worker thread is still reading: screen + loading
                # line are already on screen, the markdown itself is empty
                await pilot.pause(0.15)
                assert isinstance(app.screen, MarkdownDocScreen)
                md = app.screen.query_one("#doc-md", Markdown)
                loading = app.screen.query_one("#doc-loading", Static)
                assert md.source == ""
                assert loading.display
                # responsiveness proven: release the parked reader thread so
                # the content arrives without a fixed sleep
                gate.set()
                # content then arrives without dismissing the screen
                loaded = await wait_until(
                    pilot,
                    lambda: bool(md.source) and not loading.display,
                    timeout=30.0,
                )
                assert loaded
                assert md.source == MANUAL_DOC_FIXTURE
                assert not loading.display
                assert isinstance(app.screen, MarkdownDocScreen)

    asyncio.run(scenario())


def test_shell_command_runs_without_freezing_ui() -> None:
    from unittest.mock import patch

    from yate.editor_view.modals import OutputScreen
    from yate.services.shell import ShellResult

    gate = threading.Event()

    def slow_shell(command: str, cwd: object = None,
                   timeout: float = 60.0) -> ShellResult:
        # parked until the test has proven the UI stays responsive, so
        # headless message-pump slowness cannot let it finish too early
        gate.wait(timeout=10.0)
        return ShellResult(command, 0, "yate-async-marker", Path.cwd())

    async def scenario() -> None:
        app = YateApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            prompt_bar = app.editor.prompt_bar
            assert prompt_bar is not None
            with patch("yate.flows.shell_flows.run_shell", side_effect=slow_shell):
                # F2 opens the shell prompt in vsc mode (":" is vim-only)
                await pilot.press("f2")
                assert prompt_bar.active_mode == "shell"
                for ch in "echo hi":
                    await pilot.press(ch)
                await pilot.press("enter")
                # command dispatched: prompt closed, no output screen yet,
                # focus back in the editor while the thread is running
                await pilot.pause(0.15)
                assert len(app.screen_stack) == 1
                assert app.focused is app.editor.panes.active_view
                # the TUI stays responsive: F1 help opens over the running job
                await pilot.press("f1")
                await pilot.pause(0.1)
                assert len(app.screen_stack) == 2
                await pilot.press("escape")
                await pilot.pause(0.1)
                # responsiveness proven: release the parked shell thread so
                # the output screen arrives without a fixed sleep
                gate.set()
            # the output screen appears when the worker finishes
            shown = await wait_until(
                pilot, lambda: isinstance(app.screen, OutputScreen),
                timeout=10.0,
            )
            assert shown
            out = cast(OutputScreen, app.screen)
            assert "yate-async-marker" in out.output_text
            assert out.exit_code == 0

    asyncio.run(scenario())
