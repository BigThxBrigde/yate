"""Headless tests for the which-key flow module (WhichKeyFlows).

Drives :class:`yate.flows.whichkey_flows.WhichKeyFlows` with real keymap
sets (the vim / vsc tables from the keymap layer) and recording stand-ins
for the panel and the injected callables.  Covered: the refresh decision
order (pin > ctrl+w chord > pending candidates > hidden), the candidate
matcher, the pinned sheet, the fourteen ctrl+w rows, the ``:check-keys``
report and the no-App-handle guarantee.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

import pytest

from yate.editor_components.whichkey import ChordEntry, WhichKeyPanel
from yate.flows import StateQuery
from yate.flows.whichkey_flows import WhichKeyFlows, WindowChordHintsFn
from yate.flows.window_flows import (
    WINDOW_CHORD_HINT,
    WINDOW_CHORD_TABLE,
    WINDOW_KEY_ALIASES,
    WINDOW_SECOND_KEYS,
)
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import RESERVED_KEYS, VimKeymap
from yate.keymaps.vsc import VscKeymap

from conftest import make_action_context


class _PanelRecorder:
    """Recording stand-in for WhichKeyPanel: every push, every clear."""

    def __init__(self) -> None:
        self.shown: list[tuple[str, tuple[ChordEntry, ...]]] = []
        self.clears = 0
        self.last: str = ""

    def show_entries(self, header: str, entries: Sequence[ChordEntry]) -> None:
        """Record one (header, entries) push."""
        self.shown.append((header, tuple(entries)))
        self.last = "show"

    def clear(self) -> None:
        """Record one hide."""
        self.clears += 1
        self.last = "clear"


def _make_flows(
    keymaps: KeymapSet,
    window_pending: StateQuery = lambda: False,
    window_chord_hints: WindowChordHintsFn = lambda: WINDOW_CHORD_TABLE,
    which_key_enabled: Callable[[], bool] = lambda: True,
    which_key_auto_enabled: Callable[[], bool] = lambda: True,
) -> tuple[WhichKeyFlows, _PanelRecorder]:
    """Build the flow over a recording panel (message line kept inert).

    The auto-trigger switch defaults to ``True``, reproducing the
    pre-auto-gate behavior for every existing call site.
    """
    panel = _PanelRecorder()
    flows = WhichKeyFlows(
        keymaps=keymaps,
        window_pending=window_pending,
        window_chord_hints=window_chord_hints,
        panel=cast(WhichKeyPanel, panel),
        message=lambda _text, _kind: None,
        which_key_enabled=which_key_enabled,
        which_key_auto_enabled=which_key_auto_enabled,
    )
    return flows, panel


def test_refresh_shows_candidates_while_vim_chord_pending() -> None:
    """An armed vim operator surfaces its next-key rows under header "d"."""
    vim = VimKeymap()
    flows, panel = _make_flows(KeymapSet({"vim": vim}, "vim"))
    ctx = make_action_context()
    assert vim.handle_key(ctx, "d") is True
    assert vim.pending_prefix() == "d"
    flows.refresh()
    assert panel.clears == 0
    header, entries = panel.shown[-1]
    assert header == "d"
    keys = {e.key for e in entries}
    assert "dd" in keys
    assert "d{motion}" in keys
    assert "w" in keys  # hardcoded motion hint from the keymap hook


def test_refresh_shows_text_object_grid_under_scope_header() -> None:
    """After ``di`` the header reads "di" and the grid lists the objects."""
    vim = VimKeymap()
    flows, panel = _make_flows(KeymapSet({"vim": vim}, "vim"))
    ctx = make_action_context()
    vim.handle_key(ctx, "d")
    vim.handle_key(ctx, "i")
    flows.refresh()
    header, entries = panel.shown[-1]
    assert header == "di"
    keys = {e.key for e in entries}
    assert "w" in keys
    assert "( b" in keys
    assert "{ B" in keys


def test_refresh_clears_panel_when_idle() -> None:
    """With nothing pending the panel is hidden, not shown empty."""
    flows, panel = _make_flows(KeymapSet({"vim": VimKeymap()}, "vim"))
    flows.refresh()
    assert panel.shown == []
    assert panel.clears == 1


def test_refresh_shows_window_chords_while_ctrlw_pending() -> None:
    """The ctrl+w chord state renders the fourteen second-key rows."""
    flows, panel = _make_flows(
        KeymapSet({"vim": VimKeymap()}, "vim"),
        window_pending=lambda: True,
    )
    flows.refresh()
    header, entries = panel.shown[-1]
    assert header == "ctrl+w"
    assert len(entries) == len(WINDOW_CHORD_TABLE) == 14
    keys = {e.key for e in entries}
    assert keys == {key for key, _ in WINDOW_CHORD_TABLE}


def test_candidates_exclude_completed_and_unrelated_specs() -> None:
    """Only specs strictly longer than the pending chord qualify.

    Driven through the public refresh() path (same pending "d" state as the
    matcher itself would see), so no private helper is touched.
    """
    vim = VimKeymap()
    flows, panel = _make_flows(KeymapSet({"vim": vim}, "vim"))
    ctx = make_action_context()
    assert vim.handle_key(ctx, "d") is True
    flows.refresh()
    keys = {e.key for e in panel.shown[-1][1]}
    assert "dd" in keys
    assert "d{motion}" in keys
    # Completed specs never share the pending prefix: the "doc start" spec
    # ("gg") and the single-key "G" spec stay out, and so does y{motion}.
    # A "G" row does appear -- as the keymap's hardcoded motion hint, not
    # the binding-table spec, so its description is pinned to the hint's.
    assert "gg" not in keys
    assert "y{motion}" not in keys
    assert [e.desc for e in panel.shown[-1][1] if e.key == "G"] == ["last line"]


def test_refresh_prefers_pinned_sheet_over_pending() -> None:
    """The pin branch outranks a live chord (decision order, first hit wins)."""
    vim = VimKeymap()
    flows, panel = _make_flows(KeymapSet({"vim": vim}, "vim"))
    ctx = make_action_context()
    assert vim.handle_key(ctx, "d") is True
    assert vim.pending_prefix() == "d"  # the chord still pends underneath
    flows.toggle()
    flows.refresh()
    header, entries = panel.shown[-1]
    assert header == "vim"  # sheet header, not the "d" candidate mode
    assert len(entries) == len(vim.bindings)
    categories = {e.category for e in entries}
    assert "Vim: motion" in categories  # grouped by binding category
    assert panel.clears == 0
    assert panel.last == "show"


def test_toggle_flips_pin_and_clears_on_unpin() -> None:
    """First toggle pins the full sheet, the second hides the panel."""
    flows, panel = _make_flows(KeymapSet({"vim": VimKeymap()}, "vim"))
    flows.toggle()
    flows.refresh()
    assert panel.last == "show"
    assert panel.shown[-1][1]  # a non-empty full sheet
    assert panel.clears == 0
    flows.toggle()
    flows.refresh()
    # both refreshes after the unpin hide the panel (toggle refreshes itself,
    # then the explicit call in this test refreshes again)
    assert panel.last == "clear"
    assert panel.clears == 2


def test_vsc_never_autoshows_without_pin() -> None:
    """The modeless vsc keymap has no prefix state: every refresh hides."""
    vsc = VscKeymap()
    flows, panel = _make_flows(KeymapSet({"vsc": vsc}, "vsc"))
    ctx = make_action_context()
    for key in ("d", '"', "2"):
        assert vsc.handle_key(ctx, key) is True
        flows.refresh()
        assert panel.shown == []
        assert panel.last == "clear"
    assert panel.clears == 3


def test_conflicts_report_uses_reserved_keys_only_for_vim() -> None:
    """Reserved-key scanning applies to vim alone; vsc reports duplicates."""
    vsc = VscKeymap()
    vim = VimKeymap()
    # raw "1" is a reserved key for vim (count handling) and free in vsc
    vsc.add_binding("1", "type_one", "Type the digit 1")
    vim.add_binding("1", "type_one", "Type the digit 1")
    vsc_flows, _ = _make_flows(KeymapSet({"vsc": vsc}, "vsc"))
    vim_flows, _ = _make_flows(KeymapSet({"vim": vim}, "vim"))
    assert vsc_flows.conflicts_report() == "keymap: vsc -- no conflicts"
    vim_report = vim_flows.conflicts_report()
    assert "keymap: vim --" in vim_report
    assert "reserved" in vim_report


def test_flow_holds_no_app_handle() -> None:
    """No ``self.app`` chain appears in the module (flow-module guard, local).

    Same AST probe as the architecture guard for flow modules: only
    ``editor.py`` may hold the App handle, everything else receives
    injected callables.
    """
    path = (
        Path(__file__).resolve().parents[1]
        / "yate"
        / "flows"
        / "whichkey_flows.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "app"
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ]
    assert offenders == []


def test_window_chord_hint_covers_whichkey_rows() -> None:
    """Every WINDOW_CHORD_TABLE description keyword appears in the arm hint.

    Single-source check: the hint is derived from the same table that feeds
    the which-key panel rows, so every description word must surface in the
    message line posted by ``WindowFlows.try_window_prefix``.
    """
    descs = {desc for _, desc in WINDOW_CHORD_TABLE}
    assert all(desc in WINDOW_CHORD_HINT for desc in descs)


def test_window_dispatch_keys_match_panel_rows() -> None:
    """Non-alias dispatch keys == panel rows (one-to-one); aliases stay off-panel."""
    canonical = {key for key, _ in WINDOW_CHORD_TABLE}
    aliases = frozenset(WINDOW_KEY_ALIASES)
    # Table keys are unique, so every non-alias dispatch key maps to
    # exactly one panel row.
    assert len(WINDOW_CHORD_TABLE) == len(canonical)
    # Every canonical key appears in dispatch set.
    assert canonical <= WINDOW_SECOND_KEYS
    # Aliases appear in dispatch set.
    assert aliases <= WINDOW_SECOND_KEYS
    # No alias leaks into the panel rows.
    panel_keys = {key for key, _ in WINDOW_CHORD_TABLE}
    assert panel_keys & aliases == frozenset()
    # Dispatch set is exactly canonical + aliases (no stray keys).
    assert WINDOW_SECOND_KEYS == canonical | aliases


def test_reserved_keys_come_from_the_active_keymap() -> None:
    """The conflict report reads the active keymap's own reserved hook.

    The flow module no longer compares keymap names: a VimKeymap carries
    its RESERVED_KEYS through the base-class ``reserved_keys`` attribute,
    and a table-driven keymap contributes an empty set.
    """
    vim_flows, _ = _make_flows(KeymapSet({"vim": VimKeymap()}, "vim"))
    vsc_flows, _ = _make_flows(KeymapSet({"vsc": VscKeymap()}, "vsc"))
    assert vim_flows.keymaps.active.reserved_keys == RESERVED_KEYS
    assert vsc_flows.keymaps.active.reserved_keys == frozenset()


def test_refresh_hides_panel_when_which_key_disabled() -> None:
    """Master switch off -> every refresh hides the panel.

    The master-switch short-circuit runs before the four decision branches,
    so idle, a pending chord, an armed ctrl+w chord and a (short-circuited)
    toggle all leave the panel hidden.
    """
    vim = VimKeymap()
    flows, panel = _make_flows(
        KeymapSet({"vim": vim}, "vim"),
        window_pending=lambda: True,
        which_key_enabled=lambda: False,
    )
    # Idle: nothing pending, still hidden.
    flows.refresh()
    assert panel.last == "clear"
    # Pending chord: an armed operator still hides.
    ctx = make_action_context()
    assert vim.handle_key(ctx, "d") is True
    flows.refresh()
    assert panel.last == "clear"
    # Toggle would pin when enabled; the short-circuit keeps the panel off.
    flows.toggle()
    flows.refresh()
    assert panel.last == "clear"
    assert panel.shown == []


def test_toggle_noop_when_which_key_disabled() -> None:
    """Master switch off -> toggle never pins, so nothing survives.

    ``toggle`` short-circuits before touching the pinned state, leaving it
    unpinned; re-enabling afterwards therefore refreshes to the hidden
    branch instead of a pinned sheet.
    """
    state = {"on": False}
    vim = VimKeymap()
    flows, panel = _make_flows(
        KeymapSet({"vim": vim}, "vim"),
        which_key_enabled=lambda: state["on"],
    )
    flows.toggle()   # short-circuited: no pin
    flows.refresh()  # disabled: hidden
    assert panel.last == "clear"
    # Re-enable: no prior pin survived, so the hidden branch still wins.
    state["on"] = True
    flows.refresh()
    assert panel.last == "clear"
    assert panel.shown == []


def test_clear_method_hides_panel_unconditionally() -> None:
    """``WhichKeyFlows.clear`` delegates to the panel for :set which_key=off."""
    vim = VimKeymap()
    flows, panel = _make_flows(KeymapSet({"vim": vim}, "vim"))
    flows.toggle()
    flows.refresh()
    assert panel.last == "show"
    flows.clear()
    assert panel.last == "clear"
    assert panel.clears >= 1


def test_pinned_sheet_survives_disable_and_reenable() -> None:
    """Pin while enabled, disable, then re-enable: the sheet comes back.

    The config docstring and the toggle docstring both promise that the
    pinned state is preserved across a ``which_key = False`` interval;
    this pins the promise (pin -> disable -> re-enable -> pinned sheet
    again under the keymap-name header).
    """
    state = {"on": True}
    vim = VimKeymap()
    flows, panel = _make_flows(
        KeymapSet({"vim": vim}, "vim"),
        which_key_enabled=lambda: state["on"],
    )
    flows.toggle()
    flows.refresh()
    assert panel.last == "show"
    # Disabled: the master switch hides the sheet but forgets nothing.
    state["on"] = False
    flows.refresh()
    assert panel.last == "clear"
    # Re-enabled: the pin from before the disable window is restored.
    state["on"] = True
    flows.refresh()
    assert panel.last == "show"
    header, entries = panel.shown[-1]
    assert header == "vim"
    assert len(entries) == len(vim.bindings)


def test_sheet_and_chord_labels_never_leak_control_bytes() -> None:
    """Every panel label is printable -- no raw C0 byte reaches the UI.

    ``_spec_label`` humanizes raw-byte specs through ``key_name``; a gap in
    its C0 coverage (FS/GS/RS before the fix) put the literal 0x1d byte on
    the vsc pinned sheet -- the defect the README gallery frame exposed.
    Guards both label sources: the pinned sheet of each keymap and the
    ctrl+w chord table.
    """
    for keymap, name in ((VimKeymap(), "vim"), (VscKeymap(), "vsc")):
        flows, panel = _make_flows(KeymapSet({name: keymap}, name))
        flows.toggle()
        assert panel.last == "show"
        header, entries = panel.shown[-1]
        assert header == name
        for entry in entries:
            assert entry.key.isprintable(), (name, entry.key)
    for label, _desc in WINDOW_CHORD_TABLE:
        assert label.isprintable(), label


# --- which_key_auto gate (behavior matrix plan-d) ----------------------------


@pytest.mark.parametrize(
    "master,auto", [(True, True), (True, False), (False, True), (False, False)]
)
def test_behavior_matrix_of_master_and_auto_switches(master: bool, auto: bool) -> None:
    """The four-row issue matrix: master off hides all, auto off hides
    only the auto branches, toggle works in every master-on row."""
    vim = VimKeymap()
    ctx = make_action_context()
    assert vim.handle_key(ctx, "d") is True
    flows, panel = _make_flows(
        KeymapSet({"vim": vim}, "vim"),
        which_key_enabled=lambda: master,
        which_key_auto_enabled=lambda: auto,
    )
    flows.refresh()
    shown_before = list(panel.shown)
    clears_before = panel.clears
    flows.toggle()
    if (master, auto) == (True, True):
        assert shown_before[-1][0] == "d"
        assert len(shown_before[-1][1]) > 0
        assert panel.shown[-1][0] == "vim"
    elif (master, auto) == (True, False):
        assert shown_before == []
        assert clears_before == 1
        assert panel.shown[-1][0] == "vim"
        assert len(panel.shown[-1][1]) > 0
    else:
        assert shown_before == []
        assert panel.shown == []
        assert panel.clears == clears_before


def test_refresh_auto_disabled_hides_pending_candidates() -> None:
    """With auto off an armed chord still pends but never auto-pops."""
    vim = VimKeymap()
    flows, panel = _make_flows(
        KeymapSet({"vim": vim}, "vim"),
        which_key_auto_enabled=lambda: False,
    )
    ctx = make_action_context()
    assert vim.handle_key(ctx, "d") is True
    flows.refresh()
    assert vim.pending_prefix() == "d"
    assert panel.shown == []
    assert panel.clears == 1


def test_refresh_auto_disabled_hides_ctrl_w_chord() -> None:
    """The ctrl+w chord branch (not via refresh_ui) is gated too."""
    flows, panel = _make_flows(
        KeymapSet({"vim": VimKeymap()}, "vim"),
        window_pending=lambda: True,
        which_key_auto_enabled=lambda: False,
    )
    flows.refresh()
    assert panel.shown == []
    assert panel.clears == 1


def test_toggle_works_when_auto_disabled() -> None:
    """The core requirement: the F9 manual toggle stays usable."""
    flows, panel = _make_flows(
        KeymapSet({"vim": VimKeymap()}, "vim"),
        which_key_auto_enabled=lambda: False,
    )
    flows.toggle()
    assert panel.shown[-1][0] == "vim"
    assert len(panel.shown[-1][1]) > 0
    flows.toggle()
    assert panel.last == "clear"
    shown_count = len(panel.shown)
    flows.refresh()
    assert len(panel.shown) == shown_count


def test_refresh_auto_disabled_preserves_pinned_sheet() -> None:
    """While pinned the sheet outranks the auto gate and prefix state."""
    vim = VimKeymap()
    flows, panel = _make_flows(
        KeymapSet({"vim": vim}, "vim"),
        window_pending=lambda: True,
        which_key_auto_enabled=lambda: False,
    )
    flows.toggle()
    assert panel.shown[-1][0] == "vim"
    clears_after_pin = panel.clears
    ctx = make_action_context()
    assert vim.handle_key(ctx, "d") is True
    flows.refresh()
    assert panel.shown[-1][0] == "vim"
    assert all(header not in ("d", "ctrl+w") for header, _ in panel.shown)
    assert panel.clears == clears_after_pin


def test_auto_reenabled_restores_candidates() -> None:
    """Flipping the auto switch back on at runtime restores the popups."""
    auto = [False]
    vim = VimKeymap()
    flows, panel = _make_flows(
        KeymapSet({"vim": vim}, "vim"),
        which_key_auto_enabled=lambda: auto[0],
    )
    ctx = make_action_context()
    assert vim.handle_key(ctx, "d") is True
    flows.refresh()
    assert panel.shown == []
    auto[0] = True
    flows.refresh()
    assert panel.shown[-1][0] == "d"
    assert "dd" in {e.key for e in panel.shown[-1][1]}


def test_master_switch_off_wins_over_auto_disabled() -> None:
    """With both switches off the master semantics are unchanged."""
    flows, panel = _make_flows(
        KeymapSet({"vim": VimKeymap()}, "vim"),
        window_pending=lambda: True,
        which_key_enabled=lambda: False,
        which_key_auto_enabled=lambda: False,
    )
    flows.refresh()
    assert panel.shown == []
    assert panel.clears == 1
    flows.toggle()
    assert panel.shown == []
    assert panel.clears == 1
    assert panel.last == "clear"


def test_vsc_never_auto_pops_with_auto_disabled() -> None:
    """The modeless vsc keymap is unaffected by the auto gate."""
    flows, panel = _make_flows(
        KeymapSet({"vsc": VscKeymap()}, "vsc"),
        which_key_auto_enabled=lambda: False,
    )
    flows.refresh()
    assert panel.shown == []
    flows.toggle()
    assert panel.shown[-1][0] == "vsc"
    flows.toggle()
    assert panel.last == "clear"


def test_hide_after_manual_unpin_does_not_auto_pop() -> None:
    """After unpinning, typed prefixes never re-trigger the auto popup."""
    vim = VimKeymap()
    flows, panel = _make_flows(
        KeymapSet({"vim": vim}, "vim"),
        which_key_auto_enabled=lambda: False,
    )
    flows.toggle()
    flows.toggle()
    ctx = make_action_context()
    assert vim.handle_key(ctx, "g") is True
    # shown is an append-only history in the recorder (clear() never empties
    # it), so the pinned sheet from the first toggle stays listed; the
    # contract is "no NEW show and one clear", not an empty history.
    shown_count = len(panel.shown)
    clears_before = panel.clears
    flows.refresh()
    assert len(panel.shown) == shown_count
    assert panel.clears > clears_before
    assert panel.last == "clear"
    assert vim.pending_prefix() == "g"
