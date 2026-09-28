"""Screensaver character registry: name -> sprite frames + palette.

All 27 characters are original approximations drawn for yate (homage, not
copies of game assets) -- see the fancy_sym plan for the attribution.
Every character carries >= 2 animation frames with uniform geometry;
invariants are re-checked at import by :func:`_validate` so a typo in a
bitmap module fails fast instead of rendering garbage.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from yate.editor_sprites.render import Frame, Palette

from .chars import (
    bomberman,
    caine,
    coin,
    digdug,
    duck,
    fireflower,
    frog,
    galaga,
    ghost,
    gangle,
    goomba,
    iceclimber,
    jax,
    link,
    mario,
    megaman,
    mushroom,
    pacman,
    pomni,
    ragatha,
    samus,
    slime,
    snake,
    star,
)


@dataclass(frozen=True)
class Sprite:
    """One screensaver character: ordered animation frames plus palette."""

    frames: tuple[Frame, ...]
    palette: Palette


#: Registered characters in playlist order (mario group first, then the
#: arcade / FC-hero / Digital-Circus / original groups -- plan §4.4).
CHARACTERS: dict[str, Sprite] = {
    "mario": Sprite(frames=mario.FRAMES, palette=mario.PALETTE),
    "goomba": Sprite(frames=goomba.FRAMES, palette=goomba.PALETTE),
    "mushroom": Sprite(frames=mushroom.FRAMES, palette=mushroom.PALETTE),
    "star": Sprite(frames=star.FRAMES, palette=star.PALETTE),
    "coin": Sprite(frames=coin.FRAMES, palette=coin.PALETTE),
    "fire_flower": Sprite(frames=fireflower.FRAMES, palette=fireflower.PALETTE),
    "pacman": Sprite(frames=pacman.FRAMES, palette=pacman.PALETTE),
    "ghost_blinky": Sprite(
        frames=ghost.FRAMES, palette=ghost.palette("#ff2b2b")
    ),
    "ghost_pinky": Sprite(
        frames=ghost.FRAMES, palette=ghost.palette("#ff9dd6")
    ),
    "ghost_inky": Sprite(
        frames=ghost.FRAMES, palette=ghost.palette("#00e5e5")
    ),
    "ghost_clyde": Sprite(
        frames=ghost.FRAMES, palette=ghost.palette("#ffa500")
    ),
    "galaga_ship": Sprite(frames=galaga.FRAMES, palette=galaga.PALETTE),
    "megaman": Sprite(frames=megaman.FRAMES, palette=megaman.PALETTE),
    "bomberman": Sprite(frames=bomberman.FRAMES, palette=bomberman.PALETTE),
    "samus": Sprite(frames=samus.FRAMES, palette=samus.PALETTE),
    "link": Sprite(frames=link.FRAMES, palette=link.PALETTE),
    "ice_climber": Sprite(
        frames=iceclimber.FRAMES, palette=iceclimber.PALETTE
    ),
    "dig_dug": Sprite(frames=digdug.FRAMES, palette=digdug.PALETTE),
    "pomni": Sprite(frames=pomni.FRAMES, palette=pomni.PALETTE),
    "jax": Sprite(frames=jax.FRAMES, palette=jax.PALETTE),
    "ragatha": Sprite(frames=ragatha.FRAMES, palette=ragatha.PALETTE),
    "caine": Sprite(frames=caine.FRAMES, palette=caine.PALETTE),
    "gangle": Sprite(frames=gangle.FRAMES, palette=gangle.PALETTE),
    "duck": Sprite(frames=duck.FRAMES, palette=duck.PALETTE),
    "snake": Sprite(frames=snake.FRAMES, palette=snake.PALETTE),
    "frog": Sprite(frames=frog.FRAMES, palette=frog.PALETTE),
    "slime": Sprite(frames=slime.FRAMES, palette=slime.PALETTE),
}


def character_names() -> tuple[str, ...]:
    """Return every registered character name in playlist order."""
    return tuple(CHARACTERS)


def get_character(name: str) -> Sprite:
    """Return the sprite registered under *name*.

    Raises ``KeyError`` for unknown names; callers accepting user input
    (the yaterc ``characters`` whitelist) validate against
    :func:`character_names` first.
    """
    if name not in CHARACTERS:
        raise KeyError(f"unknown screensaver character: {name}")
    return CHARACTERS[name]


#: Rejection-sampling budget for :func:`shuffle_order` (PR #33 review).
#: The pigeonhole guard only proves a valid order *exists*; whether
#: random shuffles actually hit one depends on the multiset.  With a
#: per-shuffle hit rate ``p``, the odds of *N* retries all failing are
#: ``(1 - p) ** N`` -- exponential decay, so a budget buys most of its
#: safety early.  Bags here are small rc-whitelist rosters, so whenever a
#: solution exists ``p`` is realistically >= ~1%, which puts the residual
#: failure odds after 1000 retries around 4e-5 (~1 in 23k refills); the
#: live call chain cannot even reach multisets (screensaver names are
#: deduplicated first), making the cap purely defensive.  Raising it
#: only inflates the worst-case retry time for no observable gain; on
#: exhaustion the caller degrades to the original order, whose sole
#: consequence is a cosmetic adjacent repeat -- never a hang.
_REJECTION_RETRIES: int = 1000


def shuffle_order(
    names: Sequence[str], rng: random.Random, *, avoid: str | None = None
) -> list[str]:
    """Return *names* shuffled, with no adjacent duplicates.

    Used for the screensaver playlist: *avoid* is the character shown
    right before this draw (the previous cycle's last entry), so a
    reshuffle never replays it first.  For the built-in roster (all
    entries distinct) a plain shuffle already has no adjacent duplicates,
    so the first draw succeeds.  Three multisets are returned as-is
    because no amount of shuffling can satisfy the constraints: a single
    distinct name can never avoid a replay; when the most frequent name
    exceeds ``(len(names) + 1) // 2`` adjacent duplicates are unavoidable
    (pigeonhole); and rejection sampling is capped at
    ``_REJECTION_RETRIES`` (PR #33 review) because a barely-satisfiable
    multiset can have a tiny hit rate -- the function degrades to the
    original order instead of stalling the spawn tick.
    """
    if len(set(names)) < 2:
        return list(names)
    counts = Counter(names)
    if max(counts.values()) > (len(names) + 1) // 2:
        # pigeonhole: no adjacency-free arrangement exists, so retrying
        # would loop forever -- give up on the constraint instead
        return list(names)
    for _ in range(_REJECTION_RETRIES):
        order = list(names)
        rng.shuffle(order)
        if avoid is not None and order and order[0] == avoid:
            continue
        if all(a != b for a, b in zip(order, order[1:])):
            return order
    # budget exhausted: a valid order exists but is too rare to hit --
    # degrade to the original order rather than stall the spawn tick
    # (residual-odds math on _REJECTION_RETRIES; PR #33 review)
    return list(names)


def _validate() -> None:
    """Fail fast on malformed bitmap data at import time."""
    for name, sprite in CHARACTERS.items():
        if len(sprite.frames) < 2:
            raise ValueError(f"{name}: needs at least 2 animation frames")
        widths = {len(row) for frame in sprite.frames for row in frame}
        heights = {len(frame) for frame in sprite.frames}
        if len(widths) != 1 or len(heights) != 1:
            raise ValueError(
                f"{name}: ragged frames (widths={sorted(widths)}, "
                f"heights={sorted(heights)})"
            )
        keys = set(sprite.palette)
        for frame in sprite.frames:
            for row in frame:
                unknown = set(row) - keys - {"."}
                if unknown:
                    raise ValueError(
                        f"{name}: unknown palette keys {sorted(unknown)}"
                    )


_validate()
