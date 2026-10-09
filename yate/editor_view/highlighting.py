"""Syntax-highlight cache and background tokenize passes for the editor view.

Extracted from :mod:`yate.editor_view.editor` (big-module-split wave c): the
mixin owns the ``_hl_*`` token cache, the trailing debounce window, the
background tokenize worker and the synchronous edited-row resync.  It is
combined into :class:`EditorView` (``EditorView(ScrollView, HighlightMixin)``),
which supplies the ``doc`` property and the render-path consumers; this module
imports nothing else from its package.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Self

from textual.geometry import Region
from textual.timer import Timer, TimerCallback
from textual.worker import WorkType, Worker

from yate.editor_core.document import Document
from yate.editor_core.search import Match
from yate.editor_syntax.engine import tokenize_document_with_states
from yate.editor_syntax.engine import tokenize_line_sync
from yate.editor_syntax.tokens import Token
from yate.logs import tracing

log = tracing.get_logger(__name__)


def _tokenize_with_states(
    lines: list[str], filetype: str
) -> tuple[list[list[Token]], tuple[int, ...]]:
    """Tokenize a whole document plus the regex multiline state per row.

    Runs inside the highlight worker thread.  The states are what
    :meth:`EditorView._rebuild_tokens_on_edit` resumes from after an
    edit -- they are intentionally regex-native even when the tokens came
    from tree-sitter, because the row-level resync re-tokenizes with the
    regex backend.  With the regex backend the combined engine pass
    produces both artifacts in one scan; the tree-sitter path threads the
    states in a guarded regex companion pass (a broken custom LangSpec
    keeps prior states instead of killing the worker pass).
    """
    return tokenize_document_with_states(lines, filetype)


@dataclass(frozen=True)
class HighlightProbe:
    """Read-only snapshot of the syntax-highlight cache (tests/debugging).

    Mirrors the private ``_hl_*`` attributes of :class:`EditorView` so tests
    and tools can assert highlighter state without reaching into privates;
    as a frozen record it offers no way to mutate the widget.
    """

    #: Cached tokens per buffer row (``None`` until the first pass lands).
    tokens: list[list[Token]] | None
    #: Document the cached tokens belong to (``None`` until the first pass).
    doc: Document | None
    #: Buffer content version the cached tokens were tokenized at.
    version: int
    #: Filetype the cached tokens were tokenized for.
    filetype: str
    #: (doc, filetype, version) of the pass waiting to run / in flight.
    scheduled_key: tuple[object, str, int] | None
    #: Debounce timer reference (``None`` when nothing is deferred).
    timer: Timer | None


class HighlightMixin:
    """Syntax-highlight cache and worker scheduling, mixed into EditorView.

    A plain mixin: :class:`EditorView` combines it with ``ScrollView``
    (``EditorView(ScrollView, HighlightMixin)``).  The mixin deliberately
    does not inherit ``Widget`` -- a class inheriting both ``Widget`` and
    ``ScrollView`` resurfaces Textual's internal ``scroll_to`` signature
    split (``ScrollView.scroll_to`` lacks ``release_anchor``) as a pyright
    conflict in the host class.  Because the plain mixin lands *after*
    ``Widget`` in the host's MRO, the host-surface stubs below never
    shadow the real Textual methods at runtime; they exist only so the
    mixin's methods type-check standalone.
    """

    # Trailing debounce window that merges rapid keystrokes into a single
    # background tokenize pass (same order of magnitude as the 0.12s
    # completion popup debounce).
    _HIGHLIGHT_DEBOUNCE_S = 0.08

    # --------------------------------------------------- host surface
    # Declaration-only stubs mirroring the Textual widget members the
    # highlighter uses; the host widget supplies the real implementations
    # (and the pane document via its ``doc`` property).

    @property
    def doc(self) -> Document:
        """The pane document; provided by the host widget (:class:`EditorView`)."""
        raise NotImplementedError

    @property
    def is_mounted(self) -> bool:
        """Whether the host widget is mounted (mirrors ``Widget.is_mounted``)."""
        raise NotImplementedError

    def refresh(
        self,
        *regions: Region,
        repaint: bool = True,
        layout: bool = False,
        recompose: bool = False,
    ) -> Self:
        """Repaint the host widget (mirrors ``Widget.refresh``)."""
        raise NotImplementedError

    def set_timer(
        self,
        delay: float,
        callback: TimerCallback | None = None,
        *,
        name: str | None = None,
        pause: bool = False,
    ) -> Timer:
        """Arm a debounce timer on the host widget (mirrors ``set_timer``)."""
        raise NotImplementedError

    def run_worker[ResultType](
        self,
        work: WorkType[ResultType],
        name: str | None = "",
        group: str = "default",
        description: str = "",
        exit_on_error: bool = True,
        start: bool = True,
        exclusive: bool = False,
        thread: bool = False,
    ) -> Worker[ResultType]:
        """Start a worker on the host widget (mirrors ``DOMNode.run_worker``)."""
        raise NotImplementedError

    def _init_highlight_state(self) -> None:
        """Initialize the token cache and search-match bucket fields."""
        # Syntax token cache. Tokens belong to (doc, content_version,
        # filetype); pure cursor/scroll movement leaves the version alone,
        # so moving through a file keeps its colors. After an edit the
        # previous tokens keep coloring the text for one debounce window
        # instead of flashing the whole view uncolored.
        # Search-match buckets for the render path (see _matches_for_row):
        # keyed on the matches *list object* identity, which SearchEngine
        # replaces wholesale on every update.
        self._match_buckets: tuple[
            list[Match], dict[int, list[tuple[int, Match]]]
        ] | None = None
        self._hl_tokens: list[list[Token]] | None = None
        self._hl_doc: Document | None = None
        self._hl_version: int = -1
        self._hl_filetype: str = ""
        # Per-row text snapshot + regex multiline state sequence, written
        # together with every _hl_tokens assignment (single-writer
        # discipline): _rebuild_tokens_on_edit diffs the current lines
        # against the snapshot to reuse unchanged rows and resumes the
        # multiline state machine at the first changed row.
        self._hl_line_snapshot: tuple[str, ...] | None = None
        self._hl_ml_states: tuple[int, ...] | None = None
        # Pending/in-flight highlight pass, keyed by (doc, filetype,
        # content_version). _hl_timer is set only while a debounced pass is
        # still waiting to start; the key survives until the worker stores
        # its result, so renders can never schedule a duplicate pass for a
        # version that is already being tokenized.
        self._hl_timer: Timer | None = None
        self._hl_scheduled_key: tuple[object, str, int] | None = None

    def _tokens_for(self, row: int) -> list[Token]:
        """Cached syntax tokens for one line (tokenized off the loop).

        The first render of a document shows plain text while a worker
        thread tokenizes it, then refreshes with colors; this keeps large
        files from blocking the first paint. The cache survives cursor
        movement and scrolling -- it is only stale when the document, its
        content version or its filetype differ. After an edit the previous
        tokens keep coloring the text for one debounce window (no plain
        flash) while :meth:`_rebuild_tokens_on_edit` resyncs the edited
        rows synchronously; a doc/filetype switch never reuses the old
        tokens.
        """
        doc = self.doc
        buf = doc.buffer
        if (
            self._hl_tokens is None
            or self._hl_doc is not doc
            or self._hl_version != buf.content_version
            or self._hl_filetype != doc.filetype
        ):
            tokens = self._hl_tokens
            if tokens is None or self._hl_doc is not doc or self._hl_filetype != doc.filetype:
                # First paint or doc/filetype switch: drop any row snapshot
                # carried over from the previous document before the fresh
                # pass replaces the cache.
                self._hl_line_snapshot = None
                self._hl_ml_states = None
                self._schedule_highlight(0.0)
                return []
            # Same doc and filetype, version behind: keep coloring from the
            # previous tokens until the debounced pass replaces them, and
            # resync the edited rows on the spot so token boundaries match
            # the current text during the wait.
            self._schedule_highlight(self._HIGHLIGHT_DEBOUNCE_S)
            return self._rebuild_tokens_on_edit(row)
        return self._hl_tokens[row] if row < len(self._hl_tokens) else []

    def _rebuild_tokens_on_edit(self, row: int) -> list[Token]:
        """Resync edited rows synchronously while the worker pass pends.

        The stale tokens returned during the debounce window are computed
        from the pre-edit text, so every token ending at or past the edit
        point colors the newly typed characters with a shifted boundary --
        the end-of-line flicker. This diffs the current lines against the
        row snapshot left by the last finished pass and re-tokenizes only
        the changed rows (plus rows whose multiline state they carry) with
        the microsecond-fast regex backend; unchanged rows reuse the cached
        tokens verbatim. The rebuilt cache is written back together with
        fresh snapshots (same write site as the worker's, keeping the
        single-writer discipline), so later renders of the same version skip
        the diff and the debounced worker still replaces everything with
        exact tokens.

        Reuse is per row and shift-aware: new row r maps to cache row
        j = r - delta (delta = line-count change), and whenever the row
        text is unchanged and the threaded multiline state equals the state
        the cached tokens were built from, the cached tokens are reused
        verbatim (O(1) per row) -- so a line-inserting edit only pays real
        tokenization for rows whose text or surrounding construct actually
        changed, and rows below an inserted blank line reuse instantly
        instead of re-tokenizing to end of file. Without a usable
        snapshot, or when the line count shifted drastically (> 5 rows),
        this degrades to plain stale reuse.
        """
        tokens = self._hl_tokens
        snapshot = self._hl_line_snapshot
        ml_states = self._hl_ml_states
        doc = self.doc
        buf = doc.buffer
        if tokens is None:
            return []
        if (
            snapshot is None
            or ml_states is None
            or abs(len(snapshot) - buf.line_count) > 5
        ):
            # No usable snapshot (startup / doc switch) or a drastic line
            # count change: plain stale reuse until the worker replaces the
            # cache (rows past the end of the old tokens stay plain).
            return tokens[row] if row < len(tokens) else []

        lines = buf.lines
        cur_count = buf.line_count
        common = min(len(snapshot), cur_count)
        changed = {i for i in range(common) if snapshot[i] != lines[i]}
        changed.update(range(common, cur_count))
        if not changed:
            # Version bumped without any line changing (out-of-band mark):
            # the cached tokens still match the text exactly, so record the
            # version here too -- without this the version-staleness check
            # in :meth:`_tokens_for` would re-run the O(lines) diff on
            # every render until the worker replaces the cache.
            self._hl_version = buf.content_version
            return tokens[row] if row < len(tokens) else []

        first = min(changed)
        delta = cur_count - len(snapshot)
        # Rows above the first change are identical to the snapshot, so the
        # multiline state entering the changed region carries over verbatim.
        state = ml_states[first - 1] if 0 < first <= len(ml_states) else 0
        rebuilt: list[list[Token]] = list(tokens[:first])
        states: list[int] = list(ml_states[:first])
        r = first
        while r < cur_count:
            # Shift-aware cache row: below the edited region, new row r
            # holds old row r - delta's text (mismatches fall through to a
            # fresh tokenization, so a wrong mapping can only cost work).
            j = r - delta
            if (
                0 <= j < len(tokens)
                and lines[r] == snapshot[j]
                and state == (ml_states[j - 1] if j > 0 else 0)
            ):
                # Text unchanged and the threaded state matches the state the
                # cached tokens were built from: reuse them verbatim and jump
                # to the recorded next state -- O(1) per row, which keeps
                # line-inserting edits cheap on large files.
                state = ml_states[j]
                rebuilt.append(tokens[j])
                states.append(state)
                r += 1
                continue
            try:
                row_tokens, state = tokenize_line_sync(
                    lines[r], doc.filetype, state
                )
            except Exception:  # noqa: BLE001 - the render path must never
                # crash on a broken custom LangSpec; the row falls back to
                # its stale tokens and the carried state stays unchanged
                log.debug("sync retokenize failed on row %d", r)
                row_tokens = tokens[r] if r < len(tokens) else []
            rebuilt.append(row_tokens)
            states.append(state)
            r += 1

        self._hl_tokens = rebuilt
        self._hl_version = buf.content_version
        self._hl_line_snapshot = tuple(lines)
        self._hl_ml_states = tuple(states)
        return rebuilt[row] if row < len(rebuilt) else []

    def tokens_for(self, row: int) -> list[Token]:
        """Public accessor for one row's syntax tokens (render-path lookup).

        The same lookup the renderer performs for every row; it may schedule
        a background tokenize pass when the cache is stale, so calling it
        outside a render is exactly like rendering the row.  Exists so tests
        and tools can inspect tokens without touching private methods.
        """
        return self._tokens_for(row)

    def highlight_probe(self) -> HighlightProbe:
        """Return a read-only snapshot of the highlight cache state."""
        return HighlightProbe(
            tokens=self._hl_tokens,
            doc=self._hl_doc,
            version=self._hl_version,
            filetype=self._hl_filetype,
            scheduled_key=self._hl_scheduled_key,
            timer=self._hl_timer,
        )

    def _schedule_highlight(self, delay: float) -> None:
        """Arrange a tokenize pass for the current doc/filetype/version.

        Keyed by (doc, filetype, content_version): repeated calls for the
        same state keep the existing timer or in-flight worker, only a new
        edit restarts the trailing debounce window.
        """
        doc = self.doc
        key = (doc, doc.filetype, doc.buffer.content_version)
        if self._hl_scheduled_key == key:
            return
        if self._hl_timer is not None:
            self._hl_timer.stop()
            self._hl_timer = None
        self._hl_scheduled_key = key
        if delay > 0.0:
            self._hl_timer = self.set_timer(
                delay, self._launch_highlight, name="highlight-debounce"
            )
        else:
            # No grace period (first paint / doc or filetype switch): start
            # tokenizing right away so the first paint gets colored ASAP.
            self._launch_highlight()

    def _launch_highlight(self) -> None:
        """Timer callback: hand the pending pass to the tokenizer worker.

        Deliberately does not clear ``_hl_timer``: a stopped timer's
        already-queued callback can still fire after a newer timer was
        scheduled, and clobbering the reference here would lose the newer
        pending timer. A fired timer is inert (``stop()`` is a no-op), and
        duplicate passes are prevented by the scheduled-key guard plus the
        exclusive worker group.
        """
        if not self.is_mounted:
            return
        # Keyed to *this* widget (not the app) so concurrent panes do
        # not cancel each other's highlight passes.  The coroutine
        # *function* is passed, not an eager coroutine: if the pump is
        # closing, the worker never starts and an eager coroutine would
        # leak ("was never awaited" RuntimeWarning).
        self.run_worker(
            self._highlight_later, group="highlight",
            exclusive=True, exit_on_error=False,
        )

    async def _highlight_later(self) -> None:
        """Tokenize the current document in a thread, then repaint."""
        doc = self.doc
        buf = doc.buffer
        # shallow copy: the buffer may keep mutating while the thread runs
        lines = list(buf.lines)
        filetype = doc.filetype
        version = buf.content_version
        tokens, ml_states = await asyncio.to_thread(
            _tokenize_with_states, lines, filetype
        )
        if not self.is_mounted:
            return
        # discard the result if the document changed/closed while we worked;
        # a repaint reschedules a fresh pass for the current state
        if self.doc is not doc or buf.content_version != version:
            self.refresh()
            # Re-schedule immediately: the discarded pass must not cost an
            # extra debounce window on top of the time already spent
            # tokenizing.  The stale tokens keep coloring meanwhile (no
            # flash), and the worker group is exclusive, so this cannot
            # stack up concurrent tokenize passes.
            self._schedule_highlight(0.0)
            return
        self._hl_tokens = tokens
        self._hl_doc = doc
        self._hl_version = version
        self._hl_filetype = filetype
        # The row snapshot and multiline states ride along with every cache
        # write (they are only ever stored here and in
        # _rebuild_tokens_on_edit, always together with _hl_tokens).
        self._hl_line_snapshot = tuple(lines)
        self._hl_ml_states = ml_states
        if self._hl_scheduled_key == (doc, filetype, version):
            self._hl_scheduled_key = None
        self.refresh()
