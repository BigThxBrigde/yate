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
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from yate.editor_view.whichkey import ChordEntry, WhichKeyPanel
from yate.flows import StateQuery
from yate.flows.whichkey_flows import WINDOW_CHORDS, WhichKeyFlows
from yate.keymaps.registry import KeymapSet
from yate.keymaps.vim import VimKeymap
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
) -> tuple[WhichKeyFlows, _PanelRecorder]:
    """Build the flow over a recording panel (message line kept inert)."""
    panel = _PanelRecorder()
    flows = WhichKeyFlows(
        keymaps=keymaps,
        window_pending=window_pending,
        panel=cast(WhichKeyPanel, panel),
        message=lambda _text, _kind: None,
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
    assert len(entries) == len(WINDOW_CHORDS) == 14
    keys = {e.key for e in entries}
    assert {"q", "s", "v", "ctrl+w"} <= keys


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
    # ("gg") and the single-key "G" stay out, and so does y{motion}.
    assert "gg" not in keys
    assert "G" not in keys
    assert "y{motion}" not in keys


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
