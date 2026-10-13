"""Unit tests for ``yate.services.extension_bridges`` (the four api.* bridges).

Covers the Lsp / Highlight / Sprite bridges directly (the Syntax bridge's
happy path lives in ``tests/test_ts_backend.py``; only its
unresolvable-grammar rejection is pinned here).  The language and sprite
registries are process globals, so autouse fixtures restore them around
every test.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

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
from yate.services import clipboard
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
        run_action=lambda _name: False,
        set_theme=lambda _name: None,
        active_theme_name=lambda: "mocha",
    )
    return ExtensionAPI(ctx)


def _api_with_callbacks(
    run_action: Callable[[str], bool],
    set_theme: Callable[[str], None],
) -> ExtensionAPI:
    """An ExtensionAPI whose context callbacks are fixed at construction.

    The bridges snapshot the injected callables when the API is built, so a
    test that records calls must inject the callback up front (reassigning
    ``api.app.set_theme`` afterwards never reaches the bridge).
    """
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
        run_action=run_action,
        set_theme=set_theme,
        active_theme_name=lambda: "mocha",
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


# --- ThemeExtensionBridge -------------------------------------------------------


def test_theme_bridge_set_forwards_and_active_reads_back() -> None:
    """``set`` forwards the name to the injected callback; ``active`` reads it."""
    seen: list[str] = []
    api = _api_with_callbacks(
        run_action=lambda _name: False, set_theme=seen.append
    )

    api.theme.set("latte")

    assert seen == ["latte"]
    # the active-name callback injected above answers ``active``
    assert api.theme.active() == "mocha"


# --- ClipboardExtensionBridge ---------------------------------------------------


def test_clipboard_bridge_set_and_get_forward_to_service(
    api: ExtensionAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``set`` / ``get`` forward to the clipboard service's module functions."""
    copied: list[str] = []

    def fake_copy(text: str) -> bool:
        copied.append(text)
        return True

    monkeypatch.setattr(clipboard, "copy_text", fake_copy)
    monkeypatch.setattr(clipboard, "paste_text", lambda: "from-clipboard")

    assert api.clipboard.set("hello") is True
    assert copied == ["hello"]
    assert api.clipboard.get() == "from-clipboard"


def test_clipboard_bridge_degraded_results_pass_through(
    api: ExtensionAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The service's degraded ``False`` / ``None`` results pass through."""

    def fake_copy(_text: str) -> bool:
        return False

    monkeypatch.setattr(clipboard, "copy_text", fake_copy)
    monkeypatch.setattr(clipboard, "paste_text", lambda: None)

    assert api.clipboard.set("x") is False
    assert api.clipboard.get() is None


# --- DocsExtensionBridge --------------------------------------------------------


def test_docs_bridge_all_returns_a_fresh_list(api: ExtensionAPI, tmp_path: Path) -> None:
    """``all`` copies the session list: mutating it cannot touch the session."""
    file = tmp_path / "doc.txt"
    file.write_text("x", encoding="utf-8")
    opened = api.app.session.open(file)
    assert opened is not None

    docs = api.docs.all()
    assert opened in docs
    docs.clear()
    # the session still holds both documents (buffer + opened file)
    assert len(api.docs.all()) == 2


def test_docs_bridge_is_open_hits_and_misses(api: ExtensionAPI, tmp_path: Path) -> None:
    """``is_open`` accepts str and Path and misses on unknown files."""
    file = tmp_path / "doc.txt"
    file.write_text("x", encoding="utf-8")
    api.app.session.open(file)

    assert api.docs.is_open(file) is True
    assert api.docs.is_open(str(file)) is True
    assert api.docs.is_open(tmp_path / "other.txt") is False


# --- ActionExtensionBridge ------------------------------------------------------


def test_actions_bridge_run_dispatches_through_injected_callback() -> None:
    """``run`` forwards to the injected ``run_action`` (editor dispatch)."""
    seen: list[str] = []

    def run_action(name: str) -> bool:
        seen.append(name)
        return name != "ghost"

    api = _api_with_callbacks(run_action=run_action, set_theme=lambda _name: None)

    assert api.actions.run("probe_act") is True
    assert api.actions.run("ghost") is False
    assert seen == ["probe_act", "ghost"]


def test_actions_bridge_names_and_has_read_the_registry(api: ExtensionAPI) -> None:
    """``names`` / ``has`` read the shared ActionRegistry."""
    api.app.actions.register("probe_action", lambda _ctx: None)
    try:
        assert api.actions.has("probe_action") is True
        assert api.actions.has("no_such_action") is False
        assert "probe_action" in api.actions.names()
    finally:
        api.app.actions.unregister("probe_action")


# --- UiExtensionBridge.add_segment ---------------------------------------------


def test_ui_bridge_add_segment_registers_and_sorts_by_priority(
    api: ExtensionAPI,
) -> None:
    """``add_segment`` registers; priority sorts, ties keep registration order."""
    api.ui.add_segment("low", lambda: "low", "right", priority=1)
    api.ui.add_segment("high", lambda: "high", priority=5)
    api.ui.add_segment("tie", lambda: "t", "right", priority=1)
    api.ui.add_segment("left", lambda: "l", align="left")

    assert [segment.id for segment in api.ui.segments("right")] == [
        "high", "low", "tie",
    ]
    assert [segment.id for segment in api.ui.segments("left")] == ["left"]


def test_ui_bridge_add_segment_duplicate_id_raises_value_error(
    api: ExtensionAPI,
) -> None:
    """A duplicate id raises ValueError exactly like add_status_segment."""
    api.ui.add_segment("dup", lambda: "x")
    with pytest.raises(ValueError):
        api.ui.add_segment("dup", lambda: "y")


def test_ui_bridge_add_segment_rolls_back_inside_scope(api: ExtensionAPI) -> None:
    """Inside a rollback scope the factory-built segment is dropped again."""
    api.start_scope()
    api.ui.add_segment("scoped", lambda: "s")
    assert [segment.id for segment in api.ui.segments("right")] == ["scoped"]

    api.rollback_scope()

    assert api.ui.segments("right") == []
