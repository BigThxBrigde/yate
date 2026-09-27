"""Full-terminal screensaver: one pixel character walking across the screen.

A :class:`~textual.screen.ModalScreen` that covers the whole terminal with
the app background and walks a single sprite left-to-right (half-block
pixels rendered by :mod:`yate.editor_sprites.render`).  Characters rotate
through a shuffle playlist with no immediate repeats; each one stays for
the configured number of seconds or until it has fully walked off the
right edge, whichever comes first.

Dismissal is self-contained (R10): any key or mouse movement pops the
screen and is stopped right here, so the keystroke never leaks into the
editor underneath.  Colors come from the theme bridge via CSS variables
(R13) -- the shell never paints this screen.
"""

from __future__ import annotations

import random
from typing import override

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static

from yate.editor_sprites.characters import (
    Sprite,
    character_names,
    get_character,
    shuffle_order,
)
from yate.editor_sprites.render import render_rows, walk_x

#: Animation ticks per second (the walk advances one column per tick).
TICKS_PER_SECOND = 10

#: Animation frames change every this many ticks (~3.3 fps).
_FRAME_EVERY = 3


class ScreensaverScreen(ModalScreen[None]):
    """Idle screensaver overlay: a pixel character parade, any input exits.

    ``characters`` is the (already rc-filtered) name roster -- empty falls
    back to the whole registry so the screen can never end up with nothing
    to show.  ``switch_seconds`` is how long one character stays on
    screen; ``0`` degenerates to one animation tick, which is clamped to
    keep at least one frame visible.
    """

    DEFAULT_CSS = """
    ScreensaverScreen {
        background: $background;
    }
    ScreensaverScreen .hint {
        dock: bottom;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, characters: tuple[str, ...], switch_seconds: int) -> None:
        self._names = tuple(characters) if characters else character_names()
        self._switch_seconds = switch_seconds
        self._rng = random.Random()
        self._canvas = Static("")
        self._hint = Static(
            " any key exits · alt+shift+s toggles ", classes="hint"
        )
        self._order: list[str] = []
        self._order_pos = -1
        self._sprite: Sprite | None = None
        self._row = 0
        self._tick_count = 0
        self._spawn_tick = 0
        super().__init__()

    @override
    def compose(self) -> ComposeResult:
        yield self._canvas
        yield self._hint

    def on_mount(self) -> None:
        """Start the playlist and the animation clock."""
        self._order = shuffle_order(self._names, self._rng)
        self.set_interval(1 / TICKS_PER_SECOND, self._tick)
        self.set_timer(5.0, self._hide_hint)
        self._advance()

    # ------------------------------------------------------------- animation

    def _tick(self) -> None:
        """One animation step: advance, then switch or repaint."""
        self._tick_count += 1
        sprite = self._sprite
        if sprite is None:
            return
        elapsed = self._tick_count - self._spawn_tick
        switch_ticks = max(1, self._switch_seconds * TICKS_PER_SECOND)
        sprite_w = len(sprite.frames[0][0])
        travel = max(1, self.size.width) + sprite_w
        if elapsed >= switch_ticks or elapsed >= travel:
            self._advance()
            return
        self._paint()

    def _advance(self) -> None:
        """Switch to the next playlist entry and spawn it at a random row."""
        self._order_pos += 1
        if self._order_pos >= len(self._order):
            avoid = self._order[-1] if self._order else None
            self._order = shuffle_order(self._names, self._rng, avoid=avoid)
            self._order_pos = 0
        self._sprite = get_character(self._order[self._order_pos])
        self._spawn_tick = self._tick_count
        rows = (len(self._sprite.frames[0]) + 1) // 2
        height = max(1, self.size.height)
        self._row = self._rng.randrange(max(1, height - rows + 1))
        self._paint()

    def _paint(self) -> None:
        """Rebuild the whole canvas: blank rows plus the current frame."""
        sprite = self._sprite
        if sprite is None:
            return
        width = max(1, self.size.width)
        height = max(1, self.size.height)
        elapsed = self._tick_count - self._spawn_tick
        frame = sprite.frames[(elapsed // _FRAME_EVERY) % len(sprite.frames)]
        rows = render_rows(frame, sprite.palette)
        x = walk_x(elapsed, width, len(frame[0]))
        out = Text()
        for row_no in range(height):
            if row_no:
                out.append("\n")
            offset = row_no - self._row
            if not 0 <= offset < len(rows):
                continue
            # visible sprite columns: clip against both screen edges so a
            # half-entered / half-exited sprite never widens the canvas
            x0 = max(x, 0)
            x1 = min(x + len(rows[offset]), width)
            if x0 >= x1:
                continue
            if x0:
                out.append(" " * x0)
            for glyph, style in rows[offset][x0 - x : x1 - x]:
                out.append(glyph, style=style or None)
        self._canvas.update(out)

    def _hide_hint(self) -> None:
        """Fade the bottom-left hint away once it has been read."""
        self._hint.display = False

    # ------------------------------------------------------------- dismissal

    def on_key(self, event: events.Key) -> None:
        """Any key exits; the key is consumed and never reaches the editor."""
        event.stop()
        event.prevent_default()
        # dismiss() (not awaited) pops this screen without needing the App
        # handle -- the documented way for a screen to close itself.
        self.dismiss()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Mouse movement counts as input and exits too."""
        event.stop()
        self.dismiss()
