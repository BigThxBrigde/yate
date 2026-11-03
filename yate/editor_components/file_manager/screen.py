"""Three-pane file manager screen (lf-style, modal or fullscreen).

Left = parent directory / Windows drive level, middle = current
directory, right = syntax-highlighted preview; a bottom input line
serves filter / prompt mode and a status bar summarizes the cursor
entry.  The screen owns only browsing, marking, previewing and
file-system operations: selection goes to the injected
``open_selected`` callback (after ``dismiss``) and closing to the
injected ``close`` callback, so orchestration stays with the L3 flows
layer (constructor injection only, R3: no ``yate.editor`` imports).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Literal, override

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click, Key
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static

from yate.config import FilePreviewConfig
from yate.logs import tracing
from yate.paths import load_tcss
from yate.services.workspace import Entry, EntryStat, Workspace

from yate.editor_components import theme
from yate.editor_components.file_manager.keys import (
    DOUBLE_CLICK_WINDOW,
    G_PENDING_TIMEOUT,
    LIST_BINDINGS,
    SCREEN_BINDINGS,
)
from yate.editor_components.file_manager.model import (
    DirListing,
    SortKey,
    build_row_text,
    count_children,
    filter_entries,
    format_status,
    memory_key,
    next_sort,
    parent_and_siblings,
    sort_entries,
)
from yate.editor_components.icons import icon_color, icon_for_path
from yate.editor_components.preview import (
    PreviewCache,
    PreviewData,
    PreviewLog,
    load_preview_worker,
    preview_text,
)
from yate.editor_components.scrollbars import apply_scrollbar_theme, apply_slim_scrollbars

log = tracing.get_logger(__name__)

#: Maximum children listed in a directory preview.
_DIR_PREVIEW_CAP: int = 100

#: Directory-listing cache entry cap (FIFO eviction; aligned with the
#: preview pipeline's ``PREVIEW_CACHE_SIZE``).
_DIR_CACHE_SIZE: int = 16

#: Mode of the bottom input line / pending prompt operation.
type _InputMode = Literal["filter", "prompt"]
type _PromptKind = Literal["new-file", "new-dir", "rename", "delete"]


class _Row(Static):
    """One middle-pane list row; clicks are stopped here so the host
    ListView never posts its single-click ``Selected`` (Textual 8.2.8
    posts one on every item click) -- the screen owns cursor movement
    and the double-click window instead."""

    class Clicked(Message, namespace="file_manager_row"):
        """A row was clicked; *index* points into the screen's entry list."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(self, text: Text, index: int) -> None:
        """Render *text* for entry *index* (baked at rebuild time)."""
        super().__init__(text)
        self.index = index

    def on_click(self, event: Click) -> None:
        """Consume the click and report it to the screen (see class doc)."""
        event.stop()
        self.post_message(self.Clicked(self.index))


class _FileListView(ListView):
    """Middle-pane list; remaps inherited scroll bindings to nav actions
    (``ScrollableContainer`` would otherwise swallow left / right / home
    / end / pageup / pagedown while focused)."""

    BINDINGS = LIST_BINDINGS

    def __init__(self, screen: FileManagerScreen) -> None:
        """Bind the list to its owning *screen* (same module, L2 internal)."""
        super().__init__(id="file-manager-list")
        self._screen = screen

    def action_nav(self, name: str) -> None:
        """Forward a ``nav(name)`` binding to the screen's ``action_<name>``."""
        screen = self._screen
        if name == "up":
            screen.action_up()
        elif name == "open":
            screen.action_open()
        elif name == "top":
            screen.action_top()
        elif name == "bottom":
            screen.action_bottom()
        elif name == "half_page_up":
            screen.action_half_page_up()
        else:
            screen.action_half_page_down()


class FileManagerScreen(ModalScreen[None]):
    """lf-style three-pane file manager (parent | current | preview)."""

    DEFAULT_CSS = load_tcss("file-manager-screen.tcss")

    BINDINGS = SCREEN_BINDINGS

    def __init__(
        self,
        *,
        workspace: Workspace,
        preview: FilePreviewConfig,
        open_selected: Callable[[list[Path]], None],
        close: Callable[[], None],
        on_renamed: Callable[[Path, Path], None],
        on_deleted: Callable[[Path], None],
        on_show_hidden_changed: Callable[[bool], None],
        fullscreen: bool = False,
        initial_dir: Path | None = None,
    ) -> None:
        """Store collaborators (R3: concrete collaborators and callbacks only).

        *open_selected* receives the selected path collection (Q1/Q2
        semantics stay with the flows layer); *close* pops the overlay
        or exits the app.  *on_renamed* / *on_deleted* / *on_show_hidden_changed*
        keep the editor session and the file tree in sync (M2 / m5);
        *initial_dir* defaults to the workspace root, then the cwd;
        *fullscreen* adds the ``.fullscreen`` class.
        """
        super().__init__()
        self.workspace = workspace
        self.preview = preview
        self.open_selected = open_selected
        self.close = close
        self.on_renamed = on_renamed
        self.on_deleted = on_deleted
        self.on_show_hidden_changed = on_show_hidden_changed
        if fullscreen:
            self.add_class("fullscreen")
        root = workspace.root
        start = (initial_dir or root or Path.cwd()).resolve()
        # The drive-letter virtual level (``None``) only exists where
        # drives do: with an empty ``list_drives()`` (POSIX) a root
        # start stays on the real root (M1), others browse normally.
        at_root = start.parent == start
        self._cwd: Path | None = None if at_root and workspace.list_drives() else start
        self._all: list[Entry] = []
        self._entries: list[Entry] = []
        self._stats: dict[Path, EntryStat] = {}
        self._child_counts: dict[Path, int] = {}
        #: ``(path, show_hidden)`` -> listing, mtime-keyed freshness (R1)
        self._dir_cache: dict[tuple[Path, bool], DirListing] = {}
        #: rendered row texts, parallel to ``_entries``
        self._rows: list[Text] = []
        self._sort: SortKey = "name"
        self._desc: bool = False
        self._filter: str | None = None
        self._marked: set[Path] = set()
        #: ``(path, is_cut)``; cut buffers are consumed by the move
        self._clipboard: tuple[Path, bool] | None = None
        #: directory -> entry to land on when returning to it (``h``)
        self._dir_memory: dict[Path, Path] = {}
        self._preview_cache = PreviewCache()
        self._g_pending: bool = False
        self._g_pending_at: float = 0.0
        self._mode: _InputMode | None = None
        self._prompt_kind: _PromptKind | None = None
        self._prompt_target: Path | None = None
        self._last_click_index: int = -1
        self._last_click_time: float = 0.0

    @override
    def compose(self) -> ComposeResult:
        """Compose the three panes, the bottom input and the status bar."""
        with Vertical(id="file-manager"):
            with Horizontal(id="file-manager-body"):
                parent = ListView(id="file-manager-parent")
                parent.can_focus = False
                yield parent
                yield _FileListView(self)
                yield PreviewLog(id="file-manager-preview")
            yield Input(id="file-manager-input")
            yield Static(id="file-manager-status")

    def on_mount(self) -> None:
        """Defer the mount wiring until the composed children exist.

        Textual 8.2.8 mounts ``push_screen`` targets via ``call_next``, so
        the screen's own ``Mount`` can fire before ``compose``'s children
        are mounted (B1: NoMatches under load on the startup form).
        """
        self.call_after_refresh(self._wire_mount)

    def _wire_mount(self) -> None:
        """Wire scrollbars + theme, then build the initial listing (R15).

        Retries via ``call_after_refresh`` until the three panes are
        attached: a node present in the DOM is not enough.  ``is_attached``
        mirrors the exact check Textual's own ``mount`` performs (8.2.8:
        ``Widget.mount`` raises ``MountError`` on ``not is_attached``) --
        ``is_mounted`` cannot be used here because it never resets to
        ``False`` on unmount, so a teardown after ``q`` would pass the
        guard and then fail the populate.
        """
        panes = self.query("#file-manager-parent, #file-manager-list, #file-manager-preview")
        if len(panes) < 3 or not all(node.is_attached for node in panes):
            self.call_after_refresh(self._wire_mount)  # children not attached yet
            return
        apply_slim_scrollbars(self.query_one("#file-manager-parent", ListView))
        apply_slim_scrollbars(self.query_one("#file-manager-list", _FileListView))
        apply_slim_scrollbars(self.query_one("#file-manager-preview", PreviewLog))
        theme.attach(self, self._apply_theme)
        self._apply_theme()
        self._reload()
        self.query_one("#file-manager-list", _FileListView).focus()

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def _apply_theme(self) -> None:
        """Repaint scrollbars, rows and status bar from the active theme (R13)."""
        apply_scrollbar_theme(self.query_one("#file-manager-parent", ListView))
        apply_scrollbar_theme(self.query_one("#file-manager-list", _FileListView))
        apply_scrollbar_theme(self.query_one("#file-manager-preview", PreviewLog))
        if self._entries:
            self._rebuild_rows()
            self._render_list(previous=self._cursor_path())
            self._refresh_status()

    def _cursor_entry(self) -> Entry | None:
        """Entry under the middle-pane cursor (``None`` on an empty listing)."""
        index = self.query_one("#file-manager-list", _FileListView).index
        if index is None or not 0 <= index < len(self._entries):
            return None
        return self._entries[index]

    def _cursor_path(self) -> Path | None:
        """Path under the middle-pane cursor (``None`` on an empty listing)."""
        entry = self._cursor_entry()
        return entry.path if entry is not None else None

    def _restore_index(self, index: int, attempt: int = 0) -> None:
        """Set the list cursor once the rebuilt rows reached the DOM
        (row mount/removal is scheduled, so re-check and retry, bounded)."""
        list_view = self.query_one("#file-manager-list", _FileListView)
        if len(list_view) != len(self._entries) and attempt < 10:
            list_view.call_after_refresh(self._restore_index, index, attempt + 1)
            return
        list_view.index = index

    def _reload(self, keep: Path | None = None) -> None:
        """Rebuild the panes from the file system (shared refresh pipeline):
        list + stat + sort + render, then refresh preview and status.
        *keep* forces the cursor onto that entry (the ``h`` lf semantics).
        The middle listing goes through the mtime-keyed cache (R1): a hit
        reuses the stat dict, a fresh scan rebuilds it."""
        previous = self._cursor_path()
        if self._cwd is None:
            # drive-letter virtual level (Q4): drives listed in the middle;
            # list_drives probes are cheap, so this level stays uncached
            self._all = self.workspace.list_drives()
            cached = False
        else:
            self._all, cached = self._lookup_dir_listing(self._cwd)
        self._entries = filter_entries(self._all, self._filter or "")
        if cached:
            # Listing unchanged (mtime revalidated): keep the stat dict and
            # top up only entries never stat'ed (same setdefault as
            # _refilter); dropped entries cannot linger because a content
            # change misses the cache.  Entries carried over from other
            # directories (cross-directory navigation on cache hits) are
            # harmless: every consumer looks paths up from the current
            # entries, and any fresh scan rebuilds the dict wholesale.
            for entry in self._entries:
                if entry.path not in self._stats:
                    self._stats[entry.path] = self.workspace.stat_entry(entry.path)
        else:
            # Fresh scan is authoritative: rebuild so entries deleted since
            # the previous listing do not linger in the stat dict.
            self._stats = {
                e.path: self.workspace.stat_entry(e.path) for e in self._entries
            }
        self._entries = sort_entries(
            self._entries, self._stats, self._sort, descending=self._desc
        )
        self._rebuild_rows()
        self._render_parent()
        self._render_list(keep=keep, previous=previous)
        self._refresh_preview()
        self._refresh_status()

    def _refilter(self) -> None:
        """Light refresh for filter edits: re-filter + re-render, no re-stat."""
        previous = self._cursor_path()
        filtered = filter_entries(self._all, self._filter or "")
        for entry in filtered:
            if entry.path not in self._stats:
                self._stats[entry.path] = self.workspace.stat_entry(entry.path)
        self._entries = sort_entries(
            filtered, self._stats, self._sort, descending=self._desc
        )
        self._rebuild_rows()
        self._render_list(previous=previous)
        self._refresh_preview()
        self._refresh_status()

    def _lookup_dir_listing(self, path: Path) -> tuple[list[Entry], bool]:
        """Cached :meth:`Workspace.list_dir` probe with mtime revalidation.

        The cache key is ``(path, show_hidden)``; a hit must revalidate
        the stored stamp against the directory's current ``st_mtime_ns``,
        so any content change reads as a miss and rescans.  The stamp is
        probed *before* the scan: a change between stamp and scan keeps
        the stamp older than the content, so the next probe misses
        (stamping after the scan could pin a stale listing under a fresh
        stamp).  A failed ``stat`` (vanished directory) reads as a miss
        and falls back to an uncached ``list_dir``.  The ``bool`` reports
        whether the listing came from a fresh cache hit (``_reload``
        keeps the stat dict only then); FIFO eviction caps the cache at
        :data:`_DIR_CACHE_SIZE`.

        Residual window: a change landing in the *same* mtime tick as
        the stamp reads as fresh until the next change pushes the mtime
        again.  Nanosecond filesystems (NTFS/ext4) self-heal instantly;
        coarse-tick filesystems (FAT32, some network shares) widen the
        window to seconds -- ``r`` (force refresh) always rescans.
        """
        key = (path, self.workspace.show_hidden)
        cached = self._dir_cache.get(key)
        if cached is not None:
            try:
                fresh = path.stat().st_mtime_ns == cached.stamp
            except OSError:
                fresh = False
            if fresh:
                return cached.entries, True
        try:
            stamp = path.stat().st_mtime_ns
        except OSError:
            return self.workspace.list_dir(path), False
        entries = self.workspace.list_dir(path)
        self._dir_cache[key] = DirListing(stamp=stamp, entries=entries)
        while len(self._dir_cache) > _DIR_CACHE_SIZE:
            self._dir_cache.pop(next(iter(self._dir_cache)))
        return entries, False

    def _list_dir_cached(self, path: Path) -> list[Entry]:
        """Directory listing through the cache (consumers needing the
        hit/miss bit call :meth:`_lookup_dir_listing`)."""
        return self._lookup_dir_listing(path)[0]

    def _drop_dir_cache(self) -> None:
        """Drop every cached directory listing (mutations, force refresh)."""
        self._dir_cache.clear()

    def _rebuild_rows(self) -> None:
        """Recompute row texts from the current entries.

        Child counts are computed once per directory and cached in
        ``_child_counts`` (``setdefault`` semantics), so filter keystrokes
        never rescan the file system; :meth:`action_refresh` drops the
        cache (M3).
        """
        accent = theme.active().accent
        for entry in self._entries:
            if entry.is_dir and entry.path not in self._child_counts:
                self._child_counts[entry.path] = count_children(entry.path)
        self._rows = [
            build_row_text(
                entry,
                self._stats.get(entry.path),
                accent,
                entry.path in self._marked,
                dir_child_count=self._child_counts.get(entry.path),
                sort_key=self._sort,
            )
            for entry in self._entries
        ]

    def _render_list(
        self, *, keep: Path | None = None, previous: Path | None = None
    ) -> None:
        """Rebuild the row widgets from ``_rows``; cursor: *keep*, then
        *previous*, then the top."""
        list_view = self.query_one("#file-manager-list", _FileListView)
        list_view.clear()
        list_view.extend(
            ListItem(_Row(row_text, index))
            for index, row_text in enumerate(self._rows)
        )
        wanted = keep if keep is not None else previous
        index = 0
        if wanted is not None:
            for i, entry in enumerate(self._entries):
                if entry.path == wanted:
                    index = i
                    break
        if self._rows:
            list_view.call_after_refresh(self._restore_index, index)

    def _render_parent(self) -> None:
        """Rebuild the left pane (parent listing or placeholder).

        The drive-letter virtual level lives in the middle pane (Q4), so
        the left pane shows a placeholder both at the drive level and
        while browsing a file-system root.
        """
        pane = self.query_one("#file-manager-parent", ListView)
        pane.clear()
        t = theme.active()
        rows: list[Text] = []
        if self._cwd is None or self._cwd.parent == self._cwd:
            rows = [Text("(no parent directory)", style=t.fg_dim)]
        else:
            _parent, entries = parent_and_siblings(self._cwd, self.workspace)
            if not entries:
                rows = [Text("(empty)", style=t.fg_dim)]
            else:
                rows = [
                    self._icon_text(
                        e.name, e.is_dir, t.accent if e.is_dir else t.fg
                    )
                    for e in entries
                ]
        pane.extend(ListItem(Static(row)) for row in rows)

    @staticmethod
    def _icon_text(name: str, is_dir: bool, name_style: str) -> Text:
        """One ``icon + name`` row text with the theme-colored glyph."""
        text = Text()
        text.append(
            icon_for_path(name, is_dir) + " ",
            style=icon_color(name, is_dir, theme.active().accent),
        )
        text.append(name, style=name_style)
        return text

    def _refresh_preview(self) -> None:
        """Update the preview pane for the cursor entry (palette pipeline)."""
        pane = self.query_one("#file-manager-preview", PreviewLog)
        entry = self._cursor_entry()
        if entry is None:
            pane.clear()
            pane.write(Text("(empty directory)", style=theme.active().fg_dim))
            return
        if entry.is_dir:
            self._render_dir_preview(entry.path)
            return
        path = entry.path
        try:
            st = path.stat()
        except OSError:
            st = None
        if st is not None:
            cached = self._preview_cache.get(path, st.st_mtime_ns, st.st_size)
            if cached is not None:
                self._render_preview(cached)
                return
        pane.clear()
        pane.write(Text("loading…", style=theme.active().fg_dim))
        self.run_worker(
            # coroutine *function*: an eager coroutine would leak if
            # the worker never starts (closing pump)
            partial(self._load_preview_worker, path),
            group="file-manager-preview",
            exclusive=True,
            exit_on_error=False,
        )

    def _render_dir_preview(self, path: Path) -> None:
        """Render the first N children of directory *path* (UI thread)."""
        pane = self.query_one("#file-manager-preview", PreviewLog)
        pane.clear()
        children = self._list_dir_cached(path)
        shown = children[:_DIR_PREVIEW_CAP]
        if not shown:
            pane.write(Text("(empty directory)", style=theme.active().fg_dim))
            return
        t = theme.active()
        text = Text()
        for child in shown:
            name_style = t.accent if child.is_dir else t.fg
            text.append_text(self._icon_text(child.name, child.is_dir, name_style))
            text.append("\n")
        if len(children) > _DIR_PREVIEW_CAP:
            text.append(f"… +{len(children) - _DIR_PREVIEW_CAP} more", style=t.fg_dim)
        pane.write(text)

    async def _load_preview_worker(self, path: Path) -> None:
        """Run the shared preview worker, then paint when still selected.

        The ``is_attached`` guard below is defensive redundancy: unmount
        cancels the worker outright (``workers.cancel_node``), so the
        ``return`` is not reachable in normal flow and needs no direct
        test coverage.
        """
        data = await load_preview_worker(path, self.preview)
        # is_mounted never resets on unmount; is_attached mirrors Textual's
        # own mount check (see _wire_mount).
        if not self.is_attached:
            return
        self._preview_cache.store(data)
        entry = self._cursor_entry()
        if entry is None or entry.path != path:
            return
        self._render_preview(data)

    def _render_preview(self, data: PreviewData) -> None:
        """Paint *data* into the preview pane (UI thread)."""
        pane = self.query_one("#file-manager-preview", PreviewLog)
        pane.clear()
        if data.note is not None:
            # binary / oversize / unreadable: the pipeline's degradation note
            pane.write(Text(data.note, style=theme.active().fg_dim))
            return
        pane.write(preview_text(data, theme.active(), self.preview.max_lines))

    def _refresh_status(self) -> None:
        """Repaint the status bar for the cursor entry."""
        entry = self._cursor_entry()
        index = self.query_one("#file-manager-list", _FileListView).index
        stat = self._stats.get(entry.path) if entry is not None else None
        status = format_status(
            stat,
            index if index is not None else 0,
            len(self._entries),
            self._sort,
            self._desc,
            self._filter,
            len(self._marked),
        )
        self.query_one("#file-manager-status", Static).update(
            Text(status, style=theme.active().fg)
        )

    def _repaint_row(self, index: int) -> None:
        """Re-render a single row in place (mark toggles keep the cursor)."""
        list_view = self.query_one("#file-manager-list", _FileListView)
        children = list(list_view.children)
        if not 0 <= index < len(children) or index >= len(self._rows):
            return
        item = children[index]
        if isinstance(item, ListItem):
            item.query_one(_Row).update(self._rows[index])

    def on_key(self, event: Key) -> None:
        """Handle the ``g`` prefix sequence (state machine; not a binding).

        A second ``g`` within :data:`G_PENDING_TIMEOUT` jumps to the
        top; other keys or the timeout reset the pending state.
        """
        if self._mode is not None:
            return
        now = time.monotonic()
        if event.key == "g":
            event.stop()
            event.prevent_default()
            if self._g_pending and now - self._g_pending_at <= G_PENDING_TIMEOUT:
                self._g_pending = False
                self.action_top()
            else:
                self._g_pending = True
                self._g_pending_at = now
            return
        self._g_pending = False

    def on_file_manager_row_clicked(self, event: _Row.Clicked) -> None:
        """Row click: move the cursor; a double click opens.

        Textual 8.2.8 posts ``ListView.Selected`` on every single item
        click, so the click is intercepted at the row (see ``_Row``)."""
        if self._mode is not None:
            return
        list_view = self.query_one("#file-manager-list", _FileListView)
        list_view.focus()
        now = time.monotonic()
        if (
            event.index == self._last_click_index
            and now - self._last_click_time <= DOUBLE_CLICK_WINDOW
        ):
            self._last_click_index = -1
            self._last_click_time = 0.0
            self.action_open()
            return
        self._last_click_index = event.index
        self._last_click_time = now
        list_view.index = event.index

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter on the middle list opens the cursor entry (keyboard path)."""
        if event.list_view.id != "file-manager-list" or self._mode is not None:
            return
        self.action_open()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Cursor moves repaint the preview and the status bar."""
        if event.list_view.id != "file-manager-list":
            return
        self._refresh_preview()
        self._refresh_status()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter mode narrows the listing as the query changes."""
        if event.input.id != "file-manager-input" or self._mode != "filter":
            return
        self._filter = event.value or None
        self._refilter()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter applies the filter in filter mode, commits in prompt mode."""
        if event.input.id != "file-manager-input":
            return
        if self._mode == "filter":
            self._hide_input()
        elif self._mode == "prompt":
            self._submit_prompt(event.value)

    def _show_input(self, placeholder: str, value: str = "") -> None:
        """Show the bottom input line and focus it."""
        input_widget = self.query_one("#file-manager-input", Input)
        input_widget.placeholder = placeholder
        input_widget.value = value
        input_widget.add_class("active")
        input_widget.focus()

    def _hide_input(self) -> None:
        """Hide the bottom input line, clear the mode, refocus the list."""
        input_widget = self.query_one("#file-manager-input", Input)
        input_widget.remove_class("active")
        input_widget.value = ""
        self._mode = None
        self._prompt_kind = None
        self._prompt_target = None
        self.query_one("#file-manager-list", _FileListView).focus()

    def _show_input_error(self, message: str) -> None:
        """Show *message* on the input line, keeping the prompt context.

        With an active prompt (kind + target) the typed value and the
        pending operation survive the error: the message only replaces
        the placeholder, so the user can edit and retry or leave with
        Esc.  Without prompt context the line becomes a read-only
        notice -- Enter dismisses it (the ``kind is None`` branch of
        :meth:`_submit_prompt`).
        """
        self._mode = "prompt"
        if self._prompt_kind is None:
            self._show_input(message)
            return
        input_widget = self.query_one("#file-manager-input", Input)
        input_widget.placeholder = message
        input_widget.focus()

    def _begin_prompt(
        self, kind: _PromptKind, placeholder: str, value: str = ""
    ) -> None:
        """Open the bottom input in prompt mode for *kind*."""
        self._mode = "prompt"
        self._prompt_kind = kind
        self._prompt_target = self._cursor_path() if kind in ("rename", "delete") else None
        self._show_input(placeholder, value)

    def _submit_prompt(self, value: str) -> None:
        """Commit the pending prompt operation (errors stay on the line).

        Errors keep the input open with the typed value and the pending
        operation intact -- only the placeholder carries the message --
        so the user can correct and retry or leave with Esc; delete
        expects ``y`` (anything else cancels, explorer semantics).  A
        successful rename / delete reports to the injected callbacks so
        the editor session and file tree stay in sync (M2).
        """
        kind = self._prompt_kind
        if kind is None:
            # error-display-only prompt: Enter just closes the line
            self._hide_input()
            return
        target = self._prompt_target
        cwd = self._cwd
        renamed: tuple[Path, Path] | None = None
        deleted: Path | None = None
        try:
            if kind == "delete":
                if value.strip().lower() not in ("y", "yes") or target is None:
                    self._hide_input()
                    return
                self.workspace.remove_entry(target)
                deleted = target
            elif kind == "rename":
                if target is None:
                    self._hide_input()
                    return
                renamed = (target, self.workspace.rename_entry(target, value))
            elif kind == "new-dir":
                if cwd is None:
                    self._hide_input()  # no directory at the drive level
                    return
                self.workspace.create_entry(cwd, value, is_dir=True)
            else:
                if cwd is None:
                    self._hide_input()  # no directory at the drive level
                    return
                self.workspace.create_entry(cwd, value, is_dir=False)
        except (ValueError, FileExistsError, OSError) as exc:
            log.debug("file_manager %s failed: %s", kind, exc)
            self._show_input_error(str(exc))
            return
        self._drop_dir_cache()
        self.workspace.invalidate()
        self._hide_input()
        if renamed is not None:
            self.on_renamed(*renamed)
        elif deleted is not None:
            self.on_deleted(deleted)
        self._reload()

    def action_cursor_down(self) -> None:
        """``j`` / down: move the middle-pane cursor down one row."""
        self.query_one("#file-manager-list", _FileListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        """``k`` / up: move the middle-pane cursor up one row."""
        self.query_one("#file-manager-list", _FileListView).action_cursor_up()

    def action_top(self) -> None:
        """``gg`` / home: cursor to the first row."""
        self.query_one("#file-manager-list", _FileListView).index = 0

    def action_bottom(self) -> None:
        """``G`` / end: cursor to the last row."""
        if self._entries:
            self.query_one("#file-manager-list", _FileListView).index = len(self._entries) - 1

    def action_half_page_down(self) -> None:
        """ctrl+d: move the cursor down half a viewport."""
        self._half_page(1)

    def action_half_page_up(self) -> None:
        """ctrl+u: move the cursor up half a viewport."""
        self._half_page(-1)

    def _half_page(self, direction: int) -> None:
        """Move the cursor *direction* half-viewport steps (clamped)."""
        list_view = self.query_one("#file-manager-list", _FileListView)
        if list_view.index is None or not self._entries:
            return
        step = max(1, list_view.size.height // 2) * direction
        list_view.index = list_view.index + step

    def action_up(self) -> None:
        """``h`` / left / backspace: parent directory (lf cursor memory).

        At the drive-letter virtual level there is nothing above (the
        level stays put); at a file-system root ``h`` switches to the
        drive level when drives exist (Q4) -- the drive level only
        exists when ``list_drives()`` is non-empty (Windows; POSIX
        stays on the real root, M1).
        """
        if self._cwd is None:
            return  # already at the drive level
        if self._cwd.parent == self._cwd:
            if not self.workspace.list_drives():
                return  # POSIX: no drive level, stay at the file-system root
            self._cwd = None
            self._reload()
            return
        origin = self._cwd
        parent = self._cwd.parent
        self._dir_memory[memory_key(parent)] = origin
        self._cwd = parent
        self._reload(keep=self._dir_memory.get(memory_key(parent)))

    def action_open(self) -> None:
        """``l`` / enter / right / double click: open the cursor entry.

        A marked collection containing the cursor entry is handed whole
        to ``open_selected`` (Q2 semantics are the flows layer's
        concern); a single directory navigates into it, a single file
        goes to ``open_selected`` after ``dismiss``.
        """
        entry = self._cursor_entry()
        if entry is None:
            return
        if self._marked and entry.path in self._marked:
            selected = sorted(self._marked)
            self.dismiss()
            self.open_selected(selected)
            return
        if entry.is_dir:
            self._cwd = entry.path
            self._reload()
            return
        self.dismiss()
        self.open_selected([entry.path])

    def action_toggle_hidden(self) -> None:
        """``H`` / ``.``: toggle dotfile visibility (explorer-synced flag)."""
        self.workspace.show_hidden = not self.workspace.show_hidden
        self.on_show_hidden_changed(self.workspace.show_hidden)
        self._reload(keep=self._cursor_path())

    def action_cycle_sort(self) -> None:
        """``s``: cycle the sort key (name -> size -> mtime); dirs first."""
        self._sort = next_sort(self._sort)
        self._reload(keep=self._cursor_path())

    def action_refresh(self) -> None:
        """``r`` / F5: force refresh -- drop the workspace, directory-listing,
        child-count and stat caches, then rebuild the listing."""
        self.workspace.invalidate()
        self._drop_dir_cache()
        self._child_counts = {}
        self._stats = {}
        self._reload(keep=self._cursor_path())

    def action_mark(self) -> None:
        """space: toggle the mark on the cursor entry (cursor stays put)."""
        index = self.query_one("#file-manager-list", _FileListView).index
        if index is None:
            return
        entry = self._entries[index]
        if entry.path in self._marked:
            self._marked.discard(entry.path)
        else:
            self._marked.add(entry.path)
        self._repaint_row(index)
        self._refresh_status()

    def action_invert_marks(self) -> None:
        """``v``: invert the marks of the current listing."""
        for entry in self._entries:
            if entry.path in self._marked:
                self._marked.discard(entry.path)
            else:
                self._marked.add(entry.path)
        self._rebuild_rows()
        self._render_list(previous=self._cursor_path())
        self._refresh_status()

    def action_escape(self) -> None:
        """Two-level exit: input mode, then filter, then marks, then close."""
        if self._mode is not None:
            was_filter = self._mode == "filter"
            self._hide_input()
            if was_filter and self._filter is not None:
                self._filter = None
                self._refilter()
            return
        if self._filter is not None:
            self._filter = None
            self._refilter()
            return
        if self._marked:
            self._marked.clear()
            self._rebuild_rows()
            self._render_list(previous=self._cursor_path())
            self._refresh_status()
            return
        self.close()

    def action_quit(self) -> None:
        """``q``: close the screen through the injected callback."""
        self.close()

    def action_filter(self) -> None:
        """``/`` / ``f``: open the bottom input in filter mode."""
        self._mode = "filter"
        self._show_input("filter by name (esc clears)", self._filter or "")

    def action_new_file(self) -> None:
        """``a``: prompt for a new file name in the current directory."""
        self._begin_prompt("new-file", "new file name:")

    def action_new_dir(self) -> None:
        """``A``: prompt for a new directory name in the current directory."""
        self._begin_prompt("new-dir", "new directory name:")

    def action_rename(self) -> None:
        """``R``: prompt to rename the cursor entry (name prefilled)."""
        entry = self._cursor_entry()
        if entry is None or entry.path.parent == entry.path:
            return  # nothing selected, or a file-system root (Q4 level)
        self._begin_prompt("rename", f"rename {entry.name} to:", entry.name)

    def action_delete(self) -> None:
        """``d``: prompt for the delete confirmation (``y`` to confirm)."""
        entry = self._cursor_entry()
        if entry is None or entry.path.parent == entry.path:
            return  # nothing selected, or a file-system root (Q4 level)
        kind = "directory (recursive)" if entry.is_dir else "file"
        self._begin_prompt(
            "delete", f"delete {entry.name} - {kind}: type y to confirm"
        )

    def action_yank(self) -> None:
        """``y``: copy the cursor entry into the paste buffer."""
        self._clip(False)

    def action_cut(self) -> None:
        """``x``: cut the cursor entry into the paste buffer."""
        self._clip(True)

    def _clip(self, is_cut: bool) -> None:
        """Record the cursor entry in the paste buffer with *is_cut*."""
        entry = self._cursor_entry()
        if entry is not None:
            self._clipboard = (entry.path, is_cut)

    def action_paste(self) -> None:
        """``p``: paste the buffer into the current directory.

        A cut buffer is consumed by the move, a copy buffer survives;
        conflicts surface on the input line, never silently overwritten.
        """
        if self._clipboard is None:
            self._show_input_error("clipboard is empty")
            return
        if self._cwd is None:
            return  # no target directory at the drive-letter level (Q4)
        source, is_cut = self._clipboard
        try:
            if is_cut:
                self.workspace.move_entry(source, self._cwd)
                self._clipboard = None
            else:
                self.workspace.copy_entry(source, self._cwd)
        except (FileExistsError, OSError) as exc:
            log.debug("file_manager paste failed: %s", exc)
            self._show_input_error(f"paste failed: {exc}")
            return
        self._drop_dir_cache()
        self.workspace.invalidate()
        self._reload()
