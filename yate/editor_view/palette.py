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
from pathlib import Path
from typing import Any

from collections.abc import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from yate.registries import ActionRegistry, CommandRegistry
from yate.services.workspace import Workspace

from . import theme
from .icons import GEAR, KEYBOARD, icon_for_path

#: maximum number of result rows rendered under the input
MAX_VISIBLE = 12


def fuzzy_match(query: str, target: str) -> tuple[int, list[int]] | None:
    """Subsequence-match *query* against *target* (case insensitive).

    Returns ``(score, matched_indices)`` (lower score = better) or ``None``
    when the query is not a subsequence of the target.
    """
    if not query:
        return (0, [])
    q = query.lower()
    t = target.lower()
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


class PaletteScreen(ModalScreen[None]):
    """Fuzzy palette overlay for files (quick open) or commands."""

    BINDINGS = [
        ("escape", "dismiss", "close"),
        ("ctrl+c", "dismiss", "close"),
    ]

    DEFAULT_CSS = """
    PaletteScreen {
        align: center top;
    }
    PaletteScreen #palette {
        width: 70%;
        max-width: 90;
        height: 14;
        margin-top: 3;
        border: tall $primary;
        background: $surface;
        padding: 0 1;
    }
    PaletteScreen #palette-input {
        height: 1;
        border: none;
        background: $surface;
        padding: 0;
    }
    PaletteScreen #palette-results {
        height: 1fr;
        padding: 0;
        background: $surface;
    }
    """

    def __init__(
        self,
        mode: str,
        *,
        workspace: Workspace,
        commands: CommandRegistry,
        actions: ActionRegistry,
        open_path: Callable[[Path], None],
        focus_editor: Callable[[], None],
        execute_action: Callable[[str], bool],
        run_command: Callable[[str], None],
        refresh: Callable[[], None],
        **kwargs: Any,
    ) -> None:
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
        self.mode = mode  # "files" | "commands"
        self._entries: list[tuple[str, str, Any]] = []  # (display, hint, payload)
        self._filtered: list[tuple[int, list[int], int]] = []  # (score, hits, idx)
        self._cursor = 0
        # shown in the results pane while the file index builds in a thread
        self._status_message: str | None = None

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
        self._entries = entries

    async def _index_files(self) -> None:
        """Build the file list in a thread so large workspaces do not
        freeze the UI when the palette opens."""
        try:
            entries = await asyncio.to_thread(self._collect_file_entries)
        except OSError:
            entries = []
        if not self.is_mounted:
            return
        self._entries = entries
        self._status_message = None
        query = self.query_one("#palette-input", Input).value
        self.refilter(query)

    def refilter(self, query: str) -> None:
        scored: list[tuple[int, list[int], int]] = []
        for i, (display, hint, _payload) in enumerate(self._entries):
            match = fuzzy_match(query, display)
            hits: list[int] = []
            if match is not None:
                score, hits = match
            elif self.mode == "commands" and hint:
                # description-only matches (e.g. "save" finds :w) rank
                # below every name match
                desc_match = fuzzy_match(query, hint)
                if desc_match is None:
                    continue
                score = desc_match[0] + 1000
            else:
                continue
            scored.append((score, hits, i))
        scored.sort(key=lambda item: (item[0], self._entries[item[2]][0].lower()))
        self._filtered = scored[:MAX_VISIBLE]
        self._cursor = 0
        self._render_results()

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

    # ------------------------------------------------------------- textual

    def compose(self) -> ComposeResult:
        with Vertical(id="palette"):
            placeholder = (
                "search files by name…" if self.mode == "files"
                else "search commands and actions by name…"
            )
            yield Input(placeholder=placeholder, id="palette-input")
            yield Static(id="palette-results")

    def on_mount(self) -> None:
        # Colors come from the DEFAULT_CSS design tokens ($surface/$primary),
        # which track Textual's dark/light mode; result rows use the active
        # Catppuccin palette via Rich styles.
        if self.mode == "files":
            # walking a big workspace would freeze the modal on open; build
            # the file index in a worker thread with a status line
            self._status_message = " indexing workspace…"
            self._render_results()
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
        if event.input.id == "palette-input":
            self.refilter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "palette-input":
            return
        self._choose()

    def on_key(self, event: Key) -> None:
        if event.key in ("up", "ctrl+p", "shift+tab"):
            event.stop()
            event.prevent_default()
            if self._filtered:
                self._cursor = (self._cursor - 1) % len(self._filtered)
                self._render_results()
        elif event.key in ("down", "ctrl+n", "tab"):
            event.stop()
            event.prevent_default()
            if self._filtered:
                self._cursor = (self._cursor + 1) % len(self._filtered)
                self._render_results()
                # A single match is unambiguous: let Tab choose it immediately
                # (bash-style: unique completion is applied at once).
                if len(self._filtered) == 1:
                    self._choose()

    # ------------------------------------------------------------- actions

    def _choose(self) -> None:
        if not self._filtered:
            return
        _score, _hits, idx = self._filtered[self._cursor]
        _display, _hint, payload = self._entries[idx]
        self.dismiss()
        if self.mode == "files":
            self.open_path(payload)
            self.focus_editor()
        else:
            kind, name = payload
            if kind == "action":
                self.execute_action(str(name))
                # key dispatch refreshes the editor after an action; the
                # palette bypasses the key path, so do it here too
                self.refresh_ui()
            else:
                self.run_command(str(name))


def _walk(root: Path, limit: int = 5000) -> list[Path]:
    """Fallback file walk (no workspace root set); mirrors Workspace logic."""
    ws = Workspace(root)
    return ws.walk_files(limit=limit)
