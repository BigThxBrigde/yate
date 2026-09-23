"""Regression guards for past bugs (tag: ``regression``).

These scenarios exist because the behaviour they assert used to be wrong.
Most of them read a private attribute or two -- that is deliberate: the
guard has to pin the *mechanism* (token cache version, pane binding,
overlay theme bridge), not just the visible outcome.
"""

# regression guards deliberately reach into the view's token cache:
# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import message_text, run_command, type_text, wait_until
from yate.editor_view import theme

__all__ = ["SCENARIOS"]

#: Pause long enough for the auto-completion debounce (0.12s) to fire and its
#: worker to land, so a late ``popup.show()`` cannot race an assertion.
_SETTLE_S = 0.3


async def _regress_wq_multi_tab(tmp: Path) -> ScenarioResult:
    """:wq guards the whole session, not just the current tab.

    wq_safety: :w saves only the current document, so :wq must refuse to
    quit while *another* tab still has unsaved changes.
    """
    (tmp / "a.txt").write_text("seed a", encoding="utf-8")
    (tmp / "b.txt").write_text("seed b", encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.editor.open_path(tmp / "b.txt")
        await wait_until(pilot, lambda: app.editor.session.doc.name == "b.txt")
        await pilot.press("ctrl+end")
        await type_text(pilot, " B")
        await run_command(pilot, "bp")
        checks.append(Check("on_a", "a.txt", app.editor.session.doc.name))
        await pilot.press("ctrl+end")
        await type_text(pilot, " A")
        await run_command(pilot, "w")
        checks.append(Check("a_saved", False, app.editor.session.doc.modified))
        checks.append(Check("a_on_disk", "seed a A",
                            (tmp / "a.txt").read_text(encoding="utf-8")))
        await run_command(pilot, "wq")
        checks.append(Check("still_running", None, app.return_code))
        checks.append(Check("no_tab_lost", 2, len(app.editor.session.docs)))
        checks.append(Check("warned", True, "unsaved changes" in message_text(app)))
        checks.append(Check("b_untouched", "seed b",
                            (tmp / "b.txt").read_text(encoding="utf-8")))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_wq_multi_tab", checks, rows)


async def _regress_unicode_save(tmp: Path) -> ScenarioResult:
    """A save the encoding cannot represent reports and keeps the buffer."""
    target = tmp / "enc.txt"
    target.write_text("seed", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # A document opened as a legacy encoding cannot represent every
        # character; insert_char stands in for typing one (a real keystroke
        # would need a keyboard layout with that glyph).
        app.editor.session.doc.encoding = "ascii"
        app.editor.insert_char("é")
        await pilot.pause()
        checks.append(Check("dirty", True, app.editor.session.doc.modified))
        await run_command(pilot, "w")
        checks.append(Check("still_running", None, app.return_code))
        checks.append(Check("reported", True, "save failed" in message_text(app)))
        checks.append(Check("buffer_kept", True,
                            "é" in app.editor.session.buffer.get_text()))
        checks.append(Check("disk_untouched", "seed",
                            target.read_text(encoding="utf-8")))
        checks.append(Check("still_dirty", True, app.editor.session.doc.modified))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_unicode_save", checks, rows)


async def _regress_typing_flicker(tmp: Path) -> ScenarioResult:
    """Typing never leaves the view uncolored / with stale tokens."""
    app = new_app(target=tmp / "code.py")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        view = app.editor.panes.active_view if app.editor.panes else None
        assert view is not None
        versions: list[int] = []
        for ch in "value = 1 + 2":
            await pilot.press(ch)
            versions.append(app.editor.session.buffer.content_version)
        checks.append(Check("version_monotonic", True,
                            all(a <= b for a, b in zip(versions, versions[1:]))))
        await wait_until(pilot, lambda: view._hl_tokens is not None)
        checks.append(Check("tokens_present", True, bool(view._hl_tokens)))
        checks.append(Check("tokens_cover_buffer", True,
                            len(view._hl_tokens or []) >= app.editor.session.buffer.line_count))
        checks.append(Check("text", "value = 1 + 2", app.editor.session.buffer.lines[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_typing_flicker", checks, rows)


async def _regress_split_panes(tmp: Path) -> ScenarioResult:
    """After :only the single pane and the active document stay in sync."""
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp / "b.txt").write_text("b\n", encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        panes = app.editor.panes
        assert panes is not None
        await run_command(pilot, "vs b.txt")
        await wait_until(pilot, lambda: panes.leaf_count == 2)
        await run_command(pilot, "split")
        await wait_until(pilot, lambda: panes.leaf_count == 3)
        await run_command(pilot, "only")
        await wait_until(pilot, lambda: panes.leaf_count == 1)
        checks.append(Check("one_pane", 1, panes.leaf_count))
        checks.append(Check("active_matches_doc", True,
                            panes.active.doc is app.editor.session.doc))
        checks.append(Check("active_view_is_live", True,
                            panes.active_view is not None))
        checks.append(Check("doc_index_valid", True,
                            0 <= app.editor.session.index
                            < len(app.editor.session.docs)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_split_panes", checks, rows)


async def _regress_tab_click(tmp: Path) -> ScenarioResult:
    """Clicking a tab activates that document (hit-test regions)."""
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp / "b.txt").write_text("b\n", encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        app.editor.open_path(tmp / "b.txt")
        await wait_until(pilot, lambda: app.editor.session.doc.name == "b.txt")
        tabbar = app.editor.tabbar
        assert tabbar is not None
        _, regions = app.editor.tabbar.build(tabbar.size.width or 80)
        checks.append(Check("two_regions", True, len(regions) >= 2))
        start, _end, doc_index = regions[0]
        await pilot.click("#tabbar", offset=(start + 1, 0))
        await pilot.pause()
        checks.append(Check("clicked_index", doc_index, app.editor.session.index))
        checks.append(Check("clicked_doc", "a.txt", app.editor.session.doc.name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_tab_click", checks, rows)


async def _regress_overlay_theme(tmp: Path) -> ScenarioResult:
    """Overlays stay on the bridged yate theme (no off-palette modal)."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "theme latte")
        checks.append(Check("app_theme", theme.textual_theme_name("latte"),
                            str(app.theme)))
        await pilot.press("f1")
        await pilot.pause()
        checks.append(Check("overlay_open", 2, len(app.screen_stack)))
        checks.append(Check("theme_kept_under_modal",
                            theme.textual_theme_name("latte"), str(app.theme)))
        await pilot.press("q")
        await pilot.pause()
        checks.append(Check("overlay_closed", 1, len(app.screen_stack)))
        await run_command(pilot, "theme mocha")
        checks.append(Check("restored", theme.textual_theme_name("mocha"),
                            str(app.theme)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_overlay_theme", checks, rows)


async def _regress_completion_staleness(tmp: Path) -> ScenarioResult:
    """Typing while the completion popup is open must reach the buffer.

    The popup used to swallow *every* key while it was up; it now consumes
    only tab/enter/up/down/escape and lets the rest fall through, so the
    typed characters land in the buffer and the popup re-queries under the
    longer prefix.  The file is seeded with a candidate word ("printf") on a
    line *below* the cursor row: buffer completion reads the other rows, and
    the cursor row is excluded, so typing on row 0 cannot feed itself.  With
    an empty file the popup never opened and the old assertions were
    vacuously true -- exactly the false negative this guard now fixes.

    The target is ``.txt`` on purpose: ``.py`` would route through the
    bundled python language server (registered even when disabled via
    ``YATE_PYTHON_LSP=off``), which has no server to answer and keeps the
    popup shut, so the buffer-completion path would not be exercised.
    """
    target = tmp / "code.txt"
    target.write_text("\nprintf\n", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        popup: Any = app.editor.completion_popup
        await type_text(pilot, "pri")
        await pilot.press("ctrl+space")
        # The popup must really open: a candidate matching "pri" exists
        # ("printf"), so this check fails loudly if it ever stops opening.
        opened = await wait_until(pilot, lambda: popup.is_open)
        checks.append(Check("popup_was_open", True, opened))
        await type_text(pilot, "nt")
        # Core contract: the keys fell through instead of being swallowed,
        # so the buffer holds the whole typed word.
        checks.append(Check("no_phantom_insert", "print",
                            app.editor.session.buffer.lines[0]))
        # Measured state after the fix: typing does *not* close the popup --
        # it re-queries and stays up filtered by the longer prefix "print".
        # ``popup_closed`` therefore legitimately holds ``False`` here.
        await wait_until(pilot, lambda: popup.prefix == "print")
        checks.append(Check("popup_closed", False, not popup.is_open))
        checks.append(Check("popup_prefix", "print", popup.prefix))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("still_clean", "print",
                            app.editor.session.buffer.lines[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_completion_staleness", checks, rows)


async def _regress_completion_popup_keys(tmp: Path) -> ScenarioResult:
    """Only the popup-owned keys are consumed; every other key falls through.

    The popup used to swallow *every* keypress (``return True``), so typing
    could not refine the candidates and global chords such as Ctrl+Z were dead
    while it was up.  This guard pins the split: tab / up / down / escape stay
    owned by the popup, while printable characters and global chords reach the
    normal dispatch.  The target is ``.txt`` on purpose: a ``.py`` file routes
    through the bundled python language server (registered even with
    ``YATE_PYTHON_LSP=off``) and the popup would never open.

    Typing is followed by ``_SETTLE_S`` pauses: the auto-completion debounce
    (0.12s) fires after the keys, and its worker calls ``popup.show()`` when it
    lands, which would otherwise re-open a popup an assertion just closed.
    """
    target = tmp / "keys.txt"
    # candidates live on the row *below* the cursor row: buffer completion
    # excludes the row being typed on, so typing cannot feed itself
    target.write_text("\nprintf printk\n", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        popup: Any = app.editor.completion_popup
        buf = app.editor.session.buffer
        await type_text(pilot, "pri")
        await pilot.pause(_SETTLE_S)
        await pilot.press("ctrl+space")
        opened = await wait_until(pilot, lambda: popup.is_open)
        checks.append(Check("popup_open", True, opened))
        await pilot.pause(_SETTLE_S)

        # escape is owned by the popup: it dismisses without touching text.
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("escape_dismisses", True, not popup.is_open))
        checks.append(Check("escape_keeps_buffer", "pri", buf.lines[0]))

        # A printable key falls through: it lands in the buffer and the popup
        # keeps filtering under the longer prefix.
        await pilot.press("ctrl+space")
        reopened = await wait_until(pilot, lambda: popup.is_open)
        checks.append(Check("reopened", True, reopened))
        await pilot.pause(_SETTLE_S)
        await type_text(pilot, "n")
        checks.append(Check("typed_through", "prin", buf.lines[0]))
        refiltered = await wait_until(pilot, lambda: popup.prefix == "prin")
        checks.append(Check("popup_refilters", True, refiltered))
        await pilot.pause(_SETTLE_S)

        # A global chord falls through too: ctrl+z undoes the freshly typed
        # word (consecutive insertions merge into one undo step), which can
        # only happen if the chord reached the keymap instead of the popup.
        await pilot.press("ctrl+z")
        await pilot.pause()
        checks.append(Check("ctrl_z_undoes", "", buf.lines[0]))

        # With the popup open again, its own keys stay owned: down moves the
        # selection without touching the buffer ...
        await type_text(pilot, "pri")
        await pilot.pause(_SETTLE_S)
        await pilot.press("ctrl+space")
        await wait_until(pilot, lambda: popup.is_open)
        await pilot.pause(_SETTLE_S)
        await pilot.press("down")
        await pilot.pause()
        checks.append(Check("down_selects", 1, popup.index))
        checks.append(Check("down_keeps_buffer", "pri", buf.lines[0]))

        # ... and tab accepts the highlighted item, replacing the prefix.
        await pilot.press("tab")
        await pilot.pause()
        checks.append(Check("tab_accepts", True, not popup.is_open))
        checks.append(Check("tab_replaces", "printk", buf.lines[0]))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_completion_popup_keys", checks, rows)


async def _regress_diagnostics_cmd(tmp: Path) -> ScenarioResult:
    """:diagnostics with no server: message, no overlay, no crash."""
    app = new_app(target=tmp / "a.py")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "diagnostics")
        checks.append(Check("no_overlay", 1, len(app.screen_stack)))
        checks.append(Check("no_crash", None, app.return_code))
        checks.append(Check("buffer_intact", True,
                            app.editor.session.buffer.line_count >= 1))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_diagnostics_cmd", checks, rows)


async def _regress_theme_expansion(tmp: Path) -> ScenarioResult:
    """Every bundled theme can be activated in turn."""
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        names = list(theme.available())
        checks.append(Check("several_themes", True, len(names) >= 2))
        for name in names:
            await run_command(pilot, f"theme {name}")
            checks.append(Check(f"theme_{name}", name, theme.active().name))
        await run_command(pilot, "theme mocha")
        checks.append(Check("final_theme", "mocha", theme.active().name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("regress_theme_expansion", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("regress_wq_multi_tab", _regress_wq_multi_tab, ("regression",)),
    Scenario("regress_unicode_save", _regress_unicode_save, ("regression",)),
    Scenario("regress_typing_flicker", _regress_typing_flicker, ("regression",)),
    Scenario("regress_split_panes", _regress_split_panes, ("regression",)),
    Scenario("regress_tab_click", _regress_tab_click, ("regression",)),
    Scenario("regress_overlay_theme", _regress_overlay_theme, ("regression",)),
    Scenario("regress_completion_staleness", _regress_completion_staleness,
             ("regression",)),
    Scenario("regress_completion_popup_keys", _regress_completion_popup_keys,
             ("regression",)),
    Scenario("regress_diagnostics_cmd", _regress_diagnostics_cmd, ("regression",)),
    Scenario("regress_theme_expansion", _regress_theme_expansion,
             ("regression",)),
]
