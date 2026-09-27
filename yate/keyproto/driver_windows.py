"""Windows driver that delivers full key chords (VK + modifiers).

Textual's stock Windows driver collapses every ``KEY_EVENT_RECORD`` to its
``UnicodeChar``: the virtual-key code and ``dwControlKeyState`` are dropped,
so chords legacy bytes cannot represent are lost before yate ever sees them
(ctrl+digit produces no event at all; ctrl+` and ctrl+space share one NUL
byte).  This module keeps the stock record loop byte-for-byte for everything
yate already handles, and routes chorded records through
:class:`~yate.keyproto.chords.KeyChord` to synthesize a canonical Textual
key event (``ctrl+1``, ``ctrl+shift+e``, ``ctrl+\\`` ``...).  The dispatch
layers were already name-ready (``TOGGLE_KEYS`` contains ``ctrl+``, the
completion branch matches ``ctrl+space``), so delivery alone activates the
previously unreachable semantics.

On top of the record path the driver enables win32-input-mode
(``CSI ?9001h``): Windows Terminal then encodes every key as a structured
frame carried as text in the character stream, decoded by
:mod:`yate.keyproto.frames` -- the only delivery that preserves the modifier
state of keys legacy encodes lossily (ctrl+1 arrives as bare ``1``).
Terminals without win32-input-mode ignore the mode and keep the legacy path.

Windows-only; import lazily from :meth:`yate.app.YateApp.get_driver_class`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from ctypes import byref, wintypes
from typing import IO, cast, override

from textual import constants
from textual._xterm_parser import XTermParser
from textual.app import App
from textual.drivers import win32
from textual.drivers._writer_thread import WriterThread
from textual.drivers.windows_driver import WindowsDriver
from textual.events import Key
from textual.message import Message

from yate.keyproto.aliases import chord_to_key_name
from yate.keyproto.chords import (
    ALT_BITS,
    CTRL_BITS,
    MODIFIER_VKS,
    SHIFT_BIT,
    VK_OEM_2,
    VK_OEM_3,
    VK_OEM_4,
    VK_OEM_5,
    VK_OEM_6,
    VK_SPACE,
    KeyChord,
)
from yate.keyproto.frames import Win32FrameStream, frame_to_char, frame_to_key_name
from yate.logs import tracing

log = tracing.get_logger(__name__)

#: VK codes whose chords yate can name: digits, letters, space and the
#: US-layout punctuation OEM keys the keymaps actually reference.
#: Everything else keeps the legacy char path (arrows, F-keys, navigation --
#: their chord names are not wired into yate's tables).
_CHORD_VKS = frozenset(
    [
        *range(0x30, 0x3A),  # VK_0..VK_9
        *range(0x41, 0x5B),  # VK_A..VK_Z
        VK_SPACE,
        VK_OEM_2,
        VK_OEM_3,
        VK_OEM_4,
        VK_OEM_5,
        VK_OEM_6,
    ]
)


def record_key_override(
    vk: int, control_state: int, unicode_char: str
) -> KeyChord | None:
    """Return the :class:`KeyChord` for a chorded console key record, or
    ``None`` when the record must keep the legacy char path.

    A chord needs ctrl or alt held and a virtual key yate can name
    (:data:`_CHORD_VKS`); shift is captured so ``ctrl+shift+e`` finally
    differs from ``ctrl+e``.  *unicode_char* rides along as transport data.
    """
    if vk == 0 or vk in MODIFIER_VKS:
        return None
    ctrl = bool(control_state & CTRL_BITS)
    alt = bool(control_state & ALT_BITS)
    if not (ctrl or alt) or vk not in _CHORD_VKS:
        return None
    return KeyChord(
        vk,
        ctrl=ctrl,
        alt=alt,
        shift=bool(control_state & SHIFT_BIT),
        char=unicode_char,
    )


class ChordEventMonitor(win32.EventMonitor):
    """The stock Windows input thread with a chord branch for key records.

    ``run`` replicates :meth:`textual.drivers.win32.EventMonitor.run` and
    inserts exactly one branch: a chorded ``KEY_EVENT_RECORD`` is delivered
    as a canonical :class:`textual.events.Key` instead of being reduced to
    its character.  Any divergence in behaviour for non-chorded records
    would be a bug.  The replication is pinned against Textual **8.2.8** --
    when upgrading Textual, diff the stock ``run`` against this one first.
    """

    #: The stock parent stores this without an annotation; declare it so
    #: pyright strict can type ``self.app.log`` below.
    app: App[None]

    @override
    def run(self) -> None:
        """Read console input records; deliver chords as canonical key events."""
        exit_requested = self.exit_event.is_set
        parser = XTermParser(debug=constants.DEBUG)
        # win32-input-mode frames arrive as text inside the character stream
        # (see yate.keyproto.frames); decode them incrementally across read
        # batches and hand only the residual text to the legacy parser.
        frame_stream = Win32FrameStream()
        # The stock parser events are Messages at the type level; the runtime
        # input path is the same callable for both (see the Key cast below).
        deliver = cast("Callable[[Message], None]", self.process_event)

        try:
            read_count = wintypes.DWORD(0)
            hIn = win32.GetStdHandle(win32.STD_INPUT_HANDLE)

            max_events = 1024
            key_event_type = 0x0001
            window_buffer_size_event = 0x0004

            arrtype = win32.INPUT_RECORD * max_events
            input_records = arrtype()
            read_console_input_w = win32.KERNEL32.ReadConsoleInputW
            keys: list[str] = []
            append_key = keys.append

            while not exit_requested():

                for event in parser.tick():
                    deliver(event)

                # Wait for new events
                if win32.wait_for_handles([hIn], 100) is None:
                    continue

                # Get new events
                read_console_input_w(
                    hIn,
                    byref(input_records),
                    max_events,
                    byref(read_count),
                )
                read_input_records = input_records[: read_count.value]

                del keys[:]
                new_size: tuple[int, int] | None = None

                for input_record in read_input_records:
                    event_type = input_record.EventType

                    if event_type == key_event_type:
                        key_event = input_record.Event.KeyEvent
                        key = key_event.uChar.UnicodeChar
                        if key_event.bKeyDown:
                            # conpty emits zero-VK records for modifier
                            # transitions; the stock driver drops them.  Win32-
                            # input-mode frames ride the same shape (zero-VK
                            # text records) but carry real characters -- keep
                            # those so the frame stream below sees them.
                            if (
                                key_event.dwControlKeyState
                                and key_event.wVirtualKeyCode == 0
                                and not key
                            ):
                                continue
                            chord = record_key_override(
                                key_event.wVirtualKeyCode,
                                key_event.dwControlKeyState,
                                key,
                            )
                            if chord is not None:
                                name = chord_to_key_name(chord)
                                # VK-level evidence: the entry log in
                                # yate.editor only shows the synthesized
                                # name, which cannot explain layouts that
                                # deliver a chord under an unexpected name.
                                log.debug(
                                    "chord: vk=0x%02x state=0x%04x char=%r -> %s",
                                    key_event.wVirtualKeyCode,
                                    key_event.dwControlKeyState,
                                    chord.char,
                                    name,
                                )
                                deliver(Key(name, character=chord.char))
                                continue
                            append_key(key)
                    elif event_type == window_buffer_size_event:
                        size = input_record.Event.WindowBufferSizeEvent.dwSize
                        new_size = (size.X, size.Y)

                if keys:
                    text = (
                        "".join(keys)
                        .encode("utf-16", "surrogatepass")
                        .decode("utf-16")
                    )
                    key_frames, residual = frame_stream.feed(text)
                    residuals = [residual]
                    for key_frame in key_frames:
                        name = frame_to_key_name(key_frame)
                        if name is not None:
                            # Same VK-level evidence log as the record path.
                            log.debug(
                                "chord: vk=0x%02x state=0x%04x char=%r -> %s",
                                key_frame.vk,
                                key_frame.state,
                                key_frame.char_text,
                                name,
                            )
                            deliver(Key(name, character=key_frame.char_text))
                            continue
                        frame_char = frame_to_char(key_frame)
                        if frame_char:
                            residuals.append(frame_char)
                    residual_text = "".join(residuals)
                    if residual_text:
                        for event in parser.feed(residual_text):
                            deliver(event)
                if new_size is not None:
                    self.on_size_change(*new_size)

        except Exception as error:
            self.app.log.error("EVENT MONITOR ERROR", error)


class YateWindowsDriver(WindowsDriver):
    """Windows driver delivering full chords; otherwise identical to the
    stock :class:`~textual.drivers.windows_driver.WindowsDriver`."""

    @override
    def start_application_mode(self) -> None:
        """Start application mode with the chord-aware input monitor.

        Replicates the stock
        :meth:`textual.drivers.windows_driver.WindowsDriver.start_application_mode`
        sequence (pinned against Textual **8.2.8**) with one insertion
        (``?9001h``) and the chord monitor thread -- on a Textual upgrade,
        diff the stock sequence against this body first.
        """
        loop = asyncio.get_running_loop()

        self._restore_console = win32.enable_application_mode()

        # Driver.__init__ always sets _file to sys.__stdout__; the base class
        # types it as optional, the writer thread requires the stream.
        self._writer_thread = WriterThread(cast("IO[str]", self._file))
        self._writer_thread.start()

        self.write("\x1b[?1049h")  # Enable alt screen
        self._enable_mouse_support()
        self.write("\x1b[?25l")  # Hide cursor
        self.write("\033[?1004h")  # Enable FocusIn/FocusOut.
        self.write("\x1b[>1u")  # https://sw.kovidgoyal.net/kitty/keyboard-protocol/
        # Win32-input-mode: terminals that implement it (Windows Terminal)
        # encode every key as a full-fidelity frame (VK + modifiers), which
        # the monitor's frame stream decodes -- this is what makes ctrl+digit
        # and ctrl+shift+letter deliverable at all.  ConPTY forwards the
        # frames as text; terminals without support ignore the mode and keep
        # the legacy path.  https://learn.microsoft.com/en-us/windows/console/win32-input-mode
        self.write("\x1b[?9001h")
        self.flush()
        self._enable_bracketed_paste()

        self._event_thread = ChordEventMonitor(
            loop, self._app, self.exit_event, self.process_message
        )
        self._event_thread.start()

    @override
    def stop_application_mode(self) -> None:
        """Stop application mode, restoring state (incl. win32-input-mode)."""
        # Written before the stock teardown so the mode reset precedes the
        # alt-screen leave in the output stream.
        self.write("\x1b[?9001l")
        super().stop_application_mode()
