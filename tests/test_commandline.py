"""Unit tests for the ex-line two-phase tab completion (issue IKQ4VA).

Pilot-driven (headless Textual): a minimal host app mounts the PromptBar,
activates a command prompt and drives the tab state machine; assertions run
against the ``CommandInput`` / ``PromptBar`` state directly.
"""

# tests legitimately poke at prompt internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio

from rich.text import Text
from textual.app import App, ComposeResult
from typing import override

from yate.editor_view.commandline import OWNER_CANDIDATES, PromptBar


class _Host(App[None]):
    """Minimal host app that mounts the PromptBar under test."""

    def __init__(self, bar: PromptBar) -> None:
        super().__init__()
        self._bar = bar

    @override
    def compose(self) -> ComposeResult:
        yield self._bar


def _bar(matches: list[str]) -> PromptBar:
    """A mounted-ready PromptBar whose completer always returns *matches*."""
    return PromptBar(
        lambda _text, _mode: list(matches),
        cancel_hook=lambda: None,
        focus_editor=lambda: None,
        refresh=lambda: None,
    )


def _prompt(bar: PromptBar, value: str) -> None:
    """Activate the command prompt on *bar* positioned at *value*."""
    assert bar.activate("command")
    bar.input.value = value


def _tab(bar: PromptBar) -> None:
    """One tab-completion round (the handler bound to the Tab key)."""
    bar.input._do_tab_completion()


def test_tab_first_shows_candidates_does_not_apply() -> None:
    """The first Tab lists the matches and leaves the typed value alone."""
    bar = _bar(["set", "shade"])

    async def scenario() -> None:
        app = _Host(bar)
        async with app.run_test(size=(100, 10)):
            _prompt(bar, "se")
            _tab(bar)
            # nothing applied yet: the value is untouched and the candidate
            # string owns the message slot
            assert bar.input.value == "se"
            assert bar.input._tab_matches == ["set", "shade"]
            assert bar.input._tab_index == -1
            assert bar.owner == OWNER_CANDIDATES
            assert bar.message.display

    asyncio.run(scenario())


def test_tab_second_applies_first_candidate() -> None:
    """The second Tab applies the first candidate and drops the string."""
    bar = _bar(["set", "shade"])

    async def scenario() -> None:
        app = _Host(bar)
        async with app.run_test(size=(100, 10)):
            _prompt(bar, "se")
            _tab(bar)
            _tab(bar)
            assert bar.input.value == "set"
            assert bar.input._tab_index == 0
            assert bar.owner != OWNER_CANDIDATES

    asyncio.run(scenario())


def test_tab_cycling_through_candidates() -> None:
    """Further Tabs cycle through every match and wrap around."""
    bar = _bar(["set", "shade"])

    async def scenario() -> None:
        app = _Host(bar)
        async with app.run_test(size=(100, 10)):
            _prompt(bar, "se")
            _tab(bar)  # show
            _tab(bar)  # apply "set"
            _tab(bar)  # cycle -> "shade"
            assert bar.input.value == "shade"
            assert bar.input._tab_index == 1
            _tab(bar)  # wrap -> "set"
            assert bar.input.value == "set"
            assert bar.input._tab_index == 0

    asyncio.run(scenario())


def test_any_edit_key_clears_candidates() -> None:
    """Any non-Tab key resets the round and hides the candidate string."""
    bar = _bar(["set", "shade"])

    async def scenario() -> None:
        app = _Host(bar)
        async with app.run_test(size=(100, 10)) as pilot:
            _prompt(bar, "se")
            _tab(bar)
            assert bar.owner == OWNER_CANDIDATES
            await pilot.press("a")
            await pilot.pause()
            assert bar.owner != OWNER_CANDIDATES
            assert bar.input._tab_matches == []
            assert bar.input._tab_index == -1

    asyncio.run(scenario())


def test_escape_clears_candidates() -> None:
    """Escape cancels the prompt: the message slot is no longer owned."""
    bar = _bar(["set", "shade"])

    async def scenario() -> None:
        app = _Host(bar)
        async with app.run_test(size=(100, 10)) as pilot:
            _prompt(bar, "se")
            _tab(bar)
            assert bar.owner == OWNER_CANDIDATES
            await pilot.press("escape")
            await pilot.pause()
            assert bar.owner != OWNER_CANDIDATES

    asyncio.run(scenario())


def test_escape_resets_tab_state_for_the_next_prompt() -> None:
    """A stale tab round does not leak into the next prompt (review M1).

    ``se`` + tab leaves candidates pending; escape then reopening a prompt
    and tabbing at once must start a fresh round on the new value instead
    of applying a leftover match from the cancelled one.
    """
    bar = _bar(["set", "shade"])

    async def scenario() -> None:
        app = _Host(bar)
        async with app.run_test(size=(100, 10)) as pilot:
            _prompt(bar, "se")
            _tab(bar)
            assert bar.input._tab_matches == ["set", "shade"]
            await pilot.press("escape")
            await pilot.pause()
            # the escape branch itself drops the round
            assert bar.input._tab_matches == []
            assert bar.input._tab_index == -1
            _prompt(bar, "sh")
            # activate() resets again (single entry point, double safety)
            assert bar.input._tab_matches == []
            _tab(bar)
            # first tab of a clean round: value untouched, new matches shown
            assert bar.input.value == "sh"
            assert bar.input._tab_matches == ["set", "shade"]
            assert bar.owner == OWNER_CANDIDATES

    asyncio.run(scenario())


def test_candidates_with_brackets_render_verbatim() -> None:
    """``[`` in a candidate is escaped, not parsed as a markup tag (M2)."""
    bar = _bar(["[test].py", "foo"])

    async def scenario() -> None:
        app = _Host(bar)
        async with app.run_test(size=(100, 10)):
            _prompt(bar, "[")
            _tab(bar)
            assert bar.owner == OWNER_CANDIDATES
            rendered = bar.message.content
            assert isinstance(rendered, str)
            # the source string carries the escape so Rich cannot eat the
            # bracket as a tag (unescaped, "{[test].py, foo}" renders as
            # "{.py, foo}")
            assert rendered == "{\\[test].py, foo}"
            # ... and the markup renders back to the verbatim candidate text
            assert Text.from_markup(rendered).plain == "{[test].py, foo}"

    asyncio.run(scenario())


def test_candidates_truncated_when_oversize() -> None:
    """A candidate string wider than the input is cut with a ``...`` hint."""
    long_names = ["very-long-candidate-name-" + str(i) for i in range(5)]
    bar = _bar(long_names)

    async def scenario() -> None:
        app = _Host(bar)
        async with app.run_test(size=(100, 10)) as pilot:
            _prompt(bar, "very")
            await pilot.pause()
            _tab(bar)
            assert bar.owner == OWNER_CANDIDATES
            rendered = bar.message.content
            assert isinstance(rendered, str)
            width: int = bar.input.size.width
            assert width > 0
            # truncated to the input width (the "}" overshoots by one cell)
            assert rendered.endswith("...}")
            assert len(rendered) <= width + 1

    asyncio.run(scenario())
