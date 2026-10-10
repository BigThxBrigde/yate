"""Idle screensaver scenarios: the alt+shift+s toggle and its refusals.

The screensaver is the last action the smoke suite never exercised
(``toggle_screensaver`` was the single missing entry of the 66-action
universe), so this module drives it through both of its entry points:

* :func:`_screensaver_toggle_key` -- ``alt+shift+s`` is intercepted by name in
  :meth:`yate.editor.Editor.handle_key` (``yate/editor.py``: the chord has no
  raw byte form) and calls the registered ``toggle_screensaver`` action, so the
  real key covers the action *and* the keymap-free interception.  Two
  open/close rounds prove the toggle is idempotent.
* :func:`_screensaver_disabled_message` -- ``screen_saver.enable = False`` refuses
  to start and only reports on the message line
  (:meth:`yate.flows.overlay_flows.OverlayFlows.toggle_screensaver`).
* :func:`_screensaver_bad_roster_message` -- a ``characters`` whitelist naming
  only unknown sprites is refused too, and is *not* silently widened to the
  whole roster: falling back would betray an explicit whitelist.

The two refusals are two scenarios rather than one scenario driving two apps:
``snapshot_svg`` writes the same ``shot.svg`` for every app, so a second app
would overwrite the first app's rows with dead storage, and the harness'
invariant scan runs against the most recently created app only -- which would
leave the first app's screen stack unscanned.  One app per scenario gives each
app its own invariant coverage and its own snapshot.

Every scenario leaves the screen stack at one entry, which is what the
harness' ``invariant:no_leftover_modal`` demands; the configurations are built
per app instance, so no process-global state is mutated.
"""

from __future__ import annotations

from pathlib import Path

from tools.smoke_test.harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import message_text, run_command, wait_until
from yate.app import YateApp
from yate.config import ScreenSaverConfig, YateConfig
from yate.editor_view.screensaver import ScreensaverScreen

__all__ = ["SCENARIOS"]

#: Message ``toggle_screensaver`` writes when ``screen_saver.enable`` is off.
_DISABLED_MSG: str = "screensaver disabled (screen_saver.enable = False)"

#: Message written when the ``characters`` whitelist matches no roster entry.
_BAD_ROSTER_MSG: str = "screensaver: no valid screen_saver.characters entry"

#: The prompt line an overlay push resets to (``PromptBar.idle`` default).
_IDLE_MSG: str = " Ready. Press F1 for help."

#: Class name of the screensaver overlay, compared through
#: ``type(app.screen).__name__`` so the check reports a readable diff.
_SCREEN_NAME: str = "ScreensaverScreen"


def _screen_name(app: YateApp) -> str:
    """Class name of the screen currently on top of the stack."""
    return type(app.screen).__name__


def _walker_count(app: YateApp) -> int:
    """How many sprites the top screensaver screen is animating (0 if none).

    ``ScreensaverScreen.walkers`` only exists on the screensaver, so the
    isinstance test is what keeps the attribute access typed.
    """
    screen = app.screen
    if isinstance(screen, ScreensaverScreen):
        return len(screen.walkers)
    return 0


async def _screensaver_toggle_key(tmp: Path) -> ScenarioResult:
    """alt+shift+s opens and dismisses the screensaver, twice over.

    The chord is intercepted by key name in ``Editor.handle_key`` -- an
    ``alt+shift`` combo has no raw byte form -- and routed through the
    registered ``toggle_screensaver`` action, so this single scenario also
    closes the action-coverage gap.  Pushing goes through
    ``OverlayFlows.push``, which idles the prompt line first (the stale
    command feedback is cleared while the overlay covers it); any key
    dismisses the screen (``ScreensaverScreen.on_key`` stops the event, so
    nothing leaks into the buffer), and the second round is closed by the
    action's own pop branch instead of a key.
    """
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Leave a command message behind so the push's prompt reset is
        # observable: the overlay hides the line, and a stale note would
        # reappear on close.
        await run_command(pilot, "set bogus=1")
        checks.append(Check("stale_message_present", True,
                            "unknown option" in message_text(app)))
        checks.append(Check("prompt_idle_before", None,
                            app.editor.prompt_bar.active_mode))

        await pilot.press("alt+shift+s")
        await pilot.pause()
        checks.append(Check("opened", 2, len(app.screen_stack)))
        checks.append(Check("screen_is_screensaver", _SCREEN_NAME,
                            _screen_name(app)))
        landed = await wait_until(pilot, lambda: _walker_count(app) > 0)
        checks.append(Check("walker_spawned", True, landed))
        checks.append(Check("prompt_idled_by_push", None,
                            app.editor.prompt_bar.active_mode))
        checks.append(Check("stale_message_cleared", True,
                            _IDLE_MSG in message_text(app)))

        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("dismissed_by_key", 1, len(app.screen_stack)))
        checks.append(Check("back_to_editor", False,
                            _screen_name(app) == _SCREEN_NAME))

        # Second round: the same key opens it again (idempotent toggle) and
        # the action's own pop branch closes it this time.
        await pilot.press("alt+shift+s")
        await pilot.pause()
        checks.append(Check("reopened", 2, len(app.screen_stack)))
        checks.append(Check("reopen_screen", _SCREEN_NAME, _screen_name(app)))
        checks.append(Check("reopen_walker", True,
                            await wait_until(pilot,
                                             lambda: _walker_count(app) > 0)))
        ran = app.editor.execute_action("toggle_screensaver")
        await pilot.pause()
        checks.append(Check("action_ran", True, ran))
        checks.append(Check("closed_by_action", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("screensaver_toggle_key", checks, rows)


async def _screensaver_disabled_message(tmp: Path) -> ScenarioResult:
    """A screensaver disabled in config reports and opens nothing.

    ``screen_saver.enable = False`` also leaves the shell without an idle
    tracker, so the refusal is not merely a message -- there is no timer to
    fall back on either.
    """
    app = new_app(
        target=tmp / "a.txt",
        config=YateConfig(screen_saver=ScreenSaverConfig(enable=False)),
    )
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("no_idle_tracker", None, app.idle_tracker))
        await pilot.press("alt+shift+s")
        await pilot.pause()
        checks.append(Check("stays_closed", 1, len(app.screen_stack)))
        checks.append(Check("disabled_message", True,
                            _DISABLED_MSG in message_text(app)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("screensaver_disabled_message", checks, rows)


async def _screensaver_bad_roster_message(tmp: Path) -> ScenarioResult:
    """A ``characters`` whitelist matching no roster entry is refused.

    The whitelist is *not* silently widened to the whole roster -- falling
    back would betray an explicit whitelist -- and every unknown name was
    already reported into ``config.errors`` at startup, which the first
    check pins.
    """
    app = new_app(
        target=tmp / "b.txt",
        config=YateConfig(
            screen_saver=ScreenSaverConfig(characters=("no-such-sprite",))
        ),
    )
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        checks.append(Check("unknown_name_reported", True, any(
            "unknown screensaver character" in err
            for err in app.config.errors
        )))
        await pilot.press("alt+shift+s")
        await pilot.pause()
        checks.append(Check("bad_roster_stays_closed", 1,
                            len(app.screen_stack)))
        checks.append(Check("bad_roster_message", True,
                            _BAD_ROSTER_MSG in message_text(app)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("screensaver_bad_roster_message", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("screensaver_toggle_key", _screensaver_toggle_key, ("view",)),
    Scenario("screensaver_disabled_message", _screensaver_disabled_message,
             ("view", "regression")),
    Scenario("screensaver_bad_roster_message", _screensaver_bad_roster_message,
             ("view", "regression")),
]
