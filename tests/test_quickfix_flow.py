"""L3 behaviour of :class:`~yate.flows.quickfix_flows.QuickFixFlows`.

The flow sequences the shared L1 result set and the docked panel through
injected callbacks: provider slice replacement opens the panel, close
keeps the entries for a later reopen, empty sets silently clear a stale
panel, and every jump pushes exactly one jump-list entry.
"""

from __future__ import annotations

from pathlib import Path
from typing import override

from yate.config import YateConfig
from yate.editor_components.find_replace import RevealFn
from yate.editor_components.quickfix_panel import QuickFixPanel
from yate.editor_core import Document
from yate.editor_core.project_search import FileMatch, LineMatch
from yate.flows.quickfix_flows import QuickFixFlows
from yate.session import EditorSession, QuickFixEntry, QuickFixList


class _RecordingPanel(QuickFixPanel):
    """A panel stand-in that records repaints without mounting a UI."""

    def __init__(
        self,
        entries: QuickFixList,
        paints: list[int],
        picked: list[int],
        closed: list[None],
    ) -> None:
        super().__init__(entries, on_pick=picked.append, on_close=lambda: closed.append(None))
        self._test_entries = entries
        self.paints = paints

    @override
    def repaint(self) -> None:
        self.paints.append(len(self._test_entries.snapshot()))


class _Harness:
    """Wires a real session, a recording panel and recording callbacks."""

    def __init__(self, reveal: RevealFn | None = None) -> None:
        self.session = EditorSession(YateConfig())
        self.session.new_buffer()
        self.session.docs[self.session.index] = Document(
            None, self.session.make_buffer("one\ntwo\nthree\n")
        )
        self.entries = QuickFixList()
        self.paints: list[int] = []
        self.picked: list[int] = []
        self.closed: list[None] = []
        self.panel = _RecordingPanel(self.entries, self.paints, self.picked, self.closed)
        self.reveals: list[tuple[Path, int, int]] = []
        self.messages: list[str] = []
        self.refreshes: list[None] = []
        self.visible = False
        self.show_calls: list[None] = []
        self.hide_calls: list[None] = []
        self.flow = QuickFixFlows(
            self.session,
            self.panel,
            entries=self.entries,
            reveal=reveal if reveal is not None else self._reveal,
            show=self._show,
            hide=self._hide,
            message=lambda text, kind: self.messages.append(text),
            refresh=lambda: self.refreshes.append(None),
        )

    def _reveal(self, path: Path, row: int, col: int) -> bool:
        """Record the reveal and land the cursor like the editor verb."""
        self.reveals.append((path, row, col))
        self.session.doc.buffer.set_cursor((row, col))
        return True

    def _show(self) -> None:
        """Record one visible transition (re-shows while visible are inert)."""
        if not self.visible:
            self.visible = True
            self.show_calls.append(None)

    def _hide(self) -> None:
        """Record one hidden transition (re-hides are idempotent)."""
        self.visible = False
        self.hide_calls.append(None)


def _entry(provider: str, label: str, row: int) -> QuickFixEntry:
    """Build an entry with a per-label path and a distinct 0-based row."""
    return QuickFixEntry(
        provider=provider, path=Path(f"{label}.py"), row=row, col=0, label=label
    )


def test_set_results_replaces_provider_slice_and_opens_panel() -> None:
    """Two provider batches keep their order; the panel opens once."""
    h = _Harness()
    h.flow.set_results("diagnostics", [_entry("diagnostics", "d1", 0), _entry("diagnostics", "d2", 1)], "diags")
    h.flow.set_results("references", [_entry("references", "r1", 2)], "refs")
    assert [e.label for e in h.flow.active_entries] == ["d1", "d2", "r1"]
    assert h.flow.selected == 0
    # The panel opened once and stayed visible across the second batch.
    assert h.visible is True
    assert len(h.show_calls) == 1
    assert h.paints == [2, 3]


def test_set_search_results_flattens_hits_and_empty_batch_clears() -> None:
    """Search hits become one entry per row; an empty scan clears them."""
    h = _Harness()
    matches = [
        FileMatch(
            path=Path("search.py"),
            matches=[LineMatch(row=2, start=4, end=8), LineMatch(row=6, start=1, end=5)],
            hit_lines={2: "needle here\r\n", 6: "another needle\n"},
        )
    ]
    h.flow.set_search_results(matches)
    assert [(e.path.name, e.row, e.col, e.label) for e in h.flow.active_entries] == [
        ("search.py", 2, 4, "needle here"),
        ("search.py", 6, 1, "another needle"),
    ]
    assert h.visible is True
    h.flow.set_search_results([])
    assert h.flow.active_entries == ()
    assert h.visible is False
    assert h.messages == []


def test_next_and_prev_wrap_and_jump_records_one_push() -> None:
    """Each next/prev jumps to the wrapped entry with exactly one push."""
    h = _Harness()
    batch = [
        _entry("diagnostics", "d1", 0),
        _entry("diagnostics", "d2", 1),
        _entry("diagnostics", "d3", 2),
    ]
    h.flow.set_results("diagnostics", batch, "diags")
    h.hide_calls.clear()
    for _ in range(3):
        h.flow.next()
    assert [e.label for e in h.flow.active_entries] == ["d1", "d2", "d3"]
    # The panel re-shown via set_results stayed visible through the jumps.
    assert h.visible is True
    # next() three times: 1 -> 2 -> 0 (wrap); reveal matches each entry.
    assert [p.name for p, _r, _c in h.reveals] == ["d2.py", "d3.py", "d1.py"]
    assert [_r for _p, _r, _c in h.reveals] == [1, 2, 0]
    back, _forward = h.session.jumps.stacks()
    assert [(e.row, e.col) for e in back] == [(0, 0), (1, 0), (2, 0)]
    h.flow.prev()
    h.flow.prev()
    assert [_r for _p, _r, _c in h.reveals] == [1, 2, 0, 2, 1]
    assert len(h.session.jumps.stacks()[0]) == 5


def test_close_keeps_entries_and_reopen_restores_selection() -> None:
    """Closing hides the panel but keeps the set; reopen restores the cursor."""
    h = _Harness()
    h.flow.set_results(
        "diagnostics",
        [_entry("diagnostics", "d1", 0), _entry("diagnostics", "d2", 1)],
        "diags",
    )
    h.flow.next()  # selection -> 1
    h.flow.close()
    assert h.visible is False
    assert [e.label for e in h.flow.active_entries] == ["d1", "d2"]
    h.flow.open()
    assert h.visible is True
    assert h.flow.selected == 1


def test_empty_results_clear_and_hide_without_stale_message() -> None:
    """An empty batch clears the slice and hides the panel without noise."""
    h = _Harness()
    h.flow.set_results("diagnostics", [_entry("diagnostics", "d1", 0)], "diags")
    assert h.visible is True
    h.flow.set_results("diagnostics", [], "diags")
    assert h.visible is False
    assert h.flow.active_entries == ()
    assert h.messages == []


def test_jump_to_out_of_range_is_ignored() -> None:
    """An out-of-range index reveals nothing, pushes nothing and warns."""
    h = _Harness()
    h.flow.jump_to(99)
    assert h.reveals == []
    assert len(h.session.jumps.stacks()[0]) == 0
    assert h.messages and "index" in h.messages[-1]


def test_failed_reveal_leaves_jump_stacks_untouched() -> None:
    """An unopenable target reports the error without recording a jump."""
    def refuse(_path: Path, _row: int, _col: int) -> bool:
        raise OSError("missing target")

    h = _Harness(refuse)
    h.flow.set_results("diagnostics", [_entry("diagnostics", "d1", 0)], "diags")
    h.session.doc.buffer.set_cursor((2, 1))
    before = h.session.jumps.stacks()

    h.flow.next()

    assert h.session.jumps.stacks() == before
    assert any("cannot open" in message for message in h.messages)
    assert h.refreshes == []
    assert h.visible is True


def test_false_reveal_reports_error_and_pushes_nothing() -> None:
    """A ``False`` reveal result is treated as a failed jump (no push)."""
    def refuse(_path: Path, _row: int, _col: int) -> bool:
        return False

    h = _Harness(refuse)
    h.flow.set_results("diagnostics", [_entry("diagnostics", "d1", 0)], "diags")
    h.session.doc.buffer.set_cursor((2, 1))
    before = h.session.jumps.stacks()

    h.flow.next()

    # The reveal was attempted (refuse records nothing) and failed.
    assert h.reveals == []
    assert h.session.jumps.stacks() == before
    assert any("cannot open" in message for message in h.messages)
    assert h.refreshes == []


def test_empty_batch_from_one_provider_keeps_panel_visible() -> None:
    """An empty batch must not hide a panel other providers still populate."""
    h = _Harness()
    h.flow.set_results("diagnostics", [_entry("diagnostics", "d1", 0)], "diags")
    assert h.visible is True
    h.flow.set_results("references", [], "refs")
    assert h.visible is True
    assert [e.label for e in h.flow.active_entries] == ["d1"]
    h.flow.set_results("diagnostics", [], "diags")
    # The whole result set is now empty, so the panel hides.
    assert h.visible is False
    assert h.flow.active_entries == ()


def test_empty_list_next_and_prev_report_empty_state() -> None:
    """next/prev on an empty result set only emit the hint message."""
    h = _Harness()
    h.flow.next()
    h.flow.prev()
    assert h.messages == ["no quickfix entries", "no quickfix entries"]
    assert h.reveals == []
    assert h.session.jumps.stacks()[0] == []


def test_missing_hit_line_gets_no_preview_label() -> None:
    """A hit row whose line is absent from ``hit_lines`` gets an explicit
    ``(no preview)`` label instead of a silent empty one."""
    h = _Harness()
    matches = [
        FileMatch(
            path=Path("search.py"),
            matches=[LineMatch(row=1, start=0, end=4)],
            hit_lines={},
        )
    ]
    h.flow.set_search_results(matches)
    entries = h.flow.active_entries
    assert len(entries) == 1
    assert entries[0].label == "(no preview)"
