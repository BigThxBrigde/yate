"""Which-key flow: keymap state translated into panel pushes (L3).

The editor constructs this module with the active :class:`KeymapSet`, a
read-only probe of the vim ``ctrl+w`` chord state, the which-key panel and
the message line.  :meth:`WhichKeyFlows.refresh` recomputes the panel after
every dispatch: pinned full sheet, ``ctrl+w`` chord, pending-chord
candidates, otherwise hidden.  No rendering here (the panel owns that) and
no App handle (capability injection, issue IKJB0Q).
"""

from __future__ import annotations

from yate.editor_view.whichkey import ChordEntry, WhichKeyPanel
from yate.flows import MessageFn, StateQuery
from yate.keymaps.conflicts import find_key_conflicts, format_conflicts
from yate.keymaps.keys import key_name
from yate.keymaps.registry import KeymapSet
from yate.logs import tracing

log = tracing.get_logger(__name__)


#: Second-key rows of the vim ``ctrl+w`` chord (fourteen keys).  Every
#: description is the keyword of the hint window_flows posts when the chord
#: arms (``s/:split v/:vsplit q close o :only ... h j k l move, ctrl+w cycle
#: + - < > = resize``), so panel and message read the same words.
WINDOW_CHORDS: tuple[ChordEntry, ...] = (
    ChordEntry("h", "move"),
    ChordEntry("j", "move"),
    ChordEntry("k", "move"),
    ChordEntry("l", "move"),
    ChordEntry("s", ":split"),
    ChordEntry("v", ":vsplit"),
    ChordEntry("q", "close"),
    ChordEntry("o", ":only"),
    ChordEntry("ctrl+w", "cycle"),
    ChordEntry("+", "resize"),
    ChordEntry("-", "resize"),
    ChordEntry("<", "resize"),
    ChordEntry(">", "resize"),
    ChordEntry("=", "resize"),
)


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
        panel: WhichKeyPanel,
        message: MessageFn,
    ) -> None:
        self.keymaps = keymaps
        # Read-only probe: the ctrl+w chord state lives in window_flows.
        self._window_pending = window_pending
        self._panel = panel
        # Editor-owned message line, injected for user-facing notices.
        self._message = message
        self._pinned = False

    def refresh(self) -> None:
        """Recompute panel visibility after one dispatch (called per key).

        The four branches are mutually exclusive, first hit wins: the
        pinned full sheet, the pending ``ctrl+w`` window chord, the
        pending-chord candidates; with none of them the panel hides.
        """
        if self._pinned:
            self._panel.show_entries(self.keymaps.name, self._sheet_entries())
            return
        if self._window_pending():
            self._panel.show_entries("ctrl+w", WINDOW_CHORDS)
            return
        if pending := self.keymaps.active.pending_prefix():
            self._panel.show_entries(pending, self._candidates(pending))
            return
        self._panel.clear()

    def toggle(self) -> None:
        """Pin / unpin the full keymap sheet (the <f9> / action entry)."""
        self._pinned = not self._pinned
        self.refresh()

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
