"""The syntax-domain ``api.*`` bridges (lsp / highlight / syntax / sprites /
theme).

Grouping note: these five bridges share one module because they all wrap
the editor's language/presentation machinery (LSP registration, the
regex and tree-sitter syntax backends, the sprite roster, the theme
module) and the ``api.highlight`` / ``api.syntax`` pair is documented as
one complementary unit -- splitting them further would not shrink the
import face.

Patch-surface note: ``SyntaxExtensionBridge`` resolves
``load_language_from_grammar`` / ``drop_ts_language`` through a
late-bound ``from yate.services.extensions.bridges import ...`` lookup at
call time, because the test suite patches those names on the package
namespace (``tests/test_extension_bridges.py`` string targets,
``tests/test_ts_backend.py`` ``patch.object`` targets).  The registered
seam is the same one the ``yate/services/yxp/`` facade uses.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from yate.editor_lsp.client import DEFAULT_ROOT_MARKERS, ServerConfig
from yate.editor_lsp.manager import LspManager
from yate.editor_sprites.characters import (
    character_names,
    register_character,
    unregister_character,
)
from yate.editor_syntax import (
    LangSpec,
    available_filetypes,
    langdefs,
    prefer_regex,
    register_language,
)
from yate.editor_syntax.engine import unprefer_regex
from yate.logs import tracing

#: Trace logger ("yate.services.extensions.bridges.syntax_lsp"); silent
#: unless yate_trace is on.
log = tracing.get_logger(__name__)


class LspExtensionBridge:
    """``api.lsp`` -- register language servers from an extension."""

    def __init__(
        self,
        lsp: LspManager,
        record_undo: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        # ``None`` (headless construction in tests) degrades to a no-op sink:
        # registrations then stay permanent, like outside a rollback scope.
        self._lsp = lsp
        self._record_undo: Callable[[Callable[[], None]], None] = (
            record_undo if record_undo is not None else lambda _undo: None
        )

    def register_server(  # noqa: Any - LSP JSON payload forwarded verbatim
        self,
        name: str,
        *,
        command: str,
        args: Sequence[str] | None = None,
        filetypes: Sequence[str],
        language_ids: Mapping[str, str] | None = None,
        initialization_options: Any = None,
        settings: Any = None,
        env: Mapping[str, str] | None = None,
        root_markers: Sequence[str] | None = None,
    ) -> None:
        """Register an LSP server (lazily spawned on first matching file).

        ``command`` may be empty when the extension could not find an
        executable; the registration stays visible and fails lazily without
        disturbing the user.
        """
        self._lsp.register_server(ServerConfig(
            name=name,
            command=command,
            args=list(args) if args is not None else [],
            filetypes=list(filetypes),
            language_ids=dict(language_ids) if language_ids is not None else {},
            initialization_options=initialization_options,
            settings=settings,
            env=dict(env) if env is not None else None,
            root_markers=list(root_markers) if root_markers is not None
            else list(DEFAULT_ROOT_MARKERS),
        ))
        def undo() -> None:
            self._lsp.unregister_server(name)

        self._record_undo(undo)

    def statuses(self) -> dict[str, str]:
        """``{server name: state name}`` for every registered server."""
        return {name: state.value for name, state in self._lsp.states().items()}

    def has_state(self, name: str, state: str) -> bool:
        """True when server *name* currently reports the state *state*."""
        current = self._lsp.states().get(name)
        return current is not None and current.value == state


class HighlightExtensionBridge:
    """``api.highlight`` -- register custom syntax highlighters.

    The built-in tokenizer is declarative: a :class:`LangSpec` lists comment
    markers, keyword/type/builtin word sets and a few lexical flags, and the
    engine handles strings, numbers, comments and multiline state for free.
    See ``yate/extensions/batch_syntax.py.example`` for a complete example.
    Registrations made while a rollback scope is active are recorded through
    *record_undo*, so a failing ``setup`` also drops them (A13).
    """

    #: Re-exported so extensions can build specs via ``api.highlight.LangSpec``.
    LangSpec = LangSpec

    def __init__(self, record_undo: Callable[[Callable[[], None]], None]) -> None:
        self._record_undo = record_undo

    def register(self, spec: LangSpec, *extensions: str) -> None:
        """Register *spec* under extension keys (``"cs"``, ``"csx"``, ...).

        Re-registering an existing key replaces its highlighter, so a custom
        language can override a built-in one. The type is immediately usable
        from ``:set filetype=`` and resolved by both extension key and the
        spec's language ``name``.  The keys are also pinned to the regex
        backend, so a deliberately registered declarative highlighter wins
        over the built-in tree-sitter registration for the same key.
        """
        previous = {
            key: langdefs.lang_for(key)
            for key in (ext.lower().lstrip(".") for ext in extensions)
            if key
        }
        register_language(spec, *extensions)
        prefer_regex(*extensions)

        def undo() -> None:
            for key, prev in previous.items():
                if prev is not None:
                    langdefs.register_language(prev, key)
                else:
                    langdefs.drop_language(key)
            unprefer_regex(*extensions)

        self._record_undo(undo)

    @staticmethod
    def spec(**kwargs: Any) -> LangSpec:
        """Build a :class:`LangSpec` with keyword arguments (``name=...``)."""
        return LangSpec(**kwargs)

    @staticmethod
    def available() -> list[str]:
        """All extension keys and language names accepted by ``:set filetype``."""
        return available_filetypes()


class SyntaxExtensionBridge:
    """``api.syntax`` -- tree-sitter grammars for custom languages.

    Complements :class:`HighlightExtensionBridge`: where ``api.highlight``
    registers a simple declarative word-list spec (regex backend),
    ``api.syntax`` binds a real tree-sitter grammar plus a
    ``highlights.scm`` query for syntax-tree based highlighting.  Requires
    the optional ``tree_sitter`` dependency (``pip install yate[ts]``).
    """

    def __init__(
        self, record_undo: Callable[[Callable[[], None]], None] | None = None
    ) -> None:
        # ``None`` (headless construction in tests) degrades to a no-op sink.
        self._record_undo: Callable[[Callable[[], None]], None] = (
            record_undo if record_undo is not None else lambda _undo: None
        )

    def register_tree_sitter(
        self,
        name: str,
        *,
        grammar: str,
        extensions: Sequence[str],
        query: str,
        capture_map: dict[str, str] | None = None,
    ) -> None:
        """Register a tree-sitter grammar + query as language *name*.

        *grammar* is either an importable grammar pack name
        (``"tree_sitter_yatesh"``) or a path to a compiled shared library
        (``.dll`` / ``.so`` / ``.dylib`` built with ``tree-sitter generate``
        plus a C compiler; its C entry point must be named
        ``tree_sitter_<name>``).

        *query* is a ``highlights.scm`` source string, or a path to one
        (resolve it against your extension's ``__file__`` for robustness).

        *extensions* are the file extensions (``"ysh"``, ...) that select
        the language; they become available from ``:set filetype=`` once the
        grammar is registered.  Note that registration is all-or-nothing: the
        keys are only published *after* the grammar and query load, so a
        missing dependency, a missing pack or an invalid query registers
        nothing at all (there is no regex fallback -- register a
        :class:`LangSpec` through ``api.highlight.register`` for that).

        *capture_map* optionally overrides/extends the default
        capture-name -> token-kind mapping (see
        ``yate/editor_syntax/ts_backend/languages.py``).  A capture name that
        is in neither map is silently dropped by the backend.

        Raises ``RuntimeError`` when ``tree_sitter`` is not installed,
        ``ValueError`` for unresolvable grammars, and query errors straight
        through -- all surfaced as ``extension <name>: ...`` messages.
        """
        # Late-bound through the package namespace: the test suite patches
        # this name on yate.services.extensions.bridges (see module docstring).
        from yate.services.extensions.bridges import load_language_from_grammar

        query_src = query
        query_file = Path(query)
        if query_file.is_file():
            query_src = query_file.read_text(encoding="utf-8")
        load_language_from_grammar(
            name,
            grammar,
            query_src,
            capture_map=capture_map,
            extensions=tuple(extensions),
        )
        self._record_undo(lambda: self._undo(name, tuple(extensions)))

    @staticmethod
    def _undo(name: str, extensions: tuple[str, ...]) -> None:
        """Forget a grammar registered by a setup that then failed.

        Built-in specs are import-time data: the keys stay registered (the
        shared registry refuses to drop them), only the grammar this
        extension loaded is released.
        """
        from yate.services.extensions.bridges import drop_ts_language

        drop_ts_language(name)
        try:
            langdefs.drop_language(*extensions)
        except ValueError:
            # A built-in key cannot be dropped, and must not be.
            log.debug("rollback kept the built-in language keys %s", extensions)


class SpriteExtensionBridge:
    """``api.sprites`` -- custom characters for the idle screensaver.

    A character is a small pixel animation: each frame is a tuple of
    equal-length strings, one character per pixel (``.`` = transparent),
    and the palette maps every other key character to a ``"#rrggbb"``
    color.  The screensaver renders two pixel rows per terminal text row
    (``▀`` / ``▄`` / ``█`` half blocks), so keep sprites small enough for
    a 24-row terminal.  Registration validates like the built-in roster
    (>= 2 frames, uniform geometry, full palette coverage) and rejects
    duplicates -- built-in names included.  A failing call raises
    ``ValueError``, which the loader reports as
    ``extension <name>: ...``.  See the extension manual, section
    "Screensaver characters", for the full reference and an example.
    """

    def __init__(
        self, record_undo: Callable[[Callable[[], None]], None] | None = None
    ) -> None:
        # ``None`` (legacy headless construction, e.g. the sprite tests)
        # degrades to a no-op sink: registrations then stay permanent.
        self._record_undo: Callable[[Callable[[], None]], None] = (
            record_undo if record_undo is not None else lambda _undo: None
        )

    def register(
        self, name: str, frames: Sequence[Sequence[str]], palette: Mapping[str, str]
    ) -> None:
        """Register screensaver character *name* from *frames* + *palette*.

        *frames* is a sequence of frames, each frame a sequence of pixel
        rows; *palette* maps the row characters to hex colors.  Both are
        copied by the registry, so tuples and lists both work.  Call once
        from ``setup``; the character joins the parade, playlist shuffling
        and the rc whitelist immediately.  Inside a rollback scope the
        registration is recorded, so a failing ``setup`` removes the
        character again (A13).
        """
        register_character(
            name, tuple(tuple(rows) for rows in frames), dict(palette)
        )

        def undo(name: str = name) -> None:
            unregister_character(name)

        self._record_undo(undo)

    def unregister(self, name: str) -> None:
        """Remove the character *name* this extension registered.

        Built-in names cannot be removed (``ValueError``); unknown names
        raise ``KeyError``.  Call from ``teardown`` so a reloaded
        extension does not accumulate ghost names.
        """
        unregister_character(name)

    def names(self) -> list[str]:
        """Every registered character name (built-in roster + extensions)."""
        return list(character_names())


class ThemeExtensionBridge:
    """``api.theme`` -- switch/read the color theme from an extension.

    The bridge holds injected callbacks only (R4: ``services`` never imports
    ``yate.editor_components``); the editor wires ``set`` to the theme module's
    ``set_theme`` and ``active`` to its name.  An unknown theme name raises
    ``KeyError`` straight through -- the loader records and rolls back a
    raising ``setup``, and the API's callback guard contains it later on.
    """

    def __init__(
        self,
        set_theme: Callable[[str], None],
        active_name: Callable[[], str],
    ) -> None:
        self._set_theme = set_theme
        self._active_name = active_name

    def set(self, name: str) -> None:
        """Switch the color theme to *name* (``KeyError`` when unknown)."""
        self._set_theme(name)

    def active(self) -> str:
        """The active theme's name."""
        return self._active_name()
