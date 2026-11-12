"""Macro recording and replay orchestration (L3 flows).

The L1 :class:`~yate.session.EditorSession` owns the ``macro`` state; this
module only sequences it.  Raw-key dispatch and user notices arrive as
injected callables, so no App handle is retained here (capability injection).
"""

from __future__ import annotations

from collections.abc import Callable

from yate.keymaps.keys import MACRO_CONTROL_KEYS
from yate.logs import tracing
from yate.session import EditorSession

log = tracing.get_logger(__name__)

#: Injects ``ed.handle_raw_key``: one raw key per call, boolean handled.
type DispatchRaw = Callable[[str], bool]
#: Injects ``ed.message(text, kind)`` for user-facing notices.
type Notify = Callable[[str, str], None]

#: Replay nesting depth ceiling (AC4): replay while replaying is refused.
MAX_PLAY_DEPTH: int = 1
#: Upper bound on a recorded key sequence, to keep buffers finite.
MAX_MACRO_KEYS: int = 10000
#: Legal single-character macro register names.
MACRO_REGISTER_CHARS: str = "abcdefghijklmnopqrstuvwxyz0123456789"


class MacroFlows:
    """Sequence macro recording, awaiting and replay over L1 MacroState.

    The instance keeps only the injected collaborators; all durable state
    lives on ``session.macro`` so the flows layer stays replaceable.
    """

    def __init__(
        self,
        session: EditorSession,
        dispatch_raw: DispatchRaw,
        notify: Notify,
    ) -> None:
        self._session = session
        self._dispatch_raw = dispatch_raw
        self._notify = notify

    def toggle_record(self) -> None:
        """Enter the record awaiting state, or stop an active recording.

        The record key never consumes a captured count, so ``pending_count``
        is deliberately left untouched here.
        """
        if self.reject_if_playing():
            return
        macro = self._session.macro
        if macro.recording is not None:
            self.stop()
        else:
            macro.awaiting = "record"

    def request_play(self, count: int = 1) -> None:
        """Arm the play awaiting state, carrying the captured *count*."""
        if self.reject_if_playing():
            return
        macro = self._session.macro
        macro.pending_count = count
        macro.awaiting = "play"

    def replay_last(self, count: int | None = None) -> None:
        """Replay the last register; None/1 reuse its count, >=2 override."""
        if self.reject_if_playing():
            return
        macro = self._session.macro
        if macro.last_played is None:
            self._notify("no last macro replay", "warn")
            return
        last_reg, last_count = macro.last_played
        effective = last_count if (count is None or count == 1) else count
        self.play(last_reg, effective)

    def begin_with(self, reg: str) -> None:
        """Consume the awaited register character and start recording / play."""
        macro = self._session.macro
        if macro.awaiting is None:
            return
        if not (len(reg) == 1 and reg in MACRO_REGISTER_CHARS):
            self._notify("macro register must be one character in a-z0-9", "warn")
            macro.awaiting = None
            return
        awaiting = macro.awaiting
        macro.awaiting = None
        if awaiting == "record":
            macro.recording = reg
            macro.buffer = []
            macro.registers.pop(reg, None)
            return
        count = macro.pending_count
        macro.pending_count = 1
        self.play(reg, count)

    def play(self, reg: str, count: int) -> None:
        """Replay *reg* exactly *count* times through the injected dispatch."""
        if self.reject_if_playing():
            return
        macro = self._session.macro
        keys = macro.get(reg)
        if keys == ():
            self._notify(f"macro register @{reg} is empty", "warn")
            return
        if count < 1 or count > MAX_MACRO_KEYS:
            self._notify("macro count must be a positive integer", "warn")
            return
        macro.play_depth += 1
        if macro.play_depth > MAX_PLAY_DEPTH:
            macro.play_depth -= 1
            self._notify("macro replay already in progress", "warn")
            return
        macro.playing = True
        try:
            log.debug("macro play: reg=%s count=%d", reg, count)
            for _ in range(count):
                for raw in keys:
                    self._dispatch_raw(raw)
        finally:
            macro.playing = False
            macro.play_depth -= 1
        macro.last_played = (reg, count)

    def stop(self) -> None:
        """Freeze the current buffer into a tuple under the recording register."""
        macro = self._session.macro
        reg = macro.recording
        if reg is None:
            return
        macro.registers[reg] = tuple(macro.buffer)
        macro.recording = None
        macro.buffer = []

    def record_raw(self, raw: str) -> None:
        """Append one raw key while recording, excluding macro control keys."""
        macro = self._session.macro
        if macro.recording is None:
            return
        if raw in MACRO_CONTROL_KEYS:
            return
        if len(macro.buffer) >= MAX_MACRO_KEYS:
            self._notify("macro sequence limit reached", "warn")
            return
        macro.buffer.append(raw)

    def reject_if_playing(self) -> bool:
        """Return True and warn when a replay is already in progress (AC4)."""
        if not self._session.macro.playing:
            return False
        self._notify("macro replay already in progress", "warn")
        return True
