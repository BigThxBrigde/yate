"""VS Code-style command palette and quick file open (fuzzy filtered modal).

Two modes share one widget:

* ``"files"`` (ctrl+p): fuzzy search over the workspace files, enter opens.
* ``"commands"`` (alt+shift+p): fuzzy search over
  ``:`` commands, enter runs.

The fuzzy matcher is a plain subsequence scorer (fzf-style): every query
character must appear in order; matches at word starts / path boundaries
score better than gap matches.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from itertools import islice
from pathlib import Path
from typing import Any, override

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Input, RichLog, Static

from yate.config import FilePreviewConfig
from yate.editor_syntax.engine import tokenize_document
from yate.editor_syntax.tokens import Token
from yate.keymaps.base import ActionRunner
from yate.logs import tracing
from yate.paths import load_tcss
from yate.registries import ActionRegistry, Command, CommandRegistry
from yate.services.workspace import Workspace

from yate.editor_view import theme
from yate.editor_view.icons import GEAR, KEYBOARD, icon_for_path
from yate.editor_view.scrollbars import apply_scrollbar_theme, apply_slim_scrollbars

#: maximum number of result rows rendered under the input
MAX_VISIBLE: int = 12

log = tracing.get_logger(__name__)


@dataclass(frozen=True)
class _PreviewData:
    """Worker-produced preview payload (raw lines + tokens, no widgets)."""

    path: Path
    lines: list[str]
    tokens: list[list[Token]]
    mtime_ns: int
    size: int
    truncated: bool
    note: str | None  # binary / oversize / unreadable explanation


#: preview cache entry cap (FIFO eviction)
PREVIEW_CACHE_SIZE: int = 16


def fuzzy_match(query: str, target: str) -> tuple[int, list[int]] | None:
    """Subsequence-match *query* against *target* (case insensitive).

    Returns ``(score, matched_indices)`` (lower score = better) or ``None``
    when the query is not a subsequence of the target.
    """
    return _match_lowered(query.lower(), target.lower(), query, target)


def _match_lowered(
    q: str, t: str, query: str, target: str
) -> tuple[int, list[int]] | None:
    """Core of :func:`fuzzy_match` with the case-folding already done.

    *q* is the lowered query and *t* the lowered *target* (matched indices
    point into the original *target*, whose and *query*'s raw case only
    feed the exact-case bonus).  Palette refiltering calls this directly
    with pre-lowered entries so a keystroke does not re-``lower()`` every
    candidate string.
    """
    matched: list[int] = []
    score = 0
    ti = 0
    for qi, qch in enumerate(q):
        # skip whitespace in the query (typing "ctrlp" matches "ctrl p")
        if qch.isspace():
            continue
        idx = t.find(qch, ti)
        if idx == -1:
            return None
        matched.append(idx)
        if idx == ti and qi > 0:
            penalty = 0  # consecutive characters: best score
        elif idx == 0 or t[idx - 1] in "/\\._- ":
            penalty = 1  # word / path boundary start
        else:
            penalty = 2 + (idx - ti)  # gap penalty
        score += penalty
        # exact-case bonus
        if target[idx] == query[qi]:
            score -= 1
        ti = idx + 1
    return (score, matched)


class PreviewLog(RichLog):
    """Read-only preview pane (source lines, syntax highlighted).

    ``can_focus = False`` keeps a mouse click on the pane from stealing
    focus away from the query input (one dispatch per keypress).
    """

    can_focus = False

    @override
    def on_mount(self) -> None:
        """Own the slim-scrollbar wiring and the theme painting."""
        # RichLog inherits ScrollView.on_mount (scrollbar visibility refresh).
        super().on_mount()
        # Same self-painting pattern as the explorer (issue IKJUU2): the
        # renderer sliver alone still shows Textual's opaque default track.
        apply_slim_scrollbars(self)
        self._apply_theme()
        theme.attach(self, self._apply_theme)

    def on_unmount(self) -> None:
        """Detach from the theme broadcast."""
        theme.detach(self)

    def _apply_theme(self) -> None:
        """Paint the scrollbar palette from the active theme (IKJUU2, IKINF3 pattern)."""
        apply_scrollbar_theme(self)


class PaletteScreen(ModalScreen[None]):
    """Fuzzy palette overlay for files (quick open) or commands."""

    BINDINGS = [
        ("escape", "dismiss", "close"),
        ("ctrl+c", "dismiss", "close"),
    ]

    DEFAULT_CSS = load_tcss("palette-screen.tcss")

    def __init__(
        self,
        mode: str,
        *,
        workspace: Workspace,
        commands: CommandRegistry,
        actions: ActionRegistry,
        open_path: Callable[[Path], None],
        focus_editor: Callable[[], None],
        execute_action: ActionRunner,
        run_command: Callable[[str], None],
        refresh: Callable[[], None],
        preview: FilePreviewConfig,
        **kwargs: Any,
    ) -> None:
        """Store collaborators; *preview* configures the ctrl+p preview pane.

        ``enable`` / ``position`` / ``size`` gate the pane's existence, side
        and width (files mode only); ``max_lines`` / ``max_size`` cap the
        worker's read.  Commands mode and ``enable = False`` keep the legacy
        DOM exactly.
        """
        super().__init__(**kwargs)
        self.workspace = workspace
        self.commands = commands
        self.actions = actions
        self.open_path = open_path
        self.focus_editor = focus_editor
        self.execute_action = execute_action
        self.run_command = run_command
        #: Editor repaint hook (named apart from ``Widget.refresh``).
        self.refresh_ui = refresh
        self.preview = preview
        self.mode = mode  # "files" | "commands"
        self._entries: list[tuple[str, str, Any]] = []  # (display, hint, payload)
        #: lower-cased mirrors of ``_entries`` columns, rebuilt together with
        #: them: refilter runs per keystroke and must not re-``lower()`` every
        #: candidate string each time (issue IKKSHY profiling)
        self._entries_lower: list[str] = []
        self._hints_lower: list[str] = []
        self._filtered: list[tuple[int, list[int], int]] = []  # (score, hits, idx)
        self._cursor = 0
        # shown in the results pane while the file index builds in a thread
        self._status_message: str | None = None
        # preview payloads keyed by path; validity is judged per record via
        # its mtime_ns/size pair (see _cache_current)
        self._preview_cache: dict[Path, _PreviewData] = {}
        #: ``None`` = command list mode; the command name = argument mode for
        #: that command (entered from a command whose ``arg_completer`` runs).
        self._arg_mode: str | None = None

    @property
    def filtered_count(self) -> int:
        """Number of rows currently visible after filtering."""
        return len(self._filtered)

    @property
    def cursor_index(self) -> int:
        """Index of the highlighted row within the filtered results."""
        return self._cursor

    # --------------------------------------------------------------- data

    def _collect_file_entries(self) -> list[tuple[str, str, Any]]:
        """Walk the workspace and build ``(label, hint, path)`` rows.

        Pure data prep (filesystem traversal + ``resolve`` per file), safe
        to run in a worker thread; it must not touch Textual widgets.
        """
        entries: list[tuple[str, str, Any]] = []
        if self.workspace.root is not None:
            root = self.workspace.root
            paths = self.workspace.walk_files()
        else:
            root = Path.cwd()
            paths = _walk(root)
        for path in paths:
            try:
                label = str(path.resolve().relative_to(root.resolve()))
            except ValueError:
                label = path.name
            entries.append((label.replace("\\", "/"), "", path))
        return entries

    def _build_command_entries(self) -> None:
        """Merge the ``:`` command table and the action registry.

        Every entry carries its full name plus a description, so both
        commands (``w``, ``theme`` ...) and keymap actions (``save``,
        ``move_left`` ...) -- including ones registered by extensions --
        are reachable from the palette.  A name present in both tables
        resolves to the ``:`` command (the same spelling typed on the ex
        line) and the raw action duplicate is dropped.
        """
        entries: list[tuple[str, str, Any]] = []
        for name in self.commands.names():
            # hide "palette" itself — opening the palette from inside the
            # palette would be a no-op and feels like recursion
            if name == "palette":
                continue
            entries.append((name, self.commands.describe(name), ("command", name)))
        command_names = {name for name, _h, _p in entries}
        for name, description in self.actions.describe():
            if name in command_names:
                continue
            entries.append((name, description, ("action", name)))
        entries.sort(key=lambda entry: entry[0])
        self._set_entries(entries)

    def _set_entries(self, entries: list[tuple[str, str, Any]]) -> None:
        """Store *entries* and the lower-cased mirrors :meth:`refilter` scores against."""
        self._entries = entries
        self._entries_lower = [display.lower() for display, _hint, _payload in entries]
        self._hints_lower = [hint.lower() for _display, hint, _payload in entries]

    async def _index_files(self) -> None:
        """Build the file list in a thread so large workspaces do not
        freeze the UI when the palette opens."""
        try:
            entries = await asyncio.to_thread(self._collect_file_entries)
        except OSError:
            entries = []
        if not self.is_mounted:
            return
        self._set_entries(entries)
        self._status_message = None
        query = self.query_one("#palette-input", Input).value
        self.refilter(query)

    def refilter(self, query: str) -> None:
        """Rescore entries against *query* and re-render the result list.

        Scores against the pre-lowered entry mirrors (``_entries_lower`` /
        ``_hints_lower``) with the query lowered once per keystroke; the
        per-candidate ``str.lower()`` allocations used to dominate large
        workspaces (issue IKKSHY profiling).
        """
        q = query.lower()
        commands_mode = self.mode == "commands"
        scored: list[tuple[int, list[int], int]] = []
        for i, (display, hint, _payload) in enumerate(self._entries):
            match = _match_lowered(q, self._entries_lower[i], query, display)
            hits: list[int] = []
            if match is not None:
                score, hits = match
            elif commands_mode and hint:
                # description-only matches (e.g. "save" finds :w) rank
                # below every name match
                desc_match = _match_lowered(q, self._hints_lower[i], query, hint)
                if desc_match is None:
                    continue
                score = desc_match[0] + 1000
            else:
                continue
            scored.append((score, hits, i))
        scored.sort(key=lambda item: (item[0], self._entries_lower[item[2]]))
        self._filtered = scored[:MAX_VISIBLE]
        self._cursor = 0
        self._render_results()
        self._update_preview()

    # -------------------------------------------------------------- render

    def _render_results(self) -> None:
        t = theme.active()
        results = self.query_one("#palette-results", Static)
        text = Text()
        if self._status_message is not None:
            text.append(self._status_message, style=t.fg_dim)
            results.update(text)
            return
        if not self._filtered:
            text.append("  no matches", style=t.fg_dim)
            results.update(text)
            return
        for row, (_score, hits, idx) in enumerate(self._filtered):
            display, hint, payload = self._entries[idx]
            selected = row == self._cursor
            bg = t.accent if selected else None
            base = f"bold {t.on_accent}" if selected else t.fg
            if self.mode == "files":
                icon = icon_for_path(display.rsplit("/", 1)[-1], False)
            elif self.mode == "commands" and payload[0] == "action":
                icon = KEYBOARD
            else:
                icon = GEAR
            text.append(" ", style=f"on {bg}" if bg else "")
            text.append(icon + " ", style=(f"{t.on_accent} on {bg}") if selected else t.fg_dim)
            hit_set = set(hits)
            for ci, ch in enumerate(display):
                style = (
                    f"bold {t.on_accent} on {bg}"
                    if selected
                    else (f"bold {t.accent}" if ci in hit_set else base)
                )
                text.append(ch, style=style)
            if hint:
                # cell count, not codepoints: a CJK filename occupies two
                # cells per glyph and would otherwise shift the hint column
                pad = max(1, 30 - theme.cell_len(display))
                text.append(" " * pad, style=f"on {bg}" if bg else "")
                text.append(hint, style=(f"{t.panel} on {bg}") if selected else t.fg_dim)
            text.append("\n")
        results.update(text)

    # ------------------------------------------------------------- preview

    def _preview_pane(self) -> PreviewLog:
        """Build the preview pane widget with its configured percent width."""
        pane = PreviewLog(id="palette-preview")
        # geometry is component-owned (theme rule): the width comes from the
        # config; colors stay in palette-screen.tcss / theme.active()
        pane.styles.width = f"{self.preview.size}%"
        return pane

    def _selected_path(self) -> Path | None:
        """Path payload of the highlighted entry, or ``None`` without one."""
        if (
            self.mode != "files"
            or self._status_message is not None
            or not self._filtered
        ):
            return None
        _score, _hits, idx = self._filtered[self._cursor]
        path: Path = self._entries[idx][2]
        return path

    def _cache_current(self, data: _PreviewData) -> bool:
        """Whether *data* still matches the file on disk (mtime/size probe)."""
        try:
            st = data.path.stat()
        except OSError:
            return False
        return st.st_mtime_ns == data.mtime_ns and st.st_size == data.size

    def _update_preview(self) -> None:
        """Refresh the preview pane for the highlighted file (files mode).

        Cache hits (validated by mtime/size) re-render at once; misses show
        a loading note and spawn the exclusive read+tokenize worker, whose
        completion re-checks the cursor and only repaints when still current.
        """
        if self.mode != "files" or not self.preview.enable:
            return
        path = self._selected_path()
        if path is None:
            self._clear_preview()
            return
        cached = self._preview_cache.get(path)
        if cached is not None and self._cache_current(cached):
            self._render_preview(cached)
            return
        # A stale entry would linger until FIFO eviction; drop it now so the
        # cache only ever holds payloads valid at their last probe.
        self._preview_cache.pop(path, None)
        self._show_loading()
        self.run_worker(
            # coroutine *function*: an eager coroutine would leak if
            # the worker never starts (closing pump)
            partial(self._load_preview_worker, path), group="palette-preview",
            exclusive=True, exit_on_error=False,
        )

    def _clear_preview(self) -> None:
        """Empty the preview pane (no highlighted entry to preview)."""
        self.query_one("#palette-preview", PreviewLog).clear()

    def _show_loading(self) -> None:
        """Dim loading note while the worker reads+tokenizes the file."""
        pane = self.query_one("#palette-preview", PreviewLog)
        pane.clear()
        pane.write(Text("loading…", style=theme.active().fg_dim))

    def _load_preview(self, path: Path) -> _PreviewData:
        """Read and tokenize *path* (worker thread; never touches widgets).

        Oversize and binary files degrade to a note payload with empty
        lines; successful reads keep the real ``stat`` fields so the cache
        can serve repeat cursor visits without re-reading.  Decoding is
        declared ``errors="replace"`` so odd bytes never raise.
        """
        try:
            st = path.stat()
        except OSError as exc:
            return _PreviewData(
                path=path, lines=[], tokens=[], mtime_ns=0, size=0,
                truncated=False, note=f"cannot read: {exc}",
            )
        if st.st_size > self.preview.max_size:
            return _PreviewData(
                path=path, lines=[], tokens=[],
                mtime_ns=st.st_mtime_ns, size=st.st_size, truncated=False,
                note=f"file too large (> {self.preview.max_size} bytes)",
            )
        if not Workspace.is_text_file(path):
            return _PreviewData(
                path=path, lines=[], tokens=[],
                mtime_ns=st.st_mtime_ns, size=st.st_size, truncated=False,
                note="(binary file)",
            )
        lines: list[str] = []
        truncated = False
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                lines = [
                    line.rstrip("\n") for line in islice(fh, self.preview.max_lines)
                ]
                truncated = next(fh, None) is not None
        except OSError as exc:
            return _PreviewData(
                path=path, lines=[], tokens=[],
                mtime_ns=st.st_mtime_ns, size=st.st_size, truncated=False,
                note=f"cannot read: {exc}",
            )
        # suffix-derived filetype, same rule as Document.filetype
        filetype = path.suffix.lower().lstrip(".") or "plaintext"
        tokens: list[list[Token]] = []
        try:
            tokens = tokenize_document(lines, filetype) if lines else []
        except Exception as exc:  # noqa: BLE001 - degrade to unhighlighted text
            # A tokenizer crash must never leave the pane stuck on
            # "loading…"; align one empty token row per line so _preview_text's
            # zip still walks every line and renders it plain via t.fg.
            log.warning("palette preview tokenize failed for %s: %s", path, exc)
            tokens = [[] for _ in lines]
        return _PreviewData(
            path=path, lines=lines, tokens=tokens,
            mtime_ns=st.st_mtime_ns, size=st.st_size,
            truncated=truncated, note=None,
        )

    def _cache_store(self, data: _PreviewData) -> None:
        """Add *data* to the preview cache, evicting the oldest over capacity.

        Insertion order is the eviction order (dicts keep it), so the entry
        furthest in the past is dropped first; the just-stored payload is
        never the eviction candidate.
        """
        self._preview_cache[data.path] = data
        while len(self._preview_cache) > PREVIEW_CACHE_SIZE:
            self._preview_cache.pop(next(iter(self._preview_cache)))

    async def _load_preview_worker(self, path: Path) -> None:
        """Read+tokenize *path* in a thread, then paint when still selected.

        The thread part does IO + tokenize only; the Rich Text assembly and
        the widget write stay on the UI thread (same split as the editor's
        highlight worker).  When the cursor moved on while the worker ran,
        the payload is cached but not painted.
        """
        data = await asyncio.to_thread(self._load_preview, path)
        if not self.is_mounted:
            return
        self._cache_store(data)
        if self._selected_path() != path:
            return
        self._render_preview(data)

    def _render_preview(self, data: _PreviewData) -> None:
        """Paint *data* into the preview pane (UI thread)."""
        t = theme.active()
        pane = self.query_one("#palette-preview", PreviewLog)
        pane.clear()
        if data.note is not None:
            pane.write(Text(data.note, style=t.fg_dim))
            return
        pane.write(self._preview_text(data))

    def _preview_text(self, data: _PreviewData) -> Text:
        """Assemble the syntax-highlighted preview text (UI thread).

        Token columns are clamped to the line length (backends may lag the
        source after the truncation cut); token-free spans render with the
        plain foreground.
        """
        t = theme.active()
        text = Text()
        for line, row_tokens in zip(data.lines, data.tokens):
            pos = 0
            for tok in row_tokens:
                start, end = min(tok.start, len(line)), min(tok.end, len(line))
                if start > pos:
                    text.append(line[pos:start], style=t.fg)
                text.append(line[start:end], style=t.syntax_style(tok.kind))
                pos = max(pos, end)
            if pos < len(line):
                text.append(line[pos:], style=t.fg)
            text.append("\n")
        if data.truncated:
            text.append(
                f"… truncated at {self.preview.max_lines} lines", style=t.fg_dim
            )
        return text

    # ------------------------------------------------------------- textual

    @override
    def compose(self) -> ComposeResult:
        """Compose the query input, results list and optional preview pane."""
        with Vertical(id="palette"):
            placeholder = (
                "search files by name…" if self.mode == "files"
                else "search commands and actions by name…"
            )
            yield Input(placeholder=placeholder, id="palette-input")
            if self.mode == "files" and self.preview.enable:
                # scopes the wider #palette layout in palette-screen.tcss
                self.add_class("with-preview")
                with Horizontal(id="palette-body"):
                    if self.preview.position == "left":
                        yield self._preview_pane()
                    yield Static(id="palette-results")
                    if self.preview.position != "left":
                        yield self._preview_pane()
            else:
                # legacy DOM: the results list sits directly under #palette
                yield Static(id="palette-results")

    def on_mount(self) -> None:
        """Index files (worker) or build command entries, then focus the input."""
        # Colors come from the DEFAULT_CSS design tokens ($surface/$primary),
        # which track Textual's dark/light mode; result rows use the active
        # Catppuccin palette via Rich styles.
        if self.mode == "files":
            # walking a big workspace would freeze the modal on open; build
            # the file index in a worker thread with a status line
            self._status_message = " indexing workspace…"
            self._render_results()
            if self.preview.enable:
                self._update_preview()
            self.run_worker(
                # coroutine *function*: an eager coroutine would leak if
                # the worker never starts (closing pump)
                self._index_files, group="palette-index",
                exclusive=True, exit_on_error=False,
            )
        else:
            self._build_command_entries()
            self.refilter("")
        self.query_one("#palette-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Refilter the entries as the query changes."""
        if event.input.id == "palette-input":
            self.refilter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter picks the highlighted entry."""
        if event.input.id != "palette-input":
            return
        self._choose()

    def on_key(self, event: Key) -> None:
        """Move the selection (a unique Tab match is chosen at once)."""
        if event.key == "escape" and self._arg_mode is not None:
            # In argument mode escape steps back to the command list instead
            # of dismissing the palette; stopping the event keeps the
            # screen's escape -> dismiss binding out of the way.
            event.stop()
            event.prevent_default()
            self._exit_argument_mode()
            return
        if event.key in ("up", "ctrl+p", "shift+tab"):
            event.stop()
            event.prevent_default()
            if self._filtered:
                self._cursor = (self._cursor - 1) % len(self._filtered)
                self._render_results()
                self._update_preview()
        elif event.key in ("down", "ctrl+n", "tab"):
            event.stop()
            event.prevent_default()
            if self._filtered:
                self._cursor = (self._cursor + 1) % len(self._filtered)
                self._render_results()
                self._update_preview()
                # A single match is unambiguous: let Tab choose it immediately
                # (bash-style: unique completion is applied at once).  Plain
                # cursor movement (down / ctrl+n) must never execute anything.
                if event.key == "tab" and len(self._filtered) == 1:
                    self._choose()

    # ------------------------------------------------------------- actions

    def _choose(self) -> None:
        if not self._filtered:
            return
        _score, _hits, idx = self._filtered[self._cursor]
        _display, _hint, payload = self._entries[idx]
        if self._arg_mode is not None:
            # Argument mode: payload is ("arg", "<cmd> <value>"); submit the
            # full command string at once.
            self.dismiss()
            _kind, full = payload
            self.run_command(str(full))
            return
        if self.mode == "files":
            self.dismiss()
            self.open_path(payload)
            self.focus_editor()
        else:
            kind, name = payload
            if kind == "action":
                self.dismiss()
                self.execute_action(str(name))
                # key dispatch refreshes the editor after an action; the
                # palette bypasses the key path, so do it here too
                self.refresh_ui()
            else:
                cmd_entry = self.commands.get(str(name))
                if cmd_entry is not None and cmd_entry.arg_completer is not None:
                    # A parameterized command: pick its argument inside the
                    # palette instead of running it bare.
                    self._enter_argument_mode(cmd_entry)
                    return
                self.dismiss()
                self.run_command(str(name))

    def _enter_argument_mode(self, cmd_entry: Command) -> None:
        """Switch the palette to argument selection for *cmd_entry*.

        The query input is cleared and repurposed as an argument filter; the
        entry list is replaced with the values the command's ``arg_completer``
        offers for an empty prefix, each carrying the full ``"cmd value"``
        payload for the final submission.
        """
        self._arg_mode = cmd_entry.name
        completer = cmd_entry.arg_completer
        if completer is None:  # pragma: no cover - guarded by _choose
            return
        values = completer("")
        self._set_entries(
            [(value, "", ("arg", f"{cmd_entry.name} {value}")) for value in values]
        )
        input_widget = self.query_one("#palette-input", Input)
        input_widget.placeholder = f"argument for :{cmd_entry.name}"
        input_widget.value = ""
        self.refilter(input_widget.value)

    def _exit_argument_mode(self) -> None:
        """Leave argument mode: restore the command list (Esc, not dismiss)."""
        self._arg_mode = None
        input_widget = self.query_one("#palette-input", Input)
        input_widget.placeholder = "search commands and actions by name…"
        self._build_command_entries()
        input_widget.value = ""
        self.refilter(input_widget.value)


def _walk(root: Path) -> list[Path]:
    """Fallback file walk (no workspace root set); mirrors Workspace logic.

    Uses :meth:`Workspace.walk_files`' own default limit so the two entry
    points cannot drift apart.
    """
    return Workspace(root).walk_files()
