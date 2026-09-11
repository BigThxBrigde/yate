"""Color themes and cell-width helpers for editor_view (Rich / Textual).

The built-in theme family is `Catppuccin <https://catppuccin.com/>`_ with its
four flavors (``latte`` light, ``frappe`` / ``macchiato`` / ``mocha`` dark,
``mocha`` being the default).  A theme bundles both the chrome colors
(backgrounds, bars, selection) and the syntax token palette consumed by
:mod:`yate.editor_view.highlight`.

Cell helpers (:func:`cell_width`, :func:`char_to_cell`, ...) are theme
independent and live at the bottom of this module.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from rich.style import Style

# ---------------------------------------------------------------------------
# Syntax token kinds (produced by highlight.py)
# ---------------------------------------------------------------------------

#: Token kind -> syntax attribute name on :class:`Theme`.
SYNTAX_KINDS: dict[str, str] = {
    "keyword": "syn_keyword",
    "string": "syn_string",
    "number": "syn_number",
    "comment": "syn_comment",
    "function": "syn_function",
    "type": "syn_type",
    "constant": "syn_constant",
    "builtin": "syn_builtin",
    "decorator": "syn_decorator",
    "operator": "syn_operator",
    "property": "syn_property",
    "heading": "syn_keyword",
    "link": "syn_function",
    "emphasis": "fg_bright",
}


@dataclass(frozen=True)
class Theme:
    """A complete color scheme: chrome colors plus a syntax palette."""

    name: str
    label: str
    dark: bool

    # backgrounds
    bg: str               # editor background
    panel: str            # tab bar / side bar / status bar background
    surface: str          # current line / inputs
    gutter_bg: str        # line number gutter
    border: str           # subtle separators

    # overlays
    selection_bg: str
    match_bg: str
    match_active_bg: str
    on_accent: str        # text color drawn on top of accent chips/matches

    # foregrounds
    fg: str
    fg_dim: str           # comments / muted
    fg_muted: str         # secondary text
    fg_bright: str        # emphasis text

    # accents
    accent: str           # primary (blue)
    accent2: str          # secondary (mauve/purple)
    green: str
    yellow: str
    red: str
    orange: str

    # mode chips (status bar)
    mode_normal_bg: str
    mode_insert_bg: str
    mode_visual_bg: str
    mode_command_bg: str

    # syntax palette (Catppuccin mapping)
    syn_keyword: str
    syn_string: str
    syn_number: str
    syn_comment: str
    syn_function: str
    syn_type: str
    syn_constant: str
    syn_builtin: str
    syn_decorator: str
    syn_operator: str
    syn_property: str

    #: extra free-form metadata (reserved for user themes)
    extra: dict[str, str] = field(default_factory=dict[str, str])

    def syntax_color(self, kind: str) -> Optional[str]:
        """Return the hex color for a highlight token ``kind`` (``None`` if
        the kind should be drawn with the default foreground)."""
        attr = SYNTAX_KINDS.get(kind)
        return getattr(self, attr) if attr is not None else None

    def syntax_style(self, kind: str, bgcolor: Optional[str] = None) -> Style:
        """Rich :class:`~rich.style.Style` for a highlight token kind.

        Comments are rendered italic in addition to their dim color.
        """
        color = self.syntax_color(kind)
        return Style(
            color=color if color is not None else self.fg,
            bgcolor=bgcolor,
            italic=(kind == "comment"),
        )


# ---------------------------------------------------------------------------
# Catppuccin flavor palettes
# (https://github.com/catppuccin/catppuccin#-palettes)
# ---------------------------------------------------------------------------

def _catppuccin(name: str, label: str, dark: bool, p: dict[str, str]) -> Theme:
    """Build a Catppuccin :class:`Theme` from the raw flavor palette *p*."""
    on_accent = p["crust"] if dark else "#FFFFFF"
    return Theme(
        name=name,
        label=label,
        dark=dark,
        bg=p["base"],
        panel=p["mantle"],
        surface=p["surface0"],
        gutter_bg=p["base"],
        border=p["surface1"],
        selection_bg=p["surface2"],
        match_bg=p["yellow"],
        match_active_bg=p["peach"],
        on_accent=on_accent,
        fg=p["text"],
        fg_dim=p["overlay0"],
        fg_muted=p["overlay1"],
        fg_bright=p["subtext1"],
        accent=p["blue"],
        accent2=p["mauve"],
        green=p["green"],
        yellow=p["yellow"],
        red=p["red"],
        orange=p["peach"],
        mode_normal_bg=p["blue"],
        mode_insert_bg=p["green"],
        mode_visual_bg=p["mauve"],
        mode_command_bg=p["peach"],
        syn_keyword=p["mauve"],
        syn_string=p["green"],
        syn_number=p["peach"],
        syn_comment=p["overlay0"],
        syn_function=p["blue"],
        syn_type=p["yellow"],
        syn_constant=p["peach"],
        syn_builtin=p["red"],
        syn_decorator=p["pink"],
        syn_operator=p["sky"],
        syn_property=p["lavender"],
    )


_LATTE = {
    "rosewater": "#dc8a78", "flamingo": "#dd7878", "pink": "#ea76cb",
    "mauve": "#8839ef", "red": "#d20f39", "maroon": "#e64553",
    "peach": "#fe640b", "yellow": "#df8e1d", "green": "#40a02b",
    "teal": "#179299", "sky": "#04a5e5", "sapphire": "#209fb5",
    "blue": "#1e66f5", "lavender": "#7287fd", "text": "#4c4f69",
    "subtext1": "#5c5f77", "subtext0": "#6c6f85", "overlay2": "#7c7f93",
    "overlay1": "#8c8fa1", "overlay0": "#9ca0b0", "surface2": "#acb0be",
    "surface1": "#bcc0cc", "surface0": "#ccd0da", "base": "#eff1f5",
    "mantle": "#e6e9ef", "crust": "#dce0e8",
}

_FRAPPE = {
    "rosewater": "#f2d5cf", "flamingo": "#eebebe", "pink": "#f4b8e4",
    "mauve": "#ca9ee6", "red": "#e78284", "maroon": "#ea999c",
    "peach": "#ef9f76", "yellow": "#e5c890", "green": "#a6d189",
    "teal": "#81c8be", "sky": "#99d1db", "sapphire": "#85c1dc",
    "blue": "#8caaee", "lavender": "#babbf1", "text": "#c6d0f5",
    "subtext1": "#b5bfe2", "subtext0": "#a5adce", "overlay2": "#949cbb",
    "overlay1": "#838ba7", "overlay0": "#737994", "surface2": "#626880",
    "surface1": "#51576d", "surface0": "#414559", "base": "#303446",
    "mantle": "#292c3c", "crust": "#232634",
}

_MACCHIATO = {
    "rosewater": "#f4dbd6", "flamingo": "#f0c6c6", "pink": "#f5bde6",
    "mauve": "#c6a0f6", "red": "#ed8796", "maroon": "#ee99a0",
    "peach": "#f5a97f", "yellow": "#eed49f", "green": "#a6da95",
    "teal": "#8bd5ca", "sky": "#91d7e3", "sapphire": "#7dc4e4",
    "blue": "#8aadf4", "lavender": "#b7bdf8", "text": "#cad3f5",
    "subtext1": "#b8c0e0", "subtext0": "#a5adcb", "overlay2": "#939ab7",
    "overlay1": "#8087a2", "overlay0": "#6e738d", "surface2": "#5b6078",
    "surface1": "#494d64", "surface0": "#363a4f", "base": "#24273a",
    "mantle": "#1e2030", "crust": "#181926",
}

_MOCHA = {
    "rosewater": "#f5e0dc", "flamingo": "#f2cdcd", "pink": "#f5c2e7",
    "mauve": "#cba6f7", "red": "#f38ba8", "maroon": "#eba0ac",
    "peach": "#fab387", "yellow": "#f9e2af", "green": "#a6e3a1",
    "teal": "#94e2d5", "sky": "#89dceb", "sapphire": "#74c7ec",
    "blue": "#89b4fa", "lavender": "#b4befe", "text": "#cdd6f4",
    "subtext1": "#bac2de", "subtext0": "#a6adc8", "overlay2": "#9399b2",
    "overlay1": "#7f849c", "overlay0": "#6c7086", "surface2": "#585b70",
    "surface1": "#45475a", "surface0": "#313244", "base": "#1e1e2e",
    "mantle": "#181825", "crust": "#11111b",
}

THEMES: dict[str, Theme] = {
    "latte": _catppuccin("latte", "Catppuccin Latte", False, _LATTE),
    "frappe": _catppuccin("frappe", "Catppuccin Frappé", True, _FRAPPE),
    "macchiato": _catppuccin("macchiato", "Catppuccin Macchiato", True, _MACCHIATO),
    "mocha": _catppuccin("mocha", "Catppuccin Mocha", True, _MOCHA),
}

DEFAULT_THEME = "mocha"

_active: Theme = THEMES[DEFAULT_THEME]


def active() -> Theme:
    """Return the currently active :class:`Theme`."""
    return _active


def set_theme(name: str) -> Theme:
    """Switch the active theme by name.

    :raises KeyError: if no theme called *name* is registered.
    """
    # The active theme is intentionally process-global state (like vim's
    # colorscheme): every widget reads it through :func:`active`.
    global _active
    if name not in THEMES:
        raise KeyError(f"unknown theme: {name!r} (have: {', '.join(sorted(THEMES))})")
    _active = THEMES[name]
    return _active


def available() -> list[str]:
    """Names of all registered themes."""
    return sorted(THEMES)


def register_theme(theme: Theme) -> None:
    """Register a user-defined :class:`Theme` (e.g. loaded from yaterc)."""
    THEMES[theme.name] = theme


# ---------------------------------------------------------------------------
# Custom theme files / theme directories
# ---------------------------------------------------------------------------

#: Files already exec'd this process; a theme file reached through several
#: sources (rc dir, default dir, --theme-dir) must run once to avoid
#: re-registering the same themes repeatedly.
_loaded_theme_files: set[Path] = set()


def _theme_namespace() -> dict[str, Any]:
    """Globals injected into an external theme file."""
    return {
        "__name__": "__yatetheme__",
        "Theme": Theme,
        "register_theme": register_theme,
    }


def load_theme_file(path: Path | str) -> Optional[str]:
    """Exec one ``*.py`` theme file.

    The file may call :func:`register_theme` any number of times; regular
    ``import`` statements work as usual.  Returns ``None`` on success or a
    human-readable error string; a broken theme file never raises.
    """
    path = Path(path)
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    if resolved in _loaded_theme_files:
        return None
    try:
        source = path.read_text(encoding="utf-8")
        code = compile(source, str(path), "exec")
        # Theme files are user-authored Python executed by design.
        exec(code, _theme_namespace())  # noqa: S102 - intentional theme exec
    except Exception as exc:  # noqa: BLE001 - theme errors must not crash yate
        return f"{type(exc).__name__}: {exc}"
    _loaded_theme_files.add(resolved)
    return None


def load_theme_paths(
    paths: list[Path] | list[str] | Sequence[Path] | Sequence[str],
    errors: list[str],
) -> None:
    """Load custom themes from the given files and/or directories.

    Each entry is either a directory (every non-underscore ``*.py`` inside
    is loaded in name order) or a single ``*.py`` theme file.  Missing
    paths are skipped silently (they are usually optional default
    locations); broken files record a ``"<path>: <problem>"`` error
    instead of raising.  Later files override earlier ones when they
    register a theme of the same name.
    """
    for raw in paths:
        folder = Path(raw)
        if folder.is_dir():
            for path in sorted(folder.glob("*.py")):
                if path.name.startswith("_"):
                    continue
                problem = load_theme_file(path)
                if problem is not None:
                    errors.append(f"{path}: {problem}")
        elif folder.is_file():
            problem = load_theme_file(folder)
            if problem is not None:
                errors.append(f"{folder}: {problem}")


# ---------------------------------------------------------------------------
# Cell geometry helpers (theme independent)
# ---------------------------------------------------------------------------

def cell_width(ch: str) -> int:
    """Terminal cell width of *ch* (0 combining, 2 wide CJK/emoji, 1 else)."""
    if ch == "\t":
        return 1
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def cell_len(text: str) -> int:
    """Display cell length of *text* (wide glyphs count 2, combining 0)."""
    return sum(1 if ch == "\t" else cell_width(ch) for ch in text)


def truncate_to_cells(text: str, max_cells: int) -> str:
    """Truncate *text* to at most *max_cells* display cells."""
    if max_cells <= 0:
        return ""
    out: list[str] = []
    cells = 0
    for ch in text:
        w = 1 if ch == "\t" else cell_width(ch)
        if cells + w > max_cells:
            break
        out.append(ch)
        cells += w
    return "".join(out)


def char_to_cell(line: str, char_index: int, tab_width: int = 4) -> int:
    """Map a character index to its display cell column."""
    cells = 0
    for i, ch in enumerate(line):
        if i >= char_index:
            break
        if ch == "\t":
            cells += tab_width - (cells % tab_width)
        else:
            cells += max(1, cell_width(ch))
    return cells


def cell_to_char(line: str, cell: int, tab_width: int = 4) -> int:
    """Map a display *cell* column back to a character index."""
    cells = 0
    for i, ch in enumerate(line):
        if cells >= cell:
            return i
        if ch == "\t":
            cells += tab_width - (cells % tab_width)
        else:
            cells += max(1, cell_width(ch))
    return len(line)


def expand_char(ch: str, cells: list[str], tab_width: int) -> None:
    """Append *ch* to *cells* with tabs expanded / wide glyphs doubled."""
    if ch == "\t":
        cells.extend([" "] * (tab_width - (len(cells) % tab_width)))
        return
    w = cell_width(ch)
    if w == 0 and cells:  # combining mark attaches to previous cell
        cells[-1] += ch
    elif w == 2:
        cells.append(ch)
        cells.append("")
    else:
        cells.append(ch)
