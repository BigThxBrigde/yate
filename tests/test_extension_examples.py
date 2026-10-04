"""Acceptance tests for the bundled ``*.py.example`` extension templates.

The templates ship as documentation, so nothing else type-checks or executes
them (``pyproject.toml`` does not ship ``.py.example`` in the wheel and pyright
skips the suffix): a template that stopped registering, or that drifted from the
API it demonstrates, would surface only in a user's editor.  These tests parse
every template, run the self-contained ones through a real
:class:`ExtensionAPI`, and assert the registered spec actually paints tokens.

This is the acceptance step the syntax-langs plan listed for W3 and could not
run by hand: ``tree-sitter-fsharp`` is not installed, so the F# template is
covered by ``skipif`` plus a static capture-name check instead.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import ast
import importlib.util
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from yate.editor_syntax import engine, regex_backend, resolve_filetype, tokenize_document
from yate.editor_syntax.ts_backend import languages as ts_langs
from yate.paths import bundled_extensions_dir
from yate.services.extensions import ExtensionAPI, ExtensionContext

#: Every bundled template, by file stem.  The manual promises "seven extension
#: examples" -- this list is what keeps that sentence true.
_EXPECTED_TEMPLATES: frozenset[str] = frozenset({
    "batch_syntax",
    "diff_syntax",
    "example_ext",
    "fsharp_syntax",
    "git_syntax",
    "ini_syntax",
    "yatesh_syntax",
})

#: ``@name`` in a highlights query, dotted names included.
_CAPTURE_RE = re.compile(r"@([A-Za-z_][\w.]*)")


def _templates() -> list[Path]:
    """The bundled ``*.py.example`` templates, sorted by name."""
    return sorted(bundled_extensions_dir().glob("*.py.example"))


def _extension_api() -> ExtensionAPI:
    """An :class:`ExtensionAPI` over a minimal context (templates only set up)."""
    ctx = ExtensionContext(
        session=cast(Any, MagicMock()),
        workspace=cast(Any, MagicMock()),
        lsp=cast(Any, MagicMock()),
        keymaps=cast(Any, MagicMock()),
        actions=cast(Any, MagicMock()),
        commands=cast(Any, MagicMock()),
        message=lambda _text: None,
        run_shell=lambda _command, _show: None,
        open_path=lambda _path: None,
        save=lambda: None,
    )
    return ExtensionAPI(ctx)


@pytest.fixture
def clean_registries() -> Iterator[None]:
    """Restore every global registry a template's ``setup()`` writes to."""
    languages = dict(regex_backend._LANGUAGES)
    names = dict(regex_backend._NAME_TO_KEY)
    pinned = set(engine._REGEX_PINNED)
    ts_langs_map = dict(ts_langs._EXT_TO_LANG)
    ts_loaded = dict(ts_langs._LANGS)
    ts_failed = set(ts_langs._FAILED)
    yield
    regex_backend._LANGUAGES.clear()
    regex_backend._LANGUAGES.update(languages)
    regex_backend._NAME_TO_KEY.clear()
    regex_backend._NAME_TO_KEY.update(names)
    engine._REGEX_PINNED.clear()
    engine._REGEX_PINNED.update(pinned)
    ts_langs._EXT_TO_LANG.clear()
    ts_langs._EXT_TO_LANG.update(ts_langs_map)
    ts_langs._LANGS.clear()
    ts_langs._LANGS.update(ts_loaded)
    ts_langs._FAILED.clear()
    ts_langs._FAILED.update(ts_failed)


def _run_setup(path: Path, api: ExtensionAPI) -> dict[str, Any]:
    """Execute one template's source and call its ``setup(api)``.

    Returns the module namespace so callers can inspect module constants
    (``_QUERY``, keyword tables).  Templates keep the ``.example`` suffix and
    are never imported by the loader, so executing the source is the only way
    to run them.
    """
    source = path.read_text(encoding="utf-8")
    namespace: dict[str, Any] = {"__file__": str(path), "__name__": path.stem}
    exec(compile(source, str(path), "exec"), namespace)  # noqa: S102 - templates are ours
    setup = cast(Callable[[ExtensionAPI], None], namespace["setup"])
    setup(api)
    return namespace


def _kinds(lines: list[str], filetype: str, row: int) -> list[tuple[str, str]]:
    """Flatten one row's tokens to ``(kind, text)`` pairs."""
    tokens = tokenize_document(lines, filetype)[row]
    return [(t.kind, lines[row][t.start:t.end]) for t in tokens]


# --- every template parses and is accounted for ------------------------------


def test_every_example_template_is_valid_python() -> None:
    templates = _templates()
    assert templates, "no bundled *.py.example templates found"
    for path in templates:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_template_set_matches_the_documented_one() -> None:
    # The manual counts them ("seven extension examples"); a template added or
    # dropped without updating the docs would otherwise go unnoticed.
    assert {path.name.removesuffix(".py.example") for path in _templates()} == (
        _EXPECTED_TEMPLATES
    )


# --- declarative (regex) templates: register and paint -----------------------


def test_batch_example_registers_and_paints(
    clean_registries: None,
) -> None:
    path = bundled_extensions_dir() / "batch_syntax.py.example"
    _run_setup(path, _extension_api())
    assert resolve_filetype("batch") in ("bat", "cmd")
    lines = ["@echo off", "rem note"]
    # '@' is a command prefix here, not a decorator (at_sigil in the template).
    assert ("property", "@echo") in _kinds(lines, "bat", 0)
    assert ("keyword", "off") in _kinds(lines, "bat", 0)
    assert ("comment", "rem note") in _kinds(lines, "bat", 1)


def test_ini_example_overrides_the_builtin_spec(
    clean_registries: None,
) -> None:
    before = regex_backend.lang_for("ini")
    path = bundled_extensions_dir() / "ini_syntax.py.example"
    _run_setup(path, _extension_api())
    after = regex_backend.lang_for("ini")
    assert after is not None
    # Re-registering an existing key replaces the spec -- the point of the
    # example (";" comments instead of the built-in "#").
    assert after is not before
    assert after.line_comment == ";"
    lines = ["; note", "[section]", "key = 1"]
    assert ("comment", "; note") in _kinds(lines, "ini", 0)
    assert ("keyword", "[section]") in _kinds(lines, "ini", 1)
    assert ("property", "key") in _kinds(lines, "ini", 2)


def test_git_example_registers_both_dialects(
    clean_registries: None,
) -> None:
    path = bundled_extensions_dir() / "git_syntax.py.example"
    _run_setup(path, _extension_api())
    for key in ("gitignore", "gitconfig", "gitmodules"):
        assert resolve_filetype(key) == key
    lines = ["[core]", "\tbare = false"]
    assert ("keyword", "[core]") in _kinds(lines, "gitconfig", 0)
    # The config tokenizer's key span includes the leading indent; what matters
    # here is that the key is a property and the value a constant.
    assert ("property", "\tbare") in _kinds(lines, "gitconfig", 1)
    assert ("constant", "false") in _kinds(lines, "gitconfig", 1)
    # .gitignore has no suffix to derive a type from (documented in the
    # template), so the key is reachable by name only -- the honest assertion
    # is that plain text stays plain, not that the file highlights itself.
    assert tokenize_document(["*.log"], "plaintext") == [[]]
    assert regex_backend.lang_for("gitignore") is not None


def test_diff_example_registers_and_paints(
    clean_registries: None,
) -> None:
    path = bundled_extensions_dir() / "diff_syntax.py.example"
    _run_setup(path, _extension_api())
    assert resolve_filetype("diff") in ("diff", "patch")
    lines = ["diff --git a/x b/x", "--- a/x", "+++ b/x"]
    assert ("keyword", "diff") in _kinds(lines, "diff", 0)
    # Line-level coloring is a documented non-goal of the word-list backend:
    # the '--- a/x' line keeps its default foreground plus the punctuation the
    # operator rule claims, and no metadata word is invented for it.
    assert all(kind == "operator" for kind, _ in _kinds(lines, "diff", 1))


# --- tree-sitter template ----------------------------------------------------

_FSHARP_SKIP = pytest.mark.skipif(
    importlib.util.find_spec("tree_sitter_fsharp") is None,
    reason="tree_sitter_fsharp is not installed (the example's own prerequisite)",
)


@_FSHARP_SKIP
def test_fsharp_example_registers_a_grammar(
    clean_registries: None,
) -> None:
    path = bundled_extensions_dir() / "fsharp_syntax.py.example"
    _run_setup(path, _extension_api())
    assert ts_langs.resolve("fs") is not None
    lines = ["let x = 1", "printfn \"%d\" x"]
    assert _kinds(lines, "fs", 0) != []


def test_fsharp_query_uses_only_registered_capture_names() -> None:
    # Runs without the grammar pack: a capture name missing from
    # DEFAULT_CAPTURE_MAP is dropped silently by the backend, which is exactly
    # the trap the template's _CAPTURE_MAP comment now warns about.
    path = bundled_extensions_dir() / "fsharp_syntax.py.example"
    source = path.read_text(encoding="utf-8")
    namespace: dict[str, Any] = {"__file__": str(path), "__name__": path.stem}
    exec(compile(source, str(path), "exec"), namespace)  # noqa: S102
    query = cast(str, namespace["_QUERY"])
    used = set(_CAPTURE_RE.findall(query))
    assert used, "the example query lost every capture"
    assert used <= set(ts_langs.DEFAULT_CAPTURE_MAP)
    overrides = cast(dict[str, str], namespace["_CAPTURE_MAP"])
    assert overrides == {}
    assert set(overrides) <= set(ts_langs.DEFAULT_CAPTURE_MAP)


# --- walkthrough templates ---------------------------------------------------


def test_walkthrough_example_registers_commands(
    clean_registries: None,
) -> None:
    # The extension-system tour needs no grammar; it must simply run.
    path = bundled_extensions_dir() / "example_ext.py.example"
    namespace = _run_setup(path, _extension_api())
    assert callable(namespace["setup"])


def test_yatesh_example_fails_loudly_without_its_grammar() -> None:
    # Documents the behaviour the F# template's docstring now states: there is
    # no silent "falls back to plain text" -- a missing shared library raises
    # and the extension records an error instead of registering anything.
    path = bundled_extensions_dir() / "yatesh_syntax.py.example"
    with pytest.raises((RuntimeError, ValueError, OSError)):
        _run_setup(path, _extension_api())
