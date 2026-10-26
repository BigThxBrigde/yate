"""Tree-sitter highlighting: query captures to per-line tokens.

Call shape matches the regex backend (whole document in, one token list
per line out), so the view layer needs no special casing.  Strategy v1 is
a whole-document reparse per change: the view already debounces via
content-version invalidation and tokenizes off the UI thread, and
py-tree-sitter releases the GIL during parse.  Incremental
``Tree.edit()`` reparsing can be layered on later without changing this
call shape.

Capture resolution:

* capture names are mapped to SYNTAX_KINDS keys via the language's
  ``capture_map`` (unmapped captures inherit the default foreground);
* overlapping captures are resolved shortest-span-wins (a narrow capture
  inside a wide one repaints over it), matching the master-regex
  backend's flat, non-overlapping token output.  Captures covering the
  *exact same* span are resolved by :data:`_KIND_PRECEDENCE`; see
  :func:`_tokens_for_row`.

Tree-sitter points carry *byte* columns; every offset is converted to a
character column against the UTF-8 encoding of its line.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterator, Mapping
from types import SimpleNamespace
from typing import Any, Protocol

from yate.editor_syntax.tokens import Token
from yate.editor_syntax.ts_backend.languages import (
    LoadedLanguage,
    resolve,
    tree_sitter,
    tree_sitter_blocked,
)
from yate.logs import tracing

log = tracing.get_logger(__name__)

__all__ = ["IncrementalSession", "available_for", "tokenize_document"]

#: Reused ``tree_sitter.Parser`` per loaded ``tree_sitter.Language``.  A
#: Parser is stateless between ``parse()`` calls (verified against
#: py-tree-sitter 0.25: consecutive ``parse()`` calls on one parser give
#: independent trees), so one parser per language is built once instead of
#: per tokenize_document call.  ``Language`` is hashable and compares equal
#: for the same underlying grammar, so it is the natural cache key.
_PARSERS: dict[Any, Any] = {}


def available_for(filetype: str) -> bool:
    """Whether *filetype* can be highlighted with tree-sitter right now."""
    if tree_sitter_blocked():
        # Known heap-corrupting tree-sitter build: force the regex backend
        # even for grammars registered through the extension API.
        return False
    return resolve(filetype) is not None


def tokenize_document(lines: list[str], filetype: str) -> list[list[Token]]:
    """Highlight a whole document: one token list per input line."""
    loaded = resolve(filetype)
    if loaded is None or not lines:
        return [[] for _ in lines]
    return _highlight(lines, loaded)


def _highlight(lines: list[str], loaded: LoadedLanguage) -> list[list[Token]]:
    ts = tree_sitter()
    if ts is None:  # pragma: no cover - resolve() implies a working import
        return [[] for _ in lines]
    parser = _PARSERS.get(loaded.language)
    if parser is None:
        parser = ts.Parser(loaded.language)
        _PARSERS[loaded.language] = parser
    # The document is encoded exactly once: the joined line bytes feed the
    # parser and the same per-line list drives every column conversion.
    line_bytes = [line.encode("utf-8") for line in lines]
    tree = parser.parse(b"\n".join(line_bytes))
    captures = _query_captures(ts, loaded.query, tree.root_node)

    mappers = {row: _RowMapper(b) for row, b in enumerate(line_bytes)}
    # (char_start, char_end, kind) candidates per row, unsorted
    intervals: list[list[tuple[int, int, str]]] = [[] for _ in lines]
    for capture_name, nodes in captures.items():
        kind = loaded.capture_map.get(capture_name)
        if kind is None:
            continue
        for node in nodes:
            for row, start, end in _clip_to_rows(node, lines, line_bytes, mappers):
                intervals[row].append((start, end, kind))
    return [_tokens_for_row(ivs, len(line)) for line, ivs in zip(lines, intervals)]


def _query_captures(ts: Any, query: Any, node: Any) -> dict[str, list[Any]]:
    """Version-tolerant ``query.captures`` returning name -> nodes.

    py-tree-sitter >= 0.25 runs queries through ``QueryCursor``; 0.23/0.24
    expose ``Query.captures`` directly.  Both return a ``dict`` keyed by
    capture name.
    """
    cursor_cls = getattr(ts, "QueryCursor", None)
    if cursor_cls is not None:
        return dict(cursor_cls(query).captures(node))
    return dict(query.captures(node))


class _TsPoint(Protocol):
    row: int
    column: int


class _TsNode(Protocol):
    """The slice of the tree-sitter Node API the backend relies on."""

    start_point: _TsPoint
    end_point: _TsPoint


def _clip_to_rows(
    node: _TsNode,
    lines: list[str],
    line_bytes: list[bytes],
    mappers: Mapping[int, _RowMapper] | None = None,
) -> Iterator[tuple[int, int, int]]:
    """Split one capture node into per-row ``(row, char_start, char_end)``.

    Multi-line nodes (block comments, triple-quoted strings, heredocs)
    produce whole-line spans on the rows they cover, mirroring how the
    regex backend emits multiline constructs.  Byte columns are converted
    through the per-row :class:`_RowMapper` when one is supplied (the
    tokenize path, so repeated endpoints on a line decode only once);
    without one every endpoint falls back to the direct :func:`_to_char`
    decode.
    """
    r1, c1 = node.start_point.row, node.start_point.column
    r2, c2 = node.end_point.row, node.end_point.column
    last = len(lines) - 1
    if r1 > last:
        return
    if r2 > last:  # tree built from text that has since shrunk
        r2, c2 = last, len(line_bytes[last])
    if mappers is None:
        def char_col(row: int, byte_col: int) -> int:
            return _to_char(line_bytes[row], byte_col)
    else:
        def char_col(row: int, byte_col: int) -> int:
            return mappers[row].to_char(byte_col)
    if r1 == r2:
        yield r1, char_col(r1, c1), char_col(r1, c2)
        return
    yield r1, char_col(r1, c1), len(lines[r1])
    for row in range(r1 + 1, r2):
        yield row, 0, len(lines[row])
    yield r2, 0, char_col(r2, c2)


def _to_char(line_bytes: bytes, byte_col: int) -> int:
    """Convert a tree-sitter byte column to a character column.

    A byte column can land inside a multi-byte UTF-8 sequence (e.g. a
    stale offset after an edit): ``errors="ignore"`` then discards the
    incomplete trailing character -- its lone lead byte cannot decode on
    its own -- so such an offset maps to the first column of the character
    it cuts into.  Columns past the line end clamp to the line length.
    """
    if byte_col <= 0:
        return 0
    if byte_col >= len(line_bytes):
        byte_col = len(line_bytes)
    return len(line_bytes[:byte_col].decode("utf-8", errors="ignore"))


def _char_byte_bounds(line_bytes: bytes) -> list[int] | None:
    """Byte offsets of every UTF-8 character boundary, or ``None``.

    ``bounds[j]`` is the byte offset where the j-th character starts, with
    ``bounds[0] == 0`` and one entry per character plus the final end
    offset, so ``len(bounds) - 1`` is the character length of the line.
    Returns ``None`` when the line is not fully valid UTF-8; the caller
    then keeps using the lossy per-endpoint decode in :func:`_to_char`.
    """
    try:
        text = line_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None
    bounds = [0]
    total = 0
    for ch in text:
        codepoint = ord(ch)
        if codepoint < 0x80:
            total += 1
        elif codepoint < 0x800:
            total += 2
        elif codepoint < 0x10000:
            total += 3
        else:
            total += 4
        bounds.append(total)
    return bounds


class _RowMapper:
    """Per-row byte-column -> character-column converter.

    The first couple of distinct endpoints on a row keep the direct C
    prefix decode (:func:`_to_char`); once a row accumulates several
    (a busy highlighted line), the byte->character offset table is built
    once and every further lookup is a binary search.  All results are
    memoized, so repeated endpoints -- many captures over the same node --
    never decode twice.  The table path is exactly equivalent to the
    decode path for fully valid UTF-8 lines; invalid lines stay on the
    :func:`_to_char` path for good.
    """

    __slots__ = ("_line_bytes", "_seen", "_bounds", "_built")

    def __init__(self, line_bytes: bytes) -> None:
        self._line_bytes = line_bytes
        #: byte column -> character column, memoized lookups
        self._seen: dict[int, int] = {}
        self._bounds: list[int] | None = None
        self._built: bool = False

    def to_char(self, byte_col: int) -> int:
        """Character column for *byte_col* on this row."""
        if byte_col in self._seen:
            return self._seen[byte_col]
        if self._built:
            bounds = self._bounds
            result = (
                _table_to_char(bounds, byte_col)
                if bounds is not None
                else _to_char(self._line_bytes, byte_col)
            )
        else:
            result = _to_char(self._line_bytes, byte_col)
            if len(self._seen) >= 2:
                self._bounds = _char_byte_bounds(self._line_bytes)
                self._built = True
        self._seen[byte_col] = result
        return result


def _table_to_char(bounds: list[int], byte_col: int) -> int:
    """Table lookup matching :func:`_to_char` on a fully valid UTF-8 line.

    A column at a boundary maps to the character count before it; a column
    inside a character maps to the count of characters *fully contained*
    before it (the cut character is dropped, like ``errors="ignore"``
    would), and columns past the line end clamp to the line length.
    """
    if byte_col <= 0:
        return 0
    if byte_col >= bounds[-1]:
        return len(bounds) - 1
    return bisect_right(bounds, byte_col) - 1


#: Tie-break for captures covering the exact same span, winner first.
#: A tree-sitter query cannot express "this identifier is *not* a call", so
#: bundled queries keep a wide catch-all ``@property`` next to the narrow
#: ``@function.method`` it overlaps with, and rely on this table to pick a
#: winner.  The order is a hard rule rather than an accident of the dict
#: iteration order of ``QueryCursor.captures()``, which py-tree-sitter does
#: not document across versions.
#:
#: It is a *total* order over every SYNTAX_KINDS key, so no pair can end up
#: undecided: two same-span captures of equal rank would fall back to dict
#: order, which is exactly the non-determinism this table removes.
#: ``tests/test_ts_backend.py`` guards both properties.  Semantics from the top:
#: a call beats a plain name, a declared/element name beats the property
#: catch-all (``css.scm``'s ``(class_name) @type`` inside a pseudo-class
#: selector), a property key beats its bare string, and literals/comments --
#: which bundled queries never bind twice to one span -- come last.
#: Entries are *kinds*, not capture names: ``capture_map`` has already folded
#: ``function.call`` / ``type.builtin`` / ... onto their kind by the time an
#: interval reaches this table.
_KIND_PRECEDENCE: tuple[str, ...] = (
    "function",
    "type",
    "property",
    "builtin",
    "constant",
    "string",
    "number",
    "keyword",
    "decorator",
    "operator",
    "comment",
    "heading",
    "emphasis",
    "link",
)

#: Precomputed ranks: lower sorts first, i.e. wins the same-span contest.
_KIND_RANK: dict[str, int] = {kind: rank for rank, kind in enumerate(_KIND_PRECEDENCE)}

#: Rank for a kind outside the table.  Only reachable through an extension's own
#: ``capture_map`` (bundled queries are covered above), and shared by every such
#: kind, so a collision between two of them is undecided -- documented rather
#: than pretended away.
_KIND_RANK_OTHER: int = len(_KIND_PRECEDENCE)


#: Maximum number of disjoint changed row intervals handled with sequential
#: ``tree.edit`` calls before the session falls back to a whole-document
#: reparse.  Purely a defensive bound: a prefix/suffix-aligned line diff
#: yields a single interval, and even a jump-edit diff rarely exceeds this.
_MAX_EDIT_REGIONS: int = 4


def _tokens_from_tree(
    lines: list[str],
    line_bytes: list[bytes],
    loaded: LoadedLanguage,
    ts: Any,
    tree: Any,
) -> list[list[Token]]:
    """Run the capture pipeline against *tree* and return per-row tokens.

    Shared by the whole-document path and the incremental session: query
    captures over the full tree (queries have no incremental mode), clip
    them to rows with :class:`_RowMapper` byte tables built from
    *line_bytes*, then resolve overlaps per row.
    """
    captures = _query_captures(ts, loaded.query, tree.root_node)
    mappers = {row: _RowMapper(b) for row, b in enumerate(line_bytes)}
    intervals: list[list[tuple[int, int, str]]] = [[] for _ in lines]
    for capture_name, nodes in captures.items():
        kind = loaded.capture_map.get(capture_name)
        if kind is None:
            continue
        for node in nodes:
            for row, start, end in _clip_to_rows(node, lines, line_bytes, mappers):
                intervals[row].append((start, end, kind))
    return [_tokens_for_row(ivs, len(line)) for line, ivs in zip(lines, intervals)]


def _plan_regions(
    old_lines: tuple[str, ...], new_lines: list[str]
) -> list[tuple[int, int, int]] | None:
    """Diff two line snapshots into ``(start, old_end, new_end)`` regions.

    Common prefix and suffix rows are aligned first; rows outside them are
    identical by construction.  When the remaining middle has the same row
    count on both sides it is split further into maximal runs of differing
    rows (each run replaces an equal number of rows), otherwise the whole
    middle is one region.  Returns ``None`` when the documents are equal.
    """
    n, m = len(old_lines), len(new_lines)
    pre = 0
    while pre < n and pre < m and old_lines[pre] == new_lines[pre]:
        pre += 1
    suf = 0
    while (
        suf < n - pre
        and suf < m - pre
        and old_lines[n - 1 - suf] == new_lines[m - 1 - suf]
    ):
        suf += 1
    if pre == n and pre == m:
        return None
    old_mid_end = n - suf
    new_mid_end = m - suf
    if old_mid_end - pre == new_mid_end - pre:
        regions: list[tuple[int, int, int]] = []
        i = pre
        while i < old_mid_end:
            if old_lines[i] == new_lines[i]:
                i += 1
                continue
            j = i
            while j < old_mid_end and old_lines[j] != new_lines[j]:
                j += 1
            regions.append((i, j, j))
            i = j
        return regions
    return [(pre, old_mid_end, new_mid_end)]


def _common_prefix_len(a: str, b: str) -> int:
    """Length of the longest common character prefix of *a* and *b*."""
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[i] == b[i]:
        i += 1
    return i


def _common_suffix_len(a: str, b: str) -> int:
    """Length of the longest common character suffix of *a* and *b*."""
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[len(a) - 1 - i] == b[len(b) - 1 - i]:
        i += 1
    return i


def _bytes_before(line_bytes: list[bytes], row: int) -> int:
    """UTF-8 byte offset of the start of *row* (each line owns its newline)."""
    return sum(len(b) + 1 for b in line_bytes[:row])


class IncrementalSession:
    """Reusable incremental-parse state for one document stream.

    Holds the previous parse tree together with its line snapshot and a
    per-line UTF-8 byte cache (which doubles as the byte source for the
    capture pipeline, so unchanged lines are never re-encoded).  Each
    :meth:`update` diffs the incoming lines against the snapshot, applies
    at most :data:`_MAX_EDIT_REGIONS` ``tree.edit`` calls in document
    order, and reparses with the previous tree so tree-sitter only reuses
    unchanged subtrees.  Any internal failure degrades to a
    whole-document reparse and never raises to the caller.
    """

    __slots__ = ("filetype", "_lines", "_old_line_bytes", "_tree")

    def __init__(self, filetype: str) -> None:
        self.filetype = filetype
        self._lines: tuple[str, ...] = ()
        self._old_line_bytes: list[bytes] = []
        # Any: py-tree-sitter ships no type stubs (same precedent as _PARSERS).
        self._tree: Any | None = None

    def update(self, lines: list[str], filetype: str) -> list[list[Token]]:
        """Tokenize *lines* incrementally: one token list per input line.

        Same call shape and output contract as :func:`tokenize_document`.
        A filetype mismatch, a missing tree or any internal error takes the
        whole-document path, which rebuilds the snapshot from scratch, so
        the session always self-heals.
        """
        try:
            return self._update(lines, filetype)
        except Exception:  # noqa: BLE001 - degraded highlight must never
            # kill the caller's edit flow; fall back to a full reparse
            log.warning(
                "incremental parse failed for %s; falling back to a full"
                " reparse",
                filetype,
                exc_info=True,
            )
            self._tree = None
            try:
                return self._update(lines, filetype)
            except Exception:  # noqa: BLE001 - last resort: plain text
                log.warning(
                    "full reparse failed for %s; returning plain text",
                    filetype,
                    exc_info=True,
                )
                return [[] for _ in lines]

    def _reset(self, lines: list[str]) -> list[bytes]:
        """Rebuild the snapshot for *lines* and return its byte cache."""
        self._lines = tuple(lines)
        line_bytes = [line.encode("utf-8") for line in lines]
        self._old_line_bytes = line_bytes
        return line_bytes

    def _full(
        self, lines: list[str], filetype: str, loaded: LoadedLanguage, ts: Any
    ) -> list[list[Token]]:
        """Whole-document path: reparse from scratch and rebuild state."""
        self.filetype = filetype
        line_bytes = self._reset(lines)
        if not lines:
            self._tree = None
            return []
        parser = _PARSERS.get(loaded.language)
        if parser is None:
            parser = ts.Parser(loaded.language)
            _PARSERS[loaded.language] = parser
        tree = parser.parse(b"\n".join(line_bytes))
        self._tree = tree
        return _tokens_from_tree(lines, line_bytes, loaded, ts, tree)

    def _update(self, lines: list[str], filetype: str) -> list[list[Token]]:
        """Incremental body of :meth:`update` (may raise on broken input)."""
        loaded = resolve(filetype)
        if loaded is None:
            self._reset(lines)
            self._tree = None
            return [[] for _ in lines]
        ts = tree_sitter()
        if ts is None:  # pragma: no cover - resolve() implies a working import
            self._reset(lines)
            self._tree = None
            return [[] for _ in lines]
        tree = self._tree
        if tree is None or filetype != self.filetype:
            return self._full(lines, filetype, loaded, ts)
        if not lines:
            self._reset(lines)
            self._tree = None
            return []
        old = self._lines
        old_bytes = self._old_line_bytes
        regions = _plan_regions(old, lines)
        if regions is None:
            # Defensive: the caller's version gate should prevent no-op
            # updates; re-tokenize the current tree instead of guessing.
            return _tokens_from_tree(lines, old_bytes, loaded, ts, tree)
        if len(regions) > _MAX_EDIT_REGIONS:
            return self._full(lines, filetype, loaded, ts)
        new_bytes = [
            old_bytes[i] if i < len(old) and old[i] == line else line.encode("utf-8")
            for i, line in enumerate(lines)
        ]
        parser = _PARSERS.get(loaded.language)
        if parser is None:
            parser = ts.Parser(loaded.language)
            _PARSERS[loaded.language] = parser
        delta_bytes = 0
        delta_rows = 0
        for start_row, old_end_row, new_end_row in regions:
            edit = _region_edit(
                old, lines, old_bytes, new_bytes, start_row, old_end_row, new_end_row
            )
            # Coordinates of later regions shift by the byte/row deltas of
            # the earlier ones: each tree.edit moves the tree onto the
            # intermediate text, so edits are expressed against that state.
            tree.edit(
                edit.start_byte + delta_bytes,
                edit.old_end_byte + delta_bytes,
                edit.new_end_byte + delta_bytes,
                (edit.start_row + delta_rows, edit.start_col),
                (edit.old_end_row + delta_rows, edit.old_end_col),
                (edit.new_end_row + delta_rows, edit.new_end_col),
            )
            delta_bytes += edit.new_end_byte - edit.old_end_byte
            delta_rows += new_end_row - old_end_row
        new_tree = parser.parse(b"\n".join(new_bytes), tree)
        tokens = _tokens_from_tree(lines, new_bytes, loaded, ts, new_tree)
        self._lines = tuple(lines)
        self._old_line_bytes = new_bytes
        self._tree = new_tree
        return tokens


def _region_edit(
    old_lines: tuple[str, ...],
    new_lines: list[str],
    old_bytes: list[bytes],
    new_bytes: list[bytes],
    start_row: int,
    old_end_row: int,
    new_end_row: int,
) -> Any:
    """Compute one region's edit parameters in snapshot coordinates.

    Returns an object with ``start_byte`` / ``old_end_byte`` /
    ``new_end_byte`` (byte offsets relative to the unedited snapshot text)
    and the three ``(row, byte_col)`` points of the edit.  An empty side
    (pure insertion or pure deletion) is spanned by whole boundary lines;
    otherwise a character level common prefix/suffix refinement of the
    boundary lines shrinks the span to the smallest span whose outside is
    identical in both texts.  ``Any`` return: a small private record, kept
    shapeless to stay clear of the R2 protocol freeze (no stubs exist for
    this either way).
    """
    if old_end_row == start_row:
        # Pure insertion: new rows start_row..new_end_row-1 appear between
        # old rows start_row-1 and start_row; the span has zero old width.
        if start_row == len(old_lines):
            # Append at EOF: anchor on the end of the last old line, the
            # inserted text starts with its own leading newline.
            start_byte = _bytes_before(old_bytes, start_row - 1) + len(
                old_bytes[start_row - 1]
            )
            return SimpleNamespace(
                start_byte=start_byte,
                old_end_byte=start_byte,
                new_end_byte=start_byte
                + 1
                + sum(len(new_bytes[i]) + 1 for i in range(start_row, new_end_row)),
                start_row=start_row - 1,
                old_end_row=start_row - 1,
                new_end_row=new_end_row - 1,
                start_col=len(old_bytes[start_row - 1]),
                old_end_col=len(old_bytes[start_row - 1]),
                new_end_col=len(new_bytes[new_end_row - 1]),
            )
        start_byte = _bytes_before(old_bytes, start_row)
        return SimpleNamespace(
            start_byte=start_byte,
            old_end_byte=start_byte,
            new_end_byte=start_byte
            + sum(len(new_bytes[i]) + 1 for i in range(start_row, new_end_row)),
            start_row=start_row,
            old_end_row=start_row,
            new_end_row=new_end_row - 1,
            start_col=0,
            old_end_col=0,
            new_end_col=len(new_bytes[new_end_row - 1]),
        )
    if new_end_row == start_row:
        # Pure deletion: old rows start_row..old_end_row-1 disappear; the
        # span has zero new width.
        start_byte = _bytes_before(old_bytes, start_row)
        return SimpleNamespace(
            start_byte=start_byte,
            old_end_byte=start_byte
            + sum(len(old_bytes[i]) + 1 for i in range(start_row, old_end_row)),
            new_end_byte=start_byte,
            start_row=start_row,
            old_end_row=old_end_row - 1,
            new_end_row=start_row,
            start_col=0,
            old_end_col=len(old_bytes[old_end_row - 1]),
            new_end_col=0,
        )
    first_old = old_lines[start_row]
    first_new = new_lines[start_row]
    prefix = _common_prefix_len(first_old, first_new)
    last_old = old_lines[old_end_row - 1]
    last_new = new_lines[new_end_row - 1]
    suffix = _common_suffix_len(last_old, last_new)
    # Keep the refined prefix and suffix from overlapping on a boundary
    # line that is also the region's first and last line.
    if old_end_row - 1 == start_row:
        suffix = min(suffix, len(last_old) - prefix)
    if new_end_row - 1 == start_row:
        suffix = min(suffix, len(last_new) - prefix)
    start_col = len(first_old[:prefix].encode("utf-8"))
    old_end_col = len(last_old[: len(last_old) - suffix].encode("utf-8"))
    new_end_col = len(last_new[: len(last_new) - suffix].encode("utf-8"))
    start_byte = _bytes_before(old_bytes, start_row) + start_col
    if old_end_row - 1 == start_row:
        old_end_byte = start_byte + old_end_col - start_col
    else:
        old_end_byte = (
            start_byte
            + len(old_bytes[start_row])
            - start_col
            + 1
            + sum(len(old_bytes[i]) + 1 for i in range(start_row + 1, old_end_row - 1))
            + old_end_col
        )
    if new_end_row - 1 == start_row:
        new_end_byte = start_byte + new_end_col - start_col
    else:
        new_end_byte = (
            start_byte
            + len(new_bytes[start_row])
            - start_col
            + 1
            + sum(len(new_bytes[i]) + 1 for i in range(start_row + 1, new_end_row - 1))
            + new_end_col
        )
    return SimpleNamespace(
        start_byte=start_byte,
        old_end_byte=old_end_byte,
        new_end_byte=new_end_byte,
        start_row=start_row,
        old_end_row=old_end_row - 1,
        new_end_row=new_end_row - 1,
        start_col=start_col,
        old_end_col=old_end_col,
        new_end_col=new_end_col,
    )


def _tokens_for_row(
    intervals: list[tuple[int, int, str]], line_len: int
) -> list[Token]:
    """Resolve overlapping capture spans into flat, non-overlapping tokens.

    Ordering is deterministic for everything a bundled query can produce:
    shorter spans claim their range first (nested captures win over the
    enclosing one), spans starting earlier win over later ones, and captures
    covering the *same* span are decided by the total order in
    :data:`_KIND_PRECEDENCE`.  Only a kind that reached the backend through an
    extension's own ``capture_map`` can share a rank with another, and that
    pair stays undecided (see :data:`_KIND_RANK_OTHER`).  Gaps between claimed
    ranges are then filled by wider spans; adjacent runs of the same kind are
    merged.
    """
    if not intervals:
        return []
    claimed = bytearray(line_len)
    flat: list[tuple[int, int, str]] = []
    for start, end, kind in sorted(
        intervals,
        key=lambda iv: (iv[1] - iv[0], iv[0], _KIND_RANK.get(iv[2], _KIND_RANK_OTHER)),
    ):
        start = max(0, start)
        end = min(end, line_len)
        if end <= start:
            continue
        seg_start: int | None = None
        for i in range(start, end):
            if claimed[i]:
                if seg_start is not None:
                    flat.append((seg_start, i, kind))
                    seg_start = None
            elif seg_start is None:
                seg_start = i
        if seg_start is not None:
            flat.append((seg_start, end, kind))
            seg_start = None
        for i in range(start, end):
            claimed[i] = 1
    flat.sort()
    tokens: list[Token] = []
    for start, end, kind in flat:
        if tokens and tokens[-1].end == start and tokens[-1].kind == kind:
            tokens[-1] = Token(tokens[-1].start, end, kind)
        else:
            tokens.append(Token(start, end, kind))
    return tokens
