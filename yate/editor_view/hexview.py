"""Hex dump viewer with in-place editing: an xxd-style byte view for binaries.

The view renders 16 bytes per line -- offset, two hex groups and an ASCII
echo -- into a scrolling :class:`textual.widget.ScrollView` (line API).  The
data is handed in pre-read by the flow layer (:mod:`yate.flows.overlay_flows`
owns the size gate); the widget is presentation-only: it never touches the
filesystem.  Goto-address support adds a pure parser
(:func:`parse_hex_address`) and an in-screen input on the screen.

Editing works on an in-memory byte map: ``e`` toggles edit mode, hex digit
keys write nibbles at the byte cursor (advancing after the low half), ``u``
undoes and ``w`` hands the edited bytes to the ``write_bytes`` callback
injected on :class:`HexScreen` by the flow layer -- the write-back itself
(with its conflict and external-modification gates) lives in the flow layer,
so no layer here touches the filesystem (R3).

Theme ownership follows R13: the view subscribes on mount and repaints on
broadcast.  Key handling follows R10: the screen consumes the goto keys
(``g`` / ``:``), the editing toggle (``e``) and the dismiss keys
(``q`` / ``escape``); in edit mode it consumes the hex digits, ``u``, the
cursor keys, ``w`` and ``escape``; every other key falls through.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import override

from rich.segment import Segment
from rich.style import Style
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.geometry import Size
from textual.screen import ModalScreen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Input, Static

from yate.logs import tracing
from yate.paths import load_tcss

from yate.editor_view import theme
from yate.editor_view.scrollbars import apply_slim_scrollbars, apply_scrollbar_theme

log = tracing.get_logger(__name__)

#: Hard upper bound for hex view payloads; the flow layer refuses to push a
#: :class:`HexScreen` for larger files (100 MB read in one shot).
MAX_HEX_VIEW_SIZE: int = 100 * 1024 * 1024

#: Bytes rendered per line (the xxd convention).
_BYTES_PER_LINE: int = 16

#: Fixed content width of a full line: 8 offset digits + ``:`` + space +
#: 2 groups of 8 bytes (16 hex chars each, 2 spaces between groups,
#: total 34 chars) + 2 spaces + 16 ASCII chars.
_CONTENT_WIDTH: int = 9 + 1 + (2 * _BYTES_PER_LINE + 2) + 2 + _BYTES_PER_LINE

#: Hard cap on the undo stack; the oldest entry is dropped first
#: (``editor_core.buffer`` precedent).
MAX_UNDO_STEPS: int = 1000

#: Hex digit keys accepted in edit mode (either case).
_HEX_DIGITS: str = "0123456789abcdefABCDEF"

#: Edit-mode cursor keys -> byte delta (vim hjkl plus the arrow twins).
_CURSOR_DELTAS: dict[str, int] = {
    "h": -1,
    "l": 1,
    "k": -_BYTES_PER_LINE,
    "j": _BYTES_PER_LINE,
    "left": -1,
    "right": 1,
    "up": -_BYTES_PER_LINE,
    "down": _BYTES_PER_LINE,
}

#: Arrow keys the scrollable base binds to scrolling; in edit mode they are
#: intercepted by :meth:`HexView.on_key` before the bindings are checked.
_ARROW_KEYS: frozenset[str] = frozenset(("left", "right", "up", "down"))


def parse_hex_address(text: str, file_size: int) -> int:
    """Parse *text* into a byte offset and validate it against *file_size*.

    Accepted forms: ``0x``-prefixed hexadecimal (``0x1a``), bare hexadecimal
    containing letters (``ff``) and plain decimal (``42`` -- pure digit
    strings parse as decimal, so ``42`` is forty-two, not ``0x42``).  Raises
    :class:`ValueError` with an ``invalid format`` message when *text*
    matches neither form, and an ``out of bounds`` message when the parsed
    address falls outside ``[0, file_size)``.
    """
    stripped = text.strip()
    decimal = re.match(r"^\d+$", stripped)
    hex_digits = re.match(r"^(?:0x)?([0-9a-fA-F]+)$", stripped)
    if decimal:
        addr = int(stripped, 10)
    elif hex_digits:
        addr = int(stripped, 16)
    else:
        raise ValueError(f"invalid format: {stripped!r}")
    if not 0 <= addr < file_size:
        raise ValueError(
            f"address out of bounds: {addr:#x} (file size {file_size})"
        )
    return addr


def _classify_byte(b: int) -> str:
    """Classify *b* into a hexyl-style byte category name.

    Boundaries follow hexyl's default classification: ``0x00`` is ``null``,
    ``0x09-0x0d`` and ``0x20`` are ``whitespace``, ``0x21-0x7e`` is
    ``printable``, the remaining ASCII bytes (``0x01-0x08``, ``0x0e-0x1f``,
    ``0x7f``) are ``ascii_other`` and ``0x80-0xff`` is ``non_ascii``.
    """
    if b == 0x00:
        return "null"
    if 0x09 <= b <= 0x0D or b == 0x20:
        return "whitespace"
    if 0x21 <= b <= 0x7E:
        return "printable"
    if b <= 0x7F:
        return "ascii_other"
    return "non_ascii"


def _theme_style(category: str) -> Style:
    """Map a byte category to a Rich style from the active theme.

    The hexyl palette maps onto existing :class:`Theme` tokens (zero new
    tokens, so themes are followed automatically): ``null`` -> ``fg_dim``,
    ``printable`` -> ``accent``, ``whitespace`` -> ``green``,
    ``ascii_other`` -> ``accent2``, ``non_ascii`` -> ``yellow``.
    """
    t = theme.active()
    if category == "null":
        return Style(color=t.fg_dim)
    if category == "printable":
        return Style(color=t.accent)
    if category == "whitespace":
        return Style(color=t.green)
    if category == "ascii_other":
        return Style(color=t.accent2)
    return Style(color=t.yellow)


def _cell_style(
    b: int,
    index: int,
    cursor_byte: int,
    line_bg: str | None,
    edit_mode: bool,
) -> Style:
    """Style one byte cell for the dump columns.

    The base color is the hexyl classification; the cursor line adds
    *line_bg* as the cell background and, with *edit_mode* on, the cursor
    byte itself renders reversed (``on_accent`` on ``accent``).  Only
    styles vary -- the rendered text never does.
    """
    if edit_mode and index == cursor_byte:
        t = theme.active()
        return Style(color=t.on_accent, bgcolor=t.accent)
    style = _theme_style(_classify_byte(b))
    if line_bg is not None:
        return Style(color=style.color, bgcolor=line_bg)
    return style


def _hex_segments(
    chunk: bytes | bytearray,
    *,
    cursor_byte: int = -1,
    line_bg: str | None = None,
    edit_mode: bool = False,
) -> list[Segment]:
    """Render *chunk* as two 8-byte hex groups, one segment per byte.

    Each byte contributes its two hex characters in its classified color;
    a short final group is padded to 16 chars with default-style spaces,
    mirroring the plain-text xxd layout byte for byte.  *cursor_byte* is
    the in-chunk index of the cursor byte (``-1`` when the cursor sits on
    another line); see :func:`_cell_style` for the highlight rules.
    """
    segments: list[Segment] = []
    for i in range(0, len(chunk), 8):
        if i:
            segments.append(Segment("  ", Style(bgcolor=line_bg)))
        group = chunk[i : i + 8]
        for j, b in enumerate(group):
            segments.append(
                Segment(
                    f"{b:02x}",
                    _cell_style(b, i + j, cursor_byte, line_bg, edit_mode),
                )
            )
        # Pad to 16 chars if last group is short.
        pad = 16 - 2 * len(group)
        if pad:
            segments.append(Segment(" " * pad, Style(bgcolor=line_bg)))
    return segments


def _ascii_segments(
    chunk: bytes | bytearray,
    *,
    cursor_byte: int = -1,
    line_bg: str | None = None,
    edit_mode: bool = False,
) -> list[Segment]:
    """Render *chunk* as the ASCII echo column, one segment per byte.

    Printable bytes (``0x20-0x7e``) echo as-is, anything else as ``.`` --
    each character carries its source byte's styled cell (see
    :func:`_cell_style`).
    """
    return [
        Segment(
            chr(b) if 0x20 <= b <= 0x7E else ".",
            _cell_style(b, i, cursor_byte, line_bg, edit_mode),
        )
        for i, b in enumerate(chunk)
    ]


class HexView(ScrollView, can_focus=True):
    """Hex dump viewer (xxd-style layout) with in-place nibble editing.

    Each line renders 16 bytes: offset (8 hex digits + ``:``) + hex groups
    (2 groups of 8 bytes, no intra-byte spaces, 2 spaces between groups) +
    ASCII column (printable ``0x20-0x7e`` as-is, else ``.``).  Editing
    rewrites an in-memory ``bytearray`` copy; the cursor is a byte offset
    and the undo stack records ``(offset, old_byte)`` pairs capped at
    :data:`MAX_UNDO_STEPS`.  Write-back goes through the screen's injected
    callback; the view itself never touches the filesystem (R3).
    """

    DEFAULT_CSS = load_tcss("hex-view.tcss")

    #: unsubscribe hook from :func:`yate.editor_view.theme.attach`;
    #: ``None`` while not mounted (DiffPane precedent).
    _theme_unsubscribe: theme.Unsubscribe | None = None

    def __init__(
        self,
        path: Path,
        data: bytes,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._path = path
        # Mutable working copy for editing: the bytes handed in by the flow
        # layer are copied, never aliased.
        self._data: bytearray = bytearray(data)
        # Edit state: byte cursor, edit-mode flag, pending nibble half
        # (high first, low second -- two presses write one byte) and the
        # (offset, old_byte) undo stack.
        self._cursor_pos: int = 0
        self._edit_mode: bool = False
        self._nibble_high: bool = True
        self._undo_stack: list[tuple[int, int]] = []
        # ScrollView requires virtual_size to enable scrolling; the height is
        # the line count (last partial line included), the width the fixed
        # content width so narrow terminals get a horizontal scrollbar.
        self.virtual_size = Size(
            _CONTENT_WIDTH, (len(data) + _BYTES_PER_LINE - 1) // _BYTES_PER_LINE
        )

    @override
    def on_mount(self) -> None:
        """Wire slim scrollbars and subscribe to theme broadcasts (R13 / R15)."""
        super().on_mount()
        apply_slim_scrollbars(self)
        self._apply_theme()
        theme.attach(self, self._apply_theme)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def _apply_theme(self) -> None:
        """Repaint on theme broadcast (scrollbar palette, diff_pane precedent)."""
        apply_scrollbar_theme(self)
        self.refresh()

    def is_editing(self) -> bool:
        """Whether edit mode is on (the screen routes keys by this)."""
        return self._edit_mode

    def current_bytes(self) -> bytes:
        """Snapshot the edited payload as immutable bytes (write-back)."""
        return bytes(self._data)

    def enter_edit_mode(self) -> None:
        """Enter edit mode; hex digits now key nibbles at the cursor."""
        self._edit_mode = True
        self._nibble_high = True
        self.refresh()

    def exit_edit_mode(self) -> None:
        """Leave edit mode; keys return to the browsing face."""
        self._edit_mode = False
        self.refresh()

    def move_cursor(self, delta: int) -> None:
        """Move the cursor by *delta* bytes, clamped to the payload.

        The pending nibble half resets to high: moving abandons a half
        typed byte, so the next digit always starts a fresh one.
        """
        self._cursor_pos = max(
            0, min(self._cursor_pos + delta, len(self._data) - 1)
        )
        self._nibble_high = True
        self.refresh()

    def cursor_line(self) -> int:
        """The 16-byte content row the cursor sits on."""
        return self._cursor_pos // _BYTES_PER_LINE

    def cursor_col(self) -> int:
        """The byte column (``0``-``15``) the cursor sits on."""
        return self._cursor_pos % _BYTES_PER_LINE

    def edit_nibble(self, hex_digit: str) -> None:
        """Write one hex nibble at the cursor and record undo.

        *hex_digit* must be ``0-9`` / ``a-f`` / ``A-F`` (anything else is
        ignored).  The value merges into the pending half of the cursor
        byte -- high half first, low half second -- and the cursor advances
        to the next byte once the low half is written.  The overwritten
        byte is pushed onto the undo stack before the write; the stack is
        capped at :data:`MAX_UNDO_STEPS`, oldest entry dropped first.
        """
        if len(hex_digit) != 1 or hex_digit not in _HEX_DIGITS or not self._data:
            return
        value = int(hex_digit, 16)
        old_byte = self._data[self._cursor_pos]
        if self._nibble_high:
            new_byte = (old_byte & 0x0F) | (value << 4)
        else:
            new_byte = (old_byte & 0xF0) | value
        self._undo_stack.append((self._cursor_pos, old_byte))
        if len(self._undo_stack) > MAX_UNDO_STEPS:
            del self._undo_stack[0]
        self._data[self._cursor_pos] = new_byte
        if not self._nibble_high and self._cursor_pos < len(self._data) - 1:
            self._cursor_pos += 1
        self._nibble_high = not self._nibble_high
        self.refresh()

    def undo(self) -> None:
        """Undo the most recent nibble edit and park the cursor on it."""
        if not self._undo_stack:
            return
        offset, old_byte = self._undo_stack.pop()
        self._data[offset] = old_byte
        self._cursor_pos = offset
        self._nibble_high = True
        self.refresh()

    def on_key(self, event: Key) -> None:
        """Intercept the arrow keys while editing (scroll-binding takeover).

        The scrollable base binds the arrows to scrolling; in edit mode
        they must move the byte cursor instead, so they are consumed here
        before the widget's own bindings are checked (R10).  The remaining
        editing keys are not bound on the view and are routed by
        :meth:`HexScreen.on_key`.
        """
        if self._edit_mode and event.key in _ARROW_KEYS:
            self.move_cursor(_CURSOR_DELTAS[event.key])
            event.stop()

    @override
    def render_line(self, y: int) -> Strip:
        """Render one line of hex dump (offset + hex + ASCII), byte-classified.

        *y* is a viewport row; the content row is ``y + scroll_offset.y``
        (DiffPane precedent for the line API on this Textual version).  The
        rendered text is exactly the xxd layout; the per-byte classification
        colors live in the segment styles only (hexyl mapping onto theme
        tokens), so ``Strip.text`` stays a plain-text assertion surface.
        The cursor line carries a ``surface`` background and, in edit mode,
        the cursor byte renders reversed (``on_accent`` on ``accent``) --
        highlights touch styles only.
        """
        offset = (y + self.scroll_offset.y) * _BYTES_PER_LINE
        chunk = self._data[offset : offset + _BYTES_PER_LINE]
        if not chunk:
            return Strip.blank(self.size.width)
        t = theme.active()
        on_cursor_line = self.cursor_line() == offset // _BYTES_PER_LINE
        line_bg = t.surface if on_cursor_line else None
        cursor_byte = self._cursor_pos - offset if on_cursor_line else -1
        segments: list[Segment] = [
            Segment(
                f"{offset:08x}: ",
                Style(color=t.fg_muted, bgcolor=line_bg),
            ),
            *_hex_segments(
                chunk,
                cursor_byte=cursor_byte,
                line_bg=line_bg,
                edit_mode=self._edit_mode,
            ),
            Segment("  ", Style(bgcolor=line_bg)),
            *_ascii_segments(
                chunk,
                cursor_byte=cursor_byte,
                line_bg=line_bg,
                edit_mode=self._edit_mode,
            ),
        ]
        return Strip(segments).extend_cell_length(self.size.width)

    def _format_hex(self, chunk: bytes) -> str:
        """Format *chunk* as 2 groups of 8 bytes (xxd-style, plain text)."""
        return "".join(segment.text for segment in _hex_segments(chunk))

    def _format_ascii(self, chunk: bytes) -> str:
        """Format *chunk* as ASCII (printable 0x20-0x7e, else ``.``)."""
        return "".join(segment.text for segment in _ascii_segments(chunk))

    def scroll_to_line(self, line: int) -> None:
        """Scroll the dump so content row *line* sits at the viewport top.

        *line* is clamped to the rendered payload (``[0, line_count - 1]``),
        so an out-of-range target parks at the nearest edge instead of
        scrolling past the data.
        """
        scroll_y = max(0, min(line, self.virtual_size.height - 1))
        self.scroll_to(y=scroll_y, animate=False)


class HexScreen(ModalScreen[None]):
    """Full-screen overlay hosting a :class:`HexView` plus a goto-address input.

    ``g`` / ``:`` reveal the goto input, ``enter`` jumps to the parsed
    address and ``escape`` cancels it; with the input hidden ``e`` enters
    hex edit mode and ``q`` / ``escape`` dismiss the overlay.  In edit mode
    the hex digits key nibbles, ``u`` undoes, the vim/arrow keys move the
    byte cursor, ``w`` writes the edited bytes back through the injected
    ``write_bytes`` callback and ``escape`` leaves edit mode (R10: every
    other key falls through).
    """

    #: goto-address input handle, resolved in :meth:`on_mount` once the
    #: composed tree exists.
    _goto_input: Input | None = None

    #: hex view handle, resolved in :meth:`on_mount` once the composed tree
    #: exists; :meth:`save` falls back to the untouched payload handed in
    #: at construction while the screen is not mounted.
    _hex_view: HexView | None = None

    def __init__(
        self,
        path: Path,
        data: bytes,
        *,
        message: Callable[[str, str], None] | None = None,
        write_bytes: Callable[[Path, bytes, float, int], None] | None = None,
        mtime: float = 0.0,
        size: int = 0,
    ) -> None:
        super().__init__()
        self._path = path
        self._data = data
        # Error-report callback injected by the flow layer (the view never
        # imports upward, R3).  ``None`` keeps parse errors quiet in
        # un-injected hosts.
        self._message = message
        # Write-back callback injected by the flow layer (R3: the screen
        # never touches the filesystem itself; the conflict and TOCTOU
        # gates live in the flow layer).  ``None`` = read-only file or
        # un-injected host: the save is refused on the message line.
        self._write_bytes = write_bytes
        # Load-time stat fingerprint (mtime + size); the flow layer
        # re-checks both before writing so an externally modified file is
        # never overwritten.  (``_size`` itself is off-limits: the Textual
        # Widget base class owns that name for its layout size.)
        self._mtime = mtime
        self._load_size = size

    @override
    def compose(self) -> ComposeResult:
        """HexView filling the screen plus the hidden goto input and hint."""
        with Vertical():
            yield HexView(self._path, self._data, id="hex-view")
            goto_input = Input(id="hex-goto-input")
            goto_input.display = False
            yield goto_input
            hint = Static(
                "goto address: 0x hex or decimal - enter to jump, "
                "escape to cancel",
                id="hex-goto-hint",
            )
            hint.display = False
            yield hint

    def on_mount(self) -> None:
        """Resolve the goto input and hex view handles from the composed tree."""
        self._goto_input = self.query_one("#hex-goto-input", Input)
        self._hex_view = self.query_one("#hex-view", HexView)

    def show_goto_input(self) -> None:
        """Reveal and focus the goto-address input together with its hint."""
        if self._goto_input is None:
            return
        self._goto_input.display = True
        self.query_one("#hex-goto-hint", Static).display = True
        self._goto_input.focus()

    def hide_goto_input(self) -> None:
        """Hide the goto-address input and hand focus back to the hex view."""
        if self._goto_input is None:
            return
        self._goto_input.display = False
        self.query_one("#hex-goto-hint", Static).display = False
        self.query_one("#hex-view", HexView).focus()

    def save(self) -> None:
        """Write the edited bytes back through the injected callback (R3).

        Refused on the message line when no writer was injected (read-only
        file or un-injected host).  Writer failures (``OSError`` /
        ``ValueError``) are reported and leave the screen open; success
        reports ``saved``.
        """
        if self._write_bytes is None:
            if self._message is not None:
                self._message("write not available", "warn")
            return
        view = self._hex_view
        data = view.current_bytes() if view is not None else bytes(self._data)
        try:
            self._write_bytes(self._path, data, self._mtime, self._load_size)
        except (OSError, ValueError) as exc:
            if self._message is not None:
                self._message(f"save failed: {exc}", "warn")
            return
        if self._message is not None:
            self._message("saved", "ok")

    def on_key(self, event: Key) -> None:
        """Consume the goto / dismiss / editing keys; the rest fall through.

        Browsing face (plan-b behavior): ``g`` / ``:`` open the goto input,
        ``e`` enters hex edit mode and ``q`` / ``escape`` dismiss.  Edit
        mode consumes the hex digits (``0-9`` / ``a-f`` / ``A-F``), ``u``
        (undo), the vim/arrow cursor keys, ``w`` (write back) and
        ``escape`` (leave edit mode); everything else falls through (R10).
        While the goto input is open its keys are left to the input.
        """
        goto_open = self._goto_input is not None and self._goto_input.display
        view = self._hex_view
        if event.key in ("g", ":") and not goto_open:
            self.show_goto_input()
            event.stop()
            return
        if event.key == "escape":
            if goto_open:
                self.hide_goto_input()
            elif view is not None and view.is_editing():
                view.exit_edit_mode()
            else:
                self.dismiss(None)
            event.stop()
            return
        if event.key == "q" and not goto_open:
            self.dismiss(None)
            event.stop()
            return
        if view is None or goto_open:
            return
        if view.is_editing():
            if len(event.key) == 1 and event.key in _HEX_DIGITS:
                view.edit_nibble(event.key)
                event.stop()
            elif event.key == "u":
                view.undo()
                event.stop()
            elif event.key in _CURSOR_DELTAS:
                view.move_cursor(_CURSOR_DELTAS[event.key])
                event.stop()
            elif event.key == "w":
                self.save()
                event.stop()
            # any other key falls through (R10)
        elif event.key == "e":
            view.enter_edit_mode()
            event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Jump to the parsed address; report parse failures as a warning."""
        if event.input.id != "hex-goto-input":
            return
        try:
            addr = parse_hex_address(event.value, len(self._data))
        except ValueError:
            if self._message is not None:
                self._message(f"invalid address: {event.value!r}", "warn")
            return
        self.query_one("#hex-view", HexView).scroll_to_line(
            addr // _BYTES_PER_LINE
        )
        self.hide_goto_input()
