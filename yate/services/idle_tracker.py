"""Idle-input tracking for the screensaver trigger (pure data, no I/O).

The tracker records when input activity last happened and answers one
question: has the configured idle threshold elapsed?  It owns no timer, no
thread and no UI -- the owner (the L4 shell) pokes it from its event
handler and polls :meth:`IdleTracker.due` on its own schedule, so a
disabled screensaver costs nothing but one small object.
"""

from __future__ import annotations

import time
from collections.abc import Callable


#: ``clock()`` -- seconds as a float; injectable so tests never sleep.
type Clock = Callable[[], float]


class IdleTracker:
    """Monotonic-clock idle tracker, reset by every :meth:`poke` call.

    *clock* defaults to :func:`time.monotonic`; tests inject a fake clock
    instead of sleeping.
    """

    def __init__(self, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self._last = clock()

    def poke(self) -> None:
        """Record one input event (any key or mouse activity)."""
        self._last = self._clock()

    def due(self, threshold: float) -> bool:
        """Whether *threshold* seconds have elapsed since the last poke.

        Reads the same injected clock as :meth:`poke`, so one fake clock
        drives both sides in tests.  ``threshold <= 0`` is always due --
        the pure predicate; the caller decides that a non-positive
        threshold means the automatic trigger is disabled and skips the
        poll entirely.
        """
        return threshold <= 0 or (self._clock() - self._last) >= threshold
