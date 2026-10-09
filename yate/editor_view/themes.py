"""Color themes for editor_view: the Theme class, palettes and the registry.

Eight built-in themes ship in :data:`THEMES`:

* the four `Catppuccin <https://catppuccin.com/>`_ flavors (``latte`` light,
  ``frappe`` / ``macchiato`` / ``mocha`` dark, ``mocha`` being the default);
* Atom One Dark / One Light (``onedark`` / ``onelight``);
* `Gruvbox <https://github.com/morhetz/gruvbox>`_ dark / light medium
  (``gruvbox-dark`` / ``gruvbox-light``).

Official theme *templates* (Dracula, Ayu) are additionally shipped under
``yate/resources/theme_examples/`` as ``*.example`` files; they never
register themselves and only become themes once a user copies them to a
scanned theme directory as ``*.py``.

A theme bundles both the chrome colors (backgrounds, bars, selection) and the
syntax token palette consumed by the :mod:`yate.editor_syntax` layer.

Custom themes registered through :func:`register_theme` are strictly validated
by :func:`validate_theme` (every color must parse, opaque fields must be fully
opaque); the same rules are enforced again by :func:`to_textual_theme`, which
bridges a yate :class:`Theme` into a Textual theme (named ``yate-<name>``) so
every overlay's design tokens match the active yate palette.

The *active* theme singleton and the theme-change broadcast live in
:mod:`yate.editor_view.theme` (the facade); this module holds only the
theme data and validation.  Split from that module (big-module-split
wave d); the character geometry helpers live in
:mod:`yate.editor_view.cells`, the custom theme file loader in
:mod:`yate.editor_view.theme_files`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rich.style import Style
from textual.color import Color as TextualColor
from textual.theme import Theme as TextualTheme

from yate.editor_syntax.tokens import SYNTAX_KINDS

__all__ = [
    "DEFAULT_THEME",
    "TEXTUAL_THEME_PREFIX",
    "THEMES",
    "Theme",
    "available",
    "register_theme",
    "textual_theme_name",
    "to_textual_theme",
    "validate_theme",
]


# ---------------------------------------------------------------------------
# Syntax palette
# ---------------------------------------------------------------------------


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

    def syntax_color(self, kind: str) -> str | None:
        """Return the hex color for a highlight token ``kind`` (``None`` if
        the kind should be drawn with the default foreground)."""
        attr = SYNTAX_KINDS.get(kind)
        return getattr(self, attr) if attr is not None else None

    def syntax_style(self, kind: str, bgcolor: str | None = None) -> Style:
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


_LATTE: dict[str, str] = {
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

_FRAPPE: dict[str, str] = {
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

_MACCHIATO: dict[str, str] = {
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

_MOCHA: dict[str, str] = {
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

# ---------------------------------------------------------------------------
# Atom One Dark / One Light palettes
# (https://github.com/atom/atom/tree/master/packages/one-dark-syntax)
#
# Each palette only carries raw upstream colors; _one_family maps them onto
# the Theme semantic slots. Slots without a direct upstream color are derived
# from family semantics (gutter uses the editor background; inactive/active
# find matches use yellow/orange with on_accent as the overlaid text color;
# mode chips reuse blue/green/purple/orange).
# ---------------------------------------------------------------------------


def _one_family(name: str, label: str, dark: bool, p: dict[str, str]) -> Theme:
    """Build an Atom One :class:`Theme` from the raw palette *p*."""
    return Theme(
        name=name,
        label=label,
        dark=dark,
        bg=p["bg"],
        panel=p["panel"],
        surface=p["surface"],
        gutter_bg=p["bg"],
        border=p["border"],
        selection_bg=p["selection"],
        match_bg=p["yellow"],
        match_active_bg=p["orange"],
        on_accent=p["on_accent"],
        fg=p["fg"],
        fg_dim=p["fg_dim"],
        fg_muted=p["fg_muted"],
        fg_bright=p["fg_bright"],
        accent=p["blue"],
        accent2=p["purple"],
        green=p["green"],
        yellow=p["yellow"],
        red=p["red"],
        orange=p["orange"],
        mode_normal_bg=p["blue"],
        mode_insert_bg=p["green"],
        mode_visual_bg=p["purple"],
        mode_command_bg=p["orange"],
        syn_keyword=p["purple"],
        syn_string=p["green"],
        syn_number=p["orange"],
        syn_comment=p["fg_dim"],
        syn_function=p["blue"],
        syn_type=p["yellow"],
        syn_constant=p["orange"],
        syn_builtin=p["red"],
        syn_decorator=p["cyan"],
        syn_operator=p["cyan"],
        syn_property=p["red"],
    )


_ONE_DARK: dict[str, str] = {
    "bg": "#282c34", "panel": "#21252b", "surface": "#2c313a",
    "border": "#3a3f4b", "selection": "#3e4451",
    "fg": "#abb2bf", "fg_dim": "#5c6370", "fg_muted": "#636d83",
    "fg_bright": "#c8ccd4",
    "blue": "#61afef", "purple": "#c678dd", "green": "#98c379",
    "yellow": "#e5c07b", "red": "#e06c75", "orange": "#d19a66",
    "cyan": "#56b6c2", "on_accent": "#282c34",
}

_ONE_LIGHT: dict[str, str] = {
    "bg": "#fafafa", "panel": "#f0f0f1", "surface": "#f0f0f1",
    "border": "#d4d4d4", "selection": "#e5e5e6",
    "fg": "#383a42", "fg_dim": "#a0a1a7", "fg_muted": "#696c77",
    "fg_bright": "#23252b",
    "blue": "#4078f2", "purple": "#a626a4", "green": "#50a14f",
    "yellow": "#c18401", "red": "#e45649", "orange": "#986801",
    "cyan": "#0184bc", "on_accent": "#ffffff",
}

# ---------------------------------------------------------------------------
# Gruvbox dark/light medium palettes
# (https://github.com/morhetz/gruvbox#palette)
#
# Same raw-palette + family-factory pattern as the One themes. Keyword/string/
# number follow the gruvbox Vim highlight groups (red/green/purple); find
# matches use neutral yellow/orange.
# ---------------------------------------------------------------------------


def _gruvbox(name: str, label: str, dark: bool, p: dict[str, str]) -> Theme:
    """Build a Gruvbox :class:`Theme` from the raw palette *p*."""
    return Theme(
        name=name,
        label=label,
        dark=dark,
        bg=p["bg"],
        panel=p["panel"],
        surface=p["surface"],
        gutter_bg=p["bg"],
        border=p["border"],
        selection_bg=p["selection"],
        match_bg=p["yellow"],
        match_active_bg=p["orange"],
        on_accent=p["on_accent"],
        fg=p["fg"],
        fg_dim=p["fg_dim"],
        fg_muted=p["fg_muted"],
        fg_bright=p["fg_bright"],
        accent=p["blue"],
        accent2=p["purple"],
        green=p["green"],
        yellow=p["yellow"],
        red=p["red"],
        orange=p["orange"],
        mode_normal_bg=p["blue"],
        mode_insert_bg=p["green"],
        mode_visual_bg=p["purple"],
        mode_command_bg=p["orange"],
        syn_keyword=p["red"],
        syn_string=p["green"],
        syn_number=p["purple"],
        syn_comment=p["fg_dim"],
        syn_function=p["green"],
        syn_type=p["yellow"],
        syn_constant=p["orange"],
        syn_builtin=p["orange"],
        syn_decorator=p["aqua"],
        syn_operator=p["orange"],
        syn_property=p["aqua"],
    )


_GRUVBOX_DARK: dict[str, str] = {
    "bg": "#282828", "panel": "#3c3836", "surface": "#3c3836",
    "border": "#504945", "selection": "#504945",
    "fg": "#ebdbb2", "fg_dim": "#928374", "fg_muted": "#a89984",
    "fg_bright": "#fbf1c7",
    "blue": "#83a598", "purple": "#d3869b", "green": "#b8bb26",
    "aqua": "#8ec07c", "yellow": "#fabd2f", "red": "#fb4934",
    "orange": "#fe8019", "on_accent": "#282828",
}

_GRUVBOX_LIGHT: dict[str, str] = {
    "bg": "#fbf1c7", "panel": "#ebdbb2", "surface": "#ebdbb2",
    "border": "#d5c4a1", "selection": "#d5c4a1",
    "fg": "#3c3836", "fg_dim": "#7c6f64", "fg_muted": "#665c54",
    "fg_bright": "#282828",
    "blue": "#076678", "purple": "#8f3f71", "green": "#79740e",
    "aqua": "#427b58", "yellow": "#b57614", "red": "#9d0006",
    "orange": "#af3a03", "on_accent": "#fbf1c7",
}

#: The built-in themes, keyed by name (``mocha`` is :data:`DEFAULT_THEME`).
THEMES: dict[str, Theme] = {
    "latte": _catppuccin("latte", "Catppuccin Latte", False, _LATTE),
    "frappe": _catppuccin("frappe", "Catppuccin Frappé", True, _FRAPPE),
    "macchiato": _catppuccin("macchiato", "Catppuccin Macchiato", True, _MACCHIATO),
    "mocha": _catppuccin("mocha", "Catppuccin Mocha", True, _MOCHA),
    "onedark": _one_family("onedark", "One Dark", True, _ONE_DARK),
    "onelight": _one_family("onelight", "One Light", False, _ONE_LIGHT),
    "gruvbox-dark": _gruvbox("gruvbox-dark", "Gruvbox Dark", True, _GRUVBOX_DARK),
    "gruvbox-light": _gruvbox("gruvbox-light", "Gruvbox Light", False, _GRUVBOX_LIGHT),
}

#: Name of the theme active before any :func:`yate.editor_view.theme.set_theme`.
DEFAULT_THEME: str = "mocha"


def available() -> list[str]:
    """Names of all registered themes."""
    return sorted(THEMES)


def register_theme(theme: Theme) -> None:
    """Register a user-defined :class:`Theme` (e.g. loaded from yaterc).

    :raises ValueError: if *theme* fails :func:`validate_theme` (malformed
        name, non-bool ``dark``, unparseable color, translucent opaque field,
        ...).  Built-in themes constructed directly in :data:`THEMES` bypass
        this check; only themes funneled through this function (i.e. custom
        user themes from yaterc / ``--theme-dir``) are validated.

    Note: this only fills :data:`THEMES` -- the *active* theme singleton and
    its broadcast stay owned by :mod:`yate.editor_view.theme`.
    """
    problems = validate_theme(theme)
    if problems:
        raise ValueError(
            f"invalid theme {theme.name!r}: {'; '.join(problems)}"
        )
    THEMES[theme.name] = theme


# ---------------------------------------------------------------------------
# Textual theme bridge
#
# yate keeps its own frozen ``Theme`` palette (chrome + syntax); Textual's
# app-global design tokens (``$primary``, ``$surface``, ``$text-muted`` …)
# drive every overlay's frame chrome.  ``to_textual_theme`` bridges the two:
# one Textual theme per yate theme (named ``yate-<name>``) is registered with
# the app at startup, so the app stays permanently on a yate-derived Textual
# theme and every overlay matches yate with zero per-screen switching.
# ---------------------------------------------------------------------------

#: Prefix for every bridged Textual theme name (``yate-mocha``, ...).
TEXTUAL_THEME_PREFIX: str = "yate-"


def textual_theme_name(name: str) -> str:
    """Return the Textual theme name for the yate theme called *name*."""
    return f"{TEXTUAL_THEME_PREFIX}{name}"


#: yate ``Theme`` color fields the bridge maps into Textual.  Order is
#: irrelevant; the tuple doubles as an exhaustive iterable for validation.
_MAPPED_COLOR_FIELDS: tuple[str, ...] = (
    "bg", "panel", "surface", "fg", "fg_dim", "fg_muted", "fg_bright",
    "accent", "accent2", "green", "yellow", "red", "orange",
)

#: Subset of :data:`_MAPPED_COLOR_FIELDS` that must be fully opaque (alpha
#: == 1.0) so modal dim/backdrop and overlay bodies composite predictably.
_OPAQUE_FIELDS: tuple[str, ...] = ("bg", "panel", "surface", "fg")

#: Regex for the generated doc-hit ``<hex> <percent>`` variables.
_DOC_HIT_RE: re.Pattern[str] = re.compile(
    r"^(#[0-9a-fA-F]{6})\s+(\d{1,3})(?:%)?\s*$"
)


def validate_theme(t: Theme) -> list[str]:
    """Return a list of human-readable problems with *t* (empty = valid).

    Checks exactly the fields the Textual bridge consumes:

    1. ``name`` is a non-empty ``str``;
    2. ``dark`` is a ``bool``;
    3. every color in :data:`_MAPPED_COLOR_FIELDS` parses as a Textual color;
       the :data:`_OPAQUE_FIELDS` subset must additionally be fully opaque;
    4. the two doc-hit ``<hex> <percent>`` variables in ``t.extra``, when
       present, must be well-formed (``#rrggbb`` + ``0-100``).

    Returns the problems so callers (``register_theme``) can raise once with
    every issue listed; built-in themes are constructed directly in
    :data:`THEMES` and never pass through this helper.
    """
    problems: list[str] = []

    # Theme is a frozen dataclass with typed annotations, but custom themes
    # are user-authored Python -- runtime values may violate the annotations
    # (e.g. dark="yes"), so the isinstance checks are intentional even
    # though pyright considers them unnecessary based on the declared types.
    if not isinstance(t.name, str) or not t.name:  # pyright: ignore[reportUnnecessaryIsInstance]
        problems.append("name must be a non-empty str")
    if not isinstance(t.dark, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
        problems.append("dark must be a bool")

    for field_name in _MAPPED_COLOR_FIELDS:
        value = getattr(t, field_name, None)
        if not isinstance(value, str) or not value:  # pyright: ignore[reportUnnecessaryIsInstance]
            problems.append(f"{field_name} must be a non-empty color str")
            continue
        try:
            parsed = TextualColor.parse(value)
        except Exception:  # noqa: BLE001 - reported via the problems list
            problems.append(f"{field_name}={value!r} is not a valid color")
            continue
        if field_name in _OPAQUE_FIELDS and parsed.a != 1.0:
            problems.append(
                f"{field_name}={value!r} must be fully opaque "
                f"(alpha 1.0, got {parsed.a})"
            )

    for key in ("doc-hit-background", "doc-hit-current-background"):
        if key not in t.extra:
            continue
        value = t.extra[key]
        match = (
            _DOC_HIT_RE.match(value)
            # runtime value may violate the declared type (see note above)
            if isinstance(value, str)  # pyright: ignore[reportUnnecessaryIsInstance]
            else None
        )
        if match is None:
            problems.append(
                f"extra[{key!r}]={value!r} must be '<hex> <percent>'"
            )
            continue
        hex_part, pct_part = match.group(1), match.group(2)
        try:
            TextualColor.parse(hex_part)
        except Exception:  # noqa: BLE001 - reported via the problems list
            problems.append(
                f"extra[{key!r}]={value!r}: hex part is not a valid color"
            )
        pct = int(pct_part)
        if not 0 <= pct <= 100:
            problems.append(
                f"extra[{key!r}]={value!r}: percentage out of 0-100"
            )

    return problems


def to_textual_theme(t: Theme) -> TextualTheme:
    """Build a Textual :class:`~textual.theme.Theme` from the yate *t*.

    The mapping keeps overlay frame chrome (borders, markdown headings, code
    backgrounds, search-hit tints) on the yate palette.  Raises if *t* fails
    :func:`validate_theme` -- the bridge must never feed untrusted strings to
    ``ColorSystem.generate()``, which surfaces invalid colors late and hard.
    """
    problems = validate_theme(t)
    if problems:
        raise ValueError(
            f"cannot bridge invalid theme {t.name!r}: {'; '.join(problems)}"
        )

    yellow_hex = t.yellow
    return TextualTheme(
        name=textual_theme_name(t.name),
        primary=t.accent2,        # mauve/purple -- overlay borders, md h1-h3
        secondary=t.accent,       # blue
        warning=t.yellow,
        error=t.red,
        success=t.green,
        accent=t.orange,
        foreground=t.fg,
        background=t.bg,          # also the modal dim backdrop base
        surface=t.surface,
        panel=t.panel,            # markdown code/tables
        dark=t.dark,
        variables={
            # Exact yate muted colors instead of Textual's auto alphas.
            "text": t.fg,
            "text-muted": t.fg_muted,
            "foreground-muted": t.fg_dim,
            # Search-hit tints for the manual/changelog viewer, replacing the
            # two hardcoded Mocha-yellow values in manual.py so they follow
            # the active yate theme's yellow.  ``<hex> <percent>`` is
            # Textual's CSS alpha syntax.
            "doc-hit-background": f"{yellow_hex} 12%",
            "doc-hit-current-background": f"{yellow_hex} 40%",
        },
    )
