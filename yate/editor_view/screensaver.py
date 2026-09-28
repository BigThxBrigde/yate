"""Full-terminal screensaver: a parade of pixel characters walking by.

A :class:`~textual.screen.ModalScreen` that covers the whole terminal with
the app background while a small parade of sprites crosses it left-to-right
(half-block pixels rendered by :mod:`yate.editor_sprites.render`).  The
newest walker hands off to a successor once it is 1/8-1/3 (random) through
its journey -- or inside an explicitly configured ``dist_bounds`` window,
which also overrides the ``switch`` seconds floor.  The successor always
shows a character that is not currently
on screen, on rows no active walker occupies -- when every row is taken,
no successor spawns.  A walker leaves only after it has fully crossed the
current terminal width, so the walk distance always follows the live
terminal size, and the parade self-regulates to a few concurrent sprites.

Dismissal is self-contained (R10): any key or mouse movement pops the
screen and is stopped right here, so the keystroke never leaks into the
editor underneath.  Colors come from the theme bridge via CSS variables
(R13) -- the shell never paints this screen.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
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

#: Animation ticks per second (each walker advances one column per tick).
TICKS_PER_SECOND = 10

#: Animation frames change every this many ticks (~3.3 fps).
_FRAME_EVERY = 3


@dataclass
class Walker:
    """One sprite instance currently walking across the screen.

    Exposed read-only via :attr:`ScreensaverScreen.walkers`; the screen
    itself mutates the hand-off flag while the parade runs.
    """

    name: str
    sprite: Sprite
    #: Top text row of the sprite; its row band is owned exclusively.
    row: int
    #: Text rows the sprite occupies (``ceil(pixel rows / 2)``).
    rows: int
    #: Tick the walker spawned on; its x position derives from this.
    spawn_tick: int
    #: Tick at or after which the walker hands off to a successor.
    spawn_at: int
    #: Whether the successor hand-off already happened (or was refused).
    spawned_successor: bool = False

    @property
    def sprite_w(self) -> int:
        """Pixel width of the sprite (one text column per pixel)."""
        return len(self.sprite.frames[0][0])


class ScreensaverScreen(ModalScreen[None]):
    """Idle screensaver overlay: a pixel character parade, any input exits.

    ``characters`` is the (already rc-filtered) name roster -- empty falls
    back to the whole registry so the screen can never end up with nothing
    to show.  ``switch_seconds`` is the minimum number of seconds between
    two spawns; ``0`` lets the successor spawn as soon as the newest
    walker is 1/8-1/3 through its journey.
    """

    DEFAULT_CSS = """
    ScreensaverScreen {
        background: $background;
        overflow: hidden;
    }
    ScreensaverScreen .canvas {
        width: 1fr;
        height: 1fr;
        overflow: hidden;
    }
    ScreensaverScreen .hint {
        dock: bottom;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        characters: tuple[str, ...],
        switch_seconds: int,
        dist_bounds: tuple[float, float] | None = None,
    ) -> None:
        self._names = tuple(characters) if characters else character_names()
        self._switch_seconds = switch_seconds
        #: Explicit ``(lower, upper)`` journey window from yaterc; when set
        #: it replaces both the built-in 1/8-1/3 window and ``switch_seconds``.
        self._dist_bounds = dist_bounds
        self._rng = random.Random()
        self._canvas = Static("", classes="canvas")
        self._hint = Static(
            " any key exits · alt+shift+s toggles ", classes="hint"
        )
        self._walkers: list[Walker] = []
        self._bag: list[str] = []
        self._last_name: str | None = None
        self._tick_count = 0
        super().__init__()

    @override
    def compose(self) -> ComposeResult:
        yield self._canvas
        yield self._hint

    @property
    def walkers(self) -> tuple[Walker, ...]:
        """Snapshot of the sprites currently walking (test/telemetry view)."""
        return tuple(self._walkers)

    def on_mount(self) -> None:
        """Start the parade and the animation clock."""
        self.set_interval(1 / TICKS_PER_SECOND, self.advance_tick)
        self.set_timer(5.0, self._hide_hint)
        self._spawn()
        self._paint()

    # ------------------------------------------------------------- animation

    def advance_tick(self) -> None:
        """Advance one animation step: retire, hand off, then repaint.

        Public so tests can drive time deterministically instead of
        waiting on the real 10 Hz interval.
        """
        self._tick_count += 1
        width = max(1, self.size.width)
        # Walkers leave only through the right edge of the *current*
        # terminal width, so the walk distance follows resizes for free.
        self._walkers = [
            w
            for w in self._walkers
            if self._tick_count - w.spawn_tick < width + w.sprite_w
        ]
        if not self._walkers:
            self._spawn()
        else:
            newest = self._walkers[-1]
            if (
                not newest.spawned_successor
                and self._tick_count - newest.spawn_tick >= newest.spawn_at
            ):
                newest.spawned_successor = True
                self._spawn()
        self._paint()

    def _spawn(self) -> None:
        """Introduce a walker that differs from every active one.

        The name must not be on screen and the sprite's rows must be free;
        when no such row exists the spawn is skipped -- the parade simply
        stays as it is until walkers exiting free rows up.  A sprite taller
        than the terminal is still allowed, drawn clipped from the top row.
        """
        width = max(1, self.size.width)
        height = max(1, self.size.height)
        taken = {w.name for w in self._walkers}
        name = self._next_name(taken)
        if name is None:
            return
        sprite = get_character(name)
        rows = (len(sprite.frames[0]) + 1) // 2
        occupied: set[int] = set()
        for w in self._walkers:
            occupied.update(range(w.row, w.row + w.rows))
        if rows >= height:
            row_options = [0] if 0 not in occupied else []
        else:
            row_options = [
                r
                for r in range(height - rows + 1)
                if not any(o in occupied for o in range(r, r + rows))
            ]
        if not row_options:
            return
        travel = width + len(sprite.frames[0][0])
        if self._dist_bounds is not None:
            lo, hi = self._dist_bounds
            spawn_at = max(1, int(self._rng.uniform(lo, hi) * travel))
        else:
            threshold = int(self._rng.uniform(1 / 8, 1 / 3) * travel)
            spawn_at = max(
                1, threshold, self._switch_seconds * TICKS_PER_SECOND
            )
        self._walkers.append(
            Walker(
                name=name,
                sprite=sprite,
                row=self._rng.choice(row_options),
                rows=rows,
                spawn_tick=self._tick_count,
                spawn_at=spawn_at,
            )
        )

    def _next_name(self, taken: set[str]) -> str | None:
        """Return a playlist name that is not currently walking.

        Names come from a shuffled bag so replays stay spread out; names
        still on screen are dropped from the bag until the next reshuffle.
        Returns ``None`` when every roster name is already on screen.
        """
        if all(n in taken for n in self._names):
            return None
        while True:
            if not self._bag:
                self._bag = shuffle_order(
                    self._names, self._rng, avoid=self._last_name
                )
            name = self._bag.pop(0)
            if name not in taken:
                self._last_name = name
                return name

    def _paint(self) -> None:
        """Rebuild the whole canvas: one walker owns each row it spans."""
        width = max(1, self.size.width)
        height = max(1, self.size.height)
        by_row: dict[int, tuple[list[tuple[str, str]], int]] = {}
        for w in self._walkers:
            elapsed = self._tick_count - w.spawn_tick
            frame = w.sprite.frames[
                (elapsed // _FRAME_EVERY) % len(w.sprite.frames)
            ]
            rendered = render_rows(frame, w.sprite.palette)
            x = walk_x(elapsed, width, len(frame[0]))
            for offset, cells in enumerate(rendered):
                by_row.setdefault(w.row + offset, (cells, x))
        out = Text()
        for row_no in range(height):
            if row_no:
                out.append("\n")
            hit = by_row.get(row_no)
            if hit is None:
                continue
            cells, x = hit
            # visible sprite columns: clip against both screen edges so a
            # half-entered / half-exited sprite never widens the canvas
            x0 = max(x, 0)
            x1 = min(x + len(cells), width)
            if x0 >= x1:
                continue
            if x0:
                out.append(" " * x0)
            for glyph, style in cells[x0 - x : x1 - x]:
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
