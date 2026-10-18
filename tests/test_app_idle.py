"""Teardown-race guard in ``YateApp.poll_idle``.

The one-second poll timer armed in ``on_mount`` can fire after the last
screen has been popped during app teardown; without a stack check the poll
then touches ``self.screen`` and Textual raises ``ScreenStackError: No
screens on stack``.  Under coverage instrumentation the load is enough to
trip the race in 3/3 full pytest runs (failures only in pilot cases of
untouched files).  The guard makes the poll skip silently on an empty
stack, and the live-path case proves the guard does not break normal
screensaver scheduling.
"""

# tests legitimately poke at internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio

import pytest

from yate.app import YateApp


def test_poll_idle_survives_an_empty_screen_stack() -> None:
    """A direct-constructed (unmounted) app survives ``poll_idle``.

    Textual leaves a never-mounted app's screen stack empty, so calling
    the poll right after construction hits the teardown race head-on:
    before the guard this raised ``ScreenStackError``.
    """
    app = YateApp()
    # Lock the Textual premise this regression rides on: an unmounted
    # instance has an empty screen stack.  If a Textual upgrade changes
    # that, this assert fails first instead of the guard going untested.
    assert app._screen_stack == []
    # Before the empty-stack guard this raised textual.app.ScreenStackError.
    app.poll_idle()


def test_poll_idle_still_toggles_when_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live path: a due tracker still triggers the screensaver toggle."""
    calls: list[str] = []

    class _AlwaysDue:
        """Stand-in idle tracker that reports due on every poll."""

        def due(self, _interval: float) -> bool:
            return True

        def poke(self) -> None:
            return None

    async def scenario() -> None:
        app = YateApp()

        def record(name: str) -> None:
            calls.append(name)

        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            # on_mount installed a real tracker during startup; swap in the
            # always-due stand-in only now so the guard's own dispatch sees
            # it (the object stays alive for the monkeypatch lifetime).
            monkeypatch.setattr(app, "_idle", _AlwaysDue())
            monkeypatch.setattr(app.editor, "execute_action", record)
            app.poll_idle()
            assert calls == ["toggle_screensaver"]

    asyncio.run(scenario())
