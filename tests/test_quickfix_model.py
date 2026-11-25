"""Pure-data behaviour of the L1 quickfix model in ``yate.session``.

``replace`` drops only the same provider's prior batch and keeps the
selection when still valid, ``clear`` and ``step`` are empty-safe, and
entries are frozen pure data unaffected by later mutation of the source
list.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from yate.session import QuickFixEntry, QuickFixList


def _entry(provider: str, label: str) -> QuickFixEntry:
    """Build a minimal :class:`QuickFixEntry` with a per-label path."""
    return QuickFixEntry(
        provider=provider, path=Path(f"{label}.py"), row=0, col=0, label=label
    )


D1, D2, D3 = _entry("diagnostics", "d1"), _entry("diagnostics", "d2"), _entry(
    "diagnostics", "d3"
)
S1 = _entry("search", "s1")
R1, R2 = _entry("references", "r1"), _entry("references", "r2")


def test_replace_drops_only_the_same_provider_and_wraps_selection() -> None:
    """A provider refresh swaps only its own batch; step wraps at the top."""
    qf = QuickFixList()
    qf.replace("diagnostics", [D1, D2], "diagnostics")
    qf.replace("search", [S1], "search")
    qf.replace("references", [R1, R2], "references")
    assert qf.snapshot() == (D1, D2, S1, R1, R2)
    assert qf.selected == 0
    qf.replace("diagnostics", [D3], "diagnostics")
    assert qf.snapshot() == (D3, S1, R1, R2)
    assert D1 not in qf.snapshot() and D2 not in qf.snapshot()
    # stepping up from index 0 wraps to the last entry
    assert qf.step(-1) is R2
    assert qf.selected == 3


def test_clear_and_empty_step_are_safe() -> None:
    """Clearing empties the list; stepping an empty list moves nothing."""
    qf = QuickFixList()
    qf.replace("diagnostics", [D1], "diagnostics")
    qf.clear()
    assert qf.snapshot() == ()
    assert qf.current() is None
    assert qf.step(1) is None
    assert qf.selected == 0
    assert qf.label == ""


def test_entries_are_immutable_pure_data() -> None:
    """Entries are frozen dataclasses; mutating the source list is inert."""
    qf = QuickFixList()
    batch = [D1, D2]
    qf.replace("diagnostics", batch, "diagnostics")
    batch.append(D3)
    assert qf.snapshot() == (D1, D2)
    entry = qf.snapshot()[0]
    assert dataclasses.is_dataclass(entry)
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.label = "mutated"  # pyright: ignore[reportAttributeAccessIssue] - intended
