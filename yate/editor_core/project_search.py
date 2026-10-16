"""Project-wide search primitives over plain line lists.

File traversal, decoding and disk-write policy belong to the caller (L0
pure text algorithms; no Textual, no Workspace import).  :func:`compile_query`
is the single source of compile semantics; :class:`SearchEngine` delegates
to it, so the buffer search and the project search can never drift apart.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from yate.logs import tracing

log = tracing.get_logger(__name__)

#: Called with the number of files scanned so far (worker progress).
type ProgressFn = Callable[[int], None]


@dataclass(frozen=True)
class LineMatch:
    """One hit inside a file: 0-based row plus start/end columns."""

    row: int
    start: int
    end: int


@dataclass(frozen=True)
class FileMatch:
    """All hits in one file, in document order, plus their line texts."""

    path: Path
    matches: list[LineMatch]
    #: text of each hit row (newline-only view, ``\r`` tail kept) keyed by
    #: row, so callers can render snippets without re-reading the file
    hit_lines: dict[int, str] = field(default_factory=dict[int, str])


def compile_query(
    query: str,
    *,
    case_sensitive: bool = False,
    use_regex: bool = False,
    whole_word: bool = False,
) -> re.Pattern[str] | None:
    """Compile *query* into a search pattern, or return ``None``.

    Single source of compile semantics; :class:`SearchEngine` delegates
    here.  An empty *query* yields ``None``; without *use_regex* the query
    is matched literally via :func:`re.escape`; *whole_word* wraps the
    pattern with word-boundary lookarounds; an invalid regular expression
    yields ``None`` instead of raising.
    """
    if query == "":
        return None
    pattern = query if use_regex else re.escape(query)
    if whole_word:
        pattern = rf"(?:(?<=\W)|^){pattern}(?=\W|$)"
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(pattern, flags)
    except re.error:
        return None


def search_lines(
    lines: Sequence[str], pattern: re.Pattern[str]
) -> list[LineMatch]:
    """Collect every non-empty match of *pattern* across *lines*.

    Zero-length matches are skipped, mirroring the ``SearchEngine.update``
    guard, so patterns like ``a*`` never produce phantom hits.
    """
    matches: list[LineMatch] = []
    for row, line in enumerate(lines):
        for found in pattern.finditer(line):
            if found.start() == found.end():
                continue
            matches.append(LineMatch(row, found.start(), found.end()))
    return matches


def search_files(
    paths: Sequence[Path],
    query: str,
    *,
    case_sensitive: bool = False,
    use_regex: bool = False,
    whole_word: bool = False,
    max_file_bytes: int = 2_000_000,
    max_matches: int = 2000,
    progress: ProgressFn | None = None,
) -> list[FileMatch]:
    """Search the given files and return one :class:`FileMatch` per hit file.

    Unreadable files (``OSError``), files larger than *max_file_bytes* and
    files that are not valid UTF-8 (binary and foreign-encoding files) are
    skipped.  Each hit file also carries ``hit_lines`` -- the raw text of
    every hit row -- so snippet rendering needs no second read.  Collection
    stops once *max_matches* hits have been gathered; *progress* is called
    with the number of files scanned so far after each file, skipped ones
    included.
    """
    pattern = compile_query(
        query,
        case_sensitive=case_sensitive,
        use_regex=use_regex,
        whole_word=whole_word,
    )
    if pattern is None:
        return []
    results: list[FileMatch] = []
    total = 0
    for done, path in enumerate(paths, start=1):
        matches, hit_lines = _search_one_file(
            path, pattern, max_file_bytes, max_matches - total
        )
        if matches:
            total += len(matches)
            results.append(FileMatch(path, matches, hit_lines))
        if progress is not None:
            progress(done)
        if total >= max_matches:
            log.debug("project search stopped at %d matches", max_matches)
            break
    return results


def _search_one_file(
    path: Path, pattern: re.Pattern[str], max_file_bytes: int, budget: int
) -> tuple[list[LineMatch], dict[int, str]]:
    """Search one file and return at most *budget* hits plus their texts.

    Lines are split on ``"\\n"`` only -- the ``TextBuffer`` view -- so hit
    rows/columns line up with both buffer-side search and ``replace_lines``.
    The second element maps each hit row to its raw line text (same view,
    ``\r`` tail kept).  Returns empty results when the file is unreadable,
    oversized, not decodable as UTF-8 or simply has no matches.
    """
    try:
        data = path.read_bytes()
    except OSError:
        log.debug("project search skipped unreadable file %s", path)
        return [], {}
    if len(data) > max_file_bytes:
        return [], {}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        log.debug("project search skipped non-utf8 file %s", path)
        return [], {}
    lines = text.split("\n")
    matches = search_lines(lines, pattern)[:budget]
    return matches, {m.row: lines[m.row] for m in matches}


def replace_lines(
    lines: list[str], pattern: re.Pattern[str], replacement: str
) -> tuple[list[str], int]:
    """Replace every match of *pattern* in *lines*; return new lines + count.

    The replacement is expanded per match against the matched text alone
    (the ``SearchEngine.replace_all`` backreference semantics), then the
    pieces are concatenated into the new line.  Lines without matches are
    kept as-is.  When nothing matches at all, *lines* is returned unchanged
    -- the very same object -- so callers can use ``is`` to skip writing
    files that have no changes.  Because the expansion sees only the matched
    span, patterns whose assertions reach beyond it (``(?<=@)foo``) may keep
    the text yet still bump the count -- the same trade-off
    ``SearchEngine.replace_all`` makes.
    """
    count = 0
    out: list[str] = []
    for line in lines:
        matches = search_lines([line], pattern)
        if not matches:
            out.append(line)
            continue
        pieces: list[str] = []
        last = 0
        for match in matches:
            pieces.append(line[last : match.start])
            pieces.append(pattern.sub(replacement, line[match.start : match.end]))
            last = match.end
            count += 1
        pieces.append(line[last:])
        out.append("".join(pieces))
    if count == 0:
        return lines, 0
    return out, count
