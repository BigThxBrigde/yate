"""Pure data layer for the file manager: sorting, filtering, rows, status.

Every function is a plain function over
:class:`~yate.services.workspace.Entry` / :class:`~yate.services.workspace.EntryStat`
values; theme colors are passed in as strings (the ``accent`` parameter)
so the Screen consumes these helpers without dragging UI state in here.
Row coloring is emitted as :class:`rich.text.Text` spans, ready for
direct ListView use.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from stat import filemode
from typing import Literal

from rich.text import Text

from yate.editor_view.icons import icon_color, icon_for_path
from yate.services.workspace import Entry, EntryStat, Workspace, human_size

#: Sort keys cycled by the file manager's ``s`` key.
type SortKey = Literal["name", "size", "mtime"]

#: Order in which :func:`next_sort` cycles through the sort keys.
SORT_CYCLE: tuple[SortKey, ...] = ("name", "size", "mtime")

#: Sentinel returned by :func:`count_children` once a directory holds more
#: than 999 children; the row renderer shows it as ``999+``.
_CHILD_CAP: int = 1000

#: ``strftime`` pattern for the status bar mtime (lf-style local time).
_MTIME_FORMAT: str = "%a %b %d %H:%M:%S %Y"

#: Status-bar segment separator (lf-style middle dot, escaped to keep the
#: source ASCII).
_SEP: str = " \u00b7 "


def next_sort(current: SortKey) -> SortKey:
    """Return the sort key following *current* in :data:`SORT_CYCLE`."""
    index = SORT_CYCLE.index(current)
    return SORT_CYCLE[(index + 1) % len(SORT_CYCLE)]


def sort_entries(
    entries: list[Entry],
    stats: dict[Path, EntryStat],
    key: SortKey,
    *,
    descending: bool = False,
) -> list[Entry]:
    """Directories first (name asc), then files by *key*; stable.

    The directory group stays name-ascending regardless of *descending*,
    which only reverses the file group.  ``sorted`` stability keeps
    same-key files in their input order.  Entries missing from *stats*
    degrade to ``0`` for the size / mtime keys.
    """
    dirs = sorted((e for e in entries if e.is_dir), key=lambda e: e.name.lower())
    file_entries = [e for e in entries if not e.is_dir]
    if key == "name":
        files = sorted(file_entries, key=lambda e: e.name.lower(), reverse=descending)
    elif key == "size":
        files = sorted(
            file_entries,
            key=lambda e: stats[e.path].size if e.path in stats else 0,
            reverse=descending,
        )
    else:
        files = sorted(
            file_entries,
            key=lambda e: stats[e.path].mtime_ns if e.path in stats else 0,
            reverse=descending,
        )
    return dirs + files


def filter_entries(entries: list[Entry], query: str) -> list[Entry]:
    """Case-insensitive substring filter (empty query = no-op).

    Plain substring semantics (lf convention) rather than fuzzy scoring:
    the palette's fuzzy matcher targets file paths, not directory
    browsing.  An empty *query* returns the input list unchanged.
    """
    if not query:
        return entries
    lowered = query.lower()
    return [e for e in entries if lowered in e.name.lower()]


@dataclass(frozen=True)
class DirListing:
    """Cached directory listing with its freshness stamp (R1).

    *stamp* is the directory's ``st_mtime_ns`` probed immediately before
    the scan that produced *entries* (a raw ``Workspace.list_dir``
    result: directories first, ignore rules and dotfile visibility
    applied, not filtered or sorted by the screen).  Any change of the
    directory contents after the scan makes the stored stamp read as
    stale, so the consumer re-scans.
    """

    stamp: int
    entries: list[Entry]


@dataclass(frozen=True)
class RowSpec:
    """Plain row data for the list pane.

    The uncolored *text* is the row string; the Screen obtains the
    span-colored version through :func:`build_row_text`.
    """

    #: Plain (uncolored) row text.
    text: str
    path: Path
    is_dir: bool
    is_marked: bool
    #: :func:`human_size` result, or ``""`` for directories.
    size_text: str


def count_children(path: Path) -> int:
    """Number of direct children (any visibility), cheap scandir pass.

    Early-exits past 999 children and returns the ``1000`` sentinel.  A
    failed ``scandir`` (vanished directory) returns ``-1`` so the
    display layer omits the badge.
    """
    try:
        with os.scandir(path) as it:
            count = 0
            for _ in it:
                count += 1
                if count >= _CHILD_CAP:
                    return _CHILD_CAP
            return count
    except OSError:
        return -1


def build_row_text(
    entry: Entry,
    stat: EntryStat | None,
    accent: str,
    marked: bool,
    *,
    dir_child_count: int | None,
    sort_key: SortKey,
) -> Text:
    """Render one list row as a span-colored rich text.

    Layout: ``[* ]icon name[ (N)][ size]``.  The icon glyph comes from
    :func:`~yate.editor_view.icons.icon_for_path`, colored via
    :func:`~yate.editor_view.icons.icon_color` (directories take the
    *accent* theme color, files use the fixed Seti palette); directory
    names are accent-colored, file names keep the widget's default
    foreground.  Marked rows carry a ``* `` prefix.  Directories show a
    ``(N)`` child badge (``999+`` once capped; omitted when
    *dir_child_count* is ``None`` or negative, which is how a failed
    :func:`count_children` reports); files show :func:`human_size`
    right-aligned in a 6-character column (nothing for directories or a
    missing *stat*).  *sort_key* is reserved for a later sort-column
    indicator and does not affect the rendering.
    """
    text = Text()
    if marked:
        text.append("* ")
    icon = icon_for_path(entry.name, entry.is_dir)
    text.append(icon + " ", style=icon_color(entry.name, entry.is_dir, accent))
    name = entry.name or str(entry.path)
    if entry.is_dir:
        text.append(name, style=accent)
        if dir_child_count is not None and dir_child_count >= 0:
            if dir_child_count >= _CHILD_CAP:
                text.append(" (999+)")
            else:
                text.append(f" ({dir_child_count})")
    else:
        text.append(name)
        if stat is not None:
            text.append(" " + human_size(stat.size).rjust(6))
    return text


def _status_size(size: int) -> str:
    """:func:`human_size` with a ``B`` suffix on plain byte counts.

    Matches lf's status bar shape: ``72B`` under 1 KiB, ``15K`` /
    ``2.6M`` above (unit-carrying results are returned unchanged).
    """
    text = human_size(size)
    return text + "B" if text.isdigit() else text


def format_status(
    stat: EntryStat | None,
    index: int,
    total: int,
    sort_key: SortKey,
    descending: bool,
    filter_active: str | None,
    marked_count: int,
) -> str:
    """Format the status bar line (lf-style layout).

    ``<mode> <nlink> <owner> <group> <size> <mtime> <mid-dot> n/total
    <mid-dot> <sort hint>``.  *index* is 0-based and rendered 1-based
    (lf convention).  Owner / group fall back to ``-`` when unknown
    (Windows); a ``None`` *stat* degrades to the all-zero shape.  The
    filter segment (``filter: <query>``) appears only while a filter is
    active, and the marker segment (``marked: N``) only when
    *marked_count* is positive.  Plain byte counts carry a ``B`` suffix
    (lf style: ``72B`` but ``15K``); truncation to the terminal width is
    the display layer's job.
    """
    if stat is None:
        mode_text = filemode(0)
        nlink = 0
        owner = "-"
        group = "-"
        size_text = _status_size(0)
        mtime_text = time.strftime(_MTIME_FORMAT, time.localtime(0))
    else:
        mode_text = filemode(stat.mode)
        nlink = stat.nlink
        owner = stat.owner if stat.owner is not None else "-"
        group = stat.group if stat.group is not None else "-"
        size_text = _status_size(stat.size)
        mtime_text = time.strftime(_MTIME_FORMAT, time.localtime(stat.mtime_ns / 1e9))
    parts = [
        f"{mode_text} {nlink} {owner} {group} {size_text} {mtime_text}",
        f"{index + 1}/{total}",
        f"{sort_key} {'desc' if descending else 'asc'}",
    ]
    if filter_active is not None:
        parts.append(f"filter: {filter_active}")
    if marked_count > 0:
        parts.append(f"marked: {marked_count}")
    return _SEP.join(parts)


def parent_and_siblings(
    current: Path, workspace: Workspace
) -> tuple[Path, list[Entry]]:
    """Left-pane model: the parent directory and its listing.

    The only call site (:meth:`FileManagerScreen._render_parent`) guards
    on ``_cwd`` not being a file-system root, so this never sees the
    root itself (the drive-letter level lives in the middle pane, Q4).
    """
    return current.parent, workspace.list_dir(current.parent)


def memory_key(entry_path: Path) -> Path:
    """Cursor-memory key for a directory entry (identity anchor).

    Kept as a named seam so the Screen's ``_dir_memory`` dict keys go
    through one indirection point; currently the identity mapping.
    """
    return entry_path
