"""The ``api.*`` sub-namespace bridges (events / lsp / highlight / syntax / sprites / ui).

Each bridge wraps one capability domain for extension scripts; the
:class:`ExtensionAPI <yate.services.extension_api.ExtensionAPI>` facade
instantiates them in its ``__init__`` and hands them out through the
matching properties.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

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
    prefer_regex,
    register_language,
)
from yate.editor_syntax.ts_backend import load_language_from_grammar
from yate.logs import tracing
from yate.services.events import EditorEvent, EventHub, EventCallback

#: Trace logger ("yate.services.extension_bridges"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: The two status bar halves a segment can attach to.
type SegmentAlign = Literal["left", "right"]


class EventExtensionBridge:
    """``api.events`` -- subscribe to editor events from an extension.

    Wraps the editor-owned :class:`~yate.services.events.EventHub`; every
    subscription made while a rollback scope is active is recorded, so a
    failing ``setup`` also drops its listeners (A13).
    """

    def __init__(
        self,
        hub: EventHub,
        record_undo: Callable[[Callable[[], None]], None],
    ) -> None:
        self._hub = hub
        self._record_undo = record_undo

    def subscribe(
        self, event: EditorEvent, callback: EventCallback
    ) -> Callable[[], None]:
        """Subscribe to *event*; returns the unsubscribe thunk.

        *callback* is guarded by the hub itself (a raising listener is
        reported and skipped, never crashing the editor operation that
        emitted).  Payloads are the frozen dataclasses defined in
        :mod:`yate.services.events`.
        """
        unsubscribe = self._hub.subscribe(event, callback)
        self._record_undo(unsubscribe)
        return unsubscribe


class LspExtensionBridge:
    """``api.lsp`` -- register language servers from an extension."""

    def __init__(self, lsp: LspManager) -> None:
        self._lsp = lsp

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
    """

    #: Re-exported so extensions can build specs via ``api.highlight.LangSpec``.
    LangSpec = LangSpec

    def register(self, spec: LangSpec, *extensions: str) -> None:
        """Register *spec* under extension keys (``"cs"``, ``"csx"``, ...).

        Re-registering an existing key replaces its highlighter, so a custom
        language can override a built-in one. The type is immediately usable
        from ``:set filetype=`` and resolved by both extension key and the
        spec's language ``name``.  The keys are also pinned to the regex
        backend, so a deliberately registered declarative highlighter wins
        over the built-in tree-sitter registration for the same key.
        """
        register_language(spec, *extensions)
        prefer_regex(*extensions)

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

    def register(
        self, name: str, frames: Sequence[Sequence[str]], palette: Mapping[str, str]
    ) -> None:
        """Register screensaver character *name* from *frames* + *palette*.

        *frames* is a sequence of frames, each frame a sequence of pixel
        rows; *palette* maps the row characters to hex colors.  Both are
        copied by the registry, so tuples and lists both work.  Call once
        from ``setup``; the character joins the parade, playlist shuffling
        and the rc whitelist immediately.
        """
        register_character(
            name, tuple(tuple(rows) for rows in frames), dict(palette)
        )

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


@dataclass(frozen=True)
class StatusSegment:
    """One extension-contributed status bar segment (pull model).

    The status bar calls *provider* once per refresh pass and renders the
    returned string as the segment text; ``None`` or an empty string hides
    the segment for that pass.  *align* selects the bar half (``"left"``
    or ``"right"``); a higher *priority* sorts first within its half,
    ties keeping registration order.  The bar refreshes on every cursor
    move and mode change -- keep *provider* cheap (precompute heavier
    aggregations in event listeners instead).
    """

    id: str
    provider: Callable[[], str | None]
    align: SegmentAlign = "right"
    priority: int = 0


class UiExtensionBridge:
    """``api.ui`` -- UI elements contributed by extensions.

    Currently status bar segments only.  The bridge is a pull-model
    registry: :meth:`add_status_segment` / :meth:`remove_status_segment`
    mutate it, and the status bar widget (L2) pulls an alignment-filtered,
    priority-sorted snapshot on every refresh (:meth:`segments`).  The
    bridge never touches widgets itself.  Registrations made while a
    rollback scope is active are recorded through *record_undo*, so a
    failing ``setup`` also drops them (A13).
    """

    def __init__(
        self,
        record_undo: Callable[[Callable[[], None]], None],
    ) -> None:
        self._segments: dict[str, tuple[int, StatusSegment]] = {}
        self._counter = 0
        self._record_undo = record_undo

    def add_status_segment(self, segment: StatusSegment) -> None:
        """Register *segment* in the status bar registry.

        A duplicate id raises ``ValueError``.  Inside a rollback scope the
        registration is recorded (A13): rollback drops the segment again.
        """
        if segment.id in self._segments:
            raise ValueError(f"duplicate status segment id: {segment.id!r}")
        self._segments[segment.id] = (self._counter, segment)
        self._counter += 1

        def undo(segment: StatusSegment = segment) -> None:
            self._segments.pop(segment.id, None)

        self._record_undo(undo)

    def remove_status_segment(self, segment_id: str) -> None:
        """Drop the segment *segment_id* (``KeyError`` when unknown).

        Inside a rollback scope the removal is recorded (A13): rollback
        restores the removed entry with its original ordering.
        """
        entry = self._segments.pop(segment_id)

        def undo(
            segment_id: str = segment_id,
            entry: tuple[int, StatusSegment] = entry,
        ) -> None:
            self._segments[segment_id] = entry

        self._record_undo(undo)

    def segments(self, align: SegmentAlign) -> list[StatusSegment]:
        """Snapshot for bar half *align* (``"left"`` / ``"right"``).

        Sorted by descending priority, ties keeping registration order.
        The returned list is fresh (safe for the caller to hold); the
        segments themselves are frozen dataclasses.
        """
        entries = [
            (seq, segment)
            for seq, segment in self._segments.values()
            if segment.align == align
        ]
        entries.sort(key=lambda entry: (-entry[1].priority, entry[0]))
        return [segment for _seq, segment in entries]
