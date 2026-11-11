"""Macro record / replay flow: registers of raw key chords (L3).

State lives on the session (L1, UI-free): :attr:`EditorSession.macro_registers`
holds the recorded raw-key sequences, ``macro_recording`` the in-flight
recording and ``macro_awaiting`` the pending macro-prefix state.  This module
only orchestrates: it sees one raw key at a time from the dispatch layer
(:meth:`MacroFlows.pre_dispatch`) and replays recorded sequences through the
very same raw-key dispatch path, so what was recorded is what gets replayed.

The single control key is the shared L0 constant :data:`MACRO_PREFIX_KEY`
(``<f6>``): ``<f6> r {reg}`` starts a recording, ``<f6>`` while recording
stops it, ``<f6> p {reg}`` replays, ``<f6> @`` repeats the last macro.  Both
built-in keymaps bind it to the same ``macro_prefix`` action (see
``tests/test_macro_key_binding.py``).
"""

from __future__ import annotations

from collections.abc import Callable

from yate.keymaps.keys import MACRO_PREFIX_KEY, parse_key
from yate.logs import tracing
from yate.session import EditorSession

log = tracing.get_logger(__name__)

#: The prefix key in raw (dispatch) form: the keymap tables and the key
#: codec speak raw bytes, so comparisons below must use ``parse_key`` output,
#: never the ``<f6>`` notation (which is for bindings and docs only).
_PREFIX_RAW: str = parse_key(MACRO_PREFIX_KEY)

#: Characters a macro register name accepts (vim-style single characters).
REGISTER_CHARS: frozenset[str] = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789"
)

#: Sink that dispatches one raw key through the normal editor path.
type RawKeySink = Callable[[str], bool]

#: Sink that reports a message on the editor message line.
type MessageSink = Callable[[str], None]

#: Reads the pending count prefix from the active keymap (consumes it).
type CountSource = Callable[[], int]


class MacroFlows:
    """Records raw-key sequences into registers and replays them.

    The flow holds no state of its own beyond the injected collaborators:
    every piece of macro state lives on :class:`EditorSession` so both
    built-in keymaps, the status bar and the which-key panel read the same
    truth.  *handle_raw_key* is the editor's raw-key dispatch entry (replay
    reuses it, keeping chord / count / unbound-key semantics identical to
    manual typing); *message* reports user-visible notices; *count_source*
    lazily consumes the active keymap's count prefix (vim ``3@a`` -- the
    table-driven keymap returns 1).
    """

    def __init__(
        self,
        session: EditorSession,
        handle_raw_key: RawKeySink,
        message: MessageSink,
        count_source: CountSource,
    ) -> None:
        self.session = session
        self._handle_raw_key = handle_raw_key
        self._message = message
        self._count_source = count_source

    # --------------------------------------------------------------- queries

    def is_control_key(self, raw: str) -> bool:
        """Whether *raw* is the macro prefix control key (raw form)."""
        return raw == _PREFIX_RAW

    # --------------------------------------------------------- dispatch hook

    def pre_dispatch(self, raw: str) -> bool:
        """Intercept macro control keys and record replayable keys.

        Returns ``True`` when *raw* was consumed by the macro state machine
        (the dispatch layer then stops without keymap dispatch); ``False``
        means the key continues through the normal keymap path -- and, while
        a recording is in flight, was appended to it first.
        """
        session = self.session
        if session.macro_playing:
            # Keys produced by a replay dispatch plainly: a replayed prefix
            # key must not re-enter the macro state machine (AC4).
            return False
        if session.macro_awaiting is not None:
            awaiting = session.macro_awaiting
            session.macro_awaiting = None
            if awaiting == "prefix":
                if raw == "r":
                    session.macro_awaiting = "record"
                    return True
                if raw == "p":
                    session.macro_awaiting = "play"
                    return True
                if raw == "@":
                    self.repeat_last()
                    return True
                self._message("macro: r = record, p = play, @ = repeat last")
                return False
            if awaiting == "record":
                if raw in REGISTER_CHARS:
                    session.macro_recording = (raw, [])
                    log.debug("macro record start: register=%s", raw)
                    return True
                self._message("macro: register name must be a-z or 0-9")
                return False
            # awaiting == "play"
            if raw in REGISTER_CHARS:
                self.play(raw)
                return True
            self._message("macro: register name must be a-z or 0-9")
            return False
        if raw == _PREFIX_RAW:
            if session.macro_recording is not None:
                self._stop_recording()
            else:
                session.macro_awaiting = "prefix"
            return True
        if session.macro_recording is not None:
            session.macro_recording[1].append(raw)
        return False

    # ------------------------------------------------------------ operations

    def toggle_record(self, register: str | None = None) -> None:
        """Start recording into *register*, or stop the running recording."""
        session = self.session
        if session.macro_recording is not None:
            self._stop_recording()
            return
        if register is None or register not in REGISTER_CHARS:
            self._message("macro: usage :macro-record {a-z0-9}")
            return
        session.macro_recording = (register, [])
        log.debug("macro record start: register=%s", register)

    def play(self, register: str | None = None, count: int | None = None) -> None:
        """Replay *register*'s sequence *count* times through the editor.

        *register* ``None`` replays :attr:`EditorSession.macro_last_register`;
        *count* ``None`` consumes the active keymap's pending count prefix
        (vim ``3@a``; table-driven keymaps yield 1).  Replays while a
        recording is running or another replay is in flight are rejected
        with a notice (AC4).
        """
        session = self.session
        if session.macro_recording is not None:
            self._message("macro: stop recording first")
            return
        if session.macro_playing:
            self._message("macro: replay already in progress")
            return
        name = register if register is not None else session.macro_last_register
        if name is None or name not in REGISTER_CHARS:
            self._message("macro: usage :macro-play {a-z0-9} [count]")
            return
        sequence = session.macro_registers.get(name)
        if sequence is None:
            self._message(f"macro: nothing recorded in register {name}")
            return
        session.macro_last_register = name
        self._replay(sequence, 1 if count is None else count)

    def repeat_last(self, count: int | None = None) -> None:
        """Replay the last played-or-recorded register (``@@``)."""
        if self.session.macro_last_register is None:
            self._message("macro: no previous macro to repeat")
            return
        self.play(self.session.macro_last_register, count)

    # ------------------------------------------------------------ internals

    def _stop_recording(self) -> None:
        session = self.session
        assert session.macro_recording is not None
        register, sequence = session.macro_recording
        session.macro_registers[register] = sequence
        session.macro_last_register = register
        session.macro_recording = None
        log.debug(
            "macro record stop: register=%s keys=%d", register, len(sequence)
        )

    def _replay(self, sequence: list[str], count: int) -> None:
        session = self.session
        session.macro_playing = True
        try:
            for _ in range(count):
                for raw in list(sequence):
                    self._handle_raw_key(raw)
        finally:
            session.macro_playing = False
