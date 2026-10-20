"""Debounce-timer lifecycle of the manual / changelog doc screen.

``MarkdownDocScreen._schedule_search`` arms an ``asyncio.TimerHandle`` whose
callback closes over the screen itself.  A query typed inside the debounce
window and then dismissed used to leave that armed handle -- and with it the
reference to the unmounted screen -- alive until it fired on its own;
``on_unmount`` now cancels it and drops the pending query.

The cases drive a real headless app through pilot and arm the timer with a
real ``Input.Changed`` message, so nothing about Textual's message pump is
stubbed.  Only the hit-rebuild itself is replaced: what is under test is *when*
the search runs, not what it paints.
"""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from textual.widgets import Input, Static

from conftest import wait_until
from manual_doc_fixture import MANUAL_DOC_FIXTURE
from yate.app import YateApp
from yate.editor_view import theme as yate_theme
from yate.editor_view.manual import (
    MarkdownDocScreen,
    _strip_text,
    doc_rich_theme,
    render_doc_lines,
)


def _install_search_spy(
    monkeypatch: pytest.MonkeyPatch, calls: list[str]
) -> None:
    """Replace the hit rebuild with a recorder of the queries it received."""

    def _run_search(_screen: MarkdownDocScreen, query: str) -> None:
        calls.append(query)

    monkeypatch.setattr(MarkdownDocScreen, "_run_search", _run_search)


def test_dismiss_within_debounce_window_leaves_no_pending_timer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """escape inside the debounce window cancels the armed timer.

    Without ``on_unmount`` the handle stayed on the loop and kept the
    dismissed screen reachable; the ``is_mounted`` guard inside the flush
    made the late callback harmless but the reference outlived it anyway.
    """
    calls: list[str] = []
    _install_search_spy(monkeypatch, calls)

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
                loading = screen.query_one("#doc-loading", Static)
                # same worker-race guard as the sibling manual tests: the
                # document is read and parsed in a background thread
                assert await wait_until(
                    pilot, lambda: not loading.display, timeout=15.0
                )

                # Arm the debounce far beyond this test's lifetime (the same
                # determinism trick as tests/test_app_render.py): with 0.12s a
                # loaded runner can spend longer than that between the escape
                # key and on_unmount, so the timer legitimately fires while the
                # screen is still mounted and the silent-callback assertion
                # below fails for a scheduling reason, not a product one.
                monkeypatch.setattr(screen, "_SEARCH_DEBOUNCE_S", 30.0)

                field = screen.query_one("#doc-search-input", Input)
                # one Input.Changed arms the debounce exactly like a
                # keystroke does -- the field is deliberately left unfocused
                screen.post_message(Input.Changed(field, "exit"))
                await pilot.pause()
                assert screen._search_timer is not None

                # with the bar unfocused, escape reaches the screen's own
                # dismiss binding and closes the viewer itself
                await pilot.press("escape")
                # Textual retires the popped screen in a background task: poll
                # for the full retirement instead of assuming one pause is
                # enough, then let any in-flight messages settle while the
                # screen is already popped -- a straggler Input.Changed that
                # lands after the cancel must not re-arm the timer
                assert await wait_until(
                    pilot, lambda: screen not in app.screen_stack, timeout=5.0
                )
                await pilot.pause()
                assert await wait_until(
                    pilot, lambda: screen._search_timer is None, timeout=5.0
                )
                assert screen._pending_query is None
                # ... and the cancelled callback never runs.  The arm is 30s,
                # so a straggler cannot fire the timer by itself: only a lost
                # cancel can make this fail.
                await pilot.pause(MarkdownDocScreen._SEARCH_DEBOUNCE_S * 5)
                assert calls == []
                assert screen._search_timer is None  # nothing re-armed it

    asyncio.run(scenario())


def test_search_within_debounce_window_runs_when_screen_stays_mounted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reverse path: the teardown must not kill a live debounce timer."""
    calls: list[str] = []
    _install_search_spy(monkeypatch, calls)

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
                loading = screen.query_one("#doc-loading", Static)
                assert await wait_until(
                    pilot, lambda: not loading.display, timeout=15.0
                )

                field = screen.query_one("#doc-search-input", Input)
                screen.post_message(Input.Changed(field, "exit"))
                await pilot.pause()
                assert screen._search_timer is not None

                await pilot.pause(MarkdownDocScreen._SEARCH_DEBOUNCE_S * 5)

                assert calls == ["exit"]
                assert screen in app.screen_stack
                # the callback clears its own handle before flushing
                assert screen._search_timer is None

    asyncio.run(scenario())


def test_fire_search_flushed_immediately_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """enter flushes the pending query synchronously and still runs it once."""
    calls: list[str] = []
    _install_search_spy(monkeypatch, calls)

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
                loading = screen.query_one("#doc-loading", Static)
                assert await wait_until(
                    pilot, lambda: not loading.display, timeout=15.0
                )

                field = screen.query_one("#doc-search-input", Input)
                # typing and enter are posted back to back so the submit is
                # guaranteed to land inside the debounce window: four real
                # pilot key presses already overrun the 0.12 s window on a
                # loaded box, which would silently exercise the timer path
                screen.post_message(Input.Changed(field, "exit"))
                screen.post_message(Input.Submitted(field, "exit"))
                await pilot.pause()

                # the submit flushed the armed timer instead of waiting it out
                assert calls == ["exit"]
                assert screen._search_timer is None
                await pilot.pause(MarkdownDocScreen._SEARCH_DEBOUNCE_S * 5)
                assert calls == ["exit"]

    asyncio.run(scenario())


# --- rendering (pure, no app) -------------------------------------------------


def test_render_doc_lines_keeps_the_markdown_structure() -> None:
    """Headings, emphasis and table borders survive the one-shot render."""
    source = (
        "# Title\n\n"
        "plain **bold** text\n\n"
        "| a | b |\n| - | - |\n| 1 | 2 |\n"
    )
    rows = render_doc_lines(source, 40, active=yate_theme.active())

    text = "\n".join(_strip_text(row) for row in rows)
    assert "Title" in text
    assert "bold" in text
    # box-drawing borders: any glyph past the ASCII range (the exact code point
    # depends on Rich's table style, so pin the presence, not the glyph)
    assert any(ord(char) > 0x2000 for char in text)
    # every row fits the width it was rendered for: search hits are indexed
    # per row, so a row wider than the body would re-wrap and move them
    assert all(row.cell_length <= 40 for row in rows)


def test_render_doc_lines_wraps_to_the_requested_width() -> None:
    """A paragraph longer than the width occupies more than one row."""
    source = "word " * 40
    narrow = render_doc_lines(source, 20, active=yate_theme.active())
    wide = render_doc_lines(source, 80, active=yate_theme.active())
    assert len(narrow) > len(wide)
    assert all(row.cell_length <= 20 for row in narrow)


def test_doc_rich_theme_colors_headings_from_the_active_palette() -> None:
    """The Rich theme binds Rich's markdown style names to yate colors."""
    active = yate_theme.active()
    rich_theme = doc_rich_theme(active)

    heading = rich_theme.styles["markdown.h1"]
    assert heading.color is not None
    assert heading.color.get_truecolor().hex.lower() == active.accent2.lower()
    assert heading.bold
    code = rich_theme.styles["markdown.code_block"]
    assert code.bgcolor is not None
    assert code.bgcolor.get_truecolor().hex.lower() == active.panel.lower()
