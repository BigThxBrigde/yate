"""Tests for the idle-input tracker (yate.services.idle_tracker)."""

from __future__ import annotations

from yate.services.idle_tracker import IdleTracker


def test_due_counts_from_construction_without_poke() -> None:
    """A fresh tracker becomes due once the threshold elapses."""
    now = 0.0
    tracker = IdleTracker(clock=lambda: now)
    assert not tracker.due(59.0, 60.0)
    assert tracker.due(60.0, 60.0)


def test_poke_resets_the_idle_clock() -> None:
    """Every poke restarts the threshold window."""
    now = 0.0
    tracker = IdleTracker(clock=lambda: now)
    tracker.poke()
    now = 30.0
    assert not tracker.due(now, 60.0)
    tracker.poke()
    now = 61.0
    # only 30s since the second poke, not 61s since the first
    assert not tracker.due(now, 60.0)
    now = 91.0
    assert tracker.due(now, 60.0)


def test_zero_threshold_is_always_due() -> None:
    """A non-positive threshold is unconditionally due (pure predicate)."""
    now = 0.0
    tracker = IdleTracker(clock=lambda: now)
    tracker.poke()
    assert tracker.due(now, 0.0)
    assert tracker.due(now, -1.0)
