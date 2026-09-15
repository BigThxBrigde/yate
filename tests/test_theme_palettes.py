# pyright: reportPrivateUsage=false
"""Tests for the built-in theme palettes and the shipped theme templates.

Covers:

* every built-in theme (8): complete fields, hex format, registry/name
  consistency, syntax colors for every token kind;
* ``set_theme`` switching and the unknown-theme error listing all built-ins;
* the ``*.example`` templates under ``yate/resources/theme_examples``:
  they exec under exactly the namespace the real loader injects, register the
  advertised themes, are ignored in place (glob ``*.py``), and work end to
  end once copied to ``*.py`` inside a scanned directory;
* the version bump (single-source dynamic version).
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterator
from dataclasses import fields
from importlib.resources import files
from pathlib import Path

import pytest

import yate
from yate.editor_syntax.tokens import SYNTAX_KINDS
from yate.editor_view import theme
from yate.editor_view.theme import (
    DEFAULT_THEME,
    THEMES,
    Theme,
    load_theme_paths,
    register_theme,
    set_theme,
    textual_theme_name,
    to_textual_theme,
    validate_theme,
)

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

BUILTIN_THEMES = [
    "frappe",
    "gruvbox-dark",
    "gruvbox-light",
    "latte",
    "macchiato",
    "mocha",
    "onedark",
    "onelight",
]
_BUILTIN_THEME_SET = set(BUILTIN_THEMES)

TEMPLATE_FILES = ["dracula_theme.example", "ayu_theme.example"]
TEMPLATE_THEMES = ["dracula", "ayu-dark", "ayu-mirage", "ayu-light"]

#: Theme fields that must hold a hex color (everything except identity/extra).
COLOR_FIELDS = [
    f.name
    for f in fields(Theme)
    if f.name not in ("name", "label", "dark", "extra")
]


def _examples_dir() -> Path:
    resource = files("yate.resources").joinpath("theme_examples")
    return Path(str(resource))


def _assert_well_formed(t: Theme) -> None:
    """All color fields populated with valid hex and types correct."""
    assert isinstance(t.dark, bool)
    assert isinstance(t.name, str)
    assert t.label
    for field_name in COLOR_FIELDS:
        value = getattr(t, field_name)
        assert isinstance(value, str), field_name
        assert HEX.match(value), f"{t.name}.{field_name}={value!r}"


@pytest.fixture
def builtin_baseline() -> Iterator[None]:
    """Pin the built-in registry baseline; restore extras afterwards."""
    # The registry is process-global; other test modules may register
    # throwaway themes, so pin the built-in baseline for these tests and
    # restore whatever was registered afterwards.
    extra = {
        name: THEMES.pop(name)
        for name in list(THEMES)
        if name not in _BUILTIN_THEME_SET
    }
    yield
    THEMES.update(extra)
    set_theme(DEFAULT_THEME)


# --- built-in themes --------------------------------------------------------


def test_registry_has_exactly_eight_builtin_themes(
    builtin_baseline: None,
) -> None:
    assert sorted(THEMES) == BUILTIN_THEMES


def test_default_theme_is_registered(builtin_baseline: None) -> None:
    assert DEFAULT_THEME == "mocha"
    assert DEFAULT_THEME in THEMES


def test_every_builtin_theme_is_well_formed(builtin_baseline: None) -> None:
    for name in BUILTIN_THEMES:
        t = THEMES[name]
        assert t.name == name
        _assert_well_formed(t)


def test_syntax_colors_cover_every_token_kind(builtin_baseline: None) -> None:
    for name in BUILTIN_THEMES:
        t = THEMES[name]
        for kind in SYNTAX_KINDS:
            color = t.syntax_color(kind)
            assert color is not None, f"{name}: no color for {kind}"
            assert HEX.match(color), f"{name}.{kind}={color!r}"


def test_comments_render_italic_in_their_own_color(
    builtin_baseline: None,
) -> None:
    from rich.color import Color

    for name in BUILTIN_THEMES:
        t = THEMES[name]
        style = t.syntax_style("comment")
        assert style.italic, name
        color = style.color
        assert color is not None, name
        assert color.triplet == Color.parse(t.syn_comment).triplet, name


def test_set_theme_switches_and_unknown_theme_lists_builtins(
    builtin_baseline: None,
) -> None:
    assert set_theme("onedark") is THEMES["onedark"]
    assert theme.active() is THEMES["onedark"]
    with pytest.raises(KeyError) as ctx:
        set_theme("no-such-theme")
    message = str(ctx.value)
    for name in BUILTIN_THEMES:
        assert name in message


# --- shipped *.example templates -------------------------------------------


@pytest.fixture
def template_cleanup() -> Iterator[None]:
    """Templates register globally; drop their themes afterwards."""
    yield
    for name in TEMPLATE_THEMES:
        THEMES.pop(name, None)
    set_theme(DEFAULT_THEME)


def test_template_files_are_shipped() -> None:
    directory = _examples_dir()
    for filename in TEMPLATE_FILES:
        path = directory / filename
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")  # UTF-8, not bytes
        assert "register_theme(" in text
        assert "Theme(" in text
        # Templates must rely solely on the injected namespace: match
        # actual import statements (the prose comments mention yate).
        assert re.search(r"(?m)^\s*(?:from\s+yate|import\s+yate)\b", text) is None


def test_templates_exec_under_the_loader_namespace(
    template_cleanup: None,
) -> None:
    directory = _examples_dir()
    registered: dict[str, Theme] = {}

    def capture(t: Theme) -> None:
        registered[t.name] = t

    # Same globals the real loader injects (load_theme_file), with the
    # registering function swapped for a capturing one.
    namespace = theme._theme_namespace()
    namespace["register_theme"] = capture
    for filename in TEMPLATE_FILES:
        exec(
            compile(
                (directory / filename).read_text(encoding="utf-8"),
                filename,
                "exec",
            ),
            namespace,
        )
    assert set(registered) == set(TEMPLATE_THEMES)
    for name, t in registered.items():
        assert t.name == name
        _assert_well_formed(t)
        for kind in SYNTAX_KINDS:
            syn = t.syntax_color(kind)
            assert syn is not None, f"{name}: no color for {kind}"
            assert HEX.match(syn)


def test_templates_are_inert_inside_their_resource_directory() -> None:
    # The loader globs *.py only; *.example files must never register,
    # even when their own directory is scanned directly.
    before = sorted(THEMES)
    errors: list[str] = []
    load_theme_paths([_examples_dir()], errors)
    assert errors == []
    assert sorted(THEMES) == before
    for name in TEMPLATE_THEMES:
        assert name not in THEMES


def test_templates_load_end_to_end_after_copy_as_py(
    template_cleanup: None, tmp_path: Path
) -> None:
    directory = _examples_dir()
    shutil.copyfile(
        directory / "dracula_theme.example", tmp_path / "dracula.py"
    )
    shutil.copyfile(directory / "ayu_theme.example", tmp_path / "ayu.py")
    errors: list[str] = []
    load_theme_paths([tmp_path], errors)
    assert errors == []
    for name in TEMPLATE_THEMES:
        assert name in THEMES
        assert THEMES[name].name == name


def test_non_py_suffixes_are_not_loaded(
    template_cleanup: None, tmp_path: Path
) -> None:
    directory = _examples_dir()
    shutil.copyfile(
        directory / "dracula_theme.example", tmp_path / "dracula.txt"
    )
    shutil.copyfile(directory / "ayu_theme.example", tmp_path / "ayu.theme")
    errors: list[str] = []
    load_theme_paths([tmp_path], errors)
    assert errors == []
    for name in TEMPLATE_THEMES:
        assert name not in THEMES


def test_real_register_theme_via_template_source(template_cleanup: None) -> None:
    # Executing with the unmodified loader namespace registers globally,
    # exactly as it does for a user-copied *.py file.
    directory = _examples_dir()
    source = (directory / "dracula_theme.example").read_text(encoding="utf-8")
    exec(compile(source, "dracula_theme.example", "exec"),
         theme._theme_namespace())
    assert "dracula" in THEMES
    assert THEMES["dracula"].label == "Dracula"
    assert THEMES["dracula"].dark


# --- version ----------------------------------------------------------------


def test_version_is_bumped() -> None:
    assert yate.__version__ == "0.2.4"


def test_pyproject_keeps_the_single_dynamic_version_source() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in text
    assert 'path = "yate/__init__.py"' in text
    # No static version = line: the package __version__ is the only source.
    assert re.search(r"(?m)^version\s*=", text) is None


# --- Textual theme bridge + strict validation --------------------------------


def test_textual_theme_name_has_prefix() -> None:
    assert textual_theme_name("mocha") == "yate-mocha"
    assert textual_theme_name("gruvbox-dark") == "yate-gruvbox-dark"


@pytest.mark.parametrize("name", BUILTIN_THEMES)
def test_bridge_exact_mapping_for_every_builtin(
    builtin_baseline: None, name: str
) -> None:
    from textual.color import Color

    t = THEMES[name]
    tt = to_textual_theme(t)

    assert tt.name == textual_theme_name(name)
    assert tt.dark is t.dark
    # Field-by-field exactness per the mapping table.
    assert tt.primary == t.accent2
    assert tt.secondary == t.accent
    assert tt.warning == t.yellow
    assert tt.error == t.red
    assert tt.success == t.green
    assert tt.accent == t.orange
    assert tt.foreground == t.fg
    assert tt.background == t.bg
    assert tt.surface == t.surface
    assert tt.panel == t.panel
    # Variables override the auto-alpha defaults with exact yate colors.
    assert tt.variables["text"] == t.fg
    assert tt.variables["text-muted"] == t.fg_muted
    assert tt.variables["foreground-muted"] == t.fg_dim
    assert tt.variables["doc-hit-background"] == f"{t.yellow} 12%"
    assert tt.variables["doc-hit-current-background"] == f"{t.yellow} 40%"
    # ColorSystem.generate() must accept the mapped values without raising
    # and surface the key tokens Textual's overlays consume.
    generated = tt.to_color_system().generate()
    assert generated["primary"] == Color.parse(t.accent2).hex
    assert generated["surface"] == Color.parse(t.surface).hex
    assert generated["text"] == t.fg
    assert generated["text-muted"] == t.fg_muted
    assert generated["markdown-h1-color"] == Color.parse(t.accent2).hex


def test_validate_theme_accepts_mocha(builtin_baseline: None) -> None:
    assert validate_theme(THEMES["mocha"]) == []


def _bad(**overrides: object) -> Theme:
    """A copy of mocha with the given fields mutated."""
    base = THEMES["mocha"]
    fields_dict = {f.name: getattr(base, f.name) for f in fields(base)}
    fields_dict.update(overrides)
    return Theme(**fields_dict)  # type: ignore[arg-type]


def test_validate_theme_rejects_bad_hex(builtin_baseline: None) -> None:
    problems = validate_theme(_bad(name="bad-hex", bg="#gggggg"))
    assert any("bg" in p for p in problems)


def test_validate_theme_rejects_empty_name(builtin_baseline: None) -> None:
    problems = validate_theme(_bad(name=""))
    assert any("name" in p for p in problems)


def test_validate_theme_rejects_non_bool_dark(builtin_baseline: None) -> None:
    problems = validate_theme(_bad(name="bad-dark", dark="yes"))  # type: ignore[arg-type]
    assert any("dark" in p for p in problems)


def test_validate_theme_rejects_translucent_background(
    builtin_baseline: None,
) -> None:
    problems = validate_theme(_bad(name="translucent-bg", bg="#1e1e2e80"))
    assert any("bg" in p and "opaque" in p for p in problems)


def test_register_theme_raises_and_leaves_registry_unchanged(
    builtin_baseline: None,
) -> None:
    before = dict(THEMES)
    bad = _bad(name="bad-register", bg="#gggggg")
    with pytest.raises(ValueError):
        register_theme(bad)
    assert THEMES == before


def test_register_theme_accepts_valid_custom_theme(
    builtin_baseline: None,
) -> None:
    good = _bad(name="valid-custom")
    register_theme(good)
    try:
        assert THEMES["valid-custom"] is good
    finally:
        THEMES.pop("valid-custom", None)


def test_to_textual_theme_raises_on_invalid(builtin_baseline: None) -> None:
    with pytest.raises(ValueError):
        to_textual_theme(_bad(name="bad-bridge", bg="#gggggg"))


def test_loader_records_error_for_invalid_custom_color(
    builtin_baseline: None, tmp_path: Path
) -> None:
    # A theme file registering a malformed color must surface as a
    # config.errors entry via load_theme_paths (never raise).
    tdir = tmp_path / "themes"
    tdir.mkdir()
    src = (
        "register_theme(Theme(\n"
        '    name="bad-color", label="Bad Color", dark=True,\n'
        '    bg="#gggggg", panel="#181825", surface="#313244",\n'
        '    gutter_bg="#1e1e2e", border="#45475a",\n'
        '    selection_bg="#585b70", match_bg="#f9e2af",\n'
        '    match_active_bg="#fab387", on_accent="#11111b",\n'
        '    fg="#cdd6f4", fg_dim="#6c7086", fg_muted="#9399b2",\n'
        '    fg_bright="#bac2de",\n'
        '    accent="#89b4fa", accent2="#cba6f7", green="#a6e3a1",\n'
        '    yellow="#f9e2af", red="#f38ba8", orange="#fab387",\n'
        '    mode_normal_bg="#89b4fa", mode_insert_bg="#a6e3a1",\n'
        '    mode_visual_bg="#cba6f7", mode_command_bg="#fab387",\n'
        '    syn_keyword="#cba6f7", syn_string="#a6e3a1",\n'
        '    syn_number="#fab387", syn_comment="#6c7086",\n'
        '    syn_function="#89b4fa", syn_type="#f9e2af",\n'
        '    syn_constant="#fab387", syn_builtin="#f38ba8",\n'
        '    syn_decorator="#f5c2e7", syn_operator="#89dceb",\n'
        '    syn_property="#b4befe",\n'
        "))\n"
    )
    (tdir / "bad_color.py").write_text(src, encoding="utf-8")
    errors: list[str] = []
    load_theme_paths([tdir], errors)
    assert any("bad-color" in e or "bg" in e for e in errors)
    assert "bad-color" not in THEMES
