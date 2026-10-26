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
from typing import Any, Protocol

from yate.editor_syntax.tokens import Token
from yate.editor_syntax.ts_backend.languages import (
    LoadedLanguage,
    resolve,
    tree_sitter,
    tree_sitter_blocked,
)

__all__ = ["available_for", "tokenize_document"]

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
        cached = self._seen.get(byte_col)
        if cached is not None:
            return cached
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
