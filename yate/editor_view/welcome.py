"""Welcome-page rows for the editor view: figlet banner, hints and footer.

Extracted from :mod:`yate.editor_view.editor` (big-module-split wave c) as
pure functions: the row builder caches its result in a caller-owned dict
keyed by (theme name, vim_keys), so the host widget keeps the cache on the
instance and the rows embed no widget state.
"""

from __future__ import annotations

from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip

from yate import __version__

from yate.editor_view import theme

# ``editor.py`` imports the private ``_WelcomeRow`` alias for its cache
# annotation; listing it in ``__all__`` keeps pyright's reportPrivateUsage
# quiet (same pattern as the wave-a private registry re-exports).
__all__ = ["_WelcomeRow", "render_welcome_row", "welcome_rows"]

# Welcome-page banner: "YATE" in the ANSI Shadow figlet style
# (generated with https://patorjk.com/software/taag/, f=ANSI Shadow).
_WELCOME_BANNER: list[str] = [
    "██╗   ██╗ █████╗ ████████╗███████╗",
    "╚██╗ ██╔╝██╔══██╗╚══██╔══╝██╔════╝",
    " ╚████╔╝ ███████║   ██║   █████╗",
    "  ╚██╔╝  ██╔══██║   ██║   ██╔══╝",
    "   ██║   ██║  ██║   ██║   ███████╗",
    "   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚══════╝",
]

#: One welcome-page row: (text, color, bold, centered) cell tuples.
_WelcomeRow = list[tuple[str, str | None, bool, bool]]


def welcome_rows(
    t: theme.Theme,
    vim_keys: bool,
    cache: dict[tuple[str, bool], list[_WelcomeRow]],
) -> list[_WelcomeRow]:
    """(text, color, bold, centered) tuples per welcome row.

    The rows embed theme colors and keymap-dependent hints, so they are
    cached per (theme name, vim_keys) in the caller-owned *cache*: the
    welcome page re-renders every frame while visible and used to rebuild
    the rows each time.  A theme or keymap switch changes the cache key and
    forces a rebuild.
    """
    key = (t.name, vim_keys)
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows: list[_WelcomeRow] = [
        [],  # row 0: keep the cursor line blank
    ]
    # pad all banner lines to the same width so the per-line centering
    # below keeps the figlet block aligned (trailing spaces were trimmed
    # from the generator output, which would otherwise shift short lines)
    banner_w = max(len(art) for art in _WELCOME_BANNER)
    for art in _WELCOME_BANNER:
        rows.append([(art.ljust(banner_w), t.green, False, True)])
    rows.append([])
    rows.append([
        ("yate ", t.accent, True, True),
        (__version__, t.fg_bright, True, True),
    ])
    rows.append([("yet another terminal editor", t.fg_dim, False, True)])
    rows.append([])
    hints: list[tuple[str, str]] = [
        ("Ctrl+P", "quick open file"),
        ("Alt+Shift+P", "command palette"),
    ]
    if vim_keys:
        # The ex command prompt (":") exists in vim mode only; in vsc
        # mode ":" is an ordinary character typed into the buffer.
        hints.append((":", "ex command prompt (:w :q :e ...)"))
    hints.extend([
        ("Ctrl+F", "find in file"),
        ("Ctrl+`", "integrated terminal"),
        ("Ctrl+S", "save file"),
        ("F1", "keyboard reference"),
    ])
    for kbd, desc in hints:
        rows.append([
            ("  " + kbd.ljust(15), t.green, True, False),
            (desc, t.fg_bright, False, False),
        ])
    rows.append([])
    footer = (
        "  start typing to edit, or :e <path> to open a file"
        if vim_keys
        else "  start typing to edit; Alt+Shift+P opens the command palette"
    )
    rows.append([(footer, t.fg_dim, False, False)])
    cache[key] = rows
    return rows


def render_welcome_row(
    y: int,
    view_w: int,
    gutter_w: int,
    t: theme.Theme,
    vim_keys: bool,
    cache: dict[tuple[str, bool], list[_WelcomeRow]],
) -> Strip:
    """Render one welcome page row (gutter stays blank, no cursor)."""
    segments: list[Segment] = [Segment(" " * gutter_w, Style(bgcolor=t.bg))]
    rows = welcome_rows(t, vim_keys, cache)
    used = gutter_w
    if y < len(rows):
        row = rows[y]
        if row and all(item[3] for item in row):
            text_w = sum(len(item[0]) for item in row)
            indent = max(0, (view_w - gutter_w - text_w) // 2)
            if indent:
                segments.append(Segment(" " * indent, Style(bgcolor=t.bg)))
                used += indent
        for text, color, bold, _centered in row:
            segments.append(Segment(text, Style(color=color, bold=bold, bgcolor=t.bg)))
            used += len(text)
    pad = view_w - used
    if pad > 0:
        segments.append(Segment(" " * pad, Style(bgcolor=t.bg)))
    return Strip(segments)
