"""Unit tests for ``yate.services.extension_bridges`` (the four api.* bridges).

Covers the Lsp / Highlight / Sprite bridges directly (the Syntax bridge's
happy path lives in ``tests/test_ts_backend.py``; only its
unresolvable-grammar rejection is pinned here).  The language and sprite
registries are process globals, so autouse fixtures restore them around
every test.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections.abc import Iterator

import pytest

from yate.config import YateConfig
from yate.editor_lsp.client import DEFAULT_ROOT_MARKERS, ServerState
from yate.editor_lsp.manager import LspManager
from yate.editor_syntax import LangSpec, available_filetypes, engine, langdefs
from yate.editor_syntax.ts_backend import languages as ts_langs
from yate.editor_sprites import characters
from yate.keymaps.base import Keymap
from yate.keymaps.registry import KeymapSet
from yate.registries import ActionRegistry, CommandRegistry
from yate.session import EditorSession
from yate.services.extension_bridges import HighlightExtensionBridge
from yate.services.extensions import ExtensionAPI, ExtensionContext
from yate.services.workspace import Workspace

has_tree_sitter: bool = ts_langs.ts_available()


@pytest.fixture
def api() -> ExtensionAPI:
    """An ExtensionAPI over real registries (the test_extension_api shape)."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    ctx = ExtensionContext(
        session=session,
        workspace=Workspace(),
        lsp=LspManager(),
        keymaps=KeymapSet({"vsc": Keymap(), "vim": Keymap()}, "vsc"),
        actions=ActionRegistry(),
        commands=CommandRegistry(),
        message=lambda _text: None,
        run_shell=lambda _command, _show: None,
        open_path=lambda _path: None,
        save=lambda: None,
    )
    return ExtensionAPI(ctx)


def _drop_test_sprites() -> None:
    """Unregister every leftover ``test_sprite_`` character."""
    for name in characters.character_names():
        if name.startswith("test_sprite_"):
            characters.unregister_character(name)


@pytest.fixture(autouse=True)
def restore_sprites() -> Iterator[None]:
    """Keep the sprite roster free of ``test_sprite_`` leftovers.

    ``register_character`` mutates a process-global registry; sweep before
    and after so a failing test cannot leak into the screensaver tests.
    """
    _drop_test_sprites()
    yield
    _drop_test_sprites()


@pytest.fixture(autouse=True)
def restore_langdefs() -> Iterator[None]:
    """Snapshot and restore the language globals the highlight bridge writes.

    Three process globals move when ``api.highlight.register`` runs: the
    extension-key registry, the language-name registry and the regex-pin
    set in the engine.  All three are restored before *and* after every
    test so a leak from an earlier failing test cannot ride into this file.
    """
    languages: dict[str, LangSpec] = dict(langdefs.languages())
    names: dict[str, str] = dict(langdefs.name_to_key())
    pinned: set[str] = set(engine._REGEX_PINNED)

    def _restore() -> None:
        langdefs.languages().clear()
        langdefs.languages().update(languages)
        langdefs.name_to_key().clear()
        langdefs.name_to_key().update(names)
        engine._REGEX_PINNED.clear()
        engine._REGEX_PINNED.update(pinned)

    _restore()
    yield
    _restore()


# --- LspExtensionBridge --------------------------------------------------------


def test_lsp_bridge_register_server_maps_fields_to_config(api: ExtensionAPI) -> None:
    """``register_server`` maps the bridge kwargs onto a real ServerConfig."""
    api.lsp.register_server(
        "probe",
        command="tss",
        filetypes=["ts"],
        args=["-x"],
        language_ids={"ts": "typescript"},
    )
    configs = {config.name: config for config in api.app.lsp.configs()}
    config = configs["probe"]
    assert config.command == "tss"
    assert config.args == ["-x"]
    assert config.filetypes == ["ts"]
    assert config.language_ids == {"ts": "typescript"}

    # fields the extension left out fall back to the config defaults
    api.lsp.register_server("probe_min", command="tss2", filetypes=["tsx"])
    configs = {config.name: config for config in api.app.lsp.configs()}
    minimal = configs["probe_min"]
    assert minimal.args == []
    assert minimal.root_markers == list(DEFAULT_ROOT_MARKERS)


def test_lsp_bridge_statuses_reports_state_names(api: ExtensionAPI) -> None:
    """``statuses()`` maps server names to state-enum value strings."""
    api.lsp.register_server("probe", command="tss", filetypes=["ts"])
    statuses = api.lsp.statuses()
    assert isinstance(statuses, dict)
    assert all(isinstance(value, str) for value in statuses.values())
    assert statuses["probe"] == ServerState.CONFIGURED.value


def test_lsp_bridge_has_state_unknown_server_is_false(api: ExtensionAPI) -> None:
    """``has_state`` is False for a never-registered server."""
    assert api.lsp.has_state("nope", "running") is False


# --- HighlightExtensionBridge --------------------------------------------------


def test_highlight_bridge_register_resolves_and_pins_regex(api: ExtensionAPI) -> None:
    """``register`` publishes the spec and pins the key to the regex backend."""
    spec = LangSpec(
        name="zzlang",
        line_comment="#",
        keywords=frozenset({"zzk"}),
        type_def_words=frozenset({"zzt"}),
    )
    api.highlight.register(spec, "zzz")
    assert langdefs.lang_for("zzz") is spec
    assert "zzz" in available_filetypes()
    # the regex backend is pinned for this key -- asserted directly so a pin
    # regression is distinguishable from a word-list resolution regression
    assert "zzz" in engine._REGEX_PINNED
    # the spec's language name resolves back to the registering key
    assert langdefs.resolve_filetype("zzlang") == "zzz"
    # the tokens come from the registered regex word lists (a type-def word
    # paints as a keyword and marks the identifier after it as a type, the
    # same shape the test_highlight.py registration precedent asserts)
    line = "zzk zzt ZzType  # note"
    pairs = [
        (token.kind, line[token.start:token.end])
        for token in engine.tokenize_document([line], "zzz")[0]
    ]
    assert ("keyword", "zzk") in pairs
    assert ("keyword", "zzt") in pairs
    assert ("type", "ZzType") in pairs
    assert ("comment", "# note") in pairs


def test_highlight_bridge_spec_builds_langspec() -> None:
    """``spec`` builds a LangSpec from keyword arguments."""
    spec = HighlightExtensionBridge.spec(name="x", line_comment="#")
    assert isinstance(spec, LangSpec)
    assert spec.name == "x"


def test_highlight_bridge_available_lists_builtin_filetypes() -> None:
    """``available`` forwards the registry's filetype list."""
    available = HighlightExtensionBridge.available()
    assert available == available_filetypes()
    assert "python" in available


# --- SpriteExtensionBridge -----------------------------------------------------


def test_sprite_bridge_register_and_unregister_roundtrip(api: ExtensionAPI) -> None:
    """A registered character joins the roster; unregister removes it."""
    frames = [["ab", "cd"], ["ab", "cd"]]
    palette = {"a": "#ffffff", "b": "#000000", "c": "#112233", "d": "#445566"}
    api.sprites.register("test_sprite_rt", frames, palette)
    assert "test_sprite_rt" in api.sprites.names()

    api.sprites.unregister("test_sprite_rt")
    assert "test_sprite_rt" not in api.sprites.names()

    # a single-frame sprite is rejected like the built-in roster validates
    with pytest.raises(ValueError):
        api.sprites.register(
            "test_sprite_bad", [["ab"]], {"a": "#ffffff", "b": "#000000"}
        )


def test_sprite_bridge_unregister_unknown_raises_key_error(api: ExtensionAPI) -> None:
    """Unregistering a name that was never registered raises KeyError."""
    with pytest.raises(KeyError):
        api.sprites.unregister("no_such_sprite")


# --- SyntaxExtensionBridge -----------------------------------------------------


def test_syntax_bridge_register_rejects_unresolvable_grammar(api: ExtensionAPI) -> None:
    """An unresolvable grammar raises without publishing any extension key."""
    if not has_tree_sitter:
        with pytest.raises(RuntimeError):
            api.syntax.register_tree_sitter(
                "nope_lang",
                grammar="no_such_pack",
                extensions=["npx"],
                query="(comment) @comment",
            )
    else:
        with pytest.raises(ValueError):
            api.syntax.register_tree_sitter(
                "nope_lang",
                grammar="no_such_pack",
                extensions=["npx"],
                query="(comment) @comment",
            )
        # all-or-nothing: the extension key was never published
        assert "npx" not in available_filetypes()
