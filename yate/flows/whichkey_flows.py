"""Which-key flow: keymap state translated into panel pushes (L3).

The editor constructs this module with the active :class:`KeymapSet`, a
read-only probe of the vim ``ctrl+w`` chord state, a source of canonical
``ctrl+w`` chord rows (single-sourced in :mod:`yate.flows.window_flows`),
the which-key panel, the message line and a master-switch predicate over
the yaterc ``which_key`` option.  :meth:`WhichKeyFlows.refresh` recomputes
the panel after every dispatch: pinned full sheet, ``ctrl+w`` chord,
pending-chord candidates, otherwise hidden.  The master-switch predicate is
read on every entry (so a mid-session ``:set which_key=off`` takes effect on
the next refresh) and short-circuits all four branches.  No rendering here
(the panel owns that) and no App handle (capability injection, issue
IKJB0Q).
"""

from __future__ import annotations

from collections.abc import Callable

from yate.editor_view.whichkey import ChordEntry, WhichKeyPanel
from yate.flows import MessageFn, StateQuery
from yate.keymaps.conflicts import find_key_conflicts, format_conflicts
from yate.keymaps.keys import key_name
from yate.keymaps.registry import KeymapSet
from yate.logs import tracing

log = tracing.get_logger(__name__)


#: Predicate over the yaterc ``which_key`` master switch; evaluated on
#: every :meth:`WhichKeyFlows.refresh` / :meth:`WhichKeyFlows.toggle` entry
#: so a mid-session ``:set which_key=off`` takes effect immediately.
#: Returning ``False`` hides the panel and turns F9 into a no-op (the
#: pinned state is preserved, re-enabling restores it).
type EnabledPredicate = Callable[[], bool]


#: Source of the canonical ctrl+w chord rows; backed by the single-source
#: table in :mod:`yate.flows.window_flows` (``WINDOW_CHORD_TABLE``).
type WindowChordHintsFn = Callable[[], tuple[tuple[str, str], ...]]


def _spec_label(spec: str) -> str:
    """Panel label for one binding spec: raw bytes humanized, else verbatim.

    A raw (non-printable-leading) spec is one chord step and reads through
    :func:`~yate.keymaps.keys.key_name` (``\\x04`` becomes ``<ctrl-d>``);
    a printable spec is a typed sequence shown exactly as written (``dd``),
    which is also the form the candidate matcher compares against.
    """
    first = spec[:1]
    return key_name(spec) if first and not first.isprintable() else spec


class WhichKeyFlows:
    """Drives the which-key panel from the active keymap's state."""

    def __init__(
        self,
        keymaps: KeymapSet,
        window_pending: StateQuery,
        window_chord_hints: WindowChordHintsFn,
        panel: WhichKeyPanel,
        message: MessageFn,
        which_key_enabled: EnabledPredicate,
    ) -> None:
        self.keymaps = keymaps
        # Read-only probe: the ctrl+w chord state lives in window_flows.
        self._window_pending = window_pending
        # Canonical ctrl+w chord rows (single source: window_flows' table);
        # the panel entry construction stays local to this module.
        self._window_chord_hints = window_chord_hints
        self._panel = panel
        # Editor-owned message line, injected for user-facing notices.
        self._message = message
        # Master switch predicate (lambda over ``editor.config.which_key``).
        self._enabled = which_key_enabled
        self._pinned = False

    def refresh(self) -> None:
        """Recompute panel visibility after one dispatch (called per key).

        Master-switch short-circuit: with ``which_key = False`` the panel is
        hidden unconditionally (no-op regardless of pending chord / ctrl+w /
        pin state).  The four branches are otherwise mutually exclusive,
        first hit wins: the pinned full sheet, the pending ``ctrl+w`` window
        chord, the pending-chord candidates; with none of them the panel
        hides.
        """
        if not self._enabled():
            self._panel.clear()
            return
        if self._pinned:
            self._panel.show_entries(self.keymaps.name, self._sheet_entries())
            return
        if self._window_pending():
            entries = [ChordEntry(k, d) for k, d in self._window_chord_hints()]
            self._panel.show_entries("ctrl+w", tuple(entries))
            return
        if pending := self.keymaps.active.pending_prefix():
            self._panel.show_entries(pending, self._candidates(pending))
            return
        self._panel.clear()

    def toggle(self) -> None:
        """Pin / unpin the full keymap sheet (the <f9> / action entry).

        Master-switch short-circuit: with ``which_key = False`` this is a
        no-op (the pinned state is preserved so re-enabling restores the
        sheet).
        """
        if not self._enabled():
            return
        self._pinned = not self._pinned
        self.refresh()

    def clear(self) -> None:
        """Hide the panel unconditionally (used by ``:set which_key=off``).

        Public entry point so ``commands._apply_which_key`` can hide the
        panel without reaching for ``panel`` (the flow module owns the panel
        reference).
        """
        self._panel.clear()

    def conflicts_report(self) -> str:
        """The :check-keys report body for the active keymap.

        Each keymap carries its own reserved-key set
        (:attr:`~yate.keymaps.base.Keymap.reserved_keys` -- the raw keys its
        hardcoded dispatch branches consume); table-driven keymaps hold an
        empty set and scan duplicates alone.
        """
        conflicts = find_key_conflicts(
            self.keymaps.active, reserved=self.keymaps.active.reserved_keys
        )
        return format_conflicts(self.keymaps.name, conflicts)

    # -------------------------------------------------------------- internals

    def _candidates(self, pending: str) -> list[ChordEntry]:
        """Next-key rows for the chord typed so far (*pending*).

        A pending chord is always printable (registers, counts, operators
        and motion prefixes are typed characters), so a raw-byte spec --
        function keys, control chords -- can never be its continuation and
        never qualifies here; those humanized labels belong to the pinned
        sheet.

        Two sources merge into one grid, table rows first:

        - a binding row qualifies iff *pending* is a literal prefix of the
          spec and the spec is strictly longer
          (``spec.startswith(pending) and len(spec) > len(pending)``) --
          placeholders ``{...}`` only appear after the first character, so
          the literal-prefix test is safe;
        - the active keymap's :meth:`~yate.keymaps.base.Keymap.chord_hints`
          rows describe what its hardcoded branches consume next (an armed
          operator's motions, a find prefix's ``{char}`` follower, ...);
          a table-driven keymap contributes none.

        Rows dedupe on the label (the first occurrence wins), so a table
        entry shadows a hint row with the same label.
        """
        entries: list[ChordEntry] = []
        seen: set[str] = set()
        for binding in self.keymaps.active.bindings:
            spec = binding.key
            if not (spec.startswith(pending) and len(spec) > len(pending)):
                continue
            if spec in seen:
                continue
            seen.add(spec)
            entries.append(
                ChordEntry(spec, binding.description or str(binding.action))
            )
        for label, desc in self.keymaps.active.chord_hints():
            if label not in seen:
                seen.add(label)
                entries.append(ChordEntry(label, desc))
        return entries

    def _sheet_entries(self) -> list[ChordEntry]:
        """The whole binding table grouped by category (pinned sheet).

        Descriptions fall back to ``str(binding.action)`` exactly like the
        HelpScreen, so a description-less binding still reads on the sheet.
        """
        return [
            ChordEntry(
                _spec_label(binding.key),
                binding.description or str(binding.action),
                binding.category,
            )
            for binding in self.keymaps.active.bindings
        ]
